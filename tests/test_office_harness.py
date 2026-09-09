"""
FAZ 3a — ofis kayıt defteri, ofis harness'ı, model eşlemesi ve /desk komutları.

Hiçbir test gerçek agy/claude süreci başlatmaz. İki katman kullanılır:
  - Gerçek `TaskBoard` + gerçek `AgentRegistry`/`OfficeRegistry` (tmp kasa),
  - Köprü olarak `subprocess.Popen` taklidiyle sürülen GERÇEK `AgyProcessBridge`
    (uçtan uca akış) ya da sırayla yanıt döndüren küçük bir sahte köprü
    (paralellik/retry/bütçe gibi zamanlama senaryoları için).
"""

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from entropy.agents.compile import render_agy_agent, render_claude_agent, resolve_model
from entropy.agents.harness import (
    GRADE_THRESHOLD,
    OfficeHarness,
    extract_json_block,
)
from entropy.agents.offices import (
    OFFICE_FILENAME,
    OfficeRegistry,
    OfficeSpec,
    offices_manifest,
)
from entropy.agents.registry import AgentRegistry, AgentSpec
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id


# ---------------------------------------------------------------------------
# Ortak düzenek
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    """Kasa yolunu teste özel dizine çeker (kullanıcı kasası kirlenmesin)."""
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    return tmp_path / "Vault"


@pytest.fixture(autouse=True)
def clean_active_registry():
    """Süreç genelindeki 'süren zincir' tablosu testler arasında sızmasın."""
    OfficeHarness._active.clear()
    yield
    OfficeHarness._active.clear()


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture
def offices(vault):
    return OfficeRegistry(vault_path=vault)


@pytest.fixture
def registry(vault):
    return AgentRegistry(vault_path=vault)


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


@pytest.fixture
def seeded(registry, offices):
    """Tohum ajanlar + tohum ofis (gerçek `ensure_defaults` yolu)."""
    registry.ensure_defaults()
    offices.ensure_defaults()
    return offices.get("arastirma-ofisi")


class _ScriptedBridge:
    """
    Sırayla hazır yanıt döndüren köprü.

    Gerçek köprünün sözleşmesinden yalnızca `send_background_task_async` ve
    `terminate_background_task` kullanılıyor. Alt kartlar arasında paralelliği
    ölçebilmek için sonuçlar elle serbest bırakılabiliyor (`autorun=False`).
    """

    provider_name = "agy"

    def __init__(self, responses, autorun=True):
        self.responses = list(responses)
        self.autorun = autorun
        self.calls = []           # (task_id, agent, prompt)
        self.pending = []         # autorun=False iken bekleyen (task_id, cb)
        self.max_concurrent = 0
        self.terminated = []
        self._lock = threading.RLock()

    def _next(self, task_id, prompt):
        for idx, (matcher, text, ok) in enumerate(self.responses):
            if matcher in task_id:
                self.responses.pop(idx)
                return text, ok
        return "", False

    def send_background_task_async(self, task_id, task_name, prompt, mode=None,
                                   on_result=None, save_report=True, agent=None, **kw):
        with self._lock:
            self.calls.append((task_id, agent, prompt))
            text, ok = self._next(task_id, prompt)
            if not self.autorun:
                self.pending.append((task_id, on_result, text, ok))
                self.max_concurrent = max(self.max_concurrent, len(self.pending))
                return task_id
        if on_result is not None:
            on_result(text, ok)
        return task_id

    def release_one(self):
        """Bekleyen İLK görevi tamamlar; yeni doğan görevler beklemede kalır."""
        with self._lock:
            if not self.pending:
                return False
            task_id, cb, text, ok = self.pending.pop(0)
        if cb is not None:
            cb(text, ok)
        return True

    def release_all(self):
        """Bekleyen tüm görevleri tamamlar (autorun=False düzeneği)."""
        while True:
            with self._lock:
                if not self.pending:
                    return
                task_id, cb, text, ok = self.pending.pop(0)
            if cb is not None:
                cb(text, ok)

    def terminate_background_task(self, task_id):
        self.terminated.append(task_id)
        return True


def _plan_json(*titles, agent="arastirmaci"):
    return "İşte plan:\n```json\n" + json.dumps({
        "subtasks": [
            {"title": t, "goal": f"{t} hedefi", "criteria": [f"{t} ölçütü"],
             "agent": agent, "provider": "agy", "model": ""}
            for t in titles
        ]
    }, ensure_ascii=False) + "\n```"


def _grades_json(board, parent_id, grade=0.9):
    """Değerlendirici yanıtı; not tek değer ya da id->not sözlüğü olabilir."""
    def _build(_text, _ok=True):
        parent = board.get(parent_id)
        rows = []
        for child_id in parent.children:
            child = board.get(child_id)
            value = grade(child) if callable(grade) else grade
            rows.append({"id": child_id, "grade": value,
                         "verdict": "ok" if value >= GRADE_THRESHOLD else "eksik",
                         "missing": [] if value >= GRADE_THRESHOLD else ["kaynak yok"]})
        return "```json\n" + json.dumps({"grades": rows}) + "\n```"
    return _build


def _office_card(board, office="arastirma-ofisi", title="Pazar araştırması"):
    return board.create(TaskCard(
        id=new_task_id(title),
        title=title,
        status="backlog",
        agent="orkestrator",
        provider="agy",
        goal="Pazarı araştır ve rapora bağla.",
        criteria=["Kaynak göster"],
        office=office,
    ))


# ---------------------------------------------------------------------------
# Ofis kayıt defteri
# ---------------------------------------------------------------------------


def test_office_roundtrip_and_defaults(offices, vault):
    created = offices.ensure_defaults()
    assert created == ["arastirma-ofisi"]
    assert (vault / "Entropy" / "Offices" / "arastirma-ofisi" / OFFICE_FILENAME).is_file()

    spec = offices.get("arastirma-ofisi")
    assert spec.orchestrator == "orkestrator"
    assert spec.evaluator == "degerlendirici"
    assert spec.members == ["arastirmaci", "analist", "yazar"]
    assert spec.max_parallel == 2
    assert spec.budget_tokens > 0
    assert "Kabul standartları" in spec.charter
    # İkinci çağrı yeniden yazmaz; silinen ofis diriltilmez.
    assert offices.ensure_defaults() == []
    offices.delete("arastirma-ofisi")
    assert offices.get("arastirma-ofisi") is None


def test_office_crud_and_signal(offices, qapp):
    from entropy.core.event_bus import bus

    seen = []
    bus.offices_updated.connect(seen.append)
    try:
        offices.create(OfficeSpec(name="deney", purpose="Deney", orchestrator="orkestrator",
                                  members=["analist"], max_parallel=3, budget_tokens=999))
        assert offices.get("deney").max_parallel == 3
        offices.update(replace(offices.get("deney"), purpose="Yeni amaç"))
        assert offices.get("deney").purpose == "Yeni amaç"
        assert offices.delete("deney") is True
    finally:
        bus.offices_updated.disconnect(seen.append)
    assert "deney" in seen


def test_offices_manifest_lists_and_states_rule(offices):
    offices.ensure_defaults()
    text = offices_manifest(offices)
    assert "arastirma-ofisi" in text
    assert "/desk task" in text
    # Bütçe: ~120 token.
    assert len(text) < 700


def test_offices_manifest_empty_without_offices(offices):
    assert offices_manifest(offices) == ""


# ---------------------------------------------------------------------------
# Ajan/kart şema genişlemeleri
# ---------------------------------------------------------------------------


def test_agent_spec_office_and_models_roundtrip(registry):
    registry.create(AgentSpec(
        name="ikili", role="orchestrator", office="deney",
        model="gemini-3.8-flash-high",
        models={"agy": "gemini-3.8-flash-low", "claude": "claude-opus-5"},
        prompt="Planla.",
    ))
    loaded = registry.get("ikili")
    assert loaded.office == "deney"
    assert loaded.office_role == "orchestrator"
    assert loaded.models["claude"] == "claude-opus-5"
    assert loaded.model_for("agy") == "gemini-3.8-flash-low"
    # Bilinmeyen rol worker'a düşer.
    assert AgentSpec(name="x", role="research").office_role == "worker"


def test_seed_agents_include_orchestrator_and_evaluator(registry):
    registry.ensure_defaults()
    names = [s.name for s in registry.list()]
    assert "orkestrator" in names and "degerlendirici" in names
    assert registry.get("orkestrator").office_role == "orchestrator"
    assert registry.get("degerlendirici").office_role == "evaluator"
    assert "subtasks" in registry.get("orkestrator").prompt
    assert "grades" in registry.get("degerlendirici").prompt


def test_task_card_office_fields_roundtrip(board):
    card = board.create(TaskCard(id="ust", title="Üst", office="deney",
                                 children=["a1", "a2"]))
    child = board.create(TaskCard(id="a1", title="Alt", office="deney", parent="ust",
                                  grade=0.75, verdict="iyi", attempt=1))
    assert board.get(card.id).children == ["a1", "a2"]
    loaded = board.get(child.id)
    assert loaded.parent == "ust" and loaded.attempt == 1
    assert loaded.grade == pytest.approx(0.75)
    assert loaded.verdict == "iyi"
    # Notlanmamış kartta grade None kalmalı (0.0 ile karışmasın).
    assert board.get(card.id).grade is None


# ---------------------------------------------------------------------------
# Model eşlemesi
# ---------------------------------------------------------------------------


def test_gemini_model_never_reaches_claude_compilation():
    spec = AgentSpec(name="arastirmaci", model="gemini-3.8-flash-high", prompt="x")
    assert resolve_model(spec, "claude") == "inherit"
    text = render_claude_agent(spec)
    assert "gemini" not in text.lower()
    assert "model: inherit" in text


def test_claude_model_maps_to_gemini_in_agy_compilation():
    spec = AgentSpec(name="a", model="claude-opus-5", prompt="x")
    assert resolve_model(spec, "agy") == "gemini-3.8-flash-high"
    assert "claude" not in render_agy_agent(spec).lower()
    # Claude derlemesinde kendi adı korunur (kısaltılmış etikete iner).
    assert "opus" in render_claude_agent(spec)


def test_explicit_models_map_wins_over_single_model_field():
    spec = AgentSpec(name="a", model="gemini-3.8-flash-high",
                     models={"claude": "claude-sonnet-4-6"}, prompt="x")
    assert resolve_model(spec, "claude") == "claude-sonnet-4-6"
    assert "sonnet" in render_claude_agent(spec)


def test_compiled_seed_agent_file_has_no_gemini_in_claude_format(registry, tmp_path, monkeypatch):
    """Kabul ölçütü: derlenen .claude/agents/arastirmaci.md içinde 'gemini' geçmez."""
    import sys

    monkeypatch.setattr(sys.modules["entropy.core.config"], "APP_ROOT",
                        tmp_path / "app", raising=False)
    (tmp_path / "app").mkdir()
    registry.ensure_defaults()
    registry.compile_all(tmp_path / "app")
    text = (tmp_path / "app" / ".claude" / "agents" / "arastirmaci.md").read_text(encoding="utf-8")
    assert "gemini" not in text.lower()
    agy_text = (tmp_path / "app" / ".agents" / "agents" / "arastirmaci" / "agent.md").read_text(encoding="utf-8")
    assert "model: flash" in agy_text


# ---------------------------------------------------------------------------
# JSON ayıklama
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    '```json\n{"subtasks": []}\n```',
    '```\n{"subtasks": []}\n```',
    'Önce açıklama. {"subtasks": []} Sonra da laf.',
])
def test_extract_json_block_handles_wrappers(text):
    assert extract_json_block(text) == {"subtasks": []}


def test_extract_json_block_returns_none_for_prose():
    assert extract_json_block("Plan yapamadım, üzgünüm.") is None


# ---------------------------------------------------------------------------
# Harness: uçtan uca
# ---------------------------------------------------------------------------


def _harness(office_name, board, registry, offices, bridge):
    return OfficeHarness(office_name, board=board, registry=registry, offices=offices,
                         bridge_factory=lambda provider: bridge)


def test_end_to_end_plan_run_evaluate(seeded, board, registry, offices, tmp_path):
    holder = {}
    bridge = _ScriptedBridge([
        ("office-plan", _plan_json("Kaynak taraması", "Sayısal analiz", "Rapor"), True),
        ("card-", "Alt görev çıktısı 1.", True),
        ("card-", "Alt görev çıktısı 2.", True),
        ("card-", "Alt görev çıktısı 3.", True),
        ("office-eval", "", True),  # gerçek metin aşağıda üretiliyor
    ])
    card = _office_card(board)
    holder["grades"] = _grades_json(board, card.id, grade=0.9)

    # Değerlendirici yanıtı alt kart kimliklerini bilmeli: çağrı anında üretilir.
    original = bridge._next

    def _next(task_id, prompt, _orig=original):
        if "office-eval" in task_id:
            _orig(task_id, prompt)
            return holder["grades"](prompt), True
        return _orig(task_id, prompt)

    bridge._next = _next

    h = _harness("arastirma-ofisi", board, registry, offices, bridge)
    assert h.start(card.id) is True

    parent = board.get(card.id)
    assert parent.status == "review"
    assert len(parent.children) == 3
    assert parent.grade == pytest.approx(0.9)
    for child_id in parent.children:
        child = board.get(child_id)
        assert child.parent == card.id
        assert child.office == "arastirma-ofisi"
        assert child.status == "review"
        assert child.grade == pytest.approx(0.9)
    # Ofis raporu üst kartın özetinde toplanmış olmalı.
    assert "Alt görev çıktısı 1." in parent.summary
    # Planlama ve değerlendirme çağrıları doğru ajanla ve rapor kaydetmeden.
    agents = [c[1] for c in bridge.calls]
    assert agents[0] == "orkestrator"
    assert "degerlendirici" in agents


def test_parallelism_is_capped_by_max_parallel(seeded, board, registry, offices):
    offices.update(replace(seeded, max_parallel=2))
    bridge = _ScriptedBridge([
        ("office-plan", _plan_json("A", "B", "C", "D"), True),
        ("card-", "çıktı", True), ("card-", "çıktı", True),
        ("card-", "çıktı", True), ("card-", "çıktı", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ], autorun=False)

    card = _office_card(board)
    h = _harness("arastirma-ofisi", board, registry, offices, bridge)
    h.start(card.id)

    # Planlama bekliyor: yalnızca onu tamamla, alt kartlar başlasın.
    bridge.release_one()
    parent = board.get(card.id)
    assert len(parent.children) == 4
    running = [c for c in parent.children if board.get(c).status == "running"]
    assert len(running) == 2, "aynı anda en çok max_parallel alt kart koşmalı"

    bridge.release_all()
    assert board.get(card.id).status == "review"
    assert bridge.max_concurrent <= 2


def test_low_grade_subtask_is_retried_once(seeded, board, registry, offices):
    state = {"round": 0}

    bridge = _ScriptedBridge([("office-plan", _plan_json("A", "B"), True)])
    card = _office_card(board)

    def _next(task_id, prompt):
        if "office-plan" in task_id:
            return _plan_json("A", "B"), True
        if "card-" in task_id:
            return "çıktı", True
        # Değerlendirme: ilk turda A düşük not alır, ikinci turda düzelir.
        parent = board.get(card.id)
        state["round"] += 1
        rows = []
        for child_id in parent.children:
            child = board.get(child_id)
            if child.title == "A" and state["round"] == 1:
                rows.append({"id": child_id, "grade": 0.2, "verdict": "eksik",
                             "missing": ["kaynak"]})
            else:
                rows.append({"id": child_id, "grade": 0.95, "verdict": "ok", "missing": []})
        return "```json\n" + json.dumps({"grades": rows}) + "\n```", True

    bridge._next = _next
    h = _harness("arastirma-ofisi", board, registry, offices, bridge)
    h.start(card.id)

    parent = board.get(card.id)
    children = [board.get(c) for c in parent.children]
    a = next(c for c in children if c.title == "A")
    b = next(c for c in children if c.title == "B")
    assert a.attempt == 1, "eşiğin altındaki alt kart bir kez yeniden koşmalı"
    assert b.attempt == 0
    assert a.grade == pytest.approx(0.95)
    assert "kaynak" in a.notes or "eksik" in a.notes
    # A iki kez koşmuş olmalı, B bir kez; değerlendirme en çok iki tur.
    card_calls = [c for c in bridge.calls if c[0].startswith("card-")]
    assert len(card_calls) == 3
    assert len([c for c in bridge.calls if "office-eval" in c[0]]) == 2
    assert parent.status == "review"


def test_budget_overrun_stops_chain_and_fails_card(seeded, board, registry, offices):
    # Bütçe planlama yanıtını bile karşılamayacak kadar küçük.
    offices.update(replace(seeded, budget_tokens=5))
    bridge = _ScriptedBridge([("office-plan", _plan_json("A", "B"), True)])
    card = _office_card(board)
    h = _harness("arastirma-ofisi", board, registry, offices, bridge)
    h.start(card.id)

    parent = board.get(card.id)
    assert parent.status == "failed"
    assert "bütçe" in parent.summary.lower()
    # Zincir durdu: hiçbir alt kart koşmadı.
    assert not [c for c in bridge.calls if c[0].startswith("card-")]


def test_invalid_plan_json_fails_card_without_running_children(seeded, board, registry, offices):
    bridge = _ScriptedBridge([("office-plan", "Bunu yapamam.", True)])
    card = _office_card(board)
    _harness("arastirma-ofisi", board, registry, offices, bridge).start(card.id)
    parent = board.get(card.id)
    assert parent.status == "failed"
    assert not parent.children


def test_unknown_agent_in_plan_falls_back_to_office_member(seeded, board, registry, offices):
    bridge = _ScriptedBridge([
        ("office-plan", _plan_json("A", agent="olmayan-ajan"), True),
        ("card-", "çıktı", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    card = _office_card(board)
    _harness("arastirma-ofisi", board, registry, offices, bridge).start(card.id)
    child = board.get(board.get(card.id).children[0])
    assert child.agent in offices.get("arastirma-ofisi").members


def test_office_progress_signal_reports_phases(seeded, board, registry, offices, qapp):
    from entropy.core.event_bus import bus

    seen = []
    bus.office_progress.connect(lambda o, c, p: seen.append(p))
    bridge = _ScriptedBridge([
        ("office-plan", _plan_json("A"), True),
        ("card-", "çıktı", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    card = _office_card(board)
    _harness("arastirma-ofisi", board, registry, offices, bridge).start(card.id)
    assert seen[0] == "planning"
    assert "running" in seen and "evaluating" in seen
    assert seen[-1] == "done"


def test_stop_kills_children_and_fails_parent(seeded, board, registry, offices):
    bridge = _ScriptedBridge([
        ("office-plan", _plan_json("A", "B"), True),
        ("card-", "çıktı", True), ("card-", "çıktı", True),
    ], autorun=False)
    card = _office_card(board)
    h = _harness("arastirma-ofisi", board, registry, offices, bridge)
    h.start(card.id)
    bridge.release_one()  # planlama bitsin, alt kartlar başlasın

    assert h.stop(card.id) is True
    parent = board.get(card.id)
    assert parent.status == "failed"
    assert "durduruldu" in parent.summary.lower()


# ---------------------------------------------------------------------------
# Kesintiden devam
# ---------------------------------------------------------------------------


def test_resume_all_continues_half_finished_office_card(seeded, board, registry, offices):
    """Kapanışta yarım kalan zincir: bir alt kart bitmiş, biri 'running' öksüz."""
    parent = board.create(TaskCard(id="ust-1", title="Yarım iş", status="running",
                                   office="arastirma-ofisi", agent="orkestrator",
                                   children=["alt-1", "alt-2"]))
    board.create(TaskCard(id="alt-1", title="Biten", status="review", parent="ust-1",
                          office="arastirma-ofisi", agent="arastirmaci",
                          summary="tamam", criteria=["ölçüt"]))
    board.create(TaskCard(id="alt-2", title="Öksüz", status="running", parent="ust-1",
                          office="arastirma-ofisi", agent="arastirmaci",
                          criteria=["ölçüt"]))

    bridge = _ScriptedBridge([
        ("card-", "yeniden koşuldu", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    resumed = OfficeHarness.resume_all(board=board, offices=offices,
                                       bridge_factory=lambda provider: bridge)
    assert resumed == ["ust-1"]
    assert board.get("alt-2").status == "review"
    assert board.get("ust-1").status == "review"
    # Planlama YENİDEN koşmamalı: alt kartlar zaten var.
    assert not [c for c in bridge.calls if "office-plan" in c[0]]


def test_resume_all_replans_when_planning_never_finished(seeded, board, registry, offices):
    board.create(TaskCard(id="ust-2", title="Plansız", status="running",
                          office="arastirma-ofisi", agent="orkestrator"))
    bridge = _ScriptedBridge([
        ("office-plan", _plan_json("A"), True),
        ("card-", "çıktı", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    resumed = OfficeHarness.resume_all(board=board, offices=offices,
                                       bridge_factory=lambda provider: bridge)
    assert resumed == ["ust-2"]
    assert [c for c in bridge.calls if "office-plan" in c[0]]
    assert board.get("ust-2").status == "review"


def test_resume_all_ignores_non_office_and_finished_cards(seeded, board, offices):
    board.create(TaskCard(id="serbest", title="Ajan kartı", status="running", agent="yazar"))
    board.create(TaskCard(id="bitmis", title="Bitti", status="review",
                          office="arastirma-ofisi", children=["x"]))
    bridge = _ScriptedBridge([])
    assert OfficeHarness.resume_all(board=board, offices=offices,
                                    bridge_factory=lambda p: bridge) == []
    assert bridge.calls == []


# ---------------------------------------------------------------------------
# Bellek/rapor kancaları
# ---------------------------------------------------------------------------


def test_finalize_calls_wiki_and_office_memory_when_available(seeded, board, registry,
                                                              offices, monkeypatch, tmp_path):
    import sys
    import types

    seen = {}
    wiki = types.ModuleType("entropy.memory.wiki")
    wiki.write_query_page = lambda skill, title, body, meta: (
        seen.__setitem__("wiki", (title, meta)), tmp_path / "page.md")[1]
    mem = types.ModuleType("entropy.memory.agent_memory")
    mem.append_office_memory = lambda name, entry: seen.__setitem__("office_mem", (name, entry))
    mem.append_agent_memory = lambda name, entry: seen.__setitem__("agent_mem", (name, entry))
    monkeypatch.setitem(sys.modules, "entropy.memory.wiki", wiki)
    monkeypatch.setitem(sys.modules, "entropy.memory.agent_memory", mem)

    bridge = _ScriptedBridge([
        ("office-plan", _plan_json("A"), True),
        ("card-", "çıktı", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    card = _office_card(board)
    _harness("arastirma-ofisi", board, registry, offices, bridge).start(card.id)

    assert seen["wiki"][1]["office"] == "arastirma-ofisi"
    assert seen["office_mem"][0] == "arastirma-ofisi"
    assert seen["office_mem"][1]["kind"] == "office"
    # Ajan belleğine yazılan kayıt alt kartın kendi ajanına aittir; ofis kaydı
    # `append_office_memory` üzerinden gider (ofis adına ikinci kayıt yok).
    assert seen["agent_mem"][0] == "arastirmaci"
    assert str(tmp_path / "page.md") in board.get(card.id).output_paths


def test_finalize_survives_missing_memory_layer(seeded, board, registry, offices):
    bridge = _ScriptedBridge([
        ("office-plan", _plan_json("A"), True),
        ("card-", "çıktı", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    card = _office_card(board)
    _harness("arastirma-ofisi", board, registry, offices, bridge).start(card.id)
    assert board.get(card.id).status == "review"


# ---------------------------------------------------------------------------
# Gerçek köprü yolu (Popen taklidi)
# ---------------------------------------------------------------------------


class _FakeProc:
    """stream-json satırlarını akıtan sahte süreç (gerçek Popen'in yerine)."""

    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 999002
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


def _agy_lines(text):
    return [
        json.dumps({"event": "step_update", "step_update": {"text_delta": text}}) + "\n",
        json.dumps({"event": "result", "result": {
            "response": text,
            "usage": {"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
        }}) + "\n",
    ]


def test_real_bridge_path_plans_and_runs_office_chain(seeded, board, registry, offices,
                                                      tmp_path, monkeypatch):
    """
    Gerçek yol: OfficeHarness -> AgyProcessBridge.send_background_task_async ->
    Popen (taklit) -> akış ayrıştırma -> geri çağrı. Kota harcanmaz.
    """
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    bridge = AgyProcessBridge()
    bridge.active_project_dir = tmp_path

    card = _office_card(board)
    commands = []
    finished = threading.Event()

    def fake_popen(cmd, **kwargs):
        commands.append(list(cmd))
        joined = " ".join(str(c) for c in cmd)
        if "office-plan" in joined or "planlama" in joined or len(commands) == 1:
            return _FakeProc(_agy_lines(_plan_json("Tek alt görev")))
        if any("degerlendirici" == c for c in cmd) and len(commands) > 2:
            parent = board.get(card.id)
            rows = [{"id": cid, "grade": 0.8, "verdict": "ok", "missing": []}
                    for cid in parent.children]
            finished.set()
            return _FakeProc(_agy_lines("```json\n" + json.dumps({"grades": rows}) + "\n```"))
        return _FakeProc(_agy_lines("Alt görev çıktısı."))

    monkeypatch.setattr("entropy.core.agy_bridge.subprocess.Popen", fake_popen)

    harness = OfficeHarness("arastirma-ofisi", board=board, registry=registry,
                            offices=offices, bridge_factory=lambda provider: bridge)
    assert harness.start(card.id) is True
    assert finished.wait(timeout=20), "değerlendirme adımına ulaşılamadı"

    # Planlama çağrısı orkestratör ajanıyla ve rapor kaydetmeden koşmalı.
    plan_cmd = commands[0]
    assert "--agent" in plan_cmd
    assert plan_cmd[plan_cmd.index("--agent") + 1] == "orkestrator"
    assert "OFİS TÜZÜĞÜ" in " ".join(str(c) for c in plan_cmd)

    parent = board.get(card.id)
    assert parent.children, "alt kartlar yazılmadı"
    assert board.get(parent.children[0]).summary.startswith("Alt görev çıktısı")


# ---------------------------------------------------------------------------
# Komutlar
# ---------------------------------------------------------------------------


def test_offices_command_lists_offices(seeded):
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/offices", bridge=None)
    assert "arastirma-ofisi" in out
    assert "orkestrator" in out


def test_desk_command_shows_offices_and_states(seeded, board):
    from entropy.core.slash_commands import try_handle_local_command

    board.create(TaskCard(id="k1", title="Süren iş", status="running",
                          office="arastirma-ofisi"))
    out = try_handle_local_command("/desk", bridge=None)
    assert "Agent Desk" in out
    assert "Süren iş" in out


def test_desk_task_command_creates_card_and_starts_harness(seeded, board, offices, monkeypatch):
    from entropy.core.slash_commands import try_handle_local_command

    started = {}

    def fake_start(self, card_id):
        started["card"] = card_id
        started["office"] = self.office_name
        return True

    monkeypatch.setattr(OfficeHarness, "start", fake_start)
    out = try_handle_local_command(
        "/desk task arastirma-ofisi Pazar raporu :: Rakipleri karşılaştır", bridge=None)
    assert "Ofise Devredildi" in out
    assert started["office"] == "arastirma-ofisi"
    card = board.get(started["card"])
    assert card.office == "arastirma-ofisi"
    assert card.goal == "Rakipleri karşılaştır"
    assert card.agent == "orkestrator"


def test_desk_task_rejects_unknown_office(seeded):
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/desk task yok-ofis Başlık :: Hedef", bridge=None)
    assert "ofis yok" in out
    assert "arastirma-ofisi" in out


def test_desk_stop_command_stops_chain(seeded, board, monkeypatch):
    from entropy.core.slash_commands import try_handle_local_command

    board.create(TaskCard(id="k9", title="Durdurulacak", status="running",
                          office="arastirma-ofisi"))
    stopped = {}
    monkeypatch.setattr(OfficeHarness, "stop",
                        lambda self, cid: stopped.setdefault("id", cid) is not None)
    out = try_handle_local_command("/desk stop k9", bridge=None)
    assert stopped["id"] == "k9"
    assert "Durduruldu" in out


def test_desk_stop_refuses_non_office_card(seeded, board):
    from entropy.core.slash_commands import try_handle_local_command

    board.create(TaskCard(id="serbest", title="Ajan kartı", status="running", agent="yazar"))
    out = try_handle_local_command("/desk stop serbest", bridge=None)
    assert "/task stop" in out


def test_desk_commands_are_registered_as_local():
    from entropy.core.slash_commands import LOCAL_COMMANDS

    names = {c.name for c in LOCAL_COMMANDS}
    assert {"/desk", "/offices"} <= names


# ---------------------------------------------------------------------------
# Önyükleme ve manifest
# ---------------------------------------------------------------------------


def test_bootstrap_seeds_offices_after_agents(vault, tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(sys.modules["entropy.core.config"], "APP_ROOT",
                        tmp_path / "app", raising=False)
    (tmp_path / "app").mkdir()
    from entropy.agents.bootstrap import bootstrap_agents

    result = bootstrap_agents(project_dir=tmp_path / "app", vault_path=vault)
    assert result.ok
    assert "arastirma-ofisi" in result.offices_created
    assert {"orkestrator", "degerlendirici"} <= set(result.created)
    # Ofisin orkestratörü gerçekten kasada olmalı.
    assert AgentRegistry(vault_path=vault).get("orkestrator") is not None
    assert "ofisler" in result.summary()


def test_bridge_cognitive_context_includes_offices_section(seeded, monkeypatch):
    from entropy.core.agy_bridge import AgyProcessBridge

    bridge = AgyProcessBridge()
    monkeypatch.setattr(bridge, "agents_manifest_section", lambda: "")
    section = bridge.offices_manifest_section()
    assert "[OFİSLER]" in section
    assert "arastirma-ofisi" in section
