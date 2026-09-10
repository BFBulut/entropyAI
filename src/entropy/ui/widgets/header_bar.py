"""Üst çubuk bileşenleri — dört öğe (Faz 11-E adım 2).

Denetim (D-08): Zen üst çubuğunda **18**, Chat'te **15+** doğrudan denetim vardı;
460 px genişlikte çubuk 6 satıra sarıyor ve pencerenin %22,5'ini yiyordu.
Bu modül çubuğu dört öğeye indirir ve iki kipte de aynı bileşenleri kullanır:

1. `BrandCluster`  — durum noktası (çekirdek) + ürün adı + mod anahtarı
2. `ModelCapsule`  — sağlayıcı / model / efor tek kapsülde, tıklayınca açılır
3. `StatusCluster` — kimlik + token + bağlam + gelen kutusu rozetleri
4. `PaletteButton` — komut paleti (Ctrl+K)

Pencere denetimleri (küçült/büyüt/kapat) ayrı bir `WindowControls` çerçevesinde
durur ve "öğe" sayılmaz (çerçevesiz pencerenin sistem başlık çubuğu karşılığı).

Tasarım notu: kapsülde " · " ile birleştirilmiş üst-veri dizesi **kullanılmaz**
(`skills/ui-design/SKILL.md` §5 yasaklı desen). Sağlayıcı soluk metin, model
gövde metni, efor ayrı bir rozettir.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from entropy.core.event_bus import bus
from entropy.ui.design import TOKENS, icon as design_icon

__all__ = [
    "BrandCluster",
    "ModelCapsule",
    "StatusCluster",
    "PaletteButton",
    "WindowControls",
    "make_icon_button",
    "context_badge_tone",
    "repolish",
]

_SPACE = TOKENS["space"]
_COLOR = TOKENS["color"]


def make_icon_button(
    icon_name: str,
    accessible_name: str,
    tooltip: str = "",
    parent: Optional[QWidget] = None,
) -> QPushButton:
    """Belirteçli ikon düğmesi: 28×28 (WCAG 2.5.8 tabanı 24 px'in üstünde).

    `setAccessibleName` **zorunludur**; ekran okuyucu ipucu değil adı okur.
    """
    btn = QPushButton(parent)
    btn.setProperty("role", "icon")
    btn.setAccessibleName(accessible_name)
    btn.setToolTip(tooltip or accessible_name)
    ico = design_icon(icon_name, color=_COLOR["text.muted"])
    if ico is not None and not ico.isNull():
        btn.setIcon(ico)
    else:  # QtAwesome yoksa ad görünür kalsın (arayüz boş düğme göstermez)
        btn.setText(accessible_name[:1].upper())
    return btn


class BrandCluster(QFrame):
    """Durum noktası + ürün adı + mod anahtarı (tek öğe).

    Çekirdek görselleştirici merkez sütundan buraya iner (denetim D-11: merkezin
    %93'ü boştu). Nokta `role="statusDot"` taşır; rengi `tone` özelliğinden gelir.
    """

    def __init__(self, current_mode: str = "zen", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("brandCluster")
        self.setProperty("role", "toolbarGroup")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_SPACE["2"])

        self.status_dot = QLabel("●")
        self.status_dot.setProperty("role", "statusDot")
        self.status_dot.setProperty("tone", "ok")
        self.status_dot.setAccessibleName("Çekirdek durumu")
        self.status_dot.setToolTip("Entropy AI hazır")
        row.addWidget(self.status_dot)

        self.title = QLabel("Entropy AI")
        self.title.setProperty("role", "heading")
        self.title.setToolTip("Entropy AI")
        row.addWidget(self.title)

        self.mode_btn = QPushButton(self._mode_label(current_mode))
        self.mode_btn.setProperty("variant", "ghost")
        self.mode_btn.setAccessibleName("Kip anahtarı")
        self.mode_btn.setToolTip("Kip değiştir: Zen (Ctrl+1) · Chat (Ctrl+2) · Floating (Ctrl+3)")
        self._menu = QMenu(self.mode_btn)
        for key, label in (("zen", "Zen"), ("chat", "Chat"), ("floating", "Floating")):
            act = self._menu.addAction(label)
            act.setData(key)
        self._menu.triggered.connect(self._on_mode_chosen)
        self.mode_btn.setMenu(self._menu)
        row.addWidget(self.mode_btn)

    def insert_core(self, widget: QWidget) -> None:
        """Küçük çekirdek görselleştiriciyi durum noktasının yerine koyar."""
        row = self.layout()
        row.insertWidget(0, widget)
        self.status_dot.setVisible(False)
        self.core = widget

    @staticmethod
    def _mode_label(mode: str) -> str:
        return {"zen": "Zen", "chat": "Chat", "floating": "Floating"}.get(mode, "Zen")

    def _on_mode_chosen(self, action) -> None:
        mode = str(action.data() or "")
        if mode:
            bus.mode_requested.emit(mode)

    def set_state(self, state: str) -> None:
        """`core_state_changed` durumunu noktaya yansıtır (metin yok, renk var)."""
        tone, tip = {
            "thinking": ("warn", "Düşünüyor"),
            "executing": ("warn", "Yürütülüyor"),
            "error": ("danger", "Hata"),
        }.get(state, ("ok", "Hazır"))
        self.status_dot.setProperty("tone", tone)
        self.status_dot.setToolTip(f"Entropy AI: {tip}")
        repolish(self.status_dot)


class ModelCapsule(QFrame):
    """Sağlayıcı · model · efor tek kapsülde; tıklayınca açılır yüzey.

    Kapsül **kutuları taşır, kopyalamaz**: `provider_combo`, `model_combo` ve
    `effort_combo` gerçek nesneleridir ve açılır yüzeyin içinde yaşar. Böylece
    üst çubuk dört öğeye inerken mevcut davranış ve testler korunur.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("modelCapsule")
        self.setProperty("role", "toolbarGroup")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.button = QPushButton("model")
        self.button.setObjectName("modelCapsuleButton")
        self.button.setAccessibleName("Sağlayıcı, model ve efor")
        self.button.setToolTip("Sağlayıcı, model ve efor seçimi")
        self.button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.button.clicked.connect(self.toggle_popup)
        row.addWidget(self.button)

        # Açılır yüzey: kapsülün altında, palet ile aynı yüzey belirteci.
        self.popup = QFrame(self, Qt.WindowType.Popup)
        self.popup.setProperty("role", "palette")
        self.popup_layout = QVBoxLayout(self.popup)
        self.popup_layout.setContentsMargins(
            _SPACE["3"], _SPACE["3"], _SPACE["3"], _SPACE["3"]
        )
        self.popup_layout.setSpacing(_SPACE["2"])
        self._provider = ""
        self._model = ""
        self._effort = ""
        self._compact = False

    def add_row(self, label: str, widget: QWidget) -> None:
        """Açılır yüzeye etiketli bir satır ekler."""
        cap = QLabel(label)
        cap.setProperty("role", "label")
        self.popup_layout.addWidget(cap)
        widget.setParent(self.popup)
        widget.setAccessibleName(label)
        self.popup_layout.addWidget(widget)
        # Açılır yüzey hiç gösterilmese bile çocuklar gerçek genişliğe ulaşsın
        # (model kutusunun kırpılmadığını ölçen testler bunu okur).
        self.popup.adjustSize()

    def insert_caption(self, index: int, label: str) -> None:
        """Verilen konuma etiket ekler (koşullu eklenen kutular için)."""
        cap = QLabel(label)
        cap.setProperty("role", "label")
        self.popup_layout.insertWidget(index, cap)

    def toggle_popup(self) -> None:
        if self.popup.isVisible():
            self.popup.hide()
            return
        self.popup.adjustSize()
        self.popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        self.popup.show()

    def set_compact(self, compact: bool) -> None:
        """Dar pencerede kapsül yalnızca kısa model adını gösterir."""
        self._compact = compact
        self._render()

    def set_summary(self, provider: str, model: str, effort: str = "") -> None:
        """Kapsül metni. Üst-veri " · " ile birleştirilmez (yasaklı desen)."""
        self._provider = (provider or "").strip()
        self._model = (model or "").strip() or "model seçilmedi"
        self._effort = (effort or "").strip()
        self._render()

    def _render(self) -> None:
        provider, model, effort = self._provider, self._model, self._effort
        if getattr(self, "_compact", False):
            text = model.split("-")[0] if "-" in model else model
        else:
            text = f"{provider}  {model}" if provider else model
            if effort:
                text = f"{text}  [{effort}]"
        self.button.setText(text)
        self.button.setToolTip(
            f"Sağlayıcı: {provider or '—'}\nModel: {model}\nEfor: {effort or '—'}"
        )


class StatusCluster(QFrame):
    """Kimlik + token + bağlam + gelen kutusu rozetleri (tek öğe)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("statusCluster")
        self.setProperty("role", "toolbarGroup")
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(_SPACE["1"])
        self._secondary: list = []
        self._compact = False

    #: Dar pencerede gizlenecek ikincil rozetler (kimlik ve gelen kutusu kalır).
    def add(self, widget: QWidget, secondary: bool = False) -> None:
        self.row.addWidget(widget)
        if secondary:
            self._secondary.append(widget)

    def set_compact(self, compact: bool) -> None:
        """Dar pencerede ikincil rozetleri gizler (aşamalı açığa çıkarma).

        Bilgi kaybolmaz: token ve bağlam sayısı kapsül ipucunda ve komut
        paletinde durur. Denetim D-08: 460 px'te çubuk 6 satıra sarıyordu.
        """
        if compact == self._compact:
            return
        self._compact = compact
        for widget in self._secondary:
            widget.setVisible(not compact)


class PaletteButton(QPushButton):
    """Komut paleti düğmesi — birincil gezinme (denetim IA-9)."""

    def __init__(self, on_open: Optional[Callable[[], None]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__("Ctrl+K", parent)
        self.setObjectName("paletteButton")
        self.setAccessibleName("Komut paleti")
        self.setToolTip("Komut paleti: komut, yetenek, ajan, ofis, rapor ve pencere eylemleri (Ctrl+K)")
        ico = design_icon("search", color=_COLOR["text.muted"])
        if ico is not None and not ico.isNull():
            self.setIcon(ico)
        if on_open is not None:
            self.clicked.connect(on_open)


class WindowControls(QFrame):
    """Küçült / büyüt / kapat — çerçevesiz pencerenin başlık çubuğu karşılığı."""

    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("windowControls")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_SPACE["1"])

        self.btn_minimize = make_icon_button("chrome-minimize", "Küçült", "Küçült", self)
        self.btn_minimize.clicked.connect(self.minimize_requested.emit)
        row.addWidget(self.btn_minimize)

        self.btn_maximize = make_icon_button(
            "chrome-maximize", "Ekranı kapla",
            "Ekranı kapla / geri al (üst çubuğa çift tıklama da yapar)", self,
        )
        self.btn_maximize.clicked.connect(self.maximize_requested.emit)
        row.addWidget(self.btn_maximize)

        self.btn_close = make_icon_button("chrome-close", "Kapat", "Kapat", self)
        self.btn_close.setProperty("variant", "danger")
        self.btn_close.clicked.connect(self.close_requested.emit)
        row.addWidget(self.btn_close)


def context_badge_tone(color: str) -> str:
    """`token_badge.format_context_badge` rengini `tone` belirtecine çevirir.

    Faz 11-E: rozet rengi artık yerel QSS ile değil `tone` özelliğiyle gelir
    (tek vurgu kuralı). Biçimlendirici sözleşmesi (metin, ipucu, renk)
    değişmedi; yalnızca rengin uygulanma yolu değişti.
    """
    from entropy.ui.widgets.token_badge import CONTEXT_WARN_COLOR

    return "warn" if str(color).lower() == CONTEXT_WARN_COLOR.lower() else "ok"


def repolish(widget: QWidget) -> None:
    """`qproperty` değiştikten sonra QSS'in yeniden uygulanmasını sağlar."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
