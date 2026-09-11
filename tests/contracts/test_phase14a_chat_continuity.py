"""
Faz 14-A sözleşmesi — SOHBET SÜREKLİLİĞİ.

Kullanıcının yaşadığı arıza ("onaylıyorum" dedi, Entropy "bu oturumun bağlamı
bana ulaşmadı" dedi) ölçülmüştü: dört ardışık sohbet turunun argv'si
`NO-RESUME / RESUME / NO-RESUME / NO-RESUME` çıkıyordu, çünkü sistem istemi
sorguya bağlı bilişsel bağlam taşıyordu → imza her turda değişiyor →
`_forget_stale_session` süren oturumu düşürüyordu (Faz 14 araştırma notu A,
Ölçüm B). Bu dosya o ölçümü SÖZLEŞMEYE çevirir:

1. Sistem istemi turdan tura BİREBİR aynıdır (karma eşitliği).
2. Sorguya bağlı bağlam kullanıcı mesajının BAŞINDA blok olarak gider.
3. Aynı sohbet tek oturum kimliğiyle sürer: tur 1 `--session-id`, tur 2-4
   `--resume <aynı kimlik>`.
4. Yetenek afişi oturumu DÜŞÜRMEZ.
5. Model/efor değişince oturum bilinçli düşer ve yeni oturuma geçmiş özeti
   kullanıcı bloğuyla taşınır.
6. Sohbet turu proje kökünde SALT OKUNURdur (yazma niyeti sezilse bile).
7. Defterdeki sohbet satırı gerçek modeli ve eforu taşır.

Hiçbir test gerçek CLI çalıştırmaz: `subprocess.Popen` taklit edilir, argv
gerçek `build_command`dan, akış gerçek `consume_stream`den geçer. Kota 0.
"""

import hashlib
import json

import pytest

from entropy.core.claude_bridge import (
    CHAT_TOOLS_WRITE,
    TURN_CONTEXT_BLOCK_HEADER,
    ClaudeCodeBridge,
)


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


def _lines(text="Anladım.", session="sess-14a"):
    return [
        json.dumps({"type": "system", "subtype": "init", "session_id": session,
                    "model": "claude-fable-5-1", "tools": ["Read"]}) + "\n",
        json.dumps({"type": "assistant", "message": {
            "role": "assistant", "content": [{"type": "text", "text": text}]}}) + "\n",
        json.dumps({"type": "result", "subtype": "success", "result": text,
                    "session_id": session, "total_cost_usd": 0.0, "is_error": False,
                    "usage": {"input_tokens": 120, "output_tokens": 30}}) + "\n",
    ]


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Kasa, sohbet geçmişi ve ayar yazımı izole; saf kip AÇIK."""
    import sys

    module = sys.modules["entropy.core.config"]
    cfg = module.config
    monkeypatch.setattr(cfg, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    monkeypatch.setattr(cfg, "claude_isolated", True, raising=False)
    monkeypatch.setattr(module, "save_chat_history", lambda h: None)
    monkeypatch.setattr(type(cfg), "save_settings", lambda self: None)
    return tmp_path


def _bridge(tmp_path):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    return b


def _turn(bridge, monkeypatch, prompt, **kwargs):
    """Bir sohbet turu koşturur; argv + sistem istemi + kullanıcı mesajı döner."""
    captured = {}

    def fake_popen(cmd, **kw):
        captured["cmd"] = list(cmd)
        captured["system_prompt"] = ClaudeCodeBridge.system_prompt_text_in(cmd)
        return _FakeProc(_lines())

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    bridge._execute_prompt_worker(prompt, **kwargs)
    captured["user_message"] = bridge.last_user_message
    return captured


def _resume_of(cmd):
    return cmd[cmd.index("--resume") + 1] if "--resume" in cmd else None


def _session_of(cmd):
    return cmd[cmd.index("--session-id") + 1] if "--session-id" in cmd else None


def _sha(text):
    return hashlib.sha1((text or "").encode("utf-8", "replace")).hexdigest()


# ---------------------------------------------------------------------------
# Ölçüm B'nin sözleşme hâli: dört ardışık tur
# ---------------------------------------------------------------------------


def test_four_consecutive_turns_keep_one_session_and_one_system_prompt(tmp_path, monkeypatch):
    b = _bridge(tmp_path)
    prompts = [
        "Bugünkü konumuz mor zürafa envanteri",
        "bunu biraz açar mısın",
        # Not (Faz 14-B): burada eskiden "onaylıyorum" vardı. Artık o mesaj
        # CLI'ya HİÇ gitmiyor (bekleyen iş kuyruğunda çözülüyor), yani süreklilik
        # ölçümünü taşıyamaz; yerine sıradan bir takip turu kondu.
        "peki envanterdeki en yaşlı zürafa hangisi",
        "az önce ne dedim",
    ]
    runs = [_turn(b, monkeypatch, p) for p in prompts]

    # 1) Oturum zinciri: NO-RESUME / RESUME / RESUME / RESUME
    assert _resume_of(runs[0]["cmd"]) is None
    assert [_resume_of(r["cmd"]) for r in runs[1:]] == ["sess-14a"] * 3
    # İlk tur kimliği ÖNCEDEN atar (tek sohbet = tek kimlik sözleşmesi).
    assert _session_of(runs[0]["cmd"])
    assert "--session-id" not in runs[1]["cmd"]

    # 2) Sistem istemi dört turda birebir aynı (karma eşitliği).
    hashes = {_sha(r["system_prompt"]) for r in runs}
    assert len(hashes) == 1, "sistem istemi turdan tura değişmemeli"
    assert "Entropy AI" in runs[0]["system_prompt"]
    # Sorguya bağlı bağlam sistem isteminde DEĞİL.
    assert "[BİLİŞSEL BAĞLAM]" not in runs[0]["system_prompt"]
    assert "[ÖNCEKİ SOHBET ÖZETİ]" not in runs[3]["system_prompt"]

    # 3) O turun bağlamı kullanıcı mesajının başında.
    assert runs[0]["user_message"].startswith(TURN_CONTEXT_BLOCK_HEADER)
    assert runs[0]["user_message"].rstrip().endswith(prompts[0])
    assert runs[3]["user_message"].rstrip().endswith(prompts[3])


def test_skill_banner_turn_does_not_drop_the_session(tmp_path, monkeypatch):
    """Yetenek afişi istemi değiştirmez; kullanıcı mesajına iner."""
    b = _bridge(tmp_path)
    first = _turn(b, monkeypatch, "merhaba")

    monkeypatch.setattr(
        ClaudeCodeBridge, "resolve_target_skill",
        lambda self, prompt, active_skill=None: (None, "Yetenek: google-flow"),
    )
    second = _turn(b, monkeypatch, "bu yetenekle video üret")

    assert _resume_of(second["cmd"]) == "sess-14a"
    assert _sha(second["system_prompt"]) == _sha(first["system_prompt"])
    assert "google-flow" in second["user_message"]
    assert "google-flow" not in second["system_prompt"]


def test_model_change_opens_a_new_session_with_a_history_block(tmp_path, monkeypatch):
    b = _bridge(tmp_path)
    _turn(b, monkeypatch, "Bugünkü konumuz mor zürafa envanteri")
    _turn(b, monkeypatch, "devam")

    b.selected_model = "claude-sonnet-5"
    third = _turn(b, monkeypatch, "az önce ne dedim")

    # Model değişimi imzayı bilinçli olarak kırar: yeni oturum açılır...
    assert _resume_of(third["cmd"]) is None
    assert _session_of(third["cmd"])
    # ...ve sohbetin başı kullanıcı bloğuyla taşınır (eskiden hiç taşınmıyordu).
    assert "[ÖNCEKİ SOHBET ÖZETİ]" in third["user_message"]
    assert "mor zürafa envanteri" in third["user_message"]


def test_history_summary_keeps_whole_sentences_not_100_chars(tmp_path, monkeypatch):
    """`[:100]` kırpması kalktı: son 8 tur, mesaj başına 1.200 karakter."""
    b = _bridge(tmp_path)
    uzun = "Bugünkü konumuz " + ("mor zürafa envanteri " * 20)
    b.conversation_history = [{"role": "user", "content": uzun}]
    summary = b.chat_history_summary()
    assert len(summary) > 400
    assert summary.count("mor zürafa") > 5

    b.conversation_history = [
        {"role": "user", "content": f"mesaj {i}"} for i in range(20)
    ]
    assert b.chat_history_summary().count("\n- ") == 8


# ---------------------------------------------------------------------------
# Sohbette proje kökü salt okunur
# ---------------------------------------------------------------------------


def test_chat_turn_has_no_write_tools_even_with_write_intent(tmp_path, monkeypatch):
    b = _bridge(tmp_path)
    monkeypatch.setattr(ClaudeCodeBridge, "is_code_modifying_intent",
                        lambda self, prompt, mode="": True)
    run = _turn(b, monkeypatch, "claude_bridge.py dosyasını düzenle ve kaydet")
    cmd = run["cmd"]

    tools = cmd[cmd.index("--tools") + 1].split(",")
    for forbidden in CHAT_TOOLS_WRITE:
        assert forbidden not in tools, "sohbet turu proje kökünde salt okunur olmalı"
    assert "Read" in tools
    # Proje kökü okunabilir kalır (yalnız yazma yolu kapalı).
    assert str(tmp_path) in [cmd[i + 1] for i, a in enumerate(cmd) if a == "--add-dir"]


def test_chat_tools_stay_readonly_in_isolated_mode_but_card_path_is_untouched():
    b = ClaudeCodeBridge()
    assert "Write" not in b.chat_tools("accept-edits", needs_write=True, isolated=True)
    # Kart yolu (tools_for) DEĞİŞMEDİ: onaylı kart hâlâ yazabilir.
    assert "Write" in ClaudeCodeBridge.tools_for("accept-edits")


# ---------------------------------------------------------------------------
# Defter: model ve efor
# ---------------------------------------------------------------------------


def test_ledger_chat_row_carries_model_and_effort(tmp_path, monkeypatch):
    from entropy.core.task_ledger import TaskLedger

    ledger = TaskLedger(db_path=tmp_path / "ledger.db")
    row_id = ledger.record_chat_turn(
        {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        provider="claude", model="claude-fable-5-1", effort="high",
    )
    assert row_id
    with ledger._get_connection() as conn:
        row = conn.execute(
            "SELECT model, effort, provider FROM tasks WHERE task_id = ?", (row_id,)
        ).fetchone()
    assert tuple(row) == ("claude-fable-5-1", "high", "claude")


def test_chat_turn_writes_the_real_model_into_the_ledger(tmp_path, monkeypatch):
    """Köprüde `self.model` YOK; satır `current_model`den gelmeli."""
    captured = {}

    def fake_record(usage=None, provider="", model="", task_id="", effort=""):
        captured.update({"provider": provider, "model": model, "effort": effort})
        return "chat-1"

    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger.record_chat_turn",
                        fake_record)
    b = _bridge(tmp_path)
    _turn(b, monkeypatch, "merhaba")

    assert captured["provider"] == "claude"
    assert captured["model"], "defterdeki sohbet satırı modelsiz kalmamalı"
    assert not hasattr(b, "model"), "yanlış alan adı geri gelmemeli"
