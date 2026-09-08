"""
Automated Test Suite: Fed Net Liquidity Plumbing, Commodity Super-Cycles & Negative Oil Physics.
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import pytest

from src.entropy.agent_desk.analysis.macro_plumbing import (
    FedLiquidityPoint,
    FedLiquidityResult,
    FedPlumbingEngine,
    CommodityMarketState,
    CommodityCycleResult,
    CommoditySuperCycleModel,
    CushingStorageState,
    NegativePriceResult,
    NegativeOilPhysicsEngine,
)


# ==============================================================================
# 1. FED NET LIQUIDITY PLUMBING TESTS
# ==============================================================================

def test_fed_net_liquidity_calculation():
    """
    Verifies that Net Liquidity = WALCL - TGA - ON_RRP.
    """
    engine = FedPlumbingEngine(us_gdp_billions=28_000.0)
    # WALCL = 7500B, TGA = 750B, ON_RRP = 450B
    pt = FedLiquidityPoint(
        date="2026-09-01",
        fed_assets_walcl=7500.0,
        tga_balance=750.0,
        on_rrp_balance=450.0,
        bank_reserves=3300.0,
    )
    result = engine.analyze_point(pt)

    # Net Liquidity = 7500 - 750 - 450 = 6300B
    assert result.net_liquidity == 6300.0
    assert result.bank_reserves_estimated == 3300.0
    assert result.is_reserves_scarce is False
    assert "COMFORTABLE" in result.liquidity_regime or "ABUNDANT" in result.liquidity_regime


def test_fed_reserve_scarcity_and_lclor_warning():
    """
    Verifies that bank reserves falling below LCLoR trigger repo spike stress warnings.
    """
    # LCLoR = 28000 * 0.105 = 2940B
    engine = FedPlumbingEngine(us_gdp_billions=28_000.0)
    pt_stressed = FedLiquidityPoint(
        date="2026-09-06",
        fed_assets_walcl=6800.0,
        tga_balance=850.0,
        on_rrp_balance=350.0,
        bank_reserves=2700.0,  # Below 2940B threshold!
    )
    result = engine.analyze_point(pt_stressed)

    assert result.is_reserves_scarce is True
    assert "SCARCE" in result.liquidity_regime
    assert result.reserve_buffer_pct < 0.0


def test_fed_series_liquidity_impulse():
    """
    Verifies chronological time series processing and 4-week liquidity impulse.
    """
    engine = FedPlumbingEngine()
    series = [
        FedLiquidityPoint(date="W1", fed_assets_walcl=7500.0, tga_balance=700.0, on_rrp_balance=500.0),
        FedLiquidityPoint(date="W2", fed_assets_walcl=7450.0, tga_balance=800.0, on_rrp_balance=550.0),
    ]
    results = engine.analyze_series(series)

    assert len(results) == 2
    # W1 Net Liq = 7500 - 700 - 500 = 6300
    # W2 Net Liq = 7450 - 800 - 550 = 6100 (Contracting)
    assert results[0].net_liquidity == 6300.0
    assert results[1].net_liquidity == 6100.0
    assert results[1].weekly_impulse_pct is not None
    assert results[1].weekly_impulse_pct < 0.0


# ==============================================================================
# 2. COMMODITY SUPER-CYCLES & STOCKS-TO-USE TESTS
# ==============================================================================

def test_commodity_surplus_regime():
    """
    Verifies that high Stocks-to-Use (S/U > 25%) signals market surplus and Contango.
    """
    # 400M ending stocks / 1000M consumption = S/U 40%
    state = CommodityMarketState(
        commodity_name="Corn",
        ending_stocks=400.0,
        total_consumption=1000.0,
        baseline_price=4.5,
    )
    result = CommoditySuperCycleModel.evaluate(state)

    assert result.stocks_to_use_ratio == 0.40
    assert "SURPLUS" in result.regime
    assert "Contango" in result.term_structure_expectation
    assert result.model_implied_price < 5.0


def test_commodity_scarcity_super_cycle():
    """
    Verifies that low Stocks-to-Use (S/U < 15%) triggers exponential price spike & Backwardation.
    """
    # 80M ending stocks / 1000M consumption = S/U 8%
    state = CommodityMarketState(
        commodity_name="Copper",
        ending_stocks=80.0,
        total_consumption=1000.0,
        baseline_price=7000.0,
    )
    result = CommoditySuperCycleModel.evaluate(state)

    assert result.stocks_to_use_ratio == 0.08
    assert "SUPER-CYCLE" in result.regime
    assert "Backwardation" in result.term_structure_expectation
    # Price must spike well above baseline due to convex scarcity exponent
    assert result.model_implied_price > 10_000.0


# ==============================================================================
# 3. NEGATIVE OIL PRICE PHYSICS (APRIL 20, 2020 WTI SIMULATION)
# ==============================================================================

def test_normal_oil_market_positive_clearing():
    """
    Verifies that under unconstrained storage conditions, clearing price is positive.
    """
    # Cushing 50% full (38M / 76M)
    state = CushingStorageState(
        cushing_inventory_mb=38.0,
        max_cushing_capacity_mb=76.0,
        benchmark_ref_price=25.0,
        hours_to_contract_expiry=72.0,
        pipeline_outflow_bottleneck=0.2,
    )
    res = NegativeOilPhysicsEngine.calculate_clearing_price(state)

    assert res.utilization_pct == 50.0
    assert res.is_negative_clearing is False
    assert res.simulated_clearing_price > 0.0


def test_negative_oil_crash_simulation_april_20_2020():
    """
    Recreates the exact April 20, 2020 market failure:
    Cushing tank capacity exhausted (98%), contract expiring in 2 hours,
    distress liquidation forcing clearing price deep into negative territory (-37 $/bbl).
    """
    # 74.8M stored out of 76M capacity (98.4% utilization)
    state = CushingStorageState(
        cushing_inventory_mb=74.8,
        max_cushing_capacity_mb=76.0,
        benchmark_ref_price=18.0,
        hours_to_contract_expiry=2.0,
        pipeline_outflow_bottleneck=0.95,
        panic_liquidation_factor=2.2,
    )
    res = NegativeOilPhysicsEngine.calculate_clearing_price(state)

    assert res.utilization_pct > 95.0
    assert res.is_negative_clearing is True
    assert res.simulated_clearing_price < 0.0  # Negative clearing price!
    assert "NEGATİF FİYAT KIRILMASI" in res.physical_bottleneck_alert
    assert res.marginal_storage_cost_per_bbl > 20.0
