"""Automated test suite for Enerjisa Enerji AS (ENJSA) Financial Audit Engine."""

import sys
from pathlib import Path
import pytest

# Ensure scripts path is importable
scripts_dir = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(scripts_dir))

from audit_enjsa import audit_enerjisa


def test_enerjisa_audit_structure_and_integrity():
    data = audit_enerjisa()

    assert data["company"] == "Enerjisa Enerji A.Ş."
    assert data["ticker"] == "IS:ENJSA"

    market = data["market_data"]
    assert market["stock_price_try"] == 113.20
    assert market["market_cap_try_b"] == 133.70
    assert market["dividend_yield_pct"] == 4.49
    assert market["dividend_streak_years"] == 9

    prof = data["profitability"]
    assert prof["revenue_ltm_try_b"] == 236.40
    assert prof["ebitda_try_b"] == 44.11
    assert 6.38 <= prof["net_income_ltm_try_b"] <= 6.41
    assert prof["operating_margin_pct"] > 16.0
    assert prof["q2_26_net_income_growth_yoy_pct"] > 200.0

    cf = data["cash_flow_quality"]
    assert cf["cfo_try_b"] == 43.94
    assert cf["cfo_to_ebitda_conversion_pct"] > 99.0
    # Sloan accrual should be strongly negative, indicating superior earnings quality
    assert cf["sloan_accrual_ratio"] < -0.10

    solvency = data["balance_sheet_and_solvency"]
    assert solvency["current_ratio"] < 1.0  # Demonstrating negative working capital
    assert solvency["net_working_capital_try_b"] < 0
    assert solvency["total_debt_try_b"] == 94.03

    forensics = data["forensic_scores"]
    assert 2.0 < forensics["altman_z_score"] < 2.5
    assert "Grey Zone" in forensics["altman_zone"]

    val = data["valuation_multiples"]
    assert val["pe_ltm"] > 20.0
    assert val["pe_forward_fy26_consensus"] == 11.0
    assert val["upside_avg_pct"] > 20.0
