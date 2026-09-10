"""
Chapter 23 Financial Engineering & Quantitative Auditor Engine:
1. Marchenko-Pastur (RMT) & Ledoit-Wolf Shrinkage Denoised Covariance Portfolio Optimization
2. Synthetic CDO, David Li Copula Collapse, Base Correlation Curve & Tranche Loss Mechanics
3. Eurodollar Offshore Plumbing, Hidden FX Swap Debt & Collateral Velocity / Chain Contraction
4. Uniswap v4 Hook Dynamics, JIT Liquidity MEV Extraction & CoW Discrete Batch Auctions
5. Cartea-Jaimungal (2014) HJB Optimal Market Making Spreads & Maker-Taker Rebate Arbitrage
6. Up-C IPO Architecture, Tax Receivable Agreements (TRA), De-SPAC Dilution & IRC Sec 382 NOL Limit
"""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# =====================================================================
# 1. Marchenko-Pastur (RMT) & Ledoit-Wolf Covariance De-noising
# =====================================================================

def marchenko_pastur_bounds(q: float, sigma_sq: float = 1.0) -> Tuple[float, float]:
    """
    Calculate the lower and upper analytical eigenvalue bounds of the Marchenko-Pastur (1967) distribution.
    q = N / T (number of assets / number of observations).
    lambda_minus = sigma^2 * (1 - sqrt(q))^2
    lambda_plus  = sigma^2 * (1 + sqrt(q))^2
    """
    if q <= 0.0 or sigma_sq <= 0.0:
        raise ValueError("q and sigma_sq must be strictly positive.")
    
    lambda_minus = sigma_sq * ((1.0 - math.sqrt(q)) ** 2)
    lambda_plus = sigma_sq * ((1.0 + math.sqrt(q)) ** 2)
    return float(lambda_minus), float(lambda_plus)


def rmt_denoise_covariance(cov_matrix: np.ndarray, q: float, method: str = "clipping") -> np.ndarray:
    """
    De-noise an empirical covariance matrix using Random Matrix Theory (RMT).
    Eigenvalues falling below lambda_plus are pure random noise.
    In 'clipping' method: noise eigenvalues are replaced by their average to preserve the matrix trace (total variance).
    """
    cov = np.asarray(cov_matrix, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError("cov_matrix must be a square 2D array.")
    
    n = cov.shape[0]
    # Symmetrize
    cov = 0.5 * (cov + cov.T)
    
    # Calculate correlation matrix and variances
    std_devs = np.sqrt(np.diag(cov))
    # Replace zero std with 1 to prevent div by zero
    std_devs[std_devs <= 0] = 1.0
    outer_std = np.outer(std_devs, std_devs)
    corr = cov / outer_std
    
    # Eigen-decomposition
    eigenvals, eigenvecs = np.linalg.eigh(corr)
    # Sort descending
    idx = np.argsort(eigenvals)[::-1]
    eigenvals = eigenvals[idx]
    eigenvecs = eigenvecs[:, idx]
    
    _, lambda_plus = marchenko_pastur_bounds(q=q, sigma_sq=1.0)
    
    # Filter signal vs noise
    noise_mask = eigenvals <= lambda_plus
    
    denoised_eigenvals = eigenvals.copy()
    if np.any(noise_mask):
        # Preserve trace of noise subspace
        noise_mean = np.mean(eigenvals[noise_mask])
        denoised_eigenvals[noise_mask] = max(0.0, noise_mean)
    
    # Reconstruct denoised correlation matrix
    denoised_corr = eigenvecs @ np.diag(denoised_eigenvals) @ eigenvecs.T
    # Normalize diagonal to 1.0
    d_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(1e-8, np.diag(denoised_corr))))
    denoised_corr = d_inv_sqrt @ denoised_corr @ d_inv_sqrt
    np.fill_diagonal(denoised_corr, 1.0)
    
    # Reconstruct covariance matrix
    denoised_cov = denoised_corr * outer_std
    return 0.5 * (denoised_cov + denoised_cov.T)


def ledoit_wolf_shrinkage_constant_corr(returns: np.ndarray) -> Dict[str, Any]:
    """
    Analytical Ledoit-Wolf (2004) optimal linear shrinkage towards constant correlation target:
    Sigma* = alpha * F + (1 - alpha) * S
    where S is the sample covariance and F is the structured constant correlation target.
    """
    X = np.asarray(returns, dtype=float)
    if X.ndim != 2:
        raise ValueError("returns must be a 2D array of shape (T, N).")
    
    T, N = X.shape
    
    # Demean returns
    X = X - np.mean(X, axis=0)
    
    # Sample covariance S
    S = (X.T @ X) / float(T)
    var = np.diag(S)
    sqrt_var = np.sqrt(np.maximum(1e-12, var))
    outer_sqrt = np.outer(sqrt_var, sqrt_var)
    
    # Sample correlation R
    R = S / outer_sqrt
    # Average off-diagonal correlation
    r_bar = float((np.sum(R) - N) / max(1.0, (N * (N - 1))))
    
    # Target matrix F
    F = r_bar * outer_sqrt
    np.fill_diagonal(F, var)
    
    # Pi-hat (sum of asymptotic variances of sample covariance elements)
    X2 = X ** 2
    phi_mat = (X2.T @ X2) / float(T) - (S ** 2)
    pi_hat = float(np.sum(phi_mat))
    
    # Gamma-hat: Frobenius distance ||S - F||^2
    gamma_hat = float(np.sum((S - F) ** 2))
    
    # Rho-hat: cross-covariance terms
    term1 = float(np.sum(np.diag(phi_mat)))
    term2 = 0.0
    for i in range(N):
        for j in range(N):
            if i != j:
                term2 += phi_mat[i, j] * (sqrt_var[i] / sqrt_var[j])
    rho_hat = term1 + (r_bar / 2.0) * term2
    
    # Kappa-hat = (pi_hat - rho_hat) / gamma_hat
    kappa_hat = (pi_hat - rho_hat) / max(1e-12, gamma_hat)
    
    # Optimal shrinkage intensity alpha* in [0, 1]
    alpha_star = max(0.0, min(1.0, kappa_hat / float(T)))
    
    # Shrunk covariance matrix
    shrunk_cov = alpha_star * F + (1.0 - alpha_star) * S
    
    return {
        "shrunk_covariance": shrunk_cov,
        "sample_covariance": S,
        "target_constant_correlation": F,
        "optimal_shrinkage_intensity": float(alpha_star),
        "average_correlation": float(r_bar),
        "frobenius_distance_to_target": float(math.sqrt(gamma_hat))
    }


# =====================================================================
# 2. Synthetic CDO, Base Correlation & Tranche Pricing Mechanics
# =====================================================================

def base_correlation_expected_loss(
    attachment: float,
    detachment: float,
    base_corr: float,
    portfolio_hazard: float,
    recovery: float = 0.4,
    maturity: float = 5.0
) -> Dict[str, Any]:
    """
    Calculate the expected loss and loss absorption of a synthetic CDO tranche
    [attachment, detachment] using the Base Correlation methodology.
    base_corr: Base correlation calibrated to [0, detachment].
    """
    if not (0.0 <= attachment < detachment <= 1.0):
        raise ValueError("Invalid tranche attachment/detachment boundaries.")
    if not (0.0 <= base_corr <= 1.0):
        raise ValueError("base_corr must be between 0.0 and 1.0.")
    
    tranche_width = detachment - attachment
    
    # Portfolio cumulative default probability over horizon: PD = 1 - exp(-hazard * maturity)
    portfolio_pd = 1.0 - math.exp(-portfolio_hazard * maturity)
    portfolio_expected_loss = (1.0 - recovery) * portfolio_pd
    
    eff_detachment_loss = min(detachment, portfolio_expected_loss * (1.0 + 0.5 * (1.0 - base_corr)))
    eff_attachment_loss = min(attachment, portfolio_expected_loss * (1.0 + 0.5 * (1.0 - base_corr)))
    
    tranche_dollar_loss = max(0.0, eff_detachment_loss - eff_attachment_loss)
    tranche_loss_pct = min(1.0, tranche_dollar_loss / tranche_width)
    
    # Running spread approximation (bps)
    annuity = (1.0 - math.exp(-0.04 * maturity)) / 0.04  # Assuming 4% discount rate
    running_spread_bps = (tranche_loss_pct / max(1e-4, annuity)) * 10000.0
    
    return {
        "tranche_name": f"[{attachment*100:.1f}% - {detachment*100:.1f}%]",
        "tranche_width": float(tranche_width),
        "portfolio_expected_loss": float(portfolio_expected_loss),
        "tranche_loss_percentage": float(tranche_loss_pct),
        "estimated_running_spread_bps": float(running_spread_bps),
        "subordination": float(attachment)
    }


# =====================================================================
# 3. Eurodollar Offshore Plumbing & Collateral Velocity
# =====================================================================

def eurodollar_collateral_velocity(
    total_pledged_collateral: float,
    primary_collateral: float,
    haircut_k: float = 0.02
) -> Dict[str, Any]:
    """
    Compute Collateral Velocity and Rehypothecation Multiplier in shadow banking / tri-party repo.
    Velocity V = Total Pledged Collateral / Primary Sourced Collateral
    Theoretical multiplier ceiling under uniform haircut k: M = 1 / k
    """
    if primary_collateral <= 0.0 or total_pledged_collateral < primary_collateral:
        raise ValueError("Invalid collateral inputs.")
    if not (0.0 < haircut_k < 1.0):
        raise ValueError("Haircut must be strictly between 0 and 1.")
    
    velocity = total_pledged_collateral / primary_collateral
    theoretical_max_multiplier = 1.0 / haircut_k
    
    # Contraction risk: if haircut widens by delta_k, system liquidity contracts
    contracted_capacity = primary_collateral * (1.0 / min(0.99, (haircut_k * 2.0)))
    liquidity_deficit_shock = max(0.0, (primary_collateral * velocity) - contracted_capacity)
    
    return {
        "observed_collateral_velocity": float(velocity),
        "theoretical_max_velocity": float(theoretical_max_multiplier),
        "current_haircut": float(haircut_k),
        "shock_haircut_doubled": float(haircut_k * 2.0),
        "liquidity_contraction_deficit": float(liquidity_deficit_shock)
    }


# =====================================================================
# 4. Uniswap v4 Hook Dynamics & CoW Batch Auction Clearing
# =====================================================================

def uniswap_v4_jit_mev_profit(
    swap_volume: float,
    normal_lp_liquidity: float,
    jit_liquidity: float,
    fee_tier: float = 0.003,
    gas_cost_usd: float = 35.0
) -> Dict[str, Any]:
    """
    Model Just-In-Time (JIT) Liquidity MEV extraction in concentrated AMMs (v3/v4).
    The searcher injects massive liquidity right before a swap and burns it immediately after.
    """
    if swap_volume <= 0.0 or normal_lp_liquidity <= 0.0 or jit_liquidity < 0.0:
        raise ValueError("Swap volume and liquidity values must be positive.")
    
    total_liquidity = normal_lp_liquidity + jit_liquidity
    total_fee_generated = swap_volume * fee_tier
    
    jit_fee_share = (jit_liquidity / total_liquidity) * total_fee_generated
    passive_lp_fee_share = total_fee_generated - jit_fee_share
    
    net_jit_profit = jit_fee_share - gas_cost_usd
    is_profitable = net_jit_profit > 0.0
    
    return {
        "total_swap_fee_generated": float(total_fee_generated),
        "jit_stolen_fee_share": float(jit_fee_share),
        "passive_lp_retained_fee": float(passive_lp_fee_share),
        "jit_fee_capture_ratio": float(jit_fee_share / max(1e-6, total_fee_generated)),
        "gas_cost_usd": float(gas_cost_usd),
        "net_jit_profit_usd": float(net_jit_profit),
        "is_profitable_attack": bool(is_profitable)
    }


def cow_swap_batch_auction_clearing(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Coincidence of Wants (CoW) discrete-time batch auction clearing engine.
    Match buy and sell orders at a Uniform Clearing Price (P*), eliminating MEV and front-running.
    """
    if not orders:
        return {"matched_volume": 0.0, "clearing_price": 0.0, "unmatched_imbalance": 0.0}
    
    total_buy_volume = sum(o["amount"] for o in orders if o["side"].lower() == "buy")
    total_sell_volume = sum(o["amount"] for o in orders if o["side"].lower() == "sell")
    
    matched_volume = min(total_buy_volume, total_sell_volume)
    imbalance = abs(total_buy_volume - total_sell_volume)
    
    prices = [o["limit_price"] * o["amount"] for o in orders]
    weights = [o["amount"] for o in orders]
    clearing_price = sum(prices) / max(1e-6, sum(weights)) if sum(weights) > 0 else 1.0
    
    surplus_generated = 0.0
    for o in orders:
        if o["side"].lower() == "buy" and o["limit_price"] >= clearing_price:
            surplus_generated += (o["limit_price"] - clearing_price) * min(o["amount"], matched_volume / max(1.0, len(orders)))
        elif o["side"].lower() == "sell" and o["limit_price"] <= clearing_price:
            surplus_generated += (clearing_price - o["limit_price"]) * min(o["amount"], matched_volume / max(1.0, len(orders)))
            
    return {
        "clearing_price": float(clearing_price),
        "matched_volume": float(matched_volume),
        "unmatched_imbalance": float(imbalance),
        "imbalance_side": "buy_heavy" if total_buy_volume > total_sell_volume else "sell_heavy",
        "total_economic_surplus": float(max(0.0, surplus_generated)),
        "mev_risk_eliminated": True
    }


# =====================================================================
# 5. Cartea-Jaimungal (2014) HJB Optimal Market Making
# =====================================================================

def cartea_jaimungal_optimal_spread(
    inventory_q: int,
    gamma: float = 0.01,
    k: float = 1.5,
    A: float = 140.0,
    sigma: float = 0.02
) -> Dict[str, float]:
    """
    Cartea & Jaimungal (2014) closed-form optimal bid and ask spreads for limit order market making.
    delta_a* = ask distance from mid-price
    delta_b* = bid distance from mid-price
    """
    if gamma <= 0.0 or k <= 0.0 or A <= 0.0 or sigma <= 0.0:
        raise ValueError("Market making parameters must be strictly positive.")
    
    sym_component = (1.0 / k) * math.log(1.0 + (k / gamma))
    
    exponent = 1.0 + (gamma / k)
    inner = ((gamma * (sigma ** 2)) / (k * A)) * ((1.0 + (k / gamma)) ** exponent)
    drift_coeff = math.sqrt(max(1e-12, inner))
    
    inventory_adjustment = ((2.0 * inventory_q - 1.0) / 2.0) * drift_coeff
    
    delta_a = sym_component - inventory_adjustment
    delta_b = sym_component + inventory_adjustment
    
    delta_a = max(0.0001, delta_a)
    delta_b = max(0.0001, delta_b)
    total_spread = delta_a + delta_b
    
    return {
        "optimal_ask_distance": float(delta_a),
        "optimal_bid_distance": float(delta_b),
        "total_optimal_spread": float(total_spread),
        "inventory_skew": float(delta_b - delta_a)
    }


# =====================================================================
# 6. Up-C IPO, Tax Receivable Agreements & IRC Section 382
# =====================================================================

def upc_tax_receivable_agreement_value(
    basis_step_up: float,
    tax_rate: float = 0.25,
    tra_share: float = 0.85,
    discount_rate: float = 0.08,
    amortization_years: int = 15
) -> Dict[str, Any]:
    """
    Value the Tax Receivable Agreement (TRA) obligation in an Up-C IPO structure.
    Under IRC Sec 754, basis step-up amortizes straight-line over 15 years.
    """
    if basis_step_up <= 0.0 or tax_rate <= 0.0 or amortization_years <= 0:
        raise ValueError("Invalid financial inputs for Up-C valuation.")
    
    annual_amortization = basis_step_up / float(amortization_years)
    annual_tax_saving = annual_amortization * tax_rate
    annual_tra_payout = annual_tax_saving * tra_share
    annual_corp_benefit = annual_tax_saving * (1.0 - tra_share)
    
    annuity_factor = (1.0 - (1.0 + discount_rate) ** (-amortization_years)) / discount_rate
    tra_present_value = annual_tra_payout * annuity_factor
    corp_present_value = annual_corp_benefit * annuity_factor
    
    return {
        "basis_step_up": float(basis_step_up),
        "annual_tax_shield": float(annual_tax_saving),
        "annual_tra_liability_payout": float(annual_tra_payout),
        "annual_corporate_benefit": float(annual_corp_benefit),
        "tra_liability_present_value": float(tra_present_value),
        "corporate_retained_pv": float(corp_present_value),
        "amortization_schedule_years": amortization_years
    }


def despac_dilution_and_cash_per_share(
    trust_cash: float,
    initial_shares: float,
    redemption_rate: float,
    sponsor_promote_shares: float,
    transaction_expenses: float = 15.0e6
) -> Dict[str, Any]:
    """
    Calculate the dilution trap and depleted cash-per-share in a De-SPAC business combination.
    """
    if not (0.0 <= redemption_rate < 1.0):
        raise ValueError("redemption_rate must be between 0.0 and 1.0 (strictly less than 1.0).")
    if initial_shares <= 0.0:
        raise ValueError("initial_shares must be strictly positive.")
    
    redeemed_shares = initial_shares * redemption_rate
    remaining_public_shares = initial_shares - redeemed_shares
    
    initial_cash_per_share = trust_cash / initial_shares
    redeemed_cash = redeemed_shares * initial_cash_per_share
    
    remaining_trust_cash = trust_cash - redeemed_cash
    net_closing_cash = max(0.0, remaining_trust_cash - transaction_expenses)
    
    total_post_shares = remaining_public_shares + sponsor_promote_shares
    diluted_cash_per_share = net_closing_cash / max(1.0, total_post_shares)
    
    dilution_loss_pct = (initial_cash_per_share - diluted_cash_per_share) / initial_cash_per_share
    
    return {
        "remaining_public_shares": float(remaining_public_shares),
        "sponsor_promote_shares": float(sponsor_promote_shares),
        "total_closing_shares": float(total_post_shares),
        "net_closing_cash": float(net_closing_cash),
        "initial_cash_per_share": float(initial_cash_per_share),
        "diluted_cash_per_share": float(diluted_cash_per_share),
        "dilution_loss_percentage": float(dilution_loss_pct)
    }


def irc_section_382_nol_limitation(
    equity_value: float,
    long_term_tax_exempt_rate: float,
    total_nol: float
) -> Dict[str, Any]:
    """
    IRC Section 382 Net Operating Loss (NOL) limitation upon ownership change (>50% change over 3 years).
    """
    if equity_value <= 0.0 or long_term_tax_exempt_rate <= 0.0 or total_nol < 0.0:
        raise ValueError("Invalid parameters for Section 382 NOL calculation.")
    
    annual_limit = equity_value * long_term_tax_exempt_rate
    years_to_utilize = total_nol / annual_limit if annual_limit > 0 else float("inf")
    
    return {
        "old_equity_value": float(equity_value),
        "federal_rate": float(long_term_tax_exempt_rate),
        "annual_nol_deduction_limit": float(annual_limit),
        "total_available_nol": float(total_nol),
        "years_to_fully_utilize": float(years_to_utilize)
    }
