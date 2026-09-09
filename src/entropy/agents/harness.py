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

import json
import logging
import re
import threading
from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, List, Optional

from entropy.agents.mailbox import (
    emit_terminal,
    instructions_section,
    pending_instructions,
    report_to_entropy,
)
from entropy.agents.desk_registry import DeskOffice, DeskRegistry
from entropy.agents.compile import resolve_model
from entropy.agents.registry import VALID_PROVIDERS, AgentRegistry, default_provider
from entropy.agents.tasks import (
    ALL_CARDS,
    TaskBoard,
    TaskCard,
    _now,
    card_needs_write,
    new_task_id,
    trim_to_sections,
)
from entropy.core.project_lock import LOCK_TIMEOUT_MARKER

logger = logging.getLogger(__name__)

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

# Planlama bağlamına giren ofis raporu sayısı ve rapor başına karakter (B1).
CONTEXT_REPORT_COUNT = 3
CONTEXT_REPORT_CHARS = 1200


def orchestrator_produced_code(text: str) -> bool:
    """
    Orkestratör çıktısı araç yasağını çiğnemiş mi (kod bloğu/diff/yazma izi)?

    ```json bloğu KASITLI olarak ihlal sayılmaz: planın kendisi o biçimde
    isteniyor. Yalnızca dil etiketli kod blokları, `diff --git` başlıkları ve
    "dosyaya yazdım" gibi açık yazma beyanları ihlaldir.
    """
    return bool(_CODE_TRACE_RE.search(text or ""))

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

    def _can_web_search(self) -> bool:
        """Kadroda web araması yapabilen (read-only / full) bir ajan var mı?"""
        office = self.office
        if office is None:
            return False
        for name in office.members or []:
            spec = self.registry.get(name)
            if spec is None:
                continue
            if (spec.tools_policy or "").strip().lower() in ("read-only", "readonly", "full"):
                return True
        return False

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
                project_block = (
                    f"[PROJE — {project.name}]\n{project.goal}\n"
                    f"{(project.charter or '').strip()}\n\n"
                )
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
            context_block = "\n\n".join(parts) + "\n\n"
        # Araştırma notu alt adımı yalnızca kadroda WebSearch yetkili ajan
        # varsa istenir; yoksa orkestratör dolduramayacağı bir alan uyduruyordu.
        research_block = ""
        research_schema = ""
        if self._can_web_search():
            research_block = (
                "[ARAŞTIRMA NOTU]\nPlanlamadan önce bilgini tazele: kadronda "
                "WebSearch yetkili ajan var. Bulgularını `research_notes` "
                "alanına kısa maddeler hâlinde yaz; bunlar ofis belleğine "
                "'bulgu' notu olarak kaydedilecek.\n\n"
            )
            research_schema = (
                ',\n "research_notes": [{"title": "...", "body": "..."}]'
            )
        # Şemadaki `provider` örneği KADRODAN türer: sabit "agy" yazıldığında
        # model, kadroda yalnızca Claude ajanı olsa bile plana `agy` yazmaya
        # eğilimliydi ve claude-yalnız kurulum sessizce agy'ye düşüyordu.
        plan_provider = self._roster_provider(office)
        return (
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
            '"prompt": "..."}]'
            f"{research_schema}" + "}"
        )

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
        self._save_card_state(card_id, phase=PHASE_RUNNING)
        self._emit(card_id, PHASE_RUNNING)
        self._pump(card_id)

    # -- 2. yürütme -----------------------------------------------------

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
            limit = int(office.max_parallel or 1)
            if any(card_needs_write(c, agent_spec=self.registry.get(c.agent) if c.agent else None)
                   for c in (running + backlog)):
                limit = 1
            free = max(0, limit - len(running))
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
            self.board.run(
                child.id,
                bridge_factory=self.bridge_factory,
                on_done=lambda cid, ok, _p=card_id: self._on_child_done(_p, cid, ok),
                # Alt ajan ofisin defterinden çözülür ve ofisin çalışma
                # dizininde koşar; derlenmiş tanım orada duruyor.
                agent_registry=self.registry,
                project_path=str(self._workdir()),
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
        self._pump(card_id)

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
            blocks.append(
                f"### id: {child.id}\nBaşlık: {child.title}\nDurum: {child.status}\n"
                f"Kabul ölçütleri:\n{criteria}\nÇıktı özeti:\n"
                f"{trim_to_sections(summary, EVAL_SUMMARY_CHARS)}"
            )
        return (
            f"[OFİS TÜZÜĞÜ — {office.name}]\n{office.charter or office.purpose}\n\n"
            f"[ÜST HEDEF]\n{card.goal or card.title}\n\n"
            f"[DEĞERLENDİRİLECEK ALT GÖREVLER]\n" + "\n\n".join(blocks) + "\n\n"
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
            self._save_card_state(card_id, phase=PHASE_RUNNING)
            self._emit(card_id, PHASE_RUNNING)
            self._pump(card_id)
            return
        self._finalize(card_id)

    # -- kapanış --------------------------------------------------------

    def _finalize(self, card_id: str) -> None:
        card = self.board.get(card_id)
        if card is None:
            return
        children = self._children(card)
        graded = [c.grade for c in children if c.grade is not None]
        avg = round(sum(graded) / len(graded), 3) if graded else None
        lines = [f"# {card.title}", "", f"Ofis: {self.office_name}", ""]
        outputs = list(card.output_paths or [])
        for child in children:
            # Başlık seviyesi kasıtlı olarak `###`: rapor kartın "## Sonuç"
            # bölümüne yazılıyor ve `##` kullanılırsa kart geri okunduğunda
            # bölüm ayrıştırıcısı özeti ilk alt başlıkta kesiyordu.
            head = f"### {child.title} · {child.agent} · {child.status}"
            if child.grade is not None:
                head += f" · not {child.grade}"
            lines.append(head)
            if child.verdict:
                lines.append(f"_{child.verdict}_")
            lines.append((child.summary or "(çıktı yok)").strip())
            lines.append("")
            outputs.extend(child.output_paths or [])
        report = "\n".join(lines).strip()

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
                kwargs["agent_spec"] = payload

        for optional in ("needs_write", "project_path", "conversation_id",
                         "model", "agent_spec"):
            if not _accepts_kwarg(bridge.send_background_task_async, optional):
                kwargs.pop(optional, None)
        try:
            bridge.send_background_task_async(**kwargs)
        except Exception:
            logger.exception("Ofis çağrısı başlatılamadı: %s", agent_name)
            return False
        return True
