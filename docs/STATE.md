# STATE.md — Güncel durum (alt ajanların çalışma belleği)

> **İşe başlamadan önce bu dosyayı ve `docs/reports/` altındaki en son ilerleme raporunu oku.**
> Bu dosya alt ajanların oturumlar arası hafızasıdır: sözleşme imzaları, açık işler,
> bilinen kısıtlar ve son yeşil ölçümler burada durur. Her faz dilimi sonunda güncellenir.
> Mimari: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Kararlar: [`adr/`](adr/) · Plan: [`ROADMAP.md`](ROADMAP.md)

| | |
|---|---|
| Sürüm | **v0.8.0** (Faz 11-A sonrası etiket adayı: v0.9.0) |
| Dal | `ai/v0.1.7` (ana dal: `master`) |
| Son güncelleme | 2026-09-10, Faz 11-A (depo temizliği ve iskelet) |
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

## 2. Tam süit — son koşum

`QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider`
→ **2.039 passed, 3 failed, 309 s** (2026-09-10, Faz 11-A sonu)

| Başarısız | Neden | Ne zaman düzelir |
|---|---|---|
| `tests/test_exe.py::test_compiled_exe_exists` | `dist/EntropyAI/EntropyAI.exe` Faz 11-A'da silindi (1,8 GB üretilmiş çıktı) | QA `pyinstaller EntropyAI.spec` ile yeniden derleyince |
| `tests/test_exe.py::test_autostart_detects_compiled_exe` | aynı | aynı |
| `tests/desk/test_desk_phase7.py::test_panel_minimum_widths_sum_below_900` | **Faz 11-A'dan bağımsız, önceden var olan hata**: offscreen kipte pencere `resize(900,700)` sonrası 796 px'e düşüyor, roster paneli 871 px'te taşıyor. Dosya `tests/` kökündeyken de aynı hatayı veriyor (taşımayla ilgisi yok, doğrulandı) | ayrı bir arayüz kartı (Faz 11-E kapsamında) |

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
  worktree, branch, pr_url`. Gövde: `## Hedef / ## Kabul ölçütleri / ## Notlar / ## Sonuç`.
  Yaşam döngüsü: `backlog → running → review → done`.
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
7. Beynin yazma tarafı: `MemoryGate` yok, `reconcile_facts` 7 yazma noktasına bağlı değil
   (Faz 11-B, [ADR-0003](adr/ADR-0003-hafiza-algoritmasi-mem0-degil.md)).

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
- **Faz 11-A (bu dilim):** depo 4.685 MB → 69 MB; 17.000+ üretilmiş dosya silindi; prototip
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
