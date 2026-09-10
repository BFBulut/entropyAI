"""
Gri bant kuyruğu birleştirme turu (Faz 11.3).

Neden
-----
`MemoryGate` üç bant kullanır: `cos ≥ 0,95` kopya (NOOP), `cos < 0,80` yeni
(ADD), arası **gri bant**. Gri bantta düğüm yazılır **ve** `gray_queue.jsonl`
kuyruğuna aday olarak girer; karar ertelenir. Kuyruğu boşaltan bir tur
olmadan kuyruk sonsuza dek büyür ve yazma kapısı yalnızca yarım iş yapar.

Ne yapıyor
----------
`pending_gray()` adaylarını toplar, **N adayı tek istemde** (aday + en yakın
komşu çiftleri) köprüye verir — `distiller.run_with_bridge` deseni: modül
köprüye değil, `send_prompt(prompt) -> str` çağrılabilirine bağlıdır, böylece
Qt'siz ve gerçek model çağrısı olmadan test edilebilir. Yanıt JSON'dur; her
çift için `merge | keep_both | supersede`.

Karar uygulaması (LLM yalnızca kararı verir, yazmayı bu modül yapar):

* **merge**      — kalan düğüm (varsayılan: komşu) içeriği birleşik metinle
                   güncellenir, aday `archived=1` olur, grafta
                   `supersedes` kenarı (kalan → arşivlenen) açılır.
* **supersede**  — aday komşuyu geçersizleştirir (yönü ters merge).
* **keep_both**  — hiçbir şey yazılmaz; iki düğüm de kalır.

Her durumda kuyruk satırı `status: "done"` olur; tur idempotenttir (aynı aday
ikinci turda görünmez). İptal edilebilir: `cancel_merge()` süren turu keser,
uygulanmamış kararlar kuyrukta `pending` kalır.

Kota: **tur başına bir CLI çağrısı** (N aday tek istemde). K9 ölçütü
("yazma başına CLI turu ≤ %2") `gray_stats()` ile ölçülür.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Tek istemde sorulacak azami çift sayısı. 8 çift ≈ 4-5 bin karakterlik istem;
# daha fazlası modelin kararlarını karıştırıyor ve yanıtı kesilme riskine sokar.
DEFAULT_BATCH = 8

# İsteme konan gövde uzunlukları: aday ve komşu için ayrı ayrı.
CANDIDATE_CHARS = 700
NEIGHBOUR_CHARS = 700

ACTION_MERGE = "merge"
ACTION_KEEP_BOTH = "keep_both"
ACTION_SUPERSEDE = "supersede"
VALID_ACTIONS = (ACTION_MERGE, ACTION_KEEP_BOTH, ACTION_SUPERSEDE)

MERGE_LOG_FILENAME = "gray_merge_log.jsonl"

# İptal bayrağı süreç genelinde tekil: kullanıcı "durdur" dediğinde süren tur
# bir sonraki adayda kesilir (damıtmadaki `_CANCELLED` deseni).
_CANCELLED = threading.Event()


def cancel_merge() -> None:
    """Süren birleştirme turunu keser (uygulanmamış adaylar kuyrukta kalır)."""
    _CANCELLED.set()


def reset_cancel() -> None:
    """İptal bayrağını temizler; her yeni tur başlarken çağrılır."""
    _CANCELLED.clear()


def is_cancelled() -> bool:
    return _CANCELLED.is_set()


@dataclass
class GrayCandidate:
    """Kuyruktaki tek bir gri bant satırının okunmuş hâli."""

    node_id: str
    category: str = ""
    content: str = ""
    similarity: float = 0.0
    nearest_id: str = ""
    nearest_content: str = ""
    provenance: str = ""
    reason: str = ""

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "GrayCandidate":
        return cls(
            node_id=str(row.get("node_id") or ""),
            category=str(row.get("category") or ""),
            content=str(row.get("content") or ""),
            similarity=float(row.get("similarity") or 0.0),
            nearest_id=str(row.get("nearest_id") or ""),
            nearest_content=str(row.get("nearest_content") or ""),
            provenance=str(row.get("provenance") or ""),
            reason=str(row.get("reason") or ""),
        )


@dataclass
class MergeResult:
    """Bir turun sonucu. Sayılar rapor edilir; iddia edilmez, ölçülür."""

    candidates: int = 0
    turns: int = 0
    merged: int = 0
    kept: int = 0
    superseded: int = 0
    skipped: int = 0
    cancelled: bool = False
    errors: List[str] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    queue_path: Optional[str] = None
    prompt: str = ""

    @property
    def applied(self) -> int:
        return self.merged + self.superseded

    def as_dict(self) -> Dict[str, Any]:
        return {
            "candidates": self.candidates,
            "turns": self.turns,
            "merged": self.merged,
            "kept": self.kept,
            "superseded": self.superseded,
            "skipped": self.skipped,
            "cancelled": self.cancelled,
            "errors": list(self.errors),
        }


# -- kuyruk yardımcıları ---------------------------------------------------


def _gate(memory: Any, gate: Any = None) -> Any:
    return gate if gate is not None else memory.gate


def pending_candidates(memory: Any, gate: Any = None, limit: int = DEFAULT_BATCH) -> List[GrayCandidate]:
    """Kuyruktaki bekleyen adaylar (en fazla `limit` tane, en eskiden yeniye)."""
    rows = _gate(memory, gate).pending_gray()
    out: List[GrayCandidate] = []
    for row in rows:
        cand = GrayCandidate.from_row(row)
        if not cand.node_id:
            continue
        out.append(cand)
        if limit and len(out) >= limit:
            break
    return out


def mark_done(memory: Any, node_ids: List[str], gate: Any = None,
              actions: Optional[Dict[str, str]] = None) -> int:
    """
    Kuyruk satırlarını `status: "done"` yapar (satır silinmez, iz kalır).

    Dosya yerinde yeniden yazılır; kuyruk yalnızca ekleme yapılan bir JSONL
    olduğu için tur sırasında yeni satır gelirse o satır korunur (okuma ve
    yazma arası pencere kabul edilebilir: en kötü hâlde aday bir tur sonra
    işlenir).
    """
    ids = {i for i in node_ids if i}
    if not ids:
        return 0
    path: Path = _gate(memory, gate).queue_path
    if not path.exists():
        return 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Gri bant kuyruğu okunamadı: %s", exc)
        return 0
    changed = 0
    out: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            out.append(stripped)
            continue
        if row.get("node_id") in ids and row.get("status", "pending") == "pending":
            row["status"] = "done"
            row["resolved_at"] = time.time()
            if actions:
                row["resolution"] = actions.get(row.get("node_id"), "")
            changed += 1
        out.append(json.dumps(row, ensure_ascii=False))
    if changed:
        try:
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Gri bant kuyruğu yazılamadı: %s", exc)
            return 0
    return changed


def gray_stats(memory: Any, gate: Any = None) -> Dict[str, Any]:
    """
    K9 ölçümü: **yazma başına CLI turu**.

    `ratio` = gri bant satırı / toplam düğüm. Gri bant tek CLI turu tetikleyen
    tek banttır (ADD ve NOOP model çağırmaz), dolayısıyla bu oran K9'un
    doğrudan karşılığıdır (hedef ≤ %2).
    """
    g = _gate(memory, gate)
    path: Path = g.queue_path
    pending = done = total = 0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            if row.get("status", "pending") == "pending":
                pending += 1
            else:
                done += 1
    try:
        nodes = len(memory.get_all_nodes())
    except Exception:  # pragma: no cover - savunma
        nodes = 0
    return {
        "pending": pending,
        "done": done,
        "total_gray": total,
        "nodes": nodes,
        "ratio": (total / nodes) if nodes else 0.0,
        "queue_path": str(path),
    }


# -- istem ve ayrıştırma ---------------------------------------------------


def build_merge_prompt(candidates: List[GrayCandidate]) -> str:
    """N adayı tek isteme koyar. Model YALNIZCA karar verir, metni o yazmaz."""
    head = (
        "[GÖREV: HAFIZA GRİ BANT BİRLEŞTİRME]\n\n"
        "Aşağıda hafızaya yeni yazılmış AY düğümleri ve her birinin en yakın "
        "MEVCUT komşusu var. Benzerlikleri kopya saymaya yetmiyor, ayrı bilgi "
        "saymaya da yetmiyor. Her çift için tek bir karar ver:\n\n"
        "- \"merge\"      : ikisi AYNI bilgiyi anlatıyor; tek düğümde birleşmeli.\n"
        "- \"keep_both\"  : ikisi FARKLI bilgi taşıyor; ikisi de kalmalı.\n"
        "- \"supersede\"  : aday, komşunun bilgisini GÜNCELLİYOR (aynı konu, yeni değer);\n"
        "                 komşu geçersizleşmeli.\n\n"
        "\"merge\" seçtiysen `content` alanına iki metnin bilgi kaybı olmayan "
        "birleşik hâlini yaz (en fazla 900 karakter, düz metin). Diğer "
        "kararlarda `content` boş bırak.\n\n"
        "YALNIZCA şu biçimde JSON döndür, başka hiçbir şey yazma:\n"
        '{"decisions": [{"id": "<aday_id>", "action": "merge|keep_both|supersede", '
        '"content": "", "reason": "<tek cümle>"}]}\n\n'
    )
    blocks: List[str] = []
    for i, c in enumerate(candidates, 1):
        blocks.append(
            f"### ÇİFT {i}\n"
            f"aday_id: {c.node_id}\n"
            f"benzerlik: {c.similarity:.3f}\n"
            f"ADAY ({c.category}):\n{(c.content or '').strip()[:CANDIDATE_CHARS]}\n\n"
            f"KOMŞU ({c.nearest_id or 'yok'}):\n{(c.nearest_content or '').strip()[:NEIGHBOUR_CHARS]}"
        )
    return head + "\n\n".join(blocks) + "\n"


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_merge_response(text: str) -> Dict[str, Dict[str, str]]:
    """
    Köprü yanıtını `{aday_id: {"action", "content", "reason"}}` sözlüğüne çevirir.

    Model kod bloğu, önsöz ya da sonsöz eklerse ilk kapsayıcı JSON nesnesi
    alınır; hiç geçerli JSON yoksa boş sözlük döner ve tur "atlandı" sayılır
    (kuyruk BOŞALTILMAZ — bilinmeyen karar veri kaybına dönüşmemeli).
    """
    raw = (text or "").strip()
    if not raw:
        return {}
    payload: Any = None
    for candidate in (raw, (_JSON_BLOCK.search(raw).group(0) if _JSON_BLOCK.search(raw) else "")):
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    if payload is None:
        return {}
    items = payload.get("decisions") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return {}
    out: Dict[str, Dict[str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or item.get("node_id") or "").strip()
        action = str(item.get("action") or "").strip().lower()
        if not node_id or action not in VALID_ACTIONS:
            continue
        out[node_id] = {
            "action": action,
            "content": str(item.get("content") or "").strip(),
            "reason": str(item.get("reason") or "").strip(),
        }
    return out


# -- uygulama --------------------------------------------------------------


def _archive(memory: Any, old_id: str, new_id: str) -> bool:
    """Düğümü geçersizleştirir (siler değil): `valid_to` + `archived=1`."""
    fn = getattr(memory, "_supersede_node", None)
    if fn is None:  # pragma: no cover - savunma
        return False
    try:
        fn(old_id, new_id, time.time())
        return True
    except Exception as exc:  # pragma: no cover - savunma
        logger.warning("Düğüm arşivlenemedi (%s): %s", old_id, exc)
        return False


def _update_content(memory: Any, node_id: str, content: str) -> bool:
    """Kalan düğümün gövdesini birleşik metinle günceller (kimlik korunur)."""
    content = (content or "").strip()
    if not content:
        return False
    # Faz 11 kapanışı: doğrudan SQL yerine yazma yolunun kendisi kullanılır.
    # `_save_node(..., allow_content_update=True)` içerik sütununu günceller,
    # gömmeyi 'pending' işaretler ve graf kopyasını da senkronlar — doğrudan
    # SQL bunu yapmıyordu, graf tarafında eski metin kalıyordu.
    try:
        node = memory.get_node(node_id)
        if node is None:
            return False
        node.content = content[:4000]
        node.embedding = []
        memory._save_node(node, allow_content_update=True)
        return True
    except Exception as exc:  # pragma: no cover - savunma
        logger.warning("Birleşik içerik yazılamadı (%s): %s", node_id, exc)
        return False


def _link(graph: Any, src: str, dst: str, provenance: str) -> None:
    """Grafta `supersedes` kenarı açar; graf yoksa sessizce geçilir."""
    if graph is None or not src or not dst:
        return
    try:
        graph.add_edge(src, dst, "supersedes", weight=1.0, provenance=provenance)
    except Exception as exc:  # pragma: no cover - graf katmanı zorunlu değil
        logger.warning("supersedes kenarı açılamadı (%s→%s): %s", src, dst, exc)


def apply_decisions(
    memory: Any,
    candidates: List[GrayCandidate],
    decisions: Dict[str, Dict[str, str]],
    graph: Any = None,
    result: Optional[MergeResult] = None,
) -> MergeResult:
    """Kararları uygular ve kuyruk satırlarını kapatır."""
    res = result or MergeResult()
    resolved: List[str] = []
    actions: Dict[str, str] = {}
    for cand in candidates:
        if is_cancelled():
            res.cancelled = True
            break
        decision = decisions.get(cand.node_id)
        if not decision:
            res.skipped += 1
            continue
        action = decision["action"]
        prov = f"gray_merge:{time.strftime('%Y-%m-%d')}"
        if action == ACTION_KEEP_BOTH:
            res.kept += 1
        elif action == ACTION_MERGE and cand.nearest_id:
            # Kalan düğüm KOMŞU'dur: korpusta daha eskidir, ona bağlı kenarlar
            # ve erişim sayacı korunur. Aday arşivlenir.
            merged_text = decision.get("content") or ""
            if merged_text:
                _update_content(memory, cand.nearest_id, merged_text)
            if _archive(memory, cand.node_id, cand.nearest_id):
                _link(graph, cand.nearest_id, cand.node_id, prov)
                res.merged += 1
            else:  # pragma: no cover - savunma
                res.skipped += 1
                continue
        elif action == ACTION_SUPERSEDE and cand.nearest_id:
            if _archive(memory, cand.nearest_id, cand.node_id):
                _link(graph, cand.node_id, cand.nearest_id, prov)
                res.superseded += 1
            else:  # pragma: no cover - savunma
                res.skipped += 1
                continue
        else:
            # Komşusuz aday: birleştirilecek karşı taraf yok.
            res.kept += 1
        resolved.append(cand.node_id)
        actions[cand.node_id] = action
        res.decisions.append({"id": cand.node_id, "action": action,
                              "reason": decision.get("reason", "")})
    if resolved:
        mark_done(memory, resolved, actions=actions)
    _append_log(memory, res)
    return res


def _append_log(memory: Any, res: MergeResult) -> Optional[Path]:
    """Tur günlüğü veritabanının yanında durur (test yalıtımı bedava)."""
    try:
        path = Path(memory.gate.queue_path).parent / MERGE_LOG_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        row = dict(res.as_dict())
        row["ts"] = time.time()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return path
    except Exception as exc:  # pragma: no cover - günlük tur sonucunu bozmaz
        logger.warning("Birleştirme günlüğü yazılamadı: %s", exc)
        return None


def run_merge_round(
    memory: Any = None,
    send_prompt: Optional[Callable[[str], str]] = None,
    limit: int = DEFAULT_BATCH,
    gate: Any = None,
    graph: Any = None,
) -> MergeResult:
    """
    Tek bir birleştirme turu: kuyruk → tek istem → kararlar → uygulama.

    `send_prompt(prompt) -> str` eşzamanlı çağrılabilirdir (damıtmadaki
    `run_with_bridge` sözleşmesinin aynısı); `None` ise **hiçbir model
    çağrılmaz** ve tur "aday sayısını ölç" kuru koşumuna döner.

    Sağlayıcı seçimi çağıranın işidir (`config.provider`): bu modül köprüyü
    tanımaz, yalnızca gönderici çağrılabiliri kullanır.
    """
    reset_cancel()
    if memory is None:
        from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

        memory = CognitiveMemorySystem()
    res = MergeResult()
    try:
        res.queue_path = str(_gate(memory, gate).queue_path)
    except Exception:  # pragma: no cover
        res.queue_path = None

    candidates = pending_candidates(memory, gate=gate, limit=limit)
    res.candidates = len(candidates)
    if not candidates:
        return res
    res.prompt = build_merge_prompt(candidates)
    if send_prompt is None:
        res.skipped = len(candidates)
        res.errors.append("gönderici yok: kuru koşum, kuyruk boşaltılmadı")
        return res
    if is_cancelled():
        res.cancelled = True
        return res

    try:
        output = send_prompt(res.prompt)
        res.turns = 1
    except Exception as exc:
        res.errors.append(f"köprü hatası: {exc}")
        logger.warning("Gri bant birleştirme turu başarısız: %s", exc)
        return res

    decisions = parse_merge_response(output)
    if not decisions:
        res.errors.append("yanıt ayrıştırılamadı: kuyruk korundu")
        res.skipped = len(candidates)
        return res

    if graph is None:
        try:
            from entropy.memory.graph_store import GraphStore

            graph = GraphStore(memory=memory)
        except Exception as exc:  # pragma: no cover - graf katmanı zorunlu değil
            logger.warning("Graf deposu kurulamadı, kenar açılmayacak: %s", exc)
            graph = None

    return apply_decisions(memory, candidates, decisions, graph=graph, result=res)


__all__ = [
    "ACTION_KEEP_BOTH", "ACTION_MERGE", "ACTION_SUPERSEDE", "DEFAULT_BATCH",
    "GrayCandidate", "MergeResult", "apply_decisions", "build_merge_prompt",
    "cancel_merge", "gray_stats", "is_cancelled", "mark_done",
    "parse_merge_response", "pending_candidates", "reset_cancel", "run_merge_round",
]
