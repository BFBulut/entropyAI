#!/usr/bin/env python3
"""Quantitative CapEx Trajectory, Liquidity Runway, and 3-Month Investment Outlook Engine
for Ford Otomotiv Sanayi A.Ş. (FROTO).

Evaluates:
1. Historical CapEx cycle (Peak CapEx vs Current trajectory)
2. Debt capacity exhaustion under 1.0x Interest Coverage
3. Operating Cash Flow (CFO) vs CapEx commitment
4. 3-Month corporate CapEx expansion probability vs Cash Preservation Mode
5. Equity investor capital flows & market sentiment ahead of Q3 2026 earnings (Oct 28, 2026).
"""

from typing import Dict, Any


def evaluate_3month_investment_outlook() -> Dict[str, Any]:
    # 1. Historical CapEx (CFI Outflows in TRY Million)
    capex_history = {
        2022: 34199.0,
        2023: 46304.0,  # Peak investment: Craiova acquisition & EV groundwork
        2024: 42591.0,
        2025: 23729.0,  # Capital expenditure deceleration
        "LTM": 17972.0,
        "Q1_2026": 2093.0,
        "Q2_2026": 4347.0,
    }

    # Revenue History (TRY Million)
    revenue_history = {
        2022: 322556.0,
        2023: 594705.0,
        2024: 778801.0,
        2025: 830827.0,
        "LTM": 775224.0,
    }

    # CapEx Intensity (CapEx / Revenue %)
    capex_intensity_2023 = (capex_history[2023] / revenue_history[2023]) * 100  # ~7.79%
    capex_intensity_2025 = (capex_history[2025] / revenue_history[2025]) * 100  # ~2.86%
    capex_intensity_ltm = (capex_history["LTM"] / revenue_history["LTM"]) * 100  # ~2.32%

    # 2. Financial Headwinds & Solvency Constraints
    total_debt_m = 169782.0
    ebitda_ltm_m = 43634.0
    operating_income_ebit_m = 29591.0
    interest_coverage_ratio = 1.0  # Net interest coverage is critically constrained at 1.0x
    credit_rating = "S&P BB-"

    # 3. Cash Flow Deterioration in Q2 2026
    cfo_q2_26 = 1169.0
    capex_q2_26 = 4347.0
    free_cash_flow_q2_26 = cfo_q2_26 - capex_q2_26  # -3178.0 TRY Million
    reported_levered_fcf_q2_26 = -3384.0  # Strongly negative

    # 4. Committed Programs vs Discretionary CapEx
    # Committed: €364M New-Cab program, €2B EV Kocaeli transition (spread over multi-year schedule)
    # Average quarterly run-rate for committed CapEx: ~3500 - 4500 TRY Million
    projected_q3_capex_low = 3500.0
    projected_q3_capex_high = 4500.0

    # Probability of Corporate CapEx Acceleration / Expansion in next 3 months:
    # Constrained by:
    # a) 1.0x interest coverage (further debt borrowing is restricted)
    # b) Negative FCF in Q2 2026
    # c) Management guidance cut (EBITDA margins down to 6-7%, domestic volume down 18%)
    capex_expansion_expected = False
    capex_posture = "Nakit Koruma & Zorunlu Proje Disiplini (Cash Preservation & Controlled Run-rate)"

    # 5. Stock / Equity Market Investor Inflow Outlook (Next 3 Months)
    # Next Earnings Date: October 28, 2026 (Q3 2026)
    analyst_q3_eps_revision_pct = -31.3  # Analysts slashed Q3 EPS from $0.32 to $0.22
    technical_rating = "Strong Sell"
    macro_inflation_fx_scissors_pp = 18.0  # 32% inflation vs 14% EUR/TRY

    equity_momentum_inflow_expected = False
    equity_inflow_profile = "Bekle-Gör & Taban Arayışı (Wait-and-See / Base Building)"
    long_term_deep_value_accumulation = True  # Attractive for 12-24m horizon at 1.49x P/B, 15% div yield

    return {
        "analysis_target": "Ford Otomotiv Sanayi A.Ş. (FROTO)",
        "horizon": "Önümüzdeki 3 Ay (Q3 - Q4 2026)",
        "capex_cycle": {
            "peak_capex_year": 2023,
            "peak_capex_intensity_pct": round(capex_intensity_2023, 2),
            "current_capex_intensity_pct": round(capex_intensity_ltm, 2),
            "capex_trend": "Azalan / Disiplinli (Zirve 2023-2024'te geride kaldı)",
            "q2_26_fcf_try_m": reported_levered_fcf_q2_26,
            "fcf_status": "Negatif (-3.38 Milyar TL)",
        },
        "solvency_constraints": {
            "total_debt_try_b": round(total_debt_m / 1000.0, 2),
            "interest_coverage_ratio": interest_coverage_ratio,
            "credit_rating": credit_rating,
            "debt_expansion_capacity": "Kritik Derecede Kısıtlı (1.0x faiz karşılama ek borçlanmaya izin vermiyor)",
        },
        "corporate_capex_verdict": {
            "capex_expansion_expected_3m": capex_expansion_expected,
            "corporate_posture": capex_posture,
            "projected_quarterly_runrate_try_b": f"{projected_q3_capex_low/1000.0:.1f} - {projected_q3_capex_high/1000.0:.1f}",
            "rationale": "Yüksek faizler, S&P BB- kredi notu, negatif Q2 serbest nakit akışı ve marj baskısı nedeniyle yeni yatırım artışı beklenmez; mevcut taahhütler kontrollü sürdürülür.",
        },
        "equity_investor_inflow_verdict": {
            "inflow_surge_expected_3m": equity_momentum_inflow_expected,
            "market_profile": equity_inflow_profile,
            "next_catalyst": "28 Ekim 2026 Q3 Finansalları",
            "q3_eps_revision_pct": analyst_q3_eps_revision_pct,
            "long_term_accumulation_attractive": long_term_deep_value_accumulation,
            "rationale": "Kısa vadede kâr revizyonları ve makro makas baskısı nedeniyle hisseye agresif yatırım girişi beklenmez; taban oluşumu öngörülür.",
        },
    }


if __name__ == "__main__":
    import pprint
    result = evaluate_3month_investment_outlook()
    pprint.pprint(result)
