"""Proxy module forwarding to skills/media-agency-soldier/scripts/agency_soldier.py."""
import sys
from pathlib import Path

_p = str(Path(__file__).resolve().parents[1] / "media-agency-soldier" / "scripts")
if _p not in sys.path:
    sys.path.insert(0, _p)

import agency_soldier
from agency_soldier import AgencySoldier, run_agency_soldier

__all__ = ["AgencySoldier", "run_agency_soldier"]
