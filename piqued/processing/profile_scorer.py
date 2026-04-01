"""LLM-driven section scoring using natural language interest profiles."""

import json
import logging
from dataclasses import dataclass

from piqued.llm.base import LLMClient

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are scoring newsletter sections for a reader based on their interest profile.

Reader's interest profile:
{profile_text}

Score each section from 0.0 (definitely skip) to 1.0 (definitely read).
Consider the reader's specific interests, not just topic overlap. A section about "law" might score 0.9 if it's about constitutional rights (which they care about) or 0.2 if it's about criminal sentencing (which they don't).

For each section, return:
- "index": the section index from the input
- "score": float 0.0-1.0
- "reasoning": one sentence explaining WHY this score, referencing the reader's profile

Sections to score:
{sections_json}

Respond with a JSON array of objects."""

SCORING_PROMPT_NO_PROFILE = """You are scoring newsletter sections for a new reader with no established preferences.

Score each section from 0.0 (niche/narrow) to 1.0 (broadly interesting).
Default most sections to 0.4-0.6 (neutral). Only score high/low if the content is clearly broadly appealing or extremely niche.

Sections to score:
{sections_json}

Respond with a JSON array: [{{"index": N, "score": 0.5, "reasoning": "..."}}]"""


@dataclass
class ScoredSection:
    section_id: int
    section_index: int
    score: float
    reasoning: str


async def score_sections_for_user(
    client: LLMClient,
    sections: list[dict],
    profile_text: str | None = None,
) -> tuple[list[ScoredSection], int]:
    """Score a batch of sections using LLM + user's interest profile.

    Args:
        client: LLM client (ideally the "fast" tier).
        sections: List of dicts with keys: id, index, heading, summary, tags, feed_name.
        profile_text: User's natural language interest profile, or None for new users.

    Returns:
        Tuple of (scored sections, tokens_used).
    """
    if not sections:
        return [], 0

    sections_json = json.dumps([
        {
            "index": s["index"],
            "heading": s["heading"],
            "summary": s["summary"][:200],
            "tags": s["tags"],
            "source": s.get("feed_name", ""),
        }
        for s in sections
    ], indent=None)

    if profile_text and profile_text.strip():
        prompt = SCORING_PROMPT.format(
            profile_text=profile_text,
            sections_json=sections_json,
        )
    else:
        prompt = SCORING_PROMPT_NO_PROFILE.format(sections_json=sections_json)

    try:
        response = await client.generate(
            prompt,
            system_prompt="You are a content relevance scorer. Respond only with valid JSON.",
            json_mode=True,
            temperature=0.2,
        )

        results = _parse_scoring_response(response.text, sections)
        logger.info(
            "Scored %d sections (%d tokens), profile=%s",
            len(results), response.tokens_used,
            "yes" if profile_text else "no",
        )
        return results, response.tokens_used

    except Exception as e:
        logger.exception("LLM scoring failed: %s", e)
        return [], 0


def _parse_scoring_response(
    text: str, sections: list[dict]
) -> list[ScoredSection]:
    """Parse LLM scoring response into ScoredSection objects."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")

    # Build index→section_id lookup
    idx_to_id = {s["index"]: s["id"] for s in sections}

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        idx = item.get("index", -1)
        score = float(item.get("score", 0.5))
        score = max(0.0, min(1.0, score))
        reasoning = str(item.get("reasoning", "")).strip()

        section_id = idx_to_id.get(idx)
        if section_id is None:
            continue

        results.append(ScoredSection(
            section_id=section_id,
            section_index=idx,
            score=score,
            reasoning=reasoning,
        ))

    return results
