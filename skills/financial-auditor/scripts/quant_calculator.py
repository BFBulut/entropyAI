#!/usr/bin/env python3
"""CLI and library utility for quantitative finance calculations:
- SaaS Unit Economics (Rule of 40, Magic Number, LTV/CAC)
- Banking Metrics (NIM, Capital Adequacy Ratio)
- Fixed Income Duration & Convexity
- Market Microstructure (Order Book Imbalance - OBI, VWAP)
"""

import argparse
import json
from typing import Dict, Any, List


def calculate_saas_metrics(
    revenue_growth_pct: float,
    fcf_margin_pct: float,
    cac: float = 0.0,
    ltv: float = 0.0,
    quarterly_net_arr_add: float = 0.0,
    prev_quarter_sm_spend: float = 0.0
) -> Dict[str, Any]:
    """Calculates SaaS performance metrics."""
    rule_of_40_score = revenue_growth_pct + fcf_margin_pct
    rule_of_40_passed = rule_of_40_score >= 40.0

    ltv_cac_ratio = (ltv / cac) if cac > 0 else 0.0
    magic_number = (
        (quarterly_net_arr_add * 4.0 / prev_quarter_sm_spend)
        if prev_quarter_sm_spend > 0 else 0.0
    )

    return {
        "rule_of_40_score": round(rule_of_40_score, 2),
        "rule_of_40_passed": rule_of_40_passed,
        "ltv_cac_ratio": round(ltv_cac_ratio, 2),
        "ltv_cac_status": (
            "Mükemmel (>= 3x)" if ltv_cac_ratio >= 3.0
            else "Yetersiz (< 3x)" if ltv_cac_ratio > 0
            else "Belirtilmedi"
        ),
        "magic_number": round(magic_number, 2),
        "magic_number_status": (
            "Agresif Satış Yatırımı Yapılmalı (>= 0.75)" if magic_number >= 0.75
            else "Satış Verimliliği Düşük (< 0.75)" if magic_number > 0
            else "Belirtilmedi"
        )
    }


def calculate_banking_metrics(
    interest_income: float,
    interest_expense: float,
    earning_assets: float,
    tier1_capital: float,
    tier2_capital: float,
    risk_weighted_assets: float
) -> Dict[str, Any]:
    """Calculates Banking performance metrics (NIM & Capital Adequacy Ratio - Basel III)."""
    if earning_assets <= 0 or risk_weighted_assets <= 0:
        return {"error": "Earning assets and risk-weighted assets must be positive"}

    net_interest_income = interest_income - interest_expense
    nim_pct = (net_interest_income / earning_assets) * 100

    total_regulatory_capital = tier1_capital + tier2_capital
    car_pct = (total_regulatory_capital / risk_weighted_assets) * 100

    return {
        "net_interest_margin_pct": round(nim_pct, 2),
        "capital_adequacy_ratio_pct": round(car_pct, 2),
        "basel_iii_status": "Güçlü Tampon (>= 12%)" if car_pct >= 12.0 else "Riskli / Düşük (< 10%)"
    }


def calculate_bond_price_change(
    modified_duration: float,
    convexity: float,
    yield_change_bps: float
) -> Dict[str, Any]:
    """Calculates estimated percentage bond price change using Duration and Convexity approximation.
    dP/P ~= -D_mod * dy + 0.5 * Convexity * (dy)^2
    where dy = yield_change_bps / 10000.
    """
    dy = yield_change_bps / 10000.0
    duration_effect = -modified_duration * dy
    convexity_effect = 0.5 * convexity * (dy ** 2)
    total_pct_change = (duration_effect + convexity_effect) * 100

    return {
        "yield_change_bps": yield_change_bps,
        "duration_effect_pct": round(duration_effect * 100, 3),
        "convexity_effect_pct": round(convexity_effect * 100, 3),
        "estimated_total_price_change_pct": round(total_pct_change, 3)
    }


def calculate_order_book_imbalance(
    bid_volume: float,
    ask_volume: float
) -> Dict[str, Any]:
    """Calculates Order Book Imbalance (OBI) = (Bids - Asks) / (Bids + Asks)."""
    total_volume = bid_volume + ask_volume
    if total_volume <= 0:
        return {"error": "Total volume must be greater than zero"}

    obi = (bid_volume - ask_volume) / total_volume

    if obi > 0.40:
        signal = "Güçlü Alış Baskısı (Yukarı Yönlü Momentum)"
    elif obi < -0.40:
        signal = "Güçlü Satış Baskısı (Aşağı Yönlü Momentum)"
    else:
        signal = "Nötr / Dengeli Emir Defteri"

    return {
        "obi": round(obi, 3),
        "bid_ratio_pct": round((bid_volume / total_volume) * 100, 1),
        "ask_ratio_pct": round((ask_volume / total_volume) * 100, 1),
        "microstructure_signal": signal
    }


def calculate_vwap(trades: List[Dict[str, float]]) -> Dict[str, Any]:
    """Calculates Volume-Weighted Average Price from trade records [{'price': P, 'volume': V}]."""
    total_pv = sum(t["price"] * t["volume"] for t in trades)
    total_vol = sum(t["volume"] for t in trades)

    if total_vol <= 0:
        return {"error": "Total volume must be greater than zero"}

    vwap = total_pv / total_vol
    return {
        "vwap": round(vwap, 3),
        "total_volume": round(total_vol, 2),
        "total_turnover": round(total_pv, 2)
    }


def main():
    parser = argparse.ArgumentParser(description="Quantitative Finance & Microstructure Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # SaaS
    saas_p = subparsers.add_parser("saas")
    saas_p.add_argument("--growth", type=float, required=True, help="Revenue growth %")
    saas_p.add_argument("--fcf-margin", type=float, required=True, help="FCF margin %")
    saas_p.add_argument("--cac", type=float, default=0.0)
    saas_p.add_argument("--ltv", type=float, default=0.0)

    # Banking
    bank_p = subparsers.add_parser("banking")
    bank_p.add_argument("--int-inc", type=float, required=True)
    bank_p.add_argument("--int-exp", type=float, required=True)
    bank_p.add_argument("--earn-assets", type=float, required=True)
    bank_p.add_argument("--tier1", type=float, required=True)
    bank_p.add_argument("--tier2", type=float, default=0.0)
    bank_p.add_argument("--rwa", type=float, required=True)

    # Bond
    bond_p = subparsers.add_parser("bond")
    bond_p.add_argument("--mod-dur", type=float, required=True)
    bond_p.add_argument("--convexity", type=float, default=0.0)
    bond_p.add_argument("--bps", type=float, required=True, help="Yield change in basis points (e.g. +100 or -50)")

    # OBI
    obi_p = subparsers.add_parser("obi")
    obi_p.add_argument("--bids", type=float, required=True)
    obi_p.add_argument("--asks", type=float, required=True)

    args = parser.parse_args()

    if args.command == "saas":
        res = calculate_saas_metrics(args.growth, args.fcf_margin, args.cac, args.ltv)
    elif args.command == "banking":
        res = calculate_banking_metrics(args.int_inc, args.int_exp, args.earn_assets, args.tier1, args.tier2, args.rwa)
    elif args.command == "bond":
        res = calculate_bond_price_change(args.mod_dur, args.convexity, args.bps)
    elif args.command == "obi":
        res = calculate_order_book_imbalance(args.bids, args.asks)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
