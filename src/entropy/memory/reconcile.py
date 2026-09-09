"""
Yazma anında uzlaştırma (LLM'siz).

Faz 5.1b: grafa bir metin girerken önce kural tabanlı olgu çıkarımı yapılır,
sonra kopyalar birleştirilir ve çelişkiler geçersizleştirilir. Hiçbir şey
silinmez: çelişen eski kenar `t_valid_to` ile kapatılır, yeni kenar `supersedes`
ile eskisine bağlanır (Zep/Graphiti çift zamanlı model).

Bu modül saf veri işlemedir: veritabanı bilmez, AGY/Claude çağırmaz. GraphStore
onu `ingest_text()` içinde kullanır; böylece çıkarım kuralları tek başına test
edilebilir.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Türkçe büyük/küçük harf eşlemesi: str.lower() "I" -> "i̇" üretip normalize
# edilmiş metinleri bozabiliyor; bu yüzden önce elle eşlenir.
_TR_LOWER = str.maketrans("IİĞÜŞÖÇ", "iiğüşöç")

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")

# "Anahtar: değer" satırı. Anahtar en fazla 60 karakter ve içinde cümle sonu
# noktalaması olmamalı; yoksa normal düzyazı cümleleri de olgu sanılırdı.
KEY_VALUE_RE = re.compile(
    r"^\s*(?:[-*+]\s*)?(?:\d+[.)]\s*)?(?P<key>[^:\n]{2,60}?)\s*[::]\s*(?P<value>\S.*?)\s*$"
)

# Sayısal / tarihli ifadeler: "sürüm 0.2.1", "%42 arttı", "2026-09-10", "3 gün".
NUMERIC_RE = re.compile(
    r"(?P<pred>[\wçğıöşüÇĞİÖŞÜ]+(?:\s+[\wçğıöşüÇĞİÖŞÜ]+){0,2}?)\s*"
    r"(?P<value>%?\d+(?:[.,]\d+)*(?:\s*(?:%|tl|usd|eur|gün|saat|dk|sn|kez|adet))?)",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Yüklem olamayacak kadar genel sözcükler: bunlar anahtar olursa olgu üretilmez.
_STOP_PREDICATES = {
    "not", "notlar", "özet", "ozet", "açıklama", "aciklama", "içerik", "icerik",
    "http", "https", "bkz", "ör", "or", "vb",
}


def tr_lower(text: str) -> str:
    """Türkçe duyarlı küçük harfe indirme."""
    return (text or "").translate(_TR_LOWER).lower()


def normalize_text(text: str) -> str:
    """
    Kopya tespiti için metnin kanonik biçimi.

    Unicode normalizasyonu + küçük harf + noktalama atma + boşluk sadeleştirme.
    Aynı bilginin farklı yazımları ("Sürüm: 0.2.1" / "sürüm 0,2,1 ") aynı
    anahtara düşsün diye virgül/nokta ayıraçları da temizlenir.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = tr_lower(text)
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def token_set(text: str) -> set:
    return set(normalize_text(text).split())


def similarity(a: str, b: str) -> float:
    """Jaccard benzerliği (0..1). Gömme gerektirmez; kopya eşiği için yeterli."""
    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


DUPLICATE_THRESHOLD = 0.90


@dataclass
class Fact:
    """Kural tabanlı çıkarılmış tek olgu: (varlık, yüklem, değer)."""

    entity: str
    predicate: str
    value: str
    raw: str = ""
    kind: str = "key_value"          # key_value | numeric | date | wikilink
    provenance: str = ""

    @property
    def key(self) -> Tuple[str, str]:
        """Çelişki anahtarı: aynı varlık + aynı yüklem."""
        return (normalize_text(self.entity), normalize_text(self.predicate))

    @property
    def normalized_value(self) -> str:
        return normalize_text(self.value)

    def as_text(self) -> str:
        return f"{self.entity} — {self.predicate}: {self.value}".strip()


def extract_entities(text: str) -> List[str]:
    """Metindeki `[[varlık]]` bağlarını sırayı bozmadan, tekrarsız döndürür."""
    seen, out = set(), []
    for m in WIKILINK_RE.finditer(text or ""):
        name = m.group(1).strip()
        key = normalize_text(name)
        if name and key and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def extract_facts(
    text: str,
    default_entity: str = "",
    provenance: str = "",
    max_facts: int = 40,
) -> List[Fact]:
    """
    Kural tabanlı olgu çıkarımı. LLM yok, kota harcamaz.

    Sırasıyla: `anahtar: değer` satırları, `[[varlık]]` bağları, sayısal ve
    tarihli ifadeler. Varlık satırdaki wikilink, o yoksa `default_entity`
    (genelde rapor/görev başlığı) olur.
    """
    facts: List[Fact] = []
    seen: set = set()
    lines = (text or "").splitlines()

    def _push(fact: Fact) -> None:
        sig = (fact.key, fact.normalized_value)
        if not fact.entity or not fact.predicate or not fact.value:
            return
        if sig in seen:
            return
        seen.add(sig)
        fact.provenance = fact.provenance or provenance
        facts.append(fact)

    for lineno, line in enumerate(lines, start=1):
        if len(facts) >= max_facts:
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        line_entities = extract_entities(stripped)
        entity = line_entities[0] if line_entities else default_entity
        prov = f"{provenance}:{lineno}" if provenance else ""

        m = KEY_VALUE_RE.match(stripped.lstrip("#").strip())
        if m:
            key = WIKILINK_RE.sub(r"\1", m.group("key")).strip(" -*#")
            value = WIKILINK_RE.sub(r"\1", m.group("value")).strip()
            key_norm = normalize_text(key)
            # "http://..." gibi yanlış eşleşmeler ve içeriksiz anahtarlar elenir.
            if key_norm and key_norm not in _STOP_PREDICATES and len(value) >= 1:
                # Anahtarın içinde varlık geçiyorsa varlık odur, yüklem kalan kısım.
                key_entities = extract_entities(m.group("key"))
                fact_entity = key_entities[0] if key_entities else entity
                _push(Fact(
                    entity=fact_entity or key,
                    predicate=key if key_entities else key,
                    value=value,
                    raw=stripped,
                    kind="key_value",
                    provenance=prov,
                ))
                continue

        for date in DATE_RE.findall(stripped):
            if entity:
                _push(Fact(entity=entity, predicate="tarih", value=date,
                           raw=stripped, kind="date", provenance=prov))

        if entity:
            for nm in NUMERIC_RE.finditer(stripped):
                pred = nm.group("pred").strip()
                pred_norm = normalize_text(pred)
                if not pred_norm or pred_norm in _STOP_PREDICATES or pred_norm.isdigit():
                    continue
                _push(Fact(entity=entity, predicate=pred, value=nm.group("value").strip(),
                           raw=stripped, kind="numeric", provenance=prov))
                if len(facts) >= max_facts:
                    break

    return facts[:max_facts]


@dataclass
class ReconcileDecision:
    """Tek bir olgunun uzlaştırma sonucu."""

    fact: Fact
    action: str                      # created | duplicate | superseded
    existing_id: Optional[str] = None
    reason: str = ""


@dataclass
class ReconcileResult:
    created: List[ReconcileDecision] = field(default_factory=list)
    duplicates: List[ReconcileDecision] = field(default_factory=list)
    superseded: List[ReconcileDecision] = field(default_factory=list)

    @property
    def counts(self) -> Dict[str, int]:
        return {
            "created": len(self.created),
            "duplicate": len(self.duplicates),
            "superseded": len(self.superseded),
        }


@dataclass
class ExistingFact:
    """Grafta zaten duran bir olgu (uzlaştırıcıya girdi)."""

    id: str
    entity: str
    predicate: str
    value: str
    text: str = ""


def reconcile_facts(
    new_facts: Sequence[Fact],
    existing: Iterable[ExistingFact],
    duplicate_threshold: float = DUPLICATE_THRESHOLD,
) -> ReconcileResult:
    """
    Yeni olguları mevcutlarla karşılaştırır.

    - Normalize metin aynıysa ya da benzerlik eşiği aşıyorsa: **kopya** (yeni
      düğüm açılmaz, mevcut düğümün tekrar sayısı artar).
    - Aynı varlık + aynı yüklem, farklı değer: **çelişki**; eski kayıt
      geçersizleştirilir ve yeni kayıt `supersedes` ile eskisine bağlanır.
    - Aksi halde: **yeni**.
    """
    by_key: Dict[Tuple[str, str], List[ExistingFact]] = {}
    for ex in existing:
        by_key.setdefault(
            (normalize_text(ex.entity), normalize_text(ex.predicate)), []
        ).append(ex)

    result = ReconcileResult()
    for fact in new_facts:
        candidates = by_key.get(fact.key, [])
        matched: Optional[ExistingFact] = None
        duplicate = False
        for cand in candidates:
            if normalize_text(cand.value) == fact.normalized_value:
                matched, duplicate = cand, True
                break
            if similarity(cand.text or cand.value, fact.raw or fact.as_text()) >= duplicate_threshold:
                matched, duplicate = cand, True
                break
        if matched is None and candidates:
            # Aynı varlık+yüklem var ama değer farklı -> çelişki.
            matched = candidates[-1]

        if matched is None:
            result.created.append(ReconcileDecision(fact, "created"))
        elif duplicate:
            result.duplicates.append(
                ReconcileDecision(fact, "duplicate", matched.id, "aynı normalize metin")
            )
        else:
            result.superseded.append(
                ReconcileDecision(
                    fact, "superseded", matched.id,
                    f"aynı varlık+yüklem, farklı değer: {matched.value!r} -> {fact.value!r}",
                )
            )
    return result
