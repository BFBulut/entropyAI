"""Zen Mode: Borderless fullscreen workstation for Entropy AI."""

from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QProgressBar, QPushButton, QSizePolicy, QSplitter, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.ui.themes.cyber_theme import CYBER_THEME, STYLESHEET
from entropy.ui.widgets.core_visualizer import CoreVisualizerWidget
from entropy.ui.widgets.knowledge_graph import KnowledgeGraphWidget
from entropy.ui.widgets.mcp_drawer import MCPDrawerWidget
from entropy.ui.widgets.reports_viewer import ReportsViewerWidget
from entropy.ui.widgets.tasks_widget import TasksWidget
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

        # Left Column: Tabbed Interface for Reports, MCP Hub & Tasks
        self.left_tabs = QTabWidget()
        self.reports_viewer = ReportsViewerWidget()
        self.mcp_drawer = MCPDrawerWidget()
        self.tasks_widget = TasksWidget()
        self.left_tabs.addTab(self.reports_viewer, "📚 Raporlar & Notlar")
        self.left_tabs.addTab(self.mcp_drawer, "🔌 MCP Sunucuları")
        self.left_tabs.addTab(self.tasks_widget, "⏰ Görevler")
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

        self._load_persisted_session_to_terminal()

    def _load_persisted_session_to_terminal(self):
        """Restore full conversation history to the terminal pane on launch."""
        from entropy.core.config import CHAT_HISTORY_FILE
        if CHAT_HISTORY_FILE.exists():
            try:
                import json
                history = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
                if history:
                    cid = f" (Oturum ID: {self.bridge.current_conversation_id[:8]}...)" if self.bridge.current_conversation_id else ""
                    self.terminal_pane.append_output(f"════════════════ [AKTİF SOHBET GEÇMİŞİ YÜKLENDİ{cid} - {len(history)} Mesaj] ════════════════\n")
                    for turn in history:
                        role = "SİZ" if turn.get("role") == "user" else f"ENTROPY CORE [{self.bridge.selected_model}]"
                        content = turn.get("content", "").strip()
                        self.terminal_pane.append_output(f"\n▶ [{role}]:\n{content}\n")
                    self.terminal_pane.append_output("\n════════════════ [CANLI ÇIKTI AKIŞI BAŞLATILDI] ════════════════\n\n")
            except Exception:
                pass

    def _connect_signals(self):
        bus.model_detected.connect(self._update_model_badge)
        bus.token_usage_updated.connect(self._update_tokens)
        bus.core_state_changed.connect(self._update_status)
        bus.node_selected.connect(self._on_node_selected)
        bus.agent_turn_completed.connect(self._on_agent_turn_completed)

    @Slot(str)
    def _on_node_selected(self, node_id: str):
        """Handle clicking any node in the knowledge graph."""
        # 1. Try to open matching report / markdown file in the left reader
        found = self.reports_viewer.open_report_by_path_or_id(node_id)
        if found:
            self.left_tabs.setCurrentWidget(self.reports_viewer)
            return

        # 2. Check if it's a cognitive memory node in SQLite
        try:
            from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
            cog = CognitiveMemorySystem()
            node = cog.get_node(node_id)
            if node:
                self._show_memory_inspector_dialog(node)
        except Exception:
            pass

    def _show_memory_inspector_dialog(self, node):
        """Cyber-styled modal inspecting a cognitive memory node."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Bilişsel Düğüm Denetleyicisi - {node.id}")
        dialog.setFixedSize(500, 420)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #080B10;
                color: #F0F6FC;
                border: 1px solid #00F0FF;
                border-radius: 8px;
            }
        """)
        d_layout = QVBoxLayout(dialog)
        d_layout.setContentsMargins(16, 16, 16, 16)
        d_layout.setSpacing(10)

        # Header with Category badge
        hdr = QHBoxLayout()
        title_lbl = QLabel(f"<b style='color:#00F0FF; font-size:13px;'>🧠 {node.id}</b>")
        cat_color = "#00FF9D" if node.category == "semantic" else "#FFB300" if node.category == "episodic" else "#9D00FF"
        badge = QLabel(f"<span style='background:#141C2C; color:{cat_color}; border:1px solid {cat_color}; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:11px;'>KATMAN: {node.category.upper()}</span>")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        hdr.addWidget(badge)
        d_layout.addLayout(hdr)

        # Content text box
        content_lbl = QLabel("<b>Düğüm İçeriği / Hatırlanan Bilgi:</b>")
        content_lbl.setStyleSheet("color: #8B949E; font-size: 11px;")
        d_layout.addWidget(content_lbl)

        text_box = QTextBrowser()
        text_box.setStyleSheet("background-color: #0E1420; border: 1px solid #1F2B42; color: #F0F6FC; padding: 8px; font-size: 12px; border-radius: 4px;")
        text_box.setText(node.content)
        d_layout.addWidget(text_box)

        # Cognitive Metrics
        ebbinghaus = node.calculate_ebbinghaus_strength()
        metrics_layout = QHBoxLayout()
        imp_lbl = QLabel(f"Önem Skoru: <b>{node.importance:.2f}</b>")
        imp_lbl.setStyleSheet("color:#00FF9D; font-size:11px;")
        decay_lbl = QLabel(f"Ebbinghaus Gücü: <b>{ebbinghaus:.2f}</b>")
        decay_lbl.setStyleSheet("color:#00F0FF; font-size:11px;")
        access_lbl = QLabel(f"Erişim: <b>{node.access_count}</b>")
        access_lbl.setStyleSheet("color:#FFB300; font-size:11px;")
        metrics_layout.addWidget(imp_lbl)
        metrics_layout.addWidget(decay_lbl)
        metrics_layout.addWidget(access_lbl)
        d_layout.addLayout(metrics_layout)

        # Retention progress bar
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(ebbinghaus * 100))
        pbar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #1F2B42;
                border-radius: 4px;
                text-align: center;
                height: 12px;
                background: #0E1420;
                color: #F0F6FC;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00F0FF, stop:1 #00FF9D);
                border-radius: 3px;
            }
        """)
        d_layout.addWidget(pbar)

        # Buttons
        btn_box = QHBoxLayout()
        export_btn = QPushButton("📄 Obsidian Kasasına Aktar")
        export_btn.setStyleSheet("background-color: #141C2C; color: #00FF9D; border: 1px solid #00FF9D; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        def on_export():
            from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
            vm = ObsidianVaultManager()
            path = vm.save_research_report(f"Hafiza_{node.id}", f"# Bilişsel Düğüm: {node.id}\n\n**Kategori**: {node.category}\n**Önem**: {node.importance}\n\n{node.content}")
            bus.terminal_output_received.emit(f"[Obsidian Export] Düğüm kaydedildi: {path.name}\n")
            dialog.accept()
        export_btn.clicked.connect(on_export)
        btn_box.addWidget(export_btn)

        btn_box.addStretch()
        close_btn = QPushButton("Kapat")
        close_btn.setStyleSheet("background-color: #1A263C; color: #F0F6FC; border: 1px solid #1F2B42; padding: 6px 16px; border-radius: 4px;")
        close_btn.clicked.connect(dialog.accept)
        btn_box.addWidget(close_btn)

        d_layout.addLayout(btn_box)
        dialog.exec()

    @Slot(str)
    def _update_model_badge(self, model_name: str):
        if self.model_combo.currentText() != model_name:
            self.model_combo.setCurrentText(model_name)

    def _on_model_selected(self, model_name: str):
        if model_name and model_name != self.bridge.selected_model:
            self.bridge.set_model(model_name)

    @Slot(int)
    def _update_tokens(self, tokens: int):
        active = self.bridge.latest_input_tokens + self.bridge.latest_output_tokens
        cache_k = self.bridge.latest_cache_read_tokens // 1000
        if cache_k > 0:
            self.tokens_badge.setText(f"Aktif: {active:,} | Cache: {cache_k}k")
        else:
            self.tokens_badge.setText(f"Tokens: {tokens:,}")

        self.tokens_badge.setToolTip(
            f"Gerçek Antigravity Token Kullanım Metrikleri:\n"
            f"• Yeni Üretilen (Output): {self.bridge.latest_output_tokens:,} token\n"
            f"• Yeni Girdi (Input): {self.bridge.latest_input_tokens:,} token\n"
            f"• Düşünme (Thinking): {self.bridge.latest_thinking_tokens:,} token\n"
            f"• Sunucu Önbelleği (Cache Read): {self.bridge.latest_cache_read_tokens:,} token (Hızlı / Ücretsiz)\n"
            f"• Toplam Bağlam Boyutu: {tokens:,} token"
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
            self.terminal_pane.append_output(f"\n▶ [SİZ]:\n{text}\n")
            self.bridge.send_prompt_async(prompt=text)

    @Slot(str)
    def _on_agent_turn_completed(self, response: str):
        self.terminal_pane.append_output("\n────────────────────────────────────────────────────────────────\n")
