"""Interest model weight update logic (Exponential Weighted Average)."""

import math


def compute_alpha(feedback_count: int) -> float:
    """Compute learning rate that's aggressive early, stabilizes with data.

    alpha = 0.3 / (1 + ln(feedback_count + 1))

    At count=0:  alpha ≈ 0.30  (aggressive)
    At count=5:  alpha ≈ 0.15
    At count=20: alpha ≈ 0.09
    At count=100: alpha ≈ 0.06  (stable)
    """
    return 0.3 / (1.0 + math.log(feedback_count + 1))


def update_weight(
    current_weight: float,
    rating: float,
    feedback_count: int,
) -> float:
    """Update a topic weight using EWA with adaptive alpha.

    Args:
        current_weight: Current weight for the topic, in [-1.0, +1.0].
        rating: Signal strength. Typical values:
            +1.0  explicit thumbs up
            -1.0  explicit thumbs down
            +0.5  click-through (implicit positive)
            -1.0  article-level thumbs down
            +1.5  surprise item thumbs up (stronger signal)
        feedback_count: Current feedback_count for this topic (before update).

    Returns:
        New weight, clamped to [-1.0, +1.0].
    """
    alpha = compute_alpha(feedback_count)
    new_weight = current_weight * (1.0 - alpha) + rating * alpha
    return max(-1.0, min(1.0, new_weight))
