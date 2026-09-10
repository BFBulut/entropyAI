#!/usr/bin/env python3
"""
Canivo Pets 360° Growth Audit Slide Deck Generator.
Uses SlideDeckArchitect to compile comprehensive forensic e-commerce audit,
SEO, CWV, CRO, Unit Economics (LTV:CAC, POAS, MER, d/(m-d)), Demand Gen, Hook-Swap, and SLA slides.
Exports interactive HTML5 and Markdown slide decks to docs/slides/ and the user's Desktop.
"""

import os
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skills.slide_deck_architect.slide_engine import (
    SlideDeck,
    SlideDeckBuilder,
    SlideType,
    HTMLSlideRenderer,
    MarkdownSlideRenderer,
)


def build_canivopets_slide_deck() -> SlideDeck:
    """Compiles the complete 12-slide forensic growth audit for Canivo Pets."""
    builder = SlideDeckBuilder(
        title="Canivo Pets 360° Denetim & Büyüme Raporu",
        subtitle="D2C Evcil Hayvan Beslenmesi, Adli SEO, MarTech P0, Birim Ekonomisi & Çok Kanallı Reklam Mimarisi",
        author="Entropy AI — Medya Ajansı Askeri",
        institution="D2C E-Ticaret Büyüme & Dijital Pazarlama Grubu",
        date="2026-09-07",
        theme="cyber-slate"
    )

    # Slide 1: Cover
    builder.add_title_slide(
        title="Canivo Pets (canivopets.com) 360° Büyüme Denetimi",
        subtitle="12 Kategori Adli E-Ticaret Teşhisi, İleri Birim Ekonomisi ve Çok Kanallı Medya Uçuş Planı",
        speaker_notes="Bu sunumda canivopets.com üzerinde gerçekleştirilen 12 kategorilik 360 derece adli denetim bulgularını, MarTech P0 alarmlarını, LTV:CAC birim ekonomisini ve 30-60-90 günlük medya uçuş planını aktarıyoruz."
    )

    # Slide 2: 12-Category Scorecard
    builder.add_theory_slide(
        title="1. 📊 12 Kategorilik 360° Denetim Skorkartı",
        subtitle="Adli Web Taraması ve Dijital Olgunluk Seviyeleri",
        bullets=[
            "**Marka Kimliği & Yasal Bilgiler (%100 - Tam Uyum):** Şirket unvanı, Balıkesir Edremit üretim merkezi ve WhatsApp sipariş hattı eksiksiz.",
            "**MarTech & Takip Kodları (%0 - Kritik P0):** GA4 ve Meta CAPI tekilleştirmesi (`event_id`) eksik; reklam algoritmaları kör uçuşta.",
            "**Güvenlik & Consent Mode v2 (%10 - Kritik P0):** Google Consent Mode v2 (`ad_user_data`, `ad_personalization`) ve CSP başlıkları eksik.",
            "**Core Web Vitals (%75 - Geliştirilmeli):** 9 adet render engelleyici senkron script ve %0 WebP modern görsel oranı.",
            "**E-Ticaret CRO & Sürtünme (%45 - Severe Friction):** 17 form alanı mobilde sepet terk oranını artırıyor; misafir alışverişi eksik.",
            "**Birim Ekonomisi & Kârlılık (%100 - Elit Seviye):** Başa Baş ROAS 1,82x, Hedef ROAS 2,50x, LTV:CAC 16,76x (Underinvesting)."
        ],
        callout="En acil müdahale MarTech P0 ve Consent Mode v2 entegrasyonudur; bu adımlar tamamlanmadan reklam bütçesi ölçeklenmemelidir.",
        speaker_notes="12 kategorilik denetimde kurumsal kimlik ve kârlılık marjları kusursuzken, takip altyapısı ve mobil ödeme sürtünmesi zayıf halkadır."
    )

    # Slide 3: Corporate Identity & Location
    builder.add_two_column_slide(
        title="2. 🏢 Kurumsal Kimlik & Coğrafi Ayak İzi",
        subtitle="Kaynak Kod, Ticimax Modelleri ve Yasal Metin Analizi",
        left_title="Kurumsal Künye & Sicil",
        right_title="İletişim & MarTech Yığını",
        left_column=[
            "**Marka:** Canivo Pets",
            "**Resmi Şirket Unvanı:** TRADE BAŞYİĞİT DANIŞMANLIK İÇ VE DIŞ TİCARET LİMİTED ŞİRKETİ",
            "**Fiziksel Merkez / Sicil:** Yolören Mah. Yolören 66 Sk. No:3/A Edremit - Balıkesir / TÜRKİYE",
            "**İş Modeli:** Üreticiden Doğrudan Tüketiciye (D2C) Evcil Hayvan Beslenmesi",
            "**E-Ticaret Altyapısı:** Ticimax Cloud Suite (v8.13.806.0.111627)"
        ],
        right_column=[
            "**Telefon & WhatsApp Sipariş Hattı:** +90 540 720 62 62",
            "**Kurumsal E-Posta:** info@canivopets.com",
            "**Sosyal Medya Varlığı:** Instagram (@canivopets), YouTube (@CanivoPets), Facebook",
            "**Analitik & Takip:** Google Tag Manager (GTM-WGTLTFP6), PostHog, Meta Pixel",
            "**Ödeme Yöntemleri:** 3D Secure Kredi Kartı, Havale/EFT, Kapıda Nakit/Kartla Ödeme"
        ],
        callout="Tüm kurumsal veriler doğrulanmış; Balıkesir/Edremit merkezli üretim ve doğrudan lojistik avantajı mevcuttur.",
        speaker_notes="Markanın yasal şirket unvanı ve fiziksel adresi eksiksiz tespit edilmiştir. Ticimax altyapısı üzerinde çalışan sistemde temel takip etiketleri etkindir."
    )

    # Slide 4: Product Catalog & AOV
    builder.add_theory_slide(
        title="3. 🛍️ Ürün Kataloğu ve Fiyatlandırma Mimarisi",
        subtitle="12 SKU Dağılımı ve Ortalama Sepet Büyüklüğü (AOV)",
        bullets=[
            r"**Ortalama Sepet / Liste Fiyatı (AOV Bazı):** $\mathbf{1.694,83\text{ ₺}}$ (Taban: ₺849,00 — Tavan: ₺2.499,00)",
            "**Amiral Gemisi (Hero SKU):** Canivo Hunter Köpek Maması 15 kg (₺2.499,00 / Liste: ₺2.899,00)",
            "**Yüksek Enerji / Irk Serileri:** Canivo Kuzulu Performans 15 kg (₺2.499), Canivo Yavru 15 kg (₺2.199), Rottweiler 15 kg (₺1.999)",
            "**Fonksiyonel Sağlık Serisi (Supplements):** Canivo Joint Plus 15 kg (₺2.499), Canivo Flex Eklem Desteği (₺1.499), Anti Parvo Bağışıklık (₺1.299)",
            "**Tamamlayıcı Konserve Kolileri:** Canivo 400g Yaş Konserve 12'li Koli (₺849), 24'lü Koli (₺1.399), 36'lı Koli (₺1.899)"
        ],
        callout="Ürün portföyü kuru mama, medikal takviye ve ıslak konserve olarak kusursuz bir çapraz satış (cross-sell) matrisi sunmaktadır.",
        speaker_notes="12 SKU'luk katalogda 15 kg büyük boy çuvallar ciro omurgasını oluştururken, 849 TL'lik konserveler ve 1.499 TL'lik eklem takviyeleri yüksek marjlı çapraz satış fırsatıdır."
    )

    # Slide 5: P0 MarTech & Tracking Alarms
    builder.add_two_column_slide(
        title="4. 🚨 Kritik P0 MarTech ve Güvenlik Alarmları",
        subtitle="Veri Kaybı ve Reklam Algoritması Kör Uçuş Riskleri",
        left_title="Tespit Edilen P0 Açıkları",
        right_title="Gerekli Düzeltme Protokolü",
        left_column=[
            "**Google Consent Mode v2 Yok:** `ad_storage`, `ad_user_data` ve `ad_personalization` sinyalleri iletilmiyor (Google Ads verimi düşüyor).",
            "**Meta CAPI Sunucu Takibi Eksik:** Yalnızca tarayıcı pikseli var; iOS 14.5+ sonrası reklam dönüşümlerinin %30'u raporlanamıyor.",
            "**CSP & HSTS Güvenlik Başlıkları Yok:** Form hırsızlığı ve script enjeksiyonuna karşı tarayıcı koruması eksik."
        ],
        right_column=[
            "**Consent Mode v2 Kurulumu:** GTM üzerinden çerez izin kalkanı kurularak Google algoritmalarına uyumlu sinyal basılmalı.",
            "**Meta CAPI Entegrasyonu:** Sunucu tarafında `event_id` tekilleştirmesiyle siparişler Meta API'ye iletilmeli.",
            "**Ticimax CDN Güvenlik Başlıkları:** `Content-Security-Policy` ve `Strict-Transport-Security` başlıkları aktif edilmeli."
        ],
        callout="Takip altyapısı onarılmadan harcanan her 100 TL reklam bütçesinin 35 TL'si sinyal kaybı nedeniyle boşa gitmektedir.",
        speaker_notes="Consent Mode v2 ve CAPI olmadan Performance Max veya Meta ASC algoritmaları doğru kişiyi bulamaz. İlk 5 günde bu takip onarılmalıdır."
    )

    # Slide 6: Core Web Vitals & Web Performance
    builder.add_theory_slide(
        title="5. ⚡ Web Performans & Core Web Vitals (CWV)",
        subtitle="Sayfa Yükleme Hızı, Varlık Optimizasyonu ve Düzen Kararlılığı",
        bullets=[
            "**Modern Görsel Formatı Oranı:** **%0,0 (Kritik Performans Riski)**. Taranan 23 görselin tamamı `.png` ve `.jpg` formatındadır.",
            "**WebP / AVIF Dönüşümü:** Ticimax CDN üzerinden WebP sıkıştırması açılarak sayfa dosya boyutu %60-70 hafifletilmelidir.",
            "**Render Engelleyici Kodlar (Render-Blocking):** 9 adet senkron yüklenen CSS ve JS dosyası (`ticimax.jquery.min.js`, `style.css`).",
            "**LCP (Largest Contentful Paint) Riski:** Yüksek. Hero banner görseli (`kopek-mamalari-7ce0.jpg`) sıkıştırılmamış JPEG'dir.",
            "**CRO / Form Sürtünmesi:** 17 adet form alanı mobilde satın alma vazgeçme oranını artırmaktadır; 'Tek Tıkla Misafir Alışverişi' kurulmalıdır."
        ],
        callout="Sadece görsellerin WebP yapılması ve JS dosyalarının ötelenmesi (defer) mobil hız skorunu 40'tan 85+ bandına fırlatacaktır.",
        speaker_notes="Sayfadaki tüm resimler eski nesil JPG/PNG. Bu durum mobilde açılış süresini uzatmakta ve reklam tıklamalarında bounce rate'i yükseltmektedir."
    )

    # Slide 7: Advanced Unit Economics
    builder.add_equation_breakdown_slide(
        title="6. 💰 İleri Düzey Birim Ekonomisi ve Kârlılık Matematiği",
        equation=r"\text{Breakeven ROAS} = \frac{1}{\text{Brüt Marj}} = \frac{1}{0,55} = \mathbf{1,82x} \quad \Big| \quad \text{Hedef ROAS} = \frac{1}{0,55 - 0,15} = \mathbf{2,50x}",
        variable_explanations=[
            "**Başa Baş ROAS (1,82x):** Reklam harcamasının başa baş noktası; bu çarpanın üzeri doğrudan net kâra yazar.",
            "**Hedef ROAS (2,50x):** Şirkete operasyonel masraflar sonrası net **%15 kâr marjı** bırakan büyüme hedefi.",
            "**Maksimum CPA (₺200,00):** ₺1.694 AOV sepetinde müşteri başına ödenebilecek azami tavan edinim maliyeti."
        ],
        implications=[
            r"**LTV:CAC Rasyosu = 16,76x (Underinvesting):** LTV $\approx$ ₺4.986, CAC $\approx$ ₺297. Şirket reklam bütçesini aşırı kısıyor; güvenle 3 katına çıkarabilir.",
            "**CAC Geri Ödeme (Payback Period):** **2,4 Ay**. Müşteri 2. siparişte edinim maliyetini tamamen amorti etmektedir.",
            "**Katkı Marjları (CM):** CM1 (Brüt): %55,0 | CM2 (Operasyonel): %46,0 | CM3 (Pazarlama Net Katkısı): %21,0 | POAS: 3,12x"
        ],
        callout="Canivo Pets'in birim ekonomisi kaya gibi sağlamdır; LTV:CAC 16,76x seviyesi agresif büyüme için devasa bir alan tanımaktadır.",
        speaker_notes="Birim ekonomisi sonuçları Canivo'nun kârlı bir makine olduğunu gösteriyor. Underinvesting durumundalar; bütçe artırımı kârlı şekilde ölçeklenebilir."
    )

    # Slide 8: Relational Growth Campaigns
    builder.add_equation_breakdown_slide(
        title="7. 🚀 Marj Korumalı Kampanyalar: BOGO & İndirim Başa Başı",
        equation=r"\Delta Q = \frac{d}{m - d} = \frac{0,15}{0,55 - 0,15} = \mathbf{+37,5\%} \quad \Big| \quad \text{Net Kar}_{\text{BOGO}} = 2.499 - (950 + 280 + 130) = \mathbf{1.139\text{ ₺}}\; (\%45,6\text{ Marj})",
        variable_explanations=[
            "**İndirim Hacim Formülü:** %15'lik bir indirimde kârı korumak için sipariş hacmi en az **+%37,5** artmalıdır.",
            "**BOGO Kurgusu:** 1 Çuval 15 kg Kuru Mama (₺2.499) alana -> 12'li Yaş Mama Konservesi (Liste: ₺849) **HEDİYE!**",
            "**Maliyet Arbitrajı:** Tüketici 849 TL'lik dev bir hediye algılar; şirkete maliyeti sadece 280 TL'dir (Net Kâr: ₺1.139)."
        ],
        implications=[
            "**Çapraz İndirim (%15):** 15 kg Mama alanlara Canivo Flex Eklem Desteği ₺1.499 yerine ₺1.274 (Sepet AOV +%50,9 artışla ₺3.773 olur).",
            "**Sepet Eşik Teşviki (Cart Threshold):** ₺2.288 üzeri siparişlerde Kargo Bedava + Canivo Ölçü Kabı hediye."
        ],
        callout="BOGO kampanyasında tüketiciye 849 TL değer sunulurken, Canivo %45,6 net brüt marjını korumaktadır.",
        speaker_notes="Asla iki çuval kuru mamayı 1 alana 1 bedava yapmıyoruz. Düşük maliyetli yaş mamayı hediye ederek algılanan değeri patlatıyoruz."
    )

    # Slide 9: Multi-Channel Ads Strategy
    builder.add_two_column_slide(
        title="8. 📱 Çok Kanallı Reklam Mimarisi (₺100.000 Aylık Bütçe)",
        subtitle="Huni Odaklı Bütçe Dağılımı ve Kanal Görev Dağılımı",
        left_title="Meta Advantage+ & Google PMax",
        right_title="Google Demand Gen & Huni Dağılımı",
        left_column=[
            "**Meta Advantage+ Shopping (ASC) (₺55.000 / Ay):**",
            "- Dinamik ürün kataloğu + 5 aşamalı UGC videoları.",
            "- Mevcut müşteri harcama tavanı: **%5,0** (Yeni müşteri odaklı).",
            "**Google Performance Max (PMax) (₺30.000 / Ay):**",
            "- Merchant Center tam entegre, tROAS Hedefi: **%260**.",
            "- Arama, Alışveriş, Haritalar ve YouTube envanteri."
        ],
        right_column=[
            "**Google Demand Gen (₺15.000 / Ay):**",
            "- 9:16 Shorts, YouTube In-Stream ve Discover akışı.",
            "- Hedef Kitle: Evcil hayvan sahipleri %1-%3 Lookalike.",
            "**Huni Bütçe Dağılımı:**",
            "- TOFU (Soğuk Kitle): %55 (₺55.000)",
            "- MOFU (Ilık Kitle): %25 (₺25.000)",
            "- BOFU (Sıcak/Sepet Terk): %15 (₺15.000) | RETENTION: %5 (₺5.000)"
        ],
        callout="TOFU'da talep yaratılırken, PMax ve Meta ASC ile dönüşüm en yüksek kârlılıkla toplanır.",
        speaker_notes="100.000 TL bütçe için en verimli dağılım 55k Meta ASC, 30k Google PMax ve 15k Demand Gen kombinasyonudur."
    )

    # Slide 10: Creative Fatigue & Hook-Swap
    builder.add_theory_slide(
        title="9. 🎬 Kreatif Yorgunluk Kalkanı: 5 Açılı Hook-Swap Paketi",
        subtitle="Kazanan Video Gövdesini Korumak ve Reklam Ömrünü 3 Katına Çıkarmak",
        bullets=[
            "**Kanca 1 (Merak & Kalıp Kırıcı):** *'Veterinerlerin mama ambalajlarının arkasında gizlediği o detayı biliyor musunuz? 🤫'*",
            "**Kanca 2 (Negatif Uyarı):** *'Köpeğinize hala tahıl yüklü sıradan market mamalarını veriyorsanız hemen durun! 🛑'*",
            "**Kanca 3 (Kronik Acı / Problem):** *'Mamasını yemeyen ya da sürekli tüy döken köpeğiniz için çözüm arıyorsanız... 🐕' açılışı.*",
            "**Kanca 4 (Müşteri İtirafı / Sosyal Kanıt):** *'3 farklı ithal marka denedikten sonra Canivo'ya geçtiğimiz ilk haftada ne mi oldu?'*",
            "**Kanca 5 (Dönüşüm Öncesi / Sonrası):** *'Tüy dökülmesi ve eklem sertliği yaşayan dostumuzun 30 günlük inanılmaz değişimi!'*",
            "**Protokol:** Kazanan videonun sadece ilk 3 saniyesi değiştirilerek algoritmaya 5 yeni kreatif sunulur; prodüksiyon maliyeti %80 düşer."
        ],
        callout="Kreatif yorgunluk başladığında tüm videoyu yeniden çekmek yerine sadece kancayı (Hook) değiştirmek CPM'i %35 düşürür.",
        speaker_notes="Aynı video gövdesiyle 5 farklı psikolojik kanca test edilir. Bu yöntem Meta ve TikTok'ta reklam tükenmesini tamamen engeller."
    )

    # Slide 11: Klaviyo Retention & Lifecycle
    builder.add_theory_slide(
        title="10. 📩 Klaviyo CRM & Yaşam Döngüsü Retention Akışları",
        subtitle="Müşteri Sadakati, Sıfır Maliyetli Ciro ve Tekrar Sipariş Döngüsü",
        bullets=[
            "**Hoş Geldin Serisi (Welcome Nurture):** %10 ilk sipariş kodu + doğru mama seçim rehberi (Tahmini Ciro Katkısı: **%12**).",
            "**Terk Edilen Sepet / Ödeme (Cart & Checkout Abandonment):** 1. Saat e-posta, 6. Saat SMS (Kargo bedava teşviki) (Tahmini Katkı: **%18**).",
            "**Satın Alma Sonrası VIP Sadakat (Post-Purchase):** Siparişten 7 gün sonra takviye vitamin (Canivo Flex) çapraz satışı (Tahmini Katkı: **%10**).",
            "**45-60 Günlük Geri Kazanım (Win-Back):** 15 kg mamanın bitiş periyodunda otomatik 'Mamanız Bitmek Üzere Olabilir' hatırlatması (Tahmini Katkı: **%6**).",
            "**VIP Kulüp / Abonelik Modeli:** 'Her Ay Düzenli Kapımda' abonelerine sabit %10 indirim ile LTV 2.499 ₺'den 27.000 ₺'ye sıçrar."
        ],
        callout="E-posta ve SMS retention akışları kurulduğunda toplam mağaza cirosunun %30-40'ı sıfır reklam maliyetiyle elde edilir.",
        speaker_notes="Mama işi bir abonelik işidir. 15 kg mama 45-60 günde biter. Zamanlı hatırlatma akışları şirketin en kârlı gelir kapısıdır."
    )

    # Slide 12: 30-Day Onboarding SLA & Decision Gates
    builder.add_summary_slide(
        title="11. 🛡️ 30 Günlük Ajans Onboarding SLA'sı & 4 Karar Kapısı",
        takeaways=[
            "**Kapı 1: Data & Tracking Gate (1-5. Gün):** GA4, Meta CAPI ve Google Consent Mode v2 tam doğrulanmadan ücretli trafiğe çıkılmaz (Fail-Closed).",
            "**Kapı 2: Profitability Gate (6-10. Gün):** Başa Baş ROAS (1,82x) ve Maksimum CPA (₺200) parametreleri reklam paneline kilitlenir.",
            "**Kapı 3: CRO & Friction Gate (11-20. Gün):** 17 form alanı sadeleştirilip 'Tek Tıkla Misafir Alışverişi' kurulmadan bütçe ölçeklenmez.",
            "**Kapı 4: Scaling Gate (21-30. Gün):** POAS > 2,5x ve Blended MER > 2,2x seviyesine oturmadan aylık bütçe %20'den fazla artırılmaz."
        ],
        callout="Canivo Pets 360° Denetim & Büyüme Sunumu Tamamlandı. Başarılar!",
        speaker_notes="Bu 4 karar kapısı sayesinde Canivo Pets bütçe israfı yaşamadan kârlı ve kontrollü biçimde ölçeklenecektir."
    )

    return builder.build()


def export_slides_to_desktop(html_content: str, md_content: str) -> list[str]:
    """Saves presentation files to the user's Desktop."""
    target_desktops = []

    # Check OneDrive Desktop (Turkish Windows standard)
    user_profile = os.environ.get("USERPROFILE", r"C:\Users\batu_")
    onedrive_desktop = Path(user_profile) / "OneDrive" / "Masaüstü"
    if onedrive_desktop.is_dir():
        target_desktops.append(onedrive_desktop)

    # Also check standard Desktop
    standard_desktop = Path(user_profile) / "Desktop"
    if standard_desktop.is_dir():
        target_desktops.append(standard_desktop)

    if not target_desktops:
        # Fallback create desktop
        onedrive_desktop.mkdir(parents=True, exist_ok=True)
        target_desktops.append(onedrive_desktop)

    saved_paths = []
    for dt in target_desktops:
        html_path = dt / "CanivoPets_360_Growth_Audit_Slides.html"
        md_path = dt / "CanivoPets_360_Growth_Audit_Slides.md"

        html_path.write_text(html_content, encoding="utf-8")
        md_path.write_text(md_content, encoding="utf-8")
        saved_paths.extend([str(html_path), str(md_path)])

    return saved_paths


def main():
    deck = build_canivopets_slide_deck()

    # 1. Export to docs/slides/
    docs_slides_dir = REPO_ROOT / "docs" / "slides"
    docs_slides_dir.mkdir(parents=True, exist_ok=True)

    out_html = docs_slides_dir / "canivopets_growth_audit_slides.html"
    out_md = docs_slides_dir / "canivopets_growth_audit_slides.md"
    out_json = docs_slides_dir / "canivopets_growth_audit_slides.json"

    html_content = HTMLSlideRenderer().render(deck)
    out_html.write_text(html_content, encoding="utf-8")
    print(f"✅ Docs HTML5: {out_html}")

    md_content = MarkdownSlideRenderer().render(deck)
    out_md.write_text(md_content, encoding="utf-8")
    print(f"✅ Docs Markdown: {out_md}")

    out_json.write_text(deck.model_dump_json(indent=2), encoding="utf-8")
    print(f"✅ Docs JSON: {out_json}")

    # 2. Export to User Desktop
    saved_desktop = export_slides_to_desktop(html_content, md_content)
    for p in saved_desktop:
        print(f"🚀 Masaüstüne Kaydedildi: {p}")


if __name__ == "__main__":
    main()
