"""
Faz 11.6 — öz-amplifikasyon kilidi + açılış kablolaması + yeni slash komutları.

Kilit üç kapıdan oluşuyor ve üçü de KOTA HARCAMADAN ölçülebilir olmalı:
beyinde yanıt varken CLI hiç çağrılmamalı, düşük yenilikte zamanlanmış görev
durmalı, kaynaksız rapor L2'ye yazılmamalı. Sahte kapı/sahte zamanlayıcı ile
sürülür; gerçek model çağrısı YOK.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from entropy.agents import amplification  # noqa: E402
from entropy.agents.registry import AgentRegistry, AgentSpec  # noqa: E402
from entropy.agents.tasks import TaskBoard, TaskCard  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Entropy" / "Tasks").mkdir(parents=True, exist_ok=True)
    AgentRegistry(vault_path=root).create(
        AgentSpec(name="arastirmaci", role="Araştırmacı", provider="claude",
                  tools_policy="read-only", prompt="Araştır.")
    )
    return root


class FakeCtx:
    def __init__(self, confidence: float, text: str = "Bulgu: X.") -> None:
        self.brain_confidence = confidence
        self.text = text

    @property
    def brain_has_answer(self) -> bool:
        from entropy.memory.context_builder import CRAG_MIN_SCORE

        return self.brain_confidence >= CRAG_MIN_SCORE


class FakeBuilder:
    def __init__(self, ctx):
        self.ctx = ctx
        self.calls = []

    def build(self, query, **_kw):
        self.calls.append(query)
        return self.ctx


class FakeDecision:
    def __init__(self, action):
        self.action = action


class FakeGate:
    """`admit` sırayla verilen kararları döndürür (son karar tekrarlanır)."""

    def __init__(self, actions):
        self.actions = list(actions)
        self.seen = []

    def admit(self, category, content, **_kw):
        self.seen.append(content)
        action = self.actions[min(len(self.seen) - 1, len(self.actions) - 1)]
        return FakeDecision(action)


class FakeTask:
    def __init__(self, tid, name, prompt, enabled=True):
        self.id, self.name, self.prompt, self.enabled = tid, name, prompt, enabled


class FakeScheduler:
    def __init__(self, tasks):
        self.tasks = {t.id: t for t in tasks}
        self.disabled = []

    def disable_task(self, task_id, reason=""):
        self.tasks[task_id].enabled = False
        self.disabled.append((task_id, reason))
        return True


# ---------------------------------------------------------------------------
# Araştırma kartı sezgisi
# ---------------------------------------------------------------------------

def test_research_card_detected_by_kind_and_by_title():
    assert amplification.is_research_card(TaskCard(id="a", title="X", kind="research"))
    assert amplification.is_research_card(
        TaskCard(id="b", title="Kuantum hesaplamayı araştır", goal="rapor")
    )
    # Geliştirme kartı sezgiye takılmamalı: yanlış pozitif, kodlama kartını
    # beyin cevabıyla kapatmak demek.
    assert not amplification.is_research_card(
        TaskCard(id="c", title="Panoyu kodla", goal="dispatcher yaz")
    )
    # Açık `kind` sezgiyi EZER.
    assert not amplification.is_research_card(
        TaskCard(id="d", title="Piyasayı araştır", kind="build")
    )


# ---------------------------------------------------------------------------
# (a) Açık tespiti — beyinde yanıt varken CLI çağrılmaz
# ---------------------------------------------------------------------------

def test_card_answered_from_brain_never_calls_the_cli(vault, monkeypatch):
    board = TaskBoard(vault_path=vault)
    card = board.create(TaskCard(id="r1", title="Vektör veritabanlarını araştır",
                                 goal="son gelişmeler", agent="arastirmaci",
                                 kind="research", provider="claude"))
    board.apply_event(card.id, "task.assigned", payload={"agent": "arastirmaci"})

    builder = FakeBuilder(FakeCtx(0.91))
    monkeypatch.setattr(amplification, "brain_lookup",
                        lambda q, builder=builder: amplification.BrainAnswer(
                            has_answer=True, confidence=0.91, text="Beyindeki yanıt."))

    calls = []

    class Bridge:
        def send_background_task_async(self, **kwargs):
            calls.append(kwargs)

    task_id = board.run(card.id, bridge_factory=lambda _p=None: Bridge())

    assert task_id == "brain-r1"
    assert calls == [], "beyinde yanıt varken CLI çağrıldı"
    closed = board.get(card.id)
    assert closed.status == "review"
    assert closed.summary.startswith("Beyinden yanıtlandı")


def test_low_confidence_brain_answer_lets_the_run_proceed(vault, monkeypatch):
    board = TaskBoard(vault_path=vault)
    card = board.create(TaskCard(id="r2", title="Vektör veritabanlarını araştır",
                                 goal="son gelişmeler", agent="arastirmaci",
                                 kind="research", provider="claude"))
    board.apply_event(card.id, "task.assigned", payload={"agent": "arastirmaci"})

    builder = FakeBuilder(FakeCtx(0.10))
    monkeypatch.setattr("entropy.memory.context_builder.CognitiveContextBuilder",
                        lambda *a, **k: builder)

    calls = []

    class Bridge:
        def send_background_task_async(self, **kwargs):
            calls.append(kwargs)

    board.run(card.id, bridge_factory=lambda _p=None: Bridge())
    assert len(calls) == 1, "beyin zayıfken koşu durdurulmamalı"


def test_brain_lookup_survives_missing_memory_layer(monkeypatch):
    """Hafıza katmanı patlarsa kilit ASLA kartı kapatmamalı."""

    class Boom:
        def build(self, *_a, **_k):
            raise RuntimeError("beyin yok")

    answer = amplification.brain_lookup("soru", builder=Boom())
    assert answer.has_answer is False


# ---------------------------------------------------------------------------
# (b) Yenilik kotası
# ---------------------------------------------------------------------------

SOURCED_REPORT = (
    "Vektör veritabanlarında HNSW indeksleri 2026'da varsayılan hâline geldi ve "
    "geri çağırma oranı %98'e çıktı; kaynak https://ornek.test/hnsw sayfasında.\n\n"
    "Bellek tüketimi katman sayısıyla doğrusal artıyor, ölçüm dosyası "
    "docs/olcum/hnsw.md içinde duruyor ve 32 GB üstünde disk moduna geçiliyor.\n\n"
    "Hibrit arama (BM25 + vektör) tek başına vektörden %12 daha iyi Hit@1 veriyor; "
    "değerlendirme https://ornek.test/hibrit adresinde yayımlandı."
)


def test_novelty_report_counts_and_ratio():
    gate = FakeGate(["add", "noop", "noop"])
    report = amplification.admit_report(SOURCED_REPORT, gate=gate)
    assert report.total == 3 and report.add == 1 and report.noop == 2
    assert report.ratio == pytest.approx(1 / 3)
    assert not report.low_novelty  # 0.33 >= 0.30

    gate2 = FakeGate(["noop"])
    report2 = amplification.admit_report(SOURCED_REPORT, gate=gate2)
    assert report2.low_novelty and "DÜŞÜK YENİLİK" in report2.note()


def test_report_without_sources_is_not_written_to_l2():
    gate = FakeGate(["add"])
    report = amplification.admit_report(
        "Sistem bu konuda son derece gelişti ve artık her şeyi biliyor diyebiliriz. "
        "Kaynak gösterilmedi ama sonuç kesin olarak böyle görünüyor.",
        gate=gate,
    )
    assert report.total == 0
    assert gate.seen == [], "kaynaksız rapor kapıya hiç verilmemeli"
    assert "kaynak yok" in report.skipped_reason


def test_low_novelty_stops_the_scheduled_research_task():
    scheduler = FakeScheduler([
        FakeTask("t1", "Vektör veritabanı taraması",
                 "Vektör veritabanlarındaki son gelişmeleri araştır"),
        FakeTask("t2", "Obsidian senkronu", "Kasayı senkronla"),
    ])
    stopped = amplification.stop_scheduled_research(
        "Vektör veritabanlarını araştır", scheduler=scheduler)

    assert stopped == ["Vektör veritabanı taraması"]
    assert scheduler.tasks["t1"].enabled is False
    assert scheduler.tasks["t2"].enabled is True, "ilgisiz görev durdurulmamalı"


def test_apply_report_lock_notifies_and_stops(monkeypatch):
    card = TaskCard(id="r3", title="Vektör veritabanlarını araştır", kind="research")
    scheduler = FakeScheduler([
        FakeTask("t1", "Vektör taraması", "vektör veritabanı araştırması")])
    seen = []
    monkeypatch.setattr(amplification, "_notify",
                        lambda c, o: seen.append((c.id, o.note)))

    outcome = amplification.apply_report_lock(
        card, SOURCED_REPORT, gate=FakeGate(["noop"]), scheduler=scheduler)

    assert outcome.novelty.low_novelty
    assert outcome.stopped_tasks == ["Vektör taraması"]
    assert seen and "Zamanlanmış araştırma durduruldu" in seen[0][1]


def test_non_research_card_is_untouched():
    assert amplification.apply_report_lock(
        TaskCard(id="x", title="Panoyu kodla"), SOURCED_REPORT) is None


def test_scheduler_disable_task_keeps_the_task(tmp_path):
    from entropy.scheduler.cron_engine import TaskScheduler

    sched = TaskScheduler(storage_path=tmp_path / "tasks.json")
    sched.schedule_task("t1", "Araştırma", "araştır", "minutely", 10)
    assert sched.disable_task("t1", reason="düşük yenilik") is True
    assert sched.tasks["t1"].enabled is False
    assert sched.disable_task("t1") is False, "iki kez kapatmak False dönmeli"
    # SİLİNMEZ: kullanıcı neyin durduğunu görebilmeli ve geri açabilmeli.
    assert "t1" in sched.tasks


# ---------------------------------------------------------------------------
# Kart kapanışında kilit
# ---------------------------------------------------------------------------

def test_finish_writes_novelty_note_on_research_card(vault, monkeypatch):
    board = TaskBoard(vault_path=vault)
    card = board.create(TaskCard(id="r4", title="Hibrit aramayı araştır",
                                 goal="rapor", agent="arastirmaci",
                                 kind="research", provider="claude",
                                 status="running", started_at="2026-01-01 00:00"))
    monkeypatch.setattr(amplification, "admit_report",
                        lambda *a, **k: amplification.NoveltyReport(add=0, noop=4))
    monkeypatch.setattr(amplification, "stop_scheduled_research",
                        lambda *a, **k: ["Zamanlanmış tarama"])
    monkeypatch.setattr(amplification, "_notify", lambda *a, **k: None)

    board._finish(card.id, SOURCED_REPORT, True)

    closed = board.get(card.id)
    assert "[YENİLİK]" in closed.notes
    assert "DÜŞÜK YENİLİK" in closed.notes
    assert "Zamanlanmış tarama" in closed.notes


# ---------------------------------------------------------------------------
# Açılış kablolaması
# ---------------------------------------------------------------------------

class FakeApp:
    """Sahte QApplication: `aboutToQuit` sinyali yerine geri çağrı listesi."""

    class _Signal:
        def __init__(self):
            self.slots = []

        def connect(self, slot):
            self.slots.append(slot)

        def emit(self):
            for slot in list(self.slots):
                slot()

    def __init__(self):
        self.aboutToQuit = FakeApp._Signal()


def test_startup_reconciles_then_starts_and_quit_stops(vault, monkeypatch):
    from entropy.agents import dispatcher as disp
    from entropy.agents.bootstrap import start_board_dispatch, stop_board_dispatch

    disp.reset_dispatcher()
    order = []

    class FakeDispatcher:
        interval_s = 3

        def reconcile(self):
            order.append("reconcile")
            return ["c1"]

        def start(self):
            order.append("start")
            return True

        def stop(self):
            order.append("stop")

    fake = FakeDispatcher()
    monkeypatch.setattr(disp, "board_dispatcher", lambda create=True: fake)

    app = FakeApp()
    result = start_board_dispatch(app)

    assert result.ok if hasattr(result, "ok") else result.error is None
    assert order == ["reconcile", "start"], "uzlaştırma turdan ÖNCE koşmalı"
    assert result.recovered == ["c1"] and result.started is True
    assert "asılı kalan 1 kart" in result.summary()

    app.aboutToQuit.emit()
    assert order[-1] == "stop"

    assert stop_board_dispatch() is True
    disp.reset_dispatcher()


def test_startup_reports_error_instead_of_raising(monkeypatch):
    from entropy.agents import dispatcher as disp
    from entropy.agents.bootstrap import start_board_dispatch

    def _boom(create=True):
        raise RuntimeError("pano okunamadı")

    monkeypatch.setattr(disp, "board_dispatcher", _boom)
    result = start_board_dispatch(None)
    assert result.error and "pano okunamadı" in result.error
    assert "başlatılamadı" in result.summary()


def test_dispatcher_start_respects_the_setting(monkeypatch):
    from entropy.agents.dispatcher import BoardDispatcher

    from entropy.core.config import config

    monkeypatch.setattr(config, "board_auto_dispatch", False, raising=False)
    d = BoardDispatcher(core=object())
    assert d.start() is False


# ---------------------------------------------------------------------------
# Yeni slash komutları (hepsi YEREL: model çağırmaz)
# ---------------------------------------------------------------------------

class FakeBridge:
    provider_name = "claude"

    def __init__(self):
        self.selected_model = "claude-opus-5"
        self.selected_effort = "medium"

    def set_model(self, name):
        self.selected_model = name

    def fetch_available_models(self):
        return ["claude-opus-5", "claude-sonnet-5"]

    def effort_levels(self):
        return ["low", "medium", "high", "xhigh", "max"]


def _cmd(text, bridge=None):
    from entropy.core.slash_commands import try_handle_local_command

    return try_handle_local_command(text, bridge or FakeBridge())


def test_board_command_summarizes_states_and_taskboard_path():
    board = TaskBoard()
    board.create(TaskCard(id="b1", title="İş", goal="hedef"))

    out = _cmd("/board")

    assert out is not None and "Pano" in out
    assert "backlog" in out
    assert "TASKBOARD" in out.upper()


def test_board_pick_assigns_and_claims():
    from entropy.agents import dispatcher as disp

    AgentRegistry().create(AgentSpec(name="yazar", role="Yazar", prompt="Yaz."))
    board = TaskBoard()
    board.create(TaskCard(id="b2", title="İş", goal="hedef"))
    disp.reset_dispatcher()

    out = _cmd("/board pick b2 yazar")

    assert "Sahiplenildi" in out
    card = board.get("b2")
    assert card.status == "taken" and card.claimed_by == "yazar"
    assert disp.ClaimStore(board.vault_path).read("b2") is not None
    disp.reset_dispatcher()


def test_model_command_changes_entropys_own_setting():
    bridge = FakeBridge()
    out = _cmd("/model claude-sonnet-5", bridge)
    assert bridge.selected_model == "claude-sonnet-5"
    assert "claude-sonnet-5" in out

    # Yabancı model reddedilir: /model asla CLI'a düşmemeli.
    out2 = _cmd("/model gemini-3.8-flash-high", bridge)
    assert "değil" in out2 and bridge.selected_model == "claude-sonnet-5"

    shown = _cmd("/model", bridge)
    assert "claude-sonnet-5" in shown


def test_agent_effort_and_model_write_to_agent_md_and_recompile():
    registry = AgentRegistry()
    registry.create(AgentSpec(name="yazar", role="Yazar", provider="claude",
                              prompt="Yaz.", effort="low"))

    out = _cmd("/agent effort yazar high")
    assert "high" in out
    assert registry.get("yazar").effort == "high"
    assert "effort: high" in registry.get("yazar").path.read_text(encoding="utf-8")

    out2 = _cmd("/agent model yazar sonnet")
    assert "sonnet" in out2
    assert "sonnet" in registry.get("yazar").model

    # Derleme koştu mu: agy biçimi diske düşmeli.
    from entropy.agents.compile import claude_compile_root

    assert (claude_compile_root() / ".agents" / "agents" / "yazar" / "agent.md").is_file()

    # Tek argümanlı `/agent <ad>` hâlâ AYRINTI gösterir (ayar değil).
    detail = _cmd("/agent yazar")
    assert "Kaynak:" in detail


def test_memory_and_wiki_compile_run_dry_without_bridge():
    """
    Faz 12-A: köprüsüz çağrı artık "modül kurulu değil" demez — modüller
    GERÇEKTEN koşar, yalnızca model turu harcanmaz (kuru koşum).
    Kablolama sözleşmesi: tests/contracts/test_phase12_bridge_wiring.py.
    """
    out = _cmd("/memory merge")
    assert "Gri Bant" in out
    assert "kurulu değil" not in out
    assert _cmd("/memory") is not None and "Kullanım" in _cmd("/memory")
    compiled = _cmd("/wiki compile yazilim --turns 3")
    assert "Wiki Derle" in compiled
    assert "kurulu değil" not in compiled
    # Köprüsüz çağrıda tavan yazılır ama harcanan tur 0'dır.
    assert "0 tur harcandı" in compiled and "tavan 3" in compiled
