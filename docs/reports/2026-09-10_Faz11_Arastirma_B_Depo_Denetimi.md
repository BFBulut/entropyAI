# Faz 11 — Araştırma B: Depo Denetimi, Temizlik Manifesti ve Yeni Proje Yapısı

- **Depo:** `C:\EntropiAI` — sürüm 0.8.0, dal `ai/v0.1.7`, HEAD `12c327e`, 68 commit.
- **Kip:** SALT OKUNUR. Bu rapor dışında hiçbir dosya oluşturulmadı, silinmedi, taşınmadı, değiştirilmedi. Model çağrısı yapılmadı.
- **Ölçüm tarihi:** 2026-09-10.
- **Marka kuralı:** ticari referans ürünün ve üreticisinin adı bu raporun hiçbir yerinde geçmez.

> Ölçümlerin tamamı komut çıktısına dayanır. İçe aktarma grafiği, geçici bir AST tarayıcısıyla (yalnızca okuma) üretildi; grafik dosyası oturum geçici dizininde kaldı, depoya yazılmadı.

---

## 1. Envanter

### 1.1 Kaba tablo

| Ölçüm | Değer | Kanıt |
|---|---|---|
| Disk üzerindeki toplam boyut | **4.685 MB** | `du -sm .` |
| Dosya sayısı (`.git` hariç) | **18.700** | `find . -path ./.git -prune -o -type f -print \| wc -l` |
| Git nesneleri | **24 MB** | `du -sm .git` |
| İzlenen (tracked) dosya | **618** | `git ls-files \| wc -l` |
| İzlenmeyen (untracked, `-uall`) | **1.262** | `git status --short -uall --porcelain \| wc -l` |
| Yok sayılan (ignored, listelenmiyor) | ~16.800 dosya | aşağıdaki 1.4 |

**Tek cümlelik sonuç:** deponun disk ayak izinin **%99,5'i** git'in hiç görmediği üretilmiş çıktıdır (4.685 MB'ın 24 MB'ı git nesnesi, ~4.500 MB'ı `dist/`, `build/`, `dist_check/`, `build_check/` ve kökteki `.exe`).

### 1.2 İzlenen dosyalar (618)

```
229 src        210 tests       62 docs        55 scratch
 37 skills      11 .claude      11 (kök)       4 scripts      1 .agents
```
Kanıt: `git ls-files | awk -F/ '{if (NF==1) print "(root)"; else print $1}' | sort | uniq -c | sort -rn`

Kökteki 11 izlenen dosya: `.gitignore`, `AGENTS.md`, `EntropyAI.spec`, `EntropyAI_OneFile.spec`, `GEMINI.md`, `THIRD_PARTY.md`, `entropy.ico`, `entropy.png`, `launch.bat`, `pyproject.toml`, `run_entropy.py`.

### 1.3 İzlenmeyen dosyalar (1.262)

```
732 scratch/                              89 test_bridge_background_task_fa0/
 81 google_flow_files/                    60 test_bridge_background_task_le0/
 72 scripts/                              49 test_project_directory_binding0/
 64 (kök, .py + denetim çıktıları)         5 .agents/agents/
 58 src/entropy/tools/                     1 test_thread_off/
 49 skills/                                1 test_office_200/
                                           1 financial-auditor/
```
Kanıt: `git status --short -uall --porcelain | sed 's/^?? //' | tr -d '"' | awk -F/ '...'`

> Not: `scratch/` sayısı denetim sırasında 716 → 732'ye çıktı. Fark, paralel koşan Faz 11 arayüz denetimi ajanının yazdığı `scratch/ui/phase11/*` dosyalarıdır (`find scratch -type f -newermt "2026-09-10 04:30"`), bu denetimin ürünü değildir.

### 1.4 Yok sayılan (git'in hiç listelemediği) büyük kalemler

| Yol | Dosya | Boyut | Son değişiklik |
|---|---:|---:|---|
| `dist/` | 8.508 | **1.848,5 MB** | 2026-09-10 |
| `dist_check/` | 7.272 | **1.184,0 MB** | 2026-09-10 |
| `build/` | 48 | **778,7 MB** | 2026-09-10 |
| `EntropyAI.exe` (kök) | 1 | **475,3 MB** | 2026-09-04 |
| `build_check/` | 17 | **177,8 MB** | 2026-09-10 |
| `__pycache__` (tüm depo) | 1.075 | 31,5 MB | — |
| `.entropy/` | ~60 | ~3 MB | 2026-09-10 |
| `.pytest_cache/` | 5 | <1 MB | — |

`.gitignore` (375 bayt) bunları zaten kapsıyor: `dist/`, `build/`, `dist_check/`, `build_check/`, `*.exe`, `__pycache__/`, `.pytest_cache/`, `.entropy/`, `*.db*`.

**`.entropy/` KULLANICI VERİSİDİR — silinemez.** `src/entropy/core/config.py:76 _resolve_state_dir()` şu sırayı uygular: `ENTROPY_HOME` → **`APP_ROOT/.entropy` varsa o** → `%LOCALAPPDATA%\EntropyAI`. Depo kökünde `.entropy/` var olduğu için canlı ayar dosyası, sohbet geçmişi (`chat_history.json`), çökme günlüğü (`logs/entropy_fault.log`), görsel yükleri (`payloads/`) ve rapor indeksi oradadır.

### 1.5 Sınıflandırma

| Sınıf | İçerik | Ölçü |
|---|---|---|
| **Kaynak** | `src/entropy/**` — 183 modül | 123 ürün modülü + **60 üretilmiş prototip** |
| **Test** | `tests/` — 205 toplanan dosya | **2.374 test** (`pytest --collect-only -q`) |
| **Doc** | `docs/` — 62 dosya | reports 48/972 KB, slides 6/136 KB, specifications 6/60 KB, +2 kök md |
| **Veri** | `src/entropy/desk/assets/**` (piksel), `skills/**` | THIRD_PARTY.md ile lisanslı |
| **Üretilmiş** | `build*/`, `dist*/`, `__pycache__`, `.pytest_cache`, `.agents/agents/*` (5), `.claude/agents/` içindeki 5 dosya | 15.845 + 1.080 dosya |
| **Kullanıcı çıktısı** | kök `*_audit.md/json` (8), `google_flow_files/` (86 / 102,4 MB), `docs/CanivoPets_*`, `docs/slides/*` | 102,7 MB |
| **Ajan artığı** | kök `module_task_*.py` (13), `schema_task_*.py` (28), `test_task_*.py` (14), `test_t_exec_0.py` (1); kök test dizinleri (200 dosya); `financial-auditor/SKILL.md` (113 baytlık "# test" taslağı) | 257 dosya |

---

## 2. İçe aktarma grafiği bulguları

Yöntem: `src/entropy/**` altındaki 183 modül için AST ile `import` / `from … import` (göreli içe aktarmalar çözülerek) tarandı; içe aktaranlar `src/`, `tests/`, `scripts/`, kök `*.py` içinde arandı; ayrıca `"entropy.x.y"` biçimindeki **dizgi** kullanımları (importlib / PyInstaller hiddenimports) tüm `.py/.spec/.md/.json/.toml` dosyalarında arandı. Giriş noktaları: `run_entropy.py` → `entropy.main:main`, `EntropyAI.spec` `hiddenimports` (100+ satır), `pyproject.toml` `[project.scripts] entropy = "entropy.main:main"`, `tests/`.

### 2.1 (a) Hiçbir yerden kullanılmayan modüller

**Ürün paketlerinde sıfır yetim modül var.** 123 ürün modülünün tamamı ya bir ürün modülünden, ya `EntropyAI.spec`'ten, ya testlerden, ya da `scripts/`'ten erişiliyor.

Tek gerçek ölü ürün modülü:

| Modül | Boyut | Durum |
|---|---:|---|
| `src/entropy/platform/autostart.py` (`WindowsAutostartManager`) | 2.692 B | **Üründe hiçbir içe aktaran yok.** Yalnızca `tests/test_exe.py`, `tests/test_scheduler.py` ve `EntropyAI.spec` hiddenimports canlı tutuyor. `config.autostart_enabled` alanı `config.py:329/467/505` içinde okunup yazılıyor ama **hiçbir yerde uygulanmıyor** (`grep -rn "WindowsAutostartManager\|autostart" src/entropy/main.py src/entropy/ui/**` → boş). Yani özellik ayar olarak var, davranış olarak yok. |

Yanlış pozitif olabilecek iki modül — **silmeyin**:
- `src/entropy/skills/media_agency_soldier.py`: AST'ye görünmez. `skills/__init__.py` PEP 562 `__getattr__` ile `_LAZY = {"MediaAgencySoldierEngine": "entropy.skills.media_agency_soldier"}` üzerinden `importlib` ile yükleniyor (açılış süresi ölçümü nedeniyle tembelleştirilmiş). Paketten düşmemesi `EntropyAI.spec` hiddenimports'a bağlı.
- `src/entropy/core/perf_history.py`: ürün içe aktaranı yok ama izlenen iki geliştirici betiği kullanıyor (`scripts/perf_bench.py`, `scripts/routing_eval.py`).

### 2.2 (b) Yalnızca testlerden kullanılan modüller — `tools/autonomous_agent_architecture*` ailesi

Bu ailenin tamamı **ürün kodu değildir**:

| Ölçüm | Değer |
|---|---|
| Dosya sayısı | **60** (`autonomous_agent_architecture.py` + `_faz98…_faz158`) |
| Kaynak boyutu | **3,0 MB** / **75.578 satır** |
| Tekil en büyük dosya | `autonomous_agent_architecture.py` — 554.348 B, 13.225 satır, 197 üst düzey `class`/`def` |
| `EntropyAI.spec` hiddenimports'ta | **HAYIR.** Spec yalnızca `'entropy.tools'` ve `'entropy.tools.synthesizer'` içeriyor. |
| `src/entropy/**` içinden içe aktaran (aile dışı) | **0** |
| İzlenen (tracked) dosya | **4**: `__init__.py`, `autonomous_agent_architecture.py`, `..._faz158.py`, `synthesizer.py`. Diğer **58 faz dosyası izlenmiyor.** |

Aile içi bağımlılık (silme sırası için kritik):

- **14 dosya monolitin içinden içe aktarılıyor.** `autonomous_agent_architecture.py:12965` ve sonrasında `from .autonomous_agent_architecture_faz98 import (…)` … `faz99, faz100–104, faz126–132`. Bu 14 dosya silinirse monolit içe aktarılamaz ve onu kullanan **17** test dosyası kırılır.
- **15 dosya yalnızca testlerden içe aktarılıyor:** `faz110, faz111, faz146–faz158`.
- **30 dosya hiçbir yerden referans almıyor:** `faz107–109, faz112–125, faz133–145` (tam liste aşağıda 7. bölümde).

Ürün kodu olan tek `tools` modülü `synthesizer.py`'dir (`src/entropy/core/slash_commands.py` içe aktarıyor, spec'te var) — **korunur**.

### 2.3 Bu testler ürün davranışını mı sınıyor?

Hayır. `tests/test_autonomous_agent_architecture_faz*.py` — **32 dosya, 332 test, 372 KB, 9.923 satır** — yalnızca üretilmiş prototipi sınıyor. Her biri doğrudan `entropy.tools.autonomous_agent_architecture*` içe aktarıyor ve hiçbiri `entropy.core/agents/memory/ui/desk` içinden bir sözleşmeye dokunmuyor.

Ölçülen koşum: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_autonomous_agent_architecture_faz*.py -q -p no:cacheprovider` → **332 passed in 3.52 s**. Yani bunlar süiti yavaşlatmıyor; maliyetleri hız değil, **3,4 MB ölü kaynak ve kavramsal gürültü**.

**Sonuç: aile kendi 32 test dosyasıyla birlikte silinebilir.** Ürün davranışını sınayan tek bir testi bile götürmez.

### 2.4 (c) Yalnızca üretilmiş `tools/*faz*` dosyalarının kullandığı ürün modülü

**Yok.** Prototip ailesi `entropy.*` ürün paketlerinden hiçbir şey içe aktarmıyor (tamamen kendi kendine yeter). Yani aile silindiğinde hiçbir ürün modülü "yalnız kalıp" ölüye dönüşmez.

### 2.5 Grafikten çıkan iki kırılganlık

1. **`src.entropy.…` ikili içe aktarma.** 8 test dosyası `from src.entropy.tools… import` yazıyor (`test_..._faz110, faz111, faz153–158`). `pyproject.toml` `pythonpath = ["src"]` verdiği için aynı kod hem `entropy.x` hem `src.entropy.x` adıyla iki ayrı modül nesnesi olarak yüklenebiliyor. Bugün zararsız (prototip modülleri durum tutmuyor) ama ürün modüllerine sıçrarsa teşhisi zor hatalar üretir. Aile silinince bu sorun da kendiliğinden biter.
2. **Testler izlenmeyen dosyalara bağımlı.** 5 medya-ajansı testi `from skills.media_agency_soldier.… import` yazıyor; bu, **izlenmeyen** `skills/__init__.py` ve **izlenmeyen** `skills/media_agency_soldier/` (alt çizgili) klasörünü gerektiriyor. İzlenen sürüm `skills/media-agency-soldier/` (tireli). Temiz bir klondan `pytest` koşulursa bu 5 dosya içe aktarma hatası verir. (Bkz. 7. bölüm, "izlenmeyeni izlemeye al" satırı.)

---

## 3. Kök markdown ve CLI dosyaları

### 3.1 Kimde ne var

| Dosya / dizin | Durum | Boyut / adet |
|---|---|---|
| `AGENTS.md` | var, izleniyor | 2.246 B, 2026-09-06 |
| `GEMINI.md` | var, izleniyor | 10.143 B, 2026-09-07 |
| `CLAUDE.md` | **YOK** | — |
| `.mcp.json` | **YOK** | — |
| `.claude/agents/` | 11 dosya (6 elle yazılmış + **5 üretilmiş**) | — |
| `.agents/agents/` | 6 dosya (1 izlenen `distiller` + **5 üretilmiş, izlenmiyor**) | — |
| `THIRD_PARTY.md` | var, izleniyor (MIT + CC0 bildirimleri) | 2.236 B |

### 3.2 Hangi CLI hangisini okur (yerel `--help` çıktılarıyla doğrulandı)

**Claude Code** (`C:\Users\batu_\AppData\Roaming\npm\claude`):
- `--bare` seçeneğinin kendi açıklaması, varsayılan kipte nelerin yüklendiğini sayarak dolaylı ama kesin kanıt veriyor: *"skip hooks, LSP, plugin sync, attribution, auto-memory, background prefetches, keychain reads, and **CLAUDE.md auto-discovery**"* ve *"Explicitly provide context via: `--system-prompt[-file]`, `--append-system-prompt[-file]`, **`--add-dir` (CLAUDE.md dirs)**, `--mcp-config`, `--settings`, `--agents`, `--plugin-dir`"*.
- `--setting-sources <sources>` → *"Comma-separated list of setting sources to load (user, project, local)."*
- `--strict-mcp-config` → *"Only use MCP servers from `--mcp-config`, ignoring all other MCP configurations"*.
- `--agents <json>` → *"JSON object defining custom agents"*.
- Yani Claude Code: `CLAUDE.md` (otomatik keşif, `--add-dir` köklerinden de), `.claude/agents/*.md`, `.claude/settings*.json`, `.mcp.json`.

**agy** (`C:\Users\batu_\AppData\Local\agy\bin\agy`):
- `agy --help` çıktısında `--setting-sources`, `--strict-mcp-config`, `--append-system-prompt` **yok**; bayraklar: `--add-dir`, `--agent`, `--continue`, `--conversation`, `--dangerously-skip-permissions`, `--disable-slash-commands`, `--effort`, `--mode`, `--model`, `--print`, `--sandbox`, `--json-schema`, `--project` vb.; alt komutlar arasında `agents`, `mcp`, `plugin`, `models`.
- Ajan tanımı yerleşimi ürün kodunda sabitlenmiş: `src/entropy/core/provider.py:1149`
  ```python
  AGENT_DEFINITION_LAYOUT = {
      "agy":    (".agents/agents", "agent.md"),
      "claude": (".claude/agents", None),
  }
  ```
  ve yorumu: *"İkisi de sürecin çalışma dizinine göre keşfedilir."*
- **`GEMINI.md` agy ikilisinin belgelediği bir dosya değildir.** Bu depoda proje sözleşmesi olarak kullanılan bir insan belgesidir (ve `pyproject.toml`'da `readme = "GEMINI.md"`).

### 3.3 Entropy'nin köprüleri izole kipte bunları yüklüyor mu?

**Claude köprüsü — izolasyon sağlam.** `src/entropy/core/claude_bridge.py`:
- `--setting-sources ""` (satır 780) → kullanıcı/proje/yerel ayar dosyaları ve `.claude/agents` yüklenmez;
- `--strict-mcp-config` (774) + `--mcp-config` (776);
- `--system-prompt-file` ile varsayılan sistem istemi **değiştirilir**, eklenmez (satır 123, `REPLACE_SYSTEM_PROMPT_FILE_FLAG`);
- `--agents <json>` ile Entropy kendi kadrosunu enjekte eder (`entropy_agents_json()`, satır 832);
- `CLAUDE_CONFIG_DIR` çevre değişkeni yeniden yazılır (satır 460);
- `run_cwd()` (satır 1552) — çalışma dizini **git deposunun dışında**, `%USERPROFILE%\.entropy\workspace`. Gerekçe kodda yazılı: *"Claude Code proje kimliğini … literal cwd'den değil GİT KÖKÜNDEN çözüyor, bu yüzden depo içindeki bir alt klasör izolasyon sağlamıyor."* Tek istisna: kart bir worktree'ye bağlıysa cwd o worktree'dir.
- `--bare` bilerek kullanılmıyor (satır ~150): abonelik OAuth'unu hiç okumaz, `ANTHROPIC_API_KEY` ister.

**Ama bir boşluk var (bugün tetiklenmiyor):** `--setting-sources ""` ayar kaynaklarını kapatır; **`CLAUDE.md` otomatik keşfi ayrı bir mekanizmadır** (yalnızca `--bare` kapatıyor) ve `--add-dir` kökleri CLAUDE.md dizini sayılıyor. Entropy her koşuya `isolation_read_dirs()` ile kasa + workspace ekliyor, kart koşusunda ise proje dizinini de ekliyor. **Bugün depoda `CLAUDE.md` olmadığı için sızıntı yok.** Temizlikte kök `CLAUDE.md` oluşturulacaksa bu ölçülmeden yapılmamalı.

**agy köprüsü — izolasyon yok.** `agy_bridge.py` süreci doğrudan proje dizininde koşturuyor (`cwd=str(project_dir)`, satır 1361 ve 2045) ve agy'nin ajanları çalışma dizinine göre keşfetmesine güveniyor (`agent_definitions_dir()`, satır 644). agy ikilisinde karşılık gelen bir `--setting-sources` bayrağı olmadığı için bu, mevcut CLI ile giderilebilir bir eksik değil; kayıt altına alınması gereken bir sınırdır.

### 3.4 `.claude/agents` ve `.agents/agents` KARIŞIK — üretilmiş dosyalar depoya yazılıyor

`src/entropy/agents/compile.py:312 compile_roots()` derleme çıktısını **`APP_ROOT`** dahil birden çok köke yazıyor; kaynaktan koşulduğunda `APP_ROOT` **deponun kendisidir** (`config.py:22 _resolve_app_root()` → `Path(__file__).resolve().parents[3]`). `compile_agent()` her ajan için hem `<kök>/.agents/agents/<ad>/agent.md` hem `<kök>/.claude/agents/<ad>.md` yazıyor.

Sonuç, bu depoda ölçülebilir durumda:

| `.claude/agents/` | Kaynak |
|---|---|
| `agy-integration-engineer.md`, `memory-rag-engineer.md`, `qa-build-engineer.md`, `ui-engineer.md`, `repo-curator.md`, `research-scout.md` | **elle yazılmış, izleniyor** — kullanıcının kendi geliştirme alt ajanları |
| `analist.md`, `arastirmaci.md`, `degerlendirici.md`, `orkestrator.md`, `yazar.md` | **Entropy tarafından üretilmiş** (aynı adlar `.agents/agents/` altında da var ve orada izlenmiyor) |

Bu, kullanıcının kendi Claude Code oturumunda Entropy'nin iç kadrosunun (`analist`, `arastirmaci`, `degerlendirici`, `orkestrator`, `yazar`) alt ajan olarak görünmesine yol açıyor — nitekim bu oturumda da görünüyorlar. **Öneri:** üretilmiş beşliyi `.gitignore`'a al ve `compile_roots()`'un `APP_ROOT`'a yazmasını Faz 11'de bir düzeltme kartına dönüştür (bu rapor kod değişikliği önermez, yalnızca kanıtı verir).

### 3.5 `AGENTS.md` — yanlış ve tehlikeli

`AGENTS.md` 5 ajanlık bir kadro ilan ediyor (`Entropy AI`, `CodeArchitect`, `Tester`, `Researcher`, `MemoryConsolidator`) ve `Agents/EntropyAI/persona.md`, `Agents/CodeArchitect/persona.md` … yollarına atıf yapıyor. **`Agents/` klasörü depoda yok** (`ls -d Agents` → No such file or directory). Gerçek kadro kasadaki `Entropy/Agents` kayıt defteridir (`entropy.agents.registry`).

Bu, geçmişte ölçülmüş bir hataya yol açmış; `EntropyAI.spec` içindeki yorum aynen şunu söylüyor:

> "AGENTS.md PAKETLENMEZ: eski, elle yazılmış bir kadro listesiydi … `_internal/AGENTS.md` olarak .exe'nin yanına düşüyordu. Ajan okuma izni o klasöre uzandığında Entropy kendi kadrosunu oradan 'öğreniyor' ve var olmayan ajanları sayıyordu."

Ürün kodunda `AGENTS.md` okuyan **hiçbir yer yok**; yalnızca silinecek prototip okuyor (`tools/autonomous_agent_architecture.py:4513, 12384`). **Öneri: `AGENTS.md` içeriği tamamen değiştirilsin** — kadro listesi kaldırılsın, yerine "bu depoda ajanlar nasıl tanımlanır" (kasa kayıt defteri + `compile.py` + `.claude/agents` / `.agents/agents` eşlemesi) anlatılsın; ya da dosya `docs/_archive/` altına taşınıp yerine kısa bir yönlendirme bırakılsın.

### 3.6 `GEMINI.md` — dizin haritası eskimiş

`GEMINI.md` `pyproject.toml`'un `readme`'si ve fiilen mimari belgesi. §1 ve §2 (ilkeler, değişmezler) hâlâ doğru; **§3 "Directory Map" yanlış**:

| Haritada yazan | Gerçek |
|---|---|
| `Agents/EntropyAI/persona.md` | klasör yok |
| `src/entropy/agent_desk/{core,ui,analysis,memory,research}` | **paket yok**; gerçeği `src/entropy/desk/` |
| `run_agent_desk.py` (ayrı uygulama) | dosya yok |
| `src/entropy/tools/` "Self-tooling & dynamic tool synthesis" | gerçekte %98'i silinecek prototip; ürün kısmı tek dosya (`synthesizer.py`) |
| eksik | `src/entropy/agents/` (13 dosya, 8.502 satır — kayıt defteri, harness, kartlar, posta kutusu, worktree, PR akışı) tamamen haritada yok |

Kanıt: `ls -d Agents run_agent_desk.py src/entropy/agent_desk` → üçü de yok.

### 3.7 `Entropy/Tasks` kart biçimi ve TaskBoard markdown'ı

**Kullanıcının istediği "ajanlar Taskboard'daki görevlerini markdown'dan okusun" mantığı zaten uygulanmış durumda.** Yeni bir biçim icat etmeye gerek yok:

- `src/entropy/agents/tasks.py` (1.372 satır) — her kart `<kasa>/Entropy/Tasks/<id>.md`, YAML ön bilgi + gövde. Modül başlığındaki gerekçe: *"Kart neden dosya: … kullanıcı Obsidian'da düzenleyebilmeli ve iki taraf da aynı gerçeği görmeli. Uygulama içi bir kuyruk bunların hiçbirini vermezdi."*
- Ön bilgi alanları (`TaskCard`, satır 147–204): `id, title, status, agent, provider, model, skill, created_at, started_at, finished_at, output_paths, summary, office, project, parent, children, grade, verdict, attempt, budget_tokens, intent, checkpoint, proof, worktree, branch, pr_url`. Gövde: `## Hedef / ## Kabul ölçütleri / ## Notlar / ## Sonuç`. Yaşam döngüsü `backlog → running → review → done` (`review`de insan onayı bekler).
- Ofis kartları ayrı depoda: `<ofis>/cards/` (Faz 9 / B-9.2 ayrımı, satır 52–58).
- `src/entropy/memory/office_workspace.py` (392 satır) ofis kökünde `BOARD.md` (kartlardan türetilir), `ARCHITECTURE.md` (orkestratör doldurur), `RULES.md` (onaylı kurallardan türetilir), `checkpoints/<kart-id>.md` üretiyor; `spawn_instruction()` alt ajanlara **mutlak yolla** "önce BOARD ve ARCHITECTURE'ı oku" talimatını veriyor (`SPAWN_INSTRUCTION_MAX_CHARS = 1200`).
- `src/entropy/agents/harness.py` bunları gerçekten çağırıyor: `ensure_workspace` (855–870), `spawn_instruction` (897–915), `render_board` (947–966 ve 1624, 1832, 1838, 1997, 2216).

**Eksik olan tek şey:** bunların hiçbiri depoda görünmüyor (kasada duruyor). Faz 11'de yapılacak şey biçim değiştirmek değil, `docs/ARCHITECTURE.md` içine bu sözleşmeyi (kart ön bilgi şeması + workspace dosya düzeni) yazıp geliştirici tarafına görünür kılmaktır.

---

## 4. Docs düzeni

### 4.1 Bugünkü durum

```
docs/                                   62 dosya
├── CanivoPets_Media_Agency_Audit.md    16 KB   (müşteri çıktısı)
├── PHASED_ROADMAP.md                    4 KB   (53 satır, kendi kendini "eskimiş" ilan ediyor)
├── reports/                           972 KB   48 dosya
├── slides/                            136 KB   6 dosya (müşteri sunumu)
└── specifications/                     60 KB   6 dosya
```

`docs/reports/` üç aileye ayrılıyor:

| Aile | Adet | Boyut | Nitelik |
|---|---:|---:|---|
| `2026-09-*` faz raporları | 24 | 472 KB | **canlı proje geçmişi** |
| `2026_Kapsamli_Otonom_Ajan_Mimarisi_…_Faz1XX.md` | 21 | 444 KB | prototip ailesinin araştırma notları |
| `2026_Otonom_Ajan_Ortamlari_*` | 3 | 28 KB | prototip ailesinin araştırma notları |

### 4.2 Kaynak kodun atıf yaptığı raporlar (silinemez / taşınamaz)

`grep -rhoE "docs/(reports|specifications)/[A-Za-z0-9_.-]+\.md" src/entropy tests`:

| Rapor | Atıf sayısı | Atıf yapan |
|---|---:|---|
| `docs/reports/2026-09-10_Faz5_Tasarim_Raporu.md` | 3 | `memory/graph_store.py:10`, `ui/widgets/command_palette.py:9`, `ui/widgets/report_center.py:10` |
| `docs/reports/2026-09-11_Faz9_Teshis_Notu.md` | 2 | `ui/widgets/slash_prompt.py:8` |
| `docs/reports/2026-09-11_Faz10_Teshis_ve_Mimari_Bosluk_Notu.md` | 1 | (kaynak yorumu) |

### 4.3 Önerilen düzen — ve neden acil

**Bugün commit'lenmiş ajan tanımları, var olmayan dosyalara atıf yapıyor.** `12c327e` ile güncellenen 5 alt ajan şunu söylüyor:

- `.claude/agents/repo-curator.md:12` → *"`docs/` düzeni (`ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `adr/` kararları, `reports/` faz raporları)"*
- `memory-rag-engineer.md:20`, `qa-build-engineer.md:20`, `agy-integration-engineer.md:21` → *"İşe başlamadan önce `docs/STATE.md` (varsa) … oku"*
- `ui-engineer.md:17` → *"sözleşmeler `docs/STATE.md`'de"*

`ls docs/STATE.md` → **yok**. Yani her alt ajan her koşuda bu dosyayı arayıp bulamıyor ve "en son ilerleme raporu"na düşüyor. Önerilen düzen bu yüzden kozmetik değil, **çalışan bir bağımlılığı karşılıyor**:

```
docs/
├── ARCHITECTURE.md        # yaşayan mimari: paketler, veri akışı, kart/board sözleşmesi,
│                          # kasa yerleşimi, iki sağlayıcı köprüsü, izolasyon kuralları
├── STATE.md               # güncel durum — alt ajanların "çalışma belleği":
│                          # sürüm, dal, açık işler, bilinen kısıtlar, sözleşme imzaları
│                          # (bus sinyalleri, kwarg adları), son yeşil test sayısı
├── ROADMAP.md             # PHASED_ROADMAP.md'nin yerine; faz durumları
├── DESIGN_SYSTEM.md       # ui-engineer.md:20 zaten arıyor ("varsa")
├── adr/                   # ADR-0001… : geri alınamaz kararlar (kasa yolu, izole kip,
│                          # Desk/Entropy ayrımı, worktree kararı, dual-store bellek)
├── reports/
│   ├── faz09/  faz10/  faz11/ …        # tarih önekli mevcut dosyalar faz klasörlerine
│   └── (kod tarafından atıf yapılan 3 rapor yerinde kalır ya da atıflar güncellenir)
└── _archive/
    ├── prototype/         # 24 prototip araştırma raporu (472 KB)
    ├── specifications/    # AUTONOMOUS_AGENT_ARCHITECTURE_FAZ126.md + ARCHITECTURE'a
    │                      # damıtıldıktan sonra kalan 5 eski spec
    └── customer/          # CanivoPets audit + slides (müşteri çıktısı)
```

| Dosya | Karar | Gerekçe |
|---|---|---|
| `docs/reports/2026-09-*` (24) | **canlı** — `docs/reports/fazNN/` altına grupla | proje geçmişi; 3'ü koddan atıflı |
| `2026_Kapsamli_…Faz1XX.md` (21) | **arşiv** `_archive/prototype/` | anlattıkları kod siliniyor |
| `2026_Otonom_Ajan_Ortamlari_*` (3) | **arşiv** `_archive/prototype/` | aynı |
| `docs/specifications/AUTONOMOUS_AGENT_ARCHITECTURE_FAZ126.md` | **arşiv** | prototipin spec'i |
| `docs/specifications/` diğer 5 | **damıt → arşiv** | `SYSTEM_ARCHITECTURE`, `UI_SPECIFICATION`, `MEMORY_RAG_SPECIFICATION`, `AGY_CLI_INTEGRATION`, `TASK_SCHEDULER_SPECIFICATION` → `ARCHITECTURE.md`'ye |
| `docs/PHASED_ROADMAP.md` | **yeniden yaz → `ROADMAP.md`** | 53 satır; kendi içinde *"kod tabanı bu plandan çok daha ileride (`tools/autonomous_agent_architecture_faz*.py` serisi 158. faza kadar gidiyor)"* diyor — atıf yaptığı seri siliniyor |
| `docs/CanivoPets_*`, `docs/slides/*` | **arşiv** `_archive/customer/` | müşteri çıktısı, ürün belgesi değil |

---

## 5. Test düzeni

### 5.1 Ölçüm

`python -m pytest --collect-only -q -p no:cacheprovider` → **2.374 test / 205 dosya** (3,06 s toplama).

Dosyaların ne sınadığına göre dağılım (içe aktarma hedefine göre sınıflandırma + test sayımı):

| Grup | Ne sınıyor | Dosya | Test | Pay |
|---|---|---:|---:|---:|
| **C — ürün** | `entropy.*` ürün modülleri | 88 | **1.445** | 60,9 % |
| **B — yetenek paketleri** | `skills/**` betikleri | 43 | 372 | 15,7 % |
| **A — prototip** | `entropy.tools.autonomous_*` | 32 | 332 | 14,0 % |
| **D — kendi kendine yeten** | modelleri test dosyasının kendi içinde tanımlıyor; depodan hiçbir şey içe aktarmıyor | 42 | 225 | 9,5 % |

**A + D = 74 dosya / 557 test (%23,5) sevk edilen hiçbir kodu sınamıyor.**

D grubunun içeriği: `test_faz36…faz68_finance_models.py` (32 dosya, 1,03 MB — sınıflar dosyanın kendi içinde), `test_atatp_audit.py`, `test_enjsa_audit.py`, `test_froto_*.py`, `test_sahol_*.py`, `test_leverage_calc.py`, `test_earnings_reaction.py` (10 dosya). Bunlar birer "matematik ispat defteri"; regresyon koruması değil.

Hız: A grubu 332 test / **3,52 s**; D grubundan 3 dosya 18 test / **0,76 s**. Yani bunlar süitin yavaş kısmı değil. (Tam süit süresi ölçülmedi: salt-okunur kip.)

Faz adlı testler: `test_phase*.py` 17 + `test_ui_phase*.py` 10 = **27 dosya**.

### 5.2 Öneri

1. **Silinecek:** yalnızca A grubu (32 dosya, 332 test) — sildiği kodla birlikte. Sonra süit **2.374 → 2.042**.
2. **Taşınacak, silinmeyecek:** D grubu (42 dosya, 225 test) → `tests/_reference/` (ya da `tests/analysis/`) ve `pyproject.toml` `testpaths` dışına ya da bir `reference` işareti (`marker`) arkasına. Silmek kullanıcının nicel çalışmasını yok eder; ana süitte tutmak "2.374 test yeşil" ölçüsünü yanıltıcı kılar.
3. **Faz adlı testler yeniden adlandırılsın, silinmesin.** `test_phase9_claude_isolation_and_models.py` bir faz raporu değil, kalıcı bir sözleşmedir: "izole kip `--setting-sources ""` geçirir". Öneri: `tests/contracts/` altına taşıyıp konuya göre adlandırmak — `test_claude_isolation.py`, `test_desk_separation.py`, `test_worktrees_pr.py`, `test_workspace_memory.py`, `test_harness_discipline.py` … Test kimlikleri (`nodeid`) yalnızca dosya adıyla değişir; gövdeler aynı kalır, bu yüzden adım geri alınabilir.
4. **Önerilen dizin düzeni** (tek adımda değil, kademeli):
   ```
   tests/
   ├── contracts/     # ürün sözleşmeleri (eski test_phase*, test_ui_phase*)
   ├── unit/          # modül düzeyi
   ├── ui/            # pytest-qt / offscreen
   ├── skills/        # skills/** paketleri (B grubu)
   └── _reference/    # D grubu — kendi kendine yeten nicel defterler
   ```
5. **Kırılganlık düzeltmesi (silmeden önce):** `skills/__init__.py` ve `skills/media_agency_soldier/` izlemeye alınmalı, yoksa temiz klonda 5 test dosyası içe aktarma hatası verir (bkz. 2.5).

---

## 6. Yeni yapı önerisi

### 6.1 Bugünkü paket düzeni ve ağırlıkları

| Paket | Dosya | Satır | Rol |
|---|---:|---:|---|
| `ui/` | 37 | 20.733 | PySide6 kabuğu (Zen/Chat/Floating, widget'lar) |
| `memory/` | 22 | 13.823 | bilişsel bellek, graf, wiki, playbook, bağlam, ofis çalışma alanı |
| `core/` | 15 | 11.660 | yapılandırma, olay veriyolu, iki sağlayıcı köprüsü, slash komutlar, kilit |
| `agents/` | 13 | 8.502 | kayıt defteri, kartlar, harness, posta kutusu, worktree, PR, şablonlar |
| `desk/` | 20 | 6.697 | Agent Desk penceresi, piksel sahne motoru, paneller |
| `skills/` | 5 | 1.972 | SKILL.md keşfi + motorlar |
| `mcp/` 2 · `scheduler/` 2 · `platform/` 3 · `tools/` 2 | 9 | 1.075 | yardımcı |

En büyük tek dosyalar: `ui/widgets/knowledge_graph.py` 185 KB, `core/agy_bridge.py` 134 KB, `core/claude_bridge.py` 119 KB, `agents/harness.py` 117 KB, `core/slash_commands.py` 76 KB.

### 6.2 İstenen hedef (`core / brain / agents / desk / ui / skills`) — maliyeti

İstenen şemadaki tek gerçek değişiklik, `memory/` + `skills/` bilgi katmanının `brain/` altında toplanmasıdır; geri kalan (`core`, `agents`, `desk`, `ui`, `skills`) **zaten mevcut**.

Yalnızca `entropy.memory` → `entropy.brain` yeniden adlandırmasının dokunduğu dosyalar:

| Yüzey | Dokunulan | Kanıt |
|---|---:|---|
| `src/` içindeki içe aktarmalar | 41 dosya | `grep -rl "entropy\.memory\b" src/entropy` |
| `tests/` içindeki içe aktarmalar | 41 dosya | `grep -rl "entropy\.memory\b" tests/*.py` |
| `EntropyAI.spec` hiddenimports | 22 satır | `grep -c "entropy\.memory" EntropyAI.spec` |
| **Toplam** | **~104 dosya** | |

Karşılaştırma için diğer paketler: `core` 74 src + 59 test + 15 spec; `ui` 39 + 32 + 37; `agents` 32 + 24 + 14; `desk` 14 + 10 + 20.

Ek riskler:
1. `EntropyAI.spec` hiddenimports **dizgi** listesidir; bir satır atlanırsa `.exe` sessizce eksik paketlenir. Faz 10-C'de tam olarak bu olmuş (spec yorumu: *"bu modüller yalnizca calisma aninda importlib ile cagriliyor; PyInstaller statik tarayicisi goremedigi icin paketten dusuyor ve .exe'de worktree/PR/sablon/makbuz yollari sessizce kapaniyordu"*).
2. `skills/__init__.py` `_LAZY` haritası ve `provider.py` içindeki dizgi eşlemeleri metin olarak taşınmalı.
3. `docs/reports/*` ve `.claude/agents/*.md` içindeki yol atıfları eskir.
4. `~/.entropy` altındaki kullanıcı durumu paket adına göre anahtarlanmıyor (kontrol edildi), yani veri göçü gerekmiyor — tek gerçek risk içe aktarma yollarıdır.

### 6.3 Önerim: **iki aşama, ilk aşamada paket taşıma yok**

**Aşama 1 (Faz 11 kapsamı — önerilen):** paket adları **olduğu gibi kalsın**; yalnızca

- prototip ailesini (`tools/autonomous_agent_architecture*`, 60 dosya) ve 32 testini kaldır;
- kökü temizle (56 ajan artığı `.py`, 200 dosyalık test dizini, 475 MB `.exe`, 4 build klasörü);
- `docs/` düzenini kur (`ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `adr/`, `_archive/`);
- kök markdown'ları düzelt (`AGENTS.md` yeniden yaz, `GEMINI.md` §3 haritasını gerçekle eşitle);
- `.gitignore`'u genişlet (`scratch/`, üretilmiş ajan tanımları, test artığı dizinleri).

Bu aşama **tek bir `import` satırına dokunmaz**, `EntropyAI.spec`'te yalnızca kaldırılan `entropy.tools` girdileri sadeleşir ve tam süit A grubu dışında hiç etkilenmez. Kazanç: **~4,5 GB disk, 17.000+ dosya, 3,4 MB ölü kaynak, 74 yanıltıcı test dosyası**.

**Aşama 2 (ayrı bir faz, ayrı onay):** `entropy.memory` → `entropy.brain` (ve isteğe bağlı `memory.rag` + `memory.wiki` + `skills` bilgi katmanının `brain/` altında toplanması). Ön koşul: `docs/ARCHITECTURE.md` yazılmış, tam süit yeşil ve `.exe` bir kez sorunsuz derlenmiş olmalı; taşıma tek commit'te, `git mv` + otomatik `sed` + spec güncellemesi + tam süit + `dist_check` derlemesi ile yapılmalı.

Gerekçe: Aşama 1 kullanıcı isteğinin **tamamını** (silme, klasör düzeni, boşları kaldırma, markdown'ları değiştirme) sıfır regresyon riskiyle karşılıyor. Aşama 2 ise saf estetik bir kazanç için 104 dosyaya ve sessiz paketleme hatası riskine giriyor — ikisini aynı fazda birleştirmek, bir sorun çıktığında hangisinin sebep olduğunu ölçülemez kılar.

---

## 7. Silme manifesti (kuru koşum)

Kısaltmalar: **SİL** = kalıcı sil · **ARŞ** = `docs/_archive/` altına taşı · **DIŞ** = depo dışına taşı · **IGN** = `.gitignore`'a ekle (diskte kalır) · **KOR** = dokunma.

### 7.1 Üretilmiş ikili çıktı

| Yol | Eylem | Dosya | Boyut | Kanıt |
|---|---|---:|---:|---|
| `EntropyAI.exe` (kök) | **SİL** | 1 | **475,3 MB** | `dist/EntropyAI_Standalone.exe` ile **birebir aynı** (ilk+son 4 MB MD5 `4bec79d1…4bcb`, aynı boyut, aynı tarih 2026-09-04 = v0.8.0 öncesi). `launch.bat` bu dosyayı değil `dist\EntropyAI\EntropyAI.exe`'yi çalıştırıyor. `.gitignore`'da `*.exe`. |
| `dist/` | **SİL** | 8.508 | **1.848,5 MB** | `.gitignore`'da; `EntropyAI.spec` ile yeniden üretilir. İçinde silinmiş `agent_desk` paketinin eski derlemesi de var (`dist/EntropyAgentDesk/_internal/src/entropy/agent_desk/`). |
| `dist_check/` | **SİL** | 7.272 | **1.184,0 MB** | `.gitignore` yorumu: "Gecici build dogrulama ciktisi". |
| `build/` | **SİL** | 48 | **778,7 MB** | PyInstaller ara çıktısı; `build/EntropyAI_OneFile` 2026-09-04'ten kalma. |
| `build_check/` | **SİL** | 17 | **177,8 MB** | aynı. |
| `__pycache__` (1.075 klasör) | **SİL** | 1.075 | 31,5 MB | `.gitignore`'da. |
| `.pytest_cache/` | **SİL** | 5 | <1 MB | `.gitignore`'da. |
| **Ara toplam** | | **16.926** | **4.495,8 MB** | |

> **Kısıt:** çalışan `.exe` `dist/`i kilitler. Silmeden önce Entropy kapatılmalı (bilinen çalışma zamanı kısıtı).

### 7.2 Üretilmiş prototip kaynak + testleri

| Yol | Eylem | Dosya | Boyut | Kanıt |
|---|---|---:|---:|---|
| `src/entropy/tools/autonomous_agent_architecture.py` | **SİL** | 1 | 554 KB | `src/entropy/**` içinden içe aktaran yok; `EntropyAI.spec` hiddenimports'ta yok; yalnızca **17** test dosyası kullanıyor (`grep -lE "autonomous_agent_architecture import" tests/test_autonomous*.py \| wc -l` → 17; görev metnindeki "16" bir eksik sayımdı, 17 + 15 faz-ekli = 32 dosya). |
| `..._faz98,99,100,101,102,103,104,126,127,128,129,130,131,132` | **SİL** | 14 | ~625 KB | yalnızca monolit içe aktarıyor (satır 12965+); monolitle birlikte gider. |
| `..._faz110, faz111, faz146–faz158` | **SİL** | 15 | ~660 KB | yalnızca aynı adlı testler içe aktarıyor. |
| `..._faz107,108,109,112–125,133–145` | **SİL** | 30 | ~1,1 MB | **hiçbir yerden referans yok** (ne src, ne tests, ne spec, ne dizgi). 29'u izlenmiyor. |
| `tests/test_autonomous_agent_architecture_faz*.py` | **SİL** | 32 | 372 KB | tamamı yalnızca yukarıdaki aileyi sınıyor (332 test, 3,52 s); ürün sözleşmesi sınamıyor. |
| **Ara toplam** | | **92** | **~3,4 MB** | süit 2.374 → **2.042** test |
| `src/entropy/tools/synthesizer.py` + `__init__.py` | **KOR** | 2 | 5,8 KB | `core/slash_commands.py` içe aktarıyor; spec'te `entropy.tools.synthesizer` var. |

### 7.3 Kökteki ajan artıkları

| Yol | Eylem | Dosya | Kanıt |
|---|---|---:|---|
| `module_task_*.py` (13), `schema_task_*.py` (28), `test_task_*.py` (14), `test_t_exec_0.py` (1) | **SİL** | 56 | Şablon metinleri (`"Otonom Uygulama Modülü"`, `"Otomatik Mimari Şasisi"`, `"Otomatik Test Süiti"`) tüm depoda tek bir üreticiye ait: `dist/EntropyAgentDesk/_internal/src/entropy/agent_desk/core/concrete_action_engine.py`. **Bu paket `src/` içinde artık yok** (`ls -d src/entropy/agent_desk` → yok). Yani üreticisi kaldırılmış ölü çıktı. Gövdeleri `assert True` / `return {...}`. |
| `test_bridge_background_task_fa0/`, `test_bridge_background_task_le0/`, `test_project_directory_binding0/`, `test_thread_off/`, `test_office_200/` | **SİL** | 200 | Test koşumlarının kasa zannederek depoya yazdığı `Reports/Gorev_*.md` ve `AgentDesk/*.md` dosyaları (2026-09-05/06). Neden tekrarlanmayacağı `tests/conftest.py:115–130` `isolate_obsidian_vault` fixture'ında yazılı: *"Kanit: `Entropy/Projects/test_bridge_background_task_*` altinda 195 rapor … yazilmisti. Testler … artik tmp'ye duser."* Ayrıca `tests/test_phase8_graph_data.py:79` `is_test_artifact_name("test_bridge_background_task_fa0")` ile bu adları filtreleyen kalıcı bir koruma var. |
| `financial-auditor/` (kök) | **SİL** | 1 | İçeriği 113 baytlık taslak: ön bilgi + `# test`. Gerçek yetenek `skills/financial-auditor/SKILL.md` (45.608 B). `SkillManager` `<APP_ROOT>/skills` altını tarar, kökü değil — yani işlevsiz ama yanıltıcı. |
| `reports/` (kök) | **SİL** | 0 | **boş klasör** (`find reports -type f` → 0). |
| **Ara toplam** | | **257** | ~0,3 MB |

### 7.4 Kullanıcı çıktısı — SİLİNMEZ, taşınır

| Yol | Eylem | Dosya | Boyut | Kanıt |
|---|---|---:|---:|---|
| `atatp_financial_audit.md`, `enjsa_financial_audit.md`, `enjsa_metrics.json`, `sahol_financial_audit.md`, `canivopets_audit.md/.json`, `canivopets_audit_full.md/.json` | **ARŞ** → `docs/_archive/customer/` | 8 | 0,1 MB | Kullanıcının denetim çıktısı; repo-curator kuralı: *"depo içi kullanıcı raporları (`*_audit.md/json`) silinmez, `docs/_archive/` altına taşınır."* |
| `google_flow_files/` | **DIŞ** → depo dışına (ör. `%USERPROFILE%\EntropyOutputs\`) | 86 | **102,4 MB** | Kampanya video/görsel çıktıları + indirme betikleri; hiçbir test/kaynak referansı yok. Depoda tutulması için hiçbir teknik gerekçe yok, 102 MB. |
| `docs/CanivoPets_Media_Agency_Audit.md` | **ARŞ** → `docs/_archive/customer/` | 1 | 16 KB | müşteri çıktısı |
| `docs/slides/*` | **ARŞ** → `docs/_archive/customer/` | 6 | 136 KB | müşteri sunumu (canivopets + information_economics) |
| `docs/reports/2026_Kapsamli_…Faz1XX.md` (21) + `2026_Otonom_Ajan_Ortamlari_*` (3) | **ARŞ** → `docs/_archive/prototype/` | 24 | 472 KB | silinen prototip ailesinin araştırma notları; koddan atıf yok |
| `docs/specifications/AUTONOMOUS_AGENT_ARCHITECTURE_FAZ126.md` | **ARŞ** → `docs/_archive/prototype/` | 1 | ~10 KB | aynı aile |
| `.entropy/` | **KOR** | ~60 | 3 MB | **canlı kullanıcı durumu** (ayarlar, sohbet geçmişi, çökme günlüğü, rapor indeksi) — `config.py:76` |
| Obsidian kasası (depo dışı) | **KOR** | — | — | `config.py:114 _default_obsidian_vault()` |

### 7.5 `.gitignore`'a eklenecekler (diskte kalır, git görmez)

| Desen | Bugünkü durum | Gerekçe |
|---|---|---|
| `scratch/` | 55 izlenen + **732 izlenmeyen** dosya, 15,4 MB | Ekran görüntüleri, ölçüm betikleri, indirilmiş üçüncü taraf depo. `scratch/pixel-agents-main/` (381 dosya, 4,1 MB) üçüncü taraf bir kopya — **DIŞ** olarak depo dışına taşınmalı; `THIRD_PARTY.md` zaten kaynağı ve MIT lisansını belgeliyor. |
| `test_*/` kök dizin deseni (dar tanımlı) | 200 dosya | tekrar oluşursa git'e sızmasın |
| `module_task_*.py`, `schema_task_*.py`, `test_task_*.py` (kök) | 56 dosya | aynı |
| `.agents/agents/*` (izlenen `distiller` hariç) | 5 üretilmiş | `compile.py` her açılışta `APP_ROOT`'a yazıyor |
| `.claude/agents/{analist,arastirmaci,degerlendirici,orkestrator,yazar}.md` | 5 üretilmiş, **izleniyor** | Entropy'nin ürettiği kadro, kullanıcının geliştirme alt ajanlarıyla aynı klasörde karışıyor (3.4) |

### 7.6 İzlemeye ALINACAKLAR (temizlikten önce)

| Yol | Gerekçe |
|---|---|
| `skills/__init__.py`, `skills/media_agency_soldier/**` (8 dosya) | 5 test dosyası (`test_media_agency_*`, 372 testin bir bölümü) bunlara bağımlı; temiz klonda içe aktarma hatası verir (2.5). Alternatif: testleri izlenen `skills/media-agency-soldier/` (tireli) sürüme yönlendirmek — ama iki sürüm içerik olarak farklı, önce `diff` alınmalı. |
| `scripts/` altındaki 72 izlenmeyen betik | Denetim/rapor üretme betikleri. Karar gerekiyor: değerli olanlar izlemeye, tek seferlikler (`record_faz1XX_memories.py` ailesi) `scratch/`e ya da silmeye. |

### 7.7 Toplam kazanç

| Kalem | Dosya | Boyut |
|---|---:|---:|
| SİL — üretilmiş ikili çıktı | 16.926 | 4.495,8 MB |
| SİL — prototip kaynak + test | 92 | 3,4 MB |
| SİL — kök ajan artıkları | 257 | 0,3 MB |
| **SİL toplamı** | **17.275** | **4.499,5 MB** |
| ARŞ/DIŞ — kullanıcı + prototip belgeleri | 126 | 102,7 MB |
| DIŞ — `scratch/pixel-agents-main` | 381 | 4,1 MB |
| **Genel toplam** | **17.782** | **~4.606 MB** |

**Depo sonrası:** 4.685 MB → **~80 MB** (`.git` 24 + `src` 11 + `tests` 17 + `skills` 4 + `scripts` 3 + `docs` ~1,5 + `.entropy` 3 + ikonlar 1,5 + `scratch` kalanı ~11). Dosya sayısı 18.700 → **~920**.

**Test:** 2.374 → **2.042** (A grubu silinince); D grubu `_reference/` altına alınırsa ana süit **1.817**.

---

## 8. Uygulama sırası (repo-curator için, her adım geri alınabilir)

Kurallar: her adım tek başına commit'lenir; `git stash` / `git checkout --` / `git reset --hard` kullanılmaz; her adımdan sonra hedefli test koşulur (`QT_QPA_PLATFORM=offscreen python -m pytest <dosya> -q -p no:cacheprovider`); "geri alma" sütunu adım başarısız olursa nasıl dönüleceğini söyler.

| # | Adım | Doğrulama | Geri alma |
|---|---|---|---|
| **0** | **Ön koşul:** Entropy `.exe` ve tüm Python süreçleri kapalı (`dist/` kilitli olmasın). Tam süit bir kez koşulur, sayı kaydedilir (beklenen: 2.374 toplandı). | `pytest --collect-only -q` | — |
| **1** | **İzlemeye al:** `skills/__init__.py`, `skills/media_agency_soldier/**`. Tek başına commit. | `pytest tests/test_media_agency_*.py -q` yeşil | `git revert <commit>` |
| **2** | **`.gitignore` genişlet** (7.5 tablosu). Hiçbir dosya silinmez; yalnızca git görüşü daralır. | `git status -uall` çıktısı 1.262 → ~120 | `git revert` |
| **3** | **Üretilmiş ikili çıktıyı sil:** `dist/`, `dist_check/`, `build/`, `build_check/`, kök `EntropyAI.exe`, tüm `__pycache__`, `.pytest_cache/`. Hiçbiri izlenmiyor → **commit gerekmez**. | `du -sm .` → ~185 MB | `pyinstaller EntropyAI.spec` ile yeniden üretilir (tek gerçek maliyet: derleme süresi) |
| **4** | **Kök ajan artıklarını sil:** 56 `.py`, 5 test dizini (200 dosya), `financial-auditor/`, boş `reports/`. Hiçbiri izlenmiyor → commit gerekmez, ama `git status` temizliği not düşülür. | `ls *.py` → yalnızca `run_entropy.py`; `pytest -q --collect-only` sayısı **değişmemeli** (2.374) | dosyalar üretilmiş; geri alınacak bir şey yok. Şüphe varsa adım 3'ten önce `%TEMP%`'e kopyalanır. |
| **5** | **Kullanıcı çıktısını taşı:** kök `*_audit.md/json` → `docs/_archive/customer/`; `docs/CanivoPets_*`, `docs/slides/*` → `docs/_archive/customer/`; `google_flow_files/` ve `scratch/pixel-agents-main/` → depo dışı klasör. `git mv` kullan (izlenenler için). | `git status` yalnızca yeniden adlandırma göstermeli | `git revert` (izlenenler) / elle geri kopyala (izlenmeyenler) |
| **6** | **Prototip testlerini sil:** `tests/test_autonomous_agent_architecture_faz*.py` (32 dosya). | `pytest --collect-only -q` → **2.042** | `git revert` |
| **7** | **Prototip kaynağını sil:** `src/entropy/tools/autonomous_agent_architecture*.py` (60 dosya). `EntropyAI.spec`'te bu aileye ait girdi yok (doğrulandı) → spec'e dokunulmaz. | `python -c "import entropy.main"` hatasız; `pytest -q` → 2.042 yeşil | `git revert` (izlenen 3 dosya için); kalan 57 dosya izlenmiyordu — kaybı kabul edilir, gerekirse adım 6 öncesi yedeklenir |
| **8** | **Prototip belgelerini arşivle:** `docs/reports/2026_Kapsamli_*` (21), `2026_Otonom_Ajan_Ortamlari_*` (3), `docs/specifications/AUTONOMOUS_…FAZ126.md` → `docs/_archive/prototype/`. `git mv`. | koddan atıflı 3 rapor **taşınmadı** mı: `grep -rhoE "docs/reports/[^\"']+\.md" src/entropy` sonuçlarının hepsi hâlâ var mı | `git revert` |
| **9** | **`docs/` iskeletini kur:** `ARCHITECTURE.md`, `STATE.md`, `ROADMAP.md`, `adr/ADR-0001-…`, `_archive/README.md`. `PHASED_ROADMAP.md` → `ROADMAP.md` (`git mv` + yeniden yaz). | 5 alt ajan tanımının aradığı `docs/STATE.md` artık var | `git revert` |
| **10** | **Kök markdown'ları düzelt:** `GEMINI.md` §3 dizin haritasını gerçekle eşitle (`agent_desk` → `desk`, `agents/` ekle, `Agents/` ve `run_agent_desk.py` sil, `tools/` satırını düzelt); `AGENTS.md`'yi sahte kadro listesinden arındır. **`CLAUDE.md` bu adımda OLUŞTURULMAZ** — önce 3.3'teki `--add-dir` / CLAUDE.md sızıntısı ölçülmeli (ayrı kart). | `ls -d $(grep -oE '^│ *├── [A-Za-z_/.]+' GEMINI.md)` benzeri bir kontrol; elle okuma | `git revert` |
| **11** | **Testleri yeniden düzenle** (ayrı commit, yalnızca `git mv`): `tests/contracts/`, `tests/ui/`, `tests/skills/`, `tests/_reference/` (D grubu). `pyproject.toml` `testpaths` gerekiyorsa güncellenir. | `pytest --collect-only -q` sayısı **değişmemeli** (2.042); `_reference` hariç tutulursa 1.817 | `git revert` |
| **12** | **Kapanış ölçümü:** tam süit + `pyinstaller EntropyAI.spec` ile `dist_check`'e bir derleme + `.exe` smoke test. Önce/sonra tablosu (dosya sayısı, MB, test sayısı) `docs/STATE.md`'ye yazılır. | süit yeşil, `.exe` açılıyor | — |

**Aşama 2 (ayrı onay):** `entropy.memory` → `entropy.brain` (6.3). Ön koşul: adım 12 yeşil.

---

## 9. Kaynaklar

**Yerel CLI belgeleri (bu makinede çalıştırıldı, model çağrısı yok):**
1. `claude --help` — `--bare`, `--setting-sources`, `--strict-mcp-config`, `--agents`, `--add-dir`, `--system-prompt-file`, `--append-system-prompt-file` açıklamaları. Yol: `C:\Users\batu_\AppData\Roaming\npm\claude`.
2. `agy --help` — bayrak ve alt komut listesi (`agents`, `mcp`, `models`, `plugin`). Yol: `C:\Users\batu_\AppData\Local\agy\bin\agy`. `--setting-sources` / `--strict-mcp-config` **yok**.

**Depo içi birincil kanıt (dosya:satır):**
3. `EntropyAI.spec` — `hiddenimports` listesi; `AGENTS.md` paketlenmeme gerekçesi; Faz 10-C `importlib` notu.
4. `src/entropy/core/claude_bridge.py:123, 137–160, 720, 769–780, 826–850, 1517–1536, 1552–1579` — izolasyon bayrakları ve nötr çalışma dizini.
5. `src/entropy/core/agy_bridge.py:644, 1361, 2045` — agy ajan keşfi ve proje dizininde koşum.
6. `src/entropy/core/provider.py:1144–1160` — `AGENT_DEFINITION_LAYOUT`.
7. `src/entropy/agents/compile.py:1–22, 312–348, 351–370` — iki biçime derleme ve `compile_roots()` (`APP_ROOT` dahil).
8. `src/entropy/agents/tasks.py:1–30, 147–204` — kart dosya biçimi ve ön bilgi şeması.
9. `src/entropy/memory/office_workspace.py:1–56` — `BOARD.md` / `ARCHITECTURE.md` / `RULES.md` / `checkpoints/` düzeni ve doğuş talimatı.
10. `src/entropy/agents/harness.py:855–966, 1624, 1832, 1997, 2216` — çalışma alanı ve pano çağrıları.
11. `src/entropy/core/config.py:22–34, 76–101, 114–137` — `APP_ROOT`, `STATE_DIR`, kasa çözümü.
12. `src/entropy/skills/__init__.py:1–32` — PEP 562 tembel yükleme (`_LAZY`).
13. `tests/conftest.py:1–30, 108–132` — kullanıcı durumu ve kasa yalıtımı; kök test artıklarının gerekçesi.
14. `tests/test_phase8_graph_data.py:75–86` — `is_test_artifact_name` koruması.
15. `src/entropy/tools/autonomous_agent_architecture.py:12965–13150` — faz modüllerinin yeniden dışa aktarımı.
16. `.claude/agents/repo-curator.md:12`, `ui-engineer.md:17,20`, `qa-build-engineer.md:20`, `memory-rag-engineer.md:20`, `agy-integration-engineer.md:21` — var olmayan `docs/STATE.md` / `ARCHITECTURE.md` / `ROADMAP.md` / `adr/` atıfları.
17. `THIRD_PARTY.md` — pixel-agents (MIT) ve CC0 piksel varlık bildirimleri.
18. `pyproject.toml` — `readme = "GEMINI.md"`, `pythonpath = ["src"]`, `testpaths = ["tests"]`, bağımlılıklar.

**Kullanılan komutlar (tamamı salt okuma):**
`git ls-files`, `git status --short -uall --porcelain`, `git check-ignore -v`, `git log --oneline`, `git rev-list --count`, `du -sm`, `find`, `wc -l`, `grep -rn/-rl/-rhoE`, `python -m pytest --collect-only -q -p no:cacheprovider`, hedefli `pytest` koşumu, geçici AST içe aktarma tarayıcısı (oturum geçici dizininde).
