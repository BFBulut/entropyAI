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
# Gömülü HTML gövdelerinin renk kaynağı (Faz 12-D.2): düz onaltılık yerine
# `TOKENS`/`TOKENS["viz"]` köprüsü. Bkz. `entropy.ui.design.embedded`.
from entropy.ui.design.embedded import live_palette as _live_palette

# Faz 12-F: canli palet — tema degisince gomulu govdeler de doner.
_P = _live_palette()
# entropy.core paketi 'config' adini config NESNESINE baglar; sohbet
# gecmisi yardimcilari icin gercek modul gerekiyor.
config_module = _sys.modules["entropy.core.config"]
from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.ui.widgets.report_card_bridge import ReportCardMixin
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.platform.clipboard import ClipboardImageHandler
from entropy.skills.manager import SkillManager
from entropy.ui.themes.cyber_theme import CYBER_THEME, READING_TOKENS as RT, reading_css
from entropy.ui.design import TOKENS
from entropy.ui.widgets.command_palette import install_command_palette
from entropy.ui.widgets.header_bar import (
    BrandCluster, ModelCapsule, PaletteButton, StatusCluster,
    context_badge_tone, make_icon_button, repolish as _repolish,
)
from entropy.ui.widgets.focus_mode import install_focus_mode
from entropy.ui.widgets.notification_center import NotificationCenter
from entropy.ui.widgets.flow_layout import FlowHeaderFrame, fit_combo_to_contents
from entropy.ui.widgets.provider_badge import ProviderStatusBadge
from entropy.ui.widgets.report_center import ReportCenterWidget
from entropy.ui.widgets.timeline_panel import TimelinePanel
from entropy.ui.widgets.report_inbox import (
    InboxBadge, ReportInboxStrip, collect_recent_entries,
)
from entropy.ui.widgets.effort_selector import install_effort_selector
from entropy.ui.widgets.ui_polish import apply_model_placeholder, emoji_or_text
from entropy.ui.widgets.markdown_renderer import build_chat_bubble_html, render_markdown_to_html
from entropy.ui.window_sizing import fit_window_to_screen
from entropy.core.slash_commands import SlashCommandRegistry, invalidate_command_cache
from entropy.mcp.manager import default_mcp_manager
from entropy.ui.widgets.notification_pill import NotificationPillWidget
from entropy.ui.widgets.slash_command_popup import SlashCommandPopupWidget
from entropy.ui.widgets.slash_prompt import (
    CLI_PASSTHROUGH, close_matches, strip_skill_tokens, unknown_slash_html,
    unknown_slash_token,
)
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
        # Faz 8: tekrar kapanislarda "Failed to disconnect" uyarisi uretmesin.
        if getattr(self, "_catalog_connected", True):
            self._catalog_connected = False
            for sig in (bus.skills_updated, bus.mcp_servers_updated):
                try:
                    sig.disconnect(self._on_command_catalog_changed)
                except Exception:
                    pass
        super().closeEvent(event)


# Faz 6: sohbet penceresi 1366x768 ekranda rahatca yer alsin.
CHAT_MIN_SIZE = (460, 520)
CHAT_PREFERRED_SIZE = (620, 820)
CHAT_SCREEN_RATIO = 0.92


class ChatModeWindow(ReportCardMixin, QMainWindow):
    """Floating Chat Mode with real-time streaming, terminal drawer, and Ctrl+V images."""

    def __init__(self, bridge: AgyProcessBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.clipboard_handler = ClipboardImageHandler()
        self.staged_images: List[str] = []
        self.staged_pdfs: List[str] = []

        # Faz 11-E adım 2: stil uygulama düzeyinde tek girişten gelir
        # (`ui/manager.py` -> `apply_design_system(app)`).
        self.setWindowTitle("Entropy AI Chat")
        # Faz 6: sabit 540x700 yerine kullanilabilir alana gore boyut; kucuk
        # ekranlarda pencere gorev cubugunun altina tasmasin.
        self.setMinimumSize(*CHAT_MIN_SIZE)
        self.resize(*CHAT_PREFERRED_SIZE)
        fit_window_to_screen(self, ratio=CHAT_SCREEN_RATIO,
                             min_size=CHAT_MIN_SIZE, keep_preferred=True)
        self.setAcceptDrops(True)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(6)

        # 1. Üst çubuk — Faz 11-E adım 2/4: 15+ öğe → 4 (+ pencere yok, Chat
        # sistem başlık çubuğunu kullanır). Kaldırılan düğmeler (Desk, Proje,
        # Yeni, Raporlar, Panel, Zen) komut paletine taşındı.
        header = FlowHeaderFrame(margins=(10, 6, 10, 6))
        h_layout = header.flow()

        # (1) Marka + durum noktası + kip anahtarı
        self.brand = BrandCluster(current_mode="chat")
        h_layout.addWidget(self.brand)
        # Zen'deki `state_badge` karşılığı: durum artık tek noktada.
        self.state_badge = self.brand.status_dot

        h_layout.addStretch()

        # (2) Sağlayıcı / model / efor / yetenek tek kapsülde
        self.model_capsule = ModelCapsule()
        self.provider_combo = QComboBox()
        self.provider_combo.setAccessibleName("Sağlayıcı (CLI): agy = Antigravity, claude = Claude Code")
        self.provider_combo.setToolTip("Sağlayıcı (CLI): agy = Antigravity, claude = Claude Code")
        from entropy.core.provider import PROVIDERS as _PROVIDERS
        for p in _PROVIDERS:
            self.provider_combo.addItem(p)
        self.provider_combo.setCurrentText(getattr(self.bridge, "provider_name", "agy"))
        self.provider_combo.currentTextChanged.connect(self._on_provider_selected)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        models = self.bridge.fetch_available_models()
        for m in models:
            self.model_combo.addItem(m)
        self.model_combo.setCurrentText(self.bridge.selected_model)
        apply_model_placeholder(self.model_combo, models)
        self.model_combo.currentTextChanged.connect(self._on_model_selected)
        fit_combo_to_contents(self.model_combo)
        fit_combo_to_contents(self.provider_combo)

        self.model_capsule.add_row("Sağlayıcı", self.provider_combo)
        self.model_capsule.add_row("Model", self.model_combo)
        _effort_row = self.model_capsule.popup_layout.count()
        self.effort_combo = install_effort_selector(
            self.model_capsule.popup_layout, self.bridge, self,
            model_combo=self.model_combo,
        )
        if self.effort_combo is not None:
            self.model_capsule.insert_caption(_effort_row, "Efor")
            self.effort_combo.setAccessibleName("Efor")

        self.skill_combo = QComboBox()
        self._populate_skills_combo()
        self.model_capsule.add_row("Yetenek", self.skill_combo)
        self.model_capsule.popup.adjustSize()
        self._sync_model_capsule()
        h_layout.addWidget(self.model_capsule)

        # (3) Durum rozetleri: token + bağlam + gelen kutusu + kimlik
        self.status_cluster = StatusCluster()
        self.tokens_badge = QLabel("0 tokens")
        self.tokens_badge.setProperty("role", "badge")
        self.tokens_badge.setProperty("tone", "ok")
        self.tokens_badge.setAccessibleName("Token kullanımı")
        self.status_cluster.add(self.tokens_badge, secondary=True)

        self.context_badge = QLabel("Bağlam: %0")
        self.context_badge.setProperty("role", "badge")
        self.context_badge.setAccessibleName("Bağlam doluluğu")
        self.status_cluster.add(self.context_badge, secondary=True)
        self._apply_context_badge()

        self.inbox_badge = InboxBadge()
        self.status_cluster.add(self.inbox_badge)
        bus.report_inbox_unread.connect(self._on_inbox_unread)

        self.provider_badge = ProviderStatusBadge()
        self.provider_badge.login_requested.connect(self._on_provider_login_requested)
        self.status_cluster.add(self.provider_badge)
        h_layout.addWidget(self.status_cluster)

        # (4) Komut paleti
        self.palette_btn = PaletteButton(on_open=self.open_command_palette)
        h_layout.addWidget(self.palette_btn)

        #: Kapı ölçümü: üst çubuk öğe sayısı ≤ 4.
        self.header_items = [
            self.brand, self.model_capsule, self.status_cluster, self.palette_btn,
        ]

        # Faz 14-E: Chat kipinde üst şerit ÜÇ düğmeye iner (Sohbet, Bildirimler,
        # palet); sohbet zaten tüm pencereyi kaplar. Zen'in yedi bölümü burada
        # yoktur — Chat "sohbet öncelikli" kipin tanımıdır (B notu §4).
        self.chat_nav_strip = QFrame()
        self.chat_nav_strip.setObjectName("navStrip")
        self.chat_nav_strip.setProperty("role", "toolbarGroup")
        _nav_row = QHBoxLayout(self.chat_nav_strip)
        _nav_row.setContentsMargins(0, 0, 0, 0)
        _nav_row.setSpacing(TOKENS["space"]["1"])

        # İkon düğme (28 px): 460 px'lik dar pencerede çubuk iki satırı aşmasın
        # diye metin yerine ikon + erişilebilir ad kullanılır (ui-design §0.10).
        self.nav_chat_btn = make_icon_button(
            "comment", "Sohbet", "Yan paneli kapat, tüm pencere sohbet olsun",
            self.chat_nav_strip,
        )
        self.nav_chat_btn.clicked.connect(self.show_chat_only)
        _nav_row.addWidget(self.nav_chat_btn)

        self.nav_notifications_btn = make_icon_button(
            "bell", "Bildirimler", "Bildirim merkezini yan panelde aç",
            self.chat_nav_strip,
        )
        self.nav_notifications_btn.clicked.connect(self.show_notifications)
        _nav_row.addWidget(self.nav_notifications_btn)
        h_layout.addWidget(self.chat_nav_strip)

        # Çubuktan kaldırılan düğmeler nesne olarak korunur (testler ve
        # palet eylemleri bunları çağırır); artık üst çubukta yer kaplamazlar.
        self.desk_btn = QPushButton("Desk")
        self.desk_btn.setProperty("variant", "ghost")
        self.desk_btn.setAccessibleName("Agent Desk")
        self.desk_btn.setToolTip("Ofis masasını aç (ajan ofisleri, kanban, canlı akış)")
        self.desk_btn.clicked.connect(self.open_agent_desk)

        self.project_btn = QPushButton(self.bridge.active_project_dir.name)
        self.project_btn.setProperty("variant", "ghost")
        self.project_btn.setAccessibleName("Proje klasörü")
        self.project_btn.setToolTip(
            f"Aktif proje: {self.bridge.active_project_dir}\nDeğiştirmek için tıklayın."
        )
        self.project_btn.clicked.connect(self._select_project_dir)

        self.panel_btn = QPushButton("Panel")
        self.panel_btn.setProperty("variant", "ghost")
        self.panel_btn.setAccessibleName("Görev ve yetenek paneli")
        self.panel_btn.setToolTip("Görevler ve yetenekler panelini aç/kapat")
        self.panel_btn.clicked.connect(self.toggle_side_panel)

        # Faz 8: çubuk doğrudan düzene girer, dar pencerede satır atlar.
        # `header_frame` testler ve ölçümler için açıkta tutulur.
        self.header_frame = header
        header.setMinimumWidth(180)
        self.layout.addWidget(header)

        # Report quick notification bar (shown when a report is created)
        self.report_bar = QFrame()
        self.report_bar.setVisible(False)
        self.report_bar.setProperty("role", "toast")
        rb_layout = QHBoxLayout(self.report_bar)
        rb_layout.setContentsMargins(8, 4, 8, 4)
        self.report_bar_lbl = QLabel("Yeni araştırma raporu hazır")
        rb_layout.addWidget(self.report_bar_lbl)
        rb_layout.addStretch()

        self.btn_view_report = QPushButton("Raporu aç")
        self.btn_view_report.setProperty("variant", "primary")
        self.btn_view_report.setAccessibleName("Raporu ayrı pencerede aç")
        self.btn_view_report.clicked.connect(self._open_latest_report)
        rb_layout.addWidget(self.btn_view_report)

        btn_dismiss_report = make_icon_button("close", "Bildirimi kapat", "Kapat", self.report_bar)
        btn_dismiss_report.clicked.connect(self.dismiss_report_bar)
        rb_layout.addWidget(btn_dismiss_report)

        self.layout.addWidget(self.report_bar)

        # Multi-notification Stack: Stackable pills for reports and tasks with []
        self.notification_scroll = QScrollArea()
        self.notification_scroll.setWidgetResizable(True)
        # Faz 11-E adım 4: krom payı; tepsi 100 -> 72 px.
        self.notification_scroll.setMaximumHeight(72)
        self.notification_stack_widget = QWidget()
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
        # Faz 9: `setOpenLinks(False)` olmadan QTextBrowser `entropy-report://`
        # bağlantısını kendi belgesi sanıp yüklemeye çalışıyor; günlüğe
        # "No document for entropy-report://..." uyarısı basıyor ve sohbet
        # görünümünü boşaltabiliyordu. Bağlantıyı yalnızca biz açıyoruz.
        self.chat_browser.setOpenLinks(False)
        self.chat_browser.anchorClicked.connect(self._on_anchor_clicked)
        # Faz 11-C: `task_report_ready` → sohbette rapor kartı + "Sohbete al".
        self.install_report_cards()
        # Faz 11-E: yerel stil yerine rol sınıfı (QSS QTextBrowser[role="reader"]).
        self.chat_browser.setProperty("role", "reader")
        self.chat_browser.setAccessibleName("Sohbet akışı")
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
        self.attach_label.setProperty("role", "label")
        self.attach_layout.addWidget(self.attach_label)
        self.attach_layout.addStretch()
        remove_attach_btn = QPushButton("Kaldır")
        remove_attach_btn.setProperty("variant", "ghost")
        remove_attach_btn.setAccessibleName("Ekleri kaldır")
        remove_attach_btn.clicked.connect(self._clear_staged_images)
        self.attach_layout.addWidget(remove_attach_btn)
        self.layout.addWidget(self.attachment_bar)

        # 4. Input layout
        input_bar = QHBoxLayout()
        self.input_field = ChatInputField(self)
        self.input_field.setPlaceholderText("Mesajınızı yazın veya Ctrl+V ile görsel yapıştırın…")
        self.input_field.setAccessibleName("Mesaj alanı")
        self.input_field.returnPressed.connect(self._on_send)
        input_bar.addWidget(self.input_field)

        self.pdf_btn = QPushButton("PDF")
        self.pdf_btn.setToolTip("Finansal rapor ya da PDF belgesi yükle")
        self.pdf_btn.setAccessibleName("PDF ekle")
        self.pdf_btn.clicked.connect(self._select_pdf_file)
        input_bar.addWidget(self.pdf_btn)

        self.send_btn = QPushButton("Gönder")
        self.send_btn.setProperty("variant", "primary")
        self.send_btn.setAccessibleName("Gönder")
        self.send_btn.setToolTip("Mesajı gönder (Ctrl+Enter)")
        self.send_btn.clicked.connect(self._on_send)
        input_bar.addWidget(self.send_btn)

        self.toggle_term_btn = QPushButton("Terminal")
        self.toggle_term_btn.setProperty("variant", "ghost")
        self.toggle_term_btn.setAccessibleName("Terminal çekmecesi")
        self.toggle_term_btn.setToolTip("Terminal çekmecesini aç/kapat (Ctrl+`)")
        self.toggle_term_btn.clicked.connect(self._toggle_terminal)
        input_bar.addWidget(self.toggle_term_btn)

        self.layout.addLayout(input_bar)

        # 5. Collapsible Terminal Drawer
        self.terminal_drawer = TerminalPaneWidget(title="Canlı akış konsolu")
        self.terminal_drawer.setMaximumHeight(190)
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
        install_command_palette(
            self, on_activated=self._on_palette_activated,
            loader=self._collect_palette_items,
        )
        self._install_shortcuts()

    def _apply_header_density(self) -> None:
        """Pencere darsa üst çubuğu sıkıştırır (aşamalı açığa çıkarma).

        Eşik 620 px: bunun altında token/bağlam rozetleri gizlenir ve model
        kapsülü kısa ada döner; ikisi de ipucunda ve komut paletinde durur.
        """
        compact = self.width() < 620
        # Faz 14-E: şerit çok dar pencerede gizlenir; iki eylem komut
        # paletinde ve "Panel" düğmesinde kalır (bilgi kaybı yok).
        strip = getattr(self, "chat_nav_strip", None)
        if strip is not None:
            strip.setVisible(not compact)
        cluster = getattr(self, "status_cluster", None)
        if cluster is not None:
            cluster.set_compact(compact)
        capsule = getattr(self, "model_capsule", None)
        if capsule is not None:
            capsule.set_compact(compact)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        try:
            self._apply_header_density()
        except Exception:
            pass

    def _connect_signals(self):
        # Faz 8: closeEvent her cagrildiginda 15 sinyali kosulsuz cozuyordu.
        # Pencere birden cok kez kapatilinca (testlerde ve tepsiye alma /
        # geri getirme dongusunde) PySide her cozulmus baglanti icin
        # "Failed to disconnect ..." RuntimeWarning'i basiyordu (olculen:
        # 526 uyari). Bayrak, cozmeyi yalnizca gercekten bagliyken yapar.
        self._bus_connected = True
        bus.model_detected.connect(self._update_model_badge)
        bus.token_usage_updated.connect(self._update_tokens)
        # Ek-1 (Faz 9): koprunun ayrintili token sozlugu (oturum/tur/onbellek).
        bus.token_usage_detail.connect(self._on_token_detail)
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
        # Faz 11-E: durum tek noktada (marka kümesindeki çekirdek noktası);
        # metin ipucuna iner, renk `tone` belirtecinden gelir.
        self.brand.set_state(state)

    # Faz 13-A2 madde 4 — ÇEKİRDEK DURUMU YALNIZCA ENTROPY'NİN KENDİ TURUDUR.
    #
    # Üç işleyici de `brand.set_state(...)` çağırıyordu: bir ajan kartı ya da
    # bir damıtma arka planda koşarken çekirdek "yürütülüyor" rengine geçiyor,
    # kullanıcı Entropy'nin kendisinin düşündüğünü sanıyordu. Arka plan işinin
    # durumu ajan rozetlerinde ve gezinme noktasında yaşar; çekirdek yalnızca
    # `bus.core_state_changed`'i (yani köprünün kendi turunu) yansıtır.
    # Bilgi kaybolmuyor: her üçü de rozet ipucunda duruyor.
    @Slot(str, str)
    def _on_task_triggered(self, task_id: str, task_name: str):
        self.state_badge.setToolTip(f"Arka plan görevi çalışıyor: {task_name} ({task_id})")

    @Slot(str, bool)
    def _on_task_completed(self, task_id: str, success: bool):
        self.state_badge.setToolTip(
            "Entropy AI çekirdek durumu" if success else "Arka plan görevi hata verdi"
        )

    @Slot(str, int, int)
    def _on_distill_progress(self, skill_name: str, done: int, total: int):
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
            self.side_panel.addTab(self.tasks_widget, "Görevler")
            self.side_panel.addTab(self.skills_widget, "Yetenekler")
            self.side_panel.addTab(self.agents_widget, "Ajanlar")
            self.side_panel.addTab(self.agent_tasks_widget, "Ajan Görevleri")

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
            self.side_panel.addTab(self.report_center, "Gelen")

            self.timeline_panel = TimelinePanel()
            self.timeline_panel.event_activated.connect(self._on_timeline_activated)
            self.side_panel.addTab(self.timeline_panel, "Bugun")

            self.notification_center = NotificationCenter()
            self.notification_center.notification_activated.connect(
                self._on_notification_activated
            )
            self.side_panel.addTab(self.notification_center, "Bildirimler")
            self.side_panel_layout.addWidget(self.side_panel)
        return self.side_panel

    @Slot(str, str)
    def _on_orchestrator_answer(self, office: str, body: str):
        """
        "Orkestratore sor" yaniti sohbete "<ofis>" balonuyla duser.

        Yanit sohbete yazilir cunku bu bir diyalogdur: kullanicinin sorusu ve
        ofisin cevabi ayni akista kalmali, kartin icinde kaybolmamali.
        """
        from entropy.ui.widgets.markdown_renderer import build_chat_bubble_html

        self.chat_browser.append(
            build_chat_bubble_html(f"Ofis: {office}", str(body or ""))
        )

    @Slot(str, str, str)
    def _on_palette_activated(self, kind: str, payload: str, label: str):
        """Komut paleti secimi: rapor acilir, kalan her sey giris satirina yazilir."""
        if kind == "report":
            self._open_inbox_report(payload)
            return
        if kind == "action":
            self.run_palette_action(payload)
            return
        self.input_field.setText(payload if payload.endswith(" ") else payload + " ")
        self.input_field.setFocus()

    def _sync_model_capsule(self) -> None:
        """Kapsul metnini kopruden tazeler (tek kaynak)."""
        capsule = getattr(self, "model_capsule", None)
        if capsule is None:
            return
        effort = ""
        combo = getattr(self, "effort_combo", None)
        if combo is not None:
            try:
                effort = combo.currentText()
            except Exception:
                effort = ""
        capsule.set_summary(
            str(getattr(self.bridge, "provider_name", "") or ""),
            str(getattr(self.bridge, "selected_model", "") or ""),
            effort,
        )

    @Slot()
    def open_command_palette(self) -> None:
        """Komut paletini acar (ust cubuk dugmesi ve Ctrl+K ayni yol)."""
        opener = getattr(self, "_open_command_palette", None)
        if callable(opener):
            opener()

    @Slot()
    def dismiss_report_bar(self) -> None:
        """Rapor bildirim seridini kapatir (alici QObject slotu, lambda degil)."""
        self.report_bar.setVisible(False)

    def _collect_palette_items(self):
        """Palet kaynaklari + ust cubuktan tasinan pencere eylemleri (IA-9)."""
        from entropy.ui.widgets.command_palette import collect_palette_items

        actions = [
            ("desk", "Agent Desk'i ac", "Ofis masasi: ajan ofisleri, kanban, canli akis"),
            ("project", "Proje klasorunu degistir", "Aktif proje dizini"),
            ("new_chat", "Yeni sohbet", "Mevcut sohbeti arsivler"),
            ("panel", "Gorev ve yetenek panelini ac/kapat", "Ctrl+1"),
            ("terminal", "Terminal cekmecesini ac/kapat", "Ctrl+`"),
            ("reports", "Raporlar penceresini ac", "Ctrl+2"),
            ("mode_zen", "Zen kipine gec", "Ctrl+3"),
            ("mode_floating", "Floating kipine gec", ""),
            ("mode_chat", "Chat kipine gec", ""),
            ("toggle_lock", "Öz-amplifikasyon kilidi aç/kapat",
             "config.amplification_lock · /lock on|off"),
            ("toggle_board_auto", "Pano otomatik dağıtım aç/kapat",
             "config.board_auto_dispatch · /board auto on|off"),
        ]
        items = [
            {"kind": "action", "label": label, "subtitle": subtitle, "payload": key}
            for key, label, subtitle in actions
        ]
        try:
            items += collect_palette_items(project_dir=self.bridge.active_project_dir)
        except Exception:
            pass
        return items

    def _run_setting_toggle(self, key: str) -> str:
        """Boole ayar anahtarini cevirir (zen kipiyle ayni sozlesme)."""
        from entropy.core.slash_commands import (
            toggle_amplification_lock, toggle_board_auto_dispatch,
        )

        fn = (toggle_amplification_lock if key == "toggle_lock"
              else toggle_board_auto_dispatch)
        try:
            _state, message = fn()
        except Exception as exc:  # pragma: no cover - savunma
            message = f"Ayar degistirilemedi: {exc}"
        bus.terminal_output_received.emit(f"[Ayar] {message}\n")
        return message

    def run_palette_action(self, key: str) -> bool:
        """Palet eylemi yurutur; bilinmeyen anahtar icin False doner."""
        if key == "desk":
            self.open_agent_desk()
        elif key == "project":
            self._select_project_dir()
        elif key == "new_chat":
            self._on_new_chat()
        elif key == "panel":
            self.toggle_side_panel()
        elif key == "terminal":
            self._toggle_terminal()
        elif key == "reports":
            self._open_reports_window()
        elif key in ("toggle_lock", "toggle_board_auto"):
            self._run_setting_toggle(key)
        elif key.startswith("mode_"):
            bus.mode_requested.emit(key.split("_", 1)[1])
        else:
            return False
        return True

    def _install_shortcuts(self) -> None:
        """Klavye kisayollari (denetim D-20)."""
        from PySide6.QtGui import QShortcut

        self._shortcuts = []
        for seq, key in (
            ("Ctrl+1", "panel"),
            ("Ctrl+2", "reports"),
            ("Ctrl+3", "mode_zen"),
            ("Ctrl+`", "terminal"),
            ("Ctrl+N", "new_chat"),
        ):
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setProperty("action_key", key)
            shortcut.activated.connect(self._on_shortcut)
            self._shortcuts.append(shortcut)
        send = QShortcut(QKeySequence("Ctrl+Return"), self)
        send.activated.connect(self._on_send)
        self._shortcuts.append(send)

    @Slot()
    def _on_shortcut(self) -> None:
        """Kisayol alicisi: lambda degil QObject slotu."""
        sender = self.sender()
        if sender is None:
            return
        self.run_palette_action(str(sender.property("action_key") or ""))

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

    @Slot()
    def show_chat_only(self) -> bool:
        """Üst şeritteki "Sohbet": yan panel kapanır, pencere tümüyle sohbet."""
        self._side_panel_open = False
        self.side_panel_container.setVisible(False)
        self.panel_btn.setText("Panel")
        return True

    @Slot()
    def show_notifications(self) -> bool:
        """Üst şeritteki "Bildirimler": yan panel bildirim sekmesinde açılır."""
        panel = self.ensure_side_panel()
        self._side_panel_open = True
        self.side_panel_container.setVisible(True)
        self.panel_btn.setText("Paneli kapat")
        for index in range(panel.count()):
            if "Bildirim" in panel.tabText(index):
                panel.setCurrentIndex(index)
                return True
        return False

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
        self.panel_btn.setText("Paneli kapat" if will_show else "Panel")
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

        self.report_bar_lbl.setText(f"<span style='color:{_P["ok"]}; font-weight:bold;'>Yeni Rapor:</span> <span style='color:{_P["text"]};'>{p.stem}</span>")
        self.report_bar.setVisible(True)
        # Zen ile aynı davranış: rapor da yığılabilir bir bildirim pili üretir.
        self.add_notification_pill(title=p.stem, path_or_content=str(p), is_task=False)

        card_html = (
            f"<div style='background-color:{_P["surface"]}; border:1px solid {_P["accent"]}; border-radius:8px; padding:10px 14px; margin:8px 0;'>"
            f"<div style='color:{_P["accent"]}; font-size:11px; font-weight:bold; letter-spacing:0.8px;'>Yeni Araştırma Raporu Oluşturuldu</div>"
            f"<div style='color:{_P["text"]}; font-size:13px; font-weight:bold; margin:4px 0;'>{p.stem}</div>"
            f"<div style='color:{_P["text_muted"]}; font-size:11px; margin-bottom:8px;'>Dosya: {p.name} | Bilişsel Hafıza ve RAG'a İşlendi</div>"
            f"<a href='entropy-report://{p.as_posix()}' style='display:inline-block; background-color:{_P["accent"]}; color:{_P["bg"]}; font-weight:bold; font-size:11px; text-decoration:none; padding:5px 14px; border-radius:4px;'>Raporu aç</a>"
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
            f"<div style='background-color:{_P["surface"]}; border:1px solid {_P["ok"]}; border-radius:8px; padding:10px 14px; margin:8px 0;'>"
            f"<div style='color:{_P["ok"]}; font-size:11px; font-weight:bold; letter-spacing:0.8px;'>⏰ OTONOM PLANLI GÖREV ÇALIŞTIRILDI</div>"
            f"<div style='color:{_P["text"]}; font-size:13px; font-weight:bold; margin:4px 0;'>{task_name}</div>"
            f"<div style='color:{_P["text_muted"]}; font-size:11px; margin-bottom:8px;'>Görev Kimliği: {task_id}</div>"
        )
        if path_or_content.endswith(".md"):
            p = Path(path_or_content)
            card_html += f"<a href='entropy-report://{p.as_posix()}' style='display:inline-block; background-color:{_P["ok"]}; color:{_P["bg"]}; font-weight:bold; font-size:11px; text-decoration:none; padding:5px 14px; border-radius:4px;'>Görev raporunu aç</a>"
        card_html += "</div>"
        self.chat_browser.append(card_html)

    def _on_anchor_clicked(self, url):
        """Intercept entropy-report:// links to open the standalone viewer."""
        url_str = url.toString()
        if self.handle_context_anchor(url_str):
            return
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
            body = f"<b style='color:{_P["danger"]};'>/desk hatası:</b> {html.escape(str(exc))}"

        opened = False
        if prompt.strip() == "/desk":
            opened = self.open_agent_desk() is not None

        if body is None:
            body = (
                f"<b style='color:{_P["neutral"]};'>Agent Desk</b><br/>"
                + ("Ofis penceresi açıldı.<br/>" if opened else "")
                + f"<span style='color:{_P["text_muted"]};'>Kullanım: "
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
            self.project_btn.setText(f"{Path(new_dir).name}")
            self.project_btn.setToolTip(f"Aktif Proje: {new_dir}\nDeğiştirmek için tıklayın.")
        self._populate_skills_combo()

    def _populate_skills_combo(self):
        curr = self.skill_combo.currentData() if hasattr(self, "skill_combo") else "auto"
        self.skill_combo.blockSignals(True)
        self.skill_combo.clear()
        self.skill_combo.addItem("Yetenek: Otomatik", "auto")
        try:
            sm = SkillManager(project_dir=self.bridge.active_project_dir)
            for s in sm.list_skills():
                if s.enabled:
                    self.skill_combo.addItem(f"{s.name}", s.name)
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
            parts.append(f"Eklenen PDF: " + ", ".join(pdf_descs))
        if self.staged_images:
            parts.append(f"Eklenen Görsel: " + ", ".join([f"<b>{Path(p).name}</b>" for p in self.staged_images]))
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
                        self._append_message("Entropy AI", f"<b>Yetenek Başarıyla Yüklendi:</b> '{imported.name}' sisteme entegre edildi.", is_system=True)

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
                    self._append_message("Entropy AI", f"<b>Yetenek URL'den Yüklendi:</b> '{imported.name}' sisteme entegre edildi.", is_system=True)

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

    def _sync_terminal_button(self) -> None:
        """Terminal dugmesinin metni/durumu cekmecenin GERCEK haliyle esitlenir.

        Faz 11 kapanisi (regresyon): `_on_turn_started` cekmeceyi acarken
        etiketi ayri bir yerde ve ESKI (emojili) metinle yaziyordu; 11-E
        temizliginden sonra iki kod yolu iki farkli etiket uretiyordu.
        Tek kaynak burasi.
        """
        is_vis = not self.terminal_drawer.isHidden()
        self.toggle_term_btn.setText("Terminali kapat" if is_vis else "Terminal")
        self.toggle_term_btn.setChecked(is_vis)

    def _toggle_terminal(self):
        self.terminal_drawer.setVisible(self.terminal_drawer.isHidden())
        self._sync_terminal_button()

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
        # Faz 9: yalnızca etkin sağlayıcıya ait ad köprüye geçer; reddedilirse
        # kutu eski değerine döner (bkz. ui_polish.accept_model_selection).
        if model_name and model_name != self.bridge.selected_model:
            from entropy.ui.widgets.ui_polish import accept_model_selection

            accept_model_selection(self.bridge, self.model_combo, model_name)
        # HOTFIX v0.7.1: agy'de efor model adına gömülü; model değişince
        # efor kutusu yeni modelin son eklerine göre yeniden dolar.
        self._refresh_effort_combo()

    def sync_model_effort_ui(self) -> None:
        """
        Ust cubuk model/efor kutularini kopruden tazeler (Faz 11-C, is 4).

        `/model` ve `/effort` komutlari kopruye yaziyor ve ayari `config`e
        kaliciyor; ama Claude tarafinda `set_effort` sinyal yaymadigi icin ust
        cubuktaki kutu bayat kaliyordu. Yerel komut isledikten sonra kutular
        tek kaynaktan (koprunun secili degerleri) yeniden okunur.
        """
        combo = getattr(self, "model_combo", None)
        model = str(getattr(self.bridge, "selected_model", "") or "")
        if combo is not None and model:
            combo.blockSignals(True)
            try:
                if combo.findText(model) < 0:
                    combo.addItem(model)
                combo.setCurrentText(model)
            finally:
                combo.blockSignals(False)
        self._refresh_effort_combo()

    def _refresh_effort_combo(self):
        """Efor kutusunu (varsa) sağlayıcı+model değişiminden sonra tazeler."""
        combo = getattr(self, "effort_combo", None)
        if combo is not None:
            try:
                combo.refresh()
            except Exception:
                pass

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
        # Faz 9: yeni saglayicinin model adlari daha uzun olabilir; kutuyu yeniden olc.
        fit_combo_to_contents(self.model_combo)
        self._refresh_effort_combo()

    @Slot(int)
    def _update_tokens(self, tokens: int):
        # Sohbet ve arka plan kalemleri ayrı; biçim zen_mode ile ortak.
        from entropy.ui.widgets.token_badge import format_token_badge

        text, tip = format_token_badge(self.bridge)
        self.tokens_badge.setText(text)
        self.tokens_badge.setToolTip(tip)
        self._apply_context_badge()

    @Slot(dict)
    def _on_token_detail(self, detail: dict):
        """Koprunun `usage_badge_fields()` sozluguyle rozeti tazeler."""
        self._last_token_detail = dict(detail or {})
        self._update_tokens(int(self._last_token_detail.get("session", 0) or 0))

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
        # Faz 11-E: renk yerel QSS ile degil `tone` belirteciyle gelir.
        self.context_badge.setProperty("tone", context_badge_tone(color))
        _repolish(self.context_badge)

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
                self._append_message("Entropy AI", f"<b>Yetenek Sisteme Kuruldu:</b> '{imported.name}' başarıyla kuruldu ve seçildi.", is_system=True)

        # Check slash command handling (supports multiple slash commands in prompt)
        matched_cmds = []
        # Faz 9: istemden temizlenecek yetenek slash token'ları.
        skill_tokens_used: list = []
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
                # Model/efor degistiren komutlardan sonra ust cubuk tazelenir.
                self.sync_model_effort_ui()
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
                        f"<div style='border:1px solid {_P["line_strong"]}; background:{_P["bg"]}; border-radius:6px; padding:10px; margin:6px 0;'>",
                        f"<b style='color:{_P["accent"]}; font-size:13px;'>KULLANILABİLİR KOMUTLAR, YETENEKLER VE MCP ARAÇLARI</b><br/><br/>"
                    ]
                    for c in all_c:
                        help_html.append(
                            f"<div style='margin-bottom:4px;'>"
                            f"<span style='background-color:{c.color}22; color:{c.color}; border:1px solid {c.color}55; border-radius:3px; padding:1px 5px; font-size:11px; font-weight:bold;'>{c.badge}</span> "
                            f"<b style='color:{_P["text"]}; font-family:Consolas;'>{c.name}</b>: "
                            f"<span style='color:{_P["text_muted"]}; font-size:11px;'>{c.description}</span>"
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
                        skill_tokens_used.append(tok)

            # Faz 9: bilinmeyen slash sağlayıcı CLI'ına gitmemeli; CLI onu kendi
            # ad alanında arayıp "Unknown command" döndürüyordu.
            unknown = unknown_slash_token(prompt, set(cmds_by_token), CLI_PASSTHROUGH)
            if unknown:
                self._append_message(
                    "Entropy AI",
                    unknown_slash_html(unknown, close_matches(unknown, cmds_by_token)),
                    is_system=True,
                )
                self.input_field.clear()
                return

        chosen_skill = self.skill_combo.currentData()
        escaped_prompt = html.escape(prompt).replace('\n', '<br/>')
        display_prompt = escaped_prompt

        badge_html = ""
        badge_spans = []
        if matched_cmds:
            for mc in matched_cmds:
                badge_spans.append(
                    f"<span style='background:{_P["surface"]}; color:{mc.color}; border:1px solid {mc.color}55; border-radius:3px; padding:2px 8px; font-size:11px; font-weight:bold; margin-right:4px;'>{mc.badge}: {html.escape(mc.name)}</span>"
                )
        skill_already_badged = any(mc.category == "skill" and (mc.metadata.get("skill_name") == chosen_skill or mc.name.lstrip("/") == chosen_skill) for mc in matched_cmds)
        if chosen_skill and chosen_skill != "auto" and not skill_already_badged:
            badge_spans.append(
                f"<span style='background:{_P["surface"]}; color:{_P["ok"]}; border:1px solid {_P["line_strong"]}; border-radius:3px; padding:2px 8px; font-size:11px; font-weight:bold; margin-right:4px;'>Yetenek: {html.escape(chosen_skill)}</span>"
            )
        if badge_spans:
            badge_html = f"<div style='margin-bottom:4px;'>{' '.join(badge_spans)}</div>"

        if badge_html:
            display_prompt = f"{badge_html}<div>{escaped_prompt}</div>"

        if self.staged_images:
            img_names = ", ".join([html.escape(Path(p).name) for p in self.staged_images])
            display_prompt += f" <div style='color:{_P["accent"]}; font-size:11px; margin-top:4px;'><i>[Eklenen Görsel: {img_names}]</i></div>"
        if self.staged_pdfs:
            pdf_names = ", ".join([html.escape(Path(p).name) for p in self.staged_pdfs])
            display_prompt += f" <div style='color:{_P["ok"]}; font-size:11px; margin-top:4px;'><i>[Eklenen PDF: {pdf_names}]</i></div>"

        self._append_message("Siz", display_prompt)
        self.input_field.clear()

        images_to_send = list(self.staged_images)
        pdfs_to_send = list(self.staged_pdfs)
        self._clear_staged_images()

        actual_prompt = prompt
        # Faz 9: yetenek slash'ı arayüzde tüketildi (kombo ayarlandı); token
        # istemde kalırsa CLI onu komut sanıp "Unknown command" döndürüyor.
        if skill_tokens_used:
            actual_prompt = strip_skill_tokens(actual_prompt, skill_tokens_used)
            if not actual_prompt:
                # Yalnızca "/<yetenek>" yazıldı: iş yok, sadece yeteneği seç.
                self._append_message(
                    "Entropy AI",
                    f"<b>Yetenek etkin:</b> {html.escape(str(chosen_skill or skill_tokens_used[0]))}"
                    " — şimdi ne yapmasını istediğinizi yazın.",
                    is_system=True,
                )
                return
        if images_to_send:
            actual_prompt += "\n" + "\n".join([f"[Eklenen Görsel Dosyası: {p}]" for p in images_to_send])

        if self.bridge.is_running:
            self._append_message("Entropy AI", "⏳ <i>Önceki işlem tamamlanıyor, mesajınız sıraya alındı ve hemen ardından yanıtlanacak...</i>", is_system=True)

        # Faz 11-C: "Sohbete al" ile alınan rapor blokları istemin başına
        # eklenir ve kuyruk boşaltılır (aynı rapor iki kez gitmez).
        actual_prompt = self.apply_report_context(actual_prompt)

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
        self._sync_terminal_button()
        self.chat_browser.append(f"<div style='margin-bottom:8px;'><b style='color:{_P["accent"]};'>Entropy AI:</b><br/></div>")
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
        if not getattr(self, "_bus_connected", False):
            # Zaten cozulmus; ikinci kez denemek RuntimeWarning uretirdi.
            super().closeEvent(event)
            return
        self._bus_connected = False
        signals = [
            (bus.model_detected, self._update_model_badge),
            (bus.token_usage_updated, self._update_tokens),
            (bus.token_usage_detail, self._on_token_detail),
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
            # Faz 11-C: rapor kartı köprüsü de çözülür (sızıntı olmasın).
            (bus.task_report_ready, self._on_task_report_ready),
            # Faz 8: bagliydi ama cozulmuyordu (sizinti).
            (bus.context_pressure, self._on_context_pressure),
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

