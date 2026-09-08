"""
Automated Test Suite: Entropy Agent Desk Partitioned Memory & Knowledge Graph.
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import pytest
from src.entropy.agent_desk.memory.partitioned_memory import (
    OfficeMemoryPartition,
    MemoryRecord,
)
from src.entropy.agent_desk.memory.memory_graph_bridge import MemoryGraphBridge
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.core.models import OfficeConfig


def test_office_memory_strict_isolation():
    mem = OfficeMemoryPartition()

    # Ofis 1 için özel kayıt
    mem.store_memory(
        office_id="office_alpha",
        title="Alpha Secret Architecture",
        content="Confidential alpha design document.",
        tags=["alpha", "core"],
    )

    # Ofis 2 için özel kayıt
    mem.store_memory(
        office_id="office_beta",
        title="Beta UI Layout",
        content="Confidential beta pixel coordinates.",
        tags=["beta", "ui"],
    )

    # Genel şablon kayıt
    mem.store_memory(
        office_id="global_template",
        title="Company Coding Standards",
        content="PEP8, Type Annotations, 100% pytest pass rate.",
        tags=["standards", "global"],
        is_global=True,
    )

    # 1. Office Alpha araması: Beta içeriği ASLA dönmemeli
    alpha_results = mem.search_memory("office_alpha", query="Confidential")
    alpha_titles = [r.title for r in alpha_results]
    assert "Alpha Secret Architecture" in alpha_titles
    assert "Beta UI Layout" not in alpha_titles  # İZOLASYON KORUNDU

    # 2. Office Alpha araması: Genel şablon görünmeli
    alpha_global_search = mem.search_memory("office_alpha", query="Coding Standards")
    assert len(alpha_global_search) > 0
    assert alpha_global_search[0].title == "Company Coding Standards"

    # 3. Office Beta araması: Alpha içeriği ASLA dönmemeli
    beta_results = mem.search_memory("office_beta", query="design")
    beta_titles = [r.title for r in beta_results]
    assert "Alpha Secret Architecture" not in beta_titles

    # 4. Yetkisiz silme koruması
    alpha_rec = alpha_results[0]
    with pytest.raises(PermissionError):
        mem.delete_record(requesting_office_id="office_beta", record_id=alpha_rec.record_id)


def test_obsidian_markdown_generation():
    rec = MemoryRecord(
        office_id="office_x",
        agent_id="agent_arch",
        title="System Design Note",
        content="Clean hexagonal architecture specifications.",
        tags=["hexagonal", "design"],
    )
    md = rec.to_obsidian_markdown()
    assert "---" in md
    assert "title: System Design Note" in md
    assert "office_id: office_x" in md
    assert "tags: [hexagonal, design]" in md
    assert "# System Design Note" in md


def test_memory_graph_bridge_generation():
    cfg = OfficeConfig(
        office_id="off_graph_test",
        name="Graph Test Workspace",
        project_root="C:/graph_test",
        orchestrator_agent_id="orch_graph_01",
    )
    orch = OfficeOrchestrator(config=cfg)
    orch.initialize_default_specialists()

    task = orch.add_task(
        title="Build Knowledge Graph Node",
        description="Verify edge connectivity",
        acceptance_criteria=["Valid graph JSON"],
    )

    mem = OfficeMemoryPartition()
    mem.store_memory(
        office_id=cfg.office_id,
        title="Graph Bridge Documentation",
        content="Nodes and edges visualizer bridge specs.",
        tags=["graph", "spec"],
    )

    graph_data = MemoryGraphBridge.generate_office_graph(orch, memory_partition=mem)
    assert "nodes" in graph_data
    assert "edges" in graph_data

    node_types = {n["type"] for n in graph_data["nodes"]}
    assert "office_hub" in node_types
    assert "orchestrator" in node_types
    assert "task" in node_types
    assert "memory_note" in node_types

    edge_relationships = {e["relationship"] for e in graph_data["edges"]}
    assert "leads" in edge_relationships
    assert "supervises" in edge_relationships
    assert "stores_memory" in edge_relationships
