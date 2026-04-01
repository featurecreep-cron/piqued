"""LLM-powered article segmentation — organic tags, reasoning, model-agnostic."""

import asyncio
import json
import logging
from dataclasses import dataclass

from piqued import config
from piqued.llm.base import LLMClient

logger = logging.getLogger(__name__)

SEGMENTATION_PROMPT = """You are a newsletter analyst. Break this article into logical sections that reflect the author's topic boundaries.

For each section, provide:
1. "heading": A short heading (5-10 words)
2. "summary": A concise summary (2-3 sentences, max 60 words)
3. "topic_tags": 1-3 descriptive topic tags in snake_case. Be specific (e.g. "securities_fraud_humor" not just "humor"). {tag_instruction}
4. "has_humor": true if funny or entertaining
5. "has_surprise_data": true if contains surprising data or counterintuitive findings
6. "has_actionable_advice": true if contains practical advice
7. "reasoning": One sentence explaining why a reader interested in these topics would care about this section

Article title: {title}
Article source: {feed_name}

Article text:
{text}

Respond with a JSON array of section objects."""


@dataclass
class SegmentedSection:
    """A section extracted by the LLM from an article."""

    heading: str
    summary: str
    topic_tags: list[str]
    has_humor: bool = False
    has_surprise_data: bool = False
    has_actionable_advice: bool = False
    reasoning: str = ""


async def segment_article(
    client: LLMClient,
    text: str,
    title: str,
    feed_name: str,
    existing_tags: list[str] | None = None,
) -> tuple[list[SegmentedSection], int]:
    """Segment and summarize an article using the LLM.

    Args:
        client: LLM client for segmentation.
        text: Plain text of the article.
        title: Article title.
        feed_name: Name of the source feed.
        existing_tags: Tags already in the DB (for reuse guidance).

    Returns:
        Tuple of (sections, tokens_used).
    """
    if existing_tags:
        tag_list = ", ".join(sorted(existing_tags)[:50])
        tag_instruction = f"Reuse these existing tags when appropriate: [{tag_list}]. You may create new tags if nothing fits."
    else:
        tag_instruction = "Create descriptive tags freely."

    prompt = SEGMENTATION_PROMPT.format(
        title=title,
        feed_name=feed_name,
        text=text,
        tag_instruction=tag_instruction,
    )

    max_retries = config.get_int("max_retries")
    tokens_used = 0
    last_error = None

    for attempt in range(max_retries):
        try:
            response = await client.generate(
                prompt,
                system_prompt="You are a newsletter analyst. Respond with valid JSON only.",
                json_mode=True,
                temperature=0.3,
            )

            tokens_used = response.tokens_used

            if not response.text:
                raise ValueError("Empty response from LLM")

            sections = _parse_response(response.text)
            if sections:
                logger.info(
                    "Segmented '%s' into %d sections (%d tokens)",
                    title, len(sections), tokens_used,
                )
                return sections, tokens_used

            raise ValueError("Parsed 0 sections from response")

        except Exception as e:
            last_error = e
            wait = 2 ** (attempt + 1)
            logger.warning(
                "Segmentation attempt %d/%d failed for '%s': %s. Retrying in %ds",
                attempt + 1, max_retries, title, str(e)[:200], wait,
            )
            await asyncio.sleep(wait)

    logger.error("All %d attempts failed for '%s': %s", max_retries, title, last_error)
    return _fallback_section(title, text), tokens_used


def _parse_response(text: str) -> list[SegmentedSection]:
    """Parse LLM's JSON response into SegmentedSection objects."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")

    sections = []
    for item in data:
        if not isinstance(item, dict):
            continue

        tags = item.get("topic_tags", [])
        if isinstance(tags, str):
            tags = [tags]
        tags = [normalize_tag(t) for t in tags[:3] if t and str(t).strip()]
        tags = [t for t in tags if t]

        sections.append(
            SegmentedSection(
                heading=str(item.get("heading", "")).strip(),
                summary=str(item.get("summary", "")).strip(),
                topic_tags=tags,
                has_humor=bool(item.get("has_humor", False)),
                has_surprise_data=bool(item.get("has_surprise_data", False)),
                has_actionable_advice=bool(item.get("has_actionable_advice", False)),
                reasoning=str(item.get("reasoning", "")).strip(),
            )
        )
    return sections


def normalize_tag(tag: str) -> str:
    """Normalize a topic tag: lowercase, replace spaces/hyphens with underscores."""
    tag = str(tag).lower().strip()
    tag = tag.replace(" ", "_").replace("-", "_")
    tag = "".join(c for c in tag if c.isalnum() or c == "_")
    while "__" in tag:
        tag = tag.replace("__", "_")
    return tag.strip("_")


def _fallback_section(title: str, text: str) -> list[SegmentedSection]:
    """Create a single fallback section when LLM segmentation fails."""
    preview = text[:500].strip()
    if len(text) > 500:
        preview += "..."
    return [
        SegmentedSection(
            heading=title,
            summary=f"[Segmentation unavailable] {preview}",
            topic_tags=[],
            reasoning="LLM segmentation failed — showing raw content preview.",
        )
    ]
