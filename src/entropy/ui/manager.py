from pathlib import Path
from typing import Optional
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QAction, QIcon, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.provider import create_bridge, switch_provider
from entropy.ui.design import apply_design_system
from entropy.ui.modes.chat_mode import CHAT_MIN_SIZE, CHAT_SCREEN_RATIO, ChatModeWindow
from entropy.ui.modes.floating_mode import FloatingModeWidget
from entropy.ui.modes.zen_mode import ZEN_MIN_SIZE, ZEN_SCREEN_RATIO, ZenModeWindow
from entropy.ui.window_sizing import (
    clamp_window_into_screen,
    fit_window_to_screen,
    maximize_window_to_screen,
)

class EntropyUIManager(QObject):
    """Controls window lifecycles and mode transitions for Entropy AI."""

    #: Tek örnek başvurusu (bkz. __init__); sağlayıcı seçicisi bunu kullanır.
    instance: Optional["EntropyUIManager"] = None

    def __init__(self, bridge: Optional[AgyProcessBridge] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.bridge = bridge or create_bridge(config)
        # Üst çubuktaki "Sağlayıcı" listesi köprüyü değiştirmek için yöneticiye
        # ulaşmak zorunda; pencerelere yönetici başvurusu geçirmek yerine tek
        # örnek burada yayınlanır (uygulamada zaten tek yönetici var).
        EntropyUIManager.instance = self

        # Faz 11-E adım 2: tasarım sistemi TEK giriş noktasından uygulanır.
        # Neden `main.py` değil de burada: stil arayüz kapsamıdır ve pencereler
        # burada kuruluyor; stil pencerelerden ÖNCE uygulanmalı ki hiçbir
        # pencere kendi stil sayfasını yazmak zorunda kalmasın (eski
        # `setStyleSheet(STYLESHEET)` çağrıları kaldırıldı).
        app = QApplication.instance()
        if app is not None:
            self.design_qss = apply_design_system(app)

        # Initialize windows
        self.floating_widget = FloatingModeWidget()
        self.zen_window = ZenModeWindow(bridge=self.bridge)
        self.chat_window = ChatModeWindow(bridge=self.bridge)

        self._set_window_icons()

        self.current_mode = config.default_mode

        self._setup_tray_icon()
        self._connect_signals()

    def switch_provider(self, provider: str) -> bool:
        """
        Çalışırken sağlayıcı değiştirir ve açık pencereleri yeni köprüye bağlar.

        Eski köprü söndürülür (arka plan süreçleri ve ledger satırları öksüz
        kalmasın); pencereler yeniden yaratılmaz, yalnızca `bridge` başvuruları
        ve model listesi tazelenir — mod geçmişi ve ekran içeriği korunur.
        """
        try:
            new_bridge = switch_provider(self.bridge, provider, cfg=config)
        except Exception as e:
            bus.terminal_output_received.emit(f"\n[Sağlayıcı Değişimi Hatası]: {e}\n")
            return False

        self.bridge = new_bridge
        for win in (self.zen_window, self.chat_window):
            try:
                win.bridge = new_bridge
                refresh = getattr(win, "refresh_provider_ui", None)
                if callable(refresh):
                    refresh()
            except Exception:
                pass
        bus.terminal_output_received.emit(
            f"\n[Sağlayıcı] Artık {provider} kullanılıyor (model: {new_bridge.selected_model}).\n"
        )
        return True

    def _set_window_icons(self):
        """Apply high-resolution cybernetic app icon to all windows."""
        icon_path = Path.cwd() / "entropy.ico"
        if not icon_path.exists():
            icon_path = Path(__file__).resolve().parents[3] / "entropy.ico"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            self.floating_widget.setWindowIcon(icon)
            self.zen_window.setWindowIcon(icon)
            self.chat_window.setWindowIcon(icon)

    def _setup_tray_icon(self):
        """Create Windows notification area icon."""
        self.tray_icon = QSystemTrayIcon(self)

        icon_path = Path.cwd() / "entropy.ico"
        if not icon_path.exists():
            icon_path = Path(__file__).resolve().parents[3] / "entropy.ico"
        if icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            pix = QPixmap(16, 16)
            pix.fill(QColor(0, 240, 255))
            self.tray_icon.setIcon(QIcon(pix))
        self.tray_icon.setToolTip("Entropy AI - Agentic OS")

        # Context Menu
        menu = QMenu()
        zen_act = QAction("Zen Mode", self)
        zen_act.triggered.connect(lambda: self.switch_mode("zen"))
        menu.addAction(zen_act)

        float_act = QAction("◎ Floating Mode", self)
        float_act.triggered.connect(lambda: self.switch_mode("floating"))
        menu.addAction(float_act)

        chat_act = QAction("Chat Mode", self)
        chat_act.triggered.connect(lambda: self.switch_mode("chat"))
        menu.addAction(chat_act)

        menu.addSeparator()
        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.quit_app)
        menu.addAction(exit_act)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _connect_signals(self):
        bus.mode_requested.connect(self.switch_mode)

    @Slot(str)
    def switch_mode(self, mode_name: str):
        """Transition between Zen, Floating, and Chat modes across multiple monitors."""
        self.current_mode = mode_name.lower()

        # Find active screen where user is currently interacting
        active_screen = None
        if self.floating_widget.isVisible():
            center_pt = self.floating_widget.geometry().center()
            active_screen = QApplication.screenAt(center_pt) or self.floating_widget.screen()
        elif self.chat_window.isVisible():
            center_pt = self.chat_window.geometry().center()
            active_screen = QApplication.screenAt(center_pt) or self.chat_window.screen()
        elif self.zen_window.isVisible():
            center_pt = self.zen_window.geometry().center()
            active_screen = QApplication.screenAt(center_pt) or self.zen_window.screen()

        if not active_screen:
            active_screen = QApplication.primaryScreen()

        if self.current_mode == "zen":
            self.floating_widget.hide()
            self.chat_window.hide()
            # Faz 8: Zen acilista kullanilabilir alanin TAMAMINI kaplar.
            # (Faz 6'daki %92 orani kullaniciya "tam ekrandan cikmis" 1766x949
            # bir pencere olarak gorunuyordu.) Gorev cubugu yine erisilebilir,
            # cunku tam ekran degil `availableGeometry` kullanilir. Kullanici
            # pencereyi tasidiysa/kuculttuyse geometrisine dokunulmaz.
            if not self.zen_window.isVisible():
                maximize_window_to_screen(
                    self.zen_window,
                    min_size=ZEN_MIN_SIZE,
                    screen=active_screen,
                )
            else:
                fit_window_to_screen(
                    self.zen_window,
                    ratio=ZEN_SCREEN_RATIO,
                    min_size=ZEN_MIN_SIZE,
                    screen=active_screen,
                    keep_preferred=True,
                )
            self.zen_window.show()
            self.zen_window.raise_()
            self.zen_window.activateWindow()
        elif self.current_mode == "floating":
            self.zen_window.hide()
            self.chat_window.hide()
            if active_screen and not self.floating_widget.isVisible():
                s_geom = active_screen.geometry()
                self.floating_widget.setScreen(active_screen)
                self.floating_widget.move(
                    s_geom.x() + (s_geom.width() - self.floating_widget.width()) // 2,
                    s_geom.y() + (s_geom.height() - self.floating_widget.height()) // 2
                )
            self.floating_widget.show()
        elif self.current_mode == "chat":
            self.zen_window.hide()
            self.floating_widget.hide()
            if active_screen and not self.chat_window.isVisible():
                # Faz 6: konumlama tam ekran degil kullanilabilir alana gore;
                # pencere gorev cubugunun altina kaymaz.
                fit_window_to_screen(
                    self.chat_window,
                    ratio=CHAT_SCREEN_RATIO,
                    min_size=CHAT_MIN_SIZE,
                    screen=active_screen,
                    keep_preferred=True,
                )
            self.chat_window.show()
            self.chat_window.raise_()
            self.chat_window.activateWindow()

        # Faz 8: hangi moda gecilirse gecilsin gorunur pencere kullanilabilir
        # alanin icinde kalir (kullanici onu ekran disina surukledikten sonra
        # mod degistirse bile "hicbir sey olmuyor" durumu olusmaz).
        active = {
            "zen": self.zen_window,
            "chat": self.chat_window,
            "floating": self.floating_widget,
        }.get(self.current_mode)
        if active is not None and active.isVisible():
            try:
                clamp_window_into_screen(active, screen=active_screen)
            except Exception:
                pass

        bus.mode_changed.emit(self.current_mode)

    def bring_to_front(self):
        """
        Mevcut moddaki pencereyi gösterip öne getirir.

        İkinci bir kopya başlatıldığında tek kopya kilidi bunu çağırır; tepsiye
        çekilmiş pencere geri gelir, kullanıcı "uygulama açılmadı" sanmaz.
        """
        target = {
            "zen": self.zen_window,
            "chat": self.chat_window,
            "floating": self.floating_widget,
        }.get(self.current_mode, self.floating_widget)
        try:
            if self.current_mode == "zen":
                self.switch_mode("zen")
            else:
                target.show()
            target.raise_()
            target.activateWindow()
        except Exception:
            pass

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
