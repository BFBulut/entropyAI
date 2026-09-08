"""Unit and programmatic verification tests for Phase 27 Quantitative Financial Engine.

Covers:
- Brace-Gatarek-Musiela (BGM) / Libor Market Model & Rebonato Swaption Volatility
- 2D Crank-Nicolson & Hundsdorfer-Verwer ADI Finite Difference Scheme
- Merton-KMV Structural Credit Model & Vasicek ASRF Basel Portfolio Capital
- Kyle (1985) Continuous Depth & Vayanos-Wang (2012) OTC Search Liquidity
- Leung & Li (2015) Ornstein-Uhlenbeck Optimal Double-Stopping Stat-Arb & Stop-Loss
- Pendle YieldSpace AMM Invariant & Aave v3 E-Mode De-Peg Cascade Physics
"""

import math
from pathlib import Path
import sys
import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from bgm_adi_kmv_vayanos_leung_pendle import (
    BGMForwardMarketModelEngine,
    ADI2DFiniteDifferenceEngine,
    KMVVasicekCreditEngine,
    KyleVayanosMarketMicrostructureEngine,
    LeungLiOptimalStoppingEngine,
    PendleAaveDeFiEngine,
)


def test_bgm_forward_market_model_and_rebonato():
    """Verify BGM forward curve discount factors, Black-76 caplets, and Rebonato swaption vol."""
    tenors = [0.5, 1.0, 1.5, 2.0, 2.5]
    forwards = np.array([0.035, 0.038, 0.040, 0.042])
    vols = np.array([0.20, 0.18, 0.17, 0.16])
    delta_t = 0.5

    # 1. Discount factors
    discounts = BGMForwardMarketModelEngine.discount_factors_from_forwards(forwards, delta_t)
    assert len(discounts) == len(forwards) + 1
    assert discounts[0] == 1.0
    for k in range(len(forwards)):
        assert discounts[k + 1] < discounts[k]
        expected_p = discounts[k] / (1.0 + delta_t * forwards[k])
        assert math.isclose(discounts[k + 1], expected_p, rel_tol=1e-5)

    # 2. Black-76 Caplet
    p_end = discounts[1]
    caplet_price = BGMForwardMarketModelEngine.calculate_caplet_black76(
        forward_rate=forwards[0],
        strike=0.035,
        tau_start=0.5,
        tau_end=1.0,
        vol=vols[0],
        discount_factor_end=p_end,
    )
    assert caplet_price > 0.0
    assert caplet_price < forwards[0] * delta_t * p_end

    # 3. Correlation Matrix & Rebonato Swaption Volatility
    n = len(forwards)
    corr = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            corr[i, j] = math.exp(-0.05 * abs(tenors[i] - tenors[j]))

    reb_vol = BGMForwardMarketModelEngine.rebonato_swaption_vol(
        tenors=tenors,
        forward_rates=forwards,
        volatilities=vols,
        corr_matrix=corr,
        swap_start_idx=0,
        swap_end_idx=n,
    )
    assert 0.10 < reb_vol < 0.25

    # 4. Monte Carlo Forward Curve Simulation
    sim_res = BGMForwardMarketModelEngine.simulate_bgm_spot_measure(
        tenors=tenors,
        forward_rates=forwards,
        volatilities=vols,
        corr_matrix=corr,
        num_paths=300,
        num_steps=20,
        seed=42,
    )
    assert sim_res.forward_paths.shape == (300, 21, 4)
    assert len(sim_res.black76_caplet_prices) == 4
    assert len(sim_res.mc_caplet_prices) == 4
    for b_p, m_p in zip(sim_res.black76_caplet_prices, sim_res.mc_caplet_prices):
        assert b_p >= 0.0
        assert m_p >= 0.0


def test_adi_2d_spread_option_pde():
    """Verify Hundsdorfer-Verwer ADI scheme for European and American 2-asset spread options."""
    spot1 = 100.0
    spot2 = 95.0
    strike = 5.0
    r = 0.03
    sigma1 = 0.25
    sigma2 = 0.20
    rho = 0.5
    maturity = 0.5

    # European Spread Option
    res_euro = ADI2DFiniteDifferenceEngine.solve_spread_option_adi(
        spot1=spot1,
        spot2=spot2,
        strike=strike,
        r=r,
        sigma1=sigma1,
        sigma2=sigma2,
        rho=rho,
        maturity=maturity,
        n_s1=25,
        n_s2=25,
        n_t=15,
        is_american=False,
    )
    assert res_euro.price_at_spot > 0.0
    assert res_euro.delta_s1 > 0.0  # Long asset 1
    assert res_euro.delta_s2 < 0.0  # Short asset 2

    # American Spread Option
    res_amer = ADI2DFiniteDifferenceEngine.solve_spread_option_adi(
        spot1=spot1,
        spot2=spot2,
        strike=strike,
        r=r,
        sigma1=sigma1,
        sigma2=sigma2,
        rho=rho,
        maturity=maturity,
        n_s1=25,
        n_s2=25,
        n_t=15,
        is_american=True,
    )
    # American option value should be at least European option value
    assert res_amer.price_at_spot >= res_euro.price_at_spot - 1e-4
    intrinsic = max(spot1 - spot2 - strike, 0.0)
    assert res_amer.price_at_spot >= intrinsic - 1e-4


def test_kmv_structural_model_and_vasicek_asrf():
    """Verify Merton-KMV asset value solver and Basel Vasicek ASRF portfolio regulatory capital."""
    equity_val = 50_000_000.0
    equity_vol = 0.40
    debt_nominal = 70_000_000.0
    r = 0.04
    t = 1.0

    kmv_res = KMVVasicekCreditEngine.solve_kmv_asset_parameters(
        equity_val=equity_val,
        equity_vol=equity_vol,
        debt_nominal=debt_nominal,
        r=r,
        t=t,
    )
    assert kmv_res.asset_value > equity_val
    assert kmv_res.asset_volatility < equity_vol
    assert kmv_res.distance_to_default > 0.0
    assert 0.0 < kmv_res.expected_default_frequency < 0.5
    assert 0.0 < kmv_res.leverage_ratio < 1.0

    # Vasicek ASRF Basel Portfolio Capital
    pd = 0.015  # 1.5% PD
    lgd = 0.45
    vas_res = KMVVasicekCreditEngine.calculate_vasicek_asrf(
        pd=pd,
        lgd=lgd,
        confidence_level=0.999,
        maturity_years=2.5,
        ead=1_000_000.0,
    )
    assert vas_res.var_capital_pct > vas_res.expected_loss_pct
    assert vas_res.unexpected_loss_capital_pct > 0.0
    assert vas_res.rwa_per_million > 0.0
    assert vas_res.maturity_adjustment > 0.0


def test_kyle_continuous_and_vayanos_otc():
    """Verify Kyle continuous price impact and Vayanos-Wang search-and-bargaining OTC discounts."""
    # Kyle continuous auction
    kyle_res = KyleVayanosMarketMicrostructureEngine.solve_kyle_continuous(
        prior_mean=100.0,
        prior_var=25.0,
        noise_var_rate=1.0,
        horizon_t=1.0,
        true_value=108.0,
        num_steps=40,
        seed=42,
    )
    assert kyle_res.lambda_depth > 0.0
    assert kyle_res.beta_trading > 0.0
    assert kyle_res.expected_profit > 0.0
    assert len(kyle_res.price_trajectory) == 41

    # Vayanos-Wang OTC spread
    vw_res = KyleVayanosMarketMicrostructureEngine.calculate_vayanos_wang_otc_spread(
        unconstrained_price=100.0,
        low_utility_flow=2.0,
        high_utility_flow=5.0,
        r=0.05,
        search_intensity=2.0,
        dealer_inventory=10.0,
        dealer_carrying_cost=0.10,
        dealer_bargaining_power=0.6,
    )
    assert vw_res.dealer_bid_price < vw_res.unconstrained_price
    assert vw_res.dealer_ask_price > vw_res.unconstrained_price
    assert vw_res.bid_ask_spread > 0.0
    assert vw_res.illiquidity_discount_pct > 0.0
    assert vw_res.search_friction_component > 0.0


def test_leung_li_optimal_stopping_stat_arb():
    """Verify Leung & Li Ornstein-Uhlenbeck optimal entry, exit, and stop-loss boundaries."""
    theta = 2.5
    mu = 0.0
    sigma = 0.15
    r = 0.03
    c_entry = 0.002
    c_exit = 0.002

    policy = LeungLiOptimalStoppingEngine.calculate_optimal_boundaries(
        theta=theta,
        mu=mu,
        sigma=sigma,
        r=r,
        c_entry=c_entry,
        c_exit=c_exit,
    )
    # Entry level must be below mean, exit level must be above mean
    assert policy.optimal_entry_level < mu
    assert policy.optimal_exit_level > mu
    # Stop-loss must be strictly below entry level
    assert policy.stop_loss_level < policy.optimal_entry_level
    # Expected net profit should be positive
    assert policy.expected_net_profit > 0.0
    assert policy.expected_entry_delay > 0.0
    assert policy.expected_trade_duration > 0.0


def test_pendle_yieldspace_and_aave_emode():
    """Verify Pendle YieldSpace AMM mechanics and Aave v3 E-Mode high-leverage risk engine."""
    # 1. Yield Stripping
    p_sy = 1.0
    apy = 0.05
    mat = 0.5
    p_pt, p_yt = PendleAaveDeFiEngine.strip_yield_tokens(p_sy, apy, mat)
    assert math.isclose(p_pt + p_yt, p_sy, rel_tol=1e-5)
    assert p_pt < 1.0
    assert p_yt > 0.0

    # 2. YieldSpace AMM swap
    swap_res = PendleAaveDeFiEngine.yieldspace_swap_pt(
        pt_reserve=1_000_000.0,
        asset_reserve=980_000.0,
        maturity_years=0.5,
        pt_in=10_000.0,
    )
    assert 0.0 < swap_res.pt_price <= 1.0
    assert swap_res.yt_price >= 0.0
    assert swap_res.implied_apy > 0.0
    assert swap_res.new_pt_reserve > 1_000_000.0
    assert swap_res.new_asset_reserve < 980_000.0

    # 3. Aave v3 E-Mode
    # 100 stETH collateral at $3000 = $300,000
    # Borrowing $285,000 worth of ETH debt at $3000 (95% LTV)
    emode_risk = PendleAaveDeFiEngine.evaluate_aave_emode(
        collateral_units=100.0,
        collateral_price=3000.0,
        borrowed_units=95.0,
        debt_price=3000.0,
        emode_ltv=0.97,
        emode_lt=0.98,
        liquidation_bonus=0.015,
    )
    assert emode_risk.health_factor > 1.0
    assert not emode_risk.is_liquidatable
    assert emode_risk.current_ltv == 0.95
    assert emode_risk.critical_depeg_pct < 0.0

    # 4. De-peg cascade simulation
    # stETH de-pegs from 1.0 down to 0.95
    depeg_path = [1.0, 0.99, 0.98, 0.965, 0.95]
    cascade = PendleAaveDeFiEngine.simulate_depeg_cascade(
        collateral_units=100.0,
        debt_units=97.0,  # Max initial leverage
        initial_price_ratio=1.0,
        depeg_path=depeg_path,
        emode_ltv=0.97,
        emode_lt=0.98,
    )
    assert len(cascade) == len(depeg_path)
    # At initial parity (1.0), HF should be > 1.0
    assert cascade[0]["health_factor"] > 1.0
    # At severe depeg (0.95), account should be flagged liquidatable
    assert cascade[-1]["health_factor"] < 1.0
    assert cascade[-1]["is_liquidatable"] is True
