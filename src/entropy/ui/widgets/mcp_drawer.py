"""MCP Server Management Drawer Widget with Add Server dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QRadioButton, QVBoxLayout, QWidget, QButtonGroup
)

from entropy.mcp.manager import MCPManager
from entropy.ui.themes.cyber_theme import CYBER_THEME

class AddMCPServerDialog(QDialog):
    """Dialog to register a new MCP server via 'agy mcp add'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni MCP Sunucusu Ekle")
        self.setFixedWidth(420)
        self.setStyleSheet("""
            QDialog {
                background-color: #0E1420;
                color: #F0F6FC;
            }
            QLabel { color: #F0F6FC; font-size: 12px; }
            QLineEdit {
                background-color: #05070A;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 6px;
                color: #F0F6FC;
            }
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { border-color: #00F0FF; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: github-tools")
        form.addRow("Sunucu Adı:", self.name_input)

        # Type Selection (stdio / http)
        type_layout = QHBoxLayout()
        self.btn_group = QButtonGroup(self)
        self.radio_stdio = QRadioButton("stdio (Yerel npx/python)")
        self.radio_stdio.setChecked(True)
        self.radio_http = QRadioButton("http (Uzak URL)")
        self.btn_group.addButton(self.radio_stdio)
        self.btn_group.addButton(self.radio_http)
        type_layout.addWidget(self.radio_stdio)
        type_layout.addWidget(self.radio_http)
        form.addRow("Bağlantı Tipi:", type_layout)

        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Örn: npx -y @modelcontextprotocol/server-github")
        form.addRow("Komut / URL:", self.target_input)

        layout.addLayout(form)

        # Action buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Sunucuyu Ekle")
        save_btn.setStyleSheet("background-color: #00F0FF; color: #080B10; font-weight: bold;")
        save_btn.clicked.connect(self._on_save)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def _on_save(self):
        name = self.name_input.text().strip()
        target = self.target_input.text().strip()
        if not name or not target:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen sunucu adını ve komut/URL bilgisini doldurun.")
            return
        self.accept()

    def get_data(self):
        s_type = "stdio" if self.radio_stdio.isChecked() else "http"
        return self.name_input.text().strip(), s_type, self.target_input.text().strip()

class MCPDrawerWidget(QFrame):
    """Visual dock to inspect, toggle, and register Model Context Protocol servers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.mcp_manager = MCPManager()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("<b style='color:#00F0FF; font-size:13px;'>🔌 MCP ARAÇ VE PROTOKOL MERKEZİ</b>")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        add_btn = QPushButton("+ Yeni MCP Ekle")
        add_btn.setFixedHeight(22)
        add_btn.setStyleSheet("background-color:#00F0FF; color:#080B10; font-weight:bold; font-size:11px;")
        add_btn.clicked.connect(self._open_add_dialog)
        header_layout.addWidget(add_btn)

        self.sync_btn = QPushButton("Yenile")
        self.sync_btn.setFixedHeight(22)
        self.sync_btn.clicked.connect(self.refresh_servers)
        header_layout.addWidget(self.sync_btn)

        self.layout.addLayout(header_layout)

        # Server List Container
        self.servers_layout = QVBoxLayout()
        self.servers_layout.setSpacing(4)
        self.layout.addLayout(self.servers_layout)

        self.refresh_servers()

    def refresh_servers(self):
        while self.servers_layout.count():
            item = self.servers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        servers = self.mcp_manager.list_servers()
        for s in servers:
            row = QHBoxLayout()
            row.setContentsMargins(6, 4, 6, 4)

            status_color = "#00FF9D" if s["status"].lower() == "enabled" else "#8B949E"
            status_text = "Aktif" if s["status"].lower() == "enabled" else "Pasif"

            info_lbl = QLabel(
                f"<b style='color:#F0F6FC;'>{s['name']}</b> "
                f"<span style='color:#8B949E; font-size:10px;'>({s['type']})</span><br/>"
                f"<span style='color:#8B949E; font-size:10px;'>{s.get('target', '')[:40]}</span>"
            )
            row.addWidget(info_lbl)
            row.addStretch()

            cb = QCheckBox(status_text)
            cb.setStyleSheet(f"color: {status_color}; font-weight: bold; font-size: 11px;")
            cb.setChecked(s["status"].lower() == "enabled")
            cb.toggled.connect(lambda checked, s_name=s["name"], box=cb: self._on_toggle(s_name, checked, box))
            row.addWidget(cb)

            row_widget = QFrame()
            row_widget.setStyleSheet(f"background: {CYBER_THEME['bg_terminal']}; border: 1px solid #1F2B42; border-radius: 4px;")
            row_widget.setLayout(row)
            self.servers_layout.addWidget(row_widget)

    def _on_toggle(self, server_name: str, enabled: bool, box: QCheckBox):
        if enabled:
            ok = self.mcp_manager.enable_server(server_name)
            box.setText("Aktif")
            box.setStyleSheet("color: #00FF9D; font-weight: bold; font-size: 11px;")
        else:
            ok = self.mcp_manager.disable_server(server_name)
            box.setText("Pasif")
            box.setStyleSheet("color: #8B949E; font-weight: bold; font-size: 11px;")

    def _open_add_dialog(self):
        dialog = AddMCPServerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, s_type, target = dialog.get_data()
            success = self.mcp_manager.add_server(name, s_type, target)
            if success:
                QMessageBox.information(self, "Başarılı", f"'{name}' MCP sunucusu başarıyla eklendi!")
                self.refresh_servers()
            else:
                QMessageBox.critical(self, "Hata", f"'{name}' MCP sunucusu eklenirken bir hata oluştu.")
