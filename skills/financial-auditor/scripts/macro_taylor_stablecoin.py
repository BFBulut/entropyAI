#!/usr/bin/env python3
"""CLI and library utility for Macroeconomic & Digital Asset Analytics:
- Taylor Rule Policy Rate & Central Bank Behind-the-Curve Evaluation
- TIPS Breakeven Inflation Rate
- Miller-Orr Stochastic Corporate Cash Management Model (Z* and H* bounds)
- Over-Collateralized Stablecoin Health Factor & Liquidation Risk
"""

import argparse
import json
import math
from typing import Dict, Any, Optional


def calculate_taylor_rule_rate(
    neutral_real_rate: float,
    current_inflation: float,
    target_inflation: float,
    output_gap: float,
    actual_policy_rate: Optional[float] = None
) -> Dict[str, Any]:
    """Calculates the Taylor Rule recommended policy interest rate:
    i = r* + pi + 0.5 * (pi - pi*) + 0.5 * (y - y*)
    """
    inflation_gap = current_inflation - target_inflation
    taylor_rate = neutral_real_rate + current_inflation + 0.5 * inflation_gap + 0.5 * output_gap

    result: Dict[str, Any] = {
        "neutral_real_rate_pct": round(neutral_real_rate, 2),
        "current_inflation_pct": round(current_inflation, 2),
        "target_inflation_pct": round(target_inflation, 2),
        "inflation_gap_pct": round(inflation_gap, 2),
        "output_gap_pct": round(output_gap, 2),
        "taylor_rule_recommended_rate_pct": round(taylor_rate, 2)
    }

    if actual_policy_rate is not None:
        rate_spread = taylor_rate - actual_policy_rate
        result["actual_policy_rate_pct"] = round(actual_policy_rate, 2)
        result["policy_gap_pct"] = round(rate_spread, 2)
        if rate_spread > 0.5:
            result["stance_verdict"] = "BEHIND THE CURVE (Eğrinin Arkasında: Faiz yetersiz, sıkılaştırma baskısı yüksek)"
        elif rate_spread < -0.5:
            result["stance_verdict"] = "AHEAD OF THE CURVE (Eğrinin Önünde / Aşırı Sıkı: Faiz modelin üzerinde, indirim alanı var)"
        else:
            result["stance_verdict"] = "DENGE / UYUMLU (Model faizi ile fiili faiz tutarlı)"

    return result


def calculate_breakeven_inflation(
    nominal_yield: float,
    tips_real_yield: float
) -> Dict[str, Any]:
    """Calculates the Breakeven Inflation Rate:
    Breakeven Rate = Nominal Bond Yield - TIPS Real Yield
    """
    breakeven_rate = nominal_yield - tips_real_yield

    return {
        "nominal_yield_pct": round(nominal_yield, 3),
        "tips_real_yield_pct": round(tips_real_yield, 3),
        "breakeven_inflation_rate_pct": round(breakeven_rate, 3),
        "market_sentiment": (
            "YÜKSEK ENFLASYON BEKLENTİSİ (Piyasa enflasyon korumalı TIPS tahvillerini tercih ediyor)"
            if breakeven_rate >= 2.5
            else "ILIMLI / DENGELİ ENFLASYON BEKLENTİSİ (%2 - %2.5 bandında)"
            if breakeven_rate >= 2.0
            else "DÜŞÜK ENFLASYON / DEFLASYON RİSKİ (Nominal tahviller daha cazip)"
        )
    }


def calculate_miller_orr_bounds(
    transaction_cost: float,
    daily_cash_variance: float,
    daily_interest_rate: float,
    lower_bound: float = 0.0,
    current_cash: Optional[float] = None
) -> Dict[str, Any]:
    """Calculates optimal cash boundaries using the Miller-Orr Stochastic Cash Model:
    Z* = ((3 * F * sigma^2) / (4 * r))^(1/3) + L
    H* = 3 * Z* - 2 * L
    Average Cash = (4 * Z* - L) / 3
    """
    if transaction_cost <= 0:
        return {"error": "Transaction cost must be positive"}
    if daily_cash_variance <= 0:
        return {"error": "Daily cash variance must be positive"}
    if daily_interest_rate <= 0:
        return {"error": "Daily interest rate must be positive"}
    if lower_bound < 0:
        return {"error": "Lower bound cannot be negative"}

    base_spread = ((3.0 * transaction_cost * daily_cash_variance) / (4.0 * daily_interest_rate)) ** (1.0 / 3.0)
    target_z = base_spread + lower_bound
    upper_limit_h = 3.0 * target_z - 2.0 * lower_bound
    average_cash = (4.0 * target_z - lower_bound) / 3.0

    result: Dict[str, Any] = {
        "lower_bound_l": round(lower_bound, 2),
        "target_cash_level_z": round(target_z, 2),
        "upper_limit_h": round(upper_limit_h, 2),
        "expected_average_cash": round(average_cash, 2)
    }

    if current_cash is not None:
        result["current_cash_level"] = round(current_cash, 2)
        if current_cash > upper_limit_h:
            excess = current_cash - target_z
            result["recommended_action"] = f"MENKUL KIYMET ALIMI (Fazla nakit yatırıma yönlendirilmeli): {round(excess, 2)} TL/USD menkul kıymet alımı ile Z* seviyesine dönülmeli"
        elif current_cash < lower_bound:
            deficit = target_z - current_cash
            result["recommended_action"] = f"MENKUL KIYMET SATIŞI (Nakit takviyesi): {round(deficit, 2)} TL/USD menkul kıymet satılarak Z* seviyesine dönülmeli"
        else:
            result["recommended_action"] = "İŞLEM YAPMA (Nakit seviyesi optimal bant içerisinde dalgalanıyor)"

    return result


def calculate_stablecoin_health_factor(
    collateral_value_usd: float,
    liquidation_threshold: float,
    borrowed_amount_usd: float
) -> Dict[str, Any]:
    """Calculates health factor and liquidation risk for over-collateralized stablecoins / lending protocols:
    Health Factor = (Collateral Value * Liquidation Threshold) / Borrowed Amount
    Collateral Ratio = (Collateral Value / Borrowed Amount) * 100
    """
    if collateral_value_usd < 0:
        return {"error": "Collateral value cannot be negative"}
    if borrowed_amount_usd <= 0:
        return {"error": "Borrowed amount must be strictly positive"}
    if not (0.0 < liquidation_threshold <= 1.0):
        return {"error": "Liquidation threshold must be between 0 and 1.0 (e.g. 0.80 for 80%)"}

    health_factor = (collateral_value_usd * liquidation_threshold) / borrowed_amount_usd
    collateral_ratio = (collateral_value_usd / borrowed_amount_usd) * 100.0
    liquidation_price_ratio = (borrowed_amount_usd / liquidation_threshold) / collateral_value_usd if collateral_value_usd > 0 else 0.0

    return {
        "collateral_value_usd": round(collateral_value_usd, 2),
        "borrowed_amount_usd": round(borrowed_amount_usd, 2),
        "liquidation_threshold_pct": round(liquidation_threshold * 100.0, 1),
        "collateralization_ratio_pct": round(collateral_ratio, 2),
        "health_factor": round(health_factor, 3),
        "liquidation_risk_status": (
            "TASFİYE / DE-PEG RİSKİ (Health Factor < 1.0: Botlar tasfiye tetikleyebilir!)"
            if health_factor < 1.0
            else "KRİTİK UYARI (1.0 <= HF < 1.20: Teminat tamamlama çağrısı eşiğinde)"
            if health_factor < 1.20
            else "SAĞLIKLI / GÜVENLİ (HF >= 1.20: Yeterli teminat koruması mevcut)"
        )
    }


def main():
    parser = argparse.ArgumentParser(description="Macro Taylor Rule, TIPS Breakeven, Miller-Orr & Stablecoin Analytics")
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # Taylor Rule
    p_taylor = subparsers.add_parser("taylor", help="Calculate Taylor Rule policy rate")
    p_taylor.add_argument("--neutral", type=float, required=True, help="Neutral real interest rate (r*) in % (e.g. 2.0)")
    p_taylor.add_argument("--inflation", type=float, required=True, help="Current inflation rate in % (e.g. 5.5)")
    p_taylor.add_argument("--target", type=float, default=2.0, help="Target inflation rate in % (default: 2.0)")
    p_taylor.add_argument("--output-gap", type=float, default=0.0, help="Output gap in % (e.g. 1.0)")
    p_taylor.add_argument("--actual-rate", type=float, default=None, help="Actual central bank policy rate in %")

    # TIPS Breakeven
    p_tips = subparsers.add_parser("tips", help="Calculate TIPS Breakeven Inflation Rate")
    p_tips.add_argument("--nominal", type=float, required=True, help="Nominal Treasury yield in % (e.g. 4.30)")
    p_tips.add_argument("--real", type=float, required=True, help="TIPS real yield in % (e.g. 1.95)")

    # Miller-Orr
    p_miller = subparsers.add_parser("miller-orr", help="Calculate Miller-Orr optimal cash bounds")
    p_miller.add_argument("--cost", type=float, required=True, help="Fixed transaction cost per trade (F)")
    p_miller.add_argument("--variance", type=float, required=True, help="Daily cash flow variance (sigma^2)")
    p_miller.add_argument("--rate", type=float, required=True, help="Daily interest rate opportunity cost (r)")
    p_miller.add_argument("--lower", type=float, default=0.0, help="Lower safety cash bound (L)")
    p_miller.add_argument("--current", type=float, default=None, help="Current cash balance")

    # Stablecoin Health Factor
    p_stable = subparsers.add_parser("stablecoin", help="Calculate Stablecoin / Lending Health Factor")
    p_stable.add_argument("--collateral", type=float, required=True, help="Total collateral value in USD")
    p_stable.add_argument("--threshold", type=float, default=0.80, help="Liquidation threshold (e.g. 0.80 for 80%)")
    p_stable.add_argument("--borrowed", type=float, required=True, help="Total borrowed stablecoin amount in USD")

    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    res = {}
    if args.command == "taylor":
        res = calculate_taylor_rule_rate(args.neutral, args.inflation, args.target, args.output_gap, args.actual_rate)
    elif args.command == "tips":
        res = calculate_breakeven_inflation(args.nominal, args.real)
    elif args.command == "miller-orr":
        res = calculate_miller_orr_bounds(args.cost, args.variance, args.rate, args.lower, args.current)
    elif args.command == "stablecoin":
        res = calculate_stablecoin_health_factor(args.collateral, args.threshold, args.borrowed)
    else:
        parser.print_help()
        return

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print("\n=== ANALİTİK RAPORU ===")
        for k, v in res.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
