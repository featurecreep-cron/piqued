"""HTML → plain text extraction preserving structural hints for Gemini."""

import logging
import re

import httpx
from bs4 import BeautifulSoup, NavigableString
from readability import Document

logger = logging.getLogger(__name__)

# Minimum word count to consider RSS content "full text"
MIN_FULL_TEXT_WORDS = 100


def extract_text(html: str) -> str:
    """Convert HTML to structured plain text for LLM segmentation.

    Preserves:
    - Headings as markdown-style markers (## Heading)
    - Paragraph breaks as double newlines
    - List items as bullet points
    - Blockquotes as > prefixed lines
    - Horizontal rules as section dividers (---)

    Strips: images, scripts, styles, nav, footer, ads.
    """
    if not html or not html.strip():
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "aside", "iframe"]):
        tag.decompose()

    lines: list[str] = []
    _walk(soup, lines)

    text = "\n".join(lines)
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _walk(element, lines: list[str]) -> None:
    """Recursively walk the DOM and emit structured text."""
    for child in element.children:
        if isinstance(child, NavigableString):
            text = child.get_text()
            if text.strip():
                lines.append(text.strip())
            continue

        tag_name = child.name
        if tag_name is None:
            continue

        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_name[1])
            prefix = "#" * level
            heading_text = child.get_text(strip=True)
            if heading_text:
                lines.append("")
                lines.append(f"{prefix} {heading_text}")
                lines.append("")

        elif tag_name == "p":
            para_text = child.get_text(separator=" ", strip=True)
            if para_text:
                lines.append(para_text)
                lines.append("")

        elif tag_name in ("ul", "ol"):
            for li in child.find_all("li", recursive=False):
                li_text = li.get_text(strip=True)
                if li_text:
                    lines.append(f"- {li_text}")
            lines.append("")

        elif tag_name == "blockquote":
            bq_text = child.get_text(strip=True)
            if bq_text:
                for bq_line in bq_text.split("\n"):
                    if bq_line.strip():
                        lines.append(f"> {bq_line.strip()}")
                lines.append("")

        elif tag_name == "hr":
            lines.append("")
            lines.append("---")
            lines.append("")

        elif tag_name in ("br",):
            lines.append("")

        elif tag_name in ("div", "section", "article", "main"):
            _walk(child, lines)

        elif tag_name in ("a", "span", "strong", "em", "b", "i", "code", "mark"):
            # Inline elements — emit text content
            text = child.get_text(strip=True)
            if text:
                lines.append(text)

        elif tag_name == "pre":
            code_text = child.get_text()
            if code_text.strip():
                lines.append(f"```\n{code_text.strip()}\n```")
                lines.append("")

        elif tag_name == "table":
            # Flatten tables to rows of pipe-separated values
            for row in child.find_all("tr"):
                cells = [
                    td.get_text(strip=True) for td in row.find_all(["td", "th"])
                ]
                if any(cells):
                    lines.append("| " + " | ".join(cells) + " |")
            lines.append("")

        else:
            # Unknown tag — recurse into children
            _walk(child, lines)


def count_words(text: str) -> int:
    """Count words in plain text."""
    return len(text.split())


async def enrich_content(html: str, url: str) -> tuple[str, str]:
    """If RSS content is short (<100 words), attempt to fetch full article.

    Enrichment chain:
    1. Original URL → readability-lxml
    2. archive.is/latest/<url> → readability-lxml
    3. Give up → return original

    Returns:
        Tuple of (html_content, enrichment_source).
        enrichment_source is 'rss' (original), 'url', 'archive', or 'failed'.
    """
    text = extract_text(html)
    if count_words(text) >= MIN_FULL_TEXT_WORDS:
        return html, "rss"  # already have full content

    if not url:
        return html, "rss"

    original_words = count_words(text)

    # Attempt 1: fetch from original URL
    result = await _fetch_and_extract(url)
    if result and count_words(extract_text(result)) > original_words:
        logger.info("Enriched from URL: %d → %d words", original_words, count_words(extract_text(result)))
        return result, "url"

    # Attempt 2: try archive.is
    archive_url = f"https://archive.is/latest/{url}"
    result = await _fetch_and_extract(archive_url)
    if result and count_words(extract_text(result)) > original_words:
        logger.info("Enriched from archive.is: %d → %d words", original_words, count_words(extract_text(result)))
        return result, "archive"

    logger.info("Enrichment failed for %s — using RSS teaser (%d words)", url, original_words)
    return html, "failed"


async def _fetch_and_extract(url: str) -> str | None:
    """Fetch a URL and extract main content via readability. Returns HTML or None."""
    # SSRF protection
    from ipaddress import ip_address
    from socket import getaddrinfo
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logger.warning("Blocked non-HTTP URL: %s", url[:100])
        return None

    # Block private/internal IPs (fail closed — block on any error)
    try:
        hostname = parsed.hostname or ""
        addrs = getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addrs:
            addr = ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                logger.warning("Blocked private IP for %s: %s", url[:100], addr)
                return None
    except Exception as e:
        logger.warning("DNS check failed for %s, blocking: %s", url[:100], e)
        return None

    try:
        # follow_redirects=False to prevent SSRF via redirect to internal IPs
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=False,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        ) as client:
            resp = await client.get(url)
            # Handle redirects manually — validate each target
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location", "")
                if location:
                    return await _fetch_and_extract(location)  # recursive, re-validates
                return None
            resp.raise_for_status()

        doc = Document(resp.text)
        return doc.summary()

    except Exception as e:
        logger.debug("Fetch failed for %s: %s", url, str(e)[:100])
        return None
