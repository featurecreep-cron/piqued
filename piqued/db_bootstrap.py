"""Database schema bootstrap.

Handles three startup scenarios:

1. Fresh DB (no tables) — create_all from models, stamp head
2. Legacy DB (has app tables but no alembic_version) — stamp baseline, upgrade head
3. Migrated DB (has alembic_version) — upgrade head

This lets us adopt Alembic without breaking existing deployments.
"""

import asyncio
import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from piqued.models import Base

logger = logging.getLogger(__name__)

# Revision representing the schema before Alembic was introduced.
# Existing deployments will be stamped at this revision before upgrade.
BASELINE_REVISION = "9eb79e2a68ea"


def _alembic_config(sync_url: str) -> Config:
    """Build an Alembic Config pointing at our migration scripts."""
    cfg = Config()
    script_location = Path(__file__).parent / "alembic"
    cfg.set_main_option("script_location", str(script_location))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


def _sync_url() -> str:
    """Compute the sync sqlite URL from the current PIQUED_DATABASE_PATH env var.

    Read at call time (not import time) so test fixtures that set the env
    var per-test see the right value.
    """
    db_path = os.environ.get("PIQUED_DATABASE_PATH", "/data/piqued.db")
    return f"sqlite:///{db_path}"


def _classify_db(sync_url: str) -> str:
    """Inspect the database and return one of: 'fresh', 'legacy', 'migrated'."""
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
    finally:
        engine.dispose()
    if "alembic_version" in tables:
        return "migrated"
    if "users" in tables:
        return "legacy"
    return "fresh"


def _bootstrap_sync() -> None:
    """Run schema bootstrap synchronously."""
    sync_url = _sync_url()
    state = _classify_db(sync_url)
    cfg = _alembic_config(sync_url)

    if state == "fresh":
        logger.info("Fresh database — creating schema from models")
        engine = create_engine(sync_url)
        try:
            Base.metadata.create_all(engine)
        finally:
            engine.dispose()
        # Mark all migrations as applied; we built the current schema directly
        command.stamp(cfg, "head")
        return

    if state == "legacy":
        logger.warning(
            "Legacy database detected — stamping baseline and upgrading to head"
        )
        command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")
        return

    # state == "migrated"
    logger.info("Migrated database — running pending upgrades")
    command.upgrade(cfg, "head")


async def bootstrap_database() -> None:
    """Public entry point — call from FastAPI lifespan on startup."""
    await asyncio.to_thread(_bootstrap_sync)
