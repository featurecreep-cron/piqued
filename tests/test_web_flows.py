"""Tests for web flows: setup, login, health."""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set test DB before any imports
os.environ["PIQUED_DATABASE_PATH"] = "/tmp/piqued_test_web.db"

from piqued.db import engine
from piqued.models import Base, User
from piqued.main import app
from piqued import config


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables and configure for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # Set minimum config so is_configured() works
    config._cache.clear()
    config._cache["llm_api_key"] = "test-key"
    config._cache["freshrss_api_pass"] = "test-pass"
    config._cache["session_secret_key"] = "test-secret-key-for-testing"
    config._cache_loaded = True
    yield
    config._cache.clear()
    config._cache_loaded = False


@pytest.fixture
def transport():
    return ASGITransport(app=app)


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_no_auth(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup_get_when_no_users(self, transport):
        """Setup page accessible when no users exist."""
        config._cache.pop("llm_api_key", None)
        config._cache.pop("freshrss_api_pass", None)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/setup")
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_setup_redirects_when_users_exist(self, transport):
        """Setup redirects to login when users already exist."""
        from piqued.db import async_session
        import bcrypt

        async with async_session() as session:
            session.add(
                User(
                    username="existing",
                    password_hash=bcrypt.hashpw(b"test", bcrypt.gensalt()).decode(),
                    role="admin",
                    role_source="auto",
                )
            )
            await session.commit()

        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as client:
            r = await client.get("/setup")
            assert r.status_code == 303
            assert "/login" in r.headers["location"]
