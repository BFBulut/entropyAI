# Faz 8 Araştırma Notu — Entropy AI (v0.5.1, dal `ai/v0.1.7`)

Tarih: 2026-09-09 (akşam) · Kapsam: salt okunur inceleme, offscreen ölçüm, CLI yardım çıktıları, web araştırması. Model API çağrısı yapılmadı.

**Kanıt tabanı.** Satır numaraları aksi belirtilmedikçe **HEAD `e177d08`** (`git archive HEAD` ile çıkarılan kopya üzerinde ölçüldü). Not yazılırken çalışma ağacında Faz 8 düzenlemeleri **eşzamanlı olarak başlamıştı** (`git status`: 12 dosya `M`, yeni `flow_layout.py`, `frameless.py`, `tests/test_phase8_*.py`; mtime 19:04–19:10). Bu değişiklikler §3.7'de ayrıca değerlendirildi; §1–§3'teki bulgular kullanıcının bugün gördüğü sürümü (HEAD / `dist/EntropyAI/EntropyAI.exe`, 18:35 derlemesi) açıklar.

Ölçüm betikleri: `scratchpad/measure_header_head.py`, `measure_reports.py`, `disconnect_probe.py` (Qt offscreen, `QT_QPA_PLATFORM=offscreen`; gerçek kasa salt okundu).

---

## 1) Kullanıcı bulguları ve kök nedenler

### 1.1 Zen "tam ekrandan çıkmış" (1766×949), başlık çubuğu yok, taşınamıyor, "hiçbir şey olmuyor"

**Kanıt**

| Kaynak | Bulgu |
|---|---|
| `zen_mode.py:72` | `setWindowFlags(Qt.FramelessWindowHint \| Qt.Window)` — çerçevesiz; sistem başlık çubuğu, taşıma, yeniden boyutlandırma yok. |
| `zen_mode.py:1`, `:56` | Docstring hâlâ "Borderless **fullscreen** workstation": çerçevesizlik tam ekran varsayımıyla tasarlanmış. |
| `zen_mode.py:51-52`, `:80-81`; `manager.py:141-154` | Faz 6'da tam ekran → `fit_window_to_screen(ratio=0.92)`; **her** Zen geçişinde (`keep_preferred` yok) yeniden %92'ye ortalanır. `bring_to_front` de `switch_mode("zen")` çağırır (`manager.py:198-199`) → kullanıcının olası geometri değişikliği her seferinde ezilir. |
| Offscreen ölçüm | `ZenModeWindow.__dict__` içinde `mousePressEvent/mouseMoveEvent/mouseDoubleClickEvent` **yok** (`mouse handlers in ZenModeWindow: []`). Karşılaştırma: `floating_mode.py:36-43` sürükleme tutamağına sahip. |
| `zen_mode.py:250-253` | Üst çubukta yalnızca `✕` (close). Küçült / büyüt / tam ekran düğmesi yok. |
| Gerçek ekran (Qt, PassThrough) | `LG ULTRAGEAR` birincil, `availableGeometry=1920×1032` (mantıksal), `dpr=2.0` → `int(1920*0.92)=1766`, `int(1032*0.92)=949`. Kullanıcının bildirdiği **1766×949 tam olarak %92 kuralının sonucu**; hata değil, Faz 6 tasarımı. |

**Kök neden.** Faz 6 pencereyi tam ekrandan "%92, ortalanmış" pencereye çevirdi ama tam ekran için seçilmiş `FramelessWindowHint` bayrağını ve "taşıma gerekmez" varsayımını korudu. Sonuç: başlık çubuğu olmayan, tutamağı olmayan, her geçişte aynı yere geri dönen bir pencere. Üst çubuğa tıklamak "hiçbir şey" yapmaz çünkü olay işleyicisi yok.

**Çözüm (ui-engineer, boyut M)**
1. Üst çubukta `mousePressEvent` → `self.windowHandle().startSystemMove()`; kenar/köşelerde `startSystemResize(edges)` (Qt ≥ 5.15, Windows destekli — bkz. §2.1). Yerel snap/animasyon bedava gelir; manuel `move()` döngüsüne gerek yok.
2. Çift tıkla büyüt/geri al + `─ ❐ ✕` düğmeleri; **veya** daha basit seçenek: `FramelessWindowHint`'i kaldırıp yerel başlık çubuğuna dönmek (DPI-doğru çerçeve, Win+Ok, snap, Alt+Space bedava; tek kayıp "cyber" görünüm).
3. Açılışta kullanılabilir alanın tamamı (`availableGeometry`, görev çubuğu erişilebilir kalır); tekrar geçişte `keep_preferred=True` ile kullanıcı geometrisi korunur; ekran adına göre geometri kalıcılığı (`settings.json` zaten `desk_geometry.screen` deseniyle bunu Desk için yapıyor).
4. Regresyon testi: pencere bayrakları + geometri korunumu + çift kapanış (bkz. §3.4).

### 1.2 Çekirdekten geçilen Chat modu "~2100 px" istiyor, Zen düğmesi görünmüyor

**Kanıt (offscreen, HEAD)**

- Pencere asgarisi küçük: `CHAT_MIN_SIZE=(460,520)`, `CHAT_PREFERRED_SIZE=(620,820)` (`chat_mode.py:211-213`); `ChatModeWindow.minimumSizeHint() = 437×218`. Yani **pencerenin kendisi 2100 px istemiyor**; isteyen üst çubuk.
- Üst çubuk tek satır `QHBoxLayout` → yatay `QScrollArea` içinde (`chat_mode.py:422-435`, `ScrollBarAsNeeded`). Ölçüm: `header.sizeHint() = 2392 px` (proje adı "head" iken; gerçek proje adı "EntropiAI" ve model adı ile **2447 px**), görünür alan 600 px, `hscroll_max = 1792`.
- Bileşen dökümü (minimumSizeHint, px): başlık etiketi **221**, "🏢 Entropy Agent Desk" **238**, proje 84+, sağlayıcı combo 102, **model combo 300** (en uzun model adı), efor 96, **yetenek combo 274**, tokens 88, bağlam 110, durum 98, "+ Yeni" 108, "📚 Raporlar" 128, "🧩 Panel" 95, rozet 13, **ProviderStatusBadge 210**, "Zen Mode" **134** → toplam 2299 + aralıklar.
- **"Zen Mode" düğmesi x = 2247 px'te**; 620 px'lik pencerede ve hatta 1766 px'lik Zen genişliğinde bile görünür alanın dışında. Kaydırma çubuğu 40 px'lik şeridin altında, fark edilmiyor.
- Yan panel açılınca ek örtük minimumlar: `ReportCenterWidget.minimumSizeHint().width() = 630` (Chat "📥 Gelen" sekmesi) — Faz 7'de Zen sol panel için yapılan 1420→389 düzeltmesinin Chat tarafındaki eşi.

**Kök neden.** Faz 6 kaydırma alanı taşmayı gizledi ama içeriği küçültmedi; 16 bileşen tek satırda ~2.4k mantıksal px istiyor. Kullanıcı "2100 px"i pencereyi üst çubuk sığana kadar genişleterek görüyor.

**Çözüm (ui-engineer, boyut M)**
- Akan (wrap eden) üst çubuk: dar pencerede 2–3 satıra kırılır; **"Zen"/mod düğmeleri kaydırma bölgesinin dışında, her zaman görünür** sağ köşede.
- Kısaltmalar: başlık "💬 Entropy AI" (tam ad ipucunda), "🏢 Desk", model/yetenek combo'larına `setMaximumWidth` + elided metin (en uzun model adı 300 px'i belirliyor), `ProviderStatusBadge` kompakt mod.
- Az kullanılanlar (Floating/Chat/Zen geçişleri, Raporlar, Panel) tek "⋯" menüsüne.
- Test: `header.sizeHint().width() <= 900` ve Zen düğmesi `visibleRegion()` boş değil (600 px pencerede).

### 1.3 "Toplam raporlar görünmüyor" (Zen › 📚 Raporlar & Notlar / Rapor Merkezi)

**Gerçek kasa ölçümü** (`C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault`, salt okuma, HEAD kodu):

| Katman | Sonuç |
|---|---|
| `Entropy/**/*.md` | 994 dosya; 74'ü `_archive/AgentDesk/.obsidian/.trash` ile atlanıyor (`vault_manager.py:78`) |
| `vault.iter_report_files()` / `list_reports()` | **891** künye: `report=885`, `query=6`, `office_report=0`, `session=0` |
| Dizin dağılımı | `Entropy\Reports` 455 · `Projects\EntropiAI\Reports` 133 · **`Projects\test_bridge_background_task_fa0\Reports` 86** · `Skills\financial-auditor\Reports` 69 · **`test_bridge_background_task_le0` 60** · **`test_project_directory_binding0` 49** · … |
| `ReportsViewerWidget.refresh_reports()` | `_entries=894`, sayaç etiketi **"894 / 894 kayıt"**, liste 912 satır (grup başlıkları dahil), 18 filtre grubu |
| `ReportCenterWidget` (Zen; `reports_viewer.py:226-230` ile beslenir) | Başlık: **"895 rapor · 9 öne çıkan · 135 sessiz küme · 894 okunmadı"** (894 kasa + 1 posta kutusu) |
| `collect_recent_entries()` (Chat "Gelen") | **60** künye (`report_inbox.py:200,215`: `limit=60`) → Chat'te toplam "60 rapor" görünür, Zen'de 895 |
| Güven eşiği | `report_center.json` yok → varsayılan 0.75; rutin raporların güveni 0.9–1.0 → **135 küme sessize katlanır**, yalnızca 9 kart açık; sessiz bölüm açılışta kapalı (`_quiet_expanded=False`) |

**Kök neden (üç katman, hepsi kanıtlı)**
1. **Sayaç var ama okunamıyor:** `header_label` tek satır zengin metin, `setMinimumWidth(120)` + `SizePolicy.Ignored` (`report_center.py:885-893`) → Zen sol sütunu 460 px açılıp 220 px'e kadar daralabildiğinden (`zen_mode.py:423-426`) "895 rapor · 9 öne çıkan · …" metni **sağdan kırpılır** (QLabel elide yapmaz). Rapor Merkezi minimumu hâlâ 630 px.
2. **Toplam ≠ görünen:** 895'in 135 kümesi sessiz bölümde katlı; öne çıkan 9 kartın da çoğu gürültü (ör. "Gorev Otonom Ajan Mimarisi Arastirma…" n=206, sohbet istemi olarak kaydedilmiş "Tamamdır, şimdi senden yeni bir yetenek…"). Kullanıcı "tüm raporlar" listesini görmek için sessiz bölümü açmayı ve alttaki liste/okuyucu bölmesini fark etmeyi bekliyor.
3. **Yüzeyler tutarsız:** Chat "Gelen" 60 ile sınırlı (`limit=60`); Zen 895. `office_report=0`: ofis raporları `Entropy/Desk` altında `.md` olarak yok (0 dosya), `AgentDesk` ise tarama dışı → ofis çıktıları "toplam"a hiç girmiyor.
4. **Kasa kirliliği:** 195 rapor test koşumlarından (`test_bridge_background_task_*`, `test_project_directory_binding0`) — testler gerçek kasaya yazmış; toplamı şişiriyor ve kümeleme kalitesini bozuyor.

**Çözüm**
- ui-engineer (S): başlık iki satır / elide; "🗂 Tümü (895)" düğmesi sessiz bölümü açıp listeye odaklansın; sayaç ayrı, daralmayan kısa etiket ("895").
- memory-rag-engineer (S): Chat "Gelen" için `limit` kaldırılsın ya da "60 / 895" gösterilsin; Zen ve Chat aynı künye kaynağını paylaşsın; ofis raporlarının kasadaki gerçek yolu (`Desk/Offices/<ofis>/reports`?) `iter_report_files` kuralına eklensin.
- qa-build-engineer (S): test kasası izolasyonu (`obsidian_vault_path` fixture ile `tmp_path`'e yönlendirme) + `Projects/test_*` klasörlerinin `_archive`'e taşınması (kullanıcı onayıyla).

### 1.4 Windows DPI / çoklu monitör (PassThrough) — 1766×949 ve kalabalık üst çubuk

**Gerçek ekran verisi** (`QGuiApplication.screens()`, PassThrough):

| Ekran | Geometri (mantıksal) | Kullanılabilir | DPR | Not |
|---|---|---|---|---|
| `LG ULTRAGEAR` (birincil) | 1920×1080 @ (0,0) | 1920×1032 | **2.0** | Fiziksel 3840×2160, %200 ölçek |
| `LED  MONITOR` | 1920×1080 @ (−1920,0) | 1920×1032 | 1.0 | Desk burada açılıyor (`settings.json: desk_geometry.screen`) |
| `C32JG5x` | 1920×1080 @ (3840,0) | 1920×1032 | 1.0 | |

- `main.py:29-32` PassThrough doğru: 2.0 tam sayı, yuvarlama sorunu yok. Qt 6 Windows'ta varsayılan Per-Monitor V2 (§2.2); pencere DPR 2.0 → 1.0 ekrana geçince mantıksal boyut aynı kalır, fiziksel yarıya iner — davranış beklenen.
- Kalabalık üst çubuk **DPI sorunu değil**: 2.4k mantıksal px içerik, 1766 mantıksal px pencere (LG'de 3532×1898 fiziksel). Karışık DPI'nin tek gerçek izi Desk'te: `entropy.log:274-275` (14:04) "Unable to set geometry 3860x2020 … minimum size **1930×647** … mintrack 3886" → Agent Desk'in örtük minimumu 1930–1949 **mantıksal** px, LG'nin 1920 mantıksal genişliğini aşıyor (Faz 7'deki 1420→389 sınıfından bir örtük-minimum hatası, bu kez Desk penceresinde).

**Öneri (ui-engineer, S):** (1) Zen açılışta `availableGeometry`'nin tamamı, geometri ekran adıyla kalıcı; (2) mod geçişlerinde pencereyi hedef ekranın alanına kırpan ortak `clamp` yardımcısı; (3) Desk için `minimumSizeHint ≤ 1200` testi; (4) `%125/150` kurulumlar için PassThrough kalır (Qt: tam sayı tercih, %25 adımlar kabul edilebilir — §2.2); (5) başlık çubuğu bileşenlerinde `font-size` px yerine pt (DPR 2.0'da 11px metin fiziksel 22px, kabul; ama 1.0 ekranda küçük).

---

## 2) Web araştırması (kaynaklı)

### 2.1 PySide6 çerçevesiz pencere: taşıma / yeniden boyutlandırma / büyütme
- `QWindow::startSystemMove()` / `startSystemResize(Qt::Edges)`: Qt 5.15'te eklendi; pencere yöneticisine yerel taşıma/boyutlandırma devredilir; **Windows, X11, Wayland, macOS (move) destekli**; `bool` döner (desteklenmiyorsa yedek yol). QWidget'ta `self.windowHandle()` üzerinden çağrılır. Kaynak: [QWindow — Qt 6.11](https://doc.qt.io/qt-6/qwindow.html), [Custom client-side window decorations in Qt 5.15](https://www.qt.io/blog/custom-window-decorations), [Qt Forum: resizable frameless window](https://forum.qt.io/topic/146396/how-to-create-a-resizable-frameless-window).
- Desen: özel başlık çubuğunda `mousePressEvent` → `startSystemMove()`; kenar bölgesi vuruş testi → `startSystemResize(edges)`; çift tık → `showMaximized()/showNormal()`. Bayrak değişikliğinden sonra `show()` gerekir ([Window Flags örneği](https://doc.qt.io/qt-6/qtwidgets-widgets-windowflags-example.html)).
- Hazır kütüphane seçeneği (isteğe bağlı): [pyqt-frameless-window](https://pypi.org/project/pyqt-frameless-window/), [FramelessHelper](https://github.com/bmzp/framelesshelper-1). Yeni bağımlılık yerine 40 satırlık `startSystemMove` yeterli.

### 2.2 Windows DPI ve çoklu monitör (Qt 6)
- Qt 6 Windows'ta varsayılan **Per-Monitor DPI Aware V2**; `devicePixelRatio()` ekranlar arasında geçişte güncellenir. `QT_SCALE_FACTOR_ROUNDING_POLICY`: `Round` / `PassThrough` (Qt 6 varsayılanı PassThrough). Tam sayı ölçekler tercih; %25 adımları kabul edilebilir. `QT_ENABLE_HIGHDPI_SCALING=0` yalnız test amaçlı. Kaynak: [High DPI — Qt 6.11](https://doc.qt.io/qt-6/highdpi.html), [Qt for Python High DPI](https://doc.qt.io/qtforpython-6.5/overviews/highdpi.html), [Qt Forum: Qt6 and QT_ENABLE_HIGHDPI_SCALING](https://forum.qt.io/topic/162609/qt6-and-qt_enable_highdpi_scaling).

### 2.3 Claude Code CLI — adım/bütçe sınırları (yerelde doğrulandı: `claude --version` = 2.1.265)
- `claude --help` çıktısında **`--max-budget-usd <amount>`** var ("only works with --print"); **`--max-turns` listelenmiyor**. `claude --max-turns 1 --version` çalışıyor ama `--definitely-bogus-flag` de çalışıyor (`--version` seçenek doğrulamasından önce dönüyor) → **yerel kanıt yetersiz**; tek ucuz doğrulama: `claude -p --max-turns 1 --model haiku "1+1"` (küçük kota; QA görevinde).
- Resmî referans: `--max-turns` "Limit the number of agentic turns (print mode only). Exits with an error when the limit is reached. No limit by default"; `--max-budget-usd` "print mode only; subagent spend counts; cap enforcement requires v2.1.217+". Ayrıca `--resume <id>`, `--continue`, `--session-id <uuid>`, `--fork-session`. Kaynak: [CLI reference](https://code.claude.com/docs/en/cli-reference), [backgroundclaude CLI reference](https://backgroundclaude.com/cli-reference), [Budget cap incelemesi](https://linuxjedi.co.uk/when-the-docs-fall-short-investigating-claude-codes-budget-cap/).
- Sonuç: Claude tarafında yaptırım için iki katman: (a) `--max-turns` (varsa) + `--max-budget-usd`; (b) köprü içinde `tool_use` sayacı + süreç öldürme (agy köprüsündeki `max_steps` ile simetri; §3.1).

### 2.4 Antigravity `agy` CLI — konuşma sürdürme ve maliyet (yerelde doğrulandı: `agy --version` = 1.1.28)
- `agy --help` / `agy -p --help`: **`--conversation <id>`** (kimlikle sürdür), **`-c/--continue`** (son konuşma), `--print-timeout` (varsayılan 5m), `--effort low|medium|high`, `--output-format json|stream-json`, `--json-schema`. **Adım/tur/token/bütçe bayrağı yok** (docs da doğruluyor).
- Headless JSON çıktısındaki `usage`: `input_tokens, output_tokens, thinking_tokens, cache_read_tokens, total_tokens`; **maliyet alanı yok**. Konuşma kimliğinin JSON'da nasıl döndüğü docs'ta belirtilmiyor (köprü zaten `current_conversation_id` yakalıyor: `agy_bridge.py:1374`). Kaynak: [Headless mode](https://antigravity.google/docs/cli/headless/), [Managing Conversations](https://antigravity.google/docs/cli/conversations/), [Resume command](https://antigravity.google/docs/cli/commands/resume/), [agy cheat sheet](https://toolsbase.dev/en/reference/antigravity-cli-commands).

### 2.5 Alt görev token tahmini — pratik yöntemler
- Kaba oran: ~4 karakter ≈ 1 token (İngilizce; Türkçe'de 3–3.5). Girdi tahmini için yeterli; **çıktı/araç döngüsü tahmini için yetersiz**.
- Ajan görevlerinde en iyi pratik: aynı ajan/görev sınıfı için **geçmiş medyanı veya EMA (α≈0.2)** + güvenlik payı (p90 ya da +2σ); modelin kendi tahmini gerçekleşenle yalnızca ~0.39 korelasyon veriyor ve sistematik olarak düşük kalıyor. Kaynak: [LLM Cost Prediction: From Single Prompts to Agentic Systems](https://aipractitioner.substack.com/p/llm-cost-prediction-from-single-prompts), [Cost-Aware Speculative Execution for LLM-Agent Workflows (arXiv 2606.07846)](https://arxiv.org/pdf/2606.07846), [Fastio: AI Agent Token Cost Optimization 2026](https://fast.io/resources/ai-agent-token-cost-optimization/).
- **Yerel veri** (`~/.entropy/tasks_ledger.db`, `tasks` tablosu, 76 satır, 57'si token'lı): min 13.3k · p25 38.9k · **medyan 48.1k** · p75 61.4k · p90 82.7k · max 1.10M (tek "Medya Ajans Yeteneği Geliştirme" görevi) · ortalama 89k. Sabit 30k tahmini medyanın **%62'si**.

---

## 3) Kod denetimi (Faz 8 aday listesi için kanıt)

### 3.1 Claude köprüsünde adım tavanı yok (HEAD)
- `claude_bridge.py:738-870 consume_stream`: `tool_use` blokları yalnızca terminale yazılıyor (`:804-810`), sayaç/tavan yok. `build_command` (`:507-583`) `--max-turns`/`--max-budget-usd` üretmiyor.
- agy köprüsü ise `max_steps` alıyor (`agy_bridge.py:603, 678`) ve aşımda süreci öldürüyor. `tasks.py:621` `max_steps=MAX_STEPS_PER_CARD (=20)` geçiyor ama `:630` `_accepts_kwarg` filtresi Claude köprüsünde parametreyi **sessizce düşürüyor** → Claude alt kartları tavansız.
- **Çözüm (agy-integration-engineer, S):** `send_background_task_async(max_steps=…)` + `consume_stream` içinde `tool_use` sayacı + `on_step_limit` → `terminate`; CLI destekliyorsa `--max-turns` (sürüm probu ile, `CLAUDE_SUPPORTS_MAX_TURNS`); `--max-budget-usd` yalnız API anahtarı kullanımında anlamlı (`allow_claude_api=false`).

### 3.2 `SUBCARD_TOKEN_ESTIMATE = 30_000` sabit (`harness.py:74`, `_can_afford :300-312`)
- Ledger medyanı 48k (§2.5) → bütçe kontrolü kartı **~1.6× düşük** tahmin ediyor; "harca, sonra bak" hatasının yarısı geri geliyor. `_estimate_tokens` (`:110`) yalnız 4-karakter kuralı.
- **Çözüm (memory-rag-engineer, S):** `estimate = max(prompt_tokens×3, 1.2×medyan(aynı ofis/ajan son N görev), 30k)`, veri yoksa 48k (ledger medyanı); p90'ı "sert tavan" olarak `_can_afford`'a ikinci parametre.

### 3.3 Ofis çağrılarında `--conversation`/`--resume` kullanılmıyor (HEAD)
- Köprüler destekliyor: `agy_bridge.py:759` `--conversation <id>`, `claude_bridge.py:1328` `resume_id=conversation_id`. Ama `harness._call_agent` (`:1187-1240`) ve `tasks.py:600-635` `conversation_id` geçmiyor → orkestratör → değerlendirici → yeniden planlama zincirinde her çağrı sıfır bağlamla açılıyor; kart metni + ofis belleği her seferinde yeniden gönderiliyor.
- **Çözüm (agy-integration-engineer, M):** biten görevin sağlayıcı oturum/konuşma kimliğini `on_result` sonrası kart durumuna yaz; aynı kartın sonraki orkestratör/değerlendirici çağrılarında geçir; sağlayıcı değişince unut. Risk: uzun konuşma bağlamı maliyeti artırabilir → kart başına tur sayısı tavanı (ör. 6) ve `reset` kuralı.

### 3.4 `chat_mode.py:1373` kapanış yolunda "Failed to disconnect" uyarıları
- `closeEvent` (`chat_mode.py:1353-1375`) 15 sinyali koşulsuz `disconnect` ediyor; `zen_mode.py:1266-1285` aynı desen (14 sinyal).
- **Ölçüm** (`disconnect_probe.py`, HEAD): 1. `close()` → 0 uyarı; 2. `close()` → **15 × "libpyside: Failed to disconnect (…)"**; bağlantısız slotta `disconnect` `False` döner + `RuntimeWarning`. Test paketinde `conftest.py:29-62` her testten sonra üst düzey pencereleri **yeniden** kapatıyor → testin kendi `finally: chat.close()`'u ile çift kapanış; 526 ≈ 35 çift kapanış × 15. Tek dosyada (`tests/test_desk_window.py`) 28 uyarı sayıldı.
- **Çözüm (ui-engineer, XS):** `self._bus_connected` bayrağı; `closeEvent` yalnız bağlıysa koparır; `context_pressure`/`inbox_unread` gibi listede olmayan bağlantılar da (`chat_mode.py:598`) eklensin (sızıntı).

### 3.5 Depo kökündeki takipsiz artıklar — güvenli silme analizi

| Artık | Adet | İçe aktaran var mı? (grep `src/ tests/`) | Karar |
|---|---|---|---|
| `module_task_*.py` (kök) | 13 | **Yok** ("Otonom Uygulama Modülü … Görev ID: task_…", ajan üretimi) | Sil (veya `scratch/`); `.gitignore`'a `module_task_*.py` |
| `schema_task_*.py` (kök) | 29 | **Yok** (pydantic "TaskContract" iskeletleri) | Sil; `.gitignore`'a `schema_task_*.py` |
| `src/entropy/tools/autonomous_agent_architecture_faz*.py` | 59 takipsiz (+1 takipli `faz158`) | **16'sı** takipli 32 test dosyasınca içe aktarılıyor (`tests/test_autonomous_agent_architecture_faz*.py`, ör. `faz110`, `faz150`); **44'ü yetim** (`faz98-104, 107-109, 112-145`) | Yetimleri sil; 16'sını ya commit'le ya da test çiftiyle birlikte kaldır — **kör silme test paketini kırar** |
| `src/entropy/tools/autonomous_agent_architecture.py` | 1 | takipsiz; testler içe aktarmıyor | Sil |
| `src/entropy/memory/supabase/cognitive_memory.db` (332 KB, 6 Eyl) | 1 | Kod `~/.entropy/cognitive_memory.db` kullanıyor (`cognitive_memory.py:311`, `vault_manager.py:469`) | Sil (yedeği `~/.entropy/*.bak*` zaten var) |
| `.entropy/tasks_ledger.db` (depo içi, 0 bayt) | 1 | Ledger `~/.entropy/tasks_ledger.db` (`task_ledger.py:26`) | Sil; gitignore'da zaten |
| Kök `*_financial_audit.md`, `canivopets_audit*.{md,json}`, `enjsa_metrics.json`, `financial-auditor/`, `google_flow_files/` | ~10 | yetenek çıktıları | Kullanıcı kararı: kasaya taşı / sil |
| `scratch/_build*.log`, `EntropyAgentDesk.spec` | 5 | — | Sil / `.gitignore` |

### 3.6 Diğer gözlemler
- `entropy.log:270-273` (14:13): `vault_manager.build_knowledge_graph:674` `'NoneType' has no attribute 'strip'` — ön bilgi alanı `None` olan not grafiği çökertiyor (memory-rag-engineer, XS).
- `QFileSystemWatcher … Access is denied` (OneDrive altındaki `Entropy/Agents/*`, `Desk/Offices/dogrulama/inbox`) — izleyici + yoklama zaten var; uyarı gürültüsünü bastırmak yeter (XS).
- `dist/EntropyAI/EntropyAI.exe` 18:35 derlemesi HEAD'den (18:42) **önce**: kullanıcının gördüğü sürüm son iki commit'i içermiyor olabilir; QA her fazda `dist_check` derlemesini teyit etsin.

### 3.7 Çalışma ağacında süren Faz 8 düzenlemeleri (19:04–19:10; commit'lenmemiş)
`git diff --stat`: `harness.py +114`, `claude_bridge.py +102`, `zen_mode.py +70`, `chat_mode.py +49`, `agy_bridge.py +48`, `window_sizing.py +36`, `manager.py +29`; ayrıca `report_center.py`, `reports_viewer.py`, `core_visualizer.py`, `terminal_pane.py`, `desk_registry.py`; yeni `ui/widgets/flow_layout.py`, `ui/widgets/frameless.py`, `tests/test_phase8_steps_estimate_conversation.py`, `tests/test_ui_phase8_windows_and_reports.py`.

Görünen kapsam (diff satır başlıkları): `FlowHeaderFrame` akan üst çubuk (Chat+Zen), `toggle_maximize` + `─ ❐ ✕`, `startSystemMove`, `maximize_window_to_screen` / `clamp_window_into_screen`, `CLAUDE_SUPPORTS_MAX_TURNS=False` + `tool_use` sayacı, `estimate_subcard_tokens` (medyan × `SUBCARD_MEDIAN_MARGIN=1.2`), `office_conversation_id / remember_office_conversation`, `closeEvent` koruması, Rapor Merkezi "🗂 Tümü" düğmesi. Yani §3.1–3.4 ve §1.1–1.3'ün büyük kısmı **yolda**.

Çalışma ağacı ölçümleri: Chat üst çubuk `sizeHint` 2447 → **232 px** (akan düzen, 600 px pencerede satır atlıyor), Zen 2629 → 380 px; ama `tests/test_desk_window.py::test_zen_and_chat_have_agent_desk_button` **başarısız** (23 geçti, 1 kaldı; düğme sırası varsayımı `bar.indexOf(desk_btn)==1` akan düzende bozuldu) ve Zen `minimumSizeHint` dikeyde 713 → **990 px**'e çıktı (dar pencerede çok satıra kırılan çubuk; 1032 px'lik alanda sınırda). Faz 8 iş listesi bu işi **yeniden yazmak değil, doğrulayıp tamamlamak** olarak kurgulanmalı.

---

## 4) Faz 8 önerilen iş listesi (öncelikli, ajan ataması)

| # | Öncelik | İş | Ajan | Boyut | Kabul ölçütü |
|---|---|---|---|---|---|
| 1 | P1 | Zen pencere kabuğu: `startSystemMove` sürükleme, çift tık büyüt, `─ ❐ ✕`, açılışta tam kullanılabilir alan, tekrar geçişte geometri korunumu, ekran adına göre kalıcılık | ui-engineer | M | Pencere üst çubuktan taşınır; `switch_mode("zen")` ikinci çağrıda geometriyi ezmez; offscreen test |
| 2 | P1 | Akan üst çubuk (Chat+Zen) + kısaltmalar + mod düğmeleri sabit sağ köşe; **mevcut diff'i tamamla**: `test_zen_and_chat_have_agent_desk_button` uyumu, Zen dikey minimum ≤ 700 px | ui-engineer | M | 600 px pencerede "Zen" görünür; `header.sizeHint().width() ≤ 900`; tam test paketi yeşil |
| 3 | P1 | Rapor Merkezi görünürlüğü: sayaç elide/iki satır, "🗂 Tümü (N)" sessiz bölümü açar + listeye odaklanır, Chat "Gelen" `limit=60` kaldır/"60 / 895" | ui-engineer + memory-rag-engineer | S | Zen sol panel 220 px'te "895" okunur; Chat ve Zen aynı toplamı gösterir |
| 4 | P1 | Claude alt kart adım tavanı (`tool_use` sayacı + terminate; CLI `--max-turns` probu) ve `tasks.py` filtresinin Claude'a `max_steps` geçirmesi | agy-integration-engineer | S | Sahte akışta 21. `tool_use` → görev `failed`, süreç öldürüldü; ledger'a yazıldı |
| 5 | P2 | Uyarlanabilir alt kart tahmini: ofis/ajan medyanı × 1.2, veri yoksa 48k; p90 sert tavan | memory-rag-engineer | S | `_can_afford` medyanlı tahmin kullanır; test: 3 geçmiş görevle tahmin değişir |
| 6 | P2 | Ofis konuşma sürekliliği: kimlik yakala → kartta sakla → sonraki orkestratör/değerlendirici çağrısında `conversation_id`; sağlayıcı değişince sıfırla; tur tavanı | agy-integration-engineer | M | İkinci çağrının argv'sinde `--conversation`/`--resume` görünür (sahte köprü testi) |
| 7 | P2 | Kasa temizliği: `Projects/test_*` raporlarını `_archive`'e taşı (onayla); test kasası izolasyonu (`obsidian_vault_path` → `tmp_path`) | qa-build-engineer | S | Tam paket sonrası gerçek kasada yeni dosya yok |
| 8 | P2 | `closeEvent` çift kapanış koruması (Chat+Zen) + eksik bağlantıların koparılması | ui-engineer | XS | Paket uyarı sayısında "Failed to disconnect" = 0 |
| 9 | P3 | Artık temizliği (§3.5 tablosu) + `.gitignore` (`module_task_*.py`, `schema_task_*.py`); yetim `faz*` modülleri | qa-build-engineer | S | `git status` temiz; test paketi 1933+ yeşil |
| 10 | P3 | Desk örtük minimumu (1930 px) ve `build_knowledge_graph` `None.strip` çökmesi | ui-engineer / memory-rag-engineer | S | Desk `minimumSizeHint ≤ 1200`; grafik `None` alanlarda çökmüyor |
| 11 | P3 | `dist_check` derlemesi + smoke: Zen taşıma, Chat üst çubuk, Rapor Merkezi sayacı (LG 2.0 + 1.0 ekranlarda ekran görüntüsü) | qa-build-engineer | S | Faz raporuna 3 ekran görüntüsü |

Sıra önerisi: 2 → 1 → 8 (tek ui-engineer görevi, aynı dosyalar) ‖ 4 → 6 (agy-integration-engineer) ‖ 3 → 5 → 10b (memory-rag-engineer) → 7, 9, 11 (qa-build-engineer kapanış).

---

## 5) Kaynaklar

**Yerel kanıt**
- `git archive HEAD` (`e177d08`) kopyası üzerinde `scratchpad/measure_header_head.py`, `measure_reports.py`, `disconnect_probe.py` çıktıları (bu notta alıntılandı).
- `claude --help`, `claude --version` (2.1.265); `agy --help`, `agy -p --help`, `agy --version` (1.1.28).
- `C:\EntropiAI\.entropy\logs\entropy.log` (satır 268-276), `settings.json`; `~/.entropy/tasks_ledger.db` (`tasks`, 57 token'lı satır).
- `QGuiApplication.screens()` (PassThrough) ekran dökümü; PowerShell `Win32_VideoController`, `PerMonitorSettings`.

**Web**
- Qt: [QWindow (6.11)](https://doc.qt.io/qt-6/qwindow.html) · [Custom client-side window decorations in Qt 5.15](https://www.qt.io/blog/custom-window-decorations) · [Qt Forum — resizable frameless window](https://forum.qt.io/topic/146396/how-to-create-a-resizable-frameless-window) · [Window Flags Example](https://doc.qt.io/qt-6/qtwidgets-widgets-windowflags-example.html) · [High DPI (6.11)](https://doc.qt.io/qt-6/highdpi.html) · [Qt for Python — High DPI](https://doc.qt.io/qtforpython-6.5/overviews/highdpi.html) · [Qt Forum — QT_ENABLE_HIGHDPI_SCALING](https://forum.qt.io/topic/162609/qt6-and-qt_enable_highdpi_scaling) · [pyqt-frameless-window](https://pypi.org/project/pyqt-frameless-window/) · [FramelessHelper](https://github.com/bmzp/framelesshelper-1)
- Claude Code: [CLI reference](https://code.claude.com/docs/en/cli-reference) · [backgroundclaude — CLI reference](https://backgroundclaude.com/cli-reference) · [Investigating Claude Code's Budget Cap](https://linuxjedi.co.uk/when-the-docs-fall-short-investigating-claude-codes-budget-cap/) · [Claude Code Cheat Sheet 2026](https://computingforgeeks.com/claude-code-cheat-sheet/)
- Antigravity: [Headless mode](https://antigravity.google/docs/cli/headless/) · [Managing Conversations](https://antigravity.google/docs/cli/conversations/) · [Resume command](https://antigravity.google/docs/cli/commands/resume/) · [agy CLI cheat sheet](https://toolsbase.dev/en/reference/antigravity-cli-commands) · [Hands-on with Antigravity CLI (Codelab)](https://codelabs.developers.google.com/antigravity-cli-hands-on)
- Token tahmini: [LLM Cost Prediction: From Single Prompts to Agentic Systems](https://aipractitioner.substack.com/p/llm-cost-prediction-from-single-prompts) · [Cost-Aware Speculative Execution for LLM-Agent Workflows (arXiv)](https://arxiv.org/pdf/2606.07846) · [AI Agent Token Cost Optimization 2026](https://fast.io/resources/ai-agent-token-cost-optimization/) · [LLM Token Optimization (Redis)](https://redis.io/blog/llm-token-optimization-speed-up-apps/)
