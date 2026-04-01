"""Tests for web flows: setup, login, CSRF, onboarding."""

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

# Set test DB before any imports
os.environ["PIQUED_DATABASE_PATH"] = "/tmp/piqued_test_web.db"

from piqued.db import engine
from piqued.models import Base, User, Feed
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
    yield
    config._cache.clear()


@pytest.fixture
def transport():
    return ASGITransport(app=app)


class TestModelEnums:
    """Verify code references valid enum values."""

    def test_article_status_values_used_in_router(self):
        """All ArticleStatus values referenced in router.py exist in the enum."""
        import re
        from piqued.models import ArticleStatus

        with open("piqued/web/router.py") as f:
            source = f.read()

        # Find all ArticleStatus.XXX references
        refs = re.findall(r'ArticleStatus\.(\w+)', source)
        for ref in refs:
            assert hasattr(ArticleStatus, ref), f"ArticleStatus.{ref} does not exist. Valid: {[e.name for e in ArticleStatus]}"


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
            assert b"_csrf" in r.content

    @pytest.mark.asyncio
    async def test_setup_redirects_when_users_exist(self, transport):
        """Setup redirects to login when users already exist."""
        from piqued.db import async_session
        import bcrypt

        async with async_session() as session:
            session.add(User(
                username="existing",
                password_hash=bcrypt.hashpw(b"test", bcrypt.gensalt()).decode(),
                role="admin",
                role_source="auto",
            ))
            await session.commit()

        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            r = await client.get("/setup")
            assert r.status_code == 303
            assert "/login" in r.headers["location"]


class TestCSRF:
    @pytest.mark.asyncio
    async def test_csrf_blocks_post_without_token(self, transport):
        """POST to protected route without CSRF token is rejected."""
        from piqued.db import async_session
        import bcrypt

        # Create user first
        async with async_session() as session:
            session.add(User(
                username="testuser",
                password_hash=bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
                role="admin",
                role_source="auto",
            ))
            await session.commit()

        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            # Login to get session
            r = await client.get("/login")
            # Extract CSRF from login page
            import re
            csrf_match = re.search(r'name="_csrf" value="([^"]+)"', r.text)
            csrf = csrf_match.group(1) if csrf_match else ""

            r = await client.post("/login", data={
                "username": "testuser",
                "password": "testpass",
                "_csrf": csrf,
            })
            assert r.status_code == 303  # redirect after login

            # Now POST to settings WITHOUT csrf
            r = await client.post("/settings", data={"llm_provider": "gemini"})
            assert r.status_code == 403
            assert "CSRF" in r.text

    @pytest.mark.asyncio
    async def test_csrf_allows_post_with_valid_token(self, transport):
        """POST with valid CSRF token succeeds."""
        from piqued.db import async_session
        import bcrypt

        async with async_session() as session:
            session.add(User(
                username="testuser",
                password_hash=bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
                role="admin",
                role_source="auto",
            ))
            await session.commit()

        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            # Login
            r = await client.get("/login")
            import re
            csrf_match = re.search(r'name="_csrf" value="([^"]+)"', r.text)
            csrf = csrf_match.group(1) if csrf_match else ""
            r = await client.post("/login", data={
                "username": "testuser",
                "password": "testpass",
                "_csrf": csrf,
            })
            assert r.status_code == 303

            # Get a page to obtain the session CSRF
            r = await client.get("/settings")
            csrf_match = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
            if not csrf_match:
                csrf_match = re.search(r'name="_csrf" value="([^"]+)"', r.text)
            new_csrf = csrf_match.group(1) if csrf_match else ""
            assert new_csrf, "CSRF token should be present in settings page"

            # POST with valid CSRF — should not get 403
            r = await client.post("/settings", data={
                "_csrf": new_csrf,
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-flash",
            })
            # Should redirect (303) on success, not 403
            assert r.status_code != 403


class TestFormBodyPreservation:
    @pytest.mark.asyncio
    async def test_form_data_available_after_csrf_check(self, transport):
        """Route handler can read form data after CSRF middleware parsed body."""
        from piqued.db import async_session
        import bcrypt

        # Create user + feeds
        async with async_session() as session:
            session.add(User(
                username="testuser",
                password_hash=bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
                role="admin",
                role_source="auto",
            ))
            session.add(Feed(
                freshrss_feed_id="feed/1",
                title="Test Feed",
                url="http://example.com/feed",
                active=False,
            ))
            await session.commit()

        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            # Login
            r = await client.get("/login")
            import re
            csrf_match = re.search(r'name="_csrf" value="([^"]+)"', r.text)
            csrf = csrf_match.group(1) if csrf_match else ""
            r = await client.post("/login", data={
                "username": "testuser",
                "password": "testpass",
                "_csrf": csrf,
            })

            # Get onboarding page to get CSRF
            r = await client.get("/onboarding")
            csrf_match = re.search(r'name="_csrf" value="([^"]+)"', r.text)
            new_csrf = csrf_match.group(1) if csrf_match else ""

            # Submit feed selection — feed_id=1 should be available to handler
            r = await client.post("/onboarding/select-feed", data={
                "_csrf": new_csrf,
                "feed_id": "1",
            })
            # Should NOT be "Feed not found" (feed_id=0) — that means body was consumed
            if r.status_code == 200:
                assert "feed_id=0" not in r.text, "Form body was consumed by middleware — feed_id not available to handler"
