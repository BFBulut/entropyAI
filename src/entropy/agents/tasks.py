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
import re
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional

from entropy.agents.registry import (
    AgentRegistry,
    parse_frontmatter,
    render_frontmatter,
)

TASKS_SUBDIR = "Entropy/Tasks"

STATUSES = ("backlog", "running", "review", "done", "failed")

# Kart gövdesindeki bölüm başlıkları; ayrıştırma ve üretme aynı listeyi kullanır.
SECTION_GOAL = "Hedef"
SECTION_CRITERIA = "Kabul ölçütleri"
SECTION_NOTES = "Notlar"
SECTION_RESULT = "Sonuç"


@dataclass
class TaskCard:
    """Tek bir görev kartı."""

    id: str
    title: str = ""
    status: str = "backlog"
    agent: str = ""
    provider: str = "agy"
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
        }


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def new_task_id(title: str = "") -> str:
    """Zaman damgası + başlıktan türetilmiş, dosya adı olarak güvenli kimlik."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (title or "gorev").lower()).strip("-")[:24] or "gorev"
    return f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}"


def _split_sections(body: str) -> Dict[str, str]:
    """Gövdeyi `## Başlık` bölümlerine ayırır."""
    sections: Dict[str, str] = {}
    current = None
    buf: List[str] = []
    for line in (body or "").splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        elif current:
            buf.append(line)
    if current:
        sections[current] = "\n".join(buf).strip()
    return sections


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

    # -- okuma ---------------------------------------------------------

    def card_file(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.md"

    def list(self, status: Optional[str] = None) -> List[TaskCard]:
        cards: List[TaskCard] = []
        try:
            if not self.tasks_dir.is_dir():
                return cards
            for path in sorted(self.tasks_dir.glob("*.md")):
                card = self._read(path)
                if card is not None and (status is None or card.status == status):
                    cards.append(card)
        except OSError:
            return cards
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
        return TaskCard(
            id=str(front.get("id") or path.stem),
            title=str(front.get("title") or path.stem),
            status=status if status in STATUSES else "backlog",
            agent=str(front.get("agent") or ""),
            provider=str(front.get("provider") or "agy"),
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
        )

    # -- yazma ---------------------------------------------------------

    def create(self, card: TaskCard) -> TaskCard:
        if not card.id:
            card = replace(card, id=new_task_id(card.title))
        if not card.created_at:
            card = replace(card, created_at=_now())
        if self.card_file(card.id).exists():
            raise FileExistsError(f"'{card.id}' kimlikli kart zaten var.")
        return self._write(card)

    def update(self, card: TaskCard) -> TaskCard:
        return self._write(card)

    def _write(self, card: TaskCard) -> TaskCard:
        path = self.card_file(card.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        criteria = "\n".join(f"- {c}" for c in (card.criteria or [])) or "-"
        body = (
            f"## {SECTION_GOAL}\n{card.goal or '-'}\n\n"
            f"## {SECTION_CRITERIA}\n{criteria}\n\n"
            f"## {SECTION_NOTES}\n{card.notes or ''}\n\n"
            f"## {SECTION_RESULT}\n{card.summary or ''}\n"
        )
        path.write_text(f"{render_frontmatter(card.to_frontmatter())}\n\n{body}", encoding="utf-8")
        self._notify(card.id)
        return replace(card, path=path)

    def delete(self, task_id: str) -> bool:
        path = self.card_file(task_id)
        if not path.is_file():
            return False
        try:
            path.unlink()
        except OSError:
            return False
        self._notify(task_id)
        return True

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

    def build_prompt(self, card: TaskCard, agent_spec=None) -> str:
        """
        Ajanın gövdesi + görev sözleşmesi + kabul ölçütleri.

        Ajan gövdesi prompt'a da konur (yalnızca `--agent` ile geçilmez): derlenmiş
        ajan tanımı sağlayıcının bulamadığı bir kökten koşulduğunda sessizce
        yok sayılıyor ve görev genel bir asistan tarafından yapılıyordu. Gövdenin
        prompt'ta olması bu durumda da rolü garanti eder.
        """
        parts: List[str] = []
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
            "sessizce atlama. Yanıtın Türkçe ve markdown olsun."
        )
        if card.notes:
            parts.append(f"[NOTLAR]\n{card.notes}")
        return "\n\n".join(parts)

    def run(self, card_id: str, bridge_factory: Optional[Callable] = None) -> Optional[str]:
        """
        Kartı arka planda çalıştırır; ledger görev kimliğini döndürür.

        Çağrı bloke etmez: köprünün `send_background_task_async`ı iş parçacığı
        açar, sonuç geri çağrıda işlenir. Kart hemen `running` olur ki pano
        (ve ikinci bir /task çağrısı) aynı işi iki kez başlatmasın.
        """
        card = self.get(card_id)
        if card is None:
            return None
        if card.status == "running":
            return None

        registry = AgentRegistry(vault_path=self.vault_path)
        agent_spec = registry.get(card.agent) if card.agent else None
        provider = (card.provider or (agent_spec.provider if agent_spec else "agy") or "agy").lower()
        bridge = self.bridge_for(provider, bridge_factory=bridge_factory)
        if bridge is None:
            return None

        prompt = self.build_prompt(card, agent_spec=agent_spec)
        task_id = f"card-{card.id}"
        card = replace(card, status="running", started_at=_now(), provider=provider)
        self._write(card)

        def _on_result(full_text: str, ok: bool, _card_id=card.id):
            self._finish(_card_id, full_text, ok)

        try:
            bridge.send_background_task_async(
                task_id=task_id,
                task_name=card.title or card.id,
                prompt=prompt,
                mode="accept-edits",
                on_result=_on_result,
                save_report=True,
                agent=card.agent or None,
            )
        except Exception as exc:
            self._finish(card.id, f"Görev başlatılamadı: {exc}", False)
            return None
        return task_id

    def stop(self, card_id: str) -> bool:
        """Süren kartı keser; kart `failed` olur."""
        card = self.get(card_id)
        if card is None or card.status != "running":
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
        self._write(replace(card, status="failed", finished_at=_now(),
                            summary="Kullanıcı isteğiyle durduruldu."))
        return killed

    # -- tamamlama ------------------------------------------------------

    def _finish(self, card_id: str, full_text: str, ok: bool) -> None:
        """
        Görev bitince kartı günceller, wiki sayfası ve ajan belleği yazar.

        Bellek katmanı çağrıları içe aktarma koruması altında: `entropy.memory.wiki`
        ve `agent_memory` memory-rag tarafından sağlanıyor; henüz yoksa kart yine
        de doğru biçimde kapanmalı — ajan katmanı onlara bağımlı olamaz.
        """
        card = self.get(card_id)
        if card is None:
            return
        summary = (full_text or "").strip()
        outputs = list(card.output_paths or [])

        if ok and summary:
            page = self._write_wiki_page(card, summary)
            if page:
                outputs.append(str(page))
            self._append_agent_memory(card, summary)

        card = replace(
            card,
            status="review" if ok else "failed",
            finished_at=_now(),
            summary=summary[:4000] if summary else ("Çıktı üretilmedi." if not ok else ""),
            output_paths=outputs,
        )
        self._write(card)

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
