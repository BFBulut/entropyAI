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

Kota koruması: her adımın tahmini token maliyeti toplanır; ofisin
`budget_tokens` değeri aşılırsa zincir durur ve üst kart nedeniyle `failed`
olur. Tahmin (karakter/4) kasıtlı kabadır — amaç muhasebe değil, kaçak
zincirin kotayı boşaltmasını engellemek.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, List, Optional

from entropy.agents.offices import OfficeRegistry, OfficeSpec
from entropy.agents.registry import AgentRegistry
from entropy.agents.tasks import TaskBoard, TaskCard, _now, new_task_id

logger = logging.getLogger(__name__)

STATE_FILENAME = "state.json"

# Kabul eşiği: bunun altındaki alt kart bir kez yeniden koşar.
GRADE_THRESHOLD = 0.6
MAX_SUBTASKS = 5
MAX_ATTEMPTS = 2  # ilk koşu + bir retry

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
        offices: Optional[OfficeRegistry] = None,
        bridge_factory: Optional[Callable] = None,
    ):
        self.office_name = office_name
        self.offices = offices or OfficeRegistry()
        vault = self.offices.vault_path
        self.board = board or TaskBoard(vault_path=vault)
        self.registry = registry or AgentRegistry(vault_path=self.board.vault_path)
        self.bridge_factory = bridge_factory
        self._lock = threading.RLock()
        self._starting: set = set()

    # -- yardımcılar ----------------------------------------------------

    @property
    def office(self) -> Optional[OfficeSpec]:
        return self.offices.get(self.office_name)

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

    def _emit(self, card_id: str, phase: str) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.office_progress.emit(self.office_name, card_id, phase)
        except Exception:
            pass

    def _spend(self, card_id: str, tokens: int) -> bool:
        """
        Harcamayı işler; bütçe aşılmadıysa True.

        Aşıldığında False döner ve çağıran zinciri durdurur — kontrol harcamadan
        ÖNCE değil sonra yapılır çünkü tahminin kendisi ancak metin oluştuktan
        sonra bilinir; önemli olan bir sonraki çağrının engellenmesi.
        """
        office = self.office
        budget = office.budget_tokens if office else 0
        entry = self._save_card_state(card_id, tokens=self._card_state(card_id).get("tokens", 0) + int(tokens))
        return not (budget and entry.get("tokens", 0) > budget)

    def _children(self, card: TaskCard) -> List[TaskCard]:
        out: List[TaskCard] = []
        for child_id in card.children or []:
            child = self.board.get(child_id)
            if child is not None:
                out.append(child)
        return out

    def _fail(self, card_id: str, reason: str) -> None:
        card = self.board.get(card_id)
        if card is not None:
            summary = (card.summary or "").strip()
            summary = f"{summary}\n\n{reason}".strip() if summary else reason
            self.board.update(replace(card, status="failed", finished_at=_now(), summary=summary))
        self._save_card_state(card_id, phase=PHASE_FAILED)
        self._release(card_id)
        self._emit(card_id, PHASE_FAILED)

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

    def build_plan_prompt(self, office: OfficeSpec, card: TaskCard) -> str:
        members = []
        for name in office.members or []:
            spec = self.registry.get(name)
            if spec is None:
                continue
            skills = ", ".join(spec.skills) if spec.skills else "-"
            members.append(f"- {spec.name} ({spec.role or 'genel'}) · {spec.description} · yetenekler: {skills}")
        criteria = "\n".join(f"- {c}" for c in (card.criteria or [])) or "- (belirtilmedi)"
        return (
            f"[OFİS TÜZÜĞÜ — {office.name}]\n{office.charter or office.purpose}\n\n"
            f"[ÜST KART]\nBaşlık: {card.title}\nHedef: {card.goal or card.title}\n"
            f"Kabul ölçütleri:\n{criteria}\n\n"
            f"[ATANABİLİR AJANLAR]\n" + ("\n".join(members) or "- (yok)") + "\n\n"
            f"[İSTENEN ÇIKTI]\nEn çok {MAX_SUBTASKS} alt görev. Yalnızca TEK bir "
            "```json kod bloğu yaz, başka hiçbir şey yazma:\n"
            '{"subtasks": [{"title": "...", "goal": "...", "criteria": ["..."], '
            '"agent": "<yukarıdaki ajanlardan biri>", "provider": "agy", "model": ""}]}'
        )

    def _on_plan(self, card_id: str, text: str, ok: bool) -> None:
        if not self._spend(card_id, _estimate_tokens(text)):
            self._fail(card_id, "Ofis bütçesi (budget_tokens) planlama adımında aşıldı.")
            return
        if not ok:
            self._fail(card_id, "Planlama çağrısı başarısız oldu.")
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
            if provider not in ("agy", "claude"):
                provider = (spec.provider if spec else office.default_provider) or "agy"
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
            free = max(0, int(office.max_parallel or 1) - len(running))
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
            if not self._spend(card_id, _estimate_tokens(child.goal, *(child.criteria or []))):
                self._fail(card_id, "Ofis bütçesi (budget_tokens) yürütme adımında aşıldı.")
                return
            self.board.run(
                child.id,
                bridge_factory=self.bridge_factory,
                on_done=lambda cid, ok, _p=card_id: self._on_child_done(_p, cid, ok),
            )

    def _on_child_done(self, card_id: str, child_id: str, ok: bool) -> None:
        with self._lock:
            self._starting.discard(child_id)
        child = self.board.get(child_id)
        if child is not None:
            self._spend(card_id, _estimate_tokens(child.summary))
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

    def build_eval_prompt(self, office: OfficeSpec, card: TaskCard, children: List[TaskCard]) -> str:
        blocks = []
        for child in children:
            criteria = "\n".join(f"  - {c}" for c in (child.criteria or [])) or "  - (belirtilmedi)"
            summary = (child.summary or "(çıktı yok)").strip()
            # Değerlendirme prompt'u tüm çıktıyı taşıyamaz: beş alt görev tam
            # metinle kolayca 100k token eder. Kart başına 1500 karakter.
            blocks.append(
                f"### id: {child.id}\nBaşlık: {child.title}\nDurum: {child.status}\n"
                f"Kabul ölçütleri:\n{criteria}\nÇıktı özeti:\n{summary[:1500]}"
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
        if not self._spend(card_id, _estimate_tokens(text)):
            self._fail(card_id, "Ofis bütçesi (budget_tokens) değerlendirme adımında aşıldı.")
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
            summary=report[:8000],
            output_paths=outputs,
        ))
        self._save_card_state(card_id, phase=PHASE_DONE)
        self._release(card_id)
        self._emit(card_id, PHASE_DONE)

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
        self._fail(card_id, "Kullanıcı isteğiyle durduruldu.")
        return True

    @classmethod
    def resume_all(
        cls,
        board: Optional[TaskBoard] = None,
        offices: Optional[OfficeRegistry] = None,
        bridge_factory: Optional[Callable] = None,
    ) -> List[str]:
        """
        Yarım kalmış ofis zincirlerini sürdürür; sürdürülen üst kart kimlikleri.

        Uygulama kapandığında köprü süreçleri ölüyor ama kart dosyasında durum
        `running` kalıyor. Bu yüzden `running` alt kartlar önce `backlog`a
        çekilir (öksüz koşu diye devam ettirilemez), sonra pompa yeniden döner.
        Planlaması bitmemiş kart (children yok) baştan planlanır.
        """
        offices = offices or OfficeRegistry()
        board = board or TaskBoard(vault_path=offices.vault_path)
        resumed: List[str] = []
        try:
            cards = board.list()
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
        office: OfficeSpec,
        task_id: str,
        task_name: str,
        prompt: str,
        on_result: Callable[[str, bool], None],
    ) -> bool:
        """
        Orkestratör/değerlendirici çağrısı: rapor kaydedilmez, mod accept-edits.

        `save_report=False` çünkü bu iki çağrının çıktısı JSON; kasaya rapor
        olarak düşerse hem gürültü hem de damıtma girdisi olurdu. `mode="plan"`
        kullanılmaz: agy'de plan modu 200+ adımlık keşif döngüsü açıyor ve tek
        bir planlama çağrısı ~900k token'a çıkıyordu.
        """
        spec = self.registry.get(agent_name) if agent_name else None
        provider = ((spec.provider if spec else "") or office.default_provider or "agy").lower()
        try:
            bridge = TaskBoard.bridge_for(provider, bridge_factory=self.bridge_factory)
        except Exception:
            bridge = None
        if bridge is None:
            return False
        body = (spec.prompt.strip() + "\n\n") if (spec and spec.prompt) else ""
        try:
            bridge.send_background_task_async(
                task_id=task_id,
                task_name=task_name,
                prompt=body + prompt,
                mode="accept-edits",
                on_result=on_result,
                save_report=False,
                agent=agent_name or None,
            )
        except Exception:
            logger.exception("Ofis çağrısı başlatılamadı: %s", agent_name)
            return False
        return True
