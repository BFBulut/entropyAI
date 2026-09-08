"""
Comprehensive Test Suite for Faz 154 Master Autonomous Agent Architecture
========================================================================
Validates all subsystems:
- FastMCP 28.0 Stateless Headers (18 headers), Zero-Shot Attenuation, Interceptor & Saga Rollback
- Hypervisor Harness 18.0 AST Preflight Guard & Dynamic Annealing
- Decoupled Task Contract 24.0 20-State FSM, CAS & Erlang-OTP 18.0 DLQ
- Kahn DAG Wavefront Scheduler 28.0, Stochastic PERT & CPM Slack Borrowing 28.0
- Agent Desks 36.0, Linda Tuple Space 32.0 & AST Reconciler 26
- AAIF Horizontal Federation Router 154 & HMAC AgentCard
- Tredicim-Store 52-Layer HippoRAG 2 Dual-Node PPR & Ebbinghaus Decay
- Extreme Token Physics 46.0, CodeAct 39.0 & Radix Alignment
- End-to-End Faz 154 Master Swarm Orchestrator
"""

import pytest
import time
from src.entropy.tools.autonomous_agent_architecture_faz154 import (
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPStatelessGateway,
    FastMCPAppWidget,
    ASTPreflightGuard154,
    SpeculativeMCTSNode,
    MerkleCheckpointForest,
    HypervisorAgentHarness18,
    TaskState,
    OTPStrategy,
    DecoupledTaskContract24,
    ErlangOTPSupervisor18,
    DAGTaskNode,
    KahnDAGWavefrontScheduler28,
    LindaTupleSpace32,
    ASTSemanticReconciler26,
    AgentCard154,
    AAIFHorizontalRouter154,
    MemoryNode,
    HippoRAG2MemoryEngine,
    ASTSkeletonizer40,
    CodeActVirtualREPL39,
    RadixKVBlockAligner,
    Faz154MasterSwarmOrchestrator,
)


def test_fastmcp_headers_roundtrip():
    headers = FastMCPHeaders(
        mcp_name="test_tool",
        mcp_stage="validate",
        mcp_routing_nonce="nonce-998811",
        mcp_telemetry_budget_tokens=8192,
        mcp_consensus_epoch=42,
    )
    h_dict = headers.to_header_dict()
    assert h_dict["Mcp-Name"] == "test_tool"
    assert h_dict["Mcp-Routing-Nonce"] == "nonce-998811"
    assert h_dict["Mcp-Telemetry-Budget-Tokens"] == "8192"
    assert h_dict["Mcp-Consensus-Epoch"] == "42"

    restored = FastMCPHeaders.from_header_dict(h_dict)
    assert restored.mcp_name == "test_tool"
    assert restored.mcp_routing_nonce == "nonce-998811"
    assert restored.mcp_telemetry_budget_tokens == 8192
    assert restored.mcp_consensus_epoch == 42


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
        widget_id="w-154",
        widget_type="canvas",
        title="Agent Collaboration Canvas",
        schema={"properties": {"zoom": {"type": "number"}}},
        current_state={"zoom": 1.25},
    )
    rendered = widget.render_json()
    assert rendered["widget_id"] == "w-154"
    assert rendered["widget_type"] == "canvas"
    assert rendered["current_state"]["zoom"] == 1.25


def test_ast_preflight_guard():
    safe_code = """
def compute_metrics(values):
    return sum(values) / len(values)
"""
    allowed, violations = ASTPreflightGuard154.inspect_python_code(safe_code)
    assert allowed
    assert len(violations) == 0

    unsafe_code = """
import os
def malicious():
    eval('os.system("rm -rf /")')
"""
    allowed_unsafe, violations_unsafe = ASTPreflightGuard154.inspect_python_code(unsafe_code)
    assert not allowed_unsafe
    assert any("os" in v for v in violations_unsafe)
    assert any("eval" in v for v in violations_unsafe)


def test_speculative_mcts_and_merkle():
    mcts_node = SpeculativeMCTSNode(action_id="branch_1", visits=4, cumulative_reward=3.2, prm_score=0.9)
    ucb = mcts_node.ucb1(total_parent_visits=16)
    assert ucb > 0.0

    forest = MerkleCheckpointForest()
    state = {"file1.py": "print('hello')", "file2.py": "x = 10"}
    root_hash = forest.create_checkpoint("cp-1", state)
    assert len(root_hash) == 64

    restored = forest.rollback("cp-1")
    assert restored == state


def test_hypervisor_harness_cooling():
    harness = HypervisorAgentHarness18(initial_temp=0.8, cooling_gamma=0.5)
    assert harness.get_temperature() == 0.8
    harness.evaluate_code_action("x = 1")
    assert harness.get_temperature() == pytest.approx(0.4)
    harness.evaluate_code_action("y = 2")
    assert harness.get_temperature() == pytest.approx(0.2)


def test_decoupled_task_contract_fsm_and_cas():
    task = DecoupledTaskContract24(task_id="task-154-alpha")
    assert task.state == TaskState.UNASSIGNED

    # Acquire
    success = task.acquire("agent-lead")
    assert success
    assert task.assigned_agent == "agent-lead"
    assert task.state == TaskState.ACQUIRED
    current_cas = task.cas_token

    # Heartbeat
    hb_ok = task.heartbeat("agent-lead")
    assert hb_ok

    # Bad CAS transition
    failed_trans = task.transition_state(TaskState.IN_PROGRESS, "wrong-cas")
    assert not failed_trans

    # Good CAS transition
    ok_trans = task.transition_state(TaskState.IN_PROGRESS, current_cas)
    assert ok_trans
    assert task.state == TaskState.IN_PROGRESS

    # Rehome state transition test
    rehome_trans = task.transition_state(TaskState.REHOMED, task.cas_token)
    assert rehome_trans
    assert task.state == TaskState.REHOMED


def test_erlang_otp_supervisor():
    restart_count = 0

    def restart_agent():
        nonlocal restart_count
        restart_count += 1

    sup = ErlangOTPSupervisor18(strategy=OTPStrategy.ONE_FOR_ONE, max_restarts=2, time_window=10.0)
    sup.register_child("agent_worker_1", restart_agent)

    # First failure -> restart
    ok1 = sup.handle_child_failure("agent_worker_1", "OOM Exception")
    assert ok1
    assert restart_count == 1

    # Second failure -> restart
    ok2 = sup.handle_child_failure("agent_worker_1", "Network timeout")
    assert ok2
    assert restart_count == 2

    # Third failure -> exceeds limit of 2 -> DLQ
    ok3 = sup.handle_child_failure("agent_worker_1", "Crash loop")
    assert not ok3
    assert len(sup.dead_letter_queue) == 1
    assert sup.dead_letter_queue[0]["escalation"] == "SUPERVISOR_THRESHOLD_EXCEEDED"


def test_kahn_dag_scheduler_and_slack_borrowing():
    sched = KahnDAGWavefrontScheduler28()
    t1 = DAGTaskNode("A", optimistic=1.0, most_likely=2.0, pessimistic=3.0)  # expected = 2.0
    t2 = DAGTaskNode("B", optimistic=2.0, most_likely=4.0, pessimistic=6.0, dependencies={"A"})  # expected = 4.0
    t3 = DAGTaskNode("C", optimistic=0.5, most_likely=1.0, pessimistic=1.5, dependencies={"A"})  # expected = 1.0
    t4 = DAGTaskNode("D", optimistic=1.0, most_likely=1.0, pessimistic=1.0, dependencies={"B", "C"})  # expected = 1.0

    sched.add_task(t1)
    sched.add_task(t2)
    sched.add_task(t3)
    sched.add_task(t4)

    wavefronts, project_dur = sched.compute_cpm()
    assert len(wavefronts) == 3
    assert wavefronts[0] == ["A"]
    assert set(wavefronts[1]) == {"B", "C"}
    assert wavefronts[2] == ["D"]
    assert project_dur == pytest.approx(7.0)

    # Path A -> B -> D is 2 + 4 + 1 = 7 (Critical, Slack = 0)
    # Path A -> C -> D is 2 + 1 + 1 = 4 (Non-critical, Slack = 3)
    assert t2.slack == pytest.approx(0.0)
    assert t3.slack == pytest.approx(3.0)
    assert "FRONTIER_REASONING" in t2.assigned_model_tier
    assert "EFFICIENCY_FLASH" in t3.assigned_model_tier


def test_linda_tuple_space():
    bb = LindaTupleSpace32()
    bb.out(("task", "T1", "pending"))
    bb.out(("task", "T2", "pending"))
    bb.out(("result", "T1", 42))

    read_tuple = bb.rd(("result", "T1", None))
    assert read_tuple == ("result", "T1", 42)

    taken = bb.in_tuple(("task", "T1", "pending"))
    assert taken == ("task", "T1", "pending")
    assert bb.rd(("task", "T1", "pending")) is None

    collected = bb.collect(("task", None, "pending"))
    assert len(collected) == 1
    assert collected[0] == ("task", "T2", "pending")


def test_ast_semantic_reconciler():
    base = "def foo(): pass"
    branch_a = """
def func_a():
    return 'branch_a'
"""
    branch_b = """
def func_b():
    return 'branch_b'
"""
    merged = ASTSemanticReconciler26.reconcile(base, branch_a, branch_b)
    assert "func_a" in merged
    assert "func_b" in merged


def test_a2a_agent_card_and_hmac():
    card = AgentCard154(
        agent_id="arch-specialist-154",
        capabilities=["architecture", "static_analysis"],
        sla_latency_ms=120.0,
        token_cost_per_m=2.5,
        accuracy_score=0.98,
    )
    sig = card.sign_card()
    assert card.verify_card(sig)
    assert not card.verify_card("invalid-sig")


def test_aaif_horizontal_router():
    router = AAIFHorizontalRouter154()
    c1 = AgentCard154("cheap-fast", ["qa"], sla_latency_ms=50.0, token_cost_per_m=0.5, accuracy_score=0.90)
    c2 = AgentCard154("expensive-slow", ["qa"], sla_latency_ms=500.0, token_cost_per_m=10.0, accuracy_score=0.99)
    router.register_agent(c1)
    router.register_agent(c2)

    routed = router.route_task("qa", max_cost=5.0)
    assert routed == "cheap-fast"


def test_hipporag2_associative_ppr():
    engine = HippoRAG2MemoryEngine()
    node1 = MemoryNode("n1", "Harness Engineering for SWE", entities=["Harness", "SWE-bench"])
    node2 = MemoryNode("n2", "Agent Desks Virtualization", entities=["Agent Desks", "Harness"])
    node3 = MemoryNode("n3", "Financial Arbitrage Models", entities=["HJM", "Black-Scholes"])

    engine.add_passage(node1)
    engine.add_passage(node2)
    engine.add_passage(node3)

    results = engine.associative_ppr_query(["SWE-bench"])
    assert len(results) >= 2
    # n1 should have the highest score since it directly matches SWE-bench
    top_node_id, top_score = results[0]
    assert top_node_id == "n1"
    # n2 should also receive positive score via associative hop through 'Harness'
    scores_dict = dict(results)
    assert scores_dict.get("n2", 0.0) > 0.0


def test_ast_skeletonizer():
    full_code = """
def heavy_function(a: int, b: int) -> int:
    x = a * 10
    y = b + 20
    for i in range(100):
        x += i
    return x + y
"""
    skeleton = ASTSkeletonizer40.skeletonize(full_code)
    assert "def heavy_function(a: int, b: int) -> int:" in skeleton
    assert "pass" in skeleton
    assert "range(100)" not in skeleton


def test_codeact_virtual_repl():
    repl = CodeActVirtualREPL39()
    code = """
val = 100
multiplier = 3
result = val * multiplier
result
"""
    ok, out, err = repl.execute(code)
    assert ok
    assert out == 300
    assert err == ""


def test_radix_kv_block_aligner():
    text = "one two three four five"
    aligned = RadixKVBlockAligner.align_tokens(text, block_size=8)
    words = aligned.split()
    assert len(words) == 8
    assert words.count("<pad>") == 3


def test_faz154_master_swarm_orchestrator():
    orchestrator = Faz154MasterSwarmOrchestrator()
    res = orchestrator.run_pipeline("Entropy-Faz154-Verification")
    assert res["status"] == "SWARM_PIPELINE_COMPLETE_FAZ154"
    assert res["project_duration"] > 0
    assert res["repl_result"] == 84
    assert res["memory_retrieved"] >= 1
