"""Unit tests verifying compiled EntropyAI.exe executable and integration."""

from pathlib import Path

def test_compiled_exe_exists():
    project_root = Path(__file__).parent.parent
    exe_path = project_root / "dist" / "EntropyAI" / "EntropyAI.exe"
    assert exe_path.exists()
    assert exe_path.is_file()
    assert exe_path.stat().st_size > 1_000_000  # > 1MB

