"""
Inject ATATP Financial Audit findings into Entropy AI's Cognitive Memory System.
"""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem


def main():
    mem = CognitiveMemorySystem()
    memories = [
        (
            "episodic",
            "ATATP (ATP Yazılım ve Teknoloji A.Ş.) Finansal Denetim: 7 Eylül 2026 tarihinde 3 Eylül 2026 InvestingPro raporu incelendi. Şirketin güncel hisse fiyatı ₺293.75, piyasa değeri ₺27.5B, cari F/K 13.98x, FY26 ileri F/K 9.80x, FY27 ileri F/K 5.52x, FY28 ileri F/K 3.63x, analist konsensüs adil değeri ₺387.70 (+%32 potansiyel).",
            0.98,
            {"ticker": "IS:ATATP", "type": "financial_audit", "company": "ATP Yazılım"}
        ),
        (
            "semantic",
            "ATATP SaaS ve Kâr Kalitesi Bulguları: Şirket %84.70 brüt kâr marjı, %67.31 FAVÖK marjı ve %145.05 Rule of 40 skoru ile global elit kurumsal SaaS seviyesindedir. Yinelenen gelir payı >%50, döviz geliri %46, uluslararası satış payı %26'dır. Bilançosu ₺10.28B özkaynağa karşı sadece ₺70.6M borç ile net nakit pozisyonunda olup temerrüt riski sıfırdır.",
            0.99,
            {"ticker": "IS:ATATP", "type": "saas_metrics", "rule_of_40": 145.05}
        ),
        (
            "procedural",
            "ATATP Nakit Akış Anomalisi ve Katalizör: Raporlanan -%9.01 FCF verimi ve -₺1.618M LTM CFO, tamamen Q3 2025'teki tek seferlik -₺1.691M'luk çalışma sermayesi/portföy çıkışından kaynaklanmaktadır. Son 3 çeyrekte (Q4 25, Q1 26, Q2 26) operasyonel nakit akışı kesintisiz pozitif (+₺825.6M) seyretmiştir. 6 Kasım 2026 Q3 bilançosuyla Q3 2025 baz etkisinin düşmesi (roll-off) LTM CFO'yu pozitif +₺1.1B-₺1.4B seviyesine fırlatacak ana katalizördür.",
            0.99,
            {"ticker": "IS:ATATP", "type": "forensic_cash_flow", "catalyst_date": "2026-11-06"}
        )
    ]

    for cat, content, score, meta in memories:
        node, is_novel = mem.record_memory(
            category=cat,
            content=content,
            importance=score,
            metadata=meta
        )
        status = "NOVEL" if is_novel else "UPDATED"
        print(f"[{status}] [{cat.upper()}] {content[:70]}...")
    print("ATATP memories successfully recorded into CognitiveMemorySystem.")


if __name__ == "__main__":
    main()
