#!/usr/bin/env python3
"""CLI and library utility for Quantitative Alpha, Volatility Arbitrage and Crash Analytics:
- Grinold's Fundamental Law of Active Management (IR = IC * sqrt(N))
- Volatility Risk Premium (VRP) & Variance Swap Payout
- Private Equity Dividend Recapitalization Leverage & Return
- Circuit Breaker LULD / VBTS Distance & Thresholds
"""

import argparse
import json
import math
from typing import Dict, Any


def calculate_grinold_ir(
    information_coefficient: float,
    breadth_n: float
) -> Dict[str, Any]:
    """Calculates Information Ratio (IR) using Grinold's Fundamental Law: IR = IC * sqrt(N)."""
    if breadth_n <= 0:
        return {"error": "Breadth (number of independent bets) must be positive"}

    ir = information_coefficient * math.sqrt(breadth_n)

    return {
        "information_coefficient_ic": round(information_coefficient, 4),
        "breadth_n_bets": round(breadth_n, 1),
        "information_ratio_ir": round(ir, 3),
        "performance_verdict": (
            "EFSANEVİ / MEDALLION DÜZEYİ (IR >= 2.0: Olağanüstü Kantitatif Alfa)" if ir >= 2.0
            else "ÜST DÜZEY HEDGE FON (1.0 <= IR < 2.0: Çok Güçlü Performans)" if ir >= 1.0
            else "İYİ / REKABETÇİ (0.5 <= IR < 1.0)" if ir >= 0.5
            else "ZAYIF / GELENEKSEL (IR < 0.5: Yetersiz Genişlik veya Zayıf Sinyal)"
        )
    }


def calculate_vrp_variance_swap_payout(
    implied_vol_pct: float,
    realized_vol_pct: float,
    vega_notional: float = 10000.0
) -> Dict[str, Any]:
    """Calculates Volatility Risk Premium (VRP = IV - RV) and Variance Swap Payout for a Variance Seller.
    Variance Strike = IV^2, Realized Variance = RV^2.
    Variance Notional = Vega Notional / (2 * IV).
    Payout = (Strike Variance - Realized Variance) * Variance Notional.
    """
    if implied_vol_pct <= 0 or realized_vol_pct < 0:
        return {"error": "Implied volatility must be positive"}

    vrp_spread = implied_vol_pct - realized_vol_pct
    strike_var = (implied_vol_pct / 100.0) ** 2
    realized_var = (realized_vol_pct / 100.0) ** 2

    # Standard market variance notional: Vega Notional / (2 * IV_strike)
    variance_notional = vega_notional / (2.0 * (implied_vol_pct / 100.0))
    payout = (strike_var - realized_var) * variance_notional

    return {
        "implied_vol_pct": round(implied_vol_pct, 2),
        "realized_vol_pct": round(realized_vol_pct, 2),
        "volatility_risk_premium_pct": round(vrp_spread, 2),
        "variance_strike": round(strike_var, 6),
        "realized_variance": round(realized_var, 6),
        "variance_seller_payout": round(payout, 2),
        "arbitrage_status": (
            "POZİTİF VRP HASADI (Varyans Satıcısı Kârda: IV > RV)" if vrp_spread > 0
            else "VOLATİLİTE ŞOKU / ZARAR (Gerçekleşen Oynaklık İma Edileni Aştı: RV >= IV)"
        )
    }


def calculate_dividend_recap_impact(
    ebitda: float,
    existing_debt: float,
    new_debt_raised: float,
    pe_sponsor_equity: float,
    cash_dividend_distributed: float
) -> Dict[str, Any]:
    """Calculates the impact of a Private Equity Dividend Recapitalization:
    New Leverage (Net Debt / EBITDA) and Cash-on-Cash Return on Initial Equity.
    """
    if ebitda <= 0 or pe_sponsor_equity <= 0:
        return {"error": "EBITDA and PE sponsor equity must be positive"}

    total_debt_post_recap = existing_debt + new_debt_raised
    post_recap_leverage = total_debt_post_recap / ebitda
    cash_returned_pct = (cash_dividend_distributed / pe_sponsor_equity) * 100
    de_risked = cash_returned_pct >= 100.0

    return {
        "ebitda": round(ebitda, 2),
        "total_debt_post_recap": round(total_debt_post_recap, 2),
        "post_recap_leverage_ratio": round(post_recap_leverage, 2),
        "cash_returned_to_sponsor_pct": round(cash_returned_pct, 2),
        "sponsor_risk_status": (
            "TAM RİSKSİZLEŞTİRME (Ana Para %100 Çıkarıldı - Sonsuz IRR Potansiyeli)" if de_risked
            else f"Kısmi Risk Azaltımı (%{round(cash_returned_pct, 1)} Geri Döndü)"
        ),
        "company_distress_alert": (
            "KRİTİK İFLAS / TEMERRÜT RİSKİ (Borç / FAVÖK >= 5.0x)" if post_recap_leverage >= 5.0
            else "Kabul Edilebilir Kaldıraç (< 5.0x)"
        )
    }


def calculate_circuit_breaker_distance(
    current_price: float,
    base_price: float,
    limit_band_pct: float = 10.0
) -> Dict[str, Any]:
    """Calculates Upper / Lower Limit Circuit Breaker (LULD / BIST VBTS) thresholds and distances."""
    if base_price <= 0:
        return {"error": "Base price must be positive"}

    upper_limit = base_price * (1.0 + (limit_band_pct / 100.0))
    lower_limit = base_price * (1.0 - (limit_band_pct / 100.0))

    distance_to_upper_pct = ((upper_limit - current_price) / current_price) * 100
    distance_to_lower_pct = ((current_price - lower_limit) / current_price) * 100

    halt_imminent = distance_to_upper_pct <= 1.0 or distance_to_lower_pct <= 1.0

    return {
        "current_price": round(current_price, 2),
        "base_price": round(base_price, 2),
        "upper_limit": round(upper_limit, 2),
        "lower_limit": round(lower_limit, 2),
        "distance_to_upper_pct": round(distance_to_upper_pct, 2),
        "distance_to_lower_pct": round(distance_to_lower_pct, 2),
        "circuit_breaker_alert": halt_imminent,
        "status": (
            "DEVRE KESİCİ YAKIN / LİMİTE DAYANDI (Halt Eşiği < %1.0)" if halt_imminent
            else "Güvenli İşlem Bandı"
        )
    }


def main():
    parser = argparse.ArgumentParser(description="Alpha, Volatility & Crash Analytics Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Grinold
    g_parser = subparsers.add_parser("grinold")
    g_parser.add_argument("--ic", type=float, required=True, help="Information Coefficient (e.g. 0.05)")
    g_parser.add_argument("--breadth", type=float, required=True, help="Breadth N (independent bets)")

    # VRP
    vrp_parser = subparsers.add_parser("vrp")
    vrp_parser.add_argument("--iv", type=float, required=True, help="Implied Volatility %")
    vrp_parser.add_argument("--rv", type=float, required=True, help="Realized Volatility %")
    vrp_parser.add_argument("--vega", type=float, default=10000.0, help="Vega Notional amount")

    # Dividend Recap
    recap_parser = subparsers.add_parser("recap")
    recap_parser.add_argument("--ebitda", type=float, required=True, help="Annual EBITDA")
    recap_parser.add_argument("--debt", type=float, required=True, help="Existing debt")
    recap_parser.add_argument("--new-debt", type=float, required=True, help="New debt raised")
    recap_parser.add_argument("--equity", type=float, required=True, help="Initial PE sponsor equity")
    recap_parser.add_argument("--dividend", type=float, required=True, help="Special dividend distributed")

    # Circuit Breaker
    cb_parser = subparsers.add_parser("circuit")
    cb_parser.add_argument("--price", type=float, required=True, help="Current price")
    cb_parser.add_argument("--base", type=float, required=True, help="Session base price")
    cb_parser.add_argument("--band", type=float, default=10.0, help="Band % (default 10%)")

    args = parser.parse_args()

    if args.command == "grinold":
        res = calculate_grinold_ir(args.ic, args.breadth)
    elif args.command == "vrp":
        res = calculate_vrp_variance_swap_payout(args.iv, args.rv, args.vega)
    elif args.command == "recap":
        res = calculate_dividend_recap_impact(args.ebitda, args.debt, args.new_debt, args.equity, args.dividend)
    elif args.command == "circuit":
        res = calculate_circuit_breaker_distance(args.price, args.base, args.band)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
