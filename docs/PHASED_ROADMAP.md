# Phased Implementation Roadmap - Entropy AI

This roadmap outlines the phased development of the Entropy AI Desktop Agentic Operating System, structured in accordance with Agentic TDD and Markdown-First Architecture principles.

---


> **Durum notu (2026-09-07):** Faz 1-7 büyük ölçüde tamamlandı; kod tabanı bu plandan çok daha ileride (`tools/autonomous_agent_architecture_faz*.py` serisi 158. faza kadar gidiyor). Aşağıdaki kutular gerçek duruma göre güncellendi, açık kalan maddelerin gerekçesi yanlarında belirtildi.

## Phase 1: Foundation, Specifications & Project Scaffolding
- [x] Project architecture blueprint and directory layout
- [x] Specification documents (`SYSTEM_ARCHITECTURE.md`, `UI_SPECIFICATION.md`, `MEMORY_RAG_SPECIFICATION.md`, `AGY_CLI_INTEGRATION.md`, `TASK_SCHEDULER_SPECIFICATION.md`)
- [x] `GEMINI.md`, `AGENTS.md`, and persona files (`Agents/EntropyAI/persona.md`)
- [x] Python project environment scaffolding (`pyproject.toml` or `requirements.txt`, directory trees)

## Phase 2: Core Engine & AGY CLI Non-Blocking Bridge
- [x] Subprocess / `QProcess` asynchronous wrapper for `agy`
- [x] Real-time stdout/stderr stream parsing with Qt signal dispatch
- [x] Dynamic model detection parser (guaranteeing compliance with `agent-ui-models.md`)
- [x] Context window sliding buffer & message summarizer
- [x] Automated test suite: `tests/test_agy_bridge.py`

## Phase 3: PySide6 Desktop GUI - Tri-Modal Shell
- [x] Mode 1: Zen Mode (Borderless fullscreen window, split terminal, reports reader, knowledge graph view)
- [x] Mode 2: Floating Mode (Minimalist glowing particle core orb, always-on-top, right-click menu)
- [x] Mode 3: Chat Mode (Floating dialog, collapsible terminal drawer, real-time message bubbles)
- [x] CoreVisualizerWidget (Dynamic glowing/pulsing linked directly to streaming token chunks)
- [x] Multimodal clipboard handler (`Ctrl+C` / `Ctrl+V` image paste detection and local cache staging)
- [x] Automated test suite: `tests/test_ui_modes.py`

## Phase 4: Hybrid Cognitive Memory & RAG Engine
- [x] Obsidian Vault Manager (Read/Write markdown, daily notes, wikilink parsing)
- [ ] Supabase pgvector client & schema initialization — **yapılmadı**: bilişsel bellek yerel SQLite üzerinde çalışıyor (`memory/supabase/cognitive_memory.py`); `supabase` paketi hiç içe aktarılmıyor.
- [x] Mem0 12-layer cognitive components (Surprise filter, Ebbinghaus decay, Dreaming/Consolidation) — SQLite tabanlı
- [x] Project Codebase Indexer & local vector search
- [x] Automated test suite — `tests/test_memory.py` ve `tests/test_memory_inspector_and_rag.py` (dosya adı plandakinden farklı)

## Phase 5: MCP Hub & Dynamic Self-Tooling Engine
- [x] MCP Server Manager (Wrapping `agy mcp list`, `enable`, `disable`, `add`)
- [ ] StitchMCP integration bridge for on-the-fly UI generation — **yapılmadı**: `mcp/manager.py` yalnızca araç kataloğunda tanıtıyor, köprü yok.
- [x] Pydantic AI dynamic tool synthesis, validation, and sandboxed test execution
- [x] Automated test suite: `tests/test_mcp_and_tools.py`

## Phase 6: Scheduler & Windows System Integration
- [x] Minutely, hourly, daily, weekly background task scheduler
- [x] Windows Startup auto-launch integration (`shell:startup` / Registry `HKCU\Run`)
- [x] System tray icon and global hotkeys
- [x] Automated test suite: `tests/test_scheduler.py`

## Phase 7: System Integration, E2E Verification & Packaging
- [x] End-to-end integration tests verifying all 3 modes and AGY workflows
- [ ] User walkthrough and visual verification — manuel adım, kayıt altına alınmadı.
- [x] Self-contained executable / startup script launcher
