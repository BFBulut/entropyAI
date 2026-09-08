"""
Automated Test Suite for Faz 114 Master Autonomous Agent Architecture
====================================================================
Verifies all Faz 114 invariants:
1. Stateless FastMCP 4.1 Engine (MCPServer, Sessionless, ETag Caching, Background Tasks, Cancellation)
2. AAIF & Linux Foundation A2A v1.1.0 & AP2 2.0 (Agent Cards, SLA Latency & Automatic Clawback Penalties)
3. Self-Refining Harness 3.0 (AST Preflight Guard, Merkle Freezing, Fit Ratio Diagnostics, Circuit Breakers)
4. Agent Desks 3.0 (Single-Writer Boundary, AST Semantic Merge Conflict Detection)
5. Octa-Store Cognitive Memory (8 Layers) & RRF-8 Reciprocal Rank Fusion
6. Extreme Token Physics 6.0 (Radix Alignment, AST Skeletonization 3.0, CodeAct 3.0 Sandbox, Delta Accounting)
7. Erlang-OTP 3.0 Supervision Trees (One-for-One, One-for-All, Rest-for-One, Crash Thresholds)
8. Faz 114 Master Autonomous Swarm Orchestrator Full Mission Lifecycle
"""

import math
import time
import pytest
from src.entropy.tools.autonomous_agent_architecture_faz114 import (
    StatelessFastMCP41Engine,
    A2APhase114ProtocolEngine,
    A2ATaskDelegationRequest114,
    A2ATaskStatus114,
    AgentCard114,
    SelfRefiningHarness30,
    HarnessFailureType,
    AgentDeskWorktreeManager30,
    OctaStoreCognitiveRetriever,
    CodeActSandboxEngine114,
    CodeActSecurityException114,
    ExtremeTokenPhysicsOptimizer6,
    OTPSupervisorStrategy114,
    OTPSupervisorTree114,
    Faz114MasterAutonomousSwarmEngine,
)


# ==============================================================================
# 1. FASTMCP 4.1 STATELESS & ETAG TESTS
# ==============================================================================

def test_fastmcp41_stateless_execution_etag_and_cancellation():
    engine = StatelessFastMCP41Engine()
    counter = 0

    def calc_tool(args: dict):
        nonlocal counter
        counter += 1
        return {"val": args["x"] * 3, "counter": counter}

    engine.register_tool(
        name="tripler",
        description="Multiplies input by 3",
        parameters={"x": "int"},
        handler=calc_tool,
        cacheable=True,
        cache_ttl_seconds=30,
    )

    # 1. First call -> Cache Miss
    res1 = engine.execute_tool("tripler", {"x": 10}, user_session_id="usr_1")
    assert res1["success"] is True
    assert res1["cached"] is False
    assert res1["result"]["val"] == 30
    assert counter == 1
    assert engine.cache_misses == 1
    etag = res1["etag"]

    # 2. Second call with If-None-Match matching ETag -> 304 Not Modified
    res2 = engine.execute_tool("tripler", {"x": 10}, user_session_id="usr_1", if_none_match=etag)
    assert res2["success"] is True
    assert res2["cached"] is True
    assert res2.get("status_code") == 304
    assert counter == 1
    assert engine.cache_hits == 1

    # 3. Background Task Dispatch & Cancellation
    t_id = engine.dispatch_background_task("tripler", {"x": 5})
    st = engine.get_task_status(t_id)
    assert st["status"] == "completed"
    assert st["result"]["val"] == 15

    # Test unknown tool
    err_res = engine.execute_tool("nonexistent", {})
    assert err_res["success"] is False


# ==============================================================================
# 2. AAIF A2A v1.1.0 & AP2 2.0 SLA CONTRACT TESTS
# ==============================================================================

def test_a2a_v110_sla_contracts_and_clawback_penalties():
    engine = A2APhase114ProtocolEngine(secret_key="aaif-test-key")
    card = AgentCard114(
        agent_id="agent_fast_coder",
        name="Fast Coder Desk",
        version="2026.114.0",
        description="High throughput coding desk",
        capabilities=["python", "pytest"],
        endpoints={"tasks": "/tasks/fast_coder"},
        token_rate_per_k=0.04,
        sla_max_latency_ms=80.0,
    )
    engine.register_agent(card)

    # Verify cryptographic signature
    assert card.verify_card("aaif-test-key", engine.agent_signatures[card.agent_id])

    # 1. Delegation within SLA -> Full Payout
    contract1 = engine.create_ap2_contract("orch", "agent_fast_coder", token_budget=4000)
    req1 = A2ATaskDelegationRequest114(
        task_id="t_001",
        sender_id="orch",
        target_id="agent_fast_coder",
        payload={"task": "implement feature"},
        token_budget=4000,
        deadline_epoch_s=time.time() + 60,
        payment_contract=contract1,
    )
    resp1 = engine.delegate_task(req1, simulated_execution_ms=20.0, simulated_tokens=1000)
    assert resp1.status == A2ATaskStatus114.COMPLETED
    assert resp1.sla_breached is False
    assert math.isclose(resp1.settled_payment, 0.04, rel_tol=1e-3)  # 1000 tokens * 0.04/k = 0.04

    # 2. Delegation breaching SLA (>80ms) -> 20% Clawback Penalty Applied
    contract2 = engine.create_ap2_contract("orch", "agent_fast_coder", token_budget=4000)
    req2 = A2ATaskDelegationRequest114(
        task_id="t_002",
        sender_id="orch",
        target_id="agent_fast_coder",
        payload={"task": "heavy task"},
        token_budget=4000,
        deadline_epoch_s=time.time() + 60,
        payment_contract=contract2,
    )
    resp2 = engine.delegate_task(req2, simulated_execution_ms=100.0, simulated_tokens=1000)
    assert resp2.status == A2ATaskStatus114.COMPLETED
    assert resp2.sla_breached is True
    # Base 0.04 - 20% penalty = 0.032
    assert math.isclose(resp2.settled_payment, 0.032, rel_tol=1e-3)


# ==============================================================================
# 3. SELF-REFINING HARNESS 3.0 TESTS
# ==============================================================================

def test_self_refining_harness_fit_ratio_and_circuit_breaker():
    harness = SelfRefiningHarness30(failure_threshold=3)

    # 1. AST Preflight Guard
    safe_code = "def add(a, b):\n    return a + b\n"
    is_valid, err, merkle = harness.preflight_ast_guard(safe_code)
    assert is_valid is True
    assert err is None
    assert len(merkle) == 64

    # Dangerous code
    unsafe_code = "def run():\n    eval('2 + 2')\n"
    is_valid_bad, err_bad, _ = harness.preflight_ast_guard(unsafe_code)
    assert is_valid_bad is False
    assert "Forbidden dangerous call" in err_bad

    # 2. Execution Logging & Fit Ratio Diagnostics
    harness.record_execution(success=True)
    harness.record_execution(success=False, failure_type=HarnessFailureType.MODEL_REASONING_FAULT)
    harness.record_execution(success=False, failure_type=HarnessFailureType.SCAFFOLDING_TOOL_FAULT)

    diag = harness.generate_diagnostic_report()
    assert diag.total_runs == 3
    assert diag.successful_runs == 1
    assert 0.0 <= diag.fit_ratio <= 1.0

    # 3. Trigger Circuit Breaker
    harness.record_execution(success=False, failure_type=HarnessFailureType.TIMEOUT_FAULT)
    harness.record_execution(success=False, failure_type=HarnessFailureType.TIMEOUT_FAULT)
    assert harness.circuit_open is True


# ==============================================================================
# 4. AGENT DESKS 3.0 & AST SEMANTIC CONFLICT TESTS
# ==============================================================================

def test_agent_desks_swb_locks_and_ast_semantic_conflicts():
    mgr = AgentDeskWorktreeManager30(base_repo_dir=".entropy/test_desks")
    d1 = mgr.provision_desk("desk_backend", "Backend")
    d2 = mgr.provision_desk("desk_frontend", "Frontend")

    # 1. Single-Writer Boundary (SWB) Mutual Exclusion
    assert mgr.acquire_file_lock("desk_backend", "src/api.py") is True
    assert mgr.acquire_file_lock("desk_frontend", "src/api.py") is False  # Locked by backend
    mgr.release_file_lock("desk_backend", "src/api.py")
    assert mgr.acquire_file_lock("desk_frontend", "src/api.py") is True

    # 2. AST Semantic Conflict Detection
    branch_base = "def get_user(): pass\ndef get_order(): pass\n"
    # Desk A changes get_user, Desk B changes get_order (disjoint changes)
    branch_a = "def get_user(): return {'id': 1}\ndef get_order(): pass\n"
    branch_b = "def get_user(): pass\ndef get_order(): return {'item': 'widget'}\n"

    conflict_ab, colliding = mgr.detect_ast_semantic_conflicts(branch_a, branch_b, base_code=branch_base)
    # Different functions -> No collision
    assert conflict_ab is False
    assert len(colliding) == 0

    # Both desks change get_user differently -> Real Collision
    branch_c = "def get_user(): return 'user_c'\n"
    branch_d = "def get_user(): return 'user_d'\n"
    conflict_cd, colliding_cd = mgr.detect_ast_semantic_conflicts(branch_c, branch_d, base_code=branch_base)
    assert conflict_cd is True
    assert "get_user" in colliding_cd


# ==============================================================================
# 5. OCTA-STORE COGNITIVE MEMORY TESTS
# ==============================================================================

def test_octa_store_rrf8_fusion():
    store = OctaStoreCognitiveRetriever()
    assert len(store.layers) == 8

    # Query multi-layer retrieval
    results = store.rrf_8_fusion("A2A protocol and pgvector", top_k=5)
    assert len(results) == 5
    top_node, score = results[0]
    assert top_node.id in ("obs_01", "pgv_01", "bm_01", "smt_01", "hippo_01")
    assert score > 0.0


# ==============================================================================
# 6. CODEACT 3.0 & EXTREME TOKEN PHYSICS TESTS
# ==============================================================================

def test_codeact3_sandbox_and_token_physics_optimizer():
    codeact = CodeActSandboxEngine114()

    # 1. Safe execution
    script = "result = [x ** 2 for x in range(4)]\n"
    res = codeact.execute_codeact(script)
    assert res["success"] is True
    assert res["result"] == [0, 1, 4, 9]

    # 2. Security screening
    with pytest.raises(CodeActSecurityException114):
        codeact.execute_codeact("import os\nos.system('dir')")

    with pytest.raises(CodeActSecurityException114):
        codeact.execute_codeact("open('secret.txt', 'w')")

    # 3. Token Physics Invariants
    tp = ExtremeTokenPhysicsOptimizer6()

    # Radix boundary alignment
    padded = tp.align_to_radix_boundary("You are Entropy AI assistant.", "Query: Run test.", boundary_tokens=64)
    assert "[DYNAMIC_CONTEXT]" in padded

    # AST Skeletonization
    full_code = "def complex_algo(data: list) -> dict:\n    \"\"\"Docstring.\"\"\"\n    x = 10\n    y = 20\n    return {'ans': x + y}\n"
    skel = tp.skeletonize_python_ast(full_code)
    assert "def complex_algo(data: list) -> dict:" in skel
    assert '"""Docstring."""' in skel
    assert "..." in skel

    # Matryoshka MRL truncation
    orig_emb = [0.1] * 512
    trunc = tp.matryoshka_truncate(orig_emb, target_dim=256)
    assert len(trunc) == 256
    norm = math.sqrt(sum(x * x for x in trunc))
    assert math.isclose(norm, 1.0, rel_tol=1e-5)

    # Delta Token Accounting
    assert tp.compute_delta_tokens(current_cumulative=15000, previous_cumulative=12000) == 3000
    assert tp.compute_delta_tokens(current_cumulative=12000, previous_cumulative=12000) == 0


# ==============================================================================
# 7. ERLANG-OTP 3.0 SUPERVISION TESTS
# ==============================================================================

def test_otp_supervisor_trees_and_strategies():
    tree = OTPSupervisorTree114(strategy=OTPSupervisorStrategy114.REST_FOR_ONE, max_restarts=2)
    tree.register_worker("w1", "Ingest")
    tree.register_worker("w2", "Process")
    tree.register_worker("w3", "Output")

    # REST_FOR_ONE: crashing w2 restarts w2 and w3, but not w1
    restarted = tree.report_crash("w2")
    assert restarted == ["w2", "w3"]
    assert tree.workers["w1"].status == "RUNNING"

    # Second crash
    tree.report_crash("w2")
    assert tree.tree_collapsed is False

    # Third crash exceeds max_restarts=2 -> Tree collapsed
    collapse_resp = tree.report_crash("w2")
    assert "TREE_COLLAPSED_CIRCUIT_TRIGGERED" in collapse_resp
    assert tree.tree_collapsed is True


# ==============================================================================
# 8. FAZ 114 MASTER AUTONOMOUS SWARM ORCHESTRATOR FULL MISSION
# ==============================================================================

def test_faz114_master_swarm_mission_execution():
    swarm = Faz114MasterAutonomousSwarmEngine()
    mission_res = swarm.run_autonomous_mission(
        mission_title="Build Distributed Agent Pipeline",
        mission_spec={"objective": "Deploy 3 worker desks with FastMCP and AP2"},
    )

    assert mission_res["status"] == "SUCCESS"
    assert mission_res["a2a_status"] == "completed"
    assert mission_res["ap2_settled_payment"] > 0
    assert mission_res["mcp_success"] is True
    assert mission_res["codeact_result"] == 20  # sum([0, 2, 4, 6, 8])
    assert mission_res["single_writer_lock_acquired"] is True
    assert mission_res["delta_tokens"] == 1500
    assert mission_res["octa_nodes_retrieved"] == 4
    assert mission_res["harness_fit_ratio"] >= 0.0
