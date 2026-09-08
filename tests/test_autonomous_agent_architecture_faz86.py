"""
Unit tests for Faz 86 Autonomous Agent Architecture.
Validates:
1. ClosedLoopWatcherSentinel (ClawKeeper Decoupled State Reconstruction & Safety Sentinel).
2. CacheBlendSeamRepairer (Non-Prefix Knowledge Fusion & Boundary Seam Selective Recomputation).
3. PTYProcessTreeSupervisor (Process Hierarchy Tracking, taskkill /F /T /PID Simulation, Delta Token Accounting).
4. FastMCP2026TaskAppLifecycle (Durable Asynchronous Tasks, MCP Apps Manifests, Reverse MCP Sampling).
5. Faz86MasterAutonomousArchitectureSystem (End-to-end unified autonomous cycle with 100% integrity).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    ClosedLoopWatcherSentinel,
    CacheBlendSeamRepairer,
    PTYProcessTreeSupervisor,
    FastMCP2026TaskAppLifecycle,
    Faz86MasterAutonomousArchitectureSystem
)


def test_closed_loop_watcher_sentinel():
    sentinel = ClosedLoopWatcherSentinel(max_token_budget=100000)

    # 1. Clean code within budget and no regression -> ADMISSIBLE
    res_pass = sentinel.evaluate_admissibility(
        task_id="task_clean_001",
        current_state="IN_PROGRESS",
        proposed_code="def add(a, b):\n    return a + b\n",
        cumulative_tokens_used=45000,
        test_exit_code=0
    )
    assert res_pass["is_admissible"] is True
    assert res_pass["status"] == "ADMISSIBLE"
    assert res_pass["action"] == "PROCEED"
    assert len(res_pass["violations"]) == 0

    # 2. Forbidden pattern detected -> BREACH
    res_forbidden = sentinel.evaluate_admissibility(
        task_id="task_bad_002",
        current_state="IN_PROGRESS",
        proposed_code="eval('malicious_input()')",
        cumulative_tokens_used=50000,
        test_exit_code=0
    )
    assert res_forbidden["is_admissible"] is False
    assert res_forbidden["status"] == "ENVELOPE_BREACH"
    assert res_forbidden["action"] == "INTERVENTION_CIRCUIT_BREAKER"
    assert any("FORBIDDEN_PATTERN_DETECTED" in v for v in res_forbidden["violations"])

    # 3. Budget exceeded -> BREACH
    res_budget = sentinel.evaluate_admissibility(
        task_id="task_over_003",
        current_state="IN_PROGRESS",
        proposed_code="x = 1\n",
        cumulative_tokens_used=120000,
        test_exit_code=0
    )
    assert res_budget["is_admissible"] is False
    assert any("TOKEN_BUDGET_EXCEEDED" in v for v in res_budget["violations"])

    # 4. Test regression -> BREACH
    res_regr = sentinel.evaluate_admissibility(
        task_id="task_regr_004",
        current_state="IN_PROGRESS",
        proposed_code="x = 1\n",
        cumulative_tokens_used=30000,
        test_exit_code=1
    )
    assert res_regr["is_admissible"] is False
    assert any("TEST_REGRESSION_DETECTED" in v for v in res_regr["violations"])


def test_cache_blend_seam_repairer():
    repairer = CacheBlendSeamRepairer(default_seam_ratio=0.12)

    chunks = [
        ["System", "Directive", "Autonomous", "Agent", "Harness", "Spec"],
        ["Late", "Chunking", "Embeddings", "Preserve", "Global", "Context", "Across", "Tokens"],
        ["FastMCP", "2026", "Apps", "Deliver", "Interactive", "Client", "UIs", "Directly"]
    ]

    res = repairer.fuse_chunks_with_seam_repair(chunks, seam_recompute_ratio=0.12)
    assert res["status"] == "CACHE_BLEND_SEAM_REPAIRED"
    assert res["total_tokens"] == len(chunks[0]) + len(chunks[1]) + len(chunks[2])
    assert res["cached_tokens_reused"] > res["seam_tokens_recomputed"]
    assert res["effective_cache_hit_pct"] > 70.0
    assert res["ttft_reduction_ratio"] >= 2.0

    # Empty chunk edge case
    empty_res = repairer.fuse_chunks_with_seam_repair([])
    assert empty_res["status"] == "EMPTY_CHUNKS"
    assert empty_res["total_tokens"] == 0


def test_pty_process_tree_supervisor():
    supervisor = PTYProcessTreeSupervisor()

    # 1. Process Hierarchy & Termination
    supervisor.register_process(pid=1000, name="agy.exe")
    supervisor.register_process(pid=1001, name="language_server.exe", parent_pid=1000)
    supervisor.register_process(pid=1002, name="python_worker.exe", parent_pid=1001)

    descendants = supervisor.get_descendant_pids(1000)
    assert 1001 in descendants
    assert 1002 in descendants

    term_res = supervisor.terminate_process_tree(1000)
    assert term_res["status"] == "PROCESS_TREE_TERMINATED_CLEANLY"
    assert set(term_res["terminated_pids"]) == {1000, 1001, 1002}
    assert "taskkill /F /T /PID 1000" in term_res["command"]
    assert supervisor.process_tree[1000]["alive"] is False
    assert supervisor.process_tree[1001]["alive"] is False

    # 2. Delta Token Accounting
    turn1_lifetime = {"input_tokens": 10000, "output_tokens": 2000}
    delta1 = supervisor.calculate_delta_turn_tokens(turn1_lifetime)
    assert delta1["delta_input_tokens"] == 10000
    assert delta1["delta_output_tokens"] == 2000
    assert delta1["delta_total_tokens"] == 12000

    turn2_lifetime = {"input_tokens": 13500, "output_tokens": 2800}
    delta2 = supervisor.calculate_delta_turn_tokens(turn2_lifetime)
    assert delta2["delta_input_tokens"] == 3500
    assert delta2["delta_output_tokens"] == 800
    assert delta2["delta_total_tokens"] == 4300

    # 3. Stream line chunks
    raw = "Line 1\n\n  Line 2  \r\nLine 3"
    lines = supervisor.stream_line_chunks(raw)
    assert lines == ["Line 1", "Line 2", "Line 3"]


def test_fastmcp_task_app_lifecycle():
    lifecycle = FastMCP2026TaskAppLifecycle()

    # 1. Managed Task
    task = lifecycle.create_managed_task(task_id="task_99", prompt="Refactor auth module")
    assert task["task_id"] == "task_99"
    assert task["state"] == "RUNNING"
    assert len(task["handle"]) == 64

    steered = lifecycle.steer_task("task_99", guidance="Use argon2 for password hashing.")
    assert steered["state"] == "STEERED_IN_PROGRESS"
    assert len(steered["steer_history"]) == 1

    # 2. MCP App Dashboard
    metrics = {"coverage": "100%", "active_desks": 2}
    app = lifecycle.generate_mcp_app_dashboard("app_dash", "Security Dashboard", metrics)
    assert app["app_id"] == "app_dash"
    assert app["render_target"] == "desktop_client"
    assert len(app["components"]) == 2

    # 3. MCP Sampling
    sample = lifecycle.request_sampling_inference("Analyze log snippet")
    assert sample["status"] == "SAMPLING_SUCCESS"
    assert sample["tokens_consumed"] > 0


def test_faz86_master_autonomous_architecture_system():
    system = Faz86MasterAutonomousArchitectureSystem(embedding_dim=8)

    doc = (
        "Entropy AI utilizes Claude Code and Google Antigravity harness architectures. "
        "Agent Desks allocate isolated git worktrees with dynamic non-colliding ports. "
        "CacheBlend repairs seam tokens to enable KV cache reuse in dynamic multi-hop RAG. "
        "HippoRAG 2 provides Personalized PageRank associative retrieval across knowledge graphs."
    )
    triples = [
        ("Entropy AI", "utilizes", "Agent Desks"),
        ("Agent Desks", "isolates", "git worktrees"),
        ("Entropy AI", "deploys", "CacheBlend"),
        ("CacheBlend", "repairs", "seam tokens"),
        ("Entropy AI", "deploys", "HippoRAG 2")
    ]

    result = system.execute_faz86_autonomous_cycle(
        cycle_id="faz86_verified_run",
        goal="Demonstrate full Faz 86 Autonomous Agent Architecture with 100% test integrity",
        source_code="def safe_run():\n    return 'OK'\n",
        system_instructions="Execute autonomously with zero human intervention.",
        invariant_rules="Enforce AST verification, Desk isolation, and Delta Token Accounting.",
        conversation_history=[
            {"role": "user", "content": "How do we minimize agent tokens and isolate tasks?"},
            {"role": "assistant", "content": "Use Agent Desks, CacheBlend, and Radix prefix caching."}
        ],
        knowledge_doc=doc,
        openie_triples=triples,
        seed_concept="Entropy AI",
        query_vector=[0.1] * 8,
        memory_vectors=[("mem1", [0.1] * 8, {"title": "Agent Desks"})],
        simulate_test_pass=True,
        cumulative_tokens_snapshot={"input_tokens": 40000, "output_tokens": 10000}
    )

    assert result["status"] == "FAZ86_AUTONOMOUS_CYCLE_COMPLETE"
    assert result["overall_integrity"] == "VERIFIED_100_PERCENT"
    assert result["closed_loop_watcher"]["is_admissible"] is True
    assert result["cache_blend_seam_repair"]["status"] == "CACHE_BLEND_SEAM_REPAIRED"
    assert result["pty_process_telemetry"]["delta_tokens"]["delta_total_tokens"] > 0
    assert result["fastmcp_lifecycle"]["managed_task"]["state"] == "STEERED_IN_PROGRESS"
    assert result["faz85_core"]["agent_desk"]["merge_verification"]["status"] == "MERGE_APPROVED"
