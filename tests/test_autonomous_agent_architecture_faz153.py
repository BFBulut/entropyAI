"""
Comprehensive Test Suite for Faz 153 Master Autonomous Agent Architecture
========================================================================
Validates all subsystems:
- FastMCP 27.0 Stateless Headers, Zero-Shot Attenuation, Interceptor & Saga Rollback
- Hypervisor Harness 17.0 AST Preflight Guard & Dynamic Annealing
- Decoupled Task Contract 23.0 19-State FSM, CAS & Erlang-OTP 17.0 DLQ
- Kahn DAG Wavefront Scheduler 27.0, Stochastic PERT & CPM Slack Borrowing
- Agent Desks 35.0, Linda Tuple Space 31.0 & AST Reconciler 24
- AAIF Horizontal Federation Router 153 & HMAC AgentCard
- Vigintidu-Store 51-Layer HippoRAG 2 Dual-Node PPR & Ebbinghaus Decay
- Extreme Token Physics 45.0, CodeAct 38.0 & Radix Alignment
- End-to-End Faz 153 Master Swarm Orchestrator
"""

import pytest
import time
from src.entropy.tools.autonomous_agent_architecture_faz153 import (
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPStatelessGateway,
    FastMCPAppWidget,
    ASTPreflightGuard153,
    SpeculativeMCTSNode,
    MerkleCheckpointForest,
    HypervisorAgentHarness17,
    TaskState,
    OTPStrategy,
    DecoupledTaskContract23,
    ErlangOTPSupervisor17,
    DAGTaskNode,
    KahnDAGWavefrontScheduler27,
    LindaTupleSpace31,
    ASTSemanticReconciler24,
    AgentCard153,
    AAIFHorizontalRouter153,
    MemoryNode,
    HippoRAG2MemoryEngine,
    ASTSkeletonizer39,
    CodeActVirtualREPL38,
    RadixKVBlockAligner,
    Faz153MasterSwarmOrchestrator,
)


def test_fastmcp_headers_roundtrip():
    headers = FastMCPHeaders(
        mcp_name="test_tool",
        mcp_stage="validate",
        mcp_routing_nonce="nonce-998811",
        mcp_telemetry_budget_tokens=8192,
    )
    h_dict = headers.to_header_dict()
    assert h_dict["Mcp-Name"] == "test_tool"
    assert h_dict["Mcp-Routing-Nonce"] == "nonce-998811"
    assert h_dict["Mcp-Telemetry-Budget-Tokens"] == "8192"

    restored = FastMCPHeaders.from_header_dict(h_dict)
    assert restored.mcp_name == "test_tool"
    assert restored.mcp_routing_nonce == "nonce-998811"
    assert restored.mcp_telemetry_budget_tokens == 8192


def test_fastmcp_gateway_execution_and_interceptor():
    gw = FastMCPStatelessGateway()

    def add_numbers(a: int, b: int) -> int:
        return a + b

    def rollback_add(a: int, b: int):
        return f"rolled_back_{a}_{b}"

    schema = {
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    }
    gw.register_tool("add", add_numbers, schema, compensation_fn=rollback_add)

    # 1. Zero-shot stub
    stub = gw.generate_zero_shot_stub("add")
    assert stub == "add(a,b)"

    # 2. MRTR 206 input_required
    headers = FastMCPHeaders(mcp_name="add")
    res_partial = gw.execute_call(headers, {"a": 10})
    assert res_partial["status"] == 206
    assert res_partial["missing_slots"] == ["b"]

    # 3. Successful call
    res_full = gw.execute_call(headers, {"a": 10, "b": 20})
    assert res_full["status"] == 200
    assert res_full["output"] == 30
    assert "etag" in res_full

    # 4. ETag 304 Cache hit
    res_cached = gw.execute_call(headers, {"a": 10, "b": 20})
    assert res_cached["status"] == 304

    # 5. Saga compensation rollback
    assert len(gw.saga_compensation_stack) == 1
    rollback_logs = gw.rollback_saga()
    assert len(rollback_logs) == 1
    assert rollback_logs[0]["status"] == "compensated"


def test_fastmcp_interceptor_injection_defense():
    gw = FastMCPStatelessGateway()
    gw.register_tool("echo", lambda text: text, {"properties": {"text": {"type": "string"}}, "required": ["text"]})

    headers = FastMCPHeaders(mcp_name="echo")
    res = gw.execute_call(headers, {"text": "__import__('os').system('dir')"})
    assert res["status"] == 403
    assert "Interceptor rejected" in res["error"]


def test_ast_preflight_guard():
    safe_code = """
def calculate(x, y):
    return x * y + 42
"""
    passed, violations = ASTPreflightGuard153.audit_code(safe_code)
    assert passed
    assert len(violations) == 0

    unsafe_code = """
import os
os.system('rm -rf /')
"""
    passed2, violations2 = ASTPreflightGuard153.audit_code(unsafe_code)
    assert not passed2
    assert any("os.system" in v or "os" in v for v in violations2)


def test_speculative_mcts_node():
    root = SpeculativeMCTSNode("root", "prompt", "init", visits=10, total_reward=8.0)
    child = SpeculativeMCTSNode("c1", "code", "def f(): pass", visits=2, total_reward=1.8, parent=root)
    score = child.ucb1_score(exploration_constant=1.414)
    assert score > 0.9


def test_merkle_checkpoint_forest():
    forest = MerkleCheckpointForest()
    files = {
        "src/main.py": "print('hello')",
        "src/utils.py": "def foo(): pass",
    }
    root = forest.capture_snapshot("cp-1", files)
    assert len(root) == 64
    assert forest.verify_integrity("cp-1", files)

    tampered_files = dict(files)
    tampered_files["src/main.py"] = "print('tampered')"
    assert not forest.verify_integrity("cp-1", tampered_files)


def test_hypervisor_harness_cooling_and_circuit_breaker():
    harness = HypervisorAgentHarness17(initial_temp=0.7, cooling_rate=0.8)
    t0 = harness.get_temperature(0)
    t1 = harness.get_temperature(1)
    t5 = harness.get_temperature(5)
    assert t0 == 0.7
    assert t1 < t0
    assert t5 < t1

    # Induce circuit breaking via guard violations
    bad_code = "import posix\nposix.fork()"
    harness.evaluate_step(0, bad_code)
    harness.evaluate_step(1, bad_code)
    res3 = harness.evaluate_step(2, bad_code)
    assert res3["verdict"] == "GUARD_VIOLATION"

    res4 = harness.evaluate_step(3, "x = 1")
    assert res4["verdict"] == "REJECTED"


def test_decoupled_task_contract_cas_and_zombie():
    task = DecoupledTaskContract23(task_id="t-100", title="Refactor Engine", heartbeat_ttl_sec=0.1)
    assert task.state == TaskState.UNASSIGNED

    # CAS transition to ACQUIRED
    ok = task.atomic_cas_transition(expected_version=1, new_state=TaskState.ACQUIRED, worker_id="worker-A")
    assert ok
    assert task.state == TaskState.ACQUIRED
    assert task.cas_version == 2

    # Failed CAS transition due to version mismatch
    ok_fail = task.atomic_cas_transition(expected_version=1, new_state=TaskState.IN_PROGRESS)
    assert not ok_fail
    assert task.state == TaskState.ACQUIRED

    # Zombie detection
    time.sleep(0.15)
    assert task.is_zombie()


def test_erlang_otp_supervisor_dlq():
    restart_count = 0

    def restart_agent():
        nonlocal restart_count
        restart_count += 1

    sup = ErlangOTPSupervisor17(strategy=OTPStrategy.ONE_FOR_ONE, max_restarts=2, period_sec=10.0)
    sup.register_worker("w-1", restart_agent)

    r1 = sup.handle_worker_failure("w-1", "crash 1")
    assert r1 == "RESTARTED_ONE"
    assert restart_count == 1

    r2 = sup.handle_worker_failure("w-1", "crash 2")
    assert r2 == "RESTARTED_ONE"
    assert restart_count == 2

    # Third failure exceeds max_restarts (2) -> Escalate to DLQ
    r3 = sup.handle_worker_failure("w-1", "crash 3")
    assert r3 == "ESCALATED_TO_DLQ"
    assert len(sup.dead_letter_queue) == 1


def test_kahn_dag_wavefront_and_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler27()
    n1 = DAGTaskNode("A", 1, 2, 3)
    n2 = DAGTaskNode("B", 2, 4, 6, dependencies=["A"])
    n3 = DAGTaskNode("C", 1, 1, 1, dependencies=["A"])
    n4 = DAGTaskNode("D", 1, 2, 3, dependencies=["B", "C"])

    for n in [n1, n2, n3, n4]:
        scheduler.add_node(n)

    cpm = scheduler.compute_cpm_and_pert()
    assert cpm["project_duration"] > 0
    assert "A" in cpm["critical_path"]
    assert "B" in cpm["critical_path"]
    assert "D" in cpm["critical_path"]

    allocations = scheduler.allocate_models_slack_borrowing()
    assert "Reasoning Frontier" in allocations["B"]
    assert "High Throughput" in allocations["C"]

    wavefronts = scheduler.get_wavefront_batches()
    assert wavefronts[0] == ["A"]
    assert set(wavefronts[1]) == {"B", "C"}
    assert wavefronts[2] == ["D"]


def test_linda_tuple_space():
    linda = LindaTupleSpace31()
    linda.out(("task_ready", "task-99", 1))
    linda.out(("task_ready", "task-100", 2))
    linda.out(("heartbeat", "worker-1", time.time()))

    # Read
    r = linda.rd(("task_ready", None, 1))
    assert r is not None
    assert r[1] == "task-99"

    # Collect
    all_ready = linda.collect(("task_ready", None, None))
    assert len(all_ready) == 2

    # In (consume)
    consumed = linda.in_tuple(("task_ready", "task-99", 1))
    assert consumed == ("task_ready", "task-99", 1)
    assert len(linda.collect(("task_ready", None, None))) == 1


def test_ast_semantic_reconciler():
    base = """
def func_a():
    return 'base_a'

def func_b():
    return 'base_b'
"""

    branch_a = """
def func_a():
    return 'modified_a'

def func_b():
    return 'base_b'
"""

    branch_b = """
def func_a():
    return 'base_a'

def func_b():
    return 'modified_b'
"""

    ok, merged = ASTSemanticReconciler24.reconcile(base, branch_a, branch_b)
    assert ok
    assert "modified_a" in merged
    assert "modified_b" in merged


def test_aaif_router_and_agentcard():
    secret = b"test-secret-aaif"
    router = AAIFHorizontalRouter153(cluster_secret=secret)

    c1 = AgentCard153("agent-architect", "CodeArchitect", pareto_weights={"accuracy": 0.95, "latency": 0.3})
    c2 = AgentCard153("agent-fast", "FastCoder", pareto_weights={"accuracy": 0.6, "latency": 0.95})

    router.register_agent(c1)
    router.register_agent(c2)

    # Accuracy priority
    selected_high_acc = router.select_optimal_agent({"accuracy": 1.0, "latency": 0.1})
    assert selected_high_acc == "agent-architect"

    # Speed priority
    selected_high_speed = router.select_optimal_agent({"accuracy": 0.1, "latency": 1.0})
    assert selected_high_speed == "agent-fast"


def test_hipporag2_and_ebbinghaus():
    memory = HippoRAG2MemoryEngine(damping=0.85)
    n1 = MemoryNode("p1", "passage", "Architecture details")
    n2 = MemoryNode("e1", "entity", "FastMCP")
    n3 = MemoryNode("e2", "entity", "AgentDesks")

    memory.add_node(n1)
    memory.add_node(n2)
    memory.add_node(n3)
    memory.add_bidirectional_edge("p1", "e1")
    memory.add_bidirectional_edge("e1", "e2")

    ppr = memory.personalized_pagerank(["p1"])
    assert ppr["e1"] > 0
    assert ppr["e2"] > 0
    assert ppr["e1"] >= ppr["e2"]

    decayed = memory.ebbinghaus_forgetting_retrieval(ppr, decay_lambda=0.001)
    assert "p1" in decayed
    assert decayed["p1"] > 0


def test_ast_skeletonizer():
    code = """
def heavy_computation(data: list[int]) -> int:
    '''Calculates sum of elements.'''
    s = 0
    for x in data:
        s += x ** 2
    return s
"""
    skeleton = ASTSkeletonizer39.skeletonize(code)
    assert "pass" in skeleton
    assert "for x in data" not in skeleton
    assert "Calculates sum of elements." in skeleton


def test_codeact_virtual_repl():
    repl = CodeActVirtualREPL38()
    code = """
val = 10 * 5
print(f"Val is {val}")
res = val + 2
"""
    result = repl.execute_script(code)
    assert result["success"]
    assert "Val is 50" in result["output"]
    assert result["locals"]["res"] == 52


def test_radix_kv_aligner():
    text = "Short text"
    aligned = RadixKVBlockAligner.align_to_block(text, block_size=16)
    assert len(aligned) >= len(text)
    assert (len(aligned) // 4) % 16 == 0


def test_faz153_master_swarm_orchestrator():
    orchestrator = Faz153MasterSwarmOrchestrator()
    summary = orchestrator.run_end_to_end_pipeline()
    assert summary["status"] == "SUCCESS"
    assert summary["cpm_analysis"]["project_duration"] > 0
    assert summary["tuple_space_count"] >= 1
    assert "Computed total: 100" in summary["codeact_output"]["output"]
