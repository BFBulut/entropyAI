"""
FAZ 3 kapanış düzeltmeleri: geri çağrı sözleşmesi, kilit paralelliği, kart
gidiş-dönüşü, tohum tamamlama ve gerçek bütçe koruması.

Hiçbir test gerçek agy/claude süreci başlatmaz: `subprocess.Popen` taklit
edilir, kota harcanmaz.
"""

import json
import threading
import time
from dataclasses import replace

import pytest

from entropy.agents.harness import OfficeHarness
from entropy.agents.desk_registry import DeskOffice as OfficeSpec, DeskRegistry as OfficeRegistry
from entropy.agents.registry import (
    DEFAULT_AGENTS,
    SEED_MARKER_FILENAME,
    AgentRegistry,
    AgentSpec,
)
from entropy.agents.tasks import (
    TaskBoard,
    TaskCard,
    card_needs_write,
    new_task_id,
    trim_to_sections,
)
from entropy.core.project_lock import LOCK_TIMEOUT_MARKER, project_lock_manager


# ---------------------------------------------------------------------------
# Düzenek
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    return tmp_path / "Vault"


@pytest.fixture(autouse=True)
def clean_active_registry():
    OfficeHarness._active.clear()
    yield
    OfficeHarness._active.clear()


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


@pytest.fixture
def registry(vault):
    return AgentRegistry(vault_path=vault)


@pytest.fixture
def offices(vault):
    return OfficeRegistry(vault_path=vault)


# Faz 6: tohum ofis yok; ofisi ve kadrosunu test kurar. Ajanlar ofisin KENDİ
# defterine yazılır (Entropy'nin `Entropy/Agents` kadrosuna değil).
@pytest.fixture
def seeded(registry, offices):
    offices.create(OfficeSpec(
        name="arastirma-ofisi",
        purpose="Araştırır.",
        default_model="gemini-3.8-flash-high",
        charter="Kabul standartları: kaynaklı yaz.",
    ))
    agents = offices.agents("arastirma-ofisi")
    for name in ("arastirmaci", "analist", "yazar"):
        agents.update(AgentSpec(name=name, role="worker", description=f"{name} rolü",
                                provider="agy", tools_policy="read-write"))
    agents.update(AgentSpec(name="degerlendirici", role="evaluator",
                            description="notlar", provider="agy",
                            tools_policy="read-only"))
    return offices.get("arastirma-ofisi")


class _FakeProc:
    """stream-json satırlarını akıtan sahte süreç."""

    def __init__(self, lines, returncode=0, hold=None):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 999003
        self.stdin = None
        self.stdout = self
        self._hold = hold

    def readline(self):
        if not self._lines and self._hold is not None:
            # Son satırdan önce bekle: iki alt kartın gerçekten aynı anda
            # koştuğunu ölçebilmek için.
            self._hold.wait(10)
            self._hold = None
        return self._lines.pop(0) if self._lines else ""

    def close(self):
        pass

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


def _agy_lines(text, total=60):
    return [
        json.dumps({"event": "step_update", "step_update": {"text_delta": text}}) + "\n",
        json.dumps({"event": "result", "result": {
            "response": text,
            "usage": {"input_tokens": total - 10, "output_tokens": 10, "total_tokens": total},
        }}) + "\n",
    ]


def _plan_json(*titles, agent="arastirmaci"):
    return "```json\n" + json.dumps({
        "subtasks": [
            {"title": t, "goal": f"{t} hedefi", "criteria": [f"{t} ölçütü"],
             "agent": agent, "provider": "agy", "model": ""}
            for t in titles
        ]
    }, ensure_ascii=False) + "\n```"


def _office_card(board, title="Pazar araştırması"):
    return board.create(TaskCard(
        id=new_task_id(title), title=title, status="backlog", agent="orkestrator",
        provider="agy", goal="Pazarı araştır.", criteria=["Kaynak göster"],
        office="arastirma-ofisi",
    ))


def _wait_until(predicate, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(0.03)
    return False


# ---------------------------------------------------------------------------
# 1. Erken dönüşlerde on_result sözleşmesi
# ---------------------------------------------------------------------------


def test_real_bridge_calls_on_result_when_lock_times_out(tmp_path, monkeypatch):
    """
    GERÇEK köprü + Popen taklidi: proje yazma kilidi başkasındayken arka plan
    görevi hiç başlayamaz ve `on_result(..., False)` çağrılmalıdır.

    Regresyon: bu yolda sessizce dönülüyordu; çağıranın kartı sonsuza dek
    `running` kalıyor, ofis pompası bir daha ilerlemiyordu.
    """
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    monkeypatch.setattr(ab, "task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    monkeypatch.setattr(ab, "BACKGROUND_LOCK_TIMEOUT", 0.3)
    monkeypatch.setattr(ab.subprocess, "Popen",
                        lambda cmd, **kw: pytest.fail("kilit yokken süreç başlatılmamalı"))

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = project

    holder_ready = threading.Event()
    release = threading.Event()

    def _hold():
        project_lock_manager.acquire_write(project)
        holder_ready.set()
        release.wait(10)
        project_lock_manager.release_write(project)

    holder = threading.Thread(target=_hold, daemon=True)
    holder.start()
    assert holder_ready.wait(5)

    got = {}
    done = threading.Event()
    try:
        bridge.send_background_task_async(
            task_id="lock-1", task_name="Kilitli görev", prompt="oku ve özetle",
            on_result=lambda t, ok: (got.update(text=t, ok=ok), done.set()),
            save_report=False, needs_write=False,
        )
        assert done.wait(10), "kilit zaman aşımında on_result çağrılmadı"
    finally:
        release.set()
        holder.join(5)

    assert got["ok"] is False
    assert LOCK_TIMEOUT_MARKER in got["text"]


def test_bridge_calls_on_result_when_shutting_down(tmp_path):
    """Kapanış sırasında reddedilen görev de geri çağrıyı almalı."""
    from entropy.core.agy_bridge import AgyProcessBridge

    bridge = AgyProcessBridge()
    bridge.active_project_dir = tmp_path
    bridge._shutting_down = True

    got = {}
    bridge.send_background_task_async(
        task_id="x", task_name="Kapanan", prompt="p",
        on_result=lambda t, ok: got.update(text=t, ok=ok),
    )
    assert got["ok"] is False
    assert "kapanıyor" in got["text"]


def test_harness_requeues_child_when_lock_blocked_then_completes(seeded, board, registry,
                                                                offices, tmp_path, monkeypatch):
    """
    Kilit yüzünden başlayamayan alt kart ÖLMEZ, sıraya geri konur; kilit
    bırakılınca zincir kaldığı yerden ilerler ve üst kart `review` olur.
    """
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    monkeypatch.setattr(ab, "task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    monkeypatch.setattr(ab, "BACKGROUND_LOCK_TIMEOUT", 0.3)

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = project

    card = _office_card(board)
    blocked = {"count": 0}

    def fake_popen(cmd, **kwargs):
        joined = " ".join(str(c) for c in cmd)
        if "OFİS TÜZÜĞÜ" in joined and "DEĞERLENDİRİLECEK" not in joined:
            return _FakeProc(_agy_lines(_plan_json("A")))
        if "DEĞERLENDİRİLECEK" in joined:
            parent = board.get(card.id)
            rows = [{"id": cid, "grade": 0.9, "verdict": "ok", "missing": []}
                    for cid in parent.children]
            return _FakeProc(_agy_lines("```json\n" + json.dumps({"grades": rows}) + "\n```"))
        return _FakeProc(_agy_lines("Alt görev çıktısı."))

    monkeypatch.setattr(ab.subprocess, "Popen", fake_popen)

    # ALT KART çağrısında kilit çakışması: planlama ve değerlendirme kilidi
    # alabilsin, ilk alt kart denemesi zaman aşımına düşsün. (Gerçek kilidi
    # baştan tutmak planlamayı da bloke ederdi.)
    real_acquire = project_lock_manager.acquire_read
    calls = {"n": 0}

    def flaky_acquire(path, timeout=None):
        calls["n"] += 1
        # 1. çağrı planlama, 2. çağrı ilk alt kart denemesi (tek alt görev
        # olduğu için sıralama belirlenimli).
        if calls["n"] == 2:
            blocked["count"] = 1
            return False
        return real_acquire(path, timeout=timeout)

    monkeypatch.setattr(project_lock_manager, "acquire_read", flaky_acquire)

    harness = OfficeHarness("arastirma-ofisi", board=board, registry=registry,
                            offices=offices, bridge_factory=lambda p: bridge)
    assert harness.start(card.id) is True

    assert _wait_until(lambda: board.get(card.id).status in ("review", "failed"), 20)
    # Kilit yüzünden başlayamayan alt kart sıraya geri konmuş olmalı.
    assert blocked["count"] == 1, "kilit çakışması hiç kurulmadı"
    parent = board.get(card.id)
    assert parent.status == "review", parent.summary
    child = board.get(parent.children[0])
    assert child.status == "review"
    assert child.summary.startswith("Alt görev çıktısı")


# ---------------------------------------------------------------------------
# 2. Paralellik ve proje kilidi
# ---------------------------------------------------------------------------


def test_read_intent_children_run_concurrently_in_same_project(seeded, board, registry,
                                                               offices, tmp_path, monkeypatch):
    """
    Aynı proje dizininde iki okuma niyetli alt kart AYNI ANDA koşar; ikincisi
    kilit zaman aşımıyla ölmez.

    Regresyon: her arka plan görevi yazma kilidi alıyordu, ofisin `max_parallel`
    ayarı fiilen 1'e düşüyor ve ikinci kart 60 sn sonra `failed` oluyordu.
    """
    import entropy.core.agy_bridge as ab
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    monkeypatch.setattr(ab, "task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    monkeypatch.setattr(ab, "BACKGROUND_LOCK_TIMEOUT", 1.0)

    project = tmp_path / "proje"
    project.mkdir()
    bridge = AgyProcessBridge()
    bridge.active_project_dir = project

    card = _office_card(board)
    both_started = threading.Event()
    hold = threading.Event()
    started = []
    lock = threading.Lock()

    def fake_popen(cmd, **kwargs):
        joined = " ".join(str(c) for c in cmd)
        if "OFİS TÜZÜĞÜ" in joined and "DEĞERLENDİRİLECEK" not in joined:
            return _FakeProc(_agy_lines(_plan_json("A", "B")))
        if "DEĞERLENDİRİLECEK" in joined:
            parent = board.get(card.id)
            rows = [{"id": cid, "grade": 0.9, "verdict": "ok", "missing": []}
                    for cid in parent.children]
            return _FakeProc(_agy_lines("```json\n" + json.dumps({"grades": rows}) + "\n```"))
        with lock:
            started.append(joined)
            if len(started) >= 2:
                both_started.set()
        # İkisi de başlayana kadar bitme: eşzamanlılığın kanıtı.
        return _FakeProc(_agy_lines("Alt görev çıktısı."), hold=hold)

    monkeypatch.setattr(ab.subprocess, "Popen", fake_popen)

    harness = OfficeHarness("arastirma-ofisi", board=board, registry=registry,
                            offices=offices, bridge_factory=lambda p: bridge)
    assert harness.start(card.id) is True
    assert both_started.wait(15), "iki alt kart aynı anda koşmadı"
    hold.set()

    assert _wait_until(lambda: board.get(card.id).status in ("review", "failed"), 20)
    parent = board.get(card.id)
    children = [board.get(c) for c in parent.children]
    assert [c.status for c in children] == ["review", "review"]
    assert all(LOCK_TIMEOUT_MARKER not in (c.summary or "") for c in children)


def test_write_intent_child_drops_parallelism_to_one(seeded, board, registry, offices):
    """Yazma niyetli alt kart varsa aynı anda tek kart koşar (kilit tekil)."""
    offices.update(replace(seeded, max_parallel=3))
    card = _office_card(board)
    children = []
    for title, intent in (("A", "write"), ("B", ""), ("C", "")):
        children.append(board.create(TaskCard(
            id=new_task_id(title), title=title, status="backlog", agent="arastirmaci",
            provider="agy", goal=f"{title} hedefi", office="arastirma-ofisi",
            parent=card.id, intent=intent,
        )).id)
    board.update(replace(card, children=children, status="running"))

    started = []

    class _Bridge:
        provider_name = "agy"

        def send_background_task_async(self, task_id, task_name, prompt, mode=None,
                                       on_result=None, save_report=True, agent=None,
                                       needs_write=None, **kw):
            started.append((task_id, needs_write))
            return task_id

        def terminate_background_task(self, task_id):
            return True

    bridge = _Bridge()
    harness = OfficeHarness("arastirma-ofisi", board=board, registry=registry,
                            offices=offices, bridge_factory=lambda p: bridge)
    harness._pump(card.id)

    assert len(started) == 1, "yazma niyetli kart varken paralellik 1 olmalı"
    # Ofis alt kartları varsayılan olarak OKUMA kilidi ister.
    assert card_needs_write(board.get(children[1])) is False
    assert card_needs_write(board.get(children[0])) is True


# ---------------------------------------------------------------------------
# 3. Kart özeti gidiş-dönüşü
# ---------------------------------------------------------------------------


def test_long_sectioned_summary_survives_roundtrip(board):
    """29k karakterlik, `##` başlıklı çıktı kayıpsız geri okunmalı."""
    body_lines = []
    idx = 0
    while sum(len(x) + 1 for x in body_lines) < 29000:
        idx += 1
        body_lines.append(f"## Bölüm {idx}")
        body_lines.append(("gövde " * 40).strip())
    summary = "\n".join(body_lines)
    assert len(summary) >= 29000

    card = board.create(TaskCard(id="uzun", title="Uzun", summary=summary,
                                 goal="hedef", notes="not"))
    back = board.get("uzun")
    assert back.summary == summary
    assert back.goal == "hedef" and back.notes == "not"


def test_summary_containing_section_headings_is_escaped_symmetrically(board):
    """Çıktı tam da kart bölüm başlıklarını içeriyorsa bile kayıp olmaz."""
    summary = "## Sonuç\nilk\n\n## Notlar\nikinci\n\n### Hedef\nüçüncü"
    board.create(TaskCard(id="cakisma", title="Çakışma", summary=summary))
    assert board.get("cakisma").summary == summary
    # İkinci kez yazıp okumak da aynı sonucu vermeli (kararlı).
    board.update(replace(board.get("cakisma"), status="review"))
    assert board.get("cakisma").summary == summary


def test_finish_does_not_truncate_full_output(board, registry, monkeypatch):
    """`_finish` artık 4000 karakterde kesmez; tam çıktı kartta durur."""
    registry.ensure_defaults()
    text = "## Başlık\n" + ("x" * 12000)
    card = board.create(TaskCard(id="tam", title="Tam", agent="arastirmaci"))
    board._finish(card.id, text, True)
    assert board.get("tam").summary == text


@pytest.mark.parametrize("limit", [6000, 1200])
def test_trim_to_sections_keeps_whole_sections(limit):
    text = "\n".join(f"## Bölüm {i}\n" + "veri " * 100 for i in range(1, 30))
    out = trim_to_sections(text, limit)
    assert len(out) <= limit + 60  # + kırpma dipnotu
    assert "kırpıldı" in out
    # Kesme yalnızca bölüm sınırında: son korunan bölüm tam olmalı.
    body = out.split("\n\n[...")[0]
    kept = [ln for ln in body.splitlines() if ln.startswith("## ")]
    assert kept, "hiç bölüm korunmadı"
    assert body.rstrip().endswith("veri")


def test_eval_prompt_trims_to_six_thousand_chars(seeded, board, registry, offices):
    from entropy.agents.harness import EVAL_SUMMARY_CHARS

    card = _office_card(board)
    child = board.create(TaskCard(
        id="alt-1", title="A", status="review", agent="arastirmaci",
        office="arastirma-ofisi", parent=card.id,
        summary="\n".join(f"## B{i}\n" + "veri " * 200 for i in range(40)),
    ))
    harness = OfficeHarness("arastirma-ofisi", board=board, registry=registry, offices=offices)
    prompt = harness.build_eval_prompt(offices.get("arastirma-ofisi"), card, [child])
    # Özet bölümü kırpılmış ama bölüm bütünlüğü korunmuş olmalı.
    assert len(prompt) < len(child.summary)
    assert "kırpıldı" in prompt
    summary_part = prompt.split("Çıktı özeti:\n", 1)[1]
    assert len(summary_part) <= EVAL_SUMMARY_CHARS + 200


# ---------------------------------------------------------------------------
# 4. Tohum ajanların/ofislerin tamamlanması
# ---------------------------------------------------------------------------


def test_missing_seed_agents_are_added_to_existing_vault(vault, registry):
    """
    Kasada zaten ajan varken sürümle gelen yeni tohumlar (orkestrator,
    degerlendirici) EKLENİR.

    Regresyon: "klasör boşsa yaz" kuralı yüzünden mevcut kasalara ofis rolleri
    hiç gelmiyor ve `/desk` "ajan yok" diyerek zinciri hiç başlatamıyordu.
    """
    from entropy.agents.registry import AgentSpec

    registry.create(AgentSpec(name="arastirmaci", role="research", description="elde var"))
    created = registry.ensure_defaults()

    assert "orkestrator" in created and "degerlendirici" in created
    assert "arastirmaci" not in created, "var olan ajanın üstüne yazılmamalı"
    assert registry.get("arastirmaci").description == "elde var"
    assert registry.get("orkestrator") is not None


def test_seed_marker_prevents_resurrection_of_deleted_agent(vault, registry):
    registry.ensure_defaults()
    marker = vault / "Entropy" / "Agents" / SEED_MARKER_FILENAME
    assert marker.is_file()
    assert set(json.loads(marker.read_text(encoding="utf-8"))["seeded"]) == {
        s.name for s in DEFAULT_AGENTS
    }

    registry.delete("analist")
    assert registry.ensure_defaults() == []
    assert registry.get("analist") is None
    # İşaret dosyası ajan listesini kirletmemeli.
    assert all(s.name != SEED_MARKER_FILENAME for s in registry.list())


def test_no_seed_offices_and_orchestrator_is_born_with_office(vault, offices):
    """
    Faz 6 sözleşmesi: tohum ofis YOK, ama açılan ofisin orkestratörü VAR.

    Eskiden `ensure_defaults` bir "arastirma-ofisi" tohumluyordu; kullanıcı
    kuralı bunu kaldırdı (ofisi kullanıcı açar) ve yerine "ofis açıldığı anda
    orkestratörü doğar" kuralı geldi.
    """
    assert offices.list() == []
    offices.create(OfficeSpec(name="baska-ofis", purpose="elde var"))
    assert [o.name for o in offices.list()] == ["baska-ofis"]

    orchestrator = offices.agents("baska-ofis").get("orkestrator")
    assert orchestrator is not None
    assert orchestrator.office_role == "orchestrator"
    assert orchestrator.tools_policy == "read-only"
    # Orkestratör ofisin üyesi (alt ajanı) sayılmaz: o planlar, üretmez.
    assert offices.get("baska-ofis").members == []
    offices.delete("baska-ofis")
    assert offices.get("baska-ofis") is None


# ---------------------------------------------------------------------------
# 5. Gerçek bütçe koruması
# ---------------------------------------------------------------------------


class _StubLedger:
    """Görev kimliğine göre sabit `total_tokens` döndüren sahte ledger."""

    def __init__(self, usage):
        self.usage = usage

    def get_task(self, task_id):
        if task_id not in self.usage:
            return None
        return {"task_id": task_id, "total_tokens": self.usage[task_id]}


def test_budget_uses_real_ledger_tokens_not_estimate(seeded, board, registry,
                                                     offices, monkeypatch):
    """
    Maliyet karakter/4 tahmininden değil ledger'daki gerçek `total_tokens`'tan
    okunur; kısa yanıt bile gerçekte pahalıysa bütçe aşılır.
    """
    offices.update(replace(seeded, budget_tokens=1000))
    card = _office_card(board)
    import sys

    tl_mod = sys.modules["entropy.core.task_ledger"]
    monkeypatch.setattr(
        tl_mod, "task_ledger",
        _StubLedger({f"office-plan-{card.id}": 5000}),
    )

    class _Bridge:
        provider_name = "agy"

        def __init__(self):
            self.calls = []

        def send_background_task_async(self, task_id, task_name, prompt, on_result=None,
                                       **kw):
            self.calls.append(task_id)
            if on_result is not None:
                on_result(_plan_json("A"), True)
            return task_id

        def terminate_background_task(self, task_id):
            return True

    bridge = _Bridge()
    harness = OfficeHarness("arastirma-ofisi", board=board, registry=registry,
                            offices=offices, bridge_factory=lambda p: bridge)
    harness.start(card.id)

    parent = board.get(card.id)
    assert parent.status == "failed"
    state = harness._card_state(card.id)
    # Tahmin ~100 token olurdu; sayaç gerçek 5000'i göstermeli.
    assert state["tokens"] == 5000
    assert state["measured_tokens"] == 5000 and state["estimated_tokens"] == 0
    assert "Bütçe" in parent.summary
    # Zincir durdu: hiçbir alt kart koşmadı.
    assert [c for c in bridge.calls if c.startswith("card-")] == []


def test_budget_overrun_terminates_running_children(seeded, board, registry,
                                                    offices, monkeypatch):
    """
    Bütçe aşımında SÜREN alt kartlar `terminate_background_task` ile öldürülür
    ve üst kart nedeniyle `failed` olur.

    Regresyon: yalnızca üst kart başarısız sayılıyor, süren agy süreçleri token
    yakmayı sürdürüyordu.
    """
    offices.update(replace(seeded, budget_tokens=1000, max_parallel=2))
    card = _office_card(board)
    children = []
    for title in ("A", "B"):
        children.append(board.create(TaskCard(
            id=new_task_id(title), title=title, status="running", agent="arastirmaci",
            provider="agy", goal=f"{title} hedefi", office="arastirma-ofisi",
            parent=card.id,
        )).id)
    # Üçüncüsü bitti sayılır ve pahalıya patlar.
    finished = board.create(TaskCard(
        id=new_task_id("C"), title="C", status="review", agent="arastirmaci",
        provider="agy", office="arastirma-ofisi", parent=card.id, summary="bitti",
    ))
    children.append(finished.id)
    board.update(replace(card, children=children, status="running"))

    import sys

    tl_mod = sys.modules["entropy.core.task_ledger"]
    monkeypatch.setattr(
        tl_mod, "task_ledger",
        _StubLedger({f"card-{finished.id}": 9999}),
    )

    terminated = []

    class _Bridge:
        provider_name = "agy"

        def send_background_task_async(self, *a, **kw):
            return "x"

        def terminate_background_task(self, task_id):
            terminated.append(task_id)
            return True

    harness = OfficeHarness("arastirma-ofisi", board=board, registry=registry,
                            offices=offices, bridge_factory=lambda p: _Bridge())
    harness._on_child_done(card.id, finished.id, True)

    parent = board.get(card.id)
    assert parent.status == "failed"
    assert sorted(terminated) == sorted(f"card-{c}" for c in children[:2])
    assert all(board.get(c).status == "failed" for c in children[:2])
    assert "9999" in parent.summary or "≈ 9999" in parent.summary


def test_card_budget_overrides_office_budget(seeded, board, registry, offices, monkeypatch):
    """Kartın `budget_tokens` alanı ofisinkinin önüne geçer (kart düzeyi tavan)."""
    offices.update(replace(seeded, budget_tokens=1_000_000))
    card = board.create(TaskCard(
        id=new_task_id("dar"), title="Dar bütçe", status="backlog", agent="orkestrator",
        provider="agy", goal="hedef", office="arastirma-ofisi", budget_tokens=100,
    ))
    assert board.get(card.id).budget_tokens == 100

    import sys

    tl_mod = sys.modules["entropy.core.task_ledger"]
    monkeypatch.setattr(
        tl_mod, "task_ledger",
        _StubLedger({f"office-plan-{card.id}": 500}),
    )

    class _Bridge:
        provider_name = "agy"

        def send_background_task_async(self, task_id, task_name, prompt, on_result=None, **kw):
            if on_result is not None:
                on_result(_plan_json("A"), True)
            return task_id

        def terminate_background_task(self, task_id):
            return True

    harness = OfficeHarness("arastirma-ofisi", board=board, registry=registry,
                            offices=offices, bridge_factory=lambda p: _Bridge())
    assert harness._budget(card.id) == 100
    harness.start(card.id)
    assert board.get(card.id).status == "failed"


def test_desk_output_shows_real_spend(seeded, board, offices):
    """`/desk` harcamayı gerçek sayıyla gösterir."""
    from entropy.core.slash_commands import try_handle_local_command

    card = _office_card(board, title="Süren iş")
    board.update(replace(card, status="running"))
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    harness._save_card_state(card.id, tokens=4321)

    out = try_handle_local_command("/desk", bridge=None)
    assert "Süren iş" in out
    assert "4,321 tk" in out


def test_subtask_prompt_carries_cost_discipline(board, registry):
    """Alt kart prompt'u maliyet disiplini kurallarını taşır."""
    from entropy.agents.tasks import MAX_STEPS_PER_CARD

    registry.ensure_defaults()
    card = board.create(TaskCard(id="p1", title="P", agent="arastirmaci", goal="hedef"))
    prompt = board.build_prompt(card, agent_spec=registry.get("arastirmaci"))
    assert "depo" in prompt.lower() and "tarama" in prompt.lower()
    assert f"{MAX_STEPS_PER_CARD} araç adımı" in prompt
