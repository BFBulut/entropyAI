"""
Komut paleti (Faz 5.5) — Ctrl+K ile her şeye tek yerden erişim.

Sorun: yerel komutlar eğik çizgi menüsünde, yetenekler bir sekmede, ajanlar
başka sekmede, ofisler Agent Desk'te, raporlar üçüncü bir listede duruyordu.
Bir şeyi açmak için önce nerede olduğunu hatırlamak gerekiyordu. Palet bu beş
kaynağı tek listede toplar ve bulanık (fuzzy) aramayla süzer.

Tasarım kaynağı: `docs/reports/2026-09-10_Faz5_Tasarim_Raporu.md` §3.3
("Yaşam tarzı arayüz: komut paleti (Ctrl+K) ...").

Mimari not: kaynak toplayıcılar guard'lıdır — ofis/ajan kayıt defteri kurulu
değilse palet o bölümü atlar, açılmayı reddetmez. Toplama saf Python'dur ve
`collect_palette_items()` ile testten doğrudan çağrılabilir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout,
)

from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.ui_polish import BODY_PX, LABEL_PX
# Gömülü HTML gövdelerinin renk kaynağı (Faz 12-D.2): düz onaltılık yerine
# `TOKENS`/`TOKENS["viz"]` köprüsü. Bkz. `entropy.ui.design.embedded`.
from entropy.ui.design.embedded import live_palette as _live_palette

# Faz 12-F: canli palet — tema degisince gomulu govdeler de doner.
_P = _live_palette()

# Palette bölümleri ve rozetleri: kullanıcı sonucun nereden geldiğini görsün.
KIND_BADGES = {
    "command": ("⌘", "Komut", f"{_P["accent"]}"),
    "skill": ("", "Yetenek", f"{_P["ok"]}"),
    "agent": ("", "Ajan", f"{_P["accent"]}"),
    "office": ("", "Ofis", f"{_P["warn"]}"),
    "report": ("", "Rapor", f"{_P["neutral"]}"),
}

MAX_RESULTS = 40


# ------------------------------------------------------------ bulanık arama

def fuzzy_score(query: str, text: str) -> float:
    """
    Alt dizi (subsequence) tabanlı bulanık eşleşme puanı; eşleşme yoksa -1.

    Puanlama: sorgu harfleri metinde sırayla bulunmalıdır. Bitişik eşleşmeler
    ve sözcük başına denk gelen eşleşmeler ödüllendirilir; böylece "rpm" →
    "Rapor Merkezi" gibi baş harf yazımları üste çıkar. Tam alt dizge eşleşmesi
    ayrıca bonus alır.
    """
    q = (query or "").strip().lower()
    t = (text or "").lower()
    if not q:
        return 0.0
    if not t:
        return -1.0
    if q in t:
        # Tam alt dizge: baştaysa daha da iyi.
        return 100.0 - t.index(q) * 0.5 - len(t) * 0.01
    score = 0.0
    ti = 0
    prev_hit = -2
    for ch in q:
        found = t.find(ch, ti)
        if found < 0:
            return -1.0
        score += 1.0
        if found == prev_hit + 1:
            score += 1.5
        if found == 0 or t[found - 1] in " -_/:.":
            score += 2.0
        prev_hit = found
        ti = found + 1
    return score - len(t) * 0.01


def filter_items(
    items: Sequence[Dict[str, Any]],
    query: str,
    limit: int = MAX_RESULTS,
) -> List[Dict[str, Any]]:
    """Palet girdilerini sorguya göre süzüp puana göre sıralar."""
    q = (query or "").strip()
    if not q:
        return list(items)[:limit]
    scored: List[tuple] = []
    for item in items:
        haystack = f"{item.get('label', '')} {item.get('subtitle', '')}"
        score = max(fuzzy_score(q, str(item.get("label", ""))), fuzzy_score(q, haystack))
        if score >= 0:
            scored.append((-score, str(item.get("label", "")), item))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [item for _, _, item in scored[:limit]]


# ------------------------------------------------------------ kaynaklar

def _command_items(project_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    try:
        from entropy.core.slash_commands import SlashCommandRegistry

        commands = SlashCommandRegistry().get_all_commands(project_dir=project_dir)
    except Exception:
        return []
    return [
        {
            "kind": "command",
            "label": cmd.name,
            "subtitle": cmd.description,
            "payload": cmd.usage or cmd.name,
        }
        for cmd in commands or []
    ]


def _skill_items(project_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    try:
        from entropy.skills.manager import SkillManager

        skills = SkillManager(project_dir=project_dir).list_skills() if project_dir \
            else SkillManager().list_skills()
    except Exception:
        return []
    out = []
    for skill in skills or []:
        name = getattr(skill, "name", "") or ""
        if not name:
            continue
        out.append({
            "kind": "skill",
            "label": name,
            "subtitle": getattr(skill, "description", "") or "",
            "payload": f"/{name}",
        })
    return out


def _agent_items() -> List[Dict[str, Any]]:
    try:
        from entropy.agents.registry import AgentRegistry

        specs = AgentRegistry().list()
    except Exception:
        return []
    return [
        {
            "kind": "agent",
            "label": getattr(s, "name", ""),
            "subtitle": getattr(s, "role", "") or "",
            "payload": f"/agent {getattr(s, 'name', '')}",
        }
        for s in specs or [] if getattr(s, "name", "")
    ]


def _office_items() -> List[Dict[str, Any]]:
    try:
        from entropy.agents.offices import OfficeRegistry

        specs = OfficeRegistry().list()
    except Exception:
        return []
    return [
        {
            "kind": "office",
            "label": getattr(s, "name", ""),
            "subtitle": getattr(s, "purpose", "") or "",
            "payload": f"/ask {getattr(s, 'name', '')} ",
        }
        for s in specs or [] if getattr(s, "name", "")
    ]


def _report_items(limit: int = 80) -> List[Dict[str, Any]]:
    try:
        from entropy.ui.widgets.report_inbox import collect_recent_entries
    except Exception:
        return []
    out = []
    for entry in collect_recent_entries(limit=limit):
        path = str(entry.get("path", ""))
        if not path:
            continue
        out.append({
            "kind": "report",
            "label": str(entry.get("title") or Path(path).stem),
            "subtitle": str(entry.get("skill") or entry.get("folder") or ""),
            "payload": path,
        })
    return out


def collect_palette_items(
    project_dir: Optional[Path] = None,
    sources: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Beş kaynaktan palet girdilerini toplar: komutlar, yetenekler, ajanlar,
    ofisler, raporlar. Herhangi bir kaynak patlarsa o bölüm boş geçilir.
    """
    wanted = set(sources or ("command", "skill", "agent", "office", "report"))
    items: List[Dict[str, Any]] = []
    if "command" in wanted:
        items += _command_items(project_dir)
    if "skill" in wanted:
        items += _skill_items(project_dir)
    if "agent" in wanted:
        items += _agent_items()
    if "office" in wanted:
        items += _office_items()
    if "report" in wanted:
        items += _report_items()
    return items


# --------------------------------------------------------------- görünüm

class CommandPalette(QDialog):
    """
    Ctrl+K paleti. Seçim yapılınca `item_activated(kind, payload, label)` yayılır.

    Çağıran taraf yayını yorumlar: komut/yetenek/ofis girdisi giriş satırına
    yazılır, rapor girdisi okuyucuda açılır, ajan girdisi `/agent <ad>` çalışır.
    Palet kendi başına hiçbir şey çalıştırmaz — böylece Zen ve Chat aynı paleti
    farklı bağlamlarda kullanabilir.
    """

    item_activated = Signal(str, str, str)  # kind, payload, label

    def __init__(self, parent=None, items: Optional[Sequence[Dict[str, Any]]] = None,
                 loader: Optional[Callable[[], List[Dict[str, Any]]]] = None):
        super().__init__(parent)
        self.setWindowTitle("Komut Paleti")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.resize(620, 420)
        self._loader = loader
        self._items: List[Dict[str, Any]] = list(items) if items is not None else []
        self._visible: List[Dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Komut, yetenek, ajan, ofis ya da rapor ara. Yukarı/aşağı gez, Enter aç, Esc kapat."
        )
        self.search_input.textChanged.connect(self.apply_filter)
        root.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self._on_item_chosen)
        self.list_widget.itemClicked.connect(self._on_item_chosen)
        root.addWidget(self.list_widget, 1)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "label")
        root.addWidget(self.status_label)

        # Enter, giriş satırındayken de listedeki seçimi açsın.
        QShortcut(QKeySequence(Qt.Key.Key_Return), self.search_input, self.activate_current)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self.search_input, self.activate_current)

        if items is None:
            self.reload()
        else:
            self.apply_filter("")

    # ------------------------------------------------------------ veri

    def reload(self) -> None:
        loader = self._loader or collect_palette_items
        try:
            self._items = list(loader() or [])
        except Exception:
            self._items = []
        self.apply_filter(self.search_input.text())

    def set_items(self, items: Sequence[Dict[str, Any]]) -> None:
        self._items = list(items or [])
        self.apply_filter(self.search_input.text())

    def visible_items(self) -> List[Dict[str, Any]]:
        return list(self._visible)

    def apply_filter(self, query: str = "") -> List[Dict[str, Any]]:
        self._visible = filter_items(self._items, query)
        self.list_widget.clear()
        for item in self._visible:
            icon, badge, color = KIND_BADGES.get(str(item.get("kind")), ("•", "", f"{_P["text_muted"]}"))
            subtitle = str(item.get("subtitle") or "")
            text = f"{icon}  {item.get('label', '')}"
            if subtitle:
                text += f"   —  {subtitle[:90]}"
            row = QListWidgetItem(text)
            row.setData(Qt.ItemDataRole.UserRole, item)
            row.setToolTip(f"[{badge}] {item.get('label', '')}\n{subtitle}")
            self.list_widget.addItem(row)
        if self._visible:
            self.list_widget.setCurrentRow(0)
        self.status_label.setText(
            f"{len(self._visible)} sonuç / {len(self._items)} girdi"
            if self._items else "Palet kaynakları okunamadı."
        )
        return self._visible

    # ------------------------------------------------------------ eylem

    def activate_current(self) -> Optional[Dict[str, Any]]:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._visible):
            return None
        item = self._visible[row]
        self.item_activated.emit(
            str(item.get("kind", "")), str(item.get("payload", "")), str(item.get("label", ""))
        )
        self.accept()
        return item

    def _on_item_chosen(self, _item: QListWidgetItem) -> None:
        self.activate_current()

    def keyPressEvent(self, event):  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            row = self.list_widget.currentRow()
            delta = 1 if key == Qt.Key.Key_Down else -1
            new_row = max(0, min(self.list_widget.count() - 1, row + delta))
            self.list_widget.setCurrentRow(new_row)
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate_current()
            return
        super().keyPressEvent(event)


class CommandPaletteController(QObject):
    """
    Ctrl+K kısayolunun alıcısı.

    Neden ayrı sınıf: sinyal alıcısı lambda/closure olmamalı — alıcı bir QObject
    slotu olduğunda bağlantı Qt'nin nesne yaşam döngüsüne bağlanır, pencere
    kapandığında kendiliğinden kopar ve palet ana iş parçacığında kalır.
    """

    def __init__(self, window, on_activated=None, loader=None):
        super().__init__(window)
        self.window = window
        self.on_activated = on_activated
        self.loader = loader
        self.palette: Optional[CommandPalette] = None

    @Slot()
    def open_palette(self) -> "CommandPalette":
        # Palet tembel kurulur: açılışta beş kaynağı taramak Zen'in açılış
        # süresini uzatırdı.
        if self.palette is None:
            self.palette = CommandPalette(parent=self.window, loader=self.loader)
            if self.on_activated is not None:
                self.palette.item_activated.connect(self.on_activated)
            self.window._command_palette = self.palette
        else:
            self.palette.reload()
        self.palette.show()
        self.palette.raise_()
        self.palette.search_input.setFocus()
        self.palette.search_input.selectAll()
        return self.palette


def install_command_palette(
    window,
    on_activated: Optional[Callable[[str, str, str], None]] = None,
    loader: Optional[Callable[[], List[Dict[str, Any]]]] = None,
) -> QShortcut:
    """Bir pencereye Ctrl+K kısayolu takar; paleti ilk açılışta kurar."""
    controller = CommandPaletteController(window, on_activated=on_activated, loader=loader)
    shortcut = QShortcut(QKeySequence("Ctrl+K"), window)
    shortcut.activated.connect(controller.open_palette)
    window._command_palette_controller = controller
    window._command_palette_shortcut = shortcut
    window._open_command_palette = controller.open_palette
    return shortcut
