"""
Faz 2 arayüz testleri: ajan paneli, görev panosu kanbanı, bağlam rozeti ve
Zen/Chat paritesi.

Kayıt defteri ve görev panosu modülleri başka bir ajan tarafından yazılıyor;
buradaki testler sözleşmeye (`AgentSpec` / `TaskCard` alan adları ve
`list/get/create/update/delete/run/stop` metotları) uyan sahte nesneler
kullanır. Böylece arayüz, gerçek uygulama gelmeden de doğrulanır.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from entropy.core.event_bus import bus
from entropy.ui.widgets import agents_widget as aw
from entropy.ui.widgets import task_board_widget as tbw
from entropy.ui.widgets.agents_widget import (
    AgentEditDialog, AgentsWidget, AssignTaskDialog, call_flex, spec_field
)
from entropy.ui.widgets.task_board_widget import (
    CompactTaskListWidget, TaskBoardWidget, column_for_status, format_duration
)
from entropy.ui.widgets.token_badge import (
    CONTEXT_WARN_COLOR, CONTEXT_OK_COLOR, format_context_badge, format_token_badge
)


# --------------------------------------------------------------- sahte sözleşme

class FakeSpec(dict):
    """AgentSpec/TaskCard yerine geçen, öznitelik erişimli sözlük."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def make_agent(name="code-architect", **over):
    data = {
        "name": name, "role": "Mimari denetçi", "description": "Mimari incele",
        "provider": "claude", "model": "claude-opus-5", "effort": "high",
        "skills": ["financial-auditor", "media-agency"], "tools_policy": "read-only",
        "memory_path": "", "prompt": "# Rol\nMimariyi denetle.",
        "path": "", "updated_at": "2026-09-01T10:00:00",
    }
    data.update(over)
    return FakeSpec(data)


def make_card(card_id="t1", status="backlog", **over):
    data = {
        "id": card_id, "title": f"Görev {card_id}", "status": status,
        "agent": "code-architect", "provider": "claude", "model": "claude-opus-5",
        "skill": "", "goal": "Mimariyi denetle", "criteria": ["rapor yazılsın"],
        "created_at": "2026-09-01T10:00:00", "started_at": "2026-09-01T10:00:00",
        "finished_at": "", "output_paths": [], "summary": "", "path": "",
    }
    data.update(over)
    return FakeSpec(data)


class FakeRegistry:
    def __init__(self, agents=None):
        self._agents = list(agents or [])
        self.created, self.updated, self.deleted = [], [], []

    def list(self):
        return list(self._agents)

    def get(self, name):
        for a in self._agents:
            if a["name"] == name:
                return a
        return None

    def create(self, **data):
        self.created.append(data)
        self._agents.append(FakeSpec(data))
        return self._agents[-1]

    def update(self, agent_name, **data):
        # Not: ilk parametre adı `name` OLAMAZ; güncelleme yükü yeniden
        # adlandırma için `name` alanını taşır ve çakışırdı.
        if not isinstance(agent_name, str):
            # Bu sahte, sözlük/kwargs imzasını temsil eder; veri sınıfı almaz.
            raise TypeError("ad dizgi olmalı")
        self.updated.append((agent_name, data))
        for i, a in enumerate(self._agents):
            if a["name"] == agent_name:
                merged = dict(a)
                merged.update(data)
                self._agents[i] = FakeSpec(merged)
                return self._agents[i]
        return None

    def delete(self, agent_name):
        self.deleted.append(agent_name)
        self._agents = [a for a in self._agents if a["name"] != agent_name]
        return True


class FakeBoard:
    def __init__(self, cards=None):
        self._cards = list(cards or [])
        self.ran, self.stopped, self.deleted, self.updated = [], [], [], []
        self.archived = []

    def list(self, status=None):
        if status is None:
            return list(self._cards)
        return [c for c in self._cards if c["status"] == status]

    def get(self, card_id):
        for c in self._cards:
            if c["id"] == card_id:
                return c
        return None

    def create(self, **data):
        card = make_card(card_id=f"t{len(self._cards) + 1}", **{
            k: v for k, v in data.items() if k in make_card()
        })
        self._cards.append(card)
        return card

    def update(self, card_id, **data):
        for i, c in enumerate(self._cards):
            if c["id"] == card_id:
                merged = dict(c)
                merged.update(data)
                self._cards[i] = FakeSpec(merged)
                self.updated.append((card_id, data))
                return self._cards[i]
        return None

    def delete(self, card_id):
        self.deleted.append(card_id)
        self._cards = [c for c in self._cards if c["id"] != card_id]
        return True

    def archive_card(self, card_id, reason=""):
        """Faz 13-C madde 2: arayüzün tek kaldırma yolu (dosya silinmez)."""
        self.archived.append((card_id, reason))
        self._cards = [c for c in self._cards if c["id"] != card_id]
        return {"ok": True, "archived_to": f"_archive/{card_id}.md"}

    def run(self, card_id):
        self.ran.append(card_id)
        self.update(card_id, status="running")
        return True

    def stop(self, card_id):
        self.stopped.append(card_id)
        self.update(card_id, status="review")
        return True


class FakeBridge:
    """Köprü sözleşmesinin rozetler için gereken en küçük yüzeyi."""

    provider_name = "claude"
    selected_model = "claude-opus-5"

    def __init__(self, used=0, window=200_000, breakdown=None):
        self._used, self._window, self._breakdown = used, window, breakdown

    def fetch_available_models(self):
        return ["claude-opus-5", "claude-sonnet-5"]

    def context_used_tokens(self):
        return self._used

    def context_window_size(self):
        return self._window

    def context_fill_ratio(self):
        return self._used / float(self._window) if self._window else 0.0

    def usage_breakdown(self):
        if self._breakdown is None:
            raise AttributeError("yok")
        return self._breakdown


# --------------------------------------------------------------- Görev 1: ajanlar

def test_agents_widget_lists_registry_entries(qapp):
    registry = FakeRegistry([make_agent(), make_agent("researcher", role="Araştırmacı")])
    widget = AgentsWidget(registry=registry, board=FakeBoard())
    assert len(widget.cards) == 2
    names = [c.agent_name for c in widget.cards]
    assert names == ["code-architect", "researcher"]
    # Rol, sağlayıcı/model ve yetenek rozetleri kartta görünür.
    card_text = " ".join(
        child.text() for child in widget.cards[0].findChildren(type(widget.empty_label))
    )
    assert "Mimari denetçi" in card_text
    assert "claude / claude-opus-5" in card_text
    assert "financial-auditor" in card_text


def test_agents_widget_missing_module_shows_empty_state(qapp, monkeypatch):
    """Kayıt defteri modülü yoksa panel çökmez, açıklayıcı boş durum gösterir."""
    monkeypatch.setattr(aw, "load_registry", lambda: None)
    monkeypatch.setattr(aw, "load_board", lambda: None)
    widget = AgentsWidget()
    assert widget.cards == []
    assert widget.empty_label.isVisible() or widget.empty_label.text()
    assert "entropy.agents.registry" in widget.empty_label.text()


def test_agents_widget_create_and_update_agent(qapp):
    registry = FakeRegistry()
    widget = AgentsWidget(registry=registry, board=FakeBoard())

    data = dict(make_agent("tester", role="Sınayıcı"))
    assert widget.apply_agent_save(data, original_name=None) is True
    assert registry.created and registry.created[0]["name"] == "tester"
    assert len(widget.cards) == 1

    data["role"] = "Kıdemli Sınayıcı"
    assert widget.apply_agent_save(data, original_name="tester") is True
    assert registry.updated[0][0] == "tester"
    assert registry.updated[0][1]["role"] == "Kıdemli Sınayıcı"


def test_agents_widget_delete_agent(qapp):
    registry = FakeRegistry([make_agent()])
    widget = AgentsWidget(registry=registry, board=FakeBoard())
    assert widget.delete_agent("code-architect", confirm=False) is True
    assert registry.deleted == ["code-architect"]
    assert widget.cards == []


def test_agents_widget_assign_task_creates_and_runs(qapp):
    board = FakeBoard()
    spec = make_agent()
    widget = AgentsWidget(registry=FakeRegistry([spec]), board=board)
    card = widget.apply_task_assignment(
        {"title": "Denetim", "goal": "Mimariyi incele", "criteria": ["rapor"], "agent": "code-architect", "skill": ""},
        spec,
    )
    assert card is not None
    assert board.ran == [card["id"]]
    assert board.get(card["id"])["status"] == "running"


def test_agent_edit_dialog_provider_switches_model_list(qapp):
    dialog = AgentEditDialog(skills=["a", "b"])
    dialog.provider_combo.setCurrentText("claude")
    claude_models = [dialog.model_combo.itemText(i) for i in range(dialog.model_combo.count())]
    assert "claude-opus-5" in claude_models
    dialog.provider_combo.setCurrentText("agy")
    agy_models = [dialog.model_combo.itemText(i) for i in range(dialog.model_combo.count())]
    assert agy_models != claude_models
    assert any("gemini" in m for m in agy_models)


def test_agent_edit_dialog_prefills_and_returns_contract_fields(qapp):
    spec = make_agent()
    dialog = AgentEditDialog(spec=spec, skills=["financial-auditor", "media-agency", "x"])
    assert dialog.name_input.text() == "code-architect"
    assert dialog.provider_combo.currentText() == "claude"
    assert set(dialog.selected_skills()) == {"financial-auditor", "media-agency"}
    data = dialog.get_data()
    for field in ("name", "role", "description", "provider", "model", "effort",
                  "skills", "tools_policy", "prompt"):
        assert field in data


def test_assign_task_dialog_parses_criteria_lines(qapp):
    dialog = AssignTaskDialog(agent_name="code-architect", skills=["s1"])
    dialog.title_input.setText("Denetim")
    dialog.goal_input.setPlainText("Mimariyi incele")
    dialog.criteria_input.setPlainText("rapor yazıldı\n\ntestler geçti")
    data = dialog.get_data()
    assert data["criteria"] == ["rapor yazıldı", "testler geçti"]
    assert data["agent"] == "code-architect"


def test_agents_widget_refreshes_on_bus_signal(qapp):
    """`bus.agents_updated` varsa panel canlı yenilenir; yoksa test atlanır."""
    signal = getattr(bus, "agents_updated", None)
    if signal is None:
        pytest.skip("bus.agents_updated henüz tanımlı değil (agy ajanı ekliyor)")
    registry = FakeRegistry([make_agent()])
    widget = AgentsWidget(registry=registry, board=FakeBoard())
    registry._agents.append(make_agent("researcher"))
    signal.emit("researcher")
    assert len(widget.cards) == 2


def test_agent_card_shows_latest_task_status(qapp):
    board = FakeBoard([
        make_card("t1", status="done", created_at="2026-09-01T09:00:00"),
        make_card("t2", status="running", created_at="2026-09-02T09:00:00", title="Son iş"),
    ])
    widget = AgentsWidget(registry=FakeRegistry([make_agent()]), board=board)
    status_html = widget.cards[0].status_label.text()
    assert "Son iş" in status_html
    assert "Çalışıyor" in status_html


# --------------------------------------------------------------- Görev 2: kanban

def test_kanban_columns_group_cards_by_status(qapp):
    board = FakeBoard([
        make_card("t1", status="backlog"),
        make_card("t2", status="running"),
        make_card("t3", status="review"),
        make_card("t4", status="done"),
        make_card("t5", status="failed"),
    ])
    widget = TaskBoardWidget(board=board)
    assert [c["id"] for c in widget.cards_in_column("backlog")] == ["t1"]
    assert [c["id"] for c in widget.cards_in_column("running")] == ["t2"]
    assert [c["id"] for c in widget.cards_in_column("review")] == ["t3"]
    assert [c["id"] for c in widget.cards_in_column("done")] == ["t4"]
    # Faz 11-C: `failed` artık kendi sütununda (8 durum, 7 sütun).
    assert [c["id"] for c in widget.cards_in_column("failed")] == ["t5"]
    failed_widget = [w for w in widget.card_widgets if w.card_id == "t5"][0]
    assert "BAŞARISIZ" in failed_widget.title_label.text()


def test_column_for_status_maps_unknown_to_backlog():
    assert column_for_status("failed") == "failed"
    # `taken` ayrı sütun değil: Çalışıyor sütununda rozetle durur.
    assert column_for_status("taken") == "running"
    assert column_for_status("running") == "running"
    assert column_for_status("saçma") == "backlog"


def test_format_duration_reports_running_and_finished():
    assert format_duration(make_card(started_at="2026-09-01T10:00:00", finished_at="")) == "sürüyor"
    card = make_card(started_at="2026-09-01T10:00:00", finished_at="2026-09-01T10:02:30")
    assert format_duration(card) == "2 dk 30 sn"
    assert format_duration(make_card(started_at="")) == ""


def test_kanban_run_stop_done_delete_transitions(qapp):
    board = FakeBoard([make_card("t1", status="backlog")])
    widget = TaskBoardWidget(board=board)

    assert widget.run_card("t1") is True
    assert board.ran == ["t1"]
    assert [c["id"] for c in widget.cards_in_column("running")] == ["t1"]

    assert widget.stop_card("t1") is True
    assert [c["id"] for c in widget.cards_in_column("review")] == ["t1"]

    assert widget.mark_done("t1") is True
    assert [c["id"] for c in widget.cards_in_column("done")] == ["t1"]

    assert widget.delete_card("t1", confirm=False) is True
    # Faz 13-C madde 2: "Sil" artık ARŞİVLER; doğrudan silme çağrılmaz.
    assert board.deleted == []
    assert board.archived and board.archived[0][0] == "t1"
    assert widget.card_widgets == []


def test_kanban_detail_panel_shows_goal_and_criteria(qapp):
    board = FakeBoard([make_card("t1", goal="Mimariyi incele", criteria=["rapor", "test"])])
    widget = TaskBoardWidget(board=board)
    widget.select_card("t1")
    body = widget.detail_panel.body_label.text()
    assert "Mimariyi incele" in body
    assert "rapor" in body and "test" in body
    assert widget.detail_panel.run_btn.isEnabled()


def test_kanban_output_paths_open_via_report_signal(qapp, tmp_path):
    out = tmp_path / "rapor.md"
    out.write_text("# rapor", encoding="utf-8")
    board = FakeBoard([make_card("t1", output_paths=[str(out)])])
    widget = TaskBoardWidget(board=board)
    widget.select_card("t1")
    buttons = [
        widget.detail_panel.outputs_layout.itemAt(i).widget()
        for i in range(widget.detail_panel.outputs_layout.count())
    ]
    assert len(buttons) == 1
    seen = []
    bus.report_created.connect(seen.append)
    try:
        buttons[0].click()
    finally:
        bus.report_created.disconnect(seen.append)
    assert seen == [str(out)]


def test_kanban_refreshes_on_bus_signal(qapp):
    signal = getattr(bus, "task_cards_updated", None)
    if signal is None:
        pytest.skip("bus.task_cards_updated henüz tanımlı değil (agy ajanı ekliyor)")
    board = FakeBoard([make_card("t1")])
    widget = TaskBoardWidget(board=board)
    board._cards.append(make_card("t2", status="done"))
    signal.emit("t2")
    assert [c["id"] for c in widget.cards_in_column("done")] == ["t2"]


def test_compact_task_list_counts_open_cards(qapp):
    board = FakeBoard([
        make_card("t1", status="backlog"),
        make_card("t2", status="done"),
        make_card("t3", status="failed"),
    ])
    widget = CompactTaskListWidget(board=board)
    assert widget.open_count() == 2
    assert "2 açık" in widget.count_badge.text()


# --------------------------------------------------------------- Görev 3: bağlam

def test_context_badge_green_below_threshold():
    text, tip, color = format_context_badge(FakeBridge(used=40_000, window=200_000))
    assert text == "Bağlam: %20"
    assert color == CONTEXT_OK_COLOR
    assert "handoff" not in tip


def test_context_badge_orange_and_suggests_handoff_above_threshold():
    text, tip, color = format_context_badge(FakeBridge(used=150_000, window=200_000))
    assert text == "Bağlam: %75"
    assert color == CONTEXT_WARN_COLOR
    assert "/handoff" in tip


def test_context_badge_falls_back_to_pressure_signal_value():
    class NoRatio:
        pass

    _, _, color = format_context_badge(NoRatio(), 0.8)
    assert color == CONTEXT_WARN_COLOR


def test_token_tooltip_includes_cache_write_line():
    bridge = FakeBridge(breakdown={
        "input": 10, "output": 20, "cache_read": 30, "cache_write": 40, "total": 100
    })
    _, tip = format_token_badge(bridge)
    assert "Önbellek yazımı: 40" in tip
    assert "Önbellek okuma: 30" in tip


def test_token_tooltip_without_breakdown_stays_backward_compatible():
    class Plain:
        pass

    text, tip = format_token_badge(Plain())
    assert text == "Tokens: 0"
    assert "KALEM DÖKÜMÜ" not in tip


# --------------------------------------------------------------- mod paritesi

def test_zen_and_chat_expose_same_provider_and_context_controls(qapp, monkeypatch):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.chat_mode import ChatModeWindow
    from entropy.ui.modes.zen_mode import ZenModeWindow

    bridge = AgyProcessBridge()
    zen = ZenModeWindow(bridge=bridge)
    chat = ChatModeWindow(bridge=bridge)
    try:
        for window in (zen, chat):
            assert hasattr(window, "provider_combo")
            assert hasattr(window, "context_badge")
            items = [window.provider_combo.itemText(i) for i in range(window.provider_combo.count())]
            assert items == ["agy", "claude"]
        # Zen: Ajanlar sekmesi ve kanban panosu var.
        titles = [zen.left_tabs.tabText(i) for i in range(zen.left_tabs.count())]
        assert any("Ajanlar" in t for t in titles)
        assert hasattr(zen, "task_board_widget")
        assert hasattr(zen, "agents_widget")
        # Chat: yan panelde eşdeğer sekmeler.
        chat.ensure_side_panel()
        chat_titles = [chat.side_panel.tabText(i) for i in range(chat.side_panel.count())]
        assert any("Ajanlar" in t for t in chat_titles)
        assert any("Ajan Görevleri" in t for t in chat_titles)
    finally:
        chat.close()
        zen.close()


@pytest.mark.parametrize("mode", ["zen", "chat"])
def test_provider_combo_calls_switch_provider(qapp, monkeypatch, mode):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui import manager as manager_module

    calls = []

    class FakeManager:
        def switch_provider(self, provider):
            calls.append(provider)

    monkeypatch.setattr(manager_module.EntropyUIManager, "instance", FakeManager(), raising=False)

    bridge = AgyProcessBridge()
    if mode == "zen":
        from entropy.ui.modes.zen_mode import ZenModeWindow

        window = ZenModeWindow(bridge=bridge)
    else:
        from entropy.ui.modes.chat_mode import ChatModeWindow

        window = ChatModeWindow(bridge=bridge)
    try:
        window.provider_combo.setCurrentText("claude")
        assert calls == ["claude"]
    finally:
        window.close()


@pytest.mark.parametrize("mode", ["zen", "chat"])
def test_context_pressure_signal_turns_badge_orange(qapp, mode):
    from entropy.core.agy_bridge import AgyProcessBridge

    bridge = AgyProcessBridge()
    if mode == "zen":
        from entropy.ui.modes.zen_mode import ZenModeWindow

        window = ZenModeWindow(bridge=bridge)
    else:
        from entropy.ui.modes.chat_mode import ChatModeWindow

        window = ChatModeWindow(bridge=bridge)
    try:
        bus.context_pressure.emit(0.82)
        # Faz 11-E adim 3: rozet rengi yerel `setStyleSheet` ile degil
        # `tone` belirteciyle gelir (tek vurgu kurali, QSS tek kaynak).
        assert window.context_badge.property("tone") == "warn"
        assert "/handoff" in window.context_badge.toolTip()
    finally:
        window.close()


def test_local_command_output_rendered_as_reading_card():
    from entropy.ui.widgets.markdown_renderer import build_command_card_html

    html = build_command_card_html("<b>🔁 Oturum Aktarımı Yazıldı</b>")
    assert "KOMUT ÇIKTISI" in html
    assert "Oturum Aktarımı" in html
    # Ortalanmış küçük sistem hapı değil; sola hizalı okunur kart.
    assert "text-align:center" not in html


def test_call_flex_supports_both_signatures():
    def kwargs_only(**kw):
        return ("kwargs", kw)

    def dict_only(payload):
        return ("dict", payload)

    assert call_flex(kwargs_only, {"a": 1})[0] == "kwargs"
    assert call_flex(dict_only, {"a": 1})[0] == "dict"


def test_spec_field_reads_dataclass_and_dict():
    class Obj:
        name = "x"

    assert spec_field(Obj(), "name") == "x"
    assert spec_field({"name": "y"}, "name") == "y"
    assert spec_field({"name": None}, "name", "z") == "z"


class DataclassRegistry:
    """Gerçek `AgentRegistry` gibi `create(spec)/update(spec)` alan sahte."""

    def __init__(self):
        self.saved = []

    def list(self):
        return []

    def create(self, spec):
        self.saved.append(("create", spec))
        return spec

    def update(self, spec):
        self.saved.append(("update", spec))
        return spec

    def delete(self, name):
        self.saved.append(("delete", name))
        return True


def test_agents_widget_supports_dataclass_registry_signature(qapp):
    """Gerçek kayıt defteri AgentSpec nesnesi bekler; panel ona da uyar."""
    pytest.importorskip("entropy.agents.registry")
    from entropy.agents.registry import AgentSpec

    registry = DataclassRegistry()
    widget = AgentsWidget(registry=registry, board=FakeBoard())
    assert widget.apply_agent_save(dict(make_agent("tester")), original_name=None) is True
    kind, spec = registry.saved[0]
    assert kind == "create"
    assert isinstance(spec, AgentSpec)
    assert spec.name == "tester" and spec.provider == "claude"


def test_agents_widget_rename_deletes_old_definition(qapp):
    pytest.importorskip("entropy.agents.registry")
    registry = DataclassRegistry()
    widget = AgentsWidget(registry=registry, board=FakeBoard())
    data = dict(make_agent("yeni-ad"))
    assert widget.apply_agent_save(data, original_name="eski-ad") is True
    kinds = [k for k, _ in registry.saved]
    assert kinds == ["update", "delete"]
    assert registry.saved[1][1] == "eski-ad"
