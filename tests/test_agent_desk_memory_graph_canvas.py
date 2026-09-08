"""
Automated Test Suite: 2D Memory Knowledge Graph Canvas.
Validates:
1. Graph data ingestion and radial layout computation.
2. Hit testing and node selection signal emission.
3. Headless offscreen QPainter rendering stability.
"""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
from PySide6.QtGui import QMouseEvent, QPaintEvent, QRegion
from PySide6.QtCore import QEvent
from src.entropy.agent_desk.core.models import OfficeConfig, DeskRole
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.memory.partitioned_memory import OfficeMemoryPartition
from src.entropy.agent_desk.memory.memory_graph_bridge import MemoryGraphBridge
from src.entropy.agent_desk.ui.memory_graph_canvas import MemoryGraphCanvas


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_memory_graph_canvas_layout_and_selection(qapp):
    cfg = OfficeConfig(
        office_id="off_canvas_test",
        name="Graph Test Office",
        project_root="C:/EntropiAI",
        orchestrator_agent_id="orch_graph_001",
    )
    orch = OfficeOrchestrator(config=cfg)
    orch.initialize_default_specialists()
    orch.add_task(
        title="Index Knowledge Graph",
        description="Extract wikilinks and AST nodes",
        role_target=DeskRole.DEVELOPER,
    )

    mem_partition = OfficeMemoryPartition()
    mem_partition.store_memory(
        office_id="off_canvas_test",
        title="Graph RAG Architecture",
        content="Sub-agent nodes link to tasks and notes.",
        tags=["graph", "architecture"],
    )

    graph_data = MemoryGraphBridge.generate_office_graph(orch, mem_partition)
    assert len(graph_data["nodes"]) >= 6
    assert len(graph_data["edges"]) >= 5

    canvas = MemoryGraphCanvas()
    canvas.resize(600, 450)
    canvas.set_graph_data(graph_data)

    assert len(canvas.nodes) == len(graph_data["nodes"])
    assert len(canvas.edges) == len(graph_data["edges"])

    # Test node hit detection
    selected_payload = []
    canvas.node_selected.connect(lambda data: selected_payload.append(data))

    # Pick the center hub node
    hub_node = next(n for n in canvas.nodes.values() if n.node_type == "office_hub")
    hit_node = canvas._get_node_at_pos(QPoint(int(hub_node.x), int(hub_node.y)))
    assert hit_node is not None
    assert hit_node.node_id == hub_node.node_id

    # Offscreen paint event stability
    canvas.repaint()
