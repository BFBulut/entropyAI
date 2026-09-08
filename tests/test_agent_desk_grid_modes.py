"""
Automated Pytest Suite: Office Grid Modes (Izgara Modları).
Verifies:
1. Core OfficeGridMode enum, validation, and OfficeGridLayoutCalculator.
2. OfficeConfig grid_mode persistence, serialization, and typing invariants.
3. OfficeOrchestrator set_grid_mode, get_grid_mode, and event emission.
4. TerminalGridWidget switching between all 6 grid modes (Tabbed, 1x2 Split, 2x2 Quad, 3x3 Matrix, 1+3 Focus, Adaptive NxM).
5. Backwards compatibility for is_grid_mode and _set_grid_mode().
6. PixelCanvas apply_grid_mode desk rearrangement.
7. OfficeDetailWidget bidirectional synchronization of grid modes.
"""

import os
import pytest
from PySide6.QtWidgets import QApplication
from src.entropy.agent_desk.core.models import (
    DeskRole,
    TaskStatus,
    TaskItem,
    AgentPersona,
    OfficeConfig,
    OfficeGridMode,
    OfficeGridLayoutCalculator,
)
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.ui.terminal_grid_widget import TerminalGridWidget
from src.entropy.agent_desk.ui.agent_terminal_pane import AgentTerminalPane
from src.entropy.agent_desk.ui.pixel_canvas import PixelCanvas
from src.entropy.agent_desk.ui.office_detail_widget import OfficeDetailWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])
    return app


def test_office_grid_mode_enum_and_calculator():
    """Verifies that all 6 grid modes exist and calculator returns correct coordinate geometries."""
    assert OfficeGridMode.TABBED.value == "tabbed"
    assert OfficeGridMode.SPLIT_1X2.value == "split_1x2"
    assert OfficeGridMode.SPLIT_2X2.value == "split_2x2"
    assert OfficeGridMode.SPLIT_3X3.value == "split_3x3"
    assert OfficeGridMode.FOCUS_1_PLUS_3.value == "focus_1_plus_3"
    assert OfficeGridMode.ADAPTIVE.value == "adaptive"

    # Max Panes
    assert OfficeGridLayoutCalculator.get_max_panes(OfficeGridMode.TABBED) is None
    assert OfficeGridLayoutCalculator.get_max_panes(OfficeGridMode.SPLIT_1X2) == 2
    assert OfficeGridLayoutCalculator.get_max_panes(OfficeGridMode.SPLIT_2X2) == 4
    assert OfficeGridLayoutCalculator.get_max_panes(OfficeGridMode.SPLIT_3X3) == 9
    assert OfficeGridLayoutCalculator.get_max_panes(OfficeGridMode.FOCUS_1_PLUS_3) == 4
    assert OfficeGridLayoutCalculator.get_max_panes(OfficeGridMode.ADAPTIVE) is None

    # Empty count
    assert OfficeGridLayoutCalculator.calculate_positions(OfficeGridMode.SPLIT_2X2, 0) == []

    # TABBED: all at (0, 0, 1, 1)
    pos_tab = OfficeGridLayoutCalculator.calculate_positions(OfficeGridMode.TABBED, 3)
    assert len(pos_tab) == 3
    assert all(p == (0, 0, 1, 1) for p in pos_tab)

    # SPLIT_1X2: 2 items side-by-side
    pos_1x2 = OfficeGridLayoutCalculator.calculate_positions(OfficeGridMode.SPLIT_1X2, 2)
    assert pos_1x2 == [(0, 0, 1, 1), (0, 1, 1, 1)]

    # SPLIT_2X2: 4 items in 2x2 square
    pos_2x2 = OfficeGridLayoutCalculator.calculate_positions(OfficeGridMode.SPLIT_2X2, 4)
    assert pos_2x2 == [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)]

    # SPLIT_3X3: 9 items in 3x3 matrix
    pos_3x3 = OfficeGridLayoutCalculator.calculate_positions(OfficeGridMode.SPLIT_3X3, 9)
    assert len(pos_3x3) == 9
    assert pos_3x3[0] == (0, 0, 1, 1)
    assert pos_3x3[4] == (1, 1, 1, 1)
    assert pos_3x3[8] == (2, 2, 1, 1)

    # FOCUS_1_PLUS_3: Master pane on left, 3 sub-panes stacked on right
    pos_focus = OfficeGridLayoutCalculator.calculate_positions(OfficeGridMode.FOCUS_1_PLUS_3, 4)
    assert len(pos_focus) == 4
    assert pos_focus[0] == (0, 0, 3, 2)  # Lead agent gets large 3-row, 2-col span
    assert pos_focus[1] == (0, 2, 1, 1)
    assert pos_focus[2] == (1, 2, 1, 1)
    assert pos_focus[3] == (2, 2, 1, 1)

    # ADAPTIVE: dynamically computes grid dimension based on sqrt
    pos_adapt_4 = OfficeGridLayoutCalculator.calculate_positions(OfficeGridMode.ADAPTIVE, 4)
    assert len(pos_adapt_4) == 4
    assert pos_adapt_4 == [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)]

    pos_adapt_6 = OfficeGridLayoutCalculator.calculate_positions(OfficeGridMode.ADAPTIVE, 6)
    assert len(pos_adapt_6) == 6
    # 6 items -> ceil(sqrt(6)) = 3 cols -> 2 rows
    assert pos_adapt_6[0] == (0, 0, 1, 1)
    assert pos_adapt_6[2] == (0, 2, 1, 1)
    assert pos_adapt_6[3] == (1, 0, 1, 1)

    # Invalid mode string raises ValueError
    with pytest.raises(ValueError):
        OfficeGridLayoutCalculator.calculate_positions("invalid_mode", 2)


def test_office_config_grid_mode():
    """Verifies OfficeConfig grid_mode default, validation, and serialization."""
    cfg = OfficeConfig(
        office_id="off_grid_01",
        name="Grid Test Office",
        project_root="C:/EntropiAI",
        orchestrator_agent_id="orch_01",
    )
    # Default is TABBED
    assert cfg.grid_mode == OfficeGridMode.TABBED

    # Update with enum
    cfg.set_grid_mode(OfficeGridMode.SPLIT_3X3)
    assert cfg.grid_mode == OfficeGridMode.SPLIT_3X3

    # Update with valid string
    cfg.set_grid_mode("focus_1_plus_3")
    assert cfg.grid_mode == OfficeGridMode.FOCUS_1_PLUS_3

    # Invalid string raises ValueError
    with pytest.raises(ValueError, match="Geçersiz ofis ızgara modu"):
        cfg.set_grid_mode("non_existent_mode")

    # Invalid type raises TypeError
    with pytest.raises(TypeError):
        cfg.set_grid_mode(12345)  # type: ignore

    # Serialization roundtrip
    dumped = cfg.model_dump()
    assert dumped["grid_mode"] == "focus_1_plus_3"
    reloaded = OfficeConfig(**dumped)
    assert reloaded.grid_mode == OfficeGridMode.FOCUS_1_PLUS_3


def test_office_orchestrator_grid_mode_events():
    """Verifies that OfficeOrchestrator emits events and triggers persistence on grid mode change."""
    events = []
    persisted = []

    cfg = OfficeConfig(
        office_id="off_orch_grid",
        name="Orch Grid Office",
        project_root="C:/EntropiAI",
        orchestrator_agent_id="orch_agent_01",
    )

    orch = OfficeOrchestrator(
        config=cfg,
        on_event=lambda ev, data: events.append((ev, data)),
        save_callback=lambda: persisted.append(True),
    )

    assert orch.get_grid_mode() == OfficeGridMode.TABBED

    # Change to SPLIT_1X2
    result_mode = orch.set_grid_mode("split_1x2")
    assert result_mode == OfficeGridMode.SPLIT_1X2
    assert orch.get_grid_mode() == OfficeGridMode.SPLIT_1X2
    assert len(persisted) == 1

    # Check event
    grid_events = [e for e in events if e[0] == "grid_mode_changed"]
    assert len(grid_events) == 1
    assert grid_events[0][1]["grid_mode"] == "split_1x2"
    assert grid_events[0][1]["office_id"] == "off_orch_grid"


def test_terminal_grid_widget_all_modes(qapp):
    """Verifies that TerminalGridWidget cleanly supports all 6 grid modes and retains panes."""
    grid = TerminalGridWidget()

    p1 = AgentTerminalPane(persona=AgentPersona(agent_id="a1", name="Lead", office_id="o1"))
    p2 = AgentTerminalPane(persona=AgentPersona(agent_id="a2", name="Dev", office_id="o1"))
    p3 = AgentTerminalPane(persona=AgentPersona(agent_id="a3", name="QA", office_id="o1"))
    p4 = AgentTerminalPane(persona=AgentPersona(agent_id="a4", name="Sec", office_id="o1"))

    grid.add_or_update_pane("a1", p1, "Lead")
    grid.add_or_update_pane("a2", p2, "Dev")
    grid.add_or_update_pane("a3", p3, "QA")
    grid.add_or_update_pane("a4", p4, "Sec")

    emitted_modes = []
    grid.grid_mode_changed.connect(emitted_modes.append)

    # 1. Default Tabbed Mode
    assert not grid.is_grid_mode
    assert grid.active_grid_mode == OfficeGridMode.TABBED
    assert not grid.tab_widget.isHidden()
    assert grid.grid_container.isHidden()
    assert grid.tab_widget.count() == 4

    # 2. Switch to 1x2 Split Mode (limits to 2 panes)
    grid._set_split_1x2_mode()
    assert grid.is_grid_mode
    assert grid.active_grid_mode == OfficeGridMode.SPLIT_1X2
    assert grid.tab_widget.isHidden()
    assert not grid.grid_container.isHidden()
    assert grid.grid_layout.count() == 2
    assert emitted_modes[-1] == "split_1x2"

    # 3. Switch to 2x2 Quad Grid (4 panes)
    grid._set_grid_mode()
    assert grid.is_grid_mode
    assert grid.active_grid_mode == OfficeGridMode.SPLIT_2X2
    assert grid.grid_layout.count() == 4
    assert emitted_modes[-1] == "split_2x2"

    # 4. Switch to 3x3 Matrix Grid
    grid._set_split_3x3_mode()
    assert grid.active_grid_mode == OfficeGridMode.SPLIT_3X3
    assert grid.grid_layout.count() == 4
    assert emitted_modes[-1] == "split_3x3"

    # 5. Switch to 1+3 Focus Grid
    grid._set_focus_1_plus_3_mode()
    assert grid.active_grid_mode == OfficeGridMode.FOCUS_1_PLUS_3
    assert grid.grid_layout.count() == 4
    assert emitted_modes[-1] == "focus_1_plus_3"

    # 6. Switch to Adaptive Grid
    grid._set_adaptive_mode()
    assert grid.active_grid_mode == OfficeGridMode.ADAPTIVE
    assert grid.grid_layout.count() == 4
    assert emitted_modes[-1] == "adaptive"

    # 7. Switch back to Tab Mode
    grid._set_tab_mode()
    assert not grid.is_grid_mode
    assert grid.active_grid_mode == OfficeGridMode.TABBED
    assert not grid.tab_widget.isHidden()
    assert grid.grid_container.isHidden()
    assert grid.tab_widget.count() == 4
    assert emitted_modes[-1] == "tabbed"

    # 8. Backwards compatibility property setter
    grid.is_grid_mode = True
    assert grid.active_grid_mode == OfficeGridMode.SPLIT_2X2
    grid.is_grid_mode = False
    assert grid.active_grid_mode == OfficeGridMode.TABBED


def test_pixel_canvas_apply_grid_mode(qapp):
    """Verifies that PixelCanvas rearranges desks based on office grid modes."""
    canvas = PixelCanvas()
    lead = AgentPersona(agent_id="lead", name="Lead", office_id="o1")
    subs = [
        AgentPersona(agent_id="s1", name="S1", office_id="o1"),
        AgentPersona(agent_id="s2", name="S2", office_id="o1"),
        AgentPersona(agent_id="s3", name="S3", office_id="o1"),
    ]
    canvas.set_personas(lead, subs)

    # 1. Tabbed / Classic default
    canvas.apply_grid_mode(OfficeGridMode.TABBED)
    assert canvas.current_grid_mode == OfficeGridMode.TABBED
    assert canvas.desks[0].x == 270 and canvas.desks[0].y == 30

    # 2. 1x2 Split mode
    canvas.apply_grid_mode(OfficeGridMode.SPLIT_1X2)
    assert canvas.current_grid_mode == OfficeGridMode.SPLIT_1X2
    assert canvas.desks[0].x == 150 and canvas.desks[0].y == 120
    assert canvas.desks[1].x == 420 and canvas.desks[1].y == 120

    # 3. 2x2 Grid mode
    canvas.apply_grid_mode(OfficeGridMode.SPLIT_2X2)
    assert canvas.current_grid_mode == OfficeGridMode.SPLIT_2X2
    assert canvas.desks[0].x == 150 and canvas.desks[0].y == 40

    # 4. 3x3 Matrix mode
    canvas.apply_grid_mode(OfficeGridMode.SPLIT_3X3)
    assert canvas.current_grid_mode == OfficeGridMode.SPLIT_3X3

    # 5. 1+3 Focus mode
    canvas.apply_grid_mode(OfficeGridMode.FOCUS_1_PLUS_3)
    assert canvas.current_grid_mode == OfficeGridMode.FOCUS_1_PLUS_3
    assert canvas.desks[0].x == 280 and canvas.desks[0].y == 40

    # 6. Adaptive mode
    canvas.apply_grid_mode(OfficeGridMode.ADAPTIVE)
    assert canvas.current_grid_mode == OfficeGridMode.ADAPTIVE


def test_office_detail_widget_grid_mode_sync(qapp):
    """Verifies that OfficeDetailWidget synchronizes grid modes with OfficeOrchestrator."""
    cfg = OfficeConfig(
        office_id="off_detail_grid",
        name="Sync Grid Office",
        project_root="C:/EntropiAI",
        orchestrator_agent_id="orch_detail_01",
        grid_mode=OfficeGridMode.SPLIT_1X2,
    )
    orch = OfficeOrchestrator(config=cfg)
    detail = OfficeDetailWidget(orchestrator=orch)

    # 1. Initial sync from config
    assert detail.terminal_grid.active_grid_mode == OfficeGridMode.SPLIT_1X2
    assert detail.pixel_canvas.current_grid_mode == OfficeGridMode.SPLIT_1X2

    # 2. Switching mode on terminal_grid updates orchestrator
    detail.terminal_grid.set_grid_mode(OfficeGridMode.SPLIT_3X3)
    assert orch.get_grid_mode() == OfficeGridMode.SPLIT_3X3
    assert detail.pixel_canvas.current_grid_mode == OfficeGridMode.SPLIT_3X3

    # 3. Orchestrator event updates detail widget
    detail._on_orchestrator_event("grid_mode_changed", {"grid_mode": "focus_1_plus_3"})
    assert detail.terminal_grid.active_grid_mode == OfficeGridMode.FOCUS_1_PLUS_3
    assert detail.pixel_canvas.current_grid_mode == OfficeGridMode.FOCUS_1_PLUS_3

    detail.cleanup()
