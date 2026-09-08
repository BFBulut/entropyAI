"""
Automated Test Suite for Faz 99: 2026 Comprehensive Autonomous Agent Architecture.
Validates 100% programmatic pass rate across:
1. Faz99ContextEngineeringHarness (FSM lifecycle, AST pre-flight, zero-loss checkpoint, Windows taskkill failover).
2. Faz99AgentDesksWorkspaceManager (Git worktree isolation, AST windowed context curation, eviction).
3. Faz99SwarmProjectOrchestrator (DAG tasks, Single-Writer boundary, candidate freezing, shadow QA, test-gated merge).
4. Faz99AAIFProtocolInteroperabilityEngine (Linux Foundation/Google A2A v1.1, agent-card.json, Opacity principle, FastMCP SEP-1865 Apps).
5. Faz99CognitiveExocortexManager (MRL 256-d truncation, 1-bit BQ POPCNT Hamming, Late Chunking, iterative scan, dreaming, MemFS).
6. Faz99TokenPhysicsContextEconomizer (CodeAct 65-85% savings, RadixAttention KV cache, progressive SKILL.md disclosure, delta tokens).
7. Faz99MasterAutonomousEngine (Complete unified bootstrap and end-to-end coordination).
"""

import math
import pytest
from entropy.tools.autonomous_agent_architecture import (
    TaskContract,
    TaskFSMState,
    Faz99ContextEngineeringHarness,
    Faz99AgentDesksWorkspaceManager,
    Faz99SwarmProjectOrchestrator,
    Faz99AAIFProtocolInteroperabilityEngine,
    Faz99CognitiveExocortexManager,
    Faz99TokenPhysicsContextEconomizer,
    Faz99MasterAutonomousEngine,
)


def test_faz99_context_engineering_harness():
    harness = Faz99ContextEngineeringHarness(agent_id="test_worker_harness_faz99")
    task = TaskContract(task_id="task_harness_faz99", spec_path="specs/task.md")

    # 1. Bind task & transition FSM
    bind_res = harness.bind_task(task, worker_pid=9911)
    assert bind_res["status"] == "BOUND"
    assert bind_res["fsm_state"] == "IN_PROGRESS"
    assert bind_res["worker_pid"] == 9911
    assert task.state == TaskFSMState.IN_PROGRESS

    # 2. Pre-flight AST validation with valid code
    orig_code = "def process():\n    return 'initial'\n"
    patch_code = "def process():\n    # enhanced\n    return 'updated'\n"
    valid_res = harness.execute_with_preflight_guardrail(orig_code, patch_code, 1, 2)
    assert valid_res["success"] is True
    assert valid_res["valid_syntax"] is True
    assert "return 'updated'" in valid_res["synthesized_code"]

    # 3. Pre-flight AST validation catching syntax error before disk
    broken_patch = "def broken(:\n    return\n"
    broken_res = harness.execute_with_preflight_guardrail(orig_code, broken_patch, 1, 2)
    assert broken_res["success"] is False
    assert broken_res["valid_syntax"] is False
    assert "Pre-flight AST SyntaxError" in broken_res["error"]

    # 4. Zero-loss checkpointing
    chk = harness.create_zero_loss_checkpoint("Pre-rotation checkpoint", {"active_step": 15, "state": "OPTIMAL"})
    assert chk["sha256"] is not None
    assert len(chk["sha256"]) == 64
    assert len(harness.checkpoints) == 1

    # 5. Failover to fresh worker with Windows process tree kill command
    failover = harness.failover_to_fresh_worker(target_agent_id="test_worker_omega")
    assert failover["status"] == "FAILOVER_EXECUTED"
    assert failover["source_agent_id"] == "test_worker_harness_faz99"
    assert failover["target_agent_id"] == "test_worker_omega"
    assert "taskkill /F /T /PID 9911" in failover["windows_process_kill_cmd"]
    assert failover["preserved_task_id"] == "task_harness_faz99"


def test_faz99_agent_desks_workspace_manager():
    mgr = Faz99AgentDesksWorkspaceManager(repo_path="c:/EntropiAI")

    # 1. Allocate Git Worktree Desk
    desk = mgr.allocate_worktree_desk(agent_id="dev_agent_faz99", purpose="core_enhancement")
    assert desk["branch_name"] == "desks/desk_dev_agent_faz99"
    assert "git worktree add -b desks/desk_dev_agent_faz99" in desk["git_worktree_command"]

    # 2. Stage file with AST windowed context slicing
    large_file_content = "\n".join([f"var_{i} = {i}" for i in range(1, 401)]) + "\ndef critical_handler():\n    return True\n" + "\n".join([f"end_{j} = {j}" for j in range(1, 101)])
    staged = mgr.stage_file_on_context_desk(
        agent_id="dev_agent_faz99",
        file_path="src/critical_module.py",
        full_content=large_file_content,
        focus_symbol="critical_handler",
        max_viewport_lines=120
    )
    assert staged["tokens_staged"] < 1000
    assert staged["compression_ratio"] > 0.60
    assert staged["desk_total_tokens"] > 0
    assert staged["total_lines"] > 450

    # 3. Evict file from context desk
    evict_res = mgr.evict_from_context_desk("dev_agent_faz99", "src/critical_module.py")
    assert evict_res["status"] == "EVICTED"
    assert evict_res["remaining_tokens"] == 0

    # 4. Deallocate desk
    dealloc = mgr.deallocate_desk("dev_agent_faz99")
    assert dealloc["status"] == "DEALLOCATED"
    assert "git worktree remove --force" in dealloc["prune_command"]


def test_faz99_swarm_project_orchestrator():
    orch = Faz99SwarmProjectOrchestrator(project_name="AutonomousFaz99")

    # 1. Register DAG tasks
    orch.register_task_node("task_spec", "Architecture Spec", [])
    orch.register_task_node("task_code", "Core Implementation", ["task_spec"])
    assert len(orch.task_dag) == 2

    # 2. Single-Writer Boundary enforcement
    assert orch.acquire_single_writer_lock("dev_specialist") is True
    assert orch.acquire_single_writer_lock("qa_agent") is False  # Refused: already locked
    assert orch.release_single_writer_lock("dev_specialist") is True
    assert orch.acquire_single_writer_lock("qa_agent") is True

    # 3. Candidate Freezing with SHA-256
    bundle = {"engine.py": "def run(): pass", "manifest.json": "{}"}
    cand = orch.freeze_candidate_snapshot("dev_specialist", bundle)
    assert cand["status"] == "FROZEN"
    assert len(cand["sha256"]) == 64

    # 4. Adversarial Shadow QA Desk evaluation (Success case)
    def passing_qa_suite(b):
        return {"all_passed": True, "pass_rate": 1.0, "total_tests": 12, "failed_tests": []}

    qa_verdict = orch.dispatch_to_shadow_qa_desk(cand["candidate_id"], "shadow_qa_sentinel", passing_qa_suite)
    assert qa_verdict["all_passed"] is True
    assert qa_verdict["pass_rate"] == 1.0

    # 5. Test-Gated Merge
    merge_res = orch.evaluate_test_gated_merge(cand["candidate_id"])
    assert merge_res["verdict"] == "MERGED_SUCCESS"
    assert merge_res["action"] == "ATOMIC_MERGE_COMMITTED"
    assert len(orch.released_snapshots) == 1

    # 6. Test-Gated Rollback on failure
    broken_cand = orch.freeze_candidate_snapshot("dev_specialist", {"fail.py": "raise Exception"})
    def failing_qa_suite(b):
        return {"all_passed": False, "pass_rate": 0.25, "total_tests": 4, "failed_tests": ["test_fail"]}

    orch.dispatch_to_shadow_qa_desk(broken_cand["candidate_id"], "shadow_qa_sentinel", failing_qa_suite)
    rollback_res = orch.evaluate_test_gated_merge(broken_cand["candidate_id"])
    assert rollback_res["verdict"] == "ROLLBACK_TRIGGERED"
    assert rollback_res["action"] == "RESTORE_PREVIOUS_STABLE_SNAPSHOT"


def test_faz99_aaif_protocol_interoperability_engine():
    engine = Faz99AAIFProtocolInteroperabilityEngine(agent_id="entropy_supervisor_faz99")

    # 1. Generate standard agent-card.json
    card = engine.generate_agent_card(
        name="Entropy Core Supervisor",
        description="Master coordinating agent under AAIF standards",
        capabilities=["context_engineering", "ast_validation", "swarm_orchestration"],
        supported_tools=["stage_context", "freeze_candidate", "merge_gatekeeper"],
        endpoint_url="stdio://sandbox"
    )
    assert card["spec_version"] == "1.1.0-a2a"
    assert card["agent_id"] == "entropy_supervisor_faz99"
    assert "context_engineering" in card["capabilities"]
    assert card["security"]["opacity_guarantee"] is True

    # 2. Dispatch A2A task enforcing Opacity Principle
    task_payload = {"action": "refactor", "target": "core.py"}
    inner_cot = "Private thinking: Validate dependencies first, check typing..."
    msg = engine.dispatch_a2a_task(
        target_agent_id="worker_coder",
        task_name="Perform Refactoring",
        payload=task_payload,
        internal_cot=inner_cot,
        enforce_opacity=True
    )
    assert msg["jsonrpc"] == "2.0"
    assert msg["params"]["opacity_enforced"] is True
    assert msg["params"]["tokens_saved_via_opacity"] > 0
    assert "__unfiltered_cot" not in msg["params"]["payload"]

    # 3. Task lifecycle progression
    task_id = msg["id"]
    reg = engine.update_task_lifecycle(task_id, "WORKING")
    assert reg["state"] == "WORKING"

    completed_reg = engine.update_task_lifecycle(task_id, "COMPLETED", {"files_touched": ["core.py"]})
    assert completed_reg["state"] == "COMPLETED"
    assert completed_reg["result"]["files_touched"] == ["core.py"]

    # 4. FastMCP SEP-1865 MCP Apps UI manifest
    ui_manifest = engine.generate_mcp_app_ui_manifest(
        app_id="app_metrics_faz99",
        title="Agent Performance Metrics",
        component_type="PrefabMetricCard",
        data_payload={"qps": 450, "token_savings_pct": 82.5}
    )
    assert ui_manifest["jsonrpc"] == "2.0"
    assert ui_manifest["params"]["component"] == "PrefabMetricCard"
    assert ui_manifest["params"]["context_tax_eliminated"] is True


def test_faz99_cognitive_exocortex_manager():
    exocortex = Faz99CognitiveExocortexManager(agent_id="test_exocortex_faz99")

    # 1. Matryoshka Representation Learning (MRL) truncation & L2 normalization
    raw_vec = [float(i) for i in range(1, 385)]
    mrl_vec = exocortex.matryoshka_truncate_and_normalize(raw_vec, target_dim=256)
    assert len(mrl_vec) == 256
    norm = math.sqrt(sum(x * x for x in mrl_vec))
    assert pytest.approx(norm, 0.001) == 1.0

    # 2. 1-Bit Binary Quantization (BQ) & Hamming POPCNT distance
    v1 = [0.8, -0.1, 0.5, -0.4]
    v2 = [0.2, -0.9, -0.3, -0.1]
    b1 = exocortex.binary_quantize_vector(v1)
    b2 = exocortex.binary_quantize_vector(v2)
    assert b1 == "1010"
    assert b2 == "1000"
    ham_dist = exocortex.hamming_distance_popcnt(b1, b2)
    assert ham_dist == 1

    # 3. Jina AI Late Chunking simulation
    doc = "Sentence one of global architecture. Sentence two continues context. Sentence three concludes paragraph."
    late_chunks = exocortex.simulate_late_chunking(doc, chunk_size=5, overlap=2)
    assert len(late_chunks) >= 2
    assert late_chunks[0]["context_cliff_prevented"] is True
    assert late_chunks[0]["global_context_signature"] == late_chunks[1]["global_context_signature"]

    # 4. Iterative Index Scan bypasses Recall Cliff
    candidates = [
        {"id": "docA", "metadata": {"lang": "py", "domain": "agentic"}},
        {"id": "docB", "metadata": {"lang": "ts", "domain": "ui"}},
        {"id": "docC", "metadata": {"lang": "py", "domain": "agentic"}},
        {"id": "docD", "metadata": {"lang": "rs", "domain": "core"}},
        {"id": "docE", "metadata": {"lang": "py", "domain": "agentic"}}
    ]
    matched = exocortex.iterative_index_scan_filter(candidates, {"lang": "py", "domain": "agentic"}, top_k=2)
    assert len(matched) == 2
    assert matched[0]["id"] == "docA"
    assert matched[1]["id"] == "docC"

    # 5. Ebbinghaus Sleep-Time Dreaming consolidation
    episodes = [
        {"id": "ep_high", "content": "Master architectural invariant", "importance": 0.9, "surprise_score": 0.8, "access_count": 4},
        {"id": "ep_low", "content": "Routine keep-alive heartbeat", "importance": 0.1, "surprise_score": 0.1, "access_count": 1}
    ]
    dream_res = exocortex.run_ebbinghaus_dreaming(episodes)
    assert dream_res["status"] == "DREAMING_COMPLETE"
    assert dream_res["consolidated_count"] == 1
    assert dream_res["forgotten_count"] == 1
    assert dream_res["consolidated_insights"][0]["id"] == "ep_high"

    # 6. Letta MemFS Core Memory commits
    commit = exocortex.update_memfs_block("persona", "Faz99 Autonomous Persona", "Updated to Faz99 standards")
    assert commit["status"] == "MEMFS_COMMITTED"
    assert exocortex.memfs_blocks["persona"] == "Faz99 Autonomous Persona"
    assert len(exocortex.memfs_commit_log) >= 2


def test_faz99_token_physics_context_economizer():
    econ = Faz99TokenPhysicsContextEconomizer()

    # 1. CodeAct vs JSON Tool Calling
    json_tools = [
        {"tool": "fetch_records", "result": [{"id": i, "score": i * 5} for i in range(60)]},
        {"tool": "filter_high_scores", "result": [{"id": i, "score": i * 5} for i in range(30)]}
    ]
    codeact_script = "high_scores = [r for r in db.get_records() if r.score > 150]; print(len(high_scores))"
    savings = econ.compare_codeact_vs_json(json_tools, codeact_script)
    assert savings["json_tool_tokens"] > savings["codeact_tokens"]
    assert savings["tokens_saved"] > 0
    assert savings["savings_percentage"] > 60.0
    assert savings["context_rot_prevented"] is True

    # 2. RadixAttention KV-Cache Prefix Sharing
    radix = econ.estimate_radix_attention_savings(system_prompt_tokens=4500, shared_history_tokens=1200, num_subagents=5)
    assert radix["kv_tokens_saved"] > 15000
    assert radix["cache_hit_rate"] > 60.0

    # 3. Progressive Skill Disclosure
    skills = [
        {"name": "git_controller", "description": "Controls git worktrees", "full_instructions": "A" * 1500},
        {"name": "test_validator", "description": "Runs validation suites", "full_instructions": "B" * 2000},
        {"name": "ast_parser", "description": "Performs ast operations", "full_instructions": "C" * 2500}
    ]
    prog = econ.evaluate_progressive_skill_disclosure(skills, invoked_skill_name="test_validator")
    assert prog["tokens_saved"] > 800
    assert prog["savings_percentage"] > 50.0

    # 4. Delta Token Accounting
    prev_cum = {"input": 20000, "output": 4000}
    curr_cum = {"input": 21800, "output": 4650}
    delta = econ.calculate_delta_turn_tokens(prev_cum, curr_cum)
    assert delta["delta_input_tokens"] == 1800
    assert delta["delta_output_tokens"] == 650
    assert delta["delta_total_tokens"] == 2450

    # 5. Session Rotation Sentinel
    assert econ.check_session_rotation_trigger(12, 18)["should_rotate"] is False
    assert econ.check_session_rotation_trigger(18, 18)["should_rotate"] is True


def test_faz99_master_autonomous_engine_integration():
    engine = Faz99MasterAutonomousEngine(project_name="EntropyProduction_Faz99")
    bootstrap = engine.bootstrap_autonomous_workspace()

    assert bootstrap["status"] == "BOOTSTRAPPED_FAZ99"
    assert bootstrap["project_name"] == "EntropyProduction_Faz99"
    assert bootstrap["agent_card"]["spec_version"] == "1.1.0-a2a"
    assert "desk_harness_EntropyProduction_Faz99" in bootstrap["allocated_desk"]
    assert len(bootstrap["subsystems_ready"]) == 6
