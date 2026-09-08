"""
Comprehensive Test Suite for Faz 157 Master Autonomous Agent Architecture
========================================================================
Validates all subsystems:
- FastMCP 31.0 Stateless Headers (21 headers including deadline), Zero-Shot Attenuation, Interceptor & Saga Rollback
- FastMCP Apps Extension (SEP-1866) interactive canvas/form widgets & MCPServer alias
- Hypervisor Harness 21.0 AST Preflight Guard 43.0 (Taint Tracking) & Dynamic Temperature Annealing
- Decoupled Task Contract 27.0 23-State FSM (CANARY_VALIDATION), CAS & Erlang-OTP 21.0 DLQ
- Kahn DAG Wavefront Scheduler 31.0, Stochastic PERT & CPM Slack Borrowing 31.0
- Agent Desks 39.0, Linda Tuple Space 35.0 (multicast_tuple) & AST Reconciler 32
- AAIF Horizontal Federation Router 157 & HMAC AgentCard (17D Green Ratio)
- Sexaginta-Store 55-Layer HippoRAG 2 Dual-Node PPR & Ebbinghaus Decay
- Extreme Token Physics 49.0, CodeAct 42.0 & Radix Alignment
- End-to-End Faz 157 Master Swarm Orchestrator
"""

import pytest
import time
from src.entropy.tools.autonomous_agent_architecture_faz157 import (
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPStatelessGateway,
    MCPServer,
    FastMCPAppWidget,
    ASTPreflightGuard43,
    SpeculativeMCTSNode,
    MerkleCheckpointForest,
    HypervisorAgentHarness21,
    TaskState,
    OTPStrategy,
    DecoupledTaskContract27,
    ErlangOTPSupervisor21,
    DAGTaskNode,
    KahnDAGWavefrontScheduler31,
    LindaTupleSpace35,
    ASTSemanticReconciler32,
    AgentCard157,
    AAIFHorizontalRouter157,
    MemoryNode,
    HippoRAG2MemoryEngine,
    ASTSkeletonizer43,
    CodeActVirtualREPL42,
    RadixKVBlockAligner,
    Faz157MasterSwarmOrchestrator,
)


def test_fastmcp_headers_roundtrip_faz157():
    headers = FastMCPHeaders(
        mcp_name="test_tool_31",
        mcp_stage="validate",
        mcp_routing_nonce="nonce-157-998811",
        mcp_telemetry_budget_tokens=8192,
        mcp_consensus_epoch=51,
        mcp_isolation_boundary="desk-ephemeral-worktree-v157",
        mcp_saga_epoch=4,
        mcp_telemetry_deadline=45000,
    )
    h_dict = headers.to_header_dict()
    assert h_dict["Mcp-Name"] == "test_tool_31"
    assert h_dict["Mcp-Routing-Nonce"] == "nonce-157-998811"
    assert h_dict["Mcp-Telemetry-Budget-Tokens"] == "8192"
    assert h_dict["Mcp-Consensus-Epoch"] == "51"
    assert h_dict["Mcp-Isolation-Boundary"] == "desk-ephemeral-worktree-v157"
    assert h_dict["Mcp-Saga-Epoch"] == "4"
    assert h_dict["Mcp-Telemetry-Deadline"] == "45000"

    restored = FastMCPHeaders.from_header_dict(h_dict)
    assert restored.mcp_name == "test_tool_31"
    assert restored.mcp_routing_nonce == "nonce-157-998811"
    assert restored.mcp_telemetry_budget_tokens == 8192
    assert restored.mcp_consensus_epoch == 51
    assert restored.mcp_isolation_boundary == "desk-ephemeral-worktree-v157"
    assert restored.mcp_saga_epoch == 4
    assert restored.mcp_telemetry_deadline == 45000


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


def test_fastmcp_interceptor_rejection():
    gw = FastMCPStatelessGateway()
    gw.register_tool("secure_op", lambda: "ok")
    gw.add_interceptor(lambda h, p: (False, "Policy Violation: Unauthorized tenant"))

    headers = FastMCPHeaders(mcp_name="secure_op")
    res = gw.execute_stateless(headers, {})
    assert res["status"] == "rejected_by_interceptor"
    assert "Policy Violation" in res["reason"]


def test_fastmcp_mrtr_206_input_required():
    gw = FastMCPStatelessGateway()
    gw.register_tool("deploy_service", lambda target: f"deployed to {target}")

    headers = FastMCPHeaders(mcp_name="deploy_service")
    res = gw.execute_stateless(headers, {"__request_input": True, "__missing_fields": ["env", "api_key"]})
    assert res["status"] == "mrtr_206_input_required"
    assert "env" in res["required_fields"]
    assert res["elicitation_nonce"] is not None


def test_fastmcp_apps_widget():
    widget = FastMCPAppWidget(
        widget_id="widget-canvas-157",
        uri="ui://entropy/canvas/editor",
        title="Agent Desks UI Canvas",
        component_type="canvas",
        schema={"properties": {"zoom": {"type": "number"}}},
        state={"zoom": 1.0, "active_desk": "desk/architecture"},
    )
    rendered = widget.render_json()
    assert rendered["widget_id"] == "widget-canvas-157"
    assert rendered["component_type"] == "canvas"
    assert rendered["state"]["active_desk"] == "desk/architecture"
    assert MCPServer == FastMCPStatelessGateway


def test_ast_preflight_guard_taint_and_security():
    # Valid code
    safe_code = "x = 10\ny = x * 2\nprint(y)"
    is_safe, violations = ASTPreflightGuard43.inspect_code(safe_code)
    assert is_safe
    assert len(violations) == 0

    # Forbidden import
    unsafe_import = "import os.system\nos.system('dir')"
    is_safe2, violations2 = ASTPreflightGuard43.inspect_code(unsafe_import)
    assert not is_safe2
    assert any("Forbidden" in v for v in violations2)

    # Dynamic execution
    unsafe_eval = "eval('__import__(\"sys\").exit()')"
    is_safe3, violations3 = ASTPreflightGuard43.inspect_code(unsafe_eval)
    assert not is_safe3
    assert any("Dynamic execution" in v for v in violations3)

    # Path traversal
    unsafe_path = "with open('../../secret.txt', 'r') as f: pass"
    is_safe4, violations4 = ASTPreflightGuard43.inspect_code(unsafe_path)
    assert not is_safe4
    assert any("traversal" in v for v in violations4)

    # Taint tracking: external untrusted input flows into open sink
    taint_code = """
untrusted_file = input()
f = open(untrusted_file, 'r')
"""
    is_safe5, violations5 = ASTPreflightGuard43.inspect_code(taint_code)
    assert not is_safe5
    assert any("Tainted sink vulnerability" in v for v in violations5)


def test_hypervisor_harness_and_merkle_faz157():
    harness = HypervisorAgentHarness21(initial_temp=0.8, cooling_gamma=0.5)

    # Temperature annealing
    assert harness.compute_annealed_temperature(0) == 0.8
    assert harness.compute_annealed_temperature(1) == 0.4
    assert harness.compute_annealed_temperature(2) == 0.2

    # Checkpoint and evaluation
    initial_state = {"phase": 157, "desk": "engineering"}
    res = harness.evaluate_and_run("def add(a, b): return a + b", initial_state, retry_attempt=1)
    assert res["success"]
    assert res["temperature"] == 0.4

    # Restore from Merkle
    restored = harness.merkle_forest.restore_checkpoint(res["checkpoint_hash"])
    assert restored["phase"] == 157


def test_decoupled_task_contract_and_canary_state():
    contract = DecoupledTaskContract27(
        task_id="task-cpm-157",
        title="Architecture Synthesis",
        description="Synthesize Faz 157 Master Architecture",
    )
    assert contract.state == TaskState.UNASSIGNED
    assert not contract.is_zombie()

    # CAS Success to ACQUIRED
    ok = contract.compare_and_swap_state(expected_epoch=1, new_state=TaskState.ACQUIRED, new_agent="agent-arch-157")
    assert ok
    assert contract.state == TaskState.ACQUIRED
    assert contract.version_epoch == 2
    assert contract.assigned_agent == "agent-arch-157"

    # CAS to CANARY_VALIDATION (23rd state)
    ok_canary = contract.compare_and_swap_state(expected_epoch=2, new_state=TaskState.CANARY_VALIDATION)
    assert ok_canary
    assert contract.state == TaskState.CANARY_VALIDATION
    assert contract.version_epoch == 3

    # Stale Epoch Failure
    fail = contract.compare_and_swap_state(expected_epoch=2, new_state=TaskState.IN_PROGRESS)
    assert not fail
    assert contract.state == TaskState.CANARY_VALIDATION

    # Heartbeat refresh
    assert contract.refresh_heartbeat("agent-arch-157")
    assert not contract.refresh_heartbeat("impostor-agent")

    # Zombie Detection
    simulated_future = time.time() + 20.0
    assert contract.is_zombie(now=simulated_future)


def test_erlang_otp_supervisor_dlq_faz157():
    sup = ErlangOTPSupervisor21(strategy=OTPStrategy.ONE_FOR_ONE, max_restarts=2, window_seconds=10.0)
    task = DecoupledTaskContract27(task_id="t-error-157", title="Fail Task", description="Error")

    # Restart 1
    r1 = sup.handle_worker_failure("worker-a", task, "Memory Error")
    assert "RESTARTED" in r1

    # Restart 2
    r2 = sup.handle_worker_failure("worker-a", task, "Timeout")
    assert "RESTARTED" in r2

    # Restart 3 -> DLQ Escalation
    r3 = sup.handle_worker_failure("worker-a", task, "Crash Loop")
    assert r3 == "ESCALATED_TO_DLQ"
    assert len(sup.dead_letter_queue) == 1
    assert sup.dead_letter_queue[0]["worker_id"] == "worker-a"
    assert task.state == TaskState.QUARANTINED


def test_kahn_dag_wavefront_and_slack_borrowing_faz157():
    scheduler = KahnDAGWavefrontScheduler31()

    t1 = DAGTaskNode(node_id="t1", name="Init", optimistic_duration=1, most_likely_duration=2, pessimistic_duration=3)
    t2 = DAGTaskNode(node_id="t2", name="BranchA", dependencies={"t1"}, optimistic_duration=2, most_likely_duration=4, pessimistic_duration=6)
    t3 = DAGTaskNode(node_id="t3", name="BranchB", dependencies={"t1"}, optimistic_duration=0.5, most_likely_duration=1, pessimistic_duration=1.5)
    t4 = DAGTaskNode(node_id="t4", name="Merge", dependencies={"t2", "t3"}, optimistic_duration=1, most_likely_duration=1, pessimistic_duration=1)

    scheduler.add_node(t1)
    scheduler.add_node(t2)
    scheduler.add_node(t3)
    scheduler.add_node(t4)

    total_dur = scheduler.compute_cpm_and_slack()
    assert total_dur > 0

    # Critical path validation: t1 -> t2 -> t4 is longer than t1 -> t3 -> t4
    assert t2.slack == 0.0
    assert "Frontier-Reasoning" in t2.assigned_model_tier
    assert t3.slack > 0.0
    assert "High-Throughput-Fast" in t3.assigned_model_tier

    # Wavefront batches
    batches = scheduler.get_wavefront_batches()
    assert len(batches) == 3
    assert batches[0] == ["t1"]
    assert set(batches[1]) == {"t2", "t3"}
    assert batches[2] == ["t4"]


def test_linda_tuple_space_multicast_faz157():
    ts = LindaTupleSpace35()
    ts.out("task_event", "task-157", "ready", lease_seconds=60)

    # Multicast broadcast to multiple listener tags
    ts.multicast_tuple(["desk_engineering", "desk_qa"], "task-157", "started", lease_seconds=60)

    # Read pattern
    read_eng = ts.rd("desk_engineering", ("task-157", "started"))
    assert read_eng is not None
    assert read_eng.fields[1] == "started"

    read_qa = ts.rd("desk_qa", ("task-157", "started"))
    assert read_qa is not None
    assert read_qa.fields[1] == "started"

    # Take tuple
    in_t = ts.in_tuple("task_event", ("task-157", "ready"))
    assert in_t is not None
    assert ts.rd("task_event", ("task-157", "ready")) is None


def test_ast_semantic_reconciler_faz157():
    base = "def foo(): pass\n"
    branch_a = "def foo(): pass\ndef func_a(): return 'A'\n"
    branch_b = "def foo(): pass\ndef func_b(): return 'B'\n"

    success, merged = ASTSemanticReconciler32.reconcile(base, branch_a, branch_b)
    assert success
    assert "func_a" in merged
    assert "func_b" in merged

    # Conflict on same func
    branch_conflict = "def func_a(): return 'Conflict'\n"
    succ2, _ = ASTSemanticReconciler32.reconcile(base, branch_a, branch_conflict)
    assert not succ2


def test_aaif_horizontal_router_17d_green_faz157():
    router = AAIFHorizontalRouter157()
    c1 = AgentCard157(
        agent_id="agent-fast",
        name="FastAgent",
        domain="code",
        cost_per_1k_tokens=0.0005,
        latency_p95_ms=80.0,
        reliability_score=0.98,
        energy_green_ratio=0.98,
    )
    c2 = AgentCard157(
        agent_id="agent-frontier",
        name="FrontierAgent",
        domain="code",
        cost_per_1k_tokens=0.01,
        latency_p95_ms=600.0,
        reliability_score=0.999,
        energy_green_ratio=0.85,
    )

    router.register_card(c1)
    router.register_card(c2)

    # Select within budget
    best_fast = router.select_best_agent(max_cost=0.001, max_latency_ms=100.0)
    assert best_fast is not None
    assert best_fast.agent_id == "agent-fast"

    # HMAC Signature with green ratio
    sig = c1.sign_handshake("secret-token-157")
    assert len(sig) == 64


def test_hipporag2_and_ebbinghaus_faz157():
    engine = HippoRAG2MemoryEngine(lambda_forget=0.1)

    engine.add_memory(node_id="doc-harness", text="Hypervisor Harness 21.0 Architecture", importance=2.0, associations={"doc-desks"})
    engine.add_memory(node_id="doc-desks", text="Agent Desks Multi-Worktree Isolation", importance=1.5, associations={"doc-harness", "doc-mcp"})
    engine.add_memory(node_id="doc-mcp", text="FastMCP 31.0 Stateless Gateway", importance=1.2)

    # Query multi-hop
    results = engine.dual_node_ppr_query(["doc-harness"], damping=0.85, max_hops=3)
    assert len(results) == 3
    assert results[0][0] in {"doc-harness", "doc-desks"}

    # Retention calculation
    node = engine.nodes["doc-harness"]
    ret_now = engine.compute_retention(node)
    assert ret_now > 1.9

    future = time.time() + 36000.0  # 10 hours later
    ret_future = engine.compute_retention(node, now=future)
    assert ret_future < ret_now


def test_skeletonizer_and_codeact_repl_faz157():
    code = """
def complex_algorithm(data: list) -> int:
    '''Calculates complex algorithmic metric.'''
    x = 0
    for item in data:
        x += item * 2
    return x
"""
    skeleton = ASTSkeletonizer43.skeletonize(code)
    assert "Calculates complex algorithmic metric" in skeleton
    assert "for item in data" not in skeleton
    assert "pass" in skeleton

    # CodeAct REPL
    repl = CodeActVirtualREPL42()
    res = repl.execute_snippet("a = 10\nb = 20\nresult = a + b")
    assert res["success"]
    assert "result" in res["env_keys"]
    assert repl.locals_env["result"] == 30

    # Unsafe snippet rejected
    res_unsafe = repl.execute_snippet("import os.system")
    assert not res_unsafe["success"]


def test_radix_kv_block_aligner_faz157():
    text = "Autonomous Agent Architecture Faz 157 standard prompt tokens."
    padded = RadixKVBlockAligner.align_text_block(text, block_size=64)
    assert len(padded) >= len(text)


def test_e2e_faz157_swarm_orchestrator():
    orch = Faz157MasterSwarmOrchestrator()
    safe_action = "val = 42 * 2\noutput = f'computed_{val}'"
    res = orch.run_e2e_pipeline("Sprint Task 157", safe_action)
    assert res["status"] == "success"
    assert res["state"] == "COMPLETED"
    assert res["memory_nodes_count"] >= 1
    assert res["harness_checkpoint"] is not None
