"""Automated pytest suite for Phase 34: Quantitative Financial Engineering Architecture.

Validates:
1. Carr-Madan (1999) Fast Fourier Transform (FFT) Option Pricing Engine
2. Heston (1993) Albrecher et al. (2007) Little-Trap Branch-Cut Free Formulation
3. Black & Cox (1976) First-Passage Structural Credit Default & Safety Covenant Engine
4. Hasbrouck (1991) Information Share & Gonzalo-Granger (1995) Component Share
5. Geman, Nicole El Karoui & Jean-Charles Rochet (1995) Change of Numeraire Engine
6. Milionis, Moallemi, Roughgarden & Zhang (2022) Loss-Versus-Rebalancing (LVR) AMM Engine
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

from fft_heston_blackcox_hasbrouck_numeraire_lvr import (
    CarrMadanFFTEngine,
    HestonLittleTrapEngine,
    BlackCoxCreditEngine,
    HasbrouckPriceDiscoveryEngine,
    NumeraireChangeEngine,
    MilionisLVREngine,
    _black_scholes_call_price,
    _black_scholes_implied_vol,
)


# ==============================================================================
# 1. CARR-MADAN (1999) FFT OPTION PRICING TESTS
# ==============================================================================

def test_carr_madan_fft_black_scholes_consistency():
    """Verify that Carr-Madan FFT reproduces analytical Black-Scholes call price at ATM."""
    s0 = 100.0
    k = 100.0
    t = 1.0
    r = 0.04
    q = 0.01
    sigma = 0.20

    engine = CarrMadanFFTEngine(s0=s0, r=r, t=t, q=q)
    char_func = CarrMadanFFTEngine.black_scholes_char_func(s0, r, t, sigma, q)

    res = engine.price_single_strike(char_func, target_strike=k, n=4096, alpha=1.5, eta=0.20)
    exact_bs = _black_scholes_call_price(s0, k, t, r, sigma, q)

    assert abs(res["call_price"] - exact_bs) < 0.05
    assert abs(res["implied_vol"] - sigma) < 0.01


def test_carr_madan_fft_put_call_parity_and_monotonicity():
    """Verify Carr-Madan surface satisfies Put-Call parity and decreasing call prices."""
    s0 = 100.0
    t = 0.75
    r = 0.03
    q = 0.0
    sigma = 0.25

    engine = CarrMadanFFTEngine(s0=s0, r=r, t=t, q=q)
    char_func = CarrMadanFFTEngine.black_scholes_char_func(s0, r, t, sigma, q)
    res = engine.price_options_fft(char_func, n=2048, alpha=1.5, eta=0.25)

    assert len(res.strikes) > 50
    # Parity check across strikes: C - P = S0*exp(-qT) - K*exp(-rT)
    for k, c, p in zip(res.strikes[10:40], res.call_prices[10:40], res.put_prices[10:40]):
        expected_diff = s0 * math.exp(-q * t) - k * math.exp(-r * t)
        assert abs((c - p) - expected_diff) < 0.02

    # Monotonicity check: calls decrease as K increases
    diffs = np.diff(res.call_prices)
    assert np.all(diffs <= 0.01)  # allow tiny discretization tolerance


# ==============================================================================
# 2. HESTON (1993) LITTLE-TRAP SEMI-ANALYTIC TESTS
# ==============================================================================

def test_heston_feller_condition_and_pricing():
    """Verify Heston pricer correctly calculates Feller ratio and European option price."""
    # Feller: 2 * kappa * theta = 2 * 2.0 * 0.04 = 0.16; sigma_v^2 = 0.3^2 = 0.09 -> Ratio > 1
    engine = HestonLittleTrapEngine(
        kappa=2.0,
        theta=0.04,
        sigma_v=0.30,
        v0=0.04,
        rho=-0.50,
        r=0.03,
        q=0.0
    )

    assert engine.feller_ratio > 1.0

    res = engine.price_european(s0=100.0, k=100.0, t=1.0)
    assert res.call_price > 0.0
    assert res.put_price > 0.0
    assert res.feller_satisfied is True

    # Put-Call Parity: C - P = S0 - K * exp(-r * T)
    expected_diff = 100.0 - 100.0 * math.exp(-0.03 * 1.0)
    assert abs((res.call_price - res.put_price) - expected_diff) < 1e-4


def test_heston_little_trap_long_maturity_stability():
    """Verify stability of Albrecher et al. Little-Trap formulation for long maturity (T=5.0)."""
    # Under old branch-cut formulations, T=5.0 could produce negative/exploding prices
    engine = HestonLittleTrapEngine(
        kappa=1.0,
        theta=0.06,
        sigma_v=0.40,
        v0=0.06,
        rho=-0.70,
        r=0.05,
        q=0.01
    )

    res = engine.price_european(s0=100.0, k=100.0, t=5.0)
    assert res.call_price > 0.0
    assert 0.0 < res.p1 < 1.0
    assert 0.0 < res.p2 < 1.0
    assert not math.isnan(res.call_price)
    assert not math.isinf(res.call_price)


def test_heston_negative_correlation_skew():
    """Verify negative correlation rho < 0 generates downward-sloping volatility skew."""
    engine = HestonLittleTrapEngine(
        kappa=2.5,
        theta=0.04,
        sigma_v=0.35,
        v0=0.04,
        rho=-0.65,
        r=0.03
    )

    res_otm_put = engine.price_european(s0=100.0, k=85.0, t=0.5)
    res_atm = engine.price_european(s0=100.0, k=100.0, t=0.5)
    res_otm_call = engine.price_european(s0=100.0, k=115.0, t=0.5)

    assert res_otm_put.implied_vol > res_atm.implied_vol > res_otm_call.implied_vol


# ==============================================================================
# 3. BLACK & COX (1976) FIRST-PASSAGE CREDIT DEFAULT TESTS
# ==============================================================================

def test_black_cox_survival_probability_bounds():
    """Verify Black-Cox survival probability is strictly bounded in [0, 1]."""
    engine = BlackCoxCreditEngine(r=0.04, q=0.0)

    # Safe firm: V0 = 200, barrier = 100
    p_safe = engine.survival_probability(v0=200.0, k_barrier=100.0, gamma=0.02, t=3.0, sigma_v=0.20)
    assert 0.80 < p_safe <= 1.0

    # Distressed firm: V0 = 105, barrier C(0) = 100 * exp(-0.02*3) = 94.17
    p_distressed = engine.survival_probability(v0=105.0, k_barrier=100.0, gamma=0.02, t=3.0, sigma_v=0.30)
    assert 0.0 < p_distressed < p_safe


def test_black_cox_corporate_bond_spread_and_covenants():
    """Verify bond pricing, credit spread, and safety covenant impact."""
    engine = BlackCoxCreditEngine(r=0.05, q=0.0)

    bond_safe = engine.price_corporate_bond(
        v0=250.0, face_value=100.0, k_barrier=80.0, gamma=0.03, t=2.0, sigma_v=0.20, recovery_rate=0.40
    )
    bond_risky = engine.price_corporate_bond(
        v0=110.0, face_value=100.0, k_barrier=80.0, gamma=0.03, t=2.0, sigma_v=0.25, recovery_rate=0.40
    )

    assert bond_safe.risky_bond_price > bond_risky.risky_bond_price
    assert bond_risky.credit_spread_bps > bond_safe.credit_spread_bps
    assert bond_safe.credit_spread_bps < 300.0  # Safe firm has tight spread
    assert bond_risky.credit_spread_bps > 500.0  # Distressed firm has wide spread


# ==============================================================================
# 4. HASBROUCK (1991) & GONZALO-GRANGER (1995) PRICE DISCOVERY TESTS
# ==============================================================================

def test_hasbrouck_price_discovery_estimation():
    """Verify Hasbrouck IS and Gonzalo-Granger CS on synthetic lead-lag multi-venue data."""
    np.random.seed(42)
    n_steps = 200

    # True efficient price random walk
    innovations = np.random.normal(0, 0.01, n_steps)
    true_price = np.cumsum(innovations) + 10.0

    # Venue 1 is the price leader (tracks efficient price with minimal noise)
    p_venue1 = true_price + np.random.normal(0, 0.001, n_steps)
    # Venue 2 is a follower (lags behind Venue 1 with error-correction)
    p_venue2 = np.zeros(n_steps)
    p_venue2[0] = p_venue1[0]
    for t in range(1, n_steps):
        p_venue2[t] = p_venue2[t - 1] + 0.6 * (p_venue1[t - 1] - p_venue2[t - 1]) + np.random.normal(0, 0.003)

    prices = np.column_stack([p_venue1, p_venue2])
    res = HasbrouckPriceDiscoveryEngine.estimate_price_discovery(prices)

    assert len(res.hasbrouck_is_mid) == 2
    assert len(res.gonzalo_granger_cs) == 2
    assert np.all(res.hasbrouck_is_lower <= res.hasbrouck_is_upper + 1e-6)
    assert np.sum(res.hasbrouck_is_mid) == pytest.approx(1.0, rel=1e-3)
    assert np.sum(res.gonzalo_granger_cs) == pytest.approx(1.0, rel=1e-3)

    # Leader Venue 1 should account for the majority of price discovery
    assert res.hasbrouck_is_mid[0] > res.hasbrouck_is_mid[1]
    assert res.gonzalo_granger_cs[0] > res.gonzalo_granger_cs[1]


# ==============================================================================
# 5. GEMAN NUMERAIRE CHANGE & MARGRABE EXCHANGE OPTION TESTS
# ==============================================================================

def test_margrabe_numeraire_exchange_symmetry():
    """Verify Margrabe exchange option pricing and properties under numeraire change."""
    # When assets are identical and have equal parameters: option to exchange S2 for S1 has positive time value
    s1, s2 = 100.0, 100.0
    sigma1, sigma2 = 0.20, 0.20
    rho = 0.50
    t = 1.0

    res = NumeraireChangeEngine.margrabe_exchange_option(
        s1=s1, s2=s2, sigma1=sigma1, sigma2=sigma2, rho=rho, t=t
    )

    # Spread volatility sigma_Z = sqrt(0.2^2 - 2*0.5*0.2*0.2 + 0.2^2) = sqrt(0.04) = 0.20
    assert res.volatility_spread == pytest.approx(0.20, rel=1e-4)
    assert res.option_value > 0.0
    assert res.forward_ratio == pytest.approx(1.0)


def test_margrabe_zero_correlation_and_deep_moneyness():
    """Verify Margrabe price increases as asset 1 dominates asset 2."""
    res_itm = NumeraireChangeEngine.margrabe_exchange_option(
        s1=150.0, s2=100.0, sigma1=0.25, sigma2=0.20, rho=0.0, t=0.5
    )
    res_otm = NumeraireChangeEngine.margrabe_exchange_option(
        s1=80.0, s2=100.0, sigma1=0.25, sigma2=0.20, rho=0.0, t=0.5
    )

    assert res_itm.option_value > 50.0  # Intrinsic value S1 - S2 = 50
    assert res_otm.option_value < 10.0


# ==============================================================================
# 6. MILIONIS ET AL. (2022) LVR AMM TESTS
# ==============================================================================

def test_milionis_impermanent_loss_properties():
    """Verify analytical Impermanent Loss formula matches standard AMM mathematics."""
    # Price ratio k = 1.0 -> IL = 0
    assert MilionisLVREngine.calculate_impermanent_loss(1.0) == pytest.approx(0.0)

    # Price doubling k = 2.0 -> IL = 2*sqrt(2)/3 - 1 = -5.72%
    expected_il_2 = 2.0 * math.sqrt(2.0) / 3.0 - 1.0
    assert MilionisLVREngine.calculate_impermanent_loss(2.0) == pytest.approx(expected_il_2, rel=1e-4)

    # Price quadrupling k = 4.0 -> IL = 2*2/5 - 1 = -20.0%
    assert MilionisLVREngine.calculate_impermanent_loss(4.0) == pytest.approx(-0.20, rel=1e-4)


def test_milionis_lvr_accounting_and_profitability():
    """Verify LP accounting comparing Fee revenue vs LVR toxic arbitrage."""
    # Highly active pool with large noise trade volume -> LP is profitable
    res_active = MilionisLVREngine.analyze_lp_profitability(
        initial_spot=2000.0,
        terminal_spot=2100.0,
        pool_tvl_usd=10_000_000.0,
        annual_volatility=0.60,
        fee_tier=0.0030,  # 0.30%
        daily_volume_usd=50_000_000.0,
        time_days=30.0
    )

    assert res_active.is_lp_profitable is True
    assert res_active.fee_to_lvr_ratio > 1.0
    assert res_active.cumulative_lvr_usd > 0.0

    # Low volume pool where toxic LVR dominates fees -> LP is losing money
    res_inactive = MilionisLVREngine.analyze_lp_profitability(
        initial_spot=2000.0,
        terminal_spot=2100.0,
        pool_tvl_usd=10_000_000.0,
        annual_volatility=0.80,
        fee_tier=0.0005,  # 0.05%
        daily_volume_usd=500_000.0,
        time_days=30.0
    )

    assert res_inactive.is_lp_profitable is False
    assert res_inactive.fee_to_lvr_ratio < 1.0
    assert res_inactive.net_lp_profit_usd < 0.0


def test_concentrated_liquidity_lvr_multiplier():
    """Verify Uniswap v3 concentrated liquidity increases LVR exposure relative to v2."""
    # Range [1800, 2200]
    mult = MilionisLVREngine.concentrated_liquidity_lvr_multiplier(p_lower=1800.0, p_upper=2200.0, current_price=2000.0)
    assert mult > 1.0
    assert mult > 5.0  # Concentrated liquidity creates significant leverage
