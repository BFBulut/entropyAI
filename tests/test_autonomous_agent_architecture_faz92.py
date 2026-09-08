"""
Unit tests for Faz 92 Autonomous Agent Architecture.
Validates:
1. Faz92HarnessScaffoldingEngine (OODAV loop, 3x loop & ping-pong oscillation circuit breakers, AST pre-flight).
2. Faz92AgentDesksWorktreeManager (Desk allocation, isolation, test-gated merge gatekeeper, rollback sentinel).
3. Faz92AAIFProtocolEngine (A2A Agent Cards, JSON-RPC 2.0 delegation, SHA-256 artifact passing, FastMCP 2026 tasks).
4. Faz92TriStoreCognitiveMemorySystem (Obsidian exocortex, pgvector 0.8+ 1-Bit BQ Hamming search, Late Chunking, Ebbinghaus retention).
5. Faz92TokenPhysicsContextOptimizer (RadixAttention anchored prefix cache hit, CodeAct vs JSON calling savings, delta token accounting).
6. Faz92MasterAutonomousAgentOS (End-to-end verified mission orchestration for both success and rollback scenarios).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    Faz92HarnessScaffoldingEngine,
    Faz92AgentDesksWorktreeManager,
    Faz92WorktreeDesk,
    Faz92AAIFProtocolEngine,
    Faz92TriStoreCognitiveMemorySystem,
    Faz92TokenPhysicsContextOptimizer,
    Faz92MasterAutonomousAgentOS
)


def test_faz92_harness_scaffolding_engine():
    engine = Faz92HarnessScaffoldingEngine(max_identical_calls=3)

    # 1. Normal allowed calls
    res1 = engine.record_and_verify_call("read_file", '{"path": "a.py"}')
    res2 = engine.record_and_verify_call("read_file", '{"path": "b.py"}')
    assert res1["status"] == "CALL_ALLOWED"
    assert res2["status"] == "CALL_ALLOWED"

    # 2. Loop detection: 3x identical calls
    engine.record_and_verify_call("run_test", '{"cmd": "pytest"}')
    engine.record_and_verify_call("run_test", '{"cmd": "pytest"}')
    res_loop = engine.record_and_verify_call("run_test", '{"cmd": "pytest"}')
    assert res_loop["status"] == "CIRCUIT_BREAKER_TRIPPED"
    assert "LOOP_DETECTED" in res_loop["reason"]
    assert engine.circuit_breaker_tripped is True

    # 3. Oscillation detection [A, B, A, B]
    engine_osc = Faz92HarnessScaffoldingEngine()
    engine_osc.record_and_verify_call("toolA", "arg1")
    engine_osc.record_and_verify_call("toolB", "arg2")
    engine_osc.record_and_verify_call("toolA", "arg1")
    res_osc = engine_osc.record_and_verify_call("toolB", "arg2")
    assert res_osc["status"] == "CIRCUIT_BREAKER_TRIPPED"
    assert "OSCILLATION_DETECTED" in res_osc["reason"]

    # 4. AST Pre-flight
    valid_ast = engine.verify_ast_preflight("def hello(): return 'world'")
    assert valid_ast["valid"] is True
    assert valid_ast["error"] is None

    invalid_ast = engine.verify_ast_preflight("def broken(:")
    assert invalid_ast["valid"] is False
    assert "SyntaxError" in invalid_ast["error"]

    # 5. Full OODAV Loop
    oodav = engine.execute_oodav_loop(
        observation="User requested refactor",
        context_slice="class TargetClass: pass",
        decision_code="def new_method(): pass",
        test_verifier=lambda: True
    )
    assert oodav["status"] == "SUCCESS"
    assert oodav["telemetry"]["ast_valid"] is True


def test_faz92_agent_desks_worktree_manager():
    manager = Faz92AgentDesksWorktreeManager(base_workspace_dir=".entropy/test_workspaces")

    # 1. Allocate Desk
    desk = manager.allocate_desk(
        task_id="task_faz92_9988",
        agent_name="ArchitectUnit",
        ast_focus_slice="class Service: def run(self): pass"
    )
    assert "desk_ArchitectUnit" in desk.desk_id
    assert desk.status == "ACTIVE"
    assert desk.assigned_port >= 9100
    assert "class Service" in desk.cognitive_desk_slice

    # 2. Test-Gated Approval (100% Pass)
    approval = manager.submit_for_merge_verification(
        desk_id=desk.desk_id,
        test_results={"pass_rate": 1.0, "exit_code": 0}
    )
    assert approval["verdict"] == "APPROVED"
    assert desk.status == "MERGED_TO_MAIN"

    # 3. Test-Gated Rejection / Rollback (Regression)
    desk_fail = manager.allocate_desk(task_id="task_faz92_fail11", agent_name="JuniorUnit")
    rejection = manager.submit_for_merge_verification(
        desk_id=desk_fail.desk_id,
        test_results={"pass_rate": 0.65, "exit_code": 1}
    )
    assert rejection["verdict"] == "REJECTED_ROLLBACK"
    assert desk_fail.status == "ROLLBACK_PRUNED"


def test_faz92_aaif_protocol_engine():
    engine = Faz92AAIFProtocolEngine()

    # 1. A2A Agent Card Registration
    card = engine.register_agent_card(
        agent_id="WorkerAgent77",
        name="Worker Agent 77",
        capabilities=["git_worktree", "ast_analysis"],
        public_key_fingerprint="ed25519_test_fp"
    )
    assert card["agent_id"] == "WorkerAgent77"
    assert "https://a2a-protocol.org" in card["$schema"]
    assert card["auth"]["fingerprint"] == "ed25519_test_fp"

    # 2. A2A Strict Artifact Passing Delegation Envelope
    envelope = engine.create_a2a_delegation_envelope(
        sender_id="Supervisor01",
        target_id="WorkerAgent77",
        task_contract={"task_id": "T92", "objective": "Optimize memory retrieval"}
    )
    assert envelope["jsonrpc"] == "2.0"
    assert envelope["method"] == "a2a.delegateTask"
    assert envelope["params"]["artifact_hash"].startswith("sha256:")

    # 3. FastMCP 2026 Background Tasks
    task_rec = engine.register_mcp_task(
        task_id="mcp_task_long_eval",
        task_name="RunTestSuiteAsync",
        total_steps=10
    )
    assert task_rec["status"] == "RUNNING"
    assert task_rec["progress"] == 0.0

    progress_update = engine.update_mcp_task_progress("mcp_task_long_eval", completed_steps=10)
    assert progress_update["progress"] == 1.0
    assert progress_update["status"] == "COMPLETED"


def test_faz92_tri_store_cognitive_memory_system():
    mem = Faz92TriStoreCognitiveMemorySystem(half_life_hours=48.0)

    # 1. Obsidian Exocortex Note
    mem.add_obsidian_note("Entropy/Reports/Test.md", "# Test Architectural Decision")
    assert "Entropy/Reports/Test.md" in mem.obsidian_notes

    # 2. pgvector 0.8+ 1-Bit Binary Quantization (BQ)
    # Vector length 8: float values converted to bits
    v1 = [0.8, -0.4, 0.6, -0.9, 0.3, 0.7, -0.1, -0.5]
    rec1 = mem.insert_pgvector_bq_embedding(
        doc_id="doc_harness_arch",
        content="The harness is the runtime control plane.",
        float_vector=v1,
        surprise_score=0.9
    )
    assert rec1["bit_vector"] == "10101100"
    assert rec1["byte_size"] == 1

    v2 = [-0.8, -0.4, -0.6, -0.9, -0.3, -0.7, -0.1, -0.5]
    rec2 = mem.insert_pgvector_bq_embedding(
        doc_id="doc_irrelevant",
        content="Irrelevant background data.",
        float_vector=v2,
        surprise_score=0.1
    )
    assert rec2["bit_vector"] == "00000000"

    # 3. Two-Stage Search (Hamming -> Composite Ebbinghaus)
    query_v = [0.9, -0.3, 0.5, -0.8, 0.2, 0.8, -0.2, -0.4]  # Very similar to v1
    results = mem.search_pgvector_two_stage(query_vector=query_v, top_k=2)
    assert len(results) == 2
    assert results[0]["doc_id"] == "doc_harness_arch"
    assert results[0]["composite_score"] > results[1]["composite_score"]

    # 4. Late Chunking Simulation
    long_doc = "word " * 50
    late_chunk = mem.simulate_late_chunking(long_doc, chunk_size_words=15)
    assert late_chunk["context_cliff_prevented"] is True
    assert late_chunk["chunk_count"] == 4


def test_faz92_token_physics_context_optimizer():
    optimizer = Faz92TokenPhysicsContextOptimizer()

    # 1. RadixAttention Prefix Cache Hit
    cache_store = {"SYSTEM_PREFIX_IMMUTABLE_2026"}
    hit_res = optimizer.calculate_radix_cache_hit("SYSTEM_PREFIX_IMMUTABLE_2026", cache_store)
    assert hit_res["cache_hit"] is True
    assert hit_res["cost_reduction_pct"] == 90.0
    assert hit_res["ttft_speedup_factor"] == 10.0

    miss_res = optimizer.calculate_radix_cache_hit("RANDOM_TIMESTAMP_PREFIX", cache_store)
    assert miss_res["cache_hit"] is False
    assert miss_res["cost_reduction_pct"] == 0.0

    # 2. CodeAct vs JSON Tool Calling Savings
    savings = optimizer.calculate_codeact_savings(raw_output_size_kb=20.0, num_tool_calls=4)
    assert savings["json_tool_tokens"] == 13000
    assert savings["codeact_tokens"] == 170
    assert savings["savings_pct"] > 98.0
    assert savings["compression_factor"] > 70.0

    # 3. Delta Token Accounting
    # If lifetime usage went from 50,000 to 52,300 in this turn:
    delta = optimizer.calculate_delta_token_usage(lifetime_current=52300, lifetime_previous=50000)
    assert delta == 2300

    # Test baseline floor
    delta_floor = optimizer.calculate_delta_token_usage(lifetime_current=1000, lifetime_previous=2000)
    assert delta_floor == 0


def test_faz92_master_autonomous_agent_os():
    system = Faz92MasterAutonomousAgentOS()

    # 1. Successful mission
    success_mission = system.run_full_mission(
        mission_id="mission_faz92_success",
        goal="Develop automated CI verification harness",
        agent_name="ArchitectPrime",
        simulated_code="def build_harness(): return 'SECURE'",
        simulate_success=True
    )
    assert success_mission["final_status"] == "MISSION_SUCCESS"
    assert success_mission["desk_telemetry"]["verdict"] == "APPROVED"
    assert success_mission["a2a_envelope"] == "a2a.delegateTask"
    assert success_mission["oodav_telemetry"] == "SUCCESS"
    assert success_mission["token_physics"]["cache_hit"] is True
    assert success_mission["token_physics"]["codeact_savings_pct"] > 95.0

    # 2. Failed / Rollback mission
    fail_mission = system.run_full_mission(
        mission_id="mission_faz92_fail",
        goal="Faulty PR implementation",
        agent_name="FaultyWorker",
        simulated_code="def broken_impl(): return False",
        simulate_success=False
    )
    assert fail_mission["final_status"] == "MISSION_FAILED_ROLLBACK"
    assert fail_mission["desk_telemetry"]["verdict"] == "REJECTED_ROLLBACK"
