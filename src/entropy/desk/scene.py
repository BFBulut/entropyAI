"""
Piksel ofis sahnesi: ajanlar gerçek piksel karakterler olarak bir tile ofiste.

Faz 6'da yordamsal QPainter masaları bırakıldı; sahne artık `desk/engine/`
motorunu kullanıyor: `default-layout-1.json` düzeni, 16 px ızgara, duvar
bitmask otomatik döşemesi, mobilya manifestleri ve 16x32 karakter sayfaları
(pixel-agents / JIK-A-4 varlıkları; bkz. THIRD_PARTY.md).

Korunan sözleşme (window.py ve mevcut testler buna bağlı):
- `OfficeScene` sınıf adı, `set_office`, `set_agents`, `agent_clicked` sinyali.
- `slots` / `slot_for` / `states` / `set_state` / `agent_cards` / `relayout` /
  `_view_transform` / `_logical_size` ve bus sinyal alıcıları.

Değişen: `DeskSlot.x/y` artık mantıksal PİKSEL (hücre * 16) — masa dikdörtgeni
değil, karakterin durduğu hücre. Rect'ler hücre başına ayrı olduğu için hâlâ
çakışmaz.

Kare hızı: etkin 30 fps, boşta 10 fps, gizliyken zamanlayıcı durur.
LLM çağrısı yoktur; tüm animasyon istemci tarafıdır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from entropy.core.event_bus import bus
from entropy.desk.engine.assets import TILE_SIZE, library
from entropy.desk.engine.furniture import FurnitureLibrary
from entropy.desk.engine.layout import TILE_EMPTY, Layout, Seat, load_layout
from entropy.desk.engine.pathing import find_path, walkable_grid
from entropy.desk.engine.sprites import (
    ANIM_IDLE,
    ANIM_READ,
    ANIM_TYPE,
    ANIM_WALK,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    CharacterLibrary,
)
from entropy.desk.engine.tilemap import TileMap, carpet_case, wall_bitmask

# --------------------------------------------------------------------- durumlar
STATE_IDLE = "idle"
STATE_THINKING = "thinking"
STATE_WORKING = "working"
STATE_ERROR = "error"
STATE_WAITING = "waiting"
STATE_READING = "reading"

STATES = (
    STATE_IDLE, STATE_THINKING, STATE_WORKING, STATE_ERROR, STATE_WAITING, STATE_READING,
)

STATE_LABELS = {
    STATE_IDLE: "boşta",
    STATE_THINKING: "düşünüyor",
    STATE_WORKING: "çalışıyor",
    STATE_ERROR: "hata",
    STATE_WAITING: "bekliyor",
    STATE_READING: "okuyor",
}

STATE_COLORS = {
    STATE_IDLE: QColor(93, 116, 140),
    STATE_THINKING: QColor(255, 194, 77),
    STATE_WORKING: QColor(61, 232, 168),
    STATE_ERROR: QColor(239, 68, 68),
    STATE_WAITING: QColor(56, 217, 255),
    STATE_READING: QColor(147, 197, 253),
}

# Durum -> karakter animasyonu. Düşünme/bekleme/hata statik duruş + balon.
STATE_ANIMATION = {
    STATE_IDLE: ANIM_IDLE,
    STATE_THINKING: ANIM_IDLE,
    STATE_WORKING: ANIM_TYPE,
    STATE_READING: ANIM_READ,
    STATE_WAITING: ANIM_IDLE,
    STATE_ERROR: ANIM_IDLE,
}

# Durum -> baş üstü balon metni ("" = balon yok).
STATE_BUBBLE = {
    STATE_THINKING: "…",
    STATE_WAITING: "⏳",
    STATE_ERROR: "!",
}

STAGE_TO_STATE = {
    "planning": STATE_THINKING,
    "plan": STATE_THINKING,
    "planlama": STATE_THINKING,
    "running": STATE_WORKING,
    "executing": STATE_WORKING,
    "yurutme": STATE_WORKING,
    "reading": STATE_READING,
    "read": STATE_READING,
    "okuma": STATE_READING,
    "evaluating": STATE_THINKING,
    "evaluation": STATE_THINKING,
    "degerlendirme": STATE_THINKING,
    "queued": STATE_WAITING,
    "waiting": STATE_WAITING,
    "bekliyor": STATE_WAITING,
    "done": STATE_IDLE,
    "completed": STATE_IDLE,
    "bitti": STATE_IDLE,
    "failed": STATE_ERROR,
    "error": STATE_ERROR,
    "hata": STATE_ERROR,
}

# Araç adı bu köklerden birini içeriyorsa ajan "okuyor" sayılır.
READ_TOOL_HINTS = ("read", "oku", "grep", "search", "ara", "glob", "fetch")

ROLE_ORCHESTRATOR = "orchestrator"
ROLE_EVALUATOR = "evaluator"
ROLE_WORKER = "worker"

ACTIVE_INTERVAL_MS = 33
IDLE_INTERVAL_MS = 100

# Animasyon hızları (pixel-agents sabitleriyle aynı his).
WALK_SPEED_PX_PER_SEC = 48.0
WALK_FRAME_MS = 150
WORK_FRAME_MS = 300

MIN_ZOOM = 1
MAX_ZOOM = 3

# Karakter tıklama kutusu (mantıksal piksel).
HIT_HALF_W = 8
HIT_H = 24


@dataclass
class DeskSlot:
    """Sahnedeki tek ajan: karakter, masa yeri, durum, konum."""

    agent: str
    role: str = ROLE_WORKER
    state: str = STATE_IDLE
    note: str = ""
    seat: Optional[Seat] = None
    char_index: int = 0
    # Mantıksal piksel konum (hücre * TILE_SIZE), karakterin sol-üst ayağı.
    x: int = 0
    y: int = 0
    facing: str = DIR_DOWN
    path: List[Tuple[int, int]] = field(default_factory=list)
    path_step: int = 0
    walking: bool = False
    idle_ms: int = 0

    @property
    def rect(self) -> QRect:
        """Mantıksal çarpışma/tıklama dikdörtgeni."""
        return QRect(self.x, self.y - HIT_H + TILE_SIZE, TILE_SIZE, HIT_H)

    @property
    def cell(self) -> Tuple[int, int]:
        return (self.x // TILE_SIZE, self.y // TILE_SIZE)


@dataclass
class SceneOffice:
    name: str = ""
    orchestrator: str = ""
    evaluator: str = ""
    members: List[str] = field(default_factory=list)


def _office_field(office, name, default=""):
    """OfficeSpec / sözlük / None fark etmeksizin alan okur."""
    if office is None:
        return default
    if isinstance(office, dict):
        value = office.get(name, default)
    else:
        value = getattr(office, name, default)
    return default if value is None else value


def state_for_tool(tool_name: str) -> str:
    """Araç adından durum: okuma araçları READ, diğerleri WORKING."""
    low = (tool_name or "").lower()
    return STATE_READING if any(h in low for h in READ_TOOL_HINTS) else STATE_WORKING


class OfficeScene(QWidget):
    """Piksel ofis: tile zemin/duvar, mobilya ve masalarında ajan karakterleri."""

    agent_clicked = Signal(str)   # karaktere tıklandı: ajan adı

    def __init__(self, parent: Optional[QWidget] = None, office=None):
        super().__init__(parent)
        # Faz 9 / B-9.7: eski asgari (520x330) %200 ölçekte Desk penceresinin
        # mantıksal asgari yüksekliğini 712 px'e çıkarıyordu (hedef ≤540).
        # Sahne `fit_to_view` ile küçülebiliyor (bkz. `_view_transform`), bu
        # yüzden asgari boyut "okunur en küçük ofis" değerine indirildi;
        # varsayılan pencere boyutu değişmedi.
        self.setMinimumSize(360, 200)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMouseTracking(True)

        self.office = SceneOffice()
        self.slots: List[DeskSlot] = []
        self.selected_agent: str = ""
        self.agent_cards: Dict[str, str] = {}

        self._pulse_frame = 0
        self._elapsed_ms = 0
        self._zoom = MIN_ZOOM
        self.fit_mode = True

        # Motor parçaları
        self.assets = library()
        self.tilemap = TileMap(self.assets)
        self.furniture = FurnitureLibrary(self.assets)
        self.characters = CharacterLibrary(self.assets)
        self.layout: Layout = Layout()
        self._walkable: List[List[bool]] = []
        self._logical_size = (TILE_SIZE, TILE_SIZE)
        # Görünüm penceresinin mantıksal sol-üst köşesi (boş kenarlar kırpılır).
        self._origin = (0, 0)
        self._floor_cache: Optional[QPixmap] = None
        self._lounge_cells: List[Tuple[int, int]] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._connect_bus()
        self._load_layout("")
        if office is not None:
            self.set_office(office)
        else:
            self._sync_timer()

    # ------------------------------------------------------------ sözleşme

    def _connect_bus(self) -> None:
        """
        Bus sinyalleri: alıcı QObject slotu (lambda değil), böylece işçi iş
        parçacığından yayılan sinyal kuyruklanır ve çizim ana iş parçacığında
        kalır.
        """
        for signal_name, handler in (
            ("office_progress", self._on_office_progress),
            ("task_triggered", self._on_task_triggered),
            ("task_completed", self._on_task_completed),
            ("agent_turn_started", self._on_turn_started),
            ("agent_turn_completed", self._on_turn_completed),
            ("offices_updated", self._on_offices_updated),
        ):
            signal = getattr(bus, signal_name, None)
            if signal is not None:
                try:
                    signal.connect(handler)
                except Exception:
                    pass

    def set_office(self, office) -> None:
        """Ofis tanımını (OfficeSpec ya da sözlük) sahneye uygular."""
        self.office = SceneOffice(
            name=str(_office_field(office, "name", "")),
            orchestrator=str(_office_field(office, "orchestrator", "")),
            evaluator=str(_office_field(office, "evaluator", "")),
            members=[str(m) for m in (_office_field(office, "members", []) or [])],
        )
        self._load_layout(self.office.name)
        self._rebuild_slots()

    def set_agents(self, agents, orchestrator: str = "", evaluator: str = "") -> None:
        """Ofis nesnesi olmadan doğrudan ajan listesi verir (panel/test yolu)."""
        self.office = SceneOffice(
            name=self.office.name,
            orchestrator=orchestrator or self.office.orchestrator,
            evaluator=evaluator or self.office.evaluator,
            members=[str(a) for a in (agents or [])],
        )
        self._rebuild_slots()

    # ------------------------------------------------------------ düzen

    def _load_layout(self, office: str) -> None:
        """Ofis düzenini yükler; hata halinde boş düzenle devam edilir."""
        try:
            self.layout = load_layout(office, self.furniture, self.assets)
        except Exception:
            self.layout = Layout()
        self._floor_cache = None
        occupied = self.layout.occupied_cells() if self.layout.cols else set()
        self._walkable = (
            walkable_grid(self.layout.tiles, occupied) if self.layout.cols else []
        )
        # Görünüm yalnızca dolu alanı kapsar: düzenin boş (255) kenarları
        # sahnede kocaman siyah bant bırakıyordu, ofis de gereksiz küçülüyordu.
        if self.layout.cols:
            min_c, min_r, max_c, max_r = self.layout.bounds()
            self._origin = (min_c * TILE_SIZE, (min_r - 1) * TILE_SIZE)
            self._logical_size = (
                (max_c - min_c + 1) * TILE_SIZE,
                (max_r - min_r + 2) * TILE_SIZE,
            )
        else:
            self._origin = (0, 0)
            self._logical_size = (TILE_SIZE, TILE_SIZE)

    def _rebuild_slots(self) -> None:
        """Ajanları masalara dağıtır; mevcut durum ve konumlar korunur."""
        previous = {s.agent: s for s in self.slots}
        slots: List[DeskSlot] = []
        seen = set()

        def add(agent: str, role: str) -> None:
            if not agent or agent in seen:
                return
            seen.add(agent)
            old = previous.get(agent)
            sheet_count = max(1, self.characters.count())
            from entropy.desk.engine.sprites import character_index_for

            slots.append(DeskSlot(
                agent=agent,
                role=role,
                state=old.state if old else STATE_IDLE,
                note=old.note if old else "",
                char_index=character_index_for(agent, sheet_count),
            ))

        add(self.office.orchestrator, ROLE_ORCHESTRATOR)
        for member in self.office.members:
            if member == self.office.evaluator:
                continue
            add(member, ROLE_WORKER)
        add(self.office.evaluator, ROLE_EVALUATOR)

        self.slots = slots
        self.relayout()
        self._sync_timer()
        self.update()

    def relayout(self) -> None:
        """
        Masa yerlerini dağıtır: ilk yer (ofis merkezine en yakın) orkestratöre,
        sonra üyeler, en sona değerlendirici.

        Motor `seats_for` çağrısı masa/sandalye mobilyalarından yer üretir;
        yetmezse boş zeminden tamamlar, böylece kalabalık ofiste kimse
        görünmez kalmaz.
        """
        if not self.slots:
            return
        seats = self.layout.seats_for(len(self.slots)) if self.layout.cols else []
        order = (
            [s for s in self.slots if s.role == ROLE_ORCHESTRATOR]
            + [s for s in self.slots if s.role == ROLE_WORKER]
            + [s for s in self.slots if s.role == ROLE_EVALUATOR]
        )
        for index, slot in enumerate(order):
            seat = seats[index] if index < len(seats) else None
            slot.seat = seat
            if seat is not None and not slot.walking:
                slot.x = seat.col * TILE_SIZE
                slot.y = seat.row * TILE_SIZE
                slot.facing = seat.facing
        self._lounge_cells = [
            s.cell for s in (self.layout.seats() if self.layout.cols else [])
            if s.source == "chair" and s.cell not in {
                (sl.seat.col, sl.seat.row) for sl in self.slots if sl.seat
            }
        ]

    def slot_for(self, agent: str) -> Optional[DeskSlot]:
        for slot in self.slots:
            if slot.agent == agent:
                return slot
        return None

    def states(self) -> Dict[str, str]:
        """Test ve panel için: ajan adı -> durum."""
        return {s.agent: s.state for s in self.slots}

    def seat_assignments(self) -> Dict[str, Tuple[int, int]]:
        """Ajan -> masa hücresi (test ve ipucu için)."""
        return {
            s.agent: (s.seat.col, s.seat.row)
            for s in self.slots if s.seat is not None
        }

    # ------------------------------------------------------------ görüntü

    def set_zoom(self, zoom: int) -> None:
        """Tamsayı zoom (1x/2x/3x); `fit_mode` kapanır."""
        self._zoom = max(MIN_ZOOM, min(MAX_ZOOM, int(zoom)))
        self.fit_mode = False
        self.tilemap.clear_scaled()
        self.update()

    def fit_to_view(self) -> None:
        """`fitInView` benzeri: düzeni pencereye sığdır."""
        self.fit_mode = True
        self.update()

    @property
    def zoom(self) -> int:
        return self._zoom

    def _view_transform(self) -> Tuple[float, float, float]:
        """Mantıksal -> pencere dönüşümü (ölçek, dx, dy)."""
        logical_w, logical_h = self._logical_size
        if logical_w <= 0 or logical_h <= 0:
            return 1.0, 0.0, 0.0
        if self.fit_mode:
            fit = min(self.width() / logical_w, self.height() / logical_h)
            # 1x üstünde tamsayıya yuvarla: piksel ızgarası bozulmasın.
            scale = float(min(MAX_ZOOM, int(fit))) if fit >= 1.0 else fit
            self._zoom = max(MIN_ZOOM, min(MAX_ZOOM, int(scale) if scale >= 1 else 1))
        else:
            scale = float(self._zoom)
        dx = (self.width() - logical_w * scale) / 2 - self._origin[0] * scale
        dy = (self.height() - logical_h * scale) / 2 - self._origin[1] * scale
        return scale, dx, dy

    def _to_logical(self, point) -> QPoint:
        scale, dx, dy = self._view_transform()
        if scale <= 0:
            return QPoint(point)
        return QPoint(int((point.x() - dx) / scale), int((point.y() - dy) / scale))

    def to_widget(self, point) -> QPoint:
        """`_to_logical`'in tersi: mantıksal noktayı pencere koordinatına taşır.

        Hit-test'i (slot.rect -> slot_at) dışarıdan sürebilmek için gerekli;
        testler ve ekran görüntüsü otomasyonu bunu kullanır.
        """
        scale, dx, dy = self._view_transform()
        if scale <= 0:
            return QPoint(point)
        return QPoint(int(point.x() * scale + dx), int(point.y() * scale + dy))

    def resizeEvent(self, event):  # noqa: N802 (Qt)
        self.relayout()
        super().resizeEvent(event)

    # ------------------------------------------------------------ durum

    def set_state(self, agent: str, state: str, note: str = "") -> bool:
        """Bir ajanın durumunu değiştirir; ajan sahnede yoksa False."""
        if state not in STATES:
            state = STATE_WORKING
        slot = self.slot_for(agent)
        if slot is None:
            return False
        slot.state = state
        slot.idle_ms = 0
        if note:
            slot.note = note
        if state in (STATE_WORKING, STATE_READING, STATE_THINKING):
            # Gelen görev: karakter masasına yürür (boşta kanepeye gitmiş olabilir).
            self.walk_to_seat(agent)
        self._sync_timer()
        self.update()
        return True

    # ------------------------------------------------------------ yürüme

    def walk_to_seat(self, agent: str) -> bool:
        """Ajanı masasına yürütür. Zaten masadaysa/yol yoksa False."""
        slot = self.slot_for(agent)
        if slot is None or slot.seat is None:
            return False
        return self._walk_to(slot, (slot.seat.col, slot.seat.row), slot.seat.facing)

    def _walk_to(self, slot: DeskSlot, target: Tuple[int, int],
                 facing: Optional[str] = None) -> bool:
        if not self._walkable or slot.cell == target:
            slot.walking = False
            slot.path = []
            if facing:
                slot.facing = facing
            return False
        path = find_path(self._walkable, slot.cell, target)
        if len(path) < 2:
            return False
        slot.path = path
        slot.path_step = 0
        slot.walking = True
        return True

    def _advance_walk(self, slot: DeskSlot, dt_ms: int) -> None:
        """Yolu adım adım ilerletir; hedefe varınca oturuş yönüne döner."""
        if not slot.walking or len(slot.path) < 2:
            return
        step_px = WALK_SPEED_PX_PER_SEC * dt_ms / 1000.0
        remaining = step_px
        while remaining > 0 and slot.path_step < len(slot.path) - 1:
            nxt = slot.path[slot.path_step + 1]
            tx, ty = nxt[0] * TILE_SIZE, nxt[1] * TILE_SIZE
            dx, dy = tx - slot.x, ty - slot.y
            dist = abs(dx) + abs(dy)
            if dist <= remaining:
                slot.x, slot.y = tx, ty
                slot.path_step += 1
                remaining -= dist
            else:
                ratio = remaining / dist if dist else 0
                slot.x += int(round(dx * ratio))
                slot.y += int(round(dy * ratio))
                remaining = 0
            if dx > 0:
                slot.facing = DIR_RIGHT
            elif dx < 0:
                slot.facing = DIR_LEFT
            elif dy > 0:
                slot.facing = DIR_DOWN
            elif dy < 0:
                slot.facing = DIR_UP
        if slot.path_step >= len(slot.path) - 1:
            slot.walking = False
            slot.path = []
            if slot.seat is not None and slot.cell == (slot.seat.col, slot.seat.row):
                slot.facing = slot.seat.facing

    # ------------------------------------------------------------ bus

    def _agent_for_card(self, card_id: str) -> str:
        """Kart kimliğinden ajan adı; kart panosu yoksa boş."""
        if not card_id:
            return ""
        for agent, cid in self.agent_cards.items():
            if cid == card_id:
                return agent
        try:
            from entropy.agents.tasks import TaskBoard  # type: ignore

            card = TaskBoard().get(card_id)
            return str(getattr(card, "agent", "") or "")
        except Exception:
            return ""

    @Slot(str, str, str)
    def _on_office_progress(self, office: str, card: str, stage: str) -> None:
        if self.office.name and office and office != self.office.name:
            return
        key = str(stage).strip().lower()
        state = STAGE_TO_STATE.get(key)
        if state is None:
            # Bilinmeyen aşama bir araç adı olabilir: okuma aracıysa READ.
            state = state_for_tool(key)
        agent = self._agent_for_card(card)
        if not agent:
            agent = (
                self.office.evaluator
                if "eval" in key or "deger" in key
                else self.office.orchestrator
            )
        if agent:
            self.agent_cards[agent] = card
            self.set_state(agent, state, note=str(stage))

    @Slot(str, str)
    def _on_task_triggered(self, card_id: str, card_name: str) -> None:
        agent = self._agent_for_card(card_id)
        if agent:
            self.agent_cards[agent] = card_id
            self.set_state(agent, STATE_WORKING, note=card_name)

    @Slot(str, bool)
    def _on_task_completed(self, card_id: str, success: bool) -> None:
        agent = self._agent_for_card(card_id)
        if agent:
            self.set_state(agent, STATE_IDLE if success else STATE_ERROR)

    @Slot(str)
    def _on_turn_started(self, _prompt: str) -> None:
        agent = self.selected_agent or self.office.orchestrator
        if agent:
            self.set_state(agent, STATE_THINKING)

    @Slot(str)
    def _on_turn_completed(self, _response: str) -> None:
        agent = self.selected_agent or self.office.orchestrator
        if agent:
            self.set_state(agent, STATE_IDLE)

    @Slot(str)
    def _on_offices_updated(self, office_name: str) -> None:
        if not self.office.name or office_name in ("", self.office.name):
            try:
                from entropy.agents.desk_registry import DeskRegistry as OfficeRegistry  # type: ignore

                fresh = OfficeRegistry().get(self.office.name)
                if fresh is not None:
                    self.set_office(fresh)
            except Exception:
                pass

    # ------------------------------------------------------------ animasyon

    def is_busy(self) -> bool:
        return any(
            s.walking or s.state in (STATE_THINKING, STATE_WORKING, STATE_READING)
            for s in self.slots
        )

    def _sync_timer(self) -> None:
        """Kare hızı: etkin 30 fps, boşta 10 fps, gizliyken durur."""
        if not self.isVisible():
            self._timer.stop()
            return
        interval = ACTIVE_INTERVAL_MS if self.is_busy() else IDLE_INTERVAL_MS
        if self._timer.interval() != interval or not self._timer.isActive():
            self._timer.start(interval)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.relayout()
        self._sync_timer()

    def hideEvent(self, event):  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    @Slot()
    def _on_tick(self) -> None:
        dt = self._timer.interval() or IDLE_INTERVAL_MS
        self._elapsed_ms += dt
        self._pulse_frame = (self._pulse_frame + 1) % 60
        for slot in self.slots:
            self._advance_walk(slot, dt)
        self._sync_timer()
        self.update()

    @property
    def pulse_frame(self) -> int:
        return self._pulse_frame

    def _anim_step(self, slot: DeskSlot) -> Tuple[str, int]:
        """Bir ajan için (animasyon, kare indeksi)."""
        if slot.walking:
            return ANIM_WALK, self._elapsed_ms // WALK_FRAME_MS
        anim = STATE_ANIMATION.get(slot.state, ANIM_IDLE)
        if anim == ANIM_IDLE:
            return ANIM_IDLE, 0
        return anim, self._elapsed_ms // WORK_FRAME_MS

    # ------------------------------------------------------------ etkileşim

    def slot_at(self, raw_pos) -> Optional[DeskSlot]:
        """Pencere koordinatındaki noktanın altındaki karakter (yoksa None)."""
        pos = self._to_logical(raw_pos)
        # Önde duran (satırca aşağıdaki) karakter önce test edilir.
        for slot in sorted(self.slots, key=lambda s: -s.y):
            if slot.rect.contains(pos):
                return slot
        return None

    def mousePressEvent(self, event):  # noqa: N802
        raw = event.position().toPoint() if hasattr(event, "position") else event.pos()
        slot = self.slot_at(raw)
        if slot is not None:
            self.select_agent(slot.agent)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        """Karakter üzerinde ipucu: ad, rol, durum ve son not."""
        raw = event.position().toPoint() if hasattr(event, "position") else event.pos()
        slot = self.slot_at(raw)
        if slot is None:
            self.setToolTip("")
        else:
            role_label = {
                ROLE_ORCHESTRATOR: "orkestratör",
                ROLE_EVALUATOR: "değerlendirici",
            }.get(slot.role, "üye")
            note = f"\n{slot.note}" if slot.note else ""
            self.setToolTip(
                f"{slot.agent}\n{role_label} · "
                f"{STATE_LABELS.get(slot.state, slot.state)}{note}"
            )
        super().mouseMoveEvent(event)

    def select_agent(self, agent: str) -> None:
        self.selected_agent = agent
        self.update()
        if agent:
            self.agent_clicked.emit(agent)

    # ------------------------------------------------------------ çizim

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.fillRect(self.rect(), QColor(12, 15, 22))

        if not self.layout.cols:
            self._draw_center_text(painter, "Ofis düzeni yüklenemedi.")
            return

        scale, dx, dy = self._view_transform()
        painter.save()
        painter.translate(dx, dy)
        painter.scale(scale, scale)
        self._draw_floor(painter)
        self._draw_carpets(painter)
        self._draw_depth_layer(painter)
        painter.restore()

        if not self.slots:
            self._draw_center_text(painter, "Bu ofiste ajan yok.\nSağdaki listeden ajan ekleyin.")
            return

        for slot in self.slots:
            self._draw_label(painter, slot, scale, dx, dy)

    def _draw_center_text(self, painter: QPainter, text: str) -> None:
        painter.setPen(QColor(147, 163, 184))
        font = QFont("Segoe UI")
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _draw_floor(self, painter: QPainter) -> None:
        """Zemin karoları tek bir önbellek pixmap'ine çizilir (her karede değil)."""
        if self._floor_cache is None:
            # Önbellek TÜM ızgara boyutunda: karolar mutlak hücre koordinatına
            # çizilir, kırpılmış görünüm boyutuna sığmaz.
            w = max(self.layout.cols, 1) * TILE_SIZE
            h = max(self.layout.rows, 1) * TILE_SIZE
            cache = QPixmap(w, h)
            cache.fill(Qt.GlobalColor.transparent)
            cache_painter = QPainter(cache)
            for r in range(self.layout.rows):
                for c in range(self.layout.cols):
                    value = self.layout.tile(c, r)
                    if value == TILE_EMPTY:
                        continue
                    tile = self.tilemap.floor_tile(value)
                    if tile is not None and not tile.isNull():
                        cache_painter.drawPixmap(c * TILE_SIZE, r * TILE_SIZE, tile)
            cache_painter.end()
            self._floor_cache = cache
        painter.drawPixmap(0, 0, self._floor_cache)

    def _draw_carpets(self, painter: QPainter) -> None:
        """
        Halı: marching squares. Düzende `carpetTiles` yoksa hiç çizilmez.

        Kavşak ızgarası (cols+1) x (rows+1); vaka 0 atlanır.
        """
        cells = getattr(self.layout, "carpet_cells", None)
        if not cells:
            return
        grid = [[False] * self.layout.cols for _ in range(self.layout.rows)]
        for c, r in cells:
            if 0 <= r < self.layout.rows and 0 <= c < self.layout.cols:
                grid[r][c] = True
        for jy in range(self.layout.rows + 1):
            for jx in range(self.layout.cols + 1):
                case = carpet_case(jx, jy, grid)
                tile = self.tilemap.carpet_tile(case)
                if tile is not None and not tile.isNull():
                    painter.drawPixmap(
                        jx * TILE_SIZE - TILE_SIZE // 2,
                        jy * TILE_SIZE - TILE_SIZE // 2,
                        tile,
                    )

    def _draw_depth_layer(self, painter: QPainter) -> None:
        """Duvar + mobilya + karakterler tek listede, satır sıralı derinlikle."""
        items: List[Tuple[Tuple[int, int], object]] = []

        for r in range(self.layout.rows):
            for c in range(self.layout.cols):
                if not self.layout.is_wall(c, r):
                    continue
                mask = wall_bitmask(c, r, self.layout.tiles)
                tile = self.tilemap.wall_tile(mask)
                if tile is None or tile.isNull():
                    continue
                offset_y = TILE_SIZE - tile.height()
                items.append(((r + 1, c), ("pix", c * TILE_SIZE, r * TILE_SIZE + offset_y, tile)))

        frame = self._elapsed_ms // WORK_FRAME_MS
        for placed in self.layout.furniture:
            variant = placed.variant
            pix = self.furniture.pixmap(variant, frame if variant.animated else 0, placed.mirrored)
            if pix is None or pix.isNull():
                continue
            depth_row = placed.row + variant.footprint_h
            y = (placed.row + variant.footprint_h) * TILE_SIZE - pix.height()
            items.append(((depth_row, placed.col), ("pix", placed.col * TILE_SIZE, y, pix)))

        for slot in self.slots:
            items.append((((slot.y // TILE_SIZE) + 1, slot.x // TILE_SIZE), ("agent", slot)))

        items.sort(key=lambda it: it[0])
        for _, payload in items:
            if payload[0] == "pix":
                painter.drawPixmap(int(payload[1]), int(payload[2]), payload[3])
            else:
                self._draw_agent(painter, payload[1])

    def _draw_agent(self, painter: QPainter, slot: DeskSlot) -> None:
        sheet = self.characters.sheet(slot.char_index)
        anim, step = self._anim_step(slot)
        pix = sheet.animation_frame(slot.facing, anim, int(step)) if sheet else None

        # Karakter 16x32: ayakları hücrenin altına hizalanır, gövde yukarı taşar.
        top = slot.y + TILE_SIZE - (pix.height() if pix else 32)
        if slot.agent == self.selected_agent:
            painter.setPen(QPen(QColor(56, 217, 255), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(slot.x - 1, top - 1, TILE_SIZE + 1, (pix.height() if pix else 32) + 1)
        if pix is not None and not pix.isNull():
            painter.drawPixmap(slot.x, top, pix)
        else:
            # Varlık yüklenemediyse yine de bir gövde çizilir (sahne boş kalmasın).
            painter.fillRect(slot.x + 4, top + 12, 8, 20, STATE_COLORS[slot.state])

        bubble = STATE_BUBBLE.get(slot.state, "")
        if bubble:
            self._draw_bubble(painter, slot, top, bubble)

    def _draw_bubble(self, painter: QPainter, slot: DeskSlot, top: int, text: str) -> None:
        """Baş üstü balon: düşünüyor '…', bekliyor '⏳', hata kırmızı '!'."""
        bob = 1 if (self._pulse_frame // 15) % 2 else 0
        bx, by = slot.x + 4, top - 12 - bob
        color = QColor(238, 244, 252) if slot.state != STATE_ERROR else QColor(239, 68, 68)
        painter.setPen(QPen(QColor(18, 22, 30), 1))
        painter.setBrush(color)
        painter.drawRect(bx, by, 12, 10)
        painter.setPen(QColor(18, 22, 30) if slot.state != STATE_ERROR else QColor(255, 255, 255))
        font = QFont("Segoe UI")
        font.setPixelSize(8)
        painter.setFont(font)
        painter.drawText(QRect(bx, by, 12, 10), Qt.AlignmentFlag.AlignCenter, text)

    def _draw_label(self, painter: QPainter, slot: DeskSlot,
                    scale: float, dx: float, dy: float) -> None:
        """
        Ad etiketi piksel sabit: dönüşüm dışında, `setPixelSize` ile çizilir.
        Sahne küçülünce karakter küçülür, yazı okunur kalır.
        Orkestratör etiketi ayrı renkte ve "◆" ile işaretli.
        """
        cx = int((slot.x + TILE_SIZE / 2) * scale + dx)
        base_y = int((slot.y + TILE_SIZE) * scale + dy) + 12
        font = QFont("Segoe UI")
        font.setPixelSize(11)
        font.setBold(slot.role == ROLE_ORCHESTRATOR)
        painter.setFont(font)
        text = slot.agent
        if slot.role == ROLE_ORCHESTRATOR:
            text = f"◆ {text}"
        metrics = QFontMetrics(font)
        text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, 110)
        width = metrics.horizontalAdvance(text) + 8
        box = QRect(cx - width // 2, base_y - 11, width, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 14, 22, 190))
        painter.drawRect(box)
        painter.setPen(
            QColor(255, 214, 120) if slot.role == ROLE_ORCHESTRATOR
            else STATE_COLORS.get(slot.state, STATE_COLORS[STATE_IDLE])
        )
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
