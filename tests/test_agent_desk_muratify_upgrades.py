"""
Automated Pytest Suite for Muratify AgentSpace Parity & Upgrade Features in Entropy Agent Desk.
Verifies:
1. Team Templates (Product, Research, DevSecOps, Content).
2. Autonomous Goal Decomposer & Delegation Engine.
3. Interactive 4-Column Kanban Task Board (To Do, In Progress, Review, Done).
4. Verifiable Definition of Done (DoD) & Real Terminal Evidence Recording.
5. Multi-Pane Named Terminal Grid & View Tiling.
"""

import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from src.entropy.agent_desk.core.models import DeskRole, TaskStatus, TaskItem, AgentPersona
from src.entropy.agent_desk.core.office_manager import OfficeManager
from src.entropy.agent_desk.core.templates import get_available_templates, get_template
from src.entropy.agent_desk.core.goal_decomposer import GoalDecomposer
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.ui.kanban_board_widget import KanbanBoardWidget, EvidenceInspectorDialog
from src.entropy.agent_desk.ui.terminal_grid_widget import TerminalGridWidget
from src.entropy.agent_desk.ui.agent_terminal_pane import AgentTerminalPane


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_team_templates_registry():
    """Verifies that pre-defined team templates are correctly registered with DoD and roles."""
    templates = get_available_templates()
    assert "product_team" in templates
    assert "research_team" in templates
    assert "devsecops_team" in templates
    assert "content_team" in templates

    prod = get_template("product_team")
    assert prod is not None
    assert len(prod.roles) >= 3
    # Check lead has Definition of Done
    lead = next(r for r in prod.roles if r.role == DeskRole.ORCHESTRATOR)
    assert len(lead.definition_of_done) > 0


def test_create_office_from_template(tmp_path):
    """Verifies that OfficeManager can provision an entire office from a template."""
    storage = tmp_path / "test_data.json"
    mgr = OfficeManager(storage_path=storage)

    orch = mgr.create_office_from_template(
        template_id="product_team",
        name="Test Ürün Takımı",
        project_root=str(tmp_path),
    )

    assert orch is not None
    assert orch.config.name == "Test Ürün Takımı"
    assert "Ürün & Mimari Lideri" in orch.persona.name
    # Sub-agents should be provisioned
    assert len(orch.sub_agents) >= 3
    # Check that metadata contains DoD
    for ag in orch.sub_agents.values():
        assert "definition_of_done" in ag.persona.metadata


def test_goal_decomposer():
    """Verifies that GoalDecomposer breaks down a natural language objective into role-scoped subtasks."""
    goal = "Yeni bir kullanıcı paneli widget'ı kodla, veritabanı modelini oluştur ve pytest ile test et."
    tasks = GoalDecomposer.decompose_goal(
        goal=goal,
        office_id="office_test_123",
        project_root="C:/EntropiAI",
    )

    assert len(tasks) >= 2
    roles = [t.role_target for t in tasks]
    assert DeskRole.DEVELOPER in roles
    assert DeskRole.TESTER in roles

    for t in tasks:
        assert t.office_id == "office_test_123"
        assert t.status == TaskStatus.PENDING
        assert len(t.definition_of_done) > 0


def test_orchestrator_delegate_goal(tmp_path):
    """Verifies that OfficeOrchestrator.delegate_goal adds subtasks and logs to chat."""
    storage = tmp_path / "test_data.json"
    mgr = OfficeManager(storage_path=storage)
    orch = mgr.create_office_from_template("product_team", "Test Office", str(tmp_path))

    initial_todo_len = len(orch.todo_list)
    subtasks = orch.delegate_goal("REST API uç noktalarını uygula ve doğrula.", auto_execute=False)

    assert len(subtasks) >= 2
    assert len(orch.todo_list) == initial_todo_len + len(subtasks)
    # Check that orchestrator logged goal decomposition to chat
    assert any("Hedef Dağıtımı" in msg["message"] for msg in orch.chat_history)


def test_kanban_board_widget_population(qapp):
    """Verifies that KanbanBoardWidget correctly sorts tasks into 4 workflow columns."""
    board = KanbanBoardWidget()

    tasks = [
        TaskItem(
            task_id="t1",
            office_id="off1",
            title="Bekleyen Görev",
            status=TaskStatus.PENDING,
            role_target=DeskRole.DEVELOPER,
            definition_of_done=["DoD 1"],
        ),
        TaskItem(
            task_id="t2",
            office_id="off1",
            title="Yürütülen Görev",
            status=TaskStatus.IN_PROGRESS,
            role_target=DeskRole.DEVELOPER,
        ),
        TaskItem(
            task_id="t3",
            office_id="off1",
            title="Doğrulanan Görev",
            status=TaskStatus.VERIFYING,
            role_target=DeskRole.TESTER,
        ),
        TaskItem(
            task_id="t4",
            office_id="off1",
            title="Tamamlanan Görev",
            status=TaskStatus.COMPLETED,
            role_target=DeskRole.DEVELOPER,
            evidence_verified=True,
            evidence_log="STDOUT: 5 passed in 0.2s\n",
        ),
    ]

    board.populate_tasks(tasks)

    assert len(board.col_todo._cards) == 1
    assert len(board.col_in_progress._cards) == 1
    assert len(board.col_review._cards) == 1
    assert len(board.col_done._cards) == 1


def test_evidence_inspector_dialog(qapp):
    """Verifies that EvidenceInspectorDialog properly renders verifiable evidence transcripts."""
    task = TaskItem(
        task_id="t_ev",
        office_id="off_ev",
        title="Güvenlik Testi",
        status=TaskStatus.COMPLETED,
        verification_command="pytest tests/test_sec.py",
        definition_of_done=["Testler %100 başarılı"],
        evidence_verified=True,
        evidence_log="[STDOUT]: 10 passed in 1.1s\n[RETURN CODE]: 0",
    )
    dialog = EvidenceInspectorDialog(task=task)
    assert dialog is not None
    assert "Güvenlik Testi" in dialog.windowTitle()


def test_terminal_grid_widget_view_toggle(qapp):
    """Verifies that TerminalGridWidget cleanly switches between Tabbed and 2x2 Grid View."""
    grid = TerminalGridWidget()

    p1 = AgentTerminalPane(persona=AgentPersona(agent_id="a1", name="Lead", office_id="o1"))
    p2 = AgentTerminalPane(persona=AgentPersona(agent_id="a2", name="Dev", office_id="o1"))

    grid.add_or_update_pane("a1", p1, "Lead")
    grid.add_or_update_pane("a2", p2, "Dev")

    # In Tab Mode by default
    assert not grid.is_grid_mode
    assert not grid.tab_widget.isHidden()
    assert grid.grid_container.isHidden()
    assert grid.tab_widget.count() == 2

    # Switch to Grid Mode
    grid._set_grid_mode()
    assert grid.is_grid_mode
    assert grid.tab_widget.isHidden()
    assert not grid.grid_container.isHidden()
    assert grid.grid_layout.count() == 2

    # Switch back to Tab Mode
    grid._set_tab_mode()
    assert not grid.is_grid_mode
    assert not grid.tab_widget.isHidden()
    assert grid.grid_container.isHidden()
    assert grid.tab_widget.count() == 2
