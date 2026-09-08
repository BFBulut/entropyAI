"""
Automated Test Suite: Entropy Agent Desk Harness Engineering & Deterministic Scaffold (Phase 162).
Ontology: 'Task is State, Agent is Compute'.
Verifies FSMGuard, ASTPreflightGuard, GitRollbackShield, WindowsProcessTreeShield,
DynamicHumanElicitation, and Zero-Loss Context Failover.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

from src.entropy.agent_desk.core.models import (
    TaskItem,
    TaskStatus,
    DeskRole,
)
from src.entropy.agent_desk.core.harness import (
    TaskFSMGuard,
    InvalidStateTransitionError,
    ASTPreflightGuard,
    ASTValidationResult,
    GitRollbackShield,
    RollbackResult,
    WindowsProcessTreeShield,
    ProcessTerminationResult,
    DynamicHumanElicitation,
    ElicitationRiskLevel,
    ElicitationAction,
    ElicitationRequest,
    ElicitationResponse,
    ZeroLossFailoverShield,
    FailoverHandoverPacket,
    FailoverReason,
    AgentDeskHarness,
    desk_harness,
)


# ============================================================================
# 1. 'Task is State, Agent is Compute' Ontolojisi ve Disk Tabanlı FSM Testleri
# ============================================================================

def test_fsm_valid_lifecycle_transitions():
    task = TaskItem(
        task_id="t_fsm_01",
        office_id="off_fsm",
        title="Implement Auth Module",
    )
    assert task.status == TaskStatus.PENDING

    # PENDING -> IN_PROGRESS
    TaskFSMGuard.guard_transition(task, TaskStatus.IN_PROGRESS, reason="Assigned to Developer")
    assert task.status == TaskStatus.IN_PROGRESS

    # IN_PROGRESS -> BLOCKED
    TaskFSMGuard.guard_transition(task, TaskStatus.BLOCKED, reason="Awaiting OAuth Client Secret")
    assert task.status == TaskStatus.BLOCKED
    assert task.blocked_reason == "Awaiting OAuth Client Secret"

    # BLOCKED -> IN_PROGRESS (unblock)
    TaskFSMGuard.guard_transition(task, TaskStatus.IN_PROGRESS, reason="Secret provided")
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.blocked_reason == ""

    # IN_PROGRESS -> VERIFYING
    TaskFSMGuard.guard_transition(task, TaskStatus.VERIFYING, reason="Running pytest suite")
    assert task.status == TaskStatus.VERIFYING

    # VERIFYING -> COMPLETED
    TaskFSMGuard.guard_transition(task, TaskStatus.COMPLETED, reason="100% tests passed")
    assert task.status == TaskStatus.COMPLETED


def test_fsm_invalid_transitions_rejected_by_guard():
    task = TaskItem(
        task_id="t_fsm_02",
        office_id="off_fsm",
        title="Direct Jump Forbidden",
    )
    assert task.status == TaskStatus.PENDING

    # PENDING -> COMPLETED doğrudan geçiş yasaktır (Verifying atlanamaz)
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        TaskFSMGuard.guard_transition(task, TaskStatus.COMPLETED)
    assert "Geçersiz durum geçişi" in str(exc_info.value)
    assert task.status == TaskStatus.PENDING

    # PENDING -> IN_PROGRESS
    TaskFSMGuard.guard_transition(task, TaskStatus.IN_PROGRESS)

    # IN_PROGRESS -> BLOCKED
    TaskFSMGuard.guard_transition(task, TaskStatus.BLOCKED, reason="Need approval")

    # BLOCKED -> COMPLETED doğrudan geçiş yasaktır
    with pytest.raises(InvalidStateTransitionError):
        TaskFSMGuard.guard_transition(task, TaskStatus.COMPLETED)


def test_task_item_block_and_unblock_convenience_methods():
    task = TaskItem(
        task_id="t_fsm_03",
        office_id="off_fsm",
        title="Block Test",
    )
    task.status = TaskStatus.IN_PROGRESS

    task.block("Database migration approval required.")
    assert task.status == TaskStatus.BLOCKED
    assert "Database migration" in task.blocked_reason

    task.unblock()
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.blocked_reason == ""


# ============================================================================
# 2. Deterministik Kalkan 1: ASTPreflightGuard Testleri
# ============================================================================

def test_ast_preflight_guard_valid_code():
    code = '''
def calculate_metrics(values: list[float]) -> dict:
    total = sum(values)
    avg = total / max(1, len(values))
    return {"total": total, "average": avg}
'''
    res = ASTPreflightGuard.validate_code(code, filepath="metrics.py")
    assert res.is_valid is True
    assert res.error_message is None
    assert res.error_line is None


def test_ast_preflight_guard_catches_syntax_errors():
    faulty_code = '''
def broken_function():
    print("Missing closing bracket"
'''
    res = ASTPreflightGuard.validate_code(faulty_code, filepath="broken.py")
    assert res.is_valid is False
    assert res.error_line is not None
    assert "Sözdizimi Hatası" in res.error_message
    assert res.code_snippet is not None


def test_ast_preflight_guard_safe_write_prevents_disk_corruption():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_file = tmp_path / "agent_output.py"

        # 1. Hatalı kod diske yazılmamalı
        bad_code = "def foo(:\n    pass"
        res_bad = ASTPreflightGuard.safe_write_to_disk(target_file, bad_code)
        assert res_bad.is_valid is False
        assert not target_file.exists()

        # 2. Geçerli kod diske başarıyla yazılmalı
        good_code = "def foo():\n    return 42\n"
        res_good = ASTPreflightGuard.safe_write_to_disk(target_file, good_code)
        assert res_good.is_valid is True
        assert target_file.exists()
        assert target_file.read_text(encoding="utf-8") == good_code


# ============================================================================
# 3. Deterministik Kalkan 2: GitRollbackShield Testleri
# ============================================================================

def test_git_rollback_shield_command_and_interface():
    # Non-git folder handling
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        diff = GitRollbackShield.get_diff(tmp_path)
        assert diff == ""

        dirty = GitRollbackShield.get_dirty_files(tmp_path)
        assert dirty == []

        res = GitRollbackShield.rollback_dirty(tmp_path)
        assert res.success is True
        assert res.error == "Not a git repository."


# ============================================================================
# 4. Deterministik Kalkan 3: WindowsProcessTreeShield Testleri
# ============================================================================

def test_windows_process_tree_shield_command_format():
    cmd = WindowsProcessTreeShield.get_kill_command(12345)
    assert cmd == "taskkill /F /T /PID 12345"


def test_windows_process_tree_shield_invalid_pid():
    res = WindowsProcessTreeShield.terminate_pid_tree(0)
    assert res.killed is False
    assert res.error == "Invalid PID"


# ============================================================================
# 5. Deterministik Kalkan 4: DynamicHumanElicitation Testleri
# ============================================================================

def test_dynamic_human_elicitation_lifecycle():
    elicitation = DynamicHumanElicitation()
    received_requests = []
    elicitation.register_listener(lambda req: received_requests.append(req))

    task = TaskItem(
        task_id="t_elicit_01",
        office_id="off_elicit",
        title="Drop Production Database",
    )
    task.status = TaskStatus.IN_PROGRESS

    # 1. Onay talebi tetikleme
    req = elicitation.trigger_request(
        task=task,
        question="Veritabanını sıfırlamak istiyor musunuz?",
        proposed_action="DROP TABLE users;",
        risk_level=ElicitationRiskLevel.CRITICAL,
    )
    assert len(received_requests) == 1
    assert received_requests[0].request_id == req.request_id
    assert task.status == TaskStatus.BLOCKED
    assert "İnsan Onayı Bekleniyor" in task.blocked_reason

    # 2. İnsan onayı verildiğinde
    resp = ElicitationResponse(
        request_id=req.request_id,
        action=ElicitationAction.APPROVE,
        human_note="Onaylandı, devam et.",
    )
    elicitation.resolve_request(req.request_id, resp, task)
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.blocked_reason == ""


def test_dynamic_human_elicitation_rejection():
    elicitation = DynamicHumanElicitation()
    task = TaskItem(
        task_id="t_elicit_02",
        office_id="off_elicit",
        title="Risky Action",
    )
    task.status = TaskStatus.IN_PROGRESS

    req = elicitation.trigger_request(
        task=task,
        question="Delete root config?",
        proposed_action="rm -rf /",
        risk_level=ElicitationRiskLevel.CRITICAL,
    )
    assert task.status == TaskStatus.BLOCKED

    resp = ElicitationResponse(
        request_id=req.request_id,
        action=ElicitationAction.REJECT,
        human_note="Riskli işlem reddedildi.",
    )
    elicitation.resolve_request(req.request_id, resp, task)
    assert task.status == TaskStatus.FAILED
    assert "reddedildi" in task.error_message


# ============================================================================
# 6. Sıfır Kayıplı Yük Devri (Zero-Loss Context Failover) Testleri
# ============================================================================

def test_zero_loss_failover_threshold_detection():
    # 1. Döngü eşiği aşımı (18+ döngü)
    needed, reason = ZeroLossFailoverShield.is_failover_needed(
        turn_count=19,
        input_tokens=20000,
        max_context_tokens=128000,
    )
    assert needed is True
    assert reason == FailoverReason.CYCLE_LIMIT_EXCEEDED

    # 2. Token bağlam doygunluğu eşiği (%82+)
    needed, reason = ZeroLossFailoverShield.is_failover_needed(
        turn_count=5,
        input_tokens=110000,
        max_context_tokens=128000,
    )
    assert needed is True
    assert reason == FailoverReason.CONTEXT_SATURATION

    # 3. Güvenli eşik altında yük devri tetiklenmez
    needed, reason = ZeroLossFailoverShield.is_failover_needed(
        turn_count=4,
        input_tokens=25000,
        max_context_tokens=128000,
    )
    assert needed is False
    assert reason is None


def test_zero_loss_failover_summary_distillation():
    task = TaskItem(
        task_id="t_failover_01",
        office_id="off_fo",
        title="Refactor Storage Engine",
        turn_count=18,
        acceptance_criteria=["Clean SQLite tables", "Async thread pool"],
    )
    modified = ["src/storage.py", "tests/test_storage.py"]
    summary = ZeroLossFailoverShield.distill_summary(
        task=task,
        output_history="Storage refactored, testing connection pooling.",
        modified_files=modified,
    )
    assert "Refactor Storage Engine" in summary
    assert "src/storage.py" in summary
    assert "Clean SQLite tables" in summary
    assert "FAILOVER RAPORU" in summary


# ============================================================================
# 7. AgentDeskHarness Master Supervisor Testleri
# ============================================================================

def test_harness_supervisor_lifecycle_and_hooks():
    harness = AgentDeskHarness()
    task = TaskItem(
        task_id="t_sup_01",
        office_id="off_sup",
        title="Supervisor Test",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Pre-task hook -> IN_PROGRESS
        harness.pre_task_hook(task, tmp_path)
        assert task.status == TaskStatus.IN_PROGRESS

        # Safe code write via AST guard
        code_file = tmp_path / "worker_logic.py"
        valid_res = harness.safe_write_code(code_file, "def run():\n    return True\n")
        assert valid_res.is_valid is True
        assert code_file.exists()

        # Post-task verification success hook -> COMPLETED
        harness.post_task_verification_hook(
            task=task,
            repo_path=tmp_path,
            verification_passed=True,
            evidence_log="All assertions passed.",
        )
        assert task.status == TaskStatus.COMPLETED
        assert task.evidence_verified is True
