"""
Automated pytest suite for Phase 35: Advanced Quantitative Financial Engineering Architecture.

Validates:
1. Alfonsi-Fruth-Schied (AFS 2008/2010) Non-Linear Order Book Depth & Transient Market Impact
2. Ayache-Forsyth-Vetzal (AFV 2003) Convertible Bond Jump-to-Default Cross-Asset Model
3. ISDA SIMM v2.6 Parametric Initial Margin & Margin Valuation Adjustment (MVA)
4. Igor Halperin (2019) Q-Learner & G-Learner Reinforcement Learning Dynamic Hedging
5. Euler Allocation Principle & Shapley Value Tail Risk Attribution (ES & VaR Decomposition)
6. CowSwap Coincidence of Wants (CoW), Batch Auctions & Uniform Clearing Price (UCP)
"""

import math
import sys
from pathlib import Path
import numpy as np
import pytest

# Ensure scripts directory is importable
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "financial-auditor" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from alfonsi_ayache_simm_halperin_shapley_cowswap import (
    AlfonsiFruthSchiedEngine,
    AyacheForsythVetzalEngine,
    ISDASIMMEngine,
    HalperinGLearnerEngine,
    EulerShapleyRiskEngine,
    CowSwapBatchAuctionEngine,
    CoWTradeOrder,
    _black_scholes_call,
    _black_scholes_put,
)


# ==============================================================================
# 1. ALFONSI-FRUTH-SCHIED (AFS) LOB IMPACT TESTS
# ==============================================================================

def test_afs_gatheral_completely_monotone():
    """Verify Gatheral (2010) completely monotone resilience condition preventing price manipulation."""
    afs = AlfonsiFruthSchiedEngine(s0=100.0, gamma=0.8, rho=0.6, power_alpha=0.5)
    assert afs.verify_gatheral_no_arbitrage() is True


def test_afs_instantaneous_impact_properties():
    """Verify non-linear order book shape impact satisfies sign and power law scaling."""
    afs = AlfonsiFruthSchiedEngine(s0=100.0, gamma=1.0, rho=0.5, power_alpha=0.5)
    assert afs.instantaneous_impact(0.0) == 0.0
    impact_pos = afs.instantaneous_impact(100.0)
    impact_neg = afs.instantaneous_impact(-100.0)
    assert impact_pos > 0.0
    assert impact_neg < 0.0
    assert abs(impact_pos + impact_neg) < 1e-9
    # Sub-linear square root scaling: impact of 400 is exactly 2x impact of 100
    assert abs(afs.instantaneous_impact(400.0) - 2.0 * impact_pos) < 1e-9


def test_afs_optimal_schedule_conservation_and_shortfall():
    """Verify liquidation schedule strictly conserves shares and computes non-negative shortfall."""
    total_shares = 50000.0
    afs = AlfonsiFruthSchiedEngine(s0=150.0, gamma=0.5, rho=0.7, power_alpha=0.5)
    res = afs.solve_optimal_schedule(total_shares=total_shares, horizon_t=1.0, num_steps=8, is_sell=True)

    assert abs(np.sum(res.trade_sizes) - total_shares) < 1e-5
    assert abs(res.shares_remaining[-1]) < 1e-5
    assert np.all(res.trade_sizes > 0.0)
    assert res.implementation_shortfall >= 0.0
    assert res.gatheral_monotone_verified is True


# ==============================================================================
# 2. AYACHE-FORSYTH-VETZAL (AFV 2003) CONVERTIBLE BOND TESTS
# ==============================================================================

def test_afv_bond_floor_discounting():
    """Verify bond floor incorporates default hazard intensity and recovery rate."""
    afv_safe = AyacheForsythVetzalEngine(
        s0=50.0, face_value=1000.0, coupon_rate=0.04, conversion_ratio=20.0,
        maturity_t=5.0, risk_free_r=0.03, credit_hazard_lambda=0.0, stock_vol=0.25, recovery_rate=0.40
    )
    afv_risky = AyacheForsythVetzalEngine(
        s0=50.0, face_value=1000.0, coupon_rate=0.04, conversion_ratio=20.0,
        maturity_t=5.0, risk_free_r=0.03, credit_hazard_lambda=0.05, stock_vol=0.25, recovery_rate=0.40
    )
    safe_floor = afv_safe.calculate_bond_floor()
    risky_floor = afv_risky.calculate_bond_floor()

    assert safe_floor > risky_floor
    assert risky_floor > afv_risky.recovery * afv_risky.face_value


def test_afv_convertible_parity_and_soft_call():
    """Verify deep-in-the-money equity parity and soft-call forced redemption."""
    # Low stock price: bond floor dominates
    afv_low = AyacheForsythVetzalEngine(
        s0=20.0, face_value=1000.0, coupon_rate=0.03, conversion_ratio=20.0,
        maturity_t=3.0, risk_free_r=0.04, credit_hazard_lambda=0.02, stock_vol=0.30
    )
    res_low = afv_low.solve_afv()
    assert res_low.convertible_price >= res_low.bond_floor
    assert not res_low.is_soft_called

    # High stock price triggering soft call (> 130% of conversion price 50 -> S >= 65)
    afv_high = AyacheForsythVetzalEngine(
        s0=80.0, face_value=1000.0, coupon_rate=0.03, conversion_ratio=20.0,
        maturity_t=3.0, risk_free_r=0.04, credit_hazard_lambda=0.02, stock_vol=0.30
    )
    res_high = afv_high.solve_afv()
    assert res_high.is_soft_called is True
    assert res_high.convertible_price >= res_high.conversion_parity
    assert res_high.delta > 0.0


# ==============================================================================
# 3. ISDA SIMM v2.6 PARAMETRIC MARGIN & MVA TESTS
# ==============================================================================

def test_isda_simm_delta_margin_and_correlations():
    """Verify ISDA SIMM delta margin aggregates sensitivities with intra-bucket correlations."""
    simm = ISDASIMMEngine(funding_spread_bps=100.0, risk_free_r=0.04)
    sens = {"Rates_1Y": 100000.0, "Rates_5Y": 200000.0, "Rates_10Y": 300000.0}
    delta_im, buckets = simm.compute_delta_margin(sens)

    assert delta_im > 0.0
    # Diversified margin is strictly less than sum of absolute individual margins due to corr < 1
    sum_undiversified = sum(buckets.values())
    assert delta_im < sum_undiversified


def test_isda_simm_curvature_and_mva_lifecycle():
    """Verify curvature margin is strictly positive for non-zero gamma and MVA integrates correctly."""
    simm = ISDASIMMEngine(funding_spread_bps=80.0, risk_free_r=0.035)
    curv_im = simm.compute_curvature_margin({"Rates_5Y": 50000.0, "Equity_Large": 25000.0})
    assert curv_im > 0.0

    res = simm.run_simm_audit(
        delta_sensitivities={"Rates_5Y": 1000000.0},
        gamma_sensitivities={"Rates_5Y": 100000.0},
        vega_sensitivities={"Rates_5Y": 50000.0},
        trade_maturity_t=5.0
    )
    assert res.total_initial_margin > res.delta_margin
    assert res.mva_lifecycle_cost > 0.0
    assert res.mva_annual_charge > 0.0


# ==============================================================================
# 4. HALPERIN G-LEARNER DYNAMIC HEDGING TESTS
# ==============================================================================

def test_halperin_g_learner_turnover_reduction():
    """Verify G-Learner dampens turnover and saves transaction fees compared to pure BS delta."""
    glearner = HalperinGLearnerEngine(
        s0=100.0, strike=100.0, maturity_t=1.0, sigma=0.25,
        r=0.03, risk_aversion_lambda=0.02, transaction_cost_c=0.005
    )
    res = glearner.solve_lqg_optimal_hedge(num_steps=30)

    # In presence of quadratic transaction costs, optimal policy dampens excessive turnover
    bs_turnover = np.sum(np.abs(np.diff(res.black_scholes_delta)))
    assert res.hedging_turnover <= bs_turnover + 0.05
    assert len(res.g_learner_optimal_hedge) == 31
    assert np.all(res.g_learner_optimal_hedge >= 0.0)
    assert np.all(res.g_learner_optimal_hedge <= 1.0)


# ==============================================================================
# 5. EULER ALLOCATION & SHAPLEY VALUE TAIL RISK ATTRIBUTION TESTS
# ==============================================================================

def test_euler_allocation_exact_additivity():
    """Verify Euler allocation theorem: sum of component ES equals total portfolio ES."""
    np.random.seed(42)
    # Generate 3 correlated asset returns
    mean = [0.0005, 0.0008, 0.0004]
    cov = [
        [0.0004, 0.0001, 0.0001],
        [0.0001, 0.0009, 0.0002],
        [0.0001, 0.0002, 0.0006]
    ]
    rets = np.random.multivariate_normal(mean, cov, size=2000)
    weights = np.array([0.5, 0.3, 0.2])

    euler = EulerShapleyRiskEngine(confidence_alpha=0.975)
    res = euler.compute_euler_attribution(weights, rets)

    # Check Euler additivity: sum(CES) == Port_ES
    assert res.euler_sum_verification is True
    assert abs(np.sum(res.component_expected_shortfall) - res.portfolio_expected_shortfall) < 1e-4
    assert np.all(res.shapley_values > 0.0)
    assert abs(np.sum(res.risk_weights_pct) - 100.0) < 1e-2


# ==============================================================================
# 6. COWSWAP COINCIDENCE OF WANTS & BATCH AUCTION TESTS
# ==============================================================================

def test_cowswap_pairwise_matching_and_zero_mev():
    """Verify direct pairwise Coincidence of Wants matching and zero MEV extraction."""
    cow = CowSwapBatchAuctionEngine()
    orders = [
        CoWTradeOrder("O1", "ETH", "USDC", sell_amount=5.0, min_buy_amount=14500.0, limit_price=2900.0),
        CoWTradeOrder("O2", "USDC", "ETH", sell_amount=15000.0, min_buy_amount=4.9, limit_price=0.00033)
    ]
    res = cow.solve_batch_auction(orders)

    assert res.num_cleared_orders == 2
    assert res.arbitrage_mev_extracted == 0.0
    assert len(res.ring_trades_matched) == 1
    assert res.trader_surplus_usd > 0.0


def test_cowswap_triangular_ring_trade_and_surplus():
    """Verify 3-hop cyclic ring trade detection (A -> B -> C -> A) and clearing efficiency."""
    cow = CowSwapBatchAuctionEngine()
    orders = [
        CoWTradeOrder("O1", "ETH", "WBTC", sell_amount=20.0, min_buy_amount=0.95, limit_price=0.0475),
        CoWTradeOrder("O2", "WBTC", "USDC", sell_amount=1.0, min_buy_amount=58000.0, limit_price=58000.0),
        CoWTradeOrder("O3", "USDC", "ETH", sell_amount=60000.0, min_buy_amount=19.5, limit_price=0.000325)
    ]
    res = cow.solve_batch_auction(orders)

    assert res.num_cleared_orders == 3
    assert len(res.ring_trades_matched) == 1
    assert res.ring_trades_matched[0] == ["O1", "O2", "O3"]
    assert res.clearing_efficiency_pct == 100.0
    assert res.arbitrage_mev_extracted == 0.0
    assert res.trader_surplus_usd > 0.0
