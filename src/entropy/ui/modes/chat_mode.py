"""Chat Mode: Floating conversational modal with multimodal image support and terminal drawer."""

import html
import json
from pathlib import Path
import re
from typing import List, Optional
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QKeyEvent, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QScrollArea, QTabWidget, QTextBrowser, QVBoxLayout, QWidget
)

import sys as _sys
import entropy.core.config  # noqa: F401  (alt modulun yuklenmesi icin)
# entropy.core paketi 'config' adini config NESNESINE baglar; sohbet
# gecmisi yardimcilari icin gercek modul gerekiyor.
config_module = _sys.modules["entropy.core.config"]
from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.platform.clipboard import ClipboardImageHandler
from entropy.skills.manager import SkillManager
from entropy.ui.themes.cyber_theme import CYBER_THEME, READING_TOKENS as RT, STYLESHEET, reading_css
from entropy.ui.widgets.command_palette import install_command_palette
from entropy.ui.widgets.focus_mode import install_focus_mode
from entropy.ui.widgets.notification_center import NotificationCenter
from entropy.ui.widgets.provider_badge import ProviderStatusBadge
from entropy.ui.widgets.report_center import ReportCenterWidget
from entropy.ui.widgets.timeline_panel import TimelinePanel
from entropy.ui.widgets.report_inbox import (
    InboxBadge, ReportInboxStrip, collect_recent_entries,
)
from entropy.ui.widgets.ui_polish import apply_model_placeholder
from entropy.ui.widgets.markdown_renderer import build_chat_bubble_html, render_markdown_to_html
from entropy.core.slash_commands import SlashCommandRegistry, invalidate_command_cache
from entropy.mcp.manager import default_mcp_manager
from entropy.ui.widgets.notification_pill import NotificationPillWidget
from entropy.ui.widgets.slash_command_popup import SlashCommandPopupWidget
from entropy.ui.widgets.terminal_pane import TerminalPaneWidget

class ChatInputField(QLineEdit):
    """Custom input line that intercepts Ctrl+V for clipboard images and shows dynamic slash command autocomplete."""

    def __init__(self, parent_chat, parent=None):
        super().__init__(parent)
        self.parent_chat = parent_chat
        self.registry = SlashCommandRegistry(mcp_manager=default_mcp_manager)
        self.popup = SlashCommandPopupWidget()
        self.popup.commands_updated.connect(self._on_commands_updated)
        self.textChanged.connect(self._on_text_changed)
        self._updating_from_popup = False

        # Öneri gecikmesi: katalog taraması her tuşta değil, yazma durunca çalışır.
        # Hızlı yazarken tuş başına yapılan iş yalnızca zamanlayıcıyı yeniden
        # kurmak; katalog işi 150 ms sessizlikten sonra tek sefer yapılır.
        self._suggest_timer = QTimer(self)
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.setInterval(150)
        self._suggest_timer.timeout.connect(self._update_suggestions)
        self._pending_token: str = ""
        self._pending_prev_cmds: List[str] = []

        # Yetenek/MCP kataloğu değişince önbellek geçersiz kılınır; alıcı bu
        # QObject'in slotu (lambda değil), bağlantı bu iş parçacığına kuyruklanır.
        bus.skills_updated.connect(self._on_command_catalog_changed)
        bus.mcp_servers_updated.connect(self._on_command_catalog_changed)

    @Slot()
    def _on_command_catalog_changed(self):
        invalidate_command_cache()

    def _get_active_project_dir(self) -> Optional[Path]:
        if hasattr(self.parent_chat, "bridge") and self.parent_chat.bridge:
            return getattr(self.parent_chat.bridge, "active_project_dir", None)
        # Hata düzeltmesi: getattr(obj, None) TypeError atıyordu (nitelik adı
        # dizge olmalı); köprüsüz ebeveynlerde her tuşta istisna üretiyordu.
        return getattr(self.parent_chat, "active_project_dir", None)

    def _extract_non_command_suffix(self, text: str) -> str:
        tokens = text.split()
        non_cmd_tokens = []
        for t in tokens:
            # Drop single slash command triggers like /boost or /f, but preserve paths like /home/user/file.txt
            if t == "/" or (t.startswith("/") and t.count("/") == 1 and re.match(r"^/[a-zA-Z0-9_\-:]+$", t)):
                continue
            non_cmd_tokens.append(t)
        return " ".join(non_cmd_tokens)

    def _on_text_changed(self, text: str):
        """Tuş başına yalnızca ucuz metin ayrıştırması; ağır iş gecikmeye alınır."""
        if self._updating_from_popup:
            return

        cursor_pos = self.cursorPosition()
        text_before_cursor = text[:cursor_pos]
        tokens = text_before_cursor.split()
        active_token = tokens[-1] if tokens else ""

        # Check if the active token being typed is a single slash command (not a unix file path)
        if active_token.startswith("/") and active_token.count("/") == 1:
            self._pending_token = active_token
            # Pre-selected commands are any previous slash commands before the active token
            self._pending_prev_cmds = [
                t for t in tokens[:-1]
                if t.startswith("/") and t.count("/") == 1 and re.match(r"^/[a-zA-Z0-9_\-:]+$", t)
            ]
            self._suggest_timer.start()
        else:
            self._pending_token = ""
            self._suggest_timer.stop()
            self.popup.hide()

    @Slot()
    def _update_suggestions(self):
        """Gecikme dolunca komut önerilerini hesaplar ve açılır listeyi tazeler."""
        token = self._pending_token
        if not token:
            self.popup.hide()
            return
        p_dir = self._get_active_project_dir()
        matches = self.registry.filter_commands(token, project_dir=p_dir)
        if matches:
            self.popup.set_commands(matches, preselected=self._pending_prev_cmds)
            self.popup.show_at_input(self)
        else:
            self.popup.hide()

    def _on_commands_updated(self, cmd_list: List[str]):
        self._updating_from_popup = True
        try:
            current_text = self.text()
            suffix = self._extract_non_command_suffix(current_text)
            if cmd_list:
                cmds_str = " ".join(cmd_list)
                new_text = f"{cmds_str} {suffix}".strip() + " "
            else:
                new_text = suffix
            self.setText(new_text)
            self.setCursorPosition(len(self.text()))
        finally:
            self._updating_from_popup = False
        self.setFocus()

    def _on_command_selected(self, cmd_name: str):
        self._on_commands_updated([cmd_name])

    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.StandardKey.Paste) or (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V):
            if hasattr(self.parent_chat, "try_paste_image") and self.parent_chat.try_paste_image():
                event.accept()
                return

        if hasattr(self, "popup") and self.popup.isVisible():
            if event.key() == Qt.Key.Key_Up:
                self.popup.select_previous()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Down:
                self.popup.select_next()
                event.accept()
                return
            elif event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.popup.has_selection():
                    self.popup.confirm_selection()
                    event.accept()
                    return
            elif event.key() == Qt.Key.Key_Escape:
                self.popup.hide()
                event.accept()
                return

        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        if hasattr(self, "popup") and self.popup.isVisible():
            if not self.popup.underMouse():
                self.popup.hide()
        super().focusOutEvent(event)

    def moveEvent(self, event):
        if hasattr(self, "popup") and self.popup.isVisible():
            self.popup.show_at_input(self)
        super().moveEvent(event)

    def hideEvent(self, event):
        # Kapanış sırasında C++ tarafı önce yok edilebiliyor; RuntimeError'ı
        # yutmazsak Qt çıkışta atexit izi basıyor.
        try:
            if hasattr(self, "popup"):
                self.popup.hide()
        except RuntimeError:
            pass
        super().hideEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "popup"):
            self.popup.close()
        for sig in (bus.skills_updated, bus.mcp_servers_updated):
            try:
                sig.disconnect(self._on_command_catalog_changed)
            except Exception:
                pass
        super().closeEvent(event)


class ChatModeWindow(QMainWindow):
    """Floating Chat Mode with real-time streaming, terminal drawer, and Ctrl+V images."""

    def __init__(self, bridge: AgyProcessBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.clipboard_handler = ClipboardImageHandler()
        self.staged_images: List[str] = []
        self.staged_pdfs: List[str] = []

        self.setStyleSheet(STYLESHEET)
        self.setWindowTitle("Entropy AI Chat")
        self.resize(540, 700)
        self.setAcceptDrops(True)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(6)

        # 1. Header
        header = QFrame()
        header.setObjectName("cardFrame")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 6, 10, 6)

        title = QLabel("<b style='color:#00F0FF;'>💬 Entropy AI Chat</b>")
        h_layout.addWidget(title)

        # Agent Desk düğmesi: başlığın hemen sağında (Zen ile parite).
        self.desk_btn = QPushButton("🏢 Entropy Agent Desk")
        self.desk_btn.setFixedHeight(24)
        self.desk_btn.setToolTip("Ofis masasını aç (ajan ofisleri, kanban, canlı akış)")
        self.desk_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #C084FC;
                border: 1px solid #3B2A57;
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { border-color: #C084FC; background-color: #1A2438; }
        """)
        self.desk_btn.clicked.connect(self.open_agent_desk)
        h_layout.addWidget(self.desk_btn)

        h_layout.addStretch()

        # Project Selector Button
        self.project_btn = QPushButton(f"📁 {self.bridge.active_project_dir.name}")
        self.project_btn.setFixedHeight(24)
        self.project_btn.setToolTip(f"Aktif Proje: {self.bridge.active_project_dir}\nDeğiştirmek için tıklayın.")
        self.project_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                border-color: #00F0FF;
                background-color: #1A2438;
            }
        """)
        self.project_btn.clicked.connect(self._select_project_dir)
        h_layout.addWidget(self.project_btn)

        # Sağlayıcı seçici: hangi CLI'ın konuştuğunu belirler (agy / claude).
        # Model listesi sağlayıcıya bağlı olduğu için seçim değişince aşağıdaki
        # model combo'su da yeniden doldurulur (refresh_provider_ui).
        self.provider_combo = QComboBox()
        self.provider_combo.setToolTip("Sağlayıcı (CLI): agy = Antigravity, claude = Claude Code")
        from entropy.core.provider import PROVIDERS as _PROVIDERS
        for p in _PROVIDERS:
            self.provider_combo.addItem(p)
        self.provider_combo.setCurrentText(getattr(self.bridge, "provider_name", "agy"))
        self.provider_combo.currentTextChanged.connect(self._on_provider_selected)
        h_layout.addWidget(self.provider_combo)

        # Dynamic Model Selector Combo (RULE: agent-ui-models)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        models = self.bridge.fetch_available_models()
        for m in models:
            self.model_combo.addItem(m)
        self.model_combo.setCurrentText(self.bridge.selected_model)
        # Boş model kutusu "Model:" etiketinin yanında kopuk bir ayraç gibi
        # duruyordu; boşken ne anlama geldiğini yazan yer tutucu konur.
        apply_model_placeholder(self.model_combo, models)
        self.model_combo.currentTextChanged.connect(self._on_model_selected)
        h_layout.addWidget(self.model_combo)

        # Dynamic Skill Selector Combo
        self.skill_combo = QComboBox()
        self.skill_combo.setStyleSheet("""
            QComboBox {
                background-color: #05070A;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self._populate_skills_combo()
        h_layout.addWidget(self.skill_combo)

        self.tokens_badge = QLabel("0 tokens")
        self.tokens_badge.setStyleSheet("color:#00FF9D; font-family:'Consolas'; font-size:11px; font-weight:bold;")
        h_layout.addWidget(self.tokens_badge)

        # Bağlam doluluk rozeti (Zen ile aynı biçimlendirici).
        self.context_badge = QLabel("Bağlam: %0")
        h_layout.addWidget(self.context_badge)
        self._apply_context_badge()

        # Durum rozeti: Zen'deki çekirdek durum etiketiyle aynı bus sinyaline bağlı.
        # Arka plan görevi / damıtma haberleri de buraya düşer, böylece Chat modunda
        # da "arkada ne çalışıyor?" sorusu yanıtsız kalmaz.
        self.state_badge = QLabel("🟢 HAZIR")
        self.state_badge.setToolTip("Entropy AI çekirdek durumu")
        self.state_badge.setStyleSheet(
            "color:#00FF9D; background:#05070A; border:1px solid #1F2B42; border-radius:4px;"
            " padding:2px 8px; font-size:10px; font-weight:bold;"
        )
        h_layout.addWidget(self.state_badge)

        btn_new_chat = QPushButton("+ Yeni")
        btn_new_chat.setFixedHeight(24)
        btn_new_chat.setStyleSheet("background-color:#141C2C; color:#00F0FF; border:1px solid #00F0FF; font-weight:bold;")
        btn_new_chat.clicked.connect(self._on_new_chat)
        h_layout.addWidget(btn_new_chat)

        btn_reports = QPushButton("📚 Raporlar")
        btn_reports.setFixedHeight(24)
        btn_reports.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00FF9D;
                border: 1px solid #00FF9D;
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #00FF9D;
                color: #080B10;
            }
        """)
        btn_reports.clicked.connect(self._open_reports_window)
        h_layout.addWidget(btn_reports)

        # Görev & yetenek paneli açma düğmesi (Zen'deki sekmelerin kompakt karşılığı)
        self.panel_btn = QPushButton("🧩 Panel")
        self.panel_btn.setFixedHeight(24)
        self.panel_btn.setToolTip("Görevler ve Yetenekler panelini aç/kapat")
        self.panel_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { border-color: #00F0FF; }
        """)
        self.panel_btn.clicked.connect(self.toggle_side_panel)
        h_layout.addWidget(self.panel_btn)

        # Rapor Merkezi rozeti — Zen üst çubuğundakiyle aynı bileşen (parite).
        self.inbox_badge = InboxBadge()
        h_layout.addWidget(self.inbox_badge)
        bus.report_inbox_unread.connect(self._on_inbox_unread)

        # Saglayici durum rozeti — Zen ust cubugundakiyle ayni bilesen (parite).
        self.provider_badge = ProviderStatusBadge()
        self.provider_badge.login_requested.connect(self._on_provider_login_requested)
        h_layout.addWidget(self.provider_badge)

        btn_zen = QPushButton("Zen Mode")
        btn_zen.setFixedHeight(24)
        btn_zen.clicked.connect(lambda: bus.mode_requested.emit("zen"))
        h_layout.addWidget(btn_zen)

        self.layout.addWidget(header)

        # Report quick notification bar (shown when a report is created)
        self.report_bar = QFrame()
        self.report_bar.setVisible(False)
        self.report_bar.setStyleSheet("""
            QFrame {
                background-color: #0E1420;
                border: 1px solid #00F0FF;
                border-radius: 5px;
            }
        """)
        rb_layout = QHBoxLayout(self.report_bar)
        rb_layout.setContentsMargins(8, 4, 8, 4)
        self.report_bar_lbl = QLabel("<span style='color:#00FF9D; font-weight:bold;'>📑 Yeni Araştırma Raporu Hazır</span>")
        rb_layout.addWidget(self.report_bar_lbl)
        rb_layout.addStretch()

        self.btn_view_report = QPushButton("Ayrı Ekranda Oku ↗")
        self.btn_view_report.setFixedHeight(22)
        self.btn_view_report.setStyleSheet("background-color: #00F0FF; color: #080B10; font-weight: bold; font-size: 11px; padding: 2px 8px; border-radius: 3px;")
        self.btn_view_report.clicked.connect(self._open_latest_report)
        rb_layout.addWidget(self.btn_view_report)

        btn_dismiss_report = QPushButton("✕")
        btn_dismiss_report.setFixedSize(20, 20)
        btn_dismiss_report.setStyleSheet("background: transparent; color: #8B949E; border: none; font-weight: bold;")
        btn_dismiss_report.clicked.connect(lambda: self.report_bar.setVisible(False))
        rb_layout.addWidget(btn_dismiss_report)

        self.layout.addWidget(self.report_bar)

        # Multi-notification Stack: Stackable pills for reports and tasks with [✕]
        self.notification_scroll = QScrollArea()
        self.notification_scroll.setWidgetResizable(True)
        self.notification_scroll.setMaximumHeight(100)
        self.notification_scroll.setStyleSheet("""
            QScrollArea {
                background: #080B10;
                border: 1px dashed #1F2B42;
                border-radius: 6px;
            }
            QScrollBar:vertical {
                width: 6px;
                background: #080B10;
            }
            QScrollBar::handle:vertical {
                background: #00F0FF;
                border-radius: 3px;
            }
        """)
        self.notification_stack_widget = QWidget()
        self.notification_stack_widget.setStyleSheet("background: transparent;")
        self.notification_stack_layout = QVBoxLayout(self.notification_stack_widget)
        self.notification_stack_layout.setContentsMargins(4, 4, 4, 4)
        self.notification_stack_layout.setSpacing(4)
        self.notification_stack_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.notification_scroll.setWidget(self.notification_stack_widget)
        self.notification_scroll.setVisible(False)
        self.layout.addWidget(self.notification_scroll)

        # 2. Chat history browser
        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(False)
        self.chat_browser.anchorClicked.connect(self._on_anchor_clicked)
        self.chat_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {RT['surface_base']};
                border: 1px solid {RT['divider_soft']};
                border-radius: 10px;
                padding: 14px 16px;
                color: {RT['text_body']};
                font-family: {RT['font_body']};
                font-size: {RT['font_size_body']};
            }}
        """)
        # Faz 4 (2d/2f): sohbet gövdesi rapor okuyucu ve Agent Desk akış
        # paneliyle aynı tipografiyi kullanır. Belge stil sayfası verilmezse
        # komut kartı içindeki çıplak <table> (ör. /lint, /wiki çıktıları) Qt
        # varsayılanıyla, kalın beyaz kenarlıklarla çizilirdi.
        self.chat_browser.document().setDefaultStyleSheet(reading_css())
        self.layout.addWidget(self.chat_browser)
        self._load_chat_history()

        # 2b. Görev & Yetenek paneli için yer tutucu (içerik ilk açılışta kurulur;
        # ağır widget'lar sohbet açılışını yavaşlatmasın diye tembel yükleniyor).
        self.side_panel_container = QWidget()
        self.side_panel_container.setVisible(False)
        self.side_panel_layout = QVBoxLayout(self.side_panel_container)
        self.side_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.side_panel_layout.setSpacing(0)
        self.side_panel: Optional[QTabWidget] = None
        self._side_panel_open = False
        self.tasks_widget = None
        self.skills_widget = None
        self.layout.addWidget(self.side_panel_container)

        # 3. Staged image preview thumbnail bar
        self.attachment_bar = QFrame()
        self.attachment_bar.setVisible(False)
        self.attach_layout = QHBoxLayout(self.attachment_bar)
        self.attach_layout.setContentsMargins(4, 2, 4, 2)
        self.attach_label = QLabel()
        self.attach_label.setStyleSheet("color:#00F0FF; font-size:11px;")
        self.attach_layout.addWidget(self.attach_label)
        self.attach_layout.addStretch()
        remove_attach_btn = QPushButton("✕ Kaldır")
        remove_attach_btn.setFixedHeight(20)
        remove_attach_btn.clicked.connect(self._clear_staged_images)
        self.attach_layout.addWidget(remove_attach_btn)
        self.layout.addWidget(self.attachment_bar)

        # 4. Input layout
        input_bar = QHBoxLayout()
        self.input_field = ChatInputField(self)
        self.input_field.setPlaceholderText("Mesajınızı yazın veya Ctrl+V ile görsel yapıştırın...")
        self.input_field.returnPressed.connect(self._on_send)
        input_bar.addWidget(self.input_field)

        self.pdf_btn = QPushButton("📎 PDF")
        self.pdf_btn.setToolTip("Finansal Rapor veya PDF Belgesi Yükle")
        self.pdf_btn.setFixedHeight(28)
        self.pdf_btn.setStyleSheet("background-color:#141C2C; color:#00FF9D; border:1px solid #00FF9D; font-weight:bold; padding:2px 8px; border-radius:4px;")
        self.pdf_btn.clicked.connect(self._select_pdf_file)
        input_bar.addWidget(self.pdf_btn)

        self.send_btn = QPushButton("Gönder")
        self.send_btn.setStyleSheet("background-color:#00F0FF; color:#080B10; font-weight:bold;")
        self.send_btn.clicked.connect(self._on_send)
        input_bar.addWidget(self.send_btn)

        self.toggle_term_btn = QPushButton(">_ Terminal")
        self.toggle_term_btn.clicked.connect(self._toggle_terminal)
        input_bar.addWidget(self.toggle_term_btn)

        self.layout.addLayout(input_bar)

        # 5. Collapsible Terminal Drawer
        self.terminal_drawer = TerminalPaneWidget(title="Canlı AGY Akış Konsolu")
        self.terminal_drawer.setFixedHeight(190)
        self.terminal_drawer.setVisible(False)
        self.layout.addWidget(self.terminal_drawer)

        self._append_message("Entropy AI", "Hazır. Yerel Antigravity CLI üzerinden güvenle çalışıyorum.", is_system=True)

        # Yasam tarzi arayuz (Faz 5.5), Zen ile paralel:
        # Ctrl+Shift+F odak modu (yalnizca sohbet kalir),
        # Ctrl+K komut paleti (komut/yetenek/ajan/ofis/rapor).
        self.focus_mode = install_focus_mode(
            self,
            primary=self.chat_browser,
            secondary=[self.side_panel_container, self.terminal_drawer],
        )
        install_command_palette(self, on_activated=self._on_palette_activated)

    def _connect_signals(self):
        bus.model_detected.connect(self._update_model_badge)
        bus.token_usage_updated.connect(self._update_tokens)
        bus.agent_turn_started.connect(self._on_turn_started)
        bus.agent_turn_completed.connect(self._on_turn_completed)
        bus.token_chunk_received.connect(self._on_chunk)
        bus.report_created.connect(self._on_report_created)
        bus.task_notification.connect(self._on_task_notification)
        bus.project_changed.connect(self._on_project_changed)
        bus.skills_updated.connect(self._populate_skills_combo)
        # Zen ile aynı bus sinyalleri: durum, arka plan görevi ve damıtma ilerlemesi
        bus.core_state_changed.connect(self._update_state_badge)
        bus.task_triggered.connect(self._on_task_triggered)
        bus.task_completed.connect(self._on_task_completed)
        bus.distill_progress.connect(self._on_distill_progress)
        # Sohbet gecmisi tek kaynak: her iki mod ayni dosyayi dinler.
        bus.chat_history_updated.connect(self._on_chat_history_updated)
        bus.chat_history_cleared.connect(self._on_chat_history_cleared)
        bus.context_pressure.connect(self._on_context_pressure)

    # --------------------------------------------------- durum rozeti (Zen eşdeğeri)

    @Slot(str)
    def _update_state_badge(self, state: str):
        """Çekirdek durumunu başlıktaki rozete yansıtır (Zen'deki core_status_lbl karşılığı)."""
        mapping = {
            "thinking": ("🔵 DÜŞÜNÜYOR", "#00F0FF"),
            "executing": ("🟡 YÜRÜTÜLÜYOR", "#FFB300"),
            "error": ("🔴 HATA", "#FF4D4D"),
            "idle": ("🟢 HAZIR", "#00FF9D"),
        }
        text, color = mapping.get(state, mapping["idle"])
        self.state_badge.setText(text)
        self.state_badge.setStyleSheet(
            f"color:{color}; background:#05070A; border:1px solid #1F2B42; border-radius:4px;"
            " padding:2px 8px; font-size:10px; font-weight:bold;"
        )

    @Slot(str, str)
    def _on_task_triggered(self, task_id: str, task_name: str):
        self.state_badge.setText(f"⏰ GÖREV: {task_name[:18]}")
        self.state_badge.setToolTip(f"Arka plan görevi çalışıyor: {task_name} ({task_id})")

    @Slot(str, bool)
    def _on_task_completed(self, task_id: str, success: bool):
        self.state_badge.setText("🟢 HAZIR" if success else "🔴 GÖREV HATASI")
        self.state_badge.setToolTip("Entropy AI çekirdek durumu")

    @Slot(str, int, int)
    def _on_distill_progress(self, skill_name: str, done: int, total: int):
        self.state_badge.setText(f"📘 DAMITMA {done}/{total}")
        self.state_badge.setToolTip(f"'{skill_name}' için yordam damıtma sürüyor: {done}/{total} rapor")

    # ------------------------------------------------ görev & yetenek paneli

    def ensure_side_panel(self) -> QTabWidget:
        """Görev ve yetenek sekmelerini (tembel) kurar ve döndürür."""
        if self.side_panel is None:
            from entropy.ui.widgets.skills_widget import SkillsWidget
            from entropy.ui.widgets.tasks_widget import TasksWidget

            from entropy.ui.widgets.agents_widget import AgentsWidget
            from entropy.ui.widgets.task_board_widget import CompactTaskListWidget

            self.side_panel = QTabWidget()
            self.side_panel.setMaximumHeight(280)
            self.tasks_widget = TasksWidget(parent=self, bridge=self.bridge)
            self.skills_widget = SkillsWidget(bridge=self.bridge)
            self.agents_widget = AgentsWidget(bridge=self.bridge, compact=True)
            self.agent_tasks_widget = CompactTaskListWidget()
            self.side_panel.addTab(self.tasks_widget, "⏰ Görevler")
            self.side_panel.addTab(self.skills_widget, "🎯 Yetenekler")
            self.side_panel.addTab(self.agents_widget, "🤖 Ajanlar")
            self.side_panel.addTab(self.agent_tasks_widget, "🗂 Ajan Görevleri")

            # Kompakt "Gelen" listesi: Zen'deki şeridin aynısı, Chat panelinde.
            # Chat'te rapor okuyucu yok; girdiler kasadan doğrudan toplanır ve
            # bir rapora tıklanınca ayrı rapor penceresinde açılır.
            self.inbox_strip = ReportInboxStrip(parent=self)
            self.inbox_strip.set_entries(collect_recent_entries())
            self.inbox_strip.report_opened.connect(self._open_inbox_report)
            self.inbox_strip.unread_changed.connect(self._on_inbox_unread_changed)
            self.inbox_strip.setVisible(False)

            # Faz 5.5: "Gelen" sekmesi Rapor Merkezi'dir (kumeleme + digest +
            # onem x aciliyet + guven esigi). Zen ile paralel; deposu seritle
            # ortak, boylece okundu/pin/arsiv iki yuzeyde ayni.
            self.report_center = ReportCenterWidget(
                parent=self, store=self.inbox_strip.store, bridge=self.bridge
            )
            self.report_center.set_entries(collect_recent_entries())
            self.report_center.report_opened.connect(self._open_inbox_report)
            self.report_center.unread_changed.connect(self._on_inbox_unread_changed)
            self.report_center.orchestrator_answer.connect(self._on_orchestrator_answer)
            self.side_panel.addTab(self.report_center, "📥 Gelen")

            self.timeline_panel = TimelinePanel()
            self.timeline_panel.event_activated.connect(self._on_timeline_activated)
            self.side_panel.addTab(self.timeline_panel, "🗓 Bugun")

            self.notification_center = NotificationCenter()
            self.notification_center.notification_activated.connect(
                self._on_notification_activated
            )
            self.side_panel.addTab(self.notification_center, "🔔 Bildirimler")
            self.side_panel_layout.addWidget(self.side_panel)
        return self.side_panel

    @Slot(str, str)
    def _on_orchestrator_answer(self, office: str, body: str):
        """
        "Orkestratore sor" yaniti sohbete "🏢 <ofis>" balonuyla duser.

        Yanit sohbete yazilir cunku bu bir diyalogdur: kullanicinin sorusu ve
        ofisin cevabi ayni akista kalmali, kartin icinde kaybolmamali.
        """
        from entropy.ui.widgets.markdown_renderer import build_chat_bubble_html

        self.chat_browser.append(
            build_chat_bubble_html(f"🏢 {office}", str(body or ""))
        )

    @Slot(str, str, str)
    def _on_palette_activated(self, kind: str, payload: str, label: str):
        """Komut paleti secimi: rapor acilir, kalan her sey giris satirina yazilir."""
        if kind == "report":
            self._open_inbox_report(payload)
            return
        self.input_field.setText(payload if payload.endswith(" ") else payload + " ")
        self.input_field.setFocus()

    @Slot(str, str)
    def _on_timeline_activated(self, kind: str, target: str):
        if kind in ("report", "handoff") and target:
            self._open_inbox_report(target)

    @Slot(str, str)
    def _on_notification_activated(self, target_kind: str, target: str):
        if target_kind == "report" and target:
            self._open_inbox_report(target)

    @Slot(str)
    def _on_provider_login_requested(self, provider: str):
        self.input_field.setText(f"/login {provider} ")
        self.input_field.setFocus()

    @Slot(int)
    def _on_inbox_unread(self, count: int):
        """Rapor Merkezi rozetini günceller (QObject slotu, lambda değil)."""
        if hasattr(self, "inbox_badge"):
            self.inbox_badge.set_count(count)

    @Slot(int)
    def _on_inbox_unread_changed(self, count: int):
        """Kompakt şeritteki değişimi diğer pencerelere duyurur."""
        try:
            bus.report_inbox_unread.emit(int(count))
        except (AttributeError, RuntimeError):
            pass

    @Slot(str)
    def _open_inbox_report(self, path: str):
        """Gelen şeridinden seçilen raporu ayrı rapor penceresinde açar."""
        if not path:
            return
        try:
            from entropy.ui.widgets.standalone_report_window import (
                open_standalone_report_window,
            )

            self._inbox_report_window = open_standalone_report_window(str(path), parent=self)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Rapor Merkezi] Rapor açılamadı: {exc}\n")

    def toggle_side_panel(self):
        """Paneli açar/kapatır; ilk açılışta sekmeleri kurar.

        Durum açık bir bayrakla tutulur: pencere gizliyken (mod değişimi) alt
        widget'ların isVisible() değeri her zaman False döner ve düğme kilitlenirdi.
        """
        will_show = not self._side_panel_open
        self._side_panel_open = will_show
        if will_show:
            self.ensure_side_panel()
        self.side_panel_container.setVisible(will_show)
        self.panel_btn.setText("▼ Paneli Kapat" if will_show else "🧩 Panel")
        return will_show

    def add_notification_pill(self, title: str, path_or_content: str, is_task: bool = False):
        """Add a stackable notification pill to the chat mode window (yinelenenler elenir)."""
        for i in range(self.notification_stack_layout.count()):
            item = self.notification_stack_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, NotificationPillWidget):
                if getattr(widget, "path_or_content", None) == path_or_content:
                    return
        self.notification_scroll.setVisible(True)
        pill = NotificationPillWidget(
            title=title,
            path_or_content=path_or_content,
            is_task=is_task,
            on_open=self._open_report_path,
            on_dismiss=self._remove_notification_pill,
            parent=self.notification_stack_widget
        )
        self.notification_stack_layout.addWidget(pill)

    def _remove_notification_pill(self, pill: NotificationPillWidget):
        """Dismiss and remove a specific notification pill."""
        self.notification_stack_layout.removeWidget(pill)
        pill.deleteLater()
        if self.notification_stack_layout.count() == 0:
            self.notification_scroll.setVisible(False)

    @Slot(str)
    def _on_report_created(self, path_str: str):
        """Display notification in chat and top bar when a research report is compiled with deduplication."""
        p = Path(path_str)
        self.latest_report_path = str(p)

        import time
        now = time.time()
        if not hasattr(self, "_recent_notifications"):
            self._recent_notifications = {}
        self._recent_notifications = {k: v for k, v in self._recent_notifications.items() if now - v < 10.0}
        norm_key = str(p.resolve()).lower()
        if norm_key in self._recent_notifications:
            return
        self._recent_notifications[norm_key] = now

        self.report_bar_lbl.setText(f"<span style='color:#00FF9D; font-weight:bold;'>📑 Yeni Rapor:</span> <span style='color:#F0F6FC;'>{p.stem}</span>")
        self.report_bar.setVisible(True)
        # Zen ile aynı davranış: rapor da yığılabilir bir bildirim pili üretir.
        self.add_notification_pill(title=p.stem, path_or_content=str(p), is_task=False)

        card_html = (
            f"<div style='background-color:#0E1420; border:1px solid #00F0FF; border-radius:8px; padding:10px 14px; margin:8px 0;'>"
            f"<div style='color:#00F0FF; font-size:11px; font-weight:bold; letter-spacing:0.8px;'>📑 Yeni Araştırma Raporu Oluşturuldu</div>"
            f"<div style='color:#F0F6FC; font-size:13px; font-weight:bold; margin:4px 0;'>{p.stem}</div>"
            f"<div style='color:#8B949E; font-size:11px; margin-bottom:8px;'>Dosya: {p.name} | Bilişsel Hafıza ve RAG'a İşlendi</div>"
            f"<a href='entropy-report://{p.as_posix()}' style='display:inline-block; background-color:#00F0FF; color:#080B10; font-weight:bold; font-size:11px; text-decoration:none; padding:5px 14px; border-radius:4px;'>📖 Raporu Aç ve Oku ↗</a>"
            f"</div>"
        )
        self.chat_browser.append(card_html)

    @Slot(str, str, str)
    def _on_task_notification(self, task_id: str, task_name: str, path_or_content: str):
        """Handle task execution and result notification in chat mode with deduplication."""
        import time
        now = time.time()
        if not hasattr(self, "_recent_notifications"):
            self._recent_notifications = {}
        self._recent_notifications = {k: v for k, v in self._recent_notifications.items() if now - v < 10.0}
        norm_key = str(Path(path_or_content).resolve()).lower() if path_or_content.endswith(".md") else f"task:{task_id}"
        if norm_key in self._recent_notifications:
            return
        self._recent_notifications[norm_key] = now

        self.add_notification_pill(title=task_name, path_or_content=path_or_content, is_task=True)

        card_html = (
            f"<div style='background-color:#0E1420; border:1px solid #00FF9D; border-radius:8px; padding:10px 14px; margin:8px 0;'>"
            f"<div style='color:#00FF9D; font-size:11px; font-weight:bold; letter-spacing:0.8px;'>⏰ OTONOM PLANLI GÖREV ÇALIŞTIRILDI</div>"
            f"<div style='color:#F0F6FC; font-size:13px; font-weight:bold; margin:4px 0;'>{task_name}</div>"
            f"<div style='color:#8B949E; font-size:11px; margin-bottom:8px;'>Görev Kimliği: {task_id}</div>"
        )
        if path_or_content.endswith(".md"):
            p = Path(path_or_content)
            card_html += f"<a href='entropy-report://{p.as_posix()}' style='display:inline-block; background-color:#00FF9D; color:#080B10; font-weight:bold; font-size:11px; text-decoration:none; padding:5px 14px; border-radius:4px;'>📖 Görev Raporunu Aç ↗</a>"
        card_html += "</div>"
        self.chat_browser.append(card_html)

    def _on_anchor_clicked(self, url):
        """Intercept entropy-report:// links to open the standalone viewer."""
        url_str = url.toString()
        if "entropy-report://" in url_str:
            target = url_str.split("entropy-report://")[-1]
            self._open_report_path(target)
        elif url_str.startswith("http://") or url_str.startswith("https://"):
            import webbrowser
            webbrowser.open(url_str)

    def _open_reports_window(self):
        """Open the dedicated standalone report reader window."""
        if not hasattr(self, "_report_window") or self._report_window is None:
            from entropy.ui.widgets.standalone_report_window import StandaloneReportWindow
            self._report_window = StandaloneReportWindow()
        self._report_window.show()
        self._report_window.raise_()
        self._report_window.activateWindow()

    def _open_report_path(self, path_str: str):
        """Open the standalone report window focused on a specific report."""
        if not hasattr(self, "_report_window") or self._report_window is None:
            from entropy.ui.widgets.standalone_report_window import StandaloneReportWindow
            self._report_window = StandaloneReportWindow()
        self._report_window.open_report_file(path_str)

    def _open_latest_report(self):
        if hasattr(self, "latest_report_path") and self.latest_report_path:
            self._open_report_path(self.latest_report_path)
        else:
            self._open_reports_window()

    def _handle_desk_command(self, prompt: str) -> str:
        """
        `/desk` ve `/desk task …` komutunu işler ve çıktıyı okunur kart olarak basar.

        Komutun mantığı (ofise kart açma) agy ajanının `slash_commands`
        işleyicisinde; burada yalnızca sunum var. İşleyici henüz yoksa panel
        kullanım özetini gösterir — komut sessizce AGY'ye gitmesin diye.
        """
        from entropy.ui.widgets.markdown_renderer import build_command_card_html

        body = None
        try:
            from entropy.core.slash_commands import try_handle_local_command

            body = try_handle_local_command(prompt, self.bridge)
        except Exception as exc:
            body = f"<b style='color:#FF6B6B;'>/desk hatası:</b> {html.escape(str(exc))}"

        opened = False
        if prompt.strip() == "/desk":
            opened = self.open_agent_desk() is not None

        if body is None:
            body = (
                "<b style='color:#C084FC;'>🏢 Agent Desk</b><br/>"
                + ("Ofis penceresi açıldı.<br/>" if opened else "")
                + "<span style='color:#8B949E;'>Kullanım: "
                "<code>/desk</code> pencereyi açar · "
                "<code>/desk task &lt;ofis&gt; &lt;başlık&gt; :: &lt;hedef&gt;</code> "
                "ofise kart verir.</span>"
            )
        card = build_command_card_html(body)
        self.chat_browser.append(card)
        return card

    def open_agent_desk(self):
        """Agent Desk penceresini açar (tek örnek; açıksa öne getirir)."""
        try:
            from entropy.desk.window import open_desk_window

            return open_desk_window(parent=None, bridge=self.bridge)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Agent Desk] Pencere açılamadı: {exc}\n")
            return None

    def _select_project_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Proje Klasörü Seç", str(self.bridge.active_project_dir))
        if folder:
            self.bridge.set_project_directory(folder)

    def _on_project_changed(self, new_dir: str):
        if hasattr(self, "project_btn"):
            self.project_btn.setText(f"📁 {Path(new_dir).name}")
            self.project_btn.setToolTip(f"Aktif Proje: {new_dir}\nDeğiştirmek için tıklayın.")
        self._populate_skills_combo()

    def _populate_skills_combo(self):
        curr = self.skill_combo.currentData() if hasattr(self, "skill_combo") else "auto"
        self.skill_combo.blockSignals(True)
        self.skill_combo.clear()
        self.skill_combo.addItem("🎯 Yetenek: Otomatik", "auto")
        try:
            sm = SkillManager(project_dir=self.bridge.active_project_dir)
            for s in sm.list_skills():
                if s.enabled:
                    self.skill_combo.addItem(f"🎯 {s.name}", s.name)
        except Exception:
            pass
        idx = self.skill_combo.findData(curr)

        if idx >= 0:
            self.skill_combo.setCurrentIndex(idx)
        self.skill_combo.blockSignals(False)

    def _select_pdf_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "PDF Belgesi Seç", str(self.bridge.active_project_dir), "PDF Dosyaları (*.pdf)"
        )
        if file_path:
            self.stage_pdf_file(file_path)

    def stage_pdf_file(self, path_str: str):
        if path_str not in self.staged_pdfs:
            self.staged_pdfs.append(path_str)
        self._update_attachment_banner()

    def _update_attachment_banner(self):
        parts = []
        if self.staged_pdfs:
            pdf_descs = []
            for p_str in self.staged_pdfs:
                p = Path(p_str)
                page_info = ""
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(p_str)
                    page_info = f" ({len(reader.pages)} Sayfa)"
                except Exception:
                    pass
                pdf_descs.append(f"<b>{p.name}</b>{page_info}")
            parts.append(f"📄 Eklenen PDF: " + ", ".join(pdf_descs))
        if self.staged_images:
            parts.append(f"📎 Eklenen Görsel: " + ", ".join([f"<b>{Path(p).name}</b>" for p in self.staged_images]))
        if parts:
            self.attach_label.setText(" | ".join(parts))
            self.attachment_bar.setVisible(True)
        else:
            self.attachment_bar.setVisible(False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                local_path = url.toLocalFile()
                if not local_path:
                    continue
                lp_lower = local_path.lower()
                if lp_lower.endswith(".pdf"):
                    self.stage_pdf_file(local_path)
                elif lp_lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    self.staged_images.append(local_path)
                    self._update_attachment_banner()
                elif lp_lower.endswith((".zip", "skill.md", ".md")) or Path(local_path).is_dir():
                    sm = SkillManager(project_dir=self.bridge.active_project_dir)
                    imported = sm.import_skill_from_source(local_path)
                    if imported:
                        self._populate_skills_combo()
                        idx = self.skill_combo.findData(imported.name)
                        if idx >= 0:
                            self.skill_combo.setCurrentIndex(idx)
                        self._append_message("Entropy AI", f"🎯 <b>Yetenek Başarıyla Yüklendi:</b> '{imported.name}' sisteme entegre edildi.", is_system=True)

        elif event.mimeData().hasText():
            text = event.mimeData().text().strip()
            if (text.startswith("http://") or text.startswith("https://")) and ("github.com" in text or text.endswith(".md") or text.endswith(".zip")):
                sm = SkillManager(project_dir=self.bridge.active_project_dir)
                imported = sm.import_skill_from_source(text)
                if imported:
                    self._populate_skills_combo()
                    idx = self.skill_combo.findData(imported.name)
                    if idx >= 0:
                        self.skill_combo.setCurrentIndex(idx)
                    self._append_message("Entropy AI", f"🎯 <b>Yetenek URL'den Yüklendi:</b> '{imported.name}' sisteme entegre edildi.", is_system=True)

    def try_paste_image(self) -> bool:
        """Handle Ctrl+V image detection and staging."""
        res = self.clipboard_handler.save_clipboard_image()
        if res:
            path_str, w, h = res
            self.staged_images.append(path_str)
            self._update_attachment_banner()
            return True
        return False

    def _clear_staged_images(self):
        self.staged_images.clear()
        self.staged_pdfs.clear()
        self.attachment_bar.setVisible(False)

    def _toggle_terminal(self):
        is_vis = not self.terminal_drawer.isVisible()
        self.terminal_drawer.setVisible(is_vis)
        self.toggle_term_btn.setText("▼ Terminali Kapat" if is_vis else ">_ Terminal")

    def _on_new_chat(self):
        """Sohbeti yalnızca burada, kullanıcının açık isteğiyle sıfırlar (arşivleyerek)."""
        self.bridge.reset_conversation()  # arşivler + bus.chat_history_cleared yayar

    @Slot()
    def _on_chat_history_cleared(self):
        """Sohbet arşivlendi: ekranı temizle (hangi pencerede basıldığı fark etmez)."""
        self.chat_browser.clear()
        self._history_signature = config_module.chat_history_signature()
        self._append_message(
            "Entropy AI",
            "Yeni sohbet oturumu başlatıldı. Önceki sohbet arşive alındı.",
            is_system=True,
        )

    @Slot()
    def _on_chat_history_updated(self):
        """
        Diske yeni tur yazıldı.

        Pencere görünürse akış zaten ekrana yazıldı; yalnızca imza tazelenir.
        Gizliyse imza eski bırakılır ki bir sonraki gösterimde yeniden yüklensin.
        """
        if self.isVisible():
            self._history_signature = config_module.chat_history_signature()

    def _load_chat_history(self):
        """Sohbet görünümünü diskteki tek kaynaktan bütünüyle yeniden kurar."""
        self.chat_browser.clear()
        for msg in config_module.load_chat_history():
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            sender = "Siz" if msg.get("role") == "user" else "Entropy AI"
            self._append_message(sender, content)
        self._history_signature = config_module.chat_history_signature()
        if self.chat_browser.toPlainText().strip() == "":
            self._append_message("Entropy AI", "Sistem aktif. Size nasıl yardımcı olabilirim?", is_system=True)

    def _reload_chat_history_if_stale(self):
        """
        Pencere yeniden gösterildiğinde geçmiş bayatsa yeniden yükler.

        Mod değişiminde pencereler yok edilmiyor, yalnızca gizleniyordu; her mod
        geçmişi bir kez (kuruluşta) okuduğu için diğer modda yazılan turlar
        görünmüyor, kullanıcıya "sohbet silinmiş" gibi geliyordu.
        """
        if getattr(self.bridge, "is_running", False) or getattr(self, "_streaming_active", False):
            return  # akış sürerken yeniden kurma: yarım yanıt silinmesin
        if config_module.chat_history_signature() != getattr(self, "_history_signature", None):
            self._load_chat_history()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self._reload_chat_history_if_stale()
        except Exception:
            pass

    @Slot(str)
    def _update_model_badge(self, model_name: str):
        if self.model_combo.currentText() != model_name:
            self.model_combo.setCurrentText(model_name)

    def _on_model_selected(self, model_name: str):
        if model_name and model_name != self.bridge.selected_model:
            self.bridge.set_model(model_name)

    def _on_provider_selected(self, provider: str):
        """Sağlayıcı listesinden seçim: köprüyü yönetici üzerinden değiştirir."""
        if not provider or provider == getattr(self.bridge, "provider_name", "agy"):
            return
        from entropy.ui.manager import EntropyUIManager

        manager = EntropyUIManager.instance
        if manager is None:
            return
        manager.switch_provider(provider)

    def refresh_provider_ui(self):
        """Köprü değiştikten sonra üst çubuğu tazeler (model listesi + seçim)."""
        try:
            self.provider_combo.blockSignals(True)
            self.provider_combo.setCurrentText(getattr(self.bridge, "provider_name", "agy"))
        finally:
            self.provider_combo.blockSignals(False)
        try:
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            for m in self.bridge.fetch_available_models():
                self.model_combo.addItem(m)
            self.model_combo.setCurrentText(self.bridge.selected_model)
            apply_model_placeholder(self.model_combo)
        finally:
            self.model_combo.blockSignals(False)

    @Slot(int)
    def _update_tokens(self, tokens: int):
        # Sohbet ve arka plan kalemleri ayrı; biçim zen_mode ile ortak.
        from entropy.ui.widgets.token_badge import format_token_badge

        text, tip = format_token_badge(self.bridge)
        self.tokens_badge.setText(text)
        self.tokens_badge.setToolTip(tip)
        self._apply_context_badge()

    @Slot(float)
    def _on_context_pressure(self, ratio: float):
        """Baskı sinyali: son bilinen oranı saklar ve rozeti tazeler."""
        self._last_context_pressure = float(ratio or 0.0)
        self._apply_context_badge()

    def _apply_context_badge(self):
        """Bağlam doluluk rozeti — Zen ile ortak biçimlendirici, ortak eşik."""
        from entropy.ui.widgets.token_badge import format_context_badge

        if not hasattr(self, "context_badge"):
            return
        text, tip, color = format_context_badge(
            self.bridge, getattr(self, "_last_context_pressure", 0.0)
        )
        self.context_badge.setText(text)
        self.context_badge.setToolTip(tip)
        self.context_badge.setStyleSheet(
            f"color:{color}; font-family:'Consolas'; font-size:11px; font-weight:bold;"
        )

    def _on_send(self):
        import html
        prompt = self.input_field.text().strip()
        if not prompt and not self.staged_images and not self.staged_pdfs:
            return

        # Check if the user is asking to import/install a skill directly from URL or repo
        from entropy.skills.manager import extract_skill_source_from_text
        skill_src = extract_skill_source_from_text(prompt)
        if skill_src:
            sm = SkillManager(project_dir=self.bridge.active_project_dir)
            imported = sm.import_skill_from_source(skill_src)
            if imported:
                self._populate_skills_combo()
                idx = self.skill_combo.findData(imported.name)
                if idx >= 0:
                    self.skill_combo.setCurrentIndex(idx)
                self._append_message("Entropy AI", f"🎯 <b>Yetenek Sisteme Kuruldu:</b> '{imported.name}' başarıyla kuruldu ve seçildi.", is_system=True)

        # Check slash command handling (supports multiple slash commands in prompt)
        matched_cmds = []
        slash_tokens = re.findall(r'(?:^|\s)/([a-zA-Z0-9_\-:]+)', prompt)

        if slash_tokens and prompt.strip().startswith("/desk"):
            # /desk yerel bir komut: AGY'ye gitmez. Çıktısı okunur kart olarak
            # basılır; argümansız "/desk" ayrıca ofis penceresini açar.
            self._handle_desk_command(prompt.strip())
            self.input_field.clear()
            return

        if slash_tokens:
            # Uygulama içinde yürütülen komutlar (AGY'ye gitmez); zen_mode ile aynı işleyici.
            from entropy.core.slash_commands import try_handle_local_command
            local_html = try_handle_local_command(prompt, self.bridge)
            if local_html is not None:
                # Yerel komut çıktısı (ör. /handoff) okunur kart olarak basılır.
                from entropy.ui.widgets.markdown_renderer import build_command_card_html

                self.chat_browser.append(build_command_card_html(local_html))
                self.input_field.clear()
                return

            if len(slash_tokens) == 1 and prompt.strip() == f"/{slash_tokens[0]}":
                single_tok = slash_tokens[0]
                if single_tok == "clear":
                    self.chat_browser.clear()
                    self._append_message("Entropy AI", "Sohbet ekranı sıfırlandı.", is_system=True)
                    self.input_field.clear()
                    return
                elif single_tok == "help":
                    reg = SlashCommandRegistry(mcp_manager=default_mcp_manager)
                    all_c = reg.get_all_commands(self.bridge.active_project_dir)
                    help_html = [
                        "<div style='border:1px solid #1F2B42; background:#0A0E17; border-radius:6px; padding:10px; margin:6px 0;'>",
                        "<b style='color:#00F0FF; font-size:12px;'>⚡ KULLANILABİLİR KOMUTLAR, YETENEKLER VE MCP ARAÇLARI</b><br/><br/>"
                    ]
                    for c in all_c:
                        help_html.append(
                            f"<div style='margin-bottom:4px;'>"
                            f"<span style='background-color:{c.color}22; color:{c.color}; border:1px solid {c.color}55; border-radius:3px; padding:1px 5px; font-size:9px; font-weight:bold;'>{c.badge}</span> "
                            f"<b style='color:#F0F6FC; font-family:Consolas;'>{c.name}</b>: "
                            f"<span style='color:#8B949E; font-size:11px;'>{c.description}</span>"
                            f"</div>"
                        )
                    help_html.append("</div>")
                    self._append_message("Entropy AI", "".join(help_html), is_system=True)
                    self.input_field.clear()
                    return

            reg = SlashCommandRegistry(mcp_manager=default_mcp_manager)
            all_c = reg.get_all_commands(self.bridge.active_project_dir)
            cmds_by_token = {c.name[1:].lower() if c.name.startswith("/") else c.name.lower(): c for c in all_c}

            for tok in slash_tokens:
                c = cmds_by_token.get(tok.lower())
                if c and c not in matched_cmds:
                    matched_cmds.append(c)
                    if c.category == "skill":
                        chosen_skill_name = c.metadata.get("skill_name") or tok
                        idx = self.skill_combo.findData(chosen_skill_name)
                        if idx >= 0:
                            self.skill_combo.setCurrentIndex(idx)

        chosen_skill = self.skill_combo.currentData()
        escaped_prompt = html.escape(prompt).replace('\n', '<br/>')
        display_prompt = escaped_prompt

        badge_html = ""
        badge_spans = []
        if matched_cmds:
            for mc in matched_cmds:
                badge_spans.append(
                    f"<span style='background:#0E1420; color:{mc.color}; border:1px solid {mc.color}55; border-radius:3px; padding:2px 8px; font-size:10px; font-weight:bold; margin-right:4px;'>{mc.badge}: {html.escape(mc.name)}</span>"
                )
        skill_already_badged = any(mc.category == "skill" and (mc.metadata.get("skill_name") == chosen_skill or mc.name.lstrip("/") == chosen_skill) for mc in matched_cmds)
        if chosen_skill and chosen_skill != "auto" and not skill_already_badged:
            badge_spans.append(
                f"<span style='background:#0E1420; color:#00FF9D; border:1px solid #1F2B42; border-radius:3px; padding:2px 8px; font-size:10px; font-weight:bold; margin-right:4px;'>🎯 Yetenek: {html.escape(chosen_skill)}</span>"
            )
        if badge_spans:
            badge_html = f"<div style='margin-bottom:4px;'>{' '.join(badge_spans)}</div>"

        if badge_html:
            display_prompt = f"{badge_html}<div>{escaped_prompt}</div>"

        if self.staged_images:
            img_names = ", ".join([html.escape(Path(p).name) for p in self.staged_images])
            display_prompt += f" <div style='color:#00F0FF; font-size:11px; margin-top:4px;'><i>[Eklenen Görsel: {img_names}]</i></div>"
        if self.staged_pdfs:
            pdf_names = ", ".join([html.escape(Path(p).name) for p in self.staged_pdfs])
            display_prompt += f" <div style='color:#00FF9D; font-size:11px; margin-top:4px;'><i>[Eklenen PDF: {pdf_names}]</i></div>"

        self._append_message("Siz", display_prompt)
        self.input_field.clear()

        images_to_send = list(self.staged_images)
        pdfs_to_send = list(self.staged_pdfs)
        self._clear_staged_images()

        actual_prompt = prompt
        if images_to_send:
            actual_prompt += "\n" + "\n".join([f"[Eklenen Görsel Dosyası: {p}]" for p in images_to_send])

        if self.bridge.is_running:
            self._append_message("Entropy AI", "⏳ <i>Önceki işlem tamamlanıyor, mesajınız sıraya alındı ve hemen ardından yanıtlanacak...</i>", is_system=True)

        has_plan = any(c.name == "/plan" for c in matched_cmds) or bool(re.search(r'(?:^|\s)/plan\b', prompt, re.IGNORECASE))
        exec_mode = "plan" if has_plan else "accept-edits"
        self.bridge.send_prompt_async(
            prompt=actual_prompt,
            image_attachments=images_to_send,
            pdf_attachments=pdfs_to_send,
            active_skill=chosen_skill,
            mode=exec_mode
        )

    def _on_turn_started(self, prompt: str):
        self.send_btn.setEnabled(False)
        self.input_field.setEnabled(False)
        self._streaming_active = True
        self.terminal_drawer.setVisible(True)
        self.toggle_term_btn.setText("▼ Terminali Kapat")
        self.chat_browser.append("<div style='margin-bottom:8px;'><b style='color:#00F0FF;'>Entropy AI:</b><br/></div>")
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)

    def _on_chunk(self, chunk: str):
        if getattr(self, "_streaming_active", False):
            cursor = self.chat_browser.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(chunk)
            self.chat_browser.setTextCursor(cursor)
            self.chat_browser.ensureCursorVisible()

    def _on_turn_completed(self, full_response: str):
        self._streaming_active = False
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.chat_browser.append("<div style='margin-bottom:12px;'></div>")
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)

    def _append_message(self, sender: str, text: str, is_system: bool = False):
        """Sohbet balonu üretir (Zen paneliyle aynı tasarım sistemi)."""
        self.chat_browser.append(build_chat_bubble_html(sender, text, is_system=is_system))
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event):
        signals = [
            (bus.model_detected, self._update_model_badge),
            (bus.token_usage_updated, self._update_tokens),
            (bus.agent_turn_started, self._on_turn_started),
            (bus.agent_turn_completed, self._on_turn_completed),
            (bus.token_chunk_received, self._on_chunk),
            (bus.report_created, self._on_report_created),
            (bus.task_notification, self._on_task_notification),
            (bus.project_changed, self._on_project_changed),
            (bus.skills_updated, self._populate_skills_combo),
            (bus.core_state_changed, self._update_state_badge),
            (bus.task_triggered, self._on_task_triggered),
            (bus.task_completed, self._on_task_completed),
            (bus.distill_progress, self._on_distill_progress),
            (bus.chat_history_updated, self._on_chat_history_updated),
            (bus.chat_history_cleared, self._on_chat_history_cleared),
        ]
        for sig, slot in signals:
            try:
                sig.disconnect(slot)
            except Exception:
                pass

        # Panel çocukları bilerek kapatılmaz: TasksWidget.closeEvent tekil
        # zamanlayıcıyı durdurur; Chat penceresi kapanınca Zen'in arka plan
        # görevleri de sessizce dururdu. Pencere yok edilirken Qt bu widget'ların
        # bus bağlantılarını zaten koparır.
        super().closeEvent(event)

