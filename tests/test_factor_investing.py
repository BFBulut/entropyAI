"""
Automated Test Suite: Factor Investing, Buyback Accretion/Dilution & IFRS 16 Distortion.
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import pytest
import numpy as np

from src.entropy.agent_desk.analysis.factor_investing import (
    TSMOMParameters,
    TSMOMResult,
    TimeSeriesMomentumEngine,
    RepurchaseInputs,
    RepurchaseResult,
    ShareRepurchaseAnalyzer,
    IFRS16Inputs,
    IFRS16RestatementResult,
    IFRS16LeaseCapitalizer,
)


# ==============================================================================
# 1. TIME SERIES MOMENTUM (TSMOM) & CRISIS ALPHA TESTS
# ==============================================================================

def test_tsmom_trend_following_and_vol_scaling():
    """
    Verifies that TSMOM engine scales position by target volatility and follows trends.
    """
    # 36 months of data: 12 months up (+2% per month), 12 months down (-2%), 12 months up (+3%)
    returns = [0.02] * 12 + [-0.02] * 12 + [0.03] * 12
    engine = TimeSeriesMomentumEngine(TSMOMParameters(lookback_periods=12, target_volatility=0.15))
    res = engine.run_backtest(returns)

    assert isinstance(res, TSMOMResult)
    assert len(res.strategy_returns) == 24  # 36 - 12
    assert res.annualized_volatility > 0.0
    # Following the trend: during the second 12 months, signal was short (negative weight)
    # when market was dropping, yielding positive strategy return!
    assert res.annualized_return > 0.0


def test_tsmom_crisis_alpha_performance():
    """
    Verifies that TSMOM captures Crisis Alpha during market distress.
    """
    np.random.seed(42)
    # 60 periods: market normal with occasional severe drawdowns
    mkt_returns = list(np.random.normal(0.01, 0.04, 60))
    # Inject severe market crash in months 25-30
    for i in range(25, 30):
        mkt_returns[i] = -0.12

    engine = TimeSeriesMomentumEngine(TSMOMParameters(lookback_periods=6, target_volatility=0.15))
    res = engine.run_backtest(asset_returns=mkt_returns, benchmark_returns=mkt_returns)

    assert res.crisis_alpha != 0.0
    assert -1.0 <= res.max_drawdown <= 0.0
    assert len(res.weights_history) == 54


# ==============================================================================
# 2. SHARE REPURCHASE VALUE ACCRETION / DILUTION TESTS
# ==============================================================================

def test_share_repurchase_accretive_scenario():
    """
    Verifies that when Earnings Yield E/P exceeds after-tax cost of debt K_d*(1-t),
    the buyback is accretive (EPS increases).
    """
    # P0 = 50$, Shares = 10M, Net Income = 50M -> EPS = 5$, P/E = 10, E/P = 10%
    # Kd = 6%, Tax = 21% -> Kd*(1 - t) = 4.74%
    # Since 10% > 4.74%, EPS MUST increase!
    inputs = RepurchaseInputs(
        share_price=50.0,
        shares_outstanding=10_000_000,
        net_income=50_000_000,
        repurchase_amount=100_000_000,  # 2M shares
        cost_of_debt_pretax=0.06,
        tax_rate=0.21,
        is_debt_funded=True,
    )
    result = ShareRepurchaseAnalyzer.analyze(inputs)

    assert result.is_eps_accretive is True
    assert result.delta_eps_pct > 0.0
    assert result.post_eps > result.pre_eps
    assert result.shares_retired == 2_000_000
    assert result.post_shares_outstanding == 8_000_000
    assert result.hurdle_rate == pytest.approx(0.06 * (1.0 - 0.21), abs=1e-4)


def test_share_repurchase_dilutive_scenario():
    """
    Verifies that when E/P is lower than after-tax hurdle rate, the buyback is dilutive.
    """
    # P0 = 100$, Shares = 10M, Net Income = 25M -> EPS = 2.5$, P/E = 40, E/P = 2.5%
    # Kd = 8%, Tax = 25% -> Kd*(1 - t) = 6.0%
    # Since 2.5% < 6.0%, EPS MUST decrease!
    inputs = RepurchaseInputs(
        share_price=100.0,
        shares_outstanding=10_000_000,
        net_income=25_000_000,
        repurchase_amount=50_000_000,
        cost_of_debt_pretax=0.08,
        tax_rate=0.25,
        is_debt_funded=True,
    )
    result = ShareRepurchaseAnalyzer.analyze(inputs)

    assert result.is_eps_accretive is False
    assert result.delta_eps_pct < 0.0
    assert result.post_eps < result.pre_eps


def test_share_repurchase_accounting_illusion_buffett_mauboussin():
    """
    Verifies detection of 'Accounting Illusion':
    EPS is accretive, BUT buying shares above Intrinsic Value destroys real shareholder wealth!
    """
    # E/P = 8% > Kd*(1-t) = 4% (EPS accretive!)
    # But Share Price is 100$ while Intrinsic Value is 70$ (Overvalued by 43%)
    inputs = RepurchaseInputs(
        share_price=100.0,
        shares_outstanding=10_000_000,
        net_income=80_000_000,
        repurchase_amount=100_000_000,
        cost_of_debt_pretax=0.05,
        tax_rate=0.20,
        is_debt_funded=True,
        intrinsic_value_per_share=70.0,
    )
    result = ShareRepurchaseAnalyzer.analyze(inputs)

    assert result.is_eps_accretive is True
    assert result.is_value_creating is False  # Destroying economic value!
    assert "MUHASEBE YANILSAMASI" in result.value_verdict


# ==============================================================================
# 3. IFRS 16 LEASE CAPITALIZATION TESTS
# ==============================================================================

def test_ifrs16_lease_capitalization_and_leverage_distortion():
    """
    Verifies IFRS 16 Right-of-Use Asset & Liability capitalization,
    and documents artificial EBITDA expansion and leverage ratio jump.
    """
    # 5-year lease of 10M $ annually, IBR = 6%
    payments = [10_000_000.0] * 5
    ibr = 0.06
    pre_ebitda = 50_000_000.0
    pre_ebit = 35_000_000.0
    pre_net_debt = 100_000_000.0
    revenue = 200_000_000.0

    inputs = IFRS16Inputs(
        annual_lease_payments=payments,
        incremental_borrowing_rate=ibr,
        reported_ebitda_pre=pre_ebitda,
        reported_ebit_pre=pre_ebit,
        reported_net_debt_pre=pre_net_debt,
        revenue=revenue,
    )
    result = IFRS16LeaseCapitalizer.restate(inputs)

    # 1. PV check: sum 10M / 1.06^t for t=1..5 ~ 42.12M $
    expected_pv = sum(10_000_000.0 / (1.06 ** t) for t in range(1, 6))
    assert result.lease_liability_pv == pytest.approx(expected_pv, rel=1e-3)
    assert result.right_of_use_asset == result.lease_liability_pv

    # 2. EBITDA shift: OpEx lease eliminated -> EBITDA increases by 10M $
    assert result.delta_ebitda == 10_000_000.0
    assert result.ebitda_post == 60_000_000.0
    assert result.ebitda_margin_post_pct > result.ebitda_margin_pre_pct

    # 3. Net Debt increases by Lease Liability
    assert result.net_debt_post == pytest.approx(pre_net_debt + expected_pv, rel=1e-3)

    # 4. Leverage Ratio distortion: Pre was 100/50 = 2.0x, Post is ~142.12/60 = 2.37x
    assert result.leverage_pre == 2.0
    assert result.leverage_post > result.leverage_pre
    assert result.leverage_jump_pct > 0.0
