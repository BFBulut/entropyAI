"""
Faz 47 Financial Auditor Integration Engine:
1. Vladimir Piterbarg (2010) Multi-Currency Collateralized Discounting & Cheapest-to-Deliver (CTD) Collateral Option
2. Robert Goldstein, Nengjiu Ju & Hayne Leland (GJL 2001) Dynamic EBIT-Based Capital Structure & Endogenous Default Barrier
3. Albert S. Kyle (1985) & Kerry Back (1992) Continuous-Time Monopolistic Informed Trading & Information Absorption
4. Bruno Biais, Pierre Hillion & Chester Spatt (1995) / Christine Parlour (1998) Dynamic LOB Order Choice & Queue Fill Probability Game
5. Tobias Adrian & Markus K. Brunnermeier (2016) CoVaR, Delta-CoVaR (ΔCoVaR) & Macroprudential Systemic Risk Quantile Regression
6. Nicolae Gârleanu & Lasse Heje Pedersen (2011) Margin-Based Asset Pricing & The Leverage-Margin Basis Spread
"""

import sys
import math
import json
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

# Ensure root workspace is on path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from tests.test_faz47_finance_models import (
    PiterbargCollateralizedDiscounting,
    GoldsteinJuLelandCapitalStructure,
    KyleBackContinuousInformedTrading,
    BiaisParlourLOBGame,
    AdrianBrunnermeierCoVaR,
    GarleanuPedersenMarginPricing,
)

def run_faz47_verification_suite() -> Dict[str, Any]:
    """Runs programmatic evaluations across all 6 Faz 47 quantitative financial models."""

    # 1. Piterbarg Multi-Currency Collateralized Discounting & CTD Margrabe Option
    piterbarg_engine = PiterbargCollateralizedDiscounting(domestic_rf=0.035)
    rates = {"USD": 0.045, "EUR": 0.025, "GBP": 0.038, "JPY": 0.005}
    basis = {"USD": 0.0015, "EUR": -0.0010, "GBP": 0.0035, "JPY": -0.0040}
    best_ccy, best_net_rate = piterbarg_engine.effective_collateral_rate_deterministic(rates, basis)
    margrabe_res = piterbarg_engine.collateral_choice_option_margrabe(
        V1=1.0, V2=0.97, sigma1=0.14, sigma2=0.11, rho=0.55, T=2.0
    )
    csa_df = piterbarg_engine.discount_factor_with_ctd(base_rate=0.035, ctd_spread_bps=28.0, maturity=5.0)

    # 2. Goldstein, Ju & Leland (GJL 2001) Dynamic EBIT Capital Structure
    gjl_engine = GoldsteinJuLelandCapitalStructure(r=0.06, mu=0.015, sigma=0.24, tau_tax=0.25, alpha_bankruptcy=0.35)
    gjl_res = gjl_engine.price_capital_structure(delta_0=18.0, coupon=7.5)

    # 3. Kyle-Back Continuous Informed Trading
    kyle_engine = KyleBackContinuousInformedTrading(p0=100.0, sigma0_variance=25.0, sigma_u_noise_vol=2.5, T=1.0)
    kyle_profit = kyle_engine.expected_insider_profit()
    kyle_lambda = kyle_engine.lambda_kyle

    # 4. Biais-Parlour Dynamic LOB Game
    lob_engine = BiaisParlourLOBGame(tick_size=0.01, order_arrival_intensity=15.0, time_horizon=1.0, adverse_selection_alpha=0.005)
    q_cutoff = lob_engine.find_indifference_queue_threshold(spread=0.04, private_valuation=0.08)
    front_res = lob_engine.evaluate_order_payoffs(spread=0.04, queue_position=2, private_valuation=0.08)

    # 5. Adrian & Brunnermeier (2016) CoVaR and Delta-CoVaR
    covar_engine = AdrianBrunnermeierCoVaR(quantile_q=0.05)
    np.random.seed(42)
    n_obs = 300
    m_factor = np.random.normal(0.0, 0.025, n_obs)
    r_bank = 0.9 * m_factor + np.random.normal(0.0, 0.018, n_obs)
    r_sys = 0.75 * m_factor + 0.6 * r_bank + np.random.normal(0.0, 0.012, n_obs)
    covar_res = covar_engine.compute_delta_covar(r_bank, r_sys, state_variables=m_factor)

    # 6. Gârleanu & Pedersen (2011) Margin-Based Pricing & Basis Spread
    margin_engine = GarleanuPedersenMarginPricing(rf=0.035, market_risk_premium=0.055, margin_shadow_price_psi=0.045)
    basis_res = margin_engine.compute_law_of_one_price_basis(haircut_high=0.50, haircut_low=0.10)

    return {
        "piterbarg_ctd": {
            "optimal_currency": best_ccy,
            "optimal_net_rate": best_net_rate,
            "ctd_option_value": margrabe_res["ctd_collateral_value"],
            "csa_discount_factor_5y": csa_df,
        },
        "goldstein_ju_leland": {
            "endogenous_default_barrier": gjl_res["delta_B"],
            "firm_value": gjl_res["total_firm_value"],
            "debt_value": gjl_res["debt_value"],
            "equity_value": gjl_res["equity_value"],
            "tax_shield": gjl_res["tax_shield"],
            "credit_spread_bps": gjl_res["credit_spread_bps"],
        },
        "kyle_back": {
            "constant_lambda": kyle_lambda,
            "expected_insider_profit": kyle_profit,
        },
        "biais_parlour_lob": {
            "indifference_queue_depth": q_cutoff,
            "preferred_order_type_front": front_res["optimal_order_type"],
            "fill_probability_q2": front_res["fill_probability"],
        },
        "adrian_brunnermeier_covar": {
            "delta_covar": covar_res["delta_covar"],
            "systemic_impact_score": covar_res["systemic_impact_score"],
            "is_systemically_significant": covar_res["is_systemically_significant"],
        },
        "garleanu_pedersen_margin": {
            "basis_spread_bps": basis_res["basis_spread_bps"],
            "margin_difference": basis_res["margin_difference"],
            "shadow_price_psi": basis_res["shadow_price_psi"],
        }
    }

if __name__ == "__main__":
    results = run_faz47_verification_suite()
    print("=== FAZ 47 FINANCIAL AUDITOR VERIFICATION RESULTS ===")
    print(json.dumps(results, indent=2, default=str))
