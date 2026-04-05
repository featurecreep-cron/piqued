"""Tests for the /api/v1/ JSON API endpoints."""

import hashlib
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ["PIQUED_DATABASE_PATH"] = "/tmp/piqued_test_api_v1.db"

from piqued import config
from piqued.db import engine
from piqued.main import app
from piqued.models import ApiKey, Base, User


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    config._cache.clear()
    config._cache["llm_api_key"] = "test-key"
    config._cache["freshrss_api_pass"] = "test-pass"
    config._cache["session_secret_key"] = "test-secret"
    config._cache_loaded = True
    yield
    config._cache.clear()
    config._cache_loaded = False


@pytest.fixture
def transport():
    return ASGITransport(app=app)


async def _create_user(role="admin") -> tuple[User, str]:
    """Create a user and API key, return (user, bearer_token)."""
    import secrets

    from piqued.db import async_session

    raw = secrets.token_hex(16)
    full_key = f"pqd_{raw}"
    prefix = raw[:8]
    key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()

    async with async_session() as session:
        user = User(
            username=f"test_{secrets.token_hex(4)}", role=role, role_source="manual"
        )
        session.add(user)
        await session.flush()

        api_key = ApiKey(
            user_id=user.id,
            key_prefix=prefix,
            key_hash=key_hash,
            name="test",
        )
        session.add(api_key)
        await session.commit()
        # Refresh to get the id
        await session.refresh(user)

    return user, full_key


class TestApiHealth:
    @pytest.mark.asyncio
    async def test_health_no_auth(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/health")
            assert r.status_code == 200
            assert r.json() == {"status": "ok"}


class TestApiAuth:
    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/me")
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_bad_token_returns_401(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/me", headers={"Authorization": "Bearer pqd_invalidtoken1234"}
            )
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, transport):
        user, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert r.status_code == 200
            data = r.json()
            assert data["username"] == user.username
            assert data["role"] == "admin"


class TestApiCsrfExemption:
    @pytest.mark.asyncio
    async def test_api_post_without_csrf_succeeds(self, transport):
        """API routes should not require CSRF tokens."""
        user, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/keys",
                json={"name": "test-key"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["key"].startswith("pqd_")


class TestApiKeys:
    @pytest.mark.asyncio
    async def test_create_and_list_keys(self, transport):
        user, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create a key
            r = await client.post(
                "/api/v1/keys", json={"name": "my-key"}, headers=headers
            )
            assert r.status_code == 200
            created = r.json()
            assert created["name"] == "my-key"
            new_key = created["key"]

            # List keys
            r = await client.get("/api/v1/keys", headers=headers)
            assert r.status_code == 200
            keys = r.json()["keys"]
            assert any(k["name"] == "my-key" for k in keys)

            # Use the new key
            r = await client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer {new_key}"},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_revoke_key(self, transport):
        user, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/keys", json={"name": "revoke-me"}, headers=headers
            )
            key_id = r.json()["id"]

            r = await client.delete(f"/api/v1/keys/{key_id}", headers=headers)
            assert r.status_code == 200
            assert r.json()["ok"] is True


class TestApiUserIsolation:
    @pytest.mark.asyncio
    async def test_user_cannot_see_other_users_keys(self, transport):
        _, token_a = await _create_user(role="user")
        _, token_b = await _create_user(role="user")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # User A creates a key
            r = await client.post(
                "/api/v1/keys",
                json={"name": "a-key"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert r.status_code == 200

            # User B lists keys — should not see A's key
            r = await client.get(
                "/api/v1/keys",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            keys = r.json()["keys"]
            # B should only see the key created by _create_user for B (the fixture key)
            assert not any(k["name"] == "a-key" for k in keys)

    @pytest.mark.asyncio
    async def test_user_cannot_revoke_other_users_key(self, transport):
        _, token_a = await _create_user(role="user")
        _, token_b = await _create_user(role="user")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/keys",
                json={"name": "a-key"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
            key_id = r.json()["id"]

            # User B tries to revoke A's key
            r = await client.delete(
                f"/api/v1/keys/{key_id}",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert r.status_code == 404


class TestApiAdminGuard:
    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_users(self, transport):
        _, token = await _create_user(role="user")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/users",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_list_users(self, transport):
        _, token = await _create_user(role="admin")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/users",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert len(r.json()["users"]) >= 1


class TestApiSections:
    @pytest.mark.asyncio
    async def test_sections_returns_empty_list(self, transport):
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/sections",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["sections"] == []
            assert "date" in data
            assert "threshold" in data


class TestApiFeeds:
    @pytest.mark.asyncio
    async def test_feeds_returns_empty(self, transport):
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/feeds",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json()["feeds"] == []


class TestApiSettings:
    @pytest.mark.asyncio
    async def test_settings_returns_config(self, transport):
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/settings",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert "settings" in data
            assert data["is_admin"] is True


class TestApiLog:
    @pytest.mark.asyncio
    async def test_log_returns_empty(self, transport):
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/log",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["entries"] == []
            assert data["total"] == 0


class TestApiProfile:
    @pytest.mark.asyncio
    async def test_profile_default(self, transport):
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["profile_text"] == ""
            assert data["profile_version"] == 0

    @pytest.mark.asyncio
    async def test_edit_profile(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/profile",
                json={"profile_text": "I like distributed systems"},
                headers=headers,
            )
            assert r.status_code == 200
            data = r.json()
            assert data["profile_text"] == "I like distributed systems"
            assert data["profile_version"] == 1


class TestApiFeedXml:
    @pytest.mark.asyncio
    async def test_feed_xml_returns_rss(self, transport):
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/feed.xml",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert "xml" in r.headers["content-type"]
            assert "<rss" in r.text


class TestApiPreferences:
    @pytest.mark.asyncio
    async def test_get_defaults(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/preferences", headers=headers)
            assert r.status_code == 200
            data = r.json()
            assert data["theme"] == "light"
            assert data["layout_mode"] == "river"
            assert data["items_per_page"] == 50
            assert data["column_config"] is None

    @pytest.mark.asyncio
    async def test_update_theme(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/preferences",
                json={"theme": "dark"},
                headers=headers,
            )
            assert r.status_code == 200
            assert r.json()["theme"] == "dark"

            # Verify it persisted
            r = await client.get("/api/v1/preferences", headers=headers)
            assert r.json()["theme"] == "dark"
            # Other fields unchanged
            assert r.json()["layout_mode"] == "river"

    @pytest.mark.asyncio
    async def test_update_layout_mode(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/preferences",
                json={"layout_mode": "columns"},
                headers=headers,
            )
            assert r.status_code == 200
            assert r.json()["layout_mode"] == "columns"

    @pytest.mark.asyncio
    async def test_update_multiple(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/preferences",
                json={"theme": "dark", "layout_mode": "reader", "items_per_page": 100},
                headers=headers,
            )
            assert r.status_code == 200
            data = r.json()
            assert data["theme"] == "dark"
            assert data["layout_mode"] == "reader"
            assert data["items_per_page"] == 100

    @pytest.mark.asyncio
    async def test_update_column_config(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/preferences",
                json={"column_config": ["AI", "Security", "Homelab"]},
                headers=headers,
            )
            assert r.status_code == 200
            assert r.json()["column_config"] == ["AI", "Security", "Homelab"]

    @pytest.mark.asyncio
    async def test_invalid_theme_rejected(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/preferences",
                json={"theme": "blue"},
                headers=headers,
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_layout_rejected(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/preferences",
                json={"layout_mode": "grid"},
                headers=headers,
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_items_per_page_bounds(self, transport):
        _, token = await _create_user()
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/preferences",
                json={"items_per_page": 5},
                headers=headers,
            )
            assert r.status_code == 422

            r = await client.put(
                "/api/v1/preferences",
                json={"items_per_page": 500},
                headers=headers,
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_preferences_per_user(self, transport):
        _, token_a = await _create_user(role="user")
        _, token_b = await _create_user(role="user")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # User A sets dark theme
            await client.put(
                "/api/v1/preferences",
                json={"theme": "dark"},
                headers={"Authorization": f"Bearer {token_a}"},
            )

            # User B still has default
            r = await client.get(
                "/api/v1/preferences",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert r.json()["theme"] == "light"
