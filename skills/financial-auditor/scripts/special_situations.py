#!/usr/bin/env python3
"""CLI and library utility for special situations, LBO, M&A and commodity analytics:
- LBO Returns (MOIC, IRR, Deleveraging impact)
- M&A Accretion / Dilution (EPS impact, Synergies)
- 3:2:1 Refinery Crack Spread
- Guidotti-Greenspan FX Reserve Adequacy
"""

import argparse
import json
import math
from typing import Dict, Any


def calculate_lbo_returns(
    entry_ev: float,
    exit_ev: float,
    initial_debt: float,
    debt_paid_down: float,
    initial_equity: float,
    holding_years: float = 5.0
) -> Dict[str, Any]:
    """Calculates Leveraged Buyout (LBO) returns: Ending Equity, MOIC, and annualized IRR."""
    if initial_equity <= 0 or holding_years <= 0:
        return {"error": "Initial equity and holding years must be positive"}

    remaining_debt = max(0.0, initial_debt - debt_paid_down)
    ending_equity = max(0.0, exit_ev - remaining_debt)

    moic = ending_equity / initial_equity
    irr_pct = ((moic ** (1.0 / holding_years)) - 1.0) * 100 if moic > 0 else -100.0

    return {
        "entry_enterprise_value": round(entry_ev, 2),
        "exit_enterprise_value": round(exit_ev, 2),
        "initial_sponsor_equity": round(initial_equity, 2),
        "ending_sponsor_equity": round(ending_equity, 2),
        "debt_paid_down": round(debt_paid_down, 2),
        "remaining_debt_at_exit": round(remaining_debt, 2),
        "moic": round(moic, 2),
        "irr_pct": round(irr_pct, 2),
        "target_met": irr_pct >= 20.0,
        "performance_verdict": "Üst Düzey PE Getirisi (IRR >= %20)" if irr_pct >= 20.0 else "Standart / Düşük Getiri"
    }


def calculate_ma_accretion_dilution(
    acquirer_share_price: float,
    acquirer_shares_out: float,
    acquirer_net_income: float,
    target_equity_value: float,
    target_net_income: float,
    after_tax_synergies: float = 0.0
) -> Dict[str, Any]:
    """Calculates all-stock M&A accretion / dilution on standalone EPS."""
    if acquirer_shares_out <= 0 or acquirer_share_price <= 0:
        return {"error": "Acquirer shares and share price must be positive"}

    standalone_eps = acquirer_net_income / acquirer_shares_out
    new_shares_issued = target_equity_value / acquirer_share_price
    pro_forma_shares = acquirer_shares_out + new_shares_issued

    combined_net_income = acquirer_net_income + target_net_income + after_tax_synergies
    pro_forma_eps = combined_net_income / pro_forma_shares

    eps_change = pro_forma_eps - standalone_eps
    eps_pct_change = (eps_change / standalone_eps) * 100 if standalone_eps > 0 else 0.0

    is_accretive = eps_pct_change > 0

    return {
        "standalone_eps": round(standalone_eps, 3),
        "pro_forma_eps": round(pro_forma_eps, 3),
        "eps_pct_change": round(eps_pct_change, 2),
        "transaction_type": "AKRETİF (Accretive - Kâr Artırıcı)" if is_accretive else "DİLÜTİF (Dilutive - Kârı Sulandıran)",
        "new_shares_issued": round(new_shares_issued, 2),
        "pro_forma_shares": round(pro_forma_shares, 2)
    }


def calculate_crack_spread(
    crude_oil_price_bbl: float,
    gasoline_price_bbl: float,
    diesel_price_bbl: float
) -> Dict[str, Any]:
    """Calculates standard 3:2:1 Oil Refinery Crack Spread per barrel.
    Crack Spread = (2 * Gasoline + 1 * Diesel - 3 * Crude) / 3
    """
    spread = ((2.0 * gasoline_price_bbl) + (1.0 * diesel_price_bbl) - (3.0 * crude_oil_price_bbl)) / 3.0

    return {
        "crack_spread_per_bbl": round(spread, 2),
        "margin_status": (
            "Çok Yüksek Rafineri Marjı (Kâr Patlaması)" if spread >= 25.0
            else "Sağlıklı / Normal Rafineri Marjı" if spread >= 12.0
            else "Düşük / Baskılanmış Marj"
        )
    }


def calculate_guidotti_greenspan(
    net_fx_reserves: float,
    short_term_external_debt: float
) -> Dict[str, Any]:
    """Calculates Guidotti-Greenspan FX Reserve Adequacy Ratio = Net FX Reserves / 1Y Short-term External Debt."""
    if short_term_external_debt <= 0:
        return {"error": "Short-term debt must be positive"}

    ratio = net_fx_reserves / short_term_external_debt

    return {
        "guidotti_greenspan_ratio": round(ratio, 2),
        "threshold": 1.0,
        "resilience_status": (
            "Güvenli Liman (Rezervler kısa vadeli borcu tam karşılıyor)" if ratio >= 1.0
            else "Kur Şoku Riski (Rezerv yetersizliği, döviz devalüasyon riski)"
        ),
        "adequacy_pct": round(ratio * 100, 1)
    }


def main():
    parser = argparse.ArgumentParser(description="Special Situations & LBO Analytics Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # LBO
    lbo_p = subparsers.add_parser("lbo")
    lbo_p.add_argument("--entry-ev", type=float, required=True)
    lbo_p.add_argument("--exit-ev", type=float, required=True)
    lbo_p.add_argument("--init-debt", type=float, required=True)
    lbo_p.add_argument("--debt-paid", type=float, required=True)
    lbo_p.add_argument("--init-equity", type=float, required=True)
    lbo_p.add_argument("--years", type=float, default=5.0)

    # M&A
    ma_p = subparsers.add_parser("ma")
    ma_p.add_argument("--acq-price", type=float, required=True)
    ma_p.add_argument("--acq-shares", type=float, required=True)
    ma_p.add_argument("--acq-ni", type=float, required=True)
    ma_p.add_argument("--tgt-val", type=float, required=True)
    ma_p.add_argument("--tgt-ni", type=float, required=True)
    ma_p.add_argument("--synergies", type=float, default=0.0)

    # Crack Spread
    crack_p = subparsers.add_parser("crack")
    crack_p.add_argument("--crude", type=float, required=True)
    crack_p.add_argument("--gas", type=float, required=True)
    crack_p.add_argument("--diesel", type=float, required=True)

    # Guidotti-Greenspan
    gg_p = subparsers.add_parser("guidotti")
    gg_p.add_argument("--reserves", type=float, required=True)
    gg_p.add_argument("--debt", type=float, required=True)

    args = parser.parse_args()

    if args.command == "lbo":
        res = calculate_lbo_returns(args.entry_ev, args.exit_ev, args.init_debt, args.debt_paid, args.init_equity, args.years)
    elif args.command == "ma":
        res = calculate_ma_accretion_dilution(args.acq_price, args.acq_shares, args.acq_ni, args.tgt_val, args.tgt_ni, args.synergies)
    elif args.command == "crack":
        res = calculate_crack_spread(args.crude, args.gas, args.diesel)
    elif args.command == "guidotti":
        res = calculate_guidotti_greenspan(args.reserves, args.debt)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
