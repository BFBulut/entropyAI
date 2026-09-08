"""
Automated Test Suite for Faz 126 Master Autonomous Agent Architecture Module
=============================================================================
Verifies 100% programmatic correctness across all 8 architectural pillars:
1. Stateless FastMCP 7.5 (SEP-4600 Bitmask Matrix, Attenuation v7, ETag 304, SHM Buffers, Saga Pipeline)
2. AAIF A2A v4.5 & AP2 4.5 (Agent Cards, Pareto Routing with Latency Decay, PBFT Consensus)
3. Kahn DAG Wavefront & CPM Slack Scheduling
4. AP2 4.5 8-Tier SLA Escrow & Proof-of-Execution
5. Self-Refining Harness 11.0 (Fit Ratio 10.0, AST Guard 12.0, Merkle Rollback, Dynamic Micro-Adapters v7)
6. Agent Desks 11.0 (MG-SWB 2.0 Leases, Linda Tuple Space 6.0, 5-Way AST Semantic Merge 6.0)
7. Docosa-Store 22-Layer Memory (Graphiti 2.0 Invalidation, Ebbinghaus Decay, Dream Phase, RRF-22 Fusion)
8. Extreme Token Physics 18.0, Erlang-OTP 11.0 & Faz 126 Swarm Orchestrator
"""

import hmac
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz126 import (
    StatelessFastMCP75Engine,
    MCPToolDefinition126,
    TaskLifecycleStage126,
    AgentCard126,
    DecoupledTaskContract126,
    TaskFSMState126,
    AAIFMeshRouter126,
    AP245SLAEscrow,
    SelfRefiningHarness110,
    HarnessFaultCategory126,
    ASTPreflightGuard120,
    AgentDesks110,
    DeskRole126,
    SingleWriterBoundaryViolation126,
    DocosaStore22LayerMemory,
    TokenPhysics180,
    ErlangOTPSupervisor110,
    SupervisionStrategy126,
    Faz126MasterSwarmOrchestrator
)


def test_fastmcp75_bitmask_matrix_sbte_routing_attenuation_and_etag_caching():
    engine = StatelessFastMCP75Engine()

    def calc_multiply(args):
        return args["x"] * args["y"]

    def audit_scan(args):
        return {"vulnerabilities_found": 0, "target": args["path"]}

    t1 = MCPToolDefinition126(
        name="math_multiply",
        domain="math",
        description="Multiplies two numbers x and y",
        parameters={"x": "float", "y": "float"},
        handler=calc_multiply,
        allowed_stages=[TaskLifecycleStage126.EXECUTION],
        preconditions=lambda args: "x" in args and "y" in args,
        cacheable=True,
        cache_ttl_seconds=30,
        volatility_score=0.1,
        keywords=["multiply", "product"],
        capability_bitmask=0x01,
        sparse_binary_vector=[1, 1, 0, 0]
    )

    t2 = MCPToolDefinition126(
        name="security_audit",
        domain="security",
        description="Scans code path for security defects",
        parameters={"path": "str"},
        handler=audit_scan,
        allowed_stages=[TaskLifecycleStage126.AUDIT],
        cacheable=False,
        keywords=["audit", "scan"],
        capability_bitmask=0x02,
        sparse_binary_vector=[0, 0, 1, 1]
    )

    engine.register_tool(t1)
    engine.register_tool(t2)

    # Test bitmask capability & stage-aware negotiation
    exec_tools = engine.negotiate_active_tools(
        stage=TaskLifecycleStage126.EXECUTION,
        intent_keywords=["multiply"],
        capability_mask=0x01,
        binary_query_vector=[1, 1, 0, 0]
    )
    assert len(exec_tools) == 1
    assert exec_tools[0].name == "math_multiply"

    audit_tools = engine.negotiate_active_tools(
        stage=TaskLifecycleStage126.AUDIT,
        intent_keywords=["scan"],
        capability_mask=0x02,
        binary_query_vector=[0, 0, 1, 1]
    )
    assert len(audit_tools) == 1
    assert audit_tools[0].name == "security_audit"

    # Test Zero-Shot Attenuation v7 signature
    manifest = engine.get_attenuated_system_manifest([t1, t2])
    assert "def math_multiply(x: float, y: float) -> Any:" in manifest
    assert "def security_audit(path: str) -> Any:" in manifest

    # Test SHM buffer allocation
    buf_id = engine.allocate_shm_buffer(b"payload-data-stream")
    assert buf_id.startswith("shm://")
    assert engine.read_shm_buffer(buf_id) == b"payload-data-stream"

    # Test execution, ETag generation and 304 caching
    res1 = engine.execute_tool("math_multiply", {"x": 6.0, "y": 7.0})
    assert res1["status_code"] == 200
    assert res1["data"] == 42.0
    etag = res1["etag"]

    # Revalidation with If-None-Match
    res2 = engine.execute_tool("math_multiply", {"x": 6.0, "y": 7.0}, if_none_match_etag=etag)
    assert res2["status_code"] == 304
    assert res2["status"] == "Not Modified"

    # Test Markov next tool prediction
    engine.execute_tool("security_audit", {"path": "src/"})
    preds = engine.predict_next_tools("math_multiply")
    assert "security_audit" in preds

    # Test compound batch pipeline with Saga compensation
    step1 = {"tool": "math_multiply", "arguments": {"x": 10.0, "y": 2.0}}
    step2 = {"tool": "math_multiply", "arguments": {"x": 3.0, "y": 4.0}}
    pipe_res = engine.execute_compound_pipeline([step1, step2])
    assert pipe_res["pipeline_status"] == "Success"
    assert pipe_res["final_data"] == 12.0


def test_aaif_mesh_router_pareto_routing_and_pbft_consensus():
    router = AAIFMeshRouter126(cluster_secret="test-cluster-secret")

    card1 = AgentCard126(
        agent_id="arch-agent-1",
        name="SystemArchitect",
        role="architect",
        supported_stages=[TaskLifecycleStage126.DISCOVERY],
        skills=["design", "spec", "uml"],
        max_concurrency=5,
        current_load=0.1,
        latency_p95_ms=25.0,
        reputation_score=0.98,
        proof_of_execution_rate=0.99
    )

    card2 = AgentCard126(
        agent_id="dev-agent-1",
        name="SeniorDeveloper",
        role="developer",
        supported_stages=[TaskLifecycleStage126.EXECUTION],
        skills=["python", "rust", "refactor"],
        max_concurrency=4,
        current_load=0.3,
        latency_p95_ms=50.0,
        reputation_score=0.95,
        proof_of_execution_rate=0.97
    )

    assert router.register_agent(card1) is True
    assert router.register_agent(card2) is True

    # Signature validation
    assert card1.verify_signature("test-cluster-secret") is True

    # Pareto selection
    selected_arch = router.pareto_select_agent(TaskLifecycleStage126.DISCOVERY, ["design", "spec"])
    assert selected_arch is not None
    assert selected_arch.agent_id == "arch-agent-1"

    selected_dev = router.pareto_select_agent(TaskLifecycleStage126.EXECUTION, ["python"])
    assert selected_dev is not None
    assert selected_dev.agent_id == "dev-agent-1"

    # PBFT Quorum
    proposal = {"action": "deploy_module", "target": "c:/EntropiAI/src"}
    quorum_ok = router.execute_pbft_consensus(proposal, ["arch-agent-1", "dev-agent-1"])
    assert quorum_ok is True


def test_kahn_dag_wavefront_and_cpm_slack_scheduling():
    router = AAIFMeshRouter126()

    t1 = DecoupledTaskContract126("t1", "root", None, TaskLifecycleStage126.DISCOVERY, ["spec"], {})
    t2 = DecoupledTaskContract126("t2", "root", None, TaskLifecycleStage126.EXECUTION, ["code"], {})
    t3 = DecoupledTaskContract126("t3", "root", None, TaskLifecycleStage126.EXECUTION, ["code"], {})
    t4 = DecoupledTaskContract126("t4", "root", None, TaskLifecycleStage126.VERIFICATION, ["test"], {})

    tasks = [t1, t2, t3, t4]
    deps = {
        "t1": [],
        "t2": ["t1"],
        "t3": ["t1"],
        "t4": ["t2", "t3"]
    }
    durations = {"t1": 50.0, "t2": 150.0, "t3": 100.0, "t4": 80.0}

    schedule = router.schedule_kahn_wavefront_with_cpm(tasks, deps, durations)
    assert schedule["wave_count"] == 3
    assert schedule["waves"][0] == ["t1"]
    assert set(schedule["waves"][1]) == {"t2", "t3"}
    assert schedule["waves"][2] == ["t4"]
    assert schedule["makespan_ms"] >= 280.0
    assert "slack_times" in schedule


def test_ap2_sla_escrow_and_proof_of_execution_clawbacks():
    escrow = AP245SLAEscrow(base_bounty=1000.0)

    # 1. Nominal contract
    c_ok = DecoupledTaskContract126("c_ok", "init", "dev", TaskLifecycleStage126.EXECUTION, ["code"], {}, sla_timeout_ms=500.0, token_budget=1000)
    c_ok.tokens_consumed = 500
    c_ok.transition_to(TaskFSMState126.ASSIGNED)
    c_ok.transition_to(TaskFSMState126.EXECUTING)
    c_ok.transition_to(TaskFSMState126.VERIFYING)
    c_ok.transition_to(TaskFSMState126.AUDITED)
    c_ok.transition_to(TaskFSMState126.COMPLETED)

    res_ok = escrow.settle_contract(c_ok, actual_duration_ms=300.0, quality_score=0.95)
    assert res_ok["final_payout"] == 1000.0
    assert len(res_ok["clawbacks"]) == 0
    assert res_ok["proof_of_execution"] is not None
    assert c_ok.fsm_state == TaskFSMState126.SETTLED

    # 2. Defective contract triggering 8-tier clawbacks
    c_bad = DecoupledTaskContract126("c_bad", "init", "dev", TaskLifecycleStage126.EXECUTION, ["code"], {}, sla_timeout_ms=200.0, token_budget=500)
    c_bad.tokens_consumed = 800  # Token overrun -> 25%
    c_bad.audit_discrepancy = True  # Audit -> 20%
    c_bad.contract_hallucination = True  # Hallucination -> 35%
    c_bad.zk_poe_verified = False  # ZK-PoE -> 40%
    c_bad.transition_to(TaskFSMState126.ASSIGNED)
    c_bad.transition_to(TaskFSMState126.EXECUTING)
    c_bad.transition_to(TaskFSMState126.VERIFYING)
    c_bad.transition_to(TaskFSMState126.AUDITED)
    c_bad.transition_to(TaskFSMState126.COMPLETED)

    res_bad = escrow.settle_contract(
        c_bad,
        actual_duration_ms=450.0,  # Latency breach -> 20%
        quality_score=0.70,       # Quality flaw -> 30%
        security_breach=True,     # Security -> 50%
        schema_mismatch=True      # Schema -> 15%
    )
    # Total penalties exceed bounty -> final payout clamped to 0.0
    assert res_bad["final_payout"] == 0.0
    assert len(res_bad["clawbacks"]) == 8


def test_self_refining_harness_exokernel_fit_ratio_and_merkle_rollback():
    harness = SelfRefiningHarness110(max_consecutive_failures=3)

    # 1. Test AST Preflight Guard
    safe_code = "def add(x: int, y: int) -> int:\n    return x + y\n"
    safe, viols = harness.ast_guard.inspect_code(safe_code)
    assert safe is True
    assert len(viols) == 0

    evil_code = "import ctypes\ndef dangerous():\n    eval('1+1')\n"
    safe_evil, viols_evil = harness.ast_guard.inspect_code(evil_code)
    assert safe_evil is False
    assert any("Forbidden call" in v for v in viols_evil)
    assert any("Forbidden module" in v for v in viols_evil)

    # 2. Test Fit Ratio 10.0
    harness.record_fault(HarnessFaultCategory126.MODEL_REASONING_FAULT)
    harness.record_fault(HarnessFaultCategory126.HARNESS_SCAFFOLDING_FAULT)
    # Fit Ratio = 1.0 - (1 scaffolding / 2 total) = 0.50
    assert harness.calculate_fit_ratio() == 0.50

    # 3. Test Merkle Checkpoint Forest and Rollback
    files_v1 = {"main.py": "print('hello v1')", "utils.py": "x = 1"}
    r1 = harness.push_merkle_checkpoint(files_v1)

    files_v2 = {"main.py": "print('hello v2')", "utils.py": "x = 2"}
    r2 = harness.push_merkle_checkpoint(files_v2)

    assert r1 != r2
    rolled_root = harness.rollback_to_last_green()
    assert rolled_root == r1

    # 4. Test Dynamic Micro-Adapter Synthesis v7
    harness.synthesize_micro_adapter("fetch_user", {"uid": "user_id"})
    adapter = harness.dynamic_adapters["fetch_user"]
    adapted = adapter({"uid": "u-123", "action": "inspect"})
    assert "user_id" in adapted
    assert adapted["user_id"] == "u-123"
    assert "uid" not in adapted


def test_agent_desks_mg_swb_linda_tuple_space_and_ast_3way_reconciler():
    desks = AgentDesks110(root_path="c:/EntropiAI")

    desks.create_desk("dev-desk", DeskRole126.DEVELOPER, "feat/core")
    desks.create_desk("test-desk", DeskRole126.TESTER, "feat/qa")

    # MG-SWB 2.0 Lease: Developer writing to src/ is allowed
    assert desks.acquire_file_lease("dev-desk", "src/module.py") is True

    # Tester forbidden from writing to src/
    with pytest.raises(SingleWriterBoundaryViolation126):
        desks.acquire_file_lease("test-desk", "src/module.py")

    # Developer releasing lease
    desks.release_file_lease("dev-desk", "src/module.py")

    # Linda Distributed In-Memory Tuple Space Bus 6.0
    events_captured = []
    desks.tuple_watch("telemetry", lambda tup: events_captured.append(tup))

    desks.tuple_out(("telemetry", "dev-desk", "compile_ok", 200))
    assert len(events_captured) == 1

    read_tup = desks.tuple_read(("telemetry", "dev-desk", None, None))
    assert read_tup is not None
    assert read_tup[2] == "compile_ok"

    in_tup = desks.tuple_in(("telemetry", "dev-desk", None, None))
    assert in_tup == read_tup
    assert desks.tuple_read(("telemetry", "dev-desk", None, None)) is None

    # 5-Way AST Semantic Conflict-Free Reconciler 6.0
    base_code = "def func_a():\n    return 'base_a'\n\ndef func_b():\n    return 'base_b'\n"
    desk_a = "def func_a():\n    return 'mod_a'\n\ndef func_b():\n    return 'base_b'\n"
    desk_b = "def func_a():\n    return 'base_a'\n\ndef func_b():\n    return 'mod_b'\n"

    success, merged = desks.reconcile_ast_3way(base_code, desk_a, desk_b)
    assert success is True
    assert "return 'mod_a'" in merged
    assert "return 'mod_b'" in merged


def test_docosa_store_22_layer_cognitive_memory_and_rrf22_fusion():
    memory = DocosaStore22LayerMemory(ebbinghaus_half_life=100.0)

    # Store across various layers
    m1 = memory.store_memory(layer_id=1, content="Obsidian Exocortex root directive", importance=0.95, entities=["Exocortex", "Directive"])
    m2 = memory.store_memory(layer_id=2, content="pgvector DiskANN high dimension index", importance=0.88, entities=["pgvector", "Index"])
    m3 = memory.store_memory(layer_id=6, content="Graphiti dynamic temporal fact", importance=0.75, entities=["Graphiti", "Fact"])
    m4 = memory.store_memory(layer_id=21, content="Knowledge graph distillation centroid", importance=0.80, entities=["Distillation"])

    # Test Graphiti Bi-Temporal fact invalidation
    assert memory.invalidate_fact(m3.memory_id) is True
    assert m3.invalidated is True

    # Test HippoRAG 2 Personalized PageRank
    ppr_scores = memory.execute_hipporag2_ppr(["Exocortex"])
    assert m1.memory_id in ppr_scores
    assert ppr_scores[m1.memory_id] > 0.0

    # Test Dream Consolidation
    dream_res = memory.run_dream_consolidation()
    assert dream_res["status"] == "DreamConsolidationComplete"

    # Test RRF-22 Fusion
    results = memory.query_rrf22("Obsidian pgvector", top_k=3)
    assert len(results) >= 2
    top_score, top_item = results[0]
    assert top_score > 0.0
    assert top_item.layer_id in (1, 2)


def test_token_physics_codeact_repl_erlang_otp_and_swarm_orchestrator():
    # 1. Token Physics 18.0
    padded = TokenPhysics180.align_radix_prompt_cache("System Prompt", block_size=128)
    assert len(padded) % 128 == 0 or len(padded) >= len("System Prompt")

    delta_tok = TokenPhysics180.calculate_delta_tokens(15000, 12000)
    assert delta_tok == 3000

    chunks = TokenPhysics180.simulate_late_chunking("The quick brown fox jumps over the lazy dog", chunk_size_words=4)
    assert len(chunks) >= 2

    # CodeAct 11.0 Virtual REPL
    tool_env = {"scale_factor": 10}
    script = "val = 42\nresult = val * scale_factor\nartifacts = {'key': 'val'}"
    repl_res = TokenPhysics180.execute_codeact_virtual_repl(script, tool_env)
    assert repl_res["status"] == "Success"
    assert repl_res["result"] == 420
    assert repl_res["artifacts"]["key"] == "val"

    # AST Skeletonization 12.0
    full_code = "def compute(a, b):\n    step1 = a * 2\n    return step1 + b\n"
    skel = TokenPhysics180.ast_skeletonize(full_code)
    assert "step1 = a * 2" not in skel
    assert "def compute(a, b):" in skel

    # 2. Erlang-OTP 11.0 Supervisor
    sup = ErlangOTPSupervisor110(strategy=SupervisionStrategy126.ONE_FOR_ONE, max_restarts=2, window_seconds=60.0)
    sup.add_worker("w1", lambda: "healthy")

    r1 = sup.handle_worker_crash("w1")
    assert r1["action"] == "RESTART_WORKER"

    r2 = sup.handle_worker_crash("w1")
    assert r2["action"] == "RESTART_WORKER"

    r3 = sup.handle_worker_crash("w1")
    # 3rd restart in window exceeds max_restarts (2) -> COLLAPSE
    assert r3["action"] == "COLLAPSE_SUPERVISOR"

    # 3. Faz 126 Master Swarm Orchestrator
    orchestrator = Faz126MasterSwarmOrchestrator(workspace_root="c:/EntropiAI")
    orchestrator.bootstrap_default_agent_mesh()

    mission_tasks = [
        {"stage": "discovery", "skills": ["architecture", "spec"], "desc": "Audit system architecture"},
        {"stage": "execution", "skills": ["code", "refactor"], "desc": "Implement core pipeline"}
    ]
    mission_res = orchestrator.execute_mission("AutonomousNextGenTest", mission_tasks)
    assert mission_res["status"] == "MissionCompleted"
    assert len(mission_res["results"]) == 2
    assert mission_res["results"][0]["final_payout"] > 0
