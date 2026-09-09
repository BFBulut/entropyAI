# Faz 8 İlerleme Raporu — v0.6.0

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiket `v0.6.0` · Build: `dist_check\EntropyAI\EntropyAI.exe` (uygulama açık olduğu için; aynalama: `robocopy C:\EntropiAI\dist_check\EntropyAI C:\EntropiAI\dist\EntropyAI /MIR`)

## Sonuç
Tam paket **2001 test geçti, 0 hata**, 5 dk 38 sn (Faz 7: 1933; +68). Kota: 0 model çağrısı. Araştırma notları: `2026-09-10_Faz8_Arastirma_Notu.md`, `2026-09-10_Faz8_Graf_Tasarim_Notu.md`.

## Senin bildirdiklerin ve çözümleri
- **Zen tam ekrandan çıkmış, taşınamıyor** → kök neden: Faz 6'nın "%92 kullanılabilir ekran" kuralı LG monitöründe tam 1766×949 veriyordu; çerçevesiz pencerede hiç fare işleyicisi yoktu. Şimdi Zen kullanılabilir ekranın tamamına açılıyor (gerçek Windows penceresinde 1920×1032 ölçüldü), üst çubuktan sürükleniyor (`startSystemMove`), kenardan boyutlanıyor, çift tık ve ─/❐ düğmeleriyle maksimize/geri; her mod geçişinde pencere ekrana kenetleniyor.
- **Chat ~2100 px, Zen düğmesi görünmüyor** → kök neden: üst çubuk yatay kaydırma alanındaydı, içerik 2447 px, Zen düğmesi x=2247'de. Üst çubuk artık alt satıra saran akış düzeni; Chat'te 620 px genişlikte bile Zen ve Desk düğmeleri görünür (canlı ölçüm).
- **Toplam raporlar görünmüyor** → kök neden: yenileme sınırı 60 (895 → 61'e düşüyordu), başlık dar panelde kırpılıyordu, 135 küme "sessiz"de katlıydı. Şimdi başlık "Toplam N rapor · M öne çıkan · K sessiz", "Tümü" düğmesi tam listeyi açıyor; gerçek kasada 899 rapor listeleniyor.
- **Bilgi grafı daha düzgün** → aşağıda.

## Bilgi grafı (araştırma + uygulama)
Veri (gerçek kasa, `scripts/graph_metrics.py`):

| Ölçüt | Önce | Sonra |
|---|---|---|
| Düğüm / kenar | 1149 / 3639 | 864 / 1784 (test artıkları ve sarkan kenarlar dışarı) |
| Sarkan kenar / öz-döngü / yinelenen | 376 / 23 / 175 | 0 / 0 / 0 |
| Tekil rapor etiketi | 147 | 645 (≤ 28 karakter) |
| Tek ebeveynin en çok çocuğu | 205 | 80 (konu alt dalları) |
| Topluluk / modülerlik | 83 / 0,44 | 16 / 0,73 (Louvain) |
| Zaman/önem/tür alanı olan düğüm | 0 | hepsi (kontrol şeridi ilk kez gerçek veriyle çalışıyor) |
| JSON | 1249 KB | 899 KB |

Kanvas (1100×760, Chromium ölçümü):

| Ölçüt | Önce | Sonra |
|---|---|---|
| Dünya yayılımı | 7505×7158 | 2044×2245 |
| Ağaç kenarı medyanı | 554 | 166 |
| Kesişme (örneklem) | 256 | 66 |
| Zoom 0,95'te görünen düğüm | 15 | 239 |
| Kare süresi medyan / p95 | 50 / 57 ms | 13 / 22 ms |
| Efsane + şerit örtüsü | %12 | %1,8 (tek satır, katlanabilir; ölü kontroller gizli) |

Yenilikler: seviye halkaları + sektör çekimi + derece ağırlıklı itme, 4 bantlı ayrıntı düzeyi (yumuşak geçiş, görünüm alanı kırpma), öncelikli etiket motoru (çakışma 0), hover'da soluklaştırma, dala tıkla → dala sığdır + breadcrumb, topluluk halesi ve etiketi, Ctrl+F arama, "yol göster", mini harita, 40+ çocuklu dallarda yelpaze kenar. Yapılmayan (P2): Web Worker fizik, artımlı güncelleme, çevrimdışı kenar demetleme.

## Harness ve sağlayıcılar
- Claude'da adım tavanı (akışta araç çağrısı sayacı; `--max-turns` CLI yardımında görünmediği için kapalı bayrakla hazır).
- Alt kart token tahmini uyarlanabilir: 8k–40k, istem uzunluğu ve ofisin başarılı alt kart medyanı (ledger medyanı 48k ölçüldü; sabit 30k bu yüzden yetersizdi). Ofis `budget_tokens: 0` = sınırsız.
- Orkestratör plan → değerlendirme → yeniden plan aynı konuşmada (`--conversation` / `--resume`); alt kartlar temiz bağlamda; agy'nin kümülatif usage'ı doğru düşülüyor.

## Test yalıtımı ve kasa
- Gerçek kasaya rapor yazan testler bulundu (arka plan köprüsü varsayılan kasa yolunu alıyordu; `entropy.core` paketinin `config` adını gölgelemesi yamayı atlatıyordu). Düzeltildi; tam paket öncesi/sonrası gerçek kasada yeni dosya 0.
- Test artıkları `Entropy/_archive/2026-09-09/test_artifacts/` altına taşındı (63 dosya). **Uyarı:** QA ajanının hatalı bir taşıma komutu 198 test artığı dosyayı (`Projects/test_bridge_background_task_*`, `test_project_directory_binding0`) arşive ulaştıramadan üzerine yazdı; içerikleri sahte test gövdeleriydi, kullanıcı verisi değil. Geri almak istersen tek yol OneDrive web geri dönüşüm kutusu.
- Depo kökündeki 41 test artığı (`module_task_*`, `schema_task_*`) hiçbir kod tarafından içe aktarılmıyor; silme kararı sende.

## Ekran görüntüleri
`scratch/ui/phase8/`: live_zen, live_chat, live_chat_zen (gerçek pencere), zen_maximized, chat_1280, chat_1366x768, report_center_total, graph_open/hover_dim/branch/search/path/minimap, before/after.

## Açık kalanlar
- Gerçek fareyle sürükleme yalnızca kod yolu olarak doğrulandı; exe'de bir kez elle dene.
- Graf kesişme hedefi 60'ın 6 üstünde.
- `--max-turns` varlığı ve `--conversation` bağlam sürekliliği canlı koşuda doğrulanmadı (kota).
- Zen üst çubuğu 1366 px'te iki satır (77 px).
