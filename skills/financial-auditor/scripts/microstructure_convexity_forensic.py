#!/usr/bin/env python3
"""CLI and library utility for Market Microstructure, Yield Curve Dynamics & Forensic Financial Analytics:
- VPIN (Volume-Synchronized Probability of Toxicity) Order Flow Imbalance
- Almgren-Chriss Optimal Execution & Market Impact Trajectory
- Dechow F-Score (Accounting Manipulation & Restatement Probability)
- Piotroski F-Score (9-Point Fundamental Financial Health Assessment)
- Nelson-Siegel Yield Curve Term Structure Model (Level, Slope, Curvature)
- Heston Stochastic Volatility Model & Feller Condition Verification
"""

import argparse
import json
import math
from typing import Dict, Any, List, Optional


def calculate_vpin(
    buy_volumes: List[float],
    sell_volumes: List[float],
    bucket_size: float
) -> Dict[str, Any]:
    """Calculates the Volume-Synchronized Probability of Toxicity (VPIN):
    VPIN = sum(|V_tau^B - V_tau^S|) / (N * V)
    where N is the number of volume buckets and V is bucket_size.
    """
    if not buy_volumes or not sell_volumes:
        return {"error": "buy_volumes ve sell_volumes boş olamaz."}
    if len(buy_volumes) != len(sell_volumes):
        return {"error": "buy_volumes ve sell_volumes uzunlukları eşit olmalıdır."}
    if bucket_size <= 0:
        return {"error": "bucket_size sıfırdan büyük olmalıdır."}

    n_buckets = len(buy_volumes)
    total_imbalance = 0.0
    bucket_details = []

    for i in range(n_buckets):
        b = buy_volumes[i]
        s = sell_volumes[i]
        if b < 0 or s < 0:
            return {"error": "Hacim değerleri negatif olamaz."}
        imbalance = abs(b - s)
        total_imbalance += imbalance
        bucket_details.append({
            "bucket_index": i + 1,
            "buy_volume": round(b, 2),
            "sell_volume": round(s, 2),
            "imbalance": round(imbalance, 2)
        })

    vpin = total_imbalance / (n_buckets * bucket_size)

    if vpin > 0.35:
        regime = "AŞIRI YÜKSEK TOKSİSİTE / TOXIC ORDER FLOW (Piyasa yapıcılar likiditeyi çekiyor, Flash Crash ve ani likidite buharlaşması riski)"
    elif vpin >= 0.20:
        regime = "ORTA DÜZEY TOKSİSİTE (Bilgi sahibi kurumsal trader baskısı mevcut, spread'ler genişleyebilir)"
    else:
        regime = "DÜŞÜK TOKSİSİTE / GÜRÜLTÜ TİCARETİ (Sağlıklı iki taraflı likidite akışı, piyasa yapıcı envanter riski düşük)"

    return {
        "number_of_buckets": n_buckets,
        "bucket_size": round(bucket_size, 2),
        "total_absolute_imbalance": round(total_imbalance, 2),
        "vpin_score": round(vpin, 4),
        "vpin_percentage": round(vpin * 100, 2),
        "toxicity_regime": regime,
        "bucket_details": bucket_details
    }


def calculate_almgren_chriss_trajectory(
    total_shares: float,
    time_horizon_days: int,
    intervals: int,
    temporary_impact_eta: float,
    risk_aversion_lambda: float,
    daily_volatility_sigma: float
) -> Dict[str, Any]:
    """Calculates the Almgren-Chriss optimal liquidation trajectory:
    Balances market impact (liquidation cost) against inventory volatility risk.
    kappa = sqrt((lambda * sigma^2) / eta)
    x_j = sinh(kappa * (T - t_j)) / sinh(kappa * T) * X_0
    """
    if total_shares <= 0:
        return {"error": "total_shares sıfırdan büyük olmalıdır."}
    if time_horizon_days <= 0 or intervals <= 0:
        return {"error": "time_horizon_days ve intervals pozitif tam sayı olmalıdır."}
    if temporary_impact_eta <= 0 or risk_aversion_lambda < 0 or daily_volatility_sigma <= 0:
        return {"error": "eta, lambda ve sigma geçerli pozitif değerler olmalıdır."}

    T = float(time_horizon_days)
    dt = T / intervals

    if risk_aversion_lambda == 0.0:
        kappa = 0.0
    else:
        kappa_sq = (risk_aversion_lambda * (daily_volatility_sigma ** 2)) / temporary_impact_eta
        kappa = math.sqrt(kappa_sq)

    trajectory = []
    current_shares = total_shares

    for step in range(intervals + 1):
        t = step * dt
        if kappa == 0.0:
            remaining = total_shares * (1.0 - (t / T))
        else:
            sinh_total = math.sinh(kappa * T)
            if sinh_total == 0:
                remaining = total_shares * (1.0 - (t / T))
            else:
                remaining = total_shares * (math.sinh(kappa * (T - t)) / sinh_total)

        shares_to_sell = current_shares - remaining if step > 0 else 0.0
        trajectory.append({
            "step": step,
            "time_days": round(t, 2),
            "remaining_shares": round(max(0.0, remaining), 2),
            "sold_shares": round(max(0.0, shares_to_sell), 2)
        })
        current_shares = remaining

    if kappa > 1.5:
        urgency = "AGRESİF ÖNDEN YÜKLEMELİ İCRA (Front-Loaded: Yüksek volatilite/riskten kaçınma, ilk yarıda hızlı satış)"
    elif kappa > 0.3:
        urgency = "DENGELİ OPTİMAL İCRA (Market Impact ve volatilite riski dengeli dağıtılmış)"
    else:
        urgency = "LİNEER / TWAP BENZERİ PASİF İCRA (Düşük riskten kaçınma, geçici etkiyi minimize etmeye odaklı)"

    return {
        "total_initial_shares": round(total_shares, 2),
        "time_horizon_days": time_horizon_days,
        "intervals": intervals,
        "kappa_urgency_parameter": round(kappa, 4),
        "execution_strategy_profile": urgency,
        "trajectory": trajectory
    }


def calculate_dechow_f_score(
    accruals_pct: float,
    receivables_change_pct: float,
    inventory_change_pct: float,
    soft_assets_pct: float,
    cash_sales_growth_pct: float,
    roa_change: float
) -> Dict[str, Any]:
    """Calculates the Dechow et al. (2011) F-Score for accounting manipulation and restatement risk:
    Logit = -7.383 + 4.037*Accruals + 0.188*dReceivables + 0.192*dInventory + 0.525*SoftAssets + 0.409*dCashSales - 0.177*dROA
    Prob = 1 / (1 + exp(-Logit))
    F-Score = Prob / 0.0037 (base unconditional probability)
    """
    logit = (
        -7.383
        + (4.037 * accruals_pct)
        + (0.188 * receivables_change_pct)
        + (0.192 * inventory_change_pct)
        + (0.525 * soft_assets_pct)
        + (0.409 * cash_sales_growth_pct)
        - (0.177 * roa_change)
    )

    try:
        prob = 1.0 / (1.0 + math.exp(-logit))
    except OverflowError:
        prob = 1.0 if logit > 0 else 0.0

    unconditional_base_prob = 0.0037
    f_score = prob / unconditional_base_prob

    if f_score > 2.45:
        verdict = "KRİTİK / ÇOK YÜKSEK MANİPÜLASYON RİSKİ (F-Score > 2.45: Finansal tabloların geriye dönük düzeltilme veya manipülasyon riski piyasanın 2.5 katından fazla)"
    elif f_score >= 1.00:
        verdict = "ORTA / DİKKAT GEREKTİREN MANİPÜLASYON RİSKİ (F-Score >= 1.00: Piyasa ortalamasının üzerinde manipülasyon olasılığı)"
    else:
        verdict = "DÜŞÜK RİSK / SAĞLIKLI RAPORLAMA (F-Score < 1.00: Muhasebe kalitesi standartlara uygun, manipülasyon emaresi yok)"

    return {
        "logit_value": round(logit, 4),
        "predicted_misstatement_probability_pct": round(prob * 100, 4),
        "unconditional_base_probability_pct": round(unconditional_base_prob * 100, 2),
        "dechow_f_score": round(f_score, 2),
        "manipulation_risk_verdict": verdict
    }


def calculate_piotroski_f_score(
    roa: float,
    cfo: float,
    delta_roa: float,
    cfo_greater_than_ni: bool,
    delta_long_term_leverage: float,
    delta_current_ratio: float,
    new_shares_issued: bool,
    delta_gross_margin: float,
    delta_asset_turnover: float
) -> Dict[str, Any]:
    """Calculates the Piotroski 9-Point F-Score for fundamental financial health and value screening:
    1. ROA > 0 (1 pt)
    2. CFO > 0 (1 pt)
    3. delta_ROA > 0 (1 pt)
    4. CFO > Net Income (Akrüal kalitesi) (1 pt)
    5. delta_long_term_leverage < 0 (Kaldıraç düşüşü) (1 pt)
    6. delta_current_ratio > 0 (Likidite artışı) (1 pt)
    7. new_shares_issued == False (Hisse sulanması yok) (1 pt)
    8. delta_gross_margin > 0 (Marj artışı) (1 pt)
    9. delta_asset_turnover > 0 (Verimlilik artışı) (1 pt)
    """
    scores = {
        "f_roa": 1 if roa > 0 else 0,
        "f_cfo": 1 if cfo > 0 else 0,
        "f_delta_roa": 1 if delta_roa > 0 else 0,
        "f_accrual_quality": 1 if cfo_greater_than_ni else 0,
        "f_leverage": 1 if delta_long_term_leverage < 0 else 0,
        "f_liquidity": 1 if delta_current_ratio > 0 else 0,
        "f_no_dilution": 1 if not new_shares_issued else 0,
        "f_margin": 1 if delta_gross_margin > 0 else 0,
        "f_turnover": 1 if delta_asset_turnover > 0 else 0,
    }

    total_score = sum(scores.values())

    if total_score >= 8:
        category = "MÜKEMMEL FİNANSAL SAĞLIK / GÜÇLÜ DEĞER (Piotroski 8-9: Düşük değer tuzağı riski, üstün toparlanma potansiyeli)"
    elif total_score >= 5:
        category = "ORTA SEVİYE / KARMA FİNANSAL DURUM (Piotroski 5-7: Dengeli operasyonel performans)"
    elif total_score >= 3:
        category = "ZAYIF / RİSKLİ FİNANSAL YAPI (Piotroski 3-4: Operasyonel bozulma ve likidite baskısı)"
    else:
        category = "KRİTİK / İFLAS & DEĞER TUZAĞI RİSKİ (Piotroski 0-2: Ciddi sermaye erozyonu ve yapısal tehlike)"

    return {
        "piotroski_f_score": total_score,
        "max_score": 9,
        "breakdown": scores,
        "financial_health_classification": category
    }


def calculate_nelson_siegel_yield(
    maturity_years: float,
    beta0: float,
    beta1: float,
    beta2: float,
    lambda_param: float = 0.0609
) -> Dict[str, Any]:
    """Calculates bond yield using the Nelson-Siegel (1987) Term Structure Model:
    y(m) = beta0 + beta1 * ((1 - exp(-m/lambda)) / (m/lambda)) + beta2 * (((1 - exp(-m/lambda)) / (m/lambda)) - exp(-m/lambda))
    beta0: Level (Uzun vadeli asimptotik getiri)
    beta1: Slope (Kısa-uzun vade eğimi: beta1 < 0 ise yukarı eğimli normal eğri, beta1 > 0 ise ters getiri eğrisi)
    beta2: Curvature (Orta vadeli eğrilik/kambur)
    """
    if maturity_years <= 0:
        return {"error": "maturity_years sıfırdan büyük olmalıdır."}
    if lambda_param <= 0:
        return {"error": "lambda_param sıfırdan büyük olmalıdır."}

    m = maturity_years
    tau = m / lambda_param
    term1 = (1.0 - math.exp(-tau)) / tau
    term2 = term1 - math.exp(-tau)

    modeled_yield = beta0 + (beta1 * term1) + (beta2 * term2)

    if beta1 < -1.0:
        shape = "YUKARI EĞİMLİ / NORMAL GETİRİ EĞRİSİ (Ekonomik büyüme ve normal vadeli prim)"
    elif beta1 > 1.0:
        shape = "TERS GETİRİ EĞRİSİ / INVERTED YIELD CURVE (Resesyon öncü göstergesi)"
    else:
        shape = "DÜZLEŞMİŞ GETİRİ EĞRİSİ / FLAT CURVE (Para politikasında geçiş dönemi)"

    return {
        "maturity_years": round(maturity_years, 2),
        "beta0_level": round(beta0, 3),
        "beta1_slope": round(beta1, 3),
        "beta2_curvature": round(beta2, 3),
        "lambda_decay": round(lambda_param, 4),
        "modeled_yield_pct": round(modeled_yield, 3),
        "yield_curve_shape": shape
    }


def calculate_heston_feller_condition(
    kappa: float,
    theta: float,
    xi: float
) -> Dict[str, Any]:
    """Evaluates the Feller Condition for Heston Stochastic Volatility Model:
    dv_t = kappa * (theta - v_t) * dt + xi * sqrt(v_t) * dW_t
    Feller Condition: 2 * kappa * theta > xi^2
    Guarantees that variance v_t is strictly positive and never reaches zero.
    """
    if kappa <= 0 or theta <= 0 or xi <= 0:
        return {"error": "kappa, theta ve xi pozitif değerler olmalıdır."}

    lhs = 2.0 * kappa * theta
    rhs = xi ** 2
    feller_ratio = lhs / rhs

    condition_satisfied = lhs > rhs

    if condition_satisfied:
        verdict = "FELLER KOŞULU SAĞLANIYOR (2*kappa*theta > xi^2: Varyans sıfıra düşmez, stokastik oynaklık simülasyonu kararlı)"
    else:
        verdict = "FELLER KOŞULU İHLAL EDİLDİ (2*kappa*theta <= xi^2: Varyans sıfıra çarpabilir, simülasyonlarda sayısal kararsızlık ve volatilite patlamaları oluşabilir)"

    return {
        "kappa_mean_reversion_speed": round(kappa, 4),
        "theta_long_term_variance": round(theta, 4),
        "xi_vol_of_vol": round(xi, 4),
        "feller_ratio": round(feller_ratio, 4),
        "feller_condition_satisfied": condition_satisfied,
        "mathematical_implication": verdict
    }


def main():
    parser = argparse.ArgumentParser(description="Microstructure, Yield Curve & Forensic Analytics CLI")
    subparsers = parser.add_subparsers(dest="command", help="Alt komutlar")

    # VPIN
    vpin_parser = subparsers.add_parser("vpin", help="VPIN Toksik Akış Analizi")
    vpin_parser.add_argument("--buy-volumes", type=float, nargs="+", required=True, help="Sepet alış hacimleri")
    vpin_parser.add_argument("--sell-volumes", type=float, nargs="+", required=True, help="Sepet satış hacimleri")
    vpin_parser.add_argument("--bucket-size", type=float, required=True, help="Sepet hacim büyüklüğü")

    # Almgren-Chriss
    ac_parser = subparsers.add_parser("almgren-chriss", help="Almgren-Chriss Optimal İcra")
    ac_parser.add_argument("--total-shares", type=float, required=True, help="Toplam hisse adedi")
    ac_parser.add_argument("--days", type=int, default=5, help="Zaman ufku (gün)")
    ac_parser.add_argument("--intervals", type=int, default=5, help="Zaman adımı sayısı")
    ac_parser.add_argument("--eta", type=float, default=2.5e-6, help="Geçici piyasa etkisi katsayısı")
    ac_parser.add_argument("--risk-aversion", type=float, default=1e-6, help="Riskten kaçınma katsayısı (lambda)")
    ac_parser.add_argument("--sigma", type=float, default=0.02, help="Günlük volatilite")

    # Dechow F-Score
    dechow_parser = subparsers.add_parser("dechow", help="Dechow F-Score Muhasebe Manipülasyonu")
    dechow_parser.add_argument("--accruals", type=float, required=True, help="Toplam Akrüaller / Toplam Varlıklar")
    dechow_parser.add_argument("--receivables-change", type=float, required=True, help="Alacaklardaki Değişim")
    dechow_parser.add_argument("--inventory-change", type=float, required=True, help="Stoklardaki Değişim")
    dechow_parser.add_argument("--soft-assets", type=float, required=True, help="Yumuşak Varlıklar Oranı")
    dechow_parser.add_argument("--cash-sales-growth", type=float, required=True, help="Nakit Satışlardaki Değişim")
    dechow_parser.add_argument("--roa-change", type=float, required=True, help="ROA Değişimi")

    # Piotroski F-Score
    piotroski_parser = subparsers.add_parser("piotroski", help="Piotroski 9-Puanlık F-Score")
    piotroski_parser.add_argument("--roa", type=float, required=True, help="ROA")
    piotroski_parser.add_argument("--cfo", type=float, required=True, help="Operasyonel Nakit Akışı")
    piotroski_parser.add_argument("--delta-roa", type=float, required=True, help="ROA Değişimi")
    piotroski_parser.add_argument("--cfo-gt-ni", action="store_true", help="CFO > Net Kâr mı?")
    piotroski_parser.add_argument("--delta-leverage", type=float, required=True, help="Uzun vadeli kaldıraç değişimi")
    piotroski_parser.add_argument("--delta-current-ratio", type=float, required=True, help="Cari oran değişimi")
    piotroski_parser.add_argument("--shares-issued", action="store_true", help="Yeni hisse ihraç edildi mi?")
    piotroski_parser.add_argument("--delta-gross-margin", type=float, required=True, help="Brüt marj değişimi")
    piotroski_parser.add_argument("--delta-turnover", type=float, required=True, help="Aktif devir hızı değişimi")

    # Nelson-Siegel
    ns_parser = subparsers.add_parser("nelson-siegel", help="Nelson-Siegel Faiz Getiri Eğrisi")
    ns_parser.add_argument("--maturity", type=float, required=True, help="Vade (yıl)")
    ns_parser.add_argument("--beta0", type=float, required=True, help="Beta0 (Seviye)")
    ns_parser.add_argument("--beta1", type=float, required=True, help="Beta1 (Eğim)")
    ns_parser.add_argument("--beta2", type=float, required=True, help="Beta2 (Eğrilik)")
    ns_parser.add_argument("--lambda-param", type=float, default=0.0609, help="Lambda sönümleme parametresi")

    # Heston Feller
    heston_parser = subparsers.add_parser("heston-feller", help="Heston Feller Koşulu")
    heston_parser.add_argument("--kappa", type=float, required=True, help="Ortalamaya dönüş hızı (kappa)")
    heston_parser.add_argument("--theta", type=float, required=True, help="Uzun vadeli varyans (theta)")
    heston_parser.add_argument("--xi", type=float, required=True, help="Volatilitenin volatilitesi (xi)")

    args = parser.parse_args()

    if args.command == "vpin":
        res = calculate_vpin(args.buy_volumes, args.sell_volumes, args.bucket_size)
    elif args.command == "almgren-chriss":
        res = calculate_almgren_chriss_trajectory(args.total_shares, args.days, args.intervals, args.eta, args.risk_aversion, args.sigma)
    elif args.command == "dechow":
        res = calculate_dechow_f_score(args.accruals, args.receivables_change, args.inventory_change, args.soft_assets, args.cash_sales_growth, args.roa_change)
    elif args.command == "piotroski":
        res = calculate_piotroski_f_score(args.roa, args.cfo, args.delta_roa, args.cfo_gt_ni, args.delta_leverage, args.delta_current_ratio, args.shares_issued, args.delta_gross_margin, args.delta_turnover)
    elif args.command == "nelson-siegel":
        res = calculate_nelson_siegel_yield(args.maturity, args.beta0, args.beta1, args.beta2, args.lambda_param)
    elif args.command == "heston-feller":
        res = calculate_heston_feller_condition(args.kappa, args.theta, args.xi)
    else:
        parser.print_help()
        return

    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
