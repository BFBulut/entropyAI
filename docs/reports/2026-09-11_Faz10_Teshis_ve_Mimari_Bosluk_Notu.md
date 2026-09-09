# Faz 10 — Teşhis ve Mimari Boşluk Notu

**Tarih:** 2026-09-09 · **Kapsam:** salt okunur teşhis (kod değiştirilmedi, model çağrısı yapılmadı, çalışan uygulama kapatılmadı)
**Yöntem:** log taraması, canlı SQLite ölçümü, kaynak kodu okuması. Her bulgu kanıt (dosya:satır / sayı) ile verilmiştir.

---

## A) "Supabase'deki hatalar" — bilişsel bellek teşhisi

Kullanıcının "Supabase" dediği katman bu depoda bir bulut hizmeti değil,
`src/entropy/memory/supabase/cognitive_memory.py` içindeki **SQLite + yerel gömme (fastembed)**
bilişsel bellek modülüdür. Modül adı tarihsel bir kalıntıdır.

### A.0 Bulut Supabase yapılandırması var mı? — **YOK**

| Arama | Sonuç |
|---|---|
| `SUPABASE_URL` / `SUPABASE_KEY` / `create_client` grep (src, config) | **0 eşleşme** |
| `.env` dosyası (depo kökü) | **yok** |
| `supabase.co` geçen tek yer | `src/entropy/mcp/manager.py:353` — MCP sunucu **kataloğunda** bir katalog satırı (`https://mcp.supabase.com/mcp`), bağlantı kurulmuyor |

→ **Bağlantı hatası olasılığı elenmiştir.** Kullanıcının gördüğü "Supabase hataları" bulut kaynaklı olamaz;
yerel bellek katmanının davranışıdır. Aşağıdaki altı bulgu bunun karşılığıdır.

### A.1 Loglarda bellek kaynaklı hata **yok**; loglardaki gerçek çökme başka yerde

`.entropy/logs/entropy.log` (363 satır, 2026-09-07 07:16 → 2026-09-09 22:53) ve
`entropy_fault.log` (425 satır) üzerinde anahtar kelime sayımı:

| Anahtar | entropy.log | entropy_fault.log |
|---|---|---|
| `supabase`, `cognitive_memory`, `fastembed`, `embedding`, `recall`, `dream`, `consolidat` | **0** (hepsi) | **0** (hepsi) |
| `Traceback` | 11 | 0 |
| `ERROR` | 24 | 0 |
| `WARNING` | 71 | 0 |

Yani bellek katmanı loga **hiç** yazmıyor — ne hata ne bilgi. Bu başlı başına bir bulgudur (A.4).

Loglardaki 11 traceback iki kök nedene iniyor:

1. **9 kez** `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'Edge'`
   — `entropy\ui\widgets\frameless.py`, `eventFilter`, satır 91.
   İlk: 2026-09-09 20:32:34 · Son: 2026-09-09 20:46:43. `CRITICAL entropy.crash` seviyesinde.
   **Kök neden:** `Qt.Edge` PySide6 6.7+'ta `enum.Flag` (IntFlag değil), `int(edges)` patlıyor.
   **Durum:** kaynakta **düzeltilmiş** — `src/entropy/ui/widgets/frameless.py:96-104` artık
   `eventFilter`'ı `try/except` ile sarmalıyor ve `_is_empty_edges()` (`:32-34`) yardımcı işlevi var.
   Log satırları `dist/EntropyAI/EntropyAI.exe` (derleme tarihi **2026-09-09 22:42**) öncesindeki
   eski derlemeden geliyor. → **Regresyon değil, eski ikili.** Doğrulama: yeni derlemeyle 20:32-20:46
   aralığındaki senaryo (pencere kenarından boyutlandırma) tekrarlanmalı.

2. **2 kez** `AttributeError: 'NoneType' object has no attribute 'strip'`
   — `knowledge_graph.py:2916 refresh_graph` → `:2642 build_unified_graph` →
   `entropy\memory\obsidian\vault_manager.py:674 build_knowledge_graph`.
   İlk: 2026-09-09 14:04 · Son: 2026-09-09 15:33.
   Kaynakta `build_knowledge_graph` şu an `vault_manager.py:903`'te; satır numaraları eski ikiliye ait.
   **Kök neden adayı:** not girdisinde `title`/`body` alanının `None` gelmesi (önbellekten okunan
   `entries` sözlüğünde eksik alan). **Doğrulanamadı** — güncel kaynakta aynı yolun hâlâ kırılgan olup
   olmadığı hedefli bir testle ölçülmeli.
   **Öneri:** `ui-engineer` + `memory-rag-engineer`; kabul: boş/`None` başlıklı bir kasa notuyla
   `build_knowledge_graph` çağrısı istisna atmadan dönüyor.

**Ek gözlem (kanıt):** `%LOCALAPPDATA%\CrashDumps` içinde `EntropyAgentDesk.exe.72280.dmp` (2026-09-08 06:50)
ve üç `python.exe` dökümü var. `python.exe` dökümleri pytest koşularıyla karışır; uygulama çökmesi
sayılmamalıdır. Desk dökümü 2026-09-08 tarihli, mevcut derlemeden eski.

### A.2 Veritabanı sağlığı — **temiz**, ama iki depo birbirinden ayrışmış

Ölçüm: `C:\Users\batu_\.entropy\cognitive_memory.db` (16.977.920 bayt, son değişiklik 2026-09-09 22:38).
Yol koddan doğrulandı: `cognitive_memory.py:308-311` → `Path.home() / ".entropy" / "cognitive_memory.db"`.

```
PRAGMA integrity_check → ok
```

| Tablo | Satır |
|---|---|
| `cognitive_nodes` (eski/birincil depo) | **1404** |
| `nodes` (graf katmanı) | **1384** |
| `edges` | **1846** |
| `communities` | **89** |

Sağlık göstergeleri:

- **NULL/boş `embedding_json`: 0 / 1404.** Gömme kaybı yok.
- **Gömme modeli tekil:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` → 1404/1404. Karışık model yok.
- **Yetim kenar: 0** (`src` için 0, `dst` için 0). **Üyesiz topluluk: 0.**
- Kategori dağılımı: `semantic` 1167, `procedural` 134, `query` 64, `episodic` 11, `architecture` 8,
  `office` 7, `agent` 2, `ego` 2, diğer 4.
- Graf düğüm tipleri: `fact` 733, `report` 403, `procedure` 134, `community` 89, `episode` 10,
  `office` 7, `entity` 4, `agent` 2, `session` 1, `task` 1.
- Kenar tipleri: `similar_to` 953, `member_of` 873, `derived_from` 20.
- İlk yazım 2026-09-03 02:04:50 · **son yazım 2026-09-09 19:35:33** · son erişim 19:38:41.

**Kritik bulgu — çift depo senkronsuzluğu (P0):**

```
cognitive_nodes'ta var, graf nodes'ta YOK : 22 satır
graf nodes'ta var, cognitive_nodes'ta YOK :  2 satır (type=entity, türetilmiş, normal)
```

22 eksik satırın kategorisi: `query` 21, `semantic` 1.
Zaman aralığı **2026-09-09 10:52:50 → 18:39:58** — yani graf geçişinden (`cognitive_memory.db.pre_graph.bak`,
2026-09-09 09:40) **sonra** yazılmışlar. Legacy kalıntı değil, **canlı sapma**.

**Kök neden (kanıtlı):**
- Yazma yolu `CognitiveMemorySystem.record_memory` (`cognitive_memory.py:551-590`) → `_save_node` (`:477`)
  **yalnızca `cognitive_nodes` tablosuna** yazar. `store_node` (`:895-903`) bunun takma adıdır.
- Graf tabloları (`nodes`/`edges`/`communities`) yalnızca
  `GraphStore.migrate_from_cognitive_nodes` (`src/entropy/memory/graph_store.py:519`) ile dolar.
- **Bu işlev üretim kodunda hiç çağrılmıyor.** Grep sonucu: yalnızca
  `tests/test_graph_store_and_reconcile.py:93,125,126,236`.

→ Graf katmanı bir kez elle doldurulmuş, o günden beri **her yeni anı grafın dışında kalıyor**.
Wiki sorgu düğümleri (`src/entropy/memory/wiki.py:387`, `category="query"`) bunun en görünür kurbanı: 64
`query` düğümünün 21'i grafta yok.

**Düzeltme önerisi:** `record_memory` başarıyla yeni düğüm yazdığında graf katmanına da tek düğümlük
upsert yapmalı (`GraphStore.upsert_node`, `graph_store.py:266`), ya da uygulama açılışında/rüya
görevinde artımlı bir senkron adımı koşmalı.
**Kabul ölçütü:** üretim yolundan 5 yeni anı yazıldıktan sonra
`select count(*) from cognitive_nodes x left join nodes n on x.id=n.id where n.id is null` = 0.
**Ajan:** `memory-rag-engineer`.

**İkincil kanıt:** `memory_inspector_dialog.py:494-499` düğüm silerken **yalnızca**
`DELETE FROM cognitive_nodes` yapıyor; `nodes`/`edges` satırları yerinde kalıyor → silme de tek yönlü.

### A.3 Depo içindeki artık veritabanı (P2)

`src/entropy/memory/supabase/cognitive_memory.db` — **0 bayt değil**: 339.968 bayt, tek tablo
`cognitive_nodes`, **43 satır**, son değişiklik 2026-09-06 16:36.

- Git'te izlenmiyor (`git ls-files --error-unmatch` → "Did you forget to 'git add'?").
- `EntropyAI.spec` `datas` listesinde bu `.db` yok (`.spec:13`, `:190`); yalnızca
  `entropy.memory.supabase.cognitive_memory` **modülü** gizli içe aktarma olarak listeli (`:141`).
- Varsayılan yol her zaman `Path.home()/.entropy/` olduğu için (`cognitive_memory.py:308-311`)
  bu dosya **hiçbir zaman okunmuyor**.

**Kök neden:** eski bir çalıştırmada `db_path` göreli verilmiş.
**Düzeltme:** dosyayı sil, `.gitignore`'a `*.db` ekle.
**Kabul:** depoda `src/**/*.db` = 0 dosya; testler geçmeye devam ediyor. **Ajan:** `qa-build-engineer`.

### A.4 Sessizce yutulan istisnalar — hangi işlevler gürültüsüz başarısız oluyor

`cognitive_memory.py` içinde 13 `except Exception` bloğu var; **8'i `pass`/`continue` ile tamamen sessiz**.
Hiçbiri `logger`'a yazmıyor — bu yüzden A.1'de bellek katmanı loglarda görünmüyor.

| Satır | İşlev | Yutulan durumda ne kaybedilir |
|---|---|---|
| `:22` | modül düzeyi | numpy yoksa `_np = None` — vektörleştirilmiş geri çağırma sessizce kapanır, yavaş yola düşer |
| `:105` | `LocalEmbeddingEngine.__init__` | gömme sağlayıcısı yüklenemezse `continue` → bir sonraki adaya geçer, hiç uyarı yok |
| `:129` | `embed_text` | **gömme üretimi başarısız → `vector = None`.** Düğüm gömmesiz yazılabilir; anlamsal geri çağırma o düğüm için kalıcı olarak ölür |
| `:193` | `_run` (ısıtma) | ısıtma çökerse ilk çağrı ~1,9 sn bloklar; kullanıcı "donma" görür, log boş |
| `:327` | `CognitiveMemorySystem.__init__` → `warm_embedding_engine()` | aynı, `pass` |
| `:390` | `reembed_stale` | model değişince yeniden gömme başına başarısızlık `continue` ile atlanır; sayaç doğru görünür |
| `:609` | `hybrid_recall` | **indeksli yol çökerse sessizce skaler yola düşülür.** Kullanıcı yavaşlığı görür, nedenini asla göremez |
| `:744` | `_build_recall_index` | indeks kurulumu kısmen başarısız → eksik indeksle arama |
| `:889` | `_hybrid_recall_scalar` | tek düğümün skorlaması patlarsa o düğüm **sessizce sonuçlardan düşer** |
| `:973`, `:984`, `:997` | `dream_and_consolidate` | konsolidasyonun üç ayrı adımı sessizce atlanabilir; işlev yine "başarılı" döner |
| `:1016` | `purge_placeholder_consolidations` | temizlik sessizce yapılmaz |

**En riskli üçlü:** `:129` (gömmesiz düğüm), `:609` (geri çağırma yolunun sessiz düşüşü),
`:973/:984/:997` (rüya döngüsünün sessiz kısmi başarısızlığı). Bu üçü kullanıcının
"hafızam çalışmıyor ama hata da görmüyorum" şikâyetinin doğrudan mekanizmasıdır.

**Düzeltme önerisi:** her blok en az `logger.warning(..., exc_info=True)` yazmalı; `:129` ve `:973-997`
ayrıca bir sayaç döndürmeli (`{"failed": n}`) ki üst katman kısmi başarıyı ayırt edebilsin.
**Kabul:** yapay olarak bozulmuş gömme motoruyla bir anı yazıldığında `entropy.log`'da tam olarak
1 WARNING satırı beliriyor ve `record_memory` `embedding=None` döndürdüğünü çağırana bildiriyor.
**Ajan:** `memory-rag-engineer`.

**Bağlantılı bulgu (P1):** `reembed_stale` (`cognitive_memory.py:363`) **üretim kodunda hiç çağrılmıyor**
(grep: yalnızca tanımı). Gömme modeli değiştiğinde eski düğümler sonsuza dek eski uzayda kalır.
Bugün risk düşük (1404/1404 tek model), ama model yükseltmesinde sessiz bir bellek kaybına dönüşür.

### A.5 "Bilişsel Bellek 105" sayacı ile "7 kayıt" farkı — üç ayrı sayı, üç ayrı kaynak

Uygulamada bilişsel bellek üç farklı yerde, **üç farklı tanımla** sayılıyor:

| Yüzey | Kaynak | Ne sayar | Bugünkü değer |
|---|---|---|---|
| Zen telemetri rozeti | `ui/modes/zen_mode.py:742` → `mem.get_all_nodes()` | `cognitive_nodes` tamamı | **1404** |
| Bilgi grafı efsanesi ("Bilişsel Bellek N") | `ui/widgets/knowledge_graph.py:3677` | `SELECT ... FROM cognitive_nodes ORDER BY created_at DESC **LIMIT 80**` + alt dal/hub düğümleri | ~**100-110** (kullanıcının gördüğü **105** buradan) |
| Sohbette "hatırlanan kayıt" | `memory/context_builder.py:388` → `hybrid_recall(query, top_k=12)` | ilgi sıralı ilk 12, sonra bütçe kırpması | **≤12, tipik 5-8** |

**"105" nereden geliyor:** graf oluşturucu belleğin tamamını değil **son 80 düğümü** çekiyor
(`knowledge_graph.py:3677`); üstüne hub + alt dal + topluluk düğümleri eklenince efsane sayacı
`nodes.forEach(n => counts.set(n.group, ...))` ile (`knowledge_graph.py:1420-1423`) 105 civarı bir
sayı gösteriyor. Yani **105 bir bellek büyüklüğü değil, bir çizim kotasıdır.**

**"7 kayıt" nereden geliyor:** `_recall_section` (`context_builder.py:387-415`) `top_k=12` ile çağırıyor,
ardından `BUDGET_RECALL = 800` token bütçesi (`context_builder.py:43`) dolunca döngü `break` ile kesiliyor
(`:402-403`). Uzun anılarda 800 token 6-8 maddeye denk gelir → kullanıcının gördüğü "7 kayıt".
`hybrid_recall`'ın kendi varsayılan eşiği `min_threshold=0.15` (`cognitive_memory.py:596`) burada
**belirleyici değil**, çünkü `context_builder` eşiği geçmiyor ve 12 aday zaten eşiği geçmiş oluyor.

→ **Cevap:** fark bir geri çağırma eşiği sorunu değil, **bağlam kurucu bütçesidir** (800 token),
ikincil olarak da grafın 80 satırlık çizim kotasıdır. Veri kaybı yok.

**Düzeltme önerisi (P1, ucuz):**
1. Rozet/efsane etiketleri "gösterilen/toplam" biçiminde olsun (`105 / 1404`), böylece kullanıcı
   kotayı bellek büyüklüğü sanmasın. Kabul: efsanede iki sayı görünüyor ve toplam `get_all_nodes()`'tan geliyor.
2. `BUDGET_RECALL` ve `top_k` tek yerden ayarlanabilir olsun; "hatırlanan N/M" satırı bölüm başlığına yazılsın
   (`context_builder.py:410` başlığı `"Hatırlanan İlgili Bilgiler"` → `"... (N/M)"`).
   Kabul: 12 aday, 7 sığdırıldı senaryosunda başlıkta `7/12` görünüyor.
**Ajan:** 1 → `ui-engineer`, 2 → `memory-rag-engineer`.

### A.6 Rüya/konsolidasyon döngüsünün tetiklenmesi

`dream_and_consolidate` iki yerden çağrılıyor: `main.py:157` (yalnızca zamanlanmış `daily-dreaming`
görevi geldiğinde) ve `ui/widgets/tasks_widget.py:425` (elle). Yani konsolidasyon **zamanlayıcıya bağlı**;
zamanlayıcı görevi yoksa bellek hiç konsolide olmaz. `~/.entropy/scheduler_tasks.json` mevcut (4157 bayt)
ama içeriğinde `daily-dreaming` kaydının varlığı **doğrulanmadı** (salt okunur kapsamda açılmadı — bu
kullanıcı durum dosyasıdır, teste bağlanmamalıdır).
**Öneri:** açılışta görev yoksa oluşturan bir idempotent kayıt; kabul: temiz profilde ilk açılıştan
sonra zamanlayıcıda tam 1 adet `daily-dreaming` var. **Ajan:** `memory-rag-engineer`.

### A. Özet tablo

| # | Bulgu | Öncelik | Ajan |
|---|---|---|---|
| A.2 | Graf katmanı canlı yazımlarla senkronize değil (22 düğüm dışarıda); `migrate_from_cognitive_nodes` yalnızca testlerden çağrılıyor | **P0** | memory-rag |
| A.4 | 8 sessiz `except` + `reembed_stale` hiç çağrılmıyor → bellek hataları görünmez | **P0** | memory-rag |
| A.5 | "105" bir çizim kotası, "7" bir token bütçesi; etiketler yanıltıcı | **P1** | ui + memory-rag |
| A.1-2 | `vault_manager.build_knowledge_graph` `None.strip()` — güncel kaynakta doğrulanmadı | **P1** | ui + memory-rag |
| A.6 | Konsolidasyon yalnızca zamanlayıcı görevi varsa koşuyor | **P1** | memory-rag |
| A.3 | Depoda 43 satırlık artık `.db` | **P2** | qa-build |
| A.1-1 | `frameless.py` `Qt.Edge` çökmesi — **kaynakta düzeltilmiş**, log eski ikiliden | kapandı | — |
| A.0 | Bulut Supabase yapılandırması yok | bilgi | — |

---

## B) Desk mimari boşluk denetimi

Kullanıcının tarif ettiği çekirdek mantık altı başlıkta karşılaştırıldı.

### B.1 Dosya tabanlı ortak çalışma belleği — **YARIM**

**Var olan:**
- Ofis künyesi `OFFICE.md` (`agents/desk_registry.py:51`), bellek `MEMORY.md` (`:58`),
  proje tüzüğü `projects/<proje>/PROJECT.md` (`:54`, `:119`).
- Orkestratörün plan istemi bu üçünü **gerçekten okuyor**: `harness.build_plan_prompt`
  (`agents/harness.py:713-798`) `[OFİS TÜZÜĞÜ]`, `[PROJE]`, `[BİLGİ TAZELEME]` (ofis belleği +
  son raporlar, `:746-758`) ve posta kutusu bloklarını üretiyor.

**Eksik olan (P0):**
- **Alt kart (işçi) istemi bunların hiçbirini görmüyor.** `TaskBoard.build_prompt`
  (`agents/tasks.py:808-839`) yalnızca dört parça üretiyor: ajan gövdesi, görev sözleşmesi +
  kabul ölçütleri, proje dosya listesi, kart `notes`. Ne `MEMORY.md`, ne ofis belleği, ne pano
  durumu, ne mimari dosyası. `ContextBuilder`'ın `_agent_memory_section` / `_office_memory_section`
  bölümleri (`memory/context_builder.py:648`, `:671`) **kart yolunda hiç kullanılmıyor** —
  `tasks.py` içinde `context_builder` içe aktarımı yok.
- **"Doğduğunda önce BOARD ve ARCHITECTURE oku" talimatı hiç yok.** Grep: `BOARD.md` → 0 eşleşme,
  `ARCHITECTURE` → 0 eşleşme (yalnızca `bilişsel bellek mimarisi` gibi Türkçe metinler).

**Kabul ölçütü önerisi:** ofis kökünde `BOARD.md` (kart durum tablosu, harness her `_save_card_state`
sonrası yazar) ve `ARCHITECTURE.md` (proje başına, orkestratör yazar) üretiliyor; `build_prompt`
her alt karta bu ikisinin özetini + `MEMORY.md`'yi bütçeli olarak enjekte ediyor; iki alt kart aynı
BOARD sürümünü görüyor. **Ajan:** `agy-integration-engineer` (istem) + `memory-rag-engineer` (bütçeli özet).

### B.2 Kontrol noktası disiplini — **VAR (kısmen)**

- `state.json` (`harness.py:65 STATE_FILENAME`), kart başına birleştirmeli atomik yazım
  `_save_card_state` (`:302-317`), okuma `_card_state` (`:299`).
- `resume_all` (`harness.py:1365-1400`): `running` kalan alt kartları `backlog`a çekip pompayı
  yeniden döndürüyor; planlaması yarım kartı baştan planlıyor. Açılışta `main.py:145` çağırıyor.
- Kart `notes` ve `summary` alanları diske yazılıyor (`tasks.py:1012`, `_finish`).

**Eksik:** sürdürme **kartın son özetinden değil, kartın baştan koşmasından** ilerliyor —
yarım kalan bir alt kart tamamen yeniden başlıyor, ara özet girdiye dönmüyor.
Alt kart modül bitirdiğinde ara kontrol noktası yazan bir kanca yok.
**Kabul:** yarıda kesilen bir alt kart yeniden başlatıldığında isteminde `[ÖNCEKİ DENEME ÖZETİ]`
bloğu bulunuyor ve token maliyeti ilk denemenin altında kalıyor. **Öncelik:** P1. **Ajan:** `agy-integration-engineer`.

### B.3 Onaylı kalıcı kurallar — **YOK (altyapısı var)**

**Var olan parçalar:**
- `memory/agent_memory.py`: `append_agent_memory` (`:234`), `append_office_memory` (`:245`),
  `consolidate_agent_memory` (`:334`), `consolidate_office_memory` (`:344`) — model çağrısız,
  `MEMORY_MAX_CHARS = 6000` (`:39`), yükleme `load_agent_memory` (`:395`) / `load_office_memory` (`:405`).
- Harness kart bitince ofis/ajan belleğine yazıyor (`harness.py:1330`, `:1340-1344`;
  `tasks.py:1059-1067`).
- `memory/office_graph.py` düğüm bağlantılı ofis belleği (`OfficeGraph`, `:160`;
  `orchestrator_context`, `:532`) — pinned bellek kuralına uygun graf yapısı **var**.
- `memory/distiller.py` mevcut.

**Eksik olan (P0):** "ajan bir kural keşfetti → kullanıcı **kalıcı yap** dedi → sistem istemine enjekte
edildi" akışının **hiçbir adımı yok**. Grep: `promote`/`promoted`/`kalıcı yap`/`permanent_rule`/`pinned_rule`
üretim kodunda **0 eşleşme** (yalnızca `src/entropy/tools/autonomous_agent_architecture*.py` içindeki
araştırma/prototip dosyalarında geçiyor; bunlar çalışma yoluna bağlı değil).
Bugün ajan belleği **otomatik** birikiyor, kullanıcı onayı yok, ve alt kart isteminde
kullanılmıyor (bkz. B.1).

**Kabul ölçütü önerisi:** kart raporundaki bir maddeye "Kalıcı kural yap" düğmesi → kural
`MEMORY.md`'nin `## Kalıcı Kurallar` bölümüne `pinned: true` ile yazılıyor → bu bölüm
`build_prompt`'ta **kırpılmadan** her alt karta giriyor; ajan yeniden derlendiğinde de kayboluyor mu
diye test var. **Ajan:** `memory-rag-engineer` (depo) + `ui-engineer` (onay yüzeyi).

### B.4 Görünmez terminaller + köprü + durum eşleme — **YARIM**

| Alt madde | Durum | Kanıt |
|---|---|---|
| Ajan başına alt süreç | **kart başına** var, ajan başına **sürekli** yok | `tasks.py:841-940` her kart için köprüye `send_background_task_async`; süreç kart bitince ölür |
| stdout ayrıştırma → akış | **sağlayıcıya göre asimetrik (P0)** | `claude_bridge.py:1070` `bus.token_chunk_received.emit` `consume_stream` içinde (`:999`), arka plan işçisi (`:1776` → `:1920`) onu kullanıyor → **Claude kartları akıyor**. agy'de `token_chunk_received` emisyonları **yalnızca** `_execute_prompt_worker` (`agy_bridge.py:1241`) içinde: `:1696`, `:1712`, `:1761`. Arka plan işçisi `_execute_background_task_worker` (`:744-1240`) yalnızca `terminal_output_received` yayıyor (`:795, :811, :821, :960, :972-1009`) → **agy kartları akmıyor** |
| Ajan başına etiketleme | **YOK** | `desk/stream_panel.py:4-10` yorumu bunu açıkça kabul ediyor: "köprü akışı ajan başına etiketlemiyor (tek `token_chunk_received` var)"; tek `_buffer` alanı (`:39`) |
| Durum makinesi | **VAR** | `desk/scene.py:50-56`: `idle, thinking, working, error, waiting, reading`; etiketler `:61-68`; aşama eşlemesi `STAGE_TO_STATE` `:96-118`; araç adına göre "okuyor" sezgisi `:121` (`READ_TOOL_HINTS`) |
| Konuşma balonu | **VAR** | `scene.py:89-94` `STATE_BUBBLE`: `thinking → "…"`, `waiting → "⏳"`, `error → "!"` |
| "Dosya yazıyor: masada tuşlama" | **VAR** | `STATE_ANIMATION` `:80-87`: `working → ANIM_TYPE`, `reading → ANIM_READ` |
| "Boşta: volta/kahve" | **YARIM** | `ANIM_WALK` var (`scene.py:649`, `WALK_SPEED_PX_PER_SEC = 48.0` `:133`) ama `STATE_IDLE → ANIM_IDLE` (`:81`); **kahve animasyonu yok**, boşta volta ayrı bir yürüme durumuna bağlı |
| Sprite'a tıkla → terminal bölmesi | **VAR ama tek bölme** | `desk/window.py:280` `scene.agent_clicked` → `:480-482` `stream_panel.focus_agent(agent)`; panel tek akış tamponu tuttuğu için iki ajan paralel koşarken metinler karışır |

**Kabul ölçütü önerisi:** agy arka plan yolu da akış yayıyor; akış olayı ajan kimliği taşıyor;
`StreamPanel` ajan başına ayrı tampon tutuyor; iki alt kart paralel koşarken iki sekmenin metni karışmıyor.
**Ajan:** `agy-integration-engineer` (köprü) + `ui-engineer` (panel).

### B.5 Orkestrasyon ve **kanıtla kapatma** — **YARIM; kanıt zorunluluğu YOK (P0)**

**Var olan:**
- Lider kod yazmıyor: plan isteminde açık yasak — *"Sen kod YAZMAZSIN, dosya değiştirmezsin:
  yalnızca plan üretirsin"* (`harness.py:786-787`), ayrıca kod tespiti için
  `orchestrator_produced_code()` (`harness.py:182`).
- Panoya bölme: en çok `MAX_SUBTASKS` alt görev, JSON şeması (`harness.py:785-798`).
- Paralellik: `limit = int(office.max_parallel or 1)` (`harness.py:989`), tek seferde artırma
  yarışını önleyen not (`:976`).
- Yazma kilidi: `card_needs_write` (`tasks.py:903`) → okuma niyetli kart **paylaşımlı** kilitle
  koşuyor (`tasks.py:925-928`), böylece ikinci kart 60 sn'de ölmüyor.
- Değerlendirme: `build_eval_prompt` (`harness.py:1101-1123`) alt kart başına 0-1 not, `verdict`,
  `missing`; eşik altındakiler bir kez yeniden koşuyor (`_on_grades`, `:1150-1164`,
  `GRADE_THRESHOLD`, `MAX_ATTEMPTS`).
- İşçi istemi kanıt istiyor: *"Ölçütlerin her birini tek tek ele al ve karşılandığını **kanıtıyla**
  göster. Yapamadığın maddeyi 'yapılamadı' diye açıkça yaz"* (`tasks.py:826-828`).

**Eksik olan:** **"test koşulmadan bitti denemez" kuralının makine tarafında hiçbir yaptırımı yok.**
- Değerlendirici istemi (`harness.py:1101-1123`) yalnızca metin özetini görüyor
  (`trim_to_sections(summary, EVAL_SUMMARY_CHARS)`); test çıktısı, çıkış kodu, diff gibi
  **doğrulanabilir hiçbir yapı yok**.
- Alt kartta `tests_command` / `evidence` gibi bir alan yok (`agents/tasks.py` `TaskCard` alanları:
  `:130` civarı `project`, `notes`, `criteria`, `grade`, `verdict`).
- Yani bir alt kart "testleri geçti" **yazarsa** not alır; koşup koşmadığı ölçülmez.

**Kabul ölçütü önerisi:** `TaskCard`'a `verify_command` alanı; kart kapanmadan önce harness komutu
koşup çıkış kodunu + son 40 satırı karta yazıyor; `build_eval_prompt` bu bloğu içeriyor;
çıkış kodu ≠ 0 olan kart `grade` ne olursa olsun `done` olamıyor.
Test: sahte bir `exit 1` komutuyla kart `failed` kalıyor. **Öncelik:** P0. **Ajan:** `agy-integration-engineer` + `qa-build-engineer`.

### B.6 Ajan başına kimlik — **VAR (avatar zayıf)**

- Ad/rol/açıklama/yetenekler `AgentSpec` üzerinden geliyor; plan istemi kadroyu
  `"- {ad} ({rol}) · {açıklama} · yetenekler: {...}"` biçiminde basıyor (`harness.py:717-721`).
- Roller sabit: `ROLE_ORCHESTRATOR`, `ROLE_EVALUATOR`, `ROLE_WORKER` (`scene.py:113-115`).
- Sprite: `desk/assets/characters` + `CharacterLibrary` (`scene.py:227`); karakter seçimi
  **addan türetilmiş deterministik indeks** — `character_index_for(agent, sheet_count)`
  (`scene.py:328-335`). Yani her ajanın tutarlı bir görünümü var **ama kullanıcı seçemiyor**;
  `desk_registry.py`'de `avatar` alanı yok (grep: 0 eşleşme).
- Sürekli terminal: **yok** (B.4).
- Rol atama yüzeyi var: `desk/roster_panel.py:61-62` `assign_role`.

**Öneri (P2):** `AgentSpec`'e isteğe bağlı `avatar` (karakter sayfası indeksi) alanı; boşsa
bugünkü deterministik türetme. Kabul: künyeye `avatar: 3` yazılan ajan sahnede 3 numaralı sayfayla
çiziliyor, boş bırakılan ajan bugünküyle aynı kalıyor. **Ajan:** `ui-engineer`.

### B. Boşluk tablosu

| # | Boşluk | Durum | Öncelik | Ajan | Kabul ölçütü |
|---|---|---|---|---|---|
| B.5 | Kanıtla kapatma yok: test koşumu ölçülmüyor | yok | **P0** | agy + qa | `verify_command` çıkış kodu ≠ 0 → kart `done` olamıyor |
| B.1 | Alt kart istemi ofis belleğini/panoyu/mimariyi görmüyor; `BOARD.md`/`ARCHITECTURE.md` yok | yarım | **P0** | agy + memory-rag | İki alt kart aynı `BOARD.md` sürümünü isteminde görüyor |
| B.3 | Onaylı kalıcı kural yolu yok (`promote` grep = 0) | yok | **P0** | memory-rag + ui | "Kalıcı yap" → `MEMORY.md`/`## Kalıcı Kurallar` → her alt kart isteminde kırpılmadan |
| B.4 | agy kart yolu akış yaymıyor; akış ajan başına etiketli değil | yarım | **P0** | agy + ui | 2 paralel kart, 2 ayrı tampon, karışma yok; agy kartında metin görünüyor |
| B.2 | Sürdürme özetten değil baştan | var/kısmi | P1 | agy | Yeniden başlatılan kart isteminde `[ÖNCEKİ DENEME ÖZETİ]` var |
| B.4b | Boşta volta/kahve animasyonu; `idle → ANIM_IDLE` sabit | yarım | P2 | ui | Boşta ajan periyodik volta atıyor, en az bir "mola" pozu var |
| B.6 | `avatar` alanı yok | var/kısmi | P2 | ui | Künyedeki `avatar` sahneye yansıyor, boşsa davranış değişmiyor |

### Mimari kural denetimi (pinned kurallara karşı) — **UYUMLU**

- Ayrı kök: `Entropy/Desk/Offices/<ofis>/agents` (`memory/office_graph.py:101-105`,
  `desk_registry.py:10-13`); eski kök ayrı (`legacy_offices_dir`, `office_graph.py:109`).
- Entropy kadrosu ile ofis kadrosu karışmıyor: `tasks.py:875-889` ofis orkestratörünün adı bir
  Entropy kartına yazılırsa kart **açıkça başarısız** oluyor (sessiz düşüş kapatılmış).
- Orkestratör kod yazmıyor: `harness.py:786-787` yasak + `orchestrator_produced_code` (`:182`) denetimi.
- Orkestratör istemlerinde ürünün adı geçmiyor: `build_plan_prompt` (`:780-798`) yalnızca ofis tüzüğü,
  proje, kadro ve şema içeriyor. **Uygun.**
- Ofis belleği düğüm bağlantılı: `OfficeGraph` (`office_graph.py:160`), Desk "Bellek" sekmesi
  mini grafı çiziyor (`desk/memory_panel.py:1-10`, `compute_positions` `:71`).

---

## C) Faz 10 araştırma notundaki 10 maddeyle çakışma/örtüşme haritası

Karşılaştırma kaynağı: `docs/reports/2026-09-11_Faz10_Arastirma_Notu.md` (§0 karar tablosu, satır 22-32).

| Faz 10 maddesi | Bu nottaki karşılığı | İlişki |
|---|---|---|
| **10.1** Köprü akışına ajan etiketi | **B.4** (agy arka plan yolu akış yaymıyor; tek tampon) | **Tam örtüşme.** Bu notun ölçümü 10.1'in kanıtını bağımsız doğruluyor: agy emisyonları yalnızca `agy_bridge.py:1241` sonrası prompt yolunda (`:1696, :1712, :1761`), arka plan işçisi (`:744-1240`) yalnızca `terminal_output_received`. Yeni iş yok |
| **10.2** Ajan başına adlandırılmış terminal | **B.4** (ajan başına sürekli süreç yok; sprite tıklaması tek bölmeye gidiyor, `window.py:480-482`) | **Örtüşme.** 10.2(a) "akış terminali" kararı bu bulguyu karşılıyor |
| **10.3** Proje = depo + dal | B.1'in `PROJECT.md` yüzeyini genişletiyor | Komşu, çakışma yok |
| **10.4** Kart başına worktree | **B.5** paralellik/yazma kilidi (`tasks.py:925-928`) | Komşu. Worktree gelirse paylaşımlı kilit mantığı yeniden gözden geçirilmeli — **riskli kesişim** |
| **10.5** PR akışı | — | Kesişim yok |
| **10.6** Diff paneli | **B.5 kanıtla kapatma** ile aynı veri kaynağını (`git diff --numstat`) kullanır | **Sinerji:** diff özeti, `verify_command` çıktısıyla birlikte değerlendirici istemine girebilir. Tek uygulamada iki madde kapanır |
| **10.7** Maliyet/kota şeridi | B.2 `_card_state` token alanları | Komşu, çakışma yok |
| **10.8** Orkestratör gerçek araştırma | **B.1** bilgi tazeleme bloğu (`harness.py:746-758`, `_can_web_search` `:661-672`) | **Kısmi örtüşme.** 10.8 planlama tarafını düzeltiyor; B.1'in asıl boşluğu (**işçi** istemi) 10.8 kapsamında **değil** → yeni madde gerekli |
| **10.9** Makbuz + koşan karta yorum | **B.1** (`BOARD.md`) ve **B.5** (kanıt bölümü) | **Güçlü örtüşme.** Notun §2.9'daki makbuz iskeleti (`## Plan / İlerleme / Değerlendirme / Değişiklikler / PR / Maliyet / Yorumlar`) `BOARD.md` ihtiyacının çoğunu karşılıyor; eksik başlık: **`## Kanıt` (test komutu + çıkış kodu)** |
| **10.10** Ekip şablonları | **B.3** kalıcı kurallar (şablon = doğuştan kural) | Komşu; kalıcı kural yolu şablonlardan **bağımsız** olarak gerekli |
| **10.11** QA + derleme | Tüm A ve B maddelerinin doğrulaması | Kapsayıcı |

### Faz 10 iş listesine **eklenmesi önerilen** yeni maddeler

Araştırma notunun 10 maddesinde karşılığı olmayanlar:

| Yeni # | İş | Kabul ölçütü | Ajan | Öncelik |
|---|---|---|---|---|
| 10.12 | Bilişsel bellek çift depo senkronu (A.2) | Üretim yolundan 5 anı yazıldıktan sonra `cognitive_nodes` ∖ `nodes` = 0; silme her iki tabloyu da temizliyor | memory-rag | P0 |
| 10.13 | Sessiz istisnaların loglanması + `reembed_stale` tetiklenmesi (A.4) | Bozuk gömme motoruyla 1 WARNING satırı; model değişiminde eski düğümler yeniden gömülüyor | memory-rag | P0 |
| 10.14 | **Kanıtla kapatma**: `verify_command` + çıkış kodu + değerlendirici istemine kanıt bloğu (B.5) | `exit 1` veren kart `grade` ne olursa olsun `failed`; 10.9 makbuzunda `## Kanıt` başlığı doluyor | agy + qa | P0 |
| 10.15 | İşçi istemine ortak çalışma belleği: `BOARD.md`/`ARCHITECTURE.md` + `MEMORY.md` enjeksiyonu (B.1) | İki alt kart aynı BOARD sürümünü görüyor; bütçe aşımı yok (token ölçümü rapora giriyor) | agy + memory-rag | P0 |
| 10.16 | Onaylı kalıcı kural yolu (B.3) | "Kalıcı yap" → `## Kalıcı Kurallar` → her alt kart isteminde kırpılmadan; ajan yeniden derlenince kaybolmuyor | memory-rag + ui | P0 |
| 10.17 | Bellek sayaçlarının dürüstleştirilmesi: `105 / 1404`, `7/12` (A.5) | Efsanede iki sayı; geri çağırma başlığında `N/M` | ui + memory-rag | P1 |
| 10.18 | Kontrol noktası özetiyle sürdürme (B.2) | Yeniden başlatılan kartta `[ÖNCEKİ DENEME ÖZETİ]`; token maliyeti ilk denemenin altında | agy | P1 |
| 10.19 | `build_knowledge_graph` `None` dayanıklılığı (A.1-2) | Boş başlıklı kasa notuyla çağrı istisna atmıyor | ui + memory-rag | P1 |
| 10.20 | Temizlik: artık `.db` + `.gitignore` (A.3) | `src/**/*.db` = 0 | qa | P2 |
| 10.21 | Sahne: boşta volta/mola, `avatar` alanı (B.4b, B.6) | Boşta ajan volta atıyor; künye `avatar`'ı sahneye yansıyor | ui | P2 |

---

## Doğrulanamayan / açık kalanlar

1. **`vault_manager.build_knowledge_graph` `None.strip()` hatası güncel kaynakta hâlâ var mı** —
   log satır numaraları eski ikiliden geliyor (`:674` vs kaynakta `:903`); hedefli test yazılmadan
   söylenemez.
2. **`frameless.py` düzeltmesinin canlı doğrulaması** — kaynakta `try/except` var, ama yeni derleme
   (`dist/EntropyAI/EntropyAI.exe`, 2026-09-09 22:42) ile kenardan boyutlandırma senaryosu koşulmadı;
   kullanıcının uygulaması açık olduğu için kapatılmadı.
3. **`~/.entropy/scheduler_tasks.json` içinde `daily-dreaming` kaydı var mı** — kullanıcı durum dosyası;
   salt okunur teşhiste açılmadı, teste de bağlanmamalı.
4. **Test paketi ve `dist_check` derlemesi koşulmadı** — bu görev salt okunur teşhis kapsamındaydı;
   sayısal test/derleme kanıtı bu notta **yoktur**.
5. **Kullanıcının "7 kayıt" gördüğü tam oturum** yeniden üretilmedi; A.5'teki 7 sayısı
   `BUDGET_RECALL = 800` üzerinden çıkarımdır — kesinleştirmek için o oturumun sorgusuyla
   `_recall_section` ölçülmeli.
