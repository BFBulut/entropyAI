"""
Automated Test Suite: Antigravity Task Execution Engine & Delta Tokens.
Validates:
1. Cognitive context assembly.
2. Background thread task execution.
3. Delta token accounting: Δturn_out = max(0, Uk.out - Uk-1.out).
4. Verification command execution and QA Sentinel pass/fail handling.
5. Automated memory consolidation into OfficeMemoryPartition.
"""

import pytest
import time
from pathlib import Path
from src.entropy.agent_desk.core.models import (
    TaskItem,
    TaskStatus,
    AgentPersona,
    AgentActivityState,
    DeskRole,
    OfficeConfig,
)
from src.entropy.agent_desk.core.worker_agent import WorkerAgent
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.core.agy_task_executor import AgyTaskExecutor
from src.entropy.agent_desk.memory.partitioned_memory import OfficeMemoryPartition


def test_agy_task_executor_sync_execution(tmp_path: Path):
    mem_partition = OfficeMemoryPartition(storage_path=tmp_path / "mem.json")
    executor = AgyTaskExecutor(memory_partition=mem_partition, allow_live_agy=False)

    persona = AgentPersona(
        agent_id="test_worker_1",
        name="Backend Specialist",
        office_id="test_office_200",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
    )
    worker = WorkerAgent(persona=persona)

    task = TaskItem(
        task_id="t_101",
        office_id="test_office_200",
        title="Implement Health Check Endpoint",
        description="Write a fast health probe",
        acceptance_criteria=["Return 200 OK"],
    )

    # Senkron test yürütmesi
    executor._run_task_worker(
        task=task,
        worker=worker,
        project_root=str(tmp_path),
        on_complete=None,
    )

    assert task.status == TaskStatus.COMPLETED
    assert task.output != ""
    assert worker.persona.lifetime_tokens_input > 0
    assert worker.persona.last_turn_delta_input > 0

    # Hafıza konsolidasyonunu doğrula
    notes = mem_partition.list_office_notes("test_office_200")
    assert len(notes) == 1
    assert "Implement Health Check Endpoint" in notes[0].title


def test_verification_command_pass(tmp_path: Path):
    executor = AgyTaskExecutor(allow_live_agy=False)

    persona = AgentPersona(
        agent_id="test_qa_sentinel",
        name="QA Sentinel",
        office_id="test_office_300",
        role=DeskRole.TESTER,
        model="gemini-3.8-flash-high",
    )
    worker = WorkerAgent(persona=persona)

    task = TaskItem(
        task_id="t_102",
        office_id="test_office_300",
        title="Run Unit Tests",
        description="Check exit code of valid command",
        verification_command="python -c \"print('All passed'); exit(0)\"",
    )

    executor._run_task_worker(
        task=task,
        worker=worker,
        project_root=str(tmp_path),
        on_complete=None,
    )

    assert task.status == TaskStatus.COMPLETED
    assert task.retry_count == 0


def test_verification_command_failure_and_circuit_breaker(tmp_path: Path):
    executor = AgyTaskExecutor(allow_live_agy=False)

    persona = AgentPersona(
        agent_id="test_qa_sentinel_fail",
        name="QA Sentinel",
        office_id="test_office_400",
        role=DeskRole.TESTER,
        model="gemini-3.8-flash-high",
    )
    worker = WorkerAgent(persona=persona)

    task = TaskItem(
        task_id="t_103",
        office_id="test_office_400",
        title="Failing Verification Job",
        description="Fails 3 times then escalates",
        verification_command="python -c \"exit(1)\"",
        max_retries=3,
    )

    # Deneme 1
    executor._run_task_worker(task=task, worker=worker, project_root=str(tmp_path), on_complete=None)
    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 1

    # Deneme 2
    executor._run_task_worker(task=task, worker=worker, project_root=str(tmp_path), on_complete=None)
    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 2

    # Deneme 3 -> Circuit breaker triggers ESCALATED
    executor._run_task_worker(task=task, worker=worker, project_root=str(tmp_path), on_complete=None)
    assert task.status == TaskStatus.ESCALATED
    assert task.retry_count == 3


def test_async_task_execution_flow(tmp_path: Path):
    executor = AgyTaskExecutor(allow_live_agy=False)

    persona = AgentPersona(
        agent_id="test_async_agent",
        name="Async Developer",
        office_id="test_office_500",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
    )
    worker = WorkerAgent(persona=persona)

    task = TaskItem(
        task_id="t_async_001",
        office_id="test_office_500",
        title="Async Background Task",
        description="Runs in background without freezing caller",
    )

    done_event = []

    def on_done(t, success):
        done_event.append((t.task_id, success))

    executor.execute_task_async(
        task=task,
        worker=worker,
        project_root=str(tmp_path),
        on_complete=on_done,
    )

    # Wait up to 5 seconds for background thread
    for _ in range(50):
        if done_event:
            break
        time.sleep(0.1)

    assert len(done_event) == 1
    assert done_event[0][0] == "t_async_001"
    assert task.status == TaskStatus.COMPLETED
