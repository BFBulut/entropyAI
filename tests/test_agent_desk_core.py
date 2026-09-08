"""
Automated Test Suite: Entropy Agent Desk Core & Models.
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import sys
import time
import subprocess
import pytest
import psutil
from src.entropy.agent_desk.core.models import (
    DeskRole,
    AgentActivityState,
    TaskStatus,
    TaskItem,
    AgentPersona,
    OfficeConfig,
)
from src.entropy.agent_desk.core.agy_model_registry import AGYModelRegistry, FALLBACK_AGY_MODELS
from src.entropy.agent_desk.core.worker_agent import WorkerAgent
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.core.office_manager import OfficeManager
from src.entropy.agent_desk.core.agy_task_executor import (
    AgyTaskExecutor,
    terminate_process_tree,
    get_process_tree_kill_command,
)


def test_task_item_lifecycle_and_circuit_breaker():
    task = TaskItem(
        task_id="t_001",
        office_id="off_test",
        title="Implement Auth",
        role_target=DeskRole.DEVELOPER,
        max_retries=3,
    )
    assert task.status == TaskStatus.PENDING
    assert task.can_retry() is True

    # 1. Hata
    task.record_failure("Syntax error in line 12")
    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 1
    assert task.can_retry() is True

    # 2. Hata
    task.record_failure("Unit test failed")
    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 2
    assert task.can_retry() is True

    # 3. Hata -> Circuit Breaker tetiklenmeli
    task.record_failure("Third consecutive crash")
    assert task.status == TaskStatus.ESCALATED
    assert task.retry_count == 3
    assert task.can_retry() is False


def test_agent_persona_delta_token_accounting():
    persona = AgentPersona(
        agent_id="ag_dev_1",
        name="Developer One",
        office_id="off_test",
        model="gemini-3.8-flash-high",
    )

    # Tur 1
    persona.update_delta_tokens(cumulative_input=1000, cumulative_output=400)
    assert persona.last_turn_delta_input == 1000
    assert persona.last_turn_delta_output == 400
    assert persona.lifetime_tokens_input == 1000
    assert persona.lifetime_tokens_output == 400

    # Tur 2 (Kümülatif artış: +500 input, +250 output)
    persona.update_delta_tokens(cumulative_input=1500, cumulative_output=650)
    assert persona.last_turn_delta_input == 500
    assert persona.last_turn_delta_output == 250
    assert persona.lifetime_tokens_input == 1500
    assert persona.lifetime_tokens_output == 650


def test_agy_model_registry_dynamic_discovery_and_fallback():
    models = AGYModelRegistry.discover_models()
    assert isinstance(models, dict)
    assert len(models) > 0

    # Bilinen bir model kontrolü
    assert AGYModelRegistry.is_valid_model("gemini-3.8-flash-high") is True
    display_name = AGYModelRegistry.get_display_name("gemini-3.8-flash-high")
    assert "Gemini" in display_name

    # Bilinmeyen model kuralı: '[Model: Unknown]' veya '[Model: ...]'
    assert AGYModelRegistry.get_display_name(None) == "[Model: Unknown]"
    assert AGYModelRegistry.get_display_name("") == "[Model: Unknown]"
    assert AGYModelRegistry.is_valid_model("non-existent-ai-xyz") is False


def test_worker_agent_execution_and_activity_transitions():
    persona = AgentPersona(
        agent_id="ag_test_01",
        name="QA Sentinel",
        office_id="off_test",
        role=DeskRole.TESTER,
        model="gemini-3.8-flash-high",
    )

    activity_log = []
    chunk_log = []

    worker = WorkerAgent(
        persona=persona,
        on_activity_changed=lambda aid, st: activity_log.append(st),
        on_token_chunk=lambda aid, ch: chunk_log.append(ch),
    )

    task = TaskItem(
        task_id="t_exec_01",
        office_id="off_test",
        title="Run Regression Tests",
        role_target=DeskRole.TESTER,
        acceptance_criteria=["Pass 100%"],
    )

    res = worker.execute_task(task)
    assert res["success"] is True
    assert task.status == TaskStatus.VERIFYING
    assert worker.persona.activity_state == AgentActivityState.IDLE

    # Aktivite geçişleri tetiklenmiş olmalı: THINKING, READING, TYPING, TESTING, IDLE
    assert AgentActivityState.THINKING in activity_log
    assert AgentActivityState.READING in activity_log
    assert AgentActivityState.TYPING in activity_log
    assert AgentActivityState.TESTING in activity_log
    assert len(chunk_log) > 0


def test_office_manager_isolation_and_lifecycle():
    mgr = OfficeManager()
    o1 = mgr.create_office(name="Core Office", project_root="C:/proj1")
    o2 = mgr.create_office(name="UI Office", project_root="C:/proj2")

    assert len(mgr.list_offices()) == 2
    assert o1.config.office_id != o2.config.office_id

    # İzolasyon görünümü testi: o1 sadece kendi kadrosunu görür
    view1 = mgr.get_isolated_office_view(o1.config.office_id)
    assert view1["office_id"] == o1.config.office_id
    assert len(view1["sub_agents"]) == len(o1.sub_agents)

    # Geçersiz ofis erişiminde PermissionError
    with pytest.raises(PermissionError):
        mgr.get_isolated_office_view("non_existent_office")

    # Ofis silme
    deleted = mgr.delete_office(o1.config.office_id)
    assert deleted is True
    assert mgr.get_office(o1.config.office_id) is None
    assert len(mgr.list_offices()) == 1


def test_process_tree_kill_command_and_invariants():
    """Verifies non-leaking Windows process tree kill command generation."""
    cmd = get_process_tree_kill_command(5512)
    assert cmd == "taskkill /F /T /PID 5512"

    # Edge cases / boundary invariants
    assert terminate_process_tree(0) is False
    assert terminate_process_tree(-1) is False
    assert terminate_process_tree(None) is False


def test_process_tree_kill_live_execution_no_orphans():
    """Verifies that live process trees are forcefully terminated with no orphan process remaining."""
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    try:
        assert proc.poll() is None  # Active/running
        pid = proc.pid

        # Execute process tree termination
        killed = terminate_process_tree(pid)
        assert killed is True

        proc.wait(timeout=5.0)
        assert proc.poll() is not None  # Completely terminated, zero orphan processes
    finally:
        if proc.poll() is None:
            proc.kill()


def test_agy_task_executor_process_tree_tracking_and_task_termination():
    """Verifies AgyTaskExecutor tracks active processes and cleans them via taskkill /F /T /PID on cancel."""
    executor = AgyTaskExecutor(allow_live_agy=False)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    task_id = "t_sec_001"
    try:
        executor.register_process(task_id, proc)
        assert executor.get_active_process(task_id) is proc
        assert executor.is_task_cancelled(task_id) is False

        # Terminate task
        res = executor.terminate_task(task_id)
        assert res is True
        assert executor.is_task_cancelled(task_id) is True

        proc.wait(timeout=5.0)
        assert proc.poll() is not None  # Process dead, no orphan
    finally:
        if proc.poll() is None:
            proc.kill()


def test_agy_task_executor_terminate_all_cleans_all_orphans():
    """Verifies AgyTaskExecutor.terminate_all cleanly purges all active task process trees."""
    executor = AgyTaskExecutor(allow_live_agy=False)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    p1 = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    p2 = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    try:
        executor.register_process("t_all_1", p1)
        executor.register_process("t_all_2", p2)

        count = executor.terminate_all()
        assert count == 2

        p1.wait(timeout=5.0)
        p2.wait(timeout=5.0)
        assert p1.poll() is not None
        assert p2.poll() is not None
    finally:
        for p in [p1, p2]:
            if p.poll() is None:
                p.kill()


def test_orchestrator_cancel_task_cleans_process_tree():
    """Verifies OfficeOrchestrator.cancel_task transitions state and kills subprocess tree."""
    cfg = OfficeConfig(
        office_id="off_cancel_test",
        name="Cancellation Office",
        project_root="C:/test_proj",
        orchestrator_agent_id="orch_cancel",
    )
    orch = OfficeOrchestrator(config=cfg)
    orch.initialize_default_specialists()

    task = orch.add_task(
        title="Long Running Generation",
        description="Task to be cancelled by user/supervisor",
        role_target=DeskRole.DEVELOPER,
    )
    task.status = TaskStatus.IN_PROGRESS
    task.assigned_agent_id = next(iter(orch.sub_agents.keys()))

    executor = AgyTaskExecutor(allow_live_agy=False)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    try:
        executor.register_process(task.task_id, proc)

        # Cancel the task
        ok = orch.cancel_task(task.task_id, task_executor=executor)
        assert ok is True
        assert task.status == TaskStatus.CANCELLED
        assert "taskkill /F /T /PID" in task.error_message

        # Process should be terminated
        proc.wait(timeout=5.0)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_office_manager_delete_office_terminates_active_tasks():
    """Verifies OfficeManager.delete_office safely stops running tasks without orphan processes."""
    mgr = OfficeManager()
    office = mgr.create_office(name="Ephemeral Office", project_root="C:/ephemeral")
    task = office.add_task(
        title="Orphan Vulnerability Task",
        description="Must be terminated when office is deleted",
    )
    task.status = TaskStatus.IN_PROGRESS

    executor = AgyTaskExecutor(allow_live_agy=False)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    try:
        executor.register_process(task.task_id, proc)

        # Delete the office
        deleted = mgr.delete_office(office.config.office_id, task_executor=executor)
        assert deleted is True
        assert task.status == TaskStatus.CANCELLED

        proc.wait(timeout=5.0)
        assert proc.poll() is not None  # Process terminated cleanly
    finally:
        if proc.poll() is None:
            proc.kill()


def test_process_tree_kill_boundary_cases():
    """Verifies that terminate_process_tree safely handles invalid PID types without exceptions."""
    assert terminate_process_tree(None) is False
    assert terminate_process_tree(0) is False
    assert terminate_process_tree(-10) is False
    assert terminate_process_tree("invalid") is False
    assert terminate_process_tree("") is False
    assert terminate_process_tree([123]) is False
    assert terminate_process_tree({"pid": 123}) is False


def test_nested_process_tree_kill_eliminates_all_child_orphans():
    """
    Verifies that 'taskkill /F /T /PID <pid>' destroys both parent and child processes,
    preventing orphan language_server / worker processes on Windows.
    """
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    parent_script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print('CHILD_PID:', p.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", parent_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    child_pid = None
    try:
        # Read the child PID from parent stdout
        line = proc.stdout.readline()
        assert "CHILD_PID:" in line
        child_pid = int(line.strip().split(":")[1])
        assert psutil.pid_exists(proc.pid) is True
        assert psutil.pid_exists(child_pid) is True

        # Terminate entire process tree
        killed = terminate_process_tree(proc.pid)
        assert killed is True

        proc.wait(timeout=5.0)
        assert proc.poll() is not None

        # Give OS scheduler a brief moment to reap process handles
        time.sleep(0.5)

        # Invariant: Neither parent nor child process exists (zero orphans)
        assert psutil.pid_exists(proc.pid) is False
        assert psutil.pid_exists(child_pid) is False
    finally:
        if proc.poll() is None:
            proc.kill()
        if child_pid and psutil.pid_exists(child_pid):
            terminate_process_tree(child_pid)


def test_nested_process_tree_kill_with_grandchild_eliminates_all_orphans():
    """
    Verifies a 3-tier deep process tree (Parent -> Child -> Grandchild) is fully
    eradicated without orphan leakage.
    """
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    child_script = (
        "import subprocess, sys, time\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print('GRANDCHILD_PID:' + str(g.pid), flush=True)\n"
        "time.sleep(60)\n"
    )
    parent_script = (
        "import subprocess, sys, time\n"
        f"c = subprocess.Popen([sys.executable, '-c', {repr(child_script)}], stdout=subprocess.PIPE, text=True)\n"
        "g_line = c.stdout.readline()\n"
        "print('CHILD_PID:' + str(c.pid), flush=True)\n"
        "print(g_line.strip(), flush=True)\n"
        "time.sleep(60)\n"
    )

    proc = subprocess.Popen(
        [sys.executable, "-c", parent_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    child_pid = None
    grandchild_pid = None
    try:
        line1 = proc.stdout.readline()
        assert "CHILD_PID:" in line1
        child_pid = int(line1.strip().split(":")[1])

        line2 = proc.stdout.readline()
        assert "GRANDCHILD_PID:" in line2
        grandchild_pid = int(line2.strip().split(":")[1])

        assert psutil.pid_exists(proc.pid) is True
        assert psutil.pid_exists(child_pid) is True
        assert psutil.pid_exists(grandchild_pid) is True

        # Kill root process tree
        killed = terminate_process_tree(proc.pid)
        assert killed is True

        proc.wait(timeout=5.0)
        assert proc.poll() is not None

        time.sleep(0.5)

        # Invariant: 3-tier tree completely wiped out
        assert psutil.pid_exists(proc.pid) is False
        assert psutil.pid_exists(child_pid) is False
        assert psutil.pid_exists(grandchild_pid) is False
    finally:
        if proc.poll() is None:
            proc.kill()
        for p in [child_pid, grandchild_pid]:
            if p and psutil.pid_exists(p):
                terminate_process_tree(p)


def test_agy_task_executor_nested_tree_task_cancellation():
    """Verifies AgyTaskExecutor cleans up deep child processes on task cancellation."""
    executor = AgyTaskExecutor(allow_live_agy=False)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    parent_script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print('CHILD_PID:', p.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", parent_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    task_id = "t_tree_clean_001"
    child_pid = None
    try:
        line = proc.stdout.readline()
        assert "CHILD_PID:" in line
        child_pid = int(line.strip().split(":")[1])

        executor.register_process(task_id, proc)
        assert executor.get_active_process(task_id) is proc

        # Cancel the task
        ok = executor.terminate_task(task_id)
        assert ok is True
        assert executor.is_task_cancelled(task_id) is True

        proc.wait(timeout=5.0)
        assert proc.poll() is not None

        time.sleep(0.5)

        # Invariant: Both parent and child terminated, zero orphan
        assert psutil.pid_exists(proc.pid) is False
        assert psutil.pid_exists(child_pid) is False
    finally:
        if proc.poll() is None:
            proc.kill()
        if child_pid and psutil.pid_exists(child_pid):
            terminate_process_tree(child_pid)

