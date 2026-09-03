"""Chat Mode: Floating conversational modal with multimodal image support and terminal drawer."""

import json
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeyEvent, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
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
        self.resize(540, 700)

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

        # Dynamic Model Selector Combo (RULE: agent-ui-models)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        models = self.bridge.fetch_available_models()
        for m in models:
            self.model_combo.addItem(m)
        self.model_combo.setCurrentText(self.bridge.selected_model)
        self.model_combo.currentTextChanged.connect(self._on_model_selected)
        h_layout.addWidget(self.model_combo)

        self.tokens_badge = QLabel("0 tokens")
        self.tokens_badge.setStyleSheet("color:#00FF9D; font-family:'Consolas'; font-size:11px; font-weight:bold;")
        h_layout.addWidget(self.tokens_badge)

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

        # 2. Chat history browser
        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(False)
        self.chat_browser.anchorClicked.connect(self._on_anchor_clicked)
        self.chat_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {CYBER_THEME['bg_surface']};
                border: 1px solid {CYBER_THEME['border']};
                border-radius: 6px;
                padding: 12px;
                color: {CYBER_THEME['text_primary']};
                font-size: 13px;
                line-height: 1.5;
            }}
        """)
        self.layout.addWidget(self.chat_browser)
        self._load_chat_history()

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

    def _connect_signals(self):
        bus.model_detected.connect(self._update_model_badge)
        bus.token_usage_updated.connect(self._update_tokens)
        bus.agent_turn_started.connect(self._on_turn_started)
        bus.agent_turn_completed.connect(self._on_turn_completed)
        bus.token_chunk_received.connect(self._on_chunk)
        bus.report_created.connect(self._on_report_created)

    @Slot(str)
    def _on_report_created(self, path_str: str):
        """Display notification in chat and top bar when a research report is compiled."""
        p = Path(path_str)
        self.latest_report_path = str(p)
        self.report_bar_lbl.setText(f"<span style='color:#00FF9D; font-weight:bold;'>📑 Yeni Rapor:</span> <span style='color:#F0F6FC;'>{p.stem}</span>")
        self.report_bar.setVisible(True)

        self._append_message(
            "Entropy AI",
            f"📄 **Yeni Araştırma Raporu Oluşturuldu:** `{p.name}`\n\n"
            f"[👉 Ayrı Ekranda Aç ve İncele](entropy-report://{p.as_posix()})",
            is_system=True
        )

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

    def _toggle_terminal(self):
        is_vis = not self.terminal_drawer.isVisible()
        self.terminal_drawer.setVisible(is_vis)

    def _on_new_chat(self):
        self.bridge.reset_conversation()
        self.chat_browser.clear()
        self._append_message("Entropy AI", "Yeni sohbet oturumu başlatıldı. Nasıl yardımcı olabilirim?", is_system=True)

    def _load_chat_history(self):
        """Restore conversation history from disk upon opening."""
        from entropy.core.config import CHAT_HISTORY_FILE
        if CHAT_HISTORY_FILE.exists():
            try:
                history = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
                for msg in history:
                    sender = "Sen" if msg.get("role") == "user" else "Entropy AI"
                    self._append_message(sender, msg.get("content", ""))
            except Exception:
                pass
        if self.chat_browser.toPlainText().strip() == "":
            self._append_message("Entropy AI", "Sistem aktif. Size nasıl yardımcı olabilirim?", is_system=True)

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

    def _on_send(self):
        prompt = self.input_field.text().strip()
        if not prompt and not self.staged_images:
            return

        display_prompt = prompt
        if self.staged_images:
            img_names = ", ".join([Path(p).name for p in self.staged_images])
            display_prompt += f" <i style='color:#00F0FF;'>[Eklenen Görsel: {img_names}]</i>"

        self._append_message("Siz", display_prompt)
        self.input_field.clear()

        images_to_send = list(self.staged_images)
        self._clear_staged_images()

        actual_prompt = prompt
        if images_to_send:
            actual_prompt += "\n" + "\n".join([f"[Eklenen Görsel Dosyası: {p}]" for p in images_to_send])

        if self.bridge.is_running:
            self._append_message("Entropy AI", "⏳ <i>Önceki işlem tamamlanıyor, mesajınız sıraya alındı ve hemen ardından yanıtlanacak...</i>", is_system=True)

        self.bridge.send_prompt_async(prompt=actual_prompt, image_attachments=images_to_send)

    def _on_turn_started(self, prompt: str):
        self.send_btn.setEnabled(False)
        self.input_field.setEnabled(False)
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

    def _on_turn_completed(self, full_response: str):
        self._streaming_active = False
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.chat_browser.append("<div style='margin-bottom:12px;'></div>")
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)

    def _append_message(self, sender: str, text: str, is_system: bool = False):
        color = "#00F0FF" if sender == "Entropy AI" else "#00FF9D" if sender == "Siz" else "#FFB300"
        html = f"<div style='margin-bottom:8px;'><b style='color:{color};'>{sender}:</b><br/>{text.replace('\n', '<br/>')}</div>"
        self.chat_browser.append(html)
        self.chat_browser.moveCursor(QTextCursor.MoveOperation.End)
