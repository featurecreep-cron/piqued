"""Feedback API endpoints — all scoped by current user."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piqued import config
from piqued.auth.deps import get_current_user
from piqued.db import get_session
from piqued.feedback.learner import update_weight
from piqued.models import (
    Article,
    Feed,
    Feedback,
    FeedbackSource,
    InterestWeight,
    Section,
    SectionScore,
    User,
    UserProfile,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackRequest(BaseModel):
    section_id: int
    rating: int = Field(ge=-1, le=1)
    source: str = "explicit"
    reason: str | None = None

    @property
    def validated_source(self) -> FeedbackSource:
        try:
            return FeedbackSource(self.source)
        except ValueError:
            return FeedbackSource.explicit


class FeedbackResponse(BaseModel):
    ok: bool
    direction: str


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    req: FeedbackRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Record feedback on a section and update user's interest model weights."""
    section = await session.get(Section, req.section_id)
    if not section:
        return FeedbackResponse(ok=False, direction="unchanged")

    source = req.validated_source

    # Dedup per user: max 1 explicit vote per section per user
    if source == FeedbackSource.explicit:
        existing = await session.scalar(
            select(Feedback.id).where(
                Feedback.section_id == req.section_id,
                Feedback.user_id == user.id,
                Feedback.source == FeedbackSource.explicit,
            )
        )
        if existing:
            fb = await session.get(Feedback, existing)
            if fb:
                fb.rating = req.rating
                fb.reason = req.reason
                await session.commit()
                direction = "higher" if req.rating > 0 else "lower"
                return FeedbackResponse(ok=True, direction=direction)

    # Determine signal strength
    if source == FeedbackSource.click_through:
        signal = 0.5
    else:
        signal = float(req.rating)
        # Bonus for liking low-confidence content (surprise discovery)
        if req.rating > 0:
            cached_score = await session.get(SectionScore, (user.id, req.section_id))
            threshold = float(config.get("confidence_threshold") or "0.4")
            if cached_score and cached_score.score < threshold:
                signal = 1.5  # Surprise thumbs-up bonus

    # Store feedback with user_id
    fb = Feedback(
        user_id=user.id,
        section_id=req.section_id,
        rating=req.rating,
        source=source,
        reason=req.reason,
    )
    session.add(fb)

    # Update user's interest weights for each tag
    tags = section.tags_list
    for tag in tags:
        # Composite PK lookup: (user_id, topic)
        weight_row = await session.get(InterestWeight, (user.id, tag))
        if weight_row is None:
            weight_row = InterestWeight(
                user_id=user.id, topic=tag, weight=0.0, feedback_count=0
            )
            session.add(weight_row)
            await session.flush()

        weight_row.weight = update_weight(
            weight_row.weight, signal, weight_row.feedback_count
        )
        weight_row.feedback_count += 1

    # Increment pending feedback count on user profile (for synthesis trigger)
    profile = await session.get(UserProfile, user.id)
    if profile:
        profile.pending_feedback_count += 1
    else:
        # Auto-create profile on first feedback
        profile = UserProfile(
            user_id=user.id, profile_text="", pending_feedback_count=1
        )
        session.add(profile)

    await session.commit()

    # Trigger profile synthesis if threshold reached
    threshold = config.get_int("profile_synthesis_threshold") or 3
    if profile.pending_feedback_count >= threshold:
        import asyncio

        asyncio.create_task(_trigger_synthesis(user.id))

    direction = "higher" if req.rating > 0 else "lower"
    logger.info(
        "Feedback: user=%s section=%d rating=%d (%s) tags=%s pending=%d",
        user.username,
        req.section_id,
        req.rating,
        source.value,
        tags,
        profile.pending_feedback_count,
    )
    return FeedbackResponse(ok=True, direction=direction)


async def _trigger_synthesis(user_id: int):
    """Background task: synthesize profile from accumulated feedback."""
    from piqued.db import async_session
    from piqued.feedback.synthesizer import synthesize_profile
    from piqued.llm.factory import create_client

    try:
        async with async_session() as session:
            profile = await session.get(UserProfile, user_id)
            if not profile or profile.pending_feedback_count == 0:
                return

            # Gather recent feedback with section context
            result = await session.execute(
                select(Feedback, Section)
                .join(Section, Feedback.section_id == Section.id)
                .where(Feedback.user_id == user_id)
                .order_by(Feedback.created_at.desc())
                .limit(profile.pending_feedback_count + 5)
            )

            feedback_batch = []
            for fb, sec in result:
                article = await session.get(Article, sec.article_id)
                feed_name = ""
                if article:
                    feed = await session.get(Feed, article.feed_id)
                    feed_name = feed.title if feed else ""
                feedback_batch.append(
                    {
                        "heading": sec.heading or "",
                        "summary": sec.summary[:200],
                        "tags": sec.tags_list,
                        "rating": fb.rating,
                        "reason": fb.reason or "",
                        "feed_name": feed_name,
                    }
                )

            if not feedback_batch:
                return

            llm_config = config.get_llm_config("primary")
            client = create_client(**llm_config)
            try:
                max_words = config.get_int("profile_max_words") or 500
                new_profile, tokens = await synthesize_profile(
                    client, profile.profile_text, feedback_batch, max_words
                )

                if new_profile:
                    profile.profile_text = new_profile
                    profile.profile_version += 1
                    profile.pending_feedback_count = 0
                    from datetime import datetime, timezone

                    profile.last_synthesized_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info(
                        "Profile synthesized for user %d: v%d (%d tokens)",
                        user_id,
                        profile.profile_version,
                        tokens,
                    )
            finally:
                if hasattr(client, "close"):
                    await client.close()

    except Exception as e:
        logger.exception("Profile synthesis failed for user %d: %s", user_id, e)


@router.post("/click-through")
async def record_click_through(
    section_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Record a click-through as implicit positive signal."""
    return await submit_feedback(
        FeedbackRequest(section_id=section_id, rating=1, source="click_through"),
        user=user,
        session=session,
    )


class DownweightRequest(BaseModel):
    tag: str


@router.post("/downweight")
async def downweight_tag(
    req: DownweightRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Reduce a topic's weight for the current user."""
    # Composite PK lookup: (user_id, topic)
    weight_row = await session.get(InterestWeight, (user.id, req.tag))
    if not weight_row:
        return {"ok": False, "new_weight": 0.0}

    new_weight = max(-1.0, weight_row.weight - 0.2)
    weight_row.weight = new_weight
    weight_row.feedback_count += 1
    await session.commit()

    logger.info(
        "Downweighted '%s' for user %s: → %.2f", req.tag, user.username, new_weight
    )
    return {"ok": True, "new_weight": new_weight}
