"""
`MemoryGate` — yazma tarafı denetimi (Brain v2, Faz 11.2).

Neden
-----
Denetimde ölçüldü: 1544 düğümün **%55,7'si fazlalık** (cos ≥ 0,90 kümelemesi ile
684 benzersiz konu). Kök neden tek satırdı — düğüm kimliği içeriğin *birebir*
özeti (`_generate_node_id`), dolayısıyla tek bir kelime farkı yeni düğüm açıyordu.
Anlamsal yenilik hiçbir yerde ölçülmüyordu; ayrıca 469 düğüm (%30,4) test
fikstürüydü ve 32 düğüm sistemin kendi ürettiği kurguydu (kaynaksız).

Ne yapıyor
----------
Tek giriş kapısı. `record_memory` (ve dolayısıyla `store_node` ile yedi üretim
çağrı noktasının tamamı) yazmadan önce buradan geçer. **Model çağrısı yok**,
kota harcamaz; SAGE (arXiv:2605.30711) üç bantlı yönlendirme deseninin
LLM'siz çekirdeği:

    1. KATEGORİ      — kapalı küme (categories.py); bilinmeyen değer katı kipte red
    2. AYIKLAMA      — fikstür/test kalıbı, çok kısa metin → RED
    3. KAYNAK        — L2 (semantic) yazımında `provenance` yoksa → RED
    4. YOĞUNLUK      — korpusun en yakın komşusuna kosinüs benzerliği
    5. YÖNLENDİRME   — cos ≥ 0,95 NOOP · cos < 0,80 ADD · arası GRİ BANT
    6. GRİ BANT      — aynı varlık+yüklem farklı değer ise SUPERSEDE (reconcile),
                       değilse düğüm yazılır AMA `gray_queue.jsonl`a aday olarak
                       kuyruklanır; gece toplu CLI birleştirme turu (11.3/11-D)
                       kuyruğu boşaltır. Tur içinde model çağrılmaz.

Geri alma: `ENTROPY_MEMORY_GATE=0` kapıyı tamamen atlar, eski davranışa döner.

Katı kip (`strict`) varsayılan olarak **üretimde açık, pytest altında kapalı**:
fikstür süzgeci ve kaynak zorunluluğu testlerin kendi kısa/kaynaksız
düğümlerini reddetmemeli. Testler katı kipi `MemoryGate(..., strict=True)` ile
açıkça ister.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from entropy.memory.categories import (
    CategoryResolution,
    SEMANTIC,
    WORKING,
    normalize_category,
)
from entropy.memory.reconcile import ExistingFact, extract_facts, reconcile_facts

logger = logging.getLogger(__name__)

# -- bantlar --------------------------------------------------------------
# Hindsight (21 May 2026) ölçümü ve bizim kendi kümelememizle uyumlu: yazma
# anında kopya engellemek önceliklidir, konsolidasyonda ayrı bilgiyi korumak.
# Bu yüzden konsolidasyon eşiği (0,95+) yazma eşiğinden yüksektir.
GATE_NOOP_THRESHOLD = 0.95   # ≥ : kopya, yazma yok
GATE_ADD_THRESHOLD = 0.80    # < : açıkça yeni, doğrudan yaz
# 0,80 ≤ cos < 0,95 → gri bant

# Kapının bu uzunluğun altındaki metinleri yazmaması kural (denetim: 578 düğüm
# fikstür/kısa metin süzgecinde eleniyor).
MIN_CONTENT_CHARS = 40

ACTION_ADD = "add"
ACTION_NOOP = "noop"
ACTION_GRAY = "gray"
ACTION_SUPERSEDE = "supersede"
ACTION_REJECT = "reject"

GRAY_QUEUE_FILENAME = "gray_queue.jsonl"

# Faz 11 kapanışı (K12): v2 öncesinden gelen, kaynağı hiçbir zaman kaydedilmemiş
# L2 düğümleri. Uydurma kaynak yazmak yerine dürüst etiket: "bu düğümün kaynağı
# bilinmiyor, eski şemadan geldi". Kapının kaynak zorunluluğu bu etiketi GÜÇLÜ
# kaynak saymaz (yeni yazımlar hâlâ gerçek kaynak ister); ölçüm paketi ise bu
# düğümleri ayrı sayar ve rüya döngüsünün `forget_stale` adayı olarak bırakır.
LEGACY_PROVENANCE = "legacy:pre-v2"
# Etiketli düğümün güveni: kaynağı doğrulanamıyor, ama içerik hâlâ okunabilir.
LEGACY_CONFIDENCE = 0.40

# Kimlik düğümleri (`is_identity=1`) için DOĞRU kaynak: bu düğümler dış bir
# belgeden değil, Entropy'nin kendi kimlik/otonomi bildiriminden gelir. Uydurma
# değildir; bu yüzden `legacy:pre-v2` yerine kendi etiketini alır ve güveni
# düşürülmez. K12 (kaynaksız L2) sayımı kimlik düğümlerini kapsam dışı bırakır:
# kimlik bir "dış kaynaklı olgu" değil, sistemin aksiyomudur.
IDENTITY_PROVENANCE = "identity:core"

# Üretim hafızasına asla girmemesi gereken kalıplar. Hepsi denetimde gerçek
# düğümlerden çıkarıldı (en büyük küme 322 üyeli tek bir ofis fikstürüydü).
_FIXTURE_PATTERNS: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("pytest", re.compile(r"pytest", re.IGNORECASE)),
    ("dummyproc", re.compile(r"dummy\s*proc", re.IGNORECASE)),
    ("test_prefix", re.compile(r"(?:^|[\s/\\`'\"(])test_[a-z0-9_]+", re.IGNORECASE)),
    ("tmp_pytest_path", re.compile(r"pytest-of-|[\\/]pytest-\d+[\\/]", re.IGNORECASE)),
    # "arastirma-ofisi: Pazar araştırması / Ofis: ... · arastirmaci · review"
    ("office_card_fixture", re.compile(r"Ofis:\s.*·.*\breview\b", re.IGNORECASE | re.DOTALL)),
    ("proof_fixture", re.compile(r"\[KANIT\]\s*Komut:", re.IGNORECASE)),
)

# `provenance` olarak kabul edilen GÜÇLÜ metadata anahtarları: dış bir yola,
# URL'ye ya da dosyaya işaret ederler. "source": "scheduled_task" gibi serbest
# etiketler kaynak sayılmaz — sistemin kendi önceki çıktısı geçerli kaynak
# değildir (Manufactured Confidence, arXiv:2606.29279).
_STRONG_PROVENANCE_KEYS = (
    "path", "filepath", "file_path", "report_path", "source_path",
    "url", "source_url", "filename", "source_file",
)
# Zayıf ama yine de izlenebilir anahtarlar (L1/L3 için yeterli).
_WEAK_PROVENANCE_KEYS = ("task_id", "skill", "skill_name", "office", "project", "source")


def gate_enabled() -> bool:
    """`ENTROPY_MEMORY_GATE=0` kapıyı kapatır (geri alma bayrağı)."""
    return os.environ.get("ENTROPY_MEMORY_GATE", "1").strip() not in ("0", "false", "no")


def default_strict() -> bool:
    """Katı kip: üretimde açık, pytest koşumunda kapalı."""
    override = os.environ.get("ENTROPY_MEMORY_GATE_STRICT", "").strip()
    if override:
        return override not in ("0", "false", "no")
    return "PYTEST_CURRENT_TEST" not in os.environ


def derive_provenance(metadata: Optional[Dict[str, Any]], explicit: str = "") -> Tuple[str, bool]:
    """
    Metadata'dan kaynak dizesini çıkarır.

    Döner: `(provenance, strong)`. `strong` yalnızca dış bir yol/URL/dosya
    varsa True'dur; L2 anlamsal yazımın kabul koşulu budur.
    """
    # Açıkça verilen kaynak her zaman GÜÇLÜ sayılır: çağıran kaynağı bildiğini
    # beyan etmiştir (iç konsolidasyon, göç betiği, wiki derlemesi). "Kendi
    # önceki çıktısı geçerli kaynak değildir" kuralının denetimi araştırma turu
    # kapısına aittir (11.6), yazma kapısına değil.
    if explicit and explicit.strip():
        # Tek istisna: eski düğüm etiketi kaynak yerine geçmez. Yeni yazımlar
        # bu dizeyi vererek L2 kaynak zorunluluğunu atlayamasın (Faz 11 kapanışı).
        return explicit.strip(), explicit.strip() != LEGACY_PROVENANCE
    meta = metadata or {}
    for key in _STRONG_PROVENANCE_KEYS:
        value = meta.get(key)
        if value and str(value).strip():
            return f"{key}={str(value).strip()}", True
    parts: List[str] = []
    for key in _WEAK_PROVENANCE_KEYS:
        value = meta.get(key)
        if value and str(value).strip():
            parts.append(f"{key}={str(value).strip()}")
    return ("; ".join(parts), False)


def fixture_match(content: str) -> Optional[str]:
    """Fikstür/test kalıbı yakalarsa kalıbın adını döndürür."""
    text = content or ""
    for name, pattern in _FIXTURE_PATTERNS:
        if pattern.search(text):
            return name
    return None


@dataclass
class GateDecision:
    """Kapının tek bir aday için kararı. Yazma yolu bunu okur, kendisi karar vermez."""

    action: str
    category: str
    content: str
    importance: float = 0.5
    is_identity: bool = False
    provenance: str = ""
    confidence: float = 0.5
    novelty: float = 1.0
    similarity: float = 0.0
    nearest_id: Optional[str] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    embedding_status: str = ""

    @property
    def writes(self) -> bool:
        """Düğüm diske yazılacak mı (gri bant da yazar; kuyruğa da girer)."""
        return self.action in (ACTION_ADD, ACTION_GRAY, ACTION_SUPERSEDE)

    def as_log(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "category": self.category,
            "similarity": round(self.similarity, 4),
            "novelty": round(self.novelty, 4),
            "nearest_id": self.nearest_id,
            "reason": self.reason,
        }


class MemoryGate:
    """Yazma kapısı. Bir `CognitiveMemorySystem` örneğine bağlıdır."""

    def __init__(
        self,
        memory: Any,
        strict: Optional[bool] = None,
        queue_path: Optional[Path] = None,
        noop_threshold: float = GATE_NOOP_THRESHOLD,
        add_threshold: float = GATE_ADD_THRESHOLD,
    ) -> None:
        self.memory = memory
        self.strict = default_strict() if strict is None else bool(strict)
        self.noop_threshold = noop_threshold
        self.add_threshold = add_threshold
        self._queue_path = Path(queue_path) if queue_path else None
        # Sayaçlar: bellek panosu (11.12) ve ölçüm paketi (11.13) buradan okur.
        self.counters: Dict[str, int] = {
            ACTION_ADD: 0, ACTION_NOOP: 0, ACTION_GRAY: 0,
            ACTION_SUPERSEDE: 0, ACTION_REJECT: 0,
        }

    # -- kuyruk ------------------------------------------------------------

    @property
    def queue_path(self) -> Path:
        """Gri bant kuyruğu; veritabanının yanında durur (test yalıtımı bedava)."""
        if self._queue_path is None:
            base = Path(getattr(self.memory, "db_path", Path.home() / ".entropy" / "x.db")).parent
            self._queue_path = base / "memory" / GRAY_QUEUE_FILENAME
        return self._queue_path

    def enqueue_gray(self, decision: GateDecision, node_id: str = "") -> Optional[Path]:
        """
        Gri bant adayını JSONL kuyruğuna ekler.

        Biçim (satır başına bir JSON nesnesi) — 11.3'ün toplu CLI turu ve
        bellek panosu bu sözleşmeye göre okur:

            {"ts": float, "status": "pending", "node_id": str, "category": str,
             "content": str, "similarity": float, "nearest_id": str,
             "nearest_content": str, "provenance": str, "reason": str}
        """
        try:
            path = self.queue_path
            path.parent.mkdir(parents=True, exist_ok=True)
            nearest_content = ""
            if decision.nearest_id:
                node = self.memory.get_node(decision.nearest_id)
                nearest_content = (node.content if node else "")[:600]
            row = {
                "ts": time.time(),
                "status": "pending",
                "node_id": node_id,
                "category": decision.category,
                "content": decision.content[:2000],
                "similarity": round(decision.similarity, 4),
                "nearest_id": decision.nearest_id or "",
                "nearest_content": nearest_content,
                "provenance": decision.provenance,
                "reason": decision.reason,
            }
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            return path
        except OSError as exc:
            logger.warning("Gri bant kuyruğuna yazılamadı: %s", exc)
            return None

    def pending_gray(self) -> List[Dict[str, Any]]:
        """Kuyruktaki bekleyen adaylar (pano ve toplu birleştirme turu için)."""
        path = self.queue_path
        if not path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status", "pending") == "pending":
                out.append(row)
        return out

    # -- karar --------------------------------------------------------------

    def admit(
        self,
        category: str,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: str = "",
    ) -> GateDecision:
        """
        Bir adayı değerlendirir ve kararı döndürür. **Diske yazmaz.**

        Yazma kararını çağıran uygular (`record_memory`); böylece kapı saf ve
        tek başına test edilebilir kalır.
        """
        content = (content or "").strip()
        meta = dict(metadata or {})
        resolution: CategoryResolution = normalize_category(category)
        prov, strong = derive_provenance(meta, provenance)

        decision = GateDecision(
            action=ACTION_ADD,
            category=resolution.category,
            content=content,
            importance=max(0.0, min(1.0, importance)),
            is_identity=resolution.is_identity,
            provenance=prov,
            confidence=1.0 if resolution.is_identity else (0.75 if strong else 0.40),
            metadata=meta,
        )
        if resolution.mapped:
            meta.setdefault("legacy_category", (category or "").strip())

        # 1. Kategori: kapalı küme
        if resolution.unknown and self.strict:
            return self._reject(decision, f"bilinmeyen kategori: {category!r}")

        # 2. Ayıklama: fikstür ve çok kısa metin
        if self.strict:
            if len(content) < MIN_CONTENT_CHARS:
                return self._reject(decision, f"çok kısa içerik ({len(content)} < {MIN_CONTENT_CHARS})")
            hit = fixture_match(content)
            if hit:
                return self._reject(decision, f"fikstür kalıbı: {hit}")

        # 3. Kaynak zorunluluğu — yalnızca L2 anlamsal katman.
        #    Kimlik düğümü (L4) muaftır: kaynağı sistemin kendisidir.
        if self.strict and decision.category == SEMANTIC and not decision.is_identity and not strong:
            return self._reject(decision, "L2 anlamsal yazımda kaynak (provenance) yok")

        # L0 çalışma belleği kalıcı düğüm değildir; kapı yazmaya izin verir ama
        # geri çağırma kapsamına girmez (categories.DEFAULT_RECALL_CATEGORIES).
        if decision.category == WORKING:
            decision.reason = "L0 çalışma belleği: yenilik puanı hesaplanmaz"
            self.counters[ACTION_ADD] += 1
            return decision

        # 4. Yoğunluk puanı: korpusun en yakın komşusu
        nearest_id, similarity, embedding, status = self._nearest(content)
        decision.similarity = similarity
        decision.novelty = max(0.0, 1.0 - similarity)
        decision.nearest_id = nearest_id
        decision.embedding = embedding
        decision.embedding_status = status

        # 5. Üç bant
        if nearest_id and similarity >= self.noop_threshold:
            decision.action = ACTION_NOOP
            decision.reason = f"kopya (cos {similarity:.3f} ≥ {self.noop_threshold})"
        elif nearest_id and similarity >= self.add_threshold:
            superseded = self._supersede_target(content, nearest_id)
            if superseded:
                decision.action = ACTION_SUPERSEDE
                decision.reason = superseded
            else:
                decision.action = ACTION_GRAY
                decision.reason = (
                    f"gri bant (cos {similarity:.3f}); toplu birleştirme turuna kuyruklandı"
                )
        else:
            decision.action = ACTION_ADD
            decision.reason = f"yeni (cos {similarity:.3f} < {self.add_threshold})"

        self.counters[decision.action] += 1
        return decision

    # -- yardımcılar --------------------------------------------------------

    def _reject(self, decision: GateDecision, reason: str) -> GateDecision:
        decision.action = ACTION_REJECT
        decision.reason = reason
        decision.novelty = 0.0
        self.counters[ACTION_REJECT] += 1
        logger.info("MemoryGate RED: %s | %s", reason, decision.content[:80])
        return decision

    def _nearest(self, content: str) -> Tuple[Optional[str], float, Optional[List[float]], str]:
        """En yakın komşu; gömme yeniden kullanılsın diye vektör de döner."""
        try:
            return self.memory.nearest_neighbor(content)
        except Exception as exc:  # pragma: no cover - savunma
            logger.warning("En yakın komşu hesaplanamadı: %s", exc)
            return None, 0.0, None, ""

    def _supersede_target(self, content: str, nearest_id: str) -> str:
        """
        Gri bantta çelişki var mı: aynı varlık + aynı yüklem, farklı değer.

        `reconcile_facts` (LLM'siz, Zep/Graphiti çift zamanlı deseni) karar verir.
        Boş dize = çelişki yok.
        """
        try:
            node = self.memory.get_node(nearest_id)
            if node is None:
                return ""
            new_facts = extract_facts(content, default_entity="aday", max_facts=12)
            old_facts = extract_facts(node.content or "", default_entity="aday", max_facts=12)
            if not new_facts or not old_facts:
                return ""
            existing = [
                ExistingFact(id=nearest_id, entity=f.entity, predicate=f.predicate,
                             value=f.value, text=f.raw)
                for f in old_facts
            ]
            result = reconcile_facts(new_facts, existing)
            if result.superseded:
                return f"çelişki: {result.superseded[0].reason}"
        except Exception as exc:  # pragma: no cover - savunma
            logger.warning("Uzlaştırma başarısız: %s", exc)
        return ""
