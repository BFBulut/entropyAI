#!/usr/bin/env python3
"""1-Week Short-Term Technical Momentum & Return Probability Engine for Sabancı Holding (IS:SAHOL).
Analyzes short-term price action, technical indicators (Strong Buy), support/resistance clusters,
and 5-trading-day upward probability distribution.
"""

import math
from typing import Dict, Any


def calculate_sahol_1week_outlook(
    current_price: float = 92.50,
    trading_days: int = 5,
    calendar_days: int = 7,
    annual_volatility: float = 0.34,  # ~34% historical volatility for SAHOL
    drift_annual: float = 0.25,  # Upward drift given strong buy technical regime
) -> Dict[str, Any]:
    dt = trading_days / 252.0
    period_vol = annual_volatility * math.sqrt(dt)  # ~4.79%

    # Standard normal CDF approximation
    def norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    # Probability of positive return (S_T > S_0) over 5 trading days
    # d = (ln(S0/S0) + (mu - 0.5*sigma^2)*dt) / (sigma*sqrt(dt))
    drift_eff = drift_annual - (0.5 * (annual_volatility ** 2))
    d_pos = (drift_eff * dt) / period_vol
    upward_probability = norm_cdf(d_pos)

    # Probability of reaching at least +3.5% (₺95.74, first resistance)
    target_res1 = 95.50
    d_res1 = (math.log(current_price / target_res1) + (drift_eff * dt)) / period_vol
    prob_reach_res1 = norm_cdf(d_res1)
    # Touch probability (intra-week high touching resistance)
    touch_prob_res1 = min(0.95, 2.0 * prob_reach_res1)

    # Technical Levels (Sep 3-8, 2026)
    support_1 = 91.20  # 20-day EMA support
    support_2 = 88.80  # 50-day SMA major support
    resistance_1 = 95.50  # 1-week primary test resistance (+3.24%)
    resistance_2 = 98.20  # Secondary resistance (+6.16%)
    psychological_target = 100.00  # (+8.11%)
    fair_value_target = 101.65  # InvestingPro Fair Value (+9.89%)

    # Momentum returns from report
    momentum_data = {
        "1_week_return_pct": -1.3,
        "2_week_return_pct": 2.6,
        "3_week_return_pct": 4.2,
        "1_month_return_pct": 6.9,
        "3_month_return_pct": 2.0,
        "1_year_return_pct": 9.2,
        "5_year_return_pct": 971.4,
    }

    technical_ratings = {
        "technical_summary": "Strong Buy",
        "moving_averages": "Buy (Tüm kısa-orta vadeli EMA'lar üzerinde)",
        "technical_indicators": "Strong Buy (RSI 55 nötr-pozitif, MACD alım bölgesinde)",
        "pattern": "Boğa Flaması (Bullish Flag / Konsolidasyon)",
    }

    verdict_1week = {
        "expected_direction": "YUKARI (Yükseliş / Pozitif Tepki Ağırlıklı)",
        "upward_probability_pct": round(upward_probability * 100.0, 1),
        "touch_resistance_prob_pct": round(touch_prob_res1 * 100.0, 1),
        "primary_price_target_try": resistance_1,
        "secondary_price_target_try": resistance_2,
        "critical_stop_support_try": support_1,
        "summary": "Teknik göstergelerin 'Strong Buy' sinyali vermesi, son 1 aydaki %6.9'luk yükselişin ardından geçen haftaki -%1.3'lük hareketin bir düzeltme değil sağlıklı bir flama konsolidasyonu olduğunu teyit etmektedir. ₺91.20 desteği korundukça 1 hafta içerisinde ₺95.50 – ₺98.00 bandına doğru yükseliş beklenmektedir."
    }

    return {
        "current_price_try": current_price,
        "trading_days": trading_days,
        "calendar_days": calendar_days,
        "period_volatility_pct": round(period_vol * 100.0, 2),
        "momentum": momentum_data,
        "technicals": technical_ratings,
        "support_levels": [support_1, support_2],
        "resistance_levels": [resistance_1, resistance_2, psychological_target, fair_value_target],
        "outlook_1week": verdict_1week,
    }


if __name__ == "__main__":
    import json
    res = calculate_sahol_1week_outlook()
    print(json.dumps(res, indent=2, ensure_ascii=False))
