"""
Tests for Entropy AI - Autonomous Agent Architecture Core Engine (Faz 71)
Validates:
1. A2ANegotiationEngine (Linux Foundation AAIF A2A Protocol v1.0 Agent Cards & typed delegation).
2. AutonomousProjectGovernanceEngine (Sprint lifecycle, living specifications, task FSM, git worktrees).
3. MultiAgentConsensusEngine (Process Reward Model weighted voting, 3-way diff arbitration, HITL escalation).
4. HippoRAG2HybridRRFRetriever (Dense + Sparse BM25 + Graph PPR Reciprocal Rank Fusion & Ebbinghaus decay).
5. DynamicContextBudgetEngine (Context slot partitioner, prefix caching economics, CodeAct token savings).
6. End-to-end multi-agent orchestration integration test.
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    AgentCard,
    A2ANegotiationEngine,
    ProjectSprintPhase,
    ProjectSprint,
    AutonomousProjectGovernanceEngine,
    MultiAgentConsensusEngine,
    HippoRAG2HybridRRFRetriever,
    DynamicContextBudgetEngine,
    TaskContract,
    TaskFSMState
)


def test_a2a_negotiation_accepted_and_rejected():
    agent_coder = AgentCard(
        name="Agent-PythonCoder",
        version="2.1.0",
        description="Autonomous Python backend specialist",
        capabilities=["python", "fastapi", "pytest", "git", "ast_analysis"],
        endpoint="https://agents.entropy.local/coder"
    )

    task_valid = TaskContract(task_id="task-001", spec_path="docs/specs/task1.md")
    required_caps_valid = ["python", "pytest", "git"]

    res_accepted = A2ANegotiationEngine.negotiate_delegation(
        target_agent=agent_coder,
        required_capabilities=required_caps_valid,
        task=task_valid,
        min_capability_threshold=0.70
    )

    assert res_accepted["handshake_accepted"] is True
    assert res_accepted["status"] == "ACCEPTED"
    assert res_accepted["match_score"] == 1.0
    assert "delegation_token" in res_accepted
    assert res_accepted["delegation_token"].startswith("a2a_token_task-001")

    # Incompatible task requirements (Rust / Kernel development)
    task_incompat = TaskContract(task_id="task-002", spec_path="docs/specs/task2.md")
    required_caps_incompat = ["rust", "wasm", "linux_kernel", "ebpf"]

    res_rejected = A2ANegotiationEngine.negotiate_delegation(
        target_agent=agent_coder,
        required_capabilities=required_caps_incompat,
        task=task_incompat,
        min_capability_threshold=0.50
    )

    assert res_rejected["handshake_accepted"] is False
    assert res_rejected["status"] == "REJECTED_CAPABILITY_MISMATCH"
    assert res_rejected["match_score"] == 0.0
    assert res_rejected["delegation_token"] is None


def test_autonomous_project_governance_lifecycle():
    gov_engine = AutonomousProjectGovernanceEngine()
    sprint = gov_engine.create_sprint(
        sprint_id="sprint-core-01",
        goal="Synthesize Autonomous Memory Layer & Multi-Agent Desks",
        task_ids=["task-mem-01", "task-desk-02"]
    )

    assert sprint.sprint_id == "sprint-core-01"
    assert sprint.phase == ProjectSprintPhase.BACKLOG
    assert len(sprint.tasks) == 2
    assert "task-mem-01" in sprint.tasks

    # Advance to execution
    gov_engine.advance_phase("sprint-core-01", ProjectSprintPhase.EXECUTION)
    assert sprint.phase == ProjectSprintPhase.EXECUTION

    # Allocate worktree desk
    desk_path = "worktrees/desk_task_mem_01"
    allocated = gov_engine.allocate_worktree_for_task("sprint-core-01", "task-mem-01", desk_path)
    assert allocated == desk_path
    assert sprint.tasks["task-mem-01"].assigned_desk == desk_path
    assert sprint.tasks["task-mem-01"].state == TaskFSMState.IN_PROGRESS

    # Check telemetry
    telemetry = gov_engine.get_sprint_telemetry("sprint-core-01")
    assert telemetry["total_tasks"] == 2
    assert telemetry["completed_tasks"] == 0
    assert telemetry["in_progress_tasks"] == 1
    assert telemetry["active_worktrees_count"] == 1

    # Attempt to release sprint while tasks are incomplete -> Expect ValueError
    with pytest.raises(ValueError, match="Cannot release sprint"):
        gov_engine.advance_phase("sprint-core-01", ProjectSprintPhase.RELEASED)

    # Complete tasks and verify release
    sprint.tasks["task-mem-01"].transition_to(TaskFSMState.VERIFYING)
    sprint.tasks["task-mem-01"].transition_to(TaskFSMState.COMPLETED)
    sprint.tasks["task-desk-02"].transition_to(TaskFSMState.IN_PROGRESS)
    sprint.tasks["task-desk-02"].transition_to(TaskFSMState.VERIFYING)
    sprint.tasks["task-desk-02"].transition_to(TaskFSMState.COMPLETED)

    assert gov_engine.advance_phase("sprint-core-01", ProjectSprintPhase.RELEASED) is True
    telemetry_released = gov_engine.get_sprint_telemetry("sprint-core-01")
    assert telemetry_released["completion_rate_pct"] == 100.0


def test_multi_agent_consensus_weighted_prm():
    proposals = {
        "prop_arch_a": {"architecture": "Microkernel Actor Bus", "lines_diff": 350},
        "prop_arch_b": {"architecture": "Monolithic Shared Blackboard", "lines_diff": 800}
    }

    evaluations = [
        {"proposal_id": "prop_arch_a", "verifier_weight": 2.0, "score": 0.95},
        {"proposal_id": "prop_arch_a", "verifier_weight": 1.5, "score": 0.90},
        {"proposal_id": "prop_arch_b", "verifier_weight": 2.0, "score": 0.45},
        {"proposal_id": "prop_arch_b", "verifier_weight": 1.5, "score": 0.50},
    ]

    consensus_res = MultiAgentConsensusEngine.evaluate_consensus(
        proposals=proposals,
        verifier_evaluations=evaluations,
        approval_threshold=0.70
    )

    assert consensus_res["consensus_achieved"] is True
    assert consensus_res["winner_proposal_id"] == "prop_arch_a"
    assert consensus_res["winner_score"] > 0.90
    assert consensus_res["arbitration_action"] == "EXECUTE_WINNER"


def test_multi_agent_consensus_hitl_escalation():
    proposals = {
        "prop_sqlite": {"backend": "SQLite WAL"},
        "prop_duckdb": {"backend": "DuckDB Parquet"}
    }

    evaluations = [
        {"proposal_id": "prop_sqlite", "verifier_weight": 1.0, "score": 0.55},
        {"proposal_id": "prop_duckdb", "verifier_weight": 1.0, "score": 0.58},
    ]

    consensus_res = MultiAgentConsensusEngine.evaluate_consensus(
        proposals=proposals,
        verifier_evaluations=evaluations,
        approval_threshold=0.70
    )

    assert consensus_res["consensus_achieved"] is False
    assert consensus_res["winner_proposal_id"] is None
    assert consensus_res["arbitration_required"] is True
    assert consensus_res["arbitration_action"] == "ESCALATE_TO_HITL_ELICITATION"


def test_hipporag2_hybrid_rrf_retriever():
    retriever = HippoRAG2HybridRRFRetriever(
        k_rrf=60,
        weight_dense=0.30,
        weight_sparse=0.20,
        weight_graph=0.50
    )

    dense = ["doc_memory_01", "doc_auth_02", "doc_ui_03"]
    sparse = ["doc_auth_02", "doc_memory_01", "doc_tools_04"]
    graph_ppr = ["doc_memory_01", "doc_tools_04", "doc_auth_02"]

    fused = retriever.rank_fuse_and_decay(
        dense_ranked_ids=dense,
        sparse_ranked_ids=sparse,
        graph_ppr_ranked_ids=graph_ppr
    )

    assert len(fused) == 4
    # doc_memory_01 is top ranked across dense & graph, and 2nd in sparse
    top_doc_id, top_score = fused[0]
    assert top_doc_id == "doc_memory_01"
    assert top_score > 0.0


def test_hipporag2_hybrid_rrf_ebbinghaus_decay():
    retriever = HippoRAG2HybridRRFRetriever(k_rrf=60)
    dense = ["doc_fresh", "doc_old"]
    sparse = ["doc_fresh", "doc_old"]
    graph = ["doc_fresh", "doc_old"]

    # doc_fresh is 1 day old, doc_old is 180 days old
    ages = {"doc_fresh": 1.0, "doc_old": 180.0}

    fused = retriever.rank_fuse_and_decay(
        dense_ranked_ids=dense,
        sparse_ranked_ids=sparse,
        graph_ppr_ranked_ids=graph,
        document_ages_days=ages,
        decay_half_life_days=30.0
    )

    score_dict = dict(fused)
    assert score_dict["doc_fresh"] > score_dict["doc_old"] * 10.0


def test_dynamic_context_budget_allocator():
    # 200k model window (Claude 3.7 / Gemini standard)
    budget = DynamicContextBudgetEngine.compute_context_budget(
        total_window_tokens=200000,
        system_and_tools_tokens=15000,
        pinned_spec_tokens=5000,
        history_tokens=50000,
        max_output_tokens=8192
    )

    assert budget["anchored_prefix_tokens"] == 20000
    assert budget["is_context_saturated"] is False
    assert budget["needs_compaction"] is False
    assert budget["cached_prefix_ratio_percent"] == 10.0

    # Test saturation case
    saturated_budget = DynamicContextBudgetEngine.compute_context_budget(
        total_window_tokens=50000,
        system_and_tools_tokens=10000,
        pinned_spec_tokens=5000,
        history_tokens=30000,  # 30k / 26.8k > 100%
        max_output_tokens=8192
    )
    assert saturated_budget["is_context_saturated"] is True
    assert saturated_budget["needs_compaction"] is True


def test_codeact_efficiency_benchmark():
    # 500k raw CSV data tokens vs 150 token script + 250 token summary
    eff = DynamicContextBudgetEngine.calculate_codeact_efficiency(
        raw_dataset_tokens=500000,
        code_script_tokens=150,
        result_payload_tokens=250
    )

    assert eff["raw_dataset_tokens"] == 500000
    assert eff["codeact_total_tokens"] == 400
    assert eff["tokens_saved"] == 499600
    assert eff["savings_percent"] > 99.9
    assert eff["token_reduction_factor"] == 1250.0


def test_full_integrated_autonomous_agent_orchestration_faz71():
    """End-to-end integration validating Phase 71 multi-agent workflow."""
    # 1. Discovery & Negotiation
    agent_architect = AgentCard(
        name="LeadCodeArchitect",
        version="3.0",
        description="System architecture designer",
        capabilities=["architecture", "spec_synthesis", "prm_eval"],
        endpoint="https://agents.entropy.local/architect"
    )
    task = TaskContract(task_id="task-arch-01", spec_path="docs/specs/arch.md")
    neg = A2ANegotiationEngine.negotiate_delegation(agent_architect, ["architecture", "spec_synthesis"], task)
    assert neg["handshake_accepted"] is True

    # 2. Sprint Governance
    gov = AutonomousProjectGovernanceEngine()
    sprint = gov.create_sprint("sprint-f71", "Autonomous Orchestration", ["task-arch-01"])
    gov.advance_phase("sprint-f71", ProjectSprintPhase.EXECUTION)
    gov.allocate_worktree_for_task("sprint-f71", "task-arch-01", "worktrees/desk_arch")

    # 3. Multi-Agent Consensus
    props = {
        "p1": {"spec": "Actor Model"},
        "p2": {"spec": "Shared Mutex"}
    }
    evals = [
        {"proposal_id": "p1", "verifier_weight": 3.0, "score": 0.92},
        {"proposal_id": "p2", "verifier_weight": 3.0, "score": 0.40}
    ]
    consensus = MultiAgentConsensusEngine.evaluate_consensus(props, evals)
    assert consensus["winner_proposal_id"] == "p1"

    # 4. HippoRAG 2 Hybrid Retrieval
    retriever = HippoRAG2HybridRRFRetriever()
    results = retriever.rank_fuse_and_decay(
        dense_ranked_ids=["spec_actor", "spec_mutex"],
        sparse_ranked_ids=["spec_actor"],
        graph_ppr_ranked_ids=["spec_actor"]
    )
    assert results[0][0] == "spec_actor"
