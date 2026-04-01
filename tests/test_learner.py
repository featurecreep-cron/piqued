"""Tests for EWA weight update logic and alpha scaling."""

import math

from piqued.feedback.learner import compute_alpha, update_weight


class TestComputeAlpha:
    def test_zero_feedback_aggressive(self):
        alpha = compute_alpha(0)
        assert abs(alpha - 0.3) < 0.001

    def test_decreases_with_feedback(self):
        alphas = [compute_alpha(i) for i in range(0, 100, 5)]
        for i in range(len(alphas) - 1):
            assert alphas[i] > alphas[i + 1]

    def test_100_feedback_stabilized(self):
        alpha = compute_alpha(100)
        # 0.3 / (1 + ln(101)) ≈ 0.3 / 5.62 ≈ 0.053
        assert alpha < 0.07
        assert alpha > 0.04

    def test_always_positive(self):
        for count in [0, 1, 10, 100, 1000, 10000]:
            assert compute_alpha(count) > 0

    def test_uses_natural_log(self):
        alpha_5 = compute_alpha(5)
        expected = 0.3 / (1.0 + math.log(6))  # ln(6) ≈ 1.79
        assert abs(alpha_5 - expected) < 1e-10


class TestUpdateWeight:
    def test_thumbs_up_increases_weight(self):
        new = update_weight(0.0, 1.0, 0)
        assert new > 0.0

    def test_thumbs_down_decreases_weight(self):
        new = update_weight(0.0, -1.0, 0)
        assert new < 0.0

    def test_clamps_to_positive_one(self):
        new = update_weight(0.9, 1.5, 0)  # surprise +1.5 on already high weight
        assert new <= 1.0

    def test_clamps_to_negative_one(self):
        new = update_weight(-0.9, -1.0, 0)
        assert new >= -1.0

    def test_click_through_weaker_than_explicit(self):
        explicit = update_weight(0.0, 1.0, 0)
        click = update_weight(0.0, 0.5, 0)
        assert click < explicit
        assert click > 0.0

    def test_surprise_thumbs_up_stronger(self):
        regular = update_weight(0.0, 1.0, 0)
        surprise = update_weight(0.0, 1.5, 0)
        assert surprise > regular

    def test_early_feedback_moves_more(self):
        """With low feedback_count, weight changes more per signal."""
        early = update_weight(0.0, 1.0, 0)
        late = update_weight(0.0, 1.0, 100)
        assert abs(early) > abs(late)

    def test_stable_after_many_signals(self):
        """After many signals, individual feedback has diminishing effect."""
        weight = 0.5
        # Apply 100 thumbs-up signals
        for i in range(100):
            weight = update_weight(weight, 1.0, i)
        # Weight should approach 1.0 but be well-behaved
        assert weight <= 1.0
        assert weight > 0.8

    def test_alternating_signals_converge_to_middle(self):
        """Alternating +1/-1 signals should keep weight near zero."""
        weight = 0.0
        for i in range(100):
            rating = 1.0 if i % 2 == 0 else -1.0
            weight = update_weight(weight, rating, i)
        assert abs(weight) < 0.2

    def test_article_level_negative(self):
        """Article-level thumbs-down uses -1.0 rating."""
        new = update_weight(0.5, -1.0, 0)
        assert new < 0.5

    def test_preserves_existing_weight_direction(self):
        """A single contrary signal shouldn't flip the weight direction."""
        # Established positive weight
        weight = 0.7
        new = update_weight(weight, -1.0, 50)
        # With count=50, alpha is small, so one -1 shouldn't flip to negative
        assert new > 0.0
