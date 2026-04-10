"""Tests for the bootstrap calibration endpoints and pipeline functions."""

import hashlib
import os
import secrets
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ["PIQUED_DATABASE_PATH"] = "/tmp/piqued_test_bootstrap.db"

from piqued import config
from piqued.db import async_session, engine
from piqued.main import app
from piqued.models import (
    ApiKey,
    Article,
    ArticleStatus,
    Base,
    Feed,
    Section,
    SectionScore,
    User,
    UserProfile,
)


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
        await session.refresh(user)

    return user, full_key


async def _create_feed_with_sections(
    feed_title: str = "Test Feed",
    article_count: int = 1,
    sections_per_article: int = 2,
) -> tuple[Feed, list[Article], list[Section]]:
    """Create a feed with completed articles and sections."""
    from datetime import datetime, timezone

    async with async_session() as session:
        feed = Feed(
            freshrss_feed_id=f"feed/{secrets.token_hex(4)}",
            title=feed_title,
            url="https://example.com/feed",
            category="Test",
            active=True,
        )
        session.add(feed)
        await session.flush()

        articles = []
        sections = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i in range(article_count):
            article = Article(
                freshrss_item_id=f"item_{secrets.token_hex(4)}",
                feed_id=feed.id,
                title=f"Article {i + 1}",
                url=f"https://example.com/article-{i}",
                content_html="<p>Test content</p>",
                published_at=datetime.now(timezone.utc),
                digest_date=today,
                status=ArticleStatus.complete,
            )
            session.add(article)
            await session.flush()
            articles.append(article)

            for j in range(sections_per_article):
                section = Section(
                    article_id=article.id,
                    section_index=j,
                    heading=f"Section {j + 1}",
                    summary=f"Summary of section {j + 1} from {feed_title}",
                    topic_tags="python,testing",
                    confidence=0.5,
                )
                session.add(section)
                sections.append(section)

        await session.commit()
        for obj in [feed] + articles + sections:
            await session.refresh(obj)

    return feed, articles, sections


class TestBootstrapStatus:
    @pytest.mark.asyncio
    async def test_status_new_user(self, transport):
        """New user has bootstrap_complete=False and no sections."""
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/bootstrap/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["bootstrap_complete"] is False
            assert data["has_sections"] is False

    @pytest.mark.asyncio
    async def test_status_with_sections(self, transport):
        """Status reports has_sections=True when content exists."""
        _, token = await _create_user()
        await _create_feed_with_sections()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/bootstrap/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["has_sections"] is True

    @pytest.mark.asyncio
    async def test_status_after_complete(self, transport):
        """After bootstrap complete, status reports True."""
        import json

        user, token = await _create_user()
        async with async_session() as session:
            u = await session.get(User, user.id)
            u.preferences = json.dumps({"bootstrap_complete": True})
            await session.commit()

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/bootstrap/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json()["bootstrap_complete"] is True


class TestBootstrapSample:
    @pytest.mark.asyncio
    async def test_sample_empty(self, transport):
        """Returns empty list when no content exists."""
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/bootstrap/sample",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json() == []

    @pytest.mark.asyncio
    async def test_sample_returns_sections(self, transport):
        """Returns sections from active feeds."""
        _, token = await _create_user()
        await _create_feed_with_sections("Feed A")
        await _create_feed_with_sections("Feed B")

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/bootstrap/sample",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert len(data) == 2
            feed_titles = {s["feed_title"] for s in data}
            assert "Feed A" in feed_titles
            assert "Feed B" in feed_titles

    @pytest.mark.asyncio
    async def test_sample_max_five(self, transport):
        """Sample caps at 5 sections."""
        _, token = await _create_user()
        for i in range(7):
            await _create_feed_with_sections(f"Feed {i}")

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/bootstrap/sample",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert len(r.json()) == 5


class TestBootstrapIngest:
    @pytest.mark.asyncio
    async def test_ingest_validates_feed_count(self, transport):
        """Rejects empty or >10 feed lists."""
        _, token = await _create_user()
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/bootstrap/ingest",
                json={"feed_ids": []},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 422

            r = await client.post(
                "/api/v1/bootstrap/ingest",
                json={"feed_ids": list(range(11))},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_calls_pipeline(self, transport):
        """Ingest endpoint calls the pipeline function."""
        _, token = await _create_user()
        feed, _, _ = await _create_feed_with_sections()

        with patch(
            "piqued.processing.pipeline.ingest_feeds",
            new_callable=AsyncMock,
            return_value=4,
        ) as mock_ingest:
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                r = await client.post(
                    "/api/v1/bootstrap/ingest",
                    json={"feed_ids": [feed.id]},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200
                data = r.json()
                assert data["ok"] is True
                assert data["section_count"] == 4
                mock_ingest.assert_called_once_with([feed.id], max_per_feed=2)


class TestBootstrapComplete:
    @pytest.mark.asyncio
    async def test_complete_marks_preferences(self, transport):
        """Complete endpoint sets bootstrap_complete in preferences."""
        import json

        user, token = await _create_user()

        with patch(
            "piqued.processing.pipeline.score_recent_for_user",
            new_callable=AsyncMock,
            return_value=3,
        ):
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                r = await client.post(
                    "/api/v1/bootstrap/complete",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200
                data = r.json()
                assert data["ok"] is True
                assert data["sections_scored"] == 3

        # Verify preference was saved
        async with async_session() as session:
            u = await session.get(User, user.id)
            prefs = json.loads(u.preferences or "{}")
            assert prefs["bootstrap_complete"] is True


class TestScoreRecentForUser:
    @pytest.mark.asyncio
    async def test_no_profile_returns_zero(self):
        """Returns 0 if user has no profile."""
        from piqued.processing.pipeline import score_recent_for_user

        result = await score_recent_for_user(999, days=1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_no_unscored_sections(self):
        """Returns 0 if no unscored sections exist."""
        from piqued.processing.pipeline import score_recent_for_user

        user, _ = await _create_user()
        async with async_session() as session:
            profile = UserProfile(user_id=user.id, profile_text="likes python")
            session.add(profile)
            await session.commit()

        result = await score_recent_for_user(user.id, days=1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_scores_unscored_sections(self):
        """Scores sections that haven't been scored for this user."""
        from collections import namedtuple

        from piqued.processing.pipeline import score_recent_for_user

        user, _ = await _create_user()
        _, _, sections = await _create_feed_with_sections(sections_per_article=2)

        async with async_session() as session:
            profile = UserProfile(
                user_id=user.id, profile_text="likes python", profile_version=1
            )
            session.add(profile)
            await session.commit()

        ScoredSection = namedtuple(
            "ScoredSection", ["section_id", "score", "reasoning"]
        )
        mock_scored = [
            ScoredSection(section_id=s.id, score=0.8, reasoning="relevant")
            for s in sections
        ]

        with (
            patch(
                "piqued.processing.profile_scorer.score_sections_for_user",
                new_callable=AsyncMock,
                return_value=(mock_scored, 100),
            ),
            patch(
                "piqued.processing.pipeline._get_llm_client",
                return_value=AsyncMock(),
            ),
        ):
            result = await score_recent_for_user(user.id, days=1)
            assert result == 2

        # Verify scores were stored
        async with async_session() as session:
            from sqlalchemy import select

            scores = (
                (
                    await session.execute(
                        select(SectionScore).where(SectionScore.user_id == user.id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(scores) == 2
            assert all(s.score == 0.8 for s in scores)


class TestIngestFeeds:
    @pytest.mark.asyncio
    async def test_no_feeds_returns_zero(self):
        """Returns 0 if feed IDs don't exist."""
        from piqued.processing.pipeline import ingest_feeds

        with patch("piqued.processing.pipeline.FreshRSSClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.close = AsyncMock()
            MockClient.return_value = mock_instance

            result = await ingest_feeds([999], max_per_feed=2)
            assert result == 0
