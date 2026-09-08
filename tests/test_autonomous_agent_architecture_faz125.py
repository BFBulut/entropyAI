"""
Automated Test Suite for Faz 125 Master Autonomous Agent Architecture Module
=============================================================================
Verifies 100% programmatic correctness across all 8 architectural pillars:
1. Stateless FastMCP 7.0 (SEP-4500 Bitmask Matrix, SBTE Routing, Attenuation v6, ETag 304, Pipelines)
2. AAIF A2A v4.0 & AP2 4.0 (Agent Cards, Pareto Routing, Kahn DAG with CPM Slack, PBFT, 7-Tier Escrow)
3. Self-Refining Harness 10.0 (Fit Ratio 9.0, AST Guard 11.0, Micro-Adapters, Merkle Rollback)
4. Agent Desks 10.0 (MG-SWB Leases, Linda Tuple Space 5.0, 4-Way AST Semantic Merge 5.0)
5. Henicos-Store 21-Layer Memory (Graphiti 2.0 Invalidation, Ebbinghaus Decay, Dream Phase, RRF-21 Fusion)
6. Extreme Token Physics 17.0 (Radix Alignment, CodeAct 10.0 REPL, AST Skeletonization, Delta Tokens)
7. Erlang-OTP 10.0 Supervision Trees (One-for-One, One-for-All, Rest-for-One, Collapse Budget)
8. Faz 125 Master Autonomous Swarm Orchestrator (Full Mission Lifecycle & End-to-End Execution)
"""

import hmac
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz125 import (
    StatelessFastMCP70Engine,
    MCPToolDefinition125,
    TaskLifecycleStage125,
    AgentCard125,
    DecoupledTaskContract125,
    TaskFSMState125,
    AAIFMeshRouter125,
    AP240SLAEscrow,
    SelfRefiningHarness100,
    HarnessFaultCategory125,
    ASTPreflightGuard110,
    AgentDesks100,
    DeskRole125,
    SingleWriterBoundaryViolation125,
    HenicosStore21LayerMemory,
    TokenPhysics170,
    ErlangOTPSupervisor100,
    SupervisionStrategy125,
    Faz125MasterSwarmOrchestrator
)


def test_fastmcp70_bitmask_matrix_sbte_routing_attenuation_and_etag_caching():
    engine = StatelessFastMCP70Engine()

    def calc_multiply(args):
        return args["x"] * args["y"]

    def audit_scan(args):
        return {"vulnerabilities_found": 0, "target": args["path"]}

    t1 = MCPToolDefinition125(
        name="math_multiply",
        domain="math",
        description="Multiplies two numbers x and y",
        parameters={"x": "float", "y": "float"},
        handler=calc_multiply,
        allowed_stages=[TaskLifecycleStage125.EXECUTION],
        preconditions=lambda args: "x" in args and "y" in args,
        cacheable=True,
        cache_ttl_seconds=30,
        volatility_score=0.1,
        keywords=["multiply", "product"],
        capability_bitmask=0x01,
        sparse_binary_vector=[1, 1, 0, 0]
    )

    t2 = MCPToolDefinition125(
        name="security_audit",
        domain="security",
        description="Scans code path for security defects",
        parameters={"path": "str"},
        handler=audit_scan,
        allowed_stages=[TaskLifecycleStage125.AUDIT],
        cacheable=False,
        keywords=["audit", "scan"],
        capability_bitmask=0x02,
        sparse_binary_vector=[0, 0, 1, 1]
    )

    engine.register_tool(t1)
    engine.register_tool(t2)

    # Test bitmask capability & stage-aware negotiation
    exec_tools = engine.negotiate_active_tools(
        stage=TaskLifecycleStage125.EXECUTION,
        intent_keywords=["multiply"],
        capability_mask=0x01,
        binary_query_vector=[1, 1, 0, 0]
    )
    assert len(exec_tools) == 1
    assert exec_tools[0].name == "math_multiply"

    audit_tools = engine.negotiate_active_tools(
        stage=TaskLifecycleStage125.AUDIT,
        intent_keywords=["scan"],
        capability_mask=0x02,
        binary_query_vector=[0, 0, 1, 1]
    )
    assert len(audit_tools) == 1
    assert audit_tools[0].name == "security_audit"

    # Attenuated signature test v6
    sig = t1.get_attenuated_signature()
    assert "def math_multiply(x: float, y: float) -> Any:" in sig
    assert "Multiplies two numbers x and y" in sig

    # Execution & ETag 304 Caching test
    code1, res1 = engine.execute_tool("math_multiply", {"x": 7.0, "y": 8.0})
    assert code1 == 200
    assert res1["result"] == 56.0
    etag1 = res1["etag"]

    # Repeat with same arguments and client_etag -> expect 304
    code2, res2 = engine.execute_tool("math_multiply", {"x": 7.0, "y": 8.0}, client_etag=etag1)
    assert code2 == 304
    assert res2["status"] == "not_modified"

    # Markov pre-warming check
    predicted = engine.predict_next_tools("math_multiply")
    assert isinstance(predicted, list)

    # Reactive Streaming Push
    engine.push_context_diff("MODULE_SYNCED", {"module": "faz125", "status": "active"})
    diffs = engine.drain_context_diffs()
    assert len(diffs) == 1
    assert diffs[0]["type"] == "MODULE_SYNCED"

    # Compound Batch Pipeline test
    pipeline_def = [
        {"tool": "math_multiply", "args": {"x": 5.0, "y": 6.0}},
        {"tool": "security_audit", "args": {"path": "src/faz125.py"}}
    ]
    pipe_res = engine.execute_compound_pipeline(pipeline_def)
    assert pipe_res["pipeline_status"] == "success"
    assert pipe_res["outputs"]["step_0"] == 30.0


def test_aaif_a2a_v40_pareto_routing_kahn_cpm_pbft_and_7tier_escrow():
    router = AAIFMeshRouter125()

    # Register Agents with HMAC cards
    c1 = AgentCard125(
        agent_id="agent-arch-1",
        name="MasterArchitect",
        role="architect",
        capabilities=["python", "system_design", "fastmcp"],
        max_concurrency=4,
        current_load=1,
        reputation_score=0.99,
        avg_latency_ms=110.0,
        proof_of_execution_rate=0.99,
        quality_confidence=0.98
    )
    c2 = AgentCard125(
        agent_id="agent-dev-2",
        name="SupportDev",
        role="developer",
        capabilities=["python"],
        max_concurrency=2,
        current_load=0,
        reputation_score=0.82,
        avg_latency_ms=220.0,
        proof_of_execution_rate=0.91,
        quality_confidence=0.85
    )

    assert router.register_agent(c1) is True
    assert router.register_agent(c2) is True

    # Pareto Routing selection
    selected = router.find_pareto_optimal_agent(["python", "system_design"])
    assert selected is not None
    assert selected.agent_id == "agent-arch-1"

    # Submit tasks for Kahn DAG with CPM Slack Borrowing
    t1 = DecoupledTaskContract125("T1", "Design Exokernel", "Design spec", ["python"], estimated_duration_ms=60.0)
    t2 = DecoupledTaskContract125("T2", "Implement FastMCP 7.0", "Write code", ["python"], dependencies=["T1"], estimated_duration_ms=140.0)
    t3 = DecoupledTaskContract125("T3", "Document Protocol", "Write docs", ["docs"], dependencies=["T1"], estimated_duration_ms=40.0)
    t4 = DecoupledTaskContract125("T4", "Verify Test Suite", "Run pytest", ["test"], dependencies=["T2", "T3"], estimated_duration_ms=50.0)

    for task in [t1, t2, t3, t4]:
        router.submit_task(task)

    wavefronts, slack_times = router.compute_kahn_wavefronts_with_cpm()
    assert len(wavefronts) == 3
    assert wavefronts[0] == ["T1"]
    assert set(wavefronts[1]) == {"T2", "T3"}
    assert wavefronts[2] == ["T4"]
    assert slack_times["T3"] > 0.0
    assert slack_times["T2"] == 0.0

    # 3-Phase PBFT Quorum test
    action_str = "COMMIT_RELEASE_V125"
    sig_action = {
        "agent-arch-1": hmac.new(c1.hmac_secret.encode(), action_str.encode(), "sha256").hexdigest(),
        "agent-dev-2": hmac.new(c2.hmac_secret.encode(), action_str.encode(), "sha256").hexdigest()
    }
    assert router.execute_3phase_pbft_consensus("T4", action_str, sig_action) is True

    # AP2 4.0 7-Tier SLA Escrow test
    escrow = AP240SLAEscrow()
    escrow.lock_escrow("T2", "agent-arch-1", staked_tokens=1000, max_latency_ms=200.0, min_quality_score=0.90, token_quota=8000)

    # Settle with latency breach, quality defect, and token quota breach
    settle_res = escrow.settle_escrow(
        task_id="T2",
        actual_latency_ms=250.0,    # Latency breach: 20%
        quality_score=0.85,         # Quality defect: 30%
        security_breach=False,
        tokens_consumed=9500,       # Quota breach: 25%
        schema_defect=False,
        audit_discrepancy=False,
        contract_hallucination=False
    )
    assert settle_res["status"] == "SETTLED"
    assert settle_res["penalty_ratio"] == 0.75
    assert settle_res["released"] == 250
    assert settle_res["clawback"] == 750


def test_self_refining_harness100_ast_guard110_merkle_and_fit_ratio():
    harness = SelfRefiningHarness100(failure_threshold=3)

    # AST Preflight Guard 11.0 tests
    safe_code = "def compute(a, b):\n    return a * b + 10\n"
    is_safe, err = ASTPreflightGuard110.audit_code_safety(safe_code)
    assert is_safe is True
    assert err is None

    unsafe_eval = "def hack():\n    eval('import os; os.system(\"rm -rf /\")')\n"
    is_safe, err = ASTPreflightGuard110.audit_code_safety(unsafe_eval)
    assert is_safe is False
    assert "Forbidden call detected: eval()" in err

    unsafe_import = "import ctypes\ndef sys_hack():\n    pass\n"
    is_safe, err = ASTPreflightGuard110.audit_code_safety(unsafe_import)
    assert is_safe is False
    assert "Forbidden module import: ctypes" in err

    # Merkle Checkpoint Stack & Rollback
    base_fs = {"src/kernel.py": "print('exokernel v125')", "docs/adr.md": "# ADR 125"}
    merkle_v1 = harness.snapshot_checkpoint(base_fs)
    assert len(merkle_v1) == 64

    mutated_fs = {"src/kernel.py": "print('broken exokernel')", "docs/adr.md": "# ADR 125"}
    merkle_v2 = harness.compute_merkle_root(mutated_fs)
    assert merkle_v1 != merkle_v2

    # Rollback to green state
    rolled_back = harness.rollback_to_last_green()
    assert rolled_back["src/kernel.py"] == "print('exokernel v125')"

    # Fit Ratio 9.0 & Circuit Breaker test
    harness.record_fault(HarnessFaultCategory125.ENVIRONMENT_DEFECT, "Asyncio loop deadlock")
    harness.record_fault(HarnessFaultCategory125.MODEL_DEFECT, "Hallucinated argument 'bogus_id'")
    fit_ratio = harness.compute_fit_ratio_90()
    assert fit_ratio == 0.50

    harness.record_fault(HarnessFaultCategory125.CONTEXT_DRIFT, "Context window overflow")
    assert harness.circuit_open is True  # Reached 3 failures threshold

    # Dynamic Micro-Adapter Synthesis v6
    harness.synthesize_micro_adapter("lookup_record", {"rec_id": "record_id"})
    adapted_args = harness.adapters["lookup_record"]({"rec_id": 999, "action": "fetch"})
    assert "record_id" in adapted_args
    assert adapted_args["record_id"] == 999
    assert "rec_id" not in adapted_args


def test_agent_desks100_swb_linda_tuple_space_and_4way_ast_reconciler():
    desks = AgentDesks100()
    base_fs = {"src/engine.py": "def start():\n    pass\n"}
    desks.create_desk("dev-desk-125", base_fs)

    # Multi-Granular Single-Writer Boundary (MG-SWB)
    desks.write_file("dev-desk-125", DeskRole125.DEVELOPER, "src/engine.py", "def start():\n    return 42\n")
    assert desks.virtual_desks["dev-desk-125"]["src/engine.py"] == "def start():\n    return 42\n"

    # Developer writing to docs/ must raise SWB violation
    with pytest.raises(SingleWriterBoundaryViolation125):
        desks.write_file("dev-desk-125", DeskRole125.DEVELOPER, "docs/spec.md", "# Spec 125")

    # Linda Tuple Space 5.0: out, read, in
    desks.tuple_out(("SYNC_SIGNAL", "dev-desk-125", "READY"))
    desks.tuple_out(("PERF_METRIC", "ipc_latency", "1.2us"))

    # Non-destructive read
    read_t = desks.tuple_read(("SYNC_SIGNAL", None, "READY"))
    assert read_t == ("SYNC_SIGNAL", "dev-desk-125", "READY")
    assert len(desks.tuple_space) == 2

    # Destructive take (in)
    taken_t = desks.tuple_in(("SYNC_SIGNAL", None, "READY"))
    assert taken_t == ("SYNC_SIGNAL", "dev-desk-125", "READY")
    assert len(desks.tuple_space) == 1

    # 4-Way AST Semantic Conflict-Free Reconciler 5.0
    base_code = "def core_calc(x):\n    return x * 10\n"
    dev_code = "def core_calc(x):\n    return x * 10\n\ndef helper_fastmcp():\n    return 'fastmcp70'\n"
    test_code = "def core_calc(x):\n    return x * 10\n\ndef test_core():\n    assert core_calc(2) == 20\n"

    merged = desks.reconcile_ast_3way(base_code, dev_code, test_code)
    assert "def core_calc(x):" in merged
    assert "def helper_fastmcp():" in merged
    assert "def test_core():" in merged


def test_henicos_store_21layer_memory_bi_temporal_ebbinghaus_and_rrf21():
    memory = HenicosStore21LayerMemory()

    # Add memories across layers including Layer 20 (Causal DAG) and Layer 21 (RRF)
    m1 = memory.add_memory(layer_index=1, content="Obsidian Master Architecture Directives Faz 125", importance=0.95)
    m2 = memory.add_memory(layer_index=2, content="Supabase StreamingDiskANN pgvector 0.8 scale index", importance=0.88)
    m15 = memory.add_memory(layer_index=15, content="Episodic Trace: Execution of Faz 125 verification test suite", importance=0.96)
    m20 = memory.add_memory(layer_index=20, content="Causal Counterfactual Knowledge DAG: Do-calculus intervention on tool selection", importance=0.92)

    assert len(memory.layers[1]) == 1
    assert len(memory.layers[2]) == 1
    assert len(memory.layers[15]) == 1
    assert len(memory.layers[20]) == 1

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

    # Dynamic RRF-21 Retrieval
    results = memory.retrieve_rrf21("Architecture Faz 125 Causal", top_k=3)
    assert len(results) >= 1
    top_item, top_score = results[0]
    assert "125" in top_item.content
    assert top_score > 0.0


def test_extreme_token_physics_170_and_codeact_repl():
    # Radix prompt cache alignment (pads to multiple of 128 tokens)
    raw_prompt = "System Prompt: Autonomous Agent Fleet Faz 125"
    aligned = TokenPhysics170.align_radix_prompt_cache(raw_prompt, boundary=128)
    assert "radix_cache_aligned" in aligned

    # AST Skeletonization 11.0 (strips bodies, retains signatures and docstrings)
    code_to_skeletonize = (
        "def process_telemetry(events: list) -> dict:\n"
        "    \"\"\"Processes swarm telemetry into KPI metrics.\"\"\"\n"
        "    total = sum(events)\n"
        "    peak = max(events)\n"
        "    return {'total': total, 'peak': peak}\n"
    )
    skeleton = TokenPhysics170.ast_skeletonize(code_to_skeletonize)
    assert "Processes swarm telemetry into KPI metrics." in skeleton
    assert "..." in skeleton
    assert "total = sum(events)" not in skeleton

    # Delta Token Accounting 10.0
    current_u = {"input": 18500, "output": 2600, "total": 21100}
    baseline_u = {"input": 14000, "output": 2200, "total": 16200}
    delta = TokenPhysics170.calculate_delta_tokens(current_u, baseline_u)
    assert delta["delta_input"] == 4500
    assert delta["delta_output"] == 400
    assert delta["delta_total"] == 4900

    # CodeAct 10.0 Virtual Sandboxed Python REPL
    valid_script = (
        "raw_metrics = [100, 200, 300]\n"
        "output = sum(raw_metrics)\n"
        "print(f'Swarm total: {output}')\n"
    )
    succ, res, stdout = TokenPhysics170.execute_codeact_script(valid_script)
    assert succ is True
    assert res == 600
    assert "Swarm total: 600" in stdout

    # CodeAct Security Rejection for unsafe script
    malicious_script = "import ctypes\nctypes.string_at(0)\n"
    succ_bad, _, err_out = TokenPhysics170.execute_codeact_script(malicious_script)
    assert succ_bad is False
    assert "CodeAct Security Rejection" in err_out


def test_erlang_otp_supervisor100_supervision_strategies_and_collapse_budget():
    # Test One-For-One Strategy
    sup_one = ErlangOTPSupervisor100(SupervisionStrategy125.ONE_FOR_ONE, max_restarts=3, window_seconds=10.0)
    sup_one.register_worker("worker_a")
    sup_one.register_worker("worker_b")

    action, affected = sup_one.handle_worker_crash("worker_a")
    assert action == "RESTARTED_ONE"
    assert affected == ["worker_a"]
    assert sup_one.workers["worker_a"]["restart_count"] == 1
    assert sup_one.workers["worker_b"]["restart_count"] == 0

    # Test Rest-For-One Strategy
    sup_rest = ErlangOTPSupervisor100(SupervisionStrategy125.REST_FOR_ONE, max_restarts=5, window_seconds=10.0)
    sup_rest.register_worker("w1")
    sup_rest.register_worker("w2")
    sup_rest.register_worker("w3")

    action_rest, affected_rest = sup_rest.handle_worker_crash("w2")
    assert action_rest == "RESTARTED_REST"
    assert affected_rest == ["w2", "w3"]

    # Test Cascade Collapse Protection (exceeding restart budget)
    sup_collapse = ErlangOTPSupervisor100(SupervisionStrategy125.ONE_FOR_ALL, max_restarts=2, window_seconds=60.0)
    sup_collapse.register_worker("node1")
    sup_collapse.register_worker("node2")

    sup_collapse.handle_worker_crash("node1")
    sup_collapse.handle_worker_crash("node1")
    action_col, _ = sup_collapse.handle_worker_crash("node1")  # 3rd restart exceeds limit of 2
    assert action_col == "COLLAPSE_SUPERVISOR"
    assert sup_collapse.supervisor_collapsed is True


def test_faz125_master_swarm_orchestrator_end_to_end_mission():
    orchestrator = Faz125MasterSwarmOrchestrator()

    # Register specialized fleet agents
    architect = AgentCard125(
        agent_id="arch-125",
        name="ExokernelArchitect",
        role="architect",
        capabilities=["spec", "architecture"],
        max_concurrency=2,
        reputation_score=0.99
    )
    developer = AgentCard125(
        agent_id="dev-125",
        name="LeadFastMCPDev",
        role="developer",
        capabilities=["coding", "fastmcp"],
        max_concurrency=4,
        reputation_score=0.97
    )
    tester = AgentCard125(
        agent_id="qa-125",
        name="VerificationSentinel",
        role="tester",
        capabilities=["qa", "testing"],
        max_concurrency=2,
        reputation_score=0.99
    )

    orchestrator.router.register_agent(architect)
    orchestrator.router.register_agent(developer)
    orchestrator.router.register_agent(tester)

    mission = {
        "mission_id": "faz125-exokernel-swarm",
        "tasks": [
            {"id": "TASK-1", "title": "Design FastMCP 7.0 & Exokernel", "spec": "Write spec", "caps": ["spec"], "deps": [], "duration_ms": 40.0},
            {"id": "TASK-2", "title": "Implement SBTE Routing Tools", "spec": "Code tools", "caps": ["coding"], "deps": ["TASK-1"], "duration_ms": 120.0},
            {"id": "TASK-3", "title": "Verify Henicos-Store & Escrow", "spec": "Execute pytest", "caps": ["qa"], "deps": ["TASK-2"], "duration_ms": 50.0}
        ]
    }

    mission_output = orchestrator.run_autonomous_mission(mission)
    assert mission_output["status"] == "SUCCESS"
    assert mission_output["wavefronts_count"] == 3
    assert len(mission_output["executed_tasks"]) == 3
    assert "proof_hash" in mission_output["executed_tasks"]["TASK-3"]
    assert len(mission_output["executed_tasks"]["TASK-3"]["proof_hash"]) == 64
