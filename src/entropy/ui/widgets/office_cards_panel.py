"""Ofis kartları — Zen "Görevler" sekmesindeki **salt okunur** bölme.

Faz 12-D.2. Kullanıcı Entropy'nin panosuyla Desk ofislerinin panosunu tek
ekranda görmek istiyor; ancak mimari kural tek yönlüdür (bkz. pinned kural
"Task flow is one-directional"): **Desk kartları Entropy'nin panosuna
girmez.** Bu yüzden burada ayrı, düzenlenemez bir liste vardır:

* kaynak `TaskBoard.list(office=ALL_CARDS)` çıktısının **ofisli** kartları
  (yani `card.office` dolu ve `"entropy"` değil),
* hiçbir düğme, menü ya da sürükleme yoktur — yalnızca okuma,
* `bus.board_state_changed` ile tazelenir (guard: sinyal yoksa panel sessizce
  statik kalır).

Entropy'nin kendi kartları üstteki `TaskBoardWidget`'ta kalır; iki liste
karışmaz.
"""

from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from entropy.core.event_bus import bus
from entropy.ui.design import TOKENS

__all__ = ["OfficeCardsPanel", "ENTROPY_OFFICE"]

#: Entropy'nin kendi kartlarının ofis etiketi (bu panelde GÖSTERİLMEZ).
ENTROPY_OFFICE = "entropy"

#: Panelin yer kaplamaması için gösterilen üst sınır (tek ekran kuralı).
MAX_ROWS = 12


class OfficeCardsPanel(QFrame):
    """Desk ofis kartlarının salt okunur özeti."""

    def __init__(self, parent: Optional[QWidget] = None, board: Any = None):
        super().__init__(parent)
        self.setObjectName("officeCardsPanel")
        self.setProperty("role", "panel")
        self._board = board

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            TOKENS["space"]["2"], TOKENS["space"]["2"],
            TOKENS["space"]["2"], TOKENS["space"]["2"],
        )
        layout.setSpacing(TOKENS["space"]["1"])

        self.title_label = QLabel("Ofis kartları")
        self.title_label.setProperty("role", "heading")
        self.title_label.setToolTip(
            "Agent Desk ofislerinin kartları — salt okunur. Entropy'nin kendi"
            " panosuna girmezler; buradan düzenlenemez."
        )
        layout.addWidget(self.title_label)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("officeCardsList")
        self.list_widget.setAccessibleName("Ofis kartları (salt okunur)")
        # Salt okunur: seçim, düzenleme, sürükleme kapalı.
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.list_widget)

        self.empty_label = QLabel("Henüz ofis kartı yok. Agent Desk'te bir ofis açın.")
        self.empty_label.setProperty("role", "label")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        signal = getattr(bus, "board_state_changed", None)
        if signal is not None:
            try:
                signal.connect(self.on_board_state_changed)
            except Exception:
                pass

        self.refresh()

    # ------------------------------------------------------------------ #
    def _resolve_board(self) -> Any:
        if self._board is not None:
            return self._board
        from entropy.ui.widgets.agents_widget import load_board

        self._board = load_board()
        return self._board

    def office_cards(self) -> List[Any]:
        """Ofisli (Desk) kartlar — Entropy kartları süzülür."""
        board = self._resolve_board()
        if board is None:
            return []
        try:
            from entropy.agents.tasks import ALL_CARDS

            cards = board.list(office=ALL_CARDS)
        except Exception:
            return []
        out = []
        for card in cards or []:
            office = str(getattr(card, "office", "") or "")
            if not office or office == ENTROPY_OFFICE:
                continue
            out.append(card)
        return out

    @Slot()
    def refresh(self) -> None:
        cards = self.office_cards()
        self.list_widget.clear()
        for card in cards[:MAX_ROWS]:
            title = str(getattr(card, "title", "") or getattr(card, "id", ""))
            office = str(getattr(card, "office", "") or "")
            status = str(getattr(card, "status", "") or "")
            agent = str(getattr(card, "agent", "") or "")
            text = f"{office} — {title}"
            item = QListWidgetItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setToolTip(f"Durum: {status or 'bilinmiyor'} · Ajan: {agent or 'atanmadı'}")
            item.setData(Qt.ItemDataRole.UserRole, str(getattr(card, "id", "")))
            self.list_widget.addItem(item)
        self.title_label.setText(f"Ofis kartları ({len(cards)})")
        has_cards = bool(cards)
        self.list_widget.setVisible(has_cards)
        self.empty_label.setVisible(not has_cards)

    @Slot(dict)
    def on_board_state_changed(self, payload: dict) -> None:
        """`bus.board_state_changed` alıcısı (QObject slotu, lambda değil)."""
        self.refresh()

    def is_read_only(self) -> bool:
        """Testin ölçtüğü sözleşme: panel hiçbir düzenleme yolu sunmaz."""
        return (
            self.list_widget.selectionMode() == QAbstractItemView.SelectionMode.NoSelection
            and self.list_widget.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
            and self.list_widget.dragDropMode() == QAbstractItemView.DragDropMode.NoDragDrop
        )
