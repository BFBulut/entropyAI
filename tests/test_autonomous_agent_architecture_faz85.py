"""
Unit tests for Faz 85 Autonomous Agent Architecture.
Validates:
1. AgentDeskLifecycleManager (Git worktree isolation, dynamic port allocation, test-gated merge & rollback sentinel).
2. LateChunkingHippoRAGFusion (Context-preserving embedding & ICML 2025 HippoRAG 2 PPR multi-hop associative retrieval).
3. FastMCP2026ProtocolEngine (MCP Apps interactive UI schemas, MCP Tasks durable async handles, MCP Sampling reverse inference).
4. RadixAttentionCacheBlendSimulator (SGLang Radix prefix tree, non-contiguous CacheBlend & TTFT speedup).
5. Faz85MasterAutonomousSystem (End-to-end unified autonomous cycle with 100% integrity).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    AgentDeskLifecycleManager,
    LateChunkingHippoRAGFusion,
    FastMCP2026ProtocolEngine,
    RadixAttentionCacheBlendSimulator,
    Faz85MasterAutonomousSystem
)


def test_agent_desk_lifecycle_manager():
    manager = AgentDeskLifecycleManager(base_worktree_dir="desks", base_port=4000)

    # 1. Allocate Desk
    desk = manager.allocate_desk(
        desk_id="auth_worker",
        agent_id="agent_architect",
        branch_name="agent/auth_refactor",
        requested_ports=2
    )
    assert desk["desk_id"] == "auth_worker"
    assert desk["desk_path"] == "desks/desk_auth_worker"
    assert len(desk["allocated_ports"]) == 2
    assert desk["allocated_ports"] == [4001, 4002]
    assert desk["isolated_db_schema"] == "schema_desk_auth_worker"
    assert "git worktree add" in desk["git_worktree_command"]

    # Prevent duplicate desk
    with pytest.raises(ValueError, match="already active"):
        manager.allocate_desk("auth_worker", "agent_2", "branch_2")

    # 2. Test-Gated Merge - PASS
    merge_pass = manager.execute_test_gated_merge(
        desk_id="auth_worker",
        mock_pass=True
    )
    assert merge_pass["status"] == "MERGE_APPROVED"
    assert merge_pass["tests_passed"] is True
    assert "git merge" in merge_pass["merge_command"]
    assert "auth_worker" not in manager.active_desks
    assert len(manager.allocated_ports) == 0

    # 3. Test-Gated Merge - FAIL (Rollback Sentinel)
    desk_fail = manager.allocate_desk(
        desk_id="failing_worker",
        agent_id="agent_junior",
        branch_name="agent/failing_experiment",
        requested_ports=1
    )
    assert 4001 in manager.allocated_ports

    merge_fail = manager.execute_test_gated_merge(
        desk_id="failing_worker",
        mock_pass=False
    )
    assert merge_fail["status"] == "ROLLBACK_EXECUTED"
    assert merge_fail["tests_passed"] is False
    assert "git worktree remove --force" in merge_fail["rollback_command"]
    assert "failing_worker" not in manager.active_desks
    assert len(manager.allocated_ports) == 0


def test_late_chunking_hipporag2_fusion():
    doc = (
        "Entropy AI is an autonomous Agentic Operating System designed for Google Antigravity. "
        "The cognitive memory layer integrates Obsidian Markdown exocortex and Supabase pgvector. "
        "HippoRAG 2 provides neurobiological multi-hop associative retrieval using Personalized PageRank. "
        "Late chunking embeds long documents globally before pooling to eliminate context cliff."
    )

    # 1. Late Chunking
    late_chunk_result = LateChunkingHippoRAGFusion.embed_with_late_chunking(
        document_text=doc,
        chunk_token_size=15,
        overlap_tokens=5
    )
    assert late_chunk_result["chunk_count"] >= 2
    assert late_chunk_result["method"] == "LATE_CHUNKING_GLOBAL_POOLING"
    for chunk in late_chunk_result["chunks"]:
        assert len(chunk["embedding"]) == 8
        assert chunk["has_global_context_anchor"] is True

    # 2. HippoRAG 2 Fusion with PPR
    triples = [
        ("Entropy AI", "operates_with", "Google Antigravity"),
        ("Entropy AI", "possesses", "cognitive memory"),
        ("cognitive memory", "integrates", "Obsidian Markdown"),
        ("cognitive memory", "integrates", "Supabase pgvector"),
        ("HippoRAG 2", "uses", "Personalized PageRank"),
        ("cognitive memory", "deploys", "HippoRAG 2")
    ]

    fusion = LateChunkingHippoRAGFusion.fuse_with_hipporag2(
        chunks=late_chunk_result["chunks"],
        openie_triples=triples,
        seed_concept="HippoRAG 2",
        damping=0.85,
        max_iter=10
    )
    assert fusion["retrieval_mode"] == "HIPPOCAMPAL_PPR_ASSOCIATIVE"
    assert fusion["total_graph_nodes"] > 0
    assert len(fusion["ranked_chunks"]) > 0
    assert fusion["top_chunk_id"] is not None


def test_fastmcp_2026_protocol_engine():
    engine = FastMCP2026ProtocolEngine()

    # 1. MCP App Schema
    app = engine.generate_mcp_app_schema(
        app_id="agent_control_panel",
        title="Agent Desks Cockpit",
        component_type="metrics_dashboard",
        state_bindings={"active_desks": 3, "memory_sync": "OK"}
    )
    assert app["mcp_app_version"] == "2026-04"
    assert app["render_target"] == "desktop_webview_dock"
    assert "on_submit" in app["event_handlers"]

    # 2. Durable MCP Task
    task = engine.create_durable_mcp_task(
        task_id="task_9918",
        description="Background dreaming consolidation",
        timeout_seconds=7200
    )
    assert task["task_id"] == "task_9918"
    assert task["status"] == "RUNNING"
    assert len(task["resumption_token"]) == 64
    assert "mcp://tasks/task_9918/events" == task["streaming_endpoint"]

    # 3. Reverse MCP Sampling
    sampling = engine.execute_reverse_sampling_request(
        server_id="supabase_mcp",
        prompt="Verify schema migration for pgvector 0.8",
        target_schema={"type": "object", "properties": {"approved": {"type": "boolean"}}}
    )
    assert sampling["jsonrpc"] == "2.0"
    assert sampling["method"] == "sampling/createMessage"
    assert sampling["params"]["server_id"] == "supabase_mcp"


def test_radix_attention_cache_blend():
    simulator = RadixAttentionCacheBlendSimulator()

    # 1. Register prefixes
    sim_sys = simulator.register_prefix(
        node_id="base_system",
        parent_id="root",
        tokens=["You", "are", "Entropy", "AI"]
    )
    assert sim_sys["status"] == "RADIX_PREFIX_CACHED"

    sim_tools = simulator.register_prefix(
        node_id="base_tools",
        parent_id="base_system",
        tokens=["Tools:", "view_window", "replace_content", "test_runner"]
    )
    assert sim_tools["cached_tokens"] == 4

    # 2. Blend Cache Segments
    blend = simulator.blend_cache_segments(
        system_node_id="base_system",
        tools_node_id="base_tools",
        dynamic_query_tokens=2
    )
    assert blend["blend_status"] == "CACHE_BLEND_SUCCESS"
    assert blend["cached_prefix_tokens"] == 8
    assert blend["dynamic_query_tokens"] == 2
    assert blend["cache_hit_ratio_pct"] == 80.0
    assert blend["ttft_speedup_factor"] == "5.0x"


def test_faz85_master_autonomous_system_cycle():
    system = Faz85MasterAutonomousSystem(embedding_dim=1536)

    cycle_id = "test_cycle_faz85"
    goal = "Implement ephemeral agent desks with late chunking RAG memory."
    source_code = "def sample_worker():\n    return 'hello world'\n"
    sys_instructions = "You are Entropy AI, an autonomous software engineering companion."
    rules = "1. Verify AST before write. 2. Delta token accounting is mandatory."
    history = [
        {"role": "user", "content": "Initialize autonomous cycle."},
        {"role": "assistant", "content": "Initializing desks and RAG memory."}
    ]
    doc = (
        "Entropy AI utilizes Agent Desks for workspace isolation with Git worktrees. "
        "Late chunking preserves cross-chunk context before pooling. "
        "Personalized PageRank traverses entity relations to retrieve associative knowledge."
    )
    triples = [
        ("Entropy AI", "utilizes", "Agent Desks"),
        ("Agent Desks", "provide", "workspace isolation"),
        ("Late chunking", "preserves", "cross-chunk context"),
        ("Personalized PageRank", "traverses", "entity relations")
    ]
    query_vec = [0.1] * 1536
    mem_vecs = [
        ("m1", [0.1] * 1536, {"importance": 0.9, "category": "semantic"}),
        ("m2", [0.05] * 1536, {"importance": 0.4, "category": "episodic"})
    ]

    result = system.execute_faz85_autonomous_cycle(
        cycle_id=cycle_id,
        goal=goal,
        source_code=source_code,
        system_instructions=sys_instructions,
        invariant_rules=rules,
        conversation_history=history,
        knowledge_doc=doc,
        openie_triples=triples,
        seed_concept="Agent Desks",
        query_vector=query_vec,
        memory_vectors=mem_vecs,
        delegate_to_agent="code-architect",
        simulate_test_pass=True
    )

    assert result["status"] == "FAZ85_AUTONOMOUS_CYCLE_COMPLETE"
    assert result["overall_integrity"] == "VERIFIED_100_PERCENT"
    assert result["agent_desk"]["merge_verification"]["status"] == "MERGE_APPROVED"
    assert result["cognitive_memory_fusion"]["late_chunking"]["chunk_count"] > 0
    assert result["fastmcp_2026"]["mcp_app"]["mcp_app_version"] == "2026-04"
    assert "x" in result["radix_cache_blend"]["ttft_speedup_factor"]
    assert result["faz84_metrics"]["status"] == "FAZ84_AUTONOMOUS_CYCLE_COMPLETE"
