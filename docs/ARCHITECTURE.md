# Entropy AI — Yaşayan Mimari

> **Bu dosya kaynağın kendisiyle birlikte güncellenir.** Bir sözleşme değişirse (paket yeri,
> veri kökü, sinyal adı, kart alanı) aynı commit'te burası da değişir. Eskimiş bir mimari
> belgesi olmamasının tek yolu budur; `docs/_archive/prototype/` altındaki eski belgeler
> tam olarak bu kural uygulanmadığı için arşive düştü.
>
> Sürüm: v0.8.0 · Dal: `ai/v0.1.7` · Son güncelleme: 2026-09-10 (Faz 11-A)
> Güncel durum ve açık işler için: [`STATE.md`](STATE.md) · Kararlar için: [`adr/`](adr/)

---

## 1. İki ürün, tek depo

| | Entropy AI | Entropy Agent Desk |
|---|---|---|
| Ne | Kişisel, kendi kendini geliştiren yapay zeka: beyin (RAG + hafıza), kendi ajanları, görev panosu, üç arayüz kipi | Entropy'nin **içine gömülü ayrı uygulama**: ofisler, orkestratörler, terminallerde yazılım geliştiren alt ajanlar |
| Kod | `src/entropy/{core,agents,memory,skills,ui,mcp,scheduler,platform,tools}` | `src/entropy/desk/` + `src/entropy/agents/{desk_registry,harness,offices,worktrees,pr_flow,templates}.py` |
| Veri kökü (kasa) | `<kasa>/Entropy/**` | `<kasa>/Desk/**` |
| Ajanları | `Entropy/Agents/<ad>/AGENT.md` | `Desk/Offices/<ofis>/agents/**` |

**Bilgi tek yönlüdür.** Entropy Desk'in mimarisini bilir ve onu geliştirebilir; Desk
Entropy'nin mimarisini **bilmez**. Orkestratör istemlerinde Entropy'nin adı geçmez.
**Görev akışı da tek yönlüdür:** Entropy Desk orkestratörlerine görev/mesaj gönderir ve
rapor alır; Desk Entropy'nin panosuna kart **itemez**. Gerekçe ve zorlayıcı testler:
[ADR-0001](adr/ADR-0001-desk-ayrimi.md), `tests/contracts/test_phase9_desk_separation.py`.

---

## 2. Paketler

| Paket | Dosya | Satır | Rol |
|---|---:|---:|---|
| `ui/` (+ `modes/`, `widgets/`, `themes/`) | 37 | ~20.700 | PySide6 kabuğu: Zen / Chat / Floating kipleri, 29 widget |
| `memory/` (+ `rag/`, `obsidian/`, `supabase/`) | 22 | ~13.800 | bilişsel bellek, graf, wiki, playbook, bağlam kurucu, ofis çalışma alanı, damıtıcı |
| `core/` | 15 | ~11.700 | yapılandırma, olay veriyolu, iki sağlayıcı köprüsü, slash komutlar, kilit, kimlik, defter |
| `agents/` | 13 | ~8.500 | ajan kayıt defteri, derleme, görev kartları, harness, posta kutusu, worktree, PR akışı, şablonlar |
| `desk/` (+ `engine/`, `assets/`, `templates/`) | 20 | ~6.700 | Agent Desk penceresi, piksel sahne motoru, paneller |
| `skills/` | 5 | ~2.000 | `SKILL.md` keşfi (`manager.py`) + motorlar (tembel yüklenir) |
| `mcp/` · `scheduler/` · `platform/` · `tools/` | 9 | ~1.075 | MCP yapılandırması, zamanlayıcı, Windows yardımcıları, araç sentezleyici |

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

---

## 5. Beyin: hafıza katmanları

| Katman | Nerede | Ne tutar |
|---|---|---|
| Bilişsel bellek (12 katmanlı, çift depo) | `memory/supabase/cognitive_memory.py` — yerel SQLite + isteğe bağlı pgvector | düğümler, gömmeler, hibrit recall (semantik + sözcüksel) |
| Bilgi grafı | `memory/graph_store.py`, `graph_enrich.py`, `office_graph.py` | düğüm-kenar grafı, PPR benzeri genişletme, topluluklar |
| Wiki (derlenmiş bilgi) | `memory/wiki.py`, `lint.py` | raporlardan damıtılmış kalıcı maddeler |
| Playbook (yordamsal) | `memory/playbook.py` | "bu iş nasıl yapılır" — yetenek başına yordam |
| Kalıcı notlar | kasada `MEMORY.md` | kullanıcının elle düzenlediği gerçek |
| Ofis çalışma alanı | `memory/office_workspace.py` | `BOARD.md`, `ARCHITECTURE.md`, `RULES.md`, `checkpoints/<kart-id>.md` |
| Uzlaştırma | `memory/reconcile.py` | "bunu zaten biliyorum" denetimi (bugün yalnızca graf katmanına bağlı — Faz 11-B'nin ana işi) |
| Damıtma / rapor akışı | `memory/distiller.py`, `report_watcher.py`, `handoff.py` | rapor → wiki/playbook hattı |

**Bağlam kurucu** (`memory/context_builder.py`) sabit bir token bütçesini
(`DEFAULT_TOKEN_BUDGET = 4000`) öncelik sırasıyla doldurur: playbook → hibrit recall →
rapor alıntıları → kalıcı hafıza. Maliyet kasanın büyüklüğünden bağımsızdır.

**Onaylı kurallar** (`memory/promoted_rules.py`): ajan bir kural keşfettiğinde uygulama
kullanıcıya sorar; yalnızca "kalıcı yap" denince kural o ajanın sistem istemine her koşuda
enjekte edilir. Ajanlar hata ve günlük **yazmaz**.

Hafızanın bugünkü açığı ve algoritma kararı:
[ADR-0003](adr/ADR-0003-hafiza-algoritmasi-mem0-degil.md).

---

## 6. Görev panosu, kartlar ve harness

### 6.1 Kart = dosya

`agents/tasks.py` — her kart `<kasa>/Entropy/Tasks/<id>.md`, YAML ön bilgi + gövde.
Neden dosya: kullanıcı Obsidian'da düzenleyebilsin ve iki taraf da aynı gerçeği görsün.

Ön bilgi alanları (`TaskCard`): `id, title, status, agent, provider, model, skill, created_at,
started_at, finished_at, output_paths, summary, office, project, parent, children, grade,
verdict, attempt, budget_tokens, intent, checkpoint, proof, worktree, branch, pr_url`.
Gövde: `## Hedef / ## Kabul ölçütleri / ## Notlar / ## Sonuç`.
Yaşam döngüsü: `backlog → running → review → done` (`review` insan onayını bekler).
Ofis kartları ayrı depoda: `<ofis>/cards/`.

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
| Görevler | `task_triggered(str, str)`, `task_completed(str, bool)`, `task_notification(str, str, str)`, `task_followup_completed(dict)`, `task_cards_updated(str)` |
| Bilgi | `report_created(str)`, `node_selected(str)`, `knowledge_graph_updated()`, `cognitive_memory_updated()`, `skills_updated()`, `skill_detected(str, float)`, `playbook_updated(str)`, `reports_updated(str)`, `distill_progress(str, int, int)`, `report_inbox_unread(int)` |
| Ajanlar / ofisler | `agents_updated(str)`, `offices_updated(str)`, `office_progress(str, str, str)`, `mailbox_updated(str, str)`, `rules_updated(str, int)`, `checkpoint_written(dict)`, `proof_recorded(dict)` |
| Hata / sağlayıcı | `memory_error(dict)`, `provider_status_updated(str, dict)`, `mcp_servers_updated()` |
| İş parçacığı | `call_on_main(object)` — GUI dokunuşları daima ana iş parçacığında |

---

## 8. Arayüz

Üç kip: **Zen** (tam pano), **Chat** (sohbet öncelikli), **Floating** (küçük yüzen pencere) —
`ui/modes/`. 29 widget `ui/widgets/` altında. Tasarım sistemi bugün **yoktur**: iki yarım
sistem (`CYBER_THEME` ve `READING_TOKENS`) aynı rolleri farklı değerlerle dolduruyor.
Faz 11-E'de tek bir belirteç sistemi kurulacak
([ADR-0005](adr/ADR-0005-tasarim-sistemi-kendi-belirtecler.md)).

---

## 9. Test düzeni

```
tests/
├── conftest.py        kasa + ~/.entropy + ayar yalıtımı (testler ASLA gerçek kasaya yazmaz)
├── contracts/         kalıcı ürün sözleşmeleri (eski test_phase*) + test_architecture_rules.py
├── ui/                PySide6 / offscreen arayüz testleri
├── desk/              Agent Desk: ofisler, harness, sahne, pencere
├── skills/            skills/** paketleri
└── (kök)              modül düzeyi testler ve nicel finans defterleri
```

Koşum: `QT_QPA_PLATFORM=offscreen python -m pytest -q -p no:cacheprovider`.
Güncel test sayısı `STATE.md`'dedir.

---

## 10. Faz 11 hedef mimarisi

```
Kullanıcı ─▶ Entropy Chat ─▶ [Beyin v2: MemoryGate ▸ L1 çalışma / L2 anlamsal (graf+wiki)
                 │                       / L3 yordamsal (skill) / kimlik + kurallar]
                 │            ▲ Obsidian = soğuk depo + insan arayüzü
                 ▼            │
        Araştırma (web + aktif skill) ── rapor ── yenilik kapısı (ADD / NOOP / gri bant)
                 │
                 ▼
        Entropy/Board: TASKBOARD.md + tasks/<id>.md + events.jsonl + claims/
                       + agents/<ad>/session.json
        durum makinesi: backlog → assigned → taken → running → review → done | failed | canceled
        BoardDispatcher (QTimer): her ajana "panoda sana görev var mı?" → atomik claim
                       (O_CREAT|O_EXCL) → terminal süreci (AGENT.md: provider/model/effort)
                 │
                 ▼
        Ajan araçları (4+1): board_next / checkpoint / finish (kanıtla) / ask · Entropy: board_create
        rapor → Entropy/Reports + pano olayı → sohbete "rapor geldi" kartı → beyne yenilik kapısından
```

Desk bu ilkeleri zaten uyguluyor; Faz 11'de **Entropy tarafı ona yetişir**.
Paket adları bu fazda taşınmaz ([ADR-0004](adr/ADR-0004-faz11-paket-tasima-yok.md));
`memory → brain` Faz 12'dir.
