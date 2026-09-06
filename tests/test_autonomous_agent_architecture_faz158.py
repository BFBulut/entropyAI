"""
Comprehensive Test Suite for Faz 158 Master Autonomous Agent Architecture
========================================================================
Validates all subsystems:
- FastMCP 32.0 Stateless Headers (22 headers including Mcp-Idempotency-Window-Ms), Zero-Shot Attenuation, Interceptor & Saga Rollback
- FastMCP Apps Extension (SEP-1866) interactive canvas/form widgets & MCPServer alias
- Hypervisor Harness 22.0 AST Preflight Guard 44.0 (Bytecode & Taint Tracking) & Dynamic Temperature Annealing
- Decoupled Task Contract 28.0 24-State FSM (SHADOW_CHALLENGE & CANARY_VALIDATION), CAS & Erlang-OTP 22.0 DLQ
- Kahn DAG Wavefront Scheduler 32.0, Stochastic PERT & CPM Slack Borrowing 32.0
- Agent Desks 40.0, Linda Tuple Space 36.0 (quorum_barrier & multicast_tuple) & AST Reconciler 34
- AAIF Horizontal Federation Router 158 & HMAC AgentCard (18D Jitter Resilience & Green Ratio)
- Septuaginta-Store 56-Layer HippoRAG 2 Dual-Node PPR & Ebbinghaus Decay
- Extreme Token Physics 50.0, CodeAct 43.0 & Radix Alignment
- End-to-End Faz 158 Master Swarm Orchestrator
"""

import math
import pytest
import time
from src.entropy.tools.autonomous_agent_architecture_faz158 import (
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPStatelessGateway,
    MCPServer,
    FastMCPAppWidget,
    ASTPreflightGuard44,
    SpeculativeMCTSNode,
    MerkleCheckpointForest,
    HypervisorAgentHarness22,
    TaskState,
    OTPStrategy,
    DecoupledTaskContract28,
    ErlangOTPSupervisor22,
    DAGTaskNode,
    KahnDAGWavefrontScheduler32,
    LindaTupleSpace36,
    ASTSemanticReconciler34,
    AgentCard158,
    AAIFHorizontalRouter158,
    MemoryNode,
    HippoRAG2MemoryEngine,
    ASTSkeletonizer44,
    CodeActVirtualREPL43,
    RadixKVBlockAligner,
    Faz158MasterSwarmOrchestrator,
)


def test_fastmcp_headers_roundtrip_faz158():
    headers = FastMCPHeaders(
        mcp_name="test_tool_32",
        mcp_stage="validate",
        mcp_routing_nonce="nonce-158-998811",
        mcp_telemetry_budget_tokens=8192,
        mcp_consensus_epoch=52,
        mcp_isolation_boundary="desk-ephemeral-worktree-v158",
        mcp_saga_epoch=5,
        mcp_telemetry_deadline=45000,
        mcp_idempotency_window_ms=720000,
    )
    h_dict = headers.to_header_dict()
    assert h_dict["Mcp-Name"] == "test_tool_32"
    assert h_dict["Mcp-Routing-Nonce"] == "nonce-158-998811"
    assert h_dict["Mcp-Telemetry-Budget-Tokens"] == "8192"
    assert h_dict["Mcp-Consensus-Epoch"] == "52"
    assert h_dict["Mcp-Isolation-Boundary"] == "desk-ephemeral-worktree-v158"
    assert h_dict["Mcp-Saga-Epoch"] == "5"
    assert h_dict["Mcp-Telemetry-Deadline"] == "45000"
    assert h_dict["Mcp-Idempotency-Window-Ms"] == "720000"

    restored = FastMCPHeaders.from_header_dict(h_dict)
    assert restored.mcp_name == "test_tool_32"
    assert restored.mcp_routing_nonce == "nonce-158-998811"
    assert restored.mcp_telemetry_budget_tokens == 8192
    assert restored.mcp_consensus_epoch == 52
    assert restored.mcp_isolation_boundary == "desk-ephemeral-worktree-v158"
    assert restored.mcp_saga_epoch == 5
    assert restored.mcp_telemetry_deadline == 45000
    assert restored.mcp_idempotency_window_ms == 720000


def test_fastmcp_gateway_execution_and_interceptor():
    gw = FastMCPStatelessGateway()

    def multiply_numbers(a: int, b: int) -> int:
        return a * b

    def rollback_mult(a: int, b: int):
        return f"rolled_back_{a}_{b}"

    gw.register_tool("multiply", multiply_numbers, rollback_fn=rollback_mult)

    # Interceptor allowing call
    gw.add_interceptor(lambda h, p: (True, "OK"))

    headers = FastMCPHeaders(mcp_name="multiply")
    res = gw.execute_stateless(headers, {"a": 6, "b": 7})
    assert res["status"] == "success"
    assert res["result"] == 42
    assert len(gw.saga_log) == 1

    # Test Saga rollback
    rb_log = gw.trigger_saga_rollback()
    assert len(rb_log) == 1
    assert rb_log[0]["status"] == "rolled_back"
    assert rb_log[0]["result"] == "rolled_back_6_7"
    assert len(gw.saga_log) == 0


def test_fastmcp_interceptor_rejection():
    gw = FastMCPStatelessGateway()
    gw.register_tool("echo", lambda msg: msg)
    gw.add_interceptor(lambda h, p: (False, "Security policy violation"))

    headers = FastMCPHeaders(mcp_name="echo")
    res = gw.execute_stateless(headers, {"msg": "hello"})
    assert res["status"] == "rejected"
    assert "Security policy violation" in res["message"]


def test_fastmcp_apps_widget_registration():
    gw = FastMCPStatelessGateway()
    widget = FastMCPAppWidget(
        widget_id="param-panel-158",
        widget_type="form",
        title="Agent Governance Panel",
        schema_definition={"field": "risk_tolerance", "type": "number"},
        current_state={"risk_tolerance": 0.05}
    )
    gw.register_app_widget(widget)
    rendered = gw.app_widgets["param-panel-158"].render_json()
    assert rendered["ui_uri"] == "ui://mcp-app/widget/param-panel-158"
    assert rendered["type"] == "form"
    assert rendered["state"]["risk_tolerance"] == 0.05


def test_hypervisor_harness_ast_guard():
    safe_code = """
def calculate_alpha(x, y):
    return x * 2.5 + math.sqrt(y)
"""
    is_safe, violations = ASTPreflightGuard44.inspect_code(safe_code)
    assert is_safe
    assert len(violations) == 0

    unsafe_code = """
import os
def malicious():
    os.system("rm -rf /")
"""
    is_safe_2, violations_2 = ASTPreflightGuard44.inspect_code(unsafe_code)
    assert not is_safe_2
    assert any("os" in v for v in violations_2)


def test_hypervisor_temperature_annealing_and_merkle():
    harness = HypervisorAgentHarness22(initial_temperature=0.8, cooling_rate=0.80)
    t0 = harness.get_temperature_at_step(0)
    t1 = harness.get_temperature_at_step(1)
    t5 = harness.get_temperature_at_step(5)

    assert math.isclose(t0, 0.8)
    assert math.isclose(t1, 0.64)
    assert t5 < t1

    # Merkle Forest rollback
    forest = MerkleCheckpointForest()
    state_v1 = {"step": 1, "status": "draft"}
    h1 = forest.create_checkpoint("cp1", state_v1)
    state_v2 = {"step": 2, "status": "failed"}
    forest.create_checkpoint("cp2", state_v2)

    restored_v1 = forest.rollback("cp1")
    assert restored_v1 == state_v1


def test_speculative_mcts_ucb1():
    root = SpeculativeMCTSNode(action="init", visit_count=10, reward=8.0)
    child1 = SpeculativeMCTSNode(action="branch_a", visit_count=5, reward=4.0)
    child2 = SpeculativeMCTSNode(action="branch_b", visit_count=0, reward=0.0)

    # Unvisited child gets infinite score
    assert child2.ucb1_score(root.visit_count) == float("inf")
    # Visited child gets finite exploitation + exploration score
    score1 = child1.ucb1_score(root.visit_count)
    assert score1 > 0.8


def test_decoupled_task_contract_24_states_and_cas():
    task = DecoupledTaskContract28(task_id="task-158-core", lease_ttl_seconds=5.0)
    assert task.state == TaskState.UNASSIGNED

    # Test new SHADOW_CHALLENGE state
    task.transition(TaskState.SHADOW_CHALLENGE)
    assert task.state == TaskState.SHADOW_CHALLENGE

    # Acquire via CAS
    acquired = task.acquire_lease_cas("agent-001", expected_cas=0)
    assert acquired
    assert task.assigned_agent == "agent-001"
    assert task.cas_version == 1
    assert task.state == TaskState.ACQUIRED

    # Failed CAS race condition
    stale_acquire = task.acquire_lease_cas("agent-002", expected_cas=0)
    assert not stale_acquire


def test_erlang_otp_supervisor_dlq():
    supervisor = ErlangOTPSupervisor22(strategy=OTPStrategy.REST_FOR_ONE, max_restarts=2, within_seconds=10.0)
    task = DecoupledTaskContract28(task_id="fragile-task")

    res1 = supervisor.handle_agent_crash("agent-bad", task, "Memory allocation error")
    assert "RESTARTED_VIA_REST_FOR_ONE" in res1
    assert task.retry_count == 1

    res2 = supervisor.handle_agent_crash("agent-bad", task, "Memory allocation error 2")
    assert "RESTARTED_VIA_REST_FOR_ONE" in res2
    assert task.retry_count == 2

    # 3rd crash within window triggers DLQ escalation
    res3 = supervisor.handle_agent_crash("agent-bad", task, "Fatal fatal")
    assert res3 == "ESCALATED_TO_DLQ"
    assert task.state == TaskState.QUARANTINED
    assert len(supervisor.dead_letter_queue) == 1


def test_kahn_dag_pert_and_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler32()
    # Task A: Critical path
    task_a = DAGTaskNode(task_id="A", optimistic=1.0, most_likely=2.0, pessimistic=3.0)
    # Task B: Non-critical branch
    task_b = DAGTaskNode(task_id="B", optimistic=0.5, most_likely=1.0, pessimistic=1.5)
    # Task C: Dependent on A and B
    task_c = DAGTaskNode(task_id="C", optimistic=2.0, most_likely=3.0, pessimistic=4.0, dependencies={"A", "B"})

    scheduler.add_task(task_a)
    scheduler.add_task(task_b)
    scheduler.add_task(task_c)
    scheduler.compute_cpm_and_slack()

    assert math.isclose(task_a.slack, 0.0, abs_tol=1e-4)
    assert task_a.allocated_model_tier == "frontier_reasoning"

    assert task_b.slack > 0.0
    assert task_b.allocated_model_tier == "hyper_efficient_flash"

    wavefronts = scheduler.get_wavefronts()
    assert len(wavefronts) >= 2


def test_linda_tuple_space_and_quorum_barrier():
    space = LindaTupleSpace36()
    space.out(("job", "extract_features", 101))
    space.out(("job", "train_model", 102))

    # Read pattern
    found = space.rd(("job", "extract_features", None))
    assert found == ("job", "extract_features", 101)

    # In tuple (consume)
    consumed = space.in_tuple(("job", "train_model", None))
    assert consumed == ("job", "train_model", 102)
    assert space.rd(("job", "train_model", None)) is None

    # Quorum Barrier primitive
    v1 = space.quorum_barrier("b-158", "agent_1", required_quorum=2)
    assert not v1  # Only 1 vote so far
    v2 = space.quorum_barrier("b-158", "agent_2", required_quorum=2)
    assert v2  # Now 2 votes, barrier reached


def test_ast_semantic_reconciler():
    code_a = """
def helper_a(x):
    return x + 1
"""
    code_b = """
def helper_b(y):
    return y * 2
"""
    merged = ASTSemanticReconciler34.merge_python_sources("", code_a, code_b)
    assert "def helper_a" in merged
    assert "def helper_b" in merged


def test_aaif_horizontal_router_18d():
    router = AAIFHorizontalRouter158(shared_secret="secret-158-test")
    card_fast = AgentCard158(
        agent_id="agent-flash",
        name="Flash Agent",
        description="Fast code reviewer",
        skills=["code_review"],
        endpoint_url="https://api.entropy.ai/flash",
        accuracy_score=0.92,
        latency_ms=80.0,
        cost_per_mtoken=0.15,
        energy_green_ratio=0.98,
        jitter_resilience=0.99,
    )
    sig_fast = card_fast.compute_hmac_signature("secret-158-test")
    registered = router.register_agent(card_fast, sig_fast)
    assert registered

    routed = router.route_task_18d("code_review")
    assert routed == "agent-flash"


def test_hipporag2_dual_node_ppr_and_ebbinghaus():
    engine = HippoRAG2MemoryEngine(damping_factor=0.85)
    n1 = MemoryNode(node_id="doc_1", node_type="passage", text="FastMCP 32.0 architecture", importance=1.0)
    n2 = MemoryNode(node_id="phrase_1", node_type="phrase", text="Zero-Copy shm", importance=0.8)
    n3 = MemoryNode(node_id="doc_2", node_type="passage", text="Other unrelated note", importance=0.5)

    engine.add_node(n1)
    engine.add_node(n2)
    engine.add_node(n3)
    engine.add_edge("doc_1", "phrase_1")

    ppr = engine.compute_personalized_pagerank(["doc_1"])
    assert ppr["doc_1"] > ppr["doc_2"]
    assert ppr["phrase_1"] > ppr["doc_2"]

    retention = engine.compute_ebbinghaus_retention("doc_1")
    assert retention > 0.0


def test_ast_skeletonizer_token_compression():
    full_code = """
def complex_algorithm(data: list[int]) -> int:
    '''Calculates the sum of squares.'''
    total = 0
    for x in data:
        total += x ** 2
    return total
"""
    skeleton = ASTSkeletonizer44.skeletonize(full_code)
    assert "def complex_algorithm(data: list[int]) -> int:" in skeleton
    assert "Calculates the sum of squares" in skeleton
    assert "pass" in skeleton
    assert "total += x ** 2" not in skeleton


def test_codeact_virtual_repl():
    repl = CodeActVirtualREPL43()
    action_code = """
res_list = [i * 2 for i in range(5)]
total_sum = sum(res_list)
"""
    res = repl.execute_action(action_code)
    assert res["status"] == "success"
    assert repl.scope["total_sum"] == 20


def test_radix_kv_block_aligner():
    text = "System Prompt Definition"
    padded = RadixKVBlockAligner.pad_to_block_boundary(text, block_size_tokens=16)
    assert len(padded) % (16 * 4) == 0


def test_master_swarm_orchestrator_e2e():
    orchestrator = Faz158MasterSwarmOrchestrator()
    summary = orchestrator.run_e2e_pipeline()

    assert summary["mcp_status"] == "success"
    assert summary["mcp_result"] == 358  # 10 * 20 + 158
    assert summary["critical_path_slack_t1"] == 0.0
    assert summary["allocated_tier_t1"] == "frontier_reasoning"
    assert summary["barrier_passed"] is True
    assert summary["repl_status"] == "success"
    assert summary["harness_evaluation"]["effective_harness_rate"] >= 0.99
