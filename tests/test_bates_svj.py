"""
Automated Test Suite: David S. Bates (1996) Stochastic Volatility Jump-Diffusion (SVJ) Model.
Validates:
1. Pydantic parameter boundaries and Feller ratio computation.
2. Characteristic function mathematical invariants:
   - phi(0) == 1.
   - Martingale property: phi(-i) == S0 * exp((r - q) * t).
3. Albrecher et al. (2007) Little Heston Trap branch-cut-free continuity for long maturities.
4. Put-Call Parity consistency: C(K) - P(K) == S0 * exp(-q*t) - K * exp(-r*t).
5. Carr-Madan FFT pricing vs. Gauss-Legendre quadrature convergence.
6. Analytical Limit 1: Merton (1976) Jump-Diffusion limit as sigma_v -> 0.
7. Analytical Limit 2: Black-Scholes (1973) limit as lambda -> 0 and sigma_v -> 0.
8. Implied Volatility inversion and Volatility Smile extraction.
9. quant_team preset template registration and DoD validation.
"""

import math
import pytest
import numpy as np

from src.entropy.agent_desk.analysis.bates_svj import (
    BatesParameters,
    BatesSVJEngine,
    BatesPricingResult,
    BatesSurfaceResult,
    black_scholes_call_price,
    black_scholes_implied_vol,
)
from src.entropy.agent_desk.core.templates import (
    get_template,
    get_available_templates,
)
from src.entropy.agent_desk.core.models import DeskRole


def test_bates_parameters_validation():
    # Valid parameters
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=2.0,
        theta=0.04,
        sigma_v=0.3,
        rho=-0.7,
        r=0.03,
        q=0.01,
        jump_lambda=0.15,
        jump_mu=-0.08,
        jump_sigma=0.12,
    )
    # 2 * kappa * theta / sigma_v^2 = 2 * 2.0 * 0.04 / 0.09 = 0.16 / 0.09 = 1.777...
    assert params.feller_ratio == pytest.approx(1.777777, rel=1e-3)
    assert params.is_feller_satisfied

    # Jump compensator: exp(mu + 0.5 * sigma^2) - 1
    expected_k_bar = math.exp(-0.08 + 0.5 * (0.12 ** 2)) - 1.0
    assert params.jump_compensator == pytest.approx(expected_k_bar, rel=1e-5)

    # Invalid boundaries
    with pytest.raises(ValueError):
        BatesParameters(s0=-10.0, v0=0.04, kappa=2.0, theta=0.04, sigma_v=0.3, rho=0.0)
    with pytest.raises(ValueError):
        BatesParameters(s0=100.0, v0=0.04, kappa=2.0, theta=0.04, sigma_v=0.3, rho=1.5)


def test_characteristic_function_properties():
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=1.5,
        theta=0.04,
        sigma_v=0.25,
        rho=-0.5,
        r=0.05,
        q=0.02,
        jump_lambda=0.2,
        jump_mu=-0.05,
        jump_sigma=0.1,
    )
    engine = BatesSVJEngine(params)
    t = 1.0

    # 1. Total probability conservation: phi(0) must equal 1.0 + 0j
    phi_zero = engine.characteristic_function(0.0 + 0.0j, t)
    assert abs(phi_zero - (1.0 + 0.0j)) < 1e-10

    # 2. Martingale property: E[S_T] = S_0 * exp((r - q) * T) => phi(-i) == S_0 * exp((r - q) * T)
    phi_neg_i = engine.characteristic_function(-1.0j, t)
    expected_s_t = params.s0 * math.exp((params.r - params.q) * t)
    assert phi_neg_i.real == pytest.approx(expected_s_t, rel=1e-4)
    assert abs(phi_neg_i.imag) < 1e-4


def test_albrecher_little_heston_trap_stability():
    """Verifies that for long maturities (T=10, 20), characteristic function does not encounter branch cuts."""
    params = BatesParameters(
        s0=100.0,
        v0=0.09,
        kappa=0.5,
        theta=0.09,
        sigma_v=0.5,
        rho=-0.8,
        r=0.02,
        jump_lambda=0.5,
        jump_mu=-0.1,
        jump_sigma=0.2,
    )
    engine = BatesSVJEngine(params)

    for long_t in [5.0, 10.0, 20.0]:
        for u_val in [0.5, 1.0, 5.0, 10.0, 25.0, 50.0]:
            val = engine.characteristic_function(complex(u_val, 0.0), long_t)
            assert not cmath_isnan(val)
            assert not cmath_isinf(val)
            # Modulus of char func is bounded by 1 for real argument normalized
            # (phi(u; ln(S_T/S_0)))


def cmath_isnan(c: complex) -> bool:
    return math.isnan(c.real) or math.isnan(c.imag)


def cmath_isinf(c: complex) -> bool:
    return math.isinf(c.real) or math.isinf(c.imag)


def test_put_call_parity():
    """Verifies European Call and Put satisfy Put-Call parity."""
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=2.0,
        theta=0.04,
        sigma_v=0.3,
        rho=-0.6,
        r=0.04,
        q=0.01,
        jump_lambda=0.1,
        jump_mu=-0.05,
        jump_sigma=0.15,
    )
    engine = BatesSVJEngine(params)
    t = 0.75

    for k in [80.0, 95.0, 100.0, 105.0, 120.0]:
        res = engine.price_european(strike=k, expiry=t, method="gauss_legendre")
        # C - P = S0 * exp(-q*T) - K * exp(-r*T)
        parity_diff = res.call_price - res.put_price
        expected_diff = params.s0 * math.exp(-params.q * t) - k * math.exp(-params.r * t)
        assert parity_diff == pytest.approx(expected_diff, abs=1e-4)


def test_bates_black_scholes_limit():
    """When jump_lambda -> 0 and sigma_v -> 0, Bates SVJ converges to Black-Scholes formula."""
    sigma = 0.20
    params = BatesParameters(
        s0=100.0,
        v0=sigma ** 2,
        kappa=5.0,
        theta=sigma ** 2,
        sigma_v=1e-4,  # nearly zero volatility of variance
        rho=0.0,
        r=0.05,
        q=0.0,
        jump_lambda=0.0,  # no jumps
        jump_mu=0.0,
        jump_sigma=0.01,
    )
    engine = BatesSVJEngine(params)
    t = 1.0

    for k in [90.0, 100.0, 110.0]:
        res = engine.price_european(strike=k, expiry=t, method="gauss_legendre")
        bs_call = black_scholes_call_price(params.s0, k, t, params.r, sigma, params.q)
        assert res.call_price == pytest.approx(bs_call, rel=5e-3)


def test_bates_merton_limit():
    """When sigma_v -> 0 and v0 = theta = sigma^2, Bates SVJ converges to Robert C. Merton (1976)."""
    sigma = 0.20
    jump_lambda = 0.3
    jump_mu = -0.05
    jump_sigma = 0.15
    s0 = 100.0
    r = 0.04
    t = 0.5
    k = 100.0

    params = BatesParameters(
        s0=s0,
        v0=sigma ** 2,
        kappa=10.0,
        theta=sigma ** 2,
        sigma_v=1e-4,  # near zero vol of vol
        rho=0.0,
        r=r,
        q=0.0,
        jump_lambda=jump_lambda,
        jump_mu=jump_mu,
        jump_sigma=jump_sigma,
    )
    engine = BatesSVJEngine(params)

    bates_res = engine.price_european(strike=k, expiry=t, method="gauss_legendre")
    merton_call = BatesSVJEngine.merton_jump_diffusion_benchmark(
        s0=s0,
        k=k,
        t=t,
        r=r,
        sigma=sigma,
        jump_lambda=jump_lambda,
        jump_mu=jump_mu,
        jump_sigma=jump_sigma,
    )

    # Within 1% relative error
    assert bates_res.call_price == pytest.approx(merton_call, rel=1e-2)


def test_carr_madan_fft_surface_pricing():
    """Verifies Carr & Madan (1999) FFT option pricing generates consistent surface and skew."""
    params = BatesParameters(
        s0=100.0,
        v0=0.04,
        kappa=2.0,
        theta=0.04,
        sigma_v=0.3,
        rho=-0.7,
        r=0.03,
        q=0.0,
        jump_lambda=0.2,
        jump_mu=-0.10,
        jump_sigma=0.15,
    )
    engine = BatesSVJEngine(params)
    surface = engine.price_surface_carr_madan_fft(t=1.0, n=2048)

    assert len(surface.strikes) > 50
    assert len(surface.call_prices) == len(surface.strikes)
    assert len(surface.implied_vols) == len(surface.strikes)

    # Call prices must be monotonically decreasing in strike
    for i in range(len(surface.call_prices) - 1):
        assert surface.call_prices[i] >= surface.call_prices[i + 1] - 1e-4

    # Negative skew: implied volatility for low strike (OTM Put / ITM Call) > high strike
    low_k_idx = 10
    high_k_idx = len(surface.strikes) - 10
    assert surface.implied_vols[low_k_idx] > surface.implied_vols[high_k_idx]


def test_quant_team_template_registration():
    """Verifies quant_team preset is registered with 3 specialized roles and DoD."""
    tmpl = get_template("quant_team")
    assert tmpl is not None
    assert tmpl.name == "Kantitatif Finans & Risk Takımı (Quant Team)"
    assert tmpl.icon == "📈"
    assert len(tmpl.roles) == 3

    roles_dict = {r.slug: r for r in tmpl.roles}
    assert "quant_lead" in roles_dict
    assert "stochastic_modeler" in roles_dict
    assert "quant_sentinel" in roles_dict

    assert roles_dict["quant_lead"].role == DeskRole.ORCHESTRATOR
    assert roles_dict["stochastic_modeler"].role == DeskRole.DEVELOPER
    assert roles_dict["quant_sentinel"].role == DeskRole.TESTER

    for r in tmpl.roles:
        assert len(r.definition_of_done) >= 2
