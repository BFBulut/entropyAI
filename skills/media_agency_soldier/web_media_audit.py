import sys
from pathlib import Path
import importlib.util

_SCRIPTS = Path(__file__).resolve().parent.parent / "media-agency-soldier" / "scripts"
_spec = importlib.util.spec_from_file_location("_scripts_web_media_audit", _SCRIPTS / "web_media_audit.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

generate_audit = _mod.generate_audit
print_ascii_summary = _mod.print_ascii_summary
main = _mod.main

__all__ = [
    "generate_audit",
    "print_ascii_summary",
    "main",
]
