"""Çerçevesiz pencere için taşıma/boyutlandırma yardımcısı — Faz 8.

Sorun (kullanıcı, v0.5.1 exe): Zen penceresi `FramelessWindowHint` ile
açılıyordu ama hiçbir fare olayı işlenmiyordu. Başlık çubuğu olmadığı için
pencere **taşınamıyor**, kenarlarından **boyutlandırılamıyor**, küçültme /
maksimize düğmesi de yoktu. Tek çıkış yolu idi.

Çözüm (en az riskli seçenek): çerçeveyi geri getirmek yerine — geri getirmek
tüm tema/köşe yuvarlaması düzenini bozardı — Qt'nin **sistem** taşıma ve
boyutlandırma API'leri kullanılır:

* `QWindow.startSystemMove()`  — pencereyi pencere yöneticisine taşıttırır;
  kendi `move()` döngümüzü yazmaya göre DPI/çoklu monitör davranışı doğrudur.
* `QWindow.startSystemResize(edges)` — aynı gerekçeyle kenar boyutlandırma.

Her ikisi de Windows'ta yerel sürükleme başlatır; snap (Win+ok, kenara yapışma)
ve çift monitör geçişleri bedava gelir.
"""

import logging

from PySide6.QtCore import QEvent, QObject, Qt

logger = logging.getLogger(__name__)


#: Kenar yakalama bandı (piksel). Çok küçük olursa kullanıcı tutamaz.
RESIZE_MARGIN = 6


def has_edges(edges) -> bool:
    """`Qt.Edge` bayrağı boş mu? (Faz 9 — donma kök nedeni A)

    PySide6 6.7+'ta `Qt.Edge` bir `enum.Flag`'dır (IntFlag değil); `int(edges)`
    `TypeError: int() argument must be ... not 'Edge'` fırlatır. Bu istisna olay
    süzgecinden kaçtığı için her kenar tıklamasında CRITICAL basılıyor ve olay
    dağıtımı yarıda kalıyordu. `.value` varsa onu, yoksa `bool()`u kullanırız —
    her iki PySide6 sürümünde de doğru çalışır.
    """
    if edges is None:
        return False
    value = getattr(edges, "value", None)
    if value is not None:
        return bool(value)
    return bool(edges)


class FramelessWindowHelper(QObject):
    """Çerçevesiz bir üst pencereye taşıma + kenar boyutlandırma ekler.

    `handle` verilen widget (üst çubuk) sürükleme tutamacıdır; üzerinde çift
    tıklama maksimize/geri yapar. Pencerenin kenar bandına basmak sistem
    boyutlandırmasını başlatır.
    """

    def __init__(self, window, handle=None, resize_margin: int = RESIZE_MARGIN):
        super().__init__(window)
        self.window = window
        self.handle = handle
        self.margin = max(2, int(resize_margin))
        #: Yerel (modal) sürükle/boyutlandır döngüsü etkin mi — tek sefer kilidi.
        self._system_drag = False
        window.installEventFilter(self)
        if handle is not None:
            handle.installEventFilter(self)

    # --------------------------------------------------------------- yardımcı

    def _edges_at(self, global_pos):
        """Genel koordinat pencere kenar bandındaysa ilgili kenarları döndürür."""
        try:
            local = self.window.mapFromGlobal(global_pos)
        except Exception:
            return Qt.Edge(0)
        w, h = self.window.width(), self.window.height()
        edges = Qt.Edge(0)
        if local.x() <= self.margin:
            edges |= Qt.Edge.LeftEdge
        elif local.x() >= w - self.margin:
            edges |= Qt.Edge.RightEdge
        if local.y() <= self.margin:
            edges |= Qt.Edge.TopEdge
        elif local.y() >= h - self.margin:
            edges |= Qt.Edge.BottomEdge
        return edges

    def toggle_maximize(self) -> None:
        """Maksimize <-> geri. Düğme ve çift tıklama aynı yolu kullanır."""
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    # ------------------------------------------------------------ olay süzgeci

    def eventFilter(self, obj, event):  # noqa: N802
        # Faz 9: olay süzgecinden ASLA istisna kaçmamalı. Kaçarsa PySide6'nın
        # sanal metot sarmalayıcısı olayı tüketmeden döner, `sys.excepthook`
        # CRITICAL basar ve olay dağıtımı yarıda kalır (donma).
        try:
            return self._filter(obj, event)
        except Exception:
            logger.warning("Çerçevesiz pencere olay süzgeci hatası", exc_info=True)
            return False

    def _filter(self, obj, event):
        etype = event.type()

        if etype == QEvent.Type.MouseButtonDblClick and obj is self.handle:
            if event.button() == Qt.MouseButton.LeftButton:
                self.toggle_maximize()
                return True
            return False

        if etype == QEvent.Type.MouseButtonRelease:
            # Yerel modal sürükleme döngüsü bittiğinde kilidi aç.
            self._system_drag = False
            return False

        if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            # Faz 9: yerel sürükle/boyutlandır döngüsü içindeyken ikinci kez
            # başlatmak Windows'ta girdi-eşzamanlı çağrı hatası (0x8001010d)
            # üretiyordu; tek seferlik kilit.
            if self._system_drag:
                return False
            handle_win = self.window.windowHandle()
            if handle_win is None:
                return False
            global_pos = event.globalPosition().toPoint()

            # 1) Kenar bandı -> sistem boyutlandırma (maksimizeyken kapalı).
            if not self.window.isMaximized():
                edges = self._edges_at(global_pos)
                if has_edges(edges):
                    try:
                        self._system_drag = True
                        handle_win.startSystemResize(edges)
                        return True
                    except Exception:
                        self._system_drag = False
                        return False

            # 2) Üst çubuk -> sistem taşıma. Olayın buraya ulaşmış olması
            #    zaten hiçbir çocuğun (düğme, açılır liste) onu kabul
            #    etmediği anlamına gelir; düğmeler bozulmaz.
            if obj is self.handle:
                try:
                    self._system_drag = True
                    handle_win.startSystemMove()
                    return True
                except Exception:
                    self._system_drag = False
                    return False

        return False
