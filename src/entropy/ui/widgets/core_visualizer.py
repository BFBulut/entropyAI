"""Core Visualizer Widget: durum farkındalıklı, yumuşak geçişli organik siber çekirdek.

Durumlar (idle / thinking / executing / error) arasında renk ve enerji yumuşak
geçer; düşünürken dışa açılan halka dalgaları, yürütürken yörüngede parçacık
akışı, hatada kısa titreme ve kırmızı nabız gösterilir.

Performans: etkin durumda en fazla ~30 fps, boşta ~10 fps'e düşer; pencere
görünmezken hiç boyanmaz. Böylece masaüstünde sürekli açık duran çekirdek CPU
yormaz.
"""

import math
import random
from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QPainter, QRadialGradient, QPen
from PySide6.QtWidgets import QMenu, QWidget

from entropy.core.event_bus import bus

# Kare aralıkları (ms). 33 ms ≈ 30 fps üst sınırı, 100 ms ≈ 10 fps boşta.
ACTIVE_FRAME_MS = 33
IDLE_FRAME_MS = 100

# Durum -> (birincil parıltı, ikincil parıltı) RGB
STATE_PALETTE = {
    "idle": ((0, 240, 255), (0, 255, 157)),
    "thinking": ((0, 240, 255), (157, 0, 255)),
    "executing": ((0, 255, 157), (0, 240, 255)),
    "error": ((255, 75, 75), (255, 179, 0)),
}

# Üzerine gelince gösterilen durum ipucu
STATE_HINTS = {
    "idle": "Entropy AI · Boşta (hazır)",
    "thinking": "Entropy AI · Düşünüyor",
    "executing": "Entropy AI · Yürütülüyor",
    "error": "Entropy AI · Hata",
}


def _lerp_color(current: QColor, target: QColor, t: float) -> QColor:
    """İki rengi t oranında karıştırır (yumuşak durum geçişi)."""
    return QColor(
        int(current.red() + (target.red() - current.red()) * t),
        int(current.green() + (target.green() - current.green()) * t),
        int(current.blue() + (target.blue() - current.blue()) * t),
    )


class CoreVisualizerWidget(QWidget):
    """
    Token akışına ve ajan durumuna gerçek zamanlı tepki veren organik çekirdek
    (RULE: agent-ui-routing).
    """

    def __init__(self, parent=None, base_radius: int = 44, radius: int = None,
                 mode_menu_enabled: bool = False):
        super().__init__(parent)
        r = radius if radius is not None else base_radius
        self.base_radius = float(r)
        self.requested_base_radius = float(r)
        self.target_radius = float(r)
        self.pulse_phase = 0.0
        self.orbital_phase = 0.0
        self.pulse_intensity = 0.0
        self.state = "idle"  # idle, thinking, executing, error

        self.glow_color = QColor(0, 240, 255)       # Neon Cyan
        self.secondary_glow = QColor(0, 255, 157)   # Emerald
        self.core_color = QColor(14, 20, 32)
        self._target_glow = QColor(self.glow_color)
        self._target_secondary = QColor(self.secondary_glow)

        # Düşünme halka dalgaları: her biri 0.0 -> 1.0 ilerleyen bir yarıçap oranı
        self._ripples: list[float] = []
        self._ripple_cooldown = 0

        # Yürütme parçacıkları: yörüngede akan enerji noktaları
        self._particles: list[dict] = []

        # Hata titremesi: kalan kare sayısı
        self._shake_frames = 0
        self._error_pulse = 0.0

        # Tıklayınca mod menüsü. Floating modda çekirdek sürüklenebilir olduğu için
        # varsayılan kapalı; pencere kendi tıklama/sürükleme ayrımını yapar.
        self.mode_menu_enabled = mode_menu_enabled

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(160, 160)
        self.setToolTip(STATE_HINTS["idle"])

        self._frame_interval = ACTIVE_FRAME_MS
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate_frame)
        self.timer.start(self._frame_interval)

        # Event bus (bound method: widget silinince Qt bağlantıyı kendiliğinden koparır)
        bus.core_pulse_triggered.connect(self.trigger_pulse)
        bus.core_state_changed.connect(self.set_state)

    # ------------------------------------------------------------------ durum

    def set_state(self, new_state: str):
        """Durumu değiştirir; renkler hedefe doğru yumuşak geçer."""
        normalized = new_state if new_state in STATE_PALETTE else "idle"
        previous = self.state
        self.state = normalized

        primary, secondary = STATE_PALETTE[normalized]
        self._target_glow = QColor(*primary)
        self._target_secondary = QColor(*secondary)

        if normalized == "error" and previous != "error":
            self._shake_frames = 18
            self._error_pulse = 1.0
        if normalized == "executing":
            if not self._particles:
                self._spawn_particles()
        else:
            self._particles.clear()
        if normalized != "thinking":
            self._ripple_cooldown = 0

        self.setToolTip(STATE_HINTS[normalized])
        self._apply_frame_rate()

    def trigger_pulse(self, intensity: float = 0.8):
        """Token geldiğinde anlık enerji patlaması."""
        self.pulse_intensity = min(1.0, self.pulse_intensity + intensity)
        expansion = self.base_radius * 0.3 * min(1.0, max(0.2, intensity))
        self.target_radius = self.base_radius + expansion
        self._apply_frame_rate()

    # -------------------------------------------------------------- animasyon

    def is_active(self) -> bool:
        """Yüksek kare hızı gerektiren bir hareket var mı?"""
        return bool(
            self.state != "idle"
            or self.pulse_intensity > 0.02
            or self._ripples
            or self._particles
            or self._shake_frames > 0
        )

    def _apply_frame_rate(self):
        """Boşta kare hızını düşürerek CPU tüketimini kırar."""
        desired = ACTIVE_FRAME_MS if self.is_active() else IDLE_FRAME_MS
        if desired != self._frame_interval:
            self._frame_interval = desired
            if self.timer.isActive():
                self.timer.setInterval(desired)

    def _spawn_particles(self, count: int = 10):
        for _ in range(count):
            self._particles.append({
                "angle": random.uniform(0.0, 2 * math.pi),
                "orbit": random.uniform(1.15, 1.75),
                "speed": random.uniform(0.035, 0.085),
                "size": random.uniform(1.4, 2.8),
            })

    def _animate_frame(self):
        # Renk geçişi
        self.glow_color = _lerp_color(self.glow_color, self._target_glow, 0.18)
        self.secondary_glow = _lerp_color(self.secondary_glow, self._target_secondary, 0.18)

        speed = 0.12 if self.state == "thinking" else 0.05
        self.pulse_phase += speed
        if self.pulse_phase > 2 * math.pi:
            self.pulse_phase -= 2 * math.pi

        self.orbital_phase += 0.04
        if self.orbital_phase > 2 * math.pi:
            self.orbital_phase -= 2 * math.pi

        # Düşünürken periyodik halka dalgası doğur
        if self.state == "thinking":
            self._ripple_cooldown -= 1
            if self._ripple_cooldown <= 0:
                self._ripples.append(0.0)
                self._ripple_cooldown = 12
        self._ripples = [r + 0.045 for r in self._ripples if r + 0.045 < 1.0]

        # Yürütürken parçacık akışı
        for p in self._particles:
            p["angle"] += p["speed"]
            if p["angle"] > 2 * math.pi:
                p["angle"] -= 2 * math.pi

        # Hata titremesi ve kırmızı nabız
        if self._shake_frames > 0:
            self._shake_frames -= 1
        self._error_pulse *= 0.90 if self.state == "error" else 0.75
        if self.state == "error" and self._error_pulse < 0.25:
            self._error_pulse = 1.0

        self.pulse_intensity *= 0.92
        self._apply_frame_rate()

        # Gizliyken boyama isteme (CPU tasarrufu); durum yine ilerler.
        if self.isVisible():
            self.update()

    def _shake_offset(self) -> float:
        if self._shake_frames <= 0:
            return 0.0
        return math.sin(self._shake_frames * 1.7) * (self._shake_frames * 0.35)

    # ------------------------------------------------------------ etkileşim

    def mousePressEvent(self, event):
        """Tıklayınca mod menüsü (yalnızca menü etkinken; aksi halde ebeveyne devreder)."""
        if not self.mode_menu_enabled or event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            super().mousePressEvent(event)
            return
        self.show_mode_menu(event.globalPosition().toPoint())
        event.accept()

    def build_mode_menu(self) -> QMenu:
        """Mod geçiş menüsü; test edilebilir olması için ayrı kurulur."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color:#0E1420; color:#F0F6FC; border:1px solid #1F2B42;"
            " border-radius:6px; padding:4px; }"
            "QMenu::item:selected { background-color:#1A263C; color:#00F0FF; }"
        )
        for label, mode in (
            ("🧘 Zen Moda Geç", "zen"),
            ("💬 Chat Modunu Aç", "chat"),
            ("◎ Floating Moda Geç", "floating"),
        ):
            act = QAction(label, menu)
            act.setData(mode)
            act.triggered.connect(self._on_mode_action)
            menu.addAction(act)
        return menu

    def _on_mode_action(self):
        act = self.sender()
        mode = act.data() if act is not None else None
        if mode:
            bus.mode_requested.emit(mode)

    def show_mode_menu(self, global_pos):
        menu = self.build_mode_menu()
        menu.exec(global_pos)

    # --------------------------------------------------------------- çizim

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        shake = self._shake_offset()
        center = QPointF(w / 2.0 + shake, h / 2.0)

        # Parıltı hiçbir zaman widget sınırını aşmamalı (kare kutu kırpması olmasın)
        max_safe_radius = (min(w, h) / 2.0) - 8.0
        if max_safe_radius <= 10.0:
            painter.end()
            return

        base_r = min(self.requested_base_radius, max_safe_radius * 0.45)
        error_boost = base_r * 0.10 * self._error_pulse if self.state == "error" else 0.0
        pulse_expansion = base_r * 0.35 * self.pulse_intensity
        wave = math.sin(self.pulse_phase) * (base_r * 0.08)
        current_r = base_r + pulse_expansion + wave + error_boost

        outer_aura_r = min(max_safe_radius, current_r * 2.1)

        # 1. Yumuşak ortam parıltısı
        aura_grad = QRadialGradient(center, outer_aura_r)
        c1 = QColor(self.glow_color)
        c1.setAlpha(int(80 + 120 * self.pulse_intensity))
        aura_grad.setColorAt(0.0, c1)

        c2 = QColor(self.secondary_glow)
        c2.setAlpha(int(30 + 60 * self.pulse_intensity))
        aura_grad.setColorAt(0.45, c2)

        c_edge = QColor(self.glow_color)
        c_edge.setAlpha(0)
        aura_grad.setColorAt(1.0, c_edge)

        painter.setBrush(QBrush(aura_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, outer_aura_r, outer_aura_r)

        # 2. Yörünge halkaları
        for i, mult in enumerate([1.35, 1.65]):
            ring_r = min(max_safe_radius - 4.0, current_r * mult)
            ring_pen = QPen()
            ring_color = QColor(self.glow_color if i == 0 else self.secondary_glow)
            alpha = int((30 + 40 * math.sin(self.pulse_phase + i)) * (1.0 + self.pulse_intensity))
            ring_color.setAlpha(min(220, max(20, alpha)))
            ring_pen.setColor(ring_color)
            ring_pen.setWidthF(1.2)
            ring_pen.setStyle(Qt.PenStyle.DashLine if i == 1 else Qt.PenStyle.SolidLine)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, ring_r, ring_r)

        # 2b. Düşünme dalgaları: dışa açılıp sönen halkalar
        for progress in self._ripples:
            ripple_r = current_r + (max_safe_radius - current_r) * progress
            if ripple_r <= 0:
                continue
            rc = QColor(self.secondary_glow)
            rc.setAlpha(int(150 * (1.0 - progress)))
            pen = QPen(rc)
            pen.setWidthF(1.6)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, ripple_r, ripple_r)

        # 3. İç küre
        inner_grad = QRadialGradient(center, current_r)
        inner_grad.setColorAt(0.0, QColor(self.glow_color.red(), self.glow_color.green(), self.glow_color.blue(), 240))
        inner_grad.setColorAt(0.5, self.core_color)
        inner_grad.setColorAt(0.95, QColor(4, 7, 12, 250))
        inner_grad.setColorAt(1.0, QColor(self.glow_color.red(), self.glow_color.green(), self.glow_color.blue(), 180))

        painter.setBrush(QBrush(inner_grad))
        painter.setPen(QPen(self.glow_color, 1.8))
        painter.drawEllipse(center, current_r, current_r)

        # 3b. Yürütme parçacık akışı
        if self._particles:
            painter.setPen(Qt.PenStyle.NoPen)
            for p in self._particles:
                orbit_r = min(max_safe_radius - 2.0, current_r * p["orbit"])
                px = center.x() + math.cos(p["angle"]) * orbit_r
                py = center.y() + math.sin(p["angle"]) * orbit_r
                pc = QColor(self.secondary_glow)
                pc.setAlpha(200)
                painter.setBrush(QBrush(pc))
                painter.drawEllipse(QPointF(px, py), p["size"], p["size"])

        # 4. Merkezî tekillik
        singularity_r = max(4.0, current_r * 0.22)
        node_grad = QRadialGradient(center, singularity_r)
        node_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        node_grad.setColorAt(0.5, QColor(self.glow_color.red(), self.glow_color.green(), self.glow_color.blue(), 220))
        node_grad.setColorAt(1.0, QColor(self.glow_color.red(), self.glow_color.green(), self.glow_color.blue(), 0))

        painter.setBrush(QBrush(node_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, singularity_r, singularity_r)

        painter.end()

    def hideEvent(self, event):
        # Gizliyken timer'ı boşta hızına çek (masaüstü modunda gereksiz uyanma olmasın)
        self._frame_interval = IDLE_FRAME_MS
        if self.timer.isActive():
            self.timer.setInterval(IDLE_FRAME_MS)
        super().hideEvent(event)

    def showEvent(self, event):
        self._apply_frame_rate()
        super().showEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        try:
            bus.core_pulse_triggered.disconnect(self.trigger_pulse)
            bus.core_state_changed.disconnect(self.set_state)
        except Exception:
            pass
        super().closeEvent(event)
