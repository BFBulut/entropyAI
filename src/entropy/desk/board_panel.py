"""
Kartlar sekmesi: ofise süzülmüş kanban (`TaskBoardWidget(office=...)`).

Ayrı bir pano uygulaması yazmak yerine Faz 2 widget'ı ofis parametresiyle
yeniden kullanılır: kart eylemleri (çalıştır/durdur/bitir/sil), durum renkleri
ve detay paneli tek yerde kalır.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout

from entropy.ui.widgets.task_board_widget import TaskBoardWidget


class BoardPanel(QFrame):
    """Ofis kanbanı sarmalayıcısı; dışarıya kart seçimini yayar."""

    card_selected = Signal(str)

    def __init__(self, parent=None, board: Any = None, office: str = "", bridge: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.board_widget = TaskBoardWidget(parent=self, board=board, office=office, bridge=bridge)
        self.board_widget.card_selected.connect(self.card_selected)
        layout.addWidget(self.board_widget)

    @property
    def office(self) -> str:
        return self.board_widget.office

    def set_office(self, office: str) -> None:
        self.board_widget.set_office(office)

    def refresh(self) -> None:
        self.board_widget.refresh_cards()

    def select_card(self, card_id: str) -> None:
        self.board_widget.select_card(card_id)

    def selected_card(self) -> Optional[Any]:
        return self.board_widget.get_card(self.board_widget.selected_id)
