"""Master UI Manager: Orchestrates Zen, Floating, and Chat modes."""

from typing import Optional
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QAction, QIcon, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.ui.modes.chat_mode import ChatModeWindow
from entropy.ui.modes.floating_mode import FloatingModeWidget
from entropy.ui.modes.zen_mode import ZenModeWindow

class EntropyUIManager(QObject):
    """Controls window lifecycles and mode transitions for Entropy AI."""

    def __init__(self, bridge: Optional[AgyProcessBridge] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.bridge = bridge or AgyProcessBridge()

        # Initialize windows
        self.floating_widget = FloatingModeWidget()
        self.zen_window = ZenModeWindow(bridge=self.bridge)
        self.chat_window = ChatModeWindow(bridge=self.bridge)

        self.current_mode = config.default_mode

        self._setup_tray_icon()
        self._connect_signals()

    def _setup_tray_icon(self):
        """Create Windows notification area icon."""
        self.tray_icon = QSystemTrayIcon(self)

        # Generate simple cyber-cyan pixmap icon
        pix = QPixmap(16, 16)
        pix.fill(QColor(0, 240, 255))
        self.tray_icon.setIcon(QIcon(pix))
        self.tray_icon.setToolTip("Entropy AI - Agentic OS")

        # Context Menu
        menu = QMenu()
        zen_act = QAction("🧘 Zen Mode", self)
        zen_act.triggered.connect(lambda: self.switch_mode("zen"))
        menu.addAction(zen_act)

        float_act = QAction("◎ Floating Mode", self)
        float_act.triggered.connect(lambda: self.switch_mode("floating"))
        menu.addAction(float_act)

        chat_act = QAction("💬 Chat Mode", self)
        chat_act.triggered.connect(lambda: self.switch_mode("chat"))
        menu.addAction(chat_act)

        menu.addSeparator()
        exit_act = QAction("❌ Exit", self)
        exit_act.triggered.connect(self.quit_app)
        menu.addAction(exit_act)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _connect_signals(self):
        bus.mode_requested.connect(self.switch_mode)

    @Slot(str)
    def switch_mode(self, mode_name: str):
        """Transition between Zen, Floating, and Chat modes."""
        self.current_mode = mode_name.lower()

        if self.current_mode == "zen":
            self.floating_widget.hide()
            self.chat_window.hide()
            self.zen_window.showFullScreen()
        elif self.current_mode == "floating":
            self.zen_window.hide()
            self.floating_widget.show()
        elif self.current_mode == "chat":
            self.zen_window.hide()
            self.chat_window.show()
            self.chat_window.raise_()
            self.chat_window.activateWindow()

        bus.mode_changed.emit(self.current_mode)

    def start(self):
        """Boot into default mode (Floating by default)."""
        self.switch_mode(config.default_mode)

    def quit_app(self):
        """Clean shutdown."""
        self.floating_widget.close()
        self.zen_window.close()
        self.chat_window.close()
        self.tray_icon.hide()
        QApplication.quit()
