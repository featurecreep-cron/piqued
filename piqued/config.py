"""Two-tier configuration: bootstrap from env, runtime from DB.

Bootstrap (env only): PIQUED_DATABASE_PATH — needed to find the DB.
Runtime (DB settings table, env fallback): everything else.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Bootstrap (env only) ──────────────────────────────────────────
DATABASE_PATH = os.environ.get("PIQUED_DATABASE_PATH", "/data/piqued.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# ── Runtime settings defaults ─────────────────────────────────────
# These are the defaults used when no DB setting exists AND no env var is set.
DEFAULTS = {
    # Auth
    "auth_methods": "oidc,local,header",  # comma-separated enabled methods
    "session_secret_key": "",  # auto-generated on first boot
    "trusted_proxy_ip": "",  # IP allowed to send X-authentik-username headers
    # OIDC (Authentik)
    "oidc_client_id": "",
    "oidc_client_secret": "",
    "oidc_server_metadata_url": "",  # e.g. https://auth.savor.li/application/o/piqued/.well-known/openid-configuration
    "oidc_admin_group": "piqued-admin",  # Authentik group that grants admin role
    # LLM - primary (used for both classification and segmentation unless advanced override)
    "llm_provider": "gemini",
    "llm_model": "gemini-2.5-flash",
    "llm_api_key": "",
    "llm_base_url": "",  # only needed for ollama
    # LLM - classification override (advanced, optional)
    "llm_classify_provider": "",  # empty = use primary
    "llm_classify_model": "",
    "llm_classify_api_key": "",
    "llm_classify_base_url": "",
    # FreshRSS
    "freshrss_base_url": "https://freshrss.savor.li",
    "freshrss_username": "your_username",
    "freshrss_api_pass": "",
    # Processing
    "feed_poll_interval_minutes": "15",
    "max_concurrent_articles": "3",
    "max_article_words": "15000",
    "daily_token_budget": "500000",
    "max_retries": "3",
    "backlog_order": "newest_first",
    "max_articles_per_cycle": "3",
    # Interest model
    "confidence_threshold": "0.4",
    "surprise_surface_pct": "0.10",
    "scoring_mode": "hybrid",  # formula / llm / hybrid
    "profile_synthesis_threshold": "3",  # feedback count before synthesis
    "profile_max_words": "500",
    "scoring_batch_size": "50",
    # Interest decay
    "interest_decay_rate": "0.05",  # weight reduction per decay cycle
    "interest_decay_after_days": "14",  # days without reinforcement before decay
    # LLM - scoring override (optional, use cheap/fast model)
    "llm_scoring_provider": "",  # empty = use classify override or primary
    "llm_scoring_model": "",
    "llm_scoring_api_key": "",
    "llm_scoring_base_url": "",
    # RSS feed output
    "rss_feed_api_key": "",
}

# Cache for DB settings (refreshed per-request or on explicit reload)
_cache: dict[str, str] = {}
_cache_loaded = False


async def ensure_session_secret():
    """Generate and persist a session secret key if one doesn't exist."""
    import secrets

    current = get("session_secret_key")
    if not current:
        key = secrets.token_hex(32)
        await save_setting("session_secret_key", key)
        _cache["session_secret_key"] = key
        logger.info("Generated new session secret key")


async def load_settings_from_db():
    """Load all settings from the DB into the in-memory cache."""
    global _cache, _cache_loaded
    try:
        from sqlalchemy import select

        from piqued.db import async_session
        from piqued.models import Setting

        async with async_session() as session:
            result = await session.execute(select(Setting))
            _cache = {s.key: s.value for s in result.scalars().all()}
            _cache_loaded = True
    except Exception as e:
        logger.warning("Could not load settings from DB: %s", e)
        _cache_loaded = False


async def save_setting(key: str, value: str):
    """Save a single setting to the DB and update cache."""
    from sqlalchemy.dialects.sqlite import insert

    from piqued.db import async_session
    from piqued.models import Setting

    async with async_session() as session:
        stmt = insert(Setting).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value})
        await session.execute(stmt)
        await session.commit()

    _cache[key] = value


async def save_settings(settings_dict: dict[str, str]):
    """Save multiple settings to the DB and update cache in a single session."""
    from sqlalchemy.dialects.sqlite import insert

    from piqued.db import async_session
    from piqued.models import Setting

    async with async_session() as session:
        for key, value in settings_dict.items():
            stmt = insert(Setting).values(key=key, value=value)
            stmt = stmt.on_conflict_do_update(
                index_elements=["key"], set_={"value": value}
            )
            await session.execute(stmt)
        await session.commit()

    _cache.update(settings_dict)


def get(key: str) -> str:
    """Get a runtime setting. Priority: DB cache → env var → default.

    Note: This is synchronous. Call load_settings_from_db() at startup
    and after settings page saves to keep the cache fresh.
    """
    # 1. DB cache (if loaded)
    if _cache_loaded and key in _cache:
        return _cache[key]

    # 2. Environment variable (PIQUED_ prefix, uppercase)
    env_key = f"PIQUED_{key.upper()}"
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val

    # 3. Legacy secret file support (for backward compat during migration)
    file_env_key = f"PIQUED_{key.upper()}_FILE"
    file_path = os.environ.get(file_env_key)
    if file_path and Path(file_path).is_file():
        return Path(file_path).read_text().strip()

    # 4. Default
    return DEFAULTS.get(key, "")


def get_int(key: str) -> int:
    """Get a setting as int."""
    try:
        return int(get(key))
    except (ValueError, TypeError):
        return int(DEFAULTS.get(key, "0"))


def get_float(key: str) -> float:
    """Get a setting as float."""
    try:
        return float(get(key))
    except (ValueError, TypeError):
        return float(DEFAULTS.get(key, "0"))


def is_configured() -> bool:
    """Check if minimum required settings are present (API key + FreshRSS pass)."""
    return bool(get("llm_api_key")) and bool(get("freshrss_api_pass"))


def get_llm_config(task: str = "primary") -> dict:
    """Get LLM config for a specific task.

    Args:
        task: 'primary' (segmentation) or 'classify' (content classification).
              Classify falls back to primary if not separately configured.

    Returns:
        Dict with provider, model, api_key, base_url.
    """
    if task == "scoring":
        provider = get("llm_scoring_provider")
        if provider:
            return {
                "provider": provider,
                "model": get("llm_scoring_model"),
                "api_key": get("llm_scoring_api_key"),
                "base_url": get("llm_scoring_base_url"),
            }
        # Fall through to classify override, then primary

    if task in ("classify", "scoring"):
        provider = get("llm_classify_provider")
        if provider:
            return {
                "provider": provider,
                "model": get("llm_classify_model"),
                "api_key": get("llm_classify_api_key"),
                "base_url": get("llm_classify_base_url"),
            }

    # Primary (fallback for all tasks)
    return {
        "provider": get("llm_provider"),
        "model": get("llm_model"),
        "api_key": get("llm_api_key"),
        "base_url": get("llm_base_url"),
    }
