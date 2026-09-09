# Faz 6 İlerleme Raporu — v0.4.0

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiket `v0.4.0` · Build: `dist_check\EntropyAI\EntropyAI.exe` (uygulama açık olduğu için; aynalama: `robocopy C:\EntropiAI\dist_check\EntropyAI C:\EntropiAI\dist\EntropyAI /MIR`)

## Sonuç
Tam paket **1807 test geçti, 0 hata** (Faz 5: 1789; +79 yeni, −61 medya testi dışlandı). Kota: 0 model çağrısı.

## Senin bildirdiklerin ve çözümleri
- **Efor ayarı yok** → agy 3 / Claude 5 seviye, üst çubukta efor seçici, `/effort`, kalıcı ayar.
- **Claude'a geçince "command line too long", kırmızı çekirdek, kilitli sohbet** → sistem istemi 4k karakter üstünde `--append-system-prompt-file` ile dosyadan (argv toplamı 28k sınırı, yedek stdin bloğu); hata yolunda sohbet kilidi açılıyor; sağlayıcı değişimi süren isteği iptal ediyor.
- **Graf karışık, sığmıyor, izolasyon çalışmıyor** → kök neden ölçüldü (1101 düğüm tam çiziliyor, sığdırma 0,064). Açılışta 59 yapısal düğüm; yapraklar yakınlaşınca ya da dala tıklayınca; zoom/sığdırma tek kapıdan, panel gösterilince yeniden sığdırma; 👁️ izolasyon atalar+alt ağaç+komşular ile her kapsamda.
- **İki uygulama tek ekrana sığmıyor** → pencereler kullanılabilir ekrana göre (Zen %92, Chat, Desk %88), üst çubuk minimumları 2708 → 752 px; 1366×768 ve 1920×1080'de taşan panel 0.
- **Piksel ofis** → pixel-agents varlıkları ve formatı (MIT kod, CC0 karakterler), yeni motor ve sahne.

## Yeni mimari: Entropy Agent Desk ayrıştırıldı
- Kendi veri kökü `Entropy/Desk/Offices/<ofis>/` (ofis, ajanlar, projeler, raporlar, posta kutusu, bellek grafı, düzen). Entropy'nin ajanları Entropy'ye kaldı; tohum ofis/ajan yok. Ofis oluşturunca orkestratör otomatik doğuyor; salt okuma araçlarla derleniyor ve istemlerinde "Entropy" geçmiyor (testle sabit); plan çıktısındaki `new_agents` ile kendi alt ajanlarını yazıp derliyor. Entropy manifestte tüm orkestratörleri görüyor; `/desk`, `/ask` ile konuşuyor. Ofis içi düğüm-bağ bellek grafı; ofisten Entropy'ye tek yönlü akış.
- Gerçek kasada eski `Offices/` ve tohum `orkestrator/degerlendirici` kaldırıldı.

## Ekran görüntüleri
`scratch/ui/phase6/`: zen_1366x728, zen_1920x1040, chat_*, desk_*, graph_preview, desk_new_office, pixel_office_1x/2x.

## Faz 7'ye giden denetim bulguları (öz-denetim raporu)
Ofis raporlarının Rapor Merkezi'ne girmemesi (`Reports/reports` filtresi), Desk %88 oranı, oturma yerlerinin yığılması, bütçe korumasının başarısız kartlarda kör olması, yetim görevlerde terminal olay yokluğu, agy'de araç yasağı yaptırımı, bağlanmamış API'ler (orkestratör bağlamı, ofis grafı görünümü), Desk'te sağlayıcı/efor seçimi ve kota göstergesi, raporlardaki marka adı, kasa kirliliği (56 eski klasör).
