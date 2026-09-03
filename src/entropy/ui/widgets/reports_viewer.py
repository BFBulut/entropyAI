"""Research Reports & Memory Dossiers Viewer for Zen Mode."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSplitter, QTextBrowser, QVBoxLayout
)

from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.ui.themes.cyber_theme import CYBER_THEME

class ReportsViewerWidget(QFrame):
    """Browses and displays agent-generated research reports and Obsidian dossiers."""

    def __init__(self, parent=None, vault_manager: ObsidianVaultManager = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.vault_manager = vault_manager or ObsidianVaultManager()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title_label = QLabel("<b style='color:#00F0FF; font-size:13px;'>📚 ARAŞTIRMA VE BELLEK DOSYALARI</b>")
        header.addWidget(title_label)

        header.addStretch()

        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setFixedHeight(24)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 4px;
                padding: 2px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #080B10;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_reports)
        header.addWidget(self.refresh_btn)

        self.layout.addLayout(header)

        # Splitter between Report List and Report Content
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left list
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(180)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {CYBER_THEME['bg_terminal']};
                border: 1px solid {CYBER_THEME['border']};
                border-radius: 4px;
                color: {CYBER_THEME['text_primary']};
            }}
            QListWidget::item:selected {{
                background-color: #1A263C;
                color: {CYBER_THEME['accent_cyan']};
            }}
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.splitter.addWidget(self.list_widget)

        # Right text browser
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        self.content_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {CYBER_THEME['bg_surface']};
                border: 1px solid {CYBER_THEME['border']};
                border-radius: 4px;
                color: {CYBER_THEME['text_primary']};
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }}
        """)
        self.splitter.addWidget(self.content_browser)

        self.layout.addWidget(self.splitter)
        self.refresh_reports()

    def refresh_reports(self):
        """Reload list of reports from Obsidian Vault."""
        self.list_widget.clear()
        reports = self.vault_manager.list_reports()

        # Also add MEMORY.md to list
        if self.vault_manager.memory_file.exists():
            mem_item = QListWidgetItem("📌 Global Hafıza (MEMORY.md)")
            mem_item.setData(Qt.ItemDataRole.UserRole, str(self.vault_manager.memory_file))
            self.list_widget.addItem(mem_item)

        for rep in reports:
            item = QListWidgetItem(f"📄 {rep['title']}")
            item.setData(Qt.ItemDataRole.UserRole, rep["path"])
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self._on_item_clicked(self.list_widget.item(0))
        else:
            self.content_browser.setMarkdown(
                "### 📚 Araştırma ve Hafıza Arşivi\n\n"
                "Henüz kaydedilmiş bir araştırma raporu bulunmuyor.\n\n"
                "Zen mod komut satırından yapay zekaya *'... konusunu derinlemesine araştır ve rapor hazırla'* "
                "talimatı verdiğinizde, üretilen tüm teknik raporlar otomatik olarak buraya ve Obsidian kasanıza kaydedilecektir."
            )

    def _on_item_clicked(self, item: QListWidgetItem):
        path_str = item.data(Qt.ItemDataRole.UserRole)
        p = Path(path_str)
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="replace")
            self.content_browser.setMarkdown(content)
