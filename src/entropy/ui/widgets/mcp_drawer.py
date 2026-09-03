"""MCP Server Management Drawer Widget."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
)

from entropy.mcp.manager import MCPManager
from entropy.ui.themes.cyber_theme import CYBER_THEME

class MCPDrawerWidget(QFrame):
    """Visual dock to view and toggle Model Context Protocol servers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.mcp_manager = MCPManager()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("<b>🔌 MCP SERVERS HUB</b>")
        title_label.setStyleSheet(f"color: {CYBER_THEME['accent_cyan']}; font-size: 13px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.refresh_btn = QPushButton("Sync")
        self.refresh_btn.setFixedHeight(22)
        self.refresh_btn.clicked.connect(self.refresh_servers)
        header_layout.addWidget(self.refresh_btn)
        self.layout.addLayout(header_layout)

        # Server List Container
        self.servers_layout = QVBoxLayout()
        self.layout.addLayout(self.servers_layout)

        self.refresh_servers()

    def refresh_servers(self):
        # Clear existing
        while self.servers_layout.count():
            item = self.servers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        servers = self.mcp_manager.list_servers()
        for s in servers:
            row = QHBoxLayout()
            name_lbl = QLabel(f"<b>{s['name']}</b> <span style='color:#8B949E;'>({s['type']})</span>")
            name_lbl.setStyleSheet("font-size: 12px;")
            row.addWidget(name_lbl)
            row.addStretch()

            cb = QCheckBox("Active")
            cb.setChecked(s["status"].lower() == "enabled")
            cb.toggled.connect(lambda checked, s_name=s["name"]: self._on_toggle(s_name, checked))
            row.addWidget(cb)

            row_widget = QFrame()
            row_widget.setStyleSheet(f"background: {CYBER_THEME['bg_terminal']}; border-radius: 4px; padding: 2px;")
            row_widget.setLayout(row)
            self.servers_layout.addWidget(row_widget)

    def _on_toggle(self, server_name: str, enabled: bool):
        if enabled:
            self.mcp_manager.enable_server(server_name)
        else:
            self.mcp_manager.disable_server(server_name)
