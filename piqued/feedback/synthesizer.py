"""LLM-driven interest profile synthesis from user feedback."""

import logging

from piqued.llm.base import LLMClient

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """You maintain a reader's interest profile — a natural language description of what they find interesting and what they don't care about.

Current profile:
{current_profile}

Since the last update, the reader gave this feedback on newsletter sections:
{feedback_items}

Update the interest profile to incorporate this feedback. Rules:
1. Keep the profile concise (under {max_words} words)
2. Be specific about nuance — "interested in constitutional law, especially individual rights" is better than "interested in law"
3. When feedback contradicts an existing preference, update or soften the preference
4. When feedback reinforces an existing preference, strengthen the language
5. Group related interests into paragraphs by theme
6. Include both positive interests AND things the reader doesn't care about
7. If the reader gave a reason for their feedback, use it to understand their thinking

Return ONLY the updated profile text. No preamble, no explanation."""

INITIAL_PROFILE_PROMPT = """Based on these reactions to newsletter sections, write an initial interest profile for this reader. Infer broad interests from specific reactions — don't just list the exact topics, generalize.

Feedback:
{feedback_items}

Write a concise interest profile (2-4 paragraphs, under {max_words} words) describing:
- What topics and angles interest this reader
- What they don't care about (if any negative signals)
- Any patterns in what they find engaging

Return ONLY the profile text. No preamble."""


async def synthesize_profile(
    client: LLMClient,
    current_profile: str | None,
    feedback_batch: list[dict],
    max_words: int = 500,
) -> tuple[str, int]:
    """Synthesize an updated interest profile from accumulated feedback.

    Args:
        client: LLM client (capable tier).
        current_profile: Existing profile text, or None/empty for initial creation.
        feedback_batch: List of dicts with keys:
            heading, summary, tags, rating (+1/-1), reason (optional), feed_name.
        max_words: Maximum profile length guidance.

    Returns:
        Tuple of (new_profile_text, tokens_used).
    """
    if not feedback_batch:
        return current_profile or "", 0

    feedback_text = _format_feedback(feedback_batch)

    if current_profile and current_profile.strip():
        prompt = SYNTHESIS_PROMPT.format(
            current_profile=current_profile,
            feedback_items=feedback_text,
            max_words=max_words,
        )
    else:
        prompt = INITIAL_PROFILE_PROMPT.format(
            feedback_items=feedback_text,
            max_words=max_words,
        )

    try:
        response = await client.generate(
            prompt,
            system_prompt="You are a reader profiling assistant. Write clear, specific interest profiles.",
            temperature=0.3,
        )

        profile = response.text.strip()
        if not profile:
            raise ValueError("Empty profile response")

        logger.info(
            "Profile synthesized (%d tokens): %d feedback items → %d words",
            response.tokens_used,
            len(feedback_batch),
            len(profile.split()),
        )
        return profile, response.tokens_used

    except Exception as e:
        logger.exception("Profile synthesis failed: %s", e)
        return current_profile or "", 0


def _format_feedback(feedback_batch: list[dict]) -> str:
    """Format feedback items for the LLM prompt."""
    lines = []
    for fb in feedback_batch:
        direction = "👍 Liked" if fb.get("rating", 0) > 0 else "👎 Disliked"
        tags = ", ".join(fb.get("tags", []))
        reason = fb.get("reason", "")

        line = f'- {direction}: "{fb.get("heading", "")}"'
        if tags:
            line += f" (topics: {tags})"
        if fb.get("feed_name"):
            line += f" — from {fb['feed_name']}"
        if fb.get("summary"):
            line += f"\n  Summary: {fb['summary'][:150]}"
        if reason:
            line += f"\n  Reason: {reason}"

        lines.append(line)

    return "\n".join(lines)
