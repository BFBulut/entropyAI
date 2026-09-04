"""Automated pytest test suite for Market Liquidity, Short Squeeze and VC Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from market_liquidity_vc import (
    calculate_short_squeeze_risk,
    calculate_vc_dilution,
    calculate_impermanent_loss,
    calculate_aofm
)


def test_short_squeeze_risk():
    # Extreme squeeze case: 25% short float, 6 days to cover, 35% borrow fee
    ext_res = calculate_short_squeeze_risk(
        short_interest_shares=2500000,
        float_shares=10000000,
        avg_daily_volume=400000,
        borrow_fee_pct=35.0
    )
    assert ext_res["short_float_pct"] == 25.0
    assert ext_res["days_to_cover"] == 6.25
    assert ext_res["squeeze_alert"] is True
    assert "EKSTREM" in ext_res["risk_verdict"]

    # Low risk case: 4% short float, 1.5 days to cover
    low_res = calculate_short_squeeze_risk(
        short_interest_shares=400000,
        float_shares=10000000,
        avg_daily_volume=266667,
        borrow_fee_pct=2.0
    )
    assert low_res["short_float_pct"] == 4.0
    assert low_res["days_to_cover"] == 1.5
    assert low_res["squeeze_alert"] is False
    assert "DÜŞÜK" in low_res["risk_verdict"]

    # Invalid input
    err = calculate_short_squeeze_risk(100, 0, 0)
    assert "error" in err


def test_vc_dilution():
    # 20M pre-money, 5M investment, 10M existing shares
    # Post-money = 25M, Investor equity = 5/25 = 20%, Founder retained = 80%
    # Share price = 20M / 10M = $2.0
    # New shares = 5M / 2 = 2.5M. Total = 12.5M shares.
    res = calculate_vc_dilution(
        pre_money_valuation=20000000.0,
        investment_amount=5000000.0,
        existing_shares=10000000.0
    )
    assert res["post_money_valuation"] == 25000000.0
    assert res["investor_equity_pct"] == 20.0
    assert res["founder_retained_equity_pct"] == 80.0
    assert res["effective_share_price"] == 2.0
    assert res["new_shares_issued"] == 2500000.0
    assert res["total_post_shares"] == 12500000.0

    # Invalid input
    err = calculate_vc_dilution(0, 10, 10)
    assert "error" in err


def test_impermanent_loss():
    # Price ratio k = 2.0 (asset doubles)
    # IL = 2*sqrt(2)/(1+2) - 1 = 2*1.4142/3 - 1 = 2.8284/3 - 1 = 0.9428 - 1 = -0.0572 (-5.72%)
    res = calculate_impermanent_loss(price_ratio_k=2.0)
    assert res["price_change_pct"] == 100.0
    assert abs(res["impermanent_loss_pct"] - (-5.72)) < 0.05
    assert res["breakeven_fee_yield_needed_pct"] > 5.0

    # No price change: k = 1.0 -> IL = 0.0
    zero_res = calculate_impermanent_loss(price_ratio_k=1.0)
    assert zero_res["impermanent_loss_pct"] == 0.0

    # Invalid input
    err = calculate_impermanent_loss(0.0)
    assert "error" in err


def test_aofm():
    # Buckets: 100M at 45%, 50M at 47%
    # Total = 150M. Weighted sum = 4500 + 2350 = 6850.
    # AOFM = 6850 / 150 = 45.667%
    buckets = [
        {"amount": 100.0, "rate": 45.0},
        {"amount": 50.0, "rate": 47.0}
    ]
    res = calculate_aofm(buckets)
    assert res["total_funding_volume"] == 150.0
    assert abs(res["aofm_rate_pct"] - 45.667) < 0.01

    # Empty buckets
    err = calculate_aofm([])
    assert "error" in err
