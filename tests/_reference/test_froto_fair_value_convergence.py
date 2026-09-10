"""Automated test suite for FROTO Fair Value Convergence Engine (Jan-Feb 2027 horizon)."""

import sys
from pathlib import Path
import pytest

# Ensure scripts path is importable
scripts_dir = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(scripts_dir))

from froto_fair_value_convergence import evaluate_fair_value_convergence


def test_froto_fair_value_convergence_by_jan_feb_2027():
    data = evaluate_fair_value_convergence()

    assert data["ticker"] == "IS:FROTO"
    assert data["current_price_try"] == 76.20
    assert data["fair_value_anchor_try"] == 103.36
    assert "Ocak - Şubat 2027" in data["horizon"]

    # Catalysts
    catalysts = data["catalysts"]
    assert len(catalysts) == 4
    # Highest probability catalyst is the BIST dividend pricing rally (0.80)
    dividend_cat = [c for c in catalysts if "Temettü" in c["event"]][0]
    assert dividend_cat["bullish_probability"] >= 0.80

    # Scenarios
    scenarios = data["scenarios"]
    assert scenarios["base"]["probability"] == 0.55
    assert scenarios["base"]["target_price_try"] > 100.0
    assert scenarios["bear"]["probability"] == 0.20
    assert scenarios["bull"]["probability"] == 0.25

    # Synthesis & Expected Return
    synth = data["probabilistic_synthesis"]
    assert synth["expected_price_jan_feb_2027_try"] > 98.0  # Converges close to 103.36
    assert synth["convergence_ratio_to_fair_value_pct"] > 95.0
    assert synth["convergence_viable"] is True
    assert synth["expected_return_pct"] > 30.0
    # Forward FY27 P/E at fair value should be conservative (~8x)
    assert synth["pe_at_fair_value_fy27"] < 9.0
