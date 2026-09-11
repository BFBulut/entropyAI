"""NavStrip — üst şeritteki yatay bölüm düğmeleri (Faz 14-E).

Neden: kullanıcı düzeni "yedi bölüm yukarıda küçük düğmeler, sohbet sağda tam
panel" olarak tarif etti (Faz 14 planı §0). Dikey `NavList` sol sütunda 168 px
yer yiyordu ve sohbeti alta sıkıştırıyordu; şerit yalnızca 48 px'lik üst çubuğun
içinde yaşar, içerik alanını serbest bırakır.

Sözleşme: `NavList` ile **aynı** `QTabWidget` alt kümesini taklit eder
(`addTab / count / tabText / setTabText / indexOf / widget / setCurrentIndex /
currentIndex / setCurrentWidget / currentWidget / currentChanged / set_activity /
visible_item_count`). Böylece `zen_mode`, komut paleti, testler ve
`scripts/ui_audit.py` ekran taraması tek satır bile değişmeden çalışır.

Farkı: gövde (`stack`) şeridin içinde DEĞİL; çağıran onu ayrı bir yere koyar
(Zen'de üst şeridin altındaki içerik alanı). Bu yüzden `NavStrip` bir düğme
şeridi, `NavStrip.stack` ise bağımsız bir `QStackedWidget`'tir.

Kapı: `nav_strip_buttons == 7`, her düğmede çizilebilir ikon + erişilebilir ad,
seçili durum aynı anda tek (`scripts/ui_audit.py`, `--final`).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QScrollArea, QSizePolicy, QStackedWidget,
    QToolButton, QWidget,
)

from entropy.ui.design import TOKENS

__all__ = ["NavStrip", "NAV_BUTTON_ICON_PX"]

#: Düğme ikonunun kenar uzunluğu (px) — belirteçten gelir (ui-design §0.1).
#: B notu §4 "32×32" hedefini 48 px'lik şeride oturtmak için belirteç
#: `icon.nav` = 24 px ikon + 36 px düğme yüksekliği olarak ölçüldü; daha büyük
#: ikon düğmeyi 48 px şeridin dışına taşırıyordu (ölçüm: 1920×1080 offscreen).
NAV_BUTTON_ICON_PX = TOKENS["icon"]["nav"]


class NavStrip(QWidget):
    """İkon + 11 px etiketten oluşan yatay bölüm şeridi + ayrı gövde yığını."""

    currentChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("navStrip")
        self.setProperty("role", "toolbarGroup")
        self._icons: List[str] = []
        self._labels: List[str] = []
        self._pages: List[QWidget] = []
        self._hosts: List[QScrollArea] = []
        self.buttons: List[QToolButton] = []

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TOKENS["space"]["1"])
        self._row = row
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.idClicked.connect(self._on_button_clicked)

        # Gövde: şeridin dışında yaşar; çağıran içerik alanına yerleştirir.
        self.stack = QStackedWidget()
        self.stack.setObjectName("navStack")
        self._current = -1

    # ------------------------------------------------------- QTabWidget API

    def addTab(self, widget: QWidget, label: str, icon_name: str = "",
               tooltip: str = "") -> int:
        """Bölüm ekler: şeride bir düğme, yığına bir kaydırmalı sayfa."""
        from entropy.ui.design import icon as design_icon

        host = QScrollArea()
        host.setObjectName("navPage")
        host.setWidgetResizable(True)
        host.setFrameShape(QScrollArea.Shape.NoFrame)
        host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        host.setWidget(widget)
        self._pages.append(widget)
        self._hosts.append(host)
        index = self.stack.addWidget(host)

        btn = QToolButton(self)
        btn.setObjectName("navStripButton")
        btn.setCheckable(True)
        btn.setAutoRaise(True)
        btn.setText(label)
        btn.setAccessibleName(tooltip or label)
        btn.setToolTip(tooltip or label)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setIconSize(QSize(NAV_BUTTON_ICON_PX, NAV_BUTTON_ICON_PX))
        btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if icon_name:
            ico = design_icon(icon_name, color=TOKENS["color"]["text.muted"])
            if ico is not None and not ico.isNull():
                btn.setIcon(ico)
        self._icons.append(icon_name)
        self._labels.append(label)
        self.buttons.append(btn)
        self.group.addButton(btn, index)
        self._row.addWidget(btn)

        if self._current < 0:
            self.setCurrentIndex(0)
        return index

    def count(self) -> int:
        return self.stack.count()

    def tabText(self, index: int) -> str:
        if 0 <= index < len(self.buttons):
            return self.buttons[index].text()
        return ""

    def setTabText(self, index: int, text: str) -> None:
        if 0 <= index < len(self.buttons):
            self.buttons[index].setText(text)
            self.buttons[index].setToolTip(text)
            self.buttons[index].setAccessibleName(text)

    def indexOf(self, widget: QWidget) -> int:
        if widget in self._pages:
            return self._pages.index(widget)
        return self.stack.indexOf(widget)

    def widget(self, index: int) -> Optional[QWidget]:
        if 0 <= index < len(self._pages):
            return self._pages[index]
        return self.stack.widget(index)

    def currentIndex(self) -> int:
        return self.stack.currentIndex()

    def currentWidget(self) -> Optional[QWidget]:
        return self.widget(self.currentIndex())

    def setCurrentIndex(self, index: int) -> None:
        if not (0 <= index < self.count()):
            return
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        if index != self._current:
            self._current = index
            self.currentChanged.emit(index)

    def setCurrentWidget(self, widget: QWidget) -> None:
        index = self.indexOf(widget)
        if index >= 0:
            self.setCurrentIndex(index)

    # ------------------------------------------------------------- yardımcı

    def set_activity(self, label: str, count: int, noun: str = "çalışan") -> bool:
        """Bir bölüm düğmesine canlı etkinlik noktası koyar (13-A2 madde 4)."""
        base = str(label).split(" ●")[0]
        for btn in self.buttons:
            if btn.text().split(" ●")[0] != base:
                continue
            btn.setText(f"{base} ●{count}" if count > 0 else base)
            btn.setToolTip(f"{base}: {count} {noun}" if count > 0 else base)
            btn.setAccessibleName(btn.toolTip())
            return True
        return False

    def visible_item_count(self) -> int:
        """Kaydırmadan görünen bölüm sayısı (kapı: 1366'da yedisi de)."""
        visible = 0
        for btn in self.buttons:
            if btn.isVisibleTo(self) and btn.width() > 0:
                visible += 1
        return visible

    def set_compact(self, compact: bool) -> None:
        """Dar pencerede etiket gizlenir; ikon + erişilebilir ad kalır.

        `ui-design` §0.10: metni kaldıran sadeleştirme yerine ikon **ve**
        `accessibleName` koymak zorundadır; ikisi de burada duruyor.
        """
        style = (
            Qt.ToolButtonStyle.ToolButtonIconOnly if compact
            else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        for btn in self.buttons:
            if btn.icon().isNull():
                continue  # ikon çizilemiyorsa metin TEK tanıtıcıdır, kalır
            btn.setToolButtonStyle(style)

    def checked_count(self) -> int:
        """Aynı anda seçili düğme sayısı (kapı: tam olarak 1)."""
        return sum(1 for btn in self.buttons if btn.isChecked())

    def _on_button_clicked(self, index: int) -> None:
        self.setCurrentIndex(index)
