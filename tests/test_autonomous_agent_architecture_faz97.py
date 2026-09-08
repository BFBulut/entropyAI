"""
Unit tests for Faz 97 Autonomous Agent Architecture.
Validates:
1. Faz97CodeActREPLSandbox (Safe execution, variable export, AST pre-flight, and token comparison).
2. Faz97LettaMemFSAgentOS (Core memory blocks, MemFS commits, Ebbinghaus dreaming consolidation, rollback).
3. Faz97OpenHandsEventStreamController (Action-Observation lifecycle, delegation, event replay).
4. Faz97FastMCPAppsPrefabEngine (Prefab data tables, metric cards, action forms, and MCP app payload).
5. Faz97MultiAgentACICoordinator (100-line windowed code viewports, patch pre-flight syntax validation).
6. Faz97MasterAutonomousAgentSystem (Unified orchestration of all Faz 97 subsystems).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    Faz97CodeActREPLSandbox,
    Faz97LettaMemFSAgentOS,
    Faz97OpenHandsEventStreamController,
    Faz97FastMCPAppsPrefabEngine,
    Faz97MultiAgentACICoordinator,
    Faz97MasterAutonomousAgentSystem
)


def test_faz97_codeact_repl_sandbox_and_token_efficiency():
    sandbox = Faz97CodeActREPLSandbox()

    # 1. Valid Python Code execution with stdout & exported locals
    code_snippet = """
numbers = [1, 2, 3, 4, 5, 10, 20]
even_sum = sum(x for x in numbers if x % 2 == 0)
print(f"Calculated sum of evens: {even_sum}")
"""
    result = sandbox.execute_code(code_snippet)
    assert result["success"] is True
    assert "Calculated sum of evens: 36" in result["stdout"]
    assert result["exported_locals"]["even_sum"] == 36
    assert result["error"] is None
    assert result["codeact_mode"] == "PYTHON_REPL"

    # 2. Syntax Error detection in sandbox
    broken_code = "def invalid_syntax(: pass"
    broken_result = sandbox.execute_code(broken_code)
    assert broken_result["success"] is False
    assert "SyntaxError" in broken_result["error"]

    # 3. Token efficiency comparison: JSON Tool calling vs CodeAct
    json_payloads = [
        {"tool": "fetch_users", "args": {"limit": 100}},
        {"tool": "filter_active", "args": {"status": "active"}},
        {"tool": "sum_balances", "args": {"field": "wallet_balance"}},
        {"tool": "generate_report", "args": {"format": "summary"}}
    ]
    codeact_script = """
users = fetch_users(100)
active = [u for u in users if u['status'] == 'active']
total = sum(u['wallet_balance'] for u in active)
print(total)
"""
    eff = sandbox.compare_token_efficiency(json_payloads, codeact_script)
    assert eff["json_tool_calling_tokens"] > eff["codeact_python_tokens"]
    assert eff["tokens_saved"] > 0
    assert eff["savings_percentage"] > 20.0
    assert eff["eliminates_context_rot"] is True


def test_faz97_letta_memfs_agent_os_and_dreaming():
    os_engine = Faz97LettaMemFSAgentOS(agent_id="test_agent")

    # 1. Core memory blocks & commits
    assert "persona" in os_engine.core_memory
    edit_res = os_engine.edit_core_memory("persona", "Updated Super Agent Persona", "Update persona block")
    assert edit_res["status"] == "UPDATED"
    assert edit_res["new_value"] == "Updated Super Agent Persona"
    assert len(os_engine.memfs_commits) == 2

    # Append to block
    append_res = os_engine.append_core_memory("persona", "Specialized in High-Speed Arbitrage")
    assert "Specialized in High-Speed Arbitrage" in os_engine.core_memory["persona"]
    assert len(os_engine.memfs_commits) == 3

    # 2. Record recall events
    e1 = os_engine.record_recall_event(
        event_type="RESEARCH",
        content="Discovered new subagent worktree isolation pattern preventing .git index locks",
        importance=0.9,
        surprise_score=0.85
    )
    e2 = os_engine.record_recall_event(
        event_type="TRIVIAL",
        content="Agent executed benign ls command with 0 outputs",
        importance=0.1,
        surprise_score=0.1
    )
    assert len(os_engine.recall_memory) == 2

    # 3. Agent Dreaming Consolidation
    dream_res = os_engine.run_dreaming_consolidation(decay_rate=0.01, surprise_threshold=0.6)
    assert dream_res["dreaming_status"] == "CONSOLIDATED"
    assert dream_res["consolidated_count"] == 1  # only e1 passes threshold
    assert dream_res["forgotten_count"] == 1     # e2 pruned
    assert len(os_engine.archival_memory) == 1
    assert "Discovered new subagent worktree" in os_engine.archival_memory[0]["insight"]

    # 4. MemFS Rollback to initial baseline
    first_commit = os_engine.memfs_commits[0]["commit_id"]
    rollback_res = os_engine.memfs_rollback(first_commit)
    assert rollback_res["status"] == "ROLLED_BACK"
    assert rollback_res["restored_commit_id"] == first_commit
    assert "Autonomous Agentic Operating System" in os_engine.core_memory["persona"]


def test_faz97_openhands_event_stream_and_delegation():
    controller = Faz97OpenHandsEventStreamController()

    # 1. Emit Action
    act1 = controller.emit_action(
        agent_id="planner_agent",
        action_type="FileSearchAction",
        payload={"query": "test_*.py"}
    )
    assert act1["step"] == 1
    assert act1["kind"] == "ACTION"
    assert act1["agent_id"] == "planner_agent"

    # 2. Emit Observation
    obs1 = controller.emit_observation(
        action_event_id=act1["event_id"],
        observation_type="FileSearchObservation",
        content=["test_a.py", "test_b.py"]
    )
    assert obs1["step"] == 2
    assert obs1["kind"] == "OBSERVATION"
    assert obs1["caused_by_action"] == act1["event_id"]

    # 3. Delegate Task
    del_act = controller.delegate_task(
        parent_agent="planner_agent",
        target_agent="coder_agent",
        subtask_description="Implement FastMCP endpoint for metrics",
        context_slice={"files": ["test_a.py"]}
    )
    assert del_act["action_type"] == "AgentDelegateAction"
    assert "coder_agent" in controller.active_delegates

    # 4. Event Replay
    replay = controller.get_event_replay(start_step=1)
    assert len(replay) == 3
    assert replay[0]["step"] == 1
    assert replay[2]["action_type"] == "AgentDelegateAction"


def test_faz97_fastmcp_apps_prefab_engine():
    engine = Faz97FastMCPAppsPrefabEngine()

    # 1. Prefab Data Table
    table = engine.create_prefab_data_table(
        title="Agent Worktrees Status",
        columns=["Desk ID", "Agent", "Branch", "Status"],
        rows=[
            ["desk_alpha", "developer_alpha", "desks/alpha", "ACTIVE"],
            ["desk_beta", "developer_beta", "desks/beta", "IDLE"]
        ]
    )
    assert table["component"] == "PrefabDataTable"
    assert table["row_count"] == 2
    assert table["render_target"] == "io.modelcontextprotocol/ui"

    # 2. Prefab Metric Card
    card = engine.create_prefab_metric_card(
        label="Token Savings (CodeAct)",
        value="74.2%",
        change_pct=15.4,
        status="success"
    )
    assert card["component"] == "PrefabMetricCard"
    assert card["value"] == "74.2%"
    assert card["status"] == "success"

    # 3. Prefab Action Form
    form = engine.create_prefab_action_form(
        form_id="merge_approval_form",
        title="Approve Branch Merge",
        fields=[{"name": "branch", "type": "string"}, {"name": "confirm", "type": "boolean"}],
        submit_endpoint="/api/merge"
    )
    assert form["component"] == "PrefabActionForm"
    assert form["form_id"] == "merge_approval_form"

    # 4. Standard MCP App Payload
    app_payload = engine.render_mcp_app_payload(
        uri="ui://entropy/worktrees",
        prefabs=[table, card, form],
        raw_data={"total_desks": 2}
    )
    assert app_payload["uri"] == "ui://entropy/worktrees"
    assert len(app_payload["prefabs"]) == 3
    assert "<div class='mcp-app'" in app_payload["html_fallback"]
    assert app_payload["supported_protocol"] == "io.modelcontextprotocol/ui"


def test_faz97_multi_agent_aci_coordinator():
    coord = Faz97MultiAgentACICoordinator()

    # 1. Code Viewport creation (100-line windowing)
    sample_code = "\n".join([f"line_{i} = {i} * 2" for i in range(1, 250)])
    viewport = coord.create_code_viewport(sample_code, start_line=1, window_size=100)

    assert viewport["start_line"] == 1
    assert viewport["end_line"] == 100
    assert viewport["total_lines"] == 249
    assert viewport["has_more"] is True
    assert viewport["next_start_line"] == 101
    assert "   1 | line_1 = 1 * 2" in viewport["viewport_content"]
    assert " 100 | line_100 = 100 * 2" in viewport["viewport_content"]

    # 2. Patch Pre-Flight validation (AST syntax checks)
    orig_script = "def calculate():\n    return 42\n"
    valid_patch = "def calculate():\n    val = 42\n    return val * 2\n"
    val_res = coord.validate_patch_pre_flight(orig_script, valid_patch, start_line=1, end_line=2)
    assert val_res["valid"] is True
    assert val_res["patch_applied_successfully"] is True

    # Invalid patch resulting in broken indentation / syntax
    invalid_patch = "def calculate():\nreturn broken"
    inval_res = coord.validate_patch_pre_flight(orig_script, invalid_patch, start_line=1, end_line=2)
    assert inval_res["valid"] is False
    assert "SyntaxError" in inval_res["error"]


def test_faz97_master_autonomous_agent_system_integration():
    master = Faz97MasterAutonomousAgentSystem(project_name="EntropyAI_Production")
    init_res = master.initialize_faz97_environment()

    assert init_res["status"] == "INITIALIZED_FAZ97"
    assert init_res["project_name"] == "EntropyAI_Production"
    assert len(init_res["subsystems"]) == 5
    assert init_res["agent_os_commits"] >= 2
    assert init_res["event_stream_steps"] >= 2
