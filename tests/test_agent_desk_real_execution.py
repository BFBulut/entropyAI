"""
Automated Test Suite: Agent Desk Real Autonomous Execution & Action Engine.
Verifies that:
1. ConcreteActionEngine performs real file writing, AST preflight syntax enforcement, and command execution.
2. WorkerAgent executes concrete disk actions without fake mock sleep.
3. GoalDecomposer introspects project structure and creates grounded, file-targeted TaskItems.
4. OfficeOrchestrator dispatches A2A autonomous handoffs and executes multi-task autonomous sprints.
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import sys
import time
import pytest
from pathlib import Path
from src.entropy.agent_desk.core.models import (
    DeskRole,
    TaskStatus,
    TaskItem,
    AgentPersona,
    AgentActivityState,
    OfficeConfig,
)
from src.entropy.agent_desk.core.concrete_action_engine import ConcreteActionEngine
from src.entropy.agent_desk.core.worker_agent import WorkerAgent
from src.entropy.agent_desk.core.goal_decomposer import GoalDecomposer
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator


def test_concrete_action_engine_write_and_ast_guard(tmp_path):
    """ASTPreflightGuard korumalı dosya yazma ve okuma doğrulaması."""
    # 1. Geçerli Python kodu
    valid_code = "def hello():\n    return 'world'\n"
    target_py = tmp_path / "valid_mod.py"
    res = ConcreteActionEngine.write_file(str(target_py), valid_code, check_ast=True)
    assert res["success"] is True
    assert target_py.exists()
    assert "world" in target_py.read_text(encoding="utf-8")

    # Okuma doğrulaması
    read_text = ConcreteActionEngine.read_file(str(target_py))
    assert "hello():" in read_text

    # 2. Geçersiz Python kodu (AST hatası diske yazmayı engellemeli)
    invalid_code = "def broken(:\n    return\n"
    broken_py = tmp_path / "broken_mod.py"
    res_err = ConcreteActionEngine.write_file(str(broken_py), invalid_code, check_ast=True)
    assert res_err["success"] is False
    assert not broken_py.exists()
    assert "Sözdizimi Hatası" in res_err["error"] or "SyntaxError" in res_err["error"]


def test_concrete_action_engine_execute_command(tmp_path):
    """Gerçek komut çalıştırma ve delil (evidence log) yakalama doğrulaması."""
    cmd = f'"{sys.executable}" -c "print(\'Agent Desk Real Execution Active\')"'
    res = ConcreteActionEngine.execute_command(cmd, cwd=str(tmp_path), timeout_sec=10.0)
    assert res["success"] is True
    assert res["returncode"] == 0
    assert "Agent Desk Real Execution Active" in res["stdout"]
    assert "[KOMUT]:" in res["evidence_log"]
    assert "[STDOUT]:" in res["evidence_log"]


def test_concrete_action_engine_role_actions(tmp_path):
    """Her bir uzman rol için fiili dosya oluşturma ve içerik kontrolü."""
    task = TaskItem(
        task_id="task_role_01",
        office_id="off_test",
        title="Veri Modeli Kur",
        description="Pydantic tabanlı veri modelleri oluştur",
        role_target=DeskRole.DEVELOPER,
        acceptance_criteria=["Kod modüler yazıldı", "AST geçerli"],
    )

    chunks = []
    # Developer eylemi
    dev_res = ConcreteActionEngine.execute_role_action(
        task=task,
        role=DeskRole.DEVELOPER,
        effective_dir=tmp_path,
        emit_chunk_fn=lambda c: chunks.append(c),
    )
    assert dev_res["success"] is True
    created_file = tmp_path / f"module_{task.task_id[:8]}.py"
    assert created_file.exists()
    assert "run_implementation" in created_file.read_text(encoding="utf-8")

    # Researcher eylemi
    task_res = TaskItem(
        task_id="task_res_01",
        office_id="off_test",
        title="Teknik Dokümantasyon İncele",
        role_target=DeskRole.RESEARCHER,
        acceptance_criteria=["Kaynaklar tarandı"],
    )
    res_res = ConcreteActionEngine.execute_role_action(
        task=task_res,
        role=DeskRole.RESEARCHER,
        effective_dir=tmp_path,
        emit_chunk_fn=lambda c: chunks.append(c),
    )
    assert res_res["success"] is True
    report_file = tmp_path / f"REPORT_{task_res.task_id[:8].upper()}.md"
    assert report_file.exists()


def test_worker_agent_executes_real_actions(tmp_path):
    """WorkerAgent'ın sahte sleep yerine gerçek ConcreteActionEngine çalıştırdığını doğrular."""
    persona = AgentPersona(
        agent_id="ag_dev_01",
        name="Developer Specialist",
        office_id="off_test",
        role=DeskRole.DEVELOPER,
    )
    worker = WorkerAgent(persona=persona)
    task = TaskItem(
        task_id="task_work_01",
        office_id="off_test",
        title="Çekirdek Fonksiyon Geliştir",
        role_target=DeskRole.DEVELOPER,
        acceptance_criteria=["Fonksiyon diske yazıldı"],
    )

    result = worker.execute_task(task, effective_dir=tmp_path)
    assert result["success"] is True
    assert task.status == TaskStatus.VERIFYING
    assert (tmp_path / f"module_{task.task_id[:8]}.py").exists()
    assert worker.persona.last_turn_delta_output > 0


def test_goal_decomposer_introspects_project(tmp_path):
    """GoalDecomposer'ın proje yapısını inceleyerek zeminlenmiş görevler oluşturduğunu doğrular."""
    # Test dizini içine örnek bir python dosyası ve test oluştur
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "sample.py").write_text("def sample(): pass", encoding="utf-8")
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_sample.py").write_text("def test_sample(): assert True", encoding="utf-8")

    info = GoalDecomposer.introspect_project(str(tmp_path))
    assert len(info["python_files"]) >= 2
    assert len(info["test_files"]) >= 1

    tasks = GoalDecomposer.decompose_goal(
        goal="Kullanıcı kimlik doğrulama modülü geliştir ve test et",
        office_id="off_test",
        project_root=str(tmp_path),
    )
    assert len(tasks) >= 2
    # Görevlerin geçerli rollere sahip olduğunu doğrula
    roles = [t.role_target for t in tasks]
    assert DeskRole.DEVELOPER in roles or DeskRole.TESTER in roles
    for t in tasks:
        assert t.status == TaskStatus.PENDING
        assert len(t.definition_of_done) > 0


def test_orchestrator_autonomous_sprint_and_a2a_handoff(tmp_path):
    """OfficeOrchestrator'ın görevler arası A2A handoff ve otonom sprint döngüsünü doğrular."""
    cfg = OfficeConfig(
        office_id="off_sprint_test",
        name="Sprint Test Office",
        project_root=str(tmp_path),
        orchestrator_agent_id="ag_lead",
    )
    orch = OfficeOrchestrator(config=cfg)
    orch.initialize_default_specialists()

    handoffs_received = []
    events_received = []

    def on_event(ev_type, data):
        events_received.append((ev_type, data))
        if ev_type == "handoff_dispatched":
            handoffs_received.append(data)

    orch.on_event = on_event

    # 2 Adet ardışık görev ekle
    t1 = orch.add_task(
        title="Mimari Tasarımı Çıkar",
        description="Sistem veri modellerini belirle",
        role_target=DeskRole.CODE_ARCHITECT,
    )
    t2 = orch.add_task(
        title="Geliştirmeyi Tamamla",
        description="Fonksiyonları kodla",
        role_target=DeskRole.DEVELOPER,
    )

    assert len(orch.todo_list) == 2
    assert orch.is_sprint_active is False

    # Otonom Sprint'i başlat (Senkron mock-executor veya worker ile)
    def dummy_executor(task, worker):
        return {"success": True, "output": f"Done by {worker.persona.name}"}

    started = orch.run_autonomous_sprint(
        executor_fn=dummy_executor,
        async_run=False,
    )
    assert started is True
    # Tüm görevlerin tamamlandığını doğrula
    assert t1.status == TaskStatus.COMPLETED
    assert t2.status == TaskStatus.COMPLETED
    # A2A Handoff mesajının yayınlandığını doğrula
    assert len(handoffs_received) >= 1
    assert "tamamlandı" in handoffs_received[0]["summary"]
    # Sprint tamamlandı olayını doğrula
    assert any(ev[0] == "sprint_completed" for ev in events_received)
