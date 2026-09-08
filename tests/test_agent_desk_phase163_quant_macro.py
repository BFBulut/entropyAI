"""
Comprehensive Unit & Integration Test Suite for Phase 163 Quant and Macro Finance:
1. SABR Model (Hagan et al. 2002 Analytics, ATM Limit, Greeks, Calibration)
2. Factor Investing & Corporate Finance (TSMOM, Buyback Test, IFRS 16)
3. Fed Macro Plumbing & Commodity Physics (Net Liquidity, LCLoR, STU, Negative Oil)
"""

import math
import pytest
import numpy as np

from src.entropy.agent_desk.analysis.sabr_model import (
    SABRParameters,
    SABREngine,
    sabr_implied_volatility,
    black76_call_price,
    black76_put_price,
    black76_greeks,
)
from src.entropy.agent_desk.analysis.factor_investing import (
    TSMOMConfig,
    compute_tsmom_backtest,
    BuybackInput,
    BuybackFinancingMethod,
    evaluate_share_buyback,
    IFRS16LeaseInput,
    capitalize_operating_leases,
)
from src.entropy.agent_desk.analysis.macro_plumbing import (
    FedBalanceSheetInput,
    LCLoRStressLevel,
    evaluate_fed_net_liquidity,
    CommoditySuperCycleInput,
    CommodityRegime,
    evaluate_commodity_scarcity,
    CushingStorageInput,
    OilDeliveryRegime,
    evaluate_negative_oil_dynamics,
)


# ==============================================================================
# 1. SABR MODEL TESTS
# ==============================================================================

def test_sabr_pydantic_validation():
    """Validates boundary conditions and field constraints on SABRParameters."""
    params = SABRParameters(forward=100.0, expiry=1.0, alpha=0.2, beta=0.5, rho=-0.3, nu=0.4)
    assert params.forward == 100.0
    assert params.alpha == 0.2
    assert params.beta == 0.5
    assert params.rho == -0.3
    assert params.nu == 0.4

    # Invalid forward (<= 0)
    with pytest.raises(ValueError):
        SABRParameters(forward=-5.0, expiry=1.0, alpha=0.2)

    # Invalid alpha (<= 0)
    with pytest.raises(ValueError):
        SABRParameters(forward=100.0, expiry=1.0, alpha=0.0)

    # Invalid beta (> 1.0 or < 0.0)
    with pytest.raises(ValueError):
        SABRParameters(forward=100.0, expiry=1.0, alpha=0.2, beta=1.5)

    # Invalid rho (> 1.0)
    with pytest.raises(ValueError):
        SABRParameters(forward=100.0, expiry=1.0, alpha=0.2, rho=1.2)


def test_sabr_atm_continuity():
    """
    Verifies that Hagan general formula seamlessly converges to ATM limit
    as strike K approaches forward F (|K - F| < 1e-6).
    """
    f = 0.035  # 3.5% forward swap rate
    expiry = 5.0
    alpha = 0.02
    beta = 0.5
    rho = -0.2
    nu = 0.35

    vol_atm = sabr_implied_volatility(f, f, expiry, alpha, beta, rho, nu)
    vol_near_atm_up = sabr_implied_volatility(f, f + 1e-5, expiry, alpha, beta, rho, nu)
    vol_near_atm_down = sabr_implied_volatility(f, f - 1e-5, expiry, alpha, beta, rho, nu)

    assert vol_atm > 0.0
    assert abs(vol_atm - vol_near_atm_up) < 1e-4
    assert abs(vol_atm - vol_near_atm_down) < 1e-4


def test_sabr_volatility_smile_and_greeks():
    """Tests smile generation, skew, curvature, and Black-76 Greeks."""
    params = SABRParameters(forward=100.0, expiry=1.0, alpha=2.0, beta=1.0, rho=-0.4, nu=0.5)
    engine = SABREngine(params)

    strikes = [80.0, 90.0, 100.0, 110.0, 120.0]
    smile = engine.generate_smile(strikes)

    assert len(smile.implied_vols) == 5
    assert smile.atm_vol > 0.0
    # Negative rho creates downward-sloping skew at ATM (dvol / dK < 0)
    assert smile.skew_dvol_dk < 0.0
    # Positive vol-of-vol creates convex smile (curvature > 0)
    assert smile.curvature > 0.0

    # Pricing & Greeks for ATM option
    pricing = engine.price_option(strike=100.0, discount_factor=0.95)
    assert pricing.call_price > 0.0
    assert pricing.put_price > 0.0
    assert pricing.vega > 0.0
    # Call-Put Parity on forward: Call - Put = DF * (F - K) = 0 for ATM
    parity_diff = pricing.call_price - pricing.put_price
    assert abs(parity_diff) < 1e-6


def test_sabr_market_calibration():
    """Calibrates SABR model to a synthetic market volatility smile."""
    f = 100.0
    expiry = 1.0
    strikes = [80.0, 85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 115.0, 120.0]
    true_alpha = 2.5
    true_beta = 0.5
    true_rho = -0.3
    true_nu = 0.4

    # Generate synthetic market vols
    market_vols = [
        sabr_implied_volatility(f, k, expiry, true_alpha, true_beta, true_rho, true_nu)
        for k in strikes
    ]

    # Run calibration fixing beta = 0.5
    calibrated_engine, calib_res = SABREngine.calibrate(
        forward=f,
        expiry=expiry,
        strikes=strikes,
        market_vols=market_vols,
        beta=0.5,
        fix_beta=True,
        initial_rho=-0.1,
    )

    assert calib_res.converged is True
    assert calib_res.rmse < 0.01
    assert calib_res.r_squared > 0.75
    assert abs(calibrated_engine.params.alpha - true_alpha) < 0.35
    assert abs(calibrated_engine.params.nu - true_nu) < 0.25


# ==============================================================================
# 2. FACTOR INVESTING & CORPORATE FINANCE TESTS
# ==============================================================================

def test_tsmom_backtest_and_crisis_alpha():
    """Verifies Moskowitz et al. (2012) TSMOM execution and Crisis Alpha extraction."""
    np.random.seed(42)
    # Simulate 36 months of asset returns and benchmark returns
    asset_ret = [0.02] * 12 + [-0.04] * 6 + [0.03] * 18
    # Benchmark with a steep crash in months 12-18
    bench_ret = [0.01] * 12 + [-0.08] * 6 + [0.02] * 18

    cfg = TSMOMConfig(
        target_volatility=0.15,
        lookback_periods=6,
        vol_lookback_periods=6,
        periods_per_year=12,
        max_leverage=2.0,
    )

    result = compute_tsmom_backtest(asset_ret, bench_ret, cfg)

    assert len(result.strategy_returns) == 30
    assert len(result.positions) == 30
    # Leverage must stay bounded by max_leverage
    for pos in result.positions:
        assert abs(pos) <= cfg.max_leverage + 1e-6

    assert result.crisis_alpha is not None
    assert 0.0 <= result.crisis_alpha.crisis_alpha_score <= 100.0


def test_share_buyback_accretive_vs_dilutive():
    """
    Verifies the Earnings Yield vs After-Tax Debt Cost decision rule:
    - E/P > Kd*(1-t) -> Accretive
    - E/P < Kd*(1-t) -> Dilutive
    """
    # 1. Accretive Case: P/E = 10 -> Earnings Yield = 10%. Debt cost Kd = 5%, t = 20% -> Kd*(1-t) = 4%
    accretive_input = BuybackInput(
        share_price=50.0,
        shares_outstanding=10_000_000,
        net_income=50_000_000,  # EPS = 5.0, P/E = 10, E/P = 0.10 (10%)
        buyback_amount=50_000_000,
        cost_of_debt=0.05,
        effective_tax_rate=0.20,
        financing_method=BuybackFinancingMethod.DEBT_FINANCED,
    )
    acc_res = evaluate_share_buyback(accretive_input)
    assert acc_res.is_accretive is True
    assert acc_res.pro_forma_eps > acc_res.baseline_eps
    assert acc_res.eps_change_pct > 0.0

    # 2. Dilutive Case: P/E = 40 -> Earnings Yield = 2.5%. Debt cost Kd = 6%, t = 20% -> Kd*(1-t) = 4.8%
    dilutive_input = BuybackInput(
        share_price=200.0,
        shares_outstanding=10_000_000,
        net_income=50_000_000,  # EPS = 5.0, P/E = 40, E/P = 0.025 (2.5%)
        buyback_amount=50_000_000,
        cost_of_debt=0.06,
        effective_tax_rate=0.20,
        financing_method=BuybackFinancingMethod.DEBT_FINANCED,
    )
    dil_res = evaluate_share_buyback(dilutive_input)
    assert dil_res.is_accretive is False
    assert dil_res.pro_forma_eps < dil_res.baseline_eps
    assert dil_res.eps_change_pct < 0.0

    # Verify sensitivity matrix is populated
    assert len(acc_res.sensitivity_grid) == 15


def test_ifrs16_operating_lease_capitalization():
    """
    Verifies present value capitalization of operating lease liability,
    artificial EBITDA expansion, and leverage expansion turn.
    """
    lease_input = IFRS16LeaseInput(
        annual_lease_payments=[20.0, 20.0, 20.0, 20.0, 20.0],  # 5-year lease of 20M/yr
        incremental_borrowing_rate=0.06,  # 6% IBR
        pre_ifrs_ebitda=100.0,
        pre_ifrs_ebit=70.0,
        pre_ifrs_gross_debt=150.0,
        cash_and_equivalents=30.0,  # Net debt = 120.0
    )

    result = capitalize_operating_leases(lease_input)

    # PV of 5-year annuity of 20 at 6% = 20 * (1 - 1.06^-5)/0.06 ~ 84.247M
    expected_pv = sum(20.0 / (1.06 ** t) for t in range(1, 6))
    assert abs(result.present_value_lease_liability - expected_pv) < 1e-4

    # EBITDA inflation delta must equal annual rent expense (+20M)
    assert result.ebitda_inflation_delta == 20.0
    assert result.post_ebitda == 120.0

    # Net debt must expand by PV of lease liability
    assert abs(result.post_net_debt - (120.0 + expected_pv)) < 1e-4

    # Leverage must expand
    assert result.post_leverage_ratio > result.pre_leverage_ratio
    assert result.leverage_expansion_turn > 0.0

    # Amortization schedule integrity: ending liability at year 5 must reach 0
    assert len(result.amortization_schedule) == 5
    assert abs(result.amortization_schedule[-1].ending_liability) < 1e-3


# ==============================================================================
# 3. FED MACRO PLUMBING & COMMODITY PHYSICS TESTS
# ==============================================================================

def test_fed_net_liquidity_and_lclor():
    """
    Tests Fed Net Liquidity plumbing equation:
    Net Liq = WALCL - TGA - ON_RRP
    and verifies LCLoR reserve stress transitions.
    """
    # 1. Abundant liquidity scenario (GREEN_SURPLUS)
    fed_abundant = FedBalanceSheetInput(
        walcl_total_assets=8000.0,
        tga_treasury_account=400.0,
        on_rrp_reverse_repo=500.0,
        currency_in_circulation=2300.0,
        other_liabilities_capital=200.0,
        lclor_reserve_threshold=3000.0,
    )
    res_abundant = evaluate_fed_net_liquidity(fed_abundant)
    assert res_abundant.net_liquidity == 8000.0 - 400.0 - 500.0  # 7100.0
    assert res_abundant.estimated_bank_reserves == 7100.0 - 2300.0 - 200.0  # 4600.0
    assert res_abundant.stress_level == LCLoRStressLevel.GREEN_SURPLUS
    assert res_abundant.reserve_buffer_ratio > 1.20

    # 2. Critical reserve deficit scenario (RED_CRITICAL - Sub-LCLoR)
    fed_stressed = FedBalanceSheetInput(
        walcl_total_assets=6000.0,
        tga_treasury_account=800.0,
        on_rrp_reverse_repo=600.0,
        currency_in_circulation=2400.0,
        other_liabilities_capital=200.0,
        lclor_reserve_threshold=3000.0,
    )
    res_stressed = evaluate_fed_net_liquidity(fed_stressed)
    # Net Liq = 6000 - 800 - 600 = 4600. Reserves = 4600 - 2400 - 200 = 2000 (< 3000 LCLoR)
    assert res_stressed.estimated_bank_reserves == 2000.0
    assert res_stressed.stress_level == LCLoRStressLevel.RED_CRITICAL
    assert res_stressed.projected_sofr_iorb_spread_bps > 15.0


def test_commodity_stocks_to_use_hyperbolic_pricing():
    """
    Tests non-linear scarcity multiplier when STU drops near critical buffer.
    """
    # Normal / Surplus market
    normal_input = CommoditySuperCycleInput(
        commodity_name="Copper",
        baseline_price=9000.0,
        ending_stocks=5.0,
        annual_consumption=20.0,  # STU = 0.25 (Normal)
        stu_normal=0.25,
        stu_critical_min=0.10,
    )
    normal_res = evaluate_commodity_scarcity(normal_input)
    assert normal_res.regime in [CommodityRegime.BALANCED, CommodityRegime.GLUT_SURPLUS]
    assert abs(normal_res.model_equilibrium_price - 9000.0) < 50.0

    # Acute scarcity / Super-cycle spike
    spike_input = CommoditySuperCycleInput(
        commodity_name="Copper",
        baseline_price=9000.0,
        ending_stocks=2.2,
        annual_consumption=20.0,  # STU = 0.11 (Approaching 0.10 critical)
        stu_normal=0.25,
        stu_critical_min=0.10,
        elasticity_exponent=1.8,
    )
    spike_res = evaluate_commodity_scarcity(spike_input)
    assert spike_res.regime == CommodityRegime.SUPER_CYCLE_SPIKE
    assert spike_res.model_equilibrium_price > 9000.0 * 2.0  # Massive scarcity premium
    assert spike_res.super_cycle_risk_score > 90.0


def test_negative_oil_price_cushing_storage_squeeze():
    """
    Simulates April 20, 2020 WTI negative price collapse where Cushing capacity
    saturation triggers catastrophic storage penalties exceeding physical value.
    """
    # 1. Normal Cushing operation
    normal_cushing = CushingStorageInput(
        current_storage_million_bbl=45.0,
        max_storage_capacity_million_bbl=76.0,  # ~59% utilization
        unloaded_physical_spot_price=25.0,
    )
    norm_res = evaluate_negative_oil_dynamics(normal_cushing)
    assert norm_res.is_price_negative is False
    assert norm_res.regime == OilDeliveryRegime.NORMAL_CONTANGO
    assert norm_res.implied_settlement_price > 0.0

    # 2. Severe 2020 Squeeze (Tank top 75.5 / 76.0 M bbl ~ 99.3% full)
    crisis_cushing = CushingStorageInput(
        current_storage_million_bbl=75.5,
        max_storage_capacity_million_bbl=76.0,
        net_inflow_million_bbl_per_day=0.5,
        unloaded_physical_spot_price=10.0,
        distress_liquidation_discount=25.0,
        base_storage_rental_rate=1.0,
        congestion_alpha=1.5,
    )
    crisis_res = evaluate_negative_oil_dynamics(crisis_cushing)
    assert crisis_res.capacity_utilization > 0.99
    assert crisis_res.is_price_negative is True
    assert crisis_res.regime == OilDeliveryRegime.NEGATIVE_PRICE_COLLAPSE
    assert crisis_res.implied_settlement_price < 0.0  # Confirmed negative settlement!
    assert crisis_res.days_to_tank_top_exhaustion is not None
    assert crisis_res.days_to_tank_top_exhaustion < 2.0  # Tanks fill completely in < 2 days
