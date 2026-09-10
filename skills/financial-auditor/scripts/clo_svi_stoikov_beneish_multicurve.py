#!/usr/bin/env python3
"""
CLO Tranche Structure, Gatheral SVI Arbitrage-Free Surface, Sasha Stoikov Micro-Price & TSRV,
Messod Beneish 8-Variable M-Score & Reverse Factoring, Multi-Curve OIS/SOFR Framework, and
Fama-MacBeth 2-Pass Regression with Shanken EIV Correction.

Chapter 21 of Financial Auditor engine.
"""

import math
import numpy as np
from typing import Any, Dict, List, Optional, Tuple


# =====================================================================
# 1. CLO (Collateralized Loan Obligations) Waterfall Simulation
# =====================================================================

def clo_waterfall_simulation(
    collateral_par: float,
    senior_debt_par: float,
    mezz_debt_par: float,
    equity_par: float,
    gross_loan_spread_bps: float,
    senior_coupon_bps: float,
    mezz_coupon_bps: float,
    default_rate_annual: float = 0.02,
    recovery_rate: float = 0.70,
    ccc_bucket_pct: float = 0.05,
    ccc_limit_pct: float = 0.075,
    senior_oc_trigger: float = 1.25,
    senior_ic_trigger: float = 1.15
) -> Dict[str, Any]:
    """
    Simulates a 1-year quarterly or annual CLO cash flow waterfall with OC/IC tests
    and deleveraging (cash diversion) mechanism.
    """
    if collateral_par <= 0 or senior_debt_par <= 0:
        raise ValueError("Collateral and senior debt par must be positive.")

    # 1. Default Loss and Haircut
    defaulted_par = collateral_par * default_rate_annual
    recovered_cash = defaulted_par * recovery_rate
    net_credit_loss = defaulted_par - recovered_cash
    performing_collateral = collateral_par - defaulted_par

    # CCC Haircut if exceeds limit
    ccc_excess = max(0.0, ccc_bucket_pct - ccc_limit_pct)
    haircut_penalty = (ccc_excess * collateral_par) * 0.30  # 30% haircut on excess CCC
    adjusted_collateral_par = (performing_collateral + recovered_cash) - haircut_penalty

    # 2. OC Ratio
    senior_oc_ratio = adjusted_collateral_par / senior_debt_par
    senior_oc_pass = senior_oc_ratio >= senior_oc_trigger

    # 3. Interest Collections
    sofr_base = 0.045  # 4.5% base
    loan_yield = sofr_base + (gross_loan_spread_bps / 10000.0)
    interest_collections = performing_collateral * loan_yield

    # Debt Obligations
    senior_interest = senior_debt_par * (sofr_base + (senior_coupon_bps / 10000.0))
    mezz_interest = mezz_debt_par * (sofr_base + (mezz_coupon_bps / 10000.0))
    total_senior_interest = senior_interest

    senior_ic_ratio = interest_collections / total_senior_interest
    senior_ic_pass = senior_ic_ratio >= senior_ic_trigger

    # 4. Waterfall & Cash Diversion
    cash_pool = interest_collections
    # Pay Senior Interest
    paid_senior_int = min(cash_pool, senior_interest)
    cash_pool -= paid_senior_int

    deleveraged_amount = 0.0
    paid_mezz_int = 0.0
    equity_cash_flow = 0.0

    if not senior_oc_pass or not senior_ic_pass:
        # Cash Diversion / Trapping: divert cash to pay down Senior Par
        deleveraged_amount = cash_pool
        senior_debt_par_end = senior_debt_par - deleveraged_amount
        cash_pool = 0.0
        # Mezzanine and Equity receive zero distributions
        paid_mezz_int = 0.0
        equity_cash_flow = 0.0
    else:
        # Normal flow: pay Mezzanine
        paid_mezz_int = min(cash_pool, mezz_interest)
        cash_pool -= paid_mezz_int
        # Residual cash goes to Equity
        equity_cash_flow = cash_pool
        senior_debt_par_end = senior_debt_par

    equity_yield = (equity_cash_flow / equity_par) * 100.0 if equity_par > 0 else 0.0

    return {
        "senior_oc_ratio": senior_oc_ratio,
        "senior_oc_pass": senior_oc_pass,
        "senior_ic_ratio": senior_ic_ratio,
        "senior_ic_pass": senior_ic_pass,
        "interest_collections": interest_collections,
        "paid_senior_int": paid_senior_int,
        "paid_mezz_int": paid_mezz_int,
        "equity_cash_flow": equity_cash_flow,
        "equity_yield_pct": equity_yield,
        "deleveraged_amount": deleveraged_amount,
        "senior_debt_par_end": senior_debt_par_end,
        "net_credit_loss": net_credit_loss
    }


# =====================================================================
# 2. Jim Gatheral (2004) SVI & Arbitrage-Free Check
# =====================================================================

def svi_raw(k: np.ndarray, a: float, b: float, rho: float, m: float, sigma: float) -> np.ndarray:
    """Jim Gatheral Raw SVI: w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))."""
    return a + b * (rho * (k - m) + np.sqrt((k - m)**2 + sigma**2))


def svi_arbitrage_check(
    k_grid: np.ndarray,
    a: float,
    b: float,
    rho: float,
    m: float,
    sigma: float
) -> Dict[str, Any]:
    """
    Checks butterfly arbitrage (Breeden-Litzenberger g(k) >= 0) and Lee moment conditions.
    """
    if b < 0:
        raise ValueError("Parameter b must be non-negative.")
    if abs(rho) >= 1.0:
        raise ValueError("Parameter rho must be in (-1, 1).")
    if sigma <= 0:
        raise ValueError("Parameter sigma must be strictly positive.")

    w = svi_raw(k_grid, a, b, rho, m, sigma)
    if np.any(w <= 0):
        return {"arbitrage_free": False, "reason": "Negative total variance w(k) <= 0"}

    # Numerical first and second derivatives
    dw = np.gradient(w, k_grid)
    d2w = np.gradient(dw, k_grid)

    # Breeden-Litzenberger risk-neutral density condition g(k)
    term1 = (1.0 - (k_grid * dw) / (2.0 * w))**2
    term2 = (dw**2 / 4.0) * (1.0 / w + 0.25)
    term3 = d2w / 2.0
    g = term1 - term2 + term3

    butterfly_free = bool(np.all(g >= -1e-6))
    min_density = float(np.min(g))

    # Roger Lee moment condition: b*(1 + |rho|) < 2
    lee_value = b * (1.0 + abs(rho))
    lee_satisfied = bool(lee_value < 2.0)

    is_valid = butterfly_free and lee_satisfied

    return {
        "arbitrage_free": is_valid,
        "butterfly_free": butterfly_free,
        "min_density_g": min_density,
        "lee_value": lee_value,
        "lee_satisfied": lee_satisfied,
        "left_wing_slope": b * (rho - 1.0),
        "right_wing_slope": b * (rho + 1.0)
    }


# =====================================================================
# 3. Sasha Stoikov (2018) Micro-Price & TSRV
# =====================================================================

def calculate_micro_price(p_bid: float, p_ask: float, v_bid: float, v_ask: float) -> Dict[str, Any]:
    """
    Sasha Stoikov (2018) Micro-Price based on Order Book Imbalance (OBI).
    """
    if p_ask <= p_bid:
        raise ValueError("Ask price must be strictly greater than bid price.")
    if v_bid <= 0 or v_ask <= 0:
        raise ValueError("Bid and ask volumes must be positive.")

    spread = p_ask - p_bid
    p_mid = (p_bid + p_ask) / 2.0
    obi = (v_bid - v_ask) / (v_bid + v_ask)

    # Micro-price = P_mid + (Spread / 2) * OBI
    micro_price = p_mid + (spread / 2.0) * obi

    return {
        "mid_price": p_mid,
        "spread": spread,
        "order_book_imbalance": obi,
        "micro_price": micro_price,
        "direction_bias": "UP" if obi > 0.05 else ("DOWN" if obi < -0.05 else "NEUTRAL")
    }


def two_scale_realized_volatility(prices: np.ndarray, K: int = 5) -> Dict[str, Any]:
    """
    Zhang, Mykland & Ait-Sahalia (2005) Two-Scale Realized Volatility (TSRV).
    Removes microstructure noise from high-frequency price trajectories.
    """
    N = len(prices)
    if N < 2 * K:
        raise ValueError("Sample size N must be at least 2 * K.")

    # Fast realized variance on all observations
    rv_fast = float(np.sum(np.diff(prices)**2))

    # Slow realized variance averaged across K sub-grids
    sub_rvs = []
    for k in range(K):
        sub_grid = prices[k::K]
        sub_rvs.append(float(np.sum(np.diff(sub_grid)**2)))
    rv_slow = float(np.mean(sub_rvs))

    n_bar = (N - K + 1.0) / float(K)
    tsrv_variance = rv_slow - (n_bar / float(N)) * rv_fast
    tsrv_variance = max(0.0, tsrv_variance)
    tsrv_annual_vol = math.sqrt(tsrv_variance * 252.0) if tsrv_variance > 0 else 0.0

    return {
        "rv_fast": rv_fast,
        "rv_slow": rv_slow,
        "noise_estimate": (rv_fast - rv_slow) / (2.0 * N),
        "tsrv_variance": tsrv_variance,
        "tsrv_annual_vol": tsrv_annual_vol
    }


# =====================================================================
# 4. Messod Beneish (1999) 8-Variable M-Score Model
# =====================================================================

def calculate_beneish_m_score(
    dsri: float,
    gmi: float,
    aqi: float,
    sgi: float,
    depi: float,
    sgai: float,
    lvgi: float,
    tata: float
) -> Dict[str, Any]:
    """
    Messod Beneish (1999) 8-Variable M-Score for earnings manipulation detection.
    Threshold: M > -1.78 indicates high probability of accounting manipulation.
    """
    m_score = (
        -4.84
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.037 * tata
        + 0.0327 * lvgi
    )

    is_manipulator = bool(m_score > -1.78)
    risk_level = "HIGH_MANIPULATION_RISK" if is_manipulator else "LOW_RISK_CLEAN"

    # Red flags
    red_flags = []
    if dsri > 1.25:
        red_flags.append("DSRI: Aggressive unearned revenue acceleration.")
    if gmi > 1.20:
        red_flags.append("GMI: Severe gross margin deterioration.")
    if aqi > 1.25:
        red_flags.append("AQI: Capitalization of operating expenses.")
    if tata > 0.08:
        red_flags.append("TATA: Extreme divergence between accruals and cash flows.")

    return {
        "m_score": m_score,
        "is_manipulator": is_manipulator,
        "risk_level": risk_level,
        "red_flags": red_flags
    }


# =====================================================================
# 5. Multi-Curve OIS Discounting & FRA Par Swap Rate
# =====================================================================

def multi_curve_fra_swap(
    forward_rates: List[float],
    ois_discount_factors: List[float],
    tenors_years: List[float]
) -> Dict[str, Any]:
    """
    Calculates fair par swap rate and DV01 using dual-curve framework:
    OIS discount curve for discounting and forward projection curve for floating legs.
    """
    if len(forward_rates) != len(ois_discount_factors) or len(forward_rates) != len(tenors_years):
        raise ValueError("Rate, discount factor and tenor arrays must have equal length.")

    floating_pv = 0.0
    annuity_pv = 0.0

    prev_t = 0.0
    for f_rate, df, t in zip(forward_rates, ois_discount_factors, tenors_years):
        tau = t - prev_t
        floating_pv += tau * f_rate * df
        annuity_pv += tau * df
        prev_t = t

    par_swap_rate = floating_pv / annuity_pv if annuity_pv > 0 else 0.0
    dv01 = annuity_pv * 0.0001  # Dollar value of 1 basis point per 1 unit notional

    return {
        "par_swap_rate_pct": par_swap_rate * 100.0,
        "floating_pv": floating_pv,
        "annuity_pv": annuity_pv,
        "dv01_per_million": dv01 * 1_000_000.0
    }


# =====================================================================
# 6. Fama-MacBeth (1973) 2-Pass Regression with Shanken (1992) Correction
# =====================================================================

def fama_macbeth_shanken(
    asset_returns: np.ndarray,  # Shape: (T, N)
    factor_returns: np.ndarray  # Shape: (T, K)
) -> Dict[str, Any]:
    """
    Fama-MacBeth (1973) 2-pass cross-sectional regression with Jay Shanken (1992)
    Errors-in-Variables (EIV) analytical standard error correction.
    """
    T, N = asset_returns.shape
    T_f, K = factor_returns.shape
    if T != T_f:
        raise ValueError("Time dimensions of asset and factor returns must match.")

    # 1. First Pass: Time-Series Regressions (Estimate Betas for each asset)
    betas = np.zeros((N, K))
    # Design matrix for factors with intercept
    X_ts = np.hstack([np.ones((T, 1)), factor_returns])
    for i in range(N):
        y = asset_returns[:, i]
        b = np.linalg.lstsq(X_ts, y, rcond=None)[0]
        betas[i, :] = b[1:]  # Exclude intercept

    # 2. Second Pass: Cross-Sectional Regressions at each period t
    gamma_series = np.zeros((T, K))
    for t in range(T):
        y_cs = asset_returns[t, :]
        # Regress asset returns on estimated betas (without cross-sectional intercept for zero-beta)
        gamma_t = np.linalg.lstsq(betas, y_cs, rcond=None)[0]
        gamma_series[t, :] = gamma_t

    # Factor Risk Premia lambda
    lambda_hat = np.mean(gamma_series, axis=0)

    # Fama-MacBeth unadjusted covariance
    gamma_diff = gamma_series - lambda_hat
    cov_fm = (gamma_diff.T @ gamma_diff) / (T * (T - 1.0))
    se_fm = np.sqrt(np.diag(cov_fm))
    t_stat_fm = lambda_hat / se_fm

    # Shanken (1992) Correction
    factor_cov = np.cov(factor_returns, rowvar=False)
    if K == 1:
        factor_cov = np.array([[float(factor_cov)]])
    inv_factor_cov = np.linalg.pinv(factor_cov)

    shanken_scalar = float(1.0 + lambda_hat.T @ inv_factor_cov @ lambda_hat)
    cov_shanken = cov_fm * shanken_scalar + (1.0 / T) * factor_cov
    se_shanken = np.sqrt(np.diag(cov_shanken))
    t_stat_shanken = lambda_hat / se_shanken

    return {
        "lambda_hat": lambda_hat.tolist(),
        "se_fama_macbeth": se_fm.tolist(),
        "t_stat_fama_macbeth": t_stat_fm.tolist(),
        "shanken_scalar": shanken_scalar,
        "se_shanken": se_shanken.tolist(),
        "t_stat_shanken": t_stat_shanken.tolist()
    }