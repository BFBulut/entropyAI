"""Pytest configuration and test fixtures for Entropy AI."""

import os
import pytest
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Add src to pythonpath
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

@pytest.fixture
def sample_config():
    from entropy.core.config import EntropyConfig
    return EntropyConfig()

@pytest.fixture(scope="session")
def qapp():
    """Ensure offscreen platform plugin for headless CI/CD testing."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

@pytest.fixture(autouse=True)
def flush_qt_deferred_deletes():
    """
    Her testten sonra Qt'nin bekleyen `DeferredDelete` olaylarını boşaltır.

    Neden: testlerde olay döngüsü koşmadığı için `deleteLater()` çağrıları
    hiç işlenmiyordu; üst düzey (top-level) pencere sayısı koşum boyunca
    birikiyordu (yalnız üç arayüz dosyasında 155'e çıkıyor). ~155. canlı
    pencereden sonra offscreen Qt bir sonraki `show()` çağrısında süreci
    sessizce öldürüyordu (çıkış kodu 127, traceback/olay günlüğü kaydı yok);
    tam paket koşumu her seferinde ~%90-95'te,
    `test_focus_mode_hides_and_restores_side_panels` üzerinde düşüyordu.
    Boşaltmayla sayı 155 -> 63'e iniyor ve koşum tamamlanıyor.
    """
    app = QApplication.instance()
    before = {id(w) for w in app.topLevelWidgets()} if app is not None else set()
    yield
    try:
        from PySide6.QtCore import QEvent

        app = QApplication.instance()
        if app is None:
            return
        # Testin kendi açtığı üst düzey pencereler kapatılır; başkasının
        # (önceki testlerin/oturum düzeneğinin) pencerelerine dokunulmaz.
        for widget in list(app.topLevelWidgets()):
            if id(widget) in before:
                continue
            try:
                widget.close()
                widget.deleteLater()
            except Exception:
                pass
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def cleanup_task_scheduler():
    """Ensure background TaskScheduler threads are stopped after every test."""
    yield
    try:
        from entropy.scheduler.cron_engine import TaskScheduler
        TaskScheduler.reset_instance()
    except Exception:
        pass

@pytest.fixture(autouse=True)
def isolate_chat_history(tmp_path, monkeypatch):
    """Ensure tests never write dummy conversations into user's live chat history."""
    test_chat = tmp_path / "test_chat_history.json"
    import sys
    import entropy.core.config
    mod_cfg = sys.modules.get("entropy.core.config")
    if mod_cfg:
        monkeypatch.setattr(mod_cfg, "CHAT_HISTORY_FILE", test_chat, raising=False)
    import entropy.core.agy_bridge
    mod_agy = sys.modules.get("entropy.core.agy_bridge")
    if mod_agy:
        monkeypatch.setattr(mod_agy, "CHAT_HISTORY_FILE", test_chat, raising=False)
    yield





@pytest.fixture(autouse=True)
def _reset_distiller_state():
    """Damıtıcının modül durumu (süren görevler, iptaller) testler arasında sızmasın."""
    try:
        from entropy.memory import distiller as _d
    except Exception:
        yield
        return
    _d._ACTIVE_TASKS.clear()
    _d._CANCELLED.clear()
    _d._RETRIES.clear()
    yield
    _d._ACTIVE_TASKS.clear()
    _d._CANCELLED.clear()
    _d._RETRIES.clear()
