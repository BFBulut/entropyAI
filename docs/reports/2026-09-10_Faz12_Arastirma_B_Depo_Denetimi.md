# Faz 12 — Araştırma B: Depo Denetimi, Temizlik Manifesti ve Proje Yapısı

- **Depo:** `C:\EntropiAI` — dal `ai/v0.1.7`, HEAD `1815f32` (Faz 11-E tasarım sistemi).
- **Kip:** SALT OKUNUR. Bu rapor dışında hiçbir dosya oluşturulmadı, silinmedi, taşınmadı, değiştirilmedi. Gerçek model çağrısı yapılmadı.
- **Ölçüm tarihi:** 2026-09-10. Önceki tur: `docs/reports/2026-09-10_Faz11_Arastirma_B_Depo_Denetimi.md`.
- **Marka kuralı:** ticari referans ürünün ve üreticisinin adı bu raporun hiçbir yerinde geçmez.

> Yöntem: tüm sayılar komut çıktısıdır. İçe aktarma grafiği, oturum geçici dizininde koşan
> bir AST tarayıcısıyla üretildi (depoya yazılmadı). Tam süit bir kez koşuldu (402,85 s).

---

## 0. Faz 11-A/B/C/D/E sonrası: ne değişti

| Ölçüm | Faz 11 turu (11-A öncesi) | 11-A sonrası (STATE) | **Bugün (Faz 12)** | Kanıt |
|---|---:|---:|---:|---|
| Disk (`.git` dahil) | 4.685 MB | 69 MB | **1.459 MB** | `du -sm .` |
| bundan `dist/` + `build/` | ~4.500 MB | 0 | **1.207 + 179 MB** | `du -sm dist build` |
| Dosya sayısı (`.git` hariç) | 18.700 | 1.657 | **9.098** | `find . -path ./.git -prune -o -type f -print \| wc -l` |
| `.git` | 24 MB | — | **28 MB** | `du -sm .git` |
| İzlenen dosya | 618 | 658 | **765** | `git ls-files \| wc -l` |
| `git status --short -uall` | 1.262 | 268 | **10** (9'u değişmiş `scratch` PNG + 1 yeni rapor) | aynı komut |
| Kökteki `.py` | 57 | 1 | **1** (`run_entropy.py`) | `ls *.py` |
| `src/entropy` modülü | 183 | — | **142** | AST tarayıcı |
| Toplanan test | 2.374 | 2.042 | **2.347** | `pytest --collect-only -q` |
| Tam süit | 353 s / 3 fail | 427 s / 6 fail | **402,85 s · 2.343 passed, 4 failed** | `pytest -q --durations=15` |

**Sonuç:** Faz 11-A temizliği tuttu. Bugünkü 1.459 MB'ın **%95'i** (1.386 MB) yeniden
üretilebilir `dist/` + `build/`; git'in gördüğü her şey yaklaşık **48 MB**'dır
(izlenen ağaç: src 7,7 + tests 17,1 + skills 3,3 + scripts 1,5 + docs 1,8 + scratch 13,8 MB).
Depoda artık kök ajan artığı, prototip ailesi, 475 MB'lık kök `.exe` **yok**.

---

## 1. Envanter

### 1.1 İzlenen dosyalar (765)

```
246 src   195 tests   87 skills   84 docs   80 scripts   55 scratch   11 (kök)   6 .claude   1 .agents
```
Kanıt: `git ls-files | awk -F/ '{if (NF==1) print "(root)"; else print $1}' | sort | uniq -c | sort -rn`

Kökteki 11 izlenen dosya: `.gitignore`, `AGENTS.md`, `EntropyAI.spec`, `EntropyAI_OneFile.spec`,
`GEMINI.md`, `THIRD_PARTY.md`, `entropy.ico`, `entropy.png`, `launch.bat`, `pyproject.toml`,
`run_entropy.py`. **`CLAUDE.md` yok** (`ls CLAUDE.md` → yok), `.mcp.json` yok.

### 1.2 İzlenmeyen (10 satır)

`git status --short -uall --porcelain` çıktısının tamamı: 8 değişmiş `scratch/ui/phase10/*.png`,
2 değişmiş kaynak (`core/slash_commands.py`, `ui/widgets/tasks_widget.py` — paralel çalışan
başka bir ajanın ara hâli) ve 1 yeni rapor (`docs/reports/2026-09-10_Faz11_Ilerleme_Raporu_v0.9.4.md`).
**Faz 11'in "68 untracked betik" açık işi kapanmış**: `scripts/` altındaki 80 `.py`'nin
tamamı artık izleniyor (`git ls-files scripts | wc -l` → 80).

### 1.3 Yok sayılan büyük kalemler

| Yol | Boyut | Not |
|---|---:|---|
| `dist/` | 1.207 MB | `.gitignore`'da; `EntropyAI.spec` ile yeniden üretilir |
| `build/` | 179 MB | PyInstaller ara çıktısı |
| `.entropy/` | 3 MB | **KULLANICI VERİSİ — silinmez** (`core/config.py` `_resolve_state_dir`) |
| `__pycache__` (tüm depo) | 386 `.pyc` yalnız `src`+`tests` altında | `.gitignore`'da |

### 1.4 İzlenen ağaçtaki en ağır kalemler

| Kalem | Boyut | Karar adayı |
|---|---:|---|
| `tests/` | 17,1 MB | §5 — 82 dosyası ürün kodunu sınamıyor |
| `scratch/` (55 izlenen PNG) | 5,8 MB | ekran görüntüsü arşivi; `docs/_archive/ui/` ya da depo dışı |
| `entropy.png` | 1,37 MB | kök logo (tek dosya, 1,4 MB — 256 px PNG yeterli olur) |
| `skills/` | 3,3 MB | §2.4 — üçüzleme var |
| `scripts/` | 1,5 MB | §6 — 1,02 MB'ı tek seferlik betik |

---

## 2. İçe aktarma grafiği (142 modül)

Yöntem: `src/entropy/**` altındaki 142 modül AST ile tarandı (göreli içe aktarmalar çözüldü);
içe aktaranlar `src/`, `tests/`, `scripts/`, `run_entropy.py` içinde arandı; ayrıca `*.spec` ve
`pyproject.toml` içindeki **dizgi** kullanımları (`'entropy.x.y'`) ayrı sayıldı.

### 2.1 Yetim modül: **yok**

Hiçbir içe aktaranı olmayan 6 ad (`entropy.desk.engine`, `entropy.mcp`, `entropy.platform`,
`entropy.skills`, `entropy.skills.media_agency_soldier`, `entropy.tools`) **yanlış pozitiftir**:

- `entropy.desk.engine`, `entropy.mcp`, `entropy.platform`, `entropy.tools` → **paket
  `__init__.py`'leri**; alt modülleri doğrudan içe aktarılıyor (ör. `desk/scene.py:32-47`
  `from entropy.desk.engine.assets/…` yedi ayrı satır).
- `entropy.skills` + `entropy.skills.media_agency_soldier` → PEP 562 tembel yükleme:
  `src/entropy/skills/__init__.py:16-29` `_LAZY = {"PDFIngestionEngine": …,
  "MediaAgencySoldierEngine": "entropy.skills.media_agency_soldier"}` + `importlib`.
  Pakete girmesi `EntropyAI.spec:165-166` hiddenimports'a bağlı — **AST bunu göremez, silinmemeli.**

### 2.2 Yalnız testten erişilen ürün modülleri

| Modül | İçe aktaran | Spec'te | Durum |
|---|---|---|---|
| `entropy.core.claude_bg` (741 satır) | **yalnız** `tests/test_phase11_claude_bg.py` | **HAYIR** | Faz 11-F "kalıcı terminal" spike'ı; rapor (`2026-09-10_Faz11F_Spike_Kalici_Terminal.md`) **ertelendi** diyor. Üründe çağıran yok, `.exe`'ye girmiyor. **Karar gerekli** (bkz. §7). |
| `entropy.platform.autostart` (2.692 B) | `tests/test_exe.py`, `tests/test_scheduler.py` | evet (iki spec) | **Faz 11'den beri değişmedi.** `autostart_enabled` yalnızca `config.py:329/488/531-532`'de okunup yazılıyor; uygulayan kod yok (`grep -rn autostart src/entropy/main.py src/entropy/ui` → boş). Ayar var, davranış yok. |
| `entropy.core.perf_history` | `scripts/perf_bench.py`, `scripts/routing_eval.py` + test | evet | geliştirici aracı — **korunur** |

`entropy`, `entropy.desk`, `entropy.ui`, `entropy.ui.modes`, `entropy.ui.widgets`,
`entropy.scheduler` de "yalnız test" görünür; hepsi **paket `__init__`'i**, alt modülleri
üründen içe aktarılıyor.

### 2.3 `EntropyAI.spec` ile kaynak arasındaki sapma (yeni bulgu)

`EntropyAI.spec` hiddenimports'ta **128 `entropy.*` girdisi** var. Ters yönde tarandığında
**15 kaynak modülü spec'te hiç geçmiyor** — hepsi Faz 11'de eklenenler:

```
entropy.agents.amplification   entropy.agents.board_events   entropy.agents.board_fsm
entropy.agents.board_tools     entropy.agents.dispatcher     entropy.core.claude_bg
entropy.memory.categories      entropy.memory.dream          entropy.memory.gate
entropy.memory.gray_merge      entropy.ui.widgets.agent_session_badge
entropy.ui.widgets.header_bar  entropy.ui.widgets.nav_list
entropy.ui.widgets.report_card_bridge  entropy.ui.widgets.report_chat_card
```

Bunların çoğu statik `import` ile çağrıldığı için PyInstaller'ın tarayıcısı **muhtemelen**
yakalar; ama spec'in kendi yorumu Faz 10-C'de tam olarak bu sınıf bir sessiz düşmeyi kaydediyor
(*"bu modüller yalnizca calisma aninda importlib ile cagriliyor; … .exe'de worktree/PR/sablon/
makbuz yollari sessizce kapaniyordu"*) ve `ui/widgets/memory_inspector_dialog.py:502-503`
bugün de modül adını **dizgi** olarak veriyor (`"entropy.memory.graph_store"`,
`"entropy.memory.cognitive_memory"`). **Doğrulanamadı:** onedir çıktısında bu 15 modülün
paketlenip paketlenmediği diskten görülemiyor (uygulama modülleri PYZ içinde). §7'de bunun
için kanıtlı bir QA reçetesi var. Bu, §6'daki `memory → brain` taşımasının **en büyük riski**.

`EntropyAI.spec`'te var olmayan tek ad `entropy.ico`'dur (dosya adı, modül değil — zararsız).

### 2.4 `skills/` — aynı yeteneğin üç kopyası (yeni bulgu)

| Yol | İzlenen | Dosya | Boyut | `SKILL.md` | Rolü |
|---|---:|---:|---:|---|---|
| `skills/media-agency-soldier/` | 17 | 23 | 627 K | var | **Yetenek paketi** (`SkillManager` bunu tarar) |
| `skills/media-agency-soldier/scripts/` | — | 7 `.py` / 4.928 satır | — | — | asıl kod |
| `skills/media_agency_soldier/` | 8 | 16 | 153 K | **yok** | **Python paketi** — 5 test dosyası buradan içe aktarıyor |
| `skills/slide-deck-architect/` | 3 | 3 | 49 K | var | yetenek paketi |
| `skills/slide_deck_architect/` | 2 | 4 | 94 K | **yok** | Python paketi (`tests/skills/test_slide_deck_architect.py`) |

Üç sürüm de **içerik olarak farklı** (`diff -q` ile birebir karşılaştırıldı: `campaign_architect.py`
44 vs 987 satır, `url_analyzer.py` 949 vs 946 satır → **yakın kopya, aynı değil**). Yani bugün
"medya ajansı" mantığının üç ayrı gerçeği var: yetenek paketinin kökü (ince sarmalayıcılar),
`scripts/` (asıl 4.928 satır) ve testlerin kullandığı alt çizgili paket (1.123 satır).
Ayrıca `EntropyAI.spec` `datas` girdisi `('skills','skills')` olduğu için **her üçü de `.exe`
içine kopyalanıyor**. Faz 11'in "izlemeye al" önerisi uygulanmış ama **tekilleştirme yapılmamış**.

---

## 3. Kök markdown ve CLI dosyaları

### 3.1 Durum

| Dosya | Durum | Boyut / tarih | Yargı |
|---|---|---|---|
| `AGENTS.md` | izleniyor | 4.263 B, 2026-09-10 | **GÜNCEL ve doğru.** Faz 11-A'da yeniden yazılmış: kadro listesi değil, "ajan nerede tanımlanır" belgesi. `AGENT_DEFINITION_LAYOUT` alıntısı `core/provider.py` ile birebir; 7 değişmez sayılıyor. Doğrulanan tek eksik: §4'teki olay listesi `board_state_changed` ve `task_report_ready` sinyallerini saymıyor (`STATE.md` §3'te var). |
| `GEMINI.md` | izleniyor | 12.142 B | **§3 dizin haritası GÜNCEL** (agent_desk/persona.md temizlenmiş, "bilerek olmayanlar" bölümü eklenmiş). **§1–§2 ESKİ:** başlık hâlâ "Antigravity Interface", §1.1 *"Antigravity CLI (AGY) as Core Engine"*, §1.3 *"Supabase pgvector & Mem0"*. Ölçüm: dosyada `claude` kelimesi **3 kez** geçiyor, üçü de dizin haritasında/dipnotta — **çift sağlayıcı gerçeği §1'e hiç yansımamış**, oysa `ADR-0002` ve `STATE.md` Claude Saf Kip'i birincil koşum yolu sayıyor. |
| `CLAUDE.md` | **YOK** | — | **Bilerek yok** ve GEMINI.md:119 ile ADR-0002 gerekçeyi yazıyor. Faz 11-B ölçümü hâlâ geçerli: `--setting-sources ""` ayar kaynaklarını kapatır, **`CLAUDE.md` otomatik keşfi ayrı mekanizmadır**. **Karar: oluşturulmasın** (ölçülmeden kesinlikle hayır). |
| `.claude/agents/` | 6 dosya | — | **Tam olarak 6 geliştirme ajanı:** `agy-integration-engineer`, `memory-rag-engineer`, `qa-build-engineer`, `repo-curator`, `research-scout`, `ui-engineer`. Entropy'nin ürettiği beşli **artık yok** (ada göre `.gitignore`'da). Faz 11 bulgusu **kapandı**. |
| `.agents/agents/` | 6 klasör, izlenen **1** (`distiller`) | — | `analist, arastirmaci, degerlendirici, orkestrator, yazar` diskte duruyor ama `.agents/` `.gitignore`'da → git görmüyor. Beklenen davranış. |
| `EntropyAI_OneFile.spec` | izleniyor, 2.513 B, **2026-09-05'ten beri dokunulmamış** | — | **ÇÜRÜMÜŞ** (§3.2) |
| `pyproject.toml` | izleniyor | — | `version = "0.8.0"`, oysa `src/entropy/__init__.py:3` `__version__ = "0.1.0"` ve görev/etiket **v0.9.4**. **Üç ayrı sürüm gerçeği.** Ayrıca bağımlılık yorumları ölü pakete atıf yapıyor: *"numpy … agent_desk/analysis/* modüllerinde"*, *"pillow … agent_desk/core/media_payload_handler.py"* — `src/entropy/agent_desk` **yok**; numpy'yi gerçekte 3 dosya kullanıyor (`memory/dream.py`, `memory/graph_store.py`, `memory/supabase/cognitive_memory.py`), **PIL/pillow'u ise depoda hiçbir dosya içe aktarmıyor** (`grep -rln "from PIL\|import PIL" src skills scripts tests` → 0 sonuç). |

### 3.2 `EntropyAI_OneFile.spec` gerekli mi → **HAYIR**

| Kanıt | Ölçüm |
|---|---|
| Referans | Depoda `launch.bat`, `pyproject.toml`, herhangi bir betik ya da CI **hiç çağırmıyor**; adı yalnızca `GEMINI.md:61` dizin haritasında ve Faz 11 raporunda geçiyor |
| hiddenimports | **32 girdi** vs `EntropyAI.spec` **127** girdi |
| Eksik paketler | `entropy.agents` **0**, `entropy.desk` **0**, `entropy.mcp` **0**, `entropy.memory.gate/dream/board_fsm` **0** (`grep -c` ile ölçüldü) — yani Faz 5 sonrası hiçbir şey yok |
| Taşınabilirlik | `pathex=['c:/EntropiAI/src', 'c:/EntropiAI']` — **makineye çakılı mutlak yol** |
| datas | `('src/entropy','entropy')` — kaynağı ham kopyalıyor (`EntropyAI.spec` bunu yapmıyor) |

**Karar: arşivle** (`docs/_archive/` ya da sil). Onefile derleme gerekirse `EntropyAI.spec`
üzerinden `--onefile` eşdeğeri tek commit'te yeniden türetilebilir; bugünkü hâliyle koşulursa
**bozuk bir `.exe` üretir** ve kimse bunu fark etmez.

---

## 4. Docs

### 4.1 Bugünkü ağaç

```
docs/  1.792 K
├── ARCHITECTURE.md   274 satır
├── STATE.md          563 satır
├── ROADMAP.md         70 satır
├── adr/               ADR-0001…0005
├── reports/          872 K · 31 dosya
├── specifications/    32 K · 5 dosya (hepsi 2026-09-03)
└── _archive/         792 K (prototype 25 · customer 10 dosya)
```

### 4.2 `ARCHITECTURE.md` canlı mı → **kısmen** (yeni ölçüm)

274 satırlık dosyada Faz 11-C/D'nin ürettiği sözleşmelerin adları **hiç geçmiyor**:

| Terim | `docs/ARCHITECTURE.md` içinde geçiş |
|---|---:|
| `MemoryGate` | 1 |
| `wiki` | 5 |
| `TASKBOARD` | 1 |
| `board_fsm` | **0** |
| `dream` | **0** |
| `gray_merge` | **0** |
| `amplification` | **0** |
| `claude_bg` | **0** |

Başlığı da `> Sürüm: v0.8.0 · … Son güncelleme: 2026-09-10 (Faz 11-A)` diyor. §10 "Faz 11
hedef mimarisi" panoyu ve beyni **hedef** olarak anlatıyor, oysa ikisi de artık **kod**
(`agents/board_fsm.py`, `memory/gate.py`, `memory/dream.py`, `memory/gray_merge.py`).
**Yani ARCHITECTURE.md bir faz geride:** sözleşmelerin tek doğru kaynağı bugün `STATE.md` §3
(563 satır, 2026-09-10 QA'sıyla güncel). Bu, iki dosyanın rolünü tersine çevirmiş durumda —
`STATE.md` "çalışma belleği" olmaktan çıkıp mimari sözlüğe dönüşmüş.

### 4.3 `docs/specifications/` — beşi de damıtılmalı

Beş dosyanın **tamamı 2026-09-03 tarihli** (`ls -l`), yani Claude köprüsü, Desk ayrımı, pano
ve beyin v2'den **önce**. İlk 12 satırları bugünkü gerçeğe aykırı:

| Dosya | Çelişki (alıntı) | Gerçek |
|---|---|---|
| `AGY_CLI_INTEGRATION.md` | *"Entropy AI connects strictly via the installed and authenticated `agy` CLI"* | iki köprü var; Claude birincil (`ADR-0002`) |
| `MEMORY_RAG_SPECIFICATION.md` | *"Supabase pgvector & Mem0"*, *"Layer 12: EGO … Agents/EntropyAI/persona.md"* | `ADR-0003` "mem0 değil" diyor; `persona.md` yok; kategori kapalı kümesi 4 |
| `SYSTEM_ARCHITECTURE.md` | tri-modal UI mermaid şeması | Desk + pano + beyin katmanı hiç yok |
| `UI_SPECIFICATION.md` | sabit hex paleti (`#0B0F19`, `#00F0FF`) | Faz 11-E tasarım belirteçleri (`ADR-0005`, `ui/design/tokens.py`) |
| `TASK_SCHEDULER_SPECIFICATION.md` | cron tanımı | tek gerçekten hâlâ geçerli olan; `scheduler/cron_engine.py` ile eşleşiyor |

**Karar:** `TASK_SCHEDULER_SPECIFICATION.md`'nin özü `ARCHITECTURE.md`'ye alınır; beşi birden
`docs/_archive/specifications/` altına taşınır. Faz 11 açık işi (#6) böylece kapanır.

### 4.4 `docs/reports/` — 31 dosya, arşiv kuralı

Faz 11'de 48 idi, arşivlemeyle **31**'e indi (25 prototip notu `_archive/prototype/`,
10 müşteri çıktısı `_archive/customer/` altında). Bugün acil bir şişme yok, ama kural yazılmamış.

Koddan/testten atıf yapılan raporlar (**taşınamaz**), `grep -rhoE "docs/(reports|specifications|adr)/[^\"']+\.md" src/entropy tests scripts`:

| Rapor | Atıf |
|---|---:|
| `2026-09-10_Faz5_Tasarim_Raporu.md` | 3 |
| `2026-09-11_Faz9_Teshis_Notu.md` | 2 |
| `2026-09-10_Faz11_Arastirma_D_Arayuz_Tasarim_Denetimi.md` | 2 |
| `2026-09-10_Faz11_Arastirma_A_Hafiza_ve_RAG.md` | 1 |
| `2026-09-11_Faz10_Teshis_ve_Mimari_Bosluk_Notu.md` | 1 |

**Kırık atıf (yeni bulgu):** `scripts/sync_faz150_obsidian.py:18` hâlâ
`Path(r"C:\EntropiAI\docs\reports\2026_Kapsamli_…_Faz150.md")` okuyor; o dosya Faz 11-A'da
`docs/_archive/prototype/` altına taşındı → betik bugün **çalışmaz**. Aynı ailedeki 6 betik
mutlak `C:\EntropiAI` yolu içeriyor (`grep -l 'C:\\EntropiAI' scripts/*.py | wc -l` → 6).

**Önerilen kural (ARCHITECTURE.md'ye yazılacak):** `docs/reports/` yalnızca **son iki fazın**
raporlarını + koddan atıflı raporları tutar; kapanan faz `docs/reports/_archive/fazNN/`
altına iner. Atıf yapılan bir rapor taşınacaksa aynı commit'te koddaki yol da güncellenir.

---

## 5. Test düzeni

### 5.1 Ölçüm

- `pytest --collect-only -q -p no:cacheprovider` → **2.347 test**, 186 `test_*.py` dosyası, 1,58 s.
- Tam süit `QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider --durations=15`
  → **2.343 passed, 4 failed, 402,85 s**.
- Dizin düzeni **kurulmuş**: `tests/{contracts,ui,desk,skills}` (+ `__init__.py`'leri var),
  kökte hâlâ 130+ dosya.

### 5.2 Neyi sınıyoruz (AST ile içe aktarma hedefine göre)

| Grup | Dosya | Ne sınıyor |
|---|---:|---|
| **C — ürün** | 101 | `entropy.*` |
| **B — yetenek** | 2 | `skills/**` |
| **scripts** | 1 | `scripts/*` |
| **D — kendi kendine yeten** | **82** | depodan **hiçbir şey** içe aktarmıyor |

D grubunun ölçülen maliyeti: **563 test / 6,91 s** (82 dosya, `tests/` boyutunun büyük kısmı).
Yani **testlerin %24'ü sevk edilen hiçbir kodu sınamıyor**; bunlar nicel finans "ispat
defterleri" (`test_faz36…faz68_finance_models.py` + 50 model dosyası). Faz 11'in
`tests/_reference/` önerisi **uygulanmamış** — 82 dosya hâlâ `tests/` kökünde ve ana süite
dahil. Hız sorunu değil (%1,7 süre), **ölçüm dürüstlüğü** sorunu: "2.347 test yeşil" cümlesi
ürün güvencesini %24 abartıyor.

### 5.3 Yavaşlık nerede

En yavaş 15 testin toplamı ≈ 110 s (süitin %27'si), tamamı graf/UI:

| Test | Süre |
|---|---:|
| `test_graph_radial_layout_and_reader.py::…settles_deterministically_without_overlap[60]` | 16,49 s |
| `…::test_similarity_links_pull_related_reports_together` | 10,69 s |
| `…::test_graph_has_no_cluster_toggle_nodes` | 9,62 s |
| `test_routing_holdout.py::test_no_false_positive_regression_on_eval_set` | 8,06 s |
| `tests/ui/test_ui_agents_and_task_board.py::…same_provider_and_context_controls` | 7,94 s |

Tek başına `test_graph_radial_layout_and_reader.py` üç testte **36,8 s** yakıyor — fizik
yerleşimi gerçek yineleme sayısıyla koşuyor. Aday: yineleme sayısını parametreye alıp
ana süitte küçük N, `slow` işaretinde büyük N.

### 5.4 Sıra bağımlılığı → **yok** (4 hata gerçek)

Dört başarısız test tek tek, yalıtılmış koşuldu; **dördü de tek başına da düşüyor** →
sıra bağımlılığı değil, **Faz 11-E arayüz yeniden tasarımının bıraktığı gerçek regresyonlar**:

| Test | Hata (aynen) |
|---|---|
| `tests/test_agy_bridge.py::test_chat_mode_terminal_button_no_attribute_error` | `assert 'Terminali kapat' == '▼ Terminali Kapat'` |
| `tests/test_prompt_integrity_and_multi_slash.py::test_slash_popup_multi_selection_clicking` | `assert '[]' == '[✓]'` |
| `tests/test_graph_radial_layout_and_reader.py::test_reports_viewer_grouping_filter_and_search` | `viewer.filter_combo.findData("skill:…")` beklentisi |
| `tests/test_hierarchical_knowledge_graph.py::test_multi_hub_hierarchy_and_scope_filtering` | `"hub-projects" in hub_ids` |

İlk ikisi doğrudan emoji/glif temizliğinin (`STATE.md`: emoji 358 → 7) yan etkisi: testler
`▼` ve `✓` glifini bekliyor. Karar **sahibinde**: ya testler yeni tasarım sözleşmesine
(erişilebilir ad + ikon) göre yazılır, ya düğme metni geri gelir. Bu rapor kod değiştirmez.

**Yük altında zaman aşımı:** tam süitte zaman aşımı/asılma gözlenmedi (402,85 s, `EXIT=0`);
`pytest-timeout` kurulu değil, `addopts` yalnızca `-p no:unraisableexception`.
Yalıtım tarafında `tests/conftest.py` (213 satır) **9 autouse fixture** ile kasa ve
`~/.entropy`'yi izole ediyor; süit koşumu sırasında yeni kullanıcı verisi yazılmadı.

---

## 6. Yapı önerisi — `entropy.memory` → `entropy.brain` (güncel maliyet)

### 6.1 Bugünkü yüzey (Faz 11'deki 104 dosya ölçümünün tekrarı)

| Yüzey | Faz 11 | **Bugün** | Kanıt |
|---|---:|---:|---|
| `src/` dosyası | 41 | **45** | `grep -rl 'entropy\.memory\b' src/entropy --include=*.py \| wc -l` |
| `tests/` dosyası | 41 | **49** | aynı, `tests` |
| `scripts/` dosyası | — | **60** | aynı, `scripts` |
| `EntropyAI.spec` satırı | 22 | **22** | `grep -c` |
| `docs/` dosyası | — | **4** | aynı, `docs` |
| **Değişecek satır (src+tests+spec)** | — | **486** | `grep -rn … \| wc -l` |
| Göreli içe aktarma (`from .memory`) | — | **0** | `grep -rn 'from \.\.\?memory' src/entropy` |

**Kritik gözlem:** 60 `scripts/` dosyasının **55'i tek seferlik `record_/save_/sync_` ailesi**
(§7). Bu aileye önce karar verilirse taşıma yüzeyi **154 → 99 dosyaya** düşer
(`scripts` tarafında yalnızca 5 gerçek araç kalır: `brain_metrics.py`, `memory_blind_test.py`,
`memory_migrate_v2.py`, `graph_metrics.py`, `perf_bench.py`). **Sıra önemlidir.**

### 6.2 Riskler (ölçülmüş)

1. **Dizgi ile modül adı (AST göremez).** `ui/widgets/memory_inspector_dialog.py:502-503`
   `"entropy.memory.graph_store"` / `"entropy.memory.cognitive_memory"`;
   `memory/supabase/cognitive_memory.py:36` `logging.getLogger("entropy.memory.cognitive")`
   (kozmetik ama günlük süzgeçlerini kırar). `sed` taraması bu üçünü de yakalar; **AST tabanlı
   refactor aracı yakalamaz** (ADR-0004 bunu zaten uyarmış).
2. **Spec sapması (§2.3).** Taşımadan **önce** 15 eksik girdinin durumu ölçülmeli; taşıma
   sırasında 22 `entropy.memory` satırı yeniden yazılacak ve bir satır atlanırsa `.exe`
   sessizce eksik paketlenir.
3. **Belge atıfları:** `.claude/agents/memory-rag-engineer.md`, `docs/ROADMAP.md`,
   `docs/STATE.md` `entropy/memory` yolunu yazıyor; ayrıca 31 rapor tarihsel kayıt olduğu için
   **düzeltilmez** (rapor geçmişi dondurulur, yalnızca canlı belgeler güncellenir).
4. **Kullanıcı verisi göçü gerekmiyor** (ADR-0004'te ölçülmüştü): `~/.entropy` altındaki
   durum paket adına göre anahtarlanmıyor. `~/.entropy/cognitive_memory.db` şeması etkilenmez.
5. **Ön koşul karşılanmadı.** ADR-0004 üç ön koşul koyuyordu: ARCHITECTURE.md yazılmış
   (**kısmen**, §4.2), tam süit yeşil (**hayır**, 4 hata), `.exe` sorunsuz derlenmiş
   (son yeşil derleme 2026-09-10 QA'sında; Faz 11-E sonrası **derleme yapılmadı**).

### 6.3 Öneri: **Faz 12'de de taşıma yapılmasın — ön koşullar kapanana kadar ertele**

Gerekçe ölçüyle: taşıma **99–154 dosyaya** dokunur ve tek kazancı adlandırmadır; buna karşılık
bugün süitte **4 kırmızı** var ve spec ile kaynak arasında **15 modüllük** ölçülmemiş sapma
mevcut. Taşıma bu ikisinin üstüne binerse, çıkacak bir `.exe` hatasının sebebi
(tasarım regresyonu mu, spec sapması mı, yeniden adlandırma mı) **ölçülemez** hâle gelir —
ADR-0004'ün gerekçesinin aynısı, güncel sayılarla.

**Ön koşullar kapandıktan sonra adım planı (tek commit, geri alınabilir):**

| # | Adım | Doğrulama |
|---|---|---|
| 1 | Tek seferlik `scripts/` ailesine karar (§7) → yüzey 154 → **99** dosya | `grep -rl 'entropy\.memory\b' scripts \| wc -l` → 5 |
| 2 | 4 UI regresyonu kapansın; tam süit **2.347 yeşil** | `pytest -q` |
| 3 | `EntropyAI.spec` hiddenimports 15 eksik modülle tamamlansın; `.exe` derlensin + duman testi | derleme exit 0, `--help` exit 0 |
| 4 | **Taşıma:** `git mv src/entropy/memory src/entropy/brain`; `entropy.memory` → `entropy.brain` metin değişimi (`src`, `tests`, 5 araç betiği, `EntropyAI.spec`, canlı `docs/*`); §6.2/1'deki üç dizgi elle | `grep -rn 'entropy\.memory' src tests scripts EntropyAI.spec` → **0** |
| 5 | `python -c "import entropy.main"`; tam süit; `pyinstaller EntropyAI.spec` + `--help` + 20 sn canlı koşum | test sayısı **değişmemeli** |
| 6 | `docs/ARCHITECTURE.md` §2 paket tablosu + ADR-0006 (taşıma yapıldı) | — |

Geri alma: adım 4–6 tek commit → `git revert <commit>`.

**Başka taşıma gerekiyor mu → hayır.** Hedef şema `core / brain / agents / desk / ui / skills`;
`core`, `agents`, `desk`, `ui`, `skills` **zaten yerinde**. `tools/` (2 dosya, `synthesizer.py`)
`core/` altına alınabilir ama kazancı yok, riski var — **önerilmez**.

---

## 7. Temizlik manifesti (kuru koşum)

Kısaltmalar: **SİL** · **ARŞ** (`docs/_archive/`) · **DIŞ** (depo dışı) · **TAŞI** · **KOR** (dokunma) · **KARAR** (sahibi orkestratör).

| # | Yol | Eylem | Ölçü | Kanıt |
|---|---|---|---:|---|
| M1 | `scripts/{record_,save_,sync_,process_,register_,update_}*.py` (**59 dosya**) | **TAŞI** → `scripts/_oneshot/` + `README` (silme değil) | 1,02 MB | Hiçbir test içe aktarmıyor (`grep -rlE "record_faz\|save_faz\|sync_faz\|process_phase" tests` → **0**). 45'i kasaya yazıyor, 6'sı mutlak `C:\EntropiAI` yolu içeriyor, `sync_faz150_obsidian.py:18` **taşınmış bir rapora** bakıyor → bugün kırık. Kasada karşılıkları zaten var; kod değeri değil, tarih değeri taşıyorlar. `_oneshot/` alt paketi `entropy.memory → brain` taşıma yüzeyini 154 → 99'a düşürür. |
| M2 | `EntropyAI_OneFile.spec` | **ARŞ** → `docs/_archive/build/` | 2,5 KB | §3.2: hiç çağrılmıyor, 32/127 hiddenimports, `entropy.agents`/`entropy.desk` **0**, makineye çakılı `pathex` |
| M3 | `docs/specifications/*` (5) | **damıt → ARŞ** `docs/_archive/specifications/` | 32 KB | §4.3: hepsi 2026-09-03; dördü bugünkü mimariyle çelişiyor; `TASK_SCHEDULER_*` özü `ARCHITECTURE.md`'ye |
| M4 | `src/entropy/core/claude_bg.py` (741 satır) + `tests/test_phase11_claude_bg.py` | **KARAR** | — | §2.2: üründe çağıran yok, spec'te yok; kaynağı `2026-09-10_Faz11F_Spike_Kalici_Terminal.md` "ertelendi" diyor. Seçenek A: spike'ı `docs/_archive/spikes/` notuyla sil (32 test düşer). Seçenek B: kalsın, `ARCHITECTURE.md`'ye "deneysel, bağlı değil" satırı + spec'e girdi. **Sessiz kalması en kötü seçenek.** |
| M5 | `src/entropy/platform/autostart.py` | **KARAR (2. tur)** | 2,7 KB | Faz 11 açık işi #4 kapanmadı: `config.autostart_enabled` okunuyor/yazılıyor, uygulayan yok. Ya `main.py` açılışına bağlanır ya ayarla birlikte kaldırılır. |
| M6 | `skills/media_agency_soldier/`, `skills/slide_deck_architect/` (alt çizgili) | **TAŞI/tekilleştir** | 247 KB | §2.4: üç farklı kopya; `EntropyAI.spec` `datas=('skills','skills')` üçünü de `.exe`'ye koyuyor. Önce `diff` raporu, sonra tek kaynak + testlerin oraya yönlendirilmesi. **Tek adımda silinmez** (5 test dosyası bağımlı). |
| M7 | `scratch/ui/phase{7,8,9,10}/*.png` (55 izlenen) | **TAŞI** → `docs/_archive/ui/` ya da DIŞ | **5,8 MB** | İzlenen ağacın en ağır ikinci kalemi; ölçüm kanıtı olarak değerli ama `scratch/` `.gitignore`'da → yeni ekran görüntüleri zaten izlenmiyor, eskiler tutarsız biçimde izleniyor |
| M8 | `entropy.png` (1,37 MB) | **KARAR** | 1,37 MB | Kökteki tek büyük ikili; `EntropyAI.spec` `datas` yalnızca `entropy.ico` alıyor → `.png` pakete **girmiyor**. Küçültme ya da `docs/`'a taşıma adayı. |
| M9 | `pyproject.toml` sürüm + bağımlılık yorumları | **DÜZELT** | — | `version = "0.8.0"` vs `__init__.__version__ = "0.1.0"` vs etiket v0.9.4; `pillow` yorumu var olmayan `agent_desk/...`'a atıf, PIL'i **hiçbir dosya** içe aktarmıyor |
| M10 | `docs/ARCHITECTURE.md` | **GÜNCELLE** | — | §4.2: `board_fsm`/`dream`/`gray_merge`/`amplification` **0 geçiş**; başlık "v0.8.0 · Faz 11-A" |
| M11 | `GEMINI.md` §1–§2 | **GÜNCELLE** | — | §3.1: `claude` 3 geçiş, üçü de haritada; §1 hâlâ tek sağlayıcı + Supabase/Mem0 anlatıyor |
| M12 | `docs/reports/` arşiv kuralı | **YAZ** | — | §4.4: 31 dosya; kural yazılı değil; koddan atıflı 5 rapor listesi kayıt altına alınmalı |
| M13 | `dist/`, `build/` (1.386 MB) | **SİL (isteğe bağlı)** | 1.386 MB | `.gitignore`'da, `EntropyAI.spec` ile yeniden üretilir. **Kısıt:** çalışan `.exe` `dist/`i kilitler; ayrıca `tests/test_exe.py` bu çıktıya bağlı → silinirse **2 test kırmızıya döner** (Faz 11-A'da yaşandı). Derleme QA'sından hemen sonra silinmemeli. |
| M14 | `.entropy/`, Obsidian kasası, `docs/_archive/customer/` | **KOR** | — | kullanıcı verisi; `core/config.py` `_resolve_state_dir` |

**Bu turda SİLME önerisi yoktur** — Faz 11-A silinecekleri zaten sildi. Kalan iş **taşıma,
tekilleştirme, karar ve belge güncellemesidir.**

---

## 8. Uygulama sırası (repo-curator için; her adım tek commit, geri alınabilir)

Kural: `git stash` / `git checkout --` / `git reset --hard` **yok**; her adımdan sonra hedefli
test; geri alma = `git revert <commit>`.

| # | Adım | Doğrulama | Geri alma |
|---|---|---|---|
| 0 | Başlangıç ölçümü kaydedilir: 2.347 toplandı, 2.343/4, 402,85 s | `pytest --collect-only -q` | — |
| 1 | **M9** sürüm tekilleştirme + ölü bağımlılık yorumları | `python -c "import entropy; print(entropy.__version__)"` | revert |
| 2 | **M1** `scripts/_oneshot/` taşıması (`git mv`, 59 dosya) + `scripts/README.md` | `pytest tests -q -k "perf or routing or metrics"` yeşil; `grep -rl 'entropy\.memory' scripts \| wc -l` → 5 | revert |
| 3 | **M2** OneFile spec arşivi + `GEMINI.md` haritasından satırın çıkarılması | `ls docs/_archive/build/` | revert |
| 4 | **M3** spec damıtma → `ARCHITECTURE.md` + arşiv | koddan atıflı yol kalmadı: `grep -rn "docs/specifications" src tests` → 0 | revert |
| 5 | **M10 + M11 + M12** belge güncellemesi (ARCHITECTURE §2/§5/§6/§10, GEMINI §1–§2, rapor arşiv kuralı) | `grep -c board_fsm docs/ARCHITECTURE.md` > 0 | revert |
| 6 | **M7** ekran görüntüsü arşivi (`git mv`) | `git ls-files scratch \| wc -l` → 0 | revert |
| 7 | **M4/M5 kararları** ayrı kartlara bölünür (sahibi: agy-integration-engineer / qa-build-engineer) | karar ADR'ye yazılır | — |
| 8 | **M6** skills tekilleştirme (önce `diff` raporu, sonra tek kaynak) | `pytest tests/skills -q` yeşil | revert |
| 9 | Kapanış: tam süit + `pyinstaller EntropyAI.spec` + duman testi; önce/sonra tablosu `STATE.md`'ye | süit yeşil, `.exe --help` exit 0 | — |
| 10 | **Ancak bundan sonra** §6.3 `memory → brain` | ayrı onay | ayrı commit |

---

## 9. Karar özeti ve iş listesi

| Karar | Öneri | Sahibi |
|---|---|---|
| `entropy.memory → entropy.brain` | **Ertele** (ön koşullar açık: 4 kırmızı test, 15 modüllük spec sapması, ARCHITECTURE bir faz geride) | orkestratör kararı → memory-rag-engineer |
| `EntropyAI_OneFile.spec` | **Arşivle** (çürük, kimse çağırmıyor, bozuk `.exe` üretir) | repo-curator |
| Tek seferlik 59 betik | **`scripts/_oneshot/`'a taşı** (silme; kırık olanı ayrıca işaretle) | repo-curator |
| `docs/specifications/` (5) | **Damıt → arşivle** | repo-curator |
| `docs/ARCHITECTURE.md` | **Faz 11-C/D/E sözleşmeleriyle güncelle** (board FSM, gate, dream, gray_merge, tasarım belirteçleri) | repo-curator + memory-rag-engineer |
| `GEMINI.md` §1–§2 | **Çift sağlayıcı gerçeğine güncelle** | repo-curator |
| `CLAUDE.md` | **Oluşturulmasın** (ölçülmeden asla) | — |
| 4 kırmızı test | **Tasarım sözleşmesine göre yeniden yaz** (emoji/glif beklentileri) | ui-engineer |
| `tests/` D grubu (82 dosya / 563 test) | **`tests/_reference/`'a taşı**, ana süit dışına | qa-build-engineer |
| `core/claude_bg.py` | **Karar:** sil ya da "deneysel, bağlı değil" olarak belgele + spec'e ekle | agy-integration-engineer |
| `platform/autostart.py` | **Karar:** bağla ya da ayarla birlikte kaldır | qa-build-engineer |
| `EntropyAI.spec` 15 eksik modül | **Ölç ve tamamla** (taşımadan önce) | qa-build-engineer |
| `skills/` üçüzlemesi | **Tekilleştir** (diff → tek kaynak → testleri yönlendir) | qa-build-engineer |
| `scratch/` 55 PNG | **Arşive taşı** | repo-curator |

### Kabul ölçütleri

1. `git ls-files scripts | grep -c '_oneshot'` = 59 **ve** `pytest -q` test sayısı **değişmemiş** (2.347).
2. `grep -rn "entropy\.memory" scripts | wc -l` ≤ 5 (yalnız gerçek araçlar).
3. `grep -c "board_fsm\|gray_merge\|dream" docs/ARCHITECTURE.md` > 0; başlıktaki sürüm etiket ile aynı.
4. `ls EntropyAI_OneFile.spec` → yok; `grep -c OneFile GEMINI.md` → 0.
5. `ls docs/specifications` → yok; `grep -rn "docs/specifications" src tests` → 0.
6. Tam süit **2.347 passed** (4 regresyon kapandıktan sonra); D grubu ayrıldıysa ana süit ≈ **1.784**.
7. `python -m PyInstaller EntropyAI.spec` exit 0 + `.exe --help` exit 0 + 20 sn canlı koşumda `Traceback`/`CRITICAL` = 0.
8. `git status --short -uall` ≤ 12 satır (bugünkü 10 satırdan kötüleşmemiş).

### Riskler

| Risk | Önlem |
|---|---|
| `dist/` silinirse `tests/test_exe.py` iki testi kırmızıya döner (Faz 11-A'da yaşandı) | M13 yalnızca derleme QA'sıyla birlikte; derleme sonrası silinmez |
| Spec dizgi listesi: bir satır atlanınca `.exe` sessizce eksik | taşımadan önce §2.3 ölçümü + derleme sonrası modül varlığı testi |
| `skills/` tekilleştirmesi 5 test dosyasını kırar | önce `diff` raporu, testler tek kaynağa aynı commit'te yönlendirilir |
| Tek seferlik betiklerin taşınması kasa geçmişini bozar sanılabilir | betikler kasaya **yazan** taraf; kasa içeriği zaten yazılmış, taşıma kasaya dokunmaz |
| `scripts/_oneshot` içindeki kırık yollar (6 dosya mutlak `C:\EntropiAI`) | `README`'ye "arşiv, koşulmaz" notu |

### Doğrulanamayanlar (bu turda ölçülemedi)

1. **§2.3'teki 15 modülün `.exe` içine girip girmediği.** Onedir çıktısında uygulama modülleri
   PYZ içinde olduğu için diskten görülemedi (`find dist -name '*board_fsm*'` → boş, ama bu
   kanıt değil). QA reçetesi: derleme sonrası `dist/EntropyAI/EntropyAI.exe` ile
   `python -c "import entropy.agents.board_fsm"` eşdeğeri bir iç kontrol ya da
   PyInstaller `Analysis` grafiğinin (`build/EntropyAI/xref-EntropyAI.html`) taranması.
2. **Faz 11-E sonrası `.exe` derlemesi.** Son yeşil derleme 2026-09-10 QA'sında (`STATE.md` §2.3);
   HEAD `1815f32` ile derleme **yapılmadı** (bu görev salt okunur, derleme kota/CPU harcar).
3. **`skills/` üç kopyanın davranışsal denkliği.** Yalnızca dosya adı/satır sayısı ve `diff -q`
   ile "farklı" oldukları ölçüldü; hangisinin doğru olduğu ölçülmedi.
4. **`docs/reports/` içindeki marka taraması** bu turda tekrarlanmadı (Faz 11 QA'sında iki
   dosyada gerçek atıf bulunmuştu; karar hâlâ orkestratörde).
5. **`entropy.png`'nin gerçekten kullanılmadığı** — `.spec` `datas`'ta yok, ama çalışma anında
   `APP_ROOT` üzerinden okunuyor olabilir; grep yapılmadı.

---

## 10. Kaynaklar

**Depo içi birincil kanıt (dosya:satır):**
1. `src/entropy/skills/__init__.py:16-29` — PEP 562 `_LAZY` tembel yükleme (AST körlüğü).
2. `EntropyAI.spec:24-36, 165-166` — `datas`, `AGENTS.md` paketlenmeme gerekçesi, media-agency hiddenimports.
3. `EntropyAI_OneFile.spec:8-10` — makineye çakılı `pathex`, `('src/entropy','entropy')` datas.
4. `src/entropy/ui/widgets/memory_inspector_dialog.py:502-503` — modül adının **dizgi** olarak geçmesi.
5. `src/entropy/memory/supabase/cognitive_memory.py:36` — `logging.getLogger("entropy.memory.cognitive")`.
6. `src/entropy/core/config.py:329, 488, 531-532` — `autostart_enabled` okunur/yazılır, uygulanmaz.
7. `src/entropy/desk/scene.py:32-47` — `entropy.desk.engine.*` alt modül içe aktarmaları.
8. `scripts/sync_faz150_obsidian.py:18` — arşive taşınmış rapora bakan kırık mutlak yol.
9. `pyproject.toml:7, 17-19, 25-27` — sürüm 0.8.0, `agent_desk/...` atıflı ölü bağımlılık yorumları.
10. `src/entropy/__init__.py:3` — `__version__ = "0.1.0"`.
11. `docs/adr/ADR-0004-faz11-paket-tasima-yok.md` — taşımanın ertelenme gerekçesi ve ön koşulları.
12. `docs/ARCHITECTURE.md:8, 251-274` — "v0.8.0 · Faz 11-A" başlığı ve "Faz 11 hedef mimarisi".
13. `docs/STATE.md` §3 — bugün sözleşmelerin fiilî tek kaynağı.
14. `AGENTS.md` §1-§4 — ajan tanım yerleşimi ve 7 değişmez (gerçekle uyumlu).
15. `GEMINI.md:1-40, 55-119` — eski §1–§2, güncel §3 dizin haritası.
16. `tests/conftest.py` — 213 satır, 9 autouse fixture ile kasa/`~/.entropy` yalıtımı.

**Koşulan komutlar (tamamı salt okuma, model çağrısı yok):**
`git ls-files`, `git status --short -uall --porcelain`, `git log --oneline`, `du -sm/-sk`,
`find`, `wc -l`, `diff -q`, `grep -rn/-rl/-c/-rhoE`,
`QT_QPA_PLATFORM=offscreen python -m pytest --collect-only -q -p no:cacheprovider`,
`… pytest -q -p no:cacheprovider --durations=15` (tam süit, 402,85 s),
dört hatalı testin tek tek yalıtılmış koşumu, geçici AST içe aktarma tarayıcısı
(oturum geçici dizininde; depoya yazılmadı).

**Not:** Bu turda dış web kaynağı kullanılmadı — sorular tamamen depo içi ölçümle yanıtlanabilirdi.
