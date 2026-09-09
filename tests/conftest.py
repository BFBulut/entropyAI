"""Pytest configuration and test fixtures for Entropy AI."""

import os
import pytest
import tempfile
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Add src to pythonpath
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# --- kullanici durumu yalitimi (MODUL YUKLENIRKEN) ------------------------
# `entropy.core.task_ledger` ice aktarilir aktarilmaz `TaskLedger()` orneginin
# yolu sabitlenir (satir 477: `task_ledger = TaskLedger()`), yani fixture'a
# birakilirsa gec kalinir. Ayni sekilde `CognitiveMemorySystem()` varsayilani
# da burada tmp'ye baglanir. Olculen sizinti: kullanicinin gercek
# `~/.entropy/tasks_ledger.db` dosyasinda `project_path` sutunu
# `...\pytest-of-batu_\pytest-2301\...` olan satirlar.
_USER_STATE_TMP = Path(tempfile.mkdtemp(prefix="entropy_test_state_"))
os.environ["ENTROPY_TASK_LEDGER_DB"] = str(_USER_STATE_TMP / "tasks_ledger.db")
os.environ.setdefault(
    "ENTROPY_COGNITIVE_DB", str(_USER_STATE_TMP / "cognitive_memory.db")
)

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

@pytest.fixture(scope="session", autouse=True)
def _isolate_obsidian_vault_session(tmp_path_factory):
    """Oturum boyu kalici kasa yonlendirmesi.

    Test bazli monkeypatch yeterli degil: arka plan is parcaciklari (koprunun
    `_execute_background_task_worker` gibi) raporu fixture teardown'undan SONRA
    yaziyordu ve gercek kasaya dusuyordu. Oturum kapsaminda bir kez
    yonlendirilince yaris penceresi kapanir.
    """
    # DIKKAT: `entropy/core/__init__.py` `from entropy.core.config import config`
    # yaptigi icin `import entropy.core.config as m` MODULU DEGIL, EntropyConfig
    # ORNEGINI dondurur (paket ozniteligi alt modulu golgeler). Gercek modul
    # yalnizca sys.modules uzerinden guvenle alinir.
    import entropy.core.config  # noqa: F401  (sys.modules'e yuklenmesi icin)

    cfg_mod = sys.modules["entropy.core.config"]
    session_vault = tmp_path_factory.mktemp("session_vault")
    (session_vault / "Entropy").mkdir(parents=True, exist_ok=True)
    os.environ["ENTROPY_VAULT_PATH"] = str(session_vault)
    object.__setattr__(cfg_mod.config, "obsidian_vault_path", session_vault)
    yield session_vault


@pytest.fixture(autouse=True)
def isolate_obsidian_vault(tmp_path, monkeypatch):
    """Faz 8: hicbir test kullanicinin gercek Obsidian kasasina yazmasin.

    Kanit: `Entropy/Projects/test_bridge_background_task_*` altinda 195 rapor,
    `ObsidianVaultManager()` varsayilan yolu (config.obsidian_vault_path)
    uzerinden test kosumlarindan yazilmisti. Testler `vault_path` gecmedigi her
    yerde artik tmp'ye duser.
    """
    import entropy.core.config  # noqa: F401

    cfg_mod = sys.modules["entropy.core.config"]  # bkz. oturum fixture'i: golgeleme
    fake_vault = tmp_path / "obsidian_vault"
    (fake_vault / "Entropy").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ENTROPY_VAULT_PATH", str(fake_vault))
    monkeypatch.setattr(cfg_mod.config, "obsidian_vault_path", fake_vault)
    yield


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


@pytest.fixture(autouse=True)
def isolate_cognitive_memory_db(tmp_path, monkeypatch):
    """
    Hicbir test uretim bellek veritabanina (`~/.entropy/cognitive_memory.db`)
    yazmasin.

    Kanit: `CognitiveMemorySystem()` yol verilmeden kurulunca varsayilani
    `Path.home()/".entropy"` altindaydi; UI/damitici/graf testlerinin cogu yol
    gecmiyor ve kullanicinin canli belleğine satir ekliyordu. `ENTROPY_COGNITIVE_DB`
    ile tmp'ye yonlendirilir (kasa yalitimiyla ayni desen).
    """
    db = tmp_path / "cognitive" / "cognitive_memory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ENTROPY_COGNITIVE_DB", str(db))
    yield db


@pytest.fixture(scope="session", autouse=True)
def _isolate_user_state_session(tmp_path_factory):
    """
    Oturum boyu: gorev defteri ve ayar dosyasi kullanicinin canli
    `~/.entropy/tasks_ledger.db` ile `.entropy/settings.json` dosyalarina
    DEGMESIN.

    Neden oturum kapsami: test bazli monkeypatch yetmiyor; koprunun
    `_execute_background_task_worker` is parcacigi teardown'dan sonra yaziyor
    (kasa yalitiminda ayni yaris gorulmustu). Olculen sizinti: defterde
    `project_path = ...pytest-of-batu_/pytest-2301/...` satirlari, ayar
    dosyasinda ayni yolu tasiyan `default_project_path`.
    """
    import entropy.core.config  # noqa: F401

    root = tmp_path_factory.mktemp("user_state")
    cfg_mod = sys.modules["entropy.core.config"]
    cfg_mod.SETTINGS_FILE = root / "settings.json"
    # Yetenek etkin/pasif durumu: yalitilmamis bir `SkillManager()` kuran her
    # test kullanicinin `~/.entropy/skills_state.json` dosyasina yaziyordu
    # (olculdu: tam kosuda mtime degisiyordu, icerik ayni kalsa da).
    try:
        import entropy.skills.manager as _skills_mod

        _skills_mod.USER_SKILLS_STATE_FILE = root / "skills_state.json"
    except Exception:
        pass
    yield root
