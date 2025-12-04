"""Tests for bid score calculation formula.

Tests verify: Score = α·P + β/(T+1) + γ·W
Where:
- P = price
- T = time_elapsed_ms
- W = user_weight
- α, β, γ = coefficients
"""

import pytest
from decimal import Decimal

from app.services.bid_service import calculate_score


class TestScoreCalculation:
    """Test cases for the calculate_score function."""

    def test_basic_score_calculation(self, default_params):
        """Test basic formula: Score = α·P + β/(T+1) + γ·W

        With α=1.0, β=1000.0, γ=100.0, P=1000, T=1000, W=2.0:
        Score = 1.0*1000 + 1000/(1000+1) + 100*2.0
              = 1000 + 0.999... + 200
              ≈ 1200.999
        """
        score = calculate_score(
            price=Decimal("1000"),
            time_elapsed_ms=1000,
            weight=Decimal("2.0"),
            alpha=default_params["alpha"],
            beta=default_params["beta"],
            gamma=default_params["gamma"],
        )

        # Score = 1.0*1000 + 1000/1001 + 100*2.0 ≈ 1200.999
        expected = 1000.0 + 1000.0 / 1001.0 + 200.0
        assert abs(score - expected) < 0.001

    def test_score_with_zero_time(self, default_params):
        """Test when T=0, time bonus is maximum: β/(0+1) = β.

        With T=0: Score = α·P + β + γ·W
        """
        score = calculate_score(
            price=Decimal("500"),
            time_elapsed_ms=0,
            weight=Decimal("1.0"),
            alpha=default_params["alpha"],
            beta=default_params["beta"],
            gamma=default_params["gamma"],
        )

        # Score = 1.0*500 + 1000/(0+1) + 100*1.0 = 500 + 1000 + 100 = 1600
        expected = 500.0 + 1000.0 + 100.0
        assert abs(score - expected) < 0.001

    def test_score_with_high_time(self, default_params):
        """Test when T is large, time bonus approaches 0.

        With T=10000: β/(T+1) = 1000/10001 ≈ 0.1
        """
        score = calculate_score(
            price=Decimal("1000"),
            time_elapsed_ms=10000,
            weight=Decimal("1.0"),
            alpha=default_params["alpha"],
            beta=default_params["beta"],
            gamma=default_params["gamma"],
        )

        # Score = 1.0*1000 + 1000/10001 + 100*1.0 ≈ 1100.1
        expected = 1000.0 + 1000.0 / 10001.0 + 100.0
        assert abs(score - expected) < 0.001

    def test_score_with_very_high_time(self, default_params):
        """Test when T is very large (e.g., 1 hour = 3600000ms).

        Time bonus should be negligible.
        """
        score = calculate_score(
            price=Decimal("1000"),
            time_elapsed_ms=3600000,  # 1 hour
            weight=Decimal("1.0"),
            alpha=default_params["alpha"],
            beta=default_params["beta"],
            gamma=default_params["gamma"],
        )

        # Time bonus ≈ 1000/3600001 ≈ 0.00028, negligible
        expected = 1000.0 + 1000.0 / 3600001.0 + 100.0
        assert abs(score - expected) < 0.001
        # Verify time bonus is < 0.001
        time_bonus = 1000.0 / 3600001.0
        assert time_bonus < 0.001

    @pytest.mark.parametrize("weight,expected_weight_contrib", [
        (Decimal("0.5"), 50.0),   # Low weight user
        (Decimal("1.0"), 100.0),  # Normal weight user
        (Decimal("2.5"), 250.0),  # High weight user
        (Decimal("5.0"), 500.0),  # VIP user
    ])
    def test_score_with_different_weights(self, default_params, weight, expected_weight_contrib):
        """Test score calculation with various user weights.

        Weight contribution = γ·W = 100·W
        """
        score = calculate_score(
            price=Decimal("0"),  # Zero price to isolate weight contribution
            time_elapsed_ms=999999999,  # Very high time to minimize time bonus
            weight=weight,
            alpha=default_params["alpha"],
            beta=default_params["beta"],
            gamma=default_params["gamma"],
        )

        # With P=0 and very high T, score ≈ γ·W
        # Time bonus is negligible (1000/1000000000 ≈ 0)
        assert abs(score - expected_weight_contrib) < 0.1

    def test_score_with_custom_params(self):
        """Test score calculation with custom α, β, γ parameters."""
        score = calculate_score(
            price=Decimal("2000"),
            time_elapsed_ms=500,
            weight=Decimal("3.0"),
            alpha=Decimal("2.0"),   # Double price weight
            beta=Decimal("500.0"),  # Half time bonus
            gamma=Decimal("50.0"),  # Half weight bonus
        )

        # Score = 2.0*2000 + 500/501 + 50*3.0
        #       = 4000 + 0.998 + 150 = 4150.998
        expected = 4000.0 + 500.0 / 501.0 + 150.0
        assert abs(score - expected) < 0.001

    def test_score_price_dominance(self, default_params):
        """Test that higher price leads to higher score (when other factors equal)."""
        score_low = calculate_score(
            price=Decimal("100"),
            time_elapsed_ms=1000,
            weight=Decimal("1.0"),
            **{k: v for k, v in default_params.items()},
        )

        score_high = calculate_score(
            price=Decimal("1000"),
            time_elapsed_ms=1000,
            weight=Decimal("1.0"),
            **{k: v for k, v in default_params.items()},
        )

        assert score_high > score_low
        # Difference should be α * (1000 - 100) = 1.0 * 900 = 900
        assert abs((score_high - score_low) - 900.0) < 0.001

    def test_score_time_advantage(self, default_params):
        """Test that earlier bid (lower T) leads to higher score."""
        score_early = calculate_score(
            price=Decimal("1000"),
            time_elapsed_ms=0,  # Bid at start
            weight=Decimal("1.0"),
            **{k: v for k, v in default_params.items()},
        )

        score_late = calculate_score(
            price=Decimal("1000"),
            time_elapsed_ms=10000,  # Bid 10 seconds later
            weight=Decimal("1.0"),
            **{k: v for k, v in default_params.items()},
        )

        assert score_early > score_late
        # Early bid gets β/(0+1) = 1000, late bid gets β/(10000+1) ≈ 0.1
        time_diff = 1000.0 / 1.0 - 1000.0 / 10001.0
        assert abs((score_early - score_late) - time_diff) < 0.001

    def test_score_weight_advantage(self, default_params):
        """Test that higher weight leads to higher score."""
        score_low_weight = calculate_score(
            price=Decimal("1000"),
            time_elapsed_ms=1000,
            weight=Decimal("1.0"),
            **{k: v for k, v in default_params.items()},
        )

        score_high_weight = calculate_score(
            price=Decimal("1000"),
            time_elapsed_ms=1000,
            weight=Decimal("3.0"),
            **{k: v for k, v in default_params.items()},
        )

        assert score_high_weight > score_low_weight
        # Difference should be γ * (3.0 - 1.0) = 100 * 2.0 = 200
        assert abs((score_high_weight - score_low_weight) - 200.0) < 0.001

    def test_score_with_zero_price(self, default_params):
        """Test score calculation when price is zero."""
        score = calculate_score(
            price=Decimal("0"),
            time_elapsed_ms=0,
            weight=Decimal("1.0"),
            alpha=default_params["alpha"],
            beta=default_params["beta"],
            gamma=default_params["gamma"],
        )

        # Score = 0 + 1000/1 + 100 = 1100
        expected = 0.0 + 1000.0 + 100.0
        assert abs(score - expected) < 0.001

    def test_score_precision(self, default_params):
        """Test that score maintains reasonable precision."""
        score = calculate_score(
            price=Decimal("1234.56"),
            time_elapsed_ms=789,
            weight=Decimal("1.234"),
            alpha=default_params["alpha"],
            beta=default_params["beta"],
            gamma=default_params["gamma"],
        )

        # Verify result is a float
        assert isinstance(score, float)
        # Score should be positive
        assert score > 0

    def test_score_components_are_additive(self, default_params):
        """Verify score formula is additive: Score = price_contrib + time_contrib + weight_contrib."""
        price = Decimal("1000")
        time_ms = 500
        weight = Decimal("2.0")

        full_score = calculate_score(
            price=price,
            time_elapsed_ms=time_ms,
            weight=weight,
            alpha=default_params["alpha"],
            beta=default_params["beta"],
            gamma=default_params["gamma"],
        )

        # Calculate individual contributions
        price_contrib = float(default_params["alpha"] * price)
        time_contrib = float(default_params["beta"]) / (time_ms + 1)
        weight_contrib = float(default_params["gamma"] * weight)

        expected = price_contrib + time_contrib + weight_contrib
        assert abs(full_score - expected) < 0.001
