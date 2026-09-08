"""
Unit tests for Chapter 21 Financial Auditor Script:
CLO Waterfall, Gatheral SVI, Stoikov Micro-Price, TSRV, Beneish M-Score, Multi-Curve FRA, and Fama-MacBeth Shanken.
"""

import math
import numpy as np
import pytest
from pathlib import Path
import sys

# Ensure scripts directory is in path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from clo_svi_stoikov_beneish_multicurve import (
    clo_waterfall_simulation,
    svi_raw,
    svi_arbitrage_check,
    calculate_micro_price,
    two_scale_realized_volatility,
    calculate_beneish_m_score,
    multi_curve_fra_swap,
    fama_macbeth_shanken
)


# =====================================================================
# 1. CLO Waterfall Tests
# =====================================================================

def test_clo_waterfall_normal_passing():
    res = clo_waterfall_simulation(
        collateral_par=100.0,
        senior_debt_par=65.0,
        mezz_debt_par=25.0,
        equity_par=10.0,
        gross_loan_spread_bps=380.0,
        senior_coupon_bps=130.0,
        mezz_coupon_bps=350.0,
        default_rate_annual=0.01,
        recovery_rate=0.75,
        senior_oc_trigger=1.25
    )
    assert res["senior_oc_pass"] is True
    assert res["senior_ic_pass"] is True
    assert res["deleveraged_amount"] == 0.0
    assert res["equity_cash_flow"] > 0.0
    assert res["equity_yield_pct"] > 10.0


def test_clo_waterfall_cash_diversion_failure():
    # High defaults cause OC failure -> triggers cash diversion
    res = clo_waterfall_simulation(
        collateral_par=100.0,
        senior_debt_par=75.0,
        mezz_debt_par=15.0,
        equity_par=10.0,
        gross_loan_spread_bps=350.0,
        senior_coupon_bps=140.0,
        mezz_coupon_bps=350.0,
        default_rate_annual=0.15,
        recovery_rate=0.40,
        senior_oc_trigger=1.25
    )
    assert res["senior_oc_pass"] is False
    assert res["deleveraged_amount"] > 0.0
    assert res["paid_mezz_int"] == 0.0
    assert res["equity_cash_flow"] == 0.0
    assert res["senior_debt_par_end"] < 75.0


# =====================================================================
# 2. Gatheral SVI Arbitrage Check Tests
# =====================================================================

def test_gatheral_svi_arbitrage_free():
    k_grid = np.linspace(-0.4, 0.4, 100)
    # Typical well-behaved SVI params
    a, b, rho, m, sigma = 0.04, 0.15, -0.6, 0.0, 0.1
    res = svi_arbitrage_check(k_grid, a, b, rho, m, sigma)
    assert res["butterfly_free"] is True
    assert res["lee_satisfied"] is True
    assert res["arbitrage_free"] is True
    assert res["left_wing_slope"] < 0.0
    assert res["right_wing_slope"] > 0.0


def test_gatheral_svi_invalid_params():
    k_grid = np.linspace(-0.2, 0.2, 50)
    with pytest.raises(ValueError):
        svi_arbitrage_check(k_grid, a=0.04, b=-0.1, rho=-0.5, m=0.0, sigma=0.1)


# =====================================================================
# 3. Sasha Stoikov Micro-Price & TSRV Tests
# =====================================================================

def test_stoikov_micro_price():
    # Heavy bid volume should pull micro price towards ask
    res = calculate_micro_price(p_bid=100.0, p_ask=100.10, v_bid=9000.0, v_ask=1000.0)
    assert res["mid_price"] == 100.05
    assert res["order_book_imbalance"] == 0.80
    assert res["micro_price"] > res["mid_price"]
    assert res["direction_bias"] == "UP"


def test_two_scale_realized_volatility():
    np.random.seed(42)
    # 500 high-frequency price points with Brownian motion + iid noise
    true_innovations = np.random.normal(0, 0.01, 500)
    true_price = 100.0 + np.cumsum(true_innovations)
    noise = np.random.normal(0, 0.005, 500)
    observed_price = true_price + noise

    tsrv = two_scale_realized_volatility(observed_price, K=5)
    assert tsrv["rv_fast"] > tsrv["rv_slow"]  # Fast RV is blown up by noise
    assert tsrv["tsrv_variance"] >= 0.0
    assert tsrv["tsrv_annual_vol"] > 0.0


# =====================================================================
# 4. Messod Beneish 8-Variable M-Score Tests
# =====================================================================

def test_beneish_clean_company():
    res = calculate_beneish_m_score(
        dsri=1.02, gmi=1.01, aqi=1.00, sgi=1.04,
        depi=1.01, sgai=1.00, lvgi=1.02, tata=0.02
    )
    assert res["m_score"] < -1.78
    assert res["is_manipulator"] is False
    assert res["risk_level"] == "LOW_RISK_CLEAN"
    assert len(res["red_flags"]) == 0


def test_beneish_fraud_manipulator():
    res = calculate_beneish_m_score(
        dsri=1.45, gmi=1.30, aqi=1.35, sgi=1.40,
        depi=1.20, sgai=0.90, lvgi=1.35, tata=0.15
    )
    assert res["m_score"] > -1.78
    assert res["is_manipulator"] is True
    assert res["risk_level"] == "HIGH_MANIPULATION_RISK"
    assert len(res["red_flags"]) > 0


# =====================================================================
# 5. Multi-Curve OIS FRA Swap Tests
# =====================================================================

def test_multi_curve_fra_swap():
    forward_rates = [0.045, 0.048, 0.050, 0.052]
    ois_dfs = [0.956, 0.910, 0.865, 0.820]
    tenors = [1.0, 2.0, 3.0, 4.0]

    res = multi_curve_fra_swap(forward_rates, ois_dfs, tenors)
    assert 4.0 < res["par_swap_rate_pct"] < 6.0
    assert res["dv01_per_million"] > 0.0


# =====================================================================
# 6. Fama-MacBeth Shanken Correction Tests
# =====================================================================

def test_fama_macbeth_shanken():
    np.random.seed(42)
    T = 60  # 60 months
    N = 10  # 10 test assets
    K = 2   # 2 risk factors (e.g. Market, Size)

    factor_returns = np.random.normal(0.008, 0.04, size=(T, K))
    true_betas = np.random.uniform(0.5, 1.5, size=(N, K))
    asset_returns = factor_returns @ true_betas.T + np.random.normal(0, 0.02, size=(T, N))

    fm_res = fama_macbeth_shanken(asset_returns, factor_returns)
    assert len(fm_res["lambda_hat"]) == K
    assert fm_res["shanken_scalar"] >= 1.0  # Shanken multiplier must be >= 1.0
    # Shanken standard errors should be strictly greater than or equal to unadjusted FM SE
    for se_fm, se_sh in zip(fm_res["se_fama_macbeth"], fm_res["se_shanken"]):
        assert se_sh >= se_fm