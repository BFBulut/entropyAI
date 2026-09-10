"""Automated pytest suite for Stochastic Rates, Credit Portfolio Copula,
Deep Hedging / Fractional Differentiation & Forensic Reverse Factoring."""

import subprocess
import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from stochastic_credit_hedging_forensic import (
    calculate_hull_white_swaption_lsm,
    calculate_credit_portfolio_copula_cdo,
    calculate_deep_hedging_and_fractional_differentiation,
    calculate_forensic_reverse_factoring_spv,
    calculate_isda_restructuring_ctd,
)


def test_hull_white_swaption_lsm_valid():
    res = calculate_hull_white_swaption_lsm(
        notional=10000000.0,
        strike_rate=0.035,
        tenor_years=5.0,
        exercise_years=[1.0, 2.0, 3.0, 4.0],
        mean_reversion_a=0.05,
        volatility_sigma=0.012,
        initial_short_rate=0.035,
        n_simulations=500,
        seed=101
    )
    assert "error" not in res
    assert res["bermudan_swaption_price"] >= 0.0
    assert res["european_swaption_price"] >= 0.0
    # Bermudan option price must be greater than or equal to European option price
    assert res["bermudan_swaption_price"] >= res["european_swaption_price"] - 1.0
    assert res["early_exercise_premium"] >= 0.0
    assert 0.0 <= res["early_exercise_probability_pct"] <= 100.0
    assert "model_verdict" in res


def test_hull_white_swaption_invalid_inputs():
    err1 = calculate_hull_white_swaption_lsm(
        notional=-1000.0,
        strike_rate=0.04,
        tenor_years=5.0,
        exercise_years=[1.0],
        mean_reversion_a=0.05,
        volatility_sigma=0.01,
        initial_short_rate=0.03
    )
    assert "error" in err1

    err2 = calculate_hull_white_swaption_lsm(
        notional=1000.0,
        strike_rate=1.5,
        tenor_years=5.0,
        exercise_years=[1.0],
        mean_reversion_a=0.05,
        volatility_sigma=0.01,
        initial_short_rate=0.03
    )
    assert "error" in err2


def test_credit_portfolio_copula_cdo_gaussian_vs_student_t():
    # Gaussian copula
    res_gauss = calculate_credit_portfolio_copula_cdo(
        n_issuers=50,
        notional_per_issuer=1000000.0,
        default_probability=0.04,
        lgd_rate=0.60,
        asset_correlation=0.30,
        copula_type="gaussian",
        n_simulations=800,
        seed=42
    )
    assert "error" not in res_gauss
    assert res_gauss["expected_portfolio_loss_pct"] > 0.0
    assert len(res_gauss["tranche_breakdown"]) == 4

    # Student-t copula with heavy tails (df=3.0)
    res_t = calculate_credit_portfolio_copula_cdo(
        n_issuers=50,
        notional_per_issuer=1000000.0,
        default_probability=0.04,
        lgd_rate=0.60,
        asset_correlation=0.30,
        copula_type="student-t",
        t_copula_df=3.0,
        n_simulations=800,
        seed=42
    )
    assert "error" not in res_t
    # Student-t copula tail risk (CVaR 99%) should be high due to tail clustering
    assert res_t["portfolio_cvar_99_pct"] > 0.0


def test_fractional_differentiation_and_metalabeling():
    prices = [
        100.0, 101.5, 102.2, 101.8, 103.5, 104.2, 103.8, 105.0,
        106.5, 105.8, 107.2, 108.0, 107.5, 109.1, 110.0, 111.5
    ]
    res = calculate_deep_hedging_and_fractional_differentiation(
        prices=prices,
        d_order=0.40,
        transaction_cost_bps=5.0
    )
    assert "error" not in res
    assert res["fractional_order_d"] == 0.40
    # Memory correlation should be strongly preserved
    assert res["memory_correlation_retained"] > 0.50
    assert "metalabeling_summary" in res
    assert "hedging_verdict" in res


def test_forensic_reverse_factoring_spv():
    # Severe manipulation scenario (Carillion/Greensill model)
    res = calculate_forensic_reverse_factoring_spv(
        revenue=5000.0,
        cogs=3800.0,
        reported_cfo=450.0,
        capex=200.0,
        short_term_debt=300.0,
        long_term_debt=700.0,
        cash_and_equiv=150.0,
        reported_ebitda=600.0,
        accounts_receivable=800.0,
        inventory=400.0,
        accounts_payable=1200.0,
        reverse_factoring_hidden_payable=600.0,  # 50% of AP is bank debt!
        off_balance_sheet_spv_debt=400.0,        # SPV debt
        unbilled_receivables=250.0,              # >30% unbilled
        doubtful_debt_allowance=20.0,
        prior_doubtful_debt_allowance=60.0       # Cookie jar release
    )
    assert "error" not in res
    # True adjusted CFO is negative (450 - 600 = -150)
    assert res["forensic_adjusted_metrics"]["adjusted_cfo"] == -150.0
    assert res["forensic_adjusted_metrics"]["adjusted_fcf"] == -350.0
    # Adjusted leverage is significantly higher
    assert res["forensic_adjusted_metrics"]["adjusted_net_debt_to_ebitda"] > res["reported_metrics"]["net_debt_to_ebitda"]
    assert res["forensic_indicators"]["risk_score"] >= 3
    assert "Carillion / Greensill" in res["forensic_indicators"]["forensic_verdict"]


def test_isda_restructuring_and_ctd():
    mock_bonds = [
        {"isin": "US001", "coupon_pct": 5.0, "maturity_years": 3.0, "market_price": 55.0},
        {"isin": "US002", "coupon_pct": 3.0, "maturity_years": 8.0, "market_price": 38.0},  # CTD bond
        {"isin": "US003", "coupon_pct": 6.5, "maturity_years": 10.0, "market_price": 62.0}
    ]
    res = calculate_isda_restructuring_ctd(
        cds_spread_bps=420.0,
        notional=10000000.0,
        deliverable_bonds=mock_bonds,
        is_manufactured_default=False
    )
    assert "error" not in res
    assert res["credit_event_recognized"] is True
    assert res["cheapest_to_deliver_bond"]["isin"] == "US002"
    assert res["cheapest_to_deliver_bond"]["market_price"] == 38.0
    assert res["net_cds_payout"] == 6200000.0  # (100 - 38)% * 10M = 6.2M

    # Manufactured default rejection under ISDA 2019 NTCE rule
    res_mfg = calculate_isda_restructuring_ctd(
        cds_spread_bps=420.0,
        notional=10000000.0,
        deliverable_bonds=mock_bonds,
        is_manufactured_default=True
    )
    assert res_mfg["credit_event_recognized"] is False
    assert res_mfg["net_cds_payout"] == 0.0


def test_cli_execution():
    script_path = Path("skills/financial-auditor/scripts/stochastic_credit_hedging_forensic.py")
    cmd = [
        sys.executable,
        str(script_path),
        "isda-ctd",
        "--spread", "300.0",
        "--notional", "5000000.0"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert proc.returncode == 0
    assert "cheapest_to_deliver_bond" in proc.stdout
