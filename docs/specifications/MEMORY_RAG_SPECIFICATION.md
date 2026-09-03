## 1. Cognitive Architecture Overview

Following the research report on Desktop Agent Operating Systems, Entropy AI incorporates a 12-layer cognitive hierarchy combining:
1. **Obsidian Markdown Vault** (Local, offline, transparent, human-readable exocortex).
2. **Supabase pgvector & Mem0 (via agy Supabase MCP)** with a local SQLite-vec fallback ensuring zero-API configuration and 100% offline resilience.

```text
+-------------------------------------------------------------------------------+
| Layer 12: EGO & IDENTITY (Agents/EntropyAI/persona.md + Long-term Directives)  |
+-------------------------------------------------------------------------------+
| Layer 6:  DREAMING / CONSOLIDATION (Background clustering & summarization)    |
+-------------------------------------------------------------------------------+
| Layer 5:  FORGETTING CURVE (Ebbinghaus temporal decay via access frequency)   |
+-------------------------------------------------------------------------------+
| Layer 2:  SURPRISE & NOVELTY FILTER (High threshold for novel memory storage) |
+-------------------------------------------------------------------------------+
| Layer 1:  WORKING CONTEXT (Active turn buffer, sliding message window)        |
+-------------------------------------------------------------------------------+
```

---

## 2. Obsidian Integration

- **Vault Location**: `C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault`
- **File Structure**:
  - `Entropy/MEMORY.md`: High-level system beliefs, learned lessons, user preferences.
  - `Entropy/DailyNotes/YYYY-MM-DD.md`: Chronological log of agent actions, decisions, and outcomes.
  - `Entropy/Projects/<ProjectName>.md`: Architectural insights, key dependencies, and task states for monitored projects.
  - `Entropy/Reports/`: Detailed research dossiers generated during Zen Mode deep dives.
- **Wikilink Graph Support**: Automatically links concepts with `[[Wikilinks]]` so Obsidian's native Graph View visualizes agent reasoning.

---

## 3. Supabase pgvector Integration

- **Schema Definition**:
  ```sql
  create extension if not exists vector;

  create table entropy_memories (
      id uuid primary key default gen_random_uuid(),
      category text not null check (category in ('episodic', 'semantic', 'procedural')),
      content text not null,
      embedding vector(1536),
      importance float default 0.5,
      access_count int default 0,
      last_accessed_at timestamptz default now(),
      created_at timestamptz default now(),
      metadata jsonb default '{}'::jsonb
  );

  create index on entropy_memories using ivfflat (embedding vector_cosine_ops);
  ```

- **Hybrid Recollection Engine**:
  $$\text{FinalScore}(m) = 0.50 \times \text{CosineSim}(q, m) + 0.30 \times m.\text{importance} + 0.20 \times \exp(-\lambda \Delta t)$$
  This guarantees that recent, critical facts naturally take precedence over stale, conflicting data.
