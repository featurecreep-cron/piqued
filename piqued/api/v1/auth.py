"""API authentication — Bearer token deps that return JSON errors."""

import hashlib
import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piqued.db import get_session
from piqued.models import ApiKey, User

logger = logging.getLogger(__name__)

KEY_PREFIX = "pqd_"


async def _resolve_bearer_token(token: str, session: AsyncSession) -> User | None:
    """Look up a Bearer token and return its owner, or None."""
    if not token.startswith(KEY_PREFIX):
        return None

    raw = token[len(KEY_PREFIX) :]
    if len(raw) < 8:
        return None

    prefix = raw[:8]
    key_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    result = await session.execute(
        select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        return None

    api_key.last_used_at = datetime.now(timezone.utc)
    user = await session.get(User, api_key.user_id)
    return user


async def get_api_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    """Authenticate via Bearer token or session cookie. Returns JSON 401 on failure."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = await _resolve_bearer_token(token, session)
        if user:
            return user
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Fall through to session cookie (for browser-based API calls)
    try:
        user_id = request.session.get("user_id")
    except (AssertionError, AttributeError):
        user_id = None

    if user_id:
        user = await session.get(User, user_id)
        if user:
            return user

    raise HTTPException(status_code=401, detail="Not authenticated")


async def require_api_admin(user: User = Depends(get_api_user)) -> User:
    """Require admin role. Returns JSON 403 on failure."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
