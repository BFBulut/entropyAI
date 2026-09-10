"""
Faz 10-C: etkileşimli kart kipi (gerçek "terminal girdisi").

Neden bu testler: 10-B'de `send_followup` eklendi ama kart süreçlerinin stdin'i
ya DEVNULL'du ya da istem yazılınca kapanıyordu; takip mesajı pratikte hiçbir
zaman ajana ulaşmıyordu. Buradaki testler SAHTE KÖPRÜ KULLANMAZ: gerçek
`send_background_task_async` yolunu sahte `subprocess.Popen` ile uçtan uca
sürer, çünkü bu fazın tamamı köprünün süreç/akış yönetimindedir.

Sahte süreç, gerçek CLI'ın davranışını taklit eder: stdin'e bir kullanıcı
olayı yazıldığında SIRADAKİ turun satırlarını stdout kuyruğuna basar, stdin
kapanınca akış EOF'a düşer.
"""

import json
import queue
import threading

import pytest
from PySide6.QtCore import Qt

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.core.task_ledger import TaskLedger, TaskStatus


# ----------------------------------------------------------------------
# Sahte süreç: turlar stdin'e yazıldıkça açılır
# ----------------------------------------------------------------------


class FakeStdout:
    def __init__(self, q):
        self._q = q
        self.closed = False

    def readline(self):
        try:
            item = self._q.get(timeout=5.0)
        except queue.Empty:
            return ""
        return "" if item is None else item

    def close(self):
        self.closed = True


class FakeStdin:
    def __init__(self, proc):
        self._proc = proc
        self.written = []
        self.closed = False

    def write(self, payload):
        if self.closed:
            raise ValueError("stdin kapalı")
        self.written.append(payload)
        self._proc.feed_next_turn()

    def flush(self):
        pass

    def close(self):
        if self.closed:
            return
        self.closed = True
        self._proc.finish()


class FakeProc:
    """turns: her turda stdout'a düşecek satır listesi (0. tur ilk istemin yanıtı)."""

    instances = []

    turns = []

    def __init__(self, *args, **kwargs):
        self.args = args[0] if args else kwargs.get("args")
        self.kwargs = kwargs
        self.pid = 4321
        self._q = queue.Queue()
        self._turns = [list(t) for t in type(self).turns]
        self._turn_index = 0
        self.stdout = FakeStdout(self._q)
        self.stdin = FakeStdin(self) if kwargs.get("stdin") is not None else None
        self.terminated = False
        self._done = threading.Event()
        type(self).instances.append(self)

    # -- CLI taklidi --
    def feed_next_turn(self):
        if self._turn_index >= len(self._turns):
            return
        for line in self._turns[self._turn_index]:
            self._q.put(line)
        self._turn_index += 1

    def finish(self):
        self._done.set()
        self._q.put(None)

    # -- Popen yüzeyi --
    def poll(self):
        return 0 if self._done.is_set() else None

    def wait(self, timeout=None):
        self._done.wait(timeout if timeout is not None else 5.0)
        return 0

    def terminate(self):
        self.terminated = True
        self.finish()

    def kill(self):
        self.terminate()


AGY_TURN_1 = [
    '{"event": "step_update", "step_update": {"text_delta": "birinci tur"}}\n',
    '{"event": "result", "result": {"response": "birinci tur", '
    '"usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}}}\n',
]
AGY_TURN_2 = [
    '{"event": "step_update", "step_update": {"text_delta": "ikinci tur"}}\n',
    '{"event": "result", "result": {"response": "ikinci tur", '
    '"usage": {"input_tokens": 160, "output_tokens": 45, "total_tokens": 205}}}\n',
]

CLAUDE_TURN_1 = [
    json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "birinci tur"}]},
    }) + "\n",
    json.dumps({
        "type": "result",
        "session_id": "sess-1",
        "result": "birinci tur",
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }) + "\n",
]
CLAUDE_TURN_2 = [
    json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "ikinci tur"}]},
    }) + "\n",
    json.dumps({
        "type": "result",
        "session_id": "sess-1",
        "result": "ikinci tur",
        "usage": {"input_tokens": 60, "output_tokens": 15},
    }) + "\n",
]


# ----------------------------------------------------------------------
# Ortak kurulum
# ----------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_process_kill(monkeypatch):
    """taskkill/terminate gerçek bir PID'e gitmesin (sahte süreçlerin pid'i uydurma)."""
    monkeypatch.setattr("subprocess.run", lambda *a, **k: None)


@pytest.fixture
def stream_events():
    seen = []
    # DirectConnection: olaylar işçi iş parçacığından yayılıyor; kuyruklu
    # bağlantı olay döngüsü olmadığı için hiç teslim edilmezdi.
    bus.agent_stream.connect(seen.append, Qt.DirectConnection)
    try:
        yield seen
    finally:
        bus.agent_stream.disconnect(seen.append)


@pytest.fixture
def followups():
    seen = []
    bus.task_followup_completed.connect(seen.append, Qt.DirectConnection)
    try:
        yield seen
    finally:
        bus.task_followup_completed.disconnect(seen.append)


def _make_bridge(kind, tmp_path, monkeypatch, turns):
    """Gerçek köprü + sahte Popen; rapor yazımı kasaya değil belleğe gider."""
    import entropy.memory.obsidian.vault_manager as vm_mod

    if kind == "agy":
        from entropy.core.agy_bridge import AgyProcessBridge as Bridge

        module = "entropy.core.agy_bridge"
    else:
        from entropy.core.claude_bridge import ClaudeCodeBridge as Bridge

        module = "entropy.core.claude_bridge"

    bridge = Bridge()
    bridge.set_project_directory(tmp_path)
    ledger = TaskLedger(db_path=tmp_path / f"ledger_{kind}.db")
    monkeypatch.setattr(f"{module}.task_ledger", ledger)
    monkeypatch.setattr(
        vm_mod.ObsidianVaultManager,
        "save_research_report",
        lambda self, *a, **k: tmp_path / "rapor.md",
    )

    FakeProc.instances = []
    FakeProc.turns = turns
    monkeypatch.setattr("subprocess.Popen", FakeProc)
    return bridge, ledger


def _proc_of(bridge, task_id="kart-1"):
    """
    Bu köprünün KENDİ etkileşimli sürecini döndürür.

    Neden: `FakeProc.instances[0]` sınıf düzeyinde birikiyordu ve tam paket
    koşusunda başka bir test dosyasından artakalan bir arka plan iş parçacığı
    yamalı `subprocess.Popen`'i bu test sırasında çağırdığında listenin ilk
    öğesi YABANCI bir süreç oluyordu (agy varyantı bu yüzden yalnızca tam
    koşuda düşüyordu). Oturum defterinden okumak deterministik.
    """
    session = bridge._interactive_sessions.get(task_id)
    proc = getattr(session, "proc", None) if session is not None else None
    return proc if proc is not None else FakeProc.instances[0]


def _start(bridge, task_id="kart-1", **kwargs):
    done = threading.Event()
    got = {}

    def on_result(text, ok):
        got.update(text=text, ok=ok)
        done.set()

    bridge.send_background_task_async(
        task_id=task_id,
        task_name="Etkilesimli Kart",
        prompt="ilk istem",
        on_result=on_result,
        save_report=False,
        needs_write=True,
        interactive=True,
        stream_meta={"agent": "kasif", "office": "ofis", "card_id": "c1"},
        **kwargs,
    )
    assert done.wait(timeout=10), "kart ilk turda finalize edilmedi"
    return got


def _idle_events(events, task_id="kart-1"):
    return [
        e for e in events
        if e["task_id"] == task_id and e["state"] == "idle" and e["kind"] == "status"
        and "bekliyor" in e["text"]
    ]


# ----------------------------------------------------------------------
# (a) İlk sonuç: kart finalize, süreç canlı
# ----------------------------------------------------------------------


@pytest.mark.parametrize("kind,turns", [
    ("agy", [AGY_TURN_1, AGY_TURN_2]),
    ("claude", [CLAUDE_TURN_1, CLAUDE_TURN_2]),
])
def test_first_result_finalizes_card_but_keeps_process_alive(
    kind, turns, tmp_path, monkeypatch, stream_events
):
    bridge, ledger = _make_bridge(kind, tmp_path, monkeypatch, turns)
    got = _start(bridge)

    assert got["ok"] is True
    assert "birinci tur" in got["text"]
    # Kart defterde başarıyla kapandı ama terminal canlı.
    assert ledger.get_task("kart-1")["status"] == TaskStatus.SUCCESS.value
    proc = _proc_of(bridge)
    assert proc.poll() is None, "etkileşimli kipte süreç ilk sonuçta ölmemeli"
    assert proc.stdin is not None and not proc.stdin.closed

    # Sahne "boşta / takip mesajı bekliyor" durumunu görmeli.
    for _ in range(50):
        if _idle_events(stream_events):
            break
        threading.Event().wait(0.05)
    assert _idle_events(stream_events), "boşta (takip bekleniyor) olayı yayılmadı"
    assert "kart-1" in bridge.interactive_task_ids()

    bridge.close_interactive("kart-1")


# ----------------------------------------------------------------------
# (b) Takip mesajı → yeni tur → result + task_followup_completed
# ----------------------------------------------------------------------


@pytest.mark.parametrize("kind,turns", [
    ("agy", [AGY_TURN_1, AGY_TURN_2]),
    ("claude", [CLAUDE_TURN_1, CLAUDE_TURN_2]),
])
def test_followup_starts_new_turn_and_emits_signal(
    kind, turns, tmp_path, monkeypatch, stream_events, followups
):
    bridge, ledger = _make_bridge(kind, tmp_path, monkeypatch, turns)
    _start(bridge)

    assert bridge.send_followup("kart-1", "ikinci soru") is True

    for _ in range(100):
        if followups:
            break
        threading.Event().wait(0.05)
    assert followups, "task_followup_completed yayılmadı"
    payload = followups[0]
    assert payload["task_id"] == "kart-1"
    assert payload["card_id"] == "c1"
    assert payload["success"] is True
    assert "ikinci tur" in payload["text"]
    assert payload["usage"].get("total_tokens", 0) > 0

    # Takip mesajı gerçekten sürecin stdin'ine NDJSON olarak yazıldı.
    proc = _proc_of(bridge)
    last = json.loads(proc.stdin.written[-1])
    assert last.get("event") == "user" or last.get("type") == "user"
    assert last["message"]["content"] == "ikinci soru"

    # Ledger: yeni sütun yok, AYNI satırın toplamı arttı.
    # agy'de usage kümülatif (120 -> 205), taban çıkarıldığı için tur maliyeti
    # 85 ve satır toplamı 205 olmalı; Claude'da usage tur başına (120 + 75).
    row = ledger.get_task("kart-1")
    assert row["total_tokens"] == (205 if kind == "agy" else 195)

    # Yeni tur sahnede yeniden çalışır/düşünür durumuna döndü.
    assert any(
        e["task_id"] == "kart-1" and e["state"] in ("working", "thinking")
        for e in stream_events
    )
    bridge.close_interactive("kart-1")


@pytest.mark.parametrize("kind", ["agy", "claude"])
def test_followup_rejects_empty_and_overlong_text(kind, tmp_path, monkeypatch, stream_events):
    turns = [AGY_TURN_1, AGY_TURN_2] if kind == "agy" else [CLAUDE_TURN_1, CLAUDE_TURN_2]
    bridge, _ = _make_bridge(kind, tmp_path, monkeypatch, turns)
    _start(bridge)

    assert bridge.send_followup("kart-1", "   ") is False
    assert bridge.send_followup("kart-1", "x" * 4001) is False
    assert any(e["kind"] == "error" for e in stream_events)
    # Reddedilen mesaj sürece HİÇ yazılmadı (ilk istem dışında yazım yok).
    assert len(_proc_of(bridge).stdin.written) == 1

    bridge.close_interactive("kart-1")
    assert bridge.send_followup("kart-1", "artık kapalı") is False


# ----------------------------------------------------------------------
# (c) Boşta zaman aşımı
# ----------------------------------------------------------------------


@pytest.mark.parametrize("kind,turns", [
    ("agy", [AGY_TURN_1]),
    ("claude", [CLAUDE_TURN_1]),
])
def test_idle_timeout_closes_terminal(kind, turns, tmp_path, monkeypatch, stream_events):
    monkeypatch.setattr(config, "desk_interactive_idle_timeout_s", 0.3, raising=False)
    bridge, _ = _make_bridge(kind, tmp_path, monkeypatch, turns)
    _start(bridge)

    proc = _proc_of(bridge)
    for _ in range(100):
        if proc.poll() is not None:
            break
        threading.Event().wait(0.05)
    assert proc.poll() is not None, "boşta zaman aşımı süreci kapatmadı"
    assert proc.stdin.closed
    assert "kart-1" not in bridge.interactive_task_ids()
    assert bridge.send_followup("kart-1", "geç kaldım") is False


# ----------------------------------------------------------------------
# (d) close_interactive ve shutdown
# ----------------------------------------------------------------------


@pytest.mark.parametrize("kind,turns", [
    ("agy", [AGY_TURN_1]),
    ("claude", [CLAUDE_TURN_1]),
])
def test_close_interactive_and_shutdown_close_terminals(kind, turns, tmp_path, monkeypatch):
    bridge, _ = _make_bridge(kind, tmp_path, monkeypatch, turns)
    _start(bridge)
    proc = _proc_of(bridge)

    assert bridge.close_interactive("kart-1") is True
    assert proc.stdin.closed
    assert bridge.close_interactive("kart-1") is False
    assert bridge.interactive_task_ids() == []

    # Aynı köprüde ikinci bir kart açıp kapanışı sürelim.
    bridge2, _ = _make_bridge(kind, tmp_path, monkeypatch, turns)
    _start(bridge2, task_id="kart-2")
    proc2 = _proc_of(bridge2, "kart-2")
    assert proc2.poll() is None
    bridge2.shutdown(timeout=3.0)
    assert proc2.stdin.closed, "kapanışta etkileşimli terminal kapatılmalı"
    assert bridge2.interactive_task_ids() == []


# ----------------------------------------------------------------------
# (e) Kilit kancaları
# ----------------------------------------------------------------------


@pytest.mark.parametrize("kind,turns", [
    ("agy", [AGY_TURN_1, AGY_TURN_2]),
    ("claude", [CLAUDE_TURN_1, CLAUDE_TURN_2]),
])
def test_followup_lock_hooks_are_called(kind, turns, tmp_path, monkeypatch, followups):
    """
    Bekleyen terminal proje kilidini TUTMAZ; takip turunda kilit kancalar üzerinden
    geri alınır. Kilit API'si harness tarafında olduğu için köprü yalnızca kanca sunar.
    """
    from entropy.core.project_lock import project_lock_manager

    bridge, _ = _make_bridge(kind, tmp_path, monkeypatch, turns)
    calls = []
    _start(
        bridge,
        on_followup_start=lambda tid: calls.append(("start", tid)),
        on_followup_end=lambda tid: calls.append(("end", tid)),
    )

    # İlk sonuçtan sonra kilit serbest: aynı projeyi başkası yazma için alabilmeli.
    assert project_lock_manager.acquire_write(tmp_path, timeout=2.0) is True
    project_lock_manager.release_write(tmp_path)

    assert bridge.send_followup("kart-1", "devam") is True
    for _ in range(100):
        if followups:
            break
        threading.Event().wait(0.05)
    assert ("start", "kart-1") in calls
    for _ in range(60):
        if ("end", "kart-1") in calls:
            break
        threading.Event().wait(0.05)
    assert ("end", "kart-1") in calls
    bridge.close_interactive("kart-1")


@pytest.mark.parametrize("kind,turns", [
    ("agy", [AGY_TURN_1, AGY_TURN_2]),
    ("claude", [CLAUDE_TURN_1, CLAUDE_TURN_2]),
])
def test_followup_refused_when_lock_hook_returns_false(kind, turns, tmp_path, monkeypatch):
    bridge, _ = _make_bridge(kind, tmp_path, monkeypatch, turns)
    _start(bridge, on_followup_start=lambda tid: False)
    assert bridge.send_followup("kart-1", "devam") is False
    assert len(_proc_of(bridge).stdin.written) == 1
    bridge.close_interactive("kart-1")


# ----------------------------------------------------------------------
# (f) Kip kapalıyken eski davranış
# ----------------------------------------------------------------------


@pytest.mark.parametrize("kind,turns", [
    ("agy", [AGY_TURN_1]),
    ("claude", [CLAUDE_TURN_1]),
])
def test_disabled_flag_restores_legacy_behaviour(kind, turns, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "desk_interactive_cards", False, raising=False)
    bridge, ledger = _make_bridge(kind, tmp_path, monkeypatch, turns)

    # Kip kapalı: istem kısa olduğu için stdin borusu hiç açılmaz; akışı
    # EOF'a düşürmek için sahte süreç turu doğrudan yayınlar.
    proc_holder = {}

    class LegacyProc(FakeProc):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            proc_holder["proc"] = self
            self.feed_next_turn()
            self.finish()

    LegacyProc.instances = FakeProc.instances
    LegacyProc.turns = turns
    monkeypatch.setattr("subprocess.Popen", LegacyProc)

    got = _start(bridge)
    assert got["ok"] is True
    proc = proc_holder["proc"]
    assert proc.poll() is not None, "kip kapalıyken süreç ilk sonuçta bitmeli"
    assert bridge.interactive_task_ids() == []
    assert bridge.send_followup("kart-1", "devam") is False
    assert ledger.get_task("kart-1")["status"] == TaskStatus.SUCCESS.value
