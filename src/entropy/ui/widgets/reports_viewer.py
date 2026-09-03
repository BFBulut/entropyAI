"""Research Reports & Memory Dossiers Viewer for Zen Mode."""

from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget
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

        # Right container: RAG Status Bar + Markdown Text Browser
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # RAG / Memory Status Banner
        self.rag_status_bar = QFrame()
        self.rag_status_bar.setStyleSheet("""
            QFrame {
                background-color: #141C2C;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)
        bar_layout = QHBoxLayout(self.rag_status_bar)
        bar_layout.setContentsMargins(4, 2, 4, 2)

        self.rag_status_lbl = QLabel("<span style='color:#00FF9D; font-size:11px;'>● RAG İndeksinde Aktif</span> | <span style='color:#00F0FF; font-size:11px;'>🧠 Bilişsel Bellek: Semantik Düğüm Bağlı</span>")
        bar_layout.addWidget(self.rag_status_lbl)
        bar_layout.addStretch()

        distill_btn = QPushButton("⚡ Hafızaya Sentezle")
        distill_btn.setFixedHeight(22)
        distill_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A263C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 3px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #080B10;
            }
        """)
        distill_btn.clicked.connect(self._distill_current_report)
        bar_layout.addWidget(distill_btn)

        right_layout.addWidget(self.rag_status_bar)

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
        right_layout.addWidget(self.content_browser)
        self.splitter.addWidget(right_container)

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

    def _distill_current_report(self):
        """Distill the currently selected report into Cognitive Memory and re-index in RAG."""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
        path_str = current_item.data(Qt.ItemDataRole.UserRole)
        p = Path(path_str)
        if not p.exists():
            return
        content = p.read_text(encoding="utf-8", errors="replace")
        
        # 1. Store in Cognitive Memory
        from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
        cog = CognitiveMemorySystem()
        paragraphs = [para.strip() for para in content.split("\n\n") if para.strip() and not para.startswith("#")]
        summary = paragraphs[0][:250] if paragraphs else content[:200]
        cog.store_node(
            category="semantic",
            content=f"Araştırma Özeti [{p.stem}]: {summary}",
            importance=0.85,
            metadata={"source": "manual_distill", "path": str(p)}
        )

        # 2. Re-index in Project RAG
        from entropy.memory.rag.project_indexer import ProjectIndexer
        indexer = ProjectIndexer(config.default_project_path)
        indexer.scan_and_index(max_files=150)

        bus.terminal_output_received.emit(f"\n[🧠 Hafıza & RAG] '{p.name}' raporu başarıyla bilişsel belleğe sentezlendi ve RAG indeksine eklendi.\n")
        bus.report_created.emit(str(p))

    def open_report_by_path_or_id(self, path_or_id: str) -> bool:
        """Find and select a report by path or partial title/id."""
        clean = path_or_id.replace("o-", "").lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item_path = str(item.data(Qt.ItemDataRole.UserRole)).lower()
            if clean in item_path or Path(clean).stem.lower() in item_path:
                self.list_widget.setCurrentItem(item)
                self._on_item_clicked(item)
                return True
        return False

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
