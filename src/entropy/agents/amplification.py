"""
Öz-amplifikasyon kilidi (Faz 11.6) — araştırma kartlarının üç kapısı.

Sorun
-----
Otonom araştırma döngüsü kendi çıktısını yeniden keşfetmeye meyillidir:
zamanlanmış görev her on dakikada aynı konuyu araştırır, ajan bir önceki
raporunu okur, "yeni" bulgu diye geri yazar ve hafıza kendi yankısıyla şişer
(Manufactured Confidence). Ölçülen sonuç: 1.544 düğümün yarısından çoğu yakın
kopya. Bu modül o döngüyü üç yerden keser:

1. **AÇIK TESPİTİ** (`brain_lookup`) — koşudan ÖNCE. **Faz 13-A2'de
   varsayılan KAPATILDI** (`config.brain_shortcut_enabled = False`).
   Gerçek ekranda ölçülen hata: kullanıcı "araştırma yap" dedi, kart
   `kind=research` oldu ve 0,49 güvenle "beyinden yanıtlandı" diye kapandı —
   gösterilen "yanıt" Entropy'nin KİMLİK düğümüydü. Kullanıcının bağlayıcı
   kuralı: "araştır" dendiğinde araştırma CANLI koşar; beyin ajana
   **bağlamdır**, araştırmanın yerine geçmez. Artık bulunan bilgi isteme
   `[BEYİN]` bölümü olarak girer; kart CLI'ya gider. Kısa devre yalnızca
   açık tercihle (`brain_only`) ve yüksek eşikle (0,75, kaynaklı, kimlik
   dışı) açılır ve kart özetinde "canlı araştırma yapılmadı" yazar.
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

# Kartın niteliği: `TaskCard.kind` alanının sözleşmesi (Faz 12 kapanışı).
# Faz 13-A2: `kind` artık kısa devreyi BELİRLEMEZ (dört kartın dördü de CLI'ya
# gider); yönlendirme, istem şablonu ve yenilik kotası için tutulur.
CARD_KINDS = ("research", "write", "code", "ops")
#: `kind` hiçbir sezgiye takılmazsa yazılan değer. `write` seçilmesi bilinçli:
#: kısayol açmaz (yanlış pozitif riski yok) ama beyin paketini isteme sokar.
DEFAULT_KIND = "write"

# Kartın araştırma niteliği: açık `kind` alanı.
RESEARCH_KINDS = ("research", "arastirma", "araştırma", "arastırma", "survey")

# Başlık/hedef sezgisi — `kind` yazılmamış kartlar için. ARAŞTIRMA fiilleri
# ÖNCE bakılır: "X'i araştır ve raporu yaz" bir araştırma kartıdır. Eski sıra
# tersti ve `_WRITE_HINTS` ("yaz ") araştırma kartlarını geri çekiyordu; canlı
# ölçümde dört kartta `brain_lookup` yanıt bulmuşken CLI yine de koştu.
_RESEARCH_HINTS = (
    "araştır", "arastir", "araştırma", "arastirma", "research",
    "kaynak topla", "literatür", "literatur", "son gelişme", "son gelismeler",
    "web taraması", "web taramasi", "survey", "investigate", "piyasa analizi",
    "incele ve raporla", "karşılaştır", "karsilastir",
    # Faz 13-A2: "incele" ve "tara" tek başlarına da araştırma fiilidir
    # ("piyasayı tara", "raporu incele"); eskiden yalnızca birleşik kalıp
    # ("incele ve raporla") yakalanıyordu.
    "incele", "tara", "taraması yap", "taramasi yap",
)
# KOD fiilleri: kartı kesinlikle CLI'ya götürür (kısayol yok).
_CODE_HINTS = ("kodla", "uygula", "düzelt", "duzelt", "refactor", "test ekle",
               "implement", "fix ", "hata ayıkla", "hata ayikla", "yama",
               "modül yaz", "modul yaz", "fonksiyon", "sınıf ekle", "sinif ekle")
# OPS fiilleri: kurulum/dağıtım/izleme.
_OPS_HINTS = ("kur ", "kurulum", "dağıt", "dagit", "deploy", "build", "derle",
              "yayınla", "yayinla", "izle", "yedek", "geri yükle", "geri yukle",
              "sürüm çıkar", "surum cikar")
# YAZI fiilleri: metin üretimi (rapor, özet, çeviri, damıtma).
_WRITE_HINTS = ("yaz ", "yaz.", "yazı", "yazi", "özetle", "ozetle", "özet",
                "ozet", "rapor", "taslak", "çevir", "cevir", "damıt", "damit",
                "metin", "makale", "içerik", "icerik", "belge")


def infer_kind(title: str = "", goal: str = "") -> str:
    """
    Başlık + hedeften kart niteliğini sezer (`research|write|code|ops`).

    Sıra sabittir ve anlamlıdır: research → code → ops → write. "Araştır ve
    raporu yaz" araştırmadır; "panoyu kodla, dispatcher yaz" koddur. Hiçbiri
    tutmazsa `DEFAULT_KIND` döner — sezgi ASLA boş bırakmaz, çünkü boş `kind`
    her okuyucuda yeniden sezgiye düşüyordu.
    """
    text = f" {title or ''} {goal or ''} ".lower()
    if not text.strip():
        return DEFAULT_KIND
    if any(h in text for h in _RESEARCH_HINTS):
        return "research"
    if any(h in text for h in _CODE_HINTS):
        return "code"
    if any(h in text for h in _OPS_HINTS):
        return "ops"
    if any(h in text for h in _WRITE_HINTS):
        return "write"
    return DEFAULT_KIND


def card_kind(card: Any) -> str:
    """Kartın niteliği: açık `kind` alanı, yoksa sezgi. Boş DÖNMEZ."""
    kind = str(getattr(card, "kind", "") or "").strip().lower()
    if kind:
        return "research" if kind in RESEARCH_KINDS else kind
    return infer_kind(getattr(card, "title", "") or "",
                      getattr(card, "goal", "") or "")

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

    Sıra: (1) açık `kind` alanı, (2) başlık + hedef sezgisi (`infer_kind`).
    Açık alan sezgiyi EZER: `kind="build"` yazılmış bir kart başlığında
    "araştır" geçse de araştırma sayılmaz.
    """
    return card_kind(card) == "research"


def has_sources(text: str) -> bool:
    """Metin en az bir URL ya da dosya yolu gösteriyor mu?"""
    body = text or ""
    return bool(_URL_RE.search(body) or _PATH_RE.search(body))


# ---------------------------------------------------------------------------
# 1. Açık tespiti
# ---------------------------------------------------------------------------

# Faz 13-A2 — AÇIK TERCİHLİ KISA DEVRE EŞİĞİ. Otomatik kısayol kapandı
# (`config.brain_shortcut_enabled = False`); kullanıcı açıkça "yalnız beyin"
# dediğinde bile eşik CRAG eşiğinden (0,40) çok daha yüksek tutulur, çünkü
# burada verilen karar "canlı araştırma HİÇ yapılmasın" kararıdır.
SHORTCUT_MIN_CONFIDENCE = 0.75

#: Kartta ya da istekte "yalnız beyinden yanıtla" işareti. Kart alanı
#: (`card.brain_only`) birinci kaynaktır; metindeki işaret `/task --brain-only`
#: gibi kullanıcı yazımlarını da yakalar.
BRAIN_ONLY_MARKERS = (
    "--brain-only", "[brain-only]", "brain_only", "brain-only",
    "yalnız beyin", "yalniz beyin", "sadece beyin", "sadece hafıza",
    "sadece hafiza",
)


def brain_only_requested(card: Any = None, query: str = "") -> bool:
    """
    Kullanıcı bu iş için AÇIKÇA "yalnız beyinden yanıtla" dedi mi?

    Varsayılan **hayır**: kullanıcının bağlayıcı kuralı, "araştır" dendiğinde
    araştırmanın CANLI koşmasıdır. Kısa devre yalnız burada True dönerse
    açılır.
    """
    if card is not None:
        value = getattr(card, "brain_only", None)
        if isinstance(value, bool):
            if value:
                return True
        elif isinstance(value, str) and value.strip().lower() in ("1", "true", "evet", "yes"):
            return True
    text = " ".join(str(part or "") for part in (
        query,
        getattr(card, "title", "") if card is not None else "",
        getattr(card, "goal", "") if card is not None else "",
    )).lower()
    return any(marker in text for marker in BRAIN_ONLY_MARKERS)


def _shortcut_enabled() -> bool:
    """`config.brain_shortcut_enabled` — Faz 13-A2'den beri varsayılan KAPALI."""
    try:
        from entropy.core.config import config as _config

        return bool(getattr(_config, "brain_shortcut_enabled", False))
    except Exception:
        return False


@dataclass
class BrainAnswer:
    """
    `brain_lookup` sonucu.

    Faz 13-A2'de anlamı KESKİNLEŞTİ: `has_answer` artık "beyinde bir şey
    bulundu" değil, **"bu kart canlı koşmadan kapatılabilir"** demektir.
    Çağıran (`TaskBoard._brain_shortcut`) tek bu alana bakıyor; bulunan bilgi
    kısa devre açılmadığında da KAYBOLMAZ, `prompt_section()` ile isteme
    `[BEYİN]` bölümü olarak girer. `brain_hit`/`confidence` ham sinyali taşır
    (ölçüm ve günlük için).
    """

    has_answer: bool = False
    confidence: float = 0.0
    text: str = ""
    sources: List[str] = field(default_factory=list)
    #: Ham CRAG sinyali: beyinde eşiği geçen bir karşılık var mı?
    brain_hit: bool = False
    #: Kısa devre neden açılmadı (insan okur; boş = açıldı ya da sinyal yok).
    shortcut_reason: str = ""

    def prompt_section(self) -> str:
        """
        İsteme giren `[BEYİN]` bölümü — Faz 13-A2'den beri NORMAL yol.

        Kart türü ne olursa olsun (research dâhil) beyin cevabı kartı
        kapatmaz; CLI turunu KISALTIR: ajan aynı bilgiyi yeniden aramak
        yerine hazır, kaynaklı paketle başlar ve doğrular. Boş yanıtta boş
        dize döner (istem kirlenmesin).
        """
        body = (self.text or "").strip()
        if not body:
            return ""
        head = (f"[BEYİN]\nHafızamdan bu görev için hazır bulunan bilgi "
                f"(güven {self.confidence:.2f}). BAĞLAMDIR, yanıt değildir: "
                f"doğrula, güncelliğini sınayıp KULLAN. Araştırma isteniyorsa "
                f"bu paket canlı araştırmanın yerine GEÇMEZ:")
        tail = ""
        if self.sources:
            tail = "\nKaynaklar: " + ", ".join(str(s) for s in self.sources[:10])
        return f"{head}\n\n{body}{tail}"

    def note(self) -> str:
        """
        Kart özetine yazılacak insan okur metin — kısa devre AÇIKÇA yazılır.

        Faz 13-A2: kullanıcı sohbet kartında "canlı araştırma yapılmadı"
        cümlesini görmeden bu kapanışı ayırt edemiyordu.
        """
        return (
            f"Beyinden yanıtlandı — CANLI ARAŞTIRMA YAPILMADI "
            f"(açık tercih: yalnız beyin; güven {self.confidence:.2f}). "
            f"Bu yanıt hafızadaki kayıtlardan derlendi, web/CLI turu "
            f"açılmadı; tazelik gerekiyorsa kartı 'yalnız beyin' işareti "
            f"olmadan yeniden aç.\n\n"
            + (self.text or "")
        )


def brain_lookup(query: str, builder: Any = None, card: Any = None) -> BrainAnswer:
    """
    Beyinden bu iş için bağlam toplar; kısa devreye YALNIZCA açık tercihle izin verir.

    Faz 13-A2 (kullanıcı geri bildirimi, bağlayıcı): "araştır" dendiğinde
    araştırma canlı koşar. Bu yüzden dönen `has_answer` artık ham CRAG
    sinyali değil, şu beş koşulun BİRLİKTE sağlanmasıdır:

    1. Açık tercih: kartta `brain_only` (ya da metinde `--brain-only`), veya
       `config.brain_shortcut_enabled` açıksa `kind="research"` kartı.
    2. Beyinde eşiği geçen bir karşılık var (`ctx.brain_has_answer`) —
       kimlik (`identity:core`) ve `legacy:pre-v2` düğümleri bu skora
       KATILMAZ (`context_builder.is_answer_node`).
    3. Güven ≥ `SHORTCUT_MIN_CONFIDENCE` (0,75).
    4. Yanıt metni boş değil.
    5. Yanıt KAYNAKLI (URL ya da dosya yolu gösteriyor).

    Koşullar sağlanmasa da `text` doldurulur: çağıran onu `prompt_section()`
    ile isteme `[BEYİN]` bölümü olarak koyar. `builder`/`card` testler için
    enjekte edilebilir. Hafıza katmanı yoksa ya da hata verirse "yanıt yok"
    döner — kilit ASLA bir kartı yanlışlıkla kapatmamalı.
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
    sources = list(getattr(ctx, "sources", []) or [])
    answer = BrainAnswer(has_answer=False, confidence=conf, text=body,
                         sources=sources, brain_hit=bool(has))
    answer.has_answer, answer.shortcut_reason = _shortcut_decision(
        answer, card=card, query=text)
    return answer


def _shortcut_decision(answer: BrainAnswer, card: Any = None,
                       query: str = "") -> Tuple[bool, str]:
    """Kısa devre açılsın mı? (True, "") ya da (False, gerekçe)."""
    explicit = brain_only_requested(card, query)
    if not explicit:
        if not _shortcut_enabled():
            return False, ("otomatik kısa devre kapalı; araştırma canlı koşar "
                           "(beyin yalnızca bağlam)")
        if card is not None and not is_research_card(card):
            return False, "araştırma kartı değil"
    if not answer.brain_hit:
        return False, "beyinde eşiği geçen karşılık yok"
    if answer.confidence < SHORTCUT_MIN_CONFIDENCE:
        return False, (f"güven {answer.confidence:.2f} < "
                       f"{SHORTCUT_MIN_CONFIDENCE:.2f}")
    if not (answer.text or "").strip():
        return False, "beyin paketi boş"
    if not (has_sources(answer.text) or answer.sources):
        return False, "yanıt kaynaksız (URL ya da dosya yolu yok)"
    return True, ""


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
    "MIN_NOVELTY_RATIO", "RESEARCH_KINDS", "CARD_KINDS", "DEFAULT_KIND",
    "SHORTCUT_MIN_CONFIDENCE", "BRAIN_ONLY_MARKERS", "brain_only_requested",
    "infer_kind", "card_kind", "BrainAnswer", "NoveltyReport",
    "LockOutcome", "is_research_card", "has_sources", "brain_lookup",
    "split_claims", "admit_report", "topic_tokens", "same_topic",
    "stop_scheduled_research", "apply_report_lock",
]
