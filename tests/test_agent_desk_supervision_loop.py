"""
Automated Test Suite: Agent Desk Autonomous Supervision Loop & Model Selection.
Validates:
1. Dynamic specialist auto-spawning with role-appropriate model selection from AGYModelRegistry.
2. Formulating corrective instructions upon validation/test failures.
3. Evaluator-Optimizer feedback loop and Circuit Breaker escalation.
"""

import pytest
from src.entropy.agent_desk.core.models import (
    OfficeConfig,
    DeskRole,
    TaskItem,
    TaskStatus,
)
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.core.agy_model_registry import AGYModelRegistry


def test_orchestrator_auto_spawn_specialist():
    cfg = OfficeConfig(
        office_id="off_spawn_test",
        name="Dynamic Team",
        project_root="C:/EntropiAI",
        orchestrator_agent_id="orch_spawn_001",
    )
    orch = OfficeOrchestrator(config=cfg)
    assert len(orch.sub_agents) == 0

    # Role CodeArchitect için otomatik ajan üret
    worker = orch.find_agent_for_role(DeskRole.CODE_ARCHITECT, auto_spawn=True)
    assert worker is not None
    assert worker.persona.role == DeskRole.CODE_ARCHITECT
    assert AGYModelRegistry.is_valid_model(worker.persona.model)
    assert len(orch.sub_agents) == 1

    # Role Tester için otomatik ajan üret
    tester = orch.find_agent_for_role(DeskRole.TESTER, auto_spawn=True)
    assert tester is not None
    assert tester.persona.role == DeskRole.TESTER
    assert len(orch.sub_agents) == 2


def test_orchestrator_corrective_instruction_generation():
    cfg = OfficeConfig(
        office_id="off_corr_test",
        name="Correction Team",
        project_root="C:/EntropiAI",
        orchestrator_agent_id="orch_corr_001",
    )
    orch = OfficeOrchestrator(config=cfg)
    task = orch.add_task(
        title="Refactor Memory Parser",
        description="Fix recursive json parsing error",
        role_target=DeskRole.DEVELOPER,
    )

    task.record_failure("IndexError: list index out of range at line 42")
    instruction = orch.generate_corrective_instruction(task, task.error_message)

    assert "[DÜZELTME TALİMATI" in instruction
    assert "IndexError" in instruction
    assert task.title in instruction


def test_closed_loop_supervisory_cycle_success():
    cfg = OfficeConfig(
        office_id="off_loop_test",
        name="Supervision Team",
        project_root="C:/EntropiAI",
        orchestrator_agent_id="orch_loop_001",
    )
    orch = OfficeOrchestrator(config=cfg)
    orch.initialize_default_specialists()

    task = orch.add_task(
        title="Build AST Guard 44.0",
        description="Enforce strict taint analysis",
        role_target=DeskRole.CODE_ARCHITECT,
        acceptance_criteria=["Taint analysis passes"],
    )

    # 1. Deneme başarısız olsun
    attempt = 0
    def mock_validator(t: TaskItem) -> bool:
        nonlocal attempt
        attempt += 1
        return attempt >= 2  # 2. denemede başarı sağlansın

    res1 = orch.execute_next_task(validator_fn=mock_validator)
    assert res1["status"] == "retrying"
    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 1

    # 2. Deneme: Başarılı tamamlansın
    res2 = orch.execute_next_task(validator_fn=mock_validator)
    assert res2["status"] == "completed"
    assert task.status == TaskStatus.COMPLETED
