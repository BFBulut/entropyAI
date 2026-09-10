"""
Unit and Integration Tests for Chapter 20 Financial Auditor Script:
Merton Jump-Diffusion, Key Rate Duration (Barbell vs Bullet), Cross-Currency Basis (CIP),
Kyle's Lambda & Hasbrouck Information Share, and Sloan Accrual Anomaly & Dechow-Dichev Model.
"""

import math
import subprocess
import sys
from pathlib import Path
import pytest

# Ensure scripts directory is in path
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from merton_krd_ccbs_kyle_sloan import (
    norm_cdf,
    black_scholes_call,
    merton_jump_diffusion,
    krd_barbell_bullet,
    cross_currency_basis_cip,
    kyle_lambda_hasbrouck,
    sloan_dechow_accruals
)


# =====================================================================
# 1. Merton Jump-Diffusion Model Tests
# =====================================================================

def test_norm_cdf():
    assert math.isclose(norm_cdf(0.0), 0.5, abs_tol=1e-5)
    assert math.isclose(norm_cdf(1.96), 0.9750, abs_tol=1e-3)
    assert math.isclose(norm_cdf(-1.96), 0.0250, abs_tol=1e-3)


def test_black_scholes_call():
    # Standard BS call benchmark
    c = black_scholes_call(spot=100.0, strike=100.0, maturity=1.0, vol=0.20, rate=0.05)
    assert 10.0 < c < 11.0


def test_merton_jump_diffusion_basic():
    res = merton_jump_diffusion(
        spot=100.0,
        strike=100.0,
        maturity=1.0,
        rate=0.05,
        vol=0.20,
        jump_intensity=1.0,
        jump_mean=-0.05,
        jump_vol=0.15
    )
    assert "merton_call_price" in res
    assert "merton_put_price" in res
    assert res["merton_call_price"] > 0.0
    assert res["merton_put_price"] > 0.0
    # Check put-call parity: C - P = S - K * exp(-r*T)
    c = res["merton_call_price"]
    p = res["merton_put_price"]
    expected_diff = 100.0 - 100.0 * math.exp(-0.05 * 1.0)
    assert math.isclose(c - p, expected_diff, abs_tol=1e-2)
    assert res["total_unconditional_vol_pct"] > 20.0
    assert 0.0 < res["jump_probability_period_pct"] < 100.0


def test_merton_invalid_params():
    with pytest.raises(ValueError):
        merton_jump_diffusion(spot=-10.0, strike=100.0, maturity=1.0, rate=0.05, vol=0.2, jump_intensity=1.0, jump_mean=0.0, jump_vol=0.1)
    with pytest.raises(ValueError):
        merton_jump_diffusion(spot=100.0, strike=100.0, maturity=1.0, rate=0.05, vol=0.2, jump_intensity=-1.0, jump_mean=0.0, jump_vol=0.1)


# =====================================================================
# 2. Key Rate Duration (KRD) & Barbell vs Bullet Tests
# =====================================================================

def test_krd_barbell_bullet_duration_matching():
    res = krd_barbell_bullet(target_duration=7.5, shift_scenario="steepener")
    # Verify weights sum to 100%
    w_short = res["barbell_weights"]["short_2y_pct"]
    w_long = res["barbell_weights"]["long_30y_pct"]
    assert math.isclose(w_short + w_long, 100.0, abs_tol=0.1)
    # Barbell convexity must strictly exceed Bullet convexity
    assert res["convexity"]["barbell"] > res["convexity"]["bullet"]
    assert res["convexity"]["convexity_advantage"] > 0.0


def test_krd_scenarios():
    for sc in ["parallel_up", "parallel_down", "steepener", "flattener", "butterfly"]:
        res = krd_barbell_bullet(target_duration=7.5, shift_scenario=sc)
        assert "bullet_price_change_pct" in res["performance"]
        assert "barbell_price_change_pct" in res["performance"]
        assert "annual_carry_sacrifice_bps" in res["performance"]


def test_krd_custom_shifts():
    custom = [10.0, 20.0, 30.0, 40.0]
    res = krd_barbell_bullet(target_duration=7.5, custom_shifts_bps=custom)
    assert res["shifts_bps"] == custom


# =====================================================================
# 3. Cross-Currency Basis Swap (CCBS) Tests
# =====================================================================

def test_cross_currency_basis_cip():
    res = cross_currency_basis_cip(
        spot_fx=1.0800,
        forward_fx=1.0850,
        tenor_years=1.0,
        domestic_rate_pct=5.25,
        foreign_rate_pct=3.50,
        foreign_credit_spread_bps=60.0,
        domestic_credit_spread_bps=85.0
    )
    assert "cross_currency_basis_bps" in res
    assert res["usd_funding_premium"] is True  # Forward lower than theoretical CIP creates negative basis
    assert "funding_costs" in res
    assert "treasury_verdict" in res


def test_cross_currency_invalid_inputs():
    with pytest.raises(ValueError):
        cross_currency_basis_cip(spot_fx=0.0, forward_fx=1.0, tenor_years=1.0, domestic_rate_pct=5.0, foreign_rate_pct=3.0)


# =====================================================================
# 4. Kyle's Lambda & Hasbrouck Information Share Tests
# =====================================================================

def test_kyle_lambda_and_hasbrouck():
    dp = [0.05, -0.02, 0.10, -0.08, 0.04, 0.12, -0.03]
    q = [1200, -500, 2100, -1800, 900, 2500, -700]
    res = kyle_lambda_hasbrouck(price_changes=dp, order_flows=q, sigma_1=0.012, sigma_2=0.010, correlation_12=0.65)
    
    kyle = res["kyle_microstructure"]
    assert kyle["kyle_lambda"] > 0.0
    assert kyle["market_depth_shares"] > 0.0
    assert 0.0 <= kyle["r_squared_adverse_selection"] <= 1.0

    hasbrouck = res["hasbrouck_price_discovery"]
    assert 0.0 <= hasbrouck["market_1_info_share_pct"] <= 100.0
    assert 0.0 <= hasbrouck["market_2_info_share_pct"] <= 100.0
    assert math.isclose(hasbrouck["market_1_info_share_pct"] + hasbrouck["market_2_info_share_pct"], 100.0, abs_tol=0.1)


def test_kyle_lambda_mismatch():
    with pytest.raises(ValueError):
        kyle_lambda_hasbrouck(price_changes=[0.1, -0.1], order_flows=[100])


# =====================================================================
# 5. Sloan Accrual Anomaly & Dechow-Dichev Tests
# =====================================================================

def test_sloan_dechow_accruals_high_accruals():
    # Net income 150, but CFO only 90 (high positive accruals -> red flag)
    res = sloan_dechow_accruals(
        net_income=150.0,
        cfo=90.0,
        cfi=-40.0,
        total_assets_prev=1000.0,
        total_assets_curr=1200.0,
        delta_ca=120.0,
        delta_cash=30.0,
        delta_cl=50.0,
        delta_std=10.0,
        delta_tp=5.0,
        depreciation=45.0
    )
    assert res["sloan_accrual_ratio"] > 0.05
    assert res["forensic_red_flag"] is True
    assert "Low Quality" in res["sloan_investment_signal"]
    assert "dechow_dichev_quality" in res
    assert 0.0 <= res["earnings_persistence_probability_pct"] <= 100.0


def test_sloan_dechow_accruals_low_accruals():
    # Net income 80, CFO 170 (negative accruals -> high cash conversion, buy candidate)
    res = sloan_dechow_accruals(
        net_income=80.0,
        cfo=170.0,
        cfi=-30.0,
        total_assets_prev=1000.0,
        total_assets_curr=1000.0,
        delta_ca=20.0,
        delta_cash=60.0,
        delta_cl=30.0,
        delta_std=0.0,
        delta_tp=0.0,
        depreciation=20.0
    )
    assert res["sloan_accrual_ratio"] < -0.05
    assert res["forensic_red_flag"] is False
    assert "High Quality" in res["sloan_investment_signal"]


# =====================================================================
# 6. CLI Integration Test
# =====================================================================

def test_cli_execution():
    script_path = str(SCRIPTS_DIR / "merton_krd_ccbs_kyle_sloan.py")
    cmd = [sys.executable, script_path, "krd", "--scenario", "butterfly"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "bullet_price_change_pct" in out.stdout
    assert "barbell_price_change_pct" in out.stdout
