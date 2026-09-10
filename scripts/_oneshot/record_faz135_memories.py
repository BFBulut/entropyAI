"""
Script to inject Faz 135 Research Findings into Entropy AI's Cognitive Memory System (SQLite & 384-d dense embeddings).
"""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem

def main():
    mem = CognitiveMemorySystem()
    memories = [
        (
            "semantic",
            "Actor Model & Multi-Agent Swarm Orchestrator (Faz 135): The 2026 production standard combining OpenAI Agents SDK and AutoGen 0.4 Actor Runtime. Decoupled agents as independent asynchronous actors with mailbox queues and location transparency. Dual-delegation paradigms: Agents-as-Tools (orchestrator retains conversational control and invokes specialists) versus Direct Handoffs (triage agent switches active context cleanly to expert subagent). Erlang-OTP supervision trees with One-For-One, One-For-All, and Rest-For-One restart policies with exponential failure backoff.",
            0.99,
            {"source": "research_2026_phase135", "standard": "ActorModel_Handoffs_AutoGen04_Faz135"}
        ),
        (
            "procedural",
            "Exokernel Agent Harness 2.5 & The Harness Effect: The foundational shift from prompt engineering to harness engineering in 2026. Frontier models alone plateau at 15-25% task completion on SWE-bench Verified; deterministically wrapped in an Exokernel Harness featuring AST Preflight Guard 20.0 (blocking eval, exec, ctypes, subprocess injection), Merkle Checkpoint Forest for transactional rollback, dynamic temperature cooling (T -> 0.0), and Phi-Accrual circuit breakers, success jumps to 85-88%+ ('The Harness Effect').",
            0.99,
            {"source": "research_2026_phase135", "standard": "Exokernel_Harness_v25"}
        ),
        (
            "procedural",
            "Agent Desks 17.0 & Ephemeral Micro-Worktrees: Multi-office workspace isolation (Architecture, Engineering, Verification/QA, Research, Security, Product) on ephemeral Git Worktrees sharing `.git` objects without disk duplication. Multi-Granular Single-Writer Boundary (MG-SWB 6.0) dynamic leases with vector clocks, Linda Distributed Tuple Space 12.0 (out, rd, in_tuple, watch, eval) for zero-token in-memory reactive coordination, and 5-Way AST Semantic Conflict-Free Reconciler.",
            0.98,
            {"source": "research_2026_phase135", "standard": "AgentDesks_170_Linda12"}
        ),
        (
            "semantic",
            "Kahn DAG Wavefront Scheduler & CPM Slack Borrowing with Stochastic PERT: Tasks modeled as independent FSM state contracts (UNASSIGNED -> ACQUIRED -> IN_PROGRESS -> VERIFYING -> COMPLETED). Forward and backward passes compute early/late starts and Slack = LS - ES. Stochastic PERT duration Te = (O + 4M + P) / 6. Top-tier reasoning models (Claude 3.7 Thinking / Gemini 3 Pro) are strictly reserved for Critical Path (Slack = 0), while Slack Borrowing routes non-critical tasks to high-throughput cost-effective models (Gemini 3.8 Flash) with zero impact on delivery deadline.",
            0.99,
            {"source": "research_2026_phase135", "standard": "KahnDAG_CPM_SlackBorrowing_PERT"}
        ),
        (
            "semantic",
            "Dotriaconta-Store 32-Layer Cognitive Memory Architecture & Advanced GraphRAG: Graphiti 2.5 bi-temporal edge validity intervals (valid_from / valid_until) for non-destructive belief revision and time-travel querying, HippoRAG 2 dual-node Personalized PageRank (PPR) for associative multi-hop retrieval (10x faster, 80% cheaper than LLM multi-hop reasoning), Jina AI Late Chunking preserving full-context self-attention before mean pooling, Ebbinghaus forgetting decay with Dreaming sleep consolidation, Supabase pgvector HNSW halfvec (FP16) and sparsevec hybrid RRF search, and Mem0 passive extraction combined with Letta OS memory paging.",
            0.99,
            {"source": "research_2026_phase135", "standard": "DotriacontaStore_32_GraphRAG"}
        ),
        (
            "semantic",
            "Extreme Token Physics 26.0 & CodeAct 19.0 REPL Paradigm: Collapses multi-turn JSON tool calls into a single executable Python script (CodeAct REPL), saving 75-85% tokens and reducing latency by 50%+. Pruning source code into AST skeletons (signatures and docstrings with pass) cuts token usage by 85-92%. Radix KV-Cache block alignment (64/128/256 tokens) achieves >94% cache hit rate on Claude Prompt Caching and Gemini Context Caching. Marginal Delta Token Accounting (Delta = max(0, Uk - Uk-1)) prevents multi-turn billing distortions.",
            0.98,
            {"source": "research_2026_phase135", "standard": "TokenPhysics_260_CodeAct19"}
        ),
        (
            "procedural",
            "Skill Progressive Disclosure (SKILL.md 3-Level Architecture v4.5): Tier 1 Discovery exposes minimal YAML metadata (~80 tokens), Tier 2 Activation loads procedural Markdown instructions strictly on semantic demand, and Tier 3 Execution runs sandboxed scripts and reference code during tool invocation, eliminating context window pollution.",
            0.97,
            {"source": "research_2026_phase135", "standard": "ProgressiveSkills_45"}
        ),
        (
            "semantic",
            "FastMCP 10.5++ Gateway & AAIF A2A Protocol v1.5: Dual-standard integration combining FastMCP 10.5++ (stateless HTTP header routing, MRTR 206 input_required, shm:// and blob:// zero-copy frame pointers, ETag 304 caching with volatility decay, Zero-Shot Attenuation v15 saving >98% tokens, Two-Phase Saga compensations, and reactive resource watchers) and AAIF A2A Protocol v1.5 (HMAC-SHA256 signed Agent Cards, 4D Pareto multi-objective routing, and 3-Phase PBFT consensus).",
            0.98,
            {"source": "research_2026_phase135", "standard": "FastMCP105_AAIF_A2A_v15"}
        ),
        (
            "semantic",
            "Markdown-First Autonomous Architecture & 2026 Frontier Ecosystem: Standardized root specification files (GEMINI.md, AGENTS.md, CLAUDE.md, task.md) provide transparent, version-controlled ground truth for multi-agent systems, replacing opaque proprietary configs with inspectable, auditable declarative contracts; supported by Claude 3.7 Sonnet / Opus 4.6 Thinking, Gemini 2.5/3.1 Pro & 3.8 Flash, DeepSeek R1/V3, LangGraph, CrewAI, AutoGen 0.4 / AG2, OpenHands, Letta, Aider, and FastMCP.",
            0.97,
            {"source": "research_2026_phase135", "standard": "MarkdownFirst_2026_Faz135"}
        )
    ]

    count = 0
    for cat, content, imp, meta in memories:
        node, is_novel = mem.record_memory(
            category=cat,
            content=content,
            importance=imp,
            metadata=meta
        )
        count += 1
        print(f"[OK] Stored [{node.category}] {node.id}: Novel={is_novel}, Importance={node.importance} ({meta.get('standard')})")

    print(f"\nSuccessfully stored {count} Faz 135 memories into CognitiveMemorySystem.")

if __name__ == "__main__":
    main()
