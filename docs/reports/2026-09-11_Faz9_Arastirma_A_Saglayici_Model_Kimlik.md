# Faz 9 — Araştırma A: Sağlayıcı, Model Envanteri ve Entropy Kimliği

**Tarih:** 2026-09-09 · **Depo:** `C:\EntropiAI` · **Dal:** `ai/v0.1.7` · **Sürüm:** v0.6.0
**Kip:** SALT OKUNUR — hiçbir kaynak dosya değiştirilmedi. Gerçek model çağrısı yapılmadı.
**Ölçüm ortamı:** Claude Code `2.1.265`, `agy.exe`, Windows 11 Pro 26200.

---

## 0. Yönetici özeti (üç cümle)

1. Entropy, Claude Code'u **saf LLM arka ucu olarak değil, kullanıcının kendi terminali olarak** çalıştırıyor: `--append-system-prompt` varsayılan Claude Code istemini KORUYOR, çalışma dizini git deposunun içinde olduğu için kullanıcının otomatik-belleği, 32 yeteneği, 14 ajanı, 119 ertelenmiş MCP aracı ve git durumu her tura giriyor — ölçülen taban bağlam **34.920 token**, kullanıcının gördüğü "77k" bunun iki turda yeniden okunmasıdır (kanıt §1.1, §1.2).
2. Arka plan görev kartları **hiç sistem istemi almıyor** (`build_command` çağrısında `append_system_prompt=` parametresi yok) — bugünkü iki Claude oturumunda Entropy kimliği ölçülen **0 karakter**; kart yalnızca `[GÖREV SÖZLEŞMESİ]` metniyle Claude Code'un kendi kimliğine gidiyor (kanıt §1.3).
3. `unrecognized_model` hatasının kaynağı kartta değil ayarlarda: `set_model()` doğrulama yapmadan `provider_models["claude"] = "gemini-3.1-pro-high"` yazmış ve köprünün yabancı-model koruması tam da bu alanı **yedek değer** olarak okuduğu için devre dışı kalmış (kanıt §1.4).

---

## 1. Bulgular ve kök nedenler

### 1.1 Kök neden #1 — Sistem istemi DEĞİŞTİRİLMİYOR, EKLENİYOR

`src/entropy/core/claude_bridge.py:1058-1059` bunu açıkça tasarım kararı olarak yazıyor:

> `Neden argv'deki prompt'a değil sistem istemine: Claude Code varsayılan sistem istemini korur ve buna EKLER;`

`src/entropy/core/claude_bridge.py:565-583` — argv'ye yalnızca `--append-system-prompt` / `--append-system-prompt-file` giriyor; `--system-prompt` hiçbir kod yolunda kullanılmıyor.

**Ölçülen sonuç.** Bugünkü sohbet oturumunun (`d11ec751-b74b-46fa-8b9b-5631a00e6cec.jsonl`, 20:35) kaydedilmiş sistem istemi 15 parçadan oluşuyor:

| Parça | Uzunluk | ~Token | Baş |
|---|---:|---:|---|
| part0 | 1.210 ch | 302 | `You are an interactive agent that helps users with software…` |
| part1 | 34 ch | 8 | `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` |
| part6 | **4.097 ch** | **1.024** | `# auto memory\n\nYou have a persistent, file-based memory at ...` |
| part10 | 2.017 ch | 504 | `# Delivering work…` |
| part2–13 (toplam) | 12.438 ch | **3.109** | Claude Code'un kendi istemi |
| **part14** | **7.844 ch** | **1.961** | `Sen Entropy AI adında otonom bir masaüstü yapay zeka işletim sistemisin…` |

Yani Entropy kimliği sistem isteminin **%39'u** ve **en sonda**; Claude Code'un "yazılım mühendisliği ajanısın" kimliği ve `# auto memory` bloğu **önce** geliyor. Kullanıcının gördüğü *"Hafıza kayıtları geçmiş anlık görüntülerdir… bu turda kaydedilmeye değer yeni kalıcı bir ders çıkmadığı için hafızaya yazma yapmadım"* cümlesi tam olarak **part6'nın** talimatıdır — Entropy'nin değil.

**İkinci sızıntı kanalı:** `instructions` eklentisi 3 dosya taşıyor, hepsi `type: "AutoMemPinned"`, örn. `C:\Users\batu_\.claude\projects\C--EntropiAI\memory\agent-desk-architecture-rules.md`. Depoda hiçbir `CLAUDE.md` yok (`ls` doğrulaması: `C:\EntropiAI\CLAUDE.md`, `dist\EntropyAI\CLAUDE.md`, `~/.claude/CLAUDE.md` — üçü de yok). Yani bu 4.749 karakter tamamen **kullanıcının kişisel Claude Code sabitlenmiş belleğidir** ve Entropy'nin her turuna giriyor.

**Üçüncü sızıntı:** `session_context` eklentisi `{userEmail, gitStatus}` taşıyor — kullanıcının e-postası ve deponun git durumu her Entropy turuna gidiyor.

### 1.2 Kök neden #2 — Çalışma dizini deponun İÇİNDE; Claude Code proje kimliğini git köküne göre çözüyor

`claude_bridge.py:1192` ve `:1428`: `cwd=str(project_dir) if project_dir.exists() else None`. Bugünkü koşuda `project_dir = C:\EntropiAI\dist\EntropyAI` (günlük satırı: `2026-09-09 20:32:04,086 INFO entropy.agents.bootstrap: Ajan derlemesi: 3 ajan, kökler=['C:\\EntropiAI\\dist\\EntropyAI']`).

Bu dizinde yalnızca 3 ajan var (`analist.md`, `arastirmaci.md`, `yazar.md`) — ama oturumun `agent_listing_delta` eklentisinde **14 ajan** listelenmiş (`agy-integration-engineer`, `memory-rag-engineer`, `qa-build-engineer`, `ui-engineer`, `Explore`, `Plan`, `claude`, `general-purpose`, `claude-code-guide`, `statusline-setup`, `degerlendirici`, `orkestrator` + 3'ü). Nedeni komut çıktısıyla doğrulandı:

```
$ cd C:/EntropiAI/dist/EntropyAI && git rev-parse --show-toplevel
C:/EntropiAI
```

**Claude Code proje kimliğini (bellek dizini, `.claude/agents`, git durumu) literal cwd'den değil GIT KÖKÜNDEN çözüyor.** Bu yüzden `dist\EntropyAI` altına inmek kaçış sağlamıyor; nötr cwd'nin **herhangi bir git deposunun dışında** olması gerekiyor. Doğrulama: `cd C:/Users/batu_ && git rev-parse --show-toplevel` → `fatal: not a git repository`. Yani `%USERPROFILE%\.entropy\workspace` geçerli bir nötr köktür.

### 1.3 Kök neden #3 — Arka plan kartları sistem istemi ALMIYOR

`claude_bridge.py:1391-1399`, `_execute_background_task_worker` içinde:

```python
cmd = self.build_command(
    prompt, mode=mode, project_dir=project_dir, agent=agent,
    skip_permissions=True, resume_id=conversation_id, max_steps=max_steps,
)
```

`append_system_prompt=` **verilmiyor.** Sohbet yolu (`claude_bridge.py:1163,1178`) veriyor, arka plan yolu vermiyor.

Ölçüm bunu birebir doğruluyor — bugünkü iki arka plan oturumunda Entropy kimliği **0 karakter**:

| Oturum | Saat | Kart | systemPrompt parça | Entropy payı | Claude Code payı |
|---|---|---|---:|---:|---:|
| `d11ec751…` | 20:35 | sohbet | 15 | 7.844 ch (~1.961 tok) | 12.438 ch (~3.109 tok) |
| `78fc98df…` | 20:40 | Canivo Reklam | 14 | **0 ch** | 12.437 ch (~3.109 tok) |
| `97b14894…` | 20:44 | Görev 1 | 11 | **0 ch** | 8.327 ch (~2.081 tok) |

Karşılaştırma: AGY köprüsü kimliği bayrakla değil **prompt'un içine gömerek** taşıyor (`agy_bridge.py:1431-1467`, `system_directive` → `full_prompt_payload`), bu yüzden AGY'de sohbet/arka plan asimetrisi yok. Claude tarafında asimetri var.

### 1.4 Kök neden #4 — `unrecognized_model`: ayar dosyası zehirlenmiş, koruma yedek değeri okuyor

**Canlı kanıt** — `C:\EntropiAI\.entropy\settings.json` (20:40'ta yazılmış):

```json
"provider_models": {
  "agy":    "gemini-3.1-pro-high",
  "claude": "gemini-3.1-pro-high"     ← ZEHİRLİ
},
"claude_config_dir": ""
```

**Zincir:**

1. Üst çubuk model kutusu **düzenlenebilir** (`zen_mode.py:180 setEditable(True)`) ve `setCurrentText(self.bridge.selected_model)` listede olmayan bir değeri serbest metin olarak kabul ediyor.
2. `_on_model_selected` (`zen_mode.py:783-785`) doğrudan `bridge.set_model(model_name)` çağırıyor.
3. `claude_bridge.py:445-452 set_model()` **hiçbir doğrulama yapmadan** `config.provider_models["claude"] = model_name` yazıyor.
4. `claude_bridge.py:266-272 __init__` yabancı-model korumasını şöyle kuruyor:
   ```python
   default_model = config.provider_models.get("claude") or CLAUDE_MODELS[0]   # ← zehirli değer
   current = config.selected_model                                            # "gemini-3.1-pro-high"
   self.selected_model = current if self._is_claude_model(current) else default_model
   ```
   `_is_claude_model` `current`'ı doğru reddediyor — ama **yedek değerin kendisi de zehirli** olduğu için koruma boşa çıkıyor.
5. `build_command:557-558` → `--model gemini-3.1-pro-high` → süreç açılıyor, model reddediliyor.

**Sonuç metni** (`97b14894…jsonl`, `model: "<synthetic>"`, 153 karakter — defterdeki `çıkış kodu: 1, yanıt uzunluğu: 153` ile birebir uyuyor):

> `There's an issue with the selected model (gemini-3.1-pro-high). It may not exist or you may not have access to it. Run --model to pick a different model.`

**Kartın `model` alanı ölüdür.** `TaskCard.model` tanımlı (`agents/tasks.py:88,129,376`) ama `run_card` (`tasks.py:587-595`) yalnızca `provider`'a göre köprü seçiyor, `card.model`'i **hiçbir yere yazmıyor**. Faz 3 sağlayıcı-model eşlemesinin kartta çalışmama nedeni budur: eşleme yalnızca **ajan tanımı derlemesinde** var (`agents/compile.py:46-69 resolve_model`), görev yürütmesinde yok.

### 1.5 "77k" nereden geliyor — bileşen ölçümü

Sohbet oturumu `d11ec751`, iki asistan mesajı (benzersiz `message.id`):

| Mesaj | input | cache_creation | cache_read | output | toplam |
|---|---:|---:|---:|---:|---:|
| `msg_011CetGQT4t9JR3TsPaMcoE2` | 2 | 19.514 | 15.406 | 355 | 35.277 |
| `msg_011CetGQnRifJTasfpfmWS5c` | 2 | 5.015 | 34.920 | 2.077 | 42.014 |
| **TOPLAM** | **4** | **24.529** | **50.326** | **2.432** | **77.291** |

**77.291 ≈ kullanıcının gördüğü "Sohbet: 77k (+77k)".** Gerçek konuşma içeriği yalnızca **4 girdi + 2.432 çıktı token**; kalan **74.855 token taban bağlamın yazılıp iki kez okunmasıdır.**

İlk turun 34.920 tokenlik tabanının ölçülen bileşenleri:

| Bileşen | Ham boyut | ~Token | Kaçış yolu |
|---|---:|---:|---|
| `prompt_snapshot` → Claude Code varsayılan istemi (part0–13) | 12.438 ch | 3.109 | `--system-prompt` |
| ⤷ bunun içinde `# auto memory` (part6) | 4.097 ch | 1.024 | `--system-prompt` |
| `prompt_snapshot` → Entropy kimliği (part14) | 7.844 ch | 1.961 | *korunmalı* |
| `skill_listing` (32 yetenek) | 15.313 ch | 3.828 | `--disable-slash-commands` |
| `deferred_tools_delta` ×2 (55 + 64 = 119 araç adı) | 9.554 ch | 2.388 | `--strict-mcp-config` + `--tools` |
| `instructions` (3 × `AutoMemPinned`) | 4.749 ch | 1.187 | nötr cwd (git dışı) |
| `agent_listing_delta` (14 ajan) | 3.886 ch | 971 | nötr cwd + `--agents` |
| `session_context` (`userEmail`, `gitStatus`) | 3.671 ch | 917 | nötr cwd |
| `mcp_instructions_delta` | 460 ch | 115 | `--strict-mcp-config` |
| `environment` / `model` / `date` / `remote_session_change` | 834 ch | 208 | — |
| **Eklentiler toplamı** | **145.364 ch** | **~36.341** | |

Kalan fark (~35k ölçülen taban ile eklentilerin toplamı arasındaki örtüşme) yerleşik araç şemalarından geliyor; şemalar transcript'e yazılmadığı için doğrudan ölçülemiyor, ancak `deferred_tools` 119 aracın yalnızca **adlarını** taşıdığı, şemalarının ise araç arandığında yüklendiği görülüyor.

**Tahmini kazanç (izole profil ile):** `--system-prompt` + `--strict-mcp-config` + `--disable-slash-commands` + git dışı nötr cwd birlikte ölçülen eklentilerden **~9.400 token**'ı (skill_listing 3.828 + tools 2.388 + instructions 1.187 + agents 971 + session_context 917 + mcp 115) ve varsayılan istemden **~3.109 token**'ı kaldırır → **tur başına ~12.500 token**, iki turda **~25.000 token**. 77k'lık tur ~52k'ya iner; araç şemaları da düşerse tahminî bant **30–45k**.

### 1.6 Görev defteri kanıtı (bugün)

`%USERPROFILE%\.entropy\tasks_ledger.db` son kayıtlar — **bugün Claude ile açılan HER kart başarısız:**

| task_id | durum | sağlayıcı | token | hata |
|---|---|---|---:|---|
| `card-20260909-204445-g-rev-1` | FAILED | claude | 0/0/0 | `çıkış kodu: 1, yanıt uzunluğu: 153` |
| `card-20260909-203921-canivo-reklam` | CANCELLED | claude | — | `Uygulama kapandı; görev yarıda kesildi.` |
| `card-20260909-171945-readme-…` | FAILED | claude | — | `çıkış kodu: 0, yanıt uzunluğu: 0` |
| `card-20260909-062745-10-maddelik-…` | SUCCESS | agy | 192.041 | — |
| `card-20260909-062745-faz-1-ve-faz-2-…` | SUCCESS | agy | 340.492 | — |

**Defter şeması eksik:** `PRAGMA table_info(tasks)` → `[task_id, task_name, project_path, status, created_at, started_at, completed_at, error, result_summary, input_tokens, output_tokens, total_tokens, provider]`. **`model` sütunu yok** — hangi modelin koştuğu defterden hiç okunamıyor; bu hatanın günlerce görünmez kalmasının bir nedeni budur.

### 1.7 Model listeleri neden boş görünüyor

| Yer | Kaynak | Durum |
|---|---|---|
| Üst çubuk (`zen_mode.py:182`, `chat_mode.py:321`) | `bridge.fetch_available_models()` | **Çalışıyor** — claude'da 3 tam ad + 3 takma ad döner |
| Entropy ajan formu (`agents_widget.py:186-196`) | köprü **aynı sağlayıcıysa** ondan, değilse `FALLBACK_MODELS` | **Bozuk** — agy yedeği `["gemini-3-pro","gemini-2.5-pro","gemini-2.5-flash"]`; **üçü de `agy models` çıktısında YOK** |
| Desk kadro paneli (`desk/roster_panel.py`) | — | **Alan yok** — `grep -i model` sıfır sonuç |
| Desk pano / kart formu (`desk/board_panel.py`) | — | **Alan yok** — `grep -i model` sıfır sonuç |
| `config.available_models` (`config.py:174-187`) | sabit liste | Kısmen bayat; yalnızca agy modelleri, `claude-opus-5` yok |

### 1.8 Üst çubuk metni — ölçüm

`ui/widgets/provider_badge.py:50-66 status_text()` `label · plan · session_window · quota_hint` diziyor.
`core/identity.py:203-204` "ürkütücü" metni üretiyor: `state = f"{minutes} dk kaldı" if minutes > 0 else "süresi doldu (yenilenecek)"`.
`core/identity.py:169-171` Claude için `quota_hint = f"abonelik: {status.plan}"` — plan zaten `label · plan` içinde olduğu için **"max" iki kez** yazılıyor.

QFontMetrics ölçümü (Segoe UI 12px, `ui_polish.LABEL_PX = 12`):

| Metin | Uzunluk | Genişlik |
|---|---:|---:|
| `AGY · antigravity-cli · belirteç 2026-09-07T23:53 (süresi doldu (yenilenecek))` | 78 ch | **936 px** |
| `Claude · max · abonelik: max` | 28 ch | **336 px** |
| **Şu anki toplam (6 px boşlukla)** | | **1.278 px** |
| Hedef: ≤ **160 px** | | **8× fazla** |

### 1.9 "Yalnızca Claude" modu — sabit agy bağları

`AgyProcessBridge` doğrudan içe aktarımları (fabrika dışı): `ui/manager.py:9,26` (tip ipucu), `ui/modes/chat_mode.py:22,223`, `ui/modes/zen_mode.py:23,60`, `core/identity.py:225-227` (yalnızca ikili bulmak için). **Bunlar tip ipucu/prob amaçlı; çalışma zamanı köprüsü `create_bridge()` üzerinden geliyor — kırılgan değil.**

Gerçek risk **sabit varsayılan**: `"agy"` 30+ yerde varsayılan sağlayıcı. Kritik olanlar:

- `agents/tasks.py:87,375,456` — `TaskCard.provider` varsayılanı `"agy"`
- `agents/registry.py:116,270,295,318,341,371,463,486` — tüm tohum ajanlar `provider="agy"`
- `agents/desk_registry.py:128,223,243,414,424,510-512,581` — ofis `default_provider` varsayılanı `"agy"`
- `agents/harness.py:488,791-792,886-887,1387` — alt kart sağlayıcı düşüşü `"agy"`
- `core/provider.py:699-701` — `create_bridge`: bilinmeyen ad → `"agy"`
- `core/config.py:135` — `EntropyConfig.provider = "agy"`
- `core/provider.py:148` — `ProviderCommonMixin.provider_name = "agy"`

**Sağlayıcıdan bağımsız ve sorunsuz olanlar:** `agent_definitions_dir` / `list_agent_definitions` (`provider.py:651-680`, `AGENT_DEFINITION_LAYOUT = {"agy": (".agents/agents","agent.md"), "claude": (".claude/agents", None)}` — doğru soyutlanmış); `/wiki` ve `/lint` (`slash_commands.py:1025-1070`) — model çağırmıyor, kotadan bağımsız; damıtıcı (`memory/distiller.py:678`) — `bridge.send_background_task_async` sözleşmesi üzerinden, sağlayıcı-nötr; efor seçici (`ui/widgets/effort_selector.py:63-73`) — seviyeleri köprüden okuyor.

**Sonuç:** agy kurulu değilken/oturumsuzken uygulama açılır ve sohbet Claude'a geçirilebilir, ama **her yeni kart, ajan ve ofis `provider: agy` doğar** ve ilk koşuda ölür. "Yalnızca Claude" tek ayarla değil, varsayılanın ayardan okunmasıyla çözülür.

---

## 2. Bayrak doğrulama tablosu

Kaynak: bu makinede `claude --help` (sürüm `2.1.265`) + `code.claude.com/docs/en/cli-reference`. Gizli bayraklar canlı probla doğrulandı (aşağıda).

### 2.1 Sistem istemi

| Bayrak | Var? | `--help` / belge alıntısı | Entropy kullanıyor mu |
|---|---|---|---|
| `--system-prompt <prompt>` | ✅ | `System prompt to use for the session` · belge: *"Replace the entire system prompt with custom text"* | **HAYIR** |
| `--system-prompt-file <path>` | ✅ **gizli** | `--help`'te YOK. Belge: *"Load system prompt from a file, replacing the default prompt"* | **HAYIR** |
| `--append-system-prompt <prompt>` | ✅ | `Append a system prompt to the default system prompt` | Evet (`:581,583`) |
| `--append-system-prompt-file <path>` | ✅ **gizli** | `--help`'te YOK. Belge: *"Load additional system prompt text from a file and append to the default prompt"* | Evet (`:119,579`) |
| `--system-prompt-snapshot <on\|off>` | ✅ | `Record the system prompt once per conversation and reuse it verbatim on every request and resume… every later request and resume sends the record as-is, even when a later launch passes different text, until the conversation is compacted.` | Hayır — **`--resume` ile kritik**, aşağıya bak |
| `--exclude-dynamic-system-prompt-sections` | ✅ | `Move per-machine sections (cwd, env info, memory paths, git status) from the system prompt into the first user message… Only applies with the default system prompt (ignored with --system-prompt)` | Hayır |

**Gizli bayrak canlı probu** (kota harcamaz — süreç model çağırmadan hata veriyor):

```
$ claude -p "x" --system-prompt-file /nonexistent_zzz.txt
Error: System prompt file not found: C:\Program Files\Git\nonexistent_zzz.txt

$ claude -p "x" --append-system-prompt-file /nonexistent_zzz.txt
Error: Append system prompt file not found: C:\Program Files\Git\nonexistent_zzz.txt

$ claude -p "x" --append-system-prompt "a" --append-system-prompt-file /nonexistent_zzz.txt
Error: Cannot use both --append-system-prompt and --append-system-prompt-file. Please use only one.

$ claude --zzz-bogus-flag                      ← kontrol probu
error: unknown option '--zzz-bogus-flag'
```

Kontrol probu ile karşılaştırıldığında iki dosya bayrağı da **gerçek** (bilinmeyen seçenek hatası vermiyor, kendi anlamlı hatalarını veriyor). `claude_bridge.py:107-116`'daki mevcut varsayım doğrulandı.

> ⚠️ **`--system-prompt-snapshot` tuzağı.** Entropy `--resume <session-id>` kullanıyor (`build_command:597-600`). Snapshot varsayılan olarak `on`: **bir konuşmanın ilk isteğinde kaydedilen sistem istemi, sonraki her turda ve resume'de aynen gönderilir; sonraki koşuş farklı metin verse bile.** Yani `--system-prompt`'a geçiş, YENİ konuşmalarda etkili olur; sürmekte olan bir konuşma eski (kirli) istemi taşımaya devam eder. Faz 9'da sağlayıcı/istem değişince `ConversationMap` girdisi düşürülmeli.

### 2.2 İzolasyon

| Bayrak | Var? | Alıntı | Not |
|---|---|---|---|
| `--bare` | ✅ | `Minimal mode: skip hooks, LSP, plugin sync, attribution, auto-memory, background prefetches, keychain reads, and CLAUDE.md auto-discovery. Sets CLAUDE_CODE_SIMPLE=1. Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read).` | 🚫 **ENTROPY İÇİN KULLANILAMAZ** |
| `--safe-mode` | ✅ | `Start with all customizations (CLAUDE.md, skills, plugins, hooks, MCP servers, custom commands and agents, output styles, workflows, custom themes, keybindings, and more) disabled… Auth, model selection, built-in tools, and permissions work normally.` | ✅ **Abonelikle çalışır** |
| `--restricted` | ✅ | `removes the built-in tools that run commands or code… unless --tools names them, and ignores user, project and local settings files (managed settings and --settings still apply; add --strict-mcp-config to skip MCP servers too)` | Kısmî; yazma isteyen kartlar için fazla dar |
| `--strict-mcp-config` | ✅ | `Only use MCP servers from --mcp-config, ignoring all other MCP configurations` | ✅ |
| `--mcp-config <configs...>` | ✅ | `Load MCP servers from JSON files or strings (space-separated)` | Kullanılıyor (`:584-585`) |
| `--setting-sources <sources>` | ✅ | `Comma-separated list of setting sources to load (user, project, local).` | ✅ |
| `--disable-slash-commands` | ✅ | `Disable all skills` | ✅ (skill_listing 3.8k token) |
| `--tools <tools...>` | ✅ | `Specify the list of available tools from the built-in set. Use "" to disable all tools, "default" to use all tools, or specify tool names (e.g. "Bash,Edit,Read").` | ✅ |
| `--allowedTools` / `--disallowedTools` | ✅ | `Comma or space-separated list of tool names to allow/deny (e.g. "Bash(git *) Edit")` · belge: `"mcp__*"` her MCP aracını kaldırır | ✅ |
| `--agents <json>` | ✅ | `JSON object defining custom agents (e.g. '{"reviewer": {"description": …, "prompt": …}}')` | ✅ nötr cwd'de ajanları geri vermenin yolu |
| `--add-dir <directories...>` | ✅ | `Additional directories to allow tool access to` · belge: *"Grants file access; Claude Code doesn't discover most `.claude/` configuration from these directories."* | Kullanılıyor (`:559-562`) |
| `--permission-mode <mode>` | ✅ | `(choices: "acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan")` | Kullanılıyor (`:555`) |
| `CLAUDE_CONFIG_DIR` | ✅ (ortam) | `claude auth status --json` → `"projectsDirectory": "C:\\Users\\batu_\\.claude\\projects"` | Kod var (`:361-383`), ayar **boş** → devre dışı |

> 🚫 **`--bare` neden kullanılamaz.** Belge açık: *"In bare mode, Claude Code never reads OAuth credentials or the system keychain… set `ANTHROPIC_API_KEY`… because bare mode doesn't use your subscription login."* Kullanıcının kimliği `claude auth status --json` çıktısına göre `"authMethod": "claude.ai"`, `"subscriptionType": "max"` — yani **abonelik**. `--bare` bu aboneliği kullanamaz, ücretli API anahtarı ister. Faz 9'da `--bare` DEĞİL, **`--system-prompt` + `--strict-mcp-config` + `--setting-sources` + `--disable-slash-commands` + git-dışı nötr cwd** birleşimi kullanılmalı; `--safe-mode` de aboneliği koruyan bir alternatiftir ama `--agents`/`--mcp-config` ile Entropy'nin kendi ajanlarını geri vermeye izin verip vermediği ölçülmeli.

### 2.3 Model, efor, bütçe, akış

| Bayrak | Var? | Alıntı | Entropy |
|---|---|---|---|
| `--model <model>` | ✅ | `Provide an alias for the latest model (e.g. 'fable', 'opus', or 'sonnet') or a model's full name (e.g. 'claude-fable-5').` | Evet (`:557-558`) — **doğrulamasız** |
| `--effort <level>` | ✅ | `Effort level for the current session (low, medium, high, xhigh, max)` · belge ayrıca `ultracode` | Evet (`:604-609`); `CLAUDE_EFFORT_LEVELS` doğru, `ultracode` eksik |
| `--fallback-model <model>` | ✅ | `Enable automatic fallback to specified model(s) when the default model is overloaded or not available. Accepts a comma-separated list` | Hayır — **öneri: eklenmeli** |
| `--max-budget-usd <amount>` | ✅ | `Maximum dollar amount to spend on API calls (only works with --print)` · belge: *"Spend from subagents counts toward the cap"* | Hayır — kart bütçesi için ideal |
| `--max-turns` | ❌ | `--help`'te yok, belgede yok | `CLAUDE_SUPPORTS_MAX_TURNS = False` (`:86`) **doğru** |
| `--output-format stream-json` | ✅ | `(choices: "text", "json", "stream-json")` | Evet (`:553`) |
| `--verbose` | ✅ | `Override verbose mode setting from config` | Evet (`:554`) — stream-json ile şart, yorum doğru |
| `--include-partial-messages` | ✅ | `Include partial message chunks as they arrive (only works with --print and --output-format stream-json)` | Hayır — canlı yazım için |
| `--input-format stream-json` | ✅ | `"text" (default), or "stream-json" (realtime streaming input)` | Evet (`_apply_stdin_prompt`) |
| `--no-session-persistence` | ✅ | `Disable session persistence - sessions will not be saved to disk and cannot be resumed (only works with --print)` | Hayır — **`--resume` kullanıldığı için kullanılamaz** |
| `--json-schema <schema>` | ✅ | `JSON Schema for structured output validation` | Hayır — kart çıktısı sözleşmesi için fırsat |
| `--permission-prompts <target>` | ✅ | `"host"… or "none" (nobody: anything that would prompt is denied automatically)` | Hayır — gözetimsiz kart koşusu için |
| `--session-id <uuid>` | ✅ | `Use a specific session ID for the conversation (must be a valid UUID)` | Hayır — `ConversationMap`'i deterministik yapar |

---

## 3. Model envanteri

### 3.1 AGY (`agy models`, canlı çıktı, kota harcamaz)

```
gemini-3.8-flash-high      Gemini 3.8 Flash (High)
gemini-3.8-flash-medium    Gemini 3.8 Flash (Medium)
gemini-3.8-flash-low       Gemini 3.8 Flash (Low)
gemini-3.7-flash-high/medium/low
gemini-3.6-flash-high/medium/low
gemini-3.1-pro-high        Gemini 3.1 Pro (High)
gemini-3.1-pro-low         Gemini 3.1 Pro (Low)
claude-sonnet-4-6          Claude Sonnet 4.6 (Thinking)
claude-opus-4-6-thinking   Claude Opus 4.6 (Thinking)
gpt-oss-120b-medium        GPT-OSS 120B (Medium)
```

15 model. **Fiyat/kota bilgisi vermiyor.** `agy --help` alt komutları: `agent(s)`, `models`, `mcp`, `plugin(s)`, `remote-control`, `update`, `install`, `changelog`, `mic-serve`, `help`. `agy --effort` seviyeleri: `low|medium|high` (Claude'un `xhigh`/`max`'ı YOK — `provider_effort` ayrımı doğru).

⚠️ `FALLBACK_MODELS["agy"]` = `["gemini-3-pro", "gemini-2.5-pro", "gemini-2.5-flash"]` (`agents_widget.py:50`) — **üçü de bu listede yok**, hepsi geçersiz.

### 3.2 Claude Code

Takma adlar (belge: `code.claude.com/docs/en/model-config`):

| Takma ad | Anlamı |
|---|---|
| `default` | Geçersiz kılmayı temizler, hesabın çalışma zamanı varsayılanına döner |
| `best` | Varsa `fable`, yoksa `opus` |
| `fable` | En son Fable (varsayılan Fable 5.1) |
| `opus` | En son Opus (Anthropic API'de Opus 5) |
| `sonnet` | En son Sonnet (Sonnet 5) |
| `haiku` | Hızlı ve verimli Haiku |
| `opusplan` | Planlamada Opus, yürütmede otomatik Sonnet'e geçer |
| `opus[1m]` / `sonnet[1m]` / `fable[1m]` | 1M bağlam pencereli sürümler |

Tam kimlikler ve fiyat (kaynak: `claude-api` yeteneği, önbellek 2026-06-24):

| Model | Kimlik | Bağlam | Girdi $/1M | Çıktı $/1M |
|---|---|---:|---:|---:|
| Claude Fable 5.1 | `claude-fable-5-1` | 1M | 10,00 | 50,00 |
| Claude Fable 5 | `claude-fable-5` | 1M | 10,00 | 50,00 |
| **Claude Opus 5** | **`claude-opus-5`** | 1M | 5,00 | 25,00 |
| Claude Opus 4.8 | `claude-opus-4-8` | 1M | 5,00 | 25,00 |
| Claude Opus 4.7 | `claude-opus-4-7` | 1M | 5,00 | 25,00 |
| Claude Opus 4.6 | `claude-opus-4-6` | 1M | 5,00 | 25,00 |
| **Claude Sonnet 5** | **`claude-sonnet-5`** | 1M | 2,00 | 10,00 |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | 3,00 | 15,00 |
| **Claude Haiku 4.5** | **`claude-haiku-4-5`** | 200K | 1,00 | 5,00 |

`CLAUDE_MODELS` (`claude_bridge.py:146-155`) = `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5` — **doğru ve güncel**; takma ad eşlemesi de doğru. Eksik: `fable`, `best`, `default`, `opusplan`, `[1m]` çeşitleri.

### 3.3 Önerilen "varsayılan / ucuz / güçlü" üçlüsü

| Sağlayıcı | Ucuz (alt görev, damıtma) | Varsayılan (sohbet, kart) | Güçlü (orkestratör, denetim) |
|---|---|---|---|
| **claude** | `claude-haiku-4-5` | `claude-opus-5` | `claude-opus-5` + `--effort xhigh` |
| **agy** | `gemini-3.8-flash-low` | `gemini-3.1-pro-high` | `claude-opus-4-6-thinking` |

Gerekçe: Claude tarafında Opus 5 zaten Sonnet 5'in ~2,5 katı fiyatta ama Entropy'nin gerçek darboğazı **model değil bağlam** (§1.5) — model düşürmek yerine bağlamı temizlemek daha ucuz. AGY tarafında `pro-high` planlamayı, `flash-low` toplu okuma işlerini karşılıyor.

### 3.4 Ajan tanımı `model:` alanı — sağlayıcıya göre eşleme

Mevcut eşleyici `agents/compile.py:46-69` **var ve doğru çalışıyor**:

```python
CLAUDE_FALLBACK_MODEL = "inherit"              # Claude derlemesi: oturumun modelini miras al
AGY_FALLBACK_MODEL = "gemini-3.8-flash-high"   # agy derlemesi: güvenli varsayılan
_GEMINI_MARKERS = ("gemini", "flash", "pro", "gpt")
_CLAUDE_MARKERS = ("claude", "opus", "sonnet", "haiku")
```

Önerilen açık tablo (yürütme yolunda da uygulanacak):

| Kaynak `model:` | → claude | → agy |
|---|---|---|
| `gemini-3.1-pro-*` | `claude-opus-5` | aynen |
| `gemini-3.8-flash-*` / `*-low` | `claude-haiku-4-5` | aynen |
| `gpt-oss-120b-*` | `claude-sonnet-5` | aynen |
| `claude-opus-*` / `opus` | `claude-opus-5` | `claude-opus-4-6-thinking` |
| `claude-sonnet-*` / `sonnet` | `claude-sonnet-5` | `claude-sonnet-4-6` |
| `claude-haiku-*` / `haiku` | `claude-haiku-4-5` | `gemini-3.8-flash-high` |
| boş / `inherit` | oturum modeli | oturum modeli |

**Kritik eksik:** bu tablo yalnızca `compile.py`'de, yani **ajan `.md` dosyası yazılırken** çalışıyor. `build_command`'ın `--model` değeri ve `TaskCard.model` bu tablodan geçmiyor. Faz 9'da `resolve_model` görev yürütme yoluna da bağlanmalı.

---

## 4. Önerilen tasarım

### 4.1 İzole Claude profili — "Entropy Saf Kip"

Yeni ayar: `claude_isolated: bool = True` (varsayılan **açık**; kullanıcı kapatabilir).

`build_command` açıkken şu argv'yi kurar:

```
claude -p <prompt>
  --output-format stream-json --verbose
  --permission-mode <kip>
  --system-prompt-file  <entropy_sistem_istemi.txt>     ← DEĞİŞTİRİR, eklemez
  --strict-mcp-config                                   ← kullanıcının MCP'leri gelmez
  [--mcp-config <entropy_mcp.json>]                     ← yalnızca Entropy'nin MCP'leri
  --setting-sources ""                                  ← user/project/local ayar yüklenmez
  --disable-slash-commands                              ← 32 yetenek kataloğu gelmez
  --tools "Read,Glob,Grep,Edit,Write,Bash,WebFetch,WebSearch"
  --disallowedTools "mcp__*"
  [--agents <entropy_ajanlari.json>]                    ← Entropy'nin kendi ajanları
  --add-dir <proje_dizini>                              ← dosya erişimi, yapılandırma DEĞİL
  --model <doğrulanmış claude modeli>
  --fallback-model claude-sonnet-5
  --effort <seviye>
  [--max-budget-usd <kart bütçesi>]
  [--resume <oturum kimliği>]
```

**Çalışma dizini:** `%USERPROFILE%\.entropy\workspace` — **git deposunun dışında olmalı** (§1.2 kanıtı). Proje dosyalarına erişim `--add-dir` ile verilir; belge: *"Grants file access; Claude Code doesn't discover most `.claude/` configuration from these directories."*

**`--bare` KULLANILMAZ** — aboneliği kullanamaz (§2.2 uyarısı). `CLAUDE_CONFIG_DIR` de varsayılan olarak boş kalmalı; ayrı profil yeniden giriş demektir ve bu kullanıcının açık kararı olmalı (mevcut yorum `config.py:141-145` doğru).

**Sistem istemi içeriği** (`--system-prompt-file`): Entropy kimliği + yetenek bandı + bilişsel bağlam + ajan manifesti + sohbet özeti. Bugünkü part14 (7.844 ch) çekirdek olarak korunur; Claude Code'un 12.438 karakterlik varsayılanı tamamen düşer. **Not:** varsayılan istem düştüğü için Entropy'nin isteminde araç kullanım kuralları (Read/Edit/Bash sözleşmesi, dosya okumadan düzenleme yapma vb.) **açıkça yazılmalı** — aksi halde model araçları yanlış kullanır. Bu, Faz 9'un en riskli parçasıdır ve A/B ölçümü gerektirir.

### 4.2 Arka plan kartlarına kimlik verilmesi

`_execute_background_task_worker` içindeki `build_command` çağrısına `append_system_prompt=` yerine yeni `system_prompt=` parametresi eklenir; içerik: Entropy kimliği + kart ajanının manifesti + kartın bilişsel bağlamı. Sohbet ve kart yolları **tek** istem kurucudan beslenir.

### 4.3 Model doğrulama — üç kapı

1. **Yazma kapısı** — `set_model()` (`claude_bridge.py:445`) ve agy karşılığı: sağlayıcıya ait olmayan adı **reddeder**, `bus`'a uyarı yayar, ayara yazmaz.
2. **Okuma kapısı** — `__init__` yedek değerini de doğrular:
   ```python
   default_model = cfg.provider_models.get("claude", "")
   if not _is_claude_model(default_model):
       default_model = CLAUDE_MODELS[0]
   ```
3. **Göç kapısı** — `config.load_settings()` açılışta zehirli `provider_models` değerlerini onarır ve günlüğe yazar (bugünkü `settings.json` bu onarımla düzelir).

Ek: `build_command` `--model` eklemeden önce son bir `_is_claude_model` süzgeci; `TaskCard.model` doluysa `resolve_model(spec, provider)` üzerinden geçirilip `bridge.set_model_for_run()` ile o koşuya uygulanır.

**Defter şeması:** `tasks` tablosuna `model TEXT` sütunu eklenir (ALTER TABLE, geriye dönük uyumlu), `provider` ile birlikte yazılır.

### 4.4 Model listeleri

- `agents_widget.FALLBACK_MODELS["agy"]` → `["gemini-3.1-pro-high", "gemini-3.8-flash-high", "gemini-3.8-flash-low"]` (canlı `agy models` çıktısından).
- `config.available_models` sabit listesi kaldırılır; kaynak tek: `bridge.fetch_available_models()` + sağlayıcı başına yedek.
- `models_for_provider` (`agents_widget.py:186`) etkin köprü başka sağlayıcıdaysa **o sağlayıcı için geçici köprü kurmak yerine** sabit doğrulanmış listeyi verir (bugünkü davranış doğru, yalnızca liste bayat).
- **Desk kadro/kart formlarına model alanı eklenir** (bugün hiç yok): sağlayıcı seçimine bağlı `QComboBox`, boş = "oturumun modelini miras al".
- Üst çubuk model kutusu **düzenlenebilir kalır** ama `_on_model_selected` yalnızca doğrulanmış adı `set_model`'e geçirir; geçersizse kutuyu eski değere döndürüp ipucu gösterir.

### 4.5 Üst çubuk rozetleri

Hedef ≤ 160 px. Ölçülen seçenekler (Segoe UI 12px, rozet başına 2×6 px dolgu + 6 px boşluk dahil):

| Seçenek | Metin | Toplam | Durum |
|---|---|---:|---|
| A | `AGY ✓` + `Claude ✓ max` | 234 px | aşıyor |
| **D** | `AGY ✓` + `CC ✓` | **138 px** | ✅ |
| **E** | `⬤AGY` + `⬤CC` | **114 px** | ✅ (en dar) |
| B | `AGY` + `CC max` | 138 px | ✅ |

**Öneri: Seçenek D** — `AGY ✓` / `CC ✓`, durum **renkle** taşınır:

| Renk | Anlam | Sabit |
|---|---|---|
| 🟢 `#00FF9D` | oturum açık | `COLOR_OK` (mevcut) |
| 🟡 `#E3B341` | yenileniyor / uyarı | `COLOR_WARN` (mevcut) |
| 🔴 `#FF4D4D` | oturum kapalı | `COLOR_BAD` (mevcut) |
| ⚪ `#8B949E` | henüz ölçülmedi | `COLOR_UNKNOWN` (mevcut) |

Renk paleti **zaten doğru** (`provider_badge.py:33-47`); değişmesi gereken yalnızca `status_text()`'in ürettiği metin.

**Ayrıntılar ipucuna taşınır** (`status_tooltip` zaten hepsini içeriyor, `:69-92`): hesap, plan, kota, oturum penceresi, son hata, ölçüm anı.

**Metin düzeltmeleri:**
- `identity.py:203` — `"süresi doldu (yenilenecek)"` → `"otomatik yenilenecek"`; belirteç süresi dolduğunda rozet **sarı**, kırmızı değil (agy kendisi yeniliyor).
- `identity.py:169-171` — Claude `quota_hint = f"abonelik: {plan}"` kaldırılır; plan zaten rozette. "max · abonelik: max" tekrarı biter.

### 4.6 "Yalnızca Claude" modu

- `config.provider` tek gerçek kaynak olur; **sabit `"agy"` varsayılanları `config.provider`'dan okuyan bir yardımcıya** (`default_provider()`) çevrilir — `tasks.py`, `registry.py`, `desk_registry.py`, `harness.py`, `provider.py:699-701`.
- Açılışta `identity.probe_agy()` başarısızsa ve `probe_claude()` başarılıysa **provider otomatik `claude`'a düşer** ve kullanıcıya tek satırlık bilgi verilir (sessiz düşme yok).
- Yeni kart/ajan/ofis oluşturma formlarında sağlayıcı ön seçimi `config.provider`.
- Regresyon testi: agy ikilisi PATH'te yokmuş gibi davranan bir fikstürle sohbet + kart + ofis + damıtma uçtan uca koşar.

---

## 5. Faz 9 iş listesi

| # | İş | Ajan | Kabul ölçütü | Risk |
|---|---|---|---|---|
| **9.1** | `set_model` yazma kapısı + `__init__` yedek doğrulaması + açılışta `settings.json` onarımı (§4.3) | `agy-integration-engineer` | Yeni test: zehirli `provider_models["claude"]="gemini-3.1-pro-high"` ile köprü kurulunca `selected_model == "claude-opus-5"`; `set_model("gemini-…")` ayarı DEĞİŞTİRMİYOR; canlı `settings.json` bir açılışta onarılıyor | **Düşük.** Tek dosya, davranış daraltıcı |
| **9.2** | `build_command`'a `system_prompt=` yolu (`--system-prompt-file`), `--strict-mcp-config`, `--setting-sources ""`, `--disable-slash-commands`, `--tools`, `--disallowedTools "mcp__*"`; nötr git-dışı cwd; `claude_isolated` ayarı | `agy-integration-engineer` | `build_command` birim testi tüm bayrakları doğru sırada üretiyor; cwd `%USERPROFILE%\.entropy\workspace` ve `git rev-parse` orada başarısız; `--bare` argv'ye GİRMİYOR | **Yüksek.** Varsayılan istem düşünce araç kuralları da düşer → 9.3 ile birlikte gitmeli |
| **9.3** | Yeni Entropy sistem istemi: kimlik + araç sözleşmesi + bilişsel bağlam + ajan manifesti; sohbet ve kart tek kurucudan | `memory-rag-engineer` | İstem ≤ 8.000 karakter; `[SİSTEM BAĞLAMI]` yedek yolu korunuyor; kart yolunda Entropy payı > 0 ch (transcript ölçümü) | **Yüksek.** Araç kuralı eksikse model dosya okumadan düzenlemeye kalkar |
| **9.4** | Arka plan `build_command` çağrısına sistem istemi bağlanması (§4.2) | `agy-integration-engineer` | Yeni kart koşusunun transcript'inde `prompt_snapshot` Entropy bloğu içeriyor; sahte köprü testi argv'de `--system-prompt-file` görüyor | Orta |
| **9.5** | `resolve_model` yürütme yoluna bağlanması + `TaskCard.model` uygulanması + defter `model` sütunu | `agy-integration-engineer` | `provider: claude, model: gemini-3.1-pro-high` olan kart `claude-opus-5` ile koşuyor; defterde `model` doluyor | Orta. Şema göçü geriye dönük olmalı |
| **9.6** | `FALLBACK_MODELS` tazelemesi + `config.available_models` kaldırılması + Desk kadro/kart formlarına model alanı | `ui-engineer` | Dört yerde de (üst çubuk, Entropy ajan formu, Desk kadro, Desk kart) sağlayıcıya uygun liste dolu; agy listesindeki her ad `agy models` çıktısında var | Düşük |
| **9.7** | Kompakt rozet (Seçenek D, ≤160 px) + `identity.py` metin düzeltmeleri | `ui-engineer` | `QFontMetrics` ölçümü ≤ 160 px; ipucu tüm alanları taşıyor; "abonelik: max" tekrarı yok; "süresi doldu" metni yok | Düşük |
| **9.8** | `default_provider()` yardımcısı + 30+ sabit `"agy"` varsayılanının değiştirilmesi + agy yokken otomatik claude düşüşü | `agy-integration-engineer` | agy'siz fikstürde sohbet + kart + ofis + damıtma uçtan uca geçiyor; yeni kart `provider: claude` doğuyor | Orta. Geniş dosya yüzeyi → 9.1–9.7'den sonra |
| **9.9** | `--resume` + `--system-prompt-snapshot` etkileşimi: istem/sağlayıcı değişince `ConversationMap` girdisinin düşürülmesi | `agy-integration-engineer` | Sistem istemi değişince eski oturum sürdürülmüyor, yeni oturum açılıyor (test: `ConversationMap.forget` çağrılıyor) | Orta. Yoksa 9.2/9.3 canlıda etkisiz görünür |
| **9.10** | Ölçüm ve doğrulama: izole kip A/B token ölçümü, tam test paketi, `dist_check` derlemesi | `qa-build-engineer` | Aynı istemle izole/izolesiz iki koşunun ilk tur `cache_creation + cache_read` toplamı raporlanıyor; **hedef: ≥ %30 düşüş**; 1933+ test geçiyor | Orta. Ölçüm gerçek çağrı ister → kullanıcı onayıyla, tek turluk |

**Sıra:** 9.1 → (9.2 + 9.3 birlikte) → 9.4 → 9.9 → 9.5 → 9.6 → 9.7 → 9.8 → 9.10.

**Genel risk uyarısı.** 9.2 + 9.3, Claude Code'un yerleşik araç talimatlarını kaldırıyor. Geri dönüş yolu tek satır olmalı: `claude_isolated = False` ayarı eski `--append-system-prompt` davranışına döner. Bu bayrak Faz 9 boyunca korunmalı, ancak 9.10 ölçümü hedefi tutturduktan sonra varsayılan açık bırakılmalı.

---

## 6. Kaynaklar

**Canlı komut çıktıları (bu makine, kota harcamayan komutlar):**
- `claude --version` → `2.1.265 (Claude Code)`
- `claude --help` → tam bayrak listesi (§2)
- `claude auth status --json` → `{"loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty", "subscriptionType": "max", "projectsDirectory": "C:\\Users\\batu_\\.claude\\projects"}`
- `agy --help`, `agy models` → §3.1
- Gizli bayrak probları (`--system-prompt-file`, `--append-system-prompt-file`, kontrol probu) → §2.1
- `git rev-parse --show-toplevel` (dist içinden) → `C:/EntropiAI` → §1.2

**Kaynak dosyalar (dosya:satır):**
- `C:\EntropiAI\src\entropy\core\claude_bridge.py` — `:86` (max-turns), `:107-119` (gizli bayrak varsayımı), `:146-155` (model listesi), `:266-272` (yabancı model koruması), `:361-383` (`process_env` / `CLAUDE_CONFIG_DIR`), `:392-401` (`fetch_available_models`), `:445-452` (`set_model`), `:528-610` (`build_command`), `:1047-1100` (`build_chat_system_prompt`), `:1163,1178,1192` (sohbet yolu), `:1391-1399,1428` (arka plan yolu — **istem eksik**)
- `C:\EntropiAI\src\entropy\core\config.py` — `:114-129` (sağlayıcı varsayılanları), `:135-146` (`provider`, `provider_models`, `claude_config_dir`), `:174-187` (`available_models`), `:243-254` (yükleme)
- `C:\EntropiAI\src\entropy\core\provider.py` — `:148` (`provider_name="agy"`), `:651-680` (`AGENT_DEFINITION_LAYOUT`), `:688-710` (`create_bridge`), `:713-767` (`switch_provider`)
- `C:\EntropiAI\src\entropy\core\identity.py` — `:155-175` (`probe_claude`), `:177-208` (`_agy_session_window`), `:363-458` (`ConversationMap`)
- `C:\EntropiAI\src\entropy\core\agy_bridge.py` — `:390-419` (`fetch_available_models`), `:787` (`--agent`), `:1431-1467` (`system_directive` prompt gömme)
- `C:\EntropiAI\src\entropy\core\slash_commands.py` — `:183-192` (`/provider`), `:1025-1070` (`/wiki`, `/lint` — model çağırmaz)
- `C:\EntropiAI\src\entropy\agents\tasks.py` — `:87-88,128-129` (`provider`, `model` alanları), `:375-376` (ayrıştırma), `:449-478` (`bridge_for`), `:538` (`[GÖREV SÖZLEŞMESİ]`), `:587-595` (`run_card` — **`card.model` uygulanmıyor**)
- `C:\EntropiAI\src\entropy\agents\compile.py` — `:31-42` (işaretçiler), `:46-69` (`resolve_model`), `:110-112,128-130` (derleme)
- `C:\EntropiAI\src\entropy\agents\harness.py` — `:488,791-792,886-887,1387` (agy düşüşleri)
- `C:\EntropiAI\src\entropy\agents\registry.py` — `:95` (`VALID_PROVIDERS`), `:116,270-371,463-486`
- `C:\EntropiAI\src\entropy\agents\desk_registry.py` — `:128,223,243,414,424,510-512,581`
- `C:\EntropiAI\src\entropy\ui\widgets\provider_badge.py` — `:31-47` (renkler), `:50-66` (`status_text`), `:69-92` (`status_tooltip`)
- `C:\EntropiAI\src\entropy\ui\widgets\agents_widget.py` — `:49-52` (`FALLBACK_MODELS` — **bayat**), `:186-196` (`models_for_provider`)
- `C:\EntropiAI\src\entropy\ui\widgets\effort_selector.py` — `:39-97`
- `C:\EntropiAI\src\entropy\ui\widgets\ui_polish.py` — `:32` (`LABEL_PX = 12`), `:121-141` (`apply_model_placeholder`)
- `C:\EntropiAI\src\entropy\ui\modes\zen_mode.py` — `:175-199` (model kutusu), `:783-788` (`_on_model_selected`), `:800-812` (`refresh_provider_ui`)
- `C:\EntropiAI\src\entropy\ui\modes\chat_mode.py` — `:321,1164`
- `C:\EntropiAI\src\entropy\desk\roster_panel.py`, `board_panel.py` — **model alanı yok** (`grep -i model` sıfır sonuç)

**Çalışma zamanı kanıtı (salt okuma, yalnızca ölçü):**
- `C:\EntropiAI\.entropy\settings.json` — zehirli `provider_models` (§1.4)
- `C:\EntropiAI\.entropy\logs\entropy.log` — `2026-09-09 20:32:04,086 … kökler=['C:\\EntropiAI\\dist\\EntropyAI']`
- `%USERPROFILE%\.entropy\tasks_ledger.db` — son 12 kayıt, şema (§1.6)
- `%USERPROFILE%\.claude\projects\C--EntropiAI-dist-EntropyAI\{d11ec751…, 78fc98df…, 97b14894…}.jsonl` — sistem istemi parçalanması, eklenti boyutları, token kullanımı (§1.1, §1.3, §1.5)

**Belgeler (web):**
- https://code.claude.com/docs/en/cli-reference — sistem istemi bayrakları, `--bare`, `--safe-mode`, `--restricted`, `--strict-mcp-config`, `--setting-sources`, `--tools`, `--add-dir`, `--max-budget-usd`, `--no-session-persistence`, `--agents`, `--exclude-dynamic-system-prompt-sections`
- https://code.claude.com/docs/en/headless — bare kipin ne yüklemediği ve **abonelikle çalışmadığı**; sistem istemi değiştirme
- https://code.claude.com/docs/en/model-config — takma adlar (`default`, `best`, `fable`, `opus`, `sonnet`, `haiku`, `opusplan`, `opus[1m]`, `sonnet[1m]`, `fable[1m]`), `ANTHROPIC_MODEL`
- `claude-api` yeteneği (paket sürümü, önbellek 2026-06-24) — tam model kimlikleri ve fiyatlar
