"""Automated pytest test suite for Hawkes Processes, Rough Volatility, Repo Plumbing, Stub Value & DeFi MEV:
- Hawkes Point Processes & LOB Toxicity (Branching Ratio, Endogeneity Index, Kyle's Lambda & Spread Decomposition)
- Rough Volatility & Fractional Brownian Motion (Gatheral-Rosenbaum H~0.1, Power-law Skew Scaling)
- Repo Market Plumbing & Collateral Scarcity (GC vs Specials, Convenience Yield & TMPG Fail Charge)
- Stub Value Anomaly, Carve-Out Arbitrage & Rights Offering (Negative EV Stub, TERP & Nil-Paid Value)
- DeFi Financial Engineering: MEV Sandwich Economics & Curve v2 Dynamic Peg
"""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from hawkes_rough_repo_defi import (
    calculate_hawkes_and_lob_toxicity,
    calculate_rough_volatility_and_hurst,
    calculate_repo_plumbing_and_specials,
    calculate_stub_value_and_rights_offering,
    calculate_defi_mev_and_curve_v2
)


def test_hawkes_and_lob_toxicity():
    # 1. Stable, exogenous-driven regime
    res_stable = calculate_hawkes_and_lob_toxicity(
        mu=1.2,
        alpha=0.4,
        beta=1.0,
        cov_delta_p_q=0.0005,
        var_q=1.0,
        total_spread_bps=10.0,
        adverse_selection_pct=40.0,
        inventory_risk_pct=30.0
    )
    assert res_stable["branching_ratio_eta"] == 0.4
    assert res_stable["endogeneity_index_pct"] == 40.0
    assert res_stable["asymptotic_intensity"] == 2.0  # 1.2 / (1 - 0.4) = 2.0
    assert "Kararlı" in res_stable["stability_regime"]
    assert res_stable["kyles_lambda"] == 0.0005
    assert res_stable["spread_adverse_selection_bps"] == 4.0
    assert res_stable["spread_inventory_risk_bps"] == 3.0
    assert res_stable["spread_order_processing_bps"] == 3.0

    # 2. Near-critical flash crash danger regime
    res_critical = calculate_hawkes_and_lob_toxicity(
        mu=0.5,
        alpha=0.98,
        beta=1.0,
        cov_delta_p_q=0.012,
        var_q=1.0,
        total_spread_bps=25.0,
        adverse_selection_pct=60.0,
        inventory_risk_pct=25.0
    )
    assert res_critical["branching_ratio_eta"] == 0.98
    assert res_critical["endogeneity_index_pct"] == 98.0
    assert "Çöküş Öncesi" in res_critical["stability_regime"]
    assert "Agresif piyasa emirlerinden kaçının" in res_critical["execution_recommendation"]

    # 3. Supercritical explosion regime (eta >= 1.0)
    res_super = calculate_hawkes_and_lob_toxicity(
        mu=1.0,
        alpha=1.2,
        beta=1.0,
        cov_delta_p_q=0.05,
        var_q=1.0,
        total_spread_bps=50.0
    )
    assert res_super["branching_ratio_eta"] == 1.2
    assert res_super["asymptotic_intensity"] == float("inf")
    assert "Süper-Kritik" in res_super["stability_regime"]

    # 4. Error validation
    err = calculate_hawkes_and_lob_toxicity(mu=-1.0, alpha=0.5, beta=1.0, cov_delta_p_q=0.1, var_q=1.0, total_spread_bps=10.0)
    assert "error" in err


def test_rough_volatility_and_hurst():
    # 1. Standard rough volatility empirical regime (H = 0.12)
    res_rough = calculate_rough_volatility_and_hurst(
        hurst_parameter_h=0.12,
        spot_vol_pct=22.5,
        maturities_days=[1.0, 30.0, 365.0],
        baseline_skew_multiplier=0.15
    )
    assert res_rough["hurst_parameter_h"] == 0.12
    assert res_rough["roughness_degree"] == 0.38
    assert res_rough["power_law_exponent"] == -0.38
    assert "Rough Volatilite" in res_rough["hurst_regime"]
    assert res_rough["skew_blowup_ratio_1d_vs_1y"] > 5.0  # 365^0.38 approx 9.4x blowup
    assert len(res_rough["skew_term_structure"]) == 3
    # 1 day skew must be significantly larger than 1 year skew
    skews = res_rough["skew_term_structure"]
    assert skews[0]["atm_implied_skew"] > skews[2]["atm_implied_skew"]

    # 2. Classical Brownian motion regime (H = 0.50)
    res_brownian = calculate_rough_volatility_and_hurst(
        hurst_parameter_h=0.50,
        spot_vol_pct=20.0,
        maturities_days=[1.0, 365.0]
    )
    assert res_brownian["roughness_degree"] == 0.0
    assert res_brownian["power_law_exponent"] == 0.0
    assert "Standart Brown" in res_brownian["hurst_regime"]
    assert res_brownian["skew_blowup_ratio_1d_vs_1y"] == 1.0

    # 3. Validation error
    err = calculate_rough_volatility_and_hurst(hurst_parameter_h=1.2, spot_vol_pct=20.0)
    assert "error" in err


def test_repo_plumbing_and_specials():
    # 1. On-The-Run Treasury in severe special squeeze
    res_squeeze = calculate_repo_plumbing_and_specials(
        gc_repo_rate_pct=5.35,
        special_repo_rate_pct=0.25,
        fed_funds_target_pct=5.25,
        failed_delivery_amount=100000000.0,  # $100M
        fail_duration_days=3
    )
    assert res_squeeze["specialness_spread_pct"] == 5.1
    assert res_squeeze["specialness_spread_bps"] == 510.0
    assert res_squeeze["convenience_yield_pct"] == 5.1
    assert "Akut Özel Sıkışma" in res_squeeze["collateral_status"]
    assert res_squeeze["tmpg_fail_charge_rate_pct"] == 0.0  # 3.0 - 5.25 < 0 -> 0.0%
    assert res_squeeze["fail_penalty_cost"] == 0.0
    assert res_squeeze["negative_repo_occurred"] is False

    # 2. Zero / Low Fed Funds rate scenario with TMPG fail charge penalty
    res_low_rate = calculate_repo_plumbing_and_specials(
        gc_repo_rate_pct=0.25,
        special_repo_rate_pct=-0.50,  # Negative repo
        fed_funds_target_pct=0.25,
        failed_delivery_amount=50000000.0,  # $50M
        fail_duration_days=5
    )
    assert res_low_rate["specialness_spread_pct"] == 0.75
    assert res_low_rate["tmpg_fail_charge_rate_pct"] == 2.75  # 3.0 - 0.25 = 2.75%
    # Penalty = 50M * (2.75 / 100) * (5 / 360) = 19097.22
    assert res_low_rate["fail_penalty_cost"] == 19097.22
    assert res_low_rate["negative_repo_occurred"] is True

    # 3. Error handling
    err = calculate_repo_plumbing_and_specials(gc_repo_rate_pct=5.0, special_repo_rate_pct=4.0, fed_funds_target_pct=5.0, failed_delivery_amount=-100, fail_duration_days=1)
    assert "error" in err


def test_stub_value_and_rights_offering():
    # 1. Palm / 3Com negative stub value anomaly
    # Parent (3Com) cap: $10B, Sub (Palm) cap: $15B, Parent owns 80% of Sub ($12B stake)
    # Stub Value = 10B - 12B = -$2B
    res_stub = calculate_stub_value_and_rights_offering(
        parent_market_cap=10000000000.0,
        sub_market_cap=15000000000.0,
        ownership_pct=80.0,
        current_stock_price=50.0,
        num_existing_shares=10000000.0,
        num_new_shares=2500000.0,  # 1 for 4 rights
        subscription_price=35.0   # 30% discount
    )
    assert res_stub["sub_stake_value"] == 12000000000.0
    assert res_stub["stub_value"] == -2000000000.0
    assert res_stub["is_negative_stub"] is True
    assert "NEGATİF STUB ANOMALİSİ" in res_stub["stub_diagnosis"]

    # Rights offering checks
    # Total shares post = 12.5M
    # TERP = (10M * 50 + 2.5M * 35) / 12.5M = (500M + 87.5M) / 12.5M = 587.5M / 12.5M = 47.0
    assert res_stub["terp"] == 47.0
    assert res_stub["nil_paid_right_value"] == 3.0  # 50.0 - 47.0
    assert res_stub["subscription_discount_pct"] == 30.0
    assert res_stub["dilution_pct"] == 20.0
    assert res_stub["rights_ratio"] == "1:4.0"

    # 2. Positive stub
    res_pos = calculate_stub_value_and_rights_offering(
        parent_market_cap=20000000000.0,
        sub_market_cap=10000000000.0,
        ownership_pct=50.0,
        current_stock_price=100.0,
        num_existing_shares=1000000.0,
        num_new_shares=500000.0,
        subscription_price=80.0
    )
    assert res_pos["stub_value"] == 15000000000.0
    assert res_pos["is_negative_stub"] is False

    # 3. Error validation
    err = calculate_stub_value_and_rights_offering(
        parent_market_cap=-100, sub_market_cap=100, ownership_pct=50,
        current_stock_price=10, num_existing_shares=100, num_new_shares=10, subscription_price=5
    )
    assert "error" in err


def test_defi_mev_and_curve_v2():
    # 1. Viable sandwich attack scenario
    res_mev = calculate_defi_mev_and_curve_v2(
        victim_input_amount=100000.0,
        victim_slippage_tolerance_pct=1.5,
        pool_reserve_x=10000000.0,
        pool_reserve_y=10000000.0,
        gas_and_builder_cost_usd=250.0,
        current_internal_oracle_price=1.0000,
        market_spot_price=1.0080,  # 80 bps away
        repeg_threshold_bps=50.0
    )
    assert res_mev["initial_spot_price"] == 1.0
    assert res_mev["worst_acceptable_victim_price"] == 1.015
    assert res_mev["approx_optimal_frontrun_x"] == 75000.0
    assert res_mev["gross_mev_usd"] == 1500.0  # 100,000 * 0.015 = 1500
    assert res_mev["net_mev_profit_usd"] == 1250.0  # 1500 - 250 = 1250
    assert res_mev["mev_viable"] is True
    assert "KÂRLI SANDVİÇ" in res_mev["mev_status"]

    # Curve v2 Dynamic Peg checks
    assert res_mev["peg_distance_bps"] == 80.0
    assert res_mev["repeg_triggered"] is True
    assert "DİNAMİK YENİDEN MERKEZLEME" in res_mev["repeg_status"]

    # 2. Unviable sandwich (gas cost exceeds profit)
    res_unviable = calculate_defi_mev_and_curve_v2(
        victim_input_amount=1000.0,
        victim_slippage_tolerance_pct=0.5,
        pool_reserve_x=5000000.0,
        pool_reserve_y=5000000.0,
        gas_and_builder_cost_usd=100.0,
        current_internal_oracle_price=1.0,
        market_spot_price=1.0010,
        repeg_threshold_bps=50.0
    )
    assert res_unviable["gross_mev_usd"] == 5.0
    assert res_unviable["net_mev_profit_usd"] == -95.0
    assert res_unviable["mev_viable"] is False
    assert "ZARARLI" in res_unviable["mev_status"]
    assert res_unviable["repeg_triggered"] is False

    # 3. Error validation
    err = calculate_defi_mev_and_curve_v2(
        victim_input_amount=-10, victim_slippage_tolerance_pct=1.0,
        pool_reserve_x=1000, pool_reserve_y=1000, gas_and_builder_cost_usd=10,
        current_internal_oracle_price=1.0, market_spot_price=1.0
    )
    assert "error" in err
