"""
Deep SEO & MarTech Tracking Auditor.
Audits:
1. MarTech & Analytics Tracking Tags (GA4, GTM, Meta Pixel & CAPI, TikTok, Clarity, Hotjar, Klaviyo).
2. Search Intent Classification (Informational, Commercial, Navigational, Transactional).
3. Heading Hierarchy (H1-H6 structure & integrity).
4. Image SEO & Accessibility (Alt text, modern formats, dimensions).
5. Internal & External Link Architecture.
6. Industry Tool Gaps & Agency Recommendations (Ahrefs, Semrush, Screaming Frog, GSC, Meta Ad Library).
"""

import re
import urllib.parse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TrackingTagDetection(BaseModel):
    tag_name: str
    detected: bool
    details: str
    tag_id: Optional[str] = None
    priority: str = "P1"


class SearchIntentScore(BaseModel):
    dominant_intent: str = Field(..., description="Informational | Commercial | Navigational | Transactional")
    scores: Dict[str, float] = Field(default_factory=dict)
    matched_keywords: Dict[str, List[str]] = Field(default_factory=dict)
    recommended_page_role: str = ""


class SchemaOrgAuditResult(BaseModel):
    has_json_ld: bool
    schema_types_detected: List[str] = Field(default_factory=list)
    detected_schemas_detail: List[Dict[str, Any]] = Field(default_factory=list)
    valid_product_schema: bool = False
    missing_product_fields: List[str] = Field(default_factory=list)
    valid_organization_schema: bool = False
    has_breadcrumbs: bool = False
    has_faq_page: bool = False
    schema_health_score: int = 0
    rich_results_eligibility: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class CoreWebVitalsAuditResult(BaseModel):
    cwv_score: int
    lcp_risk: str  # Good | Needs Improvement | Poor
    inp_risk: str  # Good | Needs Improvement | Poor
    cls_risk: str  # Good | Needs Improvement | Poor
    render_blocking_scripts_count: int
    render_blocking_stylesheets_count: int
    missing_lazy_load_count: int
    missing_dimensions_img_count: int
    missing_font_swap_count: int
    viewport_tag_found: bool
    estimated_dom_depth: int
    diagnostic_checklist: List[str] = Field(default_factory=list)


class IndexabilityAuditResult(BaseModel):
    indexability_score: int
    is_indexable: bool
    meta_robots: Optional[str] = None
    noindex_detected: bool = False
    nofollow_detected: bool = False
    canonical_url: Optional[str] = None
    canonical_status: str  # Valid Self-Referencing | Missing | Cross-Domain | Unknown
    has_og_title: bool = False
    has_og_image: bool = False
    has_og_description: bool = False
    has_twitter_card: bool = False
    hreflang_languages: List[str] = Field(default_factory=list)
    sitemap_link_detected: bool = False
    warnings: List[str] = Field(default_factory=list)


class SemanticClusterAuditResult(BaseModel):
    total_words: int
    text_to_html_ratio_pct: float
    dominant_topics: List[Dict[str, Any]] = Field(default_factory=list)
    top_ngrams: Dict[str, List[str]] = Field(default_factory=dict)
    keyword_stuffing_detected: bool = False
    keyword_dilution_detected: bool = False
    recommended_pillar_concept: str = ""
    proposed_cluster_articles: List[str] = Field(default_factory=list)


class SecurityAndPrivacyAuditResult(BaseModel):
    security_score: int
    has_csp: bool
    csp_details: str
    has_hsts: bool
    has_x_frame_options: bool
    has_referrer_policy: bool
    consent_mode_v2_detected: bool
    consent_mode_details: str
    cookie_banner_detected: bool
    kvkk_gdpr_detected: bool
    security_warnings: List[str] = Field(default_factory=list)


class ECommerceCROScorecard(BaseModel):
    cro_score: int
    friction_tier: str  # OPTIMAL | MODERATE | SEVERE_FRICTION
    sticky_cta_detected: bool
    express_checkout_detected: bool
    express_methods: List[str] = Field(default_factory=list)
    guest_checkout_accessible: bool
    checkout_form_input_count: int
    trust_badges_detected: List[str] = Field(default_factory=list)
    friction_flags: List[str] = Field(default_factory=list)
    actionable_recommendations: List[str] = Field(default_factory=list)


class SERPFeatureOpportunityAuditResult(BaseModel):
    featured_snippet_readiness: str  # HIGH | MODERATE | LOW
    featured_snippet_candidates: List[str] = Field(default_factory=list)
    paa_question_count: int
    paa_questions_detected: List[str] = Field(default_factory=list)
    rich_merchant_readiness: str  # READY | PARTIAL | NOT_ELIGIBLE
    sitelinks_searchbox_eligible: bool
    serp_opportunity_score: int
    optimization_roadmap: List[str] = Field(default_factory=list)


TrackingTagDetection.model_rebuild()
SearchIntentScore.model_rebuild()
SchemaOrgAuditResult.model_rebuild()
CoreWebVitalsAuditResult.model_rebuild()
IndexabilityAuditResult.model_rebuild()
SemanticClusterAuditResult.model_rebuild()
SecurityAndPrivacyAuditResult.model_rebuild()
ECommerceCROScorecard.model_rebuild()
SERPFeatureOpportunityAuditResult.model_rebuild()


class SEOAndMarTechAuditor:
    """Specialist auditor analyzing deep technical SEO, search intent, and tracking infrastructure."""

    # Intent Lexicons (Turkish & English)
    INTENT_TRIGGERS = {
        "Informational": [
            "nasıl", "nedir", "neden", "rehber", "ipuçları", "tarihçe", "kılavuz",
            "how to", "what is", "why", "guide", "tutorial", "tips", "hakkında", "taktikleri"
        ],
        "Commercial": [
            "en iyi", "karşılaştırma", "tavsiye", "vs", "inceleme", "hangisi", "öneri",
            "best", "comparison", "review", "top 10", "vs", "alternative", "değerlendirme"
        ],
        "Navigational": [
            "giriş yap", "üye ol", "iletişim", "müşteri hizmetleri", "hesabım", "adres",
            "login", "sign in", "contact", "support", "official", "resmi web sitesi"
        ],
        "Transactional": [
            "satın al", "fiyat", "fiyatları", "sipariş", "indirim", "kampanya", "sepet",
            "ücretsiz kargo", "buy", "price", "order", "discount", "deal", "add to cart", "ödeme"
        ]
    }

    AGENCY_TOOL_CATALOG = {
        "screaming_frog": {
            "name": "Screaming Frog SEO Spider",
            "primary_role": "Derin Teknik Web Taraması (URL Düzeyi)",
            "use_case": "404/301 yönlendirme zincirleri, mükerrer canonical, robots.txt ve hreflang denetimi."
        },
        "ahrefs": {
            "name": "Ahrefs Site Audit & Explorer",
            "primary_role": "Backlink, DR ve Keyword Gap Analizi",
            "use_case": "Rakip pazar payı, arama hacmi trendleri ve kayıp backlink tespiti."
        },
        "semrush": {
            "name": "Semrush Competitive Intelligence",
            "primary_role": "Ücretli Reklam ve SERP Karşılaştırması",
            "use_case": "Rakip Google Ads bütçeleri, reklam kopyaları ve anahtar kelime zorluğu."
        },
        "google_search_console": {
            "name": "Google Search Console (GSC)",
            "primary_role": "Arama Motoru Gerçeklik ve Dizin Kapsamı",
            "use_case": "Tıklama, ortalama konum, tarama bütçesi ve dizinleme (index) doğrulama."
        },
        "pagespeed_insights": {
            "name": "Google PageSpeed Insights & CrUX",
            "primary_role": "Core Web Vitals Saha Testleri",
            "use_case": "LCP, INP, CLS ve sunucu yanıt süresi (TTFB) teşhisi."
        },
        "meta_ad_library": {
            "name": "Meta Ad Library & Ads Transparency",
            "primary_role": "Rakip Reklam Kreatif İstihbaratı",
            "use_case": "Rakiplerin en uzun süredir yayında olan kazanan kreatifleri ve kancaları."
        }
    }

    def detect_tracking_tags(self, html: str) -> Dict[str, Any]:
        """
        Scans HTML markup for essential MarTech marketing tracking tags and pixels.
        """
        tags: List[TrackingTagDetection] = []
        html_lower = html.lower()

        # 1. Google Analytics 4 (GA4)
        ga4_match = re.search(r'\b(G-[A-Z0-9]{8,12})\b', html)
        ga4_detected = bool(ga4_match) or ("googletagmanager.com/gtag/js" in html_lower and "gtag('config'" in html_lower)
        tags.append(TrackingTagDetection(
            tag_name="Google Analytics 4 (GA4)",
            detected=ga4_detected,
            details=f"GA4 Takip Kimliği: {ga4_match.group(1)}" if ga4_match else ("GA4 scripti mevcut" if ga4_detected else "Bulunamadı (P0 - Kritik Veri Kaybı)"),
            tag_id=ga4_match.group(1) if ga4_match else None,
            priority="P0"
        ))

        # 2. Google Tag Manager (GTM)
        gtm_match = re.search(r'\b(GTM-[A-Z0-9]{6,10})\b', html)
        gtm_detected = bool(gtm_match) or ("googletagmanager.com/gtm.js" in html_lower)
        tags.append(TrackingTagDetection(
            tag_name="Google Tag Manager (GTM)",
            detected=gtm_detected,
            details=f"GTM Kapsayıcı: {gtm_match.group(1)}" if gtm_match else ("GTM mevcut" if gtm_detected else "Bulunamadı (P1 - Tavsiye Edilir)"),
            tag_id=gtm_match.group(1) if gtm_match else None,
            priority="P1"
        ))

        # 3. Meta Pixel & CAPI
        meta_match = re.search(r"fbq\s*\(\s*['\"]init['\"]\s*,\s*['\"](\d{12,18})['\"]", html)
        meta_detected = bool(meta_match) or ("connect.facebook.net" in html_lower) or ("fbq(" in html_lower)
        tags.append(TrackingTagDetection(
            tag_name="Meta Pixel & CAPI",
            detected=meta_detected,
            details=f"Pixel ID: {meta_match.group(1)}" if meta_match else ("Meta Pixel scripti mevcut" if meta_detected else "Bulunamadı (P0 - Reklam Algoritması Optimize Olamaz)"),
            tag_id=meta_match.group(1) if meta_match else None,
            priority="P0"
        ))

        # 4. TikTok Pixel
        tiktok_match = re.search(r"ttq\.load\s*\(\s*['\"]([A-Z0-9]{15,25})['\"]", html)
        tiktok_detected = bool(tiktok_match) or ("analytics.tiktok.com" in html_lower) or ("ttq.load" in html_lower)
        tags.append(TrackingTagDetection(
            tag_name="TikTok Pixel",
            detected=tiktok_detected,
            details=f"TikTok Pixel ID: {tiktok_match.group(1)}" if tiktok_match else ("TikTok Pixel mevcut" if tiktok_detected else "Bulunamadı (P2)"),
            tag_id=tiktok_match.group(1) if tiktok_match else None,
            priority="P2"
        ))

        # 5. Behavior & Heatmaps (Clarity or Hotjar)
        clarity_detected = "clarity.ms/tag" in html_lower or "clarity(" in html_lower
        hotjar_detected = "static.hotjar.com" in html_lower or "_hjsettings" in html_lower
        tags.append(TrackingTagDetection(
            tag_name="Davranış & Isı Haritası (Clarity / Hotjar)",
            detected=clarity_detected or hotjar_detected,
            details="Microsoft Clarity tespit edildi" if clarity_detected else ("Hotjar tespit edildi" if hotjar_detected else "Kullanıcı davranış ısı haritası eksik (P2)"),
            priority="P2"
        ))

        # 6. Retention / Email Marketing (Klaviyo / Omnisend)
        klaviyo_detected = "klaviyo.com" in html_lower or "_learnq" in html_lower
        tags.append(TrackingTagDetection(
            tag_name="Retention / E-posta Pazarlama (Klaviyo)",
            detected=klaviyo_detected,
            details="Klaviyo entegrasyonu mevcut" if klaviyo_detected else "Klaviyo retention altyapısı tespit edilemedi (P1)",
            priority="P1"
        ))

        detected_count = sum(1 for t in tags if t.detected)
        health_score = round((detected_count / len(tags)) * 100.0, 1)

        critical_missing = [t.tag_name for t in tags if not t.detected and t.priority == "P0"]

        return {
            "tags": [t.model_dump() for t in tags],
            "detected_count": detected_count,
            "total_checked": len(tags),
            "martech_health_score": health_score,
            "critical_missing_p0": critical_missing,
            "ready_for_paid_traffic": len(critical_missing) == 0
        }

    def analyze_search_intents(
        self,
        html: str,
        title: str = "",
        meta_desc: str = ""
    ) -> SearchIntentScore:
        """
        Classifies page text into search intents (Informational, Commercial, Navigational, Transactional).
        """
        # Clean text
        clean_text = re.sub(r'<script.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<style.*?</style>', ' ', clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        text_lower = f"{title} {meta_desc} {clean_text}".lower()

        scores: Dict[str, float] = {k: 0.0 for k in self.INTENT_TRIGGERS}
        matched_words: Dict[str, List[str]] = {k: [] for k in self.INTENT_TRIGGERS}

        for intent, triggers in self.INTENT_TRIGGERS.items():
            for trig in triggers:
                count = text_lower.count(trig)
                if count > 0:
                    scores[intent] += count * (2.0 if trig in (title.lower() + meta_desc.lower()) else 1.0)
                    matched_words[intent].append(trig)

        total_score = sum(scores.values())
        normalized_scores = {}
        if total_score > 0:
            for k, v in scores.items():
                normalized_scores[k] = round((v / total_score) * 100.0, 1)
        else:
            normalized_scores = {"Transactional": 25.0, "Commercial": 25.0, "Informational": 25.0, "Navigational": 25.0}

        dominant = max(normalized_scores.items(), key=lambda x: x[1])[0]

        page_role_map = {
            "Transactional": "Kategori veya Ürün Detay Sayfası (Doğrudan Satın Alma & Sepet Dönüşümü)",
            "Commercial": "Karşılaştırma veya İnceleme Sayfası (Değerlendirme & Güven İnşası)",
            "Informational": "Eğitici Blog veya Kılavuz (Üst Huni / Organik Kitle Toplama)",
            "Navigational": "Ana Sayfa veya Kurumsal Künye (Doğrudan Marka Girişi)"
        }

        return SearchIntentScore(
            dominant_intent=dominant,
            scores=normalized_scores,
            matched_keywords={k: v[:5] for k, v in matched_words.items()},
            recommended_page_role=page_role_map.get(dominant, "Genel Web Varlığı")
        )

    def analyze_heading_hierarchy(self, html: str) -> Dict[str, Any]:
        """
        Validates heading tag hierarchy: H1 singularity, H2-H3 presence and logical nesting.
        """
        h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', html, flags=re.DOTALL | re.IGNORECASE)
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', html, flags=re.DOTALL | re.IGNORECASE)
        h3s = re.findall(r'<h3[^>]*>(.*?)</h3>', html, flags=re.DOTALL | re.IGNORECASE)

        clean_h1s = [re.sub(r'<[^>]+>', '', h).strip() for h in h1s if re.sub(r'<[^>]+>', '', h).strip()]
        clean_h2s = [re.sub(r'<[^>]+>', '', h).strip() for h in h2s if re.sub(r'<[^>]+>', '', h).strip()]
        clean_h3s = [re.sub(r'<[^>]+>', '', h).strip() for h in h3s if re.sub(r'<[^>]+>', '', h).strip()]

        if len(clean_h1s) == 1:
            h1_status = "optimal"
        elif len(clean_h1s) == 0:
            h1_status = "missing"
        else:
            h1_status = "multiple"

        violations = []
        if h1_status == "missing":
            violations.append("H1 başlığı bulunamadı; sayfanın birincil odak konusu belirsiz.")
        elif h1_status == "multiple":
            violations.append(f"Birden fazla H1 başlığı bulundu ({len(clean_h1s)} adet); sayfa tekil bir H1'e indirgenmelidir.")

        if len(clean_h3s) > 0 and len(clean_h2s) == 0:
            violations.append("H2 başlığı olmadan H3 kullanılmış; başlık hiyerarşisi kopuk.")

        is_healthy = len(violations) == 0

        return {
            "h1_status": h1_status,
            "h1_count": len(clean_h1s),
            "h1_text": clean_h1s[0] if clean_h1s else "",
            "h2_count": len(clean_h2s),
            "h3_count": len(clean_h3s),
            "is_hierarchy_healthy": is_healthy,
            "violations": violations
        }

    def analyze_image_seo(self, html: str) -> Dict[str, Any]:
        """
        Audits image SEO, ALT attribute accessibility, and modern format usage (WebP/AVIF).
        """
        img_tags = re.findall(r'<img([^>]*)>', html, flags=re.IGNORECASE)
        total_images = len(img_tags)

        missing_alt = 0
        empty_alt = 0
        modern_formats = 0

        for attrs in img_tags:
            # Check ALT
            alt_m = re.search(r'alt=["\'](.*?)["\']', attrs, flags=re.IGNORECASE)
            if not alt_m:
                missing_alt += 1
            elif not alt_m.group(1).strip():
                empty_alt += 1

            # Check Format
            src_m = re.search(r'src=["\'](.*?)["\']', attrs, flags=re.IGNORECASE)
            if src_m:
                src_val = src_m.group(1).lower()
                if any(ext in src_val for ext in [".webp", ".avif", ".svg"]):
                    modern_formats += 1

        modern_ratio = (modern_formats / total_images) if total_images > 0 else 1.0
        alt_compliance_ratio = ((total_images - (missing_alt + empty_alt)) / total_images) if total_images > 0 else 1.0

        score = round((modern_ratio * 50.0 + alt_compliance_ratio * 50.0), 1)

        return {
            "total_images": total_images,
            "missing_alt_count": missing_alt,
            "empty_alt_count": empty_alt,
            "valid_alt_ratio": round(alt_compliance_ratio, 2),
            "modern_formats_count": modern_formats,
            "modern_format_ratio": round(modern_ratio, 2),
            "image_seo_score": score
        }

    def analyze_links(self, html: str, base_domain: str = "") -> Dict[str, Any]:
        """
        Audits internal vs external link distribution and descriptive anchor texts.
        """
        links = re.findall(r'<a\s+([^>]*href=["\'](.*?)["\'][^>]*)>(.*?)</a>', html, flags=re.DOTALL | re.IGNORECASE)
        internal_count = 0
        external_count = 0
        generic_anchors = 0
        generic_words = {"tıkla", "buraya tıkla", "click here", "read more", "link", "devamını oku", "detay"}

        for full_attr, href, anchor_text in links:
            clean_anchor = re.sub(r'<[^>]+>', '', anchor_text).strip().lower()
            if clean_anchor in generic_words:
                generic_anchors += 1

            parsed = urllib.parse.urlparse(href)
            if not parsed.netloc or (base_domain and base_domain in parsed.netloc):
                internal_count += 1
            else:
                external_count += 1

        return {
            "total_links": len(links),
            "internal_links": internal_count,
            "external_links": external_count,
            "generic_anchor_count": generic_anchors,
            "link_equity_healthy": internal_count >= external_count
        }

    def get_recommended_agency_tools(self, gaps: List[str]) -> List[Dict[str, str]]:
        """
        Maps identified audit gaps to agency standard software tools.
        """
        recommended = []
        gaps_lower = " ".join(gaps).lower()

        # Always recommend core trio for full audits
        recommended.append(self.AGENCY_TOOL_CATALOG["screaming_frog"])
        recommended.append(self.AGENCY_TOOL_CATALOG["ahrefs"])
        recommended.append(self.AGENCY_TOOL_CATALOG["google_search_console"])

        if "lcp" in gaps_lower or "cpm" in gaps_lower or "performance" in gaps_lower or "speed" in gaps_lower:
            recommended.append(self.AGENCY_TOOL_CATALOG["pagespeed_insights"])
        if "reklam" in gaps_lower or "kreatif" in gaps_lower or "ad" in gaps_lower or "rakip" in gaps_lower:
            recommended.append(self.AGENCY_TOOL_CATALOG["meta_ad_library"])
            recommended.append(self.AGENCY_TOOL_CATALOG["semrush"])

        # Deduplicate by name
        seen = set()
        deduped = []
        for r in recommended:
            if r["name"] not in seen:
                seen.add(r["name"])
                deduped.append(r)
        return deduped

    def run_full_seo_and_martech_audit(self, html: str, url: str = "") -> Dict[str, Any]:
        """
        Comprehensive audit combining MarTech tracking, Search Intent, Headings, Images, Links, and Tools.
        """
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc or url

        # Extract title and meta desc
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.IGNORECASE | re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""

        desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, flags=re.IGNORECASE)
        if not desc_m:
            desc_m = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', html, flags=re.IGNORECASE)
        meta_desc = desc_m.group(1).strip() if desc_m else ""

        tracking = self.detect_tracking_tags(html)
        intent = self.analyze_search_intents(html, title=title, meta_desc=meta_desc)
        headings = self.analyze_heading_hierarchy(html)
        images = self.analyze_image_seo(html)
        links = self.analyze_links(html, base_domain=domain)
        schema = self.audit_schema_org(html)
        cwv = self.audit_core_web_vitals_dom(html)
        indexability = self.audit_indexability(html, url=url)
        clusters = self.audit_semantic_clusters(html)

        # Collect audit gaps
        gaps = []
        if not tracking["ready_for_paid_traffic"]:
            gaps.append("Kritik MarTech Takip Kodları Eksik (GA4 veya Meta Pixel)")
        if not headings["is_hierarchy_healthy"]:
            gaps.extend(headings["violations"])
        if images["missing_alt_count"] > 0:
            gaps.append(f"{images['missing_alt_count']} görselde ALT etiketi eksik.")
        if links["generic_anchor_count"] > 3:
            gaps.append(f"{links['generic_anchor_count']} jenerik link metni tespit edildi ('tıkla', 'buraya tıkla').")
        if not schema.valid_product_schema and schema.recommendations:
            gaps.extend(schema.recommendations)
        if cwv.diagnostic_checklist:
            gaps.extend(cwv.diagnostic_checklist)
        if indexability.warnings:
            gaps.extend(indexability.warnings)

        tool_recommendations = self.get_recommended_agency_tools(gaps)

        return {
            "martech_tracking": tracking,
            "search_intent_analysis": intent.model_dump(),
            "heading_hierarchy": headings,
            "image_seo": images,
            "links_audit": links,
            "schema_org_audit": schema.model_dump(),
            "core_web_vitals": cwv.model_dump(),
            "indexability_audit": indexability.model_dump(),
            "semantic_clusters": clusters.model_dump(),
            "audit_gaps_identified": gaps,
            "recommended_agency_tools": tool_recommendations
        }

    def audit_schema_org(self, html: str) -> SchemaOrgAuditResult:
        """
        Parses JSON-LD structured data and verifies Schema.org conformance for Product, Organization,
        LocalBusiness, FAQPage, and BreadcrumbList.
        """
        import json

        pattern = r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(pattern, html, flags=re.DOTALL | re.IGNORECASE)

        has_json_ld = len(matches) > 0
        detected_types: List[str] = []
        detected_detail: List[Dict[str, Any]] = []

        valid_product = False
        missing_product_fields: List[str] = []
        valid_org = False
        has_breadcrumbs = False
        has_faq = False
        rich_results: List[str] = []
        recs: List[str] = []

        for raw_block in matches:
            try:
                data = json.loads(raw_block.strip())
            except Exception:
                continue

            items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                schema_type = str(item.get("@type", ""))
                if schema_type:
                    detected_types.append(schema_type)
                    detected_detail.append({"type": schema_type, "keys": list(item.keys())})

                if schema_type == "Product":
                    missing = []
                    if not item.get("name"):
                        missing.append("name")
                    if not item.get("image"):
                        missing.append("image")
                    offers = item.get("offers")
                    if not offers or not isinstance(offers, dict):
                        missing.append("offers (price, priceCurrency, availability)")
                    else:
                        if not offers.get("price"):
                            missing.append("offers.price")
                        if not offers.get("priceCurrency"):
                            missing.append("offers.priceCurrency")
                        if not offers.get("availability"):
                            missing.append("offers.availability")
                    
                    if not missing:
                        valid_product = True
                        rich_results.append("Google Alışveriş Fiyat & Stok Zengin Sonucu (Product Rich Snippet)")
                    else:
                        missing_product_fields.extend(missing)

                elif schema_type in ("Organization", "LocalBusiness"):
                    if item.get("name") and (item.get("url") or item.get("logo")):
                        valid_org = True
                        rich_results.append("Google Bilgi Paneli / Kurumsal Varlık Doğrulaması (Knowledge Panel)")

                elif schema_type == "BreadcrumbList":
                    has_breadcrumbs = True
                    rich_results.append("SERP Kategori Gezinme Yolu (Breadcrumbs)")

                elif schema_type == "FAQPage":
                    has_faq = True
                    rich_results.append("Google SERP SSS Akordeon Zengin Sonucu (FAQ Rich Snippet)")

        # Calculate score
        score = 0
        if has_json_ld:
            score += 20
        if valid_product:
            score += 35
        elif "Product" in detected_types:
            score += 15
        if valid_org:
            score += 20
        if has_breadcrumbs:
            score += 15
        if has_faq:
            score += 10
        score = min(100, score)

        if not valid_product:
            if missing_product_fields:
                recs.append(f"Product şemasında eksik alanlar: {', '.join(set(missing_product_fields))}.")
            else:
                recs.append("Ürün sayfalarında Product JSON-LD şeması tanımlanmalı (Fiyat, Stok, SKU, Görsel).")
        if not valid_org:
            recs.append("Organization / LocalBusiness şeması eklenerek kurumsal itibar ve Google Harita eşleşmesi güçlendirilmeli.")
        if not has_breadcrumbs:
            recs.append("BreadcrumbList şeması eklenerek SERP tıklama oranı (CTR) artırılmalı.")

        return SchemaOrgAuditResult(
            has_json_ld=has_json_ld,
            schema_types_detected=list(set(detected_types)),
            detected_schemas_detail=detected_detail,
            valid_product_schema=valid_product,
            missing_product_fields=list(set(missing_product_fields)),
            valid_organization_schema=valid_org,
            has_breadcrumbs=has_breadcrumbs,
            has_faq_page=has_faq,
            schema_health_score=score,
            rich_results_eligibility=rich_results,
            recommendations=recs
        )

    def audit_core_web_vitals_dom(self, html: str) -> CoreWebVitalsAuditResult:
        """
        Diagnoses DOM elements for Core Web Vitals (LCP, INP, CLS) risks.
        """
        checklist = []
        score = 100

        # Viewport
        has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.IGNORECASE))
        if not has_viewport:
            score -= 25
            checklist.append("KRİTİK: Mobil Viewport meta etiketi eksik! Mobil ekranlarda bozulma yaşanır.")

        # Render-blocking scripts in head
        head_match = re.search(r'<head[^>]*>(.*?)</head>', html, re.DOTALL | re.IGNORECASE)
        head_html = head_match.group(1) if head_match else ""

        blocking_scripts = 0
        for s_tag in re.finditer(r'<script[^>]+src=[^>]*>', head_html, re.IGNORECASE):
            tag_str = s_tag.group(0).lower()
            if "defer" not in tag_str and "async" not in tag_str and "type=\"module\"" not in tag_str:
                blocking_scripts += 1
        if blocking_scripts > 2:
            score -= min(20, blocking_scripts * 5)
            checklist.append(f"LCP/INP Tehlikesi: Head içinde {blocking_scripts} adet render-blocking senkron script tespit edildi ('defer' veya 'async' eklenmeli).")

        # Render-blocking CSS
        blocking_css = len(re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', head_html, re.IGNORECASE))
        if blocking_css > 4:
            score -= 10
            checklist.append(f"Head içinde {blocking_css} adet harici CSS dosyası var; kritik CSS birleştirilmeli.")

        # Images missing lazy loading or dimensions
        img_tags = re.findall(r'<img[^>]+>', html, re.IGNORECASE)
        missing_lazy = 0
        missing_dimensions = 0
        for img in img_tags:
            img_l = img.lower()
            if 'loading="lazy"' not in img_l and "loading='lazy'" not in img_l:
                missing_lazy += 1
            has_w = 'width=' in img_l
            has_h = 'height=' in img_l
            if not (has_w and has_h):
                missing_dimensions += 1

        if missing_lazy > 3:
            score -= 10
            checklist.append(f"LCP Riski: {missing_lazy} görselde 'loading=\"lazy\"' özniteliği eksik.")
        if missing_dimensions > 2:
            score -= 15
            checklist.append(f"CLS Riski: {missing_dimensions} görselde açık 'width' ve 'height' boyutları belirtilmemiş (Layout Shift riski).")

        # Fonts display swap
        font_links = re.findall(r'<link[^>]+href=["\'][^"\']*fonts\.googleapis\.com[^"\']*["\'][^>]*>', html, re.IGNORECASE)
        missing_swap = 0
        for f in font_links:
            if "display=swap" not in f.lower():
                missing_swap += 1
        if missing_swap > 0:
            score -= 5
            checklist.append("Yazı tiplerinde 'display=swap' parametresi eksik; metin çizilmesinde FOUT/FOIT gecikmesi yaşanabilir.")

        # Estimated DOM depth
        dom_depth = len(re.findall(r'<(?:div|section|article|main)', html, re.IGNORECASE))
        est_depth = min(35, max(8, dom_depth // 15))

        # Risk assessments
        score = max(10, score)
        lcp_risk = "Good" if score >= 80 else "Needs Improvement" if score >= 55 else "Poor"
        inp_risk = "Good" if blocking_scripts <= 1 else "Needs Improvement" if blocking_scripts <= 3 else "Poor"
        cls_risk = "Good" if missing_dimensions <= 1 else "Needs Improvement" if missing_dimensions <= 5 else "Poor"

        return CoreWebVitalsAuditResult(
            cwv_score=score,
            lcp_risk=lcp_risk,
            inp_risk=inp_risk,
            cls_risk=cls_risk,
            render_blocking_scripts_count=blocking_scripts,
            render_blocking_stylesheets_count=blocking_css,
            missing_lazy_load_count=missing_lazy,
            missing_dimensions_img_count=missing_dimensions,
            missing_font_swap_count=missing_swap,
            viewport_tag_found=has_viewport,
            estimated_dom_depth=est_depth,
            diagnostic_checklist=checklist
        )

    def audit_indexability(self, html: str, url: str = "") -> IndexabilityAuditResult:
        """
        Audits meta robots, canonical URLs, OpenGraph/Twitter social cards, and hreflang.
        """
        score = 100
        warnings = []

        # Meta robots
        robots_m = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'](.*?)["\']', html, re.IGNORECASE)
        if not robots_m:
            robots_m = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']robots["\']', html, re.IGNORECASE)
        robots_content = robots_m.group(1).lower() if robots_m else ""

        noindex = "noindex" in robots_content
        nofollow = "nofollow" in robots_content
        is_indexable = not noindex

        if noindex:
            score -= 50
            warnings.append("KRİTİK: Sayfada 'noindex' etiketi var! Google arama sonuçlarında görünmez.")

        # Canonical
        can_m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']', html, re.IGNORECASE)
        canonical_url = can_m.group(1).strip() if can_m else None
        if not canonical_url:
            score -= 15
            can_status = "Missing"
            warnings.append("Canonical etiketi bulunamadı; mükerrer içerik (duplicate content) cezası riski.")
        elif url and canonical_url.split("?")[0].rstrip("/") == url.split("?")[0].rstrip("/"):
            can_status = "Valid Self-Referencing"
        else:
            can_status = "Cross-Domain / Parameterized"

        # OpenGraph
        og_title = bool(re.search(r'<meta[^>]+property=["\']og:title["\']', html, re.IGNORECASE))
        og_image = bool(re.search(r'<meta[^>]+property=["\']og:image["\']', html, re.IGNORECASE))
        og_desc = bool(re.search(r'<meta[^>]+property=["\']og:description["\']', html, re.IGNORECASE))
        tw_card = bool(re.search(r'<meta[^>]+name=["\']twitter:card["\']', html, re.IGNORECASE))

        if not og_image:
            score -= 10
            warnings.append("og:image etiketi eksik; sosyal medya paylaşımlarında ve WhatsApp önizlemelerinde görsel çıkmaz.")

        # Hreflang
        hreflangs = re.findall(r'<link[^>]+hreflang=["\'](.*?)["\']', html, re.IGNORECASE)

        # Sitemap
        has_sitemap = bool(re.search(r'sitemap\.xml', html, re.IGNORECASE))

        return IndexabilityAuditResult(
            indexability_score=max(10, score),
            is_indexable=is_indexable,
            meta_robots=robots_content or None,
            noindex_detected=noindex,
            nofollow_detected=nofollow,
            canonical_url=canonical_url,
            canonical_status=can_status,
            has_og_title=og_title,
            has_og_image=og_image,
            has_og_description=og_desc,
            has_twitter_card=tw_card,
            hreflang_languages=list(set(hreflangs)),
            sitemap_link_detected=has_sitemap,
            warnings=warnings
        )

    def audit_semantic_clusters(self, html: str) -> SemanticClusterAuditResult:
        """
        Analyzes content density, top 1-gram & 2-gram keywords, topic clusters, and keyword stuffing risks.
        """
        clean_text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<style[^>]*>.*?</style>', ' ', clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        words = [w.lower() for w in re.findall(r'[a-zA-ZçğıöşüÇĞİÖŞÜ]{3,}', clean_text)]
        total_words = len(words)

        text_ratio = round((len(clean_text.strip()) / max(1, len(html))) * 100.0, 2)

        stopwords = {
            "bir", "ve", "ile", "için", "olan", "bu", "şu", "da", "de", "daha", "en", "çok",
            "kadar", "gibi", "olarak", "the", "and", "for", "with", "that", "this", "from", "are"
        }
        filtered_words = [w for w in words if w not in stopwords]

        from collections import Counter
        counts = Counter(filtered_words)
        top_1grams = [w for w, c in counts.most_common(5)]

        # 2-grams
        bigrams = [f"{filtered_words[i]} {filtered_words[i+1]}" for i in range(len(filtered_words) - 1)]
        b_counts = Counter(bigrams)
        top_2grams = [b for b, c in b_counts.most_common(5)]

        stuffing = False
        if counts and total_words > 50:
            top_freq = counts.most_common(1)[0][1]
            if (top_freq / total_words * 100.0) > 4.0:
                stuffing = True

        dilution = total_words < 120

        anchor_word = top_1grams[0].capitalize() if top_1grams else "Ürün/Kategori"
        pillar = f"Kapsamlı {anchor_word} Rehberi ve Satın Alma Standartları (Pillar Content)"
        clusters = [
            f"{anchor_word} Seçerken Dikkat Edilmesi Gereken 7 Kritik Unsur",
            f"En İyi {anchor_word} Modelleri ve Kullanıcı Deneyimi İncelemesi",
            f"{anchor_word} Bakımı, Ömrünü Uzatma ve Doğru Kullanım İpuçları"
        ]

        return SemanticClusterAuditResult(
            total_words=total_words,
            text_to_html_ratio_pct=text_ratio,
            dominant_topics=[{"term": t, "count": counts[t]} for t in top_1grams],
            top_ngrams={"unigrams": top_1grams, "bigrams": top_2grams},
            keyword_stuffing_detected=stuffing,
            keyword_dilution_detected=dilution,
            recommended_pillar_concept=pillar,
            proposed_cluster_articles=clusters
        )

    def audit_security_and_privacy(
        self,
        html: str,
        headers: Optional[Dict[str, str]] = None
    ) -> SecurityAndPrivacyAuditResult:
        """
        Audits HTTP security headers, Google Consent Mode v2, and privacy/compliance flags.
        """
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}
        html_lower = html.lower()
        warnings = []
        score = 100

        # 1. Content Security Policy (CSP)
        has_csp = "content-security-policy" in hdrs or bool(re.search(r'<meta[^>]+http-equiv=[\"\'\s]*content-security-policy', html, re.I))
        csp_details = "CSP başlığı aktif (XSS ve enjeksiyon koruması mevcut)." if has_csp else "CSP (Content-Security-Policy) eksik; üçüncü taraf script enjeksiyonuna açık."
        if not has_csp:
            score -= 15
            warnings.append("Güvenlik: Content-Security-Policy (CSP) başlığı tanımlanmamış.")

        # 2. Strict-Transport-Security (HSTS)
        has_hsts = "strict-transport-security" in hdrs
        if not has_hsts:
            score -= 15
            warnings.append("SSL/TLS: HSTS başlığı eksik; HTTPS zorunlu kılınmalı (max-age=31536000).")

        # 3. X-Frame-Options (Clickjacking defense)
        has_x_frame = "x-frame-options" in hdrs or bool(re.search(r'<meta[^>]+http-equiv=[\"\'\s]*x-frame-options', html, re.I))
        if not has_x_frame:
            score -= 10
            warnings.append("Clickjacking: X-Frame-Options başlığı eksik (DENY veya SAMEORIGIN önerilir).")

        # 4. Referrer-Policy
        has_ref_policy = "referrer-policy" in hdrs or bool(re.search(r'<meta[^>]+name=[\"\'\s]*referrer', html, re.I))

        # 5. Google Consent Mode v2
        consent_keywords = ["gtag('consent'", "default_consent", "ad_storage", "analytics_storage", "ad_user_data", "ad_personalization"]
        consent_v2 = any(k in html_lower for k in consent_keywords)
        if consent_v2:
            consent_details = "Google Consent Mode v2 sinyalleri tespit edildi (Çerezsiz modelleme ve reklam uyumluluğu aktif)."
        else:
            consent_details = "Google Consent Mode v2 eksik! Avrupa ve küresel gizlilik yasaları gereği reklam dönüşüm modellemesi kaybı riski."
            score -= 20
            warnings.append("MarTech Uyarısı: Google Consent Mode v2 kurulu değil (P0 - Veri kaybı riski).")

        # 6. Cookie banner & KVKK / GDPR
        cookie_detected = any(k in html_lower for k in ["cookie-consent", "cerez-politikasi", "cookie-banner", "onetrust", "cookiebot", "çerez politikası", "çerezleri kabul et"])
        kvkk_detected = any(k in html_lower for k in ["kvkk", "aydinlatma metni", "aydınlatma metni", "gdpr", "veri sorumlusu", "gizlilik politikası"])

        if not cookie_detected:
            score -= 15
            warnings.append("Hukuk/KVKK: Çerez onay banner'ı tespit edilemedi (Yasal idari para cezası riski).")
        if not kvkk_detected:
            score -= 15
            warnings.append("Hukuk: KVKK Aydınlatma Metni veya Gizlilik Politikası bağlantısı footer'da bulunamadı.")

        return SecurityAndPrivacyAuditResult(
            security_score=max(0, score),
            has_csp=has_csp,
            csp_details=csp_details,
            has_hsts=has_hsts,
            has_x_frame_options=has_x_frame,
            has_referrer_policy=has_ref_policy,
            consent_mode_v2_detected=consent_v2,
            consent_mode_details=consent_details,
            cookie_banner_detected=cookie_detected,
            kvkk_gdpr_detected=kvkk_detected,
            security_warnings=warnings
        )

    def audit_ecommerce_cro(self, html: str) -> ECommerceCROScorecard:
        """
        Specialist e-commerce CRO audit evaluating checkout friction, sticky CTAs, and trust badges.
        """
        html_lower = html.lower()
        score = 100
        flags = []
        recs = []

        # 1. Sticky Mobile CTA
        sticky_signals = ["sticky-cta", "fixed-bottom", "sticky-cart", "floating-cta", "action-bar-fixed", "sticky_btn", "sticky_buy"]
        has_sticky = any(s in html_lower for s in sticky_signals)
        if not has_sticky:
            score -= 20
            flags.append("Mobil Yapışkan CTA (Sticky Add-to-Cart) eksik.")
            recs.append("Kullanıcı sayfayı kaydırdığında ekranın altına sabitlenen 'Sepete Ekle' barı eklenmeli (CVR +%18).")

        # 2. 1-Click Express Checkout
        express_methods = []
        if "masterpass" in html_lower:
            express_methods.append("Masterpass")
        if "apple pay" in html_lower or "apple-pay" in html_lower:
            express_methods.append("Apple Pay")
        if "google pay" in html_lower or "google-pay" in html_lower:
            express_methods.append("Google Pay")
        if "garantipay" in html_lower or "garanti pay" in html_lower:
            express_methods.append("GarantiPay")
        if "iyzico" in html_lower:
            express_methods.append("iyzico Hızlı Ödeme")
        if "paytr" in html_lower:
            express_methods.append("PayTR Express")

        has_express = len(express_methods) > 0
        if not has_express:
            score -= 20
            flags.append("1-Tıkla Hızlı Ödeme (Express Checkout) altyapısı bulunamadı.")
            recs.append("Masterpass veya Apple/Google Pay entegrasyonuyla ödeme sürtünmesi düşürülmeli.")

        # 3. Guest Checkout Accessibility
        guest_signals = ["misafir", "üye olmadan", "uye-olmadan", "guest checkout", "üye olmadan devam et"]
        has_guest = any(g in html_lower for g in guest_signals)
        if not has_guest and ("üye girişi" in html_lower or "giriş yap" in html_lower):
            score -= 15
            flags.append("Zorunlu üyelik bariyeri riski; misafir alışverişi ibaresi belirgin değil.")
            recs.append("Sepet terkini önlemek için 'Üye Olmadan Satın Al' (Misafir Alışverişi) akışı belirginleştirilmeli.")

        # 4. Form input count
        input_matches = re.findall(r'<input\b[^>]*>', html, re.IGNORECASE)
        # Filter hidden inputs
        visible_inputs = [inp for inp in input_matches if 'type="hidden"' not in inp.lower() and "type='hidden'" not in inp.lower()]
        inp_count = len(visible_inputs)

        if inp_count >= 10:
            score -= 25
            flags.append(f"Aşırı form alanı ({inp_count} alan tespit edildi - Yüksek terk riski).")
            recs.append("Ödeme ve iletişim formundaki alan sayısı 5 veya altına indirilmelidir.")
        elif inp_count >= 6:
            score -= 10
            flags.append(f"Orta düzey form sürtünmesi ({inp_count} alan).")

        # 5. Trust badges & guarantees
        trust_badges = []
        if "ssl" in html_lower or "256-bit" in html_lower:
            trust_badges.append("256-Bit SSL Şifreleme")
        if "3d secure" in html_lower or "3d-secure" in html_lower:
            trust_badges.append("3D Secure Güvenli Ödeme")
        if "iade" in html_lower or "14 gün" in html_lower or "koşulsuz iade" in html_lower:
            trust_badges.append("14 Gün Koşulsuz Para İade Garantisi")
        if "ücretsiz kargo" in html_lower or "kargo bedava" in html_lower:
            trust_badges.append("Ücretsiz Kargo Avantajı")
        if "orijinal" in html_lower or "faturalı" in html_lower:
            trust_badges.append("%100 Orijinal Ürün Garantisi")

        if len(trust_badges) < 2:
            score -= 15
            flags.append("Sosyal kanıt ve güven rozetleri (İade/SSL/Kargo garantisi) yetersiz.")
            recs.append("Sepet ve ödeme butonunun hemen altına güven rozetleri (14 Gün İade, 3D Secure, SSL) yerleştirilmeli.")

        if score >= 80:
            tier = "OPTIMAL"
        elif score >= 50:
            tier = "MODERATE"
        else:
            tier = "SEVERE_FRICTION"

        return ECommerceCROScorecard(
            cro_score=max(0, score),
            friction_tier=tier,
            sticky_cta_detected=has_sticky,
            express_checkout_detected=has_express,
            express_methods=express_methods,
            guest_checkout_accessible=has_guest,
            checkout_form_input_count=inp_count,
            trust_badges_detected=trust_badges,
            friction_flags=flags,
            actionable_recommendations=recs
        )

    def audit_serp_features(
        self,
        html: str,
        schema_audit: Optional[SchemaOrgAuditResult] = None
    ) -> SERPFeatureOpportunityAuditResult:
        """
        Evaluates page readiness for Google SERP features (Featured Snippets, PAA, Rich Merchant listings).
        """
        score = 0
        roadmap = []

        # 1. PAA (People Also Ask) questions in H2/H3
        paa_detected = []
        for h_tag in re.finditer(r'<h[23][^>]*>(.*?)</h[23]>', html, re.DOTALL | re.IGNORECASE):
            text = re.sub(r'<[^>]+>', '', h_tag.group(1)).strip()
            if any(q in text.lower() for q in ["nasıl", "nedir", "neden", "hangisi", "kaç", "ne zaman", "?"]):
                paa_detected.append(text)

        paa_count = len(paa_detected)
        if paa_count >= 3:
            score += 35
        elif paa_count >= 1:
            score += 20
        else:
            roadmap.append("Sayfa sonuna 'Sıkça Sorulan Sorular' akordeonu ve FAQPage şeması eklenerek PAA görünürlüğü hedeflenmeli.")

        # 2. Featured Snippet candidates (Concise paragraph right below heading or ordered list)
        fs_candidates = []
        for match in re.finditer(r'<h[23][^>]*>(.*?)</h[23]>\s*<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE):
            h_text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            p_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            words = p_text.split()
            if 25 <= len(words) <= 60 and any(q in h_text.lower() for q in ["nedir", "nasıl", "rehber"]):
                fs_candidates.append(f"{h_text}: {p_text[:80]}...")

        # Also check for ordered lists <ol>
        has_ordered_list = bool(re.search(r'<ol\b[^>]*>.*?</ol>', html, re.DOTALL | re.IGNORECASE))
        if has_ordered_list:
            score += 20
            fs_candidates.append("Adımlı `<ol>` sıralı liste tespit edildi (Prosedür snippet uyumlu).")

        if fs_candidates:
            score += 25
            fs_readiness = "HIGH" if score >= 60 else "MODERATE"
        else:
            fs_readiness = "LOW"
            roadmap.append("40-55 kelimelik net tanım paragrafları veya adımlı `<ol>` listeleri eklenerek Sıfırıncı Sıra (Featured Snippet) hedeflenmeli.")

        # 3. Rich Merchant listings
        has_valid_prod = schema_audit.valid_product_schema if schema_audit else False
        if has_valid_prod:
            rich_readiness = "READY"
            score += 30
        elif schema_audit and "Product" in schema_audit.schema_types_detected:
            rich_readiness = "PARTIAL"
            score += 15
            roadmap.append("Product şemasındaki eksik alanlar (fiyat, stok, gtin13, değerlendirme) tamamlanarak Google Alışveriş yıldızları kazanılmalı.")
        else:
            rich_readiness = "NOT_ELIGIBLE"
            roadmap.append("Ürün detay sayfalarına Product ve AggregateOffer JSON-LD şemaları eklenmelidir.")

        # 4. Sitelinks searchbox
        sitelinks_eligible = "searchaction" in html.lower()
        if sitelinks_eligible:
            score += 10

        return SERPFeatureOpportunityAuditResult(
            featured_snippet_readiness=fs_readiness,
            featured_snippet_candidates=fs_candidates,
            paa_question_count=paa_count,
            paa_questions_detected=paa_detected,
            rich_merchant_readiness=rich_readiness,
            sitelinks_searchbox_eligible=sitelinks_eligible,
            serp_opportunity_score=min(100, score),
            optimization_roadmap=roadmap
        )


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
