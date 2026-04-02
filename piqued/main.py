"""Piqued — FastAPI app with scheduler, web UI, and feedback API."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from piqued import config
from piqued.db import engine
from piqued.models import Base

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create/update tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

# Middleware stack — add_middleware is LIFO: last added = outermost
# We want: [SessionMiddleware] -> [CSRFMiddleware] -> [route]
# So add CSRF first (innermost), then Session (outermost)

from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402


class CSRFMiddleware(BaseHTTPMiddleware):
    PUBLIC_PATHS = {
        "/health",
        "/login",
        "/login/oidc",
        "/auth/callback",
        "/logout",
        "/setup",
    }

    async def dispatch(self, request: Request, call_next):
        from fastapi.responses import JSONResponse

        path = request.url.path

        if path in self.PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)

        if not config.is_configured():
            return RedirectResponse(url="/setup", status_code=303)

        # Ensure CSRF token in session + request.state
        request.state.csrf = ""
        if "csrf" not in request.session:
            import secrets

            request.session["csrf"] = secrets.token_hex(16)
        request.state.csrf = request.session["csrf"]

        # CSRF protection on state-mutating requests
        if request.method in ("POST", "PUT", "DELETE"):
            session_csrf = request.session.get("csrf", "")
            xhr_token = request.headers.get("X-CSRF-Token", "")
            if xhr_token and xhr_token == session_csrf:
                pass
            else:
                content_type = request.headers.get("content-type", "")
                if "form" in content_type:
                    # Read body and cache it so route handlers can re-read
                    body = await request.body()
                    from urllib.parse import parse_qs

                    parsed = parse_qs(body.decode("utf-8"))
                    form_csrf = parsed.get("_csrf", [""])[0]
                    if form_csrf != session_csrf or not session_csrf:
                        return JSONResponse(
                            {"error": "CSRF check failed"}, status_code=403
                        )
                elif not xhr_token:
                    return JSONResponse({"error": "CSRF check failed"}, status_code=403)

        return await call_next(request)


# CSRF added first = innermost, Session added second = outermost
# Request flow: Session -> CSRF -> route
app.add_middleware(CSRFMiddleware)

# Session secret: try DB first, fall back to env var, then generate a random one.
# Note: at import time the DB may not be loaded yet, so this often gets the fallback.
# ensure_session_secret() in lifespan saves a permanent key to DB for next boot.
import os as _os  # noqa: E402

session_secret = (
    config.get("session_secret_key")
    or _os.environ.get("PIQUED_SESSION_SECRET")
    or _os.urandom(32).hex()
)
app.add_middleware(SessionMiddleware, secret_key=session_secret)


# Include routers
from piqued.auth.router import router as auth_router  # noqa: E402
from piqued.feedback.router import router as feedback_router  # noqa: E402
from piqued.web.router import router as web_router  # noqa: E402

app.include_router(auth_router)
app.include_router(feedback_router)
app.include_router(web_router)

# Mount static files
static_dir = Path(__file__).parent / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
async def health():
    """Health check — always public."""
    from sqlalchemy import text
    from piqued.db import async_session

    async with async_session() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "configured": config.is_configured()}
