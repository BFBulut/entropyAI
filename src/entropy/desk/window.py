"""
Agent Desk penceresi: bağımsız üst pencere (QMainWindow, Qt.Window).

Düzen (tasarım raporu §2.3):
    sol   : OfficesPanel   — ofis listesi + CRUD
    orta  : üstte OfficeScene, altta sekmeler (Kartlar / Akış / Bellek)
    sağ   : RosterPanel    — ofisin ajanları, rol atamaları

Pencere Zen/Chat'ten bağımsızdır (ayrı üst pencere): kullanıcı ofisi ikinci
monitörde açık bırakıp sohbete devam edebilsin diye. Konum/boyut/ekran
`config.desk_geometry`'ye yazılır ve açılışta geri yüklenir; kayıtlı ekran
bağlı değilse birincil ekrana düşülür (aksi halde pencere görünmez bir
koordinatta açılırdı).

Tek örnek: `open_desk_window()` açık pencereyi öne getirir, ikincisini kurmaz.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QRect, Qt, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QSplitter, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.desk.board_panel import BoardPanel
from entropy.desk.offices_panel import OfficesPanel, load_office_registry
from entropy.desk.roster_panel import RosterPanel
from entropy.desk.scene import OfficeScene
from entropy.desk.stream_panel import StreamPanel
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT

WINDOW_TITLE = "Entropy Agent Desk"
DEFAULT_SIZE = (1400, 880)

# Kadro sütununun en küçük okunur genişliği: ajan kartındaki 3x2 ikon
# düğme ızgarası artı kimlik metni bu genişlik altında kırpılıyordu.
ROSTER_MIN_WIDTH = 380

TAB_CARDS = 0
TAB_STREAM = 1
TAB_MEMORY = 2


def load_office_memory(office_name: str) -> str:
    """
    Ofis belleğini (MEMORY.md) okur.

    Uygulamayı memory-rag ajanı yazıyor (`entropy.memory.office_memory.
    load_office_memory`); yoksa kasadaki dosya doğrudan okunur, o da yoksa
    açıklayıcı bir metin döner. Guard olmasaydı Bellek sekmesi modül gelene
    kadar pencereyi çökertirdi.
    """
    if not office_name:
        return ""
    try:
        from entropy.memory.office_memory import load_office_memory as _load  # type: ignore

        return str(_load(office_name) or "")
    except Exception:
        pass
    try:
        from pathlib import Path

        vault = Path(config.obsidian_vault_path)
        path = vault / "Entropy" / "Offices" / office_name / "MEMORY.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


class AgentDeskWindow(QMainWindow):
    """Ofis masası: sahne, kanban, akış, kadro ve ofis belleği tek pencerede."""

    def __init__(
        self,
        parent=None,
        office_registry: Any = None,
        agent_registry: Any = None,
        board: Any = None,
        bridge: Any = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        # Ana pencerenin çocuğu olarak kurulsa bile ayrı bir üst pencere olarak
        # yönetilsin: kendi görev çubuğu girdisi, kendi konumu, kendi ekranı.
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(*DEFAULT_SIZE)

        self.office_registry = office_registry if office_registry is not None else load_office_registry()
        self.agent_registry = agent_registry
        self.board = board
        self.bridge = bridge
        self.current_office: str = ""

        self._init_ui()
        self.restore_geometry()

    # ------------------------------------------------------------ arayüz

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        central.setStyleSheet(
            f"QWidget {{ background-color:{RT['surface_base']}; color:{RT['text']}; }}"
            f" QFrame#cardFrame {{ background-color:{RT['surface_raised']};"
            f" border:1px solid {RT['divider_soft']}; border-radius:{RT['radius']}; }}"
        )

        self.header_label = QLabel("")
        self.header_label.setStyleSheet("background: transparent; border: none;")
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)
        header.addWidget(self.header_label)
        header.addStretch()
        root.addLayout(header)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- sol: ofisler
        self.offices_panel = OfficesPanel(
            parent=self, registry=self.office_registry, agent_registry=self.agent_registry
        )
        self.offices_panel.office_selected.connect(self._on_office_selected)
        self.splitter.addWidget(self.offices_panel)

        # --- orta: sahne + sekmeler
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)
        center_splitter = QSplitter(Qt.Orientation.Vertical)

        self.scene = OfficeScene(parent=self)
        self.scene.agent_clicked.connect(self._on_agent_clicked)
        center_splitter.addWidget(self.scene)

        self.tabs = QTabWidget()
        self.board_panel = BoardPanel(parent=self, board=self.board, office="")
        self.stream_panel = StreamPanel(parent=self, board=self.board, office="")
        self.memory_view = QTextBrowser()
        self.memory_view.setStyleSheet(
            f"QTextBrowser {{ background-color:{RT['surface_base']};"
            f" border:1px solid {RT['divider_soft']}; border-radius:{RT['radius']};"
            f" color:{RT['text_body']}; padding:10px; font-size:{RT['font_size_small']}; }}"
        )
        self.tabs.addTab(self.board_panel, "Kartlar")
        self.tabs.addTab(self.stream_panel, "Akış")
        self.tabs.addTab(self.memory_view, "Bellek")
        center_splitter.addWidget(self.tabs)
        center_splitter.setSizes([420, 380])
        center_layout.addWidget(center_splitter)
        self.splitter.addWidget(center)

        # --- sağ: kadro
        self.roster_panel = RosterPanel(
            parent=self,
            registry=self.agent_registry,
            board=self.board,
            office_registry=self.office_registry,
            bridge=self.bridge,
            office="",
        )
        self.splitter.addWidget(self.roster_panel)
        # Kadro sütunu 320 px'te ofis kipindeki 3x2 ikon ızgarasını kırpıyordu
        # (üçüncü düğme yarım kalıyordu). Panelin alt sınırı ızgaraya göre
        # verilir ve başlangıç payı ona göre dağıtılır.
        self.roster_panel.setMinimumWidth(ROSTER_MIN_WIDTH)
        self.splitter.setSizes([250, 770, ROSTER_MIN_WIDTH])
        root.addWidget(self.splitter, 1)

        signal = getattr(bus, "offices_updated", None)
        if signal is not None:
            signal.connect(self._on_offices_updated)

        # İlk ofis seçimi paneller kurulmadan yayılmış olabilir; şimdi uygula.
        self.set_office(self.offices_panel.current_office)

    # ------------------------------------------------------------ ofis

    @Slot(str)
    def _on_office_selected(self, name: str) -> None:
        self.set_office(name)

    @Slot(str)
    def _on_offices_updated(self, _name: str = "") -> None:
        self.refresh_memory()

    def set_office(self, name: str) -> None:
        """Seçili ofisi bütün panellere uygular."""
        self.current_office = name or ""
        office = self.offices_panel.get_office(self.current_office)
        self.scene.set_office(office)
        self.board_panel.set_office(self.current_office)
        self.roster_panel.set_office(self.current_office)
        self.stream_panel.set_office(self.current_office)
        self.refresh_memory()
        title = self.current_office or "ofis seçilmedi"
        self.header_label.setText(
            f"<b style='color:{RT['accent']}; font-size:15px;'>🏢 ENTROPY AGENT DESK</b>"
            f" <span style='color:{RT['text_dim']}; font-size:12px;'>· {title}</span>"
        )
        self.setWindowTitle(f"{WINDOW_TITLE} — {title}")

    def refresh_memory(self) -> None:
        text = load_office_memory(self.current_office)
        if not text:
            self.memory_view.setHtml(
                f"<div style='color:{RT['text_dim']};'>Bu ofis için MEMORY.md henüz yok. "
                "Ofis bir kart tamamladığında bellek yazılır.</div>"
            )
            return
        try:
            from entropy.ui.widgets.markdown_renderer import render_markdown_to_html

            self.memory_view.setHtml(render_markdown_to_html(text))
        except Exception:
            self.memory_view.setPlainText(text)

    @Slot(str)
    def _on_agent_clicked(self, agent: str) -> None:
        """Sprite tıklaması: Akış sekmesine geç ve paneli o ajana odakla."""
        self.stream_panel.focus_agent(agent)
        self.tabs.setCurrentIndex(TAB_STREAM)

    # ------------------------------------------------------------ geometri

    def geometry_payload(self) -> dict:
        """Kaydedilecek konum/boyut/ekran sözlüğü."""
        rect = self.normalGeometry() if self.isMaximized() else self.geometry()
        screen = self.screen() or QGuiApplication.primaryScreen()
        return {
            "x": rect.x(),
            "y": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
            "screen": screen.name() if screen is not None else "",
            "maximized": bool(self.isMaximized()),
        }

    def save_geometry(self) -> dict:
        payload = self.geometry_payload()
        config.desk_geometry = payload
        try:
            config.save_settings()
        except Exception:
            pass
        return payload

    def restore_geometry(self, payload: Optional[dict] = None) -> bool:
        """
        Kayıtlı geometriyi uygular.

        Kayıtlı ekran artık bağlı değilse (dizüstü dock'tan çıkarılmış) pencere
        görünmez bir koordinatta açılırdı; o durumda birincil ekrana ortalanır.
        Boyut da ekranın kullanılabilir alanıyla sınırlanır.
        """
        data = payload if payload is not None else (config.desk_geometry or {})
        if not isinstance(data, dict) or not data:
            return False
        try:
            x = int(data.get("x", 0))
            y = int(data.get("y", 0))
            width = int(data.get("width", DEFAULT_SIZE[0]))
            height = int(data.get("height", DEFAULT_SIZE[1]))
        except (TypeError, ValueError):
            return False

        screens = QGuiApplication.screens()
        wanted = str(data.get("screen", ""))
        target = None
        for screen in screens:
            if screen.name() == wanted:
                target = screen
                break
        if target is None:
            target = QGuiApplication.primaryScreen()
        if target is None:
            self.setGeometry(x, y, max(width, 640), max(height, 480))
            return True

        available: QRect = target.availableGeometry()
        width = max(640, min(width, available.width()))
        height = max(480, min(height, available.height()))
        if str(data.get("screen", "")) != target.name() or not available.contains(x, y):
            # Kayıtlı ekran yok ya da konum bu ekranın dışında: ortala.
            x = available.x() + (available.width() - width) // 2
            y = available.y() + (available.height() - height) // 2
        self.setGeometry(x, y, width, height)
        if data.get("maximized"):
            self.showMaximized()
        return True

    def moveEvent(self, event):  # noqa: N802
        super().moveEvent(event)

    def closeEvent(self, event):  # noqa: N802
        self.save_geometry()
        global _OPEN_WINDOW
        if _OPEN_WINDOW is self:
            _OPEN_WINDOW = None
        super().closeEvent(event)


# --------------------------------------------------------------- tek örnek

_OPEN_WINDOW: Optional[AgentDeskWindow] = None


def existing_desk_window() -> Optional[AgentDeskWindow]:
    return _OPEN_WINDOW


def open_desk_window(parent=None, **kwargs) -> AgentDeskWindow:
    """
    Agent Desk penceresini açar. Zaten açıksa yenisini kurmaz, olanı öne getirir
    (iki pencere aynı ofisi ayrı ayrı düzenlerse hangisinin doğru olduğu
    belirsizleşirdi).
    """
    global _OPEN_WINDOW
    window = _OPEN_WINDOW
    if window is not None:
        try:
            window.showNormal()
            window.raise_()
            window.activateWindow()
            return window
        except RuntimeError:
            # Alttaki C++ nesnesi silinmiş (pencere kapatılmış): yeniden kur.
            _OPEN_WINDOW = None
    window = AgentDeskWindow(parent=parent, **kwargs)
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    _OPEN_WINDOW = window
    window.show()
    return window


def reset_desk_window() -> None:
    """Testler arasında tek örnek durumunu temizler."""
    global _OPEN_WINDOW
    _OPEN_WINDOW = None
