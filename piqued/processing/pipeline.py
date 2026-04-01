"""Processing pipeline: enrich → classify → segment → score → store."""

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from piqued import config
from piqued.db import async_session
from piqued.ingestion.classifier import classify_content, update_feed_quality
from piqued.ingestion.extractor import (
    MIN_FULL_TEXT_WORDS,
    count_words,
    enrich_content,
    extract_text,
)
from piqued.ingestion.freshrss import FeedItem, FreshRSSClient
from piqued.llm import create_client
from piqued.llm.base import LLMClient
from piqued.models import (
    Article,
    ArticleStatus,
    Feed,
    InterestWeight,
    ProcessingLog,
    Section,
)
from piqued.processing.budget import check_budget
# score_section + select_surprise_sections used at display time (web/router.py), not at ingest
from piqued.processing.segmenter import segment_article

logger = logging.getLogger(__name__)


def _get_llm_client(task: str = "primary") -> LLMClient:
    """Create an LLM client from DB settings for the given task."""
    llm_config = config.get_llm_config(task)
    return create_client(
        provider=llm_config["provider"],
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
    )

# Semaphore limits concurrent LLM calls (created lazily)
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(config.get_int("max_concurrent_articles"))
    return _semaphore


async def run_pipeline() -> dict:
    """Run the full processing pipeline. Called by scheduler every 15 min.

    Rate-limited: processes at most max_articles_per_cycle articles.
    Order controlled by backlog_order setting (newest_first or oldest_first).

    Returns:
        Summary dict with counts of fetched, processed, failed, skipped articles.
    """
    stats = {"fetched": 0, "processed": 0, "failed": 0, "skipped": 0, "budget_stop": 0}

    client = FreshRSSClient()
    try:
        # Crash recovery + fetch phase uses one session
        async with async_session() as session:
            await _recover_stuck_articles(session)

            feeds = await _get_active_feeds(session)
            if not feeds:
                logger.info("No active feeds configured")
                return stats

            new_items = await _fetch_new_items(client, feeds, session)
            stats["fetched"] = len(new_items)

        if not new_items:
            logger.info("No new articles to process")
            return stats

        # Rate limit: cap articles per cycle
        max_per_cycle = config.get_int("max_articles_per_cycle")
        if len(new_items) > max_per_cycle:
            logger.info(
                "Rate limiting: %d articles fetched, processing %d this cycle",
                len(new_items),
                max_per_cycle,
            )
            new_items = new_items[:max_per_cycle]

        # Process articles concurrently — each gets its own session
        tasks = [_process_article(article_id) for article_id in new_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                stats["failed"] += 1
                logger.error("Article processing error: %s", result)
            elif result == "processed":
                stats["processed"] += 1
            elif result == "budget_stop":
                stats["budget_stop"] += 1
            else:
                stats["skipped"] += 1

    finally:
        await client.close()

    # Post-ingest: score new sections for all users with profiles
    if stats["processed"] > 0:
        scoring_mode = config.get("scoring_mode") or "hybrid"
        if scoring_mode in ("hybrid", "llm"):
            try:
                await _score_for_all_users()
            except Exception as e:
                logger.exception("Post-ingest scoring failed: %s", e)

    logger.info("Pipeline complete: %s", stats)
    return stats


async def process_single_article(article_id: int) -> str:
    """Process a single article on-demand (from the UI "Process now" button).

    Returns: 'processed', 'failed', 'budget_stop', or 'skipped'.
    """
    return await _process_article(article_id)


async def _get_active_feeds(session: AsyncSession) -> list[Feed]:
    result = await session.execute(select(Feed).where(Feed.active.is_(True)))
    return list(result.scalars().all())


async def _fetch_new_items(
    client: FreshRSSClient, feeds: list[Feed], session: AsyncSession
) -> list[int]:
    """Fetch items from FreshRSS, dedup, store as pending articles. Returns article IDs."""
    article_ids = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for feed in feeds:
        feed_title = feed.title  # eagerly load before async calls
        feed_stream_id = feed.freshrss_feed_id
        feed_db_id = feed.id
        try:
            items = await client.get_all_stream_items(feed_stream_id)

            # Batch dedup: fetch all existing item IDs in one query
            item_ids = [item.item_id for item in items]
            if item_ids:
                existing_result = await session.execute(
                    select(Article.freshrss_item_id).where(
                        Article.freshrss_item_id.in_(item_ids)
                    )
                )
                existing_ids = {row[0] for row in existing_result}
            else:
                existing_ids = set()

            for item in items:
                if item.item_id in existing_ids:
                    continue

                article = Article(
                    freshrss_item_id=item.item_id,
                    feed_id=feed_db_id,
                    title=item.title,
                    url=item.url,
                    content_html=item.content_html,
                    published_at=item.published_at,
                    digest_date=today,
                    status=ArticleStatus.pending,
                )
                session.add(article)
                await session.flush()
                article_ids.append(article.id)

            await session.commit()
            logger.info("Fetched %d new items from '%s'", len(items), feed_title)

        except Exception as e:
            logger.error("Failed to fetch feed '%s': %s", feed_title, e)
            await session.rollback()

    # Sort by backlog_order setting
    if article_ids:
        order = config.get("backlog_order")
        # Query articles to sort by published_at
        result = await session.execute(
            select(Article.id, Article.published_at)
            .where(Article.id.in_(article_ids))
            .order_by(
                Article.published_at.desc()
                if order == "newest_first"
                else Article.published_at.asc()
            )
        )
        article_ids = [row[0] for row in result]

    return article_ids


async def _process_article(article_id: int) -> str:
    """Process a single article: enrich → classify → segment → score → store.

    Each article gets its own DB session for safe concurrency.
    Returns: 'processed', 'failed', 'budget_stop', or 'skipped'.
    """
    async with _get_semaphore():
        start = time.monotonic()
        async with async_session() as session:
            try:
                article = await session.get(Article, article_id)
                if not article or article.status not in (
                    ArticleStatus.pending,
                    ArticleStatus.processing,
                ):
                    return "skipped"

                article.status = ArticleStatus.processing
                await session.commit()

                # Check budget
                budget_ok, _ = await check_budget(session)
                if not budget_ok:
                    article.status = ArticleStatus.pending
                    await session.commit()
                    return "budget_stop"

                # Get feed info
                feed = await session.get(Feed, article.feed_id)
                feed_name = feed.title if feed else "Unknown"
                feed_quality = feed.content_quality if feed else "unknown"

                # Skip enrichment+classification for feeds with known quality
                if feed_quality == "paywall":
                    article.status = ArticleStatus.skipped_paywall
                    await session.commit()
                    await _log(session, article_id, "classify", "skipped", "Feed marked as paywall")
                    return "skipped"

                # ENRICH: attempt to get full content if RSS is short
                content_html, enrich_source = await enrich_content(
                    article.content_html or "", article.url or ""
                )
                text = extract_text(content_html)

                if not text:
                    article.status = ArticleStatus.failed
                    await session.commit()
                    await _log(session, article_id, "extract", "error", "Empty content")
                    return "failed"

                # CLASSIFY: LLM determines content type (post-enrichment)
                classify_client = _get_llm_client("classify")
                try:
                    classification, cls_confidence, cls_tokens = await classify_content(
                        classify_client, text, article.title, feed_name, article.url or ""
                    )
                finally:
                    if hasattr(classify_client, 'close'):
                        await classify_client.close()
                await _log(
                    session, article_id, "classify", "ok",
                    f"{classification} ({cls_confidence:.0%})",
                    tokens_used=cls_tokens,
                )

                # Update feed quality tracking
                if feed:
                    new_quality, new_streak = update_feed_quality(
                        feed.content_quality, feed.quality_streak, classification
                    )
                    feed.content_quality = new_quality
                    feed.quality_streak = new_streak

                # Skip segmentation for non-articles
                if classification in ("paywall_page", "error_page", "login_wall"):
                    article.status = ArticleStatus.skipped_paywall
                    await session.commit()
                    return "skipped"
                if classification == "teaser" and count_words(text) < MIN_FULL_TEXT_WORDS:
                    article.status = ArticleStatus.skipped_teaser
                    await session.commit()
                    return "skipped"

                # Word count guard
                max_words = config.get_int("max_article_words")
                word_count = count_words(text)
                if word_count > max_words:
                    words = text.split()
                    text = " ".join(words[:max_words])
                    text += f"\n\n[Truncated from {word_count} words]"
                    await _log(
                        session, article_id, "guard", "warning",
                        f"Truncated {word_count} → {max_words} words",
                    )

                # Get global tag vocabulary for LLM reuse guidance
                existing_tags = await _get_global_tag_vocabulary(session)

                # SEGMENT: LLM breaks article into sections
                segment_client = _get_llm_client("primary")
                try:
                    sections, seg_tokens = await segment_article(
                        segment_client, text, article.title, feed_name, existing_tags
                    )
                finally:
                    if hasattr(segment_client, 'close'):
                        await segment_client.close()
                article.tokens_used = cls_tokens + seg_tokens

                await _log(
                    session, article_id, "summarize", "ok",
                    f"{len(sections)} sections, {seg_tokens} tokens",
                    tokens_used=seg_tokens,
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

                # Store sections with neutral default confidence (per-user scoring at display time)
                for i, seg in enumerate(sections):
                    section = Section(
                        article_id=article_id,
                        section_index=i,
                        heading=seg.heading,
                        summary=seg.summary,
                        topic_tags=",".join(seg.topic_tags),
                        confidence=0.5,  # neutral default; per-user scoring at display time
                        has_humor=seg.has_humor,
                        has_surprise_data=seg.has_surprise_data,
                        has_actionable_advice=seg.has_actionable_advice,
                        reasoning=seg.reasoning,
                    )
                    session.add(section)

                article.status = ArticleStatus.complete
                await session.commit()

                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "Processed '%s': %d sections, %d tokens, %dms",
                    article.title, len(sections), article.tokens_used, duration_ms,
                )
                return "processed"

            except Exception as e:
                logger.error("Failed to process article %d: %s", article_id, e)
                try:
                    article = await session.get(Article, article_id)
                    if article:
                        article.status = ArticleStatus.failed
                    await session.commit()
                except Exception:
                    await session.rollback()
                await _log(session, article_id, "pipeline", "error", str(e)[:500])
                return "failed"


async def _recover_stuck_articles(session: AsyncSession) -> int:
    """Reset articles stuck in 'processing' status (from crash recovery)."""
    result = await session.execute(
        select(Article).where(Article.status == ArticleStatus.processing)
    )
    stuck = list(result.scalars().all())
    for article in stuck:
        article.status = ArticleStatus.pending
        logger.info("Recovered stuck article: %s", article.title)
    if stuck:
        await session.commit()
    return len(stuck)


async def _get_global_tag_vocabulary(session: AsyncSession) -> list[str]:
    """Get all unique topic tags across all users (for LLM reuse guidance)."""
    from sqlalchemy import distinct
    result = await session.execute(select(distinct(InterestWeight.topic)))
    return [row[0] for row in result]


async def get_user_weights(session: AsyncSession, user_id: int) -> dict[str, InterestWeight]:
    """Get interest weights for a specific user."""
    result = await session.execute(
        select(InterestWeight).where(InterestWeight.user_id == user_id)
    )
    return {w.topic: w for w in result.scalars().all()}


async def _log(
    session: AsyncSession,
    article_id: int | None,
    stage: str,
    status: str,
    detail: str | None = None,
    tokens_used: int | None = None,
    duration_ms: int | None = None,
) -> None:
    """Write a processing log entry."""
    try:
        session.add(
            ProcessingLog(
                article_id=article_id,
                stage=stage,
                status=status,
                detail=detail,
                tokens_used=tokens_used,
                duration_ms=duration_ms,
            )
        )
        await session.commit()
    except Exception as e:
        logger.error("Failed to write processing log: %s", e)


async def _score_for_all_users():
    """Score newly ingested sections for all users with profiles."""
    from piqued.models import SectionScore, UserProfile
    from piqued.processing.profile_scorer import score_sections_for_user

    async with async_session() as session:
        # Get all users with profiles
        result = await session.execute(select(UserProfile))
        profiles = list(result.scalars().all())

        if not profiles:
            return

        # Get today's unscored sections
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for profile in profiles:
            try:
                # Find sections this user hasn't scored yet
                scored_ids_result = await session.execute(
                    select(SectionScore.section_id).where(
                        SectionScore.user_id == profile.user_id
                    )
                )
                scored_ids = {r[0] for r in scored_ids_result}

                # Get today's sections
                sections_result = await session.execute(
                    select(Section)
                    .join(Article, Section.article_id == Article.id)
                    .where(Article.digest_date == today, Article.status == ArticleStatus.complete)
                )
                all_sections = list(sections_result.scalars().all())
                unscored = [s for s in all_sections if s.id not in scored_ids]

                if not unscored:
                    continue

                # Batch-load articles and feeds to avoid N+1
                article_ids = list({s.article_id for s in unscored})
                articles_result = await session.execute(
                    select(Article).where(Article.id.in_(article_ids))
                )
                articles_map = {a.id: a for a in articles_result.scalars()}

                feed_ids = list({a.feed_id for a in articles_map.values()})
                feeds_result = await session.execute(
                    select(Feed).where(Feed.id.in_(feed_ids))
                )
                feeds_map = {f.id: f for f in feeds_result.scalars()}

                section_dicts = []
                for s in unscored:
                    article = articles_map.get(s.article_id)
                    feed = feeds_map.get(article.feed_id) if article else None
                    section_dicts.append({
                        "id": s.id,
                        "index": s.section_index,
                        "heading": s.heading or "",
                        "summary": s.summary[:200],
                        "tags": s.tags_list,
                        "feed_name": feed.title if feed else "",
                    })

                # Score via LLM
                scoring_client = _get_llm_client("scoring")
                try:
                    scored, tokens = await score_sections_for_user(
                        scoring_client, section_dicts, profile.profile_text
                    )

                    for sc in scored:
                        session.add(SectionScore(
                            user_id=profile.user_id,
                            section_id=sc.section_id,
                            score=sc.score,
                            reasoning=sc.reasoning,
                            profile_version=profile.profile_version,
                        ))

                    await session.commit()
                    logger.info(
                        "Scored %d sections for user %d (%d tokens)",
                        len(scored), profile.user_id, tokens,
                    )
                finally:
                    if hasattr(scoring_client, 'close'):
                        await scoring_client.close()

            except Exception as e:
                logger.exception(
                    "Scoring failed for user %d: %s", profile.user_id, e
                )
