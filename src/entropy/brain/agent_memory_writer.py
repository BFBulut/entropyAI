"""
`agent_memory_writer` — hafızayı **alt ajan** yazar (Faz 14-D).

Neden
-----
Bugüne kadar hafıza düğümünü Entropy'nin köprüsü yazıyordu: rapor metninin ilk
300 karakteri, `success` bayrağına bakılmadan `store_node(importance=0.85)` ile
kaydediliyordu (A notu §1 satır 3c). Sonuç: gerçek hafızada hata metni
(`'list_iterator' object has no attribute`) ve 12 pytest izli düğüm.

İstenen mimaride (plan §4, §7 satır 14-D) yazan taraf **geçici alt ajandır**:
raporunun sonuna makine okunur bir blok koyar, Entropy o bloğu ayrıştırır,
doğrular ve **tek giriş kapısı** `MemoryGate` üzerinden yazar. Model burada
çağrılmaz; bu modül saf Python, Qt'siz ve kotasızdır.

Sözleşme
--------
Raporun sonunda tek bir blok::

    [HAFIZA]
    {"items": [
      {"category": "semantic",
       "content": "…en az 40 karakter, öğrenilen olgu…",
       "importance": 0.7,
       "provenance": {"report": "Entropy/Reports/…md",
                      "source_urls": ["https://…"]},
       "tags": ["canivopets", "pazar"]}
    ]}
    [/HAFIZA]

Doğrulama (hepsi sert):
  * `category` kapalı kümede (`semantic|episodic|procedural|working`),
  * `provenance` zorunlu (rapor yolu ya da en az bir kaynak URL'si),
  * en çok **8** madde, madde içeriği en çok **600** karakter,
  * blok tek başına JSON olmalı; bozuk JSON = blok yok sayılır.

Başarısız ya da kanıtsız koşuda (`success=False`) blok **hiç** okunmaz.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from entropy.brain.categories import CANONICAL_CATEGORIES
from entropy.brain.gate import REJECT_ERRORLOG

logger = logging.getLogger(__name__)

#: Blok etiketi. Görüntülenen metinden `strip_memory_blocks` ile silinir.
BLOCK_OPEN = "[HAFIZA]"
BLOCK_CLOSE = "[/HAFIZA]"

_BLOCK_RE = re.compile(
    r"\[HAFIZA\][^\]]*?(?=\{)(?P<body>.*?)\[/HAFIZA\]",
    re.IGNORECASE | re.DOTALL,
)
#: Gövdesi bulunamasa da görüntüden silinmesi gereken kaba kalıp.
_BLOCK_STRIP_RE = re.compile(r"\[HAFIZA\].*?(?:\[/HAFIZA\]|\Z)", re.IGNORECASE | re.DOTALL)

MAX_ITEMS = 8
MAX_CONTENT_CHARS = 600
MIN_CONTENT_CHARS = 40
ALLOWED_CATEGORIES = frozenset(CANONICAL_CATEGORIES)


@dataclass
class MemoryItem:
    """Alt ajanın beyan ettiği tek hafıza adayı (doğrulanmış hâli)."""

    category: str
    content: str
    importance: float = 0.5
    provenance: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WriteResult:
    """Bir raporun hafıza bloğunun sonucu. Hiçbir alanı iddia değil, sayımdır."""

    written: List[str] = field(default_factory=list)
    rejected: List[Tuple[str, str]] = field(default_factory=list)  # (reason, içerik başı)
    errors: List[str] = field(default_factory=list)
    items: List[MemoryItem] = field(default_factory=list)
    skipped_reason: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors and not self.skipped_reason


# --------------------------------------------------------------------------
# ayrıştırma
# --------------------------------------------------------------------------

def strip_memory_blocks(text: str) -> str:
    """`[HAFIZA] … [/HAFIZA]` bloğunu görüntülenen metinden siler."""
    return _BLOCK_STRIP_RE.sub("", str(text or "")).strip()


def extract_block(text: str) -> Optional[str]:
    """Son `[HAFIZA]` bloğunun ham JSON gövdesini döndürür (yoksa None)."""
    raw = str(text or "")
    matches = list(_BLOCK_RE.finditer(raw))
    if not matches:
        return None
    body = matches[-1].group("body").strip()
    # Kod çiti içinde verilmiş olabilir.
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", body).strip()
    return body or None


def parse_block(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Bloğu ayrıştırır. Döner: `(ham maddeler, hatalar)`.

    Bozuk JSON tek bir hata üretir ve **hiçbir madde** geçmez: yarım
    ayrıştırılmış hafıza, hafıza değildir.
    """
    body = extract_block(text)
    if body is None:
        return [], []
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError) as exc:
        return [], [f"[HAFIZA] bloğu geçerli JSON değil: {exc}"]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("items")
        if items is None:
            return [], ["[HAFIZA] bloğunda 'items' alanı yok"]
    else:
        return [], ["[HAFIZA] bloğu nesne ya da dizi olmalı"]
    if not isinstance(items, list):
        return [], ["[HAFIZA] 'items' bir dizi olmalı"]
    return [i for i in items if isinstance(i, dict)], []


# --------------------------------------------------------------------------
# doğrulama
# --------------------------------------------------------------------------

def _provenance_string(raw: Any) -> str:
    """`provenance` nesnesini kapının anladığı güçlü kaynak dizesine çevirir."""
    if isinstance(raw, str):
        return raw.strip()
    if not isinstance(raw, dict):
        return ""
    parts: List[str] = []
    report = str(raw.get("report") or raw.get("path") or "").strip()
    if report:
        parts.append(f"report={report}")
    urls = raw.get("source_urls") or raw.get("urls") or []
    if isinstance(urls, str):
        urls = [urls]
    clean = [str(u).strip() for u in urls if str(u).strip()]
    if clean:
        parts.append("url=" + ", ".join(clean[:5]))
    return "; ".join(parts)


def validate_items(
    raw_items: List[Dict[str, Any]],
    report_path: str = "",
) -> Tuple[List[MemoryItem], List[str]]:
    """Kapalı küme + kaynak + sayı/uzunluk sınırları. Döner: `(maddeler, hatalar)`."""
    errors: List[str] = []
    out: List[MemoryItem] = []
    if len(raw_items) > MAX_ITEMS:
        errors.append(f"madde sayısı sınırı aşıldı ({len(raw_items)} > {MAX_ITEMS}); ilk {MAX_ITEMS} alındı")
        raw_items = raw_items[:MAX_ITEMS]
    for idx, raw in enumerate(raw_items):
        category = str(raw.get("category") or "").strip().lower()
        content = str(raw.get("content") or "").strip()
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"madde {idx}: bilinmeyen kategori {category!r}")
            continue
        if len(content) < MIN_CONTENT_CHARS:
            errors.append(f"madde {idx}: içerik çok kısa ({len(content)} < {MIN_CONTENT_CHARS})")
            continue
        if len(content) > MAX_CONTENT_CHARS:
            errors.append(f"madde {idx}: içerik çok uzun ({len(content)} > {MAX_CONTENT_CHARS})")
            continue
        prov = _provenance_string(raw.get("provenance"))
        if not prov and report_path:
            prov = f"report={report_path}"
        if not prov:
            errors.append(f"madde {idx}: provenance yok (rapor yolu ya da kaynak URL zorunlu)")
            continue
        try:
            importance = float(raw.get("importance", 0.5))
        except (TypeError, ValueError):
            importance = 0.5
        tags_raw = raw.get("tags") or []
        tags = [str(t).strip() for t in tags_raw if str(t).strip()] if isinstance(tags_raw, list) else []
        metadata: Dict[str, Any] = {"writer": "agent", "source": "agent_memory_block"}
        if report_path:
            metadata["report_path"] = report_path
        if tags:
            metadata["tags"] = tags[:12]
        out.append(
            MemoryItem(
                category=category,
                content=content,
                importance=max(0.0, min(1.0, importance)),
                provenance=prov,
                tags=tags[:12],
                metadata=metadata,
            )
        )
    return out, errors


# --------------------------------------------------------------------------
# yazım — tek giriş kapısı
# --------------------------------------------------------------------------

def write_items(memory: Any, items: List[MemoryItem]) -> WriteResult:
    """
    Doğrulanmış maddeleri `MemoryGate` üzerinden yazar.

    Kapı bir kez koşar (`admit`), karar `record_memory(decision=…)` ile
    taşınır: aynı metin iki kez gömülmez (Faz 11 kapanışı sözleşmesi).
    """
    result = WriteResult(items=list(items))
    gate = memory.gate
    for item in items:
        decision = gate.admit(
            item.category,
            item.content,
            importance=item.importance,
            metadata=dict(item.metadata),
            provenance=item.provenance,
        )
        if not decision.writes:
            result.rejected.append((f"{decision.action}:{decision.reason}", item.content[:80]))
            continue
        node, _novel = memory.record_memory(
            decision.category,
            decision.content,
            importance=item.importance,
            metadata=dict(decision.metadata or item.metadata),
            provenance=decision.provenance,
            decision=decision,
        )
        if getattr(node, "archived", 0) == 1:
            result.rejected.append(("write_rejected", item.content[:80]))
        else:
            result.written.append(node.id)
    return result


def ingest_agent_report(
    memory: Any,
    text: str,
    report_path: str = "",
    success: bool = True,
    has_proof: bool = True,
) -> WriteResult:
    """
    Geçici ajanın rapor metnindeki `[HAFIZA]` bloğunu hafızaya işler.

    Başarısız ya da kanıtsız koşuda blok **okunmaz**: hafıza yalnızca kanıtlı
    sonucu saklar (`REJECT_ERRORLOG` bandının yazma tarafındaki karşılığı).
    """
    if not success or not has_proof:
        reason = "başarısız tur" if not success else "kanıtsız koşu"
        logger.info("[HAFIZA] bloğu yok sayıldı: %s (%s)", reason, report_path or "-")
        return WriteResult(skipped_reason=f"{REJECT_ERRORLOG}: {reason}")
    raw_items, parse_errors = parse_block(text)
    if parse_errors:
        return WriteResult(errors=parse_errors)
    if not raw_items:
        return WriteResult(skipped_reason="[HAFIZA] bloğu yok")
    items, validation_errors = validate_items(raw_items, report_path=report_path)
    result = write_items(memory, items)
    result.errors.extend(validation_errors)
    return result
