"""MCP Server Management Drawer Widget with Add Server dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QRadioButton, QScrollArea, QVBoxLayout, QWidget
)

from entropy.core.event_bus import bus
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
        add_btn.setFixedHeight(24)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00FF9D;
                border: 1px solid #00FF9D;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00FF9D;
                color: #080B10;
            }
        """)
        add_btn.clicked.connect(self._open_add_dialog)
        header_layout.addWidget(add_btn)

        self.sync_btn = QPushButton("Yenile")
        self.sync_btn.setFixedHeight(24)
        self.sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 4px;
                padding: 2px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #080B10;
            }
        """)
        self.sync_btn.clicked.connect(self.refresh_servers)
        header_layout.addWidget(self.sync_btn)

        self.layout.addLayout(header_layout)

        # Scroll Area for Server Cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #05070A;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #1F2B42;
                border-radius: 3px;
            }
        """)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.servers_layout = QVBoxLayout(container)
        self.servers_layout.setContentsMargins(0, 4, 0, 4)
        self.servers_layout.setSpacing(6)
        scroll_area.setWidget(container)
        self.layout.addWidget(scroll_area)

        self.refresh_servers()

    def refresh_servers(self):
        while self.servers_layout.count():
            item = self.servers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        servers = self.mcp_manager.list_servers()
        for s in servers:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #0E1420;
                    border: 1px solid #1F2B42;
                    border-radius: 6px;
                }
                QFrame:hover {
                    border-color: #00F0FF;
                }
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            card_layout.setSpacing(12)

            icon = "🌐" if s["type"] == "http" else "💻"
            icon_lbl = QLabel(f"<span style='font-size:18px;'>{icon}</span>")
            icon_lbl.setStyleSheet("background: transparent; border: none;")
            card_layout.addWidget(icon_lbl)

            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(3)

            status_badge = "<span style='color:#00FF9D; font-size:10px; font-weight:bold;'>● AKTİF</span>" if s["status"].lower() == "enabled" else "<span style='color:#8B949E; font-size:10px;'>○ PASİF</span>"
            name_lbl = QLabel(f"<b style='color:#F0F6FC; font-size:13px;'>{s['name']}</b> &nbsp; <span style='color:#8B949E; font-size:11px;'>({s['type']})</span> &nbsp; {status_badge}")
            name_lbl.setStyleSheet("background: transparent; border: none;")

            target_val = s.get('target', '')
            target_lbl = QLabel(f"<code style='background:#05070A; color:#8B949E; border:1px solid #1F2B42; border-radius:3px; padding:2px 6px; font-family:Consolas; font-size:10px;'>{target_val[:80]}</code>")
            target_lbl.setStyleSheet("background: transparent; border: none;")

            info_layout.addWidget(name_lbl)
            info_layout.addWidget(target_lbl)
            card_layout.addLayout(info_layout)
            card_layout.addStretch()

            # Toggle checkbox
            cb = QCheckBox("Etkin")
            cb.setStyleSheet("color:#00FF9D; font-weight:bold; font-size:11px; background:transparent;")
            cb.setChecked(s["status"].lower() == "enabled")
            cb.toggled.connect(lambda checked, s_name=s["name"], box=cb: self._on_toggle(s_name, checked, box))
            card_layout.addWidget(cb)

            # Remove server button
            del_btn = QPushButton("🗑️ Kaldır")
            del_btn.setFixedHeight(26)
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #261418;
                    color: #FF4D4D;
                    border: 1px solid #FF4D4D;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FF4D4D;
                    color: #080B10;
                }
            """)
            del_btn.clicked.connect(lambda _, s_name=s["name"]: self._on_remove_server(s_name))
            card_layout.addWidget(del_btn)

            self.servers_layout.addWidget(card)

        self.servers_layout.addStretch()

    def _on_remove_server(self, server_name: str):
        reply = QMessageBox.question(
            self,
            "MCP Sunucusunu Kaldır",
            f"'{server_name}' MCP sunucusunu sistemden kaldırmak istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok = self.mcp_manager.remove_server(server_name)
            if ok:
                bus.terminal_output_received.emit(f"[MCP Hub] '{server_name}' sunucusu kaldırıldı.\n")
                self.refresh_servers()
            else:
                QMessageBox.warning(self, "Hata", f"'{server_name}' sunucusu kaldırılırken bir sorun oluştu.")

    def _on_toggle(self, server_name: str, enabled: bool, box: QCheckBox):
        if enabled:
            ok = self.mcp_manager.enable_server(server_name)
            self.refresh_servers()
        else:
            ok = self.mcp_manager.disable_server(server_name)
            self.refresh_servers()

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
