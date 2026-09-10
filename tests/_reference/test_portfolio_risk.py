"""Automated pytest test suite for Portfolio Risk and Statistical Arbitrage Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from portfolio_risk import (
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_var_cvar,
    calculate_pairs_zscore
)


def test_sortino_ratio():
    # Returns with some positive and few negative returns
    returns = [0.08, 0.05, -0.01, 0.04, -0.02, 0.06]
    res = calculate_sortino_ratio(returns, target_return=0.0, risk_free_rate=0.01)
    assert res["average_return_pct"] > 0
    assert isinstance(res["sortino_ratio"], float)
    assert res["sortino_ratio"] > 1.0

    # No downside returns -> infinite sortino
    perfect_returns = [0.05, 0.04, 0.03]
    perfect_res = calculate_sortino_ratio(perfect_returns, target_return=0.0, risk_free_rate=0.0)
    assert "Sonsuz" in str(perfect_res["sortino_ratio"])

    # Empty returns
    err = calculate_sortino_ratio([])
    assert "error" in err


def test_calmar_ratio():
    # 25% CAGR, 10% Max Drawdown -> Calmar = 2.5 (Excellent)
    res = calculate_calmar_ratio(cagr_pct=25.0, max_drawdown_pct=10.0)
    assert res["calmar_ratio"] == 2.5
    assert "Mükemmel" in res["risk_reward_verdict"]

    # 10% CAGR, 30% Max Drawdown -> Calmar = 0.33 (Weak)
    weak_res = calculate_calmar_ratio(cagr_pct=10.0, max_drawdown_pct=30.0)
    assert weak_res["calmar_ratio"] == 0.33
    assert "Zayıf" in weak_res["risk_reward_verdict"]

    # Invalid drawdown
    err = calculate_calmar_ratio(10.0, 0.0)
    assert "error" in err


def test_var_cvar():
    # Portfolio: 1,000,000 TL, daily mean = 0.0%, daily std = 2.0%
    # 95% 1-day VaR ~= 1.645 * 2% = 3.29% = 32,900 TL
    res = calculate_var_cvar(
        mean_daily_return_pct=0.0,
        std_daily_dev_pct=2.0,
        portfolio_value=1000000.0,
        confidence_level=0.95
    )
    assert res["var_1day_pct"] == 3.29
    assert res["var_1day_amount"] == 32900.0
    # CVaR is always greater than VaR
    assert res["cvar_1day_amount"] > res["var_1day_amount"]
    assert "açıklama" in res or "explanation" in res

    # 99% VaR is higher than 95% VaR
    res_99 = calculate_var_cvar(
        mean_daily_return_pct=0.0,
        std_daily_dev_pct=2.0,
        portfolio_value=1000000.0,
        confidence_level=0.99
    )
    assert res_99["var_1day_amount"] > res["var_1day_amount"]

    # Invalid
    err = calculate_var_cvar(0.0, -1.0, 0)
    assert "error" in err


def test_pairs_zscore():
    # Price A = 105, Price B = 50, Beta = 2.0 -> Spread = 105 - (2 * 50) = 5.0
    # Spread mean = 0.0, std = 2.0 -> Z-score = (5 - 0) / 2 = 2.5 -> Sell A / Buy B
    sell_res = calculate_pairs_zscore(
        price_a=105.0,
        price_b=50.0,
        hedge_ratio_beta=2.0,
        spread_mean=0.0,
        spread_std=2.0
    )
    assert sell_res["current_spread"] == 5.0
    assert sell_res["z_score"] == 2.5
    assert "A SAT / B AL" in sell_res["trading_signal"]

    # Under-valued spread: Spread = -5.0 -> Z-score = -2.5 -> Buy A / Sell B
    buy_res = calculate_pairs_zscore(
        price_a=95.0,
        price_b=50.0,
        hedge_ratio_beta=2.0,
        spread_mean=0.0,
        spread_std=2.0
    )
    assert buy_res["z_score"] == -2.5
    assert "A AL / B SAT" in buy_res["trading_signal"]

    # Mean reversion close: Z-score = 0.2 -> Take profit
    neutral_res = calculate_pairs_zscore(
        price_a=100.4,
        price_b=50.0,
        hedge_ratio_beta=2.0,
        spread_mean=0.0,
        spread_std=2.0
    )
    assert neutral_res["z_score"] == 0.2
    assert "KÂR AL" in neutral_res["trading_signal"]

    # Invalid std
    err = calculate_pairs_zscore(100, 50, 2, 0, 0)
    assert "error" in err
