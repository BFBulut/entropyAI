# Entropy AI — Yaşayan Mimari

> **Bu dosya kaynağın kendisiyle birlikte güncellenir.** Bir sözleşme değişirse (paket yeri,
> veri kökü, sinyal adı, kart alanı) aynı commit'te burası da değişir. Eskimiş bir mimari
> belgesi olmamasının tek yolu budur; `docs/_archive/prototype/` altındaki eski belgeler
> tam olarak bu kural uygulanmadığı için arşive düştü.
>
> Sürüm: v0.9.4 · Dal: `ai/v0.1.7` · Son güncelleme: 2026-09-10 (Faz 12-E)
> Güncel durum ve açık işler için: [`STATE.md`](STATE.md) · Kararlar için: [`adr/`](adr/)

---

## 1. İki ürün, tek depo

| | Entropy AI | Entropy Agent Desk |
|---|---|---|
| Ne | Kişisel, kendi kendini geliştiren yapay zeka: beyin (RAG + hafıza), kendi ajanları, görev panosu, üç arayüz kipi | Entropy'nin **içine gömülü ayrı uygulama**: ofisler, orkestratörler, terminallerde yazılım geliştiren alt ajanlar |
| Kod | `src/entropy/{core,agents,memory,skills,ui,mcp,scheduler,platform,tools}` | `src/entropy/desk/` + `src/entropy/agents/{desk_registry,harness,offices,worktrees,pr_flow,templates}.py` |
| Veri kökü (kasa) | `<kasa>/Entropy/**` | `<kasa>/Desk/**` |
| Ajanları | `Entropy/Agents/<ad>/AGENT.md` | `Desk/Offices/<ofis>/agents/**` |

**Bilgi tek yönlüdür.** Entropy Desk'in mimarisini bilir ve onu geliştirebilir; Desk
Entropy'nin mimarisini **bilmez**. Orkestratör istemlerinde Entropy'nin adı geçmez.
**Görev akışı da tek yönlüdür:** Entropy Desk orkestratörlerine görev/mesaj gönderir ve
rapor alır; Desk Entropy'nin panosuna kart **itemez**. Gerekçe ve zorlayıcı testler:
[ADR-0001](adr/ADR-0001-desk-ayrimi.md), `tests/contracts/test_phase9_desk_separation.py`.

---

## 2. Paketler

| Paket | Dosya | Satır | Rol |
|---|---:|---:|---|
| `ui/` (+ `modes/`, `widgets/`, `themes/`) | 37 | ~20.700 | PySide6 kabuğu: Zen / Chat / Floating kipleri, 29 widget |
| `memory/` (+ `rag/`, `obsidian/`, `supabase/`) | 22 | ~13.800 | bilişsel bellek, graf, wiki, playbook, bağlam kurucu, ofis çalışma alanı, damıtıcı |
| `core/` | 15 | ~11.700 | yapılandırma, olay veriyolu, iki sağlayıcı köprüsü, slash komutlar, kilit, kimlik, defter |
| `agents/` | 13 | ~8.500 | ajan kayıt defteri, derleme, görev kartları, harness, posta kutusu, worktree, PR akışı, şablonlar |
| `desk/` (+ `engine/`, `assets/`, `templates/`) | 20 | ~6.700 | Agent Desk penceresi, piksel sahne motoru, paneller |
| `skills/` | 5 | ~2.000 | `SKILL.md` keşfi (`manager.py`) + motorlar (tembel yüklenir) |
| `mcp/` · `scheduler/` · `platform/` · `tools/` | 8 | ~1.000 | MCP yapılandırması, zamanlayıcı, Windows panosu (`platform/clipboard.py`), araç sentezleyici |

**Deneysel, ürüne bağlı değil:** `core/claude_bg.py` (741 satır, Faz 11-F kalıcı terminal
spike'ı) üründen çağrılmaz ve `EntropyAI.spec` hiddenimports'ta **yoktur** → `.exe`'ye
girmez; yalnız `tests/test_phase11_claude_bg.py` doğrular ([ADR-0007](adr/ADR-0007-claude-bg-ertelendi.md)).
`platform/autostart.py` **kaldırıldı** — ayar vardı, davranış yoktu
([ADR-0006](adr/ADR-0006-autostart-kaldirildi.md)).

Giriş noktaları: `run_entropy.py` → `entropy.main:main`; `pyproject.toml`
`[project.scripts] entropy = "entropy.main:main"`; paketleme `EntropyAI.spec`.

> **`EntropyAI.spec` hiddenimports bir dizgi listesidir.** Bir paket yalnızca
> `importlib` ile çağrılıyorsa PyInstaller'ın statik tarayıcısı göremez ve `.exe`
> **sessizce eksik** paketlenir (Faz 10-C'de worktree/PR/şablon/makbuz yolları böyle
> kapanmıştı). Yeni bir tembel modül eklendiğinde spec'e satır eklemek zorunludur.
> Aynı nedenle `skills/__init__.py` PEP 562 `__getattr__` ile tembel yüklenen
> `media_agency_soldier` motorunu spec'teki hiddenimports satırı ayakta tutar.

---

## 3. Veri kökleri

### 3.1 Uygulama durumu — `~/.entropy` (kullanıcı verisi, ASLA silinmez)

`core/config.py:_resolve_state_dir()` sırası:

1. `ENTROPY_HOME` ortam değişkeni,
2. `APP_ROOT/.entropy` (varsa — kurulu sürümlerin verisi taşınmadan çalışsın diye),
3. `%LOCALAPPDATA%\EntropyAI` (Windows) / `~/.entropy`.

İçerik: `settings.json`, `chat_history.json`, `logs/`, `payloads/`, rapor indeksi,
`workspace/` (Claude Saf Kip'in nötr çalışma dizini), `external/` (depo dışına
taşınmış kullanıcı ve üçüncü taraf çıktıları).

### 3.2 Obsidian kasası — insan arayüzü ve soğuk depo

`core/config.py:_default_obsidian_vault()`; `ENTROPY_VAULT_PATH` ile geçersiz kılınır.

```
<kasa>/
├── Entropy/                 # Entropy AI'nin KENDİ verisi
│   ├── Agents/<ad>/AGENT.md         kaynak ajan tanımı (kullanıcı Obsidian'da düzenler)
│   ├── Agents/<ad>/inbox/           posta kutusu (<ts>-<id>.json)
│   ├── Tasks/<id>.md                görev kartları (YAML ön bilgi + gövde)
│   ├── Reports/                     ajan raporları
│   ├── Memory/                      MEMORY.md, wiki, playbook
│   ├── Inbox/
│   └── _archive/
└── Desk/                    # Agent Desk'in KENDİ verisi (Faz 10-B'de taşındı)
    ├── Offices/<ofis>/      BOARD.md, ARCHITECTURE.md, RULES.md, cards/, agents/, checkpoints/
    ├── Templates/           ekip şablonları (tohum ofis DEĞİL)
    └── _migrations.log
```

Desk kökü kasa **kökünde** durur (`Entropy/Desk` değil): doğuş talimatı alt ajanlara mutlak
yol verdiği için klasör adı istemin içine sızıyor ve "Desk Entropy'yi bilmez" sözleşmesini
deliyordu (`core/paths.py` modül başlığı). Geçiş sözleşmesi: **kopyala → doğrula → sil**,
idempotent, `dry_run=True` varsayılan.

### 3.3 Türetilmiş ajan tanımları (proje kökünde)

`agents/compile.py` her ajanı iki sağlayıcı biçimine derler
(`core/provider.py:AGENT_DEFINITION_LAYOUT`):

```python
AGENT_DEFINITION_LAYOUT = {
    "agy":    (".agents/agents", "agent.md"),
    "claude": (".claude/agents", None),
}
```

**Kaynak tek: kasa.** Derleme çıktısı türetilmiştir ve sürüm denetimine girmez.
Faz 11-A'dan beri derleme kökleri **proje kökü + ayarlardaki etkin proje + nötr Claude
çalışma dizini**; `APP_ROOT` listede **değildir**. Gerekçe `compile.py:compile_roots()`
docstring'inde: kaynaktan koşarken APP_ROOT deponun kendisi olduğu için Entropy'nin kendi
kadrosu (`analist`, `arastirmaci`, `degerlendirici`, `orkestrator`, `yazar`) deponun
`.claude/agents/` klasörüne düşüyor ve kullanıcının geliştirme alt ajanlarıyla karışıyordu.
Depodaki `.claude/agents/` artık **yalnızca kullanıcının 6 geliştirme ajanını** taşır.

---

## 4. Sağlayıcı köprüleri ve Entropy Saf Kip

İki köprü, tek soyutlama: `core/provider.py`. **Hiçbir API anahtarı kullanılmaz**; her ikisi de
kullanıcının abonelik oturumuyla koşar.

### 4.1 Claude köprüsü — `core/claude_bridge.py` (izolasyon sağlam)

| Bayrak | Etki |
|---|---|
| `--system-prompt-file` | varsayılan sistem istemini **değiştirir** (eklemez) → Entropy kendi kimliğiyle konuşur |
| `--setting-sources ""` | kullanıcı/proje/yerel ayarlar ve keşfedilen ajanlar yüklenmez |
| `--strict-mcp-config` + `--mcp-config` | yalnızca Entropy'nin MCP sunucuları |
| `--agents <json>` | Entropy kendi kadrosunu enjekte eder |
| `CLAUDE_CONFIG_DIR` | yeniden yazılır (profil sızıntısı yok) |
| `run_cwd()` | çalışma dizini **git deposunun dışında** (`~/.entropy/workspace`); CLI proje kimliğini literal cwd'den değil git kökünden çözdüğü için depo içi bir alt klasör izolasyon sağlamaz. İstisna: kart bir worktree'ye bağlıysa cwd o worktree'dir. |

**Bilinen boşluk:** `--setting-sources ""` ayar kaynaklarını kapatır ama **kök `CLAUDE.md`
otomatik keşfi ayrı bir mekanizmadır** ve `--add-dir` kökleri de CLAUDE.md dizini sayılır.
Depoda `CLAUDE.md` bulunmadığı için bugün sızıntı yoktur; bu yüzden dosya **bilerek
oluşturulmamıştır** ([ADR-0002](adr/ADR-0002-claude-saf-kip.md)).

### 4.2 agy köprüsü — `core/agy_bridge.py` (izolasyon yok — kayıtlı sınır)

Süreç doğrudan proje dizininde koşar (`cwd=project_dir`) ve ajan keşfi çalışma dizinine
dayanır. agy ikilisinde `--setting-sources` / `--strict-mcp-config` karşılığı **yoktur**;
bu, mevcut CLI ile kapatılabilir bir açık değil, belgelenmesi gereken bir sınırdır.
Efor ayrı bir bayrak değil **model varyantı** olarak geçirilir (v0.7.1).

---

## 5. Beyin: hafıza katmanları

| Katman | Nerede | Ne tutar |
|---|---|---|
| Bilişsel bellek (12 katmanlı, çift depo) | `memory/supabase/cognitive_memory.py` — yerel SQLite + isteğe bağlı pgvector | düğümler, gömmeler, hibrit recall (semantik + sözcüksel) |
| Bilgi grafı | `memory/graph_store.py`, `graph_enrich.py`, `office_graph.py` | düğüm-kenar grafı, PPR benzeri genişletme, topluluklar |
| Wiki (derlenmiş bilgi) | `memory/wiki.py`, `lint.py` | raporlardan damıtılmış kalıcı maddeler |
| Playbook (yordamsal) | `memory/playbook.py` | "bu iş nasıl yapılır" — yetenek başına yordam |
| Kalıcı notlar | kasada `MEMORY.md` | kullanıcının elle düzenlediği gerçek |
| Ofis çalışma alanı | `memory/office_workspace.py` | `BOARD.md`, `ARCHITECTURE.md`, `RULES.md`, `checkpoints/<kart-id>.md` |
| Uzlaştırma | `memory/reconcile.py` | "bunu zaten biliyorum" denetimi (bugün yalnızca graf katmanına bağlı — Faz 11-B'nin ana işi) |
| Damıtma / rapor akışı | `memory/distiller.py`, `report_watcher.py`, `handoff.py` | rapor → wiki/playbook hattı |

**Bağlam kurucu** (`memory/context_builder.py`) sabit bir token bütçesini
(`DEFAULT_TOKEN_BUDGET = 4000`) öncelik sırasıyla doldurur: playbook → hibrit recall →
rapor alıntıları → kalıcı hafıza. Maliyet kasanın büyüklüğünden bağımsızdır.

**Onaylı kurallar** (`memory/promoted_rules.py`): ajan bir kural keşfettiğinde uygulama
kullanıcıya sorar; yalnızca "kalıcı yap" denince kural o ajanın sistem istemine her koşuda
enjekte edilir. Ajanlar hata ve günlük **yazmaz**.

### 5.1 Beyin v2 — yazma kapısı, kategoriler, turlar (Faz 11-B/C/D, **kod**)

**Yazma kapısı** `memory/gate.py` — hafızaya giden **tek** yol.
`MemoryGate.admit(category, content, importance=0.5, metadata=None, provenance="")
-> GateDecision`; `action ∈ {add, noop, gray, supersede, reject}`.
Bantlar: `cos ≥ 0.95` NOOP · `cos < 0.80` ADD · arası **gri bant** (düğüm yazılır
**ve** kuyruğa girer: `<db klasörü>/memory/gray_queue.jsonl`).
`record_memory` / `store_node` bu kapıdan geçer. **Kapı iki kez koşmaz:** kararı
çağıran aldıysa `record_memory(..., decision=<GateDecision>)` ya da
`CognitiveMemorySystem.store_decision(decision)` kullanılır (aynı metin iki kez gömülmez).
Bayraklar: `ENTROPY_MEMORY_GATE=0` kapıyı atlar, `ENTROPY_MEMORY_GATE_STRICT` katı kipi zorlar.

**Kategori kapalı kümesi** `memory/categories.py` →
`CANONICAL_CATEGORIES = ("working", "episodic", "semantic", "procedural")`.
Kimlik/kural (L4) **kategori değil bayraktır**: `is_identity`; kaynağı
`gate.IDENTITY_PROVENANCE = "identity:core"`. Eski 13+ ad `LEGACY_CATEGORY_MAP` ile
eşlenir, ham değer `metadata.legacy_category`'de kalır. Şema v2 sütunları:
`provenance, confidence, valid_from, valid_to, archived, novelty, is_identity`.
Kaynağı hiç kaydedilmemiş eski L2 düğümlere uydurma kaynak **yazılmaz**:
`gate.LEGACY_PROVENANCE = "legacy:pre-v2"`, `confidence = 0.40`.

**Rüya döngüsü** `memory/dream.py` —
`dream_and_consolidate(memory=None, send_prompt=None, vault_path=None, ...) -> DreamReport`.
Altı adım: yeniden gömme → gri bant turu → `cos ≥ 0.95` kopya birleştirme (LLM'siz) →
ölçülü unutma (`forget_stale`: önem < 0,35 **ve** `access_count ≤ 1` **ve** 30 gün →
`archived=1`, **silme yok**, `is_identity` muaf) → wiki yükseltme adayı → graf
konsolidasyonu. Zamanlanmış görev: `ensure_daily_dreaming_task(scheduler=None, hour=4)`
(idempotent, `bootstrap.ensure_memory_tasks()` çağırır).

**Gri bant birleştirme turu** `memory/gray_merge.py` —
`run_merge_round(memory=None, send_prompt=None, limit=8, ...) -> MergeResult`.
N aday **tek istemde**; yanıt `{"decisions":[{"id","action","content","reason"}]}`,
`action ∈ {merge, keep_both, supersede}`. `send_prompt=None` ise **kuru koşum**
(kuyruk boşaltılmaz, model çağrılmaz). Sağlayıcı seçimi çağıranındır.

**Wiki derleme hattı** `memory/wiki.py` —
`compile_skill(skill, bridge=None, budget_turns=8, ...) -> dict`. **Rapor başına bir tur**,
artımlı (`WIKI.state.json` işlenen rapor kümesini tutar), `bridge=None` ise model
çağrılmaz (yalnız playbook tabanlı sayfalar + indeks + lint).

**Öz-amplifikasyon kilidi** `agents/amplification.py` — üç kapı: (a) açık tespiti
(`brain_has_answer` ise kart CLI'ya gitmez, `review`e düşer), (b) yenilik kotası
(`MIN_NOVELTY_RATIO = 0.30` altında aynı konudaki zamanlanmış görev kapatılır, silinmez),
(c) kaynak zorunluluğu. `config.amplification_lock=False` kilidi kapatır.

**Geri çağırma kapsamı:** `hybrid_recall(query, top_k, min_threshold, categories=None,
include_episodic=False, expand_graph=False)` — varsayılan **L2+L3**, `archived=1` indekse
girmez. CRAG sinyali: `AssembledContext.brain_confidence` + `brain_has_answer`
(`CRAG_MIN_SCORE = 0.45`). Genel sohbet beyin paketi `BUDGET_GENERAL_BRAIN = 1500`
yalnız `skill_name` boşken ödenir.

**Ölçüm paketi (kalıcı, tek kaynak `scripts/brain_metrics.py`):** K1 yineleme, K2 Hit@1/@5,
K3 gürültü, K7 kategori disiplini, K9 gri kuyruk, K10 fikstür sızıntısı, K11 kapı gecikmesi,
K12 kaynaksız L2. Sözleşme testleri `tests/contracts/test_phase11_brain_metrics.py` (12) ve
`test_phase11_memory_isolation.py` (11). Betik **salt okunur** (`mode=ro`).

Hafızanın algoritma kararı: [ADR-0003](adr/ADR-0003-hafiza-algoritmasi-mem0-degil.md).

---

## 6. Görev panosu, kartlar ve harness

### 6.1 Kart = dosya

`agents/tasks.py` — her kart `<kasa>/Entropy/Tasks/<id>.md`, YAML ön bilgi + gövde.
Neden dosya: kullanıcı Obsidian'da düzenleyebilsin ve iki taraf da aynı gerçeği görsün.

Ön bilgi alanları (`TaskCard`): `id, title, status, agent, provider, model, skill, created_at,
started_at, finished_at, output_paths, summary, office, project, parent, children, grade,
verdict, attempt, budget_tokens, intent, checkpoint, proof, worktree, branch, pr_url`
+ **Faz 11-C**: `effort, priority, input_paths, report_path, claimed_by, claim_expiry,
event_seq`; ayrıca `kind` (`"research"` ya da boş).
Gövde: `## Hedef / ## Kabul ölçütleri / ## Notlar / ## Sonuç`.
Ofis kartları ayrı depoda: `<ofis>/cards/`.

### 6.1.1 Entropy Board — durum makinesi, olay günlüğü, tetikleyici (Faz 11-C, **kod**)

**Pano kökü** `<kasa>/Entropy/Board/` (`core/paths.py`: `BOARD_SUBDIR`,
`board_events_path()`, `board_taskboard_path()`, `board_claims_dir()`,
`board_agents_dir()`, `agent_session_path()`, `board_projection_path()`).
**Kartlar taşınmadı** — `Entropy/Tasks/` altında kalır.

**Durum makinesi** `agents/board_fsm.py` tek kaynaktır (kütüphane YOK):
`STATUSES` (8), `EVENTS` (12), `TRANSITIONS` (12 satır),
`transition(card, event, payload)`, `InvalidTransition`, `reset()`.

```
backlog → assigned → taken → running → review → done | failed | canceled
```

`review → done` yalnızca `actor="human"` + kanıt ile; `run.finished` kanıt `green=False`
ise `failed`. **Ajansız `backlog` kart koşmaz.**

**Olay günlüğü** `agents/board_events.py` — `events.jsonl`, **yalnızca ekleme**; satır şeması
`{schema_version, seq, ts, correlation_id, task_id, attempt_id, actor, action,
idempotency_key, payload}`. `projection_hash` = kanonik JSON + SHA-256;
`TASKBOARD.md` bu günlükten **türetilir** (gerçek kaynak değildir).

**Tetikleyici** `agents/dispatcher.py` — `BoardDispatcherCore(board, registry, vault_path,
runner, claim_timeout_s, max_parallel)` Qt'siz çekirdek (`tick() -> [kart_id]`,
`pick(agent)`, `reconcile() -> [kart_id]`) + `BoardDispatcher` QTimer sarmalı
(`board_dispatcher()` tekil). Sahiplenme atomiktir: `claims/<id>.lock`, `O_CREAT|O_EXCL`.
Açılış kablolaması `agents/bootstrap.start_board_dispatch(app)` → **önce `reconcile()`,
sonra `start()`**; `app.aboutToQuit` kancasına `dispatcher.stop`. Hata YÜKSELMEZ,
`DispatchStartResult.summary()` metnine düşer.

**Ajan oturum deposu** `core/identity.AgentSessionStore` →
`Entropy/Board/agents/<ad>/session.json`
`{provider: {session_id|conversation_id, signature, model, effort, cwd, updated_at}}`.
Claude kimliği `uuid5("entropy-agent:<ad>")`; `run_kwargs()` yeni oturumda
`{"session_id"}`, sürdürmede `{"conversation_id"}` döndürür. İmza
`sha1(kimlik istemi|model|efor)` — kart istemine **bağlı değildir**, yoksa `--resume`
hiç kullanılmaz. İmza düşerse **taze uuid4** üretilir (aynı `session_id`'yi yeniden
vermek CLI'da `Session ID is already in use` hatasıydı).

**Pano araçları** `agents/board_tools.py` — ajanda 4 (`board_next`, `board_checkpoint`,
`board_finish`, `board_ask`), Entropy'de +`board_create`. Taşıma biçimi
`[PANO <araç>] {json} [/PANO]`; **kanıtsız `board_finish` reddedilir** (kart `review`de kalır).

**Pano sinyalleri:** `board_state_changed(dict)` = `{card_id, status, event, agent, office,
title}`; `task_report_ready(dict)` = `{card_id, title, agent, status, ok, summary,
report_path, output_paths}`.
**Pano ayarları:** `board_auto_dispatch` (True), `board_dispatch_interval_s` (3),
`board_claim_timeout_s` (3600), `entropy_max_parallel` (2), `amplification_lock` (True).
**Yerel slash komutları:** `/board`, `/board pick <kart> <ajan>`, `/board auto on|off`,
`/lock on|off`, `/model [<ad>]`, `/agent effort|model <ad> <değer>`,
`/memory merge`, `/memory dream`, `/wiki compile <yetenek> [--turns N]`.

### 6.2 Ofis harness'ı — `agents/harness.py`

Zincir: **planla → paralel koş → notla → kapat**. Dosya tabanlıdır, kesintiden devam eder.

- `ensure_workspace()` ofis kökünde BOARD/ARCHITECTURE/RULES üretir,
- `spawn_instruction()` (`SPAWN_INSTRUCTION_MAX_CHARS = 1200`) her alt ajana ilk iş olarak
  "panoyu ve mimariyi oku" talimatını mutlak yolla verir,
- `render_board()` kartlardan `BOARD.md` projeksiyonunu üretir,
- **kanıtla kapat:** bir işçi testleri koşup yeşil sonucu raporuna iliştirmeden kartı `done`
  yapamaz; kanıt `proof_recorded` sinyaliyle görünür,
- **denetim noktası disiplini:** her modülden sonra kısa durum özeti diske yazılır
  (`checkpoint_written`); çökme sonrası uzun sohbet günlüğünden değil bu özetten devam edilir,
- kart başına git worktree (`agents/worktrees.py`, komşu `.entropy-worktrees/`), PR akışı
  (`agents/pr_flow.py`: önce yerel dal + diff, onaydan sonra push).

**Orkestratör kod yazmaz.** Araştırır, planlar, kendi alt ajanlarını oluşturur/düzenler,
raporlar; araç politikası salt okunurdur.

---

## 7. Olay veriyolu sözleşmesi — `core/event_bus.py`

Arayüz ile çekirdek arasındaki tek bağ. **Sinyal adı ve imzası bir sözleşmedir**; değişirse
bu tablo aynı commit'te güncellenir.

| Alan | Sinyaller |
|---|---|
| Kip / çekirdek | `mode_requested(str)`, `mode_changed(str)`, `core_pulse_triggered(float)`, `core_state_changed(str)` |
| Akış | `model_detected(str)`, `token_chunk_received(str)`, `terminal_output_received(str)`, `token_usage_updated(int)`, `token_usage_detail(dict)`, `agent_turn_started(str)`, `agent_turn_completed(str)`, `agent_stream(dict)` |
| Proje / bağlam | `project_changed(str)`, `context_pressure(float)`, `chat_history_updated()`, `chat_history_cleared()` |
| Araç onayı | `tool_approval_requested(str, str, str)`, `tool_approval_responded(str, bool)` |
| Görevler | `task_triggered(str, str)`, `task_completed(str, bool)`, `task_notification(str, str, str)`, `task_followup_completed(dict)`, `task_cards_updated(str)` |
| Bilgi | `report_created(str)`, `node_selected(str)`, `knowledge_graph_updated()`, `cognitive_memory_updated()`, `skills_updated()`, `skill_detected(str, float)`, `playbook_updated(str)`, `reports_updated(str)`, `distill_progress(str, int, int)`, `report_inbox_unread(int)` |
| Ajanlar / ofisler | `agents_updated(str)`, `offices_updated(str)`, `office_progress(str, str, str)`, `mailbox_updated(str, str)`, `rules_updated(str, int)`, `checkpoint_written(dict)`, `proof_recorded(dict)` |
| Hata / sağlayıcı | `memory_error(dict)`, `provider_status_updated(str, dict)`, `mcp_servers_updated()` |
| İş parçacığı | `call_on_main(object)` — GUI dokunuşları daima ana iş parçacığında |

---

## 8. Arayüz

Üç kip: **Zen** (tam pano), **Chat** (sohbet öncelikli), **Floating** (küçük yüzen pencere) —
`ui/modes/`. 29 widget `ui/widgets/` altında.

**Korunan kimlik öğeleri (Faz 13, sadeleştirme turları bunları kaldıramaz).**
Aşağıdaki üç öğe dekor değil **kimlik + durum göstergesidir**; yoğunluk sayacını
düşürmek için silinemez, ancak yeniden tasarlanabilir:
(1) **Çekirdek görselleştirici** (`ui/widgets/core_visualizer.py`, Zen sohbetinin
rezerve üst şeridinde, ≥ 48 px, ayardan gizlenebilir — sözleşme testi
`tests/ui/test_phase13_ux.py`); (2) **marka kümesi** (`brandCluster`);
(3) **model kapsülü** (`modelCapsule` — hangi modelin konuştuğu her an görünür).
Bir tur bu öğelerden birini küçültürse gerekçesini faz raporuna yazar.

### 8.1 Tasarım sistemi (Faz 11-E, **sözleşme**)

**Tek belirteç kaynağı** `ui/design/tokens.py` → `TOKENS`. Aileler: `color` (12 arayüz
rengi), `space` (1..6 → 4/8/12/16/24/32), `radius` (sm/md/lg), `type`
(title/heading/body/…) ve **ayrı** `TOKENS["viz"]` — görselleştirme paleti
(`add/del/hunk/meta`, `kind1..kind7`, `neutral`). `viz` arayüz renklerine **karışmaz**:
yalnızca veri kodlar (diff boyaması, graf düğüm türü, akış olayı).
**Gövde kodunda ham hex yasak** (Desk'te hex 17 → 0); ihlali `scripts/ui_audit.py` yakalar.

**Tek QSS girişi** `ui/design/qss.py` (yerel stil sayfası 222 → 1). Widget stil **yazmaz**,
Qt **özelliği** verir: `role` (`panel|card|title|heading|label|mono|icon|badge|toast|
statusDot|toolbarGroup`), `variant` (`primary|ghost|danger`),
`tone` (`ok|warn|danger|muted|accent`). Yeni görünüm gerekiyorsa QSS'e seçici eklenir,
widget'a `setStyleSheet` yazılmaz.

**İkonlar** `ui/design/icons.py` — QtAwesome (MIT) Codicons ailesi; QtAwesome yoksa
`icon()` boş `QIcon` döndürür ve arayüz çalışmaya devam eder. Font `.ttf`/charmap `.json`
dosyaları `EntropyAI.spec` `datas`'ına **koşullu** eklenir (paketlenmezse ikonlar boş çıkar).

**Kapılar (test edilen değişmezler):**

| Kapı | Kural |
|---|---|
| Üst çubuk | her kip `self.header_items` kurar, **öğe sayısı ≤ 4**; pencere denetimleri sayılmaz. Çubuktan kaldırılan HER işlevin komut paletinde karşılığı olmak zorundadır (IA-9) |
| Dikey gezinme | `ui/widgets/nav_list.NavList` (`QListWidget` + `QStackedWidget`), `QTabWidget` API'siyle uyumlu (`addTab(widget, label, icon_name)`, `count()`, `tabText(i)`, `setCurrentIndex(i)`, `currentChanged(int)`). Zen'de **7 bölüm**; palet anahtarları `nav_*` bu sırayı izler |
| Palet | `_collect_palette_items()` → `{"kind":"action","label","subtitle","payload"}`; `run_palette_action(key) -> bool` (bilinmeyen anahtar `False`). Zen ve Chat aynı sözleşmeyi paylaşır |
| Odak halkası | odaklanabilir her denetimin QSS `:focus` halkası **ve** `setAccessibleName` değeri vardır (WCAG 4.1.2) |
| Emoji | gövde metninde çıplak emoji yok; işaretler `CHECK_ON="[x]"` / `CHECK_OFF="[ ]"` + `tone` rengi |

Gerekçe: [ADR-0005](adr/ADR-0005-tasarim-sistemi-kendi-belirtecler.md).

---

## 9. Test düzeni

```
tests/
├── conftest.py        kasa + ~/.entropy + ayar yalıtımı (testler ASLA gerçek kasaya yazmaz)
├── contracts/         kalıcı ürün sözleşmeleri (eski test_phase*) + test_architecture_rules.py
├── ui/                PySide6 / offscreen arayüz testleri
├── desk/              Agent Desk: ofisler, harness, sahne, pencere
├── skills/            skills/** paketleri
├── _reference/        (Faz 12-E) sevk edilen kodu SINAMAYAN, kendi kendine yeten
│                      ispat defterleri: 82 dosya / 563 test, `entropy.*` içe aktarmaz
└── (kök)              modül düzeyi testler
```

Koşum: `QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider`.
Yalnız ürün süiti: `pytest tests --ignore=tests/_reference -q`.
Güncel test sayısı `STATE.md`'dedir.

**Neden `_reference/` ayrıldı:** hız değil (563 test ≈ 7 s, süitin %1,7'si), **ölçüm
dürüstlüğü** — kökte dururken "süit yeşil" cümlesi ürün güvencesini %24 abartıyordu.
Toplama sayısı **değişmedi**; `pyproject.toml` ve `conftest.py` dokunulmadı.

**Bekleme bütçeleri:** sabit duvar saati yerine `tests/timing.budget(saniye)` — makinenin
o anki hızıyla ölçeklenen bütçe (ölçek 1,0–8,0; `ENTROPY_TEST_TIMEOUT_SCALE` ile ezilir).

**Yalıtım:** `tests/conftest.py` gerçek kasayı ve `~/.entropy`'yi izole eder
(`isolate_obsidian_vault`). **Yeni bir yazma noktası eklersen yalıtımı da ekle** —
bugünkü hafızanın %30'u bu yalıtım eksikken sızmış fikstürlerdi.

### 9.1 `docs/` arşiv kuralı (Faz 12-E)

- `docs/reports/` yalnızca **son iki fazın** raporlarını + **koddan/testten atıf yapılan**
  raporları tutar; kapanan faz `docs/reports/_archive/fazNN/` altına iner.
- Atıf yapılan bir rapor taşınacaksa **aynı commit'te** koddaki yol da güncellenir
  (`scripts/_oneshot/sync_faz150_obsidian.py` tam olarak bu kural uygulanmadığı için kırıldı).
- Kullanıcı raporları (`*_audit.md/json`) **silinmez**, `docs/_archive/` altına taşınır.
- Eskimiş özellik belgeleri `docs/_archive/prototype/` altına iner; yerlerine mezar taşı
  `README` bırakılır (`docs/specifications/README.md`).

---

## 10. Faz 11 → **kod**, Faz 12 hedefleri

Faz 11'de "hedef mimari" olarak çizilen zincirin **tamamı bugün kod**:

```
Kullanıcı ─▶ Entropy Chat ─▶ [Beyin v2: MemoryGate ▸ L1 çalışma / L2 anlamsal (graf+wiki)
                 │                       / L3 yordamsal (skill) / kimlik + kurallar]
                 │            ▲ Obsidian = soğuk depo + insan arayüzü
                 ▼            │
        Araştırma (web + aktif skill) ── rapor ── yenilik kapısı (ADD / NOOP / gri bant)
                 │
                 ▼
        Entropy/Board: TASKBOARD.md + Entropy/Tasks/<id>.md + events.jsonl + claims/
                       + agents/<ad>/session.json
        durum makinesi: backlog → assigned → taken → running → review → done | failed | canceled
        BoardDispatcher (QTimer): "panoda sana görev var mı?" → atomik claim
                       (O_CREAT|O_EXCL) → terminal süreci (AGENT.md: provider/model/effort)
                 │
                 ▼
        Ajan araçları (4+1): board_next / checkpoint / finish (kanıtla) / ask · Entropy: board_create
        rapor → Entropy/Reports + pano olayı → sohbete "rapor geldi" kartı → beyne yenilik kapısından
```

Karşılıkları: `memory/gate.py`, `memory/categories.py`, `memory/dream.py`,
`memory/gray_merge.py`, `memory/wiki.py`, `agents/board_fsm.py`, `agents/board_events.py`,
`agents/dispatcher.py`, `agents/board_tools.py`, `agents/amplification.py`,
`core/identity.AgentSessionStore`, `ui/design/{tokens,qss,icons}.py`.

### 10.1 Faz 12 hedefleri

| # | Hedef | Kapı / doğrulama |
|---|---|---|
| 1 | **Depo bakımı (12-E, bu dilim):** tek seferlik betikler `scripts/_oneshot/`, referans testler `tests/_reference/`, çürük spec ve eskimiş özellik belgeleri `docs/_archive/prototype/`, `skills/` üçüzlemesinin tekilleştirilmesi, `platform/autostart.py` kaldırılması | toplama sayısı değişmez; `tests/_reference` + `tests/skills` + `test_exe` + `test_scheduler` yeşil |
| 2 | **`EntropyAI.spec` sapması:** Faz 11'de eklenen 15 modülün paketlenip paketlenmediği **ölçülür**, eksikse hiddenimports tamamlanır | derleme exit 0; `build/EntropyAI/xref-EntropyAI.html` taraması ya da `.exe` içi içe aktarma kontrolü |
| 3 | **`memory → brain` taşıması** — ön koşullar kapanmadan **başlamaz**: süit yeşil, spec sapması ölçülmüş, bu belge güncel | `grep -rn 'entropy\.memory' src tests scripts EntropyAI.spec` → 0; test sayısı değişmez ([ADR-0004](adr/ADR-0004-faz11-paket-tasima-yok.md) §adım planı) |
| 4 | **Açık işler:** `K4/K5/K6` için kalıcı harness, `config.amplification_lock`'un arayüz karşılığı, kartın `report_path` alanının doldurulması, `ui/widgets/tasks_widget.py` eski `dream_and_consolidate` çağrısı | her biri sözleşme testiyle kapanır |

**Kural:** bu bölümdeki bir hedef koda dönüştüğünde aynı commit'te yukarıdaki ilgili
bölüme (§5/§6/§8) taşınır. "Hedef" listesi kod bittikçe **kısalır**, uzamaz.
