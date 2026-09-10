"""
Unit tests for Chapter 24 Financial Auditor Script:
Carr-Madan Spanning, Breeden-Litzenberger Risk-Neutral Density,
Cont-Kukanov-Stoikov Level-1 and Deep OFI, US Treasury Basis Trade & CTD,
PE Subscription Lines & NAV Financing, Zhou First-Passage Structural Credit with Jumps,
and Uniswap v3 Option Replication & Dynamic Delta Hedging.
"""

import math
import numpy as np
import pytest
from pathlib import Path
import sys

# Ensure scripts directory is in path
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from carr_madan_ofi_basis_sublines_zhou_univ3 import (
    carr_madan_log_contract_replication,
    breeden_litzenberger_risk_neutral_density,
    calculate_level1_ofi,
    calculate_deep_ofi,
    treasury_basis_trade_analysis,
    subscription_line_irr_impact,
    nav_facility_borrowing_capacity,
    zhou_jump_default_probability_and_spread,
    uniswap_v3_option_replication_and_greeks,
    uniswap_v3_dynamic_delta_hedge_simulation
)


# =====================================================================
# 1. Carr-Madan Spanning & Breeden-Litzenberger Density Tests
# =====================================================================

def test_carr_madan_log_contract_replication():
    forward = 100.0
    r = 0.05
    t = 1.0  # 1 year
    
    strikes = np.linspace(60.0, 140.0, 81)
    # Synthetic Black-Scholes call/put curve with implied vol ~ 20%
    sigma = 0.20
    d1 = (np.log(forward / strikes) + 0.5 * (sigma ** 2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    
    def n_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
        
    calls = math.exp(-r * t) * np.array([forward * n_cdf(x1) - k * n_cdf(x2) for x1, x2, k in zip(d1, d2, strikes)])
    puts = math.exp(-r * t) * np.array([k * n_cdf(-x2) - forward * n_cdf(-x1) for x1, x2, k in zip(d1, d2, strikes)])
    
    res = carr_madan_log_contract_replication(forward, strikes, calls, puts, r, t)
    
    assert res["implied_volatility"] > 0.15
    assert res["implied_volatility"] < 0.25
    assert math.isclose(res["annualized_vix_points"], res["implied_volatility"] * 100.0)
    
    with pytest.raises(ValueError):
        carr_madan_log_contract_replication(-100.0, strikes, calls, puts, r, t)


def test_breeden_litzenberger_density():
    r = 0.03
    t = 0.5
    forward = 100.0
    sigma = 0.25
    strikes = np.linspace(70.0, 130.0, 61)
    
    d1 = (np.log(forward / strikes) + 0.5 * (sigma ** 2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    
    def n_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
        
    calls = math.exp(-r * t) * np.array([forward * n_cdf(x1) - k * n_cdf(x2) for x1, x2, k in zip(d1, d2, strikes)])
    
    res = breeden_litzenberger_risk_neutral_density(strikes, calls, r, t)
    
    assert len(res["risk_neutral_density"]) == len(strikes) - 2
    # Mean of risk-neutral density should be close to forward (100.0)
    assert 95.0 < res["mean_strike"] < 105.0
    assert res["std_strike"] > 0.0
    assert -2.0 < res["implied_skewness"] < 2.0


# =====================================================================
# 2. Cont-Kukanov-Stoikov OFI Tests
# =====================================================================

def test_calculate_level1_ofi():
    # Synthetic order book quotes
    b_p = np.array([100.0, 100.0, 100.1, 100.1, 100.0])
    b_v = np.array([50.0, 60.0, 40.0, 30.0, 45.0])
    a_p = np.array([100.2, 100.2, 100.2, 100.3, 100.2])
    a_v = np.array([50.0, 40.0, 45.0, 35.0, 50.0])
    
    ofi = calculate_level1_ofi(b_p, b_v, a_p, a_v)
    assert len(ofi) == len(b_p) - 1
    
    # Step 1: b_p flat, b_v 50->60 (delta_bid = +10)
    #         a_p flat, a_v 50->40 (delta_ask = -10)
    # OFI = +10 - (-10) = +20
    assert ofi[0] == 20.0
    
    # Step 2: b_p rises 100.0->100.1 (delta_bid = 40.0)
    #         a_p flat, a_v 40->45 (delta_ask = +5.0)
    # OFI = 40 - 5 = +35.0
    assert ofi[1] == 35.0


def test_calculate_deep_ofi():
    np.random.seed(42)
    T, K = 50, 4
    # Simulate LOB
    base_price = 100.0
    b_p = np.zeros((T, K))
    a_p = np.zeros((T, K))
    b_v = np.random.uniform(10, 50, (T, K))
    a_v = np.random.uniform(10, 50, (T, K))
    
    mid = base_price + np.cumsum(np.random.randn(T) * 0.05)
    for k in range(K):
        b_p[:, k] = mid - 0.05 * (k + 1)
        a_p[:, k] = mid + 0.05 * (k + 1)
        
    res = calculate_deep_ofi(b_p, b_v, a_p, a_v, decay_alpha=0.6)
    
    assert res["num_levels"] == 4
    assert res["num_observations"] == T - 1
    assert len(res["decay_weights"]) == 4
    assert math.isclose(sum(res["decay_weights"]), 1.0, abs_tol=1e-5)
    assert isinstance(res["price_impact_beta"], float)


# =====================================================================
# 3. US Treasury Basis Trade & CTD Tests
# =====================================================================

def test_treasury_basis_trade_analysis():
    # 10-year Treasury cash bond at 98.50, futures at 110.00, CF = 0.8850
    cash_p = 98.50
    futures_p = 110.00
    cf = 0.8850
    repo_rate = 0.0530  # 5.30% SOFR repo
    coupon_rate = 0.0450  # 4.50% coupon
    days = 60.0
    leverage = 50.0  # 2% initial haircut
    
    res = treasury_basis_trade_analysis(cash_p, futures_p, cf, repo_rate, coupon_rate, days, leverage)
    
    assert "gross_basis" in res
    assert "net_basis" in res
    assert "implied_repo_rate" in res
    assert "leveraged_roe_annualized" in res
    assert res["equity_deployed_per_bond"] == cash_p / leverage
    assert res["margin_call_equity_drawdown_pct"] > 0.0


# =====================================================================
# 4. Private Equity Subscription Lines & NAV Financing Tests
# =====================================================================

def test_subscription_line_irr_impact():
    invested = 100.0
    exit_val = 250.0
    horizon = 5.0
    delay = 1.5  # 18 months sub-line delay
    rate = 0.06  # 6% facility interest rate
    
    res = subscription_line_irr_impact(invested, exit_val, horizon, delay, rate)
    
    # Sub-line should create a positive IRR uplift by compressing time denominator
    assert res["irr_artificial_uplift_bps"] > 0.0
    assert res["subline_net_irr"] > res["organic_net_irr"]
    
    # But MoIC should experience fee drag due to loan interest
    assert res["moic_fee_drag"] > 0.0
    assert res["subline_moic"] < res["organic_moic"]


def test_nav_facility_borrowing_capacity():
    ebitda = [25.0, 40.0, 15.0]
    multiples = [10.0, 12.0, 8.0]
    senior_debt = [100.0, 200.0, 40.0]
    
    # EVs: 250, 480, 120 -> Total EV = 850
    # Equities: 150, 280, 80 -> Total NAV = 510
    res = nav_facility_borrowing_capacity(ebitda, multiples, senior_debt, max_ltv=0.15)
    
    assert res["total_portfolio_enterprise_value"] == 850.0
    assert res["total_portfolio_senior_debt"] == 340.0
    assert res["fund_net_asset_value"] == 510.0
    assert math.isclose(res["max_nav_facility_capacity"], 510.0 * 0.15, abs_tol=1e-5)


# =====================================================================
# 5. Zhou (2001) Structural Credit Model with Jumps Tests
# =====================================================================

def test_zhou_jump_default_probability():
    v0 = 100.0
    barrier = 60.0
    mu = 0.05
    sigma = 0.20
    lambda_jump = 0.10  # 0.10 jumps per year
    mu_jump = -0.25     # negative downward jump mean
    sigma_jump = 0.15
    maturity = 1.0
    r_free = 0.04
    
    res = zhou_jump_default_probability_and_spread(
        v0, barrier, mu, sigma, lambda_jump, mu_jump, sigma_jump, maturity, r_free, recovery_rate=0.40
    )
    
    assert 0.0 < res["continuous_default_prob"] < 1.0
    assert 0.0 < res["jump_default_prob"] < 1.0
    assert res["total_default_probability"] >= res["continuous_default_prob"]
    assert res["implied_credit_spread_bps"] > 0.0
    # Confirms Merton short-term spread zero-limit puzzle is solved
    assert res["merton_zero_limit_solved"] is True
    assert res["short_term_spread_limit_bps"] > 0.0


# =====================================================================
# 6. Uniswap v3 Option Replication & Delta Hedging Tests
# =====================================================================

def test_uniswap_v3_option_replication():
    current_p = 2000.0
    lower_p = 1600.0
    upper_p = 2500.0
    liquidity = 1000.0
    
    res = uniswap_v3_option_replication_and_greeks(current_p, lower_p, upper_p, liquidity)
    
    assert res["is_in_range"] is True
    assert res["amount_x"] > 0.0
    assert res["amount_y"] > 0.0
    assert res["delta"] > 0.0
    # Gamma must be strictly negative for concentrated liquidity LP
    assert res["gamma"] < 0.0
    
    # Boundary tests
    below = uniswap_v3_option_replication_and_greeks(1500.0, lower_p, upper_p, liquidity)
    assert below["is_in_range"] is False
    assert below["amount_y"] == 0.0
    assert below["gamma"] == 0.0


def test_uniswap_v3_dynamic_delta_hedge_simulation():
    lower_p = 1800.0
    upper_p = 2200.0
    liquidity = 5000.0
    
    # Downward trending prices inside range
    prices = np.linspace(2000.0, 1850.0, 20)
    
    res = uniswap_v3_dynamic_delta_hedge_simulation(
        prices, lower_p, upper_p, liquidity, fee_rate=0.003, volume_per_step=20000.0
    )
    
    assert res["num_steps"] == 20
    assert res["num_rebalances"] >= 0
    assert res["total_swap_fees_collected"] > 0.0
    # In a downward move, unhedged LP suffers losses, hedge short provides positive PnL
    assert res["total_hedge_pnl"] > 0.0
    assert res["hedged_strategy_return_pct"] > res["unhedged_lp_return_pct"]
