"""Tests for LLM-based content classifier.

Focus: bot_challenge handling. The Bloomberg/Money Stuff regression that
prompted this category surfaced because a CAPTCHA HTML page was returning
200 OK with substantial-looking text, and the classifier was forced to pick
the closest of {full_article, teaser, paywall_page, error_page, login_wall}
— which is full_article — and segmentation then surfaced "Captcha
Verification" as interesting content.
"""

import json

import pytest
from dataclasses import dataclass

from piqued.ingestion.classifier import (
    CLASSIFICATION_PROMPT,
    classify_content,
    update_feed_quality,
)


@dataclass
class FakeResponse:
    text: str
    tokens_used: int = 10


class FakeClient:
    """Mock LLM client that returns a canned classification."""

    def __init__(self, classification: str, confidence: float = 0.95):
        self._classification = classification
        self._confidence = confidence

    async def generate(
        self, prompt, system_prompt=None, json_mode=False, temperature=0.1, max_tokens=150
    ):
        return FakeResponse(
            text=json.dumps(
                {
                    "classification": self._classification,
                    "confidence": self._confidence,
                    "reason": "test",
                }
            )
        )


class TestPromptCovers:
    def test_prompt_mentions_bot_challenge_keywords(self):
        """The classification prompt must instruct the LLM about CAPTCHA pages.

        Without explicit instruction, the LLM picks the closest existing category
        (full_article) and the page slips through. The keywords below are the
        actual phrases real bot-challenge pages use.
        """
        for keyword in (
            "bot_challenge",
            "CAPTCHA",
            "unusual network activity",
            "Cloudflare",
            "verify",
        ):
            assert keyword in CLASSIFICATION_PROMPT, (
                f"prompt missing the {keyword!r} signal — "
                "real bot-challenge pages will be misclassified"
            )


class TestClassifyContent:
    @pytest.mark.asyncio
    async def test_bot_challenge_passes_validation(self):
        """The classifier must accept bot_challenge as a valid response."""
        client = FakeClient("bot_challenge")
        classification, confidence, _ = await classify_content(
            client,
            content_text="The system detected unusual network activity, "
            "requiring a CAPTCHA to verify the user isn't a robot.",
            title="Money Stuff",
            feed_name="Bloomberg",
            url="https://www.bloomberg.com/opinion/articles/example",
        )
        assert classification == "bot_challenge"
        assert confidence == 0.95

    @pytest.mark.asyncio
    async def test_unknown_classification_falls_back_to_full_article(self):
        """Defensive: an LLM returning a made-up category does not crash."""
        client = FakeClient("alien_invasion")
        classification, _, _ = await classify_content(
            client,
            content_text="text",
            title="t",
            feed_name="f",
            url="u",
        )
        assert classification == "full_article"

    @pytest.mark.asyncio
    async def test_existing_categories_still_pass(self):
        """Regression: don't break the existing five categories."""
        for cat in ("full_article", "teaser", "paywall_page", "error_page", "login_wall"):
            client = FakeClient(cat)
            classification, _, _ = await classify_content(
                client, content_text="x", title="t", feed_name="f", url="u"
            )
            assert classification == cat


class TestUpdateFeedQuality:
    def test_bot_challenge_maps_to_paywall_quality(self):
        """A captcha-walled feed must be tracked as paywall so we stop hammering it."""
        new_quality, new_streak = update_feed_quality(
            current_quality="paywall",
            current_streak=2,
            new_classification="bot_challenge",
        )
        assert new_quality == "paywall"
        assert new_streak == 3

    def test_bot_challenge_locks_when_quality_already_paywall(self):
        """When the feed is already locked as paywall, a captcha keeps it there
        and bumps the streak. (See note below: there is a separate latent bug
        where streaks from 'unknown' never accumulate — out of scope here.)
        """
        new_quality, new_streak = update_feed_quality(
            current_quality="paywall",
            current_streak=5,
            new_classification="bot_challenge",
        )
        assert new_quality == "paywall"
        assert new_streak == 6
