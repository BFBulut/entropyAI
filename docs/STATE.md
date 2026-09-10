# STATE.md — Güncel durum (alt ajanların çalışma belleği)

> **İşe başlamadan önce bu dosyayı ve `docs/reports/` altındaki en son ilerleme raporunu oku.**
> Bu dosya alt ajanların oturumlar arası hafızasıdır: sözleşme imzaları, açık işler,
> bilinen kısıtlar ve son yeşil ölçümler burada durur. Her faz dilimi sonunda güncellenir.
> Mimari: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Kararlar: [`adr/`](adr/) · Plan: [`ROADMAP.md`](ROADMAP.md)

| | |
|---|---|
| Sürüm | **v0.8.0** (Faz 11-A sonrası etiket adayı: v0.9.0) |
| Dal | `ai/v0.1.7` (ana dal: `master`) |
| Son güncelleme | 2026-09-10, **Faz 11-B QA**: hafıza göçü `--apply` uygulandı (1.544 → 711 düğüm), K1–K12 ölçüm paketi kalıcılaştı (§2.2) · **Faz 11-C**: açılış kablolaması, 11.6 öz-amplifikasyon kilidi, yeni yerel komutlar, derleme hedefi ayrıldı |
| Python | 3.13 · PySide6 · PyInstaller (`EntropyAI.spec`) |

---

## 1. Faz 11-A önce/sonra ölçümü

| Ölçüm | Önce | Sonra | Kanıt |
|---|---:|---:|---|
| Disk (`.git` dahil) | **4.685 MB** | **69 MB** | `du -sm .` |
| Dosya sayısı (`.git` hariç) | 18.700 | **1.657** | `find . -path ./.git -prune -o -type f -print \| wc -l` |
| İzlenen dosya | 625 | **658** | `git ls-files \| wc -l` |
| `git status --short -uall` satırı | 1.264 | **268** (68'i untracked) | aynı komut |
| Toplanan test | **2.374** | **2.042** | `pytest --collect-only -q` |
| Prototip kaynağı (`tools/autonomous_agent_architecture*`) | 60 dosya / 75.578 satır | **0** | `ls src/entropy/tools` |
| Kökteki `.py` | 57 | **1** (`run_entropy.py`) | `ls *.py` |

Kalan 68 untracked dosyanın tamamı `scripts/` altındaki tek seferlik rapor/hafıza betikleridir
(`record_faz1XX_memories.py`, `save_faz*_report_and_memory.py`, `sync_faz*_obsidian.py` …).
Testlerin ihtiyaç duyduğu 12 betik izlemeye alındı; geri kalanın kaderi **açık iş** (§5).

---

## 2. Tam süit — son koşum (Faz 11-A kapanış QA, 2026-09-10)

`QT_QPA_PLATFORM=offscreen python -m pytest tests -q -p no:cacheprovider`
→ **2.186 test toplandı; 2.183 passed, 3 failed, 353 s** — üç hata da o an eşzamanlı
düzenlenen Faz 11-C dosyalarının ara hâlinden (`tasks.py`, `test_office_harness.py`,
`test_agent_commands_and_claude_chat.py` koşu sırasında değişti); düzenleme bitince
aynı 61 test yeniden koşuldu → **61 passed**. Faz 11-A'ya ait açık hata kalmadı.

Kapanışta düzeltilenler:

| Eski hata | Kök neden | Düzeltme |
|---|---|---|
| `tests/desk/test_desk_phase7.py::test_panel_minimum_widths_sum_below_900` | **Ürün hatası değil, ölçüm hatası:** panel asgarileri toplamı zaten 800 px (180+240+380 ≤ 900). Offscreen sürücüde sanal ekran 800×800 olduğu için `resize(900,700)` pencereyi ancak 796 px yapıyor, üç sütun 800 px'e sığmıyordu | test sıkışmış genişlik toplamını ölçüyor (`sum(widths) ≤ 900`) ve mutlak konum kontrolünü yalnızca ekran ≥ 920 px iken yapıyor — `tests/desk/test_desk_phase7.py:142-160` |
| `tests/test_exe.py` (2 test) | `dist/EntropyAI/EntropyAI.exe` Faz 11-A'da silinmişti | yeniden derlendi (§2.1) → **2 passed** |
| `tests/contracts/test_phase9_claude_isolation_and_models.py::test_card_with_foreign_model_runs_on_claude_default` | Faz 11-C durum makinesi: **ajansız `backlog` kart koşmaz** (`agents/tasks.py:853-859`); test ajansız kart kuruyordu, yalnızca tam süitte tesadüfen geçiyordu | karta gerçek bir Entropy ajanı atandı — `tests/contracts/test_phase9_claude_isolation_and_models.py:377-390` |
| `tests/contracts/test_phase10_wiring.py::test_interactive_only_for_desk_office_cards` | aynı kural | Entropy kartı `entropy-isci` ajanına atandı — `tests/contracts/test_phase10_wiring.py:150-158` |

**Yalıtım kanıtı (tam süit önce = sonra):** `~/.entropy/tasks_ledger.db` 69.632 B / mtime
1789002644; `~/.entropy/skills_state.json` 112 B / 1788993407; `~/.entropy/cognitive_memory.db`
21.078.016 B / 1789008895 — üçü de değişmedi.

### 2.1 Build (2026-09-10)

`python -m PyInstaller EntropyAI.spec --noconfirm` → **exit 0, 233 s**, çıktı
`C:\EntropiAI\dist\EntropyAI\` (**1.199 MB**, `EntropyAI.exe` 55,6 MB).
Smoke: `--help` **exit 0**; 20 sn canlı koşum (erken çıkış yok); günlükte
`traceback`/`CRITICAL` **0**; yeni CrashDump **yok**. Spec doğrulandı: `datas`
girdilerinin hepsi mevcut, silinen `tools/*` ailesinin spec'te girdisi yoktu,
`skills/media_agency_soldier` pakete girdi (`dist/EntropyAI/_internal/skills/`).
Marka taraması ve mimari kural testleri: `tests/contracts/test_architecture_rules.py`
**13 passed**.

---

## 2.2 Faz 11-B QA — hafıza göçü uygulandı (2026-09-10)

`python scripts/memory_migrate_v2.py --apply --json` → **exit 0**.
Uygulama kapalıydı; göç öncesi kuru koşum ve kör test, sonrasında kör test
tekrarlandı (kabul kapısı: Hit@1 ≥ 8/10 **ve** gürültü ≤ %2 → **KABUL**).

| Ölçüm | Göç öncesi | Göç sonrası |
|---|---:|---:|
| `cognitive_nodes` | **1.544** | **711** (669 taşındı + 42 konsolidasyon özeti) |
| Dosya boyutu | 21.078.016 B | 7.385.088 B |
| Kategori sayısı | 17 | **3** (`semantic 639`, `procedural 59`, `episodic 13`) |
| Hit@1 / Hit@5 | 8/10 · 10/10 | **9/10 · 10/10** |
| top-5 gürültü | %2,0 | **%0,0** |
| Yineleme (cos ≥ 0,92) | %52,5 | **%4,8** (677 küme / 711 düğüm) |
| Fikstür sızıntısı (K10) | 531 | **0** |
| Kaynaksız L2 (K12) | 1.276 | **258** (açık iş, aşağıda) |
| Graf `nodes / edges / communities` | — | **713 / 578 / 40** |
| `PRAGMA integrity_check` | — | **ok** |

Atılanlar (`dropped_by_reason`): fikstür 531, yakın kopya 262 (91 temsilci
altında birleşti), uydurma mimari 33, kısa metin 49 → toplam 875.

**Yedek:** `C:\Users\batu_\.entropy\backups\cognitive_memory.pre-v2.20260910061953.db`
(21.078.016 B, 1.544 düğüm).
**Geri alma:**
`copy /Y "%USERPROFILE%\.entropy\backups\cognitive_memory.pre-v2.20260910061953.db" "%USERPROFILE%\.entropy\cognitive_memory.db"`
(uygulama kapalıyken; kapı bayrağına dokunulmaz).

### K1–K12 durumu (gerçek DB, `python scripts/brain_metrics.py --json`)

| # | Ölçüt | Hedef | Ölçüm | Karar |
|---|---|---|---:|---|
| K1 | yineleme (cos ≥ 0,92) | ≤ %10 | **%4,78** | PASS |
| K2 | Hit@1 / Hit@5 | ≥ 8/10 · ≥ 10/10 | **9/10 · 10/10** | PASS |
| K3 | top-5 gürültü | ≤ %2 | **%0,0** | PASS |
| K7 | kategori disiplini | kanonik dışı 0 | **0** (3 ad kullanımda) | PASS |
| K9 | gri bant kuyruğu | — | **0 satır** | bilgi |
| K10 | fikstür sızıntısı | 0 | **0** | PASS |
| K11 | kapı gecikmesi | ≤ 400 ms | **medyan 82,2 ms** (ilk 186 ms) | PASS |
| K12 | kaynaksız L2 | 0 | **258** | FAIL (açık iş) |

K4/K5/K6/K8 bağlam derleyici ve tur harness'ında ölçülür; bu dilimin kapsamı değil.

**K12 kök nedeni ikiye ayrıldı:**
1. *Düzeltildi* — `GraphStore._mirror_to_cognitive` `provenance` sütununu hiç
   yazmıyordu (`src/entropy/memory/graph_store.py:388-400`): konsolidasyonun
   ürettiği 42 küme/yansıma düğümü graf tarafında
   `consolidate:label_propagation` kaynağını taşıdığı hâlde `cognitive_nodes`
   tarafında kaynaksız görünüyordu. Ayna artık kaynağı taşıyor (var olan
   dolu kaynağın üzerine yazmaz). Konsolidasyon yeniden koşuldu: kaynaksız L2
   **299 → 258**, düğüm sayısı değişmedi (idempotent). Regresyon testi:
   `tests/contracts/test_phase11_brain_metrics.py::test_graph_mirror_carries_provenance_into_cognitive_nodes`.
2. *Açık* — kalan **258** düğüm v2 öncesinden gelen eski bilgi; kaynak alanları
   kaynakta da boştu. Göç bunları uydurma kaynakla damgalamadı (bilerek).
   Karar bekliyor: geriye dönük kaynak çıkarımı mı, `confidence` düşürüp
   arşivleme mi.

**Duman testi (yeni şema ile):** `dist/EntropyAI/EntropyAI.exe --help` **exit 0**;
20 sn canlı koşum (erken çıkış yok), günlüğe eklenen 4 satırda
`Traceback`/`CRITICAL` **0**; `entropy_fault.log`'a düşen
`0x8001010d` kaydı QA'nın `Stop-Process -Force` ile sonlandırmasının artığıdır
(uygulama hatası değil). Bellek sayacının okuduğu sorgu (`zen_mode.py:748-758`
→ `CognitiveMemorySystem().get_all_nodes()`) **711 düğüm, 90 ms**;
`hybrid_recall(..., expand_graph=True)` yeni graf tablolarıyla çalışıyor.
Exe koşumu veritabanına yazmadı (mtime değişmedi).

---

## 3. Aktif sözleşmeler (değiştirirsen `ARCHITECTURE.md` ile birlikte güncelle)

- **Olay veriyolu:** `entropy.core.event_bus` — sinyal adı ve imzası sözleşmedir.
  Sık kullanılanlar: `agent_stream(dict)`, `agent_turn_started(str)`,
  `agent_turn_completed(str)`, `task_notification(str, str, str)`,
  `task_followup_completed(dict)`, `checkpoint_written(dict)`, `proof_recorded(dict)`,
  `memory_error(dict)`, `provider_status_updated(str, dict)`, `call_on_main(object)`.
  Tam tablo: `ARCHITECTURE.md` §7.
- **Kart ön bilgisi (`TaskCard`, `agents/tasks.py`):** `id, title, status, agent, provider,
  model, skill, created_at, started_at, finished_at, output_paths, summary, office, project,
  parent, children, grade, verdict, attempt, budget_tokens, intent, checkpoint, proof,
  worktree, branch, pr_url` + **Faz 11-C**: `effort, priority, input_paths,
  report_path, claimed_by, claim_expiry, event_seq`.
  Gövde: `## Hedef / ## Kabul ölçütleri / ## Notlar / ## Sonuç`.
  Yaşam döngüsü (Faz 11-C, 8 durum):
  `backlog → assigned → taken → running → review → done | failed | canceled`.
- **Durum makinesi (Faz 11-C):** `agents/board_fsm.py` tek kaynak —
  `STATUSES` (8), `EVENTS` (12), `TRANSITIONS` (12 satır), `transition(card,
  event, payload)`, `InvalidTransition`, `reset()`. Kütüphane YOK.
  `review → done` yalnızca `actor="human"` + kanıt; `run.finished` kanıt
  `green=False` ise `failed`.
- **Pano kökü:** `<kasa>/Entropy/Board/` (`core/paths.py`: `BOARD_SUBDIR`,
  `board_events_path()`, `board_taskboard_path()`, `board_claims_dir()`,
  `board_agents_dir()`, `agent_session_path()`, `board_projection_path()`).
  **Kartlar taşınmadı**, `Entropy/Tasks/` altında kalır.
- **Olay günlüğü:** `agents/board_events.py` — `events.jsonl`, satır şeması
  `{schema_version, seq, ts, correlation_id, task_id, attempt_id, actor,
  action, idempotency_key, payload}`; yalnızca ekleme, `projection_hash`
  (kanonik JSON + SHA-256), `TASKBOARD.md` türetilmiş.
- **Tetikleyici:** `agents/dispatcher.py` — `BoardDispatcherCore(board,
  registry, vault_path, runner, claim_timeout_s, max_parallel)` (Qt'siz;
  `tick() -> [kart_id]`, `pick(agent)`, `reconcile() -> [kart_id]`) +
  `BoardDispatcher` (QTimer sarmalı, `board_dispatcher()` tekil).
  Sahiplenme `claims/<id>.lock` `O_CREAT|O_EXCL`.
- **Ajan oturumu:** `core/identity.AgentSessionStore` →
  `Entropy/Board/agents/<ad>/session.json`
  `{provider: {session_id|conversation_id, signature, model, effort, cwd,
  updated_at}}`; Claude kimliği `uuid5("entropy-agent:<ad>")`,
  `run_kwargs()` → `{"session_id"}` (yeni) ya da `{"conversation_id"}` (sürdür).
  İmza artık `sha1(istem|model|efor)`.
- **Pano araçları:** `agents/board_tools.py` — ajanda 4 (`board_next`,
  `board_checkpoint`, `board_finish`, `board_ask`), Entropy'de +`board_create`.
  Taşıma biçimi `[PANO <araç>] {json} [/PANO]`; kanıtsız `board_finish`
  reddedilir (kart `review`de kalır).
- **Yeni bus sinyalleri:** `board_state_changed(dict)` = `{card_id, status,
  event, agent, office, title}`; `task_report_ready(dict)` = `{card_id, title,
  agent, status, ok, summary, report_path, output_paths}`.
- **Yeni ayarlar:** `board_auto_dispatch` (True), `board_dispatch_interval_s`
  (3), `board_claim_timeout_s` (3600), `entropy_max_parallel` (2),
  `amplification_lock` (True).
- **Açılış kablolaması (Faz 11-C):** `agents/bootstrap.start_board_dispatch(app)`
  → **önce `reconcile()`, sonra `start()`**; `app.aboutToQuit` kancasına
  `dispatcher.stop` takılır. `main.py` bu tek çağrıyı yapar
  (`main.py:160-163`), kapanış zinciri ayrıca `stop_board_dispatch()` çağırır.
  Dönüş `DispatchStartResult(recovered, started, dispatcher, error)`; hata
  YÜKSELMEZ, `summary()` metnine düşer.
- **Öz-amplifikasyon kilidi (11.6, `agents/amplification.py`):** üç kapı.
  (a) **Açık tespiti** — `TaskBoard._brain_shortcut` koşudan önce
  `brain_lookup()` çağırır; `brain_has_answer` ise kart CLI'ya GİTMEZ,
  `review`e düşer ve `run()` `"brain-<id>"` döndürür. (b) **Yenilik kotası** —
  `_finish` → `apply_report_lock` → `admit_report` raporu `MemoryGate`ten
  geçirir; `MIN_NOVELTY_RATIO = 0.30` altındaysa aynı konudaki **zamanlanmış**
  görev `TaskScheduler.disable_task(id, reason)` ile kapatılır (silinmez) ve
  `bus.task_notification(card_id, "Öz-amplifikasyon kilidi", <not>)` yayılır.
  (c) **Kaynak zorunluluğu** — raporda URL/dosya yolu yoksa kapı hiç çağrılmaz
  (`NoveltyReport.skipped_reason`). Kart notuna `[YENİLİK] …` satırı yazılır.
  Ofis kartları kapsam dışı; `config.amplification_lock=False` kilidi kapatır.
- **Kart alanı `kind`:** `"research"` (ya da boş). Boşsa başlık/hedef sezgisi
  (`is_research_card`) kullanılır; sezgi dar tutulur (`_WRITE_HINTS` geri çeker).
- **Yerel slash komutları (Faz 11-C):** `/board` (durum sayıları, sahiplenmeler,
  son 6 olay, `TASKBOARD.md` yolu), `/board pick <kart> <ajan>`,
  `/model [<ad>]` (**Entropy'nin KENDİ modeli**; yabancı model reddedilir),
  `/agent effort <ad> <seviye>` · `/agent model <ad> <model>` (AGENT.md'ye
  yazar → derler → `AgentSessionStore.forget(ad)` ile oturumu tazeler, çünkü
  imza `sha1(istem|model|efor)`), `/memory merge` (`memory.gray_merge.run`,
  guard) · `/memory dream`, `/wiki compile <yetenek> [--turns N]`
  (`memory.wiki.compile_skill`, guard). Hafıza modülleri yoksa komut hata
  vermez, "henüz kurulu değil" der.
- **Derleme hedefi (Faz 11-C, DEĞİŞTİ):** `compile_agent` agy biçimini
  `compile_roots()`'un hepsine, **claude biçimini YALNIZCA
  `claude_compile_root()` = `~/.entropy/workspace` altına** yazar. Proje
  kökünde `.claude/agents` OLUŞMAZ (derlenmiş ajanlar kullanıcının kendi Claude
  Code oturumuna sızıyordu); saf kip kadroyu `--agents <json>` ile taşır.
  Desk ofisleri `compile_agent_to` ile kendi çalışma dizinlerine iki biçimi de
  yazmayı sürdürür.
- **Kasa yolları:** Entropy `<kasa>/Entropy/{Agents,Tasks,Reports,Memory,Inbox,_archive}`;
  Desk `<kasa>/Desk/{Offices,Templates}` (`core/paths.py`: `DESK_ROOT_SUBDIR = "Desk"`,
  `DESK_SUBDIR = "Desk/Offices"`, `WORKTREE_ROOT_DIRNAME = ".entropy-worktrees"`).
- **Ajan derleme yerleşimi:** `AGENT_DEFINITION_LAYOUT = {"agy": (".agents/agents",
  "agent.md"), "claude": (".claude/agents", None)}` (`core/provider.py`).
- **Derleme kökleri (Faz 11-A'da değişti):** `compile_roots()` artık `APP_ROOT`'a yazmaz;
  kökler = `project_dir` + `config.default_project_path` + `claude_workspace_path()`.
- **Claude Saf Kip bayrakları:** `--system-prompt-file`, `--setting-sources ""`,
  `--strict-mcp-config`, `--mcp-config`, `--agents <json>`, `CLAUDE_CONFIG_DIR`,
  `run_cwd()` = `~/.entropy/workspace`. `--bare` kullanılmaz.
- **Bağlam bütçesi:** `context_builder.DEFAULT_TOKEN_BUDGET = 4000`; sıra playbook →
  hibrit recall → rapor alıntıları → kalıcı hafıza.
- **Hafıza şeması v2 (Faz 11-B):** `cognitive_nodes` sütunları `provenance`,
  `confidence`, `valid_from`, `valid_to`, `archived`, `novelty`, `is_identity`
  (hepsi idempotent `ALTER`, `_init_sqlite_db` içinde).
- **Kategori kapalı kümesi:** `memory/categories.py` →
  `CANONICAL_CATEGORIES = ("working", "episodic", "semantic", "procedural")`.
  Kimlik/kural (L4) **kategori değil bayrak**: `is_identity`. Ego düğümü
  `ego-entropy-core` kimliğini korur ama kategorisi `semantic`. Eski 13+ ad
  (`query`, `session`, `office`, `agent`, `architecture`, `math`, `federation`,
  `skill` …) `LEGACY_CATEGORY_MAP` ile eşlenir; ham değer
  `metadata.legacy_category`'de kalır.
- **Yazma kapısı (`memory/gate.py`):** `MemoryGate.admit(category, content,
  importance=0.5, metadata=None, provenance="") -> GateDecision`.
  `GateDecision(action, category, content, importance, is_identity, provenance,
  confidence, novelty, similarity, nearest_id, reason, metadata, embedding,
  embedding_status)`; `action ∈ {add, noop, gray, supersede, reject}`.
  Bantlar: `cos ≥ 0.95` NOOP · `cos < 0.80` ADD · arası **gri bant**
  (düğüm yazılır **ve** kuyruğa girer). `record_memory` / `store_node` bu tek
  kapıdan geçer (yedi üretim çağrı noktası değişmedi; `store_node` artık
  `provenance=` de alır).
- **Kapı iki kez koşmaz (Faz 11 kapanışı):** kararı çağıran ZATEN aldıysa
  (`MemoryGate.admit(...) -> GateDecision`) yazma yoluna kararı verir:
  `record_memory(..., decision=<GateDecision>)` ya da kısa yolu
  `CognitiveMemorySystem.store_decision(decision, importance=None)`.
  Karar verildiğinde `admit` bir daha çağrılmaz, gömme yeniden hesaplanmaz
  (vektör karardan gelir) ve kapı sayaçları ikinci kez artmaz.
  **agy'nin bağlayacağı yer:** `agents/amplification.admit_report` şu an önce
  `MemoryGate.admit` ile karar veriyor, sonra `record_memory` ile aynı adayı
  kapıdan bir kez daha geçiriyor (aynı metin iki kez gömülüyor); ikinci çağrı
  `memory.store_decision(decision)` ile değiştirilmelidir.
- **Eski kaynaksız L2 etiketi (Faz 11 kapanışı):** v2 öncesinden gelen,
  kaynağı hiç kaydedilmemiş `semantic` düğümler için uydurma kaynak YAZILMAZ:
  `gate.LEGACY_PROVENANCE = "legacy:pre-v2"`, `confidence = 0.40`
  (`gate.LEGACY_CONFIDENCE`), `valid_from = created_at`. Etiketi
  `scripts/memory_migrate_v2.py --tag-legacy` koyar (varsayılan kuru koşum,
  `--apply` önce yedek alır, idempotent). `derive_provenance` bu dizeyi GÜÇLÜ
  kaynak saymaz — yeni yazımlar onunla L2 zorunluluğunu atlayamaz.
  `brain_metrics` K12 tanımı: etiketli düğümler "kaynaksız L2" sayılmaz, ayrı
  sayaçta raporlanır (`K12_unsourced_l2.legacy_untagged`). `dream.forget_stale`
  bu düğümleri önem eşiğinden bağımsız aday sayar: hiç geri çağrılmamış ve
  30 günden eskiyse arşivlenir.
- **İçerik güncelleme bayrağı (Faz 11-D hatası):** `_save_node`ın `ON CONFLICT`
  dalı `content` sütununa dokunmaz (düğüm kimliği içerikten türer). İçeriği
  kasten değiştiren yollar (gri bant birleştirme, rüya döngüsü) artık doğrudan
  SQL yerine `_save_node(node, allow_content_update=True)` çağırır: içerik
  güncellenir, kimlik korunur, satır `embedding_status='pending'` işaretlenir
  (`reembed_stale` tazeler) ve graf kopyası da senkronlanır.
- **Gri bant kuyruğu:** `<db klasörü>/memory/gray_queue.jsonl`, satır başına
  `{ts, status, node_id, category, content, similarity, nearest_id,
  nearest_content, provenance, reason}`; `MemoryGate.pending_gray()` okur.
- **Geri çağırma kapsamı:** `hybrid_recall(query, top_k, min_threshold,
  categories=None, include_episodic=False, expand_graph=False)`. Varsayılan
  kapsam **L2+L3** (`semantic`, `procedural`); `archived=1` satırlar indekse
  girmez. `expand_graph=True` PPR ile 1-2 atlama komşu ekler.
- **CRAG sinyali:** `AssembledContext.brain_confidence` (en iyi recall skoru) +
  `brain_has_answer` (`context_builder.CRAG_MIN_SCORE = 0.45`); `summary()`
  ikisini de döndürür.
- **Gri bant birleştirme turu (Faz 11.3, `memory/gray_merge.py`):**
  `run_merge_round(memory=None, send_prompt=None, limit=8, gate=None, graph=None)
  -> MergeResult`. `send_prompt(prompt) -> str` **eşzamanlı çağrılabilir**
  (`distiller.run_with_bridge` sözleşmesinin aynısı); sağlayıcı seçimi
  çağıranındır (`config.provider`), modül köprüyü tanımaz. `None` ise **kuru
  koşum** (kuyruk boşaltılmaz, model çağrılmaz). **N aday tek istemde** →
  yanıt JSON `{"decisions":[{"id","action","content","reason"}]}`,
  `action ∈ {merge, keep_both, supersede}`. Uygulama: `merge` → komşu kalır
  (içerik birleşik metinle güncellenir), aday `archived=1`, grafta
  `supersedes` kenarı; `supersede` → ters yön; `keep_both` → yazma yok.
  Kuyruk satırı `status: "done"` + `resolution`. İptal: `cancel_merge()` /
  `reset_cancel()`. Ayrıştırılamayan yanıt kuyruğu **boşaltmaz**.
  K9 ölçümü: `gray_stats(memory) -> {pending, done, total_gray, nodes, ratio}`.
  Tur günlüğü `<db klasörü>/memory/gray_merge_log.jsonl`.
- **Rüya döngüsü v2 (Faz 11.7, `memory/dream.py`):**
  `dream_and_consolidate(memory=None, send_prompt=None, vault_path=None, ...)
  -> DreamReport`. **Epizodik-48s koşulu YOK.** Adımlar: (1) yeniden gömme →
  (2) gri bant turu (`send_prompt` yoksa kuru koşum) → (3) cos ≥ 0,95 kopya
  birleştirme (LLM'siz, `merge_duplicates`) → (4) ölçülü unutma
  (`forget_stale`: önem < 0,35 **ve** `access_count ≤ 1` **ve** 30 gün →
  `archived=1`, **silme yok**, `is_identity` muaf) → (5) wiki yükseltme adayı
  (`wiki_promotion_candidates`: cos ≥ 0,75, ≥ 3 anlamsal düğüm; sayfayı
  yazmaz) → (6) graf konsolidasyonu + ofis akışı + `reconcile_stores`.
  Her adım sayaç döndürür, hatalar `DreamReport.errors`'a girer ve döngü
  devam eder. Kasa çıktıları: `Entropy/Memory/dream_log.md` (tek satır),
  `Entropy/Memory/wiki_candidates.md`. Zamanlanmış görev:
  `ensure_daily_dreaming_task(scheduler=None, hour=4)` — `scheduler_tasks.json`
  içine `daily-dreaming` kimliğiyle **idempotent** kayıt (varsa yeniden yazmaz).
  Eski `CognitiveMemorySystem.dream_and_consolidate` geriye dönük uyum için
  **yerinde duruyor**; yeni çağıranlar `memory.dream` modülünü kullanır.
- **Wiki derleme hattı (Faz 11.8, Karpathy L2):**
  `wiki.compile_skill(skill, bridge=None, budget_turns=8, vault_path=None,
  store=None, run_lint=True, cancel=None) -> dict`. `bridge` =
  `send_prompt(prompt) -> str`; `None` ise **model çağrılmaz** (yalnızca
  playbook tabanlı kavram/varlık sayfaları + indeks + lint, `turns=0`).
  **Rapor başına bir tur**, `budget_turns` bu çağrının tavanı. Artımlı:
  işlenen rapor kümesi `<kasa>/Entropy/Skills/<yetenek>/wiki/WIKI.state.json`
  (`{"processed": [...]}`), ikinci çağrıda yeni rapor yoksa **0 tur**.
  Dönüş: `{skill, turns, pages, new_pages, processed, remaining, base, index,
  log, lint, reason}`; `lint = {total, counts, stats}` (`lint.lint_skill`).
  Gerçek koşu tavanı: `financial-auditor` 50 rapor ≈ 50 tur → QA'da
  `budget_turns` ile bölünerek koşulur.
- **Genel sohbet beyin paketi (Faz 11.9):** `context_builder.BUDGET_GENERAL_BRAIN
  = 1500` (`BRAIN_IDENTITY_TOKENS=300`, `BRAIN_RULES_TOKENS=400`,
  `BRAIN_WIKI_PAGES=4`). Yalnızca `skill_name` **boşken** ödenir; içerik =
  kimlik düğümleri (`is_identity=1`) + onaylı kurallar (`promoted_rules`,
  `ENTROPY_OFFICE`) + **yetenekler arası** en iyi wiki sayfaları. PPR
  genişletmeli recall ve aktarım özeti kendi bölümlerinde kalır (aynı metin
  iki kez ödenmez). `_wiki_page_files(None)` artık tüm yeteneklerin
  sayfalarını döndürür; `_reports_section` yeteneksiz sohbette kasa geneli
  en yeni `GENERAL_REPORT_CANDIDATES = 60` rapora düşer.
- **Yerel komut sözleşmesi (agy bağlayacak):** `/memory merge` →
  `gray_merge.run_merge_round`, `/memory dream` → `dream.dream_and_consolidate`,
  `/wiki compile <yetenek>` → `wiki.compile_skill`. Üçü de köprü
  çağrılabilirini **çağırandan** alır; hiçbiri kendi başına kota harcamaz.
- **Bayraklar:** `ENTROPY_MEMORY_GATE=0` kapıyı tamamen atlar (geri alma);
  `ENTROPY_MEMORY_GATE_STRICT` katı kipi zorlar/kapatır (varsayılan: üretimde
  açık, pytest altında kapalı).
- **Betikler:** `scripts/memory_migrate_v2.py` (`--dry-run` varsayılan,
  `--apply` yedek alır: `~/.entropy/backups/cognitive_memory.pre-v2.<zaman>.db`),
  `scripts/memory_blind_test.py` (K2/K3 kör testi, 10 sorgu),
  `scripts/brain_metrics.py` (**Faz 11-B QA, yeni**: K1/K2/K3/K7/K9/K10/K11/K12
  raporu; **salt okunur**, `sqlite3 ... mode=ro` ile açar, `--json`,
  `--skip-recall`, `--skip-latency`). Üçü de pytest içinden çağrılabilir
  (`plan_migration`/`write_target`, `memory_blind_test.run`,
  `brain_metrics.collect`) ve testte tmp DB ile koşulur.
- **Ölçüm paketi (kalıcı):** `tests/contracts/test_phase11_brain_metrics.py`
  (12 test, sentetik korpus) + `tests/contracts/test_phase11_memory_isolation.py`
  (11 test, yazma yolu yalıtımı). Ölçüm mantığı tek kaynak: `scripts/brain_metrics.py`.
- **Doğuş talimatı:** `office_workspace.SPAWN_INSTRUCTION_MAX_CHARS = 1200`.
- **Test yalıtımı:** `tests/conftest.py` gerçek kasayı ve `~/.entropy`'yi izole eder
  (`isolate_obsidian_vault`). Yeni bir yazma noktası eklersen yalıtımı da ekle — bugünkü
  hafızanın %30'u bu yalıtım eksikken sızmış fikstürlerdir.

---

## 4. Faz 11-A'da ne değişti (kod tarafı)

| Dosya | Değişiklik |
|---|---|
| `src/entropy/agents/compile.py` | `compile_roots()` artık `APP_ROOT`'a yazmıyor (gerekçe docstring'de) |
| `tests/test_agents_bootstrap.py` | yeni sözleşmeye göre güncellendi; "APP_ROOT'a sızmaz" iddiası test edildi |
| `src/entropy/tools/` | 60 dosyalık prototip ailesi silindi; kalan: `__init__.py`, `synthesizer.py` |
| `tests/` | `contracts/`, `ui/`, `desk/`, `skills/` alt paketleri; taşınan dosyalarda yol derinliği düzeltildi (`parents[1]` → `parents[2]`) |
| `.gitignore` | üretilmiş çıktı, ajan artıkları, `scratch/`, `.agents/`, Entropy'nin derlediği 5 ajan |
| `docs/` | `ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `adr/ADR-0001…0005`, `_archive/` |
| `AGENTS.md` · `GEMINI.md` | uydurma kadro kaldırıldı; dizin haritası gerçekle eşitlendi |

**`EntropyAI.spec` değişmedi:** prototip ailesinin spec'te hiç girdisi yoktu (doğrulandı).

---

## 5. Açık işler

1. **Build doğrulaması (QA):** `pyinstaller EntropyAI.spec` → `dist_check` + `.exe` smoke test;
   `tests/test_exe.py`'nin iki testi ancak bundan sonra yeşile döner.
2. `tests/desk/test_desk_phase7.py::test_panel_minimum_widths_sum_below_900` — önceden var
   olan arayüz hatası, sahibi yok.
3. `scripts/` altındaki ~60 tek seferlik betik: izlemeye mi alınacak, `scratch/`e mi taşınacak,
   silinecek mi? Karar verilmedi (silinmedi, dokunulmadı).
4. `src/entropy/platform/autostart.py` — **tek ölü ürün modülü**: üründe içe aktaranı yok,
   yalnızca iki test ve spec canlı tutuyor; `config.autostart_enabled` okunup yazılıyor ama
   hiçbir yerde uygulanmıyor. Özellik ya bağlanmalı ya kaldırılmalı.
5. **agy köprüsünde izolasyon yok** (kayıtlı sınır, ADR-0002): süreç proje dizininde koşar,
   ajanlar çalışma dizininden keşfedilir; CLI'da karşılık gelen bayrak yok.
6. `docs/specifications/` altındaki 5 eski spec `ARCHITECTURE.md`'ye damıtılıp arşive
   taşınacak (Faz 11-A'da yalnızca prototip spec'i arşivlendi).
7. ~~Beynin yazma tarafı: `MemoryGate` yok~~ → **Faz 11-B'de kuruldu** (§3). Kalanlar:
   - ~~`--apply` koşulmadı~~ → **2026-09-10 QA'da koşuldu ve kabul edildi** (§2.2).
   - **K12 açık:** 258 eski L2 düğümü kaynaksız (§2.2).
   - ~~Gri bant kuyruğunu boşaltan toplu CLI turu yok~~ → **Faz 11-D:
     `memory/gray_merge.py`** (§3). Kalan: agy tarafında `/memory merge`
     komutunun köprüye bağlanması ve **gerçek koşum** (QA).
   - ~~**Öz-amplifikasyon kilidi (11.6)**~~ → **Faz 11-C'de tamamlandı**
     (`agents/amplification.py`, §3). Kalan: gerçek kapıyla uçtan uca ölçüm
     (ADD oranının gerçek korpusta ne çıktığı) yapılmadı.
   - ~~`dream_and_consolidate` hâlâ 48 saat + epizodik koşuluna bağlı~~ →
     **Faz 11-D: `memory/dream.py`** (§3). Eski metot geriye dönük uyum için
     duruyor; `main.py` / `tasks_widget.py` çağrılarının yeni modüle
     taşınması **ui/agy tarafında açık iş**.
   - **K4 hedefin altında (%56,8 < %60, Faz 11-D ölçümü).** Neden: wiki
     katmanı 7 yetenekten yalnızca birinde dolu; `wiki.compile_skill`in
     gerçek koşumu (QA, 11.8) sayfaları üretince beyin paketi büyüyecek.
     K5 **%38,2 ≥ %30** (kabul).

---

## 6. Son fazların özeti

- **Faz 9 (v0.7.0):** Entropy Saf Kip (Claude izolasyonu), sağlayıcı/model kimliği,
  Desk ayrımının sıkılaştırılması.
- **Faz 9.1 (v0.7.1):** efor = model varyantı (`--effort` yok), sağlayıcıya duyarlı efor
  arayüzü, proje kökü asla paket dizini olmaz, skill enjeksiyon bütçesi.
- **Faz 10 (v0.8.0):** ofis çalışma alanı dosyaları (BOARD/ARCHITECTURE/RULES), denetim
  noktaları, kanıtla kapat, onaylı kurallar, ajan başına akış sinyali + terminaller paneli,
  etkileşimli kart kipi, proje = depo + dal, kart başına worktree (Windows'ta güvenli
  temizlik), PR akışı (yerel dal + diff → onaylı push), ekip şablonları, makbuz = ofis raporu,
  Desk kökü `Desk/` altına taşındı, bilişsel bellek çift depo eşitlemesi.
- **Faz 11-D (hafıza katmanı, konsolidasyon/wiki/genel beyin):** `memory/gray_merge.py`
  (gri bant kuyruğu birleştirme turu, N aday tek istemde, iptal edilebilir,
  idempotent), `memory/dream.py` (rüya döngüsü v2 — epizodik koşulu yok, altı
  adım, adım başına sayaç, `dream_log.md`), `wiki.compile_skill` (Karpathy L2
  derleme hattı, rapor başına bir tur, `WIKI.state.json` ile artımlı, lint
  entegre), `context_builder` genel beyin paketi (`BUDGET_GENERAL_BRAIN=1500`,
  yeteneksiz sohbette kimlik + onaylı kurallar + yetenekler arası wiki, rapor
  bölümü kasa geneline düşüyor). **Ölçüm (gerçek kasa, DB kopyası, 5 genel
  sorgu):** K4 %11,4 → **%56,8**; K5 %0 → **%38,2**. Sahte köprüyle: 5 gri
  aday → 3 merge + 2 keep, 1 tur, kuyruk boşaldı; 5 rapor → 5 tur, ikinci
  çağrı 0 tur, lint 0 çelişki. Testler: `tests/test_phase11_dream_wiki_brain.py`
  (22 test).
- **Faz 11-B (bu dilim, hafıza katmanı):** şema v2 (7 yeni sütun, idempotent ALTER),
  kategori kapalı kümesi (17 değer → 4 katman + `is_identity` bayrağı), `MemoryGate`
  (fikstür süzgeci, L2 kaynak zorunluluğu, üç bant, gri bant kuyruğu, `reconcile_facts`
  bağlantısı), okuma yolu eklentileri (kapsam süzgeci, PPR genişletme, CRAG sinyali),
  göç ve kör test betikleri. **Ölçüm (gerçek DB, kuru koşum):** 1.544 → 669 düğüm
  (fikstür 531, yakın kopya 262, uydurma mimari 33, kısa 49 atılır); kategori
  `{semantic 597, episodic 13, procedural 59}`. Kör test **göç öncesi** Hit@1 8/10,
  Hit@5 10/10, gürültü %2 → **gerçek DB'nin kopyasında göç sonrası** Hit@1 **9/10**,
  Hit@5 10/10, gürültü **%0** (denetimdeki tek kaçırma, #9 DAG/kritik yol, düzeldi).
  Kapı gecikmesi 712 düğümlük korpusta medyan **234 ms** (K11 ≤ 400 ms).
- **Faz 11-A:** depo 4.685 MB → 69 MB; 17.000+ üretilmiş dosya silindi; prototip
  ailesi ve 32 testi kaldırıldı; kullanıcı çıktıları `docs/_archive/customer/` ve
  `~/.entropy/external/` altına taşındı; `docs/` iskeleti ve 5 ADR kuruldu; kök markdown'lar
  gerçekle eşitlendi; testler konu bazlı gruplandı.

---

## 7. Kırmızı çizgiler

- Kullanıcı verisi (Obsidian kasası, `~/.entropy`) **silinmez**. Depo içi kullanıcı raporları
  (`*_audit.md/json`) silinmez, `docs/_archive/` altına taşınır.
- `git stash`, `git checkout --`, `git reset --hard` **yasak**.
- Gerçek model çağrısı yapılmaz; testler hedefli koşulur.
- Ticari referans ürünün ve üreticisinin adı hiçbir dosyaya yazılmaz.
- Ölç, iddia etme: dosya sayısı, MB, test sayısı önce/sonra yazılır.
