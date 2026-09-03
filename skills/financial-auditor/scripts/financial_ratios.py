#!/usr/bin/env python3
"""CLI utility to calculate standard corporate financial ratios."""

import argparse
import json

def calculate_ratios(current_assets, current_liab, net_income, revenue, equity, total_debt=0):
    current_ratio = (current_assets / current_liab) if current_liab else 0
    net_margin = (net_income / revenue) * 100 if revenue else 0
    roe = (net_income / equity) * 100 if equity else 0
    debt_to_equity = (total_debt / equity) if equity else 0

    return {
        "current_ratio": round(current_ratio, 2),
        "liquidity_status": "Güçlü" if current_ratio >= 1.5 else "Kritik / Düşük" if current_ratio < 1.0 else "Yeterli",
        "net_profit_margin_pct": round(net_margin, 2),
        "return_on_equity_roe_pct": round(roe, 2),
        "debt_to_equity": round(debt_to_equity, 2)
    }

def main():
    parser = argparse.ArgumentParser(description="Calculate financial ratios")
    parser.add_argument("--current-assets", type=float, default=0)
    parser.add_argument("--current-liab", type=float, default=0)
    parser.add_argument("--net-income", type=float, default=0)
    parser.add_argument("--revenue", type=float, default=0)
    parser.add_argument("--equity", type=float, default=0)
    parser.add_argument("--total-debt", type=float, default=0)
    args = parser.parse_args()

    ratios = calculate_ratios(
        args.current_assets, args.current_liab,
        args.net_income, args.revenue,
        args.equity, args.total_debt
    )
    print(json.dumps(ratios, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
