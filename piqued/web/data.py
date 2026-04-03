"""Shared data-fetching logic for web and API routes."""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from piqued import config
from piqued.models import (
    ApiKey,
    Article,
    ArticleStatus,
    Feed,
    Feedback,
    InterestWeight,
    ProcessingLog,
    SectionScore,
    User,
    UserProfile,
)
from piqued.processing.scorer import score_section, select_surprise_sections

logger = logging.getLogger(__name__)


async def _get_section_scores(
    session: AsyncSession,
    user: User,
    sections: list,
    tag_weights: dict[str, float],
    total_feedback: int,
) -> dict[int, tuple[float, str | None]]:
    """Get per-user scores using hybrid strategy: cached LLM scores then formula fallback."""
    scoring_mode = config.get("scoring_mode") or "hybrid"
    section_ids = [s.id for s in sections]
    scores: dict[int, tuple[float, str | None]] = {}

    if scoring_mode in ("hybrid", "llm") and section_ids:
        profile = await session.get(UserProfile, user.id)
        current_version = profile.profile_version if profile else 0
        cached = await session.execute(
            select(SectionScore).where(
                SectionScore.user_id == user.id,
                SectionScore.section_id.in_(section_ids),
                SectionScore.profile_version >= current_version,
            )
        )
        for cs in cached.scalars():
            scores[cs.section_id] = (cs.score, cs.reasoning)

    if scoring_mode in ("hybrid", "formula"):
        for section in sections:
            if section.id not in scores:
                confidence = score_section(
                    tag_weights, section.tags_list, total_feedback
                )
                scores[section.id] = (confidence, None)
    else:
        for section in sections:
            if section.id not in scores:
                scores[section.id] = (0.5, None)

    return scores


async def _get_user_weights(
    session: AsyncSession, user: User
) -> tuple[dict[str, float], int, list]:
    """Return (tag_weights, total_feedback, weight_objects) for a user."""
    result = await session.execute(
        select(InterestWeight).where(InterestWeight.user_id == user.id)
    )
    weight_objects = list(result.scalars())
    tag_weights = {w.topic: w.weight for w in weight_objects}
    total_feedback = sum(w.feedback_count for w in weight_objects)
    return tag_weights, total_feedback, weight_objects


async def get_home_sections(
    user: User, date: str | None, session: AsyncSession
) -> dict:
    """Data for triage view: scored sections, dates, threshold, surprises."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    result = await session.execute(
        select(Article)
        .where(Article.digest_date == date, Article.status == ArticleStatus.complete)
        .options(selectinload(Article.sections), selectinload(Article.feed))
    )
    articles = list(result.scalars().unique().all())

    # Check if onboarding needed
    has_active_feeds = True
    if not articles:
        active_feeds = await session.scalar(
            select(func.count()).select_from(Feed).where(Feed.active.is_(True))
        )
        has_active_feeds = bool(active_feeds)

    tag_weights, total_feedback, weight_objects = await _get_user_weights(session, user)

    all_flat_sections = [s for a in articles for s in a.sections]
    score_map = await _get_section_scores(
        session, user, all_flat_sections, tag_weights, total_feedback
    )

    all_sections = []
    for article in articles:
        for section in article.sections:
            confidence, reasoning = score_map.get(section.id, (0.5, None))
            all_sections.append((section, article, confidence, reasoning))
    all_sections.sort(key=lambda x: x[2], reverse=True)

    threshold = config.get_float("confidence_threshold")
    section_scores = [(s.id, conf) for s, _, conf, _ in all_sections]
    surprise_ids = select_surprise_sections(
        section_scores, threshold, config.get_float("surprise_surface_pct"), date
    )

    dates_result = await session.execute(
        select(Article.digest_date)
        .where(Article.status == ArticleStatus.complete)
        .distinct()
        .order_by(Article.digest_date.desc())
        .limit(14)
    )
    available_dates = [r[0] for r in dates_result]

    return {
        "all_sections": all_sections,
        "surprise_ids": surprise_ids,
        "date": date,
        "available_dates": available_dates,
        "weights": {w.topic: w.weight for w in weight_objects},
        "threshold": threshold,
        "has_active_feeds": has_active_feeds,
        "poll_interval": config.get("feed_poll_interval_minutes"),
    }


async def get_feed_detail(feed_id: int, session: AsyncSession) -> dict | None:
    """Data for single feed view: feed + recent articles."""
    feed = await session.get(Feed, feed_id)
    if not feed:
        return None

    result = await session.execute(
        select(Article)
        .where(Article.feed_id == feed_id)
        .options(selectinload(Article.sections))
        .order_by(Article.published_at.desc())
        .limit(50)
    )
    articles = list(result.scalars().unique().all())

    return {"feed": feed, "articles": articles}


async def get_article_detail(
    article_id: int, user: User, session: AsyncSession
) -> dict | None:
    """Data for article view: article with scored sections."""
    result = await session.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(selectinload(Article.sections), selectinload(Article.feed))
    )
    article = result.scalar_one_or_none()
    if not article:
        return None

    tag_weights, total_feedback, weight_objects = await _get_user_weights(session, user)
    score_map = await _get_section_scores(
        session, user, article.sections, tag_weights, total_feedback
    )

    scored_sections = []
    for section in article.sections:
        confidence, reasoning = score_map.get(section.id, (0.5, None))
        scored_sections.append((section, confidence, reasoning))
    scored_sections.sort(key=lambda x: x[1], reverse=True)

    threshold = config.get_float("confidence_threshold")
    section_scores_list = [(s.id, conf) for s, conf, _ in scored_sections]
    surprise_ids = select_surprise_sections(
        section_scores_list,
        threshold,
        config.get_float("surprise_surface_pct"),
        article.digest_date,
    )

    return {
        "article": article,
        "scored_sections": scored_sections,
        "surprise_ids": surprise_ids,
        "weights": {w.topic: w.weight for w in weight_objects},
        "threshold": threshold,
    }


async def get_feeds_list(session: AsyncSession) -> dict:
    """Data for feed management: all feeds grouped by category."""
    result = await session.execute(select(Feed).order_by(Feed.category, Feed.title))
    feeds = list(result.scalars().all())

    categories: dict[str, list] = defaultdict(list)
    for feed in feeds:
        categories[feed.category].append(feed)

    return {"categories": dict(categories), "feeds": feeds, "feed_count": len(feeds)}


async def get_processing_log(
    session: AsyncSession, limit: int = 100, offset: int = 0
) -> dict:
    """Data for processing log with article title join."""
    total_result = await session.execute(
        select(func.count()).select_from(ProcessingLog)
    )
    total = total_result.scalar() or 0

    result = await session.execute(
        select(ProcessingLog, Article.title)
        .outerjoin(Article, ProcessingLog.article_id == Article.id)
        .order_by(ProcessingLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    entries = []
    for log, article_title in result:
        entries.append({"log": log, "article_title": article_title})

    return {"entries": entries, "limit": limit, "offset": offset, "total": total}


async def get_settings_data(user: User, session: AsyncSession) -> dict:
    """Data for settings page: config, weights, feedback, profile, users."""
    is_admin = user.role == "admin"

    current = {}
    secret_keys = {"api_key", "api_pass", "secret_key", "password"}
    for key in config.DEFAULTS:
        val = config.get(key)
        if is_admin:
            if any(s in key for s in secret_keys):
                current[key] = "••••••••" if val else ""
            else:
                current[key] = val
        else:
            if not any(s in key for s in secret_keys):
                current[key] = val

    weights_result = await session.execute(
        select(InterestWeight)
        .where(InterestWeight.user_id == user.id)
        .order_by(InterestWeight.weight.desc())
    )
    weights = list(weights_result.scalars().all())

    fb_result = await session.execute(
        select(Feedback)
        .where(Feedback.user_id == user.id)
        .options(selectinload(Feedback.section))
        .order_by(Feedback.created_at.desc())
        .limit(20)
    )
    recent_feedback = list(fb_result.scalars().all())

    user_profile = await session.get(UserProfile, user.id)

    all_users = []
    if is_admin:
        users_result = await session.execute(select(User).order_by(User.created_at))
        all_users = list(users_result.scalars().all())

    api_keys_result = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    api_keys = list(api_keys_result.scalars().all())

    return {
        "current": current,
        "is_admin": is_admin,
        "weights": weights,
        "recent_feedback": recent_feedback,
        "user_profile": user_profile,
        "all_users": all_users,
        "api_keys": api_keys,
    }


async def get_user_profile(user: User, session: AsyncSession) -> dict | None:
    """Data for user's interest profile + weights."""
    profile = await session.get(UserProfile, user.id)

    weights_result = await session.execute(
        select(InterestWeight)
        .where(InterestWeight.user_id == user.id)
        .order_by(InterestWeight.weight.desc())
    )
    weights = list(weights_result.scalars().all())

    return {
        "profile": profile,
        "weights": weights,
    }
