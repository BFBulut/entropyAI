"""Automated pytest test suite for Advanced Financial Analytics Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from advanced_analytics import (
    calculate_altman_z_score,
    calculate_beneish_m_score,
    calculate_reverse_dcf,
    calculate_fractional_kelly,
)


def test_altman_z_score_safe_and_distress():
    # Safe zone company: strong liquidity, high EBIT and retained earnings
    safe_res = calculate_altman_z_score(
        working_capital=300000,
        retained_earnings=250000,
        ebit=150000,
        market_cap=1200000,
        total_liabilities=200000,
        revenue=1000000,
        total_assets=800000
    )
    assert safe_res["risk_level"] == "LOW"
    assert safe_res["z_score"] > 2.99
    assert "Güvenli Bölge" in safe_res["zone"]

    # Distress zone company: negative working capital, low EBIT, high liabilities
    distress_res = calculate_altman_z_score(
        working_capital=-50000,
        retained_earnings=-100000,
        ebit=5000,
        market_cap=50000,
        total_liabilities=600000,
        revenue=200000,
        total_assets=500000
    )
    assert distress_res["risk_level"] == "HIGH"
    assert distress_res["z_score"] < 1.81
    assert "Tehlike Bölgesi" in distress_res["zone"]

    # Invalid assets/liabilities
    invalid_res = calculate_altman_z_score(0, 0, 0, 0, 0, 0, 0)
    assert "error" in invalid_res


def test_beneish_m_score_manipulation_detection():
    # Baseline normal company (neutral indices around 1.0, low accruals)
    normal_res = calculate_beneish_m_score(
        dsri=1.0, gmi=1.0, aqi=1.0, sgi=1.05,
        depi=1.0, sgai=1.0, tata=0.01, lvgi=1.0
    )
    assert normal_res["flag_triggered"] is False
    assert normal_res["m_score"] < -1.78
    assert "DÜŞÜK" in normal_res["manipulation_risk"]

    # Manipulator red flag company (surging receivables, aggressive growth, high accruals)
    manipulator_res = calculate_beneish_m_score(
        dsri=2.5, gmi=1.8, aqi=2.0, sgi=2.2,
        depi=1.5, sgai=1.2, tata=0.35, lvgi=2.0
    )
    assert manipulator_res["flag_triggered"] is True
    assert manipulator_res["m_score"] > -1.78
    assert "YÜKSEK" in manipulator_res["manipulation_risk"]


def test_reverse_dcf_implied_growth():
    # Healthy company: 10M market cap, 500k FCF, 10% WACC
    res = calculate_reverse_dcf(
        current_market_cap=10000000,
        current_fcf=500000,
        wacc=0.10,
        terminal_growth=0.025
    )
    assert "implied_annual_fcf_growth_pct" in res
    assert res["wacc_pct"] == 10.0
    assert isinstance(res["implied_annual_fcf_growth_pct"], float)

    # Invalid input
    err_res = calculate_reverse_dcf(0, -100)
    assert "error" in err_res


def test_fractional_kelly_sizing():
    # Positive edge: 60% win rate, 2:1 risk/reward -> full kelly = (0.6*2 - 0.4)/2 = 0.8/2 = 40%
    # Half kelly (0.5) -> 20%
    res = calculate_fractional_kelly(win_rate=0.60, risk_reward_ratio=2.0, fraction=0.5)
    assert res["full_kelly_pct"] == 40.0
    assert res["recommended_allocation_pct"] == 20.0
    assert "Pozitif Beklenti" in res["edge"]

    # Negative edge: 30% win rate, 1:1 risk/reward -> negative kelly
    neg_res = calculate_fractional_kelly(win_rate=0.30, risk_reward_ratio=1.0, fraction=0.5)
    assert neg_res["recommended_allocation_pct"] == 0.0
    assert "Negatif Beklenti" in neg_res["edge"]

    # Invalid parameters
    inv_res = calculate_fractional_kelly(win_rate=1.5, risk_reward_ratio=-1)
    assert "error" in inv_res
