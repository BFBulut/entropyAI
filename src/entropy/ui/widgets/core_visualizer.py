"""Core Visualizer Widget: An animated, pulsing energy sphere reflecting AI cognitive state."""

import math
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QRadialGradient, QPen
from PySide6.QtWidgets import QWidget

from entropy.core.event_bus import bus

class CoreVisualizerWidget(QWidget):
    """
    Renders an animated glowing core that pulses in real-time as tokens stream
    (enforcing RULE: agent-ui-routing).
    """

    def __init__(self, parent=None, radius: int = 48):
        super().__init__(parent)
        self.base_radius = radius
        self.current_radius = float(radius)
        self.target_radius = float(radius)
        self.pulse_phase = 0.0
        self.pulse_speed = 0.04
        self.glow_color = QColor(0, 240, 255) # Neon Cyan
        self.core_color = QColor(14, 20, 32)
        self.state = "idle" # idle, thinking, executing, error

        self.setMinimumSize(radius * 3, radius * 3)

        # 60 FPS animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate_frame)
        self.timer.start(16)

        # Hook into Event Bus
        bus.core_pulse_triggered.connect(self.trigger_pulse)
        bus.core_state_changed.connect(self.set_state)

    def set_state(self, new_state: str):
        self.state = new_state
        if new_state == "thinking":
            self.glow_color = QColor(0, 240, 255, 230)
            self.pulse_speed = 0.12
        elif new_state == "executing":
            self.glow_color = QColor(0, 255, 157, 230) # Emerald
            self.pulse_speed = 0.18
        elif new_state == "error":
            self.glow_color = QColor(255, 60, 60, 230)
            self.pulse_speed = 0.08
        else: # idle
            self.glow_color = QColor(0, 240, 255, 160)
            self.pulse_speed = 0.03

    def trigger_pulse(self, intensity: float = 0.8):
        """Immediately trigger a bright expansion pulse upon receiving a token chunk."""
        expansion = self.base_radius * 0.3 * min(1.0, max(0.2, intensity))
        self.target_radius = self.base_radius + expansion

    def _animate_frame(self):
        self.pulse_phase += self.pulse_speed
        if self.pulse_phase > 2 * math.pi:
            self.pulse_phase -= 2 * math.pi

        # Breathing wave
        ambient_wave = math.sin(self.pulse_phase) * (self.base_radius * 0.08)
        self.current_radius += (self.target_radius + ambient_wave - self.current_radius) * 0.15

        # Decay target back to base radius
        self.target_radius += (self.base_radius - self.target_radius) * 0.1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        r = max(10.0, self.current_radius)

        # Outer Soft Glow
        outer_gradient = QRadialGradient(center, r * 1.8)
        outer_gradient.setColorAt(0.0, self.glow_color)
        c_trans = QColor(self.glow_color)
        c_trans.setAlpha(0)
        outer_gradient.setColorAt(1.0, c_trans)

        painter.setBrush(QBrush(outer_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, r * 1.8, r * 1.8)

        # Concentric Energy Rings
        pen = QPen(self.glow_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, r * 1.2, r * 1.2)

        # Solid Inner Core
        inner_gradient = QRadialGradient(center, r)
        inner_gradient.setColorAt(0.0, QColor(0, 240, 255, 200))
        inner_gradient.setColorAt(0.6, self.core_color)
        inner_gradient.setColorAt(1.0, QColor(5, 7, 10))

        painter.setBrush(QBrush(inner_gradient))
        painter.setPen(QPen(self.glow_color, 1.5))
        painter.drawEllipse(center, r * 0.85, r * 0.85)

        # Glyphic Core Center Mark
        painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
        painter.drawEllipse(center, r * 0.18, r * 0.18)
        painter.end()
