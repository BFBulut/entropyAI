"""Automated test suite for ATP Yazılım ve Teknoloji A.Ş. (ATATP) Financial Audit Engine."""

import sys
from pathlib import Path
import pytest

# Ensure scripts path is importable
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from audit_atatp import audit_atatp
from atatp_valuation_and_scenarios import calculate_atatp_scenarios


def test_atatp_audit_market_and_trading():
    data = audit_atatp()

    assert data["ticker"] == "IS:ATATP"
    market = data["market_data"]
    assert market["stock_price_try"] == 293.75
    assert market["market_cap_try_b"] == 27.50
    assert market["pe_current"] == 13.98
    assert market["pe_fwd_fy26"] == 9.80
    assert market["pe_fwd_fy27"] == 5.52
    assert market["pe_fwd_fy28"] == 3.63
    assert market["peg_ratio"] == 1.13
    assert market["ev_ebitda_current"] == 6.39
    assert market["ev_ebitda_fy25"] == 2.96
    assert market["fair_value_estimate_try"] == 387.70
    assert 31.0 < market["upside_to_fair_value_pct"] < 33.0
    assert market["dividend_growth_streak_years"] == 5
    assert market["beta_5y"] == 0.24


def test_atatp_profitability_and_elite_margins():
    data = audit_atatp()
    prof = data["profitability_and_margins"]

    assert prof["revenue_ltm_m"] == 5570.0
    assert prof["gross_profit_ltm_m"] == 4717.9
    assert prof["gross_margin_pct"] > 84.0  # ~84.70%
    assert prof["operating_margin_pct"] > 66.0  # ~66.34%
    assert prof["ebitda_margin_pct"] > 67.0  # ~67.31%
    assert prof["net_margin_pct"] > 35.0  # ~35.35%
    assert prof["net_income_ltm_m"] == 1969.0
    assert prof["eps_diluted_ltm"] == 21.00
    assert prof["revenue_forecast_growth_pct"] > 77.0  # ~77.74% to 9.9B


def test_atatp_solvency_and_fortress_balance_sheet():
    data = audit_atatp()
    bs = data["balance_sheet_and_solvency"]

    assert bs["total_equity_m"] == 10284.0
    assert bs["total_debt_m"] == 70.6
    assert bs["current_ratio"] > 2.0  # 2.13
    assert bs["debt_to_equity_pct"] < 1.0  # Only ~0.69%
    assert bs["debt_to_assets_pct"] < 1.0  # Only ~0.64%
    assert bs["is_net_cash_positive"] is True
    assert bs["altman_z_double_prime"] > 5.0  # Deep inside the safe zone (benchmark is 2.60)
    assert bs["solvency_verdict"] == "Rock Solid - Zero Default Risk"


def test_atatp_forensic_cash_flow_and_sloan_accruals():
    data = audit_atatp()
    cf = data["forensic_cash_flow_and_accruals"]

    assert cf["cfo_ltm_m"] == -1618.0
    assert cf["cfo_q3_2025_outlier_m"] == -1691.0
    assert cf["cfo_last_3_quarters_sum_m"] == 825.6  # Normalized positive cash generation
    assert cf["cfo_annualized_normalized_m"] > 1100.0
    assert cf["sloan_accrual_reported"] > 0.30  # Apparent warning due to Q3 2025
    assert cf["sloan_accrual_normalized"] < 0.10  # Normalized quality restores health


def test_atatp_saas_metrics_and_rule_of_40():
    data = audit_atatp()
    saas = data["saas_and_business_model"]

    assert saas["recurring_revenue_pct"] >= 50.0
    assert saas["international_revenue_pct"] == 26.0
    assert saas["foreign_currency_revenue_pct"] == 46.0
    assert saas["rule_of_40_score"] > 140.0  # Exceptional SaaS benchmark score
    assert "Tradesoft" in saas["key_brands"]
    assert "Zenia" in saas["key_brands"]
    assert "AiX" in saas["key_brands"]


def test_atatp_valuation_scenarios():
    scenarios = calculate_atatp_scenarios()

    assert scenarios["stock_price_try"] == 293.75
    base = scenarios["scenarios"]["base"]
    assert base["target_price_try"] == 387.70
    assert 31.0 < base["return_pct"] < 33.0

    bull = scenarios["scenarios"]["bull"]
    assert bull["target_price_try"] > 500.0
    assert bull["return_pct"] > 80.0

    catalyst = scenarios["cfo_rolloff_catalyst"]
    assert catalyst["dropped_quarter_cfo_m"] == -1691.0
    assert catalyst["projected_ltm_cfo_after_q3_m"] > 1000.0
    assert catalyst["projected_fcf_yield_pct"] > 3.5

    matrix = scenarios["valuation_matrix"]
    assert len(matrix) > 0
    # At WACC 20% and TG 8%, value must exceed current market price
    base_case_matrix = [m for m in matrix if m["wacc_pct"] == 20.0 and m["terminal_growth_pct"] == 8.0]
    assert len(base_case_matrix) == 1
    assert base_case_matrix[0]["implied_price_try"] > 260.0
