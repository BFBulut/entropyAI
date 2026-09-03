# AGENTS.md - Agent Registry and Protocol

This document defines the agent personas, system identities, and execution protocol within Entropy AI.

---

## Registered Agents

### 1. Entropy AI (Master Orchestrator / Companion)
- **Role**: Primary Autonomous Agent, Desktop OS Controller, Pair Programmer & Researcher.
- **Persona Path**: `Agents/EntropyAI/persona.md`
- **Model Dynamic Target**: Inherited from AGY CLI configuration (e.g. Gemini 2.5 Pro, Claude 3.7 Sonnet, etc. via `agy`).
- **Permissions**: Full local workspace filesystem access within selected project directory, process spawning for `agy`, Obsidian memory vault access, Supabase memory management.

### 2. CodeArchitect Agent (Sub-Agent / Specialist)
- **Role**: Codebase indexing, static analysis, refactoring, and automated test synthesis.
- **Constraints**: Sandboxed to selected project root. Cannot perform network requests unless authorized.

### 3. MemoryConsolidator (Background Dreaming Agent)
- **Role**: Periodically analyzes episodic memories, computes importance scores, applies Ebbinghaus forgetting curves, and compiles permanent semantic notes into Obsidian & Supabase.
- **Trigger**: Runs during idle periods or scheduled via TaskScheduler.

---

## Agent Communication Protocol

All agents interact through standardized JSON-RPC or Markdown message artifacts.
- State handoffs use structured markdown artifacts (`task.md`, `session_log.md`).
- Real-time events are dispatched across the PySide6 Event Bus via typed signals (`on_agent_started`, `on_agent_token_chunk`, `on_agent_completed`).
