"""
Faz 14-B sözleşmesi — GERÇEK ONAY YÜZEYİ.

Kullanıcının yaşadığı arıza: "iki komut onay penceresinde bekliyor" denildi ama
ortada pencere de kuyruk da yoktu; saf kip CLI'ın izin diyaloğunu düşürmüş,
yerine bir şey konmamıştı (ARCHITECTURE §6.6). Bu dosya yerine konanı ölçer:

1. `core/pending.py` — tek kuyruk (add/list/resolve/wait/expire, tek kök,
   `bus.pending_changed`).
2. `core/permission_server.py` — bağımlılıksız stdio MCP sunucusu; el sıkışma,
   `tools/call` → kuyruk → karar → `content[0].text` JSON'u (allow/deny/expire).
   Şema canlı ölçümden geliyor (`scratch/phase14/permission_spike/README.md`).
3. Köprü argv'si: onay açıkken `--permission-prompt-tool` + `--mcp-config` var,
   `--dangerously-skip-permissions` YOK; kapalıyken tam tersi.
4. `result.permission_denials` → `bus.tool_permission_event` + sohbet satırı.
5. "onaylıyorum" CLI'ya gitmeden çözülür.
6. `desk_admin` istekleri aynı listede `kind="desk_change"` olarak görünür.
7. Paket eşlemesi (spec) yeni modülleri taşır.

Model çağrısı YOK: tek gerçek alt süreç, izin MCP sunucusunun kendisidir
(yerel Python, kota harcamaz).
"""

import json
import os
import subprocess
import sys
import threading
import time
from io import StringIO
from pathlib import Path

import pytest

from entropy.core import pending as pending_mod
from entropy.core import permission_server as ps
from entropy.core.claude_bridge import ClaudeCodeBridge
from entropy.core.event_bus import bus


@pytest.fixture()
def queue(tmp_path, monkeypatch):
    """Kuyruk izole bir veri kökünde (gerçek `~/.entropy` ASLA kullanılmaz)."""
    monkeypatch.setenv("ENTROPY_DATA_ROOT", str(tmp_path / "data"))
    return pending_mod.PendingQueue()


# ---------------------------------------------------------------------------
# 1. Kuyruk
# ---------------------------------------------------------------------------


def test_queue_single_root_and_roundtrip(queue, tmp_path):
    item_id = queue.add(
        "tool_permission", "Bash: rm -f x", detail="{}", risk="high",
        source="claude-cli", payload={"tool_name": "Bash"},
    )
    # Tek kök: dosya <veri kökü>/pending altında, başka hiçbir yerde değil.
    assert queue.root == tmp_path / "data" / "pending"
    assert queue.path_for(item_id).is_file()

    rows = queue.list()
    assert [r["id"] for r in rows] == [item_id]
    assert rows[0]["status"] == "pending" and rows[0]["risk"] == "high"

    out = queue.resolve(item_id, "approve", note="tamam")
    assert out["status"] == "approved" and out["decision"] == "approve"
    # Çözülmüş kayıt SİLİNMEZ; yalnız bekleyenler listesinden düşer.
    assert queue.list() == []
    assert queue.path_for(item_id).is_file()
    assert [r["id"] for r in queue.list(status=None)] == [item_id]


def test_queue_root_argument_does_not_split_the_queue(tmp_path):
    a = pending_mod.PendingQueue(tmp_path / "data")
    b = pending_mod.PendingQueue(tmp_path / "data" / "pending")
    assert a.root == b.root


def test_queue_kind_filter_and_bad_decision(queue):
    queue.add("tool_permission", "a")
    queue.add("rule_candidate", "b")
    assert [r["kind"] for r in queue.list("rule_candidate")] == ["rule_candidate"]
    with pytest.raises(ValueError):
        queue.resolve("yok", "belki")


def test_queue_wait_returns_decision_and_expires(queue, monkeypatch):
    monkeypatch.setattr(pending_mod, "POLL_INTERVAL_S", 0.01)
    item_id = queue.add("tool_permission", "Bash: ls")

    def approve_later():
        time.sleep(0.05)
        queue.resolve(item_id, "approve")

    threading.Thread(target=approve_later, daemon=True).start()
    record = queue.wait(item_id, timeout_s=3.0)
    assert record and record["status"] == "approved"

    other = queue.add("tool_permission", "Bash: rm")
    assert queue.wait(other, timeout_s=0.05) is None
    assert queue.get(other)["status"] == "expired"


def test_queue_emits_pending_changed(queue):
    seen = []
    bus.pending_changed.connect(seen.append)
    try:
        item_id = queue.add("tool_permission", "Bash: ls")
        queue.resolve(item_id, "reject", note="hayır")
    finally:
        bus.pending_changed.disconnect(seen.append)
    assert [e["action"] for e in seen] == ["added", "resolved"]
    assert seen[-1]["item"]["status"] == "rejected"


def test_watcher_announces_out_of_process_writes(queue, monkeypatch):
    """Yazan taraf ayrı süreç: kuyruğu yoklayan habercisi olay yayar."""
    watcher = pending_mod.PendingWatcher(queue)
    watcher.start()
    try:
        item_id = queue.add("tool_permission", "Bash: ls")
        # `add` kendi sinyalini zaten yaydı; haberci aynı kaydı TEKRAR yaymaz.
        first = watcher.scan_once()
        assert [e["action"] for e in first] == ["added"]
        assert watcher.scan_once() == []
        queue.resolve(item_id, "approve")
        assert [e["action"] for e in watcher.scan_once()] == ["resolved"]
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# 2. MCP izin sunucusu
# ---------------------------------------------------------------------------


def test_risk_bands():
    assert ps.risk_for_tool("Bash") == "high"
    assert ps.risk_for_tool("Write") == ps.risk_for_tool("Edit") == "medium"
    for name in ("Read", "Glob", "Grep", "WebSearch", "WebFetch"):
        assert ps.risk_for_tool(name) == "low"
    # Bilinmeyen araç sessizce "low" sayılmaz.
    assert ps.risk_for_tool("mcp__baska__sey") == "medium"


def test_handshake_and_tools_list(queue):
    init = ps.handle_message({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                              "params": {"protocolVersion": "2025-11-25"}})
    assert init["result"]["serverInfo"]["name"] == "entropy"
    assert init["result"]["protocolVersion"] == ps.PROTOCOL_VERSION
    # Bildirime yanıt YASAK.
    assert ps.handle_message({"jsonrpc": "2.0",
                              "method": "notifications/initialized"}) is None
    tools = ps.handle_message({"jsonrpc": "2.0", "id": 1,
                               "method": "tools/list"})["result"]["tools"]
    assert [t["name"] for t in tools] == [ps.TOOL_NAME]
    assert ps.PERMISSION_TOOL == "mcp__entropy__approve"


def _call(decision_thread, queue, tool_input, timeout_s=3.0):
    message = {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": ps.TOOL_NAME, "arguments": {
            "tool_name": "Bash", "input": tool_input, "tool_use_id": "toolu_1"}},
    }
    threading.Thread(target=decision_thread, daemon=True).start()
    response = ps.handle_message(message, queue=queue, timeout_s=timeout_s)
    return json.loads(response["result"]["content"][0]["text"]), response


def test_tools_call_allow_returns_measured_schema(queue, monkeypatch):
    monkeypatch.setattr(pending_mod, "POLL_INTERVAL_S", 0.01)
    tool_input = {"command": "rm -f x.txt", "description": "sil"}

    def approve():
        for _ in range(200):
            rows = queue.list("tool_permission")
            if rows:
                queue.resolve(rows[0]["id"], "approve")
                return
            time.sleep(0.01)

    decision, response = _call(approve, queue, tool_input)
    assert decision == {"behavior": "allow", "updatedInput": tool_input}
    assert response["result"]["isError"] is False
    # Ölçülen biçim TEK metin parçasıdır ve başka alan taşımaz: canlı S2'de
    # `structuredContent` eklenince CLI "invalid result" verip kararı hiç
    # okumadı (komut koşmadı, ret de `permission_denials`a düşmedi).
    assert "structuredContent" not in response["result"]
    assert len(response["result"]["content"]) == 1
    assert response["result"]["content"][0]["type"] == "text"
    # Kart gerçekten doğdu ve riski yüksek bantta.
    row = queue.list(status=None)[0]
    assert row["risk"] == "high" and row["payload"]["tool_use_id"] == "toolu_1"
    assert "rm -f x.txt" in row["title"]


def test_tools_call_deny_carries_note_to_the_model(queue, monkeypatch):
    monkeypatch.setattr(pending_mod, "POLL_INTERVAL_S", 0.01)

    def reject():
        for _ in range(200):
            rows = queue.list("tool_permission")
            if rows:
                queue.resolve(rows[0]["id"], "reject", note="bu komutu istemiyorum")
                return
            time.sleep(0.01)

    decision, _ = _call(reject, queue, {"command": "rm -rf /"})
    assert decision == {"behavior": "deny", "message": "bu komutu istemiyorum"}


def test_tools_call_timeout_denies_and_marks_expired(queue, monkeypatch):
    monkeypatch.setattr(pending_mod, "POLL_INTERVAL_S", 0.01)
    response = ps.handle_message(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": ps.TOOL_NAME,
                    "arguments": {"tool_name": "Bash", "input": {"command": "ls"},
                                  "tool_use_id": "toolu_2"}}},
        queue=queue, timeout_s=0.05,
    )
    decision = json.loads(response["result"]["content"][0]["text"])
    assert decision["behavior"] == "deny"
    assert decision["message"] == ps.DENY_TIMEOUT_MESSAGE
    assert queue.list(status=None)[0]["status"] == "expired"


def test_same_tool_use_id_is_not_asked_twice(queue, monkeypatch):
    monkeypatch.setattr(pending_mod, "POLL_INTERVAL_S", 0.01)
    cache = {}
    args = {"tool_name": "Bash", "input": {"command": "ls"}, "tool_use_id": "toolu_3"}

    def approve():
        for _ in range(200):
            rows = queue.list("tool_permission")
            if rows:
                queue.resolve(rows[0]["id"], "approve")
                return
            time.sleep(0.01)

    threading.Thread(target=approve, daemon=True).start()
    first = ps.decide(args, queue=queue, timeout_s=3.0, cache=cache)
    second = ps.decide(args, queue=queue, timeout_s=0.01, cache=cache)
    assert first["behavior"] == second["behavior"] == "allow"
    assert len(queue.list(status=None)) == 1


def test_serve_over_ndjson_stream(queue):
    """`serve()` satır satır JSON-RPC konuşur (Content-Length yok)."""
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
    ]
    out = StringIO()
    ps.serve(StringIO("\n".join(lines) + "\n"), out, queue=queue)
    responses = [json.loads(line) for line in out.getvalue().splitlines() if line]
    assert [r["id"] for r in responses] == [0, 1]


def test_real_subprocess_handshake_and_decision(tmp_path):
    """
    GERÇEK alt süreç: giriş noktası (`permission_mcp_main`) canlı el sıkışır,
    izin isteğini diske yazar ve ana sürecin kararını okur. Model çağrısı yok.
    """
    data_root = tmp_path / "data"
    env = dict(os.environ)
    env["ENTROPY_DATA_ROOT"] = str(data_root)
    env["ENTROPY_PENDING_NO_BUS"] = "1"
    src = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "entropy.core.permission_mcp_main"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env, bufsize=1,
    )
    q = pending_mod.PendingQueue(data_root)
    try:
        proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}) + "\n")
        proc.stdin.flush()
        assert json.loads(proc.stdout.readline())["result"]["serverInfo"]["name"] == "entropy"

        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": ps.TOOL_NAME, "arguments": {
                "tool_name": "Bash", "input": {"command": "echo canli"},
                "tool_use_id": "toolu_live"}}}) + "\n")
        proc.stdin.flush()

        deadline = time.time() + 20
        while time.time() < deadline:
            rows = q.list("tool_permission")
            if rows:
                q.resolve(rows[0]["id"], "approve")
                break
            time.sleep(0.05)
        else:
            pytest.fail("İzin isteği kuyruğa hiç düşmedi")

        decision = json.loads(json.loads(proc.stdout.readline())
                              ["result"]["content"][0]["text"])
        assert decision == {"behavior": "allow",
                            "updatedInput": {"command": "echo canli"}}
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


def test_mcp_config_payload_is_self_contained(queue, tmp_path):
    payload = ps.mcp_config_payload(timeout_s=60)
    server = payload["mcpServers"]["entropy"]
    assert server["type"] == "stdio" and server["command"]
    # Çocuk süreç kökü ve Qt yasağını ortamdan devralır.
    assert server["env"]["ENTROPY_DATA_ROOT"]
    assert server["env"]["ENTROPY_PENDING_NO_BUS"] == "1"
    assert server["env"][ps.TIMEOUT_ENV] == "60"
    path = ps.write_mcp_config(tmp_path / "mcp.json", timeout_s=60)
    assert json.loads(path.read_text(encoding="utf-8")) == payload


# ---------------------------------------------------------------------------
# 3. Köprü argv'si
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 191919
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


def _result_lines(denials=None):
    return [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s-14b",
                    "model": "claude-opus-5", "tools": []}) + "\n",
        json.dumps({"type": "result", "subtype": "success", "result": "bitti",
                    "session_id": "s-14b", "is_error": False,
                    "permission_denials": denials or [],
                    "usage": {"input_tokens": 10, "output_tokens": 2}}) + "\n",
    ]


@pytest.fixture()
def bridge_env(tmp_path, monkeypatch):
    module = sys.modules["entropy.core.config"]
    cfg = module.config
    monkeypatch.setenv("ENTROPY_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(cfg, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    monkeypatch.setattr(cfg, "claude_isolated", True, raising=False)
    monkeypatch.setattr(cfg, "approvals_enabled", True, raising=False)
    monkeypatch.setattr(module, "save_chat_history", lambda h: None)
    monkeypatch.setattr(type(cfg), "save_settings", lambda self: None)
    return cfg


def test_approval_argv_flags_on_and_off(bridge_env, monkeypatch):
    b = ClaudeCodeBridge()
    on = b.approval_argv()
    assert on["permission_tool"] == ps.PERMISSION_TOOL
    assert on["mcp_config"] and Path(on["mcp_config"]).is_file()
    assert on["skip_permissions"] is False

    monkeypatch.setattr(bridge_env, "approvals_enabled", False, raising=False)
    off = b.approval_argv()
    assert off == {"mcp_config": None, "permission_tool": None,
                   "skip_permissions": True}


def test_build_command_permission_flags_are_exclusive(bridge_env, tmp_path):
    b = ClaudeCodeBridge()
    cmd = b.build_command("selam", mcp_config=str(tmp_path / "m.json"),
                          permission_tool=ps.PERMISSION_TOOL,
                          skip_permissions=True)
    assert "--permission-prompt-tool" in cmd
    assert cmd[cmd.index("--permission-prompt-tool") + 1] == ps.PERMISSION_TOOL
    assert "--dangerously-skip-permissions" not in cmd
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--mcp-config") + 1] == str(tmp_path / "m.json")


def test_chat_turn_argv_has_permission_tool(bridge_env, tmp_path, monkeypatch):
    captured = {}

    def fake_popen(cmd, **kw):
        captured["cmd"] = list(cmd)
        return _FakeProc(_result_lines())

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    b._execute_prompt_worker("merhaba dünya")
    cmd = captured["cmd"]
    assert "--permission-prompt-tool" in cmd and "--mcp-config" in cmd
    assert "--dangerously-skip-permissions" not in cmd


def test_real_background_task_argv_respects_the_switch(bridge_env, tmp_path, monkeypatch):
    """GERÇEK `send_background_task_async` yolu (yalnız Popen taklit)."""
    captured = {}
    done = threading.Event()

    def fake_popen(cmd, **kw):
        captured.setdefault("cmds", []).append(list(cmd))
        return _FakeProc(_result_lines())

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path

    b.send_background_task_async(
        "t-1", "Onay testi", "kısa iş", project_path=str(tmp_path),
        save_report=False, on_result=lambda *_: done.set(),
    )
    assert done.wait(20), "arka plan görevi bitmedi"
    cmd = captured["cmds"][-1]
    assert "--permission-prompt-tool" in cmd
    assert "--dangerously-skip-permissions" not in cmd

    # Anahtar kapalıyken eski davranış: izin atlama geri gelir.
    monkeypatch.setattr(bridge_env, "approvals_enabled", False, raising=False)
    done.clear()
    b.send_background_task_async(
        "t-2", "Onay testi 2", "kısa iş", project_path=str(tmp_path),
        save_report=False, on_result=lambda *_: done.set(),
    )
    assert done.wait(20), "ikinci arka plan görevi bitmedi"
    cmd = captured["cmds"][-1]
    assert "--dangerously-skip-permissions" in cmd
    assert "--permission-prompt-tool" not in cmd


# ---------------------------------------------------------------------------
# 4. Akıştaki izin reddi
# ---------------------------------------------------------------------------


def test_permission_denial_becomes_an_event_and_a_chat_line(bridge_env):
    b = ClaudeCodeBridge()
    events, lines = [], []
    bus.tool_permission_event.connect(events.append)
    bus.terminal_output_received.connect(lines.append)
    try:
        b.consume_stream(iter(_result_lines(denials=[{
            "tool_name": "Bash",
            "tool_use_id": "toolu_9",
            "tool_input": {"command": "rm -f spike.txt"},
        }])))
    finally:
        bus.tool_permission_event.disconnect(events.append)
        bus.terminal_output_received.disconnect(lines.append)
    assert [e["phase"] for e in events] == ["denied"]
    assert events[0]["tool"] == "Bash" and "rm -f spike.txt" in events[0]["input_summary"]
    assert any("İZİN REDDEDİLDİ" in line for line in lines)


def test_pending_request_prints_a_chat_line(bridge_env):
    """İzin isteği akışta görünmez; tek haberci kuyruktur."""
    b = ClaudeCodeBridge()
    lines = []
    bus.terminal_output_received.connect(lines.append)
    try:
        pending_mod.PendingQueue().add(
            "tool_permission", "Bash: ls -la", risk="high",
            payload={"tool_name": "Bash", "tool_use_id": "toolu_x"},
        )
    finally:
        bus.terminal_output_received.disconnect(lines.append)
    assert any("İZİN İSTENDİ" in line and "ls -la" in line for line in lines)
    assert b is not None


# ---------------------------------------------------------------------------
# 5. "onaylıyorum"
# ---------------------------------------------------------------------------


def test_approval_message_resolves_single_item_without_cli(queue, bridge_env, monkeypatch):
    from entropy.core import response_hooks

    calls = []
    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen",
                        lambda *a, **k: calls.append(a) or _FakeProc([]))
    item_id = queue.add("tool_permission", "Bash: rm -f x")
    line = response_hooks.resolve_approval_message("onaylıyorum", queue)
    assert line == "✔ onaylandı: Bash: rm -f x"
    assert queue.get(item_id)["status"] == "approved"
    assert calls == [], "onay turu CLI'ya GİTMEMELİ"


def test_approval_message_variants_and_reject(queue):
    from entropy.core import response_hooks

    assert response_hooks.parse_approval_command("Onaylıyorum") == ("approve", "")
    assert response_hooks.parse_approval_command("REDDET") == ("reject", "")
    assert response_hooks.parse_approval_command("bunu nasıl yaparız") is None

    item_id = queue.add("tool_permission", "Bash: rm -rf /")
    assert response_hooks.resolve_approval_message("reddet", queue).startswith("⛔")
    assert queue.get(item_id)["status"] == "rejected"


def test_approval_message_without_queue_items_is_one_line(queue):
    from entropy.core import response_hooks

    assert response_hooks.resolve_approval_message("onaylıyorum", queue) == \
        "Bekleyen onay yok."


def test_approval_message_asks_which_one_when_ambiguous(queue):
    from entropy.core import response_hooks

    first = queue.add("tool_permission", "Bash: ls")
    queue.add("tool_permission", "Bash: pwd")
    answer = response_hooks.resolve_approval_message("onaylıyorum", queue)
    assert "2 onay bekliyor" in answer and first in answer
    assert queue.get(first)["status"] == "pending"
    # Kimlik verilirse tam o iş çözülür.
    assert response_hooks.resolve_approval_message(f"onayla {first}", queue).startswith("✔")
    assert queue.get(first)["status"] == "approved"


def test_bridge_short_circuits_approval_turn(queue, bridge_env, tmp_path, monkeypatch):
    popen_calls = []
    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen",
                        lambda *a, **k: popen_calls.append(a) or _FakeProc([]))
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    queue.add("tool_permission", "Bash: ls")
    answers = []
    bus.agent_turn_completed.connect(answers.append)
    try:
        b._execute_prompt_worker("onaylıyorum")
    finally:
        bus.agent_turn_completed.disconnect(answers.append)
    assert popen_calls == []
    assert answers and answers[-1].startswith("✔ onaylandı")


# ---------------------------------------------------------------------------
# 6. Desk köprüsü
# ---------------------------------------------------------------------------


def test_desk_requests_appear_as_desk_change(queue, tmp_path, monkeypatch):
    from entropy.agents import desk_admin

    module = sys.modules["entropy.core.config"]
    monkeypatch.setattr(module.config, "obsidian_vault_path", tmp_path / "Vault",
                        raising=False)
    record = desk_admin.queue_request("office_create",
                                      {"office": "deneme", "purpose": "test"})
    rows = queue.list("desk_change")
    assert [r["id"] for r in rows] == [record["id"]]
    assert rows[0]["kind"] == "desk_change" and rows[0]["title"]
    # Dosya TAŞINMAZ: Desk isteği kendi klasöründe kalır.
    assert not (queue.root / f"{record['id']}.json").exists()

    applied = {}
    monkeypatch.setattr(desk_admin, "apply_pending",
                        lambda rid, *a, **k: applied.setdefault("id", rid))
    out = queue.resolve(record["id"], "approve")
    assert applied["id"] == record["id"] and out["status"] == "approved"


# ---------------------------------------------------------------------------
# 7. Paket eşlemesi
# ---------------------------------------------------------------------------


def test_spec_carries_the_new_modules():
    spec = (Path(__file__).resolve().parents[2] / "EntropyAI.spec").read_text(
        encoding="utf-8")
    for module in ("entropy.core.pending", "entropy.core.permission_server",
                   "entropy.core.permission_mcp_main"):
        assert f"'{module}'" in spec, module
    for module in ("entropy.ui.widgets.pending_card",
                   "entropy.ui.widgets.nav_strip",
                   "entropy.ui.widgets.agent_runs_panel",
                   "entropy.ui.widgets.agent_stream_line",
                   "entropy.brain.agent_memory_writer",
                   "entropy.brain.artifact_archive"):
        assert f"'{module}'" in spec, module


# ---------------------------------------------------------------------------
# 8. Onay açıkken izin KİPİ (canlı S2'nin düşme sebebi)
# ---------------------------------------------------------------------------


def test_permission_tool_forces_default_mode(bridge_env, tmp_path):
    """
    Onay aracı verildiğinde kip `default` olmalı.

    Canlı S2'nin ilk koşumu `--permission-mode acceptEdits` ile gitti: CLI
    dosya yazımını izin kancasından ONCE otomatik onayladı, kuyruga hic oge
    dusmedi (`queued_item: null`).
    """
    b = ClaudeCodeBridge()
    cmd = b.build_command("selam", mode="accept-edits",
                          mcp_config=str(tmp_path / "m.json"),
                          permission_tool=ps.PERMISSION_TOOL)
    assert cmd[cmd.index("--permission-mode") + 1] == "default"

    # Onay aracı yokken eski davranış aynen sürer.
    plain = b.build_command("selam", mode="accept-edits")
    assert plain[plain.index("--permission-mode") + 1] == "acceptEdits"


def test_chat_turn_uses_default_permission_mode(bridge_env, tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "entropy.core.claude_bridge.subprocess.Popen",
        lambda cmd, **kw: (captured.__setitem__("cmd", list(cmd)),
                           _FakeProc(_result_lines()))[1],
    )
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    b._execute_prompt_worker("merhaba dünya")
    cmd = captured["cmd"]
    assert cmd[cmd.index("--permission-mode") + 1] == "default"
    # Salt okunur araç seti korunur.
    tools = cmd[cmd.index("--tools") + 1].split(",")
    assert "Write" not in tools and "Bash" not in tools


def test_isolation_flags_travel_together(bridge_env, tmp_path):
    """İzolasyon üçlüsü: kullanıcı ayarları + kullanıcı MCP sunucuları dışarıda."""
    b = ClaudeCodeBridge()
    cmd = b.build_command("selam", mcp_config=str(tmp_path / "m.json"),
                          permission_tool=ps.PERMISSION_TOOL)
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert cmd[cmd.index("--mcp-config") + 1] == str(tmp_path / "m.json")


# ---------------------------------------------------------------------------
# 9. CLI keşfi
# ---------------------------------------------------------------------------


def test_executable_discovery_order_and_diagnostic(tmp_path, monkeypatch):
    """Sahte dosya ağacıyla yedek sırası + bulunamayınca teşhis satırı."""
    module = sys.modules["entropy.core.config"]
    cfg = module.config
    home = tmp_path / "home"
    appdata = tmp_path / "AppData" / "Roaming"
    local = tmp_path / "AppData" / "Local"
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr("entropy.core.claude_bridge.shutil.which", lambda _n: None)
    monkeypatch.setattr(cfg, "claude_path", "", raising=False)
    b = ClaudeCodeBridge()

    def touch(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        return path

    # Hiçbir aday yokken: teşhis + çıplak ad.
    lines = []
    bus.terminal_output_received.connect(lines.append)
    try:
        assert b.find_claude_executable() == "claude"
    finally:
        bus.terminal_output_received.disconnect(lines.append)
    assert any("npm install -g" in line for line in lines)

    # Editör eklentisi: iki sürüm varsa EN YÜKSEĞİ.
    ext = home / ".vscode" / "extensions"
    touch(ext / "anthropic.claude-code-2.1.9-win32-x64" / "resources"
          / "native-binary" / "claude.exe")
    high = touch(ext / "anthropic.claude-code-2.1.268-win32-x64" / "resources"
                 / "native-binary" / "claude.exe")
    b2 = ClaudeCodeBridge()
    assert b2.find_claude_executable() == str(high)

    # `~/.local/bin` eklenti yolunun önünde.
    localbin = touch(home / ".local" / "bin" / "claude.exe")
    assert ClaudeCodeBridge().find_claude_executable() == str(localbin)

    # npm shim hepsinin önünde.
    shim = touch(appdata / "npm" / "claude.cmd")
    assert ClaudeCodeBridge().find_claude_executable() == str(shim)

    # `config.claude_path` en yüksek öncelik.
    manual = touch(tmp_path / "elle" / "claude.exe")
    monkeypatch.setattr(cfg, "claude_path", str(manual), raising=False)
    assert ClaudeCodeBridge().find_claude_executable() == str(manual)
