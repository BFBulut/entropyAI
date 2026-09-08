"""
Automated Pytest Suite for Faz 77 Autonomous Multi-Agent Architecture Modules.
Tests:
1. HippoRAG2ContinualMemoryEngine (Personalized PageRank, multi-hop associative recall, power iteration).
2. HarnessRuntimeSupervisor (Checkpoints, state snapshotting, deterministic rollback, budget & failure risk).
3. MultiAgentSwarmConsensusDesk (Tripartite Worker-Critic-Synthesizer pipeline & Plurality consensus voting).
4. Faz77MasterAutonomousArchitecture (Unified master orchestrator integrating memory, harness, swarm, JIT, and DAG).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    HippoRAG2ContinualMemoryEngine,
    HarnessRuntimeSupervisor,
    HarnessCheckpoint,
    MultiAgentSwarmConsensusDesk,
    Faz77MasterAutonomousArchitecture,
)


def test_hipporag2_continual_memory_engine_ppr():
    engine = HippoRAG2ContinualMemoryEngine(restart_prob=0.85, max_iter=60, tol=1e-6)

    # 1. Add passages with entities forming an associative chain:
    # [DAG] <-> [Multi-Agent] <-> [Consensus] <-> [Byzantine]
    engine.add_passage(
        passage_id="pass_dag",
        content="DAG project scheduling decomposes work into topological stages for multi-agent teams.",
        entities=["dag", "scheduling", "multi_agent"]
    )
    engine.add_passage(
        passage_id="pass_consensus",
        content="Multi-agent systems coordinate via consensus mechanisms and byzantine voting.",
        entities=["multi_agent", "consensus", "byzantine"]
    )
    engine.add_passage(
        passage_id="pass_byzantine",
        content="Byzantine voting ensures fault tolerance and workspace desk integrity.",
        entities=["byzantine", "fault_tolerance", "workspace_desk"]
    )

    # Add a direct relation
    engine.add_relation("dag", "dependency_graph", weight=2.0)

    # Query using only seed entity: "dag"
    res = engine.compute_personalized_pagerank(seed_entities=["dag"])

    assert res["converged"] is True
    assert res["iterations_to_converge"] > 0
    assert len(res["ranked_passages"]) == 3
    assert res["ranked_passages"][0]["passage_id"] == "pass_dag"

    # Verify Multi-Hop discovery:
    # "byzantine" and "multi_agent" were NOT in seed, but must be discovered via graph propagation
    discovered = res["multi_hop_discovered"]
    assert "multi_agent" in discovered
    assert "byzantine" in discovered or any(e["entity"] == "byzantine" for e in res["ranked_entities"])

    # Empty seeds case
    empty_res = engine.compute_personalized_pagerank(seed_entities=[])
    assert empty_res["ranked_passages"] == []
    assert empty_res["converged"] is True


def test_harness_runtime_supervisor_checkpoint_and_rollback():
    harness = HarnessRuntimeSupervisor(budget_alert_threshold=0.80, min_acceptable_reliability=0.50)

    original_state = {
        "step": 2,
        "active_file": "agent_worker.py",
        "variables": {"retry_count": 0, "status": "IN_PROGRESS"}
    }

    chk_res = harness.create_checkpoint(
        task_id="task_harness_01",
        step_index=2,
        state_data=original_state,
        desk_id="desk_git_wt_01"
    )

    chk_id = chk_res["checkpoint_id"]
    assert chk_res["status"] == "CHECKPOINT_CREATED"
    assert chk_id in harness.checkpoints

    # Mutate original state to simulate buggy progression
    mutated_state = original_state
    mutated_state["variables"]["retry_count"] = 5
    mutated_state["variables"]["status"] = "CORRUPTED"

    # Rollback to snapshot
    rollback_res = harness.rollback_to_checkpoint(chk_id)
    assert rollback_res["status"] == "ROLLED_BACK"
    assert rollback_res["restored_step"] == 2
    assert rollback_res["restored_state"]["variables"]["retry_count"] == 0
    assert rollback_res["restored_state"]["variables"]["status"] == "IN_PROGRESS"
    assert rollback_res["desk_id"] == "desk_git_wt_01"

    # Non-existent checkpoint
    bad_res = harness.rollback_to_checkpoint("chk_non_existent")
    assert bad_res["status"] == "ROLLBACK_FAILED"


def test_harness_runtime_supervisor_budget_and_risk():
    harness = HarnessRuntimeSupervisor(budget_alert_threshold=0.80, min_acceptable_reliability=0.50)

    # 1. Normal safe operation
    eval_safe = harness.evaluate_budget_and_risk(
        step_tokens=1000,
        current_total_tokens=10000,
        max_budget_tokens=50000,
        recent_step_successes=[True, True, True, True]
    )
    assert eval_safe["risk_level"] == "LOW"
    assert eval_safe["action_recommendation"] == "PROCEED"
    assert eval_safe["compounding_reliability"] == 1.0

    # 2. Elevated budget usage (82%)
    eval_elevated = harness.evaluate_budget_and_risk(
        step_tokens=2000,
        current_total_tokens=39000,
        max_budget_tokens=50000,
        recent_step_successes=[True, True, True]
    )
    assert eval_elevated["risk_level"] == "ELEVATED"
    assert eval_elevated["action_recommendation"] == "REDUCE_EFFORT"

    # 3. Critical budget breach (> 100%) or compounding failure
    eval_critical_budget = harness.evaluate_budget_and_risk(
        step_tokens=5000,
        current_total_tokens=48000,
        max_budget_tokens=50000,
        recent_step_successes=[True, True]
    )
    assert eval_critical_budget["risk_level"] == "CRITICAL"
    assert eval_critical_budget["action_recommendation"] == "HALT_OR_ESCALATE"

    # 4. Low reliability cascade: e.g. 50% success -> 0.5^5 = 0.03125 < 0.50
    eval_failure_cascade = harness.evaluate_budget_and_risk(
        step_tokens=100,
        current_total_tokens=5000,
        max_budget_tokens=50000,
        recent_step_successes=[True, False, False, True]
    )
    assert eval_failure_cascade["risk_level"] == "CRITICAL"
    assert eval_failure_cascade["compounding_reliability"] < 0.50


def test_swarm_consensus_tripartite_pipeline():
    swarm = MultiAgentSwarmConsensusDesk()

    worker_proposal = {
        "code": "def process_data(items): return [x * 2 for x in items]",
        "tests": "assert process_data([1, 2]) == [2, 4]"
    }

    # Case A: Critic approves with clean score
    clean_critique = {
        "passed": True,
        "severity": 0.05,
        "critique_points": []
    }
    res_clean = swarm.run_tripartite_consensus("task_01", worker_proposal, clean_critique)
    assert res_clean["consensus_status"] == "APPROVED"
    assert res_clean["revisions_applied"] is False
    assert res_clean["reviewer_score"] > 0.90

    # Case B: Critic finds flaws requiring synthesis
    flawed_critique = {
        "passed": False,
        "severity": 0.60,
        "critique_points": ["Missing type annotations", "Missing empty list guard"]
    }
    res_synth = swarm.run_tripartite_consensus("task_02", worker_proposal, flawed_critique)
    assert res_synth["consensus_status"] == "SYNTHESIZED"
    assert res_synth["revisions_applied"] is True
    assert "Missing type annotations" in res_synth["final_artifact"]["synthesizer_notes"]


def test_swarm_consensus_plurality_voting():
    swarm = MultiAgentSwarmConsensusDesk()

    candidates = [
        {"solution_signature": "algo_quicksort", "confidence": 0.95, "content": "def sort(): pass"},
        {"solution_signature": "algo_quicksort", "confidence": 0.90, "content": "def sort(): pass"},
        {"solution_signature": "algo_bubblesort", "confidence": 0.40, "content": "def slow_sort(): pass"},
    ]

    vote_res = swarm.run_plurality_voting(candidates)
    assert vote_res["status"] == "CONSENSUS_ACHIEVED"
    assert vote_res["winner"]["solution_signature"] == "algo_quicksort"
    assert vote_res["consensus_ratio"] > 0.80

    # Empty case
    empty_vote = swarm.run_plurality_voting([])
    assert empty_vote["status"] == "NO_PROPOSALS"
    assert empty_vote["winner"] is None


def test_faz77_master_autonomous_architecture_e2e():
    master = Faz77MasterAutonomousArchitecture()

    # Pre-populate HippoRAG graph
    master.hippo_rag.add_passage(
        passage_id="doc_orchestrator",
        content="Autonomous orchestrators use DAGs, JIT tools and Git worktree desks.",
        entities=["orchestration", "dag", "git_worktree", "jit_tools"]
    )

    worker_proposal = {
        "code": "class AutonomousWorker: pass",
        "description": "Initial worker scaffold"
    }
    critic_critique = {
        "passed": True,
        "severity": 0.10,
        "critique_points": ["Minor naming suggestion"]
    }

    step_res = master.run_autonomous_consensus_step(
        task_id="task_faz77_01",
        system_instructions="You are an autonomous engineering agent.",
        user_prompt="Implement autonomous worker with git worktree desk and DAG scheduling",
        seed_entities=["orchestration", "dag"],
        worker_proposal=worker_proposal,
        critic_critique=critic_critique,
        max_budget_tokens=80000,
        current_tokens=15000
    )

    assert step_res["task_id"] == "task_faz77_01"
    assert step_res["task_status"] == "COMPLETED"
    assert step_res["consensus_status"] == "APPROVED"
    assert step_res["desk_id"].startswith("desk_task_faz77_01_")
    assert step_res["checkpoint_id"].startswith("chk_task_faz77_01_")
    assert step_res["hippo_passages_found"] >= 1
    assert step_res["risk_level"] == "LOW"
    assert step_res["tool_savings_pct"] > 0.0
