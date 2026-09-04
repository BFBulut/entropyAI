#!/usr/bin/env python3
"""CLI and library utility for Factor Investing, SABR Swaptions, Fed Balance Sheet Liquidity & IFRS-16 Forensics:
- Time-Series Momentum (TSMOM / Trend Following) & Volatility Scaling (Moskowitz et al.)
- Share Buyback vs Debt Economics (Earnings Yield vs After-tax Cost of Debt True Value Creation)
- IFRS-16 / ASC-842 Lease Capitalization & EBITDA/Net Debt Distortion Analysis
- SABR (Stochastic Alpha Beta Rho) Swaption Volatility Model (Hagan et al.)
- Fed Balance Sheet Liquidity Drain/Injection Engine (Bank Reserves, TGA, ON RRP & Fed Assets)
"""

import argparse
import json
import math
from typing import Dict, Any, List, Optional


def calculate_time_series_momentum(
    past_returns_12m: float,
    recent_daily_volatility: float,
    annual_target_volatility: float = 0.15
) -> Dict[str, Any]:
    """Calculates Time-Series Momentum (TSMOM / Trend-Following) signal and volatility-scaled position sizing.
    Moskowitz, Ooi, Pedersen (2012):
    Signal: sign(R_12m) in {-1, +1}
    Position weight: w_t = (TargetVol / AnnualizedVol_t) * sign(R_12m)
    """
    if recent_daily_volatility <= 0:
        return {"error": "recent_daily_volatility sıfırdan büyük olmalıdır."}
    if annual_target_volatility <= 0:
        return {"error": "annual_target_volatility sıfırdan büyük olmalıdır."}

    annualized_vol = recent_daily_volatility * math.sqrt(252)
    
    if past_returns_12m > 0.001:
        signal = 1
        trend_direction = "LONG / YÜKSELİŞ TRENDİ (12 aylık kümülatif getiri pozitif)"
    elif past_returns_12m < -0.001:
        signal = -1
        trend_direction = "SHORT / DÜŞÜŞ TRENDİ (12 aylık kümülatif getiri negatif)"
    else:
        signal = 0
        trend_direction = "NÖTR / YATAY PİYASA (Trend sinyali yetersiz)"

    raw_weight = (annual_target_volatility / annualized_vol) * signal if annualized_vol > 0 else 0.0
    # Capped at 2.0x leverage for risk management
    clipped_weight = max(-2.0, min(2.0, raw_weight))

    return {
        "past_12m_return_pct": round(past_returns_12m * 100, 2),
        "recent_daily_volatility_pct": round(recent_daily_volatility * 100, 2),
        "annualized_realized_volatility_pct": round(annualized_vol * 100, 2),
        "target_annual_volatility_pct": round(annual_target_volatility * 100, 2),
        "trend_signal": signal,
        "trend_direction": trend_direction,
        "volatility_scaled_position_weight": round(clipped_weight, 3),
        "leverage_applied": round(abs(clipped_weight), 2)
    }


def calculate_share_buyback_roi(
    share_price: float,
    eps: float,
    debt_interest_rate_pct: float,
    corporate_tax_rate_pct: float = 25.0
) -> Dict[str, Any]:
    """Evaluates whether a debt-funded Share Buyback creates genuine economic value or merely engineers EPS:
    Earnings Yield = EPS / Share Price = 1 / (P/E)
    After-tax Cost of Debt = Interest Rate * (1 - Tax Rate)
    If Earnings Yield > After-Tax Cost of Debt -> Genuine Value Creation (Accretive & Economically Sound).
    If Earnings Yield < After-Tax Cost of Debt -> Value Destruction (EPS artar ancak özkaynak maliyetini karşılamaz).
    """
    if share_price <= 0:
        return {"error": "share_price sıfırdan büyük olmalıdır."}
    if eps == 0:
        return {"error": "eps sıfır olamaz."}
    if debt_interest_rate_pct < 0 or corporate_tax_rate_pct < 0 or corporate_tax_rate_pct >= 100:
        return {"error": "Geçersiz faiz veya vergi oranı."}

    earnings_yield_pct = (eps / share_price) * 100.0
    pe_ratio = share_price / eps if eps > 0 else float("nan")
    after_tax_debt_cost_pct = debt_interest_rate_pct * (1.0 - (corporate_tax_rate_pct / 100.0))
    economic_spread_pct = earnings_yield_pct - after_tax_debt_cost_pct

    if economic_spread_pct > 1.0:
        verdict = "GERÇEK DEĞER YARATAN GERİ ALIM (Earnings Yield > Borçlanma Maliyeti: Şirket hisselerini ucuza alarak kalıcı hissedar değeri üretiyor)"
    elif economic_spread_pct < -1.0:
        verdict = "DEĞER YOK EDEN HİSSE GERİ ALIMI (Earnings Yield < Borçlanma Maliyeti: Finansal mühendislikle EPS artırılıyor fakat şirketin gerçek sermaye maliyeti aşınıyor)"
    else:
        verdict = "NÖTR / BAŞABAŞ GERİ ALIM (Getiri ile borçlanma maliyeti dengede)"

    return {
        "share_price": round(share_price, 2),
        "eps": round(eps, 2),
        "pe_ratio": round(pe_ratio, 2) if not math.isnan(pe_ratio) else None,
        "earnings_yield_pct": round(earnings_yield_pct, 2),
        "after_tax_debt_cost_pct": round(after_tax_debt_cost_pct, 2),
        "economic_spread_pct": round(economic_spread_pct, 2),
        "buyback_evaluation": verdict
    }


def calculate_ifrs16_lease_capitalization(
    annual_lease_payment: float,
    lease_term_years: int,
    discount_rate_pct: float,
    reported_ebitda: float,
    reported_net_debt: float
) -> Dict[str, Any]:
    """Calculates IFRS-16 / ASC-842 Operating Lease Capitalization and evaluates EBITDA & Net Debt distortions:
    PV of Lease Liability = Payment * [1 - (1 + r)^(-n)] / r
    Adjusted EBITDA = Reported EBITDA + Annual Lease Payment (kira gideri operasyonel giderden çıkar, amortisman ve faize dönüşür)
    Adjusted Net Debt = Reported Net Debt + PV of Lease Liability
    """
    if annual_lease_payment <= 0 or lease_term_years <= 0 or discount_rate_pct <= 0:
        return {"error": "Kira ödemesi, vade ve iskonto oranı sıfırdan büyük olmalıdır."}

    r = discount_rate_pct / 100.0
    n = lease_term_years
    annuity_factor = (1.0 - math.pow(1.0 + r, -n)) / r
    pv_lease_liability = annual_lease_payment * annuity_factor

    adjusted_ebitda = reported_ebitda + annual_lease_payment
    adjusted_net_debt = reported_net_debt + pv_lease_liability

    unadjusted_leverage = (reported_net_debt / reported_ebitda) if reported_ebitda > 0 else float("inf")
    adjusted_leverage = (adjusted_net_debt / adjusted_ebitda) if adjusted_ebitda > 0 else float("inf")

    return {
        "annual_lease_payment": round(annual_lease_payment, 2),
        "lease_term_years": lease_term_years,
        "discount_rate_pct": round(discount_rate_pct, 2),
        "pv_capitalized_lease_liability": round(pv_lease_liability, 2),
        "reported_ebitda": round(reported_ebitda, 2),
        "adjusted_ebitda": round(adjusted_ebitda, 2),
        "ebitda_inflation_pct": round((annual_lease_payment / reported_ebitda) * 100, 2) if reported_ebitda > 0 else 0.0,
        "reported_net_debt": round(reported_net_debt, 2),
        "adjusted_net_debt": round(adjusted_net_debt, 2),
        "reported_leverage_ratio": round(unadjusted_leverage, 2),
        "adjusted_leverage_ratio": round(adjusted_leverage, 2),
        "leverage_delta": round(adjusted_leverage - unadjusted_leverage, 2)
    }


def calculate_sabr_implied_volatility(
    forward_rate: float,
    strike_rate: float,
    time_to_maturity: float,
    alpha: float,
    beta: float,
    rho: float,
    nu: float
) -> Dict[str, Any]:
    """Calculates At-The-Money and Near-the-Money Implied Volatility using the SABR Model (Hagan et al., 2002):
    dF_t = alpha_t * F_t^beta * dW_t^F
    d(alpha_t) = nu * alpha_t * dW_t^alpha
    Cov(dW^F, dW^alpha) = rho * dt
    """
    if forward_rate <= 0 or strike_rate <= 0 or time_to_maturity <= 0 or alpha <= 0 or nu <= 0:
        return {"error": "F, K, T, alpha ve nu pozitif olmalıdır."}
    if not (-1.0 <= rho <= 1.0):
        return {"error": "rho korelasyonu [-1, 1] aralığında olmalıdır."}
    if not (0.0 <= beta <= 1.0):
        return {"error": "beta esneklik katsayısı [0, 1] aralığında olmalıdır."}

    F = forward_rate
    K = strike_rate
    T = time_to_maturity

    # ATM Implied Volatility Hagan et al. formula
    if abs(F - K) < 1e-6:
        term1 = alpha / math.pow(F, 1.0 - beta)
        bracket = 1.0 + (
            (math.pow(1.0 - beta, 2) / 24.0) * (alpha * alpha / math.pow(F, 2.0 - 2.0 * beta))
            + (0.25 * rho * beta * nu * alpha / math.pow(F, 1.0 - beta))
            + ((2.0 - 3.0 * rho * rho) / 24.0) * (nu * nu)
        ) * T
        sigma_sabr = term1 * bracket
    else:
        # Near-ATM Hagan approximation
        F_mid = math.sqrt(F * K)
        log_FK = math.log(F / K)
        z = (nu / alpha) * math.pow(F_mid, 1.0 - beta) * log_FK
        x_z = math.log((math.sqrt(1.0 - 2.0 * rho * z + z * z) + z - rho) / (1.0 - rho)) if abs(z) > 1e-6 else 1.0
        zeta_factor = z / x_z if abs(z) > 1e-6 else 1.0

        denom = math.pow(F_mid, 1.0 - beta) * (
            1.0
            + (math.pow(1.0 - beta, 2) / 24.0) * (log_FK * log_FK)
            + (math.pow(1.0 - beta, 4) / 1920.0) * math.pow(log_FK, 4)
        )
        bracket = 1.0 + (
            (math.pow(1.0 - beta, 2) / 24.0) * (alpha * alpha / math.pow(F_mid, 2.0 - 2.0 * beta))
            + (0.25 * rho * beta * nu * alpha / math.pow(F_mid, 1.0 - beta))
            + ((2.0 - 3.0 * rho * rho) / 24.0) * (nu * nu)
        ) * T
        sigma_sabr = (alpha / denom) * zeta_factor * bracket

    return {
        "forward_rate": round(forward_rate, 4),
        "strike_rate": round(strike_rate, 4),
        "time_to_maturity_years": round(time_to_maturity, 2),
        "alpha_initial_vol": round(alpha, 4),
        "beta_elasticity": round(beta, 2),
        "rho_correlation": round(rho, 3),
        "nu_vol_of_vol": round(nu, 3),
        "sabr_implied_volatility_pct": round(sigma_sabr * 100, 3),
        "volatility_skew_diagnosis": "GÜÇLÜ NEGATİF ÇARPIKLIK / PUT PRİMİ" if rho < -0.3 else ("POZİTİF ÇARPIKLIK / CALL PRİMİ" if rho > 0.3 else "SİMETRİK VOLATİLİTE GÜLÜŞÜ")
    }


def calculate_on_rrp_tga_liquidity_drain(
    start_bank_reserves: float,
    delta_tga: float,
    delta_on_rrp: float,
    delta_fed_assets: float = 0.0
) -> Dict[str, Any]:
    """Calculates Net Liquidity changes in the US Financial Plumbing based on Fed Balance Sheet Identity:
    Delta Bank Reserves = Delta Fed Assets - Delta TGA - Delta ON_RRP
    - TGA artışı (Hazine borçlanması / vergi) banka rezervlerini çeker (Liquidity Drain).
    - ON RRP artışı para piyasası fonlarını Fed'e kilitler (Liquidity Drain).
    - TGA veya ON RRP azalışı piyasaya doğrudan nakit enjekte eder (Liquidity Injection).
    """
    delta_reserves = delta_fed_assets - delta_tga - delta_on_rrp
    end_bank_reserves = start_bank_reserves + delta_reserves

    if delta_reserves > 50.0:
        regime = "GÜÇLÜ LİKİDİTE ENJEKSİYONU (Banka rezervleri artıyor, hisse senedi ve riskli varlıklar için destekleyici rüzgar)"
    elif delta_reserves < -50.0:
        regime = "ŞİDDETLİ LİKİDİTE ÇEKİLİŞİ / DRAIN (TGA/RRP rezervleri emiyor, volatilite ve tahvil faizlerinde yukarı baskı)"
    else:
        regime = "DENGELİ / NÖTR LİKİDİTE AKIŞI (Rezerv seviyesi kararlı)"

    return {
        "start_bank_reserves_billion_usd": round(start_bank_reserves, 2),
        "delta_fed_assets_billion_usd": round(delta_fed_assets, 2),
        "delta_tga_billion_usd": round(delta_tga, 2),
        "delta_on_rrp_billion_usd": round(delta_on_rrp, 2),
        "net_liquidity_change_billion_usd": round(delta_reserves, 2),
        "end_bank_reserves_billion_usd": round(end_bank_reserves, 2),
        "liquidity_regime_diagnosis": regime
    }


def main():
    parser = argparse.ArgumentParser(description="Factor Investing, SABR & Fed Plumbing Analytics CLI")
    subparsers = parser.add_subparsers(dest="command", help="Alt komutlar")

    # TSMOM
    tsmom_parser = subparsers.add_parser("tsmom", help="Time-Series Momentum ve Volatilite Boyutlandırma")
    tsmom_parser.add_argument("--returns-12m", type=float, required=True, help="12 aylık kümülatif getiri")
    tsmom_parser.add_argument("--daily-vol", type=float, required=True, help="Günlük volatilite")
    tsmom_parser.add_argument("--target-vol", type=float, default=0.15, help="Hedef yıllık volatilite (varsayılan: 0.15)")

    # Buyback ROI
    bb_parser = subparsers.add_parser("buyback", help="Hisse Geri Alımı Değer Yaratım Testi")
    bb_parser.add_argument("--price", type=float, required=True, help="Hisse fiyatı")
    bb_parser.add_argument("--eps", type=float, required=True, help="Hisse Başı Kâr (EPS)")
    bb_parser.add_argument("--debt-rate", type=float, required=True, help="Borçlanma faiz oranı (%)")
    bb_parser.add_argument("--tax-rate", type=float, default=25.0, help="Kurumlar vergisi oranı (%)")

    # IFRS-16 Leases
    lease_parser = subparsers.add_parser("ifrs16", help="IFRS-16 Faaliyet Kiralaması Kapitalizasyonu")
    lease_parser.add_argument("--payment", type=float, required=True, help="Yıllık kira ödemesi")
    lease_parser.add_argument("--years", type=int, required=True, help="Kira vadesi (yıl)")
    lease_parser.add_argument("--discount-rate", type=float, required=True, help="İskonto oranı (%)")
    lease_parser.add_argument("--ebitda", type=float, required=True, help="Raporlanan EBITDA")
    lease_parser.add_argument("--net-debt", type=float, required=True, help="Raporlanan Net Borç")

    # SABR
    sabr_parser = subparsers.add_parser("sabr", help="SABR Faiz Swaption Volatilite Modeli")
    sabr_parser.add_argument("--forward", type=float, required=True, help="Forward faiz oranı")
    sabr_parser.add_argument("--strike", type=float, required=True, help="Kullanım faiz oranı (Strike)")
    sabr_parser.add_argument("--maturity", type=float, required=True, help="Vade (yıl)")
    sabr_parser.add_argument("--alpha", type=float, required=True, help="Başlangıç volatilitesi (alpha)")
    sabr_parser.add_argument("--beta", type=float, required=True, help="Esneklik parametresi (beta)")
    sabr_parser.add_argument("--rho", type=float, required=True, help="Korelasyon (rho)")
    sabr_parser.add_argument("--nu", type=float, required=True, help="Vol of Vol (nu)")

    # Fed Plumbing
    fed_parser = subparsers.add_parser("fed-plumbing", help="Fed Bilanço Likidite Borulaması")
    fed_parser.add_argument("--start-reserves", type=float, required=True, help="Başlangıç banka rezervleri ($ Milyar)")
    fed_parser.add_argument("--delta-tga", type=float, required=True, help="TGA değişimi ($ Milyar)")
    fed_parser.add_argument("--delta-rrp", type=float, required=True, help="ON RRP değişimi ($ Milyar)")
    fed_parser.add_argument("--delta-assets", type=float, default=0.0, help="Fed varlıkları değişimi ($ Milyar)")

    args = parser.parse_args()

    if args.command == "tsmom":
        res = calculate_time_series_momentum(args.returns_12m, args.daily_vol, args.target_vol)
    elif args.command == "buyback":
        res = calculate_share_buyback_roi(args.price, args.eps, args.debt_rate, args.tax_rate)
    elif args.command == "ifrs16":
        res = calculate_ifrs16_lease_capitalization(args.payment, args.years, args.discount_rate, args.ebitda, args.net_debt)
    elif args.command == "sabr":
        res = calculate_sabr_implied_volatility(args.forward, args.strike, args.maturity, args.alpha, args.beta, args.rho, args.nu)
    elif args.command == "fed-plumbing":
        res = calculate_on_rrp_tga_liquidity_drain(args.start_reserves, args.delta_tga, args.delta_rrp, args.delta_assets)
    else:
        parser.print_help()
        return

    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
