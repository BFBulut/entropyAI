"""
Sağlayıcı durum rozeti (Faz 5.5 / 5.4 arayüz yüzü).

Üst çubukta iki sağlayıcı (agy, claude) için giriş / kota / oturum penceresi
tek satırda görünür. Giriş yoksa rozet kırmızıya döner ve ipucu
`/login <provider>` der — kullanıcı "neden cevap gelmiyor" diye köprü
günlüklerine bakmak zorunda kalmasın.

Veri kaynağı: `bus.provider_status_updated(provider, dict)` (Faz 5.4, agy
ajanı). Sözlük alanları: `logged_in, plan, quota_hint, session_window,
last_error` (+ `account_hint`). Sinyal ya da alanlar yoksa rozet "bilinmiyor"
gösterir; hiçbir alan zorunlu değildir.

İş parçacığı notu: prob işçi iş parçacığında koşar ama sinyali
`bus.invoke_on_main` ile ana iş parçacığına taşır (bkz. `core/identity.py`);
buradaki slotlar bu yüzden doğrudan Qt'ye dokunabilir.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.ui_polish import LABEL_PX
# Gömülü HTML gövdelerinin renk kaynağı (Faz 12-D.2): düz onaltılık yerine
# `TOKENS`/`TOKENS["viz"]` köprüsü. Bkz. `entropy.ui.design.embedded`.
from entropy.ui.design.embedded import live_palette as _live_palette

# Faz 12-F: canli palet — tema degisince gomulu govdeler de doner.
_P = _live_palette()

# Rozette gösterilecek sağlayıcılar ve kısa adları.
PROVIDERS = (("agy", "AGY"), ("claude", "Claude"))

COLOR_OK = f"{_P["ok"]}"
COLOR_WARN = f"{_P["warn"]}"
COLOR_BAD = f"{_P["danger"]}"
COLOR_UNKNOWN = f"{_P["text_muted"]}"


def status_color(status: Optional[Dict[str, Any]]) -> str:
    """Rozet rengi: girişsiz kırmızı, hatalı sarı, girişli yeşil, bilinmeyen gri."""
    if not status:
        return COLOR_UNKNOWN
    if not status.get("logged_in"):
        return COLOR_BAD
    if status.get("last_error"):
        return COLOR_WARN
    return COLOR_OK


#: Faz 9 - kompakt durum imleri. Eski rozet uzun bir cumle basiyordu
#: ("AGY · antigravity-cli · belirtec ... (suresi doldu (yenilenecek))"),
#: ust cubugun yarisini yiyor ve akan yerlesimde ikinci satira dokuluyordu.
#: Ayrinti artik ipucunda; rozet yalnizca im + kisa plan tasir.
MARK_OK = "✓"
MARK_WARN = "⟳"
MARK_BAD = "✕"


def status_mark(status: Optional[Dict[str, Any]]) -> str:
    """Rozet imi: girisli ✓, hatali/yenilenecek ⟳, girissiz ✕, bilinmeyen ?."""
    if not status:
        return "?"
    if not status.get("logged_in"):
        return MARK_BAD
    if status.get("last_error"):
        return MARK_WARN
    return MARK_OK


#: Rozet basina hedef azami genislik (px). Iki rozet + bosluk <= 160 px.
MAX_BADGE_WIDTH = 76

#: Zengin metin etiketindeki çerçeve + dolgunun yatay maliyeti
#: (`padding:2px 8px` + 1 px kenarlık, iki yan) — asgari genişlik hesabı için.
BADGE_CHROME_PX = 2 * (8 + 1) + 2


def badge_width_for(widget, text: str) -> int:
    """Rozetin metnini KIRPMADAN gösterebileceği genişlik (px).

    Faz 13-A2 madde 5'in kök nedeni: rozet `setMaximumWidth(76)` ile sabit
    tavana vuruyordu ve "Claude ✓ max" yazısı üst çubukta "Claude ✓ ma…"
    diye kırpılıyordu. Genişlik artık **yazı tipi ölçüsünden** gelir; 76 px
    yalnızca bir TABAN, tavan değil.
    """
    metrics = widget.fontMetrics()
    return int(metrics.horizontalAdvance(text)) + BADGE_CHROME_PX

#: Kisa plan etiketinde gosterilecek azami karakter.
PLAN_CHARS = 5


def status_text(provider: str, label: str, status: Optional[Dict[str, Any]]) -> str:
    """Rozetin kompakt metni: `AGY ✓`, `Claude ✓ max`, `AGY ✕`."""
    mark = status_mark(status)
    bits: List[str] = [f"{label} {mark}"]
    if status and status.get("logged_in"):
        plan = str(status.get("plan") or "").strip()
        if plan and plan.lower() not in ("bilinmiyor", "unknown", "?"):
            bits.append(plan[:PLAN_CHARS])
    return " ".join(bits)


def status_tooltip(provider: str, status: Optional[Dict[str, Any]]) -> str:
    """
    Rozet ipucu. Giriş yoksa ilk satır `/login <provider>` — kullanıcının
    yapması gereken tek şey budur ve ipucunun en üstünde durmalıdır.
    """
    lines: List[str] = []
    if not status or not status.get("logged_in"):
        lines.append(f"Giriş yok → sohbete `/login {provider}` yazın.")
    if status:
        if status.get("account_hint"):
            lines.append(f"Hesap: {status['account_hint']}")
        if status.get("plan"):
            lines.append(f"Plan: {status['plan']}")
        if status.get("quota_hint"):
            lines.append(f"Kota: {status['quota_hint']}")
        if status.get("session_window"):
            lines.append(f"Oturum penceresi: {status['session_window']}")
        if status.get("last_error"):
            lines.append(f"Son hata: {status['last_error']}")
        if status.get("checked_at"):
            lines.append(f"Ölçüm: {status['checked_at']}")
    else:
        lines.append("Sağlayıcı durumu henüz ölçülmedi.")
    return "\n".join(lines)


class ProviderStatusBadge(QFrame):
    """Üst çubuktaki iki sağlayıcılı durum rozeti."""

    login_requested = Signal(str)  # tıklanan sağlayıcı (çağıran /login yazar)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("providerBadge")
        self.setProperty("role", "panel")
        self.statuses: Dict[str, Dict[str, Any]] = {}
        #: Faz 12-D.2 (denetim D12-06): üst çubukta AYNI ANDA tek sağlayıcı
        #: etiketi görünür. İkinci sağlayıcının durumu kaybolmaz — birincinin
        #: ipucunda ve komut paletinde durur. Boşsa (eski davranış) ikisi de
        #: gösterilir; testler bu yolu kullanmayı sürdürebilir.
        self.primary: str = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.labels: Dict[str, QLabel] = {}
        for provider, label in PROVIDERS:
            widget = QLabel("")
            widget.setTextFormat(Qt.TextFormat.RichText)
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
            self.labels[provider] = widget
            layout.addWidget(widget)
        self._signal = getattr(bus, "provider_status_updated", None)
        if self._signal is not None:
            try:
                self._signal.connect(self._on_status)
            except (TypeError, RuntimeError):
                self._signal = None
        self.refresh()

    def set_status(self, provider: str, status: Dict[str, Any]) -> None:
        self.statuses[str(provider)] = dict(status or {})
        self.refresh()

    @Slot(str, dict)
    def _on_status(self, provider: str, status: dict) -> None:
        self.set_status(provider, status)

    def refresh(self) -> None:
        for provider, label in PROVIDERS:
            status = self.statuses.get(provider)
            color = status_color(status)
            text = status_text(provider, label, status)
            widget = self.labels[provider]
            # Bos metin geride yalnizca renkli bir cerceve birakiyordu ("bos
            # kirmizi kare" ikincil adayi); metin yoksa etiket gizlenir.
            hidden_by_primary = bool(self.primary) and provider != self.primary
            widget.setVisible(bool(text.strip()) and not hidden_by_primary)
            # Metin kırpılmasın: asgari genişlik yazı tipinden hesaplanır,
            # tavan da en az o kadar olur (76 px yalnızca taban).
            needed = badge_width_for(widget, text)
            widget.setMinimumWidth(needed)
            widget.setMaximumWidth(max(MAX_BADGE_WIDTH, needed))
            widget.setText(
                f"<span style='color:{color}; border:1px solid {color};"
                f" border-radius:8px; padding:2px 8px; font-size:{LABEL_PX}px;"
                f" font-weight:600;'>{text}</span>"
            )
            widget.setToolTip(self._tooltip_for(provider))

    def set_primary(self, provider: str) -> None:
        """Üst çubukta gösterilecek sağlayıcıyı seçer (diğeri ipucuna iner)."""
        self.primary = str(provider or "")
        self.refresh()

    def _tooltip_for(self, provider: str) -> str:
        """Birincil rozetin ipucu ikinci sağlayıcının durumunu da taşır."""
        parts = [status_tooltip(provider, self.statuses.get(provider))]
        if self.primary and provider == self.primary:
            for other, label in PROVIDERS:
                if other == provider:
                    continue
                parts.append(status_tooltip(other, self.statuses.get(other)))
        return "\n".join(p for p in parts if p)

    def mousePressEvent(self, event):  # noqa: N802
        # Rozete tıklamak, giriş yapılmamış ilk sağlayıcı için /login önerir.
        for provider, _label in PROVIDERS:
            status = self.statuses.get(provider)
            if not status or not status.get("logged_in"):
                self.login_requested.emit(provider)
                break
        super().mousePressEvent(event)

    def closeEvent(self, event):  # noqa: N802
        # Faz 8: tekrarli kapanislarda ayni sinyali yeniden cozmek
        # libpyside'in "Failed to disconnect" uyarisini basiyordu.
        if not getattr(self, "_bus_connected", True):
            super().closeEvent(event)
            return
        self._bus_connected = False
        if self._signal is not None:
            try:
                self._signal.disconnect(self._on_status)
            except (TypeError, RuntimeError):
                pass
        super().closeEvent(event)
