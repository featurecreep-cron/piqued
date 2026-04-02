"""Interest model weight update logic (Exponential Weighted Average)."""

import logging
import math

logger = logging.getLogger(__name__)


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


async def apply_interest_decay():
    """Nightly job: decay weights that haven't been reinforced recently.

    Reduces weight magnitude by decay_rate for any InterestWeight
    whose updated_at is older than decay_after_days. Weights that
    decay below a threshold (0.01 magnitude) are left alone to avoid
    churning near-zero values.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from piqued import config
    from piqued.db import async_session
    from piqued.models import InterestWeight

    decay_rate = config.get_float("interest_decay_rate")
    decay_after_days = config.get_int("interest_decay_after_days")

    if decay_rate <= 0 or decay_after_days <= 0:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=decay_after_days)

    async with async_session() as session:
        result = await session.execute(
            select(InterestWeight).where(InterestWeight.updated_at < cutoff)
        )
        decayed = 0
        for weight in result.scalars():
            if abs(weight.weight) < 0.01:
                continue
            # Decay toward zero
            if weight.weight > 0:
                weight.weight = max(0.0, weight.weight - decay_rate)
            else:
                weight.weight = min(0.0, weight.weight + decay_rate)
            decayed += 1

        if decayed:
            await session.commit()
            logger.info("Interest decay: adjusted %d stale weights (cutoff=%s)", decayed, cutoff.date())
