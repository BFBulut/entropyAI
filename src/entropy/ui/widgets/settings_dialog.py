"""Ayarlar diyaloğu — tema, yoğunluk ve karar eşikleri (Faz 12-D.2).

Denetim D12-08: `LIGHT_TOKENS` ve `density: comfortable` Faz 11-E'de yazıldı
ama üründe ulaşılabilir değildi (`themes_reachable = 1`). D12-07: kullanıcının
elle ayarladığı hiçbir yerleşim değeri kalıcı değildi. Ayrıca 11-C/11-D'de
eklenen üç karar ayarının (`amplification_lock`, `board_auto_dispatch`,
`brain_confidence_threshold`) arayüzde karşılığı yoktu — yalnızca slash
komutu ve palet anahtarı vardı.

Tasarım kuralı: **küçük diyalog, tek ekran, kaydırma yok.** Alanlar dört
kümede toplanır (görünüm · beyin · pano · oturum bütçesi). Yerel stil
sayfası yazılmaz; her denetim `role`/`variant` özelliğiyle sınıflandırılır.

Sözleşme guard'ı: `config` alanları Faz 12-B tarafından eklenir. Alan yoksa
ilgili satır **hiç kurulmaz** (diyalog yine açılır).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from entropy.ui.design import TOKENS, apply_design_system
from entropy.ui.design.prefs import (
    DENSITIES,
    THEMES,
    set_ui_density,
    set_ui_theme,
    ui_density,
    ui_theme,
)

__all__ = ["SettingsDialog", "open_settings_dialog"]

_THEME_LABELS = {"dark": "Koyu", "light": "Açık"}
_DENSITY_LABELS = {"compact": "Yoğun", "comfortable": "Rahat"}


def _has(obj: Any, name: str) -> bool:
    return getattr(obj, name, None) is not None


class SettingsDialog(QDialog):
    """Tek ekranlık ayar diyaloğu; komut paletindeki "Ayarlar" eylemi açar."""

    def __init__(self, parent: Optional[QWidget] = None, config: Any = None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.setObjectName("settingsDialog")
        self.setModal(True)
        if config is None:
            from entropy.core.config import config as _config

            config = _config
        self._config = config

        root = QVBoxLayout(self)
        root.setContentsMargins(*([TOKENS["space"]["4"]] * 4))
        root.setSpacing(TOKENS["space"]["3"])

        form = QFormLayout()
        form.setSpacing(TOKENS["space"]["2"])
        root.addLayout(form)

        # --- Görünüm -------------------------------------------------------
        self.theme_combo = QComboBox()
        self.theme_combo.setAccessibleName("Tema")
        for key in THEMES:
            self.theme_combo.addItem(_THEME_LABELS.get(key, key), key)
        self.theme_combo.setCurrentIndex(max(0, list(THEMES).index(ui_theme())))
        form.addRow(QLabel("Tema"), self.theme_combo)

        self.density_combo = QComboBox()
        self.density_combo.setAccessibleName("Yoğunluk")
        for key in DENSITIES:
            self.density_combo.addItem(_DENSITY_LABELS.get(key, key), key)
        self.density_combo.setCurrentIndex(max(0, list(DENSITIES).index(ui_density())))
        form.addRow(QLabel("Yoğunluk"), self.density_combo)

        # --- Beyin ---------------------------------------------------------
        self.confidence_slider: Optional[QSlider] = None
        if _has(config, "brain_confidence_threshold"):
            self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
            self.confidence_slider.setAccessibleName("Beyin güven eşiği")
            self.confidence_slider.setRange(20, 60)  # 0,20 – 0,60
            self.confidence_slider.setSingleStep(1)
            self.confidence_slider.setPageStep(5)
            self.confidence_slider.setValue(
                int(round(float(config.brain_confidence_threshold) * 100))
            )
            self.confidence_value = QLabel()
            self.confidence_value.setProperty("role", "label")
            self.confidence_slider.valueChanged.connect(self._on_confidence_changed)
            self._on_confidence_changed(self.confidence_slider.value())
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(TOKENS["space"]["1"])
            row_layout.addWidget(self.confidence_slider)
            row_layout.addWidget(self.confidence_value)
            form.addRow(QLabel("Beyin güven eşiği"), row)

        self.lock_check: Optional[QCheckBox] = None
        if _has(config, "amplification_lock"):
            self.lock_check = QCheckBox("Öz-amplifikasyon kilidi açık")
            self.lock_check.setAccessibleName("Öz-amplifikasyon kilidi")
            self.lock_check.setToolTip(
                "Rapor hafızaya girmeden önce yenilik kotasından geçer;"
                " düşük yenilikli zamanlanmış görev kapatılır."
            )
            self.lock_check.setChecked(bool(config.amplification_lock))
            form.addRow(QLabel("Beyin"), self.lock_check)

        # --- Pano ----------------------------------------------------------
        self.auto_dispatch_check: Optional[QCheckBox] = None
        if _has(config, "board_auto_dispatch"):
            self.auto_dispatch_check = QCheckBox("Kartları kendiliğinden dağıt")
            self.auto_dispatch_check.setAccessibleName("Pano otomatik dağıtım")
            self.auto_dispatch_check.setChecked(bool(config.board_auto_dispatch))
            form.addRow(QLabel("Pano"), self.auto_dispatch_check)

        # --- Oturum bütçesi ------------------------------------------------
        self.max_cards_spin: Optional[QSpinBox] = None
        if _has(config, "agent_session_max_cards"):
            self.max_cards_spin = QSpinBox()
            self.max_cards_spin.setAccessibleName("Oturum başına kart")
            self.max_cards_spin.setRange(1, 50)
            self.max_cards_spin.setValue(int(config.agent_session_max_cards))
            form.addRow(QLabel("Oturum başına kart"), self.max_cards_spin)

        self.max_tokens_spin: Optional[QSpinBox] = None
        if _has(config, "agent_session_max_tokens"):
            self.max_tokens_spin = QSpinBox()
            self.max_tokens_spin.setAccessibleName("Oturum başına token")
            self.max_tokens_spin.setRange(1000, 1_000_000)
            self.max_tokens_spin.setSingleStep(1000)
            self.max_tokens_spin.setValue(int(config.agent_session_max_tokens))
            form.addRow(QLabel("Oturum başına token"), self.max_tokens_spin)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_btn is not None:
            save_btn.setText("Kaydet")
            save_btn.setAccessibleName("Ayarları kaydet")
            save_btn.setProperty("variant", "primary")
        cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText("Vazgeç")
            cancel_btn.setAccessibleName("Vazgeç")
        self.buttons.accepted.connect(self.apply_and_accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    # ------------------------------------------------------------------ #
    @Slot(int)
    def _on_confidence_changed(self, value: int) -> None:
        label = getattr(self, "confidence_value", None)
        if label is not None:
            label.setText(f"{value / 100:.2f}".replace(".", ","))

    def values(self) -> Dict[str, Any]:
        """Diyalogdaki güncel değerler (test bunu okur)."""
        data: Dict[str, Any] = {
            "ui_theme": self.theme_combo.currentData(),
            "ui_density": self.density_combo.currentData(),
        }
        if self.confidence_slider is not None:
            data["brain_confidence_threshold"] = self.confidence_slider.value() / 100.0
        if self.lock_check is not None:
            data["amplification_lock"] = self.lock_check.isChecked()
        if self.auto_dispatch_check is not None:
            data["board_auto_dispatch"] = self.auto_dispatch_check.isChecked()
        if self.max_cards_spin is not None:
            data["agent_session_max_cards"] = self.max_cards_spin.value()
        if self.max_tokens_spin is not None:
            data["agent_session_max_tokens"] = self.max_tokens_spin.value()
        return data

    @Slot()
    def apply_and_accept(self) -> None:
        self.apply()
        self.accept()

    def apply(self) -> Dict[str, Any]:
        """Değerleri kalıcılaştırır ve tasarım sistemini yeniden uygular."""
        data = self.values()
        set_ui_theme(str(data["ui_theme"]))
        set_ui_density(str(data["ui_density"]))
        for key, value in data.items():
            if key.startswith("ui_"):
                continue
            if getattr(self._config, key, None) is not None:
                try:
                    setattr(self._config, key, value)
                except Exception:
                    pass
        saver = getattr(self._config, "save_settings", None)
        if callable(saver):
            try:
                saver()
            except Exception:
                pass
        reapply_design(str(data["ui_theme"]), str(data["ui_density"]))
        return data


def reapply_design(theme: str, density: str) -> bool:
    """Uygulama düzeyindeki QSS'i yeni tema/yoğunlukla yeniden uygular."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return False
    apply_design_system(app, theme=theme, density=density)
    return True


def open_settings_dialog(parent: Optional[QWidget] = None, config: Any = None) -> SettingsDialog:
    """Komut paleti "Ayarlar" eyleminin çağırdığı tek giriş noktası."""
    dialog = SettingsDialog(parent=parent, config=config)
    dialog.exec()
    return dialog
