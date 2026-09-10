"""Satır sonunda alta kayan (wrap) yatay yerleşim — Faz 8.

Sorun (kullanıcı, v0.5.1): Chat ve Zen üst çubukları tek satırlık bir
`QHBoxLayout` içindeydi ve toplam örtük genişlikleri ~2450 px'ti. Faz 6'da bu,
yatay kaydırılabilir bir `QScrollArea` ile "çözülmüştü": pencere minimumu düştü
ama sağdaki düğmeler (Zen, rozetler) görünmez oldu — kullanıcı bunları
bulabilmek için çubuğu kaydırmak zorundaydı ve kaydırma çubuğu da gizliydi.

Çözüm: içerik daralmak yerine **alt satıra kayar**. `FlowLayout`
`heightForWidth` uygular; böylece 1000 px'lik bir pencerede tüm düğmeler
görünür kalır, yalnızca çubuk 2-3 satır yüksekliğe çıkar.

Minimum genişlik en geniş tek öğe kadardır (kaydırma alanına gerek yok).
"""

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QFrame, QLayout, QScrollArea, QSizePolicy


class FlowLayout(QLayout):
    """Öğeleri soldan sağa dizen, sığmayınca alt satıra geçen yerleşim."""

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 6, v_spacing: int = 4):
        super().__init__(parent)
        self._items = []
        self._h_space = h_spacing
        self._v_space = v_spacing
        self.setContentsMargins(QMargins(margin, margin, margin, margin))

    # ------------------------------------------------------------ QLayout API

    def addItem(self, item):  # noqa: N802
        self._items.append(item)

    def addStretch(self, _stretch: int = 0) -> None:
        """`QHBoxLayout` ile kaynak uyumluluğu: akan yerleşimde esneme yoktur."""
        return None

    def addSpacing(self, _size: int) -> None:
        """`QHBoxLayout` ile kaynak uyumluluğu: boşluk zaten `h_spacing`."""
        return None

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        """En geniş tek öğe kadar genişlik; yükseklik tek satır.

        Kritik nokta: toplam genişlik değil **azami öğe** genişliği döner,
        yoksa çubuk yine ~2450 px minimum dayatırdı.
        """
        size = QSize(0, 0)
        for item in self._items:
            hint = item.minimumSize()
            size = QSize(max(size.width(), hint.width()), max(size.height(), hint.height()))
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    # ------------------------------------------------------------- yerleşim

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            widget = item.widget()
            if widget is not None and not widget.isVisibleTo(widget.parentWidget()):
                # Gizli rozetler (ör. okunmadı sayacı 0) yer kaplamamalı.
                if widget.isHidden():
                    continue
            next_x = x + hint.width() + self._h_space
            if next_x - self._h_space > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._v_space
                next_x = x + hint.width() + self._h_space
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()


class FlowHeaderFrame(QFrame):
    """Akan yerleşimli üst çubuk çerçevesi.

    `QWidget` varsayılan olarak yerleşiminin `heightForWidth`'ini üst düzene
    bildirmez; boyut ilkesine `setHeightForWidth(True)` verip iki metodu
    yönlendirmezsek çubuk daraldığında alt satırlar kırpılır.
    """

    def __init__(self, parent=None, margins=(10, 6, 10, 6)):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self._flow = FlowLayout(self, margin=0, h_spacing=6, v_spacing=4)
        self._flow.setContentsMargins(*margins)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def flow(self) -> FlowLayout:
        return self._flow

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._flow.heightForWidth(width)


class FlowStripHost(QScrollArea):
    """Akan bir şeridi, asgari yükseklik dayatmadan taşıyan kaydırma kabuğu.

    Neden (Faz 12-D.1): `FlowHeaderFrame` `heightForWidth` bildirir ve üst
    `QVBoxLayout` pencerenin asgari yüksekliğini hesaplarken şeridin EN DAR
    genişlikteki satır sayısını kullanır — Zen'in durum şeridinde bu 5 satır
    (+109 px) demekti ve pencerenin 540 px'e inmesini engelliyordu. Şerit
    ikincil kromdur: kabuk asgariyi tek satırda tutar, yer varsa `max_rows`
    satıra kadar büyür, daha fazlası gerekirse dikey kaydırılır (kırpılmaz).
    """

    def __init__(self, strip: FlowHeaderFrame, max_rows: int = 2, parent=None):
        super().__init__(parent)
        self._strip = strip
        self._max_rows = max(1, int(max_rows))
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidget(strip)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    def strip(self) -> FlowHeaderFrame:
        return self._strip

    def _row_height(self) -> int:
        return max(1, self._strip.flow().minimumSize().height())

    def sizeHint(self) -> QSize:  # noqa: N802
        width = self.viewport().width() or self.width()
        wanted = self._strip.heightForWidth(width) if width > 0 else self._row_height()
        return QSize(
            self._strip.minimumSizeHint().width(),
            min(max(wanted, self._row_height()), self._row_height() * self._max_rows),
        )

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, self._row_height())

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.updateGeometry()


def fit_combo_to_contents(combo, min_width: int = 60, extra: int = 0) -> int:
    """Açılır kutuyu en uzun öğesini kırpmadan gösterecek genişliğe sabitler.

    Faz 9 kök nedeni: Chat üst çubuğunda model kutusuna
    `setMaximumWidth(170)` + `AdjustToMinimumContentsLength` verilmişti; 636 px
    genişlikte "claude-opus-5" bile "laude-opus-5" diye kırpılıyordu. Akan
    yerleşim (FlowLayout) öğe genişliğini `sizeHint()` üzerinden alır, yani
    kutuyu daraltmak yerine alt satıra kaydırabiliriz: doğru çözüm kutuya
    metnin gerektirdiği asgari genişliği vermek.

    Dönen değer uygulanan piksel genişliğidir.
    """
    texts = [combo.itemText(i) for i in range(combo.count())]
    texts.append(combo.currentText())
    line_edit = combo.lineEdit() if combo.isEditable() else None
    if line_edit is not None:
        texts.append(line_edit.placeholderText())

    # Faz 11-E: ölçü, kutunun O ANKİ fontuyla değil, tasarım sisteminin gövde
    # fontuyla da hesaplanır ve büyüğü alınır. Uygulama düzeyi stil sayfası
    # (`apply_design_system`) kutu kurulduktan SONRA uygulandığında yazı tipi
    # büyüyor ve daha önce sabitlenmiş genişlik metni kırpıyordu.
    from PySide6.QtGui import QFontMetrics

    candidates = [combo.fontMetrics()]
    try:
        from entropy.ui.design import TOKENS

        design_font = combo.font()
        design_font.setPixelSize(int(TOKENS["type"]["body"]["size"]))
        candidates.append(QFontMetrics(design_font))
    except Exception:
        pass
    widest = max(
        (m.horizontalAdvance(t or "") for m in candidates for t in texts),
        default=0,
    )
    # Çerçeve + iç dolgu + açılır ok payı (stil sayfasından bağımsız güvenli pay).
    chrome = 44 + extra
    width = max(min_width, widest + chrome)
    combo.setMinimumWidth(width)
    combo.setMaximumWidth(width)
    return width
