"""
Media Agency Soldier Skill Package.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from url_analyzer import URLAnalyzer
from campaign_architect import CampaignArchitect
from soldier import AgencySoldier
from media_calculator import MediaAgencyCalculator
from seo_analyzer import SEOAndMarTechAuditor

__all__ = [
    "URLAnalyzer",
    "CampaignArchitect",
    "AgencySoldier",
    "MediaAgencyCalculator",
    "SEOAndMarTechAuditor",
]
