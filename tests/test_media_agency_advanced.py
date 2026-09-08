"""
QA Test Suite for Advanced Media Agency Soldier Enhancements:
1. Quantitative Media Economics:
   - LTV & CAC Payback Period across all health tiers (DANGER, FRAGILE, OPTIMAL, UNDERINVESTING).
   - 3-Tier Contribution Margins (CM1, CM2, CM3) and unit profitability verdicts.
   - nCAC vs Blended CAC and Brand Cannibalization detection.
   - 3:2:2 Dynamic Creative Testing Budget and sample size modeling.
   - RFM Customer Base Segmentation and channel allocation.
2. Technical & Semantic SEO:
   - Schema.org JSON-LD parsing (Product, Offers, Org, Breadcrumbs, FAQ).
   - Core Web Vitals DOM diagnostics (LCP blocking scripts, CLS image dimensions, INP).
   - Indexability, meta robots (noindex/nofollow), canonical and OpenGraph validation.
   - Semantic Topic Clusters & N-gram density analysis.
3. Multi-Channel Performance Blueprints:
   - Meta Advantage+ Shopping Campaigns (ASC) specification.
   - Google Performance Max (PMax) Asset Group and audience signals.
   - Klaviyo / Omnisend Retention Flows (Welcome, Abandoned Cart/SMS, VIP, Win-back).
   - 30-60-90 Day Media Flight Plan & Pacing Matrix.
4. End-to-End 360 Web Media Audit CLI & Engine.
"""

import sys
import json
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "media-agency-soldier"
SRC_DIR = REPO_ROOT / "src"

for p in [str(REPO_ROOT), str(SKILL_DIR), str(SRC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from skills.media_agency_soldier.media_calculator import (
    MediaAgencyCalculator,
    LTVPaybackScorecard,
    ContributionMarginAnalysis,
    NCACAnalysis,
    CreativeTestingBudgetEstimate,
    RFMSegmentResult,
)
from skills.media_agency_soldier.seo_analyzer import (
    SEOAndMarTechAuditor,
    SchemaOrgAuditResult,
    CoreWebVitalsAuditResult,
    IndexabilityAuditResult,
    SemanticClusterAuditResult,
)
from skills.media_agency_soldier.campaign_architect import (
    CampaignArchitect,
    MetaASCBlueprint,
    GooglePMaxBlueprint,
    EmailSMSFlow,
    MediaFlightPlan,
)
from skills.media_agency_soldier.web_media_audit import generate_audit


# =====================================================================
# 1. ADVANCED MEDIA ECONOMICS TESTS
# =====================================================================

class TestAdvancedMediaEconomics:
    """Test LTV, Payback, CM1-3, nCAC, 3:2:2 test budget, and RFM."""

    def test_ltv_and_payback_optimal_tier(self):
        calc = MediaAgencyCalculator()
        # AOV = ₺1,000, 3 orders/yr, 60% gross margin, 30% annual churn, CAC = ₺1,500
        # LTV = (1000 * 3 * 0.60) / 0.30 = 1800 / 0.30 = ₺6,000
        # LTV:CAC = 6000 / 1500 = 4.0x (OPTIMAL)
        card = calc.calculate_ltv_and_payback(
            aov=1000.0,
            purchase_frequency_annual=3.0,
            gross_margin_pct=60.0,
            annual_churn_rate_pct=30.0,
            cac=1500.0
        )
        assert card.ltv == 6000.0
        assert card.ltv_to_cac_ratio == 4.0
        assert card.health_status == "OPTIMAL"
        assert "ALTIN DENGE" in card.strategic_recommendation
        assert card.payback_period_months == 10.0

    def test_ltv_and_payback_danger_tier(self):
        calc = MediaAgencyCalculator()
        # High churn, low margin, expensive CAC
        card = calc.calculate_ltv_and_payback(
            aov=500.0,
            purchase_frequency_annual=1.2,
            gross_margin_pct=30.0,
            annual_churn_rate_pct=70.0,
            cac=400.0
        )
        assert card.ltv < card.cac
        assert card.ltv_to_cac_ratio < 1.0
        assert card.health_status == "DANGER"
        assert "ÖLÜMCÜL" in card.strategic_recommendation

    def test_ltv_and_payback_underinvesting_tier(self):
        calc = MediaAgencyCalculator()
        # Very low CAC, high LTV -> ratio > 5.0
        card = calc.calculate_ltv_and_payback(
            aov=1200.0,
            purchase_frequency_annual=4.0,
            gross_margin_pct=70.0,
            annual_churn_rate_pct=25.0,
            cac=200.0
        )
        assert card.ltv_to_cac_ratio > 5.0
        assert card.health_status == "UNDERINVESTING"

    def test_contribution_margins_healthy(self):
        calc = MediaAgencyCalculator()
        # Revenue: 1000, COGS: 400, Logistics: 60, Gateway: 25, Ad Spend: 200
        # CM1 = 600 (%60.0)
        # CM2 = 600 - 85 = 515 (%51.5)
        # CM3 = 515 - 200 = 315 (%31.5) -> Healthy (>= 15%)
        cm = calc.calculate_contribution_margins(
            revenue=1000.0,
            cogs=400.0,
            logistics_and_shipping=60.0,
            payment_gateway_fee=25.0,
            ad_spend=200.0
        )
        assert cm.cm1_gross_profit == 600.0
        assert cm.cm1_pct == 60.0
        assert cm.cm2_operational_profit == 515.0
        assert cm.cm2_pct == 51.5
        assert cm.cm3_contribution_profit == 315.0
        assert cm.cm3_pct == 31.5
        assert cm.is_unit_profitable is True
        assert "SAĞLIKLI" in cm.verdict

    def test_contribution_margins_unprofitable(self):
        calc = MediaAgencyCalculator()
        # CM3 goes negative
        cm = calc.calculate_contribution_margins(
            revenue=500.0,
            cogs=300.0,
            logistics_and_shipping=80.0,
            payment_gateway_fee=20.0,
            ad_spend=250.0
        )
        assert cm.cm3_contribution_profit == -150.0
        assert cm.is_unit_profitable is False
        assert "KRİTİK ZARAR" in cm.verdict

    def test_ncac_and_cannibalization_detection(self):
        calc = MediaAgencyCalculator()
        # Normal acquisition: 100K spend, 1000 total orders, 800 new customers
        # blended = 100, ncac = 125 (125 < 160)
        ncac_norm = calc.calculate_ncac(
            total_ad_spend=100000.0,
            total_orders=1000,
            new_customers=800
        )
        assert ncac_norm.blended_cac == 100.0
        assert ncac_norm.ncac == 125.0
        assert ncac_norm.organic_cannibalization_risk is False

        # Cannibalization: 100K spend, 1000 total orders, only 200 new customers
        # blended = 100, ncac = 500 (500 > 160)
        ncac_cann = calc.calculate_ncac(
            total_ad_spend=100000.0,
            total_orders=1000,
            new_customers=200
        )
        assert ncac_cann.ncac == 500.0
        assert ncac_cann.organic_cannibalization_risk is True
        assert "YÜKSEK YAMYAMLIK" in ncac_cann.channel_efficiency_rating

    def test_creative_testing_budget_estimator(self):
        calc = MediaAgencyCalculator()
        est = calc.calculate_creative_testing_budget(
            cpm=50.0,
            expected_ctr_pct=2.0,
            expected_cvr_pct=2.5,
            target_conversions_per_variant=25,
            variant_count=7
        )
        assert est.required_clicks_per_variant == 1000
        assert est.required_impressions_per_variant == 50000
        assert est.spend_per_variant == 2500.0
        assert est.total_testing_budget_needed == 17500.0
        assert est.testing_duration_days == 7
        assert est.recommended_daily_budget == 2500.0

    def test_rfm_customer_segmentation(self):
        calc = MediaAgencyCalculator()
        segments = calc.segment_rfm_customers(total_customer_count=5000)
        assert len(segments) == 5
        names = [s.segment_name for s in segments]
        assert any("Champions" in n for n in names)
        assert any("Loyal" in n for n in names)
        assert any("At Risk" in n for n in names)
        total_pct = sum(s.percentage_of_base for s in segments)
        assert 99.0 <= total_pct <= 101.0


# =====================================================================
# 2. TECHNICAL & SEMANTIC SEO AUDIT TESTS
# =====================================================================

class TestAdvancedTechnicalSEO:
    """Test Schema.org, Core Web Vitals DOM, Indexability, and Topic Clusters."""

    def test_schema_org_valid_product(self):
        auditor = SEOAndMarTechAuditor()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "NovaStep Pro Sneaker",
                "image": "https://novastep.com.tr/img/p1.jpg",
                "offers": {
                    "@type": "Offer",
                    "price": "1899.00",
                    "priceCurrency": "TRY",
                    "availability": "https://schema.org/InStock"
                }
            }
            </script>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "NovaStep A.Ş.",
                "url": "https://novastep.com.tr"
            }
            </script>
        </head>
        <body><h1>Ürün</h1></body>
        </html>
        """
        res = auditor.audit_schema_org(html)
        assert res.has_json_ld is True
        assert res.valid_product_schema is True
        assert res.valid_organization_schema is True
        assert "Product" in res.schema_types_detected
        assert "Organization" in res.schema_types_detected
        assert res.schema_health_score >= 70

    def test_schema_org_missing_fields(self):
        auditor = SEOAndMarTechAuditor()
        html = """
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Eksik Ürün"
        }
        </script>
        """
        res = auditor.audit_schema_org(html)
        assert res.valid_product_schema is False
        assert any("image" in f for f in res.missing_product_fields)
        assert any("offers" in f for f in res.missing_product_fields)

    def test_core_web_vitals_dom_diagnostics(self):
        auditor = SEOAndMarTechAuditor()
        bad_html = """
        <html>
        <head>
            <script src="/js/heavy-1.js"></script>
            <script src="/js/heavy-2.js"></script>
            <script src="/js/heavy-3.js"></script>
            <link rel="stylesheet" href="/css/style1.css">
            <link rel="stylesheet" href="/css/style2.css">
            <link rel="stylesheet" href="/css/style3.css">
            <link rel="stylesheet" href="/css/style4.css">
            <link rel="stylesheet" href="/css/style5.css">
        </head>
        <body>
            <img src="/img/no-dimensions.jpg">
            <img src="/img/no-lazy.jpg">
        </body>
        </html>
        """
        bad_res = auditor.audit_core_web_vitals_dom(bad_html)
        assert bad_res.viewport_tag_found is False
        assert bad_res.render_blocking_scripts_count >= 3
        assert bad_res.missing_dimensions_img_count >= 2
        assert bad_res.cwv_score < 70
        assert bad_res.lcp_risk in ("Needs Improvement", "Poor")

        good_html = """
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <script defer src="/js/app.js"></script>
            <link rel="stylesheet" href="/css/app.css">
        </head>
        <body>
            <img src="/img/hero.webp" width="800" height="600" loading="lazy">
        </body>
        </html>
        """
        good_res = auditor.audit_core_web_vitals_dom(good_html)
        assert good_res.viewport_tag_found is True
        assert good_res.render_blocking_scripts_count == 0
        assert good_res.cwv_score >= 80

    def test_indexability_and_social_metadata(self):
        auditor = SEOAndMarTechAuditor()
        html = """
        <html>
        <head>
            <meta name="robots" content="index, follow">
            <link rel="canonical" href="https://novastep.com.tr/urunler">
            <meta property="og:title" content="NovaStep Koleksiyon">
            <meta property="og:image" content="https://novastep.com.tr/og.jpg">
            <meta property="og:description" content="En iyi modeller">
            <meta name="twitter:card" content="summary_large_image">
            <link rel="alternate" hreflang="tr" href="https://novastep.com.tr/">
        </head>
        <body><h1>Koleksiyon</h1></body>
        </html>
        """
        res = auditor.audit_indexability(html, url="https://novastep.com.tr/urunler")
        assert res.is_indexable is True
        assert res.noindex_detected is False
        assert res.canonical_status == "Valid Self-Referencing"
        assert res.has_og_title is True
        assert res.has_og_image is True
        assert res.has_twitter_card is True
        assert "tr" in res.hreflang_languages

    def test_semantic_topic_clusters(self):
        auditor = SEOAndMarTechAuditor()
        html = """
        <html>
        <body>
            <p>Deri ayakkabı modelleri günümüzde şıklık ve konfor arayanlar için deri ayakkabı kalitesini yansıtır.</p>
            <p>Hakiki deri ayakkabı bakımı yapıldığında uzun yıllar dayanır. Deri ayakkabı temizliği önemlidir.</p>
        </body>
        </html>
        """
        res = auditor.audit_semantic_clusters(html)
        assert res.total_words > 10
        assert "unigrams" in res.top_ngrams
        assert "Pillar" in res.recommended_pillar_concept
        assert len(res.proposed_cluster_articles) == 3


# =====================================================================
# 3. CAMPAIGN ARCHITECT BLUEPRINTS & FLIGHT PLAN TESTS
# =====================================================================

class TestCampaignArchitectAdvanced:
    """Test Meta ASC, Google PMax, Retention Flows, and 30-60-90 Flight Plan."""

    @pytest.fixture
    def mock_analysis(self):
        return {
            "brand_info": {
                "brand_name": "NovaStep",
                "domain": "novastep.com.tr"
            },
            "products": [
                {"name": "NovaStep Pro Sneaker", "price": 1899.0},
                {"name": "Deri Temizleme Köpüğü", "price": 249.0}
            ]
        }

    def test_meta_asc_blueprint_generation(self, mock_analysis):
        architect = CampaignArchitect()
        asc = architect.generate_meta_asc_blueprint(mock_analysis, monthly_meta_budget=60000.0)
        assert "[ASC]" in asc.campaign_name
        assert asc.allocated_monthly_budget == 60000.0
        assert asc.existing_customer_budget_cap_pct == 5.0
        assert len(asc.creative_mix) == 4
        assert len(asc.suggested_ad_angles) >= 3

    def test_google_pmax_blueprint_generation(self, mock_analysis):
        architect = CampaignArchitect()
        pmax = architect.generate_google_pmax_blueprint(mock_analysis, monthly_google_budget=40000.0)
        assert "[PMAX]" in pmax.campaign_name
        assert pmax.allocated_monthly_budget == 40000.0
        assert len(pmax.short_headlines) >= 5
        assert len(pmax.long_headlines) >= 3
        assert len(pmax.descriptions) >= 3
        assert len(pmax.search_themes) >= 3
        assert "first_party" in pmax.audience_signals
        assert pmax.brand_exclusion_applied is True

    def test_retention_flows_generation(self, mock_analysis):
        architect = CampaignArchitect()
        flows = architect.generate_retention_flows(mock_analysis["brand_info"])
        assert len(flows) == 4
        names = [f.flow_name for f in flows]
        assert any("Welcome" in n or "Hoş Geldin" in n for n in names)
        assert any("Abandoned" in n or "Terk Edilen" in n for n in names)
        assert any("Post-Purchase" in n or "VIP" in n for n in names)
        assert any("Win-Back" in n or "Geri Kazanım" in n for n in names)
        # Check SMS inclusion
        has_sms = any(any(s.get("channel") == "SMS" for s in f.steps) for f in flows)
        assert has_sms is True

    def test_30_60_90_flight_plan(self, mock_analysis):
        architect = CampaignArchitect()
        plan = architect.generate_30_60_90_flight_plan(monthly_budget=100000.0, analysis=mock_analysis)
        assert plan.monthly_budget == 100000.0
        assert plan.total_90_day_budget == 300000.0
        assert "1-30 Gün" in plan.phase_1_days_1_30["name"]
        assert "31-60 Gün" in plan.phase_2_days_31_60["name"]
        assert "61-90 Gün" in plan.phase_3_days_61_90["name"]
        assert "day_30_target" in plan.kpi_milestones

    def test_generate_full_package_integration(self, mock_analysis):
        architect = CampaignArchitect()
        pkg = architect.generate_full_package(mock_analysis, monthly_budget=80000.0)
        assert pkg["brand"] == "NovaStep"
        assert "meta_asc_blueprint" in pkg
        assert "google_pmax_blueprint" in pkg
        assert "retention_flows" in pkg
        assert "media_flight_plan" in pkg


# =====================================================================
# 4. END-TO-END 360 WEB MEDIA AUDIT ENGINE TEST
# =====================================================================

class TestWebMediaAuditEndToEnd:
    """Test full 360 audit CLI engine with synthetic and offline HTML."""

    def test_generate_audit_synthetic(self):
        audit = generate_audit(
            url="https://novastep.com.tr",
            brand="NovaStep",
            monthly_budget=120000.0
        )
        assert audit["brand_name"] == "NovaStep"
        assert audit["domain"] == "novastep.com.tr"
        assert len(audit["audit_categories"]) >= 7

        # Verify advanced modules presence
        assert "advanced_economics" in audit
        assert "ltv_payback" in audit["advanced_economics"]
        assert "contribution_margins" in audit["advanced_economics"]

        assert "technical_seo_deep_audit" in audit
        assert "schema_org" in audit["technical_seo_deep_audit"]
        assert "core_web_vitals" in audit["technical_seo_deep_audit"]

        assert "campaign_architecture" in audit
        assert "meta_asc_blueprint" in audit["campaign_architecture"]
        assert "google_pmax_blueprint" in audit["campaign_architecture"]
        assert "media_flight_plan" in audit["campaign_architecture"]

    def test_generate_audit_offline_html(self, tmp_path):
        sample_html = """<!DOCTYPE html>
        <html>
        <head>
            <title>NovaStep - Hakiki Deri Ayakkabı</title>
            <meta name="description" content="En şık deri ayakkabılar NovaStep'te.">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="canonical" href="https://novastep.com.tr">
            <!-- GA4 -->
            <script async src="https://www.googletagmanager.com/gtag/js?id=G-ABCDE12345"></script>
            <!-- Schema.org -->
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "NovaStep Sneaker",
                "image": "https://novastep.com.tr/img.jpg",
                "offers": {
                    "@type": "Offer",
                    "price": "1499.00",
                    "priceCurrency": "TRY",
                    "availability": "https://schema.org/InStock"
                }
            }
            </script>
        </head>
        <body>
            <h1>NovaStep Deri Ayakkabı</h1>
            <p>El yapımı ayakkabılar ve aksesuarlar.</p>
        </body>
        </html>"""

        html_file = tmp_path / "sample.html"
        html_file.write_text(sample_html, encoding="utf-8")

        audit = generate_audit(
            url="https://novastep.com.tr",
            brand="NovaStep",
            offline_html=str(html_file),
            monthly_budget=50000.0
        )

        assert audit["brand_name"] == "NovaStep"
        cats = {c["category"]: c for c in audit["audit_categories"]}
        # GA4 was present in HTML
        assert "MarTech & Takip Kodları (GA4 / CAPI)" in cats
        # Schema.org was present and valid
        assert "Schema.org & Yapılandırılmış Veri" in cats
        assert cats["Schema.org & Yapılandırılmış Veri"]["status"] == "Hazır"
