"""NavList — sol dikey gezinme (sekme çubuğunun yerine geçer).

Neden: denetimde (`docs/reports/2026-09-10_Faz11_Arastirma_D_...` D-07) Zen'in
yedi sekmesinden 1920×1080'de yalnızca 3'ü, 1366×768'de 2'si görünüyordu;
gerisine kaydırma oklarıyla ulaşılıyordu. Dikey liste yatay yer istemediği için
yedi bölümün hepsi her genişlikte görünür.

Sözleşme: `QTabWidget`'in kullandığımız API'si birebir taklit edilir
(`addTab / count / tabText / setTabText / indexOf / setCurrentIndex /
currentIndex / setCurrentWidget / currentWidget / widget / currentChanged`),
böylece çağıran kod ve mevcut testler değişmeden çalışır.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QListWidget, QListWidgetItem, QScrollArea,
    QSizePolicy, QStackedWidget, QWidget,
)

from entropy.ui.design import TOKENS, icon as design_icon

__all__ = ["NavList"]


class NavList(QWidget):
    """İkon + etiketten oluşan dikey gezinme listesi + `QStackedWidget` gövde."""

    currentChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None, nav_width: int = 168):
        super().__init__(parent)
        self.setObjectName("navRegion")
        self._icons: List[str] = []
        # Faz 12-D.1: her bölüm kendi kaydırma alanında durur. Sebep: yığının
        # `minimumSizeHint`'i sayfaların en büyüğüydü (Raporlar 428 px) ve bu
        # tek başına Zen penceresinin asgari yüksekliğini 834 px'e çıkarıyordu.
        # Kaydırma alanı asgariyi ~50 px'e indirir, içerik kırpılmaz kaydırılır.
        self._pages: List[QWidget] = []
        self._hosts: List[QScrollArea] = []

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TOKENS["space"]["2"])

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setAccessibleName("Bölüm listesi")
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.nav.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.nav.setIconSize(QSize(TOKENS["icon"]["inline"], TOKENS["icon"]["inline"]))
        # Genişlik esnek: 1366'da 168 px, dar pencerede daha az yer kaplar.
        self.nav.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.nav.setMinimumWidth(120)
        self.nav.setMaximumWidth(nav_width)
        self.nav.currentRowChanged.connect(self._on_row_changed)
        row.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.stack.setObjectName("navStack")
        row.addWidget(self.stack, 1)

    # ------------------------------------------------------- QTabWidget API

    def addTab(self, widget: QWidget, label: str, icon_name: str = "") -> int:
        """Bölüm ekler; `icon_name` verilirse `design.icon()` ile çizilir."""
        host = QScrollArea()
        host.setObjectName("navPage")
        host.setWidgetResizable(True)
        host.setFrameShape(QScrollArea.Shape.NoFrame)
        host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        host.setWidget(widget)
        self._pages.append(widget)
        self._hosts.append(host)
        index = self.stack.addWidget(host)
        item = QListWidgetItem(label)
        item.setToolTip(label)
        if icon_name:
            ico = design_icon(icon_name, color=TOKENS["color"]["text.muted"])
            if ico is not None and not ico.isNull():
                item.setIcon(ico)
        self._icons.append(icon_name)
        self.nav.addItem(item)
        if self.nav.currentRow() < 0:
            self.nav.setCurrentRow(0)
        return index

    def count(self) -> int:
        return self.stack.count()

    def tabText(self, index: int) -> str:
        item = self.nav.item(index)
        return item.text() if item is not None else ""

    def setTabText(self, index: int, text: str) -> None:
        item = self.nav.item(index)
        if item is not None:
            item.setText(text)
            item.setToolTip(text)

    def indexOf(self, widget: QWidget) -> int:
        """Sayfa gövdesini de kaydırma kabuğunu da kabul eder."""
        if widget in self._pages:
            return self._pages.index(widget)
        return self.stack.indexOf(widget)

    def widget(self, index: int) -> Optional[QWidget]:
        """Kaydırma kabuğunu değil, çağıranın eklediği gövdeyi döndürür."""
        if 0 <= index < len(self._pages):
            return self._pages[index]
        return self.stack.widget(index)

    def currentIndex(self) -> int:
        return self.stack.currentIndex()

    def currentWidget(self) -> Optional[QWidget]:
        return self.widget(self.currentIndex())

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < self.count():
            self.nav.setCurrentRow(index)

    def setCurrentWidget(self, widget: QWidget) -> None:
        index = self.stack.indexOf(widget)
        if index >= 0:
            self.setCurrentIndex(index)

    # ------------------------------------------------------------- yardımcı

    def visible_item_count(self) -> int:
        """Kaydırmadan görünen bölüm sayısı (kapı ölçümü: 1366'da hepsi)."""
        viewport = self.nav.viewport().rect()
        visible = 0
        for i in range(self.nav.count()):
            rect = self.nav.visualItemRect(self.nav.item(i))
            if rect.top() >= viewport.top() and rect.bottom() <= viewport.bottom():
                visible += 1
        return visible

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            self.currentChanged.emit(row)
