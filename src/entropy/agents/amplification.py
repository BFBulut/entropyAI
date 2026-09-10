"""
Öz-amplifikasyon kilidi (Faz 11.6) — araştırma kartlarının üç kapısı.

Sorun
-----
Otonom araştırma döngüsü kendi çıktısını yeniden keşfetmeye meyillidir:
zamanlanmış görev her on dakikada aynı konuyu araştırır, ajan bir önceki
raporunu okur, "yeni" bulgu diye geri yazar ve hafıza kendi yankısıyla şişer
(Manufactured Confidence). Ölçülen sonuç: 1.544 düğümün yarısından çoğu yakın
kopya. Bu modül o döngüyü üç yerden keser:

1. **AÇIK TESPİTİ** (`brain_lookup`) — koşudan ÖNCE. Beyinde (L2/L3) yeterli
   güvende bir yanıt varsa (`AssembledContext.brain_has_answer`, CRAG eşiği
   0.45) kart CLI'ya HİÇ gitmez; "beyinden yanıtlandı" notuyla `review`e düşer.
   Kota harcamayan tek doğru cevap budur.
2. **YENİLİK KOTASI** (`admit_report`) — koşudan SONRA. Rapor hafızaya
   `MemoryGate`ten geçerken ADD/NOOP/gri sayılır; ADD oranı %30'un altındaysa
   tur yinelenen araştırmadır. Kart notuna "düşük yenilik" yazılır ve AYNI
   konudaki **zamanlanmış** görev durdurulur (`stop_scheduled_research`) —
   yoksa aynı boş tur on dakikada bir sonsuza dek koşar.
3. **KAYNAK ZORUNLULUĞU** (`has_sources`) — rapor bir URL ya da dosya yolu
   göstermiyorsa L2 (semantic) yazımı hiç denenmez. Kapı zaten reddederdi
   (`gate.py`: "L2 anlamsal yazımda kaynak yok"); burada erken kesilmesinin
   nedeni kullanıcıya NEDENİNİ yazabilmek.

Bağımlılık yönü
---------------
Hafıza katmanı (`entropy.memory.*`) burada **isteğe bağlıdır**: her çağrı
korumalı içe aktarma ardında. Ajan katmanı hafızaya bağımlı olamaz — kart, kapı
yokken de doğru biçimde kapanmalı.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ADD oranı bu eşiğin altındaysa tur "düşük yenilik" sayılır. K8 hedefi
# "yazılanın ≥ %70'i yeni olsun"du; kilit onun tersi yönden okunuşudur.
MIN_NOVELTY_RATIO = 0.30

# Kartın araştırma niteliği: açık `kind` alanı.
RESEARCH_KINDS = ("research", "arastirma", "araştırma", "arastırma", "survey")

# Başlık/hedef sezgisi — `kind` yazılmamış kartlar için. Yalnızca ARAŞTIRMA
# fiilleri; "kodu incele" gibi geliştirme kartlarını yakalamamak için "incele"
# tek başına yeterli sayılmaz (aşağıdaki `_WRITE_HINTS` onu geri çeker).
_RESEARCH_HINTS = (
    "araştır", "arastir", "araştırma", "arastirma", "research",
    "kaynak topla", "literatür", "literatur", "son gelişme", "son gelismeler",
    "web taraması", "web taramasi", "survey", "investigate", "piyasa analizi",
)
_WRITE_HINTS = ("kodla", "uygula", "yaz ", "düzelt", "duzelt", "refactor",
                "test ekle", "implement", "fix ")

# Kaynak işareti: URL ya da dosya yolu. Rapor metninde bunlardan biri yoksa
# "kaynak" iddiası doğrulanamaz.
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/][^\s`'\"]+|(?:\.{1,2})?[\\/][^\s`'\"]{2,}"
    r"|[\w.\-]+[\\/][\w.\-][^\s`'\"]*\.[A-Za-z0-9]{1,6})"
)


def is_research_card(card: Any) -> bool:
    """
    Kart araştırma niteliğinde mi?

    Sıra: (1) açık `kind` alanı, (2) başlık + hedef sezgisi. Sezgi bilinçli
    olarak DAR: yanlış pozitif, bir geliştirme kartını beyin cevabıyla
    kapatmak demekti.
    """
    kind = str(getattr(card, "kind", "") or "").strip().lower()
    if kind:
        return kind in RESEARCH_KINDS
    text = f"{getattr(card, 'title', '') or ''} {getattr(card, 'goal', '') or ''}".lower()
    if not text.strip():
        return False
    if any(h in text for h in _WRITE_HINTS):
        return False
    return any(h in text for h in _RESEARCH_HINTS)


def has_sources(text: str) -> bool:
    """Metin en az bir URL ya da dosya yolu gösteriyor mu?"""
    body = text or ""
    return bool(_URL_RE.search(body) or _PATH_RE.search(body))


# ---------------------------------------------------------------------------
# 1. Açık tespiti
# ---------------------------------------------------------------------------

@dataclass
class BrainAnswer:
    """`brain_lookup` sonucu. `has_answer` False ise koşu normal ilerler."""

    has_answer: bool = False
    confidence: float = 0.0
    text: str = ""
    sources: List[str] = field(default_factory=list)

    def note(self) -> str:
        """Kart özetine yazılacak insan okur metin."""
        return (
            f"Beyinden yanıtlandı (güven {self.confidence:.2f} ≥ CRAG eşiği): "
            f"bu soru için hafızada yeterli yanıt var, CLI turu açılmadı.\n\n"
            + (self.text or "")
        )


def brain_lookup(query: str, builder: Any = None) -> BrainAnswer:
    """
    Beyinde bu soruya yeterli yanıt var mı (CRAG sinyali).

    `builder` testler için enjekte edilebilir; verilmezse
    `entropy.memory.context_builder` kullanılır. Hafıza katmanı yoksa ya da
    hata verirse "yanıt yok" döner — kilit ASLA bir kartı yanlışlıkla
    kapatmamalı.
    """
    text = (query or "").strip()
    if not text:
        return BrainAnswer()
    try:
        if builder is None:
            from entropy.memory.context_builder import (  # type: ignore
                CognitiveContextBuilder,
            )

            builder = CognitiveContextBuilder()
        ctx = builder.build(text)
    except Exception:
        logger.debug("Beyin sorgusu yapılamadı", exc_info=True)
        return BrainAnswer()
    try:
        has = bool(getattr(ctx, "brain_has_answer", False))
        conf = float(getattr(ctx, "brain_confidence", 0.0) or 0.0)
        body = ""
        for attr in ("recall_text", "memory_text", "text"):
            value = getattr(ctx, attr, "")
            if isinstance(value, str) and value.strip():
                body = value.strip()
                break
        if not body:
            render = getattr(ctx, "render", None)
            if callable(render):
                body = str(render() or "").strip()
    except Exception:
        return BrainAnswer()
    return BrainAnswer(has_answer=has, confidence=conf, text=body,
                       sources=list(getattr(ctx, "sources", []) or []))


# ---------------------------------------------------------------------------
# 2. Yenilik kotası
# ---------------------------------------------------------------------------

@dataclass
class NoveltyReport:
    """Bir raporun kapıdan geçişinin sayımı."""

    add: int = 0
    noop: int = 0
    gray: int = 0
    supersede: int = 0
    reject: int = 0
    skipped_reason: str = ""

    @property
    def total(self) -> int:
        return self.add + self.noop + self.gray + self.supersede + self.reject

    @property
    def ratio(self) -> float:
        return (self.add / self.total) if self.total else 0.0

    @property
    def low_novelty(self) -> bool:
        """Kota altında mı? (Hiç aday yoksa 'düşük' denmez: ölçüm yok demektir.)"""
        return bool(self.total) and self.ratio < MIN_NOVELTY_RATIO

    def note(self) -> str:
        if self.skipped_reason:
            return f"Hafızaya yazılmadı: {self.skipped_reason}"
        return (
            f"Yenilik: {self.add}/{self.total} yeni (%{self.ratio * 100:.0f}), "
            f"{self.noop} yinelenen, {self.gray} gri bant"
            + (" — DÜŞÜK YENİLİK" if self.low_novelty else "")
        )


def split_claims(text: str, max_claims: int = 12) -> List[str]:
    """
    Raporu kapıya verilecek adaylara böler.

    Madde işaretleri ve paragraflar; başlıklar ve çok kısa satırlar atılır.
    Tek bir dev blok olarak yazmak kapının benzerlik ölçümünü anlamsız
    kılıyordu (her rapor kendi başına eşsiz görünür).
    """
    claims: List[str] = []
    for raw in re.split(r"\n\s*\n|\n(?=[-*•]\s)", text or ""):
        line = " ".join(raw.split())
        line = re.sub(r"^[-*•]\s*", "", line)
        if len(line) < 40 or line.startswith("#"):
            continue
        claims.append(line[:1200])
        if len(claims) >= max_claims:
            break
    return claims


def admit_report(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    provenance: str = "",
    gate: Any = None,
    memory: Any = None,
    category: str = "semantic",
) -> NoveltyReport:
    """
    Rapor içeriğini `MemoryGate`ten geçirir ve ADD/NOOP/gri sayımını döndürür.

    Kaynak yoksa kapı hiç çağrılmaz (`skipped_reason`). `gate`/`memory`
    testlerde enjekte edilir; üretimde `CognitiveMemorySystem` + `MemoryGate`
    kullanılır. Kapı yoksa boş rapor döner — kart yine de kapanır.
    """
    report = NoveltyReport()
    body = (text or "").strip()
    if not body:
        report.skipped_reason = "rapor boş"
        return report
    if not has_sources(body):
        # KAYNAK ZORUNLULUĞU: sistemin kendi önceki çıktısı kaynak değildir.
        report.skipped_reason = (
            "kaynak yok (rapor hiçbir URL ya da dosya yolu göstermiyor); "
            "L2 anlamsal yazım yapılmadı"
        )
        return report
    try:
        if gate is None:
            from entropy.memory.gate import MemoryGate  # type: ignore

            if memory is None:
                from entropy.memory.supabase.cognitive_memory import (  # type: ignore
                    CognitiveMemorySystem,
                )

                memory = CognitiveMemorySystem()
            gate = MemoryGate(memory)
    except Exception:
        logger.debug("Hafıza kapısı yüklenemedi", exc_info=True)
        report.skipped_reason = "hafıza kapısı yok"
        return report

    meta = dict(metadata or {})
    for claim in split_claims(body):
        try:
            decision = gate.admit(category, claim, metadata=meta, provenance=provenance)
        except Exception:
            logger.debug("Kapı adayı değerlendiremedi", exc_info=True)
            continue
        action = str(getattr(decision, "action", "") or "").lower()
        if action in ("add", "gray", "supersede") and memory is not None:
            # KAPI İKİ KEZ KOŞMAZ (Faz 11 kapanışı): karar YUKARIDA alındı.
            # `record_memory` çağrısı aynı adayı kapıdan bir kez daha geçirip
            # gömmeyi yeniden hesaplıyor ve kapı sayaçlarını ikinci kez
            # artırıyordu. `store_decision` kararı olduğu gibi yazar (vektör
            # karardan gelir). Eski hafıza nesneleri için `record_memory`
            # yedeği korunur.
            store = getattr(memory, "store_decision", None)
            if callable(store):
                try:
                    store(decision, importance=getattr(decision, "importance", None))
                except Exception:
                    logger.debug("Hafızaya yazılamadı", exc_info=True)
            else:
                record = getattr(memory, "record_memory", None)
                if callable(record):
                    try:
                        record(category, claim, metadata=meta, provenance=provenance)
                    except TypeError:
                        try:
                            record(category, claim)
                        except Exception:
                            logger.debug("Hafızaya yazılamadı", exc_info=True)
                    except Exception:
                        logger.debug("Hafızaya yazılamadı", exc_info=True)
        if action == "add":
            report.add += 1
        elif action == "noop":
            report.noop += 1
        elif action == "gray":
            report.gray += 1
        elif action == "supersede":
            report.supersede += 1
        elif action == "reject":
            report.reject += 1
    return report


# ---------------------------------------------------------------------------
# 3. Zamanlanmış araştırmanın durdurulması
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "için", "icin", "ile", "ve", "veya", "bir", "bu", "şu", "the", "and", "for",
    "araştır", "arastir", "araştırma", "arastirma", "research", "raporu", "rapor",
    "son", "yeni", "hakkında", "hakkinda", "üzerine", "uzerine", "about",
}


def topic_tokens(text: str) -> List[str]:
    """Konu anahtarları: 4+ harfli, durak sözcük olmayan kelimeler."""
    words = re.split(r"[^\wğüşıöçĞÜŞİÖÇ]+", (text or "").lower())
    return [w for w in words if len(w) >= 4 and w not in _STOPWORDS]


# Gövde uzunluğu: Türkçe eklemeli bir dil ve "veritabanlarını" ile "veritabanı"
# tam eşleşmiyor. Kaba ama ucuz kök: ilk N harf. Kısa tutmak yanlış eşleşme
# (yanlışlıkla ilgisiz bir görevi durdurmak) üretirdi.
_STEM_LEN = 6


def _stem(word: str) -> str:
    return word[:_STEM_LEN]


def same_topic(a: str, b: str, min_overlap: int = 2) -> bool:
    """İki metin aynı konuyu mu anlatıyor (anahtar kelime kökü örtüşmesi)."""
    ta = {_stem(w) for w in topic_tokens(a)}
    tb = {_stem(w) for w in topic_tokens(b)}
    if not ta or not tb:
        return False
    overlap = len(ta & tb)
    return overlap >= min(min_overlap, min(len(ta), len(tb)))


def stop_scheduled_research(topic: str, scheduler: Any = None) -> List[str]:
    """
    Aynı konudaki ZAMANLANMIŞ görevleri kapatır; kapatılanların adlarını döndürür.

    Görev SİLİNMEZ, yalnızca `enabled=False` yapılır: kullanıcı isterse geri
    açabilmeli ve "on dakikada bir araştır" görevinin ne olduğunu görebilmeli.
    """
    stopped: List[str] = []
    try:
        if scheduler is None:
            from entropy.scheduler.cron_engine import TaskScheduler  # type: ignore

            scheduler = TaskScheduler.get_instance()
        tasks = list(getattr(scheduler, "tasks", {}).values())
    except Exception:
        logger.debug("Zamanlayıcı okunamadı", exc_info=True)
        return stopped
    for task in tasks:
        if not getattr(task, "enabled", True):
            continue
        haystack = f"{getattr(task, 'name', '')} {getattr(task, 'prompt', '')}"
        if not same_topic(topic, haystack):
            continue
        disable = getattr(scheduler, "disable_task", None)
        try:
            if callable(disable):
                disable(task.id, reason="düşük yenilik (öz-amplifikasyon kilidi)")
            else:
                task.enabled = False
        except Exception:
            logger.debug("Zamanlanmış görev durdurulamadı: %s", getattr(task, "id", "?"),
                         exc_info=True)
            continue
        stopped.append(str(getattr(task, "name", "") or task.id))
    return stopped


# ---------------------------------------------------------------------------
# Karta uygulanan tam kilit
# ---------------------------------------------------------------------------

@dataclass
class LockOutcome:
    """`apply_report_lock` sonucu — kart notuna ve bildirime giden tek yük."""

    novelty: NoveltyReport = field(default_factory=NoveltyReport)
    stopped_tasks: List[str] = field(default_factory=list)

    @property
    def note(self) -> str:
        text = self.novelty.note()
        if self.stopped_tasks:
            text += (" · Zamanlanmış araştırma durduruldu: "
                     + ", ".join(self.stopped_tasks))
        return text


def apply_report_lock(
    card: Any,
    text: str,
    gate: Any = None,
    memory: Any = None,
    scheduler: Any = None,
    notify: bool = True,
) -> Optional[LockOutcome]:
    """
    Araştırma kartının raporuna yenilik kotasını + kaynak kuralını uygular.

    Araştırma kartı değilse None döner (çağıran hiçbir şey yapmaz). Düşük
    yenilikte aynı konudaki zamanlanmış görev durdurulur ve
    `bus.task_notification` ile kullanıcıya bildirilir.
    """
    if not is_research_card(card):
        return None
    title = str(getattr(card, "title", "") or "")
    goal = str(getattr(card, "goal", "") or "")
    meta = {
        "task_id": str(getattr(card, "id", "") or ""),
        "skill": str(getattr(card, "skill", "") or ""),
    }
    report_path = str(getattr(card, "report_path", "") or "")
    if report_path:
        meta["report_path"] = report_path
    # KAYNAK (QA 11-C/D). `provenance` hiç geçilmiyordu: kapı her L2 adayını
    # "L2 anlamsal yazımda kaynak (provenance) yok" ile REDDEDİYOR, böylece
    # araştırma raporu hafızaya HİÇ girmiyor ve yenilik oranı her turda 0/N
    # çıkıyordu (her araştırma kartı "DÜŞÜK YENİLİK" damgası yiyor, aynı
    # konudaki zamanlanmış görev haksız yere kapatılıyordu). Kartın raporu
    # kaynağın kendisidir.
    outputs = list(getattr(card, "output_paths", None) or [])
    provenance = report_path or (str(outputs[0]) if outputs else "")
    if not provenance:
        card_id = str(getattr(card, "id", "") or "")
        provenance = f"card:{card_id}" if card_id else ""
    novelty = admit_report(text, metadata=meta, provenance=provenance,
                           gate=gate, memory=memory)
    outcome = LockOutcome(novelty=novelty)
    if novelty.low_novelty:
        outcome.stopped_tasks = stop_scheduled_research(f"{title} {goal}",
                                                        scheduler=scheduler)
    if notify and (novelty.low_novelty or novelty.skipped_reason):
        _notify(card, outcome)
    return outcome


def _notify(card: Any, outcome: LockOutcome) -> None:
    """Kullanıcıya bildirim (`task_notification`) — arayüzün sözleşmesi."""
    try:
        from entropy.core.event_bus import bus

        bus.task_notification.emit(
            str(getattr(card, "id", "") or ""),
            "Öz-amplifikasyon kilidi",
            outcome.note,
        )
    except Exception:
        logger.debug("Kilit bildirimi yayılamadı", exc_info=True)


__all__ = [
    "MIN_NOVELTY_RATIO", "RESEARCH_KINDS", "BrainAnswer", "NoveltyReport",
    "LockOutcome", "is_research_card", "has_sources", "brain_lookup",
    "split_claims", "admit_report", "topic_tokens", "same_topic",
    "stop_scheduled_research", "apply_report_lock",
]
