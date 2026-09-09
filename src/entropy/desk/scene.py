"""
Ofis sahnesi: bir ofisin ajanlarını piksel masalar olarak çizer.

Kaynak: Faz 1 `PixelCanvas`. O dosya artık var olmayan veri sınıflarına
bağlıydı; gereken çizim yardımcıları buraya taşınıp uyarlandı, ölü importlar
atıldı ve eski `desk/legacy/` paketi Faz 4'te tamamen kaldırıldı.

Uyarlamada değişenler:
- Veri kaynağı `AgentPersona` değil, ofis sözleşmesi: ajan adı + rol
  (orchestrator|evaluator|worker) + durum.
- Yerleşim ofis odaklı: orkestratör masası merkezde, üyeler çevresinde halka,
  değerlendirici sağ alt köşede. Pencere boyutlanınca yerleşim yeniden hesaplanır.
- Animasyon tamamen istemci tarafı (LLM çağrısı yok): etkinlik varken 30 fps,
  boştayken 10 fps, pencere gizliyken zamanlayıcı durur. Referans uygulamalarda
  (agent-office) boştaki ajanlar bile LLM çağırıyordu; kota için sürdürülemez.
- Etiketler piksel sabit: masa ölçeklense de yazı boyu sabit kalır, okunur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PySide6.QtCore import QRect, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from entropy.core.event_bus import bus

# --------------------------------------------------------------------- durumlar
# Tasarım raporu §2.3: boşta / düşünüyor / çalışıyor / hata / bekliyor.
STATE_IDLE = "idle"
STATE_THINKING = "thinking"
STATE_WORKING = "working"
STATE_ERROR = "error"
STATE_WAITING = "waiting"

STATES = (STATE_IDLE, STATE_THINKING, STATE_WORKING, STATE_ERROR, STATE_WAITING)

STATE_LABELS = {
    STATE_IDLE: "boşta",
    STATE_THINKING: "düşünüyor",
    STATE_WORKING: "çalışıyor",
    STATE_ERROR: "hata",
    STATE_WAITING: "bekliyor",
}

STATE_COLORS = {
    STATE_IDLE: QColor(93, 116, 140),
    STATE_THINKING: QColor(255, 194, 77),
    STATE_WORKING: QColor(61, 232, 168),
    STATE_ERROR: QColor(239, 68, 68),
    STATE_WAITING: QColor(56, 217, 255),
}

# Harness aşama adı -> sahne durumu. `bus.office_progress(office, card, stage)`
# sözleşmesi aşama adını serbest metin bırakıyor; bilinmeyen aşama "çalışıyor"
# sayılır (sessizce yutmak, sahneyi olduğundan sakin gösterirdi).
STAGE_TO_STATE = {
    "planning": STATE_THINKING,
    "plan": STATE_THINKING,
    "planlama": STATE_THINKING,
    "running": STATE_WORKING,
    "executing": STATE_WORKING,
    "yurutme": STATE_WORKING,
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

ROLE_ORCHESTRATOR = "orchestrator"
ROLE_EVALUATOR = "evaluator"
ROLE_WORKER = "worker"

# Kare hızları: etkin 30 fps (rapor sınırı), boşta 10 fps.
ACTIVE_INTERVAL_MS = 33
IDLE_INTERVAL_MS = 100

DESK_W = 160
DESK_H = 148
# Izgara hücreleri arası boşluk (mantıksal piksel).
GAP = 16


@dataclass
class DeskSlot:
    """Sahnedeki tek masa: bir ajan, bir rol, bir durum."""

    agent: str
    role: str = ROLE_WORKER
    state: str = STATE_IDLE
    note: str = ""
    x: int = 0
    y: int = 0
    width: int = DESK_W
    height: int = DESK_H

    @property
    def rect(self) -> QRect:
        return QRect(self.x, self.y, self.width, self.height)


@dataclass
class SceneOffice:
    """Sahnenin ihtiyacı olan ofis özeti (OfficeSpec'ten okunur, kopyası değil)."""

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


class OfficeScene(QWidget):
    """Ofis kat planı: orkestratör merkezde, üyeler çevrede, değerlendirici köşede."""

    agent_clicked = Signal(str)   # sprite tıklandı: ajan adı

    def __init__(self, parent: Optional[QWidget] = None, office=None):
        super().__init__(parent)
        self.setMinimumSize(520, 330)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMouseTracking(True)

        self.office = SceneOffice()
        self.slots: List[DeskSlot] = []
        self.selected_agent: str = ""
        self._pulse_frame: int = 0
        self._logical_size = (DESK_W + 2 * GAP, DESK_H + 2 * GAP)
        # Ajan adı -> son kart kimliği; tıklamada akış paneline bağlam verir.
        self.agent_cards: Dict[str, str] = {}

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._connect_bus()
        if office is not None:
            self.set_office(office)
        else:
            self._sync_timer()

    # ------------------------------------------------------------ sözleşme

    def _connect_bus(self) -> None:
        """
        Sözleşme sinyalleri agy ajanı tarafından ekleniyor; yoksa atlanır.

        Alıcılar QObject slotu (lambda değil): işçi iş parçacığından yayılan
        sinyal kuyruklanır ve çizim ana iş parçacığında kalır.
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
        self._rebuild_slots()

    def _rebuild_slots(self) -> None:
        """Ajan listesini masalara dağıtır; mevcut durumlar korunur."""
        previous = {s.agent: s for s in self.slots}
        slots: List[DeskSlot] = []
        seen = set()

        def add(agent: str, role: str) -> None:
            if not agent or agent in seen:
                return
            seen.add(agent)
            old = previous.get(agent)
            slots.append(DeskSlot(
                agent=agent,
                role=role,
                state=old.state if old else STATE_IDLE,
                note=old.note if old else "",
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

    def slot_for(self, agent: str) -> Optional[DeskSlot]:
        for slot in self.slots:
            if slot.agent == agent:
                return slot
        return None

    def states(self) -> Dict[str, str]:
        """Test ve panel için: ajan adı -> durum."""
        return {s.agent: s.state for s in self.slots}

    # ------------------------------------------------------------ yerleşim

    def relayout(self) -> None:
        """
        Masaları mantıksal ızgaraya yerleştirir: orkestratör tam merkezde, üyeler
        çevresindeki hücrelerde, değerlendirici sağ alt köşede.

        Neden ızgara, halka değil: elips halka dar panellerde (sahne yüksekliği
        ~430 px) merkezdeki masayla üst üste biniyordu. Izgarada hücreler
        tanımı gereği çakışmaz; sahne küçüldüğünde çizim ölçeklenir
        (bkz. `_view_transform`), üst üste binme oluşmaz.
        """
        orchestrators = [s for s in self.slots if s.role == ROLE_ORCHESTRATOR]
        evaluators = [s for s in self.slots if s.role == ROLE_EVALUATOR]
        workers = [s for s in self.slots if s.role == ROLE_WORKER]

        # Izgara boyutu: merkez + çevresi. 8 üyeye kadar 3x3 yeter; sonra 5x5.
        side = 3
        while side * side - 1 < max(len(workers) + (1 if evaluators else 0), 1):
            side += 2
        center = side // 2

        def cell_rect(col: int, row: int) -> tuple:
            return (GAP + col * (DESK_W + GAP), GAP + row * (DESK_H + GAP))

        for slot in orchestrators:
            slot.x, slot.y = cell_rect(center, center)

        used = {(center, center)}
        for slot in evaluators:
            slot.x, slot.y = cell_rect(side - 1, side - 1)
            used.add((side - 1, side - 1))

        # Çevre hücreleri merkeze yakınlıktan uzağa doğru sıralanır: az üyeli
        # ofiste masalar orkestratörün etrafına toplanır, kenarlara dağılmaz.
        candidates = sorted(
            ((c, r) for r in range(side) for c in range(side) if (c, r) not in used),
            key=lambda cr: (max(abs(cr[0] - center), abs(cr[1] - center)), cr[1], cr[0]),
        )
        for slot, (col, row) in zip(workers, candidates):
            slot.x, slot.y = cell_rect(col, row)

        self._logical_size = (
            GAP + side * (DESK_W + GAP),
            GAP + side * (DESK_H + GAP),
        )

    def _view_transform(self) -> tuple:
        """
        Mantıksal koordinatları pencereye sığdıran (ölçek, dx, dy) üçlüsü.

        Ölçek yalnızca küçültür (1.0 üstüne çıkılmaz): boş bir ofiste masalar
        dev gibi büyümesin, piksel çizim keskin kalsın.
        """
        logical_w, logical_h = self._logical_size
        if logical_w <= 0 or logical_h <= 0:
            return 1.0, 0.0, 0.0
        scale = min(1.0, self.width() / logical_w, self.height() / logical_h)
        dx = (self.width() - logical_w * scale) / 2
        dy = (self.height() - logical_h * scale) / 2
        return scale, dx, dy

    def _to_logical(self, point) -> "QPointF":
        from PySide6.QtCore import QPointF

        scale, dx, dy = self._view_transform()
        if scale <= 0:
            return QPointF(point)
        return QPointF((point.x() - dx) / scale, (point.y() - dy) / scale)

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
        if note:
            slot.note = note
        self._sync_timer()
        self.update()
        return True

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
        """`bus.office_progress`: aşama adını sahne durumuna çevirir."""
        if self.office.name and office and office != self.office.name:
            return
        state = STAGE_TO_STATE.get(str(stage).strip().lower(), STATE_WORKING)
        agent = self._agent_for_card(card)
        if not agent:
            # Kartın sahibi bilinmiyorsa aşama orkestratöre/değerlendiriciye aittir.
            agent = (
                self.office.evaluator
                if "eval" in str(stage).lower() or "deger" in str(stage).lower()
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
        """Köprü bir tur başlattı: seçili (yoksa orkestratör) masa düşünmeye geçer."""
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
                from entropy.agents.offices import OfficeRegistry  # type: ignore

                fresh = OfficeRegistry().get(self.office.name)
                if fresh is not None:
                    self.set_office(fresh)
            except Exception:
                pass

    # ------------------------------------------------------------ animasyon

    def is_busy(self) -> bool:
        return any(s.state in (STATE_THINKING, STATE_WORKING) for s in self.slots)

    def _sync_timer(self) -> None:
        """Kare hızını duruma göre ayarlar; gizli pencerede tamamen durdurur."""
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
        # Pencere gizliyken çizim yapmak boşuna CPU; zamanlayıcı durur.
        self._timer.stop()
        super().hideEvent(event)

    @Slot()
    def _on_tick(self) -> None:
        self._pulse_frame = (self._pulse_frame + 1) % 60
        self.update()

    @property
    def pulse_frame(self) -> int:
        return self._pulse_frame

    # ------------------------------------------------------------ etkileşim

    def mousePressEvent(self, event):  # noqa: N802
        raw = event.position().toPoint() if hasattr(event, "position") else event.pos()
        # Çizim ölçeklenmiş olabilir; tıklama mantıksal koordinata çevrilmeden
        # test edilirse küçük sahnede yanlış masa seçilirdi.
        pos = self._to_logical(raw).toPoint()
        for slot in self.slots:
            if slot.rect.contains(pos):
                self.select_agent(slot.agent)
                break
        super().mousePressEvent(event)

    def slot_at(self, raw_pos) -> Optional[DeskSlot]:
        """Pencere koordinatındaki noktanın altındaki masa (yoksa None)."""
        pos = self._to_logical(raw_pos).toPoint()
        for slot in self.slots:
            if slot.rect.contains(pos):
                return slot
        return None

    def mouseMoveEvent(self, event):  # noqa: N802
        """
        Masa üzerinde ipucu: etiket kırpıldıysa tam ad/rol/durum burada okunur.

        Kırpma bilgi gizlemesin diye ipucu ham metni taşır.
        """
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
                f"{slot.agent}\n{role_label} · {STATE_LABELS.get(slot.state, slot.state)}{note}"
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
        w, h = self.width(), self.height()

        # 1. Zemin ve ızgara (Faz 1 piksel kanvasından uyarlandı)
        painter.fillRect(0, 0, w, h, QColor(15, 18, 26))
        painter.setPen(QPen(QColor(26, 32, 44, 80), 1))
        for x in range(0, w, 24):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 24):
            painter.drawLine(0, y, w, y)

        # 2. Ofis halısı
        painter.fillRect(16, 12, max(w - 32, 10), max(h - 24, 10), QBrush(QColor(22, 27, 39)))
        painter.setPen(QPen(QColor(45, 55, 72), 2))
        painter.drawRect(16, 12, max(w - 32, 10), max(h - 24, 10))

        if not self.slots:
            painter.setPen(QColor(147, 163, 184))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Bu ofiste ajan yok.\nSağdaki listeden ajan ekleyin.",
            )
            return

        # Masalar mantıksal koordinatta çizilir; sahne dar olduğunda tüm kat planı
        # küçültülür (masalar üst üste binmesin diye). Etiketler bu ölçekten
        # etkilenmez: aşağıda dönüşüm sıfırlanıp piksel boyutlu çizilir.
        scale, dx, dy = self._view_transform()
        painter.save()
        painter.translate(dx, dy)
        painter.scale(scale, scale)
        for slot in self.slots:
            self._draw_desk(painter, slot, slot.agent == self.selected_agent)
        painter.restore()

        for slot in self.slots:
            self._draw_label(painter, slot, scale, dx, dy)

    def _draw_desk(self, painter: QPainter, slot: DeskSlot, selected: bool) -> None:
        x, y, w = slot.x, slot.y, slot.width
        is_orch = slot.role == ROLE_ORCHESTRATOR
        is_eval = slot.role == ROLE_EVALUATOR
        state = slot.state
        accent = STATE_COLORS.get(state, STATE_COLORS[STATE_IDLE])

        if selected:
            painter.setPen(QPen(QColor(56, 217, 255), 2))
            painter.setBrush(QBrush(QColor(30, 38, 56, 180)))
            painter.drawRoundedRect(x - 4, y - 4, w + 8, slot.height + 8, 4, 4)

        # Masa gövdesi: rol rengi ayırt edici (orkestratör mor, değerlendirici yeşil)
        table_color = QColor(42, 51, 68)
        if is_orch:
            table_color = QColor(56, 44, 76)
        elif is_eval:
            table_color = QColor(34, 60, 52)
        painter.setPen(QPen(QColor(60, 72, 94), 1))
        painter.setBrush(QBrush(table_color))
        painter.drawRect(x + 10, y + 40, w - 20, 50)
        painter.fillRect(x + 11, y + 41, w - 22, 1, QColor(80, 95, 122, 160))

        # Masa ayakları
        painter.fillRect(x + 16, y + 90, 8, 22, QColor(25, 30, 42))
        painter.fillRect(x + w - 24, y + 90, 8, 22, QColor(25, 30, 42))

        # Monitör (orkestratörde çift)
        mx, my = x + 35, y + 10
        painter.fillRect(mx, my, 45, 30, QColor(10, 12, 18))
        painter.setPen(QPen(QColor(80, 90, 110), 1))
        painter.drawRect(mx, my, 45, 30)
        painter.fillRect(mx + 18, my + 30, 9, 10, QColor(35, 40, 55))
        if is_orch:
            painter.fillRect(mx + 50, my + 4, 40, 26, QColor(10, 12, 18))
            painter.drawRect(mx + 50, my + 4, 40, 26)
        self._draw_screen(painter, mx, my, state)

        # Sandalye + karakter
        chair_x = x + (w // 2) - 16
        chair_y = y + 58
        chair_col = QColor(50, 25, 70) if is_orch else (QColor(25, 52, 44) if is_eval else QColor(25, 28, 38))
        painter.fillRect(chair_x, chair_y, 32, 36, chair_col)

        head_bob = 0
        if state == STATE_WORKING:
            head_bob = (0, 1, 2, 1)[(self._pulse_frame // 3) % 4]
        elif state == STATE_THINKING:
            head_bob = -1
        head_color = QColor(168, 85, 247) if is_orch else (QColor(61, 232, 168) if is_eval else QColor(245, 158, 11))
        head_x, head_y = chair_x + 6, chair_y - 14 + head_bob
        painter.fillRect(head_x, head_y, 20, 18, head_color)
        painter.fillRect(head_x + 1, head_y, 18, 2, head_color.lighter(130))
        painter.fillRect(chair_x + 10, chair_y - 8 + head_bob, 12, 4, QColor(15, 23, 42))
        painter.fillRect(chair_x + 12, chair_y - 7 + head_bob, 8, 2, accent)

        # Klavye ve yazan eller
        kb_x, kb_y = mx + 6, y + 48
        painter.fillRect(kb_x, kb_y, 34, 8, QColor(30, 36, 50))
        if state == STATE_WORKING:
            offset = (0, 2, 0, -1)[(self._pulse_frame // 4) % 4]
            painter.fillRect(kb_x + 4, kb_y - 3 + offset, 5, 4, head_color)
            painter.fillRect(kb_x + 24, kb_y - 3 - offset, 5, 4, head_color)

        # Durum balonu: renkli nokta + rol rozeti
        self._draw_state_bubble(painter, slot, accent)

    def _draw_screen(self, painter: QPainter, mx: int, my: int, state: str) -> None:
        """Monitör içi: duruma göre canlanan piksel içerik."""
        sx, sy, sw, sh = mx + 3, my + 3, 39, 24
        painter.fillRect(sx, sy, sw, sh, QColor(8, 14, 22))
        color = STATE_COLORS.get(state, STATE_COLORS[STATE_IDLE])
        if state == STATE_WORKING:
            rows = 4
            for r in range(rows):
                width = 6 + ((self._pulse_frame // 4 + r * 5) % (sw - 10))
                painter.fillRect(sx + 3, sy + 3 + r * 5, width, 2, color)
        elif state == STATE_THINKING:
            phase = (self._pulse_frame // 5) % 3
            for i in range(3):
                dot = color if i <= phase else QColor(40, 52, 70)
                painter.fillRect(sx + 8 + i * 8, sy + 11, 4, 4, dot)
        elif state == STATE_ERROR:
            painter.setPen(QPen(color, 2))
            painter.drawLine(sx + 12, sy + 7, sx + 27, sy + 18)
            painter.drawLine(sx + 27, sy + 7, sx + 12, sy + 18)
        elif state == STATE_WAITING:
            painter.fillRect(sx + 6, sy + 11, sw - 12, 3, QColor(40, 52, 70))
            head = (self._pulse_frame // 3) % (sw - 16)
            painter.fillRect(sx + 6 + head, sy + 10, 6, 5, color)
        else:
            painter.fillRect(sx + 4, sy + 20, sw - 8, 1, QColor(40, 52, 70))

    def _draw_state_bubble(self, painter: QPainter, slot: DeskSlot, accent: QColor) -> None:
        x, y, w = slot.x, slot.y, slot.width
        pulse = 1 if slot.state in (STATE_THINKING, STATE_WORKING) and (self._pulse_frame // 8) % 2 else 0
        painter.setBrush(QBrush(accent))
        painter.setPen(QPen(QColor(10, 14, 22), 1))
        painter.drawEllipse(x + w - 26, y + 2 - pulse, 10, 10)

    def _draw_label(self, painter: QPainter, slot: DeskSlot, scale: float, dx: float, dy: float) -> None:
        """
        Ad + rol + durum. Yazı tipi piksel cinsinden sabit (setPixelSize) ve
        çizim dönüşümün dışında yapılır: sahne küçülünce masalar küçülür ama
        etiketler aynı boyutta ve okunur kalır (grafik widget'ındaki piksel
        sabit etiket ilkesinin aynısı).
        """
        # Mantıksal kutuyu pencere (piksel) koordinatına taşı.
        x = int(slot.x * scale + dx)
        y = int(slot.y * scale + dy)
        w = int(slot.width * scale)
        label_y = int((slot.y + 112) * scale + dy)
        meta_y = int((slot.y + 128) * scale + dy)
        # Etiket kutusu masa genişliğiyle sınırlı: yazı tipi piksel sabit olduğu
        # için sahne küçüldükçe metin kutudan taşıp komşu masanın üstüne
        # biniyordu (Faz 2-3 notu: "sahnede etiket taşması"). Hem ad hem de
        # rol/durum satırı bu genişliğe göre kırpılır.
        box = max(24, w - 6)
        name_font = QFont("Segoe UI")
        name_font.setPixelSize(13)
        name_font.setBold(True)
        painter.setFont(name_font)
        name = QFontMetrics(name_font).elidedText(
            slot.agent, Qt.TextElideMode.ElideRight, box
        )
        painter.setPen(QColor(232, 239, 247))
        painter.drawText(x, label_y, w, 16, Qt.AlignmentFlag.AlignCenter, name)

        meta_font = QFont("Segoe UI")
        meta_font.setPixelSize(11)
        painter.setFont(meta_font)
        role_label = {
            ROLE_ORCHESTRATOR: "orkestratör",
            ROLE_EVALUATOR: "değerlendirici",
        }.get(slot.role, "üye")
        meta_text = f"{role_label} · {STATE_LABELS.get(slot.state, slot.state)}"
        meta_text = QFontMetrics(meta_font).elidedText(
            meta_text, Qt.TextElideMode.ElideRight, box
        )
        painter.setPen(STATE_COLORS.get(slot.state, STATE_COLORS[STATE_IDLE]))
        painter.drawText(x, meta_y, w, 14, Qt.AlignmentFlag.AlignCenter, meta_text)
