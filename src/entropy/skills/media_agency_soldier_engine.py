"""
Entropy AI Core Skills: MediaAgencySoldierEngine Bridge.
Connects Entropy AI runtime, event bus, and Agent Desk to the Media Agency Soldier capability.
"""

from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _find_scripts_dir() -> Optional[Path]:
    """
    skills/media-agency-soldier/scripts dizinini bulur.

    Kaynaktan çalışırken dosya <repo>/src/entropy/skills/ altındadır, yani depo
    kökü parents[3]'tür. PyInstaller ile paketlendiğinde ise veri dosyaları
    _internal/ altına açılır ve araya fazladan bir dizin girer; bu durumda
    doğru kök sys._MEIPASS'tir. Her iki düzen de sırayla denenir.
    """
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS))
    here = Path(__file__).resolve()
    candidates.extend(here.parents[2:5])  # _internal/ ve <repo> düzenlerini kapsar

    for root in candidates:
        candidate = root / "skills" / "media-agency-soldier" / "scripts"
        if candidate.is_dir():
            return candidate
    return None


_SCRIPTS_DIR = _find_scripts_dir()
if _SCRIPTS_DIR and str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from entropy.core.config import config
    from entropy.core.event_bus import bus
except ImportError:
    config = None
    bus = None

# Bu yardımcı betikler yetenek paketinin bir parçasıdır, çekirdek uygulamanın değil.
# Modül seviyesinde koşulsuz içe aktarılırlarsa, eksik oldukları anda
# entropy.skills paketi -> chat_mode -> ui.manager -> main zinciri boyunca
# uygulamanın tamamı açılmaz. Eksiklik, yalnızca bu yeteneği devre dışı bırakmalı.
URL_ANALYZER_AVAILABLE = True
try:
    from url_analyzer import URLAnalyzer
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
        GoogleDemandGenBlueprint,
        CreativeHookSwapPackage,
        AgencyOnboardingMilestone,
        AgencySLAAndOnboardingChecklist,
        EmailSMSFlow,
        MediaFlightPlan,
    )
    from agency_soldier import AgencySoldier, run_agency_soldier
    from media_calculator import (
        MediaAgencyCalculator,
        FunnelBudgetPlan,
        FunnelBudgetTier,
        PromotionalMarginSimulation,
        FunnelHealthScorecard,
        LTVPaybackScorecard,
        ContributionMarginAnalysis,
        NCACAnalysis,
        CreativeTestingBudgetEstimate,
        RFMSegmentResult,
        DiscountBreakEvenSimulation,
        POASNetProfitSimulation,
        MarketingEfficiencyRatioAnalysis,
        ABTestSignificanceAnalysis,
        BudgetPacingAndRunRateAnalysis,
    )
    from seo_analyzer import (
        SEOAndMarTechAuditor,
        TrackingTagDetection,
        SearchIntentScore,
        SchemaOrgAuditResult,
        CoreWebVitalsAuditResult,
        IndexabilityAuditResult,
        SemanticClusterAuditResult,
        SecurityAndPrivacyAuditResult,
        ECommerceCROScorecard,
        SERPFeatureOpportunityAuditResult,
    )
except ImportError as e:
    URL_ANALYZER_AVAILABLE = False
    URLAnalyzer = None
    CampaignArchitect = None
    AgencySoldier = None
    run_agency_soldier = None
    MediaAgencyCalculator = None
    SEOAndMarTechAuditor = None
    RelationalCampaignItem = None
    GoogleSearchAd = None
    UGCScriptScene = None
    MetaAdCreative = None
    TikTokReelsAd = None
    MultiChannelAdsPackage = None
    MasterCampaignPackage = None
    MetaASCBlueprint = None
    GooglePMaxBlueprint = None
    GoogleDemandGenBlueprint = None
    CreativeHookSwapPackage = None
    AgencyOnboardingMilestone = None
    AgencySLAAndOnboardingChecklist = None
    EmailSMSFlow = None
    MediaFlightPlan = None
    FunnelBudgetPlan = None
    FunnelBudgetTier = None
    PromotionalMarginSimulation = None
    FunnelHealthScorecard = None
    LTVPaybackScorecard = None
    ContributionMarginAnalysis = None
    NCACAnalysis = None
    CreativeTestingBudgetEstimate = None
    RFMSegmentResult = None
    DiscountBreakEvenSimulation = None
    POASNetProfitSimulation = None
    MarketingEfficiencyRatioAnalysis = None
    ABTestSignificanceAnalysis = None
    BudgetPacingAndRunRateAnalysis = None
    TrackingTagDetection = None
    SearchIntentScore = None
    SchemaOrgAuditResult = None
    CoreWebVitalsAuditResult = None
    IndexabilityAuditResult = None
    SemanticClusterAuditResult = None
    SecurityAndPrivacyAuditResult = None
    ECommerceCROScorecard = None
    SERPFeatureOpportunityAuditResult = None
    logger.warning(
        "Media Agency Soldier yetenek betikleri yüklenemedi (%s); bu yetenek devre dışı. "
        "Aranan dizin: %s",
        e,
        _SCRIPTS_DIR or "bulunamadı",
    )


class MediaAgencySoldierEngine:
    """Production bridge engine integrating Media Agency Soldier into Entropy AI."""

    def __init__(self, cache_dir: Optional[Path] = None):
        if not URL_ANALYZER_AVAILABLE:
            raise RuntimeError(
                "Media Agency Soldier yetenek betikleri bulunamadı; bu yetenek kullanılamıyor. "
                f"Beklenen dizin: skills/media-agency-soldier/scripts (arama sonucu: {_SCRIPTS_DIR or 'yok'})."
            )

        if cache_dir:
            self.cache_dir = Path(cache_dir)
        elif config and hasattr(config, "default_project_path"):
            self.cache_dir = Path(config.default_project_path) / ".entropy" / "media_agency_reports"
        else:
            self.cache_dir = Path.home() / ".entropy" / "media_agency_reports"

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self.analyzer = URLAnalyzer()
        self.architect = CampaignArchitect()
        self.soldier = AgencySoldier()
        self.calculator = MediaAgencyCalculator() if MediaAgencyCalculator else None
        self.seo_auditor = SEOAndMarTechAuditor() if SEOAndMarTechAuditor else None

    def analyze_offline_html(
        self,
        html_path: str | Path,
        url: Optional[str] = None,
        brand: Optional[str] = None
    ) -> Dict[str, Any]:
        """Performs offline analysis on local HTML markup."""
        p = Path(html_path)
        if not p.exists():
            raise FileNotFoundError(f"Offline HTML dosyası bulunamadı: {p}")

        content = p.read_text(encoding="utf-8", errors="replace")
        target_url = url or f"https://{p.stem}.local"
        analysis = self.analyzer.analyze_html(content, url=target_url)

        if brand:
            analysis["brand_info"]["brand_name"] = brand

        if bus and hasattr(bus, "terminal_output_received"):
            try:
                b_name = analysis.get("brand_info", {}).get("brand_name", "Bilinmeyen Marka")
                bus.terminal_output_received.emit(
                    f"\n[🚀 Medya Motoru] '{p.name}' analiz edildi. Marka: {b_name}\n"
                )
            except Exception:
                pass

        return analysis

    def analyze_url(self, url: str, brand: Optional[str] = None) -> Dict[str, Any]:
        """Fetches and analyzes live or mock URL."""
        target_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
        res = self.soldier.run(url=target_url, brand=brand)
        return res["analysis"]

    def generate_campaign_package(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generates relational campaigns and multichannel ad sets."""
        relational = self.architect.generate_relational_campaigns(analysis_result)
        brand = analysis_result.get("brand_info", {}).get("brand_name")
        ad_plans = self.architect.generate_multichannel_ad_plans(analysis_result)

        return {
            "brand": brand,
            "relational_campaigns": relational,
            "multichannel_ad_plans": ad_plans
        }

    def run_full_audit(
        self,
        source: str | Path,
        is_offline: bool = True,
        brand: Optional[str] = None,
        export_md: Optional[Path] = None,
        export_json: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Complete end-to-end audit: Analysis, Campaign Design, Multi-channel Ads, and Reports."""
        if is_offline:
            result = self.soldier.run(
                offline_html_path=str(source),
                brand=brand,
                export_json=str(export_json) if export_json else None,
                export_md=str(export_md) if export_md else None
            )
        else:
            result = self.soldier.run(
                url=str(source),
                brand=brand,
                export_json=str(export_json) if export_json else None,
                export_md=str(export_md) if export_md else None
            )

        # Ensure markdown report is embedded in return dictionary
        if export_md and Path(export_md).exists():
            result["markdown_report"] = Path(export_md).read_text(encoding="utf-8")
        else:
            from agency_soldier import generate_markdown_report
            result["markdown_report"] = generate_markdown_report(
                result["analysis"],
                result["campaigns"],
                result["ad_plans"]
            )

        if bus and hasattr(bus, "terminal_output_received"):
            try:
                b_name = result["analysis"]["brand_info"]["brand_name"]
                bus.terminal_output_received.emit(
                    f"\n[🎯 Medya Motoru] '{b_name}' için kampanya mimarisi ve rapor başarıyla oluşturuldu.\n"
                )
            except Exception:
                pass

        return result

    def calculate_unit_economics(
        self,
        analysis_result: Dict[str, Any],
        monthly_budget: float = 100000.0
    ) -> Dict[str, Any]:
        """Calculates media agency ROAS, MER, breakeven, and funnel budget allocation."""
        return self.architect.generate_unit_economics_plan(analysis_result, monthly_budget=monthly_budget)

    def run_deep_seo_audit(self, html: str, url: str = "") -> Dict[str, Any]:
        """Runs deep technical SEO, MarTech tracking tag detection, and intent classification."""
        if self.seo_auditor:
            return self.seo_auditor.run_full_seo_and_martech_audit(html, url=url)
        return {"error": "SEOAndMarTechAuditor not available"}

    def generate_meta_asc_blueprint(self, analysis_result: Dict[str, Any], monthly_budget: float = 50000.0):
        """Generates Meta Advantage+ Shopping Campaign specification."""
        return self.architect.generate_meta_asc_blueprint(analysis_result, monthly_meta_budget=monthly_budget)

    def generate_google_pmax_blueprint(self, analysis_result: Dict[str, Any], monthly_budget: float = 35000.0):
        """Generates Google Performance Max Asset Group blueprint."""
        return self.architect.generate_google_pmax_blueprint(analysis_result, monthly_google_budget=monthly_budget)

    def generate_retention_flows(self, brand_info: Dict[str, Any]):
        """Generates Klaviyo / Omnisend lifecycle retention flows."""
        return self.architect.generate_retention_flows(brand_info)

    def generate_google_demand_gen_blueprint(self, analysis_result: Dict[str, Any], monthly_budget: float = 30000.0):
        """Generates Google Demand Gen (Shorts & Discover) specification."""
        return self.architect.generate_google_demand_gen_blueprint(analysis_result, monthly_budget=monthly_budget)

    def generate_hook_swap_variations(self, analysis_result: Dict[str, Any], base_creative_name: str = "Kazanan UGC Video"):
        """Generates 5 distinct psychological hook variations for creative refresh."""
        return self.architect.generate_hook_swap_variations(analysis_result, base_creative_name=base_creative_name)

    def generate_agency_onboarding_sla(self, brand_name: str = "Marka"):
        """Generates 30-day Client Onboarding SLA roadmap and fail-closed gates."""
        return self.architect.generate_agency_onboarding_sla(brand_name=brand_name)

    def audit_security_and_privacy(self, html: str, headers: Optional[Dict[str, str]] = None):
        """Audits Content Security Policy (CSP), HSTS, and Google Consent Mode v2."""
        if self.seo_auditor:
            return self.seo_auditor.audit_security_and_privacy(html, headers=headers)
        return None

    def audit_ecommerce_cro(self, html: str):
        """Audits mobile sticky CTAs, 1-click express checkout, and checkout friction."""
        if self.seo_auditor:
            return self.seo_auditor.audit_ecommerce_cro(html)
        return None

    def audit_serp_features(self, html: str, schema_audit: Optional[Any] = None):
        """Audits readiness for Google Featured Snippets, PAA, and Rich Merchant results."""
        if self.seo_auditor:
            return self.seo_auditor.audit_serp_features(html, schema_audit=schema_audit)
        return None


__all__ = [
    "MediaAgencySoldierEngine",
    "URLAnalyzer",
    "CampaignArchitect",
    "AgencySoldier",
    "MediaAgencyCalculator",
    "SEOAndMarTechAuditor",
    "MetaASCBlueprint",
    "GooglePMaxBlueprint",
    "GoogleDemandGenBlueprint",
    "CreativeHookSwapPackage",
    "AgencyOnboardingMilestone",
    "AgencySLAAndOnboardingChecklist",
    "EmailSMSFlow",
    "MediaFlightPlan",
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
    "SchemaOrgAuditResult",
    "CoreWebVitalsAuditResult",
    "IndexabilityAuditResult",
    "SemanticClusterAuditResult",
    "SecurityAndPrivacyAuditResult",
    "ECommerceCROScorecard",
    "SERPFeatureOpportunityAuditResult",
]
