"""
Unit & Integration Test Suite for Faz 146 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 20.0 Stateless Gateway, ETag 304, MRTR 206, MCP Apps Widget, Saga Rollback
2. AST Preflight Guard 32.0 (Safe syntax, banned imports, dangerous calls, reflection, traversal)
3. Merkle Checkpoint Forest 10.0 (Filesystem snapshots and zero-loss rollback)
4. Speculative MCTS Evaluator (Tree-of-Thoughts / UCB-1 candidate selection)
5. Dynamic Deterministic Temperature Cooling Schedule (T -> 0.0)
6. Decoupled Task Contract 16.0 & Atomic CAS Heartbeat Lease Zombie Takeover
7. Linda Distributed Tuple Space 24.0 (Out, Rd, In, Collect)
8. Multi-Granular Single-Writer Boundary (MG-SWB)
9. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 20.0
10. AAIF A2A Protocol v1.0.0 Federation Router & Agent Card Signatures
11. HippoRAG 2 Dual-Node Personalized PageRank (PPR) Multi-Hop Associative Walk
12. BiTemporal Graphiti Memory 4.0 (Fact invalidation and time-travel querying)
13. Extreme Token Physics 38.0 (AST Skeletonizer 32.0, Radix KV Block Alignment, Marginal Delta Token Accounting)
14. Faz146MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz146 import (
    FastMCPGateway,
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPAppWidget,
    ASTPreflightGuard32,
    MerkleCheckpointForest10,
    SpeculativeMCTSEvaluator,
    DynamicDeterministicCooling,
    TaskState,
    DecoupledTaskContract16,
    DecoupledTaskManager,
    LindaTupleSpace24,
    AgentDesk28,
    MultiGranularSingleWriterBoundary,
    KahnDAGWavefrontScheduler20,
    AgentCard146,
    A2AFederationRouter,
    HippoRAG2PersonalizedPageRank,
    BiTemporalGraphitiMemory,
    ASTSkeletonizer32,
    RadixKVCacheAligner,
    MarginalDeltaTokenAccountant,
    Faz146MasterSwarmOrchestrator,
)


# ==============================================================================
# 1. FASTMCP 20.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp20_stateless_gateway():
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

    # 4. Saga Compensation LIFO Rollback
    rolled = gateway.rollback_saga()
    assert "add_numbers" in rolled
    assert len(reverted) == 1
    assert reverted[0] == (10, 20)


# ==============================================================================
# 2. AST PREFLIGHT GUARD 32.0 TESTS
# ==============================================================================

def test_ast_preflight_guard_32():
    # 1. Safe code
    safe_code = """
def factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    is_safe, violations = ASTPreflightGuard32.inspect(safe_code)
    assert is_safe is True
    assert len(violations) == 0

    # 2. Banned imports
    bad_import_code = "import subprocess\nsubprocess.run(['ls'])"
    is_safe, violations = ASTPreflightGuard32.inspect(bad_import_code)
    assert is_safe is False
    assert any("subprocess" in v for v in violations)

    # 3. Banned dangerous calls
    eval_code = "result = eval('2 + 2')"
    is_safe, violations = ASTPreflightGuard32.inspect(eval_code)
    assert is_safe is False
    assert any("eval" in v for v in violations)

    # 4. Reflection inspection
    reflect_code = "x = ().__class__.__subclasses__()"
    is_safe, violations = ASTPreflightGuard32.inspect(reflect_code)
    assert is_safe is False
    assert any("__subclasses__" in v for v in violations)

    # 5. Directory traversal pattern
    traversal_code = "path = '../../etc/passwd'"
    is_safe, violations = ASTPreflightGuard32.inspect(traversal_code)
    assert is_safe is False
    assert any("traversal" in v.lower() for v in violations)


# ==============================================================================
# 3. MERKLE CHECKPOINT FOREST 10.0 & ROLLBACK TESTS
# ==============================================================================

def test_merkle_checkpoint_forest_10():
    forest = MerkleCheckpointForest10()
    files_v1 = {"main.py": "print('hello')", "config.json": "{'version': 1}"}
    files_v2 = {"main.py": "print('corrupted')", "config.json": "{'version': 2}"}

    root_v1 = forest.create_checkpoint("cp-1", files_v1)
    root_v2 = forest.create_checkpoint("cp-2", files_v2)

    assert root_v1 != root_v2
    assert len(root_v1) == 64  # SHA-256 hex length

    # Rollback to cp-1
    restored = forest.rollback("cp-1")
    assert restored is not None
    assert restored["main.py"] == "print('hello')"
    assert restored["config.json"] == "{'version': 1}"


# ==============================================================================
# 4. SPECULATIVE MCTS EVALUATOR TESTS
# ==============================================================================

def test_speculative_mcts_evaluator():
    mcts = SpeculativeMCTSEvaluator(c_param=1.414)
    candidates = ["branch_a", "branch_b", "branch_c"]

    # Initial selection visits unvisited
    selected_1 = mcts.select_best_candidate(candidates, parent_visits=1)
    assert selected_1 == "branch_a"
    mcts.record_outcome("branch_a", reward=0.8)

    selected_2 = mcts.select_best_candidate(candidates, parent_visits=2)
    assert selected_2 == "branch_b"
    mcts.record_outcome("branch_b", reward=0.2)

    selected_3 = mcts.select_best_candidate(candidates, parent_visits=3)
    assert selected_3 == "branch_c"
    mcts.record_outcome("branch_c", reward=0.1)

    # Now all visited: branch_a should have highest UCB
    selected_4 = mcts.select_best_candidate(candidates, parent_visits=4)
    assert selected_4 == "branch_a"


# ==============================================================================
# 5. DYNAMIC DETERMINISTIC COOLING TESTS
# ==============================================================================

def test_dynamic_deterministic_cooling():
    t0 = DynamicDeterministicCooling.get_temperature(0, t0=0.70, alpha=0.85)
    t1 = DynamicDeterministicCooling.get_temperature(1, t0=0.70, alpha=0.85)
    t5 = DynamicDeterministicCooling.get_temperature(5, t0=0.70, alpha=0.85)
    t50 = DynamicDeterministicCooling.get_temperature(50, t0=0.70, alpha=0.85, t_min=0.01)

    assert t0 == 0.70
    assert t1 == pytest.approx(0.70 * 0.85)
    assert t5 < t1
    assert t50 == 0.01  # Clamped to t_min


# ==============================================================================
# 6. DECOUPLED TASK CONTRACT & ZOMBIE RECOVERY TESTS
# ==============================================================================

def test_decoupled_task_contract_and_zombie_recovery():
    mgr = DecoupledTaskManager()
    task = mgr.create_task("T-1", "Refactor Engine", "Specs for refactoring")
    task.heartbeat_ttl = 0.1  # Short TTL for test

    # 1. Acquire task
    ok = mgr.acquire_task("T-1", "agent-1")
    assert ok is True
    assert task.state == TaskState.ACQUIRED
    assert task.assigned_agent_id == "agent-1"

    # 2. Cannot re-acquire while active
    ok2 = mgr.acquire_task("T-1", "agent-2")
    assert ok2 is False

    # 3. Heartbeat refreshes lease
    hb = mgr.heartbeat("T-1", "agent-1")
    assert hb is True

    # 4. Wait for lease expiry -> Zombie Takeover by agent-2
    time.sleep(0.15)
    ok3 = mgr.acquire_task("T-1", "agent-2")
    assert ok3 is True
    assert task.state == TaskState.ZOMBIE_RECOVERED
    assert task.assigned_agent_id == "agent-2"

    # 5. Complete task
    done = mgr.complete_task("T-1", "agent-2", {"diff": "engine.py refactored"})
    assert done is True
    assert task.state == TaskState.COMPLETED
    assert task.assigned_agent_id is None


# ==============================================================================
# 7. LINDA TUPLE SPACE 24.0 TESTS
# ==============================================================================

def test_linda_tuple_space_24():
    space = LindaTupleSpace24()
    space.out(("TASK", "T-100", "PENDING", 1))
    space.out(("TASK", "T-101", "PENDING", 2))
    space.out(("SIGNAL", "REBOOT"))

    # 1. Read pattern with wildcard
    read_res = space.rd(("TASK", "T-100", None, None))
    assert read_res == ("TASK", "T-100", "PENDING", 1)

    # 2. Collect pattern
    all_tasks = space.collect(("TASK", None, "PENDING", None))
    assert len(all_tasks) == 2

    # 3. In (Take) tuple
    taken = space.in_tuple(("SIGNAL", "REBOOT"))
    assert taken == ("SIGNAL", "REBOOT")
    assert space.rd(("SIGNAL", "REBOOT")) is None


# ==============================================================================
# 8. MULTI-GRANULAR SINGLE WRITER BOUNDARY TESTS
# ==============================================================================

def test_single_writer_boundary():
    swb = MultiGranularSingleWriterBoundary()
    file_path = "c:/EntropiAI/src/main.py"

    # 1. Architecture desk acquires lock
    assert swb.acquire_lock(file_path, "Architecture") is True

    # 2. QA desk fails to acquire same lock
    assert swb.acquire_lock(file_path, "QA") is False

    # 3. Release and re-acquire
    assert swb.release_lock(file_path, "Architecture") is True
    assert swb.acquire_lock(file_path, "QA") is True


# ==============================================================================
# 9. KAHN DAG WAVEFRONT SCHEDULER & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_wavefront_scheduler_cpm():
    sched = KahnDAGWavefrontScheduler20()
    # Add tasks: name, O, M, P, deps
    sched.add_task("Spec", 1.0, 2.0, 3.0, [])
    sched.add_task("Backend", 2.0, 4.0, 6.0, ["Spec"])
    sched.add_task("Frontend", 1.0, 2.0, 3.0, ["Spec"])
    sched.add_task("Integration", 1.0, 2.0, 3.0, ["Backend", "Frontend"])

    wavefronts, project_duration, crit_sigma = sched.schedule()

    # 1. Wavefronts topology
    assert len(wavefronts) == 3
    assert wavefronts[0] == ["Spec"]
    assert set(wavefronts[1]) == {"Backend", "Frontend"}
    assert wavefronts[2] == ["Integration"]

    # 2. Critical Path and Slack Borrowing
    # Backend takes 4.0 vs Frontend 2.0. So Frontend has slack > 0
    backend_node = sched.nodes["Backend"]
    frontend_node = sched.nodes["Frontend"]
    spec_node = sched.nodes["Spec"]

    assert spec_node.slack == 0.0
    assert backend_node.slack == 0.0
    assert frontend_node.slack > 0.0  # Frontend has slack!

    assert "frontier-reasoning" in spec_node.assigned_model
    assert "frontier-reasoning" in backend_node.assigned_model
    assert "high-throughput" in frontend_node.assigned_model

    assert project_duration > 0.0
    assert crit_sigma > 0.0


# ==============================================================================
# 10. AAIF A2A FEDERATION ROUTER TESTS
# ==============================================================================

def test_aaif_a2a_federation_router():
    router = A2AFederationRouter()
    secret = "a2a-secret-test"

    card1 = AgentCard146(
        agent_id="agent-code-1",
        name="Senior Coder",
        endpoint_url="https://agent1.local/a2a",
        skills=["python", "refactoring"],
        accuracy_score=0.98,
        latency_ms=250.0
    )
    sig = card1.sign_card(secret)
    assert card1.verify_card(sig, secret) is True

    card2 = AgentCard146(
        agent_id="agent-code-2",
        name="Fast Coder",
        endpoint_url="https://agent2.local/a2a",
        skills=["python", "scripting"],
        accuracy_score=0.85,
        latency_ms=40.0
    )

    router.register(card1)
    router.register(card2)

    # Route task prioritizing accuracy
    best_acc = router.route_task("python", weight_acc=0.9, weight_lat=0.1)
    assert best_acc.agent_id == "agent-code-1"

    # Route task prioritizing latency
    best_lat = router.route_task("python", weight_acc=0.1, weight_lat=0.9)
    assert best_lat.agent_id == "agent-code-2"


# ==============================================================================
# 11. HIPPORAG 2 DUAL-NODE PERSONALIZED PAGERANK TESTS
# ==============================================================================

def test_hipporag2_personalized_pagerank():
    ppr = HippoRAG2PersonalizedPageRank(damping=0.85)
    ppr.add_edge("QueryEntity", "Passage1")
    ppr.add_edge("Passage1", "FactNodeA")
    ppr.add_edge("FactNodeA", "ConclusionNode")

    scores = ppr.compute_ppr(["QueryEntity"], max_iter=25)
    assert len(scores) == 4
    # QueryEntity and Passage1 should have the highest associative mass
    assert scores["QueryEntity"] > 0
    assert scores["Passage1"] > 0
    assert scores["ConclusionNode"] > 0


# ==============================================================================
# 12. BITEMPORAL GRAPHITI MEMORY 4.0 TESTS
# ==============================================================================

def test_bitemporal_graphiti_memory_4():
    mem = BiTemporalGraphitiMemory()
    t0 = 100.0
    t1 = 200.0
    t2 = 300.0

    # Fact 1: User works at Startup from t0 to t2
    mem.insert_fact("User", "Startup", "works_at", valid_from=t0, valid_until=t2)

    # At t1, User moves to BigTech
    mem.insert_fact("User", "BigTech", "works_at", valid_from=t1, valid_until=1000.0)

    # Query at t0 + 50 (should be Startup)
    res_early = mem.query_at("User", as_of_time=150.0)
    assert len(res_early) == 1
    assert res_early[0].target == "Startup"

    # Query at t1 + 50 (should be BigTech)
    res_late = mem.query_at("User", as_of_time=250.0)
    assert len(res_late) == 1
    assert res_late[0].target == "BigTech"


# ==============================================================================
# 13. EXTREME TOKEN PHYSICS 38.0 TESTS
# ==============================================================================

def test_extreme_token_physics_38():
    # 1. AST Skeletonization
    code = """
def heavy_worker(data: list) -> int:
    \"\"\"Processes heavy data.\"\"\"
    x = 0
    for item in data:
        x += item * 2
    return x
"""
    skeleton = ASTSkeletonizer32.skeletonize(code)
    assert "def heavy_worker(data: list) -> int:" in skeleton
    assert '"""Processes heavy data."""' in skeleton
    assert "pass" in skeleton
    assert "for item in data" not in skeleton

    # 2. Radix KV Block Alignment
    aligned = RadixKVCacheAligner.pad_to_boundary("hello world", block_size=16)
    assert len(aligned) % (16 * 4) == 0

    # 3. Marginal Delta Token Accounting
    accountant = MarginalDeltaTokenAccountant()
    d1 = accountant.calculate_turn_delta(1200)
    d2 = accountant.calculate_turn_delta(2800)
    assert d1 == 1200
    assert d2 == 1600  # 2800 - 1200


# ==============================================================================
# 14. FAZ 146 MASTER SWARM ORCHESTRATOR PIPELINE TEST
# ==============================================================================

def test_faz146_master_swarm_orchestrator():
    orchestrator = Faz146MasterSwarmOrchestrator()
    result = orchestrator.run_autonomous_pipeline()

    assert result["status"] == "OPERATIONAL_FRONTIER_146"
    assert result["fastmcp_invocation"]["status"] == 200
    assert len(result["scheduled_waves"]) >= 3
    assert result["project_duration_pert"] > 0
    assert result["task_completed"] is True
    assert result["linda_event"] == ("TASK_EVENT", "T-146", "COMPLETED")
    assert result["ast_inspection_safe"] is True
    assert result["delta_turn_tokens"] == 1700
