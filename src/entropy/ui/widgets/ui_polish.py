"""
Arayüz cilası için ortak yardımcılar (Faz 4).

Neden ayrı modül: metin kırpma, kaydırma çubuğu politikası ve okunaklı
tasarım belirteçleri liste/kart/kanban/ofis panellerinin her birinde ayrı ayrı
kodlanmıştı; kimi yerde hiç yoktu (uzun ofis amacı yatay kaydırma çubuğu
doğuruyor, uzun kart başlığı sütunu genişletiyordu). Tek yerde toplanınca
davranış her panelde aynı olur ve testle sabitlenebilir.

Kurallar:
- Kırpma her zaman `Qt.TextElideMode.ElideRight`; kırpılan metnin tamamı
  ipucunda (tooltip) durur — bilgi kaybı olmaz, yalnızca yer kazanılır.
- Yatay kaydırma çubukları kapalı: dikey listelerde yatay çubuk hem çirkin
  hem de gereksiz, çünkü metin zaten kırpılıyor.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractScrollArea, QLabel, QListWidget, QWidget,
)

from entropy.ui.themes.cyber_theme import READING_TOKENS as RT

# Gövde metni için okunaklı boyut aralığı (tasarım sistemi): 14–15 px.
BODY_PX = 14
BODY_STRONG_PX = 15
LABEL_PX = 12


def elide_text(text: str, width_px: int, widget: Optional[QWidget] = None) -> str:
    """Metni verilen piksel genişliğine `…` ile kırpar (sağdan)."""
    if not text:
        return ""
    metrics = QFontMetrics(widget.font()) if widget is not None else QFontMetrics(QLabel().font())
    return metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(24, int(width_px)))


def apply_list_polish(view: QAbstractItemView, elide: bool = True) -> None:
    """
    Liste/ağaç görünümüne ortak cila: sağdan kırpma + yatay çubuk kapalı.

    `setTextElideMode` yalnızca QListView/QTreeView'da var; başka bir görünüm
    verilirse sessizce atlanır (panel çökmesin diye).
    """
    try:
        if elide:
            view.setTextElideMode(Qt.TextElideMode.ElideRight)
        if isinstance(view, QListWidget):
            view.setWordWrap(False)
    except (AttributeError, TypeError):
        pass
    apply_no_hscroll(view)


def apply_no_hscroll(area: QAbstractScrollArea) -> None:
    """Yatay kaydırma çubuğunu kapatır (dikey çubuk gerektiğinde açık kalır)."""
    try:
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    except (AttributeError, TypeError):
        pass


def set_item_text(item, text: str, tooltip: Optional[str] = None) -> None:
    """
    Liste öğesine metni yazar ve TAM metni ipucuna koyar.

    Görünen metin kırpmayı Qt'ye bırakır (piksel doğru); ipucu ise ham metin
    olduğu için kullanıcı kırpılanı görebilir.
    """
    item.setText(text)
    item.setToolTip(tooltip if tooltip is not None else text)


class ElidedLabel(QLabel):
    """
    Genişliğine göre kendini sağdan kırpan etiket; tam metin ipucunda kalır.

    Düz QLabel uzun metinde ya taşar ya da düzeni genişletir. Burada tam metin
    ayrı tutulur, her `resizeEvent`'te yeniden kırpılır; böylece panel
    daraltılıp genişletildiğinde metin geri gelir (tek yönlü kesme değil).
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None, min_width: int = 40):
        super().__init__(parent)
        self._full_text = str(text)
        self._min_width = int(min_width)
        self.setToolTip(self._full_text)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self._apply()

    def full_text(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:  # noqa: N802 (Qt API)
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._apply()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt API)
        # Etiket düzeni genişletmesin: en küçük genişlik sabit tutulur.
        hint = super().minimumSizeHint()
        return QSize(self._min_width, hint.height())

    def resizeEvent(self, event):  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._apply()

    def _apply(self) -> None:
        width = self.width() or self._min_width
        super().setText(elide_text(self._full_text, width - 2, self))


MODEL_PLACEHOLDER = "(sağlayıcı varsayılanı)"


def apply_model_placeholder(combo, models=None) -> bool:
    """
    Boş model kutusuna yer tutucu koyar; doluysa dokunmaz.

    Üst çubukta "Model:" etiketinin yanındaki kutu boş kalınca aradaki boşluk
    kopmuş bir ayraç gibi görünüyordu. Yer tutucu yalnızca görsel: kutu
    düzenlenebilir kaldığı için kullanıcı istediği model adını yine yazabilir
    ve `currentText()` yer tutucuyu model adı sanmasın diye çağıranlar
    `is_model_placeholder()` ile kontrol eder.
    """
    try:
        has_items = combo.count() > 0 if models is None else bool(models)
        current = (combo.currentText() or "").strip()
        if has_items or current:
            return False
        combo.lineEdit().setPlaceholderText(MODEL_PLACEHOLDER)
        combo.setToolTip(
            "Model listesi alınamadı ya da boş. Boş bırakılırsa sağlayıcının"
            " varsayılan modeli kullanılır; dilerseniz model adını yazabilirsiniz."
        )
        return True
    except (AttributeError, RuntimeError):
        return False


def is_model_placeholder(text: str) -> bool:
    """Yer tutucu metni gerçek bir model adı sayılmamalı."""
    return (text or "").strip() == MODEL_PLACEHOLDER


def body_style(color_key: str = "text_body", size_px: int = BODY_PX, bold: bool = False) -> str:
    """Tasarım sisteminden gövde metni stil dizesi (tek kaynak)."""
    weight = "600" if bold else "400"
    return (
        f"color:{RT.get(color_key, RT['text_body'])}; font-size:{size_px}px;"
        f" font-weight:{weight}; background:transparent; border:none;"
    )


def empty_state_label(message: str, parent: Optional[QWidget] = None) -> QLabel:
    """Boş durum metni: sönük renk, ortalanmış, satır kaydırmalı."""
    label = QLabel(message, parent)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"color:{RT['text_dim']}; font-size:{BODY_PX}px; padding:18px 12px;"
        " background:transparent; border:none;"
    )
    return label


def icon_button_style(accent: Optional[str] = None) -> str:
    """Agent Desk ikon düğmeleri için ortak stil (kare, ipuçlu)."""
    color = accent or RT["accent"]
    return f"""
        QPushButton {{
            background-color:{RT['surface_soft']};
            color:{color};
            border:1px solid {RT['divider_soft']};
            border-radius:{RT['radius_small']};
            padding:4px 8px;
            font-size:{BODY_PX}px;
        }}
        QPushButton:hover {{ border-color:{color}; background-color:{RT['accent_soft']}; }}
        QPushButton:disabled {{ color:{RT['text_dim']}; border-color:{RT['divider_soft']}; }}
    """
