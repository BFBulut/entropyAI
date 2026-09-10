import sys
from pathlib import Path
import importlib.util

_SCRIPTS = Path(__file__).resolve().parent / "scripts"
_spec = importlib.util.spec_from_file_location("_scripts_campaign_architect", _SCRIPTS / "campaign_architect.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CampaignArchitect = _mod.CampaignArchitect
RelationalCampaignItem = _mod.RelationalCampaignItem
GoogleSearchAd = _mod.GoogleSearchAd
UGCScriptScene = _mod.UGCScriptScene
MetaAdCreative = _mod.MetaAdCreative
TikTokReelsAd = _mod.TikTokReelsAd
MultiChannelAdsPackage = _mod.MultiChannelAdsPackage
MasterCampaignPackage = _mod.MasterCampaignPackage
MetaASCBlueprint = _mod.MetaASCBlueprint
GooglePMaxBlueprint = _mod.GooglePMaxBlueprint
EmailSMSFlow = _mod.EmailSMSFlow
MediaFlightPlan = _mod.MediaFlightPlan
GoogleDemandGenBlueprint = _mod.GoogleDemandGenBlueprint
CreativeHookSwapPackage = _mod.CreativeHookSwapPackage
AgencyOnboardingMilestone = _mod.AgencyOnboardingMilestone
AgencySLAAndOnboardingChecklist = _mod.AgencySLAAndOnboardingChecklist

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
