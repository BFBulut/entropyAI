"""
Faz 7 — Agent Desk penceresi iyileştirmeleri.

Kapsam: oturma yerlerinin yayılması, pencere profili, Bellek mini grafı,
görev/kart sağlayıcı-model-efor-bütçe seçimi, kadro rozeti, Projeler sekmesi
ve başlık tutarlılığı.

Hepsi offscreen koşar, model çağrısı ve harness başlatma YOKTUR; sözleşme
nesneleri (TaskBoard, DeskRegistry, OfficeGraph) sahte nesnelerle temsil edilir.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeSpec(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


# --------------------------------------------------------------- 1) oturma


@pytest.fixture(scope="module")
def layout(qapp):
    from entropy.desk.engine.layout import load_layout

    return load_layout("")


def test_table_and_sofa_cells_are_seats(layout):
    """TABLE_* dört yanı ve SOFA_* hücreleri de oturma yeri üretir."""
    from entropy.desk.engine.layout import Layout

    occupied = layout.occupied_cells()
    table_seats, sofa_seats = 0, 0
    for placed in layout.furniture:
        vid = placed.variant.variant_id
        seats = layout._seats_for(placed, occupied)
        if "TABLE" in vid:
            table_seats += len(seats)
        if "SOFA" in vid:
            sofa_seats += len(seats)
    assert table_seats >= 2, "masanın yanları yer üretmedi"
    assert sofa_seats >= 1, "koltuk hücreleri yer üretmedi"
    assert isinstance(layout, Layout)


def test_ten_agents_never_share_neighbouring_cells(layout):
    """10 ajanlı ofiste hiçbir iki karakter komşu (çapraz dahil) hücrede olmaz."""
    from entropy.desk.engine.layout import _cheb

    seats = layout.seats_for(10)
    assert len(seats) == 10
    cells = [s.cell for s in seats]
    assert len(set(cells)) == 10
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            assert _cheb(a, b) >= 2, f"{a} ile {b} komşu"


def test_orchestrator_seat_is_nearest_desk_to_center(layout):
    """İlk yer (orkestratör) hâlâ merkeze en yakın masadır."""
    seats = layout.seats_for(10)
    center = layout.center_cell()
    desks = [s for s in layout.seats() if s.source == "desk"]
    best = min(desks, key=lambda s: abs(s.col - center[0]) + abs(s.row - center[1]))
    assert seats[0].cell == best.cell


def test_floor_fallback_keeps_two_cell_spacing(layout):
    """Mobilya yerleri bitince zemin yedekleri 2 hücre aralıklı gelir."""
    from entropy.desk.engine.layout import _cheb

    seats = layout.seats_for(30)
    floor = [s for s in seats if s.source == "floor"]
    if not floor:
        pytest.skip("bu düzende zemin yedeği gerekmedi")
    for seat in floor[: max(1, len(floor) // 2)]:
        others = [s for s in seats if s is not seat]
        assert min(_cheb(seat.cell, o.cell) for o in others) >= 1


# --------------------------------------------------------------- 2) pencere


def test_half_screen_geometry_right_half(qapp):
    from entropy.ui.window_sizing import half_screen_geometry

    area = QRect(0, 0, 1920, 1040)
    geom = half_screen_geometry(area, width_ratio=0.5, height_ratio=0.9, side="right")
    assert geom.width() == 960
    assert geom.height() == 936
    assert geom.right() <= area.right() + 1
    assert geom.x() == 960
    assert area.contains(geom)


def test_half_screen_geometry_left_side_and_small_screen(qapp):
    from entropy.ui.window_sizing import half_screen_geometry

    area = QRect(0, 0, 800, 600)
    geom = half_screen_geometry(area, side="left", min_size=(900, 560))
    assert geom.x() == 0
    assert geom.width() <= 800 and geom.height() <= 600


def test_desk_ratios_and_min_size(qapp):
    from entropy.desk import window as dw

    assert dw.DESK_SCREEN_RATIO == pytest.approx(0.5)
    assert dw.DESK_HEIGHT_RATIO == pytest.approx(0.9)
    assert dw.DESK_SECONDARY_RATIO == pytest.approx(0.88)
    assert dw.DESK_MIN_SIZE[0] <= 900


def test_panel_minimum_widths_sum_below_900(qapp):
    """Üç sütunun asgari genişlik toplamı yarım ekrana (≈900 px) sığar."""
    from entropy.desk.window import AgentDeskWindow

    window = AgentDeskWindow(office_registry=None, agent_registry=None)
    total = (
        window.offices_panel.minimumWidth()
        + window.tabs.minimumWidth()
        + window.roster_panel.minimumWidth()
    )
    assert total <= 900, f"asgari genişlik toplamı {total} px"
    # Açık minimumlar örtük ipuçlarını ezmeli: pencere gerçekten 900'e insin.
    window.resize(900, 700)
    QApplication.processEvents()
    assert window.width() <= 902
    for panel in (window.offices_panel, window.tabs, window.roster_panel):
        assert panel.width() > 0
        assert panel.mapTo(window, panel.rect().topRight()).x() <= window.width() + 2
    window.close()
    window.deleteLater()


# --------------------------------------------------------------- 3) bellek


VIEW_DATA = {
    "nodes": [
        {"id": "ofis-x", "name": "arastirma", "group": "ofis", "kind": "ofis",
         "degree": 3, "note": "kok"},
        {"id": "karar-1", "name": "Kaynak seçimi", "group": "karar", "kind": "karar",
         "degree": 2, "note": "Birincil kaynak olarak X seçildi."},
        {"id": "ajan-y", "name": "arastirmaci", "group": "ajan", "kind": "ajan",
         "degree": 1, "note": "agents/arastirmaci", "virtual": True},
    ],
    "links": [
        {"source": "karar-1", "target": "ofis-x", "type": "member_of",
         "alias": "member_of", "weight": 0.5},
        {"source": "ajan-y", "target": "ofis-x", "type": "member_of",
         "alias": "member_of", "weight": 0.5},
    ],
}


def test_memory_panel_draws_graph_and_shows_note(qapp):
    from entropy.desk.memory_panel import OfficeMemoryPanel, kind_color

    panel = OfficeMemoryPanel(office="")
    panel.canvas.set_data(VIEW_DATA)
    panel.resize(600, 400)
    assert len(panel.canvas.nodes) == 3
    # Tür rengi türe göre ayrışır.
    assert kind_color("karar") != kind_color("ajan")
    body = panel.show_node("karar-1")
    assert "Birincil kaynak" in body
    assert "Kaynak seçimi" in panel.note_view.toPlainText()
    panel.deleteLater()


def test_memory_panel_virtual_node_shows_only_name(qapp):
    from entropy.desk.memory_panel import OfficeMemoryPanel

    panel = OfficeMemoryPanel(office="")
    panel.canvas.set_data(VIEW_DATA)
    shown = panel.show_node("ajan-y")
    assert shown == "arastirmaci"
    text = panel.note_view.toPlainText()
    assert "arastirmaci" in text
    assert "agents/arastirmaci" not in text
    panel.deleteLater()


def test_memory_panel_click_selects_node(qapp):
    from entropy.desk.memory_panel import MiniGraphCanvas

    canvas = MiniGraphCanvas()
    canvas.resize(400, 300)
    canvas.set_data(VIEW_DATA)
    pos = canvas._screen_pos("ofis-x")
    assert pos is not None
    assert canvas.node_at(QPoint(int(pos.x()), int(pos.y()))) == "ofis-x"
    canvas.deleteLater()


def test_memory_panel_survives_missing_office(qapp):
    from entropy.desk.memory_panel import load_office_view_data

    data = load_office_view_data("")
    assert data == {"nodes": [], "links": []}


# ------------------------------------------------- 4) sağlayıcı/model/efor


def test_assign_dialog_has_execution_fields(qapp):
    from entropy.ui.widgets.agents_widget import AssignTaskDialog

    dialog = AssignTaskDialog(agent_name="arastirmaci", skills=["arastirma"],
                              provider="claude", model="opus", effort="low")
    dialog.title_input.setText("Rapor")
    dialog.goal_input.setPlainText("Kaynakları tara")
    dialog.budget_input.setText("12000")
    data = dialog.get_data()
    assert data["provider"] == "claude"
    assert data["model"] == "opus"
    assert data["effort"] == "low"
    assert data["budget_tokens"] == 12000
    dialog.deleteLater()


class FakeBoard:
    def __init__(self, cards=None):
        self.cards = list(cards or [])
        self.updated = []

    def list(self):
        return list(self.cards)

    def get(self, card_id):
        for card in self.cards:
            if card["id"] == card_id:
                return card
        return None

    def update(self, *args, **kwargs):
        self.updated.append((args, kwargs))
        return True

    def run(self, card_id):
        return True


def make_card(card_id="c1", **over):
    data = {
        "id": card_id, "title": f"Kart {card_id}", "status": "backlog",
        "agent": "arastirmaci", "provider": "agy", "model": "", "skill": "",
        "goal": "hedef", "criteria": [], "output_paths": [], "summary": "",
        "path": "", "office": "arastirma", "parent": "", "children": [],
        "notes": "", "budget_tokens": 0, "project": "",
    }
    data.update(over)
    return FakeSpec(data)


def test_card_detail_exposes_and_applies_settings(qapp):
    from entropy.ui.widgets.task_board_widget import TaskBoardWidget

    board = FakeBoard([make_card("c1")])
    widget = TaskBoardWidget(board=board, office="arastirma")
    widget.select_card("c1")
    detail = widget.detail_panel
    detail.provider_combo.setCurrentText("claude")
    detail.model_combo.setCurrentText("opus")
    detail.effort_combo.setCurrentText("high")
    detail.budget_input.setText("5000")
    payload = detail.settings_payload()
    assert payload == {"provider": "claude", "model": "opus",
                       "effort": "high", "budget_tokens": 5000}
    assert widget.update_card_settings("c1", payload) is True
    assert board.updated, "pano güncellenmedi"
    widget.deleteLater()


# --------------------------------------------------------------- 5) kadro


class FakeAgentsRegistry:
    def __init__(self, agents):
        self._agents = list(agents)

    def list(self):
        return list(self._agents)

    def get(self, name):
        for agent in self._agents:
            if agent["name"] == name:
                return agent
        return None


def make_agent(name, **over):
    data = {"name": name, "role": "worker", "office": "arastirma",
            "description": "", "provider": "agy", "model": "", "effort": "",
            "skills": [], "tools_policy": "", "memory_path": "", "prompt": "",
            "path": "", "updated_at": ""}
    data.update(over)
    return FakeSpec(data)


class FakeOfficeRegistry:
    def __init__(self, office):
        self._office = office

    def list(self):
        return [self._office]

    def get(self, name):
        return self._office if self._office["name"] == name else None


def test_orchestrator_created_agents_get_badge(qapp):
    from entropy.ui.widgets.agents_widget import AgentsWidget

    office = FakeSpec({"name": "arastirma", "orchestrator": "lider",
                       "evaluator": "", "members": ["lider", "yazar"],
                       "default_provider": "agy", "default_model": ""})
    registry = FakeAgentsRegistry([
        make_agent("lider", role="orchestrator"),
        make_agent("yazar"),
        make_agent("veri-cikarici"),   # dosyası var, members'ta yok
    ])
    widget = AgentsWidget(registry=registry, office="arastirma",
                          office_registry=FakeOfficeRegistry(office))
    created = widget.orchestrator_created_names()
    assert created == {"veri-cikarici"}
    badges = {card.agent_name: getattr(card, "origin_badge", None)
              for card in widget.cards}
    assert badges.get("veri-cikarici") is not None, "rozet çizilmedi"
    assert "orkestratör oluşturdu" in badges["veri-cikarici"].text()
    assert badges.get("yazar") is None
    assert badges.get("lider") is None
    widget.deleteLater()


# ------------------------------------------------------------- 6) projeler


class FakeProject(dict):
    def __getattr__(self, item):
        return self[item]


class FakeDesk:
    def __init__(self):
        self.projects = {}

    def list_projects(self, office):
        return list(self.projects.get(office, []))

    def create_project(self, office, project):
        entry = FakeProject({"name": getattr(project, "name", ""),
                             "office": office,
                             "goal": getattr(project, "goal", ""),
                             "charter": getattr(project, "charter", "")})
        self.projects.setdefault(office, []).append(entry)
        return entry


def test_projects_panel_lists_adds_and_filters(qapp):
    from entropy.desk.projects_panel import ProjectsPanel

    desk = FakeDesk()
    board = FakeBoard([make_card("c1", project="site"),
                       make_card("c2", project="site", status="done"),
                       make_card("c3", project="")])
    panel = ProjectsPanel(office="arastirma", desk=desk, board=board)
    assert panel.add_project({"name": "site", "goal": "web sitesi"}) is True
    assert panel.project_names() == ["site"]
    assert panel.list_widget.count() == 1
    assert "2 kart" in panel.list_widget.item(0).text()

    seen = []
    panel.project_filter_changed.connect(seen.append)
    panel.list_widget.setCurrentRow(0)
    panel.apply_filter()
    assert seen == ["site"]
    assert panel.filtered_project == "site"
    panel.clear_filter()
    assert seen == ["site", ""]
    panel.deleteLater()


def test_board_project_filter_narrows_cards(qapp):
    from entropy.ui.widgets.task_board_widget import TaskBoardWidget

    board = FakeBoard([make_card("c1", project="site"), make_card("c2", project="")])
    widget = TaskBoardWidget(board=board, office="arastirma")
    assert len(widget.list_cards()) == 2
    widget.set_project_filter("site")
    assert [str(c["id"]) for c in widget.list_cards()] == ["c1"]
    widget.set_project_filter("")
    assert len(widget.list_cards()) == 2
    widget.deleteLater()


# --------------------------------------------------------------- 7) başlık


def test_window_tabs_title_and_spend_badge(qapp):
    from entropy.desk.window import AgentDeskWindow

    window = AgentDeskWindow(office_registry=None, agent_registry=None)
    tabs = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    # Faz 10-B: "Akış" sekmesi "Terminaller" oldu (ajan başına terminal bölmesi).
    assert tabs == ["Kartlar", "Terminaller", "Projeler", "Bellek"]
    window.set_office("")
    assert "ENTROPY AGENT DESK" in window.header_label.text()
    assert window.windowTitle().startswith("Entropy Agent Desk ·")
    # Harcama rozeti veri yoksa gizlidir (uydurma sayı gösterilmez).
    assert window.spend_label.isVisible() is False
    window.close()
    window.deleteLater()


def test_project_filter_signal_switches_to_cards_tab(qapp):
    from entropy.desk.window import AgentDeskWindow, TAB_CARDS

    window = AgentDeskWindow(office_registry=None, agent_registry=None)
    window.tabs.setCurrentIndex(2)
    window._on_project_filter("site")
    assert window.tabs.currentIndex() == TAB_CARDS
    assert window.board_panel.board_widget.project_filter == "site"
    window.close()
    window.deleteLater()
