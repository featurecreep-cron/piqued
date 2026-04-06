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

    @pytest.mark.asyncio
    async def test_feeds_unread_and_untriaged_counts(self, transport):
        """Per-user counts: unread = no feedback at all, untriaged = no
        explicit vote. A click_through counts as 'seen' (so no longer unread)
        but does NOT count as 'triaged'.
        """
        from piqued.db import async_session
        from piqued.models import (
            Article,
            ArticleStatus,
            Feed,
            Feedback,
            FeedbackSource,
            Section,
        )

        user, token = await _create_user()

        async with async_session() as session:
            feed = Feed(
                freshrss_feed_id="acme-feed-1",
                title="Acme",
                url="https://acme.example/feed",
                category="news",
                active=True,
                content_quality="full",
            )
            session.add(feed)
            await session.flush()

            # Five complete articles + one pending article (pending must be
            # excluded from both counts).
            articles = []
            for i in range(5):
                a = Article(
                    feed_id=feed.id,
                    freshrss_item_id=f"acme-{i}",
                    title=f"Article {i}",
                    url=f"https://acme.example/{i}",
                    digest_date="2026-04-06",
                    status=ArticleStatus.complete,
                )
                articles.append(a)
                session.add(a)
            pending = Article(
                feed_id=feed.id,
                freshrss_item_id="acme-pending",
                title="Pending",
                url="https://acme.example/pending",
                digest_date="2026-04-06",
                status=ArticleStatus.pending,
            )
            session.add(pending)
            await session.flush()

            # Each article gets one section
            sections = []
            for a in articles:
                s = Section(
                    article_id=a.id,
                    section_index=0,
                    heading=f"section for {a.title}",
                    summary="x",
                )
                sections.append(s)
                session.add(s)
            await session.flush()

            # Article 0: explicit thumbs up → both seen and triaged
            session.add(
                Feedback(
                    user_id=user.id,
                    section_id=sections[0].id,
                    rating=1,
                    source=FeedbackSource.explicit,
                )
            )
            # Article 1: click_through only → seen but not triaged
            session.add(
                Feedback(
                    user_id=user.id,
                    section_id=sections[1].id,
                    rating=1,
                    source=FeedbackSource.click_through,
                )
            )
            # Article 2: explicit thumbs down → both seen and triaged
            session.add(
                Feedback(
                    user_id=user.id,
                    section_id=sections[2].id,
                    rating=-1,
                    source=FeedbackSource.explicit,
                )
            )
            # Articles 3 and 4: untouched → unread AND untriaged
            await session.commit()

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/feeds",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert len(data["feeds"]) == 1
            f = data["feeds"][0]
            # 5 complete + 1 pending = 6 total
            assert f["article_count"] == 6
            # Unread = articles 3,4 (no feedback at all). Article 1 (click only)
            # counts as seen.
            assert f["unread_count"] == 2
            # Untriaged = articles 1,3,4 (no explicit vote). Articles 0 and 2
            # have explicit votes.
            assert f["untriaged_count"] == 3

    @pytest.mark.asyncio
    async def test_feeds_counts_are_per_user(self, transport):
        """User A's votes don't affect User B's unread/untriaged counts."""
        from piqued.db import async_session
        from piqued.models import (
            Article,
            ArticleStatus,
            Feed,
            Feedback,
            FeedbackSource,
            Section,
        )

        user_a, token_a = await _create_user()
        user_b, token_b = await _create_user()

        async with async_session() as session:
            feed = Feed(
                freshrss_feed_id="shared-feed-1",
                title="Shared",
                url="https://shared.example/feed",
                category="news",
                active=True,
                content_quality="full",
            )
            session.add(feed)
            await session.flush()
            article = Article(
                feed_id=feed.id,
                freshrss_item_id="shared-1",
                title="Shared 1",
                url="https://shared.example/1",
                digest_date="2026-04-06",
                status=ArticleStatus.complete,
            )
            session.add(article)
            await session.flush()
            section = Section(
                article_id=article.id,
                section_index=0,
                heading="x",
                summary="x",
            )
            session.add(section)
            await session.flush()
            # User A votes; user B does not
            session.add(
                Feedback(
                    user_id=user_a.id,
                    section_id=section.id,
                    rating=1,
                    source=FeedbackSource.explicit,
                )
            )
            await session.commit()

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            ra = await client.get(
                "/api/v1/feeds",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            rb = await client.get(
                "/api/v1/feeds",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            fa = ra.json()["feeds"][0]
            fb = rb.json()["feeds"][0]
            # A has triaged the only article
            assert fa["unread_count"] == 0
            assert fa["untriaged_count"] == 0
            # B has not — same article shows as unread + untriaged for B
            assert fb["unread_count"] == 1
            assert fb["untriaged_count"] == 1


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

    @pytest.mark.asyncio
    async def test_save_settings_persists_auth_methods(self, transport):
        """Auth checkboxes round-trip as a comma-separated string.

        The response is built by re-reading the settings table inside the
        same request, so a matching value in the response confirms a real
        DB write rather than an echoed payload.
        """
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/settings",
                json={"auth_methods": "oidc,header"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json()["settings"]["auth_methods"] == "oidc,header"

            # Independent GET (separate request) — confirms DB persistence
            r2 = await client.get(
                "/api/v1/settings",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r2.json()["settings"]["auth_methods"] == "oidc,header"

    @pytest.mark.asyncio
    async def test_save_settings_masked_password_is_ignored(self, transport):
        """The masked •••••••• placeholder must NOT overwrite a real password."""
        _, token = await _create_user()
        # Seed a real value in the DB so we can prove it survives a masked save
        await config.save_setting("llm_api_key", "real-secret-abc123")

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/settings",
                json={"llm_api_key": "••••••••"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200

            # Read back via the API (response is masked, so check the cache)
            assert r.status_code == 200

        # The save_settings_api function only writes keys that pass the
        # masked-placeholder filter — confirm the cache still holds the real value
        assert config.get("llm_api_key") == "real-secret-abc123"

    @pytest.mark.asyncio
    async def test_save_settings_requires_admin(self, transport):
        _, token = await _create_user(role="user")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.put(
                "/api/v1/settings",
                json={"auth_methods": "local"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 403


class TestApiTestLlm:
    @pytest.mark.asyncio
    async def test_rejects_missing_provider(self, transport):
        _, token = await _create_user()
        config._cache["llm_provider"] = ""
        config._cache["llm_model"] = ""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-llm",
                json={},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["ok"] is False
            assert "required" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_rejects_missing_api_key(self, transport):
        _, token = await _create_user()
        config._cache["llm_api_key"] = ""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-llm",
                json={"provider": "gemini", "model": "gemini-2.5-flash"},
                headers={"Authorization": f"Bearer {token}"},
            )
            body = r.json()
            assert body["ok"] is False
            assert "api key" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_ollama_does_not_require_api_key(self, transport, monkeypatch):
        """Ollama is local — the api-key required check must be skipped."""
        _, token = await _create_user()
        # Clear the saved api key so the test proves ollama bypasses the
        # missing-key validation entirely (not just inheriting a saved key).
        config._cache["llm_api_key"] = ""

        from piqued.llm.base import LLMResponse

        captured = {}

        class FakeClient:
            async def generate(self, prompt, **kwargs):
                return LLMResponse(text="ok", tokens_used=2, model="llama3")

        def fake_create_client(provider, model, api_key="", base_url=""):
            captured["provider"] = provider
            captured["api_key"] = api_key
            return FakeClient()

        monkeypatch.setattr("piqued.llm.create_client", fake_create_client)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-llm",
                json={
                    "provider": "ollama",
                    "model": "llama3",
                    "base_url": "http://localhost:11434",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            body = r.json()
            assert body["ok"] is True, f"expected ok=True, got: {body}"
            assert "ollama/llama3" in body["detail"]
            assert "ok" in body["detail"]
        assert captured["provider"] == "ollama"
        assert captured["api_key"] == ""

    @pytest.mark.asyncio
    async def test_uses_saved_api_key_when_body_omits_it(self, transport, monkeypatch):
        """If the user clicks Test without retyping a masked password, the saved key is used."""
        _, token = await _create_user()
        config._cache["llm_api_key"] = "saved-real-key"
        config._cache["llm_provider"] = "gemini"
        config._cache["llm_model"] = "gemini-2.5-flash"

        from piqued.llm.base import LLMResponse

        captured = {}

        class FakeClient:
            async def generate(self, prompt, **kwargs):
                return LLMResponse(text="ok", tokens_used=1, model="g")

        def fake_create_client(provider, model, api_key="", base_url=""):
            captured["api_key"] = api_key
            captured["provider"] = provider
            return FakeClient()

        monkeypatch.setattr("piqued.llm.create_client", fake_create_client)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-llm",
                json={"provider": "gemini", "model": "gemini-2.5-flash"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.json()["ok"] is True

        assert captured["api_key"] == "saved-real-key"
        assert captured["provider"] == "gemini"

    @pytest.mark.asyncio
    async def test_reports_provider_exception(self, transport, monkeypatch):
        """An exception from the LLM client must surface as ok=False, not a 500."""
        _, token = await _create_user()
        config._cache["llm_api_key"] = "k"

        def fake_create_client(*a, **kw):
            raise RuntimeError("boom: invalid api key")

        monkeypatch.setattr("piqued.llm.create_client", fake_create_client)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-llm",
                json={"provider": "gemini", "model": "gemini-2.5-flash"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["ok"] is False
            assert "RuntimeError" in body["detail"]
            assert "boom" in body["detail"]

    @pytest.mark.asyncio
    async def test_requires_admin(self, transport):
        _, token = await _create_user(role="user")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-llm",
                json={"provider": "gemini", "model": "gemini-2.5-flash"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 403


class TestApiTestFreshrss:
    @pytest.mark.asyncio
    async def test_rejects_missing_fields(self, transport):
        _, token = await _create_user()
        config._cache["freshrss_base_url"] = ""
        config._cache["freshrss_username"] = ""
        config._cache["freshrss_api_pass"] = ""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-freshrss",
                json={},
                headers={"Authorization": f"Bearer {token}"},
            )
            body = r.json()
            assert body["ok"] is False
            assert "required" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_success_reports_subscription_count(self, transport, monkeypatch):
        _, token = await _create_user()

        async def fake_authenticate(self):
            self._token = "fake-token"

        async def fake_get_subscriptions(self):
            return [{"id": "1"}, {"id": "2"}, {"id": "3"}]

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient._authenticate", fake_authenticate
        )
        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient.get_subscriptions",
            fake_get_subscriptions,
        )
        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient.close", fake_close
        )

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-freshrss",
                json={
                    "freshrss_base_url": "https://example.com",
                    "freshrss_username": "user",
                    "freshrss_api_pass": "pass",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            body = r.json()
            assert body["ok"] is True
            assert "3 subscriptions" in body["detail"]

    @pytest.mark.asyncio
    async def test_reports_auth_failure(self, transport, monkeypatch):
        _, token = await _create_user()

        async def fake_authenticate(self):
            raise RuntimeError("Auth failed: bad credentials")

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient._authenticate", fake_authenticate
        )
        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient.close", fake_close
        )

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-freshrss",
                json={
                    "freshrss_base_url": "https://example.com",
                    "freshrss_username": "user",
                    "freshrss_api_pass": "pass",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            body = r.json()
            assert body["ok"] is False
            assert "RuntimeError" in body["detail"]
            assert "Auth failed" in body["detail"]

    @pytest.mark.asyncio
    async def test_uses_saved_api_pass_when_body_omits_it(self, transport, monkeypatch):
        _, token = await _create_user()
        config._cache["freshrss_api_pass"] = "saved-pass-xyz"
        config._cache["freshrss_base_url"] = "https://saved.example.com"
        config._cache["freshrss_username"] = "saved-user"

        captured = {}

        def fake_init(self, base_url=None, username=None, api_pass=None):
            captured["base_url"] = base_url
            captured["username"] = username
            captured["api_pass"] = api_pass
            self._token = None
            import httpx

            self._client = httpx.AsyncClient()
            self.base_url = base_url
            self.username = username
            self.api_pass = api_pass

        async def fake_authenticate(self):
            pass

        async def fake_get_subscriptions(self):
            return []

        async def fake_close(self):
            await self._client.aclose()

        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient._authenticate", fake_authenticate
        )
        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient.get_subscriptions",
            fake_get_subscriptions,
        )
        monkeypatch.setattr(
            "piqued.ingestion.freshrss.FreshRSSClient.close", fake_close
        )

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/settings/test-freshrss",
                json={
                    "freshrss_base_url": "https://override.example.com",
                    "freshrss_username": "override-user",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.json()["ok"] is True

        # Body fields used where present, saved value used where absent
        assert captured["base_url"] == "https://override.example.com"
        assert captured["username"] == "override-user"
        assert captured["api_pass"] == "saved-pass-xyz"


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
