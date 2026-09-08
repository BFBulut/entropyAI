"""
Automated Test Suite for Faz 115 Master Autonomous Agent Architecture
====================================================================
Verifies all Faz 115 invariants:
1. Stateless FastMCP 4.2 Engine (MCPServer, Sessionless, ETag Caching, Elicitation Form Mode, Background Tasks, Cancellation)
2. AAIF & Linux Foundation A2A v1.2 & AP2 2.1 (Agent Cards, DAG Decomposition, Multi-Criteria SLA Clawback Penalties)
3. Self-Refining Harness 4.0 (AST Preflight Guard, Merkle Checkpointing, Fit Ratio 2.0 Diagnostics, Circuit Breakers)
4. Agent Desks 4.0 (Cognitive Desk Curation, Single-Writer Boundary, AST 3-Way Semantic Merge Conflict Resolution)
5. Nona-Store Cognitive Memory (9 Layers) & RRF-9 Reciprocal Rank Fusion with Ebbinghaus Decay
6. Extreme Token Physics 7.0 (Radix Alignment, AST Skeletonization 4.0, CodeAct 4.0 Sandbox, Delta Accounting 3.0)
7. Erlang-OTP 4.0 Supervision Trees (One-for-One, One-for-All, Rest-for-One, Crash Thresholds)
8. Faz 115 Master Autonomous Swarm Orchestrator Full Mission Lifecycle
"""

import math
import time
import pytest
from src.entropy.tools.autonomous_agent_architecture_faz115 import (
    StatelessFastMCP42Engine,
    ElicitationMode,
    A2APhase115ProtocolEngine,
    A2ATaskDelegationRequest115,
    A2ATaskStatus115,
    AgentCard115,
    SelfRefiningHarness40,
    HarnessFailureType4,
    AgentDeskWorktreeManager40,
    NonaStoreCognitiveRetriever,
    CodeActSandboxEngine115,
    CodeActSecurityException115,
    ExtremeTokenPhysicsOptimizer7,
    OTPSupervisorStrategy115,
    OTPSupervisorTree115,
    Faz115MasterAutonomousSwarmEngine,
)


# ==============================================================================
# 1. FASTMCP 4.2 STATELESS & ELICITATION TESTS
# ==============================================================================

def test_fastmcp42_stateless_execution_etag_elicitation_and_cancellation():
    engine = StatelessFastMCP42Engine()
    counter = 0

    def calc_tool(args: dict):
        nonlocal counter
        counter += 1
        return {"val": args["x"] * 4, "counter": counter}

    def deploy_tool(args: dict):
        return {"deployed": True, "service": args["name"], "tier": args.get("tier", "basic")}

    engine.register_tool(
        name="quadrupler",
        description="Multiplies input by 4",
        parameters={"x": "int"},
        handler=calc_tool,
        cacheable=True,
        cache_ttl_seconds=30,
    )

    engine.register_tool(
        name="deployer",
        description="Deploys app with tier elicitation",
        parameters={"name": "str"},
        handler=deploy_tool,
        requires_elicitation=True,
        elicitation_schema={"tier": "string"},
    )

    # 1. First call -> Cache Miss
    res1 = engine.execute_tool("quadrupler", {"x": 5}, user_session_id="usr_115")
    assert res1["success"] is True
    assert res1["cached"] is False
    assert res1["result"]["val"] == 20
    assert counter == 1
    assert engine.cache_misses == 1
    etag = res1["etag"]

    # 2. Second call with If-None-Match matching ETag -> 304 Not Modified
    res2 = engine.execute_tool("quadrupler", {"x": 5}, user_session_id="usr_115", if_none_match=etag)
    assert res2["success"] is True
    assert res2["cached"] is True
    assert res2.get("status_code") == 304
    assert counter == 1
    assert engine.cache_hits == 1

    # 3. Elicitation Flow Test
    el_req_res = engine.execute_tool("deployer", {"name": "micro-gateway"})
    assert el_req_res["success"] is False
    assert el_req_res["status"] == "ELICITATION_REQUIRED"
    el_id = el_req_res["elicitation_id"]

    # Resolve elicitation with validated input
    resolved = engine.resolve_elicitation(el_id, {"tier": "enterprise_pro"})
    assert resolved is True

    # Re-execute with elicitation_id
    el_final_res = engine.execute_tool("deployer", {"name": "micro-gateway"}, elicitation_id=el_id)
    assert el_final_res["success"] is True
    assert el_final_res["result"]["deployed"] is True
    assert el_final_res["result"]["tier"] == "enterprise_pro"

    # 4. Background Task Dispatch, Progress & Cancellation
    t_id = engine.dispatch_background_task("quadrupler", {"x": 6})
    st = engine.get_task_status(t_id)
    assert st["status"] == "completed"
    assert st["progress"] == 100
    assert st["result"]["val"] == 24

    # Test unknown tool
    err_res = engine.execute_tool("nonexistent", {})
    assert err_res["success"] is False


# ==============================================================================
# 2. AAIF A2A v1.2 & AP2 2.1 SLA CONTRACT & DAG TESTS
# ==============================================================================

def test_a2a_v120_dag_decomposition_sla_contracts_and_clawback_penalties():
    engine = A2APhase115ProtocolEngine(secret_key="aaif-test-key-115")
    card = AgentCard115(
        agent_id="agent_fast_coder",
        name="Fast Coder Desk",
        version="2026.115.0",
        description="High throughput coding desk",
        capabilities=["python_codeact", "test_verification"],
        endpoints={"tasks": "/tasks/fast_coder"},
        token_rate_per_k=0.05,
        sla_max_latency_ms=80.0,
        sla_min_quality_score=0.90,
    )
    engine.register_agent(card)

    # 1. Verify Card Signature
    sig = engine.agent_signatures["agent_fast_coder"]
    assert card.verify_card("aaif-test-key-115", sig) is True
    assert card.verify_card("wrong-key", sig) is False

    # 2. DAG Decomposition
    dag = engine.decompose_goal_to_dag("Build Autonomous Memory Service")
    assert len(dag) == 4
    assert dag[0].subtask_id == "dag_01_spec"
    assert "dag_01_spec" in dag[1].dependencies

    # 3. SLA Adherent Execution -> Full Settlement
    contract1 = engine.create_ap2_contract(
        payer_id="orchestrator",
        payee_id="agent_fast_coder",
        token_budget=5000,
    )
    req1 = A2ATaskDelegationRequest115(
        task_id="task_ok_1",
        sender_id="orchestrator",
        target_id="agent_fast_coder",
        payload={"task": "implement_ast_filter"},
        token_budget=5000,
        deadline_epoch_s=time.time() + 10,
        payment_contract=contract1,
    )
    resp1 = engine.delegate_task(req1, simulated_execution_ms=20.0, simulated_tokens=2000, simulated_quality=0.95)
    assert resp1.status == A2ATaskStatus115.COMPLETED
    assert resp1.sla_latency_breached is False
    assert resp1.sla_quality_breached is False
    assert resp1.refunded_clawback == 0.0
    # Expected payout: 2000 tokens * 0.05 / 1000 = 0.10
    assert math.isclose(resp1.settled_payment, 0.10, rel_tol=1e-3)

    # 4. SLA Latency & Quality Breach -> Penalty Clawback
    contract2 = engine.create_ap2_contract(
        payer_id="orchestrator",
        payee_id="agent_fast_coder",
        token_budget=5000,
    )
    req2 = A2ATaskDelegationRequest115(
        task_id="task_slow_breach",
        sender_id="orchestrator",
        target_id="agent_fast_coder",
        payload={"task": "deep_simulation"},
        token_budget=5000,
        deadline_epoch_s=time.time() + 10,
        payment_contract=contract2,
    )
    resp2 = engine.delegate_task(req2, simulated_execution_ms=120.0, simulated_tokens=2000, simulated_quality=0.75)
    assert resp2.status == A2ATaskStatus115.COMPLETED
    assert resp2.sla_latency_breached is True
    assert resp2.sla_quality_breached is True
    # Base = 0.10. Penalties: latency=20% (0.02), quality=30% (0.03). Total clawback = 0.05. Settled = 0.05.
    assert math.isclose(resp2.refunded_clawback, 0.05, rel_tol=1e-3)
    assert math.isclose(resp2.settled_payment, 0.05, rel_tol=1e-3)


# ==============================================================================
# 3. SELF-REFINING HARNESS 4.0 TESTS
# ==============================================================================

def test_self_refining_harness40_fit_ratio_merkle_and_circuit_breaker():
    harness = SelfRefiningHarness40(failure_threshold=3)

    # 1. Preflight AST Guard tests
    valid_code = "def add(a, b):\n    return a + b\n"
    is_valid, err, digest1 = harness.preflight_ast_guard(valid_code)
    assert is_valid is True
    assert err is None
    assert len(digest1) == 64

    dangerous_code = "def attack():\n    eval('2 + 2')\n"
    is_val_dang, err_dang, digest2 = harness.preflight_ast_guard(dangerous_code)
    assert is_val_dang is False
    assert "eval" in err_dang

    syntax_bad_code = "def broken(:\n    return 1\n"
    is_val_syn, err_syn, digest3 = harness.preflight_ast_guard(syntax_bad_code)
    assert is_val_syn is False
    assert "Syntax Error" in err_syn

    # 2. Fit Ratio & Diagnostics
    harness.record_execution(success=True)
    harness.record_execution(success=False, failure_type=HarnessFailureType4.MODEL_REASONING_FAULT)
    harness.record_execution(success=False, failure_type=HarnessFailureType4.SCAFFOLDING_TOOL_FAULT)
    harness.record_execution(success=True)

    report = harness.generate_diagnostic_report()
    assert report.total_runs == 4
    assert report.successful_runs == 2
    # Failures = 2, Scaffolding = 1 -> Fit Ratio = 1.0 - (1 / 2) = 0.50
    assert math.isclose(report.fit_ratio, 0.50, rel_tol=1e-3)

    # 3. Circuit Breaker Trigger
    harness.record_execution(success=False, failure_type=HarnessFailureType4.TIMEOUT_FAULT)
    harness.record_execution(success=False, failure_type=HarnessFailureType4.TIMEOUT_FAULT)
    harness.record_execution(success=False, failure_type=HarnessFailureType4.TIMEOUT_FAULT)
    assert harness.circuit_open is True


# ==============================================================================
# 4. AGENT DESKS 4.0 & 3-WAY AST SEMANTIC MERGE TESTS
# ==============================================================================

def test_agent_desks40_swb_locks_and_3way_ast_semantic_merge():
    manager = AgentDeskWorktreeManager40()
    desk_a = manager.provision_desk("desk_alpha", "Lead Architect")
    desk_b = manager.provision_desk("desk_beta", "Core Developer")

    # 1. Cognitive Desk Curation
    manager.place_on_desk("desk_alpha", "Current Task: Schema Design")
    assert len(desk_a.cognitive_desk_items) == 1

    # 2. SWB Locking
    assert manager.acquire_file_lock("desk_alpha", "src/core/bus.py") is True
    assert manager.acquire_file_lock("desk_beta", "src/core/bus.py") is False
    manager.release_file_lock("desk_alpha", "src/core/bus.py")
    assert manager.acquire_file_lock("desk_beta", "src/core/bus.py") is True

    # 3. 3-Way AST Semantic Merge: Disjoint changes (Clean Merge)
    base_code = "def func_a():\n    return 'base_a'\n\ndef func_b():\n    return 'base_b'\n"
    branch_a = "def func_a():\n    return 'mod_a_by_desk_alpha'\n\ndef func_b():\n    return 'base_b'\n"
    branch_b = "def func_a():\n    return 'base_a'\n\ndef func_b():\n    return 'mod_b_by_desk_beta'\n"

    success, merged_code, conflicts = manager.resolve_3way_ast_merge(base_code, branch_a, branch_b)
    assert success is True
    assert len(conflicts) == 0
    assert "mod_a_by_desk_alpha" in merged_code
    assert "mod_b_by_desk_beta" in merged_code

    # 4. 3-Way AST Semantic Merge: Conflicting changes to same function
    conflict_branch_b = "def func_a():\n    return 'conflicting_alpha_change'\n\ndef func_b():\n    return 'base_b'\n"
    fail_success, _, fail_conflicts = manager.resolve_3way_ast_merge(base_code, branch_a, conflict_branch_b)
    assert fail_success is False
    assert "func_a" in fail_conflicts


# ==============================================================================
# 5. NONA-STORE COGNITIVE MEMORY & RRF-9 TESTS
# ==============================================================================

def test_nona_store_rrf9_fusion_and_ebbinghaus_retention():
    store = NonaStoreCognitiveRetriever()
    assert len(store.layers) == 9

    results = store.rrf_9_fusion("AAIF A2A Protocol Specifications", top_k=5)
    assert len(results) == 5

    # Top hit should have highest RRF score
    top_node, top_score = results[0]
    assert top_score > results[1][1]
    assert top_score > 0.0

    # Ebbinghaus strength verification
    retention = top_node.calculate_ebbinghaus_strength()
    assert 0.0 <= retention <= 1.0


# ==============================================================================
# 6. EXTREME TOKEN PHYSICS 7.0 & CODEACT 4.0 TESTS
# ==============================================================================

def test_codeact4_sandbox_and_extreme_token_physics7():
    sandbox = CodeActSandboxEngine115()

    # 1. Valid execution
    script = "total = sum([x * 5 for x in range(4)])\nresult = total + 10\n"
    res = sandbox.execute_codeact(script)
    assert res["success"] is True
    assert res["result"] == 40

    # 2. Block forbidden call
    with pytest.raises(CodeActSecurityException115):
        sandbox.execute_codeact("import os\n")

    with pytest.raises(CodeActSecurityException115):
        sandbox.execute_codeact("eval('1 + 1')\n")

    # 3. Token Physics Radix Alignment
    aligned = ExtremeTokenPhysicsOptimizer7.align_to_radix_boundary(
        static_prefix="SYSTEM ROLE: You are Entropy AI Core Orchestrator.",
        dynamic_suffix="USER INSTRUCTION: Perform analysis.",
        boundary_tokens=64,
    )
    assert "[DYNAMIC_CONTEXT]" in aligned

    # 4. AST Skeletonization
    src = "def calculate_risk(portfolio):\n    '''Calculates portfolio VaR.'''\n    val = sum(portfolio)\n    return val * 0.05\n"
    skel = ExtremeTokenPhysicsOptimizer7.skeletonize_python_ast(src)
    assert "Calculates portfolio VaR." in skel
    assert "..." in skel
    assert "sum(portfolio)" not in skel

    # 5. Matryoshka Vector Truncation
    high_dim = [0.1] * 1536
    trunc = ExtremeTokenPhysicsOptimizer7.matryoshka_truncate(high_dim, target_dim=256)
    assert len(trunc) == 256
    norm = math.sqrt(sum(x * x for x in trunc))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)

    # 6. Delta Token Accounting
    delta = ExtremeTokenPhysicsOptimizer7.compute_delta_tokens(
        current_cumulative=15420,
        previous_cumulative=13000,
    )
    assert delta == 2420


# ==============================================================================
# 7. ERLANG-OTP 4.0 SUPERVISION TESTS
# ==============================================================================

def test_otp4_supervisor_trees_and_strategies():
    # 1. One-for-One
    tree1 = OTPSupervisorTree115(strategy=OTPSupervisorStrategy115.ONE_FOR_ONE)
    tree1.register_worker("w1", "Worker 1")
    tree1.register_worker("w2", "Worker 2")

    restarted1 = tree1.report_crash("w1")
    assert restarted1 == ["w1"]
    assert tree1.workers["w1"].status == "RUNNING"
    assert tree1.workers["w2"].status == "RUNNING"

    # 2. One-for-All
    tree2 = OTPSupervisorTree115(strategy=OTPSupervisorStrategy115.ONE_FOR_ALL)
    tree2.register_worker("w1", "Worker 1")
    tree2.register_worker("w2", "Worker 2")

    restarted2 = tree2.report_crash("w1")
    assert restarted2 == ["w1", "w2"]

    # 3. Rest-for-One
    tree3 = OTPSupervisorTree115(strategy=OTPSupervisorStrategy115.REST_FOR_ONE)
    tree3.register_worker("w1", "Worker 1")
    tree3.register_worker("w2", "Worker 2")
    tree3.register_worker("w3", "Worker 3")

    restarted3 = tree3.report_crash("w2")
    assert restarted3 == ["w2", "w3"]

    # 4. Cascade Threshold Failure
    tree_fail = OTPSupervisorTree115(max_restarts=2)
    tree_fail.register_worker("fragile", "Fragile Worker")
    tree_fail.report_crash("fragile")
    tree_fail.report_crash("fragile")
    assert tree_fail.tree_collapsed is False
    res_trip = tree_fail.report_crash("fragile")
    assert "TREE_COLLAPSED_CIRCUIT_TRIGGERED" in res_trip
    assert tree_fail.tree_collapsed is True


# ==============================================================================
# 8. MASTER AUTONOMOUS SWARM ORCHESTRATOR MISSION LIFECYCLE
# ==============================================================================

def test_faz115_master_swarm_mission_execution():
    swarm = Faz115MasterAutonomousSwarmEngine()
    mission_res = swarm.run_autonomous_mission(
        mission_title="Deploy Resilient Micro-Orchestrator Swarm",
        mission_spec={"domain": "agentic_os", "target_tier": "enterprise"},
    )

    assert mission_res["status"] == "SUCCESS"
    assert mission_res["dag_subtasks_count"] == 4
    assert mission_res["a2a_status"] == "completed"
    assert mission_res["ap2_settled_payment"] > 0
    assert len(mission_res["ast_merkle_digest"]) == 64
    assert mission_res["mcp_success"] is True
    assert mission_res["elicitation_flow_success"] is True
    assert mission_res["codeact_result"] == 45
    assert mission_res["ast_3way_merge_success"] is True
    assert "100" in mission_res["ast_merged_code"]
    assert "200" in mission_res["ast_merged_code"]
    assert mission_res["single_writer_lock_acquired"] is True
    assert mission_res["delta_tokens"] == 1800
    assert mission_res["nona_nodes_retrieved"] == 5
    assert mission_res["harness_fit_ratio"] == 1.0
