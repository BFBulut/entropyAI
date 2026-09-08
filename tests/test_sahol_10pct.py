"""Automated test suite for SAHOL 1-Week 10% Probability Engine."""

import sys
from pathlib import Path
import pytest

# Ensure scripts directory is importable
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from sahol_10pct_probability import evaluate_sahol_10pct_1week


def test_sahol_10pct_target_and_sigma():
    res = evaluate_sahol_10pct_1week()

    assert res["current_price_try"] == 92.50
    assert res["target_price_try"] == 101.75
    assert res["target_return_pct"] == 10.0
    assert res["trading_days"] == 5

    # 10% move in 5 days is an extreme statistical event (~1.91 sigma)
    assert 1.70 < res["z_score_distance"] < 2.10
    assert 4.0 < res["period_volatility_pct"] < 5.5


def test_sahol_10pct_probabilities():
    res = evaluate_sahol_10pct_1week()
    probs = res["probabilities"]

    # Terminal closing probability at Day 5 is strictly under 5%
    assert 1.5 < probs["terminal_probability_10pct"] < 5.0
    # Intraday touch probability is strictly under 10%
    assert 3.5 < probs["touch_probability_10pct"] < 10.0

    # In contrast, a realistic +4% move has much higher probability
    assert probs["realistic_4pct_terminal_prob"] > 20.0
    assert probs["realistic_4pct_touch_prob"] > 40.0


def test_sahol_capital_expansion_and_verdict():
    res = evaluate_sahol_10pct_1week()
    cap = res["capital_and_liquidity"]
    verdict = res["verdict"]

    # Market cap expansion required exceeds 19 Billion TRY
    assert cap["new_capital_required_b"] > 19.0
    assert cap["beta_5y"] == 0.41

    assert verdict["is_probable"] is False
    assert "DÜŞÜK" in verdict["probability_rating"]
