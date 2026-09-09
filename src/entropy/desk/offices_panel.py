"""
Ofis listesi paneli: ofisleri listeler, oluşturur, düzenler, siler.

Kaynak `entropy.agents.offices.OfficeRegistry` (agy ajanı yazıyor). İçe aktarma
korumalı: modül yoksa panel boş liste + açıklayıcı uyarı gösterir, çökmez.
Testler yapıcıya sahte kayıt defteri verebilir.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.agents_widget import (
    DIALOG_STYLE, build_dataclass, call_contract, spec_field,
)
from entropy.ui.widgets.ui_polish import (
    BODY_PX, apply_list_polish, apply_no_hscroll, icon_button_style, set_item_text,
)

PROVIDERS = ("agy", "claude")


def load_office_registry() -> Optional[Any]:
    """DeskRegistry örneği (Faz 6 kayıt defteri); sözleşme modülü yoksa None."""
    try:
        from entropy.agents.desk_registry import DeskRegistry  # type: ignore

        return DeskRegistry()
    except Exception:
        return None


def load_agent_registry() -> Optional[Any]:
    """
    Desk'in ajan görünümü — Entropy'nin `Entropy/Agents` kadrosu DEĞİL.

    Desk kendi ofislerinin ajanlarını kullanır (Faz 6, kural 1); panelde
    Entropy'nin ajanlarını listelemek kullanıcıya seçilemeyecek adlar
    gösteriyordu.
    """
    try:
        from entropy.agents.desk_registry import DeskAgentsView  # type: ignore

        return DeskAgentsView()
    except Exception:
        return None


def agents_by_role(registry: Any, role: str) -> List[str]:
    """
    Rol filtresi: `AgentSpec.role` sözleşmede worker|orchestrator|evaluator.

    Rolü boş bırakılmış ajanlar da listeye alınır — kullanıcı ofisi kurarken
    henüz rol atamamış olabilir; onları gizlemek combo'yu boş bırakırdı.
    """
    names: List[str] = []
    try:
        specs = list(registry.list() or []) if registry is not None else []
    except Exception:
        specs = []
    for spec in specs:
        name = str(spec_field(spec, "name", ""))
        if not name:
            continue
        spec_role = str(spec_field(spec, "role", "")).strip().lower()
        if spec_role in ("", role, "worker") or role == "any":
            names.append(name)
    return names


def all_agent_names(registry: Any) -> List[str]:
    try:
        return [str(spec_field(s, "name", "")) for s in (registry.list() or []) if spec_field(s, "name", "")]
    except Exception:
        return []


class OfficeEditDialog(QDialog):
    """Ofis oluştur/düzenle formu; `get_data()` sözleşme alanlarını döner."""

    def __init__(self, parent=None, office: Any = None, agent_registry: Any = None):
        super().__init__(parent)
        self.setWindowTitle("Ofis Düzenle" if office is not None else "Yeni Ofis")
        self.setMinimumWidth(520)
        self.setStyleSheet(DIALOG_STYLE)
        self._agent_registry = agent_registry

        form = QFormLayout(self)
        form.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("ör. arastirma-ofisi")
        form.addRow("Ad", self.name_edit)

        self.purpose_edit = QLineEdit()
        self.purpose_edit.setPlaceholderText("Bu ofis ne iş yapar?")
        form.addRow("Amaç", self.purpose_edit)

        orch_names = agents_by_role(agent_registry, "orchestrator")
        eval_names = agents_by_role(agent_registry, "evaluator")
        every = all_agent_names(agent_registry)

        self.orchestrator_combo = QComboBox()
        self.orchestrator_combo.setEditable(True)
        self.orchestrator_combo.addItems(orch_names)
        form.addRow("Orkestratör", self.orchestrator_combo)

        self.evaluator_combo = QComboBox()
        self.evaluator_combo.setEditable(True)
        # Değerlendirici isteğe bağlı: boş seçenek ilk sırada.
        self.evaluator_combo.addItem("")
        self.evaluator_combo.addItems(eval_names)
        form.addRow("Değerlendirici", self.evaluator_combo)

        self.members_list = QListWidget()
        self.members_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.members_list.setMaximumHeight(140)
        apply_list_polish(self.members_list)
        for name in every:
            self.members_list.addItem(QListWidgetItem(name))
        form.addRow("Üyeler", self.members_list)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(list(PROVIDERS))
        form.addRow("Sağlayıcı", self.provider_combo)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("varsayılan model (boş = sağlayıcı varsayılanı)")
        form.addRow("Model", self.model_edit)

        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, 8)
        self.parallel_spin.setValue(2)
        form.addRow("Paralellik", self.parallel_spin)

        self.budget_spin = QSpinBox()
        self.budget_spin.setRange(0, 5_000_000)
        self.budget_spin.setSingleStep(10_000)
        self.budget_spin.setValue(60_000)
        form.addRow("Bütçe (token)", self.budget_spin)

        self.charter_edit = QPlainTextEdit()
        self.charter_edit.setPlaceholderText("Ofis tüzüğü: ne yapar, kabul standartları…")
        self.charter_edit.setMinimumHeight(120)
        form.addRow("Tüzük", self.charter_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        # Qt standart düğmeleri sistem dilinde ("Save"/"Cancel") geliyor; arayüzün
        # geri kalanı Türkçe olduğu için metinler açıkça yazılır.
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Kaydet")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.buttons = buttons

        if office is not None:
            self._prefill(office)

    def _prefill(self, office: Any) -> None:
        self.name_edit.setText(str(spec_field(office, "name", "")))
        self.purpose_edit.setText(str(spec_field(office, "purpose", "")))
        self._set_combo(self.orchestrator_combo, str(spec_field(office, "orchestrator", "")))
        self._set_combo(self.evaluator_combo, str(spec_field(office, "evaluator", "")))
        members = set(str(m) for m in (spec_field(office, "members", []) or []))
        for i in range(self.members_list.count()):
            item = self.members_list.item(i)
            if item.text() in members:
                item.setSelected(True)
                members.discard(item.text())
        # Kayıt defterinde olmayan üyeler (dosya elle düzenlenmiş olabilir) kaybolmasın.
        for extra in sorted(members):
            item = QListWidgetItem(extra)
            self.members_list.addItem(item)
            item.setSelected(True)
        provider = str(spec_field(office, "default_provider", "agy")) or "agy"
        if provider in PROVIDERS:
            self.provider_combo.setCurrentText(provider)
        self.model_edit.setText(str(spec_field(office, "default_model", "")))
        try:
            self.parallel_spin.setValue(int(spec_field(office, "max_parallel", 2) or 2))
        except (TypeError, ValueError):
            pass
        try:
            self.budget_spin.setValue(int(spec_field(office, "budget_tokens", 0) or 0))
        except (TypeError, ValueError):
            pass
        self.charter_edit.setPlainText(str(spec_field(office, "charter", "")))

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        if not value:
            return
        if combo.findText(value) < 0:
            combo.addItem(value)
        combo.setCurrentText(value)

    @Slot()
    def _on_save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Ofis adı zorunludur.")
            return
        self.accept()

    def selected_members(self) -> List[str]:
        return [i.text() for i in self.members_list.selectedItems()]

    def get_data(self) -> Dict[str, Any]:
        members = self.selected_members()
        orchestrator = self.orchestrator_combo.currentText().strip()
        evaluator = self.evaluator_combo.currentText().strip()
        # Orkestratör ve değerlendirici de ofisin üyesidir; sahne ve roster
        # onları listede bulamazsa masaları ortada kalırdı.
        for extra in (orchestrator, evaluator):
            if extra and extra not in members:
                members.append(extra)
        return {
            "name": self.name_edit.text().strip(),
            "purpose": self.purpose_edit.text().strip(),
            "orchestrator": orchestrator,
            "evaluator": evaluator,
            "members": members,
            "default_provider": self.provider_combo.currentText(),
            "default_model": self.model_edit.text().strip(),
            "max_parallel": self.parallel_spin.value(),
            "budget_tokens": self.budget_spin.value(),
            "charter": self.charter_edit.toPlainText().strip(),
        }


class OfficesPanel(QFrame):
    """Sol sütun: ofis listesi + CRUD düğmeleri."""

    office_selected = Signal(str)

    def __init__(self, parent=None, registry: Any = None, agent_registry: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.registry = registry if registry is not None else load_office_registry()
        self.agent_registry = agent_registry if agent_registry is not None else load_agent_registry()
        self.current_office: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b style='color:{RT['accent']}; font-size:13px;'>🏢 OFİSLER</b>"))
        header.addStretch()
        self.create_btn = QPushButton("+ Ofis")
        self.create_btn.setFixedHeight(24)
        self.create_btn.setToolTip("Yeni ofis oluştur")
        self.create_btn.clicked.connect(self.create_office)
        header.addWidget(self.create_btn)
        layout.addLayout(header)

        self.empty_label = QLabel("")
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(
            f"color:{RT['text_dim']}; font-size:{BODY_PX}px; padding:6px 2px;"
            " background:transparent; border:none;"
        )
        layout.addWidget(self.empty_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            f"""
            QListWidget {{
                background-color:{RT['surface_base']};
                border:1px solid {RT['divider_soft']};
                border-radius:{RT['radius']};
                color:{RT['text']};
                font-size:{BODY_PX}px;
            }}
            QListWidget::item {{ padding:8px 10px; }}
            QListWidget::item:selected {{
                background-color:{RT['accent_soft']}; color:{RT['accent']};
            }}
            """
        )
        # Uzun ofis amacı yatay kaydırma çubuğu doğurmasın; sağdan kırpılır.
        apply_list_polish(self.list_widget)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.list_widget, 1)

        # İkon + kısa metin düğmeler; her birinin ipucu var (ikon tek başına
        # ne yaptığını anlatmıyor, metin tek başına dar sütuna sığmıyor).
        actions = QHBoxLayout()
        actions.setSpacing(6)
        for attr, label, tip, handler in (
            ("edit_btn", "✏️ Düzenle", "Seçili ofisi düzenle", self.edit_current),
            ("delete_btn", "📦 Arşivle",
             "Seçili ofisi arşive taşı (silinmez; kartlar, sorgular ve posta arşive gider)",
             self.delete_current),
            ("refresh_btn", "🔄 Yenile", "Ofis listesini yeniden oku", self.refresh_offices),
        ):
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setFixedHeight(28)
            btn.setStyleSheet(icon_button_style())
            btn.clicked.connect(handler)
            setattr(self, attr, btn)
            actions.addWidget(btn)
        layout.addLayout(actions)

        signal = getattr(bus, "offices_updated", None)
        if signal is not None:
            signal.connect(self._on_offices_updated)

        self.refresh_offices()

    # ------------------------------------------------------------ veri

    def list_offices(self) -> List[Any]:
        if self.registry is None:
            return []
        try:
            return list(self.registry.list() or [])
        except Exception:
            return []

    def office_names(self) -> List[str]:
        return [str(spec_field(o, "name", "")) for o in self.list_offices()]

    def get_office(self, name: str) -> Optional[Any]:
        for office in self.list_offices():
            if str(spec_field(office, "name", "")) == name:
                return office
        return None

    @Slot(str)
    def _on_offices_updated(self, _payload: str = "") -> None:
        """Sinyal alıcısı QObject metodu (lambda değil)."""
        self.refresh_offices()

    @Slot()
    def refresh_offices(self) -> None:
        previous = self.current_office
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        offices = self.list_offices()
        for office in offices:
            name = str(spec_field(office, "name", ""))
            purpose = str(spec_field(office, "purpose", ""))
            # Görünen metin tek satır: kırpmayı Qt'ye (ElideRight) bırakırız,
            # sabit karakter kesmesi (eski purpose[:60]) hem kelime ortasından
            # bölüyor hem de ipucu vermeden bilgi gizliyordu.
            item = QListWidgetItem()
            set_item_text(
                item,
                f"{name} · {purpose}" if purpose else name,
                tooltip=f"{name}\n{purpose}" if purpose else name,
            )
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

        if not offices:
            self.empty_label.setText(
                "Henüz ofis yok. “+ Ofis” ile bir ofis kurun."
                if self.registry is not None
                else "Ofis kayıt defteri modülü yüklenemedi (entropy.agents.offices)."
            )
            self.empty_label.setVisible(True)
            self.current_office = ""
            self.office_selected.emit("")
            return
        self.empty_label.setVisible(False)

        names = [str(spec_field(o, "name", "")) for o in offices]
        target = previous if previous in names else names[0]
        self.select_office(target)

    def select_office(self, name: str) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                self.list_widget.setCurrentRow(i)
                if self.current_office != name:
                    self.current_office = name
                    self.office_selected.emit(name)
                elif self.current_office == name:
                    self.office_selected.emit(name)
                return

    def _on_current_changed(self, current, _previous) -> None:
        if current is None:
            return
        name = str(current.data(Qt.ItemDataRole.UserRole) or "")
        if name and name != self.current_office:
            self.current_office = name
            self.office_selected.emit(name)

    # ------------------------------------------------------------ eylemler

    @Slot()
    def create_office(self) -> None:
        dialog = OfficeEditDialog(parent=self, agent_registry=self.agent_registry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply_office_save(dialog.get_data(), original_name=None)

    @Slot()
    def edit_current(self) -> None:
        office = self.get_office(self.current_office)
        if office is None:
            return
        dialog = OfficeEditDialog(parent=self, office=office, agent_registry=self.agent_registry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply_office_save(dialog.get_data(), original_name=self.current_office)

    def apply_office_save(self, data: Dict[str, Any], original_name: Optional[str]) -> bool:
        """Diyalogsuz kayıt yolu (test edilebilir): create ya da update çağırır."""
        if self.registry is None:
            return False
        office_obj = build_dataclass("entropy.agents.desk_registry", "DeskOffice", data)
        try:
            if original_name:
                call_contract(self.registry.update, data, office_obj, original_name)
                if data.get("name") and data["name"] != original_name:
                    try:
                        self.registry.delete(original_name)
                    except Exception:
                        pass
            else:
                call_contract(self.registry.create, data, office_obj)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Ofisler] Kayıt hatası: {exc}\n")
            return False
        self.current_office = str(data.get("name", "") or original_name or "")
        self.refresh_offices()
        signal = getattr(bus, "offices_updated", None)
        if signal is not None:
            signal.emit(str(data.get("name", "")))
        return True

    @Slot()
    def delete_current(self) -> None:
        self.archive_office(self.current_office)

    def archive_office(self, name: str, confirm: bool = True) -> bool:
        """
        Ofisi ARŞİVLER (Faz 9 / B-9.6) — silmez.

        `vault_hygiene.archive_office` ofis klasörünü, wiki sorgu sayfalarını ve
        posta kayıtlarını `Entropy/_archive/<tarih>/` altına taşır. Eskiden
        `registry.delete()` çağrılıyordu: bir ofisin bütün kart geçmişi ve
        raporları geri dönülmez biçimde gidiyordu. Arşiv çağrısı yapılamazsa
        kayıt defterinden düşürme YAPILMAZ (veri kaybı riski) ve kullanıcı
        uyarılır.
        """
        if self.registry is None or not name:
            return False
        if confirm:
            answer = QMessageBox.question(
                self, "Ofisi Arşivle",
                f"'{name}' ofisi ARŞİVE TAŞINACAK, SİLİNMEYECEK.\n\n"
                f"Klasörü, sorgu sayfaları ve posta kayıtları "
                f"Entropy/_archive/<tarih>/ altına taşınır; ajan tanımları "
                f"korunur. Devam edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        try:
            from entropy.memory.vault_hygiene import archive_office as _archive

            vault_path = getattr(self.registry, "vault_path", None)
            result = _archive(name, vault_path=vault_path, dry_run=False)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Ofisler] Arşivleme hatası: {exc}\n")
            return False
        moved = 0
        try:
            moved = int(result.get("count", 0) or 0)
        except Exception:
            moved = 0
        bus.terminal_output_received.emit(
            f"[Ofisler] '{name}' arşivlendi ({moved} öğe taşındı).\n"
        )
        # Kayıt defterinden düşürme: arşiv başarılı olduktan SONRA.
        try:
            self.registry.delete(name)
        except Exception as exc:
            bus.terminal_output_received.emit(
                f"[Ofisler] Arşiv tamam, defterden düşürülemedi: {exc}\n"
            )
        if self.current_office == name:
            self.current_office = ""
        self.refresh_offices()
        signal = getattr(bus, "offices_updated", None)
        if signal is not None:
            signal.emit(name)
        return True

    # Geri uyum: eski çağrılar/testler `delete_office` diyor; artık arşivler.
    def delete_office(self, name: str, confirm: bool = True) -> bool:
        return self.archive_office(name, confirm=confirm)
