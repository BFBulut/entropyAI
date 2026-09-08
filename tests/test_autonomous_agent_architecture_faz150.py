"""
Unit & Integration Test Suite for Faz 150 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 24.0 Stateless Gateway, ETag 304, MRTR 206, MCP Apps Widget, Capability Check, Saga Rollback
2. AST Preflight Guard 36.0 (Safe syntax, banned imports, dangerous calls, reflection, traversal)
3. Merkle Checkpoint Forest 14.0 (Filesystem snapshots and zero-loss rollback)
4. Speculative MCTS Evaluator (Tree-of-Thoughts / UCB-1 candidate selection)
5. Dynamic Deterministic Temperature Cooling Schedule (T -> 0.0)
6. Decoupled Task Contract 20.0 & Atomic CAS Heartbeat Lease Zombie Takeover
7. Erlang-OTP 14.0 Supervision Trees (Restart intensity & DLQ escalation)
8. Linda Distributed Tuple Space 28.0 (Out, Rd, In, Collect, Watch)
9. Multi-Granular Single-Writer Boundary (MG-SWB 21.0) & Vector Clocks
10. Kahn DAG Wavefront Scheduler 24.0, Stochastic PERT & CPM Slack Borrowing
11. AAIF A2A Protocol v1.1.0 / v3.4 Federation Router, 10D Pareto Routing & PBFT Consensus
12. HippoRAG 2 Dual-Node Personalized PageRank (PPR) Multi-Hop Associative Walk
13. BiTemporal Graphiti Memory 4.4 (Fact invalidation and time-travel querying)
14. Extreme Token Physics 42.0 (AST Skeletonizer 36.0, Radix KV Block Alignment, Marginal Delta Token Accounting)
15. Faz150MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz150 import (
    FastMCPGateway,
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPAppWidget,
    ASTPreflightGuard36,
    MerkleCheckpointForest14,
    SpeculativeMCTSEvaluator,
    DynamicDeterministicCooling,
    TaskState,
    DecoupledTaskContract20,
    DecoupledTaskManager,
    ErlangOTPSupervisor14,
    SupervisionStrategy,
    LindaTupleSpace28,
    AgentDesk32,
    MultiGranularSingleWriterBoundary,
    KahnDAGWavefrontScheduler24,
    DAGTaskNode,
    AgentCard150,
    A2AFederationRouter,
    HippoRAG2PersonalizedPageRank,
    BiTemporalGraphitiMemory,
    ASTSkeletonizer36,
    RadixKVCacheAligner,
    MarginalDeltaTokenAccountant,
    Faz150MasterSwarmOrchestrator,
    MCTSNode,
)


# ==============================================================================
# 1. FASTMCP 24.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp24_stateless_gateway():
    gateway = FastMCPGateway(secret_key="test-secret-faz150")

    widget = FastMCPAppWidget(
        app_id="calc-widget",
        title="Calculator Form",
        component_type="form",
        schema_fields={"x": {"type": "integer"}, "y": {"type": "integer"}},
    )

    def multiply(x: int, y: int) -> int:
        return x * y

    def multiply_undo(x: int, y: int) -> str:
        return f"Undid multiplication of {x} and {y}"

    gateway.register_tool(
        name="multiply",
        description="Multiplies two integers",
        schema={"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
        handler=multiply,
        compensation_handler=multiply_undo,
        app_widget=widget,
        required_capability="math:multiply",
    )

    # 1.1 Capability check failure
    bad_headers = FastMCPHeaders(
        mcp_name="multiply",
        mcp_capability_token="invalid_token",
    )
    res_bad_auth = gateway.invoke(bad_headers, {"x": 5, "y": 6})
    assert res_bad_auth["status"] == 403
    assert res_bad_auth["stage"] == "auth_failure"

    # 1.2 Capability generation and success
    valid_token = gateway.generate_capability_token("math:multiply")
    good_headers = FastMCPHeaders(
        mcp_name="multiply",
        mcp_capability_token=valid_token,
        mcp_idempotency_key="req-150-1",
        mcp_transport=FastMCPTransport.ARROW_IPC,
    )
    res_ok = gateway.invoke(good_headers, {"x": 5, "y": 6})
    assert res_ok["status"] == 200
    assert res_ok["result"] == 30
    assert res_ok["app_widget"]["current_state"]["last_output"] == 30

    # 1.3 ETag 304 Not Modified
    res_cached = gateway.invoke(good_headers, {"x": 5, "y": 6})
    assert res_cached["status"] == 304
    assert res_cached["cached"] is True
    assert res_cached["result"] == 30

    # 1.4 MRTR 206 Input Required
    res_missing = gateway.invoke(good_headers, {"x": 5})
    assert res_missing["status"] == 206
    assert "y" in res_missing["missing_parameters"]

    # 1.5 Saga Rollback
    rollbacks = gateway.rollback_saga()
    assert len(rollbacks) == 1
    assert rollbacks[0]["status"] == "compensated"


# ==============================================================================
# 2. AST PREFLIGHT GUARD 36.0 TESTS
# ==============================================================================

def test_ast_preflight_guard36():
    guard = ASTPreflightGuard36()

    safe_code = """
def add(a: int, b: int) -> int:
    return a + b
"""
    res_safe = guard.inspect_code(safe_code)
    assert res_safe["safe"] is True

    unsafe_import = "import os\nos.system('dir')"
    res_import = guard.inspect_code(unsafe_import)
    assert res_import["safe"] is False
    assert any("Forbidden import" in v for v in res_import["violations"])

    unsafe_builtin = "eval('2 + 2')"
    res_builtin = guard.inspect_code(unsafe_builtin)
    assert res_builtin["safe"] is False
    assert any("eval()" in v for v in res_builtin["violations"])

    unsafe_reflection = "().__class__.__subclasses__()"
    res_refl = guard.inspect_code(unsafe_reflection)
    assert res_refl["safe"] is False
    assert any("Reflection exploit" in v for v in res_refl["violations"])


# ==============================================================================
# 3. MERKLE CHECKPOINT FOREST 14.0 TESTS
# ==============================================================================

def test_merkle_checkpoint_forest14():
    forest = MerkleCheckpointForest14()
    files_v1 = {"main.py": "print('hello v1')", "config.json": "{}"}
    root1 = forest.create_checkpoint("v1", files_v1)
    assert len(root1) == 64

    files_v2 = {"main.py": "print('hello v2')", "config.json": "{\"debug\": true}"}
    root2 = forest.create_checkpoint("v2", files_v2)
    assert root1 != root2

    restored = forest.rollback("v1")
    assert restored["main.py"] == "print('hello v1')"


# ==============================================================================
# 4. SPECULATIVE MCTS & COOLING TESTS
# ==============================================================================

def test_speculative_mcts_evaluator():
    guard = ASTPreflightGuard36()
    evaluator = SpeculativeMCTSEvaluator(guard)

    root = MCTSNode(state_id="root", code_candidate="")
    child1 = MCTSNode(state_id="c1", code_candidate="def solve(): return 42", parent=root)
    child2 = MCTSNode(state_id="c2", code_candidate="import subprocess; subprocess.Popen('sh')", parent=root)

    root.children = [child1, child2]
    root.visits = 2

    child1.visits = 1
    child1.total_reward = evaluator.evaluate_candidate(child1.code_candidate)

    child2.visits = 1
    child2.total_reward = evaluator.evaluate_candidate(child2.code_candidate)

    assert child1.total_reward > 0.5
    assert child2.total_reward == 0.0

    best = evaluator.select_best(root)
    assert best.state_id == "c1"


def test_dynamic_deterministic_cooling():
    cooling = DynamicDeterministicCooling(t0=1.0, alpha=0.8)
    t0 = cooling.get_temperature(0)
    t1 = cooling.get_temperature(1)
    t5 = cooling.get_temperature(5)
    assert t0 == 1.0
    assert abs(t1 - 0.8) < 1e-4
    assert t5 < t1


# ==============================================================================
# 5. DECOUPLED TASK CONTRACT & ZOMBIE SWEEP TESTS
# ==============================================================================

def test_decoupled_task_contract_and_zombie_sweep():
    mgr = DecoupledTaskManager()
    task = mgr.create_task("task-150-alpha", "Compile Documentation")
    assert task.state == TaskState.UNASSIGNED

    # Acquire lease
    ok = mgr.acquire_lease(task.task_id, "agent-bob", "lease-xyz")
    assert ok is True
    assert task.state == TaskState.ACQUIRED
    assert task.assigned_agent == "agent-bob"

    # Heartbeat
    hb_ok = mgr.heartbeat(task.task_id, "lease-xyz")
    assert hb_ok is True

    # Simulate lease expiry
    task.lease_expires_at = time.time() - 1.0
    swept = mgr.sweep_zombies()
    assert "task-150-alpha" in swept
    assert task.state == TaskState.ZOMBIE_RECOVERED
    assert task.assigned_agent is None


# ==============================================================================
# 6. ERLANG-OTP 14.0 SUPERVISION TESTS
# ==============================================================================

def test_erlang_otp14_supervision():
    sup = ErlangOTPSupervisor14(max_restarts=2, window_seconds=10.0)

    # First failure -> restart
    r1 = sup.record_failure("worker-1", "MemoryError")
    assert r1["action"] == "restart"

    # Second failure -> restart
    r2 = sup.record_failure("worker-1", "IndexError")
    assert r2["action"] == "restart"

    # Third failure -> exceeds max_restarts (2) -> quarantine to DLQ
    r3 = sup.record_failure("worker-1", "FatalSegfault")
    assert r3["action"] == "quarantine"
    assert len(sup.dead_letter_queue) == 1
    assert sup.dead_letter_queue[0]["worker_id"] == "worker-1"


# ==============================================================================
# 7. LINDA TUPLE SPACE 28.0 TESTS
# ==============================================================================

def test_linda_tuple_space28():
    linda = LindaTupleSpace28()
    events = []

    linda.watch(lambda t: events.append(t))

    linda.out(("job", "task-150-a", "pending"))
    linda.out(("job", "task-150-b", "completed"))
    assert len(events) == 2

    # Read non-destructive
    match = linda.rd(("job", None, "pending"))
    assert match is not None
    assert match[1] == "task-150-a"
    assert len(linda.tuples) == 2

    # Collect matching
    all_jobs = linda.collect(("job", None, None))
    assert len(all_jobs) == 2

    # In destructive
    popped = linda.in_tuple(("job", "task-150-a", None))
    assert popped is not None
    assert len(linda.tuples) == 1


# ==============================================================================
# 8. MULTI-GRANULAR SINGLE WRITER BOUNDARY & DESK TESTS
# ==============================================================================

def test_mg_swb_vector_clocks():
    mg_swb = MultiGranularSingleWriterBoundary()
    linda = LindaTupleSpace28()

    desk_code = AgentDesk32(desk_id="desk-code-150", role_name="Code", worktree_branch="desk/code/150", mg_swb=mg_swb, tuple_space=linda)
    desk_qa = AgentDesk32(desk_id="desk-qa-150", role_name="QA", worktree_branch="desk/qa/150", mg_swb=mg_swb, tuple_space=linda)

    # Code desk writes
    w1 = desk_code.execute_write("src/core.py", "def init(): pass")
    assert w1 is True
    assert mg_swb.vector_clocks["src/core.py"]["desk-code-150"] == 1

    # Concurrent write while code holds lock (simulated)
    mg_swb.acquire_writer("src/core.py", "desk-code-150")
    w2 = desk_qa.execute_write("src/core.py", "def test_core(): pass")
    assert w2 is False
    mg_swb.release_writer("src/core.py", "desk-code-150")


# ==============================================================================
# 9. KAHN DAG WAVEFRONT & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_wavefront_and_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler24()

    # Step A (1h) -> Step B (2h) -> Step D (3h)  [Total = 6h]
    # Step A (1h) -> Step C (1h) -> Step D (3h)  [Total = 5h, Slack on C = 1h]
    node_a = DAGTaskNode(task_id="A", name="Design", optimistic=1.0, most_likely=1.0, pessimistic=1.0)
    node_b = DAGTaskNode(task_id="B", name="Build Heavy", optimistic=2.0, most_likely=2.0, pessimistic=2.0)
    node_c = DAGTaskNode(task_id="C", name="Build Light", optimistic=1.0, most_likely=1.0, pessimistic=1.0)
    node_d = DAGTaskNode(task_id="D", name="Integration", optimistic=3.0, most_likely=3.0, pessimistic=3.0)

    for n in [node_a, node_b, node_c, node_d]:
        scheduler.add_node(n)

    scheduler.add_dependency("A", "B")
    scheduler.add_dependency("A", "C")
    scheduler.add_dependency("B", "D")
    scheduler.add_dependency("C", "D")

    res = scheduler.compute_critical_path_and_slack_borrowing()
    assert res["project_duration"] == 6.0
    assert "B" in res["critical_path"]
    assert "C" not in res["critical_path"]
    assert res["allocations"]["B"]["critical"] is True
    assert res["allocations"]["B"]["model_tier"] == "frontier_reasoning"
    assert res["allocations"]["C"]["critical"] is False
    assert res["allocations"]["C"]["model_tier"] == "high_throughput_flash"


# ==============================================================================
# 10. AAIF A2A FEDERATION ROUTER & PBFT CONSENSUS TESTS
# ==============================================================================

def test_a2a_federation_router_and_pbft():
    router = A2AFederationRouter()

    card_fast = AgentCard150(
        agent_id="agent-flash",
        name="Flash Specialist",
        domain="fast_code",
        capabilities=["code_gen"],
        pareto_metrics={"accuracy": 0.85, "latency": 0.1, "cost": 0.1},
    )
    card_deep = AgentCard150(
        agent_id="agent-reasoning",
        name="Deep Reasoning Specialist",
        domain="deep_arch",
        capabilities=["code_gen", "architecture"],
        pareto_metrics={"accuracy": 0.99, "latency": 0.8, "cost": 0.7},
    )

    router.register_agent(card_fast)
    router.register_agent(card_deep)

    # Prioritize accuracy
    chosen_deep = router.route_task("code_gen", {"accuracy": 0.9, "latency": 0.05, "cost": 0.05})
    assert chosen_deep == "agent-reasoning"

    # Prioritize cost/latency
    chosen_fast = router.route_task("code_gen", {"accuracy": 0.1, "latency": 0.45, "cost": 0.45})
    assert chosen_fast == "agent-flash"

    # 3-Phase PBFT Verification (4 nodes, f = 1, quorum = 3)
    votes_pass = [{"vote": "commit"}, {"vote": "commit"}, {"vote": "commit"}]
    assert router.pbft_verify(votes_pass, total_nodes=4) is True

    votes_fail = [{"vote": "commit"}, {"vote": "abort"}, {"vote": "commit"}]
    assert router.pbft_verify(votes_fail, total_nodes=4) is False


# ==============================================================================
# 11. HIPPORAG 2 DUAL-NODE PPR TESTS
# ==============================================================================

def test_hipporag2_ppr():
    ppr = HippoRAG2PersonalizedPageRank(damping=0.85, max_iter=10)
    ppr.add_edge("Passage:1", "Entity:FastMCP")
    ppr.add_edge("Entity:FastMCP", "Entity:StatelessGateway")
    ppr.add_edge("Passage:2", "Entity:StatelessGateway")

    ranks = ppr.run_ppr(["Passage:1"])
    assert len(ranks) == 4
    assert ranks["Passage:1"] > 0
    assert ranks["Entity:FastMCP"] > ranks["Passage:2"]


# ==============================================================================
# 12. BITEMPORAL GRAPHITI MEMORY TESTS
# ==============================================================================

def test_bitemporal_graphiti_memory():
    graphiti = BiTemporalGraphitiMemory()
    f0 = graphiti.record_fact("User", "prefers_model", "Gemini 2.5", valid_from=100.0)
    graphiti.invalidate_fact(f0, invalidation_time=200.0)
    f1 = graphiti.record_fact("User", "prefers_model", "Gemini 3.8", valid_from=200.0)

    as_of_150 = graphiti.query_as_of(150.0)
    assert len(as_of_150) == 1
    assert as_of_150[0]["object"] == "Gemini 2.5"

    as_of_250 = graphiti.query_as_of(250.0)
    assert len(as_of_250) == 1
    assert as_of_250[0]["object"] == "Gemini 3.8"


# ==============================================================================
# 13. EXTREME TOKEN PHYSICS TESTS
# ==============================================================================

def test_extreme_token_physics42():
    # Skeletonizer
    code = """
def complex_algorithm(x: int) -> int:
    \"\"\"Docstring retained.\"\"\"
    step1 = x * 2
    step2 = step1 + 42
    return step2
"""
    skel = ASTSkeletonizer36()
    skeleton = skel.skeletonize(code)
    assert "Docstring retained." in skeleton
    assert "pass" in skeleton
    assert "step1 = x * 2" not in skeleton

    # Radix KV Cache Aligner
    aligner = RadixKVCacheAligner(block_size=64)
    assert aligner.align_tokens(60) == 64
    assert aligner.align_tokens(64) == 64
    assert aligner.align_tokens(65) == 128

    # Delta Token Accountant
    accountant = MarginalDeltaTokenAccountant()
    d1_in, d1_out = accountant.compute_turn_delta(100, 50)
    assert d1_in == 100
    assert d1_out == 50

    d2_in, d2_out = accountant.compute_turn_delta(150, 70)
    assert d2_in == 50
    assert d2_out == 20


# ==============================================================================
# 14. FAZ 150 MASTER SWARM ORCHESTRATOR PIPELINE TEST
# ==============================================================================

def test_faz150_master_swarm_orchestrator():
    orchestrator = Faz150MasterSwarmOrchestrator()
    task_spec = {
        "task_id": "pipeline-spec-150",
        "title": "Autonomous Deployment",
        "steps": [
            {"id": "s1", "name": "Lint", "o": 1.0, "m": 1.0, "p": 1.0},
            {"id": "s2", "name": "Build", "o": 2.0, "m": 2.0, "p": 2.0},
            {"id": "s3", "name": "Deploy", "o": 1.0, "m": 1.0, "p": 1.0},
        ],
        "dependencies": [("s1", "s2"), ("s2", "s3")],
    }

    result = orchestrator.run_pipeline(task_spec)
    assert result["status"] == "success"
    assert result["task_state"] == "completed"
    assert result["cpm"]["project_duration"] == 4.0
    assert len(result["merkle_root"]) == 64
    assert result["linda_active_tuples"] >= 1
