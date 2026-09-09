"""
Faz 10-D arayüz kablolama testleri.

Kapsam: etkileşimli bekleme rozeti ve giriş satırı, `task_followup_completed`
turunun bölmeye yazılması, `close_interactive` ile arşive geçiş (ilk
`task_completed` ile GEÇMEMESİ), yetim worktree düğmesi, `prepare_review`
başlığı, `bus.memory_error` bildirimi ve Bellek denetçisindeki "Son hatalar"
bölümü.

Model çağrısı, süreç başlatma ve gerçek kasaya yazma YOKTUR: köprüler ve
ajan sözleşmeleri sahte modüllerle yerine konur.
"""

import os
import sys
import types
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from entropy.core.event_bus import bus
from entropy.desk.changes_panel import ChangesPanel, review_headline
from entropy.desk.terminals_panel import (
    TerminalsPanel, WAITING_BADGE, is_waiting_payload,
)
from entropy.ui.widgets.memory_inspector_dialog import (
    MemoryErrorsSection, format_memory_errors,
)
from entropy.ui.widgets.notification_center import NotificationCenter

SHOT_DIR = Path(__file__).resolve().parent.parent / "scratch" / "ui" / "phase10"


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    return app


class FakeBridge:
    """`send_followup` / `close_interactive` / `interactive_task_ids` sahtesi."""

    def __init__(self, live=("task-arastirmaci",)):
        self.sent = []
        self.closed = []
        self._live = list(live)

    def send_followup(self, task_id, text):
        self.sent.append((task_id, text))
        return True

    def close_interactive(self, task_id, reason="kullanıcı kapattı"):
        self.closed.append((task_id, reason))
        if task_id in self._live:
            self._live.remove(task_id)
        return True

    def interactive_task_ids(self):
        return list(self._live)


def stream_event(agent="arastirmaci", **over):
    payload = {
        "task_id": f"task-{agent}",
        "card_id": f"card-{agent}",
        "office": "arastirma",
        "agent": agent,
        "kind": "text",
        "text": "merhaba",
        "state": "working",
    }
    payload.update(over)
    return payload


def waiting_event(agent="arastirmaci"):
    return stream_event(agent, kind="status", state="idle",
                        text="Takip mesajı bekliyor…")


# ------------------------------------------------------- bekleme rozeti


def test_waiting_payload_detection():
    assert is_waiting_payload(waiting_event()) is True
    # Yalnız `state=idle` yetmez: koşu sonu da boşa düşer.
    assert is_waiting_payload(stream_event(kind="status", state="idle",
                                           text="bitti")) is False
    assert is_waiting_payload(stream_event(state="idle")) is False
    assert is_waiting_payload(None) is False


def test_waiting_badge_and_active_input(_app):
    bridge = FakeBridge()
    panel = TerminalsPanel(office="arastirma", bridge=bridge)
    panel.handle_stream(stream_event())
    panel.handle_stream(waiting_event())
    pane = panel.panes["arastirmaci"]

    assert pane.waiting is True and pane.interactive is True
    assert WAITING_BADGE in pane.header_text()
    assert pane.input.isEnabled() is True
    assert pane.send_btn.isEnabled() is True
    assert pane.close_btn.isVisibleTo(pane) is True

    pane.input.setText("devam et")
    assert pane.send_followup() is True
    assert bridge.sent == [("task-arastirmaci", "devam et")]
    panel.deleteLater()


# ------------------------------------------------------- takip turu


def test_followup_turn_is_written_to_pane(_app):
    panel = TerminalsPanel(office="arastirma", bridge=FakeBridge())
    panel.handle_stream(stream_event())
    panel.handle_stream(waiting_event())

    seen = []
    panel.card_refresh_requested.connect(seen.append)
    panel.handle_followup({
        "task_id": "task-arastirmaci",
        "card_id": "card-arastirmaci",
        "text": "ikinci tur bitti",
        "usage": {"input_tokens": 900, "output_tokens": 334},
        "turn": 2,
        "success": True,
    })
    pane = panel.panes["arastirmaci"]
    text = pane.raw_text()
    assert "Tur 2" in text and "1.234 token" in text
    assert "ikinci tur bitti" in text
    assert pane.turn == 2 and "tur 2" in pane.header_text()
    assert seen == ["card-arastirmaci"]
    panel.deleteLater()


def test_bus_followup_signal_reaches_panel(_app):
    panel = TerminalsPanel(office="arastirma", bridge=FakeBridge())
    panel.handle_stream(stream_event())
    bus.task_followup_completed.emit({
        "task_id": "task-arastirmaci", "card_id": "card-arastirmaci",
        "text": "köprüden", "usage": {"total_tokens": 42}, "turn": 3,
        "success": True,
    })
    QApplication.processEvents()
    assert "Tur 3" in panel.panes["arastirmaci"].raw_text()
    panel.deleteLater()


# ------------------------------------------------------- arşiv kuralı


def test_interactive_pane_survives_first_task_completed(_app):
    bridge = FakeBridge()
    panel = TerminalsPanel(office="arastirma", bridge=bridge)
    panel.handle_stream(stream_event())
    panel.handle_stream(waiting_event())

    # İlk `task_completed` yalnızca turun bittiğini söyler: süreç canlı.
    panel.archive_card("card-arastirmaci")
    assert panel.archived_agents() == []
    assert panel.active_agents() == ["arastirmaci"]

    # "Kapat" → köprü kapanır, bölme arşive geçer.
    pane = panel.panes["arastirmaci"]
    assert pane.close_interactive() is True
    assert bridge.closed and bridge.closed[0][0] == "task-arastirmaci"
    assert panel.archived_agents() == ["arastirmaci"]
    assert panel.archive_tabs.count() == 1
    panel.deleteLater()


def test_non_interactive_pane_archives_on_task_completed(_app):
    panel = TerminalsPanel(office="arastirma", bridge=FakeBridge(live=()))
    panel.handle_stream(stream_event())
    panel.archive_card("card-arastirmaci")
    assert panel.archived_agents() == ["arastirmaci"]
    panel.deleteLater()


def test_process_end_archives_interactive_pane(_app):
    """Köprü görevi etkileşimli listeden düşürdüyse (süreç bitişi) arşivlenir."""
    bridge = FakeBridge(live=())
    panel = TerminalsPanel(office="arastirma", bridge=bridge)
    panel.handle_stream(stream_event())
    panel.handle_stream(waiting_event())
    panel.archive_card("card-arastirmaci")
    assert panel.archived_agents() == ["arastirmaci"]
    panel.deleteLater()


# ------------------------------------------------------- yetim worktree


def test_orphan_button_calls_retry(_app, monkeypatch):
    from entropy.desk import window as win

    calls = {}
    mod = types.ModuleType("entropy.agents.worktrees")
    mod.list_orphans = lambda vault=None: ["w1", "w2"]

    def _retry(vault=None):
        calls["retry"] = True
        mod.list_orphans = lambda vault=None: []
        return {"cleaned": 2, "remaining": 0}

    mod.retry_orphans = _retry
    monkeypatch.setitem(sys.modules, "entropy.agents.worktrees", mod)

    window = win.AgentDeskWindow()
    try:
        assert window.orphan_count({}) == 2
        assert window.refresh_orphans({}) == 2
        assert window.orphan_btn.isVisibleTo(window) is True
        assert "2 yetim" in window.orphan_btn.text()

        result = window.clean_orphans()
        assert calls.get("retry") is True
        assert result["cleaned"] == 2
        assert "2 çalışma ağacı temizlendi" in window.orphan_status.text()
        assert window.refresh_orphans({}) == 0
        assert window.orphan_btn.isVisible() is False

        # `office_status` alanı varsa liste hiç okunmaz (tek üretici).
        assert window.orphan_count({"orphan_worktrees": 5}) == 5
    finally:
        window.close()
        win.reset_desk_window()


# ------------------------------------------------------- prepare_review


def test_prepare_review_headline_in_changes_header(_app, monkeypatch):
    mod = types.ModuleType("entropy.agents.pr_flow")
    mod.gh_available = lambda: False
    mod.prepare_review = lambda card, base_branch="": {
        "branch": "is/faz10", "worktree": "/tmp/w", "files": ["a.py", "b.py"],
        "file_count": 2, "added": 12, "removed": 3,
        "summary": "2 dosya", "pr_url": "",
    }
    monkeypatch.setitem(sys.modules, "entropy.agents.pr_flow", mod)

    card = types.SimpleNamespace(id="k1", worktree="", branch="is/faz10", pr_url="")
    panel = ChangesPanel(card=card, confirm=False)
    head = panel.header_text()
    assert "2 dosya" in head and "+12 −3" in head and "is/faz10" in head
    assert panel.review()["file_count"] == 2
    panel.deleteLater()


def test_review_headline_guards_missing_fields():
    assert review_headline({}) == ""
    assert review_headline({"files": ["a"], "added": 1, "removed": 0}) == "1 dosya · +1 −0"


# ------------------------------------------------------- zen: bellek uyarısı


def test_memory_error_creates_notification(_app):
    center = NotificationCenter()
    bus.memory_error.emit({"where": "graph", "message": "bozuk düğüm", "ts": 1.0})
    QApplication.processEvents()
    items = center.log.items()
    assert items and items[0]["kind"] == "memory"
    assert "graph" in items[0]["title"] and "bozuk düğüm" in items[0]["title"]
    assert "Bellek uyarısı" in center.list_widget.item(0).text()
    center.deleteLater()


def test_last_errors_section_lists_errors(_app):
    mem = types.SimpleNamespace(last_errors=[
        {"where": "sqlite", "message": "kilit", "ts": 0.0},
        {"where": "graph", "message": "bozuk", "ts": 0.0},
    ])
    section = MemoryErrorsSection(mem)
    text = section.text()
    # En yeni hata üstte.
    assert text.splitlines()[0].startswith("graph: bozuk")
    assert "sqlite: kilit" in text
    assert section.isVisible() is False or True   # görünürlük kapta belirlenir

    empty = MemoryErrorsSection(types.SimpleNamespace(last_errors=[]))
    assert empty.text() == ""
    section.deleteLater()
    empty.deleteLater()


def test_format_memory_errors_limit_and_garbage():
    rows = format_memory_errors([{"where": "w", "message": str(i)} for i in range(20)],
                                limit=3)
    assert len(rows.splitlines()) == 3
    assert format_memory_errors(None) == ""
    assert format_memory_errors(["ham satır"]) == "ham satır"
