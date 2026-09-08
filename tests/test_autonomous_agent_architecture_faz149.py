"""
Unit & Integration Test Suite for Faz 149 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 23.0 Stateless Gateway, ETag 304, MRTR 206, MCP Apps Widget, Capability Check, Saga Rollback
2. AST Preflight Guard 35.0 (Safe syntax, banned imports, dangerous calls, reflection, traversal)
3. Merkle Checkpoint Forest 13.0 (Filesystem snapshots and zero-loss rollback)
4. Speculative MCTS Evaluator (Tree-of-Thoughts / UCB-1 candidate selection)
5. Dynamic Deterministic Temperature Cooling Schedule (T -> 0.0)
6. Decoupled Task Contract 19.0 & Atomic CAS Heartbeat Lease Zombie Takeover
7. Erlang-OTP 13.0 Supervision Trees (Restart intensity & DLQ escalation)
8. Linda Distributed Tuple Space 27.0 (Out, Rd, In, Collect, Watch)
9. Multi-Granular Single-Writer Boundary (MG-SWB 20.0) & Vector Clocks
10. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 23.0
11. AAIF A2A Protocol v1.0.0 / v3.3 Federation Router, 10D Pareto Routing & PBFT Consensus
12. HippoRAG 2 Dual-Node Personalized PageRank (PPR) Multi-Hop Associative Walk
13. BiTemporal Graphiti Memory 4.3 (Fact invalidation and time-travel querying)
14. Extreme Token Physics 41.0 (AST Skeletonizer 35.0, Radix KV Block Alignment, Marginal Delta Token Accounting)
15. Faz149MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz149 import (
    FastMCPGateway,
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPAppWidget,
    ASTPreflightGuard35,
    MerkleCheckpointForest13,
    SpeculativeMCTSEvaluator,
    DynamicDeterministicCooling,
    TaskState,
    DecoupledTaskContract19,
    DecoupledTaskManager,
    ErlangOTPSupervisor13,
    SupervisionStrategy,
    LindaTupleSpace27,
    AgentDesk31,
    MultiGranularSingleWriterBoundary,
    KahnDAGWavefrontScheduler23,
    DAGTaskNode,
    AgentCard149,
    A2AFederationRouter,
    HippoRAG2PersonalizedPageRank,
    BiTemporalGraphitiMemory,
    ASTSkeletonizer35,
    RadixKVCacheAligner,
    MarginalDeltaTokenAccountant,
    Faz149MasterSwarmOrchestrator,
    MCTSNode,
)


# ==============================================================================
# 1. FASTMCP 23.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp23_stateless_gateway():
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
        return "reverted"

    gateway.register_tool(
        name="add_numbers",
        description="Adds two numbers",
        schema={"properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]},
        handler=lambda a, b: a + b,
        compensation_handler=calc_revert,
        app_widget=app_widget,
        required_capability="tool:add_numbers"
    )

    cap_token = gateway.generate_capability_token("tool:add_numbers")

    # 1. Successful invocation with valid capability token
    headers = FastMCPHeaders(mcp_name="add_numbers", mcp_idempotency_key="idemp-1", mcp_capability_token=cap_token)
    res = gateway.invoke(headers, {"a": 15, "b": 25})
    assert res["status"] == 200
    assert res["result"] == 40
    assert res["etag"] is not None
    assert res["app_widget"]["app_id"] == "calc-ui"

    # 2. ETag Caching (304)
    res_cached = gateway.invoke(headers, {"a": 15, "b": 25})
    assert res_cached["status"] == 304
    assert res_cached["cached"] is True

    # 3. MRTR 206 Input Required elicitation
    res_missing = gateway.invoke(FastMCPHeaders(mcp_name="add_numbers", mcp_capability_token=cap_token), {"a": 10})
    assert res_missing["status"] == 206
    assert res_missing["stage"] == "input_required"
    assert "b" in res_missing["missing_parameters"]

    # 4. Capability denial check
    bad_headers = FastMCPHeaders(mcp_name="add_numbers", mcp_capability_token="invalid-token")
    res_denied = gateway.invoke(bad_headers, {"a": 1, "b": 2})
    assert res_denied["status"] == 403

    # 5. Saga Rollback check
    rollbacks = gateway.rollback_saga()
    assert len(rollbacks) == 1
    assert rollbacks[0]["status"] == "rolled_back"
    assert (15, 25) in reverted


# ==============================================================================
# 2. AST PREFLIGHT GUARD 35.0 TESTS
# ==============================================================================

def test_ast_preflight_guard35():
    guard = ASTPreflightGuard35(allowed_workspace_root="C:/EntropiAI")

    # Safe code
    safe_code = """
import math
def calculate_hypotenuse(a: float, b: float) -> float:
    return math.sqrt(a**2 + b**2)
"""
    is_safe, violations = guard.inspect_code(safe_code)
    assert is_safe is True
    assert len(violations) == 0

    # Banned module
    unsafe_import = "import ctypes\nctypes.windll.kernel32"
    is_safe, violations = guard.inspect_code(unsafe_import)
    assert is_safe is False
    assert any("ctypes" in v for v in violations)

    # Forbidden call
    unsafe_call = "eval('2 + 2')"
    is_safe, violations = guard.inspect_code(unsafe_call)
    assert is_safe is False
    assert any("eval" in v for v in violations)

    # Forbidden reflection
    unsafe_refl = "subclasses = object.__subclasses__()"
    is_safe, violations = guard.inspect_code(unsafe_refl)
    assert is_safe is False
    assert any("__subclasses__" in v for v in violations)

    # Path traversal string
    unsafe_path = "path = '../../etc/passwd'"
    is_safe, violations = guard.inspect_code(unsafe_path)
    assert is_safe is False
    assert any("traversal" in v.lower() for v in violations)


# ==============================================================================
# 3. MERKLE CHECKPOINT FOREST 13.0 TESTS
# ==============================================================================

def test_merkle_checkpoint_forest13():
    forest = MerkleCheckpointForest13()
    v1_files = {
        "src/main.py": "print('v1')",
        "src/config.py": "DEBUG = True",
    }
    root1 = forest.create_checkpoint("cp-1", v1_files)
    assert len(root1) == 64

    v2_files = {
        "src/main.py": "print('v2')",
        "src/config.py": "DEBUG = False",
    }
    root2 = forest.create_checkpoint("cp-2", v2_files)
    assert root2 != root1

    # Rollback to cp-1
    restored = forest.rollback_to("cp-1")
    assert restored is not None
    assert restored["src/main.py"] == "print('v1')"
    assert restored["src/config.py"] == "DEBUG = True"


# ==============================================================================
# 4. SPECULATIVE MCTS EVALUATOR TESTS
# ==============================================================================

def test_speculative_mcts_evaluator():
    evaluator = SpeculativeMCTSEvaluator(exploration_c=1.414)
    root_state = {"accuracy": 0.5}
    candidates = [
        {"action": "refactor_architecture", "predicted_state": {"accuracy": 0.95, "safety": 0.9}},
        {"action": "quick_heuristic_fix", "predicted_state": {"accuracy": 0.70, "safety": 0.6}},
        {"action": "no_op", "predicted_state": {"accuracy": 0.50, "safety": 0.9}},
    ]

    def scoring_fn(state: dict) -> float:
        return state.get("accuracy", 0.0) * 0.7 + state.get("safety", 0.0) * 0.3

    result = evaluator.evaluate_branches(root_state, candidates, scoring_fn, iterations=30)
    assert result["best_action"] == "refactor_architecture"
    assert result["expected_reward"] > 0.8


# ==============================================================================
# 5. DYNAMIC DETERMINISTIC TEMPERATURE COOLING TESTS
# ==============================================================================

def test_dynamic_deterministic_cooling():
    cooler = DynamicDeterministicCooling(t_min=0.0, t_max=0.8, max_steps=8)
    t_start = cooler.get_temperature(0)
    assert t_start == 0.8
    t_mid = cooler.get_temperature(4)
    assert 0.0 < t_mid < 0.8
    t_end = cooler.get_temperature(8)
    assert t_end == 0.0


# ==============================================================================
# 6. DECOUPLED TASK CONTRACT 19.0 & ZOMBIE SWEEP TESTS
# ==============================================================================

def test_decoupled_task_contract_and_zombie_sweep():
    mgr = DecoupledTaskManager()
    task = mgr.create_task("task-149-a", "Autonomous Architecture Research")
    assert task.state == TaskState.UNASSIGNED

    # Acquire lease
    ok = mgr.acquire_lease("task-149-a", "agent-alpha", "lease-xyz")
    assert ok is True
    assert task.state == TaskState.ACQUIRED
    assert task.assigned_agent == "agent-alpha"

    # Progress transitions
    assert task.transition_to(TaskState.IN_PROGRESS, "Started") is True
    assert task.transition_to(TaskState.VERIFYING, "Verifying") is True

    # Simulate heartbeat timeout for zombie recovery
    task.last_heartbeat = time.time() - 25.0  # heartbeat_ttl is 15.0
    recovered = mgr.sweep_zombies(current_time=time.time())
    assert "task-149-a" in recovered
    assert task.state == TaskState.ZOMBIE_RECOVERED
    assert task.assigned_agent is None

    # Atomic re-acquisition
    reacquired = mgr.acquire_lease("task-149-a", "agent-beta", "lease-abc")
    assert reacquired is True
    assert task.state == TaskState.ACQUIRED
    assert task.assigned_agent == "agent-beta"


# ==============================================================================
# 7. ERLANG-OTP 13.0 SUPERVISION TESTS
# ==============================================================================

def test_erlang_otp13_supervision():
    supervisor = ErlangOTPSupervisor13(
        strategy=SupervisionStrategy.ONE_FOR_ONE,
        max_restarts=2,
        time_window=10.0
    )

    supervisor.register_worker("worker-1", "codegen", restart_policy="transient")

    # 1st failure -> restart with backoff
    res1 = supervisor.report_failure("worker-1", "Memory timeout", {})
    assert res1 == "restarted_with_backoff"

    # 2nd failure -> restart with backoff
    res2 = supervisor.report_failure("worker-1", "File lock error", {})
    assert res2 == "restarted_with_backoff"

    # 3rd failure -> trips circuit breaker, escalates to DLQ
    res3 = supervisor.report_failure("worker-1", "Segmentation violation", {})
    assert res3 == "escalated_to_dlq"
    assert supervisor.workers["worker-1"]["status"] == "circuit_breaker_tripped"
    assert len(supervisor.dead_letter_queue) == 1
    assert "Max restarts" in supervisor.dead_letter_queue[0]["reason"]


# ==============================================================================
# 8. LINDA DISTRIBUTED TUPLE SPACE 27.0 TESTS
# ==============================================================================

def test_linda_tuple_space27():
    ts = LindaTupleSpace27()
    received = []

    def on_task_ready(t):
        received.append(t)

    ts.watch(("task", str, "READY"), on_task_ready)

    ts.out(("task", "auth_module", "READY"))
    ts.out(("task", "database_module", "PENDING"))
    ts.out(("task", "payment_module", "READY"))

    assert len(received) == 2

    # Non-destructive rd
    match_rd = ts.rd(("task", "auth_module", "*"))
    assert match_rd == ("task", "auth_module", "READY")
    assert len(ts.tuples) == 3

    # Destructive in_tuple
    consumed = ts.in_tuple(("task", "payment_module", "*"))
    assert consumed == ("task", "payment_module", "READY")
    assert len(ts.tuples) == 2

    # Collect
    all_tasks = ts.collect(("task", str, "*"))
    assert len(all_tasks) == 2


# ==============================================================================
# 9. MULTI-GRANULAR SINGLE-WRITER BOUNDARY & VECTOR CLOCKS
# ==============================================================================

def test_mg_swb_vector_clocks():
    mg_swb = MultiGranularSingleWriterBoundary()
    path = "C:/EntropiAI/src/main.py"

    # Desk A acquires lease
    assert mg_swb.acquire_file_write_lease(path, "desk_architect") is True
    # Desk B cannot acquire simultaneous lease
    assert mg_swb.acquire_file_write_lease(path, "desk_coder") is False

    # Check vector clock
    norm_path = path.replace("\\", "/").lower()
    clock = mg_swb.vector_clocks[norm_path]
    assert clock["desk_architect"] == 1

    # Desk A releases
    assert mg_swb.release_file_write_lease(path, "desk_architect") is True
    # Now Desk B can acquire
    assert mg_swb.acquire_file_write_lease(path, "desk_coder") is True
    assert clock["desk_coder"] == 1


# ==============================================================================
# 10. KAHN DAG WAVEFRONT & CPM SLACK BORROWING 23.0 TESTS
# ==============================================================================

def test_kahn_dag_wavefront_and_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler23()

    # Create task nodes with PERT O, M, P values
    t1 = DAGTaskNode(task_id="t1", name="Requirement Analysis", optimistic=1.0, most_likely=2.0, pessimistic=3.0)
    t2 = DAGTaskNode(task_id="t2", name="Core Architecture", optimistic=2.0, most_likely=4.0, pessimistic=6.0)
    t3 = DAGTaskNode(task_id="t3", name="Unit Documentation", optimistic=1.0, most_likely=1.0, pessimistic=1.0)
    t4 = DAGTaskNode(task_id="t4", name="System Integration", optimistic=2.0, most_likely=3.0, pessimistic=4.0)

    scheduler.add_node(t1)
    scheduler.add_node(t2)
    scheduler.add_node(t3)
    scheduler.add_node(t4)

    # Dependencies: t1 -> t2, t1 -> t3, t2 -> t4, t3 -> t4
    scheduler.add_dependency("t1", "t2")
    scheduler.add_dependency("t1", "t3")
    scheduler.add_dependency("t2", "t4")
    scheduler.add_dependency("t3", "t4")

    wavefronts = scheduler.compute_wavefronts()
    assert wavefronts == [["t1"], ["t2", "t3"], ["t4"]]

    cpm = scheduler.compute_critical_path_and_slack_borrowing()
    assert "t1" in cpm["critical_path"]
    assert "t2" in cpm["critical_path"]
    assert "t4" in cpm["critical_path"]
    # t3 is shorter, so it has slack > 0
    assert scheduler.nodes["t3"].slack > 0
    assert scheduler.nodes["t3"].assigned_tier == "FAST_FLASH"
    assert scheduler.nodes["t2"].assigned_tier == "FRONTIER_REASONING"
    assert cpm["estimated_token_savings_pct"] > 0.0


# ==============================================================================
# 11. AAIF A2A v1.0.0 / v3.3 ROUTING & PBFT QUORUM TESTS
# ==============================================================================

def test_a2a_federation_router_and_pbft():
    router = A2AFederationRouter()

    card_pro = AgentCard149(
        agent_id="pro-architect",
        name="Lead Architect Agent",
        capabilities=["architecture", "system_design", "refactoring"],
        skills=["uml", "fastmcp"],
        metrics={"accuracy": 0.99, "reliability": 0.98, "latency_norm": 0.4, "cost_norm": 0.4}
    )
    card_fast = AgentCard149(
        agent_id="flash-coder",
        name="Rapid Coder Agent",
        capabilities=["codegen", "refactoring"],
        skills=["python", "pytest"],
        metrics={"accuracy": 0.92, "reliability": 0.95, "latency_norm": 0.1, "cost_norm": 0.1}
    )

    router.register_card(card_pro)
    router.register_card(card_fast)

    # Agent card JSON generation & signature
    card_json = card_pro.generate_agent_card_json()
    assert "signature" in card_json
    assert len(card_json["signature"]) == 64

    # Pareto routing
    best_id, score = router.pareto_route({"required_capabilities": ["architecture"]})
    assert best_id == "pro-architect"
    assert score > 0.7

    # PBFT Quorum consensus (2f+1 verification)
    votes_pass = ["COMMIT", "COMMIT", "COMMIT", "PREPARE"]
    assert router.pbft_verify_consensus(votes_pass, required_quorum_fraction=0.67) is True

    votes_fail = ["COMMIT", "REJECT", "REJECT"]
    assert router.pbft_verify_consensus(votes_fail, required_quorum_fraction=0.67) is False


# ==============================================================================
# 12. HIPPORAG 2 DUAL-NODE PERSONALIZED PAGERANK TESTS
# ==============================================================================

def test_hipporag2_ppr():
    ppr = HippoRAG2PersonalizedPageRank(damping=0.85)

    # Graph connecting passage nodes to entity nodes
    ppr.add_edge("Passage:A2A_Spec", "Entity:A2A_Protocol")
    ppr.add_edge("Entity:A2A_Protocol", "Passage:Agent_Card")
    ppr.add_edge("Entity:A2A_Protocol", "Entity:Linux_Foundation")
    ppr.add_edge("Entity:Linux_Foundation", "Passage:Governance")

    rankings = ppr.run_ppr(seed_nodes=["Passage:A2A_Spec"], iterations=25)
    top_two = list(rankings.keys())[:2]
    assert "Passage:A2A_Spec" in top_two
    assert "Entity:A2A_Protocol" in top_two


# ==============================================================================
# 13. BITEMPORAL GRAPHITI MEMORY 4.3 TESTS
# ==============================================================================

def test_bitemporal_graphiti_memory():
    graph = BiTemporalGraphitiMemory()
    t0 = 1000.0
    t1 = 2000.0
    t2 = 3000.0

    # At t0: User preferred Flash model
    graph.add_fact("User", "prefers_model", "Gemini 2.5 Flash", valid_start=t0)
    # At t1: User changes preference to Gemini 3.8 Flash
    graph.invalidate_fact("User", "prefers_model", "Gemini 2.5 Flash", invalid_time=t1)
    graph.add_fact("User", "prefers_model", "Gemini 3.8 Flash", valid_start=t1)

    # Query as of t0 + 500 (Historical time travel)
    historical_facts = graph.query_as_of(t0 + 500.0)
    assert ("User", "prefers_model", "Gemini 2.5 Flash") in historical_facts
    assert ("User", "prefers_model", "Gemini 3.8 Flash") not in historical_facts

    # Query as of t2 (Present time)
    present_facts = graph.query_as_of(t2)
    assert ("User", "prefers_model", "Gemini 3.8 Flash") in present_facts
    assert ("User", "prefers_model", "Gemini 2.5 Flash") not in present_facts


# ==============================================================================
# 14. EXTREME TOKEN PHYSICS 41.0 TESTS
# ==============================================================================

def test_extreme_token_physics41():
    # 1. AST Skeletonizer
    source_code = """
def heavy_computation(x: int, y: int) -> int:
    \"\"\"Performs complex calculation.\"\"\"
    temp = 0
    for i in range(x):
        temp += i * y
    return temp
"""
    skeletonizer = ASTSkeletonizer35()
    skeleton = skeletonizer.skeletonize(source_code)
    assert "for i in range(x):" not in skeleton
    assert "pass" in skeleton
    assert "def heavy_computation(x: int, y: int) -> int:" in skeleton

    # 2. Radix KV Cache Block Alignment
    aligner = RadixKVCacheAligner(block_size=64)
    assert aligner.align_tokens(64) == 64
    assert aligner.align_tokens(65) == 128
    assert aligner.align_tokens(100) == 128

    # 3. Marginal Delta Token Accounting
    accountant = MarginalDeltaTokenAccountant()
    # Turn 1
    d_in1, d_out1 = accountant.compute_turn_delta(1500, 300)
    assert d_in1 == 1500
    assert d_out1 == 300

    # Turn 2: cumulative database total increases to 3200 in, 750 out
    d_in2, d_out2 = accountant.compute_turn_delta(3200, 750)
    assert d_in2 == 1700
    assert d_out2 == 450


# ==============================================================================
# 15. FAZ 149 MASTER SWARM ORCHESTRATOR END-TO-END PIPELINE TEST
# ==============================================================================

def test_faz149_master_swarm_orchestrator():
    orchestrator = Faz149MasterSwarmOrchestrator()

    task_spec = {
        "task_id": "orchestrator-task-149",
        "title": "Master Swarm Autonomous Execution",
        "steps": [
            {"id": "step1", "name": "Security Preflight", "o": 1.0, "m": 1.5, "p": 2.0},
            {"id": "step2", "name": "Code Generation", "o": 2.0, "m": 3.0, "p": 5.0},
            {"id": "step3", "name": "Verification & QA", "o": 1.0, "m": 2.0, "p": 3.0},
        ],
        "dependencies": [
            ("step1", "step2"),
            ("step2", "step3"),
        ]
    }

    result = orchestrator.run_pipeline(task_spec)
    assert result["status"] == "success"
    assert result["task_state"] == "completed"
    assert len(result["cpm"]["critical_path"]) == 3
    assert result["linda_active_tuples"] >= 1
    assert result["merkle_root"] is not None
