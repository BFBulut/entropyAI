# Faz 10 — Araştırma Notu: Entropy Agent Desk'i gerçek geliştirme ofisine çevirmek

**Tarih:** 2026-09-11 · **Depo:** `C:\EntropiAI` · **Dal:** `ai/v0.1.7` (Faz 9 değişiklikleri çalışma ağacında)
**Kapsam:** SALT OKUNUR araştırma ve tasarım. Bu koşuda hiçbir kaynak dosya değiştirilmedi; tek yazılan dosya bu nottur.
**Girdi:** `docs/reports/2026-09-11_Faz9_Arastirma_B_Agent_Desk_Yol_Haritasi.md` §6 (P1) ve §7 "FAZ 10" tablosu (10.1–10.11).
**Amaç:** Her maddeyi doğrudan koda geçilebilecek bir tasarıma indirmek; kullanıcı onayından sonra uygulama başlar.

**Marka kuralı:** ticari referans ürün bu belgede yalnızca "**AgentSpace (ticari referans)**" olarak anılır; üretici adı ve alan adı geçmez.

**Satır numaraları uyarısı:** Faz 9 raporundaki bazı satır numaraları çalışma ağacındaki değişikliklerle kaymıştır
(ör. `tasks.py:481 project_file_section` → bugün `tasks.py:765`). Bu notta verilen tüm `dosya:satır` referansları
**bu koşuda ölçülen güncel** değerlerdir ve **`7edd8a7`** (`feat(phase-9): … v0.7.0`) commit'ine göre doğrulanmıştır.
Not: araştırma sürerken Faz 9 paralel bir süreç tarafından commit'lendi (`be96ac2` → `7edd8a7`); bütün referanslar
commit sonrası yeniden denetlendi ve dosya sınırları içinde olduğu otomatik olarak doğrulandı.

---

## 0. Karar özeti

| # | İş | Önerilen tasarım (tek cümle) | Ana kanıt | Ajan | Kota |
|---|---|---|---|---|---|
| 10.1 | Köprü akışına ajan etiketi | Eski `token_chunk_received(str)` **aynen kalır**; yanına `agent_stream_chunk(dict)` eklenir ve `consume_stream`'e isteğe bağlı `context` sözlüğü geçilir; agy arka plan yolu da ilk kez akış yayar | `claude_bridge.py:1070` tek emit, `agy_bridge.py:1030-1033` arka planda **hiç** `token_chunk_received` yok | agy | ~20-30k |
| 10.2 | Ajan başına adlandırılmış terminal | **(a) Akış terminali** — yeni bağımlılık yok, kota yok, iki sağlayıcıda da aynı; gerçek PTY Faz 11'e ertelenir (kanıt: ConPTY çalışıyor **ama** güven diyaloğu + tam VT ayrıştırıcı gerekiyor) | ConPTY probu: 1160 bayt, 24-bit renk, `?2004h` bracketed paste, "Is this a project you trust?" diyaloğu | ui | 0 |
| 10.3 | Proje = depo + dal | `DeskProject`'e `repo_path`, `base_branch`, `worktree_root` alanları; ön bilgi ayrıştırıcı zaten `front.get(...)` desenli, geriye uyum bedava | `desk_registry.py:118-126` (dataclass), `:714-729` (`get_project`) | agy | 0 |
| 10.4 | Kart başına worktree | Worktree'yi **Entropy kurar** (`git worktree add`), `claude --worktree` KULLANILMAZ (agy'de karşılığı yok); kart istemine `[ÇALIŞMA DİZİNİ]` bloğu; `run_cwd` worktree kartında nötr dizine düşmez; temizlik **doğrulamalı ve iki adımlı** | Ölçüm: dosya kilidi varken `worktree remove --force` **rc=255** ve yarım silinmiş dizin bırakıyor | agy | ~20-30k |
| 10.5 | PR akışı | `gh` **kurulu değil** → yedek yol (dal + `git diff --stat` özeti) **birincil**, `gh` varsa taslak PR ek yol; kart hiçbir durumda başarısız olmaz | `where.exe gh` → "Could not find files"; `git remote -v` → `origin https://github.com/BFBulut/entropyAI.git` var | agy | 0 |
| 10.6 | Diff paneli | Yeni "Değişiklikler" sekmesi; `git diff --numstat` özet + dosya tıklanınca `git diff -- <yol>`; QPlainTextEdit + QSyntaxHighlighter (QWebEngine **hayır**); `BoardPanel.card_selected` zaten var, pencerede bağlı değil | `board_panel.py:22,32` sinyal var; `window.py` içinde `card_selected` bağlantısı **yok** | ui | 0 |
| 10.7 | Maliyet/kota şeridi | Şeridin **çekirdeği Faz 9'da yapılmış**; eksik olan kart başına satır + sağlayıcı/oturum penceresi; tek üretici `mailbox.office_status()` kalır, yüzdelik kota YOK | `window.py:388-406` harcama rozeti çalışıyor; `mailbox.py:651-664` sözleşme | ui + agy | 0 |
| 10.8 | Orkestratör gerçek araştırma | `_can_web_search()` **kadro** kontrolünden **orkestratörün kendi araç listesi** kontrolüne döner; orkestratör zaten `read-only` = `WebSearch, WebFetch` sahibi, yalnızca istem onu kullanmaya çağırmıyor; `research_notes`'a `source` alanı zorunlu | `desk_registry.py:679` `tools_policy="read-only"`, `compile.py:143` → `WebFetch, WebSearch`; `harness.py:661-672` yanlış yeri kontrol ediyor | agy + mem | +3-8k/plan |
| 10.9 | Makbuz + koşan karta yorum | Makbuz **ayrı dosya değil**: `Offices/<ofis>/reports/<kart>.md` tek kaynak kalır, panel onu okur; yorum `instruct_office(task_id=...)` ile kutuya düşer ve **`TaskBoard.build_prompt`** içinde bir sonraki **başlamamış** alt karta enjekte edilir | `harness.py:1244-1248` rapor yolu; `mailbox.py:436-461` `instruct_office` `task_id` alıyor ama harness yalnızca **planlamada** okuyor (`harness.py:721-727`) | ui + agy | ~10k |
| 10.10 | Ekip şablonları | `Entropy/Desk/Templates/<ad>/OFFICE.md + agents/*.md`; kasada yoksa **koda gömülü** varsayılan 4 şablon; ofis diyaloğuna tek `QComboBox` | `desk_registry.py` altında hiçbir "template" kavramı yok (grep: 0 eşleşme); `_apply_new_agents` deseni hazır (`harness.py:813-861`) | agy | ~20k |
| 10.11 | QA + derleme | 10.1/10.4 için paralellik testleri, worktree yaşam döngüsü testi, `dist_check` derleme + smoke | — | qa | 0 |

**Faz 10 toplam kota tahmini: ~85–115k token** (Claude-yalnız kurulumda; ayrıntı §3).

**Ana mimari kararlar (özet):**
1. **Worktree'nin sahibi Entropy'dir**, sağlayıcı değil. `claude --worktree` cazip ama agy'de karşılığı yok; sağlayıcı-nötrlük (Faz 9.5 kararı) korunmalı.
2. **Terminal = akış terminali**, PTY değil. Kartlar zaten etkileşimsiz (`-p`); PTY ikinci bir süreç ve ikinci bir kota demek.
3. **Makbuz yeni bir depo değil**, var olan raporun okunma yüzeyi. İkinci bir gerçek kaynak açmıyoruz.
4. **PR akışının varsayılanı yerel dal + diff özeti**; `gh` bir "varsa daha iyi" yoludur, ön koşul değil.

---

## 1. Ortam ölçümleri — bu notun kanıt tabanı

Bütün çıktılar bu koşuda, `C:\EntropiAI` üzerinde alınmıştır.

### 1.1 Araç sürümleri

```
$ git --version
git version 2.49.0.windows.1

$ claude --version
2.1.265 (Claude Code)

$ agy --version
1.1.28

$ python --version
Python 3.13.5

$ gh --version
bash: gh: command not found
$ where.exe gh
INFO: Could not find files for the given pattern(s).
```

`gh` **kurulu değil**. Kurulum yolu açık: `winget` mevcut (`C:\Users\batu_\AppData\Local\Microsoft\WindowsApps\winget.exe`)
ve resmî kurulum komutu `winget install --id GitHub.cli --source winget`.

### 1.2 Depo durumu

```
$ git remote -v
origin  https://github.com/BFBulut/entropyAI.git (fetch)
origin  https://github.com/BFBulut/entropyAI.git (push)

$ git worktree list
C:/EntropiAI  be96ac2 [ai/v0.1.7]

$ git config --get core.longpaths
(boş — ayarlanmamış)

$ git ls-files | (toplam)
tracked working tree: 13.1 MB across 535 files

$ df -h /c
C:  931G  909G  23G  98% /c
```

Üç sonuç:
- **Uzak depo var** → PR akışı teknik olarak mümkün (yalnızca `gh` + kimlik doğrulama eksik).
- **`core.longpaths` kapalı** → worktree kökü kısa tutulmalı (§2.4).
- **Disk %98 dolu, 23 GB boş.** Bu deponun çalışma ağacı 13 MB, yani kart başına worktree burada ucuz;
  kullanıcı büyük bir depo bağlarsa (ör. `node_modules` içeren) her worktree o boyutu tekrar eder. Şeritte uyarı gerekli.

### 1.3 `git worktree` — Windows davranışı (canlı deney)

Geçici bir depo (`%TEMP%\...\scratchpad\wt_demo`) üzerinde yapıldı, sonunda tamamen silindi;
`C:\EntropiAI` deposunun worktree listesi **değişmedi** (yukarıdaki `git worktree list` çıktısı deneyden sonrasıdır).

| Deney | Sonuç |
|---|---|
| `git worktree add <yol> -b desk/card-abc123` | ✅ Çalışır. İki worktree'de aynı dosya bağımsız değişiyor (izolasyon gerçek). |
| İki worktree aynı anda | ✅ Çalışır. |
| Aynı dalı ikinci worktree'ye ekleme | ❌ `fatal: 'desk/card-abc123' is already used by worktree at ...` → **dal adı kart kimliğiyle birebir olmalı**, tekrar kullanılamaz. |
| `git diff --numstat` / `--stat` worktree içinde | ✅ Çalışır (`1  0  a.txt` / ` a.txt \| 1 + `). |
| Kirli worktree'yi `remove` (force'suz) | ❌ `fatal: ... contains modified or untracked files, use --force to delete it` |
| **Dosya kilidi varken `remove --force`** | ❌ **`rc=255`, `error: failed to delete '...': Invalid argument`** |
| Kilitli silme sonrası durum | ⚠️ **Yarım silinmiş.** Yönetim kaydı gitmiş (`worktree list`'te yok, ikinci deneme `is not a working tree` diyor) **ama dizin ve ajanın dosyaları diskte duruyor.** |
| `git worktree prune -v` ile kurtarma | ❌ Hiçbir şey yapmıyor (kayıt zaten silinmiş). |
| Aynı yola yeniden `worktree add` | ❌ `fatal: '...' already exists` → **kart yeniden koşamaz.** |
| `remove` dalı siliyor mu? | ❌ Hayır. `git branch --list` sonrası `desk/card-def456` duruyor → ayrı `git branch -D` gerekir. |
| Worktree deponun **içinde** (`.worktrees/…`) | ⚠️ Çalışır ama `git status --porcelain` → `?? .worktrees/` (üst deponun durumunu kirletir). |
| **Uzun yol** (358 karakter) | ❌ `fatal: could not create leading directories of '.../.git': Filename too long` |

**Bu tablonun tasarıma çevrilmesi §2.4'te.** En kritik bulgu: *silme atomik değil ve başarısızlığı sessiz değil ama yıkıcı.*
Bugünkü `harness.stop()` (`harness.py:1350-1362`) ve `_terminate_children` (`:510-537`) süreci öldürüyor ama
**dosya tanıtıcılarının kapanmasını beklemiyor**; worktree temizliği doğrudan buraya bağlanırsa yarım silinmiş
dizinler birikir.

### 1.4 `pywinpty` / ConPTY — gerçek terminal denemesi

```
$ python -c "import winpty; print(winpty.__version__)"
3.0.5           # pywinpty KURULU (import adı: winpty)
pyte            → False   (KURULU DEĞİL)
Pygments 2.19.2 → KURULU
GitPython 3.1.45→ KURULU
PySide6 6.11.2  → KURULU
```

**Deney 1 — ConPTY temel:** `PtyProcess.spawn("cmd.exe /c ver")` →
`'\x1b[1t\x1b[c\x1b[?1004h\x1b[?9001h\x1b[?7l\x1b[?7h\r\nMicrosoft Windows [Version 10.0.26200.9278]\r\n'`
ConPTY çalışıyor; çıktı ham ANSI.

**Deney 2 — abonelik kimliğiyle etkileşimli `claude` ConPTY içinde (kullanıcının açıkça sorduğu soru):**

```
--- claude TUI under ConPTY ---
bytes: 1160
raw head: '\x1b[1t\x1b[c\x1b[?1004h\x1b[?9001h\x1b[?7l\x1b[?7h\x1b7\x1b[r\x1b8\x1b[?25h\x1b[?25l
           \x1b[?2004h\x1b[?2031h\x1b[?1004h\x1b[?9001l\x1b[?9001h\r\n\x1b[38;2;255;193;7m────…'
  | Accessing workspace: …\scratchpad\ptytest
  | Quick safety check: Is this a project you created or one you trust?
  | ❯ No, exit
  |   Yes, I trust this folder
  |   Enter to confirm · Esc to cancel
```

**Sonuç (belge):** Abonelik kimliğiyle etkileşimli `claude` oturumu **ConPTY içinde çalışıyor** — TUI boyandı,
24-bit renk (`\x1b[38;2;255;193;7m`), bracketed paste (`?2004h`), fare izleme (`?1004h`, `?9001h`) geldi.
**Ama üç maliyet çıktı:**
1. İlk ekran bir **güven diyaloğu**dur; masaüstü terminali bunu programatik olarak yanıtlamak zorunda kalır.
2. Çıktı tam bir ekran arabelleği protokolüdür. Kaçış dizileri çıkarıldığında metin `Accessingworkspace:` gibi
   **kelimeleri bitişik** çıkıyor — çünkü TUI her sözcüğü imleç konumlandırmasıyla yerleştiriyor.
   Yani `QPlainTextEdit`'e ham eklemek **işe yaramaz**; `pyte` benzeri bir ekran emülatörü **zorunlu**.
3. `pyte` kurulu değil → yeni bağımlılık + PyInstaller'a yeni bir yerel/saf-python paket.

Karşılaştırma için `agy --help`'te ConPTY'ye gerek bırakmayan bir arka plan/oturum mekanizması **yok**.

### 1.5 CLI yetenek matrisi (10.2, 10.4, 10.5, 10.7 kararlarının dayanağı)

`claude --help` ve `agy --help` çıktılarından derlendi:

| Yetenek | `claude` 2.1.265 | `agy` 1.1.28 |
|---|---|---|
| `-p/--print` + `--output-format stream-json` | ✅ | ✅ |
| `--add-dir` | ✅ | ✅ |
| `--agent <ad>` | ✅ | ✅ |
| `--conversation` / `--resume` | `--resume`, `--fork-session` | `--conversation`, `--continue` |
| **`-w, --worktree [ad]`** — oturum için git worktree açar | ✅ | ❌ |
| **`--bg/--background` + `attach`/`logs`/`stop`/`rm`/`agents`** | ✅ | ❌ |
| **`--session-id <uuid>`** — oturum kimliğini **önceden** atama | ✅ | ❌ |
| **`-n, --name <ad>`** — oturuma görünen ad | ✅ | ❌ |
| **`--max-budget-usd`** (yalnızca `--print`) | ✅ | ❌ |
| `--tools` / `--allowedTools` / `--disallowedTools` | ✅ | ❌ (`--sandbox` var) |
| `--include-partial-messages` | ✅ | ❌ |
| `--max-turns` | ❌ (bu sürümde yok; `claude_bridge.py` `CLAUDE_SUPPORTS_MAX_TURNS` ile zaten belgelemiş) | ❌ |
| `--tmux` | ✅ (yalnızca `--worktree` ile; iTerm2/tmux — Windows'ta işe yaramaz) | ❌ |
| `agents --json` (TTY istemiyor) | ✅ | ❌ |

`claude agents --json` canlı çıktısı (ölçüldü):

```json
[ { "pid": 56408, "cwd": "C:\\EntropiAI", "kind": "interactive",
    "startedAt": 1788910853330, "sessionId": "4984d9a3-…", "name": "entropiai-dc" } ]
```

**Bu matrisin doğurduğu tek kural:** Claude'a özgü hiçbir yetenek Desk'in **sözleşmesi** hâline getirilemez.
`--worktree`, `--bg`, `--session-id` kullanılırsa agy sağlayıcılı bir ofis sessizce farklı davranır ve
Faz 9.5'te kapatılan "sessizce sağlayıcıya düşme" deliği geri açılır. Worktree'yi Entropy kurar (§2.4);
akış etiketini Entropy üretir (§2.1); terminal Entropy'nin kendi tamponudur (§2.2).

---

## 2. Madde madde tasarım

### 2.1 — 10.1 Köprü akışına ajan etiketi

#### Bugünkü durum (kanıt)

`token_chunk_received` **tek bir `str` taşır** ve gönderenle ilgili hiçbir şey söylemez:

- Tanım: `src/entropy/core/event_bus.py:19` → `token_chunk_received = Signal(str)   # streaming text chunk`
- Claude tarafı tek emit noktası: `src/entropy/core/claude_bridge.py:1070` (`consume_stream` içinde, `assistant`→`text` bloğunda).
  `consume_stream` (`claude_bridge.py:999-1138`) **hem sohbet hem arka plan** yolunun ortak çevirmenidir
  (`_execute_prompt_worker` ve `_execute_background_task_worker`, `:1873` ve `:1913` çağrıları).
- agy tarafı: emitler **yalnızca** `_execute_prompt_worker` içinde (`agy_bridge.py:1696`, `:1712`, `:1761`).
  Arka plan işçisi (`agy_bridge.py:744-1240`) metin deltasını **yalnızca** `bus.terminal_output_received.emit(text_delta)`
  ile yayıyor (`agy_bridge.py:1032`). **Yani agy sağlayıcılı bir ofis kartının canlı akışı Desk'te hiç görünmüyor.**
- Tüketici: `src/entropy/desk/stream_panel.py:78-80` sinyale bağlanıyor, `:174-185` `_on_chunk` her parçayı
  **odaktaki ajanın** tamponuna yazıyor. Panelin kendi başlık yorumu sorunu kabul ediyor
  (`stream_panel.py:8-11`: *"köprü akışı ajan başına etiketlemiyor … ajan başına ayrıştırma köprü sözleşmesi genişleyince yapılabilir"*).

Bilgi kaynakta **var**: `_execute_background_task_worker` imzası `task_id, task_name, …, agent, …, model, agent_spec`
alıyor (`claude_bridge.py:1776-1790`, `agy_bridge.py:744-759`). Yalnızca akışa taşınmıyor.

#### Önerilen tasarım

**A. Yeni sinyal (eskisi bozulmaz).** `event_bus.py`'ye eklenir:

```python
# Ajan etiketli akış (Faz 10.1). Eski `token_chunk_received(str)` BİR SÜRÜM
# BOYUNCA korunur: Zen ve Chat ona bağlı (zen_mode.py:603, chat_mode.py:620)
# ve sohbet yolunun ajan kavramı yok.
agent_stream_chunk = Signal(dict)
```

Sözlük şeması (tümü isteğe bağlı, `text` hariç):

| Alan | Anlam | Kaynak |
|---|---|---|
| `scope` | `"chat"` \| `"card"` \| `"office"` | çağıran işçi |
| `task_id` | ledger görev kimliği (`card-<id>`, `office-plan-<id>`, `office-eval-<id>`) | işçinin `task_id` parametresi |
| `card_id` | `task_id`'den `card-` öneki atılmış hâli (kart değilse `""`) | türetilir |
| `agent` | ajan adı | işçinin `agent` parametresi |
| `provider` | `"claude"` \| `"agy"` | `self.provider_name` |
| `model` | o koşunun modeli | `self.model_for_run(model)` |
| `kind` | `"text"` \| `"thought"` \| `"tool"` \| `"tool_result"` \| `"system"` \| `"raw"` | olay türü |
| `text` | parçanın kendisi | akış |

`office` alanı **bilerek yok**: köprü ofisi bilmez ve bilmemeli. Panel `card_id → TaskCard.office` eşlemesini
`TaskBoard.get()` ile yapar (`tasks.py:465`), böylece köprü sözleşmesi ofis kavramından bağımsız kalır.

**B. `consume_stream`'e `context` parametresi.** Tek satırlık genişletme, geriye tam uyumlu:

```python
def consume_stream(self, stream, sink=None, max_steps=None, on_step_limit=None,
                   context: Optional[dict] = None) -> Dict[str, object]:
```

`context is None` ise davranış bugünküyle **birebir aynı** (yalnızca eski sinyaller). Doluysa her
`bus.terminal_output_received.emit(...)` / `bus.token_chunk_received.emit(...)` satırının yanına
`self._emit_tagged(context, kind, text)` konur. Bu, `claude_bridge.py:1070`, `:1076`, `:1087`, `:1113`, `:1126`
noktalarında toplam **5 satır** ekleme demektir.

**C. agy paritesi (asıl kazanç).** `agy_bridge.py:1032` ve `:1039` (arka plan `text_delta` / `result.response`)
noktalarına aynı yardımcı eklenir. Böylece agy kartları **ilk kez** Desk akışında görünür.

**D. `StreamPanel` tampon modeli.** Bugün tek `self._buffer: str` var (`stream_panel.py:40`). Yenisi:

```python
self._buffers: Dict[str, str] = {}      # anahtar: card_id or task_id or agent
self._order:   List[str] = []           # en son yazılan öne
MAX_STREAM_CHARS = 40_000               # anahtar BAŞINA (bugün toplam)
MAX_STREAM_KEYS  = 8                    # en eski tampon düşer (bellek tavanı)
```

`_on_chunk(str)` (eski sinyal) yalnızca `scope="chat"` yedeği olarak kalır; `_on_tagged(dict)` esas yoldur.
`focus_agent(name)` artık tamponu **silmez**, yalnızca hangi anahtarın render edileceğini değiştirir —
bugünkü `self._buffer = ""` (`stream_panel.py:93`) davranışı ajan değiştirince veriyi kaybediyor.

#### Kabul ölçütü

1. İki alt kart aynı anda koşarken `StreamPanel._buffers` **iki ayrı anahtar** taşır ve metinler karışmaz.
2. `agent_stream_chunk` yayılmayan bir kurulumda (eski köprü taklidi) panel **çökmez**, eski yola düşer.
3. agy sağlayıcılı bir alt kart koşarken Akış sekmesinde metin görünür (bugün görünmüyor).
4. `zen_mode.py:603` ve `chat_mode.py:620` bağlantıları değişmeden çalışmaya devam eder.

#### Risk

**Yüksek — köprü sözleşmesi.** Azaltma: (a) eski sinyal hiç dokunulmadan kalır; (b) `context=None` varsayılanı
bütün mevcut çağrıları korur; (c) `tests/test_agy_bridge.py:117,580` ve `tests/test_provider_abstraction.py:205`
zaten eski sinyali doğruluyor — bunlar **değiştirilmeden** geçmeli, bu kendi başına bir regresyon kapısıdır.

---

### 2.2 — 10.2 Ajan başına adlandırılmış terminal

Bu, AgentSpace (ticari referans) ürününün 1 numaralı farklılaştırıcısı ve kullanıcının açıkça karar istediği madde.
İki seçenek somut ölçümle karşılaştırıldı.

#### Seçenek (a) — "Akış terminali" (mevcut `-p stream-json` çıktısını ajan başına bölme)

| Boyut | Değer |
|---|---|
| Yeni bağımlılık | **Yok** |
| Ek kota | **0** — aynı sürecin zaten okunan çıktısı |
| Sağlayıcı paritesi | **Tam** (10.1 agy'yi de kapsıyor) |
| Etkileşim | Salt okunur. Girdi = posta kutusu talimatı (§2.9) |
| Renk / biçim | Bizim ürettiğimiz basit sözdizimi (araç adı, düşünce, hata), TUI değil |
| PyInstaller riski | Yok |
| İş yükü | ~1 panel + tampon (10.1 tamamlandıysa) |

#### Seçenek (b) — Gerçek PTY (ConPTY / `pywinpty` + `pyte`)

| Boyut | Değer |
|---|---|
| Yeni bağımlılık | `pyte` (kurulu değil) + `pywinpty` (kurulu, 3.0.5 — ama `pyproject.toml`'da **yok**) |
| Ek kota | **İkinci bir CLI oturumu = ikinci bir konuşma.** Kartın `-p` koşusu zaten var; PTY oturumu onun **yerine** geçemez (akış-json yok), **yanına** eklenirse maliyet ikiye katlanır |
| Sağlayıcı paritesi | Kısmi — `claude` TUI çalışıyor (ölçüldü); `agy` için ayrı doğrulama gerekir |
| Etkileşim | Tam. Ama ilk ekran **güven diyaloğu** (ölçüldü) — programatik yanıt gerekir |
| Renk / biçim | Tam VT100. **`pyte` zorunlu**: kaçış dizileri çıkarıldığında metin `Accessingworkspace:` gibi bitişik çıkıyor |
| PyInstaller riski | `pywinpty` yerel uzantı + `conpty.dll`; `EntropyAI.spec`'e hidden import ve binary ekleme gerekir |
| İş yükü | VT ekran emülatörü + boyut senkronu + kapanış yönetimi; **kendi başına bir faz** |

#### AgentSpace (ticari referans) ve pixel-agents ne yapıyor?

- **AgentSpace (ticari referans):** ajan başına **adlandırılmış** terminal + sürüklenebilir bölme ağacı;
  sprite tıklaması ilgili bölmeyi öne getiriyor (Faz 9 raporu §1.2, §1.9).
- **pixel-agents (MIT, https://github.com/pixel-agents-hq/pixel-agents):** piksel ofis sahnesi + ajan durumu;
  gerçek PTY değil, süreç çıktısı görselleştirmesi. Görsel dil buradan alınıyor (kullanıcının kalıcı kuralı).
- **Google Antigravity Agent Manager:** ajanlar **Artifacts** üretiyor (görev listeleri, planlar, diff'ler,
  ekran görüntüleri, walkthrough'lar); kullanıcı bunlara Google Docs tarzı **yorum** bırakıyor.
  Yani ana yüzey terminal değil, **makbuz** (bkz. §2.9). Bu, (a) seçeneğini ayrıca destekliyor.

#### Öneri: **(a) akış terminali, Faz 10'da. PTY Faz 11+'a ertelenir.**

Gerekçe zinciri:
1. Kart koşuları **etkileşimsizdir** (`-p`, `--dangerously-skip-permissions`, `claude_bridge.py:634-680`).
   PTY'nin tek gerçek kazancı (klavye girdisi) kart modelinde **kullanılmıyor**.
2. Kullanıcının kimliği abonelik. İkinci bir etkileşimli oturum = ikinci bir kota kalemi;
   Faz 7'den beri korunan "tek üretici / ölçülen maliyet" kuralını (`harness._spend`, `harness.py:448-471`) kırar.
3. PTY çıktısı `pyte` olmadan okunamıyor — ölçümle gösterildi. `pyte` + `pywinpty` PyInstaller yüzeyini büyütüyor
   ve mevcut derleme riski (`EntropyAI.spec`) zaten dar.
4. (a) tamamlandığında (b)'ye geçiş **yıkıcı değil**: terminal panelinin arayüzü "anahtar → metin akışı"dır;
   kaynağı `agent_stream_chunk` yerine PTY okuyucusu yapmak panelin **içine** kalır.

#### Düzen kararı: döşeme ağacı değil, **sekme + bölme melezi**

Desk penceresi tek monitörde ekranın sağ **yarısı** (`window.py:48-52`, `DESK_SCREEN_RATIO = 0.5`),
varsayılan 1400×880, asgari 860×540. Orta sütunun asgarisi 240 px (`window.py:314-322` yorumları).
4 ajan yan yana bölme = ajan başına ~60 px → okunmaz. Bu yüzden:

```
Terminaller sekmesi
├── üstte: ajan şeridi (her koşan ajan bir "sekmecik": ad + durum noktası + token)
└── altta: QSplitter(Vertical) — en çok 2 görünür bölme (sabitlenmiş + odaklı)
```

- Varsayılan: **1 bölme** (odaklı ajan).
- Kullanıcı bir ajanı "sabitlerse" ikinci bölme açılır (en çok 2).
- Diğerleri şeritte kalır, tıklanınca odağa gelir.
- `scene.agent_clicked` (`scene.py:200`, `:695`) → bugün `window.py:480-484` Akış sekmesine geçiyor;
  Terminaller sekmesine yönlendirilir ve ilgili sekmecik öne gelir.
- Kapanan kartın tamponu **silinmez**, "arşiv" olarak şeritte soluk kalır (en çok `MAX_STREAM_KEYS`).

#### Kabul ölçütü

1. 3 ajan paralel koşarken şeritte 3 adlandırılmış sekmecik; her biri kendi çıktısını gösterir.
2. Bölme ayracı sürüklenerek boyutlanıyor; iki bölmede de metin okunur kalıyor (880 px yükseklikte).
3. Sprite tıklaması doğru sekmeciği öne getiriyor.
4. Biten kartın bölmesi arşivleniyor (içerik erişilebilir), silinmiyor.
5. Desk penceresi **tek ekrana sığmaya devam ediyor** (kullanıcının kalıcı kuralı).

---

### 2.3 — 10.3 Proje = depo + dal

#### Bugünkü durum (kanıt)

```python
# src/entropy/agents/desk_registry.py:118-126
@dataclass
class DeskProject:
    name: str
    office: str = ""
    goal: str = ""
    charter: str = ""
    path: Optional[Path] = None
```

`get_project` (`desk_registry.py:714-729`) ön bilgiyi `front.get(...)` ile okuyor,
`create_project` (`:731-742`) `{"name", "office", "goal"}` yazıyor. Panel formu üç alan sunuyor
(`projects_panel.py:44-79`: ad, hedef, kapsam). **Depo/dal kavramı hiçbir yerde yok.**

#### Önerilen tasarım

**A. Şema genişletme (geriye uyumlu).**

```python
@dataclass
class DeskProject:
    name: str
    office: str = ""
    goal: str = ""
    charter: str = ""
    path: Optional[Path] = None
    # Faz 10.3 — proje artık bir DEPO ve bir DAL demektir.
    repo_path: str = ""       # boş = depo bağlı değil (eski projeler böyle kalır)
    base_branch: str = ""      # boş = deponun HEAD'i
    worktree_root: str = ""    # boş = varsayılan kök (aşağıda)
```

Eski `PROJECT.md` dosyaları bu alanları taşımaz → `front.get(...)` boş döner → **kart yolu bugünküyle aynı**.
Bu, `desk_registry.py:417-467` (`DeskOffice._read`) içindeki geriye uyumlu ayrıştırma deseninin birebir tekrarıdır.

**B. Doğrulama (kayıt anında, model çağrısı yok).**

| Kontrol | Yöntem | Hata mesajı |
|---|---|---|
| Yol var mı | `Path(repo_path).is_dir()` | "Depo yolu bulunamadı" |
| Git deposu mu | `git -C <yol> rev-parse --show-toplevel` rc==0 | "Bu klasör bir git deposu değil" |
| Depo kökü mü | çıktı == normalize(`repo_path`) | "Alt klasör verildi; kök: `<X>`" |
| Dal var mı | `git -C <yol> rev-parse --verify <dal>` rc==0 | "`<dal>` dalı yok" |
| Kirli mi | `git -C <yol> status --porcelain` boş değilse **uyarı** (engel değil) | "Depoda kaydedilmemiş değişiklik var" |
| Worktree kökü uzunluğu | `len(kök) + 1 + len(kart_id) + 1 + <en derin göreli yol>` ≤ 240 | "Worktree kökü çok uzun (uzun yol desteği kapalı)" |

Son satırın sayısı ölçüme dayanıyor: bu depoda en derin göreli yol **99 karakter**
(`docs/reports/2026_Kapsamli_Otonom_Ajan_Mimarisi_…_Faz158.md`) ve `core.longpaths` kapalı.
358 karakterlik yol deneyi `Filename too long` ile öldü.

**C. Varsayılan worktree kökü.** `<repo_path>/../.entropy-worktrees/<ofis>/`

- Depo **dışında** → `git status` kirlenmez (deney: içerideki `.worktrees/` `?? .worktrees/` olarak göründü).
- Depoya komşu → yol kısa kalır (`C:\EntropiAI` için `C:\.entropy-worktrees\<ofis>\<kart-id>` ≈ 45 karakter,
  99 karakterlik en derin yolla toplam ≈ 145 < 240 ✓).
- Kullanıcı `worktree_root` ile ezebilir; ezerse yukarıdaki uzunluk kontrolü yine çalışır.

**D. Arayüz.** `ProjectEditDialog`'a (`projects_panel.py:38-79`) üç satır: "Depo yolu" (`QLineEdit` + "Gözat" düğmesi
→ `QFileDialog.getExistingDirectory`), "Taban dal" (`QComboBox`, editable; depo seçilince `git branch --format`
ile doldurulur), "Worktree kökü" (isteğe bağlı, boş = varsayılan).

#### Kabul ölçütü

1. Proje oluştururken depo yolu seçilebiliyor; geçersiz yol/dal **kaydedilmiyor** ve neden söyleniyor.
2. Alanları boş olan mevcut projeler **aynen** çalışmaya devam ediyor (`repo_path == ""` → worktree yolu hiç açılmaz).
3. Uzun yol uyarısı 240 karakter eşiğinde çıkıyor.

#### Risk: Düşük-orta. Şema genişletme; asıl risk 10.4'te.

---

### 2.4 — 10.4 Kart başına worktree

Faz 10'un **en riskli** maddesi. Kanıtlar §1.3'te.

#### Bugünkü durum (kanıt)

1. **Bütün alt kartlar aynı dizinde koşuyor.** `harness._pump` (`harness.py:971-1040`) her alt kartı
   `self.board.run(child.id, …, project_path=str(self._workdir()))` ile başlatıyor (`harness.py:1036-1039`).
   `_workdir()` ofisin tek çalışma dizini (`harness.py:283-289`).
2. **Bu yüzden yazma niyetli kartlarda paralellik fiilen 1.** `_pump` içinde:
   `if any(card_needs_write(c, …) for c in (running + backlog)): limit = 1` (`harness.py:988-991`).
   Gerekçe kodun kendi yorumunda: proje yazma kilidi tekildir ve ikinci kart 60 sn bekleyip ölür.
   **Worktree izolasyonunun asıl kazancı budur:** ayrı dizin = ayrı kilit = gerçek paralellik.
3. **Ölü tasarım:** `src/entropy/tools/autonomous_agent_architecture.py:138-163` (`AgentDesk` dataclass +
   `register`), `:668-703` (`spawn_worktree_desk`, `merge_desk_worktree`), `:1387-1397`
   (`allocate_worktree_for_task`). Depoda `src/` altında **başka hiçbir yerden çağrılmıyor**
   (grep: `worktree` yalnızca bu dosyada). Faz 9 raporunun "bağlanmamış ölü ada" tespiti doğrulandı.
   **Yeniden yazılmayacak; yalnızca sözleşmesi (kart→desk→dal üçlüsü) örnek alınacak.**
4. **Claude izole kipte cwd depo DIŞINDA.** `run_cwd` (`claude_bridge.py:1429-1446`):

   > Saf kipte NÖTR ve git deposunun DIŞINDA bir dizin (`%USERPROFILE%\.entropy\workspace`) …
   > Projeye dosya erişimi `--add-dir` ile verilir.

   Ölçüldü: `git -C %USERPROFILE%\.entropy\workspace rev-parse --show-toplevel`
   → `fatal: not a git repository`. `config.claude_isolated` **varsayılan `True`** (`config.py:283`).
   **Sonuç: bugünkü kipte bir kart `Bash` ile `git status` çalıştırsa git deposunda değildir.**
   Worktree kartları için bu **kırılma noktasıdır**.

#### Önerilen tasarım

**A. Kart alanı.** `TaskCard`'a tek alan (`tasks.py:97-137` desenine uygun):

```python
worktree: str = ""   # bu kartın izole çalışma ağacı; boş = ofisin _workdir()'i
```

Kart dosyası ön bilgisine yazılır (`TaskCard.to_frontmatter`, `tasks.py:139`); eski kartlarda yok → boş → eski davranış.

**B. Yaşam döngüsü — kim, ne zaman.**

| Aşama | Yer | Eylem |
|---|---|---|
| Alt kart başlarken | `harness._pump`, `to_start` döngüsü (`harness.py:1005+`) | Projede `repo_path` doluysa `ensure_worktree(card)` çağrılır; dönen yol `project_path` olarak `board.run`'a geçer ve karta yazılır |
| Kart biterken | `TaskBoard._finish` (`tasks.py:994`) sonrası | **Hiçbir şey.** Worktree ve dal **korunur** (kullanıcı diff'i ve PR'ı görebilsin) |
| Kart iptal/durdurulurken | `harness.stop` (`:1350`), `_terminate_children` (`:510`) | Süreç öldürülür, **temizlik hemen yapılmaz** (§C) |
| Kart silinirken | `TaskBoard.delete` (`tasks.py:563`) | `release_worktree(card)` çağrılır |
| Uygulama açılışında | `OfficeHarness.resume_all` (`harness.py:1365`) | `reconcile_worktrees()` — yetim worktree'ler saptanır ve şeritte gösterilir |

**C. Temizlik — deneyin dayattığı üç adım.**

Ölçüm (§1.3): dosya kilidi varken `worktree remove --force` **rc=255** verdi, kaydı sildi, **dizini bıraktı**,
`prune` kurtarmadı ve aynı yola yeniden `add` "already exists" ile öldü.

```
release_worktree(card):
  1. bridge.terminate_background_task(f"card-{card.id}")     # zaten var
  2. bekle: proc.poll() is not None  → +2 sn lütuf süresi     # tanıtıcılar kapansın
  3. rc = git worktree remove --force <yol>
     rc == 0 → git branch -D desk/<kart-id>  (worktree GERÇEKTEN gittiyse)
     rc != 0 → state.json'a  orphan_worktrees += [{"path", "branch", "card"}]
               ve KART BAŞARISIZ SAYILMAZ
  4. git worktree prune  (kayıt/dizin tutarsızlığını süpürür)
```

`reconcile_worktrees()` her açılışta `orphan_worktrees` listesini yeniden dener; hâlâ başarısızsa
Desk şeridinde "N yetim çalışma ağacı" uyarısı ve "Klasörü aç" düğmesi gösterir.
**Sessiz başarısızlık kabul edilmez** — deneyde tam olarak bu oluyordu.

**D. Dal adı ve yeniden koşma.** Dal `desk/<kart-id>`. Deney gösterdi ki aynı dal ikinci worktree'ye eklenemez.
Kart yeniden koştuğunda (`attempt` artışı, `harness.py` retry yolu) **aynı worktree yeniden kullanılır**;
yol yoksa ama dal varsa `git worktree add <yol> desk/<kart-id>` (`-b` **olmadan**) çağrılır.
Yol var ama kayıt yoksa (yetim durumu) → yeni yol `<kart-id>-<attempt>` olur.

**E. Ajanın gerçekten orada çalışması — iki zorunlu değişiklik.**

1. **İstemde açık beyan.** `TaskBoard.build_prompt` (`tasks.py:808-840`) bugün `project_file_section`
   (`tasks.py:765-806`) ile dosya listesi veriyor ama **çalışma dizinini söylemiyor**. Eklenecek blok:

   ```
   [ÇALIŞMA DİZİNİ]
   Bu görevin TEK çalışma dizini: <worktree mutlak yolu>
   Bu bir git worktree'sidir; dalı `desk/<kart-id>`, tabanı `<base_branch>`.
   Bütün okuma/yazma/komutlar bu dizinin İÇİNDE olacak. Başka bir depo yoluna
   yazma. Dal değiştirme, `git checkout`/`git switch` çalıştırma.
   ```

   `project_file_section`'ın kökü de worktree olur (zaten `project_path` parametresini alıyor),
   yani dosya haritası doğru ağacı gösterir. Nokta ile başlayan klasörler zaten atlanıyor
   (`tasks.py:786`), dolayısıyla `.git` dosyası gürültü yapmaz.

2. **`run_cwd` istisnası.** `claude_bridge.run_cwd` izole kipte nötr dizine düşüyor.
   Worktree'li kart için bu **yanlıştır**: ajanın `Bash` aracı git deposunda olmalı. Öneri —
   `run_cwd(project_dir, in_worktree: bool = False)`: `in_worktree` ise izolasyondan bağımsız olarak
   `project_dir` döner. Bu, izolasyonun asıl amacını (Claude'un *kullanıcının* deposunu proje sanması)
   bozmaz, çünkü worktree **kartın kendi** ağacıdır ve `--add-dir` zaten oraya işaret ediyor.

   > **Bu bir kullanıcı kararıdır** (bkz. §4, Karar 3): izolasyon kipinin tek istisnası açılıyor.

**F. Ofis paralelliği.** Worktree'li kartlarda `_pump`'ın `limit = 1` kısıtı kalkar: her kart ayrı dizinde,
ayrı kilitte. Koşul: `all(c.worktree for c in running + backlog)`. Karışık durumda (bazı kartlar worktree'siz)
eski davranış korunur — güvenli taraf.

#### Kabul ölçütü

1. İki yazma niyetli alt kart aynı depoda **aynı anda** koşuyor ve birbirinin dosyalarını görmüyor.
2. Her kartın dalı `desk/<kart-id>`; `git worktree list` iki ayrı satır gösteriyor.
3. Kart iptal edilince süreç ölüyor, worktree ve dal temizleniyor **veya** yetim olarak kaydedilip
   şeritte gösteriliyor — sessizce kaybolmuyor.
4. Kilitli dosya senaryosunda kart **başarısız olmuyor**, yalnızca temizlik erteleniyor.
5. Uzun yol eşiği aşılırsa worktree hiç açılmıyor, kart ofis `_workdir()`'inde eski yolla koşuyor
   ve notuna neden yazılıyor.

#### Risk: **Yüksek.** Azaltmalar yukarıda; ek olarak:

- Worktree açma **başarısız olursa kart ölmez**, eski tek-dizin yoluna düşer (özellik geri sarılabilir olmalı).
- `repo_path` boş projede kod yolu **hiç** çalışmaz — özellik opt-in.
- Disk %98 dolu (§1.2): `ensure_worktree` öncesi boş alan kontrolü (< 2 GB ise uyar, açma).

---

### 2.5 — 10.5 PR akışı

#### Bugünkü durum (kanıt)

- `gh` **yok** (§1.1). `gh auth status` çalıştırılamadı (komut yok) — bu yüzden gizli bilgi kopyalama sorunu doğmadı.
- Uzak depo **var**: `origin https://github.com/BFBulut/entropyAI.git`.
- Kartın `review` durağı var (`tasks.py:70` `STATUSES`), üst kart `_finalize`'da `review`'a düşüyor
  (`harness.py:1207-1217`) ama karşılığı bir dal/PR değil, insan okuması.

#### Önerilen tasarım — **yedek yol birincil**

Faz 9 tablosu "gh yoksa dal + diff özeti yedeği" diyor. Ölçüm gösteriyor ki bugün **yedek yol tek yoldur**.
Bu yüzden mimari tersine kurulur: **her zaman yerel özet üretilir; `gh` varsa üstüne PR eklenir.**

```
on_card_review(card):
    if not card.worktree: return                      # worktree yoksa PR kavramı yok
    stat  = git -C <wt> diff --stat <base>...HEAD
    files = git -C <wt> diff --numstat <base>...HEAD
    rapora [DEĞİŞİKLİKLER] bölümü yazılır (her zaman)
    card.notes += "Dal: desk/<id> · N dosya, +X/-Y satır"

    if gh_available() and remote_exists():
        git -C <wt> push -u origin desk/<id>          # KULLANICI ONAYIYLA
        url = gh pr create --draft --base <base> --head desk/<id> \
                           --title "<kart başlığı>" --body-file <gövde>
        card.pr_url = url  (ön bilgiye)
    # gh yoksa: hiçbir hata YOK, kart yine review'a geçer
```

**`gh` varlık testi:** `shutil.which("gh")` + `gh auth status` rc==0. **Çıktı asla loglanmaz/gösterilmez**
(jeton ipucu içerebilir); yalnızca `rc` okunur. Bu, kullanıcının "gizli bilgi kopyalama" uyarısının karşılığıdır.

**`push` neden onaylı:** uzak depoya yazma, kullanıcının deposunda görünür bir yan etki.
Şeritte tek düğme: "Dalı gönder ve taslak PR aç". Otomatik push **yok**.

**Taslak PR gövdesi şablonu** (`--body-file` ile geçilir; argv sınırı sorunu doğmasın —
`claude_bridge.py:879` `enforce_argv_limit` deneyimiyle aynı gerekçe):

```markdown
## Ne yapıldı
<üst kartın hedefi>

## Kart
- Kart: `<kart-id>` — <başlık>
- Ofis: `<ofis>`
- Proje: `<proje>` (`<repo_path>` @ `<base_branch>`)
- Alt görevler: <N> · ortalama not: <avg>

## Alt kart çıktıları
| Alt kart | Ajan | Sağlayıcı | Durum | Not |
|---|---|---|---|---|
| … | … | … | … | … |

## Kabul ölçütleri
- [ ] <ölçüt 1>
- [ ] <ölçüt 2>

## Rapor
`Entropy/Desk/Offices/<ofis>/reports/<kart-id>.md`

## Maliyet
<harcanan> / <bütçe> token · <sağlayıcı>

---
Entropy Agent Desk tarafından üretildi. **Taslak** — insan incelemesi bekliyor.
```

#### Kabul ölçütü

1. `gh` kurulu **değilken**: kart `review`'a geçiyor, raporda `[DEĞİŞİKLİKLER]` bölümü var, kart **başarısız değil**.
2. `gh` kuruluyken ve kullanıcı onaylayınca: PR bağlantısı kartın ön bilgisinde ve raporda görünüyor.
3. `gh auth status` çıktısı **hiçbir yere** yazılmıyor (test: log yakalayıcı boş).
4. Uzak deposu olmayan bir yerel depoda push adımı hiç denenmiyor, yalnızca dal + özet üretiliyor.

#### Risk: Orta. Dış araç + kullanıcı kimliği. Yedek yol zorunlu ve **birincil** olduğu için kart hiçbir senaryoda ölmez.

---

### 2.6 — 10.6 Diff paneli

#### Bugünkü durum (kanıt)

- `BoardPanel.card_selected = Signal(str)` var (`board_panel.py:22`) ve `TaskBoardWidget`'tan besleniyor (`:32`),
  ama `window.py` içinde **hiçbir yere bağlı değil** (grep: `card_selected` yalnızca `board_panel.py`'de).
  Yani panel kancası hazır, kullanılmıyor.
- Desk sekmeleri: Kartlar / Akış / Projeler / Bellek (`window.py:292-295`, sabitler `:60-63`).
- `Pygments 2.19.2` kurulu ama `pyproject.toml`'da **yok** (yorumda bilinçli çıkarıldığı yazıyor).
- `QWebEngineView` projede kullanılıyor (`ui/widgets/knowledge_graph.py:13`).

#### Önerilen tasarım

**Yeni sekme "Değişiklikler" (TAB_DIFF = 4).** İki bölmeli:

```
üst   : QTreeWidget  — dosya | +  | −     (git diff --numstat kaynağı)
alt   : QPlainTextEdit (salt okunur, monospace) + DiffHighlighter
```

**Veri yolu (model çağrısı yok, hepsi `git`):**

| Amaç | Komut |
|---|---|
| Özet | `git -C <wt> diff --numstat <base>...HEAD` **+** `git -C <wt> diff --numstat` (kaydedilmemiş) |
| Dosya diff'i | `git -C <wt> diff <base>...HEAD -- <yol>` (tembel: yalnızca tıklanınca) |
| Yeni dosyalar | `git -C <wt> status --porcelain` → `??` satırları ayrı grup |

**Neden QWebEngine değil:** ikinci bir web görünümü Desk'in başlangıç maliyetini ve bellek ayak izini büyütür;
bilgi grafı zaten bir `QWebEngineView` taşıyor. Diff renklendirmesi 4 kurallık bir `QSyntaxHighlighter` işi:
`+` yeşil, `-` kırmızı, `@@` mavi, `diff --git`/`index` soluk. Pygments'a bile gerek yok
(ve `pyproject.toml`'a geri eklemek istemiyoruz).

**Tembel yükleme ve tavan:** dosya diff'i **yalnızca tıklanınca** okunur; 2.000 satırdan uzun diff kırpılır ve
"… (N satır daha; dosyayı aç)" satırı basılır. `git diff` çağrıları `QThreadPool` üzerinde koşar
(büyük depoda ana iş parçacığını kilitlemesin).

**Bağlantı:** `window._init_ui` içinde `self.board_panel.card_selected.connect(self._on_card_selected)`;
slot seçili kartın `worktree` alanını okur, boşsa panel "Bu kart bir depoya bağlı değil" der.

#### Kabul ölçütü

1. Kart seçilince değişen dosya listesi ve +/− satır sayıları görünüyor.
2. Dosyaya tıklayınca renkli diff açılıyor; ikinci tıklama önbellekten geliyor.
3. Worktree'siz kartta panel boş ama **çökmüyor**, açıklama gösteriyor.
4. 500+ dosyalık bir diff'te arayüz donmuyor (ölçüm: ilk boya < 300 ms).

#### Risk: Düşük-orta (performans). `pyproject.toml`'a yeni bağımlılık **eklenmiyor**.

---

### 2.7 — 10.7 Maliyet / kota şeridi

#### Bugünkü durum (kanıt) — düşünülenden **daha ileride**

- Desk üst şeridinde harcama rozeti **zaten var ve çalışıyor**: `window.py:388-406`
  (`⛽ <harcanan> token / <bütçe> · <N> çalışan`), veri `office_spend()` (`window.py:66-90`) →
  `mailbox.office_status()` (`mailbox.py:598-664`).
- Sağlayıcı kimlik rozeti **zaten var**: `ProviderStatusBadge` (`window.py:222-229`, widget `ui/widgets/provider_badge.py`),
  alanlar `logged_in, plan, quota_hint, session_window, last_error, account_hint`.
- `office_status` sözleşmesi kart başına veriyi **zaten dönüyor** (`mailbox.py:628-636`):
  `{"id","title","status","phase","tokens","budget","children"}`.
- Claude token kalemleri: `usage_badge_fields()` (`claude_bridge.py:1162-1176`) →
  `{session, turn, cache_read, cost_weighted}`; `last_total_cost_usd` (`:345`, `:1210`).
- İki köprünün ortak sözleşmesi: `ProviderCommonMixin.usage_breakdown()` (`core/provider.py:498`).
- `/desk` metni aynı veriyi basıyor (`slash_commands.py:786-802`) — tek üretici kuralı korunmuş.

**Yani 10.7 sıfırdan bir iş değil; eksik olan üç şey:**
1. Kart başına satır (bugün yalnızca ofis toplamı görünüyor).
2. Şeritte sağlayıcı + oturum penceresi ipucunun harcamayla **aynı yerde** olması.
3. Worktree/disk uyarısı için yer (10.4'ün çıktısı).

#### Önerilen tasarım

Şerit tek satır, sağa hizalı, sola doğru öncelik sırası:

```
⛽ 84.320 / 120.000 token   ·   2 çalışan   ·   [kart: alt-3  18.4k/30k ⏳]   ·   Claude ✓ · 5h pencere   ·   ⚠ 1 yetim ağaç
```

| Bölüm | Kaynak | Notlar |
|---|---|---|
| Ofis toplamı | `office_status()["spent_tokens"]`, `["budget_tokens"]` | Bugünkü rozet |
| Çalışan sayısı | `len(office_status()["running"])` | Bugünkü rozet |
| Koşan kart | `running[i]` → `tokens/budget` | **Yeni.** Birden çok kart varsa en pahalı olan gösterilir; ipucunda hepsi |
| Sağlayıcı | `ProviderStatusBadge` (mevcut) | Şeride taşınır, ayrı satır olmaz |
| Oturum penceresi | `provider_status["session_window"]` | Zaten toplanıyor |
| Yetim ağaç | 10.4 `state.json["orphan_worktrees"]` | Yalnızca > 0 iken görünür |

**Yüzdelik kota çubuğu YOK.** Karar korunuyor: `identity.py:167-171` motorların kalan kotayı yayımlamadığını
belgeliyor; AgentSpace (ticari referans) de aynı kararı vermiş (Faz 9 §1.4). Uydurma bir yüzde yanlış güven verir.

**Tek üretici kuralı.** Şerit **kendi hesabını yapmaz**; `office_status()` genişletilir
(`spent_tokens` yanına `cost_weighted`, `provider`, `orphan_worktrees` eklenir) ve `/desk` metni de
aynı alanları basar. Test: `/desk` çıktısındaki sayılarla şeritteki sayılar **birebir** eşit.

**Not — `--max-budget-usd`:** `claude --help` bu bayrağı belgeliyor (yalnızca `--print` ile).
Bugünkü token bütçesi (`harness._budget`, `harness.py:415-422`) *token* tabanlı ve iki sağlayıcıda ortak.
Dolar bayrağı Claude'a özgü olduğu için **Faz 10'da kullanılmaz**; §4'te kullanıcıya "ikinci bir tavan olarak
eklensin mi" diye sorulur.

#### Kabul ölçütü

1. Şeritte ofis toplamı, koşan kart başına `harcanan/bütçe`, sağlayıcı ve oturum penceresi görünüyor.
2. Sayılar `/desk` metniyle **birebir** aynı (otomatik test).
3. Hiçbir yerde yüzdelik kota çubuğu yok.
4. Veri yoksa şerit **gizleniyor** (bugünkü `setVisible(False)` davranışı korunuyor).

#### Risk: Düşük.

---

### 2.8 — 10.8 Orkestratör gerçek araştırma döngüsü

#### Bugünkü durum (kanıt) — teşhis Faz 9'dakinden **farklı**

Faz 9 raporu "orkestratörün kendisine gerçek bir arama aracı verilmiyor" diyor. Ölçüm bunu **düzeltiyor**:

```python
# src/entropy/agents/desk_registry.py:659-681 (orchestrator_spec)
tools_policy="read-only",
# → compile.py:143
"read-only": "Read, Glob, Grep, WebFetch, WebSearch",
```

Orkestratörün derlenmiş tanımında **WebSearch ve WebFetch zaten var**. Ayrıca Claude yolunda
`--tools` listesi `tools_for("accept-edits", needs_write=False)` ile kuruluyor
(`claude_bridge.py:1873`) ve `CARD_TOOLS_BY_MODE["acceptEdits"]` = `CHAT_TOOLS_READONLY + CHAT_TOOLS_WRITE`
(`claude_bridge.py:153-165`), yani `WebFetch, WebSearch` argv'de **de** var.

**Gerçek hata `_can_web_search()`'te ve yanlış yerde bakıyor:**

```python
# src/entropy/agents/harness.py:661-672
def _can_web_search(self) -> bool:
    """Kadroda web araması yapabilen (read-only / full) bir ajan var mı?"""
    for name in office.members or []:          # ← ORKESTRATÖR BURADA YOK
        ...
```

`office.members` orkestratörü **dışlıyor** — `DeskRegistry._read` üye listesini kurarken
`if agent.name == spec.orchestrator or role == ORCHESTRATOR_ROLE: continue` diyor (`desk_registry.py:465`).
Sonuç: **yeni açılmış, henüz alt ajanı olmayan bir ofiste `_can_web_search()` her zaman `False` döner** ve
`build_plan_prompt` `[ARAŞTIRMA NOTU]` bloğunu ile `research_notes` şemasını hiç eklemez
(`harness.py:759-773`). Orkestratör arama aracına sahiptir ama **istem ondan asla araştırma istemez.**

İkinci sorun: blok eklendiğinde bile kaynak istemiyor. Bugünkü şema
(`harness.py:770-772`): `"research_notes": [{"title": "...", "body": "..."}]` — **`source` alanı yok**.
Model bunu kendi belleğinden doldurabilir ve doldurduğu ayırt edilemez.

#### Önerilen tasarım

**A. Kontrolü doğru yere taşı.**

```python
def _can_web_search(self) -> bool:
    """Bu ofiste ARAMA ARACI var mı? Önce orkestratörün kendi tanımına bakılır."""
    office = self.office
    if office is None:
        return False
    names = [office.orchestrator or ORCHESTRATOR_AGENT, *(office.members or [])]
    for name in names:
        spec = self.registry.get(name)
        if spec is None:
            continue
        if _policy_has_web(spec.tools_policy):       # read-only | readonly | full
            return True
    return False
```

`_policy_has_web` `compile._TOOLS_BY_POLICY` (`compile.py:142-147`) üzerinden türetilir; iki yerde ayrı
sabit listesi tutmayız — politika→araç eşlemesi **tek kaynaktan** okunur.

**B. Kaynak zorunluluğu.** Şema:

```json
"research_notes": [{"title": "...", "body": "...", "source": "https://… veya dosya:satır"}]
```

İstem metni: *"Her `research_notes` maddesi bir `source` taşımak zorundadır. Kaynağını gösteremediğin bir
maddeyi hiç yazma. Kendi belleğinden yazdığın bir madde varsa `source: bellek` yaz."*

`_write_research_notes` (`harness.py:674-711`) `source` alanını okur ve grafa
`graph.add_note(kind="bulgu", …, source=f"plan:{card.id}")` yerine
`source=<gerçek kaynak>` + `origin=f"plan:{card.id}"` olarak yazar. `source` boşsa **not yazılmaz**
(bugün başlık varsa yazıyor) — bu, "taze veriden yazıldı" kabul ölçütünün yaptırımıdır.

**C. Araç yasağı bozulmuyor.** `orchestrator_produced_code` (`harness.py:182-191`) kontrolü aynen kalır.
Arama **okumadır**, yazma değil; `tools_policy` `read-only` olarak kalır ve `_TOOLS_BY_POLICY["read-only"]`
`Edit/Write/Bash` içermez. `_on_plan`'daki kod-üretti yaptırımı (`harness.py:869-880`) dokunulmaz.

**D. agy paritesi.** agy'nin `--tools` bayrağı yok; kontrol ajan tanımındaki kurallara dayanıyor
(`compile.render_agy_agent`, `compile.py:170+`). agy için araştırma bloğu yine eklenir ama
istem "araç yoksa `source: bellek` yaz" diyeceği için sonuç dürüst kalır.

#### Kabul ölçütü

1. Yeni açılmış, alt ajansız bir ofiste `_can_web_search()` **True** dönüyor (orkestratör `read-only`).
2. Aynı kart iki kez planlandığında ikinci planın `research_notes`'u birinciden farklı ve
   en az bir madde **kaynak bağlantısı** içeriyor.
3. `source`suz madde **grafa yazılmıyor**.
4. Orkestratörün kod üretme yasağı testi (`test_architecture_rules.py`) **değişmeden** geçiyor.

#### Risk: Orta. Arama gecikmesi planlama süresini uzatır; kota +3–8k/plan.
`_can_web_search()` doğru dönmeye başlayınca **her** planlama araştırma yapmaya çalışır —
bu yüzden blok metni "en çok 3 arama" tavanını açıkça yazmalı (istemdeki `COST_DISCIPLINE` deseni, `tasks.py:86`).

---

### 2.9 — 10.9 Makbuz (artifact) görünümü + koşan karta yorum

#### Antigravity deseni (referans)

Google Antigravity Agent Manager'da ajanlar **Artifacts** üretir: görev listeleri, uygulama planları, kod diff'leri,
ekran görüntüleri, tarayıcı kayıtları, walkthrough'lar, test sonuçları. Kullanıcı bunlara Google Docs tarzı
**yorum** bırakır; ajan geri bildirimi okur ve **durmadan** yineler. Walkthrough iş bitince üretilen özet sayfadır.
Bizim karşılığımız: **plan + alt kart çıktıları + değerlendirme + diff + PR = tek makbuz sayfası.**

#### Depolama kararı: **ayrı `receipts/` klasörü AÇILMAZ**

Gerekçe: `harness._finalize` (`harness.py:1174-1241`) zaten tam bu içeriği üretiyor —
alt kart başlıkları, ajan, durum, not, verdict, özet, `output_paths` — ve iki yere yazıyor:
`Offices/<ofis>/reports/<kart-id>.md` (`_write_local_report`, `harness.py:1244-1248`) ve wiki sayfası
(`_write_office_report`, `:1274`). Ayrıca kartın kendi `summary` alanına kayıpsız kopyalanıyor (`:1215`).

Üçüncü bir klasör = üçüncü bir gerçek kaynak. Faz 9'un P0-2 dersi (kart deposu ikiye bölünmüştü) tam olarak buydu.

**Karar:** `Offices/<ofis>/reports/<kart-id>.md` **makbuzun kendisidir**. Faz 10'da yapılacak olan:
1. `_finalize`'ın yazdığı gövdeye **plan** ve **diff/PR** bölümlerini eklemek (bugün yalnızca alt kart çıktıları var).
2. Bu dosyayı **okuyan** bir panel yazmak (Desk'te "Makbuz", ya da Kartlar sekmesinin detay bölmesinde bir düğme).
3. Rapor **koşu sırasında da** artımlı yazılmak zorunda (bugün yalnızca `_finalize`'da yazılıyor) —
   `_on_plan` sonrası ve her `_on_child_done` sonrası bir kez güncellenir ki kullanıcı koşarken okuyabilsin.

Makbuz iskeleti:

```markdown
# <kart başlığı>
Ofis: <ofis> · Proje: <proje> · Dal: `desk/<id>` · Durum: <phase>

## Plan            ← _on_plan'daki JSON'un okunur hâli (alt görev tablosu)
## İlerleme        ← alt kart başına: ajan, durum, not, özet (artımlı)
## Değerlendirme   ← _on_grades çıktısı
## Değişiklikler   ← git diff --numstat (10.6 ile aynı kaynak)
## PR              ← 10.5 bağlantısı ya da "PR açılmadı (gh yok)"
## Maliyet         ← _card_state tokens / budget
## Yorumlar        ← posta kutusundaki instruction mesajları (aşağıda)
```

#### Koşan karta yorum — enjeksiyon noktası (asıl teknik iş)

Bugünkü akış (kanıt):
- `instruct_office(office, instruction, task_id="")` (`mailbox.py:436-461`) `task_id` **alıyor** ama kimse dolu geçmiyor.
- Harness talimatları **yalnızca planlamada** okuyor: `build_plan_prompt` içinde
  `pending_instructions(self.office_name, …)` → `instructions_section(...)` (`harness.py:721-727`).
- Alt kart istemi `TaskBoard.build_prompt` (`tasks.py:808-840`) — posta kutusundan **hiç haberi yok**.

Öneri:

1. **Yorum kutuya `task_id=<üst kart id>` ile düşer.** Makbuz panelindeki yorum kutusu
   `instruct_office(office, text, task_id=card.id)` çağırır. Model çağrılmaz, kota harcanmaz —
   `/desk msg` ve Desk talimat kutusuyla aynı fonksiyon (Faz 9.3'te kurulan tek yüzey kuralı korunur).

2. **`_pump`, alt kartı başlatmadan ÖNCE o üst karta ait okunmamış talimatları okur** ve
   `board.run(..., extra_context=...)` ile geçirir. Yeni bir isteğe bağlı parametre:

   ```python
   # tasks.py: TaskBoard.run(..., extra_context: str = "")
   # tasks.py: TaskBoard.build_prompt(..., extra_context: str = "")
   #   → "[KULLANICI YORUMU — koşu sırasında bırakıldı]\n<metin>"  bloğu
   ```

3. **Yalnızca HENÜZ BAŞLAMAMIŞ alt kartlara uygulanır.** `_pump`'ın `to_start` listesi zaten
   tam olarak "başlamak üzere olanlar"dır (`harness.py:1001-1003`); enjeksiyon oraya girer.
   Koşan bir sürecin istemi **değiştirilmez** — süreç kesilmez, kart durmaz.

4. **Sıradaki planlama da görür.** `pending_instructions(mark=True)` okuduğunu işaretlediği için
   aynı yorum iki kez enjekte edilmez. Ama alt kart yolunda `mark=False` ile okuyup, **alt kart
   gerçekten başlatıldıktan sonra** işaretlemek gerekir (aksi hâlde bütçe yetmediği için başlamayan
   bir kart yorumu yutar).

5. **Görünürlük.** Makbuzun "Yorumlar" bölümü kutudaki `instruction` mesajlarını (okunmuş dahil)
   zaman damgasıyla listeler — kullanıcı yorumunun nereye gittiğini görür.

#### Kabul ölçütü

1. Koşan bir karta makbuz üzerinden yorum bırakıldığında **kart durmuyor**, süren alt kart kesilmiyor.
2. Bir sonraki alt kartın isteminde `[KULLANICI YORUMU]` bloğu görünüyor (test: `build_prompt` çıktısı).
3. Aynı yorum ikinci alt karta **tekrar** enjekte edilmiyor.
4. Makbuz sayfası koşu sırasında güncelleniyor (plan → ilerleme → değerlendirme).
5. Yeni bir depo/klasör açılmıyor; makbuz `reports/<kart-id>.md`.

#### Risk: Orta. Akış ortasında istem değişimi. Azaltma: enjeksiyon yalnızca `to_start` kümesine, kilit altında.

---

### 2.10 — 10.10 Ekip şablonları

#### Bugünkü durum (kanıt)

- Ofis boş kadroyla doğuyor: `ensure_orchestrator` (`desk_registry.py:685-696`) yalnızca orkestratörü yazıyor
  (kullanıcının kalıcı kuralı: *"Ofisi oluşturduğum anda … orkestratör ajanı oluşsun"* — bu korunacak).
- Şablon kavramı **yok**: `grep -rn "template" src/entropy/agents/ src/entropy/desk/` → 0 eşleşme.
- Ofis formu (`offices_panel.py:87-170`) 9 alan sunuyor; kadro seçimi var ama **var olan** ajanlardan seçiyor
  (`all_agent_names(agent_registry)`), yeni ajan üretmiyor.
- Alt ajan üretme mekanizması **hazır**: `_apply_new_agents` (`harness.py:813-861`) — var olan adı ezmiyor,
  orkestratör rolünü reddediyor, sağlayıcıyı doğruluyor. Şablon uygulaması aynı yoldan geçmeli.

#### Önerilen tasarım

**A. Dosya biçimi.** `Entropy/Desk/Templates/<şablon-adı>/`:

```
Templates/
  arastirma/
    OFFICE.md          # ön bilgi: purpose, default_provider, max_parallel, budget_tokens; gövde = tüzük
    agents/
      arastirmaci.md   # AgentSpec ön bilgisi (registry._read ile aynı ayrıştırıcı)
      analist.md
      yazar.md
  refaktor/ …
  qa/ …
  medya/ …
```

Ayrıştırıcı **yeniden yazılmaz**: `OFFICE.md` için `DeskRegistry._read` (`desk_registry.py:417`),
ajanlar için `AgentSpec` ayrıştırıcısı (`desk_registry.py:222`) aynen kullanılır.
Şablon = "adı olmayan bir ofis klasörü".

**B. Kasada şablon yoksa koda gömülü varsayılanlar.** İlk kurulumda `Templates/` boştur; dört şablon
Python sabiti olarak (`desk_registry.TEMPLATES`) taşınır ve ilk kullanımda kasaya **yazılır**
(kullanıcı düzenleyebilsin). Bu, tohum ofis yasağını ihlal etmez: **ofis** yaratılmıyor, yalnızca
kullanıcı bir şablon seçince o şablonun kadrosu kurulan ofise uygulanıyor.

**C. Dört şablonun kadrosu.** (Orkestratör her ofiste otomatik; aşağıdakiler onun **yanına** gelir.)

| Şablon | Alt ajanlar (rol · `tools_policy`) | Sağlayıcı önerisi | Not |
|---|---|---|---|
| **Araştırma** | `arastirmaci` (worker · `read-only`), `analist` (worker · `read-only`), `yazar` (worker · `read-write`), `degerlendirici` (evaluator · `read-only`) | `config.provider` | Yazma yalnızca `yazar`da → paralellik gerçek (paylaşımlı okuma kilidi) |
| **Refaktör** | `mimar` (worker · `read-only`), `uygulayici` (worker · `read-write`), `test-yazari` (worker · `read-write`), `degerlendirici` (evaluator · `read-only`) | `config.provider` | 10.4 worktree ile iki yazıcı gerçekten paralel |
| **QA** | `regresyon-avcisi` (worker · `read-write`), `test-yazari` (worker · `read-write`), `derleyici` (worker · `full`), `degerlendirici` (evaluator · `read-only`) | `config.provider` | `full` yalnızca derleyicide (Bash gerekiyor) |
| **Medya** | `arastirmaci` (worker · `read-only`), `senarist` (worker · `read-write`), `gorsel-yonetmen` (worker · `read-write`), `degerlendirici` (evaluator · `read-only`) | `config.provider` | Mevcut `skills/` medya yetenekleriyle eşleşir |

**Sağlayıcı ve model bilerek `config.provider`'dan türetilir** — Faz 9.5'in "agy sabiti kalmasın" kararı
(`desk_registry.py:89-91` şeması artık `<o ajanın sağlayıcısı>` diyor) şablonlarda geri gelmemeli.
Şablon dosyaları `provider:` alanını **boş** bırakır; `create_office` sırasında ofisin
`default_provider`'ı doldurur.

**D. Arayüz.** `OfficeEditDialog`'a (`offices_panel.py:87`) ilk satır olarak:
`Şablon: [ (boş — yalnızca orkestratör) | Araştırma | Refaktör | QA | Medya ]`.
Şablon seçilince Amaç/Tüzük/Paralellik/Bütçe alanları **önerilen** değerlerle doldurulur (kullanıcı ezebilir),
"Üyeler" listesi salt-okunur bir önizlemeye döner. Kaydedildiğinde:
`create_office(...)` → `ensure_orchestrator(...)` → `apply_template(office, tpl)` (= `_apply_new_agents` yolu).

**E. Var olan adı ezmeme kuralı korunur.** `apply_template` `agents.get(name) is not None` ise atlar —
`_apply_new_agents`'ın (`harness.py:832`) davranışının birebir aynısı.

#### Kabul ölçütü

1. Şablon seçilerek açılan ofisin kadrosunda orkestratör + 3–4 ajan var, roller atanmış.
2. İlk kart **ek düzenleme olmadan** koşuyor (duman testi: `/desk task <ofis> …` planlıyor ve en az bir alt kart bitiriyor).
3. `config.provider = "claude"` iken şablon **agy** ajanı üretmiyor.
4. Aynı şablon iki kez uygulanınca ajanlar **çoğalmıyor** ve elle düzenlenmiş istemler **ezilmiyor**.
5. Tohum **ofis** hâlâ yok; şablon yalnızca kullanıcı bir ofis oluştururken uygulanıyor.

#### Risk: Düşük.

---

## 3. İş listesi — sıralama, ajan, kabul, risk, kota

Faz 10 içinde beş alt dilim önerilir. Her dilim sonunda rapor + onay (orkestratör kipi kuralı).

### Dilim 10-A — Temel (kota ~20-30k)

| # | İş | Ajan | Bağımlılık | Kabul | Risk | Kota |
|---|---|---|---|---|---|---|
| 10.1 | `agent_stream_chunk(dict)` + `consume_stream(context=…)` + agy arka plan akışı + `StreamPanel` çok tamponlu | agy | — | §2.1 | **Yüksek** (köprü sözleşmesi) | 20-30k (2 paralel kart) |
| 10.3 | `DeskProject`: `repo_path`/`base_branch`/`worktree_root` + doğrulama + form | agy | — | §2.3 | Düşük-orta | **0** |
| 10.7 | Maliyet şeridi: kart satırı + sağlayıcı/oturum + `office_status` alan genişletme | ui + agy | — | §2.7 | Düşük | **0** |

### Dilim 10-B — İzolasyon (kota ~20-30k)

| # | İş | Ajan | Bağımlılık | Kabul | Risk | Kota |
|---|---|---|---|---|---|---|
| 10.4 | Kart başına worktree: `TaskCard.worktree`, `ensure/release/reconcile`, `[ÇALIŞMA DİZİNİ]` bloğu, `run_cwd` istisnası, `_pump` paralellik kısıtının kalkması | agy | 10.3 | §2.4 | **Yüksek** | 20-30k (2 paralel yazma kartı) |
| 10.2 | Terminaller sekmesi: ajan şeridi + en çok 2 bölme, sprite bağlantısı, arşiv | ui | 10.1 | §2.2 | Orta | **0** (10.1 koşusu yeniden kullanılır) |

### Dilim 10-C — İnceleme (kota 0)

| # | İş | Ajan | Bağımlılık | Kabul | Risk | Kota |
|---|---|---|---|---|---|---|
| 10.6 | "Değişiklikler" sekmesi: `--numstat` ağacı + tembel dosya diff'i + `DiffHighlighter`; `card_selected` bağlantısı | ui | 10.4 | §2.6 | Düşük-orta | **0** |
| 10.5 | Yerel özet (her zaman) + `gh` varsa onaylı push & taslak PR; `gh auth status` çıktısı loglanmaz | agy | 10.4 | §2.5 | Orta | **0** |

### Dilim 10-D — Akıl ve kadro (kota ~30-45k)

| # | İş | Ajan | Bağımlılık | Kabul | Risk | Kota |
|---|---|---|---|---|---|---|
| 10.8 | `_can_web_search()` orkestratöre bakar; `research_notes`'a zorunlu `source`; kaynaksız not grafa yazılmaz | agy + mem | — | §2.8 | Orta | +3-8k/plan, doğrulama ~10-16k |
| 10.9 | Makbuz = `reports/<kart>.md` (artımlı) + okuyucu panel + `instruct_office(task_id=…)` yorumu → `build_prompt(extra_context)` | ui + agy | 10.6 | §2.9 | Orta | ~10k |
| 10.10 | 4 şablon (`Entropy/Desk/Templates/…` + koda gömülü varsayılan) + ofis diyaloğunda seçim | agy | — | §2.10 | Düşük | ~20k (4×5k duman testi) |

### Dilim 10-E — Doğrulama (kota 0)

| # | İş | Ajan | Kabul | Risk | Kota |
|---|---|---|---|---|---|
| 10.11 | Tam paket yeşil; yeni testler: iki tamponlu akış, iki paralel worktree, kilitli worktree temizliği, `gh` yokken kart `review`'a geçiyor, `/desk` ↔ şerit sayı eşitliği, şablon idempotansı; `dist_check` derleme + smoke | qa | — | Düşük | **0** |

**Toplam: ~85–115k token.** (10.1: 25k, 10.4: 25k, 10.8: 16k, 10.9: 10k, 10.10: 20k, diğerleri 0.)
Bir ofisin varsayılan bütçesi 120k (`desk_registry.py:71` `DEFAULT_BUDGET_TOKENS = 120000`),
yani Faz 10'un tüm doğrulama koşuları **tek bir ofis bütçesine** sığar.

### Riskler ve geri dönüş yolları

| Risk | Olasılık | Geri dönüş yolu |
|---|---|---|
| 10.1 köprü sözleşmesi kırılması | Orta | Eski sinyal dokunulmadı; `context=None` varsayılanı. Geri alma = yeni sinyal emitlerini kaldırmak (5 satır). |
| 10.4 yetim worktree birikmesi | **Yüksek** (ölçüldü) | `state.json["orphan_worktrees"]` + açılışta uzlaştırma + şerit uyarısı. Son çare: proje `repo_path`'i boşalt → özellik tamamen kapanır. |
| 10.4 ajan yanlış ağaçta çalışır | Orta | `[ÇALIŞMA DİZİNİ]` bloğu + `run_cwd` istisnası + `project_file_section` kökü worktree. QA testi: kartın yazdığı dosya **yalnızca** worktree'de görünmeli. |
| 10.4 disk dolması (%98) | Orta | `ensure_worktree` öncesi < 2 GB kontrolü; yetersizse worktree açılmaz, kart eski yolla koşar. |
| 10.5 `gh` kimlik doğrulaması | Yüksek | Yedek yol birincil; `gh` hiç kurulmasa da Faz 10 çıkış ölçütü karşılanır (PR bağlantısı yerine dal + diff özeti). |
| 10.8 arama kotası patlaması | Orta | İstemde "en çok 3 arama" tavanı; `_spend` zaten planlama maliyetini ledger'dan okuyor (`harness.py:864`). |
| 10.2 pencere daralması | Orta | Sekme+bölme melezi, en çok 2 görünür bölme; asgari yükseklik testi (Faz 9/B-9.7 deseninin tekrarı). |
| PyInstaller derlemesi | Düşük | Yeni bağımlılık **yok** (Pygments/pyte/pywinpty eklenmiyor). Çalışan exe `dist/`'i kilitler — derleme öncesi süreç kapatılır (bilinen kısıt). |

### Faz 10 çıkış ölçütü (Faz 9'daki tanımın ölçülebilir hâli)

Kullanıcı:
1. Bir ofise gerçek bir depo bağlar (`repo_path` + `base_branch` doğrulanmış),
2. `/desk task` ile bir kart açar; **iki yazma niyetli alt ajan ayrı worktree'lerde aynı anda** koşar
   (`git worktree list` iki `desk/<kart-id>` satırı gösterir),
3. Terminaller sekmesinde her ikisinin **adlandırılmış** çıktısını ayrı ayrı izler (karışma yok),
4. Değişiklikler sekmesinde diff'i okur,
5. Makbuza koşu sırasında bir yorum bırakır ve o yorumu **bir sonraki alt kartın** isteminde görür (kart durmadan),
6. `gh` kuruluysa taslak PR bağlantısını alır; kurulu değilse dal + diff özetini alır ve **kart yine `review`'a geçer**,
7. Harcamayı tek şeritten okur ve şeritteki sayılar `/desk` metniyle birebir aynıdır.

---

## 4. Kullanıcıdan istenecek kararlar

Uygulamaya geçmeden önce yedi kararın netleşmesi gerekiyor. Önerilen yanıtlar **kalın**.

**Karar 1 — Terminal: gerçek PTY mi, akış terminali mi?**
Öneri: **akış terminali (a)**. Ölçüm: ConPTY + abonelik kimliğiyle etkileşimli `claude` **çalışıyor**,
ama (i) ilk ekran güven diyaloğu, (ii) `pyte` zorunlu (yeni bağımlılık), (iii) ikinci bir oturum = ikinci kota.
PTY Faz 11'e ertelenirse panel arayüzü değişmeden kaynak değiştirilebilir.
*Alternatif:* PTY'yi Faz 10'da isterseniz 10.2 tek başına bir dilim olur ve Faz 10 kotası ~+30k artar.

**Karar 2 — Worktree kökü nerede olsun?**
Öneri: **`<repo_path>/../.entropy-worktrees/<ofis>/<kart-id>`** (depo dışı, kısa).
Ölçüm: depo içi kök `git status`'ü kirletiyor (`?? .worktrees/`); 358 karakterlik yol
`core.longpaths` kapalıyken `Filename too long` ile ölüyor.
*Alternatifler:* (i) `%LOCALAPPDATA%\Entropy\worktrees\…` (kasadan ve depodan tamamen ayrı, ama daha uzun yol),
(ii) depo içi `.worktrees/` + `.gitignore` girdisi (kullanıcının deposunu değiştirmeyi gerektirir — **önerilmez**).

**Karar 3 — Worktree kartlarında Claude izolasyonuna istisna açılsın mı?**
`config.claude_isolated = True` iken `run_cwd` deponun **dışına** düşüyor (`claude_bridge.py:1429-1446`);
worktree'li kartta ajanın `Bash` aracı git deposunda olmalı.
Öneri: **evet, yalnızca `card.worktree` dolu olduğunda** `run_cwd` worktree'yi döner.
*Alternatif:* istisna açılmaz; ajana git komutlarını `git -C <yol>` biçiminde yazması istemde söylenir
(daha kırılgan; model unutabilir).

**Karar 4 — `gh` kurulsun mu?**
`gh` yok; `winget install --id GitHub.cli --source winget` ile kurulabilir ve
uzak depo (`origin https://github.com/BFBulut/entropyAI.git`) hazır.
Öneri: **Faz 10 `gh` olmadan tamamlanır** (yedek yol birincil). Kurmak isterseniz kurulum + `gh auth login`
**sizin elinizde** olmalı; Entropy kimlik doğrulaması yapmaz ve `gh auth status` çıktısını hiçbir yere yazmaz.

**Karar 5 — Dalı uzak depoya push etmek otomatik mi, onaylı mı?**
Öneri: **onaylı** (şeritte tek düğme). Uzak depoya yazma kullanıcının deposunda kalıcı iz bırakır.
*Alternatif:* proje ayarında "otomatik push" kutusu (varsayılan kapalı).

**Karar 6 — Makbuz ayrı bir `receipts/` klasörü mü olsun?**
Öneri: **hayır.** `Offices/<ofis>/reports/<kart-id>.md` makbuzun kendisi olsun; içeriği plan + diff + PR ile
zenginleşsin, panel onu okusun. Gerekçe: Faz 9'un P0-2 dersi (iki kaynaklı gerçek).
*Alternatif:* `receipts/` açılır ve `reports/` özet olarak kalır — iki dosyayı senkron tutma yükü doğar.

**Karar 7 — `--max-budget-usd` ikinci bir tavan olarak eklensin mi?**
`claude` bu bayrağı destekliyor, `agy` desteklemiyor. Bugünkü tavan token tabanlı ve iki sağlayıcıda ortak.
Öneri: **Faz 10'da eklenmesin** (sağlayıcı paritesi bozulur, ikinci bir "neden durdu" kaynağı doğar).
*Alternatif:* Claude ofislerinde isteğe bağlı ikinci tavan olarak eklenir ve şeritte ayrıca gösterilir.

**Ayrıca onayınıza sunulan iki küçük nokta:**
- Faz 10 **beş dilime** bölünsün mü (10-A…10-E), her dilim sonunda rapor + onay? (Orkestratör kipi kuralı gereği önerim: **evet**.)
- 10.8'de araştırma **tavanı** kaç arama olsun? Öneri: **en çok 3** (plan başına +3-8k token).

---

## 5. Kaynaklar

### 5.1 Depo kanıtları (bu notta atıf yapılan güncel satırlar)

| Dosya | Satır | Ne için |
|---|---|---|
| `src/entropy/core/event_bus.py` | 19, 20, 27 | `token_chunk_received(str)`, `terminal_output_received`, `token_usage_detail` imzaları |
| `src/entropy/core/claude_bridge.py` | 153-165 | `CHAT_TOOLS_READONLY` (WebFetch/WebSearch dahil), `CARD_TOOLS_BY_MODE` |
| `src/entropy/core/claude_bridge.py` | 634-680 | `build_command` (`--add-dir`, `--agent`, `--tools`, `--strict-mcp-config`) |
| `src/entropy/core/claude_bridge.py` | 999-1138 | `consume_stream` — iki yolun ortak çevirmeni |
| `src/entropy/core/claude_bridge.py` | 1070 | tek `token_chunk_received.emit(chunk)` |
| `src/entropy/core/claude_bridge.py` | 1162-1176 | `usage_badge_fields()` |
| `src/entropy/core/claude_bridge.py` | 1429-1446 | `run_cwd` — izole kipte nötr, depo dışı cwd |
| `src/entropy/core/claude_bridge.py` | 1449-1462 | `tools_for(mode, needs_write)` |
| `src/entropy/core/claude_bridge.py` | 1776-1790, 1913 | arka plan işçisi imzası, `consume_stream` çağrısı |
| `src/entropy/core/agy_bridge.py` | 744-759 | arka plan işçisi imzası (aynı sözleşme) |
| `src/entropy/core/agy_bridge.py` | 1030-1033, 1039 | arka planda **yalnızca** `terminal_output_received` (akış etiketi yok) |
| `src/entropy/core/agy_bridge.py` | 1696, 1712, 1761 | sohbet yolunda `token_chunk_received` |
| `src/entropy/core/provider.py` | 498 | `usage_breakdown()` — iki köprünün ortak kalemi |
| `src/entropy/core/config.py` | 217-232, 283 | `claude_workspace_path()`, `claude_isolated = True` |
| `src/entropy/core/slash_commands.py` | 763-802, 872-884 | `/desk` metni (harcama tek üretici), `/desk stop` |
| `src/entropy/core/task_ledger.py` | 51-71, 117-131, 414-420 | ledger şeması, `record_task_start(provider, model)`, `get_task` |
| `src/entropy/agents/harness.py` | 283-289 | `_workdir()` — tüm alt kartların ortak dizini |
| `src/entropy/agents/harness.py` | 415-471 | `_budget`, `ledger_tokens`, `_spend` |
| `src/entropy/agents/harness.py` | 510-537, 1350-1362 | `_terminate_children`, `stop` (temizlik beklemesi yok) |
| `src/entropy/agents/harness.py` | 661-672 | `_can_web_search()` — **yanlış yere bakıyor** (`office.members`) |
| `src/entropy/agents/harness.py` | 674-711 | `_write_research_notes` (kaynak alanı yok) |
| `src/entropy/agents/harness.py` | 713-799 | `build_plan_prompt` (`[TALİMAT]`, `[ARAŞTIRMA NOTU]`, şema) |
| `src/entropy/agents/harness.py` | 813-861 | `_apply_new_agents` — şablon uygulamasının deseni |
| `src/entropy/agents/harness.py` | 971-1040 | `_pump` — `limit = 1` kısıtı ve `project_path=_workdir()` |
| `src/entropy/agents/harness.py` | 1174-1241, 1244-1248 | `_finalize`, `_write_local_report` (makbuzun kaynağı) |
| `src/entropy/agents/harness.py` | 1412-1511 | `_call_agent` (ofis çağrısı sözleşmesi) |
| `src/entropy/agents/tasks.py` | 52, 59-60, 81 | `TASKS_SUBDIR`, `DESK_OFFICES_SUBDIR`, `OFFICE_CARDS_DIRNAME`, `MAX_STEPS_PER_CARD` |
| `src/entropy/agents/tasks.py` | 97-137 | `TaskCard` alanları (`project`, `intent` — genişletme deseni) |
| `src/entropy/agents/tasks.py` | 334-356 | `card_needs_write` |
| `src/entropy/agents/tasks.py` | 765-806 | `project_file_section` (Faz 9'da `:481` idi) |
| `src/entropy/agents/tasks.py` | 808-840 | `build_prompt` — çalışma dizini beyanı **yok** |
| `src/entropy/agents/tasks.py` | 841-935 | `TaskBoard.run(project_path=…)` |
| `src/entropy/agents/desk_registry.py` | 70-71 | `DEFAULT_MAX_PARALLEL=2`, `DEFAULT_BUDGET_TOKENS=120000` |
| `src/entropy/agents/desk_registry.py` | 80-145 | `ORCHESTRATOR_PROMPT` (Entropy geçmiyor), `DeskProject`, `DeskOffice` |
| `src/entropy/agents/desk_registry.py` | 417-467 (üye dışlama `:465`) | `_read` — geriye uyumlu ön bilgi ayrıştırma; üyeler orkestratörü **dışlıyor** |
| `src/entropy/agents/desk_registry.py` | 659-676 (`:679` `tools_policy="read-only"`) | `orchestrator_spec`, `ensure_orchestrator` |
| `src/entropy/agents/desk_registry.py` | 714-742 | `get_project`, `create_project` |
| `src/entropy/agents/compile.py` | 142-147 | `_TOOLS_BY_POLICY` — `read-only` → `WebFetch, WebSearch` |
| `src/entropy/agents/mailbox.py` | 246-265 | `_check_scope` — yön kilidi (Faz 9.4) |
| `src/entropy/agents/mailbox.py` | 436-461 | `instruct_office(office, instruction, task_id=…)` |
| `src/entropy/agents/mailbox.py` | 544-556, 559-590 | `pending_instructions(mark=True)`, `instructions_section` |
| `src/entropy/agents/mailbox.py` | 598-664 | `office_status()` — şeridin tek üreticisi |
| `src/entropy/desk/window.py` | 44-63 | pencere profili, sekme sabitleri |
| `src/entropy/desk/window.py` | 66-90, 388-406 | `office_spend()`, harcama rozeti (10.7'nin mevcut çekirdeği) |
| `src/entropy/desk/window.py` | 283-296 | sekme kurulumu (yeni sekmelerin yeri) |
| `src/entropy/desk/window.py` | 480-484 | `_on_agent_clicked` → Akış sekmesi |
| `src/entropy/desk/stream_panel.py` | 8-11, 40, 78-80, 90-106, 174-185 | ajan etiketi eksikliği notu, tek tampon, sinyal bağlantısı |
| `src/entropy/desk/board_panel.py` | 22, 32 | `card_selected` sinyali (pencerede **bağlı değil**) |
| `src/entropy/desk/projects_panel.py` | 38-79 | `ProjectEditDialog` (üç alan) |
| `src/entropy/desk/offices_panel.py` | 87-170, 408-412 | `OfficeEditDialog`, `create_office` |
| `src/entropy/desk/scene.py` | 200, 695 | `agent_clicked` sinyali |
| `src/entropy/tools/autonomous_agent_architecture.py` | 138-163, 668-703, 1387-1397 | bağlanmamış worktree tasarımı (yalnızca sözleşme örneği) |

### 5.2 Bu koşuda alınan ölçümler

| Ölçüm | Sonuç |
|---|---|
| `git --version` | 2.49.0.windows.1 |
| `claude --version` | 2.1.265 |
| `agy --version` | 1.1.28 |
| `gh --version` / `where.exe gh` | **kurulu değil** |
| `git remote -v` | `origin https://github.com/BFBulut/entropyAI.git` |
| `git config --get core.longpaths` | ayarlanmamış |
| İzlenen çalışma ağacı | 13.1 MB / 535 dosya; en derin göreli yol 99 karakter |
| Disk | C: 931G, 23G boş (%98 dolu) |
| `git worktree` deneyleri | §1.3 tablosu (izolasyon ✓, kilitli silme rc=255 + yarım silme, uzun yol ✗, dal tekrar kullanılamıyor, `remove` dalı silmiyor) |
| `pywinpty` | 3.0.5 kurulu (`import winpty`); `pyte` **kurulu değil**; `Pygments 2.19.2`, `GitPython 3.1.45`, `PySide6 6.11.2` kurulu |
| ConPTY + `cmd.exe` | ham ANSI çıktı alındı |
| **ConPTY + etkileşimli `claude` (abonelik)** | **çalışıyor** — 1160 bayt, 24-bit renk, bracketed paste; ilk ekran güven diyaloğu; kaçış dizileri çıkarılınca metin bitişik → `pyte` zorunlu |
| `claude agents --json` | TTY istemeden JSON döndü (`pid, cwd, kind, startedAt, sessionId, name`) |
| `claude --help` / `agy --help` | §1.5 yetenek matrisi |

### 5.3 Dış kaynaklar

- **AgentSpace (ticari referans)** — ajan başına adlandırılmış terminal, bölme ağacı, sprite tıklaması, bellek grafı,
  maliyet paneli. (Üretici adı ve alan adı bilinçli olarak yazılmamıştır; ayrıntı: Faz 9 raporu §1.)
- pixel-agents (MIT, piksel ofis görsel dili) — https://github.com/pixel-agents-hq/pixel-agents
- Google Antigravity — Artifacts (görev listeleri, planlar, diff'ler, walkthrough'lar) ve Docs tarzı yorumlar:
  - https://antigravity.google/blog/introducing-google-antigravity
  - https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/
  - https://codelabs.developers.google.com/getting-started-google-antigravity
  - https://github.com/ai-infra-curriculum/ai-agent-guidebook/blob/main/guides/antigravity/agents.md
- GitHub CLI kurulumu ve PR komutları:
  - https://cli.github.com/
  - https://github.com/cli/cli/blob/trunk/docs/install_windows.md
  - https://winget.run/pkg/GitHub/cli
- Qt/Python terminal emülasyonu (10.2 seçenek (b) değerlendirmesi):
  - https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QPlainTextEdit.html
  - https://gist.github.com/ssokolow/6f93e68d2af774aebf18667a7760cd23 (QPlainTextEdit tabanlı terminal örneği)
  - https://forum.qt.io/topic/158162/need-a-terminal-like-widget-usable-from-python
  - https://pypi.org/project/tkwinterm/0.2.2 (Windows'ta `pyte` + winpty birleşimi örneği)

---

## 6. Özet

Faz 10'un on maddesi kanıtla eşleştirildi ve dört tanesinin teşhisi Faz 9'dakinden **farklı** çıktı:

1. **10.1 sanıldığından büyük:** agy köprüsü arka plan kartlarında `token_chunk_received`'i **hiç** yaymıyor
   (`agy_bridge.py:1030-1033`). Yani Desk'in Akış paneli agy ofislerinde bugün **tamamen boş**.
   Etiketleme işi aynı zamanda bir hata düzeltmesidir.
2. **10.8'in teşhisi yanlıştı:** orkestratörün arama aracı **var** (`read-only` → `WebFetch, WebSearch`);
   hata `_can_web_search()`'ün `office.members`'a bakması ve orkestratörün o listede **bulunmaması**
   (`desk_registry.py:465`). Yeni ofiste kontrol her zaman `False` dönüyor ve istem araştırma hiç istemiyor.
   Düzeltme küçük, etkisi büyük.
3. **10.7 büyük ölçüde yapılmış:** harcama rozeti ve sağlayıcı rozeti Desk şeridinde çalışıyor
   (`window.py:388-406`, `:222-229`); kalan iş kart başına satır ve tek üreticiyi genişletmek.
4. **10.4 sanıldığından risklidir:** Windows'ta dosya kilidi varken `git worktree remove --force`
   **rc=255** veriyor, kaydı siliyor ama **dizini bırakıyor**, `prune` kurtarmıyor ve aynı yola yeniden
   `add` yapılamıyor. Temizlik doğrulamalı, ertelenebilir ve yetim listeli olmak zorunda.

Kullanıcının açıkça sorduğu iki soru ölçümle yanıtlandı:
- **PTY:** abonelik kimliğiyle etkileşimli `claude` ConPTY içinde **çalışıyor** (kanıtlandı), ama güven diyaloğu,
  `pyte` bağımlılığı ve ikinci kota kalemi yüzünden Faz 10 için **akış terminali** öneriliyor.
- **`gh`:** kurulu **değil**; uzak depo ve `winget` hazır. Bu yüzden PR akışının **yedek yolu birincil** yapıldı;
  Faz 10 `gh` olmadan da çıkış ölçütünü karşılıyor.

Faz 10 beş dilime bölünüyor (temel → izolasyon → inceleme → akıl/kadro → doğrulama), toplam kota **~85-115k token**,
yani tek bir ofis bütçesine (120k) sığıyor. Uygulamaya geçmeden önce §4'teki yedi kararın onayı gerekiyor;
en kritik ikisi **terminal seçeneği** ve **worktree kökü**.
