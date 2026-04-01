"""Daily token budget tracking and circuit breaker."""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from piqued import config
from piqued.models import ProcessingLog

logger = logging.getLogger(__name__)


async def get_daily_token_usage(session: AsyncSession, day: date | None = None) -> int:
    """Get total LLM tokens used today (all stages)."""
    if day is None:
        day = datetime.now(timezone.utc).date()

    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await session.scalar(
        select(func.coalesce(func.sum(ProcessingLog.tokens_used), 0)).where(
            ProcessingLog.created_at >= start,
            ProcessingLog.created_at <= end,
        )
    )
    return result or 0


async def check_budget(session: AsyncSession) -> tuple[bool, int]:
    """Check if daily token budget allows more processing.

    Returns:
        Tuple of (budget_available, tokens_used_today).
    """
    used = await get_daily_token_usage(session)
    budget = config.get_int("daily_token_budget")
    available = used < budget
    if not available:
        logger.warning("Daily token budget exhausted: %d / %d", used, budget)
    return available, used
