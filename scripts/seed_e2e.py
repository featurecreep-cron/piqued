#!/usr/bin/env python3
"""Seed the database for E2E tests.

Creates admin + regular users, feeds, articles, sections with scores,
interest weights, processing log entries, and a user profile — enough
data to exercise all Phase 2 UAT scenarios.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

# Set test DB path before any piqued imports
os.environ["PIQUED_DATABASE_PATH"] = os.environ.get(
    "PIQUED_DATABASE_PATH", "/tmp/piqued_e2e.db"
)

import bcrypt  # noqa: E402

from piqued import config  # noqa: E402
from piqued.db import async_session, engine  # noqa: E402
from piqued.models import (  # noqa: E402
    Article,
    ArticleStatus,
    Base,
    Feed,
    InterestWeight,
    ProcessingLog,
    Section,
    SectionScore,
    User,
    UserProfile,
)

# Use UTC to match the server's digest_date query
_now_utc = datetime.now(timezone.utc)
TODAY = _now_utc.strftime("%Y-%m-%d")
YESTERDAY = (_now_utc - timedelta(days=1)).strftime("%Y-%m-%d")


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
            "confidence_threshold": "0.6",
            "surprise_surface_pct": "0.15",
        }
    )

    pw_admin = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()
    pw_user = bcrypt.hashpw(b"userpass", bcrypt.gensalt()).decode()

    async with async_session() as session:
        # ── Users ──────────────────────────────────────────────
        admin = User(
            username="testuser",
            password_hash=pw_admin,
            role="admin",
            role_source="manual",
        )
        regular = User(
            username="reader",
            password_hash=pw_user,
            role="user",
            role_source="manual",
        )
        session.add_all([admin, regular])
        await session.flush()  # get IDs

        # ── Feeds ──────────────────────────────────────────────
        feed_tech = Feed(
            freshrss_feed_id="feed/test-1",
            title="Test Feed One",
            url="https://example.com/feed1",
            category="Technology",
            active=True,
            content_quality="full",
        )
        feed_sci = Feed(
            freshrss_feed_id="feed/test-2",
            title="Test Feed Two",
            url="https://example.com/feed2",
            category="Science",
            active=True,
            content_quality="full",
        )
        feed_inactive = Feed(
            freshrss_feed_id="feed/test-3",
            title="Inactive Feed",
            url="https://example.com/feed3",
            category="Technology",
            active=False,
            content_quality="unknown",
        )
        session.add_all([feed_tech, feed_sci, feed_inactive])
        await session.flush()

        # ── Articles (today + yesterday for date nav) ──────────
        articles = []
        article_data = [
            {
                "freshrss_item_id": "item/today-1",
                "feed_id": feed_tech.id,
                "title": "New Rust Features in 2026",
                "url": "https://example.com/rust-2026",
                "digest_date": TODAY,
                "status": ArticleStatus.complete,
            },
            {
                "freshrss_item_id": "item/today-2",
                "feed_id": feed_sci.id,
                "title": "Quantum Computing Breakthrough",
                "url": "https://example.com/quantum",
                "digest_date": TODAY,
                "status": ArticleStatus.complete,
            },
            {
                "freshrss_item_id": "item/today-3",
                "feed_id": feed_tech.id,
                "title": "Docker Security Best Practices",
                "url": "https://example.com/docker-security",
                "digest_date": TODAY,
                "status": ArticleStatus.complete,
            },
            {
                "freshrss_item_id": "item/yesterday-1",
                "feed_id": feed_tech.id,
                "title": "Yesterday's Tech Article",
                "url": "https://example.com/yesterday",
                "digest_date": YESTERDAY,
                "status": ArticleStatus.complete,
            },
        ]
        for ad in article_data:
            a = Article(**ad)
            session.add(a)
            articles.append(a)
        await session.flush()

        # ── Sections — spread across tiers ─────────────────────
        sections = []
        section_data = [
            # Above threshold (Likely) — high confidence
            {
                "article_id": articles[0].id,
                "section_index": 0,
                "heading": "Memory safety improvements",
                "summary": "Rust 2026 introduces compile-time borrow checker improvements that reduce false positives by 40%.",
                "topic_tags": "rust,programming,memory-safety",
                "confidence": 0.85,
                "is_surprise": False,
                "has_actionable_advice": True,
                "reasoning": "Strong match with programming interest profile",
            },
            {
                "article_id": articles[0].id,
                "section_index": 1,
                "heading": "Async runtime changes",
                "summary": "The async ecosystem consolidates around a unified runtime interface.",
                "topic_tags": "rust,async,programming",
                "confidence": 0.78,
                "is_surprise": False,
                "has_humor": False,
                "reasoning": "Related to active programming interests",
            },
            {
                "article_id": articles[2].id,
                "section_index": 0,
                "heading": "Container image signing",
                "summary": "Sigstore and cosign provide cryptographic supply chain verification for Docker images.",
                "topic_tags": "docker,security,devops",
                "confidence": 0.72,
                "is_surprise": False,
                "has_actionable_advice": True,
                "reasoning": "Direct homelab relevance",
            },
            # Surprise — below threshold but flagged
            {
                "article_id": articles[1].id,
                "section_index": 0,
                "heading": "Topological qubits achieve stability",
                "summary": "Microsoft's topological approach reaches error correction thresholds for the first time.",
                "topic_tags": "quantum,physics,computing",
                "confidence": 0.35,
                "is_surprise": True,
                "has_surprise_data": True,
                "reasoning": "Low profile match but surprising development",
            },
            # Below threshold
            {
                "article_id": articles[1].id,
                "section_index": 1,
                "heading": "Quantum networking protocols",
                "summary": "New entanglement-based protocols enable quantum key distribution over 1000km fiber.",
                "topic_tags": "quantum,networking",
                "confidence": 0.25,
                "is_surprise": False,
                "reasoning": "Low relevance to current interests",
            },
            {
                "article_id": articles[2].id,
                "section_index": 1,
                "heading": "Rootless container gotchas",
                "summary": "Common pitfalls when running rootless containers in production environments.",
                "topic_tags": "docker,linux,security",
                "confidence": 0.45,
                "is_surprise": False,
                "reasoning": "Moderate but below threshold",
            },
            # Yesterday's section
            {
                "article_id": articles[3].id,
                "section_index": 0,
                "heading": "Yesterday's section heading",
                "summary": "Content from yesterday for date navigation testing.",
                "topic_tags": "testing",
                "confidence": 0.70,
                "is_surprise": False,
                "reasoning": "Date navigation test data",
            },
        ]
        for sd in section_data:
            s = Section(**sd)
            session.add(s)
            sections.append(s)
        await session.flush()

        # ── Section scores (per-user cached scores) ────────────
        for s in sections:
            session.add(
                SectionScore(
                    user_id=admin.id,
                    section_id=s.id,
                    score=s.confidence,
                    reasoning=s.reasoning,
                    profile_version=1,
                )
            )
            session.add(
                SectionScore(
                    user_id=regular.id,
                    section_id=s.id,
                    score=s.confidence,
                    reasoning=s.reasoning,
                    profile_version=1,
                )
            )

        # ── Interest weights ───���───────────────────────────────
        weights = [
            ("rust", 0.8, 5),
            ("programming", 0.7, 8),
            ("docker", 0.6, 4),
            ("security", 0.5, 3),
            ("quantum", 0.1, 1),
        ]
        for topic, weight, count in weights:
            session.add(
                InterestWeight(
                    user_id=admin.id,
                    topic=topic,
                    weight=weight,
                    feedback_count=count,
                )
            )

        # ── User profile ───────────────────────────────────────
        session.add(
            UserProfile(
                user_id=admin.id,
                profile_text="Interested in systems programming, Rust, Docker, homelab infrastructure, and security.",
                profile_version=1,
                pending_feedback_count=2,
            )
        )

        # ── Processing log ─────────────────────────────────────
        for a in articles[:3]:
            session.add(
                ProcessingLog(
                    article_id=a.id,
                    stage="classify",
                    status="success",
                    detail=f"Classified {a.title}",
                    tokens_used=150,
                    duration_ms=1200,
                )
            )
            session.add(
                ProcessingLog(
                    article_id=a.id,
                    stage="score",
                    status="success",
                    detail=f"Scored sections for {a.title}",
                    tokens_used=200,
                    duration_ms=800,
                )
            )

        await session.commit()

    print("E2E database seeded successfully")
    print("  Admin: testuser / testpass")
    print("  User:  reader / userpass")
    print("  Feeds: 3 (2 active, 1 inactive)")
    print("  Articles: 4 (3 today, 1 yesterday)")
    print("  Sections: 7 (3 above, 1 surprise, 2 below, 1 yesterday)")
    print("  Processing log: 6 entries")


if __name__ == "__main__":
    asyncio.run(seed())
