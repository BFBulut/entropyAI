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
   `%LOCALAPPDATA%/Programs/claude` → editör eklentileri (`.vscode`, `.vscode-insiders`, `.cursor`;
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

## 2.13 Faz 13-C KAPANIŞ (v0.10.4, 2026-09-11, qa-build-engineer) — kota **133.542 token (TAVAN AŞILDI)**

Ortam: `EntropyAI.exe` **kapalıydı** → build doğrudan `dist/` içine alındı.
Yedek: `~/.entropy/backups/p13c-20260911-0331/` (3 DB + `Entropy/Memory` 3 dosya + wiki 20 dosya).

| Adım | Sonuç | Kanıt |
|---|---|---|
| Tam süit (düzeltme öncesi) | **2.629 passed / 0 failed / 454,4 s** | `scratch/_p13c_suite.log` |
| **Tam süit (düzeltme sonrası, yetkili)** | **2.644 passed / 0 failed / 519,7 s**, exit 0 | `scratch/_p13c_suite2.log` |
| Toplama farkı | 2.605 (13-B) − 32 (`claude_bg` arşivi) + 13-C çekirdek testleri = **2.629**; + bu QA'nın **15** yeni testi = **2.644** | — |
| C4 tek yön sözleşmesi (yeni) | `tests/contracts/test_phase13c_one_way.py` **15 passed** | — |
| `test_architecture_rules` + `test_spec_sync` | **23 passed**; sürüm tek kaynak `pyproject.toml:7` = `src/entropy/__init__.py:9` = **0.10.4**; `EntropyAI.spec:154` `desk_admin`, `:251` `desk_approvals_panel`, `claude_bg` **yok** | — |
| `ui_audit.py --gate --final` | **exit 0**, `Traceback` **0**; Desk kapıları: `desk_screens_swept_count` **7**, `desk_empty_interactive_count` **0**, `desk_unnamed_icon_buttons` **0**, `desk_ghost_button_contrast` **0**, `desk_min_width` 760 beyan / 701 hesap; genel: `orphan_reparents` 0, `unnamed_icon_buttons` 0, `screens_swept_count` 7, `click_latency_ms` **9** (182 kart) | `scratch/_p13c_audit.log` |
| **Build** `PyInstaller EntropyAI.spec --noconfirm` | **exit 0, 372 s**, `dist/EntropyAI`, exe **56.045.377 B** | `scratch/_p13c_build.log` |
| `--version` / `--help` | **`Entropy AI 0.10.4`** exit 0 / exit 0 | — |
| Paket (PYZ, 7.309 modül) | `entropy.agents.desk_admin` **var**, `entropy.ui.widgets.desk_approvals_panel` **var**, `entropy.brain` + şim `entropy.memory` var, `claude_bg` **0 girdi** | — |
| 20 sn canlı koşum | **canlı kaldı** (PID 6292, `Responding=True`, pencere başlığı "Entropy AI"); günlük 451 → 455, yeni satırlarda `Traceback`/`CRITICAL`/`ModuleNotFoundError` **0/0/0** | `scratch/_p13c_live.{out,err}`, `_p13c_live_newlog.txt` |
| Yeni CrashDump | **yok** (EntropyAI adına dosya yok; en yeniler `EntropyAgentDesk.exe` 2026-09-09) | — |
| Marka taraması (parçalı sabit) | **0 / 0** | `git grep -riIl` |
| Yalıtım | `skills_state.json` 112 B / mtime **AYNI**; kasa `Entropy/Reports` **423 → 423**, `Entropy/Tasks` **1 → 1**, `Desk/Offices` **1 → 1** (kullanıcının ofisi dokunulmadı); `tasks_ledger.db` 86.016 → 90.112 B ve `cognitive_memory.db` 9.822.208 → 9.834.496 B **süitten değil**, canlı zincirden | — |
| `scratch/ui/phase10/*.png` | süit 8 dosyayı yeniden üretti → `git show HEAD:<yol> > <yol>` ile geri yazıldı, o yolda `git status` **0 satır** | — |

### Canlı Desk kanıt zinciri (izole kasa `scratch/desk_chain_13c/vault`)

Gerçek Claude, saf kip, kendi Python süreci; `config.obsidian_vault_path`
kopyaya çevrildi. **Gerçek kasaya hiçbir şey yazılmadı** (yukarıdaki dizin sayıları).

| # | Hüküm | Ölçüm | Kanıt |
|---|---|---|---|
| i | Ofis doğar → orkestratör otomatik, çalışma alanı kurulur | `QA Ofisi 13C` + `orkestrator`; `workspace/{BOARD,ARCHITECTURE,RULES}.md` üçü de **var**; 2 işçi (`kodcu`, `testci`) | `chain_log.jsonl` `i.office`/`i.workspace`/`i.member` |
| a | Ofis metninde Entropy kimliği ve `[DESK` yok | doğuş talimatı: `entropy` **False**, `[DESK` **False**; plan istemi (1.891 karakter): **False/False** | `a.no_leak`, `ii.plan_prompt` |
| ii | Orkestratör **böler, kod yazmaz** | plan → **2 alt kart** (`slugify çekirdek modülü` · kodcu, `slugify test paketi` · testci); üst kartın `output_paths` içinde `.py` **0** | `Desk/Offices/QA Ofisi 13C/cards/` |
| iii | İşçi kontrol noktası + yeşil kanıt | `workspace/checkpoints/<kart>.md` **iki kart için de yazıldı**; `proof_green: true`, `proof:` "Sonuç: yeşil … 14/15 geçiyor" | kart ön bilgisi `:36-37` |
| iv | İki işçi **paralel** koştu | iki alt kart aynı anda `running` (03:36:10 → 03:37:08), ayrı ledger satırları | ledger `card-…-ekirdek-mod-l`, `card-…-test-paketi` |
| v | Makbuz = ofis raporu, **8 bölüm** | `Plan / İlerleme / Değerlendirme / Kanıt / Değişiklikler / PR / Maliyet / Yorumlar` | `reports/20260911-033524-slugify-paketi.md` |
| vi | Efor argv'ye ulaşıyor | `build_command(prompt, effort="low")` → argv'de **`--effort low`** | `core/claude_bridge.py:836` + canlı ölçüm |
| vii | Ofis kartı özeti temiz (C1) | üst kart `summary`de `[PANO` **False**, `[DESK` **False**; alt kartlarda `checkpoint`/`proof`/`proof_green` **dolu** | `final` kaydı |
| — | **Üst kart `failed`** | ofis bütçesi 60.000 token; harness "harcanan ≈ 133.897" deyip alt kartları durdurdu. Alt kartlar yine de kontrol noktası + yeşil kanıtla `review`e ulaşmıştı | `final.summary` |

### Bu QA'da bulunan ve düzeltilen iki gerçek kusur

| # | Kusur | Kök neden | Düzeltme | Test |
|---|---|---|---|---|
| **R-13C-1** | `/desk office add QA Ofisi 13C :: …` diskte **"QA"** adlı ofis açıyordu; onay kuyruğundan gelen `office_create` de aynı yoldan kırpılıyordu (panelde "Onayla" **False** dönüyordu) | `slash_commands._handle_desk_admin` gövdeyi `split()` edip `names[0]` alıyordu — ad boşlukta kesiliyordu | `_desk_office_name(body)` (tırnak da söker); `office add` ve `office rm` ona bağlandı | `test_desk_office_add_keeps_a_multi_word_name`, `…_strips_surrounding_quotes`, `test_desk_office_rm_also_takes_a_multi_word_name`, `test_desk_admin_apply_creates_the_office_with_its_full_name` (`core/slash_commands.py:811-870`) |
| **R-13C-2** | Ofis kartı koşarken uygulama dakikada bir **"Pano ayrışması: 2 kart (dosya yok)"** uyarıyordu; oysa iki kartın dosyası da diskteydi | `TaskBoard.rewrite_taskboard` ayrışmayı `self.list()` (**yalnız Entropy kökü**) ile hesaplıyordu, projeksiyon ise ofis kartlarını da taşıyor → her ofis kartı kalıcı "(dosya yok)" | ayrışma artık `self.list(office=ALL_CARDS)` ile iki kökten hesaplanıyor; `TASKBOARD.md` satırları Entropy kartları olarak kaldı | `test_office_cards_are_not_counted_as_board_drift` (`agents/tasks.py:993-1000`) |

R-13C-2, §2.10'daki **R-13A2-1**'in ("kullanıcının 2 kartının dosyası yok")
en olası açıklamasıdır; ancak o iki kart Entropy kökünde göründüğü için
bağlantı **kanıtlanmadı** — R-13A2-1 açık kalıyor.

### Gerçek ekran (LG ULTRAGEAR, dpr **1,0** = %100; 1920×1080, avail 1920×1032)

Betikler `scratch/ui/phase13c/{real_check.py,real_board.py}`; ölçümler
`real_metrics.json`, `real_board_metrics.json`; görüntüler
`real_approvals_pending.png`, `real_approvals_after.png`, `real_desk_window.png`,
`real_splitter_442.png`, `real_archive_after.png`.

| Ölçüm | Sonuç |
|---|---|
| Desk onayları paneli | kuyruğa JSON ile `office_create` konuldu → panelde **1 bekleyen** ("Ofis aç: Onay Ofisi 13C") → **Onayla** → `approved=True`, bekleyen **0**, ofis + `orkestrator` doğdu, roster yenilendi (R-13C-1 düzeltmesinden **önce** `approved=False` ve ofis adı "Onay"dı) |
| Görevler bölücüsü 442 px | `sizes=[817, 442]`, pano yığını min genişlik ipucu **220 px** → taşma **0**, yatay kaydırma **gerekmiyor** |
| Desk penceresi 1100×700 | çerçeve **1100×731**, avail 1920×1032 → **sığıyor** (taşma 0/0) |
| "Sil" → "Arşivle" | düğme metni **"Arşivle"**, onay diyaloğu "Görevi arşivle … Dosya silinmez, `_archive/` altına taşınır" → Evet → kart panodan kalktı ve `Entropy/_archive/2026-09-11/cards/<kart>.md` olarak **taşındı** (silinmedi) |

### Kota

| Kalem | Token |
|---|---:|
| `office-plan-…-slugify-paketi` | 30.839 |
| `card-…-slugify-ekirdek-mod-l` | 51.860 |
| `card-…-slugify-test-paketi` | 50.843 |
| **Toplam (ledger delta)** | **133.542** (4.474.945 → 4.608.487; satır 98 → 101) |

**Tavan (100k) tek turda aşıldı.** `total_tokens` önbellek okumasını da
sayıyor (çıktı jetonu üç çağrıda toplam **8.421**), ama defterin ölçtüğü sayı
tavandır. Bu yüzden **adım 5 (wiki ikinci partisi, ~30k) HİÇ koşulmadı**;
`WIKI.state.json` `processed` **2'de duruyor**, K4/K5/K6 önce/sonra ölçümü
alınmadı. Gerçek kasa ve `cognitive_memory.db` wiki adına **değiştirilmedi**.

---

## 2.13-b Faz 13-C — çekirdek (2026-09-11, agy-integration-engineer) — kota 0, model çağrısı yok

API sözleşmeleri (arayüz ve Desk katmanı bunlara yazar):

| Sözleşme | İmza / davranış | Yer |
|---|---|---|
| Kart arşivi | `entropy.agents.tasks.archive_card(card_id, reason="", vault_path=None) -> dict(ok, archived_to)`; ayrıca `TaskBoard.archive_card(card_id, reason)`. Gerekçe **zorunlu** (boşsa `ok=False`), dosya `Entropy/_archive/<tarih>/cards/` altına **taşınır**. `TaskBoard.delete()` artık arşive delege eder; doğrudan `unlink` yolu yok | `agents/tasks.py:1071-1200`, `2378` |
| Arşiv olayı | Terminal kart (`done`/`canceled`) → `board.archived` **bilgi** olayı (durum değişmez); diğerleri → FSM `task.canceled` (T13). `INFO_EVENTS = ("board.drift", "board.archived")`, `EVENTS` 13 → **14** | `agents/board_fsm.py:59-72` |
| Desk onay kuyruğu | `entropy.agents.desk_admin.list_pending() -> list[dict(id, kind, payload, created_at, source, summary)]`, `apply_pending(id) -> dict(ok, message, created_paths)`, `reject_pending(id, reason="") -> bool`; kuyruk `Entropy/Desk/_pending/<id>.json`. Yapısal türler `office_create|agent_edit|task` onay bekler, `msg` doğrudan uygulanır | `agents/desk_admin.py` |
| Desk blokları | `[DESK <araç>] {json} [/DESK]`; `board_tools.parse_desk_calls`, `strip_tool_blocks` `[DESK` bloklarını da siler, `has_tool_blocks` onları da görür. Blok tüketimi **yalnız claude sohbet yolu**: `process_chat_response(text, board, registry, provider="")` | `agents/board_tools.py:53-146`, `core/response_hooks.py:50-118` |
| Kontrol noktası | **Tek yazıcı** `entropy.brain.checkpoints.write_checkpoint`; ofis adı boş/`entropy` ise yol `core.paths.board_checkpoint_path` (Entropy kökü), aksi hâlde ofis çalışma alanı. `read_checkpoint_file(path)` **mutlak yoldan** okur; kartın `checkpoint` alanı o yolu taşır ve arayüz onu okur | `brain/checkpoints.py:109-260`, `agents/board_tool_exec.py:134-206`, `ui/widgets/task_board_widget.py:177-192` |
| Ofis kartı alanları | `TaskCard.proof_green: Optional[bool]` (üç değerli). `tasks._finish` ofis kartında da blokları **temizler** ve `checkpoint`/`proof`/`proof_green` + kural adaylarına ayrıştırır (`_office_block_fields`); harness alanları okur (`OfficeHarness._card_proof`, `_close_child`) | `agents/tasks.py:1988-2090`, `agents/harness.py:1128-1145, 1906-1930` |
| Kural adayı | `entropy.agents.harness.propose_rule_candidates(office, agent, text, source="", vault_path=None, offices=None) -> list[str]` — modül düzeyi tek yazıcı; `OfficeHarness.collect_rule_candidates` ona delege eder | `agents/harness.py:343-402` |
| Efor | Kart eforu argv'ye: claude `--effort <düzey>`, agy **model adının son eki**. Üst ofis kartının eforu alt kartlara iner (`harness` plan kolu), plan/değerlendirme çağrısı da `effort` geçirir | `agents/harness.py:1647-1660, 2597-2606`, `agents/tasks.py:1664` |
| `board.stop` | Süreç **ağacı** gizli `taskkill /F /T` ile iner (`_kill_card_process_tree`, `platform.proc.popen_kwargs` → pencere açılmaz), kart `canceled`, defterin açık satırları `record_task_cancelled` ile kapanır (`_close_ledger_rows`; `card-`, `office-plan-`, `office-eval-`) | `agents/tasks.py:1802-1920` |
| İstem bütçesi | `board_tools_section()` = **595 / 600** karakter; `[DESK office_create]` bloğu kırpmadan sonra da istemde (sözleşme testi) | `agents/board_tools.py:256-275` |

Testler: `tests/contracts/test_phase13c_desk.py` (**25**), `tests/desk/test_desk_phase13c_harness_fields.py` (**4**);
hedefli koşum `tests/contracts` + `tests/desk` + `test_agents_registry_tasks.py` + `test_report_attribution_and_handoff.py` → **840 passed**.

---

## 2.12 Faz 13-C — çekirdek (2026-09-11, agy-integration-engineer) — kota 0, model çağrısı yok

Her madde bir kullanıcı şikâyetine bağlı. Ölçüm: `tests/contracts` + `tests/desk` +
`test_agents_registry_tasks` + `test_report_attribution_and_handoff` +
`test_phase11_amplification_lock` + `test_slash_commands` → **875 passed / 0 failed / 131 s**.

| Madde | Durum | Kanıt (dosya:satır) |
|---|---|---|
| **C1** ofis kartı blok sızıntısı — Desk panosunda özet ham `[PANO …] {json} [/PANO]` gösteriyordu | **bitti** | `tasks.py:1989` (`_office_block_fields` çağrısı, temizlik artık KOŞULSUZ), `tasks.py:2110` (bloklar → `checkpoint`/`proof`/`proof_green`/kural adayı ALANLARI); harness `summary`den geri ayrıştırmıyor |
| **C2** tek kontrol noktası yazıcısı + arayüzde mutlak yol | **bitti** | `brain/checkpoints.py:112` (`_is_entropy_office` boş adı da Entropy sayar), `:144` (Entropy kolu `core.paths.board_checkpoint_path`e iner — dosya adı şeması korundu), `:243` yeni `read_checkpoint_file(path)`; `ui/widgets/task_board_widget.py:177` kartın `checkpoint` ALANINI okur |
| **C3** `[DESK …]` araçları + `desk_admin` API + `/desk approve\|reject` | **bitti** | `board_tools.py:59` `DESK_OPEN_RE`, `:121` `parse_desk_calls`, `:264` istem metni, `:310` blok temizliği; `agents/desk_admin.py` (`list_pending`/`apply_pending`/`reject_pending`/`consume_desk_calls`, kuyruk `Entropy/Desk/_pending`); `core/response_hooks.py:106` (YALNIZ claude sohbet yolu); `slash_commands.py:776` `_handle_desk_admin`; `EntropyAI.spec:154` |
| **C3 istem bütçesi** | **ölçüldü** | `tools_section(False)` **975** karakter (ofis/ajan), `tools_section(True)` **1.572**; `[DESK]` farkı **597 karakter ≈ 149 jeton**, blok örneği 221 karakter / 5 satır. Ofis istemi `[DESK` içermiyor (tek yön kuralı, `'[DESK' in base → False`) |
| **C4** `archive_card` + T13 `done`→`board.archived` | **bitti** | `tasks.py:1080` `archive_card(card_id, reason) -> {ok, archived_to}` (gerekçe zorunlu; terminal kart durumunu DEĞİŞTİRMEZ, bilgi olayı yazar), `tasks.py:2382` modül düzeyi sarmalayıcı; `board_fsm.py:213` T13, `INFO_EVENTS == ("board.drift", "board.archived")` |
| **C4** `/task rm` | **bu turda tamamlandı** | `slash_commands.py:557` `/task rm\|remove\|archive <id> :: <gerekçe>` → `board.archive_card`; gerekçesiz komut hiçbir şeyi değiştirmez; kullanım metni ve `/tasks` alt bilgisi güncellendi. Testler: `test_phase13c_desk.py::test_slash_task_rm_archives_with_reason`, `…_without_reason_changes_nothing`, `…_usage_mentions_rm` |
| **C6** ofis eforu argv'ye iki sağlayıcıda da ulaşır | **bitti** | `harness.py:2596` (`spec.effort` ya da `office.default_effort` → köprü kwarg'ı), `harness.py:1651` (plan turu efor devri); claude'da `--effort`, agy'de model son eki |
| **S** `board.stop` süreç AĞACI + ledger `canceled` | **bitti** | `tasks.py:1802` `stop()`, `:1899` `_kill_card_process_tree` (Windows gizli `taskkill /F /T`, `platform.proc.popen_kwargs` → konsol parlamaz), `:1930` `_close_ledger_rows` (`record_task_cancelled`, `task_ledger.py:366`) |

**Sözleşme testi güncellemeleri (esnetme değil, sözleşme değişti):**
`test_phase11_board.py:84` ve `test_phase12_board_autonomy.py:378` — `board_fsm.EVENTS` 13 → **14**,
`INFO_EVENTS` tek elemanlıyken iki elemanlı oldu; sebep C4'ün `board.archived` BİLGİ olayı
(durum değiştirmez, izdüşümü kirletmez). Bakımcının gördüğü 5 kırmızının tamamı kapandı
(`test_phase10_harness_discipline`, `test_phase13_brain_shortcut` ve `test_spec_sync` kaynak
tarafı düzeltilerek yeşillendi; testleri gevşetilmedi).

---

## 2.12-b Faz 13-C — depo bakımı (2026-09-11, repo-curator) — kota 0, model çağrısı yok

| Adım | Sonuç | Kanıt |
|---|---|---|
| `src/entropy/core/claude_bg.py` → `docs/_archive/spikes/claude_bg/claude_bg.py` | `git mv`, geçmiş korundu; yanına geri getirme adımlarını yazan `README.md` | `git status --porcelain` → `R  src/... -> docs/...` |
| `tests/test_phase11_claude_bg.py` → `tests/_reference/` | ispat defteri olarak saklandı, **toplanmıyor** (`tests/_reference/conftest.py` → `collect_ignore`) | — |
| `EntropyAI.spec` | `'entropy.core.claude_bg'` satırı kaldırıldı. **Bulgu:** ADR-0007 madde 2 "spec'e eklenmez" diyordu ama satır oradaydı — `test_spec_sync` "her kaynak modülü spec'te olmalı" kuralını uyguladığı için girmişti; modül kaynaktan çıkınca çelişki kapandı | `EntropyAI.spec:240` (eski) |
| Kalan atıf | `grep -rn claude_bg src tests/*.py scripts EntropyAI.spec` → **0** | — |
| **Toplama** | **2.605 → 2.573** (−32, tamamı arşivlenen spike'ın testleri) | `pytest --collect-only -q` |
| `tests/contracts/test_spec_sync.py` + `test_architecture_rules.py` | **23 passed** | hedefli koşum |
| ADR | [ADR-0009](adr/ADR-0009-claude-bg-arsivlendi.md) yazıldı; ADR-0007 **sonuçlandı (arşiv)** olarak işaretlendi | — |
| Bu dosya | **1.685 → 1.032 satır**; 11-x/12-x/13-A ölçüm tabloları [`_archive/state/STATE_2026-09-10_faz11-13A.md`](_archive/state/STATE_2026-09-10_faz11-13A.md) altına indi. §3 sözleşmeler, §5 açık işler, §7 kırmızı çizgiler ve son iki dilimin (13-B, 13-A2) tabloları **yerinde**; §4 (Faz 11-A kod tablosu) ve §6 (Faz 9…11-D anlatımı) da arşive indi, yerlerinde bağlantılı özet var | — |
| `ARCHITECTURE.md` | 13-A/13-A2/13-B sözleşmeleriyle eşitlendi (§2, §5, §6.1, §8, §9, §10.1) | — |
| `.gitignore` | denetlendi, değişiklik gerekmedi (`__pycache__/`, `*.py[cod]`, `dist_check/`, `scratch/` zaten kapsıyor) | — |
| **Not (bu dilimin dışında)** | `tests/contracts/test_spec_sync.py::test_spec_lists_every_entropy_module` o an kırmızıydı (eksik modül `entropy.agents.desk_admin`); **kapandı** — satır `EntropyAI.spec:154`e eklendi | `test_spec_sync` 9/9 |

Kaynak dosyalara (`src/entropy/{agents,ui,desk,brain,core}`) **dokunulmadı**;
`EntropyAI.spec`te tek satır değişti (paralel ajanlarla çakışma riski yok).

---

## 2.11 Faz 13-B — `entropy.brain` paket taşıması (2026-09-11, memory-rag-engineer) — kota 0

Karar ve gerekçe: [ADR-0008](adr/ADR-0008-brain-paket-tasimasi.md) (ADR-0004'ün yerine geçti).

| Adım | Kanıt |
|---|---|
| Taban toplama | `pytest --collect-only -q` → **2.596 tests collected** |
| `git mv src/entropy/memory src/entropy/brain` | `git status --porcelain` → **27 satır, hepsi `R`** |
| Dizgi değişimi (`entropy.memory`→`entropy.brain`, `entropy/memory`→`entropy/brain`) | **166 dosya** (src 48, tests 57, `scripts/*.py` 5, `scripts/_oneshot/*.py` 55, `EntropyAI.spec` 1) |
| Kalan atıf | `grep -rn 'entropy\.memory\|entropy/memory' src tests scripts EntropyAI.spec` → **0** (şim + spec'in şim girdisi hariç) |
| Dizgi hâlindeki modül adları | `ui/widgets/memory_inspector_dialog.py:508-509`, `brain/supabase/cognitive_memory.py:36` (`logging.getLogger("entropy.brain.cognitive")`) — günlükleme kök günlükçüyle çalışıyor, ada dayalı süzgeç yok |
| Uyumluluk şimi | `src/entropy/memory/__init__.py`: `entropy.memory.gate is entropy.brain.gate` → **True**; derin yol `entropy.memory.obsidian.vault_manager` → **True**; `DeprecationWarning` yükseliyor; `entropy.brain` **uyarısız** |
| Spec | `'entropy.memory'` (şim) hiddenimports'a eklendi; `test_spec_sync.py` **9 passed** |
| Yeni sözleşme testi | `tests/contracts/test_brain_package_move.py` **9 passed** |
| Toplama (sonra) | **2.605** (= 2.596 + 9 yeni test) |
| Veri | `~/.entropy` altında `*.json`/`*.db` içinde `entropy.memory` dizgisi **0**; kasadaki eşleşmeler yalnız tarihsel rapor metni — **hiçbir kullanıcı dosyasına dokunulmadı** |

### B4 doğrulama (2026-09-11, qa-build-engineer) — kota 0, model çağrısı yok

Ortam: `EntropyAI.exe` **kapalıydı** → build doğrudan `dist/` içine alındı.

| Adım | Sonuç | Kanıt |
|---|---|---|
| `import entropy.main` (PYTHONPATH=src) | **OK**; `entropy.brain.__file__` = `src/entropy/brain/__init__.py`; `import entropy.memory` yalnızca `DeprecationWarning` | — |
| Toplama | **2.605 tests collected** (2,6 s) — taşımada test kaybı yok | — |
| **Tam süit** `pytest tests -q -p no:cacheprovider` (offscreen) | **2.605 passed / 0 failed / 681,1 s**, exit 0 | `scratch/_p13b4_suite.log` |
| `test_spec_sync` + `test_brain_package_move` + `test_architecture_rules` | **32 passed** | — |
| Sürüm tek kaynak | `pyproject.toml:7` = `0.10.3`, `src/entropy/__init__.py:9` `_FALLBACK_VERSION` = `0.10.3` | — |
| Kalan `entropy.memory` atfı | kaynakta **0**; yalnız şim dosyası, `EntropyAI.spec:193-194` (bilinçli şim girdisi) ve sözleşme testinin kendi dizgileri | `grep -rn` |
| **Build** `PyInstaller EntropyAI.spec --noconfirm` | **exit 0, 467 s**, `dist/EntropyAI` | `scratch/_p13b4_build.log` |
| `EntropyAI.exe --version` / `--help` | **`Entropy AI 0.10.3`** exit 0 / exit 0 | — |
| **Paket kontrolü** (PYZ, 7.308 modül) | `entropy.brain*` **30 girdi**; kaynak ağacındaki 27 brain modülünün **tamamı** pakette (`NOT PACKAGED: []`); şim `entropy.memory` **var**, `entropy.memory.<alt modül>` girdisi **yok** | `CArchiveReader` + `ZlibArchiveReader` |
| 20 sn canlı koşum | **canlı kaldı** (PID 53488, 20 sn sonra hâlâ çalışıyordu; QA kendi başlattığı süreci kapattı) | `scratch/_p13b4_live.{out,err}` |
| Beyin katmanı gerçekten yükleniyor | paketten koşan exe'nin stderr'i: `entropyrain\supabase\cognitive_memory.py:163` (fastembed uyarısı) → hafıza katmanı **yeni yoldan** yüklendi | `scratch/_p13b4_live.err` |
| Günlük deltası (447 → 451 satır) | `Traceback` 0, `CRITICAL` 0, `ModuleNotFoundError` 0 | `scratch/_p13b4_live_newlog.txt` |
| `entropy_fault.log` | yalnız `0x8001010d` (COM, iyi huylu) — dosyada **45 kez**, tamamı aynı kod, taşımadan önce de vardı; kayıt QA'nın kendi `Stop-Process`'inden | — |
| Yeni CrashDump | **yok** (en yenisi 2026-09-09, `EntropyAgentDesk.exe`) | `%LOCALAPPDATA%\CrashDumps` |
| Marka taraması (iki ad, parçalı sabitten) | **0 / 0** | `git grep -riIl` |
| Yalıtım | süit öncesi=sonrası: `cognitive_memory.db` 9.822.208 B / mtime **aynı**, `tasks_ledger.db` 86.016 B / mtime **aynı**, `skills_state.json` 112 B / mtime **aynı**; kasa `Entropy/Reports` **423 → 423**, `Entropy/Tasks` **1 → 1** | — |
| `scratch/ui/phase10/*.png` | süit 8 dosyayı yeniden üretti → `git show HEAD:<yol>` ile geri yazıldı, `git status` **0 satır** | — |

**Kalan risk kapandı:** PyInstaller sessiz eksik paketleme ölçüldü, eksik yok.
Doğrulanamayan: gerçek pencere geometrisi/sürükleme ölçümü (canlı koşum
görsel etkileşimsiz yapıldı).

---

## 2.10 Faz 13-A2 KAPANIŞ (v0.10.2, 2026-09-10, qa-build-engineer) — kota: 1 canlı kart

Ortam: `EntropyAI.exe` **AÇIKTI** (PID 47920, 22:22'de başlamış, v0.10.1) →
build `--distpath dist_check --workpath build_check` ile alındı, `dist/` bozulmadı.
Aynalama komutu (kullanıcı uygulasın):
`robocopy C:\EntropiAI\dist_check\EntropyAI C:\EntropiAI\dist\EntropyAI /MIR`

| Adım | Sonuç | Kanıt |
|---|---|---|
| Tam süit `pytest tests -q -p no:cacheprovider` (offscreen) | **2.596 passed / 0 failed / 613,0 s**, exit 0 | `scratch/_p13a2_suite2.log` |
| İlk süit koşumu (düzeltme öncesi) | 2.591 passed / **3 failed** → hepsi test sahtesi kaynaklı (aşağıda) | `scratch/_p13a2_suite.log` |
| `test_spec_sync.py` + `test_architecture_rules.py` | **23 passed**; spec hiddenimports'ta `entropy.platform.proc`, `entropy.ui.widgets.agent_run_state`, `entropy.ui.widgets.lifecycle` var (`EntropyAI.spec:221-223`), sürüm tek kaynak **0.10.2** | — |
| `python scripts/ui_audit.py --gate --final` | **exit 0** | `scratch/_p13a2_audit2.log` |
| Build `PyInstaller EntropyAI.spec --distpath dist_check` | **exit 0, 328 s**, `dist_check/EntropyAI` 1.207 MB, `EntropyAI.exe` **56.019.931 B** | `scratch/_p13a2_build.log` |
| `EntropyAI.exe --version` / `--help` | **`Entropy AI 0.10.2`** exit 0 / exit 0 | — |
| Paketteki yeni modüller | PYZ arşivinde (7.307 modül) **üçü de var** | `CArchiveReader` + `ZlibArchiveReader` ile doğrulandı |
| 20 sn canlı koşum | **YAPILAMADI**: tek örnek kilidi — `dist_check` exe'si "Zaten çalışıyor; mevcut pencere öne getirildi" deyip çıktı (kullanıcının exe'si kapatılmadı) | `scratch/_p13a2_live.log` |
| Günlükte `Traceback`/`CRITICAL` | yeni satırlarda **0** | `.entropy/logs/entropy.log` |
| Yeni CrashDump | **yok** (en yenisi 2026-09-08) | `%LOCALAPPDATA%\CrashDumps` |
| Marka taraması (iki ad, parçalı sabitten) | **0 / 0** | `git grep -riIl` |
| Yalıtım | `skills_state.json` 112 B / mtime **değişmedi**; kasa `Entropy/Reports` **423 → 423**, `Entropy/Tasks` **1 → 1**; `tasks_ledger.db` ve `cognitive_memory.db` değişti ama **süit yüzünden değil** (aşağıda) | — |

### Küçük düzeltmeler (dört madde)

| # | Düzeltme | Dosya:satır | Test |
|---|---|---|---|
| (a) | `TaskCard.brain_only: bool` alanı + ön bilgi gidiş-dönüşü (`_as_bool`) | `agents/tasks.py:239-245`, `:275` (`to_frontmatter`), `:289-296` (`_as_bool`), `:783` (okuma) | `tests/contracts/test_phase13a2_closeout.py` (7 test) |
| (a) | `/task --brain-only` — bayrak başlığa/hedefe sızmadan sökülür | `core/slash_commands.py:4` (`import re`), `:580-589`, `:621` | `test_slash_task_parses_brain_only_flag_out_of_the_title` |
| (a) | `[PANO board_create]` `brain_only` (JSON alanı ya da metindeki işaret) | `agents/board_autonomy.py:88-93`, `:120` | `test_board_create_accepts_brain_only`, `..._reads_the_marker_in_text` |
| (a) | `brain_lookup(..., card=card)` bağlantısı | `agents/tasks.py:1622` | `test_ask_brain_passes_the_card_to_brain_lookup`, `..._signature_accepts_card_keyword` |
| (b) | `git branch` çağrısı `popen_kwargs()` alıyor; `PENDING_UNHIDDEN` **boşaltıldı** | `desk/projects_panel.py:28`, `:53-58`; `tests/contracts/test_phase13_board_hygiene.py:144-147`, `:202-204` | `test_every_subprocess_call_hides_its_console` |
| (c) | `agy_bridge` `taskkill … shell=True` çağrıları — **zaten düzeltilmişti** (`:1728`, `:2527`, `:2547`, `:2575-2580` hepsi `popen_kwargs()` alıyor); yalnız kilit testi eklendi | — | `test_taskkill_calls_still_hidden` |
| (d) | `board.drift` **kendi korelasyonunu** taşır (`drift:<hash16>`); eskiden ilk ayrışan kartın kimliğini alıyordu | `agents/tasks.py:983-996` | `test_drift_event_gets_its_own_correlation` |
| (d) | `seq` artık **dosyanın son satırından** doğrulanıyor; bayat önbellek anahtar yinelemesine de kapatıldı | `agents/board_events.py:201-218` (`_tail_seq`), `:167-178` | `test_seq_stays_unique_across_two_log_instances`, `test_stale_instance_cannot_write_the_same_idempotency_key_twice` |

**(d) gerçek kanıt.** Kullanıcının kasasındaki `Entropy/Board/events.jsonl`
içinde `seq` **41, 45 ve 46 ikişer kez** yazılmıştı; 46 tam da bu QA sırasında
(hâlâ koşan v0.10.1 exe'sinden) ikinci kez düştü — yani hata canlıydı.
Dört `board.drift` olayının dördü de ilgisiz bir kartın korelasyonunu
(`20260910-064253-kisa-teknik-not`) taşıyordu. Düzeltmeden sonra yazılan
`seq` 61/63/65 olaylarının korelasyonu `drift:10a5df00…`, `drift:eef5ce2a…`,
`drift:46a9b155…` — **kendi zincirleri**, yeni yinelenen `seq` yok.

### Üç kırmızı testin teşhisi (gerçek hata mı test hatası mı)

`test_phase12_board_autonomy.py::{test_research_card_with_brain_answer_never_calls_cli,
test_write_card_runs_cli_with_brain_section}` ve
`test_phase11_amplification_lock.py::test_card_answered_from_brain_never_calls_the_cli`
**test hatasıydı**: sahte `brain_lookup` imzası `lambda q, builder=...` idi,
üretim çağrısı `card=` eklediği anda `TypeError` doğuyor ve
`tasks.py::_brain_consult`'un geniş `except Exception`'ı onu **sessizce**
yutuyordu (kısa devre hiç tetiklenmiyordu, kart CLI'ya gidiyordu). Sözleşme
§2.9'da tanımlı imza `brain_lookup(query, builder=None, card=None)`; sahteler
ona uyduruldu (`test_phase11_amplification_lock.py:124`,
`test_phase12_board_autonomy.py:490`) ve imzanın kendisi artık
`test_brain_lookup_signature_accepts_card_keyword` ile kilitli.

### `ui_audit --gate --final` sayaçları

`orphan_reparents` **0** · `unnamed_icon_buttons` **0** ·
`screens_swept_count` **7** · `empty_interactive_count` **0** ·
`ghost_button_contrast` **0** · `button_contrast` **0** ·
`click_latency_ms` **10** (182 kart) · `min_width_declaration_failures` **0** ·
`reader_min_width` **875** · `distinct_hex` **0** · `local_stylesheets` **0** ·
`contrast_failure_count` 0 · `small_target_count` 0 · `min_button_height` 30.
Bu üç sayaç hesaplanıyordu ama **basılmıyordu**; `scripts/ui_audit.py:938-941`
yazdırma listesine eklendi (kapı yeşilken bile kanıta geçmiyorlardı).

### Gerçek ekran (LG ULTRAGEAR, dpr 2,0 = %200; 1920×1080, avail 1920×1032)

Betikler `scratch/ui/phase13a2/{real_check.py,real_badge.py,real_ghost.py}`;
ölçümler `real_metrics.json`, `real_badge_dpi{1,2}.json`, `real_ghost.json`;
görüntüler `real_skills_toggle.png`, `real_agents_badge.png`,
`real_report_card.png`, `real_tasks_panel.png`, `real_header_badge_dpi{1,2}.png`.

| # | Kullanıcı bulgusu | Ölçüm | Sonuç |
|---|---|---|---|
| (a) | Yetenekler "Etkin" kutusu donduruyor | 26 yetenek dizini, **22** keşfedildi; 22 tıklamanın **azami 3,55 ms**, medyan 0,79 ms (eşik 50 ms); gerçek `skills_state.json` **kopyalandı**, özgün dosya bit bit aynı | **kapandı** |
| (b) | İkonlar çizilmiyor (boş kare) | Piksel örneklemesi (alfa > 16): yetenek yüzeyi **111/111**, Ajanlar kartı **8/8** ikon çizildi — **kaynak ağacından**; paketlenmiş exe penceresi ölçülemedi (aşağıda) | **kısmen** |
| (c) | "Raporu açSohbete al" bitişik | Kartın düz metni `…Raporu aç \| Sohbete al` — iki ayrı satır/eylem, bitişik değil | **kapandı** |
| (d) | Ajan koşarken "2 sa önce" yazıyor | Rozetler: **"çalışıyor · 1 dk 12 sn"** ve **"son koşu: az önce"**; `running_count()` **1** | **kapandı** |
| (e) | "Claude ✓ max" kırpılıyor | %200: etiket **103 px**, metin 83 px + çerçeve 18 px = 101 px → **sığıyor**; %100: **105 px** / 85+18 = 103 → sığıyor. `minimumWidth == maximumWidth == gereken` olduğu için kırpma yolu kapalı | **kapandı** |
| (f) | Görevler kalabalık, QA artıkları duruyor | Kasada QA kartı **yok** (9'u `Entropy/_archive/2026-09-10/qa-cards/`); kullanıcının 3 canivopets kartı panoda **görünüyor** ama ikisinin **dosyası diskte yok** → **R-13A2-1** | **AÇIK** |
| (g) | Görev koşarken ~20 pencere | Gerçek `QApplication` + canlı kart (`arastirmaci`, claude): **6.839 örnek / 300 s** boyunca yeni konsol penceresi **0**, `console_max` **0**, `QApplication.topLevelWidgets()` **0** | **kapandı** |

### R-13A2-1 (AÇIK REGRESYON — kullanıcı verisi)

Kullanıcının üç canivopets kartından **ikisinin `.md` dosyası kasada yok**;
kartlar yalnızca olay projeksiyonunda yaşıyor, bu yüzden pano onları
gösteriyor ama dosya kaybolmuş:

```
20260910-194435-canivopets-com-medya-uzm  (dosya yok) ≠ review
20260910-224018-canivopets-com-medya-aja  review      ≠ assigned
20260910-224237-canivopets-com-s-f-rdan-  (dosya yok) ≠ failed
```

Kasa genelinde arama (`find <kasa> -name "<id>*"`) **hiçbir kopya bulmadı**;
olay günlüğünde bu iki kart için `task.canceled`/arşiv olayı **yok**, yani
dosyalar bir olay yazılmadan silinmiş (QA kartı arşivleme diliminin yan
etkisi olması kuvvetle muhtemel). Kartlar olaylardan yeniden kurulabilir ama
**kullanıcı verisine yazma** olduğu için bu QA'da **yapılmadı**. Uygulama
durumu kendisi bildiriyor (`Pano ayrışması: 3 kart` uyarısı ~dakikada bir).

### Kota

Adım 6(g) için **tek** canlı kart (`20260910-235141-13-a2-hayalet-pencere-ol`,
`arastirmaci`, claude, tavan 20.000). Ledger satırı 97 → **98**;
`sum(total_tokens)` **4.474.945 → 4.474.945** (kartın satırı `RUNNING`,
`total_tokens` NULL kaldı: ölçüm süreci kapandığında CLI süreci öksüz kaldı).
Kart ölçümden sonra `board.stop` ile iptal edildi ve dosyası
`_archive/2026-09-10/qa-cards/` altına alındı (yedeği
`~/.entropy/backups/p13a2-qa/`), ayrışma sayısı **3 → 3** (yeni ayrışma
üretmedi). Başka model çağrısı **yok**.

### Açık kalanlar / doğrulanamayanlar

- **20 sn canlı exe koşumu ve exe penceresinden ikon görüntüsü alınamadı.**
  Kullanıcının `EntropyAI.exe`'si açık (PID 47920) ve tek örnek kilidi ikinci
  örneği hemen kapatıyor; talimat gereği kullanıcının exe'si kapatılmadı.
  Madde (b)'nin *paketlenmiş* kanıtı bu yüzden eksik; kaynak ağacında
  119/119 ikon çiziliyor ve QtAwesome fontu spec `datas`ında.
- `tasks_ledger.db` (23:51:47) ve `cognitive_memory.db` (7.684.096 →
  9.822.208 B, 23:49:13) değişti; **ikisi de süitten değil**: ledger 6(g)
  kartının (kart kimliği 23:51:41), bilişsel DB ise **koşmakta olan
  v0.10.1 exe'sinin** yazımı. Süit `tests/conftest.py` ile tmp'ye yalıtık ve
  `skills_state.json` mtime'ı hiç değişmedi.
- `scratch/ui/phase10/*.png` süit tarafından yeniden üretildi; sekizi de
  `git show HEAD:<yol> > <yol>` ile geri yazıldı (`git checkout --`
  kullanılmadı), o yolda `git status` **temiz**.
- `.entropy/logs/entropy_fault.log` COM `0x8001010d` kaydı bu koşuda
  **tekrarlamadı**; kök neden hâlâ **açık iş**.
- `scripts/ui_audit.py --gate --final` kapanışta bir kez
  `RuntimeError: libshiboken: Internal C++ object (EntropyEventBus) already
  deleted` yazdırıyor (`ui/widgets/knowledge_graph.py:4064` → 
  `core/event_bus.py:172`). Kapı çıkışını etkilemiyor (exit 0) ama gerçek bir
  yıkım sırası hatası: eşzamansız graf işi ana nesne silindikten sonra
  geri çağırıyor. **Açık iş.**

---

## 2.9 Faz 13-A2 — BEYİN KISA DEVRESİ KAPATILDI (2026-09-10, memory-rag-engineer) — kota 0

**Kullanıcı geri bildirimi (bağlayıcı):** "araştır" dendiğinde araştırma CANLI
koşar; beyin ajana **bağlamdır**, araştırmanın yerine geçmez.
Gerçek ekran kanıtı: kullanıcı "araştırma yap" dedi → kart `kind=research` →
kart CLI'ya hiç gitmeden *"Beyinden yanıtlandı (güven 0,49 ≥ CRAG eşiği)"*
notuyla kapandı ve "yanıt" diye gösterilen metin Entropy'nin **kimlik
düğümü**ydü. Entropy bunu aşmak için ikinci kartta `kind: write` seçmişti.

| Karar | Nerede | Neden |
|---|---|---|
| Otomatik kısayol **varsayılan KAPALI** (`brain_shortcut_enabled = False`) | `core/config.py:377-388`, kaydet/yükle `:531`, `:593-594` | 12-F'nin `kind=research` kısayolu kaldırıldı; dört kart türü de CLI'ya gider |
| `has_answer` artık "**kart canlı koşmadan kapatılabilir**" demek | `agents/amplification.py:202-259` (`BrainAnswer`), `:261-341` (`brain_lookup` + `_shortcut_decision`) | Tek anahtar burada olduğu için `agents/tasks.py`'ye (paralel ajan kapsamı) hiç dokunulmadı |
| Kısa devre koşulları: açık tercih **VE** CRAG isabeti **VE** güven ≥ **0,75** **VE** metin dolu **VE** kaynaklı | `amplification.py:320-341`, `SHORTCUT_MIN_CONFIDENCE = 0.75` (`:156`) | Açık tercih: `card.brain_only` alanı ya da metinde `--brain-only` / `[brain-only]` / "yalnız beyin" (`BRAIN_ONLY_MARKERS`) |
| Kısa devrede kart özeti **"CANLI ARAŞTIRMA YAPILMADI"** yazar | `amplification.py:244-259` (`note()`) | Kullanıcı bu kapanışı ayırt edebilsin |
| Kimlik (`is_identity=1` / `identity:core`) ve `legacy:pre-v2` düğümleri **asla** yanıt sayılmaz | `brain/context_builder.py:126-152` (`is_answer_node`, `is_identity_node`), `_recall_section` `:522-539` | 0,49'luk "yanıt" tam olarak buydu; güven artık yalnız yanıt sayılabilen düğümlerden |
| Kimlik düğümü bağlama **hiç paketlenmez** | `context_builder.py:1016-1022` (beyin paketinden `[Kimlik]` bloğu çıktı), `_recall_section` filtresi | Kimlik zaten sistem isteminin 1. bölümünde; ikinci kopya bütçe yiyordu |
| Tazelik ipuçlu sorguda `brain_has_answer` **False** | `context_builder.py:104-123` (`FRESHNESS_HINTS`, `wants_fresh_data`), `AssembledContext.freshness_required` `:189-205`, `build()` `:1187` | "güncel / sıfırdan / yeni / bugün / web / internet / tara" + tarih deseni (`2026`, `12.09.2026`) |
| İstem sözleşmesi artık kısa devre **vaat etmiyor** | `agents/board_tools.py:214-215` (`_ENTROPY_TOOL_TEXT`) (tek kaynak; `brain/system_prompt.board_tools_section` onu sunar) | Eski metin: "`research` kartı hafızada yanıt varsa CLI'ya HİÇ gitmez". Yeni metin 485 karakter → 600'lük `BUDGET_BOARD_TOOLS`'a **bütün** sığıyor (kırpılırsa `board_create` bloğu tümden düşüyordu) |
| `[BEYİN]` bölümü kalıyor ve tonu değişti | `amplification.py:223-242` (`prompt_section`) | "BAĞLAMDIR, yanıt değildir: doğrula… canlı araştırmanın yerine GEÇMEZ" |
| `infer_kind`: "incele", "tara" tek başlarına da research | `amplification.py:71-76` | Ölçülen eksik sezgi |

Amplifikasyon kilidinin diğer iki kapısı (**yenilik kotası** `MIN_NOVELTY_RATIO
= 0.30`, **kaynak zorunluluğu**) değişmedi.

### K tablosu — gerçek DB **salt okunur** (`~/.entropy/cognitive_memory.db`, 737 düğüm, 7.684.096 B)

Önce/sonra aynı DB üzerinde ölçüldü; "önce" eski davranış monkeypatch'le geri
getirilerek alındı (`scratchpad/k_before.py`, `brain_metrics.context_metrics()`).

| Ölçüt | Önce | Sonra | Not |
|---|---:|---:|---|
| K4 bağlam bütçe payı | %80,06 | **%74,59** | −5,47 puan = isteme ikinci kez konan kimlik bloğu (sorgu başına ~219 token) artık ödenmiyor |
| K5 damıtılmış pay | %46,65 | **%42,64** | payda küçüldü; damıtılmış token miktarı aynı |
| K6 wiki payı | %39,70 | **%42,59** | +2,89 puan: aynı bütçede wiki daha büyük pay alıyor (**PASS**) |
| K1 / K2 / K3 / K7 / K10 / K11 / K12 | — | %5,56 · 8/10·10/10 · %0,0 · 3 · 0 · 91,3 ms · 0 | sekiz hükmün sekizi **PASS** |

### Testler

| Süit | Sonuç |
|---|---|
| `tests/contracts/test_phase13_brain_shortcut.py` (yeni, 18 test) | **18 passed / 0,40 s** |
| `tests/contracts` + `test_phase12_skill_synthesis.py` + `test_phase11_amplification_lock.py` + `test_playbook_and_context.py` + `test_phase11_dream_wiki_brain.py` | **634 passed / 2 failed** → düzeltmelerden sonra aşağıdaki iki madde |
| `test_phase11_dream_wiki_brain.py` + `test_phase11_amplification_lock.py` + `test_playbook_and_context.py` (düzeltme sonrası) | **76 passed / 9,54 s** |

### Açık işler / doğrulanamayanlar

- **`card.brain_only` alanı henüz yok.** `TaskCard` (`agents/tasks.py`) ve
  `board_autonomy.create_card_from_args` bu kapsamın dışındaydı (paralel
  ajanlar). Bugün açık tercih yalnızca **metindeki işaretle** çalışıyor
  (`--brain-only`, "yalnız beyin"), çünkü `_ask_brain` beyne kartın
  başlık+hedefini geçiyor. Alan eklendiğinde `brain_lookup(..., card=card)`
  çağrısı tek satırlık iştir; `brain_only_requested` alanı zaten okuyor.
- `tests/contracts/test_spec_sync.py::test_spec_lists_every_entropy_module`
  **kırmızı** (`entropy.platform.proc`, `entropy.ui.widgets.lifecycle`
  `EntropyAI.spec` hiddenimports'ta yok). Bu iki modül **bu çalışmaya ait
  değil** (paralel ajanların yeni dosyaları); dokunulmadı.
- `tests/test_phase11_amplification_lock.py` ve
  `tests/contracts/test_phase12_board_autonomy.py` içindeki kısayol testleri
  `brain_lookup`'ı doğrudan sahteleyip `has_answer=True` verdikleri için hâlâ
  yeşil; artık **kapıyı değil, kapı sonrası bağlantıyı** ölçüyorlar. Kapının
  kendisi `test_phase13_brain_shortcut.py`'de.
- Tam süit (2.500+ test) bu dilimde **koşulmadı**; koşan kapsam yukarıdaki
  üç satırdır.

---

## 2.9b Faz 13-A2 — pano/köprü hijyeni (2026-09-10, agy-integration-engineer) — kota 0

Model çağrısı **0**. Kullanıcı geri bildiriminin üç maddesi (rozet yanlış
sağlayıcı, konsol pencereleri, "Oturumu yenile" gürültüsü) + QA artığı kart
temizliği.

### Ajan canlı durum API'si (sözleşme — arayüz rozetinin TEK kaynağı)

`entropy.core.identity.AgentSessionStore` (`src/entropy/core/identity.py:843`):

```python
store.status(name) -> {
    "state": "idle" | "running",
    "since": float | None,          # koşunun başlangıç zaman damgası
    "card_id": str, "card_title": str,
    "last_run_at": float | None,    # koşu BAŞINDA ve SONUNDA yazılır
    "provider": str,                # ajanın GÜNCEL sağlayıcısı
    "session": dict,                # o sağlayıcının oturum kaydı ({} = yok)
    "stale_sessions": [{"provider", "model", "updated_at"}],
}
store.mark_running(agent, card_id="", card_title="", provider="")
store.mark_idle(agent, provider="")
store.clear_live_state(agent) -> bool
store.current_provider(agent) -> str      # şartname > config varsayılanı
store.state_path(agent) -> Path           # Entropy/Board/agents/<ad>/state.json
```

* Canlı durum `session.json`ın **yanında** `state.json`dadır: `session.json`
  sağlayıcı anahtarlıdır ve `rotate`/`run_kwargs` onu baştan yazar; devir
  sırasında canlı durum silinmesin diye ayrıldı.
* Yazma boğazı **tek**: `TaskBoard.apply_event` → `_sync_agent_live_state`
  (`src/entropy/agents/tasks.py:833`). `taken`/`running` → `mark_running`,
  diğer her hedef → `mark_idle`. Böylece iptal, kilit düşmesi ve `reset` de
  rozeti boşa çeker. **Ofis kartları hariç** (ayrı kök kuralı).
* Rozet hatasının kökü: `ui/widgets/agent_session_badge.read_session` "en taze
  sağlayıcı kaydı"nı seçiyordu; ajan agy'ye geçtikten sonra bile saatler
  önceki claude oturumu gösteriliyordu. `status()` **güncel** sağlayıcının
  oturumunu döndürür, diğerlerini `stale_sessions` içinde verir.
* Çökme sonrası: `dispatcher.BoardDispatcherCore.reconcile` →
  `_clear_orphan_live_states` (`src/entropy/agents/dispatcher.py:390`) —
  `taken`/`running` bir kartı OLMAYAN her ajanın "running" durumu düşer.

### Alt süreç konsol pencereleri

Yardımcı: `src/entropy/platform/proc.py` → `popen_kwargs(**extra)`
(Windows'ta `CREATE_NO_WINDOW` + `STARTUPINFO(SW_HIDE)`, başka platformda boş
sözlük; çağıranın `creationflags`i EZİLMEZ, VEYA'lanır; `DETACHED_PROCESS`
varsa `CREATE_NO_WINDOW` eklenmez — ikisi birlikte geçersizdir).

Sözleşme testi `tests/contracts/test_phase13_board_hygiene.py` AST ile
`src/entropy/**` içindeki her `subprocess.{Popen,run,check_output,check_call,call}`
çağrısını tarar; `**popen_kwargs(...)` yoksa **kırmızı**.

| Sayı | Durum |
|---:|---|
| 25 | toplam `subprocess.*` spawn çağrısı |
| 19 | `popen_kwargs` ile gizlendi |
| 5 | muaf (kullanıcıya GÖRÜNMESİ istenen açıcılar: `explorer /select,`, `open -R`, `xdg-open`) |
| 1 | bekliyor: `desk/projects_panel.py:54` (`git branch`) — Desk arayüzü paralel ajanın kapsamı, testte `PENDING_UNHIDDEN` |

Ayrıca `core/identity.py`nin iki kimlik probu (`claude auth status`,
`agy models`) enjekte edilen `runner` üzerinden koştuğu için AST taramasına
takılmıyordu; ikisi de elle `popen_kwargs`e bağlandı ve `_creationflags()`
artık yardımcıya devrediyor.

**Ölçüm — bir kart koşusunda kaç alt süreç açılıyor:** `subprocess.run/Popen`
sayaçlanarak tek kart koşuldu (yalıtılmış kasa, `arastirmaci`, claude) →
**1 spawn** (CLI'ın kendisi, `core/claude_bridge.py:2412`), **gizli**.
Yani kullanıcının gördüğü "~20 pencere" kart koşusunun kendisinden DEĞİL;
düzeltilen asıl kaynaklar **bayrağı hiç olmayan** çağrılardı: 4 × `taskkill
/F /T` (`agy_bridge`), 1 × `taskkill` (`claude_bridge`), 2 × `git`
(`perf_history`). Kalan pencereler Qt tarafındadır (paralel ajan bakıyor).

### "Oturumu yenile" sessizleştirildi

`agents/session_budget._announce` artık `bus.task_notification` (OTONOM GÖREV
SONUCU kanalı) yerine `bus.terminal_output_received` + `bus.agents_updated`
kullanıyor. Sohbete otonom görev kartı, üst çubuğa "Görev: Ajan oturumu
tazelendi" çipi ve `session:<ajan>` görev kimliği **düşmüyor**; rapor
yazılmıyor, deftere (ledger) görev kaydı girmiyor. Testler:
`test_session_rotation_is_a_quiet_status_line`,
`test_rotation_does_not_write_a_task_to_the_ledger`.

### QA artığı kartların arşivi

FSM'e **T13** eklendi (`board_fsm.py`): `review`/`failed` → `canceled`,
**gerekçe (`reason`) zorunlu**; `done` terminal kalır. `board_events.board_drift`
artık dosyası olmayan `canceled` kartı ayrışma saymaz (arşivlenen kart panodan
kalkmış demektir).

Arşiv: `<kasa>/Entropy/_archive/2026-09-10/qa-cards/<kart>.json`
(projeksiyon anlık görüntüsü + kartın tüm olayları + gerekçe). **Hiçbir
rapor/kontrol noktası silinmedi**; kart `.md` dosyaları bu koşumdan önce zaten
yoktu (projeksiyonda asılıydılar).

| Kart | Eski durum | Başlık | Kanıt | Olay |
|---|---|---|---|---|
| `20260910-064253-kisa-teknik-not` | review | Kisa teknik not | 11-C QA canlı koşu 06:42 | seq 49 |
| `20260910-064500-kisa-teknik-not-2` | failed | Kisa teknik not 2 | 11-C QA canlı koşu 06:45 | seq 50 |
| `20260910-064722-gil-notu` | review | GIL notu | 11-C QA canlı koşu 06:47 | seq 51 |
| `20260910-064948-kisa-teknik-not-3` | review | Kisa teknik not 3 | 11-C QA canlı koşu 06:49 | seq 52 |
| `20260910-100914-python-dataclasses-vs-at` | review | Python dataclasses vs attrs… | §2.6 (a) | seq 53 |
| `20260910-102326-kisa-not-a` | review | Kisa not A | §2.6 (b) | seq 54 |
| `20260910-102335-kisa-not-b` | review | Kisa not B | §2.6 (b) | seq 55 |
| `20260910-102336-kisa-not-c` | review | Kisa not C | §2.6 (b) | seq 56 |
| `20260910-200343-devir-karti-d` | review | Kisa not D | §2.7 oturum devri | seq 57 |

**DOKUNULMAYAN kullanıcı kartları:** `20260910-224018-canivopets-com-medya-aja`
(assigned), `20260910-194435-canivopets-com-medya-uzm` (review),
`20260910-224237-canivopets-com-s-f-rdan-` (failed).
Ayrışma **11 → 2**; kalan iki satır kullanıcının kendi kartlarının silinmiş
`.md` dosyalarıdır (bilinçli olarak bırakıldı).

`Desk/Offices/Araştırma Ofisi/cards/20260910-033508-deneme.md` (ajan Alfa)
**bırakıldı**: Entropy panosunda değil, kullanıcının kendi ofisinin kartı ve
`events.jsonl`de izi yok — QA kaynağı **kanıtlanamadı**.

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
