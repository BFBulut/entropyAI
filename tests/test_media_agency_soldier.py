"""
Comprehensive QA Sentinel Test Suite for 'skills/media-agency-soldier'.
Tests:
1. URLAnalyzer:
   - Synthetic/Mock HTML: E-commerce, SaaS, Corporate.
   - Brand, Domain, Legal Company Title detection.
   - Physical Location (City, Country, Street/Address) and Contact Info (phone, email, social).
   - Product Catalog (products, currency prices e.g. ₺299, $49, categories).
   - Competitor detection and market benchmarking.
   - SEO Audit: Title length, Meta Description, H1 singularity/missing, OpenGraph, Canonical, Schema.org JSON-LD, Search intents.
   - Core Web Vitals & Performance: WebP/AVIF ratio, script loads, compression.
   - CRO & UX Audit: CTA buttons, trust badges, form friction.
2. CampaignArchitect:
   - Relational campaigns: BOGO ('X alana Y bedava'), Cross-Discount ('X alana Y %10 indirimli'), Cart Threshold ('X TL üzeri kargo bedava').
   - Multichannel ad plans:
     - Google Search Ads (Headlines <= 30 chars, Descriptions <= 90 chars, Negatives).
     - Meta/Instagram Ads (Hook, Carousel cards, UGC 5-stage script).
     - TikTok/Reels Ads (Hook/Kanca, Trend concept, Beats, CTA).
3. AgencySoldier CLI:
   - `--offline-html` parameter end-to-end execution.
   - JSON output verification.
   - Markdown report output verification.
4. MediaAgencySoldierEngine (Bridge):
   - Entropy AI main architecture integration and invocability.
   - Event bus signal verification.
   - SkillManager skill discovery.
"""

import sys
import json
import pytest
from pathlib import Path

# Ensure repo root and skill directory are in sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "media-agency-soldier"
SRC_DIR = REPO_ROOT / "src"

for p in [str(REPO_ROOT), str(SKILL_DIR), str(SRC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from skills.media_agency_soldier.url_analyzer import URLAnalyzer
from skills.media_agency_soldier.campaign_architect import CampaignArchitect
from skills.media_agency_soldier.soldier import AgencySoldier
from entropy.skills.media_agency_soldier_engine import MediaAgencySoldierEngine
from entropy.skills.manager import SkillManager
from entropy.core.event_bus import bus


# =====================================================================
# SYNTHETIC HTML FIXTURES
# =====================================================================

@pytest.fixture
def ecommerce_html() -> str:
    """Rich e-commerce store HTML with schema.org, WebP images, optimal SEO, and BOGO opportunities."""
    return """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>NovaStep - Hakiki Deri Ayakkabı &amp; Aksesuar Koleksiyonu</title>
    <meta name="description" content="NovaStep resmi online mağazasında el işçiliği hakiki deri erkek ayakkabıları ve aksesuarları keşfedin. Hemen sipariş verin ve fırsatları yakalayın.">
    <link rel="canonical" href="https://novastep.com.tr" />
    <meta property="og:title" content="NovaStep Deri Ayakkabı & Aksesuar" />
    <meta property="og:description" content="Yüksek kaliteli el yapımı hakiki deri ayakkabı ve cüzdanlar." />
    <meta property="og:image" content="https://novastep.com.tr/assets/banner.webp" />
    <meta property="og:url" content="https://novastep.com.tr" />
    <meta property="og:site_name" content="NovaStep" />
    <link rel="stylesheet" href="/css/main.min.css">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "NovaStep",
        "legalName": "NovaStep Ayakkabı ve Mağazacılık Ticaret A.Ş.",
        "url": "https://novastep.com.tr",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "Bağdat Caddesi No: 142",
            "addressLocality": "Kadıköy, İstanbul",
            "addressCountry": "Türkiye",
            "postalCode": "34728"
        }
    }
    </script>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Hakiki Deri Klasik Ayakkabı",
        "category": "Erkek Ayakkabı",
        "offers": {
            "@type": "Offer",
            "price": "799.00",
            "priceCurrency": "TRY"
        }
    }
    </script>
</head>
<body>
    <header>
        <h1>NovaStep 2026 Deri Ayakkabı &amp; Çanta Koleksiyonu</h1>
        <nav>
            <a href="tel:+902165550199">0216 555 01 99</a>
            <a href="mailto:destek@novastep.com.tr">destek@novastep.com.tr</a>
            <a href="https://instagram.com/novasteptr">Instagram</a>
            <a href="https://twitter.com/novasteptr">Twitter</a>
        </nav>
    </header>
    <main>
        <!-- Product Catalog Section -->
        <section class="products-grid">
            <div class="product-card">
                <h3>Hakiki Deri Klasik Ayakkabı</h3>
                <span class="category">Erkek Ayakkabı</span>
                <span class="price">₺799.00</span>
                <button class="btn btn-primary">Sepete Ekle</button>
            </div>
            <div class="product-card">
                <h3>Deri Minimalist Cüzdan</h3>
                <span class="category">Aksesuar</span>
                <span class="price">₺299.00</span>
                <button class="btn btn-primary">Hemen Satın Al</button>
            </div>
            <div class="product-card">
                <h3>Sportif Sneaker</h3>
                <span class="category">Spor</span>
                <span class="price">₺599.00</span>
                <a href="/urun/sneaker" class="btn cta">Fırsatı Keşfet</a>
            </div>
        </section>

        <!-- Market & Competitor Comparison Section -->
        <section class="comparison-section">
            <h2>Neden NovaStep? Karşılaştırma ve Farkımız</h2>
            <p>Nike ve Adidas standartlarında üst sınıf deri kalitesi ve yerli üretim fiyat avantajı.</p>
        </section>

        <!-- Trust Badges -->
        <section class="trust-container">
            <span class="badge">256-bit SSL Güvenli Ödeme</span>
            <span class="badge">3D Secure</span>
            <span class="badge">14 Gün Koşulsuz Para İade Garantisi</span>
            <span class="badge">Orijinal Ürün Sertifikası</span>
        </section>

        <!-- Newsletter Low-friction Form -->
        <section class="newsletter">
            <form action="/subscribe" method="post">
                <input type="email" name="email" placeholder="E-posta adresiniz" required />
                <button type="submit">Kayıt Ol ve İndirimi Kap</button>
            </form>
        </section>

        <!-- Images Section with Modern Formats -->
        <section class="gallery">
            <img src="/assets/hero.webp" loading="lazy" alt="Hero Ayakkabı" />
            <img src="/assets/detail.avif" loading="lazy" alt="Deri Detay" />
            <img src="/assets/cuzdan.webp" loading="lazy" alt="Deri Cüzdan" />
            <img src="/assets/logo.svg" alt="NovaStep Logo" />
        </section>
    </main>
    <footer>
        <address>Bağdat Caddesi No: 142, Kadıköy, İstanbul, Türkiye</address>
        <p>&copy; 2026 NovaStep Ayakkabı ve Mağazacılık Ticaret A.Ş. Tüm hakları saklıdır.</p>
    </footer>
    <script src="/js/app.min.js" defer></script>
    <script src="/js/analytics.min.js" async></script>
</body>
</html>"""


@pytest.fixture
def saas_html() -> str:
    """SaaS software platform HTML with USD currency, competitor alternatives, and pricing tiers."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MetricPulse - Real-time Infrastructure Monitoring SaaS Platform</title>
    <meta name="description" content="Cloud infrastructure monitoring platform at scale.">
    <link rel="canonical" href="https://metricpulse.io" />
    <meta property="og:title" content="MetricPulse Cloud" />
    <meta property="og:image" content="https://metricpulse.io/og.png" />
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "MetricPulse",
        "legalName": "MetricPulse Technologies Inc.",
        "url": "https://metricpulse.io",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "500 Howard Street",
            "addressLocality": "San Francisco",
            "addressCountry": "USA"
        }
    }
    </script>
</head>
<body>
    <nav>
        <a href="tel:+14155554321">+1 (415) 555-4321</a>
        <a href="mailto:sales@metricpulse.io">sales@metricpulse.io</a>
        <a href="https://linkedin.com/company/metricpulse">LinkedIn</a>
        <a href="https://x.com/metricpulse">Twitter</a>
    </nav>
    <main>
        <h1>Next-Gen Cloud Observability for High-Growth Tech Teams</h1>
        <div class="pricing-card">
            <h3>Starter Cloud Plan</h3>
            <div class="price">$49 / mo</div>
            <a href="/signup" class="btn">Start Free Trial</a>
        </div>
        <div class="pricing-card">
            <h3>Pro Enterprise Plan</h3>
            <div class="price">$199 / mo</div>
            <a href="/demo" class="btn">Schedule a Demo</a>
        </div>

        <!-- Competitor Comparison -->
        <div class="comparison-block">
            <h2>Why Tech Leaders Choose Us vs Datadog and NewRelic</h2>
            <p>10x faster query speeds with 70% lower cloud egress costs.</p>
        </div>

        <form class="trial-form">
            <input type="text" name="name" placeholder="Full Name" required />
            <input type="email" name="work_email" placeholder="Work Email" required />
            <input type="password" name="password" placeholder="Password" required />
            <button type="submit">Create Workspace</button>
        </form>

        <div class="security-badges">
            <span>SOC2 Certified</span>
            <span>256-bit SSL Data Encryption</span>
        </div>
    </main>
    <footer>
        <address>500 Howard Street, San Francisco, California, USA</address>
        <p>&copy; 2026 MetricPulse Technologies Inc. All rights reserved.</p>
    </footer>
    <!-- Blocking scripts -->
    <script src="/vendor/tracker.js"></script>
    <script src="/vendor/heavy-library.js"></script>
    <script src="/vendor/chat-widget.js"></script>
</body>
</html>"""


@pytest.fixture
def corporate_html() -> str:
    """Corporate logistics firm HTML with SEO violations (multiple H1, missing meta desc, high form friction)."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>Atlas</title>
    <!-- Missing meta description and canonical -->
</head>
<body>
    <header>
        <h1>Atlas Lojistik</h1>
        <h1>Uluslararası Taşımacılık Hizmetleri</h1>
        <a href="tel:08503334455">0850 333 44 55</a>
        <a href="mailto:info@atlaslojistik.com">info@atlaslojistik.com</a>
    </header>
    <main>
        <p>DHL ve Aras Kargo standartlarında güvenilir sevkiyat.</p>
        <!-- High Friction Form with 10 fields -->
        <form class="quote-form">
            <input type="text" name="company" placeholder="Şirket Adı" />
            <input type="text" name="tax_no" placeholder="Vergi No" />
            <input type="text" name="contact_person" placeholder="Yetkili Kişi" />
            <input type="tel" name="phone" placeholder="Telefon" />
            <input type="email" name="email" placeholder="E-posta" />
            <input type="text" name="pickup_city" placeholder="Çıkış Şehri" />
            <input type="text" name="dest_city" placeholder="Varış Şehri" />
            <input type="text" name="cargo_weight" placeholder="Yük Ağırlığı (Kg)" />
            <input type="text" name="volume" placeholder="Hacim (m3)" />
            <textarea name="notes" placeholder="Özel Notlar"></textarea>
            <button type="submit">Fiyat Teklifi Al</button>
        </form>
        <!-- Legacy images -->
        <img src="/img/truck1.jpg" alt="Tır 1" />
        <img src="/img/truck2.png" alt="Tır 2" />
        <img src="/img/warehouse.jpg" alt="Depo" />
        <img src="/img/office.png" alt="Ofis" />
    </main>
    <footer>
        <address>Eskişehir Yolu 9. Km, Çankaya, Ankara, Türkiye</address>
        <p>&copy; 2026 Atlas Uluslararası Taşımacılık ve Lojistik Ticaret A.Ş.</p>
    </footer>
</body>
</html>"""


# =====================================================================
# 1. URLANALYZER TESTS
# =====================================================================

class TestURLAnalyzer:
    """Test URLAnalyzer across e-commerce, SaaS, and corporate web assets."""

    def test_ecommerce_brand_domain_and_company_title(self, ecommerce_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        brand_info = res["brand_info"]

        assert brand_info["brand_name"] == "NovaStep"
        assert brand_info["domain"] == "novastep.com.tr"
        assert "NovaStep Ayakkabı ve Mağazacılık Ticaret A.Ş." in brand_info["company_title"]

    def test_ecommerce_location_and_contact_detection(self, ecommerce_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        contact = res["contact_and_location"]

        assert "İstanbul" in contact["city"]
        assert "Türkiye" in contact["country"]
        assert "Kadıköy" in contact["address"]
        assert any("0199" in p or "555" in p for p in contact["phones"])
        assert "destek@novastep.com.tr" in contact["emails"]
        assert "instagram.com/novasteptr" in contact["social_media"]["instagram"]
        assert "twitter.com/novasteptr" in contact["social_media"]["twitter"]

    def test_ecommerce_product_catalog_and_currency_prices(self, ecommerce_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        catalog = res["product_catalog"]

        assert catalog["count"] >= 3
        # Check specific product prices
        prod_names = [p["name"] for p in catalog["products"]]
        assert "Hakiki Deri Klasik Ayakkabı" in prod_names
        assert "Deri Minimalist Cüzdan" in prod_names
        assert "Sportif Sneaker" in prod_names

        prices = {p["name"]: p["price"] for p in catalog["products"]}
        assert prices["Deri Minimalist Cüzdan"] == 299.0
        assert prices["Sportif Sneaker"] == 599.0
        assert prices["Hakiki Deri Klasik Ayakkabı"] == 799.0

        assert "₺" in catalog["currencies"]
        assert catalog["min_price"] == 299.0
        assert catalog["max_price"] == 799.0
        assert catalog["average_price"] > 500.0

    def test_ecommerce_competitor_and_market_positioning(self, ecommerce_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        comp = res["competitors"]

        assert comp["comparison_present"] is True
        assert "Nike" in comp["detected_competitors"] or "Adidas" in comp["detected_competitors"]
        assert "Orta Segment" in comp["market_positioning"] or "Rekabetçi" in comp["market_positioning"]

    def test_ecommerce_seo_audit_success(self, ecommerce_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        seo = res["seo_audit"]

        # Title: 30-60 chars optimal
        assert seo["title_status"] == "optimal"
        assert 30 <= seo["title_length"] <= 60

        # Meta description: 120-160 chars optimal
        assert seo["meta_description_status"] == "optimal"
        assert 120 <= seo["meta_description_length"] <= 160

        # Single H1 check
        assert seo["h1_status"] == "optimal"
        assert seo["h1_count"] == 1
        assert "NovaStep 2026" in seo["h1_elements"][0]

        # Canonical & OG tags
        assert seo["canonical_status"] == "present"
        assert seo["canonical"] == "https://novastep.com.tr"
        assert seo["open_graph"]["status"] == "complete"

        # Schema.org JSON-LD
        assert seo["schema_json_ld"]["has_organization_schema"] is True
        assert seo["schema_json_ld"]["has_product_schema"] is True

        # Search intents
        assert "Transactional" in seo["search_intents"]
        assert "Commercial" in seo["search_intents"]

    def test_ecommerce_core_web_vitals_and_performance(self, ecommerce_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        perf = res["performance_vitals"]

        # Images: WebP / AVIF modern format dominance
        imgs = perf["images"]
        assert imgs["total"] >= 3
        assert imgs["modern_format_ratio"] >= 0.75
        assert imgs["lazy_load_count"] >= 2
        assert imgs["risk_level"] == "Low"

        # Scripts: non-blocking async/defer
        scripts = perf["scripts"]
        assert scripts["blocking_render"] == 0
        assert scripts["risk_level"] == "Low"

        # Compression & overall risk
        assert perf["compression"]["minified_assets_detected"] is True
        assert perf["overall_performance_risk"] == "Low"

    def test_ecommerce_cro_and_ux_audit(self, ecommerce_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        cro = res["cro_and_ux"]

        # CTA buttons
        assert cro["cta_buttons"]["count"] >= 3
        assert cro["cta_buttons"]["status"] == "strong"

        # Trust badges
        trust = cro["trust_badges"]
        assert trust["has_ssl_badge"] is True
        assert trust["has_guarantee"] is True
        assert any("256-bit" in b or "SSL" in b for b in trust["detected"])

        # Form friction (1 input field)
        form = cro["form_friction"]
        assert form["input_field_count"] == 1
        assert form["friction_level"] == "Low"

    def test_saas_metrics_and_usd_pricing(self, saas_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(saas_html, url="https://metricpulse.io")

        # Brand & Location
        assert res["brand_info"]["brand_name"] == "MetricPulse"
        assert "MetricPulse Technologies Inc." in res["brand_info"]["company_title"]
        assert "San Francisco" in res["contact_and_location"]["city"]
        assert "USA" in res["contact_and_location"]["country"]

        # Product & USD Prices
        catalog = res["product_catalog"]
        assert "$" in catalog["currencies"]
        prices = [p["price"] for p in catalog["products"]]
        assert 49.0 in prices
        assert 199.0 in prices

        # Competitor detection
        comp = res["competitors"]
        assert "Datadog" in comp["detected_competitors"] or "NewRelic" in comp["detected_competitors"]

        # Scripts blocking render (Moderate risk)
        perf = res["performance_vitals"]
        assert perf["scripts"]["blocking_render"] >= 3
        assert perf["scripts"]["risk_level"] in ["Moderate", "High"]

    def test_corporate_seo_violations_and_high_form_friction(self, corporate_html):
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(corporate_html, url="https://atlaslojistik.com")

        # SEO Violations
        seo = res["seo_audit"]
        assert seo["title_status"] == "too_short"
        assert seo["meta_description_status"] == "missing"
        assert seo["h1_status"] == "multiple"
        assert seo["h1_count"] == 2
        assert seo["canonical_status"] == "missing"

        # Performance: Legacy JPG/PNG images
        perf = res["performance_vitals"]
        assert perf["images"]["modern_format_count"] == 0
        assert perf["images"]["risk_level"] == "High"

        # CRO: High form friction (10 fields)
        cro = res["cro_and_ux"]
        assert cro["form_friction"]["input_field_count"] >= 9
        assert cro["form_friction"]["friction_level"] == "High"


# =====================================================================
# 2. CAMPAIGNARCHITECT TESTS
# =====================================================================

class TestCampaignArchitect:
    """Test CampaignArchitect relational campaigns and multi-channel ad copy generation."""

    def test_bogo_relational_campaign_generation(self, ecommerce_html):
        analyzer = URLAnalyzer()
        analysis = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        architect = CampaignArchitect()

        campaigns = architect.generate_relational_campaigns(analysis)
        bogo = campaigns["bogo"]

        assert bogo["mechanic"] == "X alana Y bedava"
        assert "Hakiki Deri Klasik Ayakkabı" in bogo["primary_product"]
        assert "Deri Minimalist Cüzdan" in bogo["free_product"]
        assert "Hediye" in bogo["name"] or "Bedava" in bogo["name"]
        assert len(bogo["margin_impact"]) > 0
        assert len(bogo["slogan"]) > 0

    def test_cross_discount_relational_campaign_generation(self, ecommerce_html):
        analyzer = URLAnalyzer()
        analysis = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        architect = CampaignArchitect()

        campaigns = architect.generate_relational_campaigns(analysis)
        cross = campaigns["cross_discount"]

        assert "X alana Y %10 indirimli" in cross["mechanic"]
        assert cross["discount_percent"] == 10
        assert "Hakiki Deri Klasik Ayakkabı" in cross["primary_product"]
        assert "Deri Minimalist Cüzdan" in cross["discounted_product"]
        assert len(cross["promotional_angle"]) > 0
        assert "%10" in cross["bundled_savings"]

    def test_cart_threshold_incentive_generation(self, ecommerce_html):
        analyzer = URLAnalyzer()
        analysis = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        architect = CampaignArchitect()

        campaigns = architect.generate_relational_campaigns(analysis)
        thresh = campaigns["cart_threshold"]

        assert "kargo bedava" in thresh["mechanic"]
        assert thresh["threshold_amount"] > analysis["product_catalog"]["average_price"]
        assert thresh["currency"] == "₺"
        assert "Kargo" in thresh["slogan"]
        assert "aov" in thresh["estimated_aov_lift"].lower() or "sepet" in thresh["estimated_aov_lift"].lower()

    def test_google_search_ads_character_limits_and_negatives(self, ecommerce_html):
        analyzer = URLAnalyzer()
        analysis = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        architect = CampaignArchitect()

        plans = architect.generate_multichannel_ad_plans(analysis)
        g_ads = plans["google_search_ads"]

        assert g_ads["ad_type"] == "Responsive Search Ads (RSA)"
        assert len(g_ads["headlines"]) >= 5
        # Strictly verify Google Ads headline limit: <= 30 chars
        for h in g_ads["headlines"]:
            assert len(h) <= 30, f"Headline '{h}' exceeds 30 characters ({len(h)})"

        assert len(g_ads["descriptions"]) >= 3
        # Strictly verify Google Ads description limit: <= 90 chars
        for d in g_ads["descriptions"]:
            assert len(d) <= 90, f"Description '{d}' exceeds 90 characters ({len(d)})"

        # Verify negative keywords
        assert len(g_ads["negative_keywords"]) >= 10
        assert "ücretsiz" in g_ads["negative_keywords"]
        assert "crack" in g_ads["negative_keywords"]
        assert "bedava" in g_ads["negative_keywords"]

    def test_meta_ads_hook_carousel_and_ugc_storyboard(self, ecommerce_html):
        analyzer = URLAnalyzer()
        analysis = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        architect = CampaignArchitect()

        plans = architect.generate_multichannel_ad_plans(analysis)
        meta = plans["meta_ads"]

        # Hook
        assert len(meta["hook"]) > 20
        assert "NovaStep" in meta["hook"]

        # Carousel cards
        assert len(meta["carousel_cards"]) >= 3
        for card in meta["carousel_cards"]:
            assert "card_number" in card
            assert "headline" in card
            assert "caption" in card
            assert "cta" in card
            assert len(card["headline"]) <= 40

        # UGC 5-stage scenario
        ugc = meta["ugc_scenario"]
        assert "hook_0_3s" in ugc
        assert "problem_3_8s" in ugc
        assert "solution_8_15s" in ugc
        assert "demo_15_25s" in ugc
        assert "cta_25_30s" in ugc
        assert "NovaStep" in ugc["solution_8_15s"]

    def test_tiktok_reels_ads_hook_and_trend_beats(self, ecommerce_html):
        analyzer = URLAnalyzer()
        analysis = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        architect = CampaignArchitect()

        plans = architect.generate_multichannel_ad_plans(analysis)
        tiktok = plans["tiktok_reels_ads"]

        assert "POV:" in tiktok["hook"]
        assert len(tiktok["trend_concept"]) > 10
        assert len(tiktok["script_breakdown"]) >= 3
        for beat in tiktok["script_breakdown"]:
            assert "timing" in beat
            assert "visual" in beat
            assert "audio" in beat
        assert len(tiktok["cta"]) > 0

    def test_campaign_architect_full_package(self, ecommerce_html):
        analyzer = URLAnalyzer()
        analysis = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")
        architect = CampaignArchitect()

        pkg = architect.generate_full_package(analysis)
        assert pkg["brand"] == "NovaStep"
        assert "bogo" in pkg["relational_campaigns"]
        assert "google_search_ads" in pkg["multichannel_ad_plans"]


# =====================================================================
# 3. AGENCY SOLDIER CLI TESTS
# =====================================================================

class TestAgencySoldierCLI:
    """Test AgencySoldier end-to-end execution, JSON and Markdown reporting."""

    def test_offline_html_execution(self, tmp_path, ecommerce_html):
        html_file = tmp_path / "offline_shop.html"
        html_file.write_text(ecommerce_html, encoding="utf-8")

        soldier = AgencySoldier()
        result = soldier.run(
            offline_html_path=str(html_file),
            url="https://novastep.com.tr"
        )

        assert result["metadata"]["mode"] == "offline"
        assert result["metadata"]["engine"] == "MediaAgencySoldier"
        assert result["analysis"]["brand_info"]["brand_name"] == "NovaStep"
        assert "bogo" in result["campaigns"]
        assert "google_search_ads" in result["ad_plans"]

    def test_json_output_verification(self, tmp_path, ecommerce_html):
        html_file = tmp_path / "offline_shop.html"
        html_file.write_text(ecommerce_html, encoding="utf-8")
        json_out = tmp_path / "audit_report.json"

        soldier = AgencySoldier()
        exit_code = soldier.main([
            "--offline-html", str(html_file),
            "--url", "https://novastep.com.tr",
            "--output-json", str(json_out)
        ])

        assert exit_code == 0
        assert json_out.exists()

        parsed = json.loads(json_out.read_text(encoding="utf-8"))
        assert "analysis" in parsed
        assert "campaigns" in parsed
        assert "ad_plans" in parsed
        assert parsed["analysis"]["brand_info"]["brand_name"] == "NovaStep"
        assert parsed["campaigns"]["bogo"]["mechanic"] == "X alana Y bedava"
        assert len(parsed["ad_plans"]["google_search_ads"]["headlines"]) >= 5

    def test_markdown_report_verification(self, tmp_path, ecommerce_html):
        html_file = tmp_path / "offline_shop.html"
        html_file.write_text(ecommerce_html, encoding="utf-8")
        md_out = tmp_path / "audit_report.md"

        soldier = AgencySoldier()
        exit_code = soldier.main([
            "--offline-html", str(html_file),
            "--url", "https://novastep.com.tr",
            "--output-md", str(md_out)
        ])

        assert exit_code == 0
        assert md_out.exists()

        content = md_out.read_text(encoding="utf-8")
        # Verify key Markdown sections
        assert "# 🛡️ Medya Ajansı Askeri - Kapsamlı Denetim ve Büyüme Raporu: NovaStep" in content
        assert "## 1. 🏢 Marka & Fiziksel Lokasyon Özeti" in content
        assert "## 2. 🛍️ Ürün Kataloğu ve Pazar Konumlandırması" in content
        assert "## 3. 🔍 SEO & Core Web Vitals Skorkartı" in content
        assert "## 4. 🎯 CRO & Kullanıcı Deneyimi (UX)" in content
        assert "## 5. 🚀 İlişkisel Büyüme Kampanyaları" in content
        assert "BOGO (1 Alana 1 Bedava)" in content
        assert "X alana Y bedava" in content
        assert "X alana Y %10 indirimli" in content
        assert "kargo bedava" in content
        assert "## 6. 📱 Çok Kanallı Reklam Planları" in content
        assert "Responsive Search Ads (RSA)" in content
        assert "UGC Video Akışı" in content
        assert "TikTok / Reels Kısa Video Planı" in content


# =====================================================================
# 4. MEDIAAGENCYSOLDIERENGINE (BRIDGE) TESTS
# =====================================================================

class TestMediaAgencySoldierEngine:
    """Test bridge integration into Entropy AI core architecture."""

    def test_engine_offline_analysis(self, tmp_path, ecommerce_html):
        html_file = tmp_path / "shop.html"
        html_file.write_text(ecommerce_html, encoding="utf-8")

        engine = MediaAgencySoldierEngine(cache_dir=tmp_path / "reports")
        analysis = engine.analyze_offline_html(html_file, url="https://novastep.com.tr")

        assert analysis["brand_info"]["brand_name"] == "NovaStep"
        assert analysis["product_catalog"]["count"] >= 3
        assert analysis["seo_audit"]["h1_status"] == "optimal"

    def test_engine_campaign_package(self, ecommerce_html):
        engine = MediaAgencySoldierEngine()
        analyzer = URLAnalyzer()
        analysis = analyzer.analyze_html(ecommerce_html, url="https://novastep.com.tr")

        pkg = engine.generate_campaign_package(analysis)
        assert pkg["brand"] == "NovaStep"
        assert "bogo" in pkg["relational_campaigns"]
        assert "cross_discount" in pkg["relational_campaigns"]
        assert "cart_threshold" in pkg["relational_campaigns"]
        assert "google_search_ads" in pkg["multichannel_ad_plans"]

    def test_engine_run_full_audit(self, tmp_path, ecommerce_html):
        html_file = tmp_path / "shop.html"
        html_file.write_text(ecommerce_html, encoding="utf-8")
        out_md = tmp_path / "export_audit.md"
        out_json = tmp_path / "export_audit.json"

        engine = MediaAgencySoldierEngine(cache_dir=tmp_path / "cache")
        full_res = engine.run_full_audit(
            source=html_file,
            is_offline=True,
            export_md=out_md,
            export_json=out_json
        )

        assert "markdown_report" in full_res
        assert out_md.exists()
        assert out_json.exists()
        assert full_res["analysis"]["brand_info"]["brand_name"] == "NovaStep"

    def test_engine_event_bus_emission(self, tmp_path, ecommerce_html):
        html_file = tmp_path / "shop.html"
        html_file.write_text(ecommerce_html, encoding="utf-8")

        emitted_messages = []

        def on_terminal_output(msg: str):
            emitted_messages.append(msg)

        bus.terminal_output_received.connect(on_terminal_output)
        try:
            engine = MediaAgencySoldierEngine(cache_dir=tmp_path / "cache")
            engine.run_full_audit(html_file, is_offline=True)
            assert len(emitted_messages) >= 1
            assert any("Medya Motoru" in m for m in emitted_messages)
        finally:
            bus.terminal_output_received.disconnect(on_terminal_output)

    def test_skill_manager_discovers_media_agency_soldier(self):
        mgr = SkillManager()
        skills = mgr.list_skills()
        skill_names = [s.name for s in skills]

        assert "media-agency-soldier" in skill_names
        soldier_skill = next(s for s in skills if s.name == "media-agency-soldier")
        assert soldier_skill.version == "1.0.0"
        assert "marketing" in soldier_skill.tags or "seo" in soldier_skill.tags
        assert len(soldier_skill.scripts) >= 1
        script_names = [sc["name"] for sc in soldier_skill.scripts]
        assert "soldier.py" in script_names or "agency_soldier.py" in script_names


# =====================================================================
# 5. EDGE CASES & ROBUSTNESS TESTS
# =====================================================================

class TestEdgeCasesAndInvariants:
    """Rigorous boundary and robustness checks."""

    def test_url_analyzer_missing_h1_and_empty_page(self):
        html = "<html><head><title>Minimal</title></head><body><p>No headings</p></body></html>"
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(html, url="https://minimal.test")
        seo = res["seo_audit"]

        assert seo["h1_status"] == "missing"
        assert seo["h1_count"] == 0
        assert seo["canonical_status"] == "missing"
        assert res["cro_and_ux"]["form_friction"]["friction_level"] == "Low"

    def test_url_analyzer_euro_currency_and_pricing(self):
        html = """<html><body>
            <h1>European Luxury Goods</h1>
            <div class="product">
                <h3>Leather Wallet</h3>
                <span class="price">€89.00</span>
            </div>
            <div class="product">
                <h3>Travel Bag</h3>
                <span class="price">€249.00</span>
            </div>
        </body></html>"""
        analyzer = URLAnalyzer()
        res = analyzer.analyze_html(html, url="https://euroshop.eu")
        catalog = res["product_catalog"]

        assert "€" in catalog["currencies"]
        prices = [p["price"] for p in catalog["products"]]
        assert 89.0 in prices
        assert 249.0 in prices

    def test_agency_soldier_cli_brand_override(self, tmp_path, ecommerce_html):
        html_file = tmp_path / "shop.html"
        html_file.write_text(ecommerce_html, encoding="utf-8")
        out_json = tmp_path / "override.json"

        soldier = AgencySoldier()
        code = soldier.main([
            "--offline-html", str(html_file),
            "--brand", "SuperBrand Özel",
            "--output-json", str(out_json)
        ])

        assert code == 0
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert data["analysis"]["brand_info"]["brand_name"] == "SuperBrand Özel"

    def test_agency_soldier_file_not_found_raises(self):
        soldier = AgencySoldier()
        with pytest.raises(FileNotFoundError):
            soldier.run(offline_html_path="non_existent_file_99999.html")

    def test_campaign_architect_rsa_invariants_under_long_inputs(self):
        long_brand = "BuCokUzunBirMarkaAdiVeKurumsalHoldingUnvanidirGercekten123456789"
        long_product = "AsiriDerecedeUzunBirUrunAdiVeModelNumarasiOzellikleri987654321000"
        dummy_analysis = {
            "brand_info": {"brand_name": long_brand},
            "product_catalog": {
                "products": [{"name": long_product, "price": 1200.0}],
                "currencies": ["₺"],
                "average_price": 1200.0
            }
        }
        architect = CampaignArchitect()
        plans = architect.generate_multichannel_ad_plans(dummy_analysis)
        rsa = plans["google_search_ads"]

        # Invariant 1: All headlines MUST be <= 30 characters
        for h in rsa["headlines"]:
            assert len(h) <= 30, f"Headline '{h}' ({len(h)} chars) exceeds 30 characters!"

        # Invariant 2: All descriptions MUST be <= 90 characters
        for d in rsa["descriptions"]:
            assert len(d) <= 90, f"Description '{d}' ({len(d)} chars) exceeds 90 characters!"

