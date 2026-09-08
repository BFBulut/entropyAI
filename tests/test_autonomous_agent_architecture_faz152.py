"""
Unit & Integration Test Suite for Faz 152 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 26.0 Stateless Gateway, ETag 304, MRTR 206, MCP Apps Widget, Capability Check, Interceptor & Saga Rollback
2. AST Preflight Guard 38.0 (Safe syntax, banned imports, dangerous calls, reflection, traversal)
3. Merkle Checkpoint Forest 16.0 (Filesystem snapshots and zero-loss rollback)
4. Speculative MCTS Evaluator (Tree-of-Thoughts / UCB-1 candidate selection)
5. Dynamic Deterministic Temperature Cooling Schedule (T -> 0.0)
6. Decoupled Task Contract 22.0 & Atomic CAS Heartbeat Lease Zombie Takeover
7. Erlang-OTP 16.0 Supervision Trees (Restart intensity & DLQ escalation)
8. Linda Distributed Tuple Space 30.0 (Out, Rd, In, Collect, Watch)
9. Multi-Granular Single-Writer Boundary (MG-SWB 23.0) & Vector Clocks
10. Kahn DAG Wavefront Scheduler 26.0, Stochastic PERT & CPM Slack Borrowing 26.0
11. AAIF A2A Protocol v1.2.0 / v3.6 Federation Router, 12D Pareto Routing & PBFT Consensus
12. HippoRAG 2 Dual-Node Personalized PageRank (PPR) Multi-Hop Associative Walk
13. BiTemporal Graphiti Memory 4.5 (Fact invalidation and time-travel querying)
14. Extreme Token Physics 44.0 (AST Skeletonizer 38.0, Radix KV Block Alignment, Marginal Delta Token Accounting)
15. Faz152MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz152 import (
    FastMCPGateway,
    FastMCPHeaders,
    FastMCPTransport,
    FastMCPQoSTier,
    FastMCPAppWidget,
    ASTPreflightGuard38,
    MerkleCheckpointForest16,
    SpeculativeMCTSEvaluator,
    DynamicDeterministicCooling,
    TaskState,
    DecoupledTaskContract22,
    ErlangOTPSupervisor16,
    SupervisionStrategy,
    LindaTupleSpace30,
    AgentDesk34,
    MultiGranularSingleWriterBoundary,
    KahnDAGWavefrontScheduler26,
    DAGTaskNode,
    AgentCard152,
    A2AFederationRouter,
    HippoRAG2PersonalizedPageRank,
    BiTemporalGraphitiMemory,
    ASTSkeletonizer38,
    RadixKVCacheAligner,
    MarginalDeltaTokenAccountant,
    Faz152MasterSwarmOrchestrator,
    MCTSNode,
)


# ==============================================================================
# 1. FASTMCP 26.0 STATELESS GATEWAY TESTS
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
    res = gateway.invoke(headers, {"text": "hello entropy"})
    assert res["status"] == 200
    assert res["result"] == "HELLO ENTROPY"

    # Denied tool
    token_restricted = gateway.generate_capability_token("agent-02", ["other_tool"])
    headers_restricted = FastMCPHeaders(mcp_name="echo", mcp_capability_token=token_restricted)
    res_denied = gateway.invoke(headers_restricted, {"text": "hello"})
    assert res_denied["status"] == 403


def test_fastmcp_mrtr_and_saga_compensation():
    gateway = FastMCPGateway()
    gateway.register_tool("db_provision", lambda instance_type, region: f"db_{instance_type}_{region}", "...")

    # Missing fields -> MRTR 206 input_required
    headers = FastMCPHeaders(mcp_name="db_provision")
    res_missing = gateway.invoke(headers, {"instance_type": "db.m5.large"})
    assert res_missing["status"] == 206
    assert res_missing["type"] == "input_required"
    assert "region" in res_missing["missing_fields"]

    # Valid invocation with saga compensation
    compensated_items = []
    comp_fn = lambda p: compensated_items.append(p["instance_type"]) or "rolled_back"
    res_success = gateway.invoke(headers, {"instance_type": "db.m5.large", "region": "us-east-1"}, compensation_func=comp_fn)
    assert res_success["status"] == 200

    # Trigger Saga Rollback
    rollback_res = gateway.rollback_saga()
    assert len(rollback_res) == 1
    assert rollback_res[0]["status"] == "compensated"
    assert compensated_items == ["db.m5.large"]


def test_fastmcp_app_widget_render():
    widget = FastMCPAppWidget(
        app_id="sql_explorer",
        title="SQL Query Canvas",
        component_type="canvas",
        schema={"columns": ["id", "query", "latency"]},
        state={"active_query": "SELECT * FROM memories"}
    )
    rendered = widget.render()
    assert "fastmcp-app-widget" in rendered
    assert "SQL Query Canvas" in rendered
    assert "SELECT * FROM memories" in rendered


# ==============================================================================
# 2. HYPERVISOR AGENT HARNESS 16.0 TESTS
# ==============================================================================

def test_ast_preflight_guard_safety():
    safe_code = """
def compute_metrics(values):
    return sum(values) / len(values)
"""
    safe, violations = ASTPreflightGuard38.inspect_code(safe_code)
    assert safe is True
    assert len(violations) == 0

    dangerous_code_1 = "import subprocess; subprocess.Popen('calc.exe')"
    safe_1, v_1 = ASTPreflightGuard38.inspect_code(dangerous_code_1)
    assert safe_1 is False
    assert any("subprocess" in v for v in v_1)

    dangerous_code_2 = "res = eval('2 + 2')"
    safe_2, v_2 = ASTPreflightGuard38.inspect_code(dangerous_code_2)
    assert safe_2 is False
    assert any("eval" in v for v in v_2)

    dangerous_code_3 = "x = ().__class__.__subclasses__()"
    safe_3, v_3 = ASTPreflightGuard38.inspect_code(dangerous_code_3)
    assert safe_3 is False
    assert any("__subclasses__" in v for v in v_3)

    dangerous_code_4 = "with open('../../secret.txt') as f: pass"
    safe_4, v_4 = ASTPreflightGuard38.inspect_code(dangerous_code_4)
    assert safe_4 is False
    assert any("Path traversal" in v or "open" in v for v in v_4)


def test_merkle_checkpoint_forest_integrity():
    forest = MerkleCheckpointForest16()
    files = {
        "src/core.py": "def main(): print('v1')",
        "config.json": "{\"version\": 1}"
    }
    root_hash = forest.create_checkpoint("v1.0", files)
    assert len(root_hash) == 64

    restored = forest.restore_checkpoint("v1.0")
    assert restored is not None
    assert restored["src/core.py"] == files["src/core.py"]


def test_speculative_mcts_evaluator():
    evaluator = SpeculativeMCTSEvaluator(exploration_weight=1.414)
    root = MCTSNode(state_id="root", action="root")

    c1 = MCTSNode(state_id="branch_1", action="action_A", parent=root)
    c2 = MCTSNode(state_id="branch_2", action="action_B", parent=root)
    root.children = [c1, c2]

    # Simulating backpropagation
    evaluator.backpropagate(c1, reward=1.0)
    evaluator.backpropagate(c2, reward=0.2)

    best = evaluator.select_best_candidate(root)
    assert best is not None
    assert best.action == "action_A"


def test_dynamic_deterministic_cooling():
    t0 = DynamicDeterministicCooling.get_temperature(step=0)
    t5 = DynamicDeterministicCooling.get_temperature(step=5)
    t10 = DynamicDeterministicCooling.get_temperature(step=10)

    assert t0 > t5 > t10
    assert t10 == 0.0


# ==============================================================================
# 3. DECOUPLED TASK CONTRACT & ERLANG-OTP SUPERVISION TESTS
# ==============================================================================

def test_decoupled_task_contract_and_zombie_recovery():
    task = DecoupledTaskContract22(task_id="t-100", title="Code Refactoring", heartbeat_ttl_sec=5.0)
    now = 1000.0

    # Acquire
    assert task.acquire("agent-alpha", now) is True
    assert task.state == TaskState.ACQUIRED
    assert task.lease_owner == "agent-alpha"

    # Renew
    assert task.renew_heartbeat("agent-alpha", now + 2.0) is True
    assert task.lease_expires_at == now + 7.0

    # Zombie reclamation
    assert task.check_and_reclaim_zombie(now + 4.0) is False  # Not yet expired
    assert task.check_and_reclaim_zombie(now + 8.0) is True   # Expired
    assert task.state == TaskState.ZOMBIE_RECOVERED
    assert task.lease_owner is None

    # New agent re-acquires
    assert task.acquire("agent-beta", now + 8.5) is True
    assert task.state == TaskState.ACQUIRED
    assert task.lease_owner == "agent-beta"


def test_erlang_otp_supervision_tree():
    supervisor = ErlangOTPSupervisor16(max_restarts=2, window_sec=60.0)
    task = DecoupledTaskContract22(task_id="t-200", title="Unstable Job")

    res1 = supervisor.handle_failure(task, 100.0)
    assert res1 == "restarted"
    assert task.state == TaskState.ROLLED_BACK

    res2 = supervisor.handle_failure(task, 110.0)
    assert res2 == "restarted"

    res3 = supervisor.handle_failure(task, 120.0)
    assert res3 == "escalated_to_dlq"
    assert task.state == TaskState.ESCALATED
    assert len(supervisor.dead_letter_queue) == 1


# ==============================================================================
# 4. KAHN DAG WAVEFRONT & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_cpm_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler26()

    # Create task nodes: T1 -> T2 -> T4, and T1 -> T3 -> T4
    # T2 is longer, so T1 -> T2 -> T4 is critical path; T3 has slack!
    scheduler.add_node(DAGTaskNode("T1", 2, 2, 2))                    # Expected: 2.0
    scheduler.add_node(DAGTaskNode("T2", 6, 6, 6, dependencies=["T1"]))  # Expected: 6.0
    scheduler.add_node(DAGTaskNode("T3", 2, 2, 2, dependencies=["T1"]))  # Expected: 2.0 (Slack!)
    scheduler.add_node(DAGTaskNode("T4", 3, 3, 3, dependencies=["T2", "T3"])) # Expected: 3.0

    duration, variance = scheduler.compute_cpm_and_slack_borrowing()
    assert duration == 11.0  # 2 + 6 + 3 = 11.0

    t1 = scheduler.nodes["T1"]
    t2 = scheduler.nodes["T2"]
    t3 = scheduler.nodes["T3"]
    t4 = scheduler.nodes["T4"]

    assert t1.is_critical is True
    assert t2.is_critical is True
    assert t4.is_critical is True
    assert t3.is_critical is False
    assert t3.slack == 4.0  # (11 - 3 - 2) - 2 = 4.0

    assert "Frontier_Deep_Reasoning" in t2.assigned_model_tier
    assert "High_Throughput_Flash" in t3.assigned_model_tier


# ==============================================================================
# 5. AGENT DESKS & LINDA TUPLE SPACE TESTS
# ==============================================================================

def test_linda_tuple_space_operations():
    ts = LindaTupleSpace30()
    notifications = []
    ts.watch("job_ready", lambda t: notifications.append(t[1]))

    # out
    ts.out(("job_ready", "job_42", "high_priority"))
    assert notifications == ["job_42"]

    # rd (non-destructive)
    read_t = ts.rd(("job_ready", "*", "*"))
    assert read_t is not None
    assert read_t[1] == "job_42"

    # in_tuple (destructive take)
    in_t = ts.in_tuple(("job_ready", "*", "*"))
    assert in_t is not None
    assert ts.rd(("job_ready", "*", "*")) is None


def test_multi_granular_single_writer_boundary():
    mgswb = MultiGranularSingleWriterBoundary()
    assert mgswb.acquire_write_lease("src/main.py", "agent-1", ttl=10.0) is True
    assert mgswb.acquire_write_lease("src/main.py", "agent-2", ttl=10.0) is False

    mgswb.release_write_lease("src/main.py", "agent-1")
    assert mgswb.acquire_write_lease("src/main.py", "agent-2", ttl=10.0) is True


# ==============================================================================
# 6. AAIF A2A FEDERATION ROUTER & PBFT CONSENSUS TESTS
# ==============================================================================

def test_a2a_federation_router_and_pbft():
    router = A2AFederationRouter(secret_key="aaif-key")

    agent_a = AgentCard152("ag-1", "CodeArchitect", ["code_review", "refactor"], 0.95, 120.0, 5.0, 0.98, 0.9, "L2")
    agent_b = AgentCard152("ag-2", "FastRefactorer", ["refactor"], 0.85, 40.0, 1.0, 0.90, 0.7, "L1")

    router.register_agent(agent_a)
    router.register_agent(agent_b)

    selected = router.select_pareto_agent("refactor", max_cost_per_m=6.0, min_accuracy=0.8)
    assert selected is not None
    assert selected.agent_id in ("ag-1", "ag-2")

    # PBFT Consensus verification
    votes = ["APPROVE", "APPROVE", "APPROVE", "REJECT"]
    # Total nodes = 4, f = (4-1)//3 = 1, quorum needed = 2*1 + 1 = 3
    assert router.verify_pbft_quorum(votes, "APPROVE", total_nodes=4) is True
    assert router.verify_pbft_quorum(votes, "REJECT", total_nodes=4) is False


# ==============================================================================
# 7. NOVUNDECIM-STORE 50-LAYER MEMORY & GRAPHRAG TESTS
# ==============================================================================

def test_hipporag2_personalized_page_rank():
    ppr = HippoRAG2PersonalizedPageRank(alpha=0.85)
    # Graph: (Passage_1) <-> (Entity_AI) <-> (Passage_2)
    ppr.add_edge("P1", "E_AI")
    ppr.add_edge("E_AI", "P2")
    ppr.add_edge("P2", "E_Agent")

    ranks = ppr.run_ppr(seed_nodes=["P1"], iterations=30)
    assert ranks["P1"] > 0
    assert ranks["E_AI"] > 0
    assert ranks["P2"] > 0
    assert ranks["P1"] > ranks["E_Agent"]  # Decay over multi-hop distance


def test_bitemporal_graphiti_memory():
    graphiti = BiTemporalGraphitiMemory()
    now = 100.0

    # Fact 1: Batu works at TechCorp
    graphiti.add_fact("f1", "Batu", "works_at", "TechCorp", valid_start=now, ingestion_time=now)

    # Time travels to t=105
    res_105 = graphiti.query_as_of("Batu", 105.0)
    assert len(res_105) == 1
    assert res_105[0].object == "TechCorp"

    # Fact 2: At t=110, Batu transitions to EntropiAI
    graphiti.add_fact("f2", "Batu", "works_at", "EntropiAI", valid_start=110.0, ingestion_time=110.0)

    # Querying at t=105 returns TechCorp; Querying at t=115 returns EntropiAI
    assert graphiti.query_as_of("Batu", 105.0)[0].object == "TechCorp"
    assert graphiti.query_as_of("Batu", 115.0)[0].object == "EntropiAI"


# ==============================================================================
# 8. EXTREME TOKEN PHYSICS TESTS
# ==============================================================================

def test_extreme_token_physics():
    # 1. AST Skeletonizer 38.0
    code = """
def heavy_processing(data: list) -> dict:
    '''Performs expensive calculations.'''
    x = [i * 2 for i in data]
    return {'result': sum(x)}
"""
    skeleton = ASTSkeletonizer38.skeletonize(code)
    assert "def heavy_processing(data: list) -> dict:" in skeleton
    assert "Performs expensive calculations." in skeleton
    assert "pass" in skeleton
    assert "x = [i * 2 for i in data]" not in skeleton

    # 2. Radix KV Cache Aligner
    text = "Initial system prompt context for autonomous agents."
    aligned = RadixKVCacheAligner.align_text(text, block_size=64)
    assert "[PAD]" in aligned or len(text.split()) * 1.33 % 64 == 0

    # 3. Marginal Delta Token Accounting
    accountant = MarginalDeltaTokenAccountant()
    din1, dout1 = accountant.compute_turn_delta(curr_cum_input=1000, curr_cum_output=200)
    assert din1 == 1000 and dout1 == 200

    # Turn 2: Cumulative increases to 1400 in, 350 out
    din2, dout2 = accountant.compute_turn_delta(curr_cum_input=1400, curr_cum_output=350)
    assert din2 == 400 and dout2 == 150


# ==============================================================================
# 9. FAZ 152 MASTER SWARM ORCHESTRATOR PIPELINE TEST
# ==============================================================================

def test_faz152_master_swarm_orchestrator_pipeline():
    orchestrator = Faz152MasterSwarmOrchestrator()

    # Valid step
    res_valid = orchestrator.run_pipeline_step("build_feature", "def calculate(): return 42")
    assert res_valid["status"] == "success"
    assert len(res_valid["checkpoint_root"]) == 64

    # Malicious step caught by AST guard
    res_malicious = orchestrator.run_pipeline_step("hack_system", "import os; os.system('format c:')")
    assert res_malicious["status"] == "rejected"
    assert res_malicious["reason"] == "AST_SECURITY_VIOLATION"
