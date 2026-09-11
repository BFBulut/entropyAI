# Entropy AI — Yaşayan Mimari

> **Bu dosya kaynağın kendisiyle birlikte güncellenir.** Bir sözleşme değişirse (paket yeri,
> veri kökü, sinyal adı, kart alanı) aynı commit'te burası da değişir. Eskimiş bir mimari
> belgesi olmamasının tek yolu budur; `docs/_archive/prototype/` altındaki eski belgeler
> tam olarak bu kural uygulanmadığı için arşive düştü.
>
> Sürüm: v0.12.0 (ağaç; son etiket v0.11.3) · Dal: `ai/v0.1.7` · Son güncelleme: 2026-09-11
> (Faz 14-F belge kapanışı)
>
> **"Hedef" etiketi bir sözleşme değildir.** Bu belgede yalnız **bugün kod olan** şeyler
> etiketsiz anlatılır; henüz yazılmamış olan her şey açıkça **(… hedefi)** diye
> işaretlenir ve kod bittiğinde etiket aynı commit'te kalkar.
> Faz 14'ün dört "hedef" bölümü (§6.4–§6.7) 14-A…14-E ile **kod oldu**; etiketleri
> 14-F'de kaldırıldı ve bölümler ölçülen davranışa göre yeniden yazıldı.
> Güncel durum ve açık işler için: [`STATE.md`](STATE.md) · Kararlar için: [`adr/`](adr/)

---

## 1. İki ürün, tek depo

| | Entropy AI | Entropy Agent Desk |
|---|---|---|
| Ne | Kişisel, kendi kendini geliştiren yapay zeka: beyin (RAG + hafıza), kendi ajanları, görev panosu, üç arayüz kipi | Entropy'nin **içine gömülü ayrı uygulama**: ofisler, orkestratörler, terminallerde yazılım geliştiren alt ajanlar |
| Kod | `src/entropy/{core,agents,brain,skills,ui,mcp,scheduler,platform,tools}` | `src/entropy/desk/` + `src/entropy/agents/{desk_registry,harness,offices,worktrees,pr_flow,templates}.py` |
| Veri kökü (kasa) | `<kasa>/Entropy/**` | `<kasa>/Desk/**` |
| Ajanları | `Entropy/Agents/<ad>/AGENT.md` | `Desk/Offices/<ofis>/agents/**` |

**Bilgi tek yönlüdür.** Entropy Desk'in mimarisini bilir ve onu geliştirebilir; Desk
Entropy'nin mimarisini **bilmez**. Orkestratör istemlerinde Entropy'nin adı geçmez.
**Görev akışı da tek yönlüdür:** Entropy Desk orkestratörlerine görev/mesaj gönderir ve
rapor alır; Desk Entropy'nin panosuna kart **itemez**. Gerekçe ve zorlayıcı testler:
[ADR-0001](adr/ADR-0001-desk-ayrimi.md), `tests/contracts/test_phase9_desk_separation.py`.

---

## 2. Paketler

> **Ölçüm tarihi 2026-09-11** (`find src/entropy -name '*.py' | wc -l`, satırlar `cat | wc -l`).
> Önceki tablo Faz 11'den kalmıştı ve `agents/` için **%59 eksik** sayı veriyordu; "yaşayan
> mimari" kuralı burada çiğnenmişti (Faz 14 A notu §2.1, §3 madde 8). Sayı değiştiğinde
> tablo **aynı commit'te** yeniden ölçülür.

| Paket | Dosya | Satır | Rol |
|---|---:|---:|---|
| `ui/` (+ `modes/`, `widgets/`, `themes/`, `design/`) | 58 | 27.149 | PySide6 kabuğu: Zen / Chat / Floating kipleri, 44 widget, üst bölüm şeridi, sağ tam panel |
| `brain/` (+ `rag/`, `obsidian/`, `supabase/`) | 29 | 18.067 | bilişsel bellek, graf, wiki, playbook, bağlam kurucu, kapı, **alt ajan hafıza yazarı**, artık arşivi |
| `core/` | 21 | 15.793 | yapılandırma, olay veriyolu, iki sağlayıcı köprüsü, **bekleyen işler kuyruğu**, **izin MCP sunucusu**, slash komutlar, kilit, kimlik, defter |
| `agents/` | 23 | 14.373 | ajan kayıt defteri, **geçici ajan döngüsü**, görev kartları, FSM, olay günlüğü, tetikleyici, harness, posta kutusu, worktree, PR akışı, şablonlar, Desk yönetimi |
| `desk/` (+ `engine/`, `assets/`, `templates/`) | 20 | 6.712 | Agent Desk penceresi, piksel sahne motoru, paneller |
| `skills/` | 5 | 1.972 | `SKILL.md` keşfi (`manager.py`) + motorlar (tembel yüklenir) |
| `mcp/` · `scheduler/` · `platform/` · `tools/` | 9 | 1.111 | MCP yapılandırması, zamanlayıcı, Windows panosu (`platform/clipboard.py`), gizli alt süreç (`platform/proc.py`), araç sentezleyici |
| **Toplam** | **167** | **85.520** | test dosyası **209** · toplanan test sayısı 14-F kapanış QA'sında ölçülür |

> Faz 14 farkı (14-A…14-E): **+9 modül / +4.327 satır**. Yeni modüller:
> `agents/ephemeral.py`, `core/pending.py`, `core/permission_server.py`,
> `core/permission_mcp_main.py`, `brain/agent_memory_writer.py`,
> `brain/artifact_archive.py`, `ui/widgets/nav_strip.py` ve düzen/onay widget'ları.

**Bellek paketinin adı `entropy.brain`** (Faz 13-B, [ADR-0008](adr/ADR-0008-brain-paket-tasimasi.md)).
Eski ad ve uyumluluk şimi **v0.12.0'da kaldırıldı** (Faz 14-F); eski adın içe
aktarımı artık `ModuleNotFoundError` verir. **Veri yolları paket adından bağımsızdır
ve değişmedi:** `~/.entropy/memory/`, kasada `Entropy/Memory`.

**Arşive inen kod (ürün yüzeyinde yok):** `core/claude_bg.py` (739 satır, Faz 11-F kalıcı
terminal spike'ı) Faz 13-C'de `docs/_archive/spikes/claude_bg/` altına alındı, spec girdisi
kaldırıldı, testi `tests/_reference/` altında ve **toplanmıyor**
([ADR-0009](adr/ADR-0009-claude-bg-arsivlendi.md), ADR-0007 madde 4'ün koşulu).
`platform/autostart.py` **kaldırıldı** — ayar vardı, davranış yoktu
([ADR-0006](adr/ADR-0006-autostart-kaldirildi.md)).

Giriş noktaları: `run_entropy.py` → `entropy.main:main`; `pyproject.toml`
`[project.scripts] entropy = "entropy.main:main"`; paketleme `EntropyAI.spec`.

> **`EntropyAI.spec` hiddenimports bir dizgi listesidir.** Bir paket yalnızca
> `importlib` ile çağrılıyorsa PyInstaller'ın statik tarayıcısı göremez ve `.exe`
> **sessizce eksik** paketlenir (Faz 10-C'de worktree/PR/şablon/makbuz yolları böyle
> kapanmıştı). Yeni bir tembel modül eklendiğinde spec'e satır eklemek zorunludur.
> Aynı nedenle `skills/__init__.py` PEP 562 `__getattr__` ile tembel yüklenen
> `media_agency_soldier` motorunu spec'teki hiddenimports satırı ayakta tutar.

---

## 3. Veri kökleri

### 3.0 Ölçülen gerçek: veri kökü **tek değil, üç parçalı** (Faz 14 bulgusu)

`_resolve_state_dir()` bir sıra tanımlıyor ama **7 modül `Path.home()/".entropy"` yolunu
sabit yazıyor**, dolayısıyla ayarlar ile veritabanları farklı köklere düşüyor
(A notu §2.2, ölçüm 2026-09-11):

| Kök | İçerik | Durum |
|---|---|---|
| `<depo>\.entropy` | `settings.json`, `chat_history.json`, `logs/`, **boş** `tasks_ledger.db` (0 B) | `_resolve_state_dir()` sırasının kazananı |
| `~/.entropy` | `cognitive_memory.db` (9,85 MB), **canlı** `tasks_ledger.db`, `memory/`, `skills_state.json`, `scheduler_tasks.json` | sabit yazılmış yol (7 modül) |
| `%LOCALAPPDATA%\EntropyAI` | bayat `settings.json` | üçüncü sıra; artık yazılmıyor |

Sabit yazan modüller: `brain/supabase/cognitive_memory.py`, `core/task_ledger.py`,
`core/config.py` (üç yer), `skills/manager.py`, `scheduler/cron_engine.py`,
`platform/clipboard.py`, `skills/media_agency_soldier_engine.py`.

**Faz 14'te açılan tek kaynak (kod):** `core/paths.data_root()` — sırası
`ENTROPY_DATA_ROOT` ortam değişkeni → `config.STATE_DIR` (yani
`_resolve_state_dir()` sonucu). Faz 14'te doğan her yeni durum bu köke yazar:

| Çağrı | Ne yazar |
|---|---|
| `paths.data_root()` | Faz 14 durumunun kökü; testler ve canlı koşumlar `ENTROPY_DATA_ROOT` ile izole edilir |
| `paths.pending_root()` | `<veri kökü>/pending/<id>.json` — bekleyen işler kuyruğu (§6.7) |
| `permission_server.write_mcp_config()` | `<veri kökü>/mcp/permission_mcp.json` — izin sunucusu tanıtımı (§6.6) |

**Kalan (Faz 14-F/sonrası):** yukarıdaki 7 modülün sabit `Path.home()` yazımları
**hâlâ** duruyor; bunlar da `data_root()` üzerinden türetilecek, mevcut veri
**taşınmadan** çalışmaya devam edecek (kullanıcı verisi silinmez, ROADMAP §4 madde 2).
Aşağıdaki §3.1 **hedefi** tarif eder; bugünkü fiili dağılım yukarıdaki tablodur.

### 3.1 Uygulama durumu — `~/.entropy` (kullanıcı verisi, ASLA silinmez)

`core/config.py:_resolve_state_dir()` sırası:

1. `ENTROPY_HOME` ortam değişkeni,
2. `APP_ROOT/.entropy` (varsa — kurulu sürümlerin verisi taşınmadan çalışsın diye),
3. `%LOCALAPPDATA%\EntropyAI` (Windows) / `~/.entropy`.

İçerik: `settings.json`, `chat_history.json`, `logs/`, `payloads/`, rapor indeksi,
`workspace/` (Claude Saf Kip'in nötr çalışma dizini), `external/` (depo dışına
taşınmış kullanıcı ve üçüncü taraf çıktıları).

### 3.2 Obsidian kasası — insan arayüzü ve soğuk depo

`core/config.py:_default_obsidian_vault()`; `ENTROPY_VAULT_PATH` ile geçersiz kılınır.

```
<kasa>/
├── Entropy/                 # Entropy AI'nin KENDİ verisi
│   ├── Agents/<ad>/AGENT.md         kaynak ajan tanımı (kullanıcı Obsidian'da düzenler)
│   ├── Agents/<ad>/inbox/           posta kutusu (<ts>-<id>.json)
│   ├── Tasks/<id>.md                görev kartları (YAML ön bilgi + gövde)
│   ├── Reports/                     ajan raporları
│   ├── Memory/                      MEMORY.md, wiki, playbook
│   ├── Inbox/
│   └── _archive/
└── Desk/                    # Agent Desk'in KENDİ verisi (Faz 10-B'de taşındı)
    ├── Offices/<ofis>/      BOARD.md, ARCHITECTURE.md, RULES.md, cards/, agents/, checkpoints/
    ├── Templates/           ekip şablonları (tohum ofis DEĞİL)
    └── _migrations.log
```

Desk kökü kasa **kökünde** durur (`Entropy/Desk` değil): doğuş talimatı alt ajanlara mutlak
yol verdiği için klasör adı istemin içine sızıyor ve "Desk Entropy'yi bilmez" sözleşmesini
deliyordu (`core/paths.py` modül başlığı). Geçiş sözleşmesi: **kopyala → doğrula → sil**,
idempotent, `dry_run=True` varsayılan.

### 3.3 Türetilmiş ajan tanımları (proje kökünde)

`agents/compile.py` her ajanı iki sağlayıcı biçimine derler
(`core/provider.py:AGENT_DEFINITION_LAYOUT`):

```python
AGENT_DEFINITION_LAYOUT = {
    "agy":    (".agents/agents", "agent.md"),
    "claude": (".claude/agents", None),
}
```

**Kaynak tek: kasa.** Derleme çıktısı türetilmiştir ve sürüm denetimine girmez.
Faz 11-A'dan beri derleme kökleri **proje kökü + ayarlardaki etkin proje + nötr Claude
çalışma dizini**; `APP_ROOT` listede **değildir**. Gerekçe `compile.py:compile_roots()`
docstring'inde: kaynaktan koşarken APP_ROOT deponun kendisi olduğu için Entropy'nin kendi
kadrosu (`analist`, `arastirmaci`, `degerlendirici`, `orkestrator`, `yazar`) deponun
`.claude/agents/` klasörüne düşüyor ve kullanıcının geliştirme alt ajanlarıyla karışıyordu.
Depodaki `.claude/agents/` artık **yalnızca kullanıcının 6 geliştirme ajanını** taşır.

---

## 4. Sağlayıcı köprüleri ve Entropy Saf Kip

İki köprü, tek soyutlama: `core/provider.py`. **Hiçbir API anahtarı kullanılmaz**; her ikisi de
kullanıcının abonelik oturumuyla koşar.

### 4.1 Claude köprüsü — `core/claude_bridge.py` (izolasyon sağlam)

| Bayrak | Etki |
|---|---|
| `--system-prompt-file` | varsayılan sistem istemini **değiştirir** (eklemez) → Entropy kendi kimliğiyle konuşur |
| `--setting-sources ""` | kullanıcı/proje/yerel ayarlar ve keşfedilen ajanlar yüklenmez |
| `--strict-mcp-config` + `--mcp-config` | yalnızca Entropy'nin MCP sunucuları |
| `--agents <json>` | Entropy kendi kadrosunu enjekte eder |
| `CLAUDE_CONFIG_DIR` | yeniden yazılır (profil sızıntısı yok) |
| `run_cwd()` | çalışma dizini **git deposunun dışında** (`~/.entropy/workspace`); CLI proje kimliğini literal cwd'den değil git kökünden çözdüğü için depo içi bir alt klasör izolasyon sağlamaz. İstisna: kart bir worktree'ye bağlıysa cwd o worktree'dir. |

**Bilinen boşluk:** `--setting-sources ""` ayar kaynaklarını kapatır ama **kök `CLAUDE.md`
otomatik keşfi ayrı bir mekanizmadır** ve `--add-dir` kökleri de CLAUDE.md dizini sayılır.
Depoda `CLAUDE.md` bulunmadığı için bugün sızıntı yoktur; bu yüzden dosya **bilerek
oluşturulmamıştır** ([ADR-0002](adr/ADR-0002-claude-saf-kip.md)).

### 4.2 agy köprüsü — `core/agy_bridge.py` (izolasyon yok — kayıtlı sınır)

Süreç doğrudan proje dizininde koşar (`cwd=project_dir`) ve ajan keşfi çalışma dizinine
dayanır. agy ikilisinde `--setting-sources` / `--strict-mcp-config` karşılığı **yoktur**;
bu, mevcut CLI ile kapatılabilir bir açık değil, belgelenmesi gereken bir sınırdır.
Efor ayrı bir bayrak değil **model varyantı** olarak geçirilir (v0.7.1).

### 4.3 Gizli alt süreç — `platform/proc.py` (Faz 13-A2, **sözleşme**)

`popen_kwargs(**extra)`: Windows'ta `CREATE_NO_WINDOW` + `STARTUPINFO(SW_HIDE)`,
başka platformda boş sözlük. Çağıranın `creationflags`i **ezilmez, VEYA'lanır**;
`DETACHED_PROCESS` varsa `CREATE_NO_WINDOW` eklenmez (ikisi birlikte geçersizdir).
`src/entropy/**` içindeki **her** `subprocess.{Popen,run,check_output,check_call,call}`
çağrısı bunu almak zorundadır; kapı AST taramasıyla ölçülür
(`tests/contracts/test_phase13_board_hygiene.py`). Muafiyet yalnızca kullanıcıya
**görünmesi istenen** açıcılardır (`explorer /select,`, `open -R`, `xdg-open`).
Gerekçe: kullanıcı bir görev koşarken ekranda konsol pencereleri parlıyordu;
ölçüm kaynağın kart koşusu değil bayraksız `taskkill`/`git` çağrıları olduğunu
gösterdi.

---

## 5. Beyin: hafıza katmanları

| Katman | Nerede | Ne tutar |
|---|---|---|
| Bilişsel bellek (12 katmanlı, çift depo) | `brain/supabase/cognitive_memory.py` — yerel SQLite + isteğe bağlı pgvector | düğümler, gömmeler, hibrit recall (semantik + sözcüksel) |
| Bilgi grafı | `brain/graph_store.py`, `graph_enrich.py`, `office_graph.py` | düğüm-kenar grafı, PPR benzeri genişletme, topluluklar |
| Wiki (derlenmiş bilgi) | `brain/wiki.py`, `lint.py` | raporlardan damıtılmış kalıcı maddeler |
| Playbook (yordamsal) | `brain/playbook.py` | "bu iş nasıl yapılır" — yetenek başına yordam |
| Kalıcı notlar | kasada `MEMORY.md` | kullanıcının elle düzenlediği gerçek |
| Ofis çalışma alanı | `brain/office_workspace.py` | `BOARD.md`, `ARCHITECTURE.md`, `RULES.md`, `checkpoints/<kart-id>.md` |
| Uzlaştırma | `brain/reconcile.py` | "bunu zaten biliyorum" denetimi (bugün yalnızca graf katmanına bağlı — Faz 11-B'nin ana işi) |
| Damıtma / rapor akışı | `brain/distiller.py`, `report_watcher.py`, `handoff.py` | rapor → wiki/playbook hattı |

**Bağlam kurucu** (`brain/context_builder.py`) sabit bir token bütçesini
(`DEFAULT_TOKEN_BUDGET = 4000`) öncelik sırasıyla doldurur: playbook → hibrit recall →
rapor alıntıları → kalıcı hafıza. Maliyet kasanın büyüklüğünden bağımsızdır.

**Onaylı kurallar** (`brain/promoted_rules.py`): ajan bir kural keşfettiğinde uygulama
kullanıcıya sorar; yalnızca "kalıcı yap" denince kural o ajanın sistem istemine her koşuda
enjekte edilir. Ajanlar hata ve günlük **yazmaz**.

### 5.1 Beyin v2 — yazma kapısı, kategoriler, turlar (Faz 11-B/C/D, **kod**)

**Yazma kapısı** `brain/gate.py` — hafızaya giden **tek** yol.
`MemoryGate.admit(category, content, importance=0.5, metadata=None, provenance="")
-> GateDecision`; `action ∈ {add, noop, gray, supersede, reject}`.
Bantlar: `cos ≥ 0.95` NOOP · `cos < 0.80` ADD · arası **gri bant** (düğüm yazılır
**ve** kuyruğa girer: `<db klasörü>/memory/gray_queue.jsonl`).
`record_memory` / `store_node` bu kapıdan geçer. **Kapı iki kez koşmaz:** kararı
çağıran aldıysa `record_memory(..., decision=<GateDecision>)` ya da
`CognitiveMemorySystem.store_decision(decision)` kullanılır (aynı metin iki kez gömülmez).
Bayraklar: `ENTROPY_MEMORY_GATE=0` kapıyı atlar, `ENTROPY_MEMORY_GATE_STRICT` katı kipi zorlar.

**Kategori kapalı kümesi** `brain/categories.py` →
`CANONICAL_CATEGORIES = ("working", "episodic", "semantic", "procedural")`.
Kimlik/kural (L4) **kategori değil bayraktır**: `is_identity`; kaynağı
`gate.IDENTITY_PROVENANCE = "identity:core"`. Eski 13+ ad `LEGACY_CATEGORY_MAP` ile
eşlenir, ham değer `metadata.legacy_category`'de kalır. Şema v2 sütunları:
`provenance, confidence, valid_from, valid_to, archived, novelty, is_identity`.
Kaynağı hiç kaydedilmemiş eski L2 düğümlere uydurma kaynak **yazılmaz**:
`gate.LEGACY_PROVENANCE = "legacy:pre-v2"`, `confidence = 0.40`.

**Rüya döngüsü** `brain/dream.py` —
`dream_and_consolidate(memory=None, send_prompt=None, vault_path=None, ...) -> DreamReport`.
Altı adım: yeniden gömme → gri bant turu → `cos ≥ 0.95` kopya birleştirme (LLM'siz) →
ölçülü unutma (`forget_stale`: önem < 0,35 **ve** `access_count ≤ 1` **ve** 30 gün →
`archived=1`, **silme yok**, `is_identity` muaf) → wiki yükseltme adayı → graf
konsolidasyonu. Zamanlanmış görev: `ensure_daily_dreaming_task(scheduler=None, hour=4)`
(idempotent, `bootstrap.ensure_memory_tasks()` çağırır).

**Gri bant birleştirme turu** `brain/gray_merge.py` —
`run_merge_round(memory=None, send_prompt=None, limit=8, ...) -> MergeResult`.
N aday **tek istemde**; yanıt `{"decisions":[{"id","action","content","reason"}]}`,
`action ∈ {merge, keep_both, supersede}`. `send_prompt=None` ise **kuru koşum**
(kuyruk boşaltılmaz, model çağrılmaz). Sağlayıcı seçimi çağıranındır.

**Wiki derleme hattı** `brain/wiki.py` —
`compile_skill(skill, bridge=None, budget_turns=8, ...) -> dict`. **Rapor başına bir tur**,
artımlı (`WIKI.state.json` işlenen rapor kümesini tutar), `bridge=None` ise model
çağrılmaz (yalnız playbook tabanlı sayfalar + indeks + lint).

**Öz-amplifikasyon kilidi** `agents/amplification.py` — üç kapı: (a) açık tespiti,
(b) yenilik kotası (`MIN_NOVELTY_RATIO = 0.30` altında aynı konudaki zamanlanmış görev
kapatılır, silinmez), (c) kaynak zorunluluğu. `config.amplification_lock=False` kilidi kapatır.

**Beyin kısa devresi VARSAYILAN KAPALI (Faz 13-A2, sözleşme).** Kullanıcı kuralı
bağlayıcıdır: *"araştır" dendiğinde araştırma CANLI koşar; beyin ajana **bağlamdır**,
araştırmanın yerine geçmez.* Kart CLI'ya hiç gitmeden ancak **dört koşul birden**
sağlanırsa kapanabilir (`amplification._shortcut_decision`):

1. **açık tercih** — `TaskCard.brain_only` alanı (`agents/tasks.py`, ön bilgiye
   gidip gelir) ya da metindeki işaret (`BRAIN_ONLY_MARKERS`: `--brain-only`,
   `[brain-only]`, "yalnız beyin") **ya da** `config.brain_shortcut_enabled`
   (`core/config.py:388`, **varsayılan `False`**);
2. CRAG isabeti; 3. güven ≥ `SHORTCUT_MIN_CONFIDENCE = 0.75`; 4. metin dolu **ve** kaynaklı.

Kısa devreyle kapanan kartın özeti **"CANLI ARAŞTIRMA YAPILMADI"** yazar.
**Kimlik düğümü yanıt sayılmaz ve bağlama hiç paketlenmez** (`brain/context_builder.py`
`is_answer_node` / `is_identity_node`); "0,49 güvenle beyinden yanıtlandı" hatasının
kaynağı tam olarak buydu — sunulan "yanıt" Entropy'nin kimlik düğümüydü.
Tazelik ipuçlu sorguda (`FRESHNESS_HINTS`: güncel/sıfırdan/yeni/bugün/web/internet/tara
+ tarih deseni) `brain_has_answer` **False**. `[BEYİN]` bölümü kalır ama tonu
"bağlamdır, yanıt değildir" olarak yazılıdır. Kapı: `tests/contracts/test_phase13_brain_shortcut.py`.

**Geri çağırma kapsamı:** `hybrid_recall(query, top_k, min_threshold, categories=None,
include_episodic=False, expand_graph=False)` — varsayılan **L2+L3**, `archived=1` indekse
girmez. CRAG sinyali: `AssembledContext.brain_confidence` + `brain_has_answer`
(`CRAG_MIN_SCORE = 0.45`). Genel sohbet beyin paketi `BUDGET_GENERAL_BRAIN = 1500`
yalnız `skill_name` boşken ödenir.

**Ölçüm paketi (kalıcı, tek kaynak `scripts/brain_metrics.py`):** K1 yineleme, K2 Hit@1/@5,
K3 gürültü, K7 kategori disiplini, K9 gri kuyruk, K10 fikstür sızıntısı, K11 kapı gecikmesi,
K12 kaynaksız L2. Sözleşme testleri `tests/contracts/test_phase11_brain_metrics.py` (12) ve
`test_phase11_memory_isolation.py` (11). Betik **salt okunur** (`mode=ro`).

Hafızanın algoritma kararı: [ADR-0003](adr/ADR-0003-hafiza-algoritmasi-mem0-degil.md).

---

## 6. Görev panosu, kartlar ve harness

### 6.1 Kart = dosya

`agents/tasks.py` — her kart `<kasa>/Entropy/Tasks/<id>.md`, YAML ön bilgi + gövde.
Neden dosya: kullanıcı Obsidian'da düzenleyebilsin ve iki taraf da aynı gerçeği görsün.

Ön bilgi alanları (`TaskCard`): `id, title, status, agent, provider, model, skill, created_at,
started_at, finished_at, output_paths, summary, office, project, parent, children, grade,
verdict, attempt, budget_tokens, intent, checkpoint, proof, worktree, branch, pr_url`
+ **Faz 11-C**: `effort, priority, input_paths, report_path, claimed_by, claim_expiry,
event_seq`; ayrıca `kind` (`"research"` ya da boş) ve **Faz 13-A2**: `brain_only`
(bool — kullanıcının açık tercihi, beyin kısa devresinin tek meşru kapısı;
`/task --brain-only` bayrağı başlığa sızmadan sökülür, `[PANO board_create]` onu JSON
alanı ya da metindeki işaretle okur).
Gövde: `## Hedef / ## Kabul ölçütleri / ## Notlar / ## Sonuç`.
Ofis kartları ayrı depoda: `<ofis>/cards/`.

### 6.1.1 Entropy Board — durum makinesi, olay günlüğü, tetikleyici (Faz 11-C, **kod**)

**Pano kökü** `<kasa>/Entropy/Board/` (`core/paths.py`: `BOARD_SUBDIR`,
`board_events_path()`, `board_taskboard_path()`, `board_claims_dir()`,
`board_agents_dir()`, `agent_session_path()`, `board_projection_path()`).
**Kartlar taşınmadı** — `Entropy/Tasks/` altında kalır.

**Durum makinesi** `agents/board_fsm.py` tek kaynaktır (kütüphane YOK):
`STATUSES` (8), `EVENTS` (12), `TRANSITIONS` (12 satır),
`transition(card, event, payload)`, `InvalidTransition`, `reset()`.

```
backlog → assigned → taken → running → review → done | failed | canceled
```

`review → done` yalnızca `actor="human"` + kanıt ile; `run.finished` kanıt `green=False`
ise `failed`. **Ajansız `backlog` kart koşmaz.**
**T13 (Faz 13-A2):** `review`/`failed` → `canceled` (`task.canceled`) — **gerekçe (`reason`)
zorunlu**; arşivlemenin tek meşru yolu budur. `done` terminal kalır.
`board_events.board_drift` dosyası olmayan `canceled` kartı **ayrışma saymaz**
(arşivlenen kart panodan kalkmış demektir). Olay `seq`i dosyanın **son satırından**
doğrulanır (bayat önbellek iki kez `seq` yazıyordu) ve `board.drift` olayı
**kendi korelasyonunu** taşır (`drift:<hash16>`).

**Yeniden oynatma güvenliği (Faz 14, [ADR-0010](adr/ADR-0010-gecici-ajan-mimarisi-langgraph-alinmadi.md)).**
Bir adım ya **yeniden oynatılabilir** olmalı ya da açıkça "yan etkili, oynatma" diye
işaretlenmelidir: CLI çağrısı kota harcar. Aynı olayın iki kez uygulanması
`events.jsonl`'de ikinci satır üretmez (`idempotency_key`); `review → done` yalnız
`actor="human"` + kanıtla geçer. Duraklama noktası (onay bekleme) devam ederken
**tekrar çalışır** — kuyruk bu yüzden idempotent olmak zorundadır. Paralel genişlik
kartın token bütçesiyle sınırlanır; ledger `parent_run_id` + `run_type ∈ {llm, chain, tool}`
alanlarını taşır (yerelde kalır, dış servis yok).

**Olay günlüğü** `agents/board_events.py` — `events.jsonl`, **yalnızca ekleme**; satır şeması
`{schema_version, seq, ts, correlation_id, task_id, attempt_id, actor, action,
idempotency_key, payload}`. `projection_hash` = kanonik JSON + SHA-256;
`TASKBOARD.md` bu günlükten **türetilir** (gerçek kaynak değildir).

**Tetikleyici** `agents/dispatcher.py` — `BoardDispatcherCore(board, registry, vault_path,
runner, claim_timeout_s, max_parallel)` Qt'siz çekirdek (`tick() -> [kart_id]`,
`pick(agent)`, `reconcile() -> [kart_id]`) + `BoardDispatcher` QTimer sarmalı
(`board_dispatcher()` tekil). Sahiplenme atomiktir: `claims/<id>.lock`, `O_CREAT|O_EXCL`.
Açılış kablolaması `agents/bootstrap.start_board_dispatch(app)` → **önce `reconcile()`,
sonra `start()`**; `app.aboutToQuit` kancasına `dispatcher.stop`. Hata YÜKSELMEZ,
`DispatchStartResult.summary()` metnine düşer.

**Ajan oturum deposu** `core/identity.AgentSessionStore` →
`Entropy/Board/agents/<ad>/session.json`
`{provider: {session_id|conversation_id, signature, model, effort, cwd, updated_at}}`.
**Canlı durum ayrı dosyada (Faz 13-A2, sözleşme):** `Entropy/Board/agents/<ad>/state.json`
(`store.state_path`). Ayrılma nedeni: `session.json` **sağlayıcı anahtarlıdır** ve
`rotate`/`run_kwargs` onu baştan yazar; devir sırasında canlı durum siliniyordu.
Arayüz rozetinin **TEK** kaynağı `store.status(name)`:
`{state: "idle"|"running", since, card_id, card_title, last_run_at, provider (ajanın
GÜNCEL sağlayıcısı), session (o sağlayıcının kaydı), stale_sessions[]}`;
yazma boğazı tek: `TaskBoard.apply_event` → `_sync_agent_live_state`
(`taken`/`running` → `mark_running`, diğer her hedef → `mark_idle`; **ofis kartları
hariç**). Çökme sonrası `dispatcher.reconcile` → `_clear_orphan_live_states`.
Eski hata: rozet "en taze sağlayıcı kaydı"nı seçtiği için ajan agy'ye geçtikten
sonra bile saatler önceki claude oturumunu gösteriyordu.

Claude kimliği `uuid5("entropy-agent:<ad>")`; `run_kwargs()` yeni oturumda
`{"session_id"}`, sürdürmede `{"conversation_id"}` döndürür. İmza
`sha1(kimlik istemi|model|efor)` — kart istemine **bağlı değildir**, yoksa `--resume`
hiç kullanılmaz. İmza düşerse **taze uuid4** üretilir (aynı `session_id`'yi yeniden
vermek CLI'da `Session ID is already in use` hatasıydı).

**Pano araçları** `agents/board_tools.py` — ajanda 4 (`board_next`, `board_checkpoint`,
`board_finish`, `board_ask`), Entropy'de +`board_create`. Taşıma biçimi
`[PANO <araç>] {json} [/PANO]`; **kanıtsız `board_finish` reddedilir** (kart `review`de kalır).

**Pano sinyalleri:** `board_state_changed(dict)` = `{card_id, status, event, agent, office,
title}`; `task_report_ready(dict)` = `{card_id, title, agent, status, ok, summary,
report_path, output_paths}`.
**Pano ayarları:** `board_auto_dispatch` (True), `board_dispatch_interval_s` (3),
`board_claim_timeout_s` (3600), `entropy_max_parallel` (2), `amplification_lock` (True).
**Yerel slash komutları:** `/board`, `/board pick <kart> <ajan>`, `/board auto on|off`,
`/lock on|off`, `/model [<ad>]`, `/agent effort|model <ad> <değer>`,
`/memory merge`, `/memory dream`, `/wiki compile <yetenek> [--turns N]`.

### 6.2 Ofis harness'ı — `agents/harness.py`

Zincir: **planla → paralel koş → notla → kapat**. Dosya tabanlıdır, kesintiden devam eder.

- `ensure_workspace()` ofis kökünde BOARD/ARCHITECTURE/RULES üretir,
- `spawn_instruction()` (`SPAWN_INSTRUCTION_MAX_CHARS = 1200`) her alt ajana ilk iş olarak
  "panoyu ve mimariyi oku" talimatını mutlak yolla verir,
- `render_board()` kartlardan `BOARD.md` projeksiyonunu üretir,
- **kanıtla kapat:** bir işçi testleri koşup yeşil sonucu raporuna iliştirmeden kartı `done`
  yapamaz; kanıt `proof_recorded` sinyaliyle görünür,
- **denetim noktası disiplini:** her modülden sonra kısa durum özeti diske yazılır
  (`checkpoint_written`); çökme sonrası uzun sohbet günlüğünden değil bu özetten devam edilir,
- kart başına git worktree (`agents/worktrees.py`, komşu `.entropy-worktrees/`), PR akışı
  (`agents/pr_flow.py`: önce yerel dal + diff, onaydan sonra push).

**Orkestratör kod yazmaz.** Araştırır, planlar, kendi alt ajanlarını oluşturur/düzenler,
raporlar; araç politikası salt okunurdur.

### 6.3 Rapor başlığı ve "sohbet turu ≠ rapor" (Faz 13-A, **sözleşme**)

**Başlığın tek kaynağı** `core/report_title.py` (saf Python; Qt/kasa/ajan bağımlılığı yok):

```
derive_report_title(body, fallback) :  gövdedeki ilk `# H1` → ilk anlamlı cümle → fallback
```

**Kullanıcının istem satırı hiçbir zaman başlık kaynağı değildir.** Eski davranış
başlığı istemin ilk 40 karakterinden üretiyordu; kasada "Tamamdır, şimdi senden…"
gibi başlıklar oluşmuştu. `TITLE_MAX_CHARS = 80`, `safe_filename_title()` Windows'ta
yasak karakterleri temizler, makine etiketleri (`[KONTROL NOKTASI]`, `[KANIT]`) ve
kod çitleri ayıklanır. Okuma tarafı (`ui/widgets/report_center.derive_report_title`)
**aynı sırayı** izler.

**Serbest sohbet turu RAPOR DEĞİLDİR.** Kelime sayısına dayalı sezgi kaldırıldı;
sohbet çıktısı `save_session_note()` ile `<kasa>/Entropy/Sessions/<YYYY-MM-DD>/<HHMM>-<konu>.md`
altına **`type: session`** künyesiyle yazılır (`report_title.session_note_path`).
Rapor üreten **tek** yollar: pano kartı çıktısı, `[OTONOM PLANLI GÖREV]` ve açık `/learn`
(`core/claude_bridge.py:1846`, `core/agy_bridge.py:2401`). `Sessions/` sayfaları yordam
değil **olay**tır: `brain/playbook.py` onları bilerek dışarıda bırakır ve
`brain/handoff.py` oraya düşmüş bir dosyayı aktarım sanmaz. Eski dosyalar **taşınmaz**;
görüntü katmanı onları yeniden başlıklar.

### 6.4 Geçici ajan döngüsü — `agents/ephemeral.py` (Faz 14-C, **kod**, [ADR-0010](adr/ADR-0010-gecici-ajan-mimarisi-langgraph-alinmadi.md))

Kullanıcının bağlayıcı tanımı: bir yetenek koşulacaksa Entropy `SKILL.md`'yi alır,
o iş için bir `agent.md` üretir, ajana beyinden ilgili bağlamı verir, **ayrı bir CLI
oturumu** açar, akışı anlık gösterir, raporu alır ve **ajan kendini siler**.
Kalıcı adlı kadro istenmiyor; kadro **gizlendi, silinmedi** (Desk ve pano ona bağlı).

Tek modül, tek yaşam döngüsü (Qt'siz): `prepare → spawn → stream → report → memory → cleanup`.

```
kullanıcı istemi / [AJAN run] bloğu / ajansız pano kartı
  └─ yetenek çözümü (skills/manager)
       └─ prepare(skill, prompt, brain_context, engine) -> EphemeralSpec
            └─ EphemeralRun(...)  →  run.finished (threading.Event)
                 ├─ akış    → bus.agent_stream → sohbette "Ajan: … yapıyor"
                 ├─ izin    → core/pending.PendingQueue → "onaylıyorum"
                 ├─ rapor   → kasada Ajan_<H1>_<zaman>.md (başlık H1'den)
                 ├─ hafıza  → ALT AJAN'ın [HAFIZA] bloğu → MemoryGate.admit
                 └─ temizlik→ workdir + sistem istemi dosyası silinir
```

**Sözleşme (ölçülmüş; `tests/contracts/test_phase14c_ephemeral_agent.py`, 13 test).**

1. **Künye.** `EphemeralSpec(slug, skill, goal, agent_md, provider, model, effort,
   tools, max_steps, run_id, session_id, workdir)`. `prepare()` hiçbir süreç açmaz ve
   claude yolunda **dosya yazmaz**.
2. **`agent.md` şablonu** (`build_agent_md`, saf Python): `# <slug>` → `## Görev`
   (+ `### Yetenek yordamı: <ad>`) → `## Bağlam (beyinden)` (bütçe
   `CONTEXT_TOKEN_BUDGET = 4000`, `brain/context_builder`) → `## Kabul ölçütleri`
   (her bulgu kaynaklı; beyin bağlamı araştırmanın yerine geçmez; adım tavanı) →
   `## Rapor şablonu` (**ilk satır `# H1`** — §6.3) → `## Hafıza`
   (`[HAFIZA]{json}[/HAFIZA]`, ≤ 8 madde, `provenance` zorunlu) → `## Yasaklar`
   (kod değişikliği yok, proje kökü salt okunur, kalıcı ajan/oturum kaydı açma).
3. **Taşıma.** claude yolunda tanım **argv'de**: `--agents '{"<slug>": {…}}'` +
   kullanıcı mesajı `Use the <slug> subagent …`; agy yolunda geçici
   `<workdir>/.agents/agents/<slug>/agent.md` yazılır ve koşu sonunda dizin silinir.
   Her koşu yeni `uuid4` → `--session-id`, yanında `--no-session-persistence`
   (`--resume` ile birlikte **verilmez**). `AgentSessionStore`'a hiçbir şey yazılmaz.
4. **Köprü kwarg'ı.** `send_background_task_async(..., ephemeral={"agents_json",
   "system_prompt", "extra_dirs", "no_session_persistence", "run_id"})`. Dolu
   geldiğinde kadro JSON'unun yerine koşunun tek ajanı gider, sistem istemi
   `agent.md` gövdesidir, `--add-dir` yalnız izole `workdir` + kasa rapor klasörüdür
   (**proje kökü argv'ye girmez**). 14-B onay yüzeyi aynen geçerlidir.
   `bridge.background_step_counts[task_id]` araç adımı sayısını çağırana açar.
5. **Adım tavanı yeteneğe göre.** `SKILL.md` ön bilgisindeki `max_steps` (1–500),
   yoksa `DEFAULT_MAX_STEPS = 60`; kart tavanı `MAX_STEPS_PER_CARD = 20` geçici koşuda
   kullanılmaz. Tavana çarpan kart `failed` **değil** `review` ile kapanır ve
   `run.finished` `ok=True` taşır (FSM T6; §6.1.1'e yeni geçiş eklenmedi).
6. **Tek bildirim.** Köprünün kendi rapor yolu kapalı (`save_report=False`); raporu
   Entropy yazar, `[HAFIZA]` bloğu `report_title.strip_machine_blocks` ile görüntüden
   silinir ve **tek** `bus.task_notification` yayılır
   (`"Ajan <slug> bitti: <H1>; N araç adımı; rapor: <yol>"`). `report_created`
   bilerek yayılmaz (çift kart yok).
7. **Hafızayı alt ajan yazar.** `brain/agent_memory_writer.ingest_agent_report(...,
   success=…, has_proof=…)`; Entropy kapı dışında hiçbir şey yazmaz (§6.4-D).
8. **Kendini silme.**

| Silinir | Kalır |
|---|---|
| geçici `workdir` (agy'de `agent.md` dâhil) | ledger satırı (`run_type="ephemeral"`, `parent_run_id`) |
| sistem istemi dosyası (köprü siler) | rapor dosyası |
| oturum kaydı (hiç oluşmaz) | `Board/events.jsonl` satırları · kapıdan geçen hafıza düğümü |

9. **Tetikleme yüzeyleri.** (a) `/skill run <yetenek> :: <istem>` — yerel komut, modele
   gitmez (komut yüzeyi 31 → **32**). (b) Entropy'nin kendi kararı:
   `[AJAN run] {"skill": …, "goal": …} [/AJAN]`; `response_hooks` tüketir, **tur başına
   1 ajan**, blok görüntüden silinir. (c) `agent` alanı boş pano kartı →
   `BoardDispatcherCore.tick_ephemeral()` (kadrodan kimse seçilmez; kart
   `assigned → taken → running` üzerinden yürür).
10. **İstem bütçesi.** `brain/system_prompt.BUDGET_BOARD_TOOLS` 600 → **1000**: 600'de
    `[AJAN run]` eklenince `board_create` bloğu (ve içindeki `[DESK …]` araçları)
    tamamen düşüyordu. Ölçüm: `board_tools_section(1000)` = 933 karakter.

**Canlı kanıt (S3, 2026-09-11, `claude` 2.1.268):** iki koşum; run2'de 6 `agent_stream`
satırı, 1 onaylanan `tool_permission`, **tek** bildirim, H1 doğru; run1'de 3.611 B rapor,
11 kaynak URL, 5 `[HAFIZA]` maddesi kapıdan geçti; her iki koşumda `workdir` silindi ve
ledger satırı `ephemeral` kaldı. Kanıt: `scratch/phase14/s3_live.json`,
`docs/reports/_evidence_2026-09-11_s3_live.json`, `scratch/phase14/s3_agent.md`.
**Açık:** rapor kasada `Entropy/Skills/<yetenek>/Reports/` altına düşüyor
(yeteneksiz koşuda `Entropy/Reports/`) — yol kararı Faz 15'e; agy kolu canlı koşulmadı.

### 6.4-D Alt ajan hafıza yazarı — `brain/agent_memory_writer.py` (Faz 14-D, **kod**)

Rapor gövdesinin sonundaki `[HAFIZA] {"items": […]} [/HAFIZA]` bloğu ayrıştırılır,
doğrulanır (kategori kapalı küme `working|episodic|semantic|procedural`, `provenance`
zorunlu, en çok 8 madde, madde ≤ 600 karakter) ve **yalnız** `MemoryGate.admit` →
`record_memory(decision=…)` yolundan yazılır — kapı bir kez koşar. `success=False` ya da
kanıtsız koşuda blok **hiç okunmaz**. Blok `strip_machine_blocks` ile görüntüden silinir.

**Kapının hata/günlük reddi bandı** (`brain/gate.py`, kategori kontrolünden **önce**):
`success=False` beyanı koşulsuz reddedilir; katı kipte ayrıca yığın izi/hata kalıpları
(`Traceback`, `Error:`, `Exception`, `object has no attribute`, `[Otonom Görev Hata]`,
`yürütülemedi`, `[ADIM SINIRI]`, `Timeout`), tek satırlık günlük çıktısı,
`provenance`/metadata'da pytest ya da geçici dizin izi (`pytest-of-`, `pytest-<n>`,
geçici klasör yolları) ve 40 karakterin altındaki içerik reddedilir →
`action=reject`, `reject_code=REJECT_ERRORLOG`, sayaç `gate.stats[REJECT_ERRORLOG]`.

**Artık arşivi silme değildir** (`brain/artifact_archive.py`): `archived=1` +
`metadata.archived_reason`, graf kenarlarına dokunulmaz, yazmadan önce tam DB yedeği
`~/.entropy/backups/p14d-<zaman>/`, varsayılan **kuru koşum**, her koşum kasadaki
`Entropy/Memory/archive_log.md` dosyasına bir satır yazar. Ölçüm (740 düğüm, silme yok):
etkin 716 → 700, arşivlenen 16; K2 Hit@1 8/10 ve Hit@5 10/10 **düşmedi**, K3 %0,0,
hata/günlük bandında kalan etkin düğüm 5 → **0**, pytest izli 12 → **0**.

### 6.5 Sohbet sürekliliği sözleşmesi (Faz 14-A, **kod**)

Ölçülen hata (Faz 14 öncesi): sistem istemi sorguya bağlı bilişsel bağlam taşıdığı için
`prompt_signature` hemen her turda değişiyor, `_forget_stale_session` oturumu düşürüyordu
ve 3. turdan itibaren her tur **geçmişsiz yeni bir oturum** oluyordu
(`NO-RESUME / RESUME / NO-RESUME / NO-RESUME`). "Onaylıyorum" denince neyin onaylandığı
bu yüzden kayboluyordu.

1. **Sistem istemi turdan tura sabittir.** Saf kipte sohbetin sistem istemi
   `build_system_prompt("chat", query="")` çıktısıdır: kimlik + onaylı kurallar + araç
   sözleşmesi + manifest. `[BİLİŞSEL BAĞLAM]`, `[ÖNCEKİ SOHBET ÖZETİ]`, yetenek afişi ve
   ek dosya yönergesi sistem isteminde **olamaz**. Ölçü: dört ardışık turda dosya karması aynı.
2. **Bağlam kullanıcı mesajında.** `build_turn_context_block` çıktısı
   `[BU TURUN BAĞLAMI] … [/BU TURUN BAĞLAMI]` başlığıyla kullanıcı mesajının **başına**
   konur; mesaj blokla birlikte `last_user_message` alanına yazılır (uzun mesaj stdin'e
   taştığı için argv'den okunamaz).
3. **İmza kapsamı.** `_forget_stale_session(system_prompt, model, effort, isolated)` =
   `sha1(sabit istem | sağlayıcı:model:izolasyon | efor)`. Oturum yalnız model/efor
   değişimi, saf kip anahtarı ya da onaylı kural eklenmesiyle düşer.
4. **Tek oturum kimliği.** İlk tur `--session-id <uuid>` ile kimliği önceden atar,
   sonraki turlar `--resume <aynı kimlik>`. Akıştan kimlik gelmez ve süreç 0 ile biterse
   önceden atanan kimlik sürdürülür; hata varsa sürdürülmez.
5. **Yeni oturuma geçmiş taşınır.** Oturum yokken kullanıcı bloğuna
   `[ÖNCEKİ SOHBET ÖZETİ]` eklenir: **son 8 tur, mesaj başına 1.200 karakter**
   (eski `6 × 100` kırpması kaldırıldı).
6. **Sohbette proje kökü salt okunur.** `chat_tools()` saf kipte yalnız
   `Read, Glob, Grep, WebFetch, WebSearch` verir; yazma niyeti sezgisi artık
   `Edit/Write/Bash` yetkisi **vermez**. Yol belirteçli izin bayrağı bu sürümde
   doğrulanamadı (`CLAUDE_SUPPORTS_TOOL_PATH_SCOPES = False`); kart yolu (`tools_for`)
   değişmedi.
7. **Defter.** Sohbet satırı modeli `current_model`den alır ve `effort` sütunu eklendi
   (geriye uyumlu `ALTER TABLE`); agy köprüsünde de aynı.
8. **Akış kapanışı.** `agy_bridge.close_stream(stream)` tek yardımcı: `close` metodu
   olmayan ya da patlayan akışta tur ölmez.

**Sözleşme testleri:** `tests/contracts/test_phase14a_chat_continuity.py` (8 test),
`tests/test_agy_bridge.py::test_stream_close_survives_non_file_stdout`.
**Canlı kanıt (S1, 2026-09-11):** iki ardışık tur, `tur1_resume=false`,
`tur2_resume=<aynı session_id>`; ikinci tur birinci turun konusunu doğru andı
(`docs/reports/_evidence_2026-09-11_s1_live.json`).

### 6.6 Onay yüzeyi — `--permission-prompt-tool` + stdio MCP (Faz 14-B, **kod**)

[ADR-0002](adr/ADR-0002-claude-saf-kip.md) saf kipe geçerken CLI'ın varsayılan izin
diyaloğunu düşürmüştü; yerine hiçbir şey konmamıştı (`permission_denial` / `can_use_tool`
için kaynakta 0 isabet) ve reddedilen araç modele hata metni olarak döndüğü için model
"onay penceresinde bekliyor" diye **uyduruyordu**.

**Sunucu** — `core/permission_server.py`, bağımlılıksız stdio MCP (NDJSON JSON-RPC 2.0;
`initialize` / `tools/list` / `tools/call` / `ping`), sunucu adı `entropy`, tek araç
`mcp__entropy__approve`. Giriş noktası `python -m entropy.core.permission_mcp_main`;
paketlenmiş sürümde **aynı ikili** `EntropyAI.exe --entropy-mcp-permission` ile Qt
kurulmadan sapar. Yapılandırma `core/paths.data_root()/mcp/permission_mcp.json`
(`permission_server.write_mcp_config`). **Sunucuyu Entropy başlatmaz: stdio sunucusunu
CLI doğurur.**

**Risk bandı:** `Bash/BashOutput/KillShell/NotebookEdit` → **high**,
`Write/Edit/MultiEdit` → **medium**, `Read/Glob/Grep/WebSearch/WebFetch/TodoWrite` → low,
**bilinmeyen araç → medium** (sessizce "low" sayılmaz). Karar tavanı **15 dk**
(`DEFAULT_TIMEOUT_S`, `ENTROPY_PERMISSION_TIMEOUT_S` ile ezilir); dolunca `deny` +
kayıt `expired`. Aynı `tool_use_id` ikinci kez sorulmaz (önbellek).

**Şema — ölçüldü, varsayım değil** (`scratch/phase14/permission_spike/README.md`,
`claude` 2.1.268 ile 5 canlı koşum):

| Yön | Ölçülen |
|---|---|
| CLI → araç (`arguments`) | yalnız `tool_name`, `input`, `tool_use_id` |
| araç → CLI (sonuç) | **yalnız** `content` (tek `text` parçası) + `isError: false`; kararın kendisi o metnin içinde **düz JSON**: `{"behavior":"allow","updatedInput":…}` / `{"behavior":"deny","message":…}` |

`structuredContent` eklemek **yasaktır** (`permission_server._tool_result`): canlı S2'nin
ilk koşumunda eklenmişti ve CLI kararı hiç okumadan
*"Permission prompt tool returned an invalid result…"* hatası verdi — komut koşmadı, ret
`permission_denials`a bile düşmedi. İzin **isteği** stream-json'da hiç görünmez; **ret**
`result.permission_denials` altında görünür ve koşumu başarısız yapmaz. Yanıt süresine üst
sınır ölçülmedi (45 sn sorunsuz); belgelerdeki 30 sn **bağlantı** zaman aşımıdır.

> **Kapanmayan açık (belgelenmiş sınır):** CLI'ın yerleşik **"güvenli komut" sınıfı izin
> kancasından ÖNCE koşar** — `echo`, `ls` gibi salt okunur komutlar hiç sorulmadan
> çalışır; `--restricted` ve `--permission-mode manual` bunu değiştirmedi
> (`--permission-mode manual` sessizce yok sayıldı, `system/init` her koşumda
> `permissionMode: "default"` bildirdi). Yani **"her araç sorulur" garantisi verilemez**;
> tam denetim istenirse tek katı yol `--permission-prompts none` + açık beyaz listedir.

**Köprü argv'si.** `config.approvals_enabled` (varsayılan **True**) açıkken sohbet turu ve
kart koşusu `--permission-mode default` + `--permission-prompt-tool mcp__entropy__approve`
+ `--strict-mcp-config --mcp-config <veri kökü>/mcp/permission_mcp.json` alır ve
`--dangerously-skip-permissions` **hiç eklenmez**; kapalıyken tam tersi (Faz 13 davranışı).
İki bayrak `build_command` içinde birbirini dışlar.

**CLI keşif sırası** (`find_claude_executable()`): `config.claude_path` → PATH → npm global
shim (`%APPDATA%/npm/claude.cmd`) → `~/.local/bin` → `%LOCALAPPDATA%/Programs/claude` →
editör eklentileri (`.vscode`, `.vscode-insiders`, ticari referans ürünün eklenti kökü;
`resources/native-binary/claude(.exe)`, **en yüksek sürüm**). Hiçbiri yoksa sessiz çıkış
127 yerine tek satırlık teşhis yayılır (`CLAUDE_CLI_MISSING_MESSAGE`). Sıra testle sabit.
npm'in yarım kurulumundaki gizli `node_modules/.../.claude-code-*` klasörü **bilerek
taranmaz**.

**"onaylıyorum" CLI'ya gitmez:** `response_hooks.resolve_approval_message` tek bekleyen işi
çözer ("onaylandı: …" / "reddedildi: …"), birden fazlaysa kimlikle sorar
("onayla <kimlik>"), hiç yoksa "Bekleyen onay yok." der; köprü bu turu kısa devre yapar
(kota 0, model uydurması yok).

**Kural:** sohbet turunda **proje kökü salt okunurdur** (§6.5 madde 6); kod değişikliği
yalnızca onaylı kart (worktree) yolundan yapılır.

**Canlı kanıt (S2, 2026-09-11; argv ürün yolundan `approval_argv()` + `build_command()`):**

| Ölçüt | approve | reject |
|---|---|---|
| Kuyruğa düşen `tool_permission` | 2 (`Bash`, risk **high**) | 1 (`Bash`, high) |
| `system.init.permissionMode` | `default` | `default` |
| `system.init.mcp_servers` | **yalnız** `entropy` (connected) | **yalnız** `entropy` |
| Komut koştu mu | evet, hedef dosya **silindi** | hayır, dosya **duruyor** |
| `result.permission_denials` | `[]` | **1 kayıt** (tool_input dâhil) |
| çıkış / süre | 0 / 31,0 sn | 0 / 17,2 sn |

İzolasyon kanıtı: `--strict-mcp-config` + kendi `--mcp-config` + `--setting-sources ""`
ile kullanıcının hiçbir MCP sunucusu yüklenmedi
(`docs/reports/_evidence_2026-09-11_s2_live.json`).

### 6.7 Bekleyen işler — tek kuyruk, `core/pending.py` (Faz 14-B, **kod**)

Faz 14 öncesinde iki ayrı kuyruk vardı (Desk onayları `agents/desk_admin.py` + sohbet
kartları). Hepsi tek modelde birleşti; `desk_admin` dosyaları **taşınmadı**, sarmalandı.

| Tür (`kind`) | Kaynak | "Onaylıyorum" ne yapar |
|---|---|---|
| `tool_permission` | CLI izin aracı (§6.6) | araca `allow` döner, oturum kesintisiz sürer |
| `desk_change` | `[DESK …]` blokları | `apply_pending` / `reject_pending`'e yönlenir |
| `rule_candidate` | ajanın keşfettiği kural | kural o ajanın sistem istemine kalıcı enjekte edilir |
| `skill_candidate` | beceri sentezleyici | beceri kurulur |

```python
PendingQueue(root=None)                       # varsayılan: paths.pending_root()
  .add(kind, title, detail, risk="low", source="", payload=None) -> id
  .list(kind=None, status="pending")          # status=None -> tümü
  .get(item_id) / .path_for(item_id)
  .resolve(item_id, "approve"|"reject", note="") -> dict
  .wait(item_id, timeout_s) -> dict | None    # izin aracı bunu bekler
  .expire(item_id, note="")
queue(root=None) -> PendingQueue              # modül düzeyi kısayol
```

Depolama: `paths.pending_root()` → `<veri kökü>/pending/<id>.json`; durumlar
`pending|approved|rejected|expired`, riskler `low|medium|high`. **Çözülmüş kayıt
silinmez** (`status` + `decision` + `decided_at` + `note`) — "kayıt bırakmayan silme
yoktur" (ROADMAP §4 madde 8).

**Ayrı süreç habercisi.** İzin isteğini yazan taraf CLI'ın çocuğu olan MCP sunucusudur;
onun `add()` çağrısı uygulamanın veriyoluna erişemez. Bu yüzden `PendingWatcher`
(0,5 sn yoklama, `start_watcher()`) kuyruğu izler ve olayı uygulamada yayar; köprü
`approval_argv()` çağrısında yoklayıcıyı açar. `ENTROPY_PENDING_NO_BUS` ile veriyolu
yayını kapatılabilir (alt süreçte Qt kurulmasın diye).

**Sinyaller:** `bus.pending_changed(dict)` —
`{"action": "added"|"resolved"|"expired", "item": <künye>}`;
`bus.tool_permission_event(dict)` — `{"phase": "requested"|"decided"|"denied", "tool",
"input_summary", "tool_use_id", "pending_id", "message"}`. Eski
`tool_approval_requested/responded` **duruyor** ve yanlarında yayılır (§7 sözleşmesi
bozulmadı; yalnız ekleme yapıldı).

Tek yön sözleşmesi korunur: Desk bu kuyruğa **kart itemez**, yalnız kendi değişiklik
istekleri onay için buraya düşer ([ADR-0001](adr/ADR-0001-desk-ayrimi.md)).

---

## 7. Olay veriyolu sözleşmesi — `core/event_bus.py`

Arayüz ile çekirdek arasındaki tek bağ. **Sinyal adı ve imzası bir sözleşmedir**; değişirse
bu tablo aynı commit'te güncellenir.

| Alan | Sinyaller |
|---|---|
| Kip / çekirdek | `mode_requested(str)`, `mode_changed(str)`, `core_pulse_triggered(float)`, `core_state_changed(str)` |
| Akış | `model_detected(str)`, `token_chunk_received(str)`, `terminal_output_received(str)`, `token_usage_updated(int)`, `token_usage_detail(dict)`, `agent_turn_started(str)`, `agent_turn_completed(str)`, `agent_stream(dict)` |
| Proje / bağlam | `project_changed(str)`, `context_pressure(float)`, `chat_history_updated()`, `chat_history_cleared()` |
| Araç onayı | `tool_approval_requested(str, str, str)`, `tool_approval_responded(str, bool)` |
| Bekleyen işler (Faz 14-B) | `pending_changed(dict)`, `tool_permission_event(dict)` — §6.7; eski araç onayı sinyalleri **durur**, yanlarında yayılır |
| Görevler | `task_triggered(str, str)`, `task_completed(str, bool)`, `task_notification(str, str, str)`, `task_followup_completed(dict)`, `task_cards_updated(str)` |
| Bilgi | `report_created(str)`, `node_selected(str)`, `knowledge_graph_updated()`, `cognitive_memory_updated()`, `skills_updated()`, `skill_detected(str, float)`, `playbook_updated(str)`, `reports_updated(str)`, `distill_progress(str, int, int)`, `report_inbox_unread(int)` |
| Ajanlar / ofisler | `agents_updated(str)`, `offices_updated(str)`, `office_progress(str, str, str)`, `mailbox_updated(str, str)`, `rules_updated(str, int)`, `checkpoint_written(dict)`, `proof_recorded(dict)` |
| Hata / sağlayıcı | `memory_error(dict)`, `provider_status_updated(str, dict)`, `mcp_servers_updated()` |
| İş parçacığı | `call_on_main(object)` — GUI dokunuşları daima ana iş parçacığında |

---

## 8. Arayüz

Üç kip: **Zen** (tam pano), **Chat** (sohbet öncelikli), **Floating** (küçük yüzen pencere) —
`ui/modes/`. **44 widget** `ui/widgets/` altında.

**Zen düzeni (Faz 14-E, sözleşme).** Kullanıcının tarifi: yedi bölüm üstte küçük düğme,
sohbet sağda tam yükseklikte panel.

- **Üst bölüm şeridi** `ui/widgets/nav_strip.py` (`objectName="navStrip"`): yedi düğme —
  Raporlar & Notlar, Yetenekler, Görevler, MCP Sunucuları, Ajanlar, Bugün, Bildirimler.
  Her düğmede `pixmap(16)` ile çizilebilir ikon **ve** `accessibleName`; aynı anda
  **tek** seçili düğme.
- **Gövde** tek yatay ayırıcı: solda içerik alanı, sağda **tam yükseklikte** panel —
  `Sohbet` / `Hafıza` sekmeleri; çekirdek görselleştirici sohbetin üstünde durur
  (korunan kimlik öğesi, yukarıdaki madde).
- **Tek durum satırı**; ajan akışı tek satır olarak yazılır ("Ajan: … yapıyor"),
  onay kartı `PendingQueue` sözleşmesine bağlıdır (Desk istekleri `desk_change` olarak
  aynı listede), olay başına **tek** bildirim kartı.
- **Kalıcı ajan kadrosu gizlendi**, bir "ajan koşuları" paneline alındı — silinmedi
  (Desk ve pano ona bağlı, §6.4).
- Kapılar: `skills/ui-design/SKILL.md` **G14-1** (`nav_strip_violations = 0`) ve
  **G14-1b** (`nav_strip_buttons ≥ 7`, `FINAL_MIN_GATES`); ölçüm `scripts/ui_audit.py`.

**Korunan kimlik öğeleri (Faz 13, sadeleştirme turları bunları kaldıramaz).**
Aşağıdaki üç öğe dekor değil **kimlik + durum göstergesidir**; yoğunluk sayacını
düşürmek için silinemez, ancak yeniden tasarlanabilir:
(1) **Çekirdek görselleştirici** (`ui/widgets/core_visualizer.py`, Zen sohbetinin
rezerve üst şeridinde, ≥ 48 px, ayardan gizlenebilir — sözleşme testi
`tests/ui/test_phase13_ux.py`); (2) **marka kümesi** (`brandCluster`);
(3) **model kapsülü** (`modelCapsule` — hangi modelin konuştuğu her an görünür).
Bir tur bu öğelerden birini küçültürse gerekçesini faz raporuna yazar.

**Çekirdek durumunun anlamı (Faz 13-A2, sözleşme).** Çekirdek — `brandCluster`
durum noktası ve `core_visualizer` — YALNIZCA **Entropy'nin kendi turunu**
gösterir: kaynağı tek bir sinyaldir, `bus.core_state_changed`, ve onu yalnızca
etkin köprü `send_message` yolunda yayar (`idle`/`thinking`/`executing`/`error`).
Bir **ajan kartı**, arka plan görevi ya da yordam damıtma koştuğunda çekirdek
durum DEĞİŞTİRMEZ; bu işlerin durumu ajan kartındaki koşu rozetinde
(`ui/widgets/agent_run_state.py`), gezinmedeki "Ajanlar ●n" noktasında ve rozet
ipucunda yaşar. Arka plan sürecinin durumunu çekirdeğe bağlamak yasaktır
(sözleşme testi `tests/ui/test_phase13a2_ux.py`).

**Widget yaşam döngüsü (Faz 13-A2, sözleşme).** Bir widget düzenden çıkarılıp
silinecekse `ui/widgets/lifecycle.discard_widget()` kullanılır. `setParent(None)`
**yasaktır**: Qt sözleşmesine göre widget'ı üst düzey pencereye çevirir ve
`deleteLater()` işleyene kadar masaüstünde boş bir kare olarak parlar
(kullanıcı bir görev koşarken ~20 tanesini gördü). Kapı: `ui_audit`
`orphan_reparents = 0`.

### 8.1 Tasarım sistemi (Faz 11-E, **sözleşme**)

**Tek belirteç kaynağı** `ui/design/tokens.py` → `TOKENS`. Aileler: `color` (12 arayüz
rengi), `space` (1..6 → 4/8/12/16/24/32), `radius` (sm/md/lg), `type`
(title/heading/body/…) ve **ayrı** `TOKENS["viz"]` — görselleştirme paleti
(`add/del/hunk/meta`, `kind1..kind7`, `neutral`). `viz` arayüz renklerine **karışmaz**:
yalnızca veri kodlar (diff boyaması, graf düğüm türü, akış olayı).
**Gövde kodunda ham hex yasak** (Desk'te hex 17 → 0); ihlali `scripts/ui_audit.py` yakalar.

**Tek QSS girişi** `ui/design/qss.py` (yerel stil sayfası 222 → 1). Widget stil **yazmaz**,
Qt **özelliği** verir: `role` (`panel|card|title|heading|label|mono|icon|badge|toast|
statusDot|toolbarGroup`), `variant` (`primary|ghost|danger`),
`tone` (`ok|warn|danger|muted|accent`). Yeni görünüm gerekiyorsa QSS'e seçici eklenir,
widget'a `setStyleSheet` yazılmaz.

**İkonlar** `ui/design/icons.py` — QtAwesome (MIT) Codicons ailesi; QtAwesome yoksa
`icon()` boş `QIcon` döndürür ve arayüz çalışmaya devam eder. Font `.ttf`/charmap `.json`
dosyaları `EntropyAI.spec` `datas`'ına **koşullu** eklenir (paketlenmezse ikonlar boş çıkar).

**Kapılar (test edilen değişmezler):**

| Kapı | Kural |
|---|---|
| Üst çubuk | her kip `self.header_items` kurar, **öğe sayısı ≤ 4**; pencere denetimleri sayılmaz. Çubuktan kaldırılan HER işlevin komut paletinde karşılığı olmak zorundadır (IA-9) |
| Dikey gezinme | `ui/widgets/nav_list.NavList` (`QListWidget` + `QStackedWidget`), `QTabWidget` API'siyle uyumlu (`addTab(widget, label, icon_name)`, `count()`, `tabText(i)`, `setCurrentIndex(i)`, `currentChanged(int)`). Zen'de **7 bölüm**; palet anahtarları `nav_*` bu sırayı izler |
| Palet | `_collect_palette_items()` → `{"kind":"action","label","subtitle","payload"}`; `run_palette_action(key) -> bool` (bilinmeyen anahtar `False`). Zen ve Chat aynı sözleşmeyi paylaşır |
| Odak halkası | odaklanabilir her denetimin QSS `:focus` halkası **ve** `setAccessibleName` değeri vardır (WCAG 4.1.2) |
| Emoji | gövde metninde çıplak emoji yok; işaretler `CHECK_ON="[x]"` / `CHECK_OFF="[ ]"` + `tone` rengi |

**`ui-design` 1.2.0 kapıları (Faz 13-A/13-A2, `scripts/ui_audit.py --gate --final`).**
§0 değişmezi: **metni kaldıran sadeleştirme ikon + erişilebilir ad koymak zorundadır.**

| Kapı | Kural | Sayaç |
|---|---|---|
| G13-1 | boş etkileşimli öğe yok (metinsiz **ve** ikonsuz düğme) | `empty_interactive_count` = 0, `unnamed_icon_buttons` = 0 |
| G13-2 | düğme kenarlık kontrastı ≥ 3:1, **ghost dâhil**; yüzey başına ölçülür (yükseltilmiş zeminde `line.onraised`) | `ghost_button_contrast` = 0, `button_contrast` = 0 |
| G13-3 | tıklama gecikmesi ≤ 50 ms (gerçek kart sayısıyla) | `click_latency_ms` |
| G13-4 | okuyucu ≥ 560 px **ve beyan ≥ hesaplanan** ("kapı beyana dayanamaz") | `reader_min_width`, `min_width_declaration_failures` = 0 |
| G13A2 | ebeveynsiz widget yok (§8 yaşam döngüsü) | `orphan_reparents` = 0 |

Kapılar **gerçekten ölçtüğü** için sınanır: bilerek bozulmuş bir girdiyle kırmızıya
dönmeleri testlidir. Kapı ölçerken gerçek kusur da çıktı (ghost kenarlık 1,29:1 → 3,02:1,
digest şeridi 2,35:1 → 4,85/5,49:1).

Gerekçe: [ADR-0005](adr/ADR-0005-tasarim-sistemi-kendi-belirtecler.md).

---

## 9. Test düzeni

```
tests/
├── conftest.py        kasa + ~/.entropy + ayar yalıtımı (testler ASLA gerçek kasaya yazmaz)
├── contracts/         kalıcı ürün sözleşmeleri (eski test_phase*) + test_architecture_rules.py
├── ui/                PySide6 / offscreen arayüz testleri
├── desk/              Agent Desk: ofisler, harness, sahne, pencere
├── skills/            skills/** paketleri
├── _reference/        (Faz 12-E) sevk edilen kodu SINAMAYAN, kendi kendine yeten
│                      ispat defterleri: 82 dosya / 563 test, `entropy.*` içe aktarmaz
│                      + (Faz 13-C) arşivlenen `claude_bg` spike'ının 32 testi,
│                      `conftest.py` `collect_ignore` ile TOPLANMAZ (ADR-0009)
└── (kök)              modül düzeyi testler
```

Koşum: `QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider`.
Yalnız ürün süiti: `pytest tests --ignore=tests/_reference -q`.
Güncel test sayısı `STATE.md`'dedir.

**Neden `_reference/` ayrıldı:** hız değil (563 test ≈ 7 s, süitin %1,7'si), **ölçüm
dürüstlüğü** — kökte dururken "süit yeşil" cümlesi ürün güvencesini %24 abartıyordu.
Toplama sayısı **değişmedi**; `pyproject.toml` dokunulmadı. Tek istisna Faz 13-C'dir:
`tests/_reference/conftest.py` yalnızca arşivlenen `claude_bg` testlerini toplama dışı
bırakır (toplama 2.605 → 2.573); geri kalan 563 referans testi koşmaya devam eder.

**Bekleme bütçeleri:** sabit duvar saati yerine `tests/timing.budget(saniye)` — makinenin
o anki hızıyla ölçeklenen bütçe (ölçek 1,0–8,0; `ENTROPY_TEST_TIMEOUT_SCALE` ile ezilir).

**Yalıtım:** `tests/conftest.py` gerçek kasayı ve `~/.entropy`'yi izole eder
(`isolate_obsidian_vault`). **Yeni bir yazma noktası eklersen yalıtımı da ekle** —
bugünkü hafızanın %30'u bu yalıtım eksikken sızmış fikstürlerdi.

### 9.1 `docs/` arşiv kuralı (Faz 12-E)

- `docs/reports/` yalnızca **son iki fazın** raporlarını + **koddan/testten atıf yapılan**
  raporları tutar; kapanan faz `docs/reports/_archive/fazNN/` altına iner.
- Atıf yapılan bir rapor taşınacaksa **aynı commit'te** koddaki yol da güncellenir
  (`scripts/_oneshot/sync_faz150_obsidian.py` tam olarak bu kural uygulanmadığı için kırıldı).
- Kullanıcı raporları (`*_audit.md/json`) **silinmez**, `docs/_archive/` altına taşınır.
- Eskimiş özellik belgeleri `docs/_archive/prototype/` altına iner; yerlerine mezar taşı
  `README` bırakılır (`docs/specifications/README.md`).
- **Ürüne bağlanmamış spike kodu** `docs/_archive/spikes/<ad>/` altına iner; yanına
  "ne yapıyordu / neden ertelendi / geri getirme adımları" yazan `README.md` konur
  ([ADR-0009](adr/ADR-0009-claude-bg-arsivlendi.md)).
- **`STATE.md` sıkıştırma kuralı (Faz 13-C):** dosya alt ajanların çalışma belleğidir,
  arşiv değil. §3 sözleşmeler, §5 açık işler ve §7 kırmızı çizgiler **her zaman kalır**;
  yalnız **son iki dilimin** ölçüm tabloları tutulur, daha eskiler
  `docs/_archive/state/STATE_<tarih>_<aralık>.md` altına iner ve STATE'te 3–5 satırlık
  özet + bağlantı kalır.

---

## 10. Faz 11 → **kod**, Faz 12 hedefleri

Faz 11'de "hedef mimari" olarak çizilen zincirin **tamamı bugün kod**:

```
Kullanıcı ─▶ Entropy Chat ─▶ [Beyin v2: MemoryGate ▸ L1 çalışma / L2 anlamsal (graf+wiki)
                 │                       / L3 yordamsal (skill) / kimlik + kurallar]
                 │            ▲ Obsidian = soğuk depo + insan arayüzü
                 ▼            │
        Araştırma (web + aktif skill) ── rapor ── yenilik kapısı (ADD / NOOP / gri bant)
                 │
                 ▼
        Entropy/Board: TASKBOARD.md + Entropy/Tasks/<id>.md + events.jsonl + claims/
                       + agents/<ad>/session.json
        durum makinesi: backlog → assigned → taken → running → review → done | failed | canceled
        BoardDispatcher (QTimer): "panoda sana görev var mı?" → atomik claim
                       (O_CREAT|O_EXCL) → terminal süreci (AGENT.md: provider/model/effort)
                 │
                 ▼
        Ajan araçları (4+1): board_next / checkpoint / finish (kanıtla) / ask · Entropy: board_create
        rapor → Entropy/Reports + pano olayı → sohbete "rapor geldi" kartı → beyne yenilik kapısından
```

Karşılıkları: `brain/gate.py`, `brain/categories.py`, `brain/dream.py`,
`brain/gray_merge.py`, `brain/wiki.py`, `agents/board_fsm.py`, `agents/board_events.py`,
`agents/dispatcher.py`, `agents/board_tools.py`, `agents/amplification.py`,
`core/identity.AgentSessionStore`, `ui/design/{tokens,qss,icons}.py`.

### 10.1 Faz 12 hedefleri

| # | Hedef | Kapı / doğrulama |
|---|---|---|
| 1 | ~~**Depo bakımı (12-E):**~~ — **YAPILDI**; tek seferlik betikler `scripts/_oneshot/`, referans testler `tests/_reference/`, çürük spec ve eskimiş özellik belgeleri `docs/_archive/prototype/`, `skills/` üçüzlemesinin tekilleştirilmesi, `platform/autostart.py` kaldırılması | toplama sayısı değişmez; `tests/_reference` + `tests/skills` + `test_exe` + `test_scheduler` yeşil |
| 2 | ~~**`EntropyAI.spec` sapması:**~~ — **YAPILDI** (Faz 12-A): sapmayı `tests/contracts/test_spec_sync.py` kalıcı olarak sıfırda tutuyor; Faz 11'de eklenen 15 modülün paketlenip paketlenmediği **ölçülür**, eksikse hiddenimports tamamlanır | derleme exit 0; `build/EntropyAI/xref-EntropyAI.html` taraması ya da `.exe` içi içe aktarma kontrolü |
| 3 | ~~**`memory → brain` taşıması**~~ — **YAPILDI** (Faz 13-B, [ADR-0008](adr/ADR-0008-brain-paket-tasimasi.md)); şim **v0.12.0'da kaldırıldı** (Faz 14-F) | `grep -rn 'entropy\.memory' src tests scripts EntropyAI.spec` → 0; test sayısı değişmedi (2.596) |
| 4 | **Açık işler:** `K4/K5/K6` için kalıcı harness, `config.amplification_lock`'un arayüz karşılığı, kartın `report_path` alanının doldurulması, `ui/widgets/tasks_widget.py` eski `dream_and_consolidate` çağrısı | her biri sözleşme testiyle kapanır |

**Kural:** bu bölümdeki bir hedef koda dönüştüğünde aynı commit'te yukarıdaki ilgili
bölüme (§5/§6/§8) taşınır. "Hedef" listesi kod bittikçe **kısalır**, uzamaz.

### 10.2 "Bir yetenek koştur → rapor al" (Faz 14, **kod**; canlı S3 ile ölçüldü)

Faz 13'te bu yol kalıcı kadrodan bir ajan seçip pano kartı açıyordu. Faz 14-C'den sonra
varsayılan yol **geçici ajandır** (§6.4); kalıcı kadro kodu duruyor ama arayüzde gizli.

```
 1. tetik            /skill run <yetenek> :: <istem>  ·  [AJAN run] bloğu  ·  ajansız kart
 2. yetenek çözümü   skills/manager → SKILL.md (yordam + max_steps)
 3. bağlam           brain/context_builder → 4.000 token (kimlik/legacy düğümler hariç)
 4. agent.md         agents/ephemeral.build_agent_md (H1 rapor şablonu + [HAFIZA] + yasaklar)
 5. oturum           yeni uuid4 → --session-id + --no-session-persistence + --agents
                     (+ 14-B onay yüzeyi; --add-dir yalnız workdir ve kasa rapor klasörü)
 6. akış             bus.agent_stream → sohbette tek satır ("Ajan: … yapıyor")
 7. onay             riskli araç → PendingQueue kartı → "onaylıyorum" → allow
 8. rapor            Ajan_<H1>_<zaman>.md (kasada), [HAFIZA] görüntüden silinir
 9. hafıza           alt ajanın JSON'u → MemoryGate.admit (tek kapı)
10. temizlik         workdir + sistem istemi dosyası silinir; ledger/rapor/olay kalır
11. bildirim         TEK bus.task_notification
```

**Ölçülen (S3, 2026-09-11, iki canlı koşum):** run1 → 5 araç adımı, 5 onaylanan
`tool_permission`, 3.611 B rapor, 11 kaynak URL, 5 hafıza maddesi kapıdan geçti;
run2 → 6 akış satırı, 1 araç adımı, 1 onay, 1 bildirim, 2 hafıza maddesi.
Her iki koşumda geçici dizin silindi, kalıcı oturum dosyası **hiç yazılmadı**.
