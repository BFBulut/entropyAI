# STATE.md — Güncel durum (alt ajanların çalışma belleği)

> **İşe başlamadan önce bu dosyayı ve `docs/reports/` altındaki en son ilerleme raporunu oku.**
> Bu dosya alt ajanların oturumlar arası hafızasıdır: sözleşme imzaları, açık işler,
> bilinen kısıtlar ve son yeşil ölçümler burada durur. Her faz dilimi sonunda güncellenir.
> Mimari: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Kararlar: [`adr/`](adr/) · Plan: [`ROADMAP.md`](ROADMAP.md)

| | |
|---|---|
| Sürüm | **v0.8.0** (Faz 11-A sonrası etiket adayı: v0.9.0) |
| Dal | `ai/v0.1.7` (ana dal: `master`) |
| Son güncelleme | 2026-09-10, Faz 11-A kapanış QA (süit yeşil, exe yeniden derlendi) |
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
  (3), `board_claim_timeout_s` (3600), `entropy_max_parallel` (2).
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
- **Bayraklar:** `ENTROPY_MEMORY_GATE=0` kapıyı tamamen atlar (geri alma);
  `ENTROPY_MEMORY_GATE_STRICT` katı kipi zorlar/kapatır (varsayılan: üretimde
  açık, pytest altında kapalı).
- **Betikler:** `scripts/memory_migrate_v2.py` (`--dry-run` varsayılan,
  `--apply` yedek alır: `~/.entropy/backups/cognitive_memory.pre-v2.<zaman>.db`),
  `scripts/memory_blind_test.py` (K2/K3 kör testi, 10 sorgu).
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
   - **`--apply` koşulmadı.** Gerçek veritabanı hâlâ 1.544 düğüm; yalnızca kuru koşum
     raporu alındı (669 kalır). `--apply` QA'da, Hit@1 kapısıyla (K2 düşerse geri al).
   - **Gri bant kuyruğunu boşaltan toplu CLI turu yok** (11.3, agy-integration-engineer).
   - **Öz-amplifikasyon kilidi (11.6)** yalnızca kaynak zorunluluğu tarafıyla var;
     açık tespiti + yenilik kotası harness tarafında bekliyor.
   - `dream_and_consolidate` hâlâ 48 saat + epizodik koşuluna bağlı (11.7).

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
