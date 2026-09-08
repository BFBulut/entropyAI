"""Split Terminal Pane widget for real-time stdout/stderr streaming."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import CYBER_THEME, READING_TOKENS

class TerminalPaneWidget(QFrame):
    """Real-time streaming agent terminal (enforcing RULE: agent-ui-routing)."""

    def __init__(self, parent=None, title="Entropy Core Terminal"):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header bar
        self.header_layout = QHBoxLayout()
        self.title_label = QLabel(f"<b>[>_] {title}</b>")
        self.title_label.setStyleSheet(
            f"color: {READING_TOKENS['accent']}; font-family: {READING_TOKENS['font_mono']};"
            " font-size: 12px; letter-spacing: 0.5px;"
        )
        self.header_layout.addWidget(self.title_label)

        self.header_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedHeight(24)
        self.clear_btn.clicked.connect(self.clear_terminal)
        self.header_layout.addWidget(self.clear_btn)

        self.layout.addLayout(self.header_layout)

        # Text output area
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        # Okunabilirlik: daha büyük punto ve satır aralığı. QTextEdit stil
        # sayfası line-height'i uygulamadığı için aralık blok biçimiyle verilir.
        mono = QFont("Cascadia Mono", 11)
        if not mono.exactMatch():
            mono = QFont("Consolas", 11)
        self.text_area.setFont(mono)
        self.text_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {READING_TOKENS['surface_base']};
                color: {READING_TOKENS['text_body']};
                border: 1px solid {READING_TOKENS['divider_soft']};
                border-radius: 8px;
                padding: 10px 12px;
                selection-background-color: {READING_TOKENS['accent_soft']};
            }}
        """)
        _block_fmt = QTextBlockFormat()
        _block_fmt.setLineHeight(140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        _cursor = self.text_area.textCursor()
        _cursor.select(QTextCursor.SelectionType.Document)
        _cursor.mergeBlockFormat(_block_fmt)
        self.text_area.setTextCursor(_cursor)
        self._block_format = _block_fmt
        self.layout.addWidget(self.text_area)

        # Connect to Event Bus
        bus.terminal_output_received.connect(self.append_text)

    @Slot(str)
    def append_text(self, text: str):
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # Satir araligi bicimi yeni bloklara da uygulanir.
        if getattr(self, "_block_format", None) is not None:
            cursor.setBlockFormat(self._block_format)
        cursor.insertText(text)
        self.text_area.setTextCursor(cursor)
        self.text_area.ensureCursorVisible()

    def append_output(self, text: str):
        self.append_text(text)

    def clear_terminal(self):
        self.text_area.clear()

    def clear_output(self):
        self.clear_terminal()

    def closeEvent(self, event):
        try:
            bus.terminal_output_received.disconnect(self.append_text)
        except Exception:
            pass
        super().closeEvent(event)
