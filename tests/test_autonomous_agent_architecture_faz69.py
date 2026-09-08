"""
Tests for Entropy AI - Autonomous Agent Architecture Core Engine (Faz 69)
Validates:
1. MultiAgentWorktreeOrchestrator (Agent Desks isolation, AST-verified patch generation, merge & GC).
2. DynamicToolSynthesizer (Pydantic-AI dynamic tool generation, AST verification, hazard filtering).
3. GrandProtocolRouter (ACP, A2A Artifact Passing, Stateless MCP Streamable HTTP).
4. AdvancedTokenPhysicsEngine (Context exhaustion failover trajectory, Tree-sitter compression, CodeAct filtering).
5. HippoRAG2NeurobiologicalEngine (Multi-hop PPR traversal, associative reasoning, Ebbinghaus decay).
6. SleepTimeDreamConsolidator (Shannon surprise filter, episodic to semantic promotion).
"""

from pathlib import Path
import pytest

from entropy.tools.autonomous_agent_architecture import (
    MultiAgentWorktreeOrchestrator,
    DynamicToolSynthesizer,
    GrandProtocolRouter,
    AdvancedTokenPhysicsEngine,
    HippoRAG2NeurobiologicalEngine,
    SleepTimeDreamConsolidator,
    ProtocolTransformers,
)


def test_multi_agent_worktree_orchestrator(tmp_path: Path):
    orchestrator = MultiAgentWorktreeOrchestrator(tmp_path)
    desk = orchestrator.spawn_worktree_desk("task-auth-01", branch="feature/auth", agent_id="agent-007")

    assert desk.name == "desk_task-auth-01"
    assert desk.branch == "feature/auth"
    assert desk.assigned_agent_id == "agent-007"
    assert desk.is_active is True

    # Generate patch with valid python code
    files = {
        "auth.py": "def authenticate(user: str, token: str) -> bool:\n    return user == 'admin' and bool(token)\n"
    }
    patch = orchestrator.generate_desk_patch("desk_task-auth-01", files, commit_message="Add auth function")
    assert patch["desk_name"] == "desk_task-auth-01"
    assert patch["ast_verified"] is True
    assert "checksum" in patch
    assert len(patch["checksum"]) == 64

    # Merge and GC
    success = orchestrator.merge_desk_worktree("desk_task-auth-01")
    assert success is True
    assert "desk_task-auth-01" not in orchestrator.active_patches


def test_multi_agent_worktree_orchestrator_ast_failure(tmp_path: Path):
    orchestrator = MultiAgentWorktreeOrchestrator(tmp_path)
    orchestrator.spawn_worktree_desk("task-broken-01")

    # Invalid python code syntax
    files = {"broken.py": "def foo(:\n return"}
    with pytest.raises(ValueError, match="AST verification failed"):
        orchestrator.generate_desk_patch("desk_task-broken-01", files)


def test_dynamic_tool_synthesizer_valid():
    res = DynamicToolSynthesizer.synthesize_tool(
        tool_name="calculate_var",
        docstring="Calculates Value at Risk given returns and alpha.",
        parameters={"returns": "list[float]", "alpha": "float"},
        code_body="import numpy as np\nreturn {'var': float(np.percentile(returns, 100 * alpha))}"
    )

    assert res["tool_name"] == "calculate_var"
    assert res["ast_verified"] is True
    assert "def calculate_var(returns: list[float], alpha: float) -> dict:" in res["source_code"]


def test_dynamic_tool_synthesizer_hazard():
    with pytest.raises(PermissionError, match="Hazardous pattern"):
        DynamicToolSynthesizer.synthesize_tool(
            tool_name="dangerous_tool",
            docstring="Performs dangerous call.",
            parameters={"cmd": "str"},
            code_body="import os\nos.system('rm -rf /')"
        )


def test_dynamic_tool_synthesizer_invalid_name():
    with pytest.raises(ValueError, match="Invalid tool identifier"):
        DynamicToolSynthesizer.synthesize_tool(
            tool_name="123_invalid_tool",
            docstring="Invalid name test.",
            parameters={},
            code_body="return {}"
        )


def test_grand_protocol_router_acp():
    payload = ProtocolTransformers.build_acp_message("session/prompt", {"text": "Run tests"}, msg_id=42)
    res = GrandProtocolRouter.route("acp", payload)

    assert res["protocol"] == "ACP"
    assert res["status"] == "ROUTED"
    assert res["method"] == "acp/session/prompt"
    assert res["client_id"] == 42


def test_grand_protocol_router_a2a():
    card = ProtocolTransformers.build_a2a_agent_card(
        agent_name="CodeArchitect",
        description="Autonomous static analysis agent",
        capabilities=["ast_parsing", "refactoring"],
        protocols=["A2A/2026", "MCP"]
    )
    res = GrandProtocolRouter.route("a2a", card)

    assert res["protocol"] == "A2A"
    assert res["status"] == "ROUTED"
    assert res["agent_card"] == "CodeArchitect"
    assert res["artifact_passing"] is True


def test_grand_protocol_router_stateless_mcp():
    mcp_req = ProtocolTransformers.build_stateless_mcp_request(
        tool_name="read_file",
        arguments={"path": "main.py"},
        trace_id="tr-12345",
        require_elicitation=True
    )
    res = GrandProtocolRouter.route("mcp", mcp_req)

    assert res["protocol"] == "Stateless-MCP"
    assert res["status"] == "ROUTED"
    assert res["trace_id"] == "tr-12345"
    assert res["stateless"] is True
    assert res["require_elicitation"] is True


def test_grand_protocol_router_unsupported():
    with pytest.raises(ValueError, match="Unsupported protocol"):
        GrandProtocolRouter.route("unknown_proto", {})


def test_advanced_token_physics_exhaustion_trajectory():
    res = AdvancedTokenPhysicsEngine.compute_exhaustion_trajectory(
        turns=20,
        context_limit=32000,
        system_prompt_tokens=4000,
        turn_input=1000,
        turn_output=500,
        failover_threshold=0.85
    )

    assert res["turns"] == 20
    assert res["context_limit"] == 32000
    assert res["failover_threshold_tokens"] == 27200
    assert res["requires_failover"] is True
    assert res["failover_turn"] is not None
    assert 10 <= res["failover_turn"] <= 20


def test_advanced_token_physics_repo_and_codeact():
    repo_res = AdvancedTokenPhysicsEngine.model_tree_sitter_repo_compression(
        total_lines=100000,
        avg_tokens_per_line=7.5,
        target_map_tokens=1000
    )
    assert repo_res["raw_tokens"] == 750000
    assert repo_res["savings_percent"] > 99.0
    assert repo_res["reduction_ratio"] == 750.0

    codeact_res = AdvancedTokenPhysicsEngine.model_codeact_filtering_savings(
        raw_dataset_tokens=500000,
        repl_script_tokens=35,
        filtered_result_tokens=20
    )
    assert codeact_res["saved_tokens"] == 500000 - 55
    assert codeact_res["savings_percent"] > 99.9
    assert codeact_res["efficiency_multiplier"] > 9000.0


def test_hipporag2_neurobiological_engine():
    engine = HippoRAG2NeurobiologicalEngine()
    triples = [
        ("EntropyAI", "utilizes", "AntigravityCLI"),
        ("AntigravityCLI", "executes", "AgentHarness"),
        ("AgentHarness", "manages", "AgentDesks"),
        ("AgentDesks", "leverages", "GitWorktree"),
        ("AgentHarness", "minimizes", "TokenPhysics")
    ]
    engine.add_triples(triples)

    query_res = engine.multi_hop_query(seed_entities=["EntropyAI"], damping=0.85, top_k=4)
    assert query_res["seeds"] == ["EntropyAI"]
    assert len(query_res["top_associations"]) > 0
    top_node = query_res["top_associations"][0]["node"]
    assert top_node in ["entropyai", "antigravitycli"]

    # Ebbinghaus memory decay
    raw_scores = {item["node"]: item["score"] for item in query_res["top_associations"]}
    decayed = engine.decay_memory_nodes(raw_scores, elapsed_hours=48.0, stability=24.0)
    for node, score in raw_scores.items():
        assert decayed[node] <= score


def test_sleep_time_dream_consolidator():
    vocab = {"antigravity": 0.5, "system": 0.4, "ok": 0.9}
    novel_log = "Quantum teleportation hyperdimensional manifold topological defect detected"
    routine_log = "system ok system ok"

    res = SleepTimeDreamConsolidator.consolidate_session(
        session_id="session-001",
        episodic_logs=[novel_log, routine_log],
        reference_vocab=vocab,
        surprise_threshold=4.0
    )

    assert len(res["promoted_to_semantic_memory"]) == 1
    assert res["promoted_to_semantic_memory"][0]["log"] == novel_log
    assert len(res["discarded_transient_logs"]) == 1
    assert res["discarded_transient_logs"][0]["log"] == routine_log
    assert res["promotion_rate"] == 0.5
