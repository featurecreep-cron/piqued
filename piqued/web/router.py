"""Web UI routes — piqued view, feeds, profile, log."""

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from piqued import config
from piqued.auth.deps import get_current_user, require_admin
from piqued.db import get_session
from piqued.ingestion.freshrss import FreshRSSClient
from piqued.models import (
    Article,
    ArticleStatus,
    Feed,
    Feedback,
    InterestWeight,
    ProcessingLog,
    Section,
    SectionScore,
    User,
    UserProfile,
)
from piqued.processing.scorer import score_section, select_surprise_sections

logger = logging.getLogger(__name__)


async def ensure_csrf_dep(request: Request):
    """Dependency that ensures CSRF token exists in session and on request.state."""
    try:
        if "csrf" not in request.session:
            import secrets
            request.session["csrf"] = secrets.token_hex(16)
        request.state.csrf = request.session["csrf"]
    except (AssertionError, AttributeError):
        request.state.csrf = ""


router = APIRouter(tags=["web"], dependencies=[Depends(ensure_csrf_dep)])

templates = Jinja2Templates(
    directory=str(Path(__file__).parent / "templates")
)


async def _get_section_scores(
    session: AsyncSession,
    user: User,
    sections: list,
    tag_weights: dict[str, float],
    total_feedback: int,
) -> dict[int, tuple[float, str | None]]:
    """Get scores for sections using hybrid strategy: cached LLM scores → formula fallback.

    Returns dict of section_id → (confidence, reasoning).
    """
    scoring_mode = config.get("scoring_mode") or "hybrid"
    section_ids = [s.id for s in sections]
    scores: dict[int, tuple[float, str | None]] = {}

    # Try cached LLM scores first (hybrid or llm mode)
    if scoring_mode in ("hybrid", "llm") and section_ids:
        # Only use scores from the current profile version
        profile = await session.get(UserProfile, user.id)
        current_version = profile.profile_version if profile else 0

        cached = await session.execute(
            select(SectionScore)
            .where(
                SectionScore.user_id == user.id,
                SectionScore.section_id.in_(section_ids),
                SectionScore.profile_version >= current_version,
            )
        )
        for cs in cached.scalars():
            scores[cs.section_id] = (cs.score, cs.reasoning)

    # Formula fallback for uncached sections (hybrid or formula mode)
    if scoring_mode in ("hybrid", "formula"):
        for section in sections:
            if section.id not in scores:
                confidence = score_section(tag_weights, section.tags_list, total_feedback)
                scores[section.id] = (confidence, None)
    else:
        # Pure LLM mode — uncached sections get neutral score
        for section in sections:
            if section.id not in scores:
                scores[section.id] = (0.5, None)

    return scores


@router.get("/", response_class=HTMLResponse)
async def home_view(
    request: Request,
    user: User = Depends(get_current_user),
    date: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Top Sections — flat triage view with per-user scoring."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    result = await session.execute(
        select(Article)
        .where(Article.digest_date == date, Article.status == ArticleStatus.complete)
        .options(selectinload(Article.sections), selectinload(Article.feed))
    )
    articles = list(result.scalars().unique().all())

    # Redirect to onboarding only if no active feeds (true fresh start)
    if not articles:
        active_feeds = await session.scalar(
            select(func.count()).select_from(Feed).where(Feed.active == True)
        )
        if not active_feeds:
            return RedirectResponse(url="/onboarding", status_code=303)

    # Per-user weights (for formula fallback + template display)
    weights_result = await session.execute(
        select(InterestWeight).where(InterestWeight.user_id == user.id)
    )
    user_weights = {w.topic: w for w in weights_result.scalars()}
    tag_weights = {topic: w.weight for topic, w in user_weights.items()}
    total_feedback = sum(w.feedback_count for w in user_weights.values())
    weights = {topic: w.weight for topic, w in user_weights.items()}

    # Hybrid scoring: cached LLM scores → formula fallback
    all_flat_sections = [s for a in articles for s in a.sections]
    score_map = await _get_section_scores(session, user, all_flat_sections, tag_weights, total_feedback)

    all_sections = []
    for article in articles:
        for section in article.sections:
            confidence, reasoning = score_map.get(section.id, (0.5, None))
            all_sections.append((section, article, confidence, reasoning))
    all_sections.sort(key=lambda x: x[2], reverse=True)

    # Per-user surprise surfacing
    threshold = config.get_float("confidence_threshold")
    section_scores = [(s.id, conf) for s, _, conf, _ in all_sections]
    surprise_ids = select_surprise_sections(
        section_scores, threshold, config.get_float("surprise_surface_pct"), date
    )

    # Available dates
    dates_result = await session.execute(
        select(Article.digest_date)
        .where(Article.status == ArticleStatus.complete)
        .distinct()
        .order_by(Article.digest_date.desc())
        .limit(14)
    )
    available_dates = [r[0] for r in dates_result]

    show_source = True

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "all_sections": all_sections,
            "surprise_ids": surprise_ids,
            "date": date,
            "available_dates": available_dates,
            "weights": weights,
            "threshold": threshold,
            "show_source": show_source,
            "is_configured": config.is_configured(),
            "poll_interval": config.get("feed_poll_interval_minutes"),
            "current_user": user,
        },
    )


@router.get("/feed/{feed_id}", response_class=HTMLResponse)
async def feed_view(
    request: Request,
    feed_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Articles for a specific feed."""
    feed = await session.get(Feed, feed_id)
    if not feed:
        return HTMLResponse("Feed not found", status_code=404)

    result = await session.execute(
        select(Article)
        .where(Article.feed_id == feed_id)
        .options(selectinload(Article.sections))
        .order_by(Article.published_at.desc())
        .limit(50)
    )
    articles = list(result.scalars().unique().all())

    return templates.TemplateResponse(
        request,
        "feed.html",
        {"feed": feed, "articles": articles, "current_user": user},
    )


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_view(
    request: Request,
    article_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Sections for a specific article."""
    result = await session.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(selectinload(Article.sections), selectinload(Article.feed))
    )
    article = result.scalar_one_or_none()
    if not article:
        return HTMLResponse("Article not found", status_code=404)

    # Per-user weights (for formula fallback + template display)
    weights_result = await session.execute(
        select(InterestWeight).where(InterestWeight.user_id == user.id)
    )
    user_weights = {w.topic: w for w in weights_result.scalars()}
    tag_weights = {topic: w.weight for topic, w in user_weights.items()}
    total_feedback = sum(w.feedback_count for w in user_weights.values())
    weights = {topic: w.weight for topic, w in user_weights.items()}

    # Hybrid scoring
    score_map = await _get_section_scores(session, user, article.sections, tag_weights, total_feedback)

    scored_sections = []
    for section in article.sections:
        confidence, reasoning = score_map.get(section.id, (0.5, None))
        scored_sections.append((section, confidence, reasoning))
    scored_sections.sort(key=lambda x: x[1], reverse=True)

    # Per-user surprise surfacing
    threshold = config.get_float("confidence_threshold")
    section_scores = [(s.id, conf) for s, conf, _ in scored_sections]
    surprise_ids = select_surprise_sections(
        section_scores, threshold, config.get_float("surprise_surface_pct"),
        article.digest_date,
    )

    show_source = False

    return templates.TemplateResponse(
        request,
        "article.html",
        {
            "article": article,
            "scored_sections": scored_sections,
            "surprise_ids": surprise_ids,
            "weights": weights,
            "threshold": threshold,
            "show_source": show_source,
            "current_user": user,
        },
    )


@router.get("/feeds", response_class=HTMLResponse)
async def feeds_page(
    request: Request, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Feed management page, grouped by category."""
    result = await session.execute(select(Feed).order_by(Feed.category, Feed.title))
    feeds = list(result.scalars().all())

    # Group by category
    from collections import defaultdict
    categories: dict[str, list] = defaultdict(list)
    for feed in feeds:
        categories[feed.category].append(feed)

    return templates.TemplateResponse(
        request, "feeds.html", {"categories": dict(categories), "feed_count": len(feeds), "current_user": user}
    )


@router.post("/feeds/toggle/{feed_id}")
async def toggle_feed(feed_id: int, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Toggle a feed's active status."""
    feed = await session.get(Feed, feed_id)
    if not feed:
        return {"ok": False, "active": False}
    feed.active = not feed.active
    await session.commit()
    return {"ok": True, "active": feed.active}


@router.post("/feeds/sync")
async def sync_feeds(user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Sync feed list from FreshRSS subscriptions."""
    client = FreshRSSClient()
    try:
        subs = await client.get_subscriptions()
        added = 0
        for sub in subs:
            feed_id = sub.get("id", "")
            title = sub.get("title", "")
            url = sub.get("url", "")
            # Extract category from GReader API
            categories = sub.get("categories", [])
            category = categories[0].get("label", "Uncategorized") if categories else "Uncategorized"

            existing = await session.scalar(
                select(Feed.id).where(Feed.freshrss_feed_id == feed_id)
            )
            if not existing:
                session.add(
                    Feed(
                        freshrss_feed_id=feed_id,
                        title=title,
                        url=url,
                        category=category,
                        active=False,
                    )
                )
                added += 1

        await session.commit()
        return {"ok": True, "total": len(subs), "added": added}
    finally:
        await client.close()


@router.get("/log", response_class=HTMLResponse)
async def log_page(
    request: Request, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Processing log page."""
    result = await session.execute(
        select(ProcessingLog)
        .order_by(ProcessingLog.created_at.desc())
        .limit(100)
    )
    logs = list(result.scalars().all())
    return templates.TemplateResponse(
        request, "log.html", {"logs": logs, "current_user": user}
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Settings page with profile tab — config + interest weights + feedback history."""
    from piqued.llm.factory import PROVIDERS

    # Current config values (masked for secrets)
    current = {}
    for key in config.DEFAULTS:
        val = config.get(key)
        if "api_key" in key or "api_pass" in key:
            current[key] = "••••••••" if val else ""
        else:
            current[key] = val

    # Profile data scoped to current user
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

    # User's interest profile
    user_profile = await session.get(UserProfile, user.id)

    # Admin: get all users for user management
    all_users = []
    if user.role == "admin":
        users_result = await session.execute(select(User).order_by(User.created_at))
        all_users = list(users_result.scalars().all())

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "current": current,
            "providers": sorted(PROVIDERS),
            "is_configured": config.is_configured(),
            "is_wizard": not config.is_configured(),
            "weights": weights,
            "recent_feedback": recent_feedback,
            "current_user": user,
            "user_profile": user_profile,
            "all_users": all_users,
        },
    )


@router.post("/settings")
async def save_settings(request: Request, admin: User = Depends(require_admin)):
    """Save settings from the form. Admin only."""
    from piqued.main import _start_scheduler

    form = await request.form()
    settings_to_save = {}

    for key in config.DEFAULTS:
        form_val = form.get(key)
        if form_val is None:
            continue
        form_val = str(form_val).strip()
        # Don't save masked placeholder back
        if "api_key" in key or "api_pass" in key:
            if form_val == "••••••••" or not form_val:
                continue
        settings_to_save[key] = form_val

    # Validate auth_methods — must contain at least one valid method
    if "auth_methods" in settings_to_save:
        methods = [m.strip() for m in settings_to_save["auth_methods"].split(",") if m.strip()]
        valid = {"oidc", "local", "header"}
        methods = [m for m in methods if m in valid]
        if not methods:
            methods = ["local"]  # fallback — never lock everyone out
        settings_to_save["auth_methods"] = ",".join(methods)

    # Server-side validation for numeric settings
    BOUNDS = {
        "feed_poll_interval_minutes": (1, 1440),
        "max_articles_per_cycle": (1, 50),
        "daily_token_budget": (1000, 10000000),
        "max_article_words": (500, 100000),
        "max_concurrent_articles": (1, 10),
        "max_retries": (1, 10),
        "confidence_threshold": (0.0, 1.0),
        "surprise_surface_pct": (0.0, 0.5),
        "interest_decay_rate": (0.0, 0.5),
        "interest_decay_after_days": (1, 365),
    }
    for key, (lo, hi) in BOUNDS.items():
        if key in settings_to_save:
            try:
                val = float(settings_to_save[key])
                val = max(lo, min(hi, val))
                settings_to_save[key] = str(int(val)) if isinstance(lo, int) else str(val)
            except (ValueError, TypeError):
                del settings_to_save[key]

    if settings_to_save:
        await config.save_settings(settings_to_save)
        await config.load_settings_from_db()  # refresh cache

    # Start scheduler if we just became configured
    if config.is_configured():
        _start_scheduler()

    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/profile")
async def save_profile(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Save user's edited interest profile. Bumps version, invalidates stale scores."""
    form = await request.form()
    profile_text = str(form.get("profile_text", "")).strip()

    profile = await session.get(UserProfile, user.id)
    if profile:
        profile.profile_text = profile_text
        profile.profile_version += 1
        profile.updated_at = datetime.now(timezone.utc)
    else:
        profile = UserProfile(
            user_id=user.id,
            profile_text=profile_text,
            profile_version=1,
        )
        session.add(profile)

    await session.commit()
    logger.info("Profile edited by user=%s, now v%d", user.username, profile.profile_version)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/profile/synthesize")
async def synthesize_profile_now(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Manually trigger profile synthesis from accumulated feedback."""
    profile = await session.get(UserProfile, user.id)
    if not profile:
        return RedirectResponse(url="/settings?error=No+profile+to+synthesize", status_code=303)

    # Trigger synthesis in background
    import asyncio
    from piqued.feedback.router import _trigger_synthesis
    asyncio.create_task(_trigger_synthesis(user.id))

    return RedirectResponse(url="/settings?msg=Synthesis+started", status_code=303)


@router.post("/admin/user/create")
async def admin_create_user(
    request: Request,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin: create a local user."""
    import bcrypt

    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    role = str(form.get("role", "user"))

    if not username or not password:
        return RedirectResponse(url="/settings?error=Username+and+password+required", status_code=303)
    if role not in ("admin", "user"):
        role = "user"

    # Check uniqueness
    existing = await session.scalar(select(User).where(User.username == username))
    if existing:
        return RedirectResponse(url="/settings?error=Username+already+exists", status_code=303)

    new_user = User(
        username=username,
        password_hash=bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        role=role,
        role_source="manual",
    )
    session.add(new_user)
    await session.commit()
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/admin/user/{user_id}/role")
async def admin_change_role(
    request: Request,
    user_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin: change a user's role."""
    form = await request.form()
    new_role = str(form.get("role", "user"))
    if new_role not in ("admin", "user"):
        new_role = "user"

    target = await session.get(User, user_id)
    if not target:
        return RedirectResponse(url="/settings", status_code=303)

    # Don't let admin demote themselves
    if target.id == admin.id and new_role != "admin":
        return RedirectResponse(url="/settings?error=Cannot+demote+yourself", status_code=303)

    target.role = new_role
    target.role_source = "manual"
    await session.commit()
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/article/{article_id}/process")
async def process_article_now(article_id: int, user: User = Depends(get_current_user)):
    """On-demand processing of a single article. Requires authentication."""
    from piqued.processing.pipeline import process_single_article

    result = await process_single_article(article_id)
    return {"ok": result == "processed", "result": result}


# ── Onboarding ────────────────────────────────────────────────


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Onboarding: activate feeds, then start reading."""
    # Check if user has any active feeds — if so, they're onboarded
    active_feeds = await session.scalar(
        select(func.count()).select_from(Feed).where(Feed.active == True)
    )
    if active_feeds:
        return RedirectResponse(url="/", status_code=303)

    # Always sync feeds from FreshRSS (merge — adds new, keeps existing)
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
            request, "onboarding.html",
            {"step": "error", "error_message": f"Could not sync feeds from FreshRSS: {e}", "current_user": user},
        )
    finally:
        await client.close()

    result = await session.execute(select(Feed).order_by(Feed.title))
    feeds = list(result.scalars().all())

    return templates.TemplateResponse(
        request, "onboarding.html", {"step": "feeds", "feeds": feeds, "current_user": user}
    )


@router.post("/onboarding/activate-feeds")
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
            request, "onboarding.html",
            {"step": "error", "error_message": "Please select at least one feed", "current_user": user},
        )

    # Activate selected feeds
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

    # Create profile for this user, seeded with interests if provided
    interests = str(form.get("interests", "")).strip()
    profile = await session.get(UserProfile, user.id)
    if not profile:
        profile = UserProfile(user_id=user.id, profile_text=interests)
        session.add(profile)
    elif interests and not profile.profile_text:
        profile.profile_text = interests
        profile.profile_version += 1

    await session.commit()
    logger.info("Onboarding complete: user=%s activated=%d feeds", user.username, activated)

    return RedirectResponse(url="/", status_code=303)


    # Legacy routes removed — onboarding no longer requires tag rating
