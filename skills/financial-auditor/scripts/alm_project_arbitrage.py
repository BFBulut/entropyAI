#!/usr/bin/env python3
"""CLI and library utility for ALM, Project Finance, Merger Arbitrage and GARCH:
- ALM Duration Gap & Economic Value of Equity (EVE) Sensitivity
- Project Finance Debt Service Coverage Ratio (DSCR)
- Merger Arbitrage Implied Probability & Deal Spread
- GARCH(1,1) One-Step-Ahead Conditional Variance
"""

import argparse
import json
import math
from typing import Dict, Any


def calculate_duration_gap_eve_impact(
    total_assets: float,
    total_liabilities: float,
    asset_duration: float,
    liability_duration: float,
    yield_shock_bps: float = 100.0
) -> Dict[str, Any]:
    """Calculates ALM Duration Gap and percentage change in Economic Value of Equity (EVE).
    Duration Gap = D_A - (L / A) * D_L
    Delta E / E ~= - [Duration Gap * (A / E)] * dy
    """
    equity = total_assets - total_liabilities
    if total_assets <= 0 or equity <= 0:
        return {"error": "Total assets and equity must be positive"}

    leverage_ratio = total_liabilities / total_assets
    duration_gap = asset_duration - (leverage_ratio * liability_duration)

    dy = yield_shock_bps / 10000.0
    equity_multiplier = total_assets / equity
    pct_eve_change = -(duration_gap * equity_multiplier) * dy * 100

    return {
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "equity": round(equity, 2),
        "duration_gap_years": round(duration_gap, 2),
        "yield_shock_bps": yield_shock_bps,
        "eve_pct_change": round(pct_eve_change, 2),
        "alm_risk_tier": (
            "KRİTİK İFLAS RİSKİ (Özkaynak Erimesi > %50 - SVB Tipi Uyumsuzluk)" if abs(pct_eve_change) >= 50.0
            else "YÜKSEK FAİZ RİSKİ (%20 - %50 Erime)" if abs(pct_eve_change) >= 20.0
            else "KONTROL ALTINDA / DENGELİ ALM (< %20 Erime)"
        )
    }


def calculate_project_dscr(
    cfads: float,
    principal_repayment: float,
    interest_payment: float
) -> Dict[str, Any]:
    """Calculates Project Finance Debt Service Coverage Ratio (DSCR).
    DSCR = CFADS / (Principal + Interest)
    """
    total_debt_service = principal_repayment + interest_payment
    if total_debt_service <= 0:
        return {"error": "Total debt service must be positive"}

    dscr = cfads / total_debt_service

    return {
        "cfads": round(cfads, 2),
        "debt_service": round(total_debt_service, 2),
        "dscr": round(dscr, 2),
        "covenant_status": (
            "GÜÇLÜ (DSCR >= 1.30x: Temettü Dağıtılabilir)" if dscr >= 1.30
            else "KABUL EDİLEBİLİR (1.10x <= DSCR < 1.30x: Temettü Kısıtlanabilir)" if dscr >= 1.10
            else "SÖZLEŞME İHLALİ / COVENANT BREACH (1.00x <= DSCR < 1.10x: Nakit Süpürme - Cash Sweep)" if dscr >= 1.00
            else "TEMERRÜT (DSCR < 1.00x: Nakit Borç Servisini Karşılamıyor!)"
        )
    }


def calculate_merger_arbitrage_odds(
    spot_price: float,
    offer_price: float,
    unaffected_price: float
) -> Dict[str, Any]:
    """Calculates Merger Arbitrage Deal Spread and Market-Implied Probability of Success:
    P_success = (P_spot - P_unaffected) / (P_offer - P_unaffected).
    """
    denom = offer_price - unaffected_price
    if denom <= 0 or spot_price < unaffected_price:
        return {"error": "Offer price must be strictly greater than unaffected price"}

    deal_spread = offer_price - spot_price
    deal_spread_pct = (deal_spread / spot_price) * 100
    implied_prob = (spot_price - unaffected_price) / denom
    implied_prob_pct = implied_prob * 100

    return {
        "spot_price": round(spot_price, 2),
        "offer_price": round(offer_price, 2),
        "unaffected_price": round(unaffected_price, 2),
        "deal_spread": round(deal_spread, 2),
        "gross_arbitrage_spread_pct": round(deal_spread_pct, 2),
        "market_implied_success_prob_pct": round(implied_prob_pct, 1),
        "antitrust_risk_verdict": (
            "Yüksek Kapanma Olasılığı (P >= %90: Düşük Regülasyon Engeli)" if implied_prob_pct >= 90.0
            else "Orta Seviye / Bekleme Modu (%75 - %90)" if implied_prob_pct >= 75.0
            else "Yüksek İptal / Antitröst Riski (P < %75: Anlaşma Çökebilir)"
        )
    }


def calculate_garch_next_variance(
    omega: float,
    alpha: float,
    beta: float,
    prev_variance: float,
    prev_residual_shock: float
) -> Dict[str, Any]:
    """Calculates one-step-ahead conditional variance in GARCH(1,1):
    sigma_t^2 = omega + alpha * epsilon_{t-1}^2 + beta * sigma_{t-1}^2.
    """
    if (alpha + beta) >= 1.0:
        persistence_warning = "Durağan Olmayan Süreç (alpha + beta >= 1.0)"
    else:
        persistence_warning = "Durağan / Ortalama Varyansa Dönen Süreç"

    next_var = omega + alpha * (prev_residual_shock ** 2) + beta * prev_variance
    next_vol = math.sqrt(next_var) if next_var > 0 else 0.0

    return {
        "omega": omega,
        "alpha_shock_sensitivity": alpha,
        "beta_persistence": beta,
        "persistence_factor": round(alpha + beta, 4),
        "next_period_conditional_variance": round(next_var, 6),
        "next_period_conditional_volatility_pct": round(next_vol * 100, 2),
        "process_stability": persistence_warning
    }


def main():
    parser = argparse.ArgumentParser(description="ALM, Project Finance, M&A Arbitrage & GARCH Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ALM
    alm_p = subparsers.add_parser("alm")
    alm_p.add_argument("--assets", type=float, required=True, help="Total assets")
    alm_p.add_argument("--liab", type=float, required=True, help="Total liabilities")
    alm_p.add_argument("--da", type=float, required=True, help="Asset duration in years")
    alm_p.add_argument("--dl", type=float, required=True, help="Liability duration in years")
    alm_p.add_argument("--shock", type=float, default=100.0, help="Yield shock in basis points")

    # Project DSCR
    dscr_p = subparsers.add_parser("dscr")
    dscr_p.add_argument("--cfads", type=float, required=True, help="Cash Flow Available for Debt Service")
    dscr_p.add_argument("--principal", type=float, required=True, help="Principal due")
    dscr_p.add_argument("--interest", type=float, required=True, help="Interest due")

    # Merger Arbitrage
    arb_p = subparsers.add_parser("arbitrage")
    arb_p.add_argument("--spot", type=float, required=True, help="Spot target price")
    arb_p.add_argument("--offer", type=float, required=True, help="Acquisition offer price")
    arb_p.add_argument("--unaffected", type=float, required=True, help="Unaffected pre-deal price")

    # GARCH
    garch_p = subparsers.add_parser("garch")
    garch_p.add_argument("--omega", type=float, default=0.00001)
    garch_p.add_argument("--alpha", type=float, default=0.10)
    garch_p.add_argument("--beta", type=float, default=0.85)
    garch_p.add_argument("--var", type=float, required=True, help="Previous variance")
    garch_p.add_argument("--shock", type=float, required=True, help="Previous residual return shock")

    args = parser.parse_args()

    if args.command == "alm":
        res = calculate_duration_gap_eve_impact(args.assets, args.liab, args.da, args.dl, args.shock)
    elif args.command == "dscr":
        res = calculate_project_dscr(args.cfads, args.principal, args.interest)
    elif args.command == "arbitrage":
        res = calculate_merger_arbitrage_odds(args.spot, args.offer, args.unaffected)
    elif args.command == "garch":
        res = calculate_garch_next_variance(args.omega, args.alpha, args.beta, args.var, args.shock)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
