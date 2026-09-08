#!/usr/bin/env python3
"""
Web Media Audit: Professional 360 Digital Media Agency Audit CLI & Engine.
Executes MarTech tracking validation, deep SEO & CWV health checks,
CRO friction scoring, Unit Economics calculations (ROAS, MER, CPA),
and Multi-Channel Campaign Architecture synthesis.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional

# Safe UTF-8 reconfiguration for Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from url_analyzer import URLAnalyzer
from campaign_architect import CampaignArchitect
from media_calculator import MediaAgencyCalculator
from seo_analyzer import SEOAndMarTechAuditor


def generate_audit(
    url: str = "https://example.com",
    brand: Optional[str] = None,
    offline_html: Optional[str] = None,
    monthly_budget: float = 100000.0
) -> Dict[str, Any]:
    """
    Generates a complete 360 media agency audit combining MarTech signals,
    CRO/UX, Technical SEO, Unit Economics, and Multi-channel Campaigns.
    Maintains backward compatibility with basic stub callers.
    """
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc or url.replace("https://", "").replace("http://", "").split("/")[0] or "example.com"
    brand_name = brand or domain.split(".")[0].capitalize()

    analyzer = URLAnalyzer()
    architect = CampaignArchitect()
    calc = MediaAgencyCalculator()

    if offline_html and Path(offline_html).exists():
        html_content = Path(offline_html).read_text(encoding="utf-8", errors="replace")
        analysis = analyzer.analyze_html(html_content, url=url or f"https://{domain}")
    else:
        scaffold_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{brand_name} - Resmi Web Sitesi</title>
    <meta name="description" content="{brand_name} en kaliteli ürün ve hizmetleri sunar.">
    <link rel="canonical" href="https://{domain}" />
</head>
<body>
    <h1>{brand_name} Hoş Geldiniz</h1>
    <p>En iyi ürünler ve güvenli alışveriş.</p>
</body>
</html>"""
        html_content = scaffold_html
        analysis = analyzer.analyze_html(html_content, url=url or f"https://{domain}")

    if brand:
        analysis["brand_info"]["brand_name"] = brand

    # Campaigns & Ad plans
    campaigns = architect.generate_relational_campaigns(analysis)
    ad_plans = architect.generate_multichannel_ad_plans(analysis)
    unit_econ = architect.generate_unit_economics_plan(analysis, monthly_budget=monthly_budget)

    # Advanced SEO & Technical Audits
    seo_auditor = SEOAndMarTechAuditor()
    schema_audit = seo_auditor.audit_schema_org(html_content)
    cwv_audit = seo_auditor.audit_core_web_vitals_dom(html_content)
    index_audit = seo_auditor.audit_indexability(html_content, url=url or f"https://{domain}")
    cluster_audit = seo_auditor.audit_semantic_clusters(html_content)
    security_audit = seo_auditor.audit_security_and_privacy(html_content)
    ecom_cro_audit = seo_auditor.audit_ecommerce_cro(html_content)
    serp_feature_audit = seo_auditor.audit_serp_features(html_content, schema_audit=schema_audit)

    # Advanced Blueprints & Flight Plan
    asc_blueprint = architect.generate_meta_asc_blueprint(analysis, monthly_meta_budget=monthly_budget * 0.55)
    pmax_blueprint = architect.generate_google_pmax_blueprint(analysis, monthly_google_budget=monthly_budget * 0.30)
    demand_gen_bp = architect.generate_google_demand_gen_blueprint(analysis, monthly_budget=monthly_budget * 0.15)
    hook_swap_pkg = architect.generate_hook_swap_variations(analysis)
    onboarding_sla = architect.generate_agency_onboarding_sla(brand_name)
    retention_flows = architect.generate_retention_flows(analysis.get("brand_info", {}))
    flight_plan = architect.generate_30_60_90_flight_plan(monthly_budget=monthly_budget, analysis=analysis)

    # Advanced Unit Economics calculations
    prods = analysis.get("products", [])
    avg_price = prods[0].get("price", 850.0) if prods and prods[0].get("price") else 850.0
    ltv_card = calc.calculate_ltv_and_payback(
        aov=avg_price,
        purchase_frequency_annual=3.2,
        gross_margin_pct=55.0,
        annual_churn_rate_pct=30.0,
        cac=avg_price * 0.35
    )
    cm_card = calc.calculate_contribution_margins(
        revenue=avg_price,
        cogs=avg_price * 0.45,
        logistics_and_shipping=55.0,
        payment_gateway_fee=avg_price * 0.025,
        ad_spend=avg_price * 0.25
    )
    ncac_card = calc.calculate_ncac(
        total_ad_spend=monthly_budget,
        total_orders=max(1, int(monthly_budget / max(1.0, avg_price * 0.35))),
        new_customers=max(1, int(monthly_budget / max(1.0, avg_price * 0.42)))
    )
    testing_budget = calc.calculate_creative_testing_budget(cpm=45.0, expected_ctr_pct=1.8, expected_cvr_pct=2.5)

    order_est = max(10, int(monthly_budget / max(1.0, avg_price * 0.35)))
    discount_sim = calc.simulate_discount_breakeven(
        gross_margin_pct=55.0,
        discount_pct=15.0,
        current_orders=order_est,
        current_aov=avg_price
    )
    poas_sim = calc.calculate_poas_net_profit(
        gross_revenue=avg_price * order_est,
        ad_spend=monthly_budget * 0.35,
        cogs=avg_price * order_est * 0.45,
        logistics_and_shipping=55.0 * order_est,
        payment_gateway_rate_pct=2.8,
        return_refund_rate_pct=7.5
    )
    mer_analysis = calc.calculate_mer_and_attribution(
        total_net_revenue=avg_price * order_est * 0.925,
        total_ad_spend=monthly_budget,
        channel_reported_revenues={
            "Meta ASC": monthly_budget * 2.2,
            "Google PMax": monthly_budget * 1.8,
            "TikTok Spark": monthly_budget * 0.6
        }
    )
    budget_pacing = calc.calculate_budget_pacing(
        monthly_budget=monthly_budget,
        days_elapsed=12,
        days_in_month=30,
        current_spend=monthly_budget * 0.41
    )
    ab_test_analysis = calc.calculate_ab_test_significance(
        visitors_control=5000,
        conversions_control=120,
        visitors_variant=5000,
        conversions_variant=165,
        confidence_level=0.95
    )

    # MarTech status
    martech = analysis.get("martech_tracking", {})
    martech_status = "Hazır" if martech.get("ready_for_paid_traffic") else "Eksik Kodlar Var"

    # Category status cards
    audit_categories = [
        {
            "category": "Marka Kimliği & Yasal Bilgiler",
            "status": "İncelendi",
            "priority": "Yüksek",
            "score": 100,
            "details": f"Marka: {brand_name}, Domain: {domain}"
        },
        {
            "category": "MarTech & Takip Kodları (GA4 / CAPI)",
            "status": martech_status,
            "priority": "Kritik (P0)",
            "score": martech.get("martech_health_score", 50.0),
            "details": f"Tespit edilen: {martech.get('detected_count', 0)}/{martech.get('total_checked', 6)} etiket"
        },
        {
            "category": "Güvenlik, CSP & Consent Mode v2",
            "status": "Uyumlu" if security_audit.consent_mode_v2_detected else "Consent Mode Eksik",
            "priority": "Kritik (P0)",
            "score": float(security_audit.security_score),
            "details": f"CSP: {'Var' if security_audit.has_csp else 'Yok'}, Consent v2: {'Aktif' if security_audit.consent_mode_v2_detected else 'Eksik'}"
        },
        {
            "category": "Schema.org & Yapılandırılmış Veri",
            "status": "Hazır" if schema_audit.valid_product_schema else "Eksik Alanlar",
            "priority": "Yüksek",
            "score": float(schema_audit.schema_health_score),
            "details": f"Şemalar: {', '.join(schema_audit.schema_types_detected) or 'Bulunamadı'}"
        },
        {
            "category": "Core Web Vitals DOM Teşhisi",
            "status": f"Risk: {cwv_audit.lcp_risk}",
            "priority": "Yüksek",
            "score": float(cwv_audit.cwv_score),
            "details": f"LCP: {cwv_audit.lcp_risk}, CLS: {cwv_audit.cls_risk}, INP: {cwv_audit.inp_risk}"
        },
        {
            "category": "İndekslenebilirlik & Sosyal Grafikler",
            "status": "İndekslenebilir" if index_audit.is_indexable else "Noindex Engeli",
            "priority": "Yüksek",
            "score": float(index_audit.indexability_score),
            "details": f"Canonical: {index_audit.canonical_status}, OG Görsel: {'Var' if index_audit.has_og_image else 'Yok'}"
        },
        {
            "category": "E-Ticaret CRO & Mobil Sürtünme",
            "status": ecom_cro_audit.friction_tier,
            "priority": "Yüksek",
            "score": float(ecom_cro_audit.cro_score),
            "details": f"Sticky CTA: {'Var' if ecom_cro_audit.sticky_cta_detected else 'Yok'}, Express: {', '.join(ecom_cro_audit.express_methods) or 'Yok'}"
        },
        {
            "category": "SERP Fırsatları (Snippet & PAA)",
            "status": f"Snippet: {serp_feature_audit.featured_snippet_readiness}",
            "priority": "Orta",
            "score": float(serp_feature_audit.serp_opportunity_score),
            "details": f"PAA Soru Sayısı: {serp_feature_audit.paa_question_count}, Merchant: {serp_feature_audit.rich_merchant_readiness}"
        },
        {
            "category": "Birim Ekonomisi & Breakeven ROAS",
            "status": "Hesaplandı",
            "priority": "Kritik",
            "score": 100,
            "details": f"Breakeven ROAS: {unit_econ.get('breakeven_roas')}x, Hedef ROAS: {unit_econ.get('target_roas')}x"
        },
        {
            "category": "LTV:CAC & CAC Geri Ödeme (Payback)",
            "status": ltv_card.health_status,
            "priority": "Kritik",
            "score": 95 if ltv_card.health_status == "OPTIMAL" else 60,
            "details": f"LTV: ₺{ltv_card.ltv:.2f}, LTV:CAC: {ltv_card.ltv_to_cac_ratio:.2f}x, Payback: {ltv_card.payback_period_months:.1f} ay"
        },
        {
            "category": "Katkı Marjı Kademeleri (CM1-CM3)",
            "status": "Pozitif" if cm_card.is_unit_profitable else "Negatif",
            "priority": "Kritik",
            "score": 95 if cm_card.is_unit_profitable else 40,
            "details": f"CM1: %{cm_card.cm1_pct:.1f}, CM2: %{cm_card.cm2_pct:.1f}, CM3: %{cm_card.cm3_pct:.1f}"
        },
        {
            "category": "POAS Net Kârlılık & MER Ölçümü",
            "status": "Kârlı" if poas_sim.is_profitable else "Zarar",
            "priority": "Kritik",
            "score": 95 if poas_sim.is_profitable else 45,
            "details": f"POAS: {poas_sim.poas:.2f}x, MER: {mer_analysis.blended_mer:.2f}x (Çift Sayım: {mer_analysis.attribution_overlap_factor:.2f}x)"
        }
    ]

    return {
        "brand_name": brand_name,
        "domain": domain,
        "target_url": url,
        "audit_categories": audit_categories,
        "recommended_funnel": {
            "tofu": "Eğitici video kancaları, TikTok Spark Ads, Google Demand Gen & Meta Reels (%55 Bütçe)",
            "mofu": "Kullanıcı yorumları, Carousel ve Google Search ticari arama (%25 Bütçe)",
            "bofu": "Meta ASC, DPA dinamik sepet tamamlama & Google PMax (%15 Bütçe)",
            "retention": "Klaviyo e-posta/SMS hoş geldin, terk edilen sepet ve VIP akışları (%5 Bütçe)"
        },
        "unit_economics": unit_econ,
        "advanced_economics": {
            "ltv_payback": ltv_card.model_dump(),
            "contribution_margins": cm_card.model_dump(),
            "ncac_analysis": ncac_card.model_dump(),
            "testing_budget_322": testing_budget.model_dump(),
            "discount_breakeven": discount_sim.model_dump(),
            "poas_net_profit": poas_sim.model_dump(),
            "mer_attribution": mer_analysis.model_dump(),
            "budget_pacing": budget_pacing.model_dump(),
            "ab_test_significance": ab_test_analysis.model_dump()
        },
        "technical_seo_deep_audit": {
            "schema_org": schema_audit.model_dump(),
            "core_web_vitals": cwv_audit.model_dump(),
            "indexability": index_audit.model_dump(),
            "semantic_clusters": cluster_audit.model_dump(),
            "security_and_privacy": security_audit.model_dump(),
            "ecommerce_cro": ecom_cro_audit.model_dump(),
            "serp_features": serp_feature_audit.model_dump()
        },
        "campaign_architecture": {
            "relational_campaigns": campaigns,
            "multichannel_ad_plans": ad_plans,
            "meta_asc_blueprint": asc_blueprint.model_dump(),
            "google_pmax_blueprint": pmax_blueprint.model_dump(),
            "google_demand_gen_blueprint": demand_gen_bp.model_dump(),
            "creative_hook_swap_package": hook_swap_pkg.model_dump(),
            "agency_onboarding_sla": onboarding_sla.model_dump(),
            "retention_flows": [f.model_dump() for f in retention_flows],
            "media_flight_plan": flight_plan.model_dump()
        },
        "agency_tool_stack": analysis.get("agency_tool_recommendations", [])
    }


def print_ascii_summary(audit: Dict[str, Any]):
    """Renders a clean formatted summary table in terminal."""
    b_name = audit.get("brand_name", "Marka")
    domain = audit.get("domain", "")
    unit = audit.get("unit_economics", {})

    print("\n" + "=" * 76)
    print(f"  🛡️  MEDYA AJANSI 360 WEB DENETİM VE BÜYÜME RAPORU: {b_name.upper()} ({domain})")
    print("=" * 76)
    print(f"{'KATEGORİ':<38} | {'DURUM':<14} | {'ÖNCELİK':<12} | {'SKOR':<6}")
    print("-" * 76)
    for cat in audit.get("audit_categories", []):
        print(f"{cat['category']:<38} | {cat['status']:<14} | {cat['priority']:<12} | %{cat['score']:<5.0f}")
    print("-" * 76)

    print("\n[📊 BİRİM EKONOMİSİ VE ROAS HEDEFLERİ]")
    print(f"  - Başa Baş ROAS (Breakeven)   : {unit.get('breakeven_roas', 1.82)}x (%{unit.get('breakeven_roas_pct', 182.0)})")
    print(f"  - Hedef ROAS (%15 Net Kâr)    : {unit.get('target_roas', 2.50)}x (%{unit.get('target_roas_pct', 250.0)})")
    print(f"  - Maksimum İzin Verilen CPA   : {unit.get('max_allowable_cpa', 200.0)} {unit.get('currency', '₺')}")

    adv = audit.get("advanced_economics", {})
    ltv = adv.get("ltv_payback", {})
    if ltv:
        print(f"  - Müşteri Yaşam Boyu Değeri  : ₺{ltv.get('ltv', 0):.2f} (LTV:CAC: {ltv.get('ltv_to_cac_ratio', 0)}x - {ltv.get('health_status')})")
        print(f"  - CAC Geri Ödeme Süresi       : {ltv.get('payback_period_months', 0):.1f} Ay (Payback Period)")

    cm = adv.get("contribution_margins", {})
    if cm:
        print(f"  - Katkı Marjları (CM1/2/3)    : CM1: %{cm.get('cm1_pct', 0):.1f} | CM2: %{cm.get('cm2_pct', 0):.1f} | CM3: %{cm.get('cm3_pct', 0):.1f}")

    poas = adv.get("poas_net_profit", {})
    if poas:
        print(f"  - POAS Net Kâr Oranı          : {poas.get('poas', 0):.2f}x (Net Kâr Marjı: %{poas.get('net_margin_pct', 0):.1f})")

    mer = adv.get("mer_attribution", {})
    if mer:
        print(f"  - Harmanlanmış MER            : {mer.get('blended_mer', 0):.2f}x (Çift Sayım / Overlap: {mer.get('attribution_overlap_factor', 0):.2f}x)")

    disc = adv.get("discount_breakeven", {})
    if disc:
        print(f"  - İndirim Başa Baş Artış      : %{disc.get('discount_pct', 0):.1f} İndirimde Gerekli Sipariş Hacmi: +%{disc.get('required_volume_increase_pct', 0):.1f}")

    pacing = adv.get("budget_pacing", {})
    if pacing:
        print(f"  - Bütçe Pacing Durumu         : {pacing.get('pacing_status')} (Hız Oranı: %{pacing.get('pacing_ratio', 1.0) * 100:.1f})")

    print("\n[🎯 ÖNERİLEN HUNİ BÜTÇE DAĞILIMI]")
    alloc = unit.get("funnel_budget_allocations", {}).get("balanced", {}).get("tiers", [])
    for tier in alloc:
        print(f"  - {tier.get('stage')}: %{tier.get('allocation_pct')} ({tier.get('amount')} {unit.get('currency', '₺')}) -> {tier.get('name')}")

    ca = audit.get("campaign_architecture", {})
    asc = ca.get("meta_asc_blueprint", {})
    if asc:
        print(f"\n[🚀 META ADVANTAGE+ SHOPPING (ASC)]")
        print(f"  - Kampanya: {asc.get('campaign_name')}")
        print(f"  - Bütçe: ₺{asc.get('allocated_monthly_budget', 0):,.2f} | Mevcut Müşteri Cap: %{asc.get('existing_customer_budget_cap_pct')}")

    pmax = ca.get("google_pmax_blueprint", {})
    if pmax:
        print(f"\n[🔍 GOOGLE PERFORMANCE MAX (PMAX)]")
        print(f"  - Kampanya: {pmax.get('campaign_name')}")
        print(f"  - tROAS Hedefi: %{pmax.get('target_roas_pct', 260.0):.0f} | Bütçe: ₺{pmax.get('allocated_monthly_budget', 0):,.2f}")

    dg = ca.get("google_demand_gen_blueprint", {})
    if dg:
        print(f"\n[📱 GOOGLE DEMAND GEN (SHORTS & DISCOVER)]")
        print(f"  - Kampanya: {dg.get('campaign_name')}")
        print(f"  - Bütçe: ₺{dg.get('monthly_budget', 0):,.2f} | Hedef Kanallar: {', '.join(dg.get('target_channels', []))}")

    hook_pkg = ca.get("creative_hook_swap_package", {})
    if hook_pkg:
        print(f"\n[🎬 KREATİF YORGUNLUK & HOOK-SWAP YENİLEME]")
        print(f"  - Temel Kreatif: {hook_pkg.get('winning_creative_id')}")
        for h in hook_pkg.get("hook_variants", [])[:2]:
            print(f"    * {h.get('angle')}: \"{h.get('headline_text')}\"")

    print("\n[🛠️ TAVSİYE EDİLEN AJANS ARAÇLARI]")
    for tool in audit.get("agency_tool_stack", [])[:3]:
        print(f"  - {tool.get('name')}: {tool.get('use_case')}")
    print("=" * 76 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Generate 360 Media Agency brand audit & campaign architecture")
    parser.add_argument("--url", default="https://example.com", help="Target website URL")
    parser.add_argument("--brand", default=None, help="Brand name")
    parser.add_argument("--offline-html", default=None, help="Path to local offline HTML file")
    parser.add_argument("--budget", type=float, default=100000.0, help="Monthly digital marketing budget")
    parser.add_argument("--output-json", default=None, help="File path to export JSON report")
    parser.add_argument("--output-md", default=None, help="File path to export Markdown report")
    args = parser.parse_args()

    res = generate_audit(
        url=args.url,
        brand=args.brand,
        offline_html=args.offline_html,
        monthly_budget=args.budget
    )

    print_ascii_summary(res)

    if args.output_json:
        out_p = Path(args.output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON raporu kaydedildi: {out_p}")

    if args.output_md:
        out_m = Path(args.output_md)
        out_m.parent.mkdir(parents=True, exist_ok=True)
        # Markdown Scaffold
        md_lines = [
            f"# 360 Medya Ajansı Denetim ve Büyüme Raporu: {res['brand_name']}\n",
            f"**URL:** `{res['target_url']}` | **Domain:** `{res['domain']}`\n",
            "## 1. Denetim Kategorileri ve Durum",
            "| Kategori | Durum | Öncelik | Skor |",
            "| :--- | :--- | :--- | :--- |"
        ]
        for c in res["audit_categories"]:
            md_lines.append(f"| {c['category']} | {c['status']} | {c['priority']} | %{c['score']:.0f} |")
        md_lines.append("\n## 2. Birim Ekonomisi ve Kârlılık Standartları")
        u = res["unit_economics"]
        md_lines.append(f"- **Başa Baş ROAS (Breakeven)**: {u.get('breakeven_roas')}x")
        md_lines.append(f"- **Hedef ROAS**: {u.get('target_roas')}x")
        md_lines.append(f"- **Maksimum CPA**: {u.get('max_allowable_cpa')} {u.get('currency')}")

        adv = res.get("advanced_economics", {})
        ltv = adv.get("ltv_payback", {})
        if ltv:
            md_lines.append(f"- **Müşteri Yaşam Boyu Değeri (LTV)**: ₺{ltv.get('ltv', 0):.2f}")
            md_lines.append(f"- **LTV:CAC Rasyosu**: {ltv.get('ltv_to_cac_ratio', 0)}x ({ltv.get('health_status')})")
            md_lines.append(f"- **CAC Payback Süresi**: {ltv.get('payback_period_months', 0):.1f} Ay")

        cm = adv.get("contribution_margins", {})
        if cm:
            md_lines.append(f"- **Katkı Marjları**: CM1: %{cm.get('cm1_pct')} | CM2: %{cm.get('cm2_pct')} | CM3: %{cm.get('cm3_pct')}")

        poas_d = adv.get("poas_net_profit", {})
        if poas_d:
            md_lines.append(f"- **POAS**: {poas_d.get('poas')}x | **Net Marj**: %{poas_d.get('net_margin_pct')}")

        mer_d = adv.get("mer_attribution", {})
        if mer_d:
            md_lines.append(f"- **Harmanlanmış MER**: {mer_d.get('blended_mer')}x (Overlap Faktörü: {mer_d.get('attribution_overlap_factor')}x)")

        disc_d = adv.get("discount_breakeven", {})
        if disc_d:
            md_lines.append(f"- **İndirim Hacim Esnekliği Başa Baş**: %{disc_d.get('discount_pct')} İndirim için Hacim Artış Gereksinimi: +%{disc_d.get('required_volume_increase_pct')}")

        ca = res.get("campaign_architecture", {})
        asc = ca.get("meta_asc_blueprint", {})
        if asc:
            md_lines.append(f"\n## 3. Meta Advantage+ Shopping (ASC) Mimarisi")
            md_lines.append(f"- **Kampanya Adı**: `{asc.get('campaign_name')}`")
            md_lines.append(f"- **Aylık Bütçe**: ₺{asc.get('allocated_monthly_budget', 0):,.2f}")
            md_lines.append(f"- **Mevcut Müşteri Tavanı**: %{asc.get('existing_customer_budget_cap_pct')}")

        pmax = ca.get("google_pmax_blueprint", {})
        if pmax:
            md_lines.append(f"\n## 4. Google Performance Max (PMax) Mimarisi")
            md_lines.append(f"- **Kampanya Adı**: `{pmax.get('campaign_name')}`")
            md_lines.append(f"- **tROAS Hedefi**: %{pmax.get('target_roas_pct')}")
            md_lines.append(f"- **Aylık Bütçe**: ₺{pmax.get('allocated_monthly_budget', 0):,.2f}")

        dg = ca.get("google_demand_gen_blueprint", {})
        if dg:
            md_lines.append(f"\n## 5. Google Demand Gen (Shorts & Discover) Mimarisi")
            md_lines.append(f"- **Kampanya Adı**: `{dg.get('campaign_name')}`")
            md_lines.append(f"- **Aylık Bütçe**: ₺{dg.get('monthly_budget', 0):,.2f}")
            md_lines.append(f"- **Hedef Kanallar**: {', '.join(dg.get('target_channels', []))}")

        flows = ca.get("retention_flows", [])
        if flows:
            md_lines.append("\n## 6. Retention E-Posta & SMS Yaşam Döngüsü Akışları")
            for fl in flows:
                md_lines.append(f"- **{fl.get('flow_name')}**: Tetikleyici: `{fl.get('trigger_event')}` (Tahmini Katkı: %{fl.get('projected_revenue_contribution_pct')})")

        out_m.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"Markdown raporu kaydedildi: {out_m}")


if __name__ == "__main__":
    main()
