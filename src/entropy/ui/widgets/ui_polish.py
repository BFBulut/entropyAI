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


def accept_model_selection(bridge, combo, model_name: str) -> bool:
    """
    Üst çubuk model seçimini köprüye uygular; geçersizse kutuyu geri alır.

    Faz 9 / B-9.2: model kutusu serbest metin. Yabancı bir ad (Claude
    oturumundayken `gemini-…`) köprüye geçince her koşu geçersiz `--model`
    ile başlıyor, kullanıcı ise kutuda o adı seçili görüyordu. Doğrulama
    köprünün kendi süzgecine bırakılır (`_is_claude_model`/`_is_agy_model`,
    `getattr` ile aranır); yoksa ön ek kuralına düşülür. Reddedilirse kutu
    köprünün gerçek modeline döner ve ipucu güncellenir.

    True = seçim uygulandı.
    """
    name = (model_name or "").strip()
    if not name or is_model_placeholder(name):
        return False
    provider = str(getattr(bridge, "provider_name", "") or "")
    checker = getattr(bridge, "_is_claude_model", None) if provider == "claude" else None
    if checker is None and provider == "agy":
        checker = getattr(bridge, "_is_agy_model", None)
    valid = True
    if checker is not None:
        try:
            valid = bool(checker(name))
        except Exception:
            valid = True
    else:
        low = name.lower()
        if provider == "claude":
            valid = low.startswith("claude-") or low.split("[", 1)[0] in {
                "opus", "sonnet", "haiku", "fable", "best", "default", "opusplan"
            }
        elif provider == "agy":
            valid = low.startswith(("gemini-", "gpt-")) or low.startswith("claude-")
    if valid:
        try:
            valid = bool(bridge.set_model(name))
        except Exception:
            valid = False
    if valid:
        return True
    # Geri alma: sinyaller bloklanır, yoksa bu geri yazma yeniden tetiklerdi.
    current = str(getattr(bridge, "selected_model", "") or "")
    try:
        combo.blockSignals(True)
        combo.setCurrentText(current)
        combo.setToolTip(
            f"'{name}' {provider or 'etkin'} sağlayıcısının modeli değil; "
            f"seçim '{current}' olarak kaldı."
        )
    except (AttributeError, RuntimeError):
        pass
    finally:
        try:
            combo.blockSignals(False)
        except (AttributeError, RuntimeError):
            pass
    return False


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


# --------------------------------------------------------------- emoji yedeği

#: Emoji/simge glifleri için font zinciri (Faz 9).
#: Kullanıcının günlüğünde 176 satır `OpenType support missing for
#: "Segoe UI Emoji"/"Segoe UI Symbol"` vardı; renkli emoji ailesi çözülemeyince
#: `🔴` gibi glifler **içi boş kutu** (tofu) olarak çiziliyor — kullanıcının
#: "üst çubukta boş kırmızı kare" dediği şey budur.
EMOJI_FALLBACK_FAMILIES = (
    "Segoe UI Emoji",
    "Segoe UI Symbol",
    "Noto Color Emoji",
    "Apple Color Emoji",
    "DejaVu Sans",
)

#: Emoji yerine kullanılacak metin/monokrom eşlenikler (font hiç yoksa).
EMOJI_TEXT_FALLBACK = {
    "🟢": "●", "🔴": "●", "🟡": "●", "🟠": "●", "⚪": "○", "⚫": "●",
    "✅": "✓", "❌": "✕", "⚠️": "!", "⏰": "⏱", "📘": "▤", "📥": "▼",
    "🎯": "◎", "📑": "▤", "🧠": "◇", "🔌": "▸", "🏢": "▣", "🌐": "◍",
}


_EMOJI_AVAILABLE = None


def emoji_font_available(families=EMOJI_FALLBACK_FAMILIES) -> bool:
    """Sistemde kullanılabilir bir emoji ailesi var mı? (sonuç önbelleklenir)"""
    global _EMOJI_AVAILABLE
    if _EMOJI_AVAILABLE is not None and families is EMOJI_FALLBACK_FAMILIES:
        return _EMOJI_AVAILABLE
    try:
        from PySide6.QtGui import QFontDatabase

        installed = {f.lower() for f in QFontDatabase.families()}
    except Exception:
        return False
    found = any(str(f).lower() in installed for f in families)
    if families is EMOJI_FALLBACK_FAMILIES:
        _EMOJI_AVAILABLE = found
    return found


def apply_emoji_font_fallback(app) -> bool:
    """Uygulama font zincirine emoji yedeklerini ekler.

    `QFont.setFamilies([...])` Qt'ye glif bulunamadığında sırayla denemesi
    gereken aileleri söyler; tek `setFamily` ile bu zincir kurulmuyor ve emoji
    tofu kutusuna düşüyordu. Emoji ailesi hiç yoksa `False` döner — çağıran
    taraf `emoji_or_text()` ile metin eşleniğine düşebilir.
    """
    try:
        from PySide6.QtGui import QFont

        base = app.font()
        primary = base.family() or "Segoe UI"
        families = [primary] + [f for f in EMOJI_FALLBACK_FAMILIES if f != primary]
        font = QFont(base)
        font.setFamilies(families)
        app.setFont(font)
    except Exception:
        return False
    return emoji_font_available()


def emoji_or_text(emoji: str, fallback: Optional[str] = None) -> str:
    """Emoji fontu yoksa monokrom/metin eşleniğini döndürür.

    Durum göstergeleri emojiye TEK BAŞINA güvenmemeli: rozetlerde emoji yanında
    her zaman metin ve renk bulunur, böylece glif çizilemese de durum okunur.
    """
    if emoji_font_available():
        return emoji
    if fallback is not None:
        return fallback
    return EMOJI_TEXT_FALLBACK.get(emoji, "")
