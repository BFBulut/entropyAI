"""MCP Server Management Drawer Widget with add / edit / remove dialogs."""

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QRadioButton, QScrollArea, QVBoxLayout, QWidget
)

from entropy.core.event_bus import bus
from entropy.mcp.manager import MCPManager
from entropy.ui.themes.cyber_theme import CYBER_THEME



def parse_env_text(text: str) -> Dict[str, str]:
    """`KEY=VALUE` satırlarını ortam değişkeni sözlüğüne çevirir."""
    env: Dict[str, str] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            env[key] = value.strip()
    return env


def format_env_dict(env: Optional[Dict[str, str]]) -> str:
    if not env:
        return ""
    return "\n".join(f"{k}={v}" for k, v in env.items())


class MCPServerDialog(QDialog):
    """
    MCP sunucusu ekleme ve düzenleme formu.

    Alanlar doğrudan mcp_config.json şemasına karşılık gelir: stdio sunucuda
    command + args + env, http sunucuda serverUrl. Düzenleme kipinde mevcut
    değerler doldurulur; ad değiştirilirse kayıt yeni adla taşınır.
    """

    def __init__(self, parent=None, server: Optional[Dict] = None):
        super().__init__(parent)
        self.existing = server or None
        self.setWindowTitle("MCP Sunucusunu Düzenle" if server else "Yeni MCP Sunucusu Ekle")
        self.setMinimumWidth(460)

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

        self.args_input = QLineEdit()
        self.args_input.setPlaceholderText("Boşlukla ayrılmış ek argümanlar (isteğe bağlı)")
        form.addRow("Ek Argümanlar:", self.args_input)

        self.env_input = QPlainTextEdit()
        self.env_input.setPlaceholderText("KEY=VALUE (her satıra bir tane)")
        self.env_input.setFixedHeight(70)
        form.addRow("Ortam (env):", self.env_input)

        layout.addLayout(form)

        hint = QLabel(
            "<span style='color:#8B949E; font-size:11px;'>Kayıt agy'nin "
            "<code>~/.gemini/config/mcp_config.json</code> dosyasına yazılır; "
            "bir sonraki ajan turunda etkin olur.</span>"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Action buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setAccessibleName("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Kaydet" if server else "Sunucuyu Ekle")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._on_save)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

        if server:
            self._prefill(server)

    def _prefill(self, server: Dict) -> None:
        self.name_input.setText(server.get("name", ""))
        if server.get("type") == "http" or server.get("url"):
            self.radio_http.setChecked(True)
            self.target_input.setText(server.get("url") or server.get("target", ""))
        else:
            self.radio_stdio.setChecked(True)
            command = server.get("command") or ""
            args = server.get("args") or []
            self.target_input.setText(" ".join([command] + list(args)).strip() or server.get("target", ""))
        self.env_input.setPlainText(format_env_dict(server.get("env")))

    def _on_save(self):
        if not self.name_input.text().strip() or not self.target_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen sunucu adını ve komut/URL bilgisini doldurun.")
            return
        self.accept()

    def get_data(self):
        """(ad, tip, komut/url) — geriye dönük uyumlu üçlü."""
        s_type = "stdio" if self.radio_stdio.isChecked() else "http"
        return self.name_input.text().strip(), s_type, self.target_input.text().strip()

    def get_extra(self):
        """(argümanlar, env) — formun genişletilmiş alanları."""
        args: List[str] = [a for a in self.args_input.text().split() if a]
        return args, parse_env_text(self.env_input.toPlainText())


# Geriye dönük ad (dışarıdan içe aktaran kod kırılmasın).
AddMCPServerDialog = MCPServerDialog


class MCPDrawerWidget(QFrame):
    """Visual dock to inspect, toggle, edit, and register Model Context Protocol servers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.mcp_manager = MCPManager()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("MCP sunucuları")
        title_label.setProperty("role", "heading")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        add_btn = QPushButton("+ Yeni MCP Ekle")
        add_btn.setAccessibleName("+ Yeni MCP Ekle")
        add_btn.setProperty("variant", "primary")
        add_btn.clicked.connect(self._open_add_dialog)
        header_layout.addWidget(add_btn)

        self.sync_btn = QPushButton("Yenile")
        self.sync_btn.setAccessibleName("Yenile")
        self.sync_btn.setProperty("variant", "primary")
        self.sync_btn.clicked.connect(self.refresh_servers)
        header_layout.addWidget(self.sync_btn)

        self.layout.addLayout(header_layout)

        # Scroll Area for Server Cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        container = QWidget()
        self.servers_layout = QVBoxLayout(container)
        self.servers_layout.setContentsMargins(0, 4, 0, 4)
        self.servers_layout.setSpacing(6)
        scroll_area.setWidget(container)
        self.layout.addWidget(scroll_area)

        # Yapılandırma başka bir yerden (ör. otonom görev) değişirse liste tazelensin.
        bus.mcp_servers_updated.connect(self.refresh_servers)

        self.refresh_servers()

    def _small_button(self, text: str, color: str, bg: str) -> QPushButton:
        btn = QPushButton(text)
        return btn

    def refresh_servers(self):
        while self.servers_layout.count():
            item = self.servers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        servers = self.mcp_manager.list_servers(force_refresh=True)
        for s in servers:
            card = QFrame()
            card.setProperty("role", "panel")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            card_layout.setSpacing(12)

            icon = "" if s["type"] == "http" else ""
            icon_lbl = QLabel(f"<span style='font-size:18px;'>{icon}</span>")
            icon_lbl.setProperty("role", "label")
            card_layout.addWidget(icon_lbl)

            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(3)

            status_badge = "<span style='color:#00FF9D; font-size:11px; font-weight:bold;'>● AKTİF</span>" if s["status"].lower() == "enabled" else "<span style='color:#8B949E; font-size:11px;'>○ PASİF</span>"
            name_lbl = QLabel(f"<b style='color:#F0F6FC; font-size:13px;'>{s['name']}</b> &nbsp; <span style='color:#8B949E; font-size:11px;'>({s['type']})</span> &nbsp; {status_badge}")
            name_lbl.setProperty("role", "label")

            target_val = s.get('target', '')
            target_lbl = QLabel(f"<code style='background:#05070A; color:#8B949E; border:1px solid #1F2B42; border-radius:3px; padding:2px 6px; font-family:Consolas; font-size:11px;'>{target_val[:80]}</code>")
            target_lbl.setProperty("role", "label")

            info_layout.addWidget(name_lbl)
            info_layout.addWidget(target_lbl)
            card_layout.addLayout(info_layout)
            card_layout.addStretch()

            # Toggle checkbox
            cb = QCheckBox("Etkin")
            cb.setChecked(s["status"].lower() == "enabled")
            cb.toggled.connect(lambda checked, s_name=s["name"], box=cb: self._on_toggle(s_name, checked, box))
            card_layout.addWidget(cb)

            # Edit server button
            edit_btn = self._small_button("Düzenle", "#00F0FF", "#141C2C")
            edit_btn.clicked.connect(lambda _, s_name=s["name"]: self._open_edit_dialog(s_name))
            card_layout.addWidget(edit_btn)

            # Remove server button
            del_btn = self._small_button("Kaldır", "#FF4D4D", "#261418")
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
        ok = self.mcp_manager.toggle_server(server_name, enabled)
        if ok:
            durum = "etkinleştirildi" if enabled else "pasife alındı"
            bus.terminal_output_received.emit(f"[MCP Hub] '{server_name}' sunucusu {durum}.\n")
        else:
            QMessageBox.warning(
                self, "Hata",
                f"'{server_name}' sunucusunun durumu değiştirilemedi (yapılandırma dosyası yazılamadı)."
            )
        self.refresh_servers()

    def _open_add_dialog(self):
        dialog = MCPServerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, s_type, target = dialog.get_data()
            args, env = dialog.get_extra()
            try:
                success = self.mcp_manager.add_server(name, s_type, target, args=args, env=env)
            except ValueError as e:
                QMessageBox.critical(self, "Geçersiz Yapılandırma", str(e))
                return
            if success:
                QMessageBox.information(self, "Başarılı", f"'{name}' MCP sunucusu başarıyla eklendi!")
                self.refresh_servers()
            else:
                QMessageBox.critical(self, "Hata", f"'{name}' MCP sunucusu eklenirken bir hata oluştu.")

    def _open_edit_dialog(self, server_name: str):
        server = self.mcp_manager.get_server(server_name)
        if not server:
            QMessageBox.warning(self, "Bulunamadı", f"'{server_name}' sunucusu yapılandırmada bulunamadı.")
            return
        dialog = MCPServerDialog(self, server=server)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_name, s_type, target = dialog.get_data()
        args, env = dialog.get_extra()
        try:
            success = self.mcp_manager.update_server(
                server_name,
                server_type=s_type,
                command_or_url=target,
                args=args,
                env=env,
                new_name=new_name,
            )
        except ValueError as e:
            QMessageBox.critical(self, "Geçersiz Yapılandırma", str(e))
            return
        if success:
            bus.terminal_output_received.emit(f"[MCP Hub] '{new_name}' sunucusu güncellendi.\n")
            self.refresh_servers()
        else:
            QMessageBox.critical(self, "Hata", f"'{server_name}' güncellenemedi.")

    def closeEvent(self, event):
        try:
            bus.mcp_servers_updated.disconnect(self.refresh_servers)
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(event)
