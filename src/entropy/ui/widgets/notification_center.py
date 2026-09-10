"""
Bildirim merkezi (Faz 5.5) — bus olaylarının son 50'si, tıklanınca ilgili yer.

Sorun: `notification_pill` bir olayı gösterip kayboluyordu. Kullanıcı ekrana
bakmadığı iki dakikada üç rapor gelip bir görev düşse hiçbirini göremiyordu;
"az önce ne oldu" sorusunun cevabı yoktu.

Bu panel bus'ın kullanıcıyı ilgilendiren sinyallerine abone olur ve halkasal bir
tamponda son `HISTORY_LIMIT` olayı tutar. Tampon (`NotificationLog`) saf
Python'dur; Qt bağlantısı `NotificationCenter` widget'ındadır ve **yalnızca ana
iş parçacığında** kullanılır — sinyaller zaten ana iş parçacığına kuyruklanır.

Tıklama: `notification_activated(kind, target)` yayılır. Çağıran taraf hedefi
yorumlar (rapor yolu → okuyucu, yetenek adı → Yetenekler sekmesi, vb.).
"""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout,
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.ui_polish import BODY_PX, LABEL_PX

HISTORY_LIMIT = 50

# Olay türü → (ikon, okunur ad, hedef yorumu). Hedef yorumu, tıklamanın nereye
# götüreceğini çağıran tarafa anlatır.
EVENT_META = {
    "report": ("", "Rapor", "report"),
    "task_done": ("", "Görev", "task"),
    "task_failed": ("", "Görev", "task"),
    "mailbox": ("", "Posta kutusu", "mailbox"),
    "office": ("", "Ofis", "office"),
    "skill": ("", "Yetenek", "skill"),
    "playbook": ("", "Yordam", "skill"),
    "agents": ("", "Ajanlar", "agent"),
    "provider": ("", "Sağlayıcı", "provider"),
    "graph": ("", "Bellek", "graph"),
    # Faz 10-D: sessiz bellek istisnaları artık görünür. Tıklama Bellek
    # denetçisine ("memory" hedefi) götürür.
    "memory": ("", "Bellek uyarısı", "memory"),
}


class NotificationLog:
    """Son N bildirimi tutan halkasal tampon (Qt'siz, testten çağrılabilir)."""

    def __init__(self, limit: int = HISTORY_LIMIT):
        self.limit = max(1, int(limit))
        self._items: Deque[Dict[str, Any]] = deque(maxlen=self.limit)

    def add(self, kind: str, title: str, target: str = "", ts: Optional[float] = None) -> Dict[str, Any]:
        item = {
            "kind": str(kind),
            "title": str(title),
            "target": str(target),
            "ts": float(ts if ts is not None else time.time()),
        }
        self._items.appendleft(item)
        return item

    def items(self) -> List[Dict[str, Any]]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


def format_notification(item: Dict[str, Any]) -> str:
    icon, label, _ = EVENT_META.get(str(item.get("kind")), ("•", "Olay", ""))
    clock = time.strftime("%H:%M", time.localtime(float(item.get("ts") or 0.0)))
    return f"{clock}  {icon} {label} — {item.get('title', '')}"


class NotificationCenter(QFrame):
    """Bus olaylarının son 50'sini gösteren panel."""

    notification_activated = Signal(str, str)  # target türü, hedef
    unseen_changed = Signal(int)

    def __init__(self, parent=None, limit: int = HISTORY_LIMIT):
        super().__init__(parent)
        self.setObjectName("notificationCenter")
        self.log = NotificationLog(limit)
        self._unseen = 0

        self.setProperty("role", "panel")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(5)

        head = QHBoxLayout()
        self.header_label = QLabel("")
        self.header_label.setTextFormat(Qt.TextFormat.RichText)
        head.addWidget(self.header_label)
        head.addStretch()
        self.clear_btn = QPushButton("Temizle")
        self.clear_btn.setAccessibleName("Temizle")
        self.clear_btn.setToolTip("Bildirim geçmişini temizle (olaylar diskte değil, yalnızca bu oturumda)")
        self.clear_btn.setProperty("variant", "ghost")
        self.clear_btn.clicked.connect(self.clear)
        head.addWidget(self.clear_btn)
        root.addLayout(head)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget, 1)

        self._connections = []
        self._connect_bus()
        self.refresh()

    # ------------------------------------------------------------ bus

    def _connect_bus(self) -> None:
        pairs = [
            (bus.report_created, self._on_report_created),
            (bus.task_completed, self._on_task_completed),
            (bus.playbook_updated, self._on_playbook_updated),
            (bus.agents_updated, self._on_agents_updated),
            (bus.offices_updated, self._on_offices_updated),
            (bus.skill_detected, self._on_skill_detected),
        ]
        # Faz 5 sözleşmesi: bu iki sinyali agy ajanı ekliyor; yoksa atlanır.
        mailbox_signal = getattr(bus, "mailbox_updated", None)
        if mailbox_signal is not None:
            pairs.append((mailbox_signal, self._on_mailbox_updated))
        memory_signal = getattr(bus, "memory_error", None)
        if memory_signal is not None:
            pairs.append((memory_signal, self._on_memory_error))
        provider_signal = getattr(bus, "provider_status_updated", None)
        if provider_signal is not None:
            pairs.append((provider_signal, self._on_provider_status))
        for signal, slot in pairs:
            try:
                signal.connect(slot)
                self._connections.append((signal, slot))
            except (TypeError, RuntimeError):
                continue

    @Slot(str)
    def _on_report_created(self, path: str) -> None:
        self.add("report", Path(str(path)).stem or "Yeni rapor", str(path))

    @Slot(str, bool)
    def _on_task_completed(self, task_id: str, ok: bool) -> None:
        self.add("task_done" if ok else "task_failed", str(task_id), str(task_id))

    @Slot(str)
    def _on_playbook_updated(self, skill: str) -> None:
        self.add("playbook", f"{skill} yordamı güncellendi", str(skill))

    @Slot(str)
    def _on_agents_updated(self, name: str) -> None:
        self.add("agents", f"{name or 'Ajan tanımları'} değişti", str(name))

    @Slot(str)
    def _on_offices_updated(self, name: str) -> None:
        self.add("office", f"{name or 'Ofis tanımları'} değişti", str(name))

    @Slot(str, float)
    def _on_skill_detected(self, skill: str, confidence: float) -> None:
        if not skill:
            return
        self.add("skill", f"{skill} (güven {confidence:.2f})", str(skill))

    @Slot(str, str)
    def _on_mailbox_updated(self, owner_kind: str, owner_name: str) -> None:
        self.add("mailbox", f"{owner_kind}/{owner_name} kutusu güncellendi", str(owner_name))

    @Slot(dict)
    def _on_memory_error(self, payload: dict) -> None:
        """
        `bus.memory_error` → "Bellek uyarısı" girdisi.

        Yük {where, message, ts}. Sinyal bellek katmanının İŞÇİ iş
        parçacığından gelebilir; alıcı QObject slotudur (lambda değil), Qt
        bağlantıyı kuyruklar.
        """
        data = payload if isinstance(payload, dict) else {}
        where = str(data.get("where") or "bellek")
        message = str(data.get("message") or "bilinmeyen hata")
        self.add("memory", f"{where}: {message}", where)

    @Slot(str, dict)
    def _on_provider_status(self, provider: str, status: dict) -> None:
        state = "girişli" if (status or {}).get("logged_in") else "giriş yok"
        self.add("provider", f"{provider}: {state}", str(provider))

    # ------------------------------------------------------------ veri

    def add(self, kind: str, title: str, target: str = "") -> Dict[str, Any]:
        item = self.log.add(kind, title, target)
        self._unseen = min(self.log.limit, self._unseen + 1)
        self.refresh()
        self.unseen_changed.emit(self._unseen)
        return item

    def mark_seen(self) -> None:
        self._unseen = 0
        self.unseen_changed.emit(0)

    def unseen(self) -> int:
        return self._unseen

    def clear(self) -> None:
        self.log.clear()
        self.mark_seen()
        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        items = self.log.items()
        for item in items:
            row = QListWidgetItem(format_notification(item))
            row.setData(Qt.ItemDataRole.UserRole, item)
            row.setToolTip(str(item.get("target") or ""))
            self.list_widget.addItem(row)
        self.header_label.setText(
            f"<b style='color:{RT['accent']}; font-size:{BODY_PX}px;'>BİLDİRİMLER</b>"
            f" <span style='color:{RT['text_dim']}; font-size:{LABEL_PX}px;'>"
            f"son {len(items)} olay (en fazla {self.log.limit})</span>"
        )
        if not items:
            placeholder = QListWidgetItem("Henüz bildirim yok.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(placeholder)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return
        _, _, target_kind = EVENT_META.get(str(data.get("kind")), ("•", "", ""))
        self.notification_activated.emit(target_kind, str(data.get("target", "")))

    def closeEvent(self, event):  # noqa: N802
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._connections = []
        super().closeEvent(event)
