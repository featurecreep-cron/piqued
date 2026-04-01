"""Auth dependencies for FastAPI route injection."""

import logging
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piqued import config
from piqued.db import get_session
from piqued.models import User

logger = logging.getLogger(__name__)


async def get_or_create_user(
    session: AsyncSession, username: str, email: str | None = None
) -> User:
    """Get existing user or create a new one. First user auto-becomes admin."""
    user = await session.scalar(select(User).where(User.username == username))
    if user:
        user.last_login = datetime.now(timezone.utc)
        await session.commit()
        return user

    # Check if this is the first user (auto-admin)
    from sqlalchemy import func
    count = await session.scalar(select(func.count()).select_from(User))
    role = "admin" if count == 0 else "user"
    role_source = "auto" if count == 0 else "auto"

    user = User(
        username=username,
        email=email,
        role=role,
        role_source=role_source,
        last_login=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.commit()
    logger.info("Created %s user '%s'", role, username)
    return user


def _is_trusted_proxy(request: Request) -> bool:
    """Only trust X-authentik-username from configured proxy IP."""
    trusted_ip = config.get("trusted_proxy_ip")
    if not trusted_ip:
        return False
    client_ip = request.client.host if request.client else ""
    return client_ip == trusted_ip


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    """Extract current user from session, forward-auth header, or raise 401.

    Priority:
    1. Forward-auth header (if from trusted proxy)
    2. Session cookie (from OIDC or local login)
    3. Redirect to login
    """
    # 1. Forward-auth header (trusted proxy only)
    if _is_trusted_proxy(request) and "header" in config.get("auth_methods"):
        username = request.headers.get("X-authentik-username")
        if username:
            return await get_or_create_user(session, username)

    # 2. Session (OIDC or local login)
    try:
        user_id = request.session.get("user_id")
    except AssertionError:
        user_id = None
    if user_id:
        user = await session.get(User, user_id)
        if user:
            return user
        # Stale session — clear it
        try:
            request.session.clear()
        except AssertionError:
            pass

    # 3. No auth
    raise HTTPException(status_code=303, headers={"Location": "/login"})


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an admin."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def ensure_csrf(request: Request) -> str:
    """Ensure session has a CSRF token, return it."""
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_hex(16)
    return request.session["csrf"]
