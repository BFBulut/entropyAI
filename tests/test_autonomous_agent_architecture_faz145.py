"""
Unit & Integration Test Suite for Faz 145 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 19.0 Stateless Gateway, OAuth 2.1, Horizon RBAC, ETag 304, MRTR 206, Saga Rollback
2. Decoupled Task Contract 15.0 & Heartbeat Lease Zombie Recovery
3. Erlang-OTP Supervision Tree 9.0 (Restarts, Backoff, Escalation to Root DLQ)
4. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 19.0
5. Hypervisor Agent Harness 9.0 (AST Preflight Guard 31.0, Merkle Checkpoints, Temperature Cooling)
6. Agent Desks 27.0, MG-SWB 16.0 File Locking & Linda Distributed Tuple Space 23.0
7. AAIF Horizontal Federation Router 30, 9D Pareto & PBFT Consensus
8. Tredecim-Store 43-Layer Cognitive Memory (HippoRAG 2 PPR, Graphiti Tri-Temporal, Ebbinghaus)
9. Extreme Token Physics 37.0 (AST Skeletonizer 31.0, Radix KV-Cache Alignment, Marginal Delta Tokens)
10. Skill Progressive Disclosure Standard 12.0 (Tier 1/2/3)
11. Faz145MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest
from entropy.tools.autonomous_agent_architecture_faz145 import (
    FastMCPStatelessGateway19,
    FastMCPHeaderRouting19,
    FastMCPTransport,
    FastMCPQoSTier,
    TaskState15,
    DelegationMode145,
    SupervisionStrategy145,
    DecoupledTaskContract15,
    ActorMessage145,
    ActorPriority,
    ErlangOTPSupervisionTree9,
    DAGTaskNode19,
    KahnDAGCPMScheduler19,
    ASTPreflightGuard31,
    MerkleCheckpointForest9,
    HypervisorHarness9,
    DeskRole27,
    VirtualDesk27,
    LindaDistributedTupleSpace23,
    AgentDesksManager27,
    AgentCard145,
    AAIFA2AFederationRouter30,
    TriTemporalEdge145,
    TredecimCognitiveMemory43,
    ASTSkeletonizer31,
    ExtremeTokenPhysics37,
    SkillProgressiveDisclosure12,
    Faz145MasterSwarmOrchestrator
)


# ==============================================================================
# 1. FASTMCP 19.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp19_stateless_gateway():
    gateway = FastMCPStatelessGateway19()

    def execute_calc(a: int, b: int):
        return {"result": a + b, "__compensate__": "calc_revert"}

    def query_db(table: str):
        return {"rows": [{"id": 1, "name": "test"}]}

    gateway.register_tool(
        name="calculator",
        func=execute_calc,
        pythonic_signature="(a: int, b: int) -> Dict[str, Any]",
        required_roles={"agent", "operator"},
        schema_props={"a": {"type": "integer"}, "b": {"type": "integer"}}
    )
    gateway.register_tool(
        name="db_query",
        func=query_db,
        pythonic_signature="(table: str) -> Dict[str, Any]",
        required_roles={"admin"},
        schema_props={"table": {"type": "string"}}
    )

    # 1. Zero-shot attenuation signature check
    signatures = gateway.get_zero_shot_signatures()
    assert "def calculator(a: int, b: int) -> Dict[str, Any]: ..." in signatures
    assert "def db_query(table: str) -> Dict[str, Any]: ..." in signatures

    # 2. Successful dispatch
    hdr = FastMCPHeaderRouting19(
        mcp_method="call_tool",
        mcp_name="calculator",
        oauth_token="Bearer valid_jwt_token_for_agent_entropy_core",
        mcp_qos_tier=FastMCPQoSTier.CRITICAL_LATENCY
    )
    res = gateway.dispatch(hdr, {"a": 10, "b": 25}, caller_roles={"agent"})
    assert res.success is True
    assert res.status_code == 200
    assert res.data["result"] == 35
    assert res.etag is not None
    assert len(gateway.saga_stack) == 1

    # 3. ETag 304 volatility cache test
    hdr_cache = FastMCPHeaderRouting19(
        mcp_method="call_tool",
        mcp_name="calculator",
        mcp_stage="cached_verify",
        oauth_token="Bearer valid_jwt_token_for_agent_entropy_core"
    )
    res_cached = gateway.dispatch(hdr_cache, {"a": 10, "b": 25}, caller_roles={"agent"})
    assert res_cached.success is True
    assert res_cached.status_code == 304

    # 4. MRTR 206 input elicitation test
    res_missing = gateway.dispatch(hdr, {"a": 10}, caller_roles={"agent"})
    assert res_missing.status_code == 206
    assert "b" in res_missing.input_schema_prompt

    # 5. Saga Compensation LIFO rollback test
    logs = gateway.execute_saga_rollback()
    assert len(logs) == 1
    assert "calc_revert" in logs[0]
    assert len(gateway.saga_stack) == 0


# ==============================================================================
# 2. DECOUPLED TASK CONTRACT 15.0 & HEARTBEAT LEASE TESTS
# ==============================================================================

def test_decoupled_task_contract15_and_lease():
    task = DecoupledTaskContract15(
        task_id="task_opt_145",
        title="Refactor GraphRAG Engine",
        heartbeat_ttl_seconds=0.1
    )
    assert task.state == TaskState15.UNASSIGNED

    task.state = TaskState15.ACQUIRED
    task.assigned_agent = "agent_coder_01"
    task.renew_lease()

    assert not task.is_lease_expired()
    time.sleep(0.15)
    assert task.is_lease_expired()

    # Zombie recovery transition
    task.state = TaskState15.ZOMBIE_RECOVERED
    assert task.state == TaskState15.ZOMBIE_RECOVERED


# ==============================================================================
# 3. ERLANG-OTP SUPERVISION TREE 9.0 TESTS
# ==============================================================================

def test_erlang_otp_supervision9():
    sup = ErlangOTPSupervisionTree9(
        strategy=SupervisionStrategy145.ONE_FOR_ONE,
        max_restarts=2,
        restart_window_seconds=10.0
    )
    sup.register_worker("worker_arch", "architecture")

    # 1. First failure -> restarted
    ok, msg = sup.record_failure("worker_arch", "Out of memory")
    assert ok is True
    assert "Restarted worker" in msg

    # 2. Second failure -> restarted
    ok, msg = sup.record_failure("worker_arch", "Syntax crash")
    assert ok is True

    # 3. Third failure exceeds limit -> DLQ escalation
    ok, msg = sup.record_failure("worker_arch", "Repeated timeout")
    assert ok is False
    assert "Escalated to Root DLQ" in msg
    assert len(sup.dlq) == 1
    assert sup.dlq[0]["worker_id"] == "worker_arch"


# ==============================================================================
# 4. KAHN DAG WAVEFRONT & CPM SLACK BORROWING 19.0 TESTS
# ==============================================================================

def test_kahn_dag_cpm_scheduler19():
    scheduler = KahnDAGCPMScheduler19()

    # Task A: 1, 2, 3 days
    scheduler.add_node(DAGTaskNode19("task_A", 1.0, 2.0, 3.0))
    # Task B: 2, 4, 6 days (depends on A)
    scheduler.add_node(DAGTaskNode19("task_B", 2.0, 4.0, 6.0, dependencies={"task_A"}))
    # Task C: 1, 1, 1 day (depends on A)
    scheduler.add_node(DAGTaskNode19("task_C", 1.0, 1.0, 1.0, dependencies={"task_A"}))
    # Task D: 1, 2, 3 days (depends on B and C)
    scheduler.add_node(DAGTaskNode19("task_D", 1.0, 2.0, 3.0, dependencies={"task_B", "task_C"}))

    schedule_res = scheduler.compute_cpm_and_schedule()
    assert schedule_res["status"] != "empty"
    topo = schedule_res["topological_order"]
    assert topo.index("task_A") < topo.index("task_B")
    assert topo.index("task_B") < topo.index("task_D")
    assert topo.index("task_C") < topo.index("task_D")

    # Critical path should be A -> B -> D
    assert "task_A" in schedule_res["critical_path"]
    assert "task_B" in schedule_res["critical_path"]
    assert "task_D" in schedule_res["critical_path"]
    assert "task_C" not in schedule_res["critical_path"]

    # Task C has positive slack and gets economic model via Slack Borrowing
    assert scheduler.nodes["task_C"].slack > 0.0
    assert "Flash" in scheduler.nodes["task_C"].assigned_model
    # Task B is on critical path and gets frontier model
    assert scheduler.nodes["task_B"].is_critical is True
    assert "Frontier" in scheduler.nodes["task_B"].assigned_model


# ==============================================================================
# 5. HYPERVISOR AGENT HARNESS 9.0 TESTS
# ==============================================================================

def test_hypervisor_harness9():
    harness = HypervisorHarness9(initial_temp=0.8, cooling_rate=0.5)

    # 1. Malicious import check
    malicious_code = "import os\nos.system('echo dangerous')"
    res = harness.evaluate_candidate_code(malicious_code)
    assert res["success"] is False
    assert any("Prohibited import 'os'" in v for v in res["violations"])

    # 2. Safe code passes preflight and triggers temperature cooling
    safe_code = """
def compute_metrics(values):
    return sum(values) / len(values) if values else 0.0
"""
    res_safe = harness.evaluate_candidate_code(safe_code)
    assert res_safe["success"] is True
    assert res_safe["current_temp"] == 0.4  # 0.8 * 0.5


def test_merkle_checkpoint_forest9():
    forest = MerkleCheckpointForest9()
    files_v1 = {"main.py": "print('hello')", "config.json": "{}"}
    root1 = forest.create_checkpoint(files_v1)
    assert root1 is not None

    files_v2 = {"main.py": "print('modified')", "config.json": "{}"}
    root2 = forest.create_checkpoint(files_v2)
    assert root1 != root2

    restored = forest.rollback(root1)
    assert restored["main.py"] == "print('hello')"


# ==============================================================================
# 6. AGENT DESKS 27.0 & LINDA TUPLE SPACE 23.0 TESTS
# ==============================================================================

def test_linda_distributed_tuple_space23():
    space = LindaDistributedTupleSpace23()
    received = []

    def on_task_ready(tup):
        received.append(tup)

    space.watch({"topic": "task_ready"}, on_task_ready)

    # Publish tuple
    space.out({"topic": "task_ready", "task_id": "T-100", "role": "architecture"})
    assert len(received) == 1
    assert received[0]["task_id"] == "T-100"

    # Read non-destructively
    rd_res = space.rd({"topic": "task_ready"})
    assert rd_res is not None
    assert len(space.tuples) == 1

    # Take destructively
    in_res = space.in_tuple({"topic": "task_ready"})
    assert in_res is not None
    assert len(space.tuples) == 0


def test_agent_desks_manager27_file_locking(tmp_path):
    mgr = AgentDesksManager27(str(tmp_path))

    # Architecture locks 'architecture.md'
    ok1 = mgr.acquire_file_lock(DeskRole27.ARCHITECTURE, "architecture.md")
    assert ok1 is True

    # Engineering tries to acquire lock on the same file -> rejected
    ok2 = mgr.acquire_file_lock(DeskRole27.ENGINEERING, "architecture.md")
    assert ok2 is False

    # Architecture releases lock
    mgr.release_file_lock(DeskRole27.ARCHITECTURE, "architecture.md")

    # Engineering now acquires lock successfully
    ok3 = mgr.acquire_file_lock(DeskRole27.ENGINEERING, "architecture.md")
    assert ok3 is True


# ==============================================================================
# 7. AAIF A2A HORIZONTAL FEDERATION ROUTER 30 TESTS
# ==============================================================================

def test_aaif_a2a_router30():
    router = AAIFA2AFederationRouter30(federation_secret="secret_key_aaif_2026")

    card1 = AgentCard145(
        agent_id="agent_fast_coder",
        name="Fast Coder Specialist",
        supported_skills=["python_codegen"],
        domain_authority_score=0.88,
        reasoning_depth_score=0.75,
        latency_p95_ms=350.0,
        cost_per_1k_tokens_usd=0.002,
        reliability_sla=0.999,
        ed25519_pubkey="pubkey_ed25519_fast"
    )
    card1.sign_card("secret_key_aaif_2026")

    card2 = AgentCard145(
        agent_id="agent_deep_reasoner",
        name="Deep Reasoning Architect",
        supported_skills=["python_codegen", "system_design"],
        domain_authority_score=0.98,
        reasoning_depth_score=0.97,
        latency_p95_ms=1200.0,
        cost_per_1k_tokens_usd=0.015,
        reliability_sla=0.999,
        ed25519_pubkey="pubkey_ed25519_deep"
    )
    card2.sign_card("secret_key_aaif_2026")

    assert router.register_peer_agent(card1) is True
    assert router.register_peer_agent(card2) is True

    # Routing prioritizing reasoning depth within budget
    selected = router.route_request_pareto_optimal("python_codegen", max_latency_ms=1500.0, max_cost_per_1k=0.02)
    assert selected is not None
    assert selected.agent_id == "agent_deep_reasoner"

    # PBFT Consensus verification
    proposals = [
        {"voter": "node1", "decision": "MERGE_BRANCH"},
        {"voter": "node2", "decision": "MERGE_BRANCH"},
        {"voter": "node3", "decision": "MERGE_BRANCH"},
        {"voter": "node4", "decision": "REJECT_BRANCH"}
    ]
    # For f = 1, required quorum = 2f + 1 = 3
    assert router.verify_pbft_consensus(proposals, fault_tolerance_f=1) is True


# ==============================================================================
# 8. TREDECIM-STORE 43-LAYER COGNITIVE MEMORY TESTS
# ==============================================================================

def test_tredecim_cognitive_memory43():
    mem = TredecimCognitiveMemory43()

    # 1. Tri-temporal edge
    edge = TriTemporalEdge145(
        source_entity="EntropyAI",
        relation="uses_protocol",
        target_entity="FastMCP19",
        valid_time_start=1000.0,
        valid_time_end=2000.0,
        ingestion_time=1100.0,
        transaction_time=1105.0
    )
    mem.add_tri_temporal_edge(edge)

    # Time travel query
    valid_facts = mem.query_time_travel("EntropyAI", 1500.0)
    assert len(valid_facts) == 1
    assert valid_facts[0].target_entity == "FastMCP19"

    invalid_facts = mem.query_time_travel("EntropyAI", 2500.0)
    assert len(invalid_facts) == 0

    # 2. HippoRAG 2 Personalized PageRank
    mem.add_tri_temporal_edge(TriTemporalEdge145(
        source_entity="FastMCP19",
        relation="enables",
        target_entity="ZeroShotAttenuation",
        valid_time_start=0,
        valid_time_end=3000,
        ingestion_time=0,
        transaction_time=0
    ))
    ppr_ranks = mem.personalized_pagerank_hipporag(["EntropyAI"])
    assert "EntropyAI" in ppr_ranks
    assert "FastMCP19" in ppr_ranks
    assert ppr_ranks["FastMCP19"] > 0.0

    # 3. Ebbinghaus retention decay
    ret = mem.calculate_ebbinghaus_retention(initial_importance=1.0, elapsed_hours=24.0, repetitions=2)
    assert 0.0 < ret < 1.0


# ==============================================================================
# 9. EXTREME TOKEN PHYSICS 37.0 & PROGRESSIVE SKILL DISCLOSURE TESTS
# ==============================================================================

def test_ast_skeletonizer31():
    code = '''
def calculate_complex_metric(x: int, y: int) -> float:
    """Computes the primary metric score."""
    temp = x * y
    result = temp / (x + y + 1e-5)
    return result
'''
    pruned = ASTSkeletonizer31.skeletonize(code)
    assert "Computes the primary metric score." in pruned
    assert "pass" in pruned
    assert "temp = x * y" not in pruned


def test_extreme_token_physics37_and_skills():
    # Radix KV-Cache block alignment
    aligned_64 = ExtremeTokenPhysics37.align_radix_block(130, block_size=64)
    assert aligned_64 == 192  # 64 * 3

    # Marginal Delta Token Accounting
    delta = ExtremeTokenPhysics37.compute_marginal_delta(current_cumulative=1540, previous_cumulative=1200)
    assert delta == 340

    # Progressive Skill Disclosure 12.0
    skill = SkillProgressiveDisclosure12(
        skill_name="code_analysis",
        description="Analyzes code for vulnerabilities",
        instructions_md="Run AST scanner and report findings.",
        script_path="scripts/run_analysis.py"
    )
    l1 = skill.get_level1_discovery()
    assert "- name: code_analysis" in l1
    l2 = skill.get_level2_activation()
    assert "# Skill: code_analysis" in l2
    l3 = skill.get_level3_execution_target()
    assert l3 == "scripts/run_analysis.py"


# ==============================================================================
# 10. FAZ 145 MASTER SWARM ORCHESTRATOR END-TO-END TEST
# ==============================================================================

def test_faz145_master_swarm_orchestrator(tmp_path):
    orchestrator = Faz145MasterSwarmOrchestrator(str(tmp_path))
    diagnostic = orchestrator.bootstrap_master_pipeline()

    assert diagnostic["status"] == "ready"
    assert "Faz 145" in diagnostic["phase"]
    assert "19.0" in diagnostic["fastmcp_version"]
    assert "43-Layer" in diagnostic["cognitive_memory"]
    assert "Erlang-OTP 9.0" in diagnostic["supervision_tree"]
