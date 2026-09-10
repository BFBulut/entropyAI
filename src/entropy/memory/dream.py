"""
Rüya döngüsü v2 — gece konsolidasyonu (Faz 11.7).

Neden
-----
Eski `CognitiveMemorySystem.dream_and_consolidate` yalnızca "son 48 saatte en az
2 epizodik düğüm varsa" iş yapıyordu. Denetimde ölçüldü: epizodik düğüm sayısı
13 (toplamın %0,8'i), yani döngü pratikte hiç çalışmıyordu ve konsolidasyon
(kopya birleştirme, unutma, wiki yükseltme) hiçbir zaman tetiklenmiyordu.
v2'de **epizodik-48s koşulu kalkar**: döngü korpusun tamamı üzerinde çalışır.

Adımlar (sıra bağımlıdır)
-------------------------
1. **Yeniden gömme** — bayat/`pending` vektörler tazelenir (model çağrısı yok).
2. **Gri bant birleştirme turu** — `gray_merge.run_merge_round`; köprü verilmezse
   kuru koşum (kuyruk boşaltılmaz).
3. **Kopya birleştirme** — cos ≥ 0,95 kümeleme, LLM'siz. Konsolidasyon eşiği
   yazma eşiğinden (0,80/0,95 bantları) yüksektir: yazarken öncelik kopya
   engellemek, konsolidasyonda öncelik ayrı bilgiyi korumaktır (Hindsight).
4. **Ölçülü unutma** — düşük önem **ve** hiç geri çağrılmamış **ve** 30 gün
   dokunulmamış düğümler `archived=1`. **Silme yok**; kimlik düğümleri muaf.
5. **Wiki yükseltme** — aynı konuda ≥ 3 anlamsal düğüm varsa kavram sayfası
   **adayı** üretilir (sayfayı yazan `wiki.compile_skill`; burada yalnızca aday
   listesi çıkar, kota harcanmaz).
6. **Graf konsolidasyonu** + **depo uzlaştırma** — mevcut LLM'siz adımlar.

Her adım bir sayaç döndürür; kısmi başarısızlıklar `DreamReport.errors`'a girer
ve döngü devam eder. Sonuç `Entropy/Memory/dream_log.md` dosyasına tek satır
olarak yazılır.

Kota: adım 2 dışında **hiçbir adım model çağırmaz**. Adım 2 en fazla 1 tur.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Kopya birleştirme eşiği (konsolidasyon). Yazma kapısının NOOP eşiğiyle aynı
# sayı ama farklı iş: kapı yazmayı engeller, burası yazılmış olanı toplar.
CONSOLIDATION_THRESHOLD = 0.95
# Wiki yükseltme kümeleme eşiği: daha gevşek, çünkü "aynı konu" aranıyor,
# "aynı cümle" değil.
WIKI_TOPIC_THRESHOLD = 0.75
WIKI_TOPIC_MIN_MEMBERS = 3
# Bir gecede en fazla kaç wiki adayı raporlanır (günlük satırı okunabilir kalsın).
WIKI_CANDIDATE_LIMIT = 20

# Ölçülü unutma eşikleri (rate–distortion görüşü: atmak değil, indeksten düşürmek).
FORGET_MAX_IMPORTANCE = 0.35
FORGET_MAX_ACCESS = 1
FORGET_MIN_AGE_DAYS = 30.0

# Bir turda yeniden gömülecek azami düğüm.
REEMBED_BATCH = 200

DAILY_DREAM_TASK_ID = "daily-dreaming"

DREAM_LOG_SUBPATH = "Entropy/Memory/dream_log.md"
WIKI_CANDIDATES_SUBPATH = "Entropy/Memory/wiki_candidates.md"


@dataclass
class DreamReport:
    """Her adımın sayacı. Ölç, iddia etme."""

    reembedded: int = 0
    gray_candidates: int = 0
    gray_merged: int = 0
    gray_kept: int = 0
    gray_superseded: int = 0
    gray_turns: int = 0
    duplicate_clusters: int = 0
    duplicates_merged: int = 0
    forgotten: int = 0
    wiki_candidates: List[str] = field(default_factory=list)
    graph_communities: int = 0
    reconciled: Dict[str, Any] = field(default_factory=dict)
    nodes_before: int = 0
    nodes_active_after: int = 0
    duration_s: float = 0.0
    errors: List[Dict[str, str]] = field(default_factory=list)
    log_path: Optional[str] = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> Dict[str, Any]:
        return {
            "reembedded": self.reembedded,
            "gray": {
                "candidates": self.gray_candidates, "turns": self.gray_turns,
                "merged": self.gray_merged, "kept": self.gray_kept,
                "superseded": self.gray_superseded,
            },
            "duplicate_clusters": self.duplicate_clusters,
            "duplicates_merged": self.duplicates_merged,
            "forgotten": self.forgotten,
            "wiki_candidates": list(self.wiki_candidates),
            "graph_communities": self.graph_communities,
            "reconciled": dict(self.reconciled),
            "nodes_before": self.nodes_before,
            "nodes_active_after": self.nodes_active_after,
            "duration_s": round(self.duration_s, 3),
            "errors": list(self.errors),
        }

    def summary_line(self) -> str:
        return (
            f"yeniden gömme {self.reembedded} · gri bant {self.gray_merged}m/"
            f"{self.gray_kept}k/{self.gray_superseded}s ({self.gray_candidates} aday, "
            f"{self.gray_turns} tur) · kopya {self.duplicates_merged} "
            f"({self.duplicate_clusters} küme) · unutma {self.forgotten} · "
            f"wiki adayı {len(self.wiki_candidates)} · topluluk {self.graph_communities} · "
            f"düğüm {self.nodes_before}→{self.nodes_active_after} · "
            f"{self.duration_s:.1f} sn · hata {len(self.errors)}"
        )


def _err(report: DreamReport, step: str, exc: Exception) -> None:
    report.errors.append({"step": step, "error": f"{type(exc).__name__}: {exc}"})
    logger.warning("Rüya adımı başarısız (%s): %s", step, exc)


# -- adım 3/5: kümeleme (LLM'siz) -----------------------------------------


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return max(0.0, min(1.0, num / (na * nb)))


def cluster_nodes(nodes: List[Any], threshold: float) -> List[List[Any]]:
    """
    Açgözlü kümeleme: temsilci = en yüksek (önem, erişim) olan düğüm.

    Union-find yerine açgözlü seçim: temsilcinin korpusta *kalacak* düğüm
    olması gerekiyor, dolayısıyla küme merkezini içerik değil değer belirler.
    Yalnızca gömmesi olan düğümler kümelenir.
    """
    candidates = [n for n in nodes if getattr(n, "embedding", None)]
    # Farklı boyutlu vektörler karşılaştırılamaz (model değişimi, hash yedeği,
    # test fikstürü). Boyuta göre kovalanır; her kova kendi içinde kümelenir.
    buckets: Dict[int, List[Any]] = {}
    for node in candidates:
        buckets.setdefault(len(node.embedding), []).append(node)
    if len(buckets) > 1:
        out: List[List[Any]] = []
        for group in buckets.values():
            out.extend(cluster_nodes(group, threshold))
        return out
    pool = candidates
    pool.sort(key=lambda n: (float(n.importance or 0.0), int(n.access_count or 0)), reverse=True)
    used: set = set()
    clusters: List[List[Any]] = []
    try:
        import numpy as np
    except Exception:  # pragma: no cover - numpy yoksa skaler yol
        np = None

    if np is not None and pool:
        matrix = np.asarray([n.embedding for n in pool], dtype=np.float64)
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0.0] = 1.0
        matrix = matrix / norms[:, None]
        sims = matrix @ matrix.T
        for i, node in enumerate(pool):
            if node.id in used:
                continue
            members = [node]
            used.add(node.id)
            for j in range(i + 1, len(pool)):
                other = pool[j]
                if other.id in used:
                    continue
                if float(sims[i, j]) >= threshold:
                    members.append(other)
                    used.add(other.id)
            if len(members) > 1:
                clusters.append(members)
        return clusters

    for i, node in enumerate(pool):  # pragma: no cover - numpy'siz yedek yol
        if node.id in used:
            continue
        members = [node]
        used.add(node.id)
        for other in pool[i + 1:]:
            if other.id in used:
                continue
            if _cosine(node.embedding, other.embedding) >= threshold:
                members.append(other)
                used.add(other.id)
        if len(members) > 1:
            clusters.append(members)
    return clusters


def _active_nodes(memory: Any) -> List[Any]:
    return [n for n in memory.get_all_nodes() if not int(getattr(n, "archived", 0) or 0)]


def merge_duplicates(memory: Any, nodes: Optional[List[Any]] = None,
                     threshold: float = CONSOLIDATION_THRESHOLD,
                     graph: Any = None) -> Tuple[int, int]:
    """
    cos ≥ `threshold` kümelerini tek temsilciye indirir. **Model çağırmaz.**

    Döner: `(küme_sayısı, arşivlenen_düğüm_sayısı)`. Arşivleme `_supersede_node`
    ile yapılır: gövde ve kaynak yerinde kalır, yalnızca indeksten düşer.
    """
    pool = nodes if nodes is not None else _active_nodes(memory)
    clusters = cluster_nodes(pool, threshold)
    archived = 0
    now = time.time()
    for members in clusters:
        rep = members[0]
        for other in members[1:]:
            try:
                memory._supersede_node(other.id, rep.id, now)
                archived += 1
                if graph is not None:
                    try:
                        graph.add_edge(rep.id, other.id, "supersedes", weight=1.0,
                                       provenance=f"dream_merge:{time.strftime('%Y-%m-%d')}")
                    except Exception:  # pragma: no cover - graf zorunlu değil
                        pass
            except Exception as exc:  # pragma: no cover - savunma
                logger.warning("Kopya arşivlenemedi (%s): %s", other.id, exc)
    return len(clusters), archived


# -- adım 4: ölçülü unutma -------------------------------------------------


def forget_stale(memory: Any,
                 max_importance: float = FORGET_MAX_IMPORTANCE,
                 max_access: int = FORGET_MAX_ACCESS,
                 min_age_days: float = FORGET_MIN_AGE_DAYS) -> int:
    """
    Düşük değerli, hiç geri çağrılmamış, eski düğümleri **arşivler** (silmez).

    Kimlik/kural düğümleri (`is_identity=1`) muaftır; kullanıcı onaylı kural
    kullanılmadı diye unutulamaz.
    """
    cutoff = time.time() - min_age_days * 86400.0
    try:
        with sqlite3.connect(memory.db_path) as conn:
            cur = conn.execute(
                "UPDATE cognitive_nodes SET archived = 1"
                " WHERE COALESCE(archived, 0) = 0"
                " AND COALESCE(is_identity, 0) = 0"
                " AND importance < ?"
                " AND COALESCE(access_count, 0) <= ?"
                " AND COALESCE(last_accessed, created_at) <= ?",
                (float(max_importance), int(max_access), cutoff),
            )
            conn.commit()
            count = int(cur.rowcount or 0)
    except sqlite3.Error as exc:
        logger.warning("Ölçülü unutma başarısız: %s", exc)
        return 0
    if count:
        try:
            memory._invalidate_recall_index()
        except Exception:  # pragma: no cover
            pass
    return count


# -- adım 5: wiki yükseltme adayları --------------------------------------


def wiki_promotion_candidates(memory: Any, nodes: Optional[List[Any]] = None,
                              threshold: float = WIKI_TOPIC_THRESHOLD,
                              min_members: int = WIKI_TOPIC_MIN_MEMBERS,
                              limit: int = WIKI_CANDIDATE_LIMIT) -> List[Dict[str, Any]]:
    """
    Aynı konuda ≥ `min_members` anlamsal düğüm varsa kavram sayfası adayı çıkarır.

    Sayfayı BURASI YAZMAZ: yazmak `wiki.compile_skill`in işidir ve kota
    harcayabilir. Rüya döngüsü yalnızca "hangi konu sayfayı hak ediyor"
    sorusunu LLM'siz yanıtlar.
    """
    pool = [n for n in (nodes if nodes is not None else _active_nodes(memory))
            if (n.category or "") == "semantic"]
    out: List[Dict[str, Any]] = []
    for members in cluster_nodes(pool, threshold):
        if len(members) < min_members:
            continue
        rep = members[0]
        title = " ".join((rep.content or "").split())[:90]
        skills = sorted({
            str((m.metadata or {}).get("skill") or "")
            for m in members if (m.metadata or {}).get("skill")
        })
        out.append({
            "title": title,
            "members": len(members),
            "node_ids": [m.id for m in members[:10]],
            "skills": skills,
        })
    out.sort(key=lambda d: d["members"], reverse=True)
    return out[:limit]


# -- günlük ---------------------------------------------------------------


def dream_log_path(vault_path: Optional[Path] = None) -> Path:
    from entropy.core.paths import vault_root

    return vault_root(vault_path) / DREAM_LOG_SUBPATH


def wiki_candidates_path(vault_path: Optional[Path] = None) -> Path:
    from entropy.core.paths import vault_root

    return vault_root(vault_path) / WIKI_CANDIDATES_SUBPATH


def append_dream_log(report: DreamReport, vault_path: Optional[Path] = None) -> Optional[Path]:
    """Kasaya tek satırlık rüya kaydı (insan arayüzü; soğuk depo)."""
    try:
        path = dream_log_path(vault_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# Rüya Döngüsü Günlüğü\n\n", encoding="utf-8")
        stamp = time.strftime("%Y-%m-%d %H:%M")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"- **{stamp}** — {report.summary_line()}\n")
        return path
    except OSError as exc:
        logger.warning("Rüya günlüğü yazılamadı: %s", exc)
        return None


def write_wiki_candidates(candidates: List[Dict[str, Any]],
                          vault_path: Optional[Path] = None) -> Optional[Path]:
    """Wiki adaylarını kasaya yazar (türetilmiş dosya; her gece yeniden üretilir)."""
    if not candidates:
        return None
    try:
        path = wiki_candidates_path(vault_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Wiki Kavram Sayfası Adayları", "",
                 f"_Üretim: {time.strftime('%Y-%m-%d %H:%M')} · rüya döngüsü, model çağrısı yok._", ""]
        for c in candidates:
            skills = f" · yetenek: {', '.join(c['skills'])}" if c.get("skills") else ""
            lines.append(f"- **{c['members']} düğüm**{skills} — {c['title']}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    except OSError as exc:  # pragma: no cover
        logger.warning("Wiki aday listesi yazılamadı: %s", exc)
        return None


# -- ana döngü -------------------------------------------------------------


def dream_and_consolidate(
    memory: Any = None,
    send_prompt: Optional[Callable[[str], str]] = None,
    vault_path: Optional[Path] = None,
    merge_duplicates_enabled: bool = True,
    forget_enabled: bool = True,
    write_log: bool = True,
) -> DreamReport:
    """
    Rüya döngüsü v2. Epizodik koşul YOKTUR; korpusun tamamında çalışır.

    `send_prompt` verilmezse adım 2 (gri bant) kuru koşuma düşer ve **hiçbir
    model çağrılmaz**; geri kalan altı adım her hâlükârda LLM'sizdir.
    """
    started = time.time()
    if memory is None:
        from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

        memory = CognitiveMemorySystem()
    report = DreamReport()

    try:
        report.nodes_before = len(memory.get_all_nodes())
    except Exception as exc:
        _err(report, "sayim", exc)

    # 1. yeniden gömme
    try:
        res = memory.reembed_stale(batch_limit=REEMBED_BATCH) or {}
        report.reembedded = int(res.get("updated", res.get("reembedded", 0)) or 0)
    except Exception as exc:
        _err(report, "reembed", exc)

    graph = None
    try:
        from entropy.memory.graph_store import GraphStore

        graph = GraphStore(memory=memory)
    except Exception as exc:  # pragma: no cover - graf katmanı zorunlu değil
        _err(report, "graph_store", exc)

    # 2. gri bant birleştirme turu
    try:
        from entropy.memory import gray_merge

        merge_res = gray_merge.run_merge_round(memory, send_prompt=send_prompt, graph=graph)
        report.gray_candidates = merge_res.candidates
        report.gray_turns = merge_res.turns
        report.gray_merged = merge_res.merged
        report.gray_kept = merge_res.kept
        report.gray_superseded = merge_res.superseded
        for e in merge_res.errors:
            if "kuru koşum" not in e:
                report.errors.append({"step": "gray_merge", "error": e})
    except Exception as exc:
        _err(report, "gray_merge", exc)

    # 3. kopya birleştirme (LLM'siz)
    nodes: List[Any] = []
    try:
        nodes = _active_nodes(memory)
    except Exception as exc:
        _err(report, "node_read", exc)
    if merge_duplicates_enabled and nodes:
        try:
            clusters, merged = merge_duplicates(memory, nodes, graph=graph)
            report.duplicate_clusters = clusters
            report.duplicates_merged = merged
        except Exception as exc:
            _err(report, "merge_duplicates", exc)

    # 4. ölçülü unutma
    if forget_enabled:
        try:
            report.forgotten = forget_stale(memory)
        except Exception as exc:
            _err(report, "forget", exc)

    # 5. wiki yükseltme adayları
    try:
        fresh = _active_nodes(memory)
        cands = wiki_promotion_candidates(memory, fresh)
        report.wiki_candidates = [c["title"] for c in cands]
        if write_log:
            write_wiki_candidates(cands, vault_path=vault_path)
    except Exception as exc:
        _err(report, "wiki_promote", exc)

    # 6. graf konsolidasyonu + ofis akışı + depo uzlaştırma
    if graph is not None:
        try:
            out = graph.consolidate()
            if isinstance(out, dict):
                report.graph_communities = int(out.get("communities", 0) or 0)
        except Exception as exc:
            _err(report, "graph_consolidate", exc)
        try:
            from entropy.memory.office_graph import schedule_office_ingest

            schedule_office_ingest(store=graph, background=False)
        except Exception as exc:
            _err(report, "office_ingest", exc)
    try:
        report.reconciled = memory.reconcile_stores() or {}
    except Exception as exc:
        _err(report, "reconcile", exc)

    try:
        report.nodes_active_after = len(_active_nodes(memory))
    except Exception as exc:  # pragma: no cover
        _err(report, "sayim_son", exc)

    report.duration_s = time.time() - started
    if write_log:
        path = append_dream_log(report, vault_path=vault_path)
        report.log_path = str(path) if path else None
    logger.info("Rüya döngüsü: %s", report.summary_line())
    return report


# -- zamanlanmış görev -----------------------------------------------------


def ensure_daily_dreaming_task(scheduler: Any = None, hour: int = 4) -> Optional[Any]:
    """
    `daily-dreaming` görevini **idempotent** kaydeder (varsa yeniden yazmaz).

    Görevi bu modül *çalıştırmaz*: kayıt yapar, tetikleme zamanlayıcının ve
    kullanıcı komutunun işidir (AGY kotası harcayan hiçbir şey kendiliğinden
    başlatılmaz — `send_prompt` verilmediği sürece döngü zaten kotasızdır).
    """
    if scheduler is None:
        try:
            from entropy.scheduler.cron_engine import TaskScheduler

            scheduler = TaskScheduler.get_instance()
        except Exception as exc:  # pragma: no cover - zamanlayıcı yoksa sessiz
            logger.warning("Zamanlayıcı bulunamadı: %s", exc)
            return None
    try:
        existing = getattr(scheduler, "tasks", {}) or {}
        if DAILY_DREAM_TASK_ID in existing:
            return existing[DAILY_DREAM_TASK_ID]
        return scheduler.schedule_task(
            task_id=DAILY_DREAM_TASK_ID,
            name="Gece Konsolidasyonu (Rüya Döngüsü)",
            prompt="[SISTEM] memory.dream.dream_and_consolidate",
            interval_type="daily",
            interval_value=int(hour),
            task_type="analiz",
        )
    except Exception as exc:  # pragma: no cover - savunma
        logger.warning("daily-dreaming kaydedilemedi: %s", exc)
        return None


__all__ = [
    "CONSOLIDATION_THRESHOLD", "DAILY_DREAM_TASK_ID", "DreamReport",
    "append_dream_log", "cluster_nodes", "dream_and_consolidate",
    "dream_log_path", "ensure_daily_dreaming_task", "forget_stale",
    "merge_duplicates", "wiki_promotion_candidates",
]
