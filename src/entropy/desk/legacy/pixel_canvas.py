"""
Entropy Agent Desk: Pixel Office Canvas.
2D Retro Pixel-Art Office Visualization inspired by 'pablodelucca/pixel-agents':
- Visualizes the office floor, desks, dual monitors, chairs, and pixel avatars.
- Renders live activity states: Typing (keyboard glow), Reading (document), Thinking (thought bubble), Testing (matrix pulse), Idle.
- Supports desk click interactions to inspect or switch terminals.
- Fully compatible with headless CI/CD offscreen rendering.
"""

import math
from typing import Dict, List, Optional, Callable, Union
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QTimer, Signal, QPoint
from PySide6.QtGui import (
    QPainter,
    QColor,
    QBrush,
    QPen,
    QFont,
    QLinearGradient,
    QPolygon,
)
from src.entropy.agent_desk.core.models import (
    AgentPersona,
    AgentActivityState,
    DeskRole,
    OfficeGridMode,
)


class PixelDeskData:
    def __init__(self, desk_index: int, x: int, y: int, persona: Optional[AgentPersona] = None):
        self.desk_index = desk_index
        self.x = x
        self.y = y
        self.width = 160
        self.height = 130
        self.persona = persona


class PixelCanvas(QWidget):
    agent_selected = Signal(str)  # agent_id emitted when desk clicked

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(700, 420)
        self.setFocusPolicy(Qt.ClickFocus)

        self.desks: Dict[int, PixelDeskData] = {}
        self.selected_desk_index: int = 0
        self._pulse_frame: int = 0

        # Animasyon zamanlayıcısı (Piksel aktivite parlaması)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_tick)
        self._anim_timer.start(250)

        self.current_grid_mode: OfficeGridMode = OfficeGridMode.TABBED
        self._setup_default_desk_layout()

    def _setup_default_desk_layout(self):
        """
        Ofis yerleşim planı:
        Masa 0: Üst orta (Orkestratör Masası)
        Masa 1 & 2: Alt sol (CodeArchitect & Developer)
        Masa 3 & 4: Alt sağ (Tester & Researcher)
        """
        self.desks[0] = PixelDeskData(desk_index=0, x=270, y=30)
        self.desks[1] = PixelDeskData(desk_index=1, x=80, y=230)
        self.desks[2] = PixelDeskData(desk_index=2, x=280, y=230)
        self.desks[3] = PixelDeskData(desk_index=3, x=480, y=230)
        self.desks[4] = PixelDeskData(desk_index=4, x=680, y=230)

    def apply_grid_mode(self, mode: Union[OfficeGridMode, str]):
        """Ofis masa düzenini seçilen ızgara moduna göre yeniden konumlandırır."""
        if isinstance(mode, str):
            try:
                mode = OfficeGridMode.from_str(mode)
            except ValueError:
                return
        elif not isinstance(mode, OfficeGridMode):
            return

        self.current_grid_mode = mode

        if mode == OfficeGridMode.SPLIT_1X2:
            if 0 in self.desks:
                self.desks[0].x, self.desks[0].y = 150, 120
            if 1 in self.desks:
                self.desks[1].x, self.desks[1].y = 420, 120
            for idx in list(self.desks.keys()):
                if idx >= 2:
                    c = (idx - 2) % 3
                    r = (idx - 2) // 3
                    self.desks[idx].x = 80 + c * 200
                    self.desks[idx].y = 270 + r * 140

        elif mode == OfficeGridMode.SPLIT_2X2:
            coords = [(150, 40), (420, 40), (150, 220), (420, 220)]
            for idx, (cx, cy) in enumerate(coords):
                if idx in self.desks:
                    self.desks[idx].x, self.desks[idx].y = cx, cy
            for idx in list(self.desks.keys()):
                if idx >= 4:
                    self.desks[idx].x = 80 + (idx - 4) * 200
                    self.desks[idx].y = 380

        elif mode == OfficeGridMode.SPLIT_1X3:
            for idx in sorted(self.desks.keys()):
                if idx < 3:
                    self.desks[idx].x = 60 + idx * 220
                    self.desks[idx].y = 120
                else:
                    self.desks[idx].x = 60 + (idx - 3) * 220
                    self.desks[idx].y = 280

        elif mode == OfficeGridMode.SPLIT_3X3:
            for idx in sorted(self.desks.keys()):
                r = idx // 3
                c = idx % 3
                self.desks[idx].x = 60 + c * 210
                self.desks[idx].y = 30 + r * 130

        elif mode == OfficeGridMode.FOCUS_1_PLUS_3:
            if 0 in self.desks:
                self.desks[0].x, self.desks[0].y = 280, 40
            surround = [(80, 220), (280, 220), (480, 220)]
            for idx, (cx, cy) in enumerate(surround, start=1):
                if idx in self.desks:
                    self.desks[idx].x, self.desks[idx].y = cx, cy
            for idx in sorted(self.desks.keys()):
                if idx >= 4:
                    self.desks[idx].x = 80 + (idx - 4) * 200
                    self.desks[idx].y = 380

        elif mode == OfficeGridMode.ADAPTIVE:
            count = max(1, len(self.desks))
            cols = max(1, math.ceil(math.sqrt(count)))
            for idx in sorted(self.desks.keys()):
                r = idx // cols
                c = idx % cols
                self.desks[idx].x = 60 + c * 200
                self.desks[idx].y = 40 + r * 150

        else:  # TABBED or default
            self._setup_default_desk_layout()

        self.update()

    def set_personas(self, orchestrator: AgentPersona, sub_agents: List[AgentPersona]):
        self.desks[0].persona = orchestrator
        # Clear existing sub-agent desks so removed agents disappear
        for d_idx in list(self.desks.keys()):
            if d_idx != 0:
                self.desks[d_idx].persona = None

        for i, agent in enumerate(sub_agents):
            d_idx = agent.desk_index if agent.desk_index in self.desks and agent.desk_index != 0 else (i + 1)
            if d_idx in self.desks:
                self.desks[d_idx].persona = agent
            else:
                # Dinamik yeni masa ekle
                nx = 80 + (len(self.desks) - 1) * 180
                self.desks[d_idx] = PixelDeskData(desk_index=d_idx, x=nx, y=230, persona=agent)

        if self.current_grid_mode != OfficeGridMode.TABBED:
            self.apply_grid_mode(self.current_grid_mode)
        else:
            self.update()

    def update_office(self, orchestrator):
        """Ofis personellerini ve durumlarını orkestratörden günceller."""
        if hasattr(orchestrator, "sub_agents") and hasattr(orchestrator, "persona"):
            sub_personas = [ag.persona for ag in orchestrator.sub_agents.values()]
            self.set_personas(orchestrator.persona, sub_personas)
        elif hasattr(orchestrator, "persona"):
            self.set_personas(orchestrator.persona, [])

    def update_agent_activity(self, agent_id: str, state: AgentActivityState):
        for desk in self.desks.values():
            if desk.persona and desk.persona.agent_id == agent_id:
                desk.persona.activity_state = state
                break
        self.update()

    @property
    def pulse_frame(self) -> int:
        return self._pulse_frame

    def _on_tick(self):
        self._pulse_frame = (self._pulse_frame + 1) % 60
        self.update()

    def mousePressEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        for d_idx, desk in self.desks.items():
            rect = QRect(desk.x, desk.y, desk.width, desk.height)
            if rect.contains(pos):
                self.selected_desk_index = d_idx
                if desk.persona:
                    self.agent_selected.emit(desk.persona.agent_id)
                self.update()
                break
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)  # Keskin retro piksel çizimi

        # 1. Ofis Zemin Karoları (Retro Cyberpunk / Modern Dark Office Floor)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(15, 18, 26))

        # Izgara çizgileri (Isometric/Pixel grid effect)
        pen_grid = QPen(QColor(26, 32, 44, 80))
        pen_grid.setWidth(1)
        painter.setPen(pen_grid)
        grid_size = 24
        for x in range(0, w, grid_size):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, grid_size):
            painter.drawLine(0, y, w, y)

        # 2. Ofis Halısı & Çalışma Alanı Bölmeleri
        carpet_brush = QBrush(QColor(22, 27, 39))
        painter.fillRect(40, 20, max(w - 80, 620), max(h - 40, 360), carpet_brush)

        pen_border = QPen(QColor(45, 55, 72))
        pen_border.setWidth(2)
        painter.setPen(pen_border)
        painter.drawRect(40, 20, max(w - 80, 620), max(h - 40, 360))

        # 3. Masaları ve Ajanları Çiz
        for d_idx, desk in self.desks.items():
            self._draw_pixel_desk(painter, desk, is_selected=(d_idx == self.selected_desk_index))

    def _draw_pixel_desk(self, painter: QPainter, desk: PixelDeskData, is_selected: bool):
        x, y, w, h = desk.x, desk.y, desk.width, desk.height
        persona = desk.persona
        is_orch = (desk.desk_index == 0)
        state = persona.activity_state if persona else AgentActivityState.IDLE

        # Masa Vurgusu (Seçiliyse Parlayan Kenar)
        if is_selected:
            painter.setPen(QPen(QColor(99, 102, 241), 2))
            painter.setBrush(QBrush(QColor(30, 38, 56, 180)))
            painter.drawRoundedRect(x - 4, y - 4, w + 8, h + 8, 4, 4)

        # Masa Gövdesi (Ahşap / Karbon Fiber Plaka)
        table_color = QColor(42, 51, 68) if not is_orch else QColor(56, 44, 76)
        painter.setPen(QPen(QColor(60, 72, 94), 1))
        painter.setBrush(QBrush(table_color))
        painter.drawRect(x + 10, y + 40, w - 20, 50)

        # Masa Bevel / Ahşap Üst Vurgu Çizgisi
        painter.fillRect(x + 11, y + 41, w - 22, 1, QColor(80, 95, 122, 160))

        # Masa Ayakları
        painter.fillRect(x + 16, y + 90, 8, 25, QColor(25, 30, 42))
        painter.fillRect(x + 16, y + 113, 8, 2, QColor(15, 18, 26))  # Ayak tabanı
        painter.fillRect(x + w - 24, y + 90, 8, 25, QColor(25, 30, 42))
        painter.fillRect(x + w - 24, y + 113, 8, 2, QColor(15, 18, 26))

        # Masa Aksesuarları: Post-It Notu ve Mousepad
        self._draw_desk_accessories(painter, x, y, w, state)

        # Bilgisayar Monitörü (Piksel Ekran Kasası)
        monitor_x = x + 35
        monitor_y = y + 10
        painter.fillRect(monitor_x, monitor_y, 45, 30, QColor(10, 12, 18))
        painter.setPen(QPen(QColor(80, 90, 110), 1))
        painter.drawRect(monitor_x, monitor_y, 45, 30)
        # Monitör Ayağı
        painter.fillRect(monitor_x + 18, monitor_y + 30, 9, 10, QColor(35, 40, 55))

        # Çift Monitör (Orkestratör Masası için)
        if is_orch:
            painter.fillRect(monitor_x + 50, monitor_y + 4, 40, 26, QColor(10, 12, 18))
            painter.setPen(QPen(QColor(80, 90, 110), 1))
            painter.drawRect(monitor_x + 50, monitor_y + 4, 40, 26)

        # Monitör İçi Ekran Çizimi
        self._draw_monitor_screen(painter, monitor_x, monitor_y, is_orch, state)

        # Karakter Avatarı (Sandalye, Gövde, Baş Salınımı ve Pozisyon)
        chair_x = x + (w // 2) - 16
        chair_y = y + 58
        head_color = QColor(245, 158, 11) if not is_orch else QColor(168, 85, 247)

        # Sandalye
        painter.fillRect(chair_x, chair_y, 32, 38, QColor(25, 28, 38) if not is_orch else QColor(50, 25, 70))
        painter.fillRect(chair_x + 2, chair_y + 4, 28, 1, QColor(45, 50, 68))  # Sandalye dikiş çizgisi

        # Baş Salınımı (Ritmik Bobbing & Glance)
        head_bob = 0
        head_drift_x = 0
        if state == AgentActivityState.TYPING:
            # 8-adımlı pürüzsüz yazma ritmi
            typing_bobs = [0, 1, 2, 1, 0, 1, 2, 1]
            head_bob = typing_bobs[self._pulse_frame % len(typing_bobs)]
        elif state == AgentActivityState.THINKING:
            # Düşünce balonuna doğru hafif yukarı ve sağa bakış
            head_bob = -1
            head_drift_x = 1
        elif state == AgentActivityState.READING:
            head_bob = 1

        head_x = chair_x + 6 + head_drift_x
        head_y = chair_y - 14 + head_bob

        # Ajan Piksel Başı
        painter.fillRect(head_x, head_y, 20, 18, head_color)
        # Baş Üstü Işık Vurgusu
        painter.fillRect(head_x + 1, head_y, 18, 2, head_color.lighter(130))

        # Gözler / Vizör & Odaklanma Animasyonu
        eyes_y = chair_y - 8 + head_bob
        painter.fillRect(chair_x + 10 + head_drift_x, eyes_y, 12, 4, QColor(15, 23, 42))

        visor_glow = QColor(56, 189, 248) if not is_orch else QColor(232, 121, 249)
        if state == AgentActivityState.ERROR:
            visor_glow = QColor(239, 68, 68)

        # Yazarken ekran ve klavye arasında mikro bakış odaklanması
        glance_y = 1
        if state == AgentActivityState.TYPING and (self._pulse_frame % 4 == 0):
            glance_y = 2  # Klavyeye bakış

        painter.fillRect(chair_x + 12 + head_drift_x, eyes_y + glance_y, 8, 2, visor_glow)

        # -----------------------------------------------------------------
        # Klavye, Masa Başında Yazma ve Eller Animasyonu
        # -----------------------------------------------------------------
        kb_x = monitor_x + 6
        kb_y = y + 48
        self._draw_typing_and_hands(painter, kb_x, kb_y, chair_x, chair_y, head_color, state)

        # -----------------------------------------------------------------
        # Düşünce ve Durum Balonları Animasyonu (Floating, Trail & Waves)
        # -----------------------------------------------------------------
        head_cx = head_x + 10
        head_cy = head_y
        self._draw_animated_bubble(painter, x, y, w, h, head_cx, head_cy, persona, state)

        # -----------------------------------------------------------------
        # İsim, Seviye ve Odak Enerjisi (RPG Level & Focus Bar)
        # -----------------------------------------------------------------
        font_name = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font_name)
        painter.setPen(QColor(226, 232, 240))
        agent_title = persona.name if persona else f"Boş Masa {desk.desk_index}"
        lvl_str = f"[Lv.{persona.level}] " if (persona and hasattr(persona, "level")) else ""
        painter.drawText(x, y + 118, w, 16, Qt.AlignCenter, f"{lvl_str}{agent_title[:18]}")

        if persona and hasattr(persona, "focus_energy_pct"):
            bar_w = 44
            bar_h = 3
            bar_x = x + (w - bar_w) // 2
            bar_y = y + 136
            painter.fillRect(bar_x, bar_y, bar_w, bar_h, QColor(15, 23, 42))
            energy_ratio = max(0.0, min(1.0, persona.focus_energy_pct / 100.0))
            fill_w = int(bar_w * energy_ratio)
            fill_col = (
                QColor(34, 197, 94)
                if energy_ratio > 0.5
                else (QColor(234, 179, 8) if energy_ratio > 0.2 else QColor(239, 68, 68))
            )
            painter.fillRect(bar_x, bar_y, max(1, fill_w), bar_h, fill_col)

    def _draw_desk_accessories(self, painter: QPainter, x: int, y: int, w: int, state: AgentActivityState):
        """Masa üstü not kağıdı (Post-it), mouse pad ve optik mouse çizimi."""
        # 1. Sarı Post-it Not Kağıdı (Sol masa üstü)
        note_x = x + 14
        note_y = y + 50
        painter.fillRect(note_x, note_y, 11, 12, QColor(254, 240, 138))
        # Kıvrılmış sağ alt köşe gölgesi
        painter.fillRect(note_x + 9, note_y + 10, 2, 2, QColor(202, 138, 4))
        # Not üzerindeki mini piksel metin çizgileri
        painter.fillRect(note_x + 2, note_y + 3, 7, 1, QColor(180, 130, 20, 180))
        painter.fillRect(note_x + 2, note_y + 6, 6, 1, QColor(180, 130, 20, 180))
        painter.fillRect(note_x + 2, note_y + 9, 4, 1, QColor(180, 130, 20, 180))

        # 2. Mousepad & Optik Mouse (Sağ masa üstü)
        pad_x = x + w - 38
        pad_y = y + 50
        painter.fillRect(pad_x, pad_y, 18, 14, QColor(18, 24, 38))
        painter.setPen(QPen(QColor(38, 48, 70), 1))
        painter.drawRect(pad_x, pad_y, 18, 14)

        # Mouse
        mouse_x = pad_x + 4
        mouse_y = pad_y + 3
        painter.fillRect(mouse_x, mouse_y, 9, 8, QColor(40, 48, 65))
        # Sol/sağ buton bölmesi ve aydınlatmalı tekerlek
        wheel_col = QColor(56, 189, 248) if state == AgentActivityState.READING else QColor(74, 222, 128)
        painter.fillRect(mouse_x + 4, mouse_y + 1, 1, 3, wheel_col)

    def _draw_monitor_screen(
        self, painter: QPainter, monitor_x: int, monitor_y: int, is_orch: bool, state: AgentActivityState
    ):
        """Monitör içi aktivite ekranları ve kayan canlı kod/telemetri akışı."""
        screen_x = monitor_x + 2
        screen_y = monitor_y + 2
        screen_w = 41
        screen_h = 26

        if state == AgentActivityState.TYPING:
            # Yeşil retro terminal ekranı + Çok renkli syntax highlighting & kayan kod satırları
            painter.fillRect(screen_x, screen_y, screen_w, screen_h, QColor(8, 24, 14))

            # Kod satırı 1 (Fonksiyon tanımı - mor ve camgöbeği)
            painter.fillRect(screen_x + 3, screen_y + 3, 8, 2, QColor(192, 132, 252))
            painter.fillRect(screen_x + 13, screen_y + 3, 14, 2, QColor(56, 189, 248))

            # Kod satırı 2 (Döngü ve değişken - sarı ve yeşil)
            line2_len = 12 + (self._pulse_frame % 3) * 4
            painter.fillRect(screen_x + 5, screen_y + 7, 7, 2, QColor(251, 146, 60))
            painter.fillRect(screen_x + 14, screen_y + 7, line2_len, 2, QColor(74, 222, 128))

            # Kod satırı 3 (İç blok - yeşil metin)
            painter.fillRect(screen_x + 5, screen_y + 11, 24, 2, QColor(34, 197, 94, 200))

            # Kod satırı 4 (Aktif yazılan satır ve yanıp sönen blok imleç)
            typing_len = 8 + (self._pulse_frame % 5) * 3
            painter.fillRect(screen_x + 3, screen_y + 15, typing_len, 2, QColor(74, 222, 128))
            if self._pulse_frame % 2 == 0:
                painter.fillRect(screen_x + 4 + typing_len, screen_y + 14, 3, 4, QColor(134, 239, 172))

            # Kod satırı 5 (Terminal prompt / dönüş)
            painter.fillRect(screen_x + 3, screen_y + 20, 18, 2, QColor(34, 197, 94, 160))

            if is_orch:
                # İkinci ekranda dinamik ekolayzer telemetrisi
                painter.fillRect(monitor_x + 52, monitor_y + 6, 36, 22, QColor(10, 18, 30))
                for b_idx in range(6):
                    bar_h = 4 + int(math.sin(self._pulse_frame * 0.5 + b_idx) * 5 + 6)
                    bar_h = max(2, min(16, bar_h))
                    bx = monitor_x + 55 + b_idx * 5
                    by = monitor_y + 24 - bar_h
                    painter.fillRect(bx, by, 3, bar_h, QColor(56, 189, 248, 200))

        elif state == AgentActivityState.THINKING:
            # Mor nöral akıl yürütme ekranı + Sinüzoidal düşünce dalgaları
            painter.fillRect(screen_x, screen_y, screen_w, screen_h, QColor(22, 14, 38))
            wave_alpha = 180 + (self._pulse_frame % 5) * 15
            painter.setPen(QPen(QColor(192, 132, 252, wave_alpha), 1))
            wave_pts = [
                (0, 13), (4, 13), (8, 9), (12, 17), (16, 8),
                (20, 18), (24, 10), (28, 15), (32, 13), (38, 13)
            ]
            shift = (self._pulse_frame % 4) * 2
            for pi in range(len(wave_pts) - 1):
                p1 = wave_pts[pi]
                p2 = wave_pts[pi + 1]
                x1 = screen_x + 2 + ((p1[0] + shift) % 36)
                x2 = screen_x + 2 + ((p2[0] + shift) % 36)
                if x2 > x1:
                    painter.drawLine(x1, screen_y + p1[1], x2, screen_y + p2[1])

            if is_orch:
                # İkinci ekranda nöral ağ bağlantı noktaları
                painter.fillRect(monitor_x + 52, monitor_y + 6, 36, 22, QColor(18, 12, 30))
                painter.fillRect(monitor_x + 58, monitor_y + 11, 4, 4, QColor(192, 132, 252))
                painter.fillRect(monitor_x + 76, monitor_y + 11, 4, 4, QColor(192, 132, 252))
                painter.fillRect(monitor_x + 67, monitor_y + 19, 4, 4, QColor(232, 121, 249))
                painter.setPen(QPen(QColor(192, 132, 252, 120), 1))
                painter.drawLine(monitor_x + 60, monitor_y + 13, monitor_x + 67, monitor_y + 21)
                painter.drawLine(monitor_x + 76, monitor_y + 13, monitor_x + 69, monitor_y + 21)

        elif state == AgentActivityState.READING:
            # Cyan dokümantasyon okuma ve tarama çizgisi
            painter.fillRect(screen_x, screen_y, screen_w, screen_h, QColor(12, 28, 44))
            for ly in [4, 8, 12, 16, 20]:
                painter.fillRect(
                    screen_x + 4, screen_y + ly, 28 if ly % 8 != 0 else 20, 2, QColor(56, 189, 248, 140)
                )
            scan_y = screen_y + 4 + ((self._pulse_frame * 3) % 18)
            painter.fillRect(screen_x + 2, scan_y, 37, 2, QColor(125, 211, 252, 220))

        elif state == AgentActivityState.TESTING:
            # Amber test matrisi ve ilerleme çubuğu
            painter.fillRect(screen_x, screen_y, screen_w, screen_h, QColor(36, 26, 10))
            progress_w = 4 + (self._pulse_frame % 6) * 5
            painter.fillRect(screen_x + 6, screen_y + 11, 29, 6, QColor(20, 15, 6))
            painter.fillRect(screen_x + 7, screen_y + 12, min(progress_w, 27), 4, QColor(234, 179, 8, 220))
            # Test onay tikleri
            if self._pulse_frame % 4 >= 2:
                painter.fillRect(screen_x + 6, screen_y + 5, 3, 3, QColor(74, 222, 128))
                painter.fillRect(screen_x + 12, screen_y + 5, 3, 3, QColor(74, 222, 128))

        elif state == AgentActivityState.ERROR:
            # Kırmızı alarm yanıp sönmesi
            err_glow = 240 if self._pulse_frame % 2 == 0 else 120
            painter.fillRect(screen_x, screen_y, screen_w, screen_h, QColor(239, 68, 68, err_glow))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(screen_x + 10, screen_y + 17, "ERR!")

        elif state == AgentActivityState.COFFEE_BREAK:
            # Kahve molası ekranı: Sıcak tonlar ve Zzz
            painter.fillRect(screen_x, screen_y, screen_w, screen_h, QColor(44, 28, 16))
            painter.fillRect(screen_x + 6, screen_y + 6, 16, 2, QColor(217, 119, 6, 160))
            painter.fillRect(screen_x + 6, screen_y + 11, 24, 2, QColor(245, 158, 11, 200))
            painter.setPen(QColor(254, 215, 170))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(screen_x + 6, screen_y + 22, "Mola Zzz")

        else:
            # IDLE: Dinlenmede koyu bekleme ekranı
            painter.fillRect(screen_x, screen_y, screen_w, screen_h, QColor(16, 20, 28))
            # Yanıp sönen bekleme imleci
            if self._pulse_frame % 4 < 2:
                painter.fillRect(screen_x + 4, screen_y + 5, 2, 3, QColor(71, 85, 105))

    def _draw_typing_and_hands(
        self,
        painter: QPainter,
        kb_x: int,
        kb_y: int,
        chair_x: int,
        chair_y: int,
        head_color: QColor,
        state: AgentActivityState,
    ):
        """Masa başında yazma, klavye aurası, tuş vuruşları, uçuşan sözdizimi kıvılcımları ve eller."""
        kb_w = 34
        kb_h = 14

        # 1. Mekanik Klavye Masaya Yansıyan Aydınlatma Aurası (Ambient Desk Underglow)
        if state == AgentActivityState.TYPING:
            glow_alpha = max(20, min(100, int(45 + 25 * math.sin(self._pulse_frame * 0.5))))
            painter.fillRect(kb_x - 4, kb_y - 2, kb_w + 8, kb_h + 6, QColor(34, 197, 94, glow_alpha))
            # Masa yüzeyinde parlayan ince LED yansıma çizgisi
            painter.fillRect(kb_x, kb_y + kb_h + 1, kb_w, 2, QColor(74, 222, 128, max(15, min(120, glow_alpha + 15))))

        # 2. Klavye Gövdesi (Mekanik Şasi & Plaka)
        painter.fillRect(kb_x, kb_y, kb_w, kb_h, QColor(20, 24, 32))
        painter.setPen(QPen(QColor(45, 55, 72), 1))
        painter.drawRect(kb_x, kb_y, kb_w, kb_h)
        # İç montaj plakası
        painter.fillRect(kb_x + 2, kb_y + 2, kb_w - 4, kb_h - 4, QColor(14, 18, 24))

        # 3. Klavye Tuş Matrisi (2 Satır Normal Tuş + 1 Satır Boşluk Çubuğu)
        for r in range(2):
            for c in range(5):
                kx = kb_x + 3 + c * 6
                ky = kb_y + 2 + r * 5
                # Pasif arka aydınlatmalı tuş kapakları (Hafif RGB soluma dalgası)
                if state == AgentActivityState.TYPING:
                    led_wave = int(12 * math.sin(self._pulse_frame * 0.4 + c * 0.8 + r))
                    key_base_col = QColor(30 + max(0, led_wave), 38 + max(0, led_wave * 2), 52 + max(0, led_wave))
                else:
                    key_base_col = QColor(32, 38, 50)
                painter.fillRect(kx, ky, 5, 3, key_base_col)

        # Satır 2: Spacebar ve Yan Tuşlar
        painter.fillRect(kb_x + 3, kb_y + 10, 5, 2, QColor(32, 38, 50))
        painter.fillRect(kb_x + 10, kb_y + 10, 14, 2, QColor(32, 38, 50))  # Uzun Spacebar
        painter.fillRect(kb_x + 26, kb_y + 10, 5, 2, QColor(32, 38, 50))

        hand_col = head_color.lighter(115)

        if state == AgentActivityState.TYPING:
            # -------------------------------------------------------------
            # Aktif Tuş Vuruşları & Mekanik Anahtar Parlamaları
            # -------------------------------------------------------------
            active_key_l = (self._pulse_frame * 2) % 5
            row_l = (self._pulse_frame // 3) % 2
            active_key_r = ((self._pulse_frame * 3 + 2) % 5)
            row_r = ((self._pulse_frame + 1) // 3) % 2

            if self._pulse_frame % 2 == 0:
                # Sol el tuşa basıyor: Tuş 1px aşağı iner, neon yeşil parlar
                kx_hit = kb_x + 3 + active_key_l * 6
                ky_hit = kb_y + 2 + row_l * 5 + 1
                painter.fillRect(kx_hit, ky_hit, 5, 3, QColor(74, 222, 128))
                painter.fillRect(kx_hit, ky_hit, 5, 1, QColor(187, 247, 208))  # Tuş parıltı ucu
                hand_l_y = kb_y + 3 + row_l
                hand_r_y = kb_y + 1
                hit_spark_x = kx_hit + 2
                hit_spark_y = ky_hit - 2
            else:
                # Sağ el tuşa basıyor: Tuş neon yeşil/cyan parlar
                kx_hit = kb_x + 3 + active_key_r * 6
                ky_hit = kb_y + 2 + row_r * 5 + 1
                painter.fillRect(kx_hit, ky_hit, 5, 3, QColor(74, 222, 128))
                painter.fillRect(kx_hit, ky_hit, 5, 1, QColor(187, 247, 208))
                hand_l_y = kb_y + 1
                hand_r_y = kb_y + 3 + row_r
                hit_spark_x = kx_hit + 2
                hit_spark_y = ky_hit - 2

            # Spacebar ara sıra parlar (Başparmak vuruşu)
            if self._pulse_frame % 4 == 0:
                painter.fillRect(kb_x + 10, kb_y + 10, 14, 2, QColor(56, 189, 248))
                painter.fillRect(kb_x + 12, kb_y + 10, 10, 1, QColor(186, 230, 253))

            # -------------------------------------------------------------
            # Sol ve Sağ Eller & Parmak Vurguları
            # -------------------------------------------------------------
            hand_l_x = kb_x + 4 + (self._pulse_frame % 2)
            hand_r_x = kb_x + 22 - (self._pulse_frame % 2)

            # Masa üzerine ellerin düşen mikro gölgesi
            painter.fillRect(hand_l_x, hand_l_y + 4, 6, 1, QColor(15, 20, 30, 140))
            painter.fillRect(hand_r_x, hand_r_y + 4, 6, 1, QColor(15, 20, 30, 140))

            # Sol el gövdesi ve parmak vurgusu
            painter.fillRect(hand_l_x, hand_l_y, 6, 4, hand_col)
            painter.fillRect(hand_l_x, hand_l_y, 6, 1, hand_col.lighter(130))  # Parmak ucu parıltısı
            painter.fillRect(hand_l_x, hand_l_y + 3, 6, 1, hand_col.darker(130))  # Bilek gölgesi

            # Sağ el gövdesi ve parmak vurgusu
            painter.fillRect(hand_r_x, hand_r_y, 6, 4, hand_col)
            painter.fillRect(hand_r_x, hand_r_y, 6, 1, hand_col.lighter(130))
            painter.fillRect(hand_r_x, hand_r_y + 3, 6, 1, hand_col.darker(130))

            # Kollardan sandalyeye bağlantı pikselleri ve önkol çizgisi
            painter.fillRect(chair_x + 3, chair_y + 2, 3, 4, hand_col.darker(130))
            painter.fillRect(chair_x + 26, chair_y + 2, 3, 4, hand_col.darker(130))
            painter.setPen(QPen(hand_col.darker(120), 1))
            painter.drawLine(chair_x + 4, chair_y + 3, hand_l_x + 1, hand_l_y + 1)
            painter.drawLine(chair_x + 27, chair_y + 3, hand_r_x + 4, hand_r_y + 1)

            # -------------------------------------------------------------
            # Tuş Vuruşu Anlık Mikro Kıvılcımı (Actuation Spark)
            # -------------------------------------------------------------
            painter.fillRect(hit_spark_x, max(0, hit_spark_y), 2, 2, QColor(255, 255, 255, 220))

            # -------------------------------------------------------------
            # Klavyeden Ekrana Yükselen Sözdizimi Kıvılcımları (Syntax Embers)
            # -------------------------------------------------------------
            sparks = [
                (kb_x + 6, 0, QColor(74, 222, 128)),    # String / Yeşil
                (kb_x + 14, 2, QColor(56, 189, 248)),   # Fonksiyon / Mavi
                (kb_x + 22, 4, QColor(134, 239, 172)),  # Değişken / Açık Yeşil
                (kb_x + 28, 1, QColor(253, 224, 71)),   # Sabit / Sarı
                (kb_x + 10, 3, QColor(192, 132, 252)),  # Anahtar Kelime / Lila
                (kb_x + 18, 5, QColor(244, 114, 182)),  # Operatör / Pembe
            ]
            for s_idx, (sx, p_offset, pcol) in enumerate(sparks):
                age = (self._pulse_frame * 3 + p_offset * 5) % 24
                sy = kb_y - age
                if sy > kb_y - 22:
                    sway = int(1.5 * math.sin((self._pulse_frame * 0.4) + s_idx))
                    alpha = max(0, min(255, 240 - age * 10))
                    painter.fillRect(sx + sway, sy, 2, 2, QColor(pcol.red(), pcol.green(), pcol.blue(), alpha))
                    # Çekirdek beyaz parlama
                    if age < 8:
                        painter.fillRect(sx + sway, sy, 1, 1, QColor(255, 255, 255, alpha))

        elif state == AgentActivityState.THINKING:
            # Düşünce Duruşu (Thinker Pose):
            # Sol el masada dinlenir, Sağ el çeneye dayanarak derin akıl yürütür!
            painter.fillRect(kb_x + 6, kb_y + 3, 6, 4, hand_col)
            # Çeneye dayalı sağ el
            chin_hand_x = chair_x + 18
            chin_hand_y = chair_y - 4
            painter.fillRect(chin_hand_x, chin_hand_y, 5, 5, hand_col)
            painter.fillRect(chin_hand_x + 1, chin_hand_y + 1, 3, 3, hand_col.lighter(120))
            # Kol dirsek kıvrımı
            painter.fillRect(chair_x + 24, chair_y + 2, 3, 6, hand_col.darker(130))

        elif state == AgentActivityState.READING:
            # Sol el masada notlara işaret eder, Sağ el mouse üzerindedir
            painter.fillRect(kb_x + 6, kb_y + 3, 6, 4, hand_col)
            # Mouse üzerinde sağ el
            pad_x = chair_x + 28
            painter.fillRect(pad_x, kb_y + 4, 6, 4, hand_col)

        elif state == AgentActivityState.COFFEE_BREAK:
            # Masada buharı tüten kahve kupası (Steaming Coffee Mug)
            cup_x = kb_x + 38
            cup_y = kb_y + 1
            painter.fillRect(cup_x, cup_y, 8, 10, QColor(241, 245, 249))
            painter.fillRect(cup_x + 1, cup_y + 1, 6, 2, QColor(120, 53, 15))
            painter.fillRect(cup_x + 8, cup_y + 2, 3, 5, QColor(203, 213, 225))
            # 3 Dalgalanan Buhar Pikselleri
            for i in range(3):
                steam_y = cup_y - 2 - ((self._pulse_frame * 2 + i * 4) % 10)
                steam_x = cup_x + 1 + i * 2 + (1 if (self._pulse_frame // 2) % 2 == 0 else -1)
                painter.fillRect(steam_x, steam_y, 2, 2, QColor(254, 215, 170, 160))

            # Eller rahat masada dinlenir
            painter.fillRect(kb_x + 8, kb_y + 3, 5, 4, hand_col)
            painter.fillRect(kb_x + 22, kb_y + 3, 5, 4, hand_col)

        else:
            # IDLE: Eller sandalyede/masada sakin durur
            painter.fillRect(kb_x + 8, kb_y + 3, 5, 4, hand_col)
            painter.fillRect(kb_x + 22, kb_y + 3, 5, 4, hand_col)

    def _draw_animated_bubble(
        self,
        painter: QPainter,
        x: int,
        y: int,
        w: int,
        h: int,
        head_cx: int,
        head_cy: int,
        persona: Optional[AgentPersona],
        state: AgentActivityState,
    ):
        """
        Organik 2D sinüzoidal süzülme, yükselen baloncuk zinciri, dalgalanan düşünce noktaları,
        dönen fikir parıltısı ve canlı aktivite animasyonlarını çizer.
        """
        # -----------------------------------------------------------------
        # Düşünce ve Durum Balonları Animasyonu (Floating, Trail & Waves)
        # -----------------------------------------------------------------
        if state in [
            AgentActivityState.THINKING,
            AgentActivityState.TYPING,
            AgentActivityState.READING,
            AgentActivityState.TESTING,
            AgentActivityState.ERROR,
            AgentActivityState.COFFEE_BREAK,
            AgentActivityState.TALKING,
        ] or (persona and getattr(persona, "active_speech_text", None)):

            speech_text = getattr(persona, "active_speech_text", None) if persona else None

            if state == AgentActivityState.THINKING and not speech_text:
                # =========================================================
                # ÖZEL ANİME DÜŞÜNCE BULUTU (Fluffy Retro Thought Cloud)
                # =========================================================
                # 1. Harmonik Ağırlıksız Süzülme ve Salınım (Sin/Cos Float)
                bob_y = int(3.5 * math.sin(self._pulse_frame * 0.35))
                drift_x = int(1.5 * math.cos(self._pulse_frame * 0.25))

                bubble_w = 44
                bubble_h = 28
                bubble_x = x + w - 50 + drift_x
                bubble_y = y - 14 + bob_y

                # 2. Baştan Yükselen 4 Harmonik Düşünce Baloncuğu
                b1_ox = int(1.2 * math.sin(self._pulse_frame * 0.4))
                b1_oy = int(1.2 * math.cos(self._pulse_frame * 0.4))
                b1_x = head_cx + 4 + b1_ox
                b1_y = head_cy - 4 + b1_oy + (bob_y // 2)

                b2_ox = int(1.8 * math.sin((self._pulse_frame + 2) * 0.4))
                b2_oy = int(1.8 * math.cos((self._pulse_frame + 2) * 0.4))
                b2_x = head_cx + 10 + b2_ox
                b2_y = head_cy - 11 + b2_oy + (bob_y // 2)

                b3_ox = int(2.2 * math.sin((self._pulse_frame + 4) * 0.4))
                b3_oy = int(2.2 * math.cos((self._pulse_frame + 4) * 0.4))
                b3_x = head_cx + 17 + b3_ox
                b3_y = head_cy - 18 + b3_oy + bob_y

                b4_ox = int(1.5 * math.sin((self._pulse_frame + 6) * 0.4))
                b4_oy = int(1.5 * math.cos((self._pulse_frame + 6) * 0.4))
                b4_x = head_cx + 24 + b4_ox
                b4_y = head_cy - 24 + b4_oy + bob_y

                painter.setPen(QPen(QColor(192, 132, 252, 230), 1))
                painter.setBrush(QBrush(QColor(26, 18, 44, 245)))
                painter.drawEllipse(b1_x, b1_y, 4, 4)
                painter.drawEllipse(b2_x, b2_y, 6, 6)
                painter.drawEllipse(b3_x, b3_y, 8, 8)
                painter.drawEllipse(b4_x, b4_y, 5, 5)

                # Baloncukların üzerinde cam parıltısı (Specular Highlights)
                painter.fillRect(b1_x + 1, b1_y + 1, 1, 1, QColor(255, 255, 255, 220))
                painter.fillRect(b2_x + 1, b2_y + 1, 2, 1, QColor(255, 255, 255, 220))
                painter.fillRect(b3_x + 2, b3_y + 2, 2, 1, QColor(255, 255, 255, 220))
                painter.fillRect(b4_x + 1, b4_y + 1, 1, 1, QColor(255, 255, 255, 220))

                # Yükselen sürekli nöral akış kıvılcımı
                stream_prog = (self._pulse_frame % 8) / 8.0
                st_x = int(b1_x + stream_prog * (b4_x - b1_x))
                st_y = int(b1_y + stream_prog * (b4_y - b1_y))
                painter.fillRect(st_x, st_y, 2, 2, QColor(245, 208, 254, 220))

                # 3. Bulut Morfolojisi ve Nefes Alma Genişlemesi (Breathing Lobes)
                breath = 1 if (self._pulse_frame % 8 in (2, 3, 4)) else 0

                # Dış Kozmik Mor Aura (Pulsing Corona)
                aura_alpha = max(20, min(100, int(60 + 35 * math.sin(self._pulse_frame * 0.4))))
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(168, 85, 247, aura_alpha)))
                painter.drawRoundedRect(bubble_x - 3 - breath, bubble_y - 4 - breath, bubble_w + 6 + breath * 2, bubble_h + 8 + breath * 2, 10, 10)

                # Bulut Çekirdeği ve Puf Küreleri
                cloud_core = QColor(26, 18, 44, 245)
                cloud_pen = QPen(QColor(192, 132, 252, 230), 1.5)
                painter.setPen(cloud_pen)
                painter.setBrush(QBrush(cloud_core))

                # Ana gövde ve kabarık tepe/yan puf lobları
                painter.drawRoundedRect(bubble_x + 3, bubble_y + 3, bubble_w - 6, bubble_h - 6, 8, 8)
                painter.drawEllipse(bubble_x + 6, bubble_y - 3 - breath, 15, 14)
                painter.drawEllipse(bubble_x + bubble_w - 21, bubble_y - 4 - breath, 16, 15)
                painter.drawEllipse(bubble_x - 2 - breath, bubble_y + 5, 14, bubble_h - 10)
                painter.drawEllipse(bubble_x + bubble_w - 12, bubble_y + 5, 14 + breath, bubble_h - 10)

                # Üst hatlarda parıldama çizgisi (Specular Sheen)
                sheen_pen = QPen(QColor(233, 213, 255, 190), 1)
                painter.setPen(sheen_pen)
                painter.drawLine(bubble_x + 10, bubble_y - 2 - breath, bubble_x + 17, bubble_y - 2 - breath)
                painter.drawLine(bubble_x + bubble_w - 18, bubble_y - 3 - breath, bubble_x + bubble_w - 11, bubble_y - 3 - breath)

                # 4. Bulut İçi Dinamik Düşünce Görselleri
                # A. 3 Harmonik Sinüs Düşünce Düğümü (Quantum Thought Nodes)
                node_pts = []
                for i in range(3):
                    nx = bubble_x + 11 + i * 11
                    wave_off = int(3.2 * math.sin((self._pulse_frame * 0.65) + i * 1.3))
                    ny = bubble_y + 12 + wave_off
                    is_peak = (wave_off < -1)
                    node_pts.append((nx, ny, is_peak))

                # Düğümler arası sinaptik bağlantı iplikleri
                painter.setPen(QPen(QColor(168, 85, 247, 140), 1))
                painter.drawLine(node_pts[0][0] + 2, node_pts[0][1] + 2, node_pts[1][0] + 2, node_pts[1][1] + 2)
                painter.drawLine(node_pts[1][0] + 2, node_pts[1][1] + 2, node_pts[2][0] + 2, node_pts[2][0] + 2)

                # İplikler üzerinde kayan sinaptik enerji kıvılcımı
                sp_frac = (self._pulse_frame % 6) / 6.0
                if sp_frac < 0.5:
                    sx = int(node_pts[0][0] + (sp_frac * 2) * (node_pts[1][0] - node_pts[0][0]))
                    sy = int(node_pts[0][1] + (sp_frac * 2) * (node_pts[1][1] - node_pts[0][1]))
                else:
                    sx = int(node_pts[1][0] + ((sp_frac - 0.5) * 2) * (node_pts[2][0] - node_pts[1][0]))
                    sy = int(node_pts[1][1] + ((sp_frac - 0.5) * 2) * (node_pts[2][1] - node_pts[1][1]))
                painter.fillRect(sx, sy, 2, 2, QColor(254, 240, 138, 240))

                # 3 Düğümün Çizimi
                for nx, ny, is_peak in node_pts:
                    painter.fillRect(nx, ny, 5, 5, QColor(192, 132, 252, 220 if is_peak else 140))
                    painter.fillRect(nx + 1, ny + 1, 3, 3, QColor(255, 255, 255) if is_peak else QColor(233, 213, 255))

                # B. Sağ Üstte Parlayan Fikir Yıldızı / Eureka Kıvılcımı (✦)
                sp_cx = bubble_x + bubble_w - 9
                sp_cy = bubble_y + 6
                sparkle_ph = self._pulse_frame % 4
                if sparkle_ph == 0:
                    painter.fillRect(sp_cx, sp_cy, 2, 2, QColor(253, 224, 71))
                elif sparkle_ph == 1:
                    painter.fillRect(sp_cx, sp_cy, 2, 2, QColor(254, 240, 138))
                    painter.fillRect(sp_cx - 1, sp_cy, 4, 1, QColor(254, 240, 138, 180))
                    painter.fillRect(sp_cx, sp_cy - 1, 1, 4, QColor(254, 240, 138, 180))
                elif sparkle_ph == 2:
                    painter.fillRect(sp_cx, sp_cy, 2, 2, QColor(255, 255, 255))
                    painter.fillRect(sp_cx - 2, sp_cy, 6, 1, QColor(254, 240, 138, 160))
                    painter.fillRect(sp_cx, sp_cy - 2, 1, 6, QColor(254, 240, 138, 160))
                else:
                    painter.fillRect(sp_cx, sp_cy, 2, 2, QColor(245, 158, 11, 160))

                # C. Alt Kısımda Mikro Nöral EEG Beyin Dalgası
                painter.setPen(QPen(QColor(168, 85, 247, 90), 1))
                for px in range(bubble_x + 9, bubble_x + bubble_w - 9, 2):
                    eeg_y = bubble_y + bubble_h - 7 + int(1.5 * math.sin((px * 0.4) + (self._pulse_frame * 0.5)))
                    painter.drawPoint(px, eeg_y)

                # D. Yüzen Nöral Düşünce Tozları (Floating Idea Particles)
                for d_idx in range(3):
                    dust_ox = int(7 * math.sin(self._pulse_frame * 0.25 + d_idx * 2.1))
                    dust_oy = int(4 * math.cos(self._pulse_frame * 0.3 + d_idx * 1.7))
                    d_x = bubble_x + 18 + dust_ox
                    d_y = bubble_y + 14 + dust_oy
                    painter.fillRect(d_x, d_y, 1, 1, QColor(216, 180, 254, 180))

            else:
                # =========================================================
                # DİĞER DURUMLAR VE KONUŞMA BALONU (Speech & Status Bubble)
                # =========================================================
                bob_offsets = [0, -1, -2, -3, -4, -3, -2, -1, 0, 1]
                bob_y = bob_offsets[self._pulse_frame % len(bob_offsets)]

                bubble_x = x + w - 46
                bubble_y = y - 12 + bob_y
                bubble_w = 36
                bubble_h = 26

                if state == AgentActivityState.TYPING:
                    border_color = QColor(34, 197, 94, 210 if self._pulse_frame % 2 == 0 else 160)
                    bg_color = QColor(16, 32, 22, 235)
                elif state == AgentActivityState.READING:
                    border_color = QColor(56, 189, 248, 190)
                    bg_color = QColor(14, 28, 44, 235)
                elif state == AgentActivityState.TESTING:
                    border_color = QColor(234, 179, 8, 200)
                    bg_color = QColor(36, 28, 14, 235)
                elif state == AgentActivityState.COFFEE_BREAK:
                    border_color = QColor(245, 158, 11, 200)
                    bg_color = QColor(44, 28, 16, 240)
                elif state == AgentActivityState.TALKING or speech_text:
                    border_color = QColor(56, 189, 248, 220)
                    bg_color = QColor(15, 23, 42, 240)
                else:  # ERROR
                    border_color = QColor(239, 68, 68, 240 if self._pulse_frame % 2 == 0 else 140)
                    bg_color = QColor(44, 16, 16, 240)

                if speech_text:
                    bubble_w = max(50, min(130, len(speech_text) * 6 + 14))
                    bubble_x = max(10, x + w - bubble_w - 4)

                # Konuşma balonu ucu (Pointer Notch)
                tail_pts = [
                    QPoint(bubble_x + 4, bubble_y + bubble_h - 2),
                    QPoint(head_cx + 12, head_cy - 6 + (bob_y // 2)),
                    QPoint(bubble_x + 12, bubble_y + bubble_h),
                ]
                painter.setPen(QPen(border_color, 1))
                painter.setBrush(QBrush(bg_color))
                painter.drawPolygon(tail_pts)

                painter.setPen(QPen(border_color, 1.5))
                painter.setBrush(QBrush(bg_color))
                painter.drawRoundedRect(bubble_x, bubble_y, bubble_w, bubble_h, 7, 7)

                if speech_text:
                    painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
                    painter.setPen(QColor(241, 245, 249))
                    painter.drawText(bubble_x + 5, bubble_y + 17, speech_text[:18])
                    if self._pulse_frame % 2 == 0:
                        tw_x = bubble_x + 6 + min(18, len(speech_text)) * 5
                        painter.fillRect(tw_x, bubble_y + 9, 2, 9, QColor(56, 189, 248))

                elif state == AgentActivityState.COFFEE_BREAK:
                    font_b = QFont("Segoe UI Emoji", 9)
                    painter.setFont(font_b)
                    painter.setPen(QColor(254, 215, 170))
                    painter.drawText(bubble_x + 5, bubble_y + 18, "☕ Mola")

                elif state == AgentActivityState.TYPING:
                    font_b = QFont("Segoe UI Emoji", 10)
                    painter.setFont(font_b)
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(bubble_x + 3, bubble_y + 18, "⌨️")

                    cur_x = bubble_x + 22
                    cur_y = bubble_y + 15
                    if self._pulse_frame % 2 == 0:
                        painter.fillRect(cur_x, cur_y, 5, 2, QColor(74, 222, 128))
                    else:
                        painter.fillRect(cur_x, cur_y - 2, 2, 5, QColor(74, 222, 128))

                elif state == AgentActivityState.READING:
                    font_b = QFont("Segoe UI Emoji", 10)
                    painter.setFont(font_b)
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(bubble_x + 9, bubble_y + 18, "📖")

                elif state == AgentActivityState.TESTING:
                    font_b = QFont("Segoe UI Emoji", 10)
                    painter.setFont(font_b)
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(bubble_x + 9, bubble_y + 18, "🧪")

                elif state == AgentActivityState.ERROR:
                    font_b = QFont("Segoe UI Emoji", 10)
                    painter.setFont(font_b)
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(bubble_x + 9, bubble_y + 18, "⚠️")

                    # Köşelerde yanıp sönen kırmızı alarm pikselleri
                    if self._pulse_frame % 2 == 0:
                        painter.fillRect(bubble_x + 4, bubble_y + 4, 3, 3, QColor(239, 68, 68))
                        painter.fillRect(bubble_x + bubble_w - 7, bubble_y + 4, 3, 3, QColor(239, 68, 68))
