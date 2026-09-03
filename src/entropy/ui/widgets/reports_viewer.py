"""Research Reports & Memory Dossiers Viewer for Zen Mode."""

from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSplitter, QTextBrowser, QVBoxLayout
)

from entropy.core.config import config
from entropy.core.event_bus import bus
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

        open_file_btn = QPushButton("📂 Dosya Aç...")
        open_file_btn.setFixedHeight(24)
        open_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00FF9D;
                border: 1px solid #00FF9D;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00FF9D;
                color: #080B10;
            }
        """)
        open_file_btn.clicked.connect(self._open_custom_file)
        header.addWidget(open_file_btn)

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
        self.list_widget.setFixedWidth(190)
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

        # Auto-refresh on signals
        bus.report_created.connect(self._on_report_created)
        bus.agent_turn_completed.connect(lambda _: self.refresh_reports())

        self.refresh_reports()

    def _open_custom_file(self):
        """Allow user to browse and view any markdown file from disk."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Rapor / Markdown Dosyası Seç",
            str(config.default_project_path),
            "Markdown Dosyaları (*.md *.markdown);;Tüm Dosyalar (*.*)"
        )
        if filename:
            p = Path(filename)
            item = QListWidgetItem(f"📄 {p.name}")
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self.list_widget.insertItem(0, item)
            self.list_widget.setCurrentItem(item)
            self._on_item_clicked(item)

    @Slot(str)
    def _on_report_created(self, report_path: str):
        """Immediately display a newly generated report."""
        self.refresh_reports()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == report_path:
                self.list_widget.setCurrentItem(item)
                self._on_item_clicked(item)
                break

    def refresh_reports(self):
        """Reload list of reports from Obsidian Vault and project directories."""
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

        # Also look in project reports/ and docs/
        for subfolder in ["reports", "docs", ".entropy/reports"]:
            p_folder = config.default_project_path / subfolder
            if p_folder.exists():
                for f in sorted(p_folder.glob("*.md")):
                    item = QListWidgetItem(f"📑 {f.stem.replace('_', ' ')}")
                    item.setData(Qt.ItemDataRole.UserRole, str(f))
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
