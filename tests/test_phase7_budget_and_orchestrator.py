"""
FAZ 7 — bütçe koruması, terminal sözleşmesi, araç yasağı ve bilgi tazeleme.

Hiçbir test gerçek agy/claude süreci başlatmaz: `subprocess.Popen` taklit
edilir, kota harcanmaz.
"""

import json
import time
from dataclasses import replace

import pytest

from entropy.agents.desk_registry import DeskOffice as OfficeSpec, DeskRegistry
from entropy.agents.harness import (
    ORCHESTRATOR_NO_CODE_RETRY,
    SUBCARD_ESTIMATE_FLOOR,
    SUBCARD_TOKEN_ESTIMATE,
    OfficeHarness,
    orchestrator_produced_code,
)
from entropy.agents.registry import AgentSpec
from entropy.agents.tasks import MAX_STEPS_PER_CARD, TaskBoard, TaskCard, new_task_id
from entropy.core.task_ledger import TaskLedger, TaskStatus


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


def _office_card(board, title="Pazar araştırması", budget=0):
    return board.create(TaskCard(
        id=new_task_id(title), title=title, status="backlog", agent="orkestrator",
        provider="agy", goal="Pazarı araştır.", criteria=["Kaynak göster"],
        office="arastirma-ofisi", budget_tokens=budget,
    ))


def _plan_json(*titles, agent="arastirmaci", research_notes=None):
    payload = {
        "subtasks": [
            {"title": t, "goal": f"{t} hedefi", "criteria": [f"{t} ölçütü"],
             "agent": agent, "provider": "agy", "model": ""}
            for t in titles
        ]
    }
    if research_notes is not None:
        payload["research_notes"] = research_notes
    return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"


class _RecordingBridge:
    """Çağrıları kaydeden, sonucu senkron veren sahte köprü."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.terminated = []

    def send_background_task_async(self, task_id, task_name, prompt, mode="accept-edits",
                                   on_result=None, save_report=True, agent=None,
                                   needs_write=None, project_path=None, max_steps=None,
                                   **kw):
        self.calls.append({"task_id": task_id, "prompt": prompt, "agent": agent,
                           "max_steps": max_steps, "project_path": project_path})
        reply = self.replies.pop(0) if self.replies else ("", False)
        if on_result is not None:
            on_result(reply[0], reply[1])

    def terminate_background_task(self, task_id):
        self.terminated.append(task_id)


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


# ---------------------------------------------------------------------------
# A7a — başarısız/iptal görevlerde de usage yazılır
# ---------------------------------------------------------------------------


def test_failure_and_cancel_record_last_known_usage(tmp_path):
    led = TaskLedger(db_path=tmp_path / "l.db")
    led.record_task_start("a", "Yarıda ölen", str(tmp_path))
    led.record_task_failure("a", error="Çıkış kodu: -1",
                            usage={"input_tokens": 900, "output_tokens": 100,
                                   "total_tokens": 1000})
    rec = led.get_task("a")
    assert rec["status"] == TaskStatus.FAILED.value
    assert rec["total_tokens"] == 1000, "başarısız görevin maliyeti NULL kalmamalı"

    led.record_task_start("b", "İptal", str(tmp_path))
    led.record_task_cancelled("b", reason="kapandı", usage={"total_tokens": 42})
    assert led.get_task("b")["total_tokens"] == 42
    assert led.token_totals()["total_tokens"] == 1042


def test_failure_without_usage_leaves_columns_null(tmp_path):
    """usage bilinmiyorsa sütun uydurulmaz: NULL 'ölçülmedi' demektir."""
    led = TaskLedger(db_path=tmp_path / "l.db")
    led.record_task_start("a", "Kilit hatası", str(tmp_path))
    led.record_task_failure("a", error="kilit alınamadı")
    assert led.get_task("a")["total_tokens"] is None


def test_real_bridge_writes_usage_when_process_dies_before_result(tmp_path, monkeypatch):
    """
    GERÇEK köprü + Popen taklidi: agy `result` olayı yayınlamadan ölürse bile
    ara olaydaki son `usage` ledger'a yazılır.

    Regresyon: yalnızca `result` olayı usage taşıdığı için süreç yarıda ölünce
    `total_tokens` NULL kalıyor ve ofis harness'ı gerçek maliyeti göremiyordu.
    """
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import AgyProcessBridge

    led = TaskLedger(db_path=tmp_path / "l.db")
    monkeypatch.setattr(ab, "task_ledger", led)

    lines = [
        json.dumps({"event": "step_update", "step_update": {
            "text_delta": "kısmi çıktı",
            "usage": {"input_tokens": 5000, "output_tokens": 250, "total_tokens": 5250},
        }}) + "\n",
    ]
    proc = _FakeProc(lines, returncode=1)
    monkeypatch.setattr(ab.subprocess, "Popen", lambda cmd, **kw: proc)
    monkeypatch.setattr(AgyProcessBridge, "find_agy_executable", lambda self: "agy")

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = project

    done = []
    bridge.send_background_task_async(
        task_id="card-x", task_name="ölen görev", prompt="merhaba",
        project_path=str(project), on_result=lambda t, ok: done.append(ok),
        save_report=False, needs_write=False,
    )
    assert _wait_until(lambda: done)
    assert done == [False]
    rec = led.get_task("card-x")
    assert rec["status"] == TaskStatus.FAILED.value
    assert rec["total_tokens"] == 5250


class _FakeProc:
    """stream-json satırlarını akıtan sahte süreç."""

    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 999007
        self.stdin = None
        self.stdout = self
        self.killed = False

    def readline(self):
        return self._lines.pop(0) if self._lines else ""

    def close(self):
        pass

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


# ---------------------------------------------------------------------------
# A8 — toplu geçişler terminal olay yayar
# ---------------------------------------------------------------------------


def test_mark_orphans_failed_emits_terminal_events(tmp_path, monkeypatch, vault):
    from entropy.agents import mailbox

    emitted = []
    monkeypatch.setattr(
        mailbox, "emit_terminal",
        lambda task_id, sender, status, summary="", **kw: emitted.append((task_id, status)),
    )
    led = TaskLedger(db_path=tmp_path / "l.db")
    led.record_task_start("card-abc", "Alt kart", str(tmp_path))
    led.record_task_start("office-plan-ust", "Planlama", str(tmp_path))

    assert led.mark_orphans_failed() == 2
    # Kimlikler kart kimliğine indirgenmeli: kanban `card-` önekini bilmiyor.
    assert ("abc", "failed") in emitted
    assert ("ust", "failed") in emitted


def test_cancel_active_emits_canceled_terminal_events(tmp_path, monkeypatch):
    from entropy.agents import mailbox

    emitted = []
    monkeypatch.setattr(
        mailbox, "emit_terminal",
        lambda task_id, sender, status, summary="", **kw: emitted.append((task_id, status)),
    )
    led = TaskLedger(db_path=tmp_path / "l.db")
    led.record_task_start("card-zzz", "Alt kart", str(tmp_path))
    assert led.cancel_active() == 1
    assert emitted == [("zzz", "canceled")]


def test_terminal_event_reaches_office_mailbox(tmp_path, vault):
    """Guard'sız gerçek yol: olay posta kutusunda terminal olarak görünür."""
    from entropy.agents.mailbox import has_terminal_event
    from entropy.core.config import config

    config.obsidian_vault_path = vault
    led = TaskLedger(db_path=tmp_path / "l.db")
    led.record_task_start("card-gercek", "Alt kart", str(tmp_path))
    led.mark_orphans_failed()
    assert has_terminal_event("gercek", vault_path=vault)


# ---------------------------------------------------------------------------
# C2c — alt kart adım sayacı
# ---------------------------------------------------------------------------


def test_stream_tool_steps_over_limit_terminates_task(tmp_path, monkeypatch):
    """
    GERÇEK köprü + Popen taklidi: akışta `max_steps`ten fazla araç olayı
    gelirse süreç öldürülür ve görev `failed` biter.
    """
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import MAX_STEPS_MARKER, AgyProcessBridge

    led = TaskLedger(db_path=tmp_path / "l.db")
    monkeypatch.setattr(ab, "task_ledger", led)

    tool_line = json.dumps({"event": "step_update", "step_update": {
        "step_type": "tool", "tool_name": "Read", "state": "ACTIVE"}}) + "\n"
    result_line = json.dumps({"event": "result", "result": {
        "response": "buraya hiç gelinmemeli",
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}}) + "\n"
    proc = _FakeProc([tool_line] * 6 + [result_line], returncode=0)
    monkeypatch.setattr(ab.subprocess, "Popen", lambda cmd, **kw: proc)
    monkeypatch.setattr(AgyProcessBridge, "find_agy_executable", lambda self: "agy")

    killed = []
    monkeypatch.setattr(AgyProcessBridge, "terminate_background_task",
                        lambda self, task_id: killed.append(task_id))

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
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
    assert rec["status"] == TaskStatus.FAILED.value
    assert MAX_STEPS_MARKER in rec["error"]
    # `result` satırına hiç ulaşılmadı: sayaç akışı gerçekten kesti.
    assert "buraya hiç gelinmemeli" not in (results[0][0] or "")


def test_stream_without_max_steps_is_not_limited(tmp_path, monkeypatch):
    """`max_steps` verilmezse sayaç kapalıdır (etkileşimli görevler kesilmez)."""
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import AgyProcessBridge

    monkeypatch.setattr(ab, "task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    tool_line = json.dumps({"event": "step_update", "step_update": {
        "step_type": "tool", "tool_name": "Read", "state": "ACTIVE"}}) + "\n"
    result_line = json.dumps({"event": "result", "result": {
        "response": "bitti", "usage": {"total_tokens": 10}}}) + "\n"
    proc = _FakeProc([tool_line] * 50 + [result_line])
    monkeypatch.setattr(ab.subprocess, "Popen", lambda cmd, **kw: proc)
    monkeypatch.setattr(AgyProcessBridge, "find_agy_executable", lambda self: "agy")
    monkeypatch.setattr(AgyProcessBridge, "terminate_background_task",
                        lambda self, task_id: pytest.fail("sayaç kapalıyken öldürme olmamalı"))

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = project
    out = []
    bridge.send_background_task_async(
        task_id="t", task_name="serbest", prompt="merhaba", project_path=str(project),
        on_result=lambda t, ok: out.append((t, ok)), save_report=False, needs_write=False,
    )
    assert _wait_until(lambda: out)
    assert out[0][1] is True


def test_card_run_passes_max_steps_to_bridge(board, offices, seeded, vault):
    """Kart koşumu köprüye adım tavanını GEÇİRİR (yalnızca istemde rica değil)."""
    bridge = _RecordingBridge([("çıktı", True)])
    card = board.create(TaskCard(id=new_task_id("alt"), title="Alt iş", status="backlog",
                                 agent="arastirmaci", provider="agy", goal="oku"))
    board.run(card.id, bridge_factory=lambda p: bridge,
              agent_registry=offices.agents("arastirma-ofisi"))
    assert bridge.calls[0]["max_steps"] == MAX_STEPS_PER_CARD


# ---------------------------------------------------------------------------
# C2d — alt kart istemine proje dosya listesi
# ---------------------------------------------------------------------------


def test_subcard_prompt_carries_bounded_project_file_list(board, tmp_path):
    from entropy.agents.tasks import PROJECT_FILE_LIST_LIMIT

    project = tmp_path / "proje"
    (project / "src").mkdir(parents=True)
    (project / ".git").mkdir()
    (project / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (project / "__pycache__").mkdir()
    (project / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
    for i in range(60):
        (project / "src" / f"m{i:02d}.py").write_text("pass", encoding="utf-8")

    card = TaskCard(id="c1", title="Alt iş", goal="oku", criteria=["x"])
    prompt = board.build_prompt(card, project_path=str(project))
    assert "[PROJE DOSYALARI]" in prompt
    listed = [ln for ln in prompt.splitlines() if ln.startswith("- src/")]
    assert len(listed) == PROJECT_FILE_LIST_LIMIT == 40
    # Gürültü klasörleri listeye girmemeli.
    assert ".git" not in prompt and "__pycache__" not in prompt
    # Depo taraması yasağı istemde duruyor.
    assert "deponun tamamını tarama" in prompt


def test_subcard_prompt_without_project_has_no_file_section(board):
    card = TaskCard(id="c1", title="Alt iş", goal="oku")
    assert "[PROJE DOSYALARI]" not in board.build_prompt(card)


# ---------------------------------------------------------------------------
# C1b — çağrı ÖNCESİ bütçe kontrolü
# ---------------------------------------------------------------------------


def test_subcard_not_started_when_remaining_budget_below_estimate(board, offices, seeded):
    """
    Kalan bütçe bir alt kartı taşımıyorsa süreç HİÇ başlatılmaz.

    Regresyon: eski düzen "harca, sonra bak"tı; bütçe her seferinde bir alt
    kart boyu aşılıyordu.
    """
    bridge = _RecordingBridge([(_plan_json("Kaynak tara"), True)])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda p: bridge)
    # Tavan alt kart tahmininin (Faz 8'den beri uyarlanabilir; bu kart için
    # taban 8k) altında: plan yazılır ama alt kart başlamaz.
    card = _office_card(board, budget=SUBCARD_ESTIMATE_FLOOR // 2)
    assert harness.start(card.id)

    done = board.get(card.id)
    assert done.status == "failed"
    assert "Bütçe yetersiz" in (done.summary or "")
    # Yalnızca planlama çağrısı yapıldı; alt kart için köprüye gidilmedi.
    assert [c["task_id"] for c in bridge.calls] == [f"office-plan-{card.id}"]
    for child_id in done.children or []:
        assert board.get(child_id).status != "running"


def test_can_afford_tracks_remaining_budget(board, offices, seeded):
    """Kalan bütçe alt kart tahmininin üstündeyse çağrı serbesttir."""
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    card = _office_card(board, budget=SUBCARD_TOKEN_ESTIMATE * 3)
    assert harness._remaining_budget(card.id) == SUBCARD_TOKEN_ESTIMATE * 3
    assert harness._can_afford(card.id) is True
    # Harcama kalanı tahminin altına indirince kapı kapanır.
    harness._spend(card.id, SUBCARD_TOKEN_ESTIMATE * 2 + 1)
    assert harness._can_afford(card.id) is False


# ---------------------------------------------------------------------------
# A9 — orkestratörde araç yasağı yaptırımı
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "```python\nprint(1)\n```",
    "diff --git a/x.py b/x.py\n--- a/x.py",
    "Planı uyguladım ve dosyaya yazdım.",
    "Gerekli modülü oluşturdum, dosyayı güncelledim.",
])
def test_code_traces_are_detected(text):
    assert orchestrator_produced_code(text)


def test_json_plan_block_is_not_a_violation():
    """Plan JSON'u kod bloğu biçiminde isteniyor; ihlal sayılamaz."""
    assert not orchestrator_produced_code(_plan_json("Kaynak tara"))
    assert not orchestrator_produced_code("Plan hazır, alt görevleri yazdım.")


def test_orchestrator_code_output_is_rejected_once_then_retried(board, offices, seeded):
    violating = "İşte çözüm:\n```python\nprint('merhaba')\n```"
    bridge = _RecordingBridge([(violating, True), (_plan_json("Kaynak tara"), True)])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda p: bridge)
    card = _office_card(board)
    assert harness.start(card.id)

    # İki planlama çağrısı: ilki reddedildi, ikincisi uyarıyla yeniden istendi.
    plan_calls = [c for c in bridge.calls if c["task_id"] == f"office-plan-{card.id}"]
    assert len(plan_calls) == 1 + ORCHESTRATOR_NO_CODE_RETRY
    assert "[UYARI — ARAÇ YASAĞI]" in plan_calls[1]["prompt"]
    assert board.get(card.id).status != "failed"
    assert board.get(card.id).children


def test_second_orchestrator_violation_fails_the_card(board, offices, seeded):
    violating = "```python\nprint(1)\n```"
    bridge = _RecordingBridge([(violating, True), (violating, True)])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda p: bridge)
    card = _office_card(board)
    harness.start(card.id)

    done = board.get(card.id)
    assert done.status == "failed"
    assert "Orkestratör kod üretti" in (done.summary or "")


def test_no_code_rule_does_not_apply_to_subagents(board, offices, seeded):
    """Alt ajan kod üretebilir: yasak yalnızca orkestratöre aittir."""
    bridge = _RecordingBridge([
        (_plan_json("Kod yaz"), True),
        ("```python\nprint(1)\n```", True),   # alt kart çıktısı
        ('```json\n{"grades": [] }\n```', True),
    ])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda p: bridge)
    card = _office_card(board)
    harness.start(card.id)
    assert _wait_until(lambda: board.get(card.id).status in ("review", "failed"))
    assert board.get(card.id).status == "review"


# ---------------------------------------------------------------------------
# B1 — bilgi tazeleme ve araştırma notları
# ---------------------------------------------------------------------------


def test_plan_prompt_carries_memory_context_and_recent_reports(board, offices, seeded, monkeypatch):
    import entropy.memory.office_graph as og

    monkeypatch.setattr(
        og, "orchestrator_context",
        lambda office, task="", **kw: f"# Ofis Belleği ({office})\n- (bulgu) önceki tur: {task}\n",
    )
    reports = offices.reports_dir("arastirma-ofisi")
    reports.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        (reports / f"r{i}.md").write_text(f"# Rapor {i}\nÖnceki bulgu {i}.", encoding="utf-8")
        time.sleep(0.01)

    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    card = _office_card(board)
    prompt = harness.build_plan_prompt(offices.get("arastirma-ofisi"), board.get(card.id))

    assert "[BİLGİ TAZELEME]" in prompt
    assert "önceki tur: Pazarı araştır." in prompt
    assert "[SON RAPORLAR]" in prompt
    # Yalnızca son 3 rapor: bağlam bütçesi sınırlı.
    assert prompt.count("Önceki bulgu") == 3
    assert "Önceki bulgu 0." not in prompt


def test_plan_prompt_asks_for_research_notes_only_with_websearch_member(board, offices, seeded):
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    card = board.get(_office_card(board).id)
    # `arastirmaci` read-only → WebSearch var.
    prompt = harness.build_plan_prompt(offices.get("arastirma-ofisi"), card)
    assert "[ARAŞTIRMA NOTU]" in prompt and "research_notes" in prompt

    agents = offices.agents("arastirma-ofisi")
    agents.update(AgentSpec(name="arastirmaci", role="worker", description="araştırır",
                            provider="agy", tools_policy="read-write"))
    harness2 = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    prompt2 = harness2.build_plan_prompt(offices.get("arastirma-ofisi"), card)
    assert "[ARAŞTIRMA NOTU]" not in prompt2 and "research_notes" not in prompt2


def test_research_notes_become_office_graph_findings(board, offices, seeded, vault):
    from entropy.memory.office_graph import OfficeGraph

    notes = [{"title": "Rakip fiyatları düştü", "body": "Kaynak: sektör raporu."},
             "İkinci bulgu"]
    bridge = _RecordingBridge([(_plan_json("Kaynak tara", research_notes=notes), True),
                               ("alt kart çıktısı", True),
                               ('```json\n{"grades": []}\n```', True)])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda p: bridge)
    card = _office_card(board)
    harness.start(card.id)

    graph = OfficeGraph("arastirma-ofisi", vault)
    findings = [n for n in graph.nodes.values() if n.get("kind") == "bulgu"]
    titles = {n.get("title") for n in findings}
    assert "Rakip fiyatları düştü" in titles
    assert "İkinci bulgu" in titles


def test_plan_still_works_when_memory_layer_is_missing(board, offices, seeded, monkeypatch):
    """Bellek katmanı patlarsa planlama yine ilerler (guard sözleşmesi)."""
    import entropy.memory.office_graph as og

    def _boom(*a, **kw):
        raise RuntimeError("bellek yok")

    monkeypatch.setattr(og, "orchestrator_context", _boom)
    monkeypatch.setattr(og, "OfficeGraph", _boom)

    bridge = _RecordingBridge([(_plan_json("Kaynak tara", research_notes=["x"]), True),
                               ("alt çıktı", True),
                               ('```json\n{"grades": []}\n```', True)])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda p: bridge)
    card = _office_card(board)
    assert harness.start(card.id)
    assert board.get(card.id).children


# ---------------------------------------------------------------------------
# A10 — Claude sistem istemi argv sınırı
# ---------------------------------------------------------------------------


def test_long_system_prompt_uses_file_flag_not_inline_argv():
    from entropy.core.claude_bridge import (
        SYSTEM_PROMPT_ARGV_LIMIT,
        SYSTEM_PROMPT_FILE_FLAG,
        ClaudeCodeBridge,
    )

    bridge = ClaudeCodeBridge()
    long_prompt = "B" * (SYSTEM_PROMPT_ARGV_LIMIT + 1)
    cmd = bridge.build_command("merhaba", append_system_prompt=long_prompt)

    assert SYSTEM_PROMPT_FILE_FLAG in cmd, "4k üstü istem dosya bayrağıyla geçmeli"
    assert "--append-system-prompt" not in cmd
    path = cmd[cmd.index(SYSTEM_PROMPT_FILE_FLAG) + 1]
    assert long_prompt not in " ".join(cmd), "uzun istem argv'ye sızmamalı"
    from pathlib import Path as _P
    assert _P(path).read_text(encoding="utf-8") == long_prompt
    assert bridge.system_prompt_file_in(cmd) == path


def test_short_system_prompt_stays_inline():
    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    cmd = bridge.build_command("merhaba", append_system_prompt="kısa")
    assert "--append-system-prompt" in cmd
    assert cmd[cmd.index("--append-system-prompt") + 1] == "kısa"


# ---------------------------------------------------------------------------
# QA — ofis üyeliği tanım dosyasıyla doğar
# ---------------------------------------------------------------------------


def test_members_without_definition_warn_and_stay_out_of_roster(offices, caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="entropy.agents.desk_registry"):
        office = offices.create(OfficeSpec(name="yeni-ofis", purpose="test",
                                           members=["hayalet", "gölge"]))
    assert office.members == [], "tanımsız üye kadroya girmemeli"
    assert "hayalet" in caplog.text and "gölge" in caplog.text


def test_create_member_puts_agent_into_roster(offices):
    offices.create(OfficeSpec(name="yeni-ofis", purpose="test", members=["yazar"]))
    spec = offices.create_member("yeni-ofis", "yazar", description="rapor yazar")
    assert spec is not None and spec.office == "yeni-ofis"
    assert offices.agents("yeni-ofis").agent_file("yazar").is_file()
    assert offices.get("yeni-ofis").members == ["yazar"]

    # İkinci çağrı EZMEZ: kullanıcının elle düzelttiği istem korunur.
    again = offices.create_member("yeni-ofis", "yazar", description="başka")
    assert again.description == "rapor yazar"


def test_create_member_cannot_clone_the_orchestrator(offices):
    offices.create(OfficeSpec(name="yeni-ofis", purpose="test"))
    spec = offices.create_member("yeni-ofis", "ikinci-plan", role="orchestrator")
    assert spec.office_role == "worker"
    office = offices.get("yeni-ofis")
    assert office.orchestrator == "orkestrator"
    assert "ikinci-plan" in office.members


def test_desk_agent_add_uses_create_member(vault, monkeypatch):
    from entropy.core import slash_commands as sc

    DeskRegistry(vault_path=vault).create(OfficeSpec(name="yeni-ofis", purpose="test"))
    out = sc._handle_desk_admin(
        "agent", "add yeni-ofis yazar :: rapor yazar", DeskRegistry(vault_path=vault)
    )
    assert "kaydedildi" in out
    assert DeskRegistry(vault_path=vault).get("yeni-ofis").members == ["yazar"]
