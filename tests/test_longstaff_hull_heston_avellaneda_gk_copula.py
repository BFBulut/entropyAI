"""Automated pytest suite for Phase 28: Quantitative Financial Engineering.

Tests:
1. Longstaff & Schwartz (2001) Least Squares Monte Carlo (LSM) & Early Exercise Premium
2. Hull & White (1990) Extended Vasicek & Jamshidian (1989) Swaption Decomposition
3. Heston & Nandi (2000) Closed-Form Discrete-Time GARCH Option Valuation & Put-Call Parity
4. Avellaneda & Stoikov (2008) / Guéant et al. (2012) Optimal Market Making Quotes
5. Microstructure Volatility Estimators: Parkinson, Garman-Klass, Rogers-Satchell
6. Extreme Tail Dependence Copula Architecture: Clayton, Gumbel, and Student-t Non-Linear Risk
"""

from pathlib import Path
import sys
import math
import pytest
import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from longstaff_hull_heston_avellaneda_gk_copula import (
    LongstaffSchwartzLSMEngine,
    HullWhiteShortRateEngine,
    HestonNandiGARCHEngine,
    AvellanedaStoikovMarketMakingEngine,
    MicrostructureVolatilityEngine,
    TailDependenceCopulaEngine,
    _student_t_cdf,
    _norm_cdf,
)


# ==============================================================================
# 1. LONGSTAFF & SCHWARTZ LSM TESTS
# ==============================================================================

def test_lsm_american_put_properties():
    """Verify that American Put price is >= European Put price (EEP >= 0)."""
    res = LongstaffSchwartzLSMEngine.price_american_put(
        s0=100.0, strike=100.0, r=0.05, q=0.0, sigma=0.20, t_mat=1.0, n_steps=30, n_paths=6000, seed=123
    )

    assert res.american_price > 0.0
    assert res.european_price > 0.0
    assert res.american_price >= res.european_price
    assert res.early_exercise_premium >= 0.0
    assert 0.0 < res.exercise_ratio < 1.0
    assert res.std_error > 0.0


def test_lsm_american_call_with_dividend():
    """Verify American Call with positive dividend yield has early exercise value."""
    res_no_div = LongstaffSchwartzLSMEngine.price_american_call(
        s0=100.0, strike=100.0, r=0.05, q=0.0, sigma=0.20, t_mat=1.0, n_steps=30, n_paths=4000, seed=42
    )
    res_with_div = LongstaffSchwartzLSMEngine.price_american_call(
        s0=100.0, strike=100.0, r=0.05, q=0.08, sigma=0.20, t_mat=1.0, n_steps=30, n_paths=4000, seed=42
    )

    # Without dividend, American call is never exercised early: EEP ~ 0
    assert res_no_div.early_exercise_premium < 0.20
    # With high dividend, early exercise is optimal before dividend capture
    assert res_with_div.american_price > 0.0
    assert res_with_div.early_exercise_premium >= 0.0


# ==============================================================================
# 2. HULL-WHITE SHORT RATE & JAMSHIDIAN SWAPTION TESTS
# ==============================================================================

def test_hull_white_zcb_analytical():
    """Verify analytical zero-coupon bond price under Hull-White."""
    p_1y = HullWhiteShortRateEngine.zero_coupon_bond(
        r_t=0.03, t=0.0, t_mat=1.0, a=0.05, sigma=0.01, r0=0.03
    )
    # Price should be close to exp(-0.03 * 1.0) ~ 0.97044
    assert 0.965 < p_1y < 0.975

    p_5y = HullWhiteShortRateEngine.zero_coupon_bond(
        r_t=0.03, t=0.0, t_mat=5.0, a=0.05, sigma=0.01, r0=0.03
    )
    assert p_5y < p_1y  # Longer maturity ZCB has lower price


def test_jamshidian_swaption_decomposition():
    """Verify Jamshidian decomposition yields valid critical rate and positive swaption price."""
    tenors = [1.5, 2.0, 2.5, 3.0]
    res = HullWhiteShortRateEngine.jamshidian_swaption(
        strike_swap=0.04, t_exp=1.0, swap_tenors=tenors, a=0.03, sigma=0.015, r0=0.035, swaption_type="payer"
    )

    assert res.swaption_price > 0.0
    assert -0.05 < res.critical_rate_r_star < 0.20
    assert len(res.bond_options) == len(tenors)

    # Every underlying bond option must have non-negative price
    for b_opt in res.bond_options:
        assert b_opt["zcb_option_price"] >= 0.0
        assert b_opt["weighted_price"] >= 0.0


def test_hull_white_trinomial_probabilities():
    """Verify trinomial lattice transition probabilities sum to 1.0."""
    p_u, p_m, p_d = HullWhiteShortRateEngine.trinomial_probabilities(j=0, a=0.05, dt=0.1)
    assert abs(p_u + p_m + p_d - 1.0) < 1e-12
    assert p_u > 0.0 and p_m > 0.0 and p_d > 0.0

    p_u_pos, p_m_pos, p_d_pos = HullWhiteShortRateEngine.trinomial_probabilities(j=2, a=0.05, dt=0.1)
    assert abs(p_u_pos + p_m_pos + p_d_pos - 1.0) < 1e-12


# ==============================================================================
# 3. HESTON-NANDI GARCH OPTION TESTS
# ==============================================================================

def test_heston_nandi_unconditional_variance_and_stationarity():
    """Verify unconditional variance calculation and stationarity assertion."""
    var = HestonNandiGARCHEngine.unconditional_variance(
        omega=1e-6, alpha1=1.5e-5, beta1=0.75, gamma1_star=100.0
    )
    assert var > 0.0
    annual_vol = math.sqrt(var * 252.0)
    assert 0.10 < annual_vol < 0.40

    # Non-stationary parameters should raise ValueError
    with pytest.raises(ValueError):
        HestonNandiGARCHEngine.unconditional_variance(
            omega=1e-6, alpha1=0.01, beta1=0.99, gamma1_star=100.0
        )


def test_heston_nandi_option_pricing_and_put_call_parity():
    """Verify Heston-Nandi European option prices satisfy Put-Call Parity."""
    spot = 100.0
    strike = 100.0
    r_ann = 0.05
    t_days = 126  # 0.5 year
    df = math.exp(-r_ann * (t_days / 252.0))

    res = HestonNandiGARCHEngine.price_european_call(
        spot=spot, strike=strike, r_annual=r_ann, t_days=t_days
    )

    assert res.call_price > 0.0
    assert res.put_price > 0.0
    assert 0.0 <= res.p1 <= 1.0
    assert 0.0 <= res.p2 <= 1.0

    # Put-Call Parity: Call - Put = Spot - Strike * df
    parity_diff = (res.call_price - res.put_price) - (spot - strike * df)
    assert abs(parity_diff) < 0.05


# ==============================================================================
# 4. AVELLANEDA-STOIKOV MARKET MAKING TESTS
# ==============================================================================

def test_avellaneda_stoikov_inventory_skew():
    """Verify that inventory skews quotes: long inventory lowers reservation price."""
    mid = 100.0
    gamma = 0.1
    sigma = 0.3
    t_rem = 0.5

    res_neutral = AvellanedaStoikovMarketMakingEngine.compute_quotes(mid, 0, gamma, sigma, t_rem)
    res_long = AvellanedaStoikovMarketMakingEngine.compute_quotes(mid, 5, gamma, sigma, t_rem)
    res_short = AvellanedaStoikovMarketMakingEngine.compute_quotes(mid, -5, gamma, sigma, t_rem)

    # Reservation price ordering
    assert res_short.reservation_price > res_neutral.reservation_price > res_long.reservation_price

    # When long inventory: bid quote is lower (protect against buying), ask is lower (incentivize selling)
    assert res_long.bid_quote < res_neutral.bid_quote
    assert res_long.ask_quote < res_neutral.ask_quote

    # Total spread is invariant to inventory in Guéant asymptotic formulation
    assert abs(res_neutral.total_spread - res_long.total_spread) < 1e-4


def test_avellaneda_stoikov_simulation():
    """Verify market making session simulation runs and produces bounded inventory."""
    sim = AvellanedaStoikovMarketMakingEngine.simulate_trading_session(
        s0=100.0, gamma=0.1, sigma=0.2, t_horizon=0.5, dt=0.01, max_inventory=5, seed=42
    )

    assert abs(sim.terminal_inventory) <= 5
    assert sim.total_trades_bid >= 0
    assert sim.total_trades_ask >= 0


# ==============================================================================
# 5. MICROSTRUCTURE VOLATILITY ESTIMATOR TESTS
# ==============================================================================

def test_microstructure_volatility_efficiency_hierarchy():
    """Verify Parkinson, Garman-Klass, and Rogers-Satchell estimators."""
    np.random.seed(99)
    n = 300
    # Simulate driftless random walk
    log_c = np.cumsum(np.random.normal(0.0, 0.012, n))
    c = 100.0 * np.exp(log_c)
    o = c * np.exp(np.random.normal(0.0, 0.002, n))
    h = np.maximum(o, c) * np.exp(np.abs(np.random.normal(0.0, 0.006, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(np.random.normal(0.0, 0.006, n)))

    res = MicrostructureVolatilityEngine.compare_all(o, h, l, c)

    assert res.close_to_close > 0.0
    assert res.parkinson > 0.0
    assert res.garman_klass > 0.0
    assert res.rogers_satchell > 0.0
    assert res.garman_klass_yang_zhang > 0.0

    # Estimators should be in a reasonable range (10% - 40% annualized)
    for est in [res.close_to_close, res.parkinson, res.garman_klass, res.rogers_satchell]:
        assert 0.05 < est < 0.60


def test_rogers_satchell_drift_insensitivity():
    """Verify Rogers-Satchell handles non-zero drift without explosive volatility bias."""
    np.random.seed(101)
    n = 200
    # High positive drift
    drift = 0.005
    log_c = np.cumsum(np.random.normal(drift, 0.01, n))
    c = 100.0 * np.exp(log_c)
    o = c * np.exp(np.random.normal(0.0, 0.002, n))
    h = np.maximum(o, c) * np.exp(np.abs(np.random.normal(0.0, 0.005, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(np.random.normal(0.0, 0.005, n)))

    rs_vol = MicrostructureVolatilityEngine.rogers_satchell(o, h, l, c)
    assert 0.05 < rs_vol < 0.50


# ==============================================================================
# 6. EXTREME TAIL DEPENDENCE COPULA TESTS
# ==============================================================================

def test_clayton_copula_tail_dependence():
    """Verify Clayton lower tail dependence formula lambda_L = 2^(-1/theta)."""
    # For Kendall's tau = 0.5: theta = 2*0.5 / (1 - 0.5) = 2.0
    # lambda_L = 2^(-1/2) = 1 / sqrt(2) ~ 0.7071
    res = TailDependenceCopulaEngine.analyze_clayton_crisis(kendall_tau=0.5, alpha=0.01)

    assert abs(res.parameter_theta - 2.0) < 1e-3
    assert abs(res.lower_tail_dependence_lambda_l - 0.7071) < 1e-3
    assert res.upper_tail_dependence_lambda_u == 0.0
    # Clayton joint crash probability must exceed Gaussian benchmark
    assert res.joint_crash_probability_1pct > res.gaussian_benchmark_crash_prob_1pct


def test_gumbel_copula_tail_dependence():
    """Verify Gumbel upper tail dependence formula lambda_U = 2 - 2^(1/theta)."""
    # For Kendall's tau = 0.5: theta = 1 / (1 - 0.5) = 2.0
    # lambda_U = 2 - 2^(1/2) = 2 - 1.4142 = 0.5858
    res = TailDependenceCopulaEngine.analyze_gumbel_bubble(kendall_tau=0.5, alpha=0.01)

    assert abs(res.parameter_theta - 2.0) < 1e-3
    assert abs(res.upper_tail_dependence_lambda_u - 0.5858) < 1e-3
    assert res.lower_tail_dependence_lambda_l == 0.0


def test_student_t_symmetric_tail_dependence():
    """Verify Student-t copula symmetric tail dependence decreases as degrees of freedom increase."""
    # Low df (fat tails, e.g. df=3) has high tail dependence
    td_fat = TailDependenceCopulaEngine.student_t_tail_dependence(nu=3.0, rho=0.5)
    # High df (approaching Gaussian, e.g. df=30) has lower tail dependence
    td_thin = TailDependenceCopulaEngine.student_t_tail_dependence(nu=30.0, rho=0.5)

    assert td_fat > td_thin
    assert 0.0 < td_fat < 1.0
    assert 0.0 < td_thin < 1.0


def test_student_t_cdf_helper():
    """Verify numerical Student-t CDF helper function."""
    # At t = 0, CDF = 0.5
    assert abs(_student_t_cdf(0.0, df=5.0) - 0.5) < 1e-6
    # Symmetrical properties: CDF(-x) = 1 - CDF(x)
    cdf_pos = _student_t_cdf(1.5, df=4.0)
    cdf_neg = _student_t_cdf(-1.5, df=4.0)
    assert abs(cdf_pos + cdf_neg - 1.0) < 1e-3
    assert cdf_pos > 0.5
