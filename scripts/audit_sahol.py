#!/usr/bin/env python3
"""Quantitative and Forensic Financial Audit Engine for Hacı Ömer Sabancı Holding A.Ş. (SAHOL / IS:SAHOL).
Analyzes conglomerate financials, P/B deep discount (0.46x), NAV (Net Asset Value) discount,
banking vs non-banking dynamics, Q2 2026 net income surge, and analyst consensus targets.
"""

from typing import Dict, Any


def audit_sabanci_holding() -> Dict[str, Any]:
    # 1. Base Market & Valuation Data (Sep 3, 2026)
    stock_price_try = 92.50
    market_cap_try_b = 194.30
    market_cap_try_m = 194300.0
    shares_outstanding_m = 2100.0
    range_52w_low = 72.73
    range_52w_high = 113.19
    price_pct_of_52w_high = (stock_price_try / range_52w_high) * 100.0  # 81.72%
    drawdown_from_52w_high_pct = ((range_52w_high - stock_price_try) / range_52w_high) * 100.0  # 18.28%
    premium_over_52w_low_pct = ((stock_price_try - range_52w_low) / range_52w_low) * 100.0  # 27.18%

    pe_ratio_trailing = 9.65
    pe_ratio_fwd_fy26 = 17.38
    pe_ratio_fwd_fy27 = 13.20
    peg_ratio = 0.03
    fcf_yield_reported_pct = -22.0
    book_value_per_share = 199.60
    price_to_book = stock_price_try / book_value_per_share  # 0.463x
    pb_discount_pct = (1.0 - price_to_book) * 100.0  # 53.66% discount to book value!
    beta_5y = 0.41
    dividend_yield_pct = 1.53
    dividend_streak_years = 6
    dividend_uninterrupted_years = 24
    next_earnings_date = "2026-11-11"

    fair_value_investingpro_try = 101.65
    fair_value_upside_pct = ((fair_value_investingpro_try - stock_price_try) / stock_price_try) * 100.0  # +9.89%
    analyst_consensus_target_try = 162.73
    analyst_target_low_try = 139.50
    analyst_target_high_try = 181.00
    analyst_target_upside_pct = ((analyst_consensus_target_try - stock_price_try) / stock_price_try) * 100.0  # +75.92%

    # 2. Income Statement Dynamics (TRY Million)
    revenue_ltm = 275480.0
    cogs_ltm = 8200.0
    gross_profit_ltm = 267200.0
    sga_ltm = 172300.0
    operating_profit_ltm = 90311.0
    operating_margin_pct = (operating_profit_ltm / revenue_ltm) * 100.0  # 32.78%
    income_tax_ltm = 32200.0
    net_income_ltm = 20096.0
    net_margin_ltm_pct = (net_income_ltm / revenue_ltm) * 100.0  # 7.29%
    eps_diluted_ltm = 9.70

    # Q2 2026 Quarterly Inflection
    q2_2026_revenue = 84889.0
    q2_2026_operating_profit = 31392.0
    q2_2026_net_income = 14160.0  # Massive single-quarter profit
    q2_2026_eps = 6.84
    q1_2026_net_income = 339.8
    q4_2025_net_income = 4582.0
    q3_2025_net_income = 678.8

    # 3. Balance Sheet & Capital Structure (LTM / Q2 2026, TRY Million)
    total_assets = 4653123.0  # ~4.65 Trillion TRY
    total_current_assets = 1065129.0
    total_liabilities = 3968587.0
    total_current_liabilities = 3473237.0
    total_equity = 684536.0  # ~684.5 Billion TRY
    total_debt = 1039755.0

    equity_to_assets_pct = (total_equity / total_assets) * 100.0  # 14.71% (Standard for banking conglomerates)
    debt_to_equity_pct = (total_debt / total_equity) * 100.0  # 151.89%

    # 4. Cash Flows & Working Capital (TRY Million)
    cfo_ltm = -22112.0
    cfi_ltm = -129154.0  # Large energy and US solar investments
    cff_ltm = 139367.0

    # Quarterly CFO Recovery:
    # Q3 2025 was -73,879M (one-off banking liquidity / asset allocation drag)
    # Q4 2025 was +155,444M, Q1 2026 was +7,673M, Q2 2026 was +22,991M
    cfo_last_3_quarters_sum = 155444.0 + 7673.0 + 22991.0  # +186,108M TRY positive!

    # 5. Strategic 2024-2029 Mid-Term Targets
    nav_target_usd_b = 20.0
    fx_revenue_share_target_pct = 30.0
    current_us_solar_capacity_target_mw = 500.0  # Texas 2nd solar investment

    # 6. Technical Indicator Setup from Report
    technical_summary = "Strong Buy"
    moving_averages_summary = "Buy"
    technical_indicators_summary = "Strong Buy"

    return {
        "company": "Hacı Ömer Sabancı Holding A.Ş.",
        "ticker": "IS:SAHOL",
        "market_data": {
            "stock_price_try": stock_price_try,
            "market_cap_try_b": market_cap_try_b,
            "shares_outstanding_m": shares_outstanding_m,
            "range_52w_low": range_52w_low,
            "range_52w_high": range_52w_high,
            "price_pct_of_52w_high": round(price_pct_of_52w_high, 2),
            "drawdown_from_52w_high_pct": round(drawdown_from_52w_high_pct, 2),
            "premium_over_52w_low_pct": round(premium_over_52w_low_pct, 2),
            "pe_trailing": pe_ratio_trailing,
            "pe_fwd_fy26": pe_ratio_fwd_fy26,
            "pe_fwd_fy27": pe_ratio_fwd_fy27,
            "peg_ratio": peg_ratio,
            "book_value_per_share": book_value_per_share,
            "price_to_book": round(price_to_book, 2),
            "pb_discount_pct": round(pb_discount_pct, 2),
            "beta_5y": beta_5y,
            "dividend_yield_pct": dividend_yield_pct,
            "dividend_streak_years": dividend_streak_years,
            "dividend_uninterrupted_years": dividend_uninterrupted_years,
            "fair_value_investingpro_try": fair_value_investingpro_try,
            "fair_value_upside_pct": round(fair_value_upside_pct, 2),
            "analyst_consensus_target_try": analyst_consensus_target_try,
            "analyst_target_low_try": analyst_target_low_try,
            "analyst_target_high_try": analyst_target_high_try,
            "analyst_target_upside_pct": round(analyst_target_upside_pct, 2),
            "next_earnings_date": next_earnings_date,
        },
        "profitability_and_financials": {
            "revenue_ltm_m": revenue_ltm,
            "gross_profit_ltm_m": gross_profit_ltm,
            "operating_profit_ltm_m": operating_profit_ltm,
            "operating_margin_pct": round(operating_margin_pct, 2),
            "net_income_ltm_m": net_income_ltm,
            "net_margin_ltm_pct": round(net_margin_ltm_pct, 2),
            "eps_diluted_ltm": eps_diluted_ltm,
            "q2_2026_revenue_m": q2_2026_revenue,
            "q2_2026_operating_profit_m": q2_2026_operating_profit,
            "q2_2026_net_income_m": q2_2026_net_income,
            "q2_2026_eps": q2_2026_eps,
        },
        "balance_sheet_and_nav": {
            "total_assets_m": total_assets,
            "total_equity_m": total_equity,
            "total_debt_m": total_debt,
            "book_value_per_share": book_value_per_share,
            "price_to_book": round(price_to_book, 2),
            "nav_target_usd_b": nav_target_usd_b,
            "fx_revenue_share_target_pct": fx_revenue_share_target_pct,
            "us_solar_capacity_target_mw": current_us_solar_capacity_target_mw,
            "holding_discount_verdict": "Hisse defter değerine (₺199.60) göre %53.7 iskontolu (0.46x PD/DD) işlem görmektedir.",
        },
        "cash_flows_and_recovery": {
            "cfo_ltm_m": cfo_ltm,
            "cfi_ltm_m": cfi_ltm,
            "cff_ltm_m": cff_ltm,
            "fcf_yield_pct": fcf_yield_reported_pct,
            "cfo_last_3_quarters_sum_m": cfo_last_3_quarters_sum,
            "recovery_insight": "LTM negatif CFO tamamen Q3 2025 bir kerelik bankacılık likidite hareketinden kaynaklanmıştır; son 3 çeyrek kümülatif +₺186,1B pozitif nakit üretmiştir.",
        },
        "technicals": {
            "technical_summary": technical_summary,
            "moving_averages": moving_averages_summary,
            "technical_indicators": technical_indicators_summary,
        }
    }


if __name__ == "__main__":
    import json
    res = audit_sabanci_holding()
    print(json.dumps(res, indent=2, ensure_ascii=False))
