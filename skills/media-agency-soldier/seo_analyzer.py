import sys
from pathlib import Path
import importlib.util

_SCRIPTS = Path(__file__).resolve().parent / "scripts"
_spec = importlib.util.spec_from_file_location("_scripts_seo_analyzer", _SCRIPTS / "seo_analyzer.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SEOAndMarTechAuditor = _mod.SEOAndMarTechAuditor
TrackingTagDetection = _mod.TrackingTagDetection
SearchIntentScore = _mod.SearchIntentScore
SchemaOrgAuditResult = _mod.SchemaOrgAuditResult
CoreWebVitalsAuditResult = _mod.CoreWebVitalsAuditResult
IndexabilityAuditResult = _mod.IndexabilityAuditResult
SemanticClusterAuditResult = _mod.SemanticClusterAuditResult
SecurityAndPrivacyAuditResult = _mod.SecurityAndPrivacyAuditResult
ECommerceCROScorecard = _mod.ECommerceCROScorecard
SERPFeatureOpportunityAuditResult = _mod.SERPFeatureOpportunityAuditResult

__all__ = [
    "SEOAndMarTechAuditor",
    "TrackingTagDetection",
    "SearchIntentScore",
    "SchemaOrgAuditResult",
    "CoreWebVitalsAuditResult",
    "IndexabilityAuditResult",
    "SemanticClusterAuditResult",
    "SecurityAndPrivacyAuditResult",
    "ECommerceCROScorecard",
    "SERPFeatureOpportunityAuditResult",
]
