"""
Automated Test Suite: Hagan et al. (2002) SABR Volatility Smile & Swaption Model.
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import math
import pytest
import numpy as np

from src.entropy.agent_desk.analysis.sabr_model import (
    SABRParameters,
    SABREngine,
    SABRCalibrationResult,
    black_76_price,
)


def test_sabr_parameters_validation():
    """Verifies that parameter domain constraints are strictly enforced."""
    # Valid parameters
    p = SABRParameters(f0=0.04, alpha=0.02, beta=0.5, rho=-0.2, nu=0.4)
    assert p.f0 == 0.04
    assert p.beta == 0.5
    assert p.rho == -0.2

    # Invalid f0 <= 0
    with pytest.raises(Exception):
        SABRParameters(f0=0.0, alpha=0.02, beta=0.5, rho=0.0, nu=0.4)

    # Invalid beta > 1.0 or < 0
    with pytest.raises(Exception):
        SABRParameters(f0=0.04, alpha=0.02, beta=1.5, rho=0.0, nu=0.4)

    # Invalid rho >= 1.0 or <= -1.0
    with pytest.raises(Exception):
        SABRParameters(f0=0.04, alpha=0.02, beta=0.5, rho=1.0, nu=0.4)


def test_sabr_atm_limit_continuity():
    """
    Verifies that as strike K approaches forward F, the general SABR formula
    converges continuously and smoothly to the analytical ATM limit.
    """
    p = SABRParameters(f0=0.035, alpha=0.025, beta=0.6, rho=-0.15, nu=0.35)
    engine = SABREngine(p)
    t = 2.0

    # Exact ATM
    vol_exact_atm = engine.black_volatility(k=0.035, t=t)

    # Very close strikes
    vol_near_up = engine.black_volatility(k=0.035 + 1e-6, t=t)
    vol_near_down = engine.black_volatility(k=0.035 - 1e-6, t=t)

    # Differences should be tiny (< 1e-4)
    assert abs(vol_near_up - vol_exact_atm) < 1e-4
    assert abs(vol_near_down - vol_exact_atm) < 1e-4


def test_sabr_numerical_stability_near_atm():
    """
    Verifies that no ZeroDivisionError or NaN occurs across tight near-ATM perturbations.
    """
    p = SABRParameters(f0=100.0, alpha=20.0, beta=1.0, rho=-0.3, nu=0.4)
    engine = SABREngine(p)
    t = 1.0

    perturbations = [1e-4, 1e-5, 1e-6, 1e-7, 1e-8, -1e-4, -1e-5, -1e-6]
    for eps in perturbations:
        k = 100.0 + eps
        vol = engine.black_volatility(k=k, t=t)
        assert not math.isnan(vol)
        assert not math.isinf(vol)
        assert vol > 0.0


def test_sabr_skew_and_smile_characteristics():
    """
    Verifies fundamental SABR stylized facts:
    1. Negative rho produces downward sloping volatility skew (puts more expensive than calls).
    2. Vol of vol (nu > 0) creates positive convexity (volatility smile).
    """
    # Negative correlation (Equity-like skew)
    p_skew = SABRParameters(f0=0.04, alpha=0.03, beta=0.5, rho=-0.4, nu=0.3)
    engine_skew = SABREngine(p_skew)
    t = 1.0

    vol_low_strike = engine_skew.black_volatility(k=0.03, t=t)
    vol_atm = engine_skew.black_volatility(k=0.04, t=t)
    vol_high_strike = engine_skew.black_volatility(k=0.05, t=t)

    # Downward sloping skew: vol(0.03) > vol(0.04) > vol(0.05)
    assert vol_low_strike > vol_atm > vol_high_strike

    # Smile convexity test (symmetric rho=0 with positive nu)
    p_smile = SABRParameters(f0=0.04, alpha=0.03, beta=1.0, rho=0.0, nu=0.5)
    engine_smile = SABREngine(p_smile)
    vol_atm_sym = engine_smile.black_volatility(k=0.04, t=t)
    vol_otm_call = engine_smile.black_volatility(k=0.055, t=t)
    vol_otm_put = engine_smile.black_volatility(k=0.025, t=t)

    # Smile wings higher than ATM
    assert vol_otm_call > vol_atm_sym
    assert vol_otm_put > vol_atm_sym


def test_sabr_swaption_pricing_and_put_call_parity():
    """
    Verifies that swaption prices computed from SABR volatility obey Black-76 Call-Put parity:
    Call - Put = DF * (F - K)
    """
    p = SABRParameters(f0=0.05, alpha=0.03, beta=0.7, rho=-0.25, nu=0.4)
    engine = SABREngine(p)
    t = 1.5
    df = 0.95
    strikes = [0.035, 0.045, 0.05, 0.055, 0.065]

    for k in strikes:
        call = engine.swaption_price(k=k, t=t, is_call=True, df=df)
        put = engine.swaption_price(k=k, t=t, is_call=False, df=df)
        expected_parity = df * (0.05 - k)

        assert abs((call - put) - expected_parity) < 1e-6
        assert call >= 0.0
        assert put >= 0.0


def test_sabr_calibration_to_market_smile():
    """
    Verifies calibration of alpha, rho, nu against a realistic market swaption volatility smile.
    """
    f0 = 0.03
    t = 1.0
    strikes = [0.02, 0.025, 0.03, 0.035, 0.04]
    true_params = SABRParameters(f0=f0, alpha=0.025, beta=0.5, rho=-0.2, nu=0.4)
    true_engine = SABREngine(true_params)

    # Generate synthetic market vols
    market_vols = true_engine.volatility_smile(strikes=strikes, t=t)

    # Calibrate starting from displaced initial guess
    calib = SABREngine.calibrate_smile(
        f0=f0,
        t=t,
        strikes=strikes,
        market_vols=market_vols,
        beta=0.5,
        initial_alpha=0.02,
        initial_rho=-0.05,
        initial_nu=0.25,
    )

    assert isinstance(calib, SABRCalibrationResult)
    assert calib.converged is True
    assert calib.rmse < 0.002  # Less than 20 bps RMSE fit
    assert abs(calib.alpha - 0.025) < 0.005
    assert abs(calib.rho - (-0.2)) < 0.1
