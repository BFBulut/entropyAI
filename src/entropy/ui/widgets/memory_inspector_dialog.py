"""Interactive Cyber Inspector Panel for Knowledge Graph Nodes & Cognitive Memories."""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser,
    QPushButton, QProgressBar, QFrame, QScrollArea, QWidget, QMessageBox
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem, CognitiveMemoryNode
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager

class MemoryInspectorDialog(QDialog):
    """Rich interactive modal showing node content, cognitive metrics, and related memories."""

    def __init__(self, node_id: str, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.cog = CognitiveMemorySystem()
        self.vault = ObsidianVaultManager()

        self.setWindowTitle(f"Hafıza ve Bağlam Denetleyicisi - {node_id}")
        self.setFixedSize(620, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #080B10;
                color: #F0F6FC;
                border: 1px solid #00F0FF;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                color: #F0F6FC;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)
        self.layout.setSpacing(10)

        self._render_node_details()

    def _render_node_details(self):
        # Clear previous layout if any
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        # 1. Determine node type
        cog_node = self.cog.get_node(self.node_id)
        report_file: Optional[Path] = None

        if not cog_node:
            # Check if it's an Obsidian report
            clean = self.node_id.replace("o-", "").lower()
            reports = self.vault.list_reports()
            for r in reports:
                if clean in r["title"].lower() or clean in Path(r["path"]).stem.lower():
                    report_file = Path(r["path"])
                    break
            if not report_file and self.vault.memory_file.exists() and "memory" in clean:
                report_file = self.vault.memory_file

            # Also check project reports/
            if not report_file:
                for subfolder in ["reports", "docs", ".entropy/reports"]:
                    p_folder = config.default_project_path / subfolder
                    if p_folder.exists():
                        for f in p_folder.glob("*.md"):
                            if clean in f.stem.lower():
                                report_file = f
                                break

        if cog_node:
            self._render_cognitive_node(cog_node)
        elif report_file and report_file.exists():
            self._render_report_node(report_file)
        else:
            self._render_generic_node()

    def _render_cognitive_node(self, node: CognitiveMemoryNode):
        # Header
        hdr = QHBoxLayout()
        title_lbl = QLabel(f"<b style='color:#00F0FF; font-size:14px;'>🧠 {node.id}</b>")
        hdr.addWidget(title_lbl)
        hdr.addStretch()

        cat_color = "#00FF9D" if node.category == "semantic" else "#FFB300" if node.category == "episodic" else "#00F0FF"
        badge = QLabel(f"<span style='background:#141C2C; color:{cat_color}; border:1px solid {cat_color}; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:11px;'>KATMAN: {node.category.upper()}</span>")
        hdr.addWidget(badge)
        self.layout.addLayout(hdr)

        # Content Box
        self.layout.addWidget(QLabel("<b style='color:#8B949E; font-size:11px;'>Düğüm İçeriği / Hatırlanan Bilgi:</b>"))
        content_box = QTextBrowser()
        content_box.setStyleSheet("background-color: #0E1420; border: 1px solid #1F2B42; color: #F0F6FC; padding: 8px; font-size: 12px; border-radius: 4px;")
        content_box.setFixedHeight(120)
        content_box.setMarkdown(node.content)
        self.layout.addWidget(content_box)

        # Cognitive Metrics
        ebbinghaus = node.calculate_ebbinghaus_strength()
        metrics_layout = QHBoxLayout()
        imp_lbl = QLabel(f"Önem Skoru: <b style='color:#00FF9D;'>{node.importance:.2f}</b>")
        ret_lbl = QLabel(f"Hatırlama Gücü (Ebbinghaus): <b style='color:#00F0FF;'>%{int(ebbinghaus * 100)}</b>")
        acc_lbl = QLabel(f"Erişim Sayısı: <b style='color:#E6EDF3;'>{node.access_count}</b>")
        metrics_layout.addWidget(imp_lbl)
        metrics_layout.addWidget(ret_lbl)
        metrics_layout.addWidget(acc_lbl)
        self.layout.addLayout(metrics_layout)

        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(ebbinghaus * 100))
        pbar.setFixedHeight(8)
        pbar.setTextVisible(False)
        pbar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #1F2B42;
                border-radius: 4px;
                background: #0E1420;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00F0FF, stop:1 #00FF9D);
                border-radius: 3px;
            }
        """)
        self.layout.addWidget(pbar)

        # Related Knowledge / Bağlantılı Bilgiler
        self.layout.addWidget(QLabel("<b style='color:#00F0FF; font-size:12px;'>🔗 Bu Hafızayla İlişkili Düğümler & Bilgiler:</b>"))
        related_scroll = QScrollArea()
        related_scroll.setFixedHeight(140)
        related_widget = QWidget()
        related_layout = QVBoxLayout(related_widget)
        related_layout.setContentsMargins(4, 4, 4, 4)
        related_layout.setSpacing(4)

        try:
            recalled = self.cog.hybrid_recall(node.content, limit=4)
            filtered = [r for r in recalled if r.id != node.id]
            if filtered:
                for rel in filtered:
                    btn = QPushButton(f"🧠 [{rel.category.upper()}] {rel.content[:65]}... (Skor: {rel.calculate_ebbinghaus_strength():.2f})")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #0E1420;
                            color: #E6EDF3;
                            border: 1px solid #1F2B42;
                            border-radius: 4px;
                            padding: 4px 8px;
                            text-align: left;
                            font-size: 11px;
                        }
                        QPushButton:hover {
                            border-color: #00F0FF;
                            color: #00F0FF;
                        }
                    """)
                    btn.clicked.connect(lambda _, rid=rel.id: self._switch_to_node(rid))
                    related_layout.addWidget(btn)
            else:
                related_layout.addWidget(QLabel("<span style='color:#8B949E; font-size:11px;'>Bu düğümle doğrudan eşleşen başka semantik anı bulunamadı.</span>"))
        except Exception:
            related_layout.addWidget(QLabel("<span style='color:#8B949E; font-size:11px;'>İlişkili düğümler sorgulanırken bir sorun oluştu.</span>"))

        related_layout.addStretch()
        related_scroll.setWidget(related_widget)
        related_scroll.setWidgetResizable(True)
        self.layout.addWidget(related_scroll)

        # Actions
        btn_box = QHBoxLayout()
        export_btn = QPushButton("📄 Obsidian Kasasına Aktar")
        export_btn.setStyleSheet("background-color: #141C2C; color: #00FF9D; border: 1px solid #00FF9D; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        export_btn.clicked.connect(lambda: self._export_to_obsidian(node))
        btn_box.addWidget(export_btn)

        del_btn = QPushButton("🗑️ Hafızadan Sil")
        del_btn.setStyleSheet("background-color: #261418; color: #FF4D4D; border: 1px solid #FF4D4D; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        del_btn.clicked.connect(lambda: self._delete_cog_node(node.id))
        btn_box.addWidget(del_btn)

        btn_box.addStretch()
        close_btn = QPushButton("Kapat")
        close_btn.setStyleSheet("background-color: #1A263C; color: #F0F6FC; border: 1px solid #1F2B42; padding: 6px 16px; border-radius: 4px;")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)

        self.layout.addLayout(btn_box)

    def _render_report_node(self, p: Path):
        content = p.read_text(encoding="utf-8", errors="replace")

        # Header
        hdr = QHBoxLayout()
        title_lbl = QLabel(f"<b style='color:#9D00FF; font-size:14px;'>📄 {p.name}</b>")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        badge = QLabel("<span style='background:#141C2C; color:#9D00FF; border:1px solid #9D00FF; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:11px;'>OBSİDİAN DOSYASI</span>")
        hdr.addWidget(badge)
        self.layout.addLayout(hdr)

        # Content Box
        self.layout.addWidget(QLabel("<b style='color:#8B949E; font-size:11px;'>Not Özeti ve İçerik:</b>"))
        content_box = QTextBrowser()
        content_box.setStyleSheet("background-color: #0E1420; border: 1px solid #1F2B42; color: #F0F6FC; padding: 8px; font-size: 12px; border-radius: 4px;")
        content_box.setFixedHeight(150)
        content_box.setMarkdown(content[:1500] + ("..." if len(content) > 1500 else ""))
        self.layout.addWidget(content_box)

        # Related Knowledge / Wikilinks & Semantic Nodes
        self.layout.addWidget(QLabel("<b style='color:#00F0FF; font-size:12px;'>🔗 Bu Notla İlişkili Bilgi ve Bağlantılar:</b>"))
        related_scroll = QScrollArea()
        related_scroll.setFixedHeight(120)
        related_widget = QWidget()
        related_layout = QVBoxLayout(related_widget)
        related_layout.setContentsMargins(4, 4, 4, 4)
        related_layout.setSpacing(4)

        # 1. Backlinks in text
        import re
        wikilinks = re.findall(r'\[\[(.*?)\]\]', content)
        if wikilinks:
            for wl in set(wikilinks[:5]):
                target = wl.split("|")[0].strip()
                btn = QPushButton(f"📑 [[{target}]] (Obsidian Bağlantısı)")
                btn.setStyleSheet("background-color:#0E1420; color:#9D00FF; border:1px solid #1F2B42; border-radius:4px; padding:3px 8px; text-align:left; font-size:11px;")
                btn.clicked.connect(lambda _, t=target: self._switch_to_node(f"o-{t}"))
                related_layout.addWidget(btn)

        # 2. Semantic memories matching report text
        try:
            paragraphs = [para.strip() for para in content.split("\n\n") if para.strip() and not para.startswith("#")]
            query_str = paragraphs[0][:150] if paragraphs else content[:100]
            recalled = self.cog.hybrid_recall(query_str, limit=3)
            for rel in recalled:
                btn = QPushButton(f"🧠 [Bilişsel Bellek] {rel.content[:60]}...")
                btn.setStyleSheet("background-color:#0E1420; color:#00FF9D; border:1px solid #1F2B42; border-radius:4px; padding:3px 8px; text-align:left; font-size:11px;")
                btn.clicked.connect(lambda _, rid=rel.id: self._switch_to_node(rid))
                related_layout.addWidget(btn)
        except Exception:
            pass

        related_layout.addStretch()
        related_scroll.setWidget(related_widget)
        related_scroll.setWidgetResizable(True)
        self.layout.addWidget(related_scroll)

        # Actions
        btn_box = QHBoxLayout()
        open_btn = QPushButton("📖 Ayrı Ekranda Oku")
        open_btn.setStyleSheet("background-color: #141C2C; color: #00F0FF; border: 1px solid #00F0FF; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        open_btn.clicked.connect(lambda: self._open_standalone_report(str(p)))
        btn_box.addWidget(open_btn)

        del_btn = QPushButton("🗑️ Notu Sil")
        del_btn.setStyleSheet("background-color: #261418; color: #FF4D4D; border: 1px solid #FF4D4D; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        del_btn.clicked.connect(lambda: self._delete_report_file(p))
        btn_box.addWidget(del_btn)

        btn_box.addStretch()
        close_btn = QPushButton("Kapat")
        close_btn.setStyleSheet("background-color: #1A263C; color: #F0F6FC; border: 1px solid #1F2B42; padding: 6px 16px; border-radius: 4px;")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)

        self.layout.addLayout(btn_box)

    def _render_generic_node(self):
        self.layout.addWidget(QLabel(f"<b style='color:#00F0FF; font-size:14px;'>🌐 Düğüm: {self.node_id}</b>"))
        self.layout.addWidget(QLabel("<span style='color:#8B949E;'>Bu düğüm için kayıtlı ek metin detayı bulunmuyor.</span>"))
        self.layout.addStretch()
        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.accept)
        self.layout.addWidget(close_btn)

    def _switch_to_node(self, target_node_id: str):
        self.node_id = target_node_id
        self.setWindowTitle(f"Hafıza ve Bağlam Denetleyicisi - {target_node_id}")
        self._render_node_details()

    def _export_to_obsidian(self, node: CognitiveMemoryNode):
        path = self.vault.save_research_report(f"Hafiza_{node.id}", f"# Bilişsel Düğüm: {node.id}\n\n**Kategori**: {node.category}\n**Önem**: {node.importance}\n\n{node.content}")
        bus.terminal_output_received.emit(f"[Obsidian Export] Düğüm kaydedildi: {path.name}\n")
        QMessageBox.information(self, "Başarılı", f"Düğüm Obsidian kasasına aktarıldı:\n{path.name}")

    def _delete_cog_node(self, node_id: str):
        reply = QMessageBox.question(
            self,
            "Düğümü Sil",
            f"'{node_id}' bilişsel düğümünü hafızadan kalıcı olarak silmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            import sqlite3
            db_p = Path.home() / ".entropy" / "cognitive_memory.db"
            if db_p.exists():
                with sqlite3.connect(db_p) as conn:
                    conn.execute("DELETE FROM cognitive_nodes WHERE id = ?", (node_id,))
                    conn.commit()
            bus.terminal_output_received.emit(f"[Bilişsel Hafıza] '{node_id}' düğümü silindi.\n")
            bus.knowledge_graph_updated.emit()
            self.accept()

    def _delete_report_file(self, p: Path):
        reply = QMessageBox.question(
            self,
            "Raporu Sil",
            f"'{p.name}' dosyasını diskten ve hafıza haritasından silmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            p.unlink(missing_ok=True)
            self.vault.sync_map_of_content()
            bus.terminal_output_received.emit(f"[Bilişsel Hafıza] '{p.name}' dosyası silindi.\n")
            bus.knowledge_graph_updated.emit()
            self.accept()

    def _open_standalone_report(self, file_path_str: str):
        from entropy.ui.widgets.standalone_report_window import StandaloneReportWindow
        self.report_win = StandaloneReportWindow()
        self.report_win.open_report_file(file_path_str)
        self.accept()
