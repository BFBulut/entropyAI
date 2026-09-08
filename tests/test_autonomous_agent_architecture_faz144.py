"""
Unit & Integration Test Suite for Faz 144 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 18.0 Stateless Gateway, OAuth 2.1, Horizon RBAC, ETag 304, MRTR 206, Saga Rollback
2. Decoupled Task Contract 14.0 & Actor Message
3. Erlang-OTP Supervision Tree 8.0 (Restarts, Backoff, Escalation to DLQ)
4. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 18.0
5. Hypervisor Agent Harness 8.0 (AST Preflight Guard 30.0, Speculative MCTS, Merkle Checkpoints, Cooling)
6. Agent Desks 26.0, MG-SWB 15.0 Vector Clocks & Linda Distributed Tuple Space 22.0
7. AAIF Horizontal Federation Router 28, 8D Pareto & PBFT Consensus
8. Duaequadraginta-Store 42-Layer Cognitive Memory (HippoRAG 2 PPR, Graphiti Tri-Temporal, Ebbinghaus)
9. Extreme Token Physics 36.0 (AST Skeletonizer 30.0, Radix KV-Cache Alignment, Marginal Delta Tokens)
10. Skill Progressive Disclosure Standard 11.0 (Tier 1/2/3)
11. Faz144MasterSwarmOrchestrator End-to-End Pipeline
"""

import math
import time
import pytest
from entropy.tools.autonomous_agent_architecture_faz144 import (
    FastMCPStatelessGateway18,
    FastMCPHeaderRouting18,
    FastMCPTransport,
    TaskState14,
    DelegationMode144,
    SupervisionStrategy144,
    DecoupledTaskContract14,
    ActorMessage144,
    ErlangOTPSupervisionTree8,
    DAGTaskNode18,
    KahnDAGCPMScheduler18,
    ASTPreflightGuard30,
    MerkleCheckpointForest8,
    HypervisorHarness8,
    DeskRole26,
    VirtualDesk26,
    LindaDistributedTupleSpace22,
    AgentDesksManager26,
    AgentCard144,
    AAIFA2AFederationRouter28,
    TriTemporalEdge144,
    DuaequadragintaCognitiveMemory42,
    ASTSkeletonizer30,
    ExtremeTokenPhysics36,
    SkillProgressiveDisclosure11,
    Faz144MasterSwarmOrchestrator
)


# ==============================================================================
# 1. FASTMCP 18.0 STATELESS GATEWAY TESTS
# ==============================================================================

def test_fastmcp18_stateless_gateway():
    gateway = FastMCPStatelessGateway18()

    # Register tools
    def execute_calc(a: int, b: int):
        return {"result": a + b, "__compensate__": "calc_revert"}

    def query_db(table: str):
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
    assert "def db_query(table: str) -> Dict[str, Any]: ..." in signatures

    # 2. Successful dispatch
    hdr = FastMCPHeaderRouting18(
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

    # 4. RBAC 403 Forbidden check
    hdr_db = FastMCPHeaderRouting18(
        mcp_method="call_tool",
        mcp_name="db_query",
        oauth_token="Bearer valid_jwt_token_for_agent_entropy_core"
    )
    res_forbidden = gateway.dispatch(hdr_db, {"table": "users"}, caller_roles={"agent"})
    assert res_forbidden.success is False
    assert res_forbidden.status_code == 403

    # 5. Unauthorized 401 check
    hdr_unauth = FastMCPHeaderRouting18(
        mcp_method="call_tool",
        mcp_name="calculator",
        oauth_token="expired"
    )
    res_unauth = gateway.dispatch(hdr_unauth, {"a": 1, "b": 2})
    assert res_unauth.status_code == 401

    # 6. MRTR 206 Interactive Elicitation
    gateway.register_tool(
        name="search_engine",
        func=lambda query, limit: {"results": []},
        pythonic_signature="(query: str, limit: int = 10) -> Dict[str, Any]",
        schema={"required": ["query", "limit"], "properties": {"query": {"type": "string"}}}
    )
    hdr_search = FastMCPHeaderRouting18(
        mcp_method="call_tool",
        mcp_name="search_engine",
        oauth_token="Bearer valid_jwt_token_for_agent_entropy_core"
    )
    res_mrtr = gateway.dispatch(hdr_search, {"query": "entropy"})
    assert res_mrtr.status_code == 206
    assert res_mrtr.input_schema_prompt is not None
    assert "limit" in res_mrtr.input_schema_prompt["missing_parameters"]

    # 7. Saga Rollback test
    rolled_back = gateway.trigger_saga_rollback()
    assert len(rolled_back) == 1
    assert rolled_back[0]["compensate_action"] == "calc_revert"
    assert len(gateway.saga_stack) == 0


# ==============================================================================
# 2. DECOUPLED TASK CONTRACT & ACTOR TESTS
# ==============================================================================

def test_decoupled_task_contract_and_actor():
    contract = DecoupledTaskContract14(
        task_id="task-144-01",
        title="Refactor Memory Engine",
        description="Implement Duaequadraginta cognitive memory",
        lease_duration_sec=2.0
    )

    # 1. Acquire lease
    assert contract.state == TaskState14.UNASSIGNED
    ok = contract.acquire_lease("agent-coder-1")
    assert ok is True
    assert contract.state == TaskState14.ACQUIRED
    assert contract.assigned_agent == "agent-coder-1"

    # 2. Prevent concurrent acquisition while lease active
    ok2 = contract.acquire_lease("agent-coder-2")
    assert ok2 is False

    # 3. Heartbeat extension
    hb = contract.heartbeat("agent-coder-1")
    assert hb is True

    # 4. State transitions
    contract.transition_to(TaskState14.IN_PROGRESS, "agent-coder-1")
    contract.transition_to(TaskState14.PREEMPTED, "supervisor")
    assert contract.state == TaskState14.PREEMPTED
    assert len(contract.state_history) == 3

    # 5. ActorMessage
    msg = ActorMessage144(
        msg_id="msg-01",
        sender="entropy-core",
        recipient="agent-coder-1",
        action="resume_task",
        payload={"task_id": "task-144-01"},
        delegation_mode=DelegationMode144.DIRECT_CLEAN_HANDOFF
    )
    assert msg.priority == 5
    assert msg.delegation_mode == DelegationMode144.DIRECT_CLEAN_HANDOFF


# ==============================================================================
# 3. ERLANG-OTP SUPERVISION TREE TESTS
# ==============================================================================

def test_erlang_otp_supervision_tree():
    tree = ErlangOTPSupervisionTree8(
        strategy=SupervisionStrategy144.ONE_FOR_ONE,
        max_restarts=2,
        window_seconds=10.0
    )

    restart_counter = {"agent-1": 0, "agent-2": 0}

    def restart_agent_1():
        restart_counter["agent-1"] += 1

    def restart_agent_2():
        restart_counter["agent-2"] += 1

    tree.register_child("agent-1", "coder", restart_agent_1)
    tree.register_child("agent-2", "tester", restart_agent_2)

    # 1. Normal crash and restart
    res1 = tree.handle_crash("agent-1", "division by zero")
    assert res1["status"] == "restarted"
    assert restart_counter["agent-1"] == 1
    assert restart_counter["agent-2"] == 0

    # 2. Second restart
    res2 = tree.handle_crash("agent-1", "index error")
    assert res2["status"] == "restarted"
    assert restart_counter["agent-1"] == 2

    # 3. Exceeded max restarts -> DLQ escalation
    res3 = tree.handle_crash("agent-1", "fatal OOM")
    assert res3["status"] == "escalated_to_dlq"
    assert len(tree.dead_letter_queue) == 1
    assert tree.dead_letter_queue[0]["agent_id"] == "agent-1"


# ==============================================================================
# 4. KAHN DAG WAVEFRONT & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_cpm_slack_borrowing():
    scheduler = KahnDAGCPMScheduler18()

    # Define tasks with PERT durations (O, M, P)
    # A (root) -> B, C -> D (sink)
    tA = DAGTaskNode18(task_id="A", pert_o=2, pert_m=3, pert_p=4)  # Te = (2 + 12 + 4)/6 = 3.0
    tB = DAGTaskNode18(task_id="B", dependencies={"A"}, pert_o=4, pert_m=6, pert_p=8)  # Te = (4 + 24 + 8)/6 = 6.0
    tC = DAGTaskNode18(task_id="C", dependencies={"A"}, pert_o=1, pert_m=2, pert_p=3)  # Te = (1 + 8 + 3)/6 = 2.0
    tD = DAGTaskNode18(task_id="D", dependencies={"B", "C"}, pert_o=1, pert_m=1, pert_p=1)  # Te = 1.0

    for node in [tA, tB, tC, tD]:
        scheduler.add_node(node)

    wavefronts = scheduler.compute_wavefronts()
    assert len(wavefronts) == 3
    assert wavefronts[0] == ["A"]
    assert set(wavefronts[1]) == {"B", "C"}
    assert wavefronts[2] == ["D"]

    total_duration, critical_path = scheduler.compute_cpm_and_borrow_slack()

    # Path A -> B -> D: 3.0 + 6.0 + 1.0 = 10.0
    # Path A -> C -> D: 3.0 + 2.0 + 1.0 = 6.0
    assert total_duration == 10.0
    assert critical_path == ["A", "B", "D"]

    # Slack checks: C should have slack = 10.0 - 1.0 - 2.0 - 3.0 = 4.0
    assert scheduler.nodes["C"].slack == 4.0
    assert scheduler.nodes["C"].is_critical_path is False
    assert "FAST_HIGH_THROUGHPUT" in scheduler.nodes["C"].assigned_model_tier

    # Critical path nodes should receive Frontier Reasoning tier
    assert "FRONTIER_REASONING" in scheduler.nodes["B"].assigned_model_tier


# ==============================================================================
# 5. HYPERVISOR HARNESS & AST PREFLIGHT GUARD TESTS
# ==============================================================================

def test_hypervisor_harness_guardrails_and_mcts():
    harness = HypervisorHarness8()

    # 1. Dangerous code detection
    unsafe_code = """
import os
import subprocess

def dangerous_action():
    os.system("rmdir /S /Q C:\\\\")
    eval("__import__('os').system('dir')")
"""
    is_safe, violations = ASTPreflightGuard30.audit_python_code(unsafe_code)
    assert is_safe is False
    assert any("subprocess" in v for v in violations)
    assert any("os.system" in v for v in violations)
    assert any("eval" in v for v in violations)

    # 2. Safe code passes
    safe_code = """
def calculate_metrics(values: list[float]) -> dict:
    total = sum(values)
    avg = total / len(values) if values else 0.0
    return {"total": total, "average": avg}
"""
    is_safe2, violations2 = ASTPreflightGuard30.audit_python_code(safe_code)
    assert is_safe2 is True
    assert len(violations2) == 0

    # 3. Temperature annealing
    t0 = harness.compute_annealed_temperature(0.7, 0)
    t1 = harness.compute_annealed_temperature(0.7, 1)
    t2 = harness.compute_annealed_temperature(0.7, 2)
    assert t0 == 0.7
    assert t1 < t0
    assert t2 < t1

    # 4. Merkle Checkpoint Forest Rollback
    files_v1 = {"main.py": "print('hello v1')", "utils.py": "x = 1"}
    harness.forest.create_checkpoint("cp-01", files_v1)

    restored = harness.forest.rollback_to("cp-01")
    assert restored == files_v1

    # 5. Speculative MCTS UCB-1 evaluation
    branches = [
        {"action": "refactor_a", "confidence": 0.82},
        {"action": "refactor_b", "confidence": 0.94},
        {"action": "refactor_c", "confidence": 0.61}
    ]
    best = harness.evaluate_speculative_branches(branches, lambda b: b["confidence"])
    assert best["action"] == "refactor_b"


# ==============================================================================
# 6. AGENT DESKS & LINDA TUPLE SPACE TESTS
# ==============================================================================

def test_agent_desks_and_linda_tuple_space():
    manager = AgentDesksManager26()

    desk_arch = manager.create_desk("desk-arch", DeskRole26.ARCHITECTURE, "agent-arch", "/repo/worktrees/arch")
    desk_eng = manager.create_desk("desk-eng", DeskRole26.ENGINEERING, "agent-eng", "/repo/worktrees/eng")

    # 1. Single-writer file leasing
    leased1 = manager.acquire_file_write_lease("desk-arch", "docs/architecture.md")
    assert leased1 is True
    assert desk_arch.vector_clock["desk-arch"] == 1

    # Prevent concurrent lease
    leased2 = manager.acquire_file_write_lease("desk-eng", "docs/architecture.md")
    assert leased2 is False

    # Release and reacquire
    manager.release_file_write_lease("desk-arch", "docs/architecture.md")
    leased3 = manager.acquire_file_write_lease("desk-eng", "docs/architecture.md")
    assert leased3 is True

    # 2. Linda Distributed Tuple Space
    space = manager.tuple_space
    space.out(("build_status", "success", 144))
    space.out(("test_coverage", 0.98, 144))

    # Read pattern match
    t = space.rd(("build_status", None, None))
    assert t == ("build_status", "success", 144)

    # In_tuple consumes tuple
    consumed = space.in_tuple(("build_status", None, None))
    assert consumed == ("build_status", "success", 144)
    assert space.rd(("build_status", None, None)) is None

    # Collect and sweep
    space.out(("log", "warn", "msg1"))
    space.out(("log", "error", "msg2"))
    logs = space.collect(("log", None, None))
    assert len(logs) == 2

    cleared = space.sweep("log")
    assert cleared == 2
    assert len(space.collect(("log", None, None))) == 0


# ==============================================================================
# 7. AAIF FEDERATION ROUTER & PBFT CONSENSUS TESTS
# ==============================================================================

def test_aaif_federation_router_and_pbft():
    router = AAIFA2AFederationRouter28(secret_key="secret-144")

    card1 = AgentCard144(
        agent_id="agent-fast",
        name="Fast Analyzer",
        description="Low latency worker",
        skills=["code_analysis", "formatting"],
        accuracy_score=0.91,
        latency_p95_ms=80.0,
        cost_per_mtoken_usd=0.20
    )
    card1.sign("secret-144")

    card2 = AgentCard144(
        agent_id="agent-deep",
        name="Deep Thinker",
        description="High precision analyst",
        skills=["code_analysis", "security_audit"],
        accuracy_score=0.99,
        latency_p95_ms=1200.0,
        cost_per_mtoken_usd=2.50
    )
    card2.sign("secret-144")

    assert router.register_peer_agent(card1) is True
    assert router.register_peer_agent(card2) is True

    # Route based on 8D Pareto
    routed = router.route_by_8d_pareto("formatting")
    assert routed is not None
    assert routed.agent_id == "agent-fast"

    # PBFT Consensus verification (N=4, f=1, Q=3)
    votes_success = [True, True, True, False]
    assert router.verify_pbft_consensus(votes_success, total_nodes=4) is True

    votes_fail = [True, True, False, False]
    assert router.verify_pbft_consensus(votes_fail, total_nodes=4) is False


# ==============================================================================
# 8. DUAEQUADRAGINTA COGNITIVE MEMORY & HIPPORAG 2 TESTS
# ==============================================================================

def test_duaequadraginta_cognitive_memory_and_hipporag2():
    mem = DuaequadragintaCognitiveMemory42()

    # 1. Tri-temporal facts & Time Travel
    t0 = 1000.0
    t1 = 2000.0
    mem.add_tri_temporal_fact("AuthService", "depends_on", "RedisV1", valid_from=t0, valid_until=t1)
    mem.add_tri_temporal_fact("AuthService", "depends_on", "RedisV2", valid_from=t1, valid_until=None)

    past = mem.query_time_travel("AuthService", query_time=1500.0)
    assert len(past) == 1
    assert past[0].target_entity == "RedisV1"

    current = mem.query_time_travel("AuthService", query_time=2500.0)
    assert len(current) == 1
    assert current[0].target_entity == "RedisV2"

    # 2. HippoRAG 2 Personalized PageRank
    mem.entity_graph["A"].add("B")
    mem.entity_graph["B"].add("C")
    mem.entity_graph["C"].add("D")

    ranks = mem.hipporag2_personalized_pagerank(seed_entities=["A"], alpha=0.85, max_iter=15)
    assert len(ranks) >= 4
    assert ranks["A"] > 0.0
    assert ranks["B"] > 0.0

    # 3. Ebbinghaus Forgetting Curve
    r0 = mem.apply_ebbinghaus_forgetting_curve(initial_strength=1.0, elapsed_seconds=0.0)
    r1 = mem.apply_ebbinghaus_forgetting_curve(initial_strength=1.0, elapsed_seconds=86400.0, repetition_count=1)
    r2 = mem.apply_ebbinghaus_forgetting_curve(initial_strength=1.0, elapsed_seconds=86400.0, repetition_count=5)
    assert r0 == 1.0
    assert r1 < r0
    assert r2 > r1  # Higher repetition count increases retention


# ==============================================================================
# 9. EXTREME TOKEN PHYSICS & AST SKELETONIZER TESTS
# ==============================================================================

def test_extreme_token_physics_and_skeletonizer():
    source = """
def heavy_computation(data: list[int]) -> int:
    \"\"\"Docstring to retain.\"\"\"
    x = 0
    for item in data:
        x += item ** 2
    return x
"""
    skeleton = ASTSkeletonizer30.skeletonize(source)
    assert "Docstring to retain." in skeleton
    assert "pass" in skeleton
    assert "x += item ** 2" not in skeleton

    # Radix KV-Cache block alignment
    aligned = ExtremeTokenPhysics36.align_radix_cache_boundary("hello world test prompt", block_size=10)
    assert "#cache_pad" in aligned

    # Marginal Delta Token accounting
    delta = ExtremeTokenPhysics36.compute_marginal_delta_tokens(prev_cumulative=12500, current_cumulative=13400)
    assert delta == 900


# ==============================================================================
# 10. SKILL PROGRESSIVE DISCLOSURE TESTS
# ==============================================================================

def test_skill_progressive_disclosure():
    mgr = SkillProgressiveDisclosure11()
    mgr.register_skill(
        name="web_research",
        desc="Autonomous web crawler",
        tier1_yaml="name: web_research\ndescription: Searches web for fresh facts",
        doc_path="/docs/skills/web_research.md",
        script_path="/scripts/web_crawler.py"
    )

    prompt = mgr.get_discovery_prompt()
    assert "name: web_research" in prompt
    assert len(prompt.split()) < 40  # Lightweight discovery tier


# ==============================================================================
# 11. FAZ 144 MASTER ORCHESTRATOR PIPELINE TEST
# ==============================================================================

def test_faz144_master_orchestrator_pipeline():
    orchestrator = Faz144MasterSwarmOrchestrator()
    orchestrator.bootstrap_default_system()

    res = orchestrator.execute_e2e_swarm_workflow("task-faz144-run", "Verify Faz 144 Core Swarm")
    assert res["task_id"] == "task-faz144-run"
    assert res["acquired"] is True
    assert res["final_state"] == "COMPLETED"
    assert res["fastmcp_status"] == 200
    assert res["fastmcp_data"]["phase"] == 144
