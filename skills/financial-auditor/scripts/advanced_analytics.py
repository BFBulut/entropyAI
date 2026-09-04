#!/usr/bin/env python3
"""CLI and library utility for advanced financial analytics:
- Altman Z-Score (Bankruptcy Risk)
- Beneish M-Score (Earnings Manipulation Risk)
- Reverse DCF (Implied Growth Expectations)
- Fractional Kelly Criterion (Position Sizing)
"""

import argparse
import json
import math
from typing import Dict, Any


def calculate_altman_z_score(
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    market_cap: float,
    total_liabilities: float,
    revenue: float,
    total_assets: float
) -> Dict[str, Any]:
    """Calculates Altman Z-Score for public manufacturing / corporate firms.
    Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 0.999*X5
    """
    if total_assets <= 0 or total_liabilities <= 0:
        return {"error": "Total assets and liabilities must be greater than zero"}

    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = market_cap / total_liabilities
    x5 = revenue / total_assets

    z_score = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 0.999 * x5

    if z_score < 1.81:
        zone = "Tehlike Bölgesi (Distress Zone - Yüksek İflas Riski)"
        risk_level = "HIGH"
    elif z_score <= 2.99:
        zone = "Gri Bölge (Grey Zone - Finansal Baskı / İzleme Gerekli)"
        risk_level = "MEDIUM"
    else:
        zone = "Güvenli Bölge (Safe Zone - Düşük İflas Riski)"
        risk_level = "LOW"

    return {
        "z_score": round(z_score, 3),
        "zone": zone,
        "risk_level": risk_level,
        "components": {
            "x1_liquidity": round(x1, 3),
            "x2_reinvested_profit": round(x2, 3),
            "x3_operating_efficiency": round(x3, 3),
            "x4_market_leverage": round(x4, 3),
            "x5_asset_turnover": round(x5, 3)
        }
    }


def calculate_beneish_m_score(
    dsri: float = 1.0,
    gmi: float = 1.0,
    aqi: float = 1.0,
    sgi: float = 1.0,
    depi: float = 1.0,
    sgai: float = 1.0,
    tata: float = 0.0,
    lvgi: float = 1.0
) -> Dict[str, Any]:
    """Calculates Beneish M-Score to detect financial statement manipulation.
    M-Score = -4.84 + 0.920*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI + 0.115*DEPI - 0.172*SGAI + 4.037*TATA + 0.0327*LVGI
    Threshold: M > -1.78 suggests high probability of manipulation.
    """
    m_score = (
        -4.84
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.037 * tata
        + 0.0327 * lvgi
    )

    is_manipulator_likely = m_score > -1.78

    return {
        "m_score": round(m_score, 3),
        "manipulation_risk": "YÜKSEK (Kırmızı Bayrak)" if is_manipulator_likely else "DÜŞÜK (Olağan)",
        "threshold": -1.78,
        "flag_triggered": is_manipulator_likely
    }


def calculate_reverse_dcf(
    current_market_cap: float,
    current_fcf: float,
    wacc: float = 0.10,
    terminal_growth: float = 0.025,
    projection_years: int = 10
) -> Dict[str, Any]:
    """Solves for the implied annual Free Cash Flow growth rate embedded in current market price.
    Uses binary search over growth rate g.
    """
    if current_fcf <= 0 or current_market_cap <= 0:
        return {"error": "Current FCF and Market Cap must be positive for DCF inversion"}

    def enterprise_value(g: float) -> float:
        pv = 0.0
        cf = current_fcf
        for t in range(1, projection_years + 1):
            cf = cf * (1.0 + g)
            pv += cf / ((1.0 + wacc) ** t)
        
        terminal_fcf = cf * (1.0 + terminal_growth)
        if wacc <= terminal_growth:
            return float("inf")
        tv = terminal_fcf / (wacc - terminal_growth)
        pv_tv = tv / ((1.0 + wacc) ** projection_years)
        return pv + pv_tv

    low = -0.50
    high = 1.00
    implied_g = 0.0

    for _ in range(50):
        mid = (low + high) / 2.0
        val = enterprise_value(mid)
        if val > current_market_cap:
            high = mid
        else:
            low = mid
        implied_g = mid

    return {
        "implied_annual_fcf_growth_pct": round(implied_g * 100, 2),
        "wacc_pct": round(wacc * 100, 2),
        "terminal_growth_pct": round(terminal_growth * 100, 2),
        "evaluation": (
            "Aşırı Yüksek Beklenti (Fiyat balonu riski)" if implied_g > 0.25
            else "Sağlıklı / Gerçekçi Büyüme Beklentisi" if implied_g >= 0.05
            else "Piyasa Kriz / Düşük Büyüme Fiyatlıyor (Potansiyel Değer Fırsatı)"
        )
    }


def calculate_fractional_kelly(
    win_rate: float,
    risk_reward_ratio: float,
    fraction: float = 0.5
) -> Dict[str, Any]:
    """Calculates Fractional Kelly Criterion for optimal position sizing.
    Kelly: f* = (p * b - q) / b
    where p = win_rate, q = 1 - p, b = risk_reward_ratio.
    """
    if win_rate <= 0 or win_rate >= 1.0 or risk_reward_ratio <= 0:
        return {"error": "Invalid probability or risk-reward parameters"}

    q = 1.0 - win_rate
    full_kelly = (win_rate * risk_reward_ratio - q) / risk_reward_ratio
    optimal_allocation = max(0.0, full_kelly * fraction)

    return {
        "full_kelly_pct": round(full_kelly * 100, 2),
        "recommended_allocation_pct": round(optimal_allocation * 100, 2),
        "fraction_used": fraction,
        "edge": "Pozitif Beklenti (Edge Var)" if full_kelly > 0 else "Negatif Beklenti (Pozisyon Alınmamalı)"
    }


def main():
    parser = argparse.ArgumentParser(description="Advanced Financial Analytics Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Altman Z
    z_parser = subparsers.add_parser("altman-z")
    z_parser.add_argument("--wc", type=float, required=True, help="Working Capital")
    z_parser.add_argument("--re", type=float, required=True, help="Retained Earnings")
    z_parser.add_argument("--ebit", type=float, required=True, help="EBIT")
    z_parser.add_argument("--mc", type=float, required=True, help="Market Cap")
    z_parser.add_argument("--tl", type=float, required=True, help="Total Liabilities")
    z_parser.add_argument("--rev", type=float, required=True, help="Revenue")
    z_parser.add_argument("--ta", type=float, required=True, help="Total Assets")

    # Beneish M
    m_parser = subparsers.add_parser("beneish-m")
    m_parser.add_argument("--dsri", type=float, default=1.0)
    m_parser.add_argument("--gmi", type=float, default=1.0)
    m_parser.add_argument("--aqi", type=float, default=1.0)
    m_parser.add_argument("--sgi", type=float, default=1.0)
    m_parser.add_argument("--depi", type=float, default=1.0)
    m_parser.add_argument("--sgai", type=float, default=1.0)
    m_parser.add_argument("--tata", type=float, default=0.0)
    m_parser.add_argument("--lvgi", type=float, default=1.0)

    # Reverse DCF
    rdcf_parser = subparsers.add_parser("reverse-dcf")
    rdcf_parser.add_argument("--mc", type=float, required=True, help="Current Market Cap")
    rdcf_parser.add_argument("--fcf", type=float, required=True, help="Current FCF")
    rdcf_parser.add_argument("--wacc", type=float, default=0.10, help="WACC discount rate (e.g. 0.10)")
    rdcf_parser.add_argument("--tg", type=float, default=0.025, help="Terminal growth (e.g. 0.025)")

    # Kelly
    k_parser = subparsers.add_parser("kelly")
    k_parser.add_argument("--win-rate", type=float, required=True, help="Win rate (0.0 to 1.0)")
    k_parser.add_argument("--rr", type=float, required=True, help="Risk / Reward ratio (e.g. 2.0)")
    k_parser.add_argument("--fraction", type=float, default=0.5, help="Fractional multiplier (0.5 for Half Kelly)")

    args = parser.parse_args()

    if args.command == "altman-z":
        res = calculate_altman_z_score(args.wc, args.re, args.ebit, args.mc, args.tl, args.rev, args.ta)
    elif args.command == "beneish-m":
        res = calculate_beneish_m_score(args.dsri, args.gmi, args.aqi, args.sgi, args.depi, args.sgai, args.tata, args.lvgi)
    elif args.command == "reverse-dcf":
        res = calculate_reverse_dcf(args.mc, args.fcf, args.wacc, args.tg)
    elif args.command == "kelly":
        res = calculate_fractional_kelly(args.win_rate, args.rr, args.fraction)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
