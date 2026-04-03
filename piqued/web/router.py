"""Web UI routes — piqued view, feeds, profile, log."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piqued import config
from piqued.auth.deps import get_current_user, require_admin
from piqued.db import get_session
from piqued.models import Feed, User, UserProfile
from piqued.web.data import (
    get_article_detail,
    get_feed_detail,
    get_feeds_list,
    get_home_sections,
    get_processing_log,
    get_settings_data,
)

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

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def home_view(
    request: Request,
    user: User = Depends(get_current_user),
    date: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Top Sections — flat triage view with per-user scoring."""
    data = await get_home_sections(user, date, session)

    if not data["all_sections"] and not data["has_active_feeds"]:
        return RedirectResponse(url="/onboarding", status_code=303)

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            **data,
            "show_source": True,
            "is_configured": config.is_configured(),
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
    data = await get_feed_detail(feed_id, session)
    if not data:
        return HTMLResponse("Feed not found", status_code=404)

    return templates.TemplateResponse(
        request,
        "feed.html",
        {**data, "current_user": user},
    )


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_view(
    request: Request,
    article_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Sections for a specific article."""
    data = await get_article_detail(article_id, user, session)
    if not data:
        return HTMLResponse("Article not found", status_code=404)

    return templates.TemplateResponse(
        request,
        "article.html",
        {
            **data,
            "show_source": False,
            "current_user": user,
        },
    )


@router.get("/feeds", response_class=HTMLResponse)
async def feeds_page(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Feed management page, grouped by category."""
    data = await get_feeds_list(session)

    return templates.TemplateResponse(
        request,
        "feeds.html",
        {
            "categories": data["categories"],
            "feed_count": data["feed_count"],
            "current_user": user,
        },
    )


@router.post("/feeds/toggle/{feed_id}")
async def toggle_feed(
    feed_id: int,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Toggle a feed's active status."""
    feed = await session.get(Feed, feed_id)
    if not feed:
        return {"ok": False, "active": False}
    feed.active = not feed.active
    await session.commit()
    return {"ok": True, "active": feed.active}


@router.post("/feeds/sync")
async def sync_feeds(
    user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    """Sync feed list from FreshRSS subscriptions."""
    from piqued.ingestion.freshrss import FreshRSSClient

    client = FreshRSSClient()
    try:
        subs = await client.get_subscriptions()
        added = 0
        for sub in subs:
            feed_id = sub.get("id", "")
            title = sub.get("title", "")
            url = sub.get("url", "")
            categories = sub.get("categories", [])
            category = (
                categories[0].get("label", "Uncategorized")
                if categories
                else "Uncategorized"
            )

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
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Processing log page."""
    data = await get_processing_log(session)

    return templates.TemplateResponse(
        request,
        "log.html",
        {"logs": [e["log"] for e in data["entries"]], "current_user": user},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Settings page with profile tab — config + interest weights + feedback history."""
    from piqued.llm.factory import PROVIDERS

    data = await get_settings_data(user, session)

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "current": data["current"],
            "providers": sorted(PROVIDERS),
            "is_configured": config.is_configured(),
            "is_wizard": not config.is_configured(),
            "weights": data["weights"],
            "recent_feedback": data["recent_feedback"],
            "current_user": user,
            "user_profile": data["user_profile"],
            "all_users": data["all_users"],
            "api_keys": data["api_keys"],
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
        if "api_key" in key or "api_pass" in key:
            if form_val == "••••••••" or not form_val:
                continue
        settings_to_save[key] = form_val

    if "auth_methods" in settings_to_save:
        methods = [
            m.strip() for m in settings_to_save["auth_methods"].split(",") if m.strip()
        ]
        valid = {"oidc", "local", "header"}
        methods = [m for m in methods if m in valid]
        if not methods:
            methods = ["local"]
        settings_to_save["auth_methods"] = ",".join(methods)

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
                settings_to_save[key] = (
                    str(int(val)) if isinstance(lo, int) else str(val)
                )
            except (ValueError, TypeError):
                del settings_to_save[key]

    if settings_to_save:
        await config.save_settings(settings_to_save)
        await config.load_settings_from_db()

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
    logger.info(
        "Profile edited by user=%s, now v%d", user.username, profile.profile_version
    )
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
        return RedirectResponse(
            url="/settings?error=No+profile+to+synthesize", status_code=303
        )

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
        return RedirectResponse(
            url="/settings?error=Username+and+password+required", status_code=303
        )
    if role not in ("admin", "user"):
        role = "user"

    existing = await session.scalar(select(User).where(User.username == username))
    if existing:
        return RedirectResponse(
            url="/settings?error=Username+already+exists", status_code=303
        )

    new_user = User(
        username=username,
        password_hash=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        ),
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

    if target.id == admin.id and new_role != "admin":
        return RedirectResponse(
            url="/settings?error=Cannot+demote+yourself", status_code=303
        )

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


# ── API Keys ──────────────────────────────────────────────────


@router.post("/settings/keys/create")
async def create_api_key(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create an API key for the current user."""
    import hashlib
    import secrets

    from piqued.models import ApiKey

    form = await request.form()
    name = str(form.get("key_name", "")).strip() or "Unnamed"
    raw = secrets.token_hex(16)
    full_key = f"pqd_{raw}"
    prefix = raw[:8]
    key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()

    api_key = ApiKey(
        user_id=user.id,
        key_prefix=prefix,
        key_hash=key_hash,
        name=name,
    )
    session.add(api_key)
    await session.commit()

    return RedirectResponse(url=f"/settings?new_key={full_key}", status_code=303)


@router.post("/settings/keys/{key_id}/revoke")
async def revoke_api_key(
    key_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke an API key owned by the current user."""
    from piqued.models import ApiKey

    api_key = await session.get(ApiKey, key_id)
    if api_key and api_key.user_id == user.id:
        await session.delete(api_key)
        await session.commit()
    return RedirectResponse(url="/settings", status_code=303)


# ── Onboarding ────────────────────────────────────────────────


@router.get("/onboarding", response_class=HTMLResponse)
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
