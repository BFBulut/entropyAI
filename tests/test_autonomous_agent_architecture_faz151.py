"""
Unit & Integration Test Suite for Faz 151 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 25.0 Stateless Gateway, ETag 304, MRTR 206, MCP Apps Widget, Capability Check, Interceptor & Saga Rollback
2. AST Preflight Guard 37.0 (Safe syntax, banned imports, dangerous calls, reflection, traversal)
3. Merkle Checkpoint Forest 15.0 (Filesystem snapshots and zero-loss rollback)
4. Speculative MCTS Evaluator (Tree-of-Thoughts / UCB-1 candidate selection)
5. Dynamic Deterministic Temperature Cooling Schedule (T -> 0.0)
6. Decoupled Task Contract 21.0 & Atomic CAS Heartbeat Lease Zombie Takeover
7. Erlang-OTP 15.0 Supervision Trees (Restart intensity & DLQ escalation)
8. Linda Distributed Tuple Space 29.0 (Out, Rd, In, Collect, Watch)
9. Multi-Granular Single-Writer Boundary (MG-SWB 22.0) & Vector Clocks
10. Kahn DAG Wavefront Scheduler 25.0, Stochastic PERT & CPM Slack Borrowing
11. AAIF A2A Protocol v1.1.0 / v3.5 Federation Router, 11D Pareto Routing & PBFT Consensus
12. HippoRAG 2 Dual-Node Personalized PageRank (PPR) Multi-Hop Associative Walk
13. BiTemporal Graphiti Memory 4.5 (Fact invalidation and time-travel querying)
14. Extreme Token Physics 43.0 (AST Skeletonizer 37.0, Radix KV Block Alignment, Marginal Delta Token Accounting)
15. Faz151MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz151 import (
    FastMCPGateway,
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPAppWidget,
    ASTPreflightGuard37,
    MerkleCheckpointForest15,
    SpeculativeMCTSEvaluator,
    DynamicDeterministicCooling,
    TaskState,
    DecoupledTaskContract21,
    ErlangOTPSupervisor15,
    SupervisionStrategy,
    LindaTupleSpace29,
    AgentDesk33,
    MultiGranularSingleWriterBoundary,
    KahnDAGWavefrontScheduler25,
    DAGTaskNode,
    AgentCard151,
    A2AFederationRouter,
    HippoRAG2PersonalizedPageRank,
    BiTemporalGraphitiMemory,
    ASTSkeletonizer37,
    RadixKVCacheAligner,
    MarginalDeltaTokenAccountant,
    Faz151MasterSwarmOrchestrator,
    MCTSNode,
)


# ==============================================================================
# 1. FASTMCP 25.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp_gateway_stateless_invocation():
    gateway = FastMCPGateway(secret_key="test-secret")
    gateway.register_tool(
        "calculate_sum",
        lambda a, b: a + b,
        "(a: int, b: int) -> int"
    )

    headers = FastMCPHeaders(
        mcp_name="calculate_sum",
        mcp_transport=FastMCPTransport.HTTP_STATELESS,
        mcp_qos_tier=FastMCPQoSTier.STANDARD_INTERACTIVE
    )

    res = gateway.invoke(headers, {"a": 10, "b": 25})
    assert res["status"] == 200
    assert res["result"] == 35
    assert "etag" in res

    # Check ETag 304 Caching
    res_cached = gateway.invoke(headers, {"a": 10, "b": 25})
    assert res_cached["status"] == 304
    assert res_cached["result"] == 35
    assert res_cached.get("cached") is True


def test_fastmcp_interceptor_and_capability_token():
    gateway = FastMCPGateway(secret_key="test-secret")
    gateway.register_tool("echo", lambda text: text, "(text: str) -> str")

    # Register SEP-1763 Interceptor
    def uppercase_interceptor(tool_name: str, payload: dict) -> dict:
        if tool_name == "echo" and "text" in payload:
            payload["text"] = payload["text"].upper()
        return payload

    gateway.register_interceptor(uppercase_interceptor)

    token = gateway.generate_capability_token("agent-01", ["echo"])
    headers = FastMCPHeaders(mcp_name="echo", mcp_capability_token=token)

    res = gateway.invoke(headers, {"text": "hello mcp"})
    assert res["status"] == 200
    assert res["result"] == "HELLO MCP"

    # Capability Denied
    forbidden_headers = FastMCPHeaders(mcp_name="echo", mcp_capability_token="invalid.token")
    res_denied = gateway.invoke(forbidden_headers, {"text": "hello"})
    assert res_denied["status"] == 403


def test_fastmcp_mrtr_and_saga_rollback():
    gateway = FastMCPGateway(secret_key="test-secret")
    gateway.register_tool("db_provision", lambda instance_type, region: "db_ok", "(...)")

    headers = FastMCPHeaders(mcp_name="db_provision")
    # MRTR 206 input_required
    res = gateway.invoke(headers, {"instance_type": "db.m5.large"})
    assert res["status"] == 206
    assert res["type"] == "input_required"
    assert "region" in res["missing_fields"]

    # Successful call with Saga compensation
    def compensate_drop_db(payload):
        return f"dropped_{payload['region']}"

    res_ok = gateway.invoke(headers, {"instance_type": "db.m5.large", "region": "us-east-1"}, compensation_func=compensate_drop_db)
    assert res_ok["status"] == 200

    # Execute Rollback
    rollback_res = gateway.rollback_saga()
    assert len(rollback_res) == 1
    assert rollback_res[0]["status"] == "compensated"
    assert rollback_res[0]["result"] == "dropped_us-east-1"


def test_fastmcp_app_widget_render():
    widget = FastMCPAppWidget(
        app_id="app-chart-01",
        title="Revenue Chart",
        component_type="chart",
        schema={"type": "line"},
        state={"points": [10, 20, 30]}
    )
    rendered = widget.render()
    assert "data-app-id='app-chart-01'" in rendered
    assert "Revenue Chart" in rendered


# ==============================================================================
# 2. AST PREFLIGHT GUARD 37.0 & MERKLE CHECKPOINTS
# ==============================================================================

def test_ast_preflight_guard():
    safe_code = """
def compute_metrics(x: int) -> int:
    y = x * 2
    return y + 10
"""
    safe, violations = ASTPreflightGuard37.inspect_code(safe_code)
    assert safe is True
    assert len(violations) == 0

    dangerous_code = """
import os
def attack():
    os.system("rm -rf /")
    eval("1 + 1")
    f = open('/etc/passwd')
"""
    is_safe, viols = ASTPreflightGuard37.inspect_code(dangerous_code)
    assert is_safe is False
    assert any("Banned import: os" in v for v in viols)
    assert any("eval" in v for v in viols)
    assert any("open" in v for v in viols)


def test_merkle_checkpoint_forest():
    forest = MerkleCheckpointForest15()
    files_v1 = {"main.py": "print('hello')", "config.json": "{}"}
    root1 = forest.create_checkpoint("v1", files_v1)
    assert isinstance(root1, str)
    assert len(root1) == 64

    # Restore v1
    restored = forest.restore_checkpoint("v1")
    assert restored == files_v1

    # Modify and restore
    files_v2 = {"main.py": "print('world')", "config.json": "{}"}
    root2 = forest.create_checkpoint("v2", files_v2)
    assert root1 != root2
    assert forest.restore_checkpoint("v1")["main.py"] == "print('hello')"


# ==============================================================================
# 3. SPECULATIVE MCTS & DYNAMIC TEMPERATURE COOLING
# ==============================================================================

def test_mcts_evaluator_and_cooling():
    root = MCTSNode(state_id="s0", action="init")
    c1 = MCTSNode(state_id="s1", action="action_1", parent=root)
    c2 = MCTSNode(state_id="s2", action="action_2", parent=root)
    root.children = [c1, c2]

    evaluator = SpeculativeMCTSEvaluator(exploration_weight=1.414)
    # Simulate backprop
    evaluator.backpropagate(c1, reward=1.0)
    evaluator.backpropagate(c2, reward=0.2)

    best = evaluator.select_best_candidate(root)
    assert best == c1

    # Dynamic Cooling Schedule
    t0 = DynamicDeterministicCooling.get_temperature(step=0)
    t5 = DynamicDeterministicCooling.get_temperature(step=5)
    t10 = DynamicDeterministicCooling.get_temperature(step=10)
    assert t0 == 0.7
    assert t5 < t0
    assert t10 == 0.0


# ==============================================================================
# 4. DECOUPLED TASK CONTRACT & ERLANG-OTP SUPERVISION
# ==============================================================================

def test_task_contract_lease_and_zombie_recovery():
    task = DecoupledTaskContract21(task_id="task-101", title="Build Feature")
    t0 = 1000.0

    # Acquire task
    assert task.acquire("agent-alpha", current_time=t0) is True
    assert task.state == TaskState.ACQUIRED
    assert task.lease_owner == "agent-alpha"
    assert task.lease_expires_at == t0 + 15.0

    # Renew heartbeat
    assert task.renew_heartbeat("agent-alpha", current_time=t0 + 10.0) is True
    assert task.lease_expires_at == t0 + 25.0

    # Zombie recovery after expiration
    assert task.check_and_reclaim_zombie(current_time=t0 + 20.0) is False  # not expired yet
    assert task.check_and_reclaim_zombie(current_time=t0 + 30.0) is True   # expired!
    assert task.state == TaskState.ZOMBIE_RECOVERED
    assert task.lease_owner is None


def test_erlang_otp_supervisor_escalation():
    supervisor = ErlangOTPSupervisor15(strategy=SupervisionStrategy.ONE_FOR_ONE, max_restarts=2, window_sec=60.0)
    task = DecoupledTaskContract21(task_id="task-fail", title="Flaky Task")

    action1 = supervisor.handle_failure(task, current_time=10.0)
    assert action1 == "restarted"
    assert task.state == TaskState.ROLLED_BACK

    action2 = supervisor.handle_failure(task, current_time=20.0)
    assert action2 == "restarted"

    # Exceed max_restarts
    action3 = supervisor.handle_failure(task, current_time=30.0)
    assert action3 == "escalated_to_dlq"
    assert task.state == TaskState.ESCALATED
    assert task in supervisor.dead_letter_queue


# ==============================================================================
# 5. KAHN DAG WAVEFRONT & CPM SLACK BORROWING
# ==============================================================================

def test_kahn_dag_scheduler_and_cpm_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler25()

    # Create task diamond: A -> B, A -> C, B -> D, C -> D
    # Task A: O=1, M=2, P=3 => Te = (1 + 8 + 3)/6 = 2.0
    # Task B (longer): O=4, M=4, P=4 => Te = 4.0
    # Task C (shorter): O=1, M=1, P=1 => Te = 1.0
    # Task D: O=2, M=2, P=2 => Te = 2.0
    scheduler.add_node(DAGTaskNode("A", 1, 2, 3))
    scheduler.add_node(DAGTaskNode("B", 4, 4, 4, dependencies=["A"]))
    scheduler.add_node(DAGTaskNode("C", 1, 1, 1, dependencies=["A"]))
    scheduler.add_node(DAGTaskNode("D", 2, 2, 2, dependencies=["B", "C"]))

    wavefronts = scheduler.get_wavefronts()
    assert wavefronts == [["A"], ["B", "C"], ["D"]]

    duration, variance = scheduler.compute_cpm_and_slack_borrowing()
    # Path A -> B -> D: 2 + 4 + 2 = 8.0
    # Path A -> C -> D: 2 + 1 + 2 = 5.0
    assert duration == 8.0
    assert scheduler.nodes["B"].slack == 0.0
    assert scheduler.nodes["B"].is_critical is True
    assert "Frontier" in scheduler.nodes["B"].assigned_model_tier

    # C has slack: LF=6.0, LS=5.0, ES=2.0 => Slack = 3.0
    assert scheduler.nodes["C"].slack == 3.0
    assert scheduler.nodes["C"].is_critical is False
    assert "High_Throughput_Flash" in scheduler.nodes["C"].assigned_model_tier


# ==============================================================================
# 6. LINDA TUPLE SPACE & MG-SWB
# ==============================================================================

def test_linda_tuple_space_and_mg_swb():
    ts = LindaTupleSpace29()
    received = []
    ts.watch("build_event", lambda t: received.append(t))

    ts.out(("build_event", "module_x", "success"))
    assert len(received) == 1
    assert received[0] == ("build_event", "module_x", "success")

    # Pattern read and in_tuple
    match = ts.rd(("build_event", "*", "success"))
    assert match is not None

    taken = ts.in_tuple(("build_event", "module_x", "success"))
    assert taken == ("build_event", "module_x", "success")
    assert ts.rd(("build_event", "*", "success")) is None

    # MG-SWB Dynamic File Leases
    mg_swb = MultiGranularSingleWriterBoundary()
    assert mg_swb.acquire_write_lease("src/main.py", "agent-eng-01") is True
    assert mg_swb.acquire_write_lease("src/main.py", "agent-eng-02") is False  # Locked!
    mg_swb.release_write_lease("src/main.py", "agent-eng-01")
    assert mg_swb.acquire_write_lease("src/main.py", "agent-eng-02") is True   # Unlocked


# ==============================================================================
# 7. AAIF A2A FEDERATION ROUTER & PBFT CONSENSUS
# ==============================================================================

def test_a2a_router_and_pbft_consensus():
    router = A2AFederationRouter()
    c1 = AgentCard151("agent-1", "FastWorker", ["coding"], accuracy_score=0.85, latency_ms=15.0, cost_per_m_tokens=0.2, reputation=0.9, security_clearance=3)
    c2 = AgentCard151("agent-2", "DeepReason", ["coding", "architecture"], accuracy_score=0.99, latency_ms=120.0, cost_per_m_tokens=3.0, reputation=0.98, security_clearance=5)
    router.register_agent(c1)
    router.register_agent(c2)

    # Selecting for high accuracy
    chosen = router.pareto_select("coding", weight_accuracy=0.9, weight_cost=0.05, weight_latency=0.05)
    assert chosen == "agent-2"

    # Selecting for speed & cost
    chosen_fast = router.pareto_select("coding", weight_accuracy=0.1, weight_cost=0.5, weight_latency=0.4)
    assert chosen_fast == "agent-1"

    # PBFT Quorum test: N=4 => f=1 => required_quorum = 2*1 + 1 = 3
    agents = ["a1", "a2", "a3", "a4"]
    votes_success = {"a1": True, "a2": True, "a3": True, "a4": False}
    assert router.pbft_consensus("tx-001", agents, votes_success) is True

    votes_fail = {"a1": True, "a2": False, "a3": False, "a4": False}
    assert router.pbft_consensus("tx-002", agents, votes_fail) is False


# ==============================================================================
# 8. HIPPORAG 2 PPR & BITEMPORAL GRAPHITI MEMORY
# ==============================================================================

def test_hipporag2_ppr_and_bitemporal_graphiti():
    ppr = HippoRAG2PersonalizedPageRank(damping=0.85, max_iter=15)
    ppr.add_edge("Passage_1", "Entity_FastMCP")
    ppr.add_edge("Entity_FastMCP", "Entity_StatelessHeaders")
    ppr.add_edge("Entity_StatelessHeaders", "Passage_2")

    scores = ppr.run_ppr(seed_nodes=["Passage_1"])
    assert "Passage_1" in scores
    assert "Passage_2" in scores
    assert scores["Entity_FastMCP"] > scores["Passage_2"] > 0.0

    # Graphiti BiTemporal Invalidation
    graphiti = BiTemporalGraphitiMemory()
    graphiti.add_fact("f1", "EntropyAI", "version", "Faz150", valid_start=100.0, ingestion_time=105.0)
    # At time 150, update version to Faz151
    graphiti.add_fact("f2", "EntropyAI", "version", "Faz151", valid_start=150.0, ingestion_time=155.0)

    # Query as of t=120 (should be Faz150)
    facts_at_120 = graphiti.query_as_of("EntropyAI", as_of_time=120.0)
    assert len(facts_at_120) == 1
    assert facts_at_120[0].object == "Faz150"

    # Query as of t=160 (should be Faz151)
    facts_at_160 = graphiti.query_as_of("EntropyAI", as_of_time=160.0)
    assert len(facts_at_160) == 1
    assert facts_at_160[0].object == "Faz151"


# ==============================================================================
# 9. EXTREME TOKEN PHYSICS & SKELETONIZER
# ==============================================================================

def test_ast_skeletonizer_and_token_accounting():
    code = """
def complex_function(a: int, b: str) -> bool:
    '''Documentation string.'''
    temp = a * 10
    for i in range(temp):
        print(b)
    return True
"""
    skeleton = ASTSkeletonizer37.skeletonize(code)
    assert "def complex_function(a: int, b: str) -> bool:" in skeleton
    assert "Documentation string." in skeleton
    assert "pass" in skeleton
    assert "print(b)" not in skeleton  # Body stripped!

    # Radix KV Alignment
    raw = "The agent harness controls execution"
    aligned = RadixKVCacheAligner.align_text(raw, block_size=64)
    assert "[PAD]" in aligned

    # Marginal Delta Token Accountant
    accountant = MarginalDeltaTokenAccountant()
    din1, dout1 = accountant.compute_turn_delta(100, 50)
    assert (din1, dout1) == (100, 50)

    din2, dout2 = accountant.compute_turn_delta(150, 80)
    assert (din2, dout2) == (50, 30)  # Correct turn delta, not cumulative lifetime!


# ==============================================================================
# 10. FAZ 151 MASTER SWARM ORCHESTRATOR PIPELINE
# ==============================================================================

def test_master_swarm_orchestrator_pipeline():
    orchestrator = Faz151MasterSwarmOrchestrator()
    res = orchestrator.run_pipeline_step(
        task_name="deploy_agent_mesh",
        code_snippet="def run(): return 42"
    )
    assert res["status"] == "success"
    assert "checkpoint_root" in res

    # Reject dangerous execution
    res_bad = orchestrator.run_pipeline_step(
        task_name="malicious_step",
        code_snippet="import subprocess; subprocess.Popen('calc.exe')"
    )
    assert res_bad["status"] == "rejected"
    assert res_bad["reason"] == "AST_SECURITY_VIOLATION"
