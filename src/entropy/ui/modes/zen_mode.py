"""Zen Mode: Borderless fullscreen workstation for Entropy AI."""

from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QSizePolicy, QSplitter, QTabWidget,
    QVBoxLayout, QWidget
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.ui.themes.cyber_theme import CYBER_THEME, STYLESHEET
from entropy.ui.widgets.core_visualizer import CoreVisualizerWidget
from entropy.ui.widgets.knowledge_graph import KnowledgeGraphWidget
from entropy.ui.widgets.mcp_drawer import MCPDrawerWidget
from entropy.ui.widgets.reports_viewer import ReportsViewerWidget
from entropy.ui.widgets.terminal_pane import TerminalPaneWidget

class ZenModeWindow(QMainWindow):
    """Zen Mode: Borderless fullscreen immersive AI engineering environment."""

    def __init__(self, bridge: AgyProcessBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setStyleSheet(STYLESHEET)

        # Borderless window configuration
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(10)

        # 1. Top Header Bar
        header = QFrame()
        header.setObjectName("cardFrame")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 6, 14, 6)

        # Title
        title = QLabel("<span style='color:#00F0FF; font-size:16px; font-weight:bold;'>ENTROPY AI</span> <span style='color:#8B949E; font-size:11px;'>ZEN WORKSTATION</span>")
        h_layout.addWidget(title)

        h_layout.addSpacing(16)

        # Project Selector Button
        self.project_btn = QPushButton(f"📁 Proje: {self.bridge.active_project_dir.name}")
        self.project_btn.clicked.connect(self._select_project_dir)
        h_layout.addWidget(self.project_btn)

        h_layout.addStretch()

        # Dynamic Model Selector Combo (RULE: agent-ui-models + Model Selection UX)
        h_layout.addWidget(QLabel("<span style='color:#8B949E; font-size:11px;'>Model:</span>"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        models = self.bridge.fetch_available_models()
        for m in models:
            self.model_combo.addItem(m)
        self.model_combo.setCurrentText(self.bridge.selected_model)
        self.model_combo.currentTextChanged.connect(self._on_model_selected)
        h_layout.addWidget(self.model_combo)

        h_layout.addSpacing(10)

        # Token Usage Counter (RULE: agent-ui-routing)
        self.tokens_badge = QLabel("Tokens: 0")
        self.tokens_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #05070A;
                color: #00FF9D;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 4px 10px;
                font-family: 'Consolas';
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        h_layout.addWidget(self.tokens_badge)

        h_layout.addSpacing(15)

        # New Chat Button
        btn_new_chat = QPushButton("+ Yeni Sohbet")
        btn_new_chat.setStyleSheet("background-color: #141C2C; color: #00F0FF; border: 1px solid #00F0FF; font-weight: bold;")
        btn_new_chat.clicked.connect(self.bridge.reset_conversation)
        h_layout.addWidget(btn_new_chat)

        # Mode Switch Buttons
        btn_floating = QPushButton("Floating Mod")
        btn_floating.clicked.connect(lambda: bus.mode_requested.emit("floating"))
        h_layout.addWidget(btn_floating)

        btn_chat = QPushButton("Chat Mod")
        btn_chat.clicked.connect(lambda: bus.mode_requested.emit("chat"))
        h_layout.addWidget(btn_chat)

        btn_close = QPushButton("✕")
        btn_close.setFixedWidth(30)
        btn_close.setStyleSheet("background-color: #2D1418; color: #FF4D4D; border: 1px solid #5C2025; font-weight: bold;")
        btn_close.clicked.connect(self.close)
        h_layout.addWidget(btn_close)

        root_layout.addWidget(header)

        # 2. Main Workstation Area (Vertical Splitter)
        main_v_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top Horizontal Splitter: Left (Tabs: Reports & MCP), Center (Visual Core & Prompt), Right (Graph)
        top_h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Tabbed Interface for Reports & MCP Hub
        self.left_tabs = QTabWidget()
        self.reports_viewer = ReportsViewerWidget()
        self.mcp_drawer = MCPDrawerWidget()
        self.left_tabs.addTab(self.reports_viewer, "📚 Raporlar & Notlar")
        self.left_tabs.addTab(self.mcp_drawer, "🔌 MCP Sunucuları")
        top_h_splitter.addWidget(self.left_tabs)

        # Center Column: Organic Visual Core & Quick Command Input
        center_col = QFrame()
        center_col.setObjectName("cardFrame")
        center_layout = QVBoxLayout(center_col)
        center_layout.setContentsMargins(16, 16, 16, 16)
        center_layout.setSpacing(12)

        center_layout.addStretch()
        self.core_visualizer = CoreVisualizerWidget(base_radius=56)
        self.core_visualizer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_layout.addWidget(self.core_visualizer, alignment=Qt.AlignmentFlag.AlignCenter)

        self.core_status_lbl = QLabel("AI ÇEKİRDEK: HAZIR | SIFIR-API AGY AKTİF")
        self.core_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.core_status_lbl.setStyleSheet("color: #00F0FF; font-family: 'Consolas'; font-size: 12px; letter-spacing: 1px;")
        center_layout.addWidget(self.core_status_lbl)
        center_layout.addStretch()

        # Prompt input bar in Zen Mode
        prompt_bar = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Entropy AI'a bir talimat verin (örn: 'Kod tabanını analiz et ve testleri çalıştır')...")
        self.prompt_input.returnPressed.connect(self._on_submit_prompt)
        prompt_bar.addWidget(self.prompt_input)

        send_btn = QPushButton("Çalıştır")
        send_btn.setStyleSheet("background-color: #00F0FF; color: #080B10; font-weight: bold;")
        send_btn.clicked.connect(self._on_submit_prompt)
        prompt_bar.addWidget(send_btn)
        center_layout.addLayout(prompt_bar)

        top_h_splitter.addWidget(center_col)

        # Right Column: Knowledge Graph
        self.graph_widget = KnowledgeGraphWidget()
        top_h_splitter.addWidget(self.graph_widget)

        top_h_splitter.setSizes([340, 480, 380])
        main_v_splitter.addWidget(top_h_splitter)

        # Bottom Area: Infinite Split Terminal
        self.terminal_pane = TerminalPaneWidget(title="Canlı AGY Çıktı Akışı ve Terminal")
        main_v_splitter.addWidget(self.terminal_pane)

        main_v_splitter.setSizes([560, 240])
        root_layout.addWidget(main_v_splitter)

    def _connect_signals(self):
        bus.model_detected.connect(self._update_model_badge)
        bus.token_usage_updated.connect(self._update_tokens)
        bus.core_state_changed.connect(self._update_status)

    @Slot(str)
    def _update_model_badge(self, model_name: str):
        if self.model_combo.currentText() != model_name:
            self.model_combo.setCurrentText(model_name)

    def _on_model_selected(self, model_name: str):
        if model_name and model_name != self.bridge.selected_model:
            self.bridge.set_model(model_name)

    @Slot(int)
    def _update_tokens(self, tokens: int):
        self.tokens_badge.setText(f"Tokens: {tokens:,}")
        self.tokens_badge.setToolTip(
            f"Gerçek Antigravity Token Metrikleri:\n"
            f"• Toplam Token: {tokens:,}\n"
            f"• Girdi (Input): {self.bridge.latest_input_tokens:,}\n"
            f"• Çıktı (Output): {self.bridge.latest_output_tokens:,}\n"
            f"• Düşünme (Thinking): {self.bridge.latest_thinking_tokens:,}\n"
            f"• Önbellek (Cache): {self.bridge.latest_cache_read_tokens:,}"
        )

    @Slot(str)
    def _update_status(self, state: str):
        st = "DÜŞÜNÜYOR / İŞLENİYOR" if state == "thinking" else "YÜRÜTÜLÜYOR" if state == "executing" else "HAZIR"
        self.core_status_lbl.setText(f"AI ÇEKİRDEK: {st} | SIFIR-API AGY AKTİF")

    def _select_project_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Proje Klasörü Seç", str(self.bridge.active_project_dir))
        if folder:
            self.bridge.set_project_directory(folder)
            self.project_btn.setText(f"📁 Proje: {Path(folder).name}")

    def _on_submit_prompt(self):
        text = self.prompt_input.text().strip()
        if text:
            self.prompt_input.clear()
            self.bridge.send_prompt_async(prompt=text)
