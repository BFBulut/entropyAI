"""
Kör geri çağırma testi (Faz 11 — göç öncesi/sonrası kıyas).

Denetim raporunun (2026-09-10, Ek A) 10 sorgusunu gerçek `hybrid_recall` koduyla
koşturur ve K2 (Hit@1 / Hit@5), K3 (top-5 gürültü oranı) ve gecikmeyi ölçer.
**Salt okunur**: veritabanına yazmaz (gömme geri yazımı hariç, o da yalnızca
`--db` ile verilen dosyaya). Model çağrısı yapmaz.

Kullanım:
    python scripts/memory_blind_test.py                     # varsayılan profil DB
    python scripts/memory_blind_test.py --db <yol> --json
    python scripts/memory_blind_test.py --include-episodic   # eski (süzgeçsiz) kapsam
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from entropy.memory.supabase.cognitive_memory import (  # noqa: E402
    CognitiveMemorySystem,
    default_cognitive_db_path,
)

# (sorgu, ilgililik örüntüsü). Örüntüler denetim raporundaki beklenen
# düğümlerden türetildi; gerçek korpusun konularıdır, uydurma değil.
QUERIES = [
    ("Ohlson O-Score ile temerrüt olasılığı", r"ohlson|o-score"),
    ("Volatilite yüzeyini arbitrajsız modelleme SVI", r"svi|gatheral"),
    ("VaR geriye dönük test yöntemi Basel", r"kupiec|christoffersen|geri\s*test|var"),
    ("Trend takip eden hedge fon faktör modeli", r"fung|hsieh"),
    ("Bilanço gelir tablosu nakit akış birlikte okuma", r"bilanço|nakit akış|financial-auditor"),
    ("Piyasa yapıcılığında envanter riski optimal kontrol", r"ho\s*&?\s*stoll|envanter"),
    ("Agent harness nedir", r"harness"),
    ("MCP token maliyeti yerine kod yazdırma", r"codeact|mcp"),
    ("Çok ajanlı iş akışını DAG olarak planlama, kritik yol", r"dag|kritik yol|cpm"),
    ("Hata izolasyonu için denetim ağacı stratejileri", r"supervision|denetim ağac|erlang"),
]

# Gürültü = üretim hafızasında hiç bulunmaması gereken satır.
NOISE_RE = re.compile(
    r"Ofis:\s.*·.*\breview\b|pytest|\[KANIT\]\s*Komut:|dummy\s*proc",
    re.IGNORECASE | re.DOTALL,
)


def run(db_path: Path, include_episodic: bool, top_k: int = 5) -> dict:
    mem = CognitiveMemorySystem(db_path=db_path)
    rows, hit1, hit5, noise, total_rows = [], 0, 0, 0, 0
    latencies = []

    for query, pattern in QUERIES:
        rx = re.compile(pattern, re.IGNORECASE)
        started = time.perf_counter()
        hits = mem.hybrid_recall(query, top_k=top_k, include_episodic=include_episodic)
        latencies.append((time.perf_counter() - started) * 1000.0)

        ranks = [i + 1 for i, (node, _) in enumerate(hits) if rx.search(node.content or "")]
        first = ranks[0] if ranks else 0
        hit1 += 1 if first == 1 else 0
        hit5 += 1 if first and first <= 5 else 0
        for node, _ in hits:
            total_rows += 1
            if NOISE_RE.search(node.content or ""):
                noise += 1
        rows.append({
            "query": query,
            "rank": first,
            "top1": (hits[0][0].content[:90] if hits else ""),
            "top1_score": round(hits[0][1], 4) if hits else 0.0,
        })

    return {
        "db": str(db_path),
        "include_episodic": include_episodic,
        "nodes": len(mem.get_all_nodes()),
        "hit@1": f"{hit1}/{len(QUERIES)}",
        "hit@5": f"{hit5}/{len(QUERIES)}",
        "noise_rows": noise,
        "top5_rows": total_rows,
        "noise_ratio_pct": round(100.0 * noise / max(1, total_rows), 2),
        "latency_ms_first": round(latencies[0], 1) if latencies else 0.0,
        "latency_ms_median": round(sorted(latencies)[len(latencies) // 2], 1) if latencies else 0.0,
        "results": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Kör geri çağırma testi (K2/K3)")
    ap.add_argument("--db", default=str(default_cognitive_db_path()))
    ap.add_argument("--include-episodic", action="store_true",
                    help="L1 epizodik katmanı da kapsama al (göç öncesi eski davranış)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"Veritabanı yok: {db}")
        return 2

    report = run(db, args.include_episodic)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"DB      : {report['db']}  ({report['nodes']} düğüm)")
    print(f"Kapsam  : {'L1+L2+L3' if report['include_episodic'] else 'L2+L3 (varsayılan)'}")
    print(f"Hit@1   : {report['hit@1']}")
    print(f"Hit@5   : {report['hit@5']}")
    print(f"Gürültü : {report['noise_rows']}/{report['top5_rows']} (%{report['noise_ratio_pct']})")
    print(f"Gecikme : ilk {report['latency_ms_first']} ms · medyan {report['latency_ms_median']} ms")
    print("-" * 72)
    for row in report["results"]:
        mark = "OK@%d" % row["rank"] if row["rank"] else "KAÇIRDI"
        print(f"{mark:>8}  {row['query'][:46]:46}  {row['top1_score']:.3f}  {row['top1'][:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
