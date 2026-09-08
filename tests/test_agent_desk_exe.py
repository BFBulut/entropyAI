"""
Automated Test Suite: Entropy Agent Desk Compiled Executable Verification.
Verifies that EntropyAgentDesk.exe is built, exists, has valid binary size,
and responds to CLI commands cleanly.
"""

import subprocess
from pathlib import Path


def test_compiled_agent_desk_exe_exists_and_runs():
    project_root = Path(__file__).parent.parent
    exe_path = project_root / "dist" / "EntropyAgentDesk" / "EntropyAgentDesk.exe"

    assert exe_path.exists(), f"Compiled executable not found at: {exe_path}"
    assert exe_path.is_file()
    assert exe_path.stat().st_size > 1_000_000, "EXE binary size is too small (< 1MB)"

    # Execute --version flag on the compiled binary
    res = subprocess.run(
        [str(exe_path), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    assert res.returncode == 0
    assert "Entropy Agent Desk" in res.stdout
