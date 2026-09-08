"""
Automated Pytest Suite for Faz 75 Autonomous Agent Architecture Modules.
Tests:
1. KVPrefixCacheOptimizer (Deterministic JSON canonicalization, prefix boundary split, cache hit economics).
2. AgentDeskEphemeralManager (Workspace leasing, AST syntax pre-flight verification, atomic commit & rollback).
3. A2AProtocolCardNegotiator (Linux Foundation A2A v1.0 standard Agent Card verification & task delegation).
4. HybridGraphRAGRetriever (Dense + Sparse + Graph PPR tri-modal retrieval with RRF and Ebbinghaus decay).
5. Faz75AutonomousOrchestratorPipeline (End-to-End unified turn orchestration).
"""

import datetime
from pathlib import Path
import pytest

from entropy.tools.autonomous_agent_architecture import (
    KVPrefixCacheOptimizer,
    AgentDeskEphemeralManager,
    DeskLease,
    AgentCard,
    A2AProtocolCardNegotiator,
    HybridGraphRAGRetriever,
    Faz75AutonomousOrchestratorPipeline,
)


def test_kv_prefix_cache_optimizer():
    optimizer = KVPrefixCacheOptimizer()

    # 1. Deterministic Canonical JSON formatting
    data1 = {"z_key": 1, "a_key": {"c": 3, "b": 2}}
    data2 = {"a_key": {"b": 2, "c": 3}, "z_key": 1}
    canonical1 = optimizer.canonicalize_json(data1)
    canonical2 = optimizer.canonicalize_json(data2)
    assert canonical1 == canonical2
    assert canonical1 == '{"a_key":{"b":2,"c":3},"z_key":1}'

    # 2. Prompt Partitioning
    system_inst = "You are Entropy AI, an autonomous agent."
    tools = [
        {"name": "grep_search", "desc": "Search regex in files"},
        {"name": "edit_file", "desc": "Edit lines of code"}
    ]
    dynamic_ctx = "User: Run refactoring on module X."

    partition = optimizer.partition_prompt(system_inst, tools, dynamic_ctx)
    assert "[SYSTEM_INSTRUCTIONS_BEGIN]" in partition["cached_prefix"]
    assert "[CANONICAL_TOOLS_BEGIN]" in partition["cached_prefix"]
    assert "[DYNAMIC_CONTEXT_BEGIN]" in partition["dynamic_suffix"]
    assert len(partition["prefix_hash"]) == 64

    # Test byte-identical hash consistency
    partition2 = optimizer.partition_prompt(system_inst, list(reversed(tools)), "Different user prompt")
    assert partition["prefix_hash"] == partition2["prefix_hash"]

    # 3. Cache Metrics calculation
    metrics = optimizer.calculate_cache_metrics(prefix_tokens=9000, dynamic_tokens=1000)
    assert metrics["total_tokens"] == 10000
    assert metrics["cached_tokens"] == 9000
    assert metrics["cache_hit_ratio"] == 0.90
    assert metrics["savings_percent"] == 81.0  # 90% * 90% discount = 81% total savings
    assert metrics["optimized_cost_usd"] < metrics["baseline_cost_usd"]


def test_agent_desk_ephemeral_manager():
    manager = AgentDeskEphemeralManager(default_lease_seconds=3600)

    # 1. Lease allocation
    lease = manager.lease_desk("task_refactor_core")
    assert lease.desk_id.startswith("desk_task_refactor_core_")
    assert "agent-desk/task_refactor_core/" in lease.branch_name
    assert lease.active is True
    assert len(lease.lease_token) == 16

    # 2. AST Validation - Valid Files
    valid_files = {
        "module_a.py": "def add(x: int, y: int) -> int:\n    return x + y\n",
        "config.json": '{"mode": "autonomous", "timeout": 30}'
    }
    val_res = manager.validate_staged_changes(valid_files)
    assert val_res["valid"] is True
    assert len(val_res["errors"]) == 0

    # 3. AST Validation - Syntax Errors
    broken_files = {
        "broken.py": "def broken_func(:\n    return 1",
        "broken.json": "{unquoted_key: 123}"
    }
    val_broken = manager.validate_staged_changes(broken_files)
    assert val_broken["valid"] is False
    assert "broken.py" in val_broken["errors"]
    assert "broken.json" in val_broken["errors"]

    # 4. Atomic Commit Success
    commit_ok = manager.atomic_commit(
        desk_id=lease.desk_id,
        files=valid_files,
        commit_message="Implement valid arithmetic helper"
    )
    assert commit_ok["status"] == "COMMITTED"
    assert len(commit_ok["committed_files"]) == 2
    assert len(lease.commits) == 1

    # 5. Atomic Commit Rollback on Syntax Error
    commit_fail = manager.atomic_commit(
        desk_id=lease.desk_id,
        files=broken_files,
        commit_message="Try to commit invalid code"
    )
    assert commit_fail["status"] == "ROLLED_BACK"
    assert commit_fail["committed"] is False
    assert len(lease.commits) == 1  # No new commit added

    # 6. Release Desk
    assert manager.release_desk(lease.desk_id) is True
    assert lease.desk_id not in manager.active_desks


def test_a2a_protocol_card_negotiator():
    negotiator = A2AProtocolCardNegotiator()

    # 1. Register agents
    orchestrator_card = AgentCard(
        agent_id="orch_agent",
        name="Master Orchestrator",
        version="2026.1",
        capabilities=["orchestration", "delegation"]
    )
    coder_card = AgentCard(
        agent_id="code_architect",
        name="CodeArchitect",
        version="2026.1",
        capabilities=["code_synthesis", "ast_refactor", "unit_testing"]
    )
    assert negotiator.register_agent(orchestrator_card) is True
    assert negotiator.register_agent(coder_card) is True
    assert coder_card.signature is not None

    # 2. Negotiate delegation with valid capability
    delegation_res = negotiator.negotiate_task_delegation(
        sender_card=orchestrator_card,
        target_agent_id="code_architect",
        task_requirement="code_synthesis",
        payload={"module": "auth_service", "spec": "OAuth2 PKCE flow"}
    )
    assert delegation_res["status"] == "ACCEPTED"
    assert delegation_res["protocol"] == "A2A/1.0"
    del_id = delegation_res["delegation_id"]

    # 3. Reject delegation with unsupported capability
    unsupported_res = negotiator.negotiate_task_delegation(
        sender_card=orchestrator_card,
        target_agent_id="code_architect",
        task_requirement="hardware_fpga_flashing",
        payload={}
    )
    assert unsupported_res["status"] == "REJECTED"
    assert "lacks capability" in unsupported_res["reason"]

    # 4. Complete delegation contract
    comp_res = negotiator.complete_delegation(
        delegation_id=del_id,
        result_payload={"files_generated": ["auth.py", "test_auth.py"], "tests_passed": True}
    )
    assert comp_res["status"] == "COMPLETED"
    assert len(comp_res["receipt_hash"]) == 64


def test_hybrid_graph_rag_retriever():
    retriever = HybridGraphRAGRetriever(ebbinghaus_lambda=0.05, rrf_k=60)

    # Index 3 documents with known embeddings & wikilinks
    now = datetime.datetime.now()
    retriever.index_document(
        doc_id="doc_harness",
        title="Agent Harness Architecture",
        content="The harness surrounds LLMs with tool dispatch, action loop, and memory.",
        vector=[1.0, 0.0, 0.0],
        wikilinks=["[[Agent_Desks]]", "[[A2A_Protocol]]"],
        timestamp=now,
        importance=0.9
    )
    retriever.index_document(
        doc_id="doc_token",
        title="Token Physics and Prompt Caching",
        content="Prompt caching achieves 90 percent discount on stable system prefixes.",
        vector=[0.0, 1.0, 0.0],
        wikilinks=["[[Context_Engineering]]"],
        timestamp=now - datetime.timedelta(days=10),
        importance=0.6
    )
    retriever.index_document(
        doc_id="doc_desks",
        title="Agent Desks and Worktrees",
        content="Ephemeral git worktrees isolate agent branches and prevent conflicts.",
        vector=[0.8, 0.2, 0.0],
        wikilinks=["[[Agent_Harness_Architecture]]", "[[AST_Validation]]"],
        timestamp=now - datetime.timedelta(days=2),
        importance=0.8
    )

    # Query matching doc_harness and doc_desks
    results = retriever.query_hybrid(
        query_text="harness memory and worktrees",
        query_vector=[0.9, 0.1, 0.0],
        linked_topics=["[[Agent_Desks]]"],
        top_k=2
    )
    assert len(results) == 2
    assert results[0]["doc_id"] == "doc_harness"
    assert results[0]["final_score"] > results[1]["final_score"]
    assert "rrf_score" in results[0]
    assert "retention_factor" in results[0]


def test_faz75_autonomous_orchestrator_pipeline_e2e():
    pipeline = Faz75AutonomousOrchestratorPipeline()

    # Pre-index memory
    pipeline.rag_retriever.index_document(
        doc_id="rag_doc_1",
        title="Autonomous Workspaces",
        content="Agent desks provide ephemeral worktrees with AST validation.",
        vector=[1.0, 0.0],
        wikilinks=["[[Desks]]"],
        importance=0.8
    )

    coder_card = AgentCard(
        agent_id="code_bot_75",
        name="CoderBot75",
        version="2.0",
        capabilities=["code_generation"]
    )

    valid_code = {
        "worker.py": "def execute_task() -> str:\n    return 'success'\n"
    }

    result = pipeline.execute_autonomous_turn(
        task_id="task_turn_75",
        system_prompt="You are Entropy AI Faz 75 autonomous agent.",
        tools_schema=[{"name": "bash", "params": {"cmd": "str"}}],
        task_prompt="Implement task turn worker with AST gatekeeping.",
        subagent_card=coder_card,
        generated_code_files=valid_code,
        query_vector=[1.0, 0.0],
        wikilink_context=["[[Desks]]"]
    )

    assert result["task_id"] == "task_turn_75"
    assert len(result["prefix_hash"]) == 64
    assert result["cache_savings_percent"] > 0.0
    assert result["a2a_delegation_status"] == "COMPLETED"
    assert result["rag_hit_count"] >= 1
    assert result["desk_commit_status"] == "COMMITTED"
    assert "agent-desk/task_turn_75/" in result["desk_branch"]
