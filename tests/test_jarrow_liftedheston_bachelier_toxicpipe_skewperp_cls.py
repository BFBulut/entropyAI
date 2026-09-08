"""Unit and integration test suite for Phase 31 Financial Engineering Engine.
Covers:
1. Jarrow-Yildirim (2003) Inflation Derivatives (ZCIS, Caplet/Floorlet Put-Call Parity)
2. Lifted Heston Multi-Factor Volatility (Rational kernel, simulation, rough skew scaling)
3. Louis Bachelier Normal Volatility (Negative WTI pricing, Greeks, implied vol solver)
4. Toxic Convertible PIPE & Death Spiral Arbitrage (Reflexive dilution, floor covenants)
5. Perpetual DEX Skew Funding & Pool Counterparty Risk (Delta exposure, velocity funding, insolvency)
6. CLS Multilateral Netting & FX Triangular Arbitrage (Conservation of money, netting efficiency, cross rate arbitrage)
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

from jarrow_liftedheston_bachelier_toxicpipe_skewperp_cls import (
    JarrowYildirimEngine,
    LiftedHestonEngine,
    BachelierPricingEngine,
    ToxicConvertibleForensicEngine,
    PerpDexPoolRiskEngine,
    CLSAndTriangularArbitrageEngine,
)


# ==============================================================================
# 1. JARROW-YILDIRIM TESTS
# ==============================================================================

def test_jarrow_yildirim_zcis_pricing():
    """Verify ZCIS fair rate, breakeven inflation rate and CPI forward index."""
    cpi_0 = 100.0
    nom_rate = 0.05
    real_rate = 0.02
    t_mat = 5.0
    survey_inf = 0.027

    res = JarrowYildirimEngine.price_zero_coupon_inflation_swap(
        cpi_0=cpi_0,
        nominal_zero_rate=nom_rate,
        real_zero_rate=real_rate,
        maturity=t_mat,
        survey_expected_inflation=survey_inf
    )

    assert res.maturity == 5.0
    assert math.isclose(res.breakeven_inflation_rate, 0.03, abs_tol=1e-5)
    # Fair ZCIS rate = exp(nom - real) - 1 approx
    expected_fair_zcis = math.exp(nom_rate - real_rate) - 1.0
    assert math.isclose(res.fair_zcis_rate, expected_fair_zcis, abs_tol=1e-4)
    assert res.expected_cpi_index > cpi_0
    assert math.isclose(res.inflation_risk_premium_estimate, 0.03 - survey_inf, abs_tol=1e-5)


def test_jarrow_yildirim_cap_floor_put_call_parity():
    """Verify Put-Call parity holds strictly for inflation caplet and floorlet."""
    cpi_0 = 100.0
    nom_rate = 0.04
    real_rate = 0.015
    sigma_inf = 0.02
    strike_rate = 0.025
    t_mat = 3.0

    res = JarrowYildirimEngine.price_inflation_cap_floor(
        cpi_0=cpi_0,
        nominal_rate=nom_rate,
        real_rate=real_rate,
        sigma_inflation=sigma_inf,
        strike_rate=strike_rate,
        maturity=t_mat
    )

    assert res.caplet_price > 0.0
    assert res.floorlet_price > 0.0
    assert res.put_call_parity_diff < 1e-12


def test_jarrow_yildirim_invalid_inputs():
    """Verify input validation for non-positive CPI or zero/negative maturity."""
    with pytest.raises(ValueError):
        JarrowYildirimEngine.price_zero_coupon_inflation_swap(0.0, 0.05, 0.02, 5.0)
    with pytest.raises(ValueError):
        JarrowYildirimEngine.price_inflation_cap_floor(100.0, 0.05, 0.02, -0.01, 0.025, 5.0)


# ==============================================================================
# 2. LIFTED HESTON TESTS
# ==============================================================================

def test_lifted_heston_rational_kernel_calibration():
    """Verify geometric node progression and positive weights for fractional kernel."""
    hurst_h = 0.12
    n_factors = 12
    c, x = LiftedHestonEngine.calibrate_rational_kernel(hurst_h, n_factors, t_max=1.5)

    assert len(c) == n_factors
    assert len(x) == n_factors
    assert np.all(c > 0.0)
    # Check strictly increasing geometric nodes
    assert np.all(np.diff(x) > 0.0)


def test_lifted_heston_variance_simulation():
    """Verify variance simulation remains positive and produces rough skew scaling."""
    res = LiftedHestonEngine.simulate_lifted_variance(
        v0=0.04,
        theta=0.04,
        nu_vol_of_vol=0.25,
        hurst_h=0.10,
        num_factors=8,
        t_mat=0.5,
        n_steps=100,
        seed=123
    )

    assert res.mean_variance > 0.0
    assert res.variance_std > 0.0
    assert len(res.sample_paths) == 10
    # Short term skew approx for H=0.10 is 0.01^(-0.4) ~ 6.3x
    assert res.short_term_skew_approx > 4.0


# ==============================================================================
# 3. LOUIS BACHELIER NORMAL VOLATILITY TESTS
# ==============================================================================

def test_bachelier_positive_underlying_put_call_parity():
    """Verify exact Put-Call Parity in Bachelier model: C - P = exp(-rT)*(F - K)."""
    fwd = 100.0
    strike = 105.0
    t_mat = 0.75
    sigma_n = 15.0
    r = 0.03

    res = BachelierPricingEngine.price_normal_option(fwd, strike, t_mat, sigma_n, r)

    disc = math.exp(-r * t_mat)
    parity_theoretical = disc * (fwd - strike)
    parity_actual = res.call_price - res.put_call_parity_put_price

    assert math.isclose(parity_actual, parity_theoretical, abs_tol=1e-10)
    assert 0.0 < res.delta < 1.0
    assert res.gamma > 0.0
    assert res.vega > 0.0
    assert res.is_negative_underlying is False
    assert res.black_implied_vol_atm_approx is not None


def test_bachelier_negative_underlying_pricing():
    """Verify option pricing on negative asset price (WTI Crude April 2020 collapse)."""
    fwd_negative = -37.63
    strike = -30.0
    t_mat = 0.10
    sigma_n = 25.0
    r = 0.0

    res = BachelierPricingEngine.price_normal_option(fwd_negative, strike, t_mat, sigma_n, r)

    assert res.is_negative_underlying is True
    assert res.call_price > 0.0
    assert res.put_call_parity_put_price > 0.0
    # Put-Call Parity with r=0: C - P = F - K = -37.63 - (-30.0) = -7.63
    assert math.isclose(res.call_price - res.put_call_parity_put_price, fwd_negative - strike, abs_tol=1e-10)


def test_bachelier_implied_vol_solver():
    """Verify Newton-Raphson solver accurately recovers input normal volatility."""
    fwd = 50.0
    strike = 52.0
    t_mat = 0.5
    true_sigma_n = 12.5
    r = 0.02

    res = BachelierPricingEngine.price_normal_option(fwd, strike, t_mat, true_sigma_n, r)
    recovered_sigma = BachelierPricingEngine.solve_implied_normal_vol(res.call_price, fwd, strike, t_mat, r)

    assert math.isclose(recovered_sigma, true_sigma_n, rel_tol=1e-5)


# ==============================================================================
# 4. TOXIC CONVERTIBLE PIPE TESTS
# ==============================================================================

def test_toxic_convertible_death_spiral_dilution():
    """Verify death spiral short-selling dynamics produce severe dilution and price decline."""
    debt = 2000000.0
    p0 = 10.0
    shares0 = 1000000.0

    res = ToxicConvertibleForensicEngine.simulate_death_spiral(
        debt_face_value=debt,
        initial_stock_price=p0,
        initial_shares_out=shares0,
        conversion_discount=0.25,
        kyle_lambda_impact=0.00001,
        short_volume_per_step=30000.0,
        conversion_floor_price=None,  # Uncapped death spiral
        max_steps=15
    )

    assert res.final_price < p0
    assert res.dilution_factor > 1.2
    assert res.total_short_profit > 0.0
    assert len(res.conversion_prices) == 15


def test_toxic_convertible_floor_protection():
    """Verify conversion floor halts conversion and signals debt restructuring/default."""
    debt = 5000000.0
    p0 = 2.0
    shares0 = 1000000.0
    floor = 1.0

    res = ToxicConvertibleForensicEngine.simulate_death_spiral(
        debt_face_value=debt,
        initial_stock_price=p0,
        initial_shares_out=shares0,
        conversion_discount=0.20,
        kyle_lambda_impact=0.00005,
        short_volume_per_step=20000.0,
        conversion_floor_price=floor,
        max_steps=10
    )

    assert res.is_company_bankrupt is True
    assert res.conversion_prices[-1] < floor


# ==============================================================================
# 5. PERPETUAL DEX SKEW FUNDING TESTS
# ==============================================================================

def test_perp_dex_pool_skew_funding_and_delta():
    """Verify pool delta is short when traders are net long, and funding rate is positive."""
    pool_liq = 10000000.0
    long_oi = 6000000.0
    short_oi = 2000000.0

    res = PerpDexPoolRiskEngine.evaluate_pool_state(
        pool_initial_liquidity=pool_liq,
        cumulative_fees_collected=200000.0,
        long_oi=long_oi,
        short_oi=short_oi,
        underlying_price_change_pct=0.05,
        skew_sensitivity_k=0.001
    )

    assert res.net_pool_delta_exposure == -4000000.0
    assert res.current_skew_funding_rate_hourly > 0.0  # Longs pay Shorts
    assert res.hourly_borrow_fee_long > res.hourly_borrow_fee_short
    assert res.is_pool_insolvent is False


def test_perp_dex_pool_insolvency_stress():
    """Verify pool insolvency detection under severe trader winning momentum."""
    pool_liq = 1000000.0
    long_oi = 15000000.0  # Heavy long leverage
    short_oi = 0.0

    # 10% price pump generates 1.5M trader profit, exceeding pool liquidity
    res = PerpDexPoolRiskEngine.evaluate_pool_state(
        pool_initial_liquidity=pool_liq,
        cumulative_fees_collected=50000.0,
        long_oi=long_oi,
        short_oi=short_oi,
        underlying_price_change_pct=0.10
    )

    assert res.is_pool_insolvent is True
    assert res.pool_nav == 0.0
    assert res.pool_drawdown_pct == 1.0


# ==============================================================================
# 6. CLS NETTING & FX TRIANGULAR ARBITRAGE TESTS
# ==============================================================================

def test_cls_multilateral_netting_conservation():
    """Verify multilateral netting satisfies conservation of money and reduces gross volume."""
    # 3x3 obligations matrix among 3 banks
    # Row i owes Column j
    mat = np.array([
        [0.0, 100.0, 50.0],
        [40.0, 0.0, 80.0],
        [90.0, 20.0, 0.0]
    ])
    banks = ["JPMorgan", "BNP Paribas", "Deutsche Bank"]

    res = CLSAndTriangularArbitrageEngine.calculate_multilateral_netting(mat, banks)

    assert res.gross_settlement_volume == 380.0
    assert res.is_conservation_of_money_satisfied is True
    assert res.net_funding_required < res.gross_settlement_volume
    assert res.netting_efficiency_pct > 60.0
    # Inflows - outflows sum to zero
    total_net = sum(res.institution_net_positions.values())
    assert math.isclose(total_net, 0.0, abs_tol=1e-7)


def test_fx_triangular_arbitrage_detection():
    """Verify detection of triangular arbitrage opportunities after spread and fees."""
    # Fair triangle: EUR/USD = 1.10, USD/JPY = 150.0 => EUR/JPY = 165.0
    pair_eur_usd = (1.0999, 1.1001)
    pair_usd_jpy = (149.98, 150.02)
    fair_eur_jpy = (164.95, 165.05)

    res_fair = CLSAndTriangularArbitrageEngine.detect_triangular_arbitrage(
        pair_eur_usd, pair_usd_jpy, fair_eur_jpy, fee_rate_bps=1.0
    )
    assert res_fair.is_profitable_after_fees is False

    # Arbitrage case: Direct EUR/JPY is artificially high at 168.00 / 168.05
    # One can sell EUR/JPY direct and buy synthetic
    dislocated_eur_jpy = (168.00, 168.05)
    res_arb = CLSAndTriangularArbitrageEngine.detect_triangular_arbitrage(
        pair_eur_usd, pair_usd_jpy, dislocated_eur_jpy, fee_rate_bps=1.0
    )
    assert res_arb.is_profitable_after_fees is True
    assert res_arb.arbitrage_direction == "Direct_Overpriced"
    assert res_arb.arbitrage_profit_bps > 100.0
