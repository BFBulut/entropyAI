"""Windows Autostart Integration for Entropy AI."""

import os
import sys
from pathlib import Path
from typing import Optional

class WindowsAutostartManager:
    """Manages Windows Startup folder and registry autostart for Entropy AI."""

    def __init__(self, app_name: str = "EntropyAI"):
        self.app_name = app_name
        self.startup_dir = self._get_startup_directory()
        self.startup_bat = self.startup_dir / f"{self.app_name}.bat"

    def _get_startup_directory(self) -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            p = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            if p.exists():
                return p
        # Fallback to user home
        fallback = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def is_autostart_enabled(self) -> bool:
        """Check if startup batch file exists."""
        return self.startup_bat.exists()

    def enable_autostart(
        self,
        exe_path: Optional[str] = None,
        python_exe: Optional[str] = None,
        script_path: Optional[str] = None
    ) -> bool:
        """Create a startup script in the Windows Startup directory."""
        if exe_path:
            target = f'"{exe_path}" --mode floating'
        elif python_exe and script_path:
            target = f'"{python_exe}" "{script_path}" --mode floating'
        elif getattr(sys, 'frozen', False):
            target = f'"{sys.executable}" --mode floating'
        else:
            project_root = Path(__file__).parent.parent.parent.parent
            dist_exe = project_root / "dist" / "EntropyAI" / "EntropyAI.exe"
            onefile_exe = project_root / "dist" / "EntropyAI.exe"
            if dist_exe.exists():
                target = f'"{dist_exe}" --mode floating'
            elif onefile_exe.exists():
                target = f'"{onefile_exe}" --mode floating'
            else:
                target = f'"{sys.executable}" "{project_root / "run_entropy.py"}" --mode floating'

        batch_content = (
            "@echo off\n"
            f'start "" {target}\n'
        )
        try:
            self.startup_bat.write_text(batch_content, encoding="utf-8")
            return True
        except Exception:
            return False

    def disable_autostart(self) -> bool:
        """Remove startup script from Windows Startup directory."""
        try:
            if self.startup_bat.exists():
                self.startup_bat.unlink()
            return True
        except Exception:
            return False
