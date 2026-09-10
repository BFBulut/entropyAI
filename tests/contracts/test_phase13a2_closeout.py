"""
Faz 13-A2 kapanış sözleşmeleri (qa-build-engineer).

Dört küçük düzeltmenin regresyon kilidi:
(a) `TaskCard.brain_only` alanı + `/task --brain-only` + `board_create`;
(b) `desk/projects_panel.git_branches` konsol penceresi açmaz;
(c) `agy_bridge` `taskkill` çağrıları gizli bayrak alır;
(d) `board.drift` tekil `seq` ile ve KENDİ korelasyonuyla yazılır.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from entropy.agents import board_autonomy
from entropy.agents.tasks import TaskBoard, TaskCard

SRC = Path(__file__).resolve().parents[2] / "src" / "entropy"


# -- (a) brain_only ------------------------------------------------------

def test_task_card_has_brain_only_field_and_round_trips(tmp_path):
    board = TaskBoard(tmp_path)
    card = board.create(TaskCard(id="", title="Yalnız beyin", brain_only=True))
    assert card.brain_only is True
    again = TaskBoard(tmp_path).get(card.id)
    assert again is not None and again.brain_only is True
    assert card.to_frontmatter()["brain_only"] is True


def test_brain_only_defaults_false(tmp_path):
    board = TaskBoard(tmp_path)
    card = board.create(TaskCard(id="", title="Sıradan kart"))
    assert card.brain_only is False
    assert TaskBoard(tmp_path).get(card.id).brain_only is False


def test_brain_only_requested_reads_the_card_field():
    from entropy.agents import amplification

    card = TaskCard(id="x", title="araştır", brain_only=True)
    assert amplification.brain_only_requested(card, "araştır") is True
    assert amplification.brain_only_requested(TaskCard(id="x"), "araştır") is False


def test_ask_brain_passes_the_card_to_brain_lookup(monkeypatch, tmp_path):
    """Kartın açık tercihi beyne ULAŞMALI (bağlantı yoksa alan ölü kalır)."""
    from entropy.agents import amplification

    seen = {}

    def fake_lookup(query, builder=None, card=None):
        seen["card"] = card
        return None

    monkeypatch.setattr(amplification, "brain_lookup", fake_lookup)
    board = TaskBoard(tmp_path)
    card = TaskCard(id="k1", title="araştır", goal="hedef", brain_only=True)
    board._brain_consult(card)
    assert seen.get("card") is card


def test_slash_task_parses_brain_only_flag_out_of_the_title(tmp_path, monkeypatch):
    from entropy.core import slash_commands

    monkeypatch.setattr(slash_commands, "_handle_task", slash_commands._handle_task)
    board = TaskBoard(tmp_path)
    monkeypatch.setattr("entropy.agents.tasks.TaskBoard", lambda *a, **k: board)
    from entropy.agents.registry import AgentRegistry

    class _Spec:
        name = "arastirmaci"
        provider = "claude"
        model = ""
        skills = []

    monkeypatch.setattr(AgentRegistry, "get", lambda self, n: _Spec())
    monkeypatch.setattr(AgentRegistry, "list", lambda self: [_Spec()])
    slash_commands._handle_task("arastirmaci --brain-only Kısa konu :: hedef")
    cards = board.list()
    assert cards, "kart açılmadı"
    card = cards[-1]
    assert card.brain_only is True
    assert "--brain-only" not in card.title
    assert "brain-only" not in card.goal


def test_board_create_accepts_brain_only(tmp_path):
    board = TaskBoard(tmp_path)
    card, _ = board_autonomy.create_card_from_args(
        {"title": "Beyin kartı", "goal": "hedef", "brain_only": True}, board=board
    )
    assert card is not None and card.brain_only is True
    plain, _ = board_autonomy.create_card_from_args(
        {"title": "Düz kart", "goal": "hedef"}, board=board
    )
    assert plain.brain_only is False


def test_board_create_reads_the_marker_in_text(tmp_path):
    board = TaskBoard(tmp_path)
    card, _ = board_autonomy.create_card_from_args(
        {"title": "Konu", "goal": "yalnız beyin: özetle"}, board=board
    )
    assert card is not None and card.brain_only is True


# -- (b) + (c) konsol penceresi -----------------------------------------

def _call_has_hidden_kwargs(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg is None and isinstance(kw.value, ast.Call):
            fn = kw.value.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name == "popen_kwargs":
                return True
    return False


def _spawn_calls(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("run", "Popen", "check_output", "check_call", "call"):
                base = node.func.value
                if getattr(base, "id", None) == "subprocess":
                    yield node


@pytest.mark.parametrize("rel", ["desk/projects_panel.py", "core/agy_bridge.py"])
def test_every_subprocess_call_hides_its_console(rel):
    path = SRC / rel
    bad = [n.lineno for n in _spawn_calls(path) if not _call_has_hidden_kwargs(n)]
    assert bad == [], f"{rel}: gizlemeyen çağrı satırları {bad}"


def test_taskkill_calls_still_hidden():
    """`shell=True` + `taskkill` en kolay pencere sızdıran yoldur."""
    text = (SRC / "core" / "agy_bridge.py").read_text(encoding="utf-8")
    assert "taskkill" in text
    for node in _spawn_calls(SRC / "core" / "agy_bridge.py"):
        src = ast.unparse(node)
        if "taskkill" in src:
            assert _call_has_hidden_kwargs(node), f"gizlemeyen taskkill: {node.lineno}"


# -- (d) board.drift ------------------------------------------------------

def test_drift_event_gets_its_own_correlation(tmp_path):
    board = TaskBoard(tmp_path)
    card = board.create(TaskCard(id="", title="Kart"))
    board._announce_drift(
        [{"id": card.id, "card": "backlog", "projection": "running"}],
        {"projection_hash": "abc123def456ghi789"},
    )
    drift = [e for e in board.events.read() if e["action"] == "board.drift"]
    assert len(drift) == 1
    assert drift[0]["correlation_id"] == "drift:abc123def456ghi7"
    assert drift[0]["correlation_id"] != card.id


def test_seq_stays_unique_across_two_log_instances(tmp_path):
    """İki ayrı `BoardEventLog` (ikinci süreç benzeri) aynı `seq`i yazmasın."""
    from entropy.agents.board_events import BoardEventLog

    a = BoardEventLog(tmp_path)
    b = BoardEventLog(tmp_path)
    b.last_seq()  # b önbelleğini ŞİMDİ doldurur: bundan sonrası onun için bayat
    a.append(action="board.drift", task_id="k1", actor="system",
             idempotency_key="d1")
    # `b` günlüğü `a`nın yazımından ÖNCE okumuş gibi: önbelleği bayat.
    b.append(action="board.drift", task_id="k2", actor="system",
             idempotency_key="d2")
    a.append(action="board.drift", task_id="k3", actor="system",
             idempotency_key="d3")
    seqs = [e["seq"] for e in a.read()]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs), f"tekrarlı seq: {seqs}"


def test_drift_is_idempotent_per_projection_hash(tmp_path):
    board = TaskBoard(tmp_path)
    card = board.create(TaskCard(id="", title="Kart"))
    row = [{"id": card.id, "card": "backlog", "projection": "running"}]
    board._announce_drift(row, {"projection_hash": "hash-1"})
    board._announce_drift(row, {"projection_hash": "hash-1"})
    drift = [e for e in board.events.read() if e["action"] == "board.drift"]
    assert len(drift) == 1


def test_stale_instance_cannot_write_the_same_idempotency_key_twice(tmp_path):
    """Gerçek günlükteki hata: seq 45 ve 46 aynı `drift:` anahtarıyla yazılmış."""
    from entropy.agents.board_events import BoardEventLog

    a = BoardEventLog(tmp_path)
    b = BoardEventLog(tmp_path)
    b.last_seq()
    assert a.append(action="board.drift", task_id="k1", actor="system",
                    idempotency_key="drift:same") is not None
    assert b.append(action="board.drift", task_id="k1", actor="system",
                    idempotency_key="drift:same") is None
    assert len(a.read()) == 1


def test_brain_lookup_signature_accepts_card_keyword():
    """Gerçek sözleşme: `card=` kabul edilmezse `_brain_consult` TypeError'ı
    geniş `except`te yutar ve kısa devre SESSİZCE hiç tetiklenmez."""
    import inspect

    from entropy.agents import amplification

    params = inspect.signature(amplification.brain_lookup).parameters
    assert "card" in params
    assert params["card"].default is None
