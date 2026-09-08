"""
Unit tests for Faz 93 Autonomous Agent Architecture.
Validates:
1. Faz93SupervisorTreeEngine (Erlang/OTP Let-It-Crash, restart strategies, state hydration).
2. Faz93BiTemporalKnowledgeGraph (Graphiti-style bi-temporal validity, fact invalidation, point-in-time query).
3. Faz93MCPAppsSEP1865Engine (SEP-1865 _meta.ui.resourceUri, ui:// interactive render).
4. Faz93SandboxedAgentDesk (WASM / WASI 0.2 sandbox policies, security syscall blocking).
5. Faz93TokenPhysicsLLMLinguaAndFSM (LLMLingua-2 prompt compression & FSM grammar decoding).
6. Faz93MasterAutonomousAgentOS (Full mission integration with sandboxing, recovery, and UI rendering).
"""

import time
import pytest
from entropy.tools.autonomous_agent_architecture import (
    Faz93SupervisorTreeEngine,
    SupervisionStrategy,
    Faz93BiTemporalKnowledgeGraph,
    Faz93MCPAppsSEP1865Engine,
    Faz93SandboxedAgentDesk,
    WASMSandboxPolicy,
    Faz93TokenPhysicsLLMLinguaAndFSM,
    Faz93MasterAutonomousAgentOS
)


def test_faz93_supervisor_tree_engine():
    engine = Faz93SupervisorTreeEngine(strategy=SupervisionStrategy.ONE_FOR_ONE, max_restarts=2)

    # 1. Register workers
    w1 = engine.register_worker("worker_alpha", "architect", {"last_file": "main.py"})
    w2 = engine.register_worker("worker_beta", "coder", {"last_test": "test_app.py"})
    assert w1.status == "HEALTHY"
    assert w2.status == "HEALTHY"

    # 2. Worker Alpha crashes and recovers (One-For-One: only Alpha restarts)
    rec1 = engine.handle_worker_crash("worker_alpha", "ContextWindowOverflow")
    assert rec1["status"] == "WORKER_RECOVERED"
    assert rec1["restarted_workers"] == ["worker_alpha"]
    assert "last_file" in rec1["hydrated_state_keys"]
    assert w1.restart_count == 1
    assert w1.status == "HEALTHY"

    # 3. Exceed max restarts -> TERMINATED and escalation
    engine.handle_worker_crash("worker_alpha", "MemoryLeak")
    esc = engine.handle_worker_crash("worker_alpha", "SegmentationFault")
    assert esc["status"] == "SUPERVISOR_FAILURE"
    assert esc["reason"] == "MAX_RESTARTS_EXCEEDED"
    assert w1.status == "TERMINATED"

    # 4. Strategy: REST_FOR_ONE
    rest_engine = Faz93SupervisorTreeEngine(strategy=SupervisionStrategy.REST_FOR_ONE)
    rest_engine.register_worker("node_1", "planner")
    rest_engine.register_worker("node_2", "executor")
    rest_engine.register_worker("node_3", "verifier")

    res_rest = rest_engine.handle_worker_crash("node_2", "ToolTimeout")
    assert res_rest["restarted_workers"] == ["node_2", "node_3"]


def test_faz93_bi_temporal_knowledge_graph():
    graph = Faz93BiTemporalKnowledgeGraph()

    t0 = 1000.0
    t1 = 2000.0
    t2 = 3000.0

    # Fact 1: Auth service runs on port 8080 at t0
    f1 = graph.assert_fact("AuthService", "runs_on_port", "8080", valid_time_start=t0)
    assert f1.valid_time_end is None

    # Query at t=1500 -> Port 8080
    q1 = graph.query_as_of("AuthService", "runs_on_port", 1500.0)
    assert q1 is not None
    assert q1.obj == "8080"

    # Fact 2: Auth service moved to port 9200 at t1 (invalidates Fact 1 from t1 onwards)
    f2 = graph.assert_fact("AuthService", "runs_on_port", "9200", valid_time_start=t1)
    assert f1.valid_time_end == t1
    assert f2.valid_time_end is None

    # Query at t=1500 -> Still 8080 (historic truth)
    assert graph.query_as_of("AuthService", "runs_on_port", 1500.0).obj == "8080"
    # Query at t=2500 -> Now 9200 (current truth)
    assert graph.query_as_of("AuthService", "runs_on_port", 2500.0).obj == "9200"

    # Fact evolution history
    history = graph.get_evolution_history("AuthService", "runs_on_port")
    assert len(history) == 2
    assert history[0]["obj"] == "8080" and history[0]["is_current"] is False
    assert history[1]["obj"] == "9200" and history[1]["is_current"] is True


def test_faz93_mcp_apps_sep1865_engine():
    engine = Faz93MCPAppsSEP1865Engine()

    # Register MCP App tool
    app = engine.register_mcp_app_tool(
        tool_name="live_git_diff_viewer",
        description="Interactive visual unified diff reviewer",
        resource_uri="ui://git/diff_viewer.html",
        ui_type="diff_review",
        dimensions=(1024, 768)
    )
    assert app.tool_name == "live_git_diff_viewer"

    # Check SEP-1865 descriptor structure
    desc = engine.build_tool_descriptor("live_git_diff_viewer")
    assert desc["_meta"]["ui"]["resourceUri"] == "ui://git/diff_viewer.html"
    assert desc["_meta"]["ui"]["type"] == "diff_review"
    assert desc["_meta"]["ui"]["dimensions"]["width"] == 1024

    # Execute app call
    render_res = engine.execute_app_call("live_git_diff_viewer", {"diff": "@@ -1,2 +1,2 @@"})
    assert render_res["status"] == "UI_RENDERED"
    assert render_res["ui_resource"] == "ui://git/diff_viewer.html"
    assert len(engine.rendered_ui_frames) == 1


def test_faz93_sandboxed_agent_desk():
    # Policy allowing read/write, blocking network
    policy = WASMSandboxPolicy(
        memory_limit_mb=64,
        allowed_syscalls={"read", "write", "exit"},
        network_egress=False
    )
    desk = Faz93SandboxedAgentDesk(desk_id="desk_sandboxed_01", policy=policy)

    # Clean execution
    res_clean = desk.execute_sandboxed_code("x = 1 + 1", requested_syscalls={"read", "write"})
    assert res_clean["success"] is True
    assert res_clean["telemetry"]["status"] == "EXECUTED_CLEAN"

    # Sandbox violation: Attempting unauthorized network egress socket syscall
    res_violation = desk.execute_sandboxed_code("import socket; s = socket.socket()", requested_syscalls={"socket", "connect"})
    assert res_violation["success"] is False
    assert "Security Violation" in res_violation["error"]
    assert len(desk.execution_audit_log) == 2


def test_faz93_token_physics_llmlingua_and_fsm():
    optimizer = Faz93TokenPhysicsLLMLinguaAndFSM()

    # 1. LLMLingua-2 Prompt Compression
    raw_prompt = "The quick brown fox is jumping over that lazy dog and this is in the park with a ball"
    comp_res = optimizer.compress_prompt_llmlingua2(raw_prompt, target_ratio=0.5)
    assert comp_res["reduction_pct"] > 0
    assert comp_res["compressed_tokens_approx"] < comp_res["original_tokens_approx"]
    assert comp_res["speedup_factor"] > 3.0

    # 2. FSM Grammar-Constrained Decoding
    target_schema = {"task_id", "status", "files_modified"}

    # Valid schema output
    valid_json = '{"task_id": "T93", "status": "COMPLETED", "files_modified": ["core.py"]}'
    eval_valid = optimizer.evaluate_fsm_grammar_decoding(target_schema, valid_json)
    assert eval_valid["valid"] is True
    assert eval_valid["schema_adherence_pct"] == 100.0
    assert eval_valid["tokens_saved_on_retries"] == 1500

    # Incomplete schema output
    incomplete_json = '{"task_id": "T93"}'
    eval_incomplete = optimizer.evaluate_fsm_grammar_decoding(target_schema, incomplete_json)
    assert eval_incomplete["valid"] is False
    assert "status" in eval_incomplete["missing_keys"]


def test_faz93_master_autonomous_agent_os():
    os_engine = Faz93MasterAutonomousAgentOS()

    # 1. Initialize mission
    init_res = os_engine.initialize_mission(
        mission_id="mission_faz93_alpha",
        worker_id="agent_titan",
        role="AutonomousRefactorAgent"
    )
    assert init_res["mission_id"] == "mission_faz93_alpha"
    assert init_res["worker_status"] == "HEALTHY"
    assert init_res["mcp_app_ready"] is True

    # 2. Execute Sandboxed Step (Success scenario)
    step_res = os_engine.execute_sandboxed_step(
        worker_id="agent_titan",
        code_action="def optimize(): return True",
        target_schema_keys={"result", "metrics"},
        simulated_json_output='{"result": "OPTIMIZED", "metrics": {"latency_ms": 12}}',
        requested_syscalls={"read", "write"}
    )
    assert step_res["step_status"] == "SUCCESS"
    assert step_res["fsm_eval"]["valid"] is True
    assert step_res["ui_rendered"] == "UI_RENDERED"

    # 3. Execute Sandboxed Step with Violation -> Triggers Supervisor Let-It-Crash Recovery
    step_violation = os_engine.execute_sandboxed_step(
        worker_id="agent_titan",
        code_action="os.system('curl http://malicious.site')",
        target_schema_keys={"result"},
        simulated_json_output='{"result": "FAIL"}',
        requested_syscalls={"connect", "sendto"}  # Blocked by default policy
    )
    assert step_violation["step_status"] == "FAILED_RECOVERED"
    assert "Security Violation" in step_violation["execution_error"]
    assert step_violation["supervisor_recovery"]["status"] == "WORKER_RECOVERED"
