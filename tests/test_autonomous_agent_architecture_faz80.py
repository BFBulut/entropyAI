"""
Unit tests for Faz 80 Autonomous Agent Architecture.
Validates:
1. MultiAgentChoreographyEngine (Hierarchical dispatch, Blackboard sharing, and Market Auction).
2. BinaryQuantizationRetrievalSimulator (1-bit BQ bitpacking, POPCNT Hamming distance, two-stage cosine rerank, and RAM footprint).
3. Faz80MasterAutonomousSystem (E2E autonomous sprint integration with token physics, desk leasing, and multi-agent coordination).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    MultiAgentChoreographyEngine,
    BinaryQuantizationRetrievalSimulator,
    Faz80MasterAutonomousSystem
)


def test_multi_agent_choreography_hierarchical_and_blackboard():
    engine = MultiAgentChoreographyEngine()
    engine.register_worker("coder", "Senior Coder", ["code_synth", "ast_check"], token_cost_weight=1.0)
    engine.register_worker("tester", "QA Specialist", ["test_synth", "coverage"], token_cost_weight=0.8)

    # 1. Hierarchical dispatch with capability matching
    subtasks = [
        {"subtask_id": "st_1", "title": "Implement core logic", "required_capability": "code_synth"},
        {"subtask_id": "st_2", "title": "Write unit tests", "required_capability": "test_synth"}
    ]
    dispatched = engine.dispatch_hierarchical(task_id="proj_alpha", goal="Build Feature", subtasks=subtasks)
    assert len(dispatched) == 2
    assert dispatched[0]["assigned_agent"] == "coder"
    assert dispatched[0]["status"] == "DISPATCHED"
    assert dispatched[1]["assigned_agent"] == "tester"
    assert dispatched[1]["status"] == "DISPATCHED"

    # 2. Blackboard read/write
    entry = engine.post_to_blackboard("api_contract", {"endpoint": "/v1/agents", "method": "POST"}, "coder")
    assert entry["revision"] == 1
    read_back = engine.read_from_blackboard("api_contract")
    assert read_back == {"endpoint": "/v1/agents", "method": "POST"}

    # Revision increment
    entry2 = engine.post_to_blackboard("api_contract", {"endpoint": "/v1/agents", "method": "GET"}, "tester")
    assert entry2["revision"] == 2


def test_multi_agent_market_auction():
    engine = MultiAgentChoreographyEngine()
    engine.register_worker("worker_a", "Worker Fast", ["data_proc"], token_cost_weight=1.0)
    engine.register_worker("worker_b", "Worker Premium", ["data_proc"], token_cost_weight=2.0)

    auction_res = engine.run_market_auction(task_id="task_etl", complexity_score=10.0, required_capability="data_proc")
    assert auction_res["status"] == "AWARDED"
    # worker_a has lower token_cost_weight (1.0 vs 2.0)
    assert auction_res["winner"] == "worker_a"
    assert auction_res["winning_bid"] < 15.0


def test_binary_quantization_two_stage_retrieval_and_footprint():
    sim = BinaryQuantizationRetrievalSimulator(dimension=8)

    # Index 3 vectors
    # doc1 is aligned with query
    doc1_vec = [1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0]
    # doc2 is orthogonal / mixed
    doc2_vec = [-1.0, -1.0, 1.0, 1.0, 1.0, 1.0, -1.0, -1.0]
    # doc3 is inverse of query
    doc3_vec = [-1.0, -1.0, -1.0, -1.0, 1.0, 1.0, 1.0, 1.0]

    sim.insert_vector("doc1_target", doc1_vec, {"tag": "target"})
    sim.insert_vector("doc2_mixed", doc2_vec, {"tag": "mixed"})
    sim.insert_vector("doc3_inverse", doc3_vec, {"tag": "inverse"})

    query = [0.8, 0.9, 0.5, 0.7, -0.6, -0.8, -0.4, -0.9]
    res = sim.two_stage_retrieve(query, candidate_pool_size=3, top_k=2)

    assert res["total_indexed"] == 3
    assert res["top_k_returned"] == 2
    # doc1_target should be top rank
    assert res["results"][0]["doc_id"] == "doc1_target"
    assert res["results"][0]["cosine_similarity"] > 0.9
    assert res["results"][0]["hamming_distance"] == 0

    # Calculate footprint
    footprint = sim.calculate_quantization_footprint()
    assert footprint["indexed_vectors"] == 3
    assert footprint["dimension"] == 8
    # 8 float32 = 32 bytes; 8 bits = 1 byte -> 32x reduction
    assert footprint["ram_reduction_factor"] == 32.0
    assert footprint["compression_savings_pct"] > 95.0


def test_faz80_master_autonomous_project_sprint_e2e():
    system = Faz80MasterAutonomousSystem(embedding_dim=8)

    project_id = "faz80_sprint_001"
    goal = "Synthesize autonomous agent architecture and token economics engine"
    subtasks = [
        {"subtask_id": "st_1", "title": "Build CodeAct Runner", "required_capability": "python_codeact"},
        {"subtask_id": "st_2", "title": "Verify AST", "required_capability": "ast_validation"}
    ]

    prompt_tokens = ["EntropyAI", "MasterOrchestrator", "Faz80", "SystemDirective:", "TaskIsState", "AgentIsCompute"]
    codeact_script = """
items = [10, 20, 30, 40]
filtered = [x * 2 for x in items if x > 15]
result = {"doubled": filtered, "count": len(filtered)}
"""
    query_vec = [1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0]
    memory_vecs = [
        ("mem_1", [1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0], {"topic": "agent_desks"}),
        ("mem_2", [-1.0, -1.0, 1.0, 1.0, -1.0, -1.0, 1.0, 1.0], {"topic": "legacy_chat"})
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
    assert sprint_res["status"] == "COMPLETED_AND_VERIFIED"
    assert sprint_res["radix_cache"]["cached_tokens_hit"] >= 6
    assert sprint_res["two_stage_retrieval"]["top_k_returned"] > 0
    assert sprint_res["two_stage_retrieval"]["results"][0]["doc_id"] == "mem_1"
    assert sprint_res["binary_quantization_footprint"]["ram_reduction_factor"] == 32.0
    assert len(sprint_res["multi_agent_dispatches"]) == 2
    assert sprint_res["codeact_execution"]["status"] == "SUCCESS"
    assert sprint_res["codeact_execution"]["output"] == {"doubled": [40, 60, 80], "count": 3}
    assert sprint_res["token_economics"]["tokens_saved"] > 35000
    assert sprint_res["commit_status"] == "COMMITTED"
