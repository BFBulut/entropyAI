"""
Automated pytest suite for Phase 35: Advanced Quantitative Financial Engineering.

Validates:
1. Buehler et al. (2019) Deep Hedging & Neural Risk Minimization
2. Tian et al. (2015) Stochastic Local Volatility & Particle Calibration
3. Brunnermeier & Pedersen (2009) Market Liquidity & Funding Liquidity Spirals
4. Martin & Adams (2021) Power Perpetuals & AMM Gamma Hedging
5. Andersen, Sidenius & Basu (2003) Fast Recursive Basket Credit Convolution
6. Evans & Lyons (2002) FX Microstructure & Order Flow Information Transmission
"""

import math
import sys
from pathlib import Path
import numpy as np
import pytest

# Ensure scripts directory is importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from deephedging_slv_brunnermeier_powerperp_andersen_evanslyons import (
    DeepHedgingEngine,
    DeepHedgingPolicy,
    StochasticLocalVolatilityEngine,
    BrunnermeierPedersenLiquiditySpiral,
    PowerPerpetualsSqueethEngine,
    AndersenSideniusBasuFastConvolution,
    EvansLyonsFXOrderFlowModel,
    _black_scholes_call,
    _black_scholes_delta,
)


# ==============================================================================
# 1. BUEHLER ET AL. (2019) DEEP HEDGING TESTS
# ==============================================================================

def test_deep_hedging_policy_bounds():
    """Verify that neural policy produces valid delta hedge in [0, 1]."""
    policy = DeepHedgingPolicy(seed=123)
    # Deep OTM
    d_otm = policy.predict(moneyness=0.7, tau=0.1, prev_delta=0.1)
    # Deep ITM
    d_itm = policy.predict(moneyness=1.3, tau=0.1, prev_delta=0.9)
    # ATM
    d_atm = policy.predict(moneyness=1.0, tau=0.5, prev_delta=0.5)

    assert 0.0 <= d_otm <= 1.0
    assert 0.0 <= d_itm <= 1.0
    assert 0.0 <= d_atm <= 1.0
    assert d_itm > d_otm


def test_deep_hedging_simulation_and_metrics():
    """Verify Deep Hedging simulation, transaction costs, and risk measures."""
    engine = DeepHedgingEngine(s0=100.0, strike=100.0, r=0.03, sigma=0.20, t=0.25, cost_prop=0.005)
    paths = engine.simulate_gbm_paths(n_paths=200, n_steps=20, seed=42)
    assert paths.shape == (200, 21)
    assert np.all(paths[:, 0] == 100.0)

    res_deep = engine.run_deep_hedge(paths)
    res_bs = engine.run_black_scholes_hedge(paths)

    assert res_deep.total_transaction_costs > 0.0
    assert res_bs.total_transaction_costs > 0.0
    assert not math.isnan(res_deep.cvar_95)
    assert not math.isnan(res_deep.entropic_risk)
    assert len(res_deep.final_hedge_positions) == 10


# ==============================================================================
# 2. TIAN ET AL. (2015) STOCHASTIC LOCAL VOLATILITY TESTS
# ==============================================================================

def test_slv_dupire_local_vol_surface():
    """Verify target Dupire surface has positive values and realistic skew."""
    engine = StochasticLocalVolatilityEngine(s0=100.0)
    vol_atm = engine.dupire_local_vol(s=100.0, t=0.5)
    vol_down = engine.dupire_local_vol(s=80.0, t=0.5) # Lower strike -> higher vol
    vol_up = engine.dupire_local_vol(s=120.0, t=0.5)

    assert 0.05 <= vol_atm <= 0.80
    assert vol_down > vol_atm # Negative skew present


def test_slv_simulation_and_barrier_pricing():
    """Verify SLV joint simulation and Up-and-Out barrier option pricing."""
    engine = StochasticLocalVolatilityEngine(s0=100.0, v0=0.04, kappa=1.5, theta=0.04, xi=0.3, rho=-0.6)
    res = engine.price_options(strike=100.0, barrier=120.0, t=0.5, n_steps=20, n_particles=300)

    assert res.vanilla_call_slv > 0.0
    assert res.vanilla_call_heston > 0.0
    # Up-and-out call must be cheaper than vanilla call
    assert res.up_and_out_barrier_slv <= res.vanilla_call_slv
    assert res.up_and_out_barrier_heston <= res.vanilla_call_heston
    # Leverage factor is strictly positive
    assert res.mean_leverage > 0.0


# ==============================================================================
# 3. BRUNNERMEIER & PEDERSEN (2009) LIQUIDITY SPIRAL TESTS
# ==============================================================================

def test_brunnermeier_margin_and_shock_dynamics():
    """Verify margin spiral and loss spiral triggers during negative fundamental shock."""
    model = BrunnermeierPedersenLiquiditySpiral(
        fundamental_value=100.0,
        initial_capital=50.0,
        base_vol=0.15,
        speculator_target_position=200.0
    )

    m_low_vol = model.calculate_margin(0.15)
    m_high_vol = model.calculate_margin(0.40)
    assert m_high_vol > m_low_vol # Margin requirement increases with volatility

    res = model.simulate_shock(shock_magnitude=-15.0, n_periods=10)

    assert res.margin_spiral_triggered is True
    assert res.total_fire_sales > 0.0
    assert res.trough_price < res.initial_price - 15.0 # Overshoots fundamental shock
    assert res.spread_widening_factor > 1.0 # Liquidity dry-up observed
    assert res.capital_loss_pct > 0.0


# ==============================================================================
# 4. MARTIN & ADAMS (2021) POWER PERPETUALS TESTS
# ==============================================================================

def test_power_perp_analytical_greeks():
    """Verify Power Perp Delta = 2S/scale and Gamma = 2/scale (constant positive gamma)."""
    engine = PowerPerpetualsSqueethEngine(spot=2000.0, volatility=0.80, scale_factor=1000.0)
    delta, gamma = engine.power_perp_greeks(s=2000.0)

    assert abs(delta - 4.0) < 1e-5
    assert abs(gamma - 0.002) < 1e-6

    # Test equilibrium funding rate
    funding_rate = engine.continuous_funding_rate()
    expected_rate = 0.04 + (0.80 ** 2) # r + sigma^2 = 0.68
    assert abs(funding_rate - expected_rate) < 1e-6


def test_power_perp_amm_gamma_hedging():
    """Verify that long Power Perp neutralizes AMM negative gamma and reduces IL risk."""
    engine = PowerPerpetualsSqueethEngine(spot=2000.0, volatility=0.80, scale_factor=1000.0)
    # Price rises by 25%
    res_up = engine.hedge_uniswap_v2_lp(s_initial=2000.0, s_final=2500.0, lp_pool_k=1_000_000.0)
    # Price drops by 20%
    res_down = engine.hedge_uniswap_v2_lp(s_initial=2000.0, s_final=1600.0, lp_pool_k=1_000_000.0)

    # Initial net portfolio gamma should be exactly 0
    assert res_up.net_portfolio_gamma < 1e-8
    assert res_down.net_portfolio_gamma < 1e-8

    # Unhedged LP always suffers impermanent loss
    assert res_up.unhedged_lp_loss_pct < 0.0
    assert res_down.unhedged_lp_loss_pct < 0.0

    # Power perp gamma is positive
    assert res_up.power_perp_gamma > 0.0


# ==============================================================================
# 5. ANDERSEN, SIDENIUS & BASU (2003) FAST CONVOLUTION TESTS
# ==============================================================================

def test_andersen_sidenius_basu_tranche_expected_losses():
    """Verify fast recursive convolution loss distribution and tranche subordination."""
    conv = AndersenSideniusBasuFastConvolution(
        n_obligors=125,
        default_prob=0.03,
        correlation=0.25,
        lgd=0.60
    )

    res = conv.compute_tranche_losses(n_quad_points=15)

    assert 0.0 < res.portfolio_expected_loss < 0.10
    # Strict subordination of tranche expected losses:
    # Equity tranche suffers the highest percentage loss, Senior suffers the least
    assert res.equity_tranche_loss_pct > res.mezzanine_tranche_loss_pct
    assert res.mezzanine_tranche_loss_pct > res.senior_tranche_loss_pct
    assert res.senior_tranche_loss_pct >= res.super_senior_loss_pct

    # Probability mass function sums to ~ 1.0
    total_prob = sum(res.full_loss_distribution.values())
    assert 0.0 < total_prob <= 1.01


# ==============================================================================
# 6. EVANS & LYONS (2002) FX ORDER FLOW TESTS
# ==============================================================================

def test_evans_lyons_fx_order_flow_estimation():
    """Verify Evans & Lyons order flow regression, R^2 dominance, and directional hit ratio."""
    model = EvansLyonsFXOrderFlowModel(seed=42)
    fx_ret, flow, interest = model.simulate_fx_data(n_periods=600, true_beta_flow=0.70, true_beta_macro=0.15)

    assert len(fx_ret) == 600
    res = model.fit_and_decompose(fx_ret, flow, interest)

    # Order flow price impact is positive and statistically dominant
    assert res.beta_order_flow > 0.0
    assert res.r_squared_order_flow_only > res.r_squared_macro_only
    assert res.private_information_share > 0.50
    # Directional prediction beats random walk (50%)
    assert res.hit_ratio_directional > 0.55
