"""Tests for Phase 0 features: decay, profile editing, onboarding seeding."""

import os

# Set test DB before any imports
os.environ["PIQUED_DATABASE_PATH"] = "/tmp/piqued_test_phase0.db"

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from piqued import config
from piqued.db import async_session, engine
from piqued.feedback.learner import apply_interest_decay
from piqued.models import Base, InterestWeight, User


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    config._cache.clear()
    config._cache_loaded = True
    yield
    config._cache.clear()
    config._cache_loaded = False


async def _create_user(session, username="testuser"):
    user = User(username=username, role="user", role_source="auto")
    session.add(user)
    await session.flush()
    return user


class TestInterestDecay:
    """Test the nightly interest decay logic."""

    @pytest.mark.asyncio
    async def test_decay_reduces_positive_weight(self):
        async with async_session() as session:
            user = await _create_user(session)
            old_date = datetime.now(timezone.utc) - timedelta(days=30)
            session.add(InterestWeight(
                user_id=user.id, topic="old-topic", weight=0.8,
                feedback_count=5, updated_at=old_date,
            ))
            await session.commit()
            uid = user.id

        config._cache["interest_decay_rate"] = "0.05"
        config._cache["interest_decay_after_days"] = "14"
        await apply_interest_decay()

        async with async_session() as session:
            w = await session.get(InterestWeight, (uid, "old-topic"))
            assert w.weight == pytest.approx(0.75, abs=0.001)

    @pytest.mark.asyncio
    async def test_decay_reduces_negative_weight(self):
        async with async_session() as session:
            user = await _create_user(session, "neg_user")
            old_date = datetime.now(timezone.utc) - timedelta(days=30)
            session.add(InterestWeight(
                user_id=user.id, topic="disliked", weight=-0.6,
                feedback_count=3, updated_at=old_date,
            ))
            await session.commit()
            uid = user.id

        config._cache["interest_decay_rate"] = "0.05"
        config._cache["interest_decay_after_days"] = "14"
        await apply_interest_decay()

        async with async_session() as session:
            w = await session.get(InterestWeight, (uid, "disliked"))
            assert w.weight == pytest.approx(-0.55, abs=0.001)

    @pytest.mark.asyncio
    async def test_decay_skips_recent_weights(self):
        async with async_session() as session:
            user = await _create_user(session, "recent_user")
            recent_date = datetime.now(timezone.utc) - timedelta(days=2)
            session.add(InterestWeight(
                user_id=user.id, topic="fresh", weight=0.9,
                feedback_count=10, updated_at=recent_date,
            ))
            await session.commit()
            uid = user.id

        config._cache["interest_decay_rate"] = "0.05"
        config._cache["interest_decay_after_days"] = "14"
        await apply_interest_decay()

        async with async_session() as session:
            w = await session.get(InterestWeight, (uid, "fresh"))
            assert w.weight == pytest.approx(0.9, abs=0.001)

    @pytest.mark.asyncio
    async def test_decay_skips_near_zero(self):
        async with async_session() as session:
            user = await _create_user(session, "zero_user")
            old_date = datetime.now(timezone.utc) - timedelta(days=30)
            session.add(InterestWeight(
                user_id=user.id, topic="tiny", weight=0.005,
                feedback_count=1, updated_at=old_date,
            ))
            await session.commit()
            uid = user.id

        config._cache["interest_decay_rate"] = "0.05"
        config._cache["interest_decay_after_days"] = "14"
        await apply_interest_decay()

        async with async_session() as session:
            w = await session.get(InterestWeight, (uid, "tiny"))
            assert w.weight == pytest.approx(0.005, abs=0.001)

    @pytest.mark.asyncio
    async def test_decay_disabled_when_rate_zero(self):
        config._cache["interest_decay_rate"] = "0"
        config._cache["interest_decay_after_days"] = "14"
        # Should return without error
        await apply_interest_decay()

    @pytest.mark.asyncio
    async def test_decay_does_not_overshoot_zero(self):
        """A weight of 0.03 with decay_rate 0.05 should clamp to 0, not go negative."""
        async with async_session() as session:
            user = await _create_user(session, "overshoot_user")
            old_date = datetime.now(timezone.utc) - timedelta(days=30)
            session.add(InterestWeight(
                user_id=user.id, topic="small-pos", weight=0.03,
                feedback_count=2, updated_at=old_date,
            ))
            await session.commit()
            uid = user.id

        config._cache["interest_decay_rate"] = "0.05"
        config._cache["interest_decay_after_days"] = "14"
        await apply_interest_decay()

        async with async_session() as session:
            w = await session.get(InterestWeight, (uid, "small-pos"))
            assert w.weight == 0.0


class TestConfigKeys:
    """Verify decay config keys exist in DEFAULTS."""

    def test_decay_rate_in_defaults(self):
        from piqued.config import DEFAULTS
        assert "interest_decay_rate" in DEFAULTS
        assert float(DEFAULTS["interest_decay_rate"]) == 0.05

    def test_decay_after_days_in_defaults(self):
        from piqued.config import DEFAULTS
        assert "interest_decay_after_days" in DEFAULTS
        assert int(DEFAULTS["interest_decay_after_days"]) == 14
