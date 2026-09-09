"""
Odak modu (Faz 5.5) — Ctrl+Shift+F ile tek panel.

Sorun: Zen üç sütun + alt terminal gösteriyor. Uzun bir rapor okurken ya da
uzun bir istem yazarken çevredeki altı panel dikkat dağıtıyordu; kullanıcı
elle sürükleyip kapatıp sonra geri açmak zorunda kalıyordu.

Odak modu, kayıtlı "yan" widget'ları gizler ve tek bir birincil paneli
bırakır; ikinci kısayol her şeyi geri getirir. Görünürlükten başka hiçbir şey
değişmez: splitter boyutları, sekme seçimi ve veri durumu korunur, böylece
çıkışta ekran aynen geri gelir.

Kullanım (Zen ve Chat aynı):
    controller = install_focus_mode(window, primary=center_col,
                                    secondary=[left_tabs, graph, terminal])
    controller.toggle()
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut

FOCUS_SHORTCUT = "Ctrl+Shift+F"


class FocusModeController(QObject):
    """
    Odak modunun durumunu tutan denetleyici.

    Sinyal alıcısı olarak lambda değil bu QObject'in slotu kullanılır; kısayol
    pencereyle birlikte yok olduğunda bağlantı da kendiliğinden kopar.
    """

    focus_changed = Signal(bool)

    def __init__(self, window, primary=None, secondary: Optional[Sequence[Any]] = None):
        super().__init__(window)
        self.window = window
        self.primary = primary
        self.secondary: List[Any] = [w for w in (secondary or []) if w is not None]
        self.active = False
        # Çıkışta eski görünürlüğü aynen geri koymak için: kullanıcı zaten
        # kapalı bıraktığı bir paneli odak modundan çıkınca açık bulmamalı.
        self._saved_visibility: List[bool] = []

    def is_active(self) -> bool:
        return self.active

    @Slot()
    def toggle(self) -> bool:
        if self.active:
            self.deactivate()
        else:
            self.activate()
        return self.active

    def activate(self) -> None:
        if self.active:
            return
        self._saved_visibility = []
        for widget in self.secondary:
            try:
                self._saved_visibility.append(bool(widget.isVisible()))
                widget.setVisible(False)
            except (AttributeError, RuntimeError):
                self._saved_visibility.append(True)
        if self.primary is not None:
            try:
                self.primary.setVisible(True)
            except (AttributeError, RuntimeError):
                pass
        self.active = True
        self.focus_changed.emit(True)

    def deactivate(self) -> None:
        if not self.active:
            return
        for widget, visible in zip(self.secondary, self._saved_visibility or [True] * len(self.secondary)):
            try:
                widget.setVisible(visible)
            except (AttributeError, RuntimeError):
                pass
        self.active = False
        self.focus_changed.emit(False)

    def hidden_widgets(self) -> List[Any]:
        """Şu an odak modu yüzünden gizli olan widget'lar (test/tanı için)."""
        if not self.active:
            return []
        out = []
        for widget in self.secondary:
            try:
                if not widget.isVisible():
                    out.append(widget)
            except (AttributeError, RuntimeError):
                continue
        return out


def install_focus_mode(window, primary=None, secondary: Optional[Sequence[Any]] = None) -> FocusModeController:
    """Pencereye Ctrl+Shift+F kısayolunu takar ve denetleyiciyi döner."""
    controller = FocusModeController(window, primary=primary, secondary=secondary)
    shortcut = QShortcut(QKeySequence(FOCUS_SHORTCUT), window)
    shortcut.activated.connect(controller.toggle)
    window._focus_mode = controller
    window._focus_mode_shortcut = shortcut
    return controller
