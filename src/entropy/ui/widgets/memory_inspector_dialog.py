"""Interactive Cyber Inspector Panel for Knowledge Graph Nodes & Cognitive Memories."""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser,
    QPushButton, QProgressBar, QFrame, QScrollArea, QWidget, QMessageBox
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem, CognitiveMemoryNode
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager


def _parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter returning (metadata_dict, clean_body)."""
    cleaned = text.replace('\r\n', '\n').replace('\r', '\n').lstrip()
    meta: Dict[str, Any] = {}
    body = cleaned
    if cleaned.startswith("---"):
        parts = cleaned.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip().strip('"').strip("'")
                    if k == "tags":
                        if v.startswith("[") and v.endswith("]"):
                            meta[k] = [t.strip().strip('"').strip("'") for t in v[1:-1].split(",") if t.strip()]
                        else:
                            meta[k] = [v]
                    else:
                        meta[k] = v
    return meta, body


class MemoryInspectorDialog(QDialog):
    """Rich interactive modal showing node content, cognitive metrics, and related memories."""

    def __init__(self, node_id: str, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.cog = CognitiveMemorySystem()
        self.vault = ObsidianVaultManager()

        self.setWindowTitle(f"Hafıza ve Bağlam Denetleyicisi - {node_id}")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(780, 620)
        self.setMinimumSize(560, 440)
        self.setSizeGripEnabled(True)
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

        if not self.node_id or not self.node_id.strip():
            self._render_generic_node()
            return

        # 1. Determine node type
        cog_node = self.cog.get_node(self.node_id)
        report_file: Optional[Path] = None

        if not cog_node:
            # Check direct filesystem paths
            cand = Path(self.node_id)
            if cand.is_file():
                report_file = cand
            else:
                cand_vault = self.vault.entropy_dir / self.node_id
                if cand_vault.is_file():
                    report_file = cand_vault
                elif cand_vault.with_suffix(".md").is_file():
                    report_file = cand_vault.with_suffix(".md")
                else:
                    cand_rep = self.vault.reports_dir / Path(self.node_id).name
                    if not cand_rep.name.endswith(".md"):
                        cand_rep = cand_rep.with_suffix(".md")
                    if cand_rep.is_file():
                        report_file = cand_rep

            clean_stem = Path(self.node_id).stem.lower().replace("o-", "").strip()
            # If not matched directly, search reports
            if not report_file and clean_stem:
                reports = self.vault.list_reports()
                # 1. Exact stem or title match
                for r in reports:
                    r_stem = Path(r["path"]).stem.lower()
                    r_title = r["title"].lower().replace(" ", "_")
                    if clean_stem == r_stem or clean_stem == r_title:
                        report_file = Path(r["path"])
                        break

                # 2. Substring match only if term has substance and is not a generic folder name
                if not report_file and len(clean_stem) >= 4 and clean_stem not in ["reports", "dailynotes", "entropy"]:
                    for r in reports:
                        r_stem = Path(r["path"]).stem.lower()
                        if clean_stem in r_stem or r_stem in clean_stem:
                            report_file = Path(r["path"])
                            break

            if not report_file and self.vault.memory_file.exists() and "memory" in clean_stem:
                report_file = self.vault.memory_file

            # Also check project folders
            if not report_file and clean_stem and len(clean_stem) >= 4 and clean_stem not in ["reports", "dailynotes", "entropy"]:
                for subfolder in ["reports", "docs", ".entropy/reports"]:
                    p_folder = config.default_project_path / subfolder
                    if p_folder.exists():
                        for f in p_folder.glob("*.md"):
                            if clean_stem in f.stem.lower() or f.stem.lower() in clean_stem:
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
        self.setWindowTitle(f"Hafıza ve Bağlam Denetleyicisi - {p.stem}")
        raw = p.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")

        meta, body = _parse_frontmatter(raw)

        # Sanitize ANSI codes, terminal control artifacts, and carriage returns
        import re
        body = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\([a-zA-Z]|\x1b\][^\x07\x1b]*\x07|\x1b.', '', body)
        body = body.replace('\r\n', '\n').replace('\r', '\n')
        body = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', body).strip()

        # Modern Header Card with distinct styling and no badge overlapping
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background-color: #0E1420;
                border: 1px solid #1F2B42;
                border-left: 4px solid #BC8CFF;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        hdr_vbox = QVBoxLayout(hdr_frame)
        hdr_vbox.setContentsMargins(4, 4, 4, 4)
        hdr_vbox.setSpacing(4)

        top_row = QHBoxLayout()
        folder_name = p.parent.name if p.parent else "Obsidian"
        cat_tag = QLabel(f"📂 {folder_name}")
        cat_tag.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: bold;")
        top_row.addWidget(cat_tag)
        top_row.addStretch()

        self.btn_max = QPushButton("⛶ Büyüt")
        self.btn_max.setFixedHeight(22)
        self.btn_max.setToolTip("Pencereyi Büyüt / Normal Boyuta Döndür")
        self.btn_max.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 1px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #00F0FF;
                background-color: #1A263C;
            }
        """)
        self.btn_max.clicked.connect(self._toggle_maximize)
        top_row.addWidget(self.btn_max)

        badge = QLabel("OBSİDİAN DOSYASI")
        badge.setStyleSheet("""
            background-color: #1A1429;
            color: #BC8CFF;
            border: 1px solid #9D00FF;
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        top_row.addWidget(badge)
        hdr_vbox.addLayout(top_row)

        display_title = meta.get("title") or p.stem.replace("_", " ")
        title_lbl = QLabel(f"📄 {display_title}")
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("color: #BC8CFF; font-size: 14px; font-weight: bold; padding: 2px 0;")
        hdr_vbox.addWidget(title_lbl)

        # Metadata row
        meta_items = []
        if meta.get("date"):
            meta_items.append(f"📅 {meta['date']}")
        if meta.get("project"):
            meta_items.append(f"📁 Proje: {meta['project']}")
        if meta.get("skill"):
            meta_items.append(f"🎯 Yetenek: {meta['skill']}")

        if meta_items or meta.get("tags"):
            meta_row = QHBoxLayout()
            meta_row.setSpacing(6)
            for item_text in meta_items:
                lbl = QLabel(item_text)
                lbl.setStyleSheet("color: #8B949E; font-size: 10px; font-weight: bold;")
                meta_row.addWidget(lbl)
            if meta.get("tags"):
                tags_list = meta["tags"] if isinstance(meta["tags"], list) else [str(meta["tags"])]
                for t in tags_list[:4]:
                    t_str = str(t).strip()
                    if t_str:
                        t_lbl = QLabel(f"#{t_str}")
                        t_lbl.setStyleSheet("background-color: #141C2C; color: #00F0FF; border: 1px solid #1F2B42; border-radius: 3px; padding: 1px 6px; font-size: 10px;")
                        meta_row.addWidget(t_lbl)
            meta_row.addStretch()
            hdr_vbox.addLayout(meta_row)

        self.layout.addWidget(hdr_frame)

        # Content Box - expandable with rich cyber HTML rendering
        self.layout.addWidget(QLabel("<b style='color:#8B949E; font-size:11px;'>Not Özeti ve İçerik:</b>"))
        content_box = QTextBrowser()
        content_box.setOpenExternalLinks(True)
        content_box.setStyleSheet("""
            QTextBrowser {
                background-color: #0E1420;
                border: 1px solid #1F2B42;
                border-radius: 6px;
                color: #F0F6FC;
                padding: 12px 16px;
                font-size: 13px;
                line-height: 1.6;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
        """)
        content_box.setMinimumHeight(160)
        from entropy.ui.widgets.markdown_renderer import render_markdown_to_html
        rendered_html = render_markdown_to_html(body[:5000] + ("..." if len(body) > 5000 else ""), base_dir=p.parent)
        content_box.setHtml(rendered_html)
        content_box.verticalScrollBar().setValue(0)
        self.layout.addWidget(content_box, 1)

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
        wikilinks = re.findall(r'\[\[(.*?)\]\]', body)
        if wikilinks:
            for wl in set(wikilinks[:5]):
                target = wl.split("|")[0].strip()
                btn = QPushButton(f"📑 [[{target}]] (Obsidian Bağlantısı)")
                btn.setStyleSheet("background-color:#0E1420; color:#9D00FF; border:1px solid #1F2B42; border-radius:4px; padding:3px 8px; text-align:left; font-size:11px;")
                btn.clicked.connect(lambda _, t=target: self._switch_to_node(f"o-{t}"))
                related_layout.addWidget(btn)

        # 2. Semantic memories matching report text
        try:
            paragraphs = [para.strip() for para in body.split("\n\n") if para.strip() and not para.startswith("#")]
            query_str = paragraphs[0][:150] if paragraphs else body[:100]
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

    def _toggle_maximize(self):
        """Toggle maximize/restore state with button text update."""
        if self.isMaximized():
            self.showNormal()
            if hasattr(self, "btn_max"):
                self.btn_max.setText("⛶ Büyüt")
        else:
            self.showMaximized()
            if hasattr(self, "btn_max"):
                self.btn_max.setText("🗗 Küçült")

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
            # Faz 10-B: silmenin TEK girişi bellek katmanıdır (`delete_memory`);
            # arayüz doğrudan SQL çalıştırınca bağlı kenarlar/indeksler geride
            # kalıyordu. Sözleşme yoksa (paralel ajan yazıyor) eski yola düşülür.
            deleted = False
            for module_path in (
                "entropy.memory.graph_store",
                "entropy.memory.cognitive_memory",
                "entropy.core.cognitive_memory",
            ):
                try:
                    import importlib

                    fn = getattr(importlib.import_module(module_path), "delete_memory", None)
                    if fn is None:
                        continue
                    deleted = bool(fn(node_id))
                except Exception:
                    deleted = False
                if deleted:
                    break
            if not deleted:
                import sqlite3
                from entropy.memory.supabase.cognitive_memory import (
                    default_cognitive_db_path,
                )

                db_p = default_cognitive_db_path()
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
        from entropy.ui.widgets.standalone_report_window import open_standalone_report_window
        from PySide6.QtCore import QTimer
        # Accept dialog first so the modal loop finishes and releases focus cleanly
        self.accept()
        # Launch standalone window with slight timer so it acquires foreground reliably
        QTimer.singleShot(80, lambda: open_standalone_report_window(file_path_str))
