"""Automated pytest suite for Phase 29: Advanced Quantitative Financial Engineering.

Tests:
1. Hagan et al. (2002) SABR Stochastic Volatility Model & Smile Calibration
2. Demeterfi-Derman-Kamal-Zou (1999) Variance Swap Replication & Convexity Adjustment
3. Garman & Kohlhagen (1983) Analytic FX Currency Option Pricing & Greeks
4. Merton (1976) Jump-Diffusion Option Pricing & Monte Carlo Cross-Validation
5. Continuous Kelly Criterion, Grossman-Zhou Drawdown Distribution & Ruin Analysis
6. Marcos López de Prado (2019) Hierarchical Equal Risk Contribution (HERC) Allocation
"""

from pathlib import Path
import sys
import math
import pytest
import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from sabr_varswap_fxgarman_mertonjump_kelly_herc import (
    SABRStochasticVolatilityEngine,
    VarianceSwapReplicationEngine,
    GarmanKohlhagenFXEngine,
    MertonJumpDiffusionEngine,
    ContinuousKellyGrowthEngine,
    HierarchicalEqualRiskContributionEngine,
    _black_scholes_call,
    _black_scholes_put,
)


# ==============================================================================
# 1. SABR STOCHASTIC VOLATILITY TESTS
# ==============================================================================

def test_sabr_atm_limit_consistency():
    """Verify that near-ATM implied volatility converges smoothly to exact ATM formula."""
    f = 100.0
    t = 1.0
    alpha = 0.25
    beta = 0.6
    rho = -0.3
    nu = 0.4

    atm_exact = SABRStochasticVolatilityEngine.implied_volatility(f, f, t, alpha, beta, rho, nu)
    near_atm = SABRStochasticVolatilityEngine.implied_volatility(f, f * 1.000001, t, alpha, beta, rho, nu)

    assert atm_exact > 0.0
    assert abs(atm_exact - near_atm) < 1e-4


def test_sabr_skew_direction():
    """Verify negative rho produces downward-sloping volatility skew (OTM puts > OTM calls)."""
    f = 100.0
    t = 1.0
    alpha = 2.0  # For beta=0.5, alpha / F^(1-beta) = 2.0 / 10 = 0.20 (20% ATM vol)
    beta = 0.5
    rho = -0.40  # Negative correlation -> negative skew
    nu = 0.35

    vol_low_k = SABRStochasticVolatilityEngine.implied_volatility(f, 80.0, t, alpha, beta, rho, nu)
    vol_atm = SABRStochasticVolatilityEngine.implied_volatility(f, 100.0, t, alpha, beta, rho, nu)
    vol_high_k = SABRStochasticVolatilityEngine.implied_volatility(f, 120.0, t, alpha, beta, rho, nu)

    assert vol_low_k > vol_atm > vol_high_k


def test_sabr_black76_put_call_parity():
    """Verify Black-76 call and put prices with SABR vol satisfy parity: C - P = exp(-rT)*(F - K)."""
    f = 105.0
    k = 100.0
    t = 0.75
    r = 0.04
    alpha = 0.22
    beta = 0.5
    rho = -0.2
    nu = 0.3

    call_p = SABRStochasticVolatilityEngine.price_black76(f, k, t, r, alpha, beta, rho, nu, is_call=True)
    put_p = SABRStochasticVolatilityEngine.price_black76(f, k, t, r, alpha, beta, rho, nu, is_call=False)

    expected_diff = math.exp(-r * t) * (f - k)
    assert abs((call_p - put_p) - expected_diff) < 1e-6


def test_sabr_calibration():
    """Verify calibration to synthetic smile recovers market volatilities with low RMSE."""
    f = 100.0
    t = 1.0
    strikes = [85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 115.0]
    market_vols = [0.24, 0.22, 0.205, 0.195, 0.190, 0.188, 0.192]

    res = SABRStochasticVolatilityEngine.calibrate_sabr(
        f=f, t=t, strikes=strikes, market_vols=market_vols, fixed_beta=0.5, max_iter=300
    )

    assert res.rmse < 0.015
    assert len(res.fitted_vols) == len(strikes)
    assert res.alpha > 0.0
    assert -1.0 < res.rho < 1.0


# ==============================================================================
# 2. VARIANCE SWAP REPLICATION TESTS
# ==============================================================================

def test_realized_variance_calculation():
    """Verify realized variance formula matches annualized return squared variance."""
    # Synthetic flat prices with known return
    prices = [100.0 * (1.01 ** i) for i in range(21)]
    rv_pct2, vol_pct = VarianceSwapReplicationEngine.calculate_realized_variance(prices, annualization_factor=252.0)

    assert rv_pct2 > 0.0
    assert vol_pct > 0.0
    # Annualized vol of 1% daily return is ~ 1% * sqrt(252) ~ 15.87%
    assert 14.0 < vol_pct < 17.5


def test_variance_swap_fair_strike_replication():
    """Verify Demeterfi replication produces consistent fair variance and volatility strikes."""
    s0 = 100.0
    r = 0.03
    t = 1.0
    forward = s0 * math.exp(r * t)

    strikes = [80.0, 85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0]
    # Flat 20% Black-Scholes option prices
    sigma = 0.20
    puts = [_black_scholes_put(s0, k, t, sigma, r) for k in strikes]
    calls = [_black_scholes_call(s0, k, t, sigma, r) for k in strikes]

    res = VarianceSwapReplicationEngine.replicate_fair_strike(
        s0=s0, r=r, t=t, strikes=strikes, market_put_prices=puts, market_call_prices=calls
    )

    assert res.replicated_put_count > 0
    assert res.replicated_call_count > 0
    # Fair volatility should be close to 20% (flat vol input)
    assert 18.0 < res.fair_volatility_strike_pct < 22.0
    # Jensen's inequality convexity adjustment should be positive
    assert res.convexity_adjustment_pct >= 0.0
    assert res.expected_realized_vol_pct <= res.fair_volatility_strike_pct


def test_variance_swap_settlement():
    """Verify variance swap settlement PnL and VRP."""
    prices = [100.0 + math.sin(i * 0.2) * 2.0 for i in range(30)]
    fair_k_var = 400.0  # 20% volatility squared
    vega_notional = 10000.0

    res = VarianceSwapReplicationEngine.settle_variance_swap(
        prices=prices,
        fair_variance_strike_pct2=fair_k_var,
        vega_notional=vega_notional
    )

    assert res.variance_notional == pytest.approx(vega_notional / (2.0 * math.sqrt(fair_k_var)))
    expected_pnl = res.variance_notional * (res.realized_variance_pct2 - fair_k_var)
    assert abs(res.payoff_pnl - expected_pnl) < 1e-4
    assert res.volatility_risk_premium_pct == pytest.approx(math.sqrt(fair_k_var) - res.realized_volatility_pct)


# ==============================================================================
# 3. GARMAN & KOHLHAGEN FX OPTION TESTS
# ==============================================================================

def test_garman_kohlhagen_put_call_parity():
    """Verify Garman-Kohlhagen parity: C - P = S*exp(-rf*T) - K*exp(-rd*T)."""
    spot = 1.15
    strike = 1.12
    t = 0.5
    sigma = 0.10
    rd = 0.04
    rf = 0.02

    res = GarmanKohlhagenFXEngine.price_and_greeks(spot, strike, t, sigma, rd, rf)

    actual_diff = res.call_price - res.put_price
    expected_diff = spot * math.exp(-rf * t) - strike * math.exp(-rd * t)
    assert abs(actual_diff - expected_diff) < 1e-7


def test_garman_kohlhagen_greeks_consistency():
    """Verify properties of FX Greeks: Vega > 0, Gamma > 0, Delta consistency."""
    spot = 1.20
    strike = 1.20
    t = 1.0
    sigma = 0.15
    rd = 0.05
    rf = 0.03

    res = GarmanKohlhagenFXEngine.price_and_greeks(spot, strike, t, sigma, rd, rf)

    assert res.vega > 0.0
    assert res.gamma > 0.0
    assert 0.0 < res.spot_delta_call < 1.0
    assert -1.0 < res.spot_delta_put < 0.0
    assert res.forward_delta_call == pytest.approx(res.spot_delta_call * math.exp(rf * t))
    assert res.rho_domestic > 0.0  # Call benefits from higher domestic interest
    assert res.rho_foreign < 0.0   # Call loses value with higher foreign dividend yield


def test_cip_basis_spread():
    """Verify Covered Interest Parity basis formula."""
    spot = 1.08
    t = 1.0
    rd = 0.05
    rf = 0.03
    # Theoretical forward without basis = spot * exp(rd - rf) = 1.08 * exp(0.02) = 1.1018
    # If market forward is 1.1073 (+50 bps basis)
    f_mkt = spot * math.exp((rd - rf + 0.0050) * t)
    basis_bps = GarmanKohlhagenFXEngine.covered_interest_parity_basis(spot, f_mkt, t, rd, rf)

    assert basis_bps == pytest.approx(50.0, rel=1e-3)


# ==============================================================================
# 4. MERTON (1976) JUMP-DIFFUSION TESTS
# ==============================================================================

def test_merton_put_call_parity():
    """Verify Merton jump-diffusion call and put satisfy Put-Call parity."""
    s0 = 100.0
    k = 95.0
    t = 0.5
    r = 0.05
    sigma = 0.16
    lambda_jump = 1.5
    mu_jump = -0.08
    sigma_jump = 0.12

    res = MertonJumpDiffusionEngine.price_european(
        s0, k, t, r, sigma, lambda_jump, mu_jump, sigma_jump
    )

    actual_diff = res.call_price - res.put_price
    expected_diff = s0 - k * math.exp(-r * t)
    assert abs(actual_diff - expected_diff) < 1e-6
    assert abs(res.poisson_weight_sum - 1.0) < 1e-6


def test_merton_jump_fat_tail_effect():
    """Verify that adding jumps increases deep OTM option prices compared to pure Black-Scholes."""
    s0 = 100.0
    k = 130.0  # Deep OTM call
    t = 0.25
    r = 0.05
    sigma = 0.15

    # Pure Black-Scholes
    bs_call = _black_scholes_call(s0, k, t, sigma, r)

    # Merton with upward crash/jumps
    merton_res = MertonJumpDiffusionEngine.price_european(
        s0, k, t, r, sigma, lambda_jump=2.0, mu_jump=0.10, sigma_jump=0.15
    )

    assert merton_res.call_price > bs_call


def test_merton_monte_carlo_validation():
    """Verify Monte Carlo simulated terminal price matches risk-neutral expectation."""
    s0 = 100.0
    t = 0.5
    r = 0.04
    sigma = 0.18
    lambda_jump = 0.8
    mu_jump = -0.05
    sigma_jump = 0.10

    _, mean_s_t = MertonJumpDiffusionEngine.simulate_paths(
        s0, t, r, sigma, lambda_jump, mu_jump, sigma_jump, n_steps=60, n_paths=4000, seed=123
    )

    # Under risk-neutral measure, E[S_T] = S_0 * exp(r * T)
    theoretical_mean = s0 * math.exp(r * t)
    assert abs(mean_s_t - theoretical_mean) / theoretical_mean < 0.03


# ==============================================================================
# 5. CONTINUOUS KELLY CRITERION & DRAWDOWN TESTS
# ==============================================================================

def test_continuous_kelly_growth_efficiency():
    """Verify Kelly growth maximum and that Half-Kelly achieves exactly 75% efficiency."""
    mu = 0.14
    r = 0.04
    sigma = 0.20

    res = ContinuousKellyGrowthEngine.analyze_growth_profile(mu, r, sigma)

    assert res.sharpe_ratio == pytest.approx((mu - r) / sigma)
    assert res.full_kelly_f == pytest.approx(res.sharpe_ratio / sigma)
    assert res.half_kelly_f == pytest.approx(0.5 * res.full_kelly_f)
    assert res.growth_efficiency_ratio == pytest.approx(0.75, rel=1e-5)
    assert res.max_growth_rate > res.half_kelly_growth_rate > r


def test_grossman_zhou_drawdown_distribution():
    """Verify Grossman-Zhou drawdown probability: Full Kelly P = 1 - D; Half Kelly P = (1 - D)^3."""
    res = ContinuousKellyGrowthEngine.analyze_growth_profile(
        mu=0.12, r=0.04, sigma=0.16, eval_drawdowns=[0.20, 0.50]
    )

    # 20% drawdown: Full Kelly P = 0.80, Half Kelly P = 0.80^3 = 0.512
    assert res.full_kelly_mdd_probs[0] == pytest.approx(0.80)
    assert res.half_kelly_mdd_probs[0] == pytest.approx(0.512)

    # 50% drawdown: Full Kelly P = 0.50, Half Kelly P = 0.50^3 = 0.125
    assert res.full_kelly_mdd_probs[1] == pytest.approx(0.50)
    assert res.half_kelly_mdd_probs[1] == pytest.approx(0.125)


def test_ruin_probability_bounds():
    """Verify ruin probability satisfies boundary conditions [0, 1]."""
    w0 = 100.0
    w_stop = 50.0
    w_target = 200.0
    mu = 0.10
    r = 0.02
    sigma = 0.15

    res = ContinuousKellyGrowthEngine.calculate_ruin_probability(
        w0, w_stop, w_target, mu, r, sigma, f=1.0
    )

    assert 0.0 <= res.ruin_probability <= 1.0
    assert res.ruin_probability + res.success_probability == pytest.approx(1.0)


# ==============================================================================
# 6. HIERARCHICAL EQUAL RISK CONTRIBUTION (HERC) TESTS
# ==============================================================================

def test_herc_correlation_distance():
    """Verify correlation distance matrix properties: D_ii = 0, D_ij in [0, 1]."""
    corr = np.array([
        [1.0, 0.6, 0.2],
        [0.6, 1.0, 0.4],
        [0.2, 0.4, 1.0]
    ])

    dist = HierarchicalEqualRiskContributionEngine.correlation_distance(corr)

    assert np.all(np.diag(dist) == 0.0)
    assert np.all(dist >= 0.0)
    assert np.all(dist <= 1.0)
    assert dist[0, 1] == dist[1, 0]


def test_herc_weight_allocation_properties():
    """Verify HERC weights sum to 1.0, are non-negative, and diversify across assets."""
    # 5-asset covariance matrix with block correlations
    stds = np.array([0.15, 0.18, 0.25, 0.30, 0.12])
    corr = np.array([
        [1.0, 0.8, 0.1, 0.1, 0.2],
        [0.8, 1.0, 0.1, 0.1, 0.2],
        [0.1, 0.1, 1.0, 0.7, 0.3],
        [0.1, 0.1, 0.7, 1.0, 0.3],
        [0.2, 0.2, 0.3, 0.3, 1.0]
    ])
    cov = np.outer(stds, stds) * corr

    res = HierarchicalEqualRiskContributionEngine.allocate_herc(
        cov=cov,
        asset_names=["Tech_1", "Tech_2", "Energy_1", "Energy_2", "Bond_1"]
    )

    weights = np.array(res.weights)
    assert np.sum(weights) == pytest.approx(1.0, rel=1e-6)
    assert np.all(weights > 0.0)
    assert res.portfolio_volatility > 0.0
    assert res.diversification_ratio >= 1.0
    assert res.effective_constituents_enc >= 2.0
    assert len(res.cluster_order) == 5
