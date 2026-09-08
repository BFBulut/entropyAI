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

```text
c:/EntropiAI/
├── GEMINI.md                           # Root system context, invariants & directory map
├── AGENTS.md                           # Agent registry and interaction protocol
├── Agents/
│   └── EntropyAI/
│       └── persona.md                  # Autonomous agent identity, boundaries & behavioral specs
├── docs/
│   ├── PHASED_ROADMAP.md               # Phased implementation and research documentation
│   └── specifications/
│       ├── SYSTEM_ARCHITECTURE.md      # High-level architecture and IPC specification
│       ├── UI_SPECIFICATION.md         # Zen, Floating, Chat modes and widget designs
│       ├── MEMORY_RAG_SPECIFICATION.md # Supabase pgvector + Mem0 + Obsidian GraphRAG specs
│       ├── AGY_CLI_INTEGRATION.md      # Antigravity CLI process wrapper & streaming specs
│       └── TASK_SCHEDULER_SPECIFICATION.md # Background cron scheduler specs
├── src/
│   └── entropy/
│       ├── __init__.py
│       ├── main.py                     # Application entry point & Windows startup initializer
│       ├── core/                       # Core configuration, event bus, and state management
│       ├── ui/                         # PySide6 GUI implementations
│       │   ├── modes/                  # ZenModeWindow, FloatingModeWidget, ChatModeWindow
│       │   ├── widgets/                # CoreVisualizerWidget, TerminalWidget, ReportsReader, MemoryGraph
│       │   └── themes/                 # High-contrast cybernetic/dark aesthetic design tokens
│       ├── memory/                     # Hybrid memory system
│       │   ├── obsidian/               # Vault Operator & Markdown parser
│       │   ├── supabase/               # Mem0 bilişsel katmanlar (bugün SQLite üzerinde; pgvector bağlanmadı)
│       │   └── rag/                    # Project codebase indexing & vector search
│       ├── agent_desk/                 # Çok ofisli otonom ajan platformu (ayrı uygulama: run_agent_desk.py)
│       │   ├── core/                   # Harness, görev yürütücü, ofis orkestratörü, worktree yöneticisi
│       │   ├── ui/                     # AgentDeskWindow, piksel ofis tuvali, kanban, terminal ızgarası
│       │   ├── analysis/               # Nicel finans modelleri (numpy gerektirir)
│       │   ├── memory/                 # Bölümlenmiş ajan belleği & bellek grafiği köprüsü
│       │   └── research/               # Otonom ofis araştırmacısı
│       ├── skills/                     # SKILL.md keşfi, içe aktarma ve yürütme motoru
│       ├── tools/                      # Self-tooling & Pydantic AI dynamic tool synthesis
│       ├── mcp/                        # MCP hub & 'agy mcp' process manager
│       ├── scheduler/                  # Cron-like background task runner
│       └── platform/                   # Windows startup hooks & clipboard image handler
├── skills/                             # Kurulu yetenek paketleri (her biri SKILL.md içerir)
└── tests/                              # Automated pytest suites (unit, mock-CLI, UI headless)
```
