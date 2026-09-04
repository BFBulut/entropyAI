#!/usr/bin/env python3
"""CLI and library utility for Volatility Surface, Yield Curve Butterfly PCA, M&A Collars & Crypto Arbitrage:
- Dupire Local Volatility & Sticky Strike vs Sticky Moneyness Skew Dynamics
- Fixed Income Yield Curve PCA Decomposition (Level, Slope, Curvature/Butterfly) & Convexity Bias
- M&A Floating/Fixed Collar Mechanics & Contingent Value Rights (CVR) Valuation
- Crypto Perpetual Funding Rate Cash-and-Carry Arbitrage & Concentrated Liquidity (Uniswap v3)
- Corporate Treasury Layered FX Hedging Ladder & Mark-to-Market Margin Stress Testing
"""

import argparse
import json
import math
from typing import Dict, Any, List, Optional


def calculate_dupire_local_volatility_and_bias(
    implied_vol_pct: float,
    dvol_dt_pct: float,
    dvol_dk_pct: float,
    d2vol_dk2_pct: float,
    strike_k: float,
    spot_s: float,
    time_to_maturity: float,
    risk_free_r_pct: float = 4.0
) -> Dict[str, Any]:
    """Calculates Dupire Local Volatility from Black-Scholes Implied Volatility Surface:
    Approximated Dupire formulation:
    sigma_loc^2 = (sigma_imp^2 + 2*sigma_imp*T*(dvol/dT) + 2*r*K*T*sigma_imp*(dvol/dK)) / Denominator
    Also evaluates Sticky Strike vs Sticky Moneyness (Delta) regimes.
    """
    if implied_vol_pct <= 0 or strike_k <= 0 or spot_s <= 0 or time_to_maturity <= 0:
        return {"error": "Volatilite, strike, spot ve vade pozitif olmalıdır."}

    sigma = implied_vol_pct / 100.0
    r = risk_free_r_pct / 100.0
    T = time_to_maturity
    K = strike_k
    S = spot_s

    dvol_dt = dvol_dt_pct / 100.0
    dvol_dk = dvol_dk_pct / 100.0
    d2vol_dk2 = d2vol_dk2_pct / 100.0

    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))

    numerator = sigma * sigma + 2.0 * sigma * T * dvol_dt + 2.0 * r * K * T * sigma * dvol_dk

    term1 = 1.0 + K * d1 * math.sqrt(T) * dvol_dk
    term2 = K * K * T * sigma * (d2vol_dk2 - d1 * math.sqrt(T) * (dvol_dk * dvol_dk))
    denominator = (term1 * term1) + term2

    if denominator <= 0 or numerator <= 0:
        local_vol = sigma  # fallback to implied vol if surface slope leads to arbitrage violation
        is_arbitrage_violation = True
    else:
        local_vol = math.sqrt(numerator / denominator)
        is_arbitrage_violation = False

    moneyness = S / K
    if abs(dvol_dk_pct) > 0.005:
        skew_regime = "GÜÇLÜ NEGATİF ÇARPIKLIK (Downside Put talebi / Crash Hedge primi yüksek)" if dvol_dk_pct < 0 else "POZİTİF ÇARPIKLIK (Upside Call primi)"
    else:
        skew_regime = "DÜZ VOLATİLİTE YÜZEYİ (ATM civarında simetrik dağılım)"

    return {
        "spot_price": round(spot_s, 2),
        "strike_price": round(strike_k, 2),
        "moneyness_ratio": round(moneyness, 3),
        "time_to_maturity_years": round(time_to_maturity, 2),
        "implied_volatility_pct": round(implied_vol_pct, 2),
        "dupire_local_volatility_pct": round(local_vol * 100.0, 2),
        "local_vs_implied_spread_pct": round((local_vol - sigma) * 100.0, 2),
        "calendar_slope_dvol_dt": round(dvol_dt_pct, 4),
        "strike_slope_dvol_dk": round(dvol_dk_pct, 4),
        "skew_regime_diagnosis": skew_regime,
        "arbitrage_free_surface": not is_arbitrage_violation
    }


def calculate_pca_yield_curve_and_butterfly(
    yield_2y_pct: float,
    yield_5y_pct: float,
    yield_10y_pct: float,
    yield_30y_pct: float,
    rate_volatility_pct: float = 1.0
) -> Dict[str, Any]:
    """Calculates Yield Curve PCA-style Factors (Level, Slope, Curvature) and Butterfly Spread:
    Level Factor = (Y_2y + Y_5y + Y_10y + Y_30y) / 4
    Slope (2y-10y) = Y_10y - Y_2y (getiri eğrisi eğimi)
    Slope (2y-30y) = Y_30y - Y_2y
    Curvature / 5Y Butterfly = 2 * Y_5y - (Y_2y + Y_10y)
    Convexity Bias (Futures vs Forward Swap) = 0.5 * sigma^2 * t1 * t2
    """
    level = (yield_2y_pct + yield_5y_pct + yield_10y_pct + yield_30y_pct) / 4.0
    slope_2_10 = yield_10y_pct - yield_2y_pct
    slope_2_30 = yield_30y_pct - yield_2y_pct
    butterfly_5y_bps = (2.0 * yield_5y_pct - (yield_2y_pct + yield_10y_pct)) * 100.0

    # Convexity Bias between 3M Eurodollar/SOFR Futures and 5Y Forward Swap
    sigma_rate = rate_volatility_pct / 100.0
    t1 = 0.25  # 3 ay
    t2 = 5.0   # 5 yıl
    convexity_bias_bps = (0.5 * sigma_rate * sigma_rate * t1 * t2) * 10000.0

    if slope_2_10 < 0:
        slope_diagnosis = "TERSİNE DÖNMÜŞ GETİRİ EĞRİSİ (Resesyon öncü sinyali / İnversiyon)"
    elif slope_2_10 < 0.5:
        slope_diagnosis = "YATIKLAŞMIŞ GETİRİ EĞRİSİ (Sıkılaştırıcı para politikası baskısı)"
    else:
        slope_diagnosis = "DİK / NORMAL GETİRİ EĞRİSİ (Ekonomik büyüme ve normal getiri primi)"

    if butterfly_5y_bps > 10.0:
        butterfly_diagnosis = "GÖBEK KAMBURU (Belly Hump: 5 yıllık tahvil faizi 2Y ve 10Y'ye göre pahalı/yüksek faiz)"
    elif butterfly_5y_bps < -10.0:
        butterfly_diagnosis = "ÇUKURLAŞMA (Belly Dip: 5 yıllık tahvilde göreceli talep yoğunluğu / zengin değerleme)"
    else:
        butterfly_diagnosis = "DENGELİ KELEBEK DAĞILIMI (Nötr eğrilik)"

    return {
        "yield_2y_pct": round(yield_2y_pct, 3),
        "yield_5y_pct": round(yield_5y_pct, 3),
        "yield_10y_pct": round(yield_10y_pct, 3),
        "yield_30y_pct": round(yield_30y_pct, 3),
        "pca_level_factor_pct": round(level, 3),
        "slope_2y_10y_pct": round(slope_2_10, 3),
        "slope_2y_30y_pct": round(slope_2_30, 3),
        "butterfly_5y_bps": round(butterfly_5y_bps, 2),
        "convexity_bias_bps": round(convexity_bias_bps, 2),
        "curve_slope_diagnosis": slope_diagnosis,
        "butterfly_diagnosis": butterfly_diagnosis
    }


def calculate_ma_collar_and_cvr(
    buyer_stock_price: float,
    lower_collar_floor: float,
    upper_collar_cap: float,
    base_exchange_ratio: float,
    cvr_cash_payout: float = 0.0,
    cvr_success_probability_pct: float = 50.0,
    cvr_years_to_payout: float = 2.0,
    discount_rate_pct: float = 8.0
) -> Dict[str, Any]:
    """Calculates M&A Floating/Fixed Collar Payout and Contingent Value Rights (CVR) Present Value:
    - If Buyer Price between Floor and Cap -> Fixed Exchange Ratio applies.
    - If Buyer Price < Floor -> Exchange ratio expands to maintain minimum value OR floor value holds.
    - If Buyer Price > Cap -> Exchange ratio contracts to cap acquirer dilution.
    - CVR Present Value = (Payout * Probability) / (1 + discount_rate)^years
    """
    if buyer_stock_price <= 0 or lower_collar_floor <= 0 or upper_collar_cap <= 0 or base_exchange_ratio <= 0:
        return {"error": "Fiyatlar ve değişim oranı sıfırdan büyük olmalıdır."}
    if lower_collar_floor >= upper_collar_cap:
        return {"error": "lower_collar_floor, upper_collar_cap değerinden küçük olmalıdır."}

    # Collar exchange ratio logic (Fixed value collar)
    if buyer_stock_price < lower_collar_floor:
        effective_ratio = (base_exchange_ratio * lower_collar_floor) / buyer_stock_price
        collar_status = "TABAN DEVREYE GİRDİ (Alıcı hissesi düştü; hedef hissedarı korumak için değişim oranı artırıldı)"
    elif buyer_stock_price > upper_collar_cap:
        effective_ratio = (base_exchange_ratio * upper_collar_cap) / buyer_stock_price
        collar_status = "TAVAN DEVREYE GİRDİ (Alıcı hissesi yükseldi; sulanmayı önlemek için değişim oranı düşürüldü)"
    else:
        effective_ratio = base_exchange_ratio
        collar_status = "KORİDOR İÇİNDE (Sabit baz değişim oranı geçerli)"

    equity_offer_value_per_share = effective_ratio * buyer_stock_price

    # CVR Present Value
    r = discount_rate_pct / 100.0
    p = cvr_success_probability_pct / 100.0
    cvr_pv = (cvr_cash_payout * p) / math.pow(1.0 + r, cvr_years_to_payout) if cvr_cash_payout > 0 else 0.0

    total_consideration_per_share = equity_offer_value_per_share + cvr_pv

    return {
        "buyer_stock_price": round(buyer_stock_price, 2),
        "lower_collar_floor": round(lower_collar_floor, 2),
        "upper_collar_cap": round(upper_collar_cap, 2),
        "base_exchange_ratio": round(base_exchange_ratio, 4),
        "effective_exchange_ratio": round(effective_ratio, 4),
        "collar_status": collar_status,
        "equity_offer_value_per_share": round(equity_offer_value_per_share, 2),
        "cvr_cash_payout": round(cvr_cash_payout, 2),
        "cvr_success_probability_pct": round(cvr_success_probability_pct, 2),
        "cvr_present_value": round(cvr_pv, 2),
        "total_consideration_per_share": round(total_consideration_per_share, 2)
    }


def calculate_crypto_basis_and_concentrated_liquidity(
    spot_price: float,
    perp_mark_price: float,
    funding_rate_8h_pct: float,
    lp_lower_tick_price: float,
    lp_upper_tick_price: float
) -> Dict[str, Any]:
    """Calculates Perpetual Funding Rate Basis Arbitrage (Cash-and-Carry) and Uniswap v3 Capital Efficiency:
    - Annualized Funding Yield (APR) = Funding Rate (8h) * 3 * 365
    - Basis Spread = (Perp Price - Spot Price) / Spot Price
    - Uniswap v3 Capital Efficiency Multiplier: E = 1 / (1 - sqrt(P_lower / P_upper))
    """
    if spot_price <= 0 or perp_mark_price <= 0 or lp_lower_tick_price <= 0 or lp_upper_tick_price <= 0:
        return {"error": "Fiyatlar pozitif olmalıdır."}
    if lp_lower_tick_price >= lp_upper_tick_price:
        return {"error": "lp_lower_tick_price, lp_upper_tick_price değerinden küçük olmalıdır."}

    basis_spread_pct = ((perp_mark_price - spot_price) / spot_price) * 100.0
    apr_pct = funding_rate_8h_pct * 3.0 * 365.0

    # Uniswap v3 Capital Efficiency
    ratio = lp_lower_tick_price / lp_upper_tick_price
    capital_efficiency = 1.0 / (1.0 - math.sqrt(ratio))

    in_range = lp_lower_tick_price <= spot_price <= lp_upper_tick_price

    if apr_pct > 15.0:
        strategy = "YÜKSEK POZİTİF TAŞIMA (CASH-AND-CARRY: Spot al + 1x Short Perp aç; çift haneli risksiz fonlama faizi topla)"
    elif apr_pct < -10.0:
        strategy = "TERS TAŞIMA (REVERSE CASH-AND-CARRY: Spot sat/kısa + Long Perp aç; negatif fonlama ödemesinden yararlan)"
    else:
        strategy = "DENGELİ / NÖTR FONLAMA (Düşük arbitraj marjı)"

    return {
        "spot_price": round(spot_price, 2),
        "perp_mark_price": round(perp_mark_price, 2),
        "basis_spread_pct": round(basis_spread_pct, 3),
        "funding_rate_8h_pct": round(funding_rate_8h_pct, 4),
        "annualized_funding_apr_pct": round(apr_pct, 2),
        "arbitrage_strategy_recommendation": strategy,
        "lp_price_range": [round(lp_lower_tick_price, 2), round(lp_upper_tick_price, 2)],
        "lp_in_range": in_range,
        "uniswap_v3_capital_efficiency_multiplier": round(capital_efficiency, 2)
    }


def calculate_layered_fx_hedging(
    quarterly_exposure_usd: float,
    current_spot_usdtry: float,
    q1_hedge_ratio_pct: float = 80.0,
    q2_hedge_ratio_pct: float = 60.0,
    q3_hedge_ratio_pct: float = 40.0,
    q4_hedge_ratio_pct: float = 20.0,
    forward_points_annual_pct: float = 35.0
) -> Dict[str, Any]:
    """Calculates Corporate Treasury Layered Dynamic FX Hedging Ladder & MTM Margin Stress:
    Layered hedging protects against cash-flow volatility while leaving room for market upside.
    Forward Rate = Spot * (1 + forward_points_annual_pct * (t/12))
    MTM shock test: Evaluates cash liquidity drain under a +/- 10% sudden spot FX gap.
    """
    if quarterly_exposure_usd <= 0 or current_spot_usdtry <= 0:
        return {"error": "Döviz maruziyeti ve spot kur pozitif olmalıdır."}

    ratios = [q1_hedge_ratio_pct, q2_hedge_ratio_pct, q3_hedge_ratio_pct, q4_hedge_ratio_pct]
    quarters = ["Q1 (1-3 Ay)", "Q2 (4-6 Ay)", "Q3 (7-9 Ay)", "Q4 (10-12 Ay)"]
    fwd_rates = []
    hedged_amounts = []
    unhedged_amounts = []

    for i, ratio in enumerate(ratios):
        t_years = (i + 1) * 0.25
        fwd = current_spot_usdtry * (1.0 + (forward_points_annual_pct / 100.0) * t_years)
        fwd_rates.append(fwd)
        hedged_amounts.append(quarterly_exposure_usd * (ratio / 100.0))
        unhedged_amounts.append(quarterly_exposure_usd * (1.0 - ratio / 100.0))

    total_exposure = quarterly_exposure_usd * 4.0
    total_hedged = sum(hedged_amounts)
    total_unhedged = sum(unhedged_amounts)
    overall_hedge_ratio_pct = (total_hedged / total_exposure) * 100.0

    blended_hedged_rate = sum(h * f for h, f in zip(hedged_amounts, fwd_rates)) / total_hedged if total_hedged > 0 else current_spot_usdtry

    # 10% FX adverse shock on forward contracts (MTM Margin Call liability)
    shock_spot = current_spot_usdtry * 0.90
    mtm_loss_usd = total_hedged * (1.0 - (shock_spot / current_spot_usdtry))

    return {
        "quarterly_exposure_usd": round(quarterly_exposure_usd, 2),
        "annual_total_exposure_usd": round(total_exposure, 2),
        "current_spot_rate": round(current_spot_usdtry, 3),
        "layered_hedge_ratios_pct": ratios,
        "projected_forward_rates": [round(f, 3) for f in fwd_rates],
        "total_hedged_usd": round(total_hedged, 2),
        "total_unhedged_usd": round(total_unhedged, 2),
        "overall_hedge_ratio_pct": round(overall_hedge_ratio_pct, 2),
        "blended_average_hedged_rate": round(blended_hedged_rate, 3),
        "fx_shock_10pct_mtm_liquidity_drain_usd": round(mtm_loss_usd, 2),
        "hedging_policy_diagnosis": "OPTIMAL KATMANLI KORUMA (Nakit akışı dalgalanması minimize edilirken kur kazancı esnekliği korunuyor)"
    }


def main():
    parser = argparse.ArgumentParser(description="Volatility Surface, PCA Butterfly, M&A Collars & Crypto Arbitrage CLI")
    subparsers = parser.add_subparsers(dest="command", help="Alt komutlar")

    # Dupire
    dup_parser = subparsers.add_parser("dupire", help="Dupire Yerel Volatilite ve Skew Analizi")
    dup_parser.add_argument("--iv", type=float, required=True, help="İma Edilen Oynaklık (%)")
    dup_parser.add_argument("--dvol-dt", type=float, required=True, help="Zaman eğimi (dvol/dT)")
    dup_parser.add_argument("--dvol-dk", type=float, required=True, help="Kullanım fiyatı eğimi (dvol/dK)")
    dup_parser.add_argument("--d2vol-dk2", type=float, default=0.0001, help="İkinci türev (d2vol/dK2)")
    dup_parser.add_argument("--strike", type=float, required=True, help="Kullanım Fiyatı (K)")
    dup_parser.add_argument("--spot", type=float, required=True, help="Spot Fiyat (S)")
    dup_parser.add_argument("--maturity", type=float, required=True, help="Vade (Yıl)")
    dup_parser.add_argument("--rate", type=float, default=4.0, help="Risksiz faiz (%)")

    # PCA Butterfly
    pca_parser = subparsers.add_parser("butterfly", help="Faiz Eğrisi PCA Seviye, Eğim ve Kelebek Dağılımı")
    pca_parser.add_argument("--y2", type=float, required=True, help="2 Yıllık Getiri (%)")
    pca_parser.add_argument("--y5", type=float, required=True, help="5 Yıllık Getiri (%)")
    pca_parser.add_argument("--y10", type=float, required=True, help="10 Yıllık Getiri (%)")
    pca_parser.add_argument("--y30", type=float, required=True, help="30 Yıllık Getiri (%)")
    pca_parser.add_argument("--rate-vol", type=float, default=1.0, help="Faiz volatilitesi (%)")

    # Collar M&A
    collar_parser = subparsers.add_parser("collar", help="M&A Collar (Yaka) ve CVR Değerlemesi")
    collar_parser.add_argument("--buyer-price", type=float, required=True, help="Alıcı Hisse Fiyatı")
    collar_parser.add_argument("--floor", type=float, required=True, help="Taban Fiyat (Floor)")
    collar_parser.add_argument("--cap", type=float, required=True, help="Tavan Fiyat (Cap)")
    collar_parser.add_argument("--ratio", type=float, required=True, help="Baz Değişim Oranı")
    collar_parser.add_argument("--cvr-payout", type=float, default=0.0, help="CVR Nakit Ödemesi")
    collar_parser.add_argument("--cvr-prob", type=float, default=50.0, help="CVR Başarı Olasılığı (%)")
    collar_parser.add_argument("--cvr-years", type=float, default=2.0, help="CVR Vadesi (Yıl)")
    collar_parser.add_argument("--discount-rate", type=float, default=8.0, help="İskonto Oranı (%)")

    # Crypto Basis
    crypto_parser = subparsers.add_parser("crypto-basis", help="Kripto Perpetual Fonlama Arbitrajı ve Uniswap v3")
    crypto_parser.add_argument("--spot", type=float, required=True, help="Spot Fiyat")
    crypto_parser.add_argument("--perp", type=float, required=True, help="Perp Mark Fiyatı")
    crypto_parser.add_argument("--funding", type=float, required=True, help="8 Saatlik Fonlama Oranı (%)")
    crypto_parser.add_argument("--lp-lower", type=float, required=True, help="LP Alt Fiyat Sınırı")
    crypto_parser.add_argument("--lp-upper", type=float, required=True, help="LP Üst Fiyat Sınırı")

    # FX Layered
    fx_parser = subparsers.add_parser("fx-layered", help="Katmanlı Dinamik Döviz Koruma Merdiveni")
    fx_parser.add_argument("--exposure", type=float, required=True, help="Çeyreklik Döviz Maruziyeti ($)")
    fx_parser.add_argument("--spot", type=float, required=True, help="Spot Kur")
    fx_parser.add_argument("--q1", type=float, default=80.0, help="Q1 Koruma Oranı (%)")
    fx_parser.add_argument("--q2", type=float, default=60.0, help="Q2 Koruma Oranı (%)")
    fx_parser.add_argument("--q3", type=float, default=40.0, help="Q3 Koruma Oranı (%)")
    fx_parser.add_argument("--q4", type=float, default=20.0, help="Q4 Koruma Oranı (%)")
    fx_parser.add_argument("--forward-pts", type=float, default=35.0, help="Yıllık Forward Primi (%)")

    args = parser.parse_args()

    if args.command == "dupire":
        res = calculate_dupire_local_volatility_and_bias(
            args.iv, args.dvol_dt, args.dvol_dk, args.d2vol_dk2,
            args.strike, args.spot, args.maturity, args.rate
        )
    elif args.command == "butterfly":
        res = calculate_pca_yield_curve_and_butterfly(
            args.y2, args.y5, args.y10, args.y30, args.rate_vol
        )
    elif args.command == "collar":
        res = calculate_ma_collar_and_cvr(
            args.buyer_price, args.floor, args.cap, args.ratio,
            args.cvr_payout, args.cvr_prob, args.cvr_years, args.discount_rate
        )
    elif args.command == "crypto-basis":
        res = calculate_crypto_basis_and_concentrated_liquidity(
            args.spot, args.perp, args.funding, args.lp_lower, args.lp_upper
        )
    elif args.command == "fx-layered":
        res = calculate_layered_fx_hedging(
            args.exposure, args.spot, args.q1, args.q2, args.q3, args.q4, args.forward_pts
        )
    else:
        parser.print_help()
        return

    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
