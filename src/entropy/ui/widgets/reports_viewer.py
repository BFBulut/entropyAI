"""Research Reports & Memory Dossiers Viewer for Zen Mode."""

from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter,
    QTextBrowser, QVBoxLayout, QWidget
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

        # Left Container: Search + Report List
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rapor ara...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #05070A;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 4px 8px;
                color: #F0F6FC;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #00F0FF;
            }
        """)
        self.search_input.textChanged.connect(self._filter_reports)
        left_layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(160)
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
                font-weight: bold;
            }}
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        left_layout.addWidget(self.list_widget)

        # List Action Bar: Explicit "Raporu Oku / Aç" and "Ayrı Ekranda Aç"
        list_action_bar = QHBoxLayout()
        list_action_bar.setSpacing(4)

        self.btn_read_report = QPushButton("📖 Raporu Oku")
        self.btn_read_report.setFixedHeight(26)
        self.btn_read_report.setToolTip("Seçili raporu sağ taraftaki okuma panelinde görüntüle")
        self.btn_read_report.setStyleSheet("""
            QPushButton {
                background-color: #00F0FF;
                color: #080B10;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #00FF9D;
            }
        """)
        self.btn_read_report.clicked.connect(self._read_selected_report)
        list_action_bar.addWidget(self.btn_read_report)

        self.btn_open_standalone = QPushButton("🔍 Ayrı Aç ↗")
        self.btn_open_standalone.setFixedHeight(26)
        self.btn_open_standalone.setToolTip("Raporu tam ekran ayrı pencerede aç")
        self.btn_open_standalone.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                border-color: #00F0FF;
                background-color: #1A263C;
            }
        """)
        self.btn_open_standalone.clicked.connect(self._open_current_standalone)
        list_action_bar.addWidget(self.btn_open_standalone)
        left_layout.addLayout(list_action_bar)

        left_container.setMinimumWidth(160)
        self.splitter.addWidget(left_container)

        # Right container: RAG Status Bar + Markdown Text Browser
        right_container = QWidget()
        right_container.setMinimumWidth(220)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # RAG / Memory Status & Reading Tools Banner
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
        bar_layout.setContentsMargins(6, 2, 6, 2)
        bar_layout.setSpacing(6)

        self.reader_status_lbl = QLabel("<span style='color:#00F0FF; font-weight:bold; font-size:11px;'>📖 Bilişsel Okuyucu</span>")
        bar_layout.addWidget(self.reader_status_lbl)
        bar_layout.addStretch()

        # Zoom Controls with clear typography scaling
        zoom_in_btn = QPushButton("A+")
        zoom_in_btn.setFixedSize(30, 22)
        zoom_in_btn.setToolTip("Yazı Boyutunu Büyüt (A+)")
        zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 3px;
                font-weight: bold;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover { background-color: #00F0FF; color: #080B10; }
        """)
        zoom_in_btn.clicked.connect(self._zoom_in_text)
        bar_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("A-")
        zoom_out_btn.setFixedSize(30, 22)
        zoom_out_btn.setToolTip("Yazı Boyutunu Küçült (A-)")
        zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 3px;
                font-weight: bold;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover { background-color: #00F0FF; color: #080B10; border-color: #00F0FF; }
        """)
        zoom_out_btn.clicked.connect(self._zoom_out_text)
        bar_layout.addWidget(zoom_out_btn)

        copy_btn = QPushButton("📋 Kopyala")
        copy_btn.setFixedHeight(22)
        copy_btn.setToolTip("Rapor Metnini Panoya Kopyala")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #F0F6FC;
                border: 1px solid #1F2B42;
                border-radius: 3px;
                font-size: 10px;
                padding: 1px 6px;
            }
            QPushButton:hover { background-color: #00F0FF; color: #080B10; border-color: #00F0FF; }
        """)
        copy_btn.clicked.connect(self._copy_content)
        bar_layout.addWidget(copy_btn)

        expand_btn = QPushButton("↗ Tam Ekran")
        expand_btn.setFixedHeight(22)
        expand_btn.setToolTip("Raporu tam ekran ayrı pencerede aç")
        expand_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover { background-color: #00F0FF; color: #080B10; }
        """)
        expand_btn.clicked.connect(self._open_current_standalone)
        bar_layout.addWidget(expand_btn)

        distill_btn = QPushButton("🧠 Sentezle")
        distill_btn.setFixedHeight(22)
        distill_btn.setToolTip(
            "Bu araştırma raporu otomatik olarak bilişsel belleğe alınmıştır.\n"
            "Harici veya elle düzenlenmiş notları belleğe ve RAG indeksine yeniden sentezlemek için kullanabilirsiniz."
        )
        distill_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A263C;
                color: #00FF9D;
                border: 1px solid #00FF9D;
                border-radius: 3px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00FF9D;
                color: #080B10;
            }
        """)
        distill_btn.clicked.connect(self._distill_current_report)
        bar_layout.addWidget(distill_btn)

        delete_btn = QPushButton("🗑️ Sil")
        delete_btn.setFixedHeight(22)
        delete_btn.setToolTip("Seçili raporu diskten ve hafızadan sil")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #261418;
                color: #FF4D4D;
                border: 1px solid #FF4D4D;
                border-radius: 3px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF4D4D;
                color: #080B10;
            }
        """)
        delete_btn.clicked.connect(self._delete_current_report)
        bar_layout.addWidget(delete_btn)

        right_layout.addWidget(self.rag_status_bar)

        # Right text browser: High-Contrast, Ergonomic Markdown Reader
        self.content_browser = QTextBrowser()
        self.content_browser.setMinimumWidth(200)
        self.content_browser.setOpenExternalLinks(True)
        self.content_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {CYBER_THEME['bg_surface']};
                border: 1px solid {CYBER_THEME['border']};
                border-radius: 6px;
                color: {CYBER_THEME['text_primary']};
                padding: 16px 20px;
                font-size: 14px;
                line-height: 1.6;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }}
        """)
        right_layout.addWidget(self.content_browser)
        self.splitter.addWidget(right_container)

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([200, 380])

        self.layout.addWidget(self.splitter)

        # Auto-refresh on signals
        self.active_project_dir = Path(config.default_project_path)
        bus.report_created.connect(self._on_report_created)
        bus.task_notification.connect(self._on_task_notification)
        bus.knowledge_graph_updated.connect(self.refresh_reports)
        bus.agent_turn_completed.connect(self._on_turn_completed)
        bus.project_changed.connect(self._on_project_changed)

        self.refresh_reports()

    @Slot(str, str, str)
    def _on_task_notification(self, _tid: str, _tname: str, _p: str):
        self.refresh_reports()

    @Slot(str)
    def _on_turn_completed(self, _: str):
        self.refresh_reports()

    @Slot(str)
    def _on_project_changed(self, new_dir: str):
        """Update active project directory and reload reports for the new project."""
        self.active_project_dir = Path(new_dir)
        self.refresh_reports()

    def closeEvent(self, event):
        try:
            bus.report_created.disconnect(self._on_report_created)
        except Exception:
            pass
        try:
            bus.task_notification.disconnect(self._on_task_notification)
        except Exception:
            pass
        try:
            bus.knowledge_graph_updated.disconnect(self.refresh_reports)
        except Exception:
            pass
        try:
            bus.agent_turn_completed.disconnect(self._on_turn_completed)
        except Exception:
            pass
        try:
            bus.project_changed.disconnect(self._on_project_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def _filter_reports(self, query: str):
        """Filter the list of reports according to search input."""
        q = query.strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                item.setHidden(bool(q and q not in item.text().lower()))

    def _zoom_in_text(self):
        """Increase reader typography font size across entire rich document."""
        self.content_browser.zoomIn(2)

    def _zoom_out_text(self):
        """Decrease reader typography font size across entire rich document."""
        self.content_browser.zoomOut(2)

    def _copy_content(self):
        """Copy current report markdown text to system clipboard."""
        text = self.content_browser.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            bus.terminal_output_received.emit("[📚 Rapor Merkezi] Rapor metni panoya kopyalandı.\n")

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
        active_proj = getattr(self, "active_project_dir", None) or config.default_project_path
        indexer = ProjectIndexer(active_proj)
        indexer.scan_and_index(max_files=150)

        bus.terminal_output_received.emit(f"\n[🧠 Hafıza & RAG] '{p.name}' raporu başarıyla bilişsel belleğe sentezlendi ve RAG indeksine eklendi.\n")
        bus.report_created.emit(str(p))

    def _delete_current_report(self):
        """Delete currently selected report from disk, remove from cognitive memory, and update knowledge graph."""
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "Seçim Yapılmadı", "Lütfen silmek istediğiniz not veya raporu seçin.")
            return

        path_str = current_item.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return

        p = Path(path_str)
        if not p.exists():
            QMessageBox.warning(self, "Dosya Bulunamadı", "Dosya diskte mevcut değil.")
            return

        # Protect MEMORY.md from accidental full deletion (suggest emptying or confirm strictly)
        if p.name == "MEMORY.md":
            reply = QMessageBox.question(
                self,
                "Global Hafıza Dosyası",
                "Bu dosya sistemin temel 'Global Hafıza (MEMORY.md)' dosyasıdır. Dosyayı sıfırlamak istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                p.write_text("# Entropy AI - Global Memory & Architecture Decisions\n\n## System Beliefs\n- Reset at user request.\n", encoding="utf-8")
                self.content_browser.setMarkdown(p.read_text(encoding="utf-8"))
                bus.terminal_output_received.emit("[Bilişsel Hafıza] MEMORY.md sıfırlandı.\n")
                bus.knowledge_graph_updated.emit()
            return

        reply = QMessageBox.question(
            self,
            "Raporu / Notu Sil",
            f"'{p.name}' dosyasını diskten ve bilişsel bellek dizininden kalıcı olarak silmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 1. Unlink from disk
                p.unlink()

                # 2. Remove associated memory node from SQLite
                try:
                    import sqlite3
                    db_p = Path.home() / ".entropy" / "cognitive_memory.db"
                    if db_p.exists():
                        with sqlite3.connect(db_p) as conn:
                            pattern = f"%{p.stem}%"
                            conn.execute("DELETE FROM cognitive_nodes WHERE id LIKE ? OR content LIKE ?", (pattern, pattern))
                            conn.commit()
                except Exception:
                    pass

                # 3. Update Obsidian Map of Content
                self.vault_manager.sync_map_of_content()

                # 4. Refresh viewer and knowledge graph
                self.content_browser.clear()
                self.refresh_reports()
                bus.knowledge_graph_updated.emit()
                bus.terminal_output_received.emit(f"[Bilişsel Hafıza] '{p.name}' notu diskten ve hafızadan silindi.\n")

            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dosya silinirken hata oluştu: {e}")

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
        active_proj = getattr(self, "active_project_dir", None) or config.default_project_path
        for subfolder in ["reports", "docs", ".entropy/reports"]:
            p_folder = Path(active_proj) / subfolder
            if p_folder.exists():
                for f in sorted(p_folder.glob("*.md")):
                    item = QListWidgetItem(f"📑 {f.stem.replace('_', ' ')}")
                    item.setData(Qt.ItemDataRole.UserRole, str(f))
                    self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self._on_item_clicked(self.list_widget.item(0))
        else:
            from entropy.ui.widgets.markdown_renderer import render_markdown_to_html
            self.content_browser.setHtml(
                render_markdown_to_html(
                    "### 📚 Araştırma ve Hafıza Arşivi\n\n"
                    "Henüz kaydedilmiş bir araştırma raporu bulunmuyor.\n\n"
                    "Zen mod komut satırından yapay zekaya *'... konusunu derinlemesine araştır ve rapor hazırla'* "
                    "talimatı verdiğinizde, üretilen tüm teknik raporlar otomatik olarak buraya ve Obsidian kasanıza kaydedilecektir."
                )
            )

    def _read_selected_report(self):
        """Display currently selected report in the right reading pane and ensure pane is visible."""
        current = self.list_widget.currentItem()
        if not current and self.list_widget.count() > 0:
            current = self.list_widget.item(0)
            self.list_widget.setCurrentItem(current)
        if current:
            self._on_item_clicked(current)
            sizes = self.splitter.sizes()
            if len(sizes) >= 2 and sizes[1] < 140:
                self.splitter.setSizes([200, 380])

    def _open_current_standalone(self):
        """Open the currently selected report in a standalone maximized window."""
        current = self.list_widget.currentItem()
        if current:
            path_str = current.data(Qt.ItemDataRole.UserRole)
            if path_str:
                from entropy.ui.widgets.standalone_report_window import open_standalone_report_window
                open_standalone_report_window(path_str)

    def _on_item_clicked(self, item: QListWidgetItem):
        path_str = item.data(Qt.ItemDataRole.UserRole)
        p = Path(path_str)
        if p.exists():
            raw = p.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
            # Sanitize ANSI escape sequences, control artifacts, and carriage returns
            import re
            cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\([a-zA-Z]|\x1b\][^\x07\x1b]*\x07|\x1b.', '', raw)
            cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
            cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', cleaned)

            from entropy.ui.widgets.markdown_renderer import render_markdown_to_html
            rendered_html = render_markdown_to_html(cleaned, base_dir=p.parent)
            self.content_browser.setHtml(rendered_html)
            self.content_browser.verticalScrollBar().setValue(0)
