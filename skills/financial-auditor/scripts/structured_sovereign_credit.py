#!/usr/bin/env python3
"""CLI and library utility for Structured Credit, Sovereign Debt, and Algorithmic Market Making:
- CDS Implied Probability of Default (Hazard Rate)
- Avellaneda-Stoikov HFT Market Making Reservation Price
- Sovereign Debt Snowball Effect & Required Primary Balance
- CLO Overcollateralization (OC) Test Ratio
"""

import argparse
import json
from typing import Dict, Any


def calculate_cds_implied_default_prob(
    cds_spread_bps: float,
    recovery_rate_pct: float = 40.0
) -> Dict[str, Any]:
    """Calculates annual implied probability of default (Hazard Rate) from CDS spread.
    Spread (decimal) ~= PD * (1 - Recovery)  ==>  PD = (Spread_bps / 10000) / (1 - R).
    """
    r_decimal = recovery_rate_pct / 100.0
    if r_decimal >= 1.0 or cds_spread_bps < 0:
        return {"error": "Recovery rate must be less than 100% and CDS spread non-negative"}

    spread_decimal = cds_spread_bps / 10000.0
    implied_pd_decimal = spread_decimal / (1.0 - r_decimal)
    implied_pd_pct = implied_pd_decimal * 100

    return {
        "cds_spread_bps": round(cds_spread_bps, 2),
        "recovery_rate_pct": round(recovery_rate_pct, 2),
        "implied_annual_default_prob_pct": round(implied_pd_pct, 3),
        "5yr_cumulative_survival_prob_pct": round(((1.0 - implied_pd_decimal) ** 5) * 100, 2),
        "credit_risk_tier": (
            "Yüksek Temerrüt / İflas Riski (PD >= %10)" if implied_pd_pct >= 10.0
            else "Orta / Spekülatif Kredi Riski (%3 - %10)" if implied_pd_pct >= 3.0
            else "Düşük Temerrüt Riski / Yatırım Yapılabilir (< %3)"
        )
    }


def calculate_avellaneda_stoikov_reservation_price(
    mid_price: float,
    inventory_q: float,
    risk_aversion_gamma: float = 0.1,
    volatility_sigma: float = 0.02,
    time_to_close: float = 1.0
) -> Dict[str, Any]:
    """Calculates Avellaneda-Stoikov reservation price: r(s, q, t) = s - q * gamma * sigma^2 * (T - t)."""
    if mid_price <= 0:
        return {"error": "Mid price must be positive"}

    skew = inventory_q * risk_aversion_gamma * (volatility_sigma ** 2) * time_to_close
    reservation_price = mid_price - skew

    return {
        "mid_price": round(mid_price, 4),
        "inventory_q": inventory_q,
        "inventory_skew": round(skew, 5),
        "reservation_price": round(reservation_price, 4),
        "quoting_bias": (
            "Fiyat Aşağı Kaydırıldı (Daha Fazla Mal Almaktan Kaçın, Satışı Yakınlaştır)" if inventory_q > 0
            else "Fiyat Yukarı Kaydırıldı (Açığı Kapatmak İçin Alışı Yakınlaştır)" if inventory_q < 0
            else "Dengeli Kotasyon (Envanter Nötr)"
        )
    }


def calculate_sovereign_snowball_primary_balance(
    real_interest_rate_pct: float,
    real_gdp_growth_pct: float,
    debt_to_gdp_pct: float
) -> Dict[str, Any]:
    """Calculates the Required Primary Balance to GDP (pb*) to stabilize the Debt-to-GDP ratio:
    pb* = ((r - g) / (1 + g)) * d.
    """
    r = real_interest_rate_pct / 100.0
    g = real_gdp_growth_pct / 100.0
    d = debt_to_gdp_pct / 100.0

    if (1.0 + g) == 0:
        return {"error": "Growth rate cannot be -100%"}

    snowball_factor = (r - g) / (1.0 + g)
    required_primary_balance_decimal = snowball_factor * d
    required_primary_balance_pct = required_primary_balance_decimal * 100

    is_snowballing = r > g

    return {
        "real_interest_rate_pct": round(real_interest_rate_pct, 2),
        "real_gdp_growth_pct": round(real_gdp_growth_pct, 2),
        "interest_growth_differential_pct": round((real_interest_rate_pct - real_gdp_growth_pct), 2),
        "debt_to_gdp_pct": round(debt_to_gdp_pct, 2),
        "required_primary_surplus_pct_to_stabilize": round(required_primary_balance_pct, 2),
        "dynamics_regime": (
            "Kartopu Etkisi Aktif (r > g: Borcu Sabit Tutmak İçin Zorunlu Faiz Dışı Fazla Gerekir)" if is_snowballing
            else "Büyüme Borcu Eritiyor (g > r: Ülke Faiz Dışı Açık Verse Bile Borç/GSYİH Düşer)"
        )
    }


def calculate_clo_overcollateralization_test(
    collateral_par_value: float,
    senior_debt_outstanding: float,
    required_oc_threshold_pct: float = 120.0
) -> Dict[str, Any]:
    """Calculates CLO Overcollateralization (OC) test ratio = Collateral Par / Senior Debt."""
    if senior_debt_outstanding <= 0:
        return {"error": "Senior debt must be positive"}

    actual_oc_pct = (collateral_par_value / senior_debt_outstanding) * 100
    test_passed = actual_oc_pct >= required_oc_threshold_pct

    return {
        "collateral_par_value": round(collateral_par_value, 2),
        "senior_debt_outstanding": round(senior_debt_outstanding, 2),
        "actual_oc_ratio_pct": round(actual_oc_pct, 2),
        "required_oc_threshold_pct": round(required_oc_threshold_pct, 2),
        "test_passed": test_passed,
        "waterfall_status": (
            "TEST BAŞARILI (Nakit akışı alt dilimlere ve özkaynağa akmaya devam eder)" if test_passed
            else "TEST BAŞARISIZ (Özkaynak ve alt dilim ödemeleri durdurulur, nakit kıdemli anaparaya yönlendirilir!)"
        )
    }


def main():
    parser = argparse.ArgumentParser(description="Structured Credit, Sovereign Debt & HFT Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # CDS
    cds_p = subparsers.add_parser("cds")
    cds_p.add_argument("--spread", type=float, required=True, help="CDS spread in bps (e.g. 350)")
    cds_p.add_argument("--recovery", type=float, default=40.0, help="Expected recovery rate % (default 40)")

    # Avellaneda
    as_p = subparsers.add_parser("avellaneda")
    as_p.add_argument("--mid", type=float, required=True, help="Current mid price")
    as_p.add_argument("--q", type=float, required=True, help="Current inventory position")
    as_p.add_argument("--gamma", type=float, default=0.1, help="Risk aversion parameter")
    as_p.add_argument("--sigma", type=float, default=0.02, help="Asset volatility")
    as_p.add_argument("--time", type=float, default=1.0, help="Time remaining (normalized)")

    # Sovereign
    sov_p = subparsers.add_parser("sovereign")
    sov_p.add_argument("--r", type=float, required=True, help="Real interest rate %")
    sov_p.add_argument("--g", type=float, required=True, help="Real GDP growth %")
    sov_p.add_argument("--debt", type=float, required=True, help="Debt to GDP %")

    # CLO
    clo_p = subparsers.add_parser("clo")
    clo_p.add_argument("--collateral", type=float, required=True, help="Collateral par value")
    clo_p.add_argument("--debt", type=float, required=True, help="Senior debt outstanding")
    clo_p.add_argument("--threshold", type=float, default=120.0, help="Required OC threshold %")

    args = parser.parse_args()

    if args.command == "cds":
        res = calculate_cds_implied_default_prob(args.spread, args.recovery)
    elif args.command == "avellaneda":
        res = calculate_avellaneda_stoikov_reservation_price(args.mid, args.q, args.gamma, args.sigma, args.time)
    elif args.command == "sovereign":
        res = calculate_sovereign_snowball_primary_balance(args.r, args.g, args.debt)
    elif args.command == "clo":
        res = calculate_clo_overcollateralization_test(args.collateral, args.debt, args.threshold)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
