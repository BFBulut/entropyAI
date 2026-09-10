"""Reusable Cyber Notification Pill Widget for Reports and Task Completions."""

from pathlib import Path
from typing import Callable, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

class NotificationPillWidget(QFrame):
    """A floating notification pill displaying an active report or completed task."""

    def __init__(
        self,
        title: str,
        path_or_content: str,
        is_task: bool = False,
        on_open: Optional[Callable[[str], None]] = None,
        on_dismiss: Optional[Callable[["NotificationPillWidget"], None]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.path_or_content = path_or_content
        self.on_open = on_open
        self.on_dismiss = on_dismiss
        self.is_task = is_task

        accent_color = "#00FF9D" if is_task else "#00F0FF"
        icon_prefix = "⏰ Görev:" if is_task else "Rapor:"
        btn_label = "İncele ↗" if is_task else "Oku ↗"

        self.setProperty("role", "panel")
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        # Title label
        display_title = title[:24] + (".." if len(title) > 24 else "")
        self.label = QLabel(
            f"<span style='color:{accent_color}; font-weight:bold; font-size:11px;'>{icon_prefix}</span> "
            f"<span style='color:#F0F6FC; font-size:11px;'>{display_title}</span>"
        )
        self.label.setToolTip(title)
        layout.addWidget(self.label)

        # Open button
        self.btn_open = QPushButton("Oku ↗" if not is_task else "İncele ↗")
        self.btn_open.setProperty("variant", "ghost")
        self.btn_open.clicked.connect(self._handle_open)
        layout.addWidget(self.btn_open)

        # Dismiss button
        self.btn_close = QPushButton("Kapat")
        self.btn_close.setAccessibleName("Kapat")
        self.btn_close.clicked.connect(self._handle_dismiss)
        layout.addWidget(self.btn_close)

    def _handle_open(self):
        if self.on_open:
            self.on_open(self.path_or_content)

    def _handle_dismiss(self):
        if self.on_dismiss:
            self.on_dismiss(self)
        else:
            self.deleteLater()
