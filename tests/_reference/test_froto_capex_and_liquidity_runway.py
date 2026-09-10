"""Automated test suite for FROTO 3-month CapEx and Investment Outlook Engine."""

import sys
from pathlib import Path
import pytest

# Ensure scripts path is importable
scripts_dir = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(scripts_dir))

from froto_capex_and_liquidity_runway import evaluate_3month_investment_outlook


def test_froto_3month_investment_outlook_verdict():
    data = evaluate_3month_investment_outlook()

    assert data["analysis_target"] == "Ford Otomotiv Sanayi A.Ş. (FROTO)"
    assert "3 Ay" in data["horizon"]

    # CapEx cycle: Peak CapEx occurred in 2023 (~7.8% intensity) and has tapered off to ~2.3%
    cycle = data["capex_cycle"]
    assert cycle["peak_capex_year"] == 2023
    assert cycle["peak_capex_intensity_pct"] > 7.0
    assert cycle["current_capex_intensity_pct"] < 3.0
    assert cycle["q2_26_fcf_try_m"] < 0

    # Solvency constraints: Interest coverage is 1.0x, S&P BB-
    solvency = data["solvency_and_debt"] if "solvency_and_debt" in data else data["solvency_constraints"]
    assert solvency["interest_coverage_ratio"] == 1.0
    assert solvency["credit_rating"] == "S&P BB-"
    assert solvency["total_debt_try_b"] == 169.78

    # Corporate CapEx verdict: NO expansion expected in 3 months
    corp = data["corporate_capex_verdict"]
    assert corp["capex_expansion_expected_3m"] is False
    assert "Nakit Koruma" in corp["corporate_posture"]

    # Equity investor flow verdict: NO momentum surge expected in next 3 months, wait-and-see
    equity = data["equity_investor_inflow_verdict"]
    assert equity["inflow_surge_expected_3m"] is False
    assert equity["q3_eps_revision_pct"] == -31.3
    assert equity["long_term_accumulation_attractive"] is True
