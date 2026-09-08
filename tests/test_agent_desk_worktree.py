"""
Automated Test Suite: Agent Desks Git Worktree Isolation Engine.
Validates:
1. Dynamic sandboxed port allocation.
2. Ephemeral worktree creation and lifecycle management.
3. "Isolation before Parallelism" principle: subagents execute in isolated workspaces.
4. Clean failure / cancellation teardown: zero workspace pollution on failure.
5. Merge-back on success: commits and merges changes into project root.
6. AgyTaskExecutor integration with worktree isolation enabled.
"""

import os
import subprocess
from pathlib import Path
import pytest

from src.entropy.agent_desk.core.worktree_manager import (
    WorktreeDeskManager,
    EphemeralDeskInfo,
    DeskCleanupResult,
    find_free_port,
)
from src.entropy.agent_desk.core.models import (
    TaskItem,
    TaskStatus,
    AgentPersona,
    DeskRole,
)
from src.entropy.agent_desk.core.worker_agent import WorkerAgent
from src.entropy.agent_desk.core.agy_task_executor import AgyTaskExecutor
from src.entropy.agent_desk.memory.partitioned_memory import OfficeMemoryPartition


def _setup_git_repo(repo_dir: Path):
    """Initializes a clean git repo with a commit for testing."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "EntropyTester"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "tester@entropy.ai"], cwd=str(repo_dir), check=True)
    
    # Create an initial file and commit
    readme = repo_dir / "README.md"
    readme.write_text("# Initial Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)


def test_find_free_port():
    port = find_free_port(8100, 8999)
    assert 1024 <= port <= 65535


def test_worktree_manager_filesystem_fallback(tmp_path: Path):
    """Verifies that non-git directories safely degrade to isolated filesystem directories."""
    manager = WorktreeDeskManager()
    project_root = tmp_path / "non_git_project"
    project_root.mkdir()

    assert not manager.is_git_repository(str(project_root))

    desk = manager.create_ephemeral_desk(
        project_root=str(project_root),
        office_id="off_99",
        agent_id="ag_01",
        task_id="tsk_001",
    )

    assert Path(desk.worktree_dir).exists()
    assert desk.office_id == "off_99"
    assert desk.task_id == "tsk_001"
    assert "DESK_SANDBOX_DIR" in desk.env_vars
    assert "DESK_PORT" in desk.env_vars

    # Cleanup
    result = manager.cleanup_desk(desk, merge_back=False)
    assert result.worktree_removed
    assert not Path(desk.worktree_dir).exists()


def test_worktree_manager_git_lifecycle_merge_back(tmp_path: Path):
    """Verifies full git worktree lifecycle: add -> modify in worktree -> commit -> merge -> prune."""
    repo_dir = tmp_path / "test_repo"
    _setup_git_repo(repo_dir)

    manager = WorktreeDeskManager()
    assert manager.is_git_repository(str(repo_dir))

    desk = manager.create_ephemeral_desk(
        project_root=str(repo_dir),
        office_id="off_fin",
        agent_id="agent_quant",
        task_id="task_calc_101",
    )

    assert desk.is_git_worktree
    worktree_path = Path(desk.worktree_dir)
    assert worktree_path.exists()
    assert (worktree_path / "README.md").exists()

    # Agent creates a new file inside the isolated worktree
    new_code = worktree_path / "bates_calc.py"
    new_code.write_text("# Bates SVJ calculation\nVAL = 42\n", encoding="utf-8")

    # Cleanup with merge_back=True
    res = manager.cleanup_desk(desk, merge_back=True, commit_message="feat: add bates calc")
    assert res.worktree_removed
    assert res.changes_committed
    assert not worktree_path.exists()

    # Verify branch was merged back into repo_dir
    merged_file = repo_dir / "bates_calc.py"
    assert merged_file.exists()
    assert "VAL = 42" in merged_file.read_text(encoding="utf-8")


def test_worktree_manager_cleanup_failure_zero_pollution(tmp_path: Path):
    """Verifies that failed/cancelled tasks leave zero workspace pollution in main repo."""
    repo_dir = tmp_path / "test_repo_fail"
    _setup_git_repo(repo_dir)

    manager = WorktreeDeskManager()
    desk = manager.create_ephemeral_desk(
        project_root=str(repo_dir),
        office_id="off_test",
        agent_id="agent_dev",
        task_id="task_bad_02",
    )

    worktree_path = Path(desk.worktree_dir)
    dirty_file = worktree_path / "dirty_code.py"
    dirty_file.write_text("# dirty incomplete code\n", encoding="utf-8")

    # Cleanup with merge_back=False (failure or taskkill)
    res = manager.cleanup_desk(desk, merge_back=False)
    assert res.worktree_removed
    assert not worktree_path.exists()

    # Verify main repo is pristine: no dirty_code.py exists
    assert not (repo_dir / "dirty_code.py").exists()


def test_prune_all_orphaned_desks(tmp_path: Path):
    """Verifies scanning and removing stale workspace desks."""
    repo_dir = tmp_path / "test_repo_orphan"
    _setup_git_repo(repo_dir)

    manager = WorktreeDeskManager()
    desk1 = manager.create_ephemeral_desk(str(repo_dir), "off_1", "ag_1", "t_1")
    desk2 = manager.create_ephemeral_desk(str(repo_dir), "off_1", "ag_2", "t_2")

    assert Path(desk1.worktree_dir).exists()
    assert Path(desk2.worktree_dir).exists()

    pruned = manager.prune_all_orphaned_desks(str(repo_dir))
    assert pruned == 2
    assert not Path(desk1.worktree_dir).exists()
    assert not Path(desk2.worktree_dir).exists()


def test_agy_task_executor_with_worktree_isolation(tmp_path: Path):
    """Verifies AgyTaskExecutor executing inside an ephemeral worktree."""
    repo_dir = tmp_path / "executor_repo"
    _setup_git_repo(repo_dir)

    mem_partition = OfficeMemoryPartition(storage_path=tmp_path / "mem.json")
    executor = AgyTaskExecutor(
        memory_partition=mem_partition,
        allow_live_agy=False,
        use_worktree_isolation=True,
    )

    persona = AgentPersona(
        agent_id="isolated_worker",
        name="Worktree Dev",
        office_id="off_iso",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
    )
    worker = WorkerAgent(persona=persona)

    task = TaskItem(
        task_id="task_iso_55",
        office_id="off_iso",
        title="Create Service Endpoint",
        description="Write endpoint code in worktree",
        acceptance_criteria=["Endpoint exists"],
    )

    executor._run_task_worker(
        task=task,
        worker=worker,
        project_root=str(repo_dir),
        on_complete=None,
    )

    assert task.status == TaskStatus.COMPLETED
    assert task.output != ""
    assert worker.persona.last_turn_delta_output > 0
