"""Tests for interest model confidence scoring and surprise surfacing."""

from piqued.processing.scorer import (
    compute_temperature,
    score_section,
    select_surprise_sections,
    sigmoid,
)


class TestSigmoid:
    def test_zero_returns_half(self):
        assert sigmoid(0.0) == 0.5

    def test_large_positive_near_one(self):
        assert sigmoid(10.0) > 0.999

    def test_large_negative_near_zero(self):
        assert sigmoid(-10.0) < 0.001

    def test_symmetric(self):
        assert abs(sigmoid(2.0) + sigmoid(-2.0) - 1.0) < 1e-10

    def test_overflow_protection(self):
        # Should not raise even with extreme values
        assert sigmoid(1000.0) > 0.99
        assert sigmoid(-1000.0) < 0.01


class TestTemperature:
    def test_zero_feedback_returns_four(self):
        assert compute_temperature(0) == 4.0

    def test_200_feedback_returns_two(self):
        assert compute_temperature(200) == 2.0

    def test_100_feedback_returns_three(self):
        assert compute_temperature(100) == 3.0

    def test_caps_at_200(self):
        """Feedback beyond 200 doesn't decrease temperature further."""
        assert compute_temperature(500) == 2.0
        assert compute_temperature(10000) == 2.0

    def test_monotonically_decreasing(self):
        temps = [compute_temperature(i) for i in range(0, 250, 10)]
        for i in range(len(temps) - 1):
            assert temps[i] >= temps[i + 1]


class TestScoreSection:
    def test_no_tags_returns_neutral(self):
        assert score_section({}, [], 0) == 0.5

    def test_positive_weight_above_neutral(self):
        weights = {"ai_capabilities": 0.8}
        score = score_section(weights, ["ai_capabilities"], 0)
        assert score > 0.5

    def test_negative_weight_below_neutral(self):
        weights = {"tech_policy": -0.7}
        score = score_section(weights, ["tech_policy"], 0)
        assert score < 0.5

    def test_mixed_tags_averages(self):
        weights = {"ai_capabilities": 0.8, "tech_policy": -0.8}
        score = score_section(weights, ["ai_capabilities", "tech_policy"], 0)
        # avg weight = 0.0, so score ≈ 0.5
        assert abs(score - 0.5) < 0.01

    def test_unknown_tag_treated_as_zero(self):
        weights = {"ai_capabilities": 0.8}
        score = score_section(weights, ["unknown_tag"], 0)
        assert abs(score - 0.5) < 0.01

    def test_more_feedback_narrows_scores(self):
        """With more feedback, same weights produce less extreme scores."""
        weights = {"ai_capabilities": 0.5}
        score_early = score_section(weights, ["ai_capabilities"], 0)
        score_late = score_section(weights, ["ai_capabilities"], 200)
        # Early (temp=4) should be more extreme than late (temp=2)
        assert abs(score_early - 0.5) > abs(score_late - 0.5)

    def test_strong_positive_high_confidence(self):
        weights = {"ai_capabilities": 1.0}
        score = score_section(weights, ["ai_capabilities"], 0)
        # With temp=4.0, sigmoid(1.0 * 4.0) = sigmoid(4.0) ≈ 0.982
        assert score > 0.95

    def test_strong_negative_low_confidence(self):
        weights = {"spac": -1.0}
        score = score_section(weights, ["spac"], 0)
        assert score < 0.05


class TestSurpriseSurfacing:
    def test_no_below_threshold_returns_empty(self):
        items = [(1, 0.8), (2, 0.6), (3, 0.5)]
        result = select_surprise_sections(items, 0.4, 0.10, "2026-03-23")
        assert result == set()

    def test_surfaces_at_least_one(self):
        items = [(1, 0.1), (2, 0.2), (3, 0.3)]
        result = select_surprise_sections(items, 0.4, 0.10, "2026-03-23")
        assert len(result) >= 1

    def test_only_selects_below_threshold(self):
        items = [(1, 0.1), (2, 0.8), (3, 0.2)]
        result = select_surprise_sections(items, 0.4, 0.50, "2026-03-23")
        # Only items 1 and 3 are below threshold
        assert result.issubset({1, 3})

    def test_stable_within_same_day(self):
        items = [(i, 0.1) for i in range(20)]
        r1 = select_surprise_sections(items, 0.4, 0.10, "2026-03-23")
        r2 = select_surprise_sections(items, 0.4, 0.10, "2026-03-23")
        assert r1 == r2

    def test_varies_between_days(self):
        items = [(i, 0.1) for i in range(20)]
        r1 = select_surprise_sections(items, 0.4, 0.10, "2026-03-23")
        r2 = select_surprise_sections(items, 0.4, 0.10, "2026-03-24")
        # With 20 items and 10% surface rate, different dates should pick different items
        # (not guaranteed but extremely likely with SHA-256)
        assert r1 != r2

    def test_surface_count_respects_percentage(self):
        items = [(i, 0.1) for i in range(100)]
        result = select_surprise_sections(items, 0.4, 0.10, "2026-03-23")
        assert len(result) == 10  # 10% of 100

    def test_empty_input(self):
        result = select_surprise_sections([], 0.4, 0.10, "2026-03-23")
        assert result == set()
