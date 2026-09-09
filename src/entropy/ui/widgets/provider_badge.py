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

# Rozette gösterilecek sağlayıcılar ve kısa adları.
PROVIDERS = (("agy", "AGY"), ("claude", "Claude"))

COLOR_OK = "#00FF9D"
COLOR_WARN = "#E3B341"
COLOR_BAD = "#FF4D4D"
COLOR_UNKNOWN = "#8B949E"


def status_color(status: Optional[Dict[str, Any]]) -> str:
    """Rozet rengi: girişsiz kırmızı, hatalı sarı, girişli yeşil, bilinmeyen gri."""
    if not status:
        return COLOR_UNKNOWN
    if not status.get("logged_in"):
        return COLOR_BAD
    if status.get("last_error"):
        return COLOR_WARN
    return COLOR_OK


def status_text(provider: str, label: str, status: Optional[Dict[str, Any]]) -> str:
    """Rozetin tek satırlık metni: `AGY · Pro · 3 sa`."""
    if not status:
        return f"{label} · ?"
    if not status.get("logged_in"):
        return f"{label} · giriş yok"
    bits: List[str] = [label]
    plan = str(status.get("plan") or "").strip()
    if plan:
        bits.append(plan)
    window = str(status.get("session_window") or "").strip()
    if window:
        bits.append(window)
    quota = str(status.get("quota_hint") or "").strip()
    if quota and quota.lower() not in ("bilinmiyor", "unknown", "?"):
        bits.append(quota)
    return " · ".join(bits)


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
        self.setStyleSheet(
            "QFrame#providerBadge { background:transparent; border:none; }"
            " QLabel { background:transparent; border:none; }"
        )
        self.statuses: Dict[str, Dict[str, Any]] = {}
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
            widget.setText(
                f"<span style='color:{color}; border:1px solid {color};"
                f" border-radius:8px; padding:2px 8px; font-size:{LABEL_PX}px;"
                f" font-weight:600;'>{text}</span>"
            )
            widget.setToolTip(status_tooltip(provider, status))

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
