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
from entropy.ui.widgets.tasks_widget import TasksWidget
from entropy.scheduler.cron_engine import TaskScheduler
from entropy.ui.modes.floating_mode import FloatingModeWidget
from entropy.ui.modes.chat_mode import ChatModeWindow
from entropy.ui.modes.zen_mode import ZenModeWindow
from entropy.ui.manager import EntropyUIManager


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
    assert viewer.open_report_by_path_or_id("Test Dossier") is True
    assert "Content Dossier" in viewer.content_browser.toPlainText()

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

def test_tasks_widget_card_layout(qapp, tmp_path):
    storage = tmp_path / "tasks_layout.json"
    scheduler = TaskScheduler(storage_path=storage)
    tasks_w = TasksWidget(scheduler=scheduler)
    assert tasks_w.list_widget.count() >= 3
    # Verify card size hints
    item = tasks_w.list_widget.item(0)
    assert item.sizeHint().height() >= 58

def test_zen_mode_dual_chat_and_terminal(qapp, monkeypatch):
    bridge = AgyProcessBridge()
    zen = ZenModeWindow(bridge=bridge)
    zen.show()

    # Verify presence of both chat and terminal
    assert hasattr(zen, "chat_browser")
    assert hasattr(zen, "chat_input")
    assert hasattr(zen, "terminal_pane")
    assert hasattr(zen, "submit_btn")

    # Prevent real background thread in UI test
    monkeypatch.setattr(zen.bridge, "send_prompt_async", lambda *args, **kwargs: True)

    # Verify input routing doesn't throw AttributeError
    zen.prompt_input.setText("Test quick prompt")
    zen._on_submit_prompt()
    assert zen.chat_browser.toPlainText() != ""
    assert "Test quick prompt" in zen.chat_browser.toPlainText()

    # Verify staging images works
    zen.staged_images.append("test.png")
    assert len(zen.staged_images) == 1
    zen._clear_staged_images()
    assert len(zen.staged_images) == 0

    zen.close()

def test_memory_inspector_dialog(qapp, tmp_path):
    from entropy.ui.widgets.memory_inspector_dialog import MemoryInspectorDialog
    from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

    cog = CognitiveMemorySystem()
    cog.store_node("semantic", "Test semantic insight for inspector panel", importance=0.88, metadata={"test": "1"})

    # Test opening inspector for ego core
    dlg = MemoryInspectorDialog("ego-entropy-core")
    assert dlg.windowTitle() != ""
    dlg.close()

    # Test opening inspector for a report or generic node
    dlg_gen = MemoryInspectorDialog("generic-test-node")
    assert dlg_gen.windowTitle() != ""
    dlg_gen.close()

def test_standalone_report_window(qapp, tmp_path):
    from entropy.ui.widgets.standalone_report_window import StandaloneReportWindow

    win = StandaloneReportWindow()
    assert hasattr(win, "viewer")

    # Create dummy report
    rep = tmp_path / "Dummy_Research.md"
    rep.write_text("# Dummy Research\n\nContent for test.", encoding="utf-8")

    win.open_report_file(str(rep))
    assert win.viewer.content_browser.toPlainText() != ""
    win.close()

def test_chat_mode_report_integration(qapp, tmp_path):
    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)
    chat.show()

    # Trigger report_created signal
    dummy_rep = tmp_path / "Agent_Report.md"
    dummy_rep.write_text("# Agent Report\n\nAnalysis findings.", encoding="utf-8")

    bus.report_created.emit(str(dummy_rep))
    assert chat.report_bar.isVisible()
    assert "Agent_Report" in chat.report_bar_lbl.text()
    assert "Yeni Araştırma Raporu Oluşturuldu" in chat.chat_browser.toPlainText()

    chat.close()


