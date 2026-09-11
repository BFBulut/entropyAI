"""Ajan koşuları paneli — kadro değil, KOŞU görünümü (Faz 14-E madde 5).

Faz 14 planı §5: ajan modeli kalıcı kadrodan (AGENT.md + session.json) yetenek
başına **geçici** oturuma geçiyor; kadro rosterı ve "oturum yok" rozeti artık
kullanıcıya yanlış bilgi veriyordu (planda ölçülmüş kusur: adım sınırında ölen
kartta kimlik hiç yazılmıyor). Kod **silinmez** — Desk roster paneli ve mevcut
testler `AgentsWidget`'a bağlı — yalnızca Zen'de görünürlük değişir.

Panel dört şey gösterir:

1. **Çalışan koşular** — `TaskLedger.get_active_tasks()` (ad · süre).
2. **Son koşular** — `TaskLedger.list_recent_tasks()` (durum · ad).
3. **Desk orkestratörleri** — salt okunur liste (tek yön kuralı: Desk'ten
   Entropy'ye görev akmaz, yalnız görünür).
4. **Bekleyen onaylar** — sayı + sohbet panelindeki karta bağlantı.

Her veri kaynağı guard'lıdır: modül yoksa o bölüm "—" der, panel kırılmaz.
Sohbet turu satırları (`CHAT_TURN_NAME`) koşu sayılmaz.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from entropy.core.event_bus import bus
from entropy.ui.design import TOKENS
from entropy.ui.widgets.lifecycle import discard_widget

__all__ = ["AgentRunsPanel", "ledger_runs", "desk_orchestrators"]

#: Son koşu listesinde gösterilen satır sayısı.
RECENT_LIMIT = 8


def _ledger() -> Optional[Any]:
    try:
        from entropy.core.task_ledger import TaskLedger  # type: ignore

        return TaskLedger()
    except Exception:
        return None


def ledger_runs(ledger: Any = None) -> Dict[str, List[Dict[str, Any]]]:
    """`{"active": [...], "recent": [...]}` — sohbet turları ayıklanmış."""
    out: Dict[str, List[Dict[str, Any]]] = {"active": [], "recent": []}
    led = ledger if ledger is not None else _ledger()
    if led is None:
        return out
    try:
        from entropy.core.task_ledger import CHAT_TURN_NAME
    except Exception:
        CHAT_TURN_NAME = "Sohbet turu"

    def _rows(fn, *args) -> List[Dict[str, Any]]:
        try:
            rows = fn(*args) or []
        except Exception:
            return []
        return [
            dict(r) for r in rows
            if str(dict(r).get("task_name") or "") != CHAT_TURN_NAME
        ]

    active = getattr(led, "get_active_tasks", None)
    recent = getattr(led, "list_recent_tasks", None)
    if active is not None:
        out["active"] = _rows(active)
    if recent is not None:
        out["recent"] = _rows(recent, RECENT_LIMIT * 3)[:RECENT_LIMIT]
    return out


def desk_orchestrators() -> List[str]:
    """Desk ofislerinin orkestratör adları (SALT OKUNUR)."""
    try:
        from entropy.agents import desk_admin  # type: ignore
    except Exception:
        return []
    for name in ("list_orchestrators", "orchestrator_roster", "list_offices"):
        fn = getattr(desk_admin, name, None)
        if fn is None:
            continue
        try:
            rows = fn() or []
        except Exception:
            continue
        names: List[str] = []
        for row in rows:
            if isinstance(row, dict):
                names.append(str(row.get("orchestrator") or row.get("name") or ""))
            else:
                names.append(str(row))
        return [n for n in names if n]
    return []


def _elapsed(row: Dict[str, Any]) -> str:
    """Koşu süresi ("3 dk") — zaman damgası okunamazsa boş döner."""
    stamp = row.get("started_at") or row.get("created_at")
    if not stamp:
        return ""
    try:
        import datetime

        started = datetime.datetime.fromisoformat(str(stamp))
        delta = max(0, int(time.time() - started.timestamp()))
    except Exception:
        return ""
    if delta < 60:
        return f"{delta} sn"
    if delta < 3600:
        return f"{delta // 60} dk"
    return f"{delta // 3600} sa"


class AgentRunsPanel(QFrame):
    """Koşan/biten geçici ajan oturumları + Desk orkestratörleri (salt okunur)."""

    #: Kullanıcı bekleyen onaylara gitmek istedi.
    pending_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None, ledger: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self._ledger = ledger
        self._rows: List[QWidget] = []
        self._running_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            TOKENS["space"]["3"], TOKENS["space"]["2"],
            TOKENS["space"]["3"], TOKENS["space"]["2"],
        )
        layout.setSpacing(TOKENS["space"]["2"])

        head = QHBoxLayout()
        head.setSpacing(TOKENS["space"]["2"])
        title = QLabel("Ajan koşuları")
        title.setProperty("role", "heading")
        head.addWidget(title)
        head.addStretch()
        self.pending_btn = QPushButton("Bekleyen onaylar")
        self.pending_btn.setProperty("variant", "ghost")
        self.pending_btn.setAccessibleName("Bekleyen onaylara git")
        self.pending_btn.setToolTip("Sohbet panelindeki bekleyen işler kartını göster")
        self.pending_btn.clicked.connect(self.pending_requested.emit)
        head.addWidget(self.pending_btn)
        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setProperty("variant", "ghost")
        self.refresh_btn.setAccessibleName("Koşu listesini yenile")
        self.refresh_btn.clicked.connect(self.refresh)
        head.addWidget(self.refresh_btn)
        layout.addLayout(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(TOKENS["space"]["1"])
        layout.addLayout(self.body)
        layout.addStretch()

        for signal_name in ("task_cards_updated", "board_state_changed"):
            signal = getattr(bus, signal_name, None)
            if signal is not None:
                signal.connect(self._on_bus_refresh)

        self.refresh()

    # ------------------------------------------------------------ görünüm

    @Slot()
    @Slot(dict)
    @Slot(str)
    def _on_bus_refresh(self, *_args) -> None:
        self.refresh()

    def running_count(self) -> int:
        return self._running_count

    def refresh(self) -> None:
        for widget in self._rows:
            self.body.removeWidget(widget)
            discard_widget(widget)
        self._rows = []

        runs = ledger_runs(self._ledger)
        self._running_count = len(runs["active"])

        self._add_caption(
            f"Çalışan koşular ({len(runs['active'])})"
            if runs["active"] else "Çalışan koşu yok"
        )
        for row in runs["active"]:
            elapsed = _elapsed(row)
            text = str(row.get("task_name") or row.get("task_id") or "koşu")
            self._add_line(f"{text} · çalışıyor{' · ' + elapsed if elapsed else ''}",
                           tone="warn")

        self._add_caption("Son koşular")
        if not runs["recent"]:
            self._add_line("Kayıt yok — bir yetenek çalıştırınca burada görünür.")
        for row in runs["recent"]:
            status = str(row.get("status") or "")
            tone = {"SUCCESS": "ok", "FAILED": "danger",
                    "CANCELLED": "muted"}.get(status, "")
            self._add_line(
                f"{row.get('task_name') or row.get('task_id')} · {status.lower()}",
                tone=tone,
            )

        orchestrators = desk_orchestrators()
        self._add_caption("Desk orkestratörleri (salt okunur)")
        if not orchestrators:
            self._add_line("Ofis yok.")
        for name in orchestrators:
            self._add_line(name, tone="muted")

    def _add_caption(self, text: str) -> None:
        label = QLabel(text)
        label.setProperty("role", "label")
        self.body.addWidget(label)
        self._rows.append(label)

    def _add_line(self, text: str, tone: str = "") -> None:
        label = QLabel(text)
        label.setProperty("role", "body")
        if tone:
            label.setProperty("tone", tone)
        label.setToolTip(text)
        self.body.addWidget(label)
        self._rows.append(label)
