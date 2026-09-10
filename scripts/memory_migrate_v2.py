"""
Bilişsel bellek göçü: şema v1 -> **Brain v2** (Faz 11.5).

Karar (denetim raporu §5.2): *veritabanını yeni şema ile sıfırdan kur; eski
veriden yalnızca temiz çekirdeği, yazma kapısının kurallarından geçirerek göç
ettir.* Ne saf silme (36 benzersiz kantitatif finans düğümü yeniden
üretilemez), ne saf taşıma (17 kategori -> 4 kategori geçişi ve L1/L2 ayrımı
yerinde ALTER ile denetlenebilir değil).

Kademeli süzme (raporun ölçtüğü sıra):

    ham                                                1.544
    − fikstür / ofis kartı / `query` / < 40 karakter     −578      966
    − uydurma "N-Layer" mimari serisi                     −31      935
    − cos ≥ 0,92 yakın kopyalar (birleştirilir)          −267      668

**Varsayılan kip `--dry-run`**: kaynak veritabanına ve kasaya dokunmaz, yalnızca
sayı üretir. Kaynak her durumda geçici bir kopya üzerinden okunur (şema
yükseltmesi bile gerçek dosyaya değmesin diye). `--apply` yalnızca açıkça
istendiğinde yazar ve **önce yedek alır**:

    ~/.entropy/backups/cognitive_memory.pre-v2.<zaman>.db

Geri alma: yedeği geri kopyala + `ENTROPY_MEMORY_GATE=0`.

Model çağrısı yok, kota harcamaz. İdempotent: aynı kaynak üzerinde ikinci
koşum aynı hedefi üretir.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy pyproject'te sert bağımlılık
    np = None

from entropy.memory.categories import normalize_category  # noqa: E402
from entropy.memory.gate import (  # noqa: E402
    MIN_CONTENT_CHARS,
    derive_provenance,
    fixture_match,
)
from entropy.memory.supabase.cognitive_memory import (  # noqa: E402
    CognitiveMemoryNode,
    CognitiveMemorySystem,
    default_cognitive_db_path,
)

# Konsolidasyon eşiği yazma eşiğinden yüksektir (Hindsight, 21 May 2026):
# yazarken öncelik kopya engellemek, toplu birleştirmede ayrı bilgiyi korumak.
# 0,92 denetimde "gerçekten aynı şey"i toplayan banttı.
MERGE_THRESHOLD = 0.92

# Sistemin kendi ürettiği kurgu mimari serisi: "Pentacosa-Store 25-Layer
# Cognitive Memory Architecture" ... 29 farklı ad, 32 düğüm. Hiçbirinin dış
# kaynağı yok; §4.5'teki kaynak zorunluluğu tek başına hepsini engellerdi.
FAKE_ARCHITECTURE_RE = re.compile(
    r"\d{1,3}\s*-\s*Layer\s+Cognitive\s+Memory\s+Architecture"
    r"|\b[A-Z][a-z]+(?:a|i|o)-Store\s+\d{1,3}-Layer\b",
    re.IGNORECASE,
)

DROP_FIXTURE = "fixture"
DROP_SHORT = "short"
DROP_FAKE_ARCH = "fake_architecture"
DROP_MERGED = "merged_duplicate"


@dataclass
class MigrationPlan:
    source: str = ""
    source_nodes: int = 0
    kept: List[Dict[str, Any]] = field(default_factory=list)
    dropped: List[Tuple[str, str, str]] = field(default_factory=list)  # (id, reason, ilk 60 karakter)
    merges: Dict[str, List[str]] = field(default_factory=dict)         # temsilci -> birleşenler
    category_before: Dict[str, int] = field(default_factory=dict)
    category_after: Dict[str, int] = field(default_factory=dict)

    def counts(self) -> Dict[str, Any]:
        by_reason = Counter(reason for _, reason, _ in self.dropped)
        return {
            "source": self.source,
            "source_nodes": self.source_nodes,
            "dropped_total": len(self.dropped),
            "dropped_by_reason": dict(by_reason),
            "merged_into": len(self.merges),
            "kept": len(self.kept),
            "category_before": self.category_before,
            "category_after": self.category_after,
        }


def _copy_to_temp(source: Path) -> Path:
    """
    Kaynağı geçici bir kopyaya alır.

    Neden: `CognitiveMemorySystem` açılışta idempotent ALTER koşar. Kuru koşum
    bile gerçek dosyanın şemasını değiştirmemeli.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="entropy_migrate_"))
    target = tmp_dir / "source_copy.db"
    shutil.copy2(source, target)
    return target


def _load_rows(db: Path) -> List[Dict[str, Any]]:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, category, content, importance, created_at, last_accessed,"
            " access_count, metadata_json, embedding_json FROM cognitive_nodes"
        ).fetchall()
    out = []
    for row in rows:
        try:
            meta = json.loads(row["metadata_json"] or "{}") or {}
        except ValueError:
            meta = {}
        try:
            emb = json.loads(row["embedding_json"] or "[]") or []
        except ValueError:
            emb = []
        out.append({
            "id": row["id"],
            "category": row["category"] or "",
            "content": row["content"] or "",
            "importance": row["importance"] if row["importance"] is not None else 0.5,
            "created_at": row["created_at"] or time.time(),
            "last_accessed": row["last_accessed"] or time.time(),
            "access_count": row["access_count"] or 1,
            "metadata": meta,
            "embedding": emb,
        })
    return out


def plan_migration(source: Path, merge_threshold: float = MERGE_THRESHOLD) -> MigrationPlan:
    """Kademeli süzme. Hiçbir şey yazmaz; yalnızca planı üretir."""
    plan = MigrationPlan(source=str(source))
    rows = _load_rows(source)
    plan.source_nodes = len(rows)
    plan.category_before = dict(Counter(r["category"] for r in rows))

    survivors: List[Dict[str, Any]] = []
    for row in rows:
        content = (row["content"] or "").strip()
        head = content[:60].replace("\n", " ")
        # 1. fikstür / test kalıbı
        hit = fixture_match(content)
        if hit:
            plan.dropped.append((row["id"], DROP_FIXTURE, head))
            continue
        # 2. çok kısa metin (bilgi taşımıyor)
        if len(content) < MIN_CONTENT_CHARS:
            plan.dropped.append((row["id"], DROP_SHORT, head))
            continue
        # 3. sistemin kendi ürettiği kurgu mimari serisi
        if FAKE_ARCHITECTURE_RE.search(content):
            plan.dropped.append((row["id"], DROP_FAKE_ARCH, head))
            continue
        survivors.append(row)

    # 4. yakın kopyaları birleştir. Temsilci = en yüksek (önem, erişim) düğüm;
    #    diğerleri düşer ama erişim sayıları temsilciye toplanır (bilgi kaybı yok).
    keep_flags = [True] * len(survivors)
    if np is not None and survivors:
        order = sorted(
            range(len(survivors)),
            key=lambda i: (-float(survivors[i]["importance"]), -int(survivors[i]["access_count"])),
        )
        dim = max((len(s["embedding"]) for s in survivors), default=0)
        matrix = np.zeros((len(survivors), dim), dtype=np.float64)
        for i, item in enumerate(survivors):
            vec = item["embedding"]
            if not vec or len(vec) != dim:
                continue
            arr = np.asarray(vec, dtype=np.float64)
            norm = float(np.sqrt(arr @ arr))
            if norm > 0:
                matrix[i] = arr / norm

        taken: List[int] = []
        for i in order:
            if not keep_flags[i]:
                continue
            if taken:
                sims = matrix[taken] @ matrix[i]
                best = int(np.argmax(sims)) if sims.size else -1
                if best >= 0 and float(sims[best]) >= merge_threshold:
                    rep = survivors[taken[best]]
                    keep_flags[i] = False
                    plan.merges.setdefault(rep["id"], []).append(survivors[i]["id"])
                    rep["access_count"] = int(rep["access_count"]) + int(survivors[i]["access_count"])
                    plan.dropped.append(
                        (survivors[i]["id"], DROP_MERGED, survivors[i]["content"][:60].replace("\n", " "))
                    )
                    continue
            taken.append(i)

    for i, item in enumerate(survivors):
        if not keep_flags[i]:
            continue
        resolution = normalize_category(item["category"])
        provenance, _strong = derive_provenance(item["metadata"])
        kept = dict(item)
        kept["new_category"] = resolution.category
        kept["is_identity"] = 1 if resolution.is_identity else 0
        kept["provenance"] = provenance
        if resolution.mapped:
            kept["metadata"].setdefault("legacy_category", item["category"])
        plan.kept.append(kept)

    plan.category_after = dict(Counter(k["new_category"] for k in plan.kept))
    return plan


def write_target(plan: MigrationPlan, target: Path) -> Dict[str, Any]:
    """
    Planı yeni şemalı, BOŞ bir veritabanına yazar ve graf tablolarını kurar.

    Kapı burada kapalı koşar (`ENTROPY_MEMORY_GATE=0`): yineleme elemesi zaten
    planda yapıldı, ikinci kez uygulanması kaynak düğümleri sessizce yutardı.
    Gömmeler kaynaktan **kopyalanır**, yeniden üretilmez (1.544 düğüm x ~90 ms
    tasarruf).
    """
    if target.exists():
        target.unlink()
    previous = os.environ.get("ENTROPY_MEMORY_GATE")
    os.environ["ENTROPY_MEMORY_GATE"] = "0"
    try:
        mem = CognitiveMemorySystem(db_path=target)
        for item in plan.kept:
            node = CognitiveMemoryNode(
                id=mem._generate_node_id(item["new_category"], item["content"]),
                category=item["new_category"],
                content=item["content"],
                importance=float(item["importance"]),
                created_at=float(item["created_at"]),
                last_accessed=float(item["last_accessed"]),
                access_count=int(item["access_count"]),
                metadata=item["metadata"],
                embedding=item["embedding"] or None,
                provenance=item["provenance"],
                confidence=0.75 if item["provenance"] else 0.40,
                valid_from=float(item["created_at"]),
                novelty=1.0,
                is_identity=int(item["is_identity"]),
            )
            mem._save_node(node)
        store = mem.graph_store()
        graph_stats: Dict[str, Any] = {}
        if store is not None:
            graph_stats = {
                "synced": store.sync_from_cognitive(),
                "nodes": store.node_count(),
                "edges": store.edge_count(),
            }
            try:
                store.consolidate()
                graph_stats["communities"] = len(store.list_communities())
            except Exception as exc:
                graph_stats["consolidate_error"] = str(exc)
    finally:
        if previous is None:
            os.environ.pop("ENTROPY_MEMORY_GATE", None)
        else:
            os.environ["ENTROPY_MEMORY_GATE"] = previous
    return {"written": len(plan.kept), "graph": graph_stats}


def backup(source: Path) -> Path:
    stamp = time.strftime("%Y%m%d%H%M%S")
    folder = Path.home() / ".entropy" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"cognitive_memory.pre-v2.{stamp}.db"
    shutil.copy2(source, dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="Bilişsel bellek göçü (Brain v2)")
    ap.add_argument("--source", default=str(default_cognitive_db_path()))
    ap.add_argument("--target", default="", help="hedef dosya (varsayılan: kaynağın yerine)")
    ap.add_argument("--apply", action="store_true", help="gerçekten yaz (varsayılan kuru koşum)")
    ap.add_argument("--merge-threshold", type=float, default=MERGE_THRESHOLD)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"Kaynak veritabanı yok: {source}")
        return 2

    working_copy = _copy_to_temp(source)
    plan = plan_migration(working_copy, merge_threshold=args.merge_threshold)
    report = plan.counts()
    report["source"] = str(source)
    report["mode"] = "apply" if args.apply else "dry-run"

    if args.apply:
        report["backup"] = str(backup(source))
        target = Path(args.target) if args.target else source
        staged = working_copy.parent / "brain_v2.db"
        report.update(write_target(plan, staged))
        shutil.copy2(staged, target)
        report["target"] = str(target)
    else:
        report["note"] = "kuru koşum: hiçbir dosya değiştirilmedi"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"Kaynak    : {report['source']}  ({report['source_nodes']} düğüm)")
    print(f"Kip       : {report['mode']}")
    print(f"Atılan    : {report['dropped_total']}  {report['dropped_by_reason']}")
    print(f"Birleşen  : {report['merged_into']} temsilci altında")
    print(f"Kalan     : {report['kept']}")
    print(f"Kategori  : {report['category_before']}  ->  {report['category_after']}")
    if args.apply:
        print(f"Yedek     : {report['backup']}")
        print(f"Hedef     : {report['target']}  · graf: {report.get('graph')}")
    else:
        print("Not       : kuru koşum, hiçbir dosya değiştirilmedi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
