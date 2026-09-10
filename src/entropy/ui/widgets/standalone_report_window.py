"""Standalone Window for Research Reports & Memory Dossiers."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QPushButton

from entropy.core.config import config
from entropy.ui.widgets.reports_viewer import ReportsViewerWidget
# Gömülü HTML gövdelerinin renk kaynağı (Faz 12-D.2): düz onaltılık yerine
# `TOKENS`/`TOKENS["viz"]` köprüsü. Bkz. `entropy.ui.design.embedded`.
from entropy.ui.design.embedded import palette as _embedded_palette

_P = _embedded_palette()

_ACTIVE_STANDALONE_REPORT_WINDOW: Optional["StandaloneReportWindow"] = None


def open_standalone_report_window(file_path: str, parent=None) -> "StandaloneReportWindow":
    """
    Launch or bring to foreground the dedicated standalone report reader.
    Guarantees the window will not drop behind ZenModeWindow on Windows.
    """
    global _ACTIVE_STANDALONE_REPORT_WINDOW
    if _ACTIVE_STANDALONE_REPORT_WINDOW is None:
        _ACTIVE_STANDALONE_REPORT_WINDOW = StandaloneReportWindow(parent=None)
    
    # Ensure window is pinned on top so it never drops behind fullscreen ZenModeWindow
    _ACTIVE_STANDALONE_REPORT_WINDOW.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    _ACTIVE_STANDALONE_REPORT_WINDOW.is_pinned = True
    if hasattr(_ACTIVE_STANDALONE_REPORT_WINDOW, "btn_pin"):
        _ACTIVE_STANDALONE_REPORT_WINDOW._update_pin_style()

    _ACTIVE_STANDALONE_REPORT_WINDOW.open_report_file(file_path)
    _ACTIVE_STANDALONE_REPORT_WINDOW.show()
    _ACTIVE_STANDALONE_REPORT_WINDOW.setWindowState(
        (_ACTIVE_STANDALONE_REPORT_WINDOW.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
    )
    _ACTIVE_STANDALONE_REPORT_WINDOW.raise_()
    _ACTIVE_STANDALONE_REPORT_WINDOW.activateWindow()

    # Multi-stage re-assertion to defeat OS focus-stealing on modal dialog closure
    for delay in [60, 150, 300]:
        QTimer.singleShot(delay, lambda: (
            _ACTIVE_STANDALONE_REPORT_WINDOW.raise_() if _ACTIVE_STANDALONE_REPORT_WINDOW else None,
            _ACTIVE_STANDALONE_REPORT_WINDOW.activateWindow() if _ACTIVE_STANDALONE_REPORT_WINDOW else None
        ))
    return _ACTIVE_STANDALONE_REPORT_WINDOW


class StandaloneReportWindow(QMainWindow):
    """A dedicated, resizable window to read, manage, and delete reports and dossiers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_pinned = True
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        # Faz 11-E adım 2: stil uygulama düzeyinde tek girişten gelir
        # (`ui/manager.py` -> `apply_design_system(app)`).
        self.setWindowTitle("Entropy AI - Araştırma ve Bellek Arşivi")
        self.resize(920, 660)
        self.setMinimumSize(600, 450)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Slim top bar with pin and close buttons
        header = QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 2)
        hdr_lbl = QLabel(f"<span style='color:{_P["accent"]}; font-weight:bold; font-size:13px;'>Bağımsız Rapor ve Bellek Görüntüleyici</span>")
        header.addWidget(hdr_lbl)
        header.addStretch()

        self.btn_pin = QPushButton("Üstte Sabit")
        self.btn_pin.setAccessibleName("Üstte Sabit")
        self.btn_pin.setToolTip("Pencereyi tüm pencerelerin (Zen Modu dahil) üzerinde tut")
        self.btn_pin.clicked.connect(self._toggle_pin)
        self._update_pin_style()
        header.addWidget(self.btn_pin)

        btn_close = QPushButton("Kapat")
        btn_close.setAccessibleName("Kapat")
        btn_close.clicked.connect(self.hide)
        header.addWidget(btn_close)

        layout.addLayout(header)

        # Embedded ReportsViewerWidget
        self.viewer = ReportsViewerWidget(self)
        layout.addWidget(self.viewer)

    def _update_pin_style(self):
        if self.is_pinned:
            self.btn_pin.setText("Üstte Sabit")
            self.btn_pin.setProperty("variant", "primary")
        else:
            self.btn_pin.setText("Üstte Tut")

    def _toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.is_pinned)
        self._update_pin_style()
        self.show()

    def open_report_file(self, file_path: str):
        """Open window and load a specific report file."""
        self.viewer.refresh_reports()
        self.viewer.open_report_by_path_or_id(file_path)
        self.show()
        self.raise_()
        self.activateWindow()
