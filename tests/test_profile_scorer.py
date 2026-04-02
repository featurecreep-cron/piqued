"""Tests for LLM-driven profile scoring and synthesis."""

import json
import os
import pytest

os.environ["PIQUED_DATABASE_PATH"] = "/tmp/piqued_test_profile.db"

from piqued.processing.profile_scorer import _parse_scoring_response
from piqued.feedback.synthesizer import _format_feedback


class TestScoreResponseParsing:
    """Test parsing LLM scoring responses."""

    def test_parse_valid_response(self):
        sections = [
            {"id": 10, "index": 0, "heading": "Test 1"},
            {"id": 20, "index": 1, "heading": "Test 2"},
        ]
        response = json.dumps(
            [
                {"index": 0, "score": 0.8, "reasoning": "Matches interest in law"},
                {"index": 1, "score": 0.3, "reasoning": "Not relevant"},
            ]
        )
        results = _parse_scoring_response(response, sections)
        assert len(results) == 2
        assert results[0].section_id == 10
        assert results[0].score == 0.8
        assert results[1].section_id == 20
        assert results[1].score == 0.3

    def test_parse_clamps_scores(self):
        sections = [{"id": 1, "index": 0, "heading": "Test"}]
        response = json.dumps(
            [
                {"index": 0, "score": 1.5, "reasoning": "Over max"},
            ]
        )
        results = _parse_scoring_response(response, sections)
        assert results[0].score == 1.0

    def test_parse_negative_clamp(self):
        sections = [{"id": 1, "index": 0, "heading": "Test"}]
        response = json.dumps(
            [
                {"index": 0, "score": -0.5, "reasoning": "Under min"},
            ]
        )
        results = _parse_scoring_response(response, sections)
        assert results[0].score == 0.0

    def test_parse_skips_unknown_indices(self):
        sections = [{"id": 1, "index": 0, "heading": "Test"}]
        response = json.dumps(
            [
                {"index": 0, "score": 0.5, "reasoning": "Valid"},
                {"index": 99, "score": 0.9, "reasoning": "No matching section"},
            ]
        )
        results = _parse_scoring_response(response, sections)
        assert len(results) == 1
        assert results[0].section_id == 1

    def test_parse_handles_markdown_fenced_json(self):
        sections = [{"id": 1, "index": 0, "heading": "Test"}]
        response = '```json\n[{"index": 0, "score": 0.7, "reasoning": "test"}]\n```'
        results = _parse_scoring_response(response, sections)
        assert len(results) == 1
        assert results[0].score == 0.7

    def test_parse_empty_response(self):
        sections = [{"id": 1, "index": 0, "heading": "Test"}]
        with pytest.raises(json.JSONDecodeError):
            _parse_scoring_response("", sections)

    def test_parse_non_array_response(self):
        sections = [{"id": 1, "index": 0, "heading": "Test"}]
        with pytest.raises(ValueError, match="Expected JSON array"):
            _parse_scoring_response('{"score": 0.5}', sections)


class TestFeedbackFormatting:
    """Test feedback item formatting for synthesis prompt."""

    def test_format_positive_feedback(self):
        items = [
            {
                "heading": "Great Article",
                "tags": ["law", "rights"],
                "rating": 1,
                "reason": "",
            }
        ]
        result = _format_feedback(items)
        assert "👍 Liked" in result
        assert "Great Article" in result
        assert "law, rights" in result

    def test_format_negative_with_reason(self):
        items = [
            {
                "heading": "Boring",
                "tags": ["sports"],
                "rating": -1,
                "reason": "Don't care about sports",
            }
        ]
        result = _format_feedback(items)
        assert "👎 Disliked" in result
        assert "Don't care about sports" in result

    def test_format_multiple_items(self):
        items = [
            {"heading": "A", "tags": [], "rating": 1, "reason": ""},
            {"heading": "B", "tags": [], "rating": -1, "reason": ""},
        ]
        result = _format_feedback(items)
        assert result.count("- ") == 2

    def test_format_empty_batch(self):
        result = _format_feedback([])
        assert result == ""


class TestModelEnums:
    """Verify new models have correct structure."""

    def test_user_profile_model_exists(self):
        from piqued.models import UserProfile

        assert hasattr(UserProfile, "profile_text")
        assert hasattr(UserProfile, "profile_version")
        assert hasattr(UserProfile, "pending_feedback_count")

    def test_section_score_model_exists(self):
        from piqued.models import SectionScore

        assert hasattr(SectionScore, "score")
        assert hasattr(SectionScore, "reasoning")
        assert hasattr(SectionScore, "profile_version")

    def test_user_has_profile_relationship(self):
        from piqued.models import User

        assert "profile" in User.__mapper__.relationships


class TestRouterIntegrity:
    """Verify router code references valid variables."""

    def test_no_undefined_user_in_templates(self):
        """Every route that passes current_user to template must have user dependency."""
        import re

        with open("piqued/web/router.py") as f:
            source = f.read()

        # Find function definitions and check for user dependency
        func_pattern = re.compile(
            r"(async def \w+\([^)]*\).*?)(?=async def |\Z)", re.DOTALL
        )
        for match in func_pattern.finditer(source):
            block = match.group(1)
            if '"current_user": user' in block or "'current_user': user" in block:
                has_dep = "get_current_user" in block or "require_admin" in block
                func_name = re.search(r"async def (\w+)", block).group(1)
                assert has_dep, (
                    f"{func_name} passes 'user' to template but has no user dependency"
                )
