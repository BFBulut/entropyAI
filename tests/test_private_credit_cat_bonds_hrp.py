"""Automated pytest test suite for Private Credit, Cat Bonds, LMT Distressed Maneuvers, HRP & Dispersion Trading:
- Private Credit & Unitranche Lending (SOFR + Spread, OID, PIK, Leverage/FCCR Covenants & Equity Cure)
- Catastrophe Bonds & Insurance-Linked Securities (ILS, Parametric vs Indemnity, Expected Loss, Spread Multiple)
- Liability Management Transactions (LMT / Creditor-on-Creditor Violence, J.Crew Dropdown & Serta Uptiering)
- Hierarchical Risk Parity (HRP / Lopez de Prado Machine Learning Portfolio Allocation)
- Correlation Swaps & Dispersion Trading Arbitrage (Implied vs Realized Correlation, Vega-Neutral Basket)
"""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from private_credit_cat_bonds_hrp import (
    calculate_private_credit_and_unitranche,
    calculate_cat_bond_and_ils,
    calculate_lmt_dropdown_uptiering,
    calculate_hierarchical_risk_parity,
    calculate_dispersion_and_correlation_swap
)


def test_private_credit_and_unitranche():
    # 1. Safe corridor scenario
    res = calculate_private_credit_and_unitranche(
        sofr_pct=5.25,
        margin_spread_bps=650.0,
        oid_pct=2.0,
        pik_spread_bps=150.0,
        total_debt=100000000.0,
        ebitda=20000000.0,
        interest_expense=11750000.0,
        capex=2000000.0,
        tax_expense=1500000.0,
        tenor_years=5.0,
        covenant_max_leverage=6.0,
        covenant_min_fccr=1.20,
        first_out_ratio_pct=50.0,
        first_out_spread_bps=400.0,
        last_out_spread_bps=800.0
    )
    assert res["cash_coupon_pct"] == 11.75
    assert res["total_nominal_coupon_pct"] == 13.25
    assert res["all_in_effective_yield_pct"] == 13.65
    assert res["current_leverage_ratio"] == 5.0
    assert res["leverage_cushion_turns"] == 1.0
    assert res["current_fccr"] == 1.4
    assert res["equity_cure_required"] == 0.0
    assert "GÜVENLİ" in res["covenant_status_diagnosis"].upper()

    # 2. Leverage breach & Equity Cure required
    res_breach = calculate_private_credit_and_unitranche(
        sofr_pct=5.0,
        margin_spread_bps=600.0,
        oid_pct=2.0,
        pik_spread_bps=0.0,
        total_debt=140000000.0,
        ebitda=20000000.0,  # Leverage = 7.0x > 6.0x
        interest_expense=15400000.0,
        capex=4000000.0,
        tax_expense=2000000.0,
        covenant_max_leverage=6.0,
        covenant_min_fccr=1.20
    )
    assert res_breach["current_leverage_ratio"] == 7.0
    # Required Equity Cure = 140M - (6.0 * 20M) = 20M
    assert res_breach["equity_cure_required"] == 20000000.0
    assert "İHLAL" in res_breach["covenant_status_diagnosis"].upper()

    # 3. Error handling
    err = calculate_private_credit_and_unitranche(5.0, 600.0, 2.0, 0.0, -100.0, 20.0, 10.0)
    assert "error" in err


def test_cat_bond_and_ils():
    # Hard market Cat Bond: Spread = 850 bps (8.5%), EL = 2.25%, Multiple = 3.78x
    res = calculate_cat_bond_and_ils(
        collateral_principal=100000000.0,
        spread_bps=850.0,
        expected_loss_pct=2.25,
        attachment_prob_pct=3.20,
        exhaustion_prob_pct=1.10,
        trigger_type="parametric",
        collateral_yield_pct=4.50
    )
    assert res["reinsurance_spread_pct"] == 8.50
    assert res["total_cat_bond_yield_pct"] == 13.00
    assert res["net_expected_return_pct"] == 10.75
    assert res["spread_multiple"] == 3.78
    assert res["trigger_profile"]["moral_hazard"] == "Sıfır"
    assert "SERT PİYASA" in res["pricing_regime_diagnosis"].upper()
    assert res["beta_to_equity_market"] == 0.02

    # Indemnity trigger test
    res_ind = calculate_cat_bond_and_ils(
        collateral_principal=50000000.0,
        spread_bps=400.0,
        expected_loss_pct=2.0,
        attachment_prob_pct=2.5,
        exhaustion_prob_pct=0.8,
        trigger_type="indemnity"
    )
    assert res_ind["spread_multiple"] == 2.0
    assert "YUMUŞAK" in res_ind["pricing_regime_diagnosis"].upper()
    assert res_ind["trigger_profile"]["basis_risk"] == "Sıfır (Birebir şirketin nihai bilançodaki net hasarına bağlı)"

    # Error handling
    err = calculate_cat_bond_and_ils(-100.0, 500.0, 2.0, 3.0, 1.0)
    assert "error" in err


def test_lmt_dropdown_uptiering():
    # 1. J.Crew style Dropdown
    res_drop = calculate_lmt_dropdown_uptiering(
        existing_debt=500000000.0,
        collateral_value=600000000.0,
        dropdown_asset_value=250000000.0,
        new_priming_debt=200000000.0,
        minority_debt=200000000.0,
        majority_debt=300000000.0,
        distressed_ev=350000000.0,
        transaction_type="dropdown"
    )
    assert res_drop["transaction_type"] == "DROPDOWN"
    assert res_drop["baseline_recovery_rate_pct"] == 70.0
    assert res_drop["minority_lender_recovery_rate_pct"] == 30.0
    assert res_drop["minority_creditor_haircut_loss_pct"] == 40.0
    assert "J.Crew" in res_drop["legal_and_covenant_vulnerability"]

    # 2. Serta style Uptiering
    res_uptier = calculate_lmt_dropdown_uptiering(
        existing_debt=500000000.0,
        collateral_value=600000000.0,
        dropdown_asset_value=0.0,
        new_priming_debt=200000000.0,
        minority_debt=200000000.0,
        majority_debt=300000000.0,
        distressed_ev=350000000.0,
        transaction_type="uptiering"
    )
    assert res_uptier["transaction_type"] == "UPTIERING"
    # Super-Senior = 200M new + 300M majority = 500M. Available EV = 350M.
    # Majority recovery = 350 / 500 = 70.0%. Minority receives 0.0%!
    assert res_uptier["majority_lender_recovery_rate_pct"] == 70.0
    assert res_uptier["minority_lender_recovery_rate_pct"] == 0.0
    assert res_uptier["minority_creditor_haircut_loss_pct"] == 70.0
    assert "Serta" in res_uptier["legal_and_covenant_vulnerability"]

    # Error handling
    err = calculate_lmt_dropdown_uptiering(-500.0, 600.0, 100.0, 200.0, 100.0, 100.0, 300.0)
    assert "error" in err


def test_hierarchical_risk_parity():
    assets = ["SPY", "TLT", "GLD", "VNQ"]
    vols = [16.0, 14.0, 15.0, 20.0]
    corr_matrix = [
        [1.0, -0.3, 0.1, 0.7],
        [-0.3, 1.0, 0.2, -0.2],
        [0.1, 0.2, 1.0, 0.1],
        [0.7, -0.2, 0.1, 1.0]
    ]
    res = calculate_hierarchical_risk_parity(assets, vols, corr_matrix)
    assert res["asset_count"] == 4
    assert len(res["quasi_diagonalized_order"]) == 4
    # Weights should sum to 100%
    assert 99.0 <= sum(res["hrp_weights_pct"].values()) <= 101.0
    assert "TEKİLLİK" in res["markowitz_condition_status"].upper()

    # Dimension mismatch error
    err = calculate_hierarchical_risk_parity(["SPY"], [15.0], [[1.0]])
    assert "error" in err


def test_dispersion_and_correlation_swap():
    # Index IV = 18%, Components IVs ~ 28%, Realized Corr = 0.30, Strike = 0.50
    res = calculate_dispersion_and_correlation_swap(
        index_implied_vol_pct=18.0,
        component_vols_pct=[28.0, 32.0, 24.0, 30.0, 26.0],
        component_weights=[0.25, 0.20, 0.20, 0.20, 0.15],
        realized_correlation=0.30,
        index_vega_notional=100000.0,
        correlation_strike=0.50
    )
    assert res["index_implied_vol_pct"] == 18.0
    assert 0.0 <= res["implied_correlation"] <= 1.0
    # Correlation Swap payoff: 100000 * (0.30 - 0.50) = -20000.0
    assert res["correlation_swap_payoff"] == -20000.0
    assert "dispersion_regime_diagnosis" in res

    # Long dispersion scenario where implied corr > realized corr
    res_high = calculate_dispersion_and_correlation_swap(
        index_implied_vol_pct=26.0,
        component_vols_pct=[28.0, 30.0, 27.0, 29.0],
        component_weights=[0.25, 0.25, 0.25, 0.25],
        realized_correlation=0.20,
        index_vega_notional=100000.0,
        correlation_strike=0.40
    )
    assert res_high["correlation_risk_premium"] > 0
    assert "DAĞILIM" in res_high["dispersion_regime_diagnosis"].upper()

    # Error handling
    err = calculate_dispersion_and_correlation_swap(-18.0, [25.0], [1.0], 0.3)
    assert "error" in err
