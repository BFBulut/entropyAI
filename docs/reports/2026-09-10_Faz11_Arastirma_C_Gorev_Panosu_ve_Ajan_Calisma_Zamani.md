# Faz 11 — Araştırma C: Görev Panosu ve Ajan Çalışma Zamanı

**Konu:** olay güdümlü + durum makinesi mimarisi, ajan kalıcılığı, model/efor değişimi, "ajanlara yardımcı araçlar" ilkesi
**Depo:** `C:\EntropiAI` — v0.8.0 (`pyproject.toml:7`), dal `ai/v0.1.7`
**Kip:** SALT OKUNUR araştırma. Kodda/kasada değişiklik yapılmadı; tek yazılı çıktı bu dosyadır. Model çağrısı yapılmadı (`claude --help`, `agy --help`, `claude agents --json` yalnızca yerel komutlardır).
**Tarih:** 2026-09-10

---

## 0. Yönetici özeti

Kullanıcının tarif ettiği akış — *girdi → araştır → görev üret → TASKBOARD → ajanları tetikle → TAKEN → rapor → sohbete dön* — bugün deponun **yalnızca yarısında** var, ve olan yarısı da **yanlış tarafta**: tam akış Desk ofis harness'ında (`agents/harness.py`, 2580 satır) kurulu, Entropy'nin kendi panosunda ise yok.

Somut olarak:

| Kullanıcının istediği | Bugünkü karşılığı | Durum |
|---|---|---|
| Entropy girdiyi araştırıp **kendi kararıyla** görev üretsin | Kart yalnızca `/task`, `/desk task` ya da bir UI düğmesiyle doğar | **Yok** |
| Ajanlar panoyu **kontrol etsin** (çekme/pull) | Harness alt kartı ajana **iter** (push, `harness.py:1704 _pump`) | Yanlış yön |
| Durum `TAKEN` olsun | Durum kümesi 5 değer: `backlog/running/review/done/failed` (`tasks.py:72`) — `assigned`/`taken`/`canceled` yok | **Yok** |
| Olay mimarisi | Qt sinyalleri var (`core/event_bus.py`), **diske yazılan olay günlüğü yok** | Yarım |
| Ajan başına kalıcı konuşma kimliği | Kimlik **görev başına** ve **bellekte**: `_background_conversations: Dict[str, str]` (`claude_bridge.py:387`, `agy_bridge.py:278`) — uygulama kapanınca gider | **Yok** |
| Model/efor AGENT.md'den | `model` akıyor (`tasks.py:413`), **`effort` hiçbir yere akmıyor** | Yarım |
| Rapor sohbete dönsün | Entropy kartı `report_to_entropy` **çağırmıyor**; sohbete yalnızca bildirim hapı düşüyor | Yarım |

Buna karşılık, mimarinin **taşıyıcı kolonları doğru kurulmuş** ve dış literatürle birebir örtüşüyor: kart = ön bilgili `.md` dosyası, izleyici = olay + yoklama melezi, kontrol noktası + kanıt disiplini, terminal olay sözleşmesi, proje kilidi, SQLite defter. Bu rapor bunları **korumayı**, eksik dört parçayı (durum makinesi, olay günlüğü, çekmeli tetikleyici, ajan oturum deposu) eklemeyi ve ajanlara **dört** araç vermeyi öneriyor — kırk değil.

En değerli tek bulgu: **`claude --bg` + `claude agents --json` + `claude attach <id>`** üçlüsü, "uygulama kapanıp açılsa da aynı terminal/oturum sürsün" isteğini **CLI'ın kendisi** karşılıyor (§2.5, doğrulanmış çıktı). Bu, tetikleyiciyi C#'a taşımayı gerektiren tek gerekçeyi de ortadan kaldırıyor (§3.3).

---

## 1. Mevcut durum — kanıtla

### 1.1 Kart deposu ve durum modeli

Kart, kasada YAML ön bilgili bir markdown dosyası:

- Entropy kartları: `<kasa>/Entropy/Tasks/<id>.md` (`tasks.py:54`)
- Ofis kartları: `<kasa>/Desk/Offices/<ofis>/cards/<id>.md` (`tasks.py:57-59`, `core/paths.py`)
- İki kökü birden taramak için `ALL_CARDS = "*"` (`tasks.py:70`)

`TaskCard` 31 alanlı bir dataclass (`tasks.py:146-203`): `id, title, status, agent, provider, model, skill, goal, criteria, created_at, started_at, finished_at, output_paths, summary, path, notes, office, parent, children, grade, verdict, attempt, budget_tokens, project, intent, checkpoint, proof, worktree, branch, pr_url`.

Durum kümesi beş değer:

```python
# src/entropy/agents/tasks.py:72
STATUSES = ("backlog", "running", "review", "done", "failed")
```

Geçişler **kod içine dağılmış**, tek bir tabloda değil:

- `backlog → running`: `tasks.py:1087` (`replace(card, status="running", started_at=_now(), provider=provider)`)
- `running → review|failed`: `tasks.py:1222` (`status="review" if ok else "failed"`)
- `running → failed` (kullanıcı durdurdu): `tasks.py:1192`
- `review → done`: yalnızca insan, UI'dan (`task_board_widget.py:904 mark_done`)
- `failed → backlog` (kilit alınamadı, yeniden kuyruğa): `harness.py:1826-1834`

Sonuç: **geçerli geçişi tanımlayan tek bir yer yok**; her çağıran `replace(card, status=...)` yazıyor. Bir durum eklemek (örn. `taken`) bugün en az 6 dosyaya dokunmayı gerektirir.

### 1.2 Tetikleme: bugün kartı kim başlatıyor?

`TaskBoard.run()` (`tasks.py:1013`) çağıran **tam beş** yer var:

| # | Çağıran | Kaynak | Tetikleyen |
|---|---|---|---|
| 1 | `/task <ajan> <başlık> :: <hedef>` | `slash_commands.py:589` | **Kullanıcı** |
| 2 | `/desk task <ofis> …` | `slash_commands.py:1059` | **Kullanıcı** |
| 3 | Ajanlar paneli "Görev ata" | `agents_widget.py:1400` | **Kullanıcı** |
| 4 | Kart panosu "Çalıştır" | `task_board_widget.py:884` | **Kullanıcı** |
| 5 | Ofis harness'ı alt kart pompası | `harness.py:1792` | **Orkestratör planı** |

Yani **Entropy kendi kararıyla hiçbir zaman görev üretip başlatmıyor.** `/task` işleyicisi (`slash_commands.py:524-601`) kartı oluşturup **aynı satırda** `board.run(card.id)` diyor (`:589`) — pano bir kuyruk değil, bir kayıt defteri gibi çalışıyor. `backlog` durumu pratikte hiç beklemiyor.

Tek otonom tetikleyici zamanlayıcı: `scheduler/cron_engine.py` — `TaskScheduler` (`:27`) ayrı bir `threading.Thread` ile dakikalık/saatlik/günlük `ScheduledTask` (`:14`) koşturuyor ve `~/.entropy/scheduler_tasks.json` içinde tutuyor. Ama bu **kart panosuna bağlı değil**: `_execute_task_logic` (`tasks_widget.py:419`) doğrudan köprüye prompt yolluyor, kart açmıyor.

Ofis tarafındaki pompa (`harness.py:1704 _pump`) **itmeli**: kapasiteyi hesaplar, `backlog` alt kartları seçer, `self._starting` ile çift başlatmayı önler ve `board.run(child.id, …)` çağırır (`:1792`). Ajan "panoya bakıp iş almıyor"; harness ajanı çağırıyor. Kullanıcının istediği model bunun **tersi**.

### 1.3 Olay yüzeyi: Qt sinyalleri var, günlük yok

`core/event_bus.py` 30+ tipli sinyal tanımlıyor. Bu iş için ilgili olanlar:

- `task_cards_updated(str)` — kart dosyası değişti (`event_bus.py:117`)
- `task_triggered(str,str)`, `task_completed(str,bool)`, `task_notification(str,str,str)` (`:69-71`)
- `task_followup_completed(dict)` (`:76`) — etkileşimli kartta takip turu bitti
- `office_progress(str,str,str)` — ofis, üst kart, aşama (`:127`)
- `agent_stream(dict)` — ajan/ofis/kart künyeli akış olayı (`:47-63`), yükü `provider.build_agent_stream_event` üretir (`provider.py:258`)
- `checkpoint_written(dict)`, `proof_recorded(dict)`, `rules_updated(str,int)` (`:141-144`)
- `mailbox_updated(str,str)` (`:123`)

Bunların **hiçbiri diske yazılmıyor.** Uygulama kapandığında olay dizisi kaybolur; geriye yalnızca (a) kart dosyasının son hâli, (b) SQLite defteri (`core/task_ledger.py`, `~/.entropy/tasks_ledger.db`), (c) posta kutusu mesajları kalır. Yani "ne oldu" değil "sonuç ne" saklanıyor — literatürün tam olarak eleştirdiği durum (§2.3).

Dosya izleme melez: `agents/watchers.py` `_VaultWatcher` (`:29`) hem `QFileSystemWatcher` hem 5000 ms yoklama (`:38`) kullanıyor, 400 ms geciktirme ile (`:54`). `TasksWatcher` (`:127`) iki kökü birden izliyor.

### 1.4 Ajan kalıcılığı: bugün yok

Üç ayrı katman var ve **hiçbiri ajan başına kalıcı değil**:

1. **Sohbet konuşması** — `core/identity.py:428 ConversationMap`. Sağlayıcı başına bayrak eşlemesi:
   ```python
   # src/entropy/core/identity.py:442
   FLAGS = {"agy": "--conversation", "claude": "--resume"}
   ```
   `resume_flag()` (`:485`) o tur için argv'ye eklenecek bayrağı verir; `sync_prompt()` (`:506`) sistem istemi değişince eşlemeyi düşürür (çünkü `--system-prompt-snapshot` varsayılan `on` ve süren oturum eski istemi taşır). Bu dosya `settings.json`'dan ayrı tutulur (`:432-433`). **Ama anahtarı konuşma kimliği, ajan adı değil.**

2. **Ofis konuşması** — `harness.py:507 conversation_key()` → `office:<ad>`; kimlik ofisin `state.json`'ına yazılır (`harness.py:551-573`). **Ofis başına**, ajan başına değil.

3. **Kart konuşması** — köprüde, **bellekte**:
   ```python
   # src/entropy/core/claude_bridge.py:387
   self._background_conversations: Dict[str, str] = {}
   # src/entropy/core/agy_bridge.py:278  (aynısı)
   ```
   Anahtar `task_id` = `card-<id>` (`tasks.py:1085`). Süreç ölünce sözlük gider. `background_conversation_id()` (`claude_bridge.py:1979`, `agy_bridge.py:954`) yalnızca **aynı oturum içinde** işe yarar; tek çağıranı `harness.py:2473`.

**Etkileşimli kart süreci** (Faz 10-D) canlı kalıyor ama yalnızca uygulama yaşadığı sürece: `InteractiveSession` (`provider.py:359`) alt sürecin `stdin`'ini açık tutar, `InteractiveSessionRegistry` (`provider.py:482`) `task_id → session` sözlüğü — yine bellekte. Boşta zaman aşımı 600 sn (`provider.py:338`), takip mesajı tavanı 4000 karakter (`provider.py:334`).

**Yeniden başlatma davranışı:** `main.py:85` açılışta `task_ledger.mark_orphans_failed()` çağırıyor — SQLite satırlarını FAILED yapıp posta kutusuna terminal olay yazıyor (`task_ledger.py:326-345`). `main.py:154-155` `OfficeHarness.resume_all()` çağırıyor. Ama:

```python
# src/entropy/agents/harness.py:2399
if not card.office or card.parent or card.status != "running":
    continue
```

`resume_all` **ofis kartı olmayanı atlıyor.** Yani uygulama Entropy'nin kendi kartı koşarken kapanırsa, kart dosyası sonsuza dek `status: running` kalır ve hiçbir şey onu düzeltmez.

### 1.5 Model ve efor: model akıyor, efor akmıyor

`AgentSpec` (`registry.py:139-160`) alanları: `name, role, description, provider, model, effort, skills, tools_policy, memory_path, prompt, office, models{}`. Yani **efor kaynakta var** (`registry.py:147`).

Model yolu **çalışıyor**: `resolve_card_model()` (`tasks.py:413`) kart modelini → ajan modelini sırayla dener, `compile.resolve_model` tablosundan geçirir ve `board.run` içinde `model=run_model or None` olarak köprüye verir (`tasks.py:1115`).

Efor yolu **kopuk**. Üç ayrı kırık nokta:

1. `agent_spec_payload()` (`tasks.py:444-456`) sistem istemine giren künyeyi kurarken **`effort` alanını taşımıyor** — yalnızca `name, role, description, prompt, tools_policy, office`.
2. Claude köprüsünde `build_command()` imzasında **`effort` parametresi yok** (`claude_bridge.py:648-665`); efor tek yerden geliyor:
   ```python
   # src/entropy/core/claude_bridge.py:806-813
   effort_m = re.search(r"(?:^|\s)/effort\s+(low|medium|high|xhigh|max)\b", prompt, re.IGNORECASE)
   effort = effort_m.group(1).lower() if effort_m else self.selected_effort
   if effort in CLAUDE_EFFORT_LEVELS:
       cmd.extend(["--effort", effort])
   ```
   `self.selected_effort` **oturum genelinde** (üst çubuk) ayarlanır (`claude_bridge.py:343-346`). Ajanın kendi eforu buraya hiç ulaşmıyor.
3. `claude_agents_json()` (`compile.py:246-268`) `--agents` yüküne `description/prompt/tools/model` koyuyor, **`effort` koymuyor**. Derlenmiş `.claude/agents/<ad>.md` dosyasına efor yazılıyor (`compile.py:200-201`) ama izole kipte CLI o dosyayı **okumuyor**: `--setting-sources ""` (`claude_bridge.py` izolasyon bloğu). Yani frontmatter'daki efor ölü harf.

agy tarafında efor **model adının son ekidir** (`gemini-3.8-flash-high`), ayrı bayrak değil — `agy --effort` ile `--model` çakışıyor (`agy_bridge.py:177-185`, `provider.py:47-56`). Orada `apply_effort_to_model()` (`agy_bridge.py:556`) ve `effort_for_prompt(..., default_effort=)` (`agy_bridge.py:518`) mekanizması var; yani agy'de ajan eforu **model adı üzerinden dolaylı olarak** akabiliyor, Claude'da hiç akmıyor.

Ayrıca arayüz tarafında bir geçici çözüm var ve tekrar okunmuyor:

```python
# src/entropy/ui/widgets/task_board_widget.py:846-860
"""`effort` TaskCard'da alan değil: `notes` içine `effort: <düzey>` satırı olarak taşınır."""
effort = str(payload.pop("effort", "") or "")
if effort:
    payload["notes"] = f"effort: {effort}"
```

`notes` alanı serbest metin; hiçbir kod bu satırı geri ayrıştırmıyor. Yani **kart panosundan efor değiştirmek bugün hiçbir şeye yaramıyor** (ve üstüne `notes` içeriğini eziyor).

Entropy'nin kendi modeli/eforu için `/model` (`slash_commands.py:128`) ve `/effort` (`:136`) komutları var, `config.provider_effort` sözlüğünde kalıcı; arayüzde `ui/widgets/effort_selector.py` ve `agents_widget.py:153 populate_effort_combo` sağlayıcıya göre doğru seviye kümesini üretiyor. Bu taraf **sağlam**.

### 1.6 Rapor sohbete nasıl dönüyor?

İki ayrı yol var ve Entropy'nin kendi kartı **zayıf olanı** kullanıyor.

- **Ofis kartı**: `harness.py:2224` → `report_to_entropy(...)` (`mailbox.py:467`) → Entropy gelen kutusuna `kind="report"` mesaj + `bus.report_inbox_unread` (`mailbox.py:496-501`). Rapor Merkezi ve bildirim merkezi bunu okuyor (`report_center.py:1020-1027`, `notification_center.py:153`).
- **Entropy kartı**: `TaskBoard._finish` (`tasks.py:1200`) yalnızca (a) wiki sayfası yazar, (b) ajan belleğine ekler, (c) `emit_terminal(...)` ile `kind="status"`, 500 karakterlik özet gönderir (`tasks.py:1238-1244`). **`report_to_entropy` çağrılmıyor** (tek çağıranı `harness.py:2224`, doğrulandı).

Sohbete düşen şey ise köprüden gelen ayrı bir sinyal: `bus.task_notification` (`claude_bridge.py:2299`, `agy_bridge.py:1329`) → `chat_mode._on_task_notification` (`chat_mode.py:867`) → "⏰ OTONOM PLANLI GÖREV ÇALIŞTIRILDI" kartı + "Raporu Aç" bağlantısı. Yani **rapor sohbete metin olarak girmiyor**, bir bağlantı hapı olarak görünüyor; Entropy bir sonraki turda o raporun içeriğini bağlamında görmüyor.

Ajanlar arası sohbet için `AgenticChat` (`identity.py:665 send`) var ve doğru çalışıyor: karşı tarafın oturumunu `conversation_id`/`--resume` ile sürdürüyor (`:722-729`), yanıtı gelen kutusuna `kind="report"` olarak yazıyor (`:751-762`).

### 1.7 Boşluk listesi

| # | Boşluk | Kanıt |
|---|---|---|
| **G1** | Durum makinesi yok; geçişler 6 dosyaya dağılmış, `assigned/taken/canceled` durumları yok | `tasks.py:72`, `:1088`, `:1213`, `:1182`, `harness.py:1826` |
| **G2** | Diske yazılan olay günlüğü yok; olaylar yalnızca Qt sinyali | `core/event_bus.py` (tamamı bellek içi) |
| **G3** | Çekmeli tetikleyici yok; ajan panoya bakmıyor, harness itiyor | `harness.py:1704`, `tasks.py` `run()` çağıranları |
| **G4** | Atomik sahiplenme (claim) yok; `_starting` seti yalnızca bellek içi ve tek süreç | `harness.py:1734-1737` |
| **G5** | Ajan başına kalıcı oturum kimliği yok; görev başına ve bellekte | `claude_bridge.py:387`, `agy_bridge.py:278` |
| **G6** | Entropy kartları için açılışta uzlaştırma yok; `running` kart asılı kalır | `harness.py:2399` |
| **G7** | `effort` AGENT.md'den yürütmeye hiç geçmiyor (Claude) | `tasks.py:444`, `claude_bridge.py:648`, `compile.py:246` |
| **G8** | Kart eforu `notes` içine yazılıp geri okunmuyor | `task_board_widget.py:846-860` |
| **G9** | Model/efor değişince süren süreç yeniden başlatılmıyor, eşleme düşürülmüyor | `identity.py:506` yalnızca istem imzasına bakıyor |
| **G10** | Entropy kartı raporu sohbet bağlamına dönmüyor | `tasks.py:1200` (`report_to_entropy` yok) |
| **G11** | Ajanların pano için hiç aracı yok; pano yalnızca prompt metni olarak enjekte ediliyor | `tasks.py:950 build_prompt`, `harness.py:1229 _child_lead_sections` |
| **G12** | `src/entropy/tools/` altında 60 dosya / 7.3 MB ölü kod; hiçbiri import edilmiyor | `grep -rn "from entropy.tools"` → yalnızca `synthesizer` |

---

## 2. Dış araştırma (2025–2026)

### 2.1 Dosya tabanlı görev panoları ve ajan kuyrukları

**kanban-md** (2026) tam olarak bu problemin referans uygulaması: "no database, no server, no SaaS — just files". Düzen ve alan adları doğrudan kullanılabilir:

- `kanban/config.yml` + `kanban/tasks/001-set-up-ci-pipeline.md`
- Kart ön bilgisi: `id, title, status, priority, created, updated, tags, claimed_by, claim_expiry`; isteğe bağlı `assignee, due, estimate, started, completed, parent, depends_on, blocked, class`
- Varsayılan durumlar: `backlog, todo, in-progress, review, done, archived`
- Durum başına `require_claim: true` zorlaması
- `config.yml` içinde `claim_timeout` (varsayılan 1 saat), `wip_limits`, `next_id`
- **`pick --claim <ad> --status todo --move in-progress`**: tek işlemde sahipsiz + engelsiz + bağımlılıkları karşılanmış görevi bulur, sahiplenir ve taşır — yarış koşulunu tek çağrıya indirir
- Süresi dolan sahiplenme kendiliğinden serbest kalır; Unix'te sahiplenilmiş dosya salt-okunur yapılır (**Windows'ta bu numara yok** — bizim için lock dosyası gerekecek)
- `handoff` komutu ajanlar arası devir için

Entropy'nin bugünkü kart biçimi bu şemayla **büyük ölçüde örtüşüyor**; eksik olanlar tam olarak `priority`, `claimed_by`, `claim_expiry` ve atomik `pick`.

Aynı yaklaşımın gerekçesi ("The Case for Markdown as Your Agent's Task Format", 2026): markdown'ı hem insan hem ajan hem `grep` hem git okuyabilir; ayrı bir API katmanı bu üç yolu da kapatır. Bu, deponun kendi gerekçesiyle birebir aynı (`tasks.py:1-8`).

### 2.2 Durum makinesi kütüphaneleri

İki ana Python seçeneği var ve farkları bizim için belirleyici:

- **`transitions`** (pytransitions): hafif, nesne yönelimli; makine düzeyinde kesişen ilgiler için `prepare_event`, `finalize_event`, `on_exception` geri çağrıları — günlükleme/denetim için doğrudan bağlanma noktası. Eşzamanlı ve eşzamansız geri çağrı desteği. Önemli tuzak: bir geri çağrı istisna atarsa geri çağrı işleme durur; geçiş **sonrasında** atılan istisna geri alınmaz (rollback yok) — durum değişmiş kalır.
- **`python-statemachine`**: geri çağrı imzasını inceleyip parametreleri otomatik enjekte eder; `transitions`'ta olmayan **hiyerarşik** özellikler (History pseudo-state, olaysız geçişler) sunar.

**Öneri: kütüphane eklemeyin.** Gerekçe depodan: PyYAML zaten *isteğe bağlı* bir bağımlılık ve "paketlenmiş exe'de bulunmayabiliyor" diye ajan katmanı onsuz çalışacak şekilde yazılmış (`registry.py:26-30`). Bir durum makinesi kütüphanesi aynı riski alır ama karşılığında yalnızca ~12 satırlık bir geçiş tablosu verir. Tabloyu veri olarak yazmak (§3.2) hem PyInstaller güvenli hem test edilebilir. Kriter: **hiyerarşik durum** ya da **async geri çağrı** gerekirse `python-statemachine`'e geçin; o gün gelene kadar tablo yeter.

Alınacak fikir kütüphaneden değil, disiplinden: geçiş **tek yerde tanımlı**, geçersiz geçiş **hata**, ve kesişen ilgiler (olay yazma, sinyal yayma) `finalize` benzeri **tek** kancada.

### 2.3 Olay kaynağı (event sourcing) ve append-only günlük

**ESAA** (arXiv 2602.23193, "Event Sourcing for Autonomous Agents in LLM-Based Software Engineering") bu mimarinin akademik karşılığı ve şemayı doğrudan verir:

- Ajan çıktı sözleşmesi (v0.3.0) alanları: `schema_version`, `correlation_id`, `task_id`, `attempt_id`, `actor`, `action`, `idempotency_key`, `payload`
- Günlük dosyası: **`activity.jsonl`** — satır başına bir değişmez olgu
- Temel önerme: *"gerçeğin kaynağı deponun anlık görüntüsü değil, niyetlerin/kararların/etkilerin değişmez günlüğüdür"*
- Deterministik orkestratör olayları sırayla uygulayıp `roadmap.json` maddi görünümünü türetir; görünümde JSON kanonikleştirme + SHA-256 ile hesaplanan bir **`projection_hash_sha256`** alanı var. Doğrulama = olayları yeniden oynat, karma karşılaştır, sapmayı yakala.
- Ajanlar `claim` olayıyla görev alır, `complete` olayıyla `acceptance_results` döndürür. *"Birden çok ajan paralel çalışabilir, ama sonuçları sıralı olarak doğrulanıp eklenir."*
- Ölçüm (CS2): 50 görev, 86 olay, 4 eşzamanlı ajan, 31 görev tamamlandı (%62), ~15 saat, **0 reddedilen çıktı**, `verify_status=ok`. Olay dağılımı: `promote` 17, `claim` 30, `complete` 30, `phase.complete` 8.

Pratik tarafta ("Give Agents an Append-Only Event Log", 2026) minimal reçete: **dört olay tipiyle başla** — `run.start`, `run.finish`, `lock.acquire`, `lock.release`. Argüman: *"`status: done` diyen bir satır sana nihai cevabı söyler, izlenen yolu değil."* Eşleşmeyen `run.start` = çökmüş koşu; serbest bırakılmamış kilit = kaynak sızıntısı. Ve tek kural: **eski olayı asla düzenleme/silme** — *"kodun eski olayları düzenlemesine izin verdiğin an, fazladan adımlarla birlikte yine bir durum alanına dönmüş olursun."*

Üretim tarafında aynı desen: `.jsonl` "stream recorder" + yerel yeniden oynatma aracı; çökmüş bir düğüm `replay?offset=X` ile durumunu yeniden dolduruyor, en uzun konuşmada (358 olay) çökme sonrası toparlanma **20 ms altında**. Fayda: başarısız bir oturumu **API kredisi yakmadan ve dış sistemi rahatsız etmeden** yeniden oynatmak.

Bizim için doğrudan sonuç: **kart dosyası kalır** (insan/ajan sözleşmesi), **olay günlüğü eklenir** (denetim + kurtarma omurgası), **TASKBOARD.md türetilmiş görünüm olur** (asla elle yazılmaz).

### 2.4 İzleme: `watchdog` gerekli mi?

Hayır — ve bu, deponun mevcut kodunu **doğrulayan** bir bulgu.

`watchdog`'un Windows gözlemcisi `ReadDirectoryChangesW` üzerine kurulu ve bilinen kayıplar var: API dizin yeniden adlandırma olaylarını **altındaki G/Ç tamamlanmadan önce** döndürüyor, bu da taşınan dizinin içeriği için olay kuyruğa alınmasını engelleyebiliyor. Kullanıcı raporları net: varsayılan `Observer` ile **çok sayıda olay kayboluyor**, `PollingObserver`'a zorlayınca hepsi yakalanıyor. Ağ/CIFS paylaşımlarında `PollingObserver` **açıkça** seçilmeli — ama o da ağ kopmasında çöküyor ve toparlanmıyor. `watchdog` kendi içinde de dizin ağacı anlık görüntülerini karşılaştıran bir yoklama yedeği barındırıyor.

Entropy'nin `_VaultWatcher`'ı (`watchers.py:29-125`) zaten tam olarak önerilen melezi uyguluyor: `QFileSystemWatcher` + 5000 ms yoklama + 400 ms geciktirme, ve yoklama diski yormasın diye yalnızca `(yol, mtime_ns)` imzası karşılaştırılıyor (`:88-96`). Obsidian kasalarının çoğunlukla OneDrive'da durduğu da yorumda gerekçelendirilmiş (`watchers.py:9-13`).

**Karar: `watchdog` eklenmesin.** Yeni pano kökleri (`Entropy/Board/`) mevcut `_VaultWatcher` alt sınıfı olarak eklenmeli.

### 2.5 Kalıcı oturumlar — CLI kanıtı

Bu bölümdeki her satır bu makinede çalıştırılan komutların çıktısıdır.

**`claude --help` (ilgili bayraklar):**

| Bayrak | Anlamı |
|---|---|
| `--session-id <uuid>` | *"Use a specific session ID for the conversation (must be a valid UUID)"* — **oturum kimliğini biz seçebiliyoruz** |
| `-r, --resume [value]` | Oturum kimliğiyle sürdür |
| `--fork-session` | Sürdürürken orijinali korumak yerine yeni kimlik üret |
| `-n, --name <name>` | Oturuma görünen ad ver (`/resume` seçicisinde ve terminal başlığında görünür) |
| `--bg, --background` | Oturumu arka planda başlat ve hemen dön; `claude attach/logs/stop/rm`'in aldığı kısa kimliği yazdırır. `--resume <session-id>` ile birlikte **aynı kimlik altında** arka planda sürdürür |
| `--no-session-persistence` | Oturum diske yazılmaz, sürdürülemez (print kipinde) — **kullanmayın** |
| `--effort <level>` | `low, medium, high, xhigh, max` |
| `--input-format stream-json` | Gerçek zamanlı akışlı **girdi** |
| `--json-schema <schema>` | Yapılandırılmış çıktı doğrulaması |
| `--max-budget-usd <amount>` | Print kipinde harcama tavanı |
| `--include-hook-events` | Kanca yaşam döngüsü olaylarını çıktı akışına kat |
| `--system-prompt-snapshot <on\|off>` | `on` (varsayılan): istem konuşmanın ilk isteğinde kaydedilir ve **sonraki her istek ve resume'da aynen** gönderilir |

**`claude` alt komutları (arka plan oturum yönetimi):**

```
agents [options]   Manage background agents
attach <id>        Open a background session in this terminal
logs <id>          Print a background session's recent terminal output
respawn [id]       Restart a background session (--all for all of them)
rm <id>            Delete a background session, and its worktree when that is safe
stop|kill <id>     Stop a background session. Its conversation is kept:
                   `claude attach <id>` opens it again, `claude --resume` works once it is stopped
```

`claude agents --json` — *"Print active sessions (interactive and background) as a JSON array and exit (for scripting; does not require a TTY)"*. Bu makinede çalıştırıldı, gerçek çıktı:

```json
[
  {
    "pid": 39128,
    "cwd": "C:\\EntropiAI",
    "kind": "interactive",
    "startedAt": 1789004008482,
    "sessionId": "1bdbc000-be5a-4312-95b3-82cc3ec4774d",
    "name": "entropiai-48"
  }
]
```

**Bu, kullanıcının "uygulama kapanıp açılsa da aynı terminal/oturum sürsün" isteğinin doğrudan karşılığıdır.** Entropy'nin kendi süreç ağacında tutmasına gerek yok: `--bg` ile başlatılan oturum işletim sistemi düzeyinde yaşar, `agents --json` ile keşfedilir, `attach` ile açılır, `logs` ile okunur.

**Oturum deposu diskte doğrulandı:** `~/.claude/projects/<slug(cwd)>/<session-uuid>.jsonl`. Bu makinedeki klasörler:

```
C--EntropiAI
C--EntropiAI-dist-EntropyAI
C--Entropy-Agent-Desk-dist-EntropyAgentDesk-offices-office-deneme-desks-office-deneme-orkestrat-r
C--Entropy-Agent-Desk-offices-office-meta-desks-orchestrator
C--Users-batu-
```

**Kritik sonuç:** depo **çalışma dizinine (cwd) göre anahtarlı**. Faz 10-C'de eklenen kart başına worktree (`TaskCard.worktree`, `tasks.py:200-205`) cwd'yi değiştirdiği için, aynı ajanın oturumu **başka bir proje klasörüne** düşer ve farklı bir cwd'den `--resume` onu bulamayabilir. Ajan oturum deposu tasarımında cwd **birlikte** saklanmalı (§3.4). Bu, Agent SDK belgelerinin de söylediği şey: *"store lookup key derives from the working directory, so resume from a cwd matching the original run's."*

**`agy --help` (ilgili bayraklar):**

| Bayrak | Anlamı |
|---|---|
| `--conversation` | Önceki konuşmayı kimlikle sürdür |
| `-c, --continue` | En son konuşmayı sürdür |
| `--effort` | `low\|medium\|high` |
| `--input-format` | `text, stream-json` — *"stream-json stdin'den satır başına bir NDJSON mesajı okur ve her biri için bir tur koşar; `--output-format stream-json` gerektirir"* |
| `--json-schema` | Yapılandırılmış çıktı |
| `--project` | Proje kimliği ya da adı |
| `--print-timeout` | Print kipi zaman aşımı (varsayılan 5 dk) |
| `remote-control` | *"Manage the remote-control background daemon (start, status, stop)"* |

**Asimetri (tasarımı belirler):** Claude oturum kimliğini **önceden atayabiliyor** (`--session-id <uuid>`), agy **atayamıyor** — kimliği akıştan yakalamak zorundayız (bugün `agy_bridge.py:1551-1554` bunu zaten yapıyor). Yani ajan kimliği tasarımı iki koldan yürümeli (§3.4).

Agent SDK tarafındaki genel ilke aynı: oturum kimliği `ResultMessage` ile döner, bir sonraki çağrıya verilince konuşma kaldığı yerden sürer; **fork** orijinalin geçmişinin kopyasıyla başlayan yeni bir oturum üretir ve orijinalin kimliği/geçmişi değişmez. SDK oturum durumunu **kimliğe göre** tutar, kullanıcıya göre değil — *"uygulamalar kendi oturum kimliği kalıcılık stratejisini uygulamak zorunda"*. Bu bizim `Entropy/Board/agents/<ad>/session.json` önerimizin tam gerekçesi.

### 2.6 Çoklu ajan çerçevelerinde dağıtım ve devir (handoff)

2026 karşılaştırmalarının ortak tablosu:

| Çerçeve | Dağıtım/devir modeli | Durum kalıcılığı |
|---|---|---|
| **LangGraph** | `Command` ile açık devir; konuşma bağlamı geçişte taşınır | Yerleşik checkpointing + "time travel"; 2026/04'te durum kalıcılığı ve insan-döngüde kontrol noktaları iyileştirildi (`PostgresSaver`) |
| **OpenAI Agents SDK** (Swarm'ın halefi, 2025/03) | Açık `handoff` | Bağlam değişkenleri, varsayılan **geçici** |
| **CrewAI** | Rol + görev; sıralı süreç, delegasyon | Görev çıktıları sıralı aktarılır; toparlanma desenleri LangGraph'a göre olgunlaşmamış |
| **AutoGen / AG2** | Konuşmalı `GroupChat` | Konuşma geçmişi, varsayılan bellek içi — **ajan-ajan sohbeti LLM maliyetini katlıyor** |

Entropy için üç çıkarım:

1. **Konuşmalı devir pahalıdır.** AutoGen'in `GroupChat` maliyeti bunun kanıtı. Entropy'nin dosya tabanlı devri (kart + kontrol noktası + rapor) daha ucuz ve zaten kurulu — konuşmalı devri (`AgenticChat`, `identity.py:665`) **istisna** olarak tutun, varsayılan yapmayın.
2. **Kalıcılık, çerçevelerin ayrıştığı yer.** En olgun olanın (LangGraph) ayırt edici özelliği checkpointer. Entropy'nin karşılığı `harness.py:1024 record_checkpoint` + `resume_section` (`:1089`) — doğru yerde. Eksik olan, bunun **Entropy'nin kendi kartlarına** da uygulanması (G6).
3. **Devir açık bir olay olmalı**, örtük bir çağrı değil — LangGraph'ın `Command`'ı, kanban-md'nin `handoff`'u ve ESAA'nın `claim`/`complete` olayları aynı şeyi söylüyor. Bizde bu `assigned → taken` geçişi ve `task.claimed` olayı olacak.

### 2.7 Dinamik iş akışları (2026)

1 Haziran 2026'da araştırma önizlemesi olarak duyurulan Dynamic Workflows: Claude görevi alır, **bir JavaScript orkestrasyon betiği yazar**, işi alt görevlere böler, paralel koşturur ve sonuçları doğrulayıp birleştirir. Paralel alt ajan tavanı 1000 mertebesinde. Etkinleştirme ya açık istekle ya da `ultracode` ayarıyla (Claude ne zaman iş akışı yaklaşımının uygun olduğuna kendisi karar verir). **İlerleme koşu boyunca kaydediliyor; kesilen koşu baştan başlamadan sürdürülüyor.** Anthropic'in kendi uyarısı: tipik bir oturumdan **belirgin biçimde daha çok token** harcar; küçük ve iyi kapsamlanmış işlerle başlayın.

Bizim için iki ders:

- **Ders 1 (al):** "ilerleme sürekli kaydedilir, kesilen koşu sürdürülür" — bu bizim kontrol noktası + olay günlüğü ikilisinin doğrulaması. Kart panosunun **yeniden başlatılabilirliği** birinci sınıf bir gereksinim, sonradan eklenecek bir konfor değil.
- **Ders 2 (alma):** orkestratörün **kod yazması** (JS betiği üretmesi) bizim tüzüğümüze aykırı — kullanıcının kalıcı kuralı "orkestratör hiçbir zaman kod yazmaz" ve bu `compile.ORCHESTRATOR_RULES` (`compile.py:279-283`) ile zaten dayatılıyor. Bizim karşılığımız betik değil **plan JSON'u**; `--json-schema` bayrağı (hem `claude` hem `agy`'de var) bunu şema düzeyinde zorlamak için kullanılabilir — bugün plan JSON'u serbest metinden ayrıştırılıyor (`harness.py:386 extract_json_block`).

### 2.8 Ajanlar için araç tasarımı

Anthropic'in mühendislik rehberi altı ilke veriyor ve hepsi doğrudan uygulanabilir:

1. **Doğru aracı seç:** *"Daha çok araç her zaman daha iyi sonuç vermez."* Her API uç noktasını sarmalamak yerine yüksek etkili iş akışlarına odaklan; işlevi **birleştir** — `list_users` + `list_events` + `create_event` yerine tek `schedule_event`.
2. **Ad alanı:** ilgili araçları ortak önekte grupla (`asana_search`, `jira_search`) — sınırları belirginleştirir, örtüşen seçeneklerde kafa karışıklığını önler.
3. **Anlamlı bağlam döndür:** *"Araç uygulamaları yalnızca yüksek sinyalli bilgi döndürmeye özen göstermeli."* `uuid` yerine `name`, `256px_image_url` yerine `image_url`. Ajanın seçebilmesi için `response_format` parametresi: `concise` / `detailed`.
4. **Token verimliliği:** sayfalama, aralık seçimi, süzme, kırpma — makul varsayılanlarla. Hata mesajları ajanı geniş taramadan hedefli aramaya **yönlendirmeli**.
5. **Araç açıklamalarını istem gibi yaz:** *"Araç açıklamalarındaki küçük iyileştirmeler bile çarpıcı kazanç verebilir."* Yeni bir takım arkadaşına anlatır gibi yaz; `user` değil `user_id`.
6. **Değerlendirmeyle yinele:** gerçek iş akışlarına dayalı değerlendirme kur, ajanın nerede tökezlediğini sistematik incele, transkriptlerden araçları yeniden tasarla.

Ve bağlam mühendisliği rehberinin özeti: en basit çalışan mimari; zekilik yerine **şeffaflık** (her adım incelenebilir olmalı); iyi belgelenmiş, iyi tiplenmiş, net hata mesajlı araçlar kuvvet çarpanıdır. Temel içgörü: **ajanlar, deterministik araçların deterministik olmayan kullanıcılarıdır** — araç, bu belirsizliği hesaba katan bir sözleşmedir.

Entropy bu ilkelerle **zaten hizalı** ve bu ölçülebilir:

- Modelin gördüğü araç yüzeyi izole kipte en fazla 8 yerleşik: `CHAT_TOOLS_READONLY = ["Read","Glob","Grep","WebFetch","WebSearch"]` + `CHAT_TOOLS_WRITE = ["Edit","Write","Bash"]` (`claude_bridge.py:157-158`)
- MCP ad alanı kapalı: `--disallowedTools "mcp__*"`, koddaki ölçüm notu **119 araç adı ≈ 2.4k token** (`claude_bridge.py` izolasyon bloğu)
- Yetenek kataloğu kapalı: `--disable-slash-commands`, **32 yetenek ≈ 3.8k token**
- 36 slash komut (`grep -c "SlashCommand(" src/entropy/core/slash_commands.py` → 36) **kullanıcıya** bakar, modele değil — hepsi yerel işlenir, model çağrısı üretmez
- Ajan araç politikası 4 değer: `read-only / read-write / full / no-tools` (`compile.py:142-147`)

Yani sorun "çok araç" değil. Sorun **sıfır pano aracı**: ajan panoyu yalnızca prompt'a gömülen metinden görüyor (`tasks.py:950 build_prompt`, `harness.py:1229 _child_lead_sections`) ve panoya **hiçbir şey yazamıyor** — kontrol noktası ve kanıt bile serbest metin etiketleriyle (`[KONTROL NOKTASI]`, `[KANIT]`, `tasks.py:88-90`) çıktıdan geri ayrıştırılıyor. Bu, deterministik olmayan bir kullanıcıdan deterministik bir sözleşme beklemek demek.

---

## 3. Tasarım

### 3.1 Entropy Board — dosya düzeni

**Öneri (A) — düşük göç maliyeti, önerilen:**

```
<kasa>/Entropy/Tasks/<id>.md          # KART (var; yerinde kalır, TasksWatcher zaten izliyor)
<kasa>/Entropy/Board/
    TASKBOARD.md                      # TÜRETİLMİŞ insan panosu (asla elle yazılmaz)
    events.jsonl                      # append-only olay günlüğü (tek denetim kaynağı)
    events/2026-08.jsonl              # aylık döndürülmüş arşiv
    claims/<id>.lock                  # atomik sahiplenme kirası
    agents/<ad>/session.json          # ajan başına kalıcı oturum kimliği
    projection.json                   # son uygulanan seq + projection_hash
```

Kullanıcının yazdığı düzen kartları `Entropy/Board/tasks/<id>.md` altına alıyordu (**Öneri B**). Maliyeti somut: Faz 9'da zaten bir kart göçü yapıldı ve makinesi hâlâ kodda duruyor (`tasks.py:723 _migrate_office_cards_once`, `:734 migrate_office_cards`, göç günlüğü `paths.MIGRATION_LOG_SUBPATH`). Üçüncü göç, `TasksWatcher`'ın iki kökünü, `card_file()` arama sırasını (`tasks.py:532-552`), Desk'in ofis kökünü ve kullanıcının Obsidian yer imlerini birden kırar. **Kazanç yalnızca kozmetik.** Bu yüzden A önerilir; `Entropy/Board/` *panonun* ad alanı olur, kartlar yerinde kalır. B seçilirse mevcut göç makinesi yeniden kullanılmalı ve `dry_run` varsayılanı korunmalı.

**Kart ön bilgisine eklenecek alanlar** (kanban-md ve ESAA şemalarından):

| Alan | Tip | Neden |
|---|---|---|
| `priority` | `P0\|P1\|P2` | `pick` sıralaması; bugün sıralama yalnızca dosya adı |
| `effort` | `low\|medium\|high\|xhigh\|max` | G7/G8: `notes` hilesi kalkar, gerçek alan olur |
| `input_paths` | `list[str]` | Girdi sözleşmesi; bugün yalnızca `goal` metni var |
| `report_path` | `str` | Rapor yolu; bugün `output_paths` içinde karışık duruyor |
| `claimed_by` | `str` | Sahiplenen ajan |
| `claim_expiry` | ISO ts | Kira sonu; süresi dolan sahiplenme serbest kalır |
| `event_seq` | `int` | Bu kartın gördüğü son olay sırası (projeksiyon tutarlılığı) |

Mevcut 31 alanın hiçbiri kaldırılmaz. `to_frontmatter()` (`tasks.py:204`) yedi anahtar daha yazar; `_read` (`tasks.py:592`) bilinmeyen anahtarı zaten yok sayıyor, yani **eski sürüm yeni kartı okuyabilir** (alanları kaybeder ama çökmez).

### 3.2 Durum makinesi ve olay günlüğü

**Durumlar** (`tasks.py:72` genişletilir):

```python
STATUSES = ("backlog", "assigned", "taken", "running",
            "review", "done", "failed", "canceled")
```

Geriye uyumluluk: `to_frontmatter` bilinmeyen durumu `backlog`'a düşürüyor (`tasks.py:208`). Yani yeni sürümün yazdığı `taken` kartı eski sürüm okursa `backlog` olur — veri kaybı değil, güvenli bozulma. Yeni durumların hepsi listeye eklenmeli, aksi hâlde yazılır yazılmaz `backlog`'a düşerler.

**Geçiş tablosu — tek kaynak** (`entropy/agents/board_fsm.py`, veri olarak):

| # | Kaynak | Olay | Hedef | Koruma (guard) | Etki |
|---|---|---|---|---|---|
| T1 | — | `task.created` | `backlog` | başlık ve hedef dolu | kart dosyası yazılır |
| T2 | `backlog` | `task.assigned` | `assigned` | ajan kadroda var (`registry.get`) | `agent` yazılır |
| T3 | `assigned` | `task.claimed` | `taken` | `claims/<id>.lock` `O_EXCL` ile alındı | `claimed_by`, `claim_expiry` |
| T4 | `taken` | `run.started` | `running` | köprü süreci doğdu, ledger RUNNING | `started_at`, `provider` |
| T5 | `running` | `checkpoint.written` | `running` | — | `checkpoint` yolu |
| T6 | `running` | `run.finished(ok=1)` | `review` | `[KANIT]` bloğu var ve yeşil | `summary`, `proof`, `report_path` |
| T7 | `running` | `run.finished(ok=0)` | `failed` | — | `summary` |
| T8 | `taken\|running` | `claim.expired` | `assigned` | kira doldu **ve** PID ölü | kilit silinir, `attempt` artmaz |
| T9 | `running` | `lock.timeout` | `assigned` | `LOCK_TIMEOUT_MARKER` özet içinde | yeniden kuyruk (bugün `harness.py:1826`) |
| T10 | `review` | `task.accepted` | `done` | **insan** onayı | — |
| T11 | `review` | `task.rejected` | `assigned` | `attempt < 2` | `attempt += 1` |
| T12 | `backlog\|assigned\|taken\|running` | `task.canceled` | `canceled` | — | süreç öldürülür (`tasks.py:1167`) |

`review → done` geçişinin **insan** koruması bilinçli ve mevcut tasarımın devamı (`tasks.py:23-26`: *"'review'de durur, 'done' bilinçli bir insan onayıdır"*). T6'daki kanıt koruması Faz 10-A'daki close-with-proof kuralının makineleşmiş hâli (`tasks.py:125 proof_discipline`).

Geçersiz geçiş: `InvalidTransition` istisnası. `transitions` kütüphanesinin bilinen tuzağından ders: **olay önce günlüğe, sonra karta** yazılır ve etki fonksiyonu istisna atarsa geçiş uygulanmaz (günlüğe `transition.rejected` düşer). Böylece "geçiş sonrası istisna → durum değişmiş kalır" hatası oluşmaz.

**Olay günlüğü satır şeması** (ESAA + pratik reçetenin birleşimi):

```json
{"schema_version":"1.0","seq":1284,"ts":"2026-09-10T14:32:11+03:00",
 "correlation_id":"20260910-1432-rapor","task_id":"20260910-1432-rapor",
 "attempt_id":1,"actor":"arastirmaci","action":"run.started",
 "idempotency_key":"card-20260910-1432-rapor-a1-run.started",
 "payload":{"provider":"claude","model":"claude-opus-5","effort":"high",
            "session_id":"7f1c…","cwd":"C:\\EntropiAI","ledger_task_id":"card-20260910-1432-rapor"}}
```

**Olay sözlüğü** (12 tip, tabloyla birebir + iki kilit olayı):
`task.created, task.assigned, task.claimed, run.started, checkpoint.written, run.finished, claim.expired, lock.acquire, lock.release, task.accepted, task.rejected, task.canceled`

Kurallar:

- **Yalnızca ekleme.** Hiçbir satır düzenlenmez/silinmez. Düzenlemeye izin verilen an günlük, "fazladan adımlarla bir durum alanına" dönüşür.
- `seq` monoton; yazma tek bir `threading.Lock` altında (`tasks.py:495` deseninin aynısı) + `open(..., "a", encoding="utf-8")` satır tamponsuz.
- Eşleşmeyen `run.started` = çökmüş koşu → açılışta uzlaştırıcının aradığı imza (G6'nın çözümü).
- `idempotency_key` aynı olayın iki kez yazılmasını önler (köprü geri çağrısı senkron gelirse yeniden giriş oluyor — bugün `harness.py:1738 _starting` seti bunu bellekte çözüyor).
- Aylık döndürme (`events/2026-08.jsonl`); günlük dosya **önerilmez**, projeksiyon 30 dosya açmak zorunda kalır.

**Projeksiyon:** `TASKBOARD.md` ve kart ön bilgisi **türetilmiş** görünümlerdir. `projection.json` içinde `last_seq` + `projection_hash` (JSON kanonikleştirme + SHA-256, ESAA'daki gibi). Test: günlüğü sıfırdan oynat → aynı karma çıkmalı. Bu tek test, "olay günlüğü gerçekten tek kaynak mı" sorusunu deterministik yanıtlar.

**`bus` ile ilişki:** olay yazıcı, yazdıktan sonra karşılık gelen Qt sinyalini yayar (`task_cards_updated`, `office_progress`, `checkpoint_written`, `proof_recorded`). Yani `bus` kaldırılmaz — **günlüğün önüne değil, arkasına** geçer. Bugün sinyal yayılıyor ama iz kalmıyor; sonrasında iz kalır ve sinyal onun bildirimi olur.

### 3.3 Tetikleyici — `BoardDispatcher`

**Yeni modül:** `src/entropy/agents/dispatcher.py`

```
BoardDispatcher(QObject)
  ├─ QTimer(3000 ms)              # tur zamanlayıcı
  ├─ bus.task_cards_updated       # olayla uyanma (yoklamayı beklemeden)
  └─ tick():
       for spec in registry.list():            # Entropy kadrosu
           if self.busy(spec.name): continue   # aktif kart/oturum var mı
           card = board.pick(agent=spec.name)  # ATOMİK: bul + sahiplen + taşı
           if card is None: continue
           board.start(card.id, agent_spec=spec)
```

**Atomik sahiplenme (`board.pick`)** — Windows'ta çalışan yol:

```
1. aday = [c for c in board.list(status="assigned") if c.agent == ajan]
          sıralama: priority (P0>P1>P2) → created_at
2. her aday için:
     fd = os.open(claims/<id>.lock, O_CREAT | O_EXCL | O_WRONLY)   # atomik
       başarılı → json.dump({"agent","pid","expiry"}) → events: task.claimed
                  → kart: status=taken, claimed_by, claim_expiry → DÖN
       FileExistsError → kirayı oku:
            expiry geçmiş VE pid ölü → claim.expired olayı, os.replace ile devral
            aksi hâlde → sıradaki adaya geç
```

Neden bu ikili: `O_CREAT|O_EXCL` "yoksa oluştur" ilkelinin taşınabilir hâli, `os.replace` ise NTFS'te aynı birim içinde atomik. kanban-md'nin Unix'te kullandığı "sahiplenilen dosyayı salt-okunur yap" numarası Windows'ta güvenilir değil (ACL'ler ve OneDrive senkronu araya girer), bu yüzden kilit **ayrı dosyada** tutulur — kart dosyasının kendisine dokunulmaz, böylece Obsidian'da açıkken de sahiplenme çalışır.

**Kira süresi (`claim_timeout`):** varsayılan 1 saat (kanban-md'nin varsayılanı). Entropy için `config.board_claim_timeout_s = 3600`. `MAX_STEPS_PER_CARD = 20` (`tasks.py:83`) ve `--print-timeout` varsayılanı 5 dk (agy) düşünüldüğünde bu bol; amaç zaten "asılı kalanı bir gün sonra değil, bir saat sonra kurtar".

**Paralellik:** ofis tarafında `office.max_parallel` var (`harness.py:1725`). Entropy panosu için `config.entropy_max_parallel` (varsayılan **2**). Üst sınırı zorlamaya gerek yok: yazma niyetli kartlar zaten proje yazma kilidinde serileşiyor (`core/project_lock.py`, `tasks.py:383 followup_lock_hooks`).

**Neden Python, C# değil — gerekçe:**

1. **Paylaşılan durum aynı süreçte.** Tetikleyicinin `config`, `bus`, `ConversationMap`, `project_lock_manager`, `TaskLedger` ve köprü önbelleğine (`TaskBoard._bridge_cache`, `tasks.py:495`) erişmesi gerekiyor. Ayrı bir C# süreci bunların hepsi için ikinci bir IPC katmanı ve ikinci bir gerçek kaynağı demek — projenin tüm mimarisi "tek gerçek kaynak" üzerine kurulu.
2. **Paketleme.** Uygulama tek PyInstaller exe olarak dağıtılıyor (`dist_check` akışı, `scratch/_build*.log`). .NET çalışma zamanı bağımlılığı kurulum ayak izini ve destek yüzeyini büyütür.
3. **Darboğaz tetikleyicide değil.** Tur maliyeti milisaniye; iş süresi CLI'ın model gecikmesi (dakikalar). Bir turun 3 sn'de bir dosya imzası karşılaştırması, `_VaultWatcher`'ın 5 sn'lik yoklamasıyla aynı büyüklükte ve o zaten sorunsuz çalışıyor.
4. **Atomiklik dil sorunu değil.** `os.open(O_CREAT|O_EXCL)` ve `os.replace` Python'dan da NTFS'te atomik.
5. **"Uygulama kapanınca ajan ölmesin" C# gerektirmiyor.** Bu, dil değil **süreç sahipliği** sorunuydu ve CLI'ın kendisi çözüyor: `claude --bg` + `claude agents --json` + `claude attach` (§2.5, doğrulandı). Tetikleyici C#'a taşınsaydı bile, alt süreç yine tetikleyicinin çocuğu olurdu ve tetikleyici kapanınca ölürdü.

**Sonuç: tetikleyici Python, uygulama içi bir `QObject`.** Ayrı bir Windows Servisi/C# gerekçesi yalnızca "uygulama tamamen kapalıyken de pano dönmeye devam etsin" istenirse doğar; o gün geldiğinde doğru cevap yine C# değil, `claude --bg` ile başlatılmış oturumların **kendi başlarına** koşması ve uygulamanın açılışta `agents --json` ile onları toplamasıdır.

**Akışın tamamı (kullanıcının grafiğiyle eşleşen):**

```
Kullanıcı girdisi
   └─> Entropy sohbeti (Brain/RAG + aktif yetenekler ile araştırma)
        └─> Entropy KARAR verir: bu iş devredilir
             └─> board.create(...)            → olay: task.created   → durum: backlog
             └─> board.assign(ajan)           → olay: task.assigned  → durum: assigned
                  ⋮  (pano bekler — bugün burası yok, kart hemen koşuyor)
   BoardDispatcher.tick()  ── her ajan için ──> board.pick(ajan)
             └─> claims/<id>.lock  (O_EXCL)   → olay: task.claimed   → durum: TAKEN
             └─> board.start(...)             → olay: run.started    → durum: running
                  ⋮  ajan kendi terminalinde koşar, [KONTROL NOKTASI] yazar
             └─> run.finished(ok, proof)      → olay + durum: review
             └─> report_to_entropy(...)       → Entropy gelen kutusu (kind=report)
             └─> bus.task_notification        → sohbette "rapor geldi" kartı
   Kullanıcı/Entropy inceler → task.accepted  → durum: done
```

Bu akışta Entropy'nin "kendi kararıyla görev üretmesi" (G3'ün ilk yarısı) tek bir yeni araçla çözülür: Entropy'nin sohbet turunda kullanabileceği bir `board_create` çağrısı (§3.6). Bugün bunun yerine kullanıcının `/task` yazması gerekiyor.

### 3.4 Ajan kalıcılığı

Üç katman ayrı ayrı ele alınmalı; bugün üçü de karışık.

**Katman 1 — Kimlik (oturum kimliği).** `Entropy/Board/agents/<ad>/session.json`:

```json
{
  "claude": {
    "session_id": "b3f1c0de-0000-5000-a000-<uuid5(agent)>",
    "signature": "<sha1(prompt|model|effort)[:16]>",
    "model": "claude-opus-5",
    "effort": "high",
    "cwd": "C:\\EntropiAI",
    "updated_at": "2026-09-10T14:32:11"
  },
  "agy": {
    "conversation_id": "conv_9f2…",
    "signature": "…", "model": "gemini-3.8-flash-high", "cwd": "…", "updated_at": "…"
  }
}
```

İki sağlayıcı **farklı** yürür (§2.5'teki asimetri):

- **Claude:** kimlik **bizim seçtiğimiz** deterministik bir UUID olur — `uuid5(NAMESPACE_URL, f"entropy-agent:{ajan}")`. İlk koşu `--session-id <uuid>`, sonraki koşular `--resume <uuid>`. Böylece kimlik yakalama yarışı hiç doğmaz ve dosya kaybolsa bile kimlik yeniden hesaplanabilir.
- **agy:** kimlik önceden atanamaz; akıştan yakalanır (bugünkü `agy_bridge.py:1551-1554` mekanizması) ve dosyaya yazılır; sonraki koşu `--conversation <id>`.

**`cwd` alanı zorunlu** (§2.5'teki disk bulgusu): Claude oturum deposu `~/.claude/projects/<slug(cwd)>/` altında. Kart worktree'de koşuyorsa (`TaskCard.worktree`) cwd farklıdır. Kural: **ajanın kalıcı oturumu her zaman ofisin/projenin kök dizininde açılır**; worktree'de koşan kart *ayrı* ve *geçici* bir oturum kullanır (`--fork-session` ya da yeni `--session-id`), ajanın kalıcı kimliğine dokunmaz. Aksi hâlde her worktree ajanın konuşmasını başka bir klasöre dağıtır.

**Katman 2 — Süreç (terminal).** Kullanıcının "ajanlar terminallerde çalışır ve uygulama kapansa da sürer" isteği:

| İhtiyaç | Komut | Doğrulandı |
|---|---|---|
| Ajanı arka planda başlat | `claude --bg -n <ajan> --session-id <uuid> …` | `--help` |
| Yaşayanları listele | `claude agents --json` → `pid, cwd, kind, startedAt, sessionId, name` | **çalıştırıldı** |
| Terminal bölmesinde aç | `claude attach <id>` | `--help` |
| Çıktısını oku | `claude logs <id>` | `--help` |
| Durdur (konuşma korunur) | `claude stop <id>` | `--help` |
| Sürüm sonrası yeniden doğ | `claude respawn --all` | `--help` |
| Sil | `claude rm <id>` | `--help` |

`-n <ajan>` ile oturuma ajanın adı verilir → `/resume` seçicisinde ve terminal başlığında ajan adı görünür; Desk'in terminal bölmesi (`desk/terminals_panel.py`) ve piksel sahnesi (`desk/scene.py`) bunu doğrudan eşleyebilir. Uygulama açılışında `claude agents --json` çağrılıp yaşayan oturumlar `session.json` ile eşleştirilirse, **"aynı terminal sürüyor"** vaadi gerçekten karşılanır.

agy tarafında karşılığı doğrulanmadı; `agy remote-control` alt komutu (`start/status/stop`) bir arka plan daemon'ı yönetiyor ve bu yönde bir **spike** gerektirir — söz verilmemeli.

**Katman 3 — Bellek (dosya).** Kullanıcının kalıcı kuralı: *"çökme sonrası uzun sohbet günlüğünden değil, kısa durum özetinden sürdür."* Bu zaten kurulu: `record_checkpoint` (`harness.py:1024`), `resume_section` (`harness.py:1089`), kart alanı `checkpoint` (`tasks.py:196-199`). Eksik olan Entropy'nin kendi kartlarında aynı disiplin.

**Açılış uzlaştırması (G6'nın çözümü)** — `main.py:85` civarına, `mark_orphans_failed()` ile `resume_all()` arasına:

```
BoardReconciler.run():
  1. events.jsonl'i oku → eşleşmeyen run.started olan görevleri bul
  2. her biri için:
       claims/<id>.lock varsa PID canlı mı?
         canlı  → durum running kalır (süreç hâlâ koşuyor: --bg oturumu)
         ölü    → claim.expired olayı, kilit silinir
                  checkpoint varsa  → durum assigned (kaldığı yerden sürer)
                  checkpoint yoksa  → durum assigned, attempt += 1
  3. claude agents --json ile yaşayan oturumları session.json ile eşle
```

Bugünkü `resume_all` (`harness.py:2363`) bunun ofis tarafındaki karşılığı ve mantığı doğru; yapılacak iş onu genelleştirmek, `if not card.office: continue` (`:2399`) satırını kaldırıp Entropy kartlarını da kapsamak.

**Yeni oturum ne zaman açılır:** istem, sağlayıcı, model ya da efor değiştiğinde. Bugün yalnızca istem imzası kontrol ediliyor (`identity.py:506 sync_prompt`, `:500 prompt_signature`). İmza `sha1(system_prompt)` yerine `sha1(system_prompt | model | effort)` olmalı — aksi hâlde model değiştirilip `--resume` ile eski oturuma dönülünce `--system-prompt-snapshot on` yüzünden eski istem taşınır (belge alıntısı `identity.py:511-516`'da zaten var).

### 3.5 Model ve efor

**Tek kaynak: AGENT.md.** Alanlar zaten mevcut (`registry.py:139-160`): `provider, model, effort, model_agy, model_claude`.

**Yapılacak dört değişiklik:**

1. **Künyeye efor ekle.** `agent_spec_payload()` (`tasks.py:444`) `"effort": getattr(agent_spec, "effort", "")` döndürsün.
2. **Köprülere `effort=` kwarg'ı.**
   - Claude: `build_command(..., effort: Optional[str] = None)` (`claude_bridge.py:648`); `effort = <prompt /effort> or <çağrının eforu> or self.selected_effort`. Yani öncelik sırası: tek seferlik `/effort` > ajanın eforu > oturum eforu. Mevcut regex yolu (`:806-813`) korunur, yalnızca ortaya bir basamak girer.
   - agy: yeni kwarg gerekmez; `send_background_task_async` ajanın eforunu `effort_for_prompt(..., default_effort=<ajanın eforu>)`'a geçirsin (`agy_bridge.py:518-547`) — mekanizma zaten var, yalnızca kart yolundan beslenmiyor.
   - `tasks.py:1148` satırındaki isteğe bağlı kwarg süzgecine `"effort"` eklenir (`_accepts_kwarg` deseni, `tasks.py:349`).
3. **Kartta gerçek `effort` alanı.** `TaskCard.effort` eklenir; `task_board_widget.update_card_settings` (`:846-860`) `notes` hilesini bırakır. Bu, kart panosundan efor ayarlamayı **ilk kez** işlevsel kılar.
4. **`claude_agents_json`'a efor eklenmez.** Doğrulanmış gerekçe: izole kipte `--setting-sources ""` derlenmiş ajan dosyalarını okutmuyor ve `--agents` yükünün şemasında efor yok. Efor **yalnızca** `--effort` bayrağıyla taşınır. `compile.py:200-201`'deki frontmatter yazımı zararsız ama etkisiz; yorumla işaretlenmeli ki bir daha "efor akıyor" sanılmasın.

**Değişince süreç yeniden başlar** (kullanıcının açık isteği). `AgentRegistry.save()` sonrasına kanca:

```
on_agent_saved(ad, eski_spec, yeni_spec):
    if (provider|model|effort|prompt) değişti:
        1. compile_agents(...)                       # türetilmiş tanımları tazele
        2. canlı InteractiveSession varsa kapat      # provider.py:482 registry
        3. session.json içindeki imzayı düşür        # yeni oturum açılacak
        4. bus.agents_updated.emit(ad)
        5. o ajanın SÜREN kartı varsa → durum assigned (kilit bırakılır)
           bir sonraki tick yeni model/eforla, kontrol noktasından sürdürür
```

5. adım kritik: kullanıcı "gerekirse süreç yeniden başlatılır, hafıza dosyadan devam eder" dedi. Kontrol noktası zaten diskte (`checkpoint` alanı) olduğu için yeniden koşu baştan başlamaz.

**Entropy'nin kendi modeli/eforu.** `/model` ve `/effort` (`slash_commands.py:128-141`) → `config.provider_effort` zaten kalıcı. Arayüzden değiştirilebilmesi için Ayarlar'a iki satır: sağlayıcıya göre doldurulan model kutusu + efor kutusu; ikisi de `effort_selector.effort_levels_for(provider, model, bridge)`'i kullanmalı (`agents_widget.py:163-169`) ki agy'nin "efor = model son eki" gerçeği tek yerde kalsın. **İkinci bir gerçek kaynak açılmamalı**: kutu doğrudan `bridge.set_effort()` / `config`'e yazmalı, ayrı bir ayar anahtarı icat etmemeli.

**Alt ajanların eforu** aynı arayüzden: Ajanlar paneli düzenleyicisinde efor kutusu zaten var (`agents_widget.py:389-393, 449-463`) ve AGENT.md'ye yazılıyor (`registry.py:180`). Eksik olan yalnızca §3.5/1-2, yani yazılan değerin **yürütmeye ulaşması**.

### 3.6 Araç tasarımı — "ajanlara yardımcı", "tool tool tool" değil

**Mevcut yüzey envanteri:**

| Yüzey | Sayı | Kime bakar | Token maliyeti |
|---|---|---|---|
| Slash komutlar | 36 | **Kullanıcı** (yerel işlenir, model çağırmaz) | 0 |
| Yerleşik araçlar (izole kip) | ≤ 8 | Model | küçük |
| MCP çekmecesi | kapalı (`--disallowedTools "mcp__*"`) | — | ölçüm: 119 ad ≈ 2.4k token |
| Yetenek kataloğu | kapalı (`--disable-slash-commands`) | — | ölçüm: 32 yetenek ≈ 3.8k token |
| Ajan araç politikası | 4 değer | Derleme | — |
| **Pano araçları** | **0** | — | — |

**Öneri: 4 araç, `entropy_board_` ad alanında** (Anthropic ilkesi 2). Kendi MCP sunucusu olarak sunulur (`src/entropy/mcp/manager.py` altyapısı var) ve **yalnızca** izin verilen ajanlara açılır; MCP ad alanının geri kalanı kapalı kalır.

| Araç | İmza | Neden **bu** araç |
|---|---|---|
| `board_next` | `(agent, response_format="concise") -> {task_id, title, goal, criteria[], input_paths[], checkpoint?}` | **Birleştirilmiş**: listele+süz+sahiplen+taşı tek çağrıda (Anthropic'in `schedule_event` örneğinin birebir karşılığı; kanban-md'nin `pick --claim` komutunun aynısı). Yarış koşulunu tasarımdan siler. |
| `board_checkpoint` | `(task_id, done, next, files[], tests) -> {ok, checkpoint_path}` | Kontrol noktasını serbest metinden ayrıştırmak yerine **sözleşme** yapar. Bugün `[KONTROL NOKTASI]` etiketi çıktıdan regex'le çekiliyor (`harness.py:307`) — deterministik olmayan bir üreticiden deterministik bir biçim beklemek. |
| `board_finish` | `(task_id, summary, proof{command,result,green}, outputs[]) -> {ok, status}` | Close-with-proof kuralını **araç düzeyinde** dayatır: `green=false` ya da `proof` eksikse araç **reddeder** ve hata mesajı ajanı testi koşmaya yönlendirir (Anthropic ilkesi 4: hata mesajı yönlendirici olmalı). |
| `board_ask` | `(task_id, question) -> {message_id}` | Bloke etmeyen soru; `mailbox.ask_office`/`instruct_office` altyapısını kullanır (`mailbox.py:424,439`). Ajanın "takıldım" demesi için tek yol; olmadığı için bugün ajanlar tahmin üretiyor. |

Entropy'nin **kendi** turunda (ajanların değil) tek ek araç:

| Araç | İmza | Neden |
|---|---|---|
| `board_create` | `(title, goal, criteria[], agent, priority, effort?, input_paths[]) -> {task_id}` | G3'ün ilk yarısı: Entropy'nin kendi kararıyla görev üretmesi. Bugün bunun yerine kullanıcının `/task` yazması gerekiyor. |

**Açıkça REDDEDİLEN araçlar** ve gerekçeleri:

`board_list`, `board_get`, `board_search`, `board_move`, `board_set_status`, `board_assign`, `board_claim`, `board_release`, `board_priority`, `board_comment`, `board_link`, `board_stats`…

Gerekçe (Anthropic ilkesi 1 ve 3): bunların her biri ya `board_next`'in içinde birleşiktir, ya insanın işidir (`board_set_status` → `review→done` insan onayı, `tasks.py:23-26`), ya da durum makinesini **dışarıdan bozar** (`board_move` keyfi geçiş demek — geçiş tablosu anlamsızlaşır). Ajan durum makinesinin kullanıcısı değil, **konusudur**.

**Dönüş biçimi kuralları** (Anthropic ilkeleri 3-4):

- Varsayılan `concise`; `detailed` yalnızca ajan açıkça isterse
- Kimlik yerine ad: `agent: "arastirmaci"`, `agent_uuid: …` değil; `report_path` yerine göreli yol
- `board_next` en fazla **bir** görev döndürür (liste değil) — ajan zaten tek iş yapacak
- Kriter listesi 10 maddeyle, girdi yolu listesi 40 dosyayla sınırlı (mevcut `PROJECT_FILE_LIST_LIMIT = 40`, `tasks.py:85`)
- Hata mesajları yönlendirici: `board_finish` reddederken *"test komutu koşulmamış; `pytest tests/test_x.py -q` çalıştırıp `proof.command` ve `proof.result` alanlarını doldur"* der, yalnızca "geçersiz" demez

**Ölçülebilir hedef:** beş aracın toplam şema maliyeti **≤ 800 token**. Karşılaştırma çıpası kodda mevcut: kapalı MCP çekmecesi 119 araç ≈ 2.4k token. Yani beş araç, kapatılan yüzeyin üçte biri kadar bile yer tutmamalı.

---

## 4. Mevcut kodla eşleme

### 4.1 KORU (dokunma)

| Bileşen | Dosya | Gerekçe |
|---|---|---|
| Kart = ön bilgili `.md`, iki kök | `agents/tasks.py:1-70` | kanban-md ile birebir örtüşüyor; dış literatürün önerdiği biçim |
| `TaskBoard` CRUD, atomik yazım | `tasks.py:489-720` | Çalışıyor; göç makinesi dâhil |
| `_VaultWatcher` melez izleme | `agents/watchers.py:29-125` | `watchdog`'un kendi rehberinin önerdiği desen; ekleme yapma |
| `ConversationMap` + `sync_prompt` | `core/identity.py:428-560` | Snapshot tuzağını doğru çözüyor |
| Terminal olay sözleşmesi | `agents/mailbox.py:505-545` | A2A kapanış garantisi |
| Kontrol noktası / kanıt / kural disiplini | `harness.py:1024-1174`, `tasks.py:88-145` | Faz 10-A'nın en değerli parçası |
| Proje kilidi, `TaskLedger`, worktree | `core/project_lock.py`, `core/task_ledger.py`, `agents/worktrees.py` | — |
| İzole kip araç kısıtı | `claude_bridge.py:157-169`, izolasyon bloğu | Anthropic'in token verimliliği ilkesiyle uyumlu, ölçülmüş |
| Ofis harness'ı pompası | `harness.py:1704-1810` | Ofis tarafı **itmeli** kalmalı; orkestratör planı ile pano çekmesi farklı problemlerdir |

### 4.2 DEĞİŞTİR

| # | Ne | Nerede | Nasıl |
|---|---|---|---|
| C1 | Durum kümesi | `tasks.py:72` | 5 → 8 (`assigned`, `taken`, `canceled`) |
| C2 | Geçiş mantığı | `tasks.py:1087,1192,1222`, `harness.py:1826` | Tek tabloya taşı (`agents/board_fsm.py`) |
| C3 | Olay günlüğü | yeni `agents/board_events.py` | `events.jsonl` yazıcı + projeksiyon + karma |
| C4 | Kart alanları | `tasks.py:146-235` | +`priority, effort, input_paths, report_path, claimed_by, claim_expiry, event_seq` |
| C5 | Tetikleyici | yeni `agents/dispatcher.py` | `QTimer` + `bus.task_cards_updated`; `board.pick()` |
| C6 | `run()` bölünmesi | `tasks.py:1013` | `claim()` + `start()`; `run()` uyumluluk sarmalayıcısı olarak kalır |
| C7 | Efor akışı | `tasks.py:444`, `claude_bridge.py:648`, `agy_bridge.py:518` | `effort` künyeye + `build_command(effort=)` + `default_effort=` |
| C8 | Kart efor alanı | `task_board_widget.py:846-860` | `notes` hilesi kalkar |
| C9 | Açılış uzlaştırma | `harness.py:2399`, `main.py:85-90` | `if not card.office: continue` kalkar; `BoardReconciler` eklenir |
| C10 | Ajan oturum deposu | `claude_bridge.py:387`, `agy_bridge.py:278` | Bellek sözlüğünün arkasına `Entropy/Board/agents/<ad>/session.json` |
| C11 | Rapor sohbete | `tasks.py:1200` | `_finish` başarılıyken `report_to_entropy(...)` de çağırsın |
| C12 | İmza kapsamı | `identity.py:500` | `sha1(prompt)` → `sha1(prompt\|model\|effort)` |
| C13 | Ajan kaydı kancası | `registry.save`, `agents_widget` | Model/efor değişince derle + oturum kapat + imza düşür |
| C14 | Pano araçları | `mcp/manager.py` | 4+1 araç, `entropy_board_` ad alanı |

### 4.3 KALDIR

| # | Ne | Kanıt | Gerekçe |
|---|---|---|---|
| R1 | `notes: "effort: X"` sözleşmesi | `task_board_widget.py:852-854` | Hiçbir yerde geri okunmuyor; üstüne `notes` içeriğini eziyor |
| R2 | `src/entropy/tools/autonomous_agent_architecture*.py` (60 dosya) | `du -sh src/entropy/tools/` → **7.3 MB**; `grep -rn "from entropy.tools"` → yalnızca `synthesizer` | Hiçbir yerden import edilmiyor. Ayrıca içlerinde `TaskFSMState` adlı bir enum var (`autonomous_agent_architecture.py:29`) — yeni FSM ile kavramsal olarak çakışacak ve gelecekte "hangisi gerçek" sorusunu doğuracak. `docs/` altına ya da depo dışına arşivlenmeli. |
| R3 | `compile.py:200-201` efor frontmatter'ı (**yorumla işaretle, silme**) | `--setting-sources ""` onu okutmuyor | Silmek yerine "izole kipte etkisiz" notu düşülmeli; izolasyon kapanırsa işe yarar |

Not: R2'nin depo kökündeki kardeşleri de var — `module_task_*.py`, `schema_task_*.py` (git status'ta 40+ izlenmeyen dosya) ve `google_flow_files/`, `financial-auditor/`. Bunlar bu araştırmanın kapsamı dışında ama aynı temizlik turunda ele alınmalı.

---

## 5. Kabul ölçütleri

**A. Durum makinesi**
- A1. `board_fsm.TRANSITIONS` tablosu 12 satır; `STATUSES` 8 değer.
- A2. Geçersiz geçiş (`backlog → done`) `InvalidTransition` atar; test bunu doğrular.
- A3. `review → done` yalnızca `actor="human"` ile mümkün; ajan çağrısı reddedilir.
- A4. `running → review` kanıtsız yapılamaz: `proof.green != True` ise `failed`'a düşer.

**B. Olay günlüğü**
- B1. Bir kartın tam yaşam döngüsü ≥ 6 satır olay üretir (`created, assigned, claimed, started, checkpoint, finished`).
- B2. Günlük yalnızca eklenir: test dosya boyutunun monoton arttığını ve hiçbir satırın değişmediğini doğrular.
- B3. Yeniden oynatma deterministik: aynı günlükten iki kez üretilen projeksiyonun `projection_hash` değeri aynı.
- B4. Eşleşmeyen `run.started` tespit edilebilir; `BoardReconciler` onu `assigned`'a çeker.

**C. Tetikleyici ve sahiplenme**
- C1. İki `BoardDispatcher` örneği aynı kartı aynı anda alamaz (test: 8 iş parçacığı, 1 kart → tam 1 başarı, 7 `FileExistsError`).
- C2. Kirası dolmuş + PID'i ölü kilit devralınır; PID canlıysa devralınmaz.
- C3. `board.pick` sıralaması: `P0` her zaman `P1`den önce; eşitlikte `created_at`.
- C4. `entropy_max_parallel=2` iken üçüncü kart `assigned`'da bekler.

**D. Ajan kalıcılığı**
- D1. Aynı ajan iki kart üst üste koşturur; ikinci koşuda argv'de `--resume <uuid>` (Claude) ya da `--conversation <id>` (agy) bulunur.
- D2. `session.json` uygulama yeniden başlatıldıktan sonra da aynı kimliği verir.
- D3. Model ya da efor değişince imza düşer ve yeni koşu `--resume` **içermez**.
- D4. `main.py` açılışında `running` kalmış Entropy kartı `assigned`'a çekilir (bugün asılı kalıyor).
- D5. Worktree'de koşan kart, ajanın kalıcı `session_id`'sini **değiştirmez**.

**E. Model/efor**
- E1. AGENT.md'de `effort: high` olan ajanın kartı, Claude argv'sinde `--effort high` üretir (bugün oturum eforu geliyor).
- E2. Kart panosundan efor değiştirmek kart ön bilgisinde `effort:` alanını değiştirir; `notes` alanına dokunmaz.
- E3. agy kartında ajanın eforu model son ekine dönüşür (`…-high`) ve argv'de `--effort` **bulunmaz** (mevcut çakışma kuralı korunur).
- E4. Ajan düzenleyicide model değiştirilince canlı `InteractiveSession` kapanır ve süren kart `assigned`'a döner.

**F. Araçlar ve rapor**
- F1. Ajanın gördüğü pano aracı sayısı **tam 4**; Entropy'nin 5.
- F2. Beş aracın şema maliyeti ≤ 800 token (`--debug` argv/istem ölçümüyle).
- F3. `board_finish` kanıtsız çağrıda reddeder ve hata metni test komutu koşmayı söyler.
- F4. Entropy kartı bitince Entropy gelen kutusunda `kind="report"` mesaj oluşur ve sohbette rapor kartı görünür (bugün yalnızca bildirim hapı var).

**G. Regresyon**
- G1. `tests/test_agents_registry_tasks.py`, `test_office_harness.py`, `test_phase10_harness_discipline.py`, `test_ui_agents_and_task_board.py`, `test_tasks_ledger_and_project_lock.py` yeşil kalır.
- G2. Tam paket (207 test dosyası) yeşil.
- G3. `dist_check` build'i alınır ve smoke test geçer.

---

## 6. Ajan ataması ve kota tahmini

| Ajan | İş | Dosya kapsamı (ayrık) | Tahmini kart |
|---|---|---|---|
| `agy-integration-engineer` | C1-C3, C5-C7, C10, C12: FSM tablosu, olay günlüğü, dispatcher, claim, oturum deposu, köprü efor kwarg'ı | `agents/board_fsm.py`, `agents/board_events.py`, `agents/dispatcher.py`, `agents/tasks.py`, `core/claude_bridge.py`, `core/agy_bridge.py`, `core/identity.py` | 4 |
| `ui-engineer` | C4 (UI tarafı), C8, C13, Entropy model/efor ayar satırı, pano sütunları (`assigned/taken/canceled`) | `ui/widgets/task_board_widget.py`, `ui/widgets/agents_widget.py`, `ui/widgets/effort_selector.py`, Ayarlar | 2 |
| `memory-rag-engineer` | C11, `TASKBOARD.md` projeksiyonu, rapor→sohbet kartı, ajan belleği bağlantısı | `memory/office_workspace.py`, `agents/mailbox.py`, `ui/modes/chat_mode.py` | 2 |
| `qa-build-engineer` | §5'teki tüm ölçütler için test, R2 temizliği, build + smoke | `tests/`, `src/entropy/tools/` | 2 |

**Kota tahmini.** Depo kendi çıpasını veriyor: alt kart başına `SUBCARD_TOKEN_ESTIMATE = 30_000` (`harness.py:136`), kart başına adım tavanı 20 (`tasks.py:83`), ve gerçek maliyet `_office_subcard_costs` ile ledger'dan medyanla düzeltiliyor (`harness.py:191`).

- 10 uygulama kartı × ~30k ≈ **300k token**
- Test kartları genelde daha ucuz (okuma ağırlıklı): 2 × ~20k ≈ **40k**
- Değerlendirme/yeniden koşu payı (~%20) ≈ **70k**
- **Toplam ≈ 410k token**, tek sağlayıcıda tek gün içinde makul.

Riskler: (a) `claude --bg` entegrasyonu bir spike gerektirir ve öngörülemez — ayrı ve **sonraki** bir karta ayrılmalı; (b) `agy remote-control` doğrulanmadı, söz verilmemeli; (c) R2 temizliği (7.3 MB, 60 dosya) tek başına bir kart, uygulama kartlarıyla karıştırılmamalı.

**Faz sırası önerisi:**

1. **11-C.1** — FSM tablosu + durum kümesi + olay günlüğü + projeksiyon (kabul: A, B)
2. **11-C.2** — Dispatcher + atomik claim + uzlaştırıcı (kabul: C, D4)
3. **11-C.3** — Ajan oturum deposu + imza kapsamı + yeniden başlatma kancası (kabul: D)
4. **11-C.4** — Efor akışı uçtan uca + UI (kabul: E)
5. **11-C.5** — 4+1 pano aracı + rapor→sohbet (kabul: F)
6. **11-C.6** — `claude --bg` kalıcı terminal spike'ı (ayrı, sonuç açık uçlu)

---

## 7. Kaynaklar

**Anthropic mühendislik ve ürün**
- [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — araç seçimi, ad alanı, anlamlı bağlam, token verimliliği, açıklama istem mühendisliği, değerlendirmeyle yineleme
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — en basit çalışan mimari, şeffaflık, iyi araç = kuvvet çarpanı
- [Claude Code hooks reference](https://code.claude.com/docs/en/hooks) — `SessionStart/SessionEnd/Stop/SubagentStart/SubagentStop/PreCompact/PostCompact/PreModelSwitch/PostModelSwitch/TaskCreated/TaskCompleted/FileChanged` olayları, girdi alanları (`session_id, transcript_path, cwd, effort, agent_id, agent_type`), çıktı alanları (`permissionDecision, additionalContext, systemMessage`)
- [Work with sessions — Agent SDK](https://code.claude.com/docs/en/agent-sdk/sessions) — resume, fork, oturum kimliği kalıcılığının uygulamaya ait olması, cwd'ye bağlı depo anahtarı
- [Claude Code Adds Dynamic Workflows for Parallel Agent Coordination — InfoQ (2026-06)](https://www.infoq.com/news/2026/06/dynamic-workflows-claude-code/) — orkestrasyon betiği, ilerleme kaydı ile kesintiden sürdürme, `ultracode`, token uyarısı

**Yerel CLI kanıtı (bu makinede çalıştırıldı, 2026-09-10)**
- `claude --help` — `--session-id <uuid>`, `--resume`, `--fork-session`, `-n/--name`, `--bg`, `--no-session-persistence`, `--effort`, `--input-format stream-json`, `--json-schema`, `--max-budget-usd`, `--include-hook-events`, `--system-prompt-snapshot`
- `claude agents --help`, `claude attach --help` — arka plan oturum yönetimi (`attach/logs/stop/respawn/rm`)
- `claude agents --json` — gerçek çıktı: `pid, cwd, kind, startedAt, sessionId, name`
- `agy --help`, `agy -p --help` — `--conversation`, `--continue`, `--effort low|medium|high`, `--input-format stream-json` (NDJSON stdin), `--json-schema`, `--project`, `remote-control` daemon
- `~/.claude/projects/<slug(cwd)>/<session-uuid>.jsonl` — oturum deposunun cwd'ye göre anahtarlandığının disk kanıtı

**Dosya tabanlı panolar**
- [kanban-md — File-based Kanban for AI agents and humans](https://github.com/antopolskiy/kanban-md) — `tasks/*.md` + YAML ön bilgi (`claimed_by`, `claim_expiry`), `pick --claim`, `claim_timeout`, `require_claim`, `wip_limits`, `handoff`
- [kanban-md belgeleri](https://antopolskiy.github.io/kanban-md/)
- [The Case for Markdown as Your Agent's Task Format](https://dev.to/battyterm/the-case-for-markdown-as-your-agents-task-format-6mp)
- [I Let AI Agents Manage Themselves with a Markdown File](https://dev.to/battyterm/i-let-ai-agents-manage-themselves-with-a-markdown-file-5547)

**Olay kaynağı / append-only günlük**
- [ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering (arXiv 2602.23193)](https://arxiv.org/html/2602.23193) — `activity.jsonl`, olay alanları, `projection_hash_sha256`, `claim`/`complete`, CS2 ölçümleri (50 görev / 86 olay / 4 ajan / 0 reddedilen çıktı)
- [ESAA-Conversational: An Event-Sourced Memory Layer for Continuity, Handoff, and Curation (arXiv 2606.23752)](https://arxiv.org/pdf/2606.23752)
- [Give Agents an Append-Only Event Log — Patrick Hughes (2026)](https://bmdpat.com/blog/ai-agent-event-log-observability-2026) — dört olayla başla, asla düzenleme, eşleşmeyen `run.start` = çökme
- [Agent State as Event Stream: Why Immutable Event Sourcing Beats Internal Agent Memory (2026-04)](https://tianpan.co/blog/2026-04-10-agent-state-event-stream-immutable-event-sourcing)
- [Event sourcing for LLM applications — The Hopium Lab](https://thehopiumlab.com/whiteboard/event-sourcing-for-llm-applications)
- [agentlog — append-only JSONL event bus for AI agents](https://github.com/sumant1122/agentlog)

**Durum makinesi kütüphaneleri**
- [python-statemachine (PyPI)](https://pypi.org/project/python-statemachine/) — parametre enjeksiyonlu geri çağrılar, hiyerarşik durumlar, History pseudo-state
- [python-statemachine — Coming from pytransitions](https://python-statemachine.readthedocs.io/en/v3.0.0/how-to/coming_from_transitions.html)
- [pytransitions/transitions](https://github.com/pytransitions/transitions) — `prepare_event`/`finalize_event`/`on_exception`, geçiş sonrası istisnada rollback olmaması

**Dosya izleme**
- [watchdog (PyPI)](https://pypi.org/project/watchdog/) ve [belgeler](https://python-watchdog.readthedocs.io/en/stable/api.html) — `ReadDirectoryChangesW` sınırları, `PollingObserver` yedeği
- [Issue #391 — Lots of missing events when using not PollingObserver](https://github.com/gorakhargosh/watchdog/issues/391)
- [Issue #452 — Polling Observer crashes on network loss](https://github.com/gorakhargosh/watchdog/issues/452)

**Çoklu ajan çerçeveleri**
- [Multi-Agent Orchestration Frameworks 2026 (LangGraph, CrewAI, AutoGen, Swarm)](https://presenc.ai/research/multi-agent-orchestration-frameworks-2026)
- [LangGraph vs CrewAI vs AutoGen vs Swarms Comparison 2026](https://www.buildmvpfast.com/blog/langgraph-vs-crewai-vs-autogen-swarms-agent-framework-2026)
- [LangGraph vs CrewAI vs AutoGen vs Swarm: The 2026 Comparison](https://app.ailog.fr/en/blog/guides/agent-frameworks-comparison-2026)
- [The OpenHands Software Agent SDK (arXiv 2511.03690)](https://arxiv.org/pdf/2511.03690)

**Depo içi kanıt (dosya:satır)**
`agents/tasks.py:54,70,72,83,85,146-235,349,383,413,444,458,489-720,723,950,1013,1087,1115,1148,1167,1192,1200,1222,1238` ·
`agents/watchers.py:29,38,54,127,160` ·
`agents/harness.py:116,121,125,136,374-378,478,490,507,551,1024,1089,1229,1704,1725,1792,1826,2224,2363,2399,2473` ·
`agents/registry.py:26-30,139-160,180` ·
`agents/compile.py:142-147,200-201,246-268,279-283` ·
`agents/mailbox.py:424,439,467,505` ·
`core/event_bus.py:47-63,69-76,117,123,127,141-144` ·
`core/identity.py:428,442,485,500,506,665,722-762` ·
`core/claude_bridge.py:157-169,343-346,387,648-665,806-813,1979,2219,2299` ·
`core/agy_bridge.py:177-185,278,518-547,556,954,1092,1329,1551-1554` ·
`core/provider.py:47-56,211,258,334,338,359,482` ·
`core/task_ledger.py:13-19,326-345,356` ·
`core/slash_commands.py:128-141,180-240,524-601,1059,1300-1330` ·
`scheduler/cron_engine.py:14,27` ·
`ui/widgets/task_board_widget.py:529,846-860,884,904` ·
`ui/widgets/agents_widget.py:153,389-393,449-463,1388-1400` ·
`ui/widgets/tasks_widget.py:419,436` ·
`ui/modes/chat_mode.py:867` ·
`main.py:85,109-123,154-155,161`
