"""
Unit tests for Faz 81 Autonomous Agent Architecture.
Validates:
1. MultiAgentChoreographyEngine (Hierarchical dispatch, Blackboard sharing, and Market Auction).
2. BinaryQuantizationRetrievalSimulator (1-bit BQ bitpacking, POPCNT Hamming distance, two-stage cosine rerank, and RAM footprint).
3. CircuitBreakerEngine (3x duplicate calls, alternating oscillations [A, B, A, B, A, B], and reflection injection).
4. Faz81MasterAutonomousSystem (E2E autonomous sprint integration with token physics, desk leasing, and multi-agent coordination).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    MultiAgentChoreographyEngine,
    BinaryQuantizationRetrievalSimulator,
    CircuitBreakerEngine,
    CircuitBreakerStatus,
    Faz81MasterAutonomousSystem
)


def test_faz81_choreography_and_market_auction():
    engine = MultiAgentChoreographyEngine()
    engine.register_worker("coder_fast", "Fast Coder", ["code_synth", "ast_check"], token_cost_weight=0.9)
    engine.register_worker("coder_deep", "Deep Coder", ["code_synth", "formal_verify"], token_cost_weight=1.8)

    # 1. Hierarchical dispatch
    subtasks = [
        {"subtask_id": "st_1", "title": "Implement core logic", "required_capability": "code_synth"},
        {"subtask_id": "st_2", "title": "Formal verification", "required_capability": "formal_verify"}
    ]
    dispatched = engine.dispatch_hierarchical(task_id="proj_faz81", goal="Build Feature", subtasks=subtasks)
    assert len(dispatched) == 2
    assert dispatched[0]["assigned_agent"] == "coder_fast"
    assert dispatched[1]["assigned_agent"] == "coder_deep"

    # 2. Market auction
    auction_res = engine.run_market_auction(task_id="task_opt", complexity_score=8.0, required_capability="code_synth")
    assert auction_res["status"] == "AWARDED"
    # coder_fast has lower token_cost_weight (0.9 vs 1.8)
    assert auction_res["winner"] == "coder_fast"
    assert auction_res["winning_bid"] < 15.0


def test_faz81_binary_quantization_two_stage_retrieval():
    sim = BinaryQuantizationRetrievalSimulator(dimension=8)

    # Index 3 vectors
    doc1_vec = [1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0]
    doc2_vec = [-1.0, -1.0, 1.0, 1.0, 1.0, 1.0, -1.0, -1.0]
    doc3_vec = [-1.0, -1.0, -1.0, -1.0, 1.0, 1.0, 1.0, 1.0]

    sim.insert_vector("doc1_target", doc1_vec, {"tag": "target"})
    sim.insert_vector("doc2_mixed", doc2_vec, {"tag": "mixed"})
    sim.insert_vector("doc3_inverse", doc3_vec, {"tag": "inverse"})

    query = [0.9, 0.9, 0.8, 0.7, -0.5, -0.6, -0.7, -0.8]
    res = sim.two_stage_retrieve(query, candidate_pool_size=3, top_k=2)

    assert res["total_indexed"] == 3
    assert res["top_k_returned"] == 2
    assert res["results"][0]["doc_id"] == "doc1_target"
    assert res["results"][0]["cosine_similarity"] > 0.95
    assert res["results"][0]["hamming_distance"] == 0

    footprint = sim.calculate_quantization_footprint()
    assert footprint["ram_reduction_factor"] == 32.0
    assert footprint["compression_savings_pct"] > 95.0


def test_faz81_circuit_breaker_protection():
    cb = CircuitBreakerEngine(max_identical_actions=3, max_steps_per_turn=10)

    # 1. Normal calls
    res1 = cb.record_action("read_file", {"path": "a.py"})
    assert res1["status"] in ["NORMAL", CircuitBreakerStatus.NORMAL, "normal"]
    res2 = cb.record_action("read_file", {"path": "a.py"})
    assert res2["status"] in ["WARNING", CircuitBreakerStatus.WARNING, "warning"]

    # 3rd identical call triggers circuit breaker
    res3 = cb.record_action("read_file", {"path": "a.py"})
    assert res3["status"] in ["TRIPPED", CircuitBreakerStatus.TRIPPED, "tripped"]
    assert "loop detected" in res3["tripped_reason"].lower()

    # 2. Alternating oscillation [A, B, A, B, A, B]
    cb2 = CircuitBreakerEngine()
    for _ in range(2):
        cb2.record_action("tool_a", {"x": 1})
        cb2.record_action("tool_b", {"y": 2})
    cb2.record_action("tool_a", {"x": 1})
    osc_res = cb2.record_action("tool_b", {"y": 2})
    assert osc_res["status"] in ["TRIPPED", CircuitBreakerStatus.TRIPPED, "tripped"]
    assert "oscillation" in osc_res["tripped_reason"].lower()


def test_faz81_master_autonomous_project_sprint_e2e():
    system = Faz81MasterAutonomousSystem(embedding_dim=8)

    project_id = "faz81_sprint_001"
    goal = "Execute Faz 81 Autonomous Engineering sprint with 1-bit BQ and CodeAct"
    subtasks = [
        {"subtask_id": "st_1", "title": "Build CodeAct Runner", "required_capability": "python_codeact"},
        {"subtask_id": "st_2", "title": "Verify AST", "required_capability": "ast_validation"}
    ]

    prompt_tokens = [
        "EntropyAI", "MasterOrchestrator", "Faz81", "SystemDirective:",
        "TaskIsState", "AgentIsCompute", "SpecIsDurable", "CodeIsEphemeral",
        "RadixAttentionAnchored", "CodeActASTVerified", "A2Av1_0Compliant"
    ]
    codeact_script = """
items = [10, 25, 50, 75, 100]
filtered = [x * 3 for x in items if x >= 25]
result = {"tripled": filtered, "count": len(filtered)}
"""
    query_vec = [1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0]
    memory_vecs = [
        ("mem_faz81", [1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0], {"topic": "faz81_doctrine"}),
        ("mem_legacy", [-1.0, -1.0, 1.0, 1.0, -1.0, -1.0, 1.0, 1.0], {"topic": "legacy_prompting"})
    ]

    sprint_res = system.execute_autonomous_project_sprint(
        project_id=project_id,
        goal=goal,
        subtask_specs=subtasks,
        incoming_prompt_tokens=prompt_tokens,
        codeact_script=codeact_script,
        query_vector=query_vec,
        memory_vectors=memory_vecs
    )

    assert sprint_res["project_id"] == project_id
    assert sprint_res["phase"] == "Faz 81"
    assert sprint_res["status"] == "COMPLETED_AND_VERIFIED"
    assert sprint_res["radix_cache"]["cached_tokens_hit"] >= 6
    assert sprint_res["two_stage_retrieval"]["top_k_returned"] > 0
    assert sprint_res["two_stage_retrieval"]["results"][0]["doc_id"] == "mem_faz81"
    assert sprint_res["binary_quantization_footprint"]["ram_reduction_factor"] == 32.0
    assert len(sprint_res["multi_agent_dispatches"]) == 2
    assert sprint_res["codeact_execution"]["status"] == "SUCCESS"
    assert sprint_res["codeact_execution"]["output"] == {"tripled": [75, 150, 225, 300], "count": 4}
    assert sprint_res["token_economics"]["tokens_saved"] > 45000
    assert sprint_res["commit_status"] == "COMMITTED"
