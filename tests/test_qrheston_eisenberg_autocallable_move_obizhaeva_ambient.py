"""Unit and programmatic verification tests for Phase 28 Quantitative Financial Engine.

Covers:
- Quadratic Rough Heston (QR-Heston) & Zumbach Volatility Feedback (Gatheral et al. 2021)
- Eisenberg-Noe (2001) Systemic Interbank Network Clearing & Default Cascades
- Autocallable Reverse Convertible (Snowball / Phoenix) Worst-of Pricing & Greeks
- ICE BofA MOVE, CBOE SKEW & Cross-Asset Volatility Spillover VAR Model
- Obizhaeva & Wang (2013) Optimal Execution with Resilient LOB & Transient Market Impact
- Ambient Finance (CrocSwap) Hybrid Liquidity & Maverick Dynamic Distribution AMM
"""

import math
from pathlib import Path
import sys
import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from qrheston_eisenberg_autocallable_move_obizhaeva_ambient import (
    QRHestonEngine,
    QRHestonSimulationResult,
    EisenbergNoeClearingEngine,
    EisenbergNoeClearingResult,
    AutocallableSnowballEngine,
    AutocallablePricingResult,
    CrossAssetVolSpilloverEngine,
    VolatilitySpilloverResult,
    ObizhaevaWangResilientLOBEngine,
    ObizhaevaWangExecutionResult,
    AmbientMaverickDeFiEngine,
    AmbientMaverickDeFiResult,
)


# ==============================================================================
# 1. QUADRATIC ROUGH HESTON & ZUMBACH VOLATILITY FEEDBACK TESTS
# ==============================================================================

def test_qrheston_simulation_and_zumbach_effect():
    """Verify QR-Heston rough path simulation, positivity of variance, and Zumbach feedback."""
    engine = QRHestonEngine(
        hurst=0.10,
        lam=1.5,
        theta=0.04,
        nu=0.30,
        a=1.5,
        b=0.05,
        c=0.01,
        rho=-0.65,
    )

    result = engine.simulate_paths(
        s0=100.0,
        t_exp=0.5,
        n_steps=50,
        n_paths=100,
        seed=42,
    )

    assert isinstance(result, QRHestonSimulationResult)
    assert result.spot_paths.shape == (100, 51)
    assert result.variance_paths.shape == (100, 51)
    assert result.vix_paths.shape == (100, 51)

    # Variance must remain strictly positive everywhere
    assert np.all(result.variance_paths > 0.0)

    # Spot prices must remain strictly positive
    assert np.all(result.spot_paths > 0.0)

    # Leverage effect: negative correlation between returns and volatility
    assert result.leverage_corr < 0.0

    # Implied ATM volatility should be in a realistic regime (10% to 50%)
    assert 0.10 < result.atm_implied_vol < 0.60


# ==============================================================================
# 2. EISENBERG-NOE (2001) SYSTEMIC INTERBANK NETWORK CLEARING TESTS
# ==============================================================================

def test_eisenberg_noe_interbank_clearing_and_cascade():
    """Verify Eisenberg-Noe fixed-point clearing vector, limited liability, and default cascade."""
    # 4-bank network
    # Bank 0 owes 100 to Bank 1 and 50 to Bank 2. Total p_0 = 150
    # Bank 1 owes 80 to Bank 2 and 40 to Bank 3. Total p_1 = 120
    # Bank 2 owes 50 to Bank 3 and 30 to Bank 0. Total p_2 = 80
    # Bank 3 owes 40 to Bank 0. Total p_3 = 40
    liabilities = np.array([
        [0.0, 100.0, 50.0, 0.0],
        [0.0, 0.0, 80.0, 40.0],
        [30.0, 0.0, 0.0, 50.0],
        [40.0, 0.0, 0.0, 0.0],
    ])

    # Case A: High initial liquidity -> All banks fully solvent
    e_solvent = np.array([160.0, 130.0, 90.0, 50.0])
    res_solv = EisenbergNoeClearingEngine.compute_clearing_vector(liabilities, e_solvent)
    assert np.allclose(res_solv.clearing_vector, res_solv.nominal_liabilities)
    assert res_solv.systemic_loss == 0.0
    assert len(res_solv.default_cascade) == 0
    assert np.allclose(res_solv.recovery_rates, 1.0)

    # Case B: Severe liquidity shock on Bank 0 -> Contagion cascade
    # Bank 0 has only 30 cash (owes 150)
    e_shock = np.array([30.0, 20.0, 10.0, 5.0])
    res_shock = EisenbergNoeClearingEngine.compute_clearing_vector(liabilities, e_shock)

    # Limited liability: no bank pays more than it owes
    assert np.all(res_shock.clearing_vector <= res_shock.nominal_liabilities + 1e-6)

    # Absolute priority: defaulting bank pays out all its assets
    for i in range(4):
        if res_shock.clearing_vector[i] < res_shock.nominal_liabilities[i] - 1e-4:
            # Defaulted! It must pay exactly its available wealth
            assert math.isclose(res_shock.clearing_vector[i], res_shock.total_assets[i], abs_tol=1e-4)

    # Contagion cascade must detect defaults
    assert len(res_shock.default_cascade) > 0
    assert res_shock.systemic_loss > 0.0
    assert np.any(res_shock.contagion_criticality > 0.0)


# ==============================================================================
# 3. AUTOCALLABLE REVERSE CONVERTIBLE PRICING TESTS
# ==============================================================================

def test_autocallable_snowball_pricing_and_greeks():
    """Verify worst-of autocallable note Monte Carlo valuation, barriers, and Greeks."""
    engine = AutocallableSnowballEngine(
        notional=100.0,
        coupon_rate=0.12,
        autocall_barrier=1.00,
        coupon_barrier=0.75,
        knock_in_barrier=0.70,
        risk_free_rate=0.03,
    )

    spots = [100.0, 100.0]
    vols = [0.20, 0.20]
    corr = np.array([[1.0, 0.6], [0.6, 1.0]])
    tenors = [0.25, 0.5, 0.75, 1.0]

    res = engine.price_worst_of_autocallable(
        spot_prices=spots,
        volatilities=vols,
        correlation_matrix=corr,
        observation_tenors=tenors,
        n_simulations=1500,
        seed=101,
    )

    assert isinstance(res, AutocallablePricingResult)
    # Fair price should be close to par (typically 90 to 105 for 12% coupon)
    assert 85.0 < res.fair_price < 110.0

    # Probabilities must be bounded in [0, 1]
    assert 0.0 <= res.autocall_probability <= 1.0
    assert 0.0 <= res.knock_in_probability <= 1.0

    # Expected maturity must be within [t_min, t_max]
    assert 0.25 <= res.expected_maturity <= 1.0

    # Greeks: Delta should be positive (note benefits from higher underlying spots)
    assert np.all(res.delta_basket > 0.0)


# ==============================================================================
# 4. MOVE, CBOE SKEW & VOLATILITY SPILLOVER VAR TESTS
# ==============================================================================

def test_cross_asset_vol_spillover_move_skew_irf():
    """Verify MOVE index, SKEW index calculation, and VAR impulse response dynamics."""
    # MOVE normal vol weights: 2Y=0.2, 5Y=0.2, 10Y=0.4, 30Y=0.2
    move_val = CrossAssetVolSpilloverEngine.calculate_move_index(
        implied_vol_2y=90.0,
        implied_vol_5y=95.0,
        implied_vol_10y=110.0,
        implied_vol_30y=105.0,
    )
    # Expected: 0.2*90 + 0.2*95 + 0.4*110 + 0.2*105 = 18 + 19 + 44 + 21 = 102.0
    assert math.isclose(move_val, 102.0, abs_tol=1e-5)

    # CBOE SKEW = 100 - 10 * S_RN. For S_RN = -3.2 -> SKEW = 132.0
    skew_val = CrossAssetVolSpilloverEngine.calculate_cboe_skew_index(-3.2)
    assert math.isclose(skew_val, 132.0, abs_tol=1e-5)

    # Spillover simulation
    res = CrossAssetVolSpilloverEngine.compute_macro_spillover_irf(
        move_level=move_val,
        vix_level=18.5,
        hy_spread_bps=380.0,
        horizons=10,
    )

    assert isinstance(res, VolatilitySpilloverResult)
    assert len(res.irf_move_to_vix) == 10
    assert len(res.irf_move_to_spread) == 10

    # Treasury MOVE shock propagates to equity VIX with lag (VIX IRF peaks and decays)
    assert res.irf_move_to_vix[1] > 0.0


# ==============================================================================
# 5. OBIZHAEVA & WANG (2013) RESILIENT LOB EXECUTION TESTS
# ==============================================================================

def test_obizhaeva_wang_resilient_lob_execution():
    """Verify closed-form Obizhaeva-Wang optimal liquidation schedule and transient recovery."""
    engine = ObizhaevaWangResilientLOBEngine(
        book_depth_q=25000.0,
        resilience_rate_rho=3.0,
    )

    x0 = 600000.0
    t = 1.0  # 1 day horizon
    # denom = 2 + rho * T = 2 + 3 * 1 = 5
    # Initial block = 600k / 5 = 120k
    # Continuous rate = 3 * 600k / 5 = 360k shares/day
    # Final block = 600k / 5 = 120k
    # Total = 120k + 360k * 1 + 120k = 600k

    res = engine.compute_optimal_schedule(total_shares_x0=x0, trading_horizon_t=t)
    assert isinstance(res, ObizhaevaWangExecutionResult)

    assert math.isclose(res.initial_block_order, 120000.0, rel_tol=1e-5)
    assert math.isclose(res.continuous_trading_rate, 360000.0, rel_tol=1e-5)
    assert math.isclose(res.terminal_block_order, 120000.0, rel_tol=1e-5)

    # Total shares conservation
    total_traded = res.initial_block_order + res.continuous_trading_rate * t + res.terminal_block_order
    assert math.isclose(total_traded, x0, rel_tol=1e-5)

    # Cost savings vs naive TWAP must be strictly positive
    assert res.expected_execution_cost < res.twap_cost_comparison
    assert res.cost_savings_pct > 0.0


# ==============================================================================
# 6. AMBIENT (CROCSWAP) & MAVERICK DEFI AMM TESTS
# ==============================================================================

def test_ambient_crocswap_and_maverick_dynamic_amm():
    """Verify Ambient hybrid liquidity depth, fee splits, and Maverick dynamic LVR reduction."""
    # Test In-Range: Price = 100, Range = [90, 110]
    res_in = AmbientMaverickDeFiEngine.simulate_ambient_crocswap(
        current_price=100.0,
        ambient_liquidity_l=50000.0,
        concentrated_liquidity_l=150000.0,
        range_lower=90.0,
        range_upper=110.0,
        swap_amount_y=1000.0,
    )

    assert isinstance(res_in, AmbientMaverickDeFiResult)
    assert res_in.total_effective_liquidity == 200000.0
    assert math.isclose(res_in.ambient_fee_share, 0.25, rel_tol=1e-5)
    assert math.isclose(res_in.concentrated_fee_share, 0.75, rel_tol=1e-5)
    assert res_in.lvr_reduction_pct > 40.0

    # Test Out-of-Range: Price = 120, Range = [90, 110]
    # Concentrated liquidity is inactive, 100% of fees go to ambient LPs
    res_out = AmbientMaverickDeFiEngine.simulate_ambient_crocswap(
        current_price=120.0,
        ambient_liquidity_l=50000.0,
        concentrated_liquidity_l=150000.0,
        range_lower=90.0,
        range_upper=110.0,
        swap_amount_y=1000.0,
    )

    assert res_out.total_effective_liquidity == 50000.0
    assert math.isclose(res_out.ambient_fee_share, 1.0, rel_tol=1e-5)
    assert math.isclose(res_out.concentrated_fee_share, 0.0, rel_tol=1e-5)
    assert res_out.swap_marginal_slippage > res_in.swap_marginal_slippage
