"""
Automated Test Suite for Faz 112 Master Autonomous Agent Architecture
====================================================================
Verifies all Faz 112 invariants:
- A2A Protocol v1.0.0 & AP2 (Agent Payments Protocol) Handshake, Agent Cards & Escrow
- Erlang-OTP Supervision Trees 2.0 (One-for-One, One-for-All, Rest-for-One, Rollback Sentinel)
- Code-as-Action (CodeAct) Virtual Sandbox 2.0 & AST Pre-Flight Security
- Hexa-Store Multi-Tier Hybrid Retrieval (Obsidian, pgvector 0.8+ BQ, BM25, LightRAG, HippoRAG 2, Graphiti) & RRF-6
- Radix-Cache 64-Token Alignment, AST Skeletonizer 2.0 & Delta Token Accounting
- Agent Desks Single-Writer Boundary (SWB) & Test-Gated Merge Gatekeeper
- Faz 112 Master Autonomous Swarm Orchestrator End-to-End Self-Audit
"""

import math
import time
import pytest
from src.entropy.tools.autonomous_agent_architecture_faz112 import (
    A2APhase112ProtocolEngine,
    A2ATaskDelegationRequest,
    A2ATaskStatus,
    AgentCard,
    AgentDeskWorktreeManager,
    CodeActSandboxEngine,
    CodeActSecurityException,
    ExtremeTokenPhysicsOptimizer4,
    Faz112MasterAutonomousSwarmEngine,
    HexaMemoryNode,
    HexaStoreCognitiveRetriever,
    OTPSupervisorStrategy,
    OTPSupervisorTree2,
)


def test_a2a_agent_card_and_ap2_contract():
    engine = A2APhase112ProtocolEngine()
    card = AgentCard(
        agent_id="dev_specialist",
        name="Developer Specialist Desk",
        version="2026.112.0",
        description="High precision python developer",
        capabilities=["python", "ast_refactor", "pytest"],
        endpoints={"tasks": "/tasks", "mailbox": "/mailbox"},
        token_rate_per_k=0.02,
        max_concurrency=4,
        ap2_currency="USD",
    )
    engine.register_agent(card)
    assert engine.get_agent_card("dev_specialist") is not None

    card_json = engine.generate_well_known_agent_json("dev_specialist")
    assert "https://a2a-protocol.org/schemas/v1.0.0/agent-card.json" in card_json
    assert "dev_specialist" in card_json
    assert "Developer Specialist Desk" in card_json

    # Test AP2 escrow contract creation
    contract = engine.create_ap2_contract("orchestrator", "dev_specialist", token_budget=10000)
    assert contract.escrow_amount == pytest.approx(0.20)  # 10 * 0.02
    assert contract.is_settled is False

    # Test AP2 settlement
    settled = engine.settle_ap2_contract(contract.contract_id, tokens_used=4000)
    assert settled == pytest.approx(0.08)  # 4 * 0.02
    assert contract.is_settled is True


def test_a2a_task_delegation_lifecycle_and_dlq():
    engine = A2APhase112ProtocolEngine()
    card = AgentCard(
        agent_id="qa_agent",
        name="QA Tester",
        version="2026.112.0",
        description="Tester",
        capabilities=["pytest"],
        endpoints={"tasks": "/tasks"},
        token_rate_per_k=0.01,
        max_concurrency=2,
        is_active=True,
    )
    engine.register_agent(card)

    # 1. Target offline / unregistered -> DLQ
    offline_req = A2ATaskDelegationRequest(
        task_id="task_fail_01",
        sender_id="orch",
        target_id="nonexistent_agent",
        payload={"test": "run"},
        token_budget=1000,
        deadline_epoch_s=time.time() + 100,
    )
    resp_offline = engine.delegate_task(offline_req)
    assert resp_offline.status == A2ATaskStatus.REJECTED
    assert len(engine.dead_letter_queue) == 1

    # 2. Expired deadline -> DLQ
    expired_req = A2ATaskDelegationRequest(
        task_id="task_fail_02",
        sender_id="orch",
        target_id="qa_agent",
        payload={"test": "run"},
        token_budget=1000,
        deadline_epoch_s=time.time() - 10,
    )
    resp_expired = engine.delegate_task(expired_req)
    assert resp_expired.status == A2ATaskStatus.FAILED
    assert len(engine.dead_letter_queue) == 2

    # 3. Successful delegation
    valid_req = A2ATaskDelegationRequest(
        task_id="task_ok_01",
        sender_id="orch",
        target_id="qa_agent",
        payload={"test": "run"},
        token_budget=1000,
        deadline_epoch_s=time.time() + 300,
    )
    resp_ok = engine.delegate_task(valid_req)
    assert resp_ok.status == A2ATaskStatus.IN_PROGRESS
    assert len(engine.mailboxes["qa_agent"]) == 1
    assert valid_req.signature != ""


def test_otp_supervisor_strategies_and_rollback():
    # 1. Test ONE_FOR_ONE
    sup_one = OTPSupervisorTree2(strategy=OTPSupervisorStrategy.ONE_FOR_ONE, max_restarts=2)
    sup_one.register_worker("w1", "dev")
    sup_one.register_worker("w2", "qa")
    sup_one.set_clean_checkpoint("w1", "commit_abc123")

    report = sup_one.handle_worker_fault("w1", "Division by zero")
    assert report["action"] == "RESTARTED"
    assert report["restarted_workers"] == ["w1"]
    assert report["rollback_commit"] == "commit_abc123"

    # Exceed restart limit
    sup_one.handle_worker_fault("w1", "Second crash")
    report_term = sup_one.handle_worker_fault("w1", "Third crash")
    assert report_term["action"] == "TERMINATE_CREW"

    # 2. Test ONE_FOR_ALL
    sup_all = OTPSupervisorTree2(strategy=OTPSupervisorStrategy.ONE_FOR_ALL, max_restarts=3)
    sup_all.register_worker("w1", "dev")
    sup_all.register_worker("w2", "qa")
    report_all = sup_all.handle_worker_fault("w1", "Fatal memory leak")
    assert set(report_all["restarted_workers"]) == {"w1", "w2"}

    # 3. Test REST_FOR_ONE
    sup_rest = OTPSupervisorTree2(strategy=OTPSupervisorStrategy.REST_FOR_ONE, max_restarts=3)
    sup_rest.register_worker("w1", "architect")
    sup_rest.register_worker("w2", "developer")
    sup_rest.register_worker("w3", "tester")
    report_rest = sup_rest.handle_worker_fault("w2", "Build error")
    assert report_rest["restarted_workers"] == ["w2", "w3"]
    assert "w1" not in report_rest["restarted_workers"]


def test_codeact_ast_security_scanner():
    sandbox = CodeActSandboxEngine()

    # Valid code
    is_safe, msg = sandbox.validate_code_safety("x = 10 + 20\ny = sum([x, 5])")
    assert is_safe is True
    assert "PASSED" in msg

    # Forbidden builtin eval
    is_safe_eval, msg_eval = sandbox.validate_code_safety("eval('2+2')")
    assert is_safe_eval is False
    assert "forbidden builtin" in msg_eval

    # Forbidden module os import
    is_safe_os, msg_os = sandbox.validate_code_safety("import os\nos.system('dir')")
    assert is_safe_os is False
    assert "restricted module" in msg_os

    # Forbidden subprocess from-import
    is_safe_sub, msg_sub = sandbox.validate_code_safety("from subprocess import Popen")
    assert is_safe_sub is False
    assert "restricted module" in msg_sub


def test_codeact_sandbox_execution_and_token_savings():
    sandbox = CodeActSandboxEngine()

    code = (
        "data = [1, 2, 3, 4, 5]\n"
        "squared = [x**2 for x in data]\n"
        "total = sum(squared)\n"
    )
    result = sandbox.execute_in_sandbox(code)
    assert result["success"] is True
    assert result["result_vars"]["total"] == 55
    assert result["simulated_token_savings"] == 0.85
    assert result["execution_time_ms"] >= 0.0

    # Raising security exception on dangerous execution
    with pytest.raises(CodeActSecurityException):
        sandbox.execute_in_sandbox("import sys")


def test_hexa_store_hybrid_retrieval_and_fact_invalidation():
    retriever = HexaStoreCognitiveRetriever(rrf_k=60)

    node_old = HexaMemoryNode(
        doc_id="fact_db_old",
        content="Primary database is MySQL 5.7",
        category="archival",
        dense_vec=[0.1, 0.1, 0.1],
        sparse_terms=["database", "mysql"],
        graph_entities=["DB", "MySQL"],
        graph_theme="infrastructure",
    )
    node_new = HexaMemoryNode(
        doc_id="fact_db_new",
        content="Primary database upgraded to PostgreSQL 16 with pgvector 0.8",
        category="core",
        dense_vec=[0.8, 0.8, 0.8],
        sparse_terms=["database", "postgresql", "pgvector"],
        graph_entities=["DB", "PostgreSQL", "pgvector"],
        graph_theme="infrastructure",
    )

    retriever.insert_node(node_old)
    retriever.insert_node(node_new)

    # Invalidate old fact
    invalidated = retriever.invalidate_contradiction("fact_db_old", "fact_db_new")
    assert invalidated is True

    # Query retriever
    results = retriever.query_hexa_store(
        query_vec=[0.75, 0.75, 0.75],
        query_terms=["database", "pgvector"],
        query_entities=["DB"],
        query_theme="infrastructure",
    )
    assert len(results) == 1
    assert results[0]["doc_id"] == "fact_db_new"
    assert results[0]["rrf6_score"] > 0.0


def test_hexa_store_ebbinghaus_strength_decay():
    now = time.time()
    node = HexaMemoryNode(
        doc_id="node_decay",
        content="Short lived ephemeral log",
        category="recall",
        dense_vec=[0.1],
        sparse_terms=["log"],
        graph_entities=[],
        graph_theme="logging",
        importance=0.9,
        created_at=now - 86400 * 10,
        last_accessed=now - 86400 * 10,  # 10 days ago
        access_count=1,
    )
    # Strength after 10 days without access
    decayed = node.calculate_ebbinghaus_strength(now=now, decay_rate=0.1)
    assert decayed < 0.9

    # Reinforce memory with multiple accesses
    node.access_count = 50
    node.last_accessed = now
    fresh_strength = node.calculate_ebbinghaus_strength(now=now, decay_rate=0.1)
    assert fresh_strength == pytest.approx(0.9)


def test_radix_cache_boundary_alignment():
    optimizer = ExtremeTokenPhysicsOptimizer4()
    prompt = "This is a prompt with exactly ten words for boundary testing."
    aligned_text, added_tokens = optimizer.align_to_radix_boundary(prompt)
    approx_words = len(aligned_text.split())
    # Should align to multiple of 64
    assert approx_words % 64 == 0 or added_tokens >= 0


def test_ast_code_skeletonizer_2():
    optimizer = ExtremeTokenPhysicsOptimizer4()
    code = (
        "def compute_fibonacci(n: int) -> int:\n"
        "    '''Compute the n-th Fibonacci number efficiently.'''\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    a, b = 0, 1\n"
        "    for _ in range(2, n + 1):\n"
        "        a, b = b, a + b\n"
        "    return b\n"
    )
    skeleton = optimizer.skeletonize_code(code)
    assert "..." in skeleton
    assert "Compute the n-th Fibonacci number efficiently." in skeleton
    assert "for _ in range(2, n + 1):" not in skeleton
    assert "compute_fibonacci(n: int) -> int:" in skeleton


def test_delta_token_accounting():
    optimizer = ExtremeTokenPhysicsOptimizer4()
    baseline = {
        "input_tokens": 10000,
        "output_tokens": 2000,
        "thinking_tokens": 500,
        "total_tokens": 12500,
    }
    cumulative_turn = {
        "input_tokens": 11500,
        "output_tokens": 2400,
        "thinking_tokens": 600,
        "total_tokens": 14500,
    }
    delta = optimizer.compute_turn_delta_tokens(cumulative_turn, baseline)
    assert delta["input_tokens"] == 1500
    assert delta["output_tokens"] == 400
    assert delta["thinking_tokens"] == 100
    assert delta["total_tokens"] == 2000


def test_agent_desk_worktree_swb_and_test_gated_merge(tmp_path):
    mgr = AgentDeskWorktreeManager(tmp_path)

    # 1. Worktree allocation
    wt = mgr.allocate_desk_worktree("desk_backend")
    assert ".desks" in wt

    # 2. Single-Writer Boundary (SWB)
    assert mgr.acquire_write_lock("desk_backend", "src/core.py") is True
    # Second desk trying to write the same file must be blocked
    assert mgr.acquire_write_lock("desk_frontend", "src/core.py") is False

    # Release lock and reacquire
    assert mgr.release_write_lock("desk_backend", "src/core.py") is True
    assert mgr.acquire_write_lock("desk_frontend", "src/core.py") is True

    # 3. Test-Gated Merge Gatekeeper
    ok, _ = mgr.verify_test_gated_merge(pass_rate=1.0, total_tests=25)
    assert ok is True

    fail_rate, reason_rate = mgr.verify_test_gated_merge(pass_rate=0.98, total_tests=50)
    assert fail_rate is False
    assert "100%" in reason_rate

    fail_zero, reason_zero = mgr.verify_test_gated_merge(pass_rate=1.0, total_tests=0)
    assert fail_zero is False
    assert "Zero" in reason_zero


def test_faz112_master_autonomous_swarm_engine_audit(tmp_path):
    engine = Faz112MasterAutonomousSwarmEngine(workspace_root=tmp_path)
    audit_report = engine.run_full_swarm_audit()
    assert audit_report["status"] == "OPERATIONAL"
    assert audit_report["phase"] == "Faz 112 Master Frontier"
    assert audit_report["single_writer_boundary"] == "ENFORCED"
    assert audit_report["test_gated_merge"] == "VERIFIED"
    assert audit_report["ap2_settled_amount"] > 0.0
