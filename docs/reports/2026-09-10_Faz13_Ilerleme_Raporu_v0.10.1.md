# Faz 13 İlerleme Raporu — 13-A (v0.10.1): kullanıcı deneyimi, çekirdek, onaylı canlı koşular

Tarih: 2026-09-10 · Branch `ai/v0.1.7` · Taban `v0.10.0` · Etiket `v0.10.1` · Build: `dist\EntropyAI\EntropyAI.exe`

Plan: `2026-09-10_Faz13_Plan_ve_Yol_Haritasi.md` · Araştırma: `2026-09-10_Faz13_Arastirma_Notu.md` (kota 0). Bu rapor yalnızca **13-A**'yı ve **onaylı canlı koşuları** kapatır; 13-B (`brain` taşıması) ve 13-C (Desk kanıt zinciri) onay bekliyor.

## Sonuç (özet)
- **Dört şikâyetin kök nedeni ölçüldü ve kapandı (gerçek ekran, LG %200):**
  - *Düğmeler görünmüyor:* digest kartında iki eylem düğmesi boş metinle kuruluyordu ve `ghost` varyantı kenarlıksız + sönük metindi; okuyucu araç çubuğundaki beş düğmenin metni de ikonu da boştu (11-E emoji temizliğinin artığı). Artık metin/ikon + erişilebilir ad; piksel kontrastı koyu 15,1:1 / 9,4:1, açık 18,0:1 / 5,4:1.
  - *Tıklamada kasma:* her okundu/pin tıklaması bütün kart widget'larını yıkıp yeniden kuruyor (158 kartta 139 ms) ve 143 KB JSON'u senkron yazıyordu. Yerinde güncelleme + 1 sn ertelenmiş yazım (kapanışta flush): 180 kartta **5–6 ms**, gerçek kasada en kötü **42 ms** (bütçe 50).
  - *Sıkışıklık:* kart 675 px isterken panel 240 px'e sıkışabiliyordu; okuyucu 380 px ≈ 50 karakter/satır. Okuma kipi (okuyucu ≥ 560 px, gerçek ekranda 1.232 px; digest katlanır, "Gözden geçirmeye dön"), gözden geçirme kipinde kart ≥ 520 px, liste/okuyucu 35/65, başlık satırları akışkan (gerçek asgari 572 → 218 px). Görevler: gerçek asgari 1.356 px iken beyan 220 px'ti; artık beyan = hesaplanan, boş sütunlar katlanır, dar pencerede liste + detay (900 px'te gerçek fareyle doğrulandı), detay kutularına etiket, kart önizlemesinde ham markdown yok.
  - *Zen çekirdeği:* 11-E onu 24 px durum noktasına indirmişti. 136×136 px animasyonlu çekirdek sohbet alanının üst şeridine geri döndü (etkileşimsiz, metinle ve kaydırma çubuğuyla kesişmiyor, ayarlardan gizlenebilir, varsayılan görünür). `ARCHITECTURE.md` §8 "korunan kimlik öğeleri": çekirdek, marka kümesi, model kapsülü — sadeleştirme turları kaldıramaz; sözleşme testi ≥ 48 px.
- **Rapor başlığı:** "Tamamdır, şimdi senden yeni bir yetenek…" kullanıcının kendi isteminin ilk 40 karakteriydi (`agy_bridge.py`); daha derinde 8 anahtar kelimeli sezgi serbest sohbet turlarını rapora çeviriyordu. Şimdi: başlık gövdedeki H1'den türer (istem satırı hiçbir yolda kaynak değil; tek kaynak `core/report_title.py`), rapor üreten yalnız üç yol (pano kartı, `[OTONOM PLANLI GÖREV]`, açık `/learn`), serbest sohbet turları `Entropy/Sessions/<gün>/` altına `type: session` notu olarak iner, Rapor Merkezi bunları varsayılan dışı tutar ("Oturumlar" anahtarı). Eski dosyalar taşınmadı; görüntü katmanı `Gorev_` önekini ve zaman damgasını temizler. Yan bulgular: `[OTONOM PLANLI GÖREV]` rapor dalı Türkçe "I" küçültmesi yüzünden hiç çalışmıyordu (canlandı); yeteneksiz kartın raporu yabancı yetenek klasörüne düşüyordu (kartın `skill` alanı köprüye geçmiyordu; düzeltildi).
- **Kapılar (`ui-design` 1.2.0):** G13-1 boş etkileşimli öğe = 0, G13-2 ghost kenarlık kontrastı, G13-3 tıklama gecikmesi ≤ 50 ms (180 kart), G13-4 okuyucu ≥ 560 px + beyan ≥ hesaplanan; kapılar bilerek bozulmuş girdiyle kırmızıya dönüyor (test). §0 değişmezi: metni kaldıran sadeleştirme ikon + erişilebilir ad koymak zorunda. Kapı ölçerken gerçek kusur çıktı: ghost kenarlık 1,29:1 → 3,02:1.
- **Onaylı canlı koşular (karar 1, gerçek Claude):** wiki derlemesi financial-auditor 2 tur (17 sayfa; K6 %29 → **%36**), gri birleştirme turu (2 aday → 1 birleşti, kuyruk 0; K9 ölçüldü), beceri sentezi `media-agency-soldier` tek turda `validated` → onay betikle → kasada `Skills/media-agency-soldier/SKILL.md` (`SkillManager` keşfediyor), 4. kartta oturum devri (`handoff.md` 2,5 KB, yeni oturum kimliği, `--resume` yok, kart 18,5k ≤ 30k). **Gerçek regresyon:** `active_bridge()` claude yolunda var olmayan bir sınıfı içe aktarıyordu → kotalı hafıza turlarının hiçbiri claude sağlayıcısında koşamıyordu; düzeltildi, testle kilitlendi. Kota **75,3k** (tavan 70k, %7,6 aşım; aşım görülünce ikinci 25 turluk wiki partisi koşulmadı, 56 rapor bekliyor). K2 Hit@1 9/10 → 8/10 (eşik üstü, izleniyor).
- **Kapanış QA:** tam süit **2.521 test, 0 hata** (etiket öncesi son koşu); `ui_audit --gate --final` exit 0; build exit 0, `--version`, 20 sn canlı, günlükte `Traceback`/`CRITICAL` 0; yalıtım (ledger/skills_state/cognitive DB bit-bit aynı, kasada yeni rapor yok); marka taraması 0.

## Ölçüm tablosu
| Ölçüt | Önce | Sonra |
|---|---:|---:|
| Okundu tıklaması (sessiz bölüm açık, ~160–180 kart) | 139 ms | 5–6 ms (gerçek kasa en kötü 42) |
| Tıklama başına disk yazımı | 143 KB senkron | 0 (1 sn ertelenmiş, flush) |
| Boş etkileşimli öğe | 7 (2 kart + 5 araç çubuğu) | 0 |
| Ghost kenarlık / kart yüzeyi | 1,29:1 | 3,02:1 |
| Ghost kenarlık / yükseltilmiş şerit (koyu · açık) | 2,35:1 · 3,35:1 | 4,31:1 · 4,71:1 (`line.onraised`) |
| Sohbet açılışlı görünen başlık (gerçek kasa, 969 dosya) | 4 | 0 |
| Okuyucu genişliği (okuma kipi) | 380 px | ≥ 560 (gerçek 1.232) |
| Görevler asgari beyan / gerçek | 220 / 1.356 | beyan = hesaplanan (1.778 kanban · 442 liste) |
| Çekirdek Zen'de | 24 px nokta | 136 px animasyonlu |
| K6 wiki payı | %29 | %36 |
| Gri kuyruk | 2 | 0 |

## Son geçiş (kapanış QA'sının bulduğu iki kusur)
- Liste satırı hâlâ ham "Tamamdır…" başlığını gösteriyordu: `derive_report_title` hiçbir aday makul değilse ham frontmatter başlığına düşüyor, `read_report_meta` de yedek olarak ham başlığı veriyordu. Yedek sırası artık çekirdek gövde türetimi → dosya adı → çağıranın yedeği → en son ham başlık; okuma 4 → 8 KB (uzun frontmatter gövdeyi dışarıda bırakıyordu). Gerçek kasada sohbet açılışlı görünen başlık 4 → 0 (ör. "Tamamdır, şimdi senden yeni bir yetenek" → "Medya Ajansı ve URL İstihbarat Askeri … yeteneğini uçtan").
- Digest başlık şeridinde ghost kenarlık koyu temada 2,35:1 kalıyordu: yeni belirteç `line.onraised` (yükseltilmiş yüzeylerde), kontrast tablosuna iki çift; `ui_audit` ghost kapısı artık yüzey başına ölçüyor ve bilerek yanlış kenarlıkla kırmızıya dönüyor.

## Kalanlar
- Wiki: 56 rapor işlenmedi (kota); ikinci parti ~30k, yeni onay gerekir.
- `.entropy/logs/entropy_fault.log`'da eski oturumlardan beri tekrarlayan COM `0x8001010d` kaydı (uygulama ayakta kalıyor; kök neden araştırılmadı) → 13-D.
- Paketlenmiş exe'nin gerçek penceresinde piksel ölçümü alınmadı (kaynak ağacından gerçek `QApplication` ile alındı).
- 13-B (`brain` taşıması, kota 0, tek başına) ve 13-C (Desk kanıt zinciri ~60k, `[DESK …]` araçları, `claude_bg` arşivi) onay bekliyor.
