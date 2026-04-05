"""Web routes — onboarding (server-rendered, Jinja2)."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piqued.auth.deps import get_current_user
from piqued.db import get_session
from piqued.models import Feed, User, UserProfile

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ── Onboarding (stays at original paths) ─────────────────────────

onboarding_router = APIRouter(tags=["onboarding"])


@onboarding_router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Onboarding: activate feeds, then start reading."""
    from sqlalchemy import func

    active_feeds = await session.scalar(
        select(func.count()).select_from(Feed).where(Feed.active.is_(True))
    )
    if active_feeds:
        return RedirectResponse(url="/", status_code=303)

    from piqued.ingestion.freshrss import FreshRSSClient

    client = FreshRSSClient()
    try:
        subs = await client.get_subscriptions()
        for sub in subs:
            feed_id = sub.get("id", "")
            existing = await session.scalar(
                select(Feed.id).where(Feed.freshrss_feed_id == feed_id)
            )
            if not existing:
                cats = sub.get("categories", [])
                cat = cats[0].get("label", "Uncategorized") if cats else "Uncategorized"
                session.add(
                    Feed(
                        freshrss_feed_id=feed_id,
                        title=sub.get("title", ""),
                        url=sub.get("url", ""),
                        category=cat,
                        active=False,
                    )
                )
        await session.commit()
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "onboarding.html",
            {
                "step": "error",
                "error_message": f"Could not sync feeds from FreshRSS: {e}",
                "current_user": user,
            },
        )
    finally:
        await client.close()

    result = await session.execute(select(Feed).order_by(Feed.title))
    feeds = list(result.scalars().all())

    return templates.TemplateResponse(
        request,
        "onboarding.html",
        {"step": "feeds", "feeds": feeds, "current_user": user},
    )


@onboarding_router.post("/onboarding/activate-feeds")
async def onboarding_activate_feeds(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Activate selected feeds and start using Piqued."""
    form = await request.form()
    feed_ids = form.getlist("feed_ids")

    if not feed_ids:
        return templates.TemplateResponse(
            request,
            "onboarding.html",
            {
                "step": "error",
                "error_message": "Please select at least one feed",
                "current_user": user,
            },
        )

    activated = 0
    for fid in feed_ids:
        try:
            fid_int = int(fid)
        except (ValueError, TypeError):
            continue
        feed = await session.get(Feed, fid_int)
        if feed and not feed.active:
            feed.active = True
            activated += 1

    interests = str(form.get("interests", "")).strip()
    profile = await session.get(UserProfile, user.id)
    if not profile:
        profile = UserProfile(user_id=user.id, profile_text=interests)
        session.add(profile)
    elif interests and not profile.profile_text:
        profile.profile_text = interests
        profile.profile_version += 1

    await session.commit()
    logger.info(
        "Onboarding complete: user=%s activated=%d feeds", user.username, activated
    )

    return RedirectResponse(url="/", status_code=303)
