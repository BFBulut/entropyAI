#!/usr/bin/env python3
"""CLI and library utility for REITs, Insurance Actuarial, and Carbon CBAM analytics:
- REIT FFO & AFFO (Funds from Operations & Adjusted FFO)
- Real Estate Capitalization Rate (Cap Rate)
- Insurance Combined Ratio & Float Profitability
- EU CBAM Carbon Border Adjustment Tax Liability
"""

import argparse
import json
from typing import Dict, Any


def calculate_reit_ffo_affo(
    net_income: float,
    real_estate_depreciation: float,
    gains_on_property_sales: float = 0.0,
    maintenance_capex: float = 0.0,
    straight_line_rent_adjustment: float = 0.0,
    dividend_paid: float = 0.0
) -> Dict[str, Any]:
    """Calculates REIT Funds from Operations (FFO) and Adjusted FFO (AFFO)."""
    ffo = net_income + real_estate_depreciation - gains_on_property_sales
    affo = ffo - maintenance_capex - straight_line_rent_adjustment

    affo_payout_ratio = (dividend_paid / affo) * 100 if affo > 0 and dividend_paid > 0 else 0.0

    return {
        "net_income": round(net_income, 2),
        "real_estate_depreciation": round(real_estate_depreciation, 2),
        "ffo": round(ffo, 2),
        "maintenance_capex": round(maintenance_capex, 2),
        "affo": round(affo, 2),
        "affo_payout_ratio_pct": round(affo_payout_ratio, 2),
        "dividend_safety": (
            "Güvenli Temettü Dağıtımı (AFFO Ödeme Oranı <= %85)" if affo_payout_ratio > 0 and affo_payout_ratio <= 85.0
            else "Riskli / Sürdürülemez Temettü (> %85)" if affo_payout_ratio > 85.0
            else "Temettü Verisi Yok"
        )
    }


def calculate_property_cap_rate(
    net_operating_income: float,
    property_value: float
) -> Dict[str, Any]:
    """Calculates Real Estate Capitalization Rate = NOI / Property Value."""
    if property_value <= 0:
        return {"error": "Property value must be positive"}

    cap_rate_pct = (net_operating_income / property_value) * 100

    return {
        "net_operating_income": round(net_operating_income, 2),
        "property_value": round(property_value, 2),
        "cap_rate_pct": round(cap_rate_pct, 2),
        "evaluation": (
            "Yüksek Getirili / Fırsat (Cap Rate >= %8)" if cap_rate_pct >= 8.0
            else "Sağlıklı Prime Getiri (%5 - %8)" if cap_rate_pct >= 5.0
            else "Düşük Getiri / Pahalı Varlık (< %5)"
        )
    }


def calculate_insurance_combined_ratio(
    incurred_losses: float,
    earned_premiums: float,
    underwriting_expenses: float
) -> Dict[str, Any]:
    """Calculates Insurance Loss Ratio, Expense Ratio, and Combined Ratio.
    Combined Ratio = Loss Ratio + Expense Ratio.
    """
    if earned_premiums <= 0:
        return {"error": "Earned premiums must be positive"}

    loss_ratio_pct = (incurred_losses / earned_premiums) * 100
    expense_ratio_pct = (underwriting_expenses / earned_premiums) * 100
    combined_ratio_pct = loss_ratio_pct + expense_ratio_pct

    underwriting_profit = earned_premiums - (incurred_losses + underwriting_expenses)

    return {
        "loss_ratio_pct": round(loss_ratio_pct, 2),
        "expense_ratio_pct": round(expense_ratio_pct, 2),
        "combined_ratio_pct": round(combined_ratio_pct, 2),
        "underwriting_profit": round(underwriting_profit, 2),
        "float_status": (
            "Mükemmel / Negatif Maliyetli Sermaye (Combined Ratio < %100 - Underwriting Kârı)"
            if combined_ratio_pct < 100.0
            else "Operasyonel Zarar (Combined Ratio >= %100 - Kâr Yalnızca Yatırım Getirisine Bağlı)"
        )
    }


def calculate_cbam_carbon_tax(
    export_tonnage: float,
    emissions_per_ton: float,
    eua_price_eur: float,
    local_carbon_price_eur: float = 0.0
) -> Dict[str, Any]:
    """Calculates EU Carbon Border Adjustment Mechanism (CBAM) tax liability."""
    net_carbon_price = max(0.0, eua_price_eur - local_carbon_price_eur)
    total_emissions = export_tonnage * emissions_per_ton
    total_tax_eur = total_emissions * net_carbon_price
    tax_per_ton_product_eur = emissions_per_ton * net_carbon_price

    return {
        "export_tonnage": round(export_tonnage, 2),
        "specific_emissions_per_ton": round(emissions_per_ton, 3),
        "total_embedded_emissions_ton": round(total_emissions, 2),
        "net_carbon_price_eur": round(net_carbon_price, 2),
        "total_cbam_tax_eur": round(total_tax_eur, 2),
        "tax_impact_per_ton_product_eur": round(tax_per_ton_product_eur, 2)
    }


def main():
    parser = argparse.ArgumentParser(description="REIT, Insurance & Carbon Analytics Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # REIT
    reit_p = subparsers.add_parser("reit")
    reit_p.add_argument("--ni", type=float, required=True, help="Net Income")
    reit_p.add_argument("--dep", type=float, required=True, help="Real Estate Depreciation")
    reit_p.add_argument("--gains", type=float, default=0.0, help="Gains on sales")
    reit_p.add_argument("--capex", type=float, default=0.0, help="Maintenance CapEx")
    reit_p.add_argument("--div", type=float, default=0.0, help="Dividends paid")

    # Cap Rate
    cap_p = subparsers.add_parser("caprate")
    cap_p.add_argument("--noi", type=float, required=True, help="Net Operating Income")
    cap_p.add_argument("--val", type=float, required=True, help="Property Value")

    # Insurance
    ins_p = subparsers.add_parser("insurance")
    ins_p.add_argument("--losses", type=float, required=True, help="Incurred losses")
    ins_p.add_argument("--premiums", type=float, required=True, help="Earned premiums")
    ins_p.add_argument("--expenses", type=float, required=True, help="Underwriting expenses")

    # CBAM
    cbam_p = subparsers.add_parser("cbam")
    cbam_p.add_argument("--tons", type=float, required=True, help="Export tonnage")
    cbam_p.add_argument("--intensity", type=float, required=True, help="Emissions intensity (Ton CO2 / Ton product)")
    cbam_p.add_argument("--eua", type=float, required=True, help="EU ETS EUA Price in EUR")
    cbam_p.add_argument("--local", type=float, default=0.0, help="Local carbon price in EUR")

    args = parser.parse_args()

    if args.command == "reit":
        res = calculate_reit_ffo_affo(args.ni, args.dep, args.gains, args.capex, 0.0, args.div)
    elif args.command == "caprate":
        res = calculate_property_cap_rate(args.noi, args.val)
    elif args.command == "insurance":
        res = calculate_insurance_combined_ratio(args.losses, args.premiums, args.expenses)
    elif args.command == "cbam":
        res = calculate_cbam_carbon_tax(args.tons, args.intensity, args.eua, args.local)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
