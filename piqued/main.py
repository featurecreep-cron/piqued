"""Piqued — FastAPI app with scheduler, web UI, and feedback API."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path


class _HealthCheckFilter(logging.Filter):
    """Suppress uvicorn access log entries for the /health endpoint."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /health") == -1


logging.getLogger("uvicorn.access").addFilter(_HealthCheckFilter())

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from piqued import config
from piqued.db import engine
from piqued.migrations import run_migrations
from piqued.models import Base

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create/update tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Apply column additions for tables that already existed
        await run_migrations(conn)

    # Load settings from DB into cache
    await config.load_settings_from_db()

    # Auto-generate session secret if missing
    await config.ensure_session_secret()

    # Seed feeds from YAML if DB is empty (backward compat)
    await _seed_feeds()

    # Only start scheduler if configured
    if config.is_configured():
        _start_scheduler()
    else:
        logger.warning("Piqued not configured — visit /settings to set up")

    yield

    scheduler.shutdown(wait=False)
    await engine.dispose()


def _start_scheduler():
    """Start the polling scheduler. Safe to call multiple times."""
    from piqued.feedback.learner import apply_interest_decay
    from piqued.processing.pipeline import run_pipeline

    if scheduler.running:
        return

    interval = config.get_int("feed_poll_interval_minutes")
    scheduler.add_job(
        run_pipeline,
        "interval",
        minutes=interval,
        id="feed_poll",
        replace_existing=True,
    )
    # Nightly interest decay at 3:00 AM
    scheduler.add_job(
        apply_interest_decay,
        "cron",
        hour=3,
        minute=0,
        id="interest_decay",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: polling every %d minutes, nightly decay at 03:00", interval
    )


async def _seed_feeds():
    """Load feeds from YAML into DB if feeds table is empty."""
    import yaml
    from sqlalchemy import select
    from piqued.db import async_session
    from piqued.models import Feed

    async with async_session() as session:
        result = await session.execute(select(Feed).limit(1))
        if result.scalar_one_or_none() is not None:
            return

        feed_path = Path(__file__).parent / "config" / "feeds.yaml"
        if not feed_path.exists():
            return

        with open(feed_path) as f:
            data = yaml.safe_load(f)

        for feed_cfg in data.get("feeds", []):
            if not feed_cfg.get("freshrss_feed_id"):
                continue
            session.add(
                Feed(
                    freshrss_feed_id=feed_cfg["freshrss_feed_id"],
                    title=feed_cfg.get("title", ""),
                    url=feed_cfg.get("url", ""),
                    active=True,
                )
            )
        await session.commit()


app = FastAPI(title="Piqued", version="0.4.0", lifespan=lifespan)

# Session middleware — SameSite=Lax (Starlette default) provides CSRF protection
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402
import os as _os  # noqa: E402

session_secret = (
    config.get("session_secret_key")
    or _os.environ.get("PIQUED_SESSION_SECRET")
    or _os.urandom(32).hex()
)
app.add_middleware(SessionMiddleware, secret_key=session_secret)


# Include routers
from piqued.api.v1.feed_xml import router as api_v1_feed_router  # noqa: E402
from piqued.api.v1.router import router as api_v1_router  # noqa: E402
from piqued.auth.router import router as auth_router  # noqa: E402
from piqued.feedback.router import router as feedback_router  # noqa: E402
from piqued.web.router import onboarding_router  # noqa: E402

app.include_router(api_v1_router)
app.include_router(api_v1_feed_router)
app.include_router(auth_router)
app.include_router(feedback_router)
app.include_router(onboarding_router)

# Mount static files
static_dir = Path(__file__).parent / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount SPA built assets (from Vue frontend build)
spa_dir = Path(__file__).parent / "web" / "spa"
if spa_dir.exists() and (spa_dir / "assets").exists():
    app.mount(
        "/assets", StaticFiles(directory=str(spa_dir / "assets")), name="spa-assets"
    )


@app.get("/health")
async def health():
    """Health check — always public."""
    from sqlalchemy import text
    from piqued.db import async_session

    async with async_session() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "configured": config.is_configured()}


# SPA catch-all — must be registered last so all explicit routes take priority
_SPA_EXCLUDED = (
    "/api/",
    "/login",
    "/logout",
    "/setup",
    "/onboarding",
    "/auth/",
    "/health",
    "/static",
    "/assets",
)

if spa_dir.exists() and (spa_dir / "index.html").exists():
    from fastapi.responses import HTMLResponse  # noqa: E402

    @app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def spa_catch_all(path: str):
        """Serve Vue SPA index.html for client-side routing."""
        full = f"/{path}"
        if any(full.startswith(p) for p in _SPA_EXCLUDED):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        index = spa_dir / "index.html"
        return HTMLResponse(index.read_text())
