"""
Faz 11-F spike testleri: `claude --bg` sarmalayıcısının ayrıştırıcıları,
durum makinesi ve GERÇEK süreç yolu (sahte bir `claude` çalıştırılabiliriyle).

Gerçek CLI çağrısı yapılmaz: kota harcayan koşu yalnızca spike betiğindeydi,
bulguları rapora ve modül başlığına yazıldı. Buradaki beklentiler o koşudan
birebir kopyalanan CLI çıktılarına dayanır.

**ARŞİV (Faz 13-C, ADR-0007 / ADR-0009).** Sınadığı modül üründen çıkarıldı:
`docs/_archive/spikes/claude_bg/claude_bg.py`. Bu dosya bir *ispat defteri*
olarak saklanır ve **toplanmaz** (`tests/_reference/conftest.py`
`collect_ignore`). Yeniden koşmak için modülü `src/entropy/core/claude_bg.py`
yoluna geri koymak yeterlidir; geri getirme adımları arşiv README'sindedir.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from entropy.core import claude_bg
from entropy.core.claude_bg import (
    BgAgent,
    ClaudeBgError,
    ClaudeBgSession,
    CommandResult,
    TimelineEntry,
    build_resume_command,
    build_start_command,
    parse_agents_json,
    parse_start_output,
    read_job_state,
    read_timeline,
    timeline_to_stream_events,
)

# Spike koşusundan (CLI 2.1.265) birebir alınan çıktılar.
OUT_STARTED = (
    "warning: --bg manages the session id; ignoring --session-id "
    "(use --resume <id> to continue an existing session)\n"
    "Starting background service\u2026\n"
    "backgrounded \u00b7 bfabe6d4 \u00b7 entropy-spike-1\n"
    "  claude agents             list sessions\n"
)
OUT_FORKED = (
    "note: session bfabe6d4 is already running in the background, so this "
    "started a copy as d1d56346. `claude attach bfabe6d4` opens the original.\n"
    "backgrounded \u00b7 d1d56346\n"
)
OUT_FLAGS_FORKED = (
    "note: background session bfabe6d4 keeps its own saved options, so the "
    "flags you passed started a copy as 075ba21c. Without flags, the same "
    "command continues bfabe6d4 itself.\n"
    "backgrounded \u00b7 075ba21c \u00b7 entropy-spike-1\n"
)
OUT_WOKEN = (
    "note: woke session bfabe6d4 with its saved options (--name, "
    "--system-prompt-file, --strict-mcp-config, --setting-sources, --tools, "
    "--permission-mode, --add-dir).\n"
    "backgrounded \u00b7 bfabe6d4 \u00b7 entropy-spike-1\n"
)
OUT_PRINT_CONFLICT = (
    "--bg and --print conflict: --print never starts the interactive session "
    "that `claude agents` attaches to, so the job would be unattachable."
)
AGENTS_JSON = json.dumps(
    [
        {
            "pid": 39128,
            "cwd": "C:\\EntropiAI",
            "kind": "interactive",
            "startedAt": 1789004008482,
            "sessionId": "1bdbc000-be5a-4312-95b3-82cc3ec4774d",
            "name": "entropiai-48",
        },
        {
            "pid": 54708,
            "id": "bfabe6d4",
            "cwd": "C:\\ws",
            "kind": "background",
            "startedAt": 1789011799752,
            "sessionId": "bfabe6d4-a440-410a-bdbe-7c11cce1d49a",
            "name": "entropy-spike-1",
            "status": "idle",
            "state": "done",
        },
    ]
)


# ----------------------------------------------------------------------
# Yardımcılar
# ----------------------------------------------------------------------

def _write_job(root: Path, job_id: str, *, state="done", tokens=13, flags=None, turns=()):
    """Diskteki iş künyesini (`state.json` + `timeline.jsonl`) kurar."""
    directory = root / job_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "state.json").write_text(
        json.dumps(
            {
                "state": state,
                "detail": "detay",
                "tempo": "idle",
                "tokens": tokens,
                "output": {"result": "1+1 = 2 eder"},
                "sessionId": job_id + "-a440-410a-bdbe-7c11cce1d49a",
                "resumeSessionId": job_id + "-a440-410a-bdbe-7c11cce1d49a",
                "name": "entropy-spike-1",
                "cwd": "C:\\ws",
                "respawnFlags": list(
                    flags
                    if flags is not None
                    else ["--name", "s", "--system-prompt-file", "p.txt", "--strict-mcp-config"]
                ),
                "updatedAt": "2026-09-10T03:43:22.344Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    lines = [json.dumps(t, ensure_ascii=False) for t in turns]
    (directory / "timeline.jsonl").write_text(
        ("\n".join(lines) + "\n") if lines else "", encoding="utf-8"
    )
    return directory


class FakeRunner:
    """Komutları kaydeden, önceden yazılmış çıktıları döndüren koşucu."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, cmd, cwd):
        self.calls.append((list(cmd), cwd))
        if self.responses:
            return self.responses.pop(0)
        return CommandResult(0, "", "")


# ----------------------------------------------------------------------
# Ayrıştırıcılar
# ----------------------------------------------------------------------

def test_parse_start_output_reads_short_id():
    parsed = parse_start_output(OUT_STARTED)
    assert parsed["id"] == "bfabe6d4"
    assert parsed["forked"] is False
    assert parsed["woken"] is False


def test_parse_start_output_flags_fork_on_live_resume():
    parsed = parse_start_output(OUT_FORKED)
    assert parsed["id"] == "d1d56346"
    assert parsed["forked"] is True


def test_parse_start_output_flags_fork_when_flags_passed_to_resume():
    parsed = parse_start_output(OUT_FLAGS_FORKED)
    assert parsed["id"] == "075ba21c"
    assert parsed["forked"] is True


def test_parse_start_output_detects_woken_same_id():
    parsed = parse_start_output(OUT_WOKEN)
    assert parsed["id"] == "bfabe6d4"
    assert parsed["woken"] is True
    assert parsed["forked"] is False


def test_parse_start_output_survives_mangled_separator():
    """Windows konsol kod sayfası CLI'ın orta nokta ayracını bozabilir."""
    assert parse_start_output("backgrounded � bfabe6d4 � ajan")["id"] == "bfabe6d4"
    assert parse_start_output("backgrounded ? bfabe6d4")["id"] == "bfabe6d4"


def test_parse_start_output_raises_on_print_conflict():
    with pytest.raises(ClaudeBgError):
        parse_start_output(OUT_PRINT_CONFLICT)


def test_parse_agents_json_separates_background_from_interactive():
    agents = parse_agents_json(AGENTS_JSON)
    assert len(agents) == 2
    interactive, background = agents
    assert interactive.is_background is False and interactive.id == ""
    assert background.is_background and background.id == "bfabe6d4"
    assert background.is_alive and background.state == "done"


def test_parse_agents_json_tolerates_garbage():
    assert parse_agents_json("bu json degil") == []
    assert parse_agents_json('{"a": 1}') == []


def test_dead_session_has_no_pid():
    agent = BgAgent(id="x", kind="background")
    assert agent.is_alive is False


# ----------------------------------------------------------------------
# Komut kurucular (ölçülmüş CLI kuralları)
# ----------------------------------------------------------------------

def test_start_command_never_uses_print_or_session_id_or_output_format():
    cmd = build_start_command(
        "merhaba",
        name="ofis-1",
        system_prompt_file="p.txt",
        tools=["Read", "Bash"],
        add_dirs=["C:/ws"],
    )
    assert cmd[:3] == ["claude", "--bg", "merhaba"]
    for banned in ("-p", "--print", "--session-id", "--output-format"):
        assert banned not in cmd
    assert "--system-prompt-file" in cmd and "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--tools") + 1] == "Read,Bash"
    assert cmd[cmd.index("--setting-sources") + 1] == ""


def test_start_command_rejects_empty_prompt():
    with pytest.raises(ClaudeBgError):
        build_start_command("   ")


def test_resume_command_is_deliberately_flagless():
    cmd = build_resume_command("sid-1", "devam et")
    assert cmd == ["claude", "--bg", "--resume", "sid-1", "devam et"]


# ----------------------------------------------------------------------
# Disk okuyucuları
# ----------------------------------------------------------------------

def test_read_job_state_and_isolation_flag(tmp_path):
    _write_job(tmp_path, "bfabe6d4")
    state = read_job_state("bfabe6d4", tmp_path)
    assert state.is_done and state.tokens == 13
    assert state.result == "1+1 = 2 eder"
    assert state.isolated is True


def test_forked_job_loses_isolation_flags(tmp_path):
    _write_job(tmp_path, "d1d56346", flags=["--model", "claude-fable-5-1"])
    assert read_job_state("d1d56346", tmp_path).isolated is False


def test_read_job_state_missing_returns_none(tmp_path):
    assert read_job_state("yok", tmp_path) is None


def test_read_timeline_cursor_is_incremental(tmp_path):
    _write_job(
        tmp_path,
        "bfabe6d4",
        turns=[{"at": "t1", "state": "done", "detail": "d1", "text": "1+1 = 2 eder."}],
    )
    first, offset = read_timeline("bfabe6d4", 0, tmp_path)
    assert [e.text for e in first] == ["1+1 = 2 eder."]
    again, offset2 = read_timeline("bfabe6d4", offset, tmp_path)
    assert again == [] and offset2 == offset

    path = tmp_path / "bfabe6d4" / "timeline.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": "t2", "state": "done", "text": "2 + 3 = 5"}) + "\n")
    third, _ = read_timeline("bfabe6d4", offset, tmp_path)
    assert [e.text for e in third] == ["2 + 3 = 5"]


def test_read_timeline_resets_cursor_when_file_shrinks(tmp_path):
    _write_job(tmp_path, "j", turns=[{"at": "t1", "state": "done", "text": "a"}])
    entries, _ = read_timeline("j", 10_000, tmp_path)
    assert [e.text for e in entries] == ["a"]


def test_read_timeline_skips_broken_lines(tmp_path):
    directory = _write_job(tmp_path, "j")
    (directory / "timeline.jsonl").write_text(
        "{bozuk\n" + json.dumps({"at": "t", "state": "working", "text": "iyi"}) + "\n",
        encoding="utf-8",
    )
    entries, _ = read_timeline("j", 0, tmp_path)
    assert [e.text for e in entries] == ["iyi"]


# ----------------------------------------------------------------------
# Sahne eşlemesi
# ----------------------------------------------------------------------

def test_timeline_to_stream_events_maps_states():
    events = timeline_to_stream_events(
        [
            TimelineEntry(state="working", text="dosya yaziyorum"),
            TimelineEntry(state="done", text="bitti"),
            TimelineEntry(state="failed", detail="patladi"),
            TimelineEntry(state="bilinmeyen", text="?"),
        ],
        agent="orkestrator",
        office="ofis-1",
    )
    assert [e["state"] for e in events] == ["working", "idle", "error", "thinking"]
    assert [e["kind"] for e in events] == ["text", "result", "error", "text"]
    assert events[0]["provider"] == "claude"
    assert events[0]["agent"] == "orkestrator" and events[0]["office"] == "ofis-1"
    assert events[2]["text"] == "patladi"


def test_timeline_to_stream_events_truncates_long_text():
    from entropy.core.provider import BUBBLE_TEXT_LIMIT

    long_text = "x" * (BUBBLE_TEXT_LIMIT + 50)
    event = timeline_to_stream_events([TimelineEntry(state="working", text=long_text)])[0]
    assert len(event["text"]) <= BUBBLE_TEXT_LIMIT
    assert event["full_text"] == long_text


# ----------------------------------------------------------------------
# Oturum yöneticisi (sahte koşucu)
# ----------------------------------------------------------------------

def _session(tmp_path, responses):
    runner = FakeRunner(responses)
    session = ClaudeBgSession(
        tmp_path / "store",
        runner=runner,
        jobs_root=tmp_path / "jobs",
    )
    return session, runner


def test_start_records_mapping_and_survives_reload(tmp_path):
    _write_job(tmp_path / "jobs", "bfabe6d4")
    session, runner = _session(tmp_path, [CommandResult(0, OUT_STARTED, "")])
    job_id = session.start(
        "orkestrator", "merhaba", cwd=str(tmp_path), office="ofis-1", system_prompt_file="p.txt"
    )
    assert job_id == "bfabe6d4"
    assert "--bg" in runner.calls[0][0] and runner.calls[0][1] == str(tmp_path)

    # Uygulama yeniden açıldı: kayıt diskten okunur.
    reloaded = ClaudeBgSession(tmp_path / "store", runner=FakeRunner([]), jobs_root=tmp_path / "jobs")
    record = reloaded.record("orkestrator")
    assert record.job_id == "bfabe6d4"
    assert record.session_id.startswith("bfabe6d4-")
    assert record.office == "ofis-1"


def test_start_raises_on_print_conflict(tmp_path):
    session, _ = _session(tmp_path, [CommandResult(1, "", OUT_PRINT_CONFLICT)])
    with pytest.raises(ClaudeBgError):
        session.start("a", "merhaba")


def test_send_stops_first_then_resumes_flagless(tmp_path):
    _write_job(tmp_path / "jobs", "bfabe6d4")
    session, runner = _session(
        tmp_path,
        [CommandResult(0, OUT_STARTED, ""), CommandResult(0, "stopped", ""), CommandResult(0, OUT_WOKEN, "")],
    )
    session.start("a", "merhaba")
    assert session.send("a", "devam et") == "bfabe6d4"

    stop_cmd, resume_cmd = runner.calls[1][0], runner.calls[2][0]
    assert stop_cmd == ["claude", "stop", "bfabe6d4"]
    assert resume_cmd[:4] == ["claude", "--bg", "--resume", "bfabe6d4-a440-410a-bdbe-7c11cce1d49a"]
    # Bayrak eklenmemeli: bayrak = kopya oturum = izolasyon kaybı.
    assert not [a for a in resume_cmd[4:] if a.startswith("--")]
    assert session.record("a").meta.get("forked") is None


def test_send_marks_record_when_cli_forks(tmp_path):
    _write_job(tmp_path / "jobs", "bfabe6d4")
    _write_job(tmp_path / "jobs", "d1d56346", flags=["--model", "x"])
    session, _ = _session(
        tmp_path,
        [CommandResult(0, OUT_STARTED, ""), CommandResult(0, "stopped", ""), CommandResult(0, OUT_FORKED, "")],
    )
    session.start("a", "merhaba")
    assert session.send("a", "devam") == "d1d56346"
    record = session.record("a")
    assert record.meta["forked"] is True
    assert record.cursor == 0  # yeni işin zaman çizgisi baştan okunur


def test_send_without_session_raises(tmp_path):
    session, _ = _session(tmp_path, [])
    with pytest.raises(ClaudeBgError):
        session.send("yok", "selam")


def test_logs_advance_cursor_across_calls(tmp_path):
    jobs = tmp_path / "jobs"
    _write_job(jobs, "bfabe6d4", turns=[{"at": "t1", "state": "done", "text": "birinci"}])
    session, _ = _session(tmp_path, [CommandResult(0, OUT_STARTED, "")])
    session.start("a", "merhaba")
    assert [e.text for e in session.logs("a")] == ["birinci"]
    assert session.logs("a") == []
    with (jobs / "bfabe6d4" / "timeline.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": "t2", "state": "working", "text": "ikinci"}) + "\n")
    events = session.stream_events("a")
    assert [e["text"] for e in events] == ["ikinci"]
    assert events[0]["state"] == "working"


def test_reattach_drops_orphan_records(tmp_path):
    _write_job(tmp_path / "jobs", "bfabe6d4")
    session, _ = _session(tmp_path, [CommandResult(0, OUT_STARTED, "")])
    session.start("yasayan", "merhaba")
    session._records["olmus"] = type(session.record("yasayan"))(agent="olmus", job_id="deadbeef")
    session._runner = FakeRunner([CommandResult(0, AGENTS_JSON, "")])
    alive = session.reattach()
    assert set(alive) == {"yasayan"}
    assert session.record("olmus") is None


def test_remove_stops_and_deletes(tmp_path):
    _write_job(tmp_path / "jobs", "bfabe6d4")
    session, runner = _session(
        tmp_path,
        [CommandResult(0, OUT_STARTED, ""), CommandResult(0, "stopped", ""), CommandResult(0, "removed", "")],
    )
    session.start("a", "merhaba")
    assert session.remove("a") is True
    assert runner.calls[1][0] == ["claude", "stop", "bfabe6d4"]
    assert runner.calls[2][0] == ["claude", "rm", "bfabe6d4"]
    assert session.record("a") is None
    assert session.remove("a") is False


def test_list_returns_empty_when_cli_fails(tmp_path):
    session, _ = _session(tmp_path, [CommandResult(1, "", "boom")])
    assert session.list() == []


# ----------------------------------------------------------------------
# GERÇEK süreç yolu: sahte bir `claude` çalıştırılabiliri
# ----------------------------------------------------------------------

def _fake_cli(tmp_path: Path) -> str:
    """
    Diske gerçek bir çalıştırılabilir yazar; `_default_runner` onu `subprocess`
    ile koşar. Sahte koşucuyla geçen test argv/kodlama hatalarını yakalamaz.
    """
    script = tmp_path / "fake_cli.py"
    script.write_text(
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if '--print' in args or '-p' in args:\n"
        "    sys.stderr.write('--bg and --print conflict')\n"
        "    sys.exit(1)\n"
        "if args[:1] == ['stop']:\n"
        "    print('stopped ' + args[1]); sys.exit(0)\n"
        "if args[:1] == ['agents']:\n"
        "    print('[]'); sys.exit(0)\n"
        "if '--resume' in args:\n"
        "    print('note: woke session bfabe6d4 with its saved options (--tools).')\n"
        "print('backgrounded \\u00b7 bfabe6d4 \\u00b7 ' + 'ajan')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        launcher = tmp_path / "claude.bat"
        launcher.write_text(
            "@echo off\r\n\"%s\" \"%s\" %%*\r\n" % (sys.executable, script), encoding="utf-8"
        )
    else:
        launcher = tmp_path / "claude.sh"
        launcher.write_text(
            '#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, script), encoding="utf-8"
        )
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    return str(launcher)


def test_real_subprocess_path_starts_and_resumes(tmp_path):
    """Sahte koşucu değil: gerçek `subprocess` yolu, gerçek argv sınırları."""
    _write_job(tmp_path / "jobs", "bfabe6d4", turns=[{"at": "t", "state": "done", "text": "tamam"}])
    session = ClaudeBgSession(
        tmp_path / "store",
        claude_path=_fake_cli(tmp_path),
        jobs_root=tmp_path / "jobs",
    )
    job_id = session.start("ajan", "tek cumlelik istem", cwd=str(tmp_path), system_prompt_file="p.txt")
    assert job_id == "bfabe6d4"
    assert session.state("ajan").isolated is True
    assert [e.text for e in session.logs("ajan")] == ["tamam"]
    assert session.send("ajan", "devam et") == "bfabe6d4"
    assert session.record("ajan").meta.get("forked") is None


def test_real_subprocess_path_surfaces_print_conflict(tmp_path):
    session = ClaudeBgSession(
        tmp_path / "store", claude_path=_fake_cli(tmp_path), jobs_root=tmp_path / "jobs"
    )
    # `_default_runner` üzerinden -p geçirmek için doğrudan argv kuruyoruz.
    result = claude_bg._default_runner([session.claude_path, "--bg", "-p", "x"], None)
    assert result.returncode == 1 and "conflict" in result.stderr


def test_claude_home_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert claude_bg.claude_home() == tmp_path
    assert claude_bg.jobs_dir() == tmp_path / "jobs"
    assert claude_bg.job_dir("abc") == tmp_path / "jobs" / "abc"
