"""Proxy module forwarding to skills/media-agency-soldier/scripts/campaign_architect.py."""
import sys
from pathlib import Path

_p = str(Path(__file__).resolve().parents[1] / "media-agency-soldier" / "scripts")
if _p not in sys.path:
    sys.path.insert(0, _p)

import campaign_architect
from campaign_architect import (
    CampaignArchitect,
    RelationalCampaignItem,
    GoogleSearchAd,
    UGCScriptScene,
    MetaAdCreative,
    TikTokReelsAd,
    MultiChannelAdsPackage,
    MasterCampaignPackage,
    MetaASCBlueprint,
    GooglePMaxBlueprint,
    EmailSMSFlow,
    MediaFlightPlan,
    GoogleDemandGenBlueprint,
    CreativeHookSwapPackage,
    AgencyOnboardingMilestone,
    AgencySLAAndOnboardingChecklist,
)

__all__ = [
    "CampaignArchitect",
    "RelationalCampaignItem",
    "GoogleSearchAd",
    "UGCScriptScene",
    "MetaAdCreative",
    "TikTokReelsAd",
    "MultiChannelAdsPackage",
    "MasterCampaignPackage",
    "MetaASCBlueprint",
    "GooglePMaxBlueprint",
    "GoogleDemandGenBlueprint",
    "CreativeHookSwapPackage",
    "AgencyOnboardingMilestone",
    "AgencySLAAndOnboardingChecklist",
    "EmailSMSFlow",
    "MediaFlightPlan",
]
