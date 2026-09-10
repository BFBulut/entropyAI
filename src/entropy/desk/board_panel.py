"""
Kartlar sekmesi: ofise süzülmüş kanban (`TaskBoardWidget(office=...)`) ve
altında kart detay sekmeleri (Faz 10-C: "Değişiklikler" ve "Makbuz").

Ayrı bir pano uygulaması yazmak yerine Faz 2 widget'ı ofis parametresiyle
yeniden kullanılır: kart eylemleri (çalıştır/durdur/bitir/sil), durum renkleri
ve detay paneli tek yerde kalır.

Değişiklikler/Makbuz bölmeleri BURADA (Desk'te) durur, `TaskBoardWidget`'ın
kendi detay panelinde değil: pano widget'ı Zen/Chat kipinde de kullanılıyor,
worktree ve ofis makbuzu ise yalnızca Desk kavramı.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QFrame, QSplitter, QTabWidget, QVBoxLayout

from entropy.desk.changes_panel import ChangesPanel
from entropy.desk.receipt_panel import ReceiptPanel
from entropy.ui.widgets.task_board_widget import TaskBoardWidget
from entropy.ui.design.prefs import install_splitter_persistence

TAB_CHANGES = 0
TAB_RECEIPT = 1


class BoardPanel(QFrame):
    """Ofis kanbanı sarmalayıcısı; dışarıya kart seçimini yayar."""

    card_selected = Signal(str)

    def __init__(self, parent=None, board: Any = None, office: str = "", bridge: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Faz 12-D.2: bölücü konumu QSettings'e yazılır (denetim D12-07).

        install_splitter_persistence("desk.board", splitter)
        self.board_widget = TaskBoardWidget(parent=self, board=board, office=office, bridge=bridge)
        self.board_widget.card_selected.connect(self.card_selected)
        self.board_widget.card_selected.connect(self._on_card_selected)
        splitter.addWidget(self.board_widget)

        self.detail_tabs = QTabWidget()
        self.changes_panel = ChangesPanel(parent=self)
        self.receipt_panel = ReceiptPanel(parent=self, office=office)
        self.detail_tabs.addTab(self.changes_panel, "Değişiklikler")
        self.detail_tabs.addTab(self.receipt_panel, "Makbuz")
        self.detail_tabs.setMinimumHeight(120)
        splitter.addWidget(self.detail_tabs)
        splitter.setSizes([420, 240])
        splitter.setChildrenCollapsible(True)
        layout.addWidget(splitter)

    @property
    def office(self) -> str:
        return self.board_widget.office

    def set_office(self, office: str) -> None:
        self.board_widget.set_office(office)
        self.receipt_panel.set_office(office)
        self.changes_panel.set_card(None)

    def refresh(self) -> None:
        self.board_widget.refresh_cards()

    def select_card(self, card_id: str) -> None:
        self.board_widget.select_card(card_id)
        self._on_card_selected(card_id)

    def selected_card(self) -> Optional[Any]:
        return self.board_widget.get_card(self.board_widget.selected_id)

    @Slot(str)
    def refresh_card_detail(self, card_id: str = "") -> None:
        """
        Kart detayını (Değişiklikler + Makbuz) yeniden okur.

        Faz 10-D: takip turu bittiğinde makbuza yeni satırlar düşer; seçim
        değiştirilmeden panellerin tazelenmesi gerekir. Verilen kart seçili
        değilse hiçbir şey yapılmaz (kullanıcının baktığı kart değişmesin).
        """
        target = str(card_id or "")
        current = str(getattr(self.board_widget, "selected_id", "") or "")
        if target:
            bare = target[5:] if target.startswith("card-") else target
            if current not in (target, bare):
                return
        if not current:
            return
        self.board_widget.refresh_cards()
        self._on_card_selected(current)

    @Slot(str)
    def _on_card_selected(self, card_id: str) -> None:
        """Kart seçimi Değişiklikler ve Makbuz bölmelerine uygulanır."""
        card = self.board_widget.get_card(card_id)
        self.changes_panel.set_card(card)
        self.receipt_panel.set_card(card, self.office)
