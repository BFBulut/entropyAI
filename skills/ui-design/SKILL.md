---
name: ui-design
description: >-
  Entropy AI'ın PySide6 arayüzünü tasarlarken ve değiştirirken uygulanacak tasarım
  sistemi, kontrol listesi ve ölçüm yordamı. Yeni bir panel/pencere/bileşen eklerken,
  mevcut bir ekranı sadeleştirirken veya "arayüz modern görünmüyor" türü bir istek
  geldiğinde kullanılır.
tags: ui, design, pyside6, accessibility, tokens
version: 1.0.0
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

## 1. Süreç (her arayüz işi bu sırayla)

**a. Ölç.** Değişiklikten ÖNCE `python scripts/ui_audit.py --json before.json`
çalıştır; sayıları not et.
**b. Planla.** Bir paragraf: bu değişiklik hangi kullanıcı işini kaç tıklamada
yapılabilir kılıyor? Hangi öğe **kaldırılıyor**? (Eklemeden önce bir şey çıkar.)
**c. Brief'e karşı gözden geçir.** Planın herhangi bir parçası "her uygulamada olur"
tipindeyse (§5) o parçayı değiştir ve neyi neden değiştirdiğini yaz.
**d. Uygula.** Yalnızca belirteç ve bileşen sınıfı kullanarak.
**e. Kanıtla.** Ölçüm betiğini yeniden çalıştır + offscreen ekran görüntüsü al
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
