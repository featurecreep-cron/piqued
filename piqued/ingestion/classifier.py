"""LLM-driven content classification — determines if content is a full article,
teaser, paywall page, error page, login wall, or bot/captcha challenge."""

import json
import logging

from piqued.llm.base import LLMClient

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Examine this content and classify it. The content was fetched from an RSS feed article.

Article title: {title}
Source feed: {feed_name}
Article URL: {url}

Content:
---
{content}
---

Classify this content into exactly one category:
- "full_article": This is the complete article text with substantial content
- "teaser": This is a short preview/excerpt, the full article exists elsewhere
- "paywall_page": This is a paywall notice, subscription prompt, or access-denied page
- "error_page": This is a 404, server error, or other technical error page
- "login_wall": This is a login/authentication required page
- "bot_challenge": This is a CAPTCHA, bot-detection page, or "verify you are human" challenge. Look for phrases like "unusual network activity", "verify you're not a robot", "checking your browser", "Cloudflare", "complete the security check", or short pages whose only purpose is to prove the user is human.

Respond with JSON: {{"classification": "<category>", "confidence": <0.0-1.0>, "reason": "<brief explanation>"}}"""


async def classify_content(
    client: LLMClient,
    content_text: str,
    title: str,
    feed_name: str,
    url: str,
) -> tuple[str, float, int]:
    """Classify article content using LLM.

    Args:
        client: LLM client for classification.
        content_text: Plain text of the article (post-enrichment).
        title: Article title.
        feed_name: Name of the source feed.
        url: Original article URL.

    Returns:
        Tuple of (classification, confidence, tokens_used).
        classification is one of: full_article, teaser, paywall_page, error_page,
        login_wall, bot_challenge.
    """
    # Truncate content for classification — don't need the full article
    truncated = content_text[:2000]
    if len(content_text) > 2000:
        truncated += "\n[... content continues ...]"

    prompt = CLASSIFICATION_PROMPT.format(
        title=title,
        feed_name=feed_name,
        url=url,
        content=truncated,
    )

    try:
        response = await client.generate(
            prompt,
            system_prompt="You are a content classifier. Respond only with the requested JSON.",
            json_mode=True,
            temperature=0.1,
            max_tokens=150,
        )

        data = json.loads(response.text)
        classification = data.get("classification", "full_article")
        confidence = float(data.get("confidence", 0.5))
        reason = data.get("reason", "")

        # Validate classification
        valid = {
            "full_article",
            "teaser",
            "paywall_page",
            "error_page",
            "login_wall",
            "bot_challenge",
        }
        if classification not in valid:
            logger.warning(
                "Invalid classification '%s', defaulting to full_article",
                classification,
            )
            classification = "full_article"

        logger.info(
            "Classified '%s': %s (%.0f%%) — %s [%d tokens]",
            title,
            classification,
            confidence * 100,
            reason,
            response.tokens_used,
        )
        return classification, confidence, response.tokens_used

    except Exception as e:
        logger.warning(
            "Classification failed for '%s': %s — defaulting to full_article", title, e
        )
        return "full_article", 0.5, 0


def update_feed_quality(
    current_quality: str,
    current_streak: int,
    new_classification: str,
) -> tuple[str, int]:
    """Update a feed's content_quality based on consecutive classifications.

    After 3+ consecutive same classification, lock the feed's quality.

    Args:
        current_quality: Feed's current content_quality value.
        current_streak: Feed's current quality_streak count.
        new_classification: The classification from the latest article.

    Returns:
        Tuple of (new_quality, new_streak).
    """
    # Map classifications to quality categories
    quality_map = {
        "full_article": "full",
        "teaser": "teaser",
        "paywall_page": "paywall",
        "error_page": "paywall",
        "login_wall": "paywall",
        "bot_challenge": "paywall",
    }
    mapped = quality_map.get(new_classification, "unknown")

    if current_quality == mapped:
        new_streak = current_streak + 1
    else:
        new_streak = 1

    # Lock after 3 consecutive same type
    if new_streak >= 3:
        return mapped, new_streak

    return "unknown", new_streak
