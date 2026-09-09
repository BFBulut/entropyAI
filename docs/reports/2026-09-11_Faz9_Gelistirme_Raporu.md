# Faz 9 Geliştirme Raporu — Teşhis, Öz-Analiz ve İki Fazlık Plan

Tarih: 2026-09-11 · Branch `ai/v0.1.7` · Taban `v0.6.0` · Hedef: Faz 9 → `v0.7.0` (bu faz, doğrudan uygulanıyor), Faz 10 → `v0.8.0` (ayrı araştırma + senin onayınla)

Dayanaklar (hepsi kanıtlı, dosya:satır ve günlük alıntılı):
- `2026-09-11_Faz9_Teshis_Notu.md` — bugün bildirdiğin 8 belirtinin kök nedenleri
- `2026-09-11_Faz9_Arastirma_A_Saglayici_Model_Kimlik.md` — Claude/agy sağlayıcı, model envanteri, Entropy kimliği
- `2026-09-11_Faz9_Arastirma_B_Agent_Desk_Yol_Haritasi.md` — ticari referans ve 2026 benzerleriyle özellik matrisi, boşluk analizi, Faz 9/10/11 yol haritası

## 1. Bugün gördüklerin: kök nedenler (özet)

| Belirti | Kök neden | Kanıt |
|---|---|---|
| Donma + basamaklı beyaz "Entropy AI (Yanıt Vermiyor)" pencereleri | Faz 8'de eklediğim çerçevesiz pencere yardımcısı gerçek Windows'ta her fare hareketinde çöküyordu: `int(Qt.Edge)` PySide6'da TypeError (11 CRITICAL). Üstüne, her rapor güncellemesinde 703 raporun ana iş parçacığında yeniden okunup kümelenmesi ve graf zenginleştirmenin (Louvain ~2,5 sn) ana iş parçacığında koşması. Beyaz pencereler Windows'un donmuş üst düzey pencereler için çizdiği hayaletler; kodda pencere üreten döngü yok | `frameless.py:91`, `report_center.py:1201`, günlük 20:32–20:46 |
| Chat'te okundu / tümünü okundu / temizle çalışmıyor | Zen ve Chat ayrı `ReportInboxStore` örnekleri açıp aynı `report_inbox.json`'u son-yazan-kazanır mantığıyla eziyor; her işaretleme tüm dosyayı yazıyor; yeniden yükleme durumu eziyor | `reports_viewer.py:216`, `chat_mode.py:682`, `report_inbox.py:112` |
| "Yeni Araştırma Raporu: AGENT" | Ajan dosyasını açan düğme yanlış sinyali (`report_created`) yayıyor; kasada böyle bir rapor yok, "RAG'a işlendi" iddiası sahte | `agents_widget.py:1186` |
| `/media-agency-soldier` → "Unknown command" | Slash token'ı temizlenmeden CLI'a gidiyor; "Unknown command" metni Claude Code'un, Entropy'nin değil | `chat_mode.py:1322` |
| "Görev: Canivo Reklam" — "Desk Entropy'ye görev yolluyor" | Yön tersine dönmedi; **depo ve görünüm ortak**: ofis kartları ile Entropy kartları aynı `Entropy/Tasks/` klasöründe, Zen "Görevler" sekmesi ofis süzgeci olmadan kurulmuş. Kart eski build'in tohumladığı `arastirma-ofisi` ofisinin orkestratörü `Alfa`'ya atanmış (kalıntı) | `tasks.py:51`, `zen_mode.py:315`, `task_board_widget.py:480` |
| Claude'da "normal terminal" gibi, düşünme zayıf, 77k token | Entropy'nin kimliği Claude Code'un 12.438 karakterlik varsayılan isteminin **sonuna ekleniyor** (7.844 karakter); senin Claude Code profilin (otomatik bellek talimatı, 3 kişisel bellek dosyası, 14 ajan, 119 araç, MCP sunucuları) her tura giriyor çünkü çalışma dizini git deposunun içinde ve `--strict-mcp-config` yok. Gerçek konuşma içeriği 77k'nın %3'ü; "+77k" gösterimi de hatalı (oturum toplamı kopyalanıyor) | `claude_bridge.py:1058`, `:929`; transcript ölçümü |
| Claude Code `gemini-3.1-pro-high` ile başlatıldı | `settings.json` içinde `provider_models.claude = "gemini-3.1-pro-high"` (doğrulamasız yazılmış); kart kendi `model` alanını hiç uygulamıyor, üst çubuğun köprüsünü ödünç alıyor | `config.py:118`, `tasks.py:587` |
| Model listelerinde gerekli modeller yok | agy yedek listesi bayat (`gemini-3-pro`, `gemini-2.5-*` — `agy models` çıktısında yok); Desk kadro/kart formlarında model alanı hiç yok | `agents_widget.py` FALLBACK_MODELS |
| Üst çubuk çok uzun, "süresi doldu (yenilenecek)" | Sağlayıcı durum rozeti düz metin: 1.278 px (hedef ≤ 160) | `provider_badge.py`, `identity.py:203` |
| Boş kırmızı kare | "Segoe UI Emoji" yazı tipi yüklenemiyor (176 uyarı); yalnız emoji içeren durum göstergesi boş çiziliyor | günlük |

## 2. Öz-analiz: Faz 1–8'de ne yaptım, nerede yanıldım

**Doğru gidenler.** Sağlayıcı soyutlaması ve Claude Code köprüsü; ajan/kart/ofis dosya modeli; bi-temporal bellek grafı ve uzlaştırma; wiki + lint + handoff; Report Center ve graf okunurluğu (Faz 8 ölçümleri: dünya 7505→2044, kare 50→13 ms); Desk'in ayrı kök ve orkestratör kurallarının koda ve teste bağlanması; her fazda tam paket + build + sürüm etiketi.

**Yanıldığım yerler (ve dersleri).**
1. **Yalnız offscreen doğrulama.** Faz 8 pencere yardımcısı offscreen'de test edildi ve "gerçek sürükleme denenemedi" notuyla teslim edildi; gerçek Windows'ta her fare hareketinde çöktü. Ders: pencere/olay katmanı için gerçek ekran koşusu QA'nın zorunlu adımı olacak (Faz 9'da yapıldı: canlı pencere ölçümü + exe koşusu).
2. **Ana iş parçacığında ağır iş.** Rapor Merkezi sınırını 60'tan 5000'e çıkarırken yeniden yüklemeyi iş parçacığına almadım; graf zenginleştirmeyi ana iş parçacığında bıraktım. Ders: 50 ms'yi aşan her iş işçi iş parçacığına + debounce.
3. **Kimliği eklemek yerine değiştirmek gerekiyordu.** Claude için "varsayılan istemi koru, Entropy'yi ekle" tasarımı bilinçliydi ama yanlış: Entropy'nin sesi Claude Code'un sesinin altında kaldı, senin kişisel profilin sızdı ve maliyet 2,5 kat arttı.
4. **Ortak depo.** Desk'i ayırırken kartları ayırmadım; Zen'in panosuna ofis süzgeci koymadım. Yön kuralı koda değil teamüle dayandı.
5. **Yazım kapısı yok.** Ayar dosyasına yanlış sağlayıcının modelinin yazılabilmesi, arka plan kartının kendi modelini uygulamaması ve model listelerinin bayatlaması aynı eksikliğin üç yüzü.
6. **Kalıntı temizliği eksik.** Eski build'in tohumladığı ofis ve orkestratör kasada kaldı; Entropy'nin görev formu onu atanabilir ajan olarak sundu.
7. **Test yalıtımı geç geldi.** Testler gerçek kasaya 195 rapor yazdı; Faz 8'de kapatıldı ama QA'nın taşıma komutu 198 test artığı dosyayı üzerine yazdı (kullanıcı verisi değildi). Ders: arşiv kopyala-doğrula-sil; kasaya dokunan her betik önce kuru koşum.

## 3. Faz 9 planı (uygulanıyor, `v0.7.0`)

Beş iş paketi, dört ajan, dosya sahipliği ayrık:

**A. Kararlılık (ui-engineer).** Çerçevesiz pencere düzeltmesi (bayrak kontrolü, tek sefer sistem taşıma, istisna koruması); rapor yeniden yükleme ve graf kurma işçi iş parçacığına + 1,5 sn debounce + artımlı; tek paylaşılan Report Center durumu, toplu yazım; sahte AGENT raporu kaldırıldı; skill slash komutları Entropy'de çözülüyor; emoji yazı tipi yedeği; `setOpenLinks(False)`; kompakt sağlayıcı rozetleri ("AGY ✓" / "CC ✓", ≤ 160 px, ayrıntı ipucunda).

**B. Claude izolasyonu ve model kapıları (agy-1).** "Entropy Saf Kip" (`claude_isolated`, varsayılan açık): `--system-prompt-file` ile Claude Code'un istemi **değiştirilir**; `--strict-mcp-config`, `--setting-sources ""`, `--disable-slash-commands`, `--tools`, `--disallowedTools mcp__*`, `--add-dir <proje>`, `--fallback-model`; çalışma dizini git deposunun dışında (`~/.entropy/workspace`); `--bare` kullanılmaz (abonelikle çalışmıyor). Model doğrulama üç kapı (yazma, okuma, açılış onarımı); kartın kendi `model` alanı ve sağlayıcı-model eşlemesi yürütme yolunda; defterde `model` sütunu; istem değişince eski oturum sürdürülmez; token rozeti tur farkı + önbellek ayrımı; agy yoksa otomatik Claude.

**C. Entropy sistem istemi (memory-rag).** Tek kurucu (sohbet + kart): kimlik, araç sözleşmesi (varsayılan istem düştüğü için açıkça), bilişsel bağlam, ajan manifesti, sohbet özeti; ≤ 8.000 karakter; ofis arşivinde wiki sorgu sayfaları da taşınır; rapor listesinde mtime önbelleği.

**D. Desk ↔ Entropy ayrımı (agy-2).** Ofis kartları `Entropy/Desk/Offices/<ofis>/cards/`, Entropy kartları `Entropy/Tasks/` (idempotent geçiş + günlük); Zen panosu yalnızca Entropy kartları; `/desk msg <ofis> :: <talimat>` → orkestratörün bir sonraki planına `[TALİMAT]`; yön kilidi (Entropy kutusu yalnızca rapor/durum kabul eder); sabit `agy` varsayılanları `config.provider`'dan; Entropy kartına Desk ajanı atanamaz; eski tohum ofis işaretlenir (QA arşivler).

**E. Arayüz 2. tur (ui-engineer, A bitince).** Zen panosu ofis süzgeci; model listeleri (agy canlı liste, Claude alias'ları, Desk kadro/kart formlarına model alanı, üst çubukta doğrulama); Desk "Ofise talimat" kutusu; sprite tıklaması → o ajanın akışı; Entropy ajan formunda Desk ajanları yok.

**QA.** Tam paket; mimari kural testleri (pano ofis kartı göstermez, Entropy kutusu talimat reddeder, orkestratör istemi Entropy içermez, kaynaklarda marka adı yok); kalıntı ofis arşivi; gerçek ekranda pencere koşusu; `dist` build (uygulaman kapalıysa); izole kipte tek turluk Claude ölçümü (senin kota onayınla, hedef: ilk tur taban bağlamı 34.920 → ≤ 15.000 token).

**Faz 9 çıkış ölçütü.** Claude'da Entropy kendi kimliğiyle, senin profilin sızmadan ve ≥ %30 daha az tokenle konuşur; Zen "Görevler"de yalnızca kendi kartların; `/desk msg` ile orkestratöre talimat gider ve plana girer; `config.provider = "claude"` iken uçtan uca çalışır; uygulama sürükleme ve rapor yenilemede donmaz.

## 4. Faz 10 (araştırma sonra, senin onayınla, `v0.8.0`)
Desk'i gerçek geliştirme ofisine çevirmek: köprü akışına ajan etiketi → ajan başına adlandırılmış terminal; proje = depo + dal; kart başına git worktree; taslak PR akışı (gh yoksa diff özeti); "Değişiklikler" sekmesi; maliyet/kota şeridi (yüzdelik çubuk yok, motorlar kotayı yayımlamıyor); orkestratöre gerçek web araştırma aracı; "makbuz" görünümü ve koşan karta durdurmadan yorum; ekip şablonları. Ayrıntılı kabul ölçütleri araştırma B §7'de. Faz 9 kapanınca Faz 10 için ayrı bir araştırma notu yazıp geçiş için onayını isteyeceğim.

## 5. Faz 11+ (yol haritası)
Öğrenen Entropy: MCP kayıt defteri keşfi (ad alanı doğrulama rozeti), skill kayıt defteri (`owner/repo`, topluluk kaynağında onay), skill bağlam bütçesi ölçeri, üç kapılı kendi-skill-yazma döngüsü (öner → öz-doğrula → onayla), onaylanabilir bellek kuralları, ajanlarıyla çok taraflı tartışma, şifreli sır kasası, kanıt kaydı. Kapsam dışı: bulut koşum, mobil/sesli yüzey, yüzdelik kota çubuğu.

## 6. Senden beklenenler
- Faz 9 sonunda: `dist` build'ini açıp Claude'da bir tur konuşman (kimlik ve token), Zen'de üst çubuktan sürükleme, Chat'te "Tümünü okundu say".
- Faz 10'a geçiş onayı (araştırma notuyla birlikte isteyeceğim).
- Depo kökündeki 41 test artığı dosyanın (`module_task_*`, `schema_task_*`) silinmesi için onay.
