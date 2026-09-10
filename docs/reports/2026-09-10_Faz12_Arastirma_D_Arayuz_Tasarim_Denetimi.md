# Faz 12 — Araştırma D: Arayüz Tasarım Denetimi (Faz 11-E sonrası ikinci tur)

**Tarih:** 2026-09-10
**Kapsam:** Entropy AI masaüstü arayüzü (PySide6, v0.9.4, dal `ai/v0.1.7`, HEAD `1815f32`)
**Kip:** SALT OKUNUR. Kaynak kodda, testte, kasada, ayarlarda hiçbir değişiklik yapılmadı.
Tek yazılı çıktı bu dosyadır; ayrıca `scratch/ui/phase12/` altına ölçüm/görüntü üretildi.
**Önceki tur:** `docs/reports/2026-09-10_Faz11_Arastirma_D_Arayuz_Tasarim_Denetimi.md` (aynı sorular)
**Model çağrısı:** yok. **Marka kuralı:** ticari referans ürünün ve üreticisinin adı geçmez.

**Üretilen kanıtlar**
- `scratch/ui/phase12_audit.json` — `python scripts/ui_audit.py --json`
- `scratch/ui/phase12/zen_1366.png`, `zen_1920.png`, `chat_1280.png`, `chat_460.png`, `desk_1920.png`
- `scratch/ui/phase12/shots.py` (Faz 11-E betiğinin çıktı dizini değiştirilmiş kopyası)

> **Offscreen uyarısı (kalıcı not).** `QT_QPA_PLATFORM=offscreen` sanal ekranı **800×800**'dür.
> `desk_1920.png` istenen 1600×900 yerine **796×796** yakalandı (betik çıktısı: `desk_1920 796 x 796`);
> Desk penceresi bu turda gerçek boyutunda ölçülemedi. Ayrıca offscreen sürücü gerçek yazı tipini
> yüklemiyor: görüntülerde Türkçe harfler bozuk (`Tü Mü`, `Gö revler`) ve gövde metni küçük-kapital
> gibi çiziliyor. **Bu yüzden bu raporda tipografi kalitesi, harf aralığı ve yazı tipi kimliği
> hakkında hüküm verilmedi** — o kalem "doğrulanamadı" listesindedir (§8). Yerleşim, panel oranı,
> renk ve öğe sayısı ölçümleri offscreen'de geçerlidir.

---

## 0. Yönetici özeti

Faz 11-E gerçek ve ölçülebilir bir kazanım sağladı: **yerel stil 222 → 1**, **sabit boyut 87 → 17**,
**yazı kademesi 9 → 4**, **erişilebilir ad 0 → 110**, **kısayol 2 → 8**, kontrast/odak/hedef-boyutu
kapıları **0 ihlal**, Desk'te düz renk **0**. `scripts/ui_audit.py --gate --final` ve
`tests/ui/test_phase11_design_gates.py` + `tests/ui/test_design_system.py` → **60 passed**.

Buna karşılık kullanıcının asıl şikâyeti ("karmaşık yapı") **sayısal olarak kapanmadı**:
1366×768 Zen'de aynı anda görünen denetim sayısı **153 → 156** (Faz 11 hedefi ≤ 60). Bunun nedeni
teknik değil yönetsel: Faz 11-E'nin nihai kapı listesine (`FINAL_GATES`, `scripts/ui_audit.py:82-93`)
`interactive_count` **hiç konmadı**; yani yoğunluğu ölçen tek kapı devre dışı bırakıldı ve
merkez telemetri rozetleri (IA-3) ile rapor sayaç birleştirmesi (IA-4'ün ikinci yarısı) uygulanmadı.

İkinci kalıcı sorun: **tasarım sistemi widget sınırında duruyor, gömülü HTML/SVG/JS gövdelerine
girmiyor.** `markdown_renderer.py:222` içindeki liste hâlâ kaynak koda "High-contrast Cyberpunk
Palette" olarak yazılmış ve `#00F0FF / #00FF9D / #FF007F` (kroma **255**, saf tayf) içeriyor;
`knowledge_graph.py` 50 farklı düz renkle çiziyor ve `tokens.py`'de bu iş için tanımlanmış
`viz.*` ailesini (16 belirteç, `tokens.py:80-94`) **hiç kullanmıyor**. Denetim betiği bu gövdeleri
kontrast/emoji kapısına sokmadığı için `contrast_failures = 0` yanıltıcıdır: gömülü palette
`#7928CA` üzerinde okunan metin **2,80:1** (WCAG 4,5 eşiğinin altında) ve `#1F2B42` ayraç
**1,40:1** (WCAG 1.4.11 3:1 eşiğinin altında).

Üçüncüsü: **üst çubuk "18 → 4" iddiası beyana dayalıdır.** Kapı `win.header_items` listesinin
uzunluğunu ölçüyor (`tests/ui/test_phase11_design_gates.py:161`), kullanıcının gördüğü öğeyi değil.
Ölçtüm: Zen üst çubuğunda **12 görünür yaprak widget** (pencere düğmeleri hariç **9**), Chat'te **8**.

---

## 1. Sayısal envanter — Faz 11 notu vs bugün

### 1.1 `scripts/ui_audit.py --json` (2026-09-10, `scratch/ui/phase12_audit.json`)

| Alan | Faz 11-E öncesi (BASELINE) | Faz 11-E notu | **Bugün** | Nihai kapı | Durum |
|---|---:|---:|---:|---:|---|
| `distinct_hex` | 91 | 74 | **74** | — (uzun vade ≤ 14) | AÇIK |
| `hex_total` | — | — | **303** | — | AÇIK |
| `local_stylesheets` | 222 | 1 | **1** | ≤ 40 | YEŞİL |
| `fixed_sizes` | 87 | 17 | **17** | ≤ 20 | YEŞİL |
| `distinct_font_sizes` | 9 | 4 | **4** | ≤ 5 | YEŞİL |
| `distinct_paddings` | 58 | — | **35** | — (hedef ≤ 8) | AÇIK |
| `distinct_radii` | 8 | — | **7** | — (hedef 3) | AÇIK |
| `bold_declarations` | 157 | — | **58** | — (hedef ≤ %15) | KISMEN |
| `emoji_usages` (muaflar hariç) | 358 | 7 | **7** | ≤ 40 | YEŞİL |
| `emoji_raw` (muaflar dahil) | — | 67 | **67** | — | AÇIK |
| `distinct_emojis` | 71 | — | **2** | — | YEŞİL |
| `accessible_names` | 0 | 110 | **110** | — | YEŞİL |
| `shortcuts` (`QShortcut(`) | 2 | 8 | **8** | — | YEŞİL |
| `contrast_failures` | 5 çift | 0 | **0** | 0 | YEŞİL* |
| `focusless_selectors` | 109 düğme | 0 | **0** | 0 | YEŞİL |
| `small_targets` | 23 | 0 | **0** | 0 | YEŞİL |
| `desk_hex` / `desk_stylesheets` / `desk_emoji` | 17 / 35 / — | 0 / 0 / 0 | **0 / 0 / 0** | 0 / ≤10 | YEŞİL |
| `qss_bytes` | — | — | **10.010** | — | bilgi |
| `gate_violations` | — | 0 | **0** | 0 | YEŞİL |

\* `contrast_failures = 0` yalnızca `TOKENS` çiftleri için geçerlidir; gömülü HTML/SVG renkleri
kapının **kapsamı dışındadır** (§3.2, D12-02).

Kapı testleri: `QT_QPA_PLATFORM=offscreen python -m pytest tests/ui/test_phase11_design_gates.py
tests/ui/test_design_system.py -q` → **60 passed, 29,4 s**.

### 1.2 Canlı yerleşim ölçümü (offscreen, Zen 1366×768)

| Ölçüt | Faz 11 (önce) | **Bugün** | Faz 11 hedefi | Durum |
|---|---:|---:|---:|---|
| Görünür etkileşimli denetim | 85 | **86** | — | — |
| Görünür dolu etiket | 68 | **70** | — | — |
| **Toplam görünür denetim** | **153** | **156** | **≤ 60** | **KIRMIZI (kötüleşti)** |
| Sol gezinme görünen bölüm | 2 / 7 | **7 / 7** | 7/7 | YEŞİL |
| Üst çubuk beyan edilen öğe | 18 | **4** | ≤ 4 | YEŞİL (beyan) |
| Üst çubuk **görünür yaprak widget** | — | **12** (pencere düğmeleri hariç 9) | — | ölçüm yok |
| Üst çubuk yüksekliği / pencere % | 76 px / — | **50 px / %6,5** | ≤ %8 | YEŞİL |
| İç içe `QSplitter` derinliği | 4 | **2** | ≤ 1 (skill §2) | KISMEN |
| `QSplitter` sayısı | 7 | **4** | — | iyileşti |
| 24 px altı görünür hedef | 23 | **0** | 0 | YEŞİL |
| Terminal varsayılan | açık ve boş | **gizli** | gizli | YEŞİL |
| Bölücü konumu kalıcılığı | yok | **yok** (`QSettings` kod tabanında **0 kez**) | var | KIRMIZI |

Yeniden üretim: `scratch/ui/phase12/shots.py` + bu rapordaki inline ölçüm betiği (Ek B).

### 1.3 Kalan tasarım sorunları (kanıtlı)

Numaralandırma `D12-xx`; Faz 11 karşılığı parantezde.

---

**D12-01 (Y) — Ekran yoğunluğu düşmedi: 153 → 156.** (D-09/D-10/D-11 devamı)
Ölçüm: 1366×768 Zen'de 86 etkileşimli + 70 dolu etiket = **156**. Faz 11-E'nin kendi hedefi
"≤ 60" idi ve bu hedef `FINAL_GATES` (`scripts/ui_audit.py:82-93`) içine **konmadı**; dokuz kapının
hiçbiri yoğunluk ölçmüyor. Sonuç: kapılar yeşilken kullanıcının şikâyeti duruyor.

**D12-02 (Y) — Merkez telemetri rozetleri kaldırılmadı (IA-3 uygulanmadı).**
`zen_mode.py:530-545` hâlâ beş öğelik telemetri şeridi kuruyor: `zen_telemetry_status`,
`badge_memory`, `badge_skills`, `badge_mcp`, `badge_model`. `zen_1366.png` alt şeridinde görünüyorlar
("SİSTEM HAZIR · 729 düğüm / 927 not · Yetenekler: 21 aktif · MCP: 6 aktif · [gemini-3.8-flash] ·
EntropiAI · Desk"). Yineleme çiftleri **hâlâ**:

| Bilgi | Yüzey 1 | Yüzey 2 |
|---|---|---|
| Model | üst çubuk model kapsülü (`header_bar.py`) | `badge_model` (`zen_mode.py:540`) |
| Bellek düğümü | sağ graf paneli | `badge_memory` (`zen_mode.py:536`) |
| Yetenek sayısı | sol gezinme "Yetenekler" | `badge_skills` (`zen_mode.py:537`) |
| MCP durumu | sol gezinme "MCP Sunucuları" | `badge_mcp` (`zen_mode.py:538`) |
| Sistem/sağlayıcı durumu | üst çubuk durum kümesi | `zen_telemetry_status` (`zen_mode.py:530`) |

---

**D12-03 (Y) — Rapor sayaçları hâlâ iki ayrı kaynaktan geliyor ve ekranda çelişiyor.** (D-09 kalıntısı)
`zen_1366.png`: aynı ekranda "**Toplam 662 rapor**" ve "**658 / 658 kayıt**".
Kaynaklar bağımsız: `report_center.py:1151` → `self._result['total']`;
`reports_viewer.py:534` → `len(self._entries)`. Rapor **yüzeyi** 8 → 2'ye indi, ama **sayaç
tek kaynağa bağlanmadı**; kullanıcı hangi sayının doğru olduğunu hâlâ bilemiyor.
Ayrıca 1366'da rapor sınıfı bilgi aynı anda **dört** kutuda görünüyor: sol gezinme "Raporlar ve
Notlar" paneli + "Rapor Merkezi" özeti + `658/658` liste + okuyucu.

---

**D12-04 (Y) — Gömülü SVG/HTML gövdeleri eski "neon" paletini taşıyor; belirteç oraya girmedi.**
`src/entropy/ui/widgets/markdown_renderer.py:222-223`, kaynak koddaki yorumla birlikte:

```python
        # High-contrast Cyberpunk Palette
        palette = ["#00F0FF", "#00FF9D", "#FF007F", "#FFB300", "#7928CA", "#3B82F6", "#F59E0B", "#10B981"]
```

Aynı dosyada 17 farklı düz renk var (`#00F0FF` 14 kez, `#00FF9D` 8, `#070A0F` 8, `#1F2B42` 7).
Bunlar akış diyagramı, pasta grafiği, durum makinesi ve sıralı iletişim SVG çizicilerinde
(`:125-175`, `:222-236`, `:305-330`, `:350-370`) kullanılıyor. Kroma ölçümü:
`#00F0FF`, `#00FF9D`, `#FF007F` → **255** (saf tayf; skill §5'in "yasaklı desen" listesi).
Belirteç vurgusu `#4CC2FF` kroma **179**.

**Kontrast (kendi hesabım, sRGB göreli parlaklık, WCAG 2.x):**

| Renk | `#070A0F` üzerinde | `#141C2C` üzerinde | Eşik | Sonuç |
|---|---:|---:|---:|---|
| `#7928CA` | **2,80** | **2,41** | 4,5 | KALDI |
| `#1F2B42` (ayraç/kenarlık) | **1,40** | **1,20** | 3,0 | KALDI |
| `#FF007F` | 5,25 | **4,51** | 4,5 | sınırda |
| `#3B82F6` | 5,39 | **4,63** | 4,5 | sınırda |

Ayrıca gömülü belge zemini `#070A0F`, uygulama zemini `#0B0F14` ve panel yüzeyi `#121924` —
üçü farklı siyah: okuma yüzeyi kabuğundan bir tık kopuk (Faz 11'in D-01'i, gömülü katmanda tekrar).

**Not (haksız suçlamayı önlemek için):** dosyanın **gövde CSS'i** doğru tarafta —
`markdown_renderer.py:16` `reading_css`'i içe aktarıyor, o da `cyber_theme.py:89-114`
üzerinden `TOKENS`'tan türüyor. Sorun gövde metni değil, **SVG diyagram çizicileri ve mermaid
paleti**. Yani dosya yarı göç etmiş durumda.

---

**D12-05 (Y) — `viz.*` belirteç ailesi tanımlı ama kullanan yok.**
`tokens.py:80-94` on altı `viz.*` belirteci tanımlıyor (`add/del/hunk/meta/kind1..7/neutral`,
hepsi düşük kromalı). `knowledge_graph.py` (QWebEngineView tuvali) bu aileyi **hiç içe aktarmıyor**
(`grep -n 'TOKENS\|design import' src/entropy/ui/widgets/knowledge_graph.py` → **0 satır**) ve
**50 farklı düz renk** kullanıyor; içlerinde `#FF0055`, `#00F0FF`, `#00FF9D`, `#FF79C6`, `#C792EA`,
`#BC8CFF` gibi eski neon/mor ailesi de var — Faz 11'de "mor tamamen kaldırıldı" denmişti,
tuvalde duruyor. Denetim betiği `knowledge_graph.py`'yi emoji sayımından muaf tutuyor
(`scripts/ui_audit.py:56-62`) ama **renk sayımından muaf tutmuyor**; yine de kontrast kapısı
yalnızca `TOKENS` çiftlerine baktığı için tuval hiç sınanmıyor.

---

**D12-06 (O) — Üst çubuk kapısı beyana dayalı; gerçek öğe sayısı 3× fazla.**
`tests/ui/test_phase11_design_gates.py:155-166` `len(win.header_items) <= 4` ölçüyor.
`header_items` kodun kendi beyanı. Canlı ölçüm (offscreen, Zen 1366):
görünür **yaprak** widget sayısı **12** — `Entropy AI` etiketi, `CoreVisualizerWidget`,
model kapsülü düğmesi, `Tokens: 0`, `Bağlam: %0`, `InboxBadge`, iki sağlayıcı durum etiketi,
`Ctrl+K` düğmesi, üç pencere düğmesi. Chat'te **8**.
Ayrıca üç üst çubuk etiketi metin yerine **ham HTML** taşıyor (`<span style='color…'>` ile
başlayan `QLabel.text()` değerleri) — yani üst çubukta da satır içi renk yazımı sürüyor.

---

**D12-07 (O) — Bölücü konumları kalıcı değil; `QSettings` kod tabanında hiç yok.**
`grep -rn 'QSettings\|saveState()\|restoreState(' src/entropy/ui` → **0 eşleşme**.
`ui-design/SKILL.md:50` "bölücü konumları `QSettings`'e yazılır" diyor; uygulanmadı.
Kullanıcı her açılışta üç bölgeyi yeniden ayarlıyor. İç içe bölücü derinliği de **2**
(skill eşiği 1); `QSplitter` sayısı 4.

---

**D12-08 (O) — Açık tema ve "rahat" yoğunluk yazıldı ama ürüne bağlanmadı (ölü özellik).**
`tokens.py:146-189` `LIGHT_TOKENS` ve `density: compact|comfortable` üretiyor;
`qss.py:341` `apply_design_system(app, theme="dark", density="compact")`.
Tek üretim çağrısı `ui/manager.py:42` → `apply_design_system(app)` — **argümansız**.
`src/entropy/core/config.py` içinde `theme` veya `density` anahtarı **yok**
(`grep -n 'theme\|density' src/entropy/core/config.py` → 0 satır). Arayüzde seçici yok.
Yani D-18/D-19 kodda çözüldü, üründe çözülmedi.

---

**D12-09 (O) — Gömülü okuma yüzeyi 1280 px'te yatay kaydırma üretiyor.**
`chat_1280.png` ve `chat_460.png`: sohbet gövdesinin altında yatay kaydırma çubuğu var
(y ≈ 729 / 728). Neden aday: `markdown_renderer.py:495` kod bloğu `<pre>` için
`white-space` verilmemiş (satır 514-515'teki ikinci `<pre>` `white-space:pre-wrap` alıyor,
`:495`'teki almıyor) ve SVG diyagramları sabit `width` ile üretiliyor (`w = 640`, `:225`;
`total_w = max(500, …)`, `:349`). Skill §2 "1366×768'de taşma yok" diyor; **gömülü belge
taşması kapıya hiç girmiyor** (kapı yalnızca widget yerleşimini ölçüyor).

---

**D12-10 (D) — Dar pencerede üst çubuk çerçevesi ölü boşluk ayırıyor.**
`chat_460.png`: üst çubuk iki satır ama çerçeve ~148 px (pencerenin **%18,5'i**) ve ikinci
satırın sağında geniş boş alan var. Faz 11'deki %22,5'ten iyi ama hedeflenen ≤ %10 değil.
`zen_mode.py:492-505` `_apply_header_density()` eşiği 620 px; 460 px'te rozetler gizleniyor
ama çerçeve yüksekliği küçülmüyor.

---

**D12-11 (D) — "Yasaklı desen" sayaçları denetim betiğinde yok.**
`grep -rho ' · ' src/entropy/ui` → **63** (Faz 11: 36 — **arttı**);
`grep -rho '→' src/entropy/ui` → **38**. İkisi de `ui-design/SKILL.md:79-83`'te yasaklı desen.
`scripts/ui_audit.py`'nin emoji düzenli ifadesi (`:46`, `[\U0001F300-\U0001FAFF☀-➿⬀-⯿]`)
U+2600'ün altındaki okları **kapsamıyor**, bu yüzden 38 ok sayıma girmiyor.

---

**D12-12 (D, olumlu) — Faz 11'de riskli görülen iki dosya temiz çıktı.**
`report_chat_card.py`: düz renk **0**, `setStyleSheet` **0**.
`src/entropy/desk/**`: `desk_hex 0`, `desk_stylesheets 0`, `desk_emoji 0`.
Faz 11'in "Desk daha disiplinli" tespiti korunmuş ve tamamlanmış.

---

## 2. Bilgi mimarisi değerlendirmesi (11-E sonrası tıklama sayıları)

Sayımlar 1366×768 Zen üzerinde, `zen_1366.png` ve `zen_mode.py:586-620` (palet eylem listesi) ile.

| Kullanıcı görevi | Faz 11 öncesi | Faz 11 hedefi | **Bugün** | Kanıt | Durum |
|---|---|---|---|---|---|
| "Bildirimler"e gitmek | 6 (5 kaydırma + 1 sekme) | 1 | **1** (sol listede görünür) veya Ctrl+K → yaz | `NavList` 7/7 görünür | ✔ hedefte |
| Ajanın durumunu görmek | 3–5 | 1 | **1** | aynı | ✔ |
| Terminali açmak | 1 (Chat) / zaten açık ve boş (Zen) | 0 tıklama (Ctrl+`) | **0** (kısayol) veya 1 (Ctrl+K) | `zen_mode.py:673-678`, `terminal_pane.isHidden()=True` | ✔ |
| Son raporu okumak | 2–7 | 1 tıklama + yazı | **1 tıklama + yazı** (palette `report` kaynağı) veya 2 (liste + "Raporu oku") | `command_palette.py:177-195` | ✔ |
| Ajan **eforu** değiştirmek | üst çubukta efor kutusu | — | **komut satırı**: `/agent effort <ad> <seviye>` (arayüzde tek tık yok) | `STATE.md §3`, palet eylem listesinde `agent_*` **yok** (`zen_mode.py:593-609`) | ✖ **açık** |
| Kendi modelini değiştirmek | 2 + arama | 2, tek yerde | **2** (model kapsülü → seç) | `header_bar.py` model kapsülü | ✔ |
| Bellek denetimi (bilişsel hafıza incelemesi) | — | — | **2** (sağ panel → odak seçici) + `memory_inspector_dialog` ayrı yol; palet kaydı **yok** | `zen_1366.png` sağ sütun | ✖ kısmen |
| Desk'i açmak | 1 | 1 | **1** (alt şeritte "Desk" düğmesi) veya Ctrl+K → "Agent Desk'i aç" | `zen_mode.py:594` | ✔ |

**Komut paleti kapsamı — ölçüldü.** Palet iki kaynaktan besleniyor:
`zen_mode._collect_palette_items` (`:586-620`) **17 pencere eylemi** (`desk`, `project`,
`new_chat`, `terminal`, `mode_*`×3, `nav_*`×7, `toggle_lock`, `toggle_board_auto`) +
`command_palette.collect_palette_items` (`:196-232`) beş kaynak (slash komutları, yetenekler,
ajanlar, ofisler, son 80 rapor). Kısayol sayısı **8**.
**Boşluklar:** model/efor değiştirme, tema/yoğunluk, bellek denetleyicisi, rapor dışa aktarma
ve bölücü sıfırlama paletten çağrılamıyor.

**Ne iyileşti:** gezinme (sekme → dikey liste), üst çubuk yüksekliği, terminal varsayılanı,
kısayollar, palet eylem kaydı, erişilebilir adlar, hedef boyutu, odak halkası.
**Ne kaldı:** ekran yoğunluğu (156 denetim), rapor sayaç birliği, merkez rozet yinelemesi,
bölücü kalıcılığı, gömülü belge tema köprüsü, efor/tema için arayüz yolu.

---

## 3. Tasarım sistemi olgunluğu

### 3.1 Olgunluk konumu

NN/g'nin 6 boyutlu çerçevesi ve zeroheight'ın altı ekseni (temeller, dokümantasyon, yönetişim,
benimseme, ölçüm, AI hazırlığı) ile hizalayarak [K5][K6]:

| Boyut | Durum | Kanıt |
|---|---|---|
| **Temeller (belirteç)** | **Sağlam** — 12 renk + `viz.*` 16 + boşluk/köşe/tipografi/durum/yoğunluk/tema | `tokens.py` 266 satır |
| **Bileşen** | **Orta** — QSS tek girişte (10.010 bayt), ama adlandırılmış bileşen sınıfı yok; 14 bileşenlik hedefin (Faz 11 §3.7) yalnızca `navList`, `chip`, `statusDot`, `iconButton` karşılıkları var | `qss.py` 350 satır |
| **Dokümantasyon** | **İyi** — `skills/ui-design/SKILL.md` (sürüm 1.0.0) + Faz 11 denetim raporu | — |
| **Yönetişim / kapı** | **Orta-zayıf** — 9 kapı otomatik, ama yoğunluk kapısı yok, üst çubuk kapısı beyana dayalı, gömülü HTML hiç sınanmıyor | `scripts/ui_audit.py:82-93` |
| **Benimseme** | **Kısmi** — widget katmanı %100, gömülü HTML/SVG/JS katmanı ≈%0 | D12-04, D12-05 |
| **Ölçüm** | **İyi** — betik + 60 test, JSON çıktı, taban/nihai iki kapı kümesi | `--gate --final` yeşil |
| **Erişilebilirlik** | **İyi (widget) / Ölçülmemiş (gömülü)** | contrast_failures 0 vs D12-04 |

Kısacası: **Seviye 2'nin sonu / Seviye 3'ün başı** — yayımlanmış belirteç ve tek stil kaynağı var,
kapılar otomatik; eksik olan bileşen kütüphanesi, kapı kapsamı ve ikinci render motoruna
(gömülü HTML) erişim. Sektör verisi karşılaştırması: 2026 anketinde ekiplerin **%84'ü** belirteç
kullanıyor (bir yıl önce %56) ve çoğu ekip kendini Seviye 2 / erken Seviye 3 raporluyor [K6] —
Entropy bu ortalamanın hafif üstünde ama gömülü katman yüzünden "tek görsel dil" iddiasını
karşılamıyor.

### 3.2 Eksik bileşenler (Faz 11 §3.7 listesine göre)

Var: `navList`, `chip`, `statusDot`, `iconButton`, `panel`, `splitter`, `terminal`, `palette`.
**Eksik / dağınık:** `Button` varyantları (`primary/ghost/danger` `qproperty` ile), `Card`,
`ListRow`, `Reader` (gömülü belge yüzeyi — bugün üç ayrı yol: `reading_css`, chat balonu,
komut kartı), `Toast`, `Select`, `Input`. Bu yedi bileşen tanımlanmadan `distinct_hex 74 → 14`
hedefine inilemez.

### 3.3 Gömülü HTML tema köprüsü — teknik değerlendirme

İki farklı motor var, çözümleri de farklı olmalı:

| Yüzey | Motor | Bugün | Önerilen köprü |
|---|---|---|---|
| Rapor okuyucu, sohbet balonu, komut kartı, bellek denetleyicisi, Desk bellek paneli | **QTextBrowser / QTextDocument** (Qt zengin metin) | `<style>{reading_css()}</style>` + 17 düz renk SVG | `reading_css()` genişletilir; SVG çizicilere `TOKENS`/`viz.*` **parametre** geçirilir. Qt yalnızca CSS'in dar bir alt kümesini destekler (değişken, `rgba()`, `outline` yok) [K7][K8] — bu yüzden belirteçler **Python tarafında düz onaltılığa açılmalıdır**; `cyber_theme.py:93-97` bunu zaten doğru gerekçeyle yapıyor. Ek olarak `QTextDocument.setDefaultStyleSheet()` kullanılabilir ama aynı alt küme sınırı geçerlidir [K7]. |
| Bilişsel hafıza grafiği | **QWebEngineView** (tam Chromium) | 50 düz renk, `viz.*` kullanılmıyor | Tam CSS var: `:root { --viz-kind1: … }` değişken bloğu Python'dan enjekte edilir; JS tarafı `getComputedStyle` ile okur. Tema değişince tek bir `runJavaScript` ile güncellenebilir. |

`markdown_renderer.py`'nin yarı göç etmiş olması (gövde CSS'i belirteçten, SVG'ler düz renk)
köprünün mimari değil **kapsam** sorunu olduğunu gösteriyor: yol açık, iş yapılmamış.

### 3.4 Açık tema ve yoğunluk

Kod hazır (`LIGHT_TOKENS`, `density`), ürün bağlantısı yok (D12-08). Bağlamak için gereken en
küçük iş: `config` içine `ui_theme` / `ui_density` anahtarları, `ui/manager.py:42`'nin bunları
okuması, palete iki eylem (`toggle_theme`, `toggle_density`) ve `LIGHT_TOKENS` çiftleri için
kontrast kapısının açık temada da koşması. Gömülü HTML köprüsü (3.3) olmadan açık tema
açıldığında **rapor okuyucu koyu kalır** — bu yüzden sıralama: önce köprü, sonra tema seçici.

---

## 4. Kütüphane/araç kararlarının yeniden değerlendirmesi

Faz 11 kararı: *kendi belirteç sistemi + ikon için QtAwesome, başka arayüz kütüphanesi yok.*
**Bu tur bu kararı doğruluyor; değiştirme gerekçesi bulunamadı.**

| Aday | Lisans | Bugünkü yeniden değerlendirme |
|---|---|---|
| `PySide6-Fluent-Widgets` | GPLv3 / ücretli ticari [Faz 11 K8] | **RED sürüyor.** Lisans kesici. |
| `qt-material` | BSD-2 [K3] | **RED sürüyor**, ama **bir fikri alınmalı:** çalışma zamanı tema değiştirme ve **yoğunluk ölçeği** (`density_scale`) bizde de tanımlı ama bağlı değil (D12-08). Kütüphaneyi değil deseni al. |
| `Qt Advanced Stylesheets` (`qtass-pyside6`) | — | **YENİ ADAY, sınırlı ilgi.** Çalışma zamanı renk değiştirme + SVG ikon renklendirme sunuyor [K4]. Bizim `build_qss()` zaten aynısını yapıyor; tek çekici yanı SVG kaynak renklendirme — ama ikon tarafında QtAwesome bunu zaten çözüyor. **RED.** |
| `QDarkStyleSheet` v3 | MIT | v3 "tema çerçevesi" olarak konumlanıyor [K2]; bizim sorunumuz koyu tema değil kapsam. **RED sürüyor.** |
| **QtAwesome** | MIT | **KABUL sürüyor.** `design/icons.py` (158 satır) yerinde, emoji 358 → 7. Kalan risk: PyInstaller'da font dosyalarının boş çıkması — kapanış QA'sında `dist_check` duman testiyle doğrulanmalı (**henüz doğrulanmadı**, §8). |
| **Kendi belirteç sistemi** | — | **KABUL, olgunlaşıyor.** 266 + 350 satır; W3C Design Tokens Format Module 2025.10'a [Faz 11 K2] eşlenebilir durumda. |

**Yeni araç önerisi (küçük):** yoğunluk ölçümü için `scripts/ui_audit.py`'ye offscreen bir
"canlı" kol eklenmesi (bugün betik yalnızca statik; canlı sayılar ayrı test dosyasında).
Dış bağımlılık gerektirmez.

---

## 5. `ui-design` skill'inin güncellenmesi (öneri — bu turda YAZILMADI)

`skills/ui-design/SKILL.md` sürüm 1.0.0 → **1.1.0** için önerilen değişiklikler:

### 5.1 Değişmezlere eklenecek (§0)

> **8. Gömülü belge kuralı.** QTextBrowser/QWebEngine'e gönderilen HTML, CSS, SVG ve JS
> gövdelerinde düz onaltılık renk, emoji veya sabit piksel genişlik yazmak **yasaktır**.
> Renk `TOKENS` / `viz.*`'tan parametre olarak geçer; genişlik `%`/`viewBox` ile akışkan olur.
> **9. Durum kalıcılığı.** Kullanıcının elle ayarladığı her yerleşim değeri (bölücü konumu,
> panel açık/kapalı, tema, yoğunluk) `QSettings` ya da `config` üzerinden kalıcıdır.
> **10. Kapı beyana dayanamaz.** Bir kapı, kodun kendi beyan ettiği listeyi (ör. `header_items`)
> değil, canlı widget ağacını ölçer.

### 5.2 Ölçüm betiğine eklenecek kapılar (§6)

| Yeni alan | Ne ölçer | Önerilen eşik | Bugünkü değer |
|---|---|---:|---:|
| `embedded_hex` | gömülü HTML/SVG/JS gövdelerindeki düz renk (widget QSS'i hariç) | ≤ 16 (`viz.*` sayısı) | **≥ 67** (markdown 17 + graf 50) |
| `embedded_contrast_failures` | gömülü paletin kendi zeminine karşı WCAG 1.4.3/1.4.11 | 0 | **≥ 2** (`#7928CA` 2,80 · `#1F2B42` 1,40) |
| `pure_spectrum_colors` | kroma = 255 renk sayısı (tüm katmanlar) | 0 | **≥ 6** |
| `embedded_emoji` | gömülü gövdelerde emoji | ≤ 16 | **~24** (`knowledge_graph`) |
| `arrow_glyphs` | `→` ve akrabaları (emoji regex'i U+2600 altını kaçırıyor) | ≤ 5 | **38** |
| `midpoint_separators` | `' · '` üst-veri ayracı | ≤ 20 | **63** |
| `interactive_count_zen_1366` | canlı görünür denetim + dolu etiket | **≤ 90** (ara hedef), uzun vade ≤ 60 | **156** |
| `header_leaf_widgets` | üst çubuk **canlı** yaprak widget (pencere düğmeleri hariç) | ≤ 6 | **9** (Zen) / **7** (Chat) |
| `settings_persisted_splitters` | `QSettings` ile kaydedilen bölücü sayısı | = `QSplitter` sayısı | **0 / 4** |
| `themes_reachable` | üründe ulaşılabilir tema × yoğunluk kombinasyonu | ≥ 4 | **1** |
| `embedded_h_overflow` | 1366 ve 460 px'te gömülü belgede yatay kaydırma | 0 | **≥ 2 yüzey** |

`EMOJI_RE` düzeltilmeli: `[\U0001F300-\U0001FAFF☀-➿⬀-⯿]` → oklar (U+2190–U+21FF) ve
çeşitleme seçici (U+FE0F) eklenmeli.

### 5.3 Gerçek ekran kontrol listesi (yeni §7 — offscreen'in kapatamadığı boşluk)

Kapanış QA'sında gerçek pencerede, gerçek ekranda, gerçek yazı tipiyle doğrulanacak:

- [ ] 1366×768 ve 1920×1080'de tam ekran görüntüsü; Türkçe karakterler doğru (`ğ ş ı İ ö ü ç`)
- [ ] Yazı tipi gerçekten `Segoe UI Variable Text`/`Segoe UI`; mono yalnızca terminal/kod/model kimliği
- [ ] %100 ve %200 DPI'da yan yana; denetim yükseklikleri orantılı, kırpma yok
- [ ] Tab ile 10 durak: her durakta odak halkası **fotoğraflanır**
- [ ] Ekran okuyucu bir tur: ikon düğmelerinin adı okunuyor
- [ ] Rapor okuyucusunda bir SVG diyagram + bir kod bloğu: yatay kaydırma yok, renkler belirteçten
- [ ] Bilişsel hafıza grafiği: tuval renkleri `viz.*` ailesiyle aynı
- [ ] Bölücüler oynatılır, uygulama kapatılıp açılır: konumlar korunur
- [ ] Paketlenmiş `dist/EntropyAI/EntropyAI.exe` ile aynı tur (QtAwesome font riski)
- [ ] Offscreen ile gerçek ekran görüntüsü yan yana konur; fark listesi rapora yazılır

### 5.4 Süreçte değişiklik (§1)

**e. Kanıtla** maddesine: "Kapılar yeşil ama kullanıcı görevindeki tıklama sayısı ya da görünür
denetim sayısı düşmediyse iş **bitmemiştir**. Her arayüz işi en az bir görevin tıklama sayısını
ya da `interactive_count`'u düşürmelidir."

---

## 6. Faz 12 tasarım iş listesi

Sıra bağımlıdır: T1 → T2 (T2 açık temayı mümkün kılar), T3 bağımsız, T4 T1'den sonra.

---

### T12-1 — Gömülü belge tema köprüsü (QTextBrowser kolu)
**Kapsam:** `markdown_renderer.py` SVG çizicileri (`:120-180`, `:218-240`, `:300-335`, `:345-375`)
ve mermaid paleti (`:222-223`) `TOKENS`/`viz.*`'tan parametre alır; `#070A0F` zemini
`color.surface` ile hizalanır; `<pre>` bloklarına `white-space: pre-wrap`, SVG'lere akışkan genişlik.
**Kabul ölçütü:** `embedded_hex` (markdown dosyası) **17 → 0**; `pure_spectrum_colors` 0;
`embedded_contrast_failures` 0; `embedded_h_overflow` 0 (1366 ve 460); mevcut renderer testleri yeşil.
**Ekran görüntüsü ölçütü:** `scratch/ui/phase12/t1_reader_{1366,460}.png` — bir SVG diyagram +
bir kod bloğu içeren rapor; `chat_1280.png` ile yan yana, yatay kaydırma çubuğu yok.
**Ajan:** `ui-engineer`. **Risk:** Orta — SVG çizicilerinin testleri renk dizesine bakıyor olabilir;
azaltma: renkler önce sabit yerine `viz.*`'tan gelen **aynı** değerle değiştirilip test kırılması ölçülür.

---

### T12-2 — Graf tuvali `viz.*` ailesine bağlanır (QWebEngine kolu)
**Kapsam:** `knowledge_graph.py`'ye `:root` CSS değişken bloğu Python'dan enjekte edilir;
50 düz renk → `var(--viz-*)`; mor/neon aile (`#FF0055`, `#C792EA`, `#BC8CFF`, `#00F0FF`, `#00FF9D`)
kaldırılır; gömülü emoji tür simgeleri QtAwesome/Codicon SVG'lerine ya da `viz.*` renkli şekillere döner.
**Kabul ölçütü:** `knowledge_graph` düz renk **50 → ≤ 4** (yalnızca `#000`/`#fff` gibi teknik değerler);
`embedded_emoji` 24 → 0; tema değiştirildiğinde tuval **yeniden yüklenmeden** renk değiştiriyor
(tek `runJavaScript` çağrısı); mevcut graf testleri yeşil.
**Ekran görüntüsü ölçütü:** `t2_graph_{dark,light}.png` — aynı veri, iki tema, düğüm türleri ayırt edilebilir.
**Ajan:** `ui-engineer` (gerekirse `memory-rag-engineer` düğüm türü eşlemesi için).
**Risk:** Yüksek — 4.146 satırlık dosya, gömülü JS fizik motoru; azaltma: yalnızca renk sabitleri
değiştirilir, düzen/fizik koduna dokunulmaz; her renk için önce/sonra ekran görüntüsü.

---

### T12-3 — Yoğunluk indirimi: 156 → ≤ 90 görünür denetim
**Kapsam:** IA-3 tamamlanır — `zen_mode.py:530-545` telemetri şeridi kaldırılır, bilgileri
üst çubuk durum kümesine ve sol gezinmeye taşınır; rapor sayacı **tek kaynağa** bağlanır
(`report_center.py:1151` ve `reports_viewer.py:534` aynı sayıyı okur); 1366'da aynı anda
görünen rapor kutusu 4 → 2.
**Kabul ölçütü:** `interactive_count_zen_1366` **156 → ≤ 90**; ekrandaki tüm rapor sayaçları
**aynı sayıyı** gösterir (662/658 çelişkisi kapanır); `bus` aboneliklerinin hiçbiri kopmaz
(kaldırılan rozetin sinyali yeni yüzeye yönlendirilir); tam süit yeşil.
**Ekran görüntüsü ölçütü:** `t3_zen_1366.png` — `scratch/ui/phase12/zen_1366.png` ile yan yana;
alt telemetri şeridi yok, tek rapor sayacı görünüyor.
**Ajan:** `ui-engineer` (yerleşim) + `memory-rag-engineer` (sayaç tek kaynağı).
**Risk:** Yüksek — rozetler testlerde ve olay veri yolunda adıyla geçiyor; azaltma:
kaldırma değil **yönlendirme**, öznitelik adları takma ad olarak korunur.

---

### T12-4 — Tema/yoğunluk seçicisi + bölücü kalıcılığı
**Kapsam:** `config`'e `ui_theme` (`dark|light`) ve `ui_density` (`compact|comfortable`);
`ui/manager.py:42` bunları okur; palete `toggle_theme` ve `toggle_density` eylemleri; dört
`QSplitter` konumu `QSettings`'e yazılır/okunur; palete `reset_layout`.
**Kabul ölçütü:** `themes_reachable` 1 → **4**; `settings_persisted_splitters` 0 → **4**;
`LIGHT_TOKENS` çiftleri için kontrast kapısı da yeşil; uygulama kapatılıp açıldığında bölücü
konumları korunur (test: `QSettings` sahte kökle).
**Ekran görüntüsü ölçütü:** `t4_zen_light_1366.png`, `t4_zen_comfortable_1366.png`,
`t4_splitter_restore_{before,after}.png`.
**Ajan:** `ui-engineer`. **Risk:** Orta — açık tema T12-1/T12-2 bitmeden açılırsa okuma yüzeyleri
koyu kalır; **bu yüzden T12-4, T12-1 ve T12-2'den sonra gelir**.

---

### T12-5 — Kapı ve skill güncellemesi
**Kapsam:** `scripts/ui_audit.py`'ye §5.2'deki 11 yeni alan; `EMOJI_RE` düzeltmesi;
`FINAL_GATES`'e `interactive_count_zen_1366`, `header_leaf_widgets`, `embedded_*` kapıları;
`skills/ui-design/SKILL.md` 1.0.0 → 1.1.0 (§5.1, §5.3, §5.4); `tests/ui/` içinde
`header_items` beyan kapısının **canlı yaprak sayımıyla** değiştirilmesi.
**Kabul ölçütü:** yeni kapılar bugünkü kodda **kırmızı** rapor veriyor (yani gerçekten ölçüyorlar),
T12-1..T12-4 bitince yeşile dönüyor; `--gate --final` çıkış kodu doğru; taban değerler
(`BASELINE`) bu turun ölçümüyle güncelleniyor.
**Ekran görüntüsü ölçütü:** yok (betik çıktısı JSON önce/sonra).
**Ajan:** `qa-build-engineer`. **Risk:** Düşük — kapıları sıkılaştırmak mevcut yeşil süiti kırar;
azaltma: yeni kapılar önce `BASELINE` (regresyon) koluna, `--final` koluna ancak iş bitince eklenir.

---

### T12-6 — Gerçek ekran doğrulaması (kapanış QA'sı)
**Kapsam:** §5.3 kontrol listesinin tamamı, hem `run_entropy.py` hem paketlenmiş
`dist/EntropyAI/EntropyAI.exe` ile; offscreen ↔ gerçek fark listesi.
**Kabul ölçütü:** 10 maddenin 10'u işaretli; QtAwesome ikonları paketlenmiş sürümde **çiziliyor**;
Türkçe karakterler doğru; %200 DPI'da kırpma yok.
**Ekran görüntüsü ölçütü:** `scratch/ui/phase12/live_*.png` (en az 6 adet: zen/chat × 1366/1920,
odak yürüyüşü, ikon çubuğu).
**Ajan:** `qa-build-engineer`. **Risk:** Orta — canlı koşum kota harcamaz ama pencere gerektirir;
`dist/` kilidi için uygulama kapalıyken derlenmeli (`STATE.md` kırmızı çizgileri).

---

### 6.1 Özet gösterge tablosu (bugün → Faz 12 hedefi)

| Gösterge | Faz 11 öncesi | **Bugün** | Faz 12 hedefi |
|---|---:|---:|---:|
| `distinct_hex` (widget) | 91 | **74** | ≤ 20 |
| Gömülü düz renk (markdown + graf) | ~67 | **~67** | ≤ 16 |
| Kroma 255 renk | 8 | **≥ 6** | 0 |
| Zen görünür denetim (1366) | 153 | **156** | ≤ 90 |
| Üst çubuk canlı yaprak widget | — | **9** | ≤ 6 |
| Rapor sayacı tutarlılığı | 593 vs 648 | **662 vs 658** | tek sayı |
| Ulaşılabilir tema × yoğunluk | 1 | **1** | 4 |
| Kalıcı bölücü | 0/7 | **0/4** | 4/4 |
| Gömülü kontrast ihlali | ölçülmedi | **≥ 2** | 0 |
| `' · '` / `→` | 36 / — | **63 / 38** | ≤ 20 / ≤ 5 |
| Gerçek ekran doğrulaması | yok | **yok** | 10/10 madde |

---

## 7. Karar özeti

| # | Karar | Gerekçe (kanıt) | Sahip |
|---|---|---|---|
| K1 | Faz 11-E kütüphane kararı **korunur** (kendi belirteç sistemi + QtAwesome) | Yeni aday (`qtass`) ek değer getirmiyor; lisans engelleri sürüyor [K3][K4] | orkestratör |
| K2 | Faz 12'nin **birinci işi gömülü belge köprüsüdür**, kozmetik değil | Okuma yüzeyi tüm uygulamada kullanılıyor; `markdown_renderer.py:222` neon palet, 2 WCAG ihlali | `ui-engineer` |
| K3 | **Yoğunluk kapısı geri konur** (`interactive_count ≤ 90`) | 153 → 156; ölçen kapı `FINAL_GATES`'e hiç eklenmemişti | `qa-build-engineer` |
| K4 | Beyana dayalı kapılar **canlı ölçüme** çevrilir | `header_items` 4 diyor, canlı yaprak 12 | `qa-build-engineer` |
| K5 | Açık tema/yoğunluk **köprüden sonra** açılır | Bugün açılırsa rapor okuyucu koyu kalır (D12-08 + D12-04) | orkestratör |
| K6 | Rapor sayacı tek kaynağa bağlanır (veri işi, tasarım işi değil) | 662 vs 658, iki bağımsız sayaç | `memory-rag-engineer` |
| K7 | `ui-design` skill 1.1.0'a çıkar (11 yeni kapı + gerçek ekran listesi) | §5 | `qa-build-engineer` |
| K8 | Gerçek ekran doğrulaması **kapanış QA'sının zorunlu maddesi** olur | Offscreen 800×800 ve yazı tipi yükleyemiyor | `qa-build-engineer` |

## 8. Doğrulanamayanlar

1. **Tipografi kalitesi, yazı tipi kimliği, harf aralığı, gerçek okunabilirlik** — offscreen
   sürücü Segoe UI'yi yüklemiyor; görüntülerde Türkçe harfler bozuk. Gerçek ekran gerekiyor.
2. **Desk penceresinin gerçek yerleşimi** — offscreen sanal ekran 800×800; `desk_1920` istenen
   1600×900 yerine 796×796 yakalandı.
3. **DPI %200 davranışı** — offscreen'de ölçek uygulanamadı; `main.py` `PassThrough` politikası
   kod olarak doğru ama görsel doğrulaması yok.
4. **QtAwesome ikonlarının paketlenmiş sürümde çizildiği** — `dist/` üzerinde ikon duman testi
   bu turda koşulmadı (bilinen paketleme riski, Faz 11 [K11]).
5. **Yatay kaydırmanın kesin kök nedeni** — `chat_1280.png`/`chat_460.png`'de çubuk görünüyor;
   `<pre>` (`:495`) ve sabit SVG genişlikleri **aday** neden olarak işaretlendi, izole edilmedi.
6. **Klavye ile tam gezinilebilirlik ve tab sırası** — kısayol sayısı (8) ve odak kuralı (0 ihlal)
   ölçüldü; gerçek Tab yürüyüşü yapılmadı.
7. **Ekran okuyucu çıktısı** — 110 `setAccessibleName` var, hiçbiri gerçek bir ekran okuyucuyla
   dinlenmedi.
8. **`bold_declarations = 58`'in oransal anlamı** — toplam yazı bildirimi sayısı bu turda
   ölçülmedi, "≤ %15" hedefine göre karar verilemedi.

## 9. Kaynaklar

**Erişilebilirlik (birincil)**
- WCAG 2.2 SC 1.4.3 Contrast (Minimum) — https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- WCAG 2.2 SC 1.4.11 Non-text Contrast (≥ 3:1) — https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- WCAG 2.2 SC 2.4.7 Focus Visible — https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html
- WCAG 2.2 SC 2.5.8 Target Size (≥ 24×24) — https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

**Qt / PySide6 (birincil)**
- [K7] Qt — *Supported HTML Subset* (zengin metin motorunun desteklediği HTML/CSS alt kümesi) — https://doc.qt.io/qt-6/richtext-html-subset.html
- [K8] Qt for Python — `QTextDocument` (`setDefaultStyleSheet`) — https://doc.qt.io/qtforpython-6/PySide6/QtGui/QTextDocument.html
- Qt for Python — `QTextBrowser` — https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTextBrowser.html
- Qt for Python — *Styling the Widgets Application* — https://doc.qt.io/qtforpython-6/tutorials/basictutorial/widgetstyling.html

**Kütüphaneler (depo/birincil)**
- [K2] QDarkStyleSheet (MIT; v3 tema çerçevesi) — https://github.com/ColinDuquesnoy/QDarkStyleSheet
- [K3] qt-material (BSD-2; çalışma zamanı tema + yoğunluk ölçeği) — https://github.com/UN-GCPDS/qt-material · https://qt-material.readthedocs.io/
- [K4] Qt Advanced Stylesheets — PySide6 sürümü (`qtass-pyside6`) — https://github.com/githubuser0xFFFF/qtass-pyside6
- QtAwesome (MIT) — https://github.com/spyder-ide/qtawesome · PyInstaller font sorunu: https://github.com/spyder-ide/qtawesome/issues/78

**Tasarım sistemi olgunluğu ve belirteçler (2025–2026)**
- [K5] NN/g — *Design-System Maturity: A 6-Dimension Framework* — https://www.nngroup.com/articles/design-system-maturity/
- [K6] zeroheight — *Design System Maturity Model* (altı eksen; 2026 anketinde belirteç kullanımı %84) — https://zeroheight.com/maturity/
- Sparkbox — *Design Systems Maturity Model* — https://sparkbox.com/foundry/design_system_maturity_model
- USWDS — *Maturity model* — https://designsystem.digital.gov/maturity-model/
- Atomize — *Design System Maturity: 5 Levels + Scorecard (2026)* — https://atomize.tools/blog/design-system-maturity/
- W3C Design Tokens Community Group — *Design Tokens Format Module 2025.10* (28 Ekim 2025, ilk kararlı sürüm) — https://www.designtokens.org/tr/2025.10/format/

**2025–2026 masaüstü/AI arayüz desenleri (ikincil, blog)**
- *11 Best Design Systems Examples in 2026* — https://designsystems.surf/articles/11-best-design-system-examples-in-2026
- *Modern App Colors: Design Palettes That Work in 2026* (tek vurgu + nötr taban) — https://webosmotic.com/blog/modern-app-colors/
- *UI Color Trends to Watch in 2026* — https://updivision.com/blog/post/ui-color-trends-to-watch-in-2026
- *Design Systems in 2026: Scale UI Without the Chaos* — https://www.digitalapplied.com/blog/design-systems-2026-scale-ui-without-chaos-methodology
- Faz 11 notundaki [K3]–[K6] (sakin arayüz, komut paleti öncelikli gezinme, 60-30-10, aşamalı
  açığa çıkarma) bu turda da geçerli; tekrar edilmedi.

**Ajan yeteneği referansı**
- `frontend-design` yeteneği (yerel kopya, "üretilmiş tasarım imzaları" listesi ve iki geçişli
  süreç) — `C:\Users\batu_\.claude\plugins\marketplaces\claude-plugins-official\plugins\frontend-design\skills\frontend-design\SKILL.md`
- Vercel `web-interface-guidelines` (dosya:satır biçiminde bulgu üreten meta-yetenek deseni) —
  https://github.com/vercel-labs/web-interface-guidelines

**Depo içi kanıt**
- `scratch/ui/phase12_audit.json`, `scratch/ui/phase12/*.png`, `scratch/ui/phase11e/*.png`
- `scripts/ui_audit.py:30-93` (kapsam, muaflar, taban, nihai kapılar)
- `tests/ui/test_phase11_design_gates.py`, `tests/ui/test_design_system.py` (60 passed)
- `src/entropy/ui/design/{tokens.py,qss.py,icons.py}`, `src/entropy/ui/themes/cyber_theme.py`
- `src/entropy/ui/widgets/{markdown_renderer.py,knowledge_graph.py,report_chat_card.py,header_bar.py,nav_list.py}`
- `src/entropy/ui/modes/{zen_mode.py,chat_mode.py}`

---

## Ek A — Yeniden üretim komutları

```bash
python scripts/ui_audit.py --json scratch/ui/phase12_audit.json
QT_QPA_PLATFORM=offscreen python scratch/ui/phase12/shots.py
QT_QPA_PLATFORM=offscreen python -m pytest tests/ui/test_phase11_design_gates.py tests/ui/test_design_system.py -q -p no:cacheprovider

# statik sayımlar (Git Bash)
grep -rho ' · ' src/entropy/ui --include='*.py' | wc -l                      # 63
grep -rho '→'   src/entropy/ui --include='*.py' | wc -l                      # 38
grep -rn 'QSettings' src/entropy/ui --include='*.py' | wc -l                 # 0
grep -ohE '#[0-9a-fA-F]{6}' src/entropy/ui/widgets/markdown_renderer.py | sort -u | wc -l   # 17
grep -ohE '#[0-9a-fA-F]{6}' src/entropy/ui/widgets/knowledge_graph.py  | sort -u | wc -l   # 50
grep -n 'TOKENS\|design import' src/entropy/ui/widgets/knowledge_graph.py    # 0 satır
```

## Ek B — Canlı yerleşim ölçüm betiği (offscreen)

```python
# QT_QPA_PLATFORM=offscreen python - < bu_dosya
import sys; sys.path.insert(0, 'src')
from PySide6.QtWidgets import QApplication, QLabel, QAbstractButton, QComboBox, QLineEdit, QSplitter, QWidget
app = QApplication([])
from entropy.ui.design import apply_design_system; apply_design_system(app)
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.ui.modes.zen_mode import ZenModeWindow
z = ZenModeWindow(bridge=AgyProcessBridge()); z.setGeometry(0, 0, 1366, 768); z.show()
app.processEvents(); app.processEvents()
ctrl = [c for cls in (QAbstractButton, QComboBox, QLineEdit) for c in z.findChildren(cls) if c.isVisible()]
lbl  = [c for c in z.findChildren(QLabel) if c.isVisible() and c.text().strip()]
print("gorunur denetim:", len(ctrl) + len(lbl))                      # 156
print("ust cubuk yaprak:", len([c for c in z.header_frame.findChildren(QWidget)
                                if c.isVisible() and not c.findChildren(QWidget)]))  # 12
print("nav:", type(z.left_tabs).__name__, z.left_tabs.count())       # NavList 7
print("splitter:", len(z.findChildren(QSplitter)))                   # 4
print("terminal gizli:", z.terminal_pane.isHidden())                 # True
```
