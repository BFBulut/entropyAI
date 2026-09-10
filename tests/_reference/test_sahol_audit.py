"""Automated test suite for Sabancı Holding (SAHOL) Financial Audit & 1-Week Technical Momentum Engine."""

import sys
from pathlib import Path
import pytest

# Ensure scripts directory is importable
scripts_dir = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(scripts_dir))

from audit_sahol import audit_sabanci_holding
from sahol_short_term_momentum import calculate_sahol_1week_outlook


def test_sahol_audit_market_and_deep_discount():
    data = audit_sabanci_holding()

    assert data["company"] == "Hacı Ömer Sabancı Holding A.Ş."
    assert data["ticker"] == "IS:SAHOL"

    market = data["market_data"]
    assert market["stock_price_try"] == 92.50
    assert market["market_cap_try_b"] == 194.30
    assert market["shares_outstanding_m"] == 2100.0
    assert market["pe_trailing"] == 9.65
    assert market["peg_ratio"] == 0.03
    assert market["book_value_per_share"] == 199.60
    assert market["price_to_book"] < 0.50  # 0.46x (Severely undervalued)
    assert market["pb_discount_pct"] > 50.0  # >50% discount to book
    assert market["beta_5y"] == 0.41  # Low beta
    assert market["dividend_uninterrupted_years"] == 24
    assert market["dividend_streak_years"] == 6

    # Targets & Upside
    assert market["fair_value_investingpro_try"] == 101.65
    assert 9.0 < market["fair_value_upside_pct"] < 11.0
    assert market["analyst_consensus_target_try"] == 162.73
    assert market["analyst_target_upside_pct"] > 70.0


def test_sahol_financials_and_q2_surge():
    data = audit_sabanci_holding()
    prof = data["profitability_and_financials"]

    assert prof["revenue_ltm_m"] == 275480.0
    assert prof["operating_profit_ltm_m"] == 90311.0
    assert prof["operating_margin_pct"] > 30.0
    assert prof["net_income_ltm_m"] == 20096.0
    assert prof["eps_diluted_ltm"] == 9.70

    # Q2 2026 massive quarterly contribution
    assert prof["q2_2026_net_income_m"] == 14160.0
    assert prof["q2_2026_eps"] == 6.84


def test_sahol_balance_sheet_and_cash_flow_recovery():
    data = audit_sabanci_holding()
    bs = data["balance_sheet_and_nav"]
    cf = data["cash_flows_and_recovery"]

    assert bs["total_assets_m"] > 4000000.0  # >4 Trillion TRY
    assert bs["total_equity_m"] > 600000.0  # >600 Billion TRY
    assert bs["nav_target_usd_b"] == 20.0
    assert bs["fx_revenue_share_target_pct"] == 30.0

    # Cash flow recovery over last 3 quarters
    assert cf["cfo_last_3_quarters_sum_m"] > 180000.0  # +186.1B TRY


def test_sahol_1week_short_term_momentum_and_verdict():
    outlook = calculate_sahol_1week_outlook()

    assert outlook["current_price_try"] == 92.50
    assert outlook["trading_days"] == 5
    assert outlook["period_volatility_pct"] < 6.0

    # Technicals
    tech = outlook["technicals"]
    assert tech["technical_summary"] == "Strong Buy"
    assert "Buy" in tech["moving_averages"]

    # 1-Week Verdict
    res = outlook["outlook_1week"]
    assert "YUKARI" in res["expected_direction"]
    assert res["upward_probability_pct"] > 50.0  # Statistically biased upward
    assert res["touch_resistance_prob_pct"] > 40.0
    assert res["primary_price_target_try"] == 95.50
    assert res["critical_stop_support_try"] == 91.20
