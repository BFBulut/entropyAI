"""
Tests for Faz 102 Frontier Autonomous Agent Architecture & Cognitive OS Suite.
Verifies:
1. Faz102AdaptiveHarnessEngineering (Fault localization, pre-flight AST, candidate freezing, invariant checks)
2. Faz102AgentDesksProjectGovernor (Single-Writer Boundary, Kahn DAG, Worktrees, Test-Gated Merges & Rollbacks)
3. Faz102AAIFProtocolHub (Google A2A v1.1 Opacity, Stateless MCP 2026, Async MCP Tasks)
4. Faz102CognitiveExocortexSubstrate (Shannon surprise filter, 1-Bit BQ POPCNT, Cosine rerank, HippoRAG PPR)
5. Faz102TokenPhysicsContextEconomizer (Delta token accounting, RadixAttention Trie, CodeAct REPL sandbox)
6. Faz102MasterAutonomousEngine (End-to-End Orchestrator)
"""

import pytest
import time
from typing import Tuple, List

from entropy.tools.autonomous_agent_architecture import TaskFSMState, TaskContract
from entropy.tools.autonomous_agent_architecture_faz102 import (
    Faz102AdaptiveHarnessEngineering,
    Faz102AgentDesksProjectGovernor,
    Faz102AAIFProtocolHub,
    Faz102CognitiveExocortexSubstrate,
    Faz102TokenPhysicsContextEconomizer,
    Faz102MasterAutonomousEngine
)


def test_faz102_adaptive_harness_engineering():
    harness = Faz102AdaptiveHarnessEngineering(agent_id="test_harness_102")
    task = TaskContract(task_id="task_102_harness", spec_path="specs/task.md")
    
    # Bind task
    bind_res = harness.bind_task(task, worker_pid=7711)
    assert bind_res["status"] == "BOUND"
    assert bind_res["worker_pid"] == 7711
    assert harness.state == TaskFSMState.IN_PROGRESS
    assert harness.generate_kill_command() == "taskkill /F /T /PID 7711"

    # Register invariants
    harness.register_invariants(["test_core_invariants", "test_ast_integrity"])
    assert "test_core_invariants" in harness.preservation_invariants

    # Phase 1: Localization
    codebase = {
        "src/calc.py": "def calculate_net_yield(x, y):\n    return x / y\n\ndef helper():\n    pass\n",
        "src/util.py": "def string_cleanup(s):\n    return s.strip()\n"
    }
    loc = harness.locate_fault(codebase, "calculate_net_yield")
    assert loc["total_matches"] >= 1
    assert loc["candidates"][0]["file"] == "src/calc.py"
    assert loc["candidates"][0]["start_line"] == 1

    # In-memory AST pre-flight guardrail: Valid patch
    orig_code = "def foo():\n    return 1\n"
    valid_patch = "    return 2"
    pre_valid = harness.preflight_ast_check(orig_code, valid_patch, 2, 2)
    assert pre_valid["status"] == "VALID"

    # In-memory AST pre-flight guardrail: Invalid syntax
    invalid_patch = "    return def syntax error"
    pre_invalid = harness.preflight_ast_check(orig_code, invalid_patch, 2, 2)
    assert pre_invalid["status"] == "SYNTAX_ERROR"

    # Phase 2: Candidate Freezing ($A_t^{frozen}$)
    cand_code = "def calculate_net_yield(x, y):\n    if y == 0:\n        return 0.0\n    return x / y\n"
    frozen = harness.freeze_candidate("cand_calc_1", cand_code)
    assert frozen["status"] == "FROZEN"
    assert len(frozen["sha256"]) == 64

    # Phase 3: Validation with intact invariants
    def dummy_test_runner_pass(c: str) -> Tuple[bool, List[str]]:
        return True, []

    val_res = harness.validate_and_select_candidate("cand_calc_1", dummy_test_runner_pass)
    assert val_res["accepted"] is True
    assert len(val_res["regressed_invariants"]) == 0

    # Phase 3: Validation failing an invariant
    def dummy_test_runner_regressed(c: str) -> Tuple[bool, List[str]]:
        return False, ["test_core_invariants"]

    val_fail = harness.validate_and_select_candidate("cand_calc_1", dummy_test_runner_regressed)
    assert val_fail["accepted"] is False
    assert "test_core_invariants" in val_fail["regressed_invariants"]


def test_faz102_agent_desks_project_governor(tmp_path):
    gov = Faz102AgentDesksProjectGovernor(project_root=str(tmp_path))
    
    # Provision desks: Single-Writer Boundary
    dev_desk = gov.provision_desk("dev_01", role="Developer")
    qa_desk = gov.provision_desk("qa_01", role="QA")
    reviewer_desk = gov.provision_desk("rev_01", role="Reviewer")

    assert dev_desk.is_writable is True
    assert qa_desk.is_writable is False
    assert reviewer_desk.is_writable is False
    assert dev_desk.port != qa_desk.port

    # Kahn DAG Task Scheduling
    gov.add_task("task_A", "Architecture Spec", dependencies=[])
    gov.add_task("task_B", "DB Migrations", dependencies=["task_A"])
    gov.add_task("task_C", "API Implementation", dependencies=["task_B"])
    gov.add_task("task_D", "Frontend Client", dependencies=["task_B"])
    gov.add_task("task_E", "End-to-End Test Verification", dependencies=["task_C", "task_D"])

    schedule = gov.compute_topological_schedule()
    assert schedule.index("task_A") < schedule.index("task_B")
    assert schedule.index("task_B") < schedule.index("task_C")
    assert schedule.index("task_B") < schedule.index("task_D")
    assert schedule.index("task_C") < schedule.index("task_E")
    assert schedule.index("task_D") < schedule.index("task_E")

    # Progress Logging
    gov.log_progress(dev_desk.desk_id, "task_C", "API controller written", status="OK")
    assert len(gov.inner_progress_ledger) == 1

    # Test-Gated Merge Gatekeeper: Success (pass_rate = 1.0)
    merge_ok = gov.evaluate_and_merge(dev_desk.desk_id, {"pass_rate": 1.0})
    assert merge_ok["status"] == "MERGED"
    assert dev_desk.active_branch in gov.merged_branches

    # Rollback Sentinel: Failure (pass_rate = 0.85 < 1.0)
    merge_fail = gov.evaluate_and_merge(dev_desk.desk_id, {"pass_rate": 0.85})
    assert merge_fail["status"] == "ROLLED_BACK"
    assert dev_desk.active_branch in gov.rolled_back_branches


def test_faz102_aaif_protocol_hub():
    hub = Faz102AAIFProtocolHub()
    
    # Register A2A Agent
    card = hub.register_a2a_agent(
        agent_id="agent_coder",
        name="Entropy Coder",
        description="Autonomous developer agent",
        capabilities=["python_codegen", "refactoring"],
        endpoint="https://a2a.entropy.internal/coder"
    )
    assert card["protocol_version"] == "A2A-1.1"
    assert card["opacity_guarantee"] is True

    # A2A Task Delegation with Opacity (Stripping CoT)
    dirty_contract = {
        "task_id": "T102",
        "description": "Implement auth middleware",
        "cot": "Secret reasoning step that must not leak",
        "thinking": "Model thinking log"
    }
    envelope = hub.delegate_a2a_task("orchestrator", "agent_coder", dirty_contract)
    assert envelope["method"] == "a2a.delegateTask"
    assert "cot" not in envelope["params"]["contract"]
    assert "thinking" not in envelope["params"]["contract"]
    assert envelope["params"]["contract"]["task_id"] == "T102"

    # Stateless MCP Request (2026 specification)
    mcp_req = hub.create_stateless_mcp_request("run_query", {"sql": "SELECT 1"})
    assert mcp_req["params"]["_meta"]["protocolVersion"] == "2026-07-28"
    assert mcp_req["params"]["_meta"]["stateless"] is True

    # Async MCP Tasks ('call-now, fetch-later')
    task_id = hub.spawn_async_mcp_task("deep_scan", {"path": "/tmp"})
    assert len(task_id) == 64
    poll_1 = hub.poll_mcp_task(task_id)
    assert poll_1["status"] == "RUNNING"

    hub.complete_mcp_task(task_id, {"findings": ["vuln_1", "vuln_2"]})
    poll_2 = hub.poll_mcp_task(task_id)
    assert poll_2["status"] == "COMPLETED"
    assert poll_2["result"]["findings"] == ["vuln_1", "vuln_2"]


def test_faz102_cognitive_exocortex_substrate():
    mem = Faz102CognitiveExocortexSubstrate(surprise_threshold=0.4, decay_rate=0.05)

    vec1 = [0.2] * 768 + [-0.1] * 768
    vec2 = [-0.3] * 768 + [0.4] * 768

    # Shannon Surprise Filter: Routine noise filtered
    noise_res = mem.write_memory("mem_noise", "Server alive", vec1, surprise=0.1)
    assert noise_res["status"] == "FILTERED_NOISE"

    # High surprise: Committed
    comm_res1 = mem.write_memory("mem_arch", "Microservices boundary decision", vec1, importance=0.9, surprise=0.8)
    assert comm_res1["status"] == "COMMITTED"

    comm_res2 = mem.write_memory("mem_db", "Postgres index tuning", vec2, importance=0.8, surprise=0.7)
    assert comm_res2["status"] == "COMMITTED"

    # 1-Bit Binary Quantization POPCNT verification
    bits1 = mem.quantize_to_1bit_bq(vec1)
    bits2 = mem.quantize_to_1bit_bq(vec2)
    assert len(bits1) == 1536
    assert bits1[:768] == "1" * 768
    assert bits1[768:] == "0" * 768
    assert mem.hamming_distance(bits1, bits1) == 0
    assert mem.hamming_distance(bits1, bits2) == 1536

    # Two-Stage Hybrid Recall
    recalled = mem.hybrid_two_stage_recall(vec1, top_k=2)
    assert len(recalled) == 2
    assert recalled[0]["memory_id"] == "mem_arch"
    assert recalled[0]["cosine_sim"] > 0.9

    # HippoRAG 2 Personalized PageRank (PPR)
    mem.add_graph_edge("mem_arch", "DEPENDS_ON", "mem_db")
    ppr_scores = mem.execute_hipporag_ppr(["mem_arch"], max_steps=2)
    assert "mem_db" in ppr_scores
    assert ppr_scores["mem_db"] > 0.1


def test_faz102_token_physics_context_economizer():
    phys = Faz102TokenPhysicsContextEconomizer(rotation_threshold_turns=3)

    # Delta Token Accounting
    turn1 = phys.calculate_delta_usage({"input_tokens": 1200, "output_tokens": 300})
    assert turn1["delta_input"] == 1200
    assert turn1["delta_output"] == 300
    assert turn1["turn"] == 1

    turn2 = phys.calculate_delta_usage({"input_tokens": 2500, "output_tokens": 550})
    assert turn2["delta_input"] == 1300  # 2500 - 1200
    assert turn2["delta_output"] == 250  # 550 - 300
    assert turn2["turn"] == 2
    assert phys.check_rotation_needed() is False

    turn3 = phys.calculate_delta_usage({"input_tokens": 4000, "output_tokens": 900})
    assert turn3["turn"] == 3
    assert phys.check_rotation_needed() is True

    rot = phys.reset_session()
    assert rot["status"] == "ROTATED"
    assert phys.turn_counter == 0

    # RadixAttention Prefix Caching Trie
    prefix = ["SYSTEM", "ROLE", "DEVELOPER", "INVARIANTS"]
    phys.register_prefix(prefix)
    matched, hit_rate = phys.query_prefix_cache_hit(["SYSTEM", "ROLE", "DEVELOPER", "INVARIANTS", "USER_PROMPT"])
    assert matched == 4
    assert hit_rate == 0.8

    # CodeAct Local REPL Execution (Zero MCP tax)
    code = "data = [10, 20, 30, 40]\nresult = sum(data) / len(data)"
    codeact_res = phys.execute_codeact(code)
    assert codeact_res["status"] == "SUCCESS"
    assert codeact_res["result"] == 25.0
    assert codeact_res["tokens_saved_estimate"] >= 1000


def test_faz102_master_autonomous_engine(tmp_path):
    engine = Faz102MasterAutonomousEngine(project_root=str(tmp_path))
    task = TaskContract(task_id="T_MASTER_102", spec_path="specs/master.md")
    codebase = {
        "src/core.py": "def execute_operation():\n    return 'PENDING'\n"
    }
    result = engine.run_autonomous_cycle(task, codebase, "execute_operation")
    assert result["status"] == "COMPLETED"
    assert result["validation"]["accepted"] is True
    assert result["merge"]["status"] == "MERGED"
    assert result["memory"]["status"] == "COMMITTED"
