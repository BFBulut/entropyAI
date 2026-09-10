"""FAZ 1 bağlama testleri: rapor izleyici main'e bağlı mı, /provider yerel komut mu."""

import inspect

import pytest


# ---------------------------------------------------------------- report_watcher

def test_main_starts_and_stops_report_watcher():
    """main() rapor izleyiciyi başlatmalı, _on_quit içinde durdurmalı."""
    from entropy import main as main_mod

    src = inspect.getsource(main_mod.main)
    assert "start_report_watcher()" in src
    assert "stop_report_watcher()" in src
    # stop, kapanış kancasının içinde olmalı (kancadan sonra gelen bir çağrı işe yaramaz)
    assert src.index("def _on_quit") < src.index("stop_report_watcher()")


def test_report_watcher_exports_start_stop():
    from entropy.brain import report_watcher

    assert callable(report_watcher.start_report_watcher)
    assert callable(report_watcher.stop_report_watcher)


# ---------------------------------------------------------------- /provider

class _FakeBridge:
    provider_name = "agy"
    selected_model = "gemini-3-pro"
    active_project_dir = None


def test_provider_show_returns_current_provider_and_model():
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/provider", _FakeBridge())
    assert out is not None
    assert "agy" in out
    assert "gemini-3-pro" in out


def test_provider_unknown_name_returns_error_message():
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/provider gemini", _FakeBridge())
    assert out is not None
    assert "gemini" in out
    assert "agy" in out and "claude" in out  # geçerli listeyi göstermeli


def test_provider_set_without_ui_manager_reports_error(monkeypatch):
    from entropy.ui.manager import EntropyUIManager
    from entropy.core.slash_commands import try_handle_local_command

    monkeypatch.setattr(EntropyUIManager, "instance", None, raising=False)
    out = try_handle_local_command("/provider claude", _FakeBridge())
    assert out is not None
    assert "değiştirilemedi" in out.lower() or "hazır değil" in out.lower()


def test_provider_set_calls_ui_manager_switch_provider(monkeypatch):
    from entropy.ui.manager import EntropyUIManager
    from entropy.core.slash_commands import try_handle_local_command

    calls = []

    class _FakeMgr:
        bridge = type("B", (), {"selected_model": "claude-opus-5"})()

        def switch_provider(self, name):
            calls.append(name)
            return True

    monkeypatch.setattr(EntropyUIManager, "instance", _FakeMgr(), raising=False)
    out = try_handle_local_command("/provider claude", _FakeBridge())
    assert calls == ["claude"]
    assert "claude-opus-5" in out


def test_non_provider_command_still_falls_through():
    from entropy.core.slash_commands import try_handle_local_command

    # /providers (çoğul) yerel komut değildir; AGY'ye gitmelidir.
    assert try_handle_local_command("/providers", _FakeBridge()) is None
    assert try_handle_local_command("normal soru", _FakeBridge()) is None


def test_provider_listed_in_local_commands():
    from entropy.core.slash_commands import LOCAL_COMMANDS

    assert any(c.name == "/provider" for c in LOCAL_COMMANDS)
