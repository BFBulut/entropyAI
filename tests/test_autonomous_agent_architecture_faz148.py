"""
Unit & Integration Test Suite for Faz 148 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 22.0 Stateless Gateway, ETag 304, MRTR 206, MCP Apps Widget, Saga Rollback
2. AST Preflight Guard 34.0 (Safe syntax, banned imports, dangerous calls, reflection, traversal)
3. Merkle Checkpoint Forest 12.0 (Filesystem snapshots and zero-loss rollback)
4. Speculative MCTS Evaluator (Tree-of-Thoughts / UCB-1 candidate selection)
5. Dynamic Deterministic Temperature Cooling Schedule (T -> 0.0)
6. Decoupled Task Contract 18.0 & Atomic CAS Heartbeat Lease Zombie Takeover
7. Linda Distributed Tuple Space 26.0 (Out, Rd, In, Collect)
8. Multi-Granular Single-Writer Boundary (MG-SWB 19.0)
9. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 22.0
10. AAIF A2A Protocol v1.0.0 / v3.2 Federation Router & Agent Card Signatures
11. HippoRAG 2 Dual-Node Personalized PageRank (PPR) Multi-Hop Associative Walk
12. BiTemporal Graphiti Memory 4.2 (Fact invalidation and time-travel querying)
13. Extreme Token Physics 40.0 (AST Skeletonizer 34.0, Radix KV Block Alignment, Marginal Delta Token Accounting)
14. Faz148MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz148 import (
    FastMCPGateway,
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPAppWidget,
    ASTPreflightGuard34,
    MerkleCheckpointForest12,
    SpeculativeMCTSEvaluator,
    DynamicDeterministicCooling,
    TaskState,
    DecoupledTaskContract18,
    DecoupledTaskManager,
    LindaTupleSpace26,
    AgentDesk30,
    MultiGranularSingleWriterBoundary,
    KahnDAGWavefrontScheduler22,
    DAGTaskNode,
    AgentCard148,
    A2AFederationRouter,
    HippoRAG2PersonalizedPageRank,
    BiTemporalGraphitiMemory,
    ASTSkeletonizer34,
    RadixKVCacheAligner,
    MarginalDeltaTokenAccountant,
    Faz148MasterSwarmOrchestrator,
    MCTSNode,
)


# ==============================================================================
# 1. FASTMCP 22.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp22_stateless_gateway():
    gateway = FastMCPGateway(secret_key="test-key-2026")

    app_widget = FastMCPAppWidget(
        app_id="calc-ui",
        title="Interactive Calculator",
        component_type="form",
        schema_fields={"a": "integer", "b": "integer"}
    )

    reverted = []
    def calc_revert(a: int, b: int):
        reverted.append((a, b))

    gateway.register_tool(
        name="add_numbers",
        description="Adds two numbers",
        schema={"properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]},
        handler=lambda a, b: a + b,
        compensation_handler=calc_revert,
        app_widget=app_widget
    )

    # 1. Successful invocation
    headers = FastMCPHeaders(mcp_name="add_numbers", mcp_idempotency_key="idemp-1")
    res = gateway.invoke(headers, {"a": 10, "b": 20})
    assert res["status"] == 200
    assert res["result"] == 30
    assert res["etag"] is not None
    assert res["app_widget"]["app_id"] == "calc-ui"

    # 2. ETag Caching (304)
    res_cached = gateway.invoke(headers, {"a": 10, "b": 20})
    assert res_cached["status"] == 304
    assert res_cached["cached"] is True

    # 3. MRTR 206 Input Required elicitation
    res_missing = gateway.invoke(FastMCPHeaders(mcp_name="add_numbers"), {"a": 10})
    assert res_missing["status"] == 206
    assert res_missing["stage"] == "input_required"
    assert "b" in res_missing["missing_parameters"]

    # 4. Zero-shot stubs
    stubs = gateway.generate_zero_shot_stubs()
    assert "def add_numbers(a, b): ..." in stubs

    # 5. Saga Compensation LIFO Rollback
    rolled = gateway.rollback_saga()
    assert len(rolled) == 1
    assert rolled[0]["tool"] == "add_numbers"
    assert rolled[0]["status"] == "reverted"
    assert reverted == [(10, 20)]


# ==============================================================================
# 2. AST PREFLIGHT GUARD 34.0 TESTS
# ==============================================================================

def test_ast_preflight_guard_34():
    safe_code = """
def calculate_metrics(values: list[float]) -> dict:
    total = sum(values)
    mean = total / len(values) if values else 0.0
    return {"total": total, "mean": mean}
"""
    is_safe, err = ASTPreflightGuard34.inspect_code(safe_code)
    assert is_safe is True
    assert err is None

    # Dangerous: Banned import
    bad_code1 = "import subprocess\nsubprocess.run(['rm', '-rf', '/'])"
    is_safe, err = ASTPreflightGuard34.inspect_code(bad_code1)
    assert is_safe is False
    assert "Banned import: subprocess" in err

    # Dangerous: eval()
    bad_code2 = "eval('__import__(\"os\").system(\"calc\")')"
    is_safe, err = ASTPreflightGuard34.inspect_code(bad_code2)
    assert is_safe is False
    assert "Banned builtin call" in err

    # Dangerous: Directory traversal string literal
    bad_code3 = "path = '../../etc/passwd'"
    is_safe, err = ASTPreflightGuard34.inspect_code(bad_code3)
    assert is_safe is False
    assert "Directory traversal pattern" in err

    # Dangerous: Reflection introspection
    bad_code4 = "cls = ().__class__.__bases__[0].__subclasses__()"
    is_safe, err = ASTPreflightGuard34.inspect_code(bad_code4)
    assert is_safe is False
    assert "Forbidden reflection" in err


# ==============================================================================
# 3. MERKLE CHECKPOINT FOREST 12.0 TESTS
# ==============================================================================

def test_merkle_checkpoint_forest_12():
    forest = MerkleCheckpointForest12()
    v1_files = {
        "src/main.py": "print('hello v1')",
        "src/util.py": "def f(): return 1",
    }
    root1 = forest.create_checkpoint("cp-1", v1_files)
    assert len(root1) == 64

    # Mutate files
    v2_files = {
        "src/main.py": "print('hello v2')",
        "src/util.py": "def f(): return 2",
    }
    root2 = forest.create_checkpoint("cp-2", v2_files)
    assert root1 != root2

    # Rollback to cp-1
    restored = forest.rollback("cp-1")
    assert restored["src/main.py"] == "print('hello v1')"
    assert restored["src/util.py"] == "def f(): return 1"


# ==============================================================================
# 4. SPECULATIVE MCTS EVALUATOR TESTS
# ==============================================================================

def test_speculative_mcts_evaluator():
    evaluator = SpeculativeMCTSEvaluator(exploration_constant=1.414)
    root = MCTSNode(state_desc="root")

    candidates = [
        ("branch_a_refactor", 0.75),
        ("branch_b_direct", 0.95),
        ("branch_c_experimental", 0.60),
    ]

    best_action, best_score = evaluator.select_best_candidate(root, candidates)
    # First selection under UCB1 initializes children
    assert len(root.children) == 3
    assert best_action in ["branch_a_refactor", "branch_b_direct", "branch_c_experimental"]


# ==============================================================================
# 5. DYNAMIC DETERMINISTIC COOLING TESTS
# ==============================================================================

def test_dynamic_deterministic_cooling():
    cooling = DynamicDeterministicCooling(t0=0.70, alpha=0.82, min_temp=0.01)
    t_0 = cooling.get_temperature(0)
    t_1 = cooling.get_temperature(1)
    t_5 = cooling.get_temperature(5)
    t_20 = cooling.get_temperature(20)

    assert pytest.approx(t_0, rel=1e-3) == 0.70
    assert pytest.approx(t_1, rel=1e-3) == 0.574
    assert t_5 < t_1
    assert t_20 >= 0.01


# ==============================================================================
# 6. DECOUPLED TASK CONTRACT & ATOMIC CAS TESTS
# ==============================================================================

def test_decoupled_task_contract_and_zombie():
    mgr = DecoupledTaskManager()
    task = mgr.create_task("T-1", "Implement Storage")
    assert task.state == TaskState.UNASSIGNED
    assert task.cas_version == 1

    # Successful acquisition
    ok = mgr.acquire_task("T-1", "agent-alpha", expected_version=1)
    assert ok is True
    assert task.state == TaskState.ACQUIRED
    assert task.cas_version == 2

    # Failed acquisition due to CAS version mismatch
    ok2 = mgr.acquire_task("T-1", "agent-beta", expected_version=1)
    assert ok2 is False

    # Simulate heartbeat timeout
    task.lease_heartbeat = time.time() - 20.0
    task.lease_ttl = 10.0

    zombies = mgr.sweep_zombies()
    assert "T-1" in zombies
    assert task.state == TaskState.ZOMBIE_RECOVERED
    assert task.assigned_agent is None

    # Re-acquire by healer agent
    ok_heal = mgr.acquire_task("T-1", "agent-healer", expected_version=3)
    assert ok_heal is True
    assert task.state == TaskState.ACQUIRED


# ==============================================================================
# 7. LINDA DISTRIBUTED TUPLE SPACE TESTS
# ==============================================================================

def test_linda_tuple_space_26():
    ts = LindaTupleSpace26()
    ts.out(("task_spec", "auth_module", "v1.0"))
    ts.out(("task_spec", "billing_module", "v1.0"))
    ts.out(("telemetry", "cpu_load", 0.42))

    # Read without removing
    read_item = ts.rd(("task_spec", None, "v1.0"))
    assert read_item is not None
    assert read_item[0] == "task_spec"

    # Collect matching
    all_specs = ts.collect(("task_spec", None, "v1.0"))
    assert len(all_specs) == 2

    # Atomically remove
    consumed = ts.in_tuple(("telemetry", "cpu_load", None))
    assert consumed == ("telemetry", "cpu_load", 0.42)
    assert ts.rd(("telemetry", "cpu_load", None)) is None


# ==============================================================================
# 8. MULTI-GRANULAR SINGLE-WRITER BOUNDARY TESTS
# ==============================================================================

def test_single_writer_boundary():
    swb = MultiGranularSingleWriterBoundary()
    f = "src/entropy/core.py"

    # Agent 1 acquires file
    assert swb.acquire_file(f, "agent-1", lease_duration=5.0) is True
    assert swb.vector_clocks[f]["agent-1"] == 1

    # Agent 2 rejected
    assert swb.acquire_file(f, "agent-2", lease_duration=5.0) is False

    # Agent 1 releases
    swb.release_file(f, "agent-1")
    # Now Agent 2 can acquire
    assert swb.acquire_file(f, "agent-2", lease_duration=5.0) is True
    assert swb.vector_clocks[f]["agent-2"] == 1


# ==============================================================================
# 9. KAHN DAG WAVEFRONT & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_cpm_slack_borrowing_22():
    scheduler = KahnDAGWavefrontScheduler22()
    # A (Spec): O=1, M=2, P=3 -> Te = 2.0
    scheduler.add_node(DAGTaskNode("task_a", 1.0, 2.0, 3.0))
    # B (Code): depends on A. O=2, M=4, P=6 -> Te = 4.0
    scheduler.add_node(DAGTaskNode("task_b", 2.0, 4.0, 6.0, dependencies={"task_a"}))
    # C (Docs): depends on A. O=1, M=1, P=1 -> Te = 1.0
    scheduler.add_node(DAGTaskNode("task_c", 1.0, 1.0, 1.0, dependencies={"task_a"}))
    # D (Deploy): depends on B and C. O=1, M=2, P=3 -> Te = 2.0
    scheduler.add_node(DAGTaskNode("task_d", 1.0, 2.0, 3.0, dependencies={"task_b", "task_c"}))

    wavefronts, critical_path = scheduler.compute_schedule()

    assert wavefronts[0] == ["task_a"]
    assert sorted(wavefronts[1]) == ["task_b", "task_c"]
    assert wavefronts[2] == ["task_d"]

    # Critical path is task_a -> task_b -> task_d (Te = 2 + 4 + 2 = 8.0)
    assert critical_path == ["task_a", "task_b", "task_d"]
    assert scheduler.nodes["task_b"].allocated_model_tier == "Frontier_Deep_Reasoning"
    # task_c has positive slack
    assert scheduler.nodes["task_c"].slack > 0.0
    assert scheduler.nodes["task_c"].allocated_model_tier == "High_Throughput_Flash"


# ==============================================================================
# 10. AAIF A2A FEDERATION ROUTER & AGENT CARD TESTS
# ==============================================================================

def test_a2a_federation_router():
    router = A2AFederationRouter(secret="test-a2a-secret")

    card_fast = AgentCard148(
        agent_id="agent-flash",
        name="Fast Flash Agent",
        capabilities=["code_refactor", "syntax_lint"],
        accuracy_score=0.92,
        latency_ms=80.0,
        cost_per_1k_tokens=0.0005
    )
    card_pro = AgentCard148(
        agent_id="agent-pro",
        name="Pro Reasoning Agent",
        capabilities=["code_refactor", "security_audit", "formal_proof"],
        accuracy_score=0.99,
        latency_ms=650.0,
        cost_per_1k_tokens=0.015
    )

    sig_fast = router.register_agent(card_fast)
    sig_pro = router.register_agent(card_pro)

    assert len(sig_fast) == 64
    assert len(sig_pro) == 64

    # Route with latency priority
    routed_fast = router.route_9d_pareto("code_refactor", prefer_latency=True)
    assert routed_fast.agent_id == "agent-flash"

    # Route with accuracy priority
    routed_pro = router.route_9d_pareto("code_refactor", prefer_latency=False)
    assert routed_pro.agent_id == "agent-pro"


# ==============================================================================
# 11. HIPPORAG 2 PERSONALIZED PAGERANK TESTS
# ==============================================================================

def test_hipporag2_personalized_pagerank():
    ppr = HippoRAG2PersonalizedPageRank(damping=0.85)
    ppr.add_edge("Harness", "ASTGuard")
    ppr.add_edge("ASTGuard", "Sandbox")
    ppr.add_edge("Harness", "MCTS")
    ppr.add_edge("MCTS", "MerkleForest")

    scores = ppr.run_ppr(["Harness"], iterations=30)
    assert "Harness" in scores
    assert "ASTGuard" in scores
    assert scores["Harness"] > scores["Sandbox"]


# ==============================================================================
# 12. BITEMPORAL GRAPHITI MEMORY TESTS
# ==============================================================================

def test_bitemporal_graphiti_memory():
    mem = BiTemporalGraphitiMemory()
    mem.assert_fact("database", "engine", "SQLite", valid_from=10.0)
    time.sleep(0.01)
    mem.assert_fact("database", "engine", "Supabase_pgvector", valid_from=50.0)

    # Time travel query
    engine_t20 = mem.query_as_of("database", "engine", 20.0)
    engine_t60 = mem.query_as_of("database", "engine", 60.0)

    assert engine_t20 == "SQLite"
    assert engine_t60 == "Supabase_pgvector"


# ==============================================================================
# 13. EXTREME TOKEN PHYSICS TESTS
# ==============================================================================

def test_ast_skeletonizer_and_token_physics():
    raw_code = """
def long_computation(x: int, y: int) -> int:
    '''Calculates exponential power.'''
    res = 1
    for _ in range(y):
        res *= x
    return res
"""
    skeleton = ASTSkeletonizer34.skeletonize(raw_code)
    assert "Calculates exponential power" in skeleton
    assert "pass" in skeleton
    assert "for _ in range(y):" not in skeleton

    # Radix KV-Cache block alignment
    aligner = RadixKVCacheAligner(block_size=64)
    aligned = aligner.align_text("Hello World System Instructions")
    assert len(aligned) >= len("Hello World System Instructions")

    # Marginal Delta Token Accounting
    accountant = MarginalDeltaTokenAccountant()
    din1, dout1 = accountant.compute_delta(500, 100)
    assert din1 == 500
    assert dout1 == 100

    din2, dout2 = accountant.compute_delta(750, 180)
    assert din2 == 250
    assert dout2 == 80


# ==============================================================================
# 14. FAZ 148 MASTER SWARM ORCHESTRATOR PIPELINE
# ==============================================================================

def test_faz148_master_orchestrator():
    orchestrator = Faz148MasterSwarmOrchestrator()
    res = orchestrator.run_e2e_verification()

    assert res["status"] == "Faz148_Verified"
    assert "compile_code" in res["fastmcp_tools"]
    assert len(res["critical_path"]) > 0
    assert res["task_acquired"] is True
    assert res["code_safety"] is True
    assert res["lead_t150"] == "Alice"
    assert res["lead_t250"] == "Bob"
    assert res["delta_turn_2"] == (500, 150)
