# STATE.md — Güncel durum (alt ajanların çalışma belleği)

> **İşe başlamadan önce bu dosyayı ve `docs/reports/` altındaki en son ilerleme raporunu oku.**
> Bu dosya alt ajanların oturumlar arası hafızasıdır: sözleşme imzaları, açık işler,
> bilinen kısıtlar ve son yeşil ölçümler burada durur. Her faz dilimi sonunda güncellenir.
> Mimari: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Kararlar: [`adr/`](adr/) · Plan: [`ROADMAP.md`](ROADMAP.md)

| | |
|---|---|
| Sürüm | **v0.8.0** (Faz 11-A sonrası etiket adayı: v0.9.0) |
| Dal | `ai/v0.1.7` (ana dal: `master`) |
| Son güncelleme | 2026-09-10, **Faz 11 KAPANIŞ QA** (§2.4): tam süit **2.355 passed / 0 failed / 406 s**, build exit 0 (241 s, `dist/EntropyAI`), **K12 = 0**, 11-E sözleşmeleri §3'e yazıldı, 2 sessiz arayüz regresyonu düzeltildi, 3 açık bulgu (§5.8-10) |
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
4. `src/entropy/platform/autostart.py` — **tek ölü ürün modülü**: üründe içe aktaranı yok,
   yalnızca iki test ve spec canlı tutuyor; `config.autostart_enabled` okunup yazılıyor ama
   hiçbir yerde uygulanmıyor. Özellik ya bağlanmalı ya kaldırılmalı.
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
8. **Zen penceresi %200 DPI'lı 1920×1080 monitörde ekrana SIĞMIYOR** (Faz 11
   kapanış QA, gerçek ölçüm — **Faz 6'dan beri var, 11-E regresyonu değil**).
   `ZEN_MIN_SIZE = (1100, 680)` mantıksal (`ui/modes/zen_mode.py:65`), ama
   `minimumSizeHint` **605×845**; LG ULTRAGEAR'da Qt `devicePixelRatio 2.0`
   bildirdiği hâlde `availableGeometry` 1920×1032 **mantıksal** döndürüyor →
   pencere 1920×1032 mantıksal açılıyor, bu da **3840×2064 fiziksel** piksel
   demek; panel 1920×1080. Sonuç: arayüzün **yaklaşık yarısı ekran dışında**
   kalıyor (exe görüntüsünde durum kümesi "Claude ✓ ma…" diye kesiliyor,
   pencere denetimlerinden yalnızca "Küçült" görünüyor). Asgari yükseklik
   845 mantıksal = 1690 fiziksel > 1080 olduğu için pencere bu monitörde
   **hiçbir boyutta tam sığamaz**. Kanıt: `scratch/ui/phase11e/live_dpi.json`
   (`physical_needed: [3840, 2064]`, `fits_on_screen: true` — Qt'nin kendi
   kıyası yanıltıcı), `live_exe_zen.png`. Sahibi: ui-engineer (asgari
   boyutların düşürülmesi + DPI'ya duyarlı yerleşim kararı).
9. **Desk'in bildirilen asgari boyutları gerçek değil** (Faz 11 kapanış QA;
   `tests/desk/test_desk_phase7.py::test_panel_minimum_widths_sum_below_900`
   bu yüzden kırmızı — **HEAD'de de kırmızı**, ayrı worktree'de doğrulandı,
   kapanış QA'sının değişikliklerinden bağımsız).
   *Genişlik:* bildirilen `minimumWidth` toplamı 180 + 240 + 380 = **800**,
   ama gerçek `minimumSizeHint` toplamı **314 + 511 + 380 = 1.205 px**.
   Kök neden: `QTabWidget.setMinimumWidth(240)` (`desk/window.py:390`)
   sayfaların kendi sert asgarilerini EZEMEZ; `minimumSizeHint` sayfaların
   maksimumudur. Ölçüm: `Kartlar 364 · Terminaller 507 · Projeler 852 ·
   Bellek 576` → en darboğaz **Projeler** (`desk/projects_panel.py:125`
   `setMinimumWidth(460)` + `:337` `setMinimumWidth(220)`).
   *Yükseklik:* bildirilen `minimumSize` 860×540, gerçek gereksinim
   **900×620**: 960×540 → 7 taşma, 960×580 → 3, 960×600 → 3,
   **960×620 → 0**; 860×620 → 4, **900×620 → 0**
   (`src/entropy/desk/board_panel.py:52` `detail_tabs.setMinimumHeight(120)`).
   Kanıt: `scratch/ui/phase11e/live_desk_min.py` çıktısı. Sahibi: ui-engineer
   (ya sayfa asgarileri düşürülecek ya sekmeler kaydırılabilir yapılacak).
10. **`QFont::setPointSize: Point size <= 0 (-1)` uyarısı** exe açılışında bir
   kez düşüyor (`.entropy/logs/entropy.log`, 08:03:25). Hata değil, uyarı;
   kaynağı bulunamadı (`setPointSize` yalnızca `reports_viewer.py:471`'de ve
   orada 8 ile çağrılıyor) — muhtemelen piksel boyutlu bir fontun
   `pointSize()`'ı kopyalanıyor. Açık iş.

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
