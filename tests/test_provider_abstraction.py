"""
Sağlayıcı soyutlaması: Claude Code köprüsü, fabrika, ledger göçü, maskeleme,
bağlam doluluğu.

Sahte köprüyle geçen test yetmediği için Claude akışı GERÇEK yoldan sürülür:
`subprocess.Popen` taklit edilir, gerçek `send_background_task_async` çağrılır
ve stream-json satırları gerçek ayrıştırıcıdan geçer. Böylece bayrak kurulumu,
olay çevirisi, token muhasebesi ve ledger yazımı birlikte doğrulanır.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from entropy.core.claude_bridge import (
    ClaudeCodeBridge,
    build_stdin_prompt_payload,
    normalize_permission_mode,
    parse_usage,
    prompt_via_stdin,
)
from entropy.core.event_bus import bus
from entropy.core.masking import mask_tool_output
from entropy.core.provider import (
    CONTEXT_PRESSURE_THRESHOLD,
    ProviderBridge,
    context_window_for,
    create_bridge,
    estimate_tokens,
    list_agent_definitions,
    provider_command,
    switch_provider,
)
from entropy.core.task_ledger import TaskLedger


# ---------------------------------------------------------------------------
# Sahte süreç: gerçek Popen yerine geçer, stream-json satırlarını akıtır
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 424242
        self.stdin = None
        self.stdout = self

    # stdout arayüzü
    def readline(self):
        return self._lines.pop(0) if self._lines else ""

    def close(self):
        pass

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


def _stream_lines(text="Merhaba dünya", usage=None, session="sess-1"):
    usage = usage or {
        "input_tokens": 1200,
        "output_tokens": 340,
        "cache_read_input_tokens": 8000,
        "cache_creation_input_tokens": 60,
    }
    return [
        json.dumps({"type": "system", "subtype": "init", "session_id": session,
                    "model": "claude-opus-5", "tools": ["Read", "Bash"]}) + "\n",
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}},
        ]}}) + "\n",
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": text},
        ]}}) + "\n",
        json.dumps({"type": "result", "subtype": "success", "result": text,
                    "session_id": session, "total_cost_usd": 0.0123,
                    "is_error": False, "usage": usage}) + "\n",
    ]


# ---------------------------------------------------------------------------
# Sözleşme ve bayraklar
# ---------------------------------------------------------------------------


def test_both_bridges_satisfy_provider_protocol():
    from entropy.core.agy_bridge import AgyProcessBridge

    assert isinstance(AgyProcessBridge(), ProviderBridge)
    assert isinstance(ClaudeCodeBridge(), ProviderBridge)


def test_claude_command_uses_real_cli_flags():
    b = ClaudeCodeBridge()
    b.selected_model = "claude-opus-5"
    cmd = b.build_command("selam", mode="accept-edits", project_dir=Path("C:/proj"), agent="distiller")

    # --verbose olmadan --print + stream-json ara olay yayınlamaz.
    assert "--verbose" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5"
    assert cmd[cmd.index("--agent") + 1] == "distiller"
    assert cmd[cmd.index("--add-dir") + 1] == str(Path("C:/proj"))
    assert cmd[1] == "-p"


def test_permission_mode_mapping_and_resume():
    assert normalize_permission_mode("accept-edits") == "acceptEdits"
    assert normalize_permission_mode("plan") == "plan"
    # Bilinmeyen kip güvenli varsayılana düşer; geçersiz değer süreci hiç başlatmaz.
    assert normalize_permission_mode("saçma-kip") == "acceptEdits"

    b = ClaudeCodeBridge()
    b.current_session_id = "abc-123"
    cmd = b.build_command("selam", resume=True)
    assert cmd[cmd.index("--resume") + 1] == "abc-123"


def test_long_prompt_moves_to_stdin_ndjson():
    b = ClaudeCodeBridge()
    long_prompt = "x" * 30_000
    assert prompt_via_stdin(long_prompt)
    cmd = b.build_command(long_prompt)
    payload = b._apply_stdin_prompt(cmd)

    assert cmd[cmd.index("-p") + 1] == ""
    assert cmd[cmd.index("--input-format") + 1] == "stream-json"
    obj = json.loads(payload)
    # Claude şeması "type" kullanır (agy "event" kullanıyordu).
    assert obj["type"] == "user"
    assert obj["message"]["content"] == long_prompt
    assert build_stdin_prompt_payload("a").endswith("\n")


# ---------------------------------------------------------------------------
# Gerçek yol: Popen taklidiyle arka plan görevi
# ---------------------------------------------------------------------------


def test_real_claude_bridge_background_task_streams_and_accounts_usage(tmp_path, monkeypatch):
    # Faz 14-B: onay yüzeyi açıkken kart koşusu izin ATLAMAZ; izin isteği
    # Entropy'nin MCP aracına sorulur. Veri kökü teste sabitlenir ki
    # `--mcp-config` dosyası kullanıcının gerçek kökünde oluşmasın.
    monkeypatch.setenv("ENTROPY_DATA_ROOT", str(tmp_path / "data"))
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path

    ledger = TaskLedger(db_path=tmp_path / "ledger.db")
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger", ledger)

    captured_cmd = {}

    def fake_popen(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        return _FakeProc(_stream_lines("Görev tamamlandı."))

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)

    outputs = []
    done = threading.Event()

    def on_result(text, ok):
        outputs.append((text, ok))
        done.set()

    b.send_background_task_async(
        task_id="t-1",
        task_name="Deneme",
        prompt="bir şey yap",
        project_path=str(tmp_path),
        on_result=on_result,
        save_report=False,
    )
    assert done.wait(10), "arka plan görevi bitmedi"

    text, ok = outputs[0]
    assert ok is True
    assert text == "Görev tamamlandı."

    # Faz 14-B sözleşmesi: onay yüzeyi açıkken (varsayılan) izin atlama bayrağı
    # HİÇ gönderilmez — gönderilseydi CLI izin aracını çağırmaz ve onay kartı
    # hiç doğmazdı (canlı S2 ölçümü). İzin kipi de `default` olmak zorunda:
    # `acceptEdits` dosya yazımını kancadan önce otomatik onaylıyor.
    cmd = captured_cmd["cmd"]
    assert "--dangerously-skip-permissions" not in cmd
    assert cmd[cmd.index("--permission-prompt-tool") + 1] == "mcp__entropy__approve"
    assert cmd[cmd.index("--permission-mode") + 1] == "default"

    # usage: girdi + çıktı + önbellek kalemleri toplanır.
    assert b.last_background_usage["input_tokens"] == 1200
    assert b.last_background_usage["output_tokens"] == 340
    assert b.last_background_usage["cache_read_tokens"] == 8000
    assert b.last_background_usage["total_tokens"] == 1200 + 340 + 8000 + 60
    assert b.background_total_tokens == b.last_background_usage["total_tokens"]

    row = ledger.get_task("t-1")
    assert row["status"] == "SUCCESS"
    assert row["provider"] == "claude"
    assert row["total_tokens"] == 9600


def test_real_claude_bridge_falls_back_to_skip_flag_when_approvals_disabled(
    tmp_path, monkeypatch
):
    """
    Onay yüzeyi KAPALIYKEN (Faz 13 davranışı) kart koşusu eski bayrağı alır.

    İki bayrak birbirini dışlar; bu test ikinci kolun canlı kalmasını sağlar
    (gerçek `send_background_task_async` yolu, sahte `Popen`).
    """
    from entropy.core.config import config as cfg

    monkeypatch.setenv("ENTROPY_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(cfg, "approvals_enabled", False, raising=False)

    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    monkeypatch.setattr(
        "entropy.core.claude_bridge.task_ledger", TaskLedger(db_path=tmp_path / "l.db")
    )

    captured_cmd = {}

    def fake_popen(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        return _FakeProc(_stream_lines("Bitti."))

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)

    done = threading.Event()
    b.send_background_task_async(
        task_id="t-2",
        task_name="Deneme",
        prompt="bir şey yap",
        project_path=str(tmp_path),
        on_result=lambda text, ok: done.set(),
        save_report=False,
    )
    assert done.wait(10), "arka plan görevi bitmedi"

    cmd = captured_cmd["cmd"]
    assert "--dangerously-skip-permissions" in cmd
    assert "--permission-prompt-tool" not in cmd


def test_stream_adapter_emits_bus_signals_and_reads_session():
    b = ClaudeCodeBridge()
    chunks = []
    bus.token_chunk_received.connect(chunks.append)
    try:
        res = b.consume_stream(iter(_stream_lines("akış metni", session="s-9")))
    finally:
        bus.token_chunk_received.disconnect(chunks.append)

    assert res["text"] == "akış metni"
    assert res["session_id"] == "s-9"
    assert res["cost_usd"] == pytest.approx(0.0123)
    assert res["is_error"] is False
    assert "akış metni" in chunks


def test_parse_usage_handles_missing_total():
    u = parse_usage({"input_tokens": 10, "output_tokens": 5})
    assert u["total_tokens"] == 15
    assert parse_usage(None) == {}


# ---------------------------------------------------------------------------
# auth_status
# ---------------------------------------------------------------------------


def test_claude_auth_status_reads_json(monkeypatch):
    class _Res:
        returncode = 0
        stdout = json.dumps({"loggedIn": True, "authMethod": "claude.ai",
                             "email": "a@b.c", "subscriptionType": "max"})
        stderr = ""

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.run", lambda *a, **k: _Res())
    st = ClaudeCodeBridge().auth_status()
    assert st["provider"] == "claude"
    assert st["logged_in"] is True
    assert st["subscription"] == "max"


def test_claude_auth_status_survives_missing_cli(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("claude yok")

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.run", boom)
    st = ClaudeCodeBridge().auth_status()
    assert st["logged_in"] is False
    assert "claude yok" in st["error"]


def test_agy_auth_status_uses_models_probe(monkeypatch):
    from entropy.core.agy_bridge import AgyProcessBridge

    class _Res:
        returncode = 0
        stdout = "gemini-3.1-pro-high\n"
        stderr = ""

    monkeypatch.setattr("entropy.core.agy_bridge.subprocess.run", lambda *a, **k: _Res())
    st = AgyProcessBridge().auth_status()
    assert st == {"provider": "agy", "logged_in": True, "auth_method": "antigravity-cli"}


# ---------------------------------------------------------------------------
# Fabrika ve sağlayıcı değişimi
# ---------------------------------------------------------------------------


class _Cfg:
    provider = "agy"
    provider_models = {"agy": "gemini-3.1-pro-high", "claude": "claude-opus-5"}
    selected_model = "gemini-3.1-pro-high"
    saved = 0

    def save_settings(self):
        _Cfg.saved += 1


def test_create_bridge_picks_provider_from_config():
    cfg = _Cfg()
    assert create_bridge(cfg).provider_name == "agy"
    cfg.provider = "claude"
    assert create_bridge(cfg).provider_name == "claude"
    # Bilinmeyen ad sessizce agy'ye düşer; uygulama açılmamazlık etmemeli.
    cfg.provider = "yok-böyle"
    assert create_bridge(cfg).provider_name == "agy"


def test_switch_provider_shuts_down_old_bridge_and_swaps_model():
    cfg = _Cfg()
    cfg.provider = "agy"
    old = create_bridge(cfg)
    calls = []
    old.shutdown = lambda timeout=3.0: calls.append(timeout) or {}

    new = switch_provider(old, "claude", cfg=cfg)

    assert calls, "eski köprü söndürülmedi; süreçleri öksüz kalırdı"
    assert new.provider_name == "claude"
    assert cfg.provider == "claude"
    assert cfg.selected_model == "claude-opus-5"

    with pytest.raises(ValueError):
        switch_provider(new, "gpt")


def test_provider_command_parsing():
    assert provider_command("/provider") == {"action": "show"}
    assert provider_command("/provider claude") == {"action": "set", "provider": "claude"}
    assert provider_command("  /provider AGY  ") == {"action": "set", "provider": "agy"}
    assert provider_command("/provider gpt")["action"] == "error"
    assert provider_command("normal mesaj") is None
    assert provider_command("/providers") is None


def test_agent_definition_layout_differs_per_provider(tmp_path):
    (tmp_path / ".agents" / "agents" / "distiller").mkdir(parents=True)
    (tmp_path / ".agents" / "agents" / "distiller" / "agent.md").write_text("x", encoding="utf-8")
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "reviewer.md").write_text("x", encoding="utf-8")

    assert list_agent_definitions("agy", tmp_path) == ["distiller"]
    assert list_agent_definitions("claude", tmp_path) == ["reviewer"]
    assert list_agent_definitions("claude", tmp_path / "yok") == []


# ---------------------------------------------------------------------------
# Ledger: provider sütunu ve geriye uyumlu göç
# ---------------------------------------------------------------------------


def test_provider_column_migration_keeps_old_rows_readable(tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE tasks (task_id TEXT PRIMARY KEY, task_name TEXT NOT NULL,
           project_path TEXT, status TEXT NOT NULL, created_at TIMESTAMP,
           started_at TIMESTAMP, completed_at TIMESTAMP, error TEXT, result_summary TEXT)"""
    )
    conn.execute(
        "INSERT INTO tasks VALUES ('eski','Eski Görev','C:/x','SUCCESS','t','t','t',NULL,'özet')"
    )
    conn.commit()
    conn.close()

    ledger = TaskLedger(db_path=db)
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(tasks)")}
    assert "provider" in cols

    # Sütun eklenmeden önce yazılmış satır: değeri NULL, okurken "agy" varsayılır.
    assert ledger.get_task("eski")["provider"] == "agy"

    ledger.record_task_start("yeni", "Yeni", "C:/x", provider="claude")
    assert ledger.get_task("yeni")["provider"] == "claude"
    # Parametresiz eski çağrı yerleri kırılmamalı.
    ledger.record_task_start("varsayilan", "V", "C:/x")
    assert ledger.get_task("varsayilan")["provider"] == "agy"


# ---------------------------------------------------------------------------
# Maskeleme
# ---------------------------------------------------------------------------


def test_mask_tool_output_replaces_only_long_bodies():
    big = "L" * 5000
    text = (
        "Başlangıç.\n"
        "[✔ ARAÇ TAMAMLANDI: Read (0.10s)]\n"
        "   Sonuç: C:\\proj\\a.py " + big + "\n"
        "[✔ ARAÇ TAMAMLANDI: Grep (0.02s)]\n"
        "   Sonuç: kısa çıktı\n"
    )
    masked = mask_tool_output(text)

    assert big not in masked
    assert "[araç çıktısı:" in masked
    assert "karakter, kaynak:" in masked
    assert "Read" in masked
    assert "C:\\proj\\a.py" in masked  # kaynak korunur
    assert "kısa çıktı" in masked      # sınır altı blok dokunulmaz
    assert masked.startswith("Başlangıç.")
    assert mask_tool_output("") == ""
    assert mask_tool_output(None) == ""


def test_masking_applied_to_ledger_summary(tmp_path, monkeypatch):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    ledger = TaskLedger(db_path=tmp_path / "l.db")
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger", ledger)

    body = "Z" * 4000
    text = "Rapor.\n[✔ ARAÇ TAMAMLANDI: Read (0.1s)]\n   Sonuç: C:\\x\\y.py " + body

    monkeypatch.setattr(
        "entropy.core.claude_bridge.subprocess.Popen",
        lambda cmd, **k: _FakeProc(_stream_lines(text)),
    )
    done = threading.Event()
    b.send_background_task_async(
        task_id="m-1", task_name="Maske", prompt="p",
        project_path=str(tmp_path), on_result=lambda *_: done.set(), save_report=False,
    )
    assert done.wait(10)

    summary = ledger.get_task("m-1")["result_summary"]
    assert "ZZZZ" not in summary
    assert "[araç çıktısı:" in summary


# ---------------------------------------------------------------------------
# Bağlam doluluğu ve baskı sinyali
# ---------------------------------------------------------------------------


def test_context_window_depends_on_provider_and_model():
    assert context_window_for("agy") == 1_000_000
    assert context_window_for("claude", "claude-opus-5") == 200_000
    assert context_window_for("claude", "claude-sonnet-5") == 1_000_000
    assert estimate_tokens("abcd" * 100) == 100


def test_context_fill_ratio_and_pressure_signal_fires_once():
    b = ClaudeCodeBridge()
    b.selected_model = "claude-opus-5"          # 200k pencere
    b.conversation_history = []
    b.latest_input_tokens = 0
    assert b.context_fill_ratio() == 0.0

    b.latest_input_tokens = 150_000             # %75
    ratio = b.context_fill_ratio()
    assert ratio > CONTEXT_PRESSURE_THRESHOLD

    seen = []
    bus.context_pressure.connect(seen.append)
    try:
        b.check_context_pressure()
        b.check_context_pressure()              # ikinci tur susmalı
    finally:
        bus.context_pressure.disconnect(seen.append)

    assert len(seen) == 1
    assert seen[0] == pytest.approx(ratio)

    # Doluluk düşünce bayrak sıfırlanır; yeniden dolarsa tekrar uyarır.
    b.latest_input_tokens = 1000
    b.check_context_pressure()
    assert b._context_pressure_announced is False


def test_handoff_compacts_history_when_memory_module_available(monkeypatch, tmp_path):
    import sys
    import types

    b = ClaudeCodeBridge()
    b.conversation_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"tur {i}"}
        for i in range(20)
    ]

    page = tmp_path / "handoff.md"
    seen = {}

    fake = types.ModuleType("entropy.brain.handoff")

    def write_handoff(history, meta):
        seen["n"] = len(history)
        seen["meta"] = meta
        page.write_text("devam", encoding="utf-8")
        return str(page)

    fake.write_handoff = write_handoff
    monkeypatch.setitem(sys.modules, "entropy.brain.handoff", fake)

    result = b.compact_context_via_handoff()

    assert result == str(page)
    assert seen["n"] == 20
    assert seen["meta"]["provider"] == "claude"
    # Yeni geçmiş: aktarım özeti + son 4 tur (8 mesaj).
    assert len(b.conversation_history) == 9
    assert b.conversation_history[0]["role"] == "system"
    assert str(page) in b.conversation_history[0]["content"]
    assert b.conversation_history[-1]["content"] == "tur 19"


def test_handoff_is_noop_without_memory_module(monkeypatch):
    import builtins

    b = ClaudeCodeBridge()
    b.conversation_history = [{"role": "user", "content": "a"}]

    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name == "entropy.brain.handoff":
            raise ImportError("henüz yok")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    assert b.compact_context_via_handoff() is None
    assert len(b.conversation_history) == 1


# ---------------------------------------------------------------------------
# Kapanış
# ---------------------------------------------------------------------------


def test_claude_shutdown_is_idempotent_and_cancels_ledger(tmp_path, monkeypatch):
    b = ClaudeCodeBridge()
    ledger = TaskLedger(db_path=tmp_path / "s.db")
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger", ledger)
    ledger.record_task_start("a", "A", str(tmp_path), provider="claude")

    killed = []
    monkeypatch.setattr(ClaudeCodeBridge, "_kill_tree", staticmethod(lambda p, wait_budget: killed.append(p)))

    proc = _FakeProc([])
    proc.returncode = None
    b._background_processes["a"] = proc

    stats = b.shutdown(timeout=1.0)
    assert stats["processes"] == 1
    assert stats["tasks"] == 1
    assert ledger.get_task("a")["status"] == "CANCELLED"

    # İkinci çağrı sessizce hiçbir şey yapmamalı (kapanış yolu iki kez tetiklenebiliyor).
    assert b.shutdown(timeout=1.0) == {"processes": 0, "tasks": 0, "threads": 0}

    # Kapanıştan sonra hiçbir yeni görev başlamamalı.
    b.send_background_task_async(task_id="x", task_name="X", prompt="p")
    time.sleep(0.2)
    assert ledger.get_task("x") is None
