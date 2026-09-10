#!/usr/bin/env python3
"""
Cheyette Quasi-Gaussian HJM Interest Rate Model,
Leland & Toft (1996) Endogenous Default Barrier & Capital Structure,
Bouchaud (2004) Propagator Model & Transient Market Impact (Gatheral No-Arbitrage),
Contingent Convertible (CoCo) Bonds & AT1 Write-Down Mechanics,
Betting Against Beta (BAB) Factor - Frazzini & Pedersen (2014), and
Rough Bergomi (rBergomi) Model & Volterra Fractional Volatility Skew.

Chapter 22 of Financial Auditor engine.
"""

import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# =====================================================================
# 1. Cheyette Quasi-Gaussian HJM Interest Rate Model
# =====================================================================

def cheyette_discount_bond(
    t: float,
    T: float,
    x_t: float,
    y_t: float,
    kappa: float,
    p0_t: float,
    p0_T: float
) -> Dict[str, float]:
    """
    Calculates zero-coupon bond price P(t, T) and yield under the 1-factor Cheyette model.
    In the Cheyette separable volatility framework:
        sigma(t, T) = sigma(t) * exp(-kappa * (T - t))
    The discount factor reconstitution is given by:
        P(t, T) = (P(0, T) / P(0, t)) * exp(-G(t, T)*x_t - 0.5 * G(t, T)^2 * y_t)
    where G(t, T) = (1 - exp(-kappa * (T - t))) / kappa.
    """
    if T < t:
        raise ValueError("Maturity T cannot be earlier than current time t.")
    if p0_t <= 0.0 or p0_T <= 0.0:
        raise ValueError("Initial discount factors P(0, t) and P(0, T) must be strictly positive.")
    if kappa <= 0.0:
        raise ValueError("Mean reversion speed kappa must be strictly positive.")

    tau = T - t
    if tau == 0.0:
        return {
            "bond_price": 1.0,
            "zero_yield": 0.0,
            "g_factor": 0.0,
            "drift_adjustment": 0.0
        }

    g_factor = (1.0 - math.exp(-kappa * tau)) / kappa
    drift_adjustment = -0.5 * (g_factor ** 2) * y_t
    exponent = -g_factor * x_t + drift_adjustment
    bond_price = (p0_T / p0_t) * math.exp(exponent)
    zero_yield = -math.log(max(1e-12, bond_price)) / tau

    return {
        "bond_price": bond_price,
        "zero_yield": zero_yield,
        "g_factor": g_factor,
        "drift_adjustment": drift_adjustment
    }


def cheyette_deterministic_y(kappa: float, sigma: float, t: float) -> float:
    """
    Computes the deterministic state variable y_t for constant sigma:
        y_t = (sigma^2 / (2 * kappa)) * (1 - exp(-2 * kappa * t))
    """
    if kappa <= 0.0 or sigma < 0.0 or t < 0.0:
        raise ValueError("kappa and sigma must be positive, and t >= 0.")
    if t == 0.0:
        return 0.0
    return (sigma ** 2 / (2.0 * kappa)) * (1.0 - math.exp(-2.0 * kappa * t))


# =====================================================================
# 2. Leland & Toft (1996) Endogenous Default Barrier & Capital Structure
# =====================================================================

def leland_toft_credit_structure(
    firm_value: float,
    coupon: float,
    r: float,
    delta: float,
    sigma_v: float,
    tax_rate: float = 0.25,
    bankruptcy_cost_alpha: float = 0.30
) -> Dict[str, Any]:
    """
    Computes endogenous default barrier V_B*, firm equity, debt value, and credit spread
    under Leland & Toft (1996) / Leland (1994) structural credit model.
    """
    if firm_value <= 0.0 or coupon <= 0.0 or r <= 0.0 or sigma_v <= 0.0:
        raise ValueError("Firm value, coupon, r, and sigma_v must be strictly positive.")
    if not (0.0 <= tax_rate <= 0.60):
        raise ValueError("Tax rate must be between 0.0 and 0.60.")
    if not (0.0 <= bankruptcy_cost_alpha <= 1.0):
        raise ValueError("Bankruptcy cost fraction alpha must be between 0.0 and 1.0.")

    var_v = sigma_v ** 2
    drift = r - delta - 0.5 * var_v
    discriminant = (drift ** 2) + 2.0 * r * var_v
    if discriminant < 0:
        raise ValueError("Discriminant in characteristic equation is negative.")
    
    # Positive root gamma determining first passage probability: (V_B / V)^gamma
    gamma = (drift + math.sqrt(discriminant)) / var_v

    # Smooth-pasting condition for endogenous default barrier:
    # V_B* = (gamma / (1 + gamma)) * ((1 - tax_rate) * coupon / r)
    unlevered_perpetuity = (1.0 - tax_rate) * coupon / r
    vb_star = (gamma / (1.0 + gamma)) * unlevered_perpetuity

    # Bankruptcy discount factor p_B
    if firm_value <= vb_star:
        p_b = 1.0
        is_in_default = True
    else:
        p_b = (vb_star / firm_value) ** gamma
        is_in_default = False

    # Tax shield value: (tau * C / r) * (1 - p_B)
    tax_shield = (tax_rate * coupon / r) * (1.0 - p_b)

    # Expected bankruptcy costs: alpha * V_B * p_B
    bankruptcy_costs = bankruptcy_cost_alpha * vb_star * p_b

    # Total Enterprise Value
    enterprise_value = firm_value + tax_shield - bankruptcy_costs

    # Debt Value: (C / r) * (1 - p_B) + (1 - alpha) * V_B * p_B
    debt_value = (coupon / r) * (1.0 - p_b) + (1.0 - bankruptcy_cost_alpha) * vb_star * p_b

    # Equity Value: enterprise_value - debt_value
    equity_value = max(0.0, enterprise_value - debt_value)

    # Debt yield and credit spread
    debt_yield = coupon / debt_value if debt_value > 0 else 0.0
    credit_spread_bps = max(0.0, (debt_yield - r) * 10000.0)
    leverage_ratio = debt_value / enterprise_value if enterprise_value > 0 else 0.0

    return {
        "endogenous_default_barrier": vb_star,
        "gamma_exponent": gamma,
        "first_passage_prob_discount": p_b,
        "enterprise_value": enterprise_value,
        "debt_value": debt_value,
        "equity_value": equity_value,
        "tax_shield": tax_shield,
        "bankruptcy_costs": bankruptcy_costs,
        "debt_yield_pct": debt_yield * 100.0,
        "credit_spread_bps": credit_spread_bps,
        "leverage_ratio": leverage_ratio,
        "is_in_default": is_in_default
    }


# =====================================================================
# 3. Bouchaud (2004) Propagator Model & Transient Market Impact
# =====================================================================

def bouchaud_propagator_kernel(tau: float, gamma: float = 0.5, tau0: float = 1.0, gamma_0: float = 1.0) -> float:
    """Power-law propagator kernel G(tau) = gamma_0 / (1 + tau / tau0)^gamma."""
    if tau < 0.0:
        return 0.0
    return gamma_0 / ((1.0 + (tau / tau0)) ** gamma)


def bouchaud_propagator_impact(
    order_schedule: List[float],
    dt: float = 1.0,
    gamma: float = 0.5,
    tau0: float = 1.0,
    gamma_0: float = 1.0,
    p0: float = 100.0
) -> Dict[str, Any]:
    """
    Computes transient market impact trajectory for an order schedule under Bouchaud's propagator model.
    Checks Gatheral (2010) positive-definiteness condition for absence of price manipulation arbitrage.
    """
    if not order_schedule:
        raise ValueError("Order schedule cannot be empty.")
    if dt <= 0.0 or gamma <= 0.0 or tau0 <= 0.0 or gamma_0 <= 0.0:
        raise ValueError("dt, gamma, tau0, and gamma_0 must be strictly positive.")

    n = len(order_schedule)
    price_trajectory = [p0]
    cumulative_impact = [0.0]
    times = [0.0]

    for k in range(1, n + 1):
        # Calculate impact at time t_k = k * dt
        # I(t_k) = sum_{j=0}^{k-1} G((k - j) * dt) * v_j * dt
        impact_k = 0.0
        for j in range(k):
            tau = (k - j) * dt
            kernel_val = bouchaud_propagator_kernel(tau, gamma=gamma, tau0=tau0, gamma_0=gamma_0)
            impact_k += kernel_val * order_schedule[j] * dt
        
        cumulative_impact.append(impact_k)
        price_trajectory.append(p0 + impact_k)
        times.append(k * dt)

    # Check Gatheral No-Dynamic-Arbitrage condition via Toeplitz Kernel Matrix
    # G_mat[i, j] = G(|i - j| * dt)
    kernel_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            tau_dist = abs(i - j) * dt
            kernel_matrix[i, j] = bouchaud_propagator_kernel(tau_dist, gamma=gamma, tau0=tau0, gamma_0=gamma_0)

    eigenvalues = np.linalg.eigvalsh(kernel_matrix)
    min_eigenvalue = float(np.min(eigenvalues))
    is_arbitrage_free = bool(min_eigenvalue > 0.0)

    peak_impact = float(np.max(cumulative_impact))
    residual_impact = float(cumulative_impact[-1])
    total_volume_traded = sum(order_schedule) * dt

    return {
        "is_arbitrage_free": is_arbitrage_free,
        "min_kernel_eigenvalue": min_eigenvalue,
        "peak_impact": peak_impact,
        "residual_impact": residual_impact,
        "total_volume_traded": total_volume_traded,
        "times": times,
        "price_trajectory": price_trajectory,
        "cumulative_impact": cumulative_impact
    }


# =====================================================================
# 4. Contingent Convertible (CoCo) Bonds & AT1 Write-Down Mechanics
# =====================================================================

def coco_at1_absorption_model(
    cet1_ratio: float,
    trigger_ratio: float,
    notional: float,
    share_price: float,
    conversion_floor: float,
    mode: str = "PERMANENT_WRITE_DOWN",
    ponv_triggered: bool = False,
    existing_shares: float = 1000000.0,
    equity_market_cap: float = 30000000.0
) -> Dict[str, Any]:
    """
    Evaluates CoCo / AT1 loss absorption trigger, write-down / equity conversion,
    death-spiral dilution, and Absolute Priority Rule (APR) breach risk.
    Modes:
      - PERMANENT_WRITE_DOWN (Credit Suisse March 2023 style)
      - TEMPORARY_WRITE_DOWN (discretionary recovery allowed)
      - EQUITY_CONVERSION (shares issued at max(share_price, floor))
    """
    if notional <= 0.0 or trigger_ratio <= 0.0 or conversion_floor <= 0.0:
        raise ValueError("Notional, trigger_ratio, and conversion_floor must be strictly positive.")

    mode_normalized = mode.upper().strip()
    valid_modes = {"PERMANENT_WRITE_DOWN", "TEMPORARY_WRITE_DOWN", "EQUITY_CONVERSION"}
    if mode_normalized not in valid_modes:
        raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

    # Trigger activated if CET1 is at or below threshold OR Point of Non-Viability (PONV) is declared
    is_triggered = bool((cet1_ratio <= trigger_ratio) or ponv_triggered)

    post_notional = notional
    write_down_pct = 0.0
    shares_issued = 0.0
    dilution_pct = 0.0
    death_spiral_risk = False
    apr_violation = False

    if is_triggered:
        if mode_normalized == "PERMANENT_WRITE_DOWN":
            post_notional = 0.0
            write_down_pct = 100.0
            # If bondholders are 100% wiped out while equity retains positive market cap,
            # this represents an Absolute Priority Rule (APR) inversion / violation (e.g. Credit Suisse FINMA order).
            if equity_market_cap > 0.0:
                apr_violation = True

        elif mode_normalized == "TEMPORARY_WRITE_DOWN":
            # Typical 50% initial write-down buffer
            write_down_pct = 50.0
            post_notional = notional * (1.0 - (write_down_pct / 100.0))

        elif mode_normalized == "EQUITY_CONVERSION":
            conversion_price = max(share_price, conversion_floor)
            shares_issued = notional / conversion_price
            dilution_pct = (shares_issued / (existing_shares + shares_issued)) * 100.0
            # If share price is below conversion floor, floor protects existing equity from infinite dilution;
            # but if share price is crashing and floor is low, death-spiral shorting accelerates.
            if share_price < conversion_floor * 1.05 or dilution_pct > 40.0:
                death_spiral_risk = True

    return {
        "is_triggered": is_triggered,
        "trigger_cause": "PONV" if ponv_triggered else ("CET1_BREACH" if cet1_ratio <= trigger_ratio else "NONE"),
        "mode": mode_normalized,
        "pre_notional": notional,
        "post_notional": post_notional,
        "write_down_pct": write_down_pct,
        "shares_issued": shares_issued,
        "dilution_pct": dilution_pct,
        "death_spiral_risk": death_spiral_risk,
        "apr_violation": apr_violation
    }


# =====================================================================
# 5. Betting Against Beta (BAB) Factor - Frazzini & Pedersen (2014)
# =====================================================================

def betting_against_beta_factor(
    asset_betas: List[float],
    asset_returns: List[float],
    rf: float = 0.02
) -> Dict[str, Any]:
    """
    Constructs the Betting Against Beta (BAB) factor portfolio from asset betas and returns.
    Implements Frazzini & Pedersen (2014) market-neutral leverage-constrained alpha extraction:
        R_BAB = (1 / beta_L) * (R_L - rf) - (1 / beta_H) * (R_H - rf)
        beta_BAB = (1 / beta_L) * beta_L - (1 / beta_H) * beta_H = 1 - 1 = 0 (Market Neutral).
    """
    if len(asset_betas) != len(asset_returns):
        raise ValueError("asset_betas and asset_returns must have the same length.")
    if len(asset_betas) < 4:
        raise ValueError("At least 4 assets are required to form Low and High Beta portfolios.")

    betas = np.array(asset_betas, dtype=float)
    returns = np.array(asset_returns, dtype=float)

    if np.any(betas <= 0.0):
        raise ValueError("All asset betas must be strictly positive.")

    # Split universe by median beta
    median_beta = float(np.median(betas))
    low_mask = betas <= median_beta
    high_mask = betas > median_beta

    if not np.any(low_mask) or not np.any(high_mask):
        raise ValueError("Could not split assets into low and high beta portfolios.")

    beta_l = float(np.mean(betas[low_mask]))
    beta_h = float(np.mean(betas[high_mask]))

    r_l = float(np.mean(returns[low_mask]))
    r_h = float(np.mean(returns[high_mask]))

    # Leverage multipliers to scale portfolios to beta = 1.0
    k_l = 1.0 / beta_l
    k_h = 1.0 / beta_h

    # Factor return
    excess_l = r_l - rf
    excess_h = r_h - rf
    r_bab = (k_l * excess_l) - (k_h * excess_h)

    # Beta of BAB portfolio is analytically zero
    beta_bab = (k_l * beta_l) - (k_h * beta_h)

    # Leverage gap represents the required borrowing for low-beta assets
    leverage_spread = k_l - k_h

    return {
        "beta_low": beta_l,
        "beta_high": beta_h,
        "return_low_pct": r_l * 100.0,
        "return_high_pct": r_h * 100.0,
        "leverage_multiplier_low": k_l,
        "leverage_multiplier_high": k_h,
        "bab_excess_return_pct": r_bab * 100.0,
        "bab_market_beta": beta_bab,
        "leverage_spread": leverage_spread,
        "is_alpha_positive": bool(r_bab > 0.0)
    }


# =====================================================================
# 6. Rough Bergomi (rBergomi) Model & Volterra Fractional Volatility
# =====================================================================

def rough_bergomi_atm_skew(
    hurst_parameter: float,
    eta: float,
    rho: float,
    maturities: List[float]
) -> Dict[str, Any]:
    """
    Computes theoretical at-the-money (ATM) implied volatility skew for the Rough Bergomi (rBergomi) model
    (Bayer, Friz & Gatheral 2016):
        skew(T) = d(sigma_implied) / d(k) |_{k=0} ~ 0.5 * rho * eta * (sqrt(2*H) / (H + 0.5)) * T^(H - 0.5)
    Demonstrates the power-law explosion of short-term skew (T -> 0) when H < 0.5.
    """
    if not (0.0 < hurst_parameter < 0.50):
        raise ValueError("Hurst parameter H must be in rough regime (0.0, 0.50).")
    if eta <= 0.0:
        raise ValueError("Volatility of volatility eta must be positive.")
    if not (-1.0 <= rho <= 1.0):
        raise ValueError("Correlation rho must be between -1.0 and 1.0.")
    if not maturities:
        raise ValueError("Maturities list cannot be empty.")

    h = hurst_parameter
    power_exponent = h - 0.5  # Negative exponent -> explodes as T -> 0
    constant_factor = 0.5 * rho * eta * (math.sqrt(2.0 * h) / (h + 0.5))

    skews = []
    for t in maturities:
        if t <= 0.0:
            raise ValueError("All maturities must be strictly positive.")
        skew_t = constant_factor * (t ** power_exponent)
        skews.append(float(skew_t))

    # Calculate steepness ratio between shortest and longest maturity
    t_min = min(maturities)
    t_max = max(maturities)
    skew_ratio = (t_min / t_max) ** power_exponent if t_max > 0 else 1.0

    return {
        "hurst_parameter": h,
        "vol_of_vol_eta": eta,
        "correlation_rho": rho,
        "power_law_exponent": power_exponent,
        "constant_factor": constant_factor,
        "maturities": maturities,
        "atm_skews": skews,
        "skew_steepness_ratio": skew_ratio,
        "is_skew_exploding": bool(power_exponent < 0.0)
    }


# =====================================================================
# CLI Driver
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Chapter 22: Cheyette HJM, Leland-Toft, Bouchaud, CoCo AT1, BAB & rBergomi")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Cheyette
    p_cheyette = subparsers.add_parser("cheyette", help="Cheyette Discount Bond & State Variable")
    p_cheyette.add_argument("--t", type=float, default=1.0)
    p_cheyette.add_argument("--maturity", type=float, default=5.0)
    p_cheyette.add_argument("--xt", type=float, default=0.01)
    p_cheyette.add_argument("--kappa", type=float, default=0.08)
    p_cheyette.add_argument("--sigma", type=float, default=0.012)
    p_cheyette.add_argument("--p0-t", type=float, default=0.96)
    p_cheyette.add_argument("--p0-T", type=float, default=0.82)

    # Leland-Toft
    p_leland = subparsers.add_parser("leland", help="Leland & Toft (1996) Endogenous Default Barrier")
    p_leland.add_argument("--firm-value", type=float, default=100.0)
    p_leland.add_argument("--coupon", type=float, default=6.0)
    p_leland.add_argument("--rate", type=float, default=0.05)
    p_leland.add_argument("--delta", type=float, default=0.02)
    p_leland.add_argument("--sigma-v", type=float, default=0.25)
    p_leland.add_argument("--tax-rate", type=float, default=0.25)
    p_leland.add_argument("--alpha", type=float, default=0.30)

    # Bouchaud
    p_bouchaud = subparsers.add_parser("bouchaud", help="Bouchaud Propagator Transient Market Impact")
    p_bouchaud.add_argument("--schedule", type=str, default="10,20,30,20,10,0,0,0")
    p_bouchaud.add_argument("--gamma", type=float, default=0.5)
    p_bouchaud.add_argument("--dt", type=float, default=1.0)

    # CoCo AT1
    p_coco = subparsers.add_parser("coco", help="CoCo AT1 Loss Absorption & Write-Down")
    p_coco.add_argument("--cet1", type=float, default=6.5)
    p_coco.add_argument("--trigger", type=float, default=7.0)
    p_coco.add_argument("--notional", type=float, default=1000000.0)
    p_coco.add_argument("--share-price", type=float, default=12.0)
    p_coco.add_argument("--floor", type=float, default=10.0)
    p_coco.add_argument("--mode", type=str, default="PERMANENT_WRITE_DOWN")
    p_coco.add_argument("--ponv", action="store_true")

    # BAB
    p_bab = subparsers.add_parser("bab", help="Betting Against Beta Factor (Frazzini & Pedersen 2014)")
    p_bab.add_argument("--betas", type=str, default="0.6,0.8,1.2,1.6")
    p_bab.add_argument("--returns", type=str, default="0.08,0.09,0.11,0.13")
    p_bab.add_argument("--rf", type=float, default=0.02)

    # rBergomi
    p_bergomi = subparsers.add_parser("rbergomi", help="Rough Bergomi ATM Volatility Skew")
    p_bergomi.add_argument("--hurst", type=float, default=0.10)
    p_bergomi.add_argument("--eta", type=float, default=1.9)
    p_bergomi.add_argument("--rho", type=float, default=-0.75)
    p_bergomi.add_argument("--maturities", type=str, default="0.02,0.08,0.25,1.0")

    args = parser.parse_args()

    if args.command == "cheyette":
        yt = cheyette_deterministic_y(args.kappa, args.sigma, args.t)
        res = cheyette_discount_bond(args.t, args.maturity, args.xt, yt, args.kappa, args.p0_t, args.p0_T)
        res["yt"] = yt
        print(json.dumps(res, indent=2))

    elif args.command == "leland":
        res = leland_toft_credit_structure(args.firm_value, args.coupon, args.rate, args.delta, args.sigma_v, args.tax_rate, args.alpha)
        print(json.dumps(res, indent=2))

    elif args.command == "bouchaud":
        sched = [float(x.strip()) for x in args.schedule.split(",")]
        res = bouchaud_propagator_impact(sched, dt=args.dt, gamma=args.gamma)
        print(json.dumps(res, indent=2))

    elif args.command == "coco":
        res = coco_at1_absorption_model(args.cet1, args.trigger, args.notional, args.share_price, args.floor, mode=args.mode, ponv_triggered=args.ponv)
        print(json.dumps(res, indent=2))

    elif args.command == "bab":
        betas = [float(x.strip()) for x in args.betas.split(",")]
        returns = [float(x.strip()) for x in args.returns.split(",")]
        res = betting_against_beta_factor(betas, returns, rf=args.rf)
        print(json.dumps(res, indent=2))

    elif args.command == "rbergomi":
        mats = [float(x.strip()) for x in args.maturities.split(",")]
        res = rough_bergomi_atm_skew(args.hurst, args.eta, args.rho, mats)
        print(json.dumps(res, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
