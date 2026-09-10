"""Automated pytest test suite for Factor Investing, SABR Swaptions, Fed Balance Sheet Liquidity & IFRS-16 Forensics:
- Time-Series Momentum (TSMOM) & Volatility Scaling
- Share Buyback True Economic Value Creation
- IFRS-16 Operating Lease Capitalization
- SABR Swaption Volatility Model
- Fed Balance Sheet Net Liquidity Flow
"""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from factor_liquidity_commodity import (
    calculate_time_series_momentum,
    calculate_share_buyback_roi,
    calculate_ifrs16_lease_capitalization,
    calculate_sabr_implied_volatility,
    calculate_on_rrp_tga_liquidity_drain
)


def test_time_series_momentum():
    # Long trend with 12m return = +25%, daily vol = 1.0% (~15.87% annual vol), target = 15%
    res = calculate_time_series_momentum(
        past_returns_12m=0.25,
        recent_daily_volatility=0.01,
        annual_target_volatility=0.15
    )
    assert res["trend_signal"] == 1
    assert "LONG" in res["trend_direction"]
    assert 0.9 <= res["volatility_scaled_position_weight"] <= 1.0

    # Short trend with negative returns
    res_short = calculate_time_series_momentum(
        past_returns_12m=-0.15,
        recent_daily_volatility=0.015,
        annual_target_volatility=0.15
    )
    assert res_short["trend_signal"] == -1
    assert "SHORT" in res_short["trend_direction"]
    assert res_short["volatility_scaled_position_weight"] < 0

    # Invalid inputs
    err1 = calculate_time_series_momentum(0.10, -0.01)
    assert "error" in err1
    err2 = calculate_time_series_momentum(0.10, 0.01, -0.1)
    assert "error" in err2


def test_share_buyback_roi():
    # Value creating buyback: P = 50, EPS = 5 (E/P = 10%), Debt = 6%, Tax = 25% (After-tax debt = 4.5%)
    # Spread = 10% - 4.5% = +5.5% (Accretive & Value Creating)
    res = calculate_share_buyback_roi(
        share_price=50.0,
        eps=5.0,
        debt_interest_rate_pct=6.0,
        corporate_tax_rate_pct=25.0
    )
    assert res["pe_ratio"] == 10.0
    assert res["earnings_yield_pct"] == 10.0
    assert res["after_tax_debt_cost_pct"] == 4.5
    assert res["economic_spread_pct"] == 5.5
    assert "GERÇEK DEĞER YARATAN" in res["buyback_evaluation"]

    # Value destroying buyback: P = 200, EPS = 4 (E/P = 2%), Debt = 7%, Tax = 25% (After-tax debt = 5.25%)
    # Spread = 2% - 5.25% = -3.25%
    res_destr = calculate_share_buyback_roi(200.0, 4.0, 7.0, 25.0)
    assert res_destr["economic_spread_pct"] < 0
    assert "DEĞER YOK EDEN" in res_destr["buyback_evaluation"]

    # Invalid inputs
    err = calculate_share_buyback_roi(-50.0, 5.0, 6.0)
    assert "error" in err


def test_ifrs16_lease_capitalization():
    # Annual lease payment = 10M, 5 years, discount = 5%
    # Annuity PV ~ 43.29M
    # Reported EBITDA = 50M, Reported Net Debt = 100M
    res = calculate_ifrs16_lease_capitalization(
        annual_lease_payment=10.0,
        lease_term_years=5,
        discount_rate_pct=5.0,
        reported_ebitda=50.0,
        reported_net_debt=100.0
    )
    assert res["adjusted_ebitda"] == 60.0  # 50 + 10
    assert res["adjusted_net_debt"] > 140.0
    assert res["ebitda_inflation_pct"] == 20.0
    assert res["leverage_delta"] > 0

    # Invalid inputs
    err = calculate_ifrs16_lease_capitalization(-10.0, 5, 5.0, 50.0, 100.0)
    assert "error" in err


def test_sabr_implied_volatility():
    # Forward = 4.0% (0.04), Strike = 4.0% (0.04) (ATM)
    # T = 1.0, alpha = 0.05, beta = 0.5, rho = -0.2, nu = 0.4
    res_atm = calculate_sabr_implied_volatility(
        forward_rate=0.04,
        strike_rate=0.04,
        time_to_maturity=1.0,
        alpha=0.05,
        beta=0.5,
        rho=-0.2,
        nu=0.4
    )
    assert res_atm["sabr_implied_volatility_pct"] > 0
    assert "sabr_implied_volatility_pct" in res_atm

    # Near-ATM with strike 4.5%
    res_smile = calculate_sabr_implied_volatility(
        forward_rate=0.04,
        strike_rate=0.045,
        time_to_maturity=1.0,
        alpha=0.05,
        beta=0.5,
        rho=-0.4,
        nu=0.4
    )
    assert res_smile["sabr_implied_volatility_pct"] > 0
    assert "NEGATİF ÇARPIKLIK" in res_smile["volatility_skew_diagnosis"]

    # Invalid inputs
    err1 = calculate_sabr_implied_volatility(-0.04, 0.04, 1.0, 0.05, 0.5, 0.0, 0.4)
    assert "error" in err1
    err2 = calculate_sabr_implied_volatility(0.04, 0.04, 1.0, 0.05, 0.5, -1.5, 0.4)
    assert "error" in err2


def test_on_rrp_tga_liquidity_drain():
    # Start reserves = $3,200B
    # Fed expands assets by $100B, TGA increases by $200B (Treasury debt issuance), RRP increases by $50B
    # Delta reserves = 100 - 200 - 50 = -150B (Severe Liquidity Drain)
    res_drain = calculate_on_rrp_tga_liquidity_drain(
        start_bank_reserves=3200.0,
        delta_tga=200.0,
        delta_on_rrp=50.0,
        delta_fed_assets=100.0
    )
    assert res_drain["net_liquidity_change_billion_usd"] == -150.0
    assert res_drain["end_bank_reserves_billion_usd"] == 3050.0
    assert "ŞİDDETLİ LİKİDİTE ÇEKİLİŞİ" in res_drain["liquidity_regime_diagnosis"]

    # Liquidity injection: TGA spends down by -$200B, RRP empties by -$100B
    # Delta reserves = 0 - (-200) - (-100) = +300B
    res_inj = calculate_on_rrp_tga_liquidity_drain(
        start_bank_reserves=3000.0,
        delta_tga=-200.0,
        delta_on_rrp=-100.0,
        delta_fed_assets=0.0
    )
    assert res_inj["net_liquidity_change_billion_usd"] == 300.0
    assert "GÜÇLÜ LİKİDİTE ENJEKSİYONU" in res_inj["liquidity_regime_diagnosis"]
