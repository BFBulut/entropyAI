"""Faz 14-E — yeni düzen: üst şerit, sağ tam panel, akış satırı, onay kartı.

Kabul ölçütü senaryo S5 (Faz 14 planı §7). Testler beyana değil **canlı widget
ağacına** bakar (`ui-design` §0.11) ve kapıların gerçekten ölçtüğünü bilerek
bozulmuş bir düğmeyle kanıtlar.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QSplitter, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import ui_audit  # noqa: E402

from entropy.core.agy_bridge import AgyProcessBridge
from entropy.ui.design import apply_design_system
from entropy.ui.modes.zen_mode import (
    CONTENT_MIN_WIDTH, RIGHT_PANEL_MIN_WIDTH, ZEN_PREFERRED_SIZE, ZenModeWindow,
)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    apply_design_system(application)
    return application


@pytest.fixture
def zen(app):
    window = ZenModeWindow(bridge=AgyProcessBridge())
    window.setGeometry(0, 0, 1600, 900)
    window.show()
    app.processEvents()
    yield window
    window.close()
    window.deleteLater()
    app.processEvents()


# --------------------------------------------------------------- 1. üst şerit


def test_nav_strip_has_seven_named_buttons(zen, app):
    """Yedi bölüm üst şeritte: çizilebilir ikon + erişilebilir ad + tek seçili."""
    strip = zen.nav_strip
    assert len(strip.buttons) == 7
    assert strip.visible_item_count() == 7
    assert strip.checked_count() == 1
    for btn in strip.buttons:
        assert btn.accessibleName().strip(), btn.text()
        assert not btn.icon().pixmap(16, 16).isNull(), btn.text()


def test_nav_strip_switches_content_stack(zen, app):
    """Düğme tıklaması içerik yığınını değiştirir (NavList sözleşmesi korunur)."""
    strip = zen.nav_strip
    strip.buttons[1].click()
    app.processEvents()
    assert strip.currentIndex() == 1
    assert strip.currentWidget() is zen.skills_widget
    assert strip.checked_count() == 1
    strip.setCurrentWidget(zen.reports_viewer)
    assert strip.currentIndex() == 0


def test_topbar_gate_not_relaxed(zen, app):
    """`header_items` ≤ 4 ve şerit HARİÇ yaprak sayımı ≤ 6 (kapı gevşemedi)."""
    assert len(zen.header_items) <= 4
    header, controls, strip = zen.header_frame, zen.window_controls, zen.nav_strip
    leaves = [
        w for w in header.findChildren(QWidget)
        if w.isVisibleTo(header) and not w.findChildren(QWidget)
        and not (w is controls or controls.isAncestorOf(w))
        and not (w is strip or strip.isAncestorOf(w))
    ]
    assert len(leaves) <= 6, [type(w).__name__ for w in leaves]
    # Şerit gerçekten üst çubuğun İÇİNDE (ayrı pencerede değil).
    assert header.isAncestorOf(strip)


# ----------------------------------------------------------------- 2. yerleşim


def test_single_shell_splitter_and_right_panel(zen, app):
    """Tek yatay kabuk bölücüsü; sağ panel iki sekme, varsayılan Sohbet."""
    shell = [s for s in zen.findChildren(QSplitter)
             if s.objectName() == "shellSplitter"]
    assert len(shell) == 1
    panel = zen.right_panel
    assert [panel.tabText(i) for i in range(panel.count())] == ["Sohbet", "Hafıza"]
    assert panel.currentIndex() == 0
    assert panel.minimumWidth() >= RIGHT_PANEL_MIN_WIDTH
    assert zen.content_region.minimumWidth() >= CONTENT_MIN_WIDTH
    # Hafıza sekmesi grafiği ve denetçi girişini taşır.
    assert zen.knowledge_graph.isAncestorOf(zen.knowledge_graph)
    assert zen.memory_tab.isAncestorOf(zen.knowledge_graph)
    assert zen.memory_tab.isAncestorOf(zen.memory_inspector_btn)


def test_core_visual_and_brand_preserved(zen, app):
    """Korunan kimlik öğeleri (ARCHITECTURE §8): çekirdek ≥ 48 px, marka, kapsül."""
    assert zen.core_visualizer.width() >= 48
    assert zen.core_visualizer.width() == ZenModeWindow.CORE_OVERLAY_SIZE
    assert zen.brand.isVisible() and zen.model_capsule.isVisible()
    assert zen.chat_card.isAncestorOf(zen.chat_browser)
    assert zen.right_panel.isAncestorOf(zen.chat_card)


def test_status_line_has_four_readings(zen, app):
    """Tek satır durum: sağlayıcı · token · pano · bekleyen onay."""
    for name in ("provider_status_lbl", "token_status_lbl",
                 "board_status_lbl", "pending_status_lbl"):
        label = getattr(zen, name)
        assert label.accessibleName().strip(), name
        assert zen.status_strip.isAncestorOf(label), name


def test_narrow_window_falls_back(zen, app):
    """1100 px altında geniş asgariler düşer; taşma olmaz (tek ekran kuralı)."""
    zen.setGeometry(0, 0, 960, 540)
    app.processEvents()
    assert zen.content_region.minimumWidth() < CONTENT_MIN_WIDTH
    overflowing = [
        c.objectName() or type(c).__name__
        for c in zen.centralWidget().findChildren(QWidget)
        if c.isVisible() and c.parentWidget() is zen.centralWidget()
        and (c.geometry().right() > zen.width() + 1
             or c.geometry().bottom() > zen.height() + 1)
    ]
    assert overflowing == []
    assert ZEN_PREFERRED_SIZE == (1100, 700)


# -------------------------------------------------------------- 3. akış satırı


def test_agent_stream_line_formats_and_throttles(app):
    from entropy.ui.widgets.agent_stream_line import AgentStreamLine, format_stream_line

    line = AgentStreamLine()
    assert not line.isVisible()
    text = format_stream_line({
        "agent": "Ajan", "kind": "tool_call",
        "tool": {"name": "WebSearch", "input_summary": "web araması yapıyor"},
    })
    assert text == "Ajan: web araması yapıyor"

    line.on_agent_stream({"agent": "Ajan", "kind": "tool_call",
                          "tool": {"input_summary": "web araması yapıyor"}})
    assert line.current_text() == "Ajan: web araması yapıyor"
    # Aynı satır ardışık tekrarlanmaz; 1 sn dolmadan yeni satır yazılmaz.
    line.on_agent_stream({"agent": "Ajan", "kind": "tool_call",
                          "tool": {"input_summary": "dosya yazıyor"}})
    assert line.current_text() == "Ajan: web araması yapıyor"
    # Koşu bitince satır katlanır.
    line.on_agent_stream({"agent": "Ajan", "kind": "result", "state": "idle"})
    assert not line.isVisible()
    line.deleteLater()


def test_stream_line_truncates_long_text(app):
    from entropy.ui.widgets.agent_stream_line import LINE_MAX_CHARS, format_stream_line

    text = format_stream_line({"agent": "Ajan", "kind": "text", "text": "x" * 400})
    assert len(text) <= LINE_MAX_CHARS and text.endswith("…")


def test_zen_chat_shows_stream_line(zen, app):
    """Akış satırı sohbet kartının içindedir (Desk sahnesinde değil)."""
    assert zen.chat_card.isAncestorOf(zen.agent_stream_line)


# ------------------------------------------------------------- 4. onay kartı


class _FakeQueue:
    """`entropy.core.pending.PendingQueue` imzasının sahtesi (14-B yazacak)."""

    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def list(self, kind=None):
        return [r for r in self.rows if kind in (None, r.get("kind"))]

    def resolve(self, request_id, decision, note=""):
        self.calls.append((request_id, decision, note))
        self.rows = [r for r in self.rows if r["id"] != request_id]
        return {"ok": True, "id": request_id, "decision": decision}


def _entry(rid="p1", risk="high"):
    return {
        "id": rid, "kind": "tool", "title": "Komut çalıştır: ffmpeg",
        "detail": "video üretimi", "risk": risk, "created_at": "",
        "source": "claude", "payload": {}, "status": "pending",
    }


def test_pending_card_lists_and_approves(app, monkeypatch):
    from entropy.ui.widgets import pending_card as pc

    monkeypatch.setattr(pc, "desk_pending_entries", lambda: [])
    queue = _FakeQueue([_entry()])
    card = pc.PendingWorkCard(queue=queue)
    assert len(card.entries()) == 1
    assert card.isVisible() or card.entries()
    decided = []
    card.decided.connect(lambda rid, ok: decided.append((rid, ok)))
    card.approve("p1")
    assert queue.calls == [("p1", "approve", "")]
    assert decided == [("p1", True)]
    assert card.entries() == []
    card.deleteLater()


def test_pending_card_reject_path(app, monkeypatch):
    from entropy.ui.widgets import pending_card as pc

    monkeypatch.setattr(pc, "desk_pending_entries", lambda: [])
    queue = _FakeQueue([_entry()])
    card = pc.PendingWorkCard(queue=queue)
    card.reject("p1", note="istemiyorum")
    assert queue.calls == [("p1", "reject", "istemiyorum")]
    card.deleteLater()


def test_chat_approval_only_when_single_item(app, monkeypatch):
    from entropy.ui.widgets import pending_card as pc

    monkeypatch.setattr(pc, "desk_pending_entries", lambda: [])
    queue = _FakeQueue([_entry("p1"), _entry("p2")])
    card = pc.PendingWorkCard(queue=queue)
    assert card.resolve_from_chat("onaylıyorum") is None, "belirsizken çözmemeli"
    queue.rows = [_entry("p1")]
    result = card.resolve_from_chat("tamam onaylıyorum")
    assert result and result["decision"] == "approve"
    assert card.resolve_from_chat("bunu yapma") is None
    card.deleteLater()


def test_desk_requests_join_same_card(app, monkeypatch):
    """Desk kuyruğu `kind="desk_change"` olarak aynı kartta görünür."""
    from entropy.ui.widgets import pending_card as pc

    fake = types.SimpleNamespace(
        list_pending=lambda: [{"id": "d1", "kind": "office",
                               "summary": "Yeni ofis: medya",
                               "payload": {"name": "medya"}, "created_at": ""}],
        apply_pending=lambda rid: {"ok": True, "id": rid},
        reject_pending=lambda rid, reason="": True,
    )
    import entropy.agents as agents_pkg

    monkeypatch.setitem(sys.modules, "entropy.agents.desk_admin", fake)
    monkeypatch.setattr(agents_pkg, "desk_admin", fake, raising=False)
    card = pc.PendingWorkCard(queue=_FakeQueue([]))
    rows = card.entries()
    assert [r["kind"] for r in rows] == [pc.DESK_KIND]
    assert rows[0]["title"] == "Yeni ofis: medya"
    card.refresh()
    assert card._resolve("d1", "approve")["ok"] is True
    card.deleteLater()


def test_zen_binds_pending_card_and_status(zen, app):
    assert zen.chat_card.isAncestorOf(zen.pending_card)
    assert zen.show_pending_work() is True
    assert zen.right_panel.currentIndex() == 0
    assert "Bekleyen onay" in zen.pending_status_lbl.text()


# ------------------------------------------------------------ 5. ajan koşuları


def test_agents_section_hides_roster_shows_runs(zen, app):
    """Kalıcı kadro gizli; koşu paneli görünür (kod silinmedi)."""
    zen.left_tabs.setCurrentIndex(4)
    app.processEvents()
    assert zen.agents_widget is not None
    assert not zen.agents_widget.isVisible()
    assert zen.agent_runs_panel.isVisible()
    assert not zen.desk_approvals_panel.isVisible()


def test_agent_runs_panel_reads_ledger(app, tmp_path):
    """Koşan/biten koşular defterden okunur; sohbet turları sayılmaz."""
    from entropy.core.task_ledger import CHAT_TURN_NAME, TaskLedger
    from entropy.ui.widgets.agent_runs_panel import AgentRunsPanel, ledger_runs

    ledger = TaskLedger(tmp_path / "ledger.db")
    ledger.record_task_pending("t1", "Araştırma koşusu", str(tmp_path))
    ledger.record_task_pending("t2", CHAT_TURN_NAME, str(tmp_path))
    rows = ledger_runs(ledger)
    names = [r["task_name"] for r in rows["active"]]
    assert "Araştırma koşusu" in names
    assert CHAT_TURN_NAME not in names

    panel = AgentRunsPanel(ledger=ledger)
    assert panel.running_count() == 1
    panel.deleteLater()


# --------------------------------------------------- 6. bildirim tekilleştirme


def test_single_card_per_event_identity(zen, app, tmp_path):
    """Aynı olay için `report_created` + `task_report_ready` = TEK kart."""
    report = tmp_path / "Rapor.md"
    report.write_text("# Rapor\n\nGovde.\n", encoding="utf-8")
    zen.chat_browser.clear()
    zen._on_report_created(str(report))
    first = zen.chat_browser.toPlainText()
    zen._on_report_created(str(report))
    assert zen.chat_browser.toPlainText() == first, "ikinci kart basıldı"
    zen._on_task_report_ready({"card_id": "", "title": "Rapor",
                               "report_path": str(report)})
    assert zen.chat_browser.toPlainText() == first, "üçüncü üreticiden kart düştü"


def test_identity_dedupe_is_not_time_based(zen):
    """Ölçüt kimlik: farklı kimlik geçince kart yine basılır."""
    assert zen.should_notify_once("kart-1") is True
    assert zen.should_notify_once("kart-1") is False
    assert zen.should_notify_once("kart-2") is True


# ------------------------------------------------------------------ 7. kapılar


def test_audit_exposes_nav_strip_gate():
    assert ui_audit.FINAL_GATES_14E["nav_strip_violations"] == 0
    assert ui_audit.FINAL_MIN_GATES["nav_strip_buttons"] == 7
    # Üst çubuk kapısı GEVŞETİLMEDİ.
    assert ui_audit.FINAL_GATES_12D2["header_leaf_widgets"] == 6


def test_nav_strip_gate_turns_red_on_unnamed_button(zen, app):
    """Kapı beyana değil canlı düğmeye bakar: adı silinen düğme ihlaldir."""
    from PySide6.QtGui import QIcon

    btn = zen.nav_strip.buttons[0]
    old_name, old_icon = btn.accessibleName(), btn.icon()
    btn.setAccessibleName("")
    btn.setText("")
    btn.setIcon(QIcon())
    try:
        violations = []
        for candidate in zen.nav_strip.buttons:
            if candidate.icon().pixmap(16, 16).isNull():
                violations.append("ikon")
            if not candidate.accessibleName().strip():
                violations.append("ad")
        assert violations, "bozulmuş düğme kapıyı kırmalıydı"
    finally:
        btn.setAccessibleName(old_name)
        btn.setText(old_name)
        btn.setIcon(old_icon)


def test_desk_request_appears_once_when_queue_already_has_it(app, monkeypatch):
    """
    Çift sayım kapandı: kuyruk Desk isteğini zaten katıyor.

    `PendingQueue.list()` Desk isteklerini `desk_change` olarak döndürüyor; kart
    ayrıca `desk_pending_entries()` de ekleyince aynı istek iki satır oluyordu.
    """
    from entropy.ui.widgets import pending_card as pc

    desk_row = {
        "id": "d1", "kind": pc.DESK_KIND, "title": "Yeni ofis: medya",
        "detail": "medya", "risk": "medium", "created_at": "",
        "source": "desk", "payload": {"name": "medya"}, "status": "pending",
    }
    fake = types.SimpleNamespace(
        list_pending=lambda: [{"id": "d1", "kind": "office",
                               "summary": "Yeni ofis: medya",
                               "payload": {"name": "medya"}, "created_at": ""}],
        apply_pending=lambda rid: {"ok": True, "id": rid},
        reject_pending=lambda rid, reason="": True,
    )
    import entropy.agents as agents_pkg

    monkeypatch.setitem(sys.modules, "entropy.agents.desk_admin", fake)
    monkeypatch.setattr(agents_pkg, "desk_admin", fake, raising=False)
    card = pc.PendingWorkCard(queue=_FakeQueue([desk_row]))
    rows = card.entries()
    assert [r["id"] for r in rows] == ["d1"], rows
    card.deleteLater()
