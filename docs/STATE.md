# STATE.md — Güncel durum (alt ajanların çalışma belleği)

> **İşe başlamadan önce bu dosyayı ve `docs/reports/` altındaki en son ilerleme raporunu oku.**
> Bu dosya alt ajanların oturumlar arası hafızasıdır: sözleşme imzaları, açık işler,
> bilinen kısıtlar ve son yeşil ölçümler burada durur. Her faz dilimi sonunda güncellenir.
> Mimari: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Kararlar: [`adr/`](adr/) · Plan: [`ROADMAP.md`](ROADMAP.md)

| | |
|---|---|
| Sürüm | **v0.10.0** (Faz 12 kapanış) |
| Dal | `ai/v0.1.7` (ana dal: `master`) |
| Son güncelleme | 2026-09-10, **Faz 12 KAPANIŞ QA** (§2.6): tam süit **2.456 test / 1 bayat test düzeltildi**, build exit 0 (146 s, `dist/EntropyAI`, `--version` 0.10.0), ui gate exit 0, gerçek ekran LG %200'de Zen 4/4 köşe + 3 pencere denetimi görünür, açık tema regresyonu (gömülü gövdeler koyu kalıyordu) düzeltildi, uçtan uca otonom pano döngüsü canlı doğrulandı; kota 129.051 token (tavan 120k aşıldı), wiki derlemesi / oturum devri / skill approve **koşulmadı** (§2.6) |
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

## 2.6 Faz 12 KAPANIŞ QA (2026-09-10, qa-build-engineer)

**Tam süit:** `QT_QPA_PLATFORM=offscreen python -m pytest tests -q -p no:cacheprovider`
→ 1. koşum **2.456 test; 2.455 passed, 1 failed, 406,55 s**; tek hata
`tests/test_wiki_layer_and_lint.py::test_wiki_and_lint_are_local_commands`
**bayat testti** (12-B'de `/wiki` komut paletinden kaldırılmış, alias olarak
yaşıyor) — test sözleşmeye göre düzeltildi. Arayüz palet düzeltmesinden sonra
2. koşum: **2.456 passed / 0 failed / 472,55 s**.
**Yalıtım kanıtı (önce = sonra, değişmedi):** `tasks_ledger.db` 73.728 B /
1789012264, `skills_state.json` 112 B / 1788993407, `cognitive_memory.db`
7.593.984 B / 1789015233.

**Spec:** `tests/contracts/test_spec_sync.py` beş eksik modül bildiriyordu —
`entropy.ui.design.embedded`, `…design.prefs`, `…widgets.office_cards_panel`,
`…widgets.settings_dialog`, `…widgets.skill_candidates_panel` — `EntropyAI.spec`
hiddenimports'a eklendi, **9 passed**.

**Build:** `python -m PyInstaller EntropyAI.spec --noconfirm` → **exit 0, 146 s**,
`dist/EntropyAI` **1.207 MB**, `EntropyAI.exe` 55.948.865 B; palet düzeltmesinden
sonra 2. build **exit 0, 256 s**, `EntropyAI.exe` **55.951.182 B** (dağıtılan sürüm bu). Smoke: `--help`
**exit 0** (stderr 0 bayt), `--version` → **`Entropy AI 0.10.0`** exit 0,
20 sn canlı koşum (erken çıkış yok), çıktıda `traceback`/`CRITICAL` **0**,
yeni CrashDump **yok** (en yenisi 2026-09-08).
`scripts/ui_audit.py --gate --final` **exit 0**: `distinct_hex 0`,
`embedded_hex_count 0`, `embedded_contrast_failure_count 0`,
`contrast_failure_count 0`, `themes_reachable 4`, `settings_persisted_splitters
12/12`, `interactive_count_zen_1366 50`, `header_leaf_widgets 6`.

**Marka:** iki ad da (ürün + üretici) `git grep -ril` ile **0 dosya**.
Mimari kural testleri (`tests/contracts/test_architecture_rules.py`) yeşil.

### Kota notu — tavan aşımının nedeni: ölçülemeyen sohbet tüketimi

`tasks_ledger.db` bugüne kadar **yalnızca arka plan GÖREVLERİNİ** tutuyordu
(`record_task_start` / `record_task_success`). Kullanıcının sohbet turları
(`_execute_prompt_worker` / `_apply_chat_usage`) yalnızca oturum içi sayaçlara
ve rozete yazılıyordu; uygulama kapanınca o tüketim kayboluyordu. Sonuç:
`token_totals()` "harcanan" diye gösterilen sayı gerçek tüketimin ALT sınırıydı
ve tavan (`agy` günlük kotası) defter temiz görünürken aşılıyordu.

Kapanış düzeltmesi: `TaskLedger.record_chat_turn(usage, provider, model)` —
her sohbet turu `task_id="chat-<zaman>"`, `status=SUCCESS`, `provider`
(`agy|claude`) ve `model` ile deftere yazılır; kaydedilen değer TURUN farkıdır
(agy'de kümülatif `usage` alanından çıkarılan delta), oturumun kümülatifi
değil. Sıfır tokenli tur yazılmaz. Ayrıştırma için `chat_token_totals()`
eklendi (`task_id LIKE 'chat-%'`), böylece "görev maliyeti" ile "sohbet
maliyeti" tek defterde ama ayrı okunabilir.
Yerler: `src/entropy/core/task_ledger.py` (`record_chat_turn`,
`chat_token_totals`), `src/entropy/core/claude_bridge.py` (`_apply_chat_usage`),
`src/entropy/core/agy_bridge.py` (`_execute_prompt_worker` tur muhasebesi).

### Gerçek ekran (LG ULTRAGEAR, dpr 2,0 = %200; 1920×1080, avail 1920×1032)

Betikler: `scratch/ui/phase12/live_shots.py`, `live_shots2.py`, `live_shots3.py`;
ölçümler `live_metrics.json`, `live_metrics2.json`; görüntüler `live_*.png`.

| Ölçüm | Sonuç |
|---|---|
| Zen dört köşe ekranda | **4/4 true** (`corners_on_screen`) |
| Zen üç pencere denetimi | `btn_minimize` / `btn_maximize` / `btn_close` **görünür ve pencere içinde** (30×30, x=632/666/700) |
| Zen `minimumSizeHint` | **605×481** (ekran 1920×1032'ye sığar), taşma **0** |
| Chat 1280×800 | taşma **0** |
| Desk `minimumSizeHint` | **678×407**, `fits_avail` **true**, taşma **0** |
| Bölücü sürükleme (gerçek fare olayı, `shellSplitter`) | 573/375 → **660/288**; kapat/aç sonrası **660/288** → **konum korunuyor** |
| Ayarlar diyaloğundan tema | `dark → light` uygulandı (`SettingsDialog.apply()`), `ui_theme()` **light** |

**Bulunan ve düzeltilen arayüz regresyonu (R-12F-1):** açık temaya geçince
**rapor okuyucu ve tüm gömülü HTML gövdeleri KOYU kalıyordu** (kanıt:
`scratch/ui/phase12/live_reader_light.png` önce/sonra). İki kök neden:
(a) 17 arayüz modülü paleti **içe aktarma anında** donduruyordu
(`_P = palette()`); (b) `ui/themes/cyber_theme.py` `CYBER_THEME` ve
`READING_TOKENS` tablolarını doğrudan koyu `TOKENS` üzerinden kuruyordu.
Düzeltme: `ui/design/embedded.py` içine **`LivePalette` / `live_palette()`**
(her okumada güncel temayı çözen `Mapping`), 17 modülde `_P = _live_palette()`;
`cyber_theme.py` içinde **`_LiveTable`** + `_build_cyber` / `_build_reading`
(`CYBER_THEME`, `READING_TOKENS` artık canlı). Ölçüm:
`READING_TOKENS["surface_base"]` light `#F5F7FA` / dark `#0B0F14`.
Eski `STYLESHEET` bilinçli olarak donuk bırakıldı (ürün yolunda
`apply_design_system()` onun yerine geçiyor) — **açık iş**.
Graf tuvali açık temada `grab()` ile **boş** döndü (QWebEngineView ayrı
compositor'da çizer) — bu yolla **ölçülemedi**; HTML tarafı `css_variables`
üzerinden temaya bağlı (`ui/widgets/knowledge_graph.py:3059`).

### Uçtan uca canlı pano döngüsü (gerçek koşum)

(a) Sohbette Entropy'ye "arastirmaci ajanına şu görevi ver: Python
`dataclasses` ile `attrs` farkını 6 maddede özetle, kaynak ver" →
ham yanıtta **`[PANO board_create]` bloğu var** (`scratch/_p12f_chat_raw.txt`),
gösterilen metinde blok **yok** + `Görev oluşturuldu: … → arastirmaci` makbuz
satırı (`scratch/_p12f_chat_shown.txt`). Kart
`20260910-100914-python-dataclasses-vs-at` **assigned**; tetikleyici koştu →
`taken → running → review`; `events.jsonl` seq 17-20
(`task.assigned / task.claimed / run.started / run.finished ok:true`);
**`projection.json` yazıldı** ve `TASKBOARD.md` başlığındaki
**Projeksiyon karması DOLU** (`ee40492057ef9fb0` → `480ef90f3287c9b5`).
**`report_path` artık kartta dolu** (11-C açık işi kapandı).

(b) Aynı ajana 3 kısa kart daha (A/B/C) koşuldu — hepsi `review`.
Ledger: **28.678 + 31.049 + 33.251 = 92.978 token** (`provider: claude`),
`session.json` → `cards_in_session 3`, `tokens_in_session 92.978`.
**Devir (rotation) TETİKLENMEDİ ve doğrulanamadı:** eşikler
`agent_session_max_cards = 3` / `agent_session_max_tokens = 60.000`; 3. kart
başlarken sayaçlar 2 kart / 59.727 token idi (ikisi de eşiğin altında), yani
devir **4. kartta** tetiklenecekti. 4. kart **kota tavanı** nedeniyle
KOŞULMADI → `handoff.md` **yok**, `--resume` argv kanıtı bu turda **alınmadı**
(11-C QA'sında alınmıştı). **Açık iş.**

(c) `board_checkpoint` **gerçekten dosyaya yazıldı**: B kartının `checkpoint`
alanı → `…/Desk/Offices/entropy/workspace/checkpoints/20260910-102335-kisa-not-b.md`
(350 B). **Uyarı:** Entropy kartının kontrol noktası **Desk veri kökünün
altına** düşüyor (ayrı kök kuralı) — açık iş.
**Özet blok sızıntısı:** bu QA'da koşan **4 kartın 4'ünde de 0**; sızıntılı
3 kart (`…064253`, `…064722`, `…064948`) 12-B temizleyicisinden **önceki**
11-C QA kartlarıdır (geçmiş veri).

(d) **Beyin kısayolu ÇALIŞMIYOR (yeni bulgu).** Dört kartın dördünde de
`amplification.brain_lookup(...)` → `has_answer=True` (13.104 karakterlik
yanıt), ama `amplification.is_research_card(card)` → **False**, bu yüzden
`tasks._brain_shortcut` erken dönüyor ve CLI **her seferinde** çağrılıyor.
Kök neden: `board_create` kartın `kind` alanını doldurmuyor
(`agents/board_autonomy.py`), sezgi ise "…yaz", "…özetle" gibi hedeflerde
`_WRITE_HINTS` yüzünden reddediyor (`agents/amplification.py:52-58`,
`:77-85`). Öneri: Entropy kart üretirken `kind` yazsın (araç sözleşmesine
zorunlu alan). **Açık iş.**

**Sağlayıcı notu:** (a) kartı `provider: agy` ile koştu — `arastirmaci` ajan
şartnamesinin kendisi `provider: agy, model: gemini-3.8-flash-high` diyor
(`AgentRegistry.get('arastirmaci')`), `config.provider` `claude` olsa da
şartname kazanıyor (`tasks.py:1375-1378`). (b)'deki üç kart `provider: claude`
ile açıkça oluşturulup saf kipte koşturuldu.

### Hafıza turları

Yedek: `~/.entropy/backups/cognitive_memory.qa12f.*.db`.

- `/skill synth media-agency-soldier`: **kotasız kol** koşuldu (`turns 0`),
  3 dosya üretildi, `validate_candidate` → **`draft`**, bulgu
  "eksik/boş bölüm: Girdiler, Çıktılar". Bu **tasarım gereği**dir: iskelet
  `"- (… doldurulacak)"` yazıyor (`memory/skill_synthesis.py:299-300`) ve
  doğrulayıcı "doldurulacak" içeren bölümü eksik sayıyor (`:556-558`).
  Yani **kotasız kol asla `validated` olamaz**; tek turluk zenginleştirme
  **kota tavanı** nedeniyle koşulmadı → `/skill approve` ve kasada
  `Skills/<ad>/SKILL.md` adımı **doğrulanamadı**. Açık iş.
- `/memory merge`: gri kuyruk turdan önce **0**, sonra **2 pending**
  (`~/.entropy/memory/gray_queue.jsonl`) — bugünkü kart raporları kapıdan
  gri banda düştü. Birleştirme turu köprü (model) gerektirdiği için
  **koşulmadı** (kota). Açık iş.
- `/distill wiki compile financial-auditor --turns 25`: **KOŞULMADI** — kota
  tavanı aşıldığı için tek başına en pahalı kalem. `WIKI.state.json`, sayfa
  sayısı ve lint ölçümü bu QA'da **yok**. Açık iş.

### K tablosu (`scripts/brain_metrics.py --context --json`, önce → sonra)

| Ölçüt | Önce | Sonra |
|---|---:|---:|
| düğüm | 729 | **734** |
| K1 yineleme | %5,49 | **%5,59** |
| K2 Hit@1 / Hit@5 | 9/10 · 10/10 | **9/10 · 10/10** |
| K3 gürültü | %0,0 | **%0,0** |
| K4 bağlam bütçe payı | %70,19 | **%70,19** |
| K5 damıtılmış pay | %37,21 | **%37,21** |
| K6 wiki payı | %29,00 | **%29,00** |
| K7 kategori | sem 651 / proc 59 / epi 19 | **sem 652 / proc 59 / epi 23** |
| K9 gri kuyruk (pending) | 0 | **2** |
| K10 fikstür | 0 | **0** |
| K11 kapı gecikmesi (medyan) | 85,5 ms | **90,8 ms** |
| K12 kaynaksız L2 | 0 | **0** |
| `brain_has_answer` (5 sorgu) | 3/5 | **3/5** |

K4/K5/K6 değişmedi çünkü wiki derlemesi koşulmadı (K6'yı büyütecek tek kalem oydu).

### Kota

Bu QA'da ledger'a düşen gerçek model tüketimi: **129.051 token**
(36.073 agy + 92.978 claude), tavan **120.000** → **%7,5 aşıldı**; aşımı
gördüğüm anda canlı turlar durduruldu. Sohbet turunun (a) tüketimi ledger'a
**yazılmıyor** (sohbet yolu ledger'sız) — ölçülemedi.

---

## 2.4 Faz 11 KAPANIŞ QA (2026-09-10) — kapanış sayıları

**Tam süit:** `QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider`
→ **2.352 test; 2.348 passed, 4 failed, 406 s**; dört hata düzeltildikten sonra
ikinci koşum **2.353 test; 2.352 passed, 1 failed, 427 s**. Kalan tek hata
`tests/desk/test_desk_phase7.py::test_panel_minimum_widths_sum_below_900`:
**bu QA'nın değişikliklerinden bağımsız** — ayrı bir `git worktree` ile HEAD
(8b60c5e) üzerinde de aynı şekilde kırmızı. Kök nedeni bulundu ve §5.9'a
yazıldı (Desk sayfa asgarileri sekme asgarisini eziyor). Faz 11-C/D QA'sında zaman aşımına
giren `tests/desk/test_office_hardening.py` ve `test_office_harness.py`
**bu koşumda yeşil** (tek başına 57 test / 25,5 sn; yük altında da geçti).
**Yalıtım kanıtı (önce = sonra):** `tasks_ledger.db` 73.728 B / 1789012264,
`skills_state.json` 112 B / 1788993407, `cognitive_memory.db` 7.593.984 B /
1789015233 — üçü de değişmedi.

**Build:** `python -m PyInstaller EntropyAI.spec --noconfirm` → **exit 0, 241 s**,
`C:\EntropiAI\dist\EntropyAI\` **1.206 MB**, `EntropyAI.exe` 55.833.355 B.
Smoke: `--help` **exit 0** (stderr 0 bayt); `--mode zen` ile 25 sn canlı koşum,
erken çıkış yok; `.entropy/logs/entropy.log` yeni satırlarında
`Traceback`/`CRITICAL` **0**; yeni CrashDump **yok**; exe veritabanına yazmadı.
QtAwesome fontları pakette (`_internal/qtawesome/fonts/`, 6 aile) ve
**ikonlar exe'de gerçekten çiziliyor** (gerçek ekran görüntüsü
`scratch/ui/phase11e/live_exe_zen.png`: dikey gezinmenin 7 ikonu, palet
büyüteci, model kapsülü).

**Kapanışta düzeltilenler (dört süit hatası + iki sessiz regresyon):**

| # | Bulgu | Ürün mü test mi | Düzeltme |
|---|---|---|---|
| 1 | Slash paletinde seçili `[]` ve seçilmemiş `[ ]` ayırt edilemiyordu | **ÜRÜN** (11-E emoji temizliği `[✓]`'i sildi) | `CHECK_ON="[x]"` / `CHECK_OFF="[ ]"` + `tone` rengi — `src/entropy/ui/widgets/slash_command_popup.py:12-16,26,57` |
| 2 | Terminal düğmesi iki kod yolunda iki farklı etiket üretiyordu (`_on_turn_started` eski emojili metni yazıyordu) | **ÜRÜN** | tek kaynak `_sync_terminal_button()` — `src/entropy/ui/modes/chat_mode.py:1131-1145,1494` |
| 3 | `test_reports_viewer_grouping_filter_and_search` `"📅"` arıyordu | **TEST** (11-E emojiyi kaldırdı, gruplama çalışıyor) | grup **varlığı** ve etiketi ölçülüyor — `tests/test_graph_radial_layout_and_reader.py:348-355` |
| 4 | `test_multi_hub_hierarchy_and_scope_filtering` `"🌐 Tüm Hafıza…"` bekliyordu | **TEST** | `itemData` sözleşme, metin emojisiz — `tests/test_hierarchical_knowledge_graph.py:233` |
| 5 | `reports_viewer` sıralama anahtarı `k.startswith("")` (her zaman True) | ölü kod (11-E artığı) | `src/entropy/ui/widgets/reports_viewer.py:523` |
| 6 | Yük altında zaman aşımı: sabit `Event.wait(10)` / `_wait_until(..., 20)` | **TEST** (ürün hatası değil) | `tests/timing.budget()` — yüke göre ölçeklenen bütçe; boştaki ölçek 1,0 (davranış değişmez) |

**K12 = 0 (gerçek DB, kanıt).** Kalan 2 kaynaksız L2 düğümünün ikisi de
**kimlik düğümüydü** (`is_identity=1`): `semantic-f323b831952293b5` ("I am
Entropy AI…", 103 çağrı) ve `semantic-69123da031675b0b` ("Entropy AI Kimlik ve
Otonomi İlkesi…"). Uydurma kaynak yazılmadı; doğru kaynak `identity:core`
damgalandı.
`python scripts/memory_migrate_v2.py --tag-legacy` (kuru koşum →
`identity_candidates: 2`) → `--apply` (yedek
`~/.entropy/backups/cognitive_memory.pre-v2.20260910074033.db`) →
`identity_tagged_now: 2`, ikinci koşumda `identity_candidates: 0` (idempotent).
`python scripts/brain_metrics.py` →
**K12 kaynaksız L2: 0** (eski etiketli 256 · kimlik 3, etiketsiz kimlik **0**);
karar `{'K1': 'PASS', 'K7': 'PASS', 'K10': 'PASS', 'K12': 'PASS'}`.
Düğüm sayısı 729 → 729 (yazma yok, yalnızca sütun güncellemesi).

**Gerçek ekran ölçümleri** (LG ULTRAGEAR, `devicePixelRatio 2.0`;
`scratch/ui/phase11e/live_metrics.json`, `live_zen_widths.json`, `live_dpi.json`):

| Ölçüm | Hedef | Sonuç |
|---|---|---|
| Zen 1920×1080 üst çubuk öğesi | ≤ 4 | **4** (`brandCluster`, `modelCapsule`, `statusCluster`, `paletteButton`) |
| Zen dikey gezinme | 7/7 | **7/7** (Raporlar & Notlar → Bildirimler) |
| Zen taşan panel | 0 | **0** (kaydırma alanı içeriği hariç) |
| Chat 1280×800 krom | — | başlık 49 + girdi 38 = **87 px = %10,9** |
| Odak halkası (Tab) | her durakta ad | **6/6 durak**, hepsinde `accessibleName` |
| Sürükleme (üst çubuk) | çalışıyor | **evet**: `FramelessWindowHelper.handle is header_frame`, sol tık **tüketildi**, `_system_drag=True` (`startSystemMove` yerel/bloklayıcı olduğu için sentetik olayla piksel ölçülemez) |
| Desk `minimumSize` | ≤ 960×540 | **860×540** (bildirilen) |
| Desk 1600×900 taşma | 0 | **0** |

## 2.5 Faz 12-E — depo bakımı (2026-09-10, repo-curator)

Kapsam: `scripts/`, `docs/`, `tests/` (yalnız taşıma), `skills/`, eski spec'ler,
`GEMINI.md`, `AGENTS.md`, `platform/autostart.py`, `.gitignore`.
**Silme yok** (tek istisna: ölü `autostart.py` modülü, ADR-0006 ile); her adım `git mv`
ya da arşiv taşıması → `git revert` ile geri alınabilir.

| Ölçüm | Önce | Sonra | Kanıt |
|---|---:|---:|---|
| `scripts/` kökünde `.py` | 80 | **21** | `ls scripts/*.py \| wc -l` |
| `scripts/_oneshot/` | — | **59** | `ls scripts/_oneshot/*.py \| wc -l` |
| `tests/` kökünde `test_*.py` | 130+ | **48** | 82 dosya `tests/_reference/`'a taşındı |
| Toplanan test | 2.347 (12-B ölçümü) | **2.386** | `pytest --collect-only -q` (fark paralel ajanların yeni testleri; taşımadan gelen fark **0**) |
| `docs/specifications/` | 5 spec | **0** (mezar taşı `README.md`) | `ls docs/specifications` |
| Kökteki `.spec` | 2 | **1** (`EntropyAI.spec`) | `ls *.spec` |
| `skills/media-agency-soldier/` kökünde ölü proxy | 6 dosya / 1.107 satır | **0** | `docs/_archive/skills/README.md` |
| İzlenen dosya | 765 | **779** | `git ls-files \| wc -l` |
| Depo (`.git` dahil) | 1.459 MB | **1.469 MB** | `du -sm .` — fark `dist/`+`build/` yeniden derlemesi; izlenen ağaç değişmedi |

**Koşulan hedefli testler (hepsi yeşil):**

| Süit | Sonuç |
|---|---|
| `tests/_reference` | **563 passed / 15,2 s** |
| `tests/skills` | **111 passed / 20,2 s** |
| `tests/test_exe.py` + `tests/test_scheduler.py` | **6 passed** (autostart testleri kaldırıldıktan sonra; önce 9) |
| `tests/contracts` (mimari kuralları + marka taraması dahil) | **470 passed / 92,8 s** |
| toplam bu dilimde | **693 + 470 = 1.163 passed, 0 failed** |

**Yapılanlar:**

1. **59 tek seferlik betik** (`record_/save_/sync_/process_/register_/update_*`) →
   `scripts/_oneshot/` (`git mv`, geçmiş korundu) + `_oneshot/README.md` ("koşulmaz").
   Kanıt: hiçbiri testten/üründen çağrılmıyor; kalan 21 betiğin **19'u** teste ya da
   ürün koduna bağlı (`scripts/README.md` tablosu).
2. **`EntropyAI_OneFile.spec`** (çürük) + **`docs/specifications/` 5 spec** →
   `docs/_archive/prototype/`; `docs/specifications/README.md` mezar taşı bırakıldı.
3. **`docs/ARCHITECTURE.md`** 274 → **456 satır**: §5.1 Beyin v2 (kapı/kategoriler/rüya/
   gri tur/wiki hattı/amplifikasyon/ölçüm paketi), §6.1.1 Entropy Board (FSM/olay günlüğü/
   dispatcher/oturum deposu/araçlar), §8.1 tasarım sistemi (belirteçler/QSS/ikonlar/5 kapı),
   §9 test düzeni + §9.1 `docs/` arşiv kuralı, §10 Faz 12 hedefleri. Başlık v0.9.4.
   `GEMINI.md` §1–2 çift sağlayıcı gerçeğine yeniden yazıldı (`claude` geçişi 3 → 11) ve
   §3 haritası eşitlendi; `AGENTS.md` §4'e pano sinyalleri, §5 pano araçları eklendi.
   **`CLAUDE.md` OLUŞTURULMADI** (ADR-0002).
4. **`tests/_reference/`**: ürün kodunu sınamayan 82 dosya / 563 test ayrıldı.
   Tek kod değişikliği: 49 dosyada `Path(__file__).parent.parent` → `parents[2]`.
   `pyproject.toml`/`conftest.py` **dokunulmadı**, toplama sayısı değişmedi.
5. **`skills/` üçüzlemesi ikizlemeye indi:** ölçüm üç kopyanın hangisinin gerçek olduğunu
   gösterdi — `skills/media-agency-soldier/scripts/` (4.928 satır) **tek gerçek kaynak**
   (`skills/media_agency_soldier_engine.py:33` ve `SKILL.md:43-53` oraya bakar);
   `skills/media_agency_soldier/` (alt çizgili) testlerin proxy paketi olarak kalır;
   tireli dizinin **kökündeki** 6 dosya ölüydü (dizin adı tireli → paket olarak içe
   aktarılamaz; çıplak import 0; `url_analyzer.py` alt çizgili kopyayla `diff` → SAME)
   → `docs/_archive/skills/media-agency-soldier-root-proxies/`.
   `EntropyAI.spec` `datas` **`('skills','skills')` olarak kaldı** — gerekçe spec'teki
   yeni yorumda: yetenekler çalışma anında yol çözümüyle bulunur, açık dosya listesi
   Faz 10-C'nin sessiz düşmesini geri getirir. hiddenimports'a dokunulmadı.
6. **`platform/autostart.py` kaldırıldı** (ADR-0006): ayar vardı, davranış yoktu
   (`config.autostart_enabled` okunup yazılıyor, uygulayan kod 0). Beraberinde
   `config.py`'deki 4 satır, iki test ve spec'teki tek hiddenimport satırı.
   `core/claude_bg.py` **"deneysel, bağlı değil"** etiketiyle duruyor (ADR-0007).
7. **`.gitignore`:** depo köküne düşen kullanıcı denetim çıktıları (`*_audit.md/json`,
   `*_financial_audit.md`, `*_metrics.json`) yok sayılıyor — **silinmiyor, taşınmıyor**.
   Untracked satır 60+ → **4** (dördü de paralel ajanların yeni dosyaları).

**Açık kalanlar (bu dilimde ölçülmedi):** tam süit ve `.exe` derlemesi (paralel ajanlar
aynı anda `src/` düzenliyordu — kapanış QA'sı 12-F'ye ait); `EntropyAI.spec`'in 15 eksik
modülü (12-A'nın işi); `scratch/` 55 izlenen PNG'nin arşive taşınması (M7, yapılmadı);
`entropy.png` (1,37 MB) ve `pyproject.toml` sürüm tekilleştirmesi (M8/M9, paralel ajanda).

---

## 2.3 QA 11-C/D — uçtan uca pano döngüsü + hafıza turları (2026-09-10)

**Tam süit:** `QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider`
→ **2.320 test; 2.314 passed, 6 failed, 427 s**. Altı hatanın **hepsi** eşzamanlı
süren Faz 11-E arayüz yeniden tasarımından (düğme adı/sekme sırası/rozet metni):
`tests/desk/test_desk_window.py::test_zen_and_chat_have_agent_desk_button`,
`tests/skills/test_skills.py::test_zen_mode_skills_tab_and_pdf`,
`tests/test_agy_bridge.py::test_chat_mode_terminal_button_no_attribute_error`,
`tests/ui/test_ui_parity_tasks_core.py::test_chat_mode_reacts_to_same_bus_signals_as_zen`,
`tests/ui/test_ui_phase8_windows_and_reports.py::test_chat_zen_button_exists_and_is_laid_out`,
`tests/ui/test_ui_phase9_stability.py::test_state_badge_never_shows_bare_emoji`.
Çekirdek/hafıza/pano tarafında hata yok. **Yalıtım kanıtı (önce = sonra):**
`tasks_ledger.db` 73.728 B / 1789012264, `skills_state.json` 112 B / 1788993407,
`cognitive_memory.db` 7.569.408 B / 1789012552 — üçü de değişmedi.

**Build:** `python -m PyInstaller EntropyAI.spec --noconfirm` → **exit 0, 191 s**,
`dist/EntropyAI` **1.207 MB**, `EntropyAI.exe` 55.830.354 B. Smoke: `--help`
**exit 0** (stderr 0 bayt); 20 sn canlı koşum, erken çıkış yok;
`traceback`/`CRITICAL` **0**; yeni CrashDump **yok**.

### Uçtan uca pano döngüsü (gerçek Claude, saf kip, GUI'siz)

`bootstrap.start_board_dispatch(app)` + `TaskBoard` ile üç kart koşuldu.
Zincirin tamamı ölçüldü: `assigned → taken` (claim `Entropy/Board/claims/<id>.lock`)
`→ running` (`events.jsonl` seq 1-4, `TASKBOARD.md` projeksiyonu) `→ review`
(`[PANO board_finish]`, kanıt zorunlu) + `task_report_ready` yükü +
`Entropy/Board/agents/arastirmaci/session.json`. Argv kanıtı: `--session-id
<uuid> … --effort low` (birinci koşu), `--resume <uuid>` (ikinci koşu),
`--setting-sources "" --strict-mcp-config --system-prompt-file` (saf kip).
Ledger: 23.886 + 38.818 + 66.542 = **129.246 token** (90k tavan **aşıldı**;
bu yüzden 2. adımın köprü gerektiren turları KOŞULMADI — aşağı bak).

**QA'da bulunup düzeltilen üç regresyon:**

| # | Bulgu | Kök neden | Düzeltme |
|---|---|---|---|
| R1 | Bir ajanın **ikinci kartı her zaman `failed`** (canlı kanıt: kart `20260910-064500-kisa-teknik-not-2`, 1 sn'de öldü, çıktı boş) | `AgentSessionStore.run_kwargs` imza düşünce **aynı** `uuid5` kimliğini yeniden `--session-id` ile veriyordu; CLI reprodüksiyonu: `Error: Session ID … is already in use.` | imza düştüyse **taze uuid4** üretilir — `src/entropy/core/identity.py:719-736`; test `tests/contracts/test_phase11_board.py::test_new_session_id_is_minted_when_signature_drops` |
| R2 | `--resume` **hiç kullanılmıyordu** (kalıcı ajan oturumu fiilen yoktu) | imza kaynağı `build_prompt(card)` idi; kart istemi her kartta değişince imza her koşuda düşüyordu | imza artık ajanın **kimlik istemine** bağlı — `src/entropy/agents/tasks.py:1447-1457`; 3. kart argv'sinde `--resume aa2ce1f2-…` doğrulandı |
| R3 | **Her** araştırma kartı "DÜŞÜK YENİLİK" damgası yiyor, rapor hafızaya HİÇ girmiyordu (ölçüm: `0/12 yeni`, 12 adayın 12'si `reject`) | `apply_report_lock` kapıya `provenance` geçmiyordu → `MemoryGate`: "L2 anlamsal yazımda kaynak (provenance) yok"; yan etki: aynı konudaki **zamanlanmış görev haksız yere kapatılıyordu** | kaynak karttan türetiliyor (`report_path` → ilk `output_paths` → `card:<id>`) — `src/entropy/agents/amplification.py:409-423`; aynı raporla kuru ölçüm **10 add / 2 gray (%83 yenilik)**; test `…::test_amplification_lock_passes_provenance_to_gate` |

**Öz-amplifikasyon kilidi (11.6) — canlı sonuç:** (b) yenilik kotası çalıştı
(kart notuna `[YENİLİK] …`, `bus.task_notification` yayıldı). (a) **açık tespiti
hiç tetiklenmedi**: aynı konudaki 3. kart da CLI'ya gitti, çünkü R3 yüzünden
hafızaya hiçbir şey yazılmıyordu (kısır döngü). R3 düzeltildikten sonra
kısayolun tetiklenip tetiklenmediği **ölçülmedi** (kota tavanı).

### Hafıza turları (kotasız kol)

Yedek: `~/.entropy/backups/cognitive_memory.qa11cd.20260910065640.db`.

- `dream.dream_and_consolidate(memory, send_prompt=None)` → **0 hata**, 3,46 s;
  20 yineleme kümesi / **23 birleştirme**, 0 unutma, 20 wiki adayı, 40 graf
  topluluğu; düğüm 714 → **706 aktif**; `Entropy/Memory/dream_log.md` yazıldı.
- `gray_merge`: kuyruk **boş** (`pending 0`) → birleştirme turu için aday yok
  (K9 = 0).
- `wiki.compile_skill("media-agency-soldier", bridge=None, budget_turns=8)` →
  **turns 0** (kotasız kol), **18 sayfa** yazıldı, `remaining 20` rapor köprü
  bekliyor, lint çalıştı.

| Ölçüt | Önce | Sonra |
|---|---:|---:|
| düğüm | 714 | **729** |
| K1 yineleme | %4,76 | **%4,76** |
| K2 Hit@1 / Hit@5 | 9/10 · 10/10 | **9/10 · 10/10** |
| K3 gürültü | %0,0 | **%0,0** |
| K7 kategori | `sem 639 / proc 59 / epi 16` | **`sem 651 / proc 59 / epi 19`** |
| K9 gri kuyruk | 0 | **0** |
| K10 fikstür | 0 | **0** |
| K11 kapı gecikmesi (medyan) | 72,4 ms | **133,8 ms** |
| K12 kaynaksız L2 | 258 | **258** (açık iş) |

**K4/K5/K6 ölçülemedi:** bu üçünü üreten kalıcı bir harness yok (Faz 11-D'de
tek seferlik ölçüldü, betiğe dönüştürülmedi) — **açık iş**. Yerine genel
sohbet beyin paketi 5 sorguyla ölçüldü: bağlam 1.802-3.414 token (bütçe 4.000),
`brain_has_answer` 5 sorgunun **2**'sinde True.

### Kalanlar (bu QA'da yapılan diğer bağlamalar)

- `dream.ensure_daily_dreaming_task` **üründe çağrısızdı** → `bootstrap.ensure_memory_tasks()`
  eklendi ve `main.py`'de zamanlayıcı kurulunca çağrılıyor (idempotent, model
  çağırmaz); test `…::test_ensure_memory_tasks_registers_daily_dreaming_idempotently`.
- Eski `CognitiveMemorySystem.dream_and_consolidate` çağıranları yeni modüle
  yönlendirildi: `main.py` (`daily-dreaming` kancası) ve
  `core/slash_commands.py` (`/memory dream`). `ui/widgets/tasks_widget.py:425`
  **hâlâ eski metodu çağırıyor** (11-E hareketli hedef; dokunulmadı) — açık iş.
- `config.amplification_lock` ayarının **arayüzde karşılığı yok**
  (`src/entropy/core/config.py:363`; `src/entropy/ui` altında hiç geçmiyor) — açık iş.
- Kartın `report_path` alanı **hiç dolmuyor**: köprü raporu
  `Entropy/Skills/<yetenek>/Reports/Gorev_*.md` altına yazıp yolu yalnızca
  `bus.task_notification` ile yayıyor, karta işlemiyor — açık iş.
- **Marka taraması:** üreticinin adı → **0 dosya**. Ürünün adı kelime sınırlı
  aramada 20 dosyada geçiyor; bunların çoğu "metin imleci" anlamında
  (`slide_engine.py`, `terminal_pane.py`, `graph_store.py` …). Gerçek ürün
  atfı yalnızca `docs/reports/2026-09-11_Faz9_Arastirma_B_Agent_Desk_Yol_Haritasi.md`
  (rakip taraması, 6 satır) ve `docs/reports/2026-09-10_Faz11F_…` içinde —
  **karar orkestratörde**, dokunulmadı.

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
  imza `sha1(istem|model|efor)`), `/memory merge`
  (**`memory.gray_merge.run_merge_round`** — `run` diye bir sembol YOK),
  `/memory dream` (`memory.dream.dream_and_consolidate`), `/memory stop`,
  `/distill wiki compile <yetenek> [--turns N]`
  (`memory.wiki.compile_skill`). Hafıza modülü yoksa komut GERÇEK nedeni
  gösterir ("henüz kurulu değil" yalanı yazılmaz). **Faz 12-B: üçü de arka
  planda koşar** (aşağıya bak).
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
  `brain_has_answer`; eşik **`config.brain_confidence_threshold = 0.40`**
  (Faz 12-A kalibrasyonu: 0,45 → 8/10, **0,40 → 9/10**, 0,30 → 5/10).
  `summary()` ikisini de döndürür.
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
  **Faz 12-C'de canlı sözleşme testine bağlandı** (`tests/test_phase12_skill_synthesis.py`):
  `WIKI.state.json` gerçekten yazılıyor/okunuyor (iki çağrı: 2 tur → 0 tur);
  parçalı koşu ölçüldü (5 rapor, `budget_turns=2` → 2 + 2 + 1 tur,
  `remaining` 3 → 1 → 0, aynı rapor iki kez turlanmıyor); köprüsüz çağrı 0 tur.
- **Pano araçları sistem isteminde (Faz 12-C):**
  `system_prompt.board_tools_section(max_chars=BUDGET_BOARD_TOOLS=600)` metni
  **yalnızca** `agents.board_tools.entropy_tools_section()`ten alır (12-B'nin
  sunacağı sembol). Sembol yoksa bölüm sessizce atlanır — hafıza katmanı pano
  metninin kopyasını TUTMAZ. Bölüm 2'ye (`_tools_block`) eklenir ve
  **yalnızca `kind="chat"` + `provider="claude"`** yolunda görünür (kart
  kipinde ajan kendi araç metnini alır, agy kendi varsayılan istemini korur).
- **Gri tur kasa günlüğü (Faz 12-C):** `gray_merge.run_merge_round(...,
  vault_path=None)` aday bulunan her turu `<kasa>/Entropy/Memory/merge_log.md`
  dosyasına **tek satır** olarak yazar (`append_vault_merge_log`,
  `merge_log_path`, `MergeResult.vault_log`); JSONL günlüğü
  (`gray_merge_log.jsonl`) makine tarafı olarak yerinde kalır. Aday yoksa satır
  yazılmaz. Gerçekleştirim `_merge_round_impl`e taşındı, davranış değişmedi.
- **Ölçüm paketi genişledi (Faz 12-C, `scripts/brain_metrics.py`):**
  `gray_queue_report(db, nodes)` → K9 `{rows, pending, done, nodes, ratio_pct,
  rounds, last_round}` (son turun özeti dahil);
  `context_metrics(queries=None, skill=None, builder=None)` → K4 bütçe payı,
  K5 damıtılmış pay, **K6 wiki payı** (`DEFAULT_CONTEXT_QUERIES` = 5 genel
  sorgu, `K6_MIN_WIKI_PCT = 15.0`). Wiki payı = `wiki_pages` bölümünün tamamı +
  genel beyin paketindeki `[Wiki]` bloğu. CLI: `--context [--context-skill X]`.
  **Salt okunur:** bağlam `include_handoff=False` ile kurulur (aktarım sayfası
  okunduğunda tüketilir; ölçüm kasayı değiştirmemeli). Model çağrısı yok.
- **Beceri sentezi v1 (Faz 12-C, `memory/skill_synthesis.py`, SKILLFOUNDRY):**
  Girdi: bir yetenek (playbook + wiki + raporlar) ya da tekrarlayan iş sinyali
  (`recurring_signals(vault_path, store, min_reports=MIN_RECURRENCE=3)`).
  Çıktı **aday**: `<kasa>/Entropy/Skills/_candidates/<ad>/{SKILL.md,
  scripts/<ad>.py, tests/test_<ad>.py, CANDIDATE.json}`.
  `SKILL.md` şeması yedi zorunlu bölüm (`REQUIRED_SECTIONS`): *Ne zaman
  kullanılır, Ortam varsayımları, Girdiler, Çıktılar, Adımlar, Sonlandırma
  ölçütü, Kaynaklar* (+ ön bilgi `name/description/version/schema_version/
  source_skill`); kaynak (provenance) **zorunlu**.
  `synthesize_skill(skill, name=None, send_prompt=None, vault_path=None,
  store=None)`: `send_prompt` yoksa **kotasız iskelet** (playbook bölümlerinden,
  `turns=0`), varsa **tek tur** zenginleştirme (`bridge_prompt` sözleşmesi;
  ayrıştırılamayan yanıt iskeleti bozmaz, `Kaynaklar` modelden ALINMAZ).
  Öz-doğrulama kotasız: `validate_candidate` → `checks {schema_complete,
  has_provenance, steps_testable, no_leak, has_script, has_test}`; hepsi
  geçerse `status=validated`, aksi hâlde `draft`. `no_leak` marka adını
  (parçalı sabit) ve uygulama adının sızmasını arar.
  Onay yüzeyi: `list_candidates(vault_path)` (kural onay paneliyle aynı yerde;
  **bus sinyali yayılmaz**, arayüz listeyi okur), `promote_skill(ad)` adayı
  `<kasa>/Skills/<ad>/` altına kopyalar (`CANDIDATE.json` kopyalanmaz,
  `status=approved`) — **doğrulamadan geçmeyen aday `force=True` olmadan
  yükseltilmez**; `reject_skill(ad, reason)` `status=rejected` yazar, **dosya
  silmez**. Yükseltilen paket `skills.manager.SkillManager(root_skills_dir=
  <kasa>/Skills)` ile keşfediliyor (test edildi).
- **Slash komut sözleşmesi (agy 12-B bağlayacak):** `/skill synth <yetenek>`
  → `skill_synthesis.synthesize_skill(<yetenek>, send_prompt=<köprü|None>)`
  (köprü verilirse **tek tur**), `/skill approve <ad>` → `promote_skill`,
  `/skill reject <ad> [gerekçe]` → `reject_skill`, `/skill candidates` →
  `list_candidates`. Üçü de köprüyü çağırandan alır; modül kendi başına tur
  açmaz.
- **Genel sohbet beyin paketi (Faz 11.9):** `context_builder.BUDGET_GENERAL_BRAIN
  = 1500` (`BRAIN_IDENTITY_TOKENS=300`, `BRAIN_RULES_TOKENS=400`,
  `BRAIN_WIKI_PAGES=4`). Yalnızca `skill_name` **boşken** ödenir; içerik =
  kimlik düğümleri (`is_identity=1`) + onaylı kurallar (`promoted_rules`,
  `ENTROPY_OFFICE`) + **yetenekler arası** en iyi wiki sayfaları. PPR
  genişletmeli recall ve aktarım özeti kendi bölümlerinde kalır (aynı metin
  iki kez ödenmez). `_wiki_page_files(None)` artık tüm yeteneklerin
  sayfalarını döndürür; `_reports_section` yeteneksiz sohbette kasa geneli
  en yeni `GENERAL_REPORT_CANDIDATES = 60` rapora düşer.
- **Yerel komut sözleşmesi (BAĞLANDI, Faz 12-A):** `/memory merge` →
  `gray_merge.run_merge_round`, `/memory dream` → `dream.dream_and_consolidate`,
  `/distill wiki compile <yetenek>` → `wiki.compile_skill`. Üçü de köprü
  çağrılabilirini **çağırandan** alır; sağlayıcı seçimi ve `send_prompt`
  uyarlaması tek yerde: **`core/bridge_prompt.py`**
  (`active_bridge(bridge=None)`, `make_send_prompt(bridge, label=...) ->
  Callable[[str], str]`, `BridgeUnavailable`, `DEFAULT_TURN_TIMEOUT = 900.0`).
  Uyarlayıcı köprünün **arka plan görev yolunu** (`send_background_task_async`
  → `on_result(full_text, ok)`) `threading.Event` ile bloklayan eşzamanlı bir
  çağrılabilire sarar. Köprü yoksa `send_prompt=None` → **kuru koşum**.
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
- **Arayüz tasarım sistemi (Faz 11-E, sözleşme):**
  - **Tek jeton kaynağı:** `ui/design/tokens.py` → `TOKENS`. Aileler:
    `color` (12 arayüz rengi), `space` (1..6 → 4/8/12/16/24/32),
    `radius` (sm/md/lg), `type` (title/heading/body/…), ve **ayrı**
    `TOKENS["viz"]` — görselleştirme paleti (`add/del/hunk/meta`,
    `kind1..kind7`, `neutral`). `viz` arayüz renklerine KARIŞMAZ: yalnızca
    veri kodlar (diff boyaması, graf düğüm türü, akış olayı). Gövde kodunda
    ham hex yasak (Desk'te hex 17 → 0).
  - **Tek QSS girişi:** `ui/design/qss.py` tüm uygulamanın stil kaynağıdır
    (yerel stil sayfası 222 → 1). Widget'lar stil yazmaz, **Qt özelliği**
    verir: `role` (`panel|card|title|heading|label|mono|icon|badge|toast|
    statusDot|toolbarGroup`), `variant` (`primary|ghost|danger`),
    `tone` (`ok|warn|danger|muted|accent`). Yeni bir görünüm gerekiyorsa
    QSS'e seçici eklenir, widget'a `setStyleSheet` YAZILMAZ.
  - **Üst çubuk sözleşmesi:** her kip penceresi `self.header_items` listesini
    kurar; **öğe sayısı ≤ 4** (kapı testi). Zen'de dördü: `brand`,
    `model_capsule`, `status_cluster`, `palette_btn`. Pencere denetimleri
    (`window_controls`) bu sayıma girmez. Çubuktan kaldırılan HER işlevin
    komut paletinde karşılığı olmak zorundadır (IA-9).
  - **Dikey gezinme:** `ui/widgets/nav_list.NavList` (`QListWidget` + 
    `QStackedWidget`). `QTabWidget` API'siyle uyumlu: `addTab(widget, label,
    icon_name)`, `count()`, `tabText(i)`, `setCurrentIndex(i)`, sinyal
    `currentChanged(int)`. Zen'de 7 bölüm (Raporlar, Yetenekler, Görevler,
    MCP, Ajanlar, Bugün, Bildirimler) — palet anahtarları `nav_*` bu sırayı
    izler.
  - **Palet eylemleri:** `_collect_palette_items()` `{"kind": "action",
    "label", "subtitle", "payload"}` sözlükleri döndürür; `run_palette_action(
    key) -> bool` (bilinmeyen anahtar `False`). Zen ve Chat aynı sözleşmeyi
    paylaşır. **Faz 11 kapanışında eklenen iki anahtar:** `toggle_lock`
    (`config.amplification_lock`) ve `toggle_board_auto`
    (`config.board_auto_dispatch`); ikisi de
    `core.slash_commands.toggle_amplification_lock()` /
    `toggle_board_auto_dispatch()` işlevlerini çağırır → `(durum, mesaj)`
    döner, ayarı kalıcılaştırır, **model çağırmaz**. Slash karşılıkları
    `/lock on|off` ve `/board auto on|off` aynı işlevleri kullanır.
  - **Gömülü belge köprüsü (Faz 12-D.2, YENİ):** `ui/design/embedded.py` tek
    kaynaktır. `palette(theme=None, density="compact")` düz onaltılık tablo
    döndürür (QTextBrowser/QTextDocument için; Qt CSS değişkeni tanımaz),
    `css_variables()` `:root { --viz-*: … }` bloğu, `js_palette_json()` aynı
    paletin JSON'u (QWebEngine tuvali). `theme=None` ise kullanıcının
    `QSettings` seçimi okunur. `EMBEDDED_CONTRAST_REQUIREMENTS` gömülü paletin
    kapı listesidir; `READER_LAYOUT_CSS()` `<pre>` sarma + akışkan görsel
    kurallarını verir ve `reading_css()`'in sonuna eklenir.
    `LIGHT_TOKENS["viz"]` **ayrı** koyu tonlara sahiptir (açık zeminde koyu
    temanın parlak serisi 1,7–2,7:1 kalıyordu).
  - **Graf tuvali sözleşmesi (DEĞİŞTİ):** ham şablon
    `knowledge_graph.GRAPH_TEMPLATE_SOURCE` (`__VIZ_CSS__`, `__VIZ_JSON__`
    yer tutucuları, **hiç düz renk yok**); kullanıma hazır hâli
    `graph_html_template(theme=None)` ve modül düzeyindeki
    `GRAPH_HTML_TEMPLATE` (varsayılan tema enjekte edilmiş). JS mantığı
    (fizik, yerleşim, etiket çakışması) DEĞİŞMEDİ; renkler `VIZ.*` /
    `VIZ.series[i]` üzerinden okunur.
  - **Okuma genişliği:** `markdown_renderer.set_reader_width(px)` /
    `reader_width()`; `render_markdown_to_html(..., reader_width=px)`.
    SVG'ler mantıksal `viewBox` + kutuya sığan `width/height` ile üretilir →
    1366 ve 460 px'te yatay kaydırma 0.
  - **Arayüz tercihleri (Faz 12-D.2, YENİ):** `ui/design/prefs.py` (`QSettings`,
    kök `Entropy/EntropyAI`). `ui_theme()/ui_density()` +
    `set_ui_theme/set_ui_density`, `save_splitter/restore_splitter/
    install_splitter_persistence(name, splitter)/reset_layout(names)`.
    Test kancası `set_settings_factory(factory)`. `ui/manager.py` açılışta
    `apply_design_system(app, theme=ui_theme(), density=ui_density())` çağırır.
    **Her `QSplitter` `install_splitter_persistence` ile kaydedilir** (kapı:
    `splitters_unpersisted = 0`).
  - **Ayarlar diyaloğu (YENİ):** `ui/widgets/settings_dialog.SettingsDialog`
    (`values()`, `apply()`); palet anahtarları `settings` ve `reset_layout`.
    Alanlar: tema, yoğunluk, `brain_confidence_threshold` (0,20–0,60),
    `amplification_lock`, `board_auto_dispatch`, `agent_session_max_cards`,
    `agent_session_max_tokens` — hepsi `getattr` guard'lı (12-B alanı yoksa
    satır kurulmaz).
  - **Telemetri şeridi KALDIRILDI (D12-02):** `zen_telemetry_status`,
    `badge_memory/skills/mcp/model` nesneleri **duruyor** ama görünmez
    (`setVisible(False)`); bilgi model kapsülü ve durum kümesinde. Token ve
    bağlam rozetleri üst çubuktan **model kapsülünün içine** taşındı → canlı
    üst çubuk yaprak sayısı 8 → 6. `ProviderStatusBadge.set_primary(provider)`
    çubukta yalnızca aktif sağlayıcıyı gösterir (diğeri ipucunda).
  - **Rapor sayacı tek kaynak (D12-03):** `report_center.total_count()` ve
    `reports_viewer.total_report_count()` aynı sayıyı verir.
  - **Birleşik pano (YENİ):** `ui/widgets/office_cards_panel.OfficeCardsPanel`
    — Zen "Görevler" sekmesinde **salt okunur** Desk ofis kartı listesi
    (`TaskBoard.list(office=ALL_CARDS)`, `office` boş ya da `"entropy"` olanlar
    süzülür), `bus.board_state_changed` ile tazelenir. Tek yön kuralı korunur.
  - **Beceri adayları (YENİ):** `ui/widgets/skill_candidates_panel.
    SkillCandidatesPanel` — 12-C `memory.skill_synthesis.list_candidates/
    promote_skill/reject_skill` sözleşmesi (guard'lı; modül yoksa panel boş).
    `decide(candidate_id, approve) -> bool`; onaysız etkinleşme yok.
  - **Otonom görev kartı:** `ZenModeWindow.on_board_state_changed(payload)` —
    `event == "task.assigned"` ve `actor == "entropy"` ise sohbete
    "Entropy görev verdi: <başlık> → <ajan>" kartı yazılır.
  - **Odak halkası:** odaklanabilir her denetimin QSS `:focus` halkası ve
    `setAccessibleName` değeri vardır (110 erişilebilir ad, WCAG 4.1.2).
- **Kimlik düğümü kaynağı (Faz 11 kapanışı):** `gate.IDENTITY_PROVENANCE =
  "identity:core"`. `is_identity=1` düğümler `legacy:pre-v2` etiketi ALMAZ ve
  güvenleri düşürülmez (kimlik dış kaynaklı bir olgu değil, aksiyomdur).
  Etiketi `scripts/memory_migrate_v2.py --tag-legacy` koyar
  (`apply_identity_tagging`, idempotent, `valid_from` yalnızca boşsa dolar).
  `brain_metrics` K12 sayımı kimlik düğümlerini **kapsam dışı** bırakır ve
  ayrı sayaçlarda raporlar: `identity_nodes`, `identity_untagged`.
- **Test bekleme bütçeleri:** `tests/timing.budget(saniye)` — sabit duvar saati
  yerine makinenin o anki hızıyla ölçeklenmiş bütçe (1 sn TTL'li kalibrasyon,
  ölçek 1,0–8,0 arası; `ENTROPY_TEST_TIMEOUT_SCALE` ile ezilir). Yük altında
  zaman aşımına giren eşzamanlılık testleri bunu kullanır.
- **Doğuş talimatı:** `office_workspace.SPAWN_INSTRUCTION_MAX_CHARS = 1200`.
### 3.1 Faz 12-B sözleşmeleri (otonom pano)

- **Araç yürütücüsü:** `agents/board_tool_exec.py` — tek giriş
  `execute(calls, board=None, card=None, actor="", actor_kind="agent",
  vault_path=None) -> [ToolResult]`; `ToolResult` bir `dict`
  (`{tool, ok, error?, card?, …}`). Beş araç TÜKETİLİR:
  `board_checkpoint` → `memory.checkpoints.write_checkpoint` (içe aktarma
  korumalı) + kartın `checkpoint` alanı (dosya YOLU; dosya yazılamazsa tek
  satır özet) + `bus.checkpoint_written`; `board_ask` →
  `mailbox.ask_entropy(...)` + kartın `review` alanı `"soru bekliyor"` +
  `notes` içine `[SORU] …` (kart DURUMU değişmez); `board_next` → aynı ajana
  atanmış sıradaki `assigned` Entropy kartı (`normalize_next`), yoksa
  `result="yok"` (sahiplenme YAPMAZ — kilit tetikleyicinindir);
  `board_finish` kapanış yolunda (`tasks._finish`); `board_create` ajanda
  **reddedilir** (`actor_kind != "entropy"`), ofis kartında da reddedilir.
  Hiçbir araç istisna yükseltmez.
- **Yeni kart alanı `review`:** kartın insan müdahalesi bekleyen kısa durumu
  (`status` DEĞİL). Ön bilgide `review:` olarak durur.
- **Özet temizleyici:** `board_tools.strip_tool_blocks(text)` +
  `has_tool_blocks(text)`; kapsam `[PANO …] … [/PANO]`,
  `LINE_BLOCK_TAGS = ("[KONTROL NOKTASI]", "[KANIT]")`,
  `LINE_TAGS = ("[KURAL]",)`. Uygulandığı yerler: kartın `summary`si (→
  `events.jsonl` yükü, `task_report_ready.summary`, sohbet rapor kartı, wiki
  sayfası, ajan belleği, hafıza kapısı) ve **sohbet yanıtı**. Ham metin köprü
  raporunda kalır. **OFİS kartı kapsam dışı:** Desk harness'ı blokları kartın
  `summary`sinden geri ayrıştırıyor (açık iş).
- **Entropy'nin otonom görev üretimi:** `core/response_hooks.py` →
  `process_chat_response(text, board=None, registry=None) -> str` (sohbette
  GÖSTERİLECEK metin) ve **`entropy_tools_section() -> str`** (hafıza ajanı
  `memory.system_prompt.build_system_prompt`a bunu ekler; kaynak
  `board_tools.tools_section(for_entropy=True)`, modül yoksa `""`).
  Kart üretimi `agents/board_autonomy.py`:
  `create_card_from_args(args, board=None, registry=None) -> (kart|None, not)`,
  `wake_dispatcher()`, `announce(card)`, `receipt_line(title, agent)`
  (`RECEIPT_PREFIX = "Görev oluşturuldu:"`), `MAX_CARDS_PER_TURN = 1`
  (risk R-A). Ajan Entropy kadrosunda değilse kart `backlog`ta AJANSIZ kalır
  ve notuna neden yazılır. Geçersiz JSON blok yok sayılır (günlüğe düşer).
  Kanca iki köprüde de **tek yerde**: `ProviderCommonMixin.finalize_chat_text
  (text) -> str`; `claude_bridge` ve `agy_bridge` metni KAYDETMEDEN ve
  `bus.agent_turn_completed` yaymadan önce çağırır. Görev yolunda çağrılmaz.
- **Posta yön kilidi (değişti):** `ENTROPY_INBOX_KINDS` hâlâ
  `("report", "status")`. Soru yalnızca AÇIK izinle geçer:
  `Mailbox.send(..., allow_question=True)` — tek çağıranı
  `mailbox.ask_entropy(agent, question, task_id="", sender_office=None,
  vault_path=None)`. `sender_office` doluysa (ofis ajanı) `MailboxScopeError`.
  Yeni sabit `ENTROPY_INBOX_AGENT_KINDS = ("report", "status", "question")`.
- **Oturum bütçesi:** ayarlar `agent_session_max_cards = 3`,
  `agent_session_max_tokens = 60000` (0 = sınırsız; ölçüm: 23.886 → 38.818 →
  66.542 token). `AgentSessionStore` yeni metotlar: `note_run(agent, provider,
  tokens) -> {cards_in_session, tokens_in_session}`, `rotate(agent, provider)`
  (imza + `conversation_id` düşer, sayaçlar sıfırlanır — `forget` KULLANILMAZ,
  R1), `budget_status(agent, provider, max_cards=0, max_tokens=0) ->
  {cards_in_session, tokens_in_session, exceeded, reason, last_reset_at}`.
  Yeni `session.json` alanları: `cards_in_session`, `tokens_in_session`,
  `last_reset_at`. Politika `agents/session_budget.py`:
  `rotate_if_needed(agent, provider, board=None, vault_path=None) -> str`
  (dönen metin isteme eklenecek `[ÖNCEKİ OTURUM]` bloğu; "" = oturum sürüyor),
  `write_handoff` / `build_handoff` / `handoff_section`,
  `handoff_path(agent, vault) = Entropy/Board/agents/<ad>/handoff.md`.
  Devir sayfası **kotasızdır** (kartların `summary`/`checkpoint`/`notes`
  alanlarından çıkarımsal). `tasks.run` istemi kurduktan SONRA
  `rotate_if_needed` çağırır ve bloğu isteme ekler; `tasks._finish`
  `_note_session_usage(card)` ile ledger'dan (`card-<id>.total_tokens`)
  sayaçları işler. Sinyal: `bus.task_notification("session:<ajan>", …)`.
  `--autocompact` bağlanmadı (risk R-D: sürüm bağımlı bayrak).
- **Projeksiyon ve ayrışma:** `TaskBoard.rewrite_taskboard()` artık
  `events.write_projection()` çağırır → `Entropy/Board/projection.json`
  yazılır ve `TASKBOARD.md` başlığındaki **`Projeksiyon karması` DOLU**.
  `board_events.board_drift(cards, view) -> [{id, card, projection}]`
  (kart dosyası ≠ projeksiyon). Ayrışma varsa `logger.warning` + olay
  **`board.drift`** + `TASKBOARD.md`de `DRIFT_MARK = "[!]"` satırı.
  `board_fsm.EVENTS` 12 → **13**; yeni `INFO_EVENTS = ("board.drift",)` —
  durum değiştirmeyen GÖZLEM olayı, `project()` onu geçiş tablosuna sokmaz
  (kart doğurmaz, `rejected` artırmaz).
- **Slash yüzeyi 34 → 31:** `/agents` → `/agent` (argümansız = liste),
  `/tasks` → `/task` (argümansız ya da tek durum sözcüğü = liste),
  `/wiki` → `/distill wiki …` (damıtım hattının ikinci adımı). Üç eski ad
  **alias olarak yaşar** (`try_handle_local_command` onları hâlâ yakalar),
  yalnızca komut paletindeki ayrı kayıtları kaldırıldı.
- **Uzun hafıza işleri arka planda:** `/memory merge`, `/memory dream`,
  `/distill wiki compile` artık `threading.Thread`e verilir ve komut HEMEN
  döner. API (`core/slash_commands`): `start_memory_job(job, label, work,
  join=0.0)`, `cancel_memory_job(job)`, `memory_job_running(job)`,
  `last_memory_job(job) -> {job,label,state,message,done,total}`,
  `reset_memory_jobs(timeout=10.0)` (testler). İş adları:
  `"memory-merge"`, `"memory-dream"`, `"wiki-compile"`. Sinyal
  **`bus.memory_job_progress(dict)`**, `state ∈ {started, progress, finished,
  failed, canceled}`. İptal: `/memory stop`, `/distill wiki compile stop`.
  `--wait <sn>` bayrağı YALNIZCA testler içindir (Qt olay döngüsü yokken
  senkron bekleme). `tests/conftest.py` her testten sonra
  `reset_memory_jobs()` çağırır.
- **agy 15-tur mesajı (D2 kapandı):** metin koddaki davranışla eşitlendi —
  özet üretilmiyor, konuşma kapatılıyor.

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
   olan arayüz hatası; **Faz 11 kapanış QA'sında kök nedeni bulundu**, madde 9'a taşındı.
3. `scripts/` altındaki ~60 tek seferlik betik: izlemeye mi alınacak, `scratch/`e mi taşınacak,
   silinecek mi? Karar verilmedi (silinmedi, dokunulmadı).
4. ~~`src/entropy/platform/autostart.py` ölü ürün modülü~~ — **KAPANDI (Faz 12-E)**:
   kaldırıldı, `config.autostart_enabled` ve iki testiyle birlikte
   ([ADR-0006](adr/ADR-0006-autostart-kaldirildi.md)). `core/claude_bg.py` "deneysel,
   bağlı değil" etiketiyle duruyor ([ADR-0007](adr/ADR-0007-claude-bg-ertelendi.md)).
5. **agy köprüsünde izolasyon yok** (kayıtlı sınır, ADR-0002): süreç proje dizininde koşar,
   ajanlar çalışma dizininden keşfedilir; CLI'da karşılık gelen bayrak yok.
6. `docs/specifications/` altındaki 5 eski spec `ARCHITECTURE.md`'ye damıtılıp arşive
   taşınacak (Faz 11-A'da yalnızca prototip spec'i arşivlendi).
7. ~~Beynin yazma tarafı: `MemoryGate` yok~~ → **Faz 11-B'de kuruldu** (§3). Kalanlar:
   - ~~`--apply` koşulmadı~~ → **2026-09-10 QA'da koşuldu ve kabul edildi** (§2.2).
   - ~~**K12 açık:** 258 eski L2 düğümü kaynaksız (§2.2).~~ → **Faz 11
     kapanışında K12 = 0** (§2.4): 256 eski düğüm `legacy:pre-v2`, kalan 2
     kimlik düğümü `identity:core` ile damgalandı.
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
   - ~~`tasks_widget.py` eski `dream_and_consolidate`~~ → **Faz 11 kapanışında
     taşındı** (`ui/widgets/tasks_widget.py:301-317`, `send_prompt=None`).
   - ~~`amplification_lock` / `board_auto_dispatch` arayüzde yok~~ →
     **Faz 11 kapanışında palet eylemi eklendi** (§3).
   - ~~**K12 açık**~~ → **Faz 11 kapanışında 0** (§2.4).
8. ~~**Zen penceresi %200 DPI'lı monitörde ekrana sığmıyor**~~ → **Faz 12-D.1'de
   kapatıldı.** Gerçek `minimumSizeHint` **605×834 → 605×464**, `ZEN_MIN_SIZE`
   **(1100, 680) → (860, 520)** (`ui/modes/zen_mode.py:71`). Kök nedenler:
   (a) `NavList` yığınının asgarisi en büyük sayfanınkiydi (Raporlar 428 px) —
   sayfalar artık kaydırma kabuğunda (`ui/widgets/nav_list.py:70-80`);
   (b) durum şeridi `heightForWidth` ile pencereye 5 satır dayatıyordu — şerit
   akan yerleşime alınıp `FlowStripHost` kabuğuna kondu
   (`ui/widgets/flow_layout.py:144`, `zen_mode.py:523`);
   (c) üst çubuk kompakt eşiği 620 → 1000 px (`zen_mode.py:506`), 960'ta durum
   kümesi kırpılmıyor. Ayrıca `available_geometry()` artık `availableGeometry`
   ile ekranın kendi `geometry()`'sini kesiştiriyor ve Zen `screenChanged`
   sinyalinde yeniden kenetleniyor. Ölçüm: `scratch/ui/phase12/fit_measurements.json`,
   `zen_960x540_scale2.png`, `zen_1920_scale2.png` (`QT_SCALE_FACTOR=2`, taşma 0).
   Test: `tests/ui/test_phase11_design_gates.py::test_zen_fits_960x540_scaled`.
9. ~~**Desk'in bildirilen asgari boyutları gerçek değil**~~ → **Faz 12-D.1'de
   kapatıldı.** Gerçek `minimumSizeHint` **1.205×620 → 678×405**; `DESK_MIN_SIZE`
   **(860, 540) → (760, 500)**, `ROSTER_MIN_WIDTH` **380 → 280**. Dört sekme
   sayfası ve iki yan sütun `desk/window.py:scroll_host()` kabuğunda; panellerin
   sert `setMinimumWidth(220)/Height(120)` çiftleri kaldırıldı. Test artık
   bildirilen değil **gerçek** asgariyi ölçüyor
   (`tests/desk/test_desk_phase7.py::test_panel_minimum_widths_sum_below_900`,
   yeşil). Görüntü: `scratch/ui/phase12/desk_900x560.png` (taşma 0).
10. **`QFont::setPointSize: Point size <= 0 (-1)`** — nokta/piksel birim
   karışımı iki yerde kapatıldı: `desk/memory_panel.py:193` (QSS fontu piksel
   boyutlu, `pointSizeF()` -1 dönüyor; artık birim korunuyor) ve
   `ui/widgets/reports_viewer.py:469` (boş `QFont()` yerine liste fontu).
   Uyarı günlükte açılıştan ~30 sn sonra, kullanıcı etkileşimiyle düşüyordu;
   offscreen'de yeniden üretilemedi — **gerçek ekranda doğrulanmalı** (QA).

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
