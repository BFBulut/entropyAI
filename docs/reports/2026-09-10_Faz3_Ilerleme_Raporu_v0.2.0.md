# Faz 3 İlerleme Raporu — v0.2.0 (Entropy Agent Desk)

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Etiket `v0.2.0` · Build: `dist\EntropyAI\EntropyAI.exe` (doğrudan dist)

## Sonuç
Entropy Agent Desk v1 tamam: ofisler, ofis harness'ı, bağımsız pencere, piksel sahne, ofis belleği ve grafik düğümleri. Tam paket **1635 test geçti, 0 hata** (Faz 2: 1529). Gerçek uçtan uca ofis koşusu yapıldı; pahalı ama öğretici oldu ve beş gerçek kusuru açığa çıkardı, hepsi kapatıldı.

## Yapılanlar
- **Ofisler:** `Entropy/Offices/<ofis>/OFFICE.md` (orkestratör, değerlendirici, üyeler, sağlayıcı/model, paralellik, bütçe, tüzük); tohum `arastirma-ofisi`; ajanlara `office`/`role`/çift model alanı; derlemede sağlayıcı-model eşlemesi (Claude tarafına Gemini adı gitmiyor).
- **Harness:** orkestratör ≤5 alt kartı JSON ile planlar → paralel yürütme (`max_parallel`) → değerlendirici notlar, düşük notta tek retry → üst kart inceleme + ofis raporu (wiki query sayfası + ofis özeti + log) + ofis belleği. Durum dosyada, kesintiden devam (`resume_all`), `/desk`, `/desk task`, `/desk stop`, `/offices`, manifestte ofisler.
- **Pencere:** "🏢 Agent Desk" düğmesi (Zen ve Chat); bağımsız pencere, konum/ekran hatırlanır; ofis paneli (oluştur/düzenle/sil), piksel sahne (ızgara düzen, durumlar, tıkla → akış), roster (ofis ajanları, rol atama), ofise süzülmüş kanban, akış ve bellek sekmeleri.
- **Hafıza/grafik:** ofis belleği (ajan belleğiyle aynı motor), bağlam kurucuya ofis belleği, ofis raporları, grafikte ofis/ajan/query düğümleri (renk+ikon, "Ofisler" odağı), handoff süzgeci.

## Gerçek koşu (kota onayınla) ve dersleri
Kart: "Entropy AI sürüm notu taslağı" (Faz 1–2 raporlarından 10 madde). Orkestratör 20 sn'de geçerli plan üretti (3 alt kart). Yazar ajanı ölçütleri karşılayan 10 maddelik notu üretti. Ama zincir 15 dk'da kesildi ve **546k token** harcandı (hedef 30–60k). Kök nedenler ve düzeltmeler:
1. Köprü, proje kilidi alınamayınca `on_result` çağırmadan dönüyordu → kart sonsuza dek "çalışıyor". Düzeltildi (agy + Claude).
2. Paralel kartlar aynı proje yazma kilidini istiyordu → ikinci kart hep ölüyordu. Artık okuma niyetli kartlar paylaşımlı kilit, yazanlar sırayla, kilitte bekleyen kart yeniden kuyruğa.
3. Kart özeti `##` başlığında kesiliyordu (29k karakter → 81) → değerlendirici boş özet görecekti. Simetrik kaçış ile kayıpsız.
4. Tohum `orkestrator`/`degerlendirici` mevcut kasaya yazılmıyordu → ad bazlı tohumlama (`.seeded.json`).
5. Bütçe koruması tahminle çalışıyordu (742 vs 546k) → gerçek ledger token'ı, kart düzeyi bütçe, aşımda süren alt kartlar sonlandırılır; alt kart istemlerine maliyet disiplini (yalnızca verilen dosyalar, ≤20 adım). agy'de adım sınırı bayrağı yok (`--help` ile doğrulandı).
Ek: Claude arka plan işçisinin imza hatası (görev hiç bitmiyordu) ve tek-kopya sunucusunun ana iş parçacığında olması (UI meşgulken ikinci kopya bildirimi düşüyordu) da bu turda kapandı.

Bu gece ikinci gerçek koşu yapılmadı; kota kararın "ilerde değişebilir" olduğu için sabah sen karar ver. Koşunun ürettiği kart ve rapor dosyaları kasada duruyor (`Tasks/20260909-062725-…`, `Wiki/queries/…`).

## Ekran görüntüleri
`scratch/ui/phase3/01_desk_window.png … 08_zen_topbar_desk.png`. Kozmetik: uzun metinlerde kırpma, ofis panelinde gereksiz yatay kaydırma (Faz 4'te).

## Açık kalanlar
- Değerlendirme, retry, ofis raporu ve belleği gerçek sağlayıcıyla uçtan uca doğrulanmadı (sahte köprüyle doğrulandı).
- Süren tek görevin ortasında bütçe aşımı yakalanamıyor (sinyal görev kimliği taşımıyor); kaçak en fazla bir alt kart kadar.
- Gerçek ikinci monitörde pencere doğrulanmadı (offscreen tek ekran).
- Ajan başına ayrıştırılmış canlı akış yok (tek `token_chunk_received`).

## Faz 4 (doğrudan geçiliyor, yetkinle)
Wiki katmanı (index/log/kavram sayfaları) + `/lint`; bağlam kurucunun sayfa seçmesi; arayüz modernizasyonu (kırpma/eliding, kaydırma, Faz 2–3 notları, okunaklı tasarım sisteminin Agent Desk'e uygulanması, Zen'de "Rapor" akışı ön hazırlığı); legacy klasörünün temizlenmesi (içinde eski marka adı geçiyor); performans trendi; `v0.2.1`.
