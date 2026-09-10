"""
Faz 11-C — tetikleyici ve GERÇEK köprü yolu.

Sahte köprüyle geçen test yetmez: yeni köprü parametreleri (`effort`,
`session_id`) argv'ye ancak gerçek `send_background_task_async` → worker →
`build_command` zinciri koşarsa ulaşır. O zincir burada `subprocess.Popen`
taklidiyle sürülür; model çağrısı YAPILMAZ.
"""

import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from entropy.agents.dispatcher import BoardDispatcherCore, ClaimStore  # noqa: E402
from entropy.agents.registry import AgentRegistry, AgentSpec  # noqa: E402
from entropy.agents.tasks import TaskBoard, TaskCard  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Entropy" / "Tasks").mkdir(parents=True, exist_ok=True)
    return root


def seed(vault, name="yazar", provider="claude", effort="high"):
    AgentRegistry(vault_path=vault).create(
        AgentSpec(name=name, role="Yazar", provider=provider, effort=effort)
    )


# --------------------------------------------------------------------------
# Tetikleyici turu
# --------------------------------------------------------------------------

def test_dispatcher_starts_assigned_card_and_moves_it_to_running(vault):
    seed(vault)
    board = TaskBoard(vault_path=vault)
    card = board.create(TaskCard(id="c1", title="İş", agent="yazar", goal="hedef"))
    board.apply_event(card.id, "task.assigned", payload={"agent": "yazar"})

    seen = {}

    class FakeBridge:
        def send_background_task_async(self, **kwargs):
            seen.update(kwargs)

    core = BoardDispatcherCore(
        board=board, vault_path=vault,
        runner=lambda cid, spec: board.run(cid, bridge_factory=lambda _p=None: FakeBridge()),
    )
    started = core.tick()
    assert started == [card.id]
    assert board.get(card.id).status == "running"
    assert seen["task_id"] == "card-c1"
    # Ajanın eforu köprüye ULAŞTI (Faz 11-C.4).
    assert seen["effort"] == "high"


def test_dispatcher_skips_agents_with_no_assigned_card(vault):
    seed(vault)
    board = TaskBoard(vault_path=vault)
    board.create(TaskCard(id="c1", title="İş", agent="yazar", goal="h"))  # backlog
    core = BoardDispatcherCore(board=board, vault_path=vault,
                              runner=lambda cid, spec: "task")
    assert core.tick() == []
    assert board.get("c1").status == "backlog"


def test_busy_agent_is_not_given_a_second_card(vault):
    seed(vault)
    board = TaskBoard(vault_path=vault)
    for cid in ("c1", "c2"):
        board.create(TaskCard(id=cid, title=cid, agent="yazar", goal="h"))
        board.apply_event(cid, "task.assigned", payload={"agent": "yazar"})
    core = BoardDispatcherCore(board=board, vault_path=vault,
                              runner=lambda cid, spec: "task")
    assert core.tick() == ["c1"]
    assert core.tick() == []


def test_failed_start_releases_the_claim(vault):
    seed(vault)
    board = TaskBoard(vault_path=vault)
    board.create(TaskCard(id="c1", title="İş", agent="yazar", goal="h"))
    board.apply_event("c1", "task.assigned", payload={"agent": "yazar"})
    core = BoardDispatcherCore(board=board, vault_path=vault,
                              runner=lambda cid, spec: None)
    assert core.tick() == []
    assert not ClaimStore(vault).path_for("c1").exists()
    assert board.get("c1").status == "assigned"


# --------------------------------------------------------------------------
# Gerçek köprü yolu (Popen taklidi)
# --------------------------------------------------------------------------

class _Stdout:
    def __init__(self, lines):
        self._iter = iter(lines)

    def readline(self):
        return next(self._iter, "")

    def close(self):
        pass


def _fake_popen_factory(captured, lines):
    class DummyProc:
        def __init__(self, args, *a, **kw):
            captured.append(list(args))
            self.stdout = _Stdout(lines)
            self.stdin = None
            self.pid = 4242

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

        def kill(self):
            pass

    return DummyProc


def test_real_claude_bridge_argv_carries_effort_and_session_id(tmp_path, monkeypatch):
    from entropy.core.claude_bridge import ClaudeCodeBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = ClaudeCodeBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    captured = []
    monkeypatch.setattr("subprocess.Popen", _fake_popen_factory(captured, [
        json.dumps({"type": "result", "subtype": "success", "result": "tamam",
                    "session_id": "sess-42"}) + "\n",
        "",
    ]))

    done = threading.Event()
    bridge.send_background_task_async(
        task_id="real-effort-1",
        task_name="Efor Denemesi",
        prompt="kısa iş",
        on_result=lambda text, ok: done.set(),
        save_report=False,
        effort="low",
        session_id="11111111-2222-3333-4444-555555555555",
        agent="yazar",
    )
    assert done.wait(timeout=15), "on_result çağrılmadı"
    assert captured, "Popen hiç çağrılmadı"
    argv = captured[0]
    assert "--effort" in argv and argv[argv.index("--effort") + 1] == "low"
    assert "--session-id" in argv
    assert argv[argv.index("--session-id") + 1] == "11111111-2222-3333-4444-555555555555"
    assert "--bare" not in argv


def test_real_claude_bridge_resume_wins_over_session_id(tmp_path, monkeypatch):
    from entropy.core.claude_bridge import ClaudeCodeBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = ClaudeCodeBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    captured = []
    monkeypatch.setattr("subprocess.Popen", _fake_popen_factory(captured, [
        json.dumps({"type": "result", "subtype": "success", "result": "ok"}) + "\n",
        "",
    ]))
    done = threading.Event()
    bridge.send_background_task_async(
        task_id="real-effort-2",
        task_name="Sürdürme",
        prompt="kısa iş",
        on_result=lambda text, ok: done.set(),
        save_report=False,
        conversation_id="99999999-8888-7777-6666-555555555555",
        session_id="11111111-2222-3333-4444-555555555555",
    )
    assert done.wait(timeout=15)
    argv = captured[0]
    assert "--resume" in argv
    assert "--session-id" not in argv


def test_real_agy_bridge_effort_becomes_model_suffix(tmp_path, monkeypatch):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    captured = []
    monkeypatch.setattr("subprocess.Popen", _fake_popen_factory(captured, [
        json.dumps({"event": "result", "result": {"response": "tamam"}}) + "\n",
        "",
    ]))
    done = threading.Event()
    bridge.send_background_task_async(
        task_id="real-agy-1",
        task_name="Efor",
        prompt="kısa iş",
        on_result=lambda text, ok: done.set(),
        save_report=False,
        model="gemini-3.8-flash-low",
        effort="high",
    )
    assert done.wait(timeout=15)
    argv = captured[0]
    # agy'de efor AYRI BAYRAK DEĞİL: model adının son eki.
    assert "--effort" not in argv
    assert "--model" in argv
    assert argv[argv.index("--model") + 1].endswith("-high")


def test_real_bridge_records_agent_session_on_disk(tmp_path, monkeypatch):
    from entropy.core.claude_bridge import ClaudeCodeBridge
    from entropy.core.identity import agent_session_store
    from entropy.core.task_ledger import TaskLedger

    bridge = ClaudeCodeBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    captured = []
    monkeypatch.setattr("subprocess.Popen", _fake_popen_factory(captured, [
        json.dumps({"type": "result", "subtype": "success", "result": "ok",
                    "session_id": "captured-session"}) + "\n",
        "",
    ]))
    done = threading.Event()
    bridge.send_background_task_async(
        task_id="real-session-1",
        task_name="Oturum",
        prompt="kısa iş",
        on_result=lambda text, ok: done.set(),
        save_report=False,
        agent="yazar",
    )
    assert done.wait(timeout=15)
    entry = agent_session_store().get("yazar", "claude")
    assert entry.get("conversation_id") == "captured-session"
    assert entry.get("cwd")
