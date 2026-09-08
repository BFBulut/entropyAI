"""
Yönlendirme güven puanı, değerlendirme kümesi bütünlüğü ve köprü sağlamlığı.

Kapsam
------
1. `SkillManager.score_skill_for_prompt` — karar + 0–1 güven; eşiğin altındaki
   kararlar 0,5'in altında kalmalı ki arayüz "yetenek yok"u ayırt edebilsin.
2. tests/data/routing_eval.jsonl — etiketler gerçek yetenek adları olmalı,
   kimlikler tekil, örnek sayısı ölçüm için yeterli.
3. agy köprüsü — stdin NDJSON yolunda boru kilitlenmesi olmamalı, süreç
   sonlandırma kilidi tutarken taskkill beklememeli, eşzamanlı arka plan
   görevlerinde token sayacı kaybetmemeli.

Testler sahte köprüyle değil, gerçek `_execute_background_task_worker` ve
`terminate_current_process` yollarıyla; yalnızca `subprocess.Popen` taklit edilir
(gerçek agy çağrısı yok).
"""

import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from entropy.core.agy_bridge import ARGV_PROMPT_SAFE_LIMIT, AgyProcessBridge
from entropy.core.task_ledger import TaskLedger
from entropy.skills.manager import SkillManager

DATASET = Path(__file__).resolve().parent / "data" / "routing_eval.jsonl"
REPO_SKILLS = Path(__file__).resolve().parents[1] / "skills"


def _write_skill(root: Path, name: str, desc: str, tags: str = "x"):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: \"{desc}\"\ntags: {tags}\n---\n\n# {name}\n\nTalimat.\n",
        encoding="utf-8",
    )


@pytest.fixture
def sm(tmp_path):
    _write_skill(tmp_path, "financial-auditor", "Şirket bilançolarını ve nakit akımını denetler")
    _write_skill(tmp_path, "slide-deck-architect", "Interactive HTML5 slide deck synthesis engine")
    return SkillManager(root_skills_dir=tmp_path)


# --- 1. Güven puanı --------------------------------------------------------

def test_confidence_high_for_explicit_domain_prompt(sm):
    skill, conf = sm.score_skill_for_prompt("bilanco ve nakit akim analizi yap")
    assert skill is not None and skill.name == "financial-auditor"
    assert 0.5 <= conf <= 1.0
    assert conf > 0.5, "açık alan terimi olan mesajda güven eşiğin üstünde olmalı"


def test_confidence_below_half_when_no_skill_selected(sm):
    skill, conf = sm.score_skill_for_prompt("bugun hava nasil olacak disari ciksam mi")
    assert skill is None
    assert 0.0 <= conf < 0.5, "yetenek seçilmediğinde güven 0,5'in altında kalmalı"


def test_score_and_auto_detect_agree(sm):
    """Rozetin gösterdiği karar ile gerçekte kullanılan yetenek asla ayrışmamalı."""
    for p in ("bilanco analizi yap", "bu arastirmayi slayt haline getir", "merhaba"):
        scored = sm.score_skill_for_prompt(p)[0]
        detected = sm.auto_detect_skill_for_prompt(p)
        assert (scored.name if scored else None) == (detected.name if detected else None), p


def test_ranking_is_sorted_and_covers_enabled_skills(sm):
    ranked = sm.rank_skills_for_prompt("bilanco analizi yap")
    assert len(ranked) == 2
    scores = [sc for _s, sc in ranked]
    assert scores == sorted(scores, reverse=True)


# --- 2. Değerlendirme kümesi ----------------------------------------------

def test_routing_eval_dataset_is_wellformed():
    rows = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) >= 60, "ölçüm için en az 60 örnek gerekiyor"

    known = {p.name for p in REPO_SKILLS.iterdir() if (p / "SKILL.md").is_file()}
    known |= {"media-agency-soldier", "slide-deck-architect"}  # alt çizgili dizin kopyaları
    ids = set()
    for r in rows:
        assert r["id"] not in ids, f"tekrarlanan kimlik: {r['id']}"
        ids.add(r["id"])
        assert r["prompt"].strip()
        assert "expected" in r
        if r["expected"] is not None:
            assert r["expected"] in known, f"bilinmeyen yetenek etiketi: {r['expected']}"

    assert sum(1 for r in rows if r["expected"] is None) >= 5, "alakasız örnekler olmadan yanlış pozitif ölçülemez"


# --- 3. Köprü sağlamlığı ---------------------------------------------------

class _Stdin:
    """stdin.write, stdout okunmaya başlayana kadar bloke olur (dolu boru taklidi)."""

    def __init__(self, reading: threading.Event):
        self._reading = reading
        self.buf = []
        self.closed = False

    def write(self, s):
        assert self._reading.wait(timeout=10), "stdout okunmadan stdin yazımı çözülmedi"
        self.buf.append(s)

    def flush(self):
        pass

    def close(self):
        self.closed = True


class _Stdout:
    def __init__(self, lines, reading: threading.Event):
        self._iter = iter(lines)
        self._reading = reading

    def readline(self):
        self._reading.set()
        return next(self._iter, "")

    def close(self):
        pass


def test_large_stdin_payload_does_not_deadlock_with_stdout(tmp_path, monkeypatch):
    """
    Büyük prompt stdin'e yazılırken stdout okuması başlayabilmeli.

    Regresyon: yük stdin'e bu iş parçacığından yazılıyordu; boru tamponu dolduğunda
    write() bloke oluyor, agy de stdout tamponu dolduğu için ilerleyemiyordu.
    Sahte süreç bu durumu birebir kurar: stdin.write yalnızca stdout okunmaya
    başladıktan sonra çözülür. Eski davranışta bu test kilitlenirdi.
    """
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db"))

    reading = threading.Event()
    seen = {}

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            seen["proc"] = self
            self.pid = 1234
            self.stdin = _Stdin(reading) if kwargs.get("stdin") == subprocess.PIPE else None
            self.stdout = _Stdout(['{"event": "result", "result": {"response": "tamam"}}\n', ""], reading)

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    long_prompt = "rapor metni " * (ARGV_PROMPT_SAFE_LIMIT // 10)
    done = threading.Event()

    def _run():
        bridge._execute_background_task_worker(
            task_id="deadlock-1", task_name="Uzun Görev", prompt=long_prompt,
            mode="plan", save_report=False,
        )
        done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    assert done.wait(timeout=30), "stdin yazımı ile stdout okuması kilitlendi"

    proc = seen["proc"]
    assert proc.stdin.closed, "stdin yazıldıktan sonra kapatılmalı"
    assert json.loads("".join(proc.stdin.buf))["message"]["content"] == long_prompt


def test_terminate_does_not_hold_lock_during_taskkill(monkeypatch):
    """
    Süreç ağacı öldürülürken köprü kilidi tutulmamalı.

    terminate_current_process arayüz iş parçacığından çağrılır; taskkill + wait
    kilidin içinde çalışırsa hem pencere donar hem de işçinin finally bloğu
    (aynı kilidi isteyen) bekler.
    """
    bridge = AgyProcessBridge()
    in_kill = threading.Event()
    release = threading.Event()
    lock_free = {"ok": False}

    class DummyProc:
        pid = 999

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return None

    def fake_run(*args, **kwargs):
        in_kill.set()
        # Öldürme sürerken başka bir iş parçacığı kilidi alabilmeli.
        release.wait(timeout=5)
        return None

    monkeypatch.setattr(subprocess, "run", fake_run)
    bridge._current_process = DummyProc()
    bridge._is_running = True

    t = threading.Thread(target=bridge.terminate_current_process, daemon=True)
    t.start()
    assert in_kill.wait(timeout=5), "taskkill çağrılmadı"
    lock_free["ok"] = bridge._lock.acquire(timeout=2)
    if lock_free["ok"]:
        bridge._lock.release()
    release.set()
    t.join(timeout=5)

    assert lock_free["ok"], "taskkill sürerken köprü kilidi tutuluyor (arayüz donar)"
    assert bridge._is_running is False


def test_concurrent_background_tasks_keep_token_total(tmp_path, monkeypatch):
    """Eşzamanlı iki görevin token toplamı kaybolmamalı (kilitsiz += kaybediyordu)."""
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db"))

    line = json.dumps({
        "event": "result",
        "result": {"response": "bitti", "usage": {"input_tokens": 100, "output_tokens": 50,
                                                  "total_tokens": 150}},
    }) + "\n"

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            self.pid = 77
            self.stdin = None
            self._lines = iter([line, ""])
            self.stdout = self

        def readline(self):
            time.sleep(0.01)  # iki işçinin sayaç güncellemesini örtüştür
            return next(self._lines, "")

        def close(self):
            pass

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    threads = [
        threading.Thread(
            target=bridge._execute_background_task_worker,
            kwargs=dict(task_id=f"tok-{i}", task_name=f"Görev {i}", prompt="kısa",
                        mode="plan", save_report=False),
            daemon=True,
        )
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive()

    assert bridge.background_total_tokens == 4 * 150


def test_worker_closes_ledger_when_process_cannot_start(tmp_path, monkeypatch):
    """agy hiç başlatılamazsa görev RUNNING kalmamalı (defterde açık kayıt bırakmaz)."""
    ledger = TaskLedger(db_path=tmp_path / "ledger.db")
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", ledger)
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    def boom(*args, **kwargs):
        raise FileNotFoundError("agy bulunamadı")

    monkeypatch.setattr("subprocess.Popen", boom)

    bridge._execute_background_task_worker(
        task_id="fail-1", task_name="Başlamayan Görev", prompt="kısa",
        mode="plan", save_report=False,
    )

    rec = ledger.get_task("fail-1")
    assert rec is not None
    assert rec["status"] != "RUNNING", f"görev defterde açık kaldı: {rec['status']}"
    assert "agy bulunamadı" in (rec.get("error") or "")


# --- 4. Köprü güven puanı ve sinyali ---------------------------------------

def test_bridge_exposes_confidence_and_emits_signal(tmp_path):
    """Köprü kararı güven puanıyla birlikte yayınlamalı (arayüz rozeti için)."""
    from entropy.core.event_bus import bus

    _write_skill(tmp_path, "financial-auditor", "Şirket bilançolarını ve nakit akımını denetler")
    manager = SkillManager(root_skills_dir=tmp_path)
    bridge = AgyProcessBridge()

    seen = []
    bus.skill_detected.connect(lambda name, conf: seen.append((name, conf)))
    try:
        skill, conf = bridge.score_skill_for_prompt("bilanco ve nakit akim analizi yap", sm=manager)
    finally:
        try:
            bus.skill_detected.disconnect()
        except Exception:
            pass

    assert skill is not None and skill.name == "financial-auditor"
    assert 0.5 <= conf <= 1.0
    assert bridge.last_skill_confidence == conf
    assert seen and seen[-1][0] == "financial-auditor"

    # Eski çağrı biçimi (yalnızca yetenek) bozulmamalı
    assert bridge.detect_skill_for_prompt("bilanco ve nakit akim analizi yap", sm=manager).name == "financial-auditor"
