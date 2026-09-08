"""
Media Agency Unit Economics & Percentage Calculator.
Calculates ROAS, Breakeven ROAS, Target ROAS, Max Allowable CPA, POAS, MER,
Funnel Budget Allocation (% TOFU/MOFU/BOFU/Retention), Promotional Margin Simulations,
and Conversion Funnel Health Diagnostics.
"""

import math
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FunnelBudgetTier(BaseModel):
    stage: str = Field(..., description="TOFU | MOFU | BOFU | RETENTION")
    name: str = Field(..., description="Human readable stage name")
    allocation_pct: float = Field(..., description="Percentage of total budget allocated")
    amount: float = Field(..., description="Calculated monetary allocation")
    focus_objective: str = Field(..., description="Tactical objective of this stage")
    recommended_channels: List[str] = Field(default_factory=list)


class FunnelBudgetPlan(BaseModel):
    strategy: str = Field(..., description="balanced | scale | harvest")
    total_budget: float
    currency: str = "₺"
    tiers: List[FunnelBudgetTier] = Field(default_factory=list)


class PromotionalMarginSimulation(BaseModel):
    promotion_type: str = Field(..., description="BOGO | CROSS_DISCOUNT | CART_THRESHOLD")
    headline: str
    normal_revenue: float
    promotional_revenue: float
    total_cogs: float
    additional_expenses: float
    net_gross_profit: float
    net_gross_margin_pct: float
    effective_discount_pct: float
    margin_protected: bool
    verdict: str


class FunnelHealthScorecard(BaseModel):
    impressions: int
    clicks: int
    ctr_pct: float
    cpc: float
    cpm: float
    add_to_carts: int
    atc_rate_pct: float
    checkout_initiations: int
    checkout_abandonment_rate_pct: float
    orders: int
    cvr_pct: float
    ad_spend: float
    cpa: float
    revenue: float
    aov: float
    roas: float
    roas_pct: float
    poas: Optional[float] = None
    contribution_margin_pct: Optional[float] = None
    leading_indicators_healthy: bool
    creative_fatigue_alert: bool
    diagnostic_summary: List[str] = Field(default_factory=list)


class LTVPaybackScorecard(BaseModel):
    aov: float
    purchase_frequency_annual: float
    gross_margin_pct: float
    annual_churn_rate_pct: float
    cac: float
    ltv: float
    ltv_to_cac_ratio: float
    payback_period_months: float
    health_status: str  # DANGER | FRAGILE | OPTIMAL | UNDERINVESTING
    strategic_recommendation: str


class ContributionMarginAnalysis(BaseModel):
    revenue: float
    cogs: float
    logistics_and_shipping: float
    payment_gateway_fee: float
    ad_spend: float
    cm1_gross_profit: float
    cm1_pct: float
    cm2_operational_profit: float
    cm2_pct: float
    cm3_contribution_profit: float
    cm3_pct: float
    is_unit_profitable: bool
    verdict: str


class NCACAnalysis(BaseModel):
    total_ad_spend: float
    total_orders: int
    new_customers: int
    returning_customers: int
    blended_cac: float
    ncac: float
    new_customer_order_ratio_pct: float
    organic_cannibalization_risk: bool
    channel_efficiency_rating: str


class CreativeTestingBudgetEstimate(BaseModel):
    cpm: float
    expected_ctr_pct: float
    expected_cvr_pct: float
    target_conversions_per_variant: int
    variant_count: int
    required_clicks_per_variant: int
    required_impressions_per_variant: int
    spend_per_variant: float
    total_testing_budget_needed: float
    testing_duration_days: int
    recommended_daily_budget: float
    testing_protocol_notes: str


class RFMSegmentResult(BaseModel):
    segment_name: str
    customer_count: int
    percentage_of_base: float
    recommended_budget_share_pct: float
    tactical_action: str
    recommended_channels: List[str] = Field(default_factory=list)


class DiscountBreakEvenSimulation(BaseModel):
    gross_margin_pct: float
    discount_pct: float
    current_orders: int
    current_aov: float
    discounted_aov: float
    required_volume_increase_pct: float
    break_even_order_count: int
    original_gross_profit: float
    discounted_gross_profit_at_breakeven: float
    margin_preserved: bool
    verdict: str


class POASNetProfitSimulation(BaseModel):
    gross_revenue: float
    ad_spend: float
    cogs: float
    logistics_and_shipping: float
    packaging_and_handling: float
    payment_gateway_rate_pct: float
    payment_gateway_fee: float
    return_refund_rate_pct: float
    refund_amount: float
    net_revenue: float
    net_gross_profit: float
    net_operational_profit: float
    net_profit_after_ads: float
    poas: float
    blended_roas: float
    net_margin_pct: float
    is_profitable: bool
    currency: str = "₺"
    verdict: str


class MarketingEfficiencyRatioAnalysis(BaseModel):
    total_net_revenue: float
    total_ad_spend: float
    blended_mer: float
    channel_reported_revenues: Dict[str, float] = Field(default_factory=dict)
    sum_reported_revenue: float
    attribution_overlap_factor: float
    overreporting_pct: float
    efficiency_tier: str  # SCALE_AGGRESSIVELY | STABLE_PROFIT | MONITOR_CLOSELY | HIGH_RISK_DRAIN
    strategic_directive: str


class ABTestSignificanceAnalysis(BaseModel):
    visitors_control: int
    conversions_control: int
    cvr_control_pct: float
    visitors_variant: int
    conversions_variant: int
    cvr_variant_pct: float
    relative_lift_pct: float
    z_score: float
    p_value: float
    confidence_level_pct: float
    is_statistically_significant: bool
    winner: str  # VARIANT | CONTROL | NO_WINNER
    verdict: str


class BudgetPacingAndRunRateAnalysis(BaseModel):
    monthly_budget: float
    days_elapsed: int
    days_in_month: int
    current_spend: float
    expected_spend_to_date: float
    actual_daily_burn: float
    target_daily_budget: float
    projected_end_of_month_spend: float
    pacing_ratio: float
    pacing_status: str  # ON_TRACK | OVERSPENDING | UNDERSPENDING
    recommended_adjusted_daily_budget: float
    currency: str = "₺"
    actionable_recommendation: str


FunnelBudgetTier.model_rebuild()
FunnelBudgetPlan.model_rebuild()
PromotionalMarginSimulation.model_rebuild()
FunnelHealthScorecard.model_rebuild()
LTVPaybackScorecard.model_rebuild()
ContributionMarginAnalysis.model_rebuild()
NCACAnalysis.model_rebuild()
CreativeTestingBudgetEstimate.model_rebuild()
RFMSegmentResult.model_rebuild()
DiscountBreakEvenSimulation.model_rebuild()
POASNetProfitSimulation.model_rebuild()
MarketingEfficiencyRatioAnalysis.model_rebuild()
ABTestSignificanceAnalysis.model_rebuild()
BudgetPacingAndRunRateAnalysis.model_rebuild()


class MediaAgencyCalculator:
    """Quantitative performance and unit economics calculator for digital media agencies."""

    @staticmethod
    def calculate_breakeven_roas(gross_margin_pct: float) -> float:
        """
        Calculates the minimum ROAS required to not lose money on ad spend.
        Breakeven ROAS = 1 / (Gross Margin % / 100)
        E.g. 50% gross margin -> Breakeven ROAS = 2.0 (or 200%).
        """
        if gross_margin_pct <= 0:
            return 999.0
        margin_decimal = gross_margin_pct / 100.0 if gross_margin_pct > 1.0 else gross_margin_pct
        if margin_decimal <= 0:
            return 999.0
        return round(1.0 / margin_decimal, 2)

    @staticmethod
    def calculate_target_roas(gross_margin_pct: float, target_net_margin_pct: float) -> float:
        """
        Calculates the ROAS needed to guarantee a specific net profit margin.
        Target ROAS = 1 / (Gross Margin - Target Net Margin)
        E.g. 60% gross margin, 15% net profit target -> 1 / (0.60 - 0.15) = 2.22x.
        """
        gm = gross_margin_pct / 100.0 if gross_margin_pct > 1.0 else gross_margin_pct
        nm = target_net_margin_pct / 100.0 if target_net_margin_pct > 1.0 else target_net_margin_pct

        effective_spread = gm - nm
        if effective_spread <= 0.05:
            # If net profit target exceeds or equals gross margin, unsustainable
            return round(1.0 / max(0.01, effective_spread), 2)
        return round(1.0 / effective_spread, 2)

    @staticmethod
    def calculate_max_allowable_cpa(
        aov: float,
        gross_margin_pct: float,
        target_profit_per_order: float = 0.0
    ) -> float:
        """
        Calculates maximum acquisition cost (CAC / CPA) before order becomes unprofitable.
        Max Allowable CPA = (AOV * Gross Margin %) - Target Profit per Order
        """
        gm = gross_margin_pct / 100.0 if gross_margin_pct > 1.0 else gross_margin_pct
        gross_profit = aov * gm
        max_cpa = gross_profit - target_profit_per_order
        return round(max(0.0, max_cpa), 2)

    @staticmethod
    def calculate_poas(gross_profit: float, ad_spend: float) -> float:
        """
        Profit On Ad Spend = Gross Profit / Ad Spend.
        Values > 1.0 indicate positive gross contribution.
        """
        if ad_spend <= 0:
            return 0.0
        return round(gross_profit / ad_spend, 2)

    @staticmethod
    def calculate_mer(total_revenue: float, total_marketing_spend: float) -> float:
        """
        Marketing Efficiency Ratio (Blended ROAS) = Total Revenue / Total Marketing Spend.
        Measures holistic brand health across all touchpoints.
        """
        if total_marketing_spend <= 0:
            return 0.0
        return round(total_revenue / total_marketing_spend, 2)

    @staticmethod
    def calculate_funnel_budget_split(
        total_budget: float,
        strategy: str = "balanced",
        currency: str = "₺"
    ) -> FunnelBudgetPlan:
        """
        Splits digital ad budget into Top, Middle, Bottom of funnel and Retention.
        Strategies:
        - balanced: 55% TOFU, 25% MOFU, 15% BOFU, 5% Retention
        - scale: 70% TOFU, 15% MOFU, 10% BOFU, 5% Retention
        - harvest: 35% TOFU, 30% MOFU, 25% BOFU, 10% Retention
        """
        strat = strategy.lower().strip()
        if strat == "scale":
            splits = [
                ("TOFU", "Top of Funnel (Soğuk Kitle / Keşif)", 70.0,
                 "Geniş kitle edinimi, video kancaları, pazar payı kazanımı",
                 ["Meta Reels/Video", "TikTok Ads", "Google Demand Gen"]),
                ("MOFU", "Middle of Funnel (Ilık Kitle / İnceleme)", 15.0,
                 "Etkileşim, sosyal kanıt, karşılaştırma ve inceleme trafiği",
                 ["Meta Carousel", "Google Arama (Ticari Niyet)", "YouTube"]),
                ("BOFU", "Bottom of Funnel (Sıcak Kitle / Dönüşüm)", 10.0,
                 "Dinamik yeniden pazarlama (DPA), terk edilen sepet kazanımı",
                 ["Meta Dynamic Ads (DPA)", "Google RSA (Marka + İşlemsel)", "Google PMax"]),
                ("RETENTION", "Sadakat & LTV (Mevcut Müşteri)", 5.0,
                 "Çapraz satış, ikinci sipariş teşviki, VIP teklifler",
                 ["E-posta Otomasyonu", "SMS", "Meta Custom Audience (Mevcut Müşteri)"])
            ]
        elif strat == "harvest":
            splits = [
                ("TOFU", "Top of Funnel (Soğuk Kitle / Keşif)", 35.0,
                 "Asgari marka varlığı ve seçici kitle filtreleme",
                 ["Meta Video", "Google Search Non-Brand"]),
                ("MOFU", "Middle of Funnel (Ilık Kitle / İnceleme)", 30.0,
                 "Birikmiş ilgiyi sıcak teklife hazırlama",
                 ["Meta Carousel", "Google Search Intent"]),
                ("BOFU", "Bottom of Funnel (Sıcak Kitle / Dönüşüm)", 25.0,
                 "Agresif dönüşüm ve kâr hasadı",
                 ["Meta DPA", "Google Search Brand + PMax"]),
                ("RETENTION", "Sadakat & LTV (Mevcut Müşteri)", 10.0,
                 "Yüksek LTV segmentlerine özel indirim ve sepet tamamlama",
                 ["Klaviyo/Omnisend Flows", "Meta VIP Segment"])
            ]
        else:  # balanced
            splits = [
                ("TOFU", "Top of Funnel (Soğuk Kitle / Keşif)", 55.0,
                 "Sürekli yeni müşteri akışı ve piksel öğrenim tabanı",
                 ["Meta Reels/UGC", "TikTok Ads", "Google Search Non-Brand"]),
                ("MOFU", "Middle of Funnel (Ilık Kitle / İnceleme)", 25.0,
                 "Açılış sayfası eğitimi, kullanıcı yorumları ve incelemeler",
                 ["Meta Carousel", "Google Search (Kategori/Niyet)"]),
                ("BOFU", "Bottom of Funnel (Sıcak Kitle / Dönüşüm)", 15.0,
                 "Sepet terk geri kazanımı ve doğrudan satın alma teklifi",
                 ["Meta Dynamic Ads (Catalog DPA)", "Google RSA & Shopping"]),
                ("RETENTION", "Sadakat & LTV (Mevcut Müşteri)", 5.0,
                 "Tekrar satın alma döngüsü ve AOV artırıcı paketler",
                 ["E-posta / SMS", "Meta LTV Audiences"])
            ]

        tiers: List[FunnelBudgetTier] = []
        for stage_code, stage_name, pct, focus, channels in splits:
            amt = round(total_budget * (pct / 100.0), 2)
            tiers.append(FunnelBudgetTier(
                stage=stage_code,
                name=stage_name,
                allocation_pct=pct,
                amount=amt,
                focus_objective=focus,
                recommended_channels=channels
            ))

        return FunnelBudgetPlan(
            strategy=strategy,
            total_budget=total_budget,
            currency=currency,
            tiers=tiers
        )

    @staticmethod
    def simulate_bogo_margin(
        hero_price: float,
        hero_cogs: float,
        gift_price: float,
        gift_cogs: float,
        shipping_cost: float = 0.0,
        extra_packaging: float = 0.0
    ) -> PromotionalMarginSimulation:
        """
        Simulates unit margin for a BOGO promotion (Primary Product + Free Gift).
        Validates whether the margin remains safe (>= 50%).
        """
        normal_revenue = hero_price + gift_price
        promotional_revenue = hero_price  # customer only pays for hero
        total_cogs = hero_cogs + gift_cogs
        additional_expenses = shipping_cost + extra_packaging

        net_profit = promotional_revenue - (total_cogs + additional_expenses)
        net_margin_pct = (net_profit / promotional_revenue * 100.0) if promotional_revenue > 0 else 0.0
        effective_discount_pct = (gift_price / normal_revenue * 100.0) if normal_revenue > 0 else 0.0

        is_protected = net_margin_pct >= 50.0
        if is_protected:
            verdict = "UYGUN: Brüt marj %50 üzerinde korundu; güvenle uygulanabilir BOGO promosyonu."
        elif net_margin_pct >= 35.0:
            verdict = "DİKKAT: Brüt marj %35-%50 bandında; yalnızca yüksek hacimli kitle edinimi için sınırlı süreyle uygulanabilir."
        else:
            verdict = "RİSKLİ: Brüt marj %35 altına düştü; bu hediye seçimiyle BOGO yapılması kârlılığı eritir. Daha düşük maliyetli hediye seçilmelidir."

        return PromotionalMarginSimulation(
            promotion_type="BOGO",
            headline=f"1 Alana 1 Hediye (Hero: {hero_price:.2f}, Hediye: {gift_price:.2f})",
            normal_revenue=round(normal_revenue, 2),
            promotional_revenue=round(promotional_revenue, 2),
            total_cogs=round(total_cogs, 2),
            additional_expenses=round(additional_expenses, 2),
            net_gross_profit=round(net_profit, 2),
            net_gross_margin_pct=round(net_margin_pct, 2),
            effective_discount_pct=round(effective_discount_pct, 2),
            margin_protected=is_protected,
            verdict=verdict
        )

    @staticmethod
    def simulate_bundle_discount(
        hero_price: float,
        complementary_price: float,
        discount_pct: float = 10.0,
        cogs_pct: float = 35.0
    ) -> PromotionalMarginSimulation:
        """
        Simulates unit margin for a Cross-Sell bundle discount.
        E.g. Buy Product A and get Product B with 10% discount.
        """
        normal_revenue = hero_price + complementary_price
        discounted_comp_price = complementary_price * (1.0 - (discount_pct / 100.0))
        promotional_revenue = hero_price + discounted_comp_price

        total_cogs = (hero_price * (cogs_pct / 100.0)) + (complementary_price * (cogs_pct / 100.0))
        net_profit = promotional_revenue - total_cogs
        net_margin_pct = (net_profit / promotional_revenue * 100.0) if promotional_revenue > 0 else 0.0
        effective_discount = ((normal_revenue - promotional_revenue) / normal_revenue * 100.0) if normal_revenue > 0 else 0.0

        is_protected = net_margin_pct >= 50.0
        verdict = f"Sepet genişletici bundle (%{discount_pct:.0f} indirim). Net Marj: %{net_margin_pct:.1f}. Başarılı çapraz satış yapısı."

        return PromotionalMarginSimulation(
            promotion_type="CROSS_DISCOUNT",
            headline=f"Çapraz Satış Paketi (%{discount_pct:.0f} İndirimli Tamamlayıcı Ürün)",
            normal_revenue=round(normal_revenue, 2),
            promotional_revenue=round(promotional_revenue, 2),
            total_cogs=round(total_cogs, 2),
            additional_expenses=0.0,
            net_gross_profit=round(net_profit, 2),
            net_gross_margin_pct=round(net_margin_pct, 2),
            effective_discount_pct=round(effective_discount, 2),
            margin_protected=is_protected,
            verdict=verdict
        )

    @staticmethod
    def simulate_cart_thresholds(
        current_aov: float,
        free_shipping_mult: float = 1.25,
        gift_mult: float = 1.50,
        currency: str = "₺"
    ) -> Dict[str, Any]:
        """
        Calculates optimal AOV incentive thresholds.
        Threshold 1 (Free Shipping): AOV * 1.25
        Threshold 2 (Free Gift / Extra % off): AOV * 1.50
        """
        t1 = round(current_aov * free_shipping_mult, -1)
        t2 = round(current_aov * gift_mult, -1)

        return {
            "current_aov": current_aov,
            "currency": currency,
            "tier_1_free_shipping": {
                "multiplier": free_shipping_mult,
                "threshold_amount": t1,
                "rationale": f"Sepeti {currency}{t1:.0f} üzerine çıkararak kargo maliyetini sübvanse eden psikolojik eşik."
            },
            "tier_2_tiered_gift": {
                "multiplier": gift_mult,
                "threshold_amount": t2,
                "rationale": f"Sepeti {currency}{t2:.0f} üzerine çıkararak yüksek marjlı AOV basamağı oluşturan hediye eşiği."
            }
        }

    @staticmethod
    def analyze_conversion_funnel(
        impressions: int,
        clicks: int,
        ad_spend: float,
        add_to_carts: int,
        checkouts: int,
        orders: int,
        revenue: float,
        cogs: float = 0.0
    ) -> FunnelHealthScorecard:
        """
        Diagnoses complete e-commerce conversion funnel and identifies drop-off friction points.
        """
        ctr_pct = (clicks / impressions * 100.0) if impressions > 0 else 0.0
        cpc = (ad_spend / clicks) if clicks > 0 else 0.0
        cpm = (ad_spend / impressions * 1000.0) if impressions > 0 else 0.0

        atc_rate_pct = (add_to_carts / clicks * 100.0) if clicks > 0 else 0.0
        abandonment_pct = (1.0 - (orders / checkouts)) * 100.0 if checkouts > 0 else 0.0
        cvr_pct = (orders / clicks * 100.0) if clicks > 0 else 0.0

        cpa = (ad_spend / orders) if orders > 0 else 0.0
        aov = (revenue / orders) if orders > 0 else 0.0
        roas = (revenue / ad_spend) if ad_spend > 0 else 0.0
        roas_pct = roas * 100.0

        gross_profit = revenue - cogs if cogs > 0 else revenue * 0.55
        poas = round(gross_profit / ad_spend, 2) if ad_spend > 0 else 0.0
        contrib_margin_pct = round((gross_profit - ad_spend) / revenue * 100.0, 2) if revenue > 0 else 0.0

        diagnostics = []
        leading_healthy = True
        creative_fatigue = False

        if ctr_pct < 1.2:
            diagnostics.append(f"Düşük CTR (%{ctr_pct:.2f}): Kreatif kancası ve hedefleme zayıf; tıklama maliyeti yüksek.")
            leading_healthy = False
            creative_fatigue = True
        else:
            diagnostics.append(f"Sağlıklı CTR (%{ctr_pct:.2f}): Reklam kreatifleri kitle ilgisini yakalıyor.")

        if atc_rate_pct < 6.0:
            diagnostics.append(f"Kritik ATC Düşüklüğü (%{atc_rate_pct:.1f}): Ürün sayfasında (PDP) teklif, fiyat veya görsel sürtünmesi var.")
            leading_healthy = False
        else:
            diagnostics.append(f"Güçlü Sepete Ekleme (%{atc_rate_pct:.1f}): Açılış sayfası teklifi etkili.")

        if abandonment_pct > 75.0:
            diagnostics.append(f"Yüksek Sepet Terki (%{abandonment_pct:.1f}): Ödeme adımında gizli kargo, zorunlu üyelik veya ödeme altyapısı sürtünmesi tespit edildi.")
        else:
            diagnostics.append(f"Dengeli Sepet Tamamlama (%{100 - abandonment_pct:.1f}): Ödeme akışı akıcı.")

        if roas >= 3.0:
            diagnostics.append(f"Yüksek ROAS ({roas:.2f}x): Kârlı ve ölçeklenebilir kampanya performansı.")
        elif roas >= 1.8:
            diagnostics.append(f"Ilımlı ROAS ({roas:.2f}x): Kampanya başa baş seviyesinde; AOV basamakları ile optimize edilmeli.")
        else:
            diagnostics.append(f"Tehlikeli ROAS ({roas:.2f}x): Harcama sermayeyi tüketiyor; acil kreatif ve teklif yenilenmeli.")

        return FunnelHealthScorecard(
            impressions=impressions,
            clicks=clicks,
            ctr_pct=round(ctr_pct, 2),
            cpc=round(cpc, 2),
            cpm=round(cpm, 2),
            add_to_carts=add_to_carts,
            atc_rate_pct=round(atc_rate_pct, 2),
            checkout_initiations=checkouts,
            checkout_abandonment_rate_pct=round(abandonment_pct, 2),
            orders=orders,
            cvr_pct=round(cvr_pct, 2),
            ad_spend=round(ad_spend, 2),
            cpa=round(cpa, 2),
            revenue=round(revenue, 2),
            aov=round(aov, 2),
            roas=round(roas, 2),
            roas_pct=round(roas_pct, 2),
            poas=poas,
            contribution_margin_pct=contrib_margin_pct,
            leading_indicators_healthy=leading_healthy,
            creative_fatigue_alert=creative_fatigue,
            diagnostic_summary=diagnostics
        )

    @staticmethod
    def calculate_ltv_and_payback(
        aov: float,
        purchase_frequency_annual: float,
        gross_margin_pct: float,
        annual_churn_rate_pct: float,
        cac: float
    ) -> LTVPaybackScorecard:
        """
        Calculates Customer Lifetime Value (LTV), LTV:CAC ratio, and CAC Payback Period (in months).
        LTV = (AOV * Purchase Frequency * Gross Margin %) / Churn Rate %
        Payback Period = CAC / [AOV * Gross Margin * (Purchase Frequency / 12)]
        """
        gm = gross_margin_pct / 100.0 if gross_margin_pct > 1.0 else gross_margin_pct
        churn = annual_churn_rate_pct / 100.0 if annual_churn_rate_pct > 1.0 else annual_churn_rate_pct
        churn = max(0.01, churn)

        ltv = round((aov * purchase_frequency_annual * gm) / churn, 2)
        safe_cac = max(0.01, cac)
        ltv_to_cac = round(ltv / safe_cac, 2)

        monthly_margin = aov * gm * (purchase_frequency_annual / 12.0)
        payback_months = round(cac / max(0.01, monthly_margin), 2)

        if ltv_to_cac < 1.0:
            status = "DANGER"
            rec = "ÖLÜMCÜL: Müşteri edinme maliyeti LTV'yi aşıyor (LTV:CAC < 1.0). Her edinim nakit yakıyor; edinim durdurulmalı veya teklif revize edilmeli."
        elif ltv_to_cac < 3.0:
            status = "FRAGILE"
            rec = "KIRILGAN: LTV:CAC 1.0-3.0 bandında. Sabit giderler ve operasyon sonrası marj yetersiz kalabilir; AOV basamakları ve e-posta akışları güçlendirilmeli."
        elif ltv_to_cac <= 5.0:
            status = "OPTIMAL"
            rec = "ALTIN DENGE: LTV:CAC 3.0-5.0 bandında; sağlıklı, kârlı ve sürdürülebilir büyüme koridoru. Reklam bütçesi güvenle artırılabilir."
        else:
            status = "UNDERINVESTING"
            rec = "DÜŞÜK YATIRIM: LTV:CAC > 5.0. Büyüme fırsatı kaçırılıyor; daha agresif pazar payı kazanımı için CAC toleransı ve reklam bütçesi yükseltilmeli."

        return LTVPaybackScorecard(
            aov=round(aov, 2),
            purchase_frequency_annual=round(purchase_frequency_annual, 2),
            gross_margin_pct=round(gross_margin_pct, 2),
            annual_churn_rate_pct=round(annual_churn_rate_pct, 2),
            cac=round(cac, 2),
            ltv=ltv,
            ltv_to_cac_ratio=ltv_to_cac,
            payback_period_months=payback_months,
            health_status=status,
            strategic_recommendation=rec
        )

    @staticmethod
    def calculate_contribution_margins(
        revenue: float,
        cogs: float,
        logistics_and_shipping: float,
        payment_gateway_fee: float,
        ad_spend: float
    ) -> ContributionMarginAnalysis:
        """
        Calculates 3-tier Contribution Margins:
        CM1 = Revenue - COGS (Gross Profit)
        CM2 = CM1 - (Logistics + Payment Fees) (Operational Profit)
        CM3 = CM2 - Ad Spend (Pazarlama Faaliyet Net Katkısı)
        """
        cm1 = revenue - cogs
        cm1_pct = round((cm1 / revenue * 100.0) if revenue > 0 else 0.0, 2)

        cm2 = cm1 - (logistics_and_shipping + payment_gateway_fee)
        cm2_pct = round((cm2 / revenue * 100.0) if revenue > 0 else 0.0, 2)

        cm3 = cm2 - ad_spend
        cm3_pct = round((cm3 / revenue * 100.0) if revenue > 0 else 0.0, 2)

        is_profitable = cm3 > 0
        if is_profitable and cm3_pct >= 15.0:
            verdict = f"SAĞLIKLI: Pazarlama sonrası birim kârlılık yüksek (%{cm3_pct:.1f}). Kampanya ölçeklenebilir."
        elif is_profitable:
            verdict = f"DAR MARJ: Birim kârlılık pozitif fakat kırılgan (%{cm3_pct:.1f}). İade ve lojistik maliyetleri optimize edilmeli."
        else:
            verdict = f"KRİTİK ZARAR: Reklam harcaması operasyonel marjı tüketiyor (CM3: ₺{cm3:.2f}, %{cm3_pct:.1f}). Birim başına para kaybediliyor."

        return ContributionMarginAnalysis(
            revenue=round(revenue, 2),
            cogs=round(cogs, 2),
            logistics_and_shipping=round(logistics_and_shipping, 2),
            payment_gateway_fee=round(payment_gateway_fee, 2),
            ad_spend=round(ad_spend, 2),
            cm1_gross_profit=round(cm1, 2),
            cm1_pct=cm1_pct,
            cm2_operational_profit=round(cm2, 2),
            cm2_pct=cm2_pct,
            cm3_contribution_profit=round(cm3, 2),
            cm3_pct=cm3_pct,
            is_unit_profitable=is_profitable,
            verdict=verdict
        )

    @staticmethod
    def calculate_ncac(
        total_ad_spend: float,
        total_orders: int,
        new_customers: int,
        returning_customers: Optional[int] = None
    ) -> NCACAnalysis:
        """
        Calculates Blended CAC vs New Customer Acquisition Cost (nCAC).
        Detects brand cannibalization if nCAC > 1.6 * Blended CAC.
        """
        tot_orders = max(1, total_orders)
        new_cust = max(1, new_customers)
        ret_cust = returning_customers if returning_customers is not None else max(0, tot_orders - new_cust)

        blended_cac = round(total_ad_spend / tot_orders, 2)
        ncac = round(total_ad_spend / new_cust, 2)
        new_ratio = round((new_cust / tot_orders) * 100.0, 2)
        cannibalization = ncac > (blended_cac * 1.6)

        if cannibalization:
            rating = "YÜKSEK YAMYAMLIK: Reklamlar yeni müşteri yerine mevcut müşteriyi hedefliyor. Kampanyalarda mevcut müşteri listesi hariç tutulmalı (Exclude Customers)."
        else:
            rating = "DENGELİ EDİNİM: Yeni müşteri maliyeti kabul edilebilir oranda; edinim motoru yeni kitleye ulaşıyor."

        return NCACAnalysis(
            total_ad_spend=round(total_ad_spend, 2),
            total_orders=tot_orders,
            new_customers=new_cust,
            returning_customers=ret_cust,
            blended_cac=blended_cac,
            ncac=ncac,
            new_customer_order_ratio_pct=new_ratio,
            organic_cannibalization_risk=cannibalization,
            channel_efficiency_rating=rating
        )

    @staticmethod
    def calculate_creative_testing_budget(
        cpm: float,
        expected_ctr_pct: float = 1.8,
        expected_cvr_pct: float = 2.5,
        target_conversions_per_variant: int = 30,
        variant_count: int = 7
    ) -> CreativeTestingBudgetEstimate:
        """
        Calculates required sample size, impressions, and budget for 3:2:2 dynamic creative testing.
        """
        safe_cvr = max(0.001, expected_cvr_pct / 100.0)
        safe_ctr = max(0.001, expected_ctr_pct / 100.0)

        clicks_per_var = int(target_conversions_per_variant / safe_cvr)
        impr_per_var = int(clicks_per_var / safe_ctr)
        spend_per_var = round((impr_per_var / 1000.0) * cpm, 2)
        total_budget = round(spend_per_var * variant_count, 2)
        duration_days = 7
        daily_budget = round(total_budget / duration_days, 2)

        notes = (
            f"3:2:2 Test Protokolü: {variant_count} varyantın her biri için {target_conversions_per_variant} dönüşüm "
            f"(~{clicks_per_var} tıklama, ~{impr_per_var} gösterim) hedeflenir. {duration_days} günde tamamlamak için "
            f"günlük ₺{daily_budget:.2f} test hücresi tahsis edilmelidir."
        )

        return CreativeTestingBudgetEstimate(
            cpm=round(cpm, 2),
            expected_ctr_pct=round(expected_ctr_pct, 2),
            expected_cvr_pct=round(expected_cvr_pct, 2),
            target_conversions_per_variant=target_conversions_per_variant,
            variant_count=variant_count,
            required_clicks_per_variant=clicks_per_var,
            required_impressions_per_variant=impr_per_var,
            spend_per_variant=spend_per_var,
            total_testing_budget_needed=total_budget,
            testing_duration_days=duration_days,
            recommended_daily_budget=daily_budget,
            testing_protocol_notes=notes
        )

    @staticmethod
    def segment_rfm_customers(
        total_customer_count: int = 1000,
        avg_aov: float = 850.0
    ) -> List[RFMSegmentResult]:
        """
        Segments customer base into 5 standard RFM behavioral tiers with budget allocation.
        """
        definitions = [
            ("Champions (Şampiyonlar - 555)", 0.12, 10.0,
             "VIP erken erişim, öncelikli kargo, tavsiye programı; reklamlardan hariç tutma.",
             ["Klaviyo VIP Email", "WhatsApp Concierge"]),
            ("Loyal Customers (Sadıklar - 444)", 0.22, 15.0,
             "Çapraz satış, sadakat puanları ve tamamlayıcı AOV paketleri.",
             ["Klaviyo Cross-Sell", "Meta Custom Audience"]),
            ("Potential Loyalists (Potansiyel Sadıklar)", 0.30, 20.0,
             "İkinci/üçüncü sipariş teşvik kuponu, marka hikayesi ve ürün eğitimleri.",
             ["Klaviyo Nurture", "Meta DPA Retargeting"]),
            ("At Risk (Risk Altındakiler - 244)", 0.20, 15.0,
             "Sınırlı süreli özel geri kazanım teklifi ve SMS otomasyonu.",
             ["SMS Win-Back", "Meta Re-engagement Ads"]),
            ("Hibernating / Lost (Uykudakiler - 111)", 0.16, 5.0,
             "Agresif son şans teklifi (%25 indirim); yanıt yoksa liste hijyeni için silme.",
             ["Klaviyo Sunset Flow"])
        ]

        results = []
        for name, pct, budget_share, action, channels in definitions:
            count = int(total_customer_count * pct)
            results.append(RFMSegmentResult(
                segment_name=name,
                customer_count=count,
                percentage_of_base=round(pct * 100.0, 1),
                recommended_budget_share_pct=budget_share,
                tactical_action=action,
                recommended_channels=channels
            ))
        return results

    @staticmethod
    def simulate_discount_breakeven(
        gross_margin_pct: float,
        discount_pct: float,
        current_orders: int = 500,
        current_aov: float = 1000.0,
        currency: str = "₺"
    ) -> DiscountBreakEvenSimulation:
        """
        Calculates the exact unit volume increase required to break even on gross profit
        when offering a percentage discount.
        Formula: Required Volume Increase = Discount% / (Gross Margin% - Discount%)
        """
        d = discount_pct / 100.0 if discount_pct > 1.0 else discount_pct
        m = gross_margin_pct / 100.0 if gross_margin_pct > 1.0 else gross_margin_pct

        orig_profit = round(current_orders * current_aov * m, 2)
        disc_aov = round(current_aov * (1.0 - d), 2)

        if d >= m:
            verdict = (
                f"ÖLÜMCÜL İNDİRİM: İndirim oranı (%{discount_pct:.1f}) brüt marjı (%{gross_margin_pct:.1f}) aşıyor veya eşit. "
                "Satılan her birimde doğrudan nakit zararı yazılır; hacim artışıyla kâra geçmek matematiksel olarak imkansızdır."
            )
            return DiscountBreakEvenSimulation(
                gross_margin_pct=round(gross_margin_pct, 2),
                discount_pct=round(discount_pct, 2),
                current_orders=current_orders,
                current_aov=round(current_aov, 2),
                discounted_aov=disc_aov,
                required_volume_increase_pct=9999.0,
                break_even_order_count=9999999,
                original_gross_profit=orig_profit,
                discounted_gross_profit_at_breakeven=0.0,
                margin_preserved=False,
                verdict=verdict
            )

        delta_q = d / (m - d)
        vol_increase_pct = round(delta_q * 100.0, 2)
        be_orders = math.ceil(current_orders * (1.0 + delta_q))
        unit_new_profit = current_aov * (m - d)
        disc_profit_at_be = round(be_orders * unit_new_profit, 2)

        if vol_increase_pct <= 25.0:
            verdict = (
                f"KABUL EDİLEBİLİR: %{discount_pct:.1f} indirim durumunda brüt kârı korumak için sipariş hacmi en az "
                f"+%{vol_increase_pct:.1f} ({be_orders} sipariş) artmalıdır. Kampanya ölçeklenebilir."
            )
        elif vol_increase_pct <= 60.0:
            verdict = (
                f"DİKKAT: Brüt kârı korumak için sipariş hacmi +%{vol_increase_pct:.1f} ({be_orders} sipariş) artmalıdır. "
                "Talep esnekliği (price elasticity) yüksek değilse kâr erimesi yaşanabilir."
            )
        else:
            verdict = (
                f"YÜKSEK RİSK: %{discount_pct:.1f} indirim için gereken sipariş artışı +%{vol_increase_pct:.1f} ({be_orders} sipariş). "
                "Bu seviyede indirim yerine sepette hediye veya kargo eşiği teşviki önerilir."
            )

        return DiscountBreakEvenSimulation(
            gross_margin_pct=round(gross_margin_pct, 2),
            discount_pct=round(discount_pct, 2),
            current_orders=current_orders,
            current_aov=round(current_aov, 2),
            discounted_aov=disc_aov,
            required_volume_increase_pct=vol_increase_pct,
            break_even_order_count=be_orders,
            original_gross_profit=orig_profit,
            discounted_gross_profit_at_breakeven=disc_profit_at_be,
            margin_preserved=True,
            verdict=verdict
        )

    @staticmethod
    def calculate_poas_net_profit(
        gross_revenue: float,
        ad_spend: float,
        cogs: float,
        logistics_and_shipping: float,
        payment_gateway_rate_pct: float = 2.8,
        return_refund_rate_pct: float = 8.0,
        packaging_and_handling: float = 0.0,
        currency: str = "₺"
    ) -> POASNetProfitSimulation:
        """
        Calculates Profit On Ad Spend (POAS) and Net Operating Profit after accounting
        for returns/refunds, gateway commissions, packaging, and shipping.
        """
        refund_amount = round(gross_revenue * (return_refund_rate_pct / 100.0), 2)
        net_rev = round(gross_revenue - refund_amount, 2)
        gateway_fee = round(gross_revenue * (payment_gateway_rate_pct / 100.0), 2)

        net_gross = round(net_rev - cogs, 2)
        net_ops = round(net_gross - logistics_and_shipping - packaging_and_handling - gateway_fee, 2)
        net_after_ads = round(net_ops - ad_spend, 2)

        safe_spend = max(0.01, ad_spend)
        poas = round(net_ops / safe_spend, 2)
        blended_roas = round(gross_revenue / safe_spend, 2)
        net_margin_pct = round((net_after_ads / max(1.0, gross_revenue)) * 100.0, 2)
        is_prof = net_after_ads > 0

        if poas >= 1.5:
            verdict = f"MÜKEMMEL POAS ({poas:.2f}x): Reklam harcaması tüm iade, komisyon ve lojistik maliyetlerini karşılayıp güçlü net nakit akışı (%{net_margin_pct:.1f}) üretiyor."
        elif poas >= 1.0:
            verdict = f"POZİTİF POAS ({poas:.2f}x): Kampanya kârlı bölgede fakat marj ince (%{net_margin_pct:.1f}). İade ve lojistik maliyetleri baskılanmalı."
        else:
            verdict = f"ZARAR BÖLGESİ (POAS {poas:.2f}x): Operasyonel brüt kâr reklam bütçesini karşılamıyor. Net kâr negatif ({currency}{net_after_ads:.2f}). Kampanya optimizasyonu şart."

        return POASNetProfitSimulation(
            gross_revenue=round(gross_revenue, 2),
            ad_spend=round(ad_spend, 2),
            cogs=round(cogs, 2),
            logistics_and_shipping=round(logistics_and_shipping, 2),
            packaging_and_handling=round(packaging_and_handling, 2),
            payment_gateway_rate_pct=round(payment_gateway_rate_pct, 2),
            payment_gateway_fee=gateway_fee,
            return_refund_rate_pct=round(return_refund_rate_pct, 2),
            refund_amount=refund_amount,
            net_revenue=net_rev,
            net_gross_profit=net_gross,
            net_operational_profit=net_ops,
            net_profit_after_ads=net_after_ads,
            poas=poas,
            blended_roas=blended_roas,
            net_margin_pct=net_margin_pct,
            is_profitable=is_prof,
            currency=currency,
            verdict=verdict
        )

    @staticmethod
    def calculate_mer_and_attribution(
        total_net_revenue: float,
        total_ad_spend: float,
        channel_reported_revenues: Optional[Dict[str, float]] = None
    ) -> MarketingEfficiencyRatioAnalysis:
        """
        Calculates Blended Marketing Efficiency Ratio (MER) and reconciles attribution overlap.
        Detects multi-channel double-counting inflation.
        """
        safe_spend = max(0.01, total_ad_spend)
        blended_mer = round(total_net_revenue / safe_spend, 2)

        ch_revenues = channel_reported_revenues or {}
        sum_reported = sum(ch_revenues.values()) if ch_revenues else total_net_revenue
        overlap_factor = round(sum_reported / max(1.0, total_net_revenue), 2)
        overreporting_pct = round(max(0.0, (sum_reported - total_net_revenue) / max(1.0, total_net_revenue) * 100.0), 1)

        if blended_mer >= 4.0:
            tier = "SCALE_AGGRESSIVELY"
            directive = "MÜKEMMEL MER: Şirket kârlılık tavanında çalışıyor; yeni müşteri edinimini maksimize etmek için bütçe agresif olarak artırılabilir."
        elif blended_mer >= 3.0:
            tier = "STABLE_PROFIT"
            directive = "SAĞLIKLI MER: Dengeli ve kârlı büyüme. Mevcut kanal karması korunarak dikey bütçe artışları (%15-20) uygulanabilir."
        elif blended_mer >= 2.0:
            tier = "MONITOR_CLOSELY"
            directive = "DİKKAT MER: Başa başa yakın seviye. Kreatif yorgunluğu ve kanal yamyamlığı denetlenmeli; bütçe artışı durdurulmalı."
        else:
            tier = "HIGH_RISK_DRAIN"
            directive = "KRİTİK ZARAR MER: Reklam harcaması toplam ciroyu eritiyor. Verimsiz reklam setleri derhal kapatılmalı."

        return MarketingEfficiencyRatioAnalysis(
            total_net_revenue=round(total_net_revenue, 2),
            total_ad_spend=round(total_ad_spend, 2),
            blended_mer=blended_mer,
            channel_reported_revenues=ch_revenues,
            sum_reported_revenue=round(sum_reported, 2),
            attribution_overlap_factor=overlap_factor,
            overreporting_pct=overreporting_pct,
            efficiency_tier=tier,
            strategic_directive=directive
        )

    @staticmethod
    def calculate_ab_test_significance(
        visitors_control: int,
        conversions_control: int,
        visitors_variant: int,
        conversions_variant: int,
        confidence_level: float = 0.95
    ) -> ABTestSignificanceAnalysis:
        """
        Calculates two-tailed Z-test statistical significance and p-value for A/B conversion rate tests.
        """
        n_a = max(1, visitors_control)
        c_a = max(0, conversions_control)
        n_b = max(1, visitors_variant)
        c_b = max(0, conversions_variant)

        cvr_a = c_a / n_a
        cvr_b = c_b / n_b
        cvr_a_pct = round(cvr_a * 100.0, 3)
        cvr_b_pct = round(cvr_b * 100.0, 3)

        rel_lift = round(((cvr_b - cvr_a) / max(1e-7, cvr_a)) * 100.0, 2)
        p_pool = (c_a + c_b) / (n_a + n_b)
        se = math.sqrt(max(1e-12, p_pool * (1.0 - p_pool) * ((1.0 / n_a) + (1.0 / n_b))))
        z_score = round((cvr_b - cvr_a) / se, 4)

        # Standard normal two-tailed p-value
        p_val = round(2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z_score) / math.sqrt(2.0)))), 4)
        is_sig = p_val < (1.0 - confidence_level)

        if is_sig and z_score > 0:
            winner = "VARIANT"
            verdict = f"KAZANAN VARYANT: Test %{confidence_level * 100:.0f} güvenle istatistiki olarak anlamlıdır (Z={z_score:.2f}, p={p_val:.4f}). Varyant dönüşümde +%{rel_lift:.1f} artış sağladı; kalıcı olarak yayına alınmalıdır."
        elif is_sig and z_score < 0:
            winner = "CONTROL"
            verdict = f"KONTROL ÜSTÜN: Varyant dönüşüm oranını negatif etkiledi (-%{abs(rel_lift):.1f}, p={p_val:.4f}). Test sonlandırılmalı ve varyant kaldırılmalıdır."
        else:
            winner = "NO_WINNER"
            verdict = f"İSTATİSTİKİ OLARAK ANLAMSIZ (p={p_val:.4f}): Fark tesadüfi olabilir. Anlamlı sonuca ulaşmak için daha fazla trafik ve örneklem toplanmalıdır."

        return ABTestSignificanceAnalysis(
            visitors_control=n_a,
            conversions_control=c_a,
            cvr_control_pct=cvr_a_pct,
            visitors_variant=n_b,
            conversions_variant=c_b,
            cvr_variant_pct=cvr_b_pct,
            relative_lift_pct=rel_lift,
            z_score=z_score,
            p_value=p_val,
            confidence_level_pct=round(confidence_level * 100.0, 1),
            is_statistically_significant=is_sig,
            winner=winner,
            verdict=verdict
        )

    @staticmethod
    def calculate_budget_pacing(
        monthly_budget: float,
        days_elapsed: int,
        days_in_month: int = 30,
        current_spend: float = 0.0,
        currency: str = "₺"
    ) -> BudgetPacingAndRunRateAnalysis:
        """
        Calculates ad budget pacing ratio, daily burn rate, and end-of-month run-rate projection.
        """
        safe_elapsed = max(1, min(days_elapsed, days_in_month))
        expected_to_date = round(monthly_budget * (safe_elapsed / days_in_month), 2)
        actual_burn = round(current_spend / safe_elapsed, 2)
        target_daily = round(monthly_budget / days_in_month, 2)

        days_left = max(0, days_in_month - safe_elapsed)
        projected_spend = round(current_spend + (actual_burn * days_left), 2)
        pacing_ratio = round(current_spend / max(1.0, expected_to_date), 3)

        adj_daily = round(max(0.0, (monthly_budget - current_spend) / max(1, days_left)), 2)

        if pacing_ratio > 1.08:
            status = "OVERSPENDING"
            rec = f"AŞIRI HARCAMA: Bütçe planlanan hızın üzerinde (%{pacing_ratio * 100:.1f}). Ay sonu projeksiyonu: {currency}{projected_spend:.2f}. Kalan günler için günlük bütçe {currency}{adj_daily:.2f} seviyesine düşürülmelidir."
        elif pacing_ratio < 0.92:
            status = "UNDERSPENDING"
            rec = f"DÜŞÜK HARCAMA: Bütçe geride kaldı (%{pacing_ratio * 100:.1f}). Kitle daralması veya teklif kısıtı olabilir. Hedeflenen harcamaya ulaşmak için günlük bütçe {currency}{adj_daily:.2f} seviyesine çıkarılmalıdır."
        else:
            status = "ON_TRACK"
            rec = f"TAM HEDEFTE: Harcama hızı ideal koridorda (%{pacing_ratio * 100:.1f}). Ay sonu tahmini: {currency}{projected_spend:.2f}."

        return BudgetPacingAndRunRateAnalysis(
            monthly_budget=round(monthly_budget, 2),
            days_elapsed=safe_elapsed,
            days_in_month=days_in_month,
            current_spend=round(current_spend, 2),
            expected_spend_to_date=expected_to_date,
            actual_daily_burn=actual_burn,
            target_daily_budget=target_daily,
            projected_end_of_month_spend=projected_spend,
            pacing_ratio=pacing_ratio,
            pacing_status=status,
            recommended_adjusted_daily_budget=adj_daily,
            currency=currency,
            actionable_recommendation=rec
        )


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
