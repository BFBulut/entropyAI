import sys
from pathlib import Path
import importlib.util

_SCRIPTS = Path(__file__).resolve().parent / "scripts"
_spec = importlib.util.spec_from_file_location("_scripts_media_calculator", _SCRIPTS / "media_calculator.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MediaAgencyCalculator = _mod.MediaAgencyCalculator
FunnelBudgetPlan = _mod.FunnelBudgetPlan
FunnelBudgetTier = _mod.FunnelBudgetTier
PromotionalMarginSimulation = _mod.PromotionalMarginSimulation
FunnelHealthScorecard = _mod.FunnelHealthScorecard
LTVPaybackScorecard = _mod.LTVPaybackScorecard
ContributionMarginAnalysis = _mod.ContributionMarginAnalysis
NCACAnalysis = _mod.NCACAnalysis
CreativeTestingBudgetEstimate = _mod.CreativeTestingBudgetEstimate
RFMSegmentResult = _mod.RFMSegmentResult
DiscountBreakEvenSimulation = _mod.DiscountBreakEvenSimulation
POASNetProfitSimulation = _mod.POASNetProfitSimulation
MarketingEfficiencyRatioAnalysis = _mod.MarketingEfficiencyRatioAnalysis
ABTestSignificanceAnalysis = _mod.ABTestSignificanceAnalysis
BudgetPacingAndRunRateAnalysis = _mod.BudgetPacingAndRunRateAnalysis

__all__ = [
    "MediaAgencyCalculator",
    "FunnelBudgetPlan",
    "FunnelBudgetTier",
    "PromotionalMarginSimulation",
    "FunnelHealthScorecard",
    "LTVPaybackScorecard",
    "ContributionMarginAnalysis",
    "NCACAnalysis",
    "CreativeTestingBudgetEstimate",
    "RFMSegmentResult",
    "DiscountBreakEvenSimulation",
    "POASNetProfitSimulation",
    "MarketingEfficiencyRatioAnalysis",
    "ABTestSignificanceAnalysis",
    "BudgetPacingAndRunRateAnalysis",
]
