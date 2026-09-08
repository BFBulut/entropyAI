"""
Unit tests for Chapter 22 Financial Auditor Script:
Cheyette Quasi-Gaussian HJM, Leland-Toft Endogenous Default, Bouchaud Propagator Market Impact,
CoCo AT1 Write-down & Equity Conversion, Betting Against Beta (BAB), and Rough Bergomi (rBergomi) ATM Skew.
"""

import math
import numpy as np
import pytest
from pathlib import Path
import sys

# Ensure scripts directory is in path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from cheyette_leland_bouchaud_coco_bab_rbergomi import (
    cheyette_discount_bond,
    cheyette_deterministic_y,
    leland_toft_credit_structure,
    bouchaud_propagator_kernel,
    bouchaud_propagator_impact,
    coco_at1_absorption_model,
    betting_against_beta_factor,
    rough_bergomi_atm_skew
)


# =====================================================================
# 1. Cheyette Quasi-Gaussian HJM Model Tests
# =====================================================================

def test_cheyette_deterministic_y():
    kappa = 0.08
    sigma = 0.015
    # At t = 0, y_t must be 0
    assert cheyette_deterministic_y(kappa, sigma, 0.0) == 0.0
    # At t > 0, y_t must be strictly positive
    yt = cheyette_deterministic_y(kappa, sigma, 2.0)
    assert yt > 0.0
    # Long-term limit y_inf = sigma^2 / (2 * kappa)
    y_inf = (sigma ** 2) / (2.0 * kappa)
    yt_long = cheyette_deterministic_y(kappa, sigma, 100.0)
    assert math.isclose(yt_long, y_inf, rel_tol=1e-4)


def test_cheyette_discount_bond():
    kappa = 0.05
    sigma = 0.012
    t = 1.0
    T = 5.0
    yt = cheyette_deterministic_y(kappa, sigma, t)
    res = cheyette_discount_bond(t, T, x_t=0.005, y_t=yt, kappa=kappa, p0_t=0.96, p0_T=0.80)
    
    assert 0.0 < res["bond_price"] < 1.0
    assert res["zero_yield"] > 0.0
    assert res["g_factor"] > 0.0


def test_cheyette_zero_maturity_and_invalid():
    res = cheyette_discount_bond(1.0, 1.0, 0.0, 0.0, kappa=0.05, p0_t=0.95, p0_T=0.95)
    assert res["bond_price"] == 1.0
    assert res["zero_yield"] == 0.0

    with pytest.raises(ValueError):
        cheyette_discount_bond(5.0, 2.0, 0.0, 0.0, kappa=0.05, p0_t=0.95, p0_T=0.95)


# =====================================================================
# 2. Leland & Toft (1996) Endogenous Default Barrier Tests
# =====================================================================

def test_leland_toft_solvent_firm():
    res = leland_toft_credit_structure(
        firm_value=120.0,
        coupon=5.0,
        r=0.05,
        delta=0.02,
        sigma_v=0.20,
        tax_rate=0.25,
        bankruptcy_cost_alpha=0.30
    )
    # Endogenous default barrier V_B* must be strictly positive and below current firm value
    assert 0.0 < res["endogenous_default_barrier"] < 120.0
    assert res["is_in_default"] is False
    assert 0.0 < res["first_passage_prob_discount"] < 1.0
    assert res["debt_value"] > 0.0
    assert res["equity_value"] > 0.0
    assert res["credit_spread_bps"] > 0.0
    assert 0.0 < res["leverage_ratio"] < 1.0


def test_leland_toft_default_scenario():
    # If firm value is below V_B*, firm defaults immediately
    res = leland_toft_credit_structure(
        firm_value=20.0,
        coupon=6.0,
        r=0.05,
        delta=0.02,
        sigma_v=0.25,
        tax_rate=0.25,
        bankruptcy_cost_alpha=0.30
    )
    assert res["is_in_default"] is True
    assert res["first_passage_prob_discount"] == 1.0
    assert res["equity_value"] == 0.0


def test_leland_toft_invalid_params():
    with pytest.raises(ValueError):
        leland_toft_credit_structure(firm_value=-50.0, coupon=5.0, r=0.05, delta=0.02, sigma_v=0.20)


# =====================================================================
# 3. Bouchaud Propagator Market Impact Tests
# =====================================================================

def test_bouchaud_propagator_impact():
    schedule = [10.0, 20.0, 30.0, 20.0, 10.0, 0.0, 0.0]
    res = bouchaud_propagator_impact(schedule, dt=1.0, gamma=0.5, tau0=1.0, gamma_0=1.0, p0=100.0)

    assert res["is_arbitrage_free"] is True
    assert res["min_kernel_eigenvalue"] > 0.0
    assert res["peak_impact"] > 0.0
    # Once orders cease (0.0 volume), impact decays so residual impact < peak impact
    assert res["residual_impact"] < res["peak_impact"]
    assert res["total_volume_traded"] == 90.0


def test_bouchaud_propagator_empty_and_invalid():
    with pytest.raises(ValueError):
        bouchaud_propagator_impact([])
    with pytest.raises(ValueError):
        bouchaud_propagator_impact([10.0], dt=-1.0)


# =====================================================================
# 4. CoCo AT1 Loss Absorption Tests
# =====================================================================

def test_coco_untriggered():
    res = coco_at1_absorption_model(
        cet1_ratio=11.5,
        trigger_ratio=7.0,
        notional=1000000.0,
        share_price=25.0,
        conversion_floor=15.0,
        mode="PERMANENT_WRITE_DOWN"
    )
    assert res["is_triggered"] is False
    assert res["post_notional"] == 1000000.0
    assert res["write_down_pct"] == 0.0
    assert res["apr_violation"] is False


def test_coco_permanent_write_down_credit_suisse_scenario():
    # CET1 breaches trigger, permanent write-down wipes out debt while equity retains market cap
    res = coco_at1_absorption_model(
        cet1_ratio=5.0,
        trigger_ratio=7.0,
        notional=1000000.0,
        share_price=10.0,
        conversion_floor=8.0,
        mode="PERMANENT_WRITE_DOWN",
        equity_market_cap=50000000.0
    )
    assert res["is_triggered"] is True
    assert res["post_notional"] == 0.0
    assert res["write_down_pct"] == 100.0
    # Equity has positive value while AT1 is 100% written down -> APR violation
    assert res["apr_violation"] is True


def test_coco_equity_conversion_death_spiral():
    res = coco_at1_absorption_model(
        cet1_ratio=4.5,
        trigger_ratio=5.125,
        notional=1000000.0,
        share_price=4.0,
        conversion_floor=5.0,
        mode="EQUITY_CONVERSION",
        existing_shares=200000.0
    )
    assert res["is_triggered"] is True
    # Floor protects from infinite dilution: shares = notional / floor = 1,000,000 / 5 = 200,000
    assert res["shares_issued"] == 200000.0
    assert res["dilution_pct"] == 50.0
    assert res["death_spiral_risk"] is True


# =====================================================================
# 5. Betting Against Beta (BAB) Factor Tests
# =====================================================================

def test_betting_against_beta_neutrality():
    betas = [0.5, 0.7, 1.3, 1.8]
    returns = [0.09, 0.10, 0.11, 0.13]
    res = betting_against_beta_factor(betas, returns, rf=0.02)

    assert res["beta_low"] < 1.0
    assert res["beta_high"] > 1.0
    # Portfolio market beta must be strictly zero (market neutral)
    assert abs(res["bab_market_beta"]) < 1e-6
    # Leverage multiplier for low beta > 1 (leveraged)
    assert res["leverage_multiplier_low"] > 1.0
    # Leverage multiplier for high beta < 1 (deleveraged)
    assert res["leverage_multiplier_high"] < 1.0
    assert res["leverage_spread"] > 0.0
    assert res["is_alpha_positive"] is True


def test_betting_against_beta_invalid():
    with pytest.raises(ValueError):
        betting_against_beta_factor([0.8, 1.2], [0.08, 0.12])  # less than 4 assets
    with pytest.raises(ValueError):
        betting_against_beta_factor([0.5, -0.2, 1.2, 1.5], [0.05, 0.06, 0.08, 0.10])  # negative beta


# =====================================================================
# 6. Rough Bergomi ATM Skew Tests
# =====================================================================

def test_rough_bergomi_skew_blowup():
    mats = [0.01, 0.05, 0.25, 1.0]
    res = rough_bergomi_atm_skew(hurst_parameter=0.10, eta=2.0, rho=-0.80, maturities=mats)

    assert res["is_skew_exploding"] is True
    assert res["power_law_exponent"] == -0.40  # H - 0.5 = 0.10 - 0.50 = -0.40
    # Since rho is negative, equity skews must be negative
    for skew in res["atm_skews"]:
        assert skew < 0.0
    # Short maturity skew magnitude must be strictly greater than long maturity skew magnitude
    assert abs(res["atm_skews"][0]) > abs(res["atm_skews"][-1])
    assert res["skew_steepness_ratio"] > 1.0


def test_rough_bergomi_invalid_hurst():
    with pytest.raises(ValueError):
        rough_bergomi_atm_skew(hurst_parameter=0.60, eta=2.0, rho=-0.80, maturities=[0.1, 0.5])
