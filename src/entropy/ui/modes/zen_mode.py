"""Zen Mode: Borderless fullscreen workstation for Entropy AI."""

import json
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QProgressBar, QPushButton, QSizePolicy, QSplitter, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.platform.clipboard import ClipboardImageHandler
from entropy.ui.modes.chat_mode import ChatInputField
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
        self.clipboard_handler = ClipboardImageHandler()
        self.staged_images: List[str] = []
        self._streaming_active: bool = False
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
        self.prompt_input.setPlaceholderText("Hızlı talimat verin (örn: 'Kod tabanını analiz et ve testleri çalıştır')...")
        self.prompt_input.returnPressed.connect(self._on_submit_prompt)
        prompt_bar.addWidget(self.prompt_input)

        self.submit_btn = QPushButton("Çalıştır")
        self.submit_btn.setStyleSheet("background-color: #00F0FF; color: #080B10; font-weight: bold;")
        self.submit_btn.clicked.connect(self._on_submit_prompt)
        prompt_bar.addWidget(self.submit_btn)
        center_layout.addLayout(prompt_bar)

        top_h_splitter.addWidget(center_col)

        # Right Column: Knowledge Graph
        self.graph_widget = KnowledgeGraphWidget()
        top_h_splitter.addWidget(self.graph_widget)

        top_h_splitter.setSizes([340, 480, 380])
        main_v_splitter.addWidget(top_h_splitter)

        # Bottom Area: Dual Splitter with Interactive Chat (Left) and Live AGY Terminal (Right)
        bottom_h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. Left Side: Full Interactive Chat Panel
        chat_card = QFrame()
        chat_card.setObjectName("cardFrame")
        chat_layout = QVBoxLayout(chat_card)
        chat_layout.setContentsMargins(12, 8, 12, 8)
        chat_layout.setSpacing(6)

        # Chat Header
        chat_hdr = QHBoxLayout()
        chat_title = QLabel("<b style='color:#00F0FF; font-size:12px;'>💬 Bilişsel Sohbet & Diyalog</b>")
        chat_hdr.addWidget(chat_title)
        chat_hdr.addStretch()

        btn_new_chat_zen = QPushButton("+ Yeni Sohbet")
        btn_new_chat_zen.setFixedHeight(22)
        btn_new_chat_zen.setStyleSheet(
            "background-color:#141C2C; color:#00F0FF; border:1px solid #00F0FF; font-size:11px; font-weight:bold; padding:2px 8px; border-radius:4px;"
        )
        btn_new_chat_zen.clicked.connect(self._on_new_chat)
        chat_hdr.addWidget(btn_new_chat_zen)
        chat_layout.addLayout(chat_hdr)

        # Chat Browser
        self.chat_browser = QTextBrowser()
        self.chat_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {CYBER_THEME['bg_surface']};
                border: 1px solid {CYBER_THEME['border']};
                border-radius: 6px;
                padding: 10px;
                color: {CYBER_THEME['text_primary']};
                font-size: 13px;
                line-height: 1.5;
            }}
        """)
        chat_layout.addWidget(self.chat_browser)

        # Staged image preview bar
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
        chat_layout.addWidget(self.attachment_bar)

        # Chat Input Bar
        chat_input_bar = QHBoxLayout()
        self.chat_input = ChatInputField(self)
        self.chat_input.setPlaceholderText("Mesajınızı yazın veya Ctrl+V ile görsel yapıştırın...")
        self.chat_input.returnPressed.connect(self._on_send_chat)
        chat_input_bar.addWidget(self.chat_input)

        self.chat_send_btn = QPushButton("Gönder")
        self.chat_send_btn.setStyleSheet("background-color:#00F0FF; color:#080B10; font-weight:bold; padding:6px 14px;")
        self.chat_send_btn.clicked.connect(self._on_send_chat)
        chat_input_bar.addWidget(self.chat_send_btn)
        chat_layout.addLayout(chat_input_bar)

        bottom_h_splitter.addWidget(chat_card)

        # 2. Right Side: Live Terminal
        self.terminal_pane = TerminalPaneWidget(title="Canlı AGY Çıktı Akışı ve Terminal")
        bottom_h_splitter.addWidget(self.terminal_pane)

        bottom_h_splitter.setSizes([550, 450])
        main_v_splitter.addWidget(bottom_h_splitter)

        main_v_splitter.setSizes([520, 340])
        root_layout.addWidget(main_v_splitter)

        self._load_chat_history()
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
        bus.agent_turn_started.connect(self._on_turn_started)
        bus.token_chunk_received.connect(self._on_chunk)
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
        turn_out = self.bridge.latest_output_tokens
        turn_in = self.bridge.latest_input_tokens
        sess_k = self.bridge.session_total_tokens // 1000
        cache_k = self.bridge.latest_cache_read_tokens // 1000

        if turn_out > 0:
            if sess_k > 0:
                self.tokens_badge.setText(f"Yanıt: +{turn_out:,} | İstek: {turn_in:,} | Oturum: {sess_k}k")
            else:
                self.tokens_badge.setText(f"Yanıt: +{turn_out:,} | İstek: {turn_in:,}")
        elif sess_k > 0:
            self.tokens_badge.setText(f"Oturum: {sess_k}k | Cache: {cache_k}k")
        else:
            self.tokens_badge.setText(f"Tokens: {tokens:,}")

        self.tokens_badge.setToolTip(
            f"Gerçek Antigravity (AGY) Token Kullanım Metrikleri:\n"
            f"• Son Yanıt Üretimi (Output): +{self.bridge.latest_output_tokens:,} token\n"
            f"• Son İstek Girdisi (Input Context): {self.bridge.latest_input_tokens:,} token\n"
            f"• Model Düşünme Payı (Thinking): {self.bridge.latest_thinking_tokens:,} token (Output dahilinde)\n"
            f"• Son Yanıttaki Önbellek (Cache Read): {self.bridge.latest_cache_read_tokens:,} token (Hızlı / Ücretsiz)\n"
            f"──────────────────────────────────────────────\n"
            f"• Bu Tur Toplamı (Delta Total): {self.bridge.total_tokens_used:,} token\n"
            f"• Tüm Oturum Kümülatif Toplamı: {self.bridge.session_total_tokens:,} token ({self.bridge.session_turn_count} Tur)\n"
            f"• Tüm Oturum Önbellek Toplamı: {self.bridge.session_cache_tokens:,} token"
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
            self.chat_input.setText(text)
            self._on_send_chat()

    def _on_send_chat(self):
        prompt = self.chat_input.text().strip()
        if not prompt and not self.staged_images:
            return

        display_prompt = prompt
        if self.staged_images:
            img_names = ", ".join([Path(p).name for p in self.staged_images])
            display_prompt += f" <i style='color:#00F0FF;'>[Eklenen Görsel: {img_names}]</i>"

        self._append_chat_message("Siz", display_prompt)
        self.chat_input.clear()
        self.terminal_pane.append_output(f"\n▶ [SİZ]:\n{prompt}\n")

        images_to_send = list(self.staged_images)
        self._clear_staged_images()

        actual_prompt = prompt
        if images_to_send:
            actual_prompt += "\n" + "\n".join([f"[Eklenen Görsel Dosyası: {p}]" for p in images_to_send])

        if self.bridge.is_running:
            self._append_chat_message("Entropy AI", "⏳ <i>Önceki işlem tamamlanıyor, mesajınız sıraya alındı...</i>", is_system=True)
            self.terminal_pane.append_output("[Entropy Core] Önceki işlem tamamlanıyor, mesajınız sıraya alındı...\n")

        self.chat_send_btn.setEnabled(False)
        self.chat_input.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("İşleniyor...")
        self.bridge.send_prompt_async(prompt=actual_prompt, image_attachments=images_to_send)

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
        self.terminal_pane.append_output("\n────────────────────────────────────────────────────────────────\n")

    def try_paste_image(self) -> bool:
        """Handle Ctrl+V image detection and staging."""
        res = self.clipboard_handler.save_clipboard_image()
        if res:
            path_str, w, h = res
            self.staged_images.append(path_str)
            filename = Path(path_str).name
            self.attach_label.setText(f"📎 Yapıştırılan Görsel: <b>{filename}</b> ({w}x{h} px)")
            self.attachment_bar.setVisible(True)
            return True
        return False

    def _clear_staged_images(self):
        self.staged_images.clear()
        self.attachment_bar.setVisible(False)

    def _append_chat_message(self, sender: str, text: str, is_system: bool = False):
        color = "#00F0FF" if sender == "Entropy AI" else "#00FF9D" if sender == "Siz" else "#FFB300"
        html = f"<div style='margin-bottom:8px;'><b style='color:{color};'>{sender}:</b><br/>{text.replace('\n', '<br/>')}</div>"
        self.chat_browser.append(html)
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)

    def _on_new_chat(self):
        self.bridge.reset_conversation()
        self.chat_browser.clear()
        self.terminal_pane.clear_output()
        self._append_chat_message("Entropy AI", "Yeni sohbet oturumu başlatıldı. Nasıl yardımcı olabilirim?", is_system=True)

    def _load_chat_history(self):
        from entropy.core.config import CHAT_HISTORY_FILE
        if CHAT_HISTORY_FILE.exists():
            try:
                history = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
                for msg in history:
                    sender = "Siz" if msg.get("role") == "user" else "Entropy AI"
                    self._append_chat_message(sender, msg.get("content", ""))
            except Exception:
                pass
        if self.chat_browser.toPlainText().strip() == "":
            self._append_chat_message("Entropy AI", "Zen Çalışma Alanı aktif. Size nasıl yardımcı olabilirim?", is_system=True)
