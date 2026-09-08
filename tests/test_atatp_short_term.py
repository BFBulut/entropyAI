"""Automated test suite for ATATP 11-Day Short-Term Probability & Technical Engine."""

import sys
from pathlib import Path
import pytest

# Ensure scripts path is importable
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from atatp_short_term_probability import calculate_11day_atatp_probability


def test_atatp_11day_target_and_parameters():
    res = calculate_11day_atatp_probability()

    assert res["current_price_try"] == 293.75
    assert res["target_gain_pct"] == 10.0
    assert abs(res["target_price_try"] - 323.125) < 0.02
    assert res["calendar_days"] == 11
    assert res["trading_days"] == 8
    assert res["parameters"]["annual_volatility_pct"] == 52.0
    assert 8.0 < res["parameters"]["period_volatility_pct"] < 11.0


def test_atatp_11day_statistical_probabilities():
    res = calculate_11day_atatp_probability()
    probs = res["probabilities"]

    # In an 8-trading-day horizon, a 10% upward jump is a >1 standard deviation move
    assert 12.0 < probs["terminal_probability_pct"] < 25.0
    assert 25.0 < probs["touch_probability_pct"] < 50.0


def test_atatp_11day_technical_resistance_and_catalysts():
    res = calculate_11day_atatp_probability()
    tech = res["technical_structure"]
    catalyst = res["catalyst_timeline"]

    # Target 323.13 TRY falls exactly into the 315-325 TRY resistance zone
    assert tech["target_inside_resistance"] is True
    assert tech["major_support_fib_382_try"] == 274.57
    assert tech["technical_indicator_state"].startswith("Sell")

    # Catalysts
    assert catalyst["next_earnings_date"] == "2026-11-06"
    assert catalyst["has_earnings_in_window"] is False
    assert catalyst["days_to_earnings"] >= 50
