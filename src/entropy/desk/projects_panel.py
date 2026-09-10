"""
Desk "Projeler" sekmesi: ofisin projeleri, ekleme ve kart süzme.

Faz 7: kartların `project` alanı vardı ama arayüzde proje kavramı yoktu;
kullanıcı hangi kartın hangi işe ait olduğunu ancak dosya adından çıkarıyordu.
Panel `DeskRegistry.list_projects/create_project` sözleşmesini kullanır; defter
yoksa panel boş ama çalışır durumda kalır (Desk penceresi çökmesin).

"Kartları süz" düğmesi seçili projeyi dışarı yayar; pencere bunu
`TaskBoardWidget.set_project_filter` ile Kartlar sekmesine uygular.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from entropy.core.event_bus import bus
from entropy.platform.proc import popen_kwargs
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.agents_widget import list_cards_for, load_board, spec_field


def load_desk_registry() -> Optional[Any]:
    """`DeskRegistry()`; modül yoksa None (panel boş listeyle çalışır)."""
    try:
        from entropy.agents.desk_registry import DeskRegistry  # type: ignore

        return DeskRegistry()
    except Exception:
        return None


DEFAULT_WORKTREE_DIRNAME = ".entropy-worktrees"


def git_branches(repo_path: str) -> List[str]:
    """
    Depodaki yerel dallar (`git branch --list`). Git yoksa, yol depo değilse ya
    da komut zaman aşımına uğrarsa boş liste döner; form o zaman SERBEST METİN
    kutusuna düşer (kullanıcı dal adını elle yazabilsin).
    """
    path = Path(str(repo_path or ""))
    if not path.is_dir():
        return []
    try:
        proc = subprocess.run(
            ["git", "branch", "--list", "--format=%(refname:short)"],
            cwd=str(path), capture_output=True, text=True, timeout=5,
            # Konsolsuz exe'de `git` çağrısı yeni bir konsol penceresi
            # açıyordu (Faz 13-A2 hayalet pencere bulgusu).
            **popen_kwargs(),
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    return [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]


def is_git_repo(repo_path: str) -> bool:
    """Yol bir git deposu mu (`.git` klasörü ya da dosyası)."""
    path = Path(str(repo_path or ""))
    return path.is_dir() and (path / ".git").exists()


def default_worktree_root(repo_path: str) -> str:
    """`<repo>/../.entropy-worktrees` — depo dışında, kardeş klasörde."""
    path = Path(str(repo_path or "").strip())
    if not str(path) or str(path) == ".":
        return ""
    return str((path.parent / DEFAULT_WORKTREE_DIRNAME).resolve()) if path.name else ""


def validate_project_form(data: Dict[str, str]) -> str:
    """
    Form doğrulaması → hata metni ("" = geçerli).

    Ad kontrolü buradadır (sözleşme yalnızca depoyu doğrular). Depo için
    GERÇEK sözleşme `desk_registry.validate_project_repo(repo_path,
    base_branch)`; mesajı olduğu gibi kırmızı ipuca basılır (uzun yol,
    alt klasör, eksik dal gibi durumları yalnızca o bilir). Sözleşme yoksa
    aşağıdaki yerel kurallara düşülür.
    """
    if not str(data.get("name", "")).strip():
        return "Proje adı zorunludur."
    repo = str(data.get("repo_path", "")).strip()
    branch_value = str(data.get("base_branch", "")).strip()
    try:
        from entropy.agents.desk_registry import validate_project_repo  # type: ignore

        if callable(validate_project_repo):
            message = str(validate_project_repo(repo, branch_value) or "")
            if message:
                return message
            if not repo and branch_value:
                return "Dal verildi ama depo yolu boş."
            return ""
    except Exception:
        pass
    if repo:
        if not Path(repo).is_dir():
            return "Depo yolu bulunamadı."
        if not is_git_repo(repo):
            return "Bu klasör bir git deposu değil (.git yok)."
        branch = str(data.get("base_branch", "")).strip()
        branches = git_branches(repo)
        if branch and branches and branch not in branches:
            return f"“{branch}” dalı depoda yok."
    elif str(data.get("base_branch", "")).strip():
        return "Dal verildi ama depo yolu boş."
    return ""


class ProjectEditDialog(QDialog):
    """Proje formu: ad, hedef, kapsam + depo yolu / taban dal / worktree kökü."""

    def __init__(self, parent=None, office: str = "", project: Any = None):
        super().__init__(parent)
        self.setWindowTitle(f"Yeni Proje — {office}" if office else "Yeni Proje")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("kisa-proje-adi")
        self.name_input.textChanged.connect(self._revalidate)
        form.addRow("Ad:", self.name_input)
        self.goal_input = QLineEdit()
        self.goal_input.setPlaceholderText("Bu proje neyi başarmalı?")
        form.addRow("Hedef:", self.goal_input)

        # --- Faz 10-C: proje = depo -----------------------------------
        repo_row = QHBoxLayout()
        repo_row.setSpacing(4)
        self.repo_input = QLineEdit()
        self.repo_input.setPlaceholderText("depo klasörü (git)")
        self.repo_input.textChanged.connect(self._on_repo_changed)
        repo_row.addWidget(self.repo_input, 1)
        self.repo_browse_btn = QPushButton("…")
        self.repo_browse_btn.setAccessibleName("…")
        self.repo_browse_btn.setFixedWidth(30)
        self.repo_browse_btn.setToolTip("Klasör seç")
        self.repo_browse_btn.clicked.connect(self.browse_repo)
        repo_row.addWidget(self.repo_browse_btn)
        repo_host = QWidget()
        repo_host.setLayout(repo_row)
        form.addRow("Depo yolu:", repo_host)

        self.branch_combo = QComboBox()
        self.branch_combo.setEditable(True)   # git yoksa serbest metin
        self.branch_combo.setToolTip(
            "Taban dal; depodan okunur, git yoksa elle yazılabilir."
        )
        self.branch_combo.currentTextChanged.connect(self._revalidate)
        form.addRow("Taban dal:", self.branch_combo)

        self.worktree_input = QLineEdit()
        self.worktree_input.setPlaceholderText(f"<depo>/../{DEFAULT_WORKTREE_DIRNAME}")
        form.addRow("Worktree kökü:", self.worktree_input)
        layout.addLayout(form)

        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setProperty("role", "label")
        self.hint_label.setProperty("tone", "danger")
        self.hint_label.setVisible(False)
        layout.addWidget(self.hint_label)
        layout.addWidget(QLabel("Kapsam / notlar:"))
        self.charter_input = QPlainTextEdit()
        self.charter_input.setMinimumHeight(90)
        layout.addWidget(self.charter_input)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("İptal")
        cancel.setAccessibleName("İptal")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save_btn = QPushButton("Oluştur")
        self.save_btn.setAccessibleName("Oluştur")
        self.save_btn.clicked.connect(self._on_save)
        buttons.addWidget(self.save_btn)
        layout.addLayout(buttons)

        if project is not None:
            self._prefill(project)
        self._revalidate()

    def _prefill(self, project: Any) -> None:
        self.name_input.setText(str(spec_field(project, "name", "")))
        self.goal_input.setText(str(spec_field(project, "goal", "")))
        self.charter_input.setPlainText(str(spec_field(project, "charter", "")))
        self.repo_input.setText(str(spec_field(project, "repo_path", "") or ""))
        base = str(spec_field(project, "base_branch", "") or "")
        if base:
            if self.branch_combo.findText(base) < 0:
                self.branch_combo.addItem(base)
            self.branch_combo.setCurrentText(base)
        self.worktree_input.setText(str(spec_field(project, "worktree_root", "") or ""))

    # ------------------------------------------------------------ depo

    @Slot()
    def browse_repo(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Depo klasörü seç", self.repo_input.text())
        if chosen:
            self.repo_input.setText(chosen)

    @Slot(str)
    def _on_repo_changed(self, text: str) -> None:
        """Depo değişince dal listesi ve worktree kökü varsayılanı tazelenir."""
        repo = str(text or "").strip()
        current = self.branch_combo.currentText().strip()
        branches = git_branches(repo)
        self.branch_combo.blockSignals(True)
        self.branch_combo.clear()
        if branches:
            self.branch_combo.addItems(branches)
            preferred = current if current in branches else (
                "main" if "main" in branches else
                ("master" if "master" in branches else branches[0])
            )
            self.branch_combo.setCurrentText(preferred)
        else:
            self.branch_combo.setCurrentText(current)
        self.branch_combo.blockSignals(False)
        if repo and not self.worktree_input.text().strip():
            self.worktree_input.setPlaceholderText(default_worktree_root(repo))
        self._revalidate()

    def validation_error(self) -> str:
        return validate_project_form(self.get_data())

    @Slot()
    def _revalidate(self) -> None:
        """Kırmızı ipucu + Kaydet düğmesinin etkinliği tek yerden yönetilir."""
        error = self.validation_error()
        self.hint_label.setText(error)
        self.hint_label.setVisible(bool(error))
        self.save_btn.setEnabled(not error)

    def _on_save(self) -> None:
        error = self.validation_error()
        if error:
            QMessageBox.warning(self, "Eksik Bilgi", error)
            return
        self.accept()

    def get_data(self) -> Dict[str, str]:
        repo = self.repo_input.text().strip()
        worktree_root = self.worktree_input.text().strip() or default_worktree_root(repo)
        return {
            "name": self.name_input.text().strip(),
            "goal": self.goal_input.text().strip(),
            "charter": self.charter_input.toPlainText().strip(),
            "repo_path": repo,
            "base_branch": self.branch_combo.currentText().strip(),
            "worktree_root": worktree_root if repo else "",
        }


class ProjectsPanel(QFrame):
    """Ofis projeleri: liste + durum sayacı + ekle + kart süzme."""

    project_filter_changed = Signal(str)   # "" = süzgeç yok

    def __init__(self, parent=None, office: str = "", desk: Any = None, board: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.office = office or ""
        self.desk = desk if desk is not None else load_desk_registry()
        self.board = board if board is not None else load_board()
        self.filtered_project: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        head = QHBoxLayout()
        self.title_label = QLabel("")
        self.title_label.setProperty("role", "label")
        head.addWidget(self.title_label)
        head.addStretch()
        self.add_btn = QPushButton("+ Proje")
        self.add_btn.setAccessibleName("+ Proje")
        self.add_btn.clicked.connect(self.create_project)
        head.addWidget(self.add_btn)
        self.filter_btn = QPushButton("Kartları süz")
        self.filter_btn.setAccessibleName("Kartları süz")
        self.filter_btn.setToolTip("Kartlar sekmesini seçili projeye süz")
        self.filter_btn.clicked.connect(self.apply_filter)
        head.addWidget(self.filter_btn)
        self.clear_btn = QPushButton("Süzgeci kaldır")
        self.clear_btn.setAccessibleName("Süzgeci kaldır")
        self.clear_btn.clicked.connect(self.clear_filter)
        head.addWidget(self.clear_btn)
        layout.addLayout(head)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        # --- Faz 10-B: "Çalışma belleği" hızlı görüntüleyici -----------------
        # Ofisin ortak çalışma dosyaları (BOARD.md / ARCHITECTURE.md /
        # RULES.md) SALT OKUNUR gösterilir; arayüz kasaya yazmaz — dosyaların
        # tek yazarı ajanlar/bellek katmanıdır.
        ws_head = QHBoxLayout()
        ws_head.setSpacing(4)
        ws_title = QLabel("Çalışma belleği:")
        ws_title.setProperty("role", "label")
        ws_head.addWidget(ws_title)
        self.workspace_buttons: Dict[str, QPushButton] = {}
        for key, label in (("board", "BOARD.md"),
                           ("architecture", "ARCHITECTURE.md"),
                           ("rules", "RULES.md")):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setProperty("workspace_key", key)
            btn.setToolTip(f"{label} dosyasını salt okunur göster")
            btn.clicked.connect(self._on_workspace_clicked)
            ws_head.addWidget(btn)
            self.workspace_buttons[key] = btn
        ws_head.addStretch()
        layout.addLayout(ws_head)

        self.workspace_view = QTextBrowser()
        self.workspace_view.setReadOnly(True)
        self.workspace_view.setOpenExternalLinks(False)
        self.workspace_view.setMaximumHeight(200)
        self.workspace_view.setProperty("role", "reader")
        self.workspace_view.setVisible(False)
        layout.addWidget(self.workspace_view)

        self.setMinimumWidth(220)
        self.set_office(self.office)

    # -------------------------------------------------------------- veri

    def set_office(self, office: str) -> None:
        self.office = office or ""
        self.filtered_project = ""
        self.workspace_view.setVisible(False)
        self.workspace_view.clear()
        self.refresh()

    # ------------------------------------------------ çalışma belleği

    def workspace_paths(self) -> Dict[str, Any]:
        """`office_workspace.workspace_paths`; modül/ofis yoksa boş sözlük."""
        if not self.office:
            return {}
        try:
            from entropy.brain.office_workspace import workspace_paths  # type: ignore

            return dict(workspace_paths(self.office) or {})
        except Exception:
            return {}

    @Slot()
    def _on_workspace_clicked(self) -> None:
        sender = self.sender()
        self.show_workspace(str(sender.property("workspace_key") or ""))

    def show_workspace(self, key: str) -> str:
        """
        Çalışma belleği dosyasını görüntüler ve gösterilen metni döndürür.

        Dosya yoksa açıklayıcı bir satır basılır (boş kutu "bozuk mu?"
        sorusunu doğuruyordu).
        """
        paths = self.workspace_paths()
        path = paths.get(key)
        text = ""
        if path is not None:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                text = ""
        self.workspace_view.setVisible(True)
        if not text.strip():
            name = getattr(path, "name", key or "dosya")
            self.workspace_view.setMarkdown("")
            self.workspace_view.setPlainText(
                f"{name} henüz yazılmadı. Ofis çalışmaya başlayınca ajanlar doldurur."
            )
            return ""
        self.workspace_view.setMarkdown(text)
        return text

    def workspace_text(self) -> str:
        """Test için: görüntüleyicideki düz metin."""
        return self.workspace_view.toPlainText()

    def list_projects(self) -> List[Any]:
        if self.desk is None or not self.office:
            return []
        try:
            return list(self.desk.list_projects(self.office) or [])
        except Exception:
            return []

    def card_counts(self) -> Dict[str, Dict[str, int]]:
        """Proje -> {toplam, calisan, biten} sayaçları."""
        out: Dict[str, Dict[str, int]] = {}
        if self.board is None or not self.office:
            return out
        # Faz 9: ofis kartları `Desk/Offices/<ofis>/cards/` altında;
        # `list()` (ofissiz) yalnızca Entropy kartlarını döndürdüğü için
        # sayaçlar sıfır görünüyordu.
        cards = list_cards_for(self.board, self.office)
        for card in cards:
            if self.office and str(spec_field(card, "office", "")) != self.office:
                continue
            project = str(spec_field(card, "project", ""))
            if not project:
                continue
            bucket = out.setdefault(project, {"toplam": 0, "calisan": 0, "biten": 0})
            bucket["toplam"] += 1
            status = str(spec_field(card, "status", ""))
            if status in ("running", "review"):
                bucket["calisan"] += 1
            elif status == "done":
                bucket["biten"] += 1
        return out

    def refresh(self) -> None:
        self.list_widget.clear()
        projects = self.list_projects()
        counts = self.card_counts()
        for project in projects:
            name = str(spec_field(project, "name", ""))
            goal = str(spec_field(project, "goal", ""))
            stat = counts.get(name, {"toplam": 0, "calisan": 0, "biten": 0})
            text = f"{name} — {stat['toplam']} kart · {stat['calisan']} çalışan · {stat['biten']} bitti"
            if goal:
                text += f"\n{goal}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip(goal or name)
            self.list_widget.addItem(item)
        suffix = f" · süzgeç: {self.filtered_project}" if self.filtered_project else ""
        self.title_label.setText(
            f"<b style='color:{RT['accent']}; font-size:13px;'>PROJELER</b>"
            f" <span style='color:{RT['text_dim']}; font-size:11px;'>"
            f"{self.office or 'ofis seçilmedi'} · {len(projects)} proje{suffix}</span>"
        )
        self.add_btn.setEnabled(bool(self.office) and self.desk is not None)

    def project_names(self) -> List[str]:
        return [str(spec_field(p, "name", "")) for p in self.list_projects()]

    # ------------------------------------------------------------ eylemler

    def selected_project(self) -> str:
        item = self.list_widget.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    @Slot()
    def create_project(self) -> None:
        if not self.office:
            return
        dialog = ProjectEditDialog(parent=self, office=self.office)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.add_project(dialog.get_data())

    def add_project(self, data: Dict[str, str]) -> bool:
        """Diyalogsuz ekleme yolu (test edilebilir)."""
        if self.desk is None or not self.office or not data.get("name"):
            return False
        error = validate_project_form(dict(data))
        if error:
            bus.terminal_output_received.emit(f"[Projeler] Geçersiz form: {error}\n")
            return False
        try:
            from entropy.agents.desk_registry import DeskProject  # type: ignore

            fields = {
                "name": data["name"], "office": self.office,
                "goal": data.get("goal", ""), "charter": data.get("charter", ""),
            }
            # Faz 10-C alanları sözleşmede varsa geçilir; ajan katmanı henüz
            # eklemediyse proje eski alanlarla yaratılır (form çökmesin).
            for key in ("repo_path", "base_branch", "worktree_root"):
                if data.get(key):
                    fields[key] = data[key]
            try:
                project = DeskProject(**fields)
            except TypeError:
                for key in ("repo_path", "base_branch", "worktree_root"):
                    fields.pop(key, None)
                project = DeskProject(**fields)
            self.desk.create_project(self.office, project)
        except Exception as exc:
            bus.terminal_output_received.emit(f"[Projeler] Proje eklenemedi: {exc}\n")
            return False
        self.refresh()
        return True

    @Slot()
    def apply_filter(self) -> None:
        self.set_filter(self.selected_project())

    @Slot()
    def clear_filter(self) -> None:
        self.set_filter("")

    def set_filter(self, project: str) -> None:
        self.filtered_project = project or ""
        self.refresh()
        self.project_filter_changed.emit(self.filtered_project)
