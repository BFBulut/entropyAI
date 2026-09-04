"""Automated pytest test suite for Advanced Execution, Credit Migration, PE Fund Economics, XVA & Macro Crises:
- Perold Implementation Shortfall & Square-Root Law of Market Impact
- Credit Rating Migration, Fallen Angel Surcharge & Loss Given Default (LGD / Basel EL)
- Private Equity Fund Performance (DPI, RVPI, TVPI, J-Curve & Kaplan-Schoar PME)
- XVA Derivative Pricing Adjustments (CVA, DVA, FVA, MVA, KVA)
- IMF Reserve Adequacy (ARA Metric, Sudden Stop & Crisis Vulnerability)
"""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from execution_pe_xva_crisis import (
    calculate_implementation_shortfall_and_impact,
    calculate_credit_migration_and_lgd,
    calculate_pe_fund_metrics_and_pme,
    calculate_xva_derivative_pricing,
    calculate_imf_reserve_adequacy
)


def test_implementation_shortfall_and_impact():
    # Decision: $100, Arrival: $100.20, Execution: $100.50, Final: $101.00
    # Target: 10,000 shares, Executed: 8,000 shares, Fees: $50
    res = calculate_implementation_shortfall_and_impact(
        decision_price=100.0,
        arrival_price=100.20,
        execution_price=100.50,
        final_price=101.00,
        executed_shares=8000.0,
        target_shares=10000.0,
        explicit_fees=50.0,
        daily_volatility=0.015,
        daily_volume=1000000.0
    )
    assert res["fill_rate_pct"] == 80.0
    assert res["delay_cost"] == 1600.0  # 8000 * 0.20
    assert res["realized_impact_cost"] == 2400.0  # 8000 * 0.30
    assert res["opportunity_cost"] == 2000.0  # 2000 * 1.00
    assert res["explicit_fees"] == 50.0
    assert res["total_implementation_shortfall"] == 6050.0  # 1600 + 2400 + 2000 + 50
    assert 60.0 <= res["shortfall_basis_points"] <= 61.0  # 6050 / 1,000,000 * 10,000 = 60.5 bps
    assert res["theoretical_square_root_impact_pct"] > 0
    assert "YÜKSEK İCRA KAYBI" in res["execution_diagnosis"]

    # Test error handling
    err1 = calculate_implementation_shortfall_and_impact(-100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 0.0, 0.01, 1000.0)
    assert "error" in err1
    err2 = calculate_implementation_shortfall_and_impact(100.0, 100.0, 100.0, 100.0, 120.0, 100.0, 0.0, 0.01, 1000.0)
    assert "error" in err2


def test_credit_migration_and_lgd():
    # EAD = $10M, current PD = 0.4% (BBB rating), recovery = 40% -> LGD = 60%
    # Stressed downgrade PD = 3.5% (BB - Fallen Angel), stress recovery = 30% -> stress LGD = 70%
    res = calculate_credit_migration_and_lgd(
        exposure_at_default=10000000.0,
        pd_current_pct=0.4,
        recovery_rate_pct=40.0,
        rating_downgrade_pd_pct=3.5,
        stress_recovery_rate_pct=30.0
    )
    assert res["base_lgd_pct"] == 60.0
    assert res["base_expected_loss"] == 24000.0  # 10M * 0.004 * 0.60
    assert res["stress_lgd_pct"] == 70.0
    assert res["downgrade_expected_loss"] == 245000.0  # 10M * 0.035 * 0.70
    assert res["loss_increase_multiple"] > 10.0
    assert "YÜKSEK" in res["fallen_angel_risk"]
    assert res["capital_cushion_required"] == 221000.0

    # Test error handling
    err = calculate_credit_migration_and_lgd(-100.0, 1.0, 40.0, 2.0, 30.0)
    assert "error" in err


def test_pe_fund_metrics_and_pme():
    # Early fund: PIC = 100M, Distributions = 5M, Remaining NAV = 85M
    res_early = calculate_pe_fund_metrics_and_pme(
        capital_called_pic=100.0,
        cumulative_distributions=5.0,
        remaining_nav=85.0
    )
    assert res_early["dpi"] == 0.05
    assert res_early["rvpi"] == 0.85
    assert res_early["tvpi"] == 0.90
    assert "J-EĞRİSİ ÇUKURU" in res_early["j_curve_stage"]

    # Mature fund with public benchmark PME
    res_mature = calculate_pe_fund_metrics_and_pme(
        capital_called_pic=100.0,
        cumulative_distributions=150.0,
        remaining_nav=50.0,
        benchmark_discounted_distributions_nav=225.0,
        benchmark_discounted_calls=180.0
    )
    assert res_mature["dpi"] == 1.50
    assert res_mature["rvpi"] == 0.50
    assert res_mature["tvpi"] == 2.00
    assert "HASAT & KÂR DAĞITIM" in res_mature["j_curve_stage"]
    assert res_mature["kaplan_schoar_pme"] == 1.25  # 225 / 180 = 1.25x
    assert "ALFA ÜRETİLDİ" in res_mature["pme_evaluation"]

    # Error handling
    err = calculate_pe_fund_metrics_and_pme(-100.0, 10.0, 50.0)
    assert "error" in err


def test_xva_derivative_pricing():
    # Unadjusted PV = 1,000,000
    # EE = 500,000, Counterparty PD = 2.0%, Recovery = 40% (CVA = 500k * 0.60 * 0.02 = 6,000)
    # ENE = 300,000, Own PD = 1.0%, Recovery = 40% (DVA = 300k * 0.60 * 0.01 = 1,800)
    # Funding spread = 1.0% (FVA = 500k * 0.01 = 5,000)
    # Initial Margin = 100,000, Cost of Margin = 2.0% (MVA = 100k * 0.02 = 2,000)
    # Regulatory Capital = 200,000, Hurdle = 10.0% (KVA = 200k * 0.10 = 20,000)
    res = calculate_xva_derivative_pricing(
        unadjusted_pv=1000000.0,
        expected_exposure_ee=500000.0,
        counterparty_pd_pct=2.0,
        counterparty_recovery_pct=40.0,
        expected_negative_exposure_ene=300000.0,
        own_pd_pct=1.0,
        own_recovery_pct=40.0,
        funding_spread_pct=1.0,
        initial_margin=100000.0,
        cost_of_margin_pct=2.0,
        regulatory_capital=200000.0,
        hurdle_rate_pct=10.0
    )
    assert res["cva_credit_risk"] == 6000.0
    assert res["dva_own_credit"] == 1800.0
    assert res["fva_funding_cost"] == 5000.0
    assert res["mva_margin_cost"] == 2000.0
    assert res["kva_capital_hurdle"] == 20000.0
    # Total XVA = -6000 + 1800 - 5000 - 2000 - 20000 = -31,200
    assert res["total_xva_adjustment"] == -31200.0
    assert res["adjusted_pv"] == 968800.0

    # Error handling
    err = calculate_xva_derivative_pricing(100.0, 50.0, -2.0, 40.0, 20.0, 1.0, 40.0)
    assert "error" in err


def test_imf_reserve_adequacy():
    # ST Debt = 100B, Other Portfolio = 50B, M2 = 200B, Exports = 150B
    # ARA = 0.30*100 + 0.15*50 + 0.05*200 + 0.05*150 = 30 + 7.5 + 10 + 7.5 = 55.0B
    # Reserves = 66B -> Coverage = 120% (Optimal)
    res_safe = calculate_imf_reserve_adequacy(
        actual_reserves_bn=66.0,
        short_term_external_debt_bn=100.0,
        other_portfolio_liabilities_bn=50.0,
        broad_money_m2_bn=200.0,
        annual_exports_bn=150.0
    )
    assert res_safe["imf_ara_metric_bn_usd"] == 55.0
    assert res_safe["reserve_coverage_ratio_pct"] == 120.0
    assert res_safe["reserve_surplus_deficit_bn_usd"] == 11.0
    assert "OPTIMAL VE GÜVENLİ" in res_safe["crisis_vulnerability_diagnosis"]

    # Critical depletion: Reserves = 33B -> Coverage = 60%
    res_critical = calculate_imf_reserve_adequacy(
        actual_reserves_bn=33.0,
        short_term_external_debt_bn=100.0,
        other_portfolio_liabilities_bn=50.0,
        broad_money_m2_bn=200.0,
        annual_exports_bn=150.0
    )
    assert res_critical["reserve_coverage_ratio_pct"] == 60.0
    assert "KRİTİK REZERV YETERSİZLİĞİ" in res_critical["crisis_vulnerability_diagnosis"]

    # Error handling
    err = calculate_imf_reserve_adequacy(50.0, -100.0, 50.0, 200.0, 150.0)
    assert "error" in err
