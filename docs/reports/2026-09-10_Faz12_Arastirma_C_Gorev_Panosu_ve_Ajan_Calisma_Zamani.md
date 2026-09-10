# Faz 12 — Araştırma C: Görev Panosu ve Ajan Çalışma Zamanı (ikinci tur)

**Konu:** kullanıcının döngüsünün canlı denetimi, ajan kalıcılığı ve oturum bütçesi, `claude --bg` kararının tazelenmesi, araç yüzeyi budaması
**Depo:** `C:\EntropiAI` — `pyproject.toml:7` **v0.8.0** (STATE.md başlığı v0.9.4 diyor: **sürüm etiketi ile pyproject uyuşmuyor**, aşağıda D1), dal `ai/v0.1.7`, son commit `1815f32`
**Kip:** SALT OKUNUR. Kodda/kasada değişiklik yok; tek yazılı çıktı bu dosya. Model çağrısı yapılmadı — yalnızca `claude --version/--help`, `claude agents --help`, `agy --help` ve **kotasız** test koşusu.
**Tarih:** 2026-09-10
**Önceki tur:** [`2026-09-10_Faz11_Arastirma_C_...`](2026-09-10_Faz11_Arastirma_C_Gorev_Panosu_ve_Ajan_Calisma_Zamani.md) · [`2026-09-10_Faz11F_Spike_Kalici_Terminal.md`](2026-09-10_Faz11F_Spike_Kalici_Terminal.md)

---

## 0. Yönetici özeti

Faz 11'de önerilen dört taşıyıcı parçanın **dördü de kuruldu ve canlıda çalıştı**: durum makinesi (`board_fsm.py`, 8 durum), ekleme-yalnızca olay günlüğü (`board_events.py`, kasada 16 gerçek olay), çekmeli tetikleyici (`dispatcher.py`, `claims/*.lock`), ajan başına kalıcı oturum (`identity.AgentSessionStore`, kasada gerçek `session.json` + argv'de `--resume`). Kullanıcının döngüsünün **girdi → kart → TAKEN → koşu → rapor → sohbet** kolu uçtan uca kanıtlı.

Buna karşılık döngünün **baş tarafı hâlâ kapalı**: Entropy sohbet içinde "bunu X ajanına veriyorum" diyemiyor. `board_create` aracı yazılmış ama **hiçbir yerde çağrılmıyor, ayrıştırılmıyor ve Entropy'nin istemine hiç girmiyor** (§1.2, üç bağımsız grep kanıtı). Aynı şekilde `board_next`, `board_checkpoint`, `board_ask` blokları ayrıştırılıyor ama **yalnızca `board_finish` tüketiliyor**; canlı kartta ajanın yazdığı `[KONTROL NOKTASI]` bloğu kartın `checkpoint:` alanına **hiç işlenmedi** (§1.3).

En sert ölçüm kalıcılık maliyetinde: aynı ajanın üç kartı `--resume` ile **23.886 → 38.818 → 66.542** token (ledger, §2.1). Bu doğrusal değil; dördüncü kart ~110k'yı bulur. Bugün Claude kolunda **hiçbir oturum bütçesi politikası yok**; agy kolunda ise 15 turluk bir sıfırlama var ama kullanıcıya "bağlam özetleniyor" denip aslında **özet yapılmadan konuşma atılıyor** (§2.2). Öneri: ajan başına *oturum bütçesi* (kart sayısı + token tavanı + `/compact` turu), §6.2.

`claude --bg` kararı **değişmedi ve tazelendi**: CLI sürümü hâlâ **2.1.265**, `claude agents` alt komut yüzeyi aynı; erteleme gerekçeleri geçerli. Yeni fark edilen üç bayrak (`--autocompact <auto|tokens>`, `--fork-session`, `--no-session-persistence`) bütçe politikası için `--bg`'den daha ucuz kaldıraçlar sunuyor (§3).

---

## 1. Kullanıcının döngüsü — adım adım denetim

| # | Kullanıcının adımı | Bugünkü karşılığı | Durum | Kanıt |
|---|---|---|---|---|
| 1 | Girdi (Brain + Entropy Chat) | sohbet + beyin paketi | **var** | `context_builder`, STATE §2.3 |
| 2 | Beyin + internet araştırması | aktif yetenekler + `brain_lookup` kısayolu | **var, kısayol canlıda tetiklenmedi** | `tasks.py:1349`, `amplification.py:116` |
| 3 | Entropy **kendi kararıyla** görev üretir | **YOK** — `board.create` yalnızca `/task` ve `/desk task` | **eksik** | §1.2 |
| 4 | TASKBOARD'a görev | `Board/TASKBOARD.md` türetiliyor | **var** | kasada 5 kart, 8 sütun |
| 5 | Ajanlar tek tek tetiklenir | `BoardDispatcherCore.tick()`, `max_parallel=2` | **var** | `dispatcher.py:295-315` |
| 6 | TAKEN | `task.claimed` olayı + `claims/<id>.lock` | **var** | `events.jsonl` seq 14 |
| 7 | Rapor | özet + `output_paths` + wiki sayfası | **var** | kart dosyası |
| 8 | "tamamlandı" → Entropy sohbete alır | `task_report_ready` → sohbet rapor kartı | **var** | `tasks.py:1753`, `report_card_bridge.py:37` |
| 9 | Ajanlar terminallerde | gizli `Popen` + `agent_stream`; gerçek PTY yok | **yarım** | Faz 11-F |
| 10 | Model/efor AGENT.md + arayüz | `/agent model|effort`, `effort_selector.py` | **var** | STATE §3 |
| 11 | Araçlar ajanlara yardımcı | 4+1 pano aracı tanımlı, **1'i tüketiliyor** | **yarım** | §1.3 |

### 1.1 Canlı kanıt (kasadan okundu, koşu yapılmadı)

Kasa: `C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault\Entropy\`

```
Board/           TASKBOARD.md  agents/  claims/  events.jsonl   ← projection.json YOK (§1.6)
events.jsonl     16 satır, seq 1..16
TASKBOARD.md     review (3) · failed (2) · diğer sütunlar 0
Board/agents/arastirmaci/session.json
   {"claude": {"session_id":"aa2ce1f2-…","signature":"25f77bda76e0d6a7",
               "effort":"low","cwd":"C:\\EntropiAI","conversation_id":"aa2ce1f2-…"}}
```

Zincirin tamamı olay günlüğünde görülüyor (`task.claimed` → `run.started` (pid 30820) → `run.finished` + `proof.green=true`). **Durum makinesi gerçekten tek kapı:** `run.finished` yükünde `status: "review"` üretiliyor, `done`a insan geçiriyor.

Kotasız doğrulama (bu turda koşuldu):

```
QT_QPA_PLATFORM=offscreen python -m pytest tests/contracts/test_phase11_board.py \
  tests/test_phase11_claude_bg.py -q -p no:cacheprovider
→ 93 passed, 3,98 s
```

### 1.2 Boşluk G1 — Entropy'nin otonom görev üretimi hâlâ yok

Üç bağımsız kanıt:

1. `board_create` deposu genelinde **yalnızca üç satırda** geçiyor ve üçü de tanım dosyasında:
   `board_tools.py:21` (docstring), `:56` (`ENTROPY_TOOLS`), `:207` (`_ENTROPY_TOOL_TEXT`). **Yürütücü yok.**
2. `tools_section(for_entropy=True)` üretimde **sıfır çağıran**; tek çağrı `tests/contracts/test_phase11_board.py:544`. Üretim çağrısı `tasks.py:1260` ve o da `for_entropy` **vermiyor** → ajan istemi, Entropy istemi değil.
3. `board.create(` çağıranları: `harness.py:1612` (ofis alt kartı), `slash_commands.py:624` (`/task`), `slash_commands.py:1117` (`/desk task`). Üçü de **insan ya da orkestratör planı** tetikli.

**İyileşme (Faz 11'e göre):** `/task` artık kartı doğrudan koşturmuyor; `task.assigned` olayı yazıp tetikleyiciyi uyandırıyor ve "Pano sıradaki turda ajanı uyandıracak" diyor (`slash_commands.py:627-660`). İtmeli akış çekmeliye döndü. Eksik olan yalnızca **kararı verenin Entropy olması**.

### 1.3 Boşluk G2 — beş araçtan yalnızca biri tüketiliyor

`_board_tool_results` (`tasks.py:1817-1830`) blokları ayrıştırıyor ama dönen `calls` listesi `tasks.py:1608`'de alınıp **kullanılmıyor**; yalnızca `finish` argümanları işleniyor.

Canlı kanıt — kart `20260910-064948-kisa-teknik-not-3`: ajan çıktısında `[KONTROL NOKTASI]` ve `[KURAL]` blokları var, `[PANO board_finish]` bloğu da var. Sonuç:

* `proof` → **işlendi** (olay yükünde `proof.green=true`),
* `checkpoint:` → kart dosyasında **boş**,
* `[KURAL]` adayı → kullanıcıya sorulmadı (kalıcı kural akışı Entropy kartlarında yok; `parse_checkpoint` yalnızca `harness.py:307`, yani **ofis** tarafında).

`board_next` ve `board_ask` hiç yürütülmüyor; ajan `board_next` yazsa yanıt alamaz (kartı zaten tetikleyici itiyor — sözleşme ile davranış çelişiyor).

### 1.4 Boşluk G3 — araç blokları özete sızıyor

`[PANO …]`, `[KONTROL NOKTASI]`, `[KANIT]`, `[KURAL]` blokları özetten **temizlenmiyor** (depoda `PANO` geçen tek üretim satırı ayrıştırma tarafında; temizleyici yok). Sonuç: aynı ham metin (a) kartın `summary`sine, (b) `events.jsonl` yüküne, (c) `task_report_ready` üzerinden **sohbet rapor kartına**, (d) `apply_report_lock` yoluyla **hafıza kapısına** giriyor. Hafızaya JSON araç bloğu yazmak, "ajanlar hata/günlük yazmaz" kuralının ruhuna aykırı ve yenilik ölçümünü de kirletiyor.

### 1.5 G4 — `report_path` düzeltildi, canlıda **doğrulanmadı**

`tasks.py:1585-1596` artık rapor yolunu karta yazıyor ve `output_paths`a ekliyor; `payload["report_path"]` projeksiyona taşınıyor (`tasks.py:1626-1630`). Ama kasadaki tek gerçek koşum bu düzeltmeden **önce** yapılmış: kart dosyasında `report_path:` **boş**. → Faz 12'de tek kartlık canlı doğrulama şart (kabul ölçütü K-2, §6).

### 1.6 G6 — projeksiyon karması üretimde hiç hesaplanmıyor

`BoardEventLog.write_projection` (`board_events.py:280`) ve `board_projection_path` (`paths.py:183`) **üretimde sıfır çağıran** (grep: yalnızca tanım + testler). Üretimde kullanılan yol `TaskBoard.rewrite_taskboard` (`tasks.py:890-907`) ve o, karmayı **bilerek boş** geçiyor:

```python
view = {"last_seq": self.events.last_seq(), "projection_hash": ""}
```

Canlı `TASKBOARD.md` bunu doğruluyor: `Son olay: 16 · Projeksiyon karması: ``. Yani "iki görünümün ayrışması `projection_hash` ile ölçülebiliyor" iddiası **bugün ölçülmüyor**; `Board/projection.json` hiç yazılmamış.

### 1.7 Ofis ↔ Entropy ayrımı — temiz

Tetikleyici ofis kartlarına **dört ayrı yerde** dokunmuyor: `running_count` (`dispatcher.py:234`), `busy` (`:240`), `candidates` (`:257`), `tick` içinde ajan künyesi ofisliyse atlama (`:311`), `reconcile` (`:364`). Araç sözleşmesi de ofis kartına girmiyor (`tasks.py:1254-1264`). Pano bileşeni `office` filtresi ile hem Entropy hem ofis panosunu çizebiliyor (`task_board_widget.py:692-702, 869-871`). **Tek yönlü akış korunmuş** (`_report_to_entropy` yorumu, `tasks.py:1725-1734`: ofis kartları buraya girmez).

---

## 2. Ajan kalıcılığı ve kota

### 2.1 Ölçüm — `--resume` bedeli (ledger, `~/.entropy/tasks_ledger.db`)

| Kart | Oturum | total_tokens | Artış |
|---|---|---:|---:|
| `card-…-kisa-teknik-not` | yeni (`--session-id`) | **23.886** | — |
| `card-…-kisa-teknik-not-2` | R1 hatası | `NULL` (FAILED) | — |
| `card-…-gil-notu` | `--resume` | **38.818** | +14.932 |
| `card-…-kisa-teknik-not-3` | `--resume` | **66.542** | +27.724 |

Toplam **129.246**. Artış hızlanıyor (14,9k → 27,7k): her tur bütün geçmişi yeniden gönderiyor. Bu, kalıcılığın bilinen bedeli — "bir kodlama ajanı her turda bütün konuşmayı yeniden gönderir; N'inci turun maliyeti 1..N-1 turlarının ağırlığını taşır" (kaynak K7).

**Kazanç tarafı da ölçüldü ve gerçek:** 3. kartta ajan kendiliğinden "bu raporu 06:43'te zaten ürettim" deyip işi tekrarlamadı (olay yükü seq 16). Yani kalıcılık **işe yarıyor**; sorun bedelin sınırsız olması.

### 2.2 Bugünkü politika — asimetrik ve yanıltıcı

* **Claude kolu:** `session_turn_count` sayılıyor (`claude_bridge.py:1302`) ama **hiçbir eşik yok**. Oturum yalnızca imza (`sha1(istem|model|efor)`) düşünce tazeleniyor (`identity.py:719-736`).
* **agy kolu:** 15 turda sıfırlama var (`agy_bridge.py:1884-1894`) ama kullanıcıya **"Bağlam özetlenerek yeni temiz bir AGY oturumuna aktarılıyor"** deniyor; kod ise özet üretmeden `current_conversation_id = None` yapıyor. **Mesaj yanlış** (D2).
* **Worktree kartlarında kalıcılık kapalı:** `if card.agent and not card.worktree:` (`tasks.py:1447`) → PR/worktree kartları her seferinde taze oturum. Bilinçli mi belgesiz mi, belirsiz (D3).
* agy'de `--resume` eşdeğeri **`--conversation <id>`** doğrulandı (`agy --help`, `agy_bridge.py:1117-1118`); oturum kimliği yalnızca akıştan yakalanabiliyor (`identity.py:745-748`).

### 2.3 Bağlam kırpma kaldıraçları (bu turda ölçülen CLI yüzeyi)

`claude --help` (2.1.265) çıktısından:

| Bayrak | Yardım metni | Bizim için |
|---|---|---|
| `--autocompact <auto\|tokens>` | "Auto-compact window size (auto, or 100k–1M tokens)" | pencere tavanı; **doğrudan bağlanabilir** |
| `--fork-session` | "When resuming, create a new session ID instead of reusing the original" | dallanma; kart başına yan kol için |
| `--no-session-persistence` | "sessions will not be saved to disk and cannot be resumed (only works with --print)" | tek-atımlık kartlar için ucuzlatıcı |
| `--max-budget-usd` | "only works with --print" | **abonelik kipinde anlamsız** (API çağrısı ücretlendirmesi) |
| `--max-turns` | **YOK** (302 satırlık yardım çıktısında geçmiyor) | SDK'ya özgü; plana yazılmamalı |

`/compact` Entropy'nin kendi yerel komut listesinde zaten var (34 yerel komut arasında) ama **ajan oturumlarına uygulanmıyor**; ajan oturumuna `--resume` ile tek turluk `"/compact"` istemi göndermek, ölçülmemiş ama düşük riskli bir kaldıraç (kaynak K7: "özellik bittiğinde doğal kırılma noktasında `/compact`").

---

## 3. `claude --bg` kararının tazelenmesi

| Soru | Faz 11-F | Bugün (2026-09-10, bu turda ölçüldü) |
|---|---|---|
| CLI sürümü | 2.1.265 | **2.1.265 — değişmedi** |
| `claude agents` yüzeyi | `--json/--all/--cwd` | **aynı**, ek olarak `--agent/--effort/--model/--mcp-config/--add-dir` (dağıtılan oturumlar için varsayılanlar) |
| `--bg` + `-p` çakışması | var | yardım metni aynı ("Start the session in the background and return immediately") |
| `--resume` ile çatallanma uyarısı | var | yardım metninde hâlâ açıkça yazılı: "or starts a copy and says so when the session is already running" |
| agy karşılığı | yok | **hâlâ yok** (`agy --help` 1.2.0: `--conversation`, `--continue` var; `--bg`/`attach` yok) |

**Karar: erteleme sürsün.** Yeni bir gerekçe de eklendi: bütçe sorununun asıl çözümü (`--autocompact`, oturum sıfırlama) `--bg` gerektirmiyor ve mevcut `stream-json` telemetrisini korur. `--bg` yalnızca "gece boyu çalışsın" işaretli ofis kartları için, Faz 13'te değerlendirilmeli.

---

## 4. Dış araştırma (2025–2026)

**4.1 Dosya tabanlı ajan panoları — bağımsız yakınsama.** `kanban-md` (K5) tasarımı bizimkiyle şaşırtıcı ölçüde örtüşüyor: görev = YAML ön bilgili `.md`; **`pick --claim <agent>`** tek çağrıda bul+sahiplen+taşı (bizde `board_next`, `board_tools.py:14`); sahiplenme `claimed_by` alanı ve **varsayılan 1 saatlik süre aşımı** (bizde `board_claim_timeout_s = 3600`); ajanlara özel `--compact` çıktı biçimi ("JSON'dan %70 daha az token"). Fark: onlarda ~20 CLI komutu, bizde ajana açık **4** araç. `Backlog.md` (K6) da aynı deseni "kabul ölçütleri + Definition of Done" ile kuruyor — bizim `## Kabul ölçütleri` bölümümüzün karşılığı.

**4.2 Uzun ömürlü ajan harness'ı (Anthropic, Kasım 2025 — K2).** Öneriler ve bizdeki karşılığı:
- *Initializer agent* + `init.sh` + `claude-progress.txt` → bizde `office_workspace` BOARD/ARCHITECTURE/RULES dosyaları **ofis tarafında var, Entropy tarafında yok**.
- *"Özellik listesini JSON tut, Markdown değil; model JSON'u daha az kurcalar."* → bizim kart gövdesi Markdown; `projection.json` **hiç yazılmıyor** (§1.6). Doğrudan uygulanabilir bir düzeltme.
- *Her oturum tek özellik*, sonunda commit + uçtan uca test → bizim "close with proof" kuralının aynısı; bizde araç düzeyinde zorlanıyor (`validate_finish`, `board_tools.py:105-120`) — **bu bizim önde olduğumuz yer.**
- *Compaction + yapılandırılmış not alma + alt ajan mimarisi* üçlüsü bağlam tükenmesinin standart çaresi (K1).

**4.3 Dayanıklı yürütme / olay kaynağı.** LangGraph checkpointer'ı "her mantıksal adımda durumu kalıcı depoya yaz, çökmede son kontrol noktasından devam et" diye tanımlıyor (K3); 2026 eleştirisi ise "checkpoint ≠ durable execution: yeniden oynatma ve kesinlikle-bir-kez garantisi yok" (K4). Bizim `events.jsonl` + `idempotency_key` + `attempt_id` şeması bu eleştirinin **doğru tarafında**: idempotens anahtarı yeniden oynatmada çift etkiyi engelliyor. Eksik olan tek şey projeksiyonun doğrulanması (§1.6).

**4.4 Ajanlar için araç yazımı (Anthropic, Eylül 2025 — K8/K9).** İlkeler: az sayıda **yüksek kaldıraçlı** araç seç; ad alanı ayır; kimlik yerine insan-okunur alan döndür; **yanıtı 25.000 token altında tut**; araç açıklamasını istem gibi yaz; değerlendirme güdümlü yinele. Bizim 4+1 araçlık yüzey ve `CRITERIA_LIMIT/INPUT_PATHS_LIMIT` kırpmaları bu ilkelerle uyumlu — **sorun araç sayısı değil, yürütücü eksikliği** (§1.3).

---

## 5. Araç yüzeyi envanteri

| Yüzey | Sayı | Kanıt | Kime görünüyor |
|---|---:|---|---|
| Yerel slash komutu | **34** | `name="/…"` benzersiz sayımı, `slash_commands.py` | kullanıcı + Entropy |
| Yetenek/araç türevi komut | değişken | `slash_commands.py:2008-2105` (yetenek ve araç adlarından üretiliyor) | kullanıcı |
| Pano aracı — ajan | **4** (`board_next`, `board_checkpoint`, `board_finish`, `board_ask`) | `board_tools.py:55-56` | ajan |
| Pano aracı — Entropy | **1** (`board_create`) | `board_tools.py:56` | **kimse (bağlı değil)** |
| Yerel `skills/` klasörü | **12 girdi** (2'si eski `_` adlandırmasının kopyası: `media_agency_soldier`, `slide_deck_architect`) | `ls skills` | Entropy |
| MCP çekmecesi | izole kipte kapalı (`--strict-mcp-config`) | STATE §3 | ajan: hayır |

**Budama/birleştirme önerisi (K8 ilkesiyle):**

1. **Ekleme değil bağlama:** yeni araç eklenmesin; var olan 4+1'in **yürütücüsü** yazılsın (§6.1). "Sıfır araç" değil, "sıfır yürütücü" sorunu.
2. `board_next`'i **kaldır ya da gerçek yap.** Tetikleyici kartı zaten itiyor; sözleşmede duran ama yanıtsız kalan araç, modeli boşuna deneme yapmaya itiyor (ölçülmedi ama K8'in "kararsız yüzey" uyarısı birebir bu).
3. Yerel 34 komutta **birleştirilebilir üçlü**: `/agents` + `/agent` (tek komut, argümansız = liste), `/task` + `/tasks`, `/distill` + `/wiki` (ikisi de damıtım hattı). 34 → **31**.
4. `skills/` içindeki **iki kopya klasör** temizlensin (`repo-curator`): 12 → 10.
5. Ajan yanıt bütçesi: `board_next` yükü zaten kırpılıyor; aynı kural `build_prompt`'un proje dosya bölümüne de uygulanmalı (K8: 25k token tavanı).

---

## 6. Tasarım — kalan boşluklar için somut plan

### 6.1 İş A — Entropy'nin otonom görev üretimi (G1 + G2 + G3)

**Ne:** Entropy'nin sohbet yanıtından `[PANO board_create]` bloğunu ayrıştıran, kartı `backlog`ta açıp `task.assigned` olayı yazan ve tetikleyiciyi uyandıran tek bir yürütücü. Aynı yürütücü ajan tarafında `board_checkpoint` ve `board_ask`ı da tüketsin; `board_next` ya gerçek yapılsın ya sözleşmeden çıkarılsın.

**Nerede:** yeni `agents/board_tool_exec.py` (tek giriş `execute(calls, card=None, actor=...)`), çağrı noktaları `tasks.py:1608` (ajan) ve sohbet yanıt kancası (`chat_mode.py` / `zen_mode.py` yanıt tamamlandığında).

**Ayrıca:** özet temizleyici — bloklar karta yazılmadan **önce** metinden çıkarılsın (`strip_tool_blocks`), ham metin yalnızca olay günlüğünde kalsın.

**Kabul ölçütleri**
- K-A1: Entropy'nin istemi `tools_section(for_entropy=True)` içerir; sözleşme testi bunu doğrular.
- K-A2: Sahte köprü ile: yanıtta `board_create` bloğu → kasada kart dosyası + `events.jsonl` `task.created` + `task.assigned` satırı; tetikleyici `tick()` kartı seçer.
- K-A3: `board_checkpoint` bloğu → kartın `checkpoint` alanı dolar; `board_ask` → posta kutusuna mesaj, kart durumu **değişmez**.
- K-A4: Kartın `summary` alanında `[PANO`, `[KONTROL NOKTASI]`, `[KANIT]` dizeleri **bulunmaz** (regresyon testi).
- K-A5: Ofis kartında `board_create` **reddedilir** (tek yönlü akış kuralı).

**Ajan:** `agy-integration-engineer` (yürütücü + köprü kancası), `ui-engineer` (sohbette "kart açıldı" makbuzu). **Kota:** kod tarafı kotasız; canlı doğrulama **1 kart ≈ 25k token**.

### 6.2 İş B — oturum bütçesi politikası (G5)

**Politika (öneri, ölçüme dayalı):** `AgentSessionStore` girdisine üç alan eklensin — `cards_in_session`, `tokens_in_session`, `last_reset_at`. Kural:

* `cards_in_session ≥ 3` **veya** `tokens_in_session ≥ 60.000` → oturum kapanır, sonraki kart taze `--session-id` ile başlar;
* kapanmadan önce **tek `/compact` turu** (isteğe bağlı, ayarla) ve özet kartın notuna değil `Board/agents/<ad>/handoff.md` dosyasına yazılır — devir dosyası yeni oturumun ilk isteminde okunur (K2'nin `claude-progress.txt` deseni);
* Claude kolunda ek olarak `--autocompact 100k` sabit verilsin;
* agy kolundaki 15 turluk sıfırlamanın **mesajı düzeltilsin** ya da gerçekten özet üretsin (D2).

Eşiklerin gerekçesi: ölçülen 3. kart 66,5k; 4. kart ekstrapolasyonla ~110k ve 90k tavanını tek başına aşar.

**Kabul ölçütleri**
- K-B1: Üç kart sonrası `session.json`'da yeni `session_id`; argv'de `--session-id` (`--resume` değil).
- K-B2: `handoff.md` yazılıyor ve yeni oturumun isteminde geçiyor.
- K-B3: Sahte ledger ile 4 kartlık senaryoda toplam token, politikasız senaryonun **%70'inin altında** (birim testte simüle edilir; canlı doğrulama Faz 12 kapanışına bırakılır).
- K-B4: agy kolunda kullanıcıya gösterilen metin koddaki davranışla birebir uyuşur.

**Ajan:** `agy-integration-engineer`. **Kota:** kotasız (birim test); isteğe bağlı canlı doğrulama 4 kart ≈ 60k.

### 6.3 İş C — projeksiyon doğrulaması (G6)

`rewrite_taskboard` kart dosyalarından çizmeye devam etsin ama **her yazımda** `events.project()` çalıştırılıp `projection.json` yazılsın ve iki görünüm ayrışırsa `TASKBOARD.md` başlığına "⚠ ayrışma: N kart" satırı düşsün.

- K-C1: `Board/projection.json` üretimde oluşur; `projection_hash` boş değildir.
- K-C2: Kart dosyası elle bozulduğunda ayrışma satırı görünür; düzeltilince kaybolur.

**Ajan:** `memory-rag-engineer` (olay/projeksiyon sahibi) veya `agy-integration-engineer`. **Kota:** 0.

### 6.4 İş D — ofis ↔ Entropy birleşik pano görünümü

Ayrım kodda temiz (§1.7); eksik olan **tek ekranda iki panoyu yan yana** gösteren okuma-amaçlı görünüm. `TaskBoardWidget` zaten `office` parametresi alıyor → yeni bileşen değil, **iki örnek + üst sekme**.
- K-D1: Entropy kartları ofis sütunlarına, ofis kartları Entropy sütunlarına **sızmaz** (`office` filtresi testi).
- K-D2: Ofis panosunda "Çalıştır" düğmesi **yok** (ofis kartını harness koşturur).
**Ajan:** `ui-engineer`. **Kota:** 0.

### 6.5 İş E — agy kalıcılığı ve gerçek terminal

* agy: `--conversation` yolu zaten bağlı; eksik olan **kimlik yakalama sonrası kalıcı yazım** doğrulaması → `record_captured` için canlı olmayan bir sözleşme testi (K-E1).
* Gerçek terminal: `claude --bg` **ertelensin** (§3); kullanıcıya "gerçek terminal" hissini `terminal_pane` + `agent_stream` vermeye devam etsin. Kalıcı ajan rozetini (`persistent: bool`) Faz 13'e bırak.

---

## 7. Karar özeti

| # | Karar | Gerekçe | Sahip |
|---|---|---|---|
| 1 | `board_create` + `board_checkpoint` + `board_ask` yürütücüsü yazılsın | araç var, yürütücü yok (§1.2-1.3) | agy-integration-engineer |
| 2 | Araç/etiket blokları özetten temizlensin | bloklar sohbete ve hafızaya sızıyor (§1.4) | agy-integration-engineer |
| 3 | Oturum bütçesi: 3 kart / 60k token + handoff dosyası + `--autocompact` | 23,9k→38,8k→66,5k ölçümü (§2.1) | agy-integration-engineer |
| 4 | `board_next` ya gerçek yapılsın ya sözleşmeden çıkarılsın | yanıtsız araç yüzeyi (K8) | agy-integration-engineer |
| 5 | `projection.json` + ayrışma uyarısı üretime bağlansın | karma hep boş (§1.6) | memory-rag-engineer |
| 6 | `claude --bg` ertelenmeye devam | CLI değişmedi; ucuz kaldıraçlar var (§3) | — |
| 7 | Slash 34→31 birleştirme, `skills/` kopya klasör temizliği | K8 "az ve güçlü" (§5) | repo-curator |
| 8 | `report_path` canlı tek kartla doğrulansın | düzeltme var, kanıt yok (§1.5) | qa-build-engineer |
| 9 | `pyproject` sürümü STATE ile hizalansın | 0.8.0 vs v0.9.4 (D1) | repo-curator |

---

## 8. Riskler

* **R-A:** Otonom kart üretimi açılırsa Entropy kendi kendine kart yağdırabilir. Önlem: `board_create` için tur başına **tavan 1 kart** + `amplification_lock` açık + kart açılışında kullanıcıya makbuz.
* **R-B:** Oturum sıfırlama, 3. kartta görülen "bunu zaten yaptım" kazanımını öldürür. Önlem: `handoff.md` + beyin kısayolu (`brain_lookup`) birlikte çalışsın; kayıp ölçülsün (K-B3).
* **R-C:** Özet temizleyici fazla agresif olursa kanıt metni kaybolur. Önlem: ham metin `events.jsonl`'de kalır; temizlik yalnızca kart/sohbet/hafıza yolunda.
* **R-D:** `--autocompact` davranışı belgelenmiş bir API değil, sürüm bağımlı (2.1.265). Önlem: bayrak bilinmeyen sürümde sessizce düşürülsün.
* **R-E:** Yorumla davranış çelişkileri (agy 15-tur mesajı) kullanıcı güvenini bozuyor; her politika değişikliğinde metin de güncellensin.

## 9. Doğrulanamayanlar

* **D1:** `pyproject.toml:7` **0.8.0**, STATE.md başlığı **v0.9.4** — hangisinin doğru olduğu bu turda çözülemedi.
* **D2:** agy 15-tur sıfırlamasının "özetleyerek aktarma" iddiası kodda karşılıksız görünüyor; başka bir yolda özet üretiliyor olabilir (aranıp bulunamadı).
* **D3:** `not card.worktree` koşulunun (kalıcılığın worktree kartlarında kapalı olması) bilinçli bir karar mı olduğu belgelenmemiş.
* **D4:** `board_tools.py` docstring'indeki "MCP çekmecesi 119 ad ≈ 2,4k token, 32 yetenek ≈ 3,8k token" sayıları bu turda **yeniden ölçülmedi**; yerel `skills/` klasöründe 12 girdi var.
* **D5:** Beyin kısayolunun (`_brain_shortcut`) canlıda tetiklenip tetiklenmediği hâlâ ölçülmedi (kota).
* **D6:** `/compact` isteminin `--resume` üzerinden ajan oturumuna gönderilmesinin gerçekten çalıştığı **ölçülmedi** (model çağrısı gerekirdi).
* **D7:** `--autocompact` ve `--fork-session` bayraklarının abonelik kimliğiyle `-p` kipinde etkisi ölçülmedi (yalnızca yardım metni okundu).

## 10. Kaynaklar

- **K1** Anthropic — *Effective context engineering for AI agents* (2025): https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- **K2** Anthropic — *Effective harnesses for long-running agents* (Kasım 2025): https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- **K3** LangChain — *Durable execution* (LangGraph belgeleri, 2026): https://docs.langchain.com/oss/python/langgraph/durable-execution
- **K4** Diagrid — *Checkpoints are not durable execution* (2026): https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows
- **K5** `antopolskiy/kanban-md` — dosya tabanlı kanban, `pick --claim`, `--compact`: https://github.com/antopolskiy/kanban-md
- **K6** `MrLesk/Backlog.md` — Markdown görev panosu, kabul ölçütleri/DoD: https://github.com/MrLesk/Backlog.md
- **K7** *Claude Code Token Optimization* (2026) — tur maliyetinin birikmesi, `/compact` ve `/clear` disiplini: https://buildtolaunch.substack.com/p/claude-code-token-optimization
- **K8** Anthropic — *Writing effective tools for agents* (Eylül 2025) özet ve ADR uyarlaması: https://github.com/vishnu2kmohan/mcp-server-langgraph/blob/main/adr/adr-0023-anthropic-tool-design-best-practices.md
- **K9** Anthropic Engineering ana sayfası (yazı dizini): https://www.anthropic.com/engineering
- **K10** *The Case for Markdown as Your Agent's Task Format* (2026): https://dev.to/battyterm/the-case-for-markdown-as-your-agents-task-format-6mp

**Yerel komut kanıtları:** `claude --version` → `2.1.265 (Claude Code)`; `agy --version` → `1.2.0`; `claude --help` (302 satır), `claude agents --help`, `agy --help` — hepsi kotasızdır.
