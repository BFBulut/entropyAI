"""
FAZ 2 — ajan/görev yerel komutları ve Claude sohbet yolu.

Claude tarafı sahte köprüyle değil GERÇEK `_execute_prompt_worker` yoluyla
sürülür: `subprocess.Popen` taklit edilir, stream-json satırları gerçek
ayrıştırıcıdan geçer, argv gerçek `build_command`dan gelir. Böylece
`--append-system-prompt`, `--resume`, `--add-dir` ve proje kilidi birlikte
doğrulanır. Hiçbir test gerçek CLI çalıştırmaz, kota harcamaz.
"""

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from entropy.agents.registry import AgentRegistry
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id
from entropy.core.claude_bridge import ClaudeCodeBridge
from entropy.core.slash_commands import try_handle_local_command


# ---------------------------------------------------------------------------
# Ortak taklitler
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 777001
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


def _claude_lines(text="Merhaba", session="sess-42", usage=None):
    usage = usage or {
        "input_tokens": 900,
        "output_tokens": 120,
        "cache_read_input_tokens": 4000,
        "cache_creation_input_tokens": 250,
    }
    return [
        json.dumps({"type": "system", "subtype": "init", "session_id": session,
                    "model": "claude-opus-5", "tools": ["Read"]}) + "\n",
        json.dumps({"type": "assistant", "message": {"role": "assistant",
                                                     "content": [{"type": "text", "text": text}]}}) + "\n",
        json.dumps({"type": "result", "subtype": "success", "result": text,
                    "session_id": session, "total_cost_usd": 0.01,
                    "is_error": False, "usage": usage}) + "\n",
    ]


class _Bridge:
    """Yerel komutların dokunduğu en küçük köprü yüzeyi."""

    provider_name = "agy"
    selected_model = "gemini-3.1-pro-high"
    active_project_dir = None
    conversation_history = []


def _isolate_chat_history(monkeypatch):
    """
    Sohbet geçmişi yazımını yutar.

    Doğrudan "entropy.core.config.save_chat_history" yolu monkeypatch'te çalışmaz:
    entropy.core paketi `config` adını config NESNESİNE bağlıyor. Gerçek modül
    sys.modules'tan alınır; aksi hâlde test kullanıcının chat_history.json'unu ezerdi.
    """
    import sys

    module = sys.modules["entropy.core.config"]
    monkeypatch.setattr(module, "save_chat_history", lambda h: None)
    # Token muhasebesi her turda ayarları diske yazıyor; testler kullanıcının
    # settings.json'unu (ve sonraki testlerin gördüğü kümülatif kalemleri) ezmemeli.
    # Örneğe değil SINIFA yazılır: pydantic modeli, alan olmayan bir adı örnek
    # üzerinde ayarlamayı reddediyor.
    monkeypatch.setattr(type(module.config), "save_settings", lambda self: None)


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    return tmp_path / "Vault"


@pytest.fixture
def registry(isolated_vault):
    reg = AgentRegistry(vault_path=isolated_vault)
    reg.ensure_defaults()
    return reg


# ---------------------------------------------------------------------------
# /agents ve /agent
# ---------------------------------------------------------------------------


def test_agents_command_lists_registry(registry):
    out = try_handle_local_command("/agents", _Bridge())
    assert out is not None
    for name in ("arastirmaci", "analist", "yazar"):
        assert name in out
    assert "/task" in out  # devretme yolu gösterilmeli


def test_agents_command_when_empty_shows_path(isolated_vault):
    out = try_handle_local_command("/agents", _Bridge())
    assert "Entropy/Agents" in out and "AGENT.md" in out


def test_agent_detail_command(registry):
    out = try_handle_local_command("/agent arastirmaci", _Bridge())
    assert "arastirmaci" in out
    assert "research" in out
    assert "read-only" in out
    assert "AGENT.md" in out  # kaynak dosya yolu


def test_agent_detail_unknown_name_lists_known(registry):
    out = try_handle_local_command("/agent yok-boyle", _Bridge())
    assert "yok-boyle" in out and "arastirmaci" in out


def test_agent_without_argument_shows_usage(registry):
    assert "/agent" in try_handle_local_command("/agent", _Bridge())


def test_unrelated_command_is_not_captured():
    """`/agentic` gibi başka bir komut yerel sanılmamalı."""
    assert try_handle_local_command("/agentic bir şey", _Bridge()) is None


# ---------------------------------------------------------------------------
# /task ve /tasks
# ---------------------------------------------------------------------------


def test_task_command_creates_card_without_running_it(registry, isolated_vault, monkeypatch):
    """
    Faz 11-C: `/task` artık KOŞTURMUYOR, yalnızca kart doğuruyor.

    Kart oluşturulduğu satırda başlatıldığı sürece `backlog`/`assigned` hiç
    beklemiyordu; pano bir kuyruk değil kayıt defteriydi ve sahiplenme,
    öncelik, eşzamanlılık tavanı, kurtarma kavramlarının hiçbiri işlemiyordu.
    Koşturmak artık `BoardDispatcher`ın işi.
    """
    started = {}

    class _Recorder:
        provider_name = "agy"

        def send_background_task_async(self, **kwargs):
            started.update(kwargs)

    monkeypatch.setattr(TaskBoard, "bridge_for", classmethod(lambda cls, p, bridge_factory=None: _Recorder()))

    out = try_handle_local_command(
        "/task yazar Sprint raporu :: Sprint çıktısını rapora dönüştür", _Bridge()
    )
    assert "Panoya" in out
    assert "yazar" in out

    board = TaskBoard(vault_path=isolated_vault)
    cards = board.list()
    assert len(cards) == 1
    card = cards[0]
    assert card.title == "Sprint raporu"
    assert card.goal == "Sprint çıktısını rapora dönüştür"
    assert card.agent == "yazar"
    assert card.status == "assigned"
    assert started == {}, "/task köprüye tek çağrı bile göndermemeli"

    # Kartı tetikleyici koşturur; efor ve istem o yolda üretilir.
    from entropy.agents.dispatcher import BoardDispatcherCore

    BoardDispatcherCore(board=board, vault_path=isolated_vault).tick()
    assert started["agent"] == "yazar"
    assert started["save_report"] is True
    assert "Sprint çıktısını rapora dönüştür" in started["prompt"]
    assert "yazar ajanısın" in started["prompt"]  # ajan gövdesi prompt'a girdi
    assert board.get(card.id).status == "running"


def test_task_command_rejects_unknown_agent(registry):
    out = try_handle_local_command("/task hayalet Başlık :: hedef", _Bridge())
    assert "hayalet" in out and "arastirmaci" in out


def test_task_command_requires_agent_and_title(registry):
    assert "Ajan ve başlık" in try_handle_local_command("/task yazar", _Bridge())


def test_tasks_command_lists_and_filters(registry, isolated_vault):
    board = TaskBoard(vault_path=isolated_vault)
    board.create(TaskCard(id=new_task_id("a"), title="Kart A", agent="yazar", status="backlog"))
    board.create(TaskCard(id=new_task_id("b"), title="Kart B", agent="analist", status="done"))

    out = try_handle_local_command("/tasks", _Bridge())
    assert "Kart A" in out and "Kart B" in out

    out_done = try_handle_local_command("/tasks done", _Bridge())
    assert "Kart B" in out_done and "Kart A" not in out_done

    assert "Bilinmeyen durum" in try_handle_local_command("/tasks saçma", _Bridge())


def test_task_stop_marks_card_canceled(registry, isolated_vault):
    """
    Faz 11-C: durdurulan kart `failed` değil `canceled`.

    "Kullanıcı vazgeçti" ile "iş başarısız oldu" aynı sütunda durduğu sürece
    panodaki hiçbir sayaç anlamlı değildi.
    """
    board = TaskBoard(vault_path=isolated_vault)
    card = board.create(TaskCard(id=new_task_id("c"), title="Kart C", agent="yazar"))
    board.update(replace(card, status="running"))

    out = try_handle_local_command(f"/task stop {card.id}", _Bridge())
    assert "Durduruldu" in out
    assert board.get(card.id).status == "canceled"

    # Çalışmayan kart durdurulmaz; kullanıcıya durumu söylenir.
    assert "çalışmıyor" in try_handle_local_command(f"/task stop {card.id}", _Bridge())


# ---------------------------------------------------------------------------
# Claude sohbet yolu (gerçek işçi + Popen taklidi)
# ---------------------------------------------------------------------------


def _run_chat(bridge, monkeypatch, prompt="Bu projeyi özetle", **kwargs):
    captured = {}

    def fake_popen(cmd, **kw):
        captured["cmd"] = list(cmd)
        captured["kwargs"] = kw
        # Sistem istemi argv'de de olabilir, dosyada da (uzun bağlam Windows
        # komut satırı sınırını aştığı için dosyaya taşınıyor); metin süreç
        # başlarken çözülür, çünkü dosya tur bitince siliniyor.
        captured["system_prompt"] = ClaudeCodeBridge.system_prompt_text_in(cmd)
        return _FakeProc(_claude_lines("Özet hazır."))

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", fake_popen)
    bridge._execute_prompt_worker(prompt, **kwargs)
    return captured


def test_claude_chat_injects_context_via_append_system_prompt(tmp_path, monkeypatch, registry):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    _isolate_chat_history(monkeypatch)

    captured = _run_chat(b, monkeypatch)
    cmd = captured["cmd"]

    # Uzun bağlam argv'ye yazılmaz, dosyadan gider. Faz 9'da saf kip açıkken
    # bayrak `--system-prompt-file` (varsayılan istemi DEĞİŞTİRİR), kapalıyken
    # eski `--append-system-prompt[-file]`; ikisi de kabul.
    assert any(
        f in cmd
        for f in (
            "--append-system-prompt",
            "--append-system-prompt-file",
            "--system-prompt",
            "--system-prompt-file",
        )
    )
    system_prompt = captured["system_prompt"]
    assert "Entropy AI" in system_prompt
    assert "[AJANLAR]" in system_prompt          # ajan farkındalığı sohbete de girer
    assert "arastirmaci" in system_prompt
    assert cmd[cmd.index("--add-dir") + 1] == str(tmp_path)
    # İlk turda oturum yok: --resume verilmemeli (geçersiz kimlik süreci düşürür).
    assert "--resume" not in cmd
    # Oturum kimliği init/result olayından alınır ve saklanır.
    assert b.current_session_id == "sess-42"


def test_claude_chat_second_turn_resumes_session(tmp_path, monkeypatch, registry):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    _isolate_chat_history(monkeypatch)

    _run_chat(b, monkeypatch, prompt="ilk mesaj")
    captured = _run_chat(b, monkeypatch, prompt="ikinci mesaj")
    cmd = captured["cmd"]

    assert cmd[cmd.index("--resume") + 1] == "sess-42"
    # Süren oturumda ağır bağlam tekrar gönderilmez; sistem istemi kısalır.
    system_prompt = captured["system_prompt"]
    assert "Önceki Sohbet Özeti" not in system_prompt


def test_claude_chat_records_turn_and_usage_breakdown(tmp_path, monkeypatch, registry):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    _isolate_chat_history(monkeypatch)

    _run_chat(b, monkeypatch)

    assert b.conversation_history[-1]["content"] == "Özet hazır."
    usage = b.usage_breakdown()
    # Önbelleğe yazma ayrı kalem: okuma ile aynı çuvala girmemeli.
    assert usage["cache_write"] == 250
    assert usage["cache_read"] == 4000
    assert usage["input"] == 900
    assert usage["output"] == 120


def test_agy_bridge_usage_breakdown_has_zero_cache_write(monkeypatch):
    """AGY önbelleğe yazma kalemi raporlamaz; alan var ama 0 (arayüz gizler)."""
    from entropy.core.agy_bridge import AgyProcessBridge

    b = AgyProcessBridge()
    # Kalıcı ayarlardan sızan bir kalem olmasın: bu testin konusu AGY'nin kendi
    # turlarında yazma kalemi ÜRETMEDİĞİ.
    b.last_cumulative_usage = {}
    assert b.usage_breakdown()["cache_write"] == 0


def test_claude_chat_attachments_become_paths_and_add_dirs(tmp_path, monkeypatch, registry):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    _isolate_chat_history(monkeypatch)

    media = tmp_path / "ekler"
    media.mkdir()
    img = media / "ekran.png"
    img.write_bytes(b"x")
    pdf = media / "belge.pdf"
    pdf.write_bytes(b"y")

    captured = _run_chat(
        b, monkeypatch, prompt="şunu incele",
        image_attachments=[str(img)], pdf_attachments=[str(pdf)],
    )
    cmd = captured["cmd"]
    # Faz 14-A: ek dosya yönergesi turdan tura değişir, bu yüzden sistem
    # isteminde değil KULLANICI MESAJININ başındaki bağlam bloğunda taşınır
    # (sistem istemi sabit kalmazsa oturum düşüyordu).
    user_message = b.last_user_message

    # Bulgu: CLI'da gömülü görsel için bayrak yok; Read aracı yerel yolu okuyor.
    assert str(img.resolve()) in user_message
    assert str(pdf.resolve()) in user_message
    assert "Read" in user_message
    # Dosyanın klasörü erişilebilir kılınmalı, yoksa Read izinsiz kalır.
    add_dirs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--add-dir"]
    assert str(media) in add_dirs


def test_attachment_directive_empty_without_files():
    b = ClaudeCodeBridge()
    assert b.build_attachment_directive(None, None) == ("", [])


def test_claude_chat_takes_and_releases_project_lock(tmp_path, monkeypatch, registry):
    from entropy.core.project_lock import project_lock_manager

    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    _isolate_chat_history(monkeypatch)

    calls = []
    monkeypatch.setattr(project_lock_manager, "acquire_write",
                        lambda p, timeout=None: calls.append(("acquire_write", p)) or True)
    monkeypatch.setattr(project_lock_manager, "release_write",
                        lambda p: calls.append(("release_write", p)))

    # Yazma niyeti taşıyan tur yazma kilidi almalı ve bırakmalı.
    _run_chat(b, monkeypatch, prompt="config.py dosyasını güncelle")
    kinds = [c[0] for c in calls]
    assert kinds == ["acquire_write", "release_write"]


def test_claude_chat_aborts_when_lock_times_out(tmp_path, monkeypatch, registry):
    from entropy.core.project_lock import project_lock_manager

    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    monkeypatch.setattr(project_lock_manager, "acquire_read", lambda p, timeout=None: False)
    monkeypatch.setattr(project_lock_manager, "acquire_write", lambda p, timeout=None: False)

    def explode(*a, **k):
        raise AssertionError("kilit alınamadığı hâlde süreç başlatıldı")

    monkeypatch.setattr("entropy.core.claude_bridge.subprocess.Popen", explode)
    b._execute_prompt_worker("bu projeyi özetler misin")
    assert b.is_running is False


def test_claude_chat_passes_agent_flag(tmp_path, monkeypatch, registry):
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    _isolate_chat_history(monkeypatch)

    captured = _run_chat(b, monkeypatch, agent="arastirmaci")
    assert captured["cmd"][captured["cmd"].index("--agent") + 1] == "arastirmaci"


def test_claude_chat_carries_the_roster_in_agents_flag(tmp_path, monkeypatch, registry):
    """Saf kip açıkken sohbet argv'si Entropy kadrosunu `--agents` ile taşır."""
    import json as _json

    from entropy.core.config import config

    monkeypatch.setattr(config, "claude_isolated", True)
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    _isolate_chat_history(monkeypatch)

    cmd = _run_chat(b, monkeypatch)["cmd"]
    assert "--agents" in cmd
    payload = _json.loads(cmd[cmd.index("--agents") + 1])
    assert "arastirmaci" in payload
    assert payload["arastirmaci"]["prompt"]


def test_claude_chat_without_isolation_has_no_agents_flag(tmp_path, monkeypatch, registry):
    """Saf kip kapalıyken CLI zaten `.claude/agents` okur; bayrak eklenmez."""
    from entropy.core.config import config

    monkeypatch.setattr(config, "claude_isolated", False)
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    _isolate_chat_history(monkeypatch)

    assert "--agents" not in _run_chat(b, monkeypatch)["cmd"]


def test_send_prompt_async_queues_attachments(tmp_path, monkeypatch):
    """Meşgulken sıraya alınan mesaj eklerini kaybetmemeli."""
    b = ClaudeCodeBridge()
    b.active_project_dir = tmp_path
    b._is_running = True

    b.send_prompt_async("ikinci", image_attachments=["a.png"], pdf_attachments=["b.pdf"])
    assert len(b._prompt_queue) == 1
    queued = b._prompt_queue[0]
    assert queued[0] == "ikinci"
    assert queued[1] == ["a.png"]
    assert queued[2] == ["b.pdf"]
