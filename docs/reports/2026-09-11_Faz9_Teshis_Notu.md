# Faz 9 — Teşhis Notu (salt okunur)

- Tarih: 2026-09-09 (rapor dosya adı Faz 9 konvansiyonu gereği 2026-09-11)
- Branch: `ai/v0.1.7`
- Kaynak ağacı: `C:\EntropiAI\src\entropy` (paket kökü `src/`, `entropy/` değil)
- Hiçbir kaynak dosya değiştirilmedi, model çağrısı yapılmadı, çalışan süreç kapatılmadı.

## 0. Çalışma ortamı tespiti (hangi build koşuyordu)

Kanıt — `.entropy/logs/entropy.log`:

```
2026-09-09 20:32:04,086 INFO entropy.agents.bootstrap: Ajan derlemesi: 3 ajan, kökler=['C:\\EntropiAI\\dist\\EntropyAI']
2026-09-09 06:11:13,862 INFO entropy.agents.bootstrap: Ajan derlemesi: 3 ajan, kökler=['C:\\EntropiAI\\dist_check\\EntropyAI']
```

Kanıt — `~/.entropy/tasks_ledger.db`, `tasks` tablosu:

```
card-20260909-204445-g-rev-1 | project_path = C:\EntropiAI\dist\EntropyAI | FAILED
card-20260909-203921-canivo-reklam | project_path = C:\EntropiAI\dist\EntropyAI | CANCELLED
```

**Sonuç:** günün son oturumları (17:07, 18:36, 20:24, 20:32) **eski `dist\EntropyAI`** ile
koştu; `dist_check` yalnızca 06:11'de bir kez çalıştı. `Get-Process EntropyAI` şu an boş —
uygulama 20:48'den sonra kapanmış. **Bu yüzden günlükteki traceback satır numaraları eski
build'e aittir; aşağıda her kök neden ayrıca güncel `src/` üzerinde doğrulanmıştır.**

---

## 1. Çoklu boş pencere + donma ("Entropy AI (Yanıt Vermiyor)")

### Kanıt

`.entropy/logs/entropy.log` — 20:32–20:46 arası 11 kez, aynı istisna:

```
2026-09-09 20:32:34,156 CRITICAL entropy.crash: Yakalanmayan istisna (ana iş parçacığı):
Traceback (most recent call last):
  File "entropy\ui\widgets\frameless.py", line 91, in eventFilter
TypeError: int() argument must be a string, a bytes-like object or a real number, not 'Edge'
```

`.entropy/logs/entropy_fault.log` — 26 kez:

```
Windows fatal exception: code 0x8001010d
Current thread ...:
  File "entropy\main.py", line 240 in main      <- app.exec()
  File "run_entropy.py", line 15 in <module>
```

`0x8001010d = RPC_E_CANTCALLOUT_ININPUTSYNCCALL`: "girdi-eşzamanlı bir çağrı işlenirken
dışarı çağrı yapılamaz" — Windows'un yerel sürükle/boyutlandır modal döngüsü (SendMessage)
içindeyken COM çağrısı yapıldığında oluşur.

Güncel kaynak — `src/entropy/ui/widgets/frameless.py:88-95` (hata **hâlâ mevcut**):

```python
if not self.window.isMaximized():
    edges = self._edges_at(global_pos)
    if int(edges):                       # <-- satır 91
        handle_win.startSystemResize(edges)
```

`_edges_at` (`frameless.py:47-61`) `Qt.Edge(0)` / `Qt.Edge` bayrak nesnesi döndürür.
PySide6 6.7+'ta `Qt.Edge` bir `enum.Flag`'dır (IntFlag değil) → `int(edges)` **TypeError**.

### Kök neden

1. Kullanıcı pencere kenarına her bastığında `eventFilter` satır 91'de patlar. İstisna
   `try` bloğunun **dışındadır** (try satır 92'de başlar), dolayısıyla PySide6'nın sanal
   metot sarmalayıcısına kaçar; olay tüketilmez, `sys.excepthook` CRITICAL basar ve olay
   dağıtımı yarıda kalır.
2. Üst çubuk sürüklendiğinde `startSystemMove()` (satır 100) Windows'un **modal** sürükleme
   döngüsünü başlatır. Bu döngü içindeyken Qt olay döngüsü durur; arka planda koşan
   `ReportWatcher` / `identity` prob'ları COM'a dokununca `RPC_E_CANTCALLOUT_ININPUTSYNCCALL`
   üretir (fault log'daki 26 kayıt).
3. Uygulama yanıt vermeyi bıraktığında Windows **her üst düzey HWND için bir "ghost"
   penceresi** çizer: yerel çerçeveli (─ ☐ ✕), içi bembeyaz, başlığı
   `<özgün başlık> (Yanıt Vermiyor)`. Süreçte aynı anda en az şu üst düzey pencereler var:
   `ZenModeWindow` (başlık tam olarak **"Entropy AI"**, `ui/modes/zen_mode.py:70`),
   `ChatModeWindow` (`chat_mode.py:231`), `FloatingModeWidget`, `StandaloneReportWindow`
   (modül-genel tekil + Chat'in kendi ikinci örneği), `AgentDeskWindow`, tepsi penceresi ve
   QtWebEngine yardımcı pencereleri. `ui/manager.py:36-38` üçünü de açılışta yaratır.
   Basamaklı 8-10 beyaz pencere bu ghost'lardır — kod parent'sız pencere döngüsü üretmiyor
   (`grep .show()` sonucu yalnızca 8 çağrı, hepsi tekil).
4. Donmayı uzatan ikinci etken (bkz. §2): `bus.reports_updated` her tetiklendiğinde Rapor
   Merkezi ana iş parçacığında **703 raporu** yeniden okur ve kümeler.

### Düzeltme önerisi

- `frameless.py:91` → `if edges != Qt.Edge(0):` veya `if edges.value:`; `_edges_at` doğrudan
  `int` bayrak döndürsün. Tüm `eventFilter` gövdesi `try/except Exception: return False`
  ile sarılsın — olay süzgecinden asla istisna kaçmamalı.
- `startSystemMove/Resize` çağrılarından önce ağır arka plan prob'ları duraklatılmalı ya da
  `QTimer.singleShot(0, ...)` ile modal döngü dışına atılmalı.
- Regresyon testi: `Qt.Edge` bayrağıyla `_edges_at` dönüşünün `eventFilter`'da istisna
  üretmediğini doğrulayan offscreen test.

**Ajan:** ui-engineer · **Risk:** düşük (3 satır, davranış değişmiyor); test edilmezse
kenar boyutlandırma sessizce kapanabilir.

---

## 2. CHAT'te Rapor Merkezi: "okundu", "Tümünü okundu say", "Temizle" çalışmıyor

### Kanıt

- Kasada **703** `Reports/*.md` (`find "…/Entropy" -path "*/Reports/*" -name "*.md" | wc -l`),
  toplam 821 `.md`.
- `src/entropy/ui/widgets/report_center.py:1201` → `VAULT_RELOAD_LIMIT = 5000`
- `report_center.py:1203-1206` → `reload_from_vault()` = `collect_recent_entries(limit=5000)`
- `report_inbox.py:200-231` → `collect_recent_entries` her künye için `read_report_meta(path)`
  çağırır: **her rapor dosyası diskten okunur**.
- `report_center.py:1068-1070` → `refresh()` her çağrıda `build_report_center(...)` koşar;
  `enrich_entry` (satır 273-308) her girdi için ayrıca `_read_head(path, 8192)` yapar —
  **ikinci kez disk okuması**; `cluster_entries` (satır 384-430) küme merkezleriyle
  O(N·K) TF-IDF kosinüsü hesaplar.
- `report_inbox.py:108-113` → `_set()` **her tek değişiklikte** tüm JSON'u diske yazar:

```python
def _set(self, path, **changes):
    item = self._items.setdefault(key, {"first_seen": time.time()})
    item.update(changes)
    self.save()          # <-- her mark_read çağrısında tam dosya yazımı
```

- `report_center.py:1170-1174` → `mark_all_read()` N kart × M üye döngüsünde `mark_read`
  çağırır ⇒ **yüzlerce tam dosya yazımı**, ardından tek `refresh()`.
- `report_center.py:1176-1184` → `prune_missing()` ("Temizle") tüm girdiler için
  `Path(...).exists()` çağırır; kasa OneDrive'da olduğundan her biri ağ/senkron gecikmesi.
- Ayrıca `bus.reports_updated` her sinyalinde `_on_reports_updated` → `reload_from_vault()`
  (satır 1188-1190): tek bir rapor yazımı 703 dosyanın yeniden okunmasını tetikler.

İkinci, bağımsız hata — **iki pencere aynı durum dosyasını yarıştırıyor**:

- Chat: `chat_mode.py:682,691` → `ReportInboxStrip` ile `ReportCenterWidget` **aynı** store'u paylaşır (doğru).
- Zen: `reports_viewer.py:216,227` → **ayrı bir** `ReportInboxStore()` örneği yaratır.
- `report_inbox.py:58-63` her örnek dosyayı **bir kez** yükler; `save()` (satır 77-86) tüm
  sözlüğü ezerek yazar. Zen ve Chat pencereleri aynı anda açıktır (`ui/manager.py:36-38`),
  dolayısıyla Zen tarafında yapılan tek bir işlem Chat'in okundu işaretlerini **geri alır**.
  Durum dosyası: `<STATE_DIR>/report_inbox.json` (`report_inbox.py:51-52`).

### Kök neden

(a) Kullanıcı arayüzü tıklamaya yanıt vermiyor gibi görünüyor çünkü tek tıklama =
703 dosya okuma ×2 + TF-IDF kümeleme + N tam JSON yazımı, hepsi ana iş parçacığında.
(b) İki ayrı `ReportInboxStore` örneği son-yazan-kazanır yarışı üretiyor; Zen'de "çalışıyor"
görünmesi, Zen'in son yazan olmasındandır.

### Düzeltme önerisi

- `ReportInboxStore`'u süreç-genelinde **tekil** yap (modül seviyesinde `get_store()`),
  ya da her `save()` öncesi dosyayı yeniden okuyup birleştir (read-modify-write).
- `_set()`'e `autosave=False` parametresi; `mark_all_read` / `mark_paths_read` /
  `archive_paths` toplu çalışıp sonda **tek** `save()` yapsın.
- `enrich_entry` sonucunu `(path, mtime, size)` anahtarıyla önbelleğe al; `collect_recent_entries`
  ile `_read_head` arasındaki çift okumayı tek okumaya indir.
- `reload_from_vault` iş parçacığına taşınsın veya `VAULT_RELOAD_LIMIT` görünür pencereye
  (örn. 200) indirilip "Tümü" düğmesiyle tam liste istensin.

**Ajan:** memory-rag-engineer (depo/tekillik + önbellek) + ui-engineer (toplu işlem, iş parçacığı)
**Risk:** orta — okundu durumunun tek kaynağa taşınması mevcut `report_inbox.json` içeriğini
etkilemez ama iki yüzeyin senkronu için test gerekir.

---

## 3. "Yeni Araştırma Raporu Oluşturuldu: AGENT — Dosya: AGENT.md — Bilişsel Hafıza ve RAG'a işlendi"

### Kanıt

`src/entropy/ui/widgets/agents_widget.py:1178-1187`:

```python
def open_agent_file(self, spec) -> bool:
    path = Path(path_str)
    ...
    bus.report_created.emit(str(path))     # <-- satır 1186
    return True
```

Dinleyiciler:
- `ui/modes/chat_mode.py:610 → 819 _on_report_created` → satır 841-843 kartı basar:
  `📑 Yeni Araştırma Raporu Oluşturuldu` / `Dosya: {p.name} | Bilişsel Hafıza ve RAG'a İşlendi`
- `ui/modes/zen_mode.py:595 → 638` aynısı
- `ui/widgets/knowledge_graph.py:3195 → 3210 _on_report_created` → `schedule_refresh()`
  ⇒ çekirdekte **"Rapor: AGENT"** çipi ve 1,2 sn sonra tam grafik yeniden inşası
- `ui/widgets/notification_center.py:142,164` → bildirim satırı

`ReportWatcher` **suçsuz**: `memory/report_watcher.py:91-116` yalnızca `Reports/` klasörlerini
tarar (`d.glob("*.md")`), `AGENT.md` o kapsamda değil.

Kasa doğrulaması (salt okuma) — `Reports/` altında **hiçbir** "AGENT" raporu yok:

```
Entropy/Agents/{analist,arastirmaci,yazar}/AGENT.md
Entropy/Desk/Offices/Araştırma Ofisi/agents/{Alfa,Kenan}/AGENT.md
Entropy/_archive/2026-09-09/dogrulama-canli-kosu/agents/*/AGENT.md
```

### Kök neden

`bus.report_created` iki farklı anlam taşıyor: (1) "yeni araştırma raporu üretildi ve belleğe
işlendi" (`core/agy_bridge.py:1839`, `ui/widgets/task_board_widget.py:340,346`) ve
(2) "şu dosyayı okuyucuda aç" (`agents_widget.py:1186`, `reports_viewer.py:837`). İkinci
kullanım, birinci anlamın tüm yan etkilerini (sohbet kartı, RAG iddiası, grafik yeniden
inşası, bildirim) tetikliyor. "Bilişsel Hafıza ve RAG'a İşlendi" cümlesi bu yolda **yanlış**:
hiçbir indeksleme yapılmıyor.

Ek eksik: dosya-türü süzgeci hiçbir yerde yok — `AGENT.md`, `OFFICE.md`, `MEMORY.md`,
`PLAYBOOK*`, `layout.json`, handoff sayfaları rapor sayılmaya açık.

### Düzeltme önerisi

- `bus.report_created`'ı ikiye ayır: `report_created(path)` (gerçek üretim, RAG iddiası
  yalnız burada) ve `open_file_requested(path)` (yalnızca okuyucuyu açar).
  `agents_widget.py:1186` ve `reports_viewer.py:837` ikincisini kullansın.
- `_on_report_created` içine reddetme listesi: `AGENT.md`, `OFFICE.md`, `MEMORY.md`,
  `PLAYBOOK*.md`, `SKILL.md`, `log.md`, `*.json`.
- Kart metnindeki "RAG'a İşlendi" ifadesi yalnızca indeksleme dönüşü doğrulandığında yazılsın.

**Ajan:** memory-rag-engineer (sinyal sözleşmesi + süzgeç) · ui-engineer (kart metni)
**Risk:** düşük-orta — sinyal ayrımı 6 çağrı yerini etkiler; testlerde `report_created`
bekleyen doğrulamalar güncellenmeli.

---

## 4. "Unknown command: /media-agency-soldier" ama çipte "YETENEK: /media-agency-soldier"

### Kanıt

- Bu metin **Entropy kaynağında yok** (`grep -rn "Unknown command"` yalnızca
  `skills/financial-auditor/scripts/*.py` içindeki alakasız JSON hataları). Yani cevabı
  **sağlayıcı CLI'ı (claude)** üretti: ham `/media-agency-soldier ...` metni ona gitti.
- Ledger doğrulaması: `card-20260909-204445-g-rev-1`, `error = "Çıkış kodu: 1, yanıt uzunluğu: 153"`
  — 153 karakter, kısa bir "Unknown command" yanıtına uyar.
- `core/slash_commands.py:1085` `try_handle_local_command` yalnızca sabit listeyi
  (`/distill /ask /chat /effort /login /handoff /wiki /lint /agents /agent /task(s) /offices /desk`)
  işler; **yetenek adlarını hiç ele almaz**.
- `core/slash_commands.py:1287+` `get_dynamic_skill_commands` yetenekleri yalnızca
  **tamamlayıcı/çip** için üretir (`category="skill"`, `badge="🎯 YETENEK"`).
- `ui/modes/chat_mode.py:1274-1282` eşleşen yetenek çipi basılır ve `skill_combo` gerçekten
  yeteneğe ayarlanır; ama satır **1322**:

```python
actual_prompt = prompt          # <-- "/media-agency-soldier ..." token'ı OLDUĞU GİBİ kalır
```

Sonra `self.bridge.send_prompt_async(actual_prompt, ...)`.

### Kök neden

Yetenek slash komutu **iki katmanda ayrı** ele alınıyor: arayüz onu tanıyıp yeteneği
etkinleştiriyor, ama metinden **çıkarmıyor**; CLI kendi slash komut ad alanında arayıp
bulamıyor. Beklenen davranış (yeteneği etkinleştir + kalan metni gönder) yarım uygulanmış.

### Düzeltme önerisi

`chat_mode.py` (ve Zen'deki eşleniği) içinde `matched_cmds` arasından `category == "skill"`
olanların token'ını `actual_prompt`'un **başından** temizle:

```python
for mc in matched_cmds:
    if mc.category == "skill":
        actual_prompt = re.sub(rf"(?:^|\s){re.escape(mc.name)}\b\s*", " ", actual_prompt, count=1).strip()
```

Metin tamamen boşalırsa yeteneğin kendi açılış istemi gönderilsin. Aynı temizlik
`category in ("mcp","mcp_tool")` için de gözden geçirilmeli.

**Ajan:** agy-integration-engineer (istem oluşturma) · ui-engineer (çip/kombo davranışı)
**Risk:** düşük; `/plan` gibi CLI'ın gerçekten tanıdığı komutların **silinmemesi** için
yalnızca `category == "skill"` filtrelenmeli.

---

## 5. "Görev: Canivo Reklam" kartı, model karışıklığı ve ofis/Entropy sınırı

### Kanıt — kartın kendisi

`…/Obsidian Vault/Entropy/Tasks/20260909-203921-canivo-reklam.md` (ön bilgi, aynen):

```yaml
id: 20260909-203921-canivo-reklam
title: Canivo Reklam
status: failed
agent: Alfa
provider: claude
model: claude-opus-5
skill:
office:            # <-- BOŞ
project:           # <-- BOŞ
parent:
```

`…/Entropy/Desk/Offices/Araştırma Ofisi/agents/Alfa/AGENT.md`:

```yaml
name: Alfa
role: orchestrator
description: Ofisin planlayıcısı — ... Kod yazmaz.
provider: claude
model: claude-opus-5
office: Araştırma Ofisi
```

**Alfa, Desk ofisinin ORKESTRATÖRÜDÜR.** Kartın `provider`/`model` alanları Alfa'nın
AGENT.md'siyle birebir aynı; yani kart Alfa'nın tanımından türetildi, ama `office` alanı
boş bırakıldı.

### Kanıt — ledger

```
card-20260909-203921-canivo-reklam | project_path = C:\EntropiAI\dist\EntropyAI
   | CANCELLED | error = "Uygulama kapandı; görev yarıda kesildi."  (20:40:29)
card-20260909-204445-g-rev-1       | project_path = C:\EntropiAI\dist\EntropyAI
   | FAILED    | error = "Çıkış kodu: 1, yanıt uzunluğu: 153"
card-20260909-171945-readme-mimari-ve-kurulum
   | project_path = …\Entropy\Desk\Offices\dogrulama | FAILED | "Çıkış kodu: 0, yanıt uzunluğu: 0"
```

Üretilen rapor `…/Entropy/Skills/media-agency-soldier/Reports/Gorev_Canivo Reklam_20260909_2040.md`
— gövde `## Görev Çıktısı ve Bulgular` başlığından sonra **boş**; bu yüzden "Durum: Hata/Uyarı".

### Kök neden (üç ayrı kusur)

**5a — Kart klasörü paylaşılıyor.** `src/entropy/agents/tasks.py:51`:

```python
TASKS_SUBDIR = "Entropy/Tasks"
```

Hem Entropy'nin kendi kartları (`ui/widgets/agents_widget.py:116` → `TaskBoard()`) hem ofis
harness kartları (`agents/harness.py:265,1331`, `agents/mailbox.py:559` → `TaskBoard(vault_path=…)`)
aynı `Entropy/Tasks/` yoluna yazıyor. Entropy'nin Görevler paneli ve çekirdek çipleri bu
klasörü süzgeçsiz okuduğu için **ofis kartları Entropy'de görünür** — kullanıcının
"Agent Desk, Entropy'ye görev yolluyor" algısının doğrudan kaynağı budur.

**5b — Desk orkestratörüne Entropy üzerinden iş verilebiliyor.** Kart `agent: Alfa` ile
oluşturulmuş; Alfa `role: orchestrator`'dır ve tanımı "Kod yazmaz" der. Sabit mimari
kuralına göre (ayrı ofis kökü, orkestratör Entropy'yi bilmez, kod yazmaz) Entropy'nin
görev yüzeyi Desk ofis ajanlarını hedef olarak **sunmamalıdır**. Not: Entropy'nin kendi
`AgentRegistry`'si (`agents/registry.py:418`, yalnızca `Entropy/Agents`) Alfa'yı listelemez;
kart bu nedenle Desk yüzeyinden ya da doğrudan kart yazımından gelmiş olmalı — hangi
düğmeye basıldığı **günlükten doğrulanamadı** (UI eylem günlüğü yok).

**5c — Kartın `model` alanı yürütmeye hiç geçmiyor.** `agents/tasks.py:587-591`:

```python
provider = (card.provider or (agent_spec.provider if agent_spec else "agy") or "agy").lower()
bridge = self.bridge_for(provider, bridge_factory=bridge_factory)
```

`bridge_for` (satır 447-477) sırayla: enjekte edilen fabrika → **etkin köprü (üst çubuktaki
seçim!)** → süreç önbelleği. `card.model` **hiçbir yere** aktarılmıyor; köprü kendi
`selected_model`'ini kullanıyor. `core/config.py:118,157` varsayılanı
`"agy": "gemini-3.1-pro-high"` ve `selected_model = "gemini-3.1-pro-high"`. Kart
`claude-opus-5` yazsa da yürütme üst çubuğun modeliyle koşar — kullanıcının gördüğü
"Claude Code gemini-3.1-pro-high ile başlatıldı" tam olarak budur.

Ek: `project_path` verilmediğinde köprü `active_project_dir`'e düşüyor; ledger bunun
`C:\EntropiAI\dist\EntropyAI` (exe klasörü) olduğunu gösteriyor — görevin boş çıktı
üretmesinin makul nedeni.

### Düzeltme önerisi

- `TASKS_SUBDIR`'i ikiye ayır: Entropy kartları `Entropy/Tasks/`, ofis kartları
  `Entropy/Desk/Offices/<ofis>/Tasks/` (arşivde zaten böyle bir yapı var:
  `_archive/2026-09-09/dogrulama-canli-kosu/Tasks/`). Geçiş için Entropy panelinde
  `office != ""` olan kartlar süzülsün (tek satırlık ara çözüm).
- Entropy'nin ajan seçicisi Desk ofis ajanlarını **hiç listelemesin**; Desk'e iş yalnızca
  posta kutusu komutlarıyla (`/ask <ofis>`) gitsin.
- `tasks.py`'de kart yürütülürken `card.model` köprüye geçirilsin (`bridge.selected_model`
  geçici olarak set edilip geri alınsın veya `send_background_task_async(model=...)` eklensin);
  `bridge_for`'un "etkin köprüyü ödünç alma" yolu, model uyuşmazlığında kullanılmasın.
- `project_path` boşsa görev başlatılmasın; exe klasörü asla proje kökü olmamalı.

**Ajan:** memory-rag-engineer (kart deposu/yol ayrımı) · agy-integration-engineer (model ve
proje yolu aktarımı) · ui-engineer (ajan seçici süzgeci)
**Risk:** yüksek — kart yolu değişimi mevcut kartların görünürlüğünü etkiler; taşıma
`dry_run` ile doğrulanmalı. Model aktarımı AGY kotası harcamadan test edilebilir (sahte köprü).

---

## 6. Üst çubuğun ikinci satırındaki içi boş kırmızı kare (~30×30)

### Kanıt

- `.entropy/logs/entropy.log` 00:00:08–00:00:10 arasında **176 satır**:
  `OpenType support missing for "Segoe UI Emoji"` / `"Segoe UI Symbol"` / `"Segoe UI"`,
  script 10/14/20; ayrıca **13 satır**
  `WARNING DirectWrite: CreateFontFaceFromHDC() failed (Indicates an error in an input file such as a font file.)`.
  Yani sistemde emoji fontu düzgün yüklenmiyor.
- `src/entropy/ui/modes/chat_mode.py:371,636,644,649,654` — üst çubuktaki `state_badge`
  metinleri **emoji ile başlıyor**: `"🟢 HAZIR"`, `"🔴 GÖREV HATASI"`, `"⏰ GÖREV: …"`,
  `"📘 DAMITMA n/m"`. 20:40 ve 20:44'te iki görev başarısız olduğu için rozet
  `"🔴 GÖREV HATASI"` durumundaydı (ledger: CANCELLED + FAILED).
- Üst çubuk `FlowHeaderFrame` (`chat_mode.py:254`, `ui/widgets/flow_layout.py:117-141`)
  akan yerleşimdir; pencere daraldığında rozetler **ikinci satıra** düşer — kullanıcının
  gördüğü "sol altta ENTROPY AI altında" konumu bu.

### Kök neden (birincil hipotez)

Renkli emoji fontu çözülemediği için `🔴` glifi **tofu kutusu** olarak çiziliyor; yedek
font monokrom olduğunda kutu, rozetin renginde (kırmızı) görünür. `flow_layout` yalnızca
konumu açıklar, kareyi üretmez.

Alternatif (ikincil) aday: `ui/widgets/provider_badge.py:140-144`, metin boşsa yalnızca
`border:1px solid {color}` kalan bir QLabel üretir; `status_color` (satır 40-48) giriş
yoksa `COLOR_BAD = "#FF4D4D"` döner. Bu yolda `status_text` normalde boş dönmez, bu
yüzden ikinci sırada tutuldu.

**Ekran görüntüsü piksel düzeyinde incelenmeden ikisi arasında kesin ayrım yapılamadı.**

### Düzeltme önerisi

- Üst çubuk rozetlerinde emoji yerine metin/vektör ikon kullan
  (`🟢 HAZIR` → renkli nokta çizen küçük QWidget veya `●` U+25CF; `🔴` → `●`).
- `main.py` açılışında `QFontDatabase` ile emoji ailesi denetlenip yoksa emojiler
  otomatik olarak metin eşleniğine düşsün (tek yardımcı fonksiyon, tüm rozetler kullansın).
- `provider_badge.refresh()` boş metinde etiketi `setVisible(False)` yapsın.

**Ajan:** ui-engineer · **Risk:** düşük (kozmetik); Faz 8 üst çubuk testlerinde metin
eşleşmeleri güncellenmeli.

---

## 7. "Sohbet: 77k (+77k)" — token bileşenleri

### Kanıt — rozet biçimlendirmesi

`src/entropy/ui/widgets/token_badge.py:30-43`:

```python
sess       = bridge.session_total_tokens
turn_total = bridge.total_tokens_used
chat_part  = f"Sohbet: {_k(sess)}" + (f" (+{_k(turn_total)})" if turn_total > 0 else "")
```

`src/entropy/core/claude_bridge.py:927-929`:

```python
self.session_total_tokens += turn_total
self.session_cache_tokens += usage.get("cache_read_tokens", 0)
self.total_tokens_used = self.session_total_tokens     # <-- satır 929
```

⇒ `turn_total` her zaman `sess`'e **eşitlenir**. Rozetteki "(+son tur)" kalemi **tanım gereği
oturum toplamının kopyasıdır**; "77k (+77k)" bir tutarlılık değil, bir gösterim hatasıdır
(tek turluk oturumda ayırt edilemez, çok turlu oturumda yanıltıcıdır).

### Kanıt — 77k'nın bileşimi

`core/claude_bridge.py:245-247`: `total = input + output + cache_read + cache_write`.
Yani **önbellek okuması tam fiyatlı girdi gibi toplanıyor**.

`%USERPROFILE%\.claude\projects\C--EntropiAI-dist-EntropyAI\*.jsonl` (salt okuma, yalnızca
`usage` alanları; kişisel içerik kopyalanmadı) — 09-09 tarihli bir oturumun ardışık turları:

| tur | input | cache_creation | cache_read | output | tur toplamı |
|-----|-------|----------------|-----------|--------|-------------|
| 1 | 2 | 16.022 | 15.272 | 448 | 31.744 |
| 2 | 2 | 3.938 | 31.294 | 511 | 35.745 |
| 3 | 2 | 5.264 | 35.232 | 611 | 41.109 |
| 4 | 2 | 2.539 | 40.496 | 710 | 43.747 |

Başka bir oturumda ilk tur: `cache_creation 19.514 + cache_read 15.406` = **34.9k**.

Yorum: **ilk turun taban maliyeti ~31-35k**'dır ve bunun neredeyse tamamı Entropy'den
gelmiyor. Entropy'nin katkısı ölçüldü:

- `--append-system-prompt-file` dosyaları: `%TEMP%\entropy_claude_prompts\` — 31 dosya,
  **ortalama 2.071 bayt**, en büyüğü **4.001 bayt** (~1k token).
  Üst sınır zaten kodda sabit: `claude_bridge.py:92 SYSTEM_PROMPT_CONTEXT_LIMIT = 6000`,
  `:105 SYSTEM_PROMPT_ARGV_LIMIT = 4_000`, `:119 SYSTEM_PROMPT_FILE_FLAG`.
- argv (`claude_bridge.py:550-590`): `-p`, `--output-format stream-json`, `--verbose`,
  `--permission-mode`, `--model`, `--add-dir <proje>`, opsiyonel `--agent`,
  `--append-system-prompt-file`, `--mcp-config`. `--strict-mcp-config` **kullanılmıyor** —
  yani kullanıcının genel `~/.claude.json` MCP sunucuları da yüklenir ve araç şemaları
  bağlamı büyütür (73 araç bu yüzden).

**Sonuç:** 77k ≈ Claude Code'un kendi sistem istemi + 73 araç şeması + proje dosyaları
(`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`) + MCP araç şemaları (toplam ~31-35k taban) + turdaki
araç döngülerinin biriken `cache_read`'i. Entropy'nin doğrudan payı **~1k token (%1-2)**.

### Düzeltme önerisi

- `claude_bridge.py:929` kaldırılsın; `total_tokens_used` yalnızca **o turun** toplamını
  tutsun (rozetteki "(+…)" anlamlı hale gelir).
- Rozette `cache_read` ayrı gösterilsin ("77k · önbellek 40k") — okuma neredeyse bedavadır,
  tek toplamda gösterilmesi kullanıcıyı yanıltıyor.
- `--strict-mcp-config` bayrağı eklenip yalnızca Entropy'nin MCP yapılandırması yüklensin;
  araç sayısı ve taban bağlam belirgin şekilde düşer.
- `_apply_chat_usage` her turda `config.save_settings()` çağırıyor (satır 940-943) —
  gereksiz disk yazımı, gecikmeli/atlanabilir yapılsın.

**Ajan:** agy-integration-engineer · **Risk:** düşük; `--strict-mcp-config` kullanıcının
harici MCP araçlarını kapatır, kullanıcı onayı gerekir.

---

## 8. Arşive taşınmış "dogrulama" ofisinin raporu hâlâ Rapor Merkezi'nde

### Kanıt

`_archive` süzgeci **vardır** ve doğru çalışır — `memory/obsidian/vault_manager.py:80`:

```python
_REPORT_SCAN_SKIP_DIRS = frozenset({"_archive", "AgentDesk", ".obsidian", ".trash"})
```

Ama kasada **arşiv dışında bir kopya** duruyor:

```
Entropy/Wiki/queries/2026-09-09-dogrulama-readme-ozeti.md          <-- HÂLÂ TARANIYOR
Entropy/_archive/2026-09-09/dogrulama-canli-kosu/reports/2026-09-09-dogrulama-readme-ozeti.md
Entropy/_archive/2026-09-09/dogrulama-canli-kosu/reports/20260909-171913-readme-ozeti.md
Entropy/_archive/2026-09-09/dogrulama-canli-kosu/Tasks/20260909-171913-readme-ozeti.md
```

Ve `vault_manager.py:558-567` `get_research_reports` docstring'i açıkça yazıyor:

> "Kasadaki tüm rapor benzeri künyeleri toplar (genel, proje, yetenek, **ofis raporu ve
> wiki sorgu sayfaları dahil**)."

`report_center` / `report_inbox` **ayrı bir tarama yapmıyor**: `collect_recent_entries`
(`report_inbox.py:212-215`) doğrudan `vault.list_reports()` çağırıyor.

### Kök neden

Ofis arşivlenirken (`migrate_legacy_offices` / arşive taşıma) ofisin `reports/` ve `Tasks/`
klasörleri `_archive` altına taşınmış, ama aynı içeriğin `Entropy/Wiki/queries/` altındaki
**kopyası taşınmamış**. Wiki sorgu sayfaları rapor sayıldığı için künye ayakta kalmış.

### Düzeltme önerisi

- Arşivleme işlemi, arşivlenen ofisin ürettiği `Wiki/queries/*` sayfalarını da taşısın
  (ofis adı ön eki `<ofis>-` ile eşleştirilebilir: `2026-09-09-dogrulama-readme-ozeti`).
- Alternatif/ek: `enrich_entry`'de `office` alanı dolu olan künyeler için ofisin hâlâ
  `Desk/Offices/` altında var olup olmadığı denetlensin; yoksa künye "arşiv" sayılsın.
- `prune_missing` yalnızca silinmiş dosyaları temizliyor; "sahipsiz ofis" durumunu görmüyor.

**Ajan:** memory-rag-engineer · **Risk:** düşük; taşıma `dry_run` ile doğrulanmalı,
kullanıcının elle yazdığı wiki sayfaları taşınmamalı.

---

## Ek — 2026-09-09 günlüğündeki tekrar eden kayıtlar

| Sayı | İlk – Son | Seviye / metin |
|------|-----------|----------------|
| 176 | 00:00:08 – 00:00:10 | INFO `OpenType support missing for "Segoe UI"/"Tahoma"/"Arial"/"MS UI Gothic"/"Gulim"/"SimSun"/"Segoe UI Emoji"/"Segoe UI Symbol"` (script 10/14/20) |
| 26 | (fault log) | `Windows fatal exception: code 0x8001010d` (`main.py` → `app.exec()`) |
| 16 | 02:47:55 – 20:32:03 | INFO `Çökme günlüğü kuruldu` (= 16 uygulama başlatması) |
| 13 | 00:00:08 – 00:00:10 | WARNING `DirectWrite: CreateFontFaceFromHDC() failed` |
| 11 | 13:52:58 – 20:46:43 | CRITICAL `Yakalanmayan istisna (ana iş parçacığı)` — 2'si `knowledge_graph.refresh_graph → build_unified_graph → vault_manager.build_knowledge_graph: AttributeError: 'NoneType' object has no attribute 'strip'` (13:52, 14:13), 9'u `frameless.py:91 TypeError ... not 'Edge'` (20:32–20:46) |
| 7 | 15:33:55 – 19:57:43 | WARNING `QFileSystemWatcher: FindNextChangeNotification failed for "…" (Access is denied.)` — `Entropy/Agents/*`, `Desk/Offices/dogrulama/inbox`, `Projects/test_*/Reports` |
| 4 | 05:07:03 – 20:32:04 | INFO `Ajan derlemesi: 3 ajan, kökler=['C:\EntropiAI\dist\EntropyAI']` |
| 3 | 05:07:37 – 20:32:53 | WARNING `QFont::setPointSize: Point size <= 0 (-1)` |
| 3 | 08:59:27 – 13:49:25 | INFO `Ajan derlemesi: 5 ajan, kökler=['C:\EntropiAI\dist\EntropyAI']` |
| 3 | 17:07:41 – 20:32:04 | INFO `Eski ofisler taşındı: {'dry_run': True, 'moves': [], ...}` |
| 4 | 01:02:47 – 20:48:50 | WARNING `QTextBrowser: No document for entropy-report://…` |
| 2 | 09:56:22 – 13:49:25 | WARNING `QFileSystemWatcher::addPaths: list is empty` |
| 2 | 04:55:05 – 08:59:47 | WARNING `QDxgiVSyncService not destroyed in time` |
| 2 | 14:04:45 – 14:04:49 | WARNING `QWindowsWindow::setGeometry: Unable to set geometry 3860x2020 … AgentDeskWindowClassWindow … minimum size: 1930x647` |
| 1 | 06:11:13 | INFO `Varsayılan ofisler oluşturuldu: arastirma-ofisi` |
| 1 | 08:59:27 | INFO `Varsayılan ajanlar oluşturuldu: orkestrator, degerlendirici` |

Notlar:

- **`QTextBrowser: No document for entropy-report://…`** ayrı bir kusurdur:
  `chat_mode.py:506` yalnızca `setOpenExternalLinks(False)` çağırıyor, **`setOpenLinks(False)`
  çağrılmıyor**. QTextBrowser bağlantıyı önce kendi belgesi sanıp yüklemeye çalışıyor
  (uyarı buradan), sonra `_on_anchor_clicked` (`chat_mode.py:876`) pencereyi açıyor. Yan
  etki: sohbet görünümünün boşalması. Aynısı `zen_mode.py:482` için geçerli. → ui-engineer, risk düşük.
- **`Varsayılan ofisler oluşturuldu: arastirma-ofisi`** eski bir build'e aittir: bu günlük
  metni güncel kaynakta **artık yok** (`grep` boş) ve `agents/bootstrap.py:82-86` açıkça
  "Desk ofisleri TOHUMLANMAZ (Faz 6, kural 2)" diyor. Ancak kasada bıraktığı kalıntı
  (`Desk/Offices/Araştırma Ofisi` + `Alfa`, `Kenan`) hâlâ duruyor ve §5'teki karta kaynaklık
  ediyor. `Varsayılan ajanlar oluşturuldu: orkestrator, degerlendirici` ise **Entropy'nin
  kendi** kadrosudur (`agents/registry.py:544-561`, `Entropy/Agents`) — mimari kurala aykırı değil.
- **`QWindowsWindow::setGeometry … AgentDeskWindowClassWindow … mintrack 3886x1365`**:
  Agent Desk penceresinin minimum boyutu 3840×2160 ekranın kullanılabilir alanından büyük.
  Sabit kuralda "her iki uygulama tek ekrana sığmalı" deniyor; bu ihlal edilmiş durumda. → ui-engineer.
- 13:52 ve 14:13'teki `build_knowledge_graph` `NoneType.strip()` çökmesi eski dist build'in
  satır numaralarını taşıyor; güncel `vault_manager.py:674` civarı `get_backlinks_index`
  gövdesine denk geliyor. **Güncel kaynakta bu hatanın yaşayıp yaşamadığı doğrulanamadı**
  (dist_check ile canlı tekrar üretim gerekir).

---

## Öncelikli özet

| # | Belirti | Şiddet | Ajan | Efor |
|---|---------|--------|------|------|
| 1 | `frameless.py:91 int(Qt.Edge)` → her kenar tıklamasında istisna; sistem sürükleme + COM (0x8001010d) → donma → Windows ghost pencereleri | **Kritik** | ui-engineer | çok düşük (3 satır) |
| 2 | Rapor Merkezi ana iş parçacığında 703 raporu ×2 okuyup kümeliyor; `mark_all_read` N kez tam JSON yazıyor; Zen ve Chat ayrı `ReportInboxStore` ile yarışıyor | **Kritik** | memory-rag + ui | orta |
| 5c | Kartın `model` alanı köprüye geçmiyor; üst çubuğun modeli (`gemini-3.1-pro-high`) kullanılıyor; `project_path` exe klasörüne düşüyor | **Yüksek** | agy-integration | düşük |
| 5a/5b | Entropy ve Desk kartları aynı `Entropy/Tasks/` klasöründe; Desk orkestratörü (Alfa) Entropy kartıyla çalıştırılabiliyor — mimari kural ihlali | **Yüksek** | memory-rag + ui | orta-yüksek |
| 3 | `open_agent_file` `bus.report_created` yayıyor → `AGENT.md` "araştırma raporu" sanılıyor, yanlış "RAG'a işlendi" iddiası, grafik yeniden inşası | Orta | memory-rag | düşük-orta |
| 4 | Yetenek slash token'ı istemden temizlenmiyor → CLI "Unknown command" | Orta | agy-integration | çok düşük |
| 8 | Arşivlenen ofisin `Wiki/queries/` kopyası taşınmadığı için künye ayakta | Orta | memory-rag | düşük |
| 7 | `total_tokens_used = session_total_tokens` → "(+son tur)" anlamsız; `cache_read` tam fiyat sayılıyor; `--strict-mcp-config` yok | Orta | agy-integration | düşük |
| — | `setOpenLinks(False)` eksik → `QTextBrowser: No document for entropy-report://` | Orta | ui-engineer | çok düşük |
| 6 | Emoji fontu yok (176 `OpenType support missing`) → rozet emojisi boş kutu | Düşük | ui-engineer | düşük |
| — | Agent Desk minimum penceresi 3886×1365, ekrana sığmıyor | Düşük | ui-engineer | düşük |

## Doğrulanamayan / açık kalanlar

1. **§6** — kırmızı karenin `state_badge` emojisi mi yoksa boş metinli `ProviderStatusBadge`
   mi olduğu, ekran görüntüsü piksel düzeyinde incelenmeden ayırt edilemedi.
2. **§5b** — "Canivo Reklam" kartını hangi düğmenin/yüzeyin yazdığı; uygulamada UI eylem
   günlüğü yok, günlükte iz kalmamış. Kartın `provider`/`model`'i Alfa'nın AGENT.md'siyle
   birebir aynı, `office` alanı boş.
3. **13:52/14:13 `build_knowledge_graph` `NoneType.strip()`** — eski dist build satır
   numaraları; güncel kaynakta yaşayıp yaşamadığı canlı tekrar üretim gerektirir.
4. Bu teşhis turunda **test paketi koşulmadı ve build alınmadı** (görev salt okunur teşhis
   olarak tanımlandı); düzeltmeler geldiğinde hedefli testler + `dist_check` build'i gerekir.
