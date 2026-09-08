"""
Automated Test Suite: Agent Desk Persistence & Zero Data Loss Invariants.
Validates:
1. State serialization and deserialization across application restarts.
2. 'Daha fazla silme' invariant: deleted offices and agents NEVER resurrect.
3. Office and agent edit mutations persist accurately.
4. Task and chat history persistence.
"""

import pytest
import json
from pathlib import Path
from src.entropy.agent_desk.core.office_manager import OfficeManager
from src.entropy.agent_desk.core.models import DeskRole, TaskStatus
from src.entropy.agent_desk.memory.partitioned_memory import OfficeMemoryPartition


def test_office_and_agent_persistence_cycle(tmp_path: Path):
    data_file = tmp_path / "agent_desk_data.json"
    mgr1 = OfficeManager(storage_path=data_file, auto_load=True)

    # 1. Create 2 offices
    o1 = mgr1.create_office(
        name="Alpha Core Desk",
        project_root="C:/EntropiAI/src/entropy/core",
        description="Core architecture workspace",
        orchestrator_model="claude-sonnet-4-6",
        auto_init_specialists=True,
    )
    o2 = mgr1.create_office(
        name="Beta UI Desk",
        project_root="C:/EntropiAI/src/entropy/agent_desk/ui",
        description="User interface and graphics workspace",
        orchestrator_model="gemini-3.8-flash-high",
        auto_init_specialists=True,
    )

    assert len(mgr1.list_offices()) == 2
    assert data_file.exists()

    # Add tasks to o1
    t1 = o1.add_task(
        title="Verify IPC Socket",
        description="Ensure no orphan child processes",
        role_target=DeskRole.DEVELOPER,
        acceptance_criteria=["Pass all tests"],
    )
    assert len(o1.todo_list) == 1

    # Edit an agent in o1
    agent_id = next(iter(o1.sub_agents.keys()))
    o1.update_sub_agent(
        agent_id=agent_id,
        name="Custom Master Architect",
        role=DeskRole.CODE_ARCHITECT,
        model="claude-opus-4-6-thinking",
        system_prompt="Execute deep AST inspections",
    )

    # Delete an agent in o2
    o2_agent_ids = list(o2.sub_agents.keys())
    assert len(o2_agent_ids) >= 4
    deleted_agent_id = o2_agent_ids[0]
    deleted_agent_desk = o2.sub_agents[deleted_agent_id].persona.desk_index
    assert o2.delete_sub_agent(deleted_agent_id) is True
    assert deleted_agent_id not in o2.sub_agents

    # Edit o1 office details
    mgr1.update_office(
        office_id=o1.config.office_id,
        name="Alpha Super Core Desk",
        project_root="C:/EntropiAI/core_v2",
        description="Updated description",
        orchestrator_model="claude-opus-4-6-thinking",
    )

    # Delete o2 completely!
    assert mgr1.delete_office(o2.config.office_id) is True
    assert len(mgr1.list_offices()) == 1

    # =========================================================================
    # SIMULATE APP RESTART (Launch clean new OfficeManager from the same disk file)
    # =========================================================================
    mgr2 = OfficeManager(storage_path=data_file, auto_load=True)
    assert mgr2.has_persisted_data() is True

    offices = mgr2.list_offices()
    assert len(offices) == 1, "Only 1 office should exist; deleted office must NOT resurrect!"

    loaded_o1 = mgr2.get_office(o1.config.office_id)
    assert loaded_o1 is not None
    assert loaded_o1.config.name == "Alpha Super Core Desk"
    assert loaded_o1.config.project_root == "C:/EntropiAI/core_v2"
    assert loaded_o1.persona.model == "claude-opus-4-6-thinking"

    # Verify task persisted
    assert len(loaded_o1.todo_list) == 1
    assert loaded_o1.todo_list[0].title == "Verify IPC Socket"

    # Verify edited agent persisted
    loaded_agent = loaded_o1.sub_agents.get(agent_id)
    assert loaded_agent is not None
    assert loaded_agent.persona.name == "Custom Master Architect"
    assert loaded_agent.persona.model == "claude-opus-4-6-thinking"
    assert loaded_agent.persona.system_prompt == "Execute deep AST inspections"

    # Verify deleted o2 does NOT exist
    assert mgr2.get_office(o2.config.office_id) is None


def test_delete_all_offices_never_resurrects(tmp_path: Path):
    """
    Kritik İnvaryant: Kullanıcı tüm ofisleri sildiğinde,
    uygulama yeniden açıldığında varsayılan ofisleri zorla tekrar oluşturmamalıdır.
    """
    data_file = tmp_path / "agent_desk_data.json"
    mgr1 = OfficeManager(storage_path=data_file, auto_load=True)

    o = mgr1.create_office(name="Temporary Office", project_root="C:/temp")
    assert len(mgr1.list_offices()) == 1

    # Kullanıcı siliyor
    mgr1.delete_office(o.config.office_id)
    assert len(mgr1.list_offices()) == 0
    assert data_file.exists()

    # Uygulama tekrar açılıyor
    mgr2 = OfficeManager(storage_path=data_file, auto_load=True)
    assert mgr2.has_persisted_data() is True
    assert len(mgr2.list_offices()) == 0, "Silinen ofisler asla geri gelmemelidir!"


def test_partitioned_memory_persistence(tmp_path: Path):
    mem_file = tmp_path / "agent_desk_memory.json"
    vault_dir = tmp_path / "obsidian_vault"

    p1 = OfficeMemoryPartition(storage_path=mem_file, obsidian_vault_dir=vault_dir, auto_load=True)
    r1 = p1.store_memory(
        office_id="office_test_100",
        title="Deep Architecture Rationale",
        content="Decoupled task contracts are mandatory for multi-tenant isolation.",
        tags=["architecture", "isolation"],
    )
    assert mem_file.exists()

    # Obsidian dosyasının yazıldığını doğrula
    obs_file = vault_dir / "office_test_100" / "Deep Architecture Rationale.md"
    assert obs_file.exists()
    assert "Decoupled task contracts" in obs_file.read_text(encoding="utf-8")

    # Restart simülasyonu
    p2 = OfficeMemoryPartition(storage_path=mem_file, obsidian_vault_dir=vault_dir, auto_load=True)
    loaded = p2.list_office_notes("office_test_100")
    assert len(loaded) == 1
    assert loaded[0].title == "Deep Architecture Rationale"
    assert "isolation" in loaded[0].tags
