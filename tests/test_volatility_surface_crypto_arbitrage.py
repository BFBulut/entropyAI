"""Automated pytest test suite for Volatility Surface, Yield Curve Butterfly PCA, M&A Collars & Crypto Arbitrage:
- Dupire Local Volatility & Volatility Skew Dynamics
- Fixed Income Yield Curve PCA Decomposition (Level, Slope, Butterfly) & Convexity Bias
- M&A Floating/Fixed Collar Mechanics & Contingent Value Rights (CVR) Valuation
- Crypto Perpetual Funding Rate Cash-and-Carry Arbitrage & Concentrated Liquidity (Uniswap v3)
- Corporate Treasury Layered FX Hedging Ladder & MTM Liquidity Stress Testing
"""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from volatility_surface_crypto_arbitrage import (
    calculate_dupire_local_volatility_and_bias,
    calculate_pca_yield_curve_and_butterfly,
    calculate_ma_collar_and_cvr,
    calculate_crypto_basis_and_concentrated_liquidity,
    calculate_layered_fx_hedging
)


def test_dupire_local_volatility():
    # ATM option: Spot = 100, Strike = 100, Maturity = 1.0, IV = 20%
    res = calculate_dupire_local_volatility_and_bias(
        implied_vol_pct=20.0,
        dvol_dt_pct=0.01,
        dvol_dk_pct=-0.02,
        d2vol_dk2_pct=0.0005,
        strike_k=100.0,
        spot_s=100.0,
        time_to_maturity=1.0,
        risk_free_r_pct=4.0
    )
    assert res["implied_volatility_pct"] == 20.0
    assert res["dupire_local_volatility_pct"] > 0
    assert "NEGATİF ÇARPIKLIK" in res["skew_regime_diagnosis"]
    assert res["arbitrage_free_surface"] is True

    # Error handling
    err = calculate_dupire_local_volatility_and_bias(-20.0, 0.0, 0.0, 0.0, 100.0, 100.0, 1.0)
    assert "error" in err


def test_pca_yield_curve_and_butterfly():
    # Normal curve with 5Y belly dip: 2Y=4.2%, 5Y=4.0%, 10Y=4.4%, 30Y=4.6%
    # Butterfly = 2 * 4.0 - (4.2 + 4.4) = 8.0 - 8.6 = -0.6% = -60 bps
    res = calculate_pca_yield_curve_and_butterfly(
        yield_2y_pct=4.2,
        yield_5y_pct=4.0,
        yield_10y_pct=4.4,
        yield_30y_pct=4.6,
        rate_volatility_pct=1.0
    )
    assert res["pca_level_factor_pct"] == 4.3
    assert res["slope_2y_10y_pct"] == 0.2
    assert res["butterfly_5y_bps"] == -60.0
    assert "ÇUKURLAŞMA" in res["butterfly_diagnosis"]
    assert res["convexity_bias_bps"] > 0

    # Inverted curve test
    res_inv = calculate_pca_yield_curve_and_butterfly(5.0, 4.5, 4.0, 3.8)
    assert res_inv["slope_2y_10y_pct"] < 0
    assert "TERSİNE DÖNMÜŞ" in res_inv["curve_slope_diagnosis"]


def test_ma_collar_and_cvr():
    # Buyer price = $50, Floor = $40, Cap = $60, Base ratio = 0.50
    # In corridor:
    res_corridor = calculate_ma_collar_and_cvr(
        buyer_stock_price=50.0,
        lower_collar_floor=40.0,
        upper_collar_cap=60.0,
        base_exchange_ratio=0.50,
        cvr_cash_payout=5.0,
        cvr_success_probability_pct=80.0,
        cvr_years_to_payout=2.0,
        discount_rate_pct=8.0
    )
    assert res_corridor["effective_exchange_ratio"] == 0.50
    assert res_corridor["equity_offer_value_per_share"] == 25.0  # 0.50 * 50
    assert "KORİDOR İÇİNDE" in res_corridor["collar_status"]
    # CVR PV = (5.0 * 0.80) / (1.08)^2 = 4.0 / 1.1664 ~ 3.43
    assert 3.40 <= res_corridor["cvr_present_value"] <= 3.45
    assert res_corridor["total_consideration_per_share"] > 28.0

    # Below floor: Buyer drops to $30
    res_floor = calculate_ma_collar_and_cvr(30.0, 40.0, 60.0, 0.50)
    assert "TABAN DEVREYE GİRDİ" in res_floor["collar_status"]
    assert res_floor["equity_offer_value_per_share"] == 20.0  # (0.50 * 40 / 30) * 30 = 20.0

    # Error handling
    err = calculate_ma_collar_and_cvr(50.0, 60.0, 40.0, 0.50)
    assert "error" in err


def test_crypto_basis_and_concentrated_liquidity():
    # Spot = 60,000, Perp = 60,300 (+0.5% basis), 8h funding = 0.05%
    # APR = 0.05% * 3 * 365 = 54.75%
    res = calculate_crypto_basis_and_concentrated_liquidity(
        spot_price=60000.0,
        perp_mark_price=60300.0,
        funding_rate_8h_pct=0.05,
        lp_lower_tick_price=50000.0,
        lp_upper_tick_price=72000.0
    )
    assert res["basis_spread_pct"] == 0.5
    assert res["annualized_funding_apr_pct"] == 54.75
    assert "CASH-AND-CARRY" in res["arbitrage_strategy_recommendation"]
    assert res["lp_in_range"] is True
    assert res["uniswap_v3_capital_efficiency_multiplier"] > 1.0

    # Error handling
    err = calculate_crypto_basis_and_concentrated_liquidity(60000.0, 60300.0, 0.05, 72000.0, 50000.0)
    assert "error" in err


def test_layered_fx_hedging():
    # Quarterly exposure = $10M ($40M annual), Spot = 34.0, Ratios = [80%, 60%, 40%, 20%]
    res = calculate_layered_fx_hedging(
        quarterly_exposure_usd=10000000.0,
        current_spot_usdtry=34.0,
        q1_hedge_ratio_pct=80.0,
        q2_hedge_ratio_pct=60.0,
        q3_hedge_ratio_pct=40.0,
        q4_hedge_ratio_pct=20.0,
        forward_points_annual_pct=35.0
    )
    assert res["annual_total_exposure_usd"] == 40000000.0
    assert res["total_hedged_usd"] == 20000000.0  # 8M + 6M + 4M + 2M
    assert res["overall_hedge_ratio_pct"] == 50.0
    assert res["blended_average_hedged_rate"] > 34.0
    # 10% shock on $20M hedged: $20M * 0.10 = $2,000,000
    assert res["fx_shock_10pct_mtm_liquidity_drain_usd"] == 2000000.0
    assert "OPTIMAL KATMANLI KORUMA" in res["hedging_policy_diagnosis"]

    # Error handling
    err = calculate_layered_fx_hedging(-100.0, 34.0)
    assert "error" in err
