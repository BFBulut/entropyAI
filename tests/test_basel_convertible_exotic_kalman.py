"""Automated pytest test suite for Basel III/IV Banking, Convertible Bond Arbitrage,
Exotic Barrier Options, State-Space Kalman Dynamic Pairs Trading & Downside Risk Profile:
- Basel III / Basel IV Capital Adequacy & Liquidity (CET1, Tier 1, CAR, Leverage, LCR, NSFR & Buffers)
- Convertible Bond Arbitrage & Greeks Dynamics (Parity, Conversion Premium, Bond Floor, Delta Hedge & Break-even)
- Exotic Derivatives & Barrier Options (Up-and-Out/In, Down-and-Out/In, In-Out Parity, Digital Options & Pin Risk)
- State-Space Kalman Filter Dynamic Pairs Trading (Time-Varying Beta & Alpha, Innovation Covariance & Adaptive Z-Score)
- Distribution-Agnostic Risk & Drawdown Analytics (Omega Ratio, Ulcer Index, Pain Index, Martin Ratio & Higher Moments)
"""

import subprocess
import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from basel_convertible_exotic_kalman import (
    calculate_basel_capital_and_liquidity,
    calculate_convertible_bond_and_arbitrage,
    calculate_barrier_and_digital_options,
    calculate_kalman_dynamic_pairs_trading,
    calculate_omega_ratio_and_ulcer_index
)


def test_basel_capital_and_liquidity():
    # 1. Well-capitalized top-tier bank
    res_well = calculate_basel_capital_and_liquidity(
        cet1_capital=12.0,
        tier1_capital=14.0,
        total_capital=18.0,
        rwa_credit=80.0,
        rwa_market=10.0,
        rwa_operational=10.0,
        total_exposure_leverage=250.0,
        hqla_amount=25.0,
        net_cash_outflows_30d=18.0,
        asf_amount=120.0,
        rsf_amount=100.0,
        capital_conservation_buffer_pct=2.5,
        countercyclical_buffer_pct=0.5,
        gsib_surcharge_pct=1.0
    )
    assert res_well["total_rwa"] == 100.0
    assert res_well["cet1_ratio_pct"] == 12.0
    assert res_well["tier1_ratio_pct"] == 14.0
    assert res_well["total_capital_ratio_pct"] == 18.0
    assert res_well["leverage_ratio_pct"] == 5.6
    assert res_well["lcr_pct"] == 138.89
    assert res_well["nsfr_pct"] == 120.0
    assert res_well["regulatory_compliance"]["overall_compliant"] is True
    assert res_well["regulatory_compliance"]["cet1_compliant"] is True
    assert res_well["regulatory_compliance"]["min_cet1_required_pct"] == 8.5  # 4.5 + 2.5 + 0.5 + 1.0 = 8.5
    assert res_well["surplus_deficit"]["cet1_surplus"] > 0
    assert "Kuvvetli Sermaye" in res_well["buffer_status"]

    # 2. Distressed bank failing CET1 and CAR
    res_distressed = calculate_basel_capital_and_liquidity(
        cet1_capital=5.0,
        tier1_capital=6.0,
        total_capital=8.0,
        rwa_credit=90.0,
        rwa_market=10.0,
        rwa_operational=10.0,
        total_exposure_leverage=300.0,
        hqla_amount=10.0,
        net_cash_outflows_30d=15.0,
        asf_amount=85.0,
        rsf_amount=100.0
    )
    assert res_distressed["total_rwa"] == 110.0
    assert res_distressed["regulatory_compliance"]["overall_compliant"] is False
    assert res_distressed["regulatory_compliance"]["cet1_compliant"] is False
    assert res_distressed["regulatory_compliance"]["lcr_compliant"] is False
    assert res_distressed["regulatory_compliance"]["nsfr_compliant"] is False
    assert "KRİTİK SERMAYE YETERSİZLİĞİ" in res_distressed["buffer_status"]

    # 3. Validation errors
    err = calculate_basel_capital_and_liquidity(
        cet1_capital=10.0, tier1_capital=12.0, total_capital=15.0,
        rwa_credit=0.0, rwa_market=0.0, rwa_operational=0.0,
        total_exposure_leverage=100.0, hqla_amount=10.0, net_cash_outflows_30d=10.0, asf_amount=100.0, rsf_amount=100.0
    )
    assert "error" in err


def test_convertible_bond_and_arbitrage():
    # 1. Balanced Hybrid Convertible Bond
    res_hybrid = calculate_convertible_bond_and_arbitrage(
        bond_price=1080.0,
        par_value=1000.0,
        conversion_ratio=25.0,
        stock_price=40.0,
        coupon_rate_pct=3.0,
        stock_dividend_yield_pct=1.0,
        bond_floor=880.0,
        option_delta=0.60,
        credit_spread_bps=200.0
    )
    assert res_hybrid["conversion_value_parity"] == 1000.0
    assert res_hybrid["conversion_premium_pct"] == 8.0  # (1080 - 1000) / 1000 = 8.0%
    assert res_hybrid["investment_premium_pct"] == 22.73
    assert res_hybrid["delta_hedge_shares_short_per_bond"] == 15.0  # 25 * 0.60 = 15.0
    assert res_hybrid["coupon_income_dollar"] == 30.0
    assert res_hybrid["dividend_income_dollar"] == 10.0
    assert res_hybrid["net_income_advantage_dollar"] == 20.0
    assert res_hybrid["break_even_years"] == 4.0  # 80 / 20 = 4.0 years
    assert "Dengeli" in res_hybrid["cb_profile"]

    # 2. Busted Convertible Bond (deep OTM, stock price collapsed)
    res_busted = calculate_convertible_bond_and_arbitrage(
        bond_price=750.0,
        par_value=1000.0,
        conversion_ratio=20.0,
        stock_price=15.0,
        coupon_rate_pct=4.0,
        stock_dividend_yield_pct=0.0,
        bond_floor=700.0,
        option_delta=0.15
    )
    assert res_busted["conversion_value_parity"] == 300.0
    assert res_busted["conversion_premium_pct"] == 150.0
    assert "Kırık" in res_busted["cb_profile"]

    # 3. Equity Surrogate CB (deep ITM)
    res_equity = calculate_convertible_bond_and_arbitrage(
        bond_price=2100.0,
        par_value=1000.0,
        conversion_ratio=25.0,
        stock_price=82.0,
        coupon_rate_pct=1.0,
        stock_dividend_yield_pct=0.5,
        bond_floor=800.0,
        option_delta=0.92
    )
    assert res_equity["conversion_value_parity"] == 2050.0
    assert "Hisse Vekili" in res_equity["cb_profile"]

    # 4. Error handling
    err = calculate_convertible_bond_and_arbitrage(
        bond_price=-100.0, par_value=1000.0, conversion_ratio=25.0, stock_price=40.0,
        coupon_rate_pct=2.0, stock_dividend_yield_pct=1.0, bond_floor=850.0, option_delta=0.5
    )
    assert "error" in err


def test_barrier_and_digital_options():
    # 1. Up-and-Out Call & In-Out Parity
    res_uo = calculate_barrier_and_digital_options(
        spot_price=100.0,
        strike_price=100.0,
        barrier_level=140.0,
        time_to_expiry_years=0.5,
        risk_free_rate_pct=5.0,
        volatility_pct=25.0,
        option_type="call",
        barrier_type="up-and-out",
        cash_or_nothing_payout=10.0
    )
    assert res_uo["barrier_price"] > 0.0
    assert res_uo["barrier_price"] < res_uo["vanilla_benchmark_price"]
    assert res_uo["in_out_parity_error"] < 1e-4
    assert res_uo["digital_options"]["cash_or_nothing_price"] > 0.0
    assert res_uo["digital_options"]["asset_or_nothing_price"] > 0.0
    assert "DÜŞÜK PIN RİSKİ" in res_uo["pin_risk_metrics"]["pin_risk_level"]

    # 2. Already Knocked-out Call (Spot >= Barrier)
    res_knocked = calculate_barrier_and_digital_options(
        spot_price=130.0,
        strike_price=100.0,
        barrier_level=125.0,
        time_to_expiry_years=0.5,
        risk_free_rate_pct=5.0,
        volatility_pct=25.0,
        option_type="call",
        barrier_type="up-and-out"
    )
    assert res_knocked["barrier_price"] == 0.0

    # 3. Down-and-Out Put & Down-and-In Parity
    res_do_put = calculate_barrier_and_digital_options(
        spot_price=100.0,
        strike_price=100.0,
        barrier_level=80.0,
        time_to_expiry_years=0.5,
        risk_free_rate_pct=5.0,
        volatility_pct=25.0,
        option_type="put",
        barrier_type="down-and-out"
    )
    assert res_do_put["barrier_price"] > 0.0
    assert res_do_put["in_out_parity_error"] < 1e-4

    # 4. Pin Risk Near Barrier
    res_pin = calculate_barrier_and_digital_options(
        spot_price=124.5,
        strike_price=100.0,
        barrier_level=125.0,
        time_to_expiry_years=0.05,
        risk_free_rate_pct=5.0,
        volatility_pct=20.0,
        option_type="call",
        barrier_type="up-and-out"
    )
    assert "AŞIRI YÜKSEK PIN RISKI" in res_pin["pin_risk_metrics"]["pin_risk_level"]

    # 5. Error handling
    err = calculate_barrier_and_digital_options(
        spot_price=100.0, strike_price=100.0, barrier_level=120.0,
        time_to_expiry_years=-0.1, risk_free_rate_pct=5.0, volatility_pct=20.0
    )
    assert "error" in err


def test_kalman_dynamic_pairs_trading():
    # 1. Cointegrated series with constant slope (beta ~ 1.5)
    # y = 1.5 * x + noise
    x_series = [10.0 + 0.5 * i for i in range(25)]
    y_series = [1.5 * x + ((-1) ** i) * 0.2 for i, x in enumerate(x_series)]

    res_kalman = calculate_kalman_dynamic_pairs_trading(
        price_series_y=y_series,
        price_series_x=x_series,
        delta=1e-4,
        vt_variance=1e-3
    )
    assert res_kalman["num_observations"] == 25
    assert abs(res_kalman["latest_beta"] - 1.5) < 0.2
    assert "trading_signal" in res_kalman
    assert "beta_drift_range" in res_kalman

    # 2. Structural break series (beta starts at 1.0, jumps to 2.5)
    x_break = [20.0 + i for i in range(30)]
    y_break = [1.0 * x for x in x_break[:15]] + [2.5 * x for x in x_break[15:]]
    res_break = calculate_kalman_dynamic_pairs_trading(y_break, x_break, delta=1e-3)
    assert res_break["structural_break_detected"] is True
    assert res_break["latest_beta"] > 1.8

    # 3. Length mismatch error
    err = calculate_kalman_dynamic_pairs_trading([1.0, 2.0], [1.0])
    assert "error" in err


def test_omega_ratio_and_ulcer_index():
    # 1. Positive asymmetric returns (skewed right, low drawdowns)
    returns_pos = [0.5, 0.4, 0.6, 0.3, 0.5, 0.4, 0.2, 8.0, -0.1, 0.5]
    res_pos = calculate_omega_ratio_and_ulcer_index(
        returns_pct=returns_pos,
        threshold_pct=0.0,
        risk_free_rate_annual_pct=3.0,
        periods_per_year=252
    )
    assert res_pos["omega_ratio"] > 5.0
    assert res_pos["ulcer_index"] < 2.0
    assert res_pos["martin_ratio"] > 0.0
    assert res_pos["skewness"] > 0.0
    assert "Pozitif Asimetri" in res_pos["distribution_profile"]

    # 2. Severe crash returns (large drawdowns, high Ulcer index)
    returns_crash = [1.0, 0.5, -8.0, -12.0, -5.0, 2.0, 1.0, -4.0, 0.5]
    res_crash = calculate_omega_ratio_and_ulcer_index(
        returns_pct=returns_crash,
        threshold_pct=0.0
    )
    assert res_crash["max_drawdown_pct"] > 20.0
    assert res_crash["ulcer_index"] > 10.0
    assert res_crash["pain_index"] > 5.0
    assert "Negatif Asimetri" in res_crash["distribution_profile"]

    # 3. Minimum length validation
    err = calculate_omega_ratio_and_ulcer_index([1.0])
    assert "error" in err


def test_cli_execution():
    script_path = skill_scripts_dir / "basel_convertible_exotic_kalman.py"

    # Test basel CLI
    cmd_basel = [
        sys.executable, str(script_path), "basel",
        "--cet1", "12.0", "--tier1", "14.0", "--total-capital", "18.0",
        "--rwa-credit", "80.0", "--rwa-market", "10.0", "--rwa-op", "10.0",
        "--leverage-exp", "250.0", "--hqla", "25.0", "--outflows-30d", "18.0",
        "--asf", "120.0", "--rsf", "100.0"
    ]
    p = subprocess.run(cmd_basel, capture_output=True, text=True, check=True)
    assert "cet1_ratio_pct" in p.stdout

    # Test convertible CLI
    cmd_cb = [
        sys.executable, str(script_path), "convertible",
        "--bond-price", "1080.0", "--par", "1000.0", "--conversion-ratio", "25.0",
        "--stock-price", "40.0", "--coupon-pct", "3.0", "--div-yield-pct", "1.0",
        "--bond-floor", "880.0", "--delta", "0.60"
    ]
    p_cb = subprocess.run(cmd_cb, capture_output=True, text=True, check=True)
    assert "conversion_value_parity" in p_cb.stdout

    # Test barrier CLI
    cmd_barrier = [
        sys.executable, str(script_path), "barrier",
        "--spot", "100.0", "--strike", "100.0", "--barrier", "125.0",
        "--expiry", "0.5", "--rate-pct", "5.0", "--vol-pct", "25.0"
    ]
    p_bar = subprocess.run(cmd_barrier, capture_output=True, text=True, check=True)
    assert "barrier_price" in p_bar.stdout

    # Test kalman CLI
    cmd_kal = [
        sys.executable, str(script_path), "kalman",
        "--series-y", "10.0, 11.2, 12.1, 13.5, 14.8, 15.9",
        "--series-x", "5.0, 5.5, 6.0, 6.7, 7.4, 7.9"
    ]
    p_kal = subprocess.run(cmd_kal, capture_output=True, text=True, check=True)
    assert "latest_beta" in p_kal.stdout

    # Test omega CLI
    cmd_om = [
        sys.executable, str(script_path), "omega",
        "--returns", "1.2, -0.5, 2.3, -1.1, 3.4, 0.8"
    ]
    p_om = subprocess.run(cmd_om, capture_output=True, text=True, check=True)
    assert "omega_ratio" in p_om.stdout
