"""Efor (düşünme çabası) seçici — Faz 6.

Köprü sözleşmesi (agy tarafında yazıldı):
    bridge.effort_levels() -> list[str]
    bridge.selected_effort -> str
    bridge.set_effort(level) -> None   (isteğe bağlı; varsa yapılandırmaya yazar)

Köprüde bu sözleşme yoksa kutu HİÇ oluşturulmaz (üst çubukta boş bir kutu
görünmesin). Sinyal alıcısı lambda değil, QObject metodudur.
"""

from typing import List, Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QComboBox, QWidget

EFFORT_COMBO_STYLE = """
    QComboBox {
        background-color: #0E1420;
        color: #FFB300;
        border: 1px solid #1F2B42;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: bold;
    }
    QComboBox:hover { border-color: #FFB300; }
    QComboBox::drop-down { border: none; width: 16px; }
    QComboBox QAbstractItemView {
        background-color: #0E1420;
        color: #F0F6FC;
        border: 1px solid #FFB300;
        selection-background-color: #1F2B42;
        selection-color: #FFB300;
    }
"""


def bridge_supports_effort(bridge) -> bool:
    """Köprü efor sözleşmesini uyguluyor mu?"""
    getter = getattr(bridge, "effort_levels", None)
    if not callable(getter):
        return False
    try:
        levels = list(getter() or [])
    except Exception:
        return False
    return bool(levels)


class EffortSelector(QComboBox):
    """Model kutusunun yanındaki küçük 'Efor' kutusu."""

    def __init__(self, bridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.bridge = bridge
        self.setObjectName("effortCombo")
        self.setToolTip("Modelin düşünme/çaba düzeyi. Seçim kalıcıdır.")
        self.setStyleSheet(EFFORT_COMBO_STYLE)
        self.setMaximumWidth(110)
        self.setFixedHeight(24)

        levels: List[str] = []
        try:
            levels = [str(x) for x in (bridge.effort_levels() or [])]
        except Exception:
            levels = []
        self.addItems(levels)

        current = str(getattr(bridge, "selected_effort", "") or "")
        if current in levels:
            self.setCurrentIndex(levels.index(current))
        self.currentTextChanged.connect(self._on_effort_changed)

    @Slot(str)
    def _on_effort_changed(self, level: str):
        level = (level or "").strip()
        if not level:
            return
        setter = getattr(self.bridge, "set_effort", None)
        if callable(setter):
            try:
                setter(level)
                return
            except Exception:
                pass
        # Köprüde set_effort yoksa alanı doğrudan yaz ve yapılandırmayı kaydet.
        try:
            self.bridge.selected_effort = level
            from entropy.core.config import config
            provider = str(getattr(self.bridge, "provider_name", "agy") or "agy")
            if isinstance(getattr(config, "provider_effort", None), dict):
                config.provider_effort[provider] = level
                config.save_settings()
        except Exception:
            pass


def install_effort_selector(layout, bridge, parent: Optional[QWidget] = None) -> Optional[EffortSelector]:
    """Efor kutusunu (destekleniyorsa) verilen düzene ekler; yoksa None döner."""
    if not bridge_supports_effort(bridge):
        return None
    combo = EffortSelector(bridge, parent)
    layout.addWidget(combo)
    return combo
