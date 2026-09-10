---
name: ui-design
description: >-
  Entropy AI'ın PySide6 arayüzünü tasarlarken ve değiştirirken uygulanacak tasarım
  sistemi, kontrol listesi ve ölçüm yordamı. Yeni bir panel/pencere/bileşen eklerken,
  mevcut bir ekranı sadeleştirirken veya "arayüz modern görünmüyor" türü bir istek
  geldiğinde kullanılır.
tags: ui, design, pyside6, accessibility, tokens
version: 1.3.0
---

# ui-design — Entropy arayüz tasarımı

Kaynak: `docs/reports/2026-09-10_Faz11_Arastirma_D_Arayuz_Tasarim_Denetimi.md`.
Belirteçler: `src/entropy/ui/design/tokens.py` · QSS: `design/qss.py` · ikon: `design/icons.py`.

## 0. Değişmezler (ihlal edilirse iş reddedilir)

1. **Tek kaynak.** Renk, boyut, boşluk, köşe yalnızca `entropy.ui.design.TOKENS`
   içinden gelir. Widget dosyasında düz onaltılık renk veya sihirli piksel yazmak yasak.
2. **Yerel stil yasağı.** Yeni `setStyleSheet` çağrısı eklenmez. Stil `objectName`
   veya `qproperty` (`role`, `variant`, `tone`) ile sınıflandırılır, kural `qss.py`'ye yazılır.
3. **Tek ekran.** Hiçbir kip 1366×768 kullanılabilir alanda kaydırma ya da taşma
   üretmez. Yeni bir panel eklemek, mevcut bir paneli kaldırmayı gerektirir.
4. **Tek vurgu.** Ekranda `color.accent` dışında vurgu rengi yoktur.
   `ok/warn/danger` yalnızca durum bildirir, dekorasyon değildir.
5. **Emoji ikon yasağı.** İkon `entropy.ui.design.icon()` (QtAwesome/Codicons)
   üzerinden gelir; her ikon düğmesinde `setAccessibleName()` bulunur.
6. **Odak görünür.** Odaklanabilir her denetimde 2 px `accent` halka vardır.
7. **Hedef boyutu.** Tıklanabilir hiçbir şey 24×24 px'in altında değildir (WCAG 2.5.8).
8. **Gömülü belge kuralı.** QTextBrowser/QWebEngine'e gönderilen HTML, CSS, SVG ve JS
   gövdelerinde düz onaltılık renk, emoji veya sabit piksel genişlik yazmak **yasaktır**.
   Renk `entropy.ui.design.embedded.palette()` / `css_variables()` / `js_palette_json()`
   üzerinden `TOKENS` ve `TOKENS["viz"]`'den gelir; genişlik `viewBox` + ölçek ya da
   `%` ile akışkan olur (`markdown_renderer.set_reader_width`).
9. **Durum kalıcılığı.** Kullanıcının elle ayarladığı her yerleşim değeri (bölücü konumu,
   panel açık/kapalı, tema, yoğunluk) `entropy.ui.design.prefs` (`QSettings`) üzerinden
   kalıcıdır. Yeni bir `QSplitter` eklersen aynı satırda
   `install_splitter_persistence("<ad>", splitter)` çağırırsın.
10. **Metin kaldırılıyorsa yerine ad konur.** Bir sadeleştirme turu bir
   etkileşimli öğeden metni kaldırıyorsa yerine **ikon + `accessibleName`**
   koymak zorundadır; ikisi de yoksa öğe **silinir**. (Faz 11-E'de üç kez
   ihlal edildi: slash paleti, terminal düğmesi, pin/arşiv düğmeleri; sonuç
   kullanıcının gerçek ekranda gördüğü "düğmeler görünmüyor" hatasıydı.)
11. **Kapı beyana dayanamaz.** Bir kapı, kodun kendi beyan ettiği listeyi (ör.
   `header_items`) değil **canlı widget ağacını** ölçer; "aynı anda görünen" =
   `isVisible()` **ve** `visibleRegion()` boş değil. Aynı kural genişlik için de
   geçerlidir: `setMinimumWidth` beyanı `minimumSizeHint()` hesabından küçükse
   beyan **yalandır** (Faz 13'te Görevler panosu 220 px beyan edip 1.356 px
   istiyordu).

12. **İkon nesnesi ≠ çizilen ikon.** `setIcon()` çağrılmış olması yetmez;
   `icon().pixmap(16,16).isNull()` **False** olmalıdır. QtAwesome bilinmeyen
   bir ada boş `QIcon` döndürür ve düğme ekranda boş kare olur. Metni olmayan
   her düğmede hem çizilebilir ikon hem `accessibleName` bulunur.
13. **`setParent(None)` yasak.** Widget'ı üst düzey pencereye çevirir; silinene
   kadar masaüstünde parlar. Yerine `ui/widgets/lifecycle.discard_widget()`.
14. **Tıklama ağır iş tetiklemez.** Bir denetim (kutu, anahtar, düğme) yalnızca
   durumu yazar ve kendi satırını günceller. Katalog/kasa taraması gibi ağır iş
   ≥ 300 ms birleştirilerek ertelenir ya da işçi iş parçacığına gider.
   Bir sinyalin kendi yazdığımız değişiklikten geri tepmesi bastırılır.

## 1. Süreç (her arayüz işi bu sırayla)

**a. Ölç.** Değişiklikten ÖNCE `python scripts/ui_audit.py --json before.json`
çalıştır; sayıları not et.
**b. Planla.** Bir paragraf: bu değişiklik hangi kullanıcı işini kaç tıklamada
yapılabilir kılıyor? Hangi öğe **kaldırılıyor**? (Eklemeden önce bir şey çıkar.)
**c. Brief'e karşı gözden geçir.** Planın herhangi bir parçası "her uygulamada olur"
tipindeyse (§5) o parçayı değiştir ve neyi neden değiştirdiğini yaz.
**d. Uygula.** Yalnızca belirteç ve bileşen sınıfı kullanarak.
**e. Kanıtla.** Kapılar yeşil ama kullanıcı görevindeki tıklama sayısı ya da
`interactive_count_zen_1366` düşmediyse iş **bitmemiştir**. Ölçüm betiğini yeniden çalıştır + offscreen ekran görüntüsü al
(1366×768 ve 1920×1080). Rapora önce/sonra sayı tablosu ve iki görüntü ekle.
Yeşil ölçüm olmadan iş "bitti" sayılmaz.

## 2. Yerleşim kuralları

- Bölge sayısı sabittir (Zen: sol bağlam / orta iş / sağ hafıza). Yeni bölge açılmaz.
- Her bölgede **aynı anda tek panel** görünür; diğerleri sol gezinme listesinden gelir.
- İç içe `QSplitter` derinliği **1**'i geçmez; bölücü konumları `QSettings`'e yazılır.
- İkincil şeritler (bildirim, ek, terminal, yan panel) **aynı anda en fazla bir tane**
  görünür; içerik alanı pencere yüksekliğinin **%55'inin** altına inmez.
- Aynı bilgi ekranda **bir kez** gösterilir. İkinci yüzey eklemeden önce birincisini kaldır.
- Boşluk 4 px ızgarasındadır: `space.1..6` = 4/8/12/16/24/32. Ara değer yoktur.

## 3. Tipografi ve dil

- Dört kademe: `title` 18 / `heading` 14 / `body` 13 / `label` 11; `mono` yalnızca
  terminal, kod ve model kimliği için.
- `bold` yalnızca `title` ve `heading` kademesindedir; gövde metninde kalın yok.
- Panel başlıkları cümle düzeninde: "Raporlar", "Bilişsel hafıza". BÜYÜK HARF yok.
- Düğme metni ne olacağını söyler: "Raporu aç", "Gönder", "Kalıcı yap" — "Tamam" değil.
- Aynı eylem akış boyunca aynı adı taşır.
- Boş durum bir davettir, hata bir yön tarifidir: ne oldu + ne yapılmalı. Özür dilemez.

## 4. Erişilebilirlik kontrol listesi (her iş)

- [ ] Metin kontrastı ≥ 4,5:1 (18 px+ kalın için ≥ 3:1)
- [ ] Denetim sınırı ve odak halkası kontrastı ≥ 3:1 (WCAG 1.4.11)
- [ ] Tıklama hedefi ≥ 24×24 px (WCAG 2.5.8)
- [ ] Her odaklanabilir denetimde görünür odak (WCAG 2.4.7)
- [ ] İkon düğmelerinde `setAccessibleName()`
- [ ] Tab sırası ekrandaki okuma sırasıyla aynı
- [ ] Yeni her eylemin komut paletinde bir kaydı var
- [ ] 1366×768'de taşma yok; 4K %200'de denetimler orantılı

## 5. Yasaklı desenler (üretilmiş arayüz imzaları)

Varsayılan oldukları için kullanılamaz; kullanılacaksa gerekçesi yazılır:
yakın-siyah zemin + tek parlak asit rengi vurgu · harf aralığı açılmış BÜYÜK HARF
eyebrow · " · " ile birleştirilmiş üst-veri dizeleri · her karta aynı yumuşak gölge
ve aynı yarıçap · küçük veri etiketleri için monospace · düğme metnine eklenmiş "→" ·
içeriğin sıralı olmadığı yerde 01/02/03 numaralandırma.

## 6. Ölçüm betiği

    python scripts/ui_audit.py                  # tablo
    python scripts/ui_audit.py --json out.json  # JSON
    python scripts/ui_audit.py --gate           # taban regresyon kapısı (çıkış kodu)
    python scripts/ui_audit.py --gate --final   # nihai hedefler (adım 6 sonunda yeşil)

Ürettiği alanlar: `distinct_hex`, `hex_total`, `local_stylesheets`
(+`_by_file`), `fixed_sizes`, `distinct_font_sizes`, `distinct_paddings`,
`distinct_radii`, `bold_declarations`, `emoji_usages`, `distinct_emojis`,
`accessible_names`, `shortcuts`, `contrast` (tema × çift × oran),
`contrast_failures`, `focusless_selectors`, `small_targets`, `gate_violations`.

Nihai kapı değerleri (`--final`, Faz 11-E adım 2–6 sonunda **yeşil**):

| Alan | Eşik | Ölçüm (2026-09-10) |
|---|---:|---:|
| `local_stylesheets` | ≤ 40 | **1** |
| `fixed_sizes` | ≤ 20 | **17** |
| `distinct_font_sizes` | ≤ 5 | **4** |
| `emoji_usages` (muaf dosyalar hariç) | ≤ 40 | **7** |
| `contrast_failures` | 0 | **0** |
| `focusless_selectors` | 0 | **0** |
| `small_targets` | 0 | **0** |
| `desk_hex` | 0 | **0** |
| `desk_stylesheets` | ≤ 10 | **0** |

Faz 12-D.2'de eklenen kapılar (`FINAL_GATES_12D2` + `FINAL_MIN_GATES`;
canlı olanlar `--live` ya da `--final` ile offscreen Qt kolunda ölçülür):

| Alan | Eşik | Ölçüm (2026-09-10, 12-D.2 sonrası) |
|---|---:|---:|
| `embedded_hex` | 0 | **0** (önce ≥ 67) |
| `embedded_contrast_failures` | 0 | **0** (önce ≥ 2) |
| `pure_spectrum_colors` | 0 | **0** (önce 3) |
| `arrow_glyphs` | ≤ 5 | **4** (önce 21) |
| `splitters_unpersisted` | 0 | **0** (12/12 kalıcı; önce 0/12) |
| `themes_reachable` | ≥ 4 | **4** (önce 1) |
| `interactive_count_zen_1366` | ≤ 90 | **50** |
| `header_leaf_widgets` | ≤ 6 | **6** (önce 8) |
| `embedded_h_overflow` | 0 | **0** |

Faz 13-A9'da eklenen dört kapı (`FINAL_GATES_13` + `FINAL_MIN_GATES`;
dördü de **canlı** offscreen Qt kolunda ölçülür, `--live` ya da `--final`):

| Kapı | Alan | Eşik | Nasıl ölçülür | Ölçüm (2026-09-10) |
|---|---|---:|---|---:|
| **G13-1** boş etkileşimli öğe | `empty_interactive_count` | 0 | görünür her `QAbstractButton`: `text()` dolu **veya** ikon boş değil **veya** `accessibleName()` dolu (WCAG 4.1.2) | **0** |
| **G13-2** düğme kontrastı (ghost dâhil) | `ghost_button_contrast` | 0 | ghost varyantında şeffaf zemin üzerindeki kenarlık `line.strong`/`surface` ≥ 3:1 (WCAG 1.4.11), metin ≥ 4,5:1 | **0** (önce 10) |
| **G13-3** tıklama gecikmesi | `click_latency_ms` | ≤ 50 (uyarı 100) | Rapor Merkezi, **sessiz bölüm AÇIK**, ≥ 150 sentetik küme; `QElapsedTimer` ile "okundu" tıklaması (RAIL) | **6 ms / 180 kart** |
| **G13-4** okuyucu asgarisi + beyan doğruluğu | `reader_min_width` ≥ 560 · `min_width_declaration_failures` | 560 · 0 | okuma kipinde gövde genişliği; panel beyanı ≥ `minimumSizeHint().width()` | **875 px · 0** |

Faz 13-A2'de **sertleşen ve eklenen** kapılar (kullanıcı gerçek ekranda
v0.10.1'de yedi kusur bildirdi; üçü 13-A kapılarından geçmişti):

| Kapı | Alan | Eşik | Ne değişti | Ölçüm (2026-09-10) |
|---|---|---:|---|---:|
| **G13-1** (sert) | `empty_interactive_count` | 0 | `icon().isNull()` YETMEZ: ikon `pixmap(16)` ile **gerçekten çizilebilir** olmalı; `accessibleName` artık kapıyı susturmaz (boş kare görsel bir kusurdur). Tarama **bütün gezinme ekranlarını** dolaşır (7/7), yalnızca açılış ekranını değil | **0** (önce 8) |
| **G13-1b** ekran okuyucu | `unnamed_icon_buttons` | 0 | metni de erişilebilir adı da olmayan düğme (WCAG 4.1.2) — ayrı sayaç | **0** |
| **G13-3** (genişledi) | `click_latency_ms` | ≤ 50 | Rapor Merkezi'ne ek olarak **Yetenekler "Etkin" kutusu** (26 yetenek) de ölçülür; kapı ikisinin en büyüğünü alır | **6 ms** (toggle önce **152 ms**, panel içi 1.961 ms) |
| **G13-5** hayalet pencere | `orphan_reparents` | 0 | kaynak ağacında `setParent(None)` sayısı; desen widget'ı üst düzey pencereye çevirir | **0** (önce 12) |

Kapıların **gerçekten ölçtüğü** `tests/ui/test_phase13_ux.py` ve
`tests/ui/test_phase13a2_ux.py` içinde kanıtlanır:
bilerek adsız bırakılmış bir düğme G13-1'i, 200 ms uyuyan bir işleyici G13-3'ü,
yalan beyanlı bir panel G13-4'ü kırmızıya çevirir.

Bilgi (kapı değil): `screens_swept` (7), `skill_toggle_ms`, `skill_rebuild_ms`,
`midpoint_separators` (bugün 77), `emoji_raw`,
`splitters_total`, `click_latency_cards`, `board_view_mode_1366`.

## 7. Gerçek ekran kontrol listesi (offscreen'in kapatamadığı boşluk)

Offscreen sürücü 800×800 sanal ekran kullanır ve gerçek yazı tipini yüklemez;
aşağıdakiler **gerçek pencerede, gerçek ekranda** doğrulanır (QA):

- [ ] 1366×768 ve 1920×1080 tam ekran görüntüsü; Türkçe karakterler doğru (`ğ ş ı İ ö ü ç`)
- [ ] Yazı tipi gerçekten `Segoe UI Variable Text`/`Segoe UI`; mono yalnızca terminal/kod/model kimliği
- [ ] %100 ve %200 DPI yan yana; denetim yükseklikleri orantılı, kırpma yok
- [ ] Tab ile 10 durak: her durakta odak halkası fotoğraflanır
- [ ] Ekran okuyucu bir tur: ikon düğmelerinin adı okunuyor
- [ ] Rapor okuyucusunda bir SVG diyagram + bir kod bloğu: yatay kaydırma yok, renkler belirteçten
- [ ] Bilişsel hafıza grafiği: tuval renkleri `viz.*` ailesiyle aynı; **açık temada da okunur**
- [ ] Ayarlar diyaloğunda tema/yoğunluk değiştirilir: pencere yeniden başlatılmadan döner
- [ ] Bölücüler oynatılır, uygulama kapatılıp açılır: konumlar korunur
- [ ] Paketlenmiş `dist/EntropyAI/EntropyAI.exe` ile aynı tur (QtAwesome font riski)

Emoji sayımından muaf dosyalar (`EMOJI_EXEMPT`): `design/icons.py` (emoji → ikon
eşlemesi), `design/tokens.py` (belge dizesi), `widgets/ui_polish.py` (emoji yazı
tipi yedeği), `widgets/knowledge_graph.py` (gömülü HTML/JS kanvasının `viz.*`
görsel dili). Bu dosyalardaki emoji arayüz ikonu değil, göç altyapısıdır.

Yerleşim kapıları offscreen Qt gerektirir ve
`tests/ui/test_phase11_design_gates.py` içinde ölçülür:
üst çubuk öğe sayısı ≤ 4 · 1366×768'de gezinme 7/7 görünür ve taşma 0 ·
kabuk bölücü zinciri 2 · Chat kromu 1280×800'de ≤ %25 · 460 px'te üst çubuk
≤ 2 satır · palet eylemleri + kısayollar.

**Uzun vadeli hedefler (henüz açık):** `distinct_hex` ≤ 14 (bugün 74) ve
`emoji_usages` = 0. Kalan renkler ve emoji, widget stillerinde değil **gömülü
HTML/JS gövdelerindedir** (sohbet balonları, rapor kartları, graf tuvali);
bunların belirtece bağlanması ayrı bir dilimdir.
