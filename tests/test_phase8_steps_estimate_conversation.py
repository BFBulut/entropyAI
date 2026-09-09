"""
FAZ 8 — Claude adım tavanı, uyarlanabilir alt kart tahmini, ofis konuşması.

Hiçbir test gerçek agy/claude süreci başlatmaz: `subprocess.Popen` taklit
edilir, kota harcanmaz.
"""

import json
import time

import pytest

from entropy.agents.desk_registry import DeskOffice as OfficeSpec, DeskRegistry
from entropy.agents.harness import (
    OFFICE_STATE_KEY,
    SUBCARD_ESTIMATE_CEILING,
    SUBCARD_ESTIMATE_FLOOR,
    OfficeHarness,
    estimate_subcard_tokens,
)
from entropy.agents.registry import AgentSpec
from entropy.agents.tasks import MAX_STEPS_PER_CARD, TaskBoard, TaskCard, new_task_id
from entropy.core.task_ledger import TaskLedger


# ---------------------------------------------------------------------------
# Düzenek
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    return tmp_path / "Vault"


@pytest.fixture(autouse=True)
def clean_active_registry():
    OfficeHarness._active.clear()
    yield
    OfficeHarness._active.clear()


@pytest.fixture(autouse=True)
def isolated_conversation_map(tmp_path, monkeypatch):
    """Kimlik eşlemesi test dosyasına: kullanıcının gerçek eşlemesine dokunma."""
    from entropy.core import identity

    monkeypatch.setattr(identity.conversation_map, "path", tmp_path / "conv.json")
    return identity.conversation_map


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


@pytest.fixture
def offices(vault):
    return DeskRegistry(vault_path=vault)


@pytest.fixture
def seeded(offices):
    offices.create(OfficeSpec(
        name="arastirma-ofisi",
        purpose="Araştırır.",
        charter="Kabul standartları: kaynaklı yaz.",
        budget_tokens=1_000_000,
    ))
    agents = offices.agents("arastirma-ofisi")
    agents.update(AgentSpec(name="arastirmaci", role="worker", description="araştırır",
                            provider="agy", tools_policy="read-only"))
    agents.update(AgentSpec(name="degerlendirici", role="evaluator",
                            description="notlar", provider="agy", tools_policy="read-only"))
    return offices.get("arastirma-ofisi")


def _plan_json(*titles, agent="arastirmaci"):
    payload = {"subtasks": [
        {"title": t, "goal": f"{t} hedefi", "criteria": [f"{t} ölçütü"],
         "agent": agent, "provider": "agy", "model": ""} for t in titles]}
    return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"


def _office_card(board, title="Pazar araştırması", budget=0):
    return board.create(TaskCard(
        id=new_task_id(title), title=title, status="backlog", agent="orkestrator",
        provider="agy", goal="Pazarı araştır.", criteria=["Kaynak göster"],
        budget_tokens=budget,
    ))


class _RecordingBridge:
    """Çağrıları kaydeden, sonucu senkron veren sahte köprü."""

    def __init__(self, replies, conversation_ids=None):
        self.replies = list(replies)
        self.conversation_ids = dict(conversation_ids or {})
        self.calls = []
        self.terminated = []

    def send_background_task_async(self, task_id, task_name, prompt, mode="accept-edits",
                                   on_result=None, save_report=True, agent=None,
                                   needs_write=None, project_path=None, max_steps=None,
                                   conversation_id=None, **kw):
        self.calls.append({"task_id": task_id, "prompt": prompt, "agent": agent,
                           "max_steps": max_steps, "conversation_id": conversation_id})
        reply = self.replies.pop(0) if self.replies else ("", False)
        if on_result is not None:
            on_result(reply[0], reply[1])

    def background_conversation_id(self, task_id):
        return self.conversation_ids.get(task_id)

    def terminate_background_task(self, task_id):
        self.terminated.append(task_id)


class _FakeProc:
    """stream-json satırlarını akıtan sahte süreç."""

    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 999008
        self.stdin = None
        self.stdout = self

    def readline(self):
        return self._lines.pop(0) if self._lines else ""

    def close(self):
        pass

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


def _wait_until(predicate, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(0.03)
    return False


def _assistant_tool_line(name="Read"):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": name, "input": {"path": "a.txt"}}]}}) + "\n"


def _result_line(text="bitti", session_id="sess-1"):
    return json.dumps({"type": "result", "session_id": session_id, "result": text,
                       "usage": {"input_tokens": 5, "output_tokens": 5}}) + "\n"


# ---------------------------------------------------------------------------
# 1 — Claude'da adım tavanı
# ---------------------------------------------------------------------------


def test_claude_stream_tool_steps_over_limit_terminates_task(tmp_path, monkeypatch):
    """
    GERÇEK köprü + Popen taklidi: `max_steps`ten fazla `tool_use` bloğu gelirse
    süreç öldürülür ve görev `[ADIM SINIRI]` ile `failed` biter.
    """
    import entropy.core.claude_bridge as cb
    from entropy.core.claude_bridge import MAX_STEPS_MARKER, ClaudeCodeBridge

    led = TaskLedger(db_path=tmp_path / "l.db")
    monkeypatch.setattr(cb, "task_ledger", led)

    lines = [_assistant_tool_line()] * 6 + [_result_line("buraya hiç gelinmemeli")]
    proc = _FakeProc(lines, returncode=0)
    monkeypatch.setattr(cb.subprocess, "Popen", lambda cmd, **kw: proc)
    monkeypatch.setattr(ClaudeCodeBridge, "find_claude_executable", lambda self: "claude")

    killed = []
    monkeypatch.setattr(ClaudeCodeBridge, "terminate_background_task",
                        lambda self, task_id: killed.append(task_id))

    project = tmp_path / "proje"
    project.mkdir()
    bridge = ClaudeCodeBridge()
    bridge.active_project_dir = project

    results = []
    bridge.send_background_task_async(
        task_id="card-adim", task_name="çok adımlı", prompt="merhaba",
        project_path=str(project), on_result=lambda t, ok: results.append((t, ok)),
        save_report=False, needs_write=False, max_steps=3,
    )
    assert _wait_until(lambda: results)
    assert results[0][1] is False
    assert killed == ["card-adim"]
    rec = led.get_task("card-adim")
    assert rec["status"] == "FAILED"
    assert MAX_STEPS_MARKER in rec["error"]
    # `result` satırına hiç ulaşılmadı: sayaç akışı gerçekten kesti.
    assert "buraya hiç gelinmemeli" not in (results[0][0] or "")


def test_claude_stream_without_max_steps_is_not_limited(tmp_path, monkeypatch):
    import entropy.core.claude_bridge as cb
    from entropy.core.claude_bridge import ClaudeCodeBridge

    monkeypatch.setattr(cb, "task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    proc = _FakeProc([_assistant_tool_line()] * 50 + [_result_line("bitti")])
    monkeypatch.setattr(cb.subprocess, "Popen", lambda cmd, **kw: proc)
    monkeypatch.setattr(ClaudeCodeBridge, "find_claude_executable", lambda self: "claude")
    monkeypatch.setattr(ClaudeCodeBridge, "terminate_background_task",
                        lambda self, task_id: pytest.fail("sayaç kapalıyken öldürme olmamalı"))

    project = tmp_path / "proje"
    project.mkdir()
    bridge = ClaudeCodeBridge()
    bridge.active_project_dir = project
    out = []
    bridge.send_background_task_async(
        task_id="t", task_name="serbest", prompt="merhaba", project_path=str(project),
        on_result=lambda t, ok: out.append((t, ok)), save_report=False, needs_write=False,
    )
    assert _wait_until(lambda: out)
    assert out[0][1] is True


def test_claude_argv_carries_max_turns_only_when_cli_supports_it(monkeypatch):
    """
    `claude --help` çıktısında `--max-turns` YOK (yalnızca `--max-budget-usd`).
    Var olmayan bayrak argv'ye konursa süreç ilk saniyede düşerdi; bu yüzden
    bayrak yalnızca yetenek anahtarı açıkken eklenir.
    """
    import entropy.core.claude_bridge as cb
    from entropy.core.claude_bridge import ClaudeCodeBridge

    monkeypatch.setattr(ClaudeCodeBridge, "find_claude_executable", lambda self: "claude")
    bridge = ClaudeCodeBridge()

    assert cb.CLAUDE_SUPPORTS_MAX_TURNS is False
    cmd = bridge.build_command("merhaba", max_steps=7)
    assert "--max-turns" not in cmd

    monkeypatch.setattr(cb, "CLAUDE_SUPPORTS_MAX_TURNS", True)
    cmd = bridge.build_command("merhaba", max_steps=7)
    assert cmd[cmd.index("--max-turns") + 1] == "7"


def test_card_run_passes_max_steps_to_claude_bridge(board, offices, seeded):
    """`TaskBoard.run` adım tavanını Claude köprüsüne de geçirir."""
    bridge = _RecordingBridge([("çıktı", True)])
    card = board.create(TaskCard(id=new_task_id("alt"), title="Alt iş", status="backlog",
                                 agent="arastirmaci", provider="claude", goal="oku"))
    board.run(card.id, bridge_factory=lambda p: bridge,
              agent_registry=offices.agents("arastirma-ofisi"))
    assert bridge.calls[0]["max_steps"] == MAX_STEPS_PER_CARD


def test_claude_bridge_signature_accepts_max_steps():
    """Sözleşme denetimi: `_accepts_kwarg` guard'ı bayrağı düşürmemeli."""
    from entropy.agents.tasks import _accepts_kwarg
    from entropy.core.claude_bridge import ClaudeCodeBridge

    assert _accepts_kwarg(ClaudeCodeBridge.send_background_task_async, "max_steps")
    assert _accepts_kwarg(ClaudeCodeBridge.send_background_task_async, "conversation_id")


# ---------------------------------------------------------------------------
# 2 — uyarlanabilir alt kart tahmini
# ---------------------------------------------------------------------------


def test_estimate_without_history_uses_prompt_length(board):
    """Medyan yokken istem karakteri konuşur; taban ve tavan sınırları geçerli."""
    tiny = estimate_subcard_tokens(prompt_chars=10, office="yok", board=board)
    assert tiny["tokens"] == SUBCARD_ESTIMATE_FLOOR
    assert tiny["source"] == "taban"

    mid = estimate_subcard_tokens(prompt_chars=20_000, office="yok", board=board)
    assert mid["tokens"] == 15_000  # 20000/4*3
    assert mid["source"] == "istem"

    huge = estimate_subcard_tokens(prompt_chars=500_000, office="yok", board=board)
    assert huge["tokens"] == SUBCARD_ESTIMATE_CEILING


def test_estimate_uses_office_median_when_available(board, tmp_path, seeded):
    """Ofisin başarılı alt kart medyanı (×1.2) istem tahmininden büyükse baskındır."""
    led = TaskLedger(db_path=tmp_path / "l.db")
    parent = _office_card(board)
    for idx, cost in enumerate((20_000, 25_000, 30_000)):
        child = board.create(TaskCard(
            id=new_task_id(f"alt{idx}"), title=f"alt{idx}", status="done",
            agent="arastirmaci", provider="agy", office="arastirma-ofisi",
            parent=parent.id, goal="oku"))
        led.record_task_start(f"card-{child.id}", child.title, str(tmp_path))
        led.record_task_success(f"card-{child.id}", summary="ok",
                                usage={"total_tokens": cost})

    est = estimate_subcard_tokens(prompt_chars=100, office="arastirma-ofisi",
                                  board=board, ledger=led)
    assert est["source"] == "medyan"
    assert est["tokens"] == int(25_000 * 1.2)


def test_estimate_ignores_other_offices_and_failures(board, tmp_path, seeded):
    """Başka ofisin ve başarısız kartların maliyeti medyana girmez."""
    led = TaskLedger(db_path=tmp_path / "l.db")
    parent = _office_card(board)
    fail = board.create(TaskCard(id=new_task_id("bad"), title="bad", status="failed",
                                 agent="arastirmaci", provider="agy",
                                 office="arastirma-ofisi", parent=parent.id, goal="x"))
    other = board.create(TaskCard(id=new_task_id("other"), title="other", status="done",
                                  agent="arastirmaci", provider="agy",
                                  office="baska-ofis", parent="p", goal="x"))
    for card, cost in ((fail, 39_000), (other, 39_000)):
        led.record_task_start(f"card-{card.id}", card.title, str(tmp_path))
    led.record_task_failure(f"card-{fail.id}", error="x",
                            usage={"total_tokens": 39_000})
    led.record_task_success(f"card-{other.id}", summary="ok",
                            usage={"total_tokens": 39_000})

    est = estimate_subcard_tokens(prompt_chars=100, office="arastirma-ofisi",
                                  board=board, ledger=led)
    assert est["source"] == "taban"
    assert est["tokens"] == SUBCARD_ESTIMATE_FLOOR


def test_subcard_estimate_is_written_to_card_file(board, offices, seeded):
    """Tahmin ve kaynağı alt kartın kendi dosyasına düşer."""
    bridge = _RecordingBridge([
        (_plan_json("Kaynak tara"), True),
        ("alt çıktı", True),
        ('```json\n{"grades": []}\n```', True),
    ])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda p: bridge)
    card = _office_card(board)
    harness.start(card.id)
    assert _wait_until(lambda: board.get(card.id).children)
    child = board.get(board.get(card.id).children[0])
    assert "Tahmin:" in (child.notes or "")
    assert "kaynak:" in (child.notes or "")


def test_zero_office_budget_means_unlimited(offices):
    """`budget_tokens: 0` varsayılana DÜŞMEZ; sınırsız demektir."""
    offices.create(OfficeSpec(name="sinirsiz-ofis", purpose="p", budget_tokens=0))
    assert offices.get("sinirsiz-ofis").budget_tokens == 0

    harness = OfficeHarness("sinirsiz-ofis", board=TaskBoard(vault_path=offices.vault_path),
                            offices=offices)
    assert harness._budget("yok-boyle-kart") == 0
    assert harness._remaining_budget("yok-boyle-kart") is None
    assert harness._can_afford("yok-boyle-kart", SUBCARD_ESTIMATE_CEILING) is True


def test_invalid_budget_falls_back_to_default(offices):
    from entropy.agents.desk_registry import DEFAULT_BUDGET_TOKENS

    assert DeskRegistry._int("abc", DEFAULT_BUDGET_TOKENS, allow_zero=True) == DEFAULT_BUDGET_TOKENS
    assert DeskRegistry._int("-5", DEFAULT_BUDGET_TOKENS, allow_zero=True) == DEFAULT_BUDGET_TOKENS
    assert DeskRegistry._int("0", DEFAULT_BUDGET_TOKENS, allow_zero=True) == 0
    # allow_zero olmayan alanlar (max_parallel) eski davranışı korur.
    assert DeskRegistry._int("0", 3) == 3


# ---------------------------------------------------------------------------
# 3 — ofis konuşmasının sürdürülmesi
# ---------------------------------------------------------------------------


def test_second_office_call_resumes_the_conversation(board, offices, seeded):
    """Plan → değerlendirme aynı konuşmada sürer; alt kart sürdürmez."""
    plan_task = None
    bridge = _RecordingBridge([
        (_plan_json("Kaynak tara"), True),
        ("alt çıktı", True),
        ('```json\n{"grades": []}\n```', True),
    ])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda p: bridge)
    card = _office_card(board)
    bridge.conversation_ids[f"office-plan-{card.id}"] = "konusma-42"
    harness.start(card.id)
    assert _wait_until(lambda: board.get(card.id).status in ("review", "failed"))

    calls = {c["task_id"]: c for c in bridge.calls}
    # İlk planlama kimliksiz başlar (ofisin ilk turu).
    assert calls[f"office-plan-{card.id}"]["conversation_id"] is None
    # Değerlendirme AYNI konuşmayı sürdürür.
    assert calls[f"office-eval-{card.id}"]["conversation_id"] == "konusma-42"
    # Alt kart TEMİZ bağlamla koşar.
    child_id = board.get(card.id).children[0]
    assert calls[f"card-{child_id}"]["conversation_id"] is None
    assert plan_task is None


def test_office_conversation_is_persisted_and_keyed_by_office(board, offices, seeded,
                                                              isolated_conversation_map):
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    harness.remember_office_conversation("agy", "konusma-7")

    state = json.loads((offices.office_dir("arastirma-ofisi") / "state.json").read_text(encoding="utf-8"))
    assert state[OFFICE_STATE_KEY]["conversation_id"]["agy"] == "konusma-7"
    assert harness.office_conversation_id("agy") == "konusma-7"
    assert harness.office_conversation_id("claude") is None

    # ConversationMap'te `office:` önekiyle durur; sohbet kimlikleriyle çakışmaz.
    assert isolated_conversation_map.get("office:arastirma-ofisi", "agy") == "konusma-7"
    assert isolated_conversation_map.get("arastirma-ofisi", "agy") is None
    assert isolated_conversation_map.resume_flag("office:arastirma-ofisi", "agy") == \
        ["--conversation", "konusma-7"]


def test_deleting_office_drops_the_conversation(board, offices, seeded,
                                                isolated_conversation_map):
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    harness.remember_office_conversation("agy", "konusma-9")
    assert offices.delete("arastirma-ofisi") is True
    assert isolated_conversation_map.get("office:arastirma-ofisi", "agy") is None


def test_agy_background_task_records_conversation_id(tmp_path, monkeypatch):
    """GERÇEK agy köprüsü: akıştaki konuşma kimliği görev sonrası okunabilir."""
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import AgyProcessBridge

    monkeypatch.setattr(ab, "task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    result_line = json.dumps({"event": "result", "conversation_id": "konusma-abc",
                              "result": {"response": "bitti",
                                         "usage": {"total_tokens": 10}}}) + "\n"
    proc = _FakeProc([result_line])
    monkeypatch.setattr(ab.subprocess, "Popen", lambda cmd, **kw: proc)
    monkeypatch.setattr(AgyProcessBridge, "find_agy_executable", lambda self: "agy")

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = project
    out = []
    bridge.send_background_task_async(
        task_id="office-plan-x", task_name="plan", prompt="merhaba",
        project_path=str(project), on_result=lambda t, ok: out.append((t, ok)),
        save_report=False, needs_write=False,
    )
    assert _wait_until(lambda: out)
    assert bridge.background_conversation_id("office-plan-x") == "konusma-abc"


def test_agy_argv_carries_conversation_flag(tmp_path, monkeypatch):
    """Sürdürülen çağrının argv'sinde `--conversation <id>` vardır."""
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import AgyProcessBridge

    monkeypatch.setattr(ab, "task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    seen = {}

    def _popen(cmd, **kw):
        seen["cmd"] = list(cmd)
        return _FakeProc([json.dumps({"event": "result", "result": {"response": "ok"}}) + "\n"])

    monkeypatch.setattr(ab.subprocess, "Popen", _popen)
    monkeypatch.setattr(AgyProcessBridge, "find_agy_executable", lambda self: "agy")

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = project
    out = []
    bridge.send_background_task_async(
        task_id="office-eval-x", task_name="değerlendirme", prompt="merhaba",
        project_path=str(project), on_result=lambda t, ok: out.append(ok),
        save_report=False, needs_write=False, conversation_id="konusma-abc",
    )
    assert _wait_until(lambda: out)
    cmd = seen["cmd"]
    assert cmd[cmd.index("--conversation") + 1] == "konusma-abc"


def test_claude_argv_carries_resume_flag_for_office_call(tmp_path, monkeypatch):
    """Claude tarafında aynı anlam `--resume <session-id>` ile taşınır."""
    import entropy.core.claude_bridge as cb
    from entropy.core.claude_bridge import ClaudeCodeBridge

    monkeypatch.setattr(cb, "task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    seen = {}

    def _popen(cmd, **kw):
        seen["cmd"] = list(cmd)
        return _FakeProc([_result_line("ok", session_id="sess-77")])

    monkeypatch.setattr(cb.subprocess, "Popen", _popen)
    monkeypatch.setattr(ClaudeCodeBridge, "find_claude_executable", lambda self: "claude")

    project = tmp_path / "proje"
    project.mkdir()
    bridge = ClaudeCodeBridge()
    bridge.active_project_dir = project
    out = []
    bridge.send_background_task_async(
        task_id="office-eval-y", task_name="değerlendirme", prompt="merhaba",
        project_path=str(project), on_result=lambda t, ok: out.append(ok),
        save_report=False, needs_write=False, conversation_id="sess-42",
    )
    assert _wait_until(lambda: out)
    cmd = seen["cmd"]
    assert cmd[cmd.index("--resume") + 1] == "sess-42"
    # Yeni oturum kimliği de saklanır (sonraki tur onu sürdürür).
    assert bridge.background_conversation_id("office-eval-y") == "sess-77"


def test_resumed_agy_usage_is_charged_as_delta(tmp_path, monkeypatch):
    """
    Sürdürülen konuşmada agy'nin KÜMÜLATİF usage'ı iki kez düşülmez.

    İkinci tur 30k kümülatif bildiriyorsa ve ilk tur 20k'ydı, bu turun maliyeti
    10k'dır; taban çıkarılmazsa ofis bütçesi yanlışlıkla erken tükenirdi.
    """
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import AgyProcessBridge

    led = TaskLedger(db_path=tmp_path / "l.db")
    monkeypatch.setattr(ab, "task_ledger", led)

    def _line(total, conv="konusma-k"):
        return json.dumps({"event": "result", "conversation_id": conv, "result": {
            "response": "ok", "usage": {"input_tokens": total, "output_tokens": 0,
                                        "total_tokens": total}}}) + "\n"

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = project
    monkeypatch.setattr(AgyProcessBridge, "find_agy_executable", lambda self: "agy")

    monkeypatch.setattr(ab.subprocess, "Popen", lambda cmd, **kw: _FakeProc([_line(20_000)]))
    out = []
    bridge.send_background_task_async(task_id="office-plan-z", task_name="plan",
                                      prompt="p", project_path=str(project),
                                      on_result=lambda t, ok: out.append(ok),
                                      save_report=False, needs_write=False)
    assert _wait_until(lambda: out)
    assert led.get_task("office-plan-z")["total_tokens"] == 20_000

    monkeypatch.setattr(ab.subprocess, "Popen", lambda cmd, **kw: _FakeProc([_line(30_000)]))
    out2 = []
    bridge.send_background_task_async(task_id="office-eval-z", task_name="değerlendirme",
                                      prompt="p", project_path=str(project),
                                      on_result=lambda t, ok: out2.append(ok),
                                      save_report=False, needs_write=False,
                                      conversation_id="konusma-k")
    assert _wait_until(lambda: out2)
    assert led.get_task("office-eval-z")["total_tokens"] == 10_000
