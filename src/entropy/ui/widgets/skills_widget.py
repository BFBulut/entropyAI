"""Interactive Cyber Skills & Tools Management Widget for Zen Mode."""

import os
import subprocess
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.skills.manager import SkillManager, SkillDefinition
from entropy.ui.themes.cyber_theme import CYBER_THEME

class AddSkillDialog(QDialog):
    """Dialog to manually register or synthesize a new skill."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Yetenek (Skill) Oluştur")
        self.setFixedSize(500, 420)
        self.setStyleSheet("""
            QDialog {
                background-color: #0E1420;
                color: #F0F6FC;
            }
            QLabel { color: #F0F6FC; font-size: 12px; }
            QLineEdit, QTextEdit {
                background-color: #05070A;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 6px;
                color: #F0F6FC;
                font-family: 'Segoe UI', Consolas;
            }
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { border-color: #00F0FF; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: crypto-trader veya code-optimizer")
        form.addRow("Yetenek Adı:", self.name_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Bu yetenek ne yapar, ne zaman devreye girer?")
        form.addRow("Açıklama:", self.desc_input)

        layout.addLayout(form)

        layout.addWidget(QLabel("<b>Yetenek Yönergeleri & Talimatlar (Markdown):</b>"))
        self.instructions_input = QTextEdit()
        self.instructions_input.setPlaceholderText(
            "# Yetenek Kullanım Talimatları\n\n"
            "1. Kullanıcı bu analizi talep ettiğinde şu adımları izleyin...\n"
            "2. Çıktıyı şu formatta hazırlayın..."
        )
        layout.addWidget(self.instructions_input)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Yeteneği Kaydet")
        save_btn.setStyleSheet("background-color: #00F0FF; color: #080B10; font-weight: bold;")
        save_btn.clicked.connect(self._on_save)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def _on_save(self):
        name = self.name_input.text().strip()
        desc = self.desc_input.text().strip()
        inst = self.instructions_input.toPlainText().strip()
        if not name or not desc or not inst:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen tüm alanları doldurun.")
            return
        self.accept()

    def get_data(self):
        return self.name_input.text().strip(), self.desc_input.text().strip(), self.instructions_input.toPlainText().strip()

class DownloadSkillDialog(QDialog):
    """Dialog to download a raw SKILL.md from a web or GitHub URL."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İnternetten Skill (SKILL.md) İndir")
        self.setFixedSize(480, 200)
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
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { border-color: #00F0FF; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://raw.githubusercontent.com/.../SKILL.md")
        form.addRow("Skill URL'si:", self.url_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Opsiyonel özel isim (boş bırakılabilir)")
        form.addRow("Özel İsim:", self.name_input)

        layout.addLayout(form)

        info_lbl = QLabel("<span style='color:#8B949E; font-size:11px;'>Not: Doğrudan raw SKILL.md bağlantısı giriniz. Dosya otomatik olarak indirilip tescil edilecektir.</span>")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        dl_btn = QPushButton("İndir ve Yükle")
        dl_btn.setStyleSheet("background-color: #00FF9D; color: #080B10; font-weight: bold;")
        dl_btn.clicked.connect(self._on_download)
        btn_box.addWidget(dl_btn)

        layout.addLayout(btn_box)

    def _on_download(self):
        url = self.url_input.text().strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            QMessageBox.warning(self, "Geçersiz URL", "Lütfen geçerli bir http/https bağlantısı girin.")
            return
        self.accept()

    def get_data(self):
        return self.url_input.text().strip(), self.name_input.text().strip() or None

class SkillsWidget(QFrame):
    """Visual dock to browse, toggle, download, and manage AI Skills."""

    def __init__(self, parent=None, skill_manager: Optional[SkillManager] = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.skill_manager = skill_manager or SkillManager()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("<b style='color:#00F0FF; font-size:13px;'>🎯 YETENEKLER & ARAÇ KÜTÜPHANESİ</b>")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        dl_btn = QPushButton("📥 URL'den İndir")
        dl_btn.setFixedHeight(24)
        dl_btn.setStyleSheet("""
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
        dl_btn.clicked.connect(self._open_download_dialog)
        header_layout.addWidget(dl_btn)

        add_btn = QPushButton("+ Yeni Yetenek")
        add_btn.setFixedHeight(24)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00F0FF;
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
                color: #F0F6FC;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 2px 12px;
                font-size: 11px;
            }
            QPushButton:hover { border-color: #00F0FF; }
        """)
        self.sync_btn.clicked.connect(self.refresh_skills)
        header_layout.addWidget(self.sync_btn)

        self.layout.addLayout(header_layout)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Yetenek ara (örn: pdf, finans, medya)...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #05070A;
                border: 1px solid #1F2B42;
                border-radius: 4px;
                padding: 4px 8px;
                color: #F0F6FC;
                font-size: 11px;
            }
        """)
        self.search_input.textChanged.connect(self._filter_skills)
        self.layout.addWidget(self.search_input)

        # Scroll Area for Skill Cards
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
        self.skills_layout = QVBoxLayout(container)
        self.skills_layout.setContentsMargins(0, 4, 0, 4)
        self.skills_layout.setSpacing(6)
        scroll_area.setWidget(container)
        self.layout.addWidget(scroll_area)

        self.refresh_skills()

    def refresh_skills(self):
        """Reload list of skills from filesystem."""
        while self.skills_layout.count():
            item = self.skills_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        skills = self.skill_manager.list_skills()
        filter_text = self.search_input.text().strip().lower()

        for s in skills:
            if filter_text and filter_text not in s.name.lower() and filter_text not in s.description.lower():
                continue

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

            icon_lbl = QLabel("<span style='font-size:18px;'>🎯</span>")
            icon_lbl.setStyleSheet("background: transparent; border: none;")
            card_layout.addWidget(icon_lbl)

            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(3)

            status_badge = "<span style='color:#00FF9D; font-size:10px; font-weight:bold;'>● AKTİF</span>" if s.enabled else "<span style='color:#8B949E; font-size:10px;'>○ PASİF</span>"
            script_badge = f"<span style='background:#05070A; color:#00F0FF; border:1px solid #1F2B42; border-radius:3px; padding:1px 5px; font-size:10px;'>💻 {len(s.scripts)} Araç</span>" if s.scripts else ""
            
            title_text = f"<b style='color:#F0F6FC; font-size:13px;'>{s.name}</b> &nbsp; {status_badge} &nbsp; {script_badge}"
            name_lbl = QLabel(title_text)
            name_lbl.setStyleSheet("background: transparent; border: none;")

            desc_lbl = QLabel(f"<span style='color:#8B949E; font-size:11px;'>{s.description[:85]}</span>")
            desc_lbl.setStyleSheet("background: transparent; border: none;")

            info_layout.addWidget(name_lbl)
            info_layout.addWidget(desc_lbl)
            card_layout.addLayout(info_layout)
            card_layout.addStretch()

            # Active toggle
            cb = QCheckBox("Etkin")
            cb.setStyleSheet("color:#00FF9D; font-weight:bold; font-size:11px; background:transparent;")
            cb.setChecked(s.enabled)
            cb.toggled.connect(lambda checked, s_name=s.name: self._on_toggle(s_name, checked))
            card_layout.addWidget(cb)

            # Open folder button
            folder_btn = QPushButton("📂")
            folder_btn.setFixedSize(26, 26)
            folder_btn.setToolTip("Yetenek Klasörünü Aç")
            folder_btn.setStyleSheet("background-color:#141C2C; color:#F0F6FC; border:1px solid #1F2B42; border-radius:4px;")
            folder_btn.clicked.connect(lambda _, s_path=s.path: self._open_folder(Path(s_path).parent))
            card_layout.addWidget(folder_btn)

            # Delete button
            del_btn = QPushButton("🗑️")
            del_btn.setFixedSize(26, 26)
            del_btn.setToolTip("Yeteneği Sil")
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #261418;
                    color: #FF4D4D;
                    border: 1px solid #FF4D4D;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FF4D4D;
                    color: #080B10;
                }
            """)
            del_btn.clicked.connect(lambda _, s_name=s.name: self._on_delete(s_name))
            card_layout.addWidget(del_btn)

            self.skills_layout.addWidget(card)

        self.skills_layout.addStretch()

    def _filter_skills(self):
        self.refresh_skills()

    def _on_toggle(self, skill_name: str, enabled: bool):
        self.skill_manager.toggle_skill(skill_name, enabled)
        self.refresh_skills()

    def _on_delete(self, skill_name: str):
        reply = QMessageBox.question(
            self,
            "Yeteneği Sil",
            f"'{skill_name}' yeteneğini ve araç dosyalarını kalıcı olarak silmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.skill_manager.delete_skill(skill_name)
            self.refresh_skills()

    def _open_folder(self, folder_path: Path):
        if folder_path.exists():
            if os.name == "nt":
                os.startfile(str(folder_path))
            else:
                subprocess.run(["xdg-open", str(folder_path)])

    def _open_add_dialog(self):
        dlg = AddSkillDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, desc, inst = dlg.get_data()
            self.skill_manager.create_skill(name, desc, inst)
            QMessageBox.information(self, "Başarılı", f"'{name}' yeteneği başarıyla oluşturuldu!")
            self.refresh_skills()

    def _open_download_dialog(self):
        dlg = DownloadSkillDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            url, custom_name = dlg.get_data()
            skill = self.skill_manager.download_skill_from_url(url, custom_name)
            if skill:
                QMessageBox.information(self, "Başarılı", f"'{skill.name}' yeteneği internetten başarıyla indirildi!")
                self.refresh_skills()
            else:
                QMessageBox.critical(self, "Hata", "Yetenek URL'den indirilemedi. Lütfen bağlantıyı kontrol edin.")
