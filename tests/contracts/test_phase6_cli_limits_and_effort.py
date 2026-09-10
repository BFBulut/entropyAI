"""
Faz 6: komut satırı sınırı, sistem istemi taşıma, efor ayarı ve sağlayıcı
değişiminde kilit açma.

Kullanıcının gördüğü üç kusuru doğrudan sürer:
  1. Claude'a geçince "The command line is too long" + kırmızı çekirdek + kilitli
     sohbet. Burada Popen taklidi WinError 206'yı taklit eder; köprünün turu
     hata metniyle KAPATMASI ve ikinci gönderimin çalışması beklenir.
  2. Modellerde efor ayarı yok: `effort_levels()` / `selected_effort` /
     `set_effort()` sözleşmesi ve argv'deki `--effort`.
  3. Sağlayıcı değişiminde süren isteğin iptali ve kilidin serbest kalması.

Sahte köprüyle değil GERÇEK yoldan sürülür: `subprocess.Popen` taklit edilir,
`_execute_prompt_worker` gerçek argv'yi kurar.
"""

import json
import threading
from pathlib import Path

import pytest

from entropy.core.agy_bridge import AGY_EFFORT_LEVELS, AgyProcessBridge
from entropy.core.claude_bridge import (
    ARGV_TOTAL_SAFE_LIMIT,
    CLAUDE_EFFORT_LEVELS,
    SYSTEM_CONTEXT_BLOCK_HEADER,
    SYSTEM_PROMPT_ARGV_LIMIT,
    SYSTEM_PROMPT_FILE_FLAG,
    ClaudeCodeBridge,
    argv_length,
    argv_too_long,
)
from entropy.core.event_bus import bus
from entropy.core.provider import ProviderBridge, effort_command, switch_provider


# ---------------------------------------------------------------------------
# Sahte süreç (gerçek Popen'ın yerine geçer)
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 4242
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


def _ok_lines(text="Tamam."):
    return [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s-1"}) + "\n",
        json.dumps(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
            }
        )
        + "\n",
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "result": text,
                "session_id": "s-1",
                "is_error": False,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        )
        + "\n",
    ]


# ---------------------------------------------------------------------------
# 1) Argv sınırı ve sistem istemi taşıma
# ---------------------------------------------------------------------------


def test_long_system_prompt_never_enters_argv(tmp_path):
    b = ClaudeCodeBridge()
    big = "B" * (SYSTEM_PROMPT_ARGV_LIMIT + 5_000)
    cmd = b.build_command("selam", append_system_prompt=big)

    assert "--append-system-prompt" not in cmd, "uzun sistem istemi hâlâ argv'de"
    path = cmd[cmd.index(SYSTEM_PROMPT_FILE_FLAG) + 1]
    assert Path(path).read_text(encoding="utf-8") == big
    assert not argv_too_long(cmd)
    b.cleanup_system_prompt_file(path)
    assert not Path(path).exists()


def test_short_system_prompt_stays_inline():
    b = ClaudeCodeBridge()
    cmd = b.build_command("selam", append_system_prompt="kısa bağlam")
    assert cmd[cmd.index("--append-system-prompt") + 1] == "kısa bağlam"
    assert SYSTEM_PROMPT_FILE_FLAG not in cmd


def test_total_argv_over_limit_falls_back_even_with_many_dirs():
    b = ClaudeCodeBridge()
    # Tek tek sınırın altında ama TOPLAMDA sınırı aşan bir argv: sistem istemi
    # eşiğin altında, --add-dir yolları uzun.
    dirs = [f"C:/very/long/path/segment/number/{i:04d}/" + "d" * 200 for i in range(120)]
    cmd = b.build_command(
        "selam",
        append_system_prompt="x" * (SYSTEM_PROMPT_ARGV_LIMIT - 10),
        extra_dirs=dirs,
    )
    assert argv_length(cmd) > ARGV_TOTAL_SAFE_LIMIT
    b._apply_stdin_prompt(cmd)
    # enforce_argv_limit sistem istemini dosyaya taşımış olmalı.
    assert "--append-system-prompt" not in cmd
    b.cleanup_system_prompt_file(b.system_prompt_file_in(cmd))


def test_stdin_fallback_used_when_file_flag_unsupported(monkeypatch):
    # Bayrağı tanımayan bir CLI sürümü: sistem istemi kullanıcı mesajının başına
    # [SİSTEM BAĞLAMI] bloğu olarak gömülür ve argv'de metin kalmaz.
    monkeypatch.setattr(
        "entropy.core.claude_bridge.CLAUDE_SUPPORTS_SYSTEM_PROMPT_FILE", False
    )
    b = ClaudeCodeBridge()
    big = "S" * (ARGV_TOTAL_SAFE_LIMIT + 2_000)
    cmd = b.build_command("kullanıcı mesajı", append_system_prompt=big)
    assert cmd[cmd.index("--append-system-prompt") + 1] == big

    payload = b._apply_stdin_prompt(cmd)
    assert "--append-system-prompt" not in cmd
    assert SYSTEM_PROMPT_FILE_FLAG not in cmd
    assert cmd[cmd.index("-p") + 1] == ""
    assert not argv_too_long(cmd)

    obj = json.loads(payload)
    content = obj["message"]["content"]
    assert content.startswith(SYSTEM_CONTEXT_BLOCK_HEADER)
    assert big in content
    assert content.rstrip().endswith("kullanıcı mesajı")


def test_argv_length_counts_quotes_and_spaces():
    assert argv_length(["ab", "c"]) == (2 + 3) + (1 + 3)
    assert not argv_too_long(["x"])


# ---------------------------------------------------------------------------
# 2) Hata yolunda sohbet kilidi açılır (WinError 206)
# ---------------------------------------------------------------------------


def test_command_line_too_long_unlocks_chat_and_second_send_works(tmp_path, monkeypatch):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path

    completed = []
    states = []
    bus.agent_turn_completed.connect(completed.append)
    bus.core_state_changed.connect(states.append)

    calls = {"n": 0}

    def fake_popen(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            err = OSError("[WinError 206] The filename or extension is too long")
            err.winerror = 206
            raise err
        return _FakeProc(_ok_lines("ikinci tur çalıştı"))

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    monkeypatch.setattr(b, "get_cognitive_context", lambda *a, **k: "")
    monkeypatch.setattr(b, "get_mini_cognitive_context", lambda *a, **k: "")

    try:
        b._execute_prompt_worker("ilk mesaj", project_path=str(tmp_path))

        # Kilit açıldı: köprü boşta, çekirdek idle, tur hata metniyle kapandı.
        assert b.is_running is False
        assert states and states[-1] == "idle"
        assert completed and "komut satırı" in completed[-1].lower()

        # İkinci gönderim gerçekten çalışır.
        b._execute_prompt_worker("ikinci mesaj", project_path=str(tmp_path))
        assert completed[-1] == "ikinci tur çalıştı"
        assert calls["n"] == 2
    finally:
        bus.agent_turn_completed.disconnect(completed.append)
        bus.core_state_changed.disconnect(states.append)


def test_send_prompt_async_releases_running_flag_after_failure(tmp_path, monkeypatch):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    started = threading.Event()

    def fake_popen(cmd, **kwargs):
        started.set()
        err = OSError("[WinError 206] The filename or extension is too long")
        err.winerror = 206
        raise err

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    monkeypatch.setattr(b, "get_cognitive_context", lambda *a, **k: "")

    # NOT: işçi ayrı bir iş parçacığında koştuğu için bus sinyalleri Qt olay
    # döngüsü olmadan teslim edilmez; kilit doğrudan `is_running` üzerinden
    # ölçülür (arayüzün girişi serbest bırakma koşulu da budur).
    b.send_prompt_async("bir şey", project_path=str(tmp_path))
    assert started.wait(10), "işçi hiç başlamadı"
    for _ in range(200):
        if not b.is_running:
            break
        threading.Event().wait(0.05)
    assert b.is_running is False, "hata yolunda köprü meşgul kaldı (sohbet kilitlenirdi)"

    # İkinci gönderim sıraya değil doğrudan yürütmeye gider.
    started.clear()
    b.send_prompt_async("ikinci şey", project_path=str(tmp_path))
    assert started.wait(10), "ikinci gönderim çalıştırılmadı"


def test_describe_launch_error_explains_winerror_206():
    err = OSError("[WinError 206] The filename or extension is too long")
    err.winerror = 206
    msg = ClaudeCodeBridge.describe_launch_error(err)
    assert "komut satırı" in msg.lower()
    assert "tekrar" in msg.lower()


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """
    Efor ayarı diske YAZILIR (kalıcılık sözleşmenin parçası); yazımın kullanıcının
    gerçek settings.json'ına düşmemesi için dosya yolu ve sözlük yalıtılır.
    """
    import sys

    import entropy.core.config  # noqa: F401
    from entropy.core.config import config

    # entropy.core paketi 'config' adını config NESNESİNE bağlıyor; modül
    # nesnesi yalnızca sys.modules üzerinden alınabilir (köprülerdeki aynı tuzak).
    cfg_mod = sys.modules["entropy.core.config"]
    monkeypatch.setattr(cfg_mod, "SETTINGS_FILE", tmp_path / "settings.json", raising=False)
    original = dict(getattr(config, "provider_effort", {}) or {})
    config.provider_effort = {"agy": "high", "claude": "high"}
    yield config
    config.provider_effort = original


# ---------------------------------------------------------------------------
# 3) Efor sözleşmesi
# ---------------------------------------------------------------------------


def test_effort_levels_match_each_cli():
    # `claude --help`: low, medium, high, xhigh, max (modelden bağımsız).
    assert ClaudeCodeBridge().effort_levels() == ["low", "medium", "high", "xhigh", "max"]
    # agy'de efor MODEL ADININ SON EKİDİR; seviye kümesi seçili modele bağlıdır
    # (`agy models`: pro -> low/high, flash -> low/medium/high).
    b = AgyProcessBridge()
    b.selected_model = "gemini-3.1-pro-high"
    assert b.effort_levels() == ["low", "high"]
    b.selected_model = "gemini-3.8-flash-medium"
    assert b.effort_levels() == ["low", "medium", "high"]
    assert CLAUDE_EFFORT_LEVELS[:3] == AGY_EFFORT_LEVELS


def test_claude_argv_carries_selected_effort_and_prompt_override():
    b = ClaudeCodeBridge()
    b.selected_effort = "max"
    cmd = b.build_command("selam")
    assert cmd[cmd.index("--effort") + 1] == "max"

    # Prompt içindeki tek seferlik yazım kalıcı ayarı ezer.
    cmd = b.build_command("kodu incele /effort low")
    assert cmd[cmd.index("--effort") + 1] == "low"


def test_set_effort_persists_and_rejects_invalid_level(isolated_settings):
    config = isolated_settings

    b = ClaudeCodeBridge()
    b.set_effort("xhigh")
    assert b.selected_effort == "xhigh"
    assert config.provider_effort["claude"] == "xhigh"

    with pytest.raises(ValueError):
        b.set_effort("ultra")
    # agy claude'un kümesini kabul etmemeli: geçersiz bayrak turu hiç başlatmaz.
    with pytest.raises(ValueError):
        AgyProcessBridge().set_effort("xhigh")


def test_bridges_expose_effort_contract_for_ui():
    for b in (ClaudeCodeBridge(), AgyProcessBridge()):
        assert isinstance(b, ProviderBridge)
        assert b.selected_effort in b.effort_levels()


def test_effort_command_parsing_uses_bridge_levels():
    claude = ClaudeCodeBridge()
    agy = AgyProcessBridge()
    assert effort_command("/effort", claude) == {"action": "show"}
    assert effort_command("/effort MAX", claude) == {"action": "set", "effort": "max"}
    assert effort_command("/effort max", agy)["action"] == "error"
    assert effort_command("normal mesaj", claude) is None
    # Prompt içinde geçen /effort kalıcı komut DEĞİLDİR; köprü onu o turluk okur.
    assert effort_command("kodu incele /effort low", claude) is None


def test_slash_effort_is_local_and_sets_bridge(isolated_settings):
    from entropy.core import slash_commands

    b = ClaudeCodeBridge()
    out = slash_commands.try_handle_local_command("/effort", b)
    assert out is not None and "high" in out

    out = slash_commands.try_handle_local_command("/effort xhigh", b)
    assert out is not None and "xhigh" in out
    assert b.selected_effort == "xhigh"

    out = slash_commands.try_handle_local_command("/effort ultra", b)
    assert "Bilinmeyen efor" in out


# ---------------------------------------------------------------------------
# 4) Sağlayıcı değişimi: iptal, kilit, ilk mesaj
# ---------------------------------------------------------------------------


class _Cfg:
    provider = "agy"
    provider_models = {"agy": "gemini-3.1-pro-high", "claude": "claude-opus-5"}
    provider_effort = {"agy": "high", "claude": "high"}
    selected_model = "gemini-3.1-pro-high"

    def save_settings(self):
        pass


def test_switch_provider_cancels_running_request_and_clears_lock():
    cfg = _Cfg()
    cfg.provider = "agy"
    old = AgyProcessBridge()
    old._is_running = True
    killed = []
    old.terminate_current_process = lambda: killed.append(True)
    old.shutdown = lambda timeout=3.0: {}

    states = []
    bus.core_state_changed.connect(states.append)
    try:
        new = switch_provider(old, "claude", cfg=cfg)
    finally:
        bus.core_state_changed.disconnect(states.append)

    assert killed, "süren istek iptal edilmedi"
    assert old._is_running is False, "kilit serbest bırakılmadı"
    assert states and states[-1] == "idle", "rozetler/çekirdek durumu yenilenmedi"
    assert new.provider_name == "claude"


def test_first_message_after_switch_runs(tmp_path, monkeypatch):
    cfg = _Cfg()
    cfg.provider = "agy"
    old = AgyProcessBridge()
    old._is_running = True
    old.shutdown = lambda timeout=3.0: {}

    new = switch_provider(old, "claude", cfg=cfg)
    new.active_project_dir = tmp_path

    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc(_ok_lines("değişimden sonraki ilk tur"))

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    monkeypatch.setattr(new, "get_cognitive_context", lambda *a, **k: "")

    completed = []
    bus.agent_turn_completed.connect(completed.append)
    try:
        new._execute_prompt_worker("merhaba", project_path=str(tmp_path))
    finally:
        bus.agent_turn_completed.disconnect(completed.append)

    assert completed and completed[-1] == "değişimden sonraki ilk tur"
    assert new.is_running is False
    # Yeni köprünün argv'si claude bayraklarıyla kurulmuş olmalı.
    assert "--permission-mode" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--effort") + 1] in CLAUDE_EFFORT_LEVELS
