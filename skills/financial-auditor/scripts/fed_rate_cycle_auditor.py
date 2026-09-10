#!/usr/bin/env python3
"""FED 3-Year Interest Rate Cycle & Macro Plumbing Auditor (2023 - 2026).

Decennial Hedge Fund Intelligence & Quantitative Central Bank Policy Audit.
Models:
1. 3-Year FOMC Decision Chronology & Terminal Rate Evolution.
2. Taylor (1993) & Inertial Taylor Rule Policy Gap Decomposition.
3. Fed Net Liquidity Plumbing (WALCL - TGA - ON_RRP) and QT Runoff.
4. 2Y-10Y Yield Curve Regime Dynamics (Deep Inversion to Bull Steepening).
5. Real Interest Rate Stance (Nominal - Core PCE) & Breakeven Inflation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import math


@dataclass
class FomcDecision:
    date: str
    target_range_lower: float
    target_range_upper: float
    action_bps: int
    core_pce_pct: float
    unemployment_pct: float
    real_gdp_growth_pct: float
    description: str


@dataclass
class FedPlumbingSnapshot:
    period: str
    fed_assets_bil: float       # WALCL (Trillions -> Billions)
    tga_balance_bil: float      # Treasury General Account
    on_rrp_balance_bil: float   # Overnight Reverse Repo
    bank_reserves_bil: float    # Other deposits held by depository institutions
    net_liquidity_bil: float    # Assets - TGA - ON_RRP


class FedRateCycleAuditor:
    """Quantitative auditor for the Federal Reserve 2023-2026 interest rate cycle."""

    # 3-Year FOMC Historical Trajectory
    FOMC_HISTORY: List[FomcDecision] = [
        FomcDecision("2023-02-01", 4.50, 4.75, +25, 4.7, 3.4, 2.2, "Aggressive hiking continues; downshift from 50bps to 25bps."),
        FomcDecision("2023-03-22", 4.75, 5.00, +25, 4.6, 3.5, 2.2, "SVB bank run crisis; BTFP emergency liquidity facility launched; hike maintained."),
        FomcDecision("2023-05-03", 5.00, 5.25, +25, 4.7, 3.7, 2.2, "Third consecutive 25bps hike; credit tightening monitoring."),
        FomcDecision("2023-06-14", 5.00, 5.25, 0, 4.3, 3.6, 2.2, "Hawkish pause / skip; projection of further hike."),
        FomcDecision("2023-07-26", 5.25, 5.50, +25, 4.2, 3.5, 2.9, "TERMINAL RATE PEAK: Cycle top reached at 5.25%-5.50%."),
        FomcDecision("2023-09-20", 5.25, 5.50, 0, 3.7, 3.8, 2.9, "Higher-for-Longer doctrine formalized; Dot plot revisions."),
        FomcDecision("2023-11-01", 5.25, 5.50, 0, 3.5, 3.9, 2.9, "Surge in long-term Treasury yields (10Y at 5.0%) tightens financial conditions for Fed."),
        FomcDecision("2023-12-13", 5.25, 5.50, 0, 3.2, 3.7, 2.9, "Dovish Pivot signaling: Powell acknowledges rate cut discussions for 2024."),
        FomcDecision("2024-01-31", 5.25, 5.50, 0, 2.8, 3.7, 2.5, "Patience period; March cut expectations pushed back."),
        FomcDecision("2024-05-01", 5.25, 5.50, 0, 2.8, 3.9, 2.5, "QT tapering announced: Treasury cap reduced from $60B to $25B/month."),
        FomcDecision("2024-07-31", 5.25, 5.50, 0, 2.6, 4.3, 2.5, "Sahm Rule warning indicator; labor market cooling acknowledged."),
        FomcDecision("2024-09-18", 4.75, 5.00, -50, 2.7, 4.1, 2.8, "JUMBO EASING PIVOT: 50 bps initial insurance cut; new easing regime launched."),
        FomcDecision("2024-11-07", 4.50, 4.75, -25, 2.8, 4.1, 2.8, "Follow-up 25 bps cut; policy moves closer to neutral."),
        FomcDecision("2024-12-18", 4.25, 4.50, -25, 2.6, 4.1, 2.8, "Cumulative 100 bps easing in 2024; soft landing trajectory on track."),
        FomcDecision("2025-06-18", 3.75, 4.00, -25, 2.3, 4.2, 2.1, "Mid-cycle recalibration; Core PCE approaching 2.0% target."),
        FomcDecision("2025-12-17", 3.25, 3.50, -25, 2.2, 4.2, 2.0, "QT completed; neutral policy rate range reached."),
        FomcDecision("2026-06-17", 3.25, 3.50, 0, 2.1, 4.1, 2.0, "Terminal neutral equilibrium sustained; balance sheet normalized."),
    ]

    PLUMBING_SNAPSHOTS: List[FedPlumbingSnapshot] = [
        FedPlumbingSnapshot("2023-Q1 (SVB / Hike)", 8450.0, 450.0, 2100.0, 3400.0, 5900.0),
        FedPlumbingSnapshot("2023-Q3 (Rate Peak)", 8100.0, 650.0, 1500.0, 3200.0, 5950.0),
        FedPlumbingSnapshot("2024-Q1 (Holding Peak)", 7600.0, 750.0, 500.0, 3500.0, 6350.0),
        FedPlumbingSnapshot("2024-Q3 (Jumbo Cut)", 7100.0, 800.0, 280.0, 3350.0, 6020.0),
        FedPlumbingSnapshot("2025-Q2 (QT Taper)", 6700.0, 750.0, 180.0, 3300.0, 5770.0),
        FedPlumbingSnapshot("2026-Q3 (Normalized)", 6400.0, 700.0, 120.0, 3250.0, 5580.0),
    ]

    @staticmethod
    def calculate_taylor_rule(
        r_star: float,
        inflation: float,
        target_inflation: float = 2.0,
        output_gap: float = 0.0,
    ) -> float:
        """Taylor (1993) rule: i = r* + pi + 0.5*(pi - pi*) + 0.5*(y - y*)."""
        return r_star + inflation + 0.5 * (inflation - target_inflation) + 0.5 * output_gap

    @staticmethod
    def calculate_inertial_taylor(
        previous_rate: float,
        unconstrained_taylor: float,
        rho: float = 0.85,
    ) -> float:
        """Inertial policy rate smoothing: i_t = rho * i_{t-1} + (1 - rho) * i_taylor."""
        return rho * previous_rate + (1 - rho) * unconstrained_taylor

    def audit_cycle_phases(self) -> Dict[str, Dict]:
        """Decomposes the 3-year cycle into 4 structural macro phases."""
        phases = {
            "Phase_1_Terminal_Hunt_2023": {
                "name": "Zirve Avı & 'Higher-for-Longer' Rejimi (2023)",
                "rate_range": "4.25% -> 5.50%",
                "core_driver": "1980'lerden bu yana en hızlı sıkılaşmanın finali. Enflasyonun %9'dan %4'e inişi, SVB krizi ve BTFP kalkanı.",
                "max_rate": 5.50,
                "real_fed_funds_rate": "Peak +1.30% (Pozitif kısıtlayıcı bölge)",
                "yield_curve_2y10y": "Tarihi Ters Dönme (-108 bps, Temmuz 2023)",
                "net_liquidity_impact": "ON RRP 2.2T $'dan 1.5T $'a düşerek QT etkisini emdi.",
            },
            "Phase_2_Dovish_Pivot_2024": {
                "name": "Sabır ve Büyük Gevşeme Pivotu (2024)",
                "rate_range": "5.50% -> 4.50% (100 bps kümülatif indirim)",
                "core_driver": "İstihdam soğuması (Sahm Kuralı alarmı) ve dezenflasyonun %2.6'ya inişi. 18 Eylül 50 bps Jumbo indirim.",
                "max_rate": 5.50,
                "real_fed_funds_rate": "+1.90% (Reel faiz aşırı kısıtlayıcı hale geldiği için indirim zorunlu oldu)",
                "yield_curve_2y10y": "Eğri 2 yıl sonra pozitife döndü (Un-inversion / Bull Steepener)",
                "net_liquidity_impact": "QT Treasury limiti 60B$'dan 25B$'a düşürüldü; ON RRP 300B$'ın altına indi.",
            },
            "Phase_3_Neutral_Seeking_2025": {
                "name": "Nötr Faiz ($r^*$) Arayışı ve QT Sonu (2025)",
                "rate_range": "4.50% -> 3.50%",
                "core_driver": "Yumuşak iniş (Soft Landing) başarısı; enflasyon %2.2'ye demirlendi, faizler nötr banda çekildi.",
                "max_rate": 4.50,
                "real_fed_funds_rate": "+1.30% (Denge reel faizi)",
                "yield_curve_2y10y": "Normal pozitif eğim (+30 bps term primi)",
                "net_liquidity_impact": "Bilanço 6.6T $'da durduruldu (LCLoR banka rezerv eşiği korundu).",
            },
            "Phase_4_Equilibrium_2026": {
                "name": "Yeni Makro Denge & Finansal İstikrar (2026 Mevcut)",
                "rate_range": "%3.25 - %3.50 (Sabit / Nötr)",
                "core_driver": "Yeni denge; nötr faiz seviyesinde verimlilik ve mali harcamalarla dengelenen büyüme.",
                "max_rate": 3.50,
                "real_fed_funds_rate": "+1.15% (Doğal faiz $r^*$ ile tam uyumlu)",
                "yield_curve_2y10y": "Sağlıklı pozitif eğim (+45 bps)",
                "net_liquidity_impact": "Banka rezervleri 3.25T $ (GSYİH'nin %11'i, güvenli likidite bölgesi).",
            },
        }
        return phases

    def audit_taylor_gap_timeline(self) -> List[Dict]:
        """Calculates policy stance and Taylor gap across key moments in 2023-2026."""
        results = []
        for d in self.FOMC_HISTORY:
            mid_rate = (d.target_range_lower + d.target_range_upper) / 2.0
            taylor_rate = self.calculate_taylor_rule(
                r_star=1.25,
                inflation=d.core_pce_pct,
                target_inflation=2.0,
                output_gap=0.2 if d.real_gdp_growth_pct >= 2.0 else -0.3,
            )
            gap = mid_rate - taylor_rate
            real_rate = mid_rate - d.core_pce_pct
            
            stance = "NEUTRAL"
            if gap > 0.5:
                stance = "RESTRICTIVE (Kısıtlayıcı)"
            elif gap < -0.5:
                stance = "ACCOMMODATIVE (Gevşek)"
            else:
                stance = "BALANCED (Dengeli)"

            results.append({
                "date": d.date,
                "fed_funds_mid": mid_rate,
                "core_pce": d.core_pce_pct,
                "real_fed_funds": round(real_rate, 2),
                "taylor_recommendation": round(taylor_rate, 2),
                "policy_gap": round(gap, 2),
                "stance": stance,
                "description": d.description,
            })
        return results


def run_cli_audit():
    """Generates execution report on stdout."""
    auditor = FedRateCycleAuditor()
    phases = auditor.audit_cycle_phases()
    timeline = auditor.audit_taylor_gap_timeline()

    print("================================================================================")
    print(" 🏛️ [FINANCIAL-AUDITOR] FED 3 YILLIK FAİZ VE MAKRO TESİSAT ANALİZ RAPORU (2023-2026)")
    print("================================================================================")
    
    for phase_key, data in phases.items():
        print(f"\n▶ {data['name']}")
        print(f"  • Politika Bandı: {data['rate_range']}")
        print(f"  • Temel Dinamik: {data['core_driver']}")
        print(f"  • Reel Politika Faizi: {data['real_fed_funds_rate']}")
        print(f"  • Getiri Eğrisi (2Y-10Y): {data['yield_curve_2y10y']}")
        print(f"  • Bilanço & Likidite Tesisatı: {data['net_liquidity_impact']}")

    print("\n--------------------------------------------------------------------------------")
    print(" 📊 KRİTİK FOMC DÖNÜM NOKTALARI VE TAYLOR KURALI POLİTİKA AÇIĞI:")
    print("--------------------------------------------------------------------------------")
    for item in timeline:
        if item["date"] in ["2023-02-01", "2023-07-26", "2023-12-13", "2024-09-18", "2024-12-18", "2025-12-17", "2026-06-17"]:
            print(f"[{item['date']}] Fed: %{item['fed_funds_mid']:.2f} | Çekirdek PCE: %{item['core_pce']:.1f} | Reel Faiz: %{item['real_fed_funds']:+.2f} | Taylor: %{item['taylor_recommendation']:.2f} | Duruş: {item['stance']}")


if __name__ == "__main__":
    run_cli_audit()
