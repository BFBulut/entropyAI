#!/usr/bin/env python3
"""CLI and library utility for Basel III/IV Banking, Convertible Bond Arbitrage,
Exotic Barrier Options, State-Space Kalman Dynamic Pairs Trading & Downside Risk Profile:
1. Basel III / Basel IV Capital Adequacy & Liquidity (CET1, Tier 1, CAR, RWA, Leverage, LCR, NSFR & Buffers)
2. Convertible Bond Arbitrage & Greeks Dynamics (Parity, Conversion Premium, Bond Floor, Delta Hedge & Break-even)
3. Exotic Derivatives & Barrier Options (Up-and-Out/In, Down-and-Out/In, In-Out Parity, Digital Options & Pin Risk)
4. State-Space Kalman Filter Dynamic Pairs Trading (Time-Varying Beta & Alpha, Innovation Covariance & Adaptive Z-Score)
5. Distribution-Agnostic Risk & Drawdown Analytics (Omega Ratio, Ulcer Index, Pain Index, Martin Ratio & Higher Moments)
"""

import argparse
import json
import math
from typing import Dict, Any, List, Optional, Tuple


def _norm_cdf(x: float) -> float:
    """Cumulative standard normal distribution function using math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def calculate_basel_capital_and_liquidity(
    cet1_capital: float,
    tier1_capital: float,
    total_capital: float,
    rwa_credit: float,
    rwa_market: float,
    rwa_operational: float,
    total_exposure_leverage: float,
    hqla_amount: float,
    net_cash_outflows_30d: float,
    asf_amount: float,
    rsf_amount: float,
    capital_conservation_buffer_pct: float = 2.5,
    countercyclical_buffer_pct: float = 0.5,
    gsib_surcharge_pct: float = 0.0
) -> Dict[str, Any]:
    """Calculates Basel III / Basel IV Capital Adequacy, Leverage, and Liquidity Ratios:
    - CET1, Tier 1, and Total Capital Adequacy Ratios (CAR) against RWAs.
    - Basel Leverage Ratio (Tier 1 / Total On- and Off-Balance Sheet Exposure).
    - Liquidity Coverage Ratio (LCR = HQLA / Net Outflows >= 100%).
    - Net Stable Funding Ratio (NSFR = Available Stable Funding / Required Stable Funding >= 100%).
    - Combined Buffer Requirement (CCB + CCyB + G-SIB) & Capital Surplus/Deficit.
    """
    total_rwa = rwa_credit + rwa_market + rwa_operational
    if total_rwa <= 0.0:
        return {"error": "Toplam Risk Ağırlıklı Varlıklar (RWA) pozitif olmalıdır."}
    if total_exposure_leverage <= 0.0:
        return {"error": "Kaldıraç maruziyeti (total_exposure_leverage) pozitif olmalıdır."}
    if net_cash_outflows_30d <= 0.0:
        return {"error": "30 günlük net nakit çıkışı pozitif olmalıdır."}
    if rsf_amount <= 0.0:
        return {"error": "Gerekli istikrarlı fonlama (rsf_amount) pozitif olmalıdır."}

    # Capital ratios
    cet1_ratio_pct = round((cet1_capital / total_rwa) * 100.0, 3)
    tier1_ratio_pct = round((tier1_capital / total_rwa) * 100.0, 3)
    car_ratio_pct = round((total_capital / total_rwa) * 100.0, 3)
    leverage_ratio_pct = round((tier1_capital / total_exposure_leverage) * 100.0, 3)

    # Liquidity ratios
    lcr_pct = round((hqla_amount / net_cash_outflows_30d) * 100.0, 2)
    nsfr_pct = round((asf_amount / rsf_amount) * 100.0, 2)

    # Regulatory thresholds under Basel III / IV
    combined_buffer_pct = capital_conservation_buffer_pct + countercyclical_buffer_pct + gsib_surcharge_pct
    min_cet1_required_pct = round(4.5 + combined_buffer_pct, 2)
    min_tier1_required_pct = round(6.0 + combined_buffer_pct, 2)
    min_car_required_pct = round(8.0 + combined_buffer_pct, 2)
    min_leverage_required_pct = 3.0
    min_lcr_required_pct = 100.0
    min_nsfr_required_pct = 100.0

    cet1_pass = cet1_ratio_pct >= min_cet1_required_pct
    tier1_pass = tier1_ratio_pct >= min_tier1_required_pct
    car_pass = car_ratio_pct >= min_car_required_pct
    leverage_pass = leverage_ratio_pct >= min_leverage_required_pct
    lcr_pass = lcr_pct >= min_lcr_required_pct
    nsfr_pass = nsfr_pct >= min_nsfr_required_pct

    # Surplus/Deficit amounts (in same unit as capital)
    cet1_required_capital = total_rwa * (min_cet1_required_pct / 100.0)
    cet1_surplus_amount = round(cet1_capital - cet1_required_capital, 3)

    car_required_capital = total_rwa * (min_car_required_pct / 100.0)
    car_surplus_amount = round(total_capital - car_required_capital, 3)

    hqla_surplus_amount = round(hqla_amount - net_cash_outflows_30d, 3)
    asf_surplus_amount = round(asf_amount - rsf_amount, 3)

    all_passed = cet1_pass and tier1_pass and car_pass and leverage_pass and lcr_pass and nsfr_pass

    if all_passed and cet1_surplus_amount > 0 and lcr_pct >= 120.0:
        buffer_status = "Kuvvetli Sermaye ve Likidite Fazlası (Well-Capitalized & High Buffer)"
    elif all_passed:
        buffer_status = "Yasal Sınırların Üzerinde / Dengeli Tampon (Adequately Capitalized)"
    elif not car_pass or not cet1_pass:
        buffer_status = "KRİTİK SERMAYE YETERSİZLİĞİ: MDA Dağıtım Kısıtı ve Müdahale Riski"
    else:
        buffer_status = "LİKİDİTE VEYA KALDIRAÇ İHLALİ: Acil Düzeltici Eylem Gerekli"

    return {
        "total_rwa": round(total_rwa, 2),
        "rwa_credit_pct": round((rwa_credit / total_rwa) * 100.0, 2),
        "rwa_market_pct": round((rwa_market / total_rwa) * 100.0, 2),
        "rwa_operational_pct": round((rwa_operational / total_rwa) * 100.0, 2),
        "cet1_ratio_pct": cet1_ratio_pct,
        "tier1_ratio_pct": tier1_ratio_pct,
        "total_capital_ratio_pct": car_ratio_pct,
        "leverage_ratio_pct": leverage_ratio_pct,
        "lcr_pct": lcr_pct,
        "nsfr_pct": nsfr_pct,
        "combined_buffer_pct": combined_buffer_pct,
        "regulatory_compliance": {
            "cet1_compliant": cet1_pass,
            "min_cet1_required_pct": min_cet1_required_pct,
            "tier1_compliant": tier1_pass,
            "min_tier1_required_pct": min_tier1_required_pct,
            "car_compliant": car_pass,
            "min_car_required_pct": min_car_required_pct,
            "leverage_compliant": leverage_pass,
            "min_leverage_required_pct": min_leverage_required_pct,
            "lcr_compliant": lcr_pass,
            "min_lcr_required_pct": min_lcr_required_pct,
            "nsfr_compliant": nsfr_pass,
            "min_nsfr_required_pct": min_nsfr_required_pct,
            "overall_compliant": all_passed
        },
        "surplus_deficit": {
            "cet1_surplus": cet1_surplus_amount,
            "car_surplus": car_surplus_amount,
            "hqla_surplus": hqla_surplus_amount,
            "asf_surplus": asf_surplus_amount
        },
        "buffer_status": buffer_status
    }


def calculate_convertible_bond_and_arbitrage(
    bond_price: float,
    par_value: float,
    conversion_ratio: float,
    stock_price: float,
    coupon_rate_pct: float,
    stock_dividend_yield_pct: float,
    bond_floor: float,
    option_delta: float,
    credit_spread_bps: float = 250.0
) -> Dict[str, Any]:
    """Calculates Convertible Bond (CB) Valuation and Delta-Neutral Arbitrage:
    - Parity (Conversion Value = Conversion Ratio * Stock Price).
    - Conversion Premium % and Investment Premium % (Distance from Bond Floor).
    - Delta Hedge Ratio and optimal stock short sale sizing.
    - Premium payback / Break-even period (in years).
    - Profile categorization: Busted (Debt-like), Balanced (Hybrid Sweet Spot), or Equity-Surrogate.
    """
    if par_value <= 0.0 or conversion_ratio <= 0.0 or stock_price <= 0.0 or bond_price <= 0.0:
        return {"error": "Fiyatlar, nominal değer ve dönüştürme oranı pozitif olmalıdır."}
    if bond_floor <= 0.0:
        return {"error": "Tahvil tabanı (bond_floor) pozitif olmalıdır."}

    # Conversion value (Parity)
    conversion_value = round(conversion_ratio * stock_price, 2)

    # Conversion premium % = (Bond Price - Parity) / Parity
    conversion_premium_pct = round(((bond_price - conversion_value) / conversion_value) * 100.0, 2)

    # Investment premium % = (Bond Price - Bond Floor) / Bond Floor
    investment_premium_pct = round(((bond_price - bond_floor) / bond_floor) * 100.0, 2)

    # Downside protection cushion % = (Bond Price - Bond Floor) / Bond Price
    downside_risk_to_floor_pct = round(max(0.0, ((bond_price - bond_floor) / bond_price) * 100.0), 2)

    # Delta Hedge: Number of stock shares to short per 1 convertible bond
    delta_clamped = max(0.01, min(0.99, option_delta))
    shares_short_per_bond = round(conversion_ratio * delta_clamped, 3)

    # Income advantage per bond = (Coupon in $) - (Dividend in $ on converted shares)
    coupon_income_dollar = par_value * (coupon_rate_pct / 100.0)
    dividend_income_dollar = (conversion_ratio * stock_price) * (stock_dividend_yield_pct / 100.0)
    net_income_advantage_dollar = coupon_income_dollar - dividend_income_dollar

    # Premium payback / break-even years
    dollar_premium = bond_price - conversion_value
    if dollar_premium <= 0.0:
        break_even_years = 0.0
    elif net_income_advantage_dollar > 0.0:
        break_even_years = round(dollar_premium / net_income_advantage_dollar, 2)
    else:
        break_even_years = float("inf")

    # Convertible bond profile categorization
    if delta_clamped < 0.30 or conversion_premium_pct > 60.0:
        profile = "Kırık / Busted CB (Borç Dinamiği Egemen - Yüksek Kredi Riski / Faiz Hassasiyeti)"
        arbitrage_strategy = "Distressed borç takası veya saf kredi marjı daralması oyunu; hisse opsiyon değeri ihmal edilebilir."
    elif delta_clamped > 0.80 and conversion_premium_pct < 15.0:
        profile = "Hisse Vekili / Equity Surrogate (Derin ITM - Yüksek Hisse Korelasyonu)"
        arbitrage_strategy = "Delta ~ 1.0; hisse senediyle neredeyse birebir hareket eder, aşağı yönlü koruma tabanı uzaktır."
    else:
        profile = "Dengeli / Hibrit Dönüştürülebilir (Asimetrik Konveksite & Gama Tatlı Noktası)"
        arbitrage_strategy = "Klasik CB Arbitrajı: Uzun Tahvil + Kısa Delta Hisse. Gama ölçekleme ve ucuz volatilite çıkarma fırsatı."

    # Estimated credit spread sensitivity (Omicron / Credit Duration proxy)
    credit_duration_years = max(1.0, round(bond_floor / (par_value * max(0.02, coupon_rate_pct / 100.0) + 1.0), 2))
    omicron_sensitivity_pct = round(credit_duration_years * 1.0, 2)

    return {
        "bond_price": bond_price,
        "par_value": par_value,
        "conversion_ratio": conversion_ratio,
        "conversion_value_parity": conversion_value,
        "conversion_premium_pct": conversion_premium_pct,
        "bond_floor": bond_floor,
        "investment_premium_pct": investment_premium_pct,
        "downside_risk_to_floor_pct": downside_risk_to_floor_pct,
        "option_delta": delta_clamped,
        "delta_hedge_shares_short_per_bond": shares_short_per_bond,
        "coupon_income_dollar": round(coupon_income_dollar, 2),
        "dividend_income_dollar": round(dividend_income_dollar, 2),
        "net_income_advantage_dollar": round(net_income_advantage_dollar, 2),
        "break_even_years": break_even_years if break_even_years != float("inf") else 999.0,
        "cb_profile": profile,
        "arbitrage_strategy": arbitrage_strategy,
        "credit_duration_years": credit_duration_years,
        "omicron_spread_widening_impact_pct": omicron_sensitivity_pct
    }


def calculate_barrier_and_digital_options(
    spot_price: float,
    strike_price: float,
    barrier_level: float,
    time_to_expiry_years: float,
    risk_free_rate_pct: float,
    volatility_pct: float,
    option_type: str = "call",
    barrier_type: str = "up-and-out",
    cash_or_nothing_payout: float = 10.0
) -> Dict[str, Any]:
    """Calculates Single Barrier Options (Reiner-Rubinstein analytical closed-form),
    In-Out Parity, Digital/Binary Option Payouts, and Pin Risk/Discontinuous Greeks:
    - Barrier Types: 'up-and-out', 'up-and-in', 'down-and-out', 'down-and-in'
    - Digital Options: Cash-or-Nothing Call/Put & Asset-or-Nothing Call/Put
    - Pin Risk: Distance to barrier and cliff effect on delta/gamma
    """
    if spot_price <= 0.0 or strike_price <= 0.0 or barrier_level <= 0.0:
        return {"error": "Spot, kullanım fiyatı ve bariyer seviyesi pozitif olmalıdır."}
    if time_to_expiry_years <= 0.0 or volatility_pct <= 0.0:
        return {"error": "Vadeye kalan süre ve volatilite pozitif olmalıdır."}

    S = spot_price
    K = strike_price
    H = barrier_level
    T = time_to_expiry_years
    r = risk_free_rate_pct / 100.0
    sigma = volatility_pct / 100.0
    opt = option_type.lower().strip()
    b_type = barrier_type.lower().strip()

    # Black-Scholes standard vanilla variables
    sqrt_T = math.sqrt(T)
    sigma_sqrt_T = sigma * sqrt_T
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / sigma_sqrt_T
    d2 = d1 - sigma_sqrt_T
    discount = math.exp(-r * T)

    vanilla_call = S * _norm_cdf(d1) - K * discount * _norm_cdf(d2)
    vanilla_put = K * discount * _norm_cdf(-d2) - S * _norm_cdf(-d1)
    vanilla_price = vanilla_call if opt == "call" else vanilla_put

    # Digital Options
    digital_cash_call = cash_or_nothing_payout * discount * _norm_cdf(d2)
    digital_cash_put = cash_or_nothing_payout * discount * _norm_cdf(-d2)

    digital_asset_call = S * _norm_cdf(d1)
    digital_asset_put = S * _norm_cdf(-d1)

    # Analytical Barrier Option Pricing Components (Reiner-Rubinstein / Merton)
    mu = (r - 0.5 * sigma * sigma) / (sigma * sigma)
    lambda_param = 1.0 + mu

    phi = 1.0 if opt == "call" else -1.0
    eta = 1.0 if "down" in b_type else -1.0

    x1 = (math.log(S / K)) / sigma_sqrt_T + lambda_param * sigma_sqrt_T
    x2 = (math.log(S / H)) / sigma_sqrt_T + lambda_param * sigma_sqrt_T
    y1 = (math.log((H * H) / (S * K))) / sigma_sqrt_T + lambda_param * sigma_sqrt_T
    y2 = (math.log(H / S)) / sigma_sqrt_T + lambda_param * sigma_sqrt_T

    def _term_A():
        return phi * S * _norm_cdf(phi * x1) - phi * K * discount * _norm_cdf(phi * x1 - phi * sigma_sqrt_T)

    def _term_B():
        return phi * S * _norm_cdf(phi * x2) - phi * K * discount * _norm_cdf(phi * x2 - phi * sigma_sqrt_T)

    def _term_C():
        h_s_ratio = (H / S)
        return (phi * S * (h_s_ratio ** (2.0 * lambda_param)) * _norm_cdf(eta * y1) -
                phi * K * discount * (h_s_ratio ** (2.0 * mu)) * _norm_cdf(eta * y1 - eta * sigma_sqrt_T))

    def _term_D():
        h_s_ratio = (H / S)
        return (phi * S * (h_s_ratio ** (2.0 * lambda_param)) * _norm_cdf(eta * y2) -
                phi * K * discount * (h_s_ratio ** (2.0 * mu)) * _norm_cdf(eta * y2 - eta * sigma_sqrt_T))

    A = _term_A()
    B = _term_B()
    C = _term_C()
    D = _term_D()

    # Calculate specific barrier option prices
    barrier_price = 0.0
    parity_counterpart_price = 0.0

    if opt == "call":
        if b_type == "down-and-out":
            if S <= H:
                barrier_price = 0.0
            elif K >= H:
                barrier_price = max(0.0, A - C)
            else:
                barrier_price = max(0.0, B - D)
            parity_counterpart_price = max(0.0, vanilla_call - barrier_price)
        elif b_type == "down-and-in":
            if S <= H:
                barrier_price = vanilla_call
            elif K >= H:
                barrier_price = max(0.0, C)
            else:
                barrier_price = max(0.0, A - B + D)
            parity_counterpart_price = max(0.0, vanilla_call - barrier_price)
        elif b_type == "up-and-out":
            if S >= H:
                barrier_price = 0.0
            elif K >= H:
                barrier_price = 0.0
            else:
                barrier_price = max(0.0, A - B + C - D)
            parity_counterpart_price = max(0.0, vanilla_call - barrier_price)
        elif b_type == "up-and-in":
            if S >= H:
                barrier_price = vanilla_call
            elif K >= H:
                barrier_price = vanilla_call
            else:
                barrier_price = max(0.0, B - C + D)
            parity_counterpart_price = max(0.0, vanilla_call - barrier_price)
        else:
            return {"error": f"Geçersiz bariyer türü: {barrier_type}"}
    else:  # put
        if b_type == "down-and-out":
            if S <= H:
                barrier_price = 0.0
            elif K <= H:
                barrier_price = 0.0
            else:
                barrier_price = max(0.0, A - B + C - D)
            parity_counterpart_price = max(0.0, vanilla_put - barrier_price)
        elif b_type == "down-and-in":
            if S <= H:
                barrier_price = vanilla_put
            elif K <= H:
                barrier_price = vanilla_put
            else:
                barrier_price = max(0.0, B - C + D)
            parity_counterpart_price = max(0.0, vanilla_put - barrier_price)
        elif b_type == "up-and-out":
            if S >= H:
                barrier_price = 0.0
            elif K <= H:
                barrier_price = max(0.0, A - C)
            else:
                barrier_price = max(0.0, B - D)
            parity_counterpart_price = max(0.0, vanilla_put - barrier_price)
        elif b_type == "up-and-in":
            if S >= H:
                barrier_price = vanilla_put
            elif K <= H:
                barrier_price = max(0.0, C)
            else:
                barrier_price = max(0.0, A - B + D)
            parity_counterpart_price = max(0.0, vanilla_put - barrier_price)
        else:
            return {"error": f"Geçersiz bariyer türü: {barrier_type}"}

    # Pin risk and distance to barrier in volatility standard deviations
    distance_to_barrier_pct = round(abs(S - H) / S * 100.0, 2)
    vol_standard_deviation_move = S * sigma * sqrt_T
    distance_in_sigmas = round(abs(S - H) / max(1e-5, vol_standard_deviation_move), 2)

    if distance_in_sigmas < 0.5:
        pin_risk_level = "AŞIRI YÜKSEK PIN RISKI (Uçurum Etkisi / Discontinuous Greeks Cliff)"
        hedging_note = "Bariyer seviyesine aşırı yakın: Gama ve Delta işaret değiştirebilir, dinamik koruma maliyeti patlar."
    elif distance_in_sigmas < 1.5:
        pin_risk_level = "ORTA / DİKKAT (Artan Gama Oynaklığı)"
        hedging_note = "Bariyer etki alanında: Vanilla opsiyonlarla statik süper-replikasyon koruması önerilir."
    else:
        pin_risk_level = "DÜŞÜK PIN RİSKİ (Güvenli Bölge)"
        hedging_note = "Spot bariyerden yeterince uzakta; standart delta-hedging çalıştırılabilir."

    return {
        "spot_price": S,
        "strike_price": K,
        "barrier_level": H,
        "time_to_expiry_years": T,
        "volatility_pct": volatility_pct,
        "option_type": opt.upper(),
        "barrier_type": b_type,
        "barrier_price": round(barrier_price, 4),
        "vanilla_benchmark_price": round(vanilla_price, 4),
        "parity_counterpart_price": round(parity_counterpart_price, 4),
        "in_out_parity_error": round(abs((barrier_price + parity_counterpart_price) - vanilla_price), 6),
        "digital_options": {
            "cash_or_nothing_price": round(digital_cash_call if opt == "call" else digital_cash_put, 4),
            "asset_or_nothing_price": round(digital_asset_call if opt == "call" else digital_asset_put, 4),
            "payout_cash_amount": cash_or_nothing_payout
        },
        "pin_risk_metrics": {
            "distance_to_barrier_pct": distance_to_barrier_pct,
            "distance_in_sigmas": distance_in_sigmas,
            "pin_risk_level": pin_risk_level,
            "hedging_advisory": hedging_note
        }
    }


def calculate_kalman_dynamic_pairs_trading(
    price_series_y: List[float],
    price_series_x: List[float],
    delta: float = 1e-4,
    vt_variance: float = 1e-3
) -> Dict[str, Any]:
    """Applies a 2-State Recursive Kalman Filter for Dynamic Pairs Trading:
    State equation: theta_t = theta_{t-1} + w_t, where theta = [alpha, beta]^T, w_t ~ N(0, Q_t)
    Observation equation: y_t = H_t theta_t + v_t, where H_t = [1, x_t], v_t ~ N(0, R)
    - Computes time-varying beta and alpha that instantaneously adjust to regime shifts.
    - Generates dynamic measurement innovation spread (e_t) and adaptive Z-Score (e_t / sqrt(F_t)).
    """
    if len(price_series_y) != len(price_series_x):
        return {"error": "Y ve X fiyat serileri aynı uzunlukta olmalıdır."}
    n = len(price_series_y)
    if n < 5:
        return {"error": "Kalman filtresi için en az 5 gözlem noktası gereklidir."}

    # Initialize state theta = [alpha, beta]^T
    alpha = 0.0
    beta = price_series_y[0] / price_series_x[0] if price_series_x[0] != 0 else 1.0
    P = [[1.0, 0.0], [0.0, 1.0]]  # State covariance
    R = max(1e-6, vt_variance)     # Observation variance

    betas: List[float] = []
    alphas: List[float] = []
    innovations: List[float] = []
    z_scores: List[float] = []

    for t in range(n):
        x_t = price_series_x[t]
        y_t = price_series_y[t]

        # 1. State prediction: theta_{t|t-1} = theta_{t-1}
        # Covariance prediction: P_{t|t-1} = P_{t-1} + Q_t
        q_scale = delta / (1.0 - delta) if delta < 1.0 else 1e-4
        P[0][0] += q_scale * max(1e-8, P[0][0])
        P[1][1] += q_scale * max(1e-8, P[1][1])

        # 2. Observation vector H_t = [1, x_t]
        # Measurement prediction y_hat = alpha + beta * x_t
        y_hat = alpha + beta * x_t
        e_t = y_t - y_hat  # Innovation (Spread)

        # 3. Innovation variance F_t = H P H^T + R
        hp0 = P[0][0] + x_t * P[1][0]
        hp1 = P[0][1] + x_t * P[1][1]
        F_t = hp0 * 1.0 + hp1 * x_t + R
        F_t = max(1e-8, F_t)

        # 4. Kalman Gain K_t = P H^T / F_t
        k0 = (P[0][0] + P[0][1] * x_t) / F_t
        k1 = (P[1][0] + P[1][1] * x_t) / F_t

        # 5. State update
        alpha += k0 * e_t
        beta += k1 * e_t

        # 6. Covariance update P = (I - K H) P
        P[0][0] -= k0 * hp0
        P[0][1] -= k0 * hp1
        P[1][0] -= k1 * hp0
        P[1][1] -= k1 * hp1

        z_t = e_t / math.sqrt(F_t)

        betas.append(round(beta, 4))
        alphas.append(round(alpha, 4))
        innovations.append(round(e_t, 4))
        z_scores.append(round(z_t, 3))

    latest_z = z_scores[-1]
    latest_beta = betas[-1]
    latest_alpha = alphas[-1]
    latest_spread = innovations[-1]

    # Trading signal generation based on dynamic Z-score
    if latest_z >= 2.0:
        signal = "SHORT_SPREAD: Y sat, Beta*X al (Aşırı Değerlenmiş Yayılma)"
    elif latest_z <= -2.0:
        signal = "LONG_SPREAD: Y al, Beta*X sat (Aşırı Düşmüş Yayılma)"
    elif abs(latest_z) <= 0.5:
        signal = "CLOSE_POSITION: Yayılma dengeye ulaştı (Kâr Al / Kapat)"
    else:
        signal = "HOLD / NEUTRAL: Yayılma normal salınım bandında"

    # Detect structural break if beta moved substantially over the series
    beta_range = max(betas) - min(betas)
    structural_break = beta_range > (0.4 * abs(betas[0]))

    return {
        "num_observations": n,
        "latest_beta": latest_beta,
        "latest_alpha": latest_alpha,
        "latest_spread_innovation": latest_spread,
        "latest_z_score": latest_z,
        "trading_signal": signal,
        "structural_break_detected": structural_break,
        "beta_drift_range": round(beta_range, 4),
        "history_summary": {
            "initial_beta": betas[0],
            "min_beta": min(betas),
            "max_beta": max(betas),
            "mean_z_score": round(sum(z_scores) / n, 3),
            "recent_z_scores": z_scores[-5:]
        }
    }


def calculate_omega_ratio_and_ulcer_index(
    returns_pct: List[float],
    threshold_pct: float = 0.0,
    risk_free_rate_annual_pct: float = 4.0,
    periods_per_year: int = 252
) -> Dict[str, Any]:
    """Calculates Omega Ratio (asymmetric probability distribution of gains vs losses),
    Ulcer Index & Pain Index (quadratic & absolute depth-duration drawdown metrics),
    Martin Ratio, Calmar Ratio, and Higher Distribution Moments (Skewness & Kurtosis).
    """
    if not returns_pct or len(returns_pct) < 3:
        return {"error": "En az 3 periyotluk getiri serisi girilmelidir."}

    n = len(returns_pct)
    L = threshold_pct

    # 1. Omega Ratio: Area of Gains above L / Area of Losses below L
    sum_gains_above_L = sum(max(0.0, r - L) for r in returns_pct)
    sum_losses_below_L = sum(max(0.0, L - r) for r in returns_pct)

    if sum_losses_below_L == 0.0:
        omega_ratio = 999.0
    else:
        omega_ratio = round(sum_gains_above_L / sum_losses_below_L, 3)

    # 2. Cumulative Equity Curve & Drawdown Series
    equity = [100.0]
    for r in returns_pct:
        equity.append(equity[-1] * (1.0 + r / 100.0))

    peak = equity[0]
    drawdowns_pct: List[float] = []
    current_dd_duration = 0
    max_dd_duration = 0

    for val in equity:
        if val > peak:
            peak = val
            current_dd_duration = 0
        else:
            current_dd_duration += 1
            if current_dd_duration > max_dd_duration:
                max_dd_duration = current_dd_duration

        dd = ((val - peak) / peak) * 100.0
        drawdowns_pct.append(dd)

    max_drawdown_pct = round(abs(min(drawdowns_pct)), 2)

    # 3. Ulcer Index: Quadratic root-mean-square of drawdowns
    squared_dds = [dd * dd for dd in drawdowns_pct]
    ulcer_index = round(math.sqrt(sum(squared_dds) / len(squared_dds)), 3)

    # Pain Index: Mean absolute drawdown
    pain_index = round(sum(abs(dd) for dd in drawdowns_pct) / len(drawdowns_pct), 3)

    # 4. Performance Ratios: CAGR, Calmar, Martin
    total_compounded_return = (equity[-1] / equity[0]) - 1.0
    years = n / periods_per_year
    if years > 0 and equity[-1] > 0:
        cagr_pct = round(((equity[-1] / equity[0]) ** (1.0 / years) - 1.0) * 100.0, 2)
    else:
        cagr_pct = round(total_compounded_return * 100.0, 2)

    rf = risk_free_rate_annual_pct
    excess_cagr = cagr_pct - rf

    martin_ratio = round(excess_cagr / ulcer_index, 2) if ulcer_index > 0 else 999.0
    calmar_ratio = round(cagr_pct / max_drawdown_pct, 2) if max_drawdown_pct > 0 else 999.0

    # 5. Distribution Moments: Skewness & Kurtosis
    mean_r = sum(returns_pct) / n
    variance_r = sum((r - mean_r) ** 2 for r in returns_pct) / (n - 1)
    std_r = math.sqrt(variance_r) if variance_r > 0 else 1e-8

    skewness = round(sum((r - mean_r) ** 3 for r in returns_pct) / (n * (std_r ** 3)), 3)
    excess_kurtosis = round((sum((r - mean_r) ** 4 for r in returns_pct) / (n * (std_r ** 4))) - 3.0, 3)

    if skewness > 0.5:
        distribution_note = "Pozitif Asimetri (Sağ Çarpık - Nadir Büyük Kazançlar, Sınırlı Kayıplar)"
    elif skewness < -0.5:
        distribution_note = "Negatif Asimetri (Sol Çarpık - Ani Kuyruk Çöküş Riski / Solucan Deliği)"
    else:
        distribution_note = "Simetrik Dağılım (Normal Dağılıma Yakın)"

    return {
        "num_periods": n,
        "threshold_pct": L,
        "omega_ratio": omega_ratio,
        "gain_area": round(sum_gains_above_L, 2),
        "loss_area": round(sum_losses_below_L, 2),
        "max_drawdown_pct": max_drawdown_pct,
        "max_drawdown_duration_periods": max_dd_duration,
        "ulcer_index": ulcer_index,
        "pain_index": pain_index,
        "cagr_pct": cagr_pct,
        "martin_ratio": martin_ratio,
        "calmar_ratio": calmar_ratio,
        "skewness": skewness,
        "excess_kurtosis": excess_kurtosis,
        "distribution_profile": distribution_note
    }


def main():
    parser = argparse.ArgumentParser(description="Basel IV, Convertible Bond, Exotic Barrier, Kalman & Downside Risk CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Basel subparser
    p_basel = subparsers.add_parser("basel", help="Basel III / IV Capital & Liquidity Ratios")
    p_basel.add_argument("--cet1", type=float, required=True)
    p_basel.add_argument("--tier1", type=float, required=True)
    p_basel.add_argument("--total-capital", type=float, required=True)
    p_basel.add_argument("--rwa-credit", type=float, required=True)
    p_basel.add_argument("--rwa-market", type=float, required=True)
    p_basel.add_argument("--rwa-op", type=float, required=True)
    p_basel.add_argument("--leverage-exp", type=float, required=True)
    p_basel.add_argument("--hqla", type=float, required=True)
    p_basel.add_argument("--outflows-30d", type=float, required=True)
    p_basel.add_argument("--asf", type=float, required=True)
    p_basel.add_argument("--rsf", type=float, required=True)

    # Convertible Bond subparser
    p_cb = subparsers.add_parser("convertible", help="Convertible Bond Arbitrage & Greeks")
    p_cb.add_argument("--bond-price", type=float, required=True)
    p_cb.add_argument("--par", type=float, required=True)
    p_cb.add_argument("--conversion-ratio", type=float, required=True)
    p_cb.add_argument("--stock-price", type=float, required=True)
    p_cb.add_argument("--coupon-pct", type=float, required=True)
    p_cb.add_argument("--div-yield-pct", type=float, required=True)
    p_cb.add_argument("--bond-floor", type=float, required=True)
    p_cb.add_argument("--delta", type=float, required=True)

    # Barrier Options subparser
    p_barrier = subparsers.add_parser("barrier", help="Exotic Barrier & Digital Options")
    p_barrier.add_argument("--spot", type=float, required=True)
    p_barrier.add_argument("--strike", type=float, required=True)
    p_barrier.add_argument("--barrier", type=float, required=True)
    p_barrier.add_argument("--expiry", type=float, required=True)
    p_barrier.add_argument("--rate-pct", type=float, required=True)
    p_barrier.add_argument("--vol-pct", type=float, required=True)
    p_barrier.add_argument("--option-type", type=str, default="call")
    p_barrier.add_argument("--barrier-type", type=str, default="up-and-out")

    # Kalman Pairs Trading subparser
    p_kalman = subparsers.add_parser("kalman", help="Kalman Filter Dynamic Pairs Trading")
    p_kalman.add_argument("--series-y", type=str, required=True, help="Comma-separated prices for Asset Y")
    p_kalman.add_argument("--series-x", type=str, required=True, help="Comma-separated prices for Asset X")

    # Omega & Ulcer subparser
    p_omega = subparsers.add_parser("omega", help="Omega Ratio & Ulcer Index Downside Profile")
    p_omega.add_argument("--returns", type=str, required=True, help="Comma-separated returns in percent")
    p_omega.add_argument("--threshold", type=float, default=0.0)

    args = parser.parse_args()

    if args.command == "basel":
        res = calculate_basel_capital_and_liquidity(
            cet1_capital=args.cet1,
            tier1_capital=args.tier1,
            total_capital=args.total_capital,
            rwa_credit=args.rwa_credit,
            rwa_market=args.rwa_market,
            rwa_operational=args.rwa_op,
            total_exposure_leverage=args.leverage_exp,
            hqla_amount=args.hqla,
            net_cash_outflows_30d=args.outflows_30d,
            asf_amount=args.asf,
            rsf_amount=args.rsf
        )
    elif args.command == "convertible":
        res = calculate_convertible_bond_and_arbitrage(
            bond_price=args.bond_price,
            par_value=args.par,
            conversion_ratio=args.conversion_ratio,
            stock_price=args.stock_price,
            coupon_rate_pct=args.coupon_pct,
            stock_dividend_yield_pct=args.div_yield_pct,
            bond_floor=args.bond_floor,
            option_delta=args.delta
        )
    elif args.command == "barrier":
        res = calculate_barrier_and_digital_options(
            spot_price=args.spot,
            strike_price=args.strike,
            barrier_level=args.barrier,
            time_to_expiry_years=args.expiry,
            risk_free_rate_pct=args.rate_pct,
            volatility_pct=args.vol_pct,
            option_type=args.option_type,
            barrier_type=args.barrier_type
        )
    elif args.command == "kalman":
        y_vals = [float(v.strip()) for v in args.series_y.split(",") if v.strip()]
        x_vals = [float(v.strip()) for v in args.series_x.split(",") if v.strip()]
        res = calculate_kalman_dynamic_pairs_trading(y_vals, x_vals)
    elif args.command == "omega":
        rets = [float(v.strip()) for v in args.returns.split(",") if v.strip()]
        res = calculate_omega_ratio_and_ulcer_index(rets, threshold_pct=args.threshold)
    else:
        res = {"error": "Bilinmeyen komut."}

    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
