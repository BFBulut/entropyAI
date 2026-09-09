"""
Faz 3b arayüz testleri: Agent Desk penceresi, ofis sahnesi ve panelleri.

Ofis kayıt defteri (`entropy.agents.offices`) ve ofis harness'ı başka bir ajan
tarafından yazılıyor; buradaki testler sözleşmeye uyan sahte nesneler kullanır
(OfficeSpec alan adları, list/get/create/update/delete). Böylece arayüz gerçek
uygulama gelmeden doğrulanır. Gerçek süreç başlatan hiçbir çağrı yok
(`TaskBoard.run` / `OfficeHarness.start` çağrılmaz).
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent

from entropy.core.event_bus import bus
from entropy.desk import scene as scene_mod
from entropy.desk.board_panel import BoardPanel
from entropy.desk.offices_panel import OfficeEditDialog, OfficesPanel
from entropy.desk.roster_panel import RosterPanel
from entropy.desk.scene import (
    OfficeScene, STATE_ERROR, STATE_IDLE, STATE_THINKING, STATE_WAITING, STATE_WORKING,
)
from entropy.desk.stream_panel import StreamPanel
from entropy.desk.window import (
    AgentDeskWindow, existing_desk_window, open_desk_window, reset_desk_window,
)


# --------------------------------------------------------------- sahte sözleşme

class FakeSpec(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def make_office(name="arastirma", **over):
    data = {
        "name": name,
        "purpose": "Araştırma yapar ve raporlar",
        "orchestrator": "lider",
        "evaluator": "denetci",
        "members": ["lider", "arastirmaci", "yazar", "denetci"],
        "default_provider": "agy",
        "default_model": "gemini-3.8-flash-high",
        "max_parallel": 2,
        "budget_tokens": 60000,
        "charter": "Kaynaklı, kısa rapor.",
        "path": "",
        "updated_at": "2026-09-09T10:00:00",
    }
    data.update(over)
    return FakeSpec(data)


def make_agent(name="arastirmaci", **over):
    data = {
        "name": name, "role": "worker", "office": "arastirma",
        "description": "", "provider": "agy", "model": "", "effort": "medium",
        "skills": [], "tools_policy": "", "memory_path": "", "prompt": "",
        "path": "", "updated_at": "",
    }
    data.update(over)
    return FakeSpec(data)


def make_card(card_id="c1", **over):
    data = {
        "id": card_id, "title": f"Kart {card_id}", "status": "backlog",
        "agent": "arastirmaci", "provider": "agy", "model": "", "skill": "",
        "goal": "hedef", "criteria": [], "created_at": "2026-09-09T10:00:00",
        "started_at": "", "finished_at": "", "output_paths": [], "summary": "",
        "path": "", "office": "arastirma", "parent": "", "children": [],
        "grade": "", "verdict": "", "attempt": 0,
    }
    data.update(over)
    return FakeSpec(data)


class FakeOfficeRegistry:
    def __init__(self, offices=None):
        self._offices = list(offices or [])
        self.created, self.updated, self.deleted = [], [], []

    def list(self):
        return list(self._offices)

    def get(self, name):
        for office in self._offices:
            if office["name"] == name:
                return office
        return None

    def create(self, spec):
        data = spec if isinstance(spec, dict) else dict(spec.__dict__)
        self.created.append(data)
        self._offices.append(FakeSpec(data))
        return self._offices[-1]

    def update(self, spec, original_name=None):
        data = spec if isinstance(spec, dict) else dict(spec.__dict__)
        self.updated.append(data)
        key = original_name or data.get("name")
        for i, office in enumerate(self._offices):
            if office["name"] == key:
                merged = dict(office)
                merged.update(data)
                self._offices[i] = FakeSpec(merged)
                return self._offices[i]
        return None

    def delete(self, name):
        self.deleted.append(name)
        self._offices = [o for o in self._offices if o["name"] != name]
        return True


class FakeAgentRegistry:
    def __init__(self, agents=None):
        self._agents = list(agents or [])
        self.updated = []

    def list(self):
        return list(self._agents)

    def get(self, name):
        for agent in self._agents:
            if agent["name"] == name:
                return agent
        return None

    def create(self, spec):
        data = spec if isinstance(spec, dict) else dict(spec.__dict__)
        self._agents.append(FakeSpec(data))
        return self._agents[-1]

    def update(self, spec, original_name=None):
        data = spec if isinstance(spec, dict) else dict(spec.__dict__)
        self.updated.append(data)
        key = original_name or data.get("name")
        for i, agent in enumerate(self._agents):
            if agent["name"] == key:
                merged = dict(agent)
                merged.update(data)
                self._agents[i] = FakeSpec(merged)
                return self._agents[i]
        return None

    def delete(self, name):
        self._agents = [a for a in self._agents if a["name"] != name]
        return True


class FakeBoard:
    """Kart panosu; `run` bilerek yoktur — test gerçek süreç başlatamasın."""

    def __init__(self, cards=None):
        self._cards = list(cards or [])

    def list(self):
        return list(self._cards)

    def get(self, card_id):
        for card in self._cards:
            if card["id"] == card_id:
                return card
        return None


@pytest.fixture
def offices():
    return FakeOfficeRegistry([
        make_office("arastirma"),
        make_office("yazim", orchestrator="editor", evaluator="",
                    members=["editor", "yazar"], purpose="Metin üretir"),
    ])


@pytest.fixture
def agents():
    return FakeAgentRegistry([
        make_agent("lider", role="orchestrator"),
        make_agent("arastirmaci"),
        make_agent("yazar", office="yazim"),
        make_agent("denetci", role="evaluator"),
        make_agent("bagimsiz", office=""),
    ])


@pytest.fixture
def board():
    return FakeBoard([
        make_card("ust", parent="", children=["alt1", "alt2"], status="running"),
        make_card("alt1", parent="ust", agent="arastirmaci"),
        make_card("alt2", parent="ust", agent="yazar"),
        make_card("baska", office="yazim", agent="yazar"),
    ])


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_desk_window()
    yield
    reset_desk_window()


@pytest.fixture
def window(qapp, offices, agents, board):
    win = AgentDeskWindow(office_registry=offices, agent_registry=agents, board=board)
    yield win
    win.close()
    win.deleteLater()


# --------------------------------------------------------------- pencere

def test_window_is_independent_top_level(window):
    """Bağımsız üst pencere: Qt.Window bayrağı açık, ana pencereye gömülü değil."""
    assert bool(window.windowFlags() & Qt.WindowType.Window)
    assert window.parent() is None


def test_geometry_saved_and_restored(qapp, window, monkeypatch):
    """Konum/boyut config'e yazılır ve yeni pencerede geri yüklenir."""
    from entropy.core.config import config

    saved = {}
    monkeypatch.setattr(type(config), "save_settings", lambda self: saved.update(self.desk_geometry))
    window.setGeometry(120, 90, 1000, 700)
    payload = window.save_geometry()
    assert payload["width"] == 1000 and payload["height"] == 700
    assert saved["width"] == 1000  # config.save_settings çağrıldı

    other = AgentDeskWindow(office_registry=window.office_registry)
    assert other.restore_geometry(payload) is True
    # Boyut ekranın kullanılabilir alanıyla sınırlanır (offscreen ekran 800x600).
    from PySide6.QtGui import QGuiApplication

    available = QGuiApplication.primaryScreen().availableGeometry()
    # Faz 7: kullanicinin kaydettigi GECERLI geometri korunur; yalnizca ekranin
    # kullanilabilir alanini asan olculer kirpilir (Faz 6'daki %88 tavani yok).
    assert other.width() == min(1000, available.width())
    assert other.height() == min(700, available.height())
    other.close()
    other.deleteLater()


def test_geometry_falls_back_when_screen_missing(window):
    """Kayıtlı ekran bağlı değilse pencere birincil ekrana ortalanır, kaybolmaz."""
    from PySide6.QtGui import QGuiApplication

    payload = {"x": 9000, "y": 9000, "width": 900, "height": 600,
               "screen": "OLMAYAN-EKRAN", "maximized": False}
    assert window.restore_geometry(payload) is True
    available = QGuiApplication.primaryScreen().availableGeometry()
    assert available.contains(window.geometry().center())


def test_open_desk_window_is_single_instance(qapp, offices):
    first = open_desk_window(office_registry=offices)
    second = open_desk_window(office_registry=offices)
    assert first is second
    assert existing_desk_window() is first
    first.close()


def test_office_selection_propagates_to_panels(window):
    window.set_office("yazim")
    assert window.board_panel.office == "yazim"
    assert window.roster_panel.office == "yazim"
    assert window.stream_panel.office == "yazim"
    assert "editor" in window.scene.states()


def test_memory_tab_survives_missing_module(window):
    """Ofis belleği modülü yoksa Bellek sekmesi açıklayıcı metin gösterir."""
    window.set_office("arastirma")
    assert "MEMORY.md" in window.memory_view.toPlainText()


# --------------------------------------------------------------- ofis CRUD

def test_offices_panel_lists_and_selects(qapp, offices, agents):
    panel = OfficesPanel(registry=offices, agent_registry=agents)
    assert panel.office_names() == ["arastirma", "yazim"]
    assert panel.current_office == "arastirma"
    panel.select_office("yazim")
    assert panel.current_office == "yazim"


def test_office_dialog_collects_contract_fields(qapp, agents):
    dialog = OfficeEditDialog(agent_registry=agents)
    dialog.name_edit.setText("yeni-ofis")
    dialog.purpose_edit.setText("Deneme")
    dialog.orchestrator_combo.setCurrentText("lider")
    dialog.evaluator_combo.setCurrentText("denetci")
    for i in range(dialog.members_list.count()):
        if dialog.members_list.item(i).text() == "arastirmaci":
            dialog.members_list.item(i).setSelected(True)
    dialog.parallel_spin.setValue(3)
    dialog.budget_spin.setValue(40000)
    dialog.charter_edit.setPlainText("Tüzük")
    data = dialog.get_data()
    assert data["name"] == "yeni-ofis"
    assert data["max_parallel"] == 3 and data["budget_tokens"] == 40000
    # Orkestratör ve değerlendirici otomatik üye olur.
    assert set(["arastirmaci", "lider", "denetci"]).issubset(set(data["members"]))
    assert data["charter"] == "Tüzük"
    dialog.deleteLater()


def test_office_create_update_delete(qapp, offices, agents):
    panel = OfficesPanel(registry=offices, agent_registry=agents)
    assert panel.apply_office_save({"name": "yeni", "purpose": "p", "members": []}, None) is True
    assert "yeni" in panel.office_names()
    assert panel.apply_office_save({"name": "yeni", "purpose": "güncel", "members": []}, "yeni") is True
    assert offices.get("yeni")["purpose"] == "güncel"
    assert panel.delete_office("yeni", confirm=False) is True
    assert "yeni" not in panel.office_names()


# --------------------------------------------------------------- roster

def test_roster_filters_by_office(qapp, agents, offices, board):
    roster = RosterPanel(registry=agents, board=board, office_registry=offices, office="arastirma")
    names = roster.agent_names()
    assert set(names) == {"lider", "arastirmaci", "yazar", "denetci"}
    assert "bagimsiz" not in names
    # "yazim" ofisinin üyeleri editor+yazar; editor kayıt defterinde yok, o yüzden
    # listede yalnızca yazar görünür (var olmayan üye uydurulmaz).
    roster.set_office("yazim")
    assert set(roster.agent_names()) == {"yazar"}


def test_roster_role_assignment_updates_office_and_agent(qapp, agents, offices, board):
    roster = RosterPanel(registry=agents, board=board, office_registry=offices, office="arastirma")
    assert roster.assign_role("arastirmaci", "orchestrator") is True
    assert offices.get("arastirma")["orchestrator"] == "arastirmaci"
    assert agents.get("arastirmaci")["role"] == "orchestrator"


def test_roster_cards_have_role_buttons_only_in_office_mode(qapp, agents, offices, board):
    roster = RosterPanel(registry=agents, board=board, office_registry=offices, office="arastirma")
    card = roster.agents_widget.cards[0]
    assert hasattr(card, "make_orchestrator_btn")
    assert hasattr(card, "make_evaluator_btn")

    from entropy.ui.widgets.agents_widget import AgentsWidget

    plain = AgentsWidget(registry=agents, board=board)
    assert not hasattr(plain.cards[0], "make_orchestrator_btn")
    plain.deleteLater()


# --------------------------------------------------------------- kanban

def test_board_panel_filters_by_office_and_orders_tree(qapp, board):
    panel = BoardPanel(board=board, office="arastirma")
    widget = panel.board_widget
    ids = [str(c["id"]) for c in widget.list_cards()]
    assert "baska" not in ids  # başka ofisin kartı süzüldü
    assert set(ids) == {"ust", "alt1", "alt2"}

    backlog = widget.ordered_cards(widget.cards_in_column("backlog"))
    assert [c["id"] for c in backlog] == ["alt1", "alt2"]
    assert widget.card_depth(widget.get_card("alt1")) == 1
    assert widget.card_depth(widget.get_card("ust")) == 0


def test_board_panel_switch_office(qapp, board):
    panel = BoardPanel(board=board, office="arastirma")
    panel.set_office("yazim")
    assert [c["id"] for c in panel.board_widget.list_cards()] == ["baska"]


# --------------------------------------------------------------- sahne

def test_scene_layout_roles(qapp, offices):
    scene = OfficeScene(office=offices.get("arastirma"))
    scene.resize(900, 520)
    scene.relayout()
    roles = {s.agent: s.role for s in scene.slots}
    assert roles["lider"] == "orchestrator"
    assert roles["denetci"] == "evaluator"
    assert roles["arastirmaci"] == "worker"
    # Faz 6: yerleşim artık tile düzeninden gelir. Orkestratör bir MASAYA
    # (DESK+PC hücresi) oturur ve ofis merkezine en yakın masayı alır;
    # herkesin hücresi ayrıdır, karakterler üst üste binmez.
    orch = scene.slot_for("lider")
    assert orch.seat is not None and orch.seat.source == "desk"
    center = scene.layout.center_cell()
    desks = [s for s in scene.layout.seats() if s.source == "desk"]
    nearest = min(desks, key=lambda s: abs(s.col - center[0]) + abs(s.row - center[1]))
    assert (orch.seat.col, orch.seat.row) == (nearest.col, nearest.row)
    assert len({s.seat.cell for s in scene.slots if s.seat}) == len(scene.slots)
    rects = [s.rect for s in scene.slots]
    for i, first in enumerate(rects):
        for second in rects[i + 1:]:
            assert not first.intersects(second)
    scene.deleteLater()


def test_scene_state_transitions_via_signals(qapp, offices, board, monkeypatch):
    scene = OfficeScene(office=offices.get("arastirma"))
    scene.agent_cards["arastirmaci"] = "alt1"
    assert scene.states()["arastirmaci"] == STATE_IDLE

    progress = getattr(bus, "office_progress", None)
    if progress is not None:
        progress.emit("arastirma", "alt1", "running")
    else:
        scene._on_office_progress("arastirma", "alt1", "running")
    assert scene.states()["arastirmaci"] == STATE_WORKING

    scene._on_office_progress("arastirma", "alt1", "queued")
    assert scene.states()["arastirmaci"] == STATE_WAITING
    scene._on_office_progress("arastirma", "alt1", "degerlendirme")
    assert scene.states()["arastirmaci"] == STATE_THINKING

    bus.task_completed.emit("alt1", False)
    assert scene.states()["arastirmaci"] == STATE_ERROR
    bus.task_completed.emit("alt1", True)
    assert scene.states()["arastirmaci"] == STATE_IDLE
    scene.deleteLater()


def test_scene_ignores_other_office_progress(qapp, offices):
    scene = OfficeScene(office=offices.get("arastirma"))
    scene.agent_cards["arastirmaci"] = "alt1"
    scene._on_office_progress("yazim", "alt1", "running")
    assert scene.states()["arastirmaci"] == STATE_IDLE
    scene.deleteLater()


def test_scene_timer_rate_and_hidden_stop(qapp, offices):
    """Boşta 10 fps, çalışırken 30 fps; pencere gizliyken zamanlayıcı durur."""
    scene = OfficeScene(office=offices.get("arastirma"))
    scene.show()
    assert scene._timer.interval() == scene_mod.IDLE_INTERVAL_MS
    scene.set_state("arastirmaci", STATE_WORKING)
    assert scene._timer.interval() == scene_mod.ACTIVE_INTERVAL_MS
    assert 1000 / scene._timer.interval() <= 31
    scene.hide()
    assert not scene._timer.isActive()
    scene.deleteLater()


def test_scene_click_focuses_stream(qapp, window):
    """Sprite tıklaması: Akış sekmesine geçer ve panel o ajana odaklanır."""
    window.set_office("arastirma")
    window.scene.resize(900, 520)
    window.scene.relayout()
    slot = window.scene.slot_for("arastirmaci")
    # Mantıksal koordinat -> pencere koordinatı (sahne dar olduğunda ölçeklenir).
    scale, dx, dy = window.scene._view_transform()
    point = QPoint(
        int(slot.rect.center().x() * scale + dx),
        int(slot.rect.center().y() * scale + dy),
    )
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, point, Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    window.scene.mousePressEvent(event)
    assert window.scene.selected_agent == "arastirmaci"
    assert window.stream_panel.agent == "arastirmaci"
    assert window.tabs.currentIndex() == 1  # Akış sekmesi


# --------------------------------------------------------------- akış

def test_stream_panel_shows_card_summary_and_live_chunks(qapp, board):
    panel = StreamPanel(board=board, office="arastirma")
    panel.focus_agent("arastirmaci")
    assert "alt1" in panel.view.toPlainText()
    bus.token_chunk_received.emit("merhaba ")
    bus.token_chunk_received.emit("dünya")
    assert panel.stream_text() == "merhaba dünya"
    assert "merhaba dünya" in panel.view.toPlainText()
    panel.clear_stream()
    assert panel.stream_text() == ""
    panel.deleteLater()


def test_stream_panel_ignores_chunks_without_focus(qapp, board):
    panel = StreamPanel(board=board)
    bus.token_chunk_received.emit("kayıp")
    assert panel.stream_text() == ""
    panel.deleteLater()


# --------------------------------------------------------------- Zen/Chat parite

def test_zen_and_chat_have_agent_desk_button(qapp):
    """Her iki kipte de başlığın hemen sağında "Agent Desk" düğmesi var."""
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.chat_mode import ChatModeWindow
    from entropy.ui.modes.zen_mode import ZenModeWindow

    bridge = AgyProcessBridge()
    zen = ZenModeWindow(bridge=bridge)
    chat = ChatModeWindow(bridge=bridge)
    try:
        for window in (zen, chat):
            assert hasattr(window, "desk_btn")
            # Faz 8: dar ust cubuk icin etiket kisaltildi (246 -> ~90 px);
            # tam anlam ipucunda tasiniyor.
            assert "Desk" in window.desk_btn.text()
            assert "Ofis masası" in window.desk_btn.toolTip()
            assert hasattr(window, "open_agent_desk")
        # Düğme başlığın hemen sağında: üst çubuk düzeninde 2. sırada.
        for window in (zen, chat):
            bar = window.desk_btn.parentWidget().layout()
            assert bar.indexOf(window.desk_btn) == 1
    finally:
        chat.close()
        zen.close()


def test_desk_button_opens_single_window(qapp, monkeypatch, offices):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.chat_mode import ChatModeWindow
    import entropy.desk.window as desk_window

    monkeypatch.setattr(desk_window, "load_office_registry", lambda: offices)
    chat = ChatModeWindow(bridge=AgyProcessBridge())
    try:
        first = chat.open_agent_desk()
        second = chat.open_agent_desk()
        assert first is not None and first is second
        first.close()
    finally:
        chat.close()


def test_desk_slash_command_renders_card(qapp, monkeypatch, offices):
    """`/desk` çıktısı sohbete okunur kart olarak basılır, AGY'ye gitmez."""
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.chat_mode import ChatModeWindow
    import entropy.desk.window as desk_window

    monkeypatch.setattr(desk_window, "load_office_registry", lambda: offices)
    chat = ChatModeWindow(bridge=AgyProcessBridge())
    sent = []
    monkeypatch.setattr(chat.bridge, "send_prompt", lambda *a, **k: sent.append(a), raising=False)
    try:
        chat.input_field.setText("/desk")
        chat._on_send()
        assert sent == []  # sağlayıcıya gitmedi
        assert chat.input_field.text() == ""
        assert "Agent Desk" in chat.chat_browser.toPlainText()
        window = desk_window.existing_desk_window()
        assert window is not None
        window.close()
    finally:
        chat.close()
