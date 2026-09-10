"""
Ofis harness'ı: planla → paralel koş → notla → kapat.

Üç adımın hepsi DOSYA üzerinden ilerler (kartlar kasada, aşama `state.json`
içinde). Nedeni Anthropic'in "dynamic workflows" ilkesiyle aynı: koordinasyon
konuşmanın içinde tutulursa uygulama kapanınca zincir kayboluyor; dosyada
tutulursa `resume_all()` kaldığı yerden sürdürebiliyor.

Akış:
  1. planlama  — orkestratör ajanı tek çağrıda ≤5 alt görev üretir (JSON);
                 alt kartlar `Tasks/` altına `parent` bağıyla yazılır.
  2. yürütme   — alt kartlar `max_parallel` kadar aynı anda `TaskBoard.run` ile
                 koşar; biten her kartta sıradaki başlar.
  3. değerlend.— değerlendirici ajanı çıktı özetlerini kabul ölçütlerine karşı
                 notlar; `grade < 0.6` ve `attempt < 1` olan alt kart bir kez
                 yeniden koşar. Sonra üst kart `review` olur.

Kota koruması: her adım bittiğinde maliyet SQLite ledger'dan (sağlayıcının
bildirdiği gerçek `total_tokens`) okunur ve toplanır; ledger'da usage yoksa
karakter/4 tahminine düşülür. Kartın `budget_tokens` alanı (yoksa ofisinki)
aşılırsa SÜREN alt kartlar `terminate_background_task` ile öldürülür ve üst kart
nedeniyle `failed` olur — yalnızca üst kartı başarısız saymak kotayı korumuyordu,
süren agy süreçleri token yakmaya devam ediyordu.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
import threading
from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, List, Optional

from entropy.agents.mailbox import (
    card_comments,
    comments_section,
    emit_terminal,
    instructions_section,
    pending_instructions,
    report_to_entropy,
)
from entropy.agents.desk_registry import DeskOffice, DeskRegistry
from entropy.agents.compile import claude_tools_list, is_orchestrator, resolve_model
from entropy.agents.registry import VALID_PROVIDERS, AgentRegistry, default_provider
from entropy.agents.tasks import (
    ALL_CARDS,
    CHECKPOINT_TAG,
    PROOF_TAG,
    RULE_TAG,
    TaskBoard,
    TaskCard,
    _now,
    card_needs_write,
    new_task_id,
    trim_to_sections,
)
from entropy.core.project_lock import LOCK_TIMEOUT_MARKER

logger = logging.getLogger(__name__)


class WriteLockHolder:
    """
    Proje yazma kilidini KENDİ iş parçacığında tutan sahip.

    Neden gerekli: `core.project_lock` kilidi iş parçacığına bağlıdır
    (`release_write` sahibi olmayan iş parçacığında `RuntimeError` atar). Takip
    turunda kilit arayüz iş parçacığında alınır (`bridge.send_followup` →
    `on_followup_start`) ama köprünün işçi iş parçacığında bırakılır
    (`on_followup_end`); doğrudan çağrılsaydı kilit sonsuza dek kalırdı.
    Burada tek bir yardımcı iş parçacığı hem alır hem bırakır.
    """

    def __init__(self, project_path: str):
        self.project_path = str(project_path)
        self._acquired = threading.Event()
        self._release = threading.Event()
        self._ok = False
        self._thread: Optional[threading.Thread] = None

    def acquire(self, timeout: float = 5.0) -> bool:
        from entropy.core.project_lock import project_lock_manager

        def _hold():
            try:
                self._ok = bool(
                    project_lock_manager.acquire_write(self.project_path, timeout=timeout)
                )
            except Exception:
                self._ok = False
            self._acquired.set()
            if not self._ok:
                return
            self._release.wait()
            try:
                project_lock_manager.release_write(self.project_path)
            except Exception:
                logger.debug("Yazma kilidi bırakılamadı: %s", self.project_path)

        self._thread = threading.Thread(target=_hold, daemon=True,
                                        name="entropy-followup-lock")
        self._thread.start()
        self._acquired.wait(timeout=timeout + 2.0)
        return bool(self._ok)

    def release(self) -> None:
        self._release.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

# Kilit yüzünden başlayamayan alt kart en çok bu kadar kez sıraya geri konur;
# sonrası gerçek bir kilitlenmedir ve sonsuz döngüye dönüşmemeli.
MAX_LOCK_REQUEUES = 5

# Değerlendirici prompt'unda alt kart başına en çok bu kadar karakterlik özet.
EVAL_SUMMARY_CHARS = 6000

STATE_FILENAME = "state.json"

# `state.json` içinde karta değil OFİSE ait alanların anahtarı (konuşma kimliği
# gibi). Kart kimlikleri zaman damgasıyla başlar, çakışma olamaz.
OFFICE_STATE_KEY = "__office__"

# Kabul eşiği: bunun altındaki alt kart bir kez yeniden koşar.
GRADE_THRESHOLD = 0.6
MAX_SUBTASKS = 5
MAX_ATTEMPTS = 2  # ilk koşu + bir retry

# Bir alt kartın BEKLENEN maliyeti (Faz 7 / C1b). Kontrol çağrıdan ÖNCE
# yapılabilsin diye gerekli: gerçek maliyet ancak çağrı bitince biliniyor ve
# "harca, sonra bak" düzeni her seferinde bütçeyi bir alt kart boyu aşıyordu.
# Değer ölçüme dayanıyor: agy alt kartları tipik olarak 20–40k token yakıyor.
SUBCARD_TOKEN_ESTIMATE = 30_000

# Uyarlanabilir tahmin sınırları (Faz 8 / 2). Sabit 30k hem küçük kartlarda
# bütçeyi gereksiz yere kilitliyor hem de büyük kartlarda yetersiz kalıyordu.
SUBCARD_ESTIMATE_FLOOR = 8_000
SUBCARD_ESTIMATE_CEILING = 40_000
# İstem karakterinden token'a: /4 token, ×3 ise araç turlarıyla bağlamın
# büyüme çarpanı (ölçüm: alt kart istemi tipik olarak toplam maliyetin ~1/3'ü).
SUBCARD_PROMPT_MULTIPLIER = 3
# Geçmiş medyanına güvenlik payı.
SUBCARD_MEDIAN_MARGIN = 1.2


def _median(values: List[int]) -> Optional[float]:
    data = sorted(int(v) for v in values if v)
    if not data:
        return None
    mid = len(data) // 2
    return float(data[mid]) if len(data) % 2 else (data[mid - 1] + data[mid]) / 2.0


def estimate_subcard_tokens(
    prompt_chars: int = 0,
    office: Optional[str] = None,
    ledger=None,
    board: Optional[TaskBoard] = None,
) -> Dict[str, object]:
    """
    Bir alt kartın BEKLENEN maliyeti; {"tokens": N, "source": "medyan|istem|taban"}.

    Sıra: istem karakterinden türeyen taban tahmin ile ofisin ledger'daki
    BAŞARILI alt kart medyanının (×1.2) büyüğü alınır, sonra [8k, 40k] aralığına
    kırpılır. Medyan yoksa (ofisin ilk turu) yalnızca istem konuşur. Kaynak
    etiketi kart dosyasına yazılır: bütçe kararının neye dayandığı sonradan
    denetlenebilmeli.
    """
    prompt_est = int(max(0, int(prompt_chars)) / 4 * SUBCARD_PROMPT_MULTIPLIER)
    value = float(prompt_est)
    source = "istem" if prompt_est else "taban"

    median = None
    if office and board is not None:
        median = _median(_office_subcard_costs(office, board, ledger))
    if median:
        scaled = median * SUBCARD_MEDIAN_MARGIN
        if scaled >= value:
            value = scaled
            source = "medyan"

    tokens = int(min(SUBCARD_ESTIMATE_CEILING, max(SUBCARD_ESTIMATE_FLOOR, value)))
    if tokens == SUBCARD_ESTIMATE_FLOOR and value <= SUBCARD_ESTIMATE_FLOOR:
        source = "taban"
    return {"tokens": tokens, "source": source}


def _office_subcard_costs(office: str, board: TaskBoard, ledger=None) -> List[int]:
    """Ofisin BAŞARIYLA biten alt kartlarının ledger'daki gerçek maliyetleri."""
    if ledger is None:
        try:
            from entropy.core.task_ledger import task_ledger as ledger  # type: ignore
        except Exception:
            return []
    costs: List[int] = []
    try:
        # Ofis kartları artık ofisin kendi kasasında (Faz 9 / B-9.2).
        cards = board.list(office=office)
    except Exception:
        return []
    for card in cards:
        if card.office != office or not card.parent:
            continue
        try:
            rec = ledger.get_task(f"card-{card.id}")
        except Exception:
            rec = None
        if not rec or str(rec.get("status") or "").upper() != "SUCCESS":
            continue
        value = rec.get("total_tokens")
        if value in (None, ""):
            continue
        try:
            costs.append(int(value))
        except (TypeError, ValueError):
            continue
    return costs

# Orkestratör çıktısında kod üretimi izi (A9). Alt ajanlar için GEÇERSİZ:
# yalnızca plan/rapor üretmesi gereken orkestratöre uygulanır.
ORCHESTRATOR_NO_CODE_RETRY = 1
_CODE_TRACE_RE = re.compile(
    r"```(?:py|python|js|ts|tsx|jsx|java|c|cpp|cs|go|rs|rb|php|sh|bash|ps1|sql|html|css|yaml|yml|diff|patch)\b"
    r"|^diff --git\b"
    r"|\bdosyaya\s+yazd[ıi]m\b"
    r"|\bdosyay[ıi]\s+(?:olu[şs]turdum|g[üu]ncelledim|yazd[ıi]m)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Orkestratörün plan öncesi yapabileceği en fazla arama (Faz 10-A / 5). Sınırsız
# araştırma tek planlama turunda kotanın büyük kısmını yakıyordu.
MAX_RESEARCH_QUERIES = 3

# Planlama bağlamına giren ofis raporu sayısı ve rapor başına karakter (B1).
CONTEXT_REPORT_COUNT = 3
CONTEXT_REPORT_CHARS = 1200

# Plan isteminin karakter bütçesi (Faz 10 düzeltmesi). Canlı koşuda tek plan
# çağrısı 38k token ölçüldü (`e2e_state.json` → `measured_tokens`); en şişkin
# bölüm "bilgi tazeleme" idi (ofis belleği + 3 rapor sınırsız birleşiyordu).
# Bütçe İSTEM metnine uygulanır, sistem istemine değil.
PLAN_CONTEXT_MAX_CHARS = 2000     # [BİLGİ TAZELEME] bloğu
PLAN_PROJECT_MAX_CHARS = 1500     # [PROJE] bloğu (tüzük uzun olabiliyor)
PLAN_PROMPT_MAX_CHARS = 12000     # toplam tavan


def orchestrator_produced_code(text: str) -> bool:
    """
    Orkestratör çıktısı araç yasağını çiğnemiş mi (kod bloğu/diff/yazma izi)?

    ```json bloğu KASITLI olarak ihlal sayılmaz: planın kendisi o biçimde
    isteniyor. Yalnızca dil etiketli kod blokları, `diff --git` başlıkları ve
    "dosyaya yazdım" gibi açık yazma beyanları ihlaldir.
    """
    return bool(_CODE_TRACE_RE.search(text or ""))

# ---------------------------------------------------------------------------
# Faz 10-A — blok ayrıştırıcıları (kontrol noktası / kanıt / kural adayı)
# ---------------------------------------------------------------------------

# Bir sonraki köşeli etiket satırı bloğu bitirir. Etiket = satır başında, tümü
# büyük harf (Türkçe dâhil) ve boşluk/tire içeren köşeli parantez.
_TAG_LINE_RE = re.compile(r"^\s*\[[A-ZÇĞİIÖŞÜ][A-ZÇĞİIÖŞÜ0-9 ,.:/_—-]*\]")

# Kanıt sonucu: kırmızı işaretleri yeşil işaretlerini EZER. Sıra önemli — ajan
# "3 test kırmızıydı, düzeltince yeşil oldu" yazdığında blok yine incelenmeli;
# kartın kendiliğinden kapanmaması, yanlışlıkla kapanmasından ucuzdur.
_PROOF_RED_RE = re.compile(
    r"\bk[ıi]rm[ıi]z[ıi]\b|\bred\b|\bfail(?:ed|ure|ing)?\b|\berror[s]?\b|"
    r"\bhata\b|\bge[çc]medi\b|\d+\s+failed",
    re.IGNORECASE,
)
_PROOF_GREEN_RE = re.compile(
    r"\bye[şs]il\b|\bgreen\b|\bpass(?:ed|ing)?\b|\bba[şs]ar[ıi]l[ıi]\b|"
    r"\bge[çc]ti\b|\bok\b|\d+\s+passed",
    re.IGNORECASE,
)
# Salt araştırma kartında kanıt = üretilen dosya/rapor yolu.
_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s,;]+|(?:\.{0,2}/)?[\w.\-]+/[\w.\-/]+\.\w{1,6}|[\w.\-]+\.(?:md|json|csv|txt|py|html)\b")


def parse_tagged_block(text: str, tag: str) -> str:
    """
    `[ETİKET]` satırından bir sonraki etiket satırına kadar olan gövde.

    SON eşleşme kazanır: ajan aynı bloğu birkaç kez yazdıysa geçerli olan
    koşunun sonundaki hâlidir. Kod çiti (```) de blok sınırıdır.
    """
    raw = text or ""
    idx = raw.rfind(tag)
    if idx < 0:
        return ""
    lines = raw[idx + len(tag):].splitlines()
    body: List[str] = []
    for line in lines:
        if line.strip().startswith("```"):
            break
        if body and _TAG_LINE_RE.match(line):
            break
        body.append(line)
    return "\n".join(body).strip()


def parse_checkpoint(text: str) -> str:
    """Çıktıdaki `[KONTROL NOKTASI]` bloğunun gövdesi (yoksa boş)."""
    return parse_tagged_block(text, CHECKPOINT_TAG)


def parse_proof(text: str, needs_write: bool = True) -> Optional[dict]:
    """
    `[KANIT]` bloğu -> {"text": ..., "green": bool}; blok yoksa None.

    Yazma niyeti olan kartta yeşil = test sonucu yeşil. Salt araştırma kartında
    kanıt üretilen dosya/rapor yoludur: kırmızı işareti yoksa ve blokta bir yol
    varsa yeşil sayılır.
    """
    body = parse_tagged_block(text, PROOF_TAG)
    if not body:
        return None
    red = bool(_PROOF_RED_RE.search(body))
    green = bool(_PROOF_GREEN_RE.search(body)) and not red
    if not needs_write and not red and _PATH_RE.search(body):
        green = True
    return {"text": body, "green": green}


def parse_rule_candidates(text: str) -> List[str]:
    """Satır başındaki `[KURAL] …` satırları (aday kurallar)."""
    out: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith(RULE_TAG):
            continue
        rule = stripped[len(RULE_TAG):].strip(" :-—")
        if rule and rule not in out:
            out.append(rule)
    return out


def _flex_call(func: Callable, **kwargs):
    """
    Bellek katmanı fonksiyonunu İMZASINDA olan argümanlarla çağırır.

    Bellek modülleri başka bir ajanda geliştiriliyor; imzaları tam olarak
    kestirilemez. Fazla anahtar sözcük `TypeError` ile harness'ı düşürmesin
    diye çağrı imzaya göre kırpılır.
    """
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return func(**kwargs)
    params = sig.parameters
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return func(**kwargs)
    return func(**{k: v for k, v in kwargs.items() if k in params})


# Ofis çalışma dosyaları (bellek katmanı yoksa harness kendisi yazar).
BOARD_FILENAME = "BOARD.md"
ARCHITECTURE_FILENAME = "ARCHITECTURE.md"
RULES_FILENAME = "RULES.md"
RULE_CANDIDATES_FILENAME = "RULE_CANDIDATES.md"
CHECKPOINT_DIRNAME = "checkpoints"

# Doğuş talimatının başlığı; hemen ardından okunacak dosyaların MUTLAK yolları
# gelir. Başlık harness'ın: bellek katmanı metni üretse de istemin ilk satırı
# her iki yolda da aynı olmalı ki ajan bölümü tanısın.
SPAWN_HEADER = "[DOĞUŞ TALİMATI — önce oku]"

# Aşama adları (bus.office_progress ikinci argümanı).
PHASE_PLANNING = "planning"
PHASE_RUNNING = "running"
PHASE_EVALUATING = "evaluating"
PHASE_DONE = "done"
PHASE_FAILED = "failed"


def _estimate_tokens(*texts: str) -> int:
    """Kaba token tahmini: ~4 karakter = 1 token."""
    return sum(len(t or "") for t in texts) // 4


def extract_json_block(text: str) -> Optional[dict]:
    """
    Model yanıtından JSON nesnesi ayıklar.

    Sıra: (1) ```json kod bloğu, (2) herhangi bir kod bloğu, (3) metindeki ilk
    dengeli `{...}`. Üç yol da gerekli: modeller şemayı doğru üretse bile
    çevresine "İşte plan:" gibi bir cümle eklemekten vazgeçmiyor.
    """
    if not text:
        return None
    candidates: List[str] = []
    for m in re.finditer(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE):
        candidates.append(m.group(1))
    candidates.append(text)
    for raw in candidates:
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        start = raw.find("{")
        while start != -1:
            depth = 0
            for idx in range(start, len(raw)):
                if raw[idx] == "{":
                    depth += 1
                elif raw[idx] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            data = json.loads(raw[start:idx + 1])
                            if isinstance(data, dict):
                                return data
                        except Exception:
                            break
                        break
            start = raw.find("{", start + 1)
    return None


class OfficeHarness:
    """Tek bir ofisin kart zincirini yürüten durum makinesi."""

    # Süren zincirler: kart kimliği -> harness. `stop()` ve `resume_all()` aynı
    # kartı iki kez başlatmasın diye süreç genelinde tutulur.
    _active: Dict[str, "OfficeHarness"] = {}
    _active_lock = threading.Lock()

    def __init__(
        self,
        office_name: str,
        board: Optional[TaskBoard] = None,
        registry: Optional[AgentRegistry] = None,
        offices: Optional[DeskRegistry] = None,
        bridge_factory: Optional[Callable] = None,
    ):
        self.office_name = office_name
        self.offices = offices or DeskRegistry()
        vault = self.offices.vault_path
        self.board = board or TaskBoard(vault_path=vault)
        # Ajan defteri ofisin KENDİSİNİN: Desk, Entropy'nin `Entropy/Agents`
        # kadrosunu görmez (kural 1). Enjekte edilen bir defter varsa (testler,
        # paneller) ona saygı duyulur.
        self.registry = registry or self.offices.agents(office_name)
        self.bridge_factory = bridge_factory
        self._lock = threading.RLock()
        self._starting: set = set()
        # Faz 10-D: takip turu SÜREN kartlar. Bu kartlar `running` değildir
        # (ilk turda kapandılar) ama yazma kilidini yeniden aldıkları için
        # ofisin `max_parallel` bütçesinden bir yer tutarlar; sayaç olmasaydı
        # pompa aynı anda ikinci bir yazma kartı başlatırdı.
        self._followup_active: set = set()
        # kart kimliği → o tur için kilidi tutan `WriteLockHolder`.
        self._followup_locks: Dict[str, WriteLockHolder] = {}

    # -- yardımcılar ----------------------------------------------------

    @property
    def office(self) -> Optional[DeskOffice]:
        return self.offices.get(self.office_name)

    def _workdir(self) -> Path:
        """Ofisin çalışma dizini (OFFICE.md `workdir`, yoksa ofis klasörü)."""
        try:
            return self.offices.workdir(self.office_name)
        except Exception:
            return self.offices.office_dir(self.office_name)

    def _state_path(self) -> Path:
        return self.offices.office_dir(self.office_name) / STATE_FILENAME

    def _state(self) -> dict:
        try:
            return json.loads(self._state_path().read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _card_state(self, card_id: str) -> dict:
        return dict(self._state().get(card_id) or {})

    def _save_card_state(self, card_id: str, **fields) -> dict:
        """Kart durumunu birleştirerek yazar; dosya tek kaynak olduğu için atomik."""
        with self._lock:
            state = self._state()
            entry = dict(state.get(card_id) or {})
            entry.update(fields)
            state[card_id] = entry
            path = self._state_path()
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                logger.warning("Ofis durumu yazılamadı: %s", path)
            return entry

    # -- ofis konuşması (Faz 8 / 3) -------------------------------------

    def conversation_key(self) -> str:
        """
        `ConversationMap` anahtarı: `office:<ad>`.

        Önek şart: kullanıcının sohbet konuşmaları da aynı dosyada duruyor ve
        ofis adı bir sohbet kimliğiyle çakışırsa iki oturum birbirine karışırdı.
        """
        return f"office:{self.office_name}"

    def office_conversation_id(self, provider: str) -> Optional[str]:
        """Ofisin sağlayıcı başına süren konuşma kimliği (yoksa None)."""
        entry = self._state().get(OFFICE_STATE_KEY) or {}
        value = (entry.get("conversation_id") or {}).get((provider or "").lower())
        return str(value) if value else None

    def _other_provider_conversation(self, provider: str) -> str:
        """Ofisin konuşması varsa ama BAŞKA sağlayıcıdaysa o sağlayıcının adı."""
        entry = self._state().get(OFFICE_STATE_KEY) or {}
        conv = entry.get("conversation_id") or {}
        provider = (provider or "").lower()
        for name, value in conv.items():
            if value and (name or "").lower() != provider:
                return str(name)
        return ""

    def agent_provider(self, spec, office: DeskOffice) -> str:
        """
        Bir ofis ajanının koşacağı sağlayıcı.

        Sıra: (1) ajanın kendi geçerli `provider` alanı, (2) OFİSİN varsayılanı
        — yani orkestratörün sağlayıcısı, (3) genel varsayılan. İkinci basamak
        şart: değerlendirici sağlayıcısı belirtilmemişken genel varsayılana
        düşülüyordu ve `config.provider` orkestratörünkinden farklıysa plan
        turu bir sağlayıcıda, değerlendirme başka bir sağlayıcıda açılıyordu
        (ofis konuşması sağlayıcı başına anahtarlı olduğu için de sürmüyordu).
        """
        provider = ((getattr(spec, "provider", "") if spec else "") or "").strip().lower()
        if provider in VALID_PROVIDERS:
            return provider
        provider = ((office.default_provider if office else "") or "").strip().lower()
        if provider in VALID_PROVIDERS:
            return provider
        return default_provider()

    def remember_office_conversation(self, provider: str, conversation_id: str) -> None:
        """
        Kimliği ofis `state.json`'ına ve `ConversationMap`'e yazar.

        state.json birincil kaynak: ofis klasörü silinince kimlik de gider.
        ConversationMap kopyası yalnızca kimlik panelinin ofis oturumlarını
        görebilmesi için.
        """
        provider = (provider or "").lower()
        if not provider or not conversation_id:
            return
        with self._lock:
            entry = dict(self._state().get(OFFICE_STATE_KEY) or {})
            conv = dict(entry.get("conversation_id") or {})
            if conv.get(provider) == str(conversation_id):
                return
            conv[provider] = str(conversation_id)
        self._save_card_state(OFFICE_STATE_KEY, conversation_id=conv)
        try:
            from entropy.core.identity import conversation_map

            conversation_map.set(self.conversation_key(), provider, str(conversation_id))
        except Exception:
            logger.debug("Ofis konuşması eşlemeye yazılamadı: %s", self.office_name)

    def forget_office_conversation(self) -> None:
        """Ofis arşivlenince/silinince konuşma kimliği düşer."""
        try:
            from entropy.core.identity import conversation_map

            conversation_map.forget(self.conversation_key())
        except Exception:
            pass
        try:
            with self._lock:
                state = self._state()
                if OFFICE_STATE_KEY in state:
                    state[OFFICE_STATE_KEY].pop("conversation_id", None)
                    self._state_path().write_text(
                        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
        except OSError:
            pass

    def _emit(self, card_id: str, phase: str) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.office_progress.emit(self.office_name, card_id, phase)
        except Exception:
            pass

    def _budget(self, card_id: str) -> int:
        """Geçerli token tavanı: kartınki varsa o, yoksa ofisinki."""
        card = self.board.get(card_id)
        if card is not None and int(card.budget_tokens or 0) > 0:
            return int(card.budget_tokens)
        office = self.office
        return int(office.budget_tokens) if office else 0

    @staticmethod
    def ledger_tokens(ledger_task_id: str) -> Optional[int]:
        """
        Ledger'daki GERÇEK token maliyeti; kayıt/usage yoksa None.

        Köprü `usage` alanını görev bitince ledger'a yazıyor. Bus'taki
        `token_usage_updated` sinyali kullanılmıyor: görev kimliği taşımadığı
        için eşzamanlı iki alt kartın maliyeti birbirine karışırdı.
        """
        try:
            from entropy.core.task_ledger import task_ledger

            rec = task_ledger.get_task(ledger_task_id)
        except Exception:
            return None
        if not rec:
            return None
        value = rec.get("total_tokens")
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _spend(self, card_id: str, tokens: int, ledger_task_id: Optional[str] = None) -> bool:
        """
        Harcamayı işler; bütçe aşılmadıysa True.

        `ledger_task_id` verilirse maliyet önce SQLite ledger'dan (sağlayıcının
        bildirdiği gerçek `total_tokens`) okunur; yalnızca ledger'da usage yoksa
        karakter/4 tahminine düşülür. Tahmin gerçek maliyetin onda birini bile
        göstermiyordu ve bütçe koruması fiilen çalışmıyordu.

        Aşıldığında False döner ve çağıran zinciri durdurur — kontrol harcamadan
        sonra yapılır çünkü maliyet ancak çağrı bittikten sonra bilinir; önemli
        olan bir SONRAKİ çağrının engellenmesi ve sürenlerin öldürülmesi.
        """
        real = self.ledger_tokens(ledger_task_id) if ledger_task_id else None
        amount = int(real) if real is not None else int(tokens)
        state = self._card_state(card_id)
        entry = self._save_card_state(
            card_id,
            tokens=int(state.get("tokens", 0)) + amount,
            measured_tokens=int(state.get("measured_tokens", 0)) + (int(real) if real is not None else 0),
            estimated_tokens=int(state.get("estimated_tokens", 0)) + (0 if real is not None else int(tokens)),
        )
        budget = self._budget(card_id)
        return not (budget and entry.get("tokens", 0) > budget)

    def _remaining_budget(self, card_id: str) -> Optional[int]:
        """Kalan token bütçesi; tavan tanımsızsa None (sınırsız)."""
        budget = self._budget(card_id)
        if not budget:
            return None
        return int(budget) - int(self._card_state(card_id).get("tokens", 0))

    def subcard_estimate(self, child: Optional[TaskCard] = None) -> Dict[str, object]:
        """
        Alt kart için uyarlanabilir maliyet tahmini (Faz 8 / 2).

        İstem uzunluğu kartın hedef+ölçüt metninden okunur; ofisin geçmişi
        varsa medyan baskındır. Sabit 30k tahmini küçük kartlarda bütçeyi boş
        yere kilitliyor, büyüklerde ise yetmiyordu.
        """
        prompt_chars = 0
        if child is not None:
            prompt_chars = len(child.goal or "") + sum(len(c or "") for c in (child.criteria or []))
            prompt_chars += len(child.title or "") + len(child.notes or "")
        return estimate_subcard_tokens(
            prompt_chars=prompt_chars, office=self.office_name, board=self.board
        )

    def _can_afford(self, card_id: str, estimate: int = SUBCARD_TOKEN_ESTIMATE) -> bool:
        """
        Bir sonraki alt kart çağrısı bütçeye SIĞIYOR mu (çağrıdan ÖNCE)?

        Faz 7 (C1b): eski düzen "harca, sonra bak"tı — maliyet ancak çağrı
        bitince bilindiği için bütçe her seferinde bir alt kart boyu aşılıyordu.
        Kalan bütçe alt kart tahminine eşit ya da altındaysa çağrı hiç
        başlatılmaz.
        """
        remaining = self._remaining_budget(card_id)
        if remaining is None:
            return True
        return remaining > int(estimate)

    def _terminate_children(self, card_id: str) -> List[str]:
        """Süren alt kartların köprü süreçlerini öldürür; durdurulan kimlikler."""
        stopped: List[str] = []
        card = self.board.get(card_id)
        if card is None:
            return stopped
        for child in self._children(card):
            if child.status != "running":
                continue
            try:
                bridge = TaskBoard.bridge_for(child.provider or default_provider(),
                                              bridge_factory=self.bridge_factory)
            except Exception:
                bridge = None
            if bridge is not None:
                try:
                    bridge.terminate_background_task(f"card-{child.id}")
                except Exception:
                    logger.warning("Alt kart süreci durdurulamadı: %s", child.id)
            try:
                self.board.update(replace(
                    child, status="failed", finished_at=_now(),
                    summary=(child.summary or "") + "\nBütçe aşımı nedeniyle durduruldu.",
                ))
            except Exception:
                pass
            stopped.append(child.id)
        return stopped

    def _fail_budget(self, card_id: str, phase_label: str) -> None:
        """
        Bütçe aşımını kapatır: süren alt kartları ÖLDÜR, üst kartı `failed` yap.

        Alt kartları öldürmeden üst kartı başarısız saymak kotayı korumuyordu;
        süren iki agy süreci bütçe aşıldıktan sonra da token yakmayı
        sürdürüyordu.
        """
        spent = int(self._card_state(card_id).get("tokens", 0))
        stopped = self._terminate_children(card_id)
        reason = (
            f"Bütçe (budget_tokens={self._budget(card_id)}) {phase_label} adımında aşıldı; "
            f"harcanan ≈ {spent} token."
        )
        if stopped:
            reason += f" Durdurulan alt kart: {', '.join(stopped)}."
        self._fail(card_id, reason)

    def _children(self, card: TaskCard) -> List[TaskCard]:
        out: List[TaskCard] = []
        for child_id in card.children or []:
            child = self.board.get(child_id)
            if child is not None:
                out.append(child)
        return out

    def _fail(self, card_id: str, reason: str, terminal_status: str = "failed") -> None:
        card = self.board.get(card_id)
        if card is not None:
            summary = (card.summary or "").strip()
            summary = f"{summary}\n\n{reason}".strip() if summary else reason
            self.board.update(replace(card, status="failed", finished_at=_now(), summary=summary))
        self._save_card_state(card_id, phase=PHASE_FAILED)
        self._release(card_id)
        self._emit(card_id, PHASE_FAILED)
        # TERMİNAL SÖZLEŞMESİ: başarısız/iptal de bir sondur. Bus sinyali
        # yetmiyordu — uygulama kapalıyken biten zincirin sonucu hiçbir yere
        # yazılmıyor ve kart dışarıdan "asılı" görünüyordu.
        emit_terminal(card_id, self.office_name, terminal_status, reason,
                      vault_path=self.board.vault_path)

    def _claim(self, card_id: str) -> bool:
        with OfficeHarness._active_lock:
            if card_id in OfficeHarness._active:
                return False
            OfficeHarness._active[card_id] = self
            return True

    def _release(self, card_id: str) -> None:
        with OfficeHarness._active_lock:
            OfficeHarness._active.pop(card_id, None)

    # -- 1. planlama ----------------------------------------------------

    def start(self, card_id: str) -> bool:
        """Üst kartı ofise alır ve planlama çağrısını başlatır."""
        office = self.office
        if office is None:
            return False
        card = self.board.get(card_id)
        if card is None:
            return False
        if not self._claim(card_id):
            return False

        card = replace(card, office=self.office_name, status="running", started_at=_now())
        self.board.update(card)
        self._save_card_state(card_id, phase=PHASE_PLANNING, tokens=0, eval_round=0)
        self._emit(card_id, PHASE_PLANNING)

        prompt = self.build_plan_prompt(office, card)
        ok = self._call_agent(
            agent_name=office.orchestrator,
            office=office,
            task_id=f"office-plan-{card_id}",
            task_name=f"{self.office_name}: planlama",
            prompt=prompt,
            on_result=lambda text, ok, _c=card_id: self._on_plan(_c, text, ok),
        )
        if not ok:
            self._fail(card_id, "Planlama başlatılamadı (orkestratör ajanı ya da köprü yok).")
        return ok

    # -- B1: bilgi tazeleme -------------------------------------------

    def _memory_context(self, task: str) -> str:
        """
        Ofis belleğinden planlama bağlamı (`orchestrator_context`).

        İmza sabittir: `orchestrator_context(office, task)`. Bellek katmanı
        yoksa/patlarsa boş döner — ajan katmanı bellek katmanına bağımlı olamaz.
        """
        try:
            from entropy.memory.office_graph import orchestrator_context  # type: ignore
        except Exception:
            return ""
        try:
            return (orchestrator_context(self.office_name, task) or "").strip()
        except Exception:
            logger.warning("Ofis bağlamı okunamadı: %s", self.office_name)
            return ""

    def _recent_reports(self, count: int = CONTEXT_REPORT_COUNT) -> str:
        """Ofisin son `count` raporundan kısa özet bloğu."""
        try:
            reports_dir = self.offices.reports_dir(self.office_name)
            files = sorted(
                (p for p in reports_dir.glob("*.md") if p.is_file()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:count]
        except OSError:
            return ""
        blocks = []
        for path in files:
            try:
                body = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            blocks.append(f"### {path.stem}\n{trim_to_sections(body, CONTEXT_REPORT_CHARS)}")
        return "\n\n".join(blocks)

    # -- Faz 10-A: ofis çalışma dosyaları --------------------------------

    def workspace_paths(self) -> Dict[str, Path]:
        """
        Ofisin pano/mimari/kural dosyalarının MUTLAK yolları.

        Bellek katmanının `office_workspace.ensure_workspace` fonksiyonu varsa
        önce o çağrılır (dosyaları o üretir); yoksa harness kendisi oluşturur.
        Ajan katmanı bellek katmanına bağımlı olamaz: pano dosyası yoksa da
        işçiler doğabilmeli.
        """
        base = self.offices.office_dir(self.office_name)
        paths = {
            "board": base / BOARD_FILENAME,
            "architecture": base / ARCHITECTURE_FILENAME,
            "rules": base / RULES_FILENAME,
        }
        try:
            from entropy.memory import office_workspace  # type: ignore

            result = _flex_call(
                office_workspace.ensure_workspace,
                office=self.office_name,
                vault_path=self.board.vault_path,
            )
            if isinstance(result, dict):
                for key in list(paths):
                    value = result.get(key)
                    if value:
                        paths[key] = Path(str(value))
                return paths
        except Exception:
            logger.debug("Ofis çalışma alanı bellek katmanından alınamadı: %s", self.office_name)
        try:
            base.mkdir(parents=True, exist_ok=True)
            for key, path in paths.items():
                if not path.exists():
                    path.write_text(f"# {path.stem}\n\n(henüz boş)\n", encoding="utf-8")
        except OSError:
            logger.warning("Ofis çalışma dosyaları yazılamadı: %s", base)
        return paths

    def spawn_section(self, card_id: Optional[str] = None, agent: str = "") -> str:
        """
        DOĞUŞ TALİMATI: ajan iş yapmadan ÖNCE okuyacağı dosyaların mutlak yolları.

        Kullanıcının bağlayıcı tarifi: "ajan doğunca önce BOARD/ARCHITECTURE
        dosyalarını okur". Bu yüzden bölüm hem plan hem alt kart isteminin EN
        BAŞINDA durur. Bellek katmanının `spawn_instruction`ı varsa metni o
        üretir (kontrol noktası özeti ve onaylı kuralları da katar); yoksa
        harness aynı sözleşmenin yalın hâlini yazar.
        """
        try:
            from entropy.memory import office_workspace  # type: ignore

            self.workspace_paths()  # dosyalar yoksa önce kurulsun
            text = _flex_call(
                office_workspace.spawn_instruction,
                office=self.office_name,
                card_id=card_id,
                agent=agent or None,
                vault_path=self.board.vault_path,
            )
            if isinstance(text, str) and text.strip():
                return f"{SPAWN_HEADER}\n{text.strip()}"
        except Exception:
            logger.debug("spawn_instruction bellek katmanından alınamadı: %s", self.office_name)
        paths = self.workspace_paths()
        lines = [
            SPAWN_HEADER,
            f"- PANO: {paths['board']}",
            f"- MİMARİ: {paths['architecture']}",
            f"- KURALLAR: {paths['rules']}",
            "Bu üç dosyayı işe başlamadan önce oku; panodaki kendi kartından "
            "başkasının işine girme.",
        ]
        card = self.board.get(card_id) if card_id else None
        if card is not None and card.checkpoint:
            lines.append(f"- KONTROL NOKTASI: {card.checkpoint}")
        rules = self.approved_rules_section()
        return "\n".join(lines) + (f"\n\n{rules}" if rules else "")

    def approved_rules_section(self) -> str:
        """Onaylı proje kuralları bölümü (bellek katmanı yoksa RULES.md gövdesi)."""
        try:
            from entropy.memory import promoted_rules  # type: ignore

            text = _flex_call(
                promoted_rules.rules_section,
                office=self.office_name,
                vault_path=self.board.vault_path,
            )
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception:
            logger.debug("Onaylı kurallar okunamadı: %s", self.office_name)
        return ""

    def render_board(self) -> Optional[Path]:
        """
        Panoyu (BOARD.md) kart durumlarından yeniden yazar.

        Her kart değişiminden sonra çağrılır: pano dosyası ajanların ORTAK
        gerçekliği; koşu sırasında güncellenmezse yeni doğan işçi bitmiş işi
        yeniden yapmaya kalkıyordu.
        """
        try:
            from entropy.memory import office_workspace  # type: ignore

            result = _flex_call(
                office_workspace.render_board,
                office=self.office_name,
                vault_path=self.board.vault_path,
            )
            if result:
                return Path(str(result))
        except Exception:
            logger.debug("render_board bellek katmanında yok: %s", self.office_name)
        path = self.workspace_paths()["board"]
        try:
            cards = self.board.list(office=self.office_name)
        except Exception:
            return None
        lines = [f"# {self.office_name} — pano", "", f"Güncellendi: {_now()}", ""]
        parents = [c for c in cards if not c.parent]
        for parent in parents:
            lines.append(f"## {parent.title} · {parent.status} · `{parent.id}`")
            for child in self._children(parent):
                mark = "x" if child.status == "done" else " "
                extra = f" · kanıt: {'var' if child.proof else 'yok'}"
                lines.append(
                    f"- [{mark}] {child.title} · {child.agent or '-'} · "
                    f"{child.status}{extra} · `{child.id}`"
                )
            lines.append("")
        try:
            path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        except OSError:
            logger.warning("Pano yazılamadı: %s", path)
            return None
        return path

    def update_architecture(self, notes) -> Optional[Path]:
        """Plandaki `architecture_notes` alanını ARCHITECTURE.md'ye ekler."""
        if isinstance(notes, str):
            notes = [notes]
        rows = [str(n).strip() for n in (notes or []) if str(n or "").strip()]
        if not rows:
            return None
        try:
            from entropy.memory import office_workspace  # type: ignore

            result = _flex_call(
                office_workspace.update_architecture,
                office=self.office_name,
                text="\n".join(rows),
                author=(self.office.orchestrator if self.office else "") or "",
                vault_path=self.board.vault_path,
            )
            if result:
                return Path(str(result))
        except Exception:
            logger.debug("update_architecture bellek katmanında yok: %s", self.office_name)
        path = self.workspace_paths()["architecture"]
        try:
            body = path.read_text(encoding="utf-8") if path.exists() else f"# {path.stem}\n"
            body = body.rstrip() + "\n\n## " + _now() + "\n" + "\n".join(f"- {r}" for r in rows) + "\n"
            path.write_text(body, encoding="utf-8")
        except OSError:
            logger.warning("Mimari notu yazılamadı: %s", path)
            return None
        return path

    # -- Faz 10-A: kontrol noktası / kanıt / kural adayı ------------------

    def record_checkpoint(self, card: TaskCard, text: str) -> Optional[str]:
        """
        Çıktıdaki `[KONTROL NOKTASI]` bloğunu dosyaya yazar; yol döner.

        Blok yoksa hiçbir şey yazılmaz (yanlış bir "kaldığın yer" özeti,
        hiç özet olmamasından kötüdür).
        """
        block = parse_checkpoint(text or "")
        if not block:
            return None
        try:
            from entropy.memory import checkpoints  # type: ignore

            fields = checkpoints.parse_checkpoint_block(text or "") or {}
            result = _flex_call(
                checkpoints.write_checkpoint,
                office=self.office_name,
                card_id=card.id,
                author=card.agent or "",
                summary=str(fields.get("summary") or block[:400]),
                done=str(fields.get("done") or ""),
                next_steps=str(fields.get("next_steps") or ""),
                files_touched=fields.get("files_touched") or [],
                tests=str(fields.get("tests") or ""),
                vault_path=self.board.vault_path,
            )
            if result:
                return str(result)
        except Exception:
            logger.debug("write_checkpoint bellek katmanında yok: %s", self.office_name)
        path = self.offices.office_dir(self.office_name) / CHECKPOINT_DIRNAME / f"{card.id}.md"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"# {card.title or card.id}\n\nGüncellendi: {_now()}\n\n{CHECKPOINT_TAG}\n{block}\n",
                encoding="utf-8",
            )
        except OSError:
            logger.warning("Kontrol noktası yazılamadı: %s", path)
            return None
        return str(path)

    def read_proof(self, text: str, needs_write: bool = True) -> Optional[dict]:
        """
        `[KANIT]` bloğu -> {"text", "green"}; blok yoksa None.

        Bellek katmanının `parse_proof_block`ı KESİN bir sonuç veriyorsa
        (`ok` True/False) o kazanır: "Sonuç:" alanını alan bazlı okur. Alan
        tanınmadığında (ok=None) harness'ın kendi sezgisel okuması konuşur;
        böylece bellek katmanı olmadan da kural yürürlükte kalır.
        """
        local = parse_proof(text or "", needs_write=needs_write)
        try:
            from entropy.memory import checkpoints  # type: ignore

            data = checkpoints.parse_proof_block(text or "")
        except Exception:
            data = None
        if isinstance(data, dict) and data.get("ok") is not None:
            body = local["text"] if local else " · ".join(
                str(data.get(k) or "") for k in ("command", "raw_result", "summary")
            ).strip(" ·")
            return {"text": body, "green": bool(data["ok"])}
        return local

    def resume_section(self, card: TaskCard) -> str:
        """
        Yeniden koşan kartın "kaldığın yer" bölümü.

        Sözleşme: yeniden koşuya ESKİ ÇIKTI ya da sohbet geçmişi girmez, yalnızca
        kontrol noktası girer. Sebep: eski çıktının tamamı hem bağlamı hem kotayı
        şişiriyor, hem de ajan bitmiş işi yeniden anlatmaya başlıyordu.
        """
        if not card.checkpoint:
            return ""
        try:
            from entropy.memory import checkpoints  # type: ignore

            text = _flex_call(
                checkpoints.resume_section,
                office=self.office_name,
                card_id=card.id,
                vault_path=self.board.vault_path,
            )
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception:
            logger.debug("resume_section bellek katmanında yok: %s", self.office_name)
        try:
            body = Path(card.checkpoint).read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        return (
            "[KALDIĞIN YER — kontrol noktası]\n"
            f"Kaynak: {card.checkpoint}\n{body}\n"
            "Bu noktadan SÜRDÜR; bitmiş adımları yeniden yapma. Önceki sohbet "
            "sende yok, tek gerçek kaynak bu blok ve pano."
        )

    def collect_rule_candidates(self, agent: str, text: str, source: str = "") -> List[str]:
        """
        Çıktıdaki `[KURAL] …` satırlarını ADAY olarak kaydeder ve sinyal yayar.

        Ajan keşfettiği kuralı belleğe kendisi yazamaz (kullanıcının kuralı):
        aday kuyruğa düşer, onayı kullanıcı verir.
        """
        rules = parse_rule_candidates(text or "")
        if not rules:
            return []
        stored: List[str] = []
        for rule in rules:
            try:
                from entropy.memory import promoted_rules  # type: ignore

                result = _flex_call(
                    promoted_rules.propose_rule,
                    office=self.office_name,
                    agent=agent or "",
                    text=rule,
                    source=source or "",
                    vault_path=self.board.vault_path,
                )
                # `propose_rule` kural olmayan metne None döner (log satırı,
                # yol, çok kısa cümle): o zaman aday da açılmaz.
                if result is not None:
                    stored.append(rule)
                continue
            except Exception:
                logger.debug("propose_rule bellek katmanında yok: %s", self.office_name)
            path = self.offices.office_dir(self.office_name) / RULE_CANDIDATES_FILENAME
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(f"- [ ] {rule} · {agent or '-'} · kaynak: {source or '-'}\n")
                stored.append(rule)
            except OSError:
                logger.warning("Kural adayı yazılamadı: %s", path)
        if stored:
            # UI sinyali: çekirdek olay yolunda henüz yoksa sessizce atlanır.
            try:
                from entropy.core.event_bus import bus

                signal = getattr(bus, "rules_updated", None)
                if signal is not None:
                    signal.emit(self.office_name, len(stored))
            except Exception:
                logger.debug("rules_updated sinyali yayılamadı: %s", self.office_name)
        return stored

    # -- proje deposu ve kart worktree'si (Faz 10-C) ---------------------

    def _project_of(self, card: TaskCard, parent: Optional[TaskCard] = None):
        """Kartın (ya da üstünün) bağlı olduğu ofis projesi; yoksa `None`."""
        name = (card.project or "") or ((parent.project if parent else "") or "")
        if not name:
            return None
        try:
            return self.offices.get_project(self.office_name, name)
        except Exception:
            return None

    def _worktree_eligible(self, child: TaskCard, parent: Optional[TaskCard] = None) -> bool:
        """Bu alt kart izole bir çalışma ağacında koşabilir mi (proje deposu var mı)."""
        if (child.worktree or "").strip():
            return True
        project = self._project_of(child, parent)
        return bool(project is not None and (project.repo_path or "").strip())

    def _ensure_worktree(self, child: TaskCard, parent: Optional[TaskCard] = None) -> str:
        """
        Alt kartın izole çalışma ağacını açar; yolunu döndürür ("" = açılmadı).

        Worktree açma BAŞARISIZ olursa kart ölmez: eski tek-dizin yoluna düşer
        ve nedeni kart notuna yazılır. Özellik opt-in'dir — projede `repo_path`
        yoksa bu kod yolu hiç çalışmaz.
        """
        if (child.worktree or "").strip() and Path(child.worktree).is_dir():
            return child.worktree
        project = self._project_of(child, parent)
        repo = (project.repo_path or "").strip() if project is not None else ""
        if not repo:
            return ""
        from entropy.agents import worktrees as _wt

        try:
            path = _wt.create_worktree(
                repo,
                self.office_name,
                child.id,
                base_branch=(project.base_branch or ""),
                root=(project.worktree_root or None),
            )
        except _wt.WorktreeError as exc:
            note = f"Worktree açılamadı ({exc}); kart ofis çalışma dizininde koşuyor."
            logger.warning("%s: %s", child.id, note)
            if note not in (child.notes or ""):
                self.board.update(replace(
                    child, notes=((child.notes + "\n") if child.notes else "") + note
                ))
            return ""
        self.board.update(replace(
            child, worktree=str(path), branch=_wt.branch_name(child.id)
        ))
        return str(path)

    def _child_lead_sections(self, child: TaskCard) -> List[str]:
        """Alt kart isteminin baş bölümleri: doğuş talimatı, kaldığın yer, yorum."""
        spawn = self.spawn_section(child.id, agent=child.agent or "")
        sections = [spawn]
        # Bellek katmanının doğuş talimatı kontrol noktasını zaten katmış
        # olabilir; aynı blok ikinci kez isteme girmesin.
        if "[KALDIĞIN YER" not in spawn:
            resume = self.resume_section(child)
            if resume:
                sections.append(resume)
        try:
            comments = comments_section(card_comments(
                self.office_name,
                [child.id, child.parent],
                vault_path=self.board.vault_path,
            ))
        except Exception:
            comments = ""
        if comments:
            sections.append(comments)
        return [s for s in sections if s]

    def _can_web_search(self) -> bool:
        """
        Ofiste web araması yapabilen bir ajan var mı?

        Orkestratör ÖNCE bakılır: `office.members` orkestratörü kasten dışarıda
        bırakıyor (desk_registry `_read`), bu yüzden yalnızca üyelere bakan eski
        kontrol her zaman False dönüyor ve araştırma adımı hiç istenmiyordu —
        oysa araştırmayı asıl yapacak olan, `read-only` politikasıyla
        `WebFetch, WebSearch` araçları verilmiş orkestratörün kendisi.
        """
        office = self.office
        if office is None:
            return False
        names = [office.orchestrator or ""] + list(office.members or [])
        for name in names:
            if not name:
                continue
            spec = self.registry.get(name)
            if spec is None:
                continue
            if self._spec_has_web_tools(spec):
                return True
        return False

    @staticmethod
    def _spec_has_web_tools(spec) -> bool:
        """Ajanın derlenmiş araç listesinde WebSearch var mı?"""
        try:
            from entropy.agents.compile import _TOOLS_BY_POLICY, is_orchestrator

            policy = "read-only" if is_orchestrator(spec) else (spec.tools_policy or "").lower()
            return "WebSearch" in (_TOOLS_BY_POLICY.get(policy, "") or "")
        except Exception:
            return (getattr(spec, "tools_policy", "") or "").strip().lower() in (
                "read-only", "readonly", "full",
            )

    def _write_research_notes(self, card: TaskCard, data: Optional[dict]) -> List[str]:
        """
        Plandaki `research_notes` alanını ofis grafına `kind="bulgu"` notu yazar.

        Bellek API'si guard altında: `OfficeGraph` yoksa notlar sessizce
        atlanır ve planlama yine ilerler.
        """
        raw = (data or {}).get("research_notes") if isinstance(data, dict) else None
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list) or not raw:
            return []
        try:
            from entropy.memory.office_graph import OfficeGraph  # type: ignore
        except Exception:
            return []
        try:
            graph = OfficeGraph(self.office_name, self.board.vault_path)
        except Exception:
            return []
        written: List[str] = []
        for item in raw:
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("note") or "").strip()
                body = str(item.get("body") or item.get("detail") or "").strip()
                # Kaynak bağlantısı notun gövdesine yazılır: bulgunun nereden
                # geldiği sonradan denetlenebilmeli (Faz 10-A / 5).
                link = str(item.get("source") or item.get("url") or "").strip()
                if link:
                    body = (body + f"\n\nKaynak: {link}").strip()
            else:
                title = str(item or "").strip()
                body = ""
            if not title:
                continue
            try:
                graph.add_note(kind="bulgu", title=title[:160], body=body,
                               source=f"plan:{card.id}")
            except Exception:
                logger.warning("Araştırma notu yazılamadı: %s", title[:60])
                continue
            written.append(title)
        return written

    def build_plan_prompt(self, office: DeskOffice, card: TaskCard) -> str:
        members = []
        for name in office.members or []:
            spec = self.registry.get(name)
            if spec is None:
                continue
            skills = ", ".join(spec.skills) if spec.skills else "-"
            members.append(f"- {spec.name} ({spec.role or 'genel'}) · {spec.description} · yetenekler: {skills}")
        criteria = "\n".join(f"- {c}" for c in (card.criteria or [])) or "- (belirtilmedi)"
        # Posta kutusu planlamadan ÖNCE okunur: kullanıcının `/ask <ofis>` ile
        # bıraktığı soru/talimat plana girmezse kutu yalnızca arşiv olurdu.
        # Okunanlar `mark_read` ile işaretlenir; aynı yön ikinci planlamada
        # tekrar enjekte edilip alt görevleri çoğaltmasın diye.
        try:
            inbox = instructions_section(
                pending_instructions(self.office_name, vault_path=self.board.vault_path)
            )
        except Exception:
            inbox = ""
        inbox_block = f"{inbox}\n\n" if inbox else ""
        # Proje bağlamı: kart bir ofis projesine bağlıysa projenin hedefi ve
        # tüzüğü plana girer; aksi hâlde orkestratör her kartı bağlamsız,
        # sıfırdan bir iş sanıyordu.
        project_block = ""
        if card.project:
            try:
                project = self.offices.get_project(self.office_name, card.project)
            except Exception:
                project = None
            if project is not None:
                project_block = trim_to_sections(
                    f"[PROJE — {project.name}]\n{project.goal}\n"
                    f"{(project.charter or '').strip()}",
                    PLAN_PROJECT_MAX_CHARS,
                ) + "\n\n"
        # B1 — bilgi tazeleme: orkestratör planlamadan ÖNCE ofis belleğini ve
        # son raporları görür. Eskiden her planlama sıfır bağlamla başlıyor ve
        # aynı iş turlarca yeniden keşfediliyordu.
        context_block = ""
        memory_ctx = self._memory_context(card.goal or card.title or "")
        reports_ctx = self._recent_reports()
        if memory_ctx or reports_ctx:
            parts = ["[BİLGİ TAZELEME]"]
            if memory_ctx:
                parts.append(memory_ctx)
            if reports_ctx:
                parts.append(f"[SON RAPORLAR]\n{reports_ctx}")
            # Bütçe: bellek + 3 rapor birleşince blok 5k karakteri aşabiliyordu.
            context_block = trim_to_sections(
                "\n\n".join(parts), PLAN_CONTEXT_MAX_CHARS
            ) + "\n\n"
        # Araştırma notu alt adımı yalnızca kadroda WebSearch yetkili ajan
        # varsa istenir; yoksa orkestratör dolduramayacağı bir alan uyduruyordu.
        research_block = ""
        research_schema = ""
        if self._can_web_search():
            research_block = (
                "[ARAŞTIRMA NOTU]\nPlanlamadan önce bilgini tazele: WebSearch "
                "yetkin var (araştırmayı sen yaparsın, kod yazmazsın).\n"
                f"- En çok {MAX_RESEARCH_QUERIES} arama yap; sonra dur ve planla.\n"
                "- Her bulgunun KAYNAK BAĞLANTISINI (`source`, http ile başlayan "
                "URL) yaz; kaynaksız bulgu belleğe alınmaz.\n"
                "- Bulguları `research_notes` alanına kısa maddeler hâlinde yaz; "
                "bunlar ofis belleğine 'bulgu' notu olarak kaydedilecek.\n\n"
            )
            research_schema = (
                ',\n "research_notes": [{"title": "...", "body": "...", '
                '"source": "https://..."}]'
            )
        # Şemadaki `provider` örneği KADRODAN türer: sabit "agy" yazıldığında
        # model, kadroda yalnızca Claude ajanı olsa bile plana `agy` yazmaya
        # eğilimliydi ve claude-yalnız kurulum sessizce agy'ye düşüyordu.
        plan_provider = self._roster_provider(office)
        # Doğuş talimatı EN BAŞTA: orkestratör de bir ajandır ve planlamadan
        # önce panoyu/mimariyi/kuralları okumak zorundadır.
        spawn = self.spawn_section(card.id)
        prompt = (
            f"{spawn}\n\n"
            f"[OFİS TÜZÜĞÜ — {office.name}]\n{office.charter or office.purpose}\n\n"
            f"{project_block}"
            f"{context_block}"
            f"{inbox_block}"
            f"{research_block}"
            f"[ÜST KART]\nBaşlık: {card.title}\nHedef: {card.goal or card.title}\n"
            f"Kabul ölçütleri:\n{criteria}\n\n"
            f"[KADRON]\n" + ("\n".join(members) or "- (henüz alt ajan yok)") + "\n\n"
            f"[İSTENEN ÇIKTI]\nEn çok {MAX_SUBTASKS} alt görev. Kadronda uygun ajan "
            "yoksa `new_agents` ile yeni alt ajan tanımla ve görevi ona ata. "
            "Sen kod YAZMAZSIN, dosya değiştirmezsin: yalnızca plan üretirsin. "
            "Yalnızca TEK bir ```json kod bloğu yaz, başka hiçbir şey yazma:\n"
            '{"subtasks": [{"title": "...", "goal": "...", "criteria": ["..."], '
            '"agent": "<kadrondaki ya da new_agents ile tanımladığın ad>", '
            f'"provider": "{plan_provider}", "model": ""}}],\n'
            ' "new_agents": [{"name": "...", "role": "worker", "description": "...", '
            f'"provider": "{plan_provider}", "model": "", "tools_policy": "read-write", '
            '"prompt": "..."}],\n'
            ' "architecture_notes": ["(isteğe bağlı) mimari kararın, ARCHITECTURE.md\'ye eklenecek"]'
            f"{research_schema}" + "}"
        )
        # Ölçüm günlüğe düşer: "38k token" gibi bir sayı bir daha yalnızca
        # kullanım kaydından değil, istem uzunluğundan da izlenebilsin.
        logger.info(
            "Plan istemi: %d karakter (bağlam %d, proje %d, kutu %d, doğuş %d)",
            len(prompt), len(context_block), len(project_block),
            len(inbox_block), len(spawn),
        )
        if len(prompt) > PLAN_PROMPT_MAX_CHARS:
            # Tavan aşıldıysa ŞEMA değil BAĞLAM kırpılır: şema bozulursa plan
            # ayrıştırılamaz ve tur tamamen boşa gider.
            overflow = len(prompt) - PLAN_PROMPT_MAX_CHARS
            for block in (context_block, project_block, inbox_block):
                if overflow <= 0 or not block:
                    continue
                keep = max(0, len(block) - overflow - 2)
                shrunk = (trim_to_sections(block.strip(), keep) + "\n\n") if keep else ""
                overflow -= len(block) - len(shrunk)
                prompt = prompt.replace(block, shrunk, 1)
            logger.info("Plan istemi bütçeye kırpıldı: %d karakter", len(prompt))
        return prompt

    def _roster_provider(self, office: DeskOffice) -> str:
        """
        Plan şemasında örneklenecek sağlayıcı: kadrodaki ilk üyenin sağlayıcısı,
        yoksa ofis varsayılanı, o da yoksa yapılandırma varsayılanı.
        """
        for name in office.members or []:
            spec = self.registry.get(name)
            provider = (getattr(spec, "provider", "") or "").strip().lower()
            if provider in VALID_PROVIDERS:
                return provider
        provider = (office.default_provider or "").strip().lower()
        return provider if provider in VALID_PROVIDERS else default_provider()

    def _apply_new_agents(self, data: Optional[dict]) -> List[str]:
        """
        Plandaki `new_agents` bölümünü ofisin ajan defterine yazar.

        Var olan bir adı EZMEZ: orkestratör her turda aynı ajanı yeniden
        tanımlamaya eğilimli ve üzerine yazmak kullanıcının elle düzelttiği
        istemi sessizce siliyordu. Orkestratör rolü de kabul edilmez; ofisin tek
        orkestratörü vardır ve o kendini çoğaltamaz.
        """
        raw_list = (data or {}).get("new_agents") if isinstance(data, dict) else None
        if not isinstance(raw_list, list) or not raw_list:
            return []
        from entropy.agents.registry import AgentSpec

        agents = self.offices.agents(self.office_name)
        created: List[str] = []
        for raw in raw_list:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            if not name or agents.get(name) is not None:
                continue
            role = str(raw.get("role") or "worker").strip().lower()
            if role == "orchestrator":
                role = "worker"
            provider = str(raw.get("provider") or "").strip().lower()
            office = self.office
            if provider not in VALID_PROVIDERS:
                provider = (office.default_provider if office else "") or default_provider()
            policy = str(raw.get("tools_policy") or "read-write").strip().lower()
            spec = AgentSpec(
                name=name,
                role=role,
                description=str(raw.get("description") or ""),
                provider=provider,
                model=str(raw.get("model") or "") or (office.default_model if office else ""),
                tools_policy=policy,
                memory_path=f"memory/{name}.md",
                prompt=str(raw.get("prompt") or "").strip(),
                office=self.office_name,
            )
            try:
                agents.update(spec)
            except Exception:
                logger.warning("Yeni alt ajan yazılamadı: %s", name)
                continue
            created.append(name)
        if created:
            logger.info("Ofis kadrosuna eklendi (%s): %s", self.office_name, ", ".join(created))
        return created

    def _on_plan(self, card_id: str, text: str, ok: bool) -> None:
        if not self._spend(card_id, _estimate_tokens(text), ledger_task_id=f"office-plan-{card_id}"):
            self._fail_budget(card_id, "planlama")
            return
        if not ok:
            self._fail(card_id, "Planlama çağrısı başarısız oldu.")
            return
        # A9 — araç yasağı yaptırımı. Orkestratörün tanımı `read-only`, ama
        # sağlayıcı bunu her zaman uygulamıyor: çıktıda kod bloğu/diff/yazma
        # beyanı varsa çıktı REDDEDİLİR ve bir kez uyarıyla yeniden istenir.
        if orchestrator_produced_code(text or ""):
            retries = int(self._card_state(card_id).get("no_code_retries") or 0)
            if retries >= ORCHESTRATOR_NO_CODE_RETRY:
                self._fail(card_id, "Orkestratör kod üretti; araç yasağı iki kez çiğnendi.")
                return
            self._save_card_state(card_id, no_code_retries=retries + 1)
            card = self.board.get(card_id)
            office = self.office
            if card is None or office is None:
                return
            warning = (
                "[UYARI — ARAÇ YASAĞI]\nÖnceki yanıtında kod bloğu / diff / dosya "
                "yazma izi vardı. Sen yalnızca PLAN ve RAPOR üretirsin: kod yazmaz, "
                "dosya değiştirmezsin. Yalnızca istenen JSON planını üret.\n\n"
            )
            if not self._call_agent(
                agent_name=office.orchestrator,
                office=office,
                task_id=f"office-plan-{card_id}",
                task_name=f"{self.office_name}: planlama (yeniden)",
                prompt=warning + self.build_plan_prompt(office, card),
                on_result=lambda t, o, _c=card_id: self._on_plan(_c, t, o),
            ):
                self._fail(card_id, "Planlama yeniden başlatılamadı.")
            return
        data = extract_json_block(text or "")
        subtasks = (data or {}).get("subtasks") if isinstance(data, dict) else None
        if not isinstance(subtasks, list) or not subtasks:
            self._fail(card_id, "Orkestratör geçerli bir plan JSON'u üretmedi.")
            return
        card = self.board.get(card_id)
        office = self.office
        if card is None or office is None:
            return

        # Orkestratör kendi kadrosunu kurar: plandaki `new_agents` bölümü ofisin
        # `agents/<ad>/AGENT.md` dosyalarına yazılır ve derlenir. Bu adım alt
        # kartlardan ÖNCE koşmalı; aksi hâlde yeni ajana atanan görev "ofis üyesi
        # değil" diye ilk üyeye düşürülüyordu.
        created_agents = self._apply_new_agents(data)
        if created_agents:
            office = self.office or office

        # B1 — plandaki araştırma notları ofis belleğine `bulgu` olarak düşer;
        # bir sonraki planlama bunları `orchestrator_context` üzerinden görür.
        self._write_research_notes(card, data)

        # Faz 10-A: mimari kararları ARCHITECTURE.md'ye, keşfedilen kurallar
        # ADAY kuyruğuna. Orkestratör kural dosyasını kendisi yazamaz.
        self.update_architecture((data or {}).get("architecture_notes"))
        self.collect_rule_candidates(office.orchestrator or "", text or "", source=card_id)

        children: List[str] = []
        for raw in subtasks[:MAX_SUBTASKS]:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "").strip()
            if not title:
                continue
            agent = str(raw.get("agent") or "").strip()
            # Uydurulmuş ajan adı sessizce kabul edilirse kart hiç koşmaz;
            # ofis üyesi değilse ilk üyeye düşürülür.
            if agent not in (office.members or []):
                agent = (office.members or [""])[0]
            provider = str(raw.get("provider") or "").strip().lower()
            spec = self.registry.get(agent)
            if provider not in VALID_PROVIDERS:
                provider = (spec.provider if spec else office.default_provider) or default_provider()
            criteria = raw.get("criteria") or []
            if isinstance(criteria, str):
                criteria = [criteria]
            child = TaskCard(
                id=new_task_id(title),
                title=title,
                status="backlog",
                agent=agent,
                provider=provider,
                model=str(raw.get("model") or "") or (spec.model if spec else office.default_model),
                skill=((spec.skills or [""])[0] if spec else ""),
                goal=str(raw.get("goal") or title),
                criteria=[str(c) for c in criteria],
                office=self.office_name,
                project=card.project,
                parent=card_id,
            )
            try:
                child = self.board.create(child)
            except Exception:
                continue
            children.append(child.id)

        if not children:
            self._fail(card_id, "Plan ayrıştırıldı ama tek bir alt kart bile yazılamadı.")
            return

        self.board.update(replace(card, children=children, office=self.office_name, status="running"))
        # Plan bittiği anda pano yazılır: yeni doğan işçi kendi kartını ve
        # kardeşlerinin durumunu dosyadan görür.
        self.render_board()
        self._save_card_state(card_id, phase=PHASE_RUNNING)
        self._emit(card_id, PHASE_RUNNING)
        # Makbuzun `## Plan` bölümü plan biter bitmez okunabilir olsun.
        self._write_receipt(card_id)
        self._pump(card_id)

    # -- 2. yürütme -----------------------------------------------------

    # -- etkileşimli takip turları (Faz 10-D) ----------------------------

    def _followup_hooks(self, child_id: str, project_path: str, needs_write: bool):
        """
        Takip turu kancaları: yazma kilidi + ofis paralellik sayacı.

        Köprü ilk finalize'da kilitleri BIRAKIR (doğrulandı:
        `agy_bridge._execute_background_task_worker`, ilk turdan sonra
        `_release_locks()`), yani bekleyen terminal ne kilit ne de kapasite
        tutar. Takip turu başlarken yazma kilidi YENİDEN alınır; alınamazsa
        `False` dönülür ve köprü takip mesajını hiç göndermez (iki ajanı aynı
        dosyalara salmaktansa kullanıcıya "kilit meşgul" demek doğrudur).
        """

        def _start(task_id: str, _cid=child_id, _path=project_path,
                   _write=needs_write) -> bool:
            if _write:
                holder = WriteLockHolder(_path)
                if not holder.acquire(timeout=5.0):
                    self._emit_card_stream(
                        _cid,
                        "error",
                        "Takip turu başlatılamadı: proje yazma kilidi meşgul.",
                    )
                    return False
                with self._lock:
                    self._followup_locks[_cid] = holder
            with self._lock:
                self._followup_active.add(_cid)
            return True

        def _end(task_id: str, _cid=child_id) -> None:
            with self._lock:
                self._followup_active.discard(_cid)
                holder = self._followup_locks.pop(_cid, None)
            if holder is not None:
                holder.release()

        return _start, _end

    def release_followup(self, child_id: str) -> None:
        """
        Kartın takip turu kaydını (kilit + sayaç) koşulsuz bırakır.

        Kart arşivlenirken / terminal kapatılırken çağrılır: yarım kalmış bir
        turun kilidi ofisi süresiz kilitlemesin.
        """
        with self._lock:
            self._followup_active.discard(child_id)
            holder = self._followup_locks.pop(child_id, None)
        if holder is not None:
            holder.release()

    def _emit_card_stream(self, card_id: str, kind: str, text: str) -> None:
        """Kart künyeli `bus.agent_stream` olayı (sahne bölmesi bunu basar)."""
        try:
            from entropy.core.event_bus import bus
            from entropy.core.provider import build_agent_stream_event

            child = self.board.get(card_id)
            bus.agent_stream.emit(build_agent_stream_event(
                kind,
                text,
                task_id=f"card-{card_id}",
                card_id=card_id,
                office=self.office_name,
                agent=(child.agent if child else "") or "entropy",
            ))
        except Exception:
            logger.debug("Kart akış olayı yayılamadı: %s", card_id)

    def _pump(self, card_id: str) -> None:
        """
        Boş kapasite kadar alt kart başlatır; hepsi bitmişse değerlendirmeye geçer.

        Kilit altında: geri çağrılar köprünün işçi iş parçacıklarından geliyor ve
        iki alt kart aynı anda bitince `max_parallel` iki kez aşılabiliyordu.
        """
        with self._lock:
            office = self.office
            card = self.board.get(card_id)
            if card is None or office is None:
                return
            children = self._children(card)
            running = [c for c in children if c.status == "running"]
            backlog = [c for c in children if c.status == "backlog"]
            # Yazma niyetli alt kart varsa paralellik fiilen 1'dir: proje yazma
            # kilidi tekildir ve ikinci kart zaten 60 sn bekleyip ölürdü. Okuma
            # niyetli kartlar paylaşımlı kilitle gerçekten paralel koşar.
            #
            # Faz 10-C: worktree'li kartta yazma kilidi KARTIN KENDİ ağacına
            # düşer (her kart ayrı dizin, ayrı kilit), bu yüzden kısıt yalnızca
            # izole ağaçta koşamayacak yazma kartları için geçerli.
            limit = int(office.max_parallel or 1)
            if any(
                card_needs_write(c, agent_spec=self.registry.get(c.agent) if c.agent else None)
                and not self._worktree_eligible(c, card)
                for c in (running + backlog)
            ):
                limit = 1
            # Takip turu SÜREN kartlar da kapasite tutar (Faz 10-D): kart
            # `running` değil ama ajanı canlı ve yazma kilidini elinde.
            busy = len(running) + len(
                {c.id for c in children if c.id in self._followup_active}
                - {c.id for c in running}
            )
            free = max(0, limit - busy)
            # `_starting`: köprü geri çağrıyı SENKRON verdiğinde (test taklidi ya
            # da anında hata) `board.run` içinden yeniden _pump'a giriliyor ve
            # aynı alt kart iki kez başlatılabiliyordu. Başlatılan kimlik önce
            # işaretlenir, kart dosyası `running` olana kadar koruma budur.
            to_start = [c for c in backlog if c.id not in self._starting][:free]
            self._starting.update(c.id for c in to_start)
            if not to_start and not running:
                if backlog:
                    return
                self._evaluate(card_id)
                return
        for child in to_start:
            # ÇAĞRI ÖNCESİ kontrol: kalan bütçe bir alt kartı taşımıyorsa
            # süreç hiç başlatılmaz (C1b).
            estimate = self.subcard_estimate(child)
            # Tahmin kart dosyasına yazılır: hangi sayıya göre "sığmıyor"
            # denildiği kartın kendisinden okunabilmeli.
            note = f"Tahmin: {estimate['tokens']} token (kaynak: {estimate['source']})"
            if note not in (child.notes or ""):
                child = replace(
                    child,
                    notes=((child.notes + "\n") if child.notes else "") + note,
                )
                self.board.update(child)
            if not self._can_afford(card_id, int(estimate["tokens"])):
                remaining = self._remaining_budget(card_id)
                self._terminate_children(card_id)
                self._fail(
                    card_id,
                    f"Bütçe yetersiz: kalan ≈ {remaining} token, alt kart tahmini "
                    f"{estimate['tokens']} token (kaynak: {estimate['source']}). "
                    "Yeni alt kart başlatılmadı.",
                )
                return
            if not self._spend(card_id, _estimate_tokens(child.goal, *(child.criteria or []))):
                self._fail_budget(card_id, "yürütme")
                return
            # Worktree bütçe kontrolünden SONRA açılır: sığmayan bir kart için
            # disk üstünde ağaç bırakmanın anlamı yok.
            parent = self.board.get(card_id)
            worktree = self._ensure_worktree(child, parent)
            if worktree:
                child = self.board.get(child.id) or child
            # Faz 10-D: etkileşimli kip. Kart bir Desk ofis kartıdır, kanca
            # ikilisi kilidi ve paralellik sayacını harness'ta yönetir.
            needs_write = card_needs_write(
                child, agent_spec=self.registry.get(child.agent) if child.agent else None
            )
            lock_path = worktree or str(self._workdir())
            start_hook, end_hook = self._followup_hooks(
                child.id, lock_path, needs_write
            )
            self.board.run(
                child.id,
                bridge_factory=self.bridge_factory,
                interactive=True,
                on_followup_start=start_hook,
                on_followup_end=end_hook,
                on_done=lambda cid, ok, _p=card_id: self._on_child_done(_p, cid, ok),
                # Alt ajan ofisin defterinden çözülür ve ofisin çalışma
                # dizininde koşar; derlenmiş tanım orada duruyor.
                agent_registry=self.registry,
                # Worktree'li kart KENDİ ağacında koşar: hem `--add-dir` hem
                # dosya haritası hem de yazma kilidi o ağaca bağlanır.
                project_path=worktree or str(self._workdir()),
                # Faz 10-A: istemin başına doğuş talimatı + (varsa) kontrol
                # noktasından sürdürme + koşan karta gelen yorumlar.
                lead_sections=self._child_lead_sections(child),
            )

    def _on_child_done(self, card_id: str, child_id: str, ok: bool) -> None:
        with self._lock:
            self._starting.discard(child_id)
        child = self.board.get(child_id)
        if child is not None:
            if not self._spend(card_id, _estimate_tokens(child.summary),
                               ledger_task_id=f"card-{child_id}"):
                self._fail_budget(card_id, "yürütme")
                return
            # Proje kilidini alamadığı için HİÇ BAŞLAMAMIŞ kart başarısız
            # değildir; sıraya geri konur. Eskiden bu kart `failed` kalıyor ve
            # ofis, yapılmamış bir işi yapılmış sayıyordu.
            if not ok and LOCK_TIMEOUT_MARKER in (child.summary or ""):
                state = self._card_state(card_id)
                requeues = int(state.get("lock_requeues") or 0)
                if requeues < MAX_LOCK_REQUEUES:
                    self._save_card_state(card_id, lock_requeues=requeues + 1)
                    self.board.update(replace(
                        child, status="backlog", finished_at="",
                        summary="", notes=(child.notes + "\n" if child.notes else "")
                        + "Proje kilidi alınamadı; sıraya geri konuldu.",
                    ))
                    self.render_board()
                    self._pump(card_id)
                    return
            # Faz 10-A: kontrol noktası + kanıtla kapatma + kural adayları.
            child = self._close_child(child, ok)
            self.collect_rule_candidates(child.agent, child.summary or "", source=child.id)
        self.render_board()
        # Makbuz artımlı: kullanıcı koşu sürerken `## İlerleme` bölümünü okur.
        self._write_receipt(card_id)
        self._pump(card_id)

    def _close_child(self, child: TaskCard, ok: bool) -> TaskCard:
        """
        Biten alt kartı kontrol noktası ve KANITA göre kapatır.

        Kullanıcının bağlayıcı kuralı: işçi "bitti" diyemez; testi koşturup
        yeşil sonucu rapora eklemek zorundadır. Bu yüzden `done` YALNIZCA yeşil
        `[KANIT]` bloğu olan kartın hakkıdır; kanıtsız/kırmızı kart `review`de
        insan kararını bekler. Salt araştırma kartında kanıt, üretilen
        dosya/rapor yoludur (`card_needs_write` guard'ı).
        """
        text = child.summary or ""
        fields: Dict[str, object] = {}
        checkpoint = self.record_checkpoint(child, text)
        if checkpoint:
            fields["checkpoint"] = checkpoint
        if not ok:
            if fields:
                child = replace(child, **fields)
                self.board.update(child)
            return child
        spec = self.registry.get(child.agent) if child.agent else None
        needs_write = card_needs_write(child, agent_spec=spec)
        proof = self.read_proof(text, needs_write=needs_write)
        if proof is not None and not proof["green"] and not needs_write and child.output_paths:
            # Salt araştırma kartı: blok var ama yol yazmamış; ürettiği dosya
            # kartın kendi `output_paths` alanında duruyorsa kanıt sayılır.
            proof = {"text": proof["text"] + "\nÜretilen: " + ", ".join(child.output_paths),
                     "green": True}
        if proof is None:
            fields["status"] = "review"
            reason = "kanıt eksik: `[KANIT]` bloğu yok"
        elif not proof["green"]:
            fields["status"] = "review"
            fields["proof"] = proof["text"]
            reason = "kanıt kırmızı: test sonucu yeşil değil"
        else:
            fields["status"] = "done"
            fields["proof"] = proof["text"]
            reason = ""
        if reason:
            fields["notes"] = ((child.notes + "\n") if child.notes else "") + f"Kapanmadı — {reason}."
            fields["verdict"] = (child.verdict + " · " if child.verdict else "") + reason
        child = replace(child, **fields)
        self.board.update(child)
        return child

    # -- 3. değerlendirme -----------------------------------------------

    def _evaluate(self, card_id: str) -> None:
        state = self._card_state(card_id)
        if state.get("phase") in (PHASE_DONE, PHASE_FAILED):
            return
        office = self.office
        card = self.board.get(card_id)
        if card is None or office is None:
            return
        evaluator = office.evaluator or office.orchestrator
        children = self._children(card)
        if not evaluator or not children:
            self._finalize(card_id)
            return
        eval_round = int(state.get("eval_round") or 0)
        # İkinci tur yalnızca yeniden koşulan kartlar için; üçüncü tur yok.
        targets = [c for c in children if eval_round == 0 or c.attempt > 0]
        if eval_round >= 2 or not targets:
            self._finalize(card_id)
            return

        self._save_card_state(card_id, phase=PHASE_EVALUATING, eval_round=eval_round + 1)
        self._emit(card_id, PHASE_EVALUATING)
        prompt = self.build_eval_prompt(office, card, targets)
        ok = self._call_agent(
            agent_name=evaluator,
            office=office,
            task_id=f"office-eval-{card_id}",
            task_name=f"{self.office_name}: değerlendirme",
            prompt=prompt,
            on_result=lambda text, ok, _c=card_id: self._on_grades(_c, text, ok),
        )
        if not ok:
            self._finalize(card_id)

    def build_eval_prompt(self, office: DeskOffice, card: TaskCard, children: List[TaskCard]) -> str:
        blocks = []
        for child in children:
            criteria = "\n".join(f"  - {c}" for c in (child.criteria or [])) or "  - (belirtilmedi)"
            summary = (child.summary or "(çıktı yok)").strip()
            # Değerlendirme prompt'u tüm çıktıyı taşıyamaz: beş alt görev tam
            # metinle kolayca 100k token eder. Kart başına EVAL_SUMMARY_CHARS
            # karakter, ama cümlenin ortasından değil bölüm sınırından kesilir:
            # yarım kalan bölüm değerlendiriciye "eksik iş" gibi görünüyordu.
            # Kanıt AYRI bölüm: değerlendirici uzun çıktının içinde kaybolan
            # test sonucunu görmeden "yapılmış" notu veriyordu.
            proof = (child.proof or "").strip() or "(kanıt yok)"
            blocks.append(
                f"### id: {child.id}\nBaşlık: {child.title}\nDurum: {child.status}\n"
                f"Kabul ölçütleri:\n{criteria}\nKanıt:\n{proof}\nÇıktı özeti:\n"
                f"{trim_to_sections(summary, EVAL_SUMMARY_CHARS)}"
            )
        return (
            f"[OFİS TÜZÜĞÜ — {office.name}]\n{office.charter or office.purpose}\n\n"
            f"[ÜST HEDEF]\n{card.goal or card.title}\n\n"
            f"[DEĞERLENDİRİLECEK ALT GÖREVLER]\n" + "\n\n".join(blocks) + "\n\n"
            "[ÖLÇÜT — KANIT]\nKanıt bir ölçüttür: `[KANIT]` bloğu olmayan ya da "
            "sonucu kırmızı olan alt görev, metni ne kadar iyi olursa olsun "
            "0.6'nın ALTINDA not alır. Salt araştırma görevinde kanıt, üretilen "
            "dosya/rapor yoludur.\n\n"
            "[İSTENEN ÇIKTI]\nHer alt görev için 0–1 arası not. Yalnızca TEK bir "
            "```json kod bloğu yaz:\n"
            '{"grades": [{"id": "<yukarıdaki id>", "grade": 0.0, "verdict": "...", '
            '"missing": ["..."]}]}'
        )

    def _on_grades(self, card_id: str, text: str, ok: bool) -> None:
        if not self._spend(card_id, _estimate_tokens(text), ledger_task_id=f"office-eval-{card_id}"):
            self._fail_budget(card_id, "değerlendirme")
            return
        data = extract_json_block(text or "") if ok else None
        grades = (data or {}).get("grades") if isinstance(data, dict) else None
        if isinstance(grades, list):
            for raw in grades:
                if not isinstance(raw, dict):
                    continue
                child = self.board.get(str(raw.get("id") or ""))
                if child is None or child.parent != card_id:
                    continue
                try:
                    grade = max(0.0, min(1.0, float(raw.get("grade"))))
                except (TypeError, ValueError):
                    continue
                missing = raw.get("missing") or []
                if isinstance(missing, str):
                    missing = [missing]
                verdict = str(raw.get("verdict") or "").strip()
                if missing:
                    verdict = (verdict + " · eksik: " + "; ".join(str(m) for m in missing)).strip(" ·")
                self.board.update(replace(child, grade=grade, verdict=verdict))

        # Eşiğin altındakiler bir kez yeniden koşar.
        card = self.board.get(card_id)
        if card is None:
            return
        retried = False
        for child in self._children(card):
            if child.grade is not None and child.grade < GRADE_THRESHOLD and child.attempt < MAX_ATTEMPTS - 1:
                self.board.update(replace(
                    child,
                    status="backlog",
                    attempt=child.attempt + 1,
                    notes=(child.notes + "\n" if child.notes else "")
                          + f"Yeniden koşuluyor. Değerlendirici notu: {child.grade} — {child.verdict}",
                ))
                retried = True
        if retried:
            self.render_board()
            self._save_card_state(card_id, phase=PHASE_RUNNING)
            self._emit(card_id, PHASE_RUNNING)
            self._pump(card_id)
            return
        self._finalize(card_id)

    # -- kapanış --------------------------------------------------------

    # -- makbuz (Faz 10-C / 10.9) ----------------------------------------
    #
    # Makbuz AYRI bir klasör değildir: `Offices/<ofis>/reports/<kart>.md`
    # makbuzun kendisidir. Üçüncü bir gerçek kaynak açmamak Faz 9'un P0-2
    # dersidir (kart deposu ikiye bölünmüştü). Bölüm başlıkları sözleşmedir;
    # UI onları ayrıştırarak makbuz sekmesini kurar.

    RECEIPT_SECTIONS = (
        "Plan", "İlerleme", "Değerlendirme", "Kanıt", "Değişiklikler",
        "PR", "Maliyet", "Yorumlar",
    )

    def _cost_line(self, card_id: str) -> str:
        state = self._card_state(card_id)
        budget = self._budget(card_id)
        spent = int(state.get("tokens", 0) or 0)
        measured = int(state.get("measured_tokens", 0) or 0)
        office = self.office
        provider = (office.default_provider if office else "") or default_provider()
        cap = f"{budget}" if budget else "sınırsız"
        return (f"{spent} / {cap} token (ölçülen {measured}, gerisi tahmin) · "
                f"sağlayıcı: {provider}")

    def _comments_lines(self, card: TaskCard, children: List[TaskCard]) -> List[str]:
        """Kutudaki yorumlar (OKUNMUŞ dâhil): kullanıcı yorumunun izi görünür."""
        try:
            from entropy.agents.mailbox import office_mailbox

            box = office_mailbox(self.office_name, vault_path=self.board.vault_path)
            wanted = {card.id} | {c.id for c in children}
            msgs = [m for m in box.list()
                    if m.kind in ("instruction", "question") and m.task_id in wanted]
        except Exception:
            return ["(yorum okunamadı)"]
        if not msgs:
            return ["(yorum yok)"]
        return [f"- `{m.created_at}` · {' '.join((m.text or '').split())[:400]}" for m in msgs]

    def _receipt_body(
        self,
        card: TaskCard,
        children: List[TaskCard],
        review: Optional[dict] = None,
        avg=None,
    ) -> str:
        """
        Makbuzun tam gövdesi. Alt başlıklar `###` KALIR: rapor kartın
        "## Sonuç" bölümüne de yazılıyor ve bölüm ayrıştırıcısı yalnızca dört
        bilinen `## ` başlığında kesiyor (`Hedef`, `Kabul ölçütleri`, `Notlar`,
        `Sonuç`) — makbuz başlıkları o dörtlüyle çakışmaz.
        """
        project = self._project_of(card)
        head = [f"# {card.title}", "", f"Ofis: {self.office_name}"]
        if project is not None:
            repo = (project.repo_path or "").strip()
            head.append(
                f"Proje: {project.name}"
                + (f" · depo: `{repo}` @ `{project.base_branch or 'HEAD'}`" if repo else "")
            )
        if card.branch or any(c.branch for c in children):
            branches = sorted({c.branch for c in children if c.branch} | ({card.branch} if card.branch else set()))
            head.append("Dallar: " + ", ".join(f"`{b}`" for b in branches))
        head.append("")

        lines = list(head)
        lines += ["## Plan", ""]
        if children:
            lines += ["| Alt görev | Ajan | Sağlayıcı | Ölçüt |", "|---|---|---|---|"]
            for child in children:
                lines.append(
                    f"| {child.title} | {child.agent or '-'} | {child.provider or '-'} | "
                    f"{len(child.criteria or [])} |"
                )
        else:
            lines.append("(plan henüz üretilmedi)")
        lines += ["", "## İlerleme", ""]
        if children:
            for child in children:
                headline = f"### {child.title} · {child.agent} · {child.status}"
                if child.grade is not None:
                    headline += f" · not {child.grade}"
                lines.append(headline)
                if child.verdict:
                    lines.append(f"_{child.verdict}_")
                if child.checkpoint:
                    lines.append(f"Kontrol noktası: `{child.checkpoint}`")
                lines.append((child.summary or "(çıktı yok)").strip())
                # Faz 10-D: etkileşimli kartın takip turları da makbuza girer;
                # ilk turdan sonra konuşulanlar aksi hâlde hiçbir yerde yoktu.
                from entropy.agents.tasks import followup_notes

                for note in followup_notes(child):
                    lines.append(f"- {note}")
                lines.append("")
        else:
            lines += ["(alt kart yok)", ""]
        lines += ["## Değerlendirme", ""]
        lines.append(
            f"{len(children)} alt görev · ortalama not "
            f"{avg if avg is not None else '-'}"
        )
        if card.verdict:
            lines.append(card.verdict)
        lines += ["", "## Kanıt", ""]
        proofs = [f"- `{c.id}`: {c.proof}" for c in children if (c.proof or "").strip()]
        lines += proofs or ["(kanıt bloğu yok)"]
        lines += ["", "## Değişiklikler", ""]
        from entropy.agents.pr_flow import changes_section

        lines.append(changes_section(review))
        lines += ["", "## PR", ""]
        urls = [c.pr_url for c in children if (c.pr_url or "").strip()]
        if card.pr_url:
            urls.insert(0, card.pr_url)
        if urls:
            lines += [f"- {u}" for u in urls]
        else:
            lines.append("PR açılmadı (yerel dal + diff özeti geçerli).")
        lines += ["", "## Maliyet", "", self._cost_line(card.id)]
        lines += ["", "## Yorumlar", ""]
        lines += self._comments_lines(card, children)
        return "\n".join(lines).strip()

    def _child_review(self, children: List[TaskCard]) -> Optional[dict]:
        """Alt kartların worktree'lerinden birleşik değişiklik özeti."""
        from entropy.agents.pr_flow import prepare_review

        rows: List[dict] = []
        branches: List[str] = []
        for child in children:
            if not (child.worktree or "").strip():
                continue
            project = self._project_of(child)
            data = prepare_review(child, base_branch=(project.base_branch if project else ""))
            if data.get("branch"):
                branches.append(str(data["branch"]))
            rows.extend(list(data.get("files") or []))
        if not branches:
            return None
        added = sum(int(r.get("added") or 0) for r in rows)
        removed = sum(int(r.get("removed") or 0) for r in rows)
        return {
            "branch": ", ".join(branches),
            "files": rows,
            "file_count": len(rows),
            "added": added,
            "removed": removed,
            "summary": (f"Dallar: {', '.join(branches)} · {len(rows)} dosya, "
                        f"+{added}/-{removed} satır"),
        }

    def _write_receipt(self, card_id: str) -> Optional[Path]:
        """
        Makbuzu ARTIMLI günceller (plan sonrası ve her alt kart bitişinde).

        Koşu bitmeden de okunabilmesi için: kullanıcı `## İlerleme` bölümünü
        iş sürerken görür. Hata yutulur; makbuz kartı öldürmez.
        """
        try:
            card = self.board.get(card_id)
            if card is None:
                return None
            children = self._children(card)
            graded = [c.grade for c in children if c.grade is not None]
            avg = round(sum(graded) / len(graded), 3) if graded else None
            body = self._receipt_body(card, children, review=None, avg=avg)
            path = self.offices.reports_dir(self.office_name) / f"{card.id}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            return path
        except Exception:
            logger.warning("Makbuz güncellenemedi: %s", card_id, exc_info=True)
            return None

    def _finalize(self, card_id: str) -> None:
        card = self.board.get(card_id)
        if card is None:
            return
        children = self._children(card)
        graded = [c.grade for c in children if c.grade is not None]
        avg = round(sum(graded) / len(graded), 3) if graded else None
        outputs = list(card.output_paths or [])
        for child in children:
            outputs.extend(child.output_paths or [])
        # Kart `review`'a geçerken inceleme künyesi üretilir: yerel yol
        # BİRİNCİL (push yok, ağ yok, `gh` şart değil).
        review = self._child_review(children)
        report = self._receipt_body(card, children, review=review, avg=avg)

        # Ofisin KENDİ rapor klasörü (Desk verisi); wiki sayfası ayrıca yazılır
        # ama bellek katmanı kurulu değilse rapor hiçbir yerde kalmıyordu.
        local = self._write_local_report(card, report)
        if local:
            outputs.append(str(local))
        page = self._write_office_report(card, report)
        if page:
            outputs.append(str(page))
        self._append_office_memory(card, report, avg)

        # Başarısız alt kart varsa üst kart yine `review`e düşer: karar insanın.
        self.board.update(replace(
            card,
            status="review",
            finished_at=_now(),
            grade=avg,
            verdict=f"{len(children)} alt görev, ortalama not {avg if avg is not None else '-'}",
            # Kart artık uzun metni kayıpsız saklıyor; birleşik rapor kırpılmaz.
            summary=report,
            output_paths=outputs,
        ))
        self.render_board()
        self._save_card_state(card_id, phase=PHASE_DONE)
        self._release(card_id)
        self._emit(card_id, PHASE_DONE)

        # Rapor Entropy'nin gelen kutusuna düşer (Rapor Merkezi kaynağı), sonra
        # terminal olay. Sıra önemli: rozet sayacı raporu görmeden artmamalı.
        try:
            report_to_entropy(
                self.office_name,
                card.title or card_id,
                report,
                task_id=card_id,
                output_paths=outputs,
                vault_path=self.board.vault_path,
            )
        except Exception:
            logger.warning("Ofis raporu Entropy gelen kutusuna yazılamadı: %s", card_id)
        emit_terminal(
            card_id,
            self.office_name,
            "completed",
            f"{len(children)} alt görev tamamlandı; ortalama not {avg if avg is not None else '-'}.",
            vault_path=self.board.vault_path,
        )

    def _write_local_report(self, card: TaskCard, body: str):
        """Raporu ofisin `reports/` klasörüne yazar; ayrıca belleğe aktarır."""
        try:
            path = self.offices.reports_dir(self.office_name) / f"{card.id}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        except OSError:
            return None
        # Ofis çıktısının Entropy'nin bilgi grafına aktarımı bellek ajanının
        # işi; modül yoksa rapor yine de diskte ve gelen kutusunda kalır.
        try:
            from entropy.memory.office_graph import ingest_office_into_entropy  # type: ignore
        except Exception:
            ingest_office_into_entropy = None  # type: ignore
        if ingest_office_into_entropy is not None:
            try:
                # İkinci konumsal parametre `store`'dur, rapor YOLU değil.
                # Canlı koşuda buraya `str(path)` geçiliyordu ve çağrı her
                # seferinde `'str' object has no attribute 'upsert_node'` ile
                # patlıyordu; hata yutulduğu için ofis raporu Entropy grafına
                # HİÇ akmıyor, yalnızca sessiz bir uyarı satırı kalıyordu.
                # Fonksiyon zaten ofisin `reports/` klasörünün tamamını tarar,
                # yeni yazılan rapor da o taramaya girer.
                ingest_office_into_entropy(
                    self.office_name, vault_path=self.board.vault_path
                )
            except Exception:
                logger.warning("Ofis raporu belleğe aktarılamadı: %s", card.id)
        return path

    def _write_office_report(self, card: TaskCard, body: str):
        try:
            from entropy.memory.wiki import write_query_page  # type: ignore
        except Exception:
            return None
        # Ayri ve korumali icaktarim: kategori sabiti bulunamazsa rapor yine
        # yazilir. `from entropy.memory.wiki import ...` bicimi bilerek
        # korunuyor; `from entropy.memory import wiki` paket ozniteligini
        # okur ve testlerin sys.modules yamasini atlar.
        try:
            from entropy.memory.wiki import OFFICE_REPORT_CATEGORY as office_category  # type: ignore
        except Exception:
            office_category = "Ofis raporları"
        try:
            return write_query_page(
                card.skill or "",
                f"{self.office_name}: {card.title or card.id}",
                body,
                {
                    "task_id": card.id,
                    "office": self.office_name,
                    # Kategori olmadan `write_query_page` sayfayi "Sorgular"
                    # olarak yazar ve Offices/<ofis>/reports ozeti hic
                    # uretilmez (wiki.py:212 kosulu). Ofis raporu bu bayrakla
                    # ayirt ediliyor.
                    "category": office_category,
                    "agent": card.agent,
                    "provider": card.provider,
                    "goal": card.goal,
                    "output_paths": list(card.output_paths or []),
                    "vault_path": self.board.vault_path,
                },
            )
        except Exception:
            return None

    def _append_office_memory(self, card: TaskCard, body: str, grade) -> None:
        """
        Ofis belleğine kayıt düşer.

        `append_office_memory` varsa o tercih edilir (bellek katmanı ofis
        belleğini ayrı bir dosyada tutuyor olabilir); yoksa ajan belleği
        `kind="office"` ile ofis adına yazılır. İçe aktarma koruması altında:
        ajan katmanı bellek katmanına bağımlı olamaz.
        """
        entry = {
            "task_id": card.id,
            "title": card.title,
            "goal": card.goal,
            "summary": body[:1000],
            "grade": grade,
            "kind": "office",
            "at": _now(),
            "vault_path": self.board.vault_path,
        }
        try:
            from entropy.memory.agent_memory import append_office_memory  # type: ignore
        except Exception:
            append_office_memory = None  # type: ignore
        if append_office_memory is not None:
            try:
                append_office_memory(self.office_name, entry)
                return
            except Exception:
                pass
        try:
            from entropy.memory.agent_memory import append_agent_memory  # type: ignore
        except Exception:
            return
        try:
            append_agent_memory(self.office_name, entry)
        except Exception:
            return

    # -- durdurma / sürdürme --------------------------------------------

    def stop(self, card_id: str) -> bool:
        """Zinciri keser: süren alt kartlar durdurulur, üst kart `failed` olur."""
        card = self.board.get(card_id)
        if card is None:
            return False
        for child in self._children(card):
            if child.status == "running":
                try:
                    self.board.stop(child.id)
                except Exception:
                    pass
        self._fail(card_id, "Kullanıcı isteğiyle durduruldu.", terminal_status="canceled")
        return True

    @classmethod
    def resume_all(
        cls,
        board: Optional[TaskBoard] = None,
        offices: Optional[DeskRegistry] = None,
        bridge_factory: Optional[Callable] = None,
    ) -> List[str]:
        """
        Yarım kalmış ofis zincirlerini sürdürür; sürdürülen üst kart kimlikleri.

        Uygulama kapandığında köprü süreçleri ölüyor ama kart dosyasında durum
        `running` kalıyor. Bu yüzden `running` alt kartlar önce `backlog`a
        çekilir (öksüz koşu diye devam ettirilemez), sonra pompa yeniden döner.
        Planlaması bitmemiş kart (children yok) baştan planlanır.
        """
        offices = offices or DeskRegistry()
        board = board or TaskBoard(vault_path=offices.vault_path)
        resumed: List[str] = []
        # Faz 10-D: açılışta yetim worktree'ler yeniden denenir. Kalanlar
        # kuyrukta durur ve `office_status.orphan_worktrees` ile şeritte
        # görünür — sessizce birikirlerse disk dolar ve dallar çakışır.
        try:
            from entropy.agents import worktrees as _wt

            res = _wt.retry_orphans(offices.vault_path)
            logger.info(
                "Yetim worktree temizliği: %d temizlendi, %d kaldı.",
                len(res.get("cleared") or []), len(res.get("remaining") or []),
            )
        except Exception:
            logger.warning("Yetim worktree temizliği yapılamadı.", exc_info=True)
        # Faz 11-C.12: ENTROPY kartları da uzlaştırılır. Eskiden bu döngü ofis
        # kartı olmayanı atlıyordu (`if not card.office: continue`), yani
        # uygulama Entropy'nin kendi kartı koşarken kapanırsa kart sonsuza dek
        # `status: running` kalıyor ve hiçbir şey onu düzeltmiyordu.
        try:
            from entropy.agents.dispatcher import BoardDispatcherCore

            recovered = BoardDispatcherCore(board=board).reconcile()
            if recovered:
                logger.info("Entropy panosu uzlaştırıldı: %s", ", ".join(recovered))
                resumed.extend(recovered)
        except Exception:
            logger.warning("Entropy panosu uzlaştırılamadı.", exc_info=True)
        try:
            # İki kök de taranır: yarım kalan zincirin üst kartı ofis kasasında.
            cards = board.list(office=ALL_CARDS)
        except Exception:
            return resumed
        for card in cards:
            if not card.office or card.parent or card.status != "running":
                continue
            harness = cls(card.office, board=board, offices=offices, bridge_factory=bridge_factory)
            if harness.office is None:
                continue
            children = harness._children(card)
            if not children:
                # Planlama yarıda kaldı: baştan planla (tek çağrı).
                harness._release(card.id)
                if harness.start(card.id):
                    resumed.append(card.id)
                continue
            for child in children:
                if child.status == "running":
                    board.update(replace(child, status="backlog"))
            if not harness._claim(card.id):
                continue
            resumed.append(card.id)
            harness._emit(card.id, PHASE_RUNNING)
            harness._pump(card.id)
        return resumed

    # -- köprü çağrısı ---------------------------------------------------

    def _call_agent(
        self,
        agent_name: str,
        office: DeskOffice,
        task_id: str,
        task_name: str,
        prompt: str,
        on_result: Callable[[str, bool], None],
        resume: bool = True,
    ) -> bool:
        """
        Orkestratör/değerlendirici çağrısı: rapor kaydedilmez, mod accept-edits.

        `resume=True` (varsayılan): plan → değerlendirme → yeniden plan AYNI
        sağlayıcı konuşmasında sürer. Eskiden her ofis çağrısı sıfır bağlamla
        başlıyor ve orkestratör kendi planını değerlendirirken planı hiç
        görmüyordu. Alt kartlar bu yoldan geçmez: onların temiz bağlam ilkesi
        korunur.

        `save_report=False` çünkü bu iki çağrının çıktısı JSON; kasaya rapor
        olarak düşerse hem gürültü hem de damıtma girdisi olurdu. `mode="plan"`
        kullanılmaz: agy'de plan modu 200+ adımlık keşif döngüsü açıyor ve tek
        bir planlama çağrısı ~900k token'a çıkıyordu.

        ARAÇ SÖZLEŞMESİ (Faz 10 düzeltmesi): kip `accept-edits` olduğu için
        Claude köprüsü eskiden bu yola `Edit/Write/Bash` veriyordu ve canlı
        koşuda orkestratör 3 `Bash` çağrısı yaptı — "orkestratör kod yazmaz"
        kuralı yalnızca istem metnindeydi. Artık ajanın `tools_policy`'sinden
        türeyen AÇIK araç listesi köprüye geçirilir (`claude_tools_list`;
        orkestratörde politika ne yazarsa yazsın salt-okunur). İzin kipi
        değişmez: yazma aracı listede olmadığı için izin istemi doğmaz.
        agy CLI'ında araç kısıtlama bayrağı YOK (`agy --help`: yalnızca
        `--sandbox`), orada yaptırım derlenmiş ajan kuralları +
        `orchestrator_produced_code` çıktı denetimiyle sürer.
        """
        spec = self.registry.get(agent_name) if agent_name else None
        provider = self.agent_provider(spec, office)
        try:
            bridge = TaskBoard.bridge_for(provider, bridge_factory=self.bridge_factory)
        except Exception:
            bridge = None
        if bridge is None:
            return False
        body = (spec.prompt.strip() + "\n\n") if (spec and spec.prompt) else ""

        def _wrapped(text: str, ok: bool, _provider=provider, _task_id=task_id) -> None:
            # Kimlik geri çağrıdan ÖNCE saklanır: `_on_plan` zinciri senkron
            # köprüde hemen değerlendirmeye geçebiliyor ve o çağrı kimliği
            # görmeliydi.
            try:
                getter = getattr(bridge, "background_conversation_id", None)
                new_id = getter(_task_id) if callable(getter) else None
                if new_id:
                    self.remember_office_conversation(_provider, new_id)
            except Exception:
                logger.debug("Ofis konuşma kimliği okunamadı: %s", _task_id)
            on_result(text, ok)

        kwargs = dict(
            task_id=task_id,
            task_name=task_name,
            prompt=body + prompt,
            mode="accept-edits",
            on_result=_wrapped,
            save_report=False,
            agent=agent_name or None,
            # Planlama ve değerlendirme yalnızca metin üretir: paylaşımlı okuma
            # kilidi yeter, yazma kilidi alt kartları gereksiz yere bekletirdi.
            needs_write=False,
            # Ofis ajanı ofisin çalışma dizininde koşar: derlenmiş `--agent`
            # tanımı orada duruyor ve başka bir kökten koşulunca sessizce
            # yok sayılıyordu.
            project_path=str(self._workdir()),
        )
        # Konuşma sürdürme: agy `--conversation`, Claude `--resume`; köprü
        # sözleşmesinde tek ad (`conversation_id`).
        if resume:
            existing = self.office_conversation_id(provider)
            if existing:
                kwargs["conversation_id"] = existing
            else:
                # Ofisin konuşması BAŞKA bir sağlayıcıda açılmış olabilir
                # (ör. orkestratör claude, değerlendirici agy). Oturum
                # kimlikleri sağlayıcılar arasında taşınmaz; bu bir hata değil,
                # yalnızca "temiz bağlam" demektir — günlüğe bilgi düşer.
                other = self._other_provider_conversation(provider)
                if other:
                    logger.info(
                        "Ofis konuşması %s sağlayıcısında; %s çağrısı (%s) temiz "
                        "bağlamla koşuyor.", other, provider, agent_name or "-",
                    )
        from entropy.agents.tasks import _accepts_kwarg, agent_spec_payload

        # Model ve ajan künyesi (agy-1 iki köprüye de ekledi): kart yolu bunları
        # zaten geçiriyordu, plan/değerlendirme yolu geçirmiyordu — orkestratör
        # kasadaki `models.<sağlayıcı>` geçersiz kılmasını hiç görmüyordu.
        if spec is not None:
            run_model = resolve_model(spec, provider)
            if run_model:
                kwargs["model"] = run_model
            payload = agent_spec_payload(spec)
            if payload:
                # Künyede `tools_policy` var; orkestratörde yürürlükteki
                # politika salt-okunurdur (kart dosyasında ne yazarsa yazsın),
                # sistem istemi de aynı sözleşmeyi görsün diye düzeltilir.
                if is_orchestrator(spec):
                    payload["tools_policy"] = "read-only"
                kwargs["agent_spec"] = payload
            try:
                allowed = claude_tools_list(spec)
            except Exception:
                allowed = []
            if allowed:
                kwargs["tools"] = allowed

        # Akış künyesi: orkestratör/değerlendirici çağrıları da sahnede kime
        # ait olduğu belli olsun diye etiketlenir (kart yolu zaten geçiriyordu).
        kwargs["stream_meta"] = {
            "agent": agent_name or "",
            "office": self.office_name,
            "card_id": str(task_id or "").replace("card-", "", 1),
        }
        for optional in ("needs_write", "project_path", "conversation_id",
                         "model", "agent_spec", "stream_meta", "tools"):
            if not _accepts_kwarg(bridge.send_background_task_async, optional):
                kwargs.pop(optional, None)
        try:
            bridge.send_background_task_async(**kwargs)
        except Exception:
            logger.exception("Ofis çağrısı başlatılamadı: %s", agent_name)
            return False
        return True

def release_followup_for(card_id: str) -> bool:
    """
    Kart kimligi hangi CANLI harness a aitse takip turu kaydini birakir.

    Faz 10-C: terminal bolmesindeki "Kapat" yalnizca kopruyu kapatiyordu;
    yarim kalan bir takip turunun proje yazma kilidi harness uzerinde asili
    kaliyor ve ofis bir daha yazamiyordu. Bolme harness nesnesini bilmez,
    bu yuzden arama modul duzeyinde yapilir. Idempotenttir.
    """
    cid = str(card_id or "").replace("card-", "", 1).strip()
    if not cid:
        return False
    with OfficeHarness._active_lock:
        harnesses = list(OfficeHarness._active.values())
    hit = False
    for harness in harnesses:
        try:
            if cid in getattr(harness, "_followup_active", ()) or (
                cid in getattr(harness, "_followup_locks", {})
            ):
                hit = True
            harness.release_followup(cid)
        except Exception:
            logger.debug("Takip turu birakilamadi: %s", cid, exc_info=True)
    return hit
