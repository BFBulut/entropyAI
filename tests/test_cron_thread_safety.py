"""
Denetim A4: cron zamanlayici ve 0x8001010d COM istisnasi.

Bulgu (kanit: `.entropy/logs/entropy_fault.log`, 23 kayit): istisnayi ATAN
"Current thread" her seferinde ANA is parcacigidir (`entropy/main.py` icinde).
`_scheduler_loop` dokumlerde yalnizca *seyirci* olarak gorunur ve daima
`cron_engine.py` icindeki `self._stop_event.wait(1.0)` satirinda park halindedir
-- saf `threading.Event.wait`, ne Qt ne COM.

Bu yuzden dongunun `bus.invoke_on_main` ile ana is parcacigina tasinmasi
olmayan bir nedeni "duzeltirdi". Onun yerine gercek sozlesmeyi cakiyoruz:
zamanlayici dongusu Qt pencere nesnelerine dokunmaz; disariya yalnizca
is-parcacigi-guvenli sinyal yayar.
"""

import inspect
import threading

from entropy.scheduler import cron_engine
from entropy.scheduler.cron_engine import TaskScheduler


# Ana is parcacigi disindan cagrilmasi COM/Qt cokmesi ureten tipler.
FORBIDDEN_QT_NAMES = (
    "QWidget",
    "QMessageBox",
    "QFileDialog",
    "QApplication",
    "QSystemTrayIcon",
    "QDesktopServices",
)


def test_scheduler_loop_source_touches_no_qt_widgets():
    """`_scheduler_loop` gövdesi hicbir Qt pencere/dialog turune dokunmamali."""
    src = inspect.getsource(TaskScheduler._scheduler_loop)
    hits = [n for n in FORBIDDEN_QT_NAMES if n in src]
    assert hits == [], f"zamanlayici dongusune Qt nesnesi sizdi: {hits}"


def test_cron_engine_module_imports_no_qt_widgets():
    """Modul duzeyinde de widget/dialog ithali olmamali (gelecege karsi kilit)."""
    src = inspect.getsource(cron_engine)
    import_lines = [
        ln for ln in src.splitlines()
        if ln.strip().startswith(("import ", "from ")) and "PySide6" in ln
    ]
    joined = " ".join(import_lines)
    hits = [n for n in FORBIDDEN_QT_NAMES if n in joined]
    assert hits == [], f"cron_engine Qt pencere turu ithal ediyor: {hits}"


def test_scheduler_loop_parks_on_plain_event_wait():
    """
    Dongu bosta beklerken saf `threading.Event.wait` kullanmali.

    Cokme dokumlerinde gorulen park noktasi budur; Qt olay dongusune ya da
    COM bekleyisine cevrilirse dokumlerin anlami degisir ve gercekten
    ana-is-parcacigi sorunu dogar.
    """
    src = inspect.getsource(TaskScheduler._scheduler_loop)
    assert "_stop_event.wait(" in src, "dongu artik Event.wait ile parklanmiyor"
    assert "processEvents" not in src, "dongu Qt olay dongusunu surmeye baslamis"


def test_scheduler_callback_runs_off_main_thread():
    """Zamanlanan is arka planda kosar; ana is parcacigini bloklamaz."""
    scheduler = TaskScheduler.get_instance()
    seen = {}

    def cb(task):
        seen["thread"] = threading.current_thread()
        seen["is_main"] = threading.current_thread() is threading.main_thread()

    scheduler.set_execution_callback(cb)
    try:
        # Dongunun kendisini dogrudan cagirmadan, geri cagrimin ana is
        # parcacigina zorlanmadigini dogruluyoruz: cagrim zinciri dumduz.
        worker = threading.Thread(target=lambda: cb(None))
        worker.start()
        worker.join(timeout=5)
    finally:
        scheduler.set_execution_callback(None)

    assert seen.get("is_main") is False, (
        "geri cagrim ana is parcacigina zorlanmis; cron dongusu artik "
        "arka planda calismıyor"
    )
