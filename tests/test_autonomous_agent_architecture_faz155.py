"""
Comprehensive Test Suite for Faz 155 Master Autonomous Agent Architecture
========================================================================
Validates all subsystems:
- FastMCP 29.0 Stateless Headers (19 headers), Zero-Shot Attenuation, Interceptor & Saga Rollback
- FastMCP Apps Extension (SEP-1866) interactive canvas/form widgets
- Hypervisor Harness 19.0 AST Preflight Guard & Dynamic Annealing
- Decoupled Task Contract 25.0 21-State FSM, CAS & Erlang-OTP 19.0 DLQ
- Kahn DAG Wavefront Scheduler 29.0, Stochastic PERT & CPM Slack Borrowing 29.0
- Agent Desks 37.0, Linda Tuple Space 33.0 & AST Reconciler 28
- AAIF Horizontal Federation Router 155 & HMAC AgentCard
- Quattuordecim-Store 53-Layer HippoRAG 2 Dual-Node PPR & Ebbinghaus Decay
- Extreme Token Physics 47.0, CodeAct 40.0 & Radix Alignment
- End-to-End Faz 155 Master Swarm Orchestrator
"""

import pytest
import time
from src.entropy.tools.autonomous_agent_architecture_faz155 import (
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPStatelessGateway,
    FastMCPAppWidget,
    ASTPreflightGuard155,
    SpeculativeMCTSNode,
    MerkleCheckpointForest,
    HypervisorAgentHarness19,
    TaskState,
    OTPStrategy,
    DecoupledTaskContract25,
    ErlangOTPSupervisor19,
    DAGTaskNode,
    KahnDAGWavefrontScheduler29,
    LindaTupleSpace33,
    ASTSemanticReconciler28,
    AgentCard155,
    AAIFHorizontalRouter155,
    MemoryNode,
    HippoRAG2MemoryEngine,
    ASTSkeletonizer41,
    CodeActVirtualREPL40,
    RadixKVBlockAligner,
    Faz155MasterSwarmOrchestrator,
)


def test_fastmcp_headers_roundtrip():
    headers = FastMCPHeaders(
        mcp_name="test_tool",
        mcp_stage="validate",
        mcp_routing_nonce="nonce-155-998811",
        mcp_telemetry_budget_tokens=8192,
        mcp_consensus_epoch=45,
        mcp_isolation_boundary="desk-ephemeral-worktree-v155",
    )
    h_dict = headers.to_header_dict()
    assert h_dict["Mcp-Name"] == "test_tool"
    assert h_dict["Mcp-Routing-Nonce"] == "nonce-155-998811"
    assert h_dict["Mcp-Telemetry-Budget-Tokens"] == "8192"
    assert h_dict["Mcp-Consensus-Epoch"] == "45"
    assert h_dict["Mcp-Isolation-Boundary"] == "desk-ephemeral-worktree-v155"

    restored = FastMCPHeaders.from_header_dict(h_dict)
    assert restored.mcp_name == "test_tool"
    assert restored.mcp_routing_nonce == "nonce-155-998811"
    assert restored.mcp_telemetry_budget_tokens == 8192
    assert restored.mcp_consensus_epoch == 45
    assert restored.mcp_isolation_boundary == "desk-ephemeral-worktree-v155"


def test_fastmcp_gateway_execution_and_interceptor():
    gw = FastMCPStatelessGateway()

    def multiply_numbers(a: int, b: int) -> int:
        return a * b

    def rollback_mult(a: int, b: int):
        return f"rolled_back_{a}_{b}"

    schema = {
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    }
    gw.register_tool("mult", multiply_numbers, schema, compensation_fn=rollback_mult)

    # 1. Zero-shot stub
    stub = gw.generate_zero_shot_stub("mult")
    assert stub == "mult(a,b)"

    # 2. MRTR 206 input_required
    headers = FastMCPHeaders(mcp_name="mult")
    res_partial = gw.execute_call(headers, {"a": 5})
    assert res_partial["status"] == 206
    assert res_partial["missing_slots"] == ["b"]

    # 3. Successful call
    res_full = gw.execute_call(headers, {"a": 5, "b": 10})
    assert res_full["status"] == 200
    assert res_full["output"] == 50
    assert "etag" in res_full

    # 4. ETag 304 Cache hit
    res_cached = gw.execute_call(headers, {"a": 5, "b": 10})
    assert res_cached["status"] == 304

    # 5. Saga compensation rollback
    rollback_log = gw.rollback_saga()
    assert len(rollback_log) == 1
    assert rollback_log[0]["status"] == "compensated"


def test_fastmcp_app_widget():
    widget = FastMCPAppWidget(
        widget_id="w-155",
        widget_type="canvas",
        title="Agent Collaboration Canvas",
        schema={"properties": {"zoom": {"type": "number"}}},
        current_state={"zoom": 1.5},
    )
    rendered = widget.render_json()
    assert rendered["widget_id"] == "w-155"
    assert rendered["widget_type"] == "canvas"
    assert rendered["current_state"]["zoom"] == 1.5
    assert rendered["uri"] == "ui://mcp-app/canvas/w-155"


def test_ast_preflight_guard_safety():
    safe_code = """
def compute_sum(a, b):
    return a + b
"""
    is_safe, violations = ASTPreflightGuard155.inspect_code(safe_code)
    assert is_safe
    assert len(violations) == 0

    unsafe_code = """
import ctypes
import subprocess
eval("2 + 2")
"""
    is_safe2, violations2 = ASTPreflightGuard155.inspect_code(unsafe_code)
    assert not is_safe2
    assert any("ctypes" in v for v in violations2)
    assert any("subprocess" in v for v in violations2)
    assert any("eval" in v for v in violations2)


def test_merkle_checkpoint_forest_and_rollback():
    forest = MerkleCheckpointForest()
    state_0 = {"phase": 155, "status": "init"}
    root_0 = forest.commit("cp_0", state_0)
    assert len(root_0) == 64

    rolled_back = forest.rollback("cp_0")
    assert rolled_back == state_0


def test_hypervisor_harness_execution_and_cooling():
    harness = HypervisorAgentHarness19(initial_temperature=0.8, cooling_rate=0.5)

    # Step 0
    t0 = harness.compute_temperature(0)
    assert t0 == 0.8

    # Step 1
    t1 = harness.compute_temperature(1)
    assert t1 == 0.4

    # Execute safe chunk
    res = harness.evaluate_and_execute("x = 10", "cp_safe", {"x": 0}, step=1)
    assert res["status"] == "success"
    assert res["active_temperature"] == 0.4

    # Execute unsafe chunk
    res_unsafe = harness.evaluate_and_execute("eval('bad')", "cp_bad", {"x": 10}, step=2)
    assert res_unsafe["status"] == "guard_violation"
    assert len(res_unsafe["violations"]) > 0


def test_speculative_mcts_node_ucb1():
    node = SpeculativeMCTSNode("node_1", "action_A", visits=4, total_reward=3.2, prm_score=0.9)
    ucb = node.ucb1(parent_visits=16)
    assert ucb > 0.8


def test_decoupled_task_contract_fsm_and_cas():
    task = DecoupledTaskContract25(task_id="T-155", title="Build Microkernel")
    assert task.state == TaskState.UNASSIGNED

    # Acquire
    acq = task.acquire_lease("agent-coder", ttl_seconds=10.0)
    assert acq
    assert task.state == TaskState.ACQUIRED
    assert task.assigned_agent == "agent-coder"

    # CAS renew
    v = task.lease_version
    renewed = task.renew_lease("agent-coder", expected_version=v, ttl_seconds=20.0)
    assert renewed
    assert task.state == TaskState.IN_PROGRESS
    assert task.lease_version == v + 1

    # Transition to RECLAIMED
    task.transition_to(TaskState.RECLAIMED, "agent-coder")
    assert task.state == TaskState.RECLAIMED


def test_erlang_otp_supervisor_dlq():
    sup = ErlangOTPSupervisor19(strategy=OTPStrategy.ONE_FOR_ONE, max_restarts=2)
    task = DecoupledTaskContract25(task_id="T-DLQ", title="Fragile Task")

    # Fail 1
    act1 = sup.handle_worker_failure("worker_1", "crash 1", task)
    assert "RESTART_WORKER" in act1
    assert task.state == TaskState.RECLAIMED

    # Fail 2
    act2 = sup.handle_worker_failure("worker_1", "crash 2", task)
    assert "RESTART_WORKER" in act2

    # Fail 3 (exceeds max_restarts 2)
    act3 = sup.handle_worker_failure("worker_1", "crash 3", task)
    assert act3 == "ESCALATED_TO_DLQ"
    assert task.state == TaskState.ESCALATED
    assert len(sup.dead_letter_queue) == 1


def test_kahn_dag_wavefront_and_pert_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler29()
    # A (2, 4, 6) -> Te = 4.0
    # B (1, 2, 3) -> Te = 2.0 (depends on A)
    # C (1, 1, 1) -> Te = 1.0 (depends on A)
    # D (1, 3, 5) -> Te = 3.0 (depends on B and C)
    node_a = DAGTaskNode("A", 2.0, 4.0, 6.0)
    node_b = DAGTaskNode("B", 1.0, 2.0, 3.0, dependencies={"A"})
    node_c = DAGTaskNode("C", 1.0, 1.0, 1.0, dependencies={"A"})
    node_d = DAGTaskNode("D", 1.0, 3.0, 5.0, dependencies={"B", "C"})

    scheduler.add_node(node_a)
    scheduler.add_node(node_b)
    scheduler.add_node(node_c)
    scheduler.add_node(node_d)

    res = scheduler.compute_cpm_and_borrow_slack()
    assert res["project_duration"] == 9.0  # A(4) + B(2) + D(3) = 9.0
    assert scheduler.nodes["A"].is_critical
    assert scheduler.nodes["B"].is_critical
    assert scheduler.nodes["D"].is_critical
    assert not scheduler.nodes["C"].is_critical  # C has slack
    assert scheduler.nodes["C"].slack == 1.0
    assert "SLACK_BORROWED" in scheduler.nodes["C"].allocated_model_tier
    assert "FRONTIER_REASONING" in scheduler.nodes["A"].allocated_model_tier


def test_linda_tuple_space_coordination():
    ts = LindaTupleSpace33()
    ts.out({"topic": "code_review", "status": "pending", "author": "dev1"})
    ts.lease_tuple({"topic": "heartbeat", "agent": "dev1"}, ttl_seconds=60.0)

    # Read
    found = ts.rd({"topic": "code_review"})
    assert found is not None
    assert found["author"] == "dev1"

    # In_tuple (removes)
    taken = ts.in_tuple({"topic": "code_review"})
    assert taken is not None
    assert ts.rd({"topic": "code_review"}) is None

    # Collect
    ts.out({"group": "A", "val": 1})
    ts.out({"group": "A", "val": 2})
    all_a = ts.collect({"group": "A"})
    assert len(all_a) == 2


def test_ast_semantic_reconciler():
    base = ""
    branch_a = """
def func_one():
    return 1
"""
    branch_b = """
def func_two():
    return 2
"""
    merged = ASTSemanticReconciler28.merge_declarations(base, branch_a, branch_b)
    assert "func_one" in merged
    assert "func_two" in merged


def test_aaif_agent_card_and_router():
    router = AAIFHorizontalRouter155(secret="faz155-secret")
    card1 = AgentCard155(
        agent_id="arch-1",
        name="ArchitectAgent",
        capabilities=["system_design", "refactoring"],
        pareto_weights={"accuracy": 0.95, "latency": 0.3},
    )
    card2 = AgentCard155(
        agent_id="fast-1",
        name="FastCodeAgent",
        capabilities=["system_design", "quick_patch"],
        pareto_weights={"accuracy": 0.6, "latency": 0.95},
    )
    router.register_card(card1)
    router.register_card(card2)

    # Route with high accuracy priority
    best_for_accuracy = router.route_task("system_design", {"accuracy": 1.0, "latency": 0.0})
    assert best_for_accuracy == "arch-1"

    # Route with high speed priority
    best_for_speed = router.route_task("system_design", {"accuracy": 0.0, "latency": 1.0})
    assert best_for_speed == "fast-1"

    # PBFT Consensus verification
    votes = ["COMMIT", "COMMIT", "COMMIT", "ABORT"]
    # For N=4, f=1, 2f+1 = 3. 3 COMMIT votes means consensus passes.
    assert router.verify_pbft_consensus(votes, total_nodes=4)


def test_hipporag2_memory_engine_and_dreaming():
    engine = HippoRAG2MemoryEngine(lambda_decay=0.01)
    node = MemoryNode(
        node_id="mem-1",
        content="Autonomous Agent Harness Architecture",
        category="architecture",
        importance=0.8,
    )
    engine.insert(node, ["harness", "agent", "ast_guard"])

    # Query with overlapping entities
    score = engine.compute_retrieval_score("mem-1", {"harness", "agent"})
    assert score > 0.5

    # Dreaming consolidation
    dreamed = engine.dream_consolidate()
    assert "mem-1" in dreamed
    assert engine.nodes["mem-1"].importance >= 0.85


def test_token_physics_skeletonizer_and_repl():
    code = """
class DataProcessor:
    def process(self, x):
        print("heavy calculation")
        return x * 2

def standalone():
    return 42
"""
    skeleton = ASTSkeletonizer41.skeletonize(code)
    assert "pass" in skeleton
    assert "heavy calculation" not in skeleton

    # REPL execution
    repl = CodeActVirtualREPL40()
    res = repl.execute("result = 10 * 5")
    assert res["status"] == "success"
    assert "result" in res["result_scope_keys"]

    # Radix alignment
    aligned = RadixKVBlockAligner.align("one two three", block_size=5)
    tokens = aligned.split()
    assert len(tokens) == 5
    assert tokens.count("<pad>") == 2


def test_faz155_master_swarm_orchestrator_pipeline():
    orchestrator = Faz155MasterSwarmOrchestrator()
    res = orchestrator.run_pipeline("Implement SOTA Agent Hypervisor")
    assert res["lease_acquired"] is True
    assert res["final_task_state"] == "COMPLETED"
    assert res["cpm_metrics"]["project_duration"] > 0
    assert res["tuple_retrieved"]["task"] == "Implement SOTA Agent Hypervisor"
    assert res["harness_metrics"]["status"] == "success"
