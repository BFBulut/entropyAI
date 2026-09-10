"""Automated pytest suite for Phase 27: Quantitative Financial Engineering.

Tests:
1. Duffie & Singleton (1999) CDS Hazard Rate Bootstrap & Pricing
2. Kupiec (1995) POF & Christoffersen (1998) VaR Backtesting
3. Basel Traffic Light Multipliers
4. Amihud (2002) Illiquidity Ratio & Pastor-Stambaugh (2003) Liquidity Reversal
5. Black-Derman-Toy (1990) Short-Rate Lattice & Callable Bond Backward Induction
6. Bjerksund-Stensland (1993/2002) Analytical American Option & Greeks
7. Hansen-Jagannathan (1991) SDF Volatility Bounds & CCAPM Equity Premium Puzzle
"""

from pathlib import Path
import sys
import pytest
import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from duffie_kupiec_amihud_bdt_bjerksund_hansen import (
    DuffieSingletonCDSEngine,
    VaRBacktestingEngine,
    LiquidityDynamicsEngine,
    BlackDermanToyLatticeEngine,
    BjerksundStenslandEngine,
    HansenJagannathanEngine,
)


# ==============================================================================
# 1. DUFFIE & SINGLETON CDS BOOTSTRAP TESTS
# ==============================================================================

def test_cds_hazard_rate_bootstrap_and_survival():
    mats = [1.0, 2.0, 3.0, 5.0, 10.0]
    spreads = [60.0, 85.0, 110.0, 140.0, 180.0]
    rec = 0.40
    r = 0.03

    boot = DuffieSingletonCDSEngine.bootstrap_hazard_rates(
        maturities=mats,
        spreads_bps=spreads,
        recovery_rate=rec,
        risk_free_rate=r
    )

    assert len(boot.hazard_rates) == len(mats)
    assert len(boot.survival_probabilities) == len(mats)

    # All hazard rates must be strictly positive
    for h in boot.hazard_rates:
        assert h > 0.0, f"Hazard rate must be positive, got {h}"

    # Survival probabilities must be strictly decreasing
    for i in range(len(boot.survival_probabilities) - 1):
        assert boot.survival_probabilities[i] > boot.survival_probabilities[i + 1]

    # Survival probability at 10Y must be less than 1.0
    assert 0.0 < boot.survival_probabilities[-1] < 1.0


def test_cds_contract_pricing_and_upfront():
    mats = [1.0, 2.0, 3.0, 5.0]
    spreads = [50.0, 75.0, 100.0, 130.0]
    boot = DuffieSingletonCDSEngine.bootstrap_hazard_rates(mats, spreads)

    # Price contract with spread equal to par spread at 5Y (130 bps)
    val_par = DuffieSingletonCDSEngine.price_cds(
        contract_spread_bps=130.0,
        maturity=5.0,
        bootstrap_result=boot,
        notional=10_000_000.0
    )

    # Par spread should closely match 130 bps (+- 2 bps)
    assert abs(val_par.par_spread_bps - 130.0) < 2.5
    # Net present value should be near zero for par contract
    assert abs(val_par.net_present_value) < 25_000.0

    # If traded at 100 bps (below par 130 bps), protection buyer must pay upfront
    val_below = DuffieSingletonCDSEngine.price_cds(
        contract_spread_bps=100.0,
        maturity=5.0,
        bootstrap_result=boot,
        notional=10_000_000.0
    )
    assert val_below.net_present_value > 0.0
    assert val_below.upfront_amount > 0.0


# ==============================================================================
# 2. KUPIEC POF, CHRISTOFFERSEN & BASEL TRAFFIC LIGHT TESTS
# ==============================================================================

def test_kupiec_pof_and_basel_traffic_light():
    # Scenario A: 2 violations in 250 days for 99% VaR (expected = 2.5) -> Green zone
    res_green = VaRBacktestingEngine.kupiec_pof_test(violations=2, total_observations=250, var_confidence=0.99)
    assert res_green.h0_accepted_5pct is True
    assert res_green.observed_failure_rate == 0.008

    traffic_green = VaRBacktestingEngine.basel_traffic_light(violations=2, total_observations=250)
    assert "Yeşil" in traffic_green.zone
    assert traffic_green.capital_multiplier == 3.00

    # Scenario B: 7 violations in 250 days -> Yellow zone
    traffic_yellow = VaRBacktestingEngine.basel_traffic_light(violations=7, total_observations=250)
    assert "Sarı" in traffic_yellow.zone
    assert traffic_yellow.capital_multiplier > 3.00

    # Scenario C: 15 violations in 250 days -> Red zone, H0 rejected
    res_red = VaRBacktestingEngine.kupiec_pof_test(violations=15, total_observations=250, var_confidence=0.99)
    assert res_red.h0_accepted_5pct is False

    traffic_red = VaRBacktestingEngine.basel_traffic_light(violations=15, total_observations=250)
    assert "Kırmızı" in traffic_red.zone
    assert traffic_red.capital_multiplier == 4.00


def test_christoffersen_independence_and_clustering():
    # Sequence with independent violations spread across 250 days
    hits_indep = [0] * 250
    hits_indep[30] = 1
    hits_indep[90] = 1
    hits_indep[170] = 1

    kupiec_ind, chris_ind = VaRBacktestingEngine.christoffersen_test(hits_indep, var_confidence=0.99)
    assert chris_ind.independence_accepted_5pct is True
    assert chris_ind.clustering_detected is False

    # Sequence with clustered violations (3 in a row, indicating volatility clustering blindness)
    hits_cluster = [0] * 250
    hits_cluster[50] = 1
    hits_cluster[51] = 1
    hits_cluster[52] = 1
    hits_cluster[53] = 1

    kupiec_cl, chris_cl = VaRBacktestingEngine.christoffersen_test(hits_cluster, var_confidence=0.99)
    # Consecutive hits yield high pi11
    assert chris_cl.pi11 > chris_cl.pi01
    assert chris_cl.clustering_detected is True


# ==============================================================================
# 3. AMIHUD ILLIQUIDITY & PASTOR-STAMBAUGH TESTS
# ==============================================================================

def test_amihud_illiquidity_ratio():
    returns = [0.01, -0.02, 0.005, -0.015, 0.03]
    high_vols = [100_000_000, 120_000_000, 95_000_000, 110_000_000, 130_000_000]
    low_vols = [1_000_000, 1_200_000, 950_000, 1_100_000, 1_300_000]

    res_liquid = LiquidityDynamicsEngine.calculate_amihud_illiquidity(returns, high_vols)
    res_illiquid = LiquidityDynamicsEngine.calculate_amihud_illiquidity(returns, low_vols)

    assert res_liquid.mean_illiq > 0.0
    assert res_illiquid.mean_illiq > res_liquid.mean_illiq * 50
    assert "Yüksek" in res_liquid.liquidity_tier or "Mega" in res_liquid.liquidity_tier


def test_pastor_stambaugh_reversal():
    np.random.seed(42)
    n = 100
    # Generate synthetic returns with reversal behavior
    order_flow = np.random.normal(0, 1, n)
    returns = np.zeros(n)
    for t in range(1, n):
        returns[t] = -0.05 * order_flow[t - 1] + np.random.normal(0, 0.01)

    dollar_volumes = (np.abs(order_flow) * 10_000_000 + 5_000_000).tolist()
    ps_res = LiquidityDynamicsEngine.calculate_pastor_stambaugh_reversal(
        stock_returns=returns.tolist(),
        dollar_volumes=dollar_volumes
    )
    assert ps_res.sample_size == n - 1
    assert isinstance(ps_res.gamma_coefficient, float)


# ==============================================================================
# 4. BLACK-DERMAN-TOY LATTICE & CALLABLE BOND TESTS
# ==============================================================================

def test_bdt_lattice_calibration_and_callable_bond():
    mats = [1.0, 2.0, 3.0, 4.0]
    # Zero bond prices corresponding to ~3% to 4% yields
    zeros = [0.97087, 0.94191, 0.91262, 0.88301]
    vols = [0.15, 0.15, 0.15, 0.15]

    lattice = BlackDermanToyLatticeEngine.calibrate_bdt_lattice(
        maturities=mats,
        zero_bond_prices=zeros,
        volatilities=vols,
        dt=1.0
    )

    assert lattice.time_steps == 4
    # Check calibration precision: model zero prices must closely match market zeros
    for mz, kz in zip(lattice.model_zero_prices, zeros):
        assert abs(mz - kz) < 1e-4

    # Valuation of 5% coupon straight vs callable bond (callable at 101 at t=2)
    res_bonds = BlackDermanToyLatticeEngine.price_callable_bond(
        lattice=lattice,
        face_value=100.0,
        coupon_rate=0.05,
        call_schedule={2: 101.0}
    )

    # Callable bond price can never exceed straight bond price
    assert res_bonds.callable_bond_price <= res_bonds.straight_bond_price + 1e-4
    assert res_bonds.embedded_call_option_value >= 0.0


# ==============================================================================
# 5. BJERKSUND-STENSLAND AMERICAN OPTION TESTS
# ==============================================================================

def test_bjerksund_stensland_american_call_and_put():
    s = 100.0
    k = 100.0
    t = 1.0
    r = 0.05
    q = 0.04  # High dividend yield creates early exercise incentive for call
    vol = 0.25

    res_call = BjerksundStenslandEngine.evaluate_option_with_greeks(
        spot=s, strike=k, maturity=t, rate=r, dividend_yield=q, volatility=vol, option_type="call"
    )
    # American call must be greater than or equal to European call
    assert res_call.american_price >= res_call.european_price - 1e-4
    assert res_call.early_exercise_premium >= 0.0
    assert 0.0 < res_call.delta < 1.0
    assert res_call.gamma > 0.0
    assert res_call.vega > 0.0

    # American put
    res_put = BjerksundStenslandEngine.evaluate_option_with_greeks(
        spot=s, strike=k, maturity=t, rate=r, dividend_yield=q, volatility=vol, option_type="put"
    )
    assert res_put.american_price >= res_put.european_price - 1e-4
    assert -1.0 < res_put.delta < 0.0


def test_bjerksund_stensland_deep_itm_early_exercise():
    # Spot far above trigger boundary with high dividend yield
    s = 200.0
    k = 100.0
    t = 1.0
    r = 0.03
    q = 0.08
    vol = 0.20

    res = BjerksundStenslandEngine.evaluate_option_with_greeks(
        spot=s, strike=k, maturity=t, rate=r, dividend_yield=q, volatility=vol, option_type="call"
    )
    # Should equal intrinsic value s - k = 100
    assert abs(res.american_price - (s - k)) < 1.0


# ==============================================================================
# 6. HANSEN-JAGANNATHAN VOLATILITY BOUNDS & CCAPM TESTS
# ==============================================================================

def test_hansen_jagannathan_bound_and_sharpe():
    # 3 assets with positive excess returns
    excess_mu = [0.06, 0.08, 0.05]
    cov = [
        [0.040, 0.015, 0.010],
        [0.015, 0.060, 0.020],
        [0.010, 0.020, 0.030]
    ]

    hj_res = HansenJagannathanEngine.compute_hj_volatility_bound(
        excess_returns=excess_mu,
        covariance_matrix=cov,
        risk_free_rate=0.03
    )

    assert hj_res.max_sharpe_ratio > 0.0
    assert hj_res.min_sdf_volatility_bound > 0.0
    # Tangency weights sum to ~1.0
    assert abs(sum(hj_res.optimal_tangency_weights) - 1.0) < 1e-3


def test_ccapm_equity_premium_puzzle_diagnostic():
    # Typical US historical parameters: consumption growth mean=1.8%, std=1.5%, equity Sharpe ~ 0.40
    # Low risk aversion gamma=2.0 fails the HJ bound
    diag_low_gamma = HansenJagannathanEngine.evaluate_ccapm_pricing_kernel(
        consumption_growth_mean=0.018,
        consumption_growth_std=0.015,
        risk_aversion_gamma=2.0,
        hj_bound=0.40
    )
    assert diag_low_gamma.equity_premium_puzzle_confirmed is True
    assert diag_low_gamma.theoretical_sdf_vol_ratio < 0.40

    # Unrealistic extreme risk aversion gamma=35 satisfies the HJ bound
    diag_high_gamma = HansenJagannathanEngine.evaluate_ccapm_pricing_kernel(
        consumption_growth_mean=0.018,
        consumption_growth_std=0.015,
        risk_aversion_gamma=35.0,
        hj_bound=0.40
    )
    assert diag_high_gamma.equity_premium_puzzle_confirmed is False
    assert diag_high_gamma.theoretical_sdf_vol_ratio >= 0.40
