"""
FAZ 9 — Claude izolasyonu ("Entropy Saf Kip"), model kapıları ve kart kimliği.

Hiçbir test gerçek CLI çalıştırmaz, kota harcamaz: `subprocess.Popen` taklit
edilir ve argv gerçek `build_command`dan gelir. Argv bayrakları `claude --help`
(sürüm 2.1.265) ve gizli bayraklar için canlı kontrol probuyla doğrulandı;
alıntılar `claude_bridge.py` sabitlerinin yorumlarında.
"""

import json
import threading
from pathlib import Path

import pytest

import sys

from entropy.agents.tasks import TaskBoard, TaskCard, resolve_card_model
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.claude_bridge import (
    CLAUDE_MODELS,
    REPLACE_SYSTEM_PROMPT_FILE_FLAG,
    ClaudeCodeBridge,
)
from entropy.core.config import config
from entropy.core.identity import ConversationMap
from entropy.core.task_ledger import TaskLedger

# `entropy.core` paketi 'config' adını config NESNESİNE bağlıyor; modül
# seviyesindeki yardımcılar (claude_workspace_path, is_claude_model_name, ...)
# için gerçek modül gerekiyor (köprülerdeki aynı tuzak).
config_module = sys.modules["entropy.core.config"]


# ---------------------------------------------------------------------------
# Ortak taklitler
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 990001
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


def _claude_lines(text="Bitti", session="sess-9"):
    return [
        json.dumps({"type": "system", "subtype": "init", "session_id": session}) + "\n",
        json.dumps({"type": "assistant", "message": {"role": "assistant",
                    "content": [{"type": "text", "text": text}]}}) + "\n",
        json.dumps({"type": "result", "subtype": "success", "session_id": session,
                    "usage": {"input_tokens": 10, "output_tokens": 5,
                              "cache_read_input_tokens": 1000,
                              "cache_creation_input_tokens": 100}}) + "\n",
    ]


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Gerçek `settings.json`'a dokunmayan, saf kip AÇIK bir yapılandırma."""
    monkeypatch.setattr(config_module, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(config, "claude_isolated", True)
    monkeypatch.setattr(config, "claude_workspace_dir", str(tmp_path / "workspace"))
    monkeypatch.setattr(config, "provider_models",
                        dict(config_module.DEFAULT_PROVIDER_MODELS))
    monkeypatch.setattr(config, "selected_model", "claude-opus-5")
    return tmp_path


# ---------------------------------------------------------------------------
# 9.1 — Model doğrulama, üç kapı
# ---------------------------------------------------------------------------


def test_poisoned_settings_fallback_is_validated(monkeypatch, isolated_settings):
    """OKUMA KAPISI: yedek değerin kendisi zehirliyse köprü ona düşmez."""
    monkeypatch.setattr(config, "provider_models",
                        {"agy": "gemini-3.1-pro-high", "claude": "gemini-3.1-pro-high"})
    monkeypatch.setattr(config, "selected_model", "gemini-3.1-pro-high")

    bridge = ClaudeCodeBridge()

    assert bridge.selected_model == "claude-opus-5" == CLAUDE_MODELS[0]
    cmd = bridge.build_command("merhaba")
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5"
    assert "gemini-3.1-pro-high" not in cmd


def test_set_model_rejects_foreign_name(monkeypatch, isolated_settings):
    """YAZMA KAPISI: yabancı ad ayara YAZILMAZ, seçim değişmez."""
    monkeypatch.setattr(config, "provider_models", {"agy": "gemini-3.1-pro-high",
                                                    "claude": "claude-opus-5"})
    bridge = ClaudeCodeBridge()

    assert bridge.set_model("gemini-3.1-pro-high") is False
    assert bridge.selected_model == "claude-opus-5"
    assert config.provider_models["claude"] == "claude-opus-5"

    # Geçerli ad (ve takma ad) kabul edilir.
    assert bridge.set_model("claude-sonnet-5") is True
    assert bridge.set_model("opusplan") is True
    assert config.provider_models["claude"] == "opusplan"


def test_agy_set_model_rejects_claude_only_name(monkeypatch, isolated_settings):
    monkeypatch.setattr(config, "provider_models", {"agy": "gemini-3.1-pro-high",
                                                    "claude": "claude-opus-5"})
    monkeypatch.setattr(config, "selected_model", "gemini-3.1-pro-high")
    monkeypatch.setattr(config, "available_models", ["gemini-3.1-pro-high",
                                                     "claude-sonnet-4-6"])
    bridge = AgyProcessBridge()
    assert bridge.selected_model == "gemini-3.1-pro-high"
    assert bridge.set_model("claude-opus-5") is False
    assert bridge.selected_model == "gemini-3.1-pro-high"
    # agy'nin KENDİ sunduğu claude modeli geçerlidir (canlı listeden).
    assert bridge.set_model("claude-sonnet-4-6") is True


def test_startup_repairs_poisoned_provider_models(tmp_path, monkeypatch):
    """GÖÇ KAPISI: açılışta zehirli ayar onarılır ve diske yazılır."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "provider": "claude",
        "selected_model": "gemini-3.1-pro-high",
        "provider_models": {"agy": "gemini-3.1-pro-high",
                            "claude": "gemini-3.1-pro-high"},
    }), encoding="utf-8")
    monkeypatch.setattr(config_module, "SETTINGS_FILE", settings)

    cfg = config_module.EntropyConfig()
    cfg.load_settings()

    assert cfg.provider_models["claude"] == "claude-opus-5"
    assert cfg.provider_models["agy"] == "gemini-3.1-pro-high"   # agy'ninki sağlam
    on_disk = json.loads(settings.read_text(encoding="utf-8"))
    assert on_disk["provider_models"]["claude"] == "claude-opus-5"


def test_model_name_predicates():
    assert config_module.is_claude_model_name("opus[1m]")
    assert config_module.is_claude_model_name("fable")
    assert config_module.is_claude_model_name("claude-opus-5")
    assert not config_module.is_claude_model_name("gemini-3.1-pro-high")
    assert config_module.is_agy_model_name("gemini-3.8-flash-low")
    assert config_module.is_agy_model_name("gpt-oss-120b-medium")
    assert not config_module.is_agy_model_name("claude-opus-5")


# ---------------------------------------------------------------------------
# 9.2 — Entropy Saf Kip
# ---------------------------------------------------------------------------


def test_isolated_build_command_flags(isolated_settings):
    bridge = ClaudeCodeBridge()
    cmd = bridge.build_command(
        "merhaba",
        mode="accept-edits",
        project_dir=Path(isolated_settings),
        system_prompt="Sen Entropy AI'sın.\nAraç sözleşmesi.",
    )

    # Varsayılan istem DEĞİŞTİRİLİR, eklenmez.
    assert REPLACE_SYSTEM_PROMPT_FILE_FLAG in cmd
    assert "--append-system-prompt" not in cmd
    assert "--append-system-prompt-file" not in cmd
    sp_path = Path(cmd[cmd.index(REPLACE_SYSTEM_PROMPT_FILE_FLAG) + 1])
    assert "Entropy AI" in sp_path.read_text(encoding="utf-8")

    # İzolasyon bayrakları
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--disallowedTools") + 1] == "mcp__*"
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert "--disable-slash-commands" in cmd
    assert "Read" in cmd[cmd.index("--tools") + 1]
    assert cmd[cmd.index("--fallback-model") + 1] == "claude-sonnet-5"
    assert cmd[cmd.index("--add-dir") + 1] == str(isolated_settings)

    # `--bare` ASLA: abonelik oturumunu okumaz, ANTHROPIC_API_KEY ister.
    assert "--bare" not in cmd

    # Sıra: yürütülebilir, -p, çıktı biçimi, ayrıntı, izin kipi, model.
    assert cmd[1:6] == ["-p", "merhaba", "--output-format", "stream-json", "--verbose"]
    assert cmd[6] == "--permission-mode"
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5"


def test_isolation_off_keeps_legacy_argv(isolated_settings, monkeypatch):
    monkeypatch.setattr(config, "claude_isolated", False)
    bridge = ClaudeCodeBridge()
    cmd = bridge.build_command(
        "merhaba",
        project_dir=Path(isolated_settings),
        system_prompt="Sen Entropy AI'sın.\nBağlam.",
    )
    # Değiştirme yolu kapalı: eski EKLEME yolu geri gelir.
    assert REPLACE_SYSTEM_PROMPT_FILE_FLAG not in cmd
    assert "--append-system-prompt-file" in cmd
    for flag in ("--strict-mcp-config", "--setting-sources",
                 "--disable-slash-commands", "--tools", "--fallback-model"):
        assert flag not in cmd


def test_isolated_cwd_is_outside_any_git_repo(isolated_settings):
    bridge = ClaudeCodeBridge()
    cwd = Path(bridge.run_cwd(Path(isolated_settings)))
    assert cwd.exists()
    assert not config_module.path_is_inside_git_repo(cwd)
    # Proje dizini cwd DEĞİL: erişim `--add-dir` ile verilir.
    assert cwd != Path(isolated_settings)


def test_workspace_inside_git_repo_falls_back(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    workspace = repo / "sub" / "workspace"
    monkeypatch.setattr(config, "claude_workspace_dir", str(workspace))
    resolved = config_module.claude_workspace_path()
    assert not config_module.path_is_inside_git_repo(resolved)


def test_tools_by_permission_mode():
    assert "Write" not in ClaudeCodeBridge.tools_for("plan")
    assert "Write" in ClaudeCodeBridge.tools_for("accept-edits")
    assert "Bash" in ClaudeCodeBridge.tools_for("plan", needs_write=True)


# ---------------------------------------------------------------------------
# 9.4 — Arka plan kartlarına kimlik
# ---------------------------------------------------------------------------


def test_background_card_gets_entropy_system_prompt(tmp_path, monkeypatch, isolated_settings):
    """Gerçek `send_background_task_async` yolu, sahte Popen ile."""
    bridge = ClaudeCodeBridge()
    bridge.active_project_dir = tmp_path
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["cwd"] = kwargs.get("cwd")
        # İstem dosyası tur bitince siliniyor; içeriği burada okunur.
        captured["system_prompt"] = ClaudeCodeBridge.system_prompt_text_in(list(cmd))
        return _FakeProc(_claude_lines())

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    monkeypatch.setattr(bridge, "_save_task_report", lambda *a, **k: "", raising=False)

    bridge._execute_background_task_worker(
        task_id="card-t9", task_name="Kart 9", prompt="raporu yaz",
        project_path=str(tmp_path), save_report=False,
        agent_spec={"name": "arastirmaci", "role": "worker", "prompt": "Sen araştırırsın."},
    )

    cmd = captured["cmd"]
    assert REPLACE_SYSTEM_PROMPT_FILE_FLAG in cmd
    text = captured["system_prompt"]
    assert "Entropy AI" in text
    assert "arastirmaci" in text
    assert "--bare" not in cmd
    # Kart da nötr çalışma dizininde koşar.
    assert not config_module.path_is_inside_git_repo(Path(captured["cwd"]))


# ---------------------------------------------------------------------------
# 9.6 — `--agents <json>` kadro yükü
# ---------------------------------------------------------------------------


@pytest.fixture
def roster_vault(tmp_path, monkeypatch):
    """Entropy kadrosu + bir Desk ofis ajanı olan yalıtılmış kasa."""
    from entropy.agents.desk_registry import DeskOffice, DeskRegistry
    from entropy.agents.registry import AgentRegistry, AgentSpec

    vault = tmp_path / "Vault"
    monkeypatch.setattr(config, "obsidian_vault_path", vault, raising=False)

    registry = AgentRegistry(vault_path=vault)
    registry.update(AgentSpec(
        name="arastirmaci", role="worker", description="Araştırır.",
        prompt="Sen araştırırsın.", tools_policy="read-only",
        model="gemini-3.8-flash-high",
    ))
    registry.update(AgentSpec(
        name="kodcu", role="worker", description="Kod yazar.",
        prompt="Sen kod yazarsın.", tools_policy="read-write",
        models={"claude": "claude-opus-5"},
    ))

    offices = DeskRegistry(vault_path=vault)
    offices.create(DeskOffice(name="gizli-ofis", purpose="Desk işi."))
    offices.agents("gizli-ofis").update(AgentSpec(
        name="ofis-iscisi", role="worker", description="Ofis işçisi.",
        office="gizli-ofis", tools_policy="read-only",
    ))
    return vault


def test_claude_agents_json_schema_and_desk_exclusion(roster_vault):
    from entropy.agents.compile import claude_agents_json

    payload = json.loads(claude_agents_json(roster_vault))

    assert set(payload) >= {"arastirmaci", "kodcu"}
    # Desk ofis ajanı kadroya ASLA girmez.
    assert "ofis-iscisi" not in payload
    assert not any(k.startswith("orkestrat") for k in payload)

    entry = payload["arastirmaci"]
    assert set(entry) <= {"description", "prompt", "tools", "model"}
    assert entry["description"] == "Araştırır."
    assert "Sen araştırırsın." in entry["prompt"]
    assert entry["tools"] == ["Read", "Glob", "Grep", "WebFetch", "WebSearch"]
    # Yabancı (gemini) ad Claude tarafında "inherit"e çevrilir.
    assert entry["model"] == "inherit"
    # `models.claude` geçersiz kılması doğrudan geçer.
    assert payload["kodcu"]["model"] == "claude-opus-5"
    assert "Write" in payload["kodcu"]["tools"]


def test_empty_roster_produces_no_agents_flag(tmp_path, monkeypatch, isolated_settings):
    from entropy.agents.compile import claude_agents_json

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "BosKasa", raising=False)
    assert claude_agents_json(tmp_path / "BosKasa") == ""
    assert ClaudeCodeBridge().entropy_agents_json() is None

    cmd = ClaudeCodeBridge().build_command("merhaba", agents_json=None)
    assert "--agents" not in cmd


def test_background_card_argv_carries_the_roster(tmp_path, monkeypatch, isolated_settings,
                                                 roster_vault):
    """Gerçek kart yolu: argv'de `--agents` ve içinde Entropy kadrosu var."""
    bridge = ClaudeCodeBridge()
    bridge.active_project_dir = tmp_path
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return _FakeProc(_claude_lines())

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)

    bridge._execute_background_task_worker(
        task_id="card-roster", task_name="Kadro", prompt="çalış",
        project_path=str(tmp_path), save_report=False,
    )

    cmd = captured["cmd"]
    assert "--agents" in cmd
    payload = json.loads(cmd[cmd.index("--agents") + 1])
    assert "arastirmaci" in payload
    assert "ofis-iscisi" not in payload


# ---------------------------------------------------------------------------
# 9.5 — resolve_model yürütme yolunda + defter model sütunu
# ---------------------------------------------------------------------------


def test_card_with_foreign_model_runs_on_claude_default(tmp_path, monkeypatch, isolated_settings):
    # Faz 11-C durum makinesi: AJANSIZ kart `backlog`ta kalır (backlog→running
    # geçişi yok). Model çözümünü ölçmek için kart gerçek bir Entropy ajanına
    # atanır; ajan Entropy kadrosunda olmalı (tasks.py:1308).
    from entropy.agents.registry import AgentRegistry, AgentSpec

    AgentRegistry(vault_path=tmp_path).update(AgentSpec(
        name="modelci", role="worker", description="Model testi.",
        prompt="Sen çalışırsın.", tools_policy="read-only",
    ))
    board = TaskBoard(vault_path=tmp_path)
    card = board.create(TaskCard(
        id="c-model", title="Model testi", provider="claude",
        model="gemini-3.1-pro-high", goal="dene", agent="modelci",
    ))
    # Kart modeli sağlayıcıya çevrilir: gemini-* -> "inherit" -> oturum modeli.
    assert resolve_card_model(card, provider="claude") == ""

    bridge = ClaudeCodeBridge()
    bridge.active_project_dir = tmp_path
    captured = {}

    # Kilit çekişmesine dayanıklı bekleme: köprünün işçi iş parçacığı proje
    # YAZMA kilidini beklerken (tam süitte başka bir kart aynı dizinde koşuyor
    # olabilir) 2,5 saniyelik yoklama döngüsü zaman aşımına uğruyor ve test
    # yalnızca tam süitte kırmızıya dönüyordu. Olayla beklemek hem hızlı hem de
    # tavanı yüksek tutmayı bedava yapıyor.
    launched = threading.Event()

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        launched.set()
        return _FakeProc(_claude_lines())

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    ledger = TaskLedger(db_path=tmp_path / "ledger.db")
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger", ledger)

    board.run(card.id, bridge_factory=lambda provider: bridge)
    # run_card iş parçacığı açmaz (köprü açar); sahte Popen eşzamanlı biter.
    assert launched.wait(60), "köprü süreci 60 sn içinde başlatılmadı"

    cmd = captured["cmd"]
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5"
    assert "gemini-3.1-pro-high" not in cmd
    row = ledger.get_task("card-c-model")
    assert row["model"] == "claude-opus-5"


def test_card_model_for_agy_is_kept(tmp_path):
    card = TaskCard(id="c2", provider="agy", model="gemini-3.8-flash-low")
    assert resolve_card_model(card, provider="agy") == "gemini-3.8-flash-low"


def test_ledger_model_column_is_backward_compatible(tmp_path):
    """Sütun ALTER ile eklenir; eski satırlar okunmaya devam eder."""
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE tasks (task_id TEXT PRIMARY KEY, task_name TEXT NOT NULL, "
        "project_path TEXT, status TEXT NOT NULL, created_at TIMESTAMP, "
        "started_at TIMESTAMP, completed_at TIMESTAMP, error TEXT, result_summary TEXT)"
    )
    conn.execute("INSERT INTO tasks VALUES ('eski','Eski','p','SUCCESS',NULL,NULL,NULL,NULL,NULL)")
    conn.commit()
    conn.close()

    ledger = TaskLedger(db_path=db)
    old = ledger.get_task("eski")
    assert old["provider"] == "agy" and old["model"] == ""

    ledger.record_task_start(task_id="yeni", task_name="Yeni", project_path="p",
                             provider="claude", model="claude-haiku-4-5")
    assert ledger.get_task("yeni")["model"] == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# 9.9 — --resume × sistem istemi
# ---------------------------------------------------------------------------


def test_conversation_map_forgets_on_prompt_change(tmp_path):
    cmap = ConversationMap(path=tmp_path / "map.json")
    cmap.set("office:x", "claude", "sess-1")
    cmap.set_prompt_signature("office:x", "ESKİ İSTEM")

    assert cmap.sync_prompt("office:x", "claude", "ESKİ İSTEM") is False
    assert cmap.get("office:x", "claude") == "sess-1"

    assert cmap.sync_prompt("office:x", "claude", "YENİ İSTEM") is True
    assert cmap.get("office:x", "claude") is None


def test_chat_drops_session_when_system_prompt_changes(isolated_settings):
    bridge = ClaudeCodeBridge()
    bridge.current_session_id = "sess-eski"
    assert bridge._forget_stale_session("istem A") is False   # ilk imza
    assert bridge.current_session_id == "sess-eski"
    assert bridge._forget_stale_session("istem B") is True
    assert bridge.current_session_id is None


# ---------------------------------------------------------------------------
# Ek-1 — Token gösterimi
# ---------------------------------------------------------------------------


def test_turn_tokens_are_not_session_total(isolated_settings):
    bridge = ClaudeCodeBridge()
    first = {"total_tokens": 30_000, "cache_read_tokens": 10_000}
    second = {"total_tokens": 40_000, "cache_read_tokens": 35_000}
    bridge._apply_chat_usage(first, 0.0)
    bridge._apply_chat_usage(second, 0.0)

    fields = bridge.usage_badge_fields()
    assert fields["session"] == 70_000
    # "(+son tur)" artık oturum toplamının kopyası DEĞİL.
    assert fields["turn"] == 40_000
    assert fields["cache_read"] == 45_000
    # cache_read 0,1× sayılır: (20.000 + 1.000) + (5.000 + 3.500)
    assert fields["cost_weighted"] == 29_500


def test_weighted_turn_tokens_discounts_cache_read():
    assert ClaudeCodeBridge.weighted_turn_tokens(
        {"total_tokens": 10_000, "cache_read_tokens": 10_000}
    ) == 1_000


# ---------------------------------------------------------------------------
# Ek-2 — default_provider()
# ---------------------------------------------------------------------------


def test_default_provider_reads_config(monkeypatch, isolated_settings):
    monkeypatch.setattr(config, "provider", "claude")
    assert config_module.default_provider() == "claude"
    monkeypatch.setattr(config, "provider", "")
    assert config_module.default_provider() == "agy"


def test_auto_select_provider_falls_back_to_claude(monkeypatch, isolated_settings):
    from entropy.core import identity as identity_module

    monkeypatch.setattr(config, "provider", "agy")
    ok = identity_module.ProviderStatus(provider="claude", logged_in=True)
    bad = identity_module.ProviderStatus(provider="agy", logged_in=False)

    assert identity_module.auto_select_provider(claude_status=ok, agy_status=bad) == "claude"
    assert config.provider == "claude"
    # İkinci çağrı sessiz: etkin sağlayıcının oturumu var.
    assert identity_module.auto_select_provider(claude_status=ok, agy_status=bad) is None
