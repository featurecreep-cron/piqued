"""v1 JSON API routes."""

import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piqued import config
from piqued.api.v1.auth import get_api_user, require_api_admin
from piqued.api.v1.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyItem,
    ApiKeyList,
    ArticleDetail,
    ArticleSection,
    ArticleSummary,
    ChangeRoleRequest,
    ClickThroughRequest,
    ConnectionTestResult,
    CreateUserRequest,
    DownweightRequest,
    FeedbackRequest,
    FeedbackResult,
    FeedDetail,
    FeedItem,
    FeedList,
    ProcessingLogEntry,
    ProcessingLogList,
    ProfileEditRequest,
    SectionItem,
    SectionList,
    SettingsResponse,
    SyncResult,
    UserInfo,
    UserList,
    UserPreferences,
    UserPreferencesUpdate,
    UserProfileResponse,
    WeightItem,
)
from piqued.db import get_session
from piqued.models import (
    ApiKey,
    Article,
    Feed,
    Feedback,
    FeedbackSource,
    Section,
    User,
    UserProfile,
)
from piqued.web.data import (
    get_article_detail,
    get_feed_detail,
    get_feeds_list,
    get_home_sections,
    get_processing_log,
    get_settings_data,
    get_user_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])

KEY_PREFIX = "pqd_"


# ── Public ──────────────────────────────────────────────────────


@router.get("/health")
async def health():
    return {"status": "ok"}


# ── Sections (triage view) ──────────────────────────────────────


@router.get("/sections", response_model=SectionList)
async def list_sections(
    date: str | None = None,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    data = await get_home_sections(user, date, session)
    sections = []
    for section, article, confidence, reasoning in data["all_sections"]:
        sections.append(
            SectionItem(
                id=section.id,
                article_id=article.id,
                article_title=article.title,
                feed_title=article.feed.title if article.feed else "",
                heading=section.heading,
                summary=section.summary,
                topic_tags=section.tags_list,
                score=confidence,
                reasoning=reasoning,
                is_surprise=section.id in data["surprise_ids"],
                has_humor=section.has_humor,
                has_surprise_data=section.has_surprise_data,
                has_actionable_advice=section.has_actionable_advice,
                article_url=article.url,
                published_at=article.published_at,
            )
        )
    return SectionList(
        sections=sections,
        date=data["date"],
        dates_available=data["available_dates"],
        threshold=data["threshold"],
        surprise_section_ids=list(data["surprise_ids"]),
    )


# ── Feeds ───────────────────────────────────────────────────────


@router.get("/feeds", response_model=FeedList)
async def list_feeds(
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    # Per-feed article counts via aggregated queries (avoid async lazy-loads).
    #
    # Three numbers per feed:
    #
    # - article_count: total articles ever ingested for this feed
    # - unread_count: articles with NO feedback rows from this user on any of
    #   their sections (never click-throughed, never voted)
    # - untriaged_count: articles with no `explicit` feedback rows from this
    #   user on any section (may have click-throughed but never thumbs up/down)
    #
    # Both unread/untriaged restrict to processed articles (status=complete) so
    # that pending/skipped articles don't inflate the "you haven't read this"
    # count for things you can't actually read.
    from piqued.models import ArticleStatus
    from sqlalchemy import and_, distinct, func

    # Total article count per feed
    total_result = await session.execute(
        select(Article.feed_id, func.count(Article.id)).group_by(Article.feed_id)
    )
    total_counts = dict(total_result.all())

    # Articles with at least one feedback row of any kind from this user
    seen_subq = (
        select(distinct(Article.id))
        .select_from(Article)
        .join(Section, Section.article_id == Article.id)
        .join(
            Feedback,
            and_(
                Feedback.section_id == Section.id,
                Feedback.user_id == user.id,
            ),
        )
        .subquery()
    )

    unread_result = await session.execute(
        select(Article.feed_id, func.count(Article.id))
        .where(
            Article.status == ArticleStatus.complete,
            ~Article.id.in_(select(seen_subq)),
        )
        .group_by(Article.feed_id)
    )
    unread_counts = dict(unread_result.all())

    # Articles with at least one *explicit* feedback row from this user
    triaged_subq = (
        select(distinct(Article.id))
        .select_from(Article)
        .join(Section, Section.article_id == Article.id)
        .join(
            Feedback,
            and_(
                Feedback.section_id == Section.id,
                Feedback.user_id == user.id,
                Feedback.source == FeedbackSource.explicit,
            ),
        )
        .subquery()
    )

    untriaged_result = await session.execute(
        select(Article.feed_id, func.count(Article.id))
        .where(
            Article.status == ArticleStatus.complete,
            ~Article.id.in_(select(triaged_subq)),
        )
        .group_by(Article.feed_id)
    )
    untriaged_counts = dict(untriaged_result.all())

    data = await get_feeds_list(session)
    feeds = []
    categories: dict[str, list[int]] = {}
    for cat, cat_feeds in data["categories"].items():
        categories[cat] = []
        for feed in cat_feeds:
            feeds.append(
                FeedItem(
                    id=feed.id,
                    title=feed.title,
                    url=feed.url,
                    category=feed.category,
                    active=feed.active,
                    content_quality=feed.content_quality,
                    article_count=total_counts.get(feed.id, 0),
                    unread_count=unread_counts.get(feed.id, 0),
                    untriaged_count=untriaged_counts.get(feed.id, 0),
                )
            )
            categories[cat].append(feed.id)
    return FeedList(feeds=feeds, categories=categories)


@router.get("/feeds/{feed_id}", response_model=FeedDetail)
async def feed_detail(
    feed_id: int,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    data = await get_feed_detail(feed_id, session)
    if not data:
        raise HTTPException(status_code=404, detail="Feed not found")
    feed = data["feed"]
    articles = [
        ArticleSummary(
            id=a.id,
            title=a.title,
            url=a.url,
            published_at=a.published_at,
            status=a.status.value if hasattr(a.status, "value") else str(a.status),
            section_count=len(a.sections),
        )
        for a in data["articles"]
    ]
    return FeedDetail(
        feed=FeedItem(
            id=feed.id,
            title=feed.title,
            url=feed.url,
            category=feed.category,
            active=feed.active,
            content_quality=feed.content_quality,
            article_count=len(articles),
        ),
        articles=articles,
    )


# ── Articles ────────────────────────────────────────────────────


@router.get("/articles/{article_id}", response_model=ArticleDetail)
async def article_detail_view(
    article_id: int,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    data = await get_article_detail(article_id, user, session)
    if not data:
        raise HTTPException(status_code=404, detail="Article not found")
    article = data["article"]
    sections = [
        ArticleSection(
            id=s.id,
            heading=s.heading,
            summary=s.summary,
            topic_tags=s.tags_list,
            score=conf,
            reasoning=reasoning,
            is_surprise=s.id in data["surprise_ids"],
            has_humor=s.has_humor,
            has_surprise_data=s.has_surprise_data,
            has_actionable_advice=s.has_actionable_advice,
        )
        for s, conf, reasoning in data["scored_sections"]
    ]
    return ArticleDetail(
        id=article.id,
        title=article.title,
        url=article.url,
        feed_title=article.feed.title if article.feed else "",
        published_at=article.published_at,
        status=article.status.value
        if hasattr(article.status, "value")
        else str(article.status),
        sections=sections,
    )


@router.post("/articles/{article_id}/process")
async def process_article(
    article_id: int,
    user: User = Depends(get_api_user),
):
    from piqued.processing.pipeline import process_single_article

    result = await process_single_article(article_id)
    return {"ok": result == "processed", "result": result}


# ── Profile ─────────────────────────────────────────────────────


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    data = await get_user_profile(user, session)
    profile = data["profile"]
    weights = [
        WeightItem(
            topic=w.topic,
            weight=w.weight,
            feedback_count=w.feedback_count,
            updated_at=w.updated_at,
        )
        for w in data["weights"]
    ]
    if profile:
        return UserProfileResponse(
            profile_text=profile.profile_text,
            profile_version=profile.profile_version,
            pending_feedback_count=profile.pending_feedback_count,
            last_synthesized_at=profile.last_synthesized_at,
            weights=weights,
        )
    return UserProfileResponse(
        profile_text="",
        profile_version=0,
        pending_feedback_count=0,
        last_synthesized_at=None,
        weights=weights,
    )


@router.put("/profile", response_model=UserProfileResponse)
async def edit_profile(
    body: ProfileEditRequest,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await session.get(UserProfile, user.id)
    if profile:
        profile.profile_text = body.profile_text
        profile.profile_version += 1
        profile.updated_at = datetime.now(timezone.utc)
    else:
        profile = UserProfile(
            user_id=user.id,
            profile_text=body.profile_text,
            profile_version=1,
        )
        session.add(profile)
    await session.commit()
    return await get_profile(user=user, session=session)


@router.post("/profile/synthesize")
async def synthesize_profile(
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await session.get(UserProfile, user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="No profile to synthesize")

    import asyncio

    from piqued.feedback.router import _trigger_synthesis

    asyncio.create_task(_trigger_synthesis(user.id))
    return {"ok": True, "message": "Synthesis started"}


# ── Feedback ────────────────────────────────────────────────────


@router.post("/feedback", response_model=FeedbackResult)
async def api_feedback(
    body: FeedbackRequest,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    from piqued.feedback.router import FeedbackRequest as InternalFBRequest
    from piqued.feedback.router import submit_feedback

    result = await submit_feedback(
        InternalFBRequest(
            section_id=body.section_id,
            rating=body.rating,
            reason=body.reason,
        ),
        user=user,
        session=session,
    )
    return FeedbackResult(ok=result.ok, direction=result.direction)


@router.post("/click-through")
async def api_click_through(
    body: ClickThroughRequest,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    from piqued.feedback.router import FeedbackRequest as InternalFBRequest
    from piqued.feedback.router import submit_feedback

    result = await submit_feedback(
        InternalFBRequest(section_id=body.section_id, rating=1, source="click_through"),
        user=user,
        session=session,
    )
    return {"ok": result.ok}


@router.post("/downweight")
async def api_downweight(
    body: DownweightRequest,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    from piqued.feedback.router import DownweightRequest as InternalDWRequest
    from piqued.feedback.router import downweight_tag

    result = await downweight_tag(
        InternalDWRequest(tag=body.tag), user=user, session=session
    )
    return result


# ── Settings ────────────────────────────────────────────────────


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    data = await get_settings_data(user, session)
    return SettingsResponse(
        settings=data["current"],
        is_admin=data["is_admin"],
    )


@router.put("/settings", response_model=SettingsResponse)
async def save_settings_api(
    settings: dict[str, str],
    admin: User = Depends(require_api_admin),
    session: AsyncSession = Depends(get_session),
):
    settings_to_save = {}
    for key in config.DEFAULTS:
        if key in settings:
            val = str(settings[key]).strip()
            if "api_key" in key or "api_pass" in key:
                if val == "••••••••" or not val:
                    continue
            settings_to_save[key] = val

    if settings_to_save:
        # Reuse the dep-injected session — opening a second connection while
        # this one is alive would deadlock SQLite on the write.
        await config.save_settings(settings_to_save, session=session)

    data = await get_settings_data(admin, session)
    return SettingsResponse(settings=data["current"], is_admin=data["is_admin"])


@router.post("/settings/test-llm", response_model=ConnectionTestResult)
async def test_llm_connection(
    body: dict[str, str],
    admin: User = Depends(require_api_admin),
):
    """Test an LLM provider connection with a tiny prompt.

    Body may include provider, model, api_key, base_url. Empty/missing
    fields fall back to current saved primary LLM config.
    """
    from piqued.llm import create_client

    primary = config.get_llm_config("primary")
    provider = (body.get("provider") or primary["provider"]).strip()
    model = (body.get("model") or primary["model"]).strip()
    api_key = body.get("api_key") or primary["api_key"]
    base_url = (body.get("base_url") or primary["base_url"]).strip()

    if not provider or not model:
        return ConnectionTestResult(ok=False, detail="Provider and model required")
    if provider != "ollama" and not api_key:
        return ConnectionTestResult(
            ok=False, detail="API key required for this provider"
        )

    try:
        client = create_client(
            provider=provider, model=model, api_key=api_key, base_url=base_url
        )
        resp = await client.generate(
            "Reply with the single word: ok",
            temperature=0.0,
            max_tokens=8,
        )
        text = (resp.text or "").strip()
        return ConnectionTestResult(
            ok=True,
            detail=f"{provider}/{model} responded: {text[:60] or '(empty)'}",
        )
    except Exception as e:
        return ConnectionTestResult(
            ok=False, detail=f"{type(e).__name__}: {str(e)[:200]}"
        )


@router.post("/settings/test-freshrss", response_model=ConnectionTestResult)
async def test_freshrss_connection(
    body: dict[str, str],
    admin: User = Depends(require_api_admin),
):
    """Test FreshRSS API auth + subscription fetch."""
    from piqued.ingestion.freshrss import FreshRSSClient

    base_url = (
        body.get("freshrss_base_url") or config.get("freshrss_base_url")
    ).strip()
    username = (
        body.get("freshrss_username") or config.get("freshrss_username")
    ).strip()
    api_pass = body.get("freshrss_api_pass") or config.get("freshrss_api_pass")

    if not base_url or not username or not api_pass:
        return ConnectionTestResult(
            ok=False, detail="URL, username, and API password required"
        )

    client = FreshRSSClient(base_url=base_url, username=username, api_pass=api_pass)
    try:
        await client._authenticate()
        subs = await client.get_subscriptions()
        return ConnectionTestResult(
            ok=True, detail=f"Authenticated. {len(subs)} subscriptions visible."
        )
    except Exception as e:
        return ConnectionTestResult(
            ok=False, detail=f"{type(e).__name__}: {str(e)[:200]}"
        )
    finally:
        await client.close()


# ── Processing log ──────────────────────────────────────────────


@router.get("/log", response_model=ProcessingLogList)
async def get_log(
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    data = await get_processing_log(session, limit=limit, offset=offset)
    entries = [
        ProcessingLogEntry(
            id=e["log"].id,
            article_id=e["log"].article_id,
            article_title=e["article_title"],
            stage=e["log"].stage,
            status=e["log"].status,
            detail=e["log"].detail,
            tokens_used=e["log"].tokens_used,
            duration_ms=e["log"].duration_ms,
            created_at=e["log"].created_at,
        )
        for e in data["entries"]
    ]
    return ProcessingLogList(
        entries=entries,
        limit=data["limit"],
        offset=data["offset"],
        total=data["total"],
    )


# ── User info ───────────────────────────────────────────────────


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_api_user)):
    return UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
    )


# ── Preferences ────────────────────────────────────────────────


VALID_THEMES = {"light", "dark"}
VALID_LAYOUTS = {"river", "reader", "columns"}


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(user: User = Depends(get_api_user)):
    raw = json.loads(user.preferences or "{}")
    return UserPreferences(
        **{k: v for k, v in raw.items() if k in UserPreferences.model_fields}
    )


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(
    body: UserPreferencesUpdate,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    current = json.loads(user.preferences or "{}")
    updates = body.model_dump(exclude_none=True)

    if "theme" in updates and updates["theme"] not in VALID_THEMES:
        raise HTTPException(
            status_code=422, detail=f"theme must be one of {VALID_THEMES}"
        )
    if "layout_mode" in updates and updates["layout_mode"] not in VALID_LAYOUTS:
        raise HTTPException(
            status_code=422, detail=f"layout_mode must be one of {VALID_LAYOUTS}"
        )
    if "items_per_page" in updates:
        if not (10 <= updates["items_per_page"] <= 200):
            raise HTTPException(
                status_code=422, detail="items_per_page must be between 10 and 200"
            )

    current.update(updates)
    user.preferences = json.dumps(current)
    await session.commit()

    return UserPreferences(
        **{k: v for k, v in current.items() if k in UserPreferences.model_fields}
    )


# ── Admin: feeds ────────────────────────────────────────────────


@router.post("/feeds/sync", response_model=SyncResult)
async def sync_feeds_api(
    admin: User = Depends(require_api_admin),
    session: AsyncSession = Depends(get_session),
):
    from piqued.ingestion.freshrss import FreshRSSClient

    client = FreshRSSClient()
    try:
        subs = await client.get_subscriptions()
        added = 0
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
                added += 1
        await session.commit()
        return SyncResult(ok=True, total=len(subs), added=added)
    finally:
        await client.close()


@router.post("/feeds/{feed_id}/toggle")
async def toggle_feed_api(
    feed_id: int,
    admin: User = Depends(require_api_admin),
    session: AsyncSession = Depends(get_session),
):
    feed = await session.get(Feed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    feed.active = not feed.active
    await session.commit()
    return FeedItem(
        id=feed.id,
        title=feed.title,
        url=feed.url,
        category=feed.category,
        active=feed.active,
        content_quality=feed.content_quality,
        article_count=0,
    )


# ── Admin: users ────────────────────────────────────────────────


@router.get("/users", response_model=UserList)
async def list_users(
    admin: User = Depends(require_api_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).order_by(User.created_at))
    users = [
        UserInfo(id=u.id, username=u.username, email=u.email, role=u.role)
        for u in result.scalars()
    ]
    return UserList(users=users)


@router.post("/users", response_model=UserInfo)
async def create_user_api(
    body: CreateUserRequest,
    admin: User = Depends(require_api_admin),
    session: AsyncSession = Depends(get_session),
):
    import bcrypt

    role = body.role if body.role in ("admin", "user") else "user"
    existing = await session.scalar(select(User).where(User.username == body.username))
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    new_user = User(
        username=body.username,
        password_hash=bcrypt.hashpw(
            body.password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8"),
        role=role,
        role_source="manual",
    )
    session.add(new_user)
    await session.commit()
    return UserInfo(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        role=new_user.role,
    )


@router.put("/users/{user_id}/role", response_model=UserInfo)
async def change_role_api(
    user_id: int,
    body: ChangeRoleRequest,
    admin: User = Depends(require_api_admin),
    session: AsyncSession = Depends(get_session),
):
    role = body.role if body.role in ("admin", "user") else "user"
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and role != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    target.role = role
    target.role_source = "manual"
    await session.commit()
    return UserInfo(
        id=target.id,
        username=target.username,
        email=target.email,
        role=target.role,
    )


# ── API keys ────────────────────────────────────────────────────


@router.post("/keys", response_model=ApiKeyCreated)
async def create_api_key(
    body: ApiKeyCreate,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    raw = secrets.token_hex(16)
    full_key = f"{KEY_PREFIX}{raw}"
    prefix = raw[:8]
    key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()

    api_key = ApiKey(
        user_id=user.id,
        key_prefix=prefix,
        key_hash=key_hash,
        name=body.name,
    )
    session.add(api_key)
    await session.commit()
    return ApiKeyCreated(id=api_key.id, name=api_key.name, key=full_key)


@router.get("/keys", response_model=ApiKeyList)
async def list_api_keys(
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = [
        ApiKeyItem(
            id=k.id,
            name=k.name,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in result.scalars()
    ]
    return ApiKeyList(keys=keys)


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    user: User = Depends(get_api_user),
    session: AsyncSession = Depends(get_session),
):
    api_key = await session.get(ApiKey, key_id)
    if not api_key or api_key.user_id != user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    await session.delete(api_key)
    await session.commit()
    return {"ok": True}
