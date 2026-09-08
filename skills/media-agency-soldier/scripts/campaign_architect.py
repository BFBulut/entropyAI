"""
CampaignArchitect: Relational Promotions & Multi-Channel Performance Ads Engine.
Synthesizes profit-optimized campaigns (BOGO, Cross-Sell, Cart Threshold, VIP)
and multi-channel ad copy blueprints (Google Search, Meta/Instagram, TikTok/Reels).
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

try:
    from media_calculator import MediaAgencyCalculator
except ImportError:
    MediaAgencyCalculator = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class RelationalCampaignItem(BaseModel):
    campaign_type: str = Field(..., description="BOGO | CROSS_SELL | CART_THRESHOLD | VIP_SUBSCRIPTION")
    headline: str = Field(..., description="Promotional headline")
    primary_product: str = Field(..., description="Anchor product")
    secondary_product: Optional[str] = Field(None, description="Complementary product")
    discount_mechanism: str = Field(..., description="Exact mechanic")
    margin_protection_rationale: str = Field(..., description="Margin defense rationale")
    expected_aov_lift_pct: float = Field(..., description="Estimated AOV lift percentage")
    call_to_action: str = Field(..., description="Button CTA")


class GoogleSearchAd(BaseModel):
    campaign_name: str
    headlines: List[str]
    descriptions: List[str]
    target_keywords: List[str] = Field(default_factory=list)
    negative_keywords: List[str] = Field(default_factory=list)


class UGCScriptScene(BaseModel):
    scene_number: int
    timeframe: str
    visual_direction: str
    audio_voiceover: str
    on_screen_text: str


class MetaAdCreative(BaseModel):
    hook: str
    problem_agitation: str
    solution_value_prop: str
    primary_text: str
    carousel_cards: List[Dict[str, str]] = Field(default_factory=list)
    ugc_script: List[UGCScriptScene] = Field(default_factory=list)
    cta_button_text: str = "Alışverişe Başla"


class TikTokReelsAd(BaseModel):
    three_second_hook: str
    trending_audio_theme: str
    visual_action: str
    direct_offer_and_cta: str


class MultiChannelAdsPackage(BaseModel):
    google_search: List[GoogleSearchAd] = Field(default_factory=list)
    meta_instagram: List[MetaAdCreative] = Field(default_factory=list)
    tiktok_reels: List[TikTokReelsAd] = Field(default_factory=list)


class MasterCampaignPackage(BaseModel):
    brand_name: str
    target_audience_summary: str
    relational_campaigns: List[RelationalCampaignItem] = Field(default_factory=list)
    multi_channel_ads: MultiChannelAdsPackage


class MetaASCBlueprint(BaseModel):
    campaign_name: str
    campaign_objective: str = "OUTCOME_SALES"
    budget_optimization: str = "Advantage Campaign Budget (CBO)"
    allocated_monthly_budget: float
    existing_customer_budget_cap_pct: float = 5.0
    attribution_setting: str = "7-day click or 1-day view"
    creative_mix: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_ad_angles: List[Dict[str, str]] = Field(default_factory=list)
    scaling_rules: str = "48 saatte bir en fazla %20 bütçe artışı."


class GooglePMaxBlueprint(BaseModel):
    campaign_name: str
    target_roas_pct: float
    allocated_monthly_budget: float
    asset_group_name: str
    final_url: str
    short_headlines: List[str] = Field(default_factory=list)
    long_headlines: List[str] = Field(default_factory=list)
    descriptions: List[str] = Field(default_factory=list)
    search_themes: List[str] = Field(default_factory=list)
    audience_signals: Dict[str, List[str]] = Field(default_factory=dict)
    brand_exclusion_applied: bool = True


class EmailSMSFlow(BaseModel):
    flow_name: str
    trigger_event: str
    steps: List[Dict[str, str]] = Field(default_factory=list)
    projected_revenue_contribution_pct: float


class MediaFlightPlan(BaseModel):
    monthly_budget: float
    total_90_day_budget: float
    phase_1_days_1_30: Dict[str, Any] = Field(default_factory=dict)
    phase_2_days_31_60: Dict[str, Any] = Field(default_factory=dict)
    phase_3_days_61_90: Dict[str, Any] = Field(default_factory=dict)
    kpi_milestones: Dict[str, Any] = Field(default_factory=dict)


class GoogleDemandGenBlueprint(BaseModel):
    campaign_name: str
    monthly_budget: float
    target_channels: List[str] = Field(default_factory=lambda: ["YouTube Shorts", "YouTube In-Stream", "Google Discover", "Gmail"])
    short_headlines: List[str] = Field(default_factory=list)
    long_headlines: List[str] = Field(default_factory=list)
    descriptions: List[str] = Field(default_factory=list)
    video_assets: List[Dict[str, str]] = Field(default_factory=list)
    image_assets: List[Dict[str, str]] = Field(default_factory=list)
    lookalike_segments: List[Dict[str, Any]] = Field(default_factory=list)
    call_to_action: str = "Şimdi İncele"
    bidding_strategy: str = "Maximize Conversions (Target CPA)"


class CreativeHookSwapPackage(BaseModel):
    campaign_name: str
    winning_creative_id: str
    winning_body_core_concept: str
    fatigue_indicators_triggered: List[str] = Field(default_factory=list)
    hook_variants: List[Dict[str, str]] = Field(default_factory=list)
    recommended_test_duration_days: int = 5
    actionable_testing_protocol: str


class AgencyOnboardingMilestone(BaseModel):
    day_range: str
    phase_name: str
    sla_gate: str
    deliverables: List[str] = Field(default_factory=list)
    status: str = "PENDING"


class AgencySLAAndOnboardingChecklist(BaseModel):
    brand_name: str
    target_launch_date: str
    milestones: List[AgencyOnboardingMilestone] = Field(default_factory=list)
    fail_closed_rules: List[str] = Field(default_factory=list)


RelationalCampaignItem.model_rebuild()
GoogleSearchAd.model_rebuild()
UGCScriptScene.model_rebuild()
MetaAdCreative.model_rebuild()
TikTokReelsAd.model_rebuild()
MultiChannelAdsPackage.model_rebuild()
MasterCampaignPackage.model_rebuild()
MetaASCBlueprint.model_rebuild()
GooglePMaxBlueprint.model_rebuild()
EmailSMSFlow.model_rebuild()
MediaFlightPlan.model_rebuild()
GoogleDemandGenBlueprint.model_rebuild()
CreativeHookSwapPackage.model_rebuild()
AgencyOnboardingMilestone.model_rebuild()
AgencySLAAndOnboardingChecklist.model_rebuild()


# ---------------------------------------------------------------------------
# CampaignArchitect Core Engine
# ---------------------------------------------------------------------------

class CampaignArchitect:
    """Generates margin-protected campaigns and multi-channel creative plans."""

    def __init__(self):
        pass

    def design_relational_campaigns(
        self,
        products: List[Dict[str, Any]],
        brand_info: Dict[str, Any]
    ) -> List[RelationalCampaignItem]:
        brand_name = brand_info.get("brand_name") or "Markamız"
        prod_names = [p.get("name", "") for p in products if p.get("name")]
        prod_prices = [p.get("price") for p in products if p.get("price") is not None]

        p1 = prod_names[0] if len(prod_names) > 0 else f"{brand_name} Amiral Ürün"
        p2 = prod_names[1] if len(prod_names) > 1 else f"{brand_name} Tamamlayıcı Ürün"
        p3 = prod_names[2] if len(prod_names) > 2 else f"{brand_name} Aksesuar"

        avg_price = (sum(prod_prices) / len(prod_prices)) if prod_prices else 450.0
        thresh = round(avg_price * 1.35, -1)

        return [
            RelationalCampaignItem(
                campaign_type="BOGO",
                headline=f"{p1} Alana {p2} Hediye!",
                primary_product=p1,
                secondary_product=p2,
                discount_mechanism="X alana Y bedava",
                margin_protection_rationale="Tamamlayıcı ürünün maliyet avantajı ana ürünün liste fiyatıyla sübvanse edilir.",
                expected_aov_lift_pct=22.0,
                call_to_action="Hediyeni Al"
            ),
            RelationalCampaignItem(
                campaign_type="CROSS_SELL",
                headline=f"{p1} ile Birlikte {p2} %10 İndirimli!",
                primary_product=p1,
                secondary_product=p2,
                discount_mechanism="X alana Y %10 indirimli",
                margin_protection_rationale="Marj korumalı sepet genişletme stratejisi.",
                expected_aov_lift_pct=28.0,
                call_to_action="İndirimi Yakala"
            ),
            RelationalCampaignItem(
                campaign_type="CART_THRESHOLD",
                headline=f"{int(thresh)} TL Üzeri Ücretsiz Kargo ve Sürpriz Hediye!",
                primary_product="Tüm Sepet",
                secondary_product="Hızlı Kargo",
                discount_mechanism="kargo bedava",
                margin_protection_rationale="Ortalama sepet tutarının %35 üzerinde kurgulanarak sepet tamamlama teşvik edilir.",
                expected_aov_lift_pct=35.0,
                call_to_action="Sepeti Tamamla"
            ),
            RelationalCampaignItem(
                campaign_type="VIP_SUBSCRIPTION",
                headline=f"{brand_name} VIP Kulüp Ayrıcalıkları",
                primary_product="VIP Üyelik",
                secondary_product="Özel Lansman İndirimleri",
                discount_mechanism="Sabit %15 İndirim",
                margin_protection_rationale="LTV artırımı ve sıfır CAC ile tekrarlayan satış.",
                expected_aov_lift_pct=40.0,
                call_to_action="Kulübe Katıl"
            )
        ]

    def design_multi_channel_ads(
        self,
        campaigns: List[Dict[str, Any]],
        brand_info: Dict[str, Any]
    ) -> MultiChannelAdsPackage:
        brand = brand_info.get("brand_name") or "Markamız"
        return MultiChannelAdsPackage(
            google_search=[
                GoogleSearchAd(
                    campaign_name=f"{brand} Search Ads",
                    headlines=[f"{brand} Resmi Mağaza", "Özel Lansman Fırsatı", "Aynı Gün Hızlı Kargo"],
                    descriptions=[f"{brand} kalitesiyle tanışın. En iyi seçenekleri keşfedin.", "Orijinal ürün ve iade garantisiyle hemen sipariş verin."],
                    target_keywords=[f"{brand.lower()} satın al", f"{brand.lower()} fiyatları"],
                    negative_keywords=["ücretsiz", "bedava", "crack", "torrent", "ikinci el"]
                )
            ],
            meta_instagram=[
                MetaAdCreative(
                    hook=f"Hala sıradan çözümlerle vakit mi kaybediyorsunuz? {brand} ile tanışın!",
                    problem_agitation="Piyasadaki kalitesiz ürünlerden yoruldunuz mu?",
                    solution_value_prop=f"{brand} üstün kalite ve konfor sunar.",
                    primary_text=f"{brand} ile tarzınızı ve konforunuzu zirveye taşıyın.",
                    carousel_cards=[
                        {"card": "1", "title": "Amiral Ürün", "description": "En popüler model", "badge": "Yıldız ⭐"}
                    ],
                    ugc_script=[
                        UGCScriptScene(scene_number=1, timeframe="0-3 sn", visual_direction="Kutu açılımı", audio_voiceover="Bunu gördünüz mü?", on_screen_text="Şok Fiyat!"),
                        UGCScriptScene(scene_number=2, timeframe="3-8 sn", visual_direction="Sorun gösterimi", audio_voiceover="Eskiler hep bozulurdu.", on_screen_text="Sorun Yok"),
                        UGCScriptScene(scene_number=3, timeframe="8-15 sn", visual_direction="Kullanım", audio_voiceover=f"{brand} harika!", on_screen_text=f"{brand}"),
                        UGCScriptScene(scene_number=4, timeframe="15-20 sn", visual_direction="CTA", audio_voiceover="Tıklayın!", on_screen_text="Fırsat")
                    ]
                )
            ],
            tiktok_reels=[
                TikTokReelsAd(
                    three_second_hook="POV: Hayatını değiştiren o an! 🔥",
                    trending_audio_theme="Viral upbeat drop",
                    visual_action="Ürünü kameraya göster",
                    direct_offer_and_cta=f"Bio'daki linke tıkla ve {brand} ayrıcalığını yaşa!"
                )
            ]
        )

    def build_campaign_package(
        self,
        products: List[Dict[str, Any]],
        brand_info: Dict[str, Any]
    ) -> MasterCampaignPackage:
        brand_name = brand_info.get("brand_name") or "Markamız"
        rel = self.design_relational_campaigns(products, brand_info)
        ads = self.design_multi_channel_ads([c.model_dump() for c in rel], brand_info)
        return MasterCampaignPackage(
            brand_name=brand_name,
            target_audience_summary=f"{brand_name} hedef kitlesi",
            relational_campaigns=rel,
            multi_channel_ads=ads
        )

    # -----------------------------------------------------------------------
    # Comprehensive Test Suite Bridge APIs
    # -----------------------------------------------------------------------

    def generate_relational_campaigns(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        brand_info = analysis.get("brand_info", {})
        brand_name = brand_info.get("brand_name", "Marka")
        catalog = analysis.get("product_catalog", {})
        prods = catalog.get("products", [])

        p1 = prods[0]["name"] if len(prods) > 0 else "Amiral Ürün"
        p2 = prods[1]["name"] if len(prods) > 1 else "Tamamlayıcı Ürün"

        avg_price = catalog.get("average_price") or 500.0
        curr = catalog.get("currencies", ["₺"])[0] if catalog.get("currencies") else "₺"
        threshold_val = round(avg_price * 1.35, 2)
        if threshold_val <= avg_price:
            threshold_val = avg_price + 100.0

        return {
            "bogo": {
                "name": f"{brand_name} İkili Fırsat - Hediye Ürün Avantajı",
                "mechanic": "X alana Y bedava",
                "primary_product": p1,
                "free_product": p2,
                "margin_impact": "Düşük maliyetli tamamlayıcı ürün liste fiyatıyla sübvanse edilerek brüt marj korunur.",
                "slogan": f"{p1} Alana {p2} Bedava Hediye!"
            },
            "cross_discount": {
                "name": f"{brand_name} Çapraz Sepet Genişletme Paketi",
                "mechanic": "X alana Y %10 indirimli",
                "discount_percent": 10,
                "primary_product": p1,
                "discounted_product": p2,
                "promotional_angle": "Sepet derinliğini ve ortalama sipariş tutarını artırma.",
                "bundled_savings": "Birlikte alımda sepette %10 tasarruf avantajı."
            },
            "cart_threshold": {
                "name": f"{brand_name} Ücretsiz Kargo & Sepet Teşvik Kampanyası",
                "mechanic": f"{threshold_val} {curr} üzeri alışverişlerde kargo bedava ve hediye",
                "threshold_amount": threshold_val,
                "currency": curr,
                "slogan": f"{int(threshold_val)} {curr} ve Üzeri Alışverişlerde Kargo Bedava!",
                "estimated_aov_lift": "%25 AOV Sepet Artışı Öngörüsü"
            },
            "vip_subscription": {
                "name": f"{brand_name} VIP Sadakat Kulübü",
                "mechanic": "VIP üyelere sabit indirim ve öncelikli kargo",
                "discount_percent": 15,
                "slogan": "Ayrıcalıklı Alışverişin Adresi"
            }
        }

    def generate_multichannel_ad_plans(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        brand_info = analysis.get("brand_info", {})
        brand_name = brand_info.get("brand_name", "Marka")
        catalog = analysis.get("product_catalog", {})
        prods = catalog.get("products", [])
        p1 = prods[0]["name"] if prods else "Özel Ürün"

        # Strictly <= 30 chars for Google Ads headlines
        # Strictly <= 90 chars for Google Ads descriptions
        g_headlines = [
            f"{brand_name} Resmi Sitesi"[:30],
            f"Yeni Sezon {brand_name}"[:30],
            f"{p1[:18]} Fırsatı"[:30],
            "Aynı Gün Hızlı Kargo"[:30],
            "Orijinal Ürün Garantisi"[:30],
            "Sepette Anında İndirim"[:30]
        ]
        g_descriptions = [
            f"{brand_name} koleksiyonunu keşfedin. Kalite ve konfor burada."[:90],
            "Güvenli ödeme ve 14 gün koşulsuz iade avantajıyla hemen sipariş verin."[:90],
            f"Kaçırılmayacak {brand_name} fırsatları stoklarla sınırlıdır. Hemen alın."[:90]
        ]
        g_negatives = [
            "ücretsiz", "bedava", "crack", "torrent", "ikinci el",
            "sahibinden", "iş ilanları", "kariyer", "staj", "şikayet",
            "ekşi", "hile", "sahte", "çakma"
        ]

        # Meta Hook
        meta_hook = f"Hala sıradan ürünlerle vakit mi kaybediyorsunuz? {brand_name} ile tanışma zamanı geldi!"

        # Carousel cards
        carousel_cards = [
            {
                "card_number": 1,
                "headline": f"{brand_name} Amiral Ürün"[:40],
                "caption": "En çok satan favori model.",
                "cta": "Hemen İncele"
            },
            {
                "card_number": 2,
                "headline": "Tamamlayıcı Avantaj"[:40],
                "caption": "Birlikte alımda sepette ek indirim.",
                "cta": "Sepete Ekle"
            },
            {
                "card_number": 3,
                "headline": "Hediye & Hızlı Kargo"[:40],
                "caption": "Eşik üzeri siparişlerde kargo hediye.",
                "cta": "Fırsatı Yakala"
            }
        ]

        # UGC Scenario (5 stages)
        ugc_scenario = {
            "hook_0_3s": "İçerik üreticisi kutuyu heyecanla kameraya gösterir: 'Bunu internette görüp duruyordum!'",
            "problem_3_8s": "Eski kalitesiz alternatiflerin yarattığı hayal kırıklığı vurgulanır.",
            "solution_8_15s": f"Kutu açılır ve {brand_name} kalitesi, dokusu yakın çekimle net şekilde gösterilir.",
            "demo_15_25s": "Ürünün günlük hayatta rahat ve şık kullanımı canlı olarak sergilenir.",
            "cta_25_30s": f"Aşağıdaki bağlantıya tıklayın ve {brand_name} özel hediyenizi kaçırmayın!"
        }

        # TikTok Reels Ads
        tiktok_ads = {
            "hook": "POV: 2026'da hala eski yöntemleri kullanıyorsundur...",
            "trend_concept": "Hızlı tempolu viral ses ve eğlenceli split-screen tepki formatı",
            "script_breakdown": [
                {"timing": "0-3 sn", "visual": "Parmak şıklatma ve şaşkın yüz ifadesi", "audio": "Trend drop beat"},
                {"timing": "3-8 sn", "visual": "Ürünün merkezde estetik dönüşü", "audio": "Bunu mutlaka denemelisiniz"},
                {"timing": "8-15 sn", "visual": "Sonuç ve gülümseme", "audio": "Link profilde, acele edin!"}
            ],
            "cta": "Hemen bio'daki linke tıkla ve avantajlı paketini al!"
        }

        return {
            "google_search_ads": {
                "ad_type": "Responsive Search Ads (RSA)",
                "headlines": g_headlines,
                "descriptions": g_descriptions,
                "negative_keywords": g_negatives
            },
            "meta_ads": {
                "hook": meta_hook,
                "carousel_cards": carousel_cards,
                "ugc_scenario": ugc_scenario
            },
            "tiktok_reels_ads": tiktok_ads
        }

    def generate_unit_economics_plan(
        self,
        analysis: Dict[str, Any],
        monthly_budget: float = 100000.0
    ) -> Dict[str, Any]:
        catalog = analysis.get("product_catalog", {})
        prods = catalog.get("products", [])
        avg_price = catalog.get("average_price") or 500.0
        curr = catalog.get("currencies", ["₺"])[0] if catalog.get("currencies") else "₺"

        p1_price = prods[0].get("price", avg_price) if prods else avg_price
        p2_price = prods[1].get("price", avg_price * 0.4) if len(prods) > 1 else avg_price * 0.4

        if MediaAgencyCalculator:
            calc = MediaAgencyCalculator()
            breakeven_roas = calc.calculate_breakeven_roas(gross_margin_pct=55.0)
            target_roas = calc.calculate_target_roas(gross_margin_pct=55.0, target_net_margin_pct=15.0)
            max_cpa = calc.calculate_max_allowable_cpa(aov=avg_price, gross_margin_pct=55.0, target_profit_per_order=avg_price * 0.15)
            budget_balanced = calc.calculate_funnel_budget_split(total_budget=monthly_budget, strategy="balanced", currency=curr).model_dump()
            budget_scale = calc.calculate_funnel_budget_split(total_budget=monthly_budget, strategy="scale", currency=curr).model_dump()

            bogo_sim = calc.simulate_bogo_margin(
                hero_price=p1_price,
                hero_cogs=p1_price * 0.35,
                gift_price=p2_price,
                gift_cogs=p2_price * 0.25,
                shipping_cost=35.0
            ).model_dump()

            bundle_sim = calc.simulate_bundle_discount(
                hero_price=p1_price,
                complementary_price=p2_price,
                discount_pct=10.0,
                cogs_pct=35.0
            ).model_dump()

            cart_thresh = calc.simulate_cart_thresholds(current_aov=avg_price, currency=curr)

            return {
                "assumed_gross_margin_pct": 55.0,
                "breakeven_roas": breakeven_roas,
                "breakeven_roas_pct": round(breakeven_roas * 100.0, 1),
                "target_roas": target_roas,
                "target_roas_pct": round(target_roas * 100.0, 1),
                "max_allowable_cpa": max_cpa,
                "currency": curr,
                "funnel_budget_allocations": {
                    "balanced": budget_balanced,
                    "scale": budget_scale
                },
                "promotional_simulations": {
                    "bogo_simulation": bogo_sim,
                    "bundle_simulation": bundle_sim,
                    "cart_thresholds": cart_thresh
                }
            }

        return {
            "assumed_gross_margin_pct": 55.0,
            "breakeven_roas": 1.82,
            "target_roas": 2.50,
            "max_allowable_cpa": round(avg_price * 0.40, 2),
            "currency": curr
        }

    def generate_meta_asc_blueprint(
        self,
        analysis: Dict[str, Any],
        monthly_meta_budget: float = 50000.0
    ) -> MetaASCBlueprint:
        """
        Generates Meta Advantage+ Shopping Campaign (ASC) structure.
        """
        brand_info = analysis.get("brand_info", {})
        brand_name = brand_info.get("brand_name") or "Markamız"
        products = analysis.get("products", [])
        top_prod = products[0]["name"] if products else "Koleksiyon"

        creative_mix = [
            {"format": "DPA / Dynamic Product Ads", "share_pct": 25.0, "role": "Dinamik katalog sepet tamamlama ve kişiselleştirilmiş ürün gösterimi."},
            {"format": "Statik Değer & Sosyal Kanıt", "share_pct": 25.0, "role": "Yıldızlı müşteri yorumları, basın kupürleri ve %100 memnuniyet güvencesi."},
            {"format": "Kurucu / Uzman Anlatımı", "share_pct": 20.0, "role": "Marka hikayesi, üretim kalitesi ve neden daha iyi olduğunun açıklaması."},
            {"format": "UGC Kutu Açılımı / Demo", "share_pct": 30.0, "role": "Kullanıcı deneyimi, problem-çözüm videosu ve doğrudan teklif."}
        ]

        angles = [
            {"angle": "Problem-Çözüm", "hook": f"Sıradan ürünlerden bıktınız mı? {brand_name} ile tanışın."},
            {"angle": "Sosyal Kanıt & İnceleme", "hook": f"Binlerce mutlu müşterinin tercihi {top_prod} neden bu kadar popüler?"},
            {"angle": "Kıtlık / Özel Teklif", "hook": f"Sınırlı stok! İlk siparişinize özel sepette anında indirim fırsatını kaçırmayın."}
        ]

        return MetaASCBlueprint(
            campaign_name=f"[ASC] - {brand_name} - Satış & Yeni Müşteri Büyümesi",
            allocated_monthly_budget=monthly_meta_budget,
            existing_customer_budget_cap_pct=5.0,
            creative_mix=creative_mix,
            suggested_ad_angles=angles
        )

    def generate_google_pmax_blueprint(
        self,
        analysis: Dict[str, Any],
        monthly_google_budget: float = 35000.0
    ) -> GooglePMaxBlueprint:
        """
        Generates Google Performance Max (PMax) Asset Group and audience signals.
        """
        brand_info = analysis.get("brand_info", {})
        brand_name = brand_info.get("brand_name") or "Markamız"
        domain = brand_info.get("domain") or "example.com"
        products = analysis.get("products", [])
        top_prod = products[0]["name"] if products else "Premium Ürünler"

        short_headlines = [
            f"{brand_name} Resmi Sitesi",
            f"{top_prod} Modelleri",
            "Güvenli ve Hızlı Teslimat",
            "En Çok Satan Koleksiyon",
            "Aynı Gün Kargo Fırsatı",
            "14 Gün Kolay İade",
            "Orijinal Ürün Garantisi",
            "Sezon İndirimleri Başladı",
            "Sepette Ek İndirim",
            "Hemen Sipariş Verin"
        ]

        long_headlines = [
            f"{brand_name} Resmi Web Sitesinde Yüzlerce Ürün ve Özel Fırsatlar",
            f"{top_prod} ile Kaliteyi Deneyimleyin: Ücretsiz Kargo Avantajıyla Hemen Alın",
            f"Türkiye'nin Güvenilir Markası {brand_name}: %100 Müşteri Memnuniyeti",
            "En Yeni Sezon Koleksiyonu ve Kampanyalı Fiyatlarla Güvenli Alışveriş",
            "Sepet Eşiklerine Özel Hediye ve İndirim Fırsatlarıyla Şimdi Keşfedin"
        ]

        descriptions = [
            f"{brand_name} kalitesiyle tanışın. Yüksek müşteri memnuniyeti ve güvenli ödeme.",
            f"{top_prod} ve tüm koleksiyon resmi web sitemizde. Hızlı kargo ile kapınızda.",
            "Güvenli alışveriş, taksit imkanları ve kolay iade garantisiyle hemen sipariş verin.",
            "Özel kampanyalar, sepet indirimleri ve hediye fırsatlarını kaçırmayın."
        ]

        search_themes = [
            f"{brand_name} online satış",
            f"en iyi {top_prod.lower()}",
            f"{top_prod.lower()} fiyatları",
            f"{brand_name} indirim kampanyası",
            "güvenilir online alışveriş"
        ]

        audience_signals = {
            "first_party": ["Son 180 Gün Alıcıları (Customer Match)", "GA4 Tüm Ziyaretçiler"],
            "custom_intent": [f"{brand_name}", f"satın al {top_prod.lower()}", "en iyi markalar"],
            "in_market": ["Alışveriş / Giyim / Aksesuar / E-Ticaret"]
        }

        return GooglePMaxBlueprint(
            campaign_name=f"[PMAX] - {brand_name} - Tüm Kanallar Performans",
            target_roas_pct=260.0,
            allocated_monthly_budget=monthly_google_budget,
            asset_group_name=f"{brand_name} - Çok Satanlar & Hero SKU",
            final_url=f"https://{domain}",
            short_headlines=short_headlines,
            long_headlines=long_headlines,
            descriptions=descriptions,
            search_themes=search_themes,
            audience_signals=audience_signals,
            brand_exclusion_applied=True
        )

    def generate_retention_flows(self, brand_info: Dict[str, Any]) -> List[EmailSMSFlow]:
        """
        Generates 4 essential Klaviyo/Omnisend retention email and SMS flows.
        """
        brand_name = brand_info.get("brand_name") or "Markamız"
        return [
            EmailSMSFlow(
                flow_name="Hoş Geldin Serisi (Welcome Nurture)",
                trigger_event="Bülten / Pop-up Aboneliği",
                steps=[
                    {"delay": "Anında", "channel": "Email", "subject": f"Aramıza Hoş Geldiniz! İlk siparişinize özel %10 indirim kodunuz burada.", "action": "%10 Hoş geldin kuponu"},
                    {"delay": "24 Saat", "channel": "Email", "subject": f"{brand_name} Neden Farklı? Kurucumuzdan özel bir mesaj.", "action": "Marka hikayesi ve değerler"},
                    {"delay": "48 Saat", "channel": "Email", "subject": "Müşterilerimiz en çok neyi seviyor? Çok satanları keşfedin.", "action": "Sosyal kanıt ve 5 yıldızlı yorumlar"},
                    {"delay": "72 Saat", "channel": "SMS", "subject": f"{brand_name}: Hoş geldin indirim kodunuz bu gece sona eriyor! [Link]", "action": "Aciliyet ve sepet tamamlama"}
                ],
                projected_revenue_contribution_pct=12.0
            ),
            EmailSMSFlow(
                flow_name="Terk Edilen Sepet / Ödeme (Cart & Checkout Abandonment)",
                trigger_event="Sepete Ekleme veya Ödeme Başlatıp Ayrılma",
                steps=[
                    {"delay": "1 Saat", "channel": "Email", "subject": "Sepetinizdeki ürünler sizi bekliyor!", "action": "Sepet linki hatırlatma"},
                    {"delay": "12 Saat", "channel": "SMS", "subject": f"{brand_name}: Sepetinizdeki ürünler tükenmek üzere. Ücretsiz kargo ile tamamlayın: [Link]", "action": "Kargo bedava teşviki"},
                    {"delay": "24 Saat", "channel": "Email", "subject": "Hala karar veremediniz mi? İşte bu ürünü alanların yorumları.", "action": "Sosyal kanıt ve SSS"},
                    {"delay": "48 Saat", "channel": "Email", "subject": "Sepetiniz için son şans: %5 sürpriz indirim eklendi!", "action": "Marj korumalı indirim"}
                ],
                projected_revenue_contribution_pct=18.0
            ),
            EmailSMSFlow(
                flow_name="Satın Alma Sonrası VIP Sadakat (Post-Purchase Cross-Sell)",
                trigger_event="Başarılı Sipariş Tamamlama",
                steps=[
                    {"delay": "Anında", "channel": "Email", "subject": "Siparişiniz Alındı! Hazırlık aşamalarını buradan izleyebilirsiniz.", "action": "Kargo takibi ve teşekkür"},
                    {"delay": "7 Gün", "channel": "Email", "subject": "Ürününüzü en iyi şekilde kullanma rehberi.", "action": "Eğitim ve bakım ipuçları"},
                    {"delay": "14 Gün", "channel": "Email", "subject": f"Deneyiminizi paylaşın, bir sonraki siparişinizde 100 TL puan kazanın!", "action": "Fotoğraflı yorum toplama"},
                    {"delay": "21 Gün", "channel": "Email", "subject": "Aldığınız ürünü mükemmel tamamlayan özel parçalar.", "action": "Kişiselleştirilmiş çapraz satış"}
                ],
                projected_revenue_contribution_pct=10.0
            ),
            EmailSMSFlow(
                flow_name="60 Gün Geri Kazanım (Win-Back & Reactivation)",
                trigger_event="Son Siparişten 60 Gün Geçmesi",
                steps=[
                    {"delay": "60 Gün", "channel": "Email", "subject": f"Sizi Özledik! {brand_name}'de yeni neler var?", "action": "Yeni sezon tanıtımı"},
                    {"delay": "67 Gün", "channel": "SMS", "subject": f"{brand_name}: Size özel tanımlanan 150 TL hediye kuponunu kullanın: [Link]", "action": "VIP geri kazanım kuponu"}
                ],
                projected_revenue_contribution_pct=6.0
            )
        ]

    def generate_30_60_90_flight_plan(
        self,
        monthly_budget: float = 100000.0,
        analysis: Optional[Dict[str, Any]] = None
    ) -> MediaFlightPlan:
        """
        Generates comprehensive 30-60-90 day multi-channel flight plan with spend pacing.
        """
        brand_info = (analysis or {}).get("brand_info", {})
        brand_name = brand_info.get("brand_name") or "Marka"
        total_90 = monthly_budget * 3.0

        p1 = {
            "name": "1-30 Gün: Altyapı, MarTech Sinyalleri ve Piksel Eğitimi",
            "monthly_budget": monthly_budget,
            "budget_allocation": {
                "Meta TOFU (Reels/Video)": round(monthly_budget * 0.50, 2),
                "Meta BOFU (DPA/Sepet)": round(monthly_budget * 0.15, 2),
                "Google Search (Marka + Temel)": round(monthly_budget * 0.25, 2),
                "Test Sandbox (3:2:2)": round(monthly_budget * 0.10, 2)
            },
            "strategic_milestones": [
                "GTM Server-side ve Meta CAPI tekilleştirmesinin (event_id) doğrulanması.",
                "Mobil sticky CTA ve tek adımda ödeme entegrasyonuyla CRO sürtünmesinin düşürülmesi.",
                "Piksel tabanında ilk 500+ Purchase olayının tamamlanması.",
                "Klaviyo Hoş Geldin ve Terk Edilen Sepet akışlarının canlıya alınması."
            ],
            "target_blended_roas": 2.0
        }

        p2 = {
            "name": "31-60 Gün: Katalizör Lansmanı, Teklif & Kreatif Test Ölçeklemesi",
            "monthly_budget": monthly_budget,
            "budget_allocation": {
                "Meta Advantage+ Shopping (ASC)": round(monthly_budget * 0.55, 2),
                "Google PMax": round(monthly_budget * 0.25, 2),
                "TikTok Spark Ads": round(monthly_budget * 0.10, 2),
                "Retention (Email/SMS VIP)": round(monthly_budget * 0.10, 2)
            },
            "strategic_milestones": [
                "Kazanan 3:2:2 kreatiflerin Meta ASC kampanyasına taşınması.",
                "BOGO ve %10-%15 bundle sepet teşviklerinin devreye alınması.",
                "AOV artırıcı ücretsiz kargo ve hediye eşiklerinin lansmanı.",
                "TikTok Spark Ads ile içerik üretici işbirliklerinin başlatılması."
            ],
            "target_blended_roas": 2.8
        }

        p3 = {
            "name": "61-90 Gün: Agresif Dikey/Yatay Ölçekleme ve LTV Hasadı",
            "monthly_budget": monthly_budget,
            "budget_allocation": {
                "Meta ASC (Ölçekleme)": round(monthly_budget * 0.50, 2),
                "Google PMax + RSA": round(monthly_budget * 0.30, 2),
                "TikTok & Çok Kanallı Remarketing": round(monthly_budget * 0.10, 2),
                "Retention & Sadakat (Klaviyo/VIP)": round(monthly_budget * 0.10, 2)
            },
            "strategic_milestones": [
                "Haftalık bütçe pacing ile kazanan setlerde 48 saatte bir %15-20 dikey bütçe artışı.",
                "Klaviyo retention cirosunun toplam şirket cirosunun %25'ine ulaştırılması.",
                "First-party customer match listeleri ile lookalike ve pmax kitle sinyallerinin zenginleştirilmesi.",
                "POAS ve MER optimizasyonuyla şirketin net katkı marjının (CM3) maksimize edilmesi."
            ],
            "target_blended_roas": 3.4
        }

        kpi_milestones = {
            "day_30_target": "500 Sipariş, 2.0x MER, %8.0 CAPI EMQ",
            "day_60_target": "1400 Sipariş, 2.8x MER, +%20 AOV Artışı",
            "day_90_target": "2800 Sipariş, 3.4x MER, LTV:CAC >= 3.5x"
        }

        return MediaFlightPlan(
            monthly_budget=monthly_budget,
            total_90_day_budget=total_90,
            phase_1_days_1_30=p1,
            phase_2_days_31_60=p2,
            phase_3_days_61_90=p3,
            kpi_milestones=kpi_milestones
        )

    def generate_google_demand_gen_blueprint(
        self,
        analysis: Dict[str, Any],
        monthly_budget: float = 30000.0
    ) -> GoogleDemandGenBlueprint:
        """
        Generates Google Demand Gen multi-format blueprint (YouTube Shorts, Discover, Gmail).
        """
        brand_info = analysis.get("brand_info", {})
        brand_name = brand_info.get("brand_name") or "Marka"
        products = analysis.get("products", [])
        top_prod = products[0]["name"] if products else "Koleksiyon"

        short_headlines = [
            f"{brand_name} Yeni Sezon"[:40],
            f"{top_prod[:25]} Keşfet"[:40],
            f"{brand_name} Özel Fırsatlar"[:40],
            "Hızlı ve Ücretsiz Kargo"[:40],
            "Hemen Sipariş Ver"[:40]
        ]

        long_headlines = [
            f"{brand_name} ile tarzınızı ve konforunuzu en üst seviyeye taşıyın."[:90],
            f"Özel tasarım {top_prod[:30]} ve çok daha fazlası avantajlı fiyatlarla."[:90],
            f"İlk siparişinize özel indirim ve ayrıcalıklı müşteri deneyimi."[:90]
        ]

        descriptions = [
            f"Trend modeller, yüksek kalite standartları ve güvenli ödeme {brand_name}'de."[:90],
            f"Hemen sepetinizi oluşturun, aynı gün kargo avantajını kaçırmayın."[:90],
            f"Müşteri memnuniyeti garantisi ve 14 gün ücretsiz iade imkanıyla alışverişe başlayın."[:90]
        ]

        video_assets = [
            {"aspect_ratio": "9:16 (Shorts / Reels)", "duration": "15-30s", "role": "Dikey mobil keşif ve ilk 3 saniye kanca odaklı video"},
            {"aspect_ratio": "16:9 (Landscape)", "duration": "30-60s", "role": "YouTube ana sayfa ve in-stream marka hikayesi videosu"},
            {"aspect_ratio": "1:1 (Square)", "duration": "15s", "role": "Discover akışı ürün odaklı video"}
        ]

        image_assets = [
            {"format": "1.91:1 Landscape", "role": "Google Discover ve Gmail tanıtım bannerı"},
            {"format": "1:1 Square", "role": "Ürün vitrin karesi"},
            {"format": "4:5 Portrait", "role": "Mobil tam ekran görseli"}
        ]

        lookalike_segments = [
            {"tier": "Narrow (%1-%2)", "seed": "First-Party 180 Günlük Alıcılar", "objective": "En yüksek dönüşüm verimliliği"},
            {"tier": "Balanced (%2-%5)", "seed": "Sepete Ekleyenler ve Yüksek Oturum Süresi", "objective": "Dengeli ölçekleme"},
            {"tier": "Broad (%5-%10)", "seed": "Pazar İçi (In-Market) Alışverişçiler", "objective": "Maksimum erişim ve pazar payı"}
        ]

        return GoogleDemandGenBlueprint(
            campaign_name=f"{brand_name} - Google Demand Gen (Shorts & Discover)",
            monthly_budget=round(monthly_budget, 2),
            short_headlines=short_headlines,
            long_headlines=long_headlines,
            descriptions=descriptions,
            video_assets=video_assets,
            image_assets=image_assets,
            lookalike_segments=lookalike_segments,
            call_to_action="Şimdi İncele",
            bidding_strategy="Maximize Conversions (Target CPA)"
        )

    def generate_hook_swap_variations(
        self,
        analysis: Dict[str, Any],
        base_creative_name: str = "Kazanan UGC Video"
    ) -> CreativeHookSwapPackage:
        """
        Generates 5 distinct psychological hook variations to defeat creative fatigue
        while preserving the winning video body and call to action.
        """
        brand_info = analysis.get("brand_info", {})
        brand_name = brand_info.get("brand_name") or "Marka"
        products = analysis.get("products", [])
        prod_name = products[0]["name"] if products else "ürünümüz"

        hooks = [
            {
                "angle": "Merak & Kalıp Kırıcı (Curiosity / Pattern Interrupt)",
                "hook_title": "Kimsenin Bahsetmediği Basit Sır",
                "headline_text": "Bunu kimse bilmenizi istemiyor ama... 🤫",
                "visual_action": "Kameraya gizemli yaklaşma, ani ses kısılması ve ekran zoom-in efekti.",
                "voiceover_script": f"Eğer siz de aylardır {prod_name} arayışındaysanız, bilmeniz gereken tek bir gerçek var."
            },
            {
                "angle": "Negatif Uyarı (Negative / Warning)",
                "hook_title": "Bunu Yapmayı Hemen Bırakın",
                "headline_text": f"2026'da hala eski yöntemleri kullanıyorsanız durun! 🛑",
                "visual_action": "Eski kalitesiz yöntemin kırmızı çarpı ile durdurulması.",
                "voiceover_script": "Paranızı ve zamanınızı çöpe atmayı bırakın. Bu hatayı neredeyse herkes yapıyor."
            },
            {
                "angle": "Kronik Acı / Problem (Pain-Point Question)",
                "hook_title": "Siz de Bu Sorundan Bıktınız mı?",
                "headline_text": f"Her gün bu sorunla uğraşmaktan yorulmadınız mı?",
                "visual_action": "Kullanıcının yaşadığı sıkıntılı anın gerçekçi ve filtresiz canlandırılması.",
                "voiceover_script": f"Sürekli aynı hüsranı yaşamaktan yorulduysanız, {brand_name} ile tanışma vaktiniz geldi."
            },
            {
                "angle": "Müşteri İtirafı (Social Proof / Customer Confession)",
                "hook_title": "Başta İnanmamıştım Ama...",
                "headline_text": "3. günde şok oldum! Neden herkesin bunu konuştuğunu anladım 😱",
                "visual_action": "Doğal selfie açısıyla kutu açılımı ve hayran kalma reaksiyonu.",
                "voiceover_script": f"Sosyal medyada sürekli görüyordum, abartıldığını sanmıştım. Denedikten sonra tüm fikrim değişti."
            },
            {
                "angle": "Dönüşüm / Öncesi-Sonrası (Transformation)",
                "hook_title": "Eski Durum vs Yeni Durum",
                "headline_text": "Aralarındaki farka inanamayacaksınız! ✨",
                "visual_action": "Bölünmüş ekran (Split-screen) ile anlık dramatik sonuç kıyaslaması.",
                "voiceover_script": f"Sadece 1 haftalık kullanımdan sonra ortaya çıkan farka siz de şaşıracaksınız."
            }
        ]

        fatigue_signals = [
            "Sıklık (Frequency) 7 günlük dönemde > 3.2 seviyesinde.",
            "Tıklama Oranı (CTR) son 3 günde %25'ten fazla düşüş gösterdi.",
            "Thumbstop Rate (İlk 3 saniye izleme oranı) %25'in altına indi."
        ]

        protocol = (
            "Hook-Swap Test Protokolü: Kazanan videonun gövdesi (Problem, Çözüm, Demo, CTA) birebir korunarak "
            "bu 5 kanca ayrı test setlerinde 5 gün boyunca eşit bütçeyle yarıştırılır. En yüksek Thumbstop ve "
            "en düşük CPA getiren 2 varyant ana ölçekleme kampanyasına taşınır."
        )

        return CreativeHookSwapPackage(
            campaign_name=f"{brand_name} - Hook Swap Kreatif Yenileme Paketi",
            winning_creative_id=base_creative_name,
            winning_body_core_concept=f"{brand_name} {prod_name} Değer Önerisi ve Çözüm Gösterimi",
            fatigue_indicators_triggered=fatigue_signals,
            hook_variants=hooks,
            recommended_test_duration_days=5,
            actionable_testing_protocol=protocol
        )

    def generate_agency_onboarding_sla(self, brand_name: str = "Marka") -> AgencySLAAndOnboardingChecklist:
        """
        Generates 30-day Client Onboarding SLA roadmap with strict decision gates.
        """
        milestones = [
            AgencyOnboardingMilestone(
                day_range="1 - 3. Gün",
                phase_name="Varlık Erişimi ve Yetkilendirme",
                sla_gate="Erişim Kapısı",
                deliverables=[
                    "Meta Business Manager ortaklık bağlantısı (Pixel, Katalog, Sayfa, Reklam Hesabı).",
                    "Google Ads MCC bağlantısı, GA4 ve Search Console yönetici yetkileri.",
                    "E-ticaret altyapısı salt okunur veri erişimi ve Klaviyo CRM API anahtarları."
                ],
                status="TAMAMLANDI"
            ),
            AgencyOnboardingMilestone(
                day_range="4 - 7. Gün",
                phase_name="Adli Altyapı ve MarTech Denetimi",
                sla_gate="Veri Güvenliği Kapısı (Data Gate)",
                deliverables=[
                    "GTM Server-side (sGTM) ve GA4 e-ticaret purchase veri katmanı doğrulaması.",
                    "Meta Conversions API (CAPI) sunucu tekilleştirmesi (event_id) testi (EMQ >= 8.0).",
                    "COGS, kargo, ambalaj ve POS maliyetleriyle Breakeven ROAS ve Target ROAS sözleşmesi."
                ],
                status="TAMAMLANDI"
            ),
            AgencyOnboardingMilestone(
                day_range="8 - 14. Gün",
                phase_name="Kreatif Üretimi, 3:2:2 Test ve Lansman",
                sla_gate="Teknik Trafik Kapısı (CRO Gate)",
                deliverables=[
                    "3:2:2 Dynamic Creative test paketlerinin hazırlanması ve yayına alınması.",
                    "BOGO veya sepet teşvik basamaklarının (kargo/hediye eşikleri) siteye tanımlanması.",
                    "PMax varlık grupları, negatif anahtar kelime kalkanı ve Klaviyo terk edilmiş sepet akışları."
                ],
                status="BEKLEMEDE"
            ),
            AgencyOnboardingMilestone(
                day_range="15 - 30. Gün",
                phase_name="Haftalık Büyüme Sprintleri ve Ölçekleme",
                sla_gate="Ölçekleme Kapısı (Scaling Gate)",
                deliverables=[
                    "Pazartesi-Cuma haftalık sprint ritmi: Bütçe pacing kontrolü ve yorgun kreatif rotasyonu.",
                    "Kazanan kancaların Post ID ile Meta ASC ve PMax ana kampanyalarına aktarılması.",
                    "Looker Studio gerçek zamanlı ciro, MER ve POAS panosunun teslimi."
                ],
                status="BEKLEMEDE"
            )
        ]

        rules = [
            "Veri Güvenliği Kuralı: GA4 ve Meta CAPI tekilleştirmesi doğrulanmadan hiçbir reklam yayına alınamaz.",
            "Kârlılık Kuralı: Breakeven ROAS ve CM3 hesaplanmadan bütçe girilemez.",
            "CRO Kuralı: Mobil LCP > 3.5s veya ödeme adımı bozuk olan sayfalara doğrudan ücretli trafik yönlendirilemez.",
            "Bütçe Artış Kuralı: Dikey ölçeklemede bütçe 48 saatte bir en fazla %20 artırılır."
        ]

        return AgencySLAAndOnboardingChecklist(
            brand_name=brand_name,
            target_launch_date="Lansman: Onboarding Sonrası 8. Gün",
            milestones=milestones,
            fail_closed_rules=rules
        )

    def generate_full_package(self, analysis: Dict[str, Any], monthly_budget: float = 100000.0) -> Dict[str, Any]:
        brand_info = analysis.get("brand_info", {})
        brand_name = brand_info.get("brand_name", "Marka")
        return {
            "brand": brand_name,
            "relational_campaigns": self.generate_relational_campaigns(analysis),
            "multichannel_ad_plans": self.generate_multichannel_ad_plans(analysis),
            "unit_economics": self.generate_unit_economics_plan(analysis, monthly_budget=monthly_budget),
            "meta_asc_blueprint": self.generate_meta_asc_blueprint(analysis, monthly_meta_budget=monthly_budget * 0.55).model_dump(),
            "google_pmax_blueprint": self.generate_google_pmax_blueprint(analysis, monthly_google_budget=monthly_budget * 0.30).model_dump(),
            "google_demand_gen_blueprint": self.generate_google_demand_gen_blueprint(analysis, monthly_budget=monthly_budget * 0.15).model_dump(),
            "creative_hook_swap_package": self.generate_hook_swap_variations(analysis).model_dump(),
            "agency_onboarding_sla": self.generate_agency_onboarding_sla(brand_name).model_dump(),
            "retention_flows": [f.model_dump() for f in self.generate_retention_flows(brand_info)],
            "media_flight_plan": self.generate_30_60_90_flight_plan(monthly_budget=monthly_budget, analysis=analysis).model_dump()
        }


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
