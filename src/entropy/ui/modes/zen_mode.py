"""Zen Mode: Borderless fullscreen workstation for Entropy AI."""

import html
import json
from pathlib import Path
import re
from typing import List, Optional
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget
)

import sys as _sys
import entropy.core.config  # noqa: F401  (alt modulun yuklenmesi icin)
# entropy.core paketi 'config' adini config NESNESINE baglar; sohbet
# gecmisi yardimcilari icin gercek modul gerekiyor.
config_module = _sys.modules["entropy.core.config"]
from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.ui.widgets.report_card_bridge import ReportCardMixin
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.platform.clipboard import ClipboardImageHandler
from entropy.core.slash_commands import SlashCommandRegistry
from entropy.mcp.manager import default_mcp_manager
from entropy.ui.modes.chat_mode import ChatInputField
from entropy.ui.themes.cyber_theme import CYBER_THEME, READING_TOKENS as RT, reading_css
from entropy.ui.design import TOKENS, icon as design_icon
from entropy.ui.widgets.header_bar import (
    BrandCluster, ModelCapsule, PaletteButton, StatusCluster, WindowControls,
    context_badge_tone, repolish as _repolish,
)
from entropy.ui.widgets.nav_list import NavList
from entropy.ui.widgets.report_inbox import InboxBadge
from entropy.ui.widgets.command_palette import install_command_palette
from entropy.ui.widgets.flow_layout import FlowHeaderFrame, fit_combo_to_contents
from entropy.ui.widgets.focus_mode import install_focus_mode
from entropy.ui.widgets.notification_center import NotificationCenter
from entropy.ui.widgets.provider_badge import ProviderStatusBadge
from entropy.ui.widgets.timeline_panel import TimelinePanel
from entropy.ui.widgets.effort_selector import install_effort_selector
from entropy.ui.widgets.ui_polish import apply_model_placeholder
from entropy.ui.widgets.core_visualizer import CoreVisualizerWidget
from entropy.ui.widgets.knowledge_graph import KnowledgeGraphWidget
from entropy.ui.widgets.mcp_drawer import MCPDrawerWidget
from entropy.ui.widgets.reports_viewer import ReportsViewerWidget
from entropy.ui.widgets.tasks_widget import TasksWidget
from entropy.ui.widgets.skills_widget import SkillsWidget
from entropy.ui.widgets.notification_pill import NotificationPillWidget
from entropy.ui.widgets.slash_prompt import (
    CLI_PASSTHROUGH, close_matches, strip_skill_tokens, unknown_slash_html,
    unknown_slash_token,
)
from entropy.ui.widgets.standalone_report_window import StandaloneReportWindow
from entropy.ui.widgets.terminal_pane import TerminalPaneWidget
from entropy.ui.widgets.agents_widget import AgentsWidget
from entropy.ui.widgets.rules_panel import RuleCandidatesPanel
from entropy.ui.widgets.task_board_widget import TaskBoardWidget
from entropy.ui.widgets.frameless import FramelessWindowHelper
from entropy.ui.window_sizing import fit_window_to_screen, maximize_window_to_screen

# Faz 6: 1366x768 ekranda da taşmayan asgari boyut ve ekran doluluk oranı.
ZEN_MIN_SIZE = (1100, 680)
ZEN_SCREEN_RATIO = 0.92


class ZenModeWindow(ReportCardMixin, QMainWindow):
    """Zen Mode: Borderless fullscreen immersive AI engineering environment."""

    def __init__(self, bridge: AgyProcessBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.clipboard_handler = ClipboardImageHandler()
        self.staged_images: List[str] = []
        self.staged_pdfs: List[str] = []
        self._streaming_active: bool = False
        # Faz 11-E adım 2: stil artık uygulama düzeyinde tek girişten gelir
        # (`ui/manager.py` -> `apply_design_system(app)`); pencere kendi stil
        # sayfasını yazmaz.
        # Çerçevesiz pencerede başlık görünmez ama görev çubuğu/pencere listesi
        # ve ekran okuyucular bunu kullanır: ürün adı tek biçimde "Entropy AI".
        self.setWindowTitle("Entropy AI")
        self.setAcceptDrops(True)

        # Borderless window configuration
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        self._init_ui()
        self._connect_signals()

        # Faz 8: cercevesiz pencereye tasima (ust cubuktan surukleme), cift
        # tikla maksimize ve kenarlardan boyutlandirma eklenir.
        self.frameless = FramelessWindowHelper(self, handle=self.header_frame)

        # Faz 6/8: minimum kullanilabilir alana kirpilir, sonra pencere
        # kullanilabilir alanin tamamina maksimize edilir (kullanici Zen'i
        # "tam ekrandan cikmis" gordugu icin; bkz. maximize_window_to_screen).
        self.setMinimumSize(*ZEN_MIN_SIZE)
        fit_window_to_screen(self, ratio=ZEN_SCREEN_RATIO, min_size=ZEN_MIN_SIZE)
        maximize_window_to_screen(self, min_size=ZEN_MIN_SIZE)

    def toggle_maximize(self) -> None:
        """Maksimize <-> geri (ust cubuk dugmesi ve cift tiklama)."""
        self.frameless.toggle_maximize()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(10)

        # 1. Üst çubuk — Faz 11-E adım 2: 18 öğe → 4 (+ pencere denetimleri).
        # Denetim D-08: 18 denetim 460 px'te 6 satıra sarıyordu. Kaldırılan
        # düğmeler (Desk, Proje, Yeni, Floating/Chat, Raporlar) yok olmadı;
        # komut paletine ve sol dikey gezinmeye taşındı.
        header = FlowHeaderFrame(margins=(16, 8, 16, 8))
        h_layout = header.flow()

        # (1) Marka + küçük çekirdek + durum noktası + mod anahtarı.
        # Denetim D-11: çekirdek görselleştirici merkez sütunda 160×160 px yer
        # kaplıyor ve sütunun %93'ünü boş bırakıyordu; buraya 22 px olarak iner.
        self.brand = BrandCluster(current_mode="zen")
        self.core_visualizer = CoreVisualizerWidget(base_radius=9, mode_menu_enabled=True)
        self.core_visualizer.setFixedSize(24, 24)
        self.core_visualizer.setToolTip("Entropy çekirdeği — tıklayınca kip menüsü")
        self.brand.insert_core(self.core_visualizer)
        h_layout.addWidget(self.brand)

        h_layout.addStretch()

        # (2) Sağlayıcı / model / efor tek kapsülde
        self.model_capsule = ModelCapsule()
        self.provider_combo = QComboBox()
        self.provider_combo.setAccessibleName("Sağlayıcı (CLI): agy = Antigravity, claude = Claude Code")
        self.provider_combo.setToolTip("Sağlayıcı (CLI): agy = Antigravity, claude = Claude Code")
        from entropy.core.provider import PROVIDERS as _PROVIDERS
        for _p in _PROVIDERS:
            self.provider_combo.addItem(_p)
        self.provider_combo.setCurrentText(getattr(self.bridge, "provider_name", "agy"))
        self.provider_combo.currentTextChanged.connect(self._on_provider_selected)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        models = self.bridge.fetch_available_models()
        for m in models:
            self.model_combo.addItem(m)
        self.model_combo.setCurrentText(self.bridge.selected_model)
        # Model alanı boşken ne olduğunu yazan yer tutucu (işlev değişmez).
        apply_model_placeholder(self.model_combo, models)
        # Faz 9: en uzun model adına göre ölç (Chat ile aynı kural).
        fit_combo_to_contents(self.model_combo, min_width=180)
        self.model_combo.currentTextChanged.connect(self._on_model_selected)
        fit_combo_to_contents(self.provider_combo)

        self.model_capsule.add_row("Sağlayıcı", self.provider_combo)
        self.model_capsule.add_row("Model", self.model_combo)
        # Faz 6: Efor seçici (köprüde effort_levels() varsa görünür).
        _effort_row = self.model_capsule.popup_layout.count()
        self.effort_combo = install_effort_selector(
            self.model_capsule.popup_layout, self.bridge, self,
            model_combo=self.model_combo,
        )
        if self.effort_combo is not None:
            self.model_capsule.insert_caption(_effort_row, "Efor")
            self.effort_combo.setAccessibleName("Efor")
        self.model_capsule.popup.adjustSize()
        self._sync_model_capsule()
        h_layout.addWidget(self.model_capsule)

        # (3) Durum rozetleri: kimlik + token + bağlam + gelen kutusu
        self.status_cluster = StatusCluster()
        self.tokens_badge = QLabel("Tokens: 0")
        self.tokens_badge.setProperty("role", "badge")
        self.tokens_badge.setProperty("tone", "ok")
        self.tokens_badge.setAccessibleName("Token kullanımı")
        self.status_cluster.add(self.tokens_badge, secondary=True)

        # Bağlam doluluk rozeti: %60 üstünde uyarı tonu + /handoff ipucu.
        self.context_badge = QLabel("Bağlam: %0")
        self.context_badge.setProperty("role", "badge")
        self.context_badge.setAccessibleName("Bağlam doluluğu")
        self.status_cluster.add(self.context_badge, secondary=True)
        self._apply_context_badge()

        # Rapor Merkezi rozeti (Faz 4): son 24 saatte okunmamış rapor sayısı.
        # Sıfırken kendini gizler, üst çubukta yer kaplamaz.
        self.inbox_badge = InboxBadge()
        self.status_cluster.add(self.inbox_badge)
        bus.report_inbox_unread.connect(self._on_inbox_unread)

        # Faz 5.4/5.5: iki sağlayıcı için giriş/kota/oturum penceresi rozeti.
        self.provider_badge = ProviderStatusBadge()
        self.provider_badge.login_requested.connect(self._on_provider_login_requested)
        self.status_cluster.add(self.provider_badge)
        h_layout.addWidget(self.status_cluster)

        # (4) Komut paleti — birincil gezinme (IA-9)
        self.palette_btn = PaletteButton(on_open=self.open_command_palette)
        h_layout.addWidget(self.palette_btn)

        #: Kapı ölçümü: üst çubuk öğe sayısı ≤ 4 (pencere denetimleri hariç).
        self.header_items = [
            self.brand, self.model_capsule, self.status_cluster, self.palette_btn,
        ]

        # Pencere denetimleri (çerçevesiz pencerenin başlık çubuğu karşılığı).
        self.window_controls = WindowControls()
        self.window_controls.minimize_requested.connect(self.showMinimized)
        self.window_controls.maximize_requested.connect(self.toggle_maximize)
        self.window_controls.close_requested.connect(self.close)
        self.btn_minimize = self.window_controls.btn_minimize
        self.btn_maximize = self.window_controls.btn_maximize
        h_layout.addWidget(self.window_controls)

        # Agent Desk / proje / yeni sohbet düğmeleri artık çubukta değil;
        # komut paletinden ve sol gezinme altbilgisinden çağrılır. Nesneler
        # korunur (testler ve `open_agent_desk` yolu bunlara bağlı).
        self.desk_btn = QPushButton("Desk")
        self.desk_btn.setProperty("variant", "ghost")
        self.desk_btn.setAccessibleName("Agent Desk")
        self.desk_btn.setToolTip("Ofis masasını aç (ajan ofisleri, kanban, canlı akış)")
        self.desk_btn.clicked.connect(self.open_agent_desk)

        self.project_btn = QPushButton(self.bridge.active_project_dir.name)
        self.project_btn.setProperty("variant", "ghost")
        self.project_btn.setAccessibleName("Proje klasörü")
        self.project_btn.setToolTip("Aktif proje klasörünü değiştir")
        self.project_btn.clicked.connect(self._select_project_dir)

        # Faz 8: çubuk doğrudan düzene girer, dar pencerede satır atlar.
        self.header_frame = header
        header.setMinimumWidth(200)
        root_layout.addWidget(header)

        # 2. Ana çalışma alanı — Faz 11-E adım 2: bölücü derinliği 4 → 2.
        # Eskiden zincir `main_v > top_h > left_tabs > tasks_split` biçiminde
        # dörde iniyordu ve kullanıcı bir raporu okumak için üç ayrı bölücüyü
        # ayarlamak zorundaydı (denetim D-17).
        main_v_splitter = QSplitter(Qt.Orientation.Vertical)
        main_v_splitter.setObjectName("shellSplitter")

        # Üst yatay bölücü: sol bağlam (gezinme + içerik), sağ hafıza (graf).
        top_h_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_h_splitter.setObjectName("shellSplitter")

        # Sol bölge: dikey gezinme listesi (sekme değil) + içerik yığını.
        self.left_tabs = NavList()
        self.reports_viewer = ReportsViewerWidget()
        self.mcp_drawer = MCPDrawerWidget()
        self.tasks_widget = TasksWidget(parent=self, bridge=self.bridge)
        self.skills_widget = SkillsWidget(bridge=self.bridge)
        self.agents_widget = AgentsWidget(bridge=self.bridge)

        # Görevler sekmesi iki bölüm: üstte ajan görev panosu (kanban),
        # altta mevcut zamanlanmış görev listesi. İkisi de aynı yerde kalır.
        # Bölücü değil düzen: iç içe bölücü derinliğini 2'de tutar (D-17).
        # Oranlar esnetme katsayısıyla verilir (pano 3, liste 2).
        self.task_board_widget = TaskBoardWidget()
        tasks_tab = QWidget()
        tasks_tab_layout = QVBoxLayout(tasks_tab)
        tasks_tab_layout.setContentsMargins(0, 0, 0, 0)
        tasks_tab_layout.setSpacing(TOKENS["space"]["2"])
        tasks_tab_layout.addWidget(self.task_board_widget, 3)
        tasks_tab_layout.addWidget(self.tasks_widget, 2)
        self.tasks_tab = tasks_tab

        # Rapor Merkezi kartlarindaki "Orkestratore sor" yaniti sohbete duser;
        # kopru kart uzerinden /ask komutuna gecsin diye burada baglanir.
        try:
            self.reports_viewer.report_center.bridge = self.bridge
            self.reports_viewer.report_center.orchestrator_answer.connect(
                self._on_orchestrator_answer
            )
        except AttributeError:
            pass

        self.left_tabs.addTab(self.reports_viewer, "Raporlar & Notlar", "library")
        self.left_tabs.addTab(self.skills_widget, "Yetenekler", "target")
        self.left_tabs.addTab(tasks_tab, "Görevler", "checklist")
        self.left_tabs.addTab(self.mcp_drawer, "MCP Sunucuları", "plug")
        # Faz 10-B: Entropy'nin KENDİ kural adayları (ofis = "entropy").
        # Ajan bir kural keşfedince kullanıcıya burada sorulur; "Kalıcı yap"
        # denmeden kural sistem istemine girmez.
        self.entropy_rules_panel = RuleCandidatesPanel(office="entropy")
        self.entropy_rules_panel.setMinimumHeight(120)
        agents_tab = QWidget()
        agents_tab_layout = QVBoxLayout(agents_tab)
        agents_tab_layout.setContentsMargins(0, 0, 0, 0)
        agents_tab_layout.setSpacing(TOKENS["space"]["2"])
        agents_tab_layout.addWidget(self.agents_widget, 3)
        agents_tab_layout.addWidget(self.entropy_rules_panel, 1)
        self.agents_tab = agents_tab
        self.left_tabs.addTab(agents_tab, "Ajanlar", "robot")

        # Yaşam tarzı arayüz (Faz 5.5): "bugün ne oldu" zaman çizelgesi.
        self.timeline_panel = TimelinePanel()
        self.timeline_panel.event_activated.connect(self._on_timeline_activated)
        self.left_tabs.addTab(self.timeline_panel, "Bugün", "calendar")

        # Bildirimler bölümü: merkez sütundaki ayrı bildirim tepsisi (denetim
        # D-09: rapor/bildirim bilgisi 8 ayrı yüzeyde tekrarlanıyordu) buraya
        # taşındı. Artık duran rapor yüzeyi iki tane: "Raporlar & Notlar" ve
        # "Bildirimler"; kalanı geçici bir bildirim balonu.
        self.notification_center = NotificationCenter()
        self.notification_center.notification_activated.connect(self._on_notification_activated)

        self.notification_scroll = QScrollArea()
        self.notification_scroll.setWidgetResizable(True)
        self.notification_scroll.setMaximumHeight(115)
        self.notification_stack_widget = QWidget()
        self.notification_stack_layout = QVBoxLayout(self.notification_stack_widget)
        self.notification_stack_layout.setContentsMargins(
            TOKENS["space"]["2"], TOKENS["space"]["2"],
            TOKENS["space"]["2"], TOKENS["space"]["2"],
        )
        self.notification_stack_layout.setSpacing(TOKENS["space"]["1"])
        self.notification_stack_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.notification_scroll.setWidget(self.notification_stack_widget)
        self.notification_scroll.setVisible(False)

        notifications_tab = QWidget()
        notifications_layout = QVBoxLayout(notifications_tab)
        notifications_layout.setContentsMargins(0, 0, 0, 0)
        notifications_layout.setSpacing(TOKENS["space"]["2"])
        notifications_layout.addWidget(self.notification_scroll)
        notifications_layout.addWidget(self.notification_center, 1)
        self.notifications_tab = notifications_tab
        self.left_tabs.addTab(notifications_tab, "Bildirimler", "bell")

        # Sol bölge = gezinme + içerik + durum şeridi (çekirdek merkezden
        # üst çubuğa indiği için merkez sütun kaldırıldı; alan içeriğe gitti).
        left_region = QWidget()
        left_region.setObjectName("navRegion")
        left_layout = QVBoxLayout(left_region)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(TOKENS["space"]["2"])
        left_layout.addWidget(self.left_tabs, 1)
        left_layout.addWidget(self._build_status_strip())
        top_h_splitter.addWidget(left_region)

        # Sağ bölge: düğüm-bağ bilgi grafiği (hafıza).
        self.knowledge_graph = KnowledgeGraphWidget(parent=self, vault_manager=self.reports_viewer.vault_manager)
        top_h_splitter.addWidget(self.knowledge_graph)

        # Panellerin örtük minimumSizeHint'i (sekme başlıkları, uzun etiketler, araç
        # çubukları) toplamda ~3070 px istiyordu; QSplitter bir çocuğu minimumundan
        # daha dar yapamadığı için pencere 1920 px'lik ekranda taşıyordu. Açık ve
        # küçük minimumlar vererek düzenin ekrana uymasını garanti ediyoruz; panel
        # içerikleri kendi kaydırma alanlarında daralır.
        for _panel, _min_w in ((left_region, 320), (self.knowledge_graph, 260)):
            _panel.setMinimumWidth(_min_w)

        top_h_splitter.setSizes([880, 400])
        main_v_splitter.addWidget(top_h_splitter)

        # Alt bölge: sohbet (terminal artık onun içinde katlanır çekmece).
        # 1. Left Side: Full Interactive Chat Panel
        chat_card = QFrame()
        chat_card.setObjectName("cardFrame")
        chat_layout = QVBoxLayout(chat_card)
        chat_layout.setContentsMargins(12, 8, 12, 8)
        chat_layout.setSpacing(6)

        # Panel başlığı: cümle düzeni, dört kademeli tipografi (BÜYÜK HARF yok).
        chat_hdr = QHBoxLayout()
        chat_hdr.setSpacing(TOKENS["space"]["2"])
        chat_title = QLabel("Sohbet")
        chat_title.setProperty("role", "heading")
        chat_hdr.addWidget(chat_title)

        # Rapor hazır balonu (geçici bildirim) başlık şeridinde durur.
        self.zen_report_bubble = QPushButton("Rapor hazır")
        self.zen_report_bubble.setProperty("variant", "ghost")
        self.zen_report_bubble.setAccessibleName("Hazır raporu aç")
        self.zen_report_bubble.setVisible(False)
        self.zen_report_bubble.clicked.connect(self._open_latest_zen_report)
        chat_hdr.addWidget(self.zen_report_bubble)
        chat_hdr.addStretch()

        btn_new_chat_zen = QPushButton("Yeni sohbet")
        btn_new_chat_zen.setProperty("variant", "ghost")
        btn_new_chat_zen.setAccessibleName("Yeni sohbet")
        btn_new_chat_zen.clicked.connect(self._on_new_chat)
        chat_hdr.addWidget(btn_new_chat_zen)

        self.terminal_toggle_btn = QPushButton("Terminal")
        self.terminal_toggle_btn.setProperty("variant", "ghost")
        self.terminal_toggle_btn.setCheckable(True)
        self.terminal_toggle_btn.setAccessibleName("Terminal çekmecesi")
        self.terminal_toggle_btn.setToolTip("Terminal çekmecesini aç/kapat (Ctrl+`)")
        self.terminal_toggle_btn.clicked.connect(self.toggle_terminal_drawer)
        chat_hdr.addWidget(self.terminal_toggle_btn)
        chat_layout.addLayout(chat_hdr)

        # Chat Browser
        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(False)
        # Faz 9: `setOpenLinks(False)` olmadan QTextBrowser `entropy-report://`
        # bağlantısını kendi belgesi sanıp yüklemeye çalışıyor; günlüğe
        # "No document for entropy-report://..." uyarısı basıyor ve sohbet
        # görünümünü boşaltabiliyordu. Bağlantıyı yalnızca biz açıyoruz.
        self.chat_browser.setOpenLinks(False)
        self.chat_browser.anchorClicked.connect(self._on_anchor_clicked)
        # Faz 11-C: `task_report_ready` -> sohbette rapor karti + "Sohbete al".
        self.install_report_cards()
        # Faz 11-E: yerel stil yerine rol sınıfı (QSS `QTextBrowser[role="reader"]`).
        self.chat_browser.setProperty("role", "reader")
        self.chat_browser.setAccessibleName("Sohbet akışı")
        # Faz 4 (2d/2f): sohbet gövdesi rapor okuyucu ve Agent Desk akış
        # paneliyle aynı tipografiyi kullanır. Belge stil sayfası verilmezse
        # komut kartı içindeki çıplak <table> (ör. /lint, /wiki çıktıları) Qt
        # varsayılanıyla, kalın beyaz kenarlıklarla çizilirdi.
        self.chat_browser.document().setDefaultStyleSheet(reading_css())
        chat_layout.addWidget(self.chat_browser)

        # Staged image preview bar
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
        chat_layout.addWidget(self.attachment_bar)

        # Chat Input Bar
        chat_input_bar = QHBoxLayout()
        self.chat_input = ChatInputField(self)
        self.chat_input.setPlaceholderText("Mesajınızı yazın veya Ctrl+V ile görsel yapıştırın…")
        self.chat_input.setAccessibleName("Mesaj alanı")
        self.chat_input.returnPressed.connect(self._on_send_chat)
        chat_input_bar.addWidget(self.chat_input)

        self.chat_pdf_btn = QPushButton("PDF")
        self.chat_pdf_btn.setToolTip("Finansal rapor ya da PDF belgesi ekle")
        self.chat_pdf_btn.setAccessibleName("PDF ekle")
        self.chat_pdf_btn.clicked.connect(self._select_pdf_file)
        chat_input_bar.addWidget(self.chat_pdf_btn)

        self.chat_send_btn = QPushButton("Gönder")
        self.chat_send_btn.setProperty("variant", "primary")
        self.chat_send_btn.setAccessibleName("Gönder")
        self.chat_send_btn.setToolTip("Mesajı gönder (Ctrl+Enter)")
        self.chat_send_btn.clicked.connect(self._on_send_chat)
        chat_input_bar.addWidget(self.chat_send_btn)
        chat_layout.addLayout(chat_input_bar)

        # Terminal artik alt yarinin yarisini surekli isgal eden bir sutun
        # degil, katlanir cekmece (denetim D-11: bos terminal alt yarinin
        # %45'ini kapliyordu). Varsayilan kapali; Ctrl+` ile acilir.
        self.terminal_pane = TerminalPaneWidget(title="Canlı çıktı akışı ve terminal")
        self.terminal_pane.setMinimumWidth(240)
        self.terminal_pane.setVisible(False)
        chat_layout.addWidget(self.terminal_pane, 1)

        # Aliases for input controls
        self.prompt_input = self.chat_input
        self.submit_btn = self.chat_send_btn

        main_v_splitter.addWidget(chat_card)
        chat_card.setMinimumWidth(260)
        main_v_splitter.setSizes([520, 340])
        root_layout.addWidget(main_v_splitter)

        # Odak modu (Ctrl+Shift+F): tek panel. Sohbet kalir, yan paneller
        # gizlenir; cikista eski gorunurluk aynen geri gelir.
        self.focus_mode = install_focus_mode(
            self,
            primary=chat_card,
            secondary=[left_region, self.knowledge_graph, self.terminal_pane],
        )
        # Komut paleti (Ctrl+K): komutlar, yetenekler, ajanlar, ofisler,
        # raporlar **ve pencere eylemleri** (Desk, proje, yeni sohbet, kip).
        install_command_palette(
            self, on_activated=self._on_palette_activated,
            loader=self._collect_palette_items,
        )
        self._install_shortcuts()

        self._load_chat_history()
        self._load_persisted_session_to_terminal()

    def _apply_header_density(self) -> None:
        """Pencere darsa üst çubuğu sıkıştırır (aşamalı açığa çıkarma).

        Eşik 620 px: bunun altında token/bağlam rozetleri gizlenir ve model
        kapsülü kısa ada döner; ikisi de ipucunda ve komut paletinde durur.
        """
        compact = self.width() < 620
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

    def _build_status_strip(self) -> QWidget:
        """Sol bölgenin altındaki tek satırlık durum şeridi.

        Merkez sütundaki dört telemetri rozeti (denetim D-10: hepsinin başka
        bir yüzeyde karşılığı vardı) burada tek satıra iner ve rozet/chip rolü
        alır; ayrıca Desk ve proje düğmeleri bu şeritte durur.
        """
        strip = QFrame()
        strip.setObjectName("statusStrip")
        strip.setProperty("role", "panel")
        row = QHBoxLayout(strip)
        row.setContentsMargins(
            TOKENS["space"]["2"], TOKENS["space"]["1"],
            TOKENS["space"]["2"], TOKENS["space"]["1"],
        )
        row.setSpacing(TOKENS["space"]["1"])

        self.zen_telemetry_status = QLabel("Sistem hazır")
        self.zen_telemetry_status.setProperty("role", "statusDot")
        self.zen_telemetry_status.setProperty("tone", "ok")
        self.zen_telemetry_status.setAccessibleName("Sistem durumu")
        row.addWidget(self.zen_telemetry_status)

        self.badge_memory = QLabel("Bellek: 0 Düğüm")
        self.badge_skills = QLabel("Yetenekler: 0 Aktif")
        self.badge_mcp = QLabel("MCP: Pasif")
        initial_model = self.bridge.selected_model or config.model_fallback_name
        self.badge_model = QLabel(f"[{initial_model}]")
        for badge, name in (
            (self.badge_memory, "Bellek"),
            (self.badge_skills, "Yetenekler"),
            (self.badge_mcp, "MCP"),
            (self.badge_model, "Model"),
        ):
            badge.setProperty("role", "badge")
            badge.setAccessibleName(name)
            row.addWidget(badge)

        row.addStretch()
        row.addWidget(self.project_btn)
        row.addWidget(self.desk_btn)

        self.core_status_lbl = QLabel("Entropy AI")
        self.core_status_lbl.setProperty("role", "label")
        self.core_status_lbl.setVisible(False)
        row.addWidget(self.core_status_lbl)
        return strip

    def _sync_model_capsule(self) -> None:
        """Kapsül metnini köprüden tazeler (tek kaynak)."""
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
        """Komut paletini açar (üst çubuk düğmesi ve Ctrl+K aynı yolu kullanır)."""
        opener = getattr(self, "_open_command_palette", None)
        if callable(opener):
            opener()

    def _collect_palette_items(self):
        """Palet kaynakları + üst çubuktan taşınan pencere eylemleri.

        Denetim IA-9: paletin birincil gezinme olması için çubuktan kaldırılan
        her düğmenin palette bir karşılığı olmalı.
        """
        from entropy.ui.widgets.command_palette import collect_palette_items

        actions = [
            ("desk", "Agent Desk'i aç", "Ofis masası: ajan ofisleri, kanban, canlı akış"),
            ("project", "Proje klasörünü değiştir", "Aktif proje dizini"),
            ("new_chat", "Yeni sohbet", "Mevcut sohbeti arşivler"),
            ("terminal", "Terminal çekmecesini aç/kapat", "Ctrl+`"),
            ("mode_chat", "Chat kipine geç", "Ctrl+2"),
            ("mode_floating", "Floating kipine geç", "Ctrl+3"),
            ("mode_zen", "Zen kipine geç", "Ctrl+1"),
            ("nav_reports", "Bölüm: Raporlar & Notlar", "Sol gezinme"),
            ("nav_skills", "Bölüm: Yetenekler", "Sol gezinme"),
            ("nav_tasks", "Bölüm: Görevler", "Sol gezinme"),
            ("nav_mcp", "Bölüm: MCP Sunucuları", "Sol gezinme"),
            ("nav_agents", "Bölüm: Ajanlar", "Sol gezinme"),
            ("nav_today", "Bölüm: Bugün", "Sol gezinme"),
            ("nav_notifications", "Bölüm: Bildirimler", "Sol gezinme"),
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

    def run_palette_action(self, key: str) -> bool:
        """Palet eylemi yürütür; bilinmeyen anahtar için False döner."""
        if key == "desk":
            self.open_agent_desk()
        elif key == "project":
            self._select_project_dir()
        elif key == "new_chat":
            self._on_new_chat()
        elif key == "terminal":
            self.toggle_terminal_drawer()
        elif key.startswith("mode_"):
            bus.mode_requested.emit(key.split("_", 1)[1])
        elif key.startswith("nav_"):
            index = {
                "nav_reports": 0, "nav_skills": 1, "nav_tasks": 2, "nav_mcp": 3,
                "nav_agents": 4, "nav_today": 5, "nav_notifications": 6,
            }.get(key)
            if index is None:
                return False
            self.left_tabs.setCurrentIndex(index)
        else:
            return False
        return True

    def _install_shortcuts(self) -> None:
        """Klavye kısayolları (denetim D-20: tüm uygulamada yalnızca 2 vardı)."""
        from PySide6.QtGui import QKeySequence, QShortcut

        self._shortcuts = []
        bindings = (
            ("Ctrl+1", "nav_reports"),
            ("Ctrl+2", "nav_skills"),
            ("Ctrl+3", "nav_tasks"),
            ("Ctrl+`", "terminal"),
            ("Ctrl+N", "new_chat"),
        )
        for seq, key in bindings:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setProperty("action_key", key)
            shortcut.activated.connect(self._on_shortcut)
            self._shortcuts.append(shortcut)
        send = QShortcut(QKeySequence("Ctrl+Return"), self)
        send.activated.connect(self._on_send_chat)
        self._shortcuts.append(send)

    @Slot()
    def _on_shortcut(self) -> None:
        """Kısayol alıcısı: lambda değil QObject slotu (doğrudan bağlantı olmaz)."""
        sender = self.sender()
        if sender is None:
            return
        self.run_palette_action(str(sender.property("action_key") or ""))

    @Slot()
    def toggle_terminal_drawer(self) -> None:
        """Terminal çekmecesini açar/kapatır (varsayılan kapalı)."""
        pane = getattr(self, "terminal_pane", None)
        if pane is None:
            return
        visible = not pane.isVisible()
        pane.setVisible(visible)
        btn = getattr(self, "terminal_toggle_btn", None)
        if btn is not None:
            btn.setChecked(visible)

    def _load_persisted_session_to_terminal(self):
        """Restore full conversation history to the terminal pane on launch."""
        try:
            filtered_history = config_module.load_chat_history()
            if filtered_history:
                cid = f" (Oturum ID: {self.bridge.current_conversation_id[:8]}...)" if self.bridge.current_conversation_id else ""
                self.terminal_pane.append_output(f"════════════════ [AKTİF SOHBET GEÇMİŞİ YÜKLENDİ{cid} - {len(filtered_history)} Mesaj] ════════════════\n")
                for turn in filtered_history:
                    role = "SİZ" if turn.get("role") == "user" else f"ENTROPY CORE [{self.bridge.selected_model}]"
                    content = turn.get("content", "").strip()
                    self.terminal_pane.append_output(f"\n▶ [{role}]:\n{content}\n")
                self.terminal_pane.append_output("\n════════════════ [CANLI ÇIKTI AKIŞI BAŞLATILDI] ════════════════\n\n")
        except Exception:
            pass

    def _connect_signals(self):
        bus.model_detected.connect(self._update_model_badge)
        bus.token_usage_updated.connect(self._update_tokens)
        # Ek-1 (Faz 9): koprunun ayrintili token sozlugu (oturum/tur/onbellek).
        bus.token_usage_detail.connect(self._on_token_detail)
        bus.core_state_changed.connect(self._update_status)
        bus.node_selected.connect(self._on_node_selected)
        bus.agent_turn_started.connect(self._on_turn_started)
        bus.token_chunk_received.connect(self._on_chunk)
        bus.agent_turn_completed.connect(self._on_agent_turn_completed)
        bus.report_created.connect(self._on_report_created)
        bus.task_notification.connect(self._on_task_notification)
        bus.cognitive_memory_updated.connect(self._update_telemetry_badges)
        bus.skills_updated.connect(self._update_telemetry_badges)
        bus.project_changed.connect(self._on_project_changed)
        # Sohbet gecmisi tek kaynak: Chat modu ile ayni dosyayi dinler.
        bus.chat_history_updated.connect(self._on_chat_history_updated)
        bus.chat_history_cleared.connect(self._on_chat_history_cleared)
        bus.context_pressure.connect(self._on_context_pressure)
        self._update_telemetry_badges()

    def add_notification_pill(self, title: str, path_or_content: str, is_task: bool = False):
        """Add a stackable notification pill to the center column with duplicate prevention."""
        # Check if already present in active stack
        for i in range(self.notification_stack_layout.count()):
            item = self.notification_stack_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), NotificationPillWidget):
                w = item.widget()
                if getattr(w, "path_or_content", None) == path_or_content or getattr(w, "title", None) == title:
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
        self.zen_report_bubble.setText(f"{'Görev' if is_task else 'Rapor'}: {title}")
        self.zen_report_bubble.setVisible(True)

    def _remove_notification_pill(self, pill: NotificationPillWidget):
        """Dismiss and remove a specific notification pill."""
        self.notification_stack_layout.removeWidget(pill)
        pill.deleteLater()
        if self.notification_stack_layout.count() == 0:
            self.notification_scroll.setVisible(False)
            self.zen_report_bubble.setVisible(False)

    @Slot(str)
    def _on_report_created(self, path_str: str):
        """Display floating notification pill in center column and rich card in chat with deduplication."""
        p = Path(path_str)
        self.latest_report_path = str(p)

        # Deduplication check: ignore if this exact path was notified in the last 10 seconds
        import time
        now = time.time()
        if not hasattr(self, "_recent_notifications"):
            self._recent_notifications = {}
        self._recent_notifications = {k: v for k, v in self._recent_notifications.items() if now - v < 10.0}
        norm_key = str(p.resolve()).lower()
        if norm_key in self._recent_notifications:
            return
        self._recent_notifications[norm_key] = now

        self.add_notification_pill(title=p.stem, path_or_content=str(p), is_task=False)

        card_html = (
            f"<div style='background-color:#0E1420; border:1px solid #00F0FF; border-radius:8px; padding:10px 14px; margin:8px 0;'>"
            f"<div style='color:#00F0FF; font-size:11px; font-weight:bold; letter-spacing:0.8px;'>Yeni Araştırma Raporu Oluşturuldu</div>"
            f"<div style='color:#F0F6FC; font-size:13px; font-weight:bold; margin:4px 0;'>{p.stem}</div>"
            f"<div style='color:#8B949E; font-size:11px; margin-bottom:8px;'>Dosya: {p.name} | Bilişsel Hafıza ve RAG'a İşlendi</div>"
            f"<a href='entropy-report://{p.as_posix()}' style='display:inline-block; background-color:#00F0FF; color:#080B10; font-weight:bold; font-size:11px; text-decoration:none; padding:5px 14px; border-radius:4px;'>Raporu Aç ve Oku ↗</a>"
            f"</div>"
        )
        self.chat_browser.append(card_html)

    @Slot(str, str, str)
    def _on_task_notification(self, task_id: str, task_name: str, path_or_content: str):
        """Handle task execution and result notification with deduplication."""
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
            card_html += f"<a href='entropy-report://{p.as_posix()}' style='display:inline-block; background-color:#00FF9D; color:#080B10; font-weight:bold; font-size:11px; text-decoration:none; padding:5px 14px; border-radius:4px;'>Görev Raporunu Aç ↗</a>"
        card_html += "</div>"
        self.chat_browser.append(card_html)

    def _open_latest_zen_report(self):
        if hasattr(self, "latest_report_path") and self.latest_report_path:
            self._open_report_path(self.latest_report_path)

    def _open_report_path(self, path_str: str):
        if not hasattr(self, "standalone_report_window") or self.standalone_report_window is None:
            self.standalone_report_window = StandaloneReportWindow(self)
        self.standalone_report_window.open_report_file(path_str)

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

    def _update_telemetry_badges(self):
        """Dynamically refresh telemetry metric badges in the center column."""
        try:
            from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
            from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
            from entropy.skills.manager import SkillManager
            from entropy.mcp.manager import MCPManager

            mem = CognitiveMemorySystem()
            cog_nodes = mem.get_all_nodes()
            ovm = ObsidianVaultManager()
            notes = ovm.list_all_notes()
            total_count = len(cog_nodes) + len(notes)

            if hasattr(self, "badge_memory"):
                # İki ayrı depo tek "Düğüm" etiketinde toplandığında sayı yanıltıcı
                # oluyordu (ör. 1526, ama bilişsel bellekte yalnızca 825 düğüm var).
                # Rozet artık ikisini ayrı gösteriyor.
                self.badge_memory.setText(f"{len(cog_nodes)} düğüm / {len(notes)} not")
                self.badge_memory.setToolTip(
                    f"Bilişsel Bellek (SQLite): {len(cog_nodes)} düğüm\n"
                    f"Obsidian Kasası (markdown): {len(notes)} dosya\n"
                    f"Toplam kayıt: {total_count}"
                )

            if hasattr(self, "skills_widget") and self.skills_widget:
                active_skills = [s for s in self.skills_widget.skill_manager.list_skills() if s.enabled]
            else:
                sm = SkillManager(project_dir=self.bridge.active_project_dir)
                active_skills = [s for s in sm.list_skills() if s.enabled]
            if hasattr(self, "badge_skills"):
                self.badge_skills.setText(f"Yetenekler: {len(active_skills)} aktif")
                skill_names = ", ".join([s.name for s in active_skills])
                self.badge_skills.setToolTip(f"Aktif Yetenekler ({len(active_skills)}):\n{skill_names}")

            mcp_mgr = MCPManager()
            mcp_servers = mcp_mgr.list_servers()
            active_mcp = sum(1 for s in mcp_servers if s.get("status") in ["enabled", "active", "connected"])
            if hasattr(self, "badge_mcp"):
                self.badge_mcp.setText(f"MCP: {active_mcp} aktif" if active_mcp > 0 else "MCP: pasif")
                mcp_names = ", ".join([s["name"] for s in mcp_servers if s.get("status") in ["enabled", "active", "connected"]])
                self.badge_mcp.setToolTip(f"Aktif MCP Sunucuları ({active_mcp}):\n{mcp_names}")

            if hasattr(self, "badge_model"):
                cur_model = self.bridge.selected_model or config.model_fallback_name
                clean_model = cur_model.strip("[]")
                self.badge_model.setText(f"[{clean_model}]")
        except Exception:
            pass

    @Slot(str)
    def _on_node_selected(self, node_id: str):
        """Handle clicking any node in the knowledge graph: opens the rich inspector panel in front of the user."""
        # Rapor düğümüyse okuyucuda aç ve Raporlar sekmesini öne getir.
        opened = self.reports_viewer.open_report_by_path_or_id(node_id)
        if opened and hasattr(self, "left_tabs"):
            self.left_tabs.setCurrentWidget(self.reports_viewer)

        # Open dedicated Memory & Context Inspector Panel in front of the user
        from entropy.ui.widgets.memory_inspector_dialog import MemoryInspectorDialog
        dialog = MemoryInspectorDialog(node_id, self)
        dialog.exec()

    @Slot(str)
    def _update_model_badge(self, model_name: str):
        if self.model_combo.currentText() != model_name:
            self.model_combo.setCurrentText(model_name)
        if hasattr(self, "badge_model"):
            clean_name = (model_name or config.model_fallback_name).strip("[]")
            self.badge_model.setText(f"[{clean_name}]")

    def _on_model_selected(self, model_name: str):
        # Faz 9: kutu serbest metin kabul ediyor; yalnızca ETKİN sağlayıcıya
        # ait bir ad köprüye geçirilir. Köprünün yazma kapısı (set_model)
        # reddederse kutu eski değerine döner — aksi halde arayüz seçili
        # görünen ama hiç uygulanmayan bir model gösteriyordu.
        if model_name and model_name != self.bridge.selected_model:
            from entropy.ui.widgets.ui_polish import accept_model_selection

            if not accept_model_selection(self.bridge, self.model_combo, model_name):
                return
        if hasattr(self, "badge_model"):
            clean_name = (model_name or config.model_fallback_name).strip("[]")
            self.badge_model.setText(f"[{clean_name}]")
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

    def refresh_provider_ui(self):
        """
        Sağlayıcı değiştiğinde model listesini tazeler.

        Üst çubukta Chat kipiyle aynı sağlayıcı seçicisi bulunur; burada hem
        seçim hem de yeni köprünün model listesi yansıtılır.
        """
        if hasattr(self, "provider_combo"):
            try:
                self.provider_combo.blockSignals(True)
                self.provider_combo.setCurrentText(getattr(self.bridge, "provider_name", "agy"))
            finally:
                self.provider_combo.blockSignals(False)
        if not hasattr(self, "model_combo"):
            return
        try:
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            for m in self.bridge.fetch_available_models():
                self.model_combo.addItem(m)
            self.model_combo.setCurrentText(self.bridge.selected_model)
        finally:
            self.model_combo.blockSignals(False)
        # Faz 9: yeni saglayicinin model adlari daha uzun olabilir; kutuyu yeniden olc.
        fit_combo_to_contents(self.model_combo, min_width=180)
        self._refresh_effort_combo()

    @Slot(int)
    def _update_tokens(self, tokens: int):
        # Sohbet ve arka plan kalemleri her zaman ayrı ve adıyla gösterilir;
        # biçim chat_mode ile ortak (ui/widgets/token_badge.py).
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
        """Baskı sinyali: rozeti son bilinen oranla tazeler."""
        self._last_context_pressure = float(ratio or 0.0)
        self._apply_context_badge()

    @Slot(str, str)
    def _on_orchestrator_answer(self, office: str, body: str):
        """
        "Orkestratore sor" yaniti sohbete "<ofis>" balonuyla duser.

        Yanit sohbete yazilir cunku bu bir diyalogdur: soru ve cevap ayni akista
        kalmali, kartin icinde kaybolmamali.
        """
        from entropy.ui.widgets.markdown_renderer import build_chat_bubble_html

        self.chat_browser.append(
            build_chat_bubble_html(f"{office}", str(body or ""))
        )

    @Slot(str, str, str)
    def _on_palette_activated(self, kind: str, payload: str, label: str):
        """
        Komut paleti secimi. Rapor acilir, kalan her sey giris satirina yazilir;
        palet hicbir seyi kendiliginden calistirmaz (yanlis tiklama kota yakar).
        """
        if kind == "report":
            self._open_report_path(payload)
            return
        if kind == "action":
            self.run_palette_action(payload)
            return
        self.chat_input.setText(payload if payload.endswith(" ") else payload + " ")
        self.chat_input.setFocus()

    @Slot(str, str)
    def _on_timeline_activated(self, kind: str, target: str):
        """Zaman cizelgesi satiri: rapor/aktarim okuyucuda, pano olayi kartta acilir."""
        if kind in ("report", "handoff") and target:
            self._open_report_path(target)
            return
        # Faz 11-C: pano olayina tiklaninca Gorevler sekmesi acilir ve olayin
        # karti secilir (detay panelinde hedef/olcut/kanit gorunur).
        if kind == "board" and target:
            self.open_task_card(target)

    def open_task_card(self, card_id: str) -> bool:
        """Gorevler sekmesine gecer ve karti secer; kart yoksa False."""
        board = getattr(self, "task_board_widget", None)
        if board is None or not card_id:
            return False
        index = self.left_tabs.indexOf(self.tasks_tab)
        if index >= 0:
            self.left_tabs.setCurrentIndex(index)
        board.flush_board_events()
        if board.get_card(card_id) is None:
            board.refresh_cards()
        if board.get_card(card_id) is None:
            return False
        board.select_card(card_id)
        return True

    @Slot(str, str)
    def _on_notification_activated(self, target_kind: str, target: str):
        """Bildirim: rapor acilir, yetenek/ajan ilgili sekmeye goturur."""
        if target_kind == "report" and target:
            self._open_report_path(target)
            return
        tab_map = {
            "skill": self.skills_widget,
            "agent": self.agents_widget,
            "task": getattr(self, "tasks_tab", None),
        }
        widget = tab_map.get(target_kind)
        if widget is not None:
            index = self.left_tabs.indexOf(widget)
            if index >= 0:
                self.left_tabs.setCurrentIndex(index)

    @Slot(str)
    def _on_provider_login_requested(self, provider: str):
        """Saglayici rozetine tiklandi: giris komutunu giris satirina yazar."""
        self.chat_input.setText(f"/login {provider} ")
        self.chat_input.setFocus()

    @Slot(int)
    def _on_inbox_unread(self, count: int):
        """Rapor Merkezi rozetini günceller (sinyal alıcısı QObject slotu)."""
        if hasattr(self, "inbox_badge"):
            self.inbox_badge.set_count(count)

    def _apply_context_badge(self):
        """Bağlam doluluk rozetinin metni, ipucu ve rengi (tek yerden)."""
        from entropy.ui.widgets.token_badge import format_context_badge

        if not hasattr(self, "context_badge"):
            return
        text, tip, color = format_context_badge(
            self.bridge, getattr(self, "_last_context_pressure", 0.0)
        )
        self.context_badge.setText(text)
        self.context_badge.setToolTip(tip)
        # Faz 11-E: renk yerel QSS ile değil `tone` belirteciyle gelir.
        self.context_badge.setProperty("tone", context_badge_tone(color))
        _repolish(self.context_badge)

    def _on_provider_selected(self, provider: str):
        """Sağlayıcı seçimi: Chat kipiyle aynı yönetici yolunu kullanır."""
        if not provider or provider == getattr(self.bridge, "provider_name", "agy"):
            return
        from entropy.ui.manager import EntropyUIManager

        manager = EntropyUIManager.instance
        if manager is None:
            return
        manager.switch_provider(provider)

    @Slot(str)
    def _update_status(self, state: str):
        # Faz 11-E: durum tek noktada — üst çubuktaki çekirdek noktası.
        # Merkezdeki büyük durum etiketi kaldırıldı (denetim D-10/D-11).
        label = {
            "thinking": "Entropy AI (Düşünüyor...)",
            "executing": "Entropy AI (Yürütülüyor...)",
            "error": "Entropy AI (Hata)",
        }.get(state, "Entropy AI")
        self.core_status_lbl.setText(label)
        brand = getattr(self, "brand", None)
        if brand is not None:
            brand.set_state(state)

    def _on_project_changed(self, new_dir: str):
        self.project_btn.setText(Path(new_dir).name)
        if hasattr(self, "reports_viewer") and self.reports_viewer:
            self.reports_viewer.active_project_dir = Path(new_dir)
            self.reports_viewer.refresh_reports()
        if hasattr(self, "skills_widget") and self.skills_widget:
            self.skills_widget._on_project_changed(new_dir)
        self._update_telemetry_badges()

    def open_agent_desk(self):
        """
        Agent Desk penceresini açar (tek örnek).

        Ağır modüller (sahne, ofis kayıt defteri) yalnızca kullanıcı düğmeye
        basınca yüklensin diye içe aktarma fonksiyon içinde: Zen açılışı
        yavaşlamasın.
        """
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


    def _on_submit_prompt(self):
        text = self.prompt_input.text().strip()
        if text:
            self.prompt_input.clear()
            self.chat_input.setText(text)
            self._on_send_chat()

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
                    imported = self.skills_widget.skill_manager.import_skill_from_source(local_path)
                    if imported:
                        self.terminal_pane.append_output(f"\n[Yetenek Merkezi] Sürüklenen yetenek başarıyla yüklendi: {imported.name}\n")
                        self.zen_telemetry_status.setText(f"<span style='color:#00FF9D; font-weight:bold; font-size:11px;'>Yetenek Eklendi: {imported.name}</span>")
                        self._update_telemetry_badges()

        elif event.mimeData().hasText():
            text = event.mimeData().text().strip()
            if (text.startswith("http://") or text.startswith("https://")) and ("github.com" in text or text.endswith(".md") or text.endswith(".zip")):
                imported = self.skills_widget.skill_manager.import_skill_from_source(text)
                if imported:
                    self.terminal_pane.append_output(f"\n[Yetenek Merkezi] URL'den yetenek başarıyla yüklendi: {imported.name}\n")
                    self.zen_telemetry_status.setText(f"<span style='color:#00FF9D; font-weight:bold; font-size:11px;'>Yetenek Eklendi: {imported.name}</span>")
                    self._update_telemetry_badges()

    def _on_send_chat(self):
        import html
        prompt = self.chat_input.text().strip()
        if not prompt and not self.staged_images and not self.staged_pdfs:
            return

        # Check if user passed a skill URL / repo / file in chat
        from entropy.skills.manager import SkillManager, extract_skill_source_from_text
        skill_src = extract_skill_source_from_text(prompt)
        if skill_src:
            sm = SkillManager(project_dir=self.bridge.active_project_dir)
            imported = sm.import_skill_from_source(skill_src)
            if imported:
                self.terminal_pane.append_output(f"\n[Yetenek Merkezi] '{imported.name}' yeteneği sisteme başarıyla kuruldu.\n")
                self.zen_telemetry_status.setText(f"<span style='color:#00FF9D; font-weight:bold; font-size:11px;'>Yetenek Eklendi: {imported.name}</span>")
                self._update_telemetry_badges()

        # Check slash command handling (supports multiple slash commands in prompt)
        matched_cmds: List[SlashCommand] = []
        active_skill = None
        # Faz 9: istemden temizlenecek yetenek slash token'ları.
        skill_tokens_used: List[str] = []
        slash_tokens = re.findall(r'(?:^|\s)/([a-zA-Z0-9_\-:]+)', prompt)

        if slash_tokens:
            # Uygulama içinde yürütülen komutlar (AGY'ye gitmez). Argüman alabildikleri
            # için aşağıdaki "tek token" dalından önce kontrol edilir.
            from entropy.core.slash_commands import try_handle_local_command
            local_html = try_handle_local_command(prompt, self.bridge)
            if local_html is not None:
                # Yerel komut çıktısı (ör. /handoff) okunur kart olarak basılır.
                from entropy.ui.widgets.markdown_renderer import build_command_card_html

                self.chat_browser.append(build_command_card_html(local_html))
                # Model/efor degistiren komutlardan sonra ust cubuk tazelenir.
                self.sync_model_effort_ui()
                self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)
                self.chat_input.clear()
                return

            if len(slash_tokens) == 1 and prompt.strip() == f"/{slash_tokens[0]}":
                single_tok = slash_tokens[0]
                if single_tok == "clear":
                    self.chat_browser.clear()
                    self.terminal_pane.clear_terminal()
                    self._append_chat_message("Entropy AI", "Sohbet ve terminal ekranı sıfırlandı.")
                    self.chat_input.clear()
                    return
                elif single_tok == "help":
                    reg = SlashCommandRegistry(mcp_manager=default_mcp_manager)
                    all_c = reg.get_all_commands(self.bridge.active_project_dir)
                    help_html = [
                        "<div style='border:1px solid #1F2B42; background:#0A0E17; border-radius:6px; padding:10px; margin:6px 0;'>",
                        "<b style='color:#00F0FF; font-size:13px;'>KULLANILABİLİR KOMUTLAR, YETENEKLER VE MCP ARAÇLARI</b><br/><br/>"
                    ]
                    for c in all_c:
                        help_html.append(
                            f"<div style='margin-bottom:4px;'>"
                            f"<span style='background-color:{c.color}22; color:{c.color}; border:1px solid {c.color}55; border-radius:3px; padding:1px 5px; font-size:11px; font-weight:bold;'>{c.badge}</span> "
                            f"<b style='color:#F0F6FC; font-family:Consolas;'>{c.name}</b>: "
                            f"<span style='color:#8B949E; font-size:11px;'>{c.description}</span>"
                            f"</div>"
                        )
                    help_html.append("</div>")
                    self._append_chat_message("Entropy AI", "".join(help_html))
                    self.chat_input.clear()
                    return

            # Lookup commands across all registered skills, builtins, MCPs, and tools
            reg = SlashCommandRegistry(mcp_manager=default_mcp_manager)
            all_c = reg.get_all_commands(self.bridge.active_project_dir)
            cmds_by_token = {c.name[1:].lower() if c.name.startswith("/") else c.name.lower(): c for c in all_c}

            for tok in slash_tokens:
                c = cmds_by_token.get(tok.lower())
                if c and c not in matched_cmds:
                    matched_cmds.append(c)
                    if c.category == "skill":
                        detected_skill = c.metadata.get("skill_name") or tok
                        active_skill = detected_skill
                        skill_tokens_used.append(tok)

            # Faz 9: bilinmeyen slash CLI'a gitmesin (bkz. slash_prompt).
            unknown = unknown_slash_token(prompt, set(cmds_by_token), CLI_PASSTHROUGH)
            if unknown:
                self._append_chat_message(
                    "Entropy AI",
                    unknown_slash_html(unknown, close_matches(unknown, cmds_by_token)),
                    is_system=True,
                )
                self.chat_input.clear()
                return

            if matched_cmds:
                status_parts = []
                for mc in matched_cmds:
                    status_parts.append(f"<span style='color:{mc.color}; font-weight:bold; font-size:11px;'>{mc.badge}: {mc.name}</span>")
                self.zen_telemetry_status.setText(" ".join(status_parts))

        # Check auto-detection if not explicitly detected via slash
        if not active_skill:
            try:
                sm = SkillManager(project_dir=self.bridge.active_project_dir)
                detected = self.bridge.detect_skill_for_prompt(prompt, sm=sm)
                if detected:
                    self.zen_telemetry_status.setText(f"<span style='color:#00FF9D; font-weight:bold; font-size:11px;'>Yetenek Devrede: {detected.name}</span>")
                    active_skill = detected.name
            except Exception:
                pass

        escaped_prompt = html.escape(prompt).replace('\n', '<br/>')
        display_prompt = escaped_prompt

        badge_html = ""
        badge_spans = []
        if matched_cmds:
            for mc in matched_cmds:
                badge_spans.append(
                    f"<span style='background:#0E1420; color:{mc.color}; border:1px solid {mc.color}55; border-radius:3px; padding:2px 8px; font-size:11px; font-weight:bold; margin-right:4px;'>{mc.badge}: {html.escape(mc.name)}</span>"
                )
        skill_already_badged = any(mc.category == "skill" and (mc.metadata.get("skill_name") == active_skill or mc.name.lstrip("/") == active_skill) for mc in matched_cmds)
        if active_skill and not skill_already_badged:
            badge_spans.append(
                f"<span style='background:#0E1420; color:#00FF9D; border:1px solid #1F2B42; border-radius:3px; padding:2px 8px; font-size:11px; font-weight:bold;'>Yetenek: {html.escape(active_skill)}</span>"
            )
        if badge_spans:
            badge_html = f"<div style='margin-bottom:4px;'>{' '.join(badge_spans)}</div>"

        if badge_html:
            display_prompt = f"{badge_html}<div>{escaped_prompt}</div>"

        if self.staged_images:
            img_names = ", ".join([html.escape(Path(p).name) for p in self.staged_images])
            display_prompt += f" <div style='color:#00F0FF; font-size:11px; margin-top:2px;'><i>[Eklenen Görsel: {img_names}]</i></div>"
        if self.staged_pdfs:
            pdf_names = ", ".join([html.escape(Path(p).name) for p in self.staged_pdfs])
            display_prompt += f" <div style='color:#00FF9D; font-size:11px; margin-top:2px;'><i>[Eklenen PDF: {pdf_names}]</i></div>"

        self._append_chat_message("Siz", display_prompt)
        self.chat_input.clear()
        self.terminal_pane.append_output(f"\n▶ [SİZ]:\n{prompt}\n")

        images_to_send = list(self.staged_images)
        pdfs_to_send = list(self.staged_pdfs)
        self._clear_staged_images()

        actual_prompt = prompt
        # Faz 9: yetenek slash'ı arayüzde tüketildi; token istemde kalırsa CLI
        # onu komut sanıp "Unknown command" döndürüyor.
        if skill_tokens_used:
            actual_prompt = strip_skill_tokens(actual_prompt, skill_tokens_used)
            if not actual_prompt:
                self._append_chat_message(
                    "Entropy AI",
                    f"<b>Yetenek etkin:</b> {active_skill or skill_tokens_used[0]}"
                    " — şimdi ne yapmasını istediğinizi yazın.",
                    is_system=True,
                )
                return
        if images_to_send:
            actual_prompt += "\n" + "\n".join([f"[Eklenen Görsel Dosyası: {p}]" for p in images_to_send])

        if self.bridge.is_running:
            self._append_chat_message("Entropy AI", "⏳ <i>Önceki işlem tamamlanıyor, mesajınız sıraya alındı...</i>", is_system=True)
            self.terminal_pane.append_output("[Entropy Core] Önceki işlem tamamlanıyor, mesajınız sıraya alındı...\n")

        self.chat_send_btn.setEnabled(False)
        self.chat_input.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("İşleniyor...")

        has_plan = any(c.name == "/plan" for c in matched_cmds) or bool(re.search(r'(?:^|\s)/plan\b', prompt, re.IGNORECASE))
        # Faz 11-C: "Sohbete al" ile alinan rapor bloklari istemin basina
        # eklenir ve kuyruk bosaltilir (ayni rapor iki kez gitmez).
        actual_prompt = self.apply_report_context(actual_prompt)
        exec_mode = "plan" if has_plan else "accept-edits"
        self.bridge.send_prompt_async(
            prompt=actual_prompt,
            image_attachments=images_to_send,
            pdf_attachments=pdfs_to_send,
            active_skill=active_skill,
            mode=exec_mode
        )

    def _on_turn_started(self, prompt: str):
        self.chat_send_btn.setEnabled(False)
        self.chat_input.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("İşleniyor...")
        self._streaming_active = True
        self.chat_browser.append("<div style='margin-bottom:8px;'><b style='color:#00F0FF;'>Entropy AI:</b><br/></div>")
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)

    def _on_chunk(self, chunk: str):
        if getattr(self, "_streaming_active", False):
            cursor = self.chat_browser.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(chunk)
            self.chat_browser.setTextCursor(cursor)
            self.chat_browser.ensureCursorVisible()

    @Slot(str)
    def _on_agent_turn_completed(self, response: str):
        self._streaming_active = False
        self.chat_send_btn.setEnabled(True)
        self.chat_input.setEnabled(True)
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Çalıştır")
        self.chat_browser.append("<div style='margin-bottom:12px;'></div>")
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)

    def try_paste_image(self) -> bool:
        """Handle Ctrl+V image detection and staging."""
        res = self.clipboard_handler.save_clipboard_image()
        if res:
            path_str, w, h = res
            self.staged_images.append(path_str)
            filename = Path(path_str).name
            self.attach_label.setText(f"Yapıştırılan Görsel: <b>{filename}</b> ({w}x{h} px)")
            self.attachment_bar.setVisible(True)
            return True
        return False

    def _clear_staged_images(self):
        self.staged_images.clear()
        self.staged_pdfs.clear()
        self.attachment_bar.setVisible(False)

    def _append_chat_message(self, sender: str, text: str, is_system: bool = False):
        """Sohbet balonu uretir (Chat modu ile ayni tasarim sistemi, tek kaynak)."""
        from entropy.ui.widgets.markdown_renderer import build_chat_bubble_html
        self.chat_browser.append(build_chat_bubble_html(sender, text, is_system=is_system))
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)

    def _on_new_chat(self):
        """Sohbeti yalnızca burada, kullanıcının açık isteğiyle sıfırlar (arşivleyerek)."""
        self.bridge.reset_conversation()  # arşivler + bus.chat_history_cleared yayar

    @Slot()
    def _on_chat_history_cleared(self):
        """Sohbet arşivlendi: ekranı ve terminali temizle."""
        self.chat_browser.clear()
        try:
            self.terminal_pane.clear_output()
        except Exception:
            pass
        self._history_signature = config_module.chat_history_signature()
        self._append_chat_message(
            "Entropy AI",
            "Yeni sohbet oturumu başlatıldı. Önceki sohbet arşive alındı.",
            is_system=True,
        )

    @Slot()
    def _on_chat_history_updated(self):
        """Diske yeni tur yazıldı; pencere görünürse akış zaten ekranda, imzayı tazele."""
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
            self._append_chat_message(sender, content)
        self._history_signature = config_module.chat_history_signature()
        if self.chat_browser.toPlainText().strip() == "":
            self._append_chat_message("Entropy AI", "Zen Çalışma Alanı aktif. Size nasıl yardımcı olabilirim?", is_system=True)

    def _reload_chat_history_if_stale(self):
        """Pencere yeniden gösterildiğinde geçmiş bayatsa (diğer modda yazılmışsa) yeniden yükler."""
        if getattr(self.bridge, "is_running", False) or getattr(self, "_streaming_active", False):
            return
        if config_module.chat_history_signature() != getattr(self, "_history_signature", None):
            self._load_chat_history()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self._reload_chat_history_if_stale()
        except Exception:
            pass

    def closeEvent(self, event):
        # Faz 8: Chat ile ayni duzeltme — tekrarli kapanislarda ayni
        # sinyalleri yeniden cozmek RuntimeWarning uretiyordu.
        if not getattr(self, "_bus_connected", True):
            super().closeEvent(event)
            return
        self._bus_connected = False
        signals = [
            (bus.model_detected, self._update_model_badge),
            (bus.token_usage_updated, self._update_tokens),
            (bus.token_usage_detail, self._on_token_detail),
            (bus.core_state_changed, self._update_status),
            (bus.node_selected, self._on_node_selected),
            (bus.agent_turn_started, self._on_turn_started),
            (bus.token_chunk_received, self._on_chunk),
            (bus.agent_turn_completed, self._on_agent_turn_completed),
            (bus.report_created, self._on_report_created),
            (bus.task_notification, self._on_task_notification),
            (bus.cognitive_memory_updated, self._update_telemetry_badges),
            (bus.skills_updated, self._update_telemetry_badges),
            (bus.project_changed, self._on_project_changed),
            (bus.chat_history_updated, self._on_chat_history_updated),
            (bus.chat_history_cleared, self._on_chat_history_cleared),
            # Faz 11-C: rapor kartı köprüsü de çözülür (sızıntı olmasın).
            (bus.task_report_ready, self._on_task_report_ready),
        ]
        for sig, slot in signals:
            try:
                sig.disconnect(slot)
            except Exception:
                pass

        if hasattr(self, "tasks_widget") and self.tasks_widget:
            try:
                if getattr(self.tasks_widget, "scheduler", None):
                    self.tasks_widget.scheduler.stop()
                self.tasks_widget.close()
            except Exception:
                pass
        if hasattr(self, "knowledge_graph") and self.knowledge_graph:
            try:
                self.knowledge_graph.close()
            except Exception:
                pass
        if hasattr(self, "reports_viewer") and self.reports_viewer:
            try:
                self.reports_viewer.close()
            except Exception:
                pass
        if hasattr(self, "core_visualizer") and self.core_visualizer:
            try:
                self.core_visualizer.close()
            except Exception:
                pass
        if hasattr(self, "terminal_pane") and self.terminal_pane:
            try:
                self.terminal_pane.close()
            except Exception:
                pass
        super().closeEvent(event)


