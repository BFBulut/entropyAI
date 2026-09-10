# Entropy AI — kök sistem bağlamı

> **Bu dosyayı kim okur:** `GEMINI.md`'yi agy CLI oturumları kök bağlam olarak okur.
> `AGENTS.md` bu depoda ajanların **nasıl tanımlandığını** anlatır (kadro listesi değil).
> **`CLAUDE.md` bilerek YOKTUR** — gerekçe [`docs/adr/ADR-0002-claude-saf-kip.md`](docs/adr/ADR-0002-claude-saf-kip.md);
> Entropy'nin kendi kimliği köprüden `--system-prompt-file` ile verilir, depodaki bir
> markdown'dan değil.
>
> Yaşayan mimari: `docs/ARCHITECTURE.md` · Güncel durum: `docs/STATE.md` · Kararlar: `docs/adr/`.
> Bir sözleşme burada ve orada çelişirse **`docs/ARCHITECTURE.md` kazanır**.

Entropy AI, Windows üzerinde çalışan masaüstü-yerel, kendi kendini geliştiren kişisel bir
yapay zekadır: üç arayüz kipi (Zen, Floating, Chat), Obsidian kasası + yerel SQLite bilişsel
bellek, kendi araçlarını yazıp koşturma, MCP orkestrasyonu ve **kendi görev panosu**.
Harici API anahtarı gerektirmez: abonelik kimliğiyle oturum açmış CLI'lar üzerinden koşar.
İçine gömülü ikinci ürün **Entropy Agent Desk**'tir (ofisler, orkestratörler, terminalde
yazılım geliştiren alt ajanlar) — bilgi ve görev akışı **tek yönlüdür**
([ADR-0001](docs/adr/ADR-0001-desk-ayrimi.md)).

---

## 1. Çekirdek mimari ilkeleri

### 1.1 İKİ sağlayıcı köprüsü — Claude birincil, agy ikincil

Entropy bulut API anahtarı kullanmaz; **abonelik kimliğiyle oturum açmış iki CLI**'dan
biriyle konuşur. Sağlayıcı `config.provider` ile seçilir, köprüler aynı olay veriyolu
sözleşmesini paylaşır.

| | Claude köprüsü (`core/claude_bridge.py`) | agy köprüsü (`core/agy_bridge.py`) |
|---|---|---|
| Durum | **birincil koşum yolu** ([ADR-0002](docs/adr/ADR-0002-claude-saf-kip.md)) | ikincil |
| İzolasyon | **Saf Kip: sağlam** | **yok — kayıtlı sınır** |
| Bayraklar | `--system-prompt-file`, `--setting-sources ""`, `--strict-mcp-config`, `--mcp-config`, `--agents <json>`, `CLAUDE_CONFIG_DIR`, `run_cwd()` = `~/.entropy/workspace` | `--conversation` / `--continue`, efor **model varyantı olarak** (ayrı bayrak değil) |
| Oturum | `AgentSessionStore` → `session.json`; `session_id` (yeni) / `conversation_id` (sürdür) | aynı depo, `conversation_id` |
| Ajan derleme | **yalnızca** `claude_compile_root()` = `~/.entropy/workspace` altına (proje kökünde `.claude/agents` OLUŞMAZ) | `compile_roots()`'un hepsine, `.agents/agents/<ad>/agent.md` |

**Claude-only çalışmak zorunludur:** agy kurulu ve oturum açılmış olmasa bile Entropy
tamamen Claude üzerinde koşar ve **kendi kimliğini korur** — çıplak bir CLI terminali gibi
davranmaz (yalıtılmış profil, kendi sistem istemi, kullanıcının kök markdown/MCP/otomatik
hafızası sızmaz).

### 1.2 Üç kipli uyarlanır masaüstü arayüzü

- **Zen:** çerçevesiz tam ekran çalışma istasyonu; merkezde çekirdek görselleştirici,
  bölünebilir terminal panoları, rapor okuyucu, bilgi grafı gezgini, MCP durum yuvası.
  **Dikey gezinme (`NavList`) 7 bölüm**; üst çubukta **en çok 4 öğe** (kapı testi).
- **Floating:** sürüklenebilir küçük pencere, yalnızca nabız atan çekirdek düğümü.
- **Chat:** sohbet öncelikli kip; satır içi görsel (`Ctrl+C`/`Ctrl+V`), token ölçer,
  dinamik model rozeti, katlanır akış terminali.

Tasarım sistemi Faz 11-E'de kuruldu: **tek belirteç kaynağı** `ui/design/tokens.py`,
**tek QSS girişi** `ui/design/qss.py`, ikonlar QtAwesome/Codicons
([ADR-0005](docs/adr/ADR-0005-tasarim-sistemi-kendi-belirtecler.md), `docs/ARCHITECTURE.md` §8.1).

### 1.3 Beyin: hibrit bilişsel bellek + GraphRAG (v2)

- **Obsidian kasası:** yerel-öncelikli, insan okunur markdown dış-beyin; günlük notlar,
  `MEMORY.md`, çift yönlü wikilink grafı. **Kasa soğuk depodur ve ASLA silinmez.**
- **Yerel bilişsel depo:** 12 katmanlı mimari, bugün **tamamen yerel SQLite**
  (`brain/supabase/cognitive_memory.py`). **Supabase/pgvector bağlanmadı**, `supabase`
  paketi bağımlılık listesinde **değil**; mem0 kullanılmıyor
  ([ADR-0003](docs/adr/ADR-0003-hafiza-algoritmasi-mem0-degil.md)).
- **Yazma kapısı (v2):** hafızaya giden tek yol `brain/gate.py` →
  `MemoryGate.admit(...) -> GateDecision` (`add|noop|gray|supersede|reject`);
  `cos >= 0.95` NOOP, `< 0.80` ADD, arası gri bant kuyruğu.
- **Kategori kapalı kümesi:** `working, episodic, semantic, procedural`; kimlik/kural
  **kategori değil bayraktır** (`is_identity`).
- **Turlar:** rüya döngüsü `brain/dream.py` (yeniden gömme → gri tur → kopya birleştirme →
  ölçülü unutma **arşivler, silmez** → wiki adayı → graf konsolidasyonu),
  gri bant birleştirme `brain/gray_merge.py`, wiki derleme `brain/wiki.py`
  (rapor başına bir tur, artımlı, köprüsüz kuru koşum).
- **Yetenek yordamları (playbook):** her yeteneğin raporlarından bir kez damıtılan
  "bu iş nasıl yapılır" metni (`<kasa>/Entropy/Skills/<yetenek>/PLAYBOOK.md`); bağlama
  raporlar değil bu yordam enjekte edilir → tur maliyeti depo büyüklüğünden bağımsız.
  `/distill [<yetenek>|all]` ile arka planda koşar ve kota harcar.
- **Bütçeli bağlam:** `brain/context_builder.py`, `DEFAULT_TOKEN_BUDGET = 4000`;
  sıra playbook → hibrit recall → rapor alıntıları → kalıcı hafıza. Genel sohbet beyin
  paketi `BUDGET_GENERAL_BRAIN = 1500` yalnız yeteneksiz sohbette ödenir.
  Gömme modeli çok dillidir (`paraphrase-multilingual-MiniLM-L12-v2`); Türkçe sorgularda
  İngilizce modelin sınıf ayrımı gürültü seviyesindeydi.
- **Ölçüm paketi:** `scripts/brain_metrics.py` (salt okunur) K1–K12; sözleşme testleri
  `tests/contracts/test_phase11_brain_metrics.py`.

### 1.4 Görev panosu (Entropy Board)

`<kasa>/Entropy/Board/`: `TASKBOARD.md` (türetilmiş) + `events.jsonl` (yalnızca ekleme) +
`claims/<id>.lock` (atomik `O_CREAT|O_EXCL`) + `agents/<ad>/session.json`.
Durum makinesi tek kaynak `agents/board_fsm.py`:
`backlog → assigned → taken → running → review → done | failed | canceled`.
`BoardDispatcher` (QTimer) ajanlara "panoda sana görev var mı?" diye sorar.
Ajan araçları: `board_next / board_checkpoint / board_finish / board_ask` (+ Entropy'de
`board_create`); **kanıtsız `board_finish` reddedilir**. Ayrıntı: `docs/ARCHITECTURE.md` §6.1.1.

### 1.5 Dinamik araç sentezi ve kum havuzu

- Entropy kendi Python/Pydantic-AI araçlarını üretebilir, şemasını doğrular, test eder ve
  tanımlı bir dosya sistemi sınırı içinde koşturur (`tools/synthesizer.py`).
- Tier 2 (değiştirici) araçlar `ToolSynthesizer.set_approval_handler()` ile kayıtlı bir
  onay mercii olmadan **çalıştırılmaz** (fail-closed).
- **Sınır:** kum havuzu denetimi araca geçirilen *yol argümanlarını* doğrular; aracın kendi
  gövdesindeki dosya erişimlerini kısıtlamaz. Gerçek işlem/dosya sistemi izolasyonu değildir.

### 1.6 Otonom arka plan zamanlayıcısı

`scheduler/cron_engine.py` — dakika/saat/gün/hafta ritminde, GUI iş parçacığını bloklamadan
koşan cron benzeri motor (`scheduler_tasks.json`). Günlük rüya turu `daily-dreaming`
kimliğiyle idempotent kaydedilir.
**Windows otomatik başlatma YOKTUR** — `platform/autostart.py` ve `config.autostart_enabled`
Faz 12-E'de kaldırıldı ([ADR-0006](docs/adr/ADR-0006-autostart-kaldirildi.md)):
ayar vardı, davranış yoktu.

---

## 2. Değişmezler (ihlali hata sayılır)

- **Dinamik model rozetleri:** model adı ASLA gömülü yazılmaz. Sağlayıcı sürecinin
  stdout'undan / meta verisinden ayrıştırılır; yedek `[Model: Unknown]`.
- **Gerçek zamanlı çıktı akışı:** alt süreç çıktısı bitene kadar tamponlanmaz;
  `stdout`/`stderr` satır satır Qt sinyalleriyle akıtılır.
- **Görsel etkinlik geri bildirimi:** merkezî çekirdek widget'ı gelen stdout parçalarına
  göre nabız atar/parlar.
- **Bağlam penceresi yönetimi:** istem gönderilmeden önce kayan pencere kısaltması
  uygulanır; token tükenmesi ve gecikme sıçraması önlenir.
- **Ajanlı TDD:** her modülün otomatik `pytest` süiti olur; bir özellik testleri yeşil
  olmadan "bitti" sayılmaz. **Kanıtla kapat:** bir işçi testleri koşup yeşil sonucu
  raporuna iliştirmeden kartı `done` yapamaz.
- **Sıfır taklit (zero-mock) değişmezi:** görev tamamlanmasını taklit etmek için
  `time.sleep()` ya da sahte ilerleme dizgileri KULLANILMAZ. Model/CLI yoksa harness
  gerçek, belirlenimci dosya sistemi eylemleri yapar: dosya okuma, AST çözümleme,
  `ASTPreflightGuard` ile kod yazma, kabuk komutu koşturma, kanıt günlüğü.
- **GUI daima ana iş parçacığında:** widget dokunuşları `bus.call_on_main(object)` üzerinden.
- **Kullanıcı verisi kutsaldır:** `~/.entropy` ve Obsidian kasası ASLA silinmez;
  testler `tests/conftest.py` ile ikisini de izole eder.
- **Tek yönlü Desk sınırı:** Entropy Desk'i bilir ve geliştirir; Desk Entropy'yi **bilmez**.
  Orkestratör istemlerinde Entropy'nin adı geçmez; Desk Entropy'nin panosuna kart itemez.
- **Marka kuralı:** ticari referans ürünün ve üreticisinin adı **hiçbir dosyaya** yazılmaz
  (kod, test, belge, rapor, veri, not). "Ticari referans ürün" diye anılır.
- **`EntropyAI.spec` hiddenimports bir dizgi listesidir:** yalnız `importlib` ile çağrılan
  bir modül eklenmezse `.exe` **sessizce eksik** paketlenir (Faz 10-C'de yaşandı).

---

## 3. Directory Map

> Faz 12-E'de gerçekle eşitlendi (2026-09-10). Ayrıntılı ve **yaşayan** mimari:
> `docs/ARCHITECTURE.md`; güncel durum: `docs/STATE.md`; kararlar: `docs/adr/`.
> Bu haritada olmayan bir klasör görürsen ya harita ya kod yanlıştır — ikisinden
> birini aynı commit'te düzelt.

```text
C:/EntropiAI/
├── GEMINI.md                           # Kök sistem bağlamı, değişmezler ve dizin haritası
├── AGENTS.md                           # Bu depoda ajanlar nasıl tanımlanır (kadro listesi DEĞİL)
├── THIRD_PARTY.md                      # Üçüncü taraf varlık ve lisans bildirimleri
├── EntropyAI.spec                      # PyInstaller (hiddenimports bir dizgi listesidir!)
├── run_entropy.py                      # Giriş noktası -> entropy.main:main
├── launch.bat · entropy.ico · entropy.png · pyproject.toml
├── .claude/agents/                     # YALNIZCA kullanıcının 6 geliştirme alt ajanı
├── .agents/agents/distiller/           # agy biçiminde damıtıcı ajan (izlenen tek tanım)
├── docs/
│   ├── ARCHITECTURE.md                 # Yaşayan mimari (paketler, veri kökleri, sözleşmeler)
│   ├── STATE.md                        # Güncel durum — alt ajanların çalışma belleği
│   ├── ROADMAP.md                      # Faz durumları (eski PHASED_ROADMAP.md)
│   ├── adr/                            # ADR-0001… geri alınamaz kararlar
│   ├── reports/                        # Faz raporları (tarih önekli)
│   ├── specifications/README.md        # MEZAR TAŞI: 5 eski spec _archive/prototype/'a taşındı
│   └── _archive/                       # customer/ (müşteri çıktıları) · prototype/ (eski spec'ler +
│                                       # OneFile spec) · skills/ (tekilleştirmede ayrılan kopyalar)
├── src/
│   └── entropy/
│       ├── __init__.py · main.py       # Uygulama girişi ve açılış kablolaması
│       ├── core/                       # config, event_bus, claude_bridge, agy_bridge, provider,
│       │                               # paths, identity, slash_commands, task_ledger, kilitler
│       ├── agents/                     # registry, compile, tasks, harness, mailbox, worktrees,
│       │                               # pr_flow, templates, watchers, desk_registry (Desk defteri)
│       ├── brain/                      # bilişsel bellek, graf, wiki, playbook, context_builder,
│       │   ├── obsidian/               # kasa yöneticisi
│       │   ├── supabase/               # 12 katmanlı bilişsel bellek (bugün yerel SQLite)
│       │   └── rag/                    # proje kodu indeksleme
│       ├── desk/                       # Agent Desk penceresi ve panelleri
│       │   ├── engine/                 # piksel sahne motoru
│       │   ├── assets/                 # piksel varlıklar (CC0 — bkz. THIRD_PARTY.md)
│       │   └── templates/              # ekip şablonları
│       ├── ui/
│       │   ├── modes/                  # zen_mode, chat_mode, floating_mode
│       │   ├── widgets/                # 29 widget (graf, rapor merkezi, komut paleti, terminal…)
│       │   ├── themes/                 # eski tema artıkları
│       │   └── design/                 # tokens.py · qss.py · icons.py (TEK belirteç ve stil kaynağı)
│       ├── skills/                     # SKILL.md keşfi (manager.py) + tembel yüklenen motorlar
│       ├── tools/                      # synthesizer.py (dinamik araç sentezi) — tek ürün modülü
│       ├── mcp/                        # MCP hub ve süreç yöneticisi
│       ├── scheduler/                  # cron benzeri arka plan görev koşucusu
│       └── platform/                   # clipboard.py (pano görsel işleyici) — autostart KALDIRILDI
├── skills/                             # Kurulu yetenek paketleri (tireli dizin = kanonik, SKILL.md +
│                                       # scripts/; alt çizgili dizin = testlerin içe aktardığı proxy)
├── scripts/                            # CANLI geliştirici betikleri (brain_metrics, memory_migrate_v2,
│   └── _oneshot/                       # perf_bench, routing_eval, ui_audit…) — _oneshot/: 59 tek
│                                       # seferlik faz betiği, KOŞULMAZ (bkz. _oneshot/README.md)
├── scratch/                            # Ölçüm çıktıları ve ekran görüntüleri (git'te dar kapsamlı)
└── tests/
    ├── conftest.py                     # kasa + ~/.entropy yalıtımı
    ├── contracts/                      # kalıcı ürün sözleşmeleri (eski test_phase*)
    ├── ui/ · desk/ · skills/           # konu bazlı gruplar
    ├── _reference/                     # 82 dosya / 563 test — ürün kodunu SINAMAYAN ispat defterleri
    └── (kök)                           # modül testleri
```

**Haritada bilerek OLMAYANLAR** (eski haritada vardı, gerçekte yok):

- `Agents/` klasörü ve `persona.md` dosyaları — gerçek kadro kasadadır
  (`<kasa>/Entropy/Agents/<ad>/AGENT.md`, `entropy.agents.registry`).
- `src/entropy/agent_desk/` ve `run_agent_desk.py` — Desk ayrı bir uygulama olarak
  başlatılmıyor; kodu `src/entropy/desk/` altında ve Entropy'nin içine gömülü.
- `docs/PHASED_ROADMAP.md` — `docs/ROADMAP.md` oldu.
- `src/entropy/tools/autonomous_agent_architecture*` — 60 dosyalık üretilmiş prototip,
  Faz 11-A'da 32 testiyle birlikte silindi.
- `dist/`, `build/`, `dist_check/`, `build_check/`, kök `EntropyAI.exe` — üretilmiş çıktı;
  `.gitignore`'da ve depoda tutulmaz, `pyinstaller EntropyAI.spec` ile yeniden üretilir.
- `CLAUDE.md` — **bilerek yok**; gerekçe `docs/adr/ADR-0002-claude-saf-kip.md`.
- `EntropyAI_OneFile.spec` — çürümüştü (kimse çağırmıyordu, 32/127 hiddenimports,
  makineye çakılı `pathex`); Faz 12-E'de `docs/_archive/prototype/EntropyAI_OneFile.spec.txt`
  olarak arşivlendi. Onefile derleme gerekirse `EntropyAI.spec` üzerinden türetilir.
- `src/entropy/platform/autostart.py` — kaldırıldı, `docs/adr/ADR-0006-autostart-kaldirildi.md`.
- `docs/specifications/` içindeki 5 spec — `docs/_archive/prototype/` altında; klasörde
  yalnızca mezar taşı `README.md` var.
