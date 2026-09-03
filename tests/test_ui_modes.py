"""Automated headless UI and widget tests for Entropy AI."""

import os
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication

from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.event_bus import bus
from entropy.ui.widgets.core_visualizer import CoreVisualizerWidget
from entropy.ui.widgets.terminal_pane import TerminalPaneWidget
from entropy.ui.widgets.reports_viewer import ReportsViewerWidget
from entropy.ui.modes.floating_mode import FloatingModeWidget
from entropy.ui.modes.chat_mode import ChatModeWindow
from entropy.ui.modes.zen_mode import ZenModeWindow
from entropy.ui.manager import EntropyUIManager

@pytest.fixture(scope="session")
def qapp():
    # Ensure offscreen platform plugin for headless CI/CD testing
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_core_visualizer_widget(qapp):
    widget = CoreVisualizerWidget(radius=40)
    assert widget.base_radius == 40
    assert widget.state == "idle"

    widget.set_state("thinking")
    assert widget.state == "thinking"

    widget.trigger_pulse(0.9)
    assert widget.target_radius > widget.base_radius

def test_terminal_pane_widget(qapp):
    terminal = TerminalPaneWidget(title="Test Terminal")
    terminal.append_text("Line 1\n")
    terminal.append_text("Line 2\n")

    plain_text = terminal.text_area.toPlainText()
    assert "Line 1" in plain_text
    assert "Line 2" in plain_text

    terminal.clear_terminal()
    assert terminal.text_area.toPlainText() == ""

def test_reports_viewer_widget(qapp, tmp_path):
    from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
    vault = ObsidianVaultManager(vault_path=tmp_path)
    vault.save_research_report("Test Dossier", "# Content Dossier")

    viewer = ReportsViewerWidget(vault_manager=vault)
    assert viewer.list_widget.count() >= 1

def test_floating_mode_widget(qapp):
    widget = FloatingModeWidget()
    assert widget.is_pinned_on_top is True

    # Test toggling pin
    widget._toggle_pin()
    assert widget.is_pinned_on_top is False

def test_chat_mode_staged_images(qapp, tmp_path):
    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)

    chat.show()
    # Initially no staged images
    assert len(chat.staged_images) == 0
    assert not chat.attachment_bar.isVisible()

    # Stage a simulated image
    dummy_img = tmp_path / "test.png"
    dummy_img.write_bytes(b"dummy image bytes")

    chat.staged_images.append(str(dummy_img))
    chat.attach_label.setText("📎 Pasted Image: test.png")
    chat.attachment_bar.setVisible(True)

    assert chat.attachment_bar.isVisible()

    # Clear staged
    chat._clear_staged_images()
    assert len(chat.staged_images) == 0
    assert not chat.attachment_bar.isVisible()
    chat.close()

def test_ui_manager_mode_switching(qapp):
    bridge = AgyProcessBridge()
    ui_mgr = EntropyUIManager(bridge=bridge)

    # Test switching to Zen
    ui_mgr.switch_mode("zen")
    assert ui_mgr.current_mode == "zen"
    assert ui_mgr.zen_window.isVisible()
    assert not ui_mgr.floating_widget.isVisible()

    # Test switching to Floating
    ui_mgr.switch_mode("floating")
    assert ui_mgr.current_mode == "floating"
    assert ui_mgr.floating_widget.isVisible()
    assert not ui_mgr.zen_window.isVisible()

    # Test switching to Chat
    ui_mgr.switch_mode("chat")
    assert ui_mgr.current_mode == "chat"
    assert ui_mgr.chat_window.isVisible()

    # Clean up
    ui_mgr.floating_widget.close()
    ui_mgr.zen_window.close()
    ui_mgr.chat_window.close()
    ui_mgr.tray_icon.hide()
