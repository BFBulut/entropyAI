"""
Unit tests for Chapter 23 Financial Auditor Script:
RMT Covariance De-noising, Ledoit-Wolf Shrinkage, Synthetic CDO Base Correlation,
Eurodollar Collateral Velocity, Uniswap v4 JIT / CoW Batch Auctions,
Cartea-Jaimungal HJB Optimal Market Making, Up-C TRA, De-SPAC Dilution, and IRC Section 382 NOL.
"""

import math
import numpy as np
import pytest
from pathlib import Path
import sys

# Ensure scripts directory is in path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from rmt_base_correlation_eurodollar_cartea_upc import (
    marchenko_pastur_bounds,
    rmt_denoise_covariance,
    ledoit_wolf_shrinkage_constant_corr,
    base_correlation_expected_loss,
    eurodollar_collateral_velocity,
    uniswap_v4_jit_mev_profit,
    cow_swap_batch_auction_clearing,
    cartea_jaimungal_optimal_spread,
    upc_tax_receivable_agreement_value,
    despac_dilution_and_cash_per_share,
    irc_section_382_nol_limitation
)


# =====================================================================
# 1. Marchenko-Pastur (RMT) & Ledoit-Wolf Shrinkage Tests
# =====================================================================

def test_marchenko_pastur_bounds():
    # When N=50, T=200 -> q = 0.25
    q = 0.25
    l_min, l_plus = marchenko_pastur_bounds(q, sigma_sq=1.0)
    
    # (1 - sqrt(0.25))^2 = (1 - 0.5)^2 = 0.25
    assert math.isclose(l_min, 0.25, abs_tol=1e-5)
    # (1 + sqrt(0.25))^2 = (1 + 0.5)^2 = 2.25
    assert math.isclose(l_plus, 2.25, abs_tol=1e-5)
    assert l_min < l_plus

    with pytest.raises(ValueError):
        marchenko_pastur_bounds(q=-0.1)


def test_rmt_denoise_covariance():
    np.random.seed(42)
    # Generate noisy returns for N=5 assets, T=100 observations (q = 0.05)
    N, T = 5, 100
    ret = np.random.randn(T, N)
    sample_cov = np.cov(ret, rowvar=False)
    
    denoised = rmt_denoise_covariance(sample_cov, q=N/T)
    
    # Must be square, symmetric, same dimension
    assert denoised.shape == (N, N)
    assert np.allclose(denoised, denoised.T)
    
    # Eigenvalues must be non-negative (positive semi-definite)
    eigs = np.linalg.eigvalsh(denoised)
    assert np.all(eigs >= -1e-8)


def test_ledoit_wolf_shrinkage_constant_corr():
    np.random.seed(123)
    T, N = 80, 10
    ret = np.random.randn(T, N)
    
    res = ledoit_wolf_shrinkage_constant_corr(ret)
    
    assert "shrunk_covariance" in res
    assert 0.0 <= res["optimal_shrinkage_intensity"] <= 1.0
    assert -1.0 <= res["average_correlation"] <= 1.0
    
    shrunk = res["shrunk_covariance"]
    assert shrunk.shape == (N, N)
    # Check positive definiteness
    eigs = np.linalg.eigvalsh(shrunk)
    assert np.all(eigs > 0.0)


# =====================================================================
# 2. Base Correlation & Synthetic CDO Tranche Tests
# =====================================================================

def test_base_correlation_tranches():
    # Portfolio hazard rate = 0.02 (200 bps flat hazard rate), 5y maturity
    hazard = 0.02
    
    equity_tranche = base_correlation_expected_loss(
        attachment=0.0,
        detachment=0.03,
        base_corr=0.30,
        portfolio_hazard=hazard
    )
    
    senior_tranche = base_correlation_expected_loss(
        attachment=0.07,
        detachment=0.10,
        base_corr=0.75,
        portfolio_hazard=hazard
    )
    
    # Equity tranche should absorb significantly higher loss % than senior
    assert equity_tranche["tranche_loss_percentage"] > senior_tranche["tranche_loss_percentage"]
    assert equity_tranche["estimated_running_spread_bps"] > senior_tranche["estimated_running_spread_bps"]
    assert equity_tranche["subordination"] == 0.0
    assert senior_tranche["subordination"] == 0.07

    with pytest.raises(ValueError):
        base_correlation_expected_loss(attachment=0.10, detachment=0.05, base_corr=0.5, portfolio_hazard=0.02)


# =====================================================================
# 3. Eurodollar Plumbing & Collateral Velocity Tests
# =====================================================================

def test_eurodollar_collateral_velocity():
    primary = 100.0  # 100M primary collateral (e.g. US Treasuries)
    total_pledged = 280.0  # 280M total transaction volume via rehypothecation
    haircut = 0.02  # 2% standard repo haircut
    
    res = eurodollar_collateral_velocity(total_pledged, primary, haircut)
    
    assert math.isclose(res["observed_collateral_velocity"], 2.8, rel_tol=1e-3)
    assert math.isclose(res["theoretical_max_velocity"], 50.0, rel_tol=1e-3)
    # If haircut doubles to 4%, max capacity is primary * (1 / 0.04) = 2500, deficit check
    assert res["shock_haircut_doubled"] == 0.04

    with pytest.raises(ValueError):
        eurodollar_collateral_velocity(total_pledged_collateral=50.0, primary_collateral=100.0)


# =====================================================================
# 4. Uniswap v4 JIT MEV & CoW Batch Auction Tests
# =====================================================================

def test_uniswap_v4_jit_mev():
    swap_vol = 1_000_000.0  # 1M swap
    passive_lp = 500_000.0  # 500k normal LP
    jit_lp = 4_500_000.0    # 4.5M JIT injected liquidity
    fee_tier = 0.003        # 0.30% = 3000 USD fee
    gas = 50.0
    
    res = uniswap_v4_jit_mev_profit(swap_vol, passive_lp, jit_lp, fee_tier, gas)
    
    assert res["total_swap_fee_generated"] == 3000.0
    # JIT takes 4.5M / 5.0M = 90% of fee = 2700 USD
    assert math.isclose(res["jit_stolen_fee_share"], 2700.0, rel_tol=1e-3)
    assert math.isclose(res["passive_lp_retained_fee"], 300.0, rel_tol=1e-3)
    assert res["net_jit_profit_usd"] == 2650.0
    assert res["is_profitable_attack"] is True


def test_cow_swap_batch_auction():
    orders = [
        {"id": "o1", "side": "buy", "amount": 100.0, "limit_price": 2000.0},
        {"id": "o2", "side": "sell", "amount": 80.0, "limit_price": 1980.0},
        {"id": "o3", "side": "sell", "amount": 20.0, "limit_price": 1990.0}
    ]
    
    res = cow_swap_batch_auction_clearing(orders)
    
    assert res["matched_volume"] == 100.0
    assert res["unmatched_imbalance"] == 0.0
    assert res["clearing_price"] > 0.0
    assert res["mev_risk_eliminated"] is True


# =====================================================================
# 5. Cartea-Jaimungal HJB Optimal Market Making Tests
# =====================================================================

def test_cartea_jaimungal_market_making():
    # Long inventory: q = +5
    long_res = cartea_jaimungal_optimal_spread(inventory_q=5, gamma=0.01, k=1.5, A=140.0, sigma=0.02)
    # Neutral inventory: q = 0
    flat_res = cartea_jaimungal_optimal_spread(inventory_q=0, gamma=0.01, k=1.5, A=140.0, sigma=0.02)
    # Short inventory: q = -5
    short_res = cartea_jaimungal_optimal_spread(inventory_q=-5, gamma=0.01, k=1.5, A=140.0, sigma=0.02)
    
    # When long inventory (q=5), market maker wants to sell: ask spread should be tighter than bid spread
    assert long_res["optimal_bid_distance"] > long_res["optimal_ask_distance"]
    assert long_res["inventory_skew"] > 0.0
    
    # When short inventory (q=-5), market maker wants to buy: bid spread should be tighter than ask spread
    assert short_res["optimal_ask_distance"] > short_res["optimal_bid_distance"]
    assert short_res["inventory_skew"] < 0.0
    
    # All spreads positive
    assert flat_res["total_optimal_spread"] > 0.0


# =====================================================================
# 6. Up-C TRA, De-SPAC & Section 382 NOL Tests
# =====================================================================

def test_upc_tra_valuation():
    basis_step_up = 150_000_000.0  # $150M step up amortized over 15 years = $10M/year
    tax_rate = 0.25                # 25% tax rate = $2.5M tax savings/year
    tra_share = 0.85               # 85% to TRA owners = $2.125M/year
    
    res = upc_tax_receivable_agreement_value(basis_step_up, tax_rate, tra_share, discount_rate=0.08, amortization_years=15)
    
    assert math.isclose(res["annual_tax_shield"], 2_500_000.0, abs_tol=1e-3)
    assert math.isclose(res["annual_tra_liability_payout"], 2_125_000.0, abs_tol=1e-3)
    assert math.isclose(res["annual_corporate_benefit"], 375_000.0, abs_tol=1e-3)
    assert res["tra_liability_present_value"] > 0.0
    assert res["corporate_retained_pv"] > 0.0


def test_despac_dilution():
    trust_cash = 200_000_000.0   # $200M in trust
    initial_shares = 20_000_000.0 # 20M shares ($10 NAV)
    redemption_rate = 0.90       # 90% redeemed!
    sponsor_shares = 5_000_000.0  # 5M promote shares (20% of initial total)
    expenses = 10_000_000.0      # $10M expenses
    
    res = despac_dilution_and_cash_per_share(trust_cash, initial_shares, redemption_rate, sponsor_shares, expenses)
    
    # Remaining public shares: 2M
    assert res["remaining_public_shares"] == 2_000_000.0
    # Remaining trust cash: 20M. After 10M expenses -> 10M net closing cash
    assert res["net_closing_cash"] == 10_000_000.0
    # Total post shares: 2M + 5M = 7M
    # Diluted cash per share: 10M / 7M ≈ $1.428 per share vs initial $10.0!
    assert math.isclose(res["diluted_cash_per_share"], 10.0 / 7.0, rel_tol=1e-3)
    assert res["dilution_loss_percentage"] > 0.80  # More than 80% loss in cash-per-share backing!


def test_irc_section_382_nol():
    equity_value = 50_000_000.0     # $50M company valuation
    federal_rate = 0.035            # 3.5% long term tax exempt rate
    nol = 70_000_000.0              # $70M accumulated tax losses
    
    res = irc_section_382_nol_limitation(equity_value, federal_rate, nol)
    
    # Annual limit = $50M * 3.5% = $1.75M/year
    assert math.isclose(res["annual_nol_deduction_limit"], 1_750_000.0, abs_tol=1e-3)
    # Years to fully utilize: 70M / 1.75M = 40 years!
    assert math.isclose(res["years_to_fully_utilize"], 40.0, rel_tol=1e-3)
