"""
Automated Test Suite for Faz 104: 2026 Frontier Autonomous Agent Architecture & Cognitive OS Suite
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import pytest
from src.entropy.tools.autonomous_agent_architecture import TaskContract, TaskFSMState
from src.entropy.tools.autonomous_agent_architecture_faz104 import (
    Faz104AdaptiveHarnessEngineering,
    DSPySignature,
    DSPyAssertion,
    Faz104AgentDesksProjectGovernor,
    DeskRole,
    AgentDesk,
    Faz104AAIFProtocolHub,
    MemoryBlock,
    Faz104CognitiveExocortexSubstrate,
    Faz104TokenPhysicsContextEconomizer,
    Faz104MasterAutonomousEngine,
)


def test_faz104_adaptive_harness_and_dspy_assertions():
    harness = Faz104AdaptiveHarnessEngineering(agent_id="test_harness_104")
    contract = TaskContract(task_id="task_test_104", spec_path="specs/test_104.md")

    # 1. Bind task
    res_bind = harness.bind_task(contract, worker_pid=8820)
    assert res_bind["status"] == "BOUND"
    assert res_bind["fsm_state"] == "IN_PROGRESS"
    assert res_bind["worker_pid"] == 8820

    # 2. Invariant registration & verification
    harness.register_invariants(["inv_type_check", "inv_sandbox_boundary"])
    inv_res = harness.verify_invariants({"inv_type_check": True, "inv_sandbox_boundary": True})
    assert inv_res["all_invariants_preserved"] is True
    inv_fail = harness.verify_invariants({"inv_type_check": True, "inv_sandbox_boundary": False})
    assert inv_fail["all_invariants_preserved"] is False
    assert "inv_sandbox_boundary" in inv_fail["regressions"]

    # 3. Fault localization via AST
    codebase = {
        "src/auth.py": "class TokenManager:\n    def verify_token(self, tok: str):\n        return True\n",
        "src/api.py": "def handle_route(): pass\n"
    }
    loc = harness.locate_fault(codebase, "verify_token")
    assert loc["status"] == "LOCALIZED"
    assert loc["candidate_count"] == 1
    assert loc["candidates"][0]["file"] == "src/auth.py"
    assert loc["candidates"][0]["symbol"] == "verify_token"

    # 4. AST Pre-flight checks
    safe_code = {"src/safe.py": "def compute(x: int) -> int:\n    return x * 10\n"}
    pre_safe = harness.validate_ast_preflight(safe_code)
    assert pre_safe["preflight_passed"] is True
    assert pre_safe["file_results"]["src/safe.py"]["status"] == "AST_VALID"

    unsafe_code = {"src/unsafe.py": "def run_command(c):\n    exec(c)\n"}
    pre_unsafe = harness.validate_ast_preflight(unsafe_code)
    assert pre_unsafe["preflight_passed"] is False
    assert pre_unsafe["file_results"]["src/unsafe.py"]["status"] == "SECURITY_VIOLATION"

    # 5. Merkle Candidate Freezing
    frozen = harness.freeze_candidate_patch("patch_104", {"src/safe.py": "def compute(x: int) -> int: return x * 10\n"})
    assert frozen["status"] == "CANDIDATE_FROZEN"
    assert "merkle_root" in frozen

    # 6. Process Tree Watchdog
    term = harness.terminate_process_tree()
    assert term["status"] == "TERMINATION_PREPARED"
    assert "taskkill /F /T /PID 8820" in term["command"]

    # 7. DSPy 2.5/2.6 Declarative Signatures & Runtime Assertions
    sig = harness.register_dspy_signature("CodeRefactor", ["source_code", "spec"], ["patched_code", "tests"])
    assert sig.name == "CodeRefactor"
    assert "source_code" in sig.inputs

    # Register assertions
    harness.register_dspy_assertion(
        assertion_id="assert_non_empty_patch",
        condition_fn=lambda out: len(out.get("patched_code", "").strip()) > 0,
        failure_message="Refactored code patch cannot be empty."
    )
    harness.register_dspy_assertion(
        assertion_id="assert_docstring_present",
        condition_fn=lambda out: '"""' in out.get("patched_code", ""),
        failure_message="Refactored code must contain docstrings."
    )

    # Test passing output
    passing_output = {"patched_code": '"""Module docstring"""\ndef ok(): pass\n'}
    res_pass = harness.evaluate_dspy_assertions(passing_output)
    assert res_pass["all_assertions_passed"] is True
    assert res_pass["requires_refinement"] is False

    # Test failing output triggering backtracking guidance
    failing_output = {"patched_code": ""}
    res_fail = harness.evaluate_dspy_assertions(failing_output)
    assert res_fail["all_assertions_passed"] is False
    assert res_fail["requires_refinement"] is True
    assert "assert_non_empty_patch" in res_fail["failed_assertion_ids"]
    assert len(res_fail["backtracking_guidance"]) == 2


def test_faz104_agent_desks_project_governor():
    gov = Faz104AgentDesksProjectGovernor()

    # 1. Single-Writer Boundary (SWB)
    assert gov.check_write_permission("desk_developer") is True
    assert gov.check_write_permission("desk_shadow_qa") is False
    assert gov.check_write_permission("desk_architect") is False
    assert gov.check_write_permission("desk_orchestrator") is False
    assert gov.check_write_permission("desk_verifier") is False

    # 2. DAG Task Registration & Kahn's Topological Order
    gov.register_task("task_01", "Architecture Blueprint", prerequisites=[])
    gov.register_task("task_02", "Developer Implementation", prerequisites=["task_01"])
    gov.register_task("task_03", "Adversarial QA Suite", prerequisites=["task_01"])
    gov.register_task("task_04", "Integration Verification", prerequisites=["task_02", "task_03"])

    batches = gov.get_topological_execution_order()
    assert len(batches) == 3
    assert batches[0] == ["task_01"]
    assert sorted(batches[1]) == ["task_02", "task_03"]
    assert batches[2] == ["task_04"]

    # Cyclic DAG detection
    gov_cycle = Faz104AgentDesksProjectGovernor()
    gov_cycle.register_task("t1", "Task 1", prerequisites=["t2"])
    gov_cycle.register_task("t2", "Task 2", prerequisites=["t1"])
    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        gov_cycle.get_topological_execution_order()

    # 3. Inner Progress Ledger Logging
    gov.log_progress("desk_developer", "task_02", "CompileAST", "AST validated successfully", success=True)
    assert len(gov.inner_progress_ledger) == 1
    assert gov.inner_progress_ledger[0]["action"] == "CompileAST"

    # 4. Test-Gated Merge & Rollback Sentinel
    # Non-writer attempts merge -> denied
    perm_denied = gov.test_gated_merge("desk_shadow_qa", "task_02", 1.0)
    assert perm_denied["status"] == "PERMISSION_DENIED"

    # Developer fails 2 times
    f1 = gov.test_gated_merge("desk_developer", "task_02", 0.75)
    assert f1["status"] == "MERGE_BLOCKED"
    assert f1["consecutive_failures"] == 1

    f2 = gov.test_gated_merge("desk_developer", "task_02", 0.90)
    assert f2["status"] == "MERGE_BLOCKED"
    assert f2["consecutive_failures"] == 2

    # 3rd failure triggers Rollback Sentinel
    f3 = gov.test_gated_merge("desk_developer", "task_02", 0.80)
    assert f3["status"] == "ROLLBACK_TRIGGERED"
    assert f3["rollback_info"]["action"] == "WORKTREE_HARD_RESET"
    assert "git -C .desks/developer reset --hard" in f3["rollback_info"]["command"]

    # Passing test (100%) merges successfully
    pass_res = gov.test_gated_merge("desk_developer", "task_01", 1.0)
    assert pass_res["status"] == "MERGE_APPROVED"
    assert pass_res["test_pass_rate"] == 1.0


def test_faz104_aaif_protocol_and_mcp_hub():
    hub = Faz104AAIFProtocolHub()

    # 1. Google A2A v1.1 Agent Card publishing
    card = hub.publish_agent_card("entropy_dev", "Entropy Developer Agent", ["codeact", "ast_patch", "unit_test"])
    assert card["agent_id"] == "entropy_dev"
    assert "signature_hash" in card
    assert len(card["signature_hash"]) == 64

    # 2. The Opacity Principle: Strip internal CoT/thought
    raw_msg = {
        "sender": "entropy_dev",
        "recipient": "entropy_qa",
        "thinking": "I think we should refactor module X because Y",
        "thought": "Internal scratchpad",
        "content": "<thought>Secret CoT reasoning</thought>Ready for QA validation.",
        "payload": {"diff": "--- a\n+++ b"}
    }
    sanitized = hub.enforce_opacity_principle(raw_msg)
    assert "thinking" not in sanitized
    assert "thought" not in sanitized
    assert "<thought>" not in sanitized["content"]
    assert sanitized["content"] == "Ready for QA validation."
    assert sanitized["opacity_enforced"] is True

    # 3. MCP 2026 Handling: Server-side sampling is deprecated
    sampling_req = {
        "jsonrpc": "2.0",
        "method": "sampling/createMessage",
        "params": {"messages": [{"role": "user", "content": "hello"}]},
        "id": 101
    }
    sampling_res = hub.handle_mcp_request(sampling_req)
    assert "error" in sampling_res
    assert sampling_res["error"]["code"] == -32601
    assert "Server-side sampling is deprecated" in sampling_res["error"]["message"]

    # 4. MCP 2026 Asynchronous Task Handling
    async_req = {
        "jsonrpc": "2.0",
        "method": "tools/callAsync",
        "params": {"name": "run_long_benchmark", "arguments": {"iterations": 100}},
        "id": 102
    }
    async_res = hub.handle_mcp_request(async_req)
    assert async_res["result"]["status"] == "ACCEPTED"
    assert len(async_res["result"]["task_id"]) == 64


def test_faz104_cognitive_exocortex_and_letta_memfs():
    substrate = Faz104CognitiveExocortexSubstrate()

    # 1. Letta MemFS Memory Blocks & Commits
    assert "persona" in substrate.memory_blocks
    assert "human" in substrate.memory_blocks
    assert "task" in substrate.memory_blocks

    up_res = substrate.update_memory_block("persona", "Entropy AI: 2026 Supercharged OS", commit_message="Upgraded persona")
    assert up_res["status"] == "COMMITTED"
    assert len(up_res["commit_hash"]) == 12
    assert len(substrate.memfs_history) == 1

    # 2. Shannon Surprise calculation
    surp_rare = substrate.compute_shannon_surprise(0.01)
    surp_common = substrate.compute_shannon_surprise(0.90)
    assert surp_rare > 6.0  # High surprise > 4.0
    assert surp_common < 0.2

    # 3. 1-Bit Binary Quantization (BQ) and POPCNT Hamming Distance
    v1 = [0.8, -0.5, 0.2, -0.1]
    v2 = [0.9, -0.4, -0.3, -0.2]  # bit 3 differs
    bq1 = substrate.quantize_1bit_bq(v1)
    bq2 = substrate.quantize_1bit_bq(v2)
    assert bq1 == "1010"
    assert bq2 == "1000"
    dist = substrate.hamming_distance(bq1, bq2)
    assert dist == 1

    # 4. Supabase pgvector 0.8+ Iterative Hybrid Search
    substrate.insert_vector("doc_01", "Autonomous agent harness engineering in Python", [0.8, -0.5, 0.2, -0.1], metadata={"category": "harness"})
    substrate.insert_vector("doc_02", "Modern trading microstructures in finance", [-0.8, 0.5, -0.2, 0.1], metadata={"category": "finance"})
    substrate.insert_vector("doc_03", "Agent Desks single writer boundary protocols", [0.7, -0.4, 0.3, -0.2], metadata={"category": "harness"})

    search_res = substrate.iterative_hybrid_search(
        query_float=[0.8, -0.5, 0.2, -0.1],
        query_keywords=["harness", "agent"],
        top_k=2,
        filter_key="category",
        filter_val="harness"
    )
    assert len(search_res) == 2
    assert search_res[0]["doc_id"] == "doc_01"
    assert search_res[0]["metadata"]["category"] == "harness"

    # 5. Sleep-Time Compute Dreaming Consolidation
    dream_res = substrate.sleep_time_dreaming_consolidation()
    assert dream_res["status"] == "CONSOLIDATED"


def test_faz104_token_physics_and_context_economics():
    econ = Faz104TokenPhysicsContextEconomizer()

    # 1. Provider-side Prompt Caching Layout
    persona = "Entropy AI Orchestrator"
    tools = [{"name": "read_file", "parameters": {}}]
    invariants = ["Never hardcode models", "100% pytest pass rate"]
    user_msg = "Please refactor the memory module."
    layout = econ.compute_prompt_caching_layout(persona, tools, invariants, user_msg)

    assert "SYSTEM ROLE & INVARIANTS" in layout["cached_prefix"]
    assert layout["cache_breakpoint_index"] > 0
    assert layout["dynamic_suffix"] == user_msg
    assert layout["estimated_cache_hit_rate"] >= 0.80

    # 2. CodeAct 2.0 REPL Filter Simulation
    raw_log = [f"2026-09-05 INFO Connection heartbeat {i}" for i in range(1000)]
    raw_log.append("2026-09-05 CRITICAL SQLite database disk image is malformed")
    raw_log.append("2026-09-05 CRITICAL Process tree deadlock detected")

    filter_res = econ.simulate_codeact_filter(raw_log, "CRITICAL")
    assert filter_res["original_line_count"] == 1002
    assert filter_res["filtered_line_count"] == 2
    assert filter_res["token_savings_percent"] > 99.0

    # 3. Delta Token Accounting
    # Turn 1: cumulative 1500 in, 500 out
    d1 = econ.calculate_turn_delta(1500, 500)
    assert d1["delta_input"] == 1500
    assert d1["delta_output"] == 500

    # Turn 2: cumulative 3200 in, 900 out
    d2 = econ.calculate_turn_delta(3200, 900)
    assert d2["delta_input"] == 1700
    assert d2["delta_output"] == 400


def test_faz104_master_autonomous_engine_pipeline():
    engine = Faz104MasterAutonomousEngine(agent_id="test_engine_104")

    codebase = {
        "src/core.py": "def calculate_score(val):\n    return val * 1.5\n",
        "src/utils.py": "def helper(): pass\n"
    }
    patches = {
        "src/core.py": "def calculate_score(val: float) -> float:\n    \"\"\"Calculates optimized score.\"\"\"\n    return val * 1.75\n"
    }

    res = engine.run_end_to_end_pipeline(
        task_id="task_pipeline_104",
        title="Refactor Score Calculator",
        codebase=codebase,
        target_symbol="calculate_score",
        patches=patches
    )

    assert res["status"] == "PIPELINE_SUCCESS"
    assert res["task_id"] == "task_pipeline_104"
    assert res["fault_localization"]["status"] == "LOCALIZED"
    assert res["merkle_freeze"]["status"] == "CANDIDATE_FROZEN"
    assert res["merge_result"]["status"] == "MERGE_APPROVED"
    assert res["memfs_commit"]["status"] == "COMMITTED"
