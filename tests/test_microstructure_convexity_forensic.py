"""Automated pytest test suite for Market Microstructure, Yield Curve Dynamics & Forensic Financial Analytics:
- VPIN (Volume-Synchronized Probability of Toxicity)
- Almgren-Chriss Optimal Execution
- Dechow F-Score
- Piotroski 9-Point F-Score
- Nelson-Siegel Yield Curve
- Heston Stochastic Volatility & Feller Condition
"""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parent.parent / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from microstructure_convexity_forensic import (
    calculate_vpin,
    calculate_almgren_chriss_trajectory,
    calculate_dechow_f_score,
    calculate_piotroski_f_score,
    calculate_nelson_siegel_yield,
    calculate_heston_feller_condition
)


def test_vpin_toxic_flow():
    # 5 buckets of 10,000 volume each
    # Severe imbalance: mostly sellers
    buy_vols = [1000.0, 500.0, 1500.0, 800.0, 1200.0]
    sell_vols = [9000.0, 9500.0, 8500.0, 9200.0, 8800.0]
    bucket_size = 10000.0

    res = calculate_vpin(buy_vols, sell_vols, bucket_size)
    assert res["number_of_buckets"] == 5
    assert res["bucket_size"] == 10000.0
    # Imbalances: 8000, 9000, 7000, 8400, 7600 -> sum = 40000
    # VPIN = 40000 / (5 * 10000) = 0.80 (80%)
    assert res["vpin_score"] == 0.80
    assert "AŞIRI YÜKSEK TOKSİSİTE" in res["toxicity_regime"]

    # Low toxicity balanced flow
    b_balanced = [5000.0, 4800.0, 5100.0, 4900.0, 5050.0]
    s_balanced = [5000.0, 5200.0, 4900.0, 5100.0, 4950.0]
    low_res = calculate_vpin(b_balanced, s_balanced, bucket_size)
    assert low_res["vpin_score"] < 0.20
    assert "DÜŞÜK TOKSİSİTE" in low_res["toxicity_regime"]

    # Invalid inputs
    err1 = calculate_vpin([], [], 1000)
    assert "error" in err1
    err2 = calculate_vpin([100], [100, 200], 1000)
    assert "error" in err2
    err3 = calculate_vpin([100], [100], 0)
    assert "error" in err3
    err4 = calculate_vpin([-10], [10], 1000)
    assert "error" in err4


def test_almgren_chriss_trajectory():
    total_shares = 100000.0
    days = 5
    intervals = 5
    eta = 2.5e-6
    risk_aversion = 1e-6
    sigma = 0.02

    res = calculate_almgren_chriss_trajectory(
        total_shares=total_shares,
        time_horizon_days=days,
        intervals=intervals,
        temporary_impact_eta=eta,
        risk_aversion_lambda=risk_aversion,
        daily_volatility_sigma=sigma
    )

    assert res["total_initial_shares"] == 100000.0
    assert res["time_horizon_days"] == 5
    assert len(res["trajectory"]) == 6  # 0 to 5
    assert res["trajectory"][0]["remaining_shares"] == 100000.0
    assert res["trajectory"][-1]["remaining_shares"] == 0.0
    assert "OPTİMAL İCRA" in res["execution_strategy_profile"] or "LİNEER" in res["execution_strategy_profile"]

    # Linear TWAP when risk aversion is zero
    twap_res = calculate_almgren_chriss_trajectory(
        total_shares=total_shares,
        time_horizon_days=days,
        intervals=intervals,
        temporary_impact_eta=eta,
        risk_aversion_lambda=0.0,
        daily_volatility_sigma=sigma
    )
    assert twap_res["kappa_urgency_parameter"] == 0.0
    assert "LİNEER / TWAP" in twap_res["execution_strategy_profile"]
    assert twap_res["trajectory"][1]["remaining_shares"] == 80000.0

    # Invalid inputs
    err = calculate_almgren_chriss_trajectory(-100, 5, 5, eta, risk_aversion, sigma)
    assert "error" in err


def test_dechow_f_score():
    # High risk case: high accruals, rising receivables, rising soft assets
    high_risk = calculate_dechow_f_score(
        accruals_pct=0.15,
        receivables_change_pct=0.25,
        inventory_change_pct=0.10,
        soft_assets_pct=0.70,
        cash_sales_growth_pct=-0.05,
        roa_change=-0.08
    )
    assert high_risk["dechow_f_score"] > 0
    assert "manipulation_risk_verdict" in high_risk

    # Low risk / clean accounting case: negative accruals (CFO > NI), low soft assets
    low_risk = calculate_dechow_f_score(
        accruals_pct=-0.10,
        receivables_change_pct=-0.05,
        inventory_change_pct=-0.02,
        soft_assets_pct=0.15,
        cash_sales_growth_pct=0.10,
        roa_change=0.05
    )
    assert low_risk["dechow_f_score"] < 1.00
    assert "DÜŞÜK RİSK" in low_risk["manipulation_risk_verdict"]


def test_piotroski_f_score():
    # Strong firm: all 9 points pass
    strong = calculate_piotroski_f_score(
        roa=0.08,
        cfo=5000000.0,
        delta_roa=0.02,
        cfo_greater_than_ni=True,
        delta_long_term_leverage=-0.05,
        delta_current_ratio=0.30,
        new_shares_issued=False,
        delta_gross_margin=0.04,
        delta_asset_turnover=0.10
    )
    assert strong["piotroski_f_score"] == 9
    assert "MÜKEMMEL FİNANSAL SAĞLIK" in strong["financial_health_classification"]

    # Distressed / weak firm: 1 point
    distressed = calculate_piotroski_f_score(
        roa=-0.05,
        cfo=-1000000.0,
        delta_roa=-0.03,
        cfo_greater_than_ni=False,
        delta_long_term_leverage=0.15,
        delta_current_ratio=-0.50,
        new_shares_issued=True,
        delta_gross_margin=-0.08,
        delta_asset_turnover=0.01  # only 1 pt
    )
    assert distressed["piotroski_f_score"] == 1
    assert "KRİTİK / İFLAS" in distressed["financial_health_classification"]


def test_nelson_siegel_yield():
    # Normal upward sloping curve: beta0 = 5.0%, beta1 = -2.5%, beta2 = 1.0%
    res_10y = calculate_nelson_siegel_yield(
        maturity_years=10.0,
        beta0=5.0,
        beta1=-2.5,
        beta2=1.0,
        lambda_param=2.0
    )
    assert res_10y["maturity_years"] == 10.0
    assert "YUKARI EĞİMLİ" in res_10y["yield_curve_shape"]
    assert res_10y["modeled_yield_pct"] > 0

    # Inverted yield curve: beta1 = 2.0%
    inverted = calculate_nelson_siegel_yield(2.0, 4.0, 2.0, 0.5, 2.0)
    assert "TERS GETİRİ EĞRİSİ" in inverted["yield_curve_shape"]

    # Invalid inputs
    err = calculate_nelson_siegel_yield(-1.0, 5.0, -2.0, 1.0)
    assert "error" in err


def test_heston_feller_condition():
    # Condition satisfied: 2 * 3.0 * 0.04 = 0.24 > 0.3^2 = 0.09
    res_sat = calculate_heston_feller_condition(kappa=3.0, theta=0.04, xi=0.3)
    assert res_sat["feller_condition_satisfied"] is True
    assert res_sat["feller_ratio"] > 1.0
    assert "SAĞLANIYOR" in res_sat["mathematical_implication"]

    # Condition violated: 2 * 0.5 * 0.04 = 0.04 < 0.4^2 = 0.16
    res_viol = calculate_heston_feller_condition(kappa=0.5, theta=0.04, xi=0.4)
    assert res_viol["feller_condition_satisfied"] is False
    assert res_viol["feller_ratio"] < 1.0
    assert "İHLAL EDİLDİ" in res_viol["mathematical_implication"]

    # Invalid inputs
    err = calculate_heston_feller_condition(-1.0, 0.04, 0.3)
    assert "error" in err
