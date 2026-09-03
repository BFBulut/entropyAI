"""Zen Mode: Borderless fullscreen workstation for Entropy AI."""

from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QSplitter, QVBoxLayout, QWidget
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
        h_layout.setContentsMargins(12, 6, 12, 6)

        # Title
        title = QLabel("<span style='color:#00F0FF; font-size:16px; font-weight:bold;'>ENTROPY AI</span> <span style='color:#8B949E; font-size:11px;'>ZEN WORKSTATION</span>")
        h_layout.addWidget(title)

        h_layout.addSpacing(20)

        # Project Selector Button
        self.project_btn = QPushButton(f"📁 Project: {self.bridge.active_project_dir.name}")
        self.project_btn.clicked.connect(self._select_project_dir)
        h_layout.addWidget(self.project_btn)

        h_layout.addStretch()

        # Dynamic Model Badge (RULE: agent-ui-models)
        self.model_badge = QLabel(config.model_fallback_name)
        self.model_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #05070A;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 4px 10px;
                font-family: 'Consolas';
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        h_layout.addWidget(self.model_badge)

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
            }}
        """)
        h_layout.addWidget(self.tokens_badge)

        h_layout.addSpacing(15)

        # Mode Switch Buttons
        btn_floating = QPushButton("Floating Mode")
        btn_floating.clicked.connect(lambda: bus.mode_requested.emit("floating"))
        h_layout.addWidget(btn_floating)

        btn_chat = QPushButton("Chat Mode")
        btn_chat.clicked.connect(lambda: bus.mode_requested.emit("chat"))
        h_layout.addWidget(btn_chat)

        btn_close = QPushButton("✕")
        btn_close.setFixedWidth(30)
        btn_close.setStyleSheet("background-color: #2D1418; color: #FF4D4D; border: 1px solid #5C2025;")
        btn_close.clicked.connect(self.close)
        h_layout.addWidget(btn_close)

        root_layout.addWidget(header)

        # 2. Main Workstation Area (Vertical Splitter)
        main_v_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top Horizontal Splitter: Left (Reports & MCP), Center (Visual Core & Prompt), Right (Graph)
        top_h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Reports & MCP
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(ReportsViewerWidget())
        left_layout.addWidget(MCPDrawerWidget())
        top_h_splitter.addWidget(left_col)

        # Center Column: Visual Core & Quick Command Input
        center_col = QFrame()
        center_col.setObjectName("cardFrame")
        center_layout = QVBoxLayout(center_col)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(12)

        center_layout.addStretch()
        self.core_visualizer = CoreVisualizerWidget(radius=54)
        center_layout.addWidget(self.core_visualizer, alignment=Qt.AlignmentFlag.AlignCenter)

        self.core_status_lbl = QLabel("SYSTEM IDLE - ZERO API READY")
        self.core_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.core_status_lbl.setStyleSheet("color: #00F0FF; font-family: 'Consolas'; font-size: 12px;")
        center_layout.addWidget(self.core_status_lbl)
        center_layout.addStretch()

        # Prompt input bar in Zen Mode
        prompt_bar = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Dispatch instruction to Entropy AI (e.g. 'Audit project memory and refactor tests')...")
        self.prompt_input.returnPressed.connect(self._on_submit_prompt)
        prompt_bar.addWidget(self.prompt_input)

        send_btn = QPushButton("Execute")
        send_btn.clicked.connect(self._on_submit_prompt)
        prompt_bar.addWidget(send_btn)
        center_layout.addLayout(prompt_bar)

        top_h_splitter.addWidget(center_col)

        # Right Column: Knowledge Graph
        self.graph_widget = KnowledgeGraphWidget()
        top_h_splitter.addWidget(self.graph_widget)

        top_h_splitter.setSizes([320, 480, 360])
        main_v_splitter.addWidget(top_h_splitter)

        # Bottom Area: Infinite Split Terminal
        self.terminal_pane = TerminalPaneWidget(title="Live AGY Stream & Agent Shell")
        main_v_splitter.addWidget(self.terminal_pane)

        main_v_splitter.setSizes([560, 240])
        root_layout.addWidget(main_v_splitter)

    def _connect_signals(self):
        bus.model_detected.connect(self._update_model_badge)
        bus.token_usage_updated.connect(self._update_tokens)
        bus.core_state_changed.connect(self._update_status)

    @Slot(str)
    def _update_model_badge(self, model_name: str):
        self.model_badge.setText(f"[{model_name}]")

    @Slot(int)
    def _update_tokens(self, tokens: int):
        self.tokens_badge.setText(f"Tokens: {tokens:,}")

    @Slot(str)
    def _update_status(self, state: str):
        self.core_status_lbl.setText(f"SYSTEM {state.upper()} - REAL-TIME AGY ACTIVE")

    def _select_project_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Directory", str(self.bridge.active_project_dir))
        if folder:
            self.bridge.set_project_directory(folder)
            self.project_btn.setText(f"📁 Project: {Path(folder).name}")

    def _on_submit_prompt(self):
        text = self.prompt_input.text().strip()
        if text:
            self.prompt_input.clear()
            self.bridge.send_prompt_async(prompt=text)
