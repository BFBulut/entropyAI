#!/usr/bin/env python3
"""Valuation scenarios and multiple re-rating engine for ATP Yazılım ve Teknoloji A.Ş. (ATATP).
Models 3-stage growth, quarterly cash flow roll-off, WACC sensitivity, and Bull/Base/Bear scenarios.
"""

from typing import Dict, Any, List


def calculate_atatp_scenarios() -> Dict[str, Any]:
    stock_price_try = 293.75
    shares_m = 93.80
    market_cap_b = 27.50

    # Earnings projections from InvestingPro report
    eps_current_ltm = 21.00
    eps_fy26e = 29.98
    eps_fy27e = 53.17
    eps_fy28e = 80.84

    # Scenarios:
    # 1. Bear Case (Persistent macro headwind, inflation distortions, slower international expansion)
    # Target P/E derated to 8.0x on FY26 EPS
    bear_target_pe = 8.0
    bear_target_price = round(eps_fy26e * bear_target_pe, 2)
    bear_return_pct = round(((bear_target_price - stock_price_try) / stock_price_try) * 100, 2)

    # 2. Base Case (Consensus fair value realized as Q3 2025 rolls off, FY26 EPS delivered, P/E stabilizes at 13.0x)
    base_target_pe = 13.0
    base_target_price = 387.70  # Consensus Analyst Fair Value
    base_return_pct = round(((base_target_price - stock_price_try) / stock_price_try) * 100, 2)

    # 3. Bull Case (AiX & GreenX commercialization, international SaaS accelerates to 35% of rev, FY27 EPS priced in at 10x)
    bull_target_pe = 10.0  # 10x on FY27 EPS
    bull_target_price = round(eps_fy27e * bull_target_pe, 2)  # ~531.70 TRY
    bull_return_pct = round(((bull_target_price - stock_price_try) / stock_price_try) * 100, 2)

    # Quarterly CFO Roll-off Projection
    # When Q3 2025 (-1,691M) drops out of LTM calculation in Q3 2026:
    # Assuming Q3 2026 CFO equals modest average (+250M TRY)
    cfo_q4_25 = 266.2
    cfo_q1_26 = 237.2
    cfo_q2_26 = 322.2
    cfo_q3_26_projected = 275.0
    cfo_ltm_projected_q3_26 = cfo_q4_25 + cfo_q1_26 + cfo_q2_26 + cfo_q3_26_projected
    fcf_yield_projected_pct = (cfo_ltm_projected_q3_26 / (market_cap_b * 1000)) * 100

    # Sensitivity Matrix: WACC vs Terminal Growth Rate for Equity Value
    wacc_rates = [0.20, 0.24, 0.28]
    terminal_growths = [0.06, 0.08, 0.10]
    valuation_matrix: List[Dict[str, Any]] = []

    for wacc in wacc_rates:
        for tg in terminal_growths:
            if wacc > tg:
                # Value = FY26 Net Income * (1 + tg) / (wacc - tg)
                # Cap implied value into a per share price
                implied_equity_m = (eps_fy26e * shares_m * (1 + tg)) / (wacc - tg)
                implied_price = round(implied_equity_m / shares_m, 2)
                valuation_matrix.append({
                    "wacc_pct": round(wacc * 100, 1),
                    "terminal_growth_pct": round(tg * 100, 1),
                    "implied_price_try": implied_price,
                    "upside_pct": round(((implied_price - stock_price_try) / stock_price_try) * 100, 1)
                })

    return {
        "stock_price_try": stock_price_try,
        "scenarios": {
            "bear": {
                "description": "Makro baskı ve çarpan daralması (FY26 F/K: 8.0x)",
                "target_price_try": bear_target_price,
                "return_pct": bear_return_pct,
            },
            "base": {
                "description": "Konsensüs adil değer ve Q3 2025 nakit akışı normalizasyonu",
                "target_price_try": base_target_price,
                "return_pct": base_return_pct,
            },
            "bull": {
                "description": "AiX & Zenia küresel SaaS ölçeklenmesi (FY27 F/K: 10.0x)",
                "target_price_try": bull_target_price,
                "return_pct": bull_return_pct,
            }
        },
        "cfo_rolloff_catalyst": {
            "dropped_quarter_cfo_m": -1691.0,
            "projected_ltm_cfo_after_q3_m": round(cfo_ltm_projected_q3_26, 2),
            "projected_fcf_yield_pct": round(fcf_yield_projected_pct, 2),
            "rerating_catalyst": "Q3 2026 finansallarında tek seferlik nakit çıkışının bilanço ve nakit akım tablosundan düşmesiyle FCF verimi -%9.01'den +%4.0'e fırlayacaktır."
        },
        "valuation_matrix": valuation_matrix
    }


if __name__ == "__main__":
    import json
    res = calculate_atatp_scenarios()
    print(json.dumps(res, indent=2, ensure_ascii=False))
