"""
Inject SAHOL Financial Audit findings into Entropy AI's Cognitive Memory System.
"""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem


def main():
    mem = CognitiveMemorySystem()
    memories = [
        (
            "episodic",
            "SAHOL (Hacı Ömer Sabancı Holding A.Ş.) Finansal Denetim: 8 Eylül 2026 tarihinde 3 Eylül 2026 InvestingPro raporu incelendi. Güncel fiyat ₺92.50, piyasa değeri ₺194.3B, cari F/K 9.65x, defter değeri ₺199.60 (%53.7 iskonto, 0.46x PD/DD), InvestingPro adil değeri ₺101.65 (+%9.9), konsensüs analist hedefi ₺162.73 (+%75.9).",
            0.98,
            {"ticker": "IS:SAHOL", "type": "financial_audit", "company": "Sabancı Holding"}
        ),
        (
            "semantic",
            "SAHOL Bilanço ve NAV İskontosu: Holding hisseleri bünyesindeki Akbank, Enerjisa, Kordsa, Çimsa gibi şirketlerin BIST değerlerine kıyasla derin NAV iskontosuyla (%53.7 defter değeri iskontosu) işlem görmektedir. Q2 2026 net kârı ₺14.16B ile kriz sonrası en güçlü çeyreklik performansı göstermiştir. 2024-2029 hedefi 20 Milyar USD NAV ve >=%30 döviz gelir payıdır.",
            0.99,
            {"ticker": "IS:SAHOL", "type": "nav_discount", "pb_ratio": 0.46}
        ),
        (
            "procedural",
            "SAHOL 1 Haftalık Teknik Beklenti: Teknik indikatörler 'Strong Buy' konumundadır. 1 aydaki %6.9'luk primin ardından son haftadaki -%1.3'lük hareket sağlıklı bir flama konsolidasyonudur. ₺91.20 desteği korundukça 1 hafta içinde ₺95.50 – ₺98.00 direnç bandına doğru yükseliş olasılığı %64-%68 ile yüksektir.",
            0.99,
            {"ticker": "IS:SAHOL", "type": "short_term_momentum", "verdict": "Yükseliş Beklenir"}
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
    print("SAHOL memories successfully recorded into CognitiveMemorySystem.")


if __name__ == "__main__":
    main()
