"""
Rapor Merkezi (Faz 5.5) — kümeleme, digest, önem × aciliyet, güven eşiği.

Sorun: Faz 4'ün "Gelen" şeridi raporları yalnızca zaman sırasına diziyordu.
Yirmi rapor geldiğinde şerit okunaksız, iki yüz rapor geldiğinde işe yaramaz
hale geliyor. Bu modül aynı konudaki raporları tek bir **digest kartında**
toplar, her kartı önem × aciliyet ile rozetler ve güveni yüksek rutin raporları
"sessiz" bölüme katlar; kullanıcı önce karar gerektiren şeyi görür.

Tasarım kaynağı: `docs/reports/2026-09-10_Faz5_Tasarim_Raporu.md` §3.3.

Mimari not — **LLM yok**. Kümeleme başlık TF-IDF kosinüsü + basit birleştirici
(agglomeratif) eşik kümelemesidir; bulgu satırları rapor özetlerinin ilk
cümleleridir; karar önerisi rapordaki "Öneri/Sonuç" başlığının altındaki ilk
satırdır. Böylece 200 rapor tek kota harcamadan, milisaniyeler içinde triyaj
edilir.

İş parçacığı notu: bu dosyadaki *fonksiyonlar* saf Python'dur (Qt yok), işçi
iş parçacığından çağrılabilir. `ReportCenterWidget` yalnızca ana iş
parçacığında kullanılmalıdır.
"""

from __future__ import annotations

import json
import os
import math
import re
import time
from collections import Counter
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from entropy.core.config import STATE_DIR
from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.report_inbox import ReportInboxStore, get_shared_store
from entropy.ui.widgets.ui_polish import BODY_PX, LABEL_PX
# Gömülü HTML gövdelerinin renk kaynağı (Faz 12-D.2): düz onaltılık yerine
# `TOKENS`/`TOKENS["viz"]` köprüsü. Bkz. `entropy.ui.design.embedded`.
from entropy.ui.design.embedded import palette as _embedded_palette

_P = _embedded_palette()

# --------------------------------------------------------------------- ayar

SETTINGS_FILENAME = "report_center.json"

# Güven eşiği: bu değerin ÜSTÜNDE güvene sahip kartlar "sessiz" bölüme katlanır.
# 0.75 seçildi çünkü ölçütü eksik / başarısız / düşük notlu raporların güveni
# aşağıdaki `card_confidence` ile en fazla 0.7 çıkar; yani rutin ve tam raporlar
# katlanır, kusurlu olan her şey öne gelir.
DEFAULT_QUIET_THRESHOLD = 0.75

# Başlık kosinüs benzerliği bu eşiğin üstündeyse aynı kümeye girer. 0.34,
# "Q3 Finansal Denetim — Bölüm 1/2/3" gibi seri raporları birleştirecek kadar
# gevşek, ilgisiz konuları ayıracak kadar sıkı (200 sahte raporla ölçüldü).
DEFAULT_CLUSTER_THRESHOLD = 0.34


def settings_path() -> Path:
    return Path(STATE_DIR) / SETTINGS_FILENAME


def load_quiet_threshold(path: Optional[Path] = None) -> float:
    """`report_center_quiet_threshold` ayarını okur (yoksa varsayılan)."""
    target = Path(path) if path is not None else settings_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        value = float(raw.get("report_center_quiet_threshold", DEFAULT_QUIET_THRESHOLD))
    except (OSError, ValueError, TypeError):
        return DEFAULT_QUIET_THRESHOLD
    return min(1.0, max(0.0, value))


def save_quiet_threshold(value: float, path: Optional[Path] = None) -> bool:
    target = Path(path) if path is not None else settings_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
            except ValueError:
                data = {}
        data["report_center_quiet_threshold"] = min(1.0, max(0.0, float(value)))
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except (OSError, TypeError, ValueError):
        return False


# ------------------------------------------------------------------ metin

# Türkçe + İngilizce durak sözcükler: başlık vektörünü "ve/için/report/2026"
# gibi her başlıkta geçen kelimeler baskılamasın.
STOPWORDS = {
    "ve", "ile", "için", "icin", "bir", "bu", "şu", "su", "the", "and", "for",
    "of", "on", "in", "to", "a", "an", "de", "da", "den", "dan", "raporu",
    "rapor", "report", "notu", "not", "analizi", "analiz", "hakkında",
    "hakkinda", "üzerine", "uzerine", "ozet", "özet", "summary",
}

_TOKEN_RE = re.compile(r"[0-9a-zçğıöşü]+", re.IGNORECASE)

# Aciliyet sinyali veren kelimeler. "blokaj" ve "son tarih" tasarım raporunda
# açıkça sayılıyor; kalanlar aynı ailenin yaygın yazımları.
URGENCY_WORDS = (
    "acil", "blokaj", "bloke", "blocker", "blocked", "son tarih", "deadline",
    "gecikme", "kritik", "urgent", "hemen", "risk", "durdu", "başarısız",
    "basarisiz", "failed", "hata", "ihlal", "aşıldı", "asildi",
)

# Kaynak türüne göre taban önem (bellek `importance` alanı yoksa kullanılır).
# Tasarım: ofis raporu > query > rapor.
SOURCE_IMPORTANCE = {
    "office": 0.80,
    "mailbox": 0.75,
    "query": 0.60,
    "report": 0.45,
}

# "Karar önerisi" satırını taşıyan başlıklar (markdown başlığı ya da kalın satır).
DECISION_HEADINGS = (
    "öneri", "oneri", "öneriler", "oneriler", "sonuç", "sonuc", "karar",
    "tavsiye", "recommendation", "recommendations", "conclusion", "next steps",
)

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")


def tokenize_title(title: str) -> List[str]:
    """Başlığı kümeleme için sözcüklere ayırır (küçük harf, durak sözcüksüz)."""
    tokens = [t.lower() for t in _TOKEN_RE.findall(str(title or ""))]
    return [t for t in tokens if len(t) > 2 and t not in STOPWORDS]


def tfidf_vectors(titles: Sequence[str]) -> List[Dict[str, float]]:
    """
    Başlık listesinden L2-normalize edilmiş TF-IDF vektörleri üretir.

    Neden kendi elimizle: sklearn bağımlılığı yok ve başlıklar kısa; 200 başlık
    için bu döngü bir milisaniyenin altında kalıyor.
    """
    docs = [tokenize_title(t) for t in titles]
    n = max(1, len(docs))
    df: Counter = Counter()
    for doc in docs:
        df.update(set(doc))
    vectors: List[Dict[str, float]] = []
    for doc in docs:
        tf = Counter(doc)
        vec: Dict[str, float] = {}
        for token, count in tf.items():
            idf = math.log((n + 1.0) / (df[token] + 1.0)) + 1.0
            vec[token] = (count / len(doc)) * idf
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({k: v / norm for k, v in vec.items()})
    return vectors


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    """İki seyrek vektörün kosinüs benzerliği (ikisi de L2-normalize varsayılır)."""
    if len(a) > len(b):
        a, b = b, a
    return sum(weight * b.get(token, 0.0) for token, weight in a.items())


def first_sentences(text: str, count: int = 1) -> List[str]:
    """Metinden ilk `count` cümleyi çıkarır (markdown gürültüsü temizlenir)."""
    clean = re.sub(r"^\s*[#>\-*\d.]+\s*", "", str(text or "").strip())
    clean = re.sub(r"[*_`\[\]]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return []
    parts = [p.strip() for p in _SENTENCE_RE.split(clean) if p.strip()]
    return parts[:count]


# ------------------------------------------------------------- künye zenginleştirme

def _body_after_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:]
    return text


def extract_summary_and_decision(body: str) -> Tuple[str, str]:
    """
    Rapor gövdesinden (özet ilk cümlesi, karar önerisi satırı) çifti çıkarır.

    Özet: ilk başlıksız, boş olmayan paragrafın ilk cümlesi.
    Karar: "Öneri / Sonuç / Karar" başlığından sonraki ilk anlamlı satır; böyle
    bir başlık yoksa boş dizge (kart "karar önerisi yok" der, uydurmaz).
    """
    lines = _body_after_frontmatter(body).splitlines()
    summary = ""
    decision = ""
    capture_decision = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        is_heading = stripped.startswith("#") or (
            stripped.startswith("**") and stripped.endswith("**")
        )
        heading_text = stripped.strip("#*_ ").strip().lower()
        if is_heading:
            capture_decision = any(h in heading_text for h in DECISION_HEADINGS)
            continue
        if capture_decision and not decision:
            found = first_sentences(stripped, 1)
            if found:
                decision = found[0]
                capture_decision = False
            continue
        if not summary:
            found = first_sentences(stripped, 1)
            if found:
                summary = found[0]
    return summary, decision


#: Faz 9 - rapor basi onbellegi. Anahtar: (yol, mtime, boyut, limit).
#: `refresh()` her cagrildiginda `enrich_entry` her kunye icin dosyayi ikinci
#: kez okuyordu (703 rapor => 703 disk okumasi/klik). Dosya imzasi degismedigi
#: surece artik disk'e gidilmez.
_HEAD_CACHE: Dict[tuple, str] = {}
_HEAD_CACHE_MAX = 4000


def _read_head(path: Any, limit: int = 8192) -> str:
    key = None
    try:
        st = os.stat(str(path))
        key = (str(path), st.st_mtime, st.st_size, int(limit))
        cached = _HEAD_CACHE.get(key)
        if cached is not None:
            return cached
    except OSError:
        return ""
    try:
        with open(str(path), "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(limit)
    except OSError:
        return ""
    if key is not None:
        if len(_HEAD_CACHE) > _HEAD_CACHE_MAX:
            _HEAD_CACHE.clear()
        _HEAD_CACHE[key] = head
    return head


def detect_source(entry: Dict[str, Any]) -> str:
    """Künyeden kaynak türünü çıkarır: office / query / mailbox / report."""
    if entry.get("source"):
        return str(entry["source"])
    path = str(entry.get("path", ""))
    parts = Path(path).parts
    if "Offices" in parts or str(entry.get("office") or ""):
        return "office"
    folder = str(entry.get("folder") or "").lower()
    if folder in ("queries", "query") or "/query/" in path.replace("\\", "/").lower():
        return "query"
    return "report"


def detect_office(entry: Dict[str, Any]) -> str:
    if entry.get("office"):
        return str(entry["office"])
    parts = Path(str(entry.get("path", ""))).parts
    if "Offices" in parts:
        idx = parts.index("Offices")
        if len(parts) > idx + 1:
            return parts[idx + 1]
    for tag in entry.get("tags") or []:
        if str(tag).lower().startswith("office:"):
            return str(tag).split(":", 1)[1].strip()
    return ""


def detect_card(entry: Dict[str, Any]) -> str:
    if entry.get("card"):
        return str(entry["card"])
    for tag in entry.get("tags") or []:
        low = str(tag).lower()
        for prefix in ("card:", "task:", "task_id:"):
            if low.startswith(prefix):
                return str(tag).split(":", 1)[1].strip()
    return ""


def enrich_entry(entry: Dict[str, Any], read_body: bool = True) -> Dict[str, Any]:
    """
    Rapor künyesine Rapor Merkezi'nin ihtiyaç duyduğu alanları ekler.

    Girdi `reports_viewer.read_report_meta` biçimidir; posta kutusu mesajları da
    `mailbox_entries()` ile aynı biçime çevrilir. Dosya okunamazsa (silinmiş
    olabilir) alanlar boş kalır, akış kırılmaz.
    """
    out = dict(entry)
    out["source"] = detect_source(out)
    out["office"] = detect_office(out)
    out["card"] = detect_card(out)
    body = out.get("body")
    if body is None and read_body:
        body = _read_head(out.get("path", ""))
    body = str(body or "")
    if not out.get("summary") or not out.get("decision"):
        summary, decision = extract_summary_and_decision(body)
        out.setdefault("summary", "")
        out.setdefault("decision", "")
        out["summary"] = out["summary"] or summary
        out["decision"] = out["decision"] or decision
    haystack = f"{out.get('title', '')} {out.get('summary', '')} {body[:2000]}".lower()
    out["_haystack"] = haystack
    if "status" not in out:
        out["status"] = "failed" if "failed" in haystack or "başarısız" in haystack else ""
    grade = out.get("grade")
    if grade is None:
        match = re.search(r"(?:grade|not|puan)\s*[:=]\s*([01](?:[.,]\d+)?)", haystack)
        grade = float(match.group(1).replace(",", ".")) if match else None
    out["grade"] = grade
    out["importance"] = entry_importance(out)
    out["urgency"] = entry_urgency(out)
    out["confidence"] = entry_confidence(out)
    return out


def entry_importance(entry: Dict[str, Any]) -> float:
    """
    Önem: bellek grafiğinin `importance` alanı varsa o, yoksa kaynak türü tabanı.

    Bellek ajanı düğümlere `importance` yazdığında (Faz 5.1) rapor künyesi de
    bu alanı taşır; alan yoksa tasarımdaki sıra (ofis > query > rapor) kullanılır.
    """
    raw = entry.get("importance")
    try:
        if raw is not None:
            return min(1.0, max(0.0, float(raw)))
    except (TypeError, ValueError):
        pass
    base = SOURCE_IMPORTANCE.get(detect_source(entry), 0.45)
    if entry.get("pinned"):
        base = min(1.0, base + 0.15)
    return base


def entry_urgency(entry: Dict[str, Any]) -> float:
    """
    Aciliyet: son tarih yakınlığı + blokaj kelimeleri + `failed` durumu.

    Tek bir sayı döner (0–1). Kart rozeti bu sayıyı üç kademeye indirir; ham
    değeri saklamak sıralamayı kararlı yapar.
    """
    score = 0.0
    haystack = entry.get("_haystack") or (
        f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
    )
    hits = sum(1 for word in URGENCY_WORDS if word in haystack)
    score += min(0.6, hits * 0.2)
    if str(entry.get("status", "")).lower() in ("failed", "error", "canceled"):
        score += 0.35
    due = entry.get("due") or entry.get("deadline")
    if due:
        try:
            remaining = float(due) - time.time()
            if remaining <= 0:
                score += 0.4
            elif remaining < 86400:
                score += 0.3
            elif remaining < 3 * 86400:
                score += 0.15
        except (TypeError, ValueError):
            pass
    return min(1.0, score)


def entry_confidence(entry: Dict[str, Any]) -> float:
    """
    Güven: raporun "elden geçirilmeden kabul edilebilir" olma olasılığı.

    Düşüren etkenler: `failed` durumu, eksik ölçüt (özet ya da karar satırı
    yok), `grade < 0.6`. Güveni yüksek olanlar sessiz bölüme katlanır.
    """
    score = 1.0
    if str(entry.get("status", "")).lower() in ("failed", "error", "canceled"):
        score -= 0.5
    if not str(entry.get("summary") or "").strip():
        score -= 0.2
    if not str(entry.get("decision") or "").strip():
        score -= 0.1
    grade = entry.get("grade")
    try:
        if grade is not None and float(grade) < 0.6:
            score -= 0.3
    except (TypeError, ValueError):
        pass
    return min(1.0, max(0.0, score))


# --------------------------------------------------------------- kümeleme

def cluster_entries(
    entries: Sequence[Dict[str, Any]],
    threshold: float = DEFAULT_CLUSTER_THRESHOLD,
) -> List[List[Dict[str, Any]]]:
    """
    Raporları konu + ofis + kart üçlüsüne göre kümeler.

    Önce ofis/kart kimliğine göre kaba bölme yapılır (aynı kartın raporları her
    zaman birlikte kalmalı), sonra her bölme içinde başlık TF-IDF kosinüsü ile
    tek geçişli birleştirici kümeleme koşar: her rapor, benzerliği eşiği aşan
    ilk kümenin merkezine katılır, yoksa yeni küme açar. Merkez, kümeye giren
    vektörlerin ortalamasıdır (yeniden normalize edilir).

    LLM kullanılmaz; 200 raporda ölçülen süre 10 ms'in altındadır.
    """
    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for entry in entries or []:
        key = (str(entry.get("office") or ""), str(entry.get("card") or ""))
        buckets.setdefault(key, []).append(entry)

    clusters: List[List[Dict[str, Any]]] = []
    for (office, card), bucket in buckets.items():
        if card:
            # Aynı kartın raporları tanım gereği tek konu: başlık bakılmaz.
            clusters.append(list(bucket))
            continue
        vectors = tfidf_vectors([str(e.get("title", "")) for e in bucket])
        centroids: List[Dict[str, float]] = []
        members: List[List[Dict[str, Any]]] = []
        for entry, vec in zip(bucket, vectors):
            best_idx, best_sim = -1, threshold
            for idx, centroid in enumerate(centroids):
                sim = cosine(vec, centroid)
                if sim >= best_sim:
                    best_idx, best_sim = idx, sim
            if best_idx < 0:
                centroids.append(dict(vec))
                members.append([entry])
            else:
                members[best_idx].append(entry)
                merged = dict(centroids[best_idx])
                for token, weight in vec.items():
                    merged[token] = merged.get(token, 0.0) + weight
                norm = math.sqrt(sum(v * v for v in merged.values())) or 1.0
                centroids[best_idx] = {k: v / norm for k, v in merged.items()}
        clusters.extend(members)
    return clusters


def _cluster_title(members: Sequence[Dict[str, Any]]) -> str:
    """Küme başlığı: en önemli üyenin başlığı, çoklu kümede "+N" ekiyle."""
    ordered = sorted(members, key=lambda e: (-float(e.get("importance", 0.0)), str(e.get("title", ""))))
    head = str(ordered[0].get("title") or Path(str(ordered[0].get("path", ""))).stem)
    if len(members) > 1:
        head = f"{head} (+{len(members) - 1})"
    return head


def build_digest(
    members: Sequence[Dict[str, Any]],
    quiet_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Bir kümeden digest kartı üretir.

    Kart alanları: başlık, rapor sayısı, en fazla 3 bulgu satırı (üyelerin
    özetlerinin ilk cümleleri), 1 karar önerisi satırı, önem/aciliyet/güven
    puanları ve rozet etiketleri, "detayı aç" için birincil yol.
    """
    members = list(members)
    if not members:
        return {}
    findings: List[str] = []
    for entry in sorted(members, key=lambda e: -float(e.get("importance", 0.0))):
        summary = str(entry.get("summary") or "").strip()
        if summary and summary not in findings:
            findings.append(summary)
        if len(findings) >= 3:
            break
    decision = ""
    for entry in members:
        candidate = str(entry.get("decision") or "").strip()
        if candidate:
            decision = candidate
            break
    importance = max(float(e.get("importance", 0.0)) for e in members)
    urgency = max(float(e.get("urgency", 0.0)) for e in members)
    # Küme güveni EN DÜŞÜK üyeye eşittir: kümede tek bir kusurlu rapor varsa
    # kart sessiz bölüme katlanmamalı.
    confidence = min(float(e.get("confidence", 1.0)) for e in members)
    unread = sum(1 for e in members if not e.get("read"))
    primary = sorted(members, key=lambda e: (-float(e.get("importance", 0.0)), -float(e.get("mtime", 0.0))))[0]
    threshold = DEFAULT_QUIET_THRESHOLD if quiet_threshold is None else float(quiet_threshold)
    return {
        "title": _cluster_title(members),
        "count": len(members),
        "unread": unread,
        "findings": findings,
        "decision": decision,
        "importance": importance,
        "urgency": urgency,
        "confidence": confidence,
        "importance_label": importance_label(importance),
        "urgency_label": urgency_label(urgency),
        "quiet": confidence > threshold,
        "office": str(primary.get("office") or ""),
        "card": str(primary.get("card") or ""),
        "path": str(primary.get("path") or ""),
        "pinned": any(e.get("pinned") for e in members),
        "members": members,
    }


def importance_label(value: float) -> str:
    if value >= 0.75:
        return "yüksek"
    if value >= 0.5:
        return "orta"
    return "düşük"


def urgency_label(value: float) -> str:
    if value >= 0.6:
        return "acil"
    if value >= 0.3:
        return "yakın"
    return "sakin"


def build_report_center(
    entries: Sequence[Dict[str, Any]],
    quiet_threshold: Optional[float] = None,
    cluster_threshold: float = DEFAULT_CLUSTER_THRESHOLD,
    read_body: bool = True,
) -> Dict[str, Any]:
    """
    Uçtan uca triyaj: künyeler → zenginleştirme → kümeleme → digest kartları →
    güven eşiğiyle "öne çıkan" / "sessiz" ayrımı.

    Dönen sözlük: {"cards": [...], "quiet": [...], "total": n}
    Sıralama: önce pinliler, sonra (aciliyet + önem) toplamı, sonra yenilik.
    """
    threshold = load_quiet_threshold() if quiet_threshold is None else float(quiet_threshold)
    enriched = [enrich_entry(e, read_body=read_body) for e in entries or []]
    clusters = cluster_entries(enriched, threshold=cluster_threshold)
    cards = [build_digest(c, quiet_threshold=threshold) for c in clusters]

    def sort_key(card: Dict[str, Any]):
        newest = max((float(m.get("mtime", 0.0)) for m in card["members"]), default=0.0)
        return (not card.get("pinned"), -(card["urgency"] + card["importance"]), -newest)

    cards.sort(key=sort_key)
    return {
        "cards": [c for c in cards if not c["quiet"]],
        "quiet": [c for c in cards if c["quiet"]],
        "total": len(enriched),
        "quiet_threshold": threshold,
    }


# ------------------------------------------------------------ posta kutusu

def mailbox_entries(owner_kind: str = "entropy", owner_name: str = "entropy") -> List[Dict[str, Any]]:
    """
    Entropy posta kutusundaki `report` mesajlarını rapor künyesine çevirir.

    Sözleşme (agy ajanı, Faz 5.3): `Mailbox(kind, name).list(unread=True)` →
    `Message{id, task_id, from_, to, role, kind, parts, status, created_at,
    terminal}`. Modül henüz yoksa boş liste döner: Rapor Merkezi kasadaki
    raporlarla çalışmaya devam eder.
    """
    try:
        from entropy.agents.mailbox import Mailbox  # type: ignore
    except Exception:
        return []
    try:
        messages = list(Mailbox(owner_kind, owner_name).list(unread=True) or [])
    except Exception:
        return []
    return [message_to_entry(m) for m in messages if _message_kind(m) == "report"]


def parse_timestamp(value: Any) -> float:
    """
    Unix damgası ya da ISO-8601 dizgesini float saniyeye çevirir.

    Posta kutusu `created_at` alanını ISO yazıyor (`mailbox._now()`), rapor
    künyeleri ise `mtime` float taşıyor; Rapor Merkezi ikisini aynı listede
    sıraladığı için tek dönüştürücü kullanılır. Çözülemeyen değer "şimdi"
    sayılır: mesajı listenin dibine atmak, yeni gelen raporu gizlerdi.
    """
    if value in (None, ""):
        return time.time()
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    import datetime as _dt

    text = str(value).strip().replace("Z", "+00:00")
    try:
        return _dt.datetime.fromisoformat(text).timestamp()
    except ValueError:
        return time.time()


def _message_kind(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("kind", ""))
    return str(getattr(message, "kind", ""))


def _field(message: Any, name: str, default: Any = "") -> Any:
    if isinstance(message, dict):
        return message.get(name, default)
    return getattr(message, name, default)


def message_to_entry(message: Any) -> Dict[str, Any]:
    """Posta kutusu mesajını Rapor Merkezi künyesine çevirir (guard'lı)."""
    parts = _field(message, "parts", []) or []
    texts: List[str] = []
    for part in parts:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict):
            texts.append(str(part.get("text") or part.get("content") or ""))
        else:
            texts.append(str(getattr(part, "text", "") or ""))
    body = "\n".join(t for t in texts if t)
    title = ""
    for line in body.splitlines():
        if line.strip():
            title = line.strip().lstrip("# ").strip()
            break
    sender = str(_field(message, "from_", "") or _field(message, "from", ""))
    office = sender.split("/", 1)[1] if "/" in sender else sender
    mtime = parse_timestamp(_field(message, "created_at", 0.0))
    return {
        "path": f"mailbox://{_field(message, 'id', '')}",
        "title": title or f"Posta kutusu mesajı {_field(message, 'id', '')}",
        "body": body,
        "mtime": mtime,
        "source": "mailbox",
        "office": office,
        "card": str(_field(message, "task_id", "") or ""),
        "status": str(_field(message, "status", "") or ""),
        "tags": [],
    }


# ------------------------------------------------------------ orkestratör

def ask_orchestrator(office: str, question: str, bridge: Any = None) -> str:
    """
    Kart üzerindeki "Orkestratöre sor / Revizyon iste" eylemi.

    Yerel `/ask <ofis> ...` komutunu tetikler. Komut işleyicisi (agy ajanı,
    Faz 5.3) henüz yoksa kullanıcıya ne yapması gerektiğini söyleyen bir metin
    döner — sessizce yutmak, düğmenin bozuk olduğunu gizlerdi.
    """
    prompt = f"/ask {office} {question}".strip()
    try:
        from entropy.core.slash_commands import try_handle_local_command  # type: ignore
    except Exception:
        return f"`{prompt}` komutu bu sürümde kullanılamıyor (yerel komut katmanı yok)."
    try:
        result = try_handle_local_command(prompt, bridge)
    except Exception as exc:  # pragma: no cover - işleyici hatası
        return f"`{prompt}` çalıştırılamadı: {exc}"
    if not result:
        return f"`{prompt}` komutunu bu sürüm tanımıyor."
    return str(result)


# --------------------------------------------------------------- görünüm

def _badge(text: str, fg: str, bg: str) -> str:
    return (
        f"<span style='background:{bg}; color:{fg}; border-radius:8px;"
        f" padding:1px 7px; font-size:{LABEL_PX}px; font-weight:600;'>{text}</span>"
    )


IMPORTANCE_COLORS = {
    "yüksek": (f"{_P["warn"]}", "rgba(255,159,69,0.16)"),
    "orta": (f"{_P["accent"]}", "rgba(121,192,255,0.14)"),
    "düşük": (f"{_P["text_muted"]}", "rgba(139,148,158,0.12)"),
}
URGENCY_COLORS = {
    "acil": (f"{_P["danger"]}", "rgba(255,77,77,0.16)"),
    "yakın": (f"{_P["warn"]}", "rgba(227,179,65,0.14)"),
    "sakin": (f"{_P["ok"]}", "rgba(126,231,135,0.12)"),
}


class DigestCardWidget(QFrame):
    """Tek digest kartı: başlık, rozetler, 3 bulgu, karar önerisi, eylemler."""

    def __init__(self, card: Dict[str, Any], center: "ReportCenterWidget", parent=None):
        super().__init__(parent)
        self.card = card
        self.center = center
        self.setObjectName("digestCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        # Kart içindeki uzun başlık/özet etiketleri kartın minimumunu ~580 px'e
        # itiyor, o da kaydırma alanı üzerinden panelin minimumu oluyordu.
        # Kart daralabilsin; metin kendi içinde kırpılır/sarılır.
        self.setMinimumWidth(180)
        accent =RT["accent_warn"] if card.get("unread") else RT["divider"]
        self.setProperty("role", "panel")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(6)
        self.title_label = QLabel(str(card.get("title", "")))
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setWordWrap(True)
        self.title_label.setProperty("role", "label")
        self.title_label.setToolTip(str(card.get("path", "")))
        head.addWidget(self.title_label, 1)

        imp_fg, imp_bg = IMPORTANCE_COLORS.get(card["importance_label"], IMPORTANCE_COLORS["düşük"])
        urg_fg, urg_bg = URGENCY_COLORS.get(card["urgency_label"], URGENCY_COLORS["sakin"])
        self.badge_label = QLabel(
            _badge(f"önem: {card['importance_label']}", imp_fg, imp_bg)
            + " "
            + _badge(f"aciliyet: {card['urgency_label']}", urg_fg, urg_bg)
        )
        self.badge_label.setTextFormat(Qt.TextFormat.RichText)
        self.badge_label.setToolTip(
            f"Önem {card['importance']:.2f} · Aciliyet {card['urgency']:.2f}"
            f" · Güven {card['confidence']:.2f}"
        )
        head.addWidget(self.badge_label)
        root.addLayout(head)

        meta_bits = [f"{card['count']} rapor"]
        if card.get("unread"):
            meta_bits.append(f"{card['unread']} okunmadı")
        if card.get("office"):
            meta_bits.append(f"{card['office']}")
        if card.get("card"):
            meta_bits.append(f"{card['card']}")
        self.meta_label = QLabel(" · ".join(meta_bits))
        self.meta_label.setProperty("role", "label")
        root.addWidget(self.meta_label)

        findings = card.get("findings") or []
        self.findings_label = QLabel(
            "\n".join(f"• {f}" for f in findings) if findings
            else "• Bu kümedeki raporlarda özet cümlesi bulunamadı."
        )
        self.findings_label.setWordWrap(True)
        self.findings_label.setTextFormat(Qt.TextFormat.PlainText)
        self.findings_label.setProperty("role", "label")
        root.addWidget(self.findings_label)

        decision = card.get("decision") or ""
        self.decision_label = QLabel(
            f"{decision}" if decision else "Karar önerisi yok (raporda öneri/sonuç başlığı bulunmadı)."
        )
        self.decision_label.setWordWrap(True)
        self.decision_label.setTextFormat(Qt.TextFormat.PlainText)
        self.decision_label.setProperty("role", "label")
        root.addWidget(self.decision_label)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        self.open_btn = self._action_btn("Detayı aç", "Kümenin birincil raporunu okuyucuda aç")
        self.open_btn.clicked.connect(self._on_open)
        actions.addWidget(self.open_btn)

        self.ask_btn = self._action_btn(
            "Orkestratöre sor",
            "Bu kümenin ofisine `/ask <ofis> ...` ile revizyon/açıklama isteği gönderir",
        )
        self.ask_btn.clicked.connect(self._on_ask)
        self.ask_btn.setEnabled(bool(card.get("office")))
        actions.addWidget(self.ask_btn)

        self.read_btn = self._action_btn("Okundu", "Kümedeki bütün raporları okundu işaretle")
        self.read_btn.clicked.connect(self._on_read)
        actions.addWidget(self.read_btn)

        self.pin_btn = self._action_btn("", "Sabitle / sabitlemeyi kaldır")
        self.pin_btn.clicked.connect(self._on_pin)
        actions.addWidget(self.pin_btn)

        self.archive_btn = self._action_btn("", "Kümeyi arşivle")
        self.archive_btn.clicked.connect(self._on_archive)
        actions.addWidget(self.archive_btn)
        actions.addStretch()
        root.addLayout(actions)

    @staticmethod
    def _action_btn(text: str, tip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("variant", "ghost")
        return btn

    # ---------------------------------------------------------- eylemler

    def _paths(self) -> List[str]:
        return [str(m.get("path", "")) for m in self.card.get("members", []) if m.get("path")]

    def _on_open(self) -> None:
        self.center.open_card(self.card)

    def _on_ask(self) -> None:
        self.center.ask_about_card(self.card)

    def _on_read(self) -> None:
        self.center.mark_paths_read(self._paths())

    def _on_pin(self) -> None:
        self.center.toggle_pin_paths(self._paths())

    def _on_archive(self) -> None:
        self.center.archive_paths(self._paths())


class ReportCenterWidget(QFrame):
    """
    Rapor Merkezi paneli (Zen "Raporlar" sekmesinin üst yarısı, Chat "Gelen").

    Kullanım: `set_entries(...)` rapor künyelerini verir. Panel künyeleri
    zenginleştirir, kümeler, digest kartlarına çevirir; yüksek güvenli rutin
    kümeleri "sessiz" bölümde katlı tutar.
    """

    report_opened = Signal(str)   # açılacak rapor yolu
    unread_changed = Signal(int)  # okunmadı sayısı
    #: Faz 8: "Tümü" düğmesi — tam rapor listesine geçiş isteği.
    show_all_requested = Signal()
    orchestrator_answer = Signal(str, str)  # ofis, yanıt gövdesi

    def __init__(
        self,
        parent=None,
        store: Optional[ReportInboxStore] = None,
        bridge: Any = None,
        ask_handler: Optional[Callable[[str, str], str]] = None,
    ):
        super().__init__(parent)
        self.setObjectName("reportCenter")
        # Panel dar Zen sol sekmesinde de yaşayabilmeli: başlık satırındaki
        # düğmeler ve kartlar toplamda 1400 px'lik örtük bir minimum üretiyordu.
        # Açık minimum, iç araç çubuğunun panel yerine kendisinin kırpılmasını
        # (ve kaydırma çubuğuyla erişilebilir kalmasını) sağlar.
        self.setMinimumWidth(240)
        self.store = store if store is not None else get_shared_store()
        self.bridge = bridge
        # Testler ve Chat kipi kendi işleyicisini verebilsin diye enjekte edilir;
        # varsayılan yerel `/ask` komutudur.
        self.ask_handler = ask_handler
        self._entries: List[Dict[str, Any]] = []
        self._result: Dict[str, Any] = {"cards": [], "quiet": [], "total": 0}
        self._cluster_signature: Optional[tuple] = None
        self._cluster_index: List[List[int]] = []
        self._enrich_cache: Dict[tuple, Dict[str, Any]] = {}
        self._quiet_expanded = False
        self._mailbox_cache: Optional[List[Dict[str, Any]]] = None
        self.quiet_threshold = load_quiet_threshold()
        # Faz 9 - kasa tazelemesi icin birlestirme zamanlayicisi ve isci durumu.
        self._reload_running = False
        self._reload_again = False
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._start_background_reload)

        self.setProperty("role", "panel")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.header_label = QLabel("")
        self.header_label.setTextFormat(Qt.TextFormat.RichText)
        self.header_label.setProperty("role", "label")
        # Zengin metin başlık tek satırda ~666 px minimumSizeHint üretiyordu; bu da
        # Rapor Merkezi'nin (ve onu barındıran Zen sol sekmesinin) minimumunu
        # 1400 px'in üstüne çıkarıp dar panelde araç çubuğunu kırpıyordu. Açık
        # küçük minimum vererek satırın daralmasına izin veriyoruz.
        self.header_label.setMinimumWidth(120)
        self.header_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        head.addWidget(self.header_label, 1)
        head.addStretch()
        self.mark_all_btn = DigestCardWidget._action_btn(
            "Tümünü okundu say", "Rapor Merkezi'ndeki bütün raporları okundu işaretle"
        )
        self.mark_all_btn.clicked.connect(self.mark_all_read)
        head.addWidget(self.mark_all_btn)
        self.prune_btn = DigestCardWidget._action_btn(
            "Temizle", "Silinmiş raporların okundu/pin/arşiv kayıtlarını temizle (prune)"
        )
        self.prune_btn.clicked.connect(self.prune_missing)
        head.addWidget(self.prune_btn)

        # Güven eşiği ayarı doğrudan panelde: tasarımdaki risk maddesi "yanlış
        # sessiz arşiv kararı"nı kullanıcının anında düzeltebilmesini istiyor.
        self.threshold_combo = QComboBox()
        self.threshold_combo.setToolTip(
            "Güven eşiği (report_center_quiet_threshold): bu değerin üstünde"
            " güvene sahip kümeler sessiz bölüme katlanır. Düşürmek daha çok"
            " raporu öne çıkarır."
        )
        for value in (0.50, 0.65, 0.75, 0.85, 0.95, 1.01):
            label = "kapalı" if value > 1.0 else f"eşik {value:.2f}"
            self.threshold_combo.addItem(label, value)
        head.addWidget(self.threshold_combo)
        root.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.viewport().setAutoFillBackground(False)
        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(6)
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.cards_host)
        root.addWidget(self.scroll, 1)

        self.quiet_btn = DigestCardWidget._action_btn("", "Yüksek güvenli rutin raporlar")
        self.quiet_btn.clicked.connect(self.toggle_quiet)
        # Uzun etiket ("Sessiz bölüm — N yüksek güvenli rutin küme") panelin
        # minimumunu 548 px'e çekiyordu; dar panelde metin kırpılsın, panel değil.
        self.quiet_btn.setMinimumWidth(120)
        self.quiet_btn.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        root.addWidget(self.quiet_btn)

        # Faz 8: kart listesi ozetlidir (895 rapordan 9 kart + 135 sessiz kume);
        # kullanici "toplam raporlar gorunmuyor" dedi. Bu dugme sessiz bolumu
        # acar ve tam rapor listesini gosteren yuzeyi (Raporlar sekmesi ya da
        # bagimsiz pencere) ister.
        self.show_all_btn = DigestCardWidget._action_btn(
            "Tümü", "Sessiz bölümü aç ve tam rapor listesine geç"
        )
        self.show_all_btn.clicked.connect(self._on_show_all_clicked)
        self.show_all_btn.setMinimumWidth(80)
        self.show_all_btn.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        root.addWidget(self.show_all_btn)

        self.empty_label = QLabel("")
        self.empty_label.setWordWrap(True)
        self.empty_label.setProperty("role", "label")
        root.addWidget(self.empty_label)

        self.card_widgets: List[DigestCardWidget] = []

        # Esik combosu ancak baslangic degeri okunduktan sonra baglanir; aksi
        # halde kurulum sirasinda bir kez bosuna kaydeder.
        index = self.threshold_combo.findData(self.quiet_threshold)
        if index < 0:
            index = self.threshold_combo.findData(DEFAULT_QUIET_THRESHOLD)
        self.threshold_combo.setCurrentIndex(max(0, index))
        self.threshold_combo.currentIndexChanged.connect(self._on_threshold_changed)

        # Canlılık: rapor izleyicisi ve posta kutusu. `mailbox_updated` sözleşmesi
        # agy ajanında; sinyal henüz yoksa guard sessizce atlar (rozet yine
        # `reports_updated` ile canlı kalır).
        bus.reports_updated.connect(self._on_reports_updated)
        self._mailbox_signal = getattr(bus, "mailbox_updated", None)
        if self._mailbox_signal is not None:
            try:
                self._mailbox_signal.connect(self._on_mailbox_updated)
            except (TypeError, RuntimeError):
                self._mailbox_signal = None

        self.set_entries([])

    # ------------------------------------------------------------ veri

    def set_entries(self, entries: Sequence[Dict[str, Any]]) -> None:
        self._entries = list(entries or [])
        self.refresh()

    def total_count(self) -> int:
        """Ekrandaki **tek** rapor sayacı (Faz 12-D.2, denetim D12-03).

        Rapor Merkezi ile okuyucu listesi eskiden iki bağımsız sayı yazıyordu
        (`662 rapor` ve `658 / 658 kayıt`): merkez posta kutusu iletilerini
        ekliyor ve arşivlenmişleri düşüyordu, liste ham künyeleri sayıyordu.
        Artık ikisi de bu sayıyı okur.
        """
        return int(self._result.get("total", 0))

    def all_entries(self) -> List[Dict[str, Any]]:
        """Kasa künyeleri + posta kutusu `report` mesajları, okundu durumu ekli."""
        merged: List[Dict[str, Any]] = []
        for entry in list(self._entries) + self._mailbox_entries():
            path = entry.get("path")
            if not path:
                continue
            state = self.store.entry(path)
            if state.get("archived"):
                continue
            item = dict(entry)
            item["read"] = bool(state.get("read", False))
            item["pinned"] = bool(state.get("pinned", False))
            merged.append(item)
        return merged

    def _mailbox_entries(self) -> List[Dict[str, Any]]:
        """
        Posta kutusu kunyeleri (onbellekli).

        `refresh()` her okundu/pin tiklamasinda kosuyor; her seferinde diski
        taramak yuzlerce dosyalik bir kutuda arayuzu takardi. Onbellek yalnizca
        `mailbox_updated` sinyaliyle bosaltilir — kutunun tek gercek kaynagi
        yine disk.
        """
        if self._mailbox_cache is None:
            self._mailbox_cache = mailbox_entries()
        return list(self._mailbox_cache)

    def unread_count(self) -> int:
        return sum(card.get("unread", 0) for card in self._result["cards"] + self._result["quiet"])

    def cards(self) -> List[Dict[str, Any]]:
        return list(self._result.get("cards", []))

    def quiet_cards(self) -> List[Dict[str, Any]]:
        return list(self._result.get("quiet", []))

    @Slot()
    def _on_show_all_clicked(self) -> None:
        """Sessiz bolumu acar ve tam listeyi isteyen sinyali yayar (Faz 8)."""
        if not self._quiet_expanded:
            self.toggle_quiet()
        self.show_all_requested.emit()

    @Slot(int)
    def _on_threshold_changed(self, _index: int) -> None:
        """Esik combosu (QObject slotu, lambda degil)."""
        value = self.threshold_combo.currentData()
        if value is None:
            return
        self.set_quiet_threshold(float(value))

    def set_quiet_threshold(self, value: float, persist: bool = True) -> None:
        # 1.0 ustu = "kapali": hicbir kume sessiz bolume dusmez.
        self.quiet_threshold = max(0.0, float(value))
        if persist:
            save_quiet_threshold(self.quiet_threshold)
        self.refresh()

    # ------------------------------------------------------------ görünüm

    #: `all_entries()` her cagrida depodan tazeledigi alanlar; onbellekten
    #: gelen zenginlestirmenin uzerine bunlar yeniden yazilir.
    VOLATILE_FIELDS = ("read", "pinned", "archived")

    def _enrich_cached(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Faz 9: `enrich_entry` sonucunu (yol, mtime) imzasiyla onbellekler.

        700 raporda zenginlestirme sicak onbellekle bile ~230 ms suruyordu;
        okundu/pin tiklamasi bunu her seferinde odetmemeli.
        """
        path = str(entry.get("path", ""))
        key = (path, float(entry.get("mtime") or 0.0))
        cached = self._enrich_cache.get(key) if path else None
        if cached is None:
            cached = enrich_entry(entry)
            if path:
                if len(self._enrich_cache) > 4000:
                    self._enrich_cache.clear()
                self._enrich_cache[key] = cached
        out = dict(cached)
        for field in self.VOLATILE_FIELDS:
            if field in entry:
                out[field] = entry[field]
        return out

    def _build_signature(self, entries) -> tuple:
        """Kume hesabinin girdi imzasi: (yol, mtime) cifti + esik."""
        return (
            round(float(self.quiet_threshold), 4),
            tuple((str(e.get("path", "")), float(e.get("mtime") or 0.0)) for e in entries),
        )

    def refresh(self) -> None:
        # Faz 9: TF-IDF kumelemesi 700 raporda ana is parcacigini ~300 ms
        # blokluyordu ve `mark_all_read` gibi YALNIZCA okundu bayragini
        # degistiren eylemlerde bile bastan kosuyordu. Kume BILESIMI girdiler
        # (yol + mtime) degismedikce ayni kalir; onu onbellege aliyoruz, kartlar
        # her seferinde taze okundu/pin durumuyla yeniden kuruluyor.
        entries = self.all_entries()
        signature = self._build_signature(entries)
        enriched = [self._enrich_cached(e) for e in entries]
        for idx, item in enumerate(enriched):
            item["_idx"] = idx
        if getattr(self, "_cluster_signature", None) == signature:
            groups = self._cluster_index
        else:
            groups = [
                [m.get("_idx", 0) for m in cluster]
                for cluster in cluster_entries(enriched, threshold=DEFAULT_CLUSTER_THRESHOLD)
            ]
            self._cluster_index = groups
            self._cluster_signature = signature
        threshold = float(self.quiet_threshold)
        cards = [
            build_digest([enriched[i] for i in group if i < len(enriched)],
                         quiet_threshold=threshold)
            for group in groups
            if group
        ]

        def _sort_key(card: Dict[str, Any]):
            newest = max((float(m.get("mtime", 0.0)) for m in card["members"]), default=0.0)
            return (not card.get("pinned"), -(card["urgency"] + card["importance"]), -newest)

        cards.sort(key=_sort_key)
        self._result = {
            "cards": [c for c in cards if not c["quiet"]],
            "quiet": [c for c in cards if c["quiet"]],
            "total": len(enriched),
            "quiet_threshold": threshold,
        }
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.card_widgets = []

        visible = list(self._result["cards"])
        if self._quiet_expanded:
            visible += list(self._result["quiet"])
        for card in visible:
            widget = DigestCardWidget(card, self)
            self.card_widgets.append(widget)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, widget)

        unread = self.unread_count()
        self.header_label.setText(
            f"<b style='color:{RT['accent']}; font-size:{BODY_PX}px;'>RAPOR MERKEZİ</b>"
            f" <span style='color:{RT['text_dim']}; font-size:{LABEL_PX}px;'>"
            f"Toplam {self._result['total']} rapor ·"
            f" {len(self._result['cards'])} öne çıkan"
            f" · {len(self._result['quiet'])} sessiz"
            + (f" · {unread} okunmadı" if unread else "") + "</span>"
        )
        quiet_count = len(self._result["quiet"])
        arrow = "▾" if self._quiet_expanded else "▸"
        self.quiet_btn.setText(
            f"{arrow} Sessiz bölüm — {quiet_count} yüksek güvenli rutin küme"
        )
        self.quiet_btn.setToolTip(
            "Güveni eşiğin üstünde olan rutin raporlar burada katlanır."
            f" Eşik (report_center_quiet_threshold): {self.quiet_threshold:.2f}"
        )
        self.quiet_btn.setVisible(quiet_count > 0)
        self.show_all_btn.setText(f"Tümü ({self._result['total']} rapor)")
        self.show_all_btn.setVisible(self._result["total"] > 0)
        if not visible and not quiet_count:
            self.empty_label.setText(
                "Rapor Merkezi boş. Bir araştırma, ofis kartı ya da /query"
                " tamamlandığında kümeler burada belirir."
            )
            self.empty_label.setVisible(True)
            self.scroll.setVisible(False)
        else:
            self.empty_label.setVisible(False)
            self.scroll.setVisible(True)
        self.mark_all_btn.setEnabled(bool(unread))
        self.unread_changed.emit(unread)

    def toggle_quiet(self) -> bool:
        self._quiet_expanded = not self._quiet_expanded
        self.refresh()
        return self._quiet_expanded

    # ------------------------------------------------------------ eylemler

    def open_card(self, card: Dict[str, Any]) -> None:
        path = str(card.get("path", ""))
        if not path:
            return
        self.store.mark_read(path, True)
        self.refresh()
        self.report_opened.emit(path)

    def ask_about_card(self, card: Dict[str, Any]) -> str:
        """Kartın ofisine revizyon/açıklama isteği gönderir, yanıtı yayar."""
        office = str(card.get("office") or "")
        if not office:
            return ""
        question = (
            f"“{card.get('title', '')}” raporunu gözden geçir:"
            " bulguları doğrula ve gerekiyorsa revizyon gönder."
        )
        handler = self.ask_handler
        answer = handler(office, question) if handler else ask_orchestrator(office, question, self.bridge)
        answer = str(answer or "")
        self.orchestrator_answer.emit(office, answer)
        return answer

    # Faz 9: asagidaki toplu eylemler tek dosya yazimi yapar (`set_many`).
    # Eskiden her yol icin ayri `save()` cagriliyordu; "Tumunu okundu say"
    # yuzlerce tam JSON yazimi uretip ana is parcacigini kilitliyordu.

    def mark_paths_read(self, paths: Iterable[str]) -> None:
        self.store.set_many(list(paths), read=True)
        self.refresh()

    def toggle_pin_paths(self, paths: Iterable[str]) -> bool:
        paths = list(paths)
        target = not all(self.store.is_pinned(p) for p in paths) if paths else False
        self.store.set_many(paths, pinned=target)
        self.refresh()
        return target

    def archive_paths(self, paths: Iterable[str]) -> None:
        self.store.set_many(list(paths), archived=True, read=True)
        self.refresh()

    def mark_all_read(self) -> None:
        paths = [
            member.get("path")
            for card in self._result["cards"] + self._result["quiet"]
            for member in card.get("members", [])
        ]
        self.store.set_many(paths, read=True)
        self.refresh()

    def prune_missing(self) -> int:
        """Diskte kalmamış raporların durum kayıtlarını siler."""
        existing = [
            e.get("path") for e in self._entries
            if e.get("path") and Path(str(e["path"])).exists()
        ]
        removed = self.store.prune(existing)
        self.refresh()
        return removed

    # ------------------------------------------------------------ sinyaller

    @Slot(str)
    def _on_reports_updated(self, _skill: str) -> None:
        # Faz 9: sinyal firtinasinda (bir gorev N rapor yazar) her seferinde
        # 703 dosyayi okumak yerine 1,5 sn birlestirme + isci is parcacigi.
        self.schedule_reload()

    @Slot(str, str)
    def _on_mailbox_updated(self, _owner_kind: str, _owner_name: str) -> None:
        self._mailbox_cache = None
        self.refresh()

    #: Kasadan tazelemede taranacak azami kunye sayisi (Faz 8).
    #: `collect_recent_entries` varsayilani 60'ti; `bus.reports_updated` her
    #: tetiklendiginde Rapor Merkezi 895 raporluk listeyi 61'e dusuruyordu —
    #: kullanicinin "toplam raporlar gorunmuyor" dedigi durumun kok nedeni.
    VAULT_RELOAD_LIMIT = 5000

    #: Sinyal birlestirme penceresi (ms).
    RELOAD_DEBOUNCE_MS = 1500

    def reload_from_vault(self) -> None:
        """Senkron tazeleme (testler ve ilk yukleme icin)."""
        from entropy.ui.widgets.report_inbox import collect_recent_entries

        self.set_entries(collect_recent_entries(limit=self.VAULT_RELOAD_LIMIT))

    def schedule_reload(self) -> None:
        """Kasadan tazelemeyi geciktirir; ana is parcacigi bloklanmaz."""
        timer = getattr(self, "_reload_timer", None)
        if timer is None:
            self.reload_from_vault()
            return
        timer.start(self.RELOAD_DEBOUNCE_MS)

    @Slot()
    def _start_background_reload(self) -> None:
        """Debounce doldu: kasa taramasini havuz is parcaciginda kosar."""
        if self._reload_running:
            # Kosan tarama bitince yeniden zamanlanir (asagida).
            self._reload_again = True
            return
        self._reload_running = True
        self._reload_again = False
        limit = self.VAULT_RELOAD_LIMIT
        widget = self

        class _ReloadJob(QRunnable):
            def run(self):  # noqa: D102 - isci is parcacigi
                from entropy.ui.widgets.report_inbox import collect_recent_entries

                try:
                    entries = collect_recent_entries(limit=limit)
                except Exception:
                    entries = None
                # Qt nesnelerine yalnizca ana is parcacigindan dokunulur.
                bus.invoke_on_main(partial(widget._apply_background_reload, entries))

        QThreadPool.globalInstance().start(_ReloadJob())

    def _apply_background_reload(self, entries) -> None:
        """Isci sonucu ana is parcaciginda uygulanir."""
        try:
            self._reload_running = False
            if entries is not None:
                self.set_entries(entries)
            if getattr(self, "_reload_again", False):
                self._reload_again = False
                self.schedule_reload()
        except RuntimeError:
            # Widget bu arada silinmis olabilir; sessizce cik.
            return

    def closeEvent(self, event):  # noqa: N802
        # Faz 8: tekrarli kapanislarda ayni sinyali yeniden cozmek
        # libpyside'in "Failed to disconnect" uyarisini basiyordu.
        if not getattr(self, "_bus_connected", True):
            super().closeEvent(event)
            return
        self._bus_connected = False
        try:
            bus.reports_updated.disconnect(self._on_reports_updated)
        except (TypeError, RuntimeError):
            pass
        if self._mailbox_signal is not None:
            try:
                self._mailbox_signal.disconnect(self._on_mailbox_updated)
            except (TypeError, RuntimeError):
                pass
        super().closeEvent(event)
