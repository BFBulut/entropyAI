"""Automated pytest test suite for Macro Taylor Rule, TIPS Breakeven, Miller-Orr and Stablecoin Analytics."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from macro_taylor_stablecoin import (
    calculate_taylor_rule_rate,
    calculate_breakeven_inflation,
    calculate_miller_orr_bounds,
    calculate_stablecoin_health_factor
)


def test_taylor_rule_rate():
    # Neutral = 2.0%, Current Inf = 4.0%, Target = 2.0%, Output Gap = 1.0%
    # Inflation gap = 2.0% -> 0.5 * 2.0 = 1.0%
    # Output gap = 1.0% -> 0.5 * 1.0 = 0.5%
    # Taylor rate = 2.0 + 4.0 + 1.0 + 0.5 = 7.5%
    res = calculate_taylor_rule_rate(
        neutral_real_rate=2.0,
        current_inflation=4.0,
        target_inflation=2.0,
        output_gap=1.0,
        actual_policy_rate=5.0
    )
    assert res["taylor_rule_recommended_rate_pct"] == 7.5
    assert res["policy_gap_pct"] == 2.5
    assert "BEHIND THE CURVE" in res["stance_verdict"]

    # Ahead of the curve / overly restrictive: actual rate = 8.5%
    ahead_res = calculate_taylor_rule_rate(2.0, 4.0, 2.0, 1.0, actual_policy_rate=8.5)
    assert ahead_res["policy_gap_pct"] == -1.0
    assert "AHEAD OF THE CURVE" in ahead_res["stance_verdict"]

    # Neutral / aligned: actual rate = 7.5%
    neutral_res = calculate_taylor_rule_rate(2.0, 4.0, 2.0, 1.0, actual_policy_rate=7.5)
    assert "DENGE / UYUMLU" in neutral_res["stance_verdict"]


def test_breakeven_inflation():
    # 10Y Nominal = 4.30%, TIPS Real = 1.95% -> Breakeven = 2.35% (Moderate)
    res = calculate_breakeven_inflation(nominal_yield=4.30, tips_real_yield=1.95)
    assert res["breakeven_inflation_rate_pct"] == 2.35
    assert "ILIMLI / DENGELİ" in res["market_sentiment"]

    # High inflation expectation: 5.0% - 2.0% = 3.0%
    high_res = calculate_breakeven_inflation(5.0, 2.0)
    assert high_res["breakeven_inflation_rate_pct"] == 3.0
    assert "YÜKSEK ENFLASYON BEKLENTİSİ" in high_res["market_sentiment"]

    # Low inflation / deflation risk: 2.8% - 1.5% = 1.3%
    low_res = calculate_breakeven_inflation(2.8, 1.5)
    assert low_res["breakeven_inflation_rate_pct"] == 1.3
    assert "DÜŞÜK ENFLASYON / DEFLASYON RİSKİ" in low_res["market_sentiment"]


def test_miller_orr_bounds():
    # F = 50, variance = 1,000,000, r = 0.0001, lower = 5000
    res = calculate_miller_orr_bounds(
        transaction_cost=50.0,
        daily_cash_variance=1000000.0,
        daily_interest_rate=0.0001,
        lower_bound=5000.0,
        current_cash=30000.0
    )
    # base spread ~ 7211.25, Z* ~ 12211.25, H* ~ 26633.74
    assert res["target_cash_level_z"] == 12211.25
    assert res["upper_limit_h"] == 26633.74
    # Current cash 30,000 > H* (26,633.74) -> Excess cash, buy securities
    assert "MENKUL KIYMET ALIMI" in res["recommended_action"]

    # Cash below lower bound
    deficit_res = calculate_miller_orr_bounds(50.0, 1000000.0, 0.0001, 5000.0, current_cash=2000.0)
    assert "MENKUL KIYMET SATIŞI" in deficit_res["recommended_action"]

    # Cash within optimal band
    hold_res = calculate_miller_orr_bounds(50.0, 1000000.0, 0.0001, 5000.0, current_cash=15000.0)
    assert "İŞLEM YAPMA" in hold_res["recommended_action"]

    # Invalid arguments
    err1 = calculate_miller_orr_bounds(-10.0, 1000.0, 0.001)
    assert "error" in err1
    err2 = calculate_miller_orr_bounds(50.0, -100.0, 0.001)
    assert "error" in err2
    err3 = calculate_miller_orr_bounds(50.0, 100.0, 0.0)
    assert "error" in err3
    err4 = calculate_miller_orr_bounds(50.0, 100.0, 0.001, lower_bound=-100.0)
    assert "error" in err4


def test_stablecoin_health_factor():
    # Collateral = $150,000, Threshold = 0.80, Borrowed = $100,000 -> HF = 1.20
    res = calculate_stablecoin_health_factor(
        collateral_value_usd=150000.0,
        liquidation_threshold=0.80,
        borrowed_amount_usd=100000.0
    )
    assert res["health_factor"] == 1.20
    assert res["collateralization_ratio_pct"] == 150.0
    assert "SAĞLIKLI / GÜVENLİ" in res["liquidation_risk_status"]

    # De-peg / liquidation risk: Collateral drops to $110,000 -> HF = 0.88 (< 1.0)
    liq_res = calculate_stablecoin_health_factor(110000.0, 0.80, 100000.0)
    assert liq_res["health_factor"] == 0.88
    assert "TASFİYE / DE-PEG RİSKİ" in liq_res["liquidation_risk_status"]

    # Warning zone: HF = 1.12
    warn_res = calculate_stablecoin_health_factor(140000.0, 0.80, 100000.0)
    assert warn_res["health_factor"] == 1.12
    assert "KRİTİK UYARI" in warn_res["liquidation_risk_status"]

    # Invalid inputs
    err1 = calculate_stablecoin_health_factor(-500.0, 0.80, 1000.0)
    assert "error" in err1
    err2 = calculate_stablecoin_health_factor(1000.0, 0.80, 0.0)
    assert "error" in err2
    err3 = calculate_stablecoin_health_factor(1000.0, 1.5, 500.0)
    assert "error" in err3
