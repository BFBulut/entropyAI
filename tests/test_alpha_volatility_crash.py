"""Automated pytest test suite for Quantitative Alpha, Volatility and Crash Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from alpha_volatility_crash import (
    calculate_grinold_ir,
    calculate_vrp_variance_swap_payout,
    calculate_dividend_recap_impact,
    calculate_circuit_breaker_distance
)


def test_grinold_ir():
    # IC = 0.04, Breadth N = 2500 -> IR = 0.04 * 50 = 2.0 (Medallion Tier)
    res = calculate_grinold_ir(information_coefficient=0.04, breadth_n=2500.0)
    assert res["information_ratio_ir"] == 2.0
    assert "EFSANEVİ" in res["performance_verdict"]

    # Low breadth: IC = 0.15, N = 4 -> IR = 0.15 * 2 = 0.30 (Weak)
    low_res = calculate_grinold_ir(information_coefficient=0.15, breadth_n=4.0)
    assert low_res["information_ratio_ir"] == 0.30
    assert "ZAYIF" in low_res["performance_verdict"]

    # Invalid breadth
    err = calculate_grinold_ir(0.05, 0.0)
    assert "error" in err


def test_vrp_variance_swap_payout():
    # IV = 20%, RV = 16% -> VRP = +4.0%
    # Strike var = 0.04, Realized var = 0.0256. Diff = 0.0144
    # Vega notional = 10,000 -> Variance notional = 10,000 / (2 * 0.20) = 25,000
    # Payout = 0.0144 * 25,000 = 360.0
    res = calculate_vrp_variance_swap_payout(
        implied_vol_pct=20.0,
        realized_vol_pct=16.0,
        vega_notional=10000.0
    )
    assert res["volatility_risk_premium_pct"] == 4.0
    assert res["variance_seller_payout"] == 360.0
    assert "POZİTİF VRP HASADI" in res["arbitrage_status"]

    # Volatility shock: RV = 28%, IV = 20% -> Loss for seller
    loss_res = calculate_vrp_variance_swap_payout(20.0, 28.0, 10000.0)
    assert loss_res["volatility_risk_premium_pct"] == -8.0
    assert loss_res["variance_seller_payout"] < 0
    assert "VOLATİLİTE ŞOKU" in loss_res["arbitrage_status"]

    # Invalid
    err = calculate_vrp_variance_swap_payout(0, 10)
    assert "error" in err


def test_dividend_recap_impact():
    # EBITDA = 20M, Existing debt = 30M, New debt = 80M -> Total debt = 110M
    # Post-recap leverage = 110 / 20 = 5.5x (Distress alert >= 5.0x)
    # Sponsor initial equity = 70M, Dividend = 75M -> Cash returned = 107.1% (De-risked)
    res = calculate_dividend_recap_impact(
        ebitda=20.0,
        existing_debt=30.0,
        new_debt_raised=80.0,
        pe_sponsor_equity=70.0,
        cash_dividend_distributed=75.0
    )
    assert res["post_recap_leverage_ratio"] == 5.5
    assert res["cash_returned_to_sponsor_pct"] > 100.0
    assert "TAM RİSKSİZLEŞTİRME" in res["sponsor_risk_status"]
    assert "KRİTİK İFLAS / TEMERRÜT" in res["company_distress_alert"]

    # Invalid input
    err = calculate_dividend_recap_impact(0, 10, 10, 0, 10)
    assert "error" in err


def test_circuit_breaker_distance():
    # Base price = 100, Band = 10% -> Upper = 110, Lower = 90
    # Current = 109.5 -> Distance to upper = 0.5 / 109.5 = 0.46% (Imminent halt)
    res = calculate_circuit_breaker_distance(current_price=109.5, base_price=100.0, limit_band_pct=10.0)
    assert res["upper_limit"] == 110.0
    assert res["lower_limit"] == 90.0
    assert res["circuit_breaker_alert"] is True
    assert "DEVRE KESİCİ YAKIN" in res["status"]

    # Safe price: Current = 102 -> Distance to upper = 8/102 = 7.84%
    safe_res = calculate_circuit_breaker_distance(102.0, 100.0, 10.0)
    assert safe_res["circuit_breaker_alert"] is False
    assert "Güvenli İşlem Bandı" in safe_res["status"]

    # Invalid input
    err = calculate_circuit_breaker_distance(100, 0)
    assert "error" in err
