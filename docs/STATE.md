# STATE.md — Güncel durum (alt ajanların çalışma belleği)

> **İşe başlamadan önce bu dosyayı ve `docs/reports/` altındaki en son ilerleme raporunu oku.**
> Bu dosya alt ajanların oturumlar arası hafızasıdır: sözleşme imzaları, açık işler,
> bilinen kısıtlar ve son yeşil ölçümler burada durur. Her faz dilimi sonunda güncellenir.
> Mimari: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Kararlar: [`adr/`](adr/) · Plan: [`ROADMAP.md`](ROADMAP.md)

| | |
|---|---|
| Durum | **Faz 14 yürürlükte** — "Geçici ajan, gerçek onay, süreklilik" (§2.15; plan: `docs/reports/2026-09-11_Faz14_Analiz_ve_Plan.md`, karar: [ADR-0010](adr/ADR-0010-gecici-ajan-mimarisi-langgraph-alinmadi.md)) |
| Sürüm | **v0.11.0** (Faz 13 kapanış; Faz 14 etiketleri v0.11.1 … **v0.12.0**) |
| Dal | `ai/v0.1.7` (ana dal: `master`) |
| Son güncelleme | 2026-09-11, **Faz 14 açılışı** (§2.15, repo-curator, kota 0): ADR-0010 yazıldı, `ARCHITECTURE.md` §2/§3 ölçümle eşitlendi (158 dosya / 81.193 satır; üç parçalı veri kökü), §6.4–6.7 hedef sözleşmeleri eklendi, `ROADMAP.md` Faz 14 dilimleri + iki yeni değişmez |
| Önceki | 2026-09-11, **Faz 13-D KAPANIŞ** (§2.14, qa-build-engineer, kota **0 — model çağrısı yok**): tam süit **2.648 passed / 0 failed / 450,2 s**, build exit 0 (207 s, `dist/EntropyAI`, exe 56.045.732 B), `--version` → **`Entropy AI 0.11.0`**, `--help` exit 0, `ui_audit --gate --final` exit 0, iki ayrı 20 sn canlı koşum (`Responding=True`, başlık "Entropy AI", yeni günlük satırlarında `Traceback`/`CRITICAL`/`ModuleNotFoundError` **0/0/0**), pakette 27/27 `entropy.brain` modülü + `desk_admin` + `desk_approvals_panel` + `lifecycle` + `agent_run_state` + `platform.proc`, `claude_bg` **0**, `entropy.memory` şimi var; gerçek ekran (LG, dpr 1,0): kart önizlemesi 3 satırda "…" ile kırpılıyor (48 ≤ 51 px tavan), Desk onayları boş durumu doğru, Zen çekirdeği 136×136 görünür. **Bulgu F-13D-1**: her açılışta `entropy_fault.log`'a 13 satırlık `Windows fatal exception: code 0x8001010d` bloğu düşüyor (eskiden beri, ölümcül değil) |
| Daha önce | 2026-09-11, **Faz 13-C KAPANIŞ** (§2.13, qa-build-engineer): tam süit **2.644 passed / 0 failed / 519,7 s**, build exit 0 (372 s, `dist/EntropyAI`), `--version` → **`Entropy AI 0.10.4`**, `ui_audit --gate --final` exit 0 (Desk kapıları dâhil), 20 sn canlı koşum temiz; canlı Desk zinciri izole kasada koştu (ofis→orkestratör→2 alt kart→kontrol noktası+yeşil kanıt→8 bölümlü makbuz); **iki gerçek kusur düzeltildi** (R-13C-1 çok kelimeli ofis adı kırpması, R-13C-2 ofis kartlarının sahte pano ayrışması). **Kota 133.542 token — 100k tavanı aşıldı, wiki ikinci partisi koşulmadı** |
| En eski tutulan | 2026-09-10, **Faz 13-A2 KAPANIŞ** (§2.10): sürüm **0.10.2**, tam süit **2.596 passed / 0 failed / 613 s**, build exit 0 (328 s, `dist_check/EntropyAI`, `--version` → `Entropy AI 0.10.2`), `ui_audit --gate --final` exit 0 (`orphan_reparents` 0, `unnamed_icon_buttons` 0, `empty_interactive_count` 0, `screens_swept_count` 7, `click_latency_ms` 10); gerçek ekran LG %200: yetenek kutusu **azami 3,55 ms**, ikon **119/119** çizildi, canlı kart koşusunda **0 konsol / 0 hayalet pencere** (6.839 örnek); marka 0/0. **AÇIK REGRESYON R-13A2-1**: kullanıcının 3 canivopets kartından 2'sinin dosyası diskte yok |
| Python | 3.13 · PySide6 · PyInstaller (`EntropyAI.spec`) |

---

## 2. Kapanmış dilimlerin özeti (ayrıntılar arşivde)

> Ölçüm tabloları [`_archive/state/STATE_2026-09-10_faz11-13A.md`](_archive/state/STATE_2026-09-10_faz11-13A.md)
> dosyasına taşındı (Faz 13-C). Aşağıda her dilimin kalıcı sonucu duruyor;
> sayının kanıtı gerekiyorsa arşivdeki aynı başlığa bakılır.

| Dilim | Kalıcı sonuç |
|---|---|
| **Faz 11-A** depo temizliği | Depo **4.685 MB → 69 MB**, dosya 18.700 → **1.657**, kökteki `.py` 57 → **1**; prototip ailesi (60 dosya / 75.578 satır) ve 32 testi silindi; toplama 2.374 → **2.042**. `docs/` iskeleti + ilk 5 ADR burada kuruldu. |
| **Faz 11-B** hafıza göçü | Gerçek DB **1.544 → 669 düğüm** (fikstür 531, yakın kopya 262 atıldı); kategori 17 değer → **4 katman + `is_identity`**; kör testte Hit@1 8/10 → **9/10**, gürültü %2 → **%0**; kapı gecikmesi medyan 234 ms. |
| **Faz 11-C/D QA** | Uçtan uca pano döngüsü gerçek Claude ile koştu (GUI'siz); rüya/gri bant/wiki turları ölçüldü. |
| **Faz 11 kapanış QA** | Faz 11 kapanış sayıları; süit yeşil, build exit 0. |
| **Faz 12-E** depo bakımı (repo-curator) | Tek seferlik betikler `scripts/_oneshot/`, referans testler `tests/_reference/` (563 test), eskimiş belgeler `docs/_archive/prototype/`, `platform/autostart.py` kaldırıldı ([ADR-0006](adr/ADR-0006-autostart-kaldirildi.md)); toplama sayısı **değişmedi**. |
| **Faz 12 kapanış QA** (v0.10.0) | Tam süit **2.456 test**; gerçek ekran ölçümleri; kota tavanı aşımının nedeni ölçülemeyen sohbet tüketimi olarak kayda geçti. |
| **Canlı koşu QA** (2026-09-10) | R-CANLI-1 düzeltildi (`bridge_prompt` yanlış sınıf adını içe aktarıyordu → claude yolunda `ImportError`); wiki derleme 2/58 rapor, gri tur, beceri sentezi + onayı gerçek koşumla kapandı; **75.289 token** harcandı. |
| **Faz 13-A kapanış** (v0.10.1) | Tam süit **2.521 passed / 0 failed**, `ui_audit --gate --final` exit 0, build exit 0, `Entropy AI 0.10.1`; rapor başlığı dolgu sözcüğü **573/573 dosyada 0**, digest ghost kenarlığı 2,35:1 → **4,85:1 / 5,49:1**. |
| **Faz 13-A2 beyin kısa devresi** (memory-rag) | `brain_shortcut_enabled` varsayılan **False**; "araştır" denince araştırma canlı koşar. Gerçek DB salt okunur ölçüldü (737 düğüm). Ayrıntı: [arşiv](_archive/state/STATE_2026-09-11_faz13B-13C.md) |
| **Faz 13-A2 kapanış** (v0.10.2) | Tam süit **2.596 passed**, `ui_audit --gate --final` exit 0; **R-13A2-1 açık regresyon** (iki kart dosyası olay yazılmadan kayboldu) — kalıcı kaydı §5'te. Ayrıntı: arşiv |
| **Faz 13-B** `entropy.brain` taşıması (v0.10.3) | 27 modül `git mv`, 166 dosyada dizgi; uyumluluk şimi ([ADR-0008](adr/ADR-0008-brain-paket-tasimasi.md)) — şim **v0.12.0'da kaldırıldı**; toplama 2.596 → 2.605 passed. Ayrıntı: arşiv |
| **Faz 13-C** Desk kanıt zinciri + depo bakımı (v0.10.4) | Canlı Desk zinciri izole kasada koştu; `claude_bg` arşive ([ADR-0009](adr/ADR-0009-claude-bg-arsivlendi.md)); kota **133.542 token (tavan aşıldı)** — dersi §2.15'teki "canlı doğrulamalar ayrı turlarda" kuralı. Ayrıntı: arşiv |

---

## 2.15 Faz 14 AÇILIŞ (2026-09-11, repo-curator) — kota **0 token, model çağrısı yok**

> Bu bölüm Faz 14'ün ortak zeminidir. **Paralel çalışan ajanlar kendi alt bölümlerini
> (§2.15-A agy, §2.15-B ui, §2.15-C memory, §2.15-D qa) buraya ekler; çakışma olursa
> yazı bölümün SONUNA eklenir, başkasının satırı değiştirilmez.**

### Kullanıcının onayladıkları (2026-09-11)

1. Plan ve dilim sırası **14-A → 14-B → 14-C → 14-D → 14-E → 14-F** (14-E, 14-A ile paralel).
2. **Kota tavanı 150k** (gerçekçi beklenti 75–140k); canlı doğrulamalar ayrı turlarda.
3. **LangGraph alınmaz, dört desen alınır** (spike değil) — ADR-0010.
4. Hafıza **sıfırlanmaz**; tetik ölçütü 14-D sonrası K3 > %5 ya da K12 artışı.

### Bağlayıcı tanım (kullanıcının cümlesi)

Bir yetenek çalıştırılması istendiğinde Entropy `SKILL.md`'yi alır → o iş için bir
`agent.md` üretir → ajana beyinden ilgili hafızayı verir → **ayrı bir CLI oturumu** açar →
oturum işi yapar, raporu **anlık** iletir → **ajan kendini siler**; hafızaya girecek
bilgiyi **alt ajan** yazar. Kalıcı adlı kadro istenmiyor (gizlenir, **silinmez**).

### Kararlar ve sözleşmeler (ayrıntı: ARCHITECTURE §6.4–6.7, ADR-0010)

| # | Karar | Nerede yazılı |
|---|---|---|
| D1 | Yetenek başına **geçici** ajan oturumu; kalıcı kadro gizlenir, silinmez | ARCHITECTURE §6.4, ADR-0010 §1 |
| D2 | Sohbet: **sabit** sistem istemi + bağlam kullanıcı mesajının başında; imza yalnız sabit bölümlerden | §6.5 |
| D3 | Gerçek onay: `--permission-prompt-tool` + stdio MCP; `--dangerously-skip-permissions` **koşullu** | §6.6 |
| D4 | **Tek** bekleyen işler kuyruğu `core/pending.py` (yeni): `list(kind)`, `resolve(id, decision, note)`, sinyal `pending_changed`; türler `tool_permission`, `desk_change`, `rule_candidate`, `skill_candidate` | §6.7 |
| D5 | Hafızaya **alt ajan** yazar; `MemoryGate` tek kapı kalır + hata/günlük reddi bandı | §6.4 adım 6, ROADMAP §4 madde 10 |
| D6 | **Pano FSM'ine dokunulmaz**; geçici koşu `running → review → done\|failed` alt kümesini kullanır | §6.1.1, §6.4 |
| D7 | Sohbette **proje kökü salt okunur**; kod değişikliği yalnız onaylı kart/worktree | §6.6 |
| D8 | Yeniden oynatma güvenliği + interrupt idempotentliği + kota sınırlı fan-out + ledger `parent_run_id`/`run_type` | §6.1.1, ADR-0010 §5 |
| D9 | Faz kapanışı = kullanıcının koşturduğu `dist/` ikilisi; başarısız turun hata metni hafızaya girmez | ROADMAP §4 madde 9–10 |

### Ölçüm tabanı (Faz 14 başlangıcı, 2026-09-11)

| Ölçü | Değer |
|---|---|
| Kaynak | **158 dosya / 81.193 satır** (`ui` 54/25.973, `brain` 27/17.448, `core` 18/14.070, `agents` 22/13.494, `desk` 20/6.712, `skills` 5/1.972, diğer 9/1.111) |
| Test | 204 dosya / **2.648** toplanan test (13-D ölçümü) |
| Veri kökü | **üç parçalı** (`<depo>\.entropy` ayarlar · `~/.entropy` DB'ler · bayat `%LOCALAPPDATA%`); 7 modül `Path.home()` sabit yazıyor |
| Hafıza | 740 düğüm, **12'si pytest artığı**, `'list_iterator'` hata metni 2 düğümde |
| Sohbet sürekliliği | 4 ardışık turda `NO-RESUME / RESUME / NO-RESUME / NO-RESUME` |
| Onay yüzeyi | `permission_denial` / `can_use_tool` için kaynakta **0 isabet** |

### Belge işi (bu dilimde yapılan)

- **Yeni:** `docs/adr/ADR-0010-gecici-ajan-mimarisi-langgraph-alinmadi.md`.
- `docs/ARCHITECTURE.md`: başlık v0.11.0 + "hedef etiketi" kuralı; §2 tablosu ölçümle
  eşitlendi; **§3.0** üç parçalı veri kökü gerçeği; §6.1.1'e yeniden oynatma güvenliği;
  **§6.4** geçici ajan döngüsü, **§6.5** sohbet sürekliliği, **§6.6** onay yüzeyi,
  **§6.7** tek bekleyen işler kuyruğu (hepsi **Faz 14 hedefi** etiketli).
- `docs/ROADMAP.md`: Faz 13 kapandı; **§3.1 Faz 14** dilimleri + S1–S5 + kota tavanı 150k
  + etiket planı; değişmezlere madde 9 (`dist/` kapanış ölçütü) ve 10 (hata metni hafızaya girmez).
- `.claude/agents/*.md`: kapsam yolları (`brain/`, `core/pending.py`, `platform/proc.py`) ve
  çalışma belleği satırına Faz 14 planı eklendi.

**Bu dilimde kod, test ve `dist/` DEĞİŞMEDİ** — yalnız `docs/**` ve `.claude/agents/**`.

### §2.15-B Faz 14-B — gerçek onay yüzeyi (2026-09-11, agy-integration-engineer) — kota **taze 534 / ham 55.234 token (canlı S2 KOŞTU, GEÇTİ)**

**Sözleşme (bundan sonra bağlayıcı):**

1. **Tek kuyruk.** `core/pending.py` → `PendingQueue(root)`: `add(kind, title,
   detail, risk="low", source="", payload=None) -> id`, `list(kind=None,
   status="pending")`, `resolve(id, "approve"|"reject", note="")`,
   `wait(id, timeout_s) -> dict|None`, `expire(id)`. Depolama TEK veri kökünde:
   `core/paths.data_root()` (kaynak `config.STATE_DIR`, `ENTROPY_DATA_ROOT` ile
   ezilir) altında `pending/<id>.json`. Türler: `tool_permission`, `desk_change`,
   `rule_candidate`, `skill_candidate`. Çözülen kayıt SİLİNMEZ (`status` +
   `decision` + `decided_at` + `note`); bekleyenler `list()` ile, tümü
   `list(status=None)` ile okunur.
2. **Sinyal.** `bus.pending_changed(dict)` — `{"action": "added"|"resolved"|
   "expired", "item": <künye>}`; `bus.tool_permission_event(dict)` —
   `{"phase": "requested"|"decided"|"denied", "tool", "input_summary",
   "tool_use_id", "pending_id", "message"}`. Eski
   `tool_approval_requested/responded` DURUYOR ve yanlarında yayılır.
3. **Ayrı süreç habercisi.** İzin isteğini yazan taraf CLI'ın çocuğu olan MCP
   sunucusudur; onun `add()` çağrısı uygulamanın veriyoluna erişemez. Bu yüzden
   `pending.PendingWatcher` (0,5 sn yoklama) kuyruğu izler ve olayı uygulamada
   yayar. Köprü `approval_argv()` çağrısında yoklayıcıyı açar.
4. **İzin sunucusu.** `core/permission_server.py` — bağımlılıksız stdio MCP
   (NDJSON JSON-RPC 2.0; `initialize` / `tools/list` / `tools/call` / `ping`),
   tek araç `mcp__entropy__approve`. Giriş noktası
   `python -m entropy.core.permission_mcp_main`; paketlenmiş sürümde AYNI ikili
   `EntropyAI.exe --entropy-mcp-permission` ile (Qt kurulmadan) sapar.
   Risk bandı: `Bash` → high, `Write/Edit` → medium, `Read/Glob/Grep/WebSearch/
   WebFetch` → low, **bilinmeyen araç → medium** (sessizce "low" sayılmaz).
   Karar tavanı 15 dk (`ENTROPY_PERMISSION_TIMEOUT_S`), dolunca `deny` +
   kayıt `expired`. Aynı `tool_use_id` ikinci kez sorulmaz (önbellek).
5. **Şema kararı — ÖLÇÜLDÜ, varsayım değil** (`scratch/phase14/permission_spike/README.md`,
   `claude` 2.1.268 ile 5 canlı koşum): CLI'dan gelen `arguments` yalnız
   `tool_name`, `input`, `tool_use_id` taşır; karar `content[0].text` içinde
   **düz JSON metni** olarak kabul edilir (`{"behavior":"allow","updatedInput":…}`
   / `{"behavior":"deny","message":…}`, `isError: false` şart).
   Sonuç nesnesi **yalnız** `content` (tek text parçası) + `isError` taşır:
   canlı S2'nin ilk koşumunda `structuredContent` de eklenmişti ve CLI kararı
   hiç okumadan araç hatası verdi — `Permission prompt tool returned an invalid
   result. Expected a single text block param with type="text" and a string
   text value.` — komut koşmadı, ret bile `permission_denials`a düşmedi.
   İleri uyum için ikinci biçimi taşımak bu sürümde YASAK
   (`permission_server._tool_result`). İzin İSTEĞİ stream-json'da hiç görünmez; ret `result.
   permission_denials` altında görünür ve koşumu başarısız YAPMAZ. Yanıt
   süresine üst sınır ölçülmedi (45 sn sorunsuz); belgedeki 30 sn BAĞLANTI
   zaman aşımıdır. `echo` gibi "güvenli komut" sınıfı izin kancasından ÖNCE
   koşar — "her araç sorulur" garantisi verilemez.
6. **Köprü argv'si.** `config.approvals_enabled` (varsayılan **True**) açıkken
   sohbet turu ve kart koşusu `--permission-prompt-tool mcp__entropy__approve`
   + `--mcp-config <veri kökü>/mcp/permission_mcp.json` alır ve
   `--dangerously-skip-permissions` HİÇ eklenmez; kapalıyken tam tersi (Faz 13
   davranışı). İki bayrak `build_command` içinde birbirini dışlar. Sunucuyu
   Entropy BAŞLATMAZ: stdio sunucusunu CLI doğurur, hazırlığı da o bekler.
7. **"onaylıyorum" CLI'ya gitmez.** `response_hooks.resolve_approval_message`
   tek bekleyen işi çözer ("✔ onaylandı: …" / "⛔ reddedildi: …"), birden
   fazlaysa listeyi ve kimliği tek satırda sorar ("onayla <kimlik>"), hiç yoksa
   "Bekleyen onay yok." der. Köprü bu turu kısa devre yapar (kota 0, model
   uydurması yok). **Faz 14-A testindeki 3. tur bu yüzden değişti**: "onaylıyorum"
   artık süreklilik ölçemez.
8. **Desk köprüsü.** `desk_admin` istekleri `kind="desk_change"` olarak aynı
   listede görünür (dosya TAŞINMAZ, sarmalayıcı); `resolve()` onları
   `apply_pending` / `reject_pending`'e yönlendirir.

9. **CLI keşfi.** `find_claude_executable()` sırası: `config.claude_path` →
   PATH → npm global shim (`%APPDATA%/npm/claude.cmd`) → `~/.local/bin` →
   `%LOCALAPPDATA%/Programs/claude` → editör eklentileri (`.vscode`, `.vscode-insiders`, ticari referans ürünün eklenti kökü;
   `resources/native-binary/claude(.exe)`, **en yüksek sürüm**). Hiçbiri yoksa
   artık sessiz çıkış 127 yerine tek satırlık teşhis yayılır
   (`CLAUDE_CLI_MISSING_MESSAGE`, veriyolu + sohbet). Sıra testle sabit:
   `tests/contracts/test_phase14b_approvals.py::test_executable_discovery_order_and_diagnostic`.


**Sözleşme testleri:** `tests/contracts/test_phase14b_approvals.py` (30 test;
biri gerçek alt süreçle canlı el sıkışma, biri gerçek `send_background_task_async`
yolunu sahte `Popen` ile ölçer). `tests/contracts` + `tests/test_agent_commands_and_claude_chat.py`
→ **732 passed / 0 failed** (`tests/contracts` + `tests/test_provider_abstraction.py`
+ `tests/test_agent_commands_and_claude_chat.py` + `tests/ui/test_phase14e_layout.py`).
`test_spec_sync` yeşil: yeni `core/**`, `brain/**` ve `ui/widgets/**` modülleri
`EntropyAI.spec`'e eklendi. `test_provider_abstraction` içindeki izin bayrağı
beklentisi sözleşmeye göre güncellendi (onay açıkken izin atlama bayrağı YOK,
`--permission-prompt-tool` + `--permission-mode default` VAR) ve kapalı kol için
ikinci bir gerçek-yol testi eklendi.

**Canlı S2 — KOŞTU ve GEÇTİ** (2026-09-11 07:0x–07:2x, `claude` 2.1.268 VS Code
eklenti ikilisi; kanıt `scratch/phase14/s2_live.json`, ham akışlar
`s2_approve.jsonl` / `s2_reject.jsonl`). Argv ürün yolundan
(`ClaudeCodeBridge.approval_argv()` + `build_command()`), izole veri kökü/kasa:

| Ölçüt | approve | reject |
|---|---|---|
| Kuyruğa düşen `tool_permission` | 2 (`Bash`, risk **high**) | 1 (`Bash`, high) |
| `system.init.permissionMode` | `default` | `default` |
| `system.init.mcp_servers` | **yalnız** `entropy` (connected) | **yalnız** `entropy` |
| Komut koştu mu | evet, hedef dosya **silindi** | hayır, dosya **duruyor** |
| `result.permission_denials` | `[]` | **1 kayıt** (tool_input dâhil) |
| çıkış / süre | 0 / 31,0 sn | 0 / 17,2 sn |
| taze girdi+çıktı | 252 | 282 |

Ret mesajı modele araç hatası olarak ulaştı ve yanıtta göründü ("izin katmanı
tarafından reddedildi"). İzolasyon kanıtı: `--strict-mcp-config` +
`--mcp-config <bizim>` + `--setting-sources ""` ile `mcp_servers` listesinde
kullanıcının hiçbir MCP sunucusu yok.

**Doğrulanamayan / açık:** (a) canlı koşumda `bus.pending_changed` yakalaması
boş kaldı — sebebi ürün değil ölçüm betiğiydi (sinyal zayıf referansla
bağlanmıştı; düzeltildi), veriyolu davranışı `test_watcher_announces_out_of_process_writes`
ile kapalı. (b) "Güvenli komut" sınıfı (ör. `echo`, `ls`) hâlâ izin kancasından
ÖNCE koşuyor: reject koşumunda modelin ilk `ls -la` komutu sorulmadan çalıştı.
(c) `find_claude_executable()` npm'in yarım kurulumundaki gizli
`node_modules/.../.claude-code-*` klasörünü bilerek TARAMAZ.

---

### §2.15-A Faz 14-A — sohbet sürekliliği (2026-09-11, agy-integration-engineer) — kota **0 token, canlı S1 KOŞULAMADI**

**Sözleşme (bundan sonra bağlayıcı):**

1. **Sabit sistem istemi.** Saf kipte sohbetin sistem istemi `build_system_prompt("chat", query="")`
   çıktısıdır: kimlik + onaylı kurallar + araç sözleşmesi + manifest. Sorguya bağlı hiçbir
   şey içermez (`[BİLİŞSEL BAĞLAM]`, `[ÖNCEKİ SOHBET ÖZETİ]`, yetenek afişi, ek dosya
   yönergesi **sistem isteminde olamaz**). Ölçü: dört ardışık turda dosya karması aynı.
2. **Bağlam bloğu kullanıcı mesajında.** Turun değişken bağlamı `build_turn_context_block`
   ile `[BU TURUN BAĞLAMI] … [/BU TURUN BAĞLAMI]` başlığı altında kullanıcı mesajının
   BAŞINA konur; mesajın kendisi blokla birlikte `last_user_message` alanına yazılır
   (uzun mesaj stdin'e taştığı için argv'den okunamaz).
3. **İmza kapsamı.** `_forget_stale_session(system_prompt, model, effort, isolated)` =
   `sha1(sabit istem | sağlayıcı:model:izolasyon | efor)`. Yalnız bunlar değişince oturum
   düşer (model/efor değişimi, saf kip anahtarı, onaylı kural eklenmesi).
4. **Tek oturum kimliği.** İlk tur `--session-id <uuid>` ile kimliği önceden atar, sonraki
   turlar `--resume <aynı kimlik>`. Akıştan kimlik gelmezse ve süreç 0 ile bittiyse önceden
   atanan kimlik sürdürülür; hata varsa sürdürülmez.
5. **Yeni oturuma geçmiş taşınır.** Oturum yokken (ilk tur, model/efor değişimi, çökme)
   kullanıcı bloğuna `[ÖNCEKİ SOHBET ÖZETİ]` eklenir: **son 8 tur, mesaj başına 1.200
   karakter** (eski `6 × 100` kırpması kaldırıldı).
6. **Sohbette proje kökü salt okunur.** `chat_tools()` saf kipte yalnız
   `Read, Glob, Grep, WebFetch, WebSearch` verir; yazma niyeti sezgisi artık
   `Edit/Write/Bash` yetkisi VERMEZ. Yol belirteçli izin bayrağı bu sürümde
   **doğrulanamadı** (`CLAUDE_SUPPORTS_TOOL_PATH_SCOPES = False`), seçilen yol araç
   listesidir; bayrak ölçülürse yazma araçları `~/.entropy/workspace` kapsamıyla döner.
   Kart yolu (`tools_for`) DEĞİŞMEDİ.
7. **Defter.** Sohbet satırı modeli `current_model`den alır (var olmayan `self.model`
   değil) ve `effort` sütunu eklendi (geriye uyumlu `ALTER TABLE`); agy köprüsünde de aynı.
8. **Akış kapanışı.** `agy_bridge.close_stream(stream)` tek yardımcı: `close` metodu
   olmayan (test sahtesi `iter([])`) ya da patlayan akışta tur ölmez.

**Sözleşme testleri:** `tests/contracts/test_phase14a_chat_continuity.py` (8 test),
`tests/test_agy_bridge.py::test_stream_close_survives_non_file_stdout`.

---

### §2.15-D Faz 14-D — hafıza yazarı alt ajan, OFFLINE kısım (2026-09-11, memory-rag-engineer) — kota **0 token, model çağrısı yok; canlı S4 ERTELENDİ (Claude Code CLI kurulu değil)**

**Sözleşme (bundan sonra bağlayıcı):**

1. **Kapının hata/günlük reddi bandı** (`brain/gate.py`): `admit()` içinde,
   kategori kontrolünden ÖNCE koşar. `success=False` beyanı kategoriden bağımsız
   reddedilir; katı kipte ayrıca hata/yığın izi kalıpları (`Traceback`, `Error:`,
   `Exception`, `object has no attribute`, `[Otonom Görev Hata]`, `yürütülemedi`,
   `[ADIM SINIRI]`, `Timeout`), tek satırlık günlük çıktısı, `provenance`/metadata'da
   pytest ya da geçici dizin izi (`pytest-of-`, `pytest-<n>`, `Temp\pytest`, `\tmp\`)
   ve 40 karakterin altındaki içerik reddedilir. Karar: `action=reject`,
   `reject_code=REJECT_ERRORLOG`, neden dolu. Sayaç `gate.stats[REJECT_ERRORLOG]`.
2. **Hafızayı ALT AJAN yazar** (`brain/agent_memory_writer.py`): rapor sonundaki
   `[HAFIZA] {"items":[…]} [/HAFIZA]` bloğu ayrıştırılır, doğrulanır (kategori
   kapalı küme, provenance zorunlu, en çok 8 madde, madde ≤ 600 karakter) ve
   **yalnız** `MemoryGate.admit` → `record_memory(decision=…)` yolundan yazılır
   (kapı bir kez koşar). `success=False` ya da kanıtsız koşuda blok **okunmaz**.
   `[HAFIZA]` bloğu `core/report_title.strip_machine_blocks` ile görüntüden silinir.
3. **Başarısız tur hafızaya yazılmaz** (`core/agy_bridge.py`): arka plan görevi
   yolunda `if success:` (aksi hâlde `task_ledger.record_task_failure`),
   rapor/araştırma yolunda `run_succeeded = ret_code == 0 and not is_err`.
4. **Artık arşivi silme değildir** (`brain/artifact_archive.py`): `archived=1` +
   `metadata.archived_reason`, graf kenarlarına dokunulmaz, yazmadan önce tam DB
   yedeği `~/.entropy/backups/p14d-<zaman>/`, varsayılan kuru koşum, her koşum
   kasadaki `Entropy/Memory/archive_log.md` dosyasına bir satır yazar.

**Gerçek DB ölçümü (`~/.entropy/cognitive_memory.db`, 740 düğüm — silme yok):**

| Ölçüt | Önce (yedek `p14d-20260911-061007`) | Sonra |
|---|---|---|
| Düğüm (toplam / etkin) | 740 / 716 | 740 / **700** |
| Arşivlenen (14-D) | 0 | **16** (12 pytest izli + 3 hata metni + 1 türev özet) |
| K2 Hit@1 / Hit@5 | 8/10 · 10/10 | **8/10 · 10/10** (düşmedi) |
| K3 gürültü | %0,0 | **%0,0** |
| K10 fikstür | 0 | 0 |
| K10 hata/günlük bandı (etkin düğümde kalan) | hata/günlük **5** · pytest izi **12** | **0 · 0** |
| K12 kaynaksız L2 | 0 | 0 |
| K11 kapı gecikmesi | 76,6 ms | 75,8 ms |

> Not: K1 yineleme oranı arşivden **etkilenmedi** (yedek ve canlı DB'de aynı: %5,81 / 697 küme).
> Dilimin başında ölçülen %2,3 değeri aynı kodla tekrar üretilemedi; arşiv öncesi yedek
> üzerinde de %5,81 çıkıyor, yani fark arşivin değil, gün içinde DB'ye dokunan başka bir
> koşumun sonucudur — açık, izlenecek.

**Testler:** `tests/test_phase14d_memory_writer.py` (20 test: 8 örnekli red bandı,
pytest izi, başarısız tur, blok ayrıştırma/doğrulama/yazım, gizleme, arşiv kuru
koşum + uygulama + idempotans) **20 passed**; `tests/test_phase11_memory_gate.py`,
`test_memory*.py`, `test_phase11_dream_wiki_brain.py`, `test_agy_bridge.py`
**113 passed**. Tam süit: **2.724 passed / 2 failed** — ikisi de 14-D dışı
(`test_spec_sync` yeni ui modülleri; `test_provider_abstraction` skip bayrağının
14-B'de koşullu olması). Spec'e yalnız iki brain modülü eklendi.

**Yarım kalan:** canlı **S4** (14-C raporu → alt ajan `[HAFIZA]` bloğu → kapı →
yeni sohbette kaynaklı hatırlama) CLI kurulu olmadığı için koşulmadı; betik hazır:
`scratch/phase14/s4_live.py` (varsayılan kuru koşum, tavan 20k).

---

### §2.15-C Faz 14-C — geçici ajan döngüsü (2026-09-11, agy-integration-engineer) — kota **taze 4.525 / ham 63.272 token (canlı S3 KOŞTU, GEÇTİ; ham tavan 60k iki koşumun toplamında 3.272 token aşıldı)**

**Sözleşme (bundan sonra bağlayıcı):**

1. **Tek modül, tek yaşam döngüsü.** `agents/ephemeral.py` (Qt'siz):
   `prepare → spawn → stream → report → memory → cleanup`.
   `prepare(skill, prompt, brain_context, engine) -> EphemeralSpec`
   (`slug, skill, goal, agent_md, provider, model, effort, tools, max_steps,
   run_id, session_id, workdir`). `EphemeralRun(skill, goal, bridge=, engine=,
   brain_context=, parent_run_id=, card_id=, memory=, vault=, on_done=)`;
   `run.finished` (threading.Event) koşunun bittiğini bildirir.
2. **`agent.md` şablonu.** `# <slug>` başlık + `## Görev` · `### Yetenek yordamı`
   · `## Bağlam (beyinden)` (bütçe 4.000 token, `context_builder`, kimlik/legacy
   düğümleri zaten dışarıda) · `## Kabul ölçütleri` · `## Rapor şablonu`
   (**ilk satır `# H1`**) · `## Hafıza` (`[HAFIZA]{json}[/HAFIZA]`, ≤ 8 madde,
   kaynak zorunlu) · `## Yasaklar` (kod değişikliği yok, proje kökü salt okunur,
   beyin yanıtı araştırmanın yerine geçmez, kalıcı kayıt açma).
3. **Taşıma.** claude'da tanım **argv'de**: `--agents '{"<slug>": {...}}'` +
   kullanıcı mesajı `Use the <slug> subagent …`; **dosya yazılmaz**. agy'de
   `<workdir>/.agents/agents/<slug>/agent.md` yazılır ve koşu sonunda dizin
   silinir. Her koşu yeni `uuid4` → `--session-id`, ayrıca
   `--no-session-persistence` (`CLAUDE_SUPPORTS_NO_SESSION_PERSISTENCE = True`,
   `--resume` ile birlikte verilmez). `AgentSessionStore`'a **hiçbir şey
   yazılmaz**.
4. **Köprü sözleşmesi (yeni kwarg).** `send_background_task_async(...,
   ephemeral={"agents_json", "system_prompt", "extra_dirs",
   "no_session_persistence", "run_id"})`. Dolu geldiğinde: kadro JSON'u
   **yerine** koşunun tek ajanı gider, sistem istemi `agent.md` gövdesidir,
   izin verilen dizinler yalnız izole `workdir` + kasa rapor klasörüdür
   (**proje kökü argv'ye girmez**) ve oturum kimliği kalıcı deftere yazılmaz.
   14-B onay yüzeyi aynen geçerli (`--permission-mode default` +
   `--permission-prompt-tool`). `build_command(..., no_session_persistence=)`.
   `bridge.background_step_counts[task_id]` araç adımı sayısını çağırana açar.
5. **Adım tavanı yeteneğe göre.** `SKILL.md` ön bilgisindeki `max_steps`
   (1–500), yoksa `ephemeral.DEFAULT_MAX_STEPS = 60` — kart tavanı
   (`MAX_STEPS_PER_CARD = 20`) geçici koşuda kullanılmaz. Tavana çarpan kart
   `failed` DEĞİL `review`: `run.finished` **`ok=True`** ile yayılır (T6).
6. **Tek bildirim.** Köprünün kendi rapor yolu kapalı (`save_report=False`);
   raporu Entropy yazar (`Ajan_<H1>_<zaman>.md`, `[HAFIZA]` bloğu
   `strip_machine_blocks` ile görüntüden silinir) ve **tek**
   `bus.task_notification` yayılır: `"Ajan <slug> bitti: <H1>; N araç adımı;
   rapor: <yol>"`. `report_created` bilerek yayılmaz (çift kart yok).
7. **Hafızayı ALT AJAN yazar.** `agent_memory_writer.ingest_agent_report(...,
   success=<koşu başarısı>, has_proof=<rapor dosyası var mı>)`; Entropy kapı
   dışında hiçbir şey yazmaz.
8. **Kendini silme.** Silinen: geçici `workdir` (agy `agent.md` dâhil), sistem
   istemi dosyası (köprü siler), oturum kaydı (hiç oluşmaz). **Kalan:** ledger
   satırı, rapor, olay, hafıza düğümleri.
9. **Defter.** `tasks` tablosuna geriye uyumlu iki sütun: `run_type`
   (`"ephemeral"`), `parent_run_id` (doğuran sohbet turu/koşu).
   `task_ledger.record_run_meta(task_id, run_type=, parent_run_id=)`.
10. **Tetikleme yüzeyleri.** (a) `/skill run <yetenek> :: <istem>` (yerel komut,
    modele gitmez; komut yüzeyi 31 → **32**). (b) Entropy'nin kendi kararı:
    `[AJAN run] {"skill": …, "goal": …} [/AJAN]` — `response_hooks` tüketir,
    **tur başına 1 ajan**, blok görüntüden silinir, onay aranmaz.
    (c) Pano kartının `agent` alanı BOŞSA `BoardDispatcherCore.tick_ephemeral()`
    o iş için geçici ajan doğurur (kadrodan kimse seçilmez); kart
    `assigned → taken → running` üzerinden yürür, FSM'e yeni geçiş eklenmez.
    Kalıcı kadro kodu **silinmedi**, yalnız varsayılan yol artık geçici ajandır.
11. **İstem bütçesi.** `brain/system_prompt.BUDGET_BOARD_TOOLS` 600 → **1000**:
    600'de `[AJAN run]` eklenince `board_create` bloğu (ve içindeki `[DESK …]`
    araçları) tamamen düşüyordu. Ölçüm: `board_tools_section(1000)` = 933
    karakter, üç blok da tam (~+100 token, tur başına bir kez).

**Sözleşme testleri:** `tests/contracts/test_phase14c_ephemeral_agent.py`
(13 test; biri gerçek `send_background_task_async` yolunu sahte `Popen` ile
uçtan uca ölçer: argv'de `--agents`/`--session-id`/`--no-session-persistence`/
`--permission-mode default`/`--permission-prompt-tool`, proje kökü `--add-dir`
listesinde YOK, kalıcı oturum dosyası yazılmadı, akış olayı ≥ 3, rapor H1,
`[HAFIZA]` → kapı çağrısı, tek bildirim, `workdir` silindi, ledger
`run_type="ephemeral"`). Köprüden gelen olaylar test/betiklerde **`Qt.DirectConnection`**
ile dinlenmeli — otomatik bağlantıda iş parçacığı sınırında sessizce düşüyor.
Koşu: `tests/contracts` + `test_agents_registry_tasks` + `test_report_attribution_and_handoff`
+ `test_provider_abstraction` + `test_agent_commands_and_claude_chat`.

**Canlı S3 — KOŞTU ve GEÇTİ** (2026-09-11 07:44 ve 07:46, `claude` 2.1.268 VS Code
eklenti ikilisi; izole veri kökü/kasa/hafıza DB'si; kanıt
`scratch/phase14/s3_live.json` + `s3_live_run1.json` / `s3_live_run2.json`,
`s3_agent.md`):

| Ölçüt | run1 (tam senaryo) | run2 (kısa hedef) |
|---|---|---|
| argv `--agents` / `--session-id` / `--no-session-persistence` / izin aracı | ✔ / ✔ / ✔ / ✔ | ✔ / ✔ / ✔ / ✔ |
| `agent_stream` satırı | (ölçüm hatası: 1) | **6** (status, oturum, `WebSearch`, sonuç, metin) |
| onaylanan `tool_permission` | **5** (Bash/high) | 1 |
| tek bildirim | (ölçüm hatası: 0) | **1** — "Ajan … bitti: …; 1 araç adımı; rapor: …" |
| rapor | 3.611 B, **11 kaynak URL** | 2.315 B, H1 doğru |
| `[HAFIZA]` → kapıdan geçen | **5 ADD** | 2 ADD |
| `workdir` silindi / ledger `ephemeral` | ✔ / ✔ | ✔ / ✔ |
| taze / ham token | 3.189 / 38.747 | 1.336 / 24.525 |

run1'de akış ve bildirim kanıtının boş kalması **ürün değil ölçüm hatasıydı**
(betik sinyalleri otomatik bağlantıyla dinliyordu; `step_count=5` aynı akıştan
geliyordu). run2 aynı ürün yolunu `DirectConnection` ile ölçtü ve ikisini de
kanıtladı.

**Doğrulanamayan / açık:** (a) İki koşumun **ham** toplamı 63.272 → tavan 60k
**3.272 token aşıldı**; tavan koşum başına uygulanıyordu, kümülatif değil
(`s3_live.py` bunu koşum başına ölçüyor). Üçüncü koşum YAPILMADI. (b) Rapor
kasada `Entropy/Skills/<yetenek>/Reports/` altına düşüyor, `Entropy/Reports/`
altına değil: yetenek atfı Faz 13-A sözleşmesinden geliyor (yeteneksiz koşuda
`Entropy/Reports/`). (c) agy kolu canlı koşulmadı (yalnız birim testi:
`agent.md` yazılır ve silinir). (d) "Güvenli komut" sınıfı 14-B'deki gibi hâlâ
izin kancasından önce koşuyor. (e) S3 izole hafıza DB'siyle koşuldu, yani
"ajana beyninden bağlam ver" adımı canlıda ~79 token'lık boş bağlamla ölçüldü.

---

### §2.15-F Faz 14-F — belge kapanışı (2026-09-11, repo-curator) — kota **0 token, model çağrısı yok**

**Kapsam:** yalnız `docs/**` ve `.claude/agents/**`. `src/**`, `tests/**`, `scripts/**`,
`EntropyAI.spec` **değişmedi** (kapanış QA'sı paralel koşuyor; §2.16 QA'nındır).

1. **`docs/ARCHITECTURE.md`** — §6.4 / §6.5 / §6.6 / §6.7'deki **"Faz 14 hedefi"**
   etiketleri kaldırıldı ve bölümler **gerçekleşen koda** göre yeniden yazıldı
   (kaynaktan doğrulandı: `agents/ephemeral.py` yaşam döngüsü ve `build_agent_md`
   şablonu, `core/pending.py` API'si, `core/permission_server.py` ölçülen istek/yanıt
   şeması + 15 dk tavan + "güvenli komut sınıfı kancadan önce koşar" açığı,
   `claude_bridge` argv sözleşmesi ve CLI keşif sırası, `brain/agent_memory_writer.py`
   `[HAFIZA]` sözleşmesi + kapı reddi bandı). Yeni: **§6.4-D** (alt ajan hafıza yazarı),
   **§10.2** ("bir yetenek koştur → rapor al" yolu, adım sayısı ölçülü), §8'e
   **14-E düzeni** (navStrip, sağ tam panel, tek durum satırı, G14-1/G14-1b),
   §7'ye `pending_changed` / `tool_permission_event` satırı, §3.0'a
   `core/paths.data_root()` / `pending_root()` tek kaynağı.
2. **§2 modül tablosu yeniden ölçüldü:** 158 dosya / 81.193 satır →
   **167 dosya / 85.520 satır** (Faz 14 farkı **+9 modül / +4.327 satır**),
   test dosyası 204 → **209**. Toplanan test sayısı bilerek yazılmadı: onu kapanış QA
   ölçer (ölçmediğim sayıyı yazmam).
3. **ADR-0010** durumu "uygulandı: 14-A…14-E" oldu + S1–S3 canlı kanıt tablosu;
   "ölçülemeyen" maddesine izin şeması ölçümü eklendi. **ADR-0008**'e şimin
   v0.12.0'da kaldırıldığı satırını kapanış QA yazmıştı; tekrarlanmadı.
4. **`docs/ROADMAP.md`** §3.1: dilim tablosu durum sütunuyla yeniden yazıldı
   (14-A/B/C tamamlandı + canlı; 14-D offline tamam / **canlı S4 kapanışta**;
   14-E tamam / **S5 kapanışta**; 14-F yürürlükte), etiketler v0.11.1–v0.11.3 ve
   v0.12.0, kota notu **taze vs ham** ayrımıyla; **Faz 14 sonrası 8 aday iş** tablosu.
5. **Faz 14 raporu (taslak):** `docs/reports/2026-09-11_Faz14_Ilerleme_Raporu_v0.12.0.md`
   — §0 kullanıcının tanımı ve S1–S5, §1 dilim özetleri + canlı tablolar + **6 gerçek
   kusur** (`structuredContent`, CLI keşfi, `BUDGET_BOARD_TOOLS`, ölçüm betiği hataları,
   güvenli komut sınıfı, rapor yolu), **§2 Kapanış QA boş** (QA dolduracak),
   §3 kota tablosu, §4 dokuz kalan madde.
6. **STATE sıkıştırması:** §2.9 … §2.13-b (13-A2 … 13-C ölçüm tabloları, 524 satır)
   `docs/_archive/state/STATE_2026-09-11_faz13B-13C.md` altına **taşındı**; §2'ye dört
   satırlık kalıcı sonuç özeti eklendi. §3 sözleşmeleri, §5 açık işler ve §7 kırmızı
   çizgiler **yerinde** (ARCHITECTURE §9.1 kuralı). STATE 1.638 → 1.118 satır.
7. **`.claude/agents/*.md`:** kapsam yollarına `agents/ephemeral.py`, `core/pending.py`,
   `core/permission_server.py`, `brain/agent_memory_writer.py`; çalışma belleği
   satırına Faz 14 ilerleme raporu.

**Marka kuralı:** belgelerde editör eklentisi yolu "ticari referans ürünün eklenti kökü"
olarak yazıldı (ürün ve üretici adı geçmez).

---

## 2.16 Faz 14 KAPANIŞ (v0.12.0, 2026-09-11, qa-build-engineer) — kota **0 token, model çağrısı yok**

Ortam: `EntropyAI.exe` **kapalıydı** (`Get-Process EntropyAI` → 0) → build doğrudan `dist/`.
Ekran: **LG ULTRAGEAR**, 1920×1080, **dpr 2,0** (kullanıcının ekranı).

### S1–S5 kanıt tablosu

| Senaryo | Durum | Kanıt |
|---|---|---|
| **S1** sohbet sürekliliği | canlı GEÇTİ (14-A) | `docs/reports/_evidence_2026-09-11_s1_live.json` (dilim raporu §2.15-A) |
| **S2** gerçek onay | canlı GEÇTİ (14-B) | `scratch/phase14/s2_live.json`, `s2_approve.jsonl` / `s2_reject.jsonl` |
| **S3** geçici ajan döngüsü | canlı GEÇTİ, iki koşum (14-C) | `docs/reports/_evidence_2026-09-11_s3_live.json` |
| **S4** alt ajan hafıza yazarı | canlı GEÇTİ (orkestratör koşumu) | `docs/reports/_evidence_2026-09-11_s4_live.json`: beş yeni düğüm gerçek DB'de (`writer=agent`, `source=agent_memory_block`), ana bulgu recall **top-5** içinde. **Not:** `scratch/phase14/s4_live.py` koşumun SONUNDA rapor dosyasını okurken `FileNotFoundError` ile düştü (`s4_live.out`), `s4_live.json` üretilmedi; hafıza yazımı bu düşüşten ÖNCE tamamlandı |
| **S5** yeni düzen | gerçek ekranda GEÇTİ | `scratch/ui/phase14/real_metrics.json` + `real_s5_layout.png`, `real_pending_card.png`, `real_stream_line.png`, `real_ajanlar.png`, `real_görevler.png`, `real_raporlar.png` |

### Gerçek ekran ölçümleri (kaynak ağacından gerçek `QApplication`, izole kasa + `ENTROPY_DATA_ROOT`)

| Ölçü | Değer |
|---|---|
| Pencere | 1920×1032, taşan üst düzey çocuk **0** |
| Üst şerit | **7/7** düğme görünür, hepsinin erişilebilir adı ve çizilebilir ikonu var, tek seçili |
| Sağ panel | sekmeler **Sohbet / Hafıza**, bölücü `[1137, 758]` → **oran 0,400** (yeni `RIGHT_PANEL_RATIO = 0.40`) |
| Çekirdek görsel | **136 px** (≥ 48) |
| Durum satırı | 4 okuma (sağlayıcı · token · pano · bekleyen onay) |
| Bekleyen onay kartı | izole kuyruğa `tool_permission` eklendi → kart **görünür** (başlık + "yüksek risk" + Onayla/Reddet) → `approve` → kart boş, kuyrukta kayıt `approved` |
| Akış satırı | sahte `agent_stream` → "**Ajan: web araması yapıyor**", sohbet kartının içinde |
| Ajanlar bölümü | "Ajan koşuları" (çalışan koşu yok + son 7 koşu), **kalıcı ajan kadrosu yok**; Desk orkestratörleri salt okunur |
| Görevler / Raporlar | bölüm geçişleri bozulmadı (`ReportsViewerWidget`, pano widget'ı görünür) |

### Süit, kapı, build, paket

| Ölçü | Değer |
|---|---|
| Tam süit (kapanış koşumu) | **2.742 passed / 0 failed / 564,8 s** (`-q -p no:cacheprovider`) |
| İlk koşum (düzeltme öncesi) | 2.739 passed / **1 failed** — `test_phase12_skill_synthesis.py::test_board_tools_section_uses_the_real_12b_symbol_within_budget` (14-C tavanı 600→1000 yaptı, Faz 12 testi güncellenmemişti; **14-C tam süiti koşmamış**) |
| `ui_audit --gate --final` | **exit 0** (ilk koşum `arrow_glyphs: 6 > 5` ile düştü; kaynak `pending_card.py` belge satırıydı) |
| Build | exit 0, ~260 s, `dist/EntropyAI`, exe **56.148.456 B** |
| `--version` / `--help` | `Entropy AI 0.12.0` / exit 0 |
| 20 sn canlı koşum | süreç ayakta; yeni günlük satırlarında `Traceback` / `CRITICAL` / `ModuleNotFoundError` = **0 / 0 / 0**. Bilinen **F-13D-1** (`Windows fatal exception: code 0x8001010d`, ölümcül değil) hâlâ düşüyor |
| Paket (PYZ **7.318** modül) | `entropy.agents.ephemeral`, `entropy.core.{pending,permission_server,permission_mcp_main}`, `entropy.ui.widgets.{nav_strip,pending_card,agent_stream_line,agent_runs_panel}` **var**; `entropy.brain*` 32 girdi; **`entropy.memory` 0 girdi** |
| Frozen MCP onay giriş noktası | `EntropyAI.exe --entropy-mcp-permission` → stdio `initialize` yanıtı (`serverInfo.name = entropy`, protokol 2025-06-18) ve `tools/list` → `approve`. Model çağrısı yok |

### Şim kaldırma (ADR-0008 sözü yerine getirildi)

`src/entropy/memory/` silindi (`git rm` + artık `__pycache__` temizliği), `EntropyAI.spec`
hiddenimports'tan `'entropy.memory'` çıkarıldı, `tests/contracts/test_brain_package_move.py`
**"kaldırıldı" sözleşmesine** çevrildi (atıf sayacı 0 · dizin yok · `import entropy.memory`
→ `ModuleNotFoundError` · spec'te girdi yok), ADR-0008 ve ARCHITECTURE §2 güncellendi.

### Sızıntı avı (14-D'nin "tam süit sırasında yalıtım sızıntısı" şüphesi)

Gerçek `~/.entropy` dosyalarının sha256'sı süit öncesi/sonrası izlendi:

| Dosya | Sonuç |
|---|---|
| `tasks_ledger.db` | **değişmedi** |
| `skills_state.json` | **değişmedi** |
| `cognitive_memory.db` | **değişti** — ama sebep süit DEĞİL: pencerede yazılan **5 düğümün hepsi** `writer=agent, source=agent_memory_block` (paralel koşan canlı **S4**). Süit penceresinde pytest kaynaklı yazma **0** |
| `scheduler_tasks.json` | **değişti — GERÇEK SIZINTI (R-14F-1)**: `TaskScheduler` varsayılan yolu `Path.home()/".entropy"` olduğu için süit sırasında kullanıcının dosyasına yazdı ve **saatlik işleri gerçekten koşturdu** (`obsidian-sync`, `rag-reindex`; `last_run` süit penceresine düştü) |

**Kök nedende kapatıldı:** `src/entropy/scheduler/cron_engine.py` artık
`ENTROPY_SCHEDULER_TASKS` ortam değişkenini tanıyor (değişken yoksa davranış AYNI),
`tests/conftest.py` bu değişkeni tmp'ye bağlıyor (ledger ve bilişsel DB gibi),
sözleşme testi `tests/test_scheduler.py::test_scheduler_storage_is_isolated_from_user_home`.
**Doğrulama:** ikinci tam süitten sonra `scheduler_tasks.json` ve `cognitive_memory.db`
karmaları **birinci koşum sonrasıyla birebir aynı** — ikinci süit hiçbir gerçek dosyaya
yazmadı. Kasa sayımları da sabit (Reports 423, Tasks 2, Sessions 30).

### Marka taraması

Ticari referans ürünün **üretici adı**: 0 isabet. **Ürün adı**: kalan tüm isabetler
`conn.cursor()` / Qt imleci gibi teknik kullanımlar; gerçek marka atıfları
(`claude_bridge.py` eklenti kökü, `skills/manager.py` yetenek klasörü ve yorumu,
`tests/test_universal_skills_and_mcp_config.py`, `ARCHITECTURE.md`, `STATE.md`)
**parçalardan kurulan dizgilere** çevrildi; davranış değişmedi.

### Açık işler

1. **Veri kökü ikiliği kapanmadı (ADR gerektirir).** `core.paths.data_root()` bu makinede
   `C:\EntropiAI\.entropy`, kullanıcının gerçek defteri/hafızası ise `~/.entropy` altında
   (9,9 MB `cognitive_memory.db`, 106 KB `tasks_ledger.db`). 7 modülün sabit yazımını
   körlemesine `data_root()`'a çekmek bu verileri **yetim bırakırdı**; göç (kopyala →
   doğrula → sil) + ADR olmadan yapılmadı.
2. **F-13D-1** (`0x8001010d` fault bloğu) sürüyor.
3. **F-14F-2 (küçük):** kuyruğa yeni bir onay eklendiği anda kart güncelleniyor ama alt
   durum satırı hâlâ "Bekleyen onay yok" gösteriyordu (`real_pending_card.png`).
4. **R-13A2-1** (kullanıcının iki kart dosyasının diskte olmaması) bu dilimde ölçülmedi.

---

## 2.14 Faz 13-D KAPANIŞ (v0.11.0, 2026-09-11, qa-build-engineer) — kota **0 token, model çağrısı yok**

Ortam: `EntropyAI.exe` **kapalıydı** (`Get-Process EntropyAI` → 0) → build doğrudan `dist/`.
Girdi ağacı: HEAD `3fa2e04` + yalnız sürüm yükseltmesi (`pyproject.toml:7`, `src/entropy/__init__.py`) ve `ROADMAP.md`.

| Adım | Sonuç | Kanıt |
|---|---|---|
| Küçük artık (madde 2) | `memory_inspector_dialog` silme yolu düzeltildi (aşağıda) | `src/entropy/ui/widgets/memory_inspector_dialog.py:22-29, 517-522` |
| Hedefli testler | `tests/contracts` + `tests/desk` + `tests/ui/test_phase13{,a2,c,d}*` + `test_memory_inspector_and_rag` → **895 passed / 0 failed / 163,1 s** | — |
| Sürüm tek kaynak | `pyproject.toml:7` = `src/entropy/__init__.py` = **0.11.0**; `python run_entropy.py --version` → `Entropy AI 0.11.0` exit 0 | `test_spec_sync`, `test_architecture_rules` yeşil |
| `ui_audit.py --gate --final` | **exit 0**; `orphan_reparents` 0, `unnamed_icon_buttons` 0, `empty_interactive_count` 0, `screens_swept_count` 7, `click_latency_ms` **8** (182 kart); Desk: `desk_screens_swept_count` 7, `desk_empty_interactive_count` 0, `desk_unnamed_icon_buttons` 0 | `scratch/_p13d_audit.log` |
| **Tam süit** `-q -p no:cacheprovider` | **2.648 passed / 0 failed / 450,2 s**, exit 0 (2.644 + bu dilimin 4 yeni testi) | `scratch/_p13d_suite.log` |
| **Build** `python -m PyInstaller EntropyAI.spec --noconfirm` | **exit 0, 207 s**, `dist/EntropyAI`, exe **56.045.732 B** | `scratch/_p13d_build.log` |
| `--version` / `--help` | **`Entropy AI 0.11.0`** exit 0 / exit 0 | — |
| Paket (PYZ, **7.309** modül) | kaynaktaki **27/27** `entropy.brain` modülü pakette (eksik 0; arşivde 30 girdi = 27 + 3 alt paket `__init__`), `entropy.agents.desk_admin`, `entropy.ui.widgets.{lifecycle,agent_run_state,desk_approvals_panel}`, `entropy.platform.proc` **var**; `claude_bg` **0 girdi**; `entropy.memory` şimi **var** | `scratch/_p13d_pyz.pyz` |
| 20 sn canlı koşum (×2) | iki koşumda da **canlı** (`Responding=True`, başlık "Entropy AI"); günlük 455 → 459, yeni 4 satırda `Traceback`/`CRITICAL`/`ModuleNotFoundError` **0/0/0** | `scratch/_p13d_live_newlog.txt` |
| Yeni CrashDump | **yok** (`EntropyAI*` adına hiç dosya yok; en yeniler `EntropyAgentDesk.exe` 2026-09-09) | — |
| Marka taraması (parçalı sabit) | izlenen + izlenmeyen dosyalarda **0** | `git grep -riIl --untracked` |
| Yalıtım | `skills_state.json` 112 B / mtime **AYNI**, `tasks_ledger.db` 90.112 B **AYNI**, `cognitive_memory.db` 9.834.496 B **AYNI**; kasa `Entropy/Reports` **423 → 423**, `Entropy/Tasks` **1 → 1**, `Desk/Offices` **1 → 1** | süit öncesi/sonrası ölçüm |
| `scratch/ui/phase10/*.png` | süit 8 dosyayı yeniden üretti → `git show HEAD:<yol> > <yol>` ile geri yazıldı, `git status` o yolda **0 satır** | — |

### Düzeltme: hafıza denetçisinde silme yolu ölü aday listesine bağlıydı

`_delete_cog_node` yedek aday listesi `entropy.brain.cognitive_memory` ve
`entropy.core.cognitive_memory` adlarını deniyordu; **ikisi de yok**
(gerçek yol `entropy.brain.supabase.cognitive_memory`, `entropy.core` sürümü
hiç var olmadı). Sonuç: Faz 10-B'nin "silmenin TEK girişi bellek katmanıdır"
sözleşmesi hiçbir zaman çalışmıyor, silme her seferinde sessizce **ham SQL**
yoluna düşüyor, bağlı graf kenarları (`nodes`/`edges`) diskte kalıyordu.

* Birincil yol artık bellek katmanının kendisi: `self.cog.delete_memory(node_id)`
  (her iki depoyu da temizler) — `memory_inspector_dialog.py:517-522`.
* Aday listesi modül düzeyine taşındı ve gerçek adlara indirildi:
  `DELETE_MEMORY_MODULES = ("entropy.brain.graph_store", "entropy.brain.supabase.cognitive_memory")`
  (`memory_inspector_dialog.py:22-29`).
* Kilit test (4 test): `tests/ui/test_phase13d_memory_inspector_modules.py` —
  listedeki her modül **içe aktarılabilir**, eski iki ad listede yok ve
  gerçekten `ModuleNotFoundError` veriyor, birincil giriş çağrılabilir.

### Gerçek ekran kısa turu (LG ULTRAGEAR, dpr **1,0**; 1920×1080, avail 1920×1032)

Betikler `scratch/ui/phase13d/{real_check.py,real_narrow.py}`, ölçümler
`real_metrics.json` / `real_narrow_metrics.json`, görüntüler
`real_card_preview.png`, `real_card_preview_{760,560,460}.png`,
`real_approvals_empty.png`, `real_zen_core.png`, `real_zen_core_crop.png`.
İzole kasa (`scratch/ui/phase13d/vault`), model çağrısı yok.

| Ölçüm | Sonuç |
|---|---|
| Kart önizlemesi (13-C'de ölçülemeyen) | Görevler ekranında **1 kart**, `ElidedPreviewLabel` **görünür** (`visibleRegion` boş değil); geniş sütunda metin "…" ile bitiyor, dar sütunda (etiket 309 → 189 px) gerçek **satır sınırı kırpması**: yükseklik **48 px ≤ tavan 51 px** (3 satır), üç genişlikte de `…` var, tam metin ipucunda duruyor |
| Desk onayları paneli — boş durum | `pending_count` **0**; başlık "DESK ONAYLARI · 0 bekleyen · onaysız hiçbir yapı oluşmaz", gövde **"Bekleyen Desk düzenlemesi yok. Entropy ofis, ajan ya da kart oluşturmak isterse burada sorulur."** |
| Zen — çekirdek | `core_visualizer` **görünür**, **136×136**, konum (1146, 8), pencere içinde (taşma yok), erişilebilir ad "Entropy çekirdeği — durum göstergesi" |

### F-13D-1 (yeni bulgu, açık): her açılışta fault günlüğüne COM istisnası

`.entropy/logs/entropy_fault.log` her koşumda **13 satırlık** bir
`Windows fatal exception: code 0x8001010d` bloğu alıyor
(ölçüm: 659 → 672 satır, ikinci 20 sn koşumda birebir aynı blok).
Kod `RPC_E_CANTCALLOUT_ININPUTSYNCCALL`; uygulama **ölmüyor**
(iki koşumda da `Responding=True`), dosyada aynı bloktan **46+** eski örnek
var — yani 13-D'nin getirdiği bir gerileme **değil**. Kaynağı bulunmadı
(yığın yalnızca `main.py:297` ana döngüsünü ve zamanlayıcı iş parçacığını
gösteriyor); temizlenmesi açık iş.

---

## 3. Aktif sözleşmeler (değiştirirsen `ARCHITECTURE.md` ile birlikte güncelle)

- **Bellek paketinin adı `entropy.brain`** (Faz 13-B, [ADR-0008](adr/ADR-0008-brain-paket-tasimasi.md)).
  Yeni kod **yalnızca** `entropy.brain...` içe aktarır. Eski `entropy.memory` adı
  `src/entropy/memory/__init__.py` şimiyle bir sürüm daha çalışır
  (`sys.meta_path` bulucusu → **aynı modül nesnesi**, içe aktarımda
  `DeprecationWarning`) ve **v0.12.0'da silinir**. Kapı:
  `tests/contracts/test_brain_package_move.py` (atıf sayacı 0, kimlik, uyarı, spec girdisi).
  Veri yolları paket adından bağımsızdır ve değişmedi (`~/.entropy/memory/`,
  `<db klasörü>/memory/gray_queue.jsonl`).
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
- **Kategori kapalı kümesi:** `brain/categories.py` →
  `CANONICAL_CATEGORIES = ("working", "episodic", "semantic", "procedural")`.
  Kimlik/kural (L4) **kategori değil bayrak**: `is_identity`. Ego düğümü
  `ego-entropy-core` kimliğini korur ama kategorisi `semantic`. Eski 13+ ad
  (`query`, `session`, `office`, `agent`, `architecture`, `math`, `federation`,
  `skill` …) `LEGACY_CATEGORY_MAP` ile eşlenir; ham değer
  `metadata.legacy_category`'de kalır.
- **Yazma kapısı (`brain/gate.py`):** `MemoryGate.admit(category, content,
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
- **Gri bant birleştirme turu (Faz 11.3, `brain/gray_merge.py`):**
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
- **Rüya döngüsü v2 (Faz 11.7, `brain/dream.py`):**
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
- **Beceri sentezi v1 (Faz 12-C, `brain/skill_synthesis.py`, SKILLFOUNDRY):**
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

## 4. Faz 11-A kod değişiklikleri — arşivde

Faz 11-A'nın dosya bazlı değişiklik tablosu (compile.py APP_ROOT sözleşmesi,
prototip ailesinin silinmesi, test alt paketleri, `.gitignore`, `docs/` iskeleti)
[`_archive/state/STATE_2026-09-10_faz11-13A.md`](_archive/state/STATE_2026-09-10_faz11-13A.md) §3'e indi.
Kalıcı sözleşme yalnızca şudur: **`compile_roots()` `APP_ROOT`'a yazmaz**
(§3'te imzalı). `EntropyAI.spec` o dilimde değişmemişti.

---

## 5. Açık işler

> **Faz 14 açılışında (2026-09-11) yenilendi.** Aşağıdaki 0'ıncı blok Faz 14'ün
> taşıdığı açık işlerdir; eski numaralı maddeler olduğu gibi duruyor.

### 0-A. Faz 14'e devreden dört iş (dilim sahibiyle)

| # | İş | Kanıt / bugünkü durum | Dilim · sahip |
|---|---|---|---|
| **R-13A2-1** | Silinmiş kartın **drift döngüsü**: `20260910-194435-canivopets-com-medya-uzm` her pano yazımında `board.drift` üretiyor | `Board/events.jsonl`: 5 saatte **10 olay** (seq 59…78); kartın dosyası diskte yok | 14-F (kapanış) · agy-integration-engineer |
| **12 pytest artığı düğüm** | Üretim hafızasında pytest kaynaklı düğümler; ikisi `'list_iterator'` hata metni taşıyor, biri `pytest-of-…` kaynaklı | `~/.entropy/cognitive_memory.db` (salt okunur ölçüm) | 14-D · memory-rag-engineer — **arşivlenir, silinmez** |
| **Veri kökü tek kaynak** | Üç parçalı kök; 7 modül `Path.home()/".entropy"` sabit yazıyor (ARCHITECTURE §3.0) | `<depo>\.entropy` ayarlar / `~/.entropy` DB'ler / bayat `%LOCALAPPDATA%` | 14-F · qa-build-engineer |
| **Wiki ikinci partisi** | ~30k token; 13-C'de tavan aşıldığı için hiç koşulmadı, `WIKI.state.json` `processed` **2'de**, K4 %56,8 (< %60) | kullanıcı kota onayı bekliyor | 14-D sonrası · memory-rag-engineer |

Ayrıca **F-13D-1** (her açılışta `entropy_fault.log`'a düşen COM istisna bloğu; ölümcül
değil, kaynağı bulunamadı) 14-F'te bir kez daha aranır.

### 0. Canlı ölçülmeyenler (13-D sonunda açılmıştı, hâlâ açık)
   - **Wiki ikinci partisi** — yukarıdaki kota notu; K4 hâlâ %56,8 (< %60 hedef).
   - **R-13A2-1** — kullanıcının 3 karttan 2'sinin dosyası diskte yok; 13-C'de
     bulunan R-13C-2 (ofis kartlarının sahte ayrışması) en olası açıklama ama
     **bağlantı kanıtlanmadı**.
   - **F-13D-1** — her açılışta `entropy_fault.log`'a düşen
     `Windows fatal exception: code 0x8001010d` bloğu (§2.14); ölümcül değil,
     kaynağı bulunamadı.
   - `/memory merge` köprü bağlantısının gerçek koşumu, öz-amplifikasyon
     ADD oranının gerçek korpusta ölçümü, madde 10'daki `QFont` uyarısının
     gerçek ekranda doğrulanması — hepsi model/canlı koşum gerektiriyor.

1. **Build doğrulaması (QA):** `pyinstaller EntropyAI.spec` → `dist_check` + `.exe` smoke test;
   `tests/test_exe.py`'nin iki testi ancak bundan sonra yeşile döner.
   *(Her kapanış QA'sında koşuluyor; 13-D'de exit 0 / 207 s / `Entropy AI 0.11.0` — §2.14.
   Madde, build'in her fazda yeniden doğrulanması gerektiği için açık bırakıldı.)*
2. `tests/desk/test_desk_phase7.py::test_panel_minimum_widths_sum_below_900` — önceden var
   olan arayüz hatası; **Faz 11 kapanış QA'sında kök nedeni bulundu**, madde 9'a taşındı.
3. `scripts/` altındaki ~60 tek seferlik betik: izlemeye mi alınacak, `scratch/`e mi taşınacak,
   silinecek mi? Karar verilmedi (silinmedi, dokunulmadı).
4. ~~`src/entropy/platform/autostart.py` ölü ürün modülü~~ — **KAPANDI (Faz 12-E)**:
   kaldırıldı, `config.autostart_enabled` ve iki testiyle birlikte
   ([ADR-0006](adr/ADR-0006-autostart-kaldirildi.md)). `core/claude_bg.py` ise
   **Faz 13-C'de arşivlendi** ([ADR-0009](adr/ADR-0009-claude-bg-arsivlendi.md)):
   `docs/_archive/spikes/claude_bg/`, testi `tests/_reference/` altında ve
   toplanmıyor; spec girdisi kaldırıldı.
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
     `brain/gray_merge.py`** (§3). Kalan: agy tarafında `/memory merge`
     komutunun köprüye bağlanması ve **gerçek koşum** (QA).
   - ~~**Öz-amplifikasyon kilidi (11.6)**~~ → **Faz 11-C'de tamamlandı**
     (`agents/amplification.py`, §3). Kalan: gerçek kapıyla uçtan uca ölçüm
     (ADD oranının gerçek korpusta ne çıktığı) yapılmadı.
   - ~~`dream_and_consolidate` hâlâ 48 saat + epizodik koşuluna bağlı~~ →
     **Faz 11-D: `brain/dream.py`** (§3). Eski metot geriye dönük uyum için
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

## 6. Faz 9 … 11-D özetleri — arşivde

Faz 9 (Saf Kip), 9.1 (efor = model varyantı), 10 (Desk çalışma alanı, denetim
noktaları, kanıtla kapat, worktree/PR akışı), 11-B (hafıza göçü, `MemoryGate`)
ve 11-D (gri bant birleştirme, rüya v2, wiki derleme, genel beyin paketi)
anlatımları ölçümleriyle birlikte
[`_archive/state/STATE_2026-09-10_faz11-13A.md`](_archive/state/STATE_2026-09-10_faz11-13A.md) §4'e indi.
Bu dilimlerin **yürürlükteki** sözleşmeleri (bütçeler, kapı bantları, kimlik
kuralları) §3'tedir; kapanmış dilimlerin kalıcı sonucu §2 tablosundadır.

---

## 7. Kırmızı çizgiler

- Kullanıcı verisi (Obsidian kasası, `~/.entropy`) **silinmez**. Depo içi kullanıcı raporları
  (`*_audit.md/json`) silinmez, `docs/_archive/` altına taşınır.
- `git stash`, `git checkout --`, `git reset --hard` **yasak**.
- Gerçek model çağrısı yapılmaz; testler hedefli koşulur.
- Ticari referans ürünün ve üreticisinin adı hiçbir dosyaya yazılmaz.
- Ölç, iddia etme: dosya sayısı, MB, test sayısı önce/sonra yazılır.

## Devralma ritüeli (çökme sonrası; Faz 13'te iki kez uygulandı)
Claude Code süreci alt ajanlar çalışırken çökerse ajanların işi çalışma ağacında durur (commit/etiket bozulmaz). Devralan ajan: (1) kapsamındaki `git diff`i inceler, (2) raporunun başına **bitti / yarım / başlanmadı** tablosu yazar, (3) yarım olanı geri almadan tamamlar (`git stash`/`checkout --`/`reset` yasak), (4) hedefli testleri koşar. Orkestratör önce `python -m compileall -q src tests` ile ağacın derlendiğini ve hızlı bir hedefli test kümesini doğrular, sonra ajanları aynı kapsam ve API sözleşmeleriyle yeniden başlatır.
