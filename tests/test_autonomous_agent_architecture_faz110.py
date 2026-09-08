"""
Automated Test Suite for Faz 110 Master Autonomous Agent Architecture
====================================================================
Verifies all Faz 110 invariants:
- CNP-v2 Market-Based Agent Task Bidding & SLA Tracking
- Speculative Multi-Branch Pareto Worktree Selection
- Autonomous Epistemic Dispute Arbitration Judge
- Self-Synthesizing Skill Evolution Engine
- Quad-Store RRF-3 Hybrid Retrieval & Contradiction Sentinel
- AST-Guided Code Skeletonizer & State-Based Tool Projection
- Faz 110 Master Swarm Self-Audit
"""

import pytest
from src.entropy.tools.autonomous_agent_architecture_faz110 import (
    AgentBid,
    AgentFSMState,
    AgentProfile,
    ArbitrationJudge,
    ASTCodeSkeletonizer,
    CacheBoundaryAligner,
    CNPTaskCoordinator,
    DisputeCase,
    DisputeVerdict,
    Faz110MasterAutonomousSwarmEngine,
    ParetoBranchSelector,
    QuadStoreRetriever,
    SkillEvolutionEngine,
    SpeculativeBranch,
    StateBasedToolProjector,
    TaskSpecification,
    TaskUrgency,
)


def test_cnp_task_coordinator_bidding_and_sla():
    coordinator = CNPTaskCoordinator()
    coordinator.register_agent("coder_1", "developer", ["python", "pytest", "fastapi"], token_cost_rate=0.02, base_latency_ms=70.0)
    coordinator.register_agent("coder_2", "qa_tester", ["pytest", "cypress"], token_cost_rate=0.01, base_latency_ms=50.0)
    coordinator.register_agent("coder_3", "architect", ["system_design", "python"], token_cost_rate=0.03, base_latency_ms=100.0)

    task = TaskSpecification(
        task_id="task_audit_01",
        title="Write API test suite",
        required_skills=["python", "pytest"],
        token_budget=1500,
        max_latency_ms=200.0,
        urgency=TaskUrgency.HIGH,
    )

    auction = coordinator.conduct_auction(task)
    assert auction["status"] == "AWARDED"
    assert auction["winner_id"] == "coder_1"
    assert auction["winning_bid"].affinity_score == 1.0
    assert coordinator.agents["coder_1"].current_queue_len == 1

    # Task completion
    coordinator.complete_task("task_audit_01", success=True)
    assert coordinator.agents["coder_1"].current_queue_len == 0
    assert coordinator.agents["coder_1"].total_tasks_completed == 1
    assert coordinator.agents["coder_1"].sla_success_rate == 1.0


def test_pareto_branch_selector():
    selector = ParetoBranchSelector(token_budget=3000, max_diff_lines=200)

    branch_optimal = SpeculativeBranch(
        branch_id="br_opt",
        task_id="t1",
        strategy_name="surgical_fix",
        code_diff={"file.py": "pass"},
        tests_passed=5,
        total_tests=5,
        tokens_consumed=500,
        lines_changed=8,
        ast_valid=True,
        execution_time_ms=80.0,
    )
    branch_heavy = SpeculativeBranch(
        branch_id="br_hvy",
        task_id="t1",
        strategy_name="heavy_rewrite",
        code_diff={"file.py": "pass"},
        tests_passed=5,
        total_tests=5,
        tokens_consumed=2500,
        lines_changed=180,
        ast_valid=True,
        execution_time_ms=900.0,
    )
    branch_broken = SpeculativeBranch(
        branch_id="br_brk",
        task_id="t1",
        strategy_name="failed_attempt",
        code_diff={"file.py": "pass"},
        tests_passed=3,
        total_tests=5,
        tokens_consumed=400,
        lines_changed=5,
        ast_valid=True,
        execution_time_ms=70.0,
    )

    res = selector.select_winning_branch([branch_heavy, branch_optimal, branch_broken])
    assert res["status"] == "PARETO_OPTIMAL_SELECTED"
    assert res["winner"].branch_id == "br_opt"
    assert res["viable_count"] == 2
    assert res["fitness_score"] > 0.8


def test_arbitration_judge_dispute_resolution():
    judge = ArbitrationJudge()

    # Case 1: Valid probe confirms bug in code
    target_buggy = "def multiply(a, b):\n    return a + b\n"
    probe_fail = "def test_probe():\n    assert multiply(3, 4) == 12\n"
    case_1 = DisputeCase(
        dispute_id="disp_01",
        task_id="t1",
        complainant_agent="tester",
        respondent_agent="dev",
        claim_description="Multiply function performs addition",
        code_target=target_buggy,
        probe_test_code=probe_fail,
    )
    res_1 = judge.adjudicate_dispute(case_1)
    assert res_1["verdict"] == DisputeVerdict.UPHELD_COMPLAINANT.value
    assert not res_1["execution_success"]

    # Case 2: Valid probe confirms code meets specification
    target_correct = "def multiply(a, b):\n    return a * b\n"
    probe_pass = "def test_probe():\n    assert multiply(3, 4) == 12\n"
    case_2 = DisputeCase(
        dispute_id="disp_02",
        task_id="t2",
        complainant_agent="reviewer",
        respondent_agent="dev",
        claim_description="Verify multiplication logic",
        code_target=target_correct,
        probe_test_code=probe_pass,
    )
    res_2 = judge.adjudicate_dispute(case_2)
    assert res_2["verdict"] == DisputeVerdict.UPHELD_RESPONDENT.value
    assert res_2["execution_success"]


def test_skill_evolution_engine():
    engine = SkillEvolutionEngine()
    sig = "circuit_breaker_pattern"
    code = "class CircuitBreaker:\n    pass\n"
    test_code = "def test_cb():\n    assert True\n"

    # Observation 1: Recorded but not yet crystallized
    res_1 = engine.observe_resolution(sig, code, test_code)
    assert res_1 is None
    assert engine.pattern_frequency[sig] == 1

    # Observation 2: Crystallized into skill
    res_2 = engine.observe_resolution(sig, code, test_code)
    assert res_2 is not None
    assert res_2.skill_name == sig
    assert engine.pattern_frequency[sig] == 2

    # Compile Markdown package
    md = engine.compile_skill_markdown(sig)
    assert f"name: {sig}" in md
    assert "class CircuitBreaker" in md
    assert "def test_cb" in md


def test_quad_store_rrf3_and_contradiction_sentinel():
    retriever = QuadStoreRetriever(vector_dim=4, rrf_k=60)
    v1 = [1.0, 0.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0, 0.0]
    v3 = [0.8, 0.2, 0.0, 0.0]

    n1 = retriever.insert_node("fact_v1", "Authentication using legacy session cookies", v1, ["auth", "cookies"])
    n2 = retriever.insert_node("fact_v2", "Authentication using modern JWT bearer tokens", v3, ["auth", "jwt"])
    n3 = retriever.insert_node("db_v1", "PostgreSQL database storage", v2, ["database", "postgres"])

    retriever.add_edge("fact_v1", "fact_v2")

    # Invalidate legacy fact
    assert retriever.invalidate_contradiction("fact_v1", "fact_v2") is True
    assert retriever.nodes["fact_v1"].is_active is False
    assert retriever.nodes["fact_v1"].valid_until is not None

    # Search: only active nodes should be retrieved
    results = retriever.hybrid_search_rrf3("authentication tokens", [0.9, 0.1, 0.0, 0.0], seed_node_id="fact_v2", top_k=2)
    assert len(results) == 2
    assert results[0][0] == "fact_v2"
    assert all(r[0] != "fact_v1" for r in results)


def test_ast_code_skeletonizer():
    source = (
        "import os\n\n"
        "class AgentController:\n"
        "    '''Main controller for autonomous agents.'''\n"
        "    def __init__(self, name: str):\n"
        "        self.name = name\n"
        "        self.status = 'idle'\n\n"
        "    def execute_task(self, task_id: str) -> bool:\n"
        "        '''Executes the given task.'''\n"
        "        print('Starting execution')\n"
        "        for i in range(100):\n"
        "            self.do_step(i)\n"
        "        return True\n"
    )

    skeleton = ASTCodeSkeletonizer.skeletonize(source)
    assert "class AgentController" in skeleton
    assert "def execute_task" in skeleton
    assert "Main controller for autonomous agents" in skeleton
    assert "print('Starting execution')" not in skeleton
    assert "for i in range(100)" not in skeleton
    assert "..." in skeleton


def test_state_based_tool_projector_and_cache_aligner():
    projector = StateBasedToolProjector()
    disc_tools = projector.project_tools_for_state(AgentFSMState.DISCOVERY)
    exec_tools = projector.project_tools_for_state(AgentFSMState.EXECUTION)

    disc_names = {t["name"] for t in disc_tools}
    exec_names = {t["name"] for t in exec_tools}

    assert "grep_search" in disc_names
    assert "write_to_file" not in disc_names
    assert "write_to_file" in exec_names
    assert "search_web" not in exec_names

    # KV Cache alignment
    raw = "SYSTEM PROMPT"
    aligned = CacheBoundaryAligner.pad_to_chunk_boundary(raw, chunk_size=64)
    assert "<!-- KV_CACHE_ALIGN -->" in aligned


def test_faz110_master_swarm_engine_self_audit():
    engine = Faz110MasterAutonomousSwarmEngine()
    audit = engine.run_comprehensive_self_audit()
    assert audit["audit_status"] == "SUCCESS_110_PERCENT"
    assert audit["auction_awarded"] is True
    assert audit["auction_winner"] is True
    assert audit["pareto_winner"] is True
    assert audit["dispute_resolved"] is True
    assert audit["skill_synthesized"] is True
    assert audit["contradiction_invalidated"] is True
    assert audit["rrf3_hits"] is True
    assert audit["skeleton_stripped"] is True
    assert audit["tools_projected_count"] > 0
    assert audit["cache_aligned"] is True
