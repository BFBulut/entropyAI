"""
FAZ 2 — ajan kayıt defteri, derleme, görev kartları ve yerel komutlar.

Hiçbir test gerçek agy/claude süreci başlatmaz: köprü yolu `subprocess.Popen`
taklidiyle sürülür, böylece kota harcanmadan gerçek `send_background_task_async`
yolu (bayrak kurulumu, akış ayrıştırma, geri çağrı) doğrulanır.
"""

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from entropy.agents.compile import compile_agent, render_agy_agent, render_claude_agent
from entropy.agents.registry import (
    AGENT_FILENAME,
    AgentRegistry,
    AgentSpec,
    agents_manifest,
    parse_frontmatter,
    render_frontmatter,
)
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id
from entropy.core.event_bus import bus


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


class _FakeProc:
    """stream-json satırlarını akıtan sahte süreç (gerçek Popen'in yerine)."""

    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 999001
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


def _agy_lines(text="Görev tamamlandı."):
    """agy köprüsünün beklediği olay şeması (event + iç içe yük)."""
    return [
        json.dumps({"event": "step_update", "step_update": {"text_delta": text}}) + "\n",
        json.dumps({
            "event": "result",
            "result": {
                "response": text,
                "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            },
        }) + "\n",
    ]


def _patch_app_root(monkeypatch, root):
    """
    APP_ROOT'u geçici bir dizine çeker.

    Doğrudan "entropy.core.config.APP_ROOT" yolu işe yaramaz: entropy.core paketi
    `config` adını config NESNESİNE bağlıyor, bu yüzden monkeypatch pydantic
    modeline yazmaya çalışıyor. Gerçek modül sys.modules'tan alınır.
    """
    import sys

    module = sys.modules["entropy.core.config"]
    monkeypatch.setattr(module, "APP_ROOT", Path(root), raising=False)


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    """
    Kasa yolunu teste özel bir dizine çeker.

    Gerekli: görev kartı yürütme yolu gerçek `save_report=True` ile koşuyor ve
    izole edilmezse her test çalıştırması kullanıcının Obsidian kasasına otonom
    görev raporu düşürürdü.
    """
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    return tmp_path / "Vault"


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture
def registry(vault):
    return AgentRegistry(vault_path=vault)


def _spec(name="arastirmaci", **kw):
    base = dict(
        role="research",
        description="Kaynaklı araştırma yapar.",
        provider="agy",
        model="gemini-3.8-flash-high",
        effort="medium",
        skills=["research", "media"],
        tools_policy="read-only",
        memory_path="Entropy/AgentMemory/arastirmaci.md",
        prompt="Sen araştırmacısın. Kaynak göster.",
    )
    base.update(kw)
    return AgentSpec(name=name, **base)


# ---------------------------------------------------------------------------
# Ön bilgi ayrıştırma
# ---------------------------------------------------------------------------


def test_frontmatter_roundtrip_without_yaml(monkeypatch):
    """PyYAML yoksa basit ayrıştırıcı devreye girer ve alanları kaybetmez."""
    import builtins

    real_import = builtins.__import__

    def no_yaml(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("yaml yok")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_yaml)

    text = render_frontmatter(_spec().to_frontmatter()) + "\n\n# arastirmaci\n\ngövde"
    front, body = parse_frontmatter(text)
    assert front["name"] == "arastirmaci"
    assert front["skills"] == ["research", "media"]
    assert front["provider"] == "agy"
    assert body.startswith("# arastirmaci")


def test_frontmatter_supports_block_lists():
    text = "---\nname: x\nskills:\n  - a\n  - b\n---\ngövde"
    front, body = parse_frontmatter(text)
    assert front["name"] == "x"
    assert front["skills"] == ["a", "b"]
    assert body == "gövde"


def test_body_without_frontmatter_is_kept_whole():
    front, body = parse_frontmatter("sadece gövde")
    assert front == {}
    assert body == "sadece gövde"


# ---------------------------------------------------------------------------
# Kayıt defteri CRUD
# ---------------------------------------------------------------------------


def test_registry_crud_roundtrip(registry, vault):
    spec = registry.create(_spec())
    assert spec.path == vault / "Entropy" / "Agents" / "arastirmaci" / AGENT_FILENAME
    assert spec.path.is_file()

    loaded = registry.get("arastirmaci")
    assert loaded.role == "research"
    assert loaded.skills == ["research", "media"]
    assert loaded.tools_policy == "read-only"
    assert "Kaynak göster" in loaded.prompt
    assert loaded.updated_at  # dosya mtime'ından türetilir

    registry.update(replace(loaded, description="Güncellendi."))
    assert registry.get("arastirmaci").description == "Güncellendi."

    assert [s.name for s in registry.list()] == ["arastirmaci"]
    assert registry.delete("arastirmaci") is True
    assert registry.get("arastirmaci") is None
    assert registry.delete("arastirmaci") is False


def test_registry_create_refuses_overwrite(registry):
    registry.create(_spec())
    with pytest.raises(FileExistsError):
        registry.create(_spec())


def test_registry_emits_agents_updated(registry, qapp):
    seen = []
    bus.agents_updated.connect(seen.append)
    try:
        registry.create(_spec())
        registry.delete("arastirmaci")
    finally:
        bus.agents_updated.disconnect(seen.append)
    assert seen == ["arastirmaci", "arastirmaci"]


def test_default_agents_seeded_once_and_not_resurrected(registry):
    created = registry.ensure_defaults()
    # Faz 3'te tohum kadroya ofis rolleri eklendi (orkestratör + değerlendirici).
    assert set(created) == {"arastirmaci", "analist", "yazar",
                            "orkestrator", "degerlendirici"}
    assert registry.get("arastirmaci").model == "gemini-3.8-flash-high"
    assert registry.get("yazar").role == "report writing"

    # İkinci çağrı hiçbir şey yazmaz.
    assert registry.ensure_defaults() == []
    # Kullanıcı bir ajanı sildiyse geri gelmemeli (kasa tamamen boş değil).
    registry.delete("analist")
    assert registry.ensure_defaults() == []
    assert registry.get("analist") is None


# ---------------------------------------------------------------------------
# Derleme
# ---------------------------------------------------------------------------


def test_compile_writes_both_provider_formats(registry, tmp_path, monkeypatch):
    _patch_app_root(monkeypatch, tmp_path / "app")
    spec = registry.create(_spec())
    project = tmp_path / "proj"
    project.mkdir()

    out = compile_agent(spec, project)
    agy_path = out["agy"]
    claude_path = out["claude"]
    assert agy_path.name == "agent.md"
    assert agy_path.parent.name == "arastirmaci"
    assert ".agents/agents" in agy_path.as_posix()
    assert claude_path.as_posix().endswith(".claude/agents/arastirmaci.md")

    agy_front, agy_body = parse_frontmatter(agy_path.read_text(encoding="utf-8"))
    assert agy_front["name"] == "arastirmaci"
    assert agy_front["subagent"] is True and agy_front["mainAgent"] is True
    assert agy_front["inheritCustomizations"] is False
    assert agy_front["model"] == "flash"          # gemini-3.8-flash-high -> flash
    assert "rules" in agy_front
    assert "Kaynak göster" in agy_body

    cl_front, cl_body = parse_frontmatter(claude_path.read_text(encoding="utf-8"))
    assert cl_front["name"] == "arastirmaci"
    assert cl_front["effort"] == "medium"
    assert "Read" in cl_front["tools"] and "Write" not in cl_front["tools"]  # read-only
    assert "Kaynak göster" in cl_body

    # agy biçimi proje köküne yazılır (agy ajanı çalışma dizininden keşfeder).
    assert (project / ".agents" / "agents" / "arastirmaci" / "agent.md").is_file()
    # Faz 11-C: claude biçimi proje köküne ARTIK YAZILMAZ — derlenmiş ajanlar
    # kullanıcının kendi Claude Code oturumuna sızıyordu. Tek kök: nötr çalışma
    # alanı; saf kip kadroyu `--agents <json>` ile taşıyor.
    assert not (project / ".claude").exists(), "proje köküne .claude sızdı"
    from entropy.agents.compile import claude_compile_root

    assert claude_path.parent.parent.parent == claude_compile_root()


def test_compile_skips_untouched_files(registry, tmp_path, monkeypatch):
    _patch_app_root(monkeypatch, tmp_path / "app")
    spec = registry.create(_spec())
    project = tmp_path / "proj"
    project.mkdir()

    first = compile_agent(spec, project)["agy"]
    stamp = first.stat().st_mtime_ns
    compile_agent(spec, project)
    assert first.stat().st_mtime_ns == stamp, "kaynak değişmediği hâlde dosya yeniden yazıldı"

    # Kaynak değişince yazılır.
    changed = replace(spec, prompt="Yeni gövde.")
    compile_agent(changed, project)
    assert "Yeni gövde." in first.read_text(encoding="utf-8")


def test_claude_no_tools_policy_omits_tools_field():
    spec = _spec(tools_policy="no-tools")
    front, body = parse_frontmatter(render_claude_agent(spec))
    assert "tools" not in front
    assert "Hiçbir araç kullanma" in body
    assert "Hiçbir araç kullanma" in " ".join(str(v) for v in parse_frontmatter(render_agy_agent(spec))[0].values())


def test_compile_all_returns_every_agent(registry, tmp_path, monkeypatch):
    _patch_app_root(monkeypatch, tmp_path / "app")
    registry.ensure_defaults()
    compiled = registry.compile_all(tmp_path / "proj2")
    assert set(compiled) == {"arastirmaci", "analist", "yazar",
                             "orkestrator", "degerlendirici"}


# ---------------------------------------------------------------------------
# Manifest bölümü
# ---------------------------------------------------------------------------


def test_agents_manifest_lists_agents_and_delegation_rule(registry):
    registry.ensure_defaults()
    text = agents_manifest(registry)
    assert "[AJANLAR]" in text
    for name in ("arastirmaci", "analist", "yazar"):
        assert name in text
    assert "/task <ajan> <başlık> :: <hedef>" in text
    assert "Entropy/Tasks" in text
    # Bütçe: her turda enjekte edilen bölüm ~150 token'ı aşmamalı.
    assert len(text) <= 900


def test_agents_manifest_empty_when_no_agents(registry):
    assert agents_manifest(registry) == ""


def test_bridge_cognitive_context_includes_agents_section(registry, monkeypatch):
    """Köprü manifest'i ajan bölümünü de taşımalı; yoksa devretme önerilemez."""
    from entropy.core.agy_bridge import AgyProcessBridge

    registry.ensure_defaults()
    monkeypatch.setattr(
        "entropy.agents.registry.AgentRegistry",
        lambda *a, **k: registry,
    )
    b = AgyProcessBridge()
    assert "[AJANLAR]" in b.agents_manifest_section()


# ---------------------------------------------------------------------------
# Görev kartları
# ---------------------------------------------------------------------------


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


def _card(**kw):
    base = dict(
        id=new_task_id("sprint raporu"),
        title="Sprint raporu",
        agent="yazar",
        provider="agy",
        skill="research",
        goal="Sprint çıktısını rapora dönüştür.",
        criteria=["Başlıklı markdown", "Kaynaklar bölümü"],
    )
    base.update(kw)
    return TaskCard(**base)


def test_task_card_roundtrip(board, vault):
    card = board.create(_card())
    assert card.path == vault / "Entropy" / "Tasks" / f"{card.id}.md"

    loaded = board.get(card.id)
    assert loaded.title == "Sprint raporu"
    assert loaded.status == "backlog"
    assert loaded.goal == "Sprint çıktısını rapora dönüştür."
    assert loaded.criteria == ["Başlıklı markdown", "Kaynaklar bölümü"]
    assert loaded.created_at

    board.update(replace(loaded, status="done", summary="Bitti."))
    assert board.get(card.id).status == "done"
    assert board.get(card.id).summary == "Bitti."

    assert [c.id for c in board.list(status="done")] == [card.id]
    assert board.list(status="running") == []
    assert board.delete(card.id) is True
    assert board.get(card.id) is None


def test_task_board_emits_task_cards_updated(board, qapp):
    seen = []
    bus.task_cards_updated.connect(seen.append)
    try:
        card = board.create(_card())
        board.delete(card.id)
    finally:
        bus.task_cards_updated.disconnect(seen.append)
    assert seen == [card.id, card.id]


def test_prompt_carries_agent_body_and_criteria(board, registry):
    registry.ensure_defaults()
    card = board.create(_card(agent="yazar"))
    prompt = board.build_prompt(card, agent_spec=registry.get("yazar"))
    assert "yazar ajanısın" in prompt
    assert "[GÖREV SÖZLEŞMESİ]" in prompt
    assert "Başlıklı markdown" in prompt
    assert card.goal in prompt


def test_run_uses_real_bridge_path_and_moves_card_to_review(board, registry, tmp_path, monkeypatch):
    """
    Gerçek yol: TaskBoard.run -> AgyProcessBridge.send_background_task_async ->
    Popen (taklit) -> akış ayrıştırma -> geri çağrı -> kart 'review'.
    """
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    registry.ensure_defaults()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = tmp_path
    monkeypatch.setattr(
        "entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db")
    )

    captured = {}
    done = threading.Event()

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return _FakeProc(_agy_lines("Rapor hazır."))

    monkeypatch.setattr("entropy.core.agy_bridge.subprocess.Popen", fake_popen)
    card = board.create(_card(agent="yazar", provider="agy"))
    monkeypatch.setattr("entropy.core.agy_bridge.bus.task_completed",
                        _Emitter(done, f"card-{card.id}"))
    task_id = board.run(card.id, bridge_factory=lambda provider: bridge)
    assert task_id == f"card-{card.id}"
    assert done.wait(timeout=10), "arka plan görevi bitmedi"

    # Ajan adı CLI'a --agent olarak geçmeli; kart ajansız çalışmamalı.
    assert "--agent" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--agent") + 1] == "yazar"
    # Görev sözleşmesi prompt'a girmiş olmalı.
    joined = " ".join(captured["cmd"])
    assert "GÖREV SÖZLEŞMESİ" in joined

    final = board.get(card.id)
    assert final.status == "review"
    assert "Rapor hazır." in final.summary
    assert final.started_at and final.finished_at


def test_run_marks_card_failed_when_process_fails(board, registry, tmp_path, monkeypatch):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    registry.ensure_defaults()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = tmp_path
    monkeypatch.setattr(
        "entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger2.db")
    )
    done = threading.Event()
    monkeypatch.setattr(
        "entropy.core.agy_bridge.subprocess.Popen",
        lambda cmd, **kw: _FakeProc([], returncode=1),
    )
    card = board.create(_card())
    monkeypatch.setattr("entropy.core.agy_bridge.bus.task_completed",
                        _Emitter(done, f"card-{card.id}"))
    board.run(card.id, bridge_factory=lambda provider: bridge)
    assert done.wait(timeout=10)
    assert board.get(card.id).status == "failed"


def test_run_is_idempotent_for_running_card(board, registry):
    registry.ensure_defaults()
    card = board.create(_card())
    board.update(replace(card, status="running"))
    calls = []
    assert board.run(card.id, bridge_factory=lambda p: calls.append(p)) is None
    assert calls == []


def test_run_picks_bridge_matching_card_provider(board, registry, monkeypatch):
    """Kart 'claude' diyorsa, etkin köprü agy olsa bile claude köprüsü kurulur."""
    registry.ensure_defaults()
    registry.update(replace(registry.get("analist"), provider="claude"))
    card = board.create(_card(agent="analist", provider="claude"))

    seen = {}

    class _Recorder:
        provider_name = "claude"

        def send_background_task_async(self, **kwargs):
            seen.update(kwargs)

    board.run(card.id, bridge_factory=lambda provider: (seen.setdefault("provider", provider), _Recorder())[1])
    assert seen["provider"] == "claude"
    assert seen["agent"] == "analist"
    assert seen["save_report"] is True


def test_finish_calls_wiki_and_agent_memory_when_available(board, registry, monkeypatch, tmp_path):
    """
    Bellek katmanı varsa çağrılır ve wiki sayfası output_paths'e girer;
    yoksa (import guard) kart yine doğru kapanır.
    """
    import sys
    import types

    wiki = types.ModuleType("entropy.brain.wiki")
    page = tmp_path / "wiki" / "sayfa.md"
    calls = {}

    def write_query_page(skill, title, body, meta):
        calls["wiki"] = (skill, title, body, meta)
        return page

    wiki.write_query_page = write_query_page

    mem = types.ModuleType("entropy.brain.agent_memory")

    def append_agent_memory(agent, entry):
        calls["memory"] = (agent, entry)

    mem.append_agent_memory = append_agent_memory

    monkeypatch.setitem(sys.modules, "entropy.brain.wiki", wiki)
    monkeypatch.setitem(sys.modules, "entropy.brain.agent_memory", mem)

    card = board.create(_card())
    board._finish(card.id, "Ajan çıktısı.", True)

    final = board.get(card.id)
    assert final.status == "review"
    assert str(page) in final.output_paths
    assert calls["wiki"][0] == "research"
    assert calls["memory"][0] == "yazar"


def test_finish_closes_card_even_if_memory_layer_raises(board, monkeypatch):
    """Bellek katmanı patlarsa kart yine de kapanmalı; ajan katmanı ona bağımlı değil."""
    import sys
    import types

    broken = types.ModuleType("entropy.brain.wiki")

    def boom(*args, **kwargs):
        raise RuntimeError("wiki bozuk")

    broken.write_query_page = boom
    monkeypatch.setitem(sys.modules, "entropy.brain.wiki", broken)

    card = board.create(_card())
    board._finish(card.id, "Çıktı.", True)
    final = board.get(card.id)
    assert final.status == "review"
    assert final.summary == "Çıktı."


# ---------------------------------------------------------------------------
# main.py bağlantısı ve izleyiciler
# ---------------------------------------------------------------------------


def test_main_compiles_agents_on_startup_and_project_change():
    """Derleme açılışta koşmalı ve proje değişimine bağlı olmalı."""
    import inspect

    from entropy import main as main_mod

    src = inspect.getsource(main_mod.main)
    assert "_compile_agents()" in src
    assert "project_changed.connect(_compile_agents)" in src
    assert "start_agent_watchers()" in src
    # Durdurma kapanış kancasının İÇİNDE olmalı; sonrasında çağrı işe yaramaz.
    assert src.index("def _on_quit") < src.index("stop_agent_watchers()")


def test_watchers_emit_on_new_files(vault, qapp):
    """Kasaya elle düşen bir kart/ajan, yeniden başlatmadan haber vermeli."""
    from entropy.agents.watchers import AgentsWatcher, TasksWatcher

    agents_seen, tasks_seen = [], []
    bus.agents_updated.connect(agents_seen.append)
    bus.task_cards_updated.connect(tasks_seen.append)
    aw = AgentsWatcher(vault_path=vault).start()
    tw = TasksWatcher(vault_path=vault).start()
    try:
        AgentRegistry(vault_path=vault).ensure_defaults()
        TaskBoard(vault_path=vault).create(_card())
        agents_seen.clear()
        tasks_seen.clear()
        # Yoklama yolunu doğrudan sür: zamanlayıcıyı beklemek testi yavaşlatır.
        aw._check_now()
        tw._check_now()
    finally:
        aw.stop()
        tw.stop()
        bus.agents_updated.disconnect(agents_seen.append)
        bus.task_cards_updated.disconnect(tasks_seen.append)

    assert agents_seen == [""]
    assert tasks_seen == [""]
    # Değişiklik yokken ikinci kontrol sinyal yaymamalı (sonsuz döngü olmasın).
    aw2 = AgentsWatcher(vault_path=vault)
    before = list(agents_seen)
    aw2._check_now()
    assert agents_seen == before


class _Emitter:
    """
    bus.task_completed yerine geçen, testin beklediği olayı kuran nesne.

    Görev kimliği süzgeci şart: `bus` süreç genelinde tek nesne ve önceki bir
    testten artakalan köprü iş parçacığı da bu sinyali yayınlıyor. Süzgeçsiz
    sürüm o yayınla erkenden tetikleniyor ve test kartı henüz yazılmadan
    okuyordu (kaynağı belirsiz "assert 'running' == 'failed'" hataları).
    """

    def __init__(self, event, task_id=None):
        self._event = event
        self._task_id = task_id

    def emit(self, *args):
        if self._task_id is not None and (not args or args[0] != self._task_id):
            return
        self._event.set()


def test_finish_writes_memory_into_own_vault(board, vault):
    """
    _finish, wiki sayfasını ve ajan belleğini panonun KENDİ kasasına yazmalı.

    Regresyon: vault_path aktarılmadığında bu çağrılar genel yapılandırma
    kasasına düşüyordu; testler kullanıcının gerçek Obsidian kasasını kirletti.
    """
    card = board.create(_card())
    board._finish(card.id, "Görev çıktısı gövdesi.", True)

    memory_file = vault / "Entropy" / "Agents" / "yazar" / "MEMORY.md"
    assert memory_file.exists(), "ajan belleği panonun kasasına yazılmadı"
    assert "Sprint raporu" in memory_file.read_text(encoding="utf-8")

    # Üretilen tüm çıktı yolları bu kasanın altında kalmalı.
    for path in board.get(card.id).output_paths:
        assert str(vault) in str(path), f"kasa dışına yazıldı: {path}"
