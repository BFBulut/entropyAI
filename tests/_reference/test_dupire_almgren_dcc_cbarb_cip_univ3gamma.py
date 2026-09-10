"""Automated test suite for Phase 32: Quantitative Financial Engineering, Market Execution & Structural Finance Architecture.

Validates:
1. Dupire Local Volatility Surface Inversion & Tikhonov Regularization
2. Almgren-Chriss Optimal Execution Hyperbolic Trajectory & Risk Aversion
3. DCC-GARCH Dynamic Conditional Correlation, Minimum Variance & EVT VaR
4. Convertible Bond Arbitrage, Moneyness Regimes & Gamma Scalping
5. CIP Breakdown, Cross-Currency Basis Dislocation & Regulatory SLR Hurdle
6. Uniswap v3 Option Equivalence, Negative Gamma & Break-Even Volume
"""

import math
import sys
from pathlib import Path
import numpy as np
import pytest

# Ensure skills scripts are importable
scripts_dir = Path(__file__).parents[2] / "skills" / "financial-auditor" / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from dupire_almgren_dcc_cbarb_cip_univ3gamma import (
    DupireLocalVolatilityEngine,
    AlmgrenChrissOptimalExecutionEngine,
    DCCGarchDynamicCorrelationEngine,
    ConvertibleBondArbitrageEngine,
    CIPBasisDislocationEngine,
    UniswapV3OptionEquivalenceEngine,
    _bs_call_price,
    _norm_cdf
)


# ==============================================================================
# 1. DUPIRE LOCAL VOLATILITY INVERSION TESTS
# ==============================================================================

def test_dupire_local_vol_surface_dimensions_and_regularization():
    engine = DupireLocalVolatilityEngine(spot=100.0, risk_free_rate=0.03, dividend_yield=0.01)
    strikes = [80.0, 90.0, 100.0, 110.0, 120.0]
    maturities = [0.25, 0.50, 1.00]
    
    iv_matrix = [
        engine.generate_implied_vol_smile(strikes, T, atm_vol=0.20, skew=-0.10)
        for T in maturities
    ]
    
    res = engine.invert_local_volatility_surface(strikes, maturities, iv_matrix)
    
    assert len(res.local_vol_grid) == len(maturities)
    assert len(res.local_vol_grid[0]) == len(strikes)
    assert len(res.grid_points) == len(maturities) * len(strikes)
    
    # Check that all local vols are positive and strictly clamped within bounds
    for pt in res.grid_points:
        assert engine.vol_min <= pt.local_vol <= engine.vol_max
        assert pt.local_variance > 0.0
        assert pt.call_price > 0.0


def test_dupire_calendar_and_butterfly_arbitrage_positivity():
    engine = DupireLocalVolatilityEngine(spot=100.0, risk_free_rate=0.05, dividend_yield=0.0)
    strikes = [75.0, 85.0, 95.0, 100.0, 105.0, 115.0, 125.0]
    maturities = [0.1, 0.25, 0.5, 0.75, 1.0]
    
    iv_matrix = [
        engine.generate_implied_vol_smile(strikes, T, atm_vol=0.25, skew=-0.15)
        for T in maturities
    ]
    
    res = engine.invert_local_volatility_surface(strikes, maturities, iv_matrix)
    
    # Verify butterfly arbitrage positivity (d2C/dK2 > 0) and calendar spread (dC/dT > 0)
    for pt in res.grid_points:
        assert pt.dC_dT > 0.0
        assert pt.d2C_dK2 > 0.0
        assert bool(pt.is_arbitrage_free) is True


def test_dupire_monte_carlo_barrier_vs_vanilla_call():
    engine = DupireLocalVolatilityEngine(spot=100.0, risk_free_rate=0.04)
    strikes = [80.0, 90.0, 100.0, 110.0, 120.0]
    maturities = [0.25, 0.50, 1.00]
    iv_matrix = [
        engine.generate_implied_vol_smile(strikes, T, atm_vol=0.20, skew=-0.12)
        for T in maturities
    ]
    res = engine.invert_local_volatility_surface(strikes, maturities, iv_matrix)
    
    # Up-and-out barrier call must strictly be cheaper than vanilla call
    assert res.vanilla_call_price > 0.0
    assert res.exotic_barrier_price > 0.0
    assert res.exotic_barrier_price < res.vanilla_call_price


# ==============================================================================
# 2. ALMGREN-CHRISS OPTIMAL EXECUTION TESTS
# ==============================================================================

def test_almgren_chriss_trajectory_monotonicity_and_termination():
    X_0 = 1_000_000.0
    engine = AlmgrenChrissOptimalExecutionEngine(
        total_shares=X_0,
        initial_price=50.0,
        daily_volatility=1.0,
        time_horizon_days=5.0,
        num_intervals=10,
        risk_aversion_lambda=1e-5
    )
    res = engine.compute_optimal_trajectory()
    
    # Monotonically decreasing shares remaining
    prev_shares = X_0
    for pt in res.trajectory:
        assert pt.shares_remaining < prev_shares + 1e-6
        assert pt.trade_size > 0.0
        assert pt.trade_velocity > 0.0
        prev_shares = pt.shares_remaining
        
    # Final shares remaining should be approximately zero
    assert res.trajectory[-1].shares_remaining < 1e-4
    total_traded = sum(pt.trade_size for pt in res.trajectory)
    assert math.isclose(total_traded, X_0, rel_tol=1e-3)


def test_almgren_chriss_risk_aversion_tradeoff_variance_vs_cost():
    # Low risk aversion vs High risk aversion
    eng_risk_neutral = AlmgrenChrissOptimalExecutionEngine(
        total_shares=500_000.0,
        risk_aversion_lambda=1e-8
    )
    eng_risk_averse = AlmgrenChrissOptimalExecutionEngine(
        total_shares=500_000.0,
        risk_aversion_lambda=1e-4
    )
    
    res_neutral = eng_risk_neutral.compute_optimal_trajectory()
    res_averse = eng_risk_averse.compute_optimal_trajectory()
    
    # Risk averse trades faster: kappa is higher, half-life is shorter
    assert res_averse.kappa > res_neutral.kappa
    assert res_averse.half_life_days < res_neutral.half_life_days
    
    # Risk averse pays higher expected market impact cost to drastically reduce variance
    assert res_averse.expected_shortfall_cost > res_neutral.expected_shortfall_cost
    assert res_averse.variance_of_shortfall < res_neutral.variance_of_shortfall


def test_almgren_chriss_power_law_impact_scaling():
    engine = AlmgrenChrissOptimalExecutionEngine(
        total_shares=500_000.0,
        time_horizon_days=5.0,
        num_intervals=10
    )
    res = engine.compute_optimal_trajectory()
    
    # Power-law shortfall cost is positive and bounded
    assert res.power_law_shortfall_cost > 0.0
    assert res.variance_reduction_vs_twap_pct >= 0.0


# ==============================================================================
# 3. ENGLE COPULA-DCC-GARCH TESTS
# ==============================================================================

def test_dcc_garch_stationarity_and_correlation_bounds():
    engine = DCCGarchDynamicCorrelationEngine(dcc_alpha=0.05, dcc_beta=0.92)
    assert engine.is_stationary is True
    
    # Generate 3-asset synthetic return series
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0004, 0.012, size=(80, 3))
    res = engine.fit_and_predict(returns)
    
    assert res.is_stationary is True
    assert res.num_assets == 3
    assert res.num_periods == 80
    
    # Verify all correlations are strictly within [-1.0, 1.0] and diagonal is 1.0
    for pt in res.time_series:
        corr = np.array(pt.correlation_matrix)
        assert np.all(corr >= -1.0 - 1e-6)
        assert np.all(corr <= 1.0 + 1e-6)
        np.testing.assert_allclose(np.diag(corr), np.ones(3), atol=1e-5)


def test_dcc_garch_dynamic_matrix_symmetry_and_positive_definiteness():
    engine = DCCGarchDynamicCorrelationEngine(dcc_alpha=0.08, dcc_beta=0.88)
    rng = np.random.default_rng(99)
    returns = rng.normal(0.0, 0.015, size=(60, 2))
    res = engine.fit_and_predict(returns)
    
    for pt in res.time_series:
        corr = np.array(pt.correlation_matrix)
        # Symmetry check
        np.testing.assert_allclose(corr, corr.T, atol=1e-6)
        # Positive semi-definiteness: eigenvalues >= 0
        eigvals = np.linalg.eigvalsh(corr)
        assert np.all(eigvals >= -1e-7)


def test_dcc_garch_min_variance_weights_and_var99():
    engine = DCCGarchDynamicCorrelationEngine(dcc_alpha=0.05, dcc_beta=0.90)
    rng = np.random.default_rng(77)
    returns = rng.normal(0.0002, 0.01, size=(50, 3))
    res = engine.fit_and_predict(returns)
    
    # Portfolio weights must sum to 1.0
    for pt in res.time_series:
        assert math.isclose(sum(pt.min_variance_weights), 1.0, rel_tol=1e-4)
        assert pt.portfolio_vol > 0.0
        assert pt.portfolio_var_99 > 0.0


# ==============================================================================
# 4. CONVERTIBLE BOND ARBITRAGE TESTS
# ==============================================================================

def test_convertible_arbitrage_moneyness_regimes():
    engine = ConvertibleBondArbitrageEngine(
        face_value=1000.0,
        coupon_rate=0.02,
        conversion_ratio=20.0,   # Conversion price = $50
        credit_spread=0.03
    )
    
    pos_busted = engine.evaluate_arbitrage(stock_price=20.0, stock_volatility=0.30)
    pos_hybrid = engine.evaluate_arbitrage(stock_price=50.0, stock_volatility=0.30)
    pos_parity = engine.evaluate_arbitrage(stock_price=90.0, stock_volatility=0.30)
    
    assert pos_busted.moneyness_regime == "Busted"
    assert pos_hybrid.moneyness_regime == "Hybrid"
    assert pos_parity.moneyness_regime == "Equity Parity"
    
    # Busted CB has very low delta (close to bond floor)
    assert pos_busted.delta < 3.0
    # Parity CB has delta near conversion ratio (20.0)
    assert pos_parity.delta > 18.0
    # Hybrid CB has highest dollar gamma and vega (arbitrage sweet spot)
    assert pos_hybrid.dollar_gamma > pos_busted.dollar_gamma
    assert pos_hybrid.dollar_gamma > pos_parity.dollar_gamma
    assert pos_hybrid.vega > pos_busted.vega
    assert pos_hybrid.vega > pos_parity.vega


def test_convertible_arbitrage_greeks_and_gamma_scalping_pnl():
    engine = ConvertibleBondArbitrageEngine(
        face_value=1000.0,
        coupon_rate=0.03,
        conversion_ratio=25.0,  # Conv Price = $40
        borrow_cost_annual=0.01
    )
    pos = engine.evaluate_arbitrage(stock_price=40.0, stock_volatility=0.45)
    
    assert pos.delta > 0.0
    assert pos.gamma > 0.0
    assert pos.vega > 0.0
    assert pos.theta < 0.0
    assert pos.parity_value == 40.0 * 25.0
    assert pos.cb_market_price >= pos.bond_floor_value
    assert pos.cb_market_price >= pos.parity_value


# ==============================================================================
# 5. CIP DEVIATION & CROSS-CURRENCY BASIS SWAP TESTS
# ==============================================================================

def test_cip_dislocation_forward_deviation_and_synthetic_rate():
    engine = CIPBasisDislocationEngine(
        slr_capital_requirement_pct=0.05,
        bank_hurdle_roe_pct=0.10
    )
    # EUR/USD scenario with negative basis (USD shortage)
    res = engine.analyze_cip_dislocation(
        spot_eur_usd=1.0800,
        forward_eur_usd=1.0850,
        euribor_3m=0.0350,
        sofr_3m=0.0550,
        tenor_days=90
    )
    
    assert res.theoretical_cip_forward > 0.0
    assert isinstance(res.cip_deviation_bps, float)
    assert res.synthetic_usd_funding_rate > 0.0
    # SLR hurdle is 2 * 0.05 * 0.10 = 100 bps
    assert math.isclose(res.slr_capital_hurdle_rate_bps, 100.0, abs_tol=1e-5)


def test_cip_slr_regulatory_hurdle_and_profitability_threshold():
    engine = CIPBasisDislocationEngine(
        slr_capital_requirement_pct=0.05,
        bank_hurdle_roe_pct=0.10
    )
    # Case 1: Basis dislocation is small (-40 bps) -> not profitable after 100 bps SLR hurdle
    res_unprofitable = engine.analyze_cip_dislocation(
        spot_eur_usd=1.1000,
        forward_eur_usd=1.1040,
        euribor_3m=0.0300,
        sofr_3m=0.0450,
        tenor_days=90
    )
    assert res_unprofitable.is_arbitrage_profitable is False
    
    # Case 2: Extreme dislocation (-150 bps) -> profitable after 100 bps SLR hurdle
    res_profitable = engine.analyze_cip_dislocation(
        spot_eur_usd=1.1000,
        forward_eur_usd=1.1005,  # Artificially low forward creating massive negative basis
        euribor_3m=0.0200,
        sofr_3m=0.0550,
        tenor_days=90
    )
    assert abs(res_profitable.cip_deviation_bps) > 100.0
    assert res_profitable.is_arbitrage_profitable is True


# ==============================================================================
# 6. UNISWAP V3 CONCENTRATED LIQUIDITY OPTION EQUIVALENCE TESTS
# ==============================================================================

def test_univ3_option_equivalence_exact_negative_gamma():
    engine = UniswapV3OptionEquivalenceEngine(
        liquidity_L=1_000_000.0,
        price_lower=1500.0,
        price_upper=2500.0,
        fee_rate=0.003
    )
    res = engine.evaluate_lp_option_profile(current_price=2000.0, annual_volatility=0.60)
    
    assert res.is_in_range is True
    # Mathematical proof: Gamma must strictly be negative!
    assert res.gamma < 0.0
    expected_gamma = -1_000_000.0 / (2.0 * (2000.0 ** 1.5))
    assert math.isclose(res.gamma, expected_gamma, rel_tol=1e-5)
    
    # Delta must be positive inside range
    assert res.delta_shares > 0.0
    expected_delta = 1_000_000.0 * (1.0 / math.sqrt(2000.0) - 1.0 / math.sqrt(2500.0))
    assert math.isclose(res.delta_shares, expected_delta, rel_tol=1e-5)


def test_univ3_impermanent_loss_and_delta_hedge_neutrality():
    engine = UniswapV3OptionEquivalenceEngine(
        liquidity_L=500_000.0,
        price_lower=1800.0,
        price_upper=2200.0
    )
    # Entry at 2000, price moves to 2150
    res_entry = engine.evaluate_lp_option_profile(current_price=2000.0, initial_entry_price=2000.0)
    res_shift = engine.evaluate_lp_option_profile(current_price=2150.0, initial_entry_price=2000.0)
    
    # At entry, IL is 0
    assert math.isclose(res_entry.impermanent_loss_usd, 0.0, abs_tol=1e-5)
    # As price deviates, LP value < HODL value, so IL > 0
    assert res_shift.impermanent_loss_usd > 0.0
    assert res_shift.impermanent_loss_pct > 0.0
    
    # Delta decreases as price rises (buying USDC, selling ETH)
    assert res_shift.delta_shares < res_entry.delta_shares


def test_univ3_break_even_pool_volume_formula():
    engine = UniswapV3OptionEquivalenceEngine(
        liquidity_L=1_000_000.0,
        price_lower=1800.0,
        price_upper=2200.0,
        fee_rate=0.003
    )
    res = engine.evaluate_lp_option_profile(current_price=2000.0, annual_volatility=0.70)
    
    # Break-even volume must be strictly positive and scale with vol^2
    assert res.break_even_daily_volume_usd > 0.0
    
    res_high_vol = engine.evaluate_lp_option_profile(current_price=2000.0, annual_volatility=1.40)
    # Doubling vol quadruples the required break-even fee volume (since IL ~ vol^2)
    assert math.isclose(res_high_vol.break_even_daily_volume_usd / res.break_even_daily_volume_usd, 4.0, rel_tol=1e-3)
