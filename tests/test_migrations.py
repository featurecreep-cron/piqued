"""Regression tests for the lightweight schema migration runner.

These tests simulate the production scenario: a database created against an
older schema is opened by a newer version of the app. Without migrations,
queries that reference new columns fail with sqlite3.OperationalError.
"""

import os

# Use a dedicated test DB so we can drop/recreate tables freely
os.environ["PIQUED_DATABASE_PATH"] = "/tmp/piqued_test_migrations.db"

import pytest
import pytest_asyncio
from sqlalchemy import text

from piqued.db import async_session, engine
from piqued.migrations import COLUMN_ADDITIONS, run_migrations
from piqued.models import Base


@pytest_asyncio.fixture(autouse=True)
async def fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _column_exists(conn, table: str, column: str) -> bool:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    return column in {row[1] for row in result.fetchall()}


@pytest.mark.asyncio
async def test_migration_adds_missing_preferences_column():
    """Simulate an old DB without users.preferences and verify migration adds it."""
    # Build the old users table (no preferences column)
    async with engine.begin() as conn:
        await conn.execute(
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

    # Confirm column is missing
    async with engine.begin() as conn:
        assert not await _column_exists(conn, "users", "preferences")

    # Run migrations
    async with engine.begin() as conn:
        await run_migrations(conn)

    # Confirm column now exists
    async with engine.begin() as conn:
        assert await _column_exists(conn, "users", "preferences")


@pytest.mark.asyncio
async def test_migration_is_idempotent():
    """Running migrations twice on a fresh DB should not error."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await run_migrations(conn)
        await run_migrations(conn)


@pytest.mark.asyncio
async def test_migrated_user_can_be_queried_via_orm():
    """After migration, an ORM query referencing the new column must succeed.

    This is the exact failure mode from the production stack trace.
    """
    # Old-schema users table
    async with engine.begin() as conn:
        await conn.execute(
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
        await conn.execute(
            text("INSERT INTO users (username, role) VALUES ('legacy', 'user')")
        )

    # Apply migrations
    async with engine.begin() as conn:
        await run_migrations(conn)

    # Query through the ORM, which references the preferences column
    from sqlalchemy import select
    from piqued.models import User

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.username == "legacy"))
        assert user is not None
        assert user.username == "legacy"
        assert user.preferences == "{}"


@pytest.mark.asyncio
async def test_all_model_columns_have_migration_or_exist_after_create_all():
    """Sanity check: every column in COLUMN_ADDITIONS targets a real model column.

    Prevents drift where the migration list goes stale relative to the models.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, column, _ddl in COLUMN_ADDITIONS:
            assert await _column_exists(conn, table, column), (
                f"Migration targets {table}.{column} but model doesn't define it"
            )
