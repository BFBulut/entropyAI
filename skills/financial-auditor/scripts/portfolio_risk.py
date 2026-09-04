#!/usr/bin/env python3
"""CLI and library utility for quantitative portfolio risk and statistical arbitrage:
- Sortino Ratio (Downside deviation penalty only)
- Calmar Ratio (CAGR / Maximum Drawdown)
- Parametric VaR (Value at Risk) & CVaR (Conditional VaR / Expected Shortfall)
- Pairs Trading Cointegration Spread Z-Score
"""

import argparse
import json
import math
from typing import Dict, Any, List


def calculate_sortino_ratio(
    returns: List[float],
    target_return: float = 0.0,
    risk_free_rate: float = 0.0
) -> Dict[str, Any]:
    """Calculates Sortino ratio penalizing only downside deviation below target_return."""
    if not returns:
        return {"error": "Returns list cannot be empty"}

    n = len(returns)
    avg_return = sum(returns) / n

    downside_diffs = [min(0.0, r - target_return) ** 2 for r in returns]
    downside_variance = sum(downside_diffs) / n
    downside_dev = math.sqrt(downside_variance)

    if downside_dev <= 0:
        sortino = float("inf") if (avg_return - risk_free_rate) > 0 else 0.0
    else:
        sortino = (avg_return - risk_free_rate) / downside_dev

    return {
        "average_return_pct": round(avg_return * 100, 2),
        "downside_deviation_pct": round(downside_dev * 100, 2),
        "sortino_ratio": round(sortino, 2) if sortino != float("inf") else "Sonsuz (Hiç kayıp yok)",
        "performance_verdict": (
            "Üst Düzey Asimetrik Performans (Sortino >= 2.0)" if isinstance(sortino, float) and sortino >= 2.0
            else "Tatmin Edici Risk-Ödül (1.0 <= Sortino < 2.0)" if isinstance(sortino, float) and sortino >= 1.0
            else "Yüksek Aşağı Yönlü Risk (Sortino < 1.0)"
        )
    }


def calculate_calmar_ratio(
    cagr_pct: float,
    max_drawdown_pct: float
) -> Dict[str, Any]:
    """Calculates Calmar Ratio = CAGR / abs(Max Drawdown)."""
    abs_mdd = abs(max_drawdown_pct)
    if abs_mdd <= 0:
        return {"error": "Maximum drawdown must be non-zero"}

    calmar = cagr_pct / abs_mdd

    return {
        "cagr_pct": round(cagr_pct, 2),
        "max_drawdown_pct": round(abs_mdd, 2),
        "calmar_ratio": round(calmar, 2),
        "risk_reward_verdict": (
            "Mükemmel Strateji Kalitesi (Calmar >= 2.0)" if calmar >= 2.0
            else "İyi / Standart Hedge Fon Düzeyi (1.0 <= Calmar < 2.0)" if calmar >= 1.0
            else "Zayıf / Yüksek Çöküş Riski (Calmar < 1.0)"
        )
    }


def calculate_var_cvar(
    mean_daily_return_pct: float,
    std_daily_dev_pct: float,
    portfolio_value: float,
    confidence_level: float = 0.95
) -> Dict[str, Any]:
    """Calculates 1-day Parametric VaR and CVaR (Expected Shortfall) assuming normal distribution.
    Z-scores: 95% -> 1.645, 99% -> 2.326.
    CVaR for standard normal: mu - sigma * (phi(Z) / (1 - alpha))
    """
    if portfolio_value <= 0 or std_daily_dev_pct <= 0:
        return {"error": "Portfolio value and standard deviation must be positive"}

    mu = mean_daily_return_pct / 100.0
    sigma = std_daily_dev_pct / 100.0

    if abs(confidence_level - 0.99) < 0.005:
        z = 2.326
    else:
        z = 1.645  # default 95%

    var_pct = -(mu - z * sigma)
    var_amount = var_pct * portfolio_value

    # Standard normal density at z: phi(z) = (1/sqrt(2pi)) * exp(-z^2 / 2)
    phi_z = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * (z ** 2))
    tail_prob = 1.0 - confidence_level
    cvar_pct = -(mu - sigma * (phi_z / tail_prob))
    cvar_amount = cvar_pct * portfolio_value

    return {
        "confidence_level_pct": round(confidence_level * 100, 1),
        "portfolio_value": round(portfolio_value, 2),
        "var_1day_pct": round(var_pct * 100, 2),
        "var_1day_amount": round(var_amount, 2),
        "cvar_1day_pct": round(cvar_pct * 100, 2),
        "cvar_1day_amount": round(cvar_amount, 2),
        "explanation": f"%{round(confidence_level * 100)} güven düzeyinde 1 günde maksimum kayıp {round(var_amount, 2)} TL; kuyruk koptuğunda beklenen ortalama kayıp {round(cvar_amount, 2)} TL."
    }


def calculate_pairs_zscore(
    price_a: float,
    price_b: float,
    hedge_ratio_beta: float,
    spread_mean: float,
    spread_std: float
) -> Dict[str, Any]:
    """Calculates Cointegration Spread and Z-Score for Pairs Trading."""
    if spread_std <= 0:
        return {"error": "Spread standard deviation must be positive"}

    current_spread = price_a - (hedge_ratio_beta * price_b)
    z_score = (current_spread - spread_mean) / spread_std

    if z_score >= 2.0:
        signal = "A SAT / B AL (Spread Aşırı Genişledi - Açığa Satış Fırsatı)"
    elif z_score <= -2.0:
        signal = "A AL / B SAT (Spread Aşırı Daraldı - Alım Fırsatı)"
    elif abs(z_score) <= 0.5:
        signal = "NÖTR / KÂR AL (Spread Ortalamaya Döndü - Pozisyonu Kapat)"
    else:
        signal = "BEKLE / MEVCUT POZİSYONU KORU"

    return {
        "current_spread": round(current_spread, 3),
        "spread_mean": round(spread_mean, 3),
        "spread_std": round(spread_std, 3),
        "z_score": round(z_score, 2),
        "trading_signal": signal
    }


def main():
    parser = argparse.ArgumentParser(description="Portfolio Risk & StatArb Analytics Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sortino
    sort_p = subparsers.add_parser("sortino")
    sort_p.add_argument("--returns", type=float, nargs="+", required=True, help="List of decimal returns (e.g. 0.05 -0.02 0.04)")
    sort_p.add_argument("--target", type=float, default=0.0)
    sort_p.add_argument("--rf", type=float, default=0.0)

    # Calmar
    calmar_p = subparsers.add_parser("calmar")
    calmar_p.add_argument("--cagr", type=float, required=True, help="CAGR %")
    calmar_p.add_argument("--mdd", type=float, required=True, help="Max Drawdown %")

    # VaR
    var_p = subparsers.add_parser("var")
    var_p.add_argument("--mean", type=float, default=0.05, help="Daily mean return %")
    var_p.add_argument("--std", type=float, required=True, help="Daily std dev %")
    var_p.add_argument("--val", type=float, required=True, help="Portfolio value")
    var_p.add_argument("--conf", type=float, default=0.95, help="Confidence level (0.95 or 0.99)")

    # Pairs
    pairs_p = subparsers.add_parser("pairs")
    pairs_p.add_argument("--pa", type=float, required=True, help="Price A")
    pairs_p.add_argument("--pb", type=float, required=True, help="Price B")
    pairs_p.add_argument("--beta", type=float, default=1.0, help="Hedge ratio beta")
    pairs_p.add_argument("--mean", type=float, required=True, help="Historical spread mean")
    pairs_p.add_argument("--std", type=float, required=True, help="Historical spread std")

    args = parser.parse_args()

    if args.command == "sortino":
        res = calculate_sortino_ratio(args.returns, args.target, args.rf)
    elif args.command == "calmar":
        res = calculate_calmar_ratio(args.cagr, args.mdd)
    elif args.command == "var":
        res = calculate_var_cvar(args.mean, args.std, args.val, args.conf)
    elif args.command == "pairs":
        res = calculate_pairs_zscore(args.pa, args.pb, args.beta, args.mean, args.std)
    else:
        res = {"error": "Unknown command"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
