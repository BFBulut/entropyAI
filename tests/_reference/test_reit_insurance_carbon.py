"""Automated pytest test suite for REIT, Insurance and Carbon CBAM Engine."""

import sys
from pathlib import Path
import pytest

# Ensure skill scripts path is importable
skill_scripts_dir = Path(__file__).parents[2] / "skills" / "financial-auditor" / "scripts"
sys.path.insert(0, str(skill_scripts_dir))

from reit_insurance_carbon import (
    calculate_reit_ffo_affo,
    calculate_property_cap_rate,
    calculate_insurance_combined_ratio,
    calculate_cbam_carbon_tax
)


def test_reit_ffo_affo():
    # Net Income = 50M, Depreciation = 30M, Gains = 5M -> FFO = 50 + 30 - 5 = 75M.
    # Maintenance CapEx = 15M -> AFFO = 75 - 15 = 60M.
    # Dividends paid = 45M -> Payout ratio = 45 / 60 = 75% (Safe <= 85%)
    res = calculate_reit_ffo_affo(
        net_income=50.0,
        real_estate_depreciation=30.0,
        gains_on_property_sales=5.0,
        maintenance_capex=15.0,
        dividend_paid=45.0
    )
    assert res["ffo"] == 75.0
    assert res["affo"] == 60.0
    assert res["affo_payout_ratio_pct"] == 75.0
    assert "Güvenli Temettü" in res["dividend_safety"]

    # Risky dividend payout
    risky_res = calculate_reit_ffo_affo(
        net_income=50.0,
        real_estate_depreciation=30.0,
        gains_on_property_sales=5.0,
        maintenance_capex=15.0,
        dividend_paid=55.0  # 55 / 60 = 91.67%
    )
    assert "Riskli" in risky_res["dividend_safety"]


def test_property_cap_rate():
    # NOI = 8M, Property Value = 100M -> Cap Rate = 8.0%
    res = calculate_property_cap_rate(net_operating_income=8.0, property_value=100.0)
    assert res["cap_rate_pct"] == 8.0
    assert "Yüksek Getirili" in res["evaluation"]

    # Invalid input
    err = calculate_property_cap_rate(8.0, 0.0)
    assert "error" in err


def test_insurance_combined_ratio():
    # Earned Premiums = 100M, Losses = 65M, Expenses = 28M
    # Loss ratio = 65%, Expense ratio = 28% -> Combined ratio = 93% (Underwriting profit = 7M)
    res = calculate_insurance_combined_ratio(
        incurred_losses=65.0,
        earned_premiums=100.0,
        underwriting_expenses=28.0
    )
    assert res["loss_ratio_pct"] == 65.0
    assert res["expense_ratio_pct"] == 28.0
    assert res["combined_ratio_pct"] == 93.0
    assert res["underwriting_profit"] == 7.0
    assert "Mükemmel / Negatif Maliyetli Sermaye" in res["float_status"]

    # Loss-making insurance operation (Combined ratio = 105%)
    loss_res = calculate_insurance_combined_ratio(
        incurred_losses=75.0,
        earned_premiums=100.0,
        underwriting_expenses=30.0
    )
    assert loss_res["combined_ratio_pct"] == 105.0
    assert "Operasyonel Zarar" in loss_res["float_status"]

    # Invalid input
    err = calculate_insurance_combined_ratio(50, 0, 10)
    assert "error" in err


def test_cbam_carbon_tax():
    # Steel exporter: 100,000 tons, 1.8 tons CO2 / ton steel
    # Total emissions = 180,000 tons. EUA = 80 EUR, Local carbon tax = 10 EUR -> Net = 70 EUR.
    # Total tax = 180,000 * 70 = 12,600,000 EUR. Tax per ton = 1.8 * 70 = 126 EUR.
    res = calculate_cbam_carbon_tax(
        export_tonnage=100000.0,
        emissions_per_ton=1.8,
        eua_price_eur=80.0,
        local_carbon_price_eur=10.0
    )
    assert res["total_embedded_emissions_ton"] == 180000.0
    assert res["net_carbon_price_eur"] == 70.0
    assert res["total_cbam_tax_eur"] == 12600000.0
    assert res["tax_impact_per_ton_product_eur"] == 126.0
