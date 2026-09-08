"""
Automated Pytest Suite for Faz 73 Autonomous Agent Architecture Modules.
Tests:
1. AgentDeskLifecycleController (Worktree Provisioning, AST & Test Gatekeeping, Atomic Merge & Desk GC).
2. ContextCompactorAndSlidingWindow (Anchored Prefix Caching & Historical Compaction).
3. CognitiveMemoryRouter12Layer (12-Layer Unified Memory Intent Classification & Routing).
4. A2AArtifactValidator (Diff Parsing & Strict Artifact Passing Efficiency).
5. TokenEconomicsForensicEngine (Agentic Tax Analysis, RadixAttention & Diff ROI).
6. Full Integrated Faz 73 Autonomous Governance Pipeline.
"""

from pathlib import Path
import pytest
from entropy.tools.autonomous_agent_architecture import (
    AgentDeskLifecycleController,
    DeskExecutionResult,
    ContextCompactorAndSlidingWindow,
    CognitiveMemoryRouter12Layer,
    A2AArtifactValidator,
    TokenEconomicsForensicEngine,
    AgentCard,
    A2ANegotiationEngine,
    TaskContract,
    TaskFSMState,
)


def test_agent_desk_lifecycle_and_gatekeeping(tmp_path):
    controller = AgentDeskLifecycleController(root_repo_path=tmp_path)

    # 1. Provision desk
    desk = controller.provision_desk(task_id="task_audit_42", agent_id="CodeArchitect")
    assert desk.name == "desk_task_audit_42"
    assert desk.branch == "agent/task_audit_42"
    assert desk.is_active is True

    # 2. Test AST Failure Gatekeeping (Rollback triggered)
    broken_code = {
        "src/broken.py": "def broken_syntax(:\n    pass"
    }
    result_ast_fail = controller.execute_and_gatekeep(
        desk_name="desk_task_audit_42",
        task_id="task_audit_42",
        modified_files=broken_code,
        run_tests_func=lambda: True
    )
    assert result_ast_fail.status == "ROLLBACK"
    assert result_ast_fail.ast_verified is False
    assert "AST gatekeeping failed" in result_ast_fail.error_message

    # 3. Test Unit Test Failure Gatekeeping (Rollback triggered)
    valid_syntax_code = {
        "src/feature.py": "def add(a: int, b: int) -> int:\n    return a + b\n"
    }
    result_test_fail = controller.execute_and_gatekeep(
        desk_name="desk_task_audit_42",
        task_id="task_audit_42",
        modified_files=valid_syntax_code,
        run_tests_func=lambda: False  # Simulated test failure
    )
    assert result_test_fail.status == "ROLLBACK"
    assert result_test_fail.ast_verified is True
    assert result_test_fail.tests_passed is False

    # 4. Test Success Path (AST verified + Tests pass)
    result_success = controller.execute_and_gatekeep(
        desk_name="desk_task_audit_42",
        task_id="task_audit_42",
        modified_files=valid_syntax_code,
        run_tests_func=lambda: True  # Passing tests
    )
    assert result_success.status == "SUCCESS"
    assert result_success.ast_verified is True
    assert result_success.tests_passed is True
    assert result_success.patch_checksum is not None
    assert "--- src/feature.py" in result_success.diff_content

    # 5. Merge and GC
    merge_info = controller.merge_and_gc_desk(desk_name="desk_task_audit_42")
    assert merge_info["status"] == "MERGED"
    assert merge_info["gc_completed"] is True
    assert len(controller.desk_manager.list_desks()) == 0


def test_context_compactor_and_sliding_window():
    compactor = ContextCompactorAndSlidingWindow()

    system_prompt = "You are Entropy AI, an autonomous OS orchestrator."
    tool_schemas = "Available tools: [read_file, write_file, run_bash, a2a_delegate]"
    project_spec = "# Spec: Implement SOTA Agent Desks and Token Forensics"

    # Create 10 turns of history
    history = [
        {"role": "user", "content": f"User query message turn {i} with some detailed context description."}
        if i % 2 == 0 else
        {"role": "assistant", "content": f"Assistant response turn {i} executing tool actions and reasoning."}
        for i in range(10)
    ]

    partition = compactor.partition_and_compact(
        system_prompt=system_prompt,
        tool_schemas=tool_schemas,
        project_spec=project_spec,
        history_turns=history,
        sliding_window_turns=4
    )

    # Prefix must be anchored
    assert system_prompt in partition.anchored_prefix
    assert tool_schemas in partition.anchored_prefix
    assert project_spec in partition.anchored_prefix

    # Older turns (10 - 4 = 6 turns) must be compacted
    assert "### Compacted Historical Context" in partition.compacted_summary
    assert len(partition.recent_turns) == 4

    # KV-Cache ratio should be positive and bounded
    assert partition.cached_prefix_tokens > 0
    assert 0.0 < partition.cache_hit_ratio <= 1.0


def test_cognitive_memory_router_12_layer():
    router = CognitiveMemoryRouter12Layer()

    # Test Identity intent
    route_id = router.route_query("Sen kimsin ve temel ego direktifin nedir?")
    assert route_id["detected_intent"] == "identity"
    assert "L12_EGO_CORE" in route_id["primary_layers"]

    # Test Episodic intent
    route_ep = router.route_query("Dün saat 14:00'te hangi görevleri tamamlamıştık?")
    assert route_ep["detected_intent"] == "episodic"
    assert "L4_SHORT_TERM_BUFFER" in route_ep["primary_layers"]
    assert route_ep["ebbinghaus_filtering_required"] is True

    # Test Holistic intent
    route_hol = router.route_query("Sistem mimarisinin genel özetini ve bileşen ilişkilerini göster.")
    assert route_hol["detected_intent"] == "holistic"
    assert "L8_LIGHTRAG_COMMUNITY" in route_hol["primary_layers"]
    assert route_hol["graph_expansion_required"] is True

    # Test Procedural intent
    route_proc = router.route_query("Pydantic-AI dynamic tool nasıl synthesize edilir ve kod yazılır?")
    assert route_proc["detected_intent"] == "procedural"
    assert "L1_SCRATCHPAD" in route_proc["primary_layers"]


def test_a2a_artifact_validator():
    validator = A2AArtifactValidator()

    # Valid unified diff
    valid_diff = (
        "--- a/src/main.py\n"
        "+++ b/src/main.py\n"
        "@@ -10,4 +10,4 @@\n"
        "-old_call()\n"
        "+new_call()\n"
    )
    val_res = validator.validate_diff_artifact(valid_diff)
    assert val_res["valid"] is True
    assert val_res["hunk_count"] == 1
    assert val_res["sha256"] is not None

    # Invalid diff missing markers
    invalid_diff = "Just some random text without diff headers."
    invalid_res = validator.validate_diff_artifact(invalid_diff)
    assert invalid_res["valid"] is False
    assert "Malformed diff" in invalid_res["error"]

    # Artifact Passing Token Efficiency
    chat_text = (
        "Hey agent! I looked at the file and on line 10 there is old_call(). "
        "We should replace that with new_call() because the new API deprecated old_call. "
        "Let me know if you can make that change or if you need more context on why we did it."
    )
    compact_art = "- L10: Replace old_call() with new_call() [API deprecation]"
    eff = validator.calculate_artifact_passing_efficiency(
        natural_language_chat=chat_text,
        structured_artifact=compact_art
    )
    assert eff["reduction_percent"] > 60.0
    assert eff["efficiency_ratio"] > 2.0


def test_token_economics_forensic_engine():
    engine = TokenEconomicsForensicEngine()

    roi = engine.evaluate_architecture_roi(
        turns=15,
        files_edited=4,
        avg_file_size_tokens=2000,
        avg_diff_size_tokens=120,
        system_tools_tokens=3500,
        active_skill_tokens=400,
        total_skills_count=25
    )

    # Verify significant token savings (>75%)
    assert roi["savings_percent"] > 75.0
    assert roi["compression_factor"] > 3.0
    assert roi["naive_total_tokens"] > roi["optimized_total_tokens"]
    assert roi["cost_saved_usd"] > 0.0
    assert "3.5x" in roi["estimated_latency_speedup"]


def test_full_integrated_faz73_governance_pipeline(tmp_path):
    # 1. Route task memory query
    router = CognitiveMemoryRouter12Layer()
    route = router.route_query("Otonom ajan desk ve worktree yaşam döngüsü mimarisi")
    assert route["detected_intent"] in ["holistic", "procedural"]

    # 2. Compact context and anchor prefix
    compactor = ContextCompactorAndSlidingWindow()
    partition = compactor.partition_and_compact(
        system_prompt="System Directive: Faz 73 Autonomous Governance",
        tool_schemas="[tool_provision_desk, tool_run_tests, tool_merge_patch]",
        project_spec="Full automated worktree pipeline",
        history_turns=[{"role": "user", "content": "Init task"}, {"role": "assistant", "content": "Acknowledged"}],
        sliding_window_turns=5
    )
    assert partition.cache_hit_ratio > 0.50

    # 3. Agent Desk lifecycle execution
    controller = AgentDeskLifecycleController(root_repo_path=tmp_path)
    desk = controller.provision_desk(task_id="task_faz73_pipeline")
    assert desk.is_active is True

    valid_files = {
        "src/governor.py": "def run_governance():\n    return {'status': 'healthy'}\n"
    }
    exec_result = controller.execute_and_gatekeep(
        desk_name=desk.name,
        task_id="task_faz73_pipeline",
        modified_files=valid_files,
        run_tests_func=lambda: True
    )
    assert exec_result.status == "SUCCESS"

    # 4. A2A artifact verification
    validator = A2AArtifactValidator()
    val_diff = validator.validate_diff_artifact(exec_result.diff_content)
    assert val_diff["valid"] is True

    # 5. Merge and GC desk
    merge_out = controller.merge_and_gc_desk(desk.name)
    assert merge_out["status"] == "MERGED"
    assert merge_out["gc_completed"] is True
