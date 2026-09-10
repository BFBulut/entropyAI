"""Automated pytest suite for CPPI, ERC, Hamilton Regime Switching, AMM LVR, and Sovereign Debt Restructuring."""

import math
import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from cppi_erc_hamilton_lvr_debt import (
    calculate_cppi_portfolio_insurance,
    calculate_equal_risk_contribution,
    calculate_hamilton_filter_regime_switching,
    calculate_amm_lvr_and_slippage,
    calculate_sovereign_debt_restructuring_and_nature_swap,
)


# =====================================================================
# 1. Tests for CPPI Portfolio Insurance
# =====================================================================

def test_cppi_valid_and_capital_preservation():
    # Downward market trend: asset price drops 40%
    prices = [100.0, 95.0, 90.0, 85.0, 80.0, 75.0, 70.0, 65.0, 60.0]
    res = calculate_cppi_portfolio_insurance(
        initial_asset=1_000_000.0,
        floor_ratio=0.85,
        multiplier=3.5,
        price_series=prices,
        risk_free_rate=0.04,
        ratchet_enabled=False
    )
    assert res["final_asset_value"] >= 800_000.0
    # CPPI drawdown must be substantially less severe than buy and hold
    assert res["max_drawdown_cppi"] < res["max_drawdown_bh"]
    assert res["gap_risk_single_day_threshold_pct"] == round((1.0 / 3.5) * 100, 2)
    assert "trajectory_summary" in res


def test_cppi_ratchet_and_cash_lock():
    # Severe crash down to 30
    crash_prices = [100.0, 85.0, 70.0, 55.0, 40.0, 30.0]
    res = calculate_cppi_portfolio_insurance(
        initial_asset=500_000.0,
        floor_ratio=0.90,
        multiplier=4.0,
        price_series=crash_prices,
        ratchet_enabled=True
    )
    # Crash should trigger cash-lock or floor breach protection
    assert res["cash_locked"] is True
    assert res["cash_lock_step"] is not None
    assert res["final_asset_value"] > res["final_buy_and_hold_value"]


def test_cppi_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_cppi_portfolio_insurance(-100, 0.8, 3.0, [100, 105])
    with pytest.raises(ValueError):
        calculate_cppi_portfolio_insurance(100, 1.2, 3.0, [100, 105])
    with pytest.raises(ValueError):
        calculate_cppi_portfolio_insurance(100, 0.8, 0.5, [100, 105])
    with pytest.raises(ValueError):
        calculate_cppi_portfolio_insurance(100, 0.8, 3.0, [100])


# =====================================================================
# 2. Tests for Equal Risk Contribution (ERC)
# =====================================================================

def test_erc_parity_and_diversification():
    # 3 assets with different volatilities (10%, 20%, 30%) and correlation 0.20
    cov = [
        [0.0100, 0.0040, 0.0060],
        [0.0040, 0.0400, 0.0120],
        [0.0060, 0.0120, 0.0900],
    ]
    res = calculate_equal_risk_contribution(
        covariance_matrix=cov,
        asset_names=["Tahvil", "Hisse", "Emtia"],
        expected_returns=[0.05, 0.10, 0.12]
    )

    assert res["is_perfect_parity"] is True
    # HHI must be approximately 1/3 ~ 0.3333
    assert abs(res["risk_concentration_hhi"] - (1.0 / 3.0)) < 0.005
    assert res["diversification_ratio"] >= 1.0

    # The lowest volatility asset (Tahvil) must have the highest weight
    assets = res["assets"]
    assert assets[0]["erc_weight_pct"] > assets[1]["erc_weight_pct"]
    assert assets[1]["erc_weight_pct"] > assets[2]["erc_weight_pct"]

    # Each asset's percentage risk contribution must be close to 33.33%
    for a in assets:
        assert abs(a["risk_contribution_pct"] - 33.33) < 1.0

    assert "sharpe_ratio_erc" in res


def test_erc_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_equal_risk_contribution([[0.04]])
    with pytest.raises(ValueError):
        calculate_equal_risk_contribution([[0.04, 0.01], [0.01]])


# =====================================================================
# 3. Tests for Hamilton Filter & Markov Regime Switching
# =====================================================================

def test_hamilton_filter_regimes():
    # 15 days of calm bull market followed by 10 days of volatile bear crisis
    bull_returns = [0.0012, 0.0008, 0.0015, -0.0005, 0.0020, 0.0010, 0.0005, 0.0018, 0.0009, 0.0011]
    bear_returns = [-0.0250, -0.0180, 0.0150, -0.0320, -0.0200, 0.0120, -0.0280, -0.0150]
    all_returns = bull_returns + bear_returns

    res = calculate_hamilton_filter_regime_switching(
        returns=all_returns,
        p11=0.95,
        p22=0.90,
        mu_bull=0.0010,
        sigma_bull=0.0080,
        mu_bear=-0.0015,
        sigma_bear=0.0220
    )

    assert res["total_periods"] == len(all_returns)
    assert res["expected_duration_bull_days"] == 20.0
    assert res["expected_duration_bear_days"] == 10.0
    assert abs((res["unconditional_prob_bull_pct"] + res["unconditional_prob_bear_pct"]) - 100.0) < 0.01
    assert res["current_regime"] == "BEAR"
    assert res["final_filtered_bull_prob_pct"] < 50.0
    # Dynamic strategy protects capital compared to holding the bear crash
    assert res["dynamic_strategy_return_pct"] > res["benchmark_buy_and_hold_return_pct"]


def test_hamilton_filter_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_hamilton_filter_regime_switching([])
    with pytest.raises(ValueError):
        calculate_hamilton_filter_regime_switching([0.01], p11=1.5)
    with pytest.raises(ValueError):
        calculate_hamilton_filter_regime_switching([0.01], sigma_bull=-0.01)


# =====================================================================
# 4. Tests for AMM LVR & Slippage
# =====================================================================

def test_amm_lvr_and_slippage():
    res = calculate_amm_lvr_and_slippage(
        initial_pool_x=100.0,
        initial_pool_y=300_000.0,
        annual_volatility=0.80,
        days=90.0,
        daily_swap_volume_usd=500_000.0,
        fee_tier=0.0030
    )

    assert res["pool_value_initial_usd"] == 600_000.0
    # LVR = (0.80^2 / 8) * 600_000 * (90 / 365) = 0.08 * 600_000 * 0.24657 ~ 11,835 USD
    assert res["lvr_cost_usd"] > 11_000.0
    assert res["earned_swap_fees_usd"] == 500_000.0 * 90 * 0.0030
    assert res["is_lp_profitable"] is True
    assert len(res["trade_slippage_analysis"]) == 4

    # Monotonic slippage check: larger trade size must have strictly higher slippage
    slips = res["trade_slippage_analysis"]
    for i in range(1, len(slips)):
        assert slips[i]["slippage_pct"] > slips[i - 1]["slippage_pct"]


def test_amm_lvr_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_amm_lvr_and_slippage(-10, 100, 0.5, 30, 1000)
    with pytest.raises(ValueError):
        calculate_amm_lvr_and_slippage(10, 100, -0.5, 30, 1000)
    with pytest.raises(ValueError):
        calculate_amm_lvr_and_slippage(10, 100, 0.5, 0, 1000)


# =====================================================================
# 5. Tests for Sovereign Debt Restructuring & Nature Swap
# =====================================================================

def test_sovereign_debt_and_nature_swap():
    res = calculate_sovereign_debt_restructuring_and_nature_swap(
        nominal_debt=1_000_000_000.0,
        old_coupon=0.08,
        old_maturity_years=7,
        principal_haircut_pct=0.25,
        new_coupon=0.045,
        new_maturity_years=15,
        exit_yield=0.12,
        secondary_market_price_pct=0.42,
        nature_conservation_annual_funding=3_000_000.0
    )

    assert res["original_debt_nominal"] == 1_000_000_000.0
    assert res["restructured_nominal"] == 750_000_000.0
    assert res["nominal_haircut_pct"] == 25.0
    # Because coupon dropped from 8% to 4.5% and maturity extended, effective NPV haircut must exceed nominal haircut (25%)
    assert res["effective_npv_haircut_pct"] > res["nominal_haircut_pct"]
    assert res["annual_cashflow_relief_usd"] > 40_000_000.0

    nature_data = res["debt_for_nature_swap"]
    assert nature_data["debt_buyback_cost_usd"] == 420_000_000.0
    assert nature_data["sovereign_principal_extinguished_usd"] > 500_000_000.0
    assert nature_data["net_annual_fiscal_space_gained_usd"] > 0.0

    assert res["paris_club_compliance"]["comparability_of_treatment_met"] is True


def test_sovereign_debt_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_sovereign_debt_restructuring_and_nature_swap(-1000, 0.05, 5, 0.2, 0.03, 10)
    with pytest.raises(ValueError):
        calculate_sovereign_debt_restructuring_and_nature_swap(1000, 0.05, 5, 1.2, 0.03, 10)
    with pytest.raises(ValueError):
        calculate_sovereign_debt_restructuring_and_nature_swap(1000, 0.05, 5, 0.2, 0.03, 10, exit_yield=-0.05)


def test_cli_execution():
    import subprocess
    script_path = skill_scripts_dir / "cppi_erc_hamilton_lvr_debt.py"
    res = subprocess.run([sys.executable, str(script_path), "cppi", "--asset", "1000000"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "final_asset_value" in res.stdout

    res2 = subprocess.run([sys.executable, str(script_path), "erc"], capture_output=True, text=True)
    assert res2.returncode == 0
    assert "portfolio_volatility_pct" in res2.stdout

    res3 = subprocess.run([sys.executable, str(script_path), "hamilton"], capture_output=True, text=True)
    assert res3.returncode == 0
    assert "expected_duration_bull_days" in res3.stdout

    res4 = subprocess.run([sys.executable, str(script_path), "lvr"], capture_output=True, text=True)
    assert res4.returncode == 0
    assert "lvr_cost_usd" in res4.stdout

    res5 = subprocess.run([sys.executable, str(script_path), "debt"], capture_output=True, text=True)
    assert res5.returncode == 0
    assert "debt_for_nature_swap" in res5.stdout

