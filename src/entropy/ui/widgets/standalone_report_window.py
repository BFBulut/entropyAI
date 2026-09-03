"""Standalone Window for Research Reports & Memory Dossiers."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QPushButton

from entropy.core.config import config
from entropy.ui.themes.cyber_theme import STYLESHEET
from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

class StandaloneReportWindow(QMainWindow):
    """A dedicated, resizable window to read, manage, and delete reports and dossiers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLESHEET)
        self.setWindowTitle("Entropy AI - Araştırma ve Bellek Arşivi")
        self.resize(880, 620)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header bar
        header = QHBoxLayout()
        hdr_lbl = QLabel("<b style='color:#00F0FF; font-size:14px;'>📚 ARAŞTIRMA VE BELLEK ARŞİVİ</b>")
        header.addWidget(hdr_lbl)
        header.addStretch()

        btn_close = QPushButton("Kapat")
        btn_close.setFixedHeight(24)
        btn_close.setStyleSheet("background-color:#1A263C; color:#F0F6FC; border:1px solid #1F2B42; padding:2px 14px; border-radius:4px;")
        btn_close.clicked.connect(self.hide)
        header.addWidget(btn_close)

        layout.addLayout(header)

        # Embedded ReportsViewerWidget
        self.viewer = ReportsViewerWidget(self)
        layout.addWidget(self.viewer)

    def open_report_file(self, file_path: str):
        """Open window and load a specific report file."""
        self.viewer.refresh_reports()
        self.viewer.open_report_by_path_or_id(file_path)
        self.show()
        self.raise_()
        self.activateWindow()
