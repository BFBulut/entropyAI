#!/usr/bin/env python3
"""Automated Test Suite for Corporate Earnings Announcement Reaction Simulator.
Verifies all 5 market reaction regimes, SUE surprise dynamics, priced-in penalties,
and cash flow quality multipliers.
"""

import pytest
from scripts.earnings_reaction_simulator import (
    EarningsReportInput,
    calculate_earnings_reaction,
)


def test_super_beat_bullish_rally():
    """Validates strong positive earnings beat leading to post-announcement rally (PEAD)."""
    report = EarningsReportInput(
        symbol="GROWTH_CO",
        consensus_net_profit=1000.0,
        actual_net_profit=1400.0,  # +40%
        consensus_revenue=5000.0,
        actual_revenue=5600.0,      # +12%
        pre_earnings_runup_pct=4.0, # Not overextended
        guidance_revision_pct=10.0, # Upward guidance
        cfo_to_net_income_ratio=1.2,# High quality earnings
    )
    result = calculate_earnings_reaction(report)

    assert result["profit_surprise_pct"] == 40.0
    assert result["revenue_surprise_pct"] == 12.0
    assert result["is_strong_bullish"] is True
    assert result["composite_score"] >= 35.0
    assert "GÜÇLÜ YÜKSELİŞ" in result["reaction_category"]
    assert result["quality_verdict"].startswith("YÜKSEK")


def test_sell_the_news_priced_in():
    """Validates 'Beklenti alındı, gerçek satıldı' when strong runup precedes an in-line report."""
    report = EarningsReportInput(
        symbol="RUMOR_RUNNER",
        consensus_net_profit=1000.0,
        actual_net_profit=1030.0,  # +3% mild beat
        consensus_revenue=4000.0,
        actual_revenue=4020.0,     # +0.5%
        pre_earnings_runup_pct=35.0, # Already surged +35%
        guidance_revision_pct=0.0,
        cfo_to_net_income_ratio=0.8,
    )
    result = calculate_earnings_reaction(report)

    assert result["is_sell_the_news"] is True
    assert "BEKLENTİ ALINDI GERÇEK SATILDI" in result["reaction_category"]
    assert result["composite_score"] < 10.0


def test_bearish_shock_on_miss_and_guidance_cut():
    """Validates sharp drop when both quarterly numbers miss and guidance is downgraded."""
    report = EarningsReportInput(
        symbol="TROUBLED_CORP",
        consensus_net_profit=1000.0,
        actual_net_profit=600.0,   # -40% miss
        consensus_revenue=5000.0,
        actual_revenue=4200.0,     # -16% miss
        pre_earnings_runup_pct=5.0,
        guidance_revision_pct=-15.0, # Cut full-year forecast
        cfo_to_net_income_ratio=0.6,
    )
    result = calculate_earnings_reaction(report)

    assert result["is_bearish_shock"] is True
    assert result["composite_score"] <= -35.0
    assert "SERT SATIŞ" in result["reaction_category"]


def test_quality_of_earnings_cashflow_penalty():
    """Tests that low operating cash flow (accrual anomaly) penalizes the surprise score."""
    high_cash_report = EarningsReportInput(
        symbol="REAL_CASH",
        consensus_net_profit=1000.0,
        actual_net_profit=1200.0,
        consensus_revenue=5000.0,
        actual_revenue=5000.0,
        pre_earnings_runup_pct=0.0,
        guidance_revision_pct=0.0,
        cfo_to_net_income_ratio=1.1, # High cash
    )
    paper_gain_report = EarningsReportInput(
        symbol="PAPER_PROFIT",
        consensus_net_profit=1000.0,
        actual_net_profit=1200.0,
        consensus_revenue=5000.0,
        actual_revenue=5000.0,
        pre_earnings_runup_pct=0.0,
        guidance_revision_pct=0.0,
        cfo_to_net_income_ratio=0.1, # Fake/Paper gains
    )
    res_high = calculate_earnings_reaction(high_cash_report)
    res_paper = calculate_earnings_reaction(paper_gain_report)

    assert res_high["composite_score"] > res_paper["composite_score"]
    assert "ÇOK RİSKLİ" in res_paper["quality_verdict"]


def test_relief_rally_when_oversold():
    """Validates that a heavily sold-off stock can stage a relief rally on in-line results."""
    report = EarningsReportInput(
        symbol="OVERSOLD_BEATEN",
        consensus_net_profit=1000.0,
        actual_net_profit=1020.0,  # Just in line (+2%)
        consensus_revenue=4000.0,
        actual_revenue=4000.0,
        pre_earnings_runup_pct=-25.0, # Dumped -25% prior to earnings
        guidance_revision_pct=2.0,
        cfo_to_net_income_ratio=0.9,
    )
    result = calculate_earnings_reaction(report)

    # Because it was dumped, runup_penalty is positive (+15) -> Relief rally
    assert result["composite_score"] > 10.0
    assert "ILIMLI POZİTİF" in result["reaction_category"]


def test_invalid_revenue_raises_error():
    """Ensures non-positive revenue parameters trigger ValueError."""
    with pytest.raises(ValueError, match="Revenue figures must be positive"):
        calculate_earnings_reaction(
            EarningsReportInput(
                symbol="ERR",
                consensus_net_profit=100.0,
                actual_net_profit=100.0,
                consensus_revenue=-500.0,
                actual_revenue=500.0,
                pre_earnings_runup_pct=0.0,
                guidance_revision_pct=0.0,
                cfo_to_net_income_ratio=1.0,
            )
        )
