"""
Unit & Integration Test Suite for Faz 143 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 17.0 Stateless Gateway, OAuth 2.1, Horizon RBAC, ETag 304, MRTR 206, Saga Rollback
2. Decoupled Task Contract 13.0 & Actor Message
3. Erlang-OTP Supervision Tree 7.0 (Restarts, Backoff, Escalation)
4. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 17.0
5. Hypervisor Agent Harness 7.0 (AST Preflight Guard 28.0, Speculative MCTS, Merkle Checkpoints, Cooling)
6. Agent Desks 25.0, MG-SWB 14.0 Vector Clocks & Linda Distributed Tuple Space 20.0
7. AAIF Horizontal Federation Router 26, 7D Pareto & PBFT Consensus
8. Quadraginta-Store 40-Layer Cognitive Memory (HippoRAG 2 PPR, Graphiti Tri-Temporal, Ebbinghaus)
9. Extreme Token Physics 34.0 (AST Skeletonizer 28.0, Radix KV-Cache Alignment, Marginal Delta Tokens)
10. Skill Progressive Disclosure Standard 10.0 (Tier 1/2/3)
11. Faz143MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest
from entropy.tools.autonomous_agent_architecture_faz143 import (
    FastMCPStatelessGateway17,
    FastMCPHeaderRouting17,
    FastMCPTransport,
    TaskState13,
    DelegationMode143,
    SupervisionStrategy143,
    DecoupledTaskContract13,
    ActorMessage143,
    ErlangOTPSupervisionTree7,
    DAGTaskNode17,
    KahnDAGCPMScheduler17,
    ASTPreflightGuard28,
    MerkleCheckpointForest7,
    HypervisorHarness7,
    DeskRole25,
    VirtualDesk25,
    LindaDistributedTupleSpace20,
    AgentDesksManager25,
    AgentCard143,
    AAIFA2AFederationRouter26,
    TriTemporalEdge143,
    QuadragintaCognitiveMemory40,
    ASTSkeletonizer28,
    ExtremeTokenPhysics34,
    SkillProgressiveDisclosure10,
    Faz143MasterSwarmOrchestrator
)


# ==============================================================================
# 1. FASTMCP 17.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp17_stateless_gateway():
    gateway = FastMCPStatelessGateway17()

    # Register tools
    def execute_calc(a: int, b: int):
        return {"result": a + b, "__compensate__": "calc_revert"}

    def query_db(table: str):
        if table == "secure" and False:
            pass
        return {"rows": [{"id": 1, "name": "test"}]}

    gateway.register_tool(
        name="calculator",
        func=execute_calc,
        pythonic_signature="(a: int, b: int) -> Dict[str, Any]",
        required_roles={"agent", "operator"}
    )
    gateway.register_tool(
        name="db_query",
        func=query_db,
        pythonic_signature="(table: str) -> Dict[str, Any]",
        required_roles={"admin"}
    )

    # 1. Zero-shot attenuation signature check
    signatures = gateway.get_zero_shot_signatures()
    assert "def calculator(a: int, b: int) -> Dict[str, Any]: ..." in signatures

    # 2. Successful dispatch
    hdr = FastMCPHeaderRouting17(
        mcp_method="call_tool",
        mcp_name="calculator",
        oauth_token="Bearer valid_jwt_token_for_agent_entropy_core"
    )
    res = gateway.dispatch(hdr, {"a": 10, "b": 25}, caller_roles={"agent"})
    assert res.success is True
    assert res.status_code == 200
    assert res.data["result"] == 35
    assert res.etag is not None
    assert len(gateway.saga_stack) == 1

    # 3. ETag 304 volatility cache test
    res_cached = gateway.dispatch(hdr, {"a": 10, "b": 25}, caller_roles={"agent"})
    assert res_cached.success is True
    assert res_cached.status_code == 304
    assert res_cached.cached is True

    # 4. Horizon RBAC test: db_query requires 'admin'
    hdr_db = FastMCPHeaderRouting17(
        mcp_method="call_tool",
        mcp_name="db_query",
        oauth_token="Bearer valid_jwt_token_for_agent_entropy_core"
    )
    res_forbidden = gateway.dispatch(hdr_db, {"table": "users"}, caller_roles={"agent"})
    assert res_forbidden.success is False
    assert res_forbidden.status_code == 403

    # 5. MRTR 206 input_required elicitation test (missing argument)
    res_elicitation = gateway.dispatch(hdr, {"a": 10}, caller_roles={"agent"})
    assert res_elicitation.status_code == 206
    assert res_elicitation.input_required_schema is not None

    # 6. Two-phase Saga LIFO rollback
    rolled_back = gateway.rollback_saga()
    assert len(rolled_back) == 1
    assert "calc_revert" in rolled_back[0]
    assert len(gateway.saga_stack) == 0

    # 7. Reactive Resource subscription
    events = []
    gateway.subscribe_resource("repo://events", lambda uri, payload: events.append(payload))
    pub_count = gateway.publish_resource_change("repo://events", {"event": "commit_pushed"})
    assert pub_count == 1
    assert len(events) == 1


# ==============================================================================
# 2. DECOUPLED TASK CONTRACT & ACTOR MODEL TESTS
# ==============================================================================

def test_decoupled_task_contract_and_actor():
    task = DecoupledTaskContract13(
        task_id="TASK-2026-001",
        description="Synthesize AST Guardrails",
        optimistic_cost_o=2.0,
        most_likely_cost_m=5.0,
        pessimistic_cost_p=8.0
    )

    # PERT verification: Te = (2 + 4*5 + 8) / 6 = 30 / 6 = 5.0
    assert task.pert_expected_duration == 5.0
    # Var = ((8 - 2) / 6)^2 = 1.0^2 = 1.0
    assert task.pert_variance == 1.0

    # Lease acquisition
    assert task.state == TaskState13.UNASSIGNED
    ok = task.acquire_lease("actor-engineer-1", ttl_sec=10.0)
    assert ok is True
    assert task.state == TaskState13.ACQUIRED
    assert task.assigned_actor_id == "actor-engineer-1"

    # Heartbeat renewal
    task.state = TaskState13.IN_PROGRESS
    renewed = task.renew_lease("actor-engineer-1", ttl_sec=20.0)
    assert renewed is True

    # Reject acquisition by other actor while lease is active
    ok2 = task.acquire_lease("actor-rogue-2", ttl_sec=5.0)
    assert ok2 is False


# ==============================================================================
# 3. ERLANG-OTP SUPERVISION TREE TESTS
# ==============================================================================

def test_erlang_otp_supervision_tree():
    tree = ErlangOTPSupervisionTree7(
        strategy=SupervisionStrategy143.REST_FOR_ONE,
        max_restarts=3,
        max_time_window_sec=10.0
    )
    tree.register_child("actor-A")
    tree.register_child("actor-B")
    tree.register_child("actor-C")

    # REST_FOR_ONE failure of actor-B: restarts B and C, leaves A alone
    restarts = tree.report_failure("actor-B")
    assert "actor-B" in restarts
    assert "actor-C" in restarts
    assert "actor-A" not in restarts

    # Test escalation on exceeding max restarts
    tree.report_failure("actor-B")
    tree.report_failure("actor-B")
    escalated = tree.report_failure("actor-B")
    assert any("ESCALATE_CRASH" in msg for msg in escalated)


# ==============================================================================
# 4. KAHN DAG WAVEFRONT & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_cpm_slack_borrowing():
    scheduler = KahnDAGCPMScheduler17()

    # Setup 4-task diamond DAG:
    # A (cost 2) -> B (cost 6) -> D (cost 2)
    # A (cost 2) -> C (cost 1) -> D (cost 2)
    # Path A-B-D duration = 2 + 6 + 2 = 10.0 (Critical Path, Slack = 0)
    # Path A-C-D duration = 2 + 1 + 2 = 5.0 (C has Slack = 5.0)
    tA = DecoupledTaskContract13("task-A", "Init", optimistic_cost_o=2, most_likely_cost_m=2, pessimistic_cost_p=2)
    tB = DecoupledTaskContract13("task-B", "Heavy Core", dependencies=["task-A"], optimistic_cost_o=6, most_likely_cost_m=6, pessimistic_cost_p=6)
    tC = DecoupledTaskContract13("task-C", "Light Docs", dependencies=["task-A"], optimistic_cost_o=1, most_likely_cost_m=1, pessimistic_cost_p=1)
    tD = DecoupledTaskContract13("task-D", "Final Deploy", dependencies=["task-B", "task-C"], optimistic_cost_o=2, most_likely_cost_m=2, pessimistic_cost_p=2)

    for t in [tA, tB, tC, tD]:
        scheduler.add_task(t)

    schedule = scheduler.compute_schedule()
    assert schedule["total_duration"] == 10.0
    assert "task-A" in schedule["critical_path"]
    assert "task-B" in schedule["critical_path"]
    assert "task-D" in schedule["critical_path"]
    assert "task-C" not in schedule["critical_path"]

    # Check Slack & Slack Borrowing model allocation
    node_c = schedule["nodes"]["task-C"]
    assert node_c["slack"] == 5.0
    assert "Gemini 3.8 Flash" in node_c["model"]

    node_b = schedule["nodes"]["task-B"]
    assert node_b["slack"] == 0.0
    assert "Claude 3.7 Sonnet (Thinking)" in node_b["model"]


# ==============================================================================
# 5. HYPERVISOR HARNESS & AST PREFLIGHT GUARD TESTS
# ==============================================================================

def test_hypervisor_harness_guardrails_and_mcts():
    harness = HypervisorHarness7(initial_temp=0.8)

    # 1. Temperature Cooling Test: T = 0.8 * 0.40^attempt
    t0 = harness.get_cooled_temperature(0)
    t1 = harness.get_cooled_temperature(1)
    t2 = harness.get_cooled_temperature(2)
    assert t0 == 0.8
    assert t1 == pytest.approx(0.32, rel=1e-2)
    assert t2 == pytest.approx(0.128, rel=1e-2)

    # 2. AST Preflight Guard 28.0 Security Checks
    safe_code = """
import json
def process(data):
    return json.dumps(data)
"""
    is_safe, violations = harness.guard.inspect(safe_code)
    assert is_safe is True
    assert len(violations) == 0

    dangerous_code = """
import ctypes
def exploit():
    eval("print('hacked')")
    subprocess.Popen(["cmd.exe"])
"""
    is_dangerous, v_list = harness.guard.inspect(dangerous_code)
    assert is_dangerous is False
    assert any("ctypes" in v for v in v_list)
    assert any("eval" in v for v in v_list)

    # 3. Speculative MCTS Branch Evaluation
    c1 = "import ctypes; x = 1"
    c2 = "def add(x): return x + 1"
    c3 = "def add(x): return x + 2"

    eval_result = harness.evaluate_speculative_candidates(
        candidates=[c1, c2, c3],
        test_fn=lambda code: "x + 1" in code
    )
    best = eval_result["best_candidate"]
    assert best is not None
    assert best["code"] == c2
    assert best["passed_test"] is True
    assert best["passed_ast"] is True

    # 4. Merkle Forest Checkpoint & Rollback
    file_map_v1 = {"main.py": "print('hello v1')", "utils.py": "def f(): return 1"}
    root_h1 = harness.merkle_forest.create_checkpoint("chk-1", file_map_v1)
    assert len(root_h1) == 64

    file_map_v2 = {"main.py": "print('corrupted v2')", "utils.py": "def f(): return 2"}
    harness.merkle_forest.create_checkpoint("chk-2", file_map_v2)

    rolled_back = harness.merkle_forest.rollback_to("chk-1")
    assert rolled_back is not None
    assert rolled_back["main.py"] == "print('hello v1')"


# ==============================================================================
# 6. AGENT DESKS 25.0 & LINDA DISTRIBUTED TUPLE SPACE 20.0 TESTS
# ==============================================================================

def test_agent_desks_and_linda_tuple_space():
    mgr = AgentDesksManager25()
    arch_desk = mgr.create_desk("desk-arch", DeskRole25.ARCHITECTURE, "worktrees/arch")
    eng_desk = mgr.create_desk("desk-eng", DeskRole25.ENGINEERING, "worktrees/eng")

    # 1. MG-SWB 14.0 Write Lease & Vector Clock
    assert arch_desk.vector_clock["desk-arch"] == 0
    ok = mgr.acquire_file_write_lease("desk-arch", "src/models.py", ttl_sec=20.0)
    assert ok is True
    assert arch_desk.vector_clock["desk-arch"] == 1
    assert "src/models.py" in arch_desk.active_leases

    # Contention check: eng_desk cannot write while lease is held
    ok2 = mgr.acquire_file_write_lease("desk-eng", "src/models.py", ttl_sec=20.0)
    assert ok2 is False

    mgr.release_file_write_lease("desk-arch", "src/models.py")
    ok3 = mgr.acquire_file_write_lease("desk-eng", "src/models.py", ttl_sec=20.0)
    assert ok3 is True

    # 2. Linda Distributed Tuple Space 20.0
    ts = mgr.tuple_space
    received_tuples = []
    ts.watch(("task_event", None, ...), lambda t: received_tuples.append(t))

    ts.out(("task_event", "TASK-001", "DONE"))
    ts.out(("config", "max_tokens", 4096))

    assert len(received_tuples) == 1
    assert received_tuples[0][1] == "TASK-001"

    read_val = ts.rd(("config", "max_tokens", None))
    assert read_val is not None
    assert read_val[2] == 4096

    consumed = ts.in_tuple(("config", "max_tokens", None))
    assert consumed is not None
    assert ts.rd(("config", "max_tokens", None)) is None


# ==============================================================================
# 7. AAIF HORIZONTAL FEDERATION ROUTER & PBFT CONSENSUS TESTS
# ==============================================================================

def test_aaif_federation_router_and_pbft():
    router = AAIFA2AFederationRouter26()

    card_fast = AgentCard143(
        agent_id="agent-flash",
        name="Gemini 3.8 Flash Worker",
        endpoint="https://a2a.entropy.ai/flash",
        accuracy_score=0.88,
        latency_p95_ms=120.0,
        cost_per_1k_tokens=0.0005,
        reliability_score=0.95,
        test_time_compute_tier=2,
        domain_authority_score=0.80,
        carbon_efficiency_score=0.98
    )

    card_deep = AgentCard143(
        agent_id="agent-sonnet",
        name="Claude 3.7 Sonnet Thinking",
        endpoint="https://a2a.entropy.ai/sonnet",
        accuracy_score=0.98,
        latency_p95_ms=650.0,
        cost_per_1k_tokens=0.015,
        reliability_score=0.99,
        test_time_compute_tier=5,
        domain_authority_score=0.98,
        carbon_efficiency_score=0.85
    )

    router.register_peer(card_fast)
    router.register_peer(card_deep)

    # 7D Pareto routing test with high accuracy threshold
    best = router.route_task("financial_quant", min_accuracy=0.95)
    assert best is not None
    assert best.agent_id == "agent-sonnet"

    # 3-Phase PBFT Consensus: 4 nodes, f = (4 - 1)//3 = 1 -> quorum = 2f + 1 = 3
    votes_success = [
        {"phase": "commit", "vote": True},
        {"phase": "commit", "vote": True},
        {"phase": "commit", "vote": True},
        {"phase": "commit", "vote": False}
    ]
    assert router.verify_pbft_consensus(votes_success, total_nodes=4) is True

    votes_fail = [
        {"phase": "commit", "vote": True},
        {"phase": "commit", "vote": False},
        {"phase": "commit", "vote": False},
        {"phase": "commit", "vote": False}
    ]
    assert router.verify_pbft_consensus(votes_fail, total_nodes=4) is False


# ==============================================================================
# 8. QUADRAGINTA-STORE COGNITIVE MEMORY & HIPPORAG 2 TESTS
# ==============================================================================

def test_quadraginta_cognitive_memory_and_hipporag2():
    mem = QuadragintaCognitiveMemory40()

    # 1. Graphiti Tri-temporal facts
    mem.add_tri_temporal_fact("FastMCP", "implements", "StatelessCore", valid_start=1700000000.0)
    mem.add_tri_temporal_fact("StatelessCore", "enables", "ZeroLocking", valid_start=1700000000.0)

    # 2. HippoRAG 2 Passages and Phrases
    mem.add_passage("doc_1", "FastMCP 17.0 implements Stateless Core protocol.", ["FastMCP", "StatelessCore"])
    mem.add_passage("doc_2", "Stateless Core eliminates session affinity locks.", ["StatelessCore", "ZeroLocking"])

    # Run HippoRAG 2 Personalized PageRank from seed 'FastMCP'
    ppr_ranks = mem.hipporag2_personalized_pagerank(seed_phrases=["FastMCP"], alpha=0.85, max_iter=10)
    assert "StatelessCore" in ppr_ranks
    assert ppr_ranks["FastMCP"] > 0.0
    assert ppr_ranks["StatelessCore"] > 0.0

    # 3. Ebbinghaus retention decay calculation
    # R = exp(-t / (Imp * HalfLife * (1 + 0.2*AccessCount)))
    # For t = 0, R must be 1.0
    r0 = mem.calculate_ebbinghaus_retention(importance=1.0, half_life_days=10.0, access_count=0, elapsed_days=0.0)
    assert r0 == 1.0

    # For elapsed_days = stability, R = exp(-1) = 0.3679
    r_half = mem.calculate_ebbinghaus_retention(importance=1.0, half_life_days=10.0, access_count=0, elapsed_days=10.0)
    assert r_half == pytest.approx(0.3679, rel=1e-2)

    # 4. Obsidian wikilink dossier generation
    dossier = mem.generate_obsidian_wikilink_dossier("Ajan Mimarisi", ["FastMCP", "Graphiti", "HippoRAG"])
    assert "- [[FastMCP]]" in dossier
    assert "- [[HippoRAG]]" in dossier


# ==============================================================================
# 9. EXTREME TOKEN PHYSICS & AST SKELETONIZER TESTS
# ==============================================================================

def test_extreme_token_physics_and_skeletonizer():
    # 1. AST Skeletonizer 28.0: Strips function body while preserving signature and docstring
    complex_code = """
class DataPipeline:
    def execute(self, payload: dict) -> bool:
        '''Execute the primary pipeline.'''
        step1 = payload.get("x", 1) * 2
        step2 = step1 + 42
        return step2 > 50
"""
    skeleton = ASTSkeletonizer28.skeletonize(complex_code)
    assert "class DataPipeline:" in skeleton
    assert "def execute(self, payload: dict) -> bool:" in skeleton
    assert "'''Execute the primary pipeline.'''" in skeleton or '"""Execute the primary pipeline."""' in skeleton
    assert "step1" not in skeleton
    assert "pass" in skeleton

    # 2. Radix KV-Cache block alignment
    text = "System Prompt Instruction for Agent"
    padded, total_tokens = ExtremeTokenPhysics34.align_to_radix_kv_boundary(text, block_size=16)
    assert total_tokens % 16 == 0
    assert "System Prompt Instruction" in padded

    # 3. Marginal Delta Token Accounting
    prev_telemetry = {"input": 15000, "output": 2500}
    curr_telemetry = {"input": 16200, "output": 2950}
    delta = ExtremeTokenPhysics34.compute_marginal_delta_tokens(curr_telemetry, prev_telemetry)
    assert delta["turn_input_tokens"] == 1200
    assert delta["turn_output_tokens"] == 450
    assert delta["turn_total_tokens"] == 1650


# ==============================================================================
# 10. SKILL PROGRESSIVE DISCLOSURE TESTS
# ==============================================================================

def test_skill_progressive_disclosure():
    skill = SkillProgressiveDisclosure10(
        skill_name="ast_auditor",
        yaml_frontmatter="description: AST Zero-Trust Validator\ntier: 1",
        procedural_md="# Prosedürel Doğrulama Rehberi\n1. Kodu ayrıştır.\n2. Denetle.",
        execution_code="def run_audit(code): return True"
    )

    t1 = skill.get_tier1_discovery()
    assert "skill: ast_auditor" in t1
    assert len(t1) < 150  # Compact Discovery

    t2 = skill.get_tier2_activation()
    assert "Prosedürel Doğrulama Rehberi" in t2

    t3 = skill.get_tier3_execution()
    assert "def run_audit" in t3


# ==============================================================================
# 11. FAZ 143 MASTER ORCHESTRATOR PIPELINE TEST
# ==============================================================================

def test_faz143_master_orchestrator_pipeline():
    orchestrator = Faz143MasterSwarmOrchestrator()
    orchestrator.initialize_standard_environment()

    # FastMCP tools are registered
    assert "file_system_write" in orchestrator.fastmcp.registered_tools
    assert "ast_lint" in orchestrator.fastmcp.registered_tools

    # Run multi-agent pipeline with tasks
    t1 = DecoupledTaskContract13("pipe-t1", "Arch Spec", optimistic_cost_o=1, most_likely_cost_m=2, pessimistic_cost_p=3)
    t2 = DecoupledTaskContract13("pipe-t2", "Code Synth", dependencies=["pipe-t1"], optimistic_cost_o=2, most_likely_cost_m=4, pessimistic_cost_p=6)

    res = orchestrator.run_autonomous_project_pipeline([t1, t2])
    assert res["status"] == "success"
    assert res["phase"] == "143"
    assert res["waves_count"] == 2
    assert res["critical_path"] == ["pipe-t1", "pipe-t2"]
    assert res["total_duration"] == 6.0
