"""Automated pytest test suite for Quantitative Calculator Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from quant_calculator import (
    calculate_saas_metrics,
    calculate_banking_metrics,
    calculate_bond_price_change,
    calculate_order_book_imbalance,
    calculate_vwap
)


def test_saas_metrics():
    # Pass rule of 40: 30% growth + 15% FCF margin = 45%
    res = calculate_saas_metrics(
        revenue_growth_pct=30.0,
        fcf_margin_pct=15.0,
        cac=5000,
        ltv=20000,
        quarterly_net_arr_add=250000,
        prev_quarter_sm_spend=1000000
    )
    assert res["rule_of_40_passed"] is True
    assert res["rule_of_40_score"] == 45.0
    assert res["ltv_cac_ratio"] == 4.0
    assert "Mükemmel" in res["ltv_cac_status"]
    assert res["magic_number"] == 1.0
    assert "Agresif Satış" in res["magic_number_status"]

    # Fail rule of 40: 10% growth + 5% FCF margin = 15%
    fail_res = calculate_saas_metrics(10.0, 5.0)
    assert fail_res["rule_of_40_passed"] is False
    assert fail_res["rule_of_40_score"] == 15.0


def test_banking_metrics():
    res = calculate_banking_metrics(
        interest_income=120000,
        interest_expense=40000,
        earning_assets=2000000,
        tier1_capital=240000,
        tier2_capital=60000,
        risk_weighted_assets=2000000
    )
    assert res["net_interest_margin_pct"] == 4.0
    assert res["capital_adequacy_ratio_pct"] == 15.0
    assert "Güçlü Tampon" in res["basel_iii_status"]

    # Invalid input
    err = calculate_banking_metrics(10, 5, 0, 10, 0, 0)
    assert "error" in err


def test_bond_price_change():
    # 7-year modified duration, 50 convexity, +100 bps (+1%) yield hike
    res = calculate_bond_price_change(
        modified_duration=7.0,
        convexity=50.0,
        yield_change_bps=100.0
    )
    # duration effect = -7 * 0.01 = -0.07 (-7%)
    # convexity effect = 0.5 * 50 * 0.0001 = 0.0025 (+0.25%)
    # total = -6.75%
    assert res["duration_effect_pct"] == -7.0
    assert res["convexity_effect_pct"] == 0.25
    assert res["estimated_total_price_change_pct"] == -6.75


def test_order_book_imbalance():
    # Strong buy pressure: 7000 bids vs 3000 asks -> OBI = (7000-3000)/10000 = +0.40
    res = calculate_order_book_imbalance(bid_volume=7000, ask_volume=3000)
    assert res["obi"] == 0.4
    assert res["bid_ratio_pct"] == 70.0

    # Strong sell pressure: 2000 bids vs 8000 asks -> OBI = -0.60
    sell_res = calculate_order_book_imbalance(bid_volume=2000, ask_volume=8000)
    assert sell_res["obi"] == -0.6
    assert "Satış Baskısı" in sell_res["microstructure_signal"]

    # Invalid
    inv = calculate_order_book_imbalance(0, 0)
    assert "error" in inv


def test_vwap():
    trades = [
        {"price": 100.0, "volume": 100},
        {"price": 105.0, "volume": 200},
        {"price": 102.0, "volume": 100},
    ]
    # Total turnover = 10000 + 21000 + 10200 = 41200
    # Total volume = 400
    # VWAP = 41200 / 400 = 103.0
    res = calculate_vwap(trades)
    assert res["vwap"] == 103.0
    assert res["total_volume"] == 400.0
    assert res["total_turnover"] == 41200.0
