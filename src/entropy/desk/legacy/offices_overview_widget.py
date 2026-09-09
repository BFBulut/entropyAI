"""
Entropy Agent Desk: Offices Overview Widget.
High-level birds-eye floor view of all active agent offices:
- Displays all offices, their orchestrators, team sizes, and task statistics.
- Header integrates the live Antigravity connection status badge.
- Actions to create, edit, enter, and delete offices with immediate disk persistence.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from src.entropy.agent_desk.core.office_manager import OfficeManager
from src.entropy.agent_desk.core.agy_model_registry import AGYModelRegistry
from src.entropy.agent_desk.ui.agy_status_widget import AgyStatusWidget
from src.entropy.agent_desk.ui.template_picker_dialog import TemplatePickerDialog


class OfficeCard(QFrame):
    office_entered = Signal(str)
    office_edited = Signal(str)
    office_deleted = Signal(str)

    def __init__(self, summary: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.office_id = summary["office_id"]
        self.setStyleSheet(
            """
            OfficeCard {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 10px;
                padding: 12px;
            }
            OfficeCard:hover {
                border: 1px solid #6366f1;
            }
            """
        )
        self.setFixedWidth(340)
        self.setFixedHeight(230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # Title
        lbl_title = QLabel(f"🏢 {summary['name']}")
        lbl_title.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: bold;")
        layout.addWidget(lbl_title)

        # Project Path
        lbl_path = QLabel(f"📁 {summary['project_root'][:34]}")
        lbl_path.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lbl_path)

        # Orchestrator & Model
        model_name = AGYModelRegistry.get_display_name(summary.get("orchestrator_model"))
        lbl_orch = QLabel(f"👑 Lider: [{model_name}]")
        lbl_orch.setStyleSheet("color: #a855f7; font-size: 12px; font-weight: bold;")
        layout.addWidget(lbl_orch)

        # Agent & Task stats
        stats_text = (
            f"👥 Kadro: {summary['agent_count']} Ajan\n"
            f"📋 Aktif: {summary['active_tasks']} | Bekleyen: {summary['pending_tasks']} | Tamam: {summary['completed_tasks']}"
        )
        lbl_stats = QLabel(stats_text)
        lbl_stats.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        layout.addWidget(lbl_stats)

        layout.addStretch()

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(6)

        btn_enter = QPushButton("🚀 Ofise Gir")
        btn_enter.setStyleSheet(
            "background-color: #2563eb; color: #ffffff; padding: 6px 12px; border-radius: 6px; font-weight: bold;"
        )
        btn_enter.clicked.connect(lambda: self.office_entered.emit(self.office_id))

        btn_edit = QPushButton("✏️")
        btn_edit.setToolTip("Ofisi Düzenle")
        btn_edit.setFixedSize(30, 30)
        btn_edit.setStyleSheet(
            "background-color: #475569; color: #ffffff; border-radius: 6px; font-weight: bold;"
        )
        btn_edit.clicked.connect(lambda: self.office_edited.emit(self.office_id))

        btn_delete = QPushButton("🗑️")
        btn_delete.setToolTip("Ofisi Kapat ve Sil")
        btn_delete.setFixedSize(30, 30)
        btn_delete.setStyleSheet(
            "background-color: #ef4444; color: #ffffff; border-radius: 6px; font-weight: bold;"
        )
        btn_delete.clicked.connect(lambda: self.office_deleted.emit(self.office_id))

        btn_box.addWidget(btn_enter, 1)
        btn_box.addWidget(btn_edit)
        btn_box.addWidget(btn_delete)
        layout.addLayout(btn_box)


class OfficesOverviewWidget(QWidget):
    office_selected = Signal(str)

    def __init__(self, office_manager: OfficeManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.office_manager = office_manager
        self._setup_ui()
        self.refresh_offices()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Bar with Antigravity Status
        header = QFrame()
        header.setStyleSheet("background-color: #1a202c; border-radius: 8px; padding: 6px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 6, 10, 6)

        title = QLabel("🏢 Otonom Ajan Ofisleri (Entropy Agent Spaces)")
        title.setStyleSheet("color: #f8fafc; font-size: 17px; font-weight: bold;")

        # Live AGY Status
        self.agy_status_widget = AgyStatusWidget()

        btn_new_office = QPushButton("➕ Yeni Ofis Oluştur")
        btn_new_office.setStyleSheet(
            "background-color: #16a34a; color: #ffffff; padding: 6px 14px; border-radius: 6px; font-weight: bold;"
        )
        btn_new_office.clicked.connect(self._prompt_create_office)

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setStyleSheet("background-color: #334155; color: #f8fafc; padding: 6px 12px; border-radius: 6px;")
        btn_refresh.clicked.connect(self.refresh_offices)

        h_layout.addWidget(title)
        h_layout.addStretch()
        h_layout.addWidget(self.agy_status_widget)
        h_layout.addWidget(btn_new_office)
        h_layout.addWidget(btn_refresh)
        layout.addWidget(header)

        # Scroll Area for Office Cards Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, 1)

    def refresh_offices(self):
        # Önceki kartları temizle
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        summaries = self.office_manager.get_all_offices_summary()
        if not summaries:
            empty_lbl = QLabel("Henüz bir ofis bulunmuyor. Yeni bir ofis oluşturabilir veya çalışmak istediğiniz projeyi bağlayabilirsiniz.")
            empty_lbl.setStyleSheet("color: #94a3b8; font-size: 14px; padding: 40px;")
            self.grid_layout.addWidget(empty_lbl, 0, 0)
            return

        cols = 3
        for idx, summary in enumerate(summaries):
            card = OfficeCard(summary)
            card.office_entered.connect(self.office_selected.emit)
            card.office_edited.connect(self._edit_office)
            card.office_deleted.connect(self._delete_office)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def _prompt_create_office(self):
        dialog = TemplatePickerDialog(parent=self)
        if dialog.exec() == TemplatePickerDialog.Accepted:
            data = dialog.get_data()
            tmpl_id = data["template_id"]
            if tmpl_id == "custom_empty":
                self.office_manager.create_office(
                    name=data["name"],
                    project_root=data["project_root"],
                    description=data["description"],
                    auto_init_specialists=False,
                )
            else:
                self.office_manager.create_office_from_template(
                    template_id=tmpl_id,
                    name=data["name"],
                    project_root=data["project_root"],
                    description=data["description"],
                )
            self.refresh_offices()

    def _edit_office(self, office_id: str):
        orch = self.office_manager.get_office(office_id)
        if not orch:
            return

        new_name, ok1 = QInputDialog.getText(self, "Ofisi Düzenle", "Ofis Adı:", text=orch.config.name)
        if not ok1 or not new_name.strip():
            return

        new_path, ok2 = QInputDialog.getText(self, "Ofisi Düzenle", "Proje Kök Dizini:", text=orch.config.project_root)
        if not ok2 or not new_path.strip():
            return

        new_desc, ok3 = QInputDialog.getText(self, "Ofisi Düzenle", "Açıklama:", text=orch.config.description)
        if not ok3:
            new_desc = orch.config.description

        models = AGYModelRegistry.list_model_ids()
        cur_idx = models.index(orch.persona.model) if orch.persona.model in models else 0
        model_str, ok4 = QInputDialog.getItem(self, "Ofisi Düzenle", "Lider Modeli:", models, cur_idx, False)
        if not ok4:
            model_str = orch.persona.model

        self.office_manager.update_office(
            office_id=office_id,
            name=new_name.strip(),
            project_root=new_path.strip(),
            description=new_desc.strip(),
            orchestrator_model=model_str,
        )
        self.refresh_offices()

    def _delete_office(self, office_id: str):
        orch = self.office_manager.get_office(office_id)
        name = orch.config.name if orch else office_id
        reply = QMessageBox.question(
            self,
            "Ofisi Kapat ve Sil",
            f"'{name}' ofisini ve altındaki tüm personelleri kalıcı olarak kapatmak istediğinize emin misiniz?\n(Bu işlem geri alınamaz ve uygulama yeniden açıldığında tekrar oluşturulmaz.)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.office_manager.delete_office(office_id)
            self.refresh_offices()
