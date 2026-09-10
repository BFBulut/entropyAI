# Faz 11 — Araştırma D: Arayüz Tasarım Denetimi ve Modern Tasarım Sistemi Önerisi

**Tarih:** 2026-09-10
**Kapsam:** Entropy AI masaüstü arayüzü (PySide6, v0.8.0, dal `ai/v0.1.7`)
**Kip:** Salt okunur denetim. Kaynak kodda hiçbir değişiklik yapılmadı; tek yazılı çıktı bu rapordur.
**Ölçüm betikleri (yalnızca `scratch/`):**
`scratch/ui/phase11/audit_measure.py`, `scratch/ui/phase11/audit_chrome.py`, `scratch/ui/phase11/audit_tabs.py`
**Ölçüm çıktıları:** `scratch/ui/phase11/measure.json`, `chrome.json`, `tabs.json`
**Ekran görüntüleri:** gerçek pencere `scratch/ui/phase9/live_04_zen_full.png`, `live_06_chat.png`, `live_07_chat_topbar.png`; offscreen `scratch/ui/phase11/*.png`
**Model çağrısı:** yok (bütün sayılar statik çözümleme ve offscreen Qt ölçümüyle üretildi).
**Marka kuralı:** Ticari referans ürünün ve üreticisinin adı bu belgede geçmez.

---

## 0. Yönetici özeti

Kullanıcının "çok fazla tasarımsal hata var, modern görünmeyen karmaşık bir yapı" tespiti ölçülebilir biçimde doğrulandı. Üç kök neden var:

1. **Tasarım sistemi yok, iki yarım sistem var.** `cyber_theme.py` içinde birbiriyle çelişen iki palet (`CYBER_THEME` ve `READING_TOKENS`) bulunuyor; arayüz kodunda ise **99 farklı altıgen renk**, **223 yerel `setStyleSheet` çağrısı**, **58 farklı `padding` kombinasyonu** ve **9 farklı yazı boyutu** dolaşıyor. Bileşenler tek bir kaynaktan değil, kendi kendilerinden stil alıyor.
2. **Bilgi mimarisi katmerli.** Zen'de tek ekranda **153 görünür denetim** var; sol sekme çubuğunun 7 sekmesinden 1920×1080'de yalnızca **3'ü**, 1366×768'de **2'si** görünüyor. Aynı bilgi (rapor/bildirim) **8 ayrı yüzeyde** tekrarlanıyor.
3. **Görsel dil 2015'in "neon/oyuncu" estetiği.** Vurgu renklerinin **8'i saf tayf rengi** (kroma 255, S=%100), yazı bildirimlerinin **%63'ü kalın**, panel başlıkları emoji + BÜYÜK HARF + camgöbeği kalın — bu kombinasyon üretilmiş arayüzlerin bilinen imzası (bkz. §7 [K7]).

Ayrıca üç somut erişilebilirlik ihlali bulundu: **109 düğmenin hiçbirinde odak halkası yok** (0 adet `QPushButton:focus`), **23 denetim 24 px'lik asgari hedef boyutunun altında**, ve **kenarlık rengi 1,39:1** ile 3:1 eşiğinin çok altında.

Önerilen yol: kütüphane satın almak veya Material/Fluent'e geçmek değil — **kendi belirteç (token) sistemimizi kurup QSS'i tek yerden üretmek**; ikon için `QtAwesome` (MIT), gövde için mevcut PySide6. Ayrıntı §4'te.

---

## 1. Sayısal envanter ve kanıtlı tasarım sorunları

### 1.1 Envanter tablosu

| Ölçüt | Değer | Nasıl ölçüldü | Sağlıklı hedef |
|---|---:|---|---:|
| Farklı altıgen renk (`src/entropy/ui/`) | **99** | `grep -rhoE '#[0-9a-fA-F]{6}'` → `sort -u` | 10–14 |
| Toplam renk yazımı (aynı kod tabanında) | **856** | aynı, `-u` olmadan | ~0 (hepsi belirteçten) |
| Kroma ≥ 200 olan (aşırı doygun) renk | **11** | `max(RGB)-min(RGB)` | 0–1 |
| Kroma = 255 (saf tayf rengi) | **8** | aynı | 0 |
| Farklı `font-size` değeri | **9** (9/10/11/12/13/14/15/18/22 px) | `grep -rhoE 'font-size:\s*[0-9]+px'` | 4–5 |
| Toplam `font-size` bildirimi | 248 | aynı | — |
| `font-weight: bold`/`600`/`700` bildirimi | **157** (bildirimlerin ≈%63'ü) | `grep -rhoE 'font-weight:[^;]+'` | ≤ %15 |
| Farklı `font-family` bildirimi | **18** | `grep -rhoE 'font-family:[^;]+'` | 2 |
| Farklı `border-radius` | **8** (3/4/5/6/8/9/10/12 px) | `grep -rhoE 'border-radius:\s*[0-9]+px'` | 3 |
| Farklı `padding` kombinasyonu | **58** | `grep -rhoE 'padding:\s*[0-9px ]+;'` | 6–8 |
| Farklı `setContentsMargins` kombinasyonu | **23** | `grep -rhoE 'setContentsMargins\(...\)'` | 4 |
| Farklı `setSpacing` değeri | **9** (0,2,3,4,5,6,8,10,12) | aynı | 3 |
| Farklı `letter-spacing` değeri | **8** | `grep -rhoE 'letter-spacing:[^;]+'` | 1 |
| `setStyleSheet` çağrı yeri | **223** | `grep -rc 'setStyleSheet'` | ≤ 5 |
| `setFixedWidth/Height/Size` | **87** | `grep -rhoE 'setFixed(Width\|Height\|Size)'` | ≤ 10 |
| Farklı sabit denetim yüksekliği | **6** (20/22/24/26/28/30 px) | aynı | 2–3 |
| `QPushButton` örneği | **109** | `grep -rho 'QPushButton('` | — |
| `QLabel` örneği | **124** | aynı | — |
| Emoji ikon kullanımı / farklı emoji | **376 / 76** | Unicode aralık taraması | 0 / 0 |
| `QIcon` kullanımı (tepsi ikonu hariç) | **0** | `grep -rn 'QIcon('` | — |
| `QPushButton { }` bloğu / `:hover` / `:focus` / `:pressed` | **59 / 59 / 0 / 0** | `grep -rho` | 59/59/59/59 |
| `setAccessibleName` | **0** | `grep -rho` | 109 (ikon düğmeleri için) |
| Klavye kısayolu (tüm uygulama) | **2** (Ctrl+K, Ctrl+Shift+F) | `grep -rn 'QShortcut('` | 10+ |
| " · " orta nokta ayracı | **36** | `grep -rho ' · '` | — |

**Zen (offscreen, `measure.json`)**

| Ölçüt | 1920×1080 | 1366×768 |
|---|---:|---:|
| Görünür etkileşimli denetim (düğme+kutu+alan) | **85** | **85** |
| Görünür dolu etiket | 68 | 68 |
| **Toplam görünür denetim** | **153** | **153** |
| Üst çubuk doğrudan çocuk sayısı | **18** | 18 |
| Üst çubuk satır sayısı / yüksekliği | 2 / 76 px | 2 / 75 px |
| Sol sekme sayısı | 7 | 7 |
| **Görünen sekme sayısı** | **3 / 7** | **2 / 7** |
| Sekme çubuğu taşması | **438 px (%39)** | **638 px (%57)** |
| İç içe `QSplitter` derinliği | 4 | 4 |
| Kapsayıcı derinliği (splitter+tab+scroll) | **7** | 7 |
| Çekirdek görselleştiricinin merkez sütunu doldurma oranı | **%6,7** | %12,1 |

**Chat (offscreen, `chrome.json` — tüm ikincil şeritler açıkken)**

| Ölçüt | 1280×800 | 640×860 | 460×800 |
|---|---:|---:|---:|
| Üst çubuk satırı / yüksekliği | 2 / 68 px | **4 / 126 px** | **6 / 180 px** |
| Üst çubuğun pencereye oranı | %8,5 | %14,7 | **%22,5** |
| İçerik dışı "krom" toplamı | **603 px** | 506 px | — |
| **Sohbet gövdesine kalan yükseklik** | **139 px (%17,4)** | 302 px (%35,1) | — |

### 1.2 Kanıtlı sorunlar

Aşağıdaki her madde `dosya:satır` ve/veya ekran görüntüsüyle bağlanmıştır. Önem: **Y**üksek / **O**rta / **D**üşük.

---

**D-01 (Y) — İki çelişen palet aynı dosyada yaşıyor.**
`src/entropy/ui/themes/cyber_theme.py:3-17` `CYBER_THEME` sözlüğünü, `:27-55` ise `READING_TOKENS` sözlüğünü tanımlıyor. Aynı rolü farklı değerlerle dolduruyorlar:

| Rol | `CYBER_THEME` | `READING_TOKENS` | Fark |
|---|---|---|---|
| vurgu | `accent_cyan` `#00F0FF` | `accent` `#38D9FF` | farklı ton + doygunluk |
| ana metin | `text_primary` `#F0F6FC` | `text` `#E8EFF7` | farklı |
| panel yüzeyi | `bg_surface` `#0E1420` | `surface_base` `#0F1622` | farklı |
| ayraç | `border` `#1F2B42` | `divider` `#22314A` | farklı |

Sonuç: sohbet balonu ile onu çevreleyen panel bir tık farklı gri; kullanıcı bunu "bulanık, kirli" olarak algılar. Ekran: `scratch/ui/phase9/live_04_zen_full.png` (sohbet kartı ile alt panel arasındaki geçiş).

---

**D-02 (Y) — Belirteçler kullanılmıyor; renk kodun içine gömülü.**
`cyber_theme.py:132`, `:149-169`, `:171-192` — ana stil sayfasının kendisi bile belirteç yerine düz onaltılık yazıyor (`background-color: #1A263C;`, `color: #00F0FF;`, `border: 1px solid #1F2B42;`). Aynı desen 223 yerel `setStyleSheet` çağrısına yayılmış; en yoğunları `zen_mode.py` (25), `skills_widget.py` (24), `memory_inspector_dialog.py` (21), `reports_viewer.py` (20), `chat_mode.py` (20). Örnek: `zen_mode.py:124-136` Desk düğmesinin 9 satırlık kendi QSS'i var.
**Etki:** tek bir rengi değiştirmek 856 yerde arama gerektiriyor; tema/açık kip imkânsız.

---

**D-03 (Y) — Klavye odağı görünmüyor (WCAG 2.4.7 AA ihlali).**
`cyber_theme.py:121-133` `QPushButton` ve `QPushButton:hover` tanımlı; **`:focus` yok**. Kod tabanının tamamında `QPushButton:focus` sayısı **0**, `QPushButton:pressed` sayısı **0**. 109 düğmenin hiçbiri Tab ile gezilirken nerede olduğunu göstermiyor, hiçbiri basılma geri bildirimi vermiyor.

---

**D-04 (Y) — Kenarlık/ayraç kontrastı 1,39:1 (WCAG 1.4.11 AA ihlali).**
Ölçülen oranlar (kendi hesabım, sRGB göreli parlaklık):

| Çift | Oran | Eşik | Sonuç |
|---|---:|---:|---|
| `border #1F2B42` / `bg_root #080B10` | **1,39** | 3,0 | KALDI |
| `divider #22314A` / `surface_base #0F1622` | **1,39** | 3,0 | KALDI |
| `text_muted #484F58` / `bg_root #080B10` | **2,38** | 4,5 | KALDI |
| `text_muted #484F58` / `bg_card #141C2C` | **2,06** | 4,5 | KALDI |
| `accent_purple #9D00FF` / `bg_card #141C2C` | **3,15** | 4,5 | KALDI |

Kenarlıklar görünmeyince paneller birbirinden ayrışmıyor; ekran "tek parça koyu çorba" gibi duruyor. Bu, kullanıcının "karmaşık" hissinin doğrudan görsel nedeni: sınır olmadığı için beyin gruplama yapamıyor.

---

**D-05 (Y) — Vurgu renkleri saf tayf renkleri; "neon" etkisi.**
`accent_cyan #00F0FF`, `accent_emerald #00FF9D`, `accent_amber #FFB300`, `accent_purple #9D00FF` — dördü de **S=%100, L=%50**, kroma 255. Kod tabanında kroma ≥200 olan 11 renk, kroma=255 olan 8 renk var. Modern masaüstü uygulamalarının ortak yönelimi tam tersi: tek, düşük-kroma vurgu + nötr yüzeyler (bkz. [K3], [K4], [K5]). Ayrıca `frontend-design` yeteneği bu kombinasyonu ("near-black background with a single bright acid-green accent") üretilmiş tasarımın bilinen imzası olarak sayıyor [K7].

---

**D-06 (Y) — İkonografi tamamen emoji.**
376 emoji kullanımı, **76 farklı emoji**; `QIcon` yalnızca sistem tepsisi için kullanılmış (`ui/manager.py:80,93,97`). En yoğun dosyalar: `knowledge_graph.py` (50), `chat_mode.py` (47), `reports_viewer.py` (47), `zen_mode.py` (45).
Sonuçlar:
* Emoji renklidir ve tek vurgulu paleti bozar (ekranda 🟢🔴📚🎯🔌🤖🗓🔔📥📎🧠🌐 aynı anda).
* Platforma göre farklı çizilir; `main.py:44-49` yorumu bunu zaten belgeliyor: kullanıcının makinesinde emoji "tofu" (boş kutu) çiziliyordu ve `apply_emoji_font_fallback` yaması gerekti. Yani ikon sistemimiz bir yazı tipi kazasına bağımlı.
* Ölçeklenmez, tek renkli yapılamaz, durum (etkin/pasif) alamaz.

---

**D-07 (Y) — Zen sol sekme çubuğunun yarıdan fazlası görünmüyor.**
`zen_mode.py:343-373` yedi sekme ekliyor: `📚 Raporlar & Notlar`, `🎯 Yetenekler`, `⏰ Görevler`, `🔌 MCP Sunucuları`, `🤖 Ajanlar`, `🗓 Bugun`, `🔔 Bildirimler`.
Ölçüm (`tabs.json`): sekme çubuğunun ihtiyacı **1117 px**; gerçekte 1920×1080'de **679 px**, 1366×768'de **479 px**. Görünen: **3/7** ve **2/7**. Gerisine yalnızca ok düğmeleriyle kaydırarak ulaşılıyor — `live_04_zen_full.png` sol üstteki `‹` ve `›` okları bu.
**Etki:** "Bildirimler"e ulaşmak 1366'da 5 kaydırma tıklaması istiyor; kullanıcı sekmenin varlığını bile göremiyor.

---

**D-08 (Y) — Üst çubukta 18 denetim var.**
`zen_mode.py:114-297` sırasıyla: başlık, Desk, Proje, "Sağlayıcı:" etiketi, sağlayıcı kutusu, "Model:" etiketi, model kutusu, efor kutusu, Token rozeti, Bağlam rozeti, Gelen kutusu rozeti, Sağlayıcı durum rozeti, "+ Yeni", "Floating", "Chat", küçült, büyüt, kapat = **18**.
Chat'te de aynı yığılma var (`chat_mode.py:258-443`, 15 `addWidget` + efor seçici).
Sonuç ölçüldü: Chat penceresi 640 px genişlikte üst çubuk **4 satıra**, 460 px'te **6 satıra** sarıyor ve pencerenin **%22,5'ini** yiyor (`chat_640x860.png`, `chat_420x800.png`, `live_07_chat_topbar.png`). Gerçek pencerede model kutusu da kırpılıyor: `live_06_chat.png`'de "claude-opus-5" yerine "laude-opus-5" görünüyor.

---

**D-09 (Y) — Aynı bilgi 8 yüzeyde tekrarlanıyor.**
Rapor/bildirim sınıfı bilgi için eşzamanlı yüzeyler (`tabs.json → rapor_yuzeyleri`):
1. `left_tabs[Raporlar & Notlar]` → `ReportsViewerWidget`
2. `left_tabs[Bildirimler]` → `NotificationCenter`
3. `left_tabs[Bugun]` → `TimelinePanel`
4. Üst çubuk `InboxBadge` (`zen_mode.py:231`)
5. Merkez `notification_scroll` tepsisi (`zen_mode.py:397-424`)
6. `reports_viewer.inbox_strip` → `ReportInbox`
7. `reports_viewer.report_center` → `ReportCenterWidget` (1380 satır)
8. `StandaloneReportWindow` (ayrı pencere)

Ve bu yüzeyler **tutarsız sayı gösteriyor**: `live_04_zen_full.png` üzerinde sağdaki graf efsanesi "Raporlar 593", Rapor Merkezi "Toplam 648 rapor", "Tümü (648 rapor)", liste "648 / 648 kayıt" diyor. Kullanıcı hangisine güveneceğini bilemiyor.

---

**D-10 (O) — Merkez ve sağ sütunda rozet çifti.**
`zen_mode.py:437-462` merkez sütuna dört rozet koyuyor: `🧠 Bellek: N Düğüm`, `🎯 Yetenekler: N Aktif`, `🔌 MCP: …`, `[model-adı]`. Bunların hepsinin başka bir karşılığı var:

| Bilgi | Yüzey 1 | Yüzey 2 |
|---|---|---|
| Model | üst çubuk `model_combo` | merkez `badge_model` |
| Yetenek sayısı | `left_tabs[Yetenekler]` | merkez `badge_skills` |
| MCP durumu | `left_tabs[MCP Sunucuları]` | merkez `badge_mcp` |
| Bellek düğümü | sağ graf efsanesi | merkez `badge_memory` |
| Sistem durumu | üst çubuk `provider_badge` | merkez `zen_telemetry_status` (`zen_mode.py:385`) |

---

**D-11 (Y) — Merkez sütunun %93'ü boş, sol sütun tıkabasa dolu.**
Çekirdek görselleştirici sabit 160×160 px (`core_visualizer` `base_radius=58`); merkez sütun 1920×1080'de 649×587 px. Doldurma oranı **%6,7**. Aynı anda sol sütun kendi sekme başlıklarını sığdıramıyor (D-07). Ekranda bu, `live_04_zen_full.png` ortasındaki büyük boşluk olarak görünüyor. Sağ alttaki terminal paneli de tamamen boş ve alt yarının **%45'ini** kaplıyor (`terminal_w=851` / `chat_w=1041`).

---

**D-12 (Y) — Chat'te içerik, kroma yeniliyor.**
`chat_mode.py` beş ayrı ikincil şerit tanımlıyor ve hepsi aynı anda görünebiliyor:
`report_bar` (`:452`), `notification_scroll` (`:482`, `setMaximumHeight(100)`), `side_panel_container` (`:540`, sekme kutusu `setMaximumHeight(280)` — `:686`), `attachment_bar` (`:553`), `terminal_drawer` (`:593`, `setFixedHeight(190)`).
Ölçüm (`chrome.json`, 1280×800, hepsi açık): krom **603 px**, sohbet gövdesi **139 px** — pencerenin **%17,4'ü**. Yani asıl iş yüzeyi, yardımcı panellerin altıda biri kadar.
Ayrıca yan panel yatay değil **dikey** ekleniyor (sohbetin altına, 280 px'e sıkıştırılmış 7 sekme): dar pencerede bu, 7 sekmeyi 280 px yüksekliğe hapsediyor.

---

**D-13 (O) — 23 denetim 24 px'lik asgari hedef boyutunun altında (WCAG 2.5.8 AA).**
Sabit yükseklikler: 20 px → 3 adet (`chat_mode.py:474` `setFixedSize(20,20)`, `:561`, `zen_mode.py:538`); 22 px → 20 adet (ör. `reports_viewer.py:409,427,445,463,481,498,516,540` — okuyucu araç çubuğundaki 8 ikon düğmesinin tamamı `30×22` veya `26×22`; ayrıca `report_center.py:825,944`, `rules_panel.py:219,225`, `notification_pill.py:54,75`, `timeline_panel.py:207`, `task_board_widget.py:614`, `notification_center.py:115`, `memory_inspector_dialog.py:393`, `zen_mode.py:493`, `chat_mode.py:468`).
WCAG 2.2 SC 2.5.8 tabanı 24×24 CSS px'tir; platform kılavuzları 44 pt / 48 dp önerir [K1].
Ayrıca bu düğmelerin metni tek bir emoji ya da "A+"; `setAccessibleName` **0** olduğu için ekran okuyucuya anlamlı bir ad gitmiyor (110 `setToolTip` var ama ipucu erişilebilir ad yerine geçmez).

---

**D-14 (O) — Tipografi ölçeği yok; her şey kalın.**
9 farklı boyut (9–22 px), dominant olanlar **11 px (123 kez)** ve **10 px (58 kez)**. 157 kalın bildirimi (bildirimlerin ≈%63'ü). Beş panel başlığının hepsi aynı biçimde: emoji + BÜYÜK HARF + `#00F0FF` + kalın + 13 px:
`reports_viewer.py:162` `📚 ARAŞTIRMA VE BELLEK DOSYALARI`,
`report_center.py:1190` `📥 RAPOR MERKEZİ`,
`knowledge_graph.py:3090` `🌐 BİLİŞSEL HAFIZA`,
`mcp_drawer.py:186` `🔌 MCP ARAÇ VE PROTOKOL MERKEZİ`,
`zen_mode.py:385` `🟢 SİSTEM HAZIR`.
Hepsi aynı ağırlıkta olunca hiçbiri öne çıkmıyor: hiyerarşi yok, sadece gürültü var. (BÜYÜK HARF etiket ve " · " ile birleştirilmiş üst-veri dizeleri — 36 kullanım — `frontend-design` yeteneğinin "şablon kromu" listesindeki maddelerin ta kendisi [K7].)

---

**D-15 (O) — Yazı tipi zincirleri sans ile mono'yu karıştırıyor.**
18 farklı `font-family` bildirimi. İkisi kendi içinde tutarsız:
`cyber_theme.py:106` `font-family: 'Segoe UI', 'Consolas', sans-serif;` — sans yazı tipi, yedeği **monospace**.
`zen_mode.py:432` `font-family: 'Consolas', 'Segoe UI';` — mono, yedeği sans.
Segoe UI bulunmayan bir makinede tüm arayüz monospace'e düşer. `live_06_chat.png`'de zaten karışım görünüyor: gövde sans, giriş yer tutucusu ve terminal mono.

---

**D-16 (O) — Boşluk ızgarası yok.**
58 farklı `padding` (en sık `2px 8px`, `2px 10px`, `1px 6px`), 23 farklı `setContentsMargins` (aralarında `(9,7,9,7)`, `(12,9,10,9)`, `(4,3,4,2)`), 9 farklı `setSpacing` (aralarında 3 ve 5), 8 farklı `border-radius`. Hiçbiri 4/8 ızgarasına oturmuyor. Bu, "modern görünmeme"nin en sessiz ama en yaygın nedeni: her kart başka bir ritimde nefes alıyor.

---

**D-17 (O) — Kapsayıcı derinliği 7, sürüklenebilir bölücü derinliği 4.**
Zen'de içerik şu zincirin ucunda: `QVBoxLayout` → `main_v_splitter` → `top_h_splitter` → `left_tabs (QTabWidget)` → `reports_viewer` → `reports_viewer.splitter` → `right_container` → `content_browser`. Görevler sekmesi ayrıca kendi içinde bir dikey `QSplitter` barındırıyor (`zen_mode.py:326`), Ajanlar sekmesi de (`zen_mode.py:356`).
Kullanıcı bir raporu okumak için **üç ayrı bölücüyü** doğru oranda ayarlamak zorunda; bunlardan hiçbiri kaydedilmiyor.

---

**D-18 (D) — 4K %200 + 1080p karışık kurulumda temel doğru, ölçek yanlış.**
Olumlu: `main.py:36-38` `HighDpiScaleFactorRoundingPolicy.PassThrough` kuruyor ve `window_sizing.py` tamamen `availableGeometry()` üzerinden çalışıyor — pencere görev çubuğunun altına kaçmıyor, ekran değiştirince kırpılıyor (`clamp_window_into_screen`). Bu doğru.
Sorun: 10–11 px'lik mantıksal metin ve 20–22 px'lik denetimler %100 ölçekli 1080p ekranda fiziksel olarak çok küçük kalıyor; %200'de ise sabit `setFixedWidth(30)` gibi değerler orantısız büyüyor. Kullanıcı ayarlı bir yoğunluk (density) kademesi yok — arayüz her ekranda aynı sıkışıklıkta.

---

**D-19 (D) — Açık kip / tema seçeneği yok.**
`themes/` altında tek dosya var, `light` ya da `setTheme` benzeri hiçbir kanca yok. QSS koyu değerlere gömülü olduğu için açık kip bugün 856 renk yazımını elle değiştirmek demek.

---

**D-20 (D) — Klavye erişimi yok denecek kadar az.**
Tüm uygulamada 2 global kısayol: `command_palette.py:404` Ctrl+K, `focus_mode.py:106` Ctrl+Shift+F. Yeni sohbet, kip değiştirme, terminal aç/kapa, sekme geçişi, raporu aç — hepsi yalnızca fare ile.
Olumlu not: **komut paleti zaten var** (`command_palette.py`, 5 kaynağı — komut/yetenek/ajan/ofis/rapor — bulanık aramayla topluyor). Yeniden tasarımın en güçlü dayanağı bu: yapı zaten mevcut, sadece birincil gezinme hâline getirilmesi gerekiyor.

---

**D-21 (D, kapsam dışı — not) — Agent Desk penceresi bu sorunların çoğunu taşımıyor.**
`src/entropy/desk/` (6697 satır): **17** farklı hex, **35** `setStyleSheet`, **9** `setFixed*`, **4** yazı boyutu, 8 sekme, 17 düğme — ve dosyaların çoğu `READING_TOKENS`'ı içe aktarıyor (`changes_panel.py:31`, `memory_panel.py:33`, `offices_panel.py:21`, `projects_panel.py:27`). Desk, ana uygulamadan **belirgin biçimde daha disiplinli**. Yeni tasarım sistemi Desk'e uygulanırken göç maliyeti düşük olacak; Desk'i son faza bırakmak doğru.

---

## 2. Bilgi mimarisi sadeleştirme önerisi

### 2.1 Yönlendirici ilke

> Ekrandaki her öğe, kullanıcıyı hedefine yaklaştırdığı için orada olmalı; yaklaştırmıyorsa kaldırılmalı [K3].
> İkincil ve nadir kullanılan her şey ikinci bir yüzeye ertelenir (progressive disclosure) [K6].

Bugünkü Zen bunun tersini yapıyor: **hepsi her zaman görünür**. Sonuç 153 denetim ve %17 içerik oranı.

### 2.2 Kiplerin rolleri (netleştirilmiş)

| Kip | Tek cümlelik iş | Ne gösterir | Ne göstermez |
|---|---|---|---|
| **Floating** | "Entropy orada ve müsait mi?" | Yalnızca çekirdek + durum halkası. Tıklayınca palet. | Hiçbir panel, rozet, metin. |
| **Chat** | "Konuşuyorum." | Tek sütun sohbet + giriş. Üst çubukta **en fazla 4 öğe**. | Sekme kutusu, terminal, rozet yığını. Bunlar palet/çekmece ile gelir. |
| **Zen** | "Çalışıyorum ve sistemi izliyorum." | **Üç bölge**: sol bağlam, orta iş, sağ hafıza. Her bölgede **tek** panel görünür. | Aynı anda 7 sekme, 4 rozet, 8 rapor yüzeyi. |

"Tek ekrana sığma" kuralı bu düzende kendiliğinden sağlanır, çünkü bölge sayısı sabit (3) ve her bölgenin asgari genişliği belirteçle tanımlıdır.

### 2.3 Zen'in yeni iskeleti

```
┌───────────────────────────────────────────────────────────────────────────┐
│  ◈ Entropy     EntropiAI ▾        claude · opus · high ▾      ⌘K    ─ □ ✕ │  ← 4 öğe + pencere
├──────────────┬────────────────────────────────────────┬───────────────────┤
│              │                                        │                   │
│  BAĞLAM      │           İŞ ALANI                     │   HAFIZA          │
│  (tek panel) │  ┌──────────────────────────────────┐  │   (graf)          │
│              │  │                                  │  │                   │
│  ▸ Raporlar  │  │   Sohbet (birincil)              │  │   [graf tuvali]   │
│    Yetenekler│  │                                  │  │                   │
│    Görevler  │  │                                  │  │                   │
│    Ajanlar   │  └──────────────────────────────────┘  │   ─────────────   │
│    MCP       │  ┌──────────────────────────────────┐  │   1.362 düğüm     │
│              │  │  Terminal (katlanır, varsayılan  │  │                   │
│              │  │  kapalı)                    ▲    │  │                   │
│  ───────────  │  └──────────────────────────────────┘  │                   │
│  ⌘K ile ara  │  [ mesaj yaz… ]              ⏎ Gönder  │                   │
└──────────────┴────────────────────────────────────────┴───────────────────┘
```

Değişiklikler ve gerekçeleri:

| # | Değişiklik | Ne çözer | Kanıt |
|---|---|---|---|
| **IA-1** | Sol sekme çubuğu → **dikey liste** (ikon + ad, seçili olan vurgulu). Sekme yerine bölüm. | 7 sekmeden 3'ü görünüyordu; dikey listede 7'si de görünür, kaydırma yok. | D-07 |
| **IA-2** | Üst çubuk 18 → **4 öğe**: marka, proje, birleşik model çipi (`sağlayıcı · model · efor`, tıklayınca açılır), `⌘K`. Kalanlar palete ve pencere menüsüne taşınır. | 4/6 satıra sarma, kırpılan model kutusu, %22,5 krom. | D-08 |
| **IA-3** | Merkezdeki 4 telemetri rozeti **kaldırılır**; bilgileri zaten sol listede ve sağ grafta. Sistem durumu tek bir noktaya (marka yanındaki durum noktası) iner. | 5 çift yineleme. | D-10 |
| **IA-4** | Rapor/bildirim yüzeyleri 8 → **2**: (a) sol listedeki "Raporlar" bölümü (liste + okuyucu), (b) üst çubuktaki tek gelen-kutusu noktası (tıklayınca sol listeyi Raporlar'a getirir). `NotificationCenter`, `TimelinePanel`, merkez tepsi, `inbox_strip` ve `report_bar` tek bir zaman akışında birleşir. | Tutarsız sayılar (593 / 648), 8 yüzey. | D-09 |
| **IA-5** | Çekirdek görselleştirici **merkezden çıkar**, üst çubuktaki marka noktasına iner (8–10 px, canlı durum). Merkez tamamen sohbete ayrılır. | Merkezin %93'ü boştu. | D-11 |
| **IA-6** | Terminal **katlanır çekmece** (varsayılan kapalı, `Ctrl+\``), alt yarıyı sürekli işgal etmez. | Boş terminal alt yarının %45'i. | D-11, D-12 |
| **IA-7** | Chat'te ikincil şeritler **aynı anda en fazla bir tane**; yan panel dikey değil **sağa** açılır (geniş pencerede) veya paletten çağrılır (dar pencerede). | %17,4 içerik oranı. | D-12 |
| **IA-8** | İç içe `QSplitter` 4 → **1** (yalnızca üç ana bölge arası). Panel içi bölme kaldırılır; okuyucu ya listenin yerine geçer ya da ayrı pencerede açılır. Bölücü konumları `QSettings`'e yazılır. | Kapsayıcı derinliği 7. | D-17 |
| **IA-9** | **Komut paleti birincil gezinme** olur: `⌘K` üst çubukta görünür bir düğme, boş sohbet ekranında ipucu, ve tüm eylemler (yeni sohbet, kip değiştir, terminal, rapor aç, yetenek çalıştır) palete kayıtlanır. | 2 kısayol, gizli palet. | D-20 |

### 2.4 Tıklama sayısı — önce/sonra

| Görev | Bugün | Sonra |
|---|---:|---:|
| "Bildirimler"i açmak (1366 px) | 5 kaydırma oku + 1 sekme = **6** | sol listede görünür: **1** |
| Son raporu okumak | sekmeyi bul (0–5) + kart/liste seç (1) + "Raporu Oku" (1) = **2–7** | `⌘K` + yaz + ⏎ = **1 tıklama + yazı** |
| Modeli değiştirmek | kutuyu bul (üst çubukta 18 öğe arasında) + aç + seç = **2** + arama | çip (1) + seç (1) = **2**, tek yerde |
| Terminali görmek | Zen'de zaten açık ama boş; Chat'te düğme = **1** | `Ctrl+\`` = **0 tıklama** |
| Ajanın durumunu görmek | sekmeyi kaydır (2–4) + sekme (1) = **3–5** | sol liste (**1**) |

---

## 3. Tasarım sistemi önerisi

Yapı: **belirteçler → bileşenler → şablonlar**. Belirteçler tek bir Python sözlüğünde (ileride W3C DTCG JSON biçimine [K2] taşınabilir), QSS bu sözlükten **üretilir**, bileşenler yalnızca `objectName`/`property` ile sınıflandırılır. Hiçbir widget kendi rengini yazmaz.

### 3.1 Renk belirteçleri (8 çekirdek + 3 anlamsal)

Tümü ölçüldü ve doğrulandı (hesap: sRGB göreli parlaklık, WCAG 2.x formülü).

| Belirteç | Değer | Rol | Doğrulama |
|---|---|---|---|
| `color.bg` | `#0B0F14` | uygulama zemini | — |
| `color.surface` | `#121924` | panel/kart | — |
| `color.surface.raised` | `#1A2431` | üstü, hover, seçili | `surface` ile 1,13 (ayırt edilir) |
| `color.line` | `#232E3D` | dekoratif ayraç | (metin dışı, kritik değil) |
| `color.line.strong` | `#5A6676` | **denetim sınırı, giriş kenarlığı** | `surface` 3,02 · `bg` 3,29 → 1.4.11 ✓ |
| `color.text` | `#E7EEF7` | gövde | `bg` 16,45 · `surface` 15,10 ✓ |
| `color.text.muted` | `#9AAABE` | ikincil etiket | `surface` 7,45 ✓ (mevcut `#484F58` 2,06 idi) |
| `color.accent` | `#4CC2FF` | **tek vurgu**: seçili, bağlantı, odak halkası | `surface` 8,79 · odak 3:1 ✓ · kroma 179 (mevcut 255) |
| `color.accent.ink` | `#08131B` | dolu vurgu üstündeki metin | `accent` üzerinde 9,35 ✓ |
| `color.ok` | `#57D9A3` | başarı (yalnızca durum) | `surface` 9,96 ✓ · kroma 130 |
| `color.warn` | `#E8B84B` | uyarı | `surface` 9,57 ✓ · kroma 157 |
| `color.danger` | `#F0787A` | hata/yıkıcı | `surface` 6,45 ✓ · kroma 120 |

**Kurallar:**
* Vurgu rengi ekranın en fazla **%10'unda** kullanılır (60-30-10 kuralı, [K5]).
* `ok/warn/danger` **yalnızca durum** anlatır; dekorasyon için kullanılmaz. Bugün `#00FF9D` süs olarak da kullanılıyor (`chat_pdf_btn`, `Raporu Oku`).
* Mor (`#9D00FF`, `#C084FC`, `#BC8CFF`, `#C792EA`) tamamen kaldırılır — dört ayrı mor var ve hiçbiri anlam taşımıyor.
* 99 renkten 12'ye inilir. Graf tuvalinin (`knowledge_graph.py`, 51 renk) kategori paleti ayrı bir `viz.*` ailesi olarak tanımlanır ve bu 12'ye karışmaz.

### 3.2 Tipografi (4 kademe + 1 mono)

| Belirteç | Boyut / satır | Ağırlık | Kullanım |
|---|---|---|---|
| `type.title` | 18 / 24 px | 600 | Pencere ve birincil panel başlığı (ekranda **en fazla 1 tane**) |
| `type.heading` | 14 / 20 px | 600 | Bölüm/kart başlığı |
| `type.body` | 13 / 20 px | 400 | Gövde, liste, düğme metni |
| `type.label` | 11 / 16 px | 500 | Rozet, üst-veri, yardımcı metin |
| `type.mono` | 12,5 / 18 px | 400 | Terminal, kod, model kimliği |

* Ailesi **iki**: `font.sans = "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif` ve `font.mono = "Cascadia Mono", "Consolas", monospace`. Sans yedeğinde mono, mono yedeğinde sans **olmaz** (D-15).
* `bold` kullanımı 157 → **kademelerin kendi ağırlığı** ile sınırlanır; gövde metninde vurgulama dışında kalın yok.
* BÜYÜK HARF panel başlıkları normal cümle düzenine döner: `Raporlar`, `Bilişsel hafıza`, `MCP sunucuları`.
* 9 px ve 10 px kademe kaldırılır (okunmuyor).

### 3.3 Boşluk — 4 px temelli ızgara

`space.1=4  space.2=8  space.3=12  space.4=16  space.5=24  space.6=32`

* Bileşen içi dolgu: `space.1`/`space.2`. Bileşenler arası: `space.2`/`space.3`. Bölge kenarı: `space.4`.
* Yalnızca bu altı değer; 58 padding kombinasyonu → **6 dolgu kalıbı** (`pad.xs/sm/md` × yatay/dikey).

### 3.4 Köşe, gölge, yoğunluk

| Belirteç | Değer | Kullanım |
|---|---|---|
| `radius.sm` | 6 px | düğme, giriş, rozet |
| `radius.md` | 10 px | kart, panel |
| `radius.lg` | 14 px | diyalog, palet |
| `elevation.0` | yok | zemin |
| `elevation.1` | `1px solid line` | panel (Qt'de gölge pahalı; sınır tercih edilir) |
| `elevation.2` | `QGraphicsDropShadowEffect` blur 24, y 6, `#000` @%45 | yalnızca palet ve diyalog (ekranda en fazla 1) |
| `control.height` | **28 px** (yoğun), **32 px** (rahat) | tüm düğme/giriş/kutu |
| `control.height.icon` | **28 × 28 px** | ikon düğmesi — 24 px tabanının üstünde [K1] |
| `density` | `compact` / `comfortable` | kullanıcı ayarı; `control.height` ve `space` çarpanı (D-18) |

8 köşe yarıçapı → 3; 6 sabit denetim yüksekliği → 2 (ayarlanabilir).

### 3.5 Durum belirteçleri (bugün eksik olan)

| Durum | Kural |
|---|---|
| `hover` | zemin `surface.raised` |
| `pressed` | zemin `surface.raised` + `%4` koyulaştırma |
| **`focus`** | **2 px `accent` halka, 2 px dış boşluk** — her odaklanabilir denetimde zorunlu (D-03) |
| `disabled` | opaklık %45, imleç varsayılan ok imlecine döner |
| `selected` | sol 2 px `accent` şerit + zemin `surface.raised` |

### 3.6 İkon seti

* **Emoji yok.** `QtAwesome` (MIT) üzerinden **tek bir aile**: Phosphor (MIT) veya Microsoft Codicons (CC BY 4.0) — Codicons masaüstü/geliştirici araç diline en yakın olanı.
* Boyut iki kademe: **16 px** (satır içi) ve **20 px** (araç çubuğu). Renk her zaman `text.muted`, etkin durumda `accent`.
* 76 emoji → **≈24 ikon** ile karşılanır. Eşleme örneği: 📚→`book`, 🎯→`target`, ⏰→`clock`, 🔌→`plug`, 🤖→`robot`, 🗓→`calendar`, 🔔→`bell`, 📥→`inbox`, 🧠→`brain`(Phosphor)/`circuit-board`(Codicons), 🌐→`globe`, 📎→`paperclip`, 🗑→`trash`.
* Her ikon düğmesine `setAccessibleName()` **zorunlu** (D-13).

### 3.7 Bileşen listesi (yeniden yazılacak/standartlaşacak)

Bugün 109 düğme + 124 etiket, çoğu kendi stiline sahip. Hedef: **14 bileşen**, tümü belirteçten stillenir, hiçbiri yerel `setStyleSheet` çağırmaz.

| Bileşen | `objectName` / property | Bugünkü dağınık karşılıkları |
|---|---|---|
| `Button` (variant: `primary`/`ghost`/`danger`) | `qproperty` `variant` | 59 ayrı QSS bloğu |
| `IconButton` | `iconButton` | `reports_viewer.py:409-558` (8 adet), `skills_widget.py:546-588` |
| `Chip` (rozet) | `chip`, `tone=accent/ok/warn/danger` | `tokens_badge`, `context_badge`, `badge_*`, `provider_badge`, `InboxBadge` |
| `Input` / `SearchInput` | `input` | 19 `QLineEdit` |
| `Select` | `select` | 22 `QComboBox` |
| `Panel` (başlık + gövde) | `panel` | 5 farklı BÜYÜK HARF başlık kalıbı |
| `NavList` (sol dikey gezinme) | `navList` | `left_tabs` (QTabWidget) |
| `ListRow` | `listRow` | `report_inbox`, `tasks`, `skills`, `agents` — 4 farklı satır çizimi |
| `Card` | `card` | `DigestCardWidget`, `InboxItemWidget`, kanban kartı |
| `Reader` (markdown yüzeyi) | `reader` | `content_browser`, `chat_browser`, `StandaloneReportWindow` — 3 ayrı stil |
| `Terminal` | `terminal` | `TerminalPaneWidget` |
| `CommandPalette` | `palette` | mevcut, yalnızca belirtece bağlanır |
| `Toast` / `StatusDot` | `toast`, `statusDot` | `report_bar`, `notification_pill`, `zen_telemetry_status`, tepsi |
| `Splitter` | `splitter` | 7 `QSplitter`, tutamağı görünmez |

### 3.8 Örnek: belirteçten üretilen QSS

`src/entropy/ui/themes/tokens.py` (öneri — bu denetimde **yazılmadı**):

```python
TOKENS = {
    "color": {
        "bg": "#0B0F14", "surface": "#121924", "surface.raised": "#1A2431",
        "line": "#232E3D", "line.strong": "#5A6676",
        "text": "#E7EEF7", "text.muted": "#9AAABE",
        "accent": "#4CC2FF", "accent.ink": "#08131B",
        "ok": "#57D9A3", "warn": "#E8B84B", "danger": "#F0787A",
    },
    "space": {"1": 4, "2": 8, "3": 12, "4": 16, "5": 24, "6": 32},
    "radius": {"sm": 6, "md": 10, "lg": 14},
    "type": {
        "title":   {"size": 18, "line": 24, "weight": 600},
        "heading": {"size": 14, "line": 20, "weight": 600},
        "body":    {"size": 13, "line": 20, "weight": 400},
        "label":   {"size": 11, "line": 16, "weight": 500},
        "mono":    {"size": 13, "line": 18, "weight": 400},
    },
    "control": {"height": 28, "height_icon": 28, "focus_ring": 2},
    "font": {
        "sans": '"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif',
        "mono": '"Cascadia Mono",Consolas,monospace',
    },
}
```

`src/entropy/ui/themes/qss.py` (öneri):

```python
def build_qss(t=TOKENS, density="compact") -> str:
    c, s, r, ty, ct = t["color"], t["space"], t["radius"], t["type"], t["control"]
    h = ct["height"] + (4 if density == "comfortable" else 0)
    return f"""
/* ---- temel ---- */
QWidget {{
    background: {c['bg']};
    color: {c['text']};
    font-family: {t['font']['sans']};
    font-size: {ty['body']['size']}px;
}}

/* ---- yüzeyler ---- */
QFrame#panel, QFrame#card {{
    background: {c['surface']};
    border: 1px solid {c['line']};
    border-radius: {r['md']}px;
}}
QLabel#panelTitle {{
    color: {c['text']};
    font-size: {ty['heading']['size']}px;
    font-weight: {ty['heading']['weight']};
    padding: {s['2']}px {s['3']}px;
}}
QLabel#label, QLabel[muted="true"] {{
    color: {c['text.muted']};
    font-size: {ty['label']['size']}px;
    font-weight: {ty['label']['weight']};
}}

/* ---- düğme: tek kaynak, dört durum ---- */
QPushButton {{
    min-height: {h}px; max-height: {h}px;
    padding: 0 {s['3']}px;
    background: transparent;
    color: {c['text']};
    border: 1px solid {c['line.strong']};
    border-radius: {r['sm']}px;
    font-weight: {ty['body']['weight']};
}}
QPushButton:hover    {{ background: {c['surface.raised']}; }}
QPushButton:pressed  {{ background: {c['surface.raised']}; padding-top: 1px; }}
QPushButton:focus    {{ border-color: {c['accent']};
                        outline: {ct['focus_ring']}px solid {c['accent']};
                        outline-offset: {ct['focus_ring']}px; }}
QPushButton:disabled {{ color: {c['text.muted']}; border-color: {c['line']}; }}

QPushButton[variant="primary"] {{
    background: {c['accent']}; color: {c['accent.ink']};
    border-color: {c['accent']}; font-weight: 600;
}}
QPushButton[variant="ghost"]  {{ border-color: transparent; color: {c['text.muted']}; }}
QPushButton[variant="danger"] {{ color: {c['danger']}; border-color: {c['danger']}; }}
QPushButton#iconButton {{
    min-width: {ct['height_icon']}px; max-width: {ct['height_icon']}px;
    min-height: {ct['height_icon']}px; max-height: {ct['height_icon']}px;
    padding: 0; border-color: transparent;
}}

/* ---- giriş ---- */
QLineEdit, QComboBox, QPlainTextEdit {{
    min-height: {h}px;
    background: {c['bg']};
    border: 1px solid {c['line.strong']};
    border-radius: {r['sm']}px;
    padding: 0 {s['2']}px;
    selection-background-color: {c['accent']};
    selection-color: {c['accent.ink']};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border-color: {c['accent']};
    outline: {ct['focus_ring']}px solid {c['accent']};
}}

/* ---- sol gezinme (sekme değil, liste) ---- */
QListWidget#navList {{ background: transparent; border: none; }}
QListWidget#navList::item {{
    height: {h + 6}px; padding-left: {s['3']}px;
    border-radius: {r['sm']}px; color: {c['text.muted']};
}}
QListWidget#navList::item:hover    {{ background: {c['surface.raised']}; }}
QListWidget#navList::item:selected {{
    background: {c['surface.raised']}; color: {c['text']};
    border-left: 2px solid {c['accent']};
}}

/* ---- rozet ---- */
QLabel#chip {{
    background: {c['surface.raised']}; color: {c['text.muted']};
    border: 1px solid {c['line']}; border-radius: {r['sm']}px;
    padding: 2px {s['2']}px;
    font-size: {ty['label']['size']}px; font-family: {t['font']['mono']};
}}
QLabel#chip[tone="ok"]     {{ color: {c['ok']}; }}
QLabel#chip[tone="warn"]   {{ color: {c['warn']}; }}
QLabel#chip[tone="danger"] {{ color: {c['danger']}; }}

/* ---- bölücü: görünür ama sessiz ---- */
QSplitter::handle {{ background: {c['line']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}
QSplitter::handle:hover      {{ background: {c['accent']}; }}
"""
```

Not: Qt QSS `outline-offset`'i sınırlı destekler; odak halkası bir üst sarmalayıcıda `border` ile ya da `QProxyStyle` içinde `drawPrimitive(PE_FrameFocusRect)` ile çizilmelidir. Uygulama sırasında `ui-engineer` bu iki seçenekten birini seçip testle sabitler.

---

## 4. Kütüphane kararı

### 4.1 Adaylar

| Aday | Lisans | PySide6 | PyInstaller | Bize uygunluk |
|---|---|---|---|---|
| **qfluentwidgets** (`PySide6-Fluent-Widgets` 1.11.3, Ağu 2026) | **GPLv3 (ticari olmayan) / ücretli ticari lisans** [K8] | ✓ | belge yok; kaynak (.qrc) yönetimi gerekiyor | **RED.** Lisans tek başına kesici: Entropy AI bir ürün; GPLv3 tüm kaynağı bulaştırır, ticari lisans para ve bağımlılık demek. Ayrıca kendi Fluent kimliğini dayatır, Entropy'nin kimliğini siler. |
| **qt-material** | BSD-2-Clause [K9] | ✓ | `.qss` + `.rcc` dışa aktarımı var | **RED.** Lisans uygun ama Material Design'ı dayatıyor; `QMenu` arka uca göre farklı çiziliyor (belgelenmiş sınırlama). Bizde zaten 51 renkli bir graf tuvali var, üstüne Material paleti girerse iki kimlik çarpışır. |
| **PyQtDarkTheme** (orijinal) | MIT | ✓ | — | **RED.** Bakımı durmuş; topluluk çatalı `PyQtDarkTheme-fork` (MIT, 2.3.4) sürüyor [K10]. Yeni bağımlılık için sağlıksız temel. |
| **QDarkStyleSheet** | MIT | ✓ | `.qss` + kaynak | **KISMEN.** Yalnızca hazır bir koyu tema; belirteç sistemi, bileşen kütüphanesi ve odak kuralları yok. Bizim sorunumuz "koyu tema yok" değil, "sistem yok". |
| **QtAwesome** | MIT (fontlar SIL OFL / Apache-2.0 / MIT / CC BY 4.0) [K11] | ✓ (QtPy üzerinden) | **bilinen sorun:** paketlenmiş uygulamada font dosyaları boş çıkabiliyor (spyder-ide/qtawesome #78) | **KABUL — yalnızca ikon için.** Emoji sorununu (D-06) tek başına çözer. PyInstaller riski `.spec` içinde `datas` girdisi + paketten sonra bir duman testiyle kapatılır. |
| **Kendi belirteç sistemimiz** (`tokens.py` + `build_qss()`) | — | ✓ | risk yok (saf Python) | **KABUL — ana yol.** |

### 4.2 Karar

> **Kendi belirteç sistemimizi kurarız; ikonu `QtAwesome`'dan alırız; başka arayüz kütüphanesi eklemeyiz.**

Gerekçeler:

1. **Lisans.** Ürünleşecek bir uygulamada GPLv3 (qfluentwidgets) kabul edilemez; ücretli lisans da gereksiz bir maliyet ve dış bağımlılık.
2. **Kimlik.** Entropy'nin sorunu "hazır bir tema yokluğu" değil, **kendi kurallarının olmayışı**. Material/Fluent kurmak 99 rengi 99 başka renge çevirir; disiplini getirmez. Belirteç sistemi disiplini kodun içine yazar.
3. **Maliyet.** `tokens.py` + `qss.py` toplam ~300 satır. Buna karşılık qfluentwidgets'a geçmek 109 düğme, 22 kutu, 19 giriş ve 7 bölücünün tamamının sınıfını değiştirmek demek — Faz 11 bütçesini tek başına yer.
4. **Test edilebilirlik.** Belirteç sözlüğü saf Python; kontrast oranları, ızgara uyumu ve "yerel `setStyleSheet` sayısı" doğrudan pytest ile ölçülebilir (§5.3). Dış kütüphaneyle bu ölçüm imkânsız.
5. **PyInstaller.** Saf Python sözlük + string QSS paketlemede sıfır risk. Tek dış bağımlılık QtAwesome; onun font dosyaları `EntropyAI.spec` içinde `datas`'a eklenip `dist_check` duman testinde bir ikonun gerçekten çizildiği doğrulanır.
6. **Gelecek uyum.** `TOKENS` sözlüğü, W3C Design Tokens 2025.10 [K2] JSON biçimine birebir eşlenebilir; ileride tasarım aracıyla senkron gerekirse dönüştürücü yazmak yeterli.

**Kabul edilen risk:** Fluent/Material'ın hazır bileşenlerini (TeachingTip, Flyout, Navigation) yeniden yazmamız gerekecek. Karşılığında 14 bileşen yeter (§3.7) ve bunların 12'si bugün zaten var, sadece stilleri dağınık.

---

## 5. "ui-design" yeteneği (skill) taslağı

### 5.1 Neden kendi yeteneğimizi yazıyoruz

Mevcut `frontend-design` yeteneği [K7] **web** için ve **estetik yön** veriyor: tipografi kişiliği, "şablon kromu" tuzakları, iki geçişli süreç (plan → briefe karşı gözden geçir → kod → öz eleştiri). Değerli ama Qt/PySide6'ya, belirteçlerimize ve tek-ekran kuralımıza dair hiçbir şey bilmiyor. Vercel'in `web-design-guidelines` yeteneği [K12] ise kuralları dışarıdan çekip `dosya:satır` biçiminde bulgu üreten bir **meta-yetenek**; bu desen bizim için doğru ama kural kaynağı bizim olmalı.

Bu yüzden: **`ui-design`** — Entropy'nin `ui-engineer` ajanına verilecek, ilkeler + kontrol listesi + **çalıştırılabilir ölçüm betiği** içeren bir yetenek. Ölçüm betiği kritik: bugünkü raporun tüm sayıları böyle üretildi, ajan da aynı sayıları üretip kendi işini kanıtlayabilmeli ("kanıtla kapat" kuralı).

### 5.2 `SKILL.md` içeriği (taslak)

```markdown
---
name: ui-design
description: Entropy AI'ın PySide6 arayüzünü tasarlarken ve değiştirirken uygulanacak
  tasarım sistemi, kontrol listesi ve ölçüm yordamı. Yeni bir panel/pencere/bileşen
  eklerken, mevcut bir ekranı sadeleştirirken veya "arayüz modern görünmüyor" türü
  bir istek geldiğinde kullanılır.
---

# ui-design — Entropy arayüz tasarımı

## 0. Değişmezler (ihlal edilirse iş reddedilir)

1. **Tek kaynak.** Renk, boyut, boşluk, köşe yalnızca `entropy.ui.themes.tokens.TOKENS`
   içinden gelir. Widget dosyasında düz onaltılık renk veya piksel yazmak yasak.
2. **Yerel stil yasağı.** Yeni `setStyleSheet` çağrısı eklenmez. Stil `objectName`
   veya `qproperty` ile sınıflandırılır, kural `qss.py` içine yazılır.
3. **Tek ekran.** Hiçbir kip 1366×768 kullanılabilir alanda kaydırma ya da taşma
   üretmez. Yeni bir panel eklemek, mevcut bir paneli kaldırmayı gerektirir.
4. **Tek vurgu.** Ekranda `color.accent` dışında vurgu rengi yoktur. `ok/warn/danger`
   yalnızca durum bildirir, dekorasyon değildir.
5. **Emoji ikon yasağı.** İkon `QtAwesome` ailesinden gelir; her ikon düğmesinde
   `setAccessibleName()` bulunur.
6. **Odak görünür.** Odaklanabilir her denetimde 2 px `accent` halka vardır.
7. **Hedef boyutu.** Tıklanabilir hiçbir şey 24×24 px'in altında değildir (WCAG 2.5.8).

## 1. Süreç (her arayüz işi bu sırayla)

**a. Ölç.** Değişiklikten ÖNCE `python scratch/ui/ui_audit.py --mode zen --size 1366x768`
   çalıştır, sayıları not et (denetim sayısı, krom oranı, taşma, kontrast ihlali).
**b. Planla.** Bir paragraf: bu değişiklik hangi kullanıcı işini kaç tıklamada
   yapılabilir kılıyor? Hangi öğe **kaldırılıyor**? (Chanel kuralı: eklemeden önce bir
   şey çıkar.)
**c. Brief'e karşı gözden geçir.** Planın herhangi bir parçası "her uygulamada olur"
   tipindeyse — BÜYÜK HARF etiket, ' · ' ile birleştirilmiş üst-veri, her başlığın
   üstünde bir eyebrow, her karta aynı gölge, saf tayf rengi vurgu — o parçayı değiştir
   ve neyi neden değiştirdiğini yaz.
**d. Uygula.** Yalnızca belirteç ve bileşen sınıfı kullanarak.
**e. Kanıtla.** Ölçüm betiğini yeniden çalıştır + offscreen ekran görüntüsü al
   (1366×768 ve 1920×1080). Rapora önce/sonra sayı tablosu ve iki görüntü ekle.
   Yeşil ölçüm olmadan iş "bitti" sayılmaz.

## 2. Yerleşim kuralları

- Bölge sayısı sabittir (Zen: sol bağlam / orta iş / sağ hafıza). Yeni bölge açılmaz.
- Her bölgede **aynı anda tek panel** görünür. Diğerleri sol gezinme listesinden gelir.
- İç içe `QSplitter` derinliği **1**'i geçmez. Bölücü konumları `QSettings`'e yazılır.
- İkincil şeritler (bildirim, ek, terminal, yan panel) **aynı anda en fazla bir tane**
  görünür; içerik alanı pencere yüksekliğinin **%55'inin** altına inemez.
- Aynı bilgi ekranda **bir kez** gösterilir. İkinci bir yüzey eklemeden önce birincisini
  kaldır.

## 3. Tipografi ve dil

- Dört kademe: title 18 / heading 14 / body 13 / label 11. Mono yalnızca terminal,
  kod ve model kimliği için.
- `bold` yalnızca title ve heading kademesindedir. Gövde metninde kalın yok.
- Panel başlıkları cümle düzeninde: "Raporlar", "Bilişsel hafıza". BÜYÜK HARF yok.
- Düğme metni ne olacağını söyler: "Raporu aç", "Gönder", "Kalıcı yap" — "Tamam" değil.
- Aynı eylem akış boyunca aynı adı taşır ("Yayınla" düğmesi "Yayınlandı" bildirimi verir).
- Boş durum bir davettir, hata bir yön tarifidir: ne oldu + ne yapılmalı. Özür dilemez.

## 4. Erişilebilirlik kontrol listesi (her PR)

- [ ] Metin kontrastı ≥ 4,5:1 (18 px+ kalın için ≥ 3:1)
- [ ] Denetim sınırı ve odak halkası kontrastı ≥ 3:1 (WCAG 1.4.11)
- [ ] Tıklama hedefi ≥ 24×24 px (WCAG 2.5.8)
- [ ] Her odaklanabilir denetimde görünür odak (WCAG 2.4.7)
- [ ] İkon düğmelerinde `setAccessibleName()`
- [ ] Tab sırası ekrandaki okuma sırasıyla aynı
- [ ] Yeni her eylemin komut paletinde bir kaydı var
- [ ] 1366×768'de taşma yok; 4K %200'de denetimler orantılı

## 5. Yasaklı desenler (üretilmiş arayüz imzaları)

Bunlar yasak değil ama **varsayılan oldukları için** kullanılamaz; kullanılacaksa
gerekçesi yazılır:
- Yakın-siyah zemin + tek parlak asit rengi vurgu
- Her başlığın üstünde harf aralığı açılmış BÜYÜK HARF eyebrow
- ' · ' ile birleştirilmiş üst-veri dizeleri
- Her kartın altında aynı yumuşak gri gölge, her şeye aynı köşe yarıçapı
- Küçük veri etiketleri için monospace
- Düğme/bağlantı metnine eklenmiş '→'
- İçeriğin gerçekten sıralı olmadığı yerde 01 / 02 / 03 numaralandırma

## 6. Ölçüm betiği

`scratch/ui/ui_audit.py` — offscreen Qt ile çalışır, model çağrısı yapmaz:

    python scratch/ui/ui_audit.py --mode zen --size 1366x768 --json out.json --shot out.png

Ürettiği alanlar: `interactive_count`, `header_rows`, `header_pct`, `visible_tabs` /
`hidden_tabs`, `overflow_px`, `chrome_px`, `content_pct`, `splitter_depth`,
`local_stylesheets`, `hardcoded_hex`, `fixed_sizes`, `emoji_icons`,
`contrast_failures[]`, `small_targets[]`, `focusless_controls[]`.

Kapı (gate) değerleri — aşılırsa iş reddedilir:
| Alan | Eşik |
|---|---|
| `hidden_tabs` | 0 |
| `header_rows` (1280 px) | ≤ 1 |
| `content_pct` | ≥ 55 |
| `interactive_count` (Zen) | ≤ 60 |
| `local_stylesheets` (değişen dosyalarda) | 0 yeni |
| `hardcoded_hex` (değişen dosyalarda) | 0 yeni |
| `contrast_failures` | 0 |
| `small_targets` | 0 |
| `focusless_controls` | 0 |
```

### 5.3 Yeteneğin yanına konacak testler

`tests/test_ui_design_system.py` (öneri, Faz 11'de `qa-build-engineer` yazar):

| Test | Ne doğrular |
|---|---|
| `test_no_hardcoded_hex_in_widgets` | `src/entropy/ui/**` içinde `themes/` dışında `#RRGGBB` yok |
| `test_no_local_stylesheets` | `setStyleSheet` yalnızca `themes/` ve uygulama kökünde |
| `test_token_contrast` | Her `text*`/`accent*` çifti için oran hesaplanır, eşikler tutar |
| `test_target_sizes` | `setFixed*` ile verilen hiçbir denetim < 24 px |
| `test_focus_rules_exist` | Üretilen QSS'te odaklanabilir her seçici için `:focus` kuralı var |
| `test_no_emoji_icons` | Widget kaynaklarında emoji aralığı boş |
| `test_zen_fits_1366` | Offscreen Zen'de `hidden_tabs == []`, taşma yok |
| `test_chat_content_ratio` | Tüm şeritler açıkken içerik ≥ %55 |

Bu testler yeteneğin "kanıtla kapat" kuralını mekanikleştirir: ajan iddia edemez, ölçüm gösterir.

---

## 6. Fazlı yeniden tasarım planı

Her adım: **kapsam → kabul ölçütü → ekran görüntüsü ölçütü → ajan → risk**.
Toplam tahmini: 6 adım. Adımlar sıralıdır; her adım kendi başına derlenebilir ve geri alınabilir olmalıdır.

---

### Adım 1 — Belirteç temeli (temel tokenlar)

**Kapsam:** `themes/tokens.py` (yeni), `themes/qss.py` (yeni), `themes/cyber_theme.py` → geriye dönük uyumluluk katmanı (`CYBER_THEME` ve `READING_TOKENS` yeni belirteçlerden türetilir, eski anahtar adları korunur). Hiçbir widget dosyasına dokunulmaz.
**Kabul ölçütü:**
* Uygulama açılır, hiçbir panel kırılmaz; tam test paketi yeşil.
* `test_token_contrast` yeşil: 12 belirteç çiftinin tümü eşikleri geçer.
* `CYBER_THEME` ve `READING_TOKENS` artık aynı vurgu/metin/yüzey değerlerini döndürür (D-01 kapanır).
**Ekran görüntüsü ölçütü:** `scratch/ui/phase11/step1_{zen,chat}_{1366x768,1920x1080}.png` — Faz 11-D'deki karşılıklarıyla yan yana; yerleşim aynı, renkler yeni.
**Ajan:** `ui-engineer` (uygulama), `qa-build-engineer` (test + build).
**Risk:** Orta. Eski anahtar adlarını kullanan 223 çağrı yeri var; uyumluluk katmanı eksik bir anahtar bırakırsa `KeyError` ile panel çöker. **Azaltma:** `cyber_theme` sözlüklerinin anahtar kümesi teste bağlanır (`test_theme_keys_stable`).

---

### Adım 2 — Kabuk ve üst çubuk

**Kapsam:** `zen_mode.py` üst çubuk (18 → 4 öğe), `chat_mode.py` üst çubuk, `flow_layout.py`, pencere denetimleri; birleşik model çipi (sağlayıcı · model · efor tek açılır yüzeyde); `⌘K` görünür düğme; komut paletine yeni eylemlerin kaydı; `Ctrl+\``, `Ctrl+N`, `Ctrl+1/2/3` kısayolları.
**Kabul ölçütü:**
* Zen üst çubuğu 1366 px'te **1 satır**; Chat üst çubuğu 1280 px'te **1 satır**, 640 px'te **≤2 satır**.
* Chat'te üst çubuk pencere yüksekliğinin **≤%8'i** (bugün %22,5).
* Model kutusu hiçbir genişlikte kırpılmıyor (`live_06_chat.png`'deki "laude-opus-5" hatası kapanır).
* Komut paletinde ≥ 12 eylem kayıtlı; her yeni kısayolun bir palet karşılığı var.
**Ekran görüntüsü ölçütü:** `step2_chat_{460,640,1280}.png` + `step2_zen_header.png`; ölçüm JSON'unda `header_rows` ve `header_pct` önce/sonra.
**Ajan:** `ui-engineer`; palet kayıtları için `agy-integration-engineer` (slash/komut kayıt defterine dokunuluyorsa).
**Risk:** Yüksek. Üst çubuk testlerin dokunduğu nesneleri barındırıyor (`tokens_badge`, `provider_badge`, `model_combo`, `btn_zen`). **Azaltma:** taşınan her denetim için eski öznitelik adı takma ad olarak korunur; `qa-build-engineer` önce mevcut arayüz testlerini çalıştırıp kırılanları listeler.

---

### Adım 3 — Sol bölge: sekmeden gezinme listesine

**Kapsam:** `zen_mode.py:326-375` `QTabWidget` → `NavList` (dikey liste + `QStackedWidget`); `chat_mode.py:678-726` yan panelin dikeyden sağa taşınması; sekme başlıklarındaki emoji → QtAwesome ikonu; panel başlıklarının BÜYÜK HARF'ten cümle düzenine dönmesi (5 dosya).
**Kabul ölçütü:**
* 1366×768'de **7/7 bölüm görünür**, `hidden_tabs == []`, `overflow_px == 0`.
* Bölüm değiştirmek **1 tıklama** (bugün 1–6).
* Chat'te yan panel açıkken sohbet gövdesi ≥ %55.
**Ekran görüntüsü ölçütü:** `step3_zen_nav_1366.png` (yedi bölümün hepsi görünür), `step3_chat_sidepanel.png`.
**Ajan:** `ui-engineer`.
**Risk:** Orta-yüksek. `left_tabs` birçok testte ve `focus_mode`/`command_palette` bağlantılarında adıyla geçiyor. **Azaltma:** `NavList`'e `addTab/count/tabText/setCurrentIndex` uyumlu bir kabuk (shim) yazılır, testler değişmeden geçer.

---

### Adım 4 — Yineleme temizliği ve merkez bölge

**Kapsam:** Merkez telemetri rozetleri kaldırılır (`zen_mode.py:437-462`); `zen_telemetry_status` tek durum noktasına iner; merkez tamamen sohbete verilir; çekirdek görselleştirici üst çubuğa küçülür; terminal katlanır çekmece olur; 8 rapor yüzeyi 2'ye iner (`NotificationCenter` + `TimelinePanel` + merkez tepsi + `inbox_strip` + `report_bar` → tek zaman akışı); rapor sayaçları tek kaynaktan okunur.
**Kabul ölçütü:**
* Zen'de görünür denetim **153 → ≤60**.
* Rapor/bildirim yüzeyi **8 → 2**; ekrandaki tüm rapor sayaçları **aynı sayıyı** gösterir (593/648 tutarsızlığı kapanır — bu bir veri hatası olduğu için ayrıca doğrulanır).
* Merkez sütunda sohbet alanı ≥ %70; terminal kapalıyken alt bölge 0 px.
**Ekran görüntüsü ölçütü:** `step4_zen_1920.png` ve `step4_zen_1366.png`; `live_04_zen_full.png` ile yan yana konur.
**Ajan:** `ui-engineer` (yerleşim), `memory-rag-engineer` (rapor sayacının tek kaynağı — 593 vs 648 farkının kökü rapor indeksinde).
**Risk:** Yüksek. Kaldırılan rozetler ve paneller testlerde ve olay veri yolu (`bus`) abonelerinde geçiyor; bildirim akışının birleştirilmesi davranış değişikliğidir. **Azaltma:** Kaldırma değil, **birleştirme**: her kaldırılan yüzeyin sinyali yeni tek yüzeye yönlendirilir; `bus` abonelikleri korunur.

---

### Adım 5 — Bileşen standardizasyonu ve erişilebilirlik

**Kapsam:** 14 bileşenin `objectName`/`qproperty` ile sınıflandırılması; 223 yerel `setStyleSheet`'in silinmesi; 87 `setFixed*`'in belirteçli iki yüksekliğe indirilmesi; QtAwesome ikon geçişi (376 emoji → ~24 ikon); `setAccessibleName` eklenmesi; odak halkası (`QProxyStyle` veya sarmalayıcı sınır); yoğunluk (compact/comfortable) ayarı.
**Kabul ölçütü:**
* `local_stylesheets ≤ 5`, `hardcoded_hex == 0` (themes dışı), `fixed_sizes ≤ 10`.
* `contrast_failures == 0`, `small_targets == 0`, `focusless_controls == 0`.
* `emoji_icons == 0`; paketlenmiş `dist_check` sürümünde ikonlar çiziliyor (QtAwesome font riski kapanır).
* Klavye ile tüm arayüz gezilebiliyor; her durakta odak görünür.
**Ekran görüntüsü ölçütü:** `step5_focus_walk.png` (Tab ile 10 durak, odak halkası görünür), `step5_icons.png` (ikon çubuğu, emoji yok), `step5_density_{compact,comfortable}.png`.
**Ajan:** `ui-engineer`; `qa-build-engineer` (PyInstaller `datas` girdisi + `dist_check` duman testi).
**Risk:** Yüksek (hacim). 30 widget dosyasına dokunuluyor. **Azaltma:** Dosya bazlı ilerlenir, her dosyadan sonra hedefli test; `git` üzerinde her widget ailesi ayrı commit.

---

### Adım 6 — Agent Desk hizalaması

**Kapsam:** `src/entropy/desk/**` yeni belirteçlere geçer (17 hex → 0, 35 `setStyleSheet` → 0, 8 sekme → gezinme listesi), aynı bileşen kütüphanesini kullanır. Piksel ofis görselleri kendi görsel dilini korur (ayrı `viz.*` ailesi).
**Kabul ölçütü:**
* Desk ve Zen yan yana açıldığında aynı ürün gibi görünür (aynı yüzey, kenarlık, tipografi, ikon).
* Desk penceresi 1366×768'in yarısında taşmadan çalışır (mevcut `half_screen_geometry` kuralı korunur).
* Desk testleri yeşil; ofis/board/orkestratör davranışı değişmemiş.
**Ekran görüntüsü ölçütü:** `step6_desk_zen_side_by_side.png`.
**Ajan:** `ui-engineer`.
**Risk:** Düşük. Desk zaten `READING_TOKENS` kullanıyor (D-21); göç maliyeti diğer adımların çok altında.

---

### 6.1 Sıralama gerekçesi

Adım 1 olmadan diğerleri anlamsız (belirteç yoksa standart yok). Adım 2 ve 3 en görünür kazancı verir ve kullanıcının şikâyetinin merkezindedir ("karmaşık"). Adım 4 en riskli davranış değişikliğini içerir, bu yüzden kabuk oturduktan sonra gelir. Adım 5 hacimlidir ama mekaniktir; testler onu güvenli kılar. Adım 6 en sona bırakılır çünkü Desk zaten sağlıklıdır ve son hizalama en ucuzudur.

### 6.2 Ölçülecek özet göstergeler (önce → hedef)

| Gösterge | Bugün | Hedef |
|---|---:|---:|
| Farklı hex renk | 99 | ≤ 14 |
| Yerel `setStyleSheet` | 223 | ≤ 5 |
| `setFixed*` | 87 | ≤ 10 |
| Farklı yazı boyutu | 9 | 5 |
| Farklı padding kombinasyonu | 58 | ≤ 8 |
| Emoji ikon | 376 | 0 |
| Zen görünür denetim | 153 | ≤ 60 |
| Zen görünen sekme (1366) | 2 / 7 | 7 / 7 |
| Chat içerik oranı (1280, hepsi açık) | %17,4 | ≥ %55 |
| Chat üst çubuk oranı (460 px) | %22,5 | ≤ %10 |
| WCAG kontrast ihlali | 5 çift | 0 |
| 24 px altı hedef | 23 | 0 |
| Odak halkası olmayan düğme | 109 | 0 |
| Klavye kısayolu | 2 | ≥ 12 |

---

## 7. Kaynaklar

**Erişilebilirlik standartları**
* [K1] WCAG 2.2 SC 2.5.8 Target Size (Minimum, AA) — tıklanabilir hedef ≥ 24×24 CSS px; platform kılavuzları (44 pt / 48 dp) daha büyüğünü önerir. https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html · özet: https://www.digitala11y.com/understanding-sc-2-5-8-target-size-minimum/
* WCAG 2.2 SC 1.4.11 Non-text Contrast (AA) — arayüz bileşeni ve durumu ≥ 3:1. https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
* WCAG 2.2 SC 2.4.7 Focus Visible (AA) — klavye odağı görünür olmalı. https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html

**Tasarım sistemi ve belirteçler**
* [K2] W3C Design Tokens Community Group, *Design Tokens Format Module 2025.10* — ilk kararlı sürüm (28 Ekim 2025); tema/çoklu-marka, Oklch/Display P3, takma ad ve miras. https://www.designtokens.org/tr/2025.10/format/ · duyuru: https://www.w3.org/community/design-tokens/2025/10/28/design-tokens-specification-reaches-first-stable-version/

**2025–2026 masaüstü/AI arayüz desenleri**
* [K3] *UX/UI design trends for 2026: calm interfaces, transparent AI and the end of visual theatrics* — sakin arayüz, bilişsel yükü düşürme, "her öğe yerini hak etmeli". https://elements.envato.com/learn/ux-ui-design-trends
* [K4] *7 SaaS UI Design Trends for 2026, Shown With Real Screens* — komut paleti öncelikli gezinme, aşamalı açığa çıkarma. https://www.saasui.design/blog/7-saas-ui-design-trends-2026
* [K5] *UI Color Palette 2026: Best Practices* (IxDF) ve *How to Choose a Color Palette for UI Design* (UXPin) — 1–2 marka rengi + 1 vurgu + 8–10 kademeli nötr + 4 anlamsal renk; 60-30-10 dağılımı. https://ixdf.org/literature/article/ui-color-palette · https://www.uxpin.com/studio/blog/choose-color-pallete/
* [K6] Progressive disclosure (Nielsen, 1995) — ikincil seçenekleri ikinci yüzeye ertele. NN/g: https://www.nngroup.com/videos/progressive-disclosure/ · derleme: https://www.uxpin.com/studio/blog/what-is-progressive-disclosure/

**Ajan yetenekleri (skill) — referans yaklaşımlar**
* [K7] `frontend-design` yeteneği (yerel kopya): `C:\Users\batu_\.claude\plugins\marketplaces\claude-plugins-official\plugins\frontend-design\skills\frontend-design\SKILL.md` — iki geçişli süreç, "üretilmiş tasarım imzaları" listesi, "aynadan bir aksesuar çıkar" kısıtı, ekran görüntüsüyle öz eleştiri.
* [K12] Vercel `web-interface-guidelines` / `web-design-guidelines` yeteneği — 17 kategoride 100 kural, `dosya:satır` biçiminde bulgu, kural kaynağını dışarıdan çeken meta-yetenek deseni. https://vercel.com/design/guidelines · https://github.com/vercel-labs/web-interface-guidelines · yetenek: https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md
* Tasarım yeteneği derlemeleri (SKILL.md/DESIGN.md örnekleri): https://github.com/bergside/awesome-design-skills · https://github.com/plugin87/ux-ui-agent-skills

**Qt / PySide6 kütüphaneleri ve lisanslar**
* [K8] PySide6-Fluent-Widgets (`qfluentwidgets`) 1.11.3 (1 Ağustos 2026) — **ticari olmayan kullanım GPLv3, ticari kullanım için ücretli lisans zorunlu**. https://pypi.org/project/PySide6-Fluent-Widgets/ · https://github.com/zhiyiYo/PyQt-Fluent-Widgets
* [K9] qt-material — **BSD-2-Clause** (Copyright 2020, GCPDS); PySide6/PyQt6, yoğunluk ölçeği, `.qss`+`.rcc` dışa aktarımı; belgelenmiş sınırlama: `QMenu` arka uca göre farklı çiziliyor. https://github.com/UN-GCPDS/qt-material · https://qt-material.readthedocs.io/
* [K10] PyQtDarkTheme — orijinal depo bakımsız; sürdürülen çatal `PyQtDarkTheme-fork` 2.3.4, **MIT**. https://github.com/5yutan5/PyQtDarkTheme · https://github.com/bauripalash/PyQtDarkTheme-fork · https://pypi.org/project/PyQtDarkTheme-fork/
* [K11] QtAwesome — **MIT** (Spyder ekibi); paketli fontlar: Font Awesome ve Elusive (SIL OFL), Phosphor (MIT), Material Design Icons ve Remix (Apache-2.0), Microsoft Codicons (CC BY 4.0). Bilinen paketleme sorunu: PyInstaller ile font dosyaları boş çıkabiliyor. https://github.com/spyder-ide/qtawesome · sorun: https://github.com/spyder-ide/qtawesome/issues/78
* QDarkStyleSheet — MIT. https://github.com/ColinDuquesnoy/QDarkStyleSheet
* Qt for Python — widget stillendirme (QSS'i dosyadan yükleme, yerel `setStyleSheet` yerine): https://doc.qt.io/qtforpython-6/tutorials/basictutorial/widgetstyling.html
* PySide6 lisansı (LGPLv3 / GPL / ticari): https://pypi.org/project/PySide6/ · karşılaştırma: https://www.pythonguis.com/faq/licensing-differences-between-pyqt6-and-pyside6/

**Depo içi kanıt**
* Ekran görüntüleri (gerçek pencere): `scratch/ui/phase9/live_04_zen_full.png`, `live_06_chat.png`, `live_07_chat_topbar.png`, `scratch/ui/phase8/live_zen.png`
* Ekran görüntüleri (offscreen, bu denetim): `scratch/ui/phase11/zen_1920x1080.png`, `zen_1366x768.png`, `zen_header.png`, `zen_left_tabs.png`, `zen_reports_tab.png`, `chat_1280x800.png`, `chat_640x860.png`, `chat_420x800.png`, `chat_header.png`, `chat_all_open_1280x800.png`, `floating.png`
* Ölçüm çıktıları: `scratch/ui/phase11/measure.json`, `chrome.json`, `tabs.json`
* Ölçüm betikleri: `scratch/ui/phase11/audit_measure.py`, `audit_chrome.py`, `audit_tabs.py`

---

## Ek A — Denetlenen dosyalar ve boyutları

| Dosya | Satır | Not |
|---|---:|---|
| `src/entropy/ui/themes/cyber_theme.py` | 193 | iki çelişen palet (D-01) |
| `src/entropy/ui/modes/zen_mode.py` | 1432 | 18 öğeli üst çubuk, 7 sekme, 4 splitter |
| `src/entropy/ui/modes/chat_mode.py` | 1474 | 5 ikincil şerit, dikey yan panel |
| `src/entropy/ui/modes/floating_mode.py` | 124 | sağlıklı — tek widget, 5 hex |
| `src/entropy/ui/window_sizing.py` | 171 | **sağlıklı** — DPI/ekran mantığı doğru |
| `src/entropy/ui/widgets/ui_polish.py` | 324 | doğru yönde bir başlangıç (kırpma, mono/gövde px sabitleri) ama belirteç değil |
| `src/entropy/ui/widgets/knowledge_graph.py` | 4146 | 51 hex, 50 emoji — ayrı `viz.*` ailesi gerekiyor |
| `src/entropy/ui/widgets/reports_viewer.py` | 1231 | 8 adet 26×22 ikon düğmesi, 14 `setFixed*` |
| `src/entropy/ui/widgets/report_center.py` | 1380 | üçüncü rapor yüzeyi |
| `src/entropy/ui/widgets/command_palette.py` | 409 | **mevcut ve iyi** — birincil gezinme yapılmalı |
| `src/entropy/ui/widgets/*` (kalan 20 dosya) | ~8500 | ortalama 11 `setStyleSheet` / dosya |
| `src/entropy/desk/**` | 6697 | **kapsam dışı, sağlıklı** (D-21) |

## Ek B — Ölçümlerin yeniden üretilmesi

```powershell
# tümü offscreen; uygulama penceresi açılmaz, model çağrılmaz
python scratch\ui\phase11\audit_measure.py    # measure.json + 8 ekran görüntüsü
python scratch\ui\phase11\audit_chrome.py     # chrome.json + 2 ekran görüntüsü
python scratch\ui\phase11\audit_tabs.py       # tabs.json
```

Statik sayımlar (Git Bash):

```bash
grep -rhoE '#[0-9a-fA-F]{6}' src/entropy/ui/ --include='*.py' | tr 'a-f' 'A-F' | sort -u | wc -l   # 99
grep -rho 'setStyleSheet' src/entropy/ui/ --include='*.py' | wc -l                                  # 223
grep -rhoE 'setFixed(Width|Height|Size)' src/entropy/ui/ --include='*.py' | wc -l                   # 87
grep -rhoE 'font-size:\s*[0-9]+px' src/entropy/ui/ --include='*.py' | grep -oE '[0-9]+' | sort -u   # 9 kademe
grep -rho 'QPushButton:focus' src/entropy/ui/ --include='*.py' | wc -l                              # 0
```
