#!/usr/bin/env python3
"""CLI and library utility for Money Markets, Short Squeeze, VC Dilution and AMM Liquidity:
- Short Squeeze Risk (Short Float %, Days-to-Cover, Borrow Fee)
- VC Dilution & Post-Money Cap Table
- AMM Impermanent Loss (Uniswap x*y=k)
- Central Bank AOFM (Weighted Average Cost of Funding)
"""

import argparse
import json
import math
from typing import Dict, Any, List


def calculate_short_squeeze_risk(
    short_interest_shares: float,
    float_shares: float,
    avg_daily_volume: float,
    borrow_fee_pct: float = 5.0
) -> Dict[str, Any]:
    """Calculates Short Squeeze risk metrics: Short Float %, Days-to-Cover (SIR), and Alert Level."""
    if float_shares <= 0 or avg_daily_volume <= 0:
        return {"error": "Float shares and average daily volume must be positive"}

    short_float_pct = (short_interest_shares / float_shares) * 100
    days_to_cover = short_interest_shares / avg_daily_volume

    is_extreme = short_float_pct >= 20.0 and days_to_cover >= 5.0
    is_high = short_float_pct >= 15.0 or days_to_cover >= 4.0 or borrow_fee_pct >= 20.0

    risk_verdict = (
        "EKSTREM SHORT SQUEEZE RİSKİ (Tetiklenmeye Hazır Kaskad)" if is_extreme
        else "YÜKSEK SQUEEZE RİSKİ (Sıkışma Potansiyeli Mevcut)" if is_high
        else "DÜŞÜK / NORMAL (Olağan Açığa Satış Düzeyi)"
    )

    return {
        "short_interest_shares": short_interest_shares,
        "float_shares": float_shares,
        "short_float_pct": round(short_float_pct, 2),
        "days_to_cover": round(days_to_cover, 2),
        "borrow_fee_pct": round(borrow_fee_pct, 2),
        "risk_verdict": risk_verdict,
        "squeeze_alert": is_extreme or is_high
    }


def calculate_vc_dilution(
    pre_money_valuation: float,
    investment_amount: float,
    existing_shares: float,
    option_pool_pct: float = 0.0
) -> Dict[str, Any]:
    """Calculates VC Post-Money Valuation, Share Price, Investor Equity %, and Founder Dilution."""
    if pre_money_valuation <= 0 or investment_amount <= 0 or existing_shares <= 0:
        return {"error": "Valuation, investment amount, and existing shares must be positive"}

    post_money_valuation = pre_money_valuation + investment_amount
    investor_equity_pct = (investment_amount / post_money_valuation) * 100
    
    # Effective pre-money adjusted for option pool if unallocated
    share_price = pre_money_valuation / existing_shares
    new_shares_issued = investment_amount / share_price
    total_post_shares = existing_shares + new_shares_issued

    founder_retention_pct = (existing_shares / total_post_shares) * 100

    return {
        "pre_money_valuation": round(pre_money_valuation, 2),
        "investment_amount": round(investment_amount, 2),
        "post_money_valuation": round(post_money_valuation, 2),
        "investor_equity_pct": round(investor_equity_pct, 2),
        "founder_retained_equity_pct": round(founder_retention_pct, 2),
        "effective_share_price": round(share_price, 3),
        "new_shares_issued": round(new_shares_issued, 2),
        "total_post_shares": round(total_post_shares, 2)
    }


def calculate_impermanent_loss(price_ratio_k: float) -> Dict[str, Any]:
    """Calculates AMM Impermanent Loss percentage when asset price changes by ratio k (P_new / P_old).
    IL = (2 * sqrt(k) / (1 + k)) - 1
    """
    if price_ratio_k <= 0:
        return {"error": "Price ratio must be positive"}

    il_decimal = (2.0 * math.sqrt(price_ratio_k) / (1.0 + price_ratio_k)) - 1.0
    il_pct = il_decimal * 100

    return {
        "price_ratio_k": round(price_ratio_k, 3),
        "price_change_pct": round((price_ratio_k - 1.0) * 100, 2),
        "impermanent_loss_pct": round(il_pct, 2),
        "impermanent_loss_decimal": round(il_decimal, 4),
        "breakeven_fee_yield_needed_pct": round(abs(il_pct), 2)
    }


def calculate_aofm(funding_buckets: List[Dict[str, float]]) -> Dict[str, Any]:
    """Calculates Central Bank Weighted Average Cost of Funding (AOFM).
    Buckets: [{'amount': volume, 'rate': interest_rate_pct}]
    """
    total_amount = sum(b["amount"] for b in funding_buckets)
    if total_amount <= 0:
        return {"error": "Total funding amount must be positive"}

    weighted_rate_sum = sum(b["amount"] * b["rate"] for b in funding_buckets)
    aofm = weighted_rate_sum / total_amount

    return {
        "total_funding_volume": round(total_amount, 2),
        "aofm_rate_pct": round(aofm, 3),
        "bucket_count": len(funding_buckets)
    }


def main():
    parser = argparse.ArgumentParser(description="Money Markets, Short Squeeze & VC Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Short Squeeze
    sq_p = subparsers.add_parser("squeeze")
    sq_p.add_argument("--short-shares", type=float, required=True, help="Total shorted shares")
    sq_p.add_argument("--float", type=float, required=True, help="Public float shares")
    sq_p.add_argument("--adv", type=float, required=True, help="Average daily volume")
    sq_p.add_argument("--borrow-fee", type=float, default=5.0, help="Annual borrow fee %")

    # VC Dilution
    vc_p = subparsers.add_parser("vc")
    vc_p.add_argument("--pre", type=float, required=True, help="Pre-money valuation")
    vc_p.add_argument("--invest", type=float, required=True, help="Investment amount")
    vc_p.add_argument("--shares", type=float, required=True, help="Existing shares")

    # Impermanent Loss
    il_p = subparsers.add_parser("il")
    il_p.add_argument("--ratio", type=float, required=True, help="Price change ratio k = P_new / P_old (e.g. 1.5 for +50%, 2.0 for +100%)")

    # AOFM
    aofm_p = subparsers.add_parser("aofm")
    aofm_p.add_argument("--data", type=str, required=True, help="JSON list of buckets: '[{\"amount\": 100, \"rate\": 45.0}, {\"amount\": 50, \"rate\": 47.0}]'")

    args = parser.parse_args()

    if args.command == "squeeze":
        res = calculate_short_squeeze_risk(args.short_shares, getattr(args, "float"), args.adv, args.borrow_fee)
    elif args.command == "vc":
        res = calculate_vc_dilution(args.pre, args.invest, args.shares)
    elif args.command == "il":
        res = calculate_impermanent_loss(args.ratio)
    elif args.command == "aofm":
        buckets = json.loads(args.data)
        res = calculate_aofm(buckets)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
