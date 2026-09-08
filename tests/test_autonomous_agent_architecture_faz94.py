"""
Unit tests for Faz 94 Autonomous Agent Architecture.
Validates:
1. Faz94HarnessOfHarnessEngine (Single-Writer Boundary, Candidate Freezing, Evidence State).
2. Faz94HarnessOfHarnessEngine Dual Cross-Loop Persistence (Regression detection, preservation invariants).
3. Faz94HybridExocortexMemoryEngine (pgvector 0.8+ 1-Bit BQ POPCNT search, Obsidian daily trace).
4. Faz94TokenPhysicsContextEngine (Automatic Prefix Caching, Code-as-Action savings, Delta tokens).
5. Faz94MasterAutonomousAgentOS (End-to-end mission lifecycle with frozen QA gating).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    AgentRole,
    ArtifactState,
    EvidenceState,
    Faz94HarnessOfHarnessEngine,
    Faz94HybridExocortexMemoryEngine,
    Faz94TokenPhysicsContextEngine,
    Faz94MasterAutonomousAgentOS
)


def test_faz94_hoh_single_writer_boundary_and_candidate_freezing():
    engine = Faz94HarnessOfHarnessEngine(project_name="TradingEngine")
    artifact = engine.start_iteration(initial_files={"main.py": "print('hello')"})

    assert artifact.iteration == 1
    assert "main.py" in artifact.files
    assert not artifact.is_frozen

    # 1. Developer role can successfully mutate files
    mut_res = engine.apply_file_mutation(
        role=AgentRole.DEVELOPER,
        file_path="main.py",
        content="print('hello autonomous world')"
    )
    assert mut_res["status"] == "MUTATION_APPLIED"
    assert engine.artifact_state.files["main.py"] == "print('hello autonomous world')"

    # 2. Planner and QA Tester roles are BLOCKED by Single-Writer Boundary
    with pytest.raises(PermissionError) as exc_planner:
        engine.apply_file_mutation(
            role=AgentRole.PLANNER,
            file_path="main.py",
            content="malicious_patch()"
        )
    assert "Single-Writer Boundary Violation" in str(exc_planner.value)

    with pytest.raises(PermissionError) as exc_qa:
        engine.apply_file_mutation(
            role=AgentRole.QA_TESTER,
            file_path="main.py",
            content="force_test_pass = True"
        )
    assert "Single-Writer Boundary Violation" in str(exc_qa.value)

    # 3. Candidate Freezing locks artifact before QA evaluation
    freeze_res = engine.freeze_candidate()
    assert freeze_res["status"] == "CANDIDATE_FROZEN"
    assert engine.artifact_state.is_frozen is True

    # 4. Mutation on frozen candidate raises PermissionError even for Developer
    with pytest.raises(PermissionError) as exc_frozen:
        engine.apply_file_mutation(
            role=AgentRole.DEVELOPER,
            file_path="main.py",
            content="late_patch()"
        )
    assert "Candidate Freezing Active" in str(exc_frozen.value)


def test_faz94_hoh_dual_cross_loop_persistence_and_regressions():
    engine = Faz94HarnessOfHarnessEngine(project_name="OrderRouter")
    engine.start_iteration(initial_files={"router.py": "def route(): return True"})
    engine.freeze_candidate()

    # Iteration 1 QA: Invariants test_init and test_auth pass, test_speed fails
    qa1 = engine.execute_qa_evaluation(
        test_results={"test_init": True, "test_auth": True, "test_speed": False},
        discovered_bugs=["latency_spike_p99"]
    )
    assert qa1["verdict"] == "GAPS_REMAIN"
    assert "test_init" in qa1["newly_verified"]
    assert "test_auth" in qa1["newly_verified"]
    assert "test_speed" in qa1["open_regression_gaps"]
    assert "latency_spike_p99" in qa1["open_regression_gaps"]
    assert engine.evidence_state.verified_preservation_invariants == ["test_auth", "test_init"]

    # Iteration 2: Fix speed, but accidentally break test_auth (REGRESSION!)
    engine.start_iteration()
    engine.apply_file_mutation(
        role=AgentRole.DEVELOPER,
        file_path="router.py",
        content="def route(): return fast_route()"
    )
    engine.freeze_candidate()

    qa2 = engine.execute_qa_evaluation(
        test_results={"test_init": True, "test_auth": False, "test_speed": True}
    )
    assert qa2["verdict"] == "REGRESSION_DETECTED"
    assert "test_auth" in qa2["regressions"]
    assert "test_auth" in qa2["open_regression_gaps"]
    # Broken test_auth is removed from verified invariants until fixed
    assert "test_auth" not in engine.evidence_state.verified_preservation_invariants
    assert "test_init" in engine.evidence_state.verified_preservation_invariants
    assert "test_speed" in engine.evidence_state.verified_preservation_invariants


def test_faz94_hybrid_exocortex_pgvector_bq_popcnt():
    exocortex = Faz94HybridExocortexMemoryEngine()

    # 1. 1-Bit Binary Quantization verification
    float_vec_a = [0.8, -0.4, 0.1, -0.9, 0.5]
    bq_a = exocortex.binary_quantize(float_vec_a)
    assert bq_a == "10101"

    float_vec_b = [0.7, -0.2, -0.3, -0.8, 0.6]  # bit 2 differs (0 vs 1)
    bq_b = exocortex.binary_quantize(float_vec_b)
    assert bq_b == "10001"

    # 2. POPCNT Hamming distance
    h_dist = exocortex.popcnt_hamming_distance(bq_a, bq_b)
    assert h_dist == 1

    # 3. Two-stage search
    exocortex.insert_semantic_memory(
        doc_id="mem_1",
        text="Single-Writer Boundary enforces developer-only code mutation.",
        embedding=[0.9, -0.1, 0.5, -0.8, 0.7],
        category="architecture",
        wikilinks=["[[Single-Writer Boundary]]", "[[HoH]]"]
    )
    exocortex.insert_semantic_memory(
        doc_id="mem_2",
        text="Obsidian daily notes capture session execution traces.",
        embedding=[-0.8, 0.7, -0.6, 0.2, -0.5],
        category="exocortex",
        wikilinks=["[[DailyNotes]]"]
    )

    query_vec = [0.85, -0.15, 0.45, -0.75, 0.65]  # Very close to mem_1
    top_hits = exocortex.hybrid_two_stage_search(query_vec, top_k=2)

    assert len(top_hits) >= 1
    assert top_hits[0]["id"] == "mem_1"
    assert top_hits[0]["cosine_sim"] > 0.95
    assert "[[HoH]]" in top_hits[0]["wikilinks"]

    # 4. Obsidian daily trace logging
    trace_res = exocortex.append_obsidian_daily_trace(
        agent_name="EntropyMasterOS",
        action="Validated pgvector 0.8+ POPCNT BQ search",
        tokens_consumed=180
    )
    assert "EntropyMasterOS" in trace_res["line"]
    assert "ΔTokens: 180" in trace_res["line"]


def test_faz94_token_physics_apc_context_engineering():
    token_eng = Faz94TokenPhysicsContextEngine()

    # 1. Automatic Prefix Caching (APC) Prompt Layout
    prompt_res = token_eng.construct_apc_optimized_prompt(
        system_directive="You are an autonomous SWE agent operating with HoH invariants.",
        tool_metadata_index=[
            {"name": "freeze_candidate", "description": "Locks code artifact as immutable"},
            {"name": "apply_mutation", "description": "Writes code enforcing Single-Writer Boundary"}
        ],
        project_invariants=[
            "Single-Writer Boundary: Only Developer role mutates files",
            "100% Pytest pass rate required before merge"
        ],
        volatile_user_query="Execute step 3 of order routing refactor"
    )

    assert prompt_res["estimated_kv_cache_hit_ratio"] > 0.70
    assert prompt_res["ttft_speedup_factor"] > 3.0
    assert "### SYSTEM DIRECTIVES" in prompt_res["full_prompt"]
    assert "### AVAILABLE TOOLS" in prompt_res["full_prompt"]
    assert prompt_res["full_prompt"].endswith("Execute step 3 of order routing refactor")

    # 2. Code-as-Action vs JSON Tool Calling Token Calculator
    savings = token_eng.calculate_code_as_action_savings(num_steps=6, avg_step_tokens=500)
    assert savings["json_tool_calling_tokens"] == 3000
    assert savings["code_as_action_tokens"] == 550
    assert savings["percent_savings"] > 80.0

    # 3. Delta Token Accounting
    current_usage = {"input_tokens": 15000, "output_tokens": 4200, "total_tokens": 19200}
    previous_usage = {"input_tokens": 12500, "output_tokens": 3400, "total_tokens": 15900}
    delta = token_eng.compute_delta_tokens(current_usage, previous_usage)

    assert delta["delta_input"] == 2500
    assert delta["delta_output"] == 800
    assert delta["delta_total"] == 3300


def test_faz94_master_autonomous_agent_os_integration():
    os_engine = Faz94MasterAutonomousAgentOS(project_name="AutonomousAlpha")

    # 1. Start mission with preservation invariants
    mission = os_engine.start_mission(
        mission_id="mission_101",
        initial_files={"core.py": "class Alpha: pass"},
        preservation_invariants=["test_core_exists", "test_schema_valid"]
    )
    assert mission["status"] == "DEVELOPMENT_ACTIVE"
    assert mission["iteration"] == 1

    # 2. Developer applies mutation
    mut = os_engine.execute_developer_mutation(
        mission_id="mission_101",
        file_path="core.py",
        new_content="class Alpha:\n    def compute(self): return 42"
    )
    assert mut["status"] == "MUTATION_APPLIED"

    # 3. Freeze and execute independent QA
    qa_results = os_engine.freeze_and_run_qa(
        mission_id="mission_101",
        test_suite_results={
            "test_core_exists": True,
            "test_schema_valid": True,
            "test_alpha_compute": True
        }
    )
    assert qa_results["freeze"]["status"] == "CANDIDATE_FROZEN"
    assert qa_results["qa"]["verdict"] == "PASSED"
    assert "test_alpha_compute" in qa_results["qa"]["newly_verified"]
    assert len(qa_results["qa"]["regressions"]) == 0
