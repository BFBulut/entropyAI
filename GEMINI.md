# Entropy AI (Agentic OS & Antigravity Interface)

Entropy AI is an autonomous, desktop-native Agentic Operating System designed specifically as a sophisticated companion and interface for Google Antigravity (`agy` CLI). It runs on Windows, features three fluid desktop modes (Zen, Floating, Chat), maintains persistent cognitive memory via Obsidian and a local SQLite cognitive store, writes and executes its own tools, and provides full MCP orchestration without requiring external API keys.

---

## 1. Core Architecture Principles

1. **Antigravity CLI (AGY) as Core Engine**:
   - Zero direct cloud API key dependencies; Entropy AI communicates directly with the authenticated `agy` CLI process via `QProcess` or asynchronous `subprocess.Popen`.
   - All tool approvals, session resumptions (`--conversation`, `--continue`), model reasoning efforts (`--effort`), and mode selections (`accept-edits`, `plan`) are controlled through AGY.

2. **Tri-Modal Adaptive Desktop Interface**:
   - **Zen Mode**: Immersive, borderless fullscreen workstation featuring a glowing central AI core visualizer, infinite split terminal panes, research report visualizer/reader, knowledge graph explorer, and active MCP status dock.
   - **Floating Mode**: Ambient, draggable minimalist desktop widget showing only the pulsing AI core node. Features a rich context menu (Right-click: Pin on Top, Switch to Zen, Open Chat, Quick Command, Minimize).
   - **Chat Mode**: Floating conversational modal with inline multi-modal image support (`Ctrl+C` / `Ctrl+V`), dynamic token meter, live dynamic model badges, and collapsible streaming terminal drawer.

3. **Hybrid Cognitive Memory & GraphRAG**:
   - **Obsidian Vault Layer**: Local-first, human-readable markdown exocortex situated at the user's Obsidian Vault. Manages daily notes, architectural decision records (`MEMORY.md`), and bidirectional wikilink graphs.
   - **Local Cognitive Store (Mem0 Layer)**: 12-layer cognitive memory architecture (Surprise filter, Ebbinghaus forgetting curve, background consolidation/dreaming, ego/persona stability, and hybrid recall combining vector similarity, recency, and importance). Bugün tamamen yerel SQLite üzerinde çalışır (`memory/supabase/cognitive_memory.py`); Supabase/pgvector arka ucu henüz bağlanmadı ve `supabase` paketi bağımlılık listesinde değildir.
   - **Project RAG**: Codebase indexing and semantic retrieval for any user-selected project folder.
   - **Yetenek Yordamları (Skill Playbooks)**: Her yeteneğin birikmiş araştırma raporlarından bir kez damıtılan "bu iş nasıl yapılır" metni (`<vault>/Entropy/Skills/<yetenek>/PLAYBOOK.md`). Bağlama her turda raporların kendisi değil bu yordam enjekte edilir; böylece tur maliyeti depo büyüklüğünden bağımsız kalır. Damıtma `/distill [<yetenek>|all]` komutu ya da yetenek panelindeki 📘 düğmesiyle AGY üzerinden arka planda çalışır ve kota harcar. Kaynak raporlar `.entropy/skill_report_index.json` indeksiyle yeteneklere eşlenir; kasa dosyalarına dokunulmaz. Damıtma, agy'nin `distiller` alt ajanıyla koşar (`.agents/agents/distiller/agent.md`; araçsız, `model: flash`, tek yanıt) — ajan tanımı etkin proje dizinine yoksa `entropy.memory.distiller.ensure_distill_agent` tarafından yazılır; agy ajanları çalışma dizinine göre keşfeder. Not: `media-agency-researcher` 2026-09-07'de `media-agency-soldier` içine katıldı (araştırma aşamaları + `scripts/web_media_audit.py`); yönlendirme anahtar kelimeleri de oraya taşındı.
   - **Bütçeli Bağlam Kurulumu**: `memory/context_builder.py` sabit bir token bütçesini öncelik sırasıyla doldurur: yordam → proje hafızası → hibrit recall → rapor alıntıları → kod → MEMORY.md. Gömme modeli çok dillidir (`paraphrase-multilingual-MiniLM-L12-v2`); Türkçe sorgularda İngilizce modelin sınıf ayrımı gürültü seviyesindeydi.
   - **Yetenek Yönlendirme**: Sözcüksel skor + anlamsal benzerlik (ad, açıklama, Türkçe alan anahtar kelimeleri, playbook başı) + konuşma önceliği (kısa göndermeli takiplerde son yetenek). Tüm çağrılar `AgyProcessBridge.detect_skill_for_prompt()` üzerinden geçer.

4. **Dynamic Tool Synthesis & Sandboxing**:
   - Entropy AI can generate its own Python/Pydantic-AI tools on the fly, validate their schemas, test them, and execute them within a defined filesystem boundary.
   - Tier 2 (mutating) araçlar, `ToolSynthesizer.set_approval_handler()` ile kayıtlı bir onay mercii olmadan çalıştırılmaz (fail-closed).
   - **Sınır**: Kum havuzu denetimi araca geçirilen *yol argümanlarını* doğrular; aracın kendi gövdesindeki dosya erişimlerini kısıtlamaz. Gerçek bir işlem/dosya sistemi izolasyonu değildir.

5. **Autonomous Background Task Scheduler**:
   - Cron-like engine executing periodic tasks on minute, hour, day, and week cadences without blocking the GUI thread.
   - Direct integration with Windows Startup (`shell:startup` or registry `Software\Microsoft\Windows\CurrentVersion\Run`).

---

## 2. Mandatory Rules & Invariants

- **Dynamic Model Badges**: NEVER hardcode model names (e.g. `[Gemini 2.5 Flash]`). Always parse dynamically from `agy` process stdout or metadata. Default fallback is `[Model: Unknown]`.
- **Real-Time Output Piping**: Never buffer subprocess outputs until completion. Stream `stdout` and `stderr` line-by-line using Qt signals to keep the terminal and visualizer instantly responsive.
- **Visual Activity Feedback**: The central AI core widget must pulse/glow dynamically in response to incoming stdout chunks ("active thinking/typing").
- **Context Window Management**: Implement sliding context window truncation (e.g., last 20 messages with summarization) before dispatching prompts to prevent token exhaustion and latency spikes.
- **Agentic TDD**: Every module must be accompanied by automated `pytest` test suites. 100% test pass rate is mandatory before considering any feature complete.
- **Concrete Agent Harness & Zero-Mock Invariant**: Never use `time.sleep()` or hardcoded simulated progress strings (`-> Dosya taranıyor...`, `-> Kod üretildi...`) to emulate task completion. If an external model or CLI is unavailable, the execution harness MUST execute real deterministic filesystem actions: reading files, analyzing ASTs, writing code files via `ASTPreflightGuard`, running shell commands, and recording evidence logs. Goal decomposers must introspect the actual project directory and test suites to produce file-grounded `TaskItem`s with concrete DoD. Multi-agent systems must automatically dispatch structured A2A handoff events upon task completion.

---

## 3. Directory Map

> Faz 11-A'da gerçekle eşitlendi (2026-09-10). Ayrıntılı ve **yaşayan** mimari:
> `docs/ARCHITECTURE.md`; güncel durum: `docs/STATE.md`; kararlar: `docs/adr/`.
> Bu haritada olmayan bir klasör görürsen ya harita ya kod yanlıştır — ikisinden
> birini aynı commit'te düzelt.

```text
C:/EntropiAI/
├── GEMINI.md                           # Kök sistem bağlamı, değişmezler ve dizin haritası
├── AGENTS.md                           # Bu depoda ajanlar nasıl tanımlanır (kadro listesi DEĞİL)
├── THIRD_PARTY.md                      # Üçüncü taraf varlık ve lisans bildirimleri
├── EntropyAI.spec                      # PyInstaller (hiddenimports bir dizgi listesidir!)
├── EntropyAI_OneFile.spec
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
│   ├── specifications/                 # Eski spec'ler (ARCHITECTURE.md'ye damıtılıyor)
│   └── _archive/{customer,prototype}/  # Müşteri çıktıları ve silinen prototipin notları
├── src/
│   └── entropy/
│       ├── __init__.py · main.py       # Uygulama girişi ve açılış kablolaması
│       ├── core/                       # config, event_bus, claude_bridge, agy_bridge, provider,
│       │                               # paths, identity, slash_commands, task_ledger, kilitler
│       ├── agents/                     # registry, compile, tasks, harness, mailbox, worktrees,
│       │                               # pr_flow, templates, watchers, desk_registry (Desk defteri)
│       ├── memory/                     # bilişsel bellek, graf, wiki, playbook, context_builder,
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
│       │   └── themes/                 # bugün iki yarım sistem; Faz 11-E'de tek belirteç seti
│       ├── skills/                     # SKILL.md keşfi (manager.py) + tembel yüklenen motorlar
│       ├── tools/                      # synthesizer.py (dinamik araç sentezi) — tek ürün modülü
│       ├── mcp/                        # MCP hub ve süreç yöneticisi
│       ├── scheduler/                  # cron benzeri arka plan görev koşucusu
│       └── platform/                   # Windows açılış kancaları, pano görsel işleyici
├── skills/                             # Kurulu yetenek paketleri (her biri SKILL.md içerir)
├── scripts/                            # Geliştirici betikleri (perf_bench, routing_eval, graph_metrics…)
├── scratch/                            # Ölçüm çıktıları ve ekran görüntüleri (git'te dar kapsamlı)
└── tests/
    ├── conftest.py                     # kasa + ~/.entropy yalıtımı
    ├── contracts/                      # kalıcı ürün sözleşmeleri (eski test_phase*)
    ├── ui/ · desk/ · skills/           # konu bazlı gruplar
    └── (kök)                           # modül testleri ve nicel finans defterleri
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
