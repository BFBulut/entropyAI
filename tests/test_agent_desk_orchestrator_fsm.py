"""
Automated Test Suite: Entropy Agent Desk Orchestrator FSM & Verification Loops.
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import pytest
from src.entropy.agent_desk.core.models import (
    DeskRole,
    TaskStatus,
    OfficeConfig,
)
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator


def test_orchestrator_initialization_and_specialists():
    cfg = OfficeConfig(
        office_id="off_orch_test",
        name="Test Intelligence Office",
        project_root="C:/test_root",
        orchestrator_agent_id="orch_agent_001",
    )
    orch = OfficeOrchestrator(config=cfg, orchestrator_model="claude-sonnet-4-6")
    orch.initialize_default_specialists()

    assert len(orch.sub_agents) == 4
    roles = [ag.persona.role for ag in orch.sub_agents.values()]
    assert DeskRole.CODE_ARCHITECT in roles
    assert DeskRole.DEVELOPER in roles
    assert DeskRole.TESTER in roles
    assert DeskRole.RESEARCHER in roles
    assert orch.persona.desk_index == 0


def test_orchestrator_dynamic_subagent_creation():
    cfg = OfficeConfig(
        office_id="off_dynamic_test",
        name="Dynamic Team",
        project_root="C:/test_root",
        orchestrator_agent_id="orch_002",
    )
    orch = OfficeOrchestrator(config=cfg)

    # Yeni özel ajan oluştur
    new_worker = orch.create_sub_agent(
        name="Security Forensic Auditor",
        role=DeskRole.CUSTOM,
        model="gemini-3.8-flash-high",
        system_prompt="Güvenlik zafiyetlerini ve token sızıntılarını tara.",
    )
    assert new_worker.persona.role == DeskRole.CUSTOM
    assert new_worker.persona.agent_id in orch.sub_agents
    assert len(orch.chat_history) > 0


def test_orchestrator_task_success_loop():
    cfg = OfficeConfig(
        office_id="off_success_test",
        name="Success Team",
        project_root="C:/test_root",
        orchestrator_agent_id="orch_003",
    )
    orch = OfficeOrchestrator(config=cfg)
    orch.initialize_default_specialists()

    task = orch.add_task(
        title="Create Database Schema",
        description="Write SQLite migration script",
        role_target=DeskRole.CODE_ARCHITECT,
        acceptance_criteria=["Table created"],
    )
    assert task.status == TaskStatus.PENDING

    # Sıradaki görevi başarılı doğrulayıcı ile işlet
    res = orch.execute_next_task(validator_fn=lambda t: True)
    assert res is not None
    assert res["status"] == "completed"
    assert task.status == TaskStatus.COMPLETED


def test_orchestrator_corrective_feedback_and_circuit_breaker():
    cfg = OfficeConfig(
        office_id="off_retry_test",
        name="Retry Team",
        project_root="C:/test_root",
        orchestrator_agent_id="orch_004",
    )
    orch = OfficeOrchestrator(config=cfg)
    orch.initialize_default_specialists()

    task = orch.add_task(
        title="Failing Unit Test Mission",
        description="Intentionally faulty test case",
        role_target=DeskRole.TESTER,
        acceptance_criteria=["Never passes"],
    )

    # Deneme 1: Başarısız -> Status: FAILED / Retrying
    res1 = orch.execute_next_task(validator_fn=lambda t: False)
    assert res1["status"] == "retrying"
    assert task.retry_count == 1
    assert task.status == TaskStatus.FAILED

    # Deneme 2: Tekrar başarısız -> Retrying
    res2 = orch.execute_next_task(validator_fn=lambda t: False)
    assert res2["status"] == "retrying"
    assert task.retry_count == 2
    assert task.status == TaskStatus.FAILED

    # Deneme 3: Circuit Breaker devreye girmeli -> Status: ESCALATED
    res3 = orch.execute_next_task(validator_fn=lambda t: False)
    assert res3["status"] == "escalated"
    assert task.retry_count == 3
    assert task.status == TaskStatus.ESCALATED

    # Artık sırada pending/failed görev kalmadı
    res_none = orch.execute_next_task()
    assert res_none is None
