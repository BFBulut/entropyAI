"""Automated test suite for Ford Otomotiv Sanayi AS (FROTO) Financial Audit Engine."""

import sys
from pathlib import Path
import pytest

# Ensure scripts path is importable
scripts_dir = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(scripts_dir))

from audit_froto import audit_ford_otosan


def test_froto_audit_structure_and_integrity():
    data = audit_ford_otosan()

    assert data["company"] == "Ford Otomotiv Sanayi A.Ş."
    assert data["ticker"] == "IS:FROTO"

    # Market Data
    market = data["market_data"]
    assert market["stock_price_try"] == 76.20
    assert market["market_cap_try_b"] == 267.60
    assert market["dividend_yield_pct"] == 15.0
    assert market["dividend_uninterrupted_years"] == 23
    assert market["dividend_streak_years"] == 5
    assert market["beta_5y"] == 0.32
    assert 41.0 < market["drawdown_from_52w_high_pct"] < 42.0

    # Macro & Margin Scissors
    macro = data["macro_scissors"]
    assert macro["turkey_inflation_pct"] == 32.0
    assert macro["eur_try_appreciation_pct"] == 14.0
    assert macro["negative_margin_scissors_pp"] == 18.0
    assert macro["ebitda_margin_contraction_bps"] == 240.0
    assert macro["export_share_pct"] == 84.0
    assert macro["european_market_share_pct"] == 15.5
    assert macro["european_market_rank"] == 1

    # Profitability Dynamics
    prof = data["profitability_ltm"]
    assert prof["revenue_try_b"] == 775.22
    assert prof["gross_margin_pct"] < 8.0  # Structurally weak gross margin
    assert prof["ebitda_margin_pct"] < 6.0
    assert prof["net_income_try_b"] == 27.16

    # Solvency, Leverage and S&P Warnings
    solvency = data["solvency_and_debt"]
    assert solvency["total_debt_try_b"] == 169.78
    assert solvency["total_equity_try_b"] == 179.19
    assert solvency["current_ratio"] > 1.20
    assert solvency["net_working_capital_try_b"] > 50.0
    assert solvency["debt_to_equity_pct"] > 90.0
    assert solvency["interest_coverage_ratio"] == 1.0
    assert solvency["credit_rating"] == "S&P BB-"

    # Cash Flow Quality & Richard Sloan Accruals
    cf = data["cash_flow_quality"]
    assert cf["cfo_ltm_try_b"] == 45.63
    assert cf["cfo_to_ebitda_pct"] > 100.0  # Strong LTM CFO conversion
    assert cf["sloan_accrual_ratio"] < 0.0  # Cash flows exceed net income (positive earnings quality)
    assert cf["q2_26_levered_fcf_try_m"] < 0  # Free cash flow turned negative in Q2 2026

    # Forensic Altman Z
    forensics = data["forensic_scores"]
    assert 2.8 < forensics["altman_z_score"] < 3.0
    assert "Grey Zone" in forensics["altman_zone"]

    # Valuation & Forward Re-rating
    val = data["valuation_multiples"]
    assert val["pe_ltm"] == 9.85
    assert val["pe_fwd_fy26"] == 7.80
    assert val["pe_fwd_fy27"] == 5.22
    assert val["pe_fwd_fy28"] == 3.48
    assert val["pb_ratio"] == 1.49
    assert val["upside_fair_value_pct"] > 35.0
    assert val["upside_median_analyst_pct"] > 70.0
    assert val["upside_jpmorgan_pct"] > 170.0
