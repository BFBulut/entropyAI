"""Research Reports Viewer for Zen Mode."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QSplitter, QTextBrowser, QVBoxLayout
)

from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.ui.themes.cyber_theme import CYBER_THEME

class ReportsViewerWidget(QFrame):
    """Browses and displays agent-generated research reports and dossiers."""

    def __init__(self, parent=None, vault_manager: ObsidianVaultManager = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.vault_manager = vault_manager or ObsidianVaultManager()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header
        title_label = QLabel("<b>📚 RESEARCH & MEMORY DOSSIERS</b>")
        title_label.setStyleSheet(f"color: {CYBER_THEME['accent_cyan']}; font-size: 13px;")
        self.layout.addWidget(title_label)

        # Splitter between Report List and Report Viewer
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left list
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(200)
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
            }}
        """)
        self.splitter.addWidget(self.content_browser)

        self.layout.addWidget(self.splitter)
        self.refresh_reports()

    def refresh_reports(self):
        """Reload list of reports from Obsidian Vault."""
        self.list_widget.clear()
        reports = self.vault_manager.list_reports()

        if not reports:
            # Add default welcome/architecture report if none exists
            default_path = self.vault_manager.save_research_report(
                title="Agentic OS Overview",
                content=(
                    "# Entropy AI Agentic Operating System\n\n"
                    "Welcome to Entropy AI. This system runs on-device using Antigravity CLI.\n\n"
                    "## Key Capabilities\n"
                    "- Tri-Modal UI (Zen, Floating, Chat)\n"
                    "- 12-Layer Mem0 + Supabase Cognitive Memory\n"
                    "- Obsidian Markdown Vault Integration\n"
                    "- Dynamic Pydantic AI Self-Tooling\n"
                ),
                tags=["overview", "architecture"]
            )
            reports = self.vault_manager.list_reports()

        for rep in reports:
            item = QListWidgetItem(rep["title"])
            item.setData(Qt.ItemDataRole.UserRole, rep["path"])
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self._on_item_clicked(self.list_widget.item(0))

    def _on_item_clicked(self, item: QListWidgetItem):
        path_str = item.data(Qt.ItemDataRole.UserRole)
        p = Path(path_str)
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="replace")
            self.content_browser.setMarkdown(content)
