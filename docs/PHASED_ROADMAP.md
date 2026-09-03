# Phased Implementation Roadmap - Entropy AI

This roadmap outlines the phased development of the Entropy AI Desktop Agentic Operating System, structured in accordance with Agentic TDD and Markdown-First Architecture principles.

---

## Phase 1: Foundation, Specifications & Project Scaffolding
- [x] Project architecture blueprint and directory layout
- [x] Specification documents (`SYSTEM_ARCHITECTURE.md`, `UI_SPECIFICATION.md`, `MEMORY_RAG_SPECIFICATION.md`, `AGY_CLI_INTEGRATION.md`, `TASK_SCHEDULER_SPECIFICATION.md`)
- [x] `GEMINI.md`, `AGENTS.md`, and persona files (`Agents/EntropyAI/persona.md`)
- [ ] Python project environment scaffolding (`pyproject.toml` or `requirements.txt`, directory trees)

## Phase 2: Core Engine & AGY CLI Non-Blocking Bridge
- [ ] Subprocess / `QProcess` asynchronous wrapper for `agy`
- [ ] Real-time stdout/stderr stream parsing with Qt signal dispatch
- [ ] Dynamic model detection parser (guaranteeing compliance with `agent-ui-models.md`)
- [ ] Context window sliding buffer & message summarizer
- [ ] Automated test suite: `tests/test_agy_bridge.py`

## Phase 3: PySide6 Desktop GUI - Tri-Modal Shell
- [ ] Mode 1: Zen Mode (Borderless fullscreen window, split terminal, reports reader, knowledge graph view)
- [ ] Mode 2: Floating Mode (Minimalist glowing particle core orb, always-on-top, right-click menu)
- [ ] Mode 3: Chat Mode (Floating dialog, collapsible terminal drawer, real-time message bubbles)
- [ ] CoreVisualizerWidget (Dynamic glowing/pulsing linked directly to streaming token chunks)
- [ ] Multimodal clipboard handler (`Ctrl+C` / `Ctrl+V` image paste detection and local cache staging)
- [ ] Automated test suite: `tests/test_ui_modes.py`

## Phase 4: Hybrid Cognitive Memory & RAG Engine
- [ ] Obsidian Vault Manager (Read/Write markdown, daily notes, wikilink parsing)
- [ ] Supabase pgvector client & schema initialization
- [ ] Mem0 12-layer cognitive components (Surprise filter, Ebbinghaus decay, Dreaming/Consolidation)
- [ ] Project Codebase Indexer & local vector search
- [ ] Automated test suite: `tests/test_memory_rag.py`

## Phase 5: MCP Hub & Dynamic Self-Tooling Engine
- [ ] MCP Server Manager (Wrapping `agy mcp list`, `enable`, `disable`, `add`)
- [ ] StitchMCP integration bridge for on-the-fly UI generation
- [ ] Pydantic AI dynamic tool synthesis, validation, and sandboxed test execution
- [ ] Automated test suite: `tests/test_mcp_and_tools.py`

## Phase 6: Scheduler & Windows System Integration
- [ ] Minutely, hourly, daily, weekly background task scheduler
- [ ] Windows Startup auto-launch integration (`shell:startup` / Registry `HKCU\Run`)
- [ ] System tray icon and global hotkeys
- [ ] Automated test suite: `tests/test_scheduler.py`

## Phase 7: System Integration, E2E Verification & Packaging
- [ ] End-to-end integration tests verifying all 3 modes and AGY workflows
- [ ] User walkthrough and visual verification
- [ ] Self-contained executable / startup script launcher
