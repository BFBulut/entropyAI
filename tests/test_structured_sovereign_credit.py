"""Automated pytest test suite for Structured Credit, Sovereign Debt and HFT Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from structured_sovereign_credit import (
    calculate_cds_implied_default_prob,
    calculate_avellaneda_stoikov_reservation_price,
    calculate_sovereign_snowball_primary_balance,
    calculate_clo_overcollateralization_test
)


def test_cds_implied_default_prob():
    # CDS spread = 300 bps (0.03), Recovery = 40% (0.40)
    # PD = 0.03 / (1 - 0.40) = 0.03 / 0.60 = 5.0%
    res = calculate_cds_implied_default_prob(cds_spread_bps=300.0, recovery_rate_pct=40.0)
    assert res["implied_annual_default_prob_pct"] == 5.0
    assert "Orta / Spekülatif" in res["credit_risk_tier"]
    assert res["5yr_cumulative_survival_prob_pct"] > 70.0

    # High distress CDS: 900 bps
    distress_res = calculate_cds_implied_default_prob(cds_spread_bps=900.0, recovery_rate_pct=40.0)
    assert distress_res["implied_annual_default_prob_pct"] == 15.0
    assert "Yüksek Temerrüt" in distress_res["credit_risk_tier"]

    # Invalid input
    err = calculate_cds_implied_default_prob(300, 100)
    assert "error" in err


def test_avellaneda_stoikov_reservation_price():
    # Mid price = 100, inventory q = +50 (long), gamma = 0.1, sigma = 0.02, T-t = 1
    # skew = 50 * 0.1 * (0.0004) * 1 = 0.002
    # reservation price = 100 - 0.002 = 99.998
    res = calculate_avellaneda_stoikov_reservation_price(
        mid_price=100.0,
        inventory_q=50.0,
        risk_aversion_gamma=0.1,
        volatility_sigma=0.02,
        time_to_close=1.0
    )
    assert res["mid_price"] == 100.0
    assert res["reservation_price"] < 100.0
    assert "Fiyat Aşağı Kaydırıldı" in res["quoting_bias"]

    # Short inventory q = -50
    short_res = calculate_avellaneda_stoikov_reservation_price(
        mid_price=100.0,
        inventory_q=-50.0,
        risk_aversion_gamma=0.1,
        volatility_sigma=0.02,
        time_to_close=1.0
    )
    assert short_res["reservation_price"] > 100.0
    assert "Fiyat Yukarı Kaydırıldı" in short_res["quoting_bias"]

    # Invalid
    err = calculate_avellaneda_stoikov_reservation_price(0, 10)
    assert "error" in err


def test_sovereign_snowball_primary_balance():
    # Snowball active: r = 5.0%, g = 2.0%, Debt/GDP = 80%
    # (r - g) / (1 + g) = (0.05 - 0.02) / 1.02 = 0.03 / 1.02 = 0.02941
    # pb* = 0.02941 * 0.80 = 0.02353 = 2.35% of GDP
    res = calculate_sovereign_snowball_primary_balance(
        real_interest_rate_pct=5.0,
        real_gdp_growth_pct=2.0,
        debt_to_gdp_pct=80.0
    )
    assert res["required_primary_surplus_pct_to_stabilize"] == 2.35
    assert "Kartopu Etkisi Aktif" in res["dynamics_regime"]

    # Favorable growth: g = 4.0%, r = 2.0%
    fav_res = calculate_sovereign_snowball_primary_balance(
        real_interest_rate_pct=2.0,
        real_gdp_growth_pct=4.0,
        debt_to_gdp_pct=60.0
    )
    assert fav_res["required_primary_surplus_pct_to_stabilize"] < 0
    assert "Büyüme Borcu Eritiyor" in fav_res["dynamics_regime"]


def test_clo_overcollateralization_test():
    # Collateral = 500M, Senior Debt = 400M -> Actual OC = 125%
    # Required threshold = 120% -> Test Passed
    res = calculate_clo_overcollateralization_test(
        collateral_par_value=500.0,
        senior_debt_outstanding=400.0,
        required_oc_threshold_pct=120.0
    )
    assert res["actual_oc_ratio_pct"] == 125.0
    assert res["test_passed"] is True
    assert "TEST BAŞARILI" in res["waterfall_status"]

    # Failed test: Collateral suffered defaults down to 440M -> Actual OC = 110%
    fail_res = calculate_clo_overcollateralization_test(
        collateral_par_value=440.0,
        senior_debt_outstanding=400.0,
        required_oc_threshold_pct=120.0
    )
    assert fail_res["actual_oc_ratio_pct"] == 110.0
    assert fail_res["test_passed"] is False
    assert "TEST BAŞARISIZ" in fail_res["waterfall_status"]

    # Invalid input
    err = calculate_clo_overcollateralization_test(500, 0)
    assert "error" in err
