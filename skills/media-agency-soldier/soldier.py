import sys
from pathlib import Path
import importlib.util

_SCRIPTS = Path(__file__).resolve().parent / "scripts"
_spec = importlib.util.spec_from_file_location("_scripts_soldier", _SCRIPTS / "agency_soldier.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

AgencySoldier = _mod.AgencySoldier
run_agency_soldier = _mod.run_agency_soldier
generate_markdown_report = _mod.generate_markdown_report

__all__ = ["AgencySoldier", "run_agency_soldier", "generate_markdown_report"]
