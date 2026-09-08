"""
Unit and headless UI tests verifying thread-safe Qt Signal event bridge
and crash-free task execution lifecycle in Entropy Agent Desk.
"""

import os
import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.entropy.agent_desk.core.models import (
    OfficeConfig,
    DeskRole,
    TaskStatus,
    AgentActivityState,
)
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.ui.office_detail_widget import OfficeDetailWidget
from src.entropy.agent_desk.ui.agent_desk_window import AgentDeskWindow
from src.entropy.agent_desk.core.office_manager import OfficeManager


def test_office_detail_threadsafe_event_bridge(qapp):
    """Verifies that events dispatched from background threads safely route through DetailEventBridge."""
    cfg = OfficeConfig(
        office_id="test_thread_off",
        name="Thread Safe Office",
        orchestrator_agent_id="orch_thread_id",
        project_root="C:/EntropiAI",
    )
    orch = OfficeOrchestrator(config=cfg)
    orch.initialize_default_specialists()

    widget = OfficeDetailWidget(orchestrator=orch)
    widget.show()
    qapp.processEvents()

    # Add a task
    task = orch.add_task(
        title="Async Threadsafe Task",
        description="Verify zero UI crashes under cross-thread signal emission",
        role_target=DeskRole.DEVELOPER,
    )
    assert task.status == TaskStatus.PENDING

    # Run task async with mock/offline executor
    widget.task_executor.allow_live_agy = False
    orch.execute_specific_task(
        task_id=task.task_id,
        task_executor=widget.task_executor,
        async_run=True,
    )

    # Process events for up to 3 seconds until completed
    start = time.time()
    while time.time() - start < 3.0:
        qapp.processEvents()
        time.sleep(0.05)
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            break

    assert task.status == TaskStatus.COMPLETED
    assert widget.list_todo.count() >= 1
    assert widget.list_chat.count() >= 1

    # Cleanup without crashing
    widget.cleanup()
    widget.close()
    qapp.processEvents()


def test_agent_desk_window_detail_transition_cleanup(qapp, tmp_path):
    """Verifies that switching between overview and office detail does not crash with zombie callbacks."""
    storage_file = tmp_path / "test_desk_window.json"
    mgr = OfficeManager(storage_path=storage_file)
    o1 = mgr.create_office(
        name="Desk Transition Test",
        project_root=str(tmp_path),
        orchestrator_model="gemini-3.8-flash-high",
    )

    win = AgentDeskWindow(office_manager=mgr)
    win.show()
    qapp.processEvents()

    # Open office detail
    win.open_office_detail(o1.config.office_id)
    qapp.processEvents()
    assert win.detail_widget is not None

    # Return to overview (must cleanup detail_widget safely)
    win.show_overview()
    qapp.processEvents()
    assert win.detail_widget is None

    # Re-open office detail
    win.open_office_detail(o1.config.office_id)
    qapp.processEvents()
    assert win.detail_widget is not None

    win.close()
    qapp.processEvents()
