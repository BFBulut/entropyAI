"""
Zaman çizelgesi (Faz 5.5) — "bugün ne oldu?" tek listede.

Sorun: bir günün içinde çalışan zamanlanmış görevler, üretilen raporlar,
aktarım (handoff) sayfaları ve ofis olayları dört ayrı yüzeyde birikiyordu;
"dün akşam ne yaptı bu sistem" sorusunun tek cevabı yoktu.

Kaynaklar (hepsi guard'lı, hiçbiri zorunlu değil):
  * görev ledger'ı — `entropy.core.task_ledger.task_ledger.list_recent_tasks()`
  * rapor kasası   — `report_inbox.collect_recent_entries()`
  * aktarım sayfaları — kasadaki `Handoff*` başlıklı notlar (rapor künyesinden)
  * ofis olayları  — Entropy posta kutusundaki mesajlar (`Mailbox`)

Toplama saf Python'dur (`collect_timeline`), Qt gerektirmez ve testten doğrudan
çağrılabilir. Widget yalnızca ana iş parçacığında kullanılmalıdır.
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout,
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.ui_polish import BODY_PX, LABEL_PX

#: Faz 11-E adim 3: emoji ikon yasagi. Satirin basindaki simge sutunu yerine
#: turun ADI yazilir; anlam metinle tasinir (ekran okuyucu da okur).
KIND_ICONS = {
    "task": "",
    "report": "",
    "handoff": "",
    "office": "",
    "board": "",
}

KIND_LABELS = {
    "task": "Görev",
    "report": "Rapor",
    "handoff": "Aktarım",
    "office": "Ofis",
    "board": "Pano",
}

#: Zaman çizelgesine alınan pano olayı sayısı (Faz 11-C sözleşmesi: son 50).
BOARD_EVENT_LIMIT = 50


def _parse_ts(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def day_bounds(now: Optional[float] = None) -> tuple:
    """Verilen anın içinde bulunduğu yerel günün [başlangıç, bitiş) damgaları."""
    moment = dt.datetime.fromtimestamp(now if now is not None else time.time())
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp(), (start + dt.timedelta(days=1)).timestamp()


# ------------------------------------------------------------ kaynaklar

def _task_events() -> List[Dict[str, Any]]:
    try:
        from entropy.core.task_ledger import task_ledger

        rows = task_ledger.list_recent_tasks(limit=120) or []
    except Exception:
        return []
    events = []
    for row in rows:
        ts = _parse_ts(row.get("completed_at") or row.get("started_at") or row.get("created_at"))
        status = str(row.get("status") or "")
        events.append({
            "kind": "task",
            "ts": ts,
            "title": str(row.get("task_name") or row.get("task_id") or "Görev"),
            "detail": status,
            "status": status,
            "target": str(row.get("task_id") or ""),
        })
    return events


def _report_events() -> List[Dict[str, Any]]:
    try:
        from entropy.ui.widgets.report_inbox import collect_recent_entries

        entries = collect_recent_entries(limit=80) or []
    except Exception:
        return []
    events = []
    for entry in entries:
        path = str(entry.get("path", ""))
        title = str(entry.get("title") or Path(path).stem)
        # Aktarım sayfaları ayrı türdür: bağlam doluluğu nedeniyle otomatik
        # yazılırlar ve "bugün ne oldu" listesinde rapor gibi görünmemeliler.
        is_handoff = "handoff" in title.lower() or "aktarım" in title.lower()
        events.append({
            "kind": "handoff" if is_handoff else "report",
            "ts": _parse_ts(entry.get("mtime")),
            "title": title,
            "detail": str(entry.get("skill") or entry.get("folder") or ""),
            "status": "",
            "target": path,
        })
    return events


def _office_events() -> List[Dict[str, Any]]:
    try:
        from entropy.agents.mailbox import Mailbox

        messages = list(Mailbox("entropy", "entropy").list() or [])
    except Exception:
        return []
    events = []
    for message in messages:
        sender = str(getattr(message, "from_", "") or "")
        events.append({
            "kind": "office",
            "ts": _parse_ts(getattr(message, "created_at", "")),
            "title": (getattr(message, "text", "") or "").splitlines()[0][:90]
            if getattr(message, "text", "") else f"{getattr(message, 'kind', 'mesaj')}",
            "detail": f"{sender} · {getattr(message, 'kind', '')} · {getattr(message, 'status', '')}",
            "status": str(getattr(message, "status", "")),
            "target": str(getattr(message, "id", "")),
        })
    return events


def _board_events(limit: int = BOARD_EVENT_LIMIT) -> List[Dict[str, Any]]:
    """
    `Entropy/Board/events.jsonl` son N olayı (Faz 11-C).

    Satır şeması `{schema_version, seq, ts, correlation_id, task_id,
    attempt_id, actor, action, idempotency_key, payload}`. Dosya yoksa ya da
    satır bozuksa o satır atlanır — uydurma olay üretilmez.
    """
    try:
        from entropy.core.paths import board_events_path

        path = Path(board_events_path())
    except Exception:
        return []
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    import json

    events: List[Dict[str, Any]] = []
    for line in lines[-max(1, int(limit)):]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        title = str(payload.get("title") or row.get("task_id") or "Pano olayı")
        detail_bits = [str(row.get("action") or "")]
        for key in ("status", "agent"):
            value = str(payload.get(key) or "")
            if value:
                detail_bits.append(value)
        events.append({
            "kind": "board",
            "ts": _parse_ts(row.get("ts")),
            "title": title,
            "detail": " · ".join(b for b in detail_bits if b),
            "status": str(payload.get("status") or ""),
            "target": str(row.get("task_id") or ""),
            "seq": row.get("seq"),
            "actor": str(row.get("actor") or ""),
        })
    return events


def collect_timeline(
    now: Optional[float] = None,
    events: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Bugünün olaylarını tek listede, en yeniden eskiye sıralar.

    `events` verilirse kaynak toplayıcılar atlanır (testler ve önizleme için).
    Gün sınırı yerel saate göredir; damgası olmayan olay listeye alınmaz çünkü
    "bugün" iddiası doğrulanamaz.
    """
    raw = list(events) if events is not None else (
        _task_events() + _report_events() + _office_events() + _board_events()
    )
    start, end = day_bounds(now)
    today = [e for e in raw if start <= float(e.get("ts") or 0.0) < end]
    today.sort(key=lambda e: -float(e.get("ts") or 0.0))
    return today


def format_event(event: Dict[str, Any]) -> str:
    """Olayı tek satırlık okunur metne çevirir: `14:32  Rapor — başlık`."""
    ts = float(event.get("ts") or 0.0)
    clock = dt.datetime.fromtimestamp(ts).strftime("%H:%M") if ts else "--:--"
    icon = KIND_ICONS.get(str(event.get("kind")), "")
    label = KIND_LABELS.get(str(event.get("kind")), "Olay")
    line = f"{clock}  {icon} {label} — {event.get('title', '')}"
    detail = str(event.get("detail") or "")
    if detail:
        line += f"  ({detail})"
    return line


# --------------------------------------------------------------- görünüm

class TimelinePanel(QFrame):
    """
    "Bugün" zaman çizelgesi paneli. Satıra tıklanınca `event_activated` yayılır
    (kind, target); çağıran taraf raporu açar ya da ilgili sekmeye geçer.
    """

    event_activated = Signal(str, str)  # kind, target

    def __init__(self, parent=None, events: Optional[Sequence[Dict[str, Any]]] = None,
                 now: Optional[float] = None):
        super().__init__(parent)
        self.setObjectName("timelinePanel")
        self._injected = list(events) if events is not None else None
        self._now = now
        self._events: List[Dict[str, Any]] = []

        self.setProperty("role", "panel")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(5)

        head = QHBoxLayout()
        self.header_label = QLabel("")
        self.header_label.setTextFormat(Qt.TextFormat.RichText)
        head.addWidget(self.header_label)
        head.addStretch()
        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setAccessibleName("Yenile")
        self.refresh_btn.setToolTip("Bugünün olaylarını yeniden topla")
        self.refresh_btn.setProperty("variant", "ghost")
        self.refresh_btn.clicked.connect(self.refresh)
        head.addWidget(self.refresh_btn)
        root.addLayout(head)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget, 1)

        bus.report_created.connect(self._on_bus_event)
        bus.task_completed.connect(self._on_task_completed)
        # Faz 11-C: pano geçişleri de "bugün" listesine düşer; salvo hâlinde
        # gelebildikleri için yenileme debounce edilir.
        self._board_debounce = QTimer(self)
        self._board_debounce.setSingleShot(True)
        self._board_debounce.setInterval(200)
        self._board_debounce.timeout.connect(self.refresh)
        board_signal = getattr(bus, "board_state_changed", None)
        if board_signal is not None:
            board_signal.connect(self._on_board_state_changed)
        self.refresh()

    def events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    @Slot()
    def refresh(self) -> None:
        self._events = collect_timeline(now=self._now, events=self._injected)
        self.list_widget.clear()
        for event in self._events:
            row = QListWidgetItem(format_event(event))
            row.setData(Qt.ItemDataRole.UserRole, event)
            row.setToolTip(str(event.get("target") or ""))
            self.list_widget.addItem(row)
        day = dt.datetime.fromtimestamp(self._now or time.time()).strftime("%d.%m.%Y")
        self.header_label.setText(
            f"<b style='color:{RT['accent']}; font-size:{BODY_PX}px;'>BUGÜN</b>"
            f" <span style='color:{RT['text_dim']}; font-size:{LABEL_PX}px;'>"
            f"{day} · {len(self._events)} olay</span>"
        )
        if not self._events:
            placeholder = QListWidgetItem(
                "Bugün henüz kayıtlı bir olay yok. Görev, rapor ve ofis olayları burada birikir."
            )
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(placeholder)

    @Slot(str)
    def _on_bus_event(self, _payload: str) -> None:
        self.refresh()

    @Slot(dict)
    def _on_board_state_changed(self, _payload: dict) -> None:
        """Pano durumu değişti (QObject slotu, lambda değil) — gecikmeli yenile."""
        self._board_debounce.start()

    def flush_board_events(self) -> None:
        """Bekleyen debounce'u hemen uygular (test ve pencere odaklanması)."""
        if self._board_debounce.isActive():
            self._board_debounce.stop()
            self.refresh()

    @Slot(str, bool)
    def _on_task_completed(self, _task_id: str, _ok: bool) -> None:
        self.refresh()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        event = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(event, dict):
            self.event_activated.emit(str(event.get("kind", "")), str(event.get("target", "")))

    def closeEvent(self, event):  # noqa: N802
        # Faz 8: tekrarli kapanislarda ayni sinyali yeniden cozmek
        # libpyside'in "Failed to disconnect" uyarisini basiyordu.
        if not getattr(self, "_bus_connected", True):
            super().closeEvent(event)
            return
        self._bus_connected = False
        for signal, slot in (
            (bus.report_created, self._on_bus_event),
            (bus.task_completed, self._on_task_completed),
        ):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        super().closeEvent(event)
