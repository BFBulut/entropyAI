"""
Unit tests for Autonomous Agent Architecture Engine (Faz 66).
Validates Harness FSM, AST Pre-Flight, Zero-Loss Failover, AgentDesks,
ACP/A2A/MCP Protocols, HippoRAG 2 PPR & Ebbinghaus Hybrid Scoring,
and Radical Token Physics Calculators.
"""

import pytest
from pathlib import Path
import math

from entropy.tools.autonomous_agent_architecture import (
    TaskFSMState,
    TaskContract,
    ASTPreFlightVerifier,
    ZeroLossFailoverManager,
    AgentDeskManager,
    ProtocolTransformers,
    HippoRAG2Retriever,
    TokenPhysicsCalculator,
    SpecDrivenDAGScheduler,
    GenerativePRMVerifier,
    RadixAttentionSimulator,
)


def test_task_fsm_valid_transitions():
    task = TaskContract(task_id="task-101", spec_path="specs/auth.md")
    assert task.state == TaskFSMState.PENDING

    # PENDING -> IN_PROGRESS
    task.transition_to(TaskFSMState.IN_PROGRESS, reason="Agent picked up task")
    assert task.state == TaskFSMState.IN_PROGRESS
    assert len(task.history) == 1

    # IN_PROGRESS -> VERIFYING
    task.transition_to(TaskFSMState.VERIFYING, reason="Code completed, running tests")
    assert task.state == TaskFSMState.VERIFYING

    # VERIFYING -> COMPLETED
    task.transition_to(TaskFSMState.COMPLETED, reason="100% tests passed")
    assert task.state == TaskFSMState.COMPLETED

    # COMPLETED is terminal, cannot transition
    with pytest.raises(ValueError, match="Invalid FSM transition"):
        task.transition_to(TaskFSMState.IN_PROGRESS)


def test_task_fsm_blocked_and_recovery():
    task = TaskContract(task_id="task-102", spec_path="specs/db.md")
    task.transition_to(TaskFSMState.IN_PROGRESS)
    
    # IN_PROGRESS -> BLOCKED
    task.transition_to(TaskFSMState.BLOCKED, reason="Context limit reached (85%)")
    assert task.state == TaskFSMState.BLOCKED

    # BLOCKED -> IN_PROGRESS
    task.transition_to(TaskFSMState.IN_PROGRESS, reason="Failover agent spawned")
    assert task.state == TaskFSMState.IN_PROGRESS

    # Invalid jump directly from IN_PROGRESS to PENDING
    with pytest.raises(ValueError):
        task.transition_to(TaskFSMState.PENDING)


def test_ast_preflight_verifier():
    valid_code = """
def calculate_metrics(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
"""
    is_valid, err = ASTPreFlightVerifier.verify_python_code(valid_code)
    assert is_valid is True
    assert err is None

    invalid_syntax = """
def broken_syntax(values
    return 42
"""
    is_valid_bad, err_bad = ASTPreFlightVerifier.verify_python_code(invalid_syntax)
    assert is_valid_bad is False
    assert "SyntaxError" in err_bad


def test_zero_loss_failover():
    checkpoint = ZeroLossFailoverManager.create_checkpoint(
        task_id="task-999",
        git_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
        completed_steps=["Scaffold repo", "Implement models"],
        next_goals=["Write unit tests", "Run linter"],
        ast_verified=True
    )
    assert checkpoint["task_id"] == "task-999"
    assert checkpoint["ast_verified"] is True

    patch, completed, goals = ZeroLossFailoverManager.restore_checkpoint(checkpoint)
    assert "+++ b/file.py" in patch
    assert len(completed) == 2
    assert goals[0] == "Write unit tests"

    # Reject unverified checkpoint
    unverified_cp = dict(checkpoint)
    unverified_cp["ast_verified"] = False
    with pytest.raises(ValueError, match="Cannot restore from unverified AST"):
        ZeroLossFailoverManager.restore_checkpoint(unverified_cp)


def test_agent_desk_manager(tmp_path: Path):
    manager = AgentDeskManager(root_repo_path=tmp_path)
    desk = manager.create_desk("api-feature", "feat/api", agent_id="agent-01")
    assert desk.name == "api-feature"
    assert desk.branch == "feat/api"
    assert desk.is_active is True

    # Duplicate desk name error
    with pytest.raises(ValueError, match="already exists"):
        manager.create_desk("api-feature", "feat/api2")

    desks = manager.list_desks()
    assert len(desks) == 1

    # Release desk
    released = manager.release_desk("api-feature")
    assert released is True
    assert len(manager.list_desks()) == 0


def test_protocol_transformers():
    # ACP
    acp_msg = ProtocolTransformers.build_acp_message("session/prompt", {"text": "run test"}, msg_id=42)
    assert acp_msg["jsonrpc"] == "2.0"
    assert acp_msg["id"] == 42
    assert acp_msg["method"] == "acp/session/prompt"

    # A2A Agent Card
    card = ProtocolTransformers.build_a2a_agent_card(
        agent_name="CodeArchitect",
        description="Autonomous refactoring agent",
        capabilities=["ast_edit", "pytest_execution"],
        protocols=["JSON-RPC", "SSE"]
    )
    assert card["name"] == "CodeArchitect"
    assert card["protocol"] == "A2A/2026"
    assert "ast_edit" in card["capabilities"]
    assert card["opacity_level"] == "strict_artifact_passing"

    # Stateless MCP
    mcp_req = ProtocolTransformers.build_stateless_mcp_request(
        tool_name="git_worktree_add",
        arguments={"branch": "feat/xyz"},
        trace_id="trace-abc-123",
        require_elicitation=True
    )
    assert mcp_req["jsonrpc"] == "2.0"
    assert mcp_req["method"] == "tools/call"
    assert mcp_req["params"]["_meta"]["stateless"] is True
    assert mcp_req["params"]["_meta"]["require_elicitation"] is True


def test_hipporag2_and_hybrid_scoring():
    retriever = HippoRAG2Retriever()
    retriever.add_relation("AgentHarness", "manages", "TaskContract")
    retriever.add_relation("TaskContract", "enforces", "DoDGate")
    retriever.add_relation("AgentHarness", "isolates", "AgentDesk")
    retriever.add_relation("AgentDesk", "uses", "GitWorktree")

    ppr = retriever.compute_personalized_pagerank(seed_entities=["agentharness"])
    assert "agentharness" in ppr
    assert "taskcontract" in ppr
    assert "agentdesk" in ppr
    assert ppr["agentharness"] > 0
    # Sum of probabilities should be approximately 1.0
    total_prob = sum(ppr.values())
    assert abs(total_prob - 1.0) < 1e-4

    # Hybrid Score Calculation
    score = HippoRAG2Retriever.calculate_hybrid_score(
        dense_sim=0.90,
        bm25_score=0.85,
        hippo_ppr=ppr["taskcontract"],
        graph_centrality=0.80,
        elapsed_hours=2.0,
        memory_stability=10.0,
        importance=0.95
    )
    assert 0.0 < score <= 1.0


def test_token_physics_calculator():
    # Agentic Tax
    tax_result = TokenPhysicsCalculator.calculate_agentic_tax(
        turns=5,
        system_prompt_tokens=2000,
        tools_tokens=1000,
        avg_turn_input=500,
        avg_turn_output=300
    )
    assert tax_result["turns"] == 5
    assert tax_result["total_tokens_spent"] > tax_result["single_turn_naive_tokens"]
    assert tax_result["agentic_tax_ratio"] > 1.0

    # Anchored Prefix Cache Savings
    cache_result = TokenPhysicsCalculator.calculate_anchored_cache_savings(
        total_tokens=10000,
        cached_prefix_tokens=7000,
        cache_discount_rate=0.90
    )
    assert cache_result["hit_ratio"] == 0.70
    assert cache_result["savings_percent"] == 63.0  # 70% * 90% = 63% savings

    # Diff Savings
    diff_result = TokenPhysicsCalculator.calculate_diff_savings(
        full_file_tokens=2000,
        diff_tokens=100
    )
    assert diff_result["savings_percent"] == 95.0
    assert diff_result["reduction_ratio"] == 20.0

    # Delta Turn Tokens
    cur_usage = {
        "input_tokens": 15000,
        "output_tokens": 4000,
        "thinking_tokens": 2500,
        "cache_read_tokens": 10000,
        "total_tokens": 19000
    }
    prev_usage = {
        "input_tokens": 12000,
        "output_tokens": 3000,
        "thinking_tokens": 2000,
        "cache_read_tokens": 8000,
        "total_tokens": 15000
    }
    delta = TokenPhysicsCalculator.calculate_delta_turn_tokens(cur_usage, prev_usage)
    assert delta["input_tokens"] == 3000
    assert delta["output_tokens"] == 1000
    assert delta["thinking_tokens"] == 500
    assert delta["cache_read_tokens"] == 2000
    assert delta["total_tokens"] == 4000


def test_spec_driven_dag_scheduler():
    dag = SpecDrivenDAGScheduler()
    dag.add_task("task-1", "Design Schema")
    dag.add_task("task-2", "Implement DB Models", dependencies=["task-1"])
    dag.add_task("task-3", "Implement Business Logic", dependencies=["task-2"])
    dag.add_task("task-4", "Create API Endpoints", dependencies=["task-3"])

    # Initially only task-1 is ready
    ready = dag.get_ready_tasks(completed_task_ids=set())
    assert ready == ["task-1"]

    # When task-1 is done, task-2 becomes ready
    ready_after_1 = dag.get_ready_tasks(completed_task_ids={"task-1"})
    assert ready_after_1 == ["task-2"]

    # Topological order
    order = dag.get_topological_order()
    assert order == ["task-1", "task-2", "task-3", "task-4"]

    # Export markdown
    mermaid = dag.export_dag_markdown()
    assert "graph TD" in mermaid
    assert "task-1 --> task-2" in mermaid


def test_spec_driven_dag_cycle_detection():
    dag = SpecDrivenDAGScheduler()
    dag.add_task("task-A", "Component A", dependencies=["task-B"])
    dag.add_task("task-B", "Component B", dependencies=["task-A"])

    with pytest.raises(ValueError, match="Cycle detected"):
        dag.get_topological_order()


def test_generative_prm_verifier():
    # Valid reasoning and safe action
    res_valid = GenerativePRMVerifier.evaluate_step(
        step_index=1,
        thought="The task requires implementing a cache simulator. Let's write unit tests first.",
        action="write_to_file(target='test_cache.py')",
        observation="File created successfully."
    )
    assert res_valid["passed"] is True
    assert res_valid["score"] >= 0.9

    # Dangerous command detection
    res_danger = GenerativePRMVerifier.evaluate_step(
        step_index=2,
        thought="Let's clean everything by deleting all files.",
        action="run_command(cmd='rm -rf /')",
        observation=""
    )
    assert res_danger["passed"] is False
    assert res_danger["score"] == 0.0
    assert "Safety violation" in res_danger["critique"]

    # Shallow thought rejection
    res_shallow = GenerativePRMVerifier.evaluate_step(
        step_index=3,
        thought="ok",
        action="do_something()",
        observation=""
    )
    assert res_shallow["passed"] is False
    assert "Shallow thinking" in res_shallow["critique"]


def test_radix_attention_simulator():
    sim = RadixAttentionSimulator()
    system_prefix = ["You", "are", "Entropy", "AI", "master", "agent"]

    # Insert initial system prompt
    matched_0 = sim.insert_prompt(system_prefix)
    assert matched_0 == 0  # Cold cache

    # Check prefix match for new turn sharing the same system prefix + user query
    user_turn = system_prefix + ["Please", "inspect", "the", "repo"]
    matched_count, hit_ratio = sim.match_prefix(user_turn)
    assert matched_count == 6
    assert hit_ratio == 6 / 10  # 60% KV cache hit

    # Insert second prompt with same prefix
    matched_inserted = sim.insert_prompt(user_turn)
    assert matched_inserted == 6
