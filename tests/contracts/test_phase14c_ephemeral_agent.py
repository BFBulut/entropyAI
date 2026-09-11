"""
Faz 14-C sözleşme testleri — geçici (kendini silen) ajan döngüsü.

Ölçülen şey, kullanıcının bağlayıcı tanımının her adımı (ARCHITECTURE §6.4):
`agent.md` üretimi → ayrı oturum → canlı akış → rapor → hafıza (ALT AJAN
yazar) → kendini silme. Köprü yolu SAHTE KÖPRÜYLE değil, gerçek
`send_background_task_async` ile ölçülür (yalnız `subprocess.Popen` taklit
edilir): 13-A dersi, sahte köprüyle geçen testin argv'yi hiç görmemesiydi.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from entropy.agents import ephemeral
from entropy.core.claude_bridge import ClaudeCodeBridge


# ---------------------------------------------------------------------------
# Ortam
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 424242
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


REPORT_TEXT = (
    "# canivopets.com sıfırdan araştırma\n\n"
    "## Özet\n- Site evcil hayvan ürünleri satıyor.\n\n"
    "## Kaynaklar\n- https://canivopets.com\n\n"
    "[HAFIZA]\n"
    '{"items": [{"category": "semantic", "content": "canivopets.com evcil '
    'hayvan ürünleri satan bir e-ticaret sitesidir ve kargoyu 48 saatte '
    'yapar.", "importance": 0.6, "provenance": "https://canivopets.com"}]}\n'
    "[/HAFIZA]\n"
)


def _stream_lines(text=REPORT_TEXT, steps=2, is_error=False):
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s-14c",
                    "model": "claude-opus-5", "tools": []}) + "\n",
    ]
    for i in range(steps):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "id": f"t{i}",
                                     "name": "WebSearch",
                                     "input": {"query": "canivopets"}}]},
        }) + "\n")
    lines.append(json.dumps({
        "type": "result", "subtype": "success", "result": text,
        "session_id": "s-14c", "is_error": is_error,
        "permission_denials": [],
        "usage": {"input_tokens": 120, "output_tokens": 40},
    }) + "\n")
    return lines


class _FakeVault:
    """Kasa taklidi: raporu gerçekten diske yazar (yol iddia edilebilsin)."""

    def __init__(self, root: Path):
        self.vault_path = root
        self.saved = []

    def save_research_report(self, name, content, tags=None, skill_name=None,
                             project_name=None):
        target = Path(self.vault_path) / "Entropy" / "Reports" / f"{name}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.saved.append(target)
        return target


@pytest.fixture()
def env(tmp_path, monkeypatch):
    module = sys.modules["entropy.core.config"]
    cfg = module.config
    monkeypatch.setenv("ENTROPY_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(cfg, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    monkeypatch.setattr(cfg, "claude_isolated", True, raising=False)
    monkeypatch.setattr(cfg, "approvals_enabled", True, raising=False)
    monkeypatch.setattr(type(cfg), "save_settings", lambda self: None)
    (tmp_path / "Vault").mkdir(parents=True, exist_ok=True)
    return cfg


@pytest.fixture()
def run_env(env, tmp_path, monkeypatch):
    """Gerçek köprü + taklit süreç + taklit kasa + hafıza kancası kaydı."""
    captured = {"cmds": [], "memory": []}

    def fake_popen(cmd, **kw):
        captured["cmds"].append(list(cmd))
        captured["kw"] = kw
        return _FakeProc(captured.get("lines") or _stream_lines())

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)

    import entropy.brain.agent_memory_writer as amw

    def fake_ingest(memory, text, report_path="", success=True, has_proof=True):
        captured["memory"].append({"text": text, "report_path": report_path,
                                   "success": success, "has_proof": has_proof})
        return amw.WriteResult(written=["n-1"])

    monkeypatch.setattr(ephemeral, "_default_vault",
                        lambda: _FakeVault(tmp_path / "Vault"))
    monkeypatch.setattr("entropy.brain.agent_memory_writer.ingest_agent_report",
                        fake_ingest)
    return captured


def _make_run(tmp_path, captured, **kwargs):
    bridge = ClaudeCodeBridge()
    bridge.active_project_dir = tmp_path
    run = ephemeral.EphemeralRun(
        skill=None,
        goal="canivopets.com'u sıfırdan araştır",
        bridge=bridge,
        brain_context="Beyinde bu işe ait kayıt yok.",
        engine={"provider": "claude", "model": "claude-opus-5", "effort": "low"},
        vault=_FakeVault(tmp_path / "Vault"),
        **kwargs,
    )
    return run


# ---------------------------------------------------------------------------
# 1. agent.md üretimi (prepare) — saf Python, süreç açmaz
# ---------------------------------------------------------------------------


def test_agent_md_carries_the_seven_contract_sections(env):
    spec = ephemeral.prepare(
        skill=None, prompt="canivopets.com'u araştır",
        brain_context="Kayıt yok.", engine={"model": "claude-opus-5"},
    )
    md = spec.agent_md
    for heading in ("## Görev", "## Bağlam (beyinden)", "## Kabul ölçütleri",
                    "## Rapor şablonu", "## Hafıza", "## Yasaklar"):
        assert heading in md, heading
    assert md.splitlines()[0] == f"# {spec.slug}"
    # Rapor şablonunun İLK satırı H1 olmalı (§6.3 başlık sözleşmesi).
    tpl = md.split("## Rapor şablonu", 1)[1]
    first = [ln for ln in tpl.splitlines() if ln.strip() and not ln.startswith("```")][0]
    assert first.startswith("# "), first
    # Hafıza sözleşmesi ve yasaklar metinde AÇIK.
    assert "[HAFIZA]" in md and "[/HAFIZA]" in md
    assert "en çok 8 madde" in md.lower()
    assert "kaynak zorunlu" in md.lower()
    assert "kod değişikliği yok" in md.lower()
    assert "salt okunur" in md.lower()
    assert "araştırmanın yerine geçmez" in md.lower()


def test_max_steps_comes_from_skill_frontmatter_not_the_card_ceiling(env, tmp_path):
    from entropy.agents.tasks import MAX_STEPS_PER_CARD

    skill_file = tmp_path / "skill" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("---\nname: arastirma\nmax_steps: 120\n---\n# gövde\n",
                          encoding="utf-8")

    class _Skill:
        name = "arastirma"
        description = "test"
        instructions = "yordam"
        path = str(skill_file)

    spec = ephemeral.prepare(skill=_Skill(), prompt="iş", brain_context="-")
    assert spec.max_steps == 120
    # Ön bilgi yoksa kart tavanı DEĞİL, yeteneğe uygun tavan geçerli.
    plain = ephemeral.prepare(skill=None, prompt="iş", brain_context="-")
    assert plain.max_steps == ephemeral.DEFAULT_MAX_STEPS == 60
    assert plain.max_steps > MAX_STEPS_PER_CARD


def test_agents_json_declares_one_ephemeral_agent_and_message_calls_it(env):
    spec = ephemeral.prepare(skill=None, prompt="araştır", brain_context="-",
                             engine={"model": "claude-opus-5"})
    payload = json.loads(spec.agents_json())
    assert list(payload) == [spec.slug]
    entry = payload[spec.slug]
    assert entry["prompt"] == spec.agent_md
    assert entry["model"] == "claude-opus-5"
    assert "WebSearch" in entry["tools"]
    assert f"Use the {spec.slug} subagent" in spec.user_message()


def test_every_run_gets_a_fresh_identity(env):
    a = ephemeral.prepare(skill=None, prompt="x", brain_context="-")
    b = ephemeral.prepare(skill=None, prompt="x", brain_context="-")
    assert a.slug != b.slug and a.session_id != b.session_id


# ---------------------------------------------------------------------------
# 2. Gerçek köprü yolu: argv, akış, rapor, hafıza, silme, defter
# ---------------------------------------------------------------------------


def test_full_loop_over_the_real_bridge_path(run_env, tmp_path, monkeypatch):
    from entropy.core.event_bus import bus
    from entropy.core.task_ledger import task_ledger

    stream_events = []
    notifications = []
    # DirectConnection ŞART: olaylar köprünün İŞ PARÇACIĞINDAN yayılıyor;
    # otomatik bağlantıda kuyruğa giriyor ve olay döngüsü olmayan testte hiç
    # teslim edilmiyordu (Faz 10 testlerindeki aynı kural).
    notify = lambda *a: notifications.append(a)
    bus.agent_stream.connect(stream_events.append, Qt.DirectConnection)
    bus.task_notification.connect(notify, Qt.DirectConnection)
    try:
        run = _make_run(tmp_path, run_env)
        spec = run.prepare()
        workdir = spec.workdir
        assert workdir.is_dir()
        run.spawn()
        assert run.finished.wait(30), "geçici ajan koşusu bitmedi"
    finally:
        for sig, fn in ((bus.agent_stream, stream_events.append),
                        (bus.task_notification, notify)):
            try:
                sig.disconnect(fn)
            except Exception:
                pass

    cmd = run_env["cmds"][-1]

    # (a) Tanım argv'de taşınır; diske ajan dosyası yazılmaz.
    assert "--agents" in cmd
    payload = json.loads(cmd[cmd.index("--agents") + 1])
    assert list(payload) == [spec.slug]
    # (b) Her koşu kendi oturumu; kalıcı kayıt yok.
    assert cmd[cmd.index("--session-id") + 1] == spec.session_id
    assert "--no-session-persistence" in cmd
    assert "--resume" not in cmd
    # (c) 14-B onay yüzeyi bozulmadı.
    assert cmd[cmd.index("--permission-mode") + 1] == "default"
    assert "--permission-prompt-tool" in cmd
    assert "--dangerously-skip-permissions" not in cmd
    # (d) Proje kökü argv'ye GİRMEZ: izin verilen dizinler izole çalışma dizini
    #     ve kasa rapor klasörüdür.
    add_dirs = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--add-dir"]
    assert str(workdir) in add_dirs
    assert str(Path(__file__).resolve().parents[2]) not in add_dirs

    # (e) Kalıcı oturum defterine yazılmadı.
    assert not run.bridge._background_conversations.get("x")
    sessions = list((tmp_path / "data").rglob("session.json"))
    assert sessions == []

    # (f) Canlı akış olayı yayıldı (doğuş + araç adımları).
    assert len(stream_events) >= 3
    assert any(spec.slug in str(e.get("agent") or "") for e in stream_events)

    # (g) Rapor: başlık H1'den, `[HAFIZA]` bloğu görüntüden silinmiş.
    assert run.report_path and Path(run.report_path).is_file()
    body = Path(run.report_path).read_text(encoding="utf-8")
    assert body.splitlines()[0].startswith("# canivopets.com")
    assert "[HAFIZA]" not in body

    # (h) Hafızayı ALT AJAN yazar: kapıya ham metin + kanıt bayrağı gider.
    assert len(run_env["memory"]) == 1
    call = run_env["memory"][0]
    assert call["success"] is True and call["has_proof"] is True
    assert "[HAFIZA]" in call["text"]

    # (i) TEK bildirim, çift kart yok.
    assert len(notifications) == 1
    summary = notifications[0][1]
    assert summary.startswith("Ajan ") and spec.slug in summary
    assert "araç adımı" in summary and run.report_path in summary

    # (j) Kendini sildi: çalışma dizini yok, defter satırı VAR.
    assert not workdir.exists()
    row = task_ledger.get_task(run.task_id)
    assert row and str(row.get("run_type") or "") == "ephemeral"


def test_agy_path_writes_and_then_deletes_the_agent_md(env, tmp_path):
    spec = ephemeral.prepare(skill=None, prompt="iş", brain_context="-",
                             engine={"provider": "agy"})
    spec.workdir = tmp_path / "wd"
    spec.workdir.mkdir()
    path = ephemeral._write_agy_agent_md(spec)
    assert path.is_file() and path.name == "agent.md"
    assert f"name: {spec.slug}" in path.read_text(encoding="utf-8")

    run = ephemeral.EphemeralRun(goal="iş")
    run.spec = spec
    run.cleanup()
    assert not spec.workdir.exists()


def test_step_ceiling_closes_the_card_in_review_not_failed(env, tmp_path,
                                                           monkeypatch):
    events = []
    monkeypatch.setattr(ephemeral, "_close_card",
                        lambda *a, **k: events.append(a))
    # Gerçek kapatma yolunun FSM sözleşmesi: adım tavanı `ok=True` ile gider.
    from entropy.agents import board_fsm

    payloads = []

    class _Board:
        def apply_event(self, card_id, event, actor="", payload=None):
            payloads.append((event, dict(payload or {})))
            return None

    monkeypatch.setattr("entropy.agents.tasks.TaskBoard", lambda *a, **k: _Board())
    monkeypatch.undo()  # `_close_card` taklidini kaldır, gerçeği ölç
    monkeypatch.setattr("entropy.agents.tasks.TaskBoard", lambda *a, **k: _Board())

    ephemeral._close_card("c-1", ok=False, hit_limit=True, report_path="r.md",
                          text="[ADIM SINIRI] …")
    assert payloads and payloads[-1][0] == "run.finished"
    assert payloads[-1][1]["ok"] is True  # tavana çarpan kart `review`e gider
    board_fsm.transitions_for("running", "run.finished")  # olay sözleşmede

    ephemeral._close_card("c-2", ok=False, hit_limit=False, report_path="",
                          text="hata")
    assert payloads[-1][1]["ok"] is False


def test_failed_run_does_not_feed_memory(run_env, tmp_path):
    run_env["lines"] = _stream_lines(text="", is_error=True)
    run = _make_run(tmp_path, run_env)
    run.prepare()
    run.spawn()
    assert run.finished.wait(30)
    assert run_env["memory"] == [] or run_env["memory"][0]["success"] is False


# ---------------------------------------------------------------------------
# 3. Tetikleme yüzeyleri
# ---------------------------------------------------------------------------


def test_agent_block_parses_and_is_stripped_from_the_displayed_text():
    text = ('Bakıyorum.\n[AJAN run] {"skill": "arastirma", "goal": "canivopets"} '
            '[/AJAN]\nSonuç gelince söylerim.')
    assert ephemeral.parse_agent_blocks(text) == [
        {"skill": "arastirma", "goal": "canivopets"}]
    cleaned = ephemeral.strip_agent_blocks(text)
    assert "[AJAN" not in cleaned and "Sonuç gelince" in cleaned
    # Bozuk JSON turu çöpe atmaz.
    assert ephemeral.parse_agent_blocks("[AJAN run] {bozuk} [/AJAN]") == []


def test_chat_hook_runs_one_ephemeral_agent_per_turn(monkeypatch):
    from entropy.core import response_hooks

    calls = []

    class _Run:
        spec = type("S", (), {"slug": "arastirma-abc"})()

    monkeypatch.setattr(ephemeral, "run_skill",
                        lambda skill, goal, **kw: (calls.append((skill, goal))
                                                   or _Run()))
    monkeypatch.setattr("entropy.agents.board_tools.parse_tool_calls",
                        lambda t: [])
    text = ('[AJAN run] {"skill": "arastirma", "goal": "A"} [/AJAN]\n'
            '[AJAN run] {"skill": "arastirma", "goal": "B"} [/AJAN]')
    out = response_hooks.process_chat_response(text)
    assert len(calls) == 1 and calls[0][1] == "A"
    assert "[AJAN" not in out
    assert "arastirma-abc" in out


def test_tool_contract_is_offered_to_entropy():
    from entropy.core.response_hooks import entropy_tools_section

    section = entropy_tools_section()
    assert "[AJAN run]" in section
    assert "kendini siler" in section


def test_slash_skill_run_starts_an_ephemeral_agent(monkeypatch):
    from entropy.core import slash_commands

    calls = []

    class _Run:
        spec = ephemeral.EphemeralSpec(slug="arastirma-1", skill="arastirma",
                                       goal="g", description="d", agent_md="m")

    monkeypatch.setattr(ephemeral, "run_skill",
                        lambda skill, goal, **kw: (calls.append((skill, goal))
                                                   or _Run()))
    out = slash_commands.try_handle_local_command(
        "/skill run arastirma :: canivopets.com'u araştır", bridge=None)
    assert out is not None and "arastirma-1" in out
    assert calls == [("arastirma", "canivopets.com'u araştır")]

    usage = slash_commands.try_handle_local_command("/skill", bridge=None)
    assert "/skill run" in usage


def test_dispatcher_gives_an_agentless_card_an_ephemeral_agent(env, tmp_path,
                                                               monkeypatch):
    from entropy.agents.dispatcher import BoardDispatcherCore
    from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id

    board = TaskBoard(vault_path=tmp_path / "Vault")
    card = board.create(TaskCard(id=new_task_id("ajansız iş"),
                                 title="ajansız iş", status="backlog",
                                 agent="", goal="canivopets araştır"))
    spawned = []

    class _Run:
        def __init__(self, **kw):
            self.kw = kw
            self.spec = None

        def prepare(self):
            self.spec = ephemeral.prepare(skill=None, prompt=self.kw.get("goal", ""),
                                          brain_context="-")
            return self.spec

        def spawn(self):
            spawned.append(self.kw)
            return "eph-1"

    monkeypatch.setattr(ephemeral, "EphemeralRun", _Run)
    core = BoardDispatcherCore(board=board, vault_path=tmp_path / "Vault")
    started = core.tick_ephemeral()
    assert started == [card.id]
    assert spawned and spawned[0]["card_id"] == card.id
    # Kalıcı kadrodan kimse seçilmedi.
    assert str(board.get(card.id).agent).startswith("arastirma-")
    assert board.get(card.id).status == "running"
