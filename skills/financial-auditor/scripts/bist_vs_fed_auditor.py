#!/usr/bin/env python3
"""BIST vs FED Transmission & Asset Allocation Auditor (2023 - 2026).

Quantitative Hedge Fund Analytics:
1. BIST 100 Annual Performance (TL & USD Terms) 2023-2026.
2. FED Rate Transmission Mechanism to Borsa Istanbul.
3. FOMC Announcement Volatility Patterns (Lucca-Moench Pre-FOMC Drift & Whipsaws).
4. Comparative Investment Decision Matrix: Borsa Istanbul vs. Wall Street (S&P 500/Nasdaq).
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math


@dataclass
class AnnualMarketPerformance:
    year: int
    bist_tl_start: float
    bist_tl_end: float
    usd_try_start: float
    usd_try_end: float
    sp500_start: float
    sp500_end: float

    @property
    def bist_tl_return_pct(self) -> float:
        return ((self.bist_tl_end - self.bist_tl_start) / self.bist_tl_start) * 100.0

    @property
    def bist_usd_start(self) -> float:
        return self.bist_tl_start / self.usd_try_start

    @property
    def bist_usd_end(self) -> float:
        return self.bist_tl_end / self.usd_try_end

    @property
    def bist_usd_return_pct(self) -> float:
        return ((self.bist_usd_end - self.bist_usd_start) / self.bist_usd_start) * 100.0

    @property
    def sp500_return_pct(self) -> float:
        return ((self.sp500_end - self.sp500_start) / self.sp500_start) * 100.0


class BistFedAuditor:
    """Audits BIST historical returns, FED sensitivity, and comparative allocation."""

    HISTORICAL_DATA: List[AnnualMarketPerformance] = [
        # 2023: High nominal TL inflation rally, but TRY devaluation resulted in USD loss
        AnnualMarketPerformance(2023, 5509.0, 7470.0, 18.71, 29.50, 3840.0, 4770.0),
        # 2024: Rating upgrades (Fitch/Moody's), FATF grey list exit, carry trade, foreign inflows
        AnnualMarketPerformance(2024, 7470.0, 9920.0, 29.50, 35.25, 4770.0, 5880.0),
        # 2025: TCMB rate cutting cycle begins, disinflation consolidation
        AnnualMarketPerformance(2025, 9920.0, 12600.0, 35.25, 39.80, 5880.0, 6420.0),
        # 2026 (YTD / Current Snapshot)
        AnnualMarketPerformance(2026, 12600.0, 13850.0, 39.80, 42.10, 6420.0, 6750.0),
    ]

    def audit_annual_returns(self) -> List[Dict]:
        """Calculates exact TL and USD returns for BIST vs S&P 500 for each year."""
        records = []
        for d in self.HISTORICAL_DATA:
            records.append({
                "year": d.year,
                "bist_tl_start": d.bist_tl_start,
                "bist_tl_end": d.bist_tl_end,
                "bist_tl_return_pct": round(d.bist_tl_return_pct, 2),
                "bist_usd_start": round(d.bist_usd_start, 2),
                "bist_usd_end": round(d.bist_usd_end, 2),
                "bist_usd_return_pct": round(d.bist_usd_return_pct, 2),
                "sp500_return_pct": round(d.sp500_return_pct, 2),
                "verdict_tl": "YÜKSELİŞ (Nominal TL)" if d.bist_tl_return_pct > 0 else "DÜŞÜŞ (Nominal TL)",
                "verdict_usd": "YÜKSELİŞ (Reel Dolar)" if d.bist_usd_return_pct > 0 else "DÜŞÜŞ (Reel Dolar)",
            })
        return records

    def audit_transmission_channels(self) -> Dict[str, Dict]:
        """Maps out the 5 core transmission channels from FED to Borsa Istanbul."""
        channels = {
            "channel_1_global_liquidity": {
                "name": "Küresel Likidite ve Risk İştahı (Risk-On / Risk-Off)",
                "mechanism": "Fed faiz indirdiğinde küresel likidite bollaşır. Gelişmiş piyasalarda getiri arayışı (Yield Seeking) artar ve fonlar Gelişmekte Olan Piyasalara (EM) ve BIST'e akar.",
                "fed_hiking_impact": "Negatif: Fonlar anavatana (ABD Doları/Hazine Bonoları) kaçar, EM borsalarından yabancı çıkışı olur.",
                "fed_cutting_impact": "Pozitif: Gelişmekte olan ülkelere portföy girişleri hızlanır, BIST yabancı takas oranı yükselir.",
            },
            "channel_2_dxy_and_em_currencies": {
                "name": "Dolar Endeksi (DXY) ve Kur Baskısı",
                "mechanism": "Fed faiz artırınca DXY yükselir, USD/TRY üzerinde yukarı yönlü baskı oluşur. Kur şoku yerli şirketlerin döviz borcu maliyetini artırır.",
                "fed_hiking_impact": "TL değer kaybeder, ithal girdi maliyetleri ve kur riski kâr marjlarını baskılar.",
                "fed_cutting_impact": "DXY zayıflar, TL üzerindeki değer kaybı baskısı hafifler, TCMB rezerv biriktirir.",
            },
            "channel_3_tcmb_policy_room": {
                "name": "TCMB'nin Politika Alanı (Monetary Leeway)",
                "mechanism": "Fed'in yüksek faiz politikası TCMB'yi faizleri daha uzun süre yüksek tutmaya zorlar. Fed faiz indirdiğinde TCMB'nin iç piyasada faiz indirme alanı genişler.",
                "fed_hiking_impact": "Yüksek iç borçlanma maliyeti, BIST sanayi şirketlerinin finansman giderlerini patlatır.",
                "fed_cutting_impact": "TCMB rahat faiz indirir; kredi faizleri düşer, BIST şirketlerinin değerlemeleri (DCF çarpanları) yükselir.",
            },
            "channel_4_turkey_cds_and_eurobond": {
                "name": "Türkiye 5 Yıllık CDS ve Eurobond Borçlanma Maliyeti",
                "mechanism": "Fed faizleri ABD risksiz faiz oranını belirler. Fed faiz indirdikçe Türk Hazine ve özel sektör Eurobond kuponları ucuzlar, CDS risk primi geriler.",
                "fed_hiking_impact": "Türkiye CDS'i yükselir (2022'de 700-900 bps bandına çıkmıştı), bankaların sendikasyon maliyetleri artar.",
                "fed_cutting_impact": "CDS 250-280 bps seviyelerine geriler, Türk bankalarının özkaynak kârlılığı (ROE) ve BIST Bankacılık Endeksi (XBANK) ralli yapar.",
            },
            "channel_5_commodity_and_energy": {
                "name": "Emtia ve Enerji Fiyatları (Petrol / İthalat Faturası)",
                "mechanism": "Fed politikası küresel talebi ve dolar cinsinden emtia fiyatlarını belirler. Türkiye enerji ithalatçısı bir ülke olduğu için cari açık ve şirket kârlılığı doğrudan etkilenir.",
                "fed_hiking_impact": "Yüksek emtia + pahalı dolar = Çifte cari açık baskısı.",
                "fed_cutting_impact": "Emtia maliyetlerinin dengelenmesi, cari açığın daralması ve BIST'te kâr marjlarının toparlanması.",
            },
        }
        return channels

    def audit_fomc_microstructure_volatility(self) -> Dict[str, str]:
        """Explains intraday and swing volatility regimes during FOMC announcements."""
        return {
            "pre_fomc_drift": "FOMC toplantısından 24 saat önce piyasada genellikle 'bekle-gör' düşük hacmi ve riskten kaçınma süzülmesi (drift) görülür.",
            "announcement_shock_1400_est": "TSİ 21:00 (14:00 EST) Karar Metni ve Dot Plot açıklanır. Algoritmalar saniyeler içinde karar metnindeki şahin/güvercin sözcük frekansını tarar. BIST gece kapalı olduğu için ilk etki ertesi sabah açılışta GAP (fiyat boşluğu) olarak yansır.",
            "press_conference_whipsaw_1430_est": "TSİ 21:30 (14:30 EST) Powell basın toplantısı. Powell'ın her tonlama değişikliğiyle piyasalarda çift yönlü 'whipsaw' (silkeleme/testere) dalgalanmaları oluşur.",
            "volatility_crush": "Karar sonrası belirsizliğin kalkmasıyla Opsiyon İma Edilen Volatilitesi (IV / VIX) aniden çöker (Volatility Crush). Piyasalar temel trendine oturur.",
        }

    def evaluate_bist_vs_us_stocks(self) -> Dict[str, Dict]:
        """Provides institutional-grade comparative allocation decision."""
        comparison = {
            "bist_pros_cons": {
                "pros": [
                    "Çok Düşük Çarpanlar (Deep Value): F/K 6-8x, PD/DD 1.2-1.6x bandıyla küresel emsallerine göre %45-55 iskontolu.",
                    "Yüksek Enflasyon Kalkanı: Şirketlerin ciroları ve varlık değerleri enflasyonla paralel yeniden değerlenir.",
                    "TCMB Faiz İndirim Potansiyeli: 2025-2026 gevşeme döngüsü hisse değerlemelerine güçlü kaldıraç sağlar.",
                    "Vergi Avantajı: BIST hisselerinde gerçek kişiler için stopaj ve gelir vergisi muafiyeti (%0 vergi).",
                ],
                "cons": [
                    "Kur Riski (TL Değer Kaybı): TL bazında %50 kazansanız bile dolar bazında reel getiri eriyebilir.",
                    "Siyasi & Jeopolitik Risk Primi: Yabancı yatırımcı ani şoklarda hızlı likidite çıkışı yapabilir.",
                    "Sığ Derinlik: Birkaç büyük BIST 30 hissesi dışında hacim likiditesi kısıtlıdır.",
                ],
            },
            "us_stocks_pros_cons": {
                "pros": [
                    "Dolar Bazlı Reel Büyüme: Dünyanın rezerv para birimi cinsinden kesintisiz bileşik getiri.",
                    "Yapay Zeka & Global Teknoloji Tekelleri: Nvidia, Microsoft, Apple, Google, Amazon gibi küresel nakit makinelerine doğrudan ortaklık.",
                    "Muazzam Likidite ve Şeffaflık: Dünyanın en derin sermaye piyasası, sıfır spread ile anında alım-satım.",
                    "Düşük Ülke Riski: Hukuki altyapı ve kurumsal yönetişim garantisi.",
                ],
                "cons": [
                    "Pahalı Çarpanlar (High Valuation): S&P 500 F/K 22-25x, Shiller CAPE >33x (Tarihsel ortalamaların çok üzerinde).",
                    "Vergi Yükümlülüğü: Türk vergi mevzuatına göre yurtdışı hisse kârları gelir vergisi dilimine (%15 - %40) tabidir.",
                    "Gecikmeli Kriz Riski: Fed faiz indirim döngüsünde geç kalırsa olası resesyon riski.",
                ],
            },
            "strategic_allocation_verdict": {
                "verdict": "HİBRİT ÇEKİRDEK-UYDU STRATEJİSİ (Core-Satellite Allocation)",
                "ideal_portfolio": "Yatırımcı portföyünü tek bir borsaya kilitlemek finansal olarak rasyonel değildir. İdeal strateji: %50-60 ABD Borsaları (S&P 500 / Nasdaq / Küresel Şirketler) çekirdek portföy olarak tutulmalı; %30-40 Borsa İstanbul (BIST 30 / Yüksek İskontolu Bankacılık & Sanayi Şampiyonları) ile Türk lirasındaki yüksek nominal getiri ve potansiyel ralli yakalanmalıdır.",
            },
        }
        return comparison


def run_bist_fed_audit():
    auditor = BistFedAuditor()
    returns = auditor.audit_annual_returns()
    channels = auditor.audit_transmission_channels()
    volatility = auditor.audit_fomc_microstructure_volatility()
    eval_matrix = auditor.evaluate_bist_vs_us_stocks()

    print("================================================================================")
    print(" 🇹🇷 BIST 100 FED FAİZ DÖNGÜSÜ YILLIK PERFORMANS VE AMERİKAN BORSASI KARŞILAŞTIRMASI")
    print("================================================================================")
    for r in returns:
        print(f"\n▶ Yıl: {r['year']}")
        print(f"  • BIST 100 (TL): {r['bist_tl_start']} -> {r['bist_tl_end']} ({r['bist_tl_return_pct']:+.2f}%) [{r['verdict_tl']}]")
        print(f"  • BIST 100 (USD): ${r['bist_usd_start']} -> ${r['bist_usd_end']} ({r['bist_usd_return_pct']:+.2f}%) [{r['verdict_usd']}]")
        print(f"  • S&P 500 (USD): {r['sp500_return_pct']:+.2f}%")


if __name__ == "__main__":
    run_bist_fed_audit()
