"""Research Reports & Memory Dossiers Viewer for Zen Mode."""

import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter,
    QSizePolicy, QTextBrowser, QVBoxLayout, QWidget
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.ui.themes.cyber_theme import CYBER_THEME, READING_TOKENS as RT
from entropy.ui.widgets.report_center import ReportCenterWidget
from entropy.ui.widgets.report_inbox import ReportInboxStrip
from entropy.ui.widgets.ui_polish import apply_list_polish

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def read_report_meta(path: Path) -> Dict[str, Any]:
    """
    Bir rapor dosyasının başlık/etiket/yetenek/proje/tarih üstverisini okur.
    Kaynak sırası: YAML ön maddesi → dosya yolu (Skills/<ad>/Reports) → dosya damgası.
    Dosyanın tamamı okunmaz; ön madde için ilk 4 KB yeter.
    """
    meta: Dict[str, Any] = {
        "path": str(path),
        "title": path.stem.replace("_", " "),
        "tags": [],
        "skill": "",
        "project": "",
        "date": "",
        "modified": "",
        "folder": path.parent.name,
    }
    try:
        stat = path.stat()
        meta["modified"] = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        meta["mtime"] = stat.st_mtime
    except OSError:
        meta["mtime"] = 0.0

    parts = path.parts
    if "Skills" in parts:
        idx = parts.index("Skills")
        if len(parts) > idx + 1:
            meta["skill"] = parts[idx + 1]
    if "Projects" in parts:
        idx = parts.index("Projects")
        if len(parts) > idx + 1:
            meta["project"] = parts[idx + 1]

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(4096)
    except OSError:
        head = ""
    head = head.lstrip("﻿")
    match = FRONTMATTER_RE.match(head)
    if match:
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip().strip('"').strip("'")
            if key == "title" and value:
                meta["title"] = value
            elif key == "date" and value:
                meta["date"] = value
            elif key == "tags" and value:
                raw = value.strip("[]")
                tags = [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]
                meta["tags"] = tags
                for t in tags:
                    low = t.lower()
                    if low.startswith("skill:") and not meta["skill"]:
                        meta["skill"] = t.split(":", 1)[1].strip()
                    elif low.startswith("project:") and not meta["project"]:
                        meta["project"] = t.split(":", 1)[1].strip()
    if not meta["date"]:
        meta["date"] = (meta["modified"] or "")[:10]
    return meta


def move_to_trash(path: Path, trash_root: Path = None) -> str:
    """
    Dosyayı kalıcı olarak silmeden çöpe gönderir.
    send2trash varsa işletim sisteminin geri dönüşüm kutusu, yoksa `.trash`
    alt klasörü kullanılır. Hiçbir durumda unlink çağrılmaz.
    `.trash` kasa kökünde tutulur; Entropy/ altında olsaydı taşınan raporlar
    listede ve bilgi grafiğinde yeniden görünürdü.
    """
    try:
        from send2trash import send2trash  # type: ignore
        send2trash(str(path))
        return "recycle-bin"
    except Exception:
        pass
    trash_dir = Path(trash_root) if trash_root else (path.parent / ".trash")
    trash_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = trash_dir / f"{path.stem}_{stamp}{path.suffix}"
    shutil.move(str(path), str(target))
    return str(target)


def reveal_in_file_manager(path: Path) -> bool:
    """Dosyanın bulunduğu klasörü işletim sisteminin dosya yöneticisinde açar."""
    try:
        if sys.platform.startswith("win"):
            if path.exists():
                subprocess.Popen(["explorer", "/select,", os.path.normpath(str(path))])
            else:
                os.startfile(str(path.parent))  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
            return True
        subprocess.Popen(["xdg-open", str(path.parent)])
        return True
    except Exception:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def obsidian_uri(path: Path, vault_path: Path) -> str:
    """Rapor için `obsidian://open?vault=...&file=...` bağlantısı üretir."""
    from urllib.parse import quote
    try:
        rel = path.resolve().relative_to(Path(vault_path).resolve())
        rel_str = str(rel.with_suffix("")).replace("\\", "/")
    except Exception:
        rel_str = path.stem
    return f"obsidian://open?vault={quote(Path(vault_path).name)}&file={quote(rel_str)}"


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
        # Başlık dar panelde daralabilsin; yoksa üstteki araç çubuğu satırı
        # panelin minimumunu ~676 px'e çıkarıp Zen sol sekmesini kırpıyor.
        title_label.setMinimumWidth(100)
        title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(title_label, 1)

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

        # Rapor Merkezi "Gelen" seridi (Faz 4): son 24 saatte uretilen raporlar,
        # /query sayfalari ve ofis raporlari okunmadi sayaciyla ustte durur.
        # Tiklaninca okuyucuda acilir ve okundu isaretlenir.
        self.inbox_strip = ReportInboxStrip(parent=self)
        self.inbox_strip.report_opened.connect(self.open_report_by_path_or_id)
        self.inbox_strip.unread_changed.connect(self._on_inbox_unread_changed)
        self.layout.addWidget(self.inbox_strip)
        # Faz 5.5: seridin yerini Rapor Merkezi aldi (kumeleme + digest + onem x
        # aciliyet + guven esigi). Serit nesnesi kaldirilmadi cunku okundu/pin/
        # arsiv deposunu ve rozet sozlesmesini paylasiyorlar; yalnizca gizlenir,
        # boylece ayni bilgi ekranda iki kez gorunmez.
        self.inbox_strip.setVisible(False)

        # Rapor Merkezi: sekmenin ust yarisi. Alt yari liste + okuyucudur.
        self.report_center = ReportCenterWidget(parent=self, store=self.inbox_strip.store)
        self.report_center.report_opened.connect(self.open_report_by_path_or_id)
        self.report_center.unread_changed.connect(self._on_inbox_unread_changed)
        # Faz 8: "Tümü" düğmesi tam listeye geçirir (süzgeçleri sıfırlar).
        self.report_center.show_all_requested.connect(self.show_all_reports)
        self.layout.addWidget(self.report_center, 1)

        # Splitter between Report List and Report Content
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Container: Search + Report List
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # Gruplama ve yetenek/proje filtresi
        combo_style = """
            QComboBox {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QComboBox:hover { border-color: #00F0FF; }
            QComboBox::drop-down { border: none; width: 16px; }
            QComboBox QAbstractItemView {
                background-color: #0E1420;
                color: #F0F6FC;
                border: 1px solid #00F0FF;
                selection-background-color: #1F2B42;
                selection-color: #00F0FF;
            }
        """
        combo_row = QHBoxLayout()
        combo_row.setSpacing(4)

        self.group_combo = QComboBox()
        self.group_combo.setFixedHeight(24)
        self.group_combo.setToolTip("Rapor listesini yeteneğe ya da tarihe göre grupla")
        self.group_combo.setStyleSheet(combo_style)
        self.group_combo.addItem("🎯 Yeteneğe Göre", "skill")
        self.group_combo.addItem("📅 Tarihe Göre", "date")
        self.group_combo.addItem("📄 Düz Liste", "flat")
        self.group_combo.currentIndexChanged.connect(self._rebuild_list)
        combo_row.addWidget(self.group_combo, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.setFixedHeight(24)
        self.filter_combo.setToolTip("Yalnızca seçili yetenek / proje raporlarını göster")
        self.filter_combo.setStyleSheet(combo_style)
        self.filter_combo.addItem("Tümü", "")
        self.filter_combo.currentIndexChanged.connect(self._rebuild_list)
        combo_row.addWidget(self.filter_combo, 1)

        left_layout.addLayout(combo_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Başlık / etiket ara...")
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

        self.list_count_lbl = QLabel("")
        self.list_count_lbl.setStyleSheet("color:#8B949E; font-size:10px; padding:0 2px;")
        left_layout.addWidget(self.list_count_lbl)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(120)
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
        # Uzun rapor basliklari yatay kaydirma cubugu dogurmasin; sagdan
        # kirpilir, tam metin girdinin ipucunda kalir (bkz. _rebuild_list).
        apply_list_polish(self.list_widget)
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

        # Dar Zen panelinde okuyucu bolunmesi de daralabilmeli (bkz. Faz 7).
        left_container.setMinimumWidth(120)
        self.splitter.addWidget(left_container)

        # Right container: RAG Status Bar + Markdown Text Browser
        right_container = QWidget()
        right_container.setMinimumWidth(160)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # RAG / Memory Status & Reading Tools Banner
        self.rag_status_bar = QFrame()
        # Okuma araç çubuğu (durum + A+/A-/🔗/📁) doğal olarak ~514 px istiyordu;
        # dar panelde çubuğun kendisi kırpılsın, panel genişlemesin.
        self.rag_status_bar.setMinimumWidth(200)
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

        self.btn_open_obsidian = QPushButton("🔗")
        self.btn_open_obsidian.setFixedSize(26, 22)
        self.btn_open_obsidian.setToolTip("Obsidian — seçili raporu Obsidian kasasında açar")
        self.btn_open_obsidian.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #BC8CFF;
                border: 1px solid #BC8CFF;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover { background-color: #BC8CFF; color: #080B10; }
        """)
        self.btn_open_obsidian.clicked.connect(self._open_in_obsidian)
        bar_layout.addWidget(self.btn_open_obsidian)

        self.btn_open_folder = QPushButton("📁")
        self.btn_open_folder.setFixedSize(26, 22)
        self.btn_open_folder.setToolTip("Klasör — raporun bulunduğu klasörü dosya yöneticisinde açar")
        self.btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #E3B341;
                border: 1px solid #1F2B42;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover { border-color: #E3B341; color: #E3B341; }
        """)
        self.btn_open_folder.clicked.connect(self._open_containing_folder)
        bar_layout.addWidget(self.btn_open_folder)

        copy_btn = QPushButton("📋")
        copy_btn.setFixedSize(26, 22)
        copy_btn.setToolTip("Kopyala — rapor metnini panoya alır")
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

        expand_btn = QPushButton("↗")
        expand_btn.setFixedSize(26, 22)
        expand_btn.setToolTip("Tam ekran — raporu ayrı pencerede açar")
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

        distill_btn = QPushButton("🧠")
        distill_btn.setFixedSize(26, 22)
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

        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedSize(26, 22)
        delete_btn.setToolTip("Sil — seçili raporu diskten ve hafızadan kaldırır")
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

        # Seçili raporun künyesi: başlık, oluşturulma, yetenek/proje, etiketler.
        self.meta_panel = QLabel("")
        self.meta_panel.setWordWrap(True)
        self.meta_panel.setTextFormat(Qt.TextFormat.RichText)
        self.meta_panel.setStyleSheet(f"""
            QLabel {{
                background-color: {RT['surface_raised']};
                border: none;
                border-left: 3px solid {RT['accent']};
                border-radius: {RT['radius_small']};
                padding: 8px 12px;
                color: {RT['text_dim']};
                font-size: {RT['font_size_small']};
            }}
        """)
        self.meta_panel.setVisible(False)
        right_layout.addWidget(self.meta_panel)

        # Right text browser: High-Contrast, Ergonomic Markdown Reader
        self.content_browser = QTextBrowser()
        self.content_browser.setMinimumWidth(200)
        self.content_browser.setOpenExternalLinks(True)
        # Rapor okuma yuzeyi: sohbet balonlariyla ayni tasarim belirtecleri.
        self.content_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {RT['surface_base']};
                border: 1px solid {RT['divider_soft']};
                border-radius: 10px;
                color: {RT['text_body']};
                padding: 18px 22px;
                font-size: {RT['font_size_body']};
                font-family: {RT['font_body']};
                selection-background-color: {RT['accent_soft']};
            }}
        """)
        right_layout.addWidget(self.content_browser)
        self.splitter.addWidget(right_container)

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([200, 380])

        self.layout.addWidget(self.splitter, 1)

        # Auto-refresh on signals
        self.active_project_dir = Path(config.default_project_path)
        self._entries: List[Dict[str, Any]] = []
        self._current_path: str = ""
        bus.report_created.connect(self._on_report_created)
        bus.task_notification.connect(self._on_task_notification)
        bus.knowledge_graph_updated.connect(self.refresh_reports)
        bus.agent_turn_completed.connect(self._on_turn_completed)
        bus.project_changed.connect(self._on_project_changed)

        self.refresh_reports()

    @Slot(str, str, str)
    @Slot(int)
    def _on_inbox_unread_changed(self, count: int):
        """
        Gelen seridi sayaci degisti: rozeti gosteren pencerelere duyur.

        Alici QObject slotu (lambda degil); rapor izleyici isci is parcacigindan
        yenileme tetiklerse bile sinyal ana is parcacigina kuyruklanir.
        """
        try:
            bus.report_inbox_unread.emit(int(count))
        except (AttributeError, RuntimeError):
            pass

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
        # Faz 8: tekrar kapanislarda "Failed to disconnect" RuntimeWarning'i
        # uretmesin; cozme yalnizca gercekten bagliyken yapilir.
        if not getattr(self, "_bus_connected", True):
            super().closeEvent(event)
            return
        self._bus_connected = False
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

    def _filter_reports(self, query: str = ""):
        """Arama kutusu değişince listeyi yeniden kurar (başlık + etiket + yetenek araması)."""
        self._rebuild_list()

    def _add_group_header(self, text: str):
        """Seçilemeyen bir grup başlığı satırı ekler."""
        header = QListWidgetItem(text)
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        header.setData(Qt.ItemDataRole.UserRole, None)
        header.setData(Qt.ItemDataRole.UserRole + 1, "header")
        from PySide6.QtGui import QColor, QFont
        header.setForeground(QColor("#00F0FF"))
        font = QFont()
        font.setBold(True)
        font.setPointSize(8)
        header.setFont(font)
        self.list_widget.addItem(header)

    def _entry_matches(self, entry: Dict[str, Any], query: str, group_filter: str) -> bool:
        """Arama metni ve yetenek/proje filtresine göre kaydın görünürlüğü."""
        if group_filter and entry.get("group_key", "") != group_filter:
            return False
        if not query:
            return True
        haystack = " ".join([
            str(entry.get("title", "")),
            str(entry.get("skill", "")),
            str(entry.get("project", "")),
            " ".join(entry.get("tags", []) or []),
            Path(str(entry.get("path", ""))).name,
        ]).lower()
        return query in haystack

    def _rebuild_list(self, *_args):
        """Kayıtları gruplama/filtre/arama durumuna göre listeye yazar."""
        query = self.search_input.text().strip().lower()
        group_filter = self.filter_combo.currentData() or ""
        mode = self.group_combo.currentData() or "skill"

        prev_path = self._current_path
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        visible = [e for e in self._entries if self._entry_matches(e, query, group_filter)]

        def add_entry(entry: Dict[str, Any]):
            item = QListWidgetItem(entry["label"])
            item.setData(Qt.ItemDataRole.UserRole, entry["path"])
            tip = [entry.get("title", "")]
            if entry.get("skill"):
                tip.append(f"Yetenek: {entry['skill']}")
            if entry.get("project"):
                tip.append(f"Proje: {entry['project']}")
            if entry.get("date"):
                tip.append(f"Tarih: {entry['date']}")
            item.setToolTip("\n".join([t for t in tip if t]))
            self.list_widget.addItem(item)

        if mode == "flat":
            for entry in visible:
                add_entry(entry)
        else:
            buckets: Dict[str, List[Dict[str, Any]]] = {}
            for entry in visible:
                key = entry["group_label"] if mode == "skill" else entry["date_label"]
                buckets.setdefault(key, []).append(entry)
            if mode == "skill":
                keys = sorted(buckets.keys(), key=lambda k: (k.startswith("📌"), k.lower()), reverse=False)
            else:
                # Tarih grupları yeniden eskiye
                keys = sorted(buckets.keys(), key=lambda k: max(e.get("mtime", 0.0) for e in buckets[k]), reverse=True)
            for key in keys:
                self._add_group_header(f"{key}  ({len(buckets[key])})")
                for entry in buckets[key]:
                    add_entry(entry)

        self.list_widget.blockSignals(False)
        self.list_count_lbl.setText(f"{len(visible)} / {len(self._entries)} kayıt")

        # Önceki seçim hâlâ listedeyse korunur, değilse ilk rapor seçilir.
        restored = False
        if prev_path:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == prev_path:
                    self.list_widget.setCurrentItem(item)
                    restored = True
                    break
        if not restored:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole):
                    self.list_widget.setCurrentItem(item)
                    self._on_item_clicked(item)
                    break

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
            entry = self._make_entry(p, "📄", forced_group="📂 Dışarıdan Açılan")
            self._entries.insert(0, entry)
            if self.filter_combo.findData(entry["group_key"]) < 0:
                self.filter_combo.addItem(entry["group_label"], entry["group_key"])
            self._current_path = str(p)
            self._rebuild_list()
            self.open_report_by_path_or_id(str(p))

    @Slot(str)
    def _on_report_created(self, report_path: str):
        """Immediately display a newly generated report."""
        self.refresh_reports()
        self.open_report_by_path_or_id(report_path)

    def _distill_current_report(self):
        """Distill the currently selected report into Cognitive Memory and re-index in RAG."""
        p = self._selected_path()
        if p is None:
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

        # Tek onay; dosya kalıcı silinmez, geri dönüşüm kutusuna / .trash'e taşınır.
        reply = QMessageBox.question(
            self,
            "Raporu / Notu Çöpe Taşı",
            f"'{p.name}' dosyası geri dönüşüm kutusuna taşınacak ve bilişsel bellek kaydı kaldırılacak.\n"
            "Dosya kalıcı olarak silinmez, gerekirse geri alabilirsiniz. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 1. Çöpe taşı (kalıcı silme yok)
                trash_root = Path(self.vault_manager.vault_path) / ".trash"
                destination = move_to_trash(p, trash_root)

                # 2. Remove associated memory node from SQLite
                try:
                    import sqlite3
                    from entropy.memory.supabase.cognitive_memory import (
                        default_cognitive_db_path,
                    )

                    db_p = default_cognitive_db_path()
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
                self.meta_panel.setVisible(False)
                self._current_path = ""
                self.refresh_reports()
                bus.knowledge_graph_updated.emit()
                where = "geri dönüşüm kutusuna" if destination == "recycle-bin" else f"'{destination}' konumuna"
                bus.terminal_output_received.emit(
                    f"[Bilişsel Hafıza] '{p.name}' notu {where} taşındı ve hafıza kaydı kaldırıldı.\n"
                )

            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dosya çöpe taşınırken hata oluştu: {e}")

    def _open_in_obsidian(self):
        """Seçili raporu Obsidian uygulamasında açar (obsidian:// protokolü)."""
        p = self._selected_path()
        if not p:
            QMessageBox.information(self, "Seçim Yapılmadı", "Önce bir rapor seçin.")
            return
        uri = obsidian_uri(p, self.vault_manager.vault_path)
        opened = QDesktopServices.openUrl(QUrl(uri))
        if not opened:
            # Obsidian kurulu değilse dosyayı varsayılan uygulamayla aç
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
        bus.terminal_output_received.emit(f"[📚 Rapor Merkezi] Obsidian'da açılıyor: {p.name}\n")

    def _open_containing_folder(self):
        """Seçili raporun klasörünü dosya yöneticisinde açar."""
        p = self._selected_path()
        if not p:
            QMessageBox.information(self, "Seçim Yapılmadı", "Önce bir rapor seçin.")
            return
        reveal_in_file_manager(p)
        bus.terminal_output_received.emit(f"[📚 Rapor Merkezi] Klasör açıldı: {p.parent}\n")

    def _selected_path(self):
        """Seçili liste satırının dosya yolu (grup başlıkları atlanır)."""
        item = self.list_widget.currentItem()
        path_str = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not path_str:
            path_str = self._current_path
        if not path_str:
            return None
        p = Path(path_str)
        return p if p.exists() else None

    def open_report_by_path_or_id(self, path_or_id: str) -> bool:
        """
        Bir raporu yola, grafik düğüm kimliğine (örn. `Reports/Faz_72`) ya da
        başlığa göre bulup okuyucuda açar. Kayıt arama/filtre yüzünden gizliyse
        filtreler temizlenip liste yeniden kurulur.
        """
        if not path_or_id:
            return False
        raw = str(path_or_id).replace("\\", "/")
        clean = raw.lower()
        # Grafik düğüm kimliği "Klasör/Başlık" biçimindedir; son parça yeter.
        stem = Path(clean).stem.lower()

        target = None
        for entry in self._entries:
            ep = str(entry.get("path", "")).replace("\\", "/").lower()
            if ep == clean:
                target = entry
                break
        if target is None:
            for entry in self._entries:
                ep = str(entry.get("path", "")).replace("\\", "/").lower()
                if clean and clean in ep:
                    target = entry
                    break
                if stem and (Path(ep).stem == stem or stem in ep):
                    target = entry
                    break
        if target is None:
            for entry in self._entries:
                if stem and stem.replace("_", " ") in str(entry.get("title", "")).lower():
                    target = entry
                    break
        if target is None:
            return False

        # Hedef gizliyse filtreleri sıfırla
        query = self.search_input.text().strip().lower()
        group_filter = self.filter_combo.currentData() or ""
        if not self._entry_matches(target, query, group_filter):
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
            self.filter_combo.blockSignals(True)
            self.filter_combo.setCurrentIndex(0)
            self.filter_combo.blockSignals(False)
            self._rebuild_list()

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == target["path"]:
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item)
                self._on_item_clicked(item)
                return True
        return False

    def _make_entry(self, path: Path, icon: str, forced_group: str = "") -> Dict[str, Any]:
        """Dosyadan liste kaydı üretir (künye + gruplama anahtarları)."""
        meta = read_report_meta(path)
        if forced_group:
            group_label = forced_group
            group_key = forced_group
        elif meta["skill"]:
            group_label = f"🎯 {meta['skill']}"
            group_key = f"skill:{meta['skill']}"
        elif meta["project"]:
            group_label = f"📁 {meta['project']}"
            group_key = f"project:{meta['project']}"
        else:
            group_label = "🗂️ Genel Raporlar"
            group_key = "general"

        date_str = str(meta.get("date") or "")[:10]
        try:
            d = datetime.date.fromisoformat(date_str)
            today = datetime.date.today()
            delta = (today - d).days
            if delta <= 0:
                date_label = "📅 Bugün"
            elif delta == 1:
                date_label = "📅 Dün"
            elif delta < 7:
                date_label = "📅 Bu Hafta"
            elif delta < 31:
                date_label = "📅 Bu Ay"
            else:
                date_label = f"📅 {d.strftime('%Y-%m')}"
        except ValueError:
            date_label = "📅 Tarihsiz"

        meta.update({
            "label": f"{icon} {meta['title']}",
            "group_label": group_label,
            "group_key": group_key,
            "date_label": date_label,
        })
        return meta

    @Slot()
    def show_all_reports(self) -> None:
        """Süzgeçleri sıfırlayıp tam rapor listesini gösterir (Faz 8).

        Rapor Merkezi kartları özettir; kullanıcı "toplam raporlar görünmüyor"
        dediğinde asıl istediği bu ham listedir.
        """
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.filter_combo.blockSignals(True)
        self.filter_combo.setCurrentIndex(0)  # "Tümü"
        self.filter_combo.blockSignals(False)
        self._rebuild_list()
        self.list_widget.setFocus()

    def refresh_reports(self):
        """Obsidian kasasından ve proje klasörlerinden rapor künyelerini yeniden yükler."""
        entries: List[Dict[str, Any]] = []
        seen = set()

        # Global hafıza dosyası her zaman en üstte kendi grubunda
        if self.vault_manager.memory_file.exists():
            mem = self._make_entry(self.vault_manager.memory_file, "📌", forced_group="📌 Global Hafıza")
            mem["label"] = "📌 Global Hafıza (MEMORY.md)"
            mem["title"] = "Global Hafıza (MEMORY.md)"
            entries.append(mem)
            seen.add(str(self.vault_manager.memory_file))

        for rep in self.vault_manager.list_reports():
            p = Path(rep["path"])
            if str(p) in seen or not p.exists():
                continue
            seen.add(str(p))
            entries.append(self._make_entry(p, "📄"))

        # Also look in project reports/ and docs/
        active_proj = getattr(self, "active_project_dir", None) or config.default_project_path
        for subfolder in ["reports", "docs", ".entropy/reports"]:
            p_folder = Path(active_proj) / subfolder
            if p_folder.exists():
                for f in sorted(p_folder.glob("*.md")):
                    if str(f) in seen:
                        continue
                    seen.add(str(f))
                    entry = self._make_entry(f, "📑")
                    if entry["group_key"] == "general":
                        entry["group_label"] = f"📁 {Path(active_proj).name} / {subfolder}"
                        entry["group_key"] = f"project:{Path(active_proj).name}"
                    entries.append(entry)

        self._entries = entries
        # Gelen seridi ayni kunye listesinden beslenir: ikinci bir tarama yok.
        try:
            self.inbox_strip.set_entries(entries)
        except (AttributeError, RuntimeError):
            pass
        # Rapor Merkezi de ayni listeden beslenir; posta kutusu mesajlarini
        # kendisi ekler (kasa taramasi ikinci kez yapilmaz).
        try:
            self.report_center.set_entries(entries)
        except (AttributeError, RuntimeError):
            pass

        # Filtre açılır listesini keşfedilen gruplara göre tazele
        prev_filter = self.filter_combo.currentData()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Tümü", "")
        group_pairs = {}
        for e in entries:
            group_pairs.setdefault(e["group_key"], e["group_label"])
        for key in sorted(group_pairs, key=lambda k: group_pairs[k].lower()):
            self.filter_combo.addItem(group_pairs[key], key)
        idx = self.filter_combo.findData(prev_filter)
        self.filter_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.filter_combo.blockSignals(False)

        self._rebuild_list()

        if not entries:
            self.meta_panel.setVisible(False)
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
        if (not current or not current.data(Qt.ItemDataRole.UserRole)):
            current = None
            for i in range(self.list_widget.count()):
                candidate = self.list_widget.item(i)
                if candidate and candidate.data(Qt.ItemDataRole.UserRole):
                    current = candidate
                    self.list_widget.setCurrentItem(candidate)
                    break
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

    def _update_meta_panel(self, path: Path):
        """Okuyucunun üstünde seçili raporun künyesini gösterir."""
        meta = next((e for e in self._entries if e.get("path") == str(path)), None)
        if meta is None:
            meta = read_report_meta(path)
        chips = []
        if meta.get("skill"):
            chips.append(
                f"<span style='color:#00FF9D;'>🎯 {meta['skill']}</span>"
            )
        if meta.get("project"):
            chips.append(f"<span style='color:#58A6FF;'>📁 {meta['project']}</span>")
        if meta.get("date"):
            chips.append(f"<span style='color:#E3B341;'>📅 {meta['date']}</span>")
        if meta.get("modified"):
            chips.append(f"<span style='color:#8B949E;'>🕒 {meta['modified']}</span>")
        tags = [t for t in (meta.get("tags") or []) if not t.lower().startswith(("skill:", "project:"))]
        tag_html = ""
        if tags:
            tag_html = "<br/>" + " ".join(
                f"<span style='background:#141C2C; border:1px solid #1F2B42; border-radius:3px; padding:1px 5px; color:#BC8CFF;'>#{t}</span>"
                for t in tags[:10]
            )
        self.meta_panel.setText(
            f"<b style='color:#F0F6FC; font-size:12px;'>{meta.get('title', path.stem)}</b><br/>"
            + " &nbsp;·&nbsp; ".join(chips)
            + tag_html
        )
        self.meta_panel.setToolTip(str(path))
        self.meta_panel.setVisible(True)

    def _on_item_clicked(self, item: QListWidgetItem):
        path_str = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not path_str:
            return  # Grup başlığı satırı
        p = Path(path_str)
        if p.exists():
            self._current_path = str(p)
            self._update_meta_panel(p)
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
