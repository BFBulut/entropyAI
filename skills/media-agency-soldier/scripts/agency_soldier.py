#!/usr/bin/env python3
"""
AgencySoldier: Master Orchestrator for Media Agency Soldier Skill.
CLI and Programmatic class executing web audits, relational campaigns, and multi-channel ads.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

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

logger = logging.getLogger("AgencySoldier")


# ---------------------------------------------------------------------------
# ANSI Palette
# ---------------------------------------------------------------------------

class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def supports_color(cls) -> bool:
        return sys.stdout.isatty() or os.environ.get("TERM") is not None


def cprint(text: str, color: str = "", bold: bool = False):
    msg = f"{Colors.BOLD if bold else ''}{color}{text}{Colors.RESET}" if (Colors.supports_color() and color) else text
    try:
        print(msg)
    except (UnicodeEncodeError, OSError):
        try:
            enc = sys.stdout.encoding or "utf-8"
            print(msg.encode(enc, errors="replace").decode(enc))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Markdown Report Generator
# ---------------------------------------------------------------------------

def generate_markdown_report(analysis: Dict[str, Any], campaigns: Dict[str, Any], ad_plans: Dict[str, Any]) -> str:
    brand = analysis.get("brand_info", {}).get("brand_name", "Marka")
    domain = analysis.get("brand_info", {}).get("domain", "")
    comp = analysis.get("contact_and_location", {})
    cat = analysis.get("product_catalog", {})
    seo = analysis.get("seo_audit", {})
    perf = analysis.get("performance_vitals", {})
    cro = analysis.get("cro_and_ux", {})

    md = []
    md.append(f"# 🛡️ Medya Ajansı Askeri - Kapsamlı Denetim ve Büyüme Raporu: {brand}\n")
    md.append(f"**Domain**: `{domain}` | **Analiz Versiyonu**: `v1.0.0`\n")

    # 1. Brand & Location
    md.append("## 1. 🏢 Marka & Fiziksel Lokasyon Özeti\n")
    md.append(f"- **Marka Adı**: {brand}")
    md.append(f"- **Şirket Unvanı**: {analysis.get('brand_info', {}).get('company_title')}")
    md.append(f"- **Lokasyon**: {comp.get('address')}, {comp.get('city')}, {comp.get('country')}")
    md.append(f"- **İletişim**: {', '.join(comp.get('emails', []))} | {', '.join(comp.get('phones', []))}\n")

    # 2. Product Catalog
    md.append("## 2. 🛍️ Ürün Kataloğu ve Pazar Konumlandırması\n")
    md.append(f"- **Toplam Tespit Edilen Ürün**: {cat.get('count', 0)}")
    md.append(f"- **Ortalama Fiyat**: {cat.get('average_price', 0):.2f} {cat.get('currencies', ['₺'])[0] if cat.get('currencies') else '₺'}")
    md.append(f"- **Fiyat Aralığı**: {cat.get('min_price', 0)} - {cat.get('max_price', 0)}\n")
    md.append("| Ürün Adı | Fiyat |")
    md.append("| :--- | :--- |")
    for p in cat.get("products", [])[:6]:
        md.append(f"| {p.get('name')} | {p.get('price')} |")
    md.append("")

    # 3. SEO & CWV
    md.append("## 3. 🔍 SEO & Core Web Vitals Skorkartı\n")
    md.append(f"- **Title**: `{seo.get('title')}` (Durum: **{seo.get('title_status')}**)")
    md.append(f"- **Meta Description**: `{seo.get('meta_description')}` (Durum: **{seo.get('meta_description_status')}**)")
    md.append(f"- **H1 Durumu**: **{seo.get('h1_status')}** ({seo.get('h1_count')} adet)")
    md.append(f"- **Canonical**: `{seo.get('canonical')}` ({seo.get('canonical_status')})")
    md.append(f"- **Modern Görsel Oranı**: %{int(perf.get('images', {}).get('modern_format_ratio', 0) * 100)}")
    md.append(f"- **Render-Blocking Script**: {perf.get('scripts', {}).get('blocking_render', 0)}")
    md.append(f"- **Genel Performans Riski**: **{perf.get('overall_performance_risk')}**\n")

    # 4. CRO & UX
    md.append("## 4. 🎯 CRO & Kullanıcı Deneyimi (UX)\n")
    md.append(f"- **CTA Buton Sayısı**: {cro.get('cta_buttons', {}).get('count', 0)} (Durum: **{cro.get('cta_buttons', {}).get('status')}**)")
    md.append(f"- **Form Sürtünme Seviyesi**: **{cro.get('form_friction', {}).get('friction_level')}**")
    md.append(f"- **Güven Rozetleri**: {', '.join(cro.get('trust_badges', {}).get('detected', []))}\n")

    # 5. Relational Campaigns
    md.append("## 5. 🚀 İlişkisel Büyüme Kampanyaları\n")
    bogo = campaigns.get("bogo", {})
    cross = campaigns.get("cross_discount", {})
    thresh = campaigns.get("cart_threshold", {})

    md.append(f"### BOGO (1 Alana 1 Bedava)\n- **Mekanizma**: `{bogo.get('mechanic')}`\n- **Slogan**: *\"{bogo.get('slogan')}\"*\n- **Marj Etkisi**: {bogo.get('margin_impact')}\n")
    md.append(f"### Çapraz Satış İndirimi\n- **Mekanizma**: `{cross.get('mechanic')}`\n- **Tasarruf**: {cross.get('bundled_savings')}\n")
    md.append(f"### Sepet Eşik Teşviki\n- **Mekanizma**: `{thresh.get('mechanic')}`\n- **Slogan**: *\"{thresh.get('slogan')}\"*\n- **Kargo**: kargo bedava fırsatı\n")

    # 6. Multi-channel Ads
    md.append("## 6. 📱 Çok Kanallı Reklam Planları\n")
    g_ads = ad_plans.get("google_search_ads", {})
    meta = ad_plans.get("meta_ads", {})
    tiktok = ad_plans.get("tiktok_reels_ads", {})

    md.append(f"### Responsive Search Ads (RSA)\n- **Başlıklar**:\n")
    for h in g_ads.get("headlines", []):
        md.append(f"  - `{h}` ({len(h)} kr)")
    md.append(f"- **Açıklamalar**:\n")
    for d in g_ads.get("descriptions", []):
        md.append(f"  - `{d}` ({len(d)} kr)")
    md.append(f"- **Negatifler**: {', '.join(g_ads.get('negative_keywords', [])[:10])}\n")

    md.append("### Meta / Instagram Reklam Kurgusu\n")
    md.append(f"**Vurucu Kanca**: *\"{meta.get('hook')}\"*\n")
    md.append("**UGC Video Akışı:**\n")
    for stage, text in meta.get("ugc_scenario", {}).items():
        md.append(f"- **{stage}**: {text}")
    md.append("")

    md.append("### TikTok / Reels Kısa Video Planı\n")
    md.append(f"- **Kanca (Hook)**: *\"{tiktok.get('hook')}\"*\n")
    md.append(f"- **Trend Konsept**: {tiktok.get('trend_concept')}\n")
    md.append(f"- **CTA**: {tiktok.get('cta')}\n")

    # 7. Unit Economics & Funnel Allocations
    md.append("## 7. 📊 Birim Ekonomisi, ROAS ve Huni Bütçe Dağılımı\n")
    avg_p = cat.get("average_price", 0)
    curr = cat.get("currencies", ["₺"])[0] if cat.get("currencies") else "₺"
    breakeven_roas = round(1.0 / 0.55, 2)
    target_roas = round(1.0 / (0.55 - 0.15), 2)
    max_cpa = round(avg_p * 0.40, 2)
    md.append(f"- **Varsayılan Brüt Kâr Marjı**: %55.0")
    md.append(f"- **Başa Baş ROAS (Breakeven)**: **{breakeven_roas:.2f}x** (%{breakeven_roas*100:.0f}) — Bu oranın altındaki reklam harcaması doğrudan zarar yazar.")
    md.append(f"- **Hedef ROAS (%15 Net Kâr İçin)**: **{target_roas:.2f}x** (%{target_roas*100:.0f})")
    md.append(f"- **Maksimum İzin Verilebilir CPA**: **{max_cpa:.2f} {curr}**")
    md.append("\n**Önerilen Huni Bütçe Dağılım Modeli (Dengeli Büyüme):**")
    md.append("- **TOFU (%55)**: Soğuk Kitle / Keşif & Video Kancaları (Piksel Öğrenimi)")
    md.append("- **MOFU (%25)**: Ilık Kitle / Değerlendirme & Sosyal Kanıt")
    md.append("- **BOFU (%15)**: Sıcak Kitle / Dinamik Yeniden Pazarlama (DPA)")
    md.append("- **Retention (%5)**: Mevcut Müşteri / LTV & E-posta/SMS Otomasyonu\n")

    # 8. MarTech Tracking & Agency Tools
    md.append("## 8. 🛠️ MarTech Sinyalleri & Profesyonel Ajans Araç Kiti\n")
    martech = analysis.get("martech_tracking", {})
    md.append(f"- **MarTech Sağlık Skoru**: %{martech.get('martech_health_score', 0)}")
    md.append(f"- **Ücretli Trafiğe Hazırlık**: {'✅ Hazır' if martech.get('ready_for_paid_traffic') else '⚠️ Kritik Takip Kodları Eksik'}")
    if martech.get("critical_missing_p0"):
        md.append(f"- **Kritik Eksikler (P0)**: {', '.join(martech.get('critical_missing_p0'))}")

    md.append("\n**Önerilen Profesyonel Ajans Araçları:**")
    tools = analysis.get("agency_tool_recommendations", [])
    if tools:
        for t in tools[:4]:
            md.append(f"- **{t.get('name')}**: {t.get('primary_role')} — *{t.get('use_case')}*")
    else:
        md.append("- **Screaming Frog SEO Spider**: 404/301 yönlendirmeleri ve teknik indeksleme.")
        md.append("- **Ahrefs / Semrush**: Backlink profili ve rekabetçi reklam istihbaratı.")
        md.append("- **Google Search Console**: Gerçek organik performans ve tarama bütçesi.")
    md.append("")

    return "\n".join(md)


# ---------------------------------------------------------------------------
# AgencySoldier Orchestrator Class
# ---------------------------------------------------------------------------

class AgencySoldier:
    """Master controller for executing audits and generating campaign artifacts."""

    def __init__(self):
        self.analyzer = URLAnalyzer()
        self.architect = CampaignArchitect()

    def run(
        self,
        offline_html_path: Optional[str] = None,
        url: Optional[str] = None,
        brand: Optional[str] = None,
        export_json: Optional[str] = None,
        export_md: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs full audit and returns unified output structure."""
        if offline_html_path:
            p = Path(offline_html_path)
            if not p.exists():
                raise FileNotFoundError(f"HTML dosyası bulunamadı: {p}")
            html_text = p.read_text(encoding="utf-8", errors="replace")
            effective_url = url or f"https://{p.stem}.com"
            mode = "offline"
        elif url:
            html_text = self.analyzer.fetch_html(url)
            effective_url = url
            mode = "live"
        else:
            raise ValueError("Lütfen 'url' veya 'offline_html_path' belirtin.")

        analysis = self.analyzer.analyze_html(html_text, url=effective_url)
        if brand:
            analysis["brand_info"]["brand_name"] = brand

        campaigns = self.architect.generate_relational_campaigns(analysis)
        ad_plans = self.architect.generate_multichannel_ad_plans(analysis)
        unit_econ = self.architect.generate_unit_economics_plan(analysis)

        output = {
            "metadata": {
                "mode": mode,
                "engine": "MediaAgencySoldier",
                "version": "1.0.0"
            },
            "analysis": analysis,
            "campaigns": campaigns,
            "ad_plans": ad_plans,
            "unit_economics": unit_econ
        }

        # Export JSON
        if export_json:
            j_p = Path(export_json)
            j_p.parent.mkdir(parents=True, exist_ok=True)
            j_p.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

        # Export MD
        if export_md:
            m_p = Path(export_md)
            m_p.parent.mkdir(parents=True, exist_ok=True)
            md_content = generate_markdown_report(analysis, campaigns, ad_plans)
            m_p.write_text(md_content, encoding="utf-8")

        return output

    def main(self, args_list: Optional[List[str]] = None) -> int:
        """CLI argument parser entry point returning exit code."""
        parser = argparse.ArgumentParser(description="Media Agency Soldier CLI")
        parser.add_argument("--url", "-u", type=str, help="Hedef web sitesi URL")
        parser.add_argument("--brand", "-b", type=str, help="Marka adı")
        parser.add_argument("--offline-html", "-f", type=str, help="Çevrimdışı HTML dosyası")
        parser.add_argument("--output-json", "--export-json", "-j", dest="export_json", type=str, help="JSON çıktı yolu")
        parser.add_argument("--output-md", "--export-md", "-m", dest="export_md", type=str, help="Markdown çıktı yolu")
        parser.add_argument("--verbose", "-v", action="store_true", help="Detaylı log")

        parsed = parser.parse_args(args_list)

        try:
            self.run(
                offline_html_path=parsed.offline_html,
                url=parsed.url,
                brand=parsed.brand,
                export_json=parsed.export_json,
                export_md=parsed.export_md
            )
            return 0
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return 1


def run_agency_soldier(
    url: Optional[str] = None,
    brand: Optional[str] = None,
    offline_html_path: Optional[str] = None,
    export_json_path: Optional[str] = None,
    export_md_path: Optional[str] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    soldier = AgencySoldier()
    return soldier.run(
        offline_html_path=offline_html_path,
        url=url,
        brand=brand,
        export_json=export_json_path,
        export_md=export_md_path
    )


if __name__ == "__main__":
    soldier = AgencySoldier()
    sys.exit(soldier.main())
