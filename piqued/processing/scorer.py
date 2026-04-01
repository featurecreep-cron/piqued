"""Interest model confidence scoring and surprise surfacing."""

import hashlib
import math


def sigmoid(x: float) -> float:
    """Standard sigmoid function, clamped to avoid overflow."""
    x = max(-20.0, min(20.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def compute_temperature(total_feedback: int) -> float:
    """Temperature starts wide (4.0) and narrows (2.0) as feedback grows.

    Wide temperature → scores spread toward 0/1 (more decisive but less calibrated).
    Narrow temperature → scores cluster near 0.5 (cautious).

    We start wide to give clear differentiation from day one, then narrow
    as the model accumulates real feedback data.
    """
    progress = min(total_feedback / 200.0, 1.0)
    return 4.0 - 2.0 * progress  # 4.0 → 2.0


def score_section(
    tag_weights: dict[str, float],
    section_tags: list[str],
    total_feedback: int,
) -> float:
    """Compute confidence score (0.0-1.0) for a section given its tags.

    Args:
        tag_weights: Current interest weights {topic: weight}.
        section_tags: Tags assigned to this section by Gemini.
        total_feedback: Total feedback signals across all tags (for temperature).

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    if not section_tags:
        return 0.5  # no tags → neutral

    weights = [tag_weights.get(tag, 0.0) for tag in section_tags]
    raw = sum(weights) / len(weights)
    temperature = compute_temperature(total_feedback)
    return sigmoid(raw * temperature)


def select_surprise_sections(
    section_ids_and_scores: list[tuple[int, float]],
    threshold: float,
    surface_pct: float,
    digest_date: str,
) -> set[int]:
    """Select low-confidence sections to surface as discoveries.

    Uses a seeded random based on digest_date for stable within-day display.

    Args:
        section_ids_and_scores: List of (section_id, confidence) tuples.
        threshold: Confidence threshold below which sections are eligible.
        surface_pct: Fraction of below-threshold sections to surface (e.g. 0.10).
        digest_date: YYYY-MM-DD string used as random seed for stability.

    Returns:
        Set of section IDs to mark as surprise/discovery.
    """
    below = [
        (sid, score) for sid, score in section_ids_and_scores if score < threshold
    ]
    if not below:
        return set()

    count = max(1, round(len(below) * surface_pct))

    # Deterministic selection: hash each section ID with the date,
    # sort by hash, take top `count`
    def sort_key(item: tuple[int, float]) -> str:
        sid = item[0]
        return hashlib.sha256(f"{digest_date}:{sid}".encode()).hexdigest()

    below_sorted = sorted(below, key=sort_key)
    return {sid for sid, _ in below_sorted[:count]}
