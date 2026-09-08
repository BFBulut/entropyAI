"""
Automated Test Suite for Faz 98: 2026 Comprehensive Autonomous Agent Architecture.
Validates 100% programmatic pass rate across:
1. Faz98AgentHarnessRuntime (FSM lifecycle, AST pre-flight, zero-loss checkpoint, Windows taskkill failover).
2. Faz98AgentDesksWorkspaceManager (Git worktree isolation, AST windowed context curation, eviction).
3. Faz98SwarmProjectOrchestrator (DAG tasks, Single-Writer boundary, candidate freezing, shadow QA, test-gated merge).
4. Faz98A2AProtocolInteroperabilityEngine (Linux Foundation/Google A2A spec, agent-card.json, Opacity principle, JSON-RPC 2.0).
5. Faz98CognitiveExocortexManager (MRL 256-d truncation, 1-bit BQ POPCNT Hamming, iterative index scan, dreaming, MemFS).
6. Faz98TokenPhysicsContextEconomizer (CodeAct 65-85% savings, RadixAttention KV cache, progressive SKILL.md disclosure, delta tokens).
7. Faz98MasterAutonomousEngine (Complete unified bootstrap and end-to-end coordination).
"""

import math
import pytest
from entropy.tools.autonomous_agent_architecture import (
    TaskContract,
    TaskFSMState,
    Faz98AgentHarnessRuntime,
    Faz98AgentDesksWorkspaceManager,
    Faz98SwarmProjectOrchestrator,
    Faz98A2AProtocolInteroperabilityEngine,
    Faz98CognitiveExocortexManager,
    Faz98TokenPhysicsContextEconomizer,
    Faz98MasterAutonomousEngine,
)


def test_faz98_agent_harness_runtime():
    harness = Faz98AgentHarnessRuntime(agent_id="test_worker_harness")
    task = TaskContract(task_id="task_harness_01", spec_path="specs/task.md")

    # 1. Bind task & transition FSM
    bind_res = harness.bind_task(task, worker_pid=8844)
    assert bind_res["status"] == "BOUND"
    assert bind_res["fsm_state"] == "IN_PROGRESS"
    assert bind_res["worker_pid"] == 8844
    assert task.state == TaskFSMState.IN_PROGRESS

    # 2. Pre-flight AST validation with valid code
    orig_code = "def calculate():\n    return 42\n"
    patch_code = "def calculate():\n    # optimized\n    return 42 * 2\n"
    valid_res = harness.execute_with_preflight_guardrail(orig_code, patch_code, 1, 2)
    assert valid_res["success"] is True
    assert valid_res["valid_syntax"] is True
    assert "return 42 * 2" in valid_res["synthesized_code"]

    # 3. Pre-flight AST validation catching syntax error before disk
    broken_patch = "def broken(:\n    pass\n"
    broken_res = harness.execute_with_preflight_guardrail(orig_code, broken_patch, 1, 2)
    assert broken_res["success"] is False
    assert broken_res["valid_syntax"] is False
    assert "Pre-flight AST SyntaxError" in broken_res["error"]

    # 4. Zero-loss checkpointing
    chk = harness.create_zero_loss_checkpoint("Pre-rotation checkpoint", {"active_step": 12, "vars": {"acc": 99}})
    assert chk["sha256"] is not None
    assert len(chk["sha256"]) == 64
    assert len(harness.checkpoints) == 1

    # 5. Failover to fresh worker with Windows process tree kill command
    failover = harness.failover_to_fresh_worker(target_agent_id="test_worker_beta")
    assert failover["status"] == "FAILOVER_EXECUTED"
    assert failover["source_agent_id"] == "test_worker_harness"
    assert failover["target_agent_id"] == "test_worker_beta"
    assert "taskkill /F /T /PID 8844" in failover["windows_process_kill_cmd"]
    assert failover["preserved_task_id"] == "task_harness_01"


def test_faz98_agent_desks_workspace_manager():
    mgr = Faz98AgentDesksWorkspaceManager(repo_path="c:/EntropiAI")

    # 1. Allocate Git Worktree Desk
    desk = mgr.allocate_worktree_desk(agent_id="dev_agent_01", purpose="feature_refactor")
    assert desk["branch_name"] == "desks/desk_dev_agent_01"
    assert "git worktree add -b desks/desk_dev_agent_01" in desk["git_worktree_command"]

    # 2. Stage file with AST windowed context slicing
    large_file_content = "\n".join([f"line_{i} = {i}" for i in range(1, 401)]) + "\ndef target_function():\n    return 'hit'\n" + "\n".join([f"tail_{j} = {j}" for j in range(1, 101)])
    staged = mgr.stage_file_on_context_desk(
        agent_id="dev_agent_01",
        file_path="src/large_module.py",
        full_content=large_file_content,
        focus_symbol="target_function",
        max_viewport_lines=100
    )
    assert staged["tokens_staged"] < 1000
    assert staged["compression_ratio"] > 0.60
    assert staged["desk_total_tokens"] > 0
    assert staged["total_lines"] > 450

    # 3. Evict file from context desk
    evict_res = mgr.evict_from_context_desk("dev_agent_01", "src/large_module.py")
    assert evict_res["status"] == "EVICTED"
    assert evict_res["remaining_tokens"] == 0

    # 4. Deallocate desk
    dealloc = mgr.deallocate_desk("dev_agent_01")
    assert dealloc["status"] == "DEALLOCATED"
    assert "git worktree remove --force" in dealloc["prune_command"]


def test_faz98_swarm_project_orchestrator():
    orch = Faz98SwarmProjectOrchestrator(project_name="AutonomousAlpha")

    # 1. Register DAG tasks
    orch.register_task_node("t1", "Design Specification", [])
    orch.register_task_node("t2", "Implement Code", ["t1"])
    assert len(orch.task_dag) == 2

    # 2. Single-Writer Boundary enforcement
    assert orch.acquire_single_writer_lock("dev_agent") is True
    assert orch.acquire_single_writer_lock("hacker_agent") is False  # Refused: already locked
    assert orch.release_single_writer_lock("dev_agent") is True
    assert orch.acquire_single_writer_lock("hacker_agent") is True

    # 3. Candidate Freezing with SHA-256
    code_bundle = {"main.py": "print('hello world')", "config.json": "{}"}
    cand = orch.freeze_candidate_snapshot("hacker_agent", code_bundle)
    assert cand["status"] == "FROZEN"
    assert len(cand["sha256"]) == 64

    # 4. Adversarial Shadow QA Desk evaluation (Success case)
    def passing_qa_suite(bundle):
        return {"all_passed": True, "pass_rate": 1.0, "total_tests": 10, "failed_tests": []}

    qa_verdict = orch.dispatch_to_shadow_qa_desk(cand["candidate_id"], "shadow_qa_agent", passing_qa_suite)
    assert qa_verdict["all_passed"] is True
    assert qa_verdict["pass_rate"] == 1.0

    # 5. Test-Gated Merge
    merge_res = orch.evaluate_test_gated_merge(cand["candidate_id"])
    assert merge_res["verdict"] == "MERGED_SUCCESS"
    assert merge_res["action"] == "ATOMIC_MERGE_COMMITTED"
    assert len(orch.released_snapshots) == 1

    # 6. Test-Gated Rollback on failure
    broken_cand = orch.freeze_candidate_snapshot("hacker_agent", {"broken.py": "syntax error"})
    def failing_qa_suite(bundle):
        return {"all_passed": False, "pass_rate": 0.5, "total_tests": 4, "failed_tests": ["test_syntax"]}

    orch.dispatch_to_shadow_qa_desk(broken_cand["candidate_id"], "shadow_qa_agent", failing_qa_suite)
    rollback_res = orch.evaluate_test_gated_merge(broken_cand["candidate_id"])
    assert rollback_res["verdict"] == "ROLLBACK_TRIGGERED"
    assert rollback_res["action"] == "RESTORE_PREVIOUS_STABLE_SNAPSHOT"


def test_faz98_a2a_protocol_interoperability_engine():
    engine = Faz98A2AProtocolInteroperabilityEngine(agent_id="entropy_supervisor")

    # 1. Generate standard agent-card.json
    card = engine.generate_agent_card(
        name="Entropy Code Architect",
        description="Specialist subagent in code analysis and refactoring",
        capabilities=["ast_parsing", "git_worktree", "test_synthesis"],
        supported_tools=["read_file", "write_file"],
        endpoint_url="stdio://sandbox"
    )
    assert card["spec_version"] == "1.0.0-a2a"
    assert card["agent_id"] == "entropy_supervisor"
    assert "ast_parsing" in card["capabilities"]

    # 2. Dispatch A2A task enforcing Opacity Principle
    task_payload = {"repo": "EntropyAI", "file": "engine.py"}
    inner_cot = "Thinking: First examine AST, then plan diff, ensure backward compatibility..."
    msg = engine.dispatch_a2a_task(
        target_agent_id="code_architect_worker",
        task_name="Refactor AST Parser",
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

    completed_reg = engine.update_task_lifecycle(task_id, "COMPLETED", {"output_file": "engine_refactored.py"})
    assert completed_reg["state"] == "COMPLETED"
    assert completed_reg["result"]["output_file"] == "engine_refactored.py"


def test_faz98_cognitive_exocortex_manager():
    exocortex = Faz98CognitiveExocortexManager(agent_id="test_exocortex")

    # 1. Matryoshka Representation Learning (MRL) truncation & L2 normalization
    raw_vec = [float(i) for i in range(1, 385)]
    mrl_vec = exocortex.matryoshka_truncate_and_normalize(raw_vec, target_dim=256)
    assert len(mrl_vec) == 256
    norm = math.sqrt(sum(x * x for x in mrl_vec))
    assert pytest.approx(norm, 0.001) == 1.0

    # 2. 1-Bit Binary Quantization (BQ) & Hamming POPCNT distance
    v1 = [0.5, -0.2, 0.9, -0.8]
    v2 = [0.1, -0.4, -0.5, -0.9]
    b1 = exocortex.binary_quantize_vector(v1)
    b2 = exocortex.binary_quantize_vector(v2)
    assert b1 == "1010"
    assert b2 == "1000"
    ham_dist = exocortex.hamming_distance_popcnt(b1, b2)
    assert ham_dist == 1

    # 3. Iterative Index Scan bypasses Recall Cliff
    candidates = [
        {"id": "doc1", "metadata": {"lang": "py", "topic": "finance"}},
        {"id": "doc2", "metadata": {"lang": "js", "topic": "ui"}},
        {"id": "doc3", "metadata": {"lang": "py", "topic": "finance"}},
        {"id": "doc4", "metadata": {"lang": "cpp", "topic": "core"}},
        {"id": "doc5", "metadata": {"lang": "py", "topic": "finance"}}
    ]
    matched = exocortex.iterative_index_scan_filter(candidates, {"lang": "py", "topic": "finance"}, top_k=2)
    assert len(matched) == 2
    assert matched[0]["id"] == "doc1"
    assert matched[1]["id"] == "doc3"

    # 4. Ebbinghaus Sleep-Time Dreaming consolidation
    episodes = [
        {"id": "ep1", "content": "Crucial architecture discovery", "importance": 0.95, "surprise_score": 0.85, "access_count": 5},
        {"id": "ep2", "content": "Routine ping output", "importance": 0.1, "surprise_score": 0.1, "access_count": 1}
    ]
    dream_res = exocortex.run_ebbinghaus_dreaming(episodes)
    assert dream_res["status"] == "DREAMING_COMPLETE"
    assert dream_res["consolidated_count"] == 1
    assert dream_res["forgotten_count"] == 1
    assert dream_res["consolidated_insights"][0]["id"] == "ep1"

    # 5. Letta MemFS Core Memory commits
    commit = exocortex.update_memfs_block("persona", "Updated Autonomous Persona", "Updated persona instructions")
    assert commit["status"] == "MEMFS_COMMITTED"
    assert exocortex.memfs_blocks["persona"] == "Updated Autonomous Persona"
    assert len(exocortex.memfs_commit_log) >= 2


def test_faz98_token_physics_context_economizer():
    econ = Faz98TokenPhysicsContextEconomizer()

    # 1. CodeAct vs JSON Tool Calling
    json_tools = [
        {"tool": "query_db", "result": [{"id": i, "val": i * 10} for i in range(50)]},
        {"tool": "filter_results", "result": [{"id": i, "val": i * 10} for i in range(25)]}
    ]
    codeact_script = "res = [x for x in db.query() if x.val > 200]; print(len(res))"
    savings = econ.compare_codeact_vs_json(json_tools, codeact_script)
    assert savings["json_tool_tokens"] > savings["codeact_tokens"]
    assert savings["tokens_saved"] > 0
    assert savings["savings_percentage"] > 60.0
    assert savings["context_rot_prevented"] is True

    # 2. RadixAttention KV-Cache Prefix Sharing
    radix = econ.estimate_radix_attention_savings(system_prompt_tokens=4000, shared_history_tokens=1000, num_subagents=4)
    assert radix["kv_tokens_saved"] > 10000
    assert radix["cache_hit_rate"] > 70.0

    # 3. Progressive Skill Disclosure
    skills = [
        {"name": "git_mgr", "description": "Manages git branches", "full_instructions": "X" * 1200},
        {"name": "test_runner", "description": "Runs test suites", "full_instructions": "Y" * 1500},
        {"name": "db_migrator", "description": "Runs migrations", "full_instructions": "Z" * 1800}
    ]
    prog = econ.evaluate_progressive_skill_disclosure(skills, invoked_skill_name="test_runner")
    assert prog["tokens_saved"] > 500
    assert prog["savings_percentage"] > 50.0

    # 4. Delta Token Accounting
    prev_cum = {"input": 15000, "output": 2500}
    curr_cum = {"input": 16200, "output": 2950}
    delta = econ.calculate_delta_turn_tokens(prev_cum, curr_cum)
    assert delta["delta_input_tokens"] == 1200
    assert delta["delta_output_tokens"] == 450
    assert delta["delta_total_tokens"] == 1650

    # 5. Session Rotation Sentinel
    assert econ.check_session_rotation_trigger(10, 18)["should_rotate"] is False
    assert econ.check_session_rotation_trigger(19, 18)["should_rotate"] is True


def test_faz98_master_autonomous_engine_integration():
    engine = Faz98MasterAutonomousEngine(project_name="EntropyProduction_Faz98")
    bootstrap = engine.bootstrap_autonomous_workspace()

    assert bootstrap["status"] == "BOOTSTRAPPED_FAZ98"
    assert bootstrap["project_name"] == "EntropyProduction_Faz98"
    assert bootstrap["agent_card"]["spec_version"] == "1.0.0-a2a"
    assert "desks/desk_harness_EntropyProduction_Faz98" in bootstrap["allocated_desk"]
    assert len(bootstrap["subsystems_ready"]) == 6
