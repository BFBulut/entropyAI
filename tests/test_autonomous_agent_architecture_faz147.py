"""
Unit & Integration Test Suite for Faz 147 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 21.0 Stateless Gateway, ETag 304, MRTR 206, MCP Apps Widget, Saga Rollback
2. AST Preflight Guard 33.0 (Safe syntax, banned imports, dangerous calls, reflection, traversal)
3. Merkle Checkpoint Forest 11.0 (Filesystem snapshots and zero-loss rollback)
4. Speculative MCTS Evaluator (Tree-of-Thoughts / UCB-1 candidate selection)
5. Dynamic Deterministic Temperature Cooling Schedule (T -> 0.0)
6. Decoupled Task Contract 17.0 & Atomic CAS Heartbeat Lease Zombie Takeover
7. Linda Distributed Tuple Space 25.0 (Out, Rd, In, Collect)
8. Multi-Granular Single-Writer Boundary (MG-SWB 18.0)
9. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 21.0
10. AAIF A2A Protocol v1.0.0 Federation Router & Agent Card Signatures
11. HippoRAG 2 Dual-Node Personalized PageRank (PPR) Multi-Hop Associative Walk
12. BiTemporal Graphiti Memory 4.1 (Fact invalidation and time-travel querying)
13. Extreme Token Physics 39.0 (AST Skeletonizer 33.0, Radix KV Block Alignment, Marginal Delta Token Accounting)
14. Faz147MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz147 import (
    FastMCPGateway,
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPAppWidget,
    ASTPreflightGuard33,
    MerkleCheckpointForest11,
    SpeculativeMCTSEvaluator,
    DynamicDeterministicCooling,
    TaskState,
    DecoupledTaskContract17,
    DecoupledTaskManager,
    LindaTupleSpace25,
    AgentDesk29,
    MultiGranularSingleWriterBoundary,
    KahnDAGWavefrontScheduler21,
    AgentCard147,
    A2AFederationRouter,
    HippoRAG2PersonalizedPageRank,
    BiTemporalGraphitiMemory,
    ASTSkeletonizer33,
    RadixKVCacheAligner,
    MarginalDeltaTokenAccountant,
    Faz147MasterSwarmOrchestrator,
)


# ==============================================================================
# 1. FASTMCP 21.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp21_stateless_gateway():
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
    assert rolled == ["add_numbers"]
    assert reverted == [(10, 20)]


# ==============================================================================
# 2. AST PREFLIGHT GUARD 33.0 TESTS
# ==============================================================================

def test_ast_preflight_guard_33():
    # 1. Valid safe code
    safe_code = """
def compute_metrics(values):
    return sum(values) / len(values)
"""
    passed, violations = ASTPreflightGuard33.inspect_code(safe_code)
    assert passed is True
    assert len(violations) == 0

    # 2. Banned imports & calls
    danger_code = """
import subprocess
import socket

def attack():
    eval('__import__("os").system("dir")')
    os.system("rmdir /s /q test")
    x = ().__class__.__bases__[0].__subclasses__()
    path = "../secret/credentials.env"
"""
    passed, violations = ASTPreflightGuard33.inspect_code(danger_code)
    assert passed is False
    assert any("subprocess" in v for v in violations)
    assert any("socket" in v for v in violations)
    assert any("eval" in v for v in violations)
    assert any("os.system" in v for v in violations)
    assert any("__subclasses__" in v for v in violations)
    assert any("Path traversal" in v for v in violations)


# ==============================================================================
# 3. MERKLE CHECKPOINT FOREST 11.0 TESTS
# ==============================================================================

def test_merkle_checkpoint_forest_11():
    forest = MerkleCheckpointForest11()
    state_v1 = {
        "src/main.py": "print('hello')",
        "config.json": '{"mode": "zen"}'
    }
    hash_v1 = forest.snapshot("chk-1", state_v1)
    assert len(hash_v1) == 64

    # State v2
    state_v2 = {
        "src/main.py": "print('corrupted code')",
        "config.json": '{"mode": "zen"}'
    }
    hash_v2 = forest.snapshot("chk-2", state_v2)
    assert hash_v1 != hash_v2

    # Rollback to v1
    recovered = forest.rollback("chk-1")
    assert recovered == state_v1
    assert recovered["src/main.py"] == "print('hello')"


# ==============================================================================
# 4. SPECULATIVE MCTS EVALUATOR TESTS
# ==============================================================================

def test_speculative_mcts_evaluator():
    evaluator = SpeculativeMCTSEvaluator(exploration_constant=1.414)
    candidates = [
        {"name": "branch_A", "mean_reward": 0.85, "visits": 10},
        {"name": "branch_B", "mean_reward": 0.92, "visits": 50},
        {"name": "branch_C", "mean_reward": 0.70, "visits": 2},
    ]
    scored = evaluator.score_candidates(candidates, total_visits=100)
    assert len(scored) == 3
    # Verify ranked descending
    assert scored[0][1] >= scored[1][1] >= scored[2][1]


# ==============================================================================
# 5. DYNAMIC DETERMINISTIC COOLING TESTS
# ==============================================================================

def test_dynamic_deterministic_cooling():
    cooling = DynamicDeterministicCooling(t0=0.70, alpha=0.85, min_temp=0.01)
    t0 = cooling.get_temperature(0)
    t1 = cooling.get_temperature(1)
    t5 = cooling.get_temperature(5)
    t50 = cooling.get_temperature(50)

    assert t0 == 0.70
    assert t1 == round(0.70 * 0.85, 4)
    assert t5 < t1
    assert t50 == 0.01  # clamped to min_temp


# ==============================================================================
# 6. DECOUPLED TASK CONTRACT & ZOMBIE TAKEOVER TESTS
# ==============================================================================

def test_decoupled_task_contract_and_zombie_recovery():
    manager = DecoupledTaskManager()
    task = manager.create_task("T-1", "Index Codebase", "Parse AST for project")
    assert task.state == TaskState.UNASSIGNED
    assert task.cas_version == 1

    # Acquire Task
    success = manager.acquire_task("T-1", "agent-architect", current_cas=1)
    assert success is True
    assert task.state == TaskState.ACQUIRED
    assert task.assigned_agent_id == "agent-architect"
    assert task.cas_version == 2

    # CAS Conflict check
    bad_cas = manager.acquire_task("T-1", "agent-rogue", current_cas=1)
    assert bad_cas is False

    # Heartbeat
    hb = manager.heartbeat("T-1", "agent-architect")
    assert hb is True

    # Zombie Sweep Simulation (expired lease)
    now_future = time.time() + 30.0  # 30s in future > 15s TTL
    recovered = manager.sweep_zombies(now=now_future)
    assert "T-1" in recovered
    assert task.state == TaskState.ZOMBIE_RECOVERED
    assert task.assigned_agent_id is None
    assert task.cas_version == 3

    # Re-acquire by fresh agent
    re_acquire = manager.acquire_task("T-1", "agent-healer", current_cas=3)
    assert re_acquire is True
    assert task.assigned_agent_id == "agent-healer"


# ==============================================================================
# 7. LINDA DISTRIBUTED TUPLE SPACE TESTS
# ==============================================================================

def test_linda_tuple_space_25():
    ts = LindaTupleSpace25()
    ts.out({"topic": "spec", "author": "architect", "phase": 147})
    ts.out({"topic": "code", "author": "engineer", "phase": 147})
    ts.out({"topic": "test", "author": "qa", "phase": 147})

    # Read (rd) non-destructive
    found = ts.rd({"topic": "code", "phase": "*"})
    assert found is not None
    assert found["author"] == "engineer"
    assert len(ts.tuples) == 3

    # In (in_tuple) destructive
    taken = ts.in_tuple({"topic": "spec", "phase": 147})
    assert taken is not None
    assert taken["author"] == "architect"
    assert len(ts.tuples) == 2

    # Collect all matching
    matched = ts.collect({"phase": 147})
    assert len(matched) == 2
    assert len(ts.tuples) == 0


# ==============================================================================
# 8. MULTI-GRANULAR SINGLE-WRITER BOUNDARY TESTS
# ==============================================================================

def test_single_writer_boundary():
    swb = MultiGranularSingleWriterBoundary()
    path = "src/entropy/main.py"

    # Agent 1 acquires lock
    assert swb.acquire_lock(path, "agent-1") is True
    assert swb.vector_clocks[path]["agent-1"] == 1

    # Agent 2 fails to acquire
    assert swb.acquire_lock(path, "agent-2") is False

    # Agent 1 re-acquires (increments vector clock)
    assert swb.acquire_lock(path, "agent-1") is True
    assert swb.vector_clocks[path]["agent-1"] == 2

    # Agent 1 releases lock
    assert swb.release_lock(path, "agent-1") is True

    # Agent 2 now succeeds
    assert swb.acquire_lock(path, "agent-2") is True
    assert swb.vector_clocks[path]["agent-2"] == 1


# ==============================================================================
# 9. KAHN DAG WAVEFRONT SCHEDULER & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_wavefront_scheduler_cpm():
    scheduler = KahnDAGWavefrontScheduler21()
    # Task A: Spec (1, 2, 3) -> Te = 2.0
    scheduler.add_node("task_A", optimistic=1.0, most_likely=2.0, pessimistic=3.0)
    # Task B: Database (2, 4, 6) -> Te = 4.0, depends on A
    scheduler.add_node("task_B", optimistic=2.0, most_likely=4.0, pessimistic=6.0, dependencies=["task_A"])
    # Task C: Docs (1, 1, 1) -> Te = 1.0, depends on A (Has slack!)
    scheduler.add_node("task_C", optimistic=1.0, most_likely=1.0, pessimistic=1.0, dependencies=["task_A"])
    # Task D: Deploy (1, 2, 3) -> Te = 2.0, depends on B and C
    scheduler.add_node("task_D", optimistic=1.0, most_likely=2.0, pessimistic=3.0, dependencies=["task_B", "task_C"])

    schedule = scheduler.compute_schedule()
    # Path A -> B -> D duration: 2.0 + 4.0 + 2.0 = 8.0
    # Path A -> C -> D duration: 2.0 + 1.0 + 2.0 = 5.0
    assert schedule["project_duration"] == 8.0
    assert schedule["critical_path"] == ["task_A", "task_B", "task_D"]

    nodes = schedule["nodes"]
    # Critical tasks get frontier reasoning
    assert nodes["task_A"]["assigned_model_tier"] == "frontier_reasoning"
    assert nodes["task_B"]["assigned_model_tier"] == "frontier_reasoning"
    assert nodes["task_D"]["assigned_model_tier"] == "frontier_reasoning"

    # Non-critical task C gets flash efficient (slack borrowing)
    assert nodes["task_C"]["slack"] == 3.0  # 4.0 - 1.0 = 3.0 slack
    assert nodes["task_C"]["assigned_model_tier"] == "flash_efficient"


# ==============================================================================
# 10. AAIF A2A FEDERATION ROUTER & AGENT CARD TESTS
# ==============================================================================

def test_aaif_a2a_federation_router():
    router = A2AFederationRouter(secret_signing_key="aaif-key-2026")
    card1 = AgentCard147(
        agent_id="agent-claude",
        name="Claude Code Architect",
        version="1.0.0",
        capabilities=["code_synthesis", "refactoring"],
        supported_protocols=["a2a/1.0.0", "mcp/2026"],
        cost_per_million_tokens=15.0,
        average_latency_ms=1200.0,
        accuracy_score=0.98
    )
    card2 = AgentCard147(
        agent_id="agent-flash",
        name="Flash Speed Refactorer",
        version="1.0.0",
        capabilities=["code_synthesis", "formatting"],
        supported_protocols=["a2a/1.0.0"],
        cost_per_million_tokens=0.20,
        average_latency_ms=150.0,
        accuracy_score=0.92
    )

    router.register_agent(card1)
    router.register_agent(card2)

    assert card1.public_signature != ""
    assert card2.public_signature != ""

    # Select optimal agent for code_synthesis with cost budget
    best_accurate = router.find_pareto_optimal_agent("code_synthesis", max_cost=20.0)
    assert best_accurate.agent_id == "agent-claude"

    best_budget = router.find_pareto_optimal_agent("code_synthesis", max_cost=1.0)
    assert best_budget.agent_id == "agent-flash"


# ==============================================================================
# 11. HIPPORAG 2 DUAL-NODE PERSONALIZED PAGERANK TESTS
# ==============================================================================

def test_hipporag2_personalized_pagerank():
    hippo = HippoRAG2PersonalizedPageRank(damping_factor=0.85, max_iterations=20)
    # Build associative graph
    hippo.add_edge("Harness", "ASTPreflight")
    hippo.add_edge("Harness", "MerkleForest")
    hippo.add_edge("ASTPreflight", "Sandbox")
    hippo.add_edge("MerkleForest", "Rollback")
    hippo.add_edge("OtherTopic", "UnrelatedNode")

    # Spread activation from 'Harness'
    ppr_scores = hippo.compute_ppr(seed_nodes=["Harness"])
    assert len(ppr_scores) > 0
    top_nodes = list(ppr_scores.keys())

    # 'Harness' and direct neighbors should rank higher than 'UnrelatedNode'
    assert ppr_scores["Harness"] > ppr_scores["UnrelatedNode"]
    assert ppr_scores["ASTPreflight"] > ppr_scores["UnrelatedNode"]


# ==============================================================================
# 12. BITEMPORAL GRAPHITI MEMORY TESTS
# ==============================================================================

def test_bitemporal_graphiti_memory_4():
    graphiti = BiTemporalGraphitiMemory()
    # At t=10, project lead is Alice
    graphiti.assert_fact("project_entropy", "lead", "Alice", timestamp=10.0)
    # At t=50, project lead changes to Bob
    graphiti.assert_fact("project_entropy", "lead", "Bob", timestamp=50.0)

    # Historical query at t=30 should return Alice
    assert graphiti.query_as_of("project_entropy", "lead", target_time=30.0) == "Alice"

    # Current query at t=60 should return Bob
    assert graphiti.query_as_of("project_entropy", "lead", target_time=60.0) == "Bob"


# ==============================================================================
# 13. EXTREME TOKEN PHYSICS TESTS
# ==============================================================================

def test_extreme_token_physics_39():
    # 1. AST Skeletonizer
    code = """
def process_data(data: list[int]) -> dict:
    \"\"\"Process the data list.\"\"\"
    x = 10
    y = [i * 2 for i in data]
    result = {"sum": sum(y)}
    return result
"""
    skeleton = ASTSkeletonizer33.skeletonize(code)
    assert "Process the data list." in skeleton
    assert "x = 10" not in skeleton
    assert "pass" in skeleton

    # 2. Radix KV Cache Block Aligner
    aligner = RadixKVCacheAligner(block_size=128)
    aligned = aligner.align_text("Hello world")
    approx_tokens = math.ceil(len(aligned) / 4.0)
    assert approx_tokens % 128 == 0

    # 3. Marginal Delta Token Accountant
    accountant = MarginalDeltaTokenAccountant()
    turn1 = accountant.compute_turn_delta(current_cumulative_input=1000, current_cumulative_output=200)
    assert turn1["turn_input_tokens"] == 1000
    assert turn1["turn_output_tokens"] == 200

    turn2 = accountant.compute_turn_delta(current_cumulative_input=1250, current_cumulative_output=280)
    assert turn2["turn_input_tokens"] == 250
    assert turn2["turn_output_tokens"] == 80
    assert turn2["turn_total_tokens"] == 330


# ==============================================================================
# 14. FAZ 147 MASTER SWARM ORCHESTRATOR INTEGRATION TEST
# ==============================================================================

def test_faz147_master_swarm_orchestrator():
    orchestrator = Faz147MasterSwarmOrchestrator()
    res = orchestrator.execute_pipeline()
    assert res["task_acquired"] is True
    assert res["tuple_intent"]["task_id"] == "T-147-ALPHA"
    assert res["current_version_fact"] == "faz_147"
    assert res["schedule_duration"] == 6.0
    assert res["critical_path"] == ["spec", "code"]
    assert res["status"] == "ready_and_verified"
