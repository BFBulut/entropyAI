"""Unit tests for Phase 27 Quantitative Financial Engineering Models.

Modules tested:
- Guéant-Tapia-Manziadi (2012) Closed-Form HJB Market Making & Inventory Quotes
- Rebonato's SABR-LMM & CMS Spread Option Convexity Adjustment
- Flesaker-Hughston (1996) Positive Interest Rate Framework & Caplets
- Lévy Copulas & Systemic Co-Jumps (Cont & Tankov 2004)
- Fractional Cointegration & FCVAR (Johansen & Nielsen 2012)
- Kyle-Obizhaeva (2016) Market Microstructure Invariance
"""

import pytest
import math
import numpy as np

from pathlib import Path
import sys
import pytest
import math
import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from gueant_sabrlmm_flesaker_levycopula_fcvar_obizhaeva import (
    GueantMarketMakingEngine,
    GueantQuotesResult,
    RebonatoSABRLMMEngine,
    CMSSpreadResult,
    FlesakerHughstonEngine,
    FlesakerHughstonBondResult,
    LevyCopulaEngine,
    LevyCoJumpResult,
    FCVARSpreadEngine,
    FCVARResult,
    KyleObizhaevaInvarianceEngine,
    MicrostructureInvarianceResult,
)


# ==============================================================================
# 1. GUÉANT-TAPIA-MANZIADI MARKET MAKING TESTS
# ==============================================================================

def test_gueant_market_making_quotes_symmetry_and_inventory_skew():
    engine = GueantMarketMakingEngine(
        gamma=0.1,
        sigma=0.25,
        intensity_a=150.0,
        intensity_k=1.5,
        max_inventory=10,
    )

    u_vec = engine.compute_asymptotic_u_vector()
    assert len(u_vec) == 21

    # At inventory q = 0, bid and ask half-spreads should be symmetric
    q0_res = engine.calculate_optimal_quotes(current_inventory=0, mid_price=100.0, u_vector=u_vec)
    assert isinstance(q0_res, GueantQuotesResult)
    assert q0_res.inventory == 0
    assert q0_res.bid_price < 100.0 < q0_res.ask_price
    assert pytest.approx(q0_res.bid_spread, rel=1e-2) == q0_res.ask_spread
    assert q0_res.total_spread > 0.0

    # At long inventory q = 5, market maker wants to unload:
    # ask spread should be tighter than at q = 0, bid spread should be wider
    q_long_res = engine.calculate_optimal_quotes(current_inventory=5, mid_price=100.0, u_vector=u_vec)
    assert q_long_res.ask_spread < q0_res.ask_spread
    assert q_long_res.bid_spread > q0_res.bid_spread
    assert q_long_res.ask_arrival_intensity > q0_res.ask_arrival_intensity
    assert q_long_res.bid_arrival_intensity < q0_res.bid_arrival_intensity

    # At short inventory q = -5, market maker wants to buy back:
    # bid spread should be tighter, ask spread should be wider
    q_short_res = engine.calculate_optimal_quotes(current_inventory=-5, mid_price=100.0, u_vector=u_vec)
    assert q_short_res.bid_spread < q0_res.bid_spread
    assert q_short_res.ask_spread > q0_res.ask_spread

    # Boundary handling: at max inventory +10, cannot buy more
    q_boundary = engine.calculate_optimal_quotes(current_inventory=10, mid_price=100.0, u_vector=u_vec)
    assert q_boundary.bid_spread > 5.0 * q0_res.bid_spread


def test_gueant_market_making_validation_errors():
    with pytest.raises(ValueError, match="strictly positive"):
        GueantMarketMakingEngine(gamma=-0.1)

    with pytest.raises(ValueError, match="at least 1"):
        GueantMarketMakingEngine(max_inventory=0)

    engine = GueantMarketMakingEngine(max_inventory=5)
    with pytest.raises(ValueError, match="exceeds max inventory bounds"):
        engine.calculate_optimal_quotes(current_inventory=6)


# ==============================================================================
# 2. REBONATO'S SABR-LMM & CMS SPREAD CONVEXITY TESTS
# ==============================================================================

def test_rebonato_cms_convexity_and_spread_option_pricing():
    # Long CMS 10Y @ 3.5%, Short CMS 2Y @ 3.0%
    cms_long_fwd = 0.035
    cms_short_fwd = 0.030
    vol_long = 0.22
    vol_short = 0.32
    maturity = 2.0
    rho = 0.85

    # 1. Test single leg convexity adjustment
    adj_10y = RebonatoSABRLMMEngine.calculate_cms_convexity_adjustment(
        swap_rate=cms_long_fwd,
        annuity=1.0,
        swap_volatility=vol_long,
        maturity_years=maturity,
        tenor_years=10.0,
    )
    assert adj_10y > 0.0
    # Convexity adjustment typically ranges between 1 and 30 bps
    assert 0.0001 < adj_10y < 0.0050

    # 2. Test full CMS spread option pricing
    res = RebonatoSABRLMMEngine.price_cms_spread_option(
        cms_long_fwd=cms_long_fwd,
        cms_short_fwd=cms_short_fwd,
        cms_long_vol=vol_long,
        cms_short_vol=vol_short,
        rho_spread=rho,
        maturity_years=maturity,
        strike_spread=0.005, # 50 bps strike
        discount_factor=0.92,
    )

    assert isinstance(res, CMSSpreadResult)
    assert res.adjusted_cms_long > cms_long_fwd
    assert res.adjusted_cms_short > cms_short_fwd
    assert res.spread_rate == pytest.approx(res.adjusted_cms_long - res.adjusted_cms_short, abs=1e-6)
    assert res.spread_volatility > 0.0
    assert res.call_spread_option_price > 0.0

    # Invalid correlation bounds check
    with pytest.raises(ValueError, match="in \\[-1, 1\\]"):
        RebonatoSABRLMMEngine.price_cms_spread_option(
            cms_long_fwd=0.04,
            cms_short_fwd=0.03,
            cms_long_vol=0.2,
            cms_short_vol=0.2,
            rho_spread=1.5,
            maturity_years=1.0,
            strike_spread=0.01,
        )


# ==============================================================================
# 3. FLESAKER-HUGHSTON POSITIVE INTEREST RATE TESTS
# ==============================================================================

def test_flesaker_hughston_positive_rates_and_caplets():
    engine = FlesakerHughstonEngine(
        decay_alpha=0.035,
        volatility_sigma=0.18,
        weight_factor=0.5,
    )

    # 1. Verify bond prices are strictly in (0, 1) and monotonically decreasing with maturity
    p_1y = engine.compute_bond_price(t=0.0, T=1.0)
    p_5y = engine.compute_bond_price(t=0.0, T=5.0)
    p_10y = engine.compute_bond_price(t=0.0, T=10.0)

    assert 0.0 < p_10y < p_5y < p_1y < 1.0
    assert engine.compute_bond_price(t=2.0, T=2.0) == 1.0

    # 2. Verify caplet pricing
    caplet_res = engine.price_caplet(
        t=0.0,
        T_start=1.0,
        T_end=2.0,
        strike_rate=0.035,
        x_t=1.0,
    )
    assert isinstance(caplet_res, FlesakerHughstonBondResult)
    assert caplet_res.time_to_maturity == 2.0
    assert caplet_res.bond_price > 0.0
    assert caplet_res.instantaneous_forward > 0.0
    assert caplet_res.caplet_price > 0.0

    # Deep out-of-the-money caplet should be worth less than at-the-money
    otm_res = engine.price_caplet(
        t=0.0,
        T_start=1.0,
        T_end=2.0,
        strike_rate=0.15,
        x_t=1.0,
    )
    assert otm_res.caplet_price < caplet_res.caplet_price

    # Error handling
    with pytest.raises(ValueError, match="positive"):
        FlesakerHughstonEngine(decay_alpha=-0.01)


# ==============================================================================
# 4. LÉVY COPULAS & MULTIVARIATE CO-JUMPS TESTS
# ==============================================================================

def test_levy_copula_cojump_intensity_and_crisis_detection():
    # 1. Test Clayton Lévy copula functional form
    u1, u2, theta = 1.5, 2.0, 1.5
    copula_val = LevyCopulaEngine.calculate_clayton_levy_copula(u1, u2, theta)
    assert copula_val > 0.0
    # Homogeneity of order 1: C(c*u1, c*u2) = c * C(u1, u2)
    c = 2.5
    scaled_copula = LevyCopulaEngine.calculate_clayton_levy_copula(c * u1, c * u2, theta)
    assert pytest.approx(scaled_copula, rel=1e-5) == c * copula_val

    # 2. Systemic co-jump evaluation during normal regime
    normal_eval = LevyCopulaEngine.evaluate_systemic_cojump(
        jump_threshold_1=-0.10, # 10% drop
        jump_threshold_2=-0.10,
        base_jump_rate_1=1.0,
        base_jump_rate_2=1.0,
        jump_size_eta_1=0.02,
        jump_size_eta_2=0.02,
        copula_theta=0.8,
    )
    assert isinstance(normal_eval, LevyCoJumpResult)
    assert normal_eval.tail_cojump_intensity > 0.0
    assert 0.0 <= normal_eval.cojump_probability_ratio <= 1.0

    # 3. Extreme stress regime: high dependence theta & large base rates
    stress_eval = LevyCopulaEngine.evaluate_systemic_cojump(
        jump_threshold_1=-0.04,
        jump_threshold_2=-0.04,
        base_jump_rate_1=4.0,
        base_jump_rate_2=4.0,
        jump_size_eta_1=0.05,
        jump_size_eta_2=0.05,
        copula_theta=3.5,
    )
    assert stress_eval.tail_cojump_intensity > normal_eval.tail_cojump_intensity
    assert stress_eval.cojump_probability_ratio > normal_eval.cojump_probability_ratio
    assert stress_eval.is_extreme_tail_crisis is True


# ==============================================================================
# 5. FRACTIONAL COINTEGRATION & FCVAR SPREAD TESTS
# ==============================================================================

def test_fcvar_long_memory_spread_dynamics():
    # 1. Fractional weights expansion
    weights = FCVARSpreadEngine.compute_fractional_weights(d=0.35, max_lags=20)
    assert len(weights) == 20
    assert weights[0] == 1.0
    # Weights decay alternating or decreasing towards 0
    assert abs(weights[-1]) < abs(weights[1])

    # 2. Generate simulated fractionally cointegrated series
    np.random.seed(42)
    n_points = 100
    common_trend = np.cumsum(np.random.normal(0, 1, n_points))
    spread_noise = np.random.normal(0, 0.5, n_points)
    x_series = (common_trend + np.random.normal(0, 0.2, n_points)).tolist()
    y_series = (1.5 * common_trend + spread_noise).tolist()

    res = FCVARSpreadEngine.estimate_fractional_spread_dynamics(
        series_y=y_series,
        series_x=x_series,
        fractional_d=0.30,
        adjustment_alpha=-0.20,
    )

    assert isinstance(res, FCVARResult)
    assert res.fractional_d == 0.30
    assert res.is_long_memory_stationary is True
    assert pytest.approx(res.cointegration_beta, rel=0.25) == 1.5
    assert res.mean_reversion_half_life > 0.0
    assert res.optimal_trading_signal in {"BUY_SPREAD", "SELL_SPREAD", "NEUTRAL"}

    # Validation errors
    with pytest.raises(ValueError, match="same length"):
        FCVARSpreadEngine.estimate_fractional_spread_dynamics([1.0, 2.0], [1.0])

    with pytest.raises(ValueError, match="must be in \\(0.0, 0.5\\)"):
        FCVARSpreadEngine.estimate_fractional_spread_dynamics(y_series, x_series, fractional_d=0.75)


# ==============================================================================
# 6. KYLE-OBIZHAEVA MICROSTRUCTURE INVARIANCE TESTS
# ==============================================================================

def test_kyle_obizhaeva_market_microstructure_invariance():
    # Large cap equity setup: Price $100, 5M shares daily, 25% annual vol, 20,000 share order
    res = KyleObizhaevaInvarianceEngine.compute_invariance_metrics(
        price=100.0,
        daily_volume_shares=5_000_000.0,
        annual_volatility=0.25,
        order_size_shares=20_000.0,
    )

    assert isinstance(res, MicrostructureInvarianceResult)
    assert res.invariant_bet_size_shares > 0.0
    assert res.invariant_bet_size_usd > 0.0
    assert res.business_time_velocity > 0.0
    assert res.meta_order_price_impact_bps > 0.0
    assert res.predicted_bid_ask_spread_bps > 0.0
    assert res.execution_risk_cost_usd > 0.0

    # Verify scaling property: A larger order size increases price impact
    larger_res = KyleObizhaevaInvarianceEngine.compute_invariance_metrics(
        price=100.0,
        daily_volume_shares=5_000_000.0,
        annual_volatility=0.25,
        order_size_shares=80_000.0,
    )
    assert larger_res.meta_order_price_impact_bps > res.meta_order_price_impact_bps
    # (80k / 20k)^(1/3) = 4^(1/3) ~ 1.5874
    expected_impact_ratio = (80000.0 / 20000.0) ** (1.0 / 3.0)
    actual_ratio = larger_res.meta_order_price_impact_bps / res.meta_order_price_impact_bps
    assert pytest.approx(actual_ratio, rel=1e-3) == expected_impact_ratio

    # Higher volatility increases predicted spread
    high_vol_res = KyleObizhaevaInvarianceEngine.compute_invariance_metrics(
        price=100.0,
        daily_volume_shares=5_000_000.0,
        annual_volatility=0.50,
        order_size_shares=20_000.0,
    )
    assert high_vol_res.predicted_bid_ask_spread_bps > res.predicted_bid_ask_spread_bps

    # Validation errors
    with pytest.raises(ValueError, match="strictly positive"):
        KyleObizhaevaInvarianceEngine.compute_invariance_metrics(
            price=-50.0,
            daily_volume_shares=1000.0,
            annual_volatility=0.2,
            order_size_shares=10.0,
        )
