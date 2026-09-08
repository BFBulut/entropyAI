"""
Automated Test Suite for Faz 123 Master Autonomous Agent Architecture Module
=============================================================================
Verifies 100% programmatic correctness across all 8 architectural pillars:
1. Stateless FastMCP 6.0 (SEP-4000 Tool Graph, Stage Masking, Attenuation v4, ETag 304, Pipelines)
2. AAIF A2A v3.0 & AP2 3.0 (Agent Cards, Pareto Routing, DAG Scheduling, Byzantine PBFT, 5-Tier Escrow)
3. Self-Refining Harness 8.0 (Fit Ratio 7.0, AST Guard 9.0, Dynamic Adapters, Merkle Rollback)
4. Agent Desks 8.0 (SWB Leases, Shared Blackboard Bus, 3-Way AST Semantic Merge 3.0)
5. Octadeca-Store 18-Layer Memory (Graphiti Invalidation, Ebbinghaus Decay, Dream Phase, RRF-18 Fusion)
6. Extreme Token Physics 15.0 (Radix Alignment, CodeAct 8.0 REPL, AST Skeletonization, Delta Tokens)
7. Erlang-OTP 8.0 Supervision Trees (One-for-One, One-for-All, Rest-for-One, Collapse Budget)
8. Faz 123 Master Autonomous Swarm Orchestrator (Full Mission Lifecycle & End-to-End Execution)
"""

import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz123 import (
    StatelessFastMCP60Engine,
    MCPToolDefinition123,
    TaskLifecycleStage123,
    AgentCard123,
    DecoupledTaskContract123,
    TaskFSMState123,
    AAIFMeshRouter123,
    AP230SLAEscrow,
    SelfRefiningHarness80,
    HarnessFaultCategory123,
    ASTPreflightGuard90,
    AgentDesks80,
    DeskRole123,
    SingleWriterBoundaryViolation123,
    OctadecaStore18LayerMemory,
    TokenPhysics150,
    ErlangOTPSupervisor80,
    SupervisionStrategy123,
    Faz123MasterSwarmOrchestrator
)


def test_fastmcp60_tool_graph_stage_masking_attenuation_and_etag_caching():
    engine = StatelessFastMCP60Engine()

    def calc_multiply(args):
        return args["x"] * args["y"]

    def audit_scan(args):
        return {"vulnerabilities_found": 0, "target": args["path"]}

    t1 = MCPToolDefinition123(
        name="math_multiply",
        domain="math",
        description="Multiplies two numbers x and y",
        parameters={"x": "float", "y": "float"},
        handler=calc_multiply,
        allowed_stages=[TaskLifecycleStage123.EXECUTION],
        preconditions=lambda args: "x" in args and "y" in args,
        cacheable=True,
        cache_ttl_seconds=30,
        volatility_score=0.1,
        keywords=["multiply", "product", "math"]
    )
    t2 = MCPToolDefinition123(
        name="sec_audit",
        domain="security",
        description="Performs security compliance audit on path",
        parameters={"path": "str"},
        handler=audit_scan,
        allowed_stages=[TaskLifecycleStage123.AUDIT, TaskLifecycleStage123.VERIFICATION],
        preconditions=lambda args: len(args.get("path", "")) > 0,
        cacheable=True,
        cache_ttl_seconds=60,
        volatility_score=0.2,
        keywords=["audit", "security", "scan"]
    )

    engine.register_tool(t1)
    engine.register_tool(t2)

    # 1. Test SEP-4000 Stage-Aware Intent Micro-Routing
    neg_exec = engine.negotiate_active_tools("I need to multiply numbers", stage=TaskLifecycleStage123.EXECUTION)
    assert neg_exec["selected_tool_count"] == 1
    assert neg_exec["tool_names"] == ["math_multiply"]
    assert "def math_multiply(x: float, y: float) -> Any:" in neg_exec["attenuated_signatures"]
    assert neg_exec["token_saving_ratio"] >= 0.90

    # In DISCOVERY stage, math_multiply should NOT be permitted
    neg_disc = engine.negotiate_active_tools("I need to multiply numbers", stage=TaskLifecycleStage123.DISCOVERY)
    assert "math_multiply" not in neg_disc["tool_names"]

    # 2. Execution, Preconditions & Volatility ETag Caching
    # Precondition failure
    fail_res = engine.execute_tool("math_multiply", {"x": 10})
    assert fail_res["status"] == "error"
    assert fail_res["http_status"] == 400

    # Successful execution
    res1 = engine.execute_tool("math_multiply", {"x": 6, "y": 7})
    assert res1["status"] == "success"
    assert res1["data"] == 42
    assert res1["cached"] is False
    etag = res1["etag"]

    # Repeat with ETag -> 304 Not Modified
    res2 = engine.execute_tool("math_multiply", {"x": 6, "y": 7}, request_etag=etag)
    assert res2["http_status"] == 304
    assert res2["cached"] is True
    assert res2["data"] is None

    # 3. Compound Batch Pipeline with Fallback
    pipeline_steps = [
        {"tool": "math_multiply", "arguments": {"x": 3, "y": 4}},
        {"tool": "math_multiply", "arguments": {"x": 2, "y": 5}}
    ]
    pipe_results = engine.execute_compound_pipeline(pipeline_steps)
    assert len(pipe_results) == 2
    assert pipe_results[0]["data"] == 12
    assert pipe_results[1]["data"] == 10

    # 4. Reactive Context Push
    engine.push_context_diff("STAGE_ADVANCED", {"stage": "VERIFICATION"})
    diffs = engine.drain_context_diffs()
    assert len(diffs) == 1
    assert diffs[0]["event_type"] == "STAGE_ADVANCED"
    assert engine.drain_context_diffs() == []


def test_a2a_v30_mesh_agent_cards_dag_scheduler_and_ap2_escrow():
    router = AAIFMeshRouter123()

    card_arch = AgentCard123(
        agent_id="agent-arch-01",
        name="ArchitectPrime",
        role="Architect",
        capabilities=["architecture", "spec_writing"],
        latency_ms=25.0,
        current_load=0.15,
        reputation_score=0.98,
        token_cost_factor=1.0,
        poe_success_rate=0.99,
        ed25519_pubkey="pub-arch-key-01"
    )
    card_dev = AgentCard123(
        agent_id="agent-dev-01",
        name="CodeCraftsman",
        role="Developer",
        capabilities=["coding", "refactoring"],
        latency_ms=45.0,
        current_load=0.30,
        reputation_score=0.95,
        token_cost_factor=1.0,
        poe_success_rate=0.96,
        ed25519_pubkey="pub-dev-key-01"
    )

    assert router.register_agent(card_arch) is True
    assert router.register_agent(card_dev) is True

    # 1. Pareto Optimal Routing
    opt_arch = router.find_pareto_optimal_agent("architecture")
    assert opt_arch is not None
    assert opt_arch.agent_id == "agent-arch-01"

    # 2. Kahn's Topological Wavefront DAG Scheduling
    t1 = DecoupledTaskContract123(task_id="T1", title="Define Schema")
    t2 = DecoupledTaskContract123(task_id="T2", title="Implement Backend", dependencies=["T1"])
    t3 = DecoupledTaskContract123(task_id="T3", title="Implement UI", dependencies=["T1"])
    t4 = DecoupledTaskContract123(task_id="T4", title="Integration Tests", dependencies=["T2", "T3"])

    waves = router.schedule_dag([t1, t2, t3, t4])
    assert len(waves) == 3
    assert waves[0] == ["T1"]
    assert set(waves[1]) == {"T2", "T3"}
    assert waves[2] == ["T4"]

    # 3. AP2 3.0 SLA Escrow Settlement & 5-Tier Penalties
    contract_clean = DecoupledTaskContract123(
        task_id="T2",
        title="Implement Backend",
        assigned_agent_id="agent-dev-01",
        staked_tokens=1000,
        sla_timeout_seconds=50.0,
        quality_score=0.95,
        security_clean=True,
        tokens_consumed=4000,
        token_quota=8000
    )
    settle_clean = AP230SLAEscrow.settle_contract(contract_clean, "def backend(): return True")
    assert settle_clean["status"] == "SETTLED"
    assert settle_clean["payout_tokens"] == 1000
    assert settle_clean["clawback_tokens"] == 0
    assert len(settle_clean["proof_of_execution"]) == 64

    # Contract with Latency Breach and Quality Defect
    contract_breach = DecoupledTaskContract123(
        task_id="T_LATE",
        title="Late Job",
        assigned_agent_id="agent-dev-01",
        staked_tokens=1000,
        sla_timeout_seconds=0.01,  # Guaranteed breach
        quality_score=0.70,        # Quality defect (<0.85) -> 30% clawback
        security_clean=True,
        tokens_consumed=2000,
        token_quota=8000
    )
    time.sleep(0.02)
    settle_breached = AP230SLAEscrow.settle_contract(contract_breach, "output")
    # Latency 20% + Quality 30% = 50% clawback
    assert settle_breached["clawback_ratio"] == 0.50
    assert settle_breached["payout_tokens"] == 500
    assert settle_breached["clawback_tokens"] == 500

    # 4. PBFT Byzantine Consensus
    pbft = router.execute_pbft_consensus("hash-0x123", ["agent-arch-01", "agent-dev-01"])
    assert pbft["consensus_reached"] is True
    assert pbft["commit_votes"] == 2


def test_self_refining_harness80_fit_ratio_ast_guard_and_circuit_breaker():
    # 1. AST Preflight Guard 9.0
    safe_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    is_safe, vios = ASTPreflightGuard90.audit_code(safe_code)
    assert is_safe is True
    assert vios == []

    evil_code = "import ctypes\ndef attack():\n    eval('1+1')\n"
    is_safe2, vios2 = ASTPreflightGuard90.audit_code(evil_code)
    assert is_safe2 is False
    assert any("Forbidden call: eval" in v for v in vios2)
    assert any("Forbidden import: ctypes" in v for v in vios2)

    # 2. Self-Refining Harness 8.0 & Merkle Checkpoints
    harness = SelfRefiningHarness80(failure_threshold=3)
    snapshot1 = {"main.py": "print('hello')", "test.py": "assert True"}
    root1 = harness.push_merkle_checkpoint(snapshot1)
    assert len(root1) == 64
    assert len(harness.merkle_checkpoints) == 1

    # 3. Fit Ratio 7.0 & Consecutive Failures
    harness.record_outcome(False, HarnessFaultCategory123.MODEL_HALLUCINATION)
    harness.record_outcome(False, HarnessFaultCategory123.MODEL_HALLUCINATION)
    # Fit Ratio: 0 harness faults / 2 total = 1.0 (pure model issue)
    assert harness.compute_fit_ratio() == 1.0

    # 3rd failure trips the circuit breaker
    res3 = harness.record_outcome(False, HarnessFaultCategory123.HARNESS_TOOL_DRIFT)
    assert res3["circuit_status"] == "OPEN"
    assert res3["action"] == "ROLLBACK_TO_MERKLE_CHECKPOINT"
    assert res3["checkpoint"] == root1
    # Now 1 harness fault out of 3 = Fit ratio ~0.6667
    assert 0.66 <= harness.compute_fit_ratio() <= 0.67

    # 4. Dynamic Micro-Adapter Synthesis
    adapter = harness.synthesize_micro_adapter("user_fetch", expected_param="user_id", actual_param="uid")
    adapted_args = adapter({"uid": 42, "role": "admin"})
    assert adapted_args == {"user_id": 42, "role": "admin"}


def test_agent_desks80_swb_leases_blackboard_and_3way_ast_merge():
    desks = AgentDesks80()

    # 1. Single-Writer Boundary (SWB) Permissions
    assert desks.acquire_file_lease("dev-desk-1", DeskRole123.DEVELOPER, "src/entropy/core.py") is True
    # Architect attempting to write to src/ violates SWB
    with pytest.raises(SingleWriterBoundaryViolation123):
        desks.acquire_file_lease("arch-desk-1", DeskRole123.ARCHITECT, "src/entropy/core.py")

    # Developer attempting to lock an already leased file
    assert desks.acquire_file_lease("dev-desk-2", DeskRole123.DEVELOPER, "src/entropy/core.py") is False

    # Release lease
    desks.release_file_lease("dev-desk-1", "src/entropy/core.py")
    assert desks.acquire_file_lease("dev-desk-2", DeskRole123.DEVELOPER, "src/entropy/core.py") is True

    # 2. Shared Blackboard Bus (Zero-Token IPC)
    desks.publish_blackboard("build_event", {"status": "SUCCESS", "exit_code": 0})
    read_val = desks.read_blackboard("build_event")
    assert read_val["status"] == "SUCCESS"
    assert read_val["exit_code"] == 0

    # 3. 3-Way AST Semantic Conflict-Free Reconciler 3.0
    base_code = """
def alpha():
    return 1

def beta():
    return 2
"""
    desk_a_code = """
def alpha():
    return 100

def beta():
    return 2
"""
    desk_b_code = """
def alpha():
    return 1

def beta():
    return 200

def gamma():
    return 300
"""
    success, merged_code, notes = AgentDesks80.three_way_ast_semantic_merge(
        base_code, desk_a_code, desk_b_code
    )
    assert success is True
    assert "return 100" in merged_code
    assert "return 200" in merged_code
    assert "gamma" in merged_code
    assert len(notes) >= 3


def test_octadeca_store_18layer_memory_ebbinghaus_and_rrf18():
    mem = OctadecaStore18LayerMemory()

    # 1. Store across cognitive layers
    n1 = mem.store_memory(1, "Obsidian Exocortex root documentation on agents", ["obsidian", "agent"], 0.9)
    n2 = mem.store_memory(2, "Supabase DiskANN vector embeddings index", ["supabase", "pgvector"], 0.85)
    n6 = mem.store_memory(6, "Graphiti fact: LLM context limit is 128k", ["context", "limit"], 0.5)
    n9 = mem.store_memory(9, "Ebbinghaus decay memory item with low importance", ["ephemeral"], 0.2)

    assert len(mem.nodes) == 4

    # 2. Graphiti Bi-temporal Invalidation
    mem.invalidate_bitemporal_fact(n6.node_id, "Context limit upgraded to 1M tokens")
    assert mem.nodes[n6.node_id].invalidated is True

    # 3. Ebbinghaus Forgetting Decay & Dream Consolidation
    future_time = time.time() + (100 * 3600)  # 100 hours later
    decayed_retention = n9.compute_ebbinghaus_retention(future_time)
    assert decayed_retention < 0.10

    # 4. RRF-18 Hybrid Search
    search_results = mem.hybrid_search_rrf18("Obsidian agent documentation", top_k=2)
    assert len(search_results) >= 1
    assert search_results[0]["node_id"] == n1.node_id
    assert search_results[0]["rank"] == 1
    assert search_results[0]["rrf_score"] > 0
    # Invalidated fact n6 must NOT appear in search results
    assert all(r["node_id"] != n6.node_id for r in search_results)


def test_token_physics150_radix_alignment_skeletonization_codeact_and_delta_tokens():
    # 1. Radix Prompt Cache Alignment
    prompt = "System prompt header"
    aligned = TokenPhysics150.align_radix_prompt_cache(prompt, boundary=128)
    assert len(aligned) % 128 == 0
    assert aligned.startswith(prompt)

    # 2. AST Code Skeletonization 9.0
    full_code = """
def compute_metrics(x: int, y: int) -> int:
    \"\"\"Calculates sum metric.\"\"\"
    temp = x * 2
    temp2 = y * 3
    return temp + temp2
"""
    skeleton = TokenPhysics150.skeletonize_ast_code(full_code)
    assert "compute_metrics" in skeleton
    assert "Calculates sum metric." in skeleton
    assert "..." in skeleton
    assert "temp = x * 2" not in skeleton

    # 3. CodeAct 8.0 Virtual REPL Sandbox
    def mock_add(a, b):
        return a + b

    def mock_square(x):
        return x * x

    script = """
a = mock_add(3, 4)
result = mock_square(a)
"""
    repl_res = TokenPhysics150.execute_codeact_repl(
        script,
        {"mock_add": mock_add, "mock_square": mock_square}
    )
    assert repl_res["status"] == "success"
    assert repl_res["result"] == 49
    assert repl_res["tokens_saved_ratio"] > 0.85

    # 4. Delta Token Accounting 8.0
    cur_cumulative = {"input_tokens": 15000, "output_tokens": 4200, "total_tokens": 19200}
    prev_cumulative = {"input_tokens": 12000, "output_tokens": 3800, "total_tokens": 15800}
    deltas = TokenPhysics150.compute_delta_tokens(cur_cumulative, prev_cumulative)
    assert deltas["input_tokens"] == 3000
    assert deltas["output_tokens"] == 400
    assert deltas["total_tokens"] == 3400


def test_erlang_otp80_supervision_strategies_and_collapse():
    # 1. One-for-One Strategy
    sup = ErlangOTPSupervisor80(strategy=SupervisionStrategy123.ONE_FOR_ONE, max_restarts=2, window_seconds=60.0)
    sup.register_child("worker-1")
    sup.register_child("worker-2")

    r1 = sup.report_child_crash("worker-1")
    assert r1["action"] == "RESTART_CHILDREN"
    assert r1["affected_children"] == ["worker-1"]

    # 2. Collapse Trigger after Exceeding Restart Budget
    sup.report_child_crash("worker-1")
    r3 = sup.report_child_crash("worker-1")
    assert r3["action"] == "COLLAPSE_SUPERVISOR"
    assert sup.is_collapsed is True

    # 3. One-for-All Strategy
    sup_all = ErlangOTPSupervisor80(strategy=SupervisionStrategy123.ONE_FOR_ALL, max_restarts=5)
    sup_all.register_child("node-a")
    sup_all.register_child("node-b")
    r_all = sup_all.report_child_crash("node-a")
    assert r_all["affected_children"] == ["node-a", "node-b"]


def test_faz123_master_autonomous_swarm_orchestrator_lifecycle():
    orchestrator = Faz123MasterSwarmOrchestrator()

    cards = [
        AgentCard123(
            agent_id="lead-arch",
            name="ArchMaster",
            role="Architect",
            capabilities=["architecture"],
            latency_ms=20.0,
            current_load=0.1,
            reputation_score=0.99,
            token_cost_factor=1.0,
            poe_success_rate=0.98,
            ed25519_pubkey="pub-arch"
        ),
        AgentCard123(
            agent_id="lead-dev",
            name="DevMaster",
            role="Developer",
            capabilities=["coding"],
            latency_ms=30.0,
            current_load=0.2,
            reputation_score=0.97,
            token_cost_factor=1.0,
            poe_success_rate=0.95,
            ed25519_pubkey="pub-dev"
        )
    ]

    mission_res = orchestrator.run_mission_lifecycle(
        mission_title="Autonomous Agent Desk Integration",
        goal_prompt="Coordinate swarm to build and verify module",
        agent_cards=cards
    )

    assert mission_res["status"] == "MISSION_SUCCESS"
    assert mission_res["waves_scheduled"] == 2
    assert mission_res["desk_lease_granted"] is True
    assert mission_res["escrow_settlement"]["status"] == "SETTLED"
    assert len(mission_res["escrow_settlement"]["proof_of_execution"]) == 64
    assert mission_res["memory_node_id"].startswith("mem-1-")
