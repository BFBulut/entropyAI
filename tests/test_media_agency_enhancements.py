"""
QA Sentinel Test Suite for Media Agency Enhancements:
1. MediaAgencyCalculator (Breakeven ROAS, Target ROAS, Max CPA, POAS, MER, Funnel Splits, Margin Simulations).
2. SEOAndMarTechAuditor (GA4, GTM, Meta CAPI, TikTok Pixel, Intent Scoring, Heading Hierarchy, Image SEO, Tools).
3. URLAnalyzer MarTech Integration & Backward Compatibility.
4. CampaignArchitect Unit Economics Blueprint.
5. web_media_audit CLI and Agency Engine Extensions.
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
    FunnelBudgetPlan,
    PromotionalMarginSimulation,
    FunnelHealthScorecard,
)
from skills.media_agency_soldier.seo_analyzer import (
    SEOAndMarTechAuditor,
    TrackingTagDetection,
    SearchIntentScore,
)
from skills.media_agency_soldier.url_analyzer import URLAnalyzer
from skills.media_agency_soldier.campaign_architect import CampaignArchitect
from entropy.skills.media_agency_soldier_engine import MediaAgencySoldierEngine


# =====================================================================
# 1. MEDIA AGENCY CALCULATOR TESTS
# =====================================================================

class TestMediaAgencyCalculator:
    """Test quantitative unit economics and percentage calculations."""

    def test_breakeven_roas_calculation(self):
        calc = MediaAgencyCalculator()
        # 50% margin -> 2.0x (200%)
        assert calc.calculate_breakeven_roas(50.0) == 2.0
        # 80% margin -> 1.25x
        assert calc.calculate_breakeven_roas(80.0) == 1.25
        # 60% margin -> 1.67x
        assert calc.calculate_breakeven_roas(60.0) == 1.67
        # 20% margin -> 5.0x
        assert calc.calculate_breakeven_roas(20.0) == 5.0
        # 0% or negative margin edge case
        assert calc.calculate_breakeven_roas(0.0) == 999.0
        assert calc.calculate_breakeven_roas(-10.0) == 999.0

    def test_target_roas_calculation(self):
        calc = MediaAgencyCalculator()
        # 60% gross margin, 15% net profit target -> 1 / (0.60 - 0.15) = 2.22x
        t_roas = calc.calculate_target_roas(60.0, 15.0)
        assert t_roas == 2.22

        # 50% gross margin, 10% net profit target -> 1 / (0.50 - 0.10) = 2.50x
        assert calc.calculate_target_roas(50.0, 10.0) == 2.50

        # High net profit target constraint
        assert calc.calculate_target_roas(50.0, 50.0) > 10.0

    def test_max_allowable_cpa_calculation(self):
        calc = MediaAgencyCalculator()
        # AOV ₺800, margin 65% (₺520), target net profit per order ₺120 -> max CPA = ₺400
        max_cpa = calc.calculate_max_allowable_cpa(aov=800.0, gross_margin_pct=65.0, target_profit_per_order=120.0)
        assert max_cpa == 400.0

        # Zero target profit: max CPA equals entire gross profit
        assert calc.calculate_max_allowable_cpa(aov=500.0, gross_margin_pct=50.0) == 250.0

    def test_poas_and_mer_metrics(self):
        calc = MediaAgencyCalculator()
        # POAS = Gross profit / Ad spend
        assert calc.calculate_poas(gross_profit=15000.0, ad_spend=10000.0) == 1.50
        assert calc.calculate_poas(gross_profit=5000.0, ad_spend=10000.0) == 0.50
        assert calc.calculate_poas(gross_profit=5000.0, ad_spend=0.0) == 0.0

        # MER = Total revenue / Total marketing spend
        assert calc.calculate_mer(total_revenue=500000.0, total_marketing_spend=100000.0) == 5.0
        assert calc.calculate_mer(total_revenue=100000.0, total_marketing_spend=0.0) == 0.0

    def test_funnel_budget_allocation_strategies(self):
        calc = MediaAgencyCalculator()
        total_budget = 100000.0

        # Balanced: 55% TOFU, 25% MOFU, 15% BOFU, 5% Retention
        plan_balanced = calc.calculate_funnel_budget_split(total_budget, strategy="balanced", currency="₺")
        assert plan_balanced.strategy == "balanced"
        assert len(plan_balanced.tiers) == 4
        pcts = {t.stage: t.allocation_pct for t in plan_balanced.tiers}
        amts = {t.stage: t.amount for t in plan_balanced.tiers}

        assert pcts["TOFU"] == 55.0
        assert pcts["MOFU"] == 25.0
        assert pcts["BOFU"] == 15.0
        assert pcts["RETENTION"] == 5.0
        assert sum(amts.values()) == total_budget

        # Scale strategy: 70% TOFU
        plan_scale = calc.calculate_funnel_budget_split(total_budget, strategy="scale")
        pcts_scale = {t.stage: t.allocation_pct for t in plan_scale.tiers}
        assert pcts_scale["TOFU"] == 70.0
        assert pcts_scale["BOFU"] == 10.0

        # Harvest strategy: 35% TOFU, 25% BOFU
        plan_harvest = calc.calculate_funnel_budget_split(total_budget, strategy="harvest")
        pcts_harvest = {t.stage: t.allocation_pct for t in plan_harvest.tiers}
        assert pcts_harvest["TOFU"] == 35.0
        assert pcts_harvest["BOFU"] == 25.0

    def test_bogo_promotional_margin_simulation(self):
        calc = MediaAgencyCalculator()
        # Safe BOGO: High-ticket Hero (₺1200, cogs ₺360) + Free Low-cost Gift (₺250, cogs ₺35) + Shipping ₺40
        sim_safe = calc.simulate_bogo_margin(
            hero_price=1200.0,
            hero_cogs=360.0,
            gift_price=250.0,
            gift_cogs=35.0,
            shipping_cost=40.0
        )
        assert sim_safe.margin_protected is True
        assert sim_safe.net_gross_margin_pct > 60.0
        assert "UYGUN" in sim_safe.verdict

        # Dangerous BOGO: ₺500 Hero (cogs ₺350) + ₺500 Gift (cogs ₺350)
        sim_risky = calc.simulate_bogo_margin(
            hero_price=500.0,
            hero_cogs=350.0,
            gift_price=500.0,
            gift_cogs=350.0
        )
        assert sim_risky.margin_protected is False
        assert sim_risky.net_gross_profit < 0
        assert "RİSKLİ" in sim_risky.verdict

    def test_bundle_discount_simulation(self):
        calc = MediaAgencyCalculator()
        sim_bundle = calc.simulate_bundle_discount(
            hero_price=1000.0,
            complementary_price=400.0,
            discount_pct=10.0,
            cogs_pct=35.0
        )
        assert sim_bundle.margin_protected is True
        assert sim_bundle.promotional_revenue == 1000.0 + (400.0 * 0.9)
        assert sim_bundle.net_gross_margin_pct >= 60.0

    def test_cart_thresholds_simulation(self):
        calc = MediaAgencyCalculator()
        thresh = calc.simulate_cart_thresholds(current_aov=450.0, currency="₺")
        t1 = thresh["tier_1_free_shipping"]["threshold_amount"]
        t2 = thresh["tier_2_tiered_gift"]["threshold_amount"]

        assert t1 > 450.0
        assert t2 > t1
        assert "kargo" in thresh["tier_1_free_shipping"]["rationale"].lower()

    def test_conversion_funnel_health_diagnostics(self):
        calc = MediaAgencyCalculator()
        # Healthy funnel
        health = calc.analyze_conversion_funnel(
            impressions=100000,
            clicks=2500,       # CTR = 2.5%
            ad_spend=5000.0,    # CPC = 2.0
            add_to_carts=250,   # ATC = 10%
            checkouts=150,
            orders=75,          # CVR = 3.0%, Abandonment = 50%
            revenue=22500.0,    # ROAS = 4.5x, AOV = 300
            cogs=9000.0
        )
        assert health.ctr_pct == 2.5
        assert health.cpc == 2.0
        assert health.roas == 4.5
        assert health.poas > 1.0
        assert health.leading_indicators_healthy is True
        assert health.creative_fatigue_alert is False

        # Degraded funnel with creative fatigue and checkout friction
        degraded = calc.analyze_conversion_funnel(
            impressions=100000,
            clicks=800,        # CTR = 0.8% (low)
            ad_spend=4000.0,
            add_to_carts=30,   # ATC = 3.75% (low)
            checkouts=25,
            orders=3,          # Abandonment = 88% (high)
            revenue=900.0,     # ROAS = 0.225x (critical)
            cogs=400.0
        )
        assert degraded.ctr_pct == 0.8
        assert degraded.leading_indicators_healthy is False
        assert degraded.creative_fatigue_alert is True
        assert degraded.checkout_abandonment_rate_pct > 80.0


# =====================================================================
# 2. SEO AND MARTECH AUDITOR TESTS
# =====================================================================

class TestSEOAndMarTechAuditor:
    """Test deep SEO, MarTech tag sniffing, search intents, and agency tool matching."""

    @pytest.fixture
    def tracked_store_html(self) -> str:
        return """<!DOCTYPE html>
        <html>
        <head>
            <title>NovaStep Deri Ayakkabı - Resmi Satış Mağazası</title>
            <meta name="description" content="NovaStep resmi mağazasında hakiki deri ayakkabıları indirimli fiyatlarla hemen satın al.">
            <link rel="canonical" href="https://novastep.com.tr" />
            <!-- GA4 Tag -->
            <script async src="https://www.googletagmanager.com/gtag/js?id=G-ABCD1234EF"></script>
            <script>
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', 'G-ABCD1234EF');
            </script>
            <!-- GTM Tag -->
            <script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer','GTM-XYZ7890');</script>
            <!-- Meta Pixel -->
            <script>
                !function(f,b,e,v,n,t,s)
                {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
                n.callMethod.apply(n,arguments):n.queue.push(arguments)};
                if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
                n.queue=[];t=b.createElement(e);t.async=!0;
                t.src=v;s=b.getElementsByTagName(e)[0];
                s.parentNode.insertBefore(t,s)}(window, document,'script',
                'https://connect.facebook.net/en_US/fbevents.js');
                fbq('init', '123456789012345');
                fbq('track', 'PageView');
            </script>
        </head>
        <body>
            <h1>NovaStep 2026 Koleksiyonu</h1>
            <h2>Erkek Ayakkabıları</h2>
            <h3>Klasik Modeller</h3>
            <img src="/img/1.webp" alt="Hakiki Deri Klasik Ayakkabı" />
            <img src="/img/2.avif" alt="Deri Detay" />
            <a href="/urunler">Tüm Ürünleri İncele</a>
            <a href="https://instagram.com/novastep">Sosyal Medya</a>
        </body>
        </html>"""

    def test_martech_tag_detection(self, tracked_store_html):
        auditor = SEOAndMarTechAuditor()
        res = auditor.detect_tracking_tags(tracked_store_html)

        assert res["total_checked"] >= 5
        assert res["detected_count"] >= 3
        assert res["ready_for_paid_traffic"] is True

        tag_names = [t["tag_name"] for t in res["tags"] if t["detected"]]
        assert any("GA4" in n for n in tag_names)
        assert any("GTM" in n for n in tag_names)
        assert any("Meta Pixel" in n for n in tag_names)

        # Check tag IDs
        ga4 = next(t for t in res["tags"] if "GA4" in t["tag_name"])
        assert ga4["tag_id"] == "G-ABCD1234EF"
        meta = next(t for t in res["tags"] if "Meta Pixel" in t["tag_name"])
        assert meta["tag_id"] == "123456789012345"

    def test_missing_martech_tags_alert(self):
        plain_html = "<html><head><title>No Tracking</title></head><body><h1>Hello</h1></body></html>"
        auditor = SEOAndMarTechAuditor()
        res = auditor.detect_tracking_tags(plain_html)

        assert res["detected_count"] == 0
        assert res["ready_for_paid_traffic"] is False
        assert len(res["critical_missing_p0"]) >= 2
        assert any("GA4" in m for m in res["critical_missing_p0"])
        assert any("Meta" in m for m in res["critical_missing_p0"])

    def test_search_intent_scoring(self):
        auditor = SEOAndMarTechAuditor()

        # Transactional intent page
        trans_html = """<html><body>
            <h1>Deri Ceket Satın Al - Kampanyalı Fiyatlar</h1>
            <p>Hemen sipariş verin, sepette anında %20 indirim fırsatını ve ücretsiz kargo avantajını yakalayın.</p>
        </body></html>"""
        intent_trans = auditor.analyze_search_intents(trans_html, title="Satın Al", meta_desc="İndirimli fiyat")
        assert intent_trans.dominant_intent == "Transactional"
        assert "Ürün" in intent_trans.recommended_page_role or "Satın Alma" in intent_trans.recommended_page_role

        # Informational intent page
        info_html = """<html><body>
            <h1>Hakiki Deri Bakımı Nasıl Yapılır? Kapsamlı Rehber</h1>
            <p>Deri ayakkabı temizliğinin püf noktaları, ipuçları ve evde bakım rehberi.</p>
        </body></html>"""
        intent_info = auditor.analyze_search_intents(info_html, title="Rehber", meta_desc="Nasıl yapılır")
        assert intent_info.dominant_intent == "Informational"
        assert "Blog" in intent_info.recommended_page_role or "Rehber" in intent_info.recommended_page_role

    def test_heading_hierarchy_analysis(self):
        auditor = SEOAndMarTechAuditor()

        # Optimal single H1
        ok_html = "<html><body><h1>Ana Başlık</h1><h2>Alt 1</h2><h3>Detay 1</h3></body></html>"
        h_ok = auditor.analyze_heading_hierarchy(ok_html)
        assert h_ok["h1_status"] == "optimal"
        assert h_ok["h1_count"] == 1
        assert h_ok["is_hierarchy_healthy"] is True

        # Multiple H1 violation
        multi_html = "<html><body><h1>Başlık 1</h1><h1>Başlık 2</h1></body></html>"
        h_multi = auditor.analyze_heading_hierarchy(multi_html)
        assert h_multi["h1_status"] == "multiple"
        assert h_multi["is_hierarchy_healthy"] is False
        assert len(h_multi["violations"]) > 0

    def test_image_seo_and_alt_audit(self):
        auditor = SEOAndMarTechAuditor()
        html = """<html><body>
            <img src="/assets/hero.webp" alt="Hero Çanta" />
            <img src="/assets/detail.avif" alt="Detay Görünüm" />
            <img src="/assets/no-alt.jpg" />
        </body></html>"""
        img_res = auditor.analyze_image_seo(html)
        assert img_res["total_images"] == 3
        assert img_res["missing_alt_count"] == 1
        assert img_res["modern_formats_count"] == 2
        assert img_res["modern_format_ratio"] > 0.65

    def test_agency_tool_recommendations(self):
        auditor = SEOAndMarTechAuditor()
        tools = auditor.get_recommended_agency_tools(gaps=["Kritik LCP gecikmesi", "Reklam kopyaları eksik"])
        tool_names = [t["name"] for t in tools]

        assert any("Screaming Frog" in t for t in tool_names)
        assert any("Ahrefs" in t for t in tool_names)
        assert any("PageSpeed" in t for t in tool_names)
        assert any("Meta Ad Library" in t for t in tool_names)


# =====================================================================
# 3. END-TO-END URLANALYZER & CAMPAIGN ARCHITECT INTEGRATION
# =====================================================================

class TestURLAnalyzerAndCampaignIntegration:
    """Test that URLAnalyzer and CampaignArchitect seamlessly expose new enhancements."""

    def test_url_analyzer_exposes_martech_and_agency_tools(self, tmp_path):
        html = """<!DOCTYPE html>
        <html>
        <head>
            <title>Lüks Deri Mağazası</title>
            <meta name="description" content="En iyi el yapımı deri cüzdan modelleri.">
            <script src="https://www.googletagmanager.com/gtag/js?id=G-TEST123456"></script>
        </head>
        <body>
            <h1>El Yapımı Deri Ürünler</h1>
            <div class="product">
                <h3>Cüzdan</h3>
                <span class="price">₺450.00</span>
            </div>
        </body></html>"""

        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(html, url="https://deri.local")

        assert "martech_tracking" in res
        assert "agency_tool_recommendations" in res
        assert len(res["agency_tool_recommendations"]) >= 2
        assert res["martech_tracking"]["detected_count"] >= 1

    def test_campaign_architect_generates_unit_economics_plan(self):
        architect = CampaignArchitect()
        mock_analysis = {
            "brand_info": {"brand_name": "NovaStep"},
            "product_catalog": {
                "products": [
                    {"name": "Deri Ayakkabı", "price": 1200.0},
                    {"name": "Bakım Kremi", "price": 200.0}
                ],
                "average_price": 700.0,
                "currencies": ["₺"]
            }
        }

        full_pkg = architect.generate_full_package(mock_analysis)
        assert "unit_economics" in full_pkg
        unit = full_pkg["unit_economics"]

        assert unit["breakeven_roas"] == 1.82
        assert unit["target_roas"] == 2.50
        assert unit["max_allowable_cpa"] > 0
        assert "balanced" in unit["funnel_budget_allocations"]
        assert "scale" in unit["funnel_budget_allocations"]
        assert "bogo_simulation" in unit["promotional_simulations"]


# =====================================================================
# 4. MEDIA AGENCY SOLDIER ENGINE TESTS
# =====================================================================

class TestMediaAgencySoldierEngineEnhancements:
    """Test engine methods calculate_unit_economics and run_deep_seo_audit."""

    def test_engine_unit_economics_call(self):
        engine = MediaAgencySoldierEngine()
        mock_analysis = {
            "brand_info": {"brand_name": "TestMarka"},
            "product_catalog": {
                "products": [{"name": "Ürün 1", "price": 500.0}],
                "average_price": 500.0,
                "currencies": ["₺"]
            }
        }

        econ = engine.calculate_unit_economics(mock_analysis, monthly_budget=50000.0)
        assert "breakeven_roas" in econ
        assert "funnel_budget_allocations" in econ
        assert econ["funnel_budget_allocations"]["balanced"]["total_budget"] == 50000.0

    def test_engine_deep_seo_audit_call(self):
        engine = MediaAgencySoldierEngine()
        html = "<html><head><title>Test</title></head><body><h1>Başlık</h1></body></html>"
        seo_res = engine.run_deep_seo_audit(html, url="https://test.com")

        assert "martech_tracking" in seo_res
        assert "search_intent_analysis" in seo_res
        assert "recommended_agency_tools" in seo_res


# =====================================================================
# 5. CLI TEST FOR WEB_MEDIA_AUDIT
# =====================================================================

class TestWebMediaAuditCLI:
    """Test web_media_audit.py end-to-end execution and JSON export."""

    def test_web_media_audit_json_export(self, tmp_path):
        from skills.media_agency_soldier.web_media_audit import generate_audit

        out_json = tmp_path / "web_audit.json"
        audit = generate_audit(
            url="https://novastep.com.tr",
            brand="NovaStep",
            monthly_budget=150000.0
        )

        assert audit["brand_name"] == "NovaStep"
        assert len(audit["audit_categories"]) >= 5
        assert audit["unit_economics"]["breakeven_roas"] > 1.0
        assert "tofu" in audit["recommended_funnel"]
        assert len(audit["agency_tool_stack"]) >= 2
