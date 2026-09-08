"""
Damıtma sayaçları, çift başlatma kilidi ve iş parçacığı güvenliği.

Kullanıcı üç sorun bildirdi (2026-09-07):
- Aynı yetenek için iki damıtma başlatılınca ikisi "biraz farklı" çalışıyordu:
  iki zincir aynı grubu iki kez damıtıp birbirinin üstüne yazıyordu.
- Diskteki rapor sayacı yeni bir başlatmada sıfırlanıyordu: tazeleme turu
  0'dan başlıyor, kaynak kümesi değişince (yeni rapor) her şey baştan okunuyordu.
- Damıtma başlattıktan sonra uygulama kapanıyordu: sonuç geri çağrısı işçi iş
  parçacığında koşuyor, oradan Qt sinyalleri/zincir başlatılıyordu.
"""

import os
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from entropy.core.event_bus import bus
from entropy.memory.distiller import MAX_SOURCES_PER_PASS, PlaybookDistiller, _ACTIVE_TASKS
from entropy.memory.playbook import PlaybookStore, SkillReportIndex


class _FakeBridge:
    def __init__(self, project_dir=None):
        self.active_project_dir = project_dir
        self.calls = []

    def send_background_task_async(self, **kwargs):
        self.calls.append(kwargs)

    def complete_last(self, text: str, success: bool = True):
        self.calls[-1]["on_result"](text, success)


def _store(root: Path, skill: str, n: int, start_ts: float = 1_700_000_000.0) -> PlaybookStore:
    rep = root / "Entropy" / "Skills" / skill / "Reports"
    rep.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        p = rep / f"r{i:03d}.md"
        p.write_text(f"---\ntitle: R{i}\n---\n\nAdim {i}.\n" + "x" * 400, encoding="utf-8")
        os.utime(p, (start_ts + i, start_ts + i))
    return PlaybookStore(vault_path=root, index=SkillReportIndex(index_path=root / "idx.json"))


_PROC = "## Calisma Adimlari\n1. Tara.\n2. Karsilastir.\n\n## Kontrol\n- Dogrula."


@pytest.fixture(autouse=True)
def _clean_active():
    _ACTIVE_TASKS.clear()
    yield
    _ACTIVE_TASKS.clear()


def test_second_start_for_same_skill_is_refused_while_running(tmp_path):
    store = _store(tmp_path, "demo", 3)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()

    first = d.run_via_bridge(bridge, "demo")
    second = d.run_via_bridge(bridge, "demo")

    assert first and not first.get("already_running")
    assert second and second["already_running"] is True
    assert len(bridge.calls) == 1, "ikinci zincir açılmamalı"

    bridge.complete_last(_PROC)
    third = d.run_via_bridge(bridge, "demo")  # bitti; yeniden başlatılabilir (tazeleme)
    assert third and not third.get("already_running")


def test_refresh_pass_keeps_counter_at_total_and_does_not_chain(tmp_path):
    n = MAX_SOURCES_PER_PASS + 5
    store = _store(tmp_path, "demo", n)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()

    # Tüm arşivi işle (iki tur).
    d.run_via_bridge(bridge, "demo")
    bridge.complete_last(_PROC)
    assert store.load("demo").processed_count == MAX_SOURCES_PER_PASS
    bridge.complete_last(_PROC + "\n\n## Ek\n- Devam.")
    pb = store.load("demo")
    assert pb.processed_count == n == pb.source_count
    calls_before = len(bridge.calls)

    got = []

    def _collect(name, done, total):
        got.append((name, done, total))

    bus.distill_progress.connect(_collect)
    try:
        started = d.run_via_bridge(bridge, "demo")
        assert started["batch_start"] == n - MAX_SOURCES_PER_PASS
        assert "tazeleme" in bridge.calls[-1]["task_name"]
        assert got and got[-1][1] == n, "tazeleme başlarken sayaç 0'a düşmemeli"
        bridge.complete_last(_PROC + "\n\n## Ek\n- Tazelendi.")
    finally:
        bus.distill_progress.disconnect(_collect)

    pb = store.load("demo")
    assert pb.processed_count == n, "tazeleme sonrası sayaç toplamda kalmalı"
    assert len(bridge.calls) == calls_before + 1, "tazeleme tek turdur, zincirlenmez"


def test_new_report_appended_continues_from_processed_count(tmp_path):
    n = MAX_SOURCES_PER_PASS + 10  # kuyruk 10 > 24//6: ayrı tur kalır
    store = _store(tmp_path, "demo", n)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()

    d.run_via_bridge(bridge, "demo")
    bridge.complete_last(_PROC)
    # Zincir ikinci turu açtı; onu bitirmeden yeni rapor gelsin.
    assert store.load("demo").processed_count == MAX_SOURCES_PER_PASS
    _ACTIVE_TASKS.clear()  # süren turu yok say (test amaçlı)

    late = tmp_path / "Entropy" / "Skills" / "demo" / "Reports" / "zzz_yeni.md"
    late.write_text("---\ntitle: Yeni\n---\n\nYeni rapor.\n" + "y" * 400, encoding="utf-8")
    os.utime(late, (1_700_000_000.0 + n + 10, 1_700_000_000.0 + n + 10))

    plan = d.plan("demo")
    assert plan["sources_total"] == n + 1
    assert plan["batch_start"] == MAX_SOURCES_PER_PASS, "yeni rapor sona eklendi; sayaç sıfırlanmamalı"


def test_removed_report_drops_counter_by_one(tmp_path):
    n = MAX_SOURCES_PER_PASS + 10  # kuyruk 10 > 24//6: ayrı tur kalır
    store = _store(tmp_path, "demo", n)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()
    d.run_via_bridge(bridge, "demo")
    bridge.complete_last(_PROC)
    _ACTIVE_TASKS.clear()

    (tmp_path / "Entropy" / "Skills" / "demo" / "Reports" / "r001.md").unlink()
    # Okunmuş bir rapor silindi: sayaç bir düşer, kalan okunmamışlar sıradadır; 0'a dönülmez.
    assert d.plan("demo")["batch_start"] == MAX_SOURCES_PER_PASS - 1


def test_playbook_roundtrip_keeps_processed_digest(tmp_path):
    from entropy.memory.playbook import SkillPlaybook

    pb = SkillPlaybook(skill="s", procedure="## A\n- b", source_count=3, processed_count=2,
                       source_digest="abc", processed_digest="def")
    back = SkillPlaybook.from_markdown(pb.to_markdown(), "s")
    assert back.processed_digest == "def" and back.processed_count == 2
    # Eski dosyalarda alan yok: boş kalır, sayaç sürer.
    legacy = SkillPlaybook.from_markdown("---\nskill: s\nsource_count: 3\n---\n\n# x\n\n## A\n", "s")
    assert legacy.processed_digest == "" and legacy.processed_count == 3


def test_result_callback_runs_on_main_thread(tmp_path, qapp=None):
    """İşçi iş parçacığından gelen sonuç ana iş parçacığında işlenmeli."""
    from PySide6.QtCore import QCoreApplication, QThread
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    store = _store(tmp_path, "demo", 2)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()
    d.run_via_bridge(bridge, "demo")
    cb = bridge.calls[-1]["on_result"]

    seen = {}

    def _on_updated(name):
        seen["thread"] = QThread.currentThread()

    bus.playbook_updated.connect(_on_updated)
    try:
        t = threading.Thread(target=cb, args=(_PROC, True), name="worker")
        t.start()
        t.join(5)
        assert store.load("demo") is None, "işçi iş parçacığında hemen yazılmamalı; ana döngüye taşınmalı"
        deadline = time.time() + 5
        while time.time() < deadline and store.load("demo") is None:
            QCoreApplication.processEvents()
            time.sleep(0.02)
        assert store.load("demo") is not None
        assert seen["thread"] is app.thread()
    finally:
        bus.playbook_updated.disconnect(_on_updated)


def test_crash_logging_installs_and_records_uncaught_exception(tmp_path):
    import logging
    import sys

    import entropy.core.crash_log as cl

    cl._INSTALLED = None
    old_hook = sys.excepthook
    try:
        path = cl.install_crash_logging(tmp_path / "logs")
        assert path is not None and path.name == "entropy.log"
        try:
            raise RuntimeError("deneme patlaması")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        for h in logging.getLogger().handlers:
            h.flush()
        assert "deneme patlaması" in path.read_text(encoding="utf-8")
    finally:
        sys.excepthook = old_hook
        for h in list(logging.getLogger().handlers):
            if getattr(h, "baseFilename", "").startswith(str(tmp_path)):
                logging.getLogger().removeHandler(h)
                h.close()
        cl._INSTALLED = None


def test_rejected_last_batch_ends_chain_without_refresh_restart(tmp_path, monkeypatch):
    """
    Ledger'da görülen hata: [120→123] bitti, 33 sn sonra kendiliğinden [0→24] başladı.
    Son grup reddedilip atlandığında zincir bitmeli; tazeleme turu açılmamalı.
    """
    import entropy.memory.distiller as dmod

    monkeypatch.setattr(dmod, "MAX_SOURCES_PER_PASS", 3)
    store = _store(tmp_path, "demo", 6)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()

    got = []
    bus.distill_progress.connect(lambda n, a, b: got.append((a, b)))
    d.run_via_bridge(bridge, "demo")
    long_proc = "## A\n" + "- madde\n" * 30 + "## B\n- x\n## C\n- y\n## D\n- z\n"
    bridge.complete_last(long_proc)                    # 0→3 kaydedildi, 3→6 açıldı
    bridge.complete_last("## A\n- kisa")               # ret → yeniden deneme
    bridge.complete_last("## A\n- kisa")               # ikinci ret → atla
    pb = store.load("demo")
    assert pb.processed_count == 6, "atlanan grup işlenmiş sayılmalı"
    assert got[-1] == (6, 6), "sayaç 6/6'ya çekilmeli (kart yeşile döner)"
    assert len(bridge.calls) == 3, "tazeleme turu açılmamalı (önceden 4. çağrı geliyordu)"


def test_small_tail_batch_joins_previous_pass(tmp_path, monkeypatch):
    import entropy.memory.distiller as dmod

    monkeypatch.setattr(dmod, "MAX_SOURCES_PER_PASS", 24)
    store = _store(tmp_path, "demo", 51)  # 24 + 24 + 3 → kuyruk 3 ≤ 24//6
    d = PlaybookDistiller(store=store)
    p1 = d.prepare("demo")
    assert len(p1["sources"]) == 24 and p1["processed_after"] == 24
    d.complete(p1, _PROC)
    p2 = d.prepare("demo")
    assert p2["batch_start"] == 24 and len(p2["sources"]) == 27 and p2["processed_after"] == 51


def test_legacy_fully_processed_playbook_is_green_despite_stale_digest(tmp_path):
    """
    Kullanıcı senaryosu: eski build 123/123 yazdı ama parmak izi mtime tabanlıydı
    (OneDrive dokununca değişti). Yeni build'de yan dosya yok → tek seferlik geçiş →
    durum 'guncel' olmalı, sayaç toplamda kalmalı; parmak izi uyuşmazlığı turuncu yapmamalı.
    """
    from entropy.memory.playbook import SkillPlaybook

    store = _store(tmp_path, "demo", 5)
    pb = SkillPlaybook(skill="demo", procedure=_PROC, source_count=5, processed_count=5,
                       source_digest="eski-mtime-parmak-izi", version=23)
    store.save(pb)
    assert store.state_path("demo").exists() is False
    assert store.status("demo")["state"] == "hafif-degisim", "geçiş öncesi eski mantık"

    d = PlaybookDistiller(store=store)
    assert d.plan("demo")["batch_start"] == 5           # geçiş burada yazılır
    st = store.status("demo")
    assert st["state"] == "guncel" and st["distilled_from"] == 5


def test_changed_report_content_becomes_unprocessed(tmp_path):
    store = _store(tmp_path, "demo", 3)
    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()
    d.run_via_bridge(bridge, "demo")
    bridge.complete_last(_PROC)
    assert store.status("demo")["state"] == "guncel"

    # Yalnızca dokunma (mtime): durum değişmemeli.
    p = tmp_path / "Entropy" / "Skills" / "demo" / "Reports" / "r001.md"
    os.utime(p, None)
    assert store.status("demo")["state"] == "guncel"

    # İçerik değişince o rapor yeniden okunmalı: 'kismi', sayaç 2/3, sıradaki grup yalnızca o dosya.
    p.write_text(p.read_text(encoding="utf-8") + "\nYeni bulgu.\n", encoding="utf-8")
    st = store.status("demo")
    assert st["state"] == "kismi" and st["distilled_from"] == 2
    plan = d.plan("demo")
    assert plan["batch_start"] == 2 and plan["sources_this_pass"] == 1


def test_same_named_report_in_two_folders_counts_once(tmp_path):
    """
    Gerçek kasada 123 kaynağın 18'i aynı adla hem Skills/<y>/Reports hem düz Reports
    altında vardı: aynı rapor iki kez damıtılıyor, yan dosyada ad çakışıyordu (104/123).
    """
    store = _store(tmp_path, "demo", 3)
    flat = tmp_path / "Entropy" / "Reports"
    flat.mkdir(parents=True)
    src = tmp_path / "Entropy" / "Skills" / "demo" / "Reports" / "r001.md"
    (flat / "r001.md").write_text(src.read_text(encoding="utf-8").replace("Adim 1", "Adim 1 (kopya)") + "\n#skill:demo\n", encoding="utf-8")
    (flat / "baska.md").write_text("---\ntitle: B\n---\n\n#skill:demo\n" + "z" * 300, encoding="utf-8")

    srcs = store.source_reports("demo")
    assert len(srcs) == 4, "ad çakışan kopya bir kez sayılmalı"
    assert sum(1 for p in srcs if p.name == "r001.md") == 1
    assert next(p for p in srcs if p.name == "r001.md").parent.name == "Reports" and "Skills" in str(next(p for p in srcs if p.name == "r001.md"))

    d = PlaybookDistiller(store=store)
    bridge = _FakeBridge()
    d.run_via_bridge(bridge, "demo")
    bridge.complete_last(_PROC)
    st = store.status("demo")
    assert st["state"] == "guncel" and st["distilled_from"] == 4 == st["source_count"]
