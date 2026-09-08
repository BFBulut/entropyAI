"""
Automated Test Suite for Faz 124 Master Autonomous Agent Architecture Module
=============================================================================
Verifies 100% programmatic correctness across all 8 architectural pillars:
1. Stateless FastMCP 6.5 (SEP-4200 Bitmask Matrix, Stage Masking, Attenuation v5, ETag 304, Pipelines)
2. AAIF A2A v3.5 & AP2 3.5 (Agent Cards, Pareto Routing, Kahn DAG with CPM Slack, PBFT, 6-Tier Escrow)
3. Self-Refining Harness 9.0 (Fit Ratio 8.0, AST Guard 10.0, Micro-Adapters, Merkle Rollback)
4. Agent Desks 9.0 (SWB Leases, Linda Tuple Space, 3-Way AST Semantic Merge 4.0)
5. Icos-Store 20-Layer Memory (Graphiti 2.0 Invalidation, Ebbinghaus Decay, Dream Phase, RRF-20 Fusion)
6. Extreme Token Physics 16.0 (Radix Alignment, CodeAct 9.0 REPL, AST Skeletonization, Delta Tokens)
7. Erlang-OTP 9.0 Supervision Trees (One-for-One, One-for-All, Rest-for-One, Collapse Budget)
8. Faz 124 Master Autonomous Swarm Orchestrator (Full Mission Lifecycle & End-to-End Execution)
"""

import hmac
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz124 import (
    StatelessFastMCP65Engine,
    MCPToolDefinition124,
    TaskLifecycleStage124,
    AgentCard124,
    DecoupledTaskContract124,
    TaskFSMState124,
    AAIFMeshRouter124,
    AP235SLAEscrow,
    SelfRefiningHarness90,
    HarnessFaultCategory124,
    ASTPreflightGuard100,
    AgentDesks90,
    DeskRole124,
    SingleWriterBoundaryViolation124,
    IcosStore20LayerMemory,
    TokenPhysics160,
    ErlangOTPSupervisor90,
    SupervisionStrategy124,
    Faz124MasterSwarmOrchestrator
)


def test_fastmcp65_bitmask_matrix_stage_masking_attenuation_and_etag_caching():
    engine = StatelessFastMCP65Engine()

    def calc_multiply(args):
        return args["x"] * args["y"]

    def audit_scan(args):
        return {"vulnerabilities_found": 0, "target": args["path"]}

    t1 = MCPToolDefinition124(
        name="math_multiply",
        domain="math",
        description="Multiplies two numbers x and y",
        parameters={"x": "float", "y": "float"},
        handler=calc_multiply,
        allowed_stages=[TaskLifecycleStage124.EXECUTION],
        preconditions=lambda args: "x" in args and "y" in args,
        cacheable=True,
        cache_ttl_seconds=30,
        volatility_score=0.1,
        keywords=["multiply", "product"],
        capability_bitmask=0x01
    )

    t2 = MCPToolDefinition124(
        name="security_audit",
        domain="security",
        description="Scans code path for security defects",
        parameters={"path": "str"},
        handler=audit_scan,
        allowed_stages=[TaskLifecycleStage124.AUDIT],
        cacheable=False,
        keywords=["audit", "scan"],
        capability_bitmask=0x02
    )

    engine.register_tool(t1)
    engine.register_tool(t2)

    # Test bitmask capability & stage-aware negotiation
    exec_tools = engine.negotiate_active_tools(
        stage=TaskLifecycleStage124.EXECUTION,
        intent_keywords=["multiply"],
        capability_mask=0x01
    )
    assert len(exec_tools) == 1
    assert exec_tools[0].name == "math_multiply"

    audit_tools = engine.negotiate_active_tools(
        stage=TaskLifecycleStage124.AUDIT,
        intent_keywords=["scan"],
        capability_mask=0x02
    )
    assert len(audit_tools) == 1
    assert audit_tools[0].name == "security_audit"

    # Attenuated signature test
    sig = t1.get_attenuated_signature()
    assert "def math_multiply(x: float, y: float) -> Any:" in sig
    assert "Multiplies two numbers x and y" in sig

    # Execution & ETag 304 Caching test
    code1, res1 = engine.execute_tool("math_multiply", {"x": 6.0, "y": 7.0})
    assert code1 == 200
    assert res1["result"] == 42.0
    etag1 = res1["etag"]

    # Repeat with same arguments and client_etag -> expect 304
    code2, res2 = engine.execute_tool("math_multiply", {"x": 6.0, "y": 7.0}, client_etag=etag1)
    assert code2 == 304
    assert res2["status"] == "not_modified"

    # Reactive Streaming Push
    engine.push_context_diff("FILE_MODIFIED", {"path": "src/core.py", "lines_changed": 12})
    diffs = engine.drain_context_diffs()
    assert len(diffs) == 1
    assert diffs[0]["type"] == "FILE_MODIFIED"

    # Compound Batch Pipeline test
    pipeline_def = [
        {"tool": "math_multiply", "args": {"x": 3.0, "y": 4.0}},
        {"tool": "security_audit", "args": {"path": "src/lib.py"}}
    ]
    pipe_res = engine.execute_compound_pipeline(pipeline_def)
    assert pipe_res["pipeline_status"] == "success"
    assert pipe_res["outputs"]["step_0"] == 12.0


def test_aaif_a2a_v35_pareto_routing_kahn_cpm_pbft_and_6tier_escrow():
    router = AAIFMeshRouter124()

    # Register Agents with HMAC cards
    c1 = AgentCard124(
        agent_id="agent-dev-1",
        name="CodeArchitect",
        role="developer",
        capabilities=["python", "refactor", "fastmcp"],
        max_concurrency=3,
        current_load=1,
        reputation_score=0.98,
        avg_latency_ms=120.0,
        proof_of_execution_rate=0.99
    )
    c2 = AgentCard124(
        agent_id="agent-dev-2",
        name="JuniorDev",
        role="developer",
        capabilities=["python"],
        max_concurrency=2,
        current_load=0,
        reputation_score=0.80,
        avg_latency_ms=250.0,
        proof_of_execution_rate=0.90
    )

    assert router.register_agent(c1) is True
    assert router.register_agent(c2) is True

    # Pareto Routing selection
    selected = router.find_pareto_optimal_agent(["python", "refactor"])
    assert selected is not None
    assert selected.agent_id == "agent-dev-1"

    # Submit tasks for Kahn DAG with CPM Slack
    t1 = DecoupledTaskContract124("T1", "Design API", "Design spec", ["python"], estimated_duration_ms=50.0)
    t2 = DecoupledTaskContract124("T2", "Implement API", "Write code", ["python"], dependencies=["T1"], estimated_duration_ms=150.0)
    t3 = DecoupledTaskContract124("T3", "Document API", "Write docs", ["docs"], dependencies=["T1"], estimated_duration_ms=40.0)
    t4 = DecoupledTaskContract124("T4", "Verify API", "Run test suite", ["test"], dependencies=["T2", "T3"], estimated_duration_ms=60.0)

    for task in [t1, t2, t3, t4]:
        router.submit_task(task)

    wavefronts, slack_times = router.compute_kahn_wavefronts_with_cpm()
    assert len(wavefronts) == 3
    assert wavefronts[0] == ["T1"]
    assert set(wavefronts[1]) == {"T2", "T3"}
    assert wavefronts[2] == ["T4"]
    # T3 is shorter than T2 on parallel branch, so T3 should have slack > 0
    assert slack_times["T3"] > 0.0
    assert slack_times["T2"] == 0.0  # Critical path task has 0 slack

    # 3-Phase PBFT Quorum test
    action_str = "COMMIT_RELEASE_V124"
    sigs = {
        "agent-dev-1": c1.generate_signature(),
        "agent-dev-2": c2.generate_signature()
    }
    # PBFT check with action hash
    sig_action = {
        "agent-dev-1": hmac.new(c1.hmac_secret.encode(), action_str.encode(), "sha256").hexdigest(),
        "agent-dev-2": hmac.new(c2.hmac_secret.encode(), action_str.encode(), "sha256").hexdigest()
    }
    assert router.execute_3phase_pbft_consensus("T4", action_str, sig_action) is True

    # AP2 3.5 6-Tier SLA Escrow test
    escrow = AP235SLAEscrow()
    escrow.lock_escrow("T2", "agent-dev-1", staked_tokens=1000, max_latency_ms=200.0, min_quality_score=0.90)

    # Settle with latency breach and minor quality defect
    settle_res = escrow.settle_escrow(
        task_id="T2",
        actual_latency_ms=280.0,  # Latency breach: 20% penalty
        quality_score=0.82,       # Quality defect: 30% penalty
        security_breach=False
    )
    assert settle_res["status"] == "SETTLED"
    assert settle_res["penalty_ratio"] == 0.50
    assert settle_res["released"] == 500
    assert settle_res["clawback"] == 500


def test_self_refining_harness90_ast_guard100_merkle_and_fit_ratio():
    harness = SelfRefiningHarness90(failure_threshold=3)

    # AST Preflight Guard 10.0 tests
    safe_code = "def compute(a, b):\n    return a + b\n"
    is_safe, err = ASTPreflightGuard100.audit_code_safety(safe_code)
    assert is_safe is True
    assert err is None

    unsafe_eval = "def hack():\n    eval('2 + 2')\n"
    is_safe, err = ASTPreflightGuard100.audit_code_safety(unsafe_eval)
    assert is_safe is False
    assert "Forbidden call detected: eval()" in err

    unsafe_import = "import ctypes\ndef sys_hack():\n    pass\n"
    is_safe, err = ASTPreflightGuard100.audit_code_safety(unsafe_import)
    assert is_safe is False
    assert "Forbidden module import: ctypes" in err

    # Merkle Checkpoint Stack & Rollback
    base_fs = {"src/app.py": "print('v1.0')", "docs/api.md": "# API Docs"}
    merkle_v1 = harness.snapshot_checkpoint(base_fs)
    assert len(merkle_v1) == 64

    mutated_fs = {"src/app.py": "print('broken v1.1')", "docs/api.md": "# API Docs"}
    merkle_v2 = harness.compute_merkle_root(mutated_fs)
    assert merkle_v1 != merkle_v2

    # Rollback to green state
    rolled_back = harness.rollback_to_last_green()
    assert rolled_back["src/app.py"] == "print('v1.0')"

    # Fit Ratio 8.0 & Circuit Breaker test
    harness.record_fault(HarnessFaultCategory124.ENVIRONMENT_DEFECT, "Connection timeout to Redis")
    harness.record_fault(HarnessFaultCategory124.MODEL_DEFECT, "Hallucinated parameter 'extra_key'")
    fit_ratio = harness.compute_fit_ratio_80()
    assert fit_ratio == 0.50

    harness.record_fault(HarnessFaultCategory124.TOOL_DEFECT, "Schema drift on 'user_id'")
    assert harness.circuit_open is True  # Reached 3 failures threshold

    # Dynamic Micro-Adapter Synthesis v5
    harness.synthesize_micro_adapter("fetch_user", {"uid": "user_id"})
    adapted_args = harness.adapters["fetch_user"]({"uid": 42, "role": "admin"})
    assert "user_id" in adapted_args
    assert adapted_args["user_id"] == 42
    assert "uid" not in adapted_args


def test_agent_desks90_swb_linda_tuple_space_and_3way_ast_reconciler():
    desks = AgentDesks90()
    base_fs = {"src/main.py": "def run():\n    pass\n"}
    desks.create_desk("dev-desk-1", base_fs)

    # Single-Writer Boundary (SWB) enforcement
    # Developer can write to src/
    desks.write_file("dev-desk-1", DeskRole124.DEVELOPER, "src/main.py", "def run():\n    return 1\n")
    assert desks.virtual_desks["dev-desk-1"]["src/main.py"] == "def run():\n    return 1\n"

    # Developer writing to docs/ must raise SWB violation
    with pytest.raises(SingleWriterBoundaryViolation124):
        desks.write_file("dev-desk-1", DeskRole124.DEVELOPER, "docs/spec.md", "# Spec")

    # Linda Tuple Space: out, read, in
    desks.tuple_out(("BUILD_STATUS", "dev-desk-1", "PASSED"))
    desks.tuple_out(("METRIC", "cpu", "45%"))

    # Non-destructive read
    read_t = desks.tuple_read(("BUILD_STATUS", None, "PASSED"))
    assert read_t == ("BUILD_STATUS", "dev-desk-1", "PASSED")
    assert len(desks.tuple_space) == 2

    # Destructive take (in)
    taken_t = desks.tuple_in(("BUILD_STATUS", None, "PASSED"))
    assert taken_t == ("BUILD_STATUS", "dev-desk-1", "PASSED")
    assert len(desks.tuple_space) == 1

    # 3-Way AST Semantic Conflict-Free Reconciler 4.0
    base_code = "def compute_core(x):\n    return x * 2\n"
    dev_code = "def compute_core(x):\n    return x * 2\n\ndef helper_dev():\n    return 'dev'\n"
    test_code = "def compute_core(x):\n    return x * 2\n\ndef test_suite():\n    assert compute_core(2) == 4\n"

    merged = desks.reconcile_ast_3way(base_code, dev_code, test_code)
    assert "def compute_core(x):" in merged
    assert "def helper_dev():" in merged
    assert "def test_suite():" in merged


def test_icos_store_20layer_memory_bi_temporal_ebbinghaus_and_rrf20():
    memory = IcosStore20LayerMemory()

    # Add memories across layers
    m1 = memory.add_memory(layer_index=1, content="Obsidian Architecture Directives for Faz 124", importance=0.9)
    m2 = memory.add_memory(layer_index=2, content="Supabase StreamingDiskANN pgvector 0.8 scale index", importance=0.85)
    m15 = memory.add_memory(layer_index=15, content="Episodic Trace: Successful compilation of Faz 124 suite", importance=0.95)

    assert len(memory.layers[1]) == 1
    assert len(memory.layers[2]) == 1
    assert len(memory.layers[15]) == 1

    # Graphiti 2.0 Bi-Temporal Soft Invalidation
    assert memory.invalidate_fact_bi_temporal(m2.item_id) is True
    assert m2.is_invalidated is True
    assert m2.invalid_at is not None

    # Ebbinghaus Decay & Retention calculation
    retention = memory.compute_ebbinghaus_retention(m15, time.time())
    assert retention > 0.90

    # Dream Consolidation
    consolidation = memory.run_dream_consolidation()
    assert consolidation["promoted"] >= 1
    assert len(memory.layers[1]) >= 2  # Promoted from layer 15 to layer 1

    # Dynamic RRF-20 Retrieval
    results = memory.retrieve_rrf20("Architecture Faz 124", top_k=3)
    assert len(results) >= 1
    top_item, top_score = results[0]
    assert "124" in top_item.content
    assert top_score > 0.0


def test_extreme_token_physics_160_and_codeact_repl():
    # Radix prompt cache alignment (pads to multiple of 128 tokens)
    raw_prompt = "System Prompt: Autonomous Agent Fleet"
    aligned = TokenPhysics160.align_radix_prompt_cache(raw_prompt, boundary=128)
    assert "radix_cache_aligned" in aligned

    # AST Skeletonization 10.0 (strips bodies, retains signatures and docstrings)
    code_to_skeletonize = (
        "def process_data(records: list) -> dict:\n"
        "    \"\"\"Processes raw records into aggregate stats.\"\"\"\n"
        "    total = sum(records)\n"
        "    avg = total / len(records)\n"
        "    return {'total': total, 'avg': avg}\n"
    )
    skeleton = TokenPhysics160.ast_skeletonize(code_to_skeletonize)
    assert "Processes raw records into aggregate stats." in skeleton
    assert "..." in skeleton
    assert "total = sum(records)" not in skeleton

    # Delta Token Accounting 9.0
    current_u = {"input": 15400, "output": 2100, "total": 17500}
    baseline_u = {"input": 12000, "output": 1800, "total": 13800}
    delta = TokenPhysics160.calculate_delta_tokens(current_u, baseline_u)
    assert delta["delta_input"] == 3400
    assert delta["delta_output"] == 300
    assert delta["delta_total"] == 3700

    # CodeAct 9.0 Virtual Sandboxed Python REPL
    valid_script = (
        "data = [10, 20, 30, 40]\n"
        "output = sum(data)\n"
        "print(f'Computed sum: {output}')\n"
    )
    succ, res, stdout = TokenPhysics160.execute_codeact_script(valid_script)
    assert succ is True
    assert res == 100
    assert "Computed sum: 100" in stdout

    # CodeAct Security Rejection for unsafe script
    malicious_script = "import ctypes\nctypes.string_at(0)\n"
    succ_bad, _, err_out = TokenPhysics160.execute_codeact_script(malicious_script)
    assert succ_bad is False
    assert "CodeAct Security Rejection" in err_out


def test_erlang_otp_supervisor90_supervision_strategies_and_collapse_budget():
    # Test One-For-One Strategy
    sup_one = ErlangOTPSupervisor90(SupervisionStrategy124.ONE_FOR_ONE, max_restarts=3, window_seconds=10.0)
    sup_one.register_worker("worker_a")
    sup_one.register_worker("worker_b")

    action, affected = sup_one.handle_worker_crash("worker_a")
    assert action == "RESTARTED_ONE"
    assert affected == ["worker_a"]
    assert sup_one.workers["worker_a"]["restart_count"] == 1
    assert sup_one.workers["worker_b"]["restart_count"] == 0

    # Test Rest-For-One Strategy
    sup_rest = ErlangOTPSupervisor90(SupervisionStrategy124.REST_FOR_ONE, max_restarts=5, window_seconds=10.0)
    sup_rest.register_worker("w1")
    sup_rest.register_worker("w2")
    sup_rest.register_worker("w3")

    action_rest, affected_rest = sup_rest.handle_worker_crash("w2")
    assert action_rest == "RESTARTED_REST"
    assert affected_rest == ["w2", "w3"]

    # Test Cascade Collapse Protection (exceeding restart budget)
    sup_collapse = ErlangOTPSupervisor90(SupervisionStrategy124.ONE_FOR_ALL, max_restarts=2, window_seconds=60.0)
    sup_collapse.register_worker("node1")
    sup_collapse.register_worker("node2")

    sup_collapse.handle_worker_crash("node1")
    sup_collapse.handle_worker_crash("node1")
    action_col, _ = sup_collapse.handle_worker_crash("node1")  # 3rd restart exceeds limit of 2
    assert action_col == "COLLAPSE_SUPERVISOR"
    assert sup_collapse.supervisor_collapsed is True


def test_faz124_master_swarm_orchestrator_end_to_end_mission():
    orchestrator = Faz124MasterSwarmOrchestrator()

    # Register specialized fleet agents
    architect = AgentCard124(
        agent_id="arch-01",
        name="SystemArchitect",
        role="architect",
        capabilities=["spec", "architecture"],
        max_concurrency=2,
        reputation_score=0.99
    )
    developer = AgentCard124(
        agent_id="dev-01",
        name="LeadDeveloper",
        role="developer",
        capabilities=["coding", "fastmcp"],
        max_concurrency=4,
        reputation_score=0.96
    )
    tester = AgentCard124(
        agent_id="qa-01",
        name="VerificationSentinel",
        role="tester",
        capabilities=["qa", "testing"],
        max_concurrency=2,
        reputation_score=0.98
    )

    orchestrator.router.register_agent(architect)
    orchestrator.router.register_agent(developer)
    orchestrator.router.register_agent(tester)

    mission = {
        "mission_id": "faz124-frontier-swarm",
        "tasks": [
            {"id": "TASK-1", "title": "Design Microkernel Protocol", "spec": "Write spec", "caps": ["spec"], "deps": [], "duration_ms": 40.0},
            {"id": "TASK-2", "title": "Implement FastMCP 6.5 Tools", "spec": "Code tools", "caps": ["coding"], "deps": ["TASK-1"], "duration_ms": 120.0},
            {"id": "TASK-3", "title": "Verify Test Suite", "spec": "Execute pytest", "caps": ["qa"], "deps": ["TASK-2"], "duration_ms": 50.0}
        ]
    }

    mission_output = orchestrator.run_autonomous_mission(mission)
    assert mission_output["status"] == "SUCCESS"
    assert mission_output["wavefronts_count"] == 3
    assert len(mission_output["executed_tasks"]) == 3
    assert "proof_hash" in mission_output["executed_tasks"]["TASK-3"]
    assert len(mission_output["executed_tasks"]["TASK-3"]["proof_hash"]) == 64
