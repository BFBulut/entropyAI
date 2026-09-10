"""
Görev kartları: kasadaki markdown dosyaları hem panonun hem ajanların kaynağı.

Kart neden dosya: Entropy bir işi ajana devretmek istediğinde kart yazabilmeli,
kullanıcı Obsidian'da düzenleyebilmeli ve iki taraf da aynı gerçeği görmeli.
Uygulama içi bir kuyruk bunların hiçbirini vermezdi.

Dosya biçimi `<kasa>/Entropy/Tasks/<id>.md`:

    ---
    id: 20260909-1432-rapor
    title: Sprint raporu
    status: backlog
    agent: yazar
    provider: agy
    model: ""
    skill: research
    created_at: 2026-09-09T14:32:00
    ...
    ---
    ## Hedef
    ...
    ## Kabul ölçütleri
    - ...
    ## Notlar
    ## Sonuç

Yaşam döngüsü: backlog → running → review (başarısızsa failed) → done.
"review"de durur, "done" bilinçli bir insan onayıdır: ajan çıktısını kimse
okumadan "bitti" saymak, panonun tamamını anlamsız kılardı.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional

from entropy.core import paths as _paths

from entropy.agents import board_fsm as _board_fsm
from entropy.agents.mailbox import emit_terminal
from entropy.agents.registry import (
    AgentRegistry,
    default_provider,
    parse_frontmatter,
    render_frontmatter,
)

TASKS_SUBDIR = "Entropy/Tasks"

# Faz 9 / B-9.2 — kart deposu ikiye ayrıldı. Entropy'nin KENDİ kartları
# `Entropy/Tasks` altında kalır; ofis kartları ofisin kendi kasasında,
# Desk ofis kökündeki `<ofis>/cards/` altında durur. Ayrım eskiden yalnızca
# kart ön bilgisindeki `office:` alanındaydı; aynı klasörde durdukları için
# Obsidian'da, yedeklemede ve panolarda iki dünya karışıyordu.
DESK_OFFICES_SUBDIR = _paths.DESK_SUBDIR
OFFICE_CARDS_DIRNAME = "cards"

# Taşıma günlüğü: geri alınabilirlik için her taşınan kartın eski/yeni yolu.
MIGRATION_LOG_SUBPATH = _paths.MIGRATION_LOG_SUBPATH

# `list(office=ALL_CARDS)` iki kökü de tarar. Varsayılan (`office=None`)
# YALNIZCA Entropy kartlarını döndürür: Entropy'nin panosu ofis kartlarını
# kendi işi sanmasın diye süzme artık depo düzeyinde.
ALL_CARDS = "*"

# Faz 11-C: durum kümesi ve geçerli geçişler tek kaynaktan (`board_fsm`) gelir.
# Buradaki ad geriye uyumluluk içindir: onlarca çağıran `tasks.STATUSES` diyor.
STATUSES = _board_fsm.STATUSES

# Kart gövdesindeki bölüm başlıkları; ayrıştırma ve üretme aynı listeyi kullanır.
SECTION_GOAL = "Hedef"
SECTION_CRITERIA = "Kabul ölçütleri"
SECTION_NOTES = "Notlar"
SECTION_RESULT = "Sonuç"

# Alt kart adım tavanı. agy'de adım/tur sayısını sınırlayan bir CLI bayrağı YOK
# (`agy -p --help`: yalnızca --effort ve --print-timeout), bu yüzden sınır
# prompt sözleşmesiyle konuyor.
MAX_STEPS_PER_CARD = 20

# Alt kart istemine giren proje dosya listesi tavanı (Faz 7 / C2d).
PROJECT_FILE_LIST_LIMIT = 40

COST_DISCIPLINE = (
    "[MALİYET DİSİPLİNİ]\n"
    "- Yalnızca sana verilen dosyaları ve yolları oku; deponun tamamını tarama, "
    "geniş `grep`/`glob` gezintisi yapma.\n"
    f"- En çok {MAX_STEPS_PER_CARD} araç adımı kullan; ölçütleri karşıladığında dur.\n"
    "- Aynı dosyayı ikinci kez okuma; gerekli bilgiyi ilk okumada çıkar.\n"
    "- Bilgi eksikse tahmin üretme, 'yapılamadı: <neden>' yaz."
)

# Faz 10-A — işçi disiplini. Üç blok da SATIR BAŞINDA köşeli etiketle yazılır;
# harness çıktıdan bunları ayrıştırıp kart alanlarına (`checkpoint`, `proof`)
# ve kural adayı kuyruğuna çevirir. Etiketler sabit: serbest metinden çıkarım
# yapmaya çalışmak her sağlayıcıda başka sonuç veriyordu.
CHECKPOINT_TAG = "[KONTROL NOKTASI]"
PROOF_TAG = "[KANIT]"
RULE_TAG = "[KURAL]"

CHECKPOINT_DISCIPLINE = (
    f"[KONTROL NOKTASI KURALI]\n"
    f"Her modülü/adımı bitirdiğinde çıktına satır başında `{CHECKPOINT_TAG}` "
    "bloğu yaz:\n"
    "Yapılan: <bitirdiğin iş>\n"
    "Sonraki: <sıradaki adım>\n"
    "Dosyalar: <dokunduğun yollar>\n"
    "Testler: <koşturduğun komut ve sonucu>\n"
    "Koşu yarıda kesilirse bu bloktan sürdürülecek; blok yoksa iş baştan "
    "yapılmak zorunda kalır."
)

RULE_DISCIPLINE = (
    f"[KURAL ÖNERME]\n"
    f"Projeye dair kalıcı bir kural keşfedersen satır başında `{RULE_TAG} <kural>` "
    "yaz. Belleğe, kural dosyasına ya da tüzüğe KENDİN yazma: bunlar yalnızca "
    "adaydır, onayı kullanıcı verir."
)


def proof_discipline(needs_write: bool) -> str:
    """`[KANIT]` bloğu sözleşmesi; yazma niyeti olmayan kartta kanıt = üretilen yol."""
    if needs_write:
        body = (
            "Çalıştırdığın test komutu: <komut>\n"
            "Sonuç: yeşil | kırmızı (kaç test geçti/kaldı)\n"
            "Özet: <tek cümle>\n"
            "Test koşturmadan 'bitti' deme: kanıtsız ya da kırmızı çıktı "
            "kabul edilmez, kart yeniden koşar."
        )
    else:
        body = (
            "Bu kart dosya değiştirmiyor; kanıt olarak ÜRETTİĞİN dosya/rapor "
            "yolunu ver:\n"
            "Çıktı: <ürettiğin dosya ya da rapor yolu>\n"
            "Sonuç: yeşil\n"
            "Özet: <tek cümle>"
        )
    return f"[KANIT — ZORUNLU]\nÇıktının sonuna satır başında `{PROOF_TAG}` bloğu yaz:\n{body}"


@dataclass
class TaskCard:
    """Tek bir görev kartı."""

    id: str
    title: str = ""
    status: str = "backlog"
    agent: str = ""
    provider: str = field(default_factory=default_provider)
    model: str = ""
    skill: str = ""
    goal: str = ""
    criteria: List[str] = field(default_factory=list)
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    output_paths: List[str] = field(default_factory=list)
    summary: str = ""
    path: Optional[Path] = None
    notes: str = ""
    # Ofis alanları (Faz 3). Üst kart `children` ile alt kartlarını tutar, alt
    # kart `parent` ile üstünü; ağaç iki yönlü çünkü pano üstten aşağı, harness
    # ise bir alt kart bitince yukarı bakıyor ve tek yönlü bağ her iki tarafta
    # da tüm kartları taramayı gerektirirdi.
    office: str = ""
    parent: str = ""
    children: List[str] = field(default_factory=list)
    # Değerlendiricinin verdiği not (0–1) ve gerekçesi; `None` = notlanmadı.
    grade: Optional[float] = None
    verdict: str = ""
    # Kaç kez koşuldu: eşiğin altındaki alt kart bir kez yeniden koşar (retry ≤ 1).
    attempt: int = 0
    # Kart düzeyi token tavanı; 0 ise ofisin `budget_tokens` değeri geçerli.
    budget_tokens: int = 0
    # Ofis projesi (`projects/<proje>/PROJECT.md`). Boşsa kart projesizdir;
    # ofis kartları bir projeye bağlanınca rapor ve bellek o proje altında
    # toplanır ve orkestratör planlarken projenin kapsamını görür.
    project: str = ""
    # Kilit niyeti: "write" (proje dosyalarını değiştirir) | "read" | "" (çıkarım).
    # Ofis alt kartları varsayılan olarak OKUMA: paylaşımlı kilitle aynı proje
    # dizininde birbirlerini beklemeden koşabilsinler.
    intent: str = ""
    # Faz 10-A. `checkpoint`: ajanın son `[KONTROL NOKTASI]` bloğunun yazıldığı
    # DOSYA yolu; çökme sonrası yeniden koşu bu dosyadan sürer (eski sohbet
    # değil). `proof`: `[KANIT]` bloğunun kısa metni — kart yalnızca kanıtı
    # yeşilse `done` olabilir. İkisi de kart ön bilgisinde durur: UI ve harness
    # aynı tek kaynağı okur.
    checkpoint: str = ""
    proof: str = ""
    # Faz 10-C. `worktree`: bu kartın izole çalışma ağacının MUTLAK yolu
    # (boş = ofisin ortak `_workdir()`'i; eski kartlar böyle kalır).
    # `branch`: o ağacın dalı (`desk/<kart-id>`). `pr_url`: taslak PR bağlantısı
    # ("" = PR açılmadı). Üçü de kart ön bilgisinde durur; UI ve harness aynı
    # tek kaynağı okur, ikinci bir defter açılmaz.
    worktree: str = ""
    branch: str = ""
    pr_url: str = ""
    # Faz 11-C (pano alanları).
    # `effort`: ARTIK GERÇEK ALAN. Eskiden arayüz eforu `notes` içine
    # "effort: <düzey>" satırı olarak yazıyordu ve hiçbir kod onu geri
    # okumuyordu (üstüne `notes` içeriğini de eziyordu): kart panosundan efor
    # değiştirmek fiilen hiçbir şey yapmıyordu.
    effort: str = ""
    # `priority`: sahiplenme sırası (P0 > P1 > P2 > boş). Eskiden sıralama
    # yalnızca dosya adıydı, yani "acil" diye bir kavram yoktu.
    priority: str = ""
    # `input_paths`: kartın girdi sözleşmesi; ajan neyi okuyacağını hedef
    # metninden tahmin etmek zorunda kalmasın.
    input_paths: List[str] = field(default_factory=list)
    # `report_path`: kartın raporu. `output_paths` içinde karışık duruyordu.
    report_path: str = ""
    # `claimed_by` / `claim_expiry`: atomik sahiplenme kirası (`claims/<id>.lock`
    # ile aynı gerçeğin kart üzerindeki görünümü; kilit AYRI dosyada durur ki
    # kart Obsidian'da açıkken de sahiplenme çalışsın).
    claimed_by: str = ""
    claim_expiry: str = ""
    # `event_seq`: kartın gördüğü son pano olayının sırası (projeksiyon tutarlılığı).
    event_seq: int = 0
    # Faz 11.6. `kind`: kartın niteliği ("research" | "" ). Öz-amplifikasyon
    # kilidi (agents/amplification.py) yalnızca ARAŞTIRMA kartlarına uygulanır:
    # beyinde yanıt varsa CLI turu hiç açılmaz, rapor düşük yenilikliyse aynı
    # konudaki zamanlanmış görev durdurulur. Alan boşsa başlık/hedef sezgisi
    # kullanılır — sezgi dar tutulur çünkü yanlış pozitif bir geliştirme kartını
    # beyin cevabıyla kapatmak demek.
    kind: str = ""
    # Faz 12-B. `review`: kartın İNSAN müdahalesi bekleyen kısa durumu
    # ("soru bekliyor" gibi). Kart DURUMU (`status`) değil: `board_ask` bloke
    # etmez, ajan çalışmaya devam eder; ama panoda "burada bir soru asılı"
    # görünmeli. `notes` bunu taşıyamazdı (serbest metin, aranamaz).
    review: str = ""

    def to_frontmatter(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status if self.status in STATUSES else "backlog",
            "agent": self.agent,
            "provider": self.provider,
            "model": self.model,
            "skill": self.skill,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "output_paths": list(self.output_paths or []),
            "office": self.office,
            "project": self.project,
            "parent": self.parent,
            "children": list(self.children or []),
            "grade": "" if self.grade is None else round(float(self.grade), 3),
            "verdict": self.verdict,
            "attempt": int(self.attempt or 0),
            "budget_tokens": int(self.budget_tokens or 0),
            "intent": self.intent,
            "checkpoint": self.checkpoint,
            "worktree": self.worktree,
            "branch": self.branch,
            "pr_url": self.pr_url,
            "effort": self.effort,
            "priority": self.priority,
            "input_paths": list(self.input_paths or []),
            "report_path": self.report_path,
            "claimed_by": self.claimed_by,
            "claim_expiry": self.claim_expiry,
            "event_seq": int(self.event_seq or 0),
            "kind": self.kind,
            "review": self.review,
            # Kanıt ön bilgide tek satıra sıkıştırılır: YAML çok satırlı değer
            # taşımıyor ve blok metni gövdeye yazılırsa bölüm ayrıştırıcısı
            # sonucu ikiye bölerdi.
            "proof": " ".join((self.proof or "").split())[:400],
        }


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def new_task_id(title: str = "") -> str:
    """Zaman damgası + başlıktan türetilmiş, dosya adı olarak güvenli kimlik."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (title or "gorev").lower()).strip("-")[:24] or "gorev"
    return f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}"


SECTIONS = (SECTION_GOAL, SECTION_CRITERIA, SECTION_NOTES, SECTION_RESULT)

# Bölüm sınırı YALNIZCA bu dört başlıktır. Eskiden herhangi bir `## ...` satırı
# sınır sayılıyordu ve ajan çıktısı `## Bulgular` gibi bir başlık içerdiğinde
# "Sonuç" bölümü ilk başlıkta kesiliyordu: 29k karakterlik çıktı geri okunduğunda
# birkaç yüz karaktere iniyordu.
_SECTION_HEAD_RE = re.compile(r"^##\s+(" + "|".join(re.escape(s) for s in SECTIONS) + r")\s*$")

# Gövde metni tesadüfen tam da bu dört başlıktan birini içerebilir. O durumda
# yazarken bir seviye indirilir ve görünmez bir HTML yorumu işareti konur;
# okurken aynı işaretle geri yükselir. Simetrik olduğu için kayıpsız.
_ESCAPE_MARK = "<!--entropy-esc-->"
_ESCAPED_HEAD_RE = re.compile(
    r"^###\s+(" + "|".join(re.escape(s) for s in SECTIONS) + r")\s*" + re.escape(_ESCAPE_MARK) + r"\s*$"
)


def _escape_body(text: str) -> str:
    """Bölüm sınırıyla çakışan başlıkları bir seviye indirir (yazma yönü)."""
    if not text:
        return text or ""
    out = []
    for line in text.splitlines():
        m = _SECTION_HEAD_RE.match(line)
        out.append(f"### {m.group(1)} {_ESCAPE_MARK}" if m else line)
    return "\n".join(out)


def _unescape_body(text: str) -> str:
    """`_escape_body`nin tersi (okuma yönü)."""
    if not text or _ESCAPE_MARK not in text:
        return text or ""
    out = []
    for line in text.splitlines():
        m = _ESCAPED_HEAD_RE.match(line)
        out.append(f"## {m.group(1)}" if m else line)
    return "\n".join(out)


def trim_to_sections(text: str, limit: int) -> str:
    """
    Metni `limit` karakterin altına, BÖLÜM BÜTÜNLÜĞÜNÜ bozmadan kırpar.

    Değerlendirici prompt'u için: ham `text[:1500]` kesmesi cümlenin ortasında
    duruyor ve değerlendirici eksik gördüğü bölümü "yapılmamış" sayıyordu. Burada
    yalnızca tam markdown blokları (başlıktan başlığa) alınır.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    blocks: List[List[str]] = [[]]
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+\S", line) and blocks[-1]:
            blocks.append([])
        blocks[-1].append(line)
    kept: List[str] = []
    total = 0
    for block in blocks:
        chunk = "\n".join(block)
        if kept and total + len(chunk) + 1 > limit:
            break
        kept.append(chunk)
        total += len(chunk) + 1
    out = "\n".join(kept)
    if len(out) > limit:
        # Tek blok bile sığmıyor: sert kesmekten başka seçenek yok.
        out = out[:limit]
    if len(out) < len(text):
        out = out.rstrip() + "\n\n[... çıktı kırpıldı; tamamı kartta]"
    return out


def _split_sections(body: str) -> Dict[str, str]:
    """Gövdeyi bilinen `## Başlık` bölümlerine ayırır."""
    sections: Dict[str, str] = {}
    current = None
    buf: List[str] = []
    for line in (body or "").splitlines():
        m = _SECTION_HEAD_RE.match(line)
        if m:
            if current:
                sections[current] = _unescape_body("\n".join(buf).strip())
            current = m.group(1).strip()
            buf = []
        elif current:
            buf.append(line)
    if current:
        sections[current] = _unescape_body("\n".join(buf).strip())
    return sections


# Proje dosyalarını değiştirme niyeti taşıyan fiiller. Liste kasıtlı olarak dar:
# "rapor yaz" gibi kasaya üreten işler yazma kilidi almamalı, yoksa her alt kart
# yeniden sıraya girer ve ofis paralelliği anlamsızlaşır.
_WRITE_INTENT_RE = re.compile(
    r"\b(refactor|refaktör|kodu?\s+(değiştir|düzelt|yaz)|dosyayı?\s+(değiştir|düzenle|güncelle|sil)|"
    r"düzenle|yamala|patch|implement|uygula|commit|migrasyon|migration|"
    r"testleri?\s+(ekle|yaz)|hata\s*ayıkla|debug|derle|build)\b",
    re.IGNORECASE,
)


def _accepts_kwarg(func, name: str) -> bool:
    """`func` verilen adlı anahtar argümanı (ya da **kwargs) kabul ediyor mu?"""
    import inspect

    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False
    if name in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def interactive_cards_enabled() -> bool:
    """`config.desk_interactive_cards` bayrağı (içe aktarım tembel: döngü yok)."""
    try:
        from entropy.core.config import config

        return bool(getattr(config, "desk_interactive_cards", True))
    except Exception:
        return False


def is_desk_card(card: "TaskCard") -> bool:
    """
    Kart bir Desk OFİS kartı mı? (Entropy'nin kendi kartlarında `office` boştur.)

    Etkileşimli kip yalnızca ofis kartlarında açılır: Entropy'nin kendi arka
    plan görevleri (damıtma, konsolidasyon) bittiğinde süreç ölmeli, canlı
    kalan bir terminal orada yalnızca kota ve kilit tutardı.
    """
    return bool(str(getattr(card, "office", "") or "").strip())


def followup_lock_hooks(project_path: Optional[str], needs_write: bool):
    """
    Varsayılan takip turu kancaları: yazma niyetli kartta proje yazma kilidi.

    Köprü ilk finalize'da kilitleri bırakır (bekleyen terminal koşan kart
    değildir); takip turu YENİDEN kilit ister. Ofis harness'ı kendi
    kancalarını geçer (sayaç da tutar), bu ikili yalnızca harness'sız
    (doğrudan `TaskBoard.run`) yol içindir.
    """
    if not needs_write or not project_path:
        return None, None
    from entropy.core.project_lock import project_lock_manager

    target = str(project_path)

    def _start(_task_id: str) -> bool:
        try:
            return bool(project_lock_manager.acquire_write(target, timeout=5.0))
        except Exception:
            return False

    def _end(_task_id: str) -> None:
        try:
            project_lock_manager.release_write(target)
        except Exception:
            pass

    return _start, _end


def resolve_card_model(card: "TaskCard", agent_spec=None, provider: str = "") -> str:
    """
    Kartın bu koşuda kullanacağı ham model adı (Faz 9.5).

    Sıra: (1) kartın `model` alanı, (2) ajan tanımının modeli. İki durumda da ad
    `compile.resolve_model` tablosundan geçirilir; sağlayıcıya ait olmayan bir ad
    (ör. `provider: claude` + `model: gemini-3.1-pro-high`) o sağlayıcının
    karşılığına çevrilir. Boş dönüş = "oturumun modelini miras al".

    Eskiden kartın `model` alanı hiçbir yere aktarılmıyordu; köprü üst çubuğun
    modelini kullanıyor ve claude kartları `unrecognized_model` ile ölüyordu.
    """
    from entropy.agents.compile import CLAUDE_FALLBACK_MODEL, resolve_model
    from entropy.agents.registry import AgentSpec

    provider = (provider or "").strip().lower()
    raw = (card.model or "").strip()
    spec = agent_spec
    if raw:
        # Kart modeli ajan tanımını geçersiz kılar; tabloyu kullanabilmek için
        # geçici bir spec'e sarılır (resolve_model spec üzerinden çalışıyor).
        spec = AgentSpec(name=card.agent or card.id, model=raw)
    if spec is None:
        return ""
    resolved = (resolve_model(spec, provider) or "").strip()
    if not resolved or resolved.lower() == CLAUDE_FALLBACK_MODEL:
        # "inherit": köprü kendi oturum modelinde kalsın.
        return ""
    return resolved


def resolve_card_effort(card: "TaskCard", agent_spec=None) -> str:
    """
    Kartın bu koşudaki eforu: (1) kartın `effort` alanı, (2) ajanın eforu.

    Boş dönüş = "köprünün oturum eforunda kal". Faz 11-C öncesi bu yol tamamen
    kopuktu: `AgentSpec.effort` alanı vardı, arayüz onu AGENT.md'ye yazıyordu
    ama yürütmeye HİÇ ulaşmıyordu — Claude'da her kart üst çubuğun eforuyla
    koşuyordu, kart panosundaki efor kutusu ise `notes` alanına yazıp kayboluyordu.
    """
    value = str(getattr(card, "effort", "") or "").strip().lower()
    if not value and agent_spec is not None:
        value = str(getattr(agent_spec, "effort", "") or "").strip().lower()
    return value


def agent_session_kwargs(agent: str, provider: str, model: str = "",
                         effort: str = "", system_prompt: str = "",
                         vault_path=None) -> Dict[str, object]:
    """
    Ajanın KALICI oturumu için köprüye geçilecek kwarg'lar.

    İki sağlayıcı farklı yürür (CLI asimetrisi):

    - **Claude** oturum kimliğini önceden atayabiliyor (`--session-id <uuid>`),
      bu yüzden kimlik `uuid5(ad)` ile deterministik üretilir: kimlik yakalama
      yarışı hiç doğmaz ve dosya kaybolsa bile aynı kimlik yeniden hesaplanır.
      İlk koşu `--session-id`, sonraki koşular `--resume`.
    - **agy** kimliği önceden atayamıyor; akıştan yakalanır ve `session.json`a
      yazılır, sonraki koşu `--conversation <id>` alır.

    İstem/model/efor/sağlayıcı değişince imza düşer ve YENİ oturum açılır:
    `--system-prompt-snapshot` varsayılan olarak açık, yani sürdürülen bir
    oturum eski istemi taşımaya devam ederdi.

    Worktree'de koşan kart bu yolu HİÇ kullanmaz (çağıran süzer): Claude'un
    oturum deposu çalışma dizinine göre anahtarlı, worktree ajanın kalıcı
    konuşmasını başka bir klasöre dağıtırdı.
    """
    try:
        from entropy.core.identity import agent_session_store
    except Exception:
        return {}
    try:
        store = agent_session_store(vault_path)
        return store.run_kwargs(agent, provider, model=model, effort=effort,
                                system_prompt=system_prompt)
    except Exception:
        logging.getLogger(__name__).debug("Ajan oturumu okunamadı", exc_info=True)
        return {}


def agent_spec_payload(agent_spec) -> Optional[dict]:
    """Ajan tanımının sistem istemine giren, sağlayıcıdan bağımsız özeti."""
    if agent_spec is None:
        return None
    return {
        "name": getattr(agent_spec, "name", "") or "",
        "role": getattr(agent_spec, "role", "") or "",
        "description": getattr(agent_spec, "description", "") or "",
        "prompt": getattr(agent_spec, "prompt", "") or "",
        "tools_policy": getattr(agent_spec, "tools_policy", "") or "",
        "office": getattr(agent_spec, "office", "") or "",
        # Efor künyeye Faz 11-C'de girdi: ajanın "ne kadar düşünsün" ayarı
        # yalnızca argv'ye değil, kartın kendi kimliğine de yazılı olsun.
        "effort": getattr(agent_spec, "effort", "") or "",
    }


def card_needs_write(card: "TaskCard", agent_spec=None) -> bool:
    """
    Kart proje dizininde YAZMA kilidi gerektiriyor mu?

    Sıra: (1) kartın açık `intent` alanı, (2) ajanın `tools_policy` kısıtı,
    (3) ofis alt kartıysa varsayılan OKUMA, (4) metinde yazma fiili araması.
    """
    intent = (card.intent or "").strip().lower()
    if intent in ("write", "yazma", "rw"):
        return True
    if intent in ("read", "okuma", "ro", "read-only"):
        return False
    if agent_spec is not None and (getattr(agent_spec, "tools_policy", "") or "").lower() in (
        "read-only", "readonly", "okuma"
    ):
        return False
    if card.parent or card.office:
        # Ofis alt kartı: aksi açıkça yazılmadıkça okuma kilidiyle koşar.
        return False
    text = " ".join([card.title or "", card.goal or "", " ".join(card.criteria or []), card.notes or ""])
    return bool(_WRITE_INTENT_RE.search(text))


def _bullets(text: str) -> List[str]:
    return [
        re.sub(r"^[-*]\s+", "", ln).strip()
        for ln in (text or "").splitlines()
        if ln.strip().startswith(("-", "*"))
    ]


class TaskBoard:
    """Kasadaki görev kartlarının CRUD'u ve yürütülmesi."""

    # Sağlayıcı başına köprü önbelleği: bir kart "claude" derken etkin köprü
    # "agy" ise o sağlayıcının köprüsü kurulur. Her kart için yeni köprü kurmak
    # süreç başına onlarca boşta CLI oturumu ve token sayacı demekti.
    _bridge_cache: Dict[str, object] = {}
    _bridge_lock = threading.Lock()

    def __init__(self, vault_path: Optional[Path | str] = None):
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        self.vault_path = Path(vault_path)
        self.tasks_dir = self.vault_path / TASKS_SUBDIR
        self.desk_offices_dir = self.vault_path / DESK_OFFICES_SUBDIR
        self._migrate_office_cards_once()

    # -- yollar --------------------------------------------------------

    def office_cards_dir(self, office: str) -> Path:
        """Bir ofisin kart klasörü (`Desk/Offices/<ofis>/cards`)."""
        return self.desk_offices_dir / str(office).strip() / OFFICE_CARDS_DIRNAME

    def _office_card_dirs(self) -> List[Path]:
        """Diskte var olan tüm ofis kart klasörleri."""
        out: List[Path] = []
        try:
            if not self.desk_offices_dir.is_dir():
                return out
            for child in sorted(self.desk_offices_dir.iterdir()):
                if not child.is_dir():
                    continue
                cards = child / OFFICE_CARDS_DIRNAME
                if cards.is_dir():
                    out.append(cards)
        except OSError:
            return out
        return out

    # -- okuma ---------------------------------------------------------

    def card_file(self, task_id: str, office: Optional[str] = None) -> Path:
        """
        Kartın dosya yolu.

        `office` verilmişse doğrudan o ofisin kart klasörü kullanılır (yazma
        yolu bunu kullanır: kart hangi ofise aitse oraya yazılır). Verilmemişse
        önce Entropy kökü, sonra ofis kökleri aranır; hiçbirinde yoksa Entropy
        kökü döner — yani "yeni kart" varsayılan olarak Entropy'nindir.
        """
        office = (office or "").strip()
        if office:
            return self.office_cards_dir(office) / f"{task_id}.md"
        entropy_path = self.tasks_dir / f"{task_id}.md"
        if entropy_path.is_file():
            return entropy_path
        for cards_dir in self._office_card_dirs():
            candidate = cards_dir / f"{task_id}.md"
            if candidate.is_file():
                return candidate
        return entropy_path

    def list(self, status: Optional[str] = None,
             office: Optional[str] = None) -> List[TaskCard]:
        """
        Kartlar. `office=None` → YALNIZCA Entropy kartları,
        `office="<ad>"` → yalnızca o ofisin kartları,
        `office=ALL_CARDS` → iki kök birden.
        """
        cards: List[TaskCard] = []
        scope = (office or "").strip()
        if scope == ALL_CARDS:
            roots = [self.tasks_dir] + self._office_card_dirs()
        elif scope:
            roots = [self.office_cards_dir(scope)]
        else:
            roots = [self.tasks_dir]
        for root in roots:
            try:
                if not root.is_dir():
                    continue
                for path in sorted(root.glob("*.md")):
                    card = self._read(path)
                    if card is None:
                        continue
                    if status is not None and card.status != status:
                        continue
                    # Entropy kökündeki bir kart `office:` taşıyorsa (taşıma
                    # yapılamamış kalıntı) Entropy listesine KARIŞTIRILMAZ.
                    if not scope and card.office:
                        continue
                    if scope and scope != ALL_CARDS and card.office != scope:
                        continue
                    cards.append(card)
            except OSError:
                continue
        return cards

    def get(self, task_id: str) -> Optional[TaskCard]:
        return self._read(self.card_file(task_id))

    def _read(self, path: Path) -> Optional[TaskCard]:
        try:
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        front, body = parse_frontmatter(text)
        sections = _split_sections(body)
        outputs = front.get("output_paths") or []
        if isinstance(outputs, str):
            outputs = [o.strip() for o in outputs.split(",") if o.strip()]
        status = str(front.get("status") or "backlog").strip().lower()
        children = front.get("children") or []
        if isinstance(children, str):
            children = [c.strip() for c in children.split(",") if c.strip()]
        raw_grade = front.get("grade")
        try:
            grade = float(raw_grade) if str(raw_grade).strip() not in ("", "None") else None
        except (TypeError, ValueError):
            grade = None
        try:
            attempt = int(str(front.get("attempt") or 0).strip() or 0)
        except (TypeError, ValueError):
            attempt = 0
        try:
            budget_tokens = int(str(front.get("budget_tokens") or 0).strip() or 0)
        except (TypeError, ValueError):
            budget_tokens = 0
        inputs = front.get("input_paths") or []
        if isinstance(inputs, str):
            inputs = [p.strip() for p in inputs.split(",") if p.strip()]
        try:
            event_seq = int(str(front.get("event_seq") or 0).strip() or 0)
        except (TypeError, ValueError):
            event_seq = 0
        return TaskCard(
            id=str(front.get("id") or path.stem),
            title=str(front.get("title") or path.stem),
            status=status if status in STATUSES else "backlog",
            agent=str(front.get("agent") or ""),
            provider=str(front.get("provider") or default_provider()),
            model=str(front.get("model") or ""),
            skill=str(front.get("skill") or ""),
            goal=sections.get(SECTION_GOAL, "").strip(),
            criteria=_bullets(sections.get(SECTION_CRITERIA, "")),
            created_at=str(front.get("created_at") or ""),
            started_at=str(front.get("started_at") or ""),
            finished_at=str(front.get("finished_at") or ""),
            output_paths=[str(o) for o in outputs],
            summary=sections.get(SECTION_RESULT, "").strip(),
            notes=sections.get(SECTION_NOTES, "").strip(),
            path=path,
            office=str(front.get("office") or ""),
            project=str(front.get("project") or ""),
            parent=str(front.get("parent") or ""),
            children=[str(c) for c in children],
            grade=grade,
            verdict=str(front.get("verdict") or ""),
            attempt=attempt,
            budget_tokens=budget_tokens,
            intent=str(front.get("intent") or "").strip().lower(),
            checkpoint=str(front.get("checkpoint") or ""),
            proof=str(front.get("proof") or ""),
            worktree=str(front.get("worktree") or ""),
            branch=str(front.get("branch") or ""),
            pr_url=str(front.get("pr_url") or ""),
            effort=str(front.get("effort") or "").strip().lower(),
            priority=str(front.get("priority") or "").strip().upper(),
            input_paths=[str(p) for p in inputs],
            report_path=str(front.get("report_path") or ""),
            claimed_by=str(front.get("claimed_by") or ""),
            claim_expiry=str(front.get("claim_expiry") or ""),
            event_seq=event_seq,
            kind=str(front.get("kind") or "").strip().lower(),
            review=str(front.get("review") or ""),
        )

    # -- yazma ---------------------------------------------------------

    def create(self, card: TaskCard) -> TaskCard:
        if not card.id:
            card = replace(card, id=new_task_id(card.title))
        if not card.created_at:
            card = replace(card, created_at=_now())
        if self.card_file(card.id, office=card.office).exists() or self.get(card.id) is not None:
            raise FileExistsError(f"'{card.id}' kimlikli kart zaten var.")
        return self._write(card)

    def update(self, card: TaskCard) -> TaskCard:
        return self._write(card)

    # -- durum makinesi + olay günlüğü (Faz 11-C) ----------------------

    @property
    def events(self):
        """Bu kasanın pano olay günlüğü."""
        from entropy.agents.board_events import BoardEventLog

        log = getattr(self, "_event_log", None)
        if log is None:
            log = BoardEventLog(self.vault_path)
            self._event_log = log
        return log

    def apply_event(self, card_id: str, event: str, payload: Optional[dict] = None,
                    actor: str = "") -> Optional[TaskCard]:
        """
        Kartı durum makinesinden geçirir: DOĞRULA → GÜNLÜĞE YAZ → KARTA YAZ.

        Sıra bilinçli. `transitions` kütüphanesinin bilinen tuzağı "geçiş
        sonrası istisna geri alınmaz"dı; burada doğrulama (koruma) her şeyden
        önce koşar, dolayısıyla reddedilen bir geçiş hiçbir yan etki üretmez.
        Günlük karttan ÖNCE yazılır çünkü tek denetim kaynağı odur: kart
        dosyası onun türetilmiş görünümüdür.

        Geçersiz geçişte `board_fsm.InvalidTransition` yükselir — sessizce
        yutulmaz; "neden bu kart hâlâ backlog'da" sorusunun cevabı bir
        istisna olmalı, bir sessizlik değil.
        """
        card = self.get(card_id)
        if card is None:
            return None
        payload = dict(payload or {})
        payload.setdefault("actor", actor or "")
        # Doğrulama (istisna atabilir; kart henüz DEĞİŞMEDİ).
        row = _board_fsm.resolve_target(card, event, payload)
        log_payload = dict(payload)
        log_payload.setdefault("title", card.title)
        log_payload.setdefault("agent", card.agent)
        log_payload.setdefault("status", row.target)
        written = self.events.append(
            event, card.id, actor=actor or payload.get("actor") or "",
            payload=log_payload, attempt_id=int(card.attempt or 0) + 1,
        )
        if written is not None:
            payload["event_seq"] = int(written.get("seq") or 0)
        new_card = _board_fsm.transition(card, event, payload)
        new_card = self._write(new_card)
        self._announce_state(new_card, event, row.target)
        self.rewrite_taskboard()
        return new_card

    def reset_card(self, card_id: str, reason: str = "",
                   actor: str = "system") -> Optional[TaskCard]:
        """Asılı/başarısız kartı kuyruğa geri çeker (uzlaştırıcı kapısı)."""
        card = self.get(card_id)
        if card is None:
            return None
        new_card = _board_fsm.reset(card, reason=reason, actor=actor)
        self.events.append("task.reset", card.id, actor=actor,
                           payload={"reason": reason, "status": new_card.status,
                                    "agent": card.agent},
                           attempt_id=int(card.attempt or 0) + 1,
                           idempotency_key=f"{card.id}-reset-{_now()}")
        new_card = self._write(new_card)
        self._announce_state(new_card, "task.reset", new_card.status)
        self.rewrite_taskboard()
        return new_card

    def _advance_to_running(self, card: TaskCard, provider: str = "",
                            model: str = "", effort: str = "") -> Optional[TaskCard]:
        """
        Kartı hangi durumdan gelirse gelsin `running`e taşır (uyumluluk yolu).

        `run()` Faz 11-C'de bir SARMALAYICI oldu: asıl akış "dispatcher
        sahiplenir → başlatır", ama `/desk task`, harness pompası ve arayüz
        düğmeleri hâlâ doğrudan `run()` çağırıyor. Bu yardımcı aradaki
        geçişleri (assign → claim → start) makineden geçirerek üretir; hiçbiri
        atlanmaz, yani olay günlüğü kartın tam yaşam döngüsünü görür.

        Geçiş reddedilirse (ör. iptal edilmiş kart) None döner ve koşu başlamaz.
        """
        from entropy.agents.dispatcher import ClaimStore

        try:
            if card.status in ("review", "failed"):
                card = self.reset_card(card.id, reason="", actor="system") or card
            if card.status == "backlog" and str(card.agent or "").strip():
                card = self.apply_event(card.id, "task.assigned", actor="system",
                                        payload={"agent": card.agent}) or card
            if card.status == "backlog":
                # Ajansız kart: makinede `backlog → running` yok. Kart panoda
                # bekler; bu bilinçli, "kimin işi" belli olmadan koşu başlamaz.
                return None
            if card.status == "assigned":
                lease = ClaimStore(self.vault_path).acquire(card.id, card.agent or "entropy")
                if lease is None:
                    return None
                card = self.apply_event(
                    card.id, "task.claimed", actor=card.agent or "system",
                    payload={"claimed": True, "claimed_by": card.agent or "entropy",
                             "claim_expiry": lease.get("expiry", "")},
                ) or card
            if card.status != "taken":
                return None
            return self.apply_event(
                card.id, "run.started", actor=card.agent or "system",
                payload={"provider": provider, "model": model, "effort": effort,
                         "pid": os.getpid()},
            )
        except _board_fsm.InvalidTransition:
            logging.getLogger(__name__).warning(
                "Kart koşuya alınamadı (geçersiz geçiş): %s (%s)", card.id, card.status
            )
            return None

    def rewrite_taskboard(self) -> None:
        """
        `TASKBOARD.md`yi kart dosyalarından yeniden üretir.

        Projeksiyonun kaynağı olay günlüğüdür ama insan panosu kart
        dosyalarından çizilir: kullanıcı Obsidian'da bir kartı elle
        düzenlediğinde pano da onu göstermeli. İki görünümün ayrışması
        `projection_hash` ile ayrıca ölçülebiliyor.
        """
        try:
            cards = list(self.list())
            rows = [{
                "id": c.id, "title": c.title, "status": c.status, "agent": c.agent,
                "effort": c.effort, "priority": c.priority,
                "report_path": c.report_path,
            } for c in cards]
            # Faz 12-B (araştırma C §1.6 / karar 5): projeksiyon ARTIK gerçekten
            # hesaplanıyor. `projection_hash` şimdiye dek boş geçiliyordu, yani
            # "iki görünüm ayrışırsa ölçeriz" iddiasının hiçbir karşılığı yoktu
            # ve `Board/projection.json` hiç yazılmamıştı.
            from entropy.agents.board_events import board_drift

            view = self.events.write_projection()
            drift = board_drift(cards, view)
            view = dict(view, drift=len(drift))
            self.events.render_taskboard(view, cards=rows)
            if drift:
                self._announce_drift(drift, view)
        except Exception:
            logging.getLogger(__name__).debug("TASKBOARD.md yazılamadı", exc_info=True)

    def _announce_drift(self, drift: List[dict], view: dict) -> None:
        """Kart dosyaları ile olay projeksiyonu ayrıştıysa uyarır ve olay yazar."""
        logging.getLogger(__name__).warning(
            "Pano ayrışması: %d kart (kart dosyası ≠ olay projeksiyonu): %s",
            len(drift),
            ", ".join(f"{d['id']}({d['card']}≠{d['projection']})" for d in drift[:5]),
        )
        try:
            self.events.append(
                task_id=drift[0]["id"],
                actor="system",
                action="board.drift",
                payload={"count": len(drift), "cards": drift[:20],
                         "projection_hash": str(view.get("projection_hash") or "")},
                idempotency_key=f"drift:{view.get('projection_hash') or ''}",
            )
        except Exception:
            logging.getLogger(__name__).debug("Ayrışma olayı yazılamadı", exc_info=True)

    @staticmethod
    def _announce_state(card: TaskCard, event: str, status: str) -> None:
        """`bus.board_state_changed` — arayüz ve sahne tek sözleşmeden beslenir."""
        try:
            from entropy.core.event_bus import bus

            bus.board_state_changed.emit({
                "card_id": card.id,
                "status": status,
                "event": event,
                "agent": card.agent or "",
                "office": card.office or "",
                "title": card.title or "",
            })
        except Exception:
            pass

    def _write(self, card: TaskCard) -> TaskCard:
        # Kartın kökü `office` alanından türer: ofis kartı ofisin kasasına,
        # Entropy kartı `Entropy/Tasks` altına yazılır.
        path = self.card_file(card.id, office=card.office)
        # Kart ofis kazandıysa (ya da kaybettiyse) eski kökteki kopya silinir;
        # aksi hâlde aynı kimlikle iki dosya kalır ve iki kaynaklı gerçek olur.
        old = self.card_file(card.id)
        if old != path and old.is_file():
            try:
                old.unlink()
            except OSError:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        criteria = "\n".join(f"- {c}" for c in (card.criteria or [])) or "-"
        body = (
            f"## {SECTION_GOAL}\n{_escape_body(card.goal) or '-'}\n\n"
            f"## {SECTION_CRITERIA}\n{criteria}\n\n"
            f"## {SECTION_NOTES}\n{_escape_body(card.notes)}\n\n"
            f"## {SECTION_RESULT}\n{_escape_body(card.summary)}\n"
        )
        path.write_text(f"{render_frontmatter(card.to_frontmatter())}\n\n{body}", encoding="utf-8")
        self._notify(card.id)
        return replace(card, path=path)

    def delete(self, task_id: str) -> bool:
        card = self.get(task_id)
        path = self.card_file(task_id) if card is None else (card.path or self.card_file(task_id))
        if not path.is_file():
            return False
        # Faz 10-C: kart gidiyorsa izole çalışma ağacı da gider. Silme
        # BAŞARISIZ olabilir (Windows dosya kilidi, ölçüm: rc=255); o durumda
        # kayıt ertelenmiş temizlik kuyruğuna düşer ve kart yine silinir.
        if card is not None and (card.worktree or ""):
            try:
                from entropy.agents import worktrees as _wt

                _wt.release_worktree(card, force=True, vault_path=self.vault_path)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Kart worktree'si kaldırılamadı: %s", task_id, exc_info=True
                )
        try:
            path.unlink()
        except OSError:
            return False
        self._notify(task_id)
        return True

    # -- taşıma (Faz 9 / B-9.2) ------------------------------------------

    # Kasa başına tek kez koşar: her `TaskBoard()` kurulumunda diski taramak
    # gereksiz; taşıma zaten idempotent ama ucuz olmalı.
    _migrated_vaults: set = set()
    _migrate_lock = threading.Lock()

    def _migrate_office_cards_once(self) -> None:
        key = str(self.vault_path.resolve() if self.vault_path.exists() else self.vault_path)
        with TaskBoard._migrate_lock:
            if key in TaskBoard._migrated_vaults:
                return
            TaskBoard._migrated_vaults.add(key)
        try:
            self.migrate_office_cards()
        except Exception:
            logging.getLogger(__name__).warning("Ofis kartı taşıması yapılamadı.", exc_info=True)

    def migrate_office_cards(self) -> List[str]:
        """
        `Entropy/Tasks` altında kalmış OFİS kartlarını ofis kasasına taşır.

        Tek işlemde, doğrulamalı ve idempotent: hedefte aynı içerik zaten
        varsa kaynak silinir, hedef farklıysa kaynak DOKUNULMADAN bırakılır
        (iki kaynaklı gerçeği sessizce çözmek veri kaybı riskiydi). Her adım
        `Desk/_migrations.log` dosyasına yazılır.
        """
        moved: List[str] = []
        entries: List[str] = []
        try:
            if not self.tasks_dir.is_dir():
                return moved
            candidates = sorted(self.tasks_dir.glob("*.md"))
        except OSError:
            return moved
        desk_offices = self._desk_agent_offices()
        with TaskBoard._migrate_lock:
            for path in candidates:
                card = self._read(path)
                if card is None:
                    continue
                if not card.office:
                    # Ofissiz ama ajanı bir DESK ofisine ait olan kart: kullanıcı
                    # `/task ... Alfa` yazarken "ofise iş vermek" istiyordu, kart
                    # ise Entropy kökünde ofissiz doğuyor ve `run()` kadro
                    # kontrolüne takılıp `failed` oluyordu. Niyet ajandan
                    # okunabildiği için kart o ofise devredilir.
                    if self._claim_card_for_office(path, card, desk_offices, moved, entries):
                        continue
                    continue
                target = self.office_cards_dir(card.office) / path.name
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                try:
                    if target.is_file():
                        if target.read_text(encoding="utf-8") == text:
                            path.unlink()
                            entries.append(f"tekrar\t{path}\t{target}")
                        else:
                            entries.append(f"çakışma\t{path}\t{target}")
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text, encoding="utf-8")
                    # Doğrulama: hedef okunabiliyor ve aynı kimliği taşıyor mu?
                    check = self._read(target)
                    if check is None or check.id != card.id:
                        entries.append(f"doğrulanamadı\t{path}\t{target}")
                        continue
                    path.unlink()
                    moved.append(card.id)
                    entries.append(f"taşındı\t{path}\t{target}")
                except OSError as exc:
                    entries.append(f"hata\t{path}\t{target}\t{exc}")
        if entries:
            self._append_migration_log(entries)
        if moved:
            logging.getLogger(__name__).info("Ofis kartı taşındı (%d): %s", len(moved), ", ".join(moved))
            self._notify("")
        return moved

    def _desk_agent_offices(self) -> Dict[str, str]:
        """`{ajan adı: ofis}` — Desk ofislerinin tüm kadrosu (orkestratör dâhil)."""
        try:
            from entropy.agents.desk_registry import DeskRegistry

            desk = DeskRegistry(vault_path=self.vault_path)
            out: Dict[str, str] = {}
            for office in desk.list():
                for name in office.roster():
                    out.setdefault(name, office.name)
            return out
        except Exception:
            return {}

    def _claim_card_for_office(self, path: Path, card: "TaskCard",
                               desk_offices: Dict[str, str],
                               moved: List[str], entries: List[str]) -> bool:
        """
        Ofissiz kartı, ajanının ofisine devreder. Devredilirse True.

        Koşan kart DOKUNULMAZ (yürütmenin altından dosya çekmek sonucu
        kaybettirirdi) ve hedefte aynı adlı bir kart varsa çakışma yazılıp
        kaynak bırakılır. Yazma doğrulanamazsa kaynak geri konur.
        """
        office = desk_offices.get((card.agent or "").strip())
        if not office or card.status == "running":
            return False
        target = self.office_cards_dir(office) / path.name
        try:
            source_text = path.read_text(encoding="utf-8")
        except OSError:
            return False
        if target.is_file():
            entries.append(f"çakışma\t{path}\t{target}")
            return False
        try:
            self._write(replace(card, office=office))
        except OSError as exc:
            entries.append(f"hata\t{path}\t{target}\t{exc}")
            return False
        check = self._read(target)
        if check is None or check.id != card.id or check.office != office:
            # Geri al: kaynak dosya `_write` sırasında silinmiş olabilir.
            try:
                path.write_text(source_text, encoding="utf-8")
                target.unlink()
            except OSError:
                pass
            entries.append(f"doğrulanamadı\t{path}\t{target}")
            return False
        moved.append(card.id)
        entries.append(f"ofise-atandı\t{path}\t{target}\t{office}")
        return True

    def _append_migration_log(self, entries: List[str]) -> None:
        path = self.vault_path / MIGRATION_LOG_SUBPATH
        stamp = _now()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                for row in entries:
                    fh.write(f"{stamp}\t{row}\n")
        except OSError:
            logging.getLogger(__name__).warning("Taşıma günlüğü yazılamadı: %s", path)

    @staticmethod
    def _notify(task_id: str) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.task_cards_updated.emit(task_id)
        except Exception:
            pass

    # -- yürütme --------------------------------------------------------

    @classmethod
    def bridge_for(cls, provider: str, bridge_factory: Optional[Callable] = None):
        """
        Kartın sağlayıcısına uygun köprüyü verir.

        Sıra: (1) test/çağıran enjeksiyonu, (2) etkin köprü aynı sağlayıcıysa o,
        (3) süreç genelinde önbelleklenen, o sağlayıcıya ait yeni köprü.
        """
        provider = (provider or "agy").strip().lower()
        if bridge_factory is not None:
            return bridge_factory(provider)

        try:
            from entropy.ui.manager import EntropyUIManager

            mgr = getattr(EntropyUIManager, "instance", None)
            active = getattr(mgr, "bridge", None) if mgr is not None else None
            if active is not None and getattr(active, "provider_name", None) == provider:
                return active
        except Exception:
            pass

        with cls._bridge_lock:
            cached = cls._bridge_cache.get(provider)
            if cached is not None:
                return cached
            from entropy.core.provider import create_bridge

            bridge = create_bridge(provider=provider)
            cls._bridge_cache[provider] = bridge
            return bridge

    @staticmethod
    def project_file_section(project_path: Optional[str], limit: int = PROJECT_FILE_LIST_LIMIT) -> str:
        """
        Alt kart istemine giren PROJE DOSYA LİSTESİ (ilk `limit` yol).

        Faz 7 (C2d): alt ajan kendi başına depoyu taramasın diye istemde hazır
        bir dosya haritası verilir. Liste bilerek kısa ve göreli: tam ağaç
        tek başına on binlerce token ediyordu ve mutlak yollar istemde kasa
        konumunu sızdırıyordu. Gizli klasörler (`.git`, `__pycache__`, `node_modules`)
        atlanır: gürültüden başka bir şey taşımıyorlar.
        """
        if not project_path:
            return ""
        root = Path(project_path)
        skip = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
                ".pytest_cache", "dist", "build", ".idea", ".vscode"}
        paths: List[str] = []
        try:
            if not root.is_dir():
                return ""
            for current, dirs, files in os.walk(root):
                dirs[:] = sorted(d for d in dirs if d not in skip and not d.startswith("."))
                for name in sorted(files):
                    if name.startswith("."):
                        continue
                    try:
                        rel = str(Path(current, name).relative_to(root))
                    except ValueError:
                        continue
                    paths.append(rel.replace("\\", "/"))
                    if len(paths) >= limit:
                        break
                if len(paths) >= limit:
                    break
        except OSError:
            return ""
        if not paths:
            return ""
        return (
            "[PROJE DOSYALARI]\n"
            f"(ilk {len(paths)} yol; kök: proje dizini)\n"
            + "\n".join(f"- {p}" for p in paths)
        )

    def build_prompt(
        self,
        card: TaskCard,
        agent_spec=None,
        project_path: Optional[str] = None,
        lead_sections: Optional[List[str]] = None,
    ) -> str:
        """
        Ajanın gövdesi + görev sözleşmesi + kabul ölçütleri.

        `lead_sections` istemin EN BAŞINA girer (doğuş talimatı, kaldığın yer,
        koşan karta yorum). Sıra bilinçli: ajan doğar doğmaz önce panoyu ve
        mimariyi okumalı; bu bilgi ajan gövdesinin altına düşerse uzun istemde
        ilk okunanın altında kalıyordu.

        Ajan gövdesi prompt'a da konur (yalnızca `--agent` ile geçilmez): derlenmiş
        ajan tanımı sağlayıcının bulamadığı bir kökten koşulduğunda sessizce
        yok sayılıyor ve görev genel bir asistan tarafından yapılıyordu. Gövdenin
        prompt'ta olması bu durumda da rolü garanti eder.
        """
        parts: List[str] = [s.strip() for s in (lead_sections or []) if (s or "").strip()]
        if agent_spec is not None and (agent_spec.prompt or "").strip():
            parts.append(agent_spec.prompt.strip())
        criteria = "\n".join(f"- {c}" for c in (card.criteria or [])) or "- (belirtilmedi)"
        parts.append(
            "[GÖREV SÖZLEŞMESİ]\n"
            f"Başlık: {card.title}\n"
            f"Hedef: {card.goal or card.title}\n"
            f"Kabul ölçütleri:\n{criteria}\n\n"
            "Kurallar: Ölçütlerin her birini tek tek ele al ve karşılandığını "
            "kanıtıyla göster. Yapamadığın maddeyi 'yapılamadı' diye açıkça yaz; "
            "sessizce atlama. Yanıtın Türkçe ve markdown olsun.\n\n"
            # Maliyet disiplini: kota koruması yalnızca bütçe sayacıyla değil,
            # görevin kendi kapsamıyla da yapılır. Sınırsız keşif yetkisi verilen
            # bir alt kart tek başına ofisin bütçesini bitiriyordu.
            f"{COST_DISCIPLINE}"
        )
        # Faz 10-A: kontrol noktası / kanıt / kural adayı disiplini. Kanıt
        # metni kartın yazma niyetine göre değişir: salt araştırma kartında
        # "test koştur" demek ajanı olmayan bir testi uydurmaya itiyordu.
        parts.append(CHECKPOINT_DISCIPLINE)
        parts.append(proof_discipline(card_needs_write(card, agent_spec=agent_spec)))
        parts.append(RULE_DISCIPLINE)
        # Faz 11-C.5: pano araç sözleşmesi. Ofis kartına GİRMEZ — ofis tarafı
        # harness'ın itmeli akışında koşuyor ve orada kartı ajan seçmiyor;
        # `board_next` orada anlamsız, üstelik iki panonun sözleşmesini
        # karıştırırdı.
        if not card.office:
            try:
                from entropy.agents.board_tools import tools_section

                parts.append(tools_section())
            except Exception:
                pass
        # Faz 10-C: worktree'li kartta ajan HANGİ dizinde olduğunu bilmeli.
        # Ölçüm: izole kipte `Bash` aracı git deposunun dışında koşuyordu ve
        # `git status` "not a git repository" diyordu; artık cwd worktree ama
        # ajanın da başka bir depoya yazmaya kalkmaması için beyan gerekiyor.
        if (card.worktree or "").strip():
            parts.append(
                "[ÇALIŞMA DİZİNİ]\n"
                f"Bu görevin TEK çalışma dizinin: {card.worktree}\n"
                f"Burası bir git worktree'sidir; dalı `{card.branch or 'desk/' + card.id}`. "
                "Git komutlarını bu dizinde çalıştır.\n"
                "Bütün okuma/yazma bu dizinin İÇİNDE olacak; başka bir depo "
                "yoluna yazma, dal değiştirme (`git checkout`/`git switch` yok)."
            )
        files_block = self.project_file_section(project_path)
        if files_block:
            parts.append(files_block)
        if card.notes:
            parts.append(f"[NOTLAR]\n{card.notes}")
        return "\n\n".join(parts)

    def run(
        self,
        card_id: str,
        bridge_factory: Optional[Callable] = None,
        on_done: Optional[Callable[[str, bool], None]] = None,
        agent_registry=None,
        project_path: Optional[str] = None,
        lead_sections: Optional[List[str]] = None,
        interactive: Optional[bool] = None,
        on_followup_start: Optional[Callable[[str], object]] = None,
        on_followup_end: Optional[Callable[[str], object]] = None,
    ) -> Optional[str]:
        """
        Kartı arka planda çalıştırır; ledger görev kimliğini döndürür.

        Çağrı bloke etmez: köprünün `send_background_task_async`ı iş parçacığı
        açar, sonuç geri çağrıda işlenir. Kart hemen `running` olur ki pano
        (ve ikinci bir /task çağrısı) aynı işi iki kez başlatmasın.

        `on_done(kart_id, başarılı)` kart kapandıktan SONRA çağrılır (köprünün
        işçi iş parçacığında). Ofis harness'ı sıradaki alt kartı buradan
        başlatır; Qt sinyaline bağlanmak zorunda kalsaydı harness bir olay
        döngüsü olmadan (arka plan görevi, test) çalışamazdı.

        `interactive` (Faz 10-D): None ise karttan türetilir — Desk OFİS
        kartında ve `config.desk_interactive_cards` açıkken True, Entropy'nin
        kendi kartlarında her zaman False. Kanca verilmezse yazma niyetli kart
        için varsayılan proje kilidi kancaları takılır (`followup_lock_hooks`).
        """
        card = self.get(card_id)
        if card is None:
            return None
        if card.status == "running":
            return None

        # Ajan defteri dışarıdan verilebilir: ofis kartlarının ajanı Entropy'nin
        # kadrosunda değil, ofisin kendi `agents/` klasöründedir (Faz 6).
        registry = agent_registry or AgentRegistry(vault_path=self.vault_path)
        agent_spec = registry.get(card.agent) if card.agent else None
        # Ek-1 (Faz 9): Entropy kartı (office boş) YALNIZCA Entropy kadrosundaki
        # bir ajana koşar. Bir ofis orkestratörünün adı Entropy kartına
        # yazıldığında kart sessizce genel bir asistanla koşuyordu; iki kadro
        # birbirine karışmasın diye bu artık açık bir hata.
        if card.agent and not card.office and agent_spec is None:
            self._write(replace(
                card,
                status="failed",
                finished_at=_now(),
                summary=f"Koşulmadı: '{card.agent}' ajanı Entropy kadrosunda değil.",
            ))
            emit_terminal(f"card-{card.id}", card.agent, "failed",
                          summary=f"'{card.agent}' ajanı Entropy kadrosunda değil.",
                          vault_path=self.vault_path)
            return None
        provider = (
            card.provider
            or (agent_spec.provider if agent_spec else "")
            or default_provider()
        ).lower()
        # Faz 11.6 — AÇIK TESPİTİ. Araştırma kartında koşudan ÖNCE beyne
        # sorulur: yeterli güvende bir yanıt varsa CLI turu HİÇ açılmaz, kart
        # "beyinden yanıtlandı" özetiyle `review`e düşer. Kilit, kotayı
        # harcamadan kapanan tek yoldur; hata durumunda (hafıza katmanı yok,
        # sorgu patladı) sessizce normal koşuya devam eder.
        brain = self._brain_shortcut(card, provider=provider)
        if brain is not None:
            return brain

        bridge = self.bridge_for(provider, bridge_factory=bridge_factory)
        if bridge is None:
            return None

        # MODEL (Faz 9.5). Kartın `model` alanı yürütmeye HİÇ geçmiyordu: köprü
        # üst çubuğun modeliyle koşuyor, `provider: claude` olan bir kart
        # `gemini-3.1-pro-high` ile başlatılıp `unrecognized_model` ile ölüyordu.
        # Ad `resolve_model` ile sağlayıcıya çevrilir (gemini-* -> claude-opus-5)
        # ve o koşuya `model=` olarak geçirilir.
        run_model = resolve_card_model(card, agent_spec=agent_spec, provider=provider)

        # EFOR (Faz 11-C.4). Kaynak tek: AGENT.md. Kartın kendi `effort` alanı
        # ajanınkini ezer; ikisi de boşsa köprü oturum eforunda kalır.
        run_effort = resolve_card_effort(card, agent_spec=agent_spec)

        prompt = self.build_prompt(card, agent_spec=agent_spec, project_path=project_path,
                                   lead_sections=lead_sections)
        needs_write = card_needs_write(card, agent_spec=agent_spec)
        # Faz 12-B: OTURUM BÜTÇESİ. Eşik aşıldıysa oturum burada döner ve devir
        # sayfası isteme eklenir; `agent_session_kwargs` aşağıda taze bir
        # kimlik üretir. Sıra önemli: istem oturum kararından SONRA
        # tamamlanmalı, yoksa taze oturum devir sayfasını hiç görmez.
        if card.agent and not card.worktree:
            try:
                from entropy.agents import session_budget

                handoff_block = session_budget.rotate_if_needed(
                    card.agent, provider, board=self, vault_path=self.vault_path
                )
            except Exception:
                handoff_block = ""
            if handoff_block:
                prompt = f"{prompt}\n\n{handoff_block}"
        task_id = f"card-{card.id}"
        # Durum geçişi ARTIK durum makinesinden: `backlog`/`assigned` kart
        # gerekirse otomatik olarak `taken`a taşınır (uyumluluk yolu — dispatcher
        # kartı zaten sahiplenmiş olabilir), sonra `run.started` yayılır.
        card = self._advance_to_running(
            card, provider=provider, model=run_model, effort=run_effort,
        )
        if card is None:
            return None

        def _on_result(full_text: str, ok: bool, report_path: str = "",
                       _card_id=card.id):
            # `report_path`: köprünün kasaya yazdığı rapor dosyası. Köprü bu
            # üçüncü argümanı YALNIZCA parametre adı `report_path` olan geri
            # çağrılara geçirir (`core/provider.call_on_result`).
            self._finish(_card_id, full_text, ok, report_path=report_path)
            if on_done is not None:
                try:
                    on_done(_card_id, ok)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Kart tamamlama geri çağrısı hata verdi (%s)", _card_id
                    )

        kwargs = dict(
            task_id=task_id,
            task_name=card.title or card.id,
            prompt=prompt,
            mode="accept-edits",
            on_result=_on_result,
            save_report=True,
            agent=card.agent or None,
            # Okuma niyetli kart paylaşımlı kilitle koşar; aksi hâlde aynı
            # proje dizinindeki ikinci alt kart 60 sn bekleyip ölüyordu.
            needs_write=needs_write,
            # Adım tavanı yaptırımı: istemdeki "en çok N adım" ricası
            # tutmadığında köprü akıştaki araç olaylarını sayıp süreci öldürür.
            max_steps=MAX_STEPS_PER_CARD,
            # Kartın modeli o koşuya uygulanır; boşsa köprü oturum modelinde kalır.
            model=run_model or None,
            # Ajanın kimliği kartın sistem istemine girer (Faz 9.4).
            agent_spec=agent_spec_payload(agent_spec),
            # Faz 11-C.4: ajanın/kartın eforu argv'ye ulaşır. Claude'da
            # `--effort <düzey>`, agy'de model adının son eki olur (agy'de
            # `--effort` ile `--model` çakışıyor; kural korunur).
            effort=run_effort or None,
            # Faz 10-A: akış olayları kart/ofis/ajan künyesiyle etiketlenir;
            # Desk sahnesi ve terminal bölmeleri olayı bu meta ile eşler.
            stream_meta={
                "agent": card.agent or "",
                "office": card.office or "",
                "card_id": card.id,
            },
        )
        # Ofis kartı kendi çalışma dizininde koşar; derlenmiş ajan tanımı orada.
        if project_path:
            kwargs["project_path"] = str(project_path)

        # Faz 10-D: etkileşimli kip YALNIZCA Desk ofis kartında açılır.
        want_interactive = (
            is_desk_card(card) if interactive is None else bool(interactive)
        ) and interactive_cards_enabled()
        if want_interactive:
            if on_followup_start is None and on_followup_end is None:
                on_followup_start, on_followup_end = followup_lock_hooks(
                    kwargs.get("project_path"), needs_write
                )
            kwargs["interactive"] = True
            if on_followup_start is not None:
                kwargs["on_followup_start"] = on_followup_start
            if on_followup_end is not None:
                kwargs["on_followup_end"] = on_followup_end
        # `needs_write` bilmeyen dar köprü sözleşmeleri (ve sahte köprüler) için
        # imza denetimi. TypeError'ı yakalayıp yeniden denemek yanlış olurdu:
        # köprünün KENDİ gövdesinden gelen bir TypeError görevi iki kez
        # başlatırdı.
        # Faz 11-C.3: ajanın KALICI oturumu. Claude'da kimlik önceden
        # atanabiliyor (`--session-id <uuid>`), agy'de yalnızca akıştan
        # yakalanıyor; iki kol da `agent_session` sözleşmesinden beslenir.
        if card.agent and not card.worktree:
            # İmza kaynağı ajanın KİMLİK istemidir, kartın istemi değil
            # (QA 11-C/D): `build_prompt` her kartta farklı metin üretir, bu
            # yüzden imza her koşuda düşüyor ve `--resume` HİÇ kullanılmıyordu
            # ("kalıcı oturum" fiilen yoktu). Ajan tanımı/model/efor
            # değişmedikçe imza sabit kalır.
            session_prompt = (getattr(agent_spec, "prompt", "") or "") if agent_spec else prompt
            session_kwargs = agent_session_kwargs(
                card.agent, provider,
                model=run_model, effort=run_effort,
                system_prompt=session_prompt, vault_path=self.vault_path,
            )
            kwargs.update(session_kwargs)

        for optional in ("needs_write", "project_path", "max_steps", "model",
                         "agent_spec", "stream_meta", "interactive",
                         "on_followup_start", "on_followup_end", "effort",
                         "session_id", "conversation_id", "agent_name"):
            if optional in kwargs and not _accepts_kwarg(
                bridge.send_background_task_async, optional
            ):
                kwargs.pop(optional, None)
        try:
            bridge.send_background_task_async(**kwargs)
        except Exception as exc:
            self._finish(card.id, f"Görev başlatılamadı: {exc}", False)
            if on_done is not None:
                try:
                    on_done(card.id, False)
                except Exception:
                    pass
            return None
        return task_id

    def _brain_shortcut(self, card: TaskCard, provider: str = "") -> Optional[str]:
        """
        Araştırma kartı beyinden yanıtlanabiliyorsa kartı kapatır (Faz 11.6-a).

        Dönüş: kart kapatıldıysa sahte görev kimliği (`brain-<id>`) — çağıranlar
        (dispatcher, harness) bunu "kart işlendi" olarak okur ve ikinci bir tur
        açmaz; aksi hâlde None ve normal koşu devam eder.

        Ofis kartları KAPSAM DIŞI: Desk'in kendi zinciri ara çıktılara bağlı ve
        Entropy'nin beyni Desk'e sızmamalı (tek yönlü bilgi kuralı).
        """
        if card.office:
            return None
        try:
            from entropy.core.config import config as _config

            if not getattr(_config, "amplification_lock", True):
                return None
        except Exception:
            pass
        try:
            from entropy.agents import amplification

            if not amplification.is_research_card(card):
                return None
            answer = amplification.brain_lookup(
                f"{card.title or ''}\n{card.goal or ''}".strip()
            )
        except Exception:
            logging.getLogger(__name__).debug("Beyin kısayolu denenemedi", exc_info=True)
            return None
        if not answer.has_answer or not (answer.text or "").strip():
            return None
        moved = self._advance_to_running(card, provider=provider or card.provider)
        if moved is None:
            return None
        self._finish(moved.id, answer.note(), True)
        return f"brain-{card.id}"

    def stop(self, card_id: str) -> bool:
        """Süren kartı keser; kart `failed` olur."""
        card = self.get(card_id)
        if card is None or card.status not in ("running", "taken"):
            return False
        killed = False
        for provider in ("agy", "claude"):
            bridge = self._bridge_cache.get(provider)
            if bridge is None:
                continue
            try:
                bridge.terminate_background_task(f"card-{card_id}")
                killed = True
            except Exception:
                continue
        try:
            from entropy.ui.manager import EntropyUIManager

            mgr = getattr(EntropyUIManager, "instance", None)
            active = getattr(mgr, "bridge", None) if mgr is not None else None
            if active is not None:
                active.terminate_background_task(f"card-{card_id}")
                killed = True
        except Exception:
            pass
        # Faz 11-C: durdurma artık `failed` değil `canceled`. İkisini ayırmak
        # panonun okunabilirliği için şart: "kullanıcı vazgeçti" ile "iş
        # başarısız oldu" aynı sütunda durduğu sürece hiçbir sayaç anlamlı
        # değildi.
        try:
            self.apply_event(card.id, "task.canceled", actor="user",
                             payload={"summary": "Kullanıcı isteğiyle durduruldu."})
        except _board_fsm.InvalidTransition:
            self._write(replace(card, status="failed", finished_at=_now(),
                                summary="Kullanıcı isteğiyle durduruldu."))
        try:
            from entropy.agents.dispatcher import ClaimStore

            ClaimStore(self.vault_path).release(card.id)
        except Exception:
            pass
        emit_terminal(card.id, card.office or card.agent or "entropy", "canceled",
                      "Kullanıcı isteğiyle durduruldu.", vault_path=self.vault_path)
        return killed

    # -- tamamlama ------------------------------------------------------

    def _finish(self, card_id: str, full_text: str, ok: bool,
                report_path: str = "") -> None:
        """
        Görev bitince kartı günceller, wiki sayfası ve ajan belleği yazar.

        Bellek katmanı çağrıları içe aktarma koruması altında: `entropy.memory.wiki`
        ve `agent_memory` memory-rag tarafından sağlanıyor; henüz yoksa kart yine
        de doğru biçimde kapanmalı — ajan katmanı onlara bağımlı olamaz.
        """
        card = self.get(card_id)
        if card is None:
            return
        raw_output = (full_text or "").strip()
        # Faz 12-B (araştırma C §1.4): araç/etiket blokları KARTA, sohbete ve
        # hafızaya girmeden temizlenir. Ham metin köprünün raporunda ve olay
        # günlüğünde kayıpsız kalır (risk R-C); buradan sonraki her tüketici
        # temizlenmiş metni görür.
        tool_calls, finish_args, tool_reject = _board_tool_results(raw_output)
        # OFİS kartı KAPSAM DIŞI: Desk harness'ı blokları kartın `summary`sinden
        # geri ayrıştırıyor (kontrol noktası dosyası, kanıt, kural adayı).
        # Orada temizlik yapmak harness'ın tek gerçek kaynağını yok ederdi;
        # Desk'in kendi temizliği harness'ın işidir (açık iş).
        summary = raw_output if card.office else _strip_tool_blocks(raw_output)
        if not summary and isinstance(finish_args, dict):
            # Ajan SADECE araç bloğu yazdıysa özet boş kalmasın: `board_finish`
            # zaten bir `summary` alanı taşıyor.
            summary = str(finish_args.get("summary") or "").strip()
        outputs = list(card.output_paths or [])
        # RAPOR YOLU (Faz 11 kapanışı): köprü raporu
        # `Entropy/Skills/<yetenek>/Reports/Gorev_*.md` altına yazıyor ve yolu
        # şimdiye dek yalnızca `bus.task_notification` ile yayıyordu; kartın
        # `report_path` alanı hiç dolmuyordu. Yol geldiyse karta İŞLENİR
        # (var olanın üzerine yazılmaz) ve `output_paths`a da girer ki
        # amplifikasyon kilidi kaynağı (provenance) buradan türetebilsin.
        report_path = str(report_path or "").strip()
        if report_path and not (card.report_path or "").strip():
            # Diske YAZILIR: `apply_event` kartı dosyadan yeniden okur,
            # bellekteki kopya oraya taşınmaz.
            card = self._write(replace(card, report_path=report_path))
        if report_path and report_path not in outputs:
            outputs.append(report_path)

        if ok and summary:
            page = self._write_wiki_page(card, summary)
            if page:
                outputs.append(str(page))
            self._append_agent_memory(card, summary)

        # Faz 11-C.5: ajanın pano araçları. `[PANO board_finish]` bloğu varsa
        # KANIT ondan gelir ve kanıtsız kapanış reddedilir (kart `review`de
        # insan önüne kalır). Kanıt açıkça kırmızıysa (`green: false`) kart
        # `failed`a düşer — close-with-proof kuralının makineleşmiş hâli.
        if ok and finish_args and tool_reject is None:
            proof_payload = finish_args.get("proof")
        else:
            proof_payload = None
        if finish_args and isinstance(finish_args.get("proof"), dict)                 and finish_args["proof"].get("green") is False:
            ok = False
        for extra in (finish_args or {}).get("outputs") or []:
            if str(extra).strip() and str(extra) not in outputs:
                outputs.append(str(extra))

        # Durum geçişi durum makinesinden (`run.finished`); günlüğe de düşer.
        payload = {
            "ok": bool(ok),
            "summary": summary if summary else ("Çıktı üretilmedi." if not ok else ""),
            "finished_at": _now(),
        }
        if card.report_path:
            # Projeksiyona taşınır (`board_events.PROJECTED_FIELDS`): TASKBOARD.md
            # rapor bağlantısını buradan basar.
            payload["report_path"] = card.report_path
        if proof_payload:
            payload["proof"] = proof_payload
        moved = None
        try:
            moved = self.apply_event(card.id, "run.finished",
                                     actor=card.agent or "system", payload=payload)
        except _board_fsm.InvalidTransition:
            moved = None
        # Uyumluluk yolu: kart makinenin beklediği durumda değilse (eski kart,
        # doğrudan `_write` ile `running` yapılmış bir çağıran) eski davranış
        # aynen uygulanır — kart HER HÂLÜKÂRDA kapanmalı; asılı kart, kirli bir
        # geçişten daha pahalı.
        if moved is None:
            card = replace(
                card,
                status="review" if ok else "failed",
                finished_at=_now(),
                # Özet KIRPILMAZ: kart artık `##` başlıklı uzun çıktıyı kayıpsız
                # geri okuyabiliyor ve tek gerçek kaynak o. Kırpma, çıktının
                # tüketildiği yerde (değerlendirici prompt'u) yapılır.
                summary=payload["summary"],
                output_paths=outputs,
            )
            self._write(card)
        else:
            card = self._write(replace(moved, summary=payload["summary"],
                                       output_paths=outputs))
        try:
            from entropy.agents.dispatcher import ClaimStore

            ClaimStore(self.vault_path).release(card.id)
        except Exception:
            pass
        # Faz 12-B: beş aracın YÜRÜTÜCÜSÜ. `board_finish` yukarıda tüketildi;
        # `board_checkpoint` kontrol noktasını yazar, `board_ask` soruyu
        # Entropy'nin kutusuna bırakır, `board_next` sıradaki kartı söyler,
        # `board_create` ajanda REDDEDİLİR. Kart burada zaten kapandı: yürütücü
        # kartın son hâlini alır ve alan güncellemeleri diske işlenir.
        card = self._run_board_tools(tool_calls, card)
        # Oturum sayaçları (Faz 12-B): kart + token. Token ledger'dan okunur —
        # köprü `record_task_success`ı `on_result`tan ÖNCE çağırıyor, yani
        # bu noktada satır dolu.
        self._note_session_usage(card)

        if tool_reject:
            # Terminal olay YAYILMAZ: `emit_terminal` yalnızca son durumu
            # (completed/failed/canceled) taşır ve kartın gerçek sonu aşağıda
            # ayrıca yayılıyor. Ret nedeni günlüğe ve kartın özetine düşer.
            logging.getLogger(__name__).info(
                "board_finish reddedildi (%s): %s", card.id, tool_reject
            )
        # TERMİNAL SÖZLEŞMESİ (A2A): kart kapandığı ANDA terminal olay yayılır.
        # `review` de bir sondur — koşu bitti, karar insanın; asılı görevle
        # bitmiş görevi ayırt edebilmenin tek yolu bu olay.
        emit_terminal(
            card.id,
            card.office or card.agent or "entropy",
            "completed" if ok else "failed",
            (summary or "")[:500],
            vault_path=self.vault_path,
        )
        if not card.office:
            # Faz 11.6-b/c: yenilik kotası + kaynak zorunluluğu. Rapor hafızaya
            # `MemoryGate` üzerinden girer; ADD oranı eşiğin altındaysa aynı
            # konudaki zamanlanmış araştırma durdurulur. Karta düşen not,
            # kullanıcının "neden durdu" sorusunun tek yanıtıdır.
            card = self._apply_amplification_lock(card, summary, ok)
            self._report_to_entropy(card, summary, ok)

    def _note_session_usage(self, card: TaskCard) -> None:
        """Kartın token harcamasını ajanın oturum sayacına işler (Faz 12-B)."""
        if not card.agent or card.worktree or card.office:
            return
        tokens = 0
        try:
            from entropy.core.task_ledger import task_ledger

            row = task_ledger.get_task(f"card-{card.id}") or {}
            tokens = int(row.get("total_tokens") or 0)
        except Exception:
            tokens = 0
        try:
            from entropy.agents import session_budget

            session_budget.note_run(
                card.agent, (card.provider or default_provider()).lower(),
                tokens=tokens, vault_path=self.vault_path,
            )
        except Exception:
            logging.getLogger(__name__).debug("Oturum sayacı işlenemedi", exc_info=True)

    def _run_board_tools(self, tool_calls, card: TaskCard) -> TaskCard:
        """
        Ajanın pano araçlarını yürütür ve kartın güncel hâlini döndürür.

        Hata YÜKSELTMEZ: bir aracın patlaması kapanmış kartı geri alamaz.
        """
        if not tool_calls:
            return card
        try:
            from entropy.agents import board_tool_exec

            results = board_tool_exec.execute(
                tool_calls, board=self, card=card,
                actor=card.agent or "", actor_kind=board_tool_exec.ACTOR_AGENT,
                vault_path=self.vault_path,
            )
        except Exception:
            logging.getLogger(__name__).debug("Pano araçları yürütülemedi", exc_info=True)
            return card
        for res in results:
            updated = res.get("card")
            if updated is not None:
                card = updated
            if not res.get("ok"):
                logging.getLogger(__name__).info(
                    "Pano aracı reddedildi (%s / %s): %s",
                    card.id, res.get("tool"), res.get("error"),
                )
        return card

    def _apply_amplification_lock(self, card: TaskCard, summary: str,
                                  ok: bool) -> TaskCard:
        """
        Araştırma raporuna yenilik kotası + kaynak kuralını uygular (Faz 11.6).

        Kartın `## Notlar` bölümüne tek satırlık bir ölçüm yazar; kart hiçbir
        durumda BU YÜZDEN başarısız olmaz — kilit ölçer ve durdurur, yargılamaz.
        """
        if not ok or not (summary or "").strip():
            return card
        # "Beyinden yanıtlandı" turu ölçüme girmez: yeni bilgi üretmemiştir ve
        # kendi çıktısını hafızaya geri yazmak tam olarak engellenen döngüdür.
        if (summary or "").lstrip().startswith("Beyinden yanıtlandı"):
            return card
        # Anahtar (`/lock off`): kilit kapalıysa yenilik kotası da koşmaz —
        # açık tespitiyle aynı ayar, aksi hâlde "kapattım ama hâlâ ölçüyor".
        try:
            from entropy.core.config import config as _config

            if not getattr(_config, "amplification_lock", True):
                return card
        except Exception:
            pass
        try:
            from entropy.agents import amplification

            outcome = amplification.apply_report_lock(card, summary)
        except Exception:
            logging.getLogger(__name__).debug("Amplifikasyon kilidi koşmadı", exc_info=True)
            return card
        if outcome is None:
            return card
        note = f"[YENİLİK] {outcome.note}"
        notes = (card.notes or "").rstrip()
        return self._write(replace(
            card, notes=(notes + "\n" + note).strip() if notes else note
        ))

    def _report_to_entropy(self, card: TaskCard, summary: str, ok: bool) -> None:
        """
        Entropy KARTININ raporunu Entropy'nin gelen kutusuna ve sohbete taşır.

        Faz 11 öncesi bu yol yalnızca OFİS kartlarında vardı (`harness`);
        Entropy'nin kendi kartı bitince sohbete düşen tek şey bir bildirim
        hapıydı ve rapor bir sonraki turda Entropy'nin bağlamına HİÇ girmiyordu.
        Ofis kartları buraya girmez: akış tek yönlü kalır (Desk → Entropy yolu
        harness'ın işidir, tersi yasaktır).
        """
        try:
            from entropy.agents.mailbox import report_to_entropy

            report_to_entropy(
                card.agent or "entropy",
                card.title or card.id,
                summary or "",
                task_id=card.id,
                output_paths=list(card.output_paths or []),
                vault_path=self.vault_path,
            )
        except Exception:
            logging.getLogger(__name__).debug("Rapor kutusuna düşmedi", exc_info=True)
        try:
            from entropy.core.event_bus import bus

            # `task_report_ready`: sohbete RAPOR KARTI basan tek sözleşme.
            # Yükün alanları arayüzün sözleşmesidir (ui-engineer bağlar).
            bus.task_report_ready.emit({
                "card_id": card.id,
                "title": card.title or card.id,
                "agent": card.agent or "",
                "status": card.status,
                "ok": bool(ok),
                "summary": (summary or "")[:2000],
                "report_path": card.report_path or "",
                "output_paths": list(card.output_paths or []),
            })
        except Exception:
            pass

    def _write_wiki_page(self, card: TaskCard, body: str):
        try:
            from entropy.memory.wiki import write_query_page  # type: ignore
        except Exception:
            return None
        try:
            return write_query_page(
                card.skill or "",
                card.title or card.id,
                body,
                {
                    "task_id": card.id,
                    "agent": card.agent,
                    "provider": card.provider,
                    "goal": card.goal,
                    # Panonun bağlı olduğu kasa; yoksa genel yapılandırma kasasına
                    # yazılır ve testler kullanıcı kasasını kirletir.
                    "vault_path": self.vault_path,
                },
            )
        except Exception:
            return None

    def _append_agent_memory(self, card: TaskCard, body: str) -> None:
        try:
            from entropy.memory.agent_memory import append_agent_memory  # type: ignore
        except Exception:
            return
        try:
            append_agent_memory(
                card.agent,
                {
                    "task_id": card.id,
                    "title": card.title,
                    "goal": card.goal,
                    "summary": body[:1000],
                    "at": _now(),
                    "vault_path": self.vault_path,
                },
            )
        except Exception:
            return


# ---------------------------------------------------------------------------
# Takip turu kaydı (Faz 10-D)
# ---------------------------------------------------------------------------

FOLLOWUP_NOTE_PREFIX = "Takip turu"


def _strip_tool_blocks(text: str) -> str:
    """
    Araç/etiket bloklarını özetten temizler (Faz 12-B, karar 2).

    Modül yoksa metin OLDUĞU GİBİ döner: temizlik bir kolaylıktır, kartın
    kapanmasının önkoşulu değildir.
    """
    try:
        from entropy.agents.board_tools import strip_tool_blocks

        return strip_tool_blocks(text or "")
    except Exception:
        return (text or "").strip()


def _board_tool_results(text: str):
    """
    Ajan çıktısındaki pano araç bloklarını ayrıştırır.

    Dönüş: (çağrılar, board_finish argümanları, ret nedeni). Ret nedeni None
    değilse kanıt sözleşmesi karşılanmamıştır ve kart `done` olamaz.
    """
    try:
        from entropy.agents import board_tools

        calls = board_tools.parse_tool_calls(text or "")
        finish = next((c.args for c in calls if c.name == "board_finish"), None)
        reject = board_tools.validate_finish(finish) if finish is not None else None
        return calls, finish, reject
    except Exception:
        return [], None, None


def followup_note_line(payload: Dict[str, object]) -> str:
    """`bus.task_followup_completed` yükünden tek satırlık makbuz notu."""
    turn = int(payload.get("turn") or 0)
    text = " ".join(str(payload.get("text") or "").split())[:200]
    usage = payload.get("usage") or {}
    tokens = 0
    if isinstance(usage, dict):
        tokens = int(usage.get("total_tokens") or 0)
    ok = "tamam" if payload.get("success") else "yanıtsız"
    return (
        f"{FOLLOWUP_NOTE_PREFIX} {turn} · {ok} · {tokens} token · "
        f"{text or '(metin yok)'}"
    )


def followup_notes(card: "TaskCard") -> List[str]:
    """Kartın notlarındaki takip turu satırları (makbuz bu listeyi basar)."""
    return [
        line.strip()
        for line in (getattr(card, "notes", "") or "").splitlines()
        if line.strip().startswith(FOLLOWUP_NOTE_PREFIX)
    ]


def record_followup(
    payload: Dict[str, object],
    board: Optional["TaskBoard"] = None,
    vault_path: Optional[Path | str] = None,
) -> bool:
    """
    Takip turu özetini kartın `## Notlar` bölümüne ekler.

    Ledger token toplamı KÖPRÜDE güncelleniyor; burada yalnızca insanın
    okuyacağı iz yazılır (makbuzun `## İlerleme` bölümü bu satırları basar).
    """
    if not isinstance(payload, dict):
        return False
    card_id = str(payload.get("card_id") or "").strip()
    if not card_id:
        task_id = str(payload.get("task_id") or "")
        card_id = task_id[5:] if task_id.startswith("card-") else ""
    if not card_id:
        return False
    board = board or TaskBoard(vault_path=vault_path)
    card = board.get(card_id)
    if card is None:
        return False
    line = followup_note_line(payload)
    if line in (card.notes or ""):
        return False
    notes = ((card.notes + "\n") if card.notes else "") + line
    board.update(replace(card, notes=notes))
    return True


_followup_recorder_installed = False


def connect_followup_recorder(vault_path: Optional[Path | str] = None) -> bool:
    """
    `bus.task_followup_completed` → kart notu köprüsünü BİR KEZ bağlar.

    İki kez bağlanırsa aynı tur iki kez yazılırdı; bayrak modül düzeyinde.
    """
    global _followup_recorder_installed
    if _followup_recorder_installed:
        return False
    from entropy.core.event_bus import bus

    def _handler(payload, _vault=vault_path):
        try:
            record_followup(payload, vault_path=_vault)
        except Exception:
            logging.getLogger(__name__).warning(
                "Takip turu notu yazılamadı", exc_info=True
            )

    bus.task_followup_completed.connect(_handler)
    _followup_recorder_installed = True
    return True
