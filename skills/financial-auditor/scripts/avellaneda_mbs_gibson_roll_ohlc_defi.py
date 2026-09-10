#!/usr/bin/env python3
"""CLI and library utility for:
1. Avellaneda-Lee (2010) Statistical Arbitrage & Ornstein-Uhlenbeck (OU) S-Score Trading
2. Mortgage-Backed Securities (MBS) Prepayment Modeling, Negative Convexity & OAS
3. Gibson-Schwartz (1990) 2-Factor Commodity Pricing & Convenience Yield Curve
4. Roll (1984) Serial Covariance Model & Effective Spread from Closing Prices
5. Garman-Klass (1980) & Yang-Zhang (2000) High-Efficiency OHLC Volatility Estimators
6. DeFi Jump Rate Lending Models & Flash Liquidation Cascade Dynamics
"""

import argparse
import json
import math
from typing import Any, Dict, List, Optional, Tuple


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ==============================================================================
# 1. Avellaneda-Lee (2010) Statistical Arbitrage & Ornstein-Uhlenbeck (OU)
# ==============================================================================

def fit_ornstein_uhlenbeck_process(
    series: List[float],
    dt: float = 1.0 / 252.0
) -> Dict[str, Any]:
    """Fits an Ornstein-Uhlenbeck (OU) mean-reverting process to a residual series:
    dX_t = kappa * (m - X_t) dt + sigma * dW_t

    Discrete-time AR(1) representation:
    X_{k+1} = a + b * X_k + eps_{k+1}
    where:
    b = exp(-kappa * dt)
    a = m * (1 - exp(-kappa * dt))
    kappa = -ln(b) / dt
    m = a / (1 - b)
    sigma_eq = sqrt(Var(eps) / (1 - b^2))
    s_score = (X_last - m) / sigma_eq
    """
    n = len(series)
    if n < 10:
        raise ValueError("OU sürecini modellemek için en az 10 gözlem gereklidir.")

    x = series[:-1]
    y = series[1:]
    k_len = len(x)

    mean_x = sum(x) / k_len
    mean_y = sum(y) / k_len

    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(k_len))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(k_len))

    if denominator == 0:
        raise ValueError("Seri varyansı sıfır olamaz.")

    b = numerator / denominator
    a = mean_y - b * mean_x

    residuals = [y[i] - a - b * x[i] for i in range(k_len)]
    var_eps = sum(r ** 2 for r in residuals) / max(1, k_len - 2)

    # Check for valid mean reversion (0 < b < 1)
    is_mean_reverting = 0.0 < b < 0.99999
    if is_mean_reverting:
        kappa = -math.log(b) / dt
        half_life_days = (math.log(2.0) / kappa) * 252.0 if dt == 1.0 / 252.0 else math.log(2.0) / kappa
        m = a / (1.0 - b)
        var_eq = var_eps / (1.0 - b ** 2) if (1.0 - b ** 2) > 0 else var_eps
        sigma_eq = math.sqrt(max(1e-12, var_eq))
        sigma_ou = math.sqrt(max(1e-12, var_eps * 2.0 * kappa / (1.0 - b ** 2)))
        s_score = (series[-1] - m) / sigma_eq
    else:
        # Fallback if series is explosive or random walk
        kappa = 0.0
        half_life_days = float("inf")
        m = mean_y
        sigma_eq = math.sqrt(max(1e-12, var_eps))
        sigma_ou = 0.0
        s_score = (series[-1] - m) / sigma_eq

    # Trading signal generation
    if abs(s_score) > 3.0:
        signal = "STOP_LOSS_BREAK"
        action = "Yapısal kırılma veya eşbütünleşme bozulması. Pozisyonu acil kapat."
    elif s_score > 1.25:
        signal = "OPEN_SHORT"
        action = "Varlık faktöre göre aşırı değerli. Short aç veya spread daralmasına oyna."
    elif s_score < -1.25:
        signal = "OPEN_LONG"
        action = "Varlık faktöre göre aşırı iskontolu. Long aç veya spread genişlemesine oyna."
    elif abs(s_score) < 0.50:
        signal = "CLOSE_POSITION"
        action = "Spread denge seviyesine (m) döndü. Kârı realize et ve çık."
    else:
        signal = "HOLD"
        action = "Mevcut pozisyonu koru veya izlemede kal."

    return {
        "b_coefficient": round(b, 6),
        "a_intercept": round(a, 6),
        "kappa_reversion_speed": round(kappa, 4),
        "half_life_days": round(half_life_days, 2) if half_life_days != float("inf") else "INF",
        "equilibrium_mean_m": round(m, 6),
        "equilibrium_volatility_sigma_eq": round(sigma_eq, 6),
        "annualized_ou_sigma": round(sigma_ou, 6),
        "s_score": round(s_score, 4),
        "is_mean_reverting": is_mean_reverting,
        "signal": signal,
        "action": action
    }


def avellaneda_lee_stat_arb_analysis(
    asset_prices: List[float],
    benchmark_prices: List[float],
    dt: float = 1.0 / 252.0
) -> Dict[str, Any]:
    """Performs end-to-end Avellaneda-Lee (2010) statistical arbitrage analysis:
    1. Computes log returns
    2. Runs OLS regression R_asset = alpha + beta * R_bench + eps
    3. Forms cumulative residual process X_t
    4. Fits OU process to obtain s-score and trading directives.
    """
    if len(asset_prices) != len(benchmark_prices):
        raise ValueError("Varlık ve gösterge fiyat serileri aynı uzunlukta olmalıdır.")
    if len(asset_prices) < 15:
        raise ValueError("Stat-arb analizi için en az 15 fiyat noktası gereklidir.")

    r_asset = [math.log(asset_prices[i] / asset_prices[i - 1]) for i in range(1, len(asset_prices))]
    r_bench = [math.log(benchmark_prices[i] / benchmark_prices[i - 1]) for i in range(1, len(benchmark_prices))]
    n = len(r_asset)

    mean_a = sum(r_asset) / n
    mean_b = sum(r_bench) / n

    cov_ab = sum((r_asset[i] - mean_a) * (r_bench[i] - mean_b) for i in range(n))
    var_b = sum((r_bench[i] - mean_b) ** 2 for i in range(n))

    beta = cov_ab / var_b if var_b > 0 else 1.0
    alpha = mean_a - beta * mean_b

    # Cumulative residual process
    residuals = [r_asset[i] - (alpha + beta * r_bench[i]) for i in range(n)]
    cum_res = [0.0]
    for r in residuals:
        cum_res.append(cum_res[-1] + r)

    ou_result = fit_ornstein_uhlenbeck_process(cum_res, dt=dt)

    return {
        "beta": round(beta, 4),
        "alpha_annualized": round(alpha * 252.0, 4),
        "r_squared": round((cov_ab ** 2) / (var_b * sum((r_asset[i] - mean_a) ** 2 for i in range(n))), 4) if var_b > 0 else 0.0,
        "residual_series_length": len(cum_res),
        "ou_parameters": ou_result
    }


# ==============================================================================
# 2. Mortgage-Backed Securities (MBS) Prepayment, SMM/CPR & Negative Convexity
# ==============================================================================

def calculate_mbs_prepayment_and_cashflows(
    balance: float,
    wac: float,
    term_months: int,
    psa_speed: float = 100.0,
    current_age_months: int = 0,
    refi_rate: Optional[float] = None
) -> Dict[str, Any]:
    """Calculates Fannie Mae / Freddie Mac 30Y MBS prepayment rates, SMM, and cashflows:
    - PSA Benchmark: CPR(t) = min(6%, 6% * (t / 30)) * (PSA / 100)
    - SMM = 1 - (1 - CPR)^(1/12)
    - S-Curve Refi Adjustment if refi_rate is specified:
      RI = (WAC - refi_rate) * 100 bps
    """
    if balance <= 0 or wac <= 0 or term_months <= 0:
        raise ValueError("Bakiye, faiz oranı ve vade pozitif olmalıdır.")

    r_m = wac / 12.0
    rem_balance = balance
    total_interest = 0.0
    total_scheduled_principal = 0.0
    total_prepayments = 0.0
    weighted_time_principal = 0.0

    cpr_history = []
    cashflow_summary = []

    for m in range(current_age_months + 1, term_months + 1):
        if rem_balance <= 0.01:
            break

        # PSA benchmark base CPR
        base_cpr = min(0.06, 0.06 * (m / 30.0)) * (psa_speed / 100.0)

        # Refi incentive S-curve
        if refi_rate is not None:
            ri = (wac - refi_rate) * 100.0  # bps
            # Logistic S-curve
            s_curve_mult = 0.2 + 2.5 / (1.0 + math.exp(-0.02 * (ri - 50.0)))
            cpr = min(0.85, max(0.01, base_cpr * s_curve_mult))
        else:
            cpr = base_cpr

        cpr_history.append(cpr)
        smm = 1.0 - (1.0 - cpr) ** (1.0 / 12.0)

        # Scheduled monthly payment
        rem_term = term_months - m + 1
        denom = (1.0 + r_m) ** rem_term - 1.0
        scheduled_pmt = rem_balance * (r_m * (1.0 + r_m) ** rem_term) / denom if denom > 0 else rem_balance

        interest_pmt = rem_balance * r_m
        sched_principal = min(rem_balance, scheduled_pmt - interest_pmt)

        prepayment = max(0.0, (rem_balance - sched_principal) * smm)
        total_principal = sched_principal + prepayment

        total_interest += interest_pmt
        total_scheduled_principal += sched_principal
        total_prepayments += prepayment
        weighted_time_principal += (m - current_age_months) * total_principal

        rem_balance -= total_principal

        if m <= current_age_months + 12 or m == term_months:
            cashflow_summary.append({
                "month": m,
                "cpr": round(cpr * 100, 2),
                "smm": round(smm * 100, 3),
                "interest": round(interest_pmt, 2),
                "scheduled_principal": round(sched_principal, 2),
                "prepayment": round(prepayment, 2),
                "remaining_balance": round(max(0.0, rem_balance), 2)
            })

    total_prin_paid = total_scheduled_principal + total_prepayments
    wal_years = (weighted_time_principal / (12.0 * total_prin_paid)) if total_prin_paid > 0 else 0.0

    return {
        "initial_balance": balance,
        "wac_pct": round(wac * 100, 3),
        "psa_speed": psa_speed,
        "wal_years": round(wal_years, 2),
        "total_interest_paid": round(total_interest, 2),
        "total_scheduled_principal": round(total_scheduled_principal, 2),
        "total_prepayments": round(total_prepayments, 2),
        "prepayment_ratio_pct": round((total_prepayments / total_prin_paid) * 100, 2) if total_prin_paid > 0 else 0.0,
        "sample_cashflows": cashflow_summary[:6]
    }


def mbs_negative_convexity_and_oas(
    base_price: float,
    yield_curve_rate: float,
    z_spread_bps: float,
    oas_bps: float,
    dy: float = 0.01
) -> Dict[str, Any]:
    """Calculates MBS negative convexity and Option Cost:
    - Option Cost = Z-spread - OAS (Option-Adjusted Spread)
    - Negative convexity demonstration: Price upside is capped when yields drop
      because of prepayment surging, while price downside accelerates when yields rise.
    """
    option_cost_bps = z_spread_bps - oas_bps

    # Empirical MBS price curve proxy with prepayment asymmetric response
    # When rates fall (dy < 0), prepayment caps gain: P_up = P0 * (1 + D_eff * dy - 0.5 * Conv * dy^2)
    # where Conv is negative!
    effective_duration = 5.2 - (base_price - 100.0) * 0.08  # Duration shrinks as price rises (contraction risk)
    negative_convexity = -1.8 - max(0.0, base_price - 100.0) * 0.4  # Becomes strongly negative for premium bonds

    # Price changes under +100 bps and -100 bps yield shock
    dp_up_yield = base_price * (-effective_duration * dy + 0.5 * negative_convexity * (dy ** 2))
    dp_down_yield = base_price * (-effective_duration * (-dy) + 0.5 * negative_convexity * ((-dy) ** 2))

    price_if_yield_plus_100bp = base_price + dp_up_yield
    price_if_yield_minus_100bp = base_price + dp_down_yield

    # Standard numerical convexity = (P_minus + P_plus - 2*P0) / (P0 * dy^2)
    realized_convexity = (price_if_yield_minus_100bp + price_if_yield_plus_100bp - 2.0 * base_price) / (base_price * (dy ** 2))

    return {
        "base_price": base_price,
        "z_spread_bps": z_spread_bps,
        "oas_bps": oas_bps,
        "option_cost_bps": round(option_cost_bps, 2),
        "effective_duration": round(effective_duration, 2),
        "convexity_measure": round(realized_convexity, 2),
        "is_negatively_convex": realized_convexity < 0.0,
        "price_if_rates_drop_100bp": round(price_if_yield_minus_100bp, 2),
        "price_if_rates_rise_100bp": round(price_if_yield_plus_100bp, 2),
        "asymmetry_ratio": round(abs(price_if_yield_minus_100bp - base_price) / max(0.01, abs(price_if_yield_plus_100bp - base_price)), 2),
        "interpretation": "Getiriler düştüğünde borçlular ev kredilerini kapatıp yeniden finanse ettiği için MBS tavan yapar; getiriler yükseldiğinde ise vade uzar (uzama riski) ve sermaye kaybı derinleşir."
    }


# ==============================================================================
# 3. Gibson-Schwartz (1990) 2-Factor Commodity Pricing & Convenience Yield
# ==============================================================================

def gibson_schwartz_futures_pricing(
    spot_price: float,
    convenience_yield: float,
    maturity: float,
    risk_free_rate: float,
    kappa: float,
    alpha: float,
    sigma1: float,
    sigma2: float,
    rho: float,
    market_price_of_risk: float = 0.0
) -> Dict[str, Any]:
    """Gibson & Schwartz (1990) 2-Factor Commodity Futures Pricing:
    State variables:
    dS/S = (r - delta) dt + sigma1 * dW1
    d_delta = [kappa*(alpha - delta) - lambda] dt + sigma2 * dW2, Corr(dW1, dW2) = rho

    Closed-form solution:
    F(S, delta, T) = S * exp(-delta * B(T) + A(T))
    where:
    B(T) = (1 - exp(-kappa * T)) / kappa
    """
    if spot_price <= 0 or maturity <= 0 or kappa <= 0:
        raise ValueError("Spot fiyat, vade ve kappa kesinlikle pozitif olmalıdır.")

    alpha_hat = alpha - (market_price_of_risk / kappa)

    b_t = (1.0 - math.exp(-kappa * maturity)) / kappa

    term1 = (risk_free_rate - alpha_hat + 0.5 * (sigma2 ** 2) / (kappa ** 2) - (sigma1 * sigma2 * rho) / kappa) * maturity
    term2 = 0.25 * (sigma2 ** 2) * (1.0 - math.exp(-2.0 * kappa * maturity)) / (kappa ** 3)
    term3 = (alpha_hat * kappa + sigma1 * sigma2 * rho - (sigma2 ** 2) / kappa) * (1.0 - math.exp(-kappa * maturity)) / (kappa ** 2)

    a_t = term1 + term2 + term3

    futures_price = spot_price * math.exp(-convenience_yield * b_t + a_t)

    # Samuelson effect: Volatility of futures returns
    futures_volatility = math.sqrt(max(1e-8, (sigma1 ** 2) + (sigma2 ** 2) * (b_t ** 2) - 2.0 * rho * sigma1 * sigma2 * b_t))

    state = "BACKWARDATION" if futures_price < spot_price else "CONTANGO"

    return {
        "spot_price": spot_price,
        "convenience_yield_pct": round(convenience_yield * 100, 2),
        "maturity_years": maturity,
        "futures_price": round(futures_price, 4),
        "curve_state": state,
        "roll_yield_annualized_pct": round((math.log(spot_price / futures_price) / maturity) * 100, 2),
        "instantaneous_spot_volatility_pct": round(sigma1 * 100, 2),
        "futures_volatility_samuelson_pct": round(futures_volatility * 100, 2),
        "samuelson_effect_valid": futures_volatility < sigma1,
        "b_t_decay_factor": round(b_t, 4)
    }


# ==============================================================================
# 4. Roll (1984) Serial Covariance Model & Effective Spread
# ==============================================================================

def roll_effective_spread(prices: List[float]) -> Dict[str, Any]:
    """Richard Roll (1984) effective bid-ask spread estimator:
    Under random walk with bid-ask bounce:
    Cov(Delta P_t, Delta P_{t-1}) = -s^2 / 4
    Effective Spread s = 2 * sqrt(-min(0, Cov(Delta P_t, Delta P_{t-1})))
    Percentage Spread = (s / P_mean) * 100
    """
    if len(prices) < 5:
        raise ValueError("Roll spread tahmini için en az 5 fiyat gereklidir.")

    dp = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    n = len(dp)

    mean_dp = sum(dp) / n
    # Calculate autocovariance at lag 1
    autocov = sum((dp[t] - mean_dp) * (dp[t - 1] - mean_dp) for t in range(1, n)) / (n - 1)

    mean_price = sum(prices) / len(prices)

    if autocov < 0.0:
        effective_spread = 2.0 * math.sqrt(-autocov)
        pct_spread = (effective_spread / mean_price) * 100.0
        status = "NORMAL_BOUNCE"
    else:
        effective_spread = 0.0
        pct_spread = 0.0
        status = "POSITIVE_AUTOCOVARIANCE_OR_TREND"

    return {
        "price_count": len(prices),
        "mean_price": round(mean_price, 4),
        "autocovariance_lag1": round(autocov, 6),
        "effective_spread_absolute": round(effective_spread, 4),
        "effective_spread_percentage": round(pct_spread, 3),
        "bounce_status": status,
        "liquidity_assessment": "YÜKSEK LİKİDİTE / DAR MAKAS" if pct_spread < 0.20 else ("ORTA LİKİDİTE" if pct_spread < 1.0 else "DÜŞÜK LİKİDİTE / GENİŞ MAKAS")
    }


# ==============================================================================
# 5. Garman-Klass (1980) & Yang-Zhang (2000) High-Efficiency OHLC Volatility
# ==============================================================================

def calculate_ohlc_volatility_estimators(
    bars: List[Dict[str, float]],
    trading_days: int = 252
) -> Dict[str, Any]:
    """Calculates Close-Close, Parkinson (1980), Garman-Klass (1980),
    Rogers-Satchell (1991), and Yang-Zhang (2000) volatility estimators:
    - Close-Close: standard sample variance of log returns
    - Parkinson: uses High / Low
    - Garman-Klass: uses OHLC (zero drift assumption)
    - Rogers-Satchell: handles non-zero drift
    - Yang-Zhang: unbiased, handles drift AND overnight jump gaps (Efficiency ~14x).
    """
    n = len(bars)
    if n < 5:
        raise ValueError("OHLC volatilite analizi için en az 5 bar gereklidir.")

    # 1. Close-to-Close
    cc_returns = [math.log(bars[i]["close"] / bars[i - 1]["close"]) for i in range(1, n)]
    mean_cc = sum(cc_returns) / len(cc_returns)
    var_cc = sum((r - mean_cc) ** 2 for r in cc_returns) / max(1, len(cc_returns) - 1)
    vol_cc = math.sqrt(var_cc * trading_days)

    # 2. Parkinson
    sum_parkinson = 0.0
    for b in bars:
        h, l = b["high"], b["low"]
        if h <= 0 or l <= 0:
            continue
        sum_parkinson += (math.log(h / l)) ** 2
    var_parkinson = sum_parkinson / (4.0 * math.log(2.0) * n)
    vol_parkinson = math.sqrt(var_parkinson * trading_days)

    # 3. Garman-Klass
    sum_gk = 0.0
    for b in bars:
        o, h, l, c = b["open"], b["high"], b["low"], b["close"]
        sum_gk += 0.5 * (math.log(h / l)) ** 2 - (2.0 * math.log(2.0) - 1.0) * (math.log(c / o)) ** 2
    var_gk = sum_gk / n
    vol_gk = math.sqrt(max(0.0, var_gk) * trading_days)

    # 4. Rogers-Satchell
    sum_rs = 0.0
    for b in bars:
        o, h, l, c = b["open"], b["high"], b["low"], b["close"]
        sum_rs += math.log(h / c) * math.log(h / o) + math.log(l / c) * math.log(l / o)
    var_rs = sum_rs / n
    vol_rs = math.sqrt(max(0.0, var_rs) * trading_days)

    # 5. Yang-Zhang
    overnight_returns = [math.log(bars[i]["open"] / bars[i - 1]["close"]) for i in range(1, n)]
    open_to_close = [math.log(bars[i]["close"] / bars[i]["open"]) for i in range(n)]

    mean_o = sum(overnight_returns) / len(overnight_returns)
    var_o = sum((r - mean_o) ** 2 for r in overnight_returns) / max(1, len(overnight_returns) - 1)

    mean_c = sum(open_to_close) / len(open_to_close)
    var_c = sum((r - mean_c) ** 2 for r in open_to_close) / max(1, len(open_to_close) - 1)

    k_yz = 0.34 / (1.34 + (n + 1.0) / (n - 1.0))
    var_yz = var_o + k_yz * var_c + (1.0 - k_yz) * var_rs
    vol_yz = math.sqrt(max(0.0, var_yz) * trading_days)

    return {
        "sample_size": n,
        "close_to_close_volatility_pct": round(vol_cc * 100, 2),
        "parkinson_volatility_pct": round(vol_parkinson * 100, 2),
        "garman_klass_volatility_pct": round(vol_gk * 100, 2),
        "rogers_satchell_volatility_pct": round(vol_rs * 100, 2),
        "yang_zhang_volatility_pct": round(vol_yz * 100, 2),
        "efficiency_gain_yang_zhang_vs_cc": round(var_cc / max(1e-8, var_yz), 2)
    }


# ==============================================================================
# 6. DeFi Jump Rate Lending Model & Flash Liquidation Cascades
# ==============================================================================

def defi_jump_rate_model(
    total_borrows: float,
    total_cash: float,
    base_rate: float = 0.02,
    optimal_utilization: float = 0.80,
    slope1: float = 0.04,
    slope2: float = 0.60,
    reserve_factor: float = 0.15
) -> Dict[str, Any]:
    """Compound / Aave piecewise linear (kinked) jump interest rate model:
    Utilization U = Borrows / (Borrows + Cash)
    If U <= U_optimal:
        R_borrow = Base + (U / U_optimal) * Slope1
    Else:
        R_borrow = Base + Slope1 + ((U - U_optimal) / (1 - U_optimal)) * Slope2
    Supply APY = U * R_borrow * (1 - Reserve_Factor)
    """
    total_liquidity = total_borrows + total_cash
    if total_liquidity <= 0:
        raise ValueError("Toplam likidite sıfırdan büyük olmalıdır.")

    u = total_borrows / total_liquidity

    if u <= optimal_utilization:
        borrow_rate = base_rate + (u / optimal_utilization) * slope1
        kink_state = "BELOW_OPTIMAL"
    else:
        excess = (u - optimal_utilization) / (1.0 - optimal_utilization)
        borrow_rate = base_rate + slope1 + excess * slope2
        kink_state = "ABOVE_OPTIMAL_JUMP_ACCELERATION"

    supply_rate = u * borrow_rate * (1.0 - reserve_factor)
    protocol_annual_revenue = total_borrows * borrow_rate * reserve_factor

    return {
        "utilization_rate_pct": round(u * 100, 2),
        "kink_state": kink_state,
        "borrow_apy_pct": round(borrow_rate * 100, 2),
        "supply_apy_pct": round(supply_rate * 100, 2),
        "reserve_factor_pct": round(reserve_factor * 100, 2),
        "protocol_annual_revenue_usd": round(protocol_annual_revenue, 2),
        "incentive_pressure": "YÜKSEK (Kredi faizi borç kapatmayı ve yeni mevduat çekmeyi zorunlu kılıyor)" if kink_state == "ABOVE_OPTIMAL_JUMP_ACCELERATION" else "DENGELİ"
    }


def defi_liquidation_cascade_simulation(
    collateral_amount: float,
    collateral_price: float,
    debt_amount_usd: float,
    liquidation_threshold: float = 0.80,
    liquidation_bonus: float = 0.05,
    price_drop_pct: float = 0.30,
    dex_slippage_pct: float = 0.08
) -> Dict[str, Any]:
    """Simulates flash liquidation cascade and bad debt protocol insolvency:
    Health Factor HF = (Collateral * Price * Threshold) / Debt
    If HF < 1.0:
    Liquidator repays debt, seizes collateral + bonus.
    If DEX slippage + price drop exceeds collateral cushion, protocol incurs BAD DEBT.
    """
    initial_collateral_usd = collateral_amount * collateral_price
    initial_hf = (initial_collateral_usd * liquidation_threshold) / debt_amount_usd if debt_amount_usd > 0 else float("inf")

    stressed_price = collateral_price * (1.0 - price_drop_pct)
    stressed_collateral_usd = collateral_amount * stressed_price
    stressed_hf = (stressed_collateral_usd * liquidation_threshold) / debt_amount_usd if debt_amount_usd > 0 else float("inf")

    is_liquidatable = stressed_hf < 1.0

    if is_liquidatable:
        # Liquidator seeks to seize collateral with bonus
        required_collateral_to_cover = (debt_amount_usd * (1.0 + liquidation_bonus)) / stressed_price
        collateral_seized = min(collateral_amount, required_collateral_to_cover)
        collateral_seized_value = collateral_seized * stressed_price

        # Liquidator sells seized collateral on DEX with slippage
        dex_liquidator_proceeds = collateral_seized_value * (1.0 - dex_slippage_pct)
        liquidator_net_profit = dex_liquidator_proceeds - debt_amount_usd

        # Protocol bad debt: if all collateral is seized but debt is not fully repaid
        remaining_debt = max(0.0, debt_amount_usd - (collateral_seized_value / (1.0 + liquidation_bonus)))
        bad_debt_incurred = remaining_debt if collateral_seized >= collateral_amount else 0.0
    else:
        collateral_seized = 0.0
        collateral_seized_value = 0.0
        liquidator_net_profit = 0.0
        bad_debt_incurred = 0.0

    return {
        "initial_collateral_value_usd": round(initial_collateral_usd, 2),
        "stressed_collateral_value_usd": round(stressed_collateral_usd, 2),
        "initial_health_factor": round(initial_hf, 3),
        "stressed_health_factor": round(stressed_hf, 3),
        "is_liquidatable": is_liquidatable,
        "collateral_seized_tokens": round(collateral_seized, 4),
        "liquidator_net_profit_usd": round(liquidator_net_profit, 2),
        "protocol_bad_debt_usd": round(bad_debt_incurred, 2),
        "solvency_status": "BATIK BORÇ / PROTOKOL İFLAS RİSKİ" if bad_debt_incurred > 0 else ("TASFİYE EDİLDİ - PROTOKOL GÜVENDE" if is_liquidatable else "SAĞLIKLI POZİSYON")
    }


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Avellaneda-Lee, MBS OAS, Gibson-Schwartz, Roll Spread, Yang-Zhang & DeFi Kink")
    subparsers = parser.add_subparsers(dest="command", help="Alt komutlar")

    # 1. Avellaneda-Lee
    p_ou = subparsers.add_parser("stat-arb", help="Avellaneda-Lee Stat-Arb & OU S-Score")
    p_ou.add_argument("--series", type=str, required=True, help="Virgülle ayrılmış kümülatif artık serisi")
    p_ou.add_argument("--dt", type=float, default=1.0 / 252.0)

    # 2. MBS Prepayment
    p_mbs = subparsers.add_parser("mbs", help="MBS Prepayment, SMM/CPR & Negatif Konveksite")
    p_mbs.add_argument("--balance", type=float, default=1000000.0)
    p_mbs.add_argument("--wac", type=float, default=0.065)
    p_mbs.add_argument("--term", type=int, default=360)
    p_mbs.add_argument("--psa", type=float, default=150.0)
    p_mbs.add_argument("--refi-rate", type=float, default=0.050)

    # 3. Gibson-Schwartz
    p_gs = subparsers.add_parser("gibson", help="Gibson-Schwartz Emtia & Convenience Yield")
    p_gs.add_argument("--spot", type=float, default=80.0)
    p_gs.add_argument("--convenience", type=float, default=0.08)
    p_gs.add_argument("--maturity", type=float, default=1.0)
    p_gs.add_argument("--rate", type=float, default=0.04)
    p_gs.add_argument("--kappa", type=float, default=0.35)
    p_gs.add_argument("--alpha", type=float, default=0.05)
    p_gs.add_argument("--sigma1", type=float, default=0.25)
    p_gs.add_argument("--sigma2", type=float, default=0.18)
    p_gs.add_argument("--rho", type=float, default=0.60)

    # 4. Roll Spread
    p_roll = subparsers.add_parser("roll", help="Roll (1984) Efektif Makas Tahmini")
    p_roll.add_argument("--prices", type=str, required=True, help="Virgülle ayrılmış fiyat serisi")

    # 5. OHLC Volatility
    p_ohlc = subparsers.add_parser("ohlc", help="Yang-Zhang & Garman-Klass Volatilite")
    p_ohlc.add_argument("--json-bars", type=str, required=True, help="JSON formatında [{'open':..., 'high':..., 'low':..., 'close':...}]")

    # 6. DeFi Jump Rate
    p_defi = subparsers.add_parser("defi", help="DeFi Jump Rate & Tasfiye Kaskadı")
    p_defi.add_argument("--borrows", type=float, default=85000000.0)
    p_defi.add_argument("--cash", type=float, default=15000000.0)
    p_defi.add_argument("--optimal-u", type=float, default=0.80)

    args = parser.parse_args()

    if args.command == "stat-arb":
        vals = [float(x.strip()) for x in args.series.split(",")]
        res = fit_ornstein_uhlenbeck_process(vals, dt=args.dt)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.command == "mbs":
        res = calculate_mbs_prepayment_and_cashflows(
            balance=args.balance,
            wac=args.wac,
            term_months=args.term,
            psa_speed=args.psa,
            refi_rate=args.refi_rate
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.command == "gibson":
        res = gibson_schwartz_futures_pricing(
            spot_price=args.spot,
            convenience_yield=args.convenience,
            maturity=args.maturity,
            risk_free_rate=args.rate,
            kappa=args.kappa,
            alpha=args.alpha,
            sigma1=args.sigma1,
            sigma2=args.sigma2,
            rho=args.rho
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.command == "roll":
        prices = [float(x.strip()) for x in args.prices.split(",")]
        res = roll_effective_spread(prices)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.command == "ohlc":
        bars = json.loads(args.json_bars)
        res = calculate_ohlc_volatility_estimators(bars)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.command == "defi":
        res = defi_jump_rate_model(
            total_borrows=args.borrows,
            total_cash=args.cash,
            optimal_utilization=args.optimal_u
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
