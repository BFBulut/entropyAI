"""
Tek kopya kilidi ve zincirlenen damıtma turları.
"""

import uuid
from pathlib import Path

import pytest

from entropy.core.event_bus import bus
from entropy.core.single_instance import SingleInstanceGuard
from entropy.memory.distiller import PlaybookDistiller
from entropy.memory.playbook import PlaybookStore, SkillReportIndex


def _second_launch_child(name: str) -> "subprocess.Popen":
    """
    İkinci kopyayı AYRI bir süreçte simüle eder.

    Gerçekte iki kopya iki süreçtir: ilk kopyanın olay döngüsü, ikincisi el
    sıkışma yanıtını beklerken çalışır. Aynı süreçte yapılırsa istemci bloklar,
    sunucu hiç kabul edemez ve test yapay olarak başarısız olur.
    """
    import subprocess
    import sys

    code = (
        "import os,sys; os.environ['QT_QPA_PLATFORM']='offscreen'; sys.path.insert(0,'src');"
        "from PySide6.QtCore import QCoreApplication; app=QCoreApplication([]);"
        "from entropy.core.single_instance import SingleInstanceGuard;"
        f"g=SingleInstanceGuard(name={name!r});"
        "acq=g.try_acquire(); ok=g.notify_existing() if not acq else False;"
        "print('ACQ', acq, 'NOTIFY', ok); sys.exit(0 if (not acq and ok) else 3)"
    )
    return subprocess.Popen([sys.executable, "-c", code], cwd=str(Path(__file__).resolve().parents[1]),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_single_instance_second_launch_activates_first(qapp):
    import time

    name = f"entropy-test-{uuid.uuid4().hex[:8]}"
    first = SingleInstanceGuard(name=name)
    assert first.try_acquire() is True

    fired = []
    first.activated.connect(lambda: fired.append(1))

    child = _second_launch_child(name)
    deadline = time.time() + 15.0
    while child.poll() is None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    out, err = child.communicate(timeout=5)
    assert child.returncode == 0, f"ikinci kopya kilidi alamamalı ve bildirmeli: rc={child.returncode} out={out} err={err[-300:]}"

    for _ in range(50):
        qapp.processEvents()
        time.sleep(0.01)
    assert fired, "ilk kopya öne çıkma sinyalini almalı"
    first.release()

    third = SingleInstanceGuard(name=name)
    assert third.try_acquire() is True, "kilit bırakılınca yeniden alınabilmeli"
    third.release()


class _ChainBridge:
    """Her çağrıyı kaydeder; drain() ile sonuçları sırayla teslim eder (zincir dahil)."""

    active_project_dir = None

    def __init__(self, reply):
        self.calls = []
        self.reply = reply

    def send_background_task_async(self, **kw):
        self.calls.append(kw)

    def drain(self, max_rounds=20):
        i = 0
        while i < len(self.calls) and i < max_rounds:
            self.calls[i]["on_result"](self.reply, True)
            i += 1
        return i


def _vault(root: Path, skill: str, n: int) -> PlaybookStore:
    rep = root / "Entropy" / "Skills" / skill / "Reports"
    rep.mkdir(parents=True)
    for i in range(n):
        (rep / f"r{i}.md").write_text(f"---\ntitle: R{i}\n---\n\nSite denetimi {i}.\n" + "x" * 500, encoding="utf-8")
    return PlaybookStore(vault_path=root, index=SkillReportIndex(index_path=root / "idx.json"))


RICH = "\n\n".join(
    f"## {h}\n" + ("madde " * 60).strip()
    for h in ("Ne Zaman Kullanılır", "Çalışma Adımları", "Karar Ölçütleri", "Bilinen Tuzaklar", "Çıktı Biçimi")
)


def test_auto_continue_chains_passes_and_reports_progress(tmp_path, monkeypatch):
    import entropy.memory.distiller as dmod

    monkeypatch.setattr(dmod, "MAX_SOURCES_PER_PASS", 4)
    store = _vault(tmp_path, "demo", 10)
    d = PlaybookDistiller(store=store)
    bridge = _ChainBridge(RICH)

    progress = []
    bus.distill_progress.connect(lambda s, a, b: progress.append((a, b)))
    try:
        started = d.run_via_bridge(bridge, "demo", auto_continue=True, agent="distiller")
        assert started["batch_start"] == 0 and started["sources"] == 4
        assert bridge.calls[0]["agent"] == "distiller"
        rounds = bridge.drain()
    finally:
        bus.distill_progress.disconnect()

    assert rounds == 3, "10 rapor, 4'lük turlar -> 3 tur zincirlenmeli"
    assert [c["task_name"].split("[")[1].rstrip("]") for c in bridge.calls] == ["0→4/10", "4→8/10", "8→10/10"]
    assert progress[-1] == (10, 10)
    assert store.status("demo")["state"] == "guncel"
    assert store.load("demo").version == 3


def test_distill_stop_halts_chain_and_terminates_running_task(tmp_path, monkeypatch):
    """/distill stop: süren görev sonlandırılır, sıradaki tur başlamaz, iptal kayıt yazmaz."""
    import entropy.memory.distiller as dmod
    from entropy.core.slash_commands import try_handle_local_command

    monkeypatch.setattr(dmod, "MAX_SOURCES_PER_PASS", 4)
    store = _vault(tmp_path, "demo", 10)
    d = PlaybookDistiller(store=store)

    class _Bridge(_ChainBridge):
        active_project_dir = None
        killed = []

        def terminate_background_task(self, task_id):
            self.killed.append(task_id)

    bridge = _Bridge(RICH)
    d.run_via_bridge(bridge, "demo", auto_continue=True)
    assert PlaybookDistiller.active_skills() == ["demo"]

    class _SM:
        def __init__(self, *a, **k): pass
        def list_skills(self):
            from entropy.skills.manager import SkillDefinition
            return [SkillDefinition(name="demo", description="d", instructions="", path=str(tmp_path), scripts=[])]

    import entropy.skills.manager as sm_mod
    monkeypatch.setattr(sm_mod, "SkillManager", _SM)

    out = try_handle_local_command("/distill stop demo", bridge, distiller=d)
    assert "durduruldu" in out and bridge.killed == [bridge.calls[0]["task_id"]]

    # Süren görevin sonucu gelse bile kaydedilmemeli ve zincir sürmemeli
    bridge.calls[0]["on_result"](RICH, True)
    assert store.load("demo") is None
    assert len(bridge.calls) == 1

    # Yeni bir başlatma iptali sıfırlar
    d.run_via_bridge(bridge, "demo", auto_continue=False)
    assert len(bridge.calls) == 2
    bridge.calls[1]["on_result"](RICH, True)
    assert store.load("demo") is not None


def test_token_badge_separates_chat_and_background():
    from entropy.ui.widgets.token_badge import format_token_badge

    class B:
        session_total_tokens = 0; total_tokens_used = 0; latest_output_tokens = 0; latest_input_tokens = 0
        latest_thinking_tokens = 0; latest_cache_read_tokens = 0; session_turn_count = 0; session_cache_tokens = 0
        background_total_tokens = 0; last_background_usage = {}

    b = B()
    assert format_token_badge(b)[0] == "Tokens: 0"

    b.background_total_tokens = 103_974
    b.last_background_usage = {"total_tokens": 62_226, "input_tokens": 36_170, "output_tokens": 26_056}
    text, tip = format_token_badge(b)
    assert text == "Arka plan: 103k (son 62k)", text
    assert "Sohbet" not in text and "62,226" in tip

    b.session_total_tokens = 12_400; b.total_tokens_used = 3_100; b.session_turn_count = 4
    text, _ = format_token_badge(b)
    assert text == "Sohbet: 12k (+3k)  ·  Arka plan: 103k (son 62k)", text

    b.background_total_tokens = 1_250_000
    assert "1.25M" in format_token_badge(b)[0]


def test_auto_continue_off_runs_single_pass(tmp_path, monkeypatch):
    import entropy.memory.distiller as dmod

    monkeypatch.setattr(dmod, "MAX_SOURCES_PER_PASS", 4)
    store = _vault(tmp_path, "demo", 10)
    bridge = _ChainBridge(RICH)
    PlaybookDistiller(store=store).run_via_bridge(bridge, "demo", auto_continue=False)
    bridge.drain()
    assert len(bridge.calls) == 1
    assert store.status("demo")["state"] == "kismi"
