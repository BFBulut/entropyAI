"""
Faz 10-B: `bus.agent_stream` sözleşmesi ve kart yolu telemetrisi.

Neden bu testler: piksel ajan sahnesi arka planda koşan gizli terminallerin
avatarıdır ve TEK beslemesi `agent_stream`'dir. Kart yolunda eskiden yalnızca
`terminal_output_received` yayılıyordu (agy) ya da olaylar ajan etiketi
taşımıyordu (Claude); iki eksik de sahnede "hangi sprite konuşuyor" sorusunu
yanıtsız bırakıyordu. Testler sahte Popen akışlarıyla GERÇEK köprü yolunu
sürer — sahte köprüyle geçen bir test imza uyumsuzluğunu gizlerdi.
"""

import threading

import pytest
from PySide6.QtCore import Qt

from entropy.core.event_bus import bus
from entropy.core import provider as provider_mod


# ----------------------------------------------------------------------
# Sahte süreç yardımcıları
# ----------------------------------------------------------------------


class DummyStdout:
    def __init__(self, lines):
        self._iter = iter(lines)

    def readline(self):
        return next(self._iter, "")

    def close(self):
        pass


class DummyStdin:
    def __init__(self):
        self.written = []
        self.closed = False

    def write(self, payload):
        self.written.append(payload)

    def flush(self):
        pass

    def close(self):
        self.closed = True


def make_proc_class(lines, stdin=None):
    class DummyProc:
        instances = []

        def __init__(self, *args, **kwargs):
            self.stdout = DummyStdout(list(lines))
            self.stdin = stdin
            self.pid = 9911
            DummyProc.instances.append(self)

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    return DummyProc


@pytest.fixture
def stream_events():
    """`agent_stream` yükleri sırayla toplanır; test sonunda bağlantı çözülür."""
    events = []
    # DirectConnection: olaylar işçi iş parçacığından yayılıyor; kuyruklu
    # bağlantı Qt olay döngüsü olmadan hiç teslim edilmezdi.
    bus.agent_stream.connect(events.append, Qt.DirectConnection)
    try:
        yield events
    finally:
        bus.agent_stream.disconnect(events.append)


@pytest.fixture
def legacy_signals():
    """Geriye uyum: eski sinyaller de dinlenir, yayımları kesilmemeli."""
    chunks = []
    term = []
    bus.token_chunk_received.connect(chunks.append, Qt.DirectConnection)
    bus.terminal_output_received.connect(term.append, Qt.DirectConnection)
    try:
        yield {"chunks": chunks, "terminal": term}
    finally:
        bus.token_chunk_received.disconnect(chunks.append)
        bus.terminal_output_received.disconnect(term.append)


# ----------------------------------------------------------------------
# Sözleşme: yük kurulumu, kırpma, durum eşlemesi
# ----------------------------------------------------------------------


def test_payload_has_full_contract_keys():
    ev = provider_mod.build_agent_stream_event(
        "text", "merhaba", task_id="t1", card_id="c1", office="Studio",
        agent="planner", provider="agy", model="model-x",
    )
    for key in ("task_id", "card_id", "office", "agent", "provider", "model",
                "kind", "text", "tool", "state", "ts"):
        assert key in ev, f"sözleşme alanı eksik: {key}"
    assert ev["agent"] == "planner" and ev["office"] == "Studio"
    assert ev["state"] == "thinking"
    assert "full_text" not in ev, "kırpma yokken full_text taşınmamalı"


def test_bubble_text_is_trimmed_and_full_text_preserved():
    long_text = "x" * 900
    ev = provider_mod.build_agent_stream_event("text", long_text)
    assert len(ev["text"]) <= provider_mod.BUBBLE_TEXT_LIMIT
    assert ev["text"].endswith("…")
    assert ev["full_text"] == long_text


@pytest.mark.parametrize(
    "kind,tool,expected",
    [
        ("thinking", None, "thinking"),
        ("text", None, "thinking"),
        ("tool_call", "Edit", "working"),
        ("tool_call", "Write", "working"),
        ("tool_call", "Bash", "working"),
        ("tool_call", "MultiEdit", "working"),
        ("tool_call", "NotebookEdit", "working"),
        ("tool_call", "write_file", "working"),
        ("tool_call", "run_command", "working"),
        ("tool_call", "Read", "thinking"),
        ("tool_call", "Glob", "thinking"),
        ("tool_call", "Grep", "thinking"),
        ("tool_call", "WebFetch", "thinking"),
        ("tool_call", "WebSearch", "thinking"),
        ("result", None, "idle"),
        ("error", None, "error"),
    ],
)
def test_state_mapping(kind, tool, expected):
    assert provider_mod.stream_state_for(kind, tool) == expected


def test_emit_never_raises_on_bad_input():
    # Telemetri görevi düşürmemeli: bozuk girdi sessizce yutulur.
    assert provider_mod.emit_agent_stream("text", None) is not None


# ----------------------------------------------------------------------
# agy kart yolu
# ----------------------------------------------------------------------


AGY_LINES = [
    '{"event": "step_update", "step_update": {"step_type": "agent_thought", '
    '"thought": "Once dosyayi okuyayim."}}\n',
    '{"event": "step_update", "step_update": {"step_type": "tool", '
    '"tool_name": "Read", "state": "ACTIVE", "parameters": {"path": "a.py"}}}\n',
    '{"event": "step_update", "step_update": {"step_type": "tool", '
    '"tool_name": "Write", "state": "ACTIVE", "parameters": {"path": "a.py"}}}\n',
    '{"event": "step_update", "step_update": {"step_type": "tool", '
    '"tool_name": "Write", "state": "DONE", "output": "yazildi"}}\n',
    '{"event": "step_update", "step_update": {"text_delta": "Bitti raporu."}}\n',
    '{"event": "result", "result": {"response": "tamam"}}\n',
    "",
]


def _run_agy_card(tmp_path, monkeypatch, lines=AGY_LINES, stdin=None, **kwargs):
    import entropy.brain.obsidian.vault_manager as vm_mod
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr(
        "entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db")
    )
    monkeypatch.setattr(
        vm_mod.ObsidianVaultManager,
        "save_research_report",
        lambda self, *a, **k: (tmp_path / "x.md"),
    )
    proc_cls = make_proc_class(lines, stdin=stdin)
    monkeypatch.setattr("subprocess.Popen", proc_cls)

    done = threading.Event()
    got = {}

    def on_result(text, ok):
        got.update(text=text, ok=ok)
        done.set()

    bridge.send_background_task_async(
        task_id="card-1",
        task_name="Kart",
        prompt="bir sey yap",
        on_result=on_result,
        save_report=False,
        **kwargs,
    )
    assert done.wait(timeout=15), "on_result çağrılmadı"
    return bridge, got, proc_cls


def test_agy_card_emits_agent_stream_sequence(tmp_path, monkeypatch, stream_events):
    _run_agy_card(
        tmp_path, monkeypatch,
        stream_meta={"agent": "planner", "office": "Studio", "card_id": "c-9"},
    )
    kinds = [e["kind"] for e in stream_events]
    assert kinds[0] == "thinking"
    assert "tool_call" in kinds and "tool_result" in kinds
    assert kinds[-1] == "result"

    # Etiket her olayda taşınır: sahne sprite'ı buradan seçer.
    assert all(e["agent"] == "planner" for e in stream_events)
    assert all(e["office"] == "Studio" for e in stream_events)
    assert all(e["card_id"] == "c-9" for e in stream_events)
    assert all(e["task_id"] == "card-1" for e in stream_events)
    assert all(e["provider"] == "agy" for e in stream_events)

    tool_calls = [e for e in stream_events if e["kind"] == "tool_call"]
    states = {e["tool"]["name"]: e["state"] for e in tool_calls}
    assert states["Read"] == "thinking", "okuma aracı masaya oturtmamalı"
    assert states["Write"] == "working", "yazma aracı tuşlama olmalı"
    assert stream_events[-1]["state"] == "idle"


def test_agy_card_without_stream_meta_defaults_to_entropy(tmp_path, monkeypatch, stream_events):
    _run_agy_card(tmp_path, monkeypatch)
    assert stream_events, "meta yokken de akış yayılmalı"
    assert all(e["agent"] == "entropy" for e in stream_events)
    assert all(e["office"] == "" for e in stream_events)


def test_agy_card_still_emits_legacy_signals(tmp_path, monkeypatch, legacy_signals):
    # `token_chunk_received` kart yolunda BUGÜNE DEK hiç yayılmıyordu; artık
    # yayılıyor ve `terminal_output_received` de kesilmiyor.
    _, got, _ = _run_agy_card(tmp_path, monkeypatch)
    assert got["ok"] is True
    assert any("Bitti raporu." in c for c in legacy_signals["chunks"])
    assert any("Bitti raporu." in t for t in legacy_signals["terminal"])


def test_agy_card_error_maps_to_error_state(tmp_path, monkeypatch, stream_events):
    lines = [
        '{"event": "step_update", "step_update": {"step_type": "tool", '
        '"tool_name": "Bash", "state": "ERROR", "error": "izin yok"}}\n',
        '{"event": "result", "result": {"response": "olmadi"}}\n',
        "",
    ]
    _run_agy_card(tmp_path, monkeypatch, lines=lines)
    errors = [e for e in stream_events if e["kind"] == "error"]
    assert errors and errors[0]["state"] == "error"
    assert "izin yok" in errors[0]["text"]


# ----------------------------------------------------------------------
# Claude kart yolu
# ----------------------------------------------------------------------


CLAUDE_LINES = [
    '{"type": "system", "subtype": "init", "session_id": "s1", "model": "m", "tools": []}\n',
    '{"type": "assistant", "message": {"content": ['
    '{"type": "thinking", "thinking": "plan yapiyorum"}]}}\n',
    '{"type": "assistant", "message": {"content": ['
    '{"type": "tool_use", "name": "Grep", "input": {"pattern": "x"}}]}}\n',
    '{"type": "assistant", "message": {"content": ['
    '{"type": "tool_use", "name": "Edit", "input": {"file_path": "a.py"}}]}}\n',
    '{"type": "user", "message": {"content": ['
    '{"type": "tool_result", "name": "Edit", "content": "ok"}]}}\n',
    '{"type": "assistant", "message": {"content": ['
    '{"type": "text", "text": "Bitti."}]}}\n',
    '{"type": "result", "session_id": "s1", "result": "Bitti.", "total_cost_usd": 0}\n',
]


def test_claude_consume_stream_emits_labeled_events(stream_events):
    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    out = bridge.consume_stream(
        iter(CLAUDE_LINES),
        stream_meta={"agent": "coder", "office": "Studio", "card_id": "c-3"},
        task_id="card-7",
    )
    assert out["text"] == "Bitti."
    kinds = [e["kind"] for e in stream_events]
    assert kinds[0] == "status"
    assert "thinking" in kinds and "tool_call" in kinds and "tool_result" in kinds
    assert kinds[-1] == "result"
    assert all(e["agent"] == "coder" and e["office"] == "Studio" for e in stream_events)
    assert all(e["card_id"] == "c-3" and e["task_id"] == "card-7" for e in stream_events)
    assert all(e["provider"] == "claude" for e in stream_events)

    states = {
        e["tool"]["name"]: e["state"]
        for e in stream_events if e["kind"] == "tool_call"
    }
    assert states["Grep"] == "thinking"
    assert states["Edit"] == "working"
    assert stream_events[-1]["state"] == "idle"


def test_claude_chat_path_defaults_to_entropy_and_keeps_legacy(stream_events, legacy_signals):
    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    bridge.consume_stream(iter(CLAUDE_LINES))
    assert all(e["agent"] == "entropy" and e["office"] == "" for e in stream_events)
    assert any("Bitti." in c for c in legacy_signals["chunks"])
    assert any("Bitti." in t for t in legacy_signals["terminal"])


def test_claude_error_result_maps_to_error_state(stream_events):
    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    bridge.consume_stream(iter([
        '{"type": "result", "session_id": "s", "is_error": true, "result": "patladi"}\n',
    ]))
    assert stream_events[-1]["kind"] == "error"
    assert stream_events[-1]["state"] == "error"


# ----------------------------------------------------------------------
# Ajan başına terminal girdisi (10.2 altyapısı)
# ----------------------------------------------------------------------


def test_agy_send_followup_writes_ndjson_to_live_process():
    import json

    from entropy.core.agy_bridge import AgyProcessBridge

    bridge = AgyProcessBridge()
    stdin = DummyStdin()
    proc = type("P", (), {"stdin": stdin})()
    bridge._background_processes["live"] = proc

    assert bridge.send_followup("live", "devam et") is True
    payload = json.loads(stdin.written[0])
    assert payload["event"] == "user"
    assert payload["message"]["content"] == "devam et"


def test_claude_send_followup_writes_ndjson_to_live_process():
    import json

    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    stdin = DummyStdin()
    proc = type("P", (), {"stdin": stdin})()
    bridge._background_processes["live"] = proc

    assert bridge.send_followup("live", "devam et") is True
    payload = json.loads(stdin.written[0])
    assert payload["type"] == "user"
    assert payload["message"]["content"] == "devam et"


def test_send_followup_false_when_no_process_or_closed_stdin():
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.claude_bridge import ClaudeCodeBridge

    for bridge in (AgyProcessBridge(), ClaudeCodeBridge()):
        assert bridge.send_followup("yok", "merhaba") is False

        stdin = DummyStdin()
        stdin.closed = True
        bridge._background_processes["kapali"] = type("P", (), {"stdin": stdin})()
        assert bridge.send_followup("kapali", "merhaba") is False

        # stdin borusu hiç açılmamış süreç (DEVNULL) de False döner.
        bridge._background_processes["devnull"] = type("P", (), {"stdin": None})()
        assert bridge.send_followup("devnull", "merhaba") is False

        # Boş metin gönderilmez.
        bridge._background_processes["acik"] = type("P", (), {"stdin": DummyStdin()})()
        assert bridge.send_followup("acik", "   ") is False


# ----------------------------------------------------------------------
# Yeni bus sinyalleri (yalnızca tanım; yayım harness/bellek tarafında)
# ----------------------------------------------------------------------


def test_new_bus_signals_exist_and_carry_expected_payloads():
    seen = {}
    # Sozlesme: harness kural adaylarini yazinca (ofis adi, eklenen sayi)
    # yayar; tek argumanli eski imza panele sayiyi tasiyamiyordu.
    bus.rules_updated.connect(lambda o, n: seen.update(rules=(o, n)))
    bus.memory_error.connect(lambda d: seen.update(mem=d))
    bus.checkpoint_written.connect(lambda d: seen.update(cp=d))
    bus.proof_recorded.connect(lambda d: seen.update(proof=d))

    bus.rules_updated.emit("Studio", 2)
    bus.memory_error.emit({"where": "graph", "message": "bozuk", "ts": 1.0})
    bus.checkpoint_written.emit({"office": "Studio", "card_id": "c1", "path": "p"})
    bus.proof_recorded.emit({"office": "Studio", "card_id": "c1", "ok": True, "command": "pytest"})

    assert seen["rules"] == ("Studio", 2)
    assert seen["mem"]["where"] == "graph"
    assert seen["cp"]["card_id"] == "c1"
    assert seen["proof"]["ok"] is True
