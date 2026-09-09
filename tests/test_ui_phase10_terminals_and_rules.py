"""
Faz 10-B arayüz testleri: ajan başına terminal, sprite durum eşleme, kural
onayı, kontrol noktası/kanıt görünümü ve çalışma belleği görüntüleyici.

Model çağrısı, süreç başlatma ve gerçek kasaya yazma YOKTUR: akış yükleri
sahtedir (`bus.agent_stream` sözleşmesi), kural deposu `tmp_path` kasasına
yazılır, köprü sahte bir nesnedir.

Ekran görüntüleri `scratch/ui/phase10/` altına düşer (varsa yeniden yazılır).
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from entropy.desk.scene import (
    OfficeScene, STATE_ERROR, STATE_IDLE, STATE_THINKING, STATE_WORKING,
    BUBBLE_MAX_CHARS, BUBBLE_TTL_MS,
)
from entropy.desk.terminals_panel import TerminalsPanel
from entropy.ui.widgets.rules_panel import RuleCandidatesPanel
from entropy.ui.widgets.task_board_widget import (
    TaskBoardWidget, card_proof, proof_is_missing,
)

SHOT_DIR = Path(__file__).resolve().parent.parent / "scratch" / "ui" / "phase10"


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    return app


def shoot(widget, name: str) -> Path:
    """Widget'ın ekran görüntüsünü kaydeder (offscreen kanvas)."""
    widget.resize(max(widget.width(), 720), max(widget.height(), 420))
    widget.show()
    QApplication.processEvents()
    path = SHOT_DIR / f"{name}.png"
    widget.grab().save(str(path))
    return path


def stream_event(agent, **over):
    """`bus.agent_stream` sözleşmesine uyan sahte yük."""
    payload = {
        "task_id": f"task-{agent}",
        "card_id": f"card-{agent}",
        "office": "arastirma",
        "agent": agent,
        "provider": "test",
        "model": "test-model",
        "kind": "text",
        "text": "",
        "full_text": "",
        "tool": None,
        "state": "working",
        "ts": 0.0,
    }
    payload.update(over)
    return payload


class FakeCard:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class FakeBoard:
    def __init__(self, cards=()):
        self._cards = {c.id: c for c in cards}

    def get(self, card_id):
        return self._cards.get(card_id)

    def list(self, **_kw):
        return list(self._cards.values())


class FakeBridge:
    """`send_followup` sözleşmesi: koşan ajana stdin ile mesaj."""

    def __init__(self, accept=True):
        self.accept = accept
        self.sent = []

    def send_followup(self, task_id, text):
        self.sent.append((task_id, text))
        return self.accept


# --------------------------------------------------------- 1) terminal bölmeleri


def test_terminal_panes_do_not_mix_two_agents(_app):
    panel = TerminalsPanel(office="arastirma")
    panel.handle_stream(stream_event("arastirmaci", text="kaynak taranıyor"))
    panel.handle_stream(stream_event("yazar", text="taslak yazılıyor"))
    panel.handle_stream(stream_event("arastirmaci", text="ikinci kaynak"))

    assert set(panel.active_agents()) == {"arastirmaci", "yazar"}
    first = panel.stream_text("arastirmaci")
    second = panel.stream_text("yazar")
    assert "kaynak taranıyor" in first and "ikinci kaynak" in first
    assert "taslak" not in first
    assert "taslak yazılıyor" in second and "kaynak" not in second

    shoot(panel, "terminals_two_agents")
    panel.deleteLater()


def test_terminal_kinds_are_colored_and_raw_text_visible(_app):
    panel = TerminalsPanel(office="arastirma")
    panel.handle_stream(stream_event("a", kind="thinking", text="düşünüyorum",
                                     state="thinking"))
    panel.handle_stream(stream_event("a", kind="tool_call",
                                     tool={"name": "Read", "input_summary": "x.py"}))
    panel.handle_stream(stream_event("a", kind="result", text="bitti", state="idle"))
    panel.handle_stream(stream_event("a", kind="error", text="çöktü", state="error"))

    pane = panel.pane_for("a")
    # Qt zengin metni renkleri küçük harfe indirir.
    html = pane.view.toHtml().lower()
    assert "#ef4444" in html          # hata kırmızı
    assert "#3de8a8" in html          # sonuç yeşil
    assert "#ffc24d" in html          # araç çağrısı sarı
    assert "italic" in html           # düşünce italik
    raw = pane.raw_text()
    assert "düşünüyorum" in raw and "Read(x.py)" in raw and "çöktü" in raw
    panel.deleteLater()


def test_terminal_layout_switches_to_tabs_at_four_agents(_app):
    panel = TerminalsPanel(office="arastirma")
    for name in ("a", "b", "c"):
        panel.handle_stream(stream_event(name, text="x"))
    assert panel.is_tabbed() is False
    panel.handle_stream(stream_event("d", text="x"))
    assert panel.is_tabbed() is True
    assert panel.tabs.count() == 4
    panel.deleteLater()


def test_finished_card_pane_moves_to_archive_and_is_kept(_app):
    panel = TerminalsPanel(office="arastirma")
    panel.handle_stream(stream_event("arastirmaci", text="çıktı"))
    assert panel.archive_card("card-arastirmaci") is True
    assert panel.archived_agents() == ["arastirmaci"]
    assert panel.active_agents() == []
    # Bölme silinmez: metni hâlâ okunabilir.
    assert "çıktı" in panel.stream_text("arastirmaci")
    assert panel.archive_tabs.count() == 1
    panel.deleteLater()


def test_followup_input_disabled_without_bridge_and_sends_with_bridge(_app):
    panel = TerminalsPanel(office="arastirma")
    panel.handle_stream(stream_event("arastirmaci", text="çıktı"))
    pane = panel.pane_for("arastirmaci")
    assert pane.can_send() is False
    assert pane.input.isEnabled() is False
    assert pane.input.toolTip()          # pasifken ipucu var

    bridge = FakeBridge()
    panel.set_bridge(bridge)
    assert pane.can_send() is True
    pane.input.setText("şu dosyaya da bak")
    assert pane.send_followup() is True
    assert bridge.sent == [("task-arastirmaci", "şu dosyaya da bak")]
    panel.deleteLater()


def test_focus_agent_raises_pane(_app):
    panel = TerminalsPanel(office="arastirma")
    for name in ("a", "b", "c", "d"):
        panel.handle_stream(stream_event(name, text="x"))
    panel.focus_agent("c")
    assert panel.tabs.currentWidget() is panel.pane_for("c")
    assert panel.agent == "c"
    panel.deleteLater()


# ------------------------------------------------------------- 2) sahne eşleme


def make_scene():
    scene = OfficeScene()
    scene.set_office({
        "name": "arastirma",
        "orchestrator": "lider",
        "evaluator": "denetci",
        "members": ["lider", "arastirmaci", "denetci"],
    })
    return scene


def test_scene_maps_stream_state_to_sprite_state(_app):
    scene = make_scene()
    for state, expected in (
        ("thinking", STATE_THINKING),
        ("working", STATE_WORKING),
        ("error", STATE_ERROR),
        ("idle", STATE_IDLE),
    ):
        scene.handle_stream(stream_event("arastirmaci", state=state, text="x"))
        assert scene.states()["arastirmaci"] == expected
    scene.deleteLater()


def test_scene_bubble_is_clipped_and_expires(_app):
    scene = make_scene()
    long_text = "kaynak " * 40
    scene.handle_stream(stream_event("arastirmaci", state="thinking", text=long_text))
    bubble = scene.bubbles()["arastirmaci"]
    assert len(bubble) <= BUBBLE_MAX_CHARS
    assert bubble.endswith("…")

    shoot(scene, "scene_thinking_bubble")

    scene.expire_bubbles(BUBBLE_TTL_MS - 100)
    assert "arastirmaci" in scene.bubbles()
    scene.expire_bubbles(200)
    assert scene.bubbles() == {}
    scene.deleteLater()


def test_scene_error_state_shows_bubble_and_unknown_agent_is_ignored(_app):
    scene = make_scene()
    scene.handle_stream(stream_event("arastirmaci", state="error", kind="error",
                                     text="komut başarısız"))
    assert scene.states()["arastirmaci"] == STATE_ERROR
    assert "komut başarısız" in scene.bubbles()["arastirmaci"]
    # Sahnede olmayan ajan sessizce yok sayılır (çökme yok).
    scene.handle_stream(stream_event("yok-boyle-ajan", state="working"))
    assert "yok-boyle-ajan" not in scene.states()
    scene.deleteLater()


def test_scene_other_office_stream_is_ignored(_app):
    scene = make_scene()
    scene.handle_stream(stream_event("arastirmaci", office="baska-ofis",
                                     state="error"))
    assert scene.states()["arastirmaci"] == STATE_IDLE
    scene.deleteLater()


def test_scene_click_target_agent_is_focusable_in_terminals(_app):
    """Sprite tıklaması -> Terminaller bölmesi öne (pencere kablolaması)."""
    scene = make_scene()
    panel = TerminalsPanel(office="arastirma")
    scene.agent_clicked.connect(panel.focus_agent)
    scene.select_agent("arastirmaci")
    assert panel.pane_for("arastirmaci", create=False) is not None
    assert panel.agent == "arastirmaci"
    scene.deleteLater()
    panel.deleteLater()


# -------------------------------------------------------------- 3) kural onayı


@pytest.fixture
def rules_vault(tmp_path, monkeypatch):
    """Kural deposunu geçici kasaya bağlar (gerçek kasa salt okunur kalır)."""
    from entropy.memory import promoted_rules

    monkeypatch.setattr(promoted_rules, "_vault_root", lambda vault_path=None: tmp_path)
    return promoted_rules


def test_rule_candidates_promote_and_reject(_app, rules_vault):
    rules_vault.propose_rule(
        "arastirma", "arastirmaci",
        "Rapor yazmadan önce kaynakları tarihe göre sırala.",
        source="card-1",
    )
    rules_vault.propose_rule(
        "arastirma", "yazar",
        "Her bölümün sonunda tek cümlelik özet bırak.",
        source="card-2",
    )
    panel = RuleCandidatesPanel(office="arastirma")
    assert len(panel.candidates()) == 2
    shoot(panel, "rules_panel")

    first = panel.candidates()[0]
    assert panel.promote_rule(first.id) is True
    assert [r.id for r in panel.approved()] == [first.id]
    # Onaylı kural sistem istemi bloğuna girer; aday girmez.
    section = rules_vault.rules_section("arastirma")
    assert first.text in section
    assert panel.candidates()[0].text not in section

    second = panel.candidates()[0]
    assert panel.reject_rule(second.id) is True
    assert panel.candidates() == []
    assert second.text not in rules_vault.rules_section("arastirma")
    panel.deleteLater()


def test_rule_panel_entropy_office_is_separate(_app, rules_vault):
    rules_vault.propose_rule(
        "entropy", "entropy",
        "Kozmetik değişiklik hafıza işinin önüne geçmesin.",
    )
    entropy_panel = RuleCandidatesPanel(office="entropy")
    office_panel = RuleCandidatesPanel(office="arastirma")
    assert len(entropy_panel.candidates()) == 1
    assert office_panel.candidates() == []
    assert "Entropy" in entropy_panel.title_label.text()
    entropy_panel.deleteLater()
    office_panel.deleteLater()


def test_rule_panel_without_memory_module_is_empty(_app, monkeypatch):
    """Bellek modülü yoksa panel boş ve sessiz kalır (pencere çökmez)."""
    from entropy.ui.widgets import rules_panel as mod

    monkeypatch.setattr(mod, "rules_api", lambda: None)
    panel = RuleCandidatesPanel(office="arastirma")
    assert panel.candidates() == []
    assert panel.promote_rule("x") is False
    panel.deleteLater()


# ------------------------------------------------- 4) kontrol noktası ve kanıt


def make_board():
    return FakeBoard([
        FakeCard(
            id="c-green", title="Yeşil kanıtlı", status="review", office="arastirma",
            agent="arastirmaci", provider="test", model="m", goal="hedef",
            criteria=["ölçüt"], output_paths=[], summary="", parent="", children=[],
            project="", budget_tokens=0, notes="", effort="",
            checkpoint={
                "summary": "İki kaynak tarandı",
                "next_steps": "Üçüncü kaynağı ekle",
                "files_touched": ["rapor.md"],
                "updated_at": "2026-09-09T10:00:00",
            },
            proof={"command": "pytest tests/test_x.py", "result": "green",
                   "ok": True, "summary": "3 test geçti"},
        ),
        FakeCard(
            id="c-none", title="Kanıtsız", status="review", office="arastirma",
            agent="yazar", provider="test", model="m", goal="hedef",
            criteria=[], output_paths=[], summary="", parent="", children=[],
            project="", budget_tokens=0, notes="", effort="",
        ),
    ])


def test_card_detail_shows_checkpoint_and_green_proof(_app):
    widget = TaskBoardWidget(board=make_board(), office="arastirma")
    widget.select_card("c-green")
    detail = widget.detail_panel
    assert detail.checkpoint_label.isVisibleTo(widget)
    assert "İki kaynak tarandı" in detail.checkpoint_label.text()
    assert "Üçüncü kaynağı ekle" in detail.checkpoint_label.text()
    assert "yeşil" in detail.proof_label.text()
    assert "pytest tests/test_x.py" in detail.proof_label.text()
    shoot(widget, "card_proof")
    widget.deleteLater()


def test_card_without_proof_is_marked_missing(_app):
    board = make_board()
    card = board.get("c-none")
    assert card_proof(card) is None
    assert proof_is_missing(card) is True
    assert proof_is_missing(board.get("c-green")) is False

    widget = TaskBoardWidget(board=board, office="arastirma")
    widget.select_card("c-none")
    assert "kanıt yok" in widget.detail_panel.proof_label.text()
    # İnceleme sütunundaki kart "kanıt eksik" etiketiyle işaretlenir.
    from entropy.ui.widgets.task_board_widget import TaskCardWidget

    flags = {
        w.card_id: w.proof_missing
        for w in widget.findChildren(TaskCardWidget)
    }
    assert flags.get("c-none") is True
    assert flags.get("c-green") is False
    widget.deleteLater()


def test_red_proof_is_marked_missing(_app):
    card = FakeCard(id="c-red", title="Kırmızı", status="review", office="o",
                    proof={"command": "pytest", "result": "red", "ok": False,
                           "summary": "1 test düştü"})
    assert proof_is_missing(card) is True
    # Bekleyen kartta etiket yok: iş henüz bitmedi.
    assert proof_is_missing(FakeCard(id="x", status="backlog", office="o")) is False


# --------------------------------------------- 5) çalışma belleği görüntüleyici


def test_workspace_viewer_reads_board_architecture_rules(_app, tmp_path, monkeypatch):
    from entropy.desk.projects_panel import ProjectsPanel

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "BOARD.md").write_text("# Pano\n\n- kart-1", encoding="utf-8")
    (ws / "ARCHITECTURE.md").write_text("# Mimari\n\nModüller", encoding="utf-8")

    panel = ProjectsPanel(office="arastirma", desk=None, board=FakeBoard())
    monkeypatch.setattr(
        panel, "workspace_paths",
        lambda: {"board": ws / "BOARD.md",
                 "architecture": ws / "ARCHITECTURE.md",
                 "rules": ws / "RULES.md"},
    )
    assert "kart-1" in panel.show_workspace("board")
    assert "Pano" in panel.workspace_text()
    assert "Modüller" in panel.show_workspace("architecture")
    # Yazılmamış dosya: boş kutu değil, açıklayıcı satır.
    assert panel.show_workspace("rules") == ""
    assert "RULES.md" in panel.workspace_text()
    panel.deleteLater()


# --------------------------------------------------------- 6) harcama şeridi


def test_spend_tooltip_lists_running_cards(_app):
    from entropy.desk.window import AgentDeskWindow

    info = {
        "spent_tokens": 4200,
        "budget_tokens": 60000,
        "running": [
            {"id": "c1", "title": "Kaynak taraması", "tokens": 1200,
             "budget": 20000, "phase": "running"},
            {"id": "c2", "title": "Rapor yazımı", "tokens": 3000, "budget": 0},
        ],
    }
    tip = AgentDeskWindow.spend_tooltip(info)
    assert "Kaynak taraması: 1.200 / 20.000 token" in tip
    assert "Rapor yazımı: 3.000 token" in tip
    assert AgentDeskWindow.spend_tooltip({"spent_tokens": 5}).startswith("Koşan kart yok")


# ------------------------------------------------------ 7) pencere kablolaması


def test_desk_window_terminals_tab_and_sprite_click(_app):
    from entropy.desk.window import (
        AgentDeskWindow, TAB_TERMINALS, reset_desk_window,
    )

    reset_desk_window()
    window = AgentDeskWindow(office_registry=None, agent_registry=None)
    tabs = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert tabs[TAB_TERMINALS] == "Terminaller"
    # Sprite tıklaması: Terminaller sekmesi öne gelir, bölme o ajana odaklanır.
    window._on_agent_clicked("arastirmaci")
    assert window.tabs.currentIndex() == TAB_TERMINALS
    assert window.terminals_panel.agent == "arastirmaci"
    assert window.stream_panel.agent == "arastirmaci"
    window.close()
    window.deleteLater()
    reset_desk_window()
