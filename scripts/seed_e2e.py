#!/usr/bin/env python3
"""Seed the database for E2E tests. Creates a test user and minimal config."""

import asyncio
import os
import sys

# Set test DB path before any piqued imports
os.environ["PIQUED_DATABASE_PATH"] = os.environ.get(
    "PIQUED_DATABASE_PATH", "/tmp/piqued_e2e.db"
)

from piqued import config  # noqa: E402
from piqued.db import async_session, engine  # noqa: E402
from piqued.models import Base, Feed, User  # noqa: E402


async def seed():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed config
    config._cache.clear()
    config._cache["llm_api_key"] = "test-key"
    config._cache["freshrss_api_pass"] = "test-pass"
    config._cache["session_secret_key"] = "e2e-test-secret"
    config._cache_loaded = True
    await config.save_settings(
        {
            "llm_api_key": "test-key",
            "freshrss_api_pass": "test-pass",
            "session_secret_key": "e2e-test-secret",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
        }
    )

    # Create test user
    import bcrypt

    async with async_session() as session:
        user = User(
            username="testuser",
            password_hash=bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
            role="admin",
            role_source="manual",
        )
        session.add(user)

        # Add a couple of test feeds
        session.add(
            Feed(
                freshrss_feed_id="feed/test-1",
                title="Test Feed One",
                url="https://example.com/feed1",
                category="Technology",
                active=True,
            )
        )
        session.add(
            Feed(
                freshrss_feed_id="feed/test-2",
                title="Test Feed Two",
                url="https://example.com/feed2",
                category="Science",
                active=True,
            )
        )
        await session.commit()

    print("E2E database seeded successfully")


if __name__ == "__main__":
    asyncio.run(seed())
