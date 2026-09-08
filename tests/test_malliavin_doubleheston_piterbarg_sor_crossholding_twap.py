"""Automated Test Suite for Phase 30: Quantitative Financial Engineering Architecture.

Tests cover:
1. Malliavin Calculus Monte Carlo Greeks (Continuous & Discontinuous Payoffs)
2. Double Heston & Heston 3/2 Super-Linear Stochastic Volatility
3. Piterbarg Multi-Currency Collateral Discounting & CTD Optionality
4. Smart Order Routing (SOR) & Fragmented Venue Allocation
5. Cross-Holding / Circular Ownership Leontief Matrix & HoldCo Forensics
6. Uniswap v3/v4 TWAP Oracle Manipulation Economics & Arbitrageur Leakage
"""

import math
import sys
from pathlib import Path
import pytest
import numpy as np

# Ensure skills scripts are importable
scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from malliavin_doubleheston_piterbarg_sor_crossholding_twap import (
    MalliavinGreeksEngine,
    StochasticVolatilityAdvancedEngine,
    PiterbargCollateralDiscountEngine,
    CollateralCurrencyQuote,
    SmartOrderRoutingEngine,
    VenueQuote,
    CrossHoldingHoldCoEngine,
    UniswapTwapOracleManipulationEngine,
)


# ==============================================================================
# 1. MALLIAVIN CALCULUS MONTE CARLO GREEKS TESTS
# ==============================================================================

def test_malliavin_vanilla_call_convergence():
    """Verify that Malliavin Greeks match analytical Black-Scholes within confidence intervals."""
    s0 = 100.0
    k = 100.0
    r = 0.05
    sigma = 0.20
    t = 1.0

    res = MalliavinGreeksEngine.calculate_greeks(
        s0=s0, k_strike=k, r=r, sigma=sigma, t_mat=t, n_paths=150000, payoff_type="vanilla_call", seed=42
    )

    assert res.analytic_delta_benchmark is not None
    assert res.analytic_gamma_benchmark is not None

    # Delta should be within 3 standard errors
    delta_diff = abs(res.delta_malliavin - res.analytic_delta_benchmark)
    assert delta_diff < 3.0 * res.delta_standard_err
    assert abs(res.delta_malliavin - 0.6368) < 0.02

    # Gamma should be within 3.5 standard errors
    gamma_diff = abs(res.gamma_malliavin - res.analytic_gamma_benchmark)
    assert gamma_diff < 3.5 * res.gamma_standard_err
    assert res.gamma_malliavin > 0.0


def test_malliavin_digital_call_discontinuous():
    """Verify Malliavin Delta for discontinuous digital call matches analytical benchmark."""
    s0 = 100.0
    k = 100.0
    r = 0.05
    sigma = 0.20
    t = 1.0

    res = MalliavinGreeksEngine.calculate_greeks(
        s0=s0, k_strike=k, r=r, sigma=sigma, t_mat=t, n_paths=150000, payoff_type="digital_call", seed=123
    )

    assert res.is_discontinuous_payoff is True
    assert res.analytic_delta_benchmark is not None

    # Malliavin enables differentiation of indicator without Dirac delta explosion
    delta_diff = abs(res.delta_malliavin - res.analytic_delta_benchmark)
    assert delta_diff < 3.0 * res.delta_standard_err


def test_malliavin_input_validation():
    """Verify edge case validations."""
    with pytest.raises(ValueError, match="strictly positive"):
        MalliavinGreeksEngine.calculate_greeks(s0=-10, k_strike=100, r=0.05, sigma=0.2, t_mat=1.0)

    with pytest.raises(ValueError, match="at least 1000"):
        MalliavinGreeksEngine.calculate_greeks(s0=100, k_strike=100, r=0.05, sigma=0.2, t_mat=1.0, n_paths=500)


# ==============================================================================
# 2. DOUBLE HESTON & HESTON 3/2 VOLATILITY TESTS
# ==============================================================================

def test_double_heston_simulation():
    """Verify two-scale Double Heston variance dynamics."""
    res = StochasticVolatilityAdvancedEngine.simulate_double_heston(
        s0=100.0, r=0.04, v1_0=0.02, kappa1=10.0, theta1=0.02, sigma_v1=0.25, rho1=-0.7,
        v2_0=0.03, kappa2=0.5, theta2=0.03, sigma_v2=0.10, rho2=-0.2, t_mat=0.5, n_steps=50, n_paths=2000, seed=777
    )

    assert res.total_initial_variance == pytest.approx(0.05, abs=1e-6)
    assert res.fast_reverting_variance == 0.02
    assert res.slow_reverting_variance == 0.03
    assert res.feller_ratio_fast > 0.0
    assert res.feller_ratio_slow > 0.0
    assert res.simulated_terminal_mean > 50.0  # Asset should not explode
    assert res.integrated_variance_mean > 0.0


def test_heston_three_halves_super_linear():
    """Verify Heston 3/2 super-linear vol-of-vol model."""
    res = StochasticVolatilityAdvancedEngine.simulate_heston_three_halves(
        s0=100.0, r=0.03, v0=0.04, kappa=5.0, theta=0.04, epsilon=2.5, rho=-0.6,
        t_mat=0.25, n_steps=60, n_paths=3000, vix_strike=0.20, seed=888
    )

    assert res.super_linear_exponent == 1.5
    assert res.vix_call_proxy_price >= 0.0
    assert res.vol_of_vol_amplification > 0.0


# ==============================================================================
# 3. PITERBARG (2010) COLLATERAL DISCOUNTING TESTS
# ==============================================================================

def test_piterbarg_multi_currency_collateral_discounting():
    """Verify CTD collateral selection and embedded option valuation."""
    quotes = [
        CollateralCurrencyQuote(currency="USD", collateral_rate=0.050, domestic_foreign_basis=0.0, haircut=0.0),
        CollateralCurrencyQuote(currency="EUR", collateral_rate=0.035, domestic_foreign_basis=-0.010, haircut=1.0),
        CollateralCurrencyQuote(currency="JPY", collateral_rate=0.005, domestic_foreign_basis=-0.040, haircut=2.0)
    ]

    res = PiterbargCollateralDiscountEngine.calculate_discount_curve(
        notional=1000000.0, maturity_years=5.0, domestic_r=0.05, collateral_quotes=quotes, volatility_basis=0.02
    )

    # Rates:
    # USD: 0.05 - 0.0 + 0 = 0.050
    # EUR: 0.035 - (-0.010) + 0.01 = 0.055
    # JPY: 0.005 - (-0.040) + 0.02 = 0.065
    assert res.cheapest_to_deliver_currency == "USD"
    assert res.embedded_option_value_bps > 0.0
    assert res.piterbarg_discount_factor < 1.0
    assert res.zero_coupon_present_value < 1000000.0


def test_piterbarg_single_currency_no_option():
    """If only single currency is allowed, embedded CTD option is 0 bps."""
    quotes = [CollateralCurrencyQuote("USD", 0.045, 0.0, 0.0)]
    res = PiterbargCollateralDiscountEngine.calculate_discount_curve(100000.0, 2.0, 0.045, quotes)
    assert res.embedded_option_value_bps == 0.0
    assert res.effective_collateral_rate == pytest.approx(0.045, abs=1e-6)


# ==============================================================================
# 4. SMART ORDER ROUTING (SOR) TESTS
# ==============================================================================

def test_smart_order_routing_allocation():
    """Verify institutional block order routing across Lit and Dark venues."""
    venues = [
        VenueQuote("Lit_A", "lit", 20000, 50.00, 50.02, 0.002, 2.0, 1.0),
        VenueQuote("Lit_B", "lit", 30000, 50.00, 50.01, -0.001, 1.5, 1.0),  # cheaper lit
        VenueQuote("Dark_1", "dark", 25000, 50.00, 50.005, 0.0005, 6.0, 0.7, 0.002)
    ]

    res = SmartOrderRoutingEngine.optimize_route(order_size=40000, side="buy", venues=venues, urgency_parameter=0.3)

    total_routed = sum(res.routed_allocations.values())
    assert total_routed == pytest.approx(40000.0, abs=1e-5)
    assert res.dark_ratio > 0.0
    assert res.lit_ratio > 0.0
    # Cheaper lit venue Lit_B should receive substantial allocation
    assert res.routed_allocations["Lit_B"] > 0.0


def test_smart_order_routing_high_urgency_avoids_dark():
    """Higher urgency should reduce dark pool allocation in favor of immediate lit execution."""
    venues = [
        VenueQuote("Lit_A", "lit", 50000, 100.00, 100.02, 0.002, 1.0, 1.0),
        VenueQuote("Dark_1", "dark", 40000, 100.00, 100.01, 0.001, 5.0, 0.8, 0.005)
    ]

    res_patient = SmartOrderRoutingEngine.optimize_route(30000, "buy", venues, urgency_parameter=0.1)
    res_urgent = SmartOrderRoutingEngine.optimize_route(30000, "buy", venues, urgency_parameter=0.9)

    assert res_patient.dark_ratio > res_urgent.dark_ratio


# ==============================================================================
# 5. CROSS-HOLDING & HOLDCO FORENSICS TESTS
# ==============================================================================

def test_cross_holding_leontief_decomposition():
    """Verify Leontief inversion and forward equilibrium consistency."""
    standalone_ops = [4000.0, 2000.0, 1000.0]
    c_matrix = [
        [0.0, 0.30, 0.10],
        [0.10, 0.0, 0.20],
        [0.05, 0.10, 0.0]
    ]

    # Forward: V_m = (I - C)^(-1) * V_op
    eq_market_caps = CrossHoldingHoldCoEngine.solve_equilibrium_market_caps(standalone_ops, c_matrix)

    # Market caps must be strictly larger than standalone operating values due to cross-holdings
    for m, op in zip(eq_market_caps, standalone_ops):
        assert m > op

    # Backward: V_op = (I - C) * V_m
    analysis = CrossHoldingHoldCoEngine.analyze_cross_holdings(eq_market_caps, c_matrix)

    for reconstructed_op, orig_op in zip(analysis.standalone_operating_values, standalone_ops):
        assert reconstructed_op == pytest.approx(orig_op, abs=1e-4)

    assert analysis.double_counted_equity_volume > 0.0


def test_cross_holding_holdco_discount_and_unbundling():
    """Verify HoldCo discount against SOTP NAV and activist upside."""
    m_caps = [3000.0, 4000.0, 2500.0]
    c_matrix = [
        [0.0, 0.50, 0.40],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0]
    ]

    # HoldCo NAV = standalone (3000 - 0.5*4000 - 0.4*2500 = 0) + 2000 + 1000 = 3000M
    # If traded at 2100M:
    res = CrossHoldingHoldCoEngine.analyze_cross_holdings(
        m_caps, c_matrix, holdco_index=0, holdco_traded_market_cap=2100.0
    )

    assert res.holdco_market_cap == 2100.0
    assert res.holdco_nav == pytest.approx(3000.0, abs=1e-4)
    assert res.holdco_discount_percent == pytest.approx(30.0, abs=0.1)
    assert res.activist_unbundling_upside_percent == pytest.approx(42.86, abs=0.1)


# ==============================================================================
# 6. UNISWAP TWAP ORACLE MANIPULATION TESTS
# ==============================================================================

def test_uniswap_twap_oracle_manipulation_cost():
    """Verify TWAP manipulation cost calculation and economic unviability."""
    res = UniswapTwapOracleManipulationEngine.calculate_attack_cost(
        p0_true=1000.0,
        p_target=2000.0,
        window_seconds=1800,
        blocks_manipulated=5,
        block_time_seconds=12,
        pool_liquidity_l=1000000.0,
        protocol_exploit_gain=100000.0
    )

    assert res.single_block_slippage_cost > 0.0
    assert res.leakage_to_arbitrageurs_per_block > 0.0
    assert res.total_cumulative_manipulation_cost > res.single_block_slippage_cost
    assert res.resulting_twap_price > 1000.0
    assert res.resulting_twap_price < 2000.0  # TWAP lags spot manipulation
    assert res.is_attack_economically_viable is False  # Attack costs tens of millions, exploit is only $100k


def test_uniswap_twap_arbitrageur_leakage_zero_on_no_distortion():
    """If target price equals true price, arbitrageur leakage must be zero."""
    res = UniswapTwapOracleManipulationEngine.calculate_attack_cost(
        p0_true=1000.0,
        p_target=1000.0,
        window_seconds=1800,
        blocks_manipulated=5,
        pool_liquidity_l=1000000.0
    )

    assert res.leakage_to_arbitrageurs_per_block == pytest.approx(0.0, abs=1e-9)
    assert res.resulting_twap_price == pytest.approx(1000.0, abs=1e-6)
