"""
Unit tests for Faz 91 Autonomous Agent Architecture.
Validates:
1. CodeAsActionEngine (CodeAct / smolagents code-as-action execution & MCP tax calculation).
2. CAIDWorktreeDeskManager (Git worktree desk allocation, test-gated merge gatekeeper, rollback sentinel).
3. ProgressiveDisclosureSkillRegistry (SKILL.md frontmatter parsing, on-demand hydration, token savings).
4. LettaCognitiveOperatingSystem (Hierarchical Core/Recall/Archival memory & sleep-time compute dreaming).
5. LLMLinguaTokenCompressor (Token classification distillation, keyword retention, compression ratio).
6. Faz91MasterAutonomousAgentOS (Full end-to-end mission orchestration).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    CodeAsActionEngine,
    CAIDWorktreeDeskManager,
    CAIDWorktreeDesk,
    ProgressiveDisclosureSkillRegistry,
    LettaCognitiveOperatingSystem,
    LLMLinguaTokenCompressor,
    Faz91MasterAutonomousAgentOS
)


def test_code_as_action_engine():
    engine = CodeAsActionEngine()

    # 1. Valid Python execution
    code = """
numbers = [1, 2, 3, 4, 5]
evens = [x for x in numbers if x % 2 == 0]
total = sum(evens)
"""
    res = engine.execute_code_block(code)
    assert res["status"] == "SUCCESS"
    assert res["output_vars"]["total"] == 6
    assert res["output_vars"]["evens"] == [2, 4]
    assert res["duration_ms"] >= 0.0

    # 2. Syntax/Runtime error handling (AST Pre-flight)
    bad_code = "def invalid_syntax(:"
    bad_res = engine.execute_code_block(bad_code)
    assert bad_res["status"] == "EXECUTION_ERROR"
    assert "SyntaxError" in bad_res["error"]

    # 3. CodeAct vs JSON Tool Calling comparison
    comp = engine.compare_codeact_vs_json_calling(
        num_steps=5, raw_payload_size_kb=20.0, num_tools_in_schema=15
    )
    assert comp["logic_step_reduction_pct"] == 80.0
    assert comp["token_savings_multiplier"] > 2.0
    assert comp["tokens_saved"] > 5000
    assert comp["context_rot_prevented"] is True


def test_caid_worktree_desk_manager():
    manager = CAIDWorktreeDeskManager(base_worktree_dir=".entropy/test_workspaces")

    # 1. Allocate Desk
    desk = manager.allocate_worktree_desk(task_id="task_91_abc123", agent_name="CoderAgent")
    assert desk.desk_id == "desk_CoderAgent_task_91_"
    assert "desk_CoderAgent" in desk.worktree_path
    assert desk.status == "ACTIVE"

    # 2. Test-Gated Merge Gatekeeper: Approval on 100% Pass Rate
    pass_results = {"pass_rate": 1.0, "exit_code": 0, "passed": 15}
    approved = manager.submit_worktree_work(
        desk_id=desk.desk_id,
        modified_files=["module_a.py", "module_b.py"],
        test_suite_result=pass_results
    )
    assert approved["verdict"] == "APPROVED"
    assert desk.status == "MERGE_APPROVED"
    assert len(manager.merge_history) == 1

    # 3. Test-Gated Merge Gatekeeper: Rollback on Failure
    desk2 = manager.allocate_worktree_desk(task_id="task_91_fail456", agent_name="BuggyAgent")
    fail_results = {"pass_rate": 0.8, "exit_code": 1, "passed": 8}
    rejected = manager.submit_worktree_work(
        desk_id=desk2.desk_id,
        modified_files=["broken.py"],
        test_suite_result=fail_results
    )
    assert rejected["verdict"] == "REJECTED_ROLLBACK"
    assert desk2.status == "ROLLBACK_TRIGGERED"

    # 4. Cleanup
    assert manager.cleanup_worktree(desk.desk_id) is True
    assert desk.status == "PRUNED"


def test_progressive_disclosure_skill_registry():
    registry = ProgressiveDisclosureSkillRegistry()

    # 1. Register Skills
    registry.register_skill(
        name="web_browser",
        description="Searches web pages and extracts content via HTTP/DOM.",
        full_instructions="Use CSS selectors or xpath to extract markdown text. Handle rate limiting gracefully.",
        scripts=["browse.py"],
        references=["api_spec.md"]
    )
    registry.register_skill(
        name="sql_analytics",
        description="Queries analytics databases and computes aggregates.",
        full_instructions="Enforce read-only transactions. Always use parameterized queries to prevent injection."
    )

    # 2. Phase 1: Progressive Summary
    summary = registry.get_system_prompt_skills_summary()
    assert "web_browser" in summary
    assert "sql_analytics" in summary
    assert "Enforce read-only transactions" not in summary  # Full instructions must NOT leak to system prompt!

    # 3. Phase 2: On-demand Hydration
    hydrated = registry.hydrate_skill("web_browser")
    assert hydrated["name"] == "web_browser"
    assert "Handle rate limiting gracefully" in hydrated["instructions"]
    assert hydrated["scripts"] == ["browse.py"]

    # 4. Token Savings Calculation
    savings = registry.compute_context_savings()
    assert savings["progressive_summary_tokens"] < savings["monolithic_full_tokens"]
    assert savings["savings_pct"] > 0.0


def test_letta_cognitive_operating_system():
    letta = LettaCognitiveOperatingSystem(initial_persona="Entropy AI Test Persona")

    # 1. Core Memory
    assert "Entropy AI Test Persona" in letta.core_memory["persona"]
    letta.update_core_memory_block("current_objective", "Execute Faz 91 validation")
    assert letta.core_memory["current_objective"] == "Execute Faz 91 validation"

    # 2. Recall Memory
    letta.record_recall_turn("user", "What is the agent harness?")
    letta.record_recall_turn("agent", "The harness is the runtime control plane.")
    letta.record_recall_turn("user", "How does CodeAct work?")
    assert len(letta.recall_memory) == 3

    # 3. Sleep-Time Compute Dreaming
    dream = letta.sleep_time_compute_dream(min_turns_to_consolidate=3)
    assert dream["status"] == "DREAM_CONSOLIDATION_COMPLETE"
    assert dream["turns_processed"] == 3
    assert len(letta.recall_memory) == 0  # Window reset
    assert len(letta.archival_memory) == 1

    # 4. Archival Search
    found = letta.search_archival_memory("harness agent")
    assert len(found) == 1
    assert "Consolidated Rule" in found[0]["content"]


def test_llmlingua_token_compressor():
    compressor = LLMLinguaTokenCompressor()

    raw_text = (
        "The system has executed the task and the status is success. "
        "Furthermore, we can observe that def calculate_metrics was called on line 42 "
        "and no error or failure was encountered during the entire operation."
    )

    comp = compressor.compress_text(raw_text, target_ratio=0.5)
    assert comp["original_tokens"] > comp["compressed_tokens"]
    assert comp["savings_pct"] > 0.0
    # Must preserve critical symbols
    assert "success" in comp["compressed_text"]
    assert "def" in comp["compressed_text"]
    assert "42" in comp["compressed_text"]


def test_faz91_master_autonomous_agent_os():
    system = Faz91MasterAutonomousAgentOS()

    # 1. Successful mission execution
    res = system.execute_faz91_autonomous_mission(
        mission_id="mission_91_alpha",
        goal="Develop and test the new CodeAct module",
        agent_name="MasterArchitect",
        python_action_code="values = [10, 20, 30]; total = sum(values)",
        raw_log_output="Running pytest: 15 passed in 0.12s. status: success.",
        simulate_test_pass=True
    )
    assert res["status"] == "FAZ91_MISSION_COMPLETE"
    assert res["desk_telemetry"]["merge_verdict"] == "APPROVED"
    assert res["code_as_action"]["action_status"] == "SUCCESS"
    assert res["token_compression"]["savings_pct"] >= 0.0
    assert res["letta_cognitive_os"]["dream_status"] == "DREAM_CONSOLIDATION_COMPLETE"

    # 2. Failed test mission triggering rollback
    fail_res = system.execute_faz91_autonomous_mission(
        mission_id="mission_91_beta",
        goal="Develop feature with failing tests",
        agent_name="JuniorWorker",
        python_action_code="x = 100",
        simulate_test_pass=False
    )
    assert fail_res["status"] == "FAZ91_MISSION_ROLLBACK"
    assert fail_res["desk_telemetry"]["merge_verdict"] == "REJECTED_ROLLBACK"
