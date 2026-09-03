# Entropy AI (Agentic OS & Antigravity Interface)

Entropy AI is an autonomous, desktop-native Agentic Operating System designed specifically as a sophisticated companion and interface for Google Antigravity (`agy` CLI). It runs on Windows, features three fluid desktop modes (Zen, Floating, Chat), maintains persistent cognitive memory via Obsidian and Supabase pgvector, writes and executes its own tools, and provides full MCP orchestration without requiring external API keys.

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
   - **Supabase pgvector & Mem0 Layer**: 12-layer cognitive memory architecture (Surprise filter, Ebbinghaus forgetting curve, background consolidation/dreaming, ego/persona stability, and hybrid recall combining vector similarity, recency, and importance).
   - **Project RAG**: Codebase indexing and semantic retrieval for any user-selected project folder.

4. **Dynamic Tool Synthesis & Sandboxing**:
   - Entropy AI can generate its own Python/Pydantic-AI tools on the fly, validate their schemas, test them, and execute them within a strictly defined filesystem boundary.
   - Sandboxing guarantees that execution blast radius is contained strictly to the designated project directory.

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
│       │   ├── supabase/               # pgvector client & Mem0 cognitive layers
│       │   └── rag/                    # Project codebase indexing & vector search
│       ├── tools/                      # Self-tooling & Pydantic AI dynamic tool synthesis
│       ├── mcp/                        # MCP hub & 'agy mcp' process manager
│       ├── scheduler/                  # Cron-like background task runner
│       └── platform/                   # Windows startup hooks & clipboard image handler
└── tests/                              # Automated pytest suites (unit, mock-CLI, UI headless)
```
