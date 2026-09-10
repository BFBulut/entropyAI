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
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.desk.board_panel import BoardPanel
from entropy.desk.offices_panel import (
    OfficesPanel,
    load_agent_registry,
    load_office_registry,
)
from entropy.desk.roster_panel import RosterPanel
from entropy.desk.scene import OfficeScene
from entropy.desk.memory_panel import OfficeMemoryPanel
from entropy.desk.projects_panel import ProjectsPanel
from entropy.desk.stream_panel import StreamPanel
from entropy.desk.terminals_panel import TerminalsPanel
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT

WINDOW_TITLE = "Entropy Agent Desk"
DEFAULT_SIZE = (1400, 880)
# Faz 7 pencere profili:
#   tek monitör  -> ekranın SAĞ yarısı (%50 genişlik, %90 yükseklik); Zen sola
#                   sığsın diye. Faz 6'daki %88 tek ekranda Zen'in üstünü
#                   kapatıyordu.
#   ikinci ekran -> orada kullanılabilir alanın %88'i, ortalanmış.
DESK_SCREEN_RATIO = 0.5          # tek monitörde genişlik oranı
DESK_HEIGHT_RATIO = 0.9          # tek monitörde yükseklik oranı
DESK_SECONDARY_RATIO = 0.88      # ikinci monitörde kaplama oranı
# Faz 12-D.1: bildirilen asgari artık GERÇEK asgariye yakın (ölçülen
# `minimumSizeHint` 678x405); eskiden 860x540 bildiriliyor ama düzen
# 1.205x620 dayatıyordu.
DESK_MIN_SIZE = (760, 500)

# Kadro sütununun en küçük okunur genişliği: ajan kartındaki 3x2 ikon
# düğme ızgarası artı kimlik metni bu genişlik altında kırpılıyordu.
# Faz 12-D.1: 380 -> 280. Panel artık kaydırma kabuğunun içinde; ızgara
# kırpılmaz, dar sütunda kaydırılır. Toplam asgari 180 + 200 + 280 = 660.
ROSTER_MIN_WIDTH = 280


def scroll_host(widget: QWidget, min_width: int = 0, min_height: int = 0) -> QScrollArea:
    """Paneli, pencereye sert asgari dayatmayan kaydırma kabuğuna sarar.

    Faz 12-D.1: Desk'in bildirilen asgari boyutu (860x540) gerçek değildi;
    sayfaların örtük `minimumSizeHint`i (Projeler 852, Terminaller 507,
    Bellek 576 px) `QTabWidget.setMinimumWidth` ile EZİLEMİYOR ve gerçek
    asgari 1.205x620 px'e çıkıyordu. Kaydırma kabuğunun asgarisi çocuğundan
    bağımsızdır: içerik kırpılmaz, kaydırılır.
    """
    host = QScrollArea()
    host.setWidgetResizable(True)
    host.setFrameShape(QFrame.Shape.NoFrame)
    host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    host.setWidget(widget)
    if min_width:
        host.setMinimumWidth(min_width)
    if min_height:
        host.setMinimumHeight(min_height)
    return host

TAB_CARDS = 0
# Faz 10-B: eski "Akış" sekmesi "Terminaller" oldu. Kart özeti (StreamPanel)
# sekmenin üst bölmesinde durur, altında ajan başına terminal bölmeleri.
# `TAB_STREAM` adı geriye uyum için korunur; `TAB_TERMINALS` yeni adıdır.
TAB_STREAM = 1
TAB_TERMINALS = 1
TAB_PROJECTS = 2
TAB_MEMORY = 3


def office_spend(office: str) -> Optional[dict]:
    """
    Ofis harcama panosu (`office_status`); sözleşme yoksa None → rozet gizlenir.

    Tek üretici kuralı: `/desk` ile aynı veri okunur. Faz 7'de sözleşme
    `agents.harness` altında aranır, orada yoksa `agents.mailbox`'a düşülür
    (uygulama oraya taşındı); ikisi de yoksa rozet hiç gösterilmez — uydurma
    bir harcama sayısı göstermek yanlış güven verirdi.
    """
    if not office:
        return None
    getter = None
    for module_path in ("entropy.agents.harness", "entropy.agents.mailbox"):
        try:
            import importlib

            getter = getattr(importlib.import_module(module_path), "office_status", None)
        except Exception:
            getter = None
        if getter is not None:
            break
    if getter is None:
        return None
    try:
        return dict(getter(office) or {})
    except Exception:
        return None


def _worktrees_fn(name: str) -> Optional[Any]:
    """
    `entropy.agents.worktrees.<name>` guard'lı okuma.

    `importlib.import_module` kullanılır (paket özniteliği değil): sözleşme
    modülü henüz yoksa ya da testte yerine konmuşsa doğru nesne bulunur.
    """
    try:
        import importlib

        fn = getattr(importlib.import_module("entropy.agents.worktrees"), name, None)
    except Exception:
        return None
    return fn if callable(fn) else None


def desk_target_screen() -> Optional[Any]:
    """Desk'in açılacağı ekran: ikinci monitör varsa o, yoksa birincil."""
    screens = list(QGuiApplication.screens())
    primary = QGuiApplication.primaryScreen()
    for screen in screens:
        if screen is not primary:
            return screen
    return primary


def desk_default_geometry(screen: Any = None) -> QRect:
    """Faz 7 pencere profili: ikinci ekranda %88, tek ekranda sağ yarı."""
    from entropy.ui.window_sizing import available_geometry, fitted_geometry, half_screen_geometry

    target = screen if screen is not None else desk_target_screen()
    area = available_geometry(target)
    primary = QGuiApplication.primaryScreen()
    if target is not None and primary is not None and target is not primary:
        return fitted_geometry(area, ratio=DESK_SECONDARY_RATIO, min_size=DESK_MIN_SIZE)
    return half_screen_geometry(
        area,
        width_ratio=DESK_SCREEN_RATIO,
        height_ratio=DESK_HEIGHT_RATIO,
        side="right",
        min_size=DESK_MIN_SIZE,
    )


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

        from entropy.core import paths as _paths

        vault = Path(config.obsidian_vault_path)
        # Faz 10-B: Desk verisi kasa kökündeki `Desk/Offices` altında.
        path = _paths.desk_offices_dir(vault) / office_name / "MEMORY.md"
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
        # Faz 6: sabit 1400x880 kucuk ekranlarda tasiyordu. Pencere kullanilabilir
        # alanin en cok %88'ini kaplar ve ortalanir; kayitli geometri varsa
        # _restore_geometry() bunun uzerine yazar (o da alana kirpilir).
        self.resize(*DEFAULT_SIZE)
        target = desk_target_screen()
        geom = desk_default_geometry(target)
        self.setMinimumSize(min(DESK_MIN_SIZE[0], geom.width()),
                            min(DESK_MIN_SIZE[1], geom.height()))
        if target is not None:
            try:
                self.windowHandle() and self.windowHandle().setScreen(target)
            except Exception:
                pass
        self.setGeometry(geom)

        self.office_registry = office_registry if office_registry is not None else load_office_registry()
        # Kadro paneli Desk'in KENDİ ajanlarını gösterir; Entropy'nin
        # `Entropy/Agents` kadrosu Desk'e girmez (Faz 6, kural 1).
        self.agent_registry = (
            agent_registry if agent_registry is not None else load_agent_registry()
        )
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

        self.header_label = QLabel("")
        self.header_label.setProperty("role", "label")
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)
        header.addWidget(self.header_label)
        header.addStretch()

        # Faz 7: harcama rozeti (veri yoksa gizli) + iki sağlayıcı kimlik rozeti.
        self.spend_label = QLabel("")
        self.spend_label.setProperty("role", "label")
        self.spend_label.setVisible(False)
        header.addWidget(self.spend_label)

        # Faz 10-D: yetim worktree uyarısı. Sayı `office_status`ün
        # `orphan_worktrees` alanından, o yoksa `worktrees.list_orphans`tan
        # gelir; sıfırsa düğme hiç görünmez (boş uyarı güven kaybettirir).
        self.orphan_btn = QPushButton("")
        self.orphan_btn.setFixedHeight(24)
        self.orphan_btn.setToolTip(
            "Kapatılamamış worktree'leri yeniden temizlemeyi dener "
            "(worktrees.retry_orphans)."
        )
        self.orphan_btn.clicked.connect(self.clean_orphans)
        self.orphan_btn.setVisible(False)
        header.addWidget(self.orphan_btn)
        self.orphan_status = QLabel("")
        self.orphan_status.setProperty("role", "label")
        self.orphan_status.setVisible(False)
        header.addWidget(self.orphan_status)
        try:
            from entropy.ui.widgets.provider_badge import ProviderStatusBadge

            self.provider_badge = ProviderStatusBadge(parent=self)
            header.addWidget(self.provider_badge)
        except Exception:
            self.provider_badge = None
        root.addLayout(header)

        # --- Faz 9 / B-9.3: "Ofise talimat" kutusu ------------------------
        # Entropy'den ofise yön vermenin arayüzdeki tek yüzeyi. Talimat
        # `instruct_office` ile ofisin posta kutusuna düşer; orkestratör bir
        # sonraki planından önce okur. Model ÇAĞRILMAZ, kota harcanmaz.
        instruct = QHBoxLayout()
        instruct.setContentsMargins(4, 0, 4, 0)
        instruct.setSpacing(6)
        self.instruct_input = QLineEdit()
        self.instruct_input.setPlaceholderText(
            "Ofise talimat… (orkestratörün bir sonraki planına girer)"
        )
        self.instruct_input.setClearButtonEnabled(True)
        self.instruct_input.returnPressed.connect(self.send_instruction)
        instruct.addWidget(self.instruct_input, 1)
        self.instruct_btn = QPushButton("Talimat gönder")
        self.instruct_btn.setAccessibleName("Talimat gönder")
        self.instruct_btn.setFixedHeight(26)
        self.instruct_btn.setToolTip(
            "Talimatı seçili ofisin posta kutusuna bırakır; koşu başlatmaz."
        )
        self.instruct_btn.clicked.connect(self.send_instruction)
        instruct.addWidget(self.instruct_btn)
        self.instruct_badge = QLabel("")
        self.instruct_badge.setProperty("role", "label")
        self.instruct_badge.setToolTip("Ofisin okunmamış mesaj sayısı")
        instruct.addWidget(self.instruct_badge)
        self.instruct_status = QLabel("")
        self.instruct_status.setProperty("role", "label")
        self.instruct_status.setWordWrap(False)
        instruct.addWidget(self.instruct_status)
        root.addLayout(instruct)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- sol: ofisler
        self.offices_panel = OfficesPanel(
            parent=self, registry=self.office_registry, agent_registry=self.agent_registry
        )
        self.offices_panel.office_selected.connect(self._on_office_selected)
        self.offices_host = scroll_host(self.offices_panel, min_width=180)
        self.splitter.addWidget(self.offices_host)

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
        self.board_panel = BoardPanel(parent=self, board=self.board, office="", bridge=self.bridge)
        self.stream_panel = StreamPanel(parent=self, board=self.board, office="")
        self.projects_panel = ProjectsPanel(parent=self, office="", board=self.board)
        self.projects_panel.project_filter_changed.connect(self._on_project_filter)
        self.memory_panel = OfficeMemoryPanel(parent=self, office="")
        # Geri uyum: eski çağrılar (ve testler) `memory_view` ile MEMORY.md
        # metnine bakıyor; panelin alt bölmesi aynı nesnedir.
        self.memory_view = self.memory_panel.memory_view
        self.terminals_panel = TerminalsPanel(
            parent=self, office="", bridge=self.bridge, board=self.board
        )
        # Faz 10-D: takip turu bitince kartın Değişiklikler/Makbuz bölmeleri
        # tazelenir (alıcı QObject slotu, lambda değil).
        self.terminals_panel.card_refresh_requested.connect(
            self.board_panel.refresh_card_detail
        )
        terminals_tab = QWidget()
        terminals_layout = QVBoxLayout(terminals_tab)
        terminals_layout.setContentsMargins(0, 0, 0, 0)
        terminals_layout.setSpacing(0)
        terminals_split = QSplitter(Qt.Orientation.Vertical)
        terminals_split.addWidget(self.stream_panel)
        terminals_split.addWidget(self.terminals_panel)
        terminals_split.setSizes([180, 420])
        terminals_layout.addWidget(terminals_split)
        self.terminals_tab = terminals_tab

        # Sayfalar kaydırma kabuğunda: sert asgari yok, içerik kırpılmaz.
        self.tabs.addTab(scroll_host(self.board_panel), "Kartlar")
        self.tabs.addTab(scroll_host(terminals_tab), "Terminaller")
        self.tabs.addTab(scroll_host(self.projects_panel), "Projeler")
        self.tabs.addTab(scroll_host(self.memory_panel), "Bellek")
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
        self.roster_host = scroll_host(self.roster_panel, min_width=ROSTER_MIN_WIDTH)
        self.splitter.addWidget(self.roster_host)
        # Kadro sütunu 320 px'te ofis kipindeki 3x2 ikon ızgarasını kırpıyordu
        # (üçüncü düğme yarım kalıyordu). Panelin alt sınırı ızgaraya göre
        # verilir ve başlangıç payı ona göre dağıtılır.
        self.roster_panel.setMinimumWidth(0)
        # Faz 6: panellerin ortuk asgari genisligi toplamda ~2200 px istiyordu;
        # 1366 px'lik ekranda sag sutun kirpiliyordu. Acik ve kucuk minimumlarla
        # splitter oranlari serbest kalir, panel icerikleri kendi kaydirma
        # alanlarinda daralir.
        self.offices_panel.setMinimumWidth(0)
        # Faz 7: yarım ekran Desk (≈900 px) için AÇIK asgari genişlikler.
        # Qt düzeni açık minimumu örtük `minimumSizeHint`in önüne alır; aksi
        # halde akış paneli 535 px, projeler 880 px isteyip orta sütunu
        # şişiriyordu. Toplam: 180 + 240 + 380 = 800 px.
        # Faz 9 / B-9.7: AÇIK asgari YÜKSEKLİKLER de verilir. Panellerin örtük
        # `minimumSizeHint`i (bellek 278, projeler 114 …) sekme yığınını 306 px
        # istemeye zorluyor, sahne ile birlikte pencerenin mantıksal asgari
        # yüksekliği %200 ölçekte 712 px'e çıkıyordu. Panel içerikleri kendi
        # kaydırma alanlarında daralır.
        # Faz 12-D.1: sert panel asgarileri kaldırıldı; sayfalar kaydırma
        # kabuğunda daralır. Yalnızca sütun düzeyinde küçük asgariler kalır.
        for panel in (self.board_panel, self.stream_panel, self.terminals_panel,
                      self.projects_panel, self.memory_panel):
            panel.setMinimumWidth(0)
            panel.setMinimumHeight(0)
        center.setMinimumWidth(200)
        center_splitter.setChildrenCollapsible(True)
        self.tabs.setMinimumWidth(200)
        self.tabs.setMinimumHeight(120)
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
        self.projects_panel.refresh()
        self.refresh_spend()

    def set_office(self, name: str) -> None:
        """Seçili ofisi bütün panellere uygular."""
        self.current_office = name or ""
        office = self.offices_panel.get_office(self.current_office)
        self.scene.set_office(office)
        self.board_panel.set_office(self.current_office)
        self.roster_panel.set_office(self.current_office)
        self.stream_panel.set_office(self.current_office)
        self.terminals_panel.set_office(self.current_office)
        self.projects_panel.set_office(self.current_office)
        self.refresh_memory()
        self.refresh_spend()
        self.instruct_status.setText("")
        has_office = bool(self.current_office)
        self.instruct_input.setEnabled(has_office)
        self.instruct_btn.setEnabled(has_office)
        self.refresh_unread()
        title = self.current_office or "ofis seçilmedi"
        self.header_label.setText(
            f"<b style='color:{RT['accent']}; font-size:15px;'>ENTROPY AGENT DESK</b>"
            f" <span style='color:{RT['text_dim']}; font-size:12px;'>· {title}</span>"
        )
        # Faz 7: başlık her yerde aynı biçimde ("· <ofis>"), pencere adı ile
        # üst şerit birbirini tutsun.
        self.setWindowTitle(f"{WINDOW_TITLE} · {title}")

    def refresh_memory(self) -> None:
        """Bellek sekmesi: mini graf + MEMORY.md metni birlikte tazelenir."""
        self.memory_panel.set_office(self.current_office)

    def refresh_spend(self) -> None:
        """Ofis harcama rozeti; `office_status` yoksa rozet gizlenir."""
        info = office_spend(self.current_office)
        if not info:
            self.spend_label.setVisible(False)
            self.spend_label.setText("")
            # Harcama panosu yoksa da yetim worktree uyarısı gösterilebilir.
            self.refresh_orphans({})
            return
        spent = int(info.get("spent_tokens", info.get("tokens", 0)) or 0)
        budget = int(info.get("budget_tokens", info.get("budget", 0)) or 0)
        running = len(info.get("running", []) or [])
        text = f"{spent:,} token".replace(",", ".")
        if budget:
            text += f" / {budget:,}".replace(",", ".")
        if running:
            text += f" · {running} çalışan"
        self.spend_label.setText(
            f"<span style='color:{RT['text_dim']}; font-size:11px;'>{text}</span>"
        )
        self.spend_label.setToolTip(self.spend_tooltip(info))
        self.spend_label.setVisible(True)
        self.refresh_orphans(info)

    # ------------------------------------------------- yetim worktree'ler

    def orphan_count(self, info: Optional[dict] = None) -> int:
        """
        Yetim worktree sayısı.

        Öncelik `office_status`ün `orphan_worktrees` alanıdır (tek üretici);
        alan henüz yoksa `worktrees.list_orphans(vault)` guard'lı okunur.
        İkisi de yoksa 0 — uydurma sayı gösterilmez.
        """
        data = info if info is not None else office_spend(self.current_office)
        value = (data or {}).get("orphan_worktrees")
        if isinstance(value, (list, tuple, set)):
            return len(value)
        if isinstance(value, int):
            return max(0, value)
        fn = _worktrees_fn("list_orphans")
        if fn is None:
            return 0
        try:
            return len(list(fn(config.obsidian_vault_path) or []))
        except Exception:
            return 0

    def refresh_orphans(self, info: Optional[dict] = None,
                        keep_status: bool = False) -> int:
        """
        Düğmeyi sayıya göre gösterir/gizler.

        `keep_status`: temizleme sonrası çağrıda bilgi satırı KORUNUR; aksi
        halde sonucu yazan satır aynı karede silinirdi.
        """
        count = self.orphan_count(info)
        if count > 0:
            self.orphan_btn.setText(f"{count} yetim çalışma ağacı · temizle")
        self.orphan_btn.setVisible(count > 0)
        if not count and not keep_status:
            self.orphan_status.setVisible(False)
            self.orphan_status.setText("")
        return count

    @Slot()
    def clean_orphans(self) -> dict:
        """`worktrees.retry_orphans(vault)` çağırır ve sonucu şeride yazar."""
        fn = _worktrees_fn("retry_orphans")
        if fn is None:
            self._set_orphan_status("Temizleme sözleşmesi bulunamadı.", ok=False)
            return {}
        try:
            result = dict(fn(config.obsidian_vault_path) or {})
        except Exception as exc:
            self._set_orphan_status(f"Temizlenemedi: {exc}", ok=False)
            return {}
        cleaned = int(result.get("cleaned", result.get("removed", 0)) or 0)
        left = int(result.get("remaining", result.get("failed", 0)) or 0)
        text = f"{cleaned} çalışma ağacı temizlendi"
        if left:
            text += f" · {left} kaldı"
        self._set_orphan_status(text, ok=not left)
        self.refresh_orphans(keep_status=True)
        return result

    def _set_orphan_status(self, text: str, ok: bool = True) -> None:
        color = RT["accent_alt"] if ok else RT["accent_warn"]
        self.orphan_status.setText(
            f"<span style='color:{color}; font-size:11px;'>{text}</span>"
        )
        self.orphan_status.setVisible(True)

    @staticmethod
    def spend_tooltip(info: dict) -> str:
        """
        Rozetin ipucu: koşan kart başına `harcanan/bütçe` satırı.

        Sayılar `office_status` çıktısından BİREBİR alınır; burada yeniden
        hesaplanmaz (iki yerde ayrı hesap panoların birbirini tutmamasına yol
        açıyordu).
        """
        running = list((info or {}).get("running", []) or [])
        lines = []
        for card in running:
            if not isinstance(card, dict):
                continue
            title = str(card.get("title") or card.get("id") or "—")
            tokens = int(card.get("tokens", 0) or 0)
            budget = int(card.get("budget", 0) or 0)
            amount = f"{tokens:,}".replace(",", ".")
            if budget:
                amount += " / " + f"{budget:,}".replace(",", ".")
            phase = str(card.get("phase") or "")
            line = f"{title}: {amount} token"
            if phase:
                line += f" · {phase}"
            lines.append(line)
        if not lines:
            spent = int((info or {}).get("spent_tokens",
                                         (info or {}).get("tokens", 0)) or 0)
            return (
                "Koşan kart yok. Ofis toplamı: "
                + f"{spent:,}".replace(",", ".")
                + " token"
            )
        return "Koşan kartlar (harcanan / bütçe):\n" + "\n".join(lines)

    # -------------------------------------------------------- talimat

    def unread_count(self) -> int:
        """Seçili ofisin okunmamış mesaj sayısı (sözleşme yoksa 0)."""
        if not self.current_office:
            return 0
        try:
            from entropy.agents.mailbox import office_mailbox

            return int(office_mailbox(self.current_office).unread_count() or 0)
        except Exception:
            return 0

    def refresh_unread(self) -> None:
        count = self.unread_count()
        if not count:
            self.instruct_badge.setText("")
            self.instruct_badge.setVisible(False)
            return
        self.instruct_badge.setText(
            f"<span style='color:{RT['accent_warn']}; font-size:11px; font-weight:600;'>"
            f"{count} okunmamış</span>"
        )
        self.instruct_badge.setVisible(True)

    @Slot()
    def send_instruction(self) -> bool:
        """
        Kutudaki metni seçili ofise talimat olarak yollar.

        Boş metin sessizce reddedilir (mailbox `ValueError` atıyor; kullanıcıya
        istisna değil, kısa bir uyarı gösterilir). Başarıda kutu temizlenir ve
        "orkestratörün bir sonraki planına girecek" bilgisi yazılır.
        """
        text = self.instruct_input.text().strip()
        if not self.current_office:
            self._set_instruct_status("Önce bir ofis seçin.", ok=False)
            return False
        if not text:
            self._set_instruct_status("Talimat boş olamaz.", ok=False)
            return False
        try:
            from entropy.agents.mailbox import instruct_office

            instruct_office(self.current_office, text)
        except Exception as exc:
            self._set_instruct_status(f"Gönderilemedi: {exc}", ok=False)
            return False
        self.instruct_input.clear()
        self._set_instruct_status(
            "Talimat kutuya bırakıldı; orkestratörün bir sonraki planına girecek.",
            ok=True,
        )
        self.refresh_unread()
        return True

    def _set_instruct_status(self, text: str, ok: bool = True) -> None:
        color = RT["accent_alt"] if ok else RT["accent_warn"]
        self.instruct_status.setText(
            f"<span style='color:{color}; font-size:11px;'>{text}</span>"
        )

    @Slot(str)
    def _on_project_filter(self, project: str) -> None:
        """Projeler sekmesindeki süzgeci Kartlar sekmesine uygular."""
        widget = getattr(self.board_panel, "board_widget", None)
        setter = getattr(widget, "set_project_filter", None)
        if setter is not None:
            setter(project)
        self.tabs.setCurrentIndex(TAB_CARDS)

    @Slot(str)
    def _on_agent_clicked(self, agent: str) -> None:
        """Sprite tıklaması: Akış sekmesine geç ve paneli o ajana odakla."""
        self.stream_panel.focus_agent(agent)
        # Faz 10-B: sprite tıklaması ajanın GERÇEK terminal bölmesini öne alır.
        self.terminals_panel.focus_agent(agent)
        self.tabs.setCurrentIndex(TAB_TERMINALS)

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
        # Faz 7: kullanicinin kaydettigi GECERLI geometri korunur; yalnizca
        # ekranin kullanilabilir alanini asan olculer kirpilir. (Faz 6'daki
        # %88 tavani, kullanici pencereyi buyuttuyse her acilista kucultuyordu.)
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
