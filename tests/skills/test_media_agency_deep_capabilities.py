"""Automated test suite for Media Agency Soldier deep capabilities.

Validates:
- Unit economics: Discount break-even, POAS net profit, MER & attribution overlap,
  A/B test significance (Z-test), budget pacing & run-rate.
- Campaign architecture: Google Demand Gen blueprints, Creative Hook-Swap variations,
  Agency onboarding 30-day roadmap & fail-closed SLAs.
- Technical & martech audit: Security/Privacy (CSP, HSTS, Consent Mode v2),
  E-commerce CRO scorecard (friction index), SERP feature opportunities.
- Core engine bridge exposure and end-to-end audit completeness.
"""

import pytest
from skills.media_agency_soldier.media_calculator import (
    MediaAgencyCalculator,
    DiscountBreakEvenSimulation,
    POASNetProfitSimulation,
    MarketingEfficiencyRatioAnalysis,
    ABTestSignificanceAnalysis,
    BudgetPacingAndRunRateAnalysis,
)
from skills.media_agency_soldier.campaign_architect import (
    CampaignArchitect,
    GoogleDemandGenBlueprint,
    CreativeHookSwapPackage,
    AgencySLAAndOnboardingChecklist,
)
from skills.media_agency_soldier.seo_analyzer import (
    SEOAndMarTechAuditor,
    SecurityAndPrivacyAuditResult,
    ECommerceCROScorecard,
    SERPFeatureOpportunityAuditResult,
)
from skills.media_agency_soldier.web_media_audit import generate_audit
from entropy.skills.media_agency_soldier_engine import MediaAgencySoldierEngine


# ==============================================================================
# 1. Advanced Unit Economics & Statistics Tests
# ==============================================================================

def test_discount_breakeven_simulation():
    """Verify price elasticity & required volume uplift: d / (margin - d)."""
    # 20% discount on a 60% gross margin product -> requires 0.20 / (0.60 - 0.20) = 50% uplift
    sim = MediaAgencyCalculator.simulate_discount_breakeven(
        gross_margin_pct=60.0,
        discount_pct=20.0,
        current_orders=1000,
        current_aov=200.0,
    )
    assert isinstance(sim, DiscountBreakEvenSimulation)
    assert sim.required_volume_increase_pct == 50.0
    assert sim.break_even_order_count == 1500
    assert sim.original_gross_profit == 120000.0
    assert sim.discounted_aov == 160.0
    assert sim.margin_preserved is True
    assert "sipari" in sim.verdict.lower() or "artmal" in sim.verdict.lower()

    # Fatal discount exceeding margin: 35% discount with 30% margin
    fatal_sim = MediaAgencyCalculator.simulate_discount_breakeven(
        gross_margin_pct=30.0,
        discount_pct=35.0,
        current_orders=100,
        current_aov=100.0,
    )
    assert fatal_sim.margin_preserved is False
    assert "ölümcül" in fatal_sim.verdict.lower() or "olumcul" in fatal_sim.verdict.lower() or "zarar" in fatal_sim.verdict.lower()


def test_poas_net_profit_simulation():
    """Verify true profit on ad spend accounting for returns, payment gateway, and shipping."""
    poas = MediaAgencyCalculator.calculate_poas_net_profit(
        gross_revenue=100000.0,
        ad_spend=25000.0,
        cogs=40000.0,
        logistics_and_shipping=4000.0,
        payment_gateway_rate_pct=2.5,
        return_refund_rate_pct=10.0,
        packaging_and_handling=0.0,
    )
    assert isinstance(poas, POASNetProfitSimulation)
    assert poas.blended_roas == 4.0
    assert poas.net_revenue == 90000.0
    assert poas.payment_gateway_fee == 2500.0
    assert poas.net_operational_profit > 0
    assert poas.net_profit_after_ads > 0
    assert poas.poas > 1.0
    assert poas.is_profitable is True


def test_mer_and_attribution_overlap():
    """Verify blended MER and cross-channel double-counting detection."""
    mer_data = MediaAgencyCalculator.calculate_mer_and_attribution(
        total_net_revenue=250000.0,
        total_ad_spend=50000.0,
        channel_reported_revenues={"meta_ads": 160000.0, "google_ads": 140000.0},
    )
    assert isinstance(mer_data, MarketingEfficiencyRatioAnalysis)
    assert mer_data.blended_mer == 5.0
    assert mer_data.sum_reported_revenue == 300000.0
    # Overlap factor = 300,000 / 250,000 = 1.20 (20% overreporting)
    assert mer_data.attribution_overlap_factor == 1.20
    assert mer_data.overreporting_pct == 20.0
    assert mer_data.efficiency_tier == "SCALE_AGGRESSIVELY"


def test_ab_test_significance_analysis():
    """Verify two-proportion two-tailed Z-test with 95% confidence."""
    # Variant clearly beats Control: Control 200/10000 (2%), Variant 300/10000 (3%)
    test_res = MediaAgencyCalculator.calculate_ab_test_significance(
        visitors_control=10000,
        conversions_control=200,
        visitors_variant=10000,
        conversions_variant=300,
        confidence_level=0.95,
    )
    assert isinstance(test_res, ABTestSignificanceAnalysis)
    assert test_res.is_statistically_significant is True
    assert test_res.p_value < 0.001
    assert test_res.relative_lift_pct == 50.0
    assert test_res.winner == "VARIANT"

    # Inconclusive test: Control 100/5000 (2.0%), Variant 103/5000 (2.06%)
    inc_res = MediaAgencyCalculator.calculate_ab_test_significance(
        visitors_control=5000,
        conversions_control=100,
        visitors_variant=5000,
        conversions_variant=103,
    )
    assert inc_res.is_statistically_significant is False
    assert inc_res.winner == "NO_WINNER"


def test_budget_pacing_and_run_rate():
    """Verify monthly spend pace, daily burn target, and corridor status."""
    # Target 60,000 for 30 days. On day 15, expected is 30,000. Actual is 36,000 (Over-pacing).
    pacing = MediaAgencyCalculator.calculate_budget_pacing(
        monthly_budget=60000.0,
        days_elapsed=15,
        days_in_month=30,
        current_spend=36000.0,
    )
    assert isinstance(pacing, BudgetPacingAndRunRateAnalysis)
    assert pacing.expected_spend_to_date == 30000.0
    assert pacing.pacing_ratio == 1.20
    assert pacing.pacing_status == "OVERSPENDING"
    assert pacing.projected_end_of_month_spend == 72000.0
    assert pacing.recommended_adjusted_daily_budget == 1600.0  # (60k - 36k) / 15 days


# ==============================================================================
# 2. Campaign Architecture & Creative Blueprint Tests
# ==============================================================================

def test_demand_gen_blueprint_generation():
    """Verify Google Demand Gen multi-format creative & lookalike asset pack."""
    architect = CampaignArchitect()
    analysis_mock = {
        "brand_info": {"brand_name": "AuraGlow"},
        "products": [{"name": "Anti-Aging Serum", "price": "450"}]
    }
    dg = architect.generate_google_demand_gen_blueprint(
        analysis=analysis_mock,
        monthly_budget=45000.0,
    )
    assert isinstance(dg, GoogleDemandGenBlueprint)
    assert "Demand Gen" in dg.campaign_name
    assert dg.monthly_budget == 45000.0
    assert len(dg.video_assets) == 3
    # Check aspect ratios
    aspects = [v["aspect_ratio"] for v in dg.video_assets]
    assert any("9:16" in a for a in aspects)
    assert any("16:9" in a for a in aspects)
    assert any("1:1" in a for a in aspects)
    assert len(dg.lookalike_segments) >= 3


def test_hook_swap_variations():
    """Verify 5 behavioral hook frameworks with identical bodies."""
    architect = CampaignArchitect()
    analysis_mock = {
        "brand_info": {"brand_name": "BioShield"},
        "products": [{"name": "Probiyotik Cilt Kremi", "price": "320"}]
    }
    package = architect.generate_hook_swap_variations(
        analysis=analysis_mock,
        base_creative_name="Kazanan UGC Video"
    )
    assert isinstance(package, CreativeHookSwapPackage)
    assert len(package.hook_variants) == 5
    hook_angles = [h["angle"] for h in package.hook_variants]
    assert any("Merak" in a for a in hook_angles)
    assert any("Negatif Uyarı" in a for a in hook_angles)
    assert package.winning_body_core_concept != ""
    assert package.actionable_testing_protocol != ""


def test_agency_onboarding_sla():
    """Verify 30-day agency onboarding milestones and fail-closed gates."""
    architect = CampaignArchitect()
    sla = architect.generate_agency_onboarding_sla("ZenVibe")
    assert isinstance(sla, AgencySLAAndOnboardingChecklist)
    assert sla.brand_name == "ZenVibe"
    assert len(sla.milestones) == 4
    # Ensure all 4 milestones have sla gates and fail closed rules exist
    gates = [m.sla_gate for m in sla.milestones]
    assert any("Erişim" in g for g in gates)
    assert any("Veri" in g for g in gates)
    assert len(sla.fail_closed_rules) >= 3


# ==============================================================================
# 3. Technical SEO & CRO Scorecard Tests
# ==============================================================================

def test_security_and_privacy_audit():
    """Verify CSP, HSTS, and Google Consent Mode v2 checks."""
    auditor = SEOAndMarTechAuditor()
    headers_ok = {
        "content-security-policy": "default-src 'self'",
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
    }
    body_with_consent = "<html><head><script>gtag('consent', 'default', {'ad_storage': 'denied'});</script></head><body>Aydınlatma Metni ve Çerez Politikası</body></html>"

    sec = auditor.audit_security_and_privacy(html=body_with_consent, headers=headers_ok)
    assert isinstance(sec, SecurityAndPrivacyAuditResult)
    assert sec.has_csp is True
    assert sec.has_hsts is True
    assert sec.consent_mode_v2_detected is True
    assert sec.cookie_banner_detected is True or sec.kvkk_gdpr_detected is True
    assert sec.security_score >= 80

    # Test broken headers & missing consent
    sec_bad = auditor.audit_security_and_privacy(html="<html><body>Simple site</body></html>", headers={})
    assert sec_bad.has_csp is False
    assert sec_bad.has_hsts is False
    assert sec_bad.consent_mode_v2_detected is False
    assert sec_bad.security_score < 50
    assert len(sec_bad.security_warnings) >= 3


def test_ecommerce_cro_scorecard():
    """Verify checkout friction, express pay, and guest checkout auditing."""
    auditor = SEOAndMarTechAuditor()
    html_cro_optimized = """
    <html>
      <div class="sticky-cta">Hemen Satın Al</div>
      <button class="masterpass-btn">Masterpass ile Öde</button>
      <div id="guest-checkout">Üye Olmadan Devam Et</div>
      <div class="trust-badge">256-bit SSL Güvenli Alışveriş - 14 Gün Koşulsuz İade</div>
      <form>
        <input type="text" name="name">
        <input type="tel" name="phone">
        <input type="text" name="address">
      </form>
    </html>
    """
    cro = auditor.audit_ecommerce_cro(html_cro_optimized)
    assert isinstance(cro, ECommerceCROScorecard)
    assert cro.sticky_cta_detected is True
    assert cro.express_checkout_detected is True
    assert "Masterpass" in cro.express_methods
    assert cro.guest_checkout_accessible is True
    assert len(cro.trust_badges_detected) >= 2
    assert cro.checkout_form_input_count == 3
    assert cro.friction_tier == "OPTIMAL"


def test_serp_feature_opportunities():
    """Verify Featured Snippet, PAA, and rich merchant data detection."""
    auditor = SEOAndMarTechAuditor()
    html_serp = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "Ortopedik Tabanlık",
          "image": "https://example.com/img.jpg",
          "offers": {
            "@type": "Offer",
            "price": "350",
            "priceCurrency": "TRY",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <h2>Sıkça Sorulan Sorular</h2>
        <h3>Tabanlık nasıl kullanılır?</h3>
        <p>Tüm spor ve günlük ayakkabılarla tam uyumludur tabanlığınızı içine yerleştiriniz.</p>
        <h3>Nasıl temizlenir?</h3>
        <p>Ilık sabunlu suyla elde yıkayınız ve gölgede kurutunuz çok pratik bir süreçtir.</p>
        <ol>
          <li>Eski tabanlığı çıkarın</li>
          <li>NovaStep tabanlığı yerleştirin</li>
        </ol>
      </body>
    </html>
    """
    schema_res = auditor.audit_schema_org(html_serp)
    serp = auditor.audit_serp_features(html_serp, schema_audit=schema_res)
    assert isinstance(serp, SERPFeatureOpportunityAuditResult)
    assert serp.paa_question_count >= 2
    assert any("nasıl" in q.lower() for q in serp.paa_questions_detected)
    assert serp.rich_merchant_readiness in ("READY", "PARTIAL")
    assert serp.serp_opportunity_score >= 50


# ==============================================================================
# 4. Engine Bridge & End-to-End Comprehensive Audit
# ==============================================================================

def test_media_agency_soldier_engine_bridge():
    """Verify MediaAgencySoldierEngine exposes all newly introduced capabilities."""
    engine = MediaAgencySoldierEngine()

    # Demand Gen
    dg = engine.generate_google_demand_gen_blueprint(
        analysis_result={"brand_info": {"brand_name": "Lumina"}, "products": [{"name": "Serum"}]},
        monthly_budget=35000.0,
    )
    assert "Demand Gen" in dg.campaign_name
    assert len(dg.video_assets) == 3

    # Hook Swap
    hooks = engine.generate_hook_swap_variations(
        analysis_result={"brand_info": {"brand_name": "Lumina"}, "products": [{"name": "Serum"}]},
        base_creative_name="Kazanan Video",
    )
    assert len(hooks.hook_variants) == 5

    # SLA Onboarding
    sla = engine.generate_agency_onboarding_sla("Lumina")
    assert len(sla.milestones) == 4
    assert len(sla.fail_closed_rules) >= 3

    # Security & Privacy
    sec = engine.audit_security_and_privacy(headers={"strict-transport-security": "max-age=3600"}, html="KVKK aydınlatma metni")
    assert sec.has_hsts is True

    # CRO
    cro = engine.audit_ecommerce_cro("<div class='sticky-cta'>Satın Al</div>")
    assert cro.sticky_cta_detected is True

    # SERP
    serp = engine.audit_serp_features("<h3>Nasıl uygulanır?</h3><ol><li>Adım 1</li></ol>")
    assert serp.paa_question_count >= 1


def test_full_web_media_audit_includes_all_12_categories(tmp_path):
    """Verify generate_audit produces all 12 categories with deep metrics."""
    html_file = tmp_path / "index.html"
    html_file.write_text("""
    <html>
      <head>
        <title>NovaStep Ortopedik Tabanlık</title>
        <script type="application/ld+json">
        {
          "@context":"https://schema.org/",
          "@type":"Product",
          "name":"NovaStep Tabanlık",
          "image":"https://novastep.com.tr/img.jpg",
          "offers":{"@type":"Offer","price":"350","priceCurrency":"TRY","availability":"https://schema.org/InStock"}
        }
        </script>
      </head>
      <body>
        <div class="sticky-cta">Sepete Ekle</div>
        <button class="masterpass">Hızlı Öde</button>
        <div class="trust-badge">256-bit SSL Güvenli Alışveriş 14 Gün İade</div>
        <h3>Ortopedik tabanlık nasıl temizlenir?</h3>
        <p>Ilık sabunlu suyla elde yıkayınız ve gölgede kurutunuz.</p>
        <ol><li>Ayakkabıyı açın</li><li>Tabanlığı yerleştirin</li></ol>
      </body>
    </html>
    """, encoding="utf-8")

    audit = generate_audit(
        url="https://novastep.com.tr",
        brand="NovaStep",
        offline_html=str(html_file),
        monthly_budget=60000.0,
    )

    assert "audit_categories" in audit
    categories = audit["audit_categories"]
    assert len(categories) == 12

    # Check deep audit structures
    assert "technical_seo_deep_audit" in audit
    technical_seo = audit["technical_seo_deep_audit"]
    assert "security_and_privacy" in technical_seo
    assert "ecommerce_cro" in technical_seo
    assert "serp_features" in technical_seo

    # Check campaign architecture
    assert "campaign_architecture" in audit
    blueprint = audit["campaign_architecture"]
    assert "google_demand_gen_blueprint" in blueprint
    assert "creative_hook_swap_package" in blueprint
    assert "agency_onboarding_sla" in blueprint

    # Check advanced economics
    assert "advanced_economics" in audit
    economics = audit["advanced_economics"]
    assert "discount_breakeven" in economics
    assert "poas_net_profit" in economics
    assert "mer_attribution" in economics
    assert "budget_pacing" in economics
    assert "ab_test_significance" in economics
