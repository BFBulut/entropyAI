"""Split Terminal Pane widget for real-time stdout/stderr streaming."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import CYBER_THEME

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
        self.title_label.setStyleSheet(f"color: {CYBER_THEME['accent_cyan']}; font-family: 'Consolas';")
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
        self.text_area.setFont(QFont("Consolas", 10))
        self.text_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {CYBER_THEME['bg_terminal']};
                color: #A9B7C6;
                border: 1px solid {CYBER_THEME['border']};
                border-radius: 4px;
            }}
        """)
        self.layout.addWidget(self.text_area)

        # Connect to Event Bus
        bus.terminal_output_received.connect(self.append_text)

    @Slot(str)
    def append_text(self, text: str):
        self.text_area.moveCursor(QTextCursor.MoveOperation.End)
        self.text_area.insertPlainText(text)
        self.text_area.moveCursor(QTextCursor.MoveOperation.End)

    def append_output(self, text: str):
        self.append_text(text)

    def clear_terminal(self):
        self.text_area.clear()

    def clear_output(self):
        self.clear_terminal()
