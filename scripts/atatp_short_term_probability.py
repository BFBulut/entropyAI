#!/usr/bin/env python3
"""Short-term (11-day) quantitative probability and technical catalyst engine for ATATP.
Models log-normal return distribution, first-passage barrier touch probability,
Fibonacci technical levels, and macro/earnings catalyst timeline.
"""

import math
from typing import Dict, Any


def calculate_11day_atatp_probability(
    current_price: float = 293.75,
    target_gain_pct: float = 10.0,
    calendar_days: int = 11,
    trading_days: int = 8,
    annual_volatility: float = 0.52,  # 52% annualized volatility characteristic of BIST tech
    annual_risk_free_rate: float = 0.35,  # 35% BIST risk-free benchmark
) -> Dict[str, Any]:
    target_price = round(current_price * (1.0 + (target_gain_pct / 100.0)), 2)
    dt = trading_days / 252.0
    vol_sqrt_t = annual_volatility * math.sqrt(dt)

    # 1. Terminal Probability (P(S_T >= Target))
    # Drift mu adjusted for risk-neutral / local trend
    drift = annual_risk_free_rate - (0.5 * (annual_volatility ** 2))
    log_ratio = math.log(target_price / current_price)
    d2 = (math.log(current_price / target_price) + (drift * dt)) / vol_sqrt_t

    # Standard normal CDF approximation (Abramowitz & Stegun)
    def norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    terminal_prob = norm_cdf(d2)

    # 2. First-Passage Touch Probability (Probability of touching target price at any point within 11 days)
    # Using reflection principle approximation for standard Brownian motion
    touch_prob = min(1.0, 2.0 * terminal_prob)

    # 3. Technical Support & Resistance Levels (Based on 52-Week Range ₺122.6 - ₺368.5)
    high_52w = 368.50
    low_52w = 122.60
    range_span = high_52w - low_52w  # 245.90 TRY

    # Fibonacci Retracement from 368.5 peak
    fib_236 = round(high_52w - (0.236 * range_span), 2)  # ₺310.47
    fib_382 = round(high_52w - (0.382 * range_span), 2)  # ₺274.57 (Key major support)
    fib_500 = round(high_52w - (0.500 * range_span), 2)  # ₺245.55

    # Resistance cluster right around +10% target:
    # ₺315 - ₺325 is the previous breakdown pivot (gap zone and 20-day SMA retest)
    resistance_pivot_low = 315.00
    resistance_pivot_high = 325.00

    # 4. Catalyst Analysis over 11-day window
    # Next Earnings Date: 2026-11-06 (November 6, 2026 -> ~60 days away)
    days_to_earnings = 60
    has_earnings_catalyst_11d = False
    has_scheduled_dividend_11d = False

    # Historical Momentum Context from InvestingPro report
    # 1-Week Return: -3.3% (Sell-off cooling)
    # 2-Week Return: -3.7%
    # Technical Indicator Score: "Sell" (RSI & MACD in downward momentum correction)
    # Moving Averages: "Neutral"

    return {
        "current_price_try": current_price,
        "target_price_try": target_price,
        "target_gain_pct": target_gain_pct,
        "calendar_days": calendar_days,
        "trading_days": trading_days,
        "parameters": {
            "annual_volatility_pct": round(annual_volatility * 100, 1),
            "period_volatility_pct": round(vol_sqrt_t * 100, 2),
        },
        "probabilities": {
            "terminal_probability_pct": round(terminal_prob * 100, 2),
            "touch_probability_pct": round(touch_prob * 100, 2),
            "statistical_verdict": "Düşük-Orta Olasılık (~%18 terminal, ~%36 anlık temas)",
        },
        "technical_structure": {
            "resistance_cluster_try": [resistance_pivot_low, resistance_pivot_high],
            "target_inside_resistance": resistance_pivot_low <= target_price <= resistance_pivot_high,
            "major_support_fib_382_try": fib_382,
            "minor_resistance_fib_236_try": fib_236,
            "technical_indicator_state": "Sell (Düzeltme & Soğuma modunda)",
            "moving_averages_state": "Neutral",
        },
        "catalyst_timeline": {
            "days_to_earnings": days_to_earnings,
            "next_earnings_date": "2026-11-06",
            "has_earnings_in_window": has_earnings_catalyst_11d,
            "summary": "11 günlük pencerede (Eylül ortası) planlanmış bir bilanço veya temettü katalizörü bulunmamaktadır. Ana katalizör Kasım başındaki Q3 bilançosudur."
        }
    }


if __name__ == "__main__":
    import json
    res = calculate_11day_atatp_probability()
    print(json.dumps(res, indent=2, ensure_ascii=False))
