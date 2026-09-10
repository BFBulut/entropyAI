"""
Faz 11-C arayüz dalgası — pano, ajan oturumu, rapor kartı, olay akışı.

Testler offscreen çalışır, gerçek model çağırmaz ve gerçek kasaya yazmaz
(`tests/conftest.py` yalıtımı). Sahte pano/kayıt defteri nesneleri
`tests/ui/test_ui_agents_and_task_board.py` ile aynı sözleşmeyi taklit eder.
"""

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from entropy.core.event_bus import bus
from entropy.ui.widgets import agent_session_badge as asb
from entropy.ui.widgets import task_board_widget as tbw
from entropy.ui.widgets.report_chat_card import (
    ReportContextQueue, report_card_html, report_context_block, short_summary,
)
from entropy.ui.widgets.task_board_widget import (
    COLUMNS, TaskBoardWidget, card_badges, card_is_editable, column_for_status,
)
from entropy.ui.widgets.timeline_panel import TimelinePanel, _board_events, collect_timeline


# --------------------------------------------------------------- sahte sözleşme

class FakeSpec(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def make_card(card_id="t1", status="backlog", **over):
    data = {
        "id": card_id, "title": f"Görev {card_id}", "status": status,
        "agent": "entropy-isci", "provider": "claude", "model": "claude-opus-5",
        "skill": "", "goal": "Mimariyi denetle", "criteria": ["rapor yazılsın"],
        "created_at": "2026-09-01T10:00:00", "started_at": "", "finished_at": "",
        "output_paths": [], "summary": "", "path": "", "notes": "",
        # Faz 11-C alanları
        "effort": "", "priority": "", "input_paths": [], "report_path": "",
        "claimed_by": "", "claim_expiry": "", "event_seq": 0,
    }
    data.update(over)
    return FakeSpec(data)


class FakeBoard:
    def __init__(self, cards=None):
        self._cards = list(cards or [])
        self.updated = []

    def list(self, status=None, office=None):
        return list(self._cards)

    def get(self, card_id):
        for c in self._cards:
            if c["id"] == card_id:
                return c
        return None

    def update(self, card_id, **data):
        self.updated.append((card_id, data))
        for i, c in enumerate(self._cards):
            if c["id"] == card_id:
                merged = dict(c)
                merged.update(data)
                self._cards[i] = FakeSpec(merged)
                return self._cards[i]
        return None

    def delete(self, card_id):
        self._cards = [c for c in self._cards if c["id"] != card_id]
        return True


# ------------------------------------------------------------------ 1. sütunlar

def test_columns_cover_all_eight_statuses():
    """8 durum 7 sütuna dağılır; `taken` Çalışıyor sütununda durur."""
    keys = [key for key, _ in COLUMNS]
    assert keys == ["backlog", "assigned", "running", "review", "done",
                    "failed", "canceled"]
    statuses = ["backlog", "assigned", "taken", "running", "review", "done",
                "failed", "canceled"]
    assert {column_for_status(s) for s in statuses} == set(keys)
    assert column_for_status("taken") == "running"
    assert column_for_status("bilinmeyen") == "backlog"


def test_board_distributes_cards_into_new_columns(qapp):
    board = FakeBoard([
        make_card("t1", status="backlog"),
        make_card("t2", status="assigned"),
        make_card("t3", status="taken"),
        make_card("t4", status="running"),
        make_card("t5", status="review"),
        make_card("t6", status="done"),
        make_card("t7", status="failed"),
        make_card("t8", status="canceled"),
    ])
    widget = TaskBoardWidget(board=board)
    assert [c["id"] for c in widget.cards_in_column("assigned")] == ["t2"]
    # `taken` ve `running` tek sütunda, rozetle ayrılır.
    assert [c["id"] for c in widget.cards_in_column("running")] == ["t3", "t4"]
    assert [c["id"] for c in widget.cards_in_column("failed")] == ["t7"]
    assert [c["id"] for c in widget.cards_in_column("canceled")] == ["t8"]
    taken_widget = [w for w in widget.card_widgets if w.card_id == "t3"][0]
    assert ("sahiplenildi", "accent") in taken_widget.badges


def test_terminal_columns_hidden_when_empty(qapp):
    """Başarısız/İptal sütunları boşken gizlenir (pano tek ekrana sığsın)."""
    board = FakeBoard([make_card("t1", status="backlog")])
    widget = TaskBoardWidget(board=board)
    assert widget.column_frames["failed"].isVisibleTo(widget) is False
    assert widget.column_frames["canceled"].isVisibleTo(widget) is False
    assert widget.column_frames["backlog"].isVisibleTo(widget) is True
    board._cards.append(make_card("t2", status="failed"))
    widget.refresh_cards()
    assert widget.column_frames["failed"].isVisibleTo(widget) is True


def test_card_badges_show_priority_claim_effort_and_agent():
    card = make_card("t1", status="taken", priority="P0",
                     claimed_by="entropy-isci", effort="high", agent="entropy-isci")
    badges = dict(card_badges(card))
    assert badges["P0"] == "danger"
    assert "sahip: entropy-isci" in badges
    assert "efor high" in badges
    assert badges["entropy-isci"] == "ok"


# ------------------------------------------------------ 2. efor kart alanına yazar

def test_effort_written_to_real_card_field_not_notes(qapp):
    """`notes: "effort: X"` hilesi kaldırıldı; efor gerçek alana yazılır."""
    board = FakeBoard([make_card("t1", status="backlog")])
    widget = TaskBoardWidget(board=board)
    ok = widget.update_card_settings(
        "t1", {"provider": "claude", "model": "claude-opus-5",
               "effort": "high", "budget_tokens": 0}
    )
    assert ok is True
    card_id, payload = board.updated[-1]
    assert card_id == "t1"
    assert payload["effort"] == "high"
    assert "notes" not in payload


def test_settings_locked_for_started_cards(qapp):
    board = FakeBoard([make_card("t1", status="running", started_at="2026-09-01T10:00:00")])
    widget = TaskBoardWidget(board=board)
    widget.select_card("t1")
    assert card_is_editable(board.get("t1")) is False
    assert widget.detail_panel.settings_editable() is False
    assert widget.update_card_settings("t1", {"effort": "low"}) is False
    assert board.updated == []


def test_settings_editable_for_assigned_cards(qapp):
    board = FakeBoard([make_card("t1", status="assigned")])
    widget = TaskBoardWidget(board=board)
    widget.select_card("t1")
    assert widget.detail_panel.settings_editable() is True


# ------------------------------------------------- board_state_changed + dosya

def test_board_state_changed_refreshes_with_debounce(qapp):
    board = FakeBoard([make_card("t1", status="backlog")])
    widget = TaskBoardWidget(board=board)
    board._cards[0] = make_card("t1", status="running")
    bus.board_state_changed.emit({
        "card_id": "t1", "status": "running", "event": "run.started",
        "agent": "entropy-isci", "office": "", "title": "Görev t1",
    })
    # Debounce: yenileme henüz yapılmadı, ama olay kaydedildi.
    assert widget.last_board_event["status"] == "running"
    widget.flush_board_events()
    assert [c["id"] for c in widget.cards_in_column("running")] == ["t1"]


def test_board_state_changed_ignores_other_offices(qapp):
    board = FakeBoard([make_card("t1", status="backlog", office="alfa")])
    widget = TaskBoardWidget(board=board, office="alfa")
    bus.board_state_changed.emit({"card_id": "x", "office": "beta", "status": "done"})
    assert widget.last_board_event == {}


def test_taskboard_button_emits_report_signal(qapp, tmp_path, monkeypatch):
    path = tmp_path / "TASKBOARD.md"
    path.write_text("# Pano\n", encoding="utf-8")
    monkeypatch.setattr(
        "entropy.core.paths.board_taskboard_path", lambda *a, **k: path
    )
    widget = TaskBoardWidget(board=FakeBoard([]))
    seen = []
    bus.report_created.connect(seen.append)
    try:
        assert widget.open_taskboard_file() == str(path)
    finally:
        bus.report_created.disconnect(seen.append)
    assert seen == [str(path)]


# ---------------------------------------------------------- 3. oturum rozeti

def _write_session(tmp_path, agent="entropy-isci", **over):
    target = tmp_path / agent / "session.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {"session_id": "abc123", "signature": "sig", "model": "claude-opus-5",
              "effort": "high", "cwd": "", "updated_at": time.time() - 300}
    record.update(over)
    target.write_text(json.dumps({"claude": record}), encoding="utf-8")
    return target


def test_session_badge_reads_persistent_session(tmp_path):
    path = _write_session(tmp_path)
    info = asb.read_session("entropy-isci", path=path)
    assert info is not None
    assert info["provider"] == "claude"
    text = asb.session_badge_text(info)
    assert "kalıcı oturum" in text and "claude" in text and "dk önce" in text


def test_session_badge_without_file_says_no_session(tmp_path):
    assert asb.read_session("yok", path=tmp_path / "yok.json") is None
    assert asb.session_badge_text(None) == asb.NO_SESSION_TEXT


def test_session_badge_ignores_record_without_identity(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"claude": {"model": "x"}}), encoding="utf-8")
    assert asb.read_session("a", path=target) is None


def test_clear_session_removes_file(tmp_path):
    path = _write_session(tmp_path)
    assert asb.clear_session("entropy-isci", path=path) is True
    assert not path.exists()
    assert asb.clear_session("entropy-isci", path=path) is False


def test_agent_card_shows_session_badge(qapp, tmp_path, monkeypatch):
    from entropy.ui.widgets.agents_widget import AgentsWidget

    path = _write_session(tmp_path)
    monkeypatch.setattr(
        "entropy.core.paths.agent_session_path", lambda agent, *a, **k: path
    )

    class FakeRegistry:
        def list(self):
            return [FakeSpec({
                "name": "entropy-isci", "role": "worker", "description": "",
                "provider": "claude", "model": "claude-opus-5", "effort": "high",
                "skills": [], "tools_policy": "inherit", "memory_path": "",
                "prompt": "", "path": "", "updated_at": "",
            })]

        def get(self, name):
            return self.list()[0]

    widget = AgentsWidget(registry=FakeRegistry(), board=FakeBoard([]))
    card = widget.cards[0]
    assert "kalıcı oturum" in card.session_label.text()
    assert card.session_reset_btn.isEnabled() is True
    card.session_reset_btn.click()
    assert not path.exists()
    assert card.session_label.text() == asb.NO_SESSION_TEXT


# ------------------------------------------------------------ 4. rapor kartı

REPORT_PAYLOAD = {
    "card_id": "t42", "title": "Mimari denetimi", "agent": "entropy-isci",
    "status": "done", "ok": True,
    "summary": "Kod tabanı denetlendi. " + "ayrıntı " * 80,
    "report_path": "C:/kasa/Entropy/Reports/denetim.md",
    "output_paths": ["C:/kasa/Entropy/Reports/denetim.md"],
}


def test_report_card_html_has_summary_and_two_actions():
    html = report_card_html(REPORT_PAYLOAD)
    assert "RAPOR GELDİ" in html
    assert "Mimari denetimi" in html
    assert "entropy-isci" in html
    assert "Raporu aç" in html and "Sohbete al" in html
    assert "entropy-report://" in html and "entropy-context://t42" in html


def test_summary_is_capped_at_300_chars():
    short = short_summary(REPORT_PAYLOAD["summary"])
    assert len(short) == 300
    assert short.endswith("…")


def test_report_context_block_format():
    block = report_context_block(REPORT_PAYLOAD)
    assert block.startswith("[RAPOR: Mimari denetimi | entropy-isci | done]")
    assert block.endswith("[/RAPOR]")
    assert "denetim.md" in block


def test_context_queue_prefixes_prompt_once():
    queue = ReportContextQueue()
    queue.add(REPORT_PAYLOAD)
    assert len(queue) == 1
    merged = queue.apply("Bu raporu özetle")
    assert merged.startswith("[RAPOR:")
    assert merged.endswith("Bu raporu özetle")
    # Kuyruk boşaldı: aynı rapor ikinci istemde tekrar gitmez.
    assert queue.apply("ikinci istem") == "ikinci istem"


def test_context_queue_deduplicates_same_card():
    queue = ReportContextQueue()
    queue.add(REPORT_PAYLOAD)
    queue.add(REPORT_PAYLOAD)
    assert len(queue) == 1


class _FakeBrowser:
    def __init__(self):
        self.html = []

    def append(self, text):
        self.html.append(text)

    def moveCursor(self, *_a):
        pass


class _Host:
    """Karışımı (mixin) taşıyan en küçük konak — Qt penceresi kurmadan test."""

    def __init__(self):
        from entropy.ui.widgets.report_card_bridge import ReportCardMixin

        self.__class__ = type("Host", (ReportCardMixin, _Host), {})
        self.chat_browser = _FakeBrowser()
        self.messages = []
        self.install_report_cards()

    def _append_message(self, sender, text, is_system=False):
        self.messages.append((sender, text))


def test_report_ready_signal_prints_card_and_take_to_chat(qapp):
    host = _Host()
    bus.task_report_ready.emit(dict(REPORT_PAYLOAD))
    assert any("RAPOR GELDİ" in h for h in host.chat_browser.html)
    # "Sohbete al" bağlantısı bağlam kuyruğuna yazar.
    assert host.handle_context_anchor("entropy-context://t42") is True
    assert len(host.report_context) == 1
    merged = host.apply_report_context("özetle")
    assert merged.startswith("[RAPOR: Mimari denetimi")
    # Bilinmeyen anahtar sessizce yutulmaz, False döner.
    assert host.handle_context_anchor("entropy-context://yok") is False


# ------------------------------------------------------------- 5. olay akışı

def test_board_events_read_last_50_lines(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    now = time.time()
    lines = []
    for i in range(60):
        lines.append(json.dumps({
            "schema_version": 1, "seq": i, "ts": now, "task_id": f"t{i}",
            "actor": "human", "action": "run.started",
            "payload": {"title": f"Görev {i}", "status": "running", "agent": "isci"},
        }))
    lines.append("bozuk satır")
    path.write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.setattr("entropy.core.paths.board_events_path", lambda *a, **k: path)

    events = _board_events()
    assert len(events) == 49  # son 50 satırın biri bozuk, atlandı
    assert events[0]["kind"] == "board"
    assert events[-1]["target"] == "t59"
    assert "run.started" in events[-1]["detail"]


def test_board_events_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "entropy.core.paths.board_events_path", lambda *a, **k: tmp_path / "yok.jsonl"
    )
    assert _board_events() == []


def test_timeline_shows_board_events_and_click_target(qapp):
    now = time.time()
    injected = [{
        "kind": "board", "ts": now, "title": "Görev t1",
        "detail": "run.started · running", "status": "running", "target": "t1",
    }]
    panel = TimelinePanel(events=injected, now=now)
    assert [e["kind"] for e in panel.events()] == ["board"]
    text = panel.list_widget.item(0).text()
    assert "Pano" in text and "Görev t1" in text
    seen = []
    panel.event_activated.connect(lambda k, t: seen.append((k, t)))
    panel._on_item_clicked(panel.list_widget.item(0))
    assert seen == [("board", "t1")]


def test_timeline_refreshes_on_board_state_changed(qapp):
    panel = TimelinePanel(events=[], now=time.time())
    bus.board_state_changed.emit({"card_id": "t1", "status": "done"})
    assert panel._board_debounce.isActive() is True
    panel.flush_board_events()
    assert panel._board_debounce.isActive() is False


# ------------------------------------ 6. Entropy'nin kendi model/eforu (is 4)

class _FakeCombo:
    def __init__(self, items=()):
        self._items = list(items)
        self._current = self._items[0] if self._items else ""

    def blockSignals(self, _flag):
        pass

    def findText(self, text):
        return self._items.index(text) if text in self._items else -1

    def addItem(self, text):
        self._items.append(text)

    def setCurrentText(self, text):
        self._current = text

    def currentText(self):
        return self._current


class _FakeBridge:
    provider_name = "claude"
    selected_model = "claude-haiku-4-5"
    selected_effort = "low"


class _ModeHost:
    """Kip penceresi kurmadan `sync_model_effort_ui` sözleşmesini ölçer."""

    def __init__(self):
        self.bridge = _FakeBridge()
        self.model_combo = _FakeCombo(["claude-opus-5"])
        self.effort_refreshed = 0

    def _refresh_effort_combo(self):
        self.effort_refreshed += 1


@pytest.mark.parametrize("mode", ["chat", "zen"])
def test_slash_model_effort_syncs_top_bar(mode):
    """`/model` ve `/effort` köprüye yazar; üst çubuk kutuları tazelenir."""
    if mode == "chat":
        from entropy.ui.modes.chat_mode import ChatModeWindow as Window
    else:
        from entropy.ui.modes.zen_mode import ZenModeWindow as Window

    host = _ModeHost()
    Window.sync_model_effort_ui(host)
    # Köprüdeki model kutuda yoktu: eklenip seçildi (bayat kutu düzeltildi).
    assert host.model_combo.currentText() == "claude-haiku-4-5"
    assert host.effort_refreshed == 1
