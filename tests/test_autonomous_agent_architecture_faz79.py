"""
Unit tests for Faz 79 Autonomous Agent Architecture.
Validates:
1. RadixAttentionPrefixCacheSimulator (Trie-based prefix matching, TTFT speedup, and cache-bust detection).
2. CodeActExecutionEngine (AST-verified execution and quantitative token economics).
3. LightRAGDualLevelGraphEngine (Low-level entities + High-level communities + Hybrid retrieval).
4. Faz79MasterAutonomousArchitecture (E2E autonomous sprint integration).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    RadixAttentionPrefixCacheSimulator,
    CodeActExecutionEngine,
    LightRAGDualLevelGraphEngine,
    Faz79MasterAutonomousArchitecture
)


def test_radix_attention_cache_matching_and_ttft():
    sim = RadixAttentionPrefixCacheSimulator(bytes_per_token_kv=128)
    
    prefix = ["System:", "You", "are", "EntropyAI", "Mode:", "Autonomous"]
    added = sim.insert_prefix(prefix)
    assert added == 6
    assert sim.total_cached_tokens == 6

    # 1. Exact match hit
    prompt = ["System:", "You", "are", "EntropyAI", "Mode:", "Autonomous", "User:", "Hello"]
    eval_res = sim.evaluate_request(prompt)
    assert eval_res["cached_tokens_hit"] == 6
    assert eval_res["uncached_tokens_prefill"] == 2
    assert eval_res["hit_ratio"] == 0.75
    assert eval_res["acceleration_factor"] > 1.0
    assert eval_res["cache_busted"] is False

    # 2. Cache-bust due to dynamic timestamp prefix
    busted_prompt = ["timestamp:2026-09-05", "System:", "You", "are"]
    bust_eval = sim.evaluate_request(busted_prompt)
    assert bust_eval["cached_tokens_hit"] == 0
    assert bust_eval["cache_busted"] is True
    assert "invalidated Trie prefix" in bust_eval["bust_reason"]


def test_codeact_execution_and_ast_safety():
    engine = CodeActExecutionEngine()

    # 1. Valid code action
    valid_code = """
data = [10, 20, 30, 40, 50]
filtered = [x for x in data if x > 25]
result = {"sum": sum(filtered), "count": len(filtered)}
"""
    res = engine.execute_code_action(valid_code)
    assert res["status"] == "SUCCESS"
    assert res["output"] == {"sum": 120, "count": 3}
    assert res["error"] is None

    # 2. Invalid syntax caught by AST pre-flight
    broken_code = """
def broken_func(
    return "syntax error"
"""
    err_res = engine.execute_code_action(broken_code)
    assert err_res["status"] == "AST_ERROR"
    assert "SyntaxError" in err_res["error"]


def test_codeact_token_economics_comparison():
    engine = CodeActExecutionEngine()
    
    # 50,000 token dataset filtered by 120-token python script yielding 20-token summary
    econ = engine.compare_token_efficiency(
        raw_dataset_size_tokens=50000,
        json_tool_turns=5,
        codeact_script_tokens=120,
        codeact_output_tokens=20
    )
    assert econ["codeact_total_tokens"] == 140
    assert econ["tokens_saved"] > 50000
    assert econ["reduction_percentage"] > 99.0
    assert econ["compression_ratio"] > 300.0


def test_lightrag_dual_level_indexing_and_retrieval():
    graph = LightRAGDualLevelGraphEngine()

    # 1. Low-level entities & relations
    graph.add_entity("func_verify_ast", "Function", "Validates python code syntax via ast.parse")
    graph.add_entity("class_task_contract", "Class", "FSM TaskContract maintaining durable state")
    graph.add_relation("class_task_contract", "func_verify_ast", "validates_with")

    # 2. High-level communities
    graph.register_community(
        community_id="comm_harness_core",
        title="Agent Harness Core Subsystem",
        summary="Deterministic chassis ensuring safety, zero-loss failover, and AST verification.",
        members=["func_verify_ast", "class_task_contract"]
    )

    # Low-level query
    low_res = graph.dual_level_retrieve(query="ast code verification", mode="low")
    assert len(low_res["results"]) >= 1
    assert low_res["results"][0]["entity_id"] == "func_verify_ast"

    # High-level query
    high_res = graph.dual_level_retrieve(query="harness architecture subsystem", mode="high")
    assert len(high_res["results"]) >= 1
    assert high_res["results"][0]["community_id"] == "comm_harness_core"

    # Hybrid query
    hybrid_res = graph.dual_level_retrieve(query="ast harness subsystem", mode="hybrid")
    assert hybrid_res["dual_level_synthesized"] is True
    assert hybrid_res["low_level_hits"] >= 1
    assert hybrid_res["high_level_hits"] >= 1


def test_faz79_master_autonomous_sprint_e2e():
    master = Faz79MasterAutonomousArchitecture()

    incoming_prompt = [
        "You", "are", "EntropyAI", "Autonomous", "Agentic", "OS",
        "SystemInvariants:", "ZeroExternalAPIKeys", "RealTimePiping",
        "TaskIsState", "AgentIsCompute", "ASTPreFlightMandatory",
        "SprintGoal:", "Implement", "Telemetry"
    ]
    codeact_script = """
# Compute synthetic telemetry metrics
telemetry_data = [99.2, 99.5, 99.8, 100.0]
avg_uptime = sum(telemetry_data) / len(telemetry_data)
result = {"system": "EntropyAI", "avg_uptime": round(avg_uptime, 2)}
"""

    sprint_res = master.execute_autonomous_sprint(
        task_id="sprint_telemetry_2026",
        goal="Autonomous Telemetry Sprint with RadixAttention and CodeAct",
        subtasks=["calculate_uptime", "persist_metrics"],
        incoming_prompt_tokens=incoming_prompt,
        codeact_snippet=codeact_script,
        dataset_tokens=30000
    )

    assert sprint_res["sprint_status"] == "COMPLETED"
    assert sprint_res["radix_cache_eval"]["cached_tokens_hit"] == 12
    assert sprint_res["radix_cache_eval"]["hit_ratio"] > 0.70
    assert sprint_res["codeact_execution"]["status"] == "SUCCESS"
    assert sprint_res["codeact_execution"]["output"]["avg_uptime"] == 99.62
    assert sprint_res["token_economics"]["reduction_percentage"] > 99.0
    assert sprint_res["commit_status"] == "COMMITTED"
    assert sprint_res["dual_ledger_snapshot"]["task_ledger"]["version"] == 1
    assert sprint_res["dual_ledger_snapshot"]["progress_ledger_count"] == 1
