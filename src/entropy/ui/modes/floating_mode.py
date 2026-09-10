"""Floating Mode: Minimalist ambient floating AI core widget."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QMenu, QVBoxLayout, QWidget

from entropy.core.event_bus import bus
from entropy.ui.widgets.core_visualizer import CoreVisualizerWidget

class FloatingModeWidget(QWidget):
    """Minimalist ambient AI core floating on desktop."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_pinned_on_top = True
        self._drag_pos = QPoint()
        self._press_global = QPoint()
        self._was_dragged = False

        # Frameless, translucent window
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow
        if self.is_pinned_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Core visualizer with organic, unclipped glow
        self.visualizer = CoreVisualizerWidget(base_radius=42)
        self.layout.addWidget(self.visualizer)

        self.setFixedSize(200, 200)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._press_global = event.globalPosition().toPoint()
            self._was_dragged = False
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._was_dragged = True
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Sürüklemeden ayırt edilen tek tık: mod menüsünü açar."""
        if event.button() == Qt.MouseButton.LeftButton and not self._was_dragged:
            self.show_mode_menu(event.globalPosition().toPoint())
            event.accept()
            return
        self._was_dragged = False
        super().mouseReleaseEvent(event)

    def show_mode_menu(self, global_pos):
        """Çekirdeğin mod menüsünü gösterir (görselleştirici ile ortak menü)."""
        menu = self.visualizer.build_mode_menu()
        menu.exec(global_pos)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double-clicking the core summons Chat Mode."""
        if event.button() == Qt.MouseButton.LeftButton:
            bus.mode_requested.emit("chat")
            event.accept()

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Right-click context menu (Pin, Switch to Zen, Open Chat, Exit)."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0E1420;
                color: #F0F6FC;
                border: 1px solid #1F2B42;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #1A263C;
                color: #00F0FF;
            }
        """)

        # 1. Pin / Always on top toggle
        pin_text = "Sabitlemeyi Kaldır" if self.is_pinned_on_top else "Ekrana Sabitle (Always On Top)"
        action_pin = QAction(pin_text, self)
        action_pin.triggered.connect(self._toggle_pin)
        menu.addAction(action_pin)

        menu.addSeparator()

        # 2. Switch to Zen Mode
        action_zen = QAction("Zen Moda Geç", self)
        action_zen.triggered.connect(lambda: bus.mode_requested.emit("zen"))
        menu.addAction(action_zen)

        # 3. Switch to Chat Mode
        action_chat = QAction("Chat Modunu Aç", self)
        action_chat.triggered.connect(lambda: bus.mode_requested.emit("chat"))
        menu.addAction(action_chat)

        menu.addSeparator()

        # 4. Exit
        action_exit = QAction("Kapat / Çıkış", self)
        action_exit.triggered.connect(self.close)
        menu.addAction(action_exit)

        menu.exec(event.globalPos())

    def _toggle_pin(self):
        self.is_pinned_on_top = not self.is_pinned_on_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.is_pinned_on_top)
        self.show()

    def closeEvent(self, event):
        if hasattr(self, "visualizer") and self.visualizer:
            try:
                self.visualizer.close()
            except Exception:
                pass
        super().closeEvent(event)
