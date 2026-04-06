"""Regression tests for the Alembic schema bootstrap.

These tests cover the three startup scenarios:
- fresh: empty DB, schema created from models
- legacy: pre-Alembic DB without preferences column
- migrated: DB already managed by Alembic

The legacy case reproduces the production failure that prompted this work:
a long-lived database with the old users schema causes 500 errors on login
because the ORM expects users.preferences.
"""

import os
from pathlib import Path

# Use a dedicated test DB path so we can drop/recreate freely
TEST_DB_PATH = "/tmp/piqued_test_migrations.db"
os.environ["PIQUED_DATABASE_PATH"] = TEST_DB_PATH

import pytest  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402


def _wipe_db():
    Path(TEST_DB_PATH).unlink(missing_ok=True)


def _sync_engine():
    return create_engine(f"sqlite:///{TEST_DB_PATH}")


def _column_exists(table: str, column: str) -> bool:
    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            return column in {c["name"] for c in inspect(conn).get_columns(table)}
    finally:
        engine.dispose()


def _table_exists(table: str) -> bool:
    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            return table in inspect(conn).get_table_names()
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def clean_db(monkeypatch):
    # Other test modules set PIQUED_DATABASE_PATH at import time; reassert ours
    # per-test so _sync_url() resolves to our isolated DB.
    monkeypatch.setenv("PIQUED_DATABASE_PATH", TEST_DB_PATH)
    _wipe_db()
    yield
    _wipe_db()


def test_fresh_db_creates_full_schema_and_stamps_head():
    """Empty DB → create_all + stamp head."""
    from piqued.db_bootstrap import _bootstrap_sync

    _bootstrap_sync()

    assert _table_exists("users")
    assert _table_exists("alembic_version")
    assert _column_exists("users", "preferences")

    # alembic_version should hold the head revision
    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev is not None
    finally:
        engine.dispose()


def test_legacy_db_gets_stamped_and_upgraded():
    """Pre-Alembic DB without preferences → stamp baseline, upgrade head.

    This is the exact production failure mode.
    """
    # Build the old users table by hand (no preferences column, no alembic_version)
    engine = _sync_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        email TEXT,
                        password_hash TEXT,
                        oidc_sub TEXT UNIQUE,
                        oidc_provider TEXT,
                        role TEXT DEFAULT 'user',
                        role_source TEXT DEFAULT 'auto',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_login DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text("INSERT INTO users (username, role) VALUES ('legacy', 'user')")
            )
    finally:
        engine.dispose()

    assert not _column_exists("users", "preferences")
    assert not _table_exists("alembic_version")

    from piqued.db_bootstrap import _bootstrap_sync

    _bootstrap_sync()

    assert _column_exists("users", "preferences")
    assert _table_exists("alembic_version")

    # Existing user data should survive the migration
    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT username, preferences FROM users WHERE username='legacy'")
            ).first()
            assert row is not None
            assert row[0] == "legacy"
            assert row[1] == "{}"
    finally:
        engine.dispose()


def test_migrated_db_runs_pending_upgrades_idempotently():
    """Already-migrated DB → upgrade head is a no-op when already at head."""
    from piqued.db_bootstrap import _bootstrap_sync

    _bootstrap_sync()  # fresh
    _bootstrap_sync()  # should be a no-op
    _bootstrap_sync()  # still no-op

    assert _column_exists("users", "preferences")


def test_orm_query_works_after_legacy_upgrade():
    """The exact query from the production stack trace must succeed post-bootstrap."""
    # Build legacy schema with a user
    engine = _sync_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        email TEXT,
                        password_hash TEXT,
                        oidc_sub TEXT UNIQUE,
                        oidc_provider TEXT,
                        role TEXT DEFAULT 'user',
                        role_source TEXT DEFAULT 'auto',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_login DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text("INSERT INTO users (username, role) VALUES ('smilerz', 'admin')")
            )
    finally:
        engine.dispose()

    from piqued.db_bootstrap import _bootstrap_sync

    _bootstrap_sync()

    # Reproduce the failing query path: SELECT users.id, ..., users.preferences ...
    # Build a fresh async engine bound to this test's DB (piqued.db.engine is
    # frozen at import time to whichever test loaded it first).
    import asyncio

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from piqued.models import User

    async def _query():
        async_engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_PATH}")
        try:
            session_factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as session:
                return await session.scalar(select(User).where(User.username == "smilerz"))
        finally:
            await async_engine.dispose()

    user = asyncio.run(_query())
    assert user is not None
    assert user.username == "smilerz"
    assert user.preferences == "{}"
