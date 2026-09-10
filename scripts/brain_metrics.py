"""
Beyin ölçüm paketi (Faz 11.13) — K1..K12 raporu.

**Salt okunur.** Verilen veritabanını hiç değiştirmez; yalnızca `SELECT` yapar
ve gömmeleri bellekte kullanır. Model çağrısı yapmaz.

Kullanım:
    python scripts/brain_metrics.py                 # varsayılan profil DB
    python scripts/brain_metrics.py --db <yol> --json
    python scripts/brain_metrics.py --skip-recall   # K2/K3'ü atla (hızlı)

Ölçütler (kaynak: docs/reports/2026-09-10_Faz11_Arastirma_A_Hafiza_ve_RAG.md §4.8):

| # | Ölçüt | Hedef |
|---|---|---|
| K1  | yineleme oranı (cos >= 0,92 fazlalık) | <= %10 |
| K2  | Hit@1 / Hit@5 (kör test) | >= 8/10, >= 10/10 |
| K3  | top-5 gürültü oranı | <= %2 |
| K7  | kategori disiplini | tam 4 kanonik ad |
| K10 | fikstür sızıntısı | 0 düğüm |
| K11 | yazma yolu (kapı) gecikmesi | <= 400 ms |
| K12 | kaynaksız L2 (semantic) düğümü | 0 |

K4/K5/K6/K8/K9 bağlam derleyici ve tur harness'ı tarafında ölçülür; burada
yalnızca kuyruk sayacı (K9 ham girdisi) raporlanır.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from entropy.memory.categories import CANONICAL_CATEGORIES  # noqa: E402
from entropy.memory.gate import LEGACY_PROVENANCE  # noqa: E402
from entropy.memory.supabase.cognitive_memory import (  # noqa: E402
    CognitiveMemorySystem,
    default_cognitive_db_path,
)

# Hedefler (raporun §4.8 tablosu)
K1_MAX_DUP_PCT = 10.0
K2_MIN_HIT1 = 8
K2_MIN_HIT5 = 10
K3_MAX_NOISE_PCT = 2.0
K7_EXPECTED_CATEGORIES = set(CANONICAL_CATEGORIES)
K10_MAX_FIXTURE = 0
K11_MAX_GATE_MS = 400.0
K12_MAX_UNSOURCED = 0

DUP_THRESHOLD = 0.92

# K10: üretim hafızasına asla girmemesi gereken kalıplar (kör testin gürültü
# tanımıyla aynı; kapının `_FIXTURE_PATTERNS` kümesinin gözlemlenebilir hâli).
FIXTURE_RE = re.compile(
    r"Ofis:\s.*·.*\breview\b|pytest|\[KANIT\]\s*Komut:|dummy\s*proc|(?:^|[\s/\\`'\"(])test_[a-z0-9_]+",
    re.IGNORECASE | re.DOTALL,
)

L2_CATEGORY = "semantic"


# --------------------------------------------------------------------------
# ham okuma
# --------------------------------------------------------------------------

def read_rows(db_path: Path) -> List[Dict[str, Any]]:
    """`cognitive_nodes` satırlarını salt okunur açar."""
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cognitive_nodes)")}
        rows = []
        for row in conn.execute("SELECT * FROM cognitive_nodes"):
            item = {k: row[k] for k in row.keys()}
            item["_embedding"] = _parse_embedding(item.get("embedding_json"))
            rows.append(item)
        for row in rows:
            row["_has_provenance"] = bool((row.get("provenance") or "").strip()) if "provenance" in cols else False
        return rows
    finally:
        conn.close()


def _parse_embedding(raw: Any) -> Optional[List[float]]:
    if raw in (None, "", b""):
        return None
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except Exception:
            return None
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except Exception:
            return None
    else:
        value = raw
    if isinstance(value, list) and value:
        try:
            return [float(x) for x in value]
        except Exception:
            return None
    return None


# --------------------------------------------------------------------------
# K1 — yineleme
# --------------------------------------------------------------------------

def duplication_ratio(rows: Sequence[Dict[str, Any]], threshold: float = DUP_THRESHOLD) -> Dict[str, Any]:
    """
    Union-find kümeleme: cos >= eşik olan düğümler aynı kümeye girer.
    Yineleme oranı = (düğüm sayısı - küme sayısı) / düğüm sayısı.
    """
    vectors = [(i, r["_embedding"]) for i, r in enumerate(rows) if r.get("_embedding")]
    n = len(vectors)
    if n < 2:
        return {"nodes_with_embedding": n, "clusters": n, "duplicate_pct": 0.0, "threshold": threshold}

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    try:
        import numpy as np  # noqa: WPS433

        mat = np.array([v for _, v in vectors], dtype="float32")
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms
        # Blok blok: 1.500 x 1.500 tek seferde de sığar ama büyük DB'de bölmek gerekir.
        block = 512
        for start in range(0, n, block):
            sims = mat[start:start + block] @ mat.T
            idx_i, idx_j = (sims >= threshold).nonzero()
            for a, b in zip(idx_i.tolist(), idx_j.tolist()):
                gi = start + a
                if gi < b:
                    union(gi, b)
    except ImportError:  # numpy yoksa saf Python
        for i in range(n):
            vi = vectors[i][1]
            for j in range(i + 1, n):
                if _cosine(vi, vectors[j][1]) >= threshold:
                    union(i, j)

    clusters = len({find(i) for i in range(n)})
    return {
        "nodes_with_embedding": n,
        "clusters": clusters,
        "duplicate_pct": round(100.0 * (n - clusters) / n, 2),
        "threshold": threshold,
    }


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# --------------------------------------------------------------------------
# K7 / K10 / K12
# --------------------------------------------------------------------------

def category_report(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row.get("category") or ""] = counts.get(row.get("category") or "", 0) + 1
    extra = sorted(set(counts) - K7_EXPECTED_CATEGORIES)
    return {
        "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "distinct": len(counts),
        "non_canonical": extra,
    }


def fixture_leak(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    hits = [r["id"] for r in rows if FIXTURE_RE.search(r.get("content") or "")]
    return {"count": len(hits), "sample_ids": hits[:5]}


def unsourced_l2(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    K12 = kaynaksız L2 sayısı.

    Faz 11 kapanışı: `legacy:pre-v2` etiketli düğümler (v2 öncesinden gelen,
    kaynağı hiçbir zaman kaydedilmemiş düğümler) K12'ye SAYILMAZ — uydurma
    kaynak yazmak yerine dürüstçe etiketlendiler. Gizlenmesinler diye ayrı
    sayaçta raporlanırlar: `legacy_untagged`. K12 böylece yalnızca "yeni yazma
    yolundan kaynaksız geçmiş L2 düğümü" ölçer; hedef hâlâ 0.
    """
    hits: List[str] = []
    legacy: List[str] = []
    for r in rows:
        if r.get("category") != L2_CATEGORY:
            continue
        prov = (r.get("provenance") or "").strip()
        if prov == LEGACY_PROVENANCE:
            legacy.append(r["id"])
        elif not r.get("_has_provenance"):
            hits.append(r["id"])
    return {
        "count": len(hits),
        "sample_ids": hits[:5],
        "legacy_untagged": len(legacy),
        "legacy_sample_ids": legacy[:5],
    }


# --------------------------------------------------------------------------
# K11 — kapı gecikmesi (salt okunur: karar alınır, yazılmaz)
# --------------------------------------------------------------------------

def gate_latency(db_path: Path, samples: int = 9) -> Dict[str, Any]:
    """
    `MemoryGate.admit()` çağrı süresini ölçer. **Yazmaz**: yalnızca kararı alır,
    dönen `GateDecision` atılır.
    """
    mem = CognitiveMemorySystem(db_path=db_path)
    gate = mem.gate
    durations: List[float] = []
    for i in range(samples):
        content = (
            f"Ölçüm adayı {i}: kapı gecikmesi ölçümü için üretilen, korpusta "
            f"bulunmayan yeterince uzun bir aday metin ({i * 7}). "
            "Bu metin diske yazılmaz."
        )
        started = time.perf_counter()
        gate.admit("semantic", content, provenance="scripts/brain_metrics.py")
        durations.append((time.perf_counter() - started) * 1000.0)
    warm = durations[1:] or durations
    return {
        "samples": len(durations),
        "first_ms": round(durations[0], 1),
        "median_ms": round(statistics.median(warm), 1),
        "max_ms": round(max(warm), 1),
    }


def gray_queue_count(db_path: Path) -> int:
    """K9 ham girdisi: gri bant kuyruğundaki satır sayısı."""
    path = Path(db_path).parent / "memory" / "gray_queue.jsonl"
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


# --------------------------------------------------------------------------
# toplu rapor
# --------------------------------------------------------------------------

def collect(
    db_path: Path,
    include_recall: bool = True,
    include_latency: bool = True,
    dup_threshold: float = DUP_THRESHOLD,
) -> Dict[str, Any]:
    rows = read_rows(db_path)
    report: Dict[str, Any] = {
        "db": str(db_path),
        "nodes": len(rows),
        "K1_duplication": duplication_ratio(rows, dup_threshold),
        "K7_categories": category_report(rows),
        "K10_fixture_leak": fixture_leak(rows),
        "K12_unsourced_l2": unsourced_l2(rows),
        "K9_gray_queue_rows": gray_queue_count(db_path),
    }
    if include_recall:
        from memory_blind_test import run as blind_run  # noqa: WPS433

        blind = blind_run(Path(db_path), include_episodic=False)
        report["K2_K3_recall"] = {
            "hit@1": blind["hit@1"],
            "hit@5": blind["hit@5"],
            "noise_ratio_pct": blind["noise_ratio_pct"],
            "latency_ms_median": blind["latency_ms_median"],
        }
    if include_latency:
        report["K11_gate_latency"] = gate_latency(Path(db_path))
    report["verdict"] = verdict(report)
    return report


def verdict(report: Dict[str, Any]) -> Dict[str, Any]:
    """Her ölçüt için PASS/FAIL. Ölçülmeyen ölçüt raporda yer almaz."""
    out: Dict[str, Any] = {}
    dup = report.get("K1_duplication")
    if dup:
        out["K1"] = "PASS" if dup["duplicate_pct"] <= K1_MAX_DUP_PCT else "FAIL"
    recall = report.get("K2_K3_recall")
    if recall:
        hit1 = int(str(recall["hit@1"]).split("/")[0])
        hit5 = int(str(recall["hit@5"]).split("/")[0])
        out["K2"] = "PASS" if (hit1 >= K2_MIN_HIT1 and hit5 >= K2_MIN_HIT5) else "FAIL"
        out["K3"] = "PASS" if recall["noise_ratio_pct"] <= K3_MAX_NOISE_PCT else "FAIL"
    cats = report.get("K7_categories")
    if cats:
        out["K7"] = "PASS" if not cats["non_canonical"] else "FAIL"
    leak = report.get("K10_fixture_leak")
    if leak:
        out["K10"] = "PASS" if leak["count"] <= K10_MAX_FIXTURE else "FAIL"
    lat = report.get("K11_gate_latency")
    if lat:
        out["K11"] = "PASS" if lat["median_ms"] <= K11_MAX_GATE_MS else "FAIL"
    uns = report.get("K12_unsourced_l2")
    if uns:
        out["K12"] = "PASS" if uns["count"] <= K12_MAX_UNSOURCED else "FAIL"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Beyin ölçüm paketi (K1..K12)")
    ap.add_argument("--db", default=str(default_cognitive_db_path()))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skip-recall", action="store_true", help="K2/K3'ü atla")
    ap.add_argument("--skip-latency", action="store_true", help="K11'i atla")
    ap.add_argument("--dup-threshold", type=float, default=DUP_THRESHOLD)
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"Veritabanı yok: {db}")
        return 2

    report = collect(
        db,
        include_recall=not args.skip_recall,
        include_latency=not args.skip_latency,
        dup_threshold=args.dup_threshold,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"DB        : {report['db']}  ({report['nodes']} düğüm)")
    k1 = report["K1_duplication"]
    print(f"K1 yineleme : %{k1['duplicate_pct']}  ({k1['clusters']} küme / {k1['nodes_with_embedding']} düğüm)")
    if "K2_K3_recall" in report:
        r = report["K2_K3_recall"]
        print(f"K2 isabet   : Hit@1 {r['hit@1']} · Hit@5 {r['hit@5']}")
        print(f"K3 gürültü  : %{r['noise_ratio_pct']}")
    cats = report["K7_categories"]
    print(f"K7 kategori : {cats['distinct']} ad · kanonik dışı: {cats['non_canonical'] or 'yok'}")
    print(f"K9 gri kuyruk: {report['K9_gray_queue_rows']} satır")
    print(f"K10 fikstür : {report['K10_fixture_leak']['count']}")
    if "K11_gate_latency" in report:
        print(f"K11 kapı    : medyan {report['K11_gate_latency']['median_ms']} ms")
    print(f"K12 kaynaksız L2: {report['K12_unsourced_l2']['count']}"
          f"  (eski etiketli: {report['K12_unsourced_l2'].get('legacy_untagged', 0)})")
    print(f"Karar       : {report['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
