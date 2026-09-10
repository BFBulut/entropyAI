"""
Faz 11 kapanışı — kartın `report_path` alanı ve ayar komutları.

Kapsam:
1. Köprü raporu kasaya yazdıktan SONRA geri çağrıyı çağırır ve rapor yolunu
   `report_path=` ile geçirir (gerçek `send_background_task_async` yolu, sahte
   `subprocess.Popen`).
2. `TaskBoard._finish` rapor yolunu karta, `run.finished` yüküne,
   `task_report_ready` sinyaline ve `TASKBOARD.md` projeksiyonuna işler.
3. `amplification.admit_report` kapıyı iki kez koşturmaz (`store_decision`).
4. `/lock on|off` ve `/board auto on|off` yerel komutları.

Gerçek model çağrısı YOK.
"""

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from entropy.agents.board_events import render_taskboard_text  # noqa: E402
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Entropy" / "Tasks").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


def make_card(board, **kw):
    card = TaskCard(
        id=kw.pop("id", new_task_id("test")),
        title=kw.pop("title", "Test kartı"),
        agent=kw.pop("agent", "arastirmaci"),
        goal=kw.pop("goal", "Bir şey yaz"),
        **kw,
    )
    return board.create(card)


def run_card(board, card_id, text, ok=True, report_path=""):
    board.apply_event(card_id, "task.assigned", payload={"agent": "arastirmaci"})
    board.apply_event(card_id, "task.claimed",
                      payload={"claimed": True, "claimed_by": "arastirmaci"})
    board.apply_event(card_id, "run.started", payload={"provider": "claude"})
    board._finish(card_id, text, ok, report_path=report_path)


# --------------------------------------------------------------------------
# 1. Gerçek köprü yolu (sahte Popen)
# --------------------------------------------------------------------------

class _DummyStdout:
    def __init__(self, lines):
        self._iter = iter(lines)

    def readline(self):
        return next(self._iter, "")

    def close(self):
        pass


def _dummy_proc_factory(lines, pid=4711):
    class DummyProc:
        def __init__(self, *args, **kwargs):
            self.stdout = _DummyStdout(lines)
            self.pid = pid

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    return DummyProc


def test_real_bridge_passes_saved_report_path_to_on_result(tmp_path, monkeypatch):
    """Köprü, kasaya yazdığı rapor yolunu geri çağrıya `report_path=` ile verir."""
    import entropy.brain.obsidian.vault_manager as vm_mod
    import entropy.brain.supabase.cognitive_memory as cm_mod
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))

    rapor = tmp_path / "Gorev_Test_20260910_1200.md"

    def fake_save(self, title, content, tags=None, project_name=None, skill_name=None):
        rapor.write_text(content, encoding="utf-8")
        return rapor

    monkeypatch.setattr(vm_mod.ObsidianVaultManager, "save_research_report", fake_save)
    monkeypatch.setattr(cm_mod.CognitiveMemorySystem, "store_node",
                        lambda self, **kw: (None, False))
    monkeypatch.setattr(bridge, "detect_skill_for_prompt", lambda prompt, sm=None: None)
    monkeypatch.setattr("subprocess.Popen", _dummy_proc_factory([
        '{"event": "result", "result": {"response": "bitti"}}\n',
        "",
    ]))

    done = threading.Event()
    got = {}

    def on_result(text, ok, report_path=""):
        got.update(text=text, ok=ok, report_path=report_path)
        done.set()

    bridge.send_background_task_async(
        task_id="rp-1",
        task_name="Rapor Yolu",
        prompt="kısa iş",
        mode="accept-edits",
        on_result=on_result,
        save_report=True,
    )
    assert done.wait(30), "geri çağrı çağrılmadı"
    assert got["ok"] is True
    # Rapor ÖNCE yazıldı: geri çağrı yolu gördü.
    assert got["report_path"] == str(rapor)


def test_bridge_keeps_two_argument_callbacks_working(tmp_path, monkeypatch):
    """Eski `(metin, başarı)` imzalı geri çağrılar bozulmaz."""
    import entropy.brain.obsidian.vault_manager as vm_mod
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    monkeypatch.setattr(vm_mod.ObsidianVaultManager, "save_research_report",
                        lambda self, *a, **k: tmp_path / "x.md")
    monkeypatch.setattr("subprocess.Popen", _dummy_proc_factory([
        '{"event": "result", "result": {"response": "tamam"}}\n',
        "",
    ]))

    done = threading.Event()
    got = {}

    def on_result(text, ok):
        got.update(text=text, ok=ok)
        done.set()

    bridge.send_background_task_async(
        task_id="rp-2", task_name="Eski imza", prompt="iş",
        on_result=on_result, save_report=True,
    )
    assert done.wait(30)
    assert got["ok"] is True


def test_call_on_result_only_feeds_named_report_path_parameter():
    """Üçüncü argüman kapanış hilesi olan geri çağrılar yanlış eşlenmez."""
    from entropy.core.provider import call_on_result

    seen = {}

    def closure_style(text, ok, _card_id="k1"):
        seen["card"] = _card_id

    call_on_result(closure_style, "x", True, "C:/rapor.md")
    assert seen["card"] == "k1"


# --------------------------------------------------------------------------
# 2. Kart alanı + projeksiyon
# --------------------------------------------------------------------------

def test_finish_records_report_path_on_card_and_signal(board, vault):
    from entropy.core.event_bus import bus

    seen = []
    bus.task_report_ready.connect(seen.append)
    try:
        card = make_card(board)
        rapor = str(vault / "Entropy" / "Skills" / "x" / "Reports" / "Gorev_x.md")
        run_card(board, card.id, "işi bitirdim", True, report_path=rapor)
    finally:
        bus.task_report_ready.disconnect(seen.append)

    saved = board.get(card.id)
    assert saved.report_path == rapor
    assert rapor in (saved.output_paths or [])
    assert seen and seen[-1]["report_path"] == rapor


def test_report_path_reaches_projection_and_taskboard(board, vault):
    from entropy.agents.board_events import board_event_log

    card = make_card(board)
    rapor = str(vault / "Entropy" / "Skills" / "x" / "Reports" / "Gorev_y.md")
    run_card(board, card.id, "bitti", True, report_path=rapor)

    view = board_event_log(vault).project()
    assert view["cards"][card.id]["report_path"] == rapor
    text = render_taskboard_text(list(view["cards"].values()))
    assert "[rapor](" in text and "Gorev_y.md" in text


def test_taskboard_line_has_no_link_without_report_path():
    text = render_taskboard_text([{"id": "k1", "title": "Kart", "status": "backlog"}])
    assert "[rapor](" not in text


def test_existing_report_path_is_not_overwritten(board, vault):
    card = make_card(board, report_path="C:/onceki.md")
    run_card(board, card.id, "bitti", True, report_path=str(vault / "yeni.md"))
    assert board.get(card.id).report_path == "C:/onceki.md"


# --------------------------------------------------------------------------
# 3. Kapı iki kez koşmaz
# --------------------------------------------------------------------------

class _FakeDecision:
    def __init__(self, content):
        self.action = "add"
        self.category = "semantic"
        self.content = content
        self.importance = 0.6
        self.provenance = "https://example.com/a"
        self.metadata = {}


class _FakeGate:
    def __init__(self):
        self.calls = 0

    def admit(self, category, content, metadata=None, provenance="", **kw):
        self.calls += 1
        return _FakeDecision(content)


class _FakeMemory:
    def __init__(self):
        self.decisions = []
        self.records = []

    def store_decision(self, decision, importance=None):
        self.decisions.append(decision)
        return (None, True)

    def record_memory(self, *a, **kw):
        self.records.append((a, kw))
        return (None, True)


def test_admit_report_writes_through_store_decision_only():
    from entropy.agents import amplification

    gate, memory = _FakeGate(), _FakeMemory()
    text = (
        "- Birinci bulgu uzun bir cümledir ve kaynağı https://example.com/a adresidir.\n"
        "- İkinci bulgu bambaşka bir konudur, kaynak: https://example.com/b sayfası.\n"
    )
    report = amplification.admit_report(text, gate=gate, memory=memory)

    assert report.add == gate.calls > 0
    # Kapı aday başına TEK kez koştu ve ikinci yazım `record_memory`e gitmedi.
    assert len(memory.decisions) == gate.calls
    assert memory.records == []
    # Yazılan tam olarak kapının kararıdır (gömme yeniden hesaplanmaz).
    assert all(isinstance(d, _FakeDecision) for d in memory.decisions)


def test_admit_report_falls_back_to_record_memory_without_store_decision():
    from entropy.agents import amplification

    class _Old(_FakeMemory):
        store_decision = None

    gate, memory = _FakeGate(), _Old()
    amplification.admit_report(
        "- Tek bir bulgu, kaynağı https://example.com/a adresidir.\n",
        gate=gate, memory=memory,
    )
    assert memory.records and memory.decisions == []


# --------------------------------------------------------------------------
# 4. Ayar komutları
# --------------------------------------------------------------------------

@pytest.fixture
def cfg(monkeypatch, tmp_path):
    from entropy.core.config import config as _cfg

    monkeypatch.setattr(type(_cfg), "save_settings", lambda self: None)
    monkeypatch.setattr(_cfg, "amplification_lock", True, raising=False)
    monkeypatch.setattr(_cfg, "board_auto_dispatch", True, raising=False)
    return _cfg


def test_lock_command_reports_and_toggles(cfg):
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/lock", None)
    assert "AÇIK" in out
    out = try_handle_local_command("/lock off", None)
    assert "KAPALI" in out and cfg.amplification_lock is False
    out = try_handle_local_command("/lock on", None)
    assert "AÇIK" in out and cfg.amplification_lock is True
    assert "Anlaşılmayan" in try_handle_local_command("/lock belki", None)


def test_board_auto_command_toggles_and_touches_dispatcher(cfg, monkeypatch):
    from entropy.core import slash_commands

    calls = []

    class _Dispatcher:
        def start(self):
            calls.append("start")
            return True

        def stop(self):
            calls.append("stop")

    monkeypatch.setattr("entropy.agents.dispatcher.board_dispatcher",
                        lambda: _Dispatcher())
    out = slash_commands.try_handle_local_command("/board auto off", None)
    assert "KAPALI" in out and cfg.board_auto_dispatch is False
    out = slash_commands.try_handle_local_command("/board auto on", None)
    assert "AÇIK" in out and cfg.board_auto_dispatch is True
    assert calls == ["stop", "start"]


def test_amplification_lock_off_skips_novelty_quota(board, monkeypatch, cfg):
    from entropy.agents import amplification

    monkeypatch.setattr(cfg, "amplification_lock", False, raising=False)
    called = []
    monkeypatch.setattr(amplification, "apply_report_lock",
                        lambda *a, **k: called.append(a))
    card = make_card(board, title="X konusunu araştır", goal="Kaynak topla")
    run_card(board, card.id, "https://example.com kaynaklı rapor", True)
    assert called == []
