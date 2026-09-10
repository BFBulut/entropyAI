#!/usr/bin/env python3
"""Quantitative Simulator and Decision Engine for Corporate Earnings Announcements.
Models Earnings Surprise (SUE), Priced-in Expectations, Forward Guidance,
Quality of Earnings (CFO/Net Income), and Post-Earnings Announcement Drift (PEAD).
"""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class EarningsReportInput:
    symbol: str
    consensus_net_profit: float
    actual_net_profit: float
    consensus_revenue: float
    actual_revenue: float
    pre_earnings_runup_pct: float  # Stock return in 1-3 months prior to earnings (%)
    guidance_revision_pct: float   # Change in full-year forecast by management (%)
    cfo_to_net_income_ratio: float # Operating Cash Flow / Net Income (Earnings Quality)


def calculate_earnings_reaction(report: EarningsReportInput) -> Dict[str, Any]:
    """Evaluates corporate financial results and simulates the expected market reaction.
    
    Returns:
        Dict containing surprise metrics, composite score, expected reaction category,
        volatility expectation, and detailed qualitative reasoning.
    """
    if report.consensus_revenue <= 0 or report.actual_revenue <= 0:
        raise ValueError("Revenue figures must be positive.")

    # 1. Earnings Surprise (SUE Metric)
    if report.consensus_net_profit != 0:
        profit_surprise_pct = (
            (report.actual_net_profit - report.consensus_net_profit)
            / abs(report.consensus_net_profit)
        ) * 100.0
    else:
        profit_surprise_pct = 100.0 if report.actual_net_profit > 0 else -100.0

    revenue_surprise_pct = (
        (report.actual_revenue - report.consensus_revenue)
        / report.consensus_revenue
    ) * 100.0

    # 2. Quality of Earnings Multiplier (Sloan Accrual check)
    # If CFO / Net Income < 0.5, profits are largely paper accruals/non-cash -> penalty
    if report.cfo_to_net_income_ratio >= 1.0:
        quality_factor = 1.15
        quality_verdict = "YÜKSEK (Kâr reel nakit akışıyla destekleniyor)"
    elif report.cfo_to_net_income_ratio >= 0.7:
        quality_factor = 1.0
        quality_verdict = "SAĞLIKLI (Normal operasyonel nakit dönüşümü)"
    elif report.cfo_to_net_income_ratio >= 0.3:
        quality_factor = 0.8
        quality_verdict = "ZAYIF (Kârın önemli kısmı alacaklarda/stoklarda bağlı)"
    else:
        quality_factor = 0.5
        quality_verdict = "ÇOK RİSKLİ (Kağıt üzerinde kâr; nakit girişi yok/negatif)"

    # 3. Base Surprise Score (-50 to +50)
    # Profit surprise carries 70% weight, revenue carries 30% weight
    weighted_surprise = (profit_surprise_pct * 0.70) + (revenue_surprise_pct * 0.30)
    raw_surprise_score = max(-50.0, min(50.0, weighted_surprise)) * quality_factor

    # 4. Guidance Revision Impact (-30 to +30)
    # Guidance represents future discounted cash flows
    guidance_score = max(-30.0, min(30.0, report.guidance_revision_pct * 2.0))

    # 5. "Priced-in" Penalty / Momentum Adjustment (-30 to +15)
    # If stock ran up >25% prior to earnings, market was already expecting a blow-out report.
    # If surprise is only mild (<15%), huge runup triggers "Sell the News" profit taking!
    runup_penalty = 0.0
    if report.pre_earnings_runup_pct > 30.0:
        if profit_surprise_pct < 20.0:
            # High expectation gap: sharp profit taking
            runup_penalty = -25.0
        else:
            # Positive surprise beats even aggressive runup
            runup_penalty = -10.0
    elif report.pre_earnings_runup_pct > 15.0:
        if profit_surprise_pct <= 5.0:
            runup_penalty = -15.0
        else:
            runup_penalty = -5.0
    elif report.pre_earnings_runup_pct < -15.0:
        # Stock was heavily dumped before earnings; low hurdle rate
        if profit_surprise_pct > -5.0:
            runup_penalty = +15.0  # Relief rally ("en kötü geride kaldı")
        else:
            runup_penalty = -5.0

    # 6. Composite Reaction Score (-100 to +100)
    composite_score = raw_surprise_score + guidance_score + runup_penalty
    composite_score = max(-100.0, min(100.0, round(composite_score, 1)))

    # 7. Scenario Classification & Actionable Narrative
    if report.pre_earnings_runup_pct > 20.0 and profit_surprise_pct >= 0.0 and composite_score < 35.0:
        reaction_category = "BEKLENTİ ALINDI GERÇEK SATILDI (Sell the News / Kâr Satışı)"
        expected_price_movement = "-%2 ile -%7 arası geçici kâr realizasyonu"
        primary_driver = "Bilanço beklentileri karşılasa veya hafif aşsa da hisse öncesinde aşırı primlendiği için kâr satışı başladı."
    elif composite_score >= 35.0:
        reaction_category = "GÜÇLÜ YÜKSELİŞ VE RALLİ (PEAD - Pozitif Sürüklenme)"
        expected_price_movement = "+%5 ile +%15 arası yükseliş ve takip eden çeyrekte devam eğilimi"
        primary_driver = "Konsensüs üzeri net kâr, güçlü nakit akışı ve yukarı yönlü gelecek rehberliği."
    elif 10.0 <= composite_score < 35.0:
        reaction_category = "ILIMLI POZİTİF (Hafif Yükseliş / Güven Tazeleme)"
        expected_price_movement = "+%1.5 ile +%5 arası dengeli artış"
        primary_driver = "Beklentilere paralel veya hafif üzeri sonuçlar; istikrarlı marjlar."
    elif -10.0 <= composite_score < 10.0:
        reaction_category = "NÖTR / YATAY (Fiyatlanmış Sonuçlar)"
        expected_price_movement = "-%1.5 ile +%1.5 arası dalgalı bant"
        primary_driver = "Mali tablolar piyasa beklentileriyle birebir örtüştü; sürpriz faktörü yok."
    elif -35.0 <= composite_score < -10.0:
        reaction_category = "ILIMLI DÜŞÜŞ (Beklenti Altı Performans)"
        expected_price_movement = "-%2 ile -%6 arası satış baskısı"
        primary_driver = "Kâr marjlarında daralma veya hedeflerin hafif altında kalan operasyonel performans."
    else:
        reaction_category = "SERT SATIŞ / DÜŞÜŞ ŞOKU (Miss & Guidance Downgrade)"
        expected_price_movement = "-%6 ile -%15 arası sert geri çekilme veya taban fiyatlama"
        primary_driver = "Hem kârda ciddi sapma hem de şirketin geleceğe dönük hedeflerini aşağı revize etmesi."

    return {
        "symbol": report.symbol,
        "profit_surprise_pct": round(profit_surprise_pct, 2),
        "revenue_surprise_pct": round(revenue_surprise_pct, 2),
        "pre_earnings_runup_pct": round(report.pre_earnings_runup_pct, 2),
        "guidance_revision_pct": round(report.guidance_revision_pct, 2),
        "cfo_to_net_income_ratio": round(report.cfo_to_net_income_ratio, 2),
        "quality_verdict": quality_verdict,
        "composite_score": composite_score,
        "reaction_category": reaction_category,
        "expected_price_movement": expected_price_movement,
        "primary_driver": primary_driver,
        "is_sell_the_news": "BEKLENTİ ALINDI GERÇEK SATILDI" in reaction_category,
        "is_strong_bullish": composite_score >= 35.0,
        "is_bearish_shock": composite_score <= -35.0,
    }


if __name__ == "__main__":
    import json
    
    # Örnek 1: Beklenti Alındı Gerçek Satıldı (BIST Klasik Senaryo)
    sample_sell_the_news = EarningsReportInput(
        symbol="ORNEK1_SELL_NEWS",
        consensus_net_profit=1000.0,
        actual_net_profit=1050.0,  # Hafif üzeri (+%5 beat)
        consensus_revenue=8000.0,
        actual_revenue=8100.0,
        pre_earnings_runup_pct=35.0,  # Bilanço öncesi hisse %35 coşmuş
        guidance_revision_pct=0.0,
        cfo_to_net_income_ratio=0.85,
    )

    # Örnek 2: Güçlü Pozitif Sürpriz ve Ralli (PEAD)
    sample_super_beat = EarningsReportInput(
        symbol="ORNEK2_SUPER_BEAT",
        consensus_net_profit=1000.0,
        actual_net_profit=1450.0,  # +%45 dev sürpriz
        consensus_revenue=8000.0,
        actual_revenue=9200.0,
        pre_earnings_runup_pct=5.0,   # Öncesinde yatay kalmış
        guidance_revision_pct=15.0,  # Gelecek hedefleri artırıldı
        cfo_to_net_income_ratio=1.20, # Nakit akışı canavar gibi
    )

    print("--- SENARYO 1: Beklenti Alındı Gerçek Satıldı ---")
    print(json.dumps(calculate_earnings_reaction(sample_sell_the_news), indent=2, ensure_ascii=False))
    print("\n--- SENARYO 2: Çifte Sürpriz & Güçlü Ralli ---")
    print(json.dumps(calculate_earnings_reaction(sample_super_beat), indent=2, ensure_ascii=False))
