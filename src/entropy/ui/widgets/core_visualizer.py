"""Core Visualizer Widget: An organic, animated glowing cyber-orb with dynamic breathing and particle aura."""

import math
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QRadialGradient, QPen
from PySide6.QtWidgets import QWidget

from entropy.core.event_bus import bus

class CoreVisualizerWidget(QWidget):
    """
    Renders an organic, unclipped pulsing cyber core that reacts to token stream chunks
    in real-time (enforcing RULE: agent-ui-routing).
    """

    def __init__(self, parent=None, base_radius: int = 44, radius: int = None):
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

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(160, 160)

        # 60 FPS Animation Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate_frame)
        self.timer.start(16)

        # Connect to Event Bus
        bus.core_pulse_triggered.connect(self.trigger_pulse)
        bus.core_state_changed.connect(self.set_state)

    def set_state(self, new_state: str):
        self.state = new_state
        if new_state == "thinking":
            self.glow_color = QColor(0, 240, 255)
            self.secondary_glow = QColor(157, 0, 255) # Purple surge
        elif new_state == "executing":
            self.glow_color = QColor(0, 255, 157)     # Emerald
            self.secondary_glow = QColor(0, 240, 255)
        elif new_state == "error":
            self.glow_color = QColor(255, 75, 75)
            self.secondary_glow = QColor(255, 179, 0)
        else: # idle
            self.glow_color = QColor(0, 240, 255)
            self.secondary_glow = QColor(0, 255, 157)

    def trigger_pulse(self, intensity: float = 0.8):
        """Trigger an instant energy burst upon token reception."""
        self.pulse_intensity = min(1.0, self.pulse_intensity + intensity)
        expansion = self.base_radius * 0.3 * min(1.0, max(0.2, intensity))
        self.target_radius = self.base_radius + expansion

    def _animate_frame(self):
        speed = 0.12 if self.state == "thinking" else 0.04
        self.pulse_phase += speed
        if self.pulse_phase > 2 * math.pi:
            self.pulse_phase -= 2 * math.pi

        self.orbital_phase += 0.03
        if self.orbital_phase > 2 * math.pi:
            self.orbital_phase -= 2 * math.pi

        # Decay pulse intensity smoothly
        self.pulse_intensity *= 0.92
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        center = QPointF(w / 2.0, h / 2.0)

        # Ensure glow NEVER exceeds widget bounds to prevent square box clipping
        max_safe_radius = (min(w, h) / 2.0) - 8.0
        if max_safe_radius <= 10.0:
            return

        # Base radius adapts to container size
        base_r = min(self.requested_base_radius, max_safe_radius * 0.45)
        pulse_expansion = base_r * 0.35 * self.pulse_intensity
        wave = math.sin(self.pulse_phase) * (base_r * 0.08)
        current_r = base_r + pulse_expansion + wave

        # Outermost aura radius strictly clamped inside widget
        outer_aura_r = min(max_safe_radius, current_r * 2.1)

        # 1. Soft Ambient Radial Glow (Fades to 0 well before edges)
        aura_grad = QRadialGradient(center, outer_aura_r)
        c1 = QColor(self.glow_color)
        c1.setAlpha(int(80 + 120 * self.pulse_intensity))
        aura_grad.setColorAt(0.0, c1)

        c2 = QColor(self.secondary_glow)
        c2.setAlpha(int(30 + 60 * self.pulse_intensity))
        aura_grad.setColorAt(0.45, c2)

        c_edge = QColor(self.glow_color)
        c_edge.setAlpha(0) # Absolutely transparent at edge
        aura_grad.setColorAt(1.0, c_edge)

        painter.setBrush(QBrush(aura_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, outer_aura_r, outer_aura_r)

        # 2. Orbital Energy Wave Rings (Floating particle rings)
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

        # 3. Inner Solid Cyber Sphere
        inner_grad = QRadialGradient(center, current_r)
        inner_grad.setColorAt(0.0, QColor(0, 240, 255, 240))
        inner_grad.setColorAt(0.5, self.core_color)
        inner_grad.setColorAt(0.95, QColor(4, 7, 12, 250))
        inner_grad.setColorAt(1.0, QColor(0, 240, 255, 180))

        painter.setBrush(QBrush(inner_grad))
        painter.setPen(QPen(self.glow_color, 1.8))
        painter.drawEllipse(center, current_r, current_r)

        # 4. Central Singularity Node
        singularity_r = max(4.0, current_r * 0.22)
        node_grad = QRadialGradient(center, singularity_r)
        node_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        node_grad.setColorAt(0.5, QColor(0, 240, 255, 220))
        node_grad.setColorAt(1.0, QColor(0, 240, 255, 0))

        painter.setBrush(QBrush(node_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, singularity_r, singularity_r)

        painter.end()
