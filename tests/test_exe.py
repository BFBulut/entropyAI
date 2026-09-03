"""Unit tests verifying compiled EntropyAI.exe executable and integration."""

from pathlib import Path
from entropy.platform.autostart import WindowsAutostartManager

def test_compiled_exe_exists():
    project_root = Path(__file__).parent.parent
    exe_path = project_root / "dist" / "EntropyAI" / "EntropyAI.exe"
    assert exe_path.exists()
    assert exe_path.is_file()
    assert exe_path.stat().st_size > 1_000_000  # > 1MB

def test_autostart_detects_compiled_exe(tmp_path):
    mgr = WindowsAutostartManager(app_name="EntropyAI_Test")
    mgr.startup_dir = tmp_path
    mgr.startup_bat = tmp_path / "EntropyAI_Test.bat"

    mgr.enable_autostart()
    content = mgr.startup_bat.read_text(encoding="utf-8")
    assert "EntropyAI.exe" in content
    assert "--mode floating" in content
