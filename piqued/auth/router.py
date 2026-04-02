"""Auth routes: login, OIDC callback, logout."""

import logging
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piqued import config
from piqued.auth.deps import ensure_csrf, get_or_create_user
from piqued.db import get_session
from piqued.models import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])

templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent / "web" / "templates")
)

# OAuth client — configured lazily from DB settings
_oauth: OAuth | None = None
_oauth_settings: tuple | None = None


def _get_oauth() -> OAuth:
    """Get or create the OAuth client from current settings. Recreates if settings changed."""
    global _oauth, _oauth_settings
    client_id = config.get("oidc_client_id")
    client_secret = config.get("oidc_client_secret")
    metadata_url = config.get("oidc_server_metadata_url")

    if not client_id or not metadata_url:
        return None

    current_settings = (client_id, client_secret, metadata_url)
    if _oauth is not None and _oauth_settings == current_settings:
        return _oauth

    _oauth = OAuth()
    _oauth.register(
        name="authentik",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=metadata_url,
        client_kwargs={"scope": "openid email profile"},
    )
    _oauth_settings = current_settings
    return _oauth


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page showing enabled auth methods."""
    csrf = ensure_csrf(request)
    methods = config.get("auth_methods").split(",")
    oidc_configured = bool(config.get("oidc_client_id"))

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "methods": methods,
            "oidc_configured": oidc_configured,
            "csrf": csrf,
            "error": request.query_params.get("error"),
        },
    )


@router.get("/login/oidc")
async def login_oidc(request: Request):
    """Redirect to Authentik for OIDC login."""
    oauth = _get_oauth()
    if not oauth:
        return RedirectResponse(url="/login?error=OIDC+not+configured", status_code=303)

    redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.authentik.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def auth_callback(request: Request, session: AsyncSession = Depends(get_session)):
    """OIDC callback — exchange code for token, create/update user, set session."""
    oauth = _get_oauth()
    if not oauth:
        return RedirectResponse(url="/login?error=OIDC+not+configured", status_code=303)

    try:
        token = await oauth.authentik.authorize_access_token(request)
    except Exception as e:
        logger.error("OIDC token exchange failed: %s", e)
        return RedirectResponse(url="/login?error=OIDC+login+failed", status_code=303)

    userinfo = token.get("userinfo", {})
    username = userinfo.get("preferred_username", "")
    email = userinfo.get("email", "")
    groups = userinfo.get("groups", [])
    sub = userinfo.get("sub", "")

    if not username:
        return RedirectResponse(
            url="/login?error=No+username+in+OIDC+response", status_code=303
        )

    # Get or create user
    user = await get_or_create_user(session, username, email)

    # Update OIDC fields
    user.oidc_sub = sub
    user.oidc_provider = "authentik"
    user.email = email or user.email

    # OIDC group → role mapping
    admin_group = config.get("oidc_admin_group")
    if admin_group:
        in_admin_group = admin_group in groups
        if in_admin_group and user.role_source != "manual":
            user.role = "admin"
            user.role_source = "oidc"
        elif not in_admin_group and user.role_source == "oidc":
            # Demote: was granted admin via group, group removed
            user.role = "user"
            user.role_source = "oidc"

    await session.commit()

    # Set session
    request.session["user_id"] = user.id
    ensure_csrf(request)

    logger.info("OIDC login: %s (role=%s)", username, user.role)
    return RedirectResponse(url="/", status_code=303)


@router.post("/login")
async def login_local(request: Request, session: AsyncSession = Depends(get_session)):
    """Local username/password login."""
    if "local" not in config.get("auth_methods").split(","):
        return RedirectResponse(
            url="/login?error=Local+login+disabled", status_code=303
        )

    form = await request.form()

    # CSRF check
    csrf_token = form.get("_csrf", "")
    if csrf_token != request.session.get("csrf"):
        return RedirectResponse(url="/login?error=Invalid+request", status_code=303)

    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))

    if not username or not password:
        return RedirectResponse(
            url="/login?error=Username+and+password+required", status_code=303
        )

    user = await session.scalar(select(User).where(User.username == username))
    if not user or not user.password_hash:
        return RedirectResponse(url="/login?error=Invalid+credentials", status_code=303)

    if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        return RedirectResponse(url="/login?error=Invalid+credentials", status_code=303)

    user.last_login = datetime.now(timezone.utc)
    await session.commit()

    request.session["user_id"] = user.id
    ensure_csrf(request)

    logger.info("Local login: %s", username)
    return RedirectResponse(url="/", status_code=303)


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, session: AsyncSession = Depends(get_session)):
    """First-launch setup: create admin + configure app. Only available when no users exist."""
    from sqlalchemy import func

    user_count = await session.scalar(select(func.count()).select_from(User))
    if user_count:
        return RedirectResponse(url="/login", status_code=303)

    csrf = ensure_csrf(request)
    from piqued.llm.factory import PROVIDERS

    return templates.TemplateResponse(
        request,
        "setup.html",
        {"csrf": csrf, "providers": sorted(PROVIDERS)},
    )


@router.post("/setup")
async def setup_submit(request: Request, session: AsyncSession = Depends(get_session)):
    """Process first-launch setup: create admin user + save app config."""
    from sqlalchemy import func

    user_count = await session.scalar(select(func.count()).select_from(User))
    if user_count:
        return RedirectResponse(url="/login", status_code=303)

    form = await request.form()

    # Create admin user
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    if not username or not password:
        csrf = ensure_csrf(request)
        from piqued.llm.factory import PROVIDERS

        return templates.TemplateResponse(
            request,
            "setup.html",
            {
                "csrf": csrf,
                "providers": sorted(PROVIDERS),
                "error": "Username and password are required",
            },
        )

    admin = User(
        username=username,
        password_hash=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        ),
        role="admin",
        role_source="auto",
        last_login=datetime.now(timezone.utc),
    )
    session.add(admin)
    await session.commit()

    # Save app settings
    settings_to_save = {}
    for key in (
        "llm_provider",
        "llm_model",
        "llm_api_key",
        "llm_base_url",
        "freshrss_base_url",
        "freshrss_username",
        "freshrss_api_pass",
    ):
        val = str(form.get(key, "")).strip()
        if val:
            settings_to_save[key] = val

    if settings_to_save:
        from piqued import config as cfg

        await cfg.save_settings(settings_to_save)
        await cfg.load_settings_from_db()

    # Auto-login as the new admin
    request.session["user_id"] = admin.id
    ensure_csrf(request)

    logger.info("Setup complete: admin user '%s' created", username)

    # Start scheduler if now configured
    from piqued import config as cfg

    if cfg.is_configured():
        from piqued.main import _start_scheduler

        _start_scheduler()

    return RedirectResponse(url="/onboarding", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """Clear session and redirect to login."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
