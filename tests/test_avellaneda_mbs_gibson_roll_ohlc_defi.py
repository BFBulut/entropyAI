import math
from pathlib import Path
import sys
import pytest

# Ensure scripts directory is in path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from avellaneda_mbs_gibson_roll_ohlc_defi import (
    fit_ornstein_uhlenbeck_process,
    avellaneda_lee_stat_arb_analysis,
    calculate_mbs_prepayment_and_cashflows,
    mbs_negative_convexity_and_oas,
    gibson_schwartz_futures_pricing,
    roll_effective_spread,
    calculate_ohlc_volatility_estimators,
    defi_jump_rate_model,
    defi_liquidation_cascade_simulation
)


def test_fit_ornstein_uhlenbeck_process():
    # Synthetic mean-reverting series around mean 0
    series = [0.0, 0.45, 0.30, 0.15, -0.20, -0.40, -0.25, 0.05, 0.35, 0.20, -0.10, -0.30, -0.05, 0.10, 0.0]
    res = fit_ornstein_uhlenbeck_process(series)
    assert res["is_mean_reverting"] is True
    assert res["kappa_reversion_speed"] > 0.0
    assert res["half_life_days"] > 0.0
    assert "s_score" in res
    assert res["signal"] in ["OPEN_SHORT", "OPEN_LONG", "CLOSE_POSITION", "HOLD", "STOP_LOSS_BREAK"]


def test_avellaneda_lee_stat_arb_analysis():
    # Asset and benchmark with positive beta
    bench = [100.0, 101.0, 102.5, 101.8, 103.0, 102.2, 104.0, 103.5, 105.0, 104.2, 106.0, 105.5, 107.0, 106.8, 108.0]
    asset = [50.0, 50.8, 51.6, 51.0, 51.9, 51.2, 52.4, 52.0, 53.1, 52.5, 53.8, 53.2, 54.3, 54.1, 55.0]
    res = avellaneda_lee_stat_arb_analysis(asset, bench)
    assert res["beta"] > 0.0
    assert res["residual_series_length"] == len(asset)
    assert "ou_parameters" in res
    assert res["ou_parameters"]["s_score"] is not None


def test_calculate_mbs_prepayment_and_cashflows():
    res = calculate_mbs_prepayment_and_cashflows(
        balance=500000.0,
        wac=0.065,
        term_months=360,
        psa_speed=150.0,
        refi_rate=0.050
    )
    assert res["initial_balance"] == 500000.0
    assert res["wal_years"] > 0.0
    assert res["wal_years"] < 30.0  # Prepayments shorten WAL significantly below 30
    assert res["total_prepayments"] > 0.0
    assert res["prepayment_ratio_pct"] > 0.0
    assert len(res["sample_cashflows"]) > 0


def test_mbs_negative_convexity_and_oas():
    res = mbs_negative_convexity_and_oas(
        base_price=103.5,
        yield_curve_rate=0.045,
        z_spread_bps=165.0,
        oas_bps=110.0
    )
    assert res["option_cost_bps"] == pytest.approx(55.0, 0.1)
    assert res["is_negatively_convex"] is True
    assert res["convexity_measure"] < 0.0
    # Asymmetry: yield drop upside is smaller than yield rise downside
    assert res["asymmetry_ratio"] < 1.0


def test_gibson_schwartz_futures_pricing():
    # High convenience yield -> Backwardation
    res_back = gibson_schwartz_futures_pricing(
        spot_price=80.0,
        convenience_yield=0.12,
        maturity=1.0,
        risk_free_rate=0.04,
        kappa=0.35,
        alpha=0.05,
        sigma1=0.28,
        sigma2=0.18,
        rho=0.60
    )
    assert res_back["curve_state"] == "BACKWARDATION"
    assert res_back["futures_price"] < 80.0
    assert res_back["samuelson_effect_valid"] is True
    assert res_back["futures_volatility_samuelson_pct"] < res_back["instantaneous_spot_volatility_pct"]

    # Low convenience yield -> Contango
    res_cont = gibson_schwartz_futures_pricing(
        spot_price=80.0,
        convenience_yield=0.01,
        maturity=1.0,
        risk_free_rate=0.05,
        kappa=0.35,
        alpha=0.02,
        sigma1=0.25,
        sigma2=0.15,
        rho=0.40
    )
    assert res_cont["curve_state"] == "CONTANGO"
    assert res_cont["futures_price"] > 80.0


def test_roll_effective_spread():
    # Sequence with clear negative bid-ask bounce
    prices = [100.0, 100.5, 100.0, 100.6, 100.1, 100.5, 100.0, 100.7, 100.1, 100.6, 100.0]
    res = roll_effective_spread(prices)
    assert res["autocovariance_lag1"] < 0.0
    assert res["effective_spread_absolute"] > 0.0
    assert res["bounce_status"] == "NORMAL_BOUNCE"


def test_calculate_ohlc_volatility_estimators():
    # 10 daily bars
    bars = [
        {"open": 100.0, "high": 102.5, "low": 99.5, "close": 101.8},
        {"open": 102.0, "high": 103.5, "low": 101.0, "close": 102.2},
        {"open": 101.5, "high": 104.0, "low": 100.8, "close": 103.5},
        {"open": 103.0, "high": 105.0, "low": 102.0, "close": 104.0},
        {"open": 104.2, "high": 104.8, "low": 102.5, "close": 103.0},
        {"open": 102.8, "high": 103.5, "low": 100.5, "close": 101.0},
        {"open": 101.2, "high": 102.8, "low": 99.8, "close": 102.0},
        {"open": 102.5, "high": 105.2, "low": 101.8, "close": 104.5},
        {"open": 104.0, "high": 106.0, "low": 103.2, "close": 105.5},
        {"open": 105.0, "high": 107.0, "low": 104.5, "close": 106.2}
    ]
    res = calculate_ohlc_volatility_estimators(bars)
    assert res["sample_size"] == 10
    assert res["close_to_close_volatility_pct"] > 0.0
    assert res["parkinson_volatility_pct"] > 0.0
    assert res["garman_klass_volatility_pct"] > 0.0
    assert res["rogers_satchell_volatility_pct"] > 0.0
    assert res["yang_zhang_volatility_pct"] > 0.0


def test_defi_jump_rate_model():
    # Below optimal utilization (e.g. 50%)
    res_below = defi_jump_rate_model(total_borrows=50000000.0, total_cash=50000000.0, optimal_utilization=0.80)
    assert res_below["kink_state"] == "BELOW_OPTIMAL"
    assert res_below["borrow_apy_pct"] < 10.0

    # Above optimal utilization (e.g. 90%)
    res_above = defi_jump_rate_model(total_borrows=90000000.0, total_cash=10000000.0, optimal_utilization=0.80)
    assert res_above["kink_state"] == "ABOVE_OPTIMAL_JUMP_ACCELERATION"
    assert res_above["borrow_apy_pct"] > res_below["borrow_apy_pct"]
    assert res_above["protocol_annual_revenue_usd"] > 0.0


def test_defi_liquidation_cascade_simulation():
    # Severe crash: 50% price drop with 10% DEX slippage -> bad debt
    res = defi_liquidation_cascade_simulation(
        collateral_amount=100.0,
        collateral_price=1000.0,   # Initial collateral = $100k
        debt_amount_usd=80000.0,   # Debt = $80k -> HF = (100k * 0.8) / 80k = 1.0
        liquidation_threshold=0.80,
        liquidation_bonus=0.08,
        price_drop_pct=0.50,       # Stressed price = $500 -> Stressed collateral = $50k
        dex_slippage_pct=0.10
    )
    assert res["is_liquidatable"] is True
    assert res["stressed_health_factor"] < 1.0
    assert res["protocol_bad_debt_usd"] > 0.0
    assert "BATIK BORÇ" in res["solvency_status"]
