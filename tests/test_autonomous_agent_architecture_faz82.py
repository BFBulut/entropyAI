"""
Unit tests for Faz 82 Autonomous Agent Architecture.
Validates:
1. Hypergraph RAG Engine (n-ary non-decomposable relations & incidence scoring).
2. MCP Apps and Durable Tasks (July 2026 specification).
3. Practical Byzantine Swarm Consensus (pBFT fault-tolerant multi-agent quorum).
4. End-to-end Faz 82 Master Autonomous System execution with Ephemeral Desks and AST Pre-Flight Shield.
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    HypergraphRAGEngine,
    Hyperedge,
    MCPAppsAndTasksRegistry,
    PracticalByzantineSwarmConsensus,
    Faz82MasterAutonomousSystem
)


def test_hypergraph_rag_engine():
    engine = HypergraphRAGEngine()

    # Test adding valid hyperedge
    e1 = engine.add_hyperedge(
        hyperedge_id="edge_compiler",
        nodes={"Agent:Coder", "Tool:FastMCP", "File:parser.py", "State:Success"},
        weight=1.5,
        attributes={"domain": "AST"}
    )
    assert e1.hyperedge_id == "edge_compiler"
    assert len(e1.nodes) == 4

    e2 = engine.add_hyperedge(
        hyperedge_id="edge_tester",
        nodes={"Agent:Tester", "Tool:PytestRunner", "File:test_parser.py", "State:Success"},
        weight=1.0
    )

    # Test invalid hyperedge (< 2 nodes)
    with pytest.raises(ValueError):
        engine.add_hyperedge("invalid_edge", {"SingleNode"})

    # Test higher-order query
    results = engine.query_higher_order(query_nodes={"Agent:Coder", "Tool:FastMCP"}, top_k=2)
    assert len(results) >= 1
    top_hit = results[0]
    assert top_hit["hyperedge_id"] == "edge_compiler"
    assert top_hit["score"] > 0.0
    assert "Tool:FastMCP" in top_hit["nodes"]

    summary = engine.get_incidence_matrix_summary()
    assert summary["total_nodes"] == 7
    assert summary["total_hyperedges"] == 2
    assert summary["avg_hyperedge_cardinality"] == 4.0


def test_mcp_apps_and_durable_tasks():
    registry = MCPAppsAndTasksRegistry()

    # 1. MCP App Registration
    app = registry.register_mcp_app(
        app_id="app_diff_review",
        title="Interactive Diff Hunk Reviewer",
        component_type="diff_viewer",
        schema={"allow_inline_edits": True, "syntax_highlighting": "python"}
    )
    assert app.app_id == "app_diff_review"
    assert "app_diff_review" in registry.apps

    # 2. MCP Durable Task Lifecycle
    task = registry.create_durable_task(
        task_id="task_refactor_core",
        goal="Refactor routing tables to async fastmcp",
        runner_agent="lead_synthesizer"
    )
    assert task.status == "PENDING"

    # Update progress
    res_update = registry.update_task_progress(
        task_id="task_refactor_core",
        progress=45.0,
        status="RUNNING",
        checkpoint_data={"active_file": "router.py", "lines_modified": 120}
    )
    assert res_update["status"] == "RUNNING"
    assert res_update["progress"] == 45.0
    assert res_update["total_checkpoints"] == 1

    # Mid-flight input injection
    res_inject = registry.inject_mid_flight_input(
        task_id="task_refactor_core",
        sender="human_supervisor",
        feedback="Ensure backward compatibility with ACP v1.0 clients."
    )
    assert res_inject["injected"] is True
    assert res_inject["feedback_count"] == 1
    assert registry.tasks["task_refactor_core"].mid_flight_inputs[0]["feedback"] == "Ensure backward compatibility with ACP v1.0 clients."


def test_practical_byzantine_swarm_consensus():
    swarm = ["agent_alpha", "agent_beta", "agent_gamma", "agent_delta"]
    consensus = PracticalByzantineSwarmConsensus(agent_nodes=swarm, max_faulty=1)
    assert consensus.quorum_threshold == 3  # 2f + 1 = 3

    round_id = "round_pr_402"
    diff_patch = "--- a/core.py\n+++ b/core.py\n@@ -1 +1 @@\n-old\n+new"
    spec = "Update core engine to Faz 82"

    proposal = consensus.initiate_proposal(round_id, leader="agent_alpha", diff_patch=diff_patch, specification=spec)
    digest = proposal["digest"]
    assert proposal["state"] == "PRE_PREPARE"

    # First vote (valid)
    v1 = consensus.submit_prepare_vote(round_id, "agent_beta", computed_digest=digest, ast_valid=True, tests_pass=True)
    assert v1["valid_prepares"] == 2  # leader + beta

    # Second vote (valid) -> triggers COMMIT state
    v2 = consensus.submit_prepare_vote(round_id, "agent_gamma", computed_digest=digest, ast_valid=True, tests_pass=True)
    assert v2["valid_prepares"] == 3
    assert v2["state"] == "COMMIT"

    # Commit phase
    c1 = consensus.submit_commit_vote(round_id, "agent_alpha", "sig_alpha")
    c2 = consensus.submit_commit_vote(round_id, "agent_beta", "sig_beta")
    c3 = consensus.submit_commit_vote(round_id, "agent_gamma", "sig_gamma")
    assert c3["state"] == "FINALIZED"
    assert c3["verdict"] == "ACCEPTED"


def test_faz82_master_autonomous_system_e2e():
    system = Faz82MasterAutonomousSystem(embedding_dim=8)

    cycle_id = "faz82_sprint_001"
    goal = "Synthesize and verify fault-tolerant MCP App router"
    spec = "Must include Hypergraph incidence scoring and pBFT consensus."

    candidate_code = '''
def calculate_hypergraph_incidence(e_cardinality: int, q_cardinality: int, intersection: int) -> float:
    import math
    if e_cardinality == 0 or q_cardinality == 0:
        return 0.0
    return intersection / math.sqrt(e_cardinality * q_cardinality)
'''

    query_concepts = {"Pattern:HarnessEngineering", "Protocol:MCP", "Protocol:pBFT"}
    query_vector = [0.8, -0.5, 0.3, -0.1, 0.9, -0.2, 0.4, -0.7]

    memory_vectors = [
        ("doc_1", [0.7, -0.4, 0.2, -0.1, 0.8, -0.2, 0.3, -0.6], {"title": "Harness Engineering Spec"}),
        ("doc_2", [-0.8, 0.5, -0.3, 0.1, -0.9, 0.2, -0.4, 0.7], {"title": "Legacy Monolith Document"})
    ]

    result = system.execute_faz82_autonomous_cycle(
        cycle_id=cycle_id,
        goal=goal,
        candidate_code=candidate_code,
        specification=spec,
        query_concepts=query_concepts,
        query_vector=query_vector,
        memory_vectors=memory_vectors
    )

    assert result["status"] == "SUCCESS_CONSENSUS_VERIFIED"
    assert result["consensus_verdict"] == "ACCEPTED"
    assert result["ast_validation"]["valid"] is True
    assert result["mcp_task_status"] == "COMPLETED"
    assert len(result["hypergraph_retrieval"]) >= 1
    assert result["bq_retrieval"]["results"][0]["doc_id"] == "doc_1"


def test_faz82_master_autonomous_system_ast_shield_fail():
    system = Faz82MasterAutonomousSystem(embedding_dim=8)

    broken_code = '''
def broken_syntax_function(:
    return 42
'''
    result = system.execute_faz82_autonomous_cycle(
        cycle_id="broken_cycle",
        goal="Fix bug",
        candidate_code=broken_code,
        specification="Should fail ast",
        query_concepts={"Protocol:MCP"},
        query_vector=[0.1] * 8,
        memory_vectors=[]
    )

    assert result["status"] == "AST_VALIDATION_FAILED"
    assert "SyntaxError" in result["error"]
    assert system.mcp_registry.tasks["broken_cycle"].status == "FAILED"
