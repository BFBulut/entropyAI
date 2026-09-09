# Faz 9 İlerleme Raporu — v0.7.0

Tarih: 2026-09-11 · Branch `ai/v0.1.7` · Etiket `v0.7.0` · Build: `dist\EntropyAI\EntropyAI.exe` (doğrudan dist; uygulaman kapalıydı; `--help` 0, canlı koşum temiz)

Plan ve dayanaklar: `2026-09-11_Faz9_Gelistirme_Raporu.md` (öz-analiz + plan), `…_Faz9_Teshis_Notu.md`, `…_Faz9_Arastirma_A_…`, `…_Faz9_Arastirma_B_…`.

## Sonuç
Tam paket **2126 test geçti, 0 hata** (Faz 8: 2001; +125). Kota: bir tur izole Claude ölçümü (0,08 USD) + bir tek kelimelik model probu; agy 0.

## Çıkış ölçütü kanıtları
| Ölçüt | Sonuç |
|---|---|
| Claude'da Entropy kendi kimliğiyle, profilin sızmadan | Canlı tek tur: sistem istemi 15 parça → 1; Claude Code varsayılan istemi ve "auto memory" bloğu yok; araç 73 → 5; MCP 0. Yanıt: "Ben Entropy AI … komuta ettiğim ofis Araştırma Ofisi (orkestratör Alfa) … ajanlarım analist, arastirmaci, yazar" |
| ≥ %30 daha az token | İlk istek 34.920 → **7.120 token (−%79,6)**; abonelik oturumuyla, API anahtarı istenmedi |
| Zen "Görevler"de yalnızca kendi kartların | Kart deposu ayrıldı; Alfa'ya atadığın iki kart açılışta Araştırma Ofisi'ne devredildi (`Entropy/Desk/_migrations.log`, 3 satır); `Entropy/Tasks` 0 ofis kartı |
| `/desk msg` ile orkestratöre talimat | Talimat ofis kutusuna düşüyor, bir sonraki planda `[TALİMAT — kullanıcıdan gelen bağlayıcı yön]`; Desk'te "Ofise talimat" kutusu; ters yön (ofis → Entropy talimat) kodla reddediliyor |
| `config.provider = "claude"` iken uçtan uca | Sahte köprüyle ofis zinciri agy çağrılmadan kapanıyor; agy yoksa açılışta Claude'a düşüş; iki sağlayıcı ayarıyla hedefli paket yeşil |
| Sürükleme ve yenilemede donma yok | Gerçek ekranda Zen 1920×1032, üst çubuktan sürükleme (+144, +96 px), CRITICAL 0; rapor yenilemesinde ana iş parçacığı bloklanması 2142 → 0 ms |

## Bildirdiklerin ve çözümleri
- **Donma + beyaz hayalet pencereler:** çerçevesiz pencere süzgecindeki `int(Qt.Edge)` çökmesi giderildi, sistem taşıma tek sefer; rapor yeniden yükleme, zenginleştirme ve graf kurma işçi iş parçacığına alındı (1,5 sn debounce, artımlı önbellek).
- **Chat'te okundu / tümünü okundu / temizle:** Zen ve Chat tek paylaşılan durum; toplu tek yazım (700 → 1); yenileme durumu ezmiyor.
- **"AGENT" sahte raporu:** ajan dosyasını açmak artık rapor sinyali yaymıyor.
- **`/media-agency-soldier` → "Unknown command":** skill slash komutları Entropy'de çözülüyor (etkinleştir + metni temizle); bilinmeyen slash CLI'a gitmiyor.
- **"Desk Entropy'ye görev yolluyor":** yön hiç tersine dönmemişti; ortak klasör ve süzgeçsiz pano düzeltildi; Entropy formu Desk ajanlarını listelemiyor; Entropy kartına Desk ajanı atanırsa kart koşmadan düşüyor.
- **Claude'da "normal terminal":** "Entropy Saf Kip" varsayılan açık (`claude_isolated`): `--system-prompt-file`, `--strict-mcp-config`, `--setting-sources ""`, `--disable-slash-commands`, `--tools`, `--fallback-model`, Entropy ajanları `--agents` JSON'u ile; çalışma dizini git dışı `~/.entropy/workspace`; `--bare` kullanılmıyor (abonelikle çalışmıyor). İstem değişince eski oturum sürdürülmüyor.
- **Gemini modeli Claude'a gitti:** model doğrulama üç kapı (yazma, okuma, açılış onarımı); ayar dosyan onarıldı; kart kendi modelini ve kimliğini alıyor; defterde `model` sütunu.
- **Model listeleri:** agy listesi canlı `agy models` çıktısından (14 ad), Claude alias'ları dahil; Entropy ajan formu, Desk kadro/kart formları ve kart detayında sağlayıcıya bağlı model kutusu; üst çubuk geçersiz adı reddedip eski değere dönüyor; "fable 5.1 high effort" gibi serbest metin `fable` + `high` olarak çözülüyor (`fable` alias'ı canlı probda `claude-fable-5-1`'e açıldı).
- **Üst çubuk uzun, "süresi doldu":** iki kompakt rozet ("AGY ✓", "Claude ✓ max"; 1.278 → 158 px), ayrıntı ipucunda; token rozeti artık gerçek tur farkı + önbellek kalemi.
- **Boş kırmızı kare:** emoji yazı tipi yedeği; durum rozetleri yalnız emoji değil; canlı koşumda yazı tipi uyarısı 0.
- **Model kutusu kırpılması (Chat):** kutu en uzun ada göre ölçülüyor.

## Kasa ve geçişler (yedekli)
- `dogrulama` ofisinin kalan izleri (wiki sorgu sayfası, posta) arşive; wiki dizinindeki kırık bağ temizlendi.
- Entropy'nin tohum ajanlarındaki `office: arastirma-ofisi` kalıntısı tohumdan kaldırıldı.
- Açılış geçişleri: Araştırma Ofisi orkestratörü Alfa `tools_policy full → read-only` (kural), iki kart ofise devredildi; idempotent (ikinci koşumda 0 işlem).
- **Araştırma Ofisi senin canlı ofisin; arşivlenmedi.** Ofis dosyasındaki `default_model: fable 5.1 high effort` okuma anında çözülüyor; Desk'ten kaydedince normalize hâli yazılır.

## Ekran görüntüleri
`scratch/ui/phase9/`: live_04_zen_full, live_05_zen_after_drag, live_06_chat, live_07_chat_topbar, topbar_badges, report_center_chat_after_mark_all, desk_instruct_box, desk_board_office_cards, zen_tasks_entropy_only, model_lists, chat_topbar_620.

## Açık kalanlar
- Kart/plan çağrılarına ofis eforu uçtan uca geçmiyor (`TaskCard.effort` yok); ofis eforu şimdilik ajan tanımı üzerinden.
- Ofis konuşması plan ve değerlendirme farklı sağlayıcıdaysa sürmüyor (bilinçli, yalnızca günlükte).
- `--agents` JSON'unun büyük kadroda argv sınırını aşması hâlinde bayrak düşürülüyor (günlük); stdin yolu yok.
- `0x8001010d` COM uyarısı (`probe_agy`) ölümcül değil, sürüyor.
- Faz 10 araştırma notu ayrıca sunulacak; geçiş onayına bağlı.
