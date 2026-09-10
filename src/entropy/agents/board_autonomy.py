"""
Entropy'nin KENDİ kararıyla görev üretmesi (Faz 12-B, araştırma C §1.2 / karar 1).

Boşluk G1: `board_create` aracı yazılmıştı ama hiçbir yerde çağrılmıyor,
ayrıştırılmıyor ve Entropy'nin istemine hiç girmiyordu. Kullanıcının döngüsünün
3. adımı ("Entropy kendi kararıyla görev üretir") fiilen yoktu: kart yalnızca
`/task`, `/desk task` ve ofis harness'ından doğuyordu — yani her zaman bir
insan ya da orkestratör planı tetikliyordu.

Bu modül o kararı kart dosyasına çeviren tek yerdir. Bilerek DAR:

- **Tur başına tavan bir kart** (`MAX_CARDS_PER_TURN`, risk R-A): kendi kendine
  kart yağdıran bir Entropy, kotayı bir gecede bitirir. Fazlası yok sayılır ve
  makbuzda söylenir.
- **Ajan doğrulaması:** ad Entropy kadrosunda olmalı. Değilse kart SİLİNMEZ,
  `backlog`ta ajansız kalır ve notuna neden yazılır — durum makinesinde ajansız
  kart koşmaz, yani yanlış ada yazılmış bir kart sessizce genel bir asistanla
  koşamaz.
- **Ofis kartı üretemez:** akış tek yönlüdür (Entropy → Desk talimatı
  `instruct_office` ile gider, kart değil).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Bir sohbet turunda açılabilecek en fazla kart (araştırma C risk R-A).
MAX_CARDS_PER_TURN = 1

#: Makbuz satırının biçimi (arayüz ve testler bunu arar).
RECEIPT_PREFIX = "Görev oluşturuldu:"


def receipt_line(title: str, agent: str) -> str:
    """Sohbette bloğun yerine basılan tek satırlık makbuz."""
    return f"{RECEIPT_PREFIX} {title} → {agent or '(atanmadı)'}"


def _known_agents(registry=None) -> List[str]:
    try:
        if registry is None:
            from entropy.agents.registry import AgentRegistry

            registry = AgentRegistry()
        return [str(getattr(s, "name", "") or "") for s in registry.list()]
    except Exception:
        logger.debug("Ajan kadrosu okunamadı", exc_info=True)
        return []


def create_card_from_args(
    args: Dict[str, Any], board=None, registry=None
) -> Tuple[Optional[object], str]:
    """
    `board_create` argümanlarından kart üretir.

    Dönüş `(kart, not)`. Kart `None` ise not RET NEDENİDİR; kart doluysa not
    bilgilendirmedir (boş olabilir).
    """
    from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id

    title = str(args.get("title") or "").strip()
    if not title:
        return None, "başlık yok: `title` zorunlu"
    if str(args.get("office") or "").strip():
        return None, ("ofis kartı açılamaz: Desk'e iş talimat olarak gider "
                      "(tek yönlü akış)")
    board = board if board is not None else TaskBoard()

    goal = str(args.get("goal") or "").strip() or title
    criteria = [str(c).strip() for c in (args.get("criteria") or []) if str(c).strip()]
    inputs = [str(p).strip() for p in (args.get("input_paths") or []) if str(p).strip()]
    agent = str(args.get("agent") or "").strip()
    priority = str(args.get("priority") or "").strip().upper()
    effort = str(args.get("effort") or "").strip().lower()

    note = ""
    spec = None
    if agent:
        try:
            if registry is None:
                from entropy.agents.registry import AgentRegistry

                registry = AgentRegistry()
            spec = registry.get(agent)
        except Exception:
            spec = None
        if spec is None:
            known = ", ".join(_known_agents(registry)) or "(kadro boş)"
            note = (f"'{agent}' Entropy kadrosunda yok; kart ajansız açıldı "
                    f"(backlog). Kadro: {known}")
            agent = ""

    card = TaskCard(
        id=new_task_id(title),
        title=title,
        status="backlog",
        agent=agent,
        goal=goal,
        criteria=criteria,
        input_paths=inputs,
        priority=priority,
        effort=effort,
        notes=note,
    )
    if spec is not None:
        card.provider = getattr(spec, "provider", "") or card.provider
        card.model = getattr(spec, "model", "") or card.model
        skills = list(getattr(spec, "skills", None) or [])
        card.skill = skills[0] if skills else ""

    card = board.create(card)
    if agent:
        # `assigned`: tetikleyici yalnızca bu durumdaki kartı sahiplenir.
        try:
            card = board.apply_event(card.id, "task.assigned", actor="entropy",
                                     payload={"agent": agent}) or card
        except Exception as exc:
            note = (note + " · " if note else "") + f"panoya alınamadı: {exc}"
    else:
        note = note or ("ajan verilmedi; kart backlog'ta bekliyor "
                        "(ajansız kart koşmaz)")
    return card, note


def wake_dispatcher() -> bool:
    """Tetikleyiciyi uyandırır (kapalıysa False; kart panoda bekler)."""
    try:
        from entropy.agents.dispatcher import board_dispatcher

        dispatcher = board_dispatcher()
        if dispatcher is None:
            return False
        dispatcher.start()
        return True
    except Exception:
        logger.debug("Tetikleyici uyandırılamadı", exc_info=True)
        return False


def announce(card) -> None:
    """`bus.board_state_changed` — arayüz kartı anında görsün."""
    try:
        from entropy.core.event_bus import bus

        bus.board_state_changed.emit({
            "card_id": getattr(card, "id", ""),
            "status": getattr(card, "status", ""),
            "event": "task.created",
            "agent": getattr(card, "agent", "") or "",
            "office": "",
            "title": getattr(card, "title", "") or "",
        })
    except Exception:
        pass


__all__ = ["MAX_CARDS_PER_TURN", "RECEIPT_PREFIX", "receipt_line",
           "create_card_from_args", "wake_dispatcher", "announce"]
