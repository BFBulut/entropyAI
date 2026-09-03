"""Chat Mode: Floating conversational modal with multimodal image support and terminal drawer."""

from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeyEvent, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.platform.clipboard import ClipboardImageHandler
from entropy.ui.themes.cyber_theme import CYBER_THEME, STYLESHEET
from entropy.ui.widgets.terminal_pane import TerminalPaneWidget

class ChatInputField(QLineEdit):
    """Custom input line that intercepts Ctrl+V for clipboard images."""

    def __init__(self, parent_chat, parent=None):
        super().__init__(parent)
        self.parent_chat = parent_chat

    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.StandardKey.Paste) or (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V):
            if self.parent_chat.try_paste_image():
                event.accept()
                return
        super().keyPressEvent(event)

class ChatModeWindow(QMainWindow):
    """Floating Chat Mode with real-time streaming, terminal drawer, and Ctrl+V images."""

    def __init__(self, bridge: AgyProcessBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.clipboard_handler = ClipboardImageHandler()
        self.staged_images: List[str] = []

        self.setStyleSheet(STYLESHEET)
        self.setWindowTitle("Entropy AI Chat")
        self.resize(520, 680)

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

        h_layout.addStretch()

        # Dynamic Model badge (RULE: agent-ui-models)
        self.model_badge = QLabel(config.model_fallback_name)
        self.model_badge.setStyleSheet("color:#00F0FF; font-family:'Consolas'; font-size:11px; font-weight:bold;")
        h_layout.addWidget(self.model_badge)

        self.tokens_badge = QLabel("0 tokens")
        self.tokens_badge.setStyleSheet("color:#00FF9D; font-family:'Consolas'; font-size:11px;")
        h_layout.addWidget(self.tokens_badge)

        btn_zen = QPushButton("Zen Mode")
        btn_zen.setFixedHeight(24)
        btn_zen.clicked.connect(lambda: bus.mode_requested.emit("zen"))
        h_layout.addWidget(btn_zen)

        self.layout.addWidget(header)

        # 2. Chat history browser
        self.chat_browser = QTextBrowser()
        self.chat_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {CYBER_THEME['bg_surface']};
                border: 1px solid {CYBER_THEME['border']};
                border-radius: 6px;
                padding: 10px;
                color: {CYBER_THEME['text_primary']};
            }}
        """)
        self.layout.addWidget(self.chat_browser)

        # 3. Staged image preview thumbnail bar
        self.attachment_bar = QFrame()
        self.attachment_bar.setVisible(False)
        self.attach_layout = QHBoxLayout(self.attachment_bar)
        self.attach_layout.setContentsMargins(4, 2, 4, 2)
        self.attach_label = QLabel()
        self.attach_label.setStyleSheet("color:#00F0FF; font-size:11px;")
        self.attach_layout.addWidget(self.attach_label)
        self.attach_layout.addStretch()
        remove_attach_btn = QPushButton("✕ Remove")
        remove_attach_btn.setFixedHeight(20)
        remove_attach_btn.clicked.connect(self._clear_staged_images)
        self.attach_layout.addWidget(remove_attach_btn)
        self.layout.addWidget(self.attachment_bar)

        # 4. Input layout
        input_bar = QHBoxLayout()
        self.input_field = ChatInputField(self)
        self.input_field.setPlaceholderText("Type message or paste image with Ctrl+V...")
        self.input_field.returnPressed.connect(self._on_send)
        input_bar.addWidget(self.input_field)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send)
        input_bar.addWidget(self.send_btn)

        self.toggle_term_btn = QPushButton(">_ Terminal")
        self.toggle_term_btn.clicked.connect(self._toggle_terminal)
        input_bar.addWidget(self.toggle_term_btn)

        self.layout.addLayout(input_bar)

        # 5. Collapsible Terminal Drawer
        self.terminal_drawer = TerminalPaneWidget(title="Real-Time AGY Subprocess Stream")
        self.terminal_drawer.setFixedHeight(180)
        self.terminal_drawer.setVisible(False)
        self.layout.addWidget(self.terminal_drawer)

        self._append_message("Entropy AI", "Ready. Antigravity CLI initialized on-device without external API keys.", is_system=True)

    def _connect_signals(self):
        bus.model_detected.connect(self._update_model_badge)
        bus.token_usage_updated.connect(self._update_tokens)
        bus.agent_turn_started.connect(self._on_turn_started)
        bus.agent_turn_completed.connect(self._on_turn_completed)
        bus.token_chunk_received.connect(self._on_chunk)

    def try_paste_image(self) -> bool:
        """Handle Ctrl+V image detection and staging."""
        res = self.clipboard_handler.save_clipboard_image()
        if res:
            path_str, w, h = res
            self.staged_images.append(path_str)
            filename = Path(path_str).name
            self.attach_label.setText(f"📎 Pasted Image: <b>{filename}</b> ({w}x{h} px)")
            self.attachment_bar.setVisible(True)
            return True
        return False

    def _clear_staged_images(self):
        self.staged_images.clear()
        self.attachment_bar.setVisible(False)

    def _toggle_terminal(self):
        is_vis = not self.terminal_drawer.isVisible()
        self.terminal_drawer.setVisible(is_vis)

    @Slot(str)
    def _update_model_badge(self, model_name: str):
        self.model_badge.setText(f"[{model_name}]")

    @Slot(int)
    def _update_tokens(self, tokens: int):
        self.tokens_badge.setText(f"{tokens:,} tokens")

    def _on_send(self):
        prompt = self.input_field.text().strip()
        if not prompt and not self.staged_images:
            return

        display_prompt = prompt
        if self.staged_images:
            img_names = ", ".join([Path(p).name for p in self.staged_images])
            display_prompt += f" <i style='color:#00F0FF;'>[Attached: {img_names}]</i>"

        self._append_message("You", display_prompt)
        self.input_field.clear()

        images_to_send = list(self.staged_images)
        self._clear_staged_images()

        self.bridge.send_prompt_async(prompt=prompt, image_attachments=images_to_send)

    def _on_turn_started(self, prompt: str):
        self.send_btn.setEnabled(False)
        self.input_field.setEnabled(False)

    def _on_turn_completed(self, full_response: str):
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self._append_message("Entropy AI", full_response)

    def _on_chunk(self, chunk: str):
        # Keeps terminal and UI active
        pass

    def _append_message(self, sender: str, text: str, is_system: bool = False):
        color = "#00F0FF" if sender == "Entropy AI" else "#00FF9D" if sender == "You" else "#FFB300"
        html = f"<div style='margin-bottom:8px;'><b style='color:{color};'>{sender}:</b><br/>{text.replace('\n', '<br/>')}</div>"
        self.chat_browser.append(html)
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)
