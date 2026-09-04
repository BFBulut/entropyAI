#!/usr/bin/env python3
"""CLI and library utility for Advanced Execution, Credit Migration, PE Fund Economics, XVA & Macro Crises:
- Perold Implementation Shortfall & Square-Root Law of Market Impact (Algorithmic Execution)
- Credit Rating Migration, Fallen Angel Surcharge & Loss Given Default (LGD / Basel EL)
- Private Equity Fund Economics (DPI, RVPI, TVPI, J-Curve & Kaplan-Schoar PME Benchmarking)
- XVA Derivative Valuation Suite (CVA, DVA, FVA, MVA, KVA & Net Pricing Adjustment)
- IMF Reserve Adequacy (ARA Metric, Sudden Stop & Currency Crisis Vulnerability Assessment)
"""

import argparse
import json
import math
from typing import Dict, Any, Optional


def calculate_implementation_shortfall_and_impact(
    decision_price: float,
    arrival_price: float,
    execution_price: float,
    final_price: float,
    executed_shares: float,
    target_shares: float,
    explicit_fees: float,
    daily_volatility: float,
    daily_volume: float,
    impact_constant_y: float = 0.6
) -> Dict[str, Any]:
    """Calculates André Perold's Implementation Shortfall (1988) and Almgren-style Square-Root Law of Market Impact:
    Paper Return = Target Shares * (Final Price - Decision Price) [for buy order]
    Delay Cost = Executed Shares * (Arrival Price - Decision Price)
    Price Impact / Realized Spread = Executed Shares * (Execution Price - Arrival Price)
    Opportunity Cost = (Target Shares - Executed Shares) * (Final Price - Decision Price)
    Explicit Fees = Brokerage, exchange, regulatory fees
    Total Implementation Shortfall = Delay + Impact + Opportunity + Fees
    Square-Root Market Impact: I_perm = Y * sigma_daily * sqrt(Q / V_daily) * Price
    """
    if decision_price <= 0 or arrival_price <= 0 or execution_price <= 0 or final_price <= 0:
        return {"error": "Fiyatlar pozitif olmalıdır."}
    if executed_shares < 0 or target_shares <= 0 or executed_shares > target_shares:
        return {"error": "Hisse adetleri pozitif ve icra edilen <= hedef olmalıdır."}
    if daily_volatility < 0 or daily_volume <= 0:
        return {"error": "Volatilite negatif olamaz, günlük hacim pozitif olmalıdır."}

    unfilled_shares = target_shares - executed_shares

    # Perold 4-Component Decomposition
    delay_cost = executed_shares * (arrival_price - decision_price)
    realized_impact_cost = executed_shares * (execution_price - arrival_price)
    opportunity_cost = unfilled_shares * (final_price - decision_price)
    total_shortfall_cash = delay_cost + realized_impact_cost + opportunity_cost + explicit_fees

    total_decision_notional = target_shares * decision_price
    shortfall_bps = (total_shortfall_cash / total_decision_notional) * 10000.0 if total_decision_notional > 0 else 0.0

    # Theoretical Square-Root Law Permanent Impact
    participation_rate = (executed_shares / daily_volume) if daily_volume > 0 else 0.0
    theoretical_impact_pct = impact_constant_y * daily_volatility * math.sqrt(participation_rate)
    theoretical_impact_cash = theoretical_impact_pct * (executed_shares * decision_price)

    return {
        "target_shares": target_shares,
        "executed_shares": executed_shares,
        "fill_rate_pct": round((executed_shares / target_shares) * 100, 2),
        "decision_price": round(decision_price, 4),
        "arrival_price": round(arrival_price, 4),
        "execution_price": round(execution_price, 4),
        "final_price": round(final_price, 4),
        "delay_cost": round(delay_cost, 2),
        "realized_impact_cost": round(realized_impact_cost, 2),
        "opportunity_cost": round(opportunity_cost, 2),
        "explicit_fees": round(explicit_fees, 2),
        "total_implementation_shortfall": round(total_shortfall_cash, 2),
        "shortfall_basis_points": round(shortfall_bps, 2),
        "theoretical_square_root_impact_pct": round(theoretical_impact_pct * 100, 3),
        "theoretical_impact_cash": round(theoretical_impact_cash, 2),
        "execution_diagnosis": "MÜKEMMEL İCRA (Düşük Slippage)" if shortfall_bps < 15.0 else (
            "KABUL EDİLEBİLİR İCRA (15-50 bps)" if shortfall_bps <= 50.0 else "YÜKSEK İCRA KAYBI / TOKSİK AKIŞ SÜZÜLMESİ (>50 bps)"
        )
    }


def calculate_credit_migration_and_lgd(
    exposure_at_default: float,
    pd_current_pct: float,
    recovery_rate_pct: float,
    rating_downgrade_pd_pct: float,
    stress_recovery_rate_pct: float
) -> Dict[str, Any]:
    """Calculates Credit Rating Migration, Loss Given Default (LGD) and Basel Expected Loss (EL) dynamics:
    Base LGD = 1.0 - Recovery Rate
    Base EL = EAD * PD * LGD
    Downgrade / Stressed EL = EAD * Downgrade_PD * Stressed_LGD
    Fallen Angel Surcharge = Difference in economic capital required upon entering High Yield zone.
    """
    if exposure_at_default <= 0:
        return {"error": "exposure_at_default pozitif olmalıdır."}
    if not (0 <= pd_current_pct <= 100) or not (0 <= rating_downgrade_pd_pct <= 100):
        return {"error": "Temerrüt olasılıkları (PD) %0-%100 aralığında olmalıdır."}
    if not (0 <= recovery_rate_pct <= 100) or not (0 <= stress_recovery_rate_pct <= 100):
        return {"error": "Kurtarma oranları (Recovery) %0-%100 aralığında olmalıdır."}

    lgd_base = 1.0 - (recovery_rate_pct / 100.0)
    lgd_stress = 1.0 - (stress_recovery_rate_pct / 100.0)

    el_base = exposure_at_default * (pd_current_pct / 100.0) * lgd_base
    el_downgrade = exposure_at_default * (rating_downgrade_pd_pct / 100.0) * lgd_stress
    el_surge_ratio = (el_downgrade / el_base) if el_base > 0 else float("inf")

    is_fallen_angel = (pd_current_pct <= 0.8) and (rating_downgrade_pd_pct >= 2.5)

    return {
        "exposure_at_default": round(exposure_at_default, 2),
        "current_pd_pct": round(pd_current_pct, 3),
        "base_recovery_rate_pct": round(recovery_rate_pct, 2),
        "base_lgd_pct": round(lgd_base * 100, 2),
        "base_expected_loss": round(el_base, 2),
        "downgrade_pd_pct": round(rating_downgrade_pd_pct, 3),
        "stress_recovery_rate_pct": round(stress_recovery_rate_pct, 2),
        "stress_lgd_pct": round(lgd_stress * 100, 2),
        "downgrade_expected_loss": round(el_downgrade, 2),
        "loss_increase_multiple": round(el_surge_ratio, 2),
        "fallen_angel_risk": "YÜKSEK (IG -> HY Sınır Geçişi / Zorunlu Kurumsal Satış Riski)" if is_fallen_angel else "DÜŞÜK / NORMAL KREDİ HAREKETİ",
        "capital_cushion_required": round(el_downgrade - el_base, 2)
    }


def calculate_pe_fund_metrics_and_pme(
    capital_called_pic: float,
    cumulative_distributions: float,
    remaining_nav: float,
    benchmark_discounted_distributions_nav: Optional[float] = None,
    benchmark_discounted_calls: Optional[float] = None
) -> Dict[str, Any]:
    """Calculates Private Equity Fund Performance Metrics and Kaplan-Schoar Public Market Equivalent (PME):
    DPI (Distributed to Paid-In) = Cumulative Distributions / Paid-In Capital (PIC)
    RVPI (Residual Value to Paid-In) = Remaining Unrealized NAV / Paid-In Capital (PIC)
    TVPI (Total Value to Paid-In) = DPI + RVPI
    Kaplan-Schoar PME = Sum(Distributions_discounted + NAV_discounted) / Sum(Calls_discounted)
    PME > 1.0 indicates outperformance against public equity benchmark after all fees and illiquidity.
    """
    if capital_called_pic <= 0:
        return {"error": "capital_called_pic (Yatırılan Sermaye) sıfırdan büyük olmalıdır."}
    if cumulative_distributions < 0 or remaining_nav < 0:
        return {"error": "Dağıtımlar ve Kalan NAV negatif olamaz."}

    dpi = cumulative_distributions / capital_called_pic
    rvpi = remaining_nav / capital_called_pic
    tvpi = dpi + rvpi

    # J-Curve Diagnosis
    if dpi < 0.15 and tvpi < 1.05:
        j_curve_phase = "J-EĞRİSİ ÇUKURU (Yatırım & Fon Kuruluş Dönemi: Masraflar ve henüz gerçekleşmemiş değerlemeler)"
    elif dpi >= 1.0:
        j_curve_phase = "HASAT & KÂR DAĞITIM AŞAMASI (Yatırımcı anaparasını nakden geri aldı, ilave getiriler serbest nakit)"
    else:
        j_curve_phase = "BÜYÜME & DEĞER YARATIM DÖNEMİ (Portföy olgunlaşıyor, NAV büyümesi ağırlıkta)"

    pme_score = None
    pme_diagnosis = "PME HESAPLANMADI (Referans endeks nakit akışları girilmedi)"
    if benchmark_discounted_distributions_nav is not None and benchmark_discounted_calls is not None:
        if benchmark_discounted_calls > 0:
            pme_score = round(benchmark_discounted_distributions_nav / benchmark_discounted_calls, 3)
            if pme_score > 1.0:
                pme_diagnosis = f"ALFA ÜRETİLDİ (PME: {pme_score}x > 1.0x: Kamu piyasa endeksini aşan net getiri)"
            else:
                pme_diagnosis = f"KAMU PİYASASININ GERİSİNDE (PME: {pme_score}x < 1.0x: Likiditesizlik primini karşılamadı)"

    return {
        "capital_called_pic": round(capital_called_pic, 2),
        "cumulative_distributions": round(cumulative_distributions, 2),
        "remaining_nav": round(remaining_nav, 2),
        "total_value": round(cumulative_distributions + remaining_nav, 2),
        "dpi": round(dpi, 3),
        "rvpi": round(rvpi, 3),
        "tvpi": round(tvpi, 3),
        "j_curve_stage": j_curve_phase,
        "kaplan_schoar_pme": pme_score,
        "pme_evaluation": pme_diagnosis
    }


def calculate_xva_derivative_pricing(
    unadjusted_pv: float,
    expected_exposure_ee: float,
    counterparty_pd_pct: float,
    counterparty_recovery_pct: float,
    expected_negative_exposure_ene: float,
    own_pd_pct: float,
    own_recovery_pct: float,
    funding_spread_pct: float = 0.75,
    initial_margin: float = 0.0,
    cost_of_margin_pct: float = 1.25,
    regulatory_capital: float = 0.0,
    hurdle_rate_pct: float = 10.0
) -> Dict[str, Any]:
    """Calculates Total XVA adjustments for Bilateral OTC Derivatives:
    Adjusted Value = Unadjusted PV - CVA + DVA - FVA - MVA - KVA
    CVA = EE * (1 - R_c) * PD_c
    DVA = ENE * (1 - R_own) * PD_own
    FVA = EE * Funding_Spread
    MVA = Initial_Margin * Cost_of_Margin
    KVA = Regulatory_Capital * Hurdle_Rate
    """
    if counterparty_pd_pct < 0 or counterparty_recovery_pct < 0 or own_pd_pct < 0 or own_recovery_pct < 0:
        return {"error": "Olasılık ve kurtarma oranları negatif olamaz."}

    cva = expected_exposure_ee * (1.0 - (counterparty_recovery_pct / 100.0)) * (counterparty_pd_pct / 100.0)
    dva = expected_negative_exposure_ene * (1.0 - (own_recovery_pct / 100.0)) * (own_pd_pct / 100.0)
    fva = expected_exposure_ee * (funding_spread_pct / 100.0)
    mva = initial_margin * (cost_of_margin_pct / 100.0)
    kva = regulatory_capital * (hurdle_rate_pct / 100.0)

    total_xva = -cva + dva - fva - mva - kva
    adjusted_pv = unadjusted_pv + total_xva

    return {
        "unadjusted_pv": round(unadjusted_pv, 2),
        "cva_credit_risk": round(cva, 2),
        "dva_own_credit": round(dva, 2),
        "fva_funding_cost": round(fva, 2),
        "mva_margin_cost": round(mva, 2),
        "kva_capital_hurdle": round(kva, 2),
        "total_xva_adjustment": round(total_xva, 2),
        "adjusted_pv": round(adjusted_pv, 2),
        "valuation_impact_pct": round((total_xva / abs(unadjusted_pv)) * 100, 2) if abs(unadjusted_pv) > 0 else 0.0
    }


def calculate_imf_reserve_adequacy(
    actual_reserves_bn: float,
    short_term_external_debt_bn: float,
    other_portfolio_liabilities_bn: float,
    broad_money_m2_bn: float,
    annual_exports_bn: float
) -> Dict[str, Any]:
    """Calculates IMF ARA (Assessing Reserve Adequacy) Metric for Emerging Markets:
    ARA Metric = 0.30 * ShortTermDebt + 0.15 * OtherPortfolioLiabilities + 0.05 * BroadMoney(M2) + 0.05 * Exports
    Adequacy Ratio = (Actual Reserves / ARA Metric) * 100
    - 100% - 150%: Adequate and Safe Buffer
    - > 150%: Excessive Accumulation (High carrying cost)
    - 75% - 100%: Vulnerable (Prone to external shocks and capital outflows)
    - < 75%: Critical Inadequacy (High sudden stop, balance-of-payments crisis and devaluation risk)
    """
    if (short_term_external_debt_bn < 0 or other_portfolio_liabilities_bn < 0 or
            broad_money_m2_bn < 0 or annual_exports_bn < 0):
        return {"error": "Borç, para arzı ve ihracat değerleri negatif olamaz."}

    ara_metric = (
        0.30 * short_term_external_debt_bn
        + 0.15 * other_portfolio_liabilities_bn
        + 0.05 * broad_money_m2_bn
        + 0.05 * annual_exports_bn
    )

    if ara_metric <= 0:
        return {"error": "Toplam risk parametreleri sıfırdan büyük olmalıdır."}

    coverage_ratio_pct = (actual_reserves_bn / ara_metric) * 100.0

    if coverage_ratio_pct > 150.0:
        diagnosis = "AŞIRI REZERV BİRİKİMİ (Yüksek fırsat maliyeti ve sterilizasyon baskısı)"
    elif coverage_ratio_pct >= 100.0:
        diagnosis = "OPTIMAL VE GÜVENLİ DÖVİZ REZERVİ (IMF Standartlarında yeterli dış şok tamponu)"
    elif coverage_ratio_pct >= 75.0:
        diagnosis = "HASSAS / DİKKAT GEREKTİREN SEVİYE (Sermaye çıkışlarına ve ani duruşa karşı savunmasız)"
    else:
        diagnosis = "KRİTİK REZERV YETERSİZLİĞİ / DEVALÜASYON VE ÖDEMELER DENGESİ KRİZİ ALARMI (Sudden Stop riski)"

    return {
        "actual_reserves_bn_usd": round(actual_reserves_bn, 2),
        "short_term_debt_component_bn": round(0.30 * short_term_external_debt_bn, 2),
        "portfolio_liabilities_component_bn": round(0.15 * other_portfolio_liabilities_bn, 2),
        "m2_flight_component_bn": round(0.05 * broad_money_m2_bn, 2),
        "export_shock_component_bn": round(0.05 * annual_exports_bn, 2),
        "imf_ara_metric_bn_usd": round(ara_metric, 2),
        "reserve_coverage_ratio_pct": round(coverage_ratio_pct, 2),
        "reserve_surplus_deficit_bn_usd": round(actual_reserves_bn - ara_metric, 2),
        "crisis_vulnerability_diagnosis": diagnosis
    }


def main():
    parser = argparse.ArgumentParser(description="Advanced Execution, PE, XVA & Macro Crisis Analytics CLI")
    subparsers = parser.add_subparsers(dest="command", help="Alt komutlar")

    # Shortfall
    sf_parser = subparsers.add_parser("shortfall", help="Perold Implementation Shortfall ve Karekök Etki")
    sf_parser.add_argument("--decision", type=float, required=True, help="Karar anı fiyatı")
    sf_parser.add_argument("--arrival", type=float, required=True, help="Varış fiyatı")
    sf_parser.add_argument("--execution", type=float, required=True, help="İcra fiyatı")
    sf_parser.add_argument("--final", type=float, required=True, help="Gün sonu kapanış fiyatı")
    sf_parser.add_argument("--executed-shares", type=float, required=True, help="İcra edilen adet")
    sf_parser.add_argument("--target-shares", type=float, required=True, help="Hedeflenen adet")
    sf_parser.add_argument("--fees", type=float, default=0.0, help="Komisyon ve ücretler")
    sf_parser.add_argument("--vol", type=float, default=0.015, help="Günlük volatilite")
    sf_parser.add_argument("--volume", type=float, default=1000000.0, help="Günlük hacim")

    # Credit Migration
    cm_parser = subparsers.add_parser("credit-migration", help="Kredi Notu Göçü, Fallen Angel ve LGD")
    cm_parser.add_argument("--ead", type=float, required=True, help="Exposure at Default (EAD)")
    cm_parser.add_argument("--pd-current", type=float, required=True, help="Mevcut PD (%)")
    cm_parser.add_argument("--recovery", type=float, required=True, help="Normal Kurtarma Oranı (%)")
    cm_parser.add_argument("--pd-downgrade", type=float, required=True, help="Düşürülmüş PD (%)")
    cm_parser.add_argument("--stress-recovery", type=float, required=True, help="Stres altındaki Kurtarma Oranı (%)")

    # PE Metrics
    pe_parser = subparsers.add_parser("pe-metrics", help="Özel Sermaye Fon Metrikleri (DPI, TVPI, PME)")
    pe_parser.add_argument("--pic", type=float, required=True, help="Yatırılan Sermaye (PIC)")
    pe_parser.add_argument("--distributions", type=float, required=True, help="Kümülatif Dağıtımlar")
    pe_parser.add_argument("--nav", type=float, required=True, help="Kalan Portföy NAV")
    pe_parser.add_argument("--bench-dist", type=float, default=None, help="Endeks İskontolu Dağıtım+NAV")
    pe_parser.add_argument("--bench-calls", type=float, default=None, help="Endeks İskontolu Çağrılar")

    # XVA
    xva_parser = subparsers.add_parser("xva", help="XVA Türev Fiyatlama Düzeltmeleri (CVA, DVA, FVA, MVA, KVA)")
    xva_parser.add_argument("--pv", type=float, required=True, help="Düzeltilmemiş Risksiz Bugünkü Değer")
    xva_parser.add_argument("--ee", type=float, required=True, help="Beklenen Pozitif Maruziyet (EE)")
    xva_parser.add_argument("--cp-pd", type=float, required=True, help="Karşı taraf PD (%)")
    xva_parser.add_argument("--cp-recovery", type=float, default=40.0, help="Karşı taraf kurtarma oranı (%)")
    xva_parser.add_argument("--ene", type=float, required=True, help="Beklenen Negatif Maruziyet (ENE)")
    xva_parser.add_argument("--own-pd", type=float, required=True, help="Kendi PD (%)")
    xva_parser.add_argument("--own-recovery", type=float, default=40.0, help="Kendi kurtarma oranı (%)")
    xva_parser.add_argument("--funding-spread", type=float, default=0.75, help="Fonlama spread (%)")
    xva_parser.add_argument("--initial-margin", type=float, default=0.0, help="Başlangıç teminatı (IM)")
    xva_parser.add_argument("--margin-cost", type=float, default=1.25, help="Teminat maliyeti (%)")
    xva_parser.add_argument("--reg-capital", type=float, default=0.0, help="Düzenleyici sermaye")
    xva_parser.add_argument("--hurdle-rate", type=float, default=10.0, help="Sermaye getiri eşiği (%)")

    # IMF ARA
    ara_parser = subparsers.add_parser("imf-ara", help="IMF Rezerv Yeterliliği ve Kriz Barometresi")
    ara_parser.add_argument("--reserves", type=float, required=True, help="Fiili Döviz Rezervleri ($ Milyar)")
    ara_parser.add_argument("--st-debt", type=float, required=True, help="Kısa Vadeli Dış Borç ($ Milyar)")
    ara_parser.add_argument("--portfolio", type=float, required=True, help="Diğer Portföy Borçları ($ Milyar)")
    ara_parser.add_argument("--m2", type=float, required=True, help="Geniş Para M2 ($ Milyar)")
    ara_parser.add_argument("--exports", type=float, required=True, help="Yıllık İhracat ($ Milyar)")

    args = parser.parse_args()

    if args.command == "shortfall":
        res = calculate_implementation_shortfall_and_impact(
            args.decision, args.arrival, args.execution, args.final,
            args.executed_shares, args.target_shares, args.fees,
            args.vol, args.volume
        )
    elif args.command == "credit-migration":
        res = calculate_credit_migration_and_lgd(
            args.ead, args.pd_current, args.recovery,
            args.pd_downgrade, args.stress_recovery
        )
    elif args.command == "pe-metrics":
        res = calculate_pe_fund_metrics_and_pme(
            args.pic, args.distributions, args.nav,
            args.bench_dist, args.bench_calls
        )
    elif args.command == "xva":
        res = calculate_xva_derivative_pricing(
            args.pv, args.ee, args.cp_pd, args.cp_recovery,
            args.ene, args.own_pd, args.own_recovery,
            args.funding_spread, args.initial_margin, args.margin_cost,
            args.reg_capital, args.hurdle_rate
        )
    elif args.command == "imf-ara":
        res = calculate_imf_reserve_adequacy(
            args.reserves, args.st_debt, args.portfolio, args.m2, args.exports
        )
    else:
        parser.print_help()
        return

    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
