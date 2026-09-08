"""
Kapanış temizliği (AgyProcessBridge.shutdown) ve yönlendirme kararı özeti.

Buradaki testlerin tamamı gerçek köprüyü sürer; yalnızca `subprocess.Popen` ve
`taskkill` çağrısı taklit edilir. Sahte bir köprüyle yazılsalardı asıl doğrulanan
şey — gerçek arka plan görevi yolunda açılan sürecin defterde tutulup kapanışta
ağacıyla birlikte öldürülmesi — hiç sınanmamış olurdu.
"""

import threading
import time

import pytest

from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.event_bus import bus
from entropy.core.task_ledger import TaskLedger, TaskStatus


class FakeProc:
    """Uzun süren bir agy süreci; öldürülene kadar stdout'u açık tutar."""

    def __init__(self, *args, **kwargs):
        self.pid = 90001
        self.returncode = None
        self.killed = threading.Event()
        self.stdin = None
        self.stdout = self
        FakeProc.instances.append(self)

    instances: list = []

    # -- stdout arayüzü --
    def readline(self):
        # Kapanış öldürene kadar blokla; gerçek agy de sonuç beklerken burada durur.
        self.killed.wait(timeout=5.0)
        return ""

    def close(self):
        pass

    # -- süreç arayüzü --
    def poll(self):
        return None if not self.killed.is_set() else 0

    def wait(self, timeout=None):
        self.killed.wait(timeout=timeout if timeout is not None else 5.0)
        return 0

    def terminate(self):
        self.killed.set()

    def kill(self):
        self.killed.set()


@pytest.fixture
def bridge_with_fakes(tmp_path, monkeypatch):
    """Gerçek köprü + sahte Popen + sahte taskkill + yalıtılmış ledger."""
    FakeProc.instances = []
    monkeypatch.setattr("subprocess.Popen", FakeProc)

    kill_cmds = []

    def fake_run(cmd, *a, **k):
        kill_cmds.append(cmd)
        for p in FakeProc.instances:
            if str(p.pid) in str(cmd):
                p.killed.set()
        return None

    monkeypatch.setattr("subprocess.run", fake_run)

    ledger = TaskLedger(db_path=tmp_path / "ledger.db")
    # Not: "entropy.core.task_ledger.task_ledger" yolu yamalanamaz — entropy.core
    # paketi aynı adı örnek için kullandığından o ad modülü değil TaskLedger'ı
    # gösterir. Köprü modülünün genel adını yamalamak doğru ve yeterli olan yol.
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", ledger)

    bridge = AgyProcessBridge()
    bridge.active_project_dir = tmp_path
    return bridge, ledger, kill_cmds


def _wait_for_process(bridge, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bridge._background_processes:
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------- Görev 1


def test_shutdown_kills_background_process_tree_with_taskkill(bridge_with_fakes):
    """Çalışan arka plan görevi kapanışta ağacıyla (taskkill /T) sonlandırılmalı."""
    bridge, _ledger, kill_cmds = bridge_with_fakes

    bridge.send_background_task_async(
        task_id="bg-1", task_name="Uzun Görev", prompt="calis", save_report=False
    )
    assert _wait_for_process(bridge), "arka plan süreci defterde belirmedi"

    stats = bridge.shutdown(timeout=3.0)

    assert stats["processes"] == 1
    assert FakeProc.instances[0].killed.is_set(), "süreç öldürülmedi"
    joined = " ".join(str(c) for c in kill_cmds)
    assert "/T" in joined, "çocuk süreçler (language_server) için /T şart"
    assert "/F" in joined
    assert str(FakeProc.instances[0].pid) in joined


def test_shutdown_marks_running_tasks_cancelled_not_failed(bridge_with_fakes):
    """Kapanışta kesilen görev CANCELLED olmalı; FAILED kullanıcıya sahte arıza gösterir."""
    bridge, ledger, _ = bridge_with_fakes

    bridge.send_background_task_async(
        task_id="bg-2", task_name="Kesilecek", prompt="calis", save_report=False
    )
    assert _wait_for_process(bridge)

    bridge.shutdown(timeout=3.0)

    row = ledger.get_task("bg-2")
    assert row is not None
    assert row["status"] == TaskStatus.CANCELLED.value
    assert "kapan" in (row["error"] or "").lower()
    assert ledger.get_active_tasks() == []


def test_shutdown_refuses_new_background_tasks(bridge_with_fakes):
    """Kapanıştan sonra gelen görev yeni bir agy ağacı doğurmamalı."""
    bridge, _ledger, _ = bridge_with_fakes

    bridge.shutdown(timeout=1.0)
    before = len(FakeProc.instances)
    bridge.send_background_task_async(
        task_id="bg-3", task_name="Geç Kalan", prompt="calis", save_report=False
    )
    time.sleep(0.3)
    assert len(FakeProc.instances) == before, "kapanış sonrası süreç başlatıldı"


def test_shutdown_is_idempotent_and_bounded(bridge_with_fakes):
    """İkinci çağrı iş yapmamalı ve kapanış bütçeyi aşmamalı (arayüz iş parçacığı)."""
    bridge, _ledger, _ = bridge_with_fakes

    bridge.send_background_task_async(
        task_id="bg-4", task_name="Uzun", prompt="calis", save_report=False
    )
    assert _wait_for_process(bridge)

    t0 = time.monotonic()
    first = bridge.shutdown(timeout=3.0)
    elapsed = time.monotonic() - t0
    second = bridge.shutdown(timeout=3.0)

    assert first["processes"] == 1
    assert second == {"processes": 0, "tasks": 0, "threads": 0}
    assert elapsed < 4.0, f"kapanış {elapsed:.2f}s sürdü; 3 sn bütçe aşıldı"


def test_shutdown_stops_skill_watcher(tmp_path, monkeypatch):
    """Yetenek izleyicisi kapanışta durmalı; aksi hâlde yıkım sırasında timer ateşler."""
    import entropy.skills.manager as sm_mod

    stopped = {"n": 0}

    class DummyWatcher:
        def stop(self):
            stopped["n"] += 1

    monkeypatch.setattr(sm_mod, "_skill_watcher", DummyWatcher(), raising=False)

    bridge = AgyProcessBridge()
    bridge.shutdown(timeout=1.0)

    assert stopped["n"] == 1
    assert sm_mod._skill_watcher is None
    assert sm_mod.stop_skill_watcher() is False, "yeniden çağrı güvenli olmalı"


# ---------------------------------------------------------------- Görev 3


class _StubSkill:
    def __init__(self, name):
        self.name = name


class _StubManager:
    def __init__(self, skill, confidence):
        self._skill = skill
        self._conf = confidence

    def score_skill_for_prompt(self, prompt, **kwargs):
        return self._skill, self._conf


@pytest.mark.parametrize("skill_name,conf", [("financial-auditor", 0.91), (None, 0.12)])
def test_skill_detected_signal_emitted_on_every_scoring(skill_name, conf):
    """Her yönlendirme kararı bus.skill_detected ile yayınlanmalı (rozet senkronu)."""
    bridge = AgyProcessBridge()
    got = []
    bus.skill_detected.connect(lambda n, c: got.append((n, c)))
    try:
        skill = _StubSkill(skill_name) if skill_name else None
        res, c = bridge.score_skill_for_prompt("bilanco analizi", sm=_StubManager(skill, conf))
    finally:
        bus.skill_detected.disconnect()

    assert got, "sinyal yayınlanmadı"
    assert got[-1][0] == (skill_name or "")
    assert got[-1][1] == pytest.approx(conf)
    assert bridge.last_skill_confidence == pytest.approx(conf)
    assert c == pytest.approx(conf)


def test_skill_detected_emitted_for_each_send_not_only_first():
    """Ardışık kararların hepsi yayınlanmalı; ikinci mesajda rozet donmamalı."""
    bridge = AgyProcessBridge()
    got = []
    bus.skill_detected.connect(lambda n, c: got.append((n, c)))
    try:
        bridge.score_skill_for_prompt("a", sm=_StubManager(_StubSkill("pdf-analyzer"), 0.8))
        bridge.score_skill_for_prompt("b", sm=_StubManager(None, 0.2))
        bridge.score_skill_for_prompt("c", sm=_StubManager(_StubSkill("skill-creator"), 0.55))
    finally:
        bus.skill_detected.disconnect()

    assert [n for n, _ in got] == ["pdf-analyzer", "", "skill-creator"]


def test_low_confidence_note_added_only_when_weak():
    """Zayıf kararda kataloğa uyarı satırı eklenir; güçlü kararda hiç eklenmez."""
    bridge = AgyProcessBridge()
    skill = _StubSkill("financial-auditor")

    bridge.last_skill_confidence = 0.55
    note = bridge.low_confidence_manifest_note(skill)
    assert "düşük güvenli" in note
    assert "yeteneksiz yanıtla" in note
    assert note.count("\n") == 0, "manifest'e tek satır eklenmeli"

    bridge.last_skill_confidence = 0.85
    assert bridge.low_confidence_manifest_note(skill) == ""

    bridge.last_skill_confidence = 0.30
    assert bridge.low_confidence_manifest_note(None) == "", "yetenek yokken not anlamsız"


def test_cognitive_context_carries_low_confidence_note(tmp_path, monkeypatch):
    """Not gerçekten prompt'a (bilişsel bağlam katalogunun sonuna) düşmeli."""
    import entropy.skills.manager as sm_mod

    class ManifestManager:
        def __init__(self, *a, **k):
            pass

        def get_skills_manifest(self, active_skill=None):
            return "## YETENEK KATALOGU\n- financial-auditor"

    monkeypatch.setattr(sm_mod, "SkillManager", ManifestManager)

    bridge = AgyProcessBridge()
    bridge.active_project_dir = tmp_path
    bridge.last_skill_confidence = 0.52
    ctx = bridge.get_cognitive_context("bilanco", target_skill=_StubSkill("financial-auditor"))
    assert "düşük güvenli" in ctx

    bridge.last_skill_confidence = 0.95
    ctx2 = bridge.get_cognitive_context("bilanco", target_skill=_StubSkill("financial-auditor"))
    assert "düşük güvenli" not in ctx2


def test_last_decision_summary_labels():
    """/skills gibi yerel komutların tüketeceği özet: karar + güven + zayıflık yargısı."""
    bridge = AgyProcessBridge()

    bridge.last_active_skill = "financial-auditor"
    bridge.last_skill_confidence = 0.92
    s = bridge.last_decision_summary()
    assert s["skill"] == "financial-auditor"
    assert s["low_confidence"] is False
    assert s["label"] == "güçlü eşleşme"
    assert "0.92" in s["text"]

    bridge.last_skill_confidence = 0.51
    s = bridge.last_decision_summary()
    assert s["low_confidence"] is True
    assert s["label"] == "zayıf eşleşme"

    bridge.last_active_skill = None
    bridge.last_skill_confidence = 0.1
    s = bridge.last_decision_summary()
    assert s["skill"] is None
    assert s["low_confidence"] is False
    assert "yetenek yok" in s["text"]


def test_decision_summary_and_manifest_note_share_one_threshold():
    """Eşik tek yerde: arayüz etiketiyle prompt'a düşen not asla ayrışmamalı."""
    bridge = AgyProcessBridge()
    bridge.last_active_skill = "pdf-analyzer"
    eps = 1e-6
    for conf, weak in [
        (AgyProcessBridge.LOW_CONFIDENCE_THRESHOLD - eps, True),
        (AgyProcessBridge.LOW_CONFIDENCE_THRESHOLD, False),
    ]:
        bridge.last_skill_confidence = conf
        note = bridge.low_confidence_manifest_note(_StubSkill("pdf-analyzer"))
        assert bool(note) is weak
        assert bridge.last_decision_summary()["low_confidence"] is weak
