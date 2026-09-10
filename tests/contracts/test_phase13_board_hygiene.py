"""
Faz 13-A2 sözleşmeleri: ajan canlı durumu, konsol penceresi, sessiz oturum devri.

Üç kullanıcı şikâyeti buradaki üç bölüme birebir karşılık gelir:

A. Rozet "kalıcı oturum · claude · 2 sa önce" diyordu, oysa ajan agy ile
   koşuyordu (başka sağlayıcının BAYAT oturumu gösteriliyordu).
B. "Bir görev çalıştırınca ~20 pencere açılıp kapanıyor" — pencereli exe'nin
   açtığı her konsol alt süreci.
C. "Oturumu yenile" sohbete otonom görev kartı + çip düşürüyordu.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

from entropy.agents import board_events, board_fsm
from entropy.agents.tasks import TaskBoard, TaskCard
from entropy.core.identity import AgentSessionStore

SRC = Path(__file__).resolve().parents[2] / "src" / "entropy"


# ---------------------------------------------------------------------------
# A. Ajan canlı durum API'si
# ---------------------------------------------------------------------------

def test_status_returns_full_contract_keys(tmp_path, monkeypatch):
    store = AgentSessionStore(tmp_path)
    monkeypatch.setattr(store, "current_provider", lambda name: "agy")
    st = store.status("arastirmaci")
    assert set(st) >= {"state", "since", "card_id", "card_title",
                       "last_run_at", "provider", "stale_sessions"}
    assert st["state"] == "idle"
    assert st["since"] is None
    assert st["last_run_at"] is None
    assert st["provider"] == "agy"


def test_mark_running_then_idle_tracks_card_and_last_run(tmp_path, monkeypatch):
    store = AgentSessionStore(tmp_path)
    monkeypatch.setattr(store, "current_provider", lambda name: "agy")
    before = time.time()
    store.mark_running("arastirmaci", card_id="c-1", card_title="Kart bir",
                       provider="agy")
    st = store.status("arastirmaci")
    assert st["state"] == "running"
    assert st["card_id"] == "c-1" and st["card_title"] == "Kart bir"
    assert st["since"] is not None and st["since"] >= before
    # `last_run_at` BAŞTA da yazılır: koşu ortasında çöken uygulamada rozet
    # "hiç çalışmamış" göstermesin.
    assert st["last_run_at"] is not None and st["last_run_at"] >= before

    store.mark_idle("arastirmaci")
    st2 = store.status("arastirmaci")
    assert st2["state"] == "idle"
    assert st2["since"] is None
    assert st2["card_id"] == "" and st2["card_title"] == ""
    assert st2["last_run_at"] >= st["last_run_at"]


def test_status_uses_current_provider_and_lists_stale_sessions(tmp_path, monkeypatch):
    """Kullanıcının gördüğü hata: ajan agy iken rozet claude oturumu basıyordu."""
    store = AgentSessionStore(tmp_path)
    store.record("arastirmaci", "claude", session_id="old-claude",
                 signature="s1", model="claude-x")
    time.sleep(0.01)
    store.record("arastirmaci", "agy", conversation_id="fresh-agy",
                 signature="s2", model="gemini-3.8-flash-high")
    monkeypatch.setattr(store, "current_provider", lambda name: "agy")

    st = store.status("arastirmaci")
    assert st["provider"] == "agy"
    assert st["session"].get("conversation_id") == "fresh-agy"
    assert [s["provider"] for s in st["stale_sessions"]] == ["claude"]


def test_current_provider_prefers_agent_spec(tmp_path, monkeypatch):
    from entropy.agents import registry as _registry

    spec = _registry.AgentSpec(name="arastirmaci", provider="agy",
                              model="gemini-3.8-flash-high")

    class _Reg:
        def __init__(self, *a, **k):
            pass

        def get(self, name):
            return spec if name == "arastirmaci" else None

    monkeypatch.setattr(_registry, "AgentRegistry", _Reg)
    assert AgentSessionStore(tmp_path).current_provider("arastirmaci") == "agy"


def test_card_run_lifecycle_writes_then_clears_live_state(tmp_path):
    board = TaskBoard(vault_path=tmp_path)
    store = AgentSessionStore(tmp_path)
    card = board.create(TaskCard(id="", title="Canlı durum kartı",
                                 agent="arastirmaci", status="backlog"))
    board.apply_event(card.id, "task.assigned", actor="user",
                      payload={"agent": "arastirmaci"})
    board.apply_event(card.id, "task.claimed", actor="arastirmaci",
                      payload={"claimed": True, "claimed_by": "arastirmaci"})
    assert store.status("arastirmaci")["state"] == "running"  # taken de koşu sayılır
    board.apply_event(card.id, "run.started", actor="arastirmaci",
                      payload={"provider": "agy", "pid": 1})
    live = store.status("arastirmaci")
    assert live["state"] == "running" and live["card_id"] == card.id

    board.apply_event(card.id, "run.finished", actor="arastirmaci",
                      payload={"ok": True, "summary": "bitti", "proof": "yok",
                               "report_path": "r.md"})
    assert store.status("arastirmaci")["state"] == "idle"


def test_reconcile_clears_orphan_running_state(tmp_path):
    """Uygulama koşu ortasında çöktü: kart yok ama `state.json` 'running'."""
    from entropy.agents.dispatcher import BoardDispatcherCore

    board = TaskBoard(vault_path=tmp_path)
    store = AgentSessionStore(tmp_path)
    store.mark_running("arastirmaci", card_id="olmayan-kart",
                       card_title="Öksüz", provider="agy")
    assert store.status("arastirmaci")["state"] == "running"

    BoardDispatcherCore(board=board, vault_path=tmp_path).reconcile()
    assert store.status("arastirmaci")["state"] == "idle"


# ---------------------------------------------------------------------------
# B. Alt süreç konsol pencereleri
# ---------------------------------------------------------------------------

#: Kullanıcıya GÖRÜNMESİ istenen kabuk açıcıları — pencere gizlenmez.
_OPENER_TOKENS = ("explorer", "xdg-open", "open")

#: Henüz düzeltilmemiş çağrılar (`dosya:satır`). Bu küme BÜYÜYEMEZ: yeni bir
#: bayraksız çağrı testi kırar. Buradakiler paralel ajanların (Desk arayüzü)
#: kapsamındadır ve orada düzeltilecektir.
# Faz 13-A2 kapanışı: liste BOŞ. `desk/projects_panel.py` `git branch`
# çağrısı da `popen_kwargs()` alıyor; yeni bir istisna eklenirse
# `test_pending_list_does_not_rot` onu da kovalar.
PENDING_UNHIDDEN: set[str] = set()

_SPAWNERS = {"Popen", "run", "check_output", "check_call", "call"}


def _is_opener(node: ast.Call) -> bool:
    for arg in node.args[:1]:
        for token in ast.walk(arg):
            if isinstance(token, ast.Constant) and isinstance(token.value, str):
                head = token.value.strip().strip("/").split()[0] if token.value.strip() else ""
                if head in _OPENER_TOKENS:
                    return True
    return False


def _has_hidden_kwargs(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg is None:  # **popen_kwargs(...)
            call = kw.value
            if isinstance(call, ast.Call):
                fn = call.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name == "popen_kwargs":
                    return True
    return False


def _subprocess_calls():
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not isinstance(fn, ast.Attribute) or fn.attr not in _SPAWNERS:
                continue
            base = fn.value
            if not (isinstance(base, ast.Name) and base.id == "subprocess"):
                continue
            yield path, node


def test_every_subprocess_spawn_hides_the_console_window():
    offenders = []
    for path, node in _subprocess_calls():
        if _is_opener(node) or _has_hidden_kwargs(node):
            continue
        rel = path.relative_to(SRC).as_posix()
        offenders.append(f"{rel}:{node.lineno}")
    assert set(offenders) <= PENDING_UNHIDDEN, (
        "Konsol penceresi gizlemeyen alt süreç çağrıları: "
        + ", ".join(sorted(set(offenders) - PENDING_UNHIDDEN))
    )


def test_pending_list_does_not_rot():
    """Bekleyen liste düzeltilince testin kendisi de güncellensin."""
    if not PENDING_UNHIDDEN:
        return
    found = {f"{path.relative_to(SRC).as_posix()}:{node.lineno}"
             for path, node in _subprocess_calls()}
    assert PENDING_UNHIDDEN <= found, (
        "PENDING_UNHIDDEN içindeki satır artık yok; listeyi güncelle: "
        + ", ".join(sorted(PENDING_UNHIDDEN - found))
    )


def test_popen_kwargs_sets_both_flags_on_windows(monkeypatch):
    from entropy.platform import proc

    monkeypatch.setattr(proc, "IS_WINDOWS", True)
    monkeypatch.setattr(proc, "CREATE_NO_WINDOW", 0x08000000)
    kwargs = proc.popen_kwargs(timeout=5)
    assert kwargs["timeout"] == 5
    assert kwargs["creationflags"] & 0x08000000
    # `STARTUPINFO` bu platformda gerçekten kuruluyorsa alan dolu olmalı.
    if proc.hidden_startupinfo() is not None:
        assert kwargs.get("startupinfo") is not None


def test_popen_kwargs_is_noop_off_windows(monkeypatch):
    from entropy.platform import proc

    monkeypatch.setattr(proc, "IS_WINDOWS", False)
    assert proc.popen_kwargs(timeout=5) == {"timeout": 5}


def test_popen_kwargs_keeps_caller_flags(monkeypatch):
    from entropy.platform import proc

    monkeypatch.setattr(proc, "IS_WINDOWS", True)
    monkeypatch.setattr(proc, "CREATE_NO_WINDOW", 0x08000000)
    out = proc.popen_kwargs(creationflags=0x00000200)  # CREATE_NEW_PROCESS_GROUP
    assert out["creationflags"] & 0x00000200
    assert out["creationflags"] & 0x08000000


# ---------------------------------------------------------------------------
# C. Sessiz oturum devri
# ---------------------------------------------------------------------------

def test_session_rotation_is_a_quiet_status_line(tmp_path, monkeypatch):
    """Devir ne otonom görev kartı, ne çip, ne de rapor üretir."""
    from entropy.agents import session_budget
    from entropy.core.event_bus import bus

    notifications, lines = [], []
    bus.task_notification.connect(lambda *a: notifications.append(a))
    bus.terminal_output_received.connect(lambda s: lines.append(s))

    monkeypatch.setattr(session_budget, "_thresholds", lambda: (1, 0))
    monkeypatch.setattr(session_budget, "write_handoff",
                        lambda *a, **k: tmp_path / "handoff.md")
    monkeypatch.setattr(session_budget, "handoff_section", lambda *a, **k: "DEVİR")

    store = AgentSessionStore(tmp_path)
    store.record("arastirmaci", "agy", conversation_id="x", signature="s")
    store.note_run("arastirmaci", "agy", tokens=10)
    monkeypatch.setattr("entropy.core.identity.agent_session_store",
                        lambda vault_path=None: store)

    out = session_budget.rotate_if_needed("arastirmaci", "agy", vault_path=tmp_path)
    assert out == "DEVİR"
    assert notifications == [], f"otonom görev bildirimi düştü: {notifications}"
    assert any("oturumu tazelendi" in line for line in lines)
    assert not any("session:" in line for line in lines)


def test_rotation_does_not_write_a_task_to_the_ledger(tmp_path, monkeypatch):
    from entropy.agents import session_budget
    from entropy.core.task_ledger import task_ledger

    created = []
    for method in ("record_task_pending", "record_task_start"):
        monkeypatch.setattr(task_ledger, method,
                            lambda *a, _m=method, **k: created.append(_m))
    monkeypatch.setattr(session_budget, "_thresholds", lambda: (1, 0))
    monkeypatch.setattr(session_budget, "write_handoff", lambda *a, **k: None)
    monkeypatch.setattr(session_budget, "handoff_section", lambda *a, **k: "")

    store = AgentSessionStore(tmp_path)
    store.record("arastirmaci", "agy", conversation_id="x", signature="s")
    store.note_run("arastirmaci", "agy", tokens=10)
    monkeypatch.setattr("entropy.core.identity.agent_session_store",
                        lambda vault_path=None: store)

    session_budget.rotate_if_needed("arastirmaci", "agy", vault_path=tmp_path)
    assert created == []


# ---------------------------------------------------------------------------
# D. Arşivleme geçişi (QA artığı kartlar)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["review", "failed"])
def test_finished_card_can_be_archived_with_a_reason(status):
    card = {"id": "c", "status": status, "agent": "arastirmaci"}
    out = board_fsm.transition(card, "task.canceled",
                               {"reason": "QA artığı", "actor": "curator"})
    assert out["status"] == "canceled"


@pytest.mark.parametrize("status", ["review", "failed"])
def test_archiving_without_a_reason_is_rejected(status):
    card = {"id": "c", "status": status, "agent": "arastirmaci"}
    with pytest.raises(board_fsm.InvalidTransition):
        board_fsm.transition(card, "task.canceled", {"actor": "curator"})


def test_done_card_stays_terminal():
    with pytest.raises(board_fsm.InvalidTransition):
        board_fsm.transition({"id": "c", "status": "done"}, "task.canceled",
                             {"reason": "QA artığı"})


def test_archived_card_without_a_file_is_not_drift():
    view = {"cards": {"a": {"status": "canceled"}, "b": {"status": "review"}}}
    drift = board_events.board_drift([], view)
    assert [d["id"] for d in drift] == ["b"]
