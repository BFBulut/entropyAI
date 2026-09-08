"""
Automated Test Suite for Faz 111 Master Autonomous Agent Architecture
====================================================================
Verifies all Faz 111 invariants:
- A2A Protocol v1.0.0 Handshake, Agent Cards & HMAC Authentication
- Erlang-OTP Supervision Trees (One-for-One, One-for-All, Rest-for-One, Churn Limiting)
- Code-as-Action (CodeAct) Virtual Sandbox & AST Pre-Flight Security
- Penta-Store Hybrid Retrieval (Dense, Sparse, LightRAG, HippoRAG 2, Graphiti) & RRF-4
- Radix-Cache 64-Token Alignment, AST Skeletonizer & Delta Token Accounting
- Faz 111 Master Autonomous Swarm Orchestrator End-to-End Self-Audit
"""

import math
import time
import pytest
from src.entropy.tools.autonomous_agent_architecture_faz111 import (
    A2AProtocolEngine,
    A2ATaskDelegationRequest,
    A2ATaskStatus,
    AgentCard,
    CodeActVirtualSandbox,
    Faz111MasterAutonomousSwarmEngine,
    OTPSupervisorTree,
    PentaStoreRetriever,
    RadixCachePromptOptimizer,
    SupervisorStrategy,
)


def test_a2a_agent_card_and_discovery():
    engine = A2AProtocolEngine()
    card = AgentCard(
        agent_id="dev_agent_01",
        name="Developer Specialist",
        version="1.0.0",
        description="High precision python developer",
        skills=["python", "pytest", "fastapi"],
        endpoints={"tasks": "/tasks", "health": "/health"},
        token_rate_per_k=0.02,
        max_concurrency=2,
    )
    engine.register_agent(card)
    assert engine.get_agent_card("dev_agent_01") is not None

    card_json = engine.generate_well_known_agent_card_json("dev_agent_01")
    assert "https://a2a-protocol.org/schemas/v1.0.0/agent-card.json" in card_json
    assert "dev_agent_01" in card_json
    assert "Developer Specialist" in card_json


def test_a2a_task_delegation_handshake_and_hmac():
    engine = A2AProtocolEngine()
    card = AgentCard(
        agent_id="qa_agent",
        name="QA Tester",
        version="1.0.0",
        description="Tester",
        skills=["pytest"],
        endpoints={"tasks": "/tasks"},
        token_rate_per_k=0.01,
        max_concurrency=2,
        is_active=True,
    )
    engine.register_agent(card)

    task_id = "task_verify_001"
    valid_sig = engine.sign_payload(task_id)

    # 1. Invalid signature
    bad_req = A2ATaskDelegationRequest(
        task_id=task_id,
        sender_id="orch",
        target_id="qa_agent",
        payload={"test": "run"},
        token_budget=1000,
        deadline_epoch_s=time.time() + 100,
        signature="invalid_signature",
    )
    bad_resp = engine.delegate_task(bad_req)
    assert bad_resp.status == A2ATaskStatus.REJECTED
    assert "HMAC" in bad_resp.status_detail

    # 2. Target offline / unregistered
    offline_req = A2ATaskDelegationRequest(
        task_id=task_id,
        sender_id="orch",
        target_id="nonexistent_agent",
        payload={"test": "run"},
        token_budget=1000,
        deadline_epoch_s=time.time() + 100,
        signature=valid_sig,
    )
    offline_resp = engine.delegate_task(offline_req)
    assert offline_resp.status == A2ATaskStatus.REJECTED

    # 3. Deadline expired
    expired_req = A2ATaskDelegationRequest(
        task_id=task_id,
        sender_id="orch",
        target_id="qa_agent",
        payload={"test": "run"},
        token_budget=1000,
        deadline_epoch_s=time.time() - 10,
        signature=valid_sig,
    )
    expired_resp = engine.delegate_task(expired_req)
    assert expired_resp.status == A2ATaskStatus.REJECTED
    assert "expired" in expired_resp.status_detail

    # 4. Valid delegation
    valid_req = A2ATaskDelegationRequest(
        task_id=task_id,
        sender_id="orch",
        target_id="qa_agent",
        payload={"test": "run"},
        token_budget=1000,
        deadline_epoch_s=time.time() + 100,
        signature=valid_sig,
    )
    valid_resp = engine.delegate_task(valid_req)
    assert valid_resp.status == A2ATaskStatus.QUEUED
    assert valid_resp.assigned_desk == ".desks/desk_qa_agent"


def test_a2a_task_status_transitions_and_artifacts():
    engine = A2AProtocolEngine()
    card = AgentCard(
        agent_id="coder",
        name="Coder",
        version="1.0.0",
        description="Coder",
        skills=["python"],
        endpoints={"tasks": "/tasks"},
        token_rate_per_k=0.02,
        max_concurrency=1,
    )
    engine.register_agent(card)

    task_id = "task_dev_99"
    sig = engine.sign_payload(task_id)
    req = A2ATaskDelegationRequest(
        task_id=task_id,
        sender_id="orch",
        target_id="coder",
        payload={"task": "build feature"},
        token_budget=2000,
        deadline_epoch_s=time.time() + 300,
        signature=sig,
    )
    engine.delegate_task(req)

    t1 = engine.transition_task_status(task_id, A2ATaskStatus.IN_PROGRESS, "Started coding", tokens=100)
    assert t1.status == A2ATaskStatus.IN_PROGRESS
    assert t1.tokens_consumed == 100

    t2 = engine.transition_task_status(
        task_id,
        A2ATaskStatus.COMPLETED,
        "Finished",
        artifact={"diff": "+ def foo(): pass"},
        tokens=150,
    )
    assert t2.status == A2ATaskStatus.COMPLETED
    assert t2.tokens_consumed == 250
    assert t2.result_artifact["diff"] == "+ def foo(): pass"


def test_otp_supervisor_strategies():
    # ONE_FOR_ONE
    sup_one = OTPSupervisorTree(strategy=SupervisorStrategy.ONE_FOR_ONE)
    sup_one.register_child("c1", "role1")
    sup_one.register_child("c2", "role2")
    res1 = sup_one.handle_crash("c1", "Division by zero")
    assert res1["action"] == "RESTARTED"
    assert res1["restarted_agents"] == ["c1"]

    # ONE_FOR_ALL
    sup_all = OTPSupervisorTree(strategy=SupervisorStrategy.ONE_FOR_ALL)
    sup_all.register_child("c1", "role1")
    sup_all.register_child("c2", "role2")
    res_all = sup_all.handle_crash("c1", "Database lock")
    assert res_all["action"] == "RESTARTED"
    assert set(res_all["restarted_agents"]) == {"c1", "c2"}

    # REST_FOR_ONE
    sup_rest = OTPSupervisorTree(strategy=SupervisorStrategy.REST_FOR_ONE)
    sup_rest.register_child("c1", "role1")
    sup_rest.register_child("c2", "role2")
    sup_rest.register_child("c3", "role3")
    res_rest = sup_rest.handle_crash("c2", "Worker crashed")
    assert res_rest["action"] == "RESTARTED"
    assert res_rest["restarted_agents"] == ["c2", "c3"]


def test_otp_supervisor_max_restarts_churn_prevention():
    sup = OTPSupervisorTree(strategy=SupervisorStrategy.ONE_FOR_ONE, max_restarts=2, window_seconds=60.0)
    sup.register_child("flaky_agent", "tester")

    # 1st crash: OK
    r1 = sup.handle_crash("flaky_agent")
    assert r1["action"] == "RESTARTED"

    # 2nd crash: OK
    r2 = sup.handle_crash("flaky_agent")
    assert r2["action"] == "RESTARTED"

    # 3rd crash: Exceeds max_restarts=2 -> HALT_TREE
    r3 = sup.handle_crash("flaky_agent")
    assert r3["action"] == "HALT_TREE"
    assert sup.tree_crashed is True


def test_codeact_ast_security_inspection():
    sandbox = CodeActVirtualSandbox()

    # Safe code
    safe_code = (
        "import json\n"
        "data = {'values': [10, 20, 30]}\n"
        "result = sum(data['values'])\n"
    )
    is_safe, err = sandbox.inspect_ast(safe_code)
    assert is_safe is True
    assert err is None

    # Forbidden call (eval)
    unsafe_eval = "x = eval('2 + 2')"
    is_safe, err = sandbox.inspect_ast(unsafe_eval)
    assert is_safe is False
    assert "Forbidden call 'eval'" in err

    # Forbidden import (subprocess)
    unsafe_sub = "import subprocess\nsubprocess.run(['dir'])"
    is_safe, err = sandbox.inspect_ast(unsafe_sub)
    assert is_safe is False
    assert "Forbidden import module 'subprocess'" in err


def test_codeact_sandboxed_execution():
    sandbox = CodeActVirtualSandbox()
    code = (
        "data = [1, 2, 3, 4, 5]\n"
        "squared = [x ** 2 for x in data]\n"
        "result = {'sum': sum(squared), 'count': len(squared)}\n"
    )
    res = sandbox.execute_code(code)
    assert res["success"] is True
    assert res["result"]["sum"] == 55
    assert res["result"]["count"] == 5
    assert res["duration_ms"] > 0.0


def test_penta_store_rrf4_hybrid_retrieval():
    store = PentaStoreRetriever()
    store.insert_fact(
        doc_id="fact_a",
        content="PostgreSQL pgvector supports halfvec for 50% index compression",
        dense_vec=[1.0, 0.0, 0.0],
        keywords=["pgvector", "halfvec", "compression"],
        entities=["pgvector", "PostgreSQL"],
        community_theme="database",
    )
    store.insert_fact(
        doc_id="fact_b",
        content="Obsidian markdown vault acts as a bidirectional exocortex",
        dense_vec=[0.0, 1.0, 0.0],
        keywords=["obsidian", "exocortex", "markdown"],
        entities=["Obsidian"],
        community_theme="memory",
    )

    results = store.query_penta_store(
        query_vec=[0.9, 0.1, 0.0],
        query_terms=["halfvec", "compression"],
        query_entities=["pgvector"],
        query_theme="database",
    )
    assert len(results) == 2
    assert results[0]["doc_id"] == "fact_a"
    assert results[0]["rrf_score"] > results[1]["rrf_score"]


def test_penta_store_bi_temporal_invalidation():
    store = PentaStoreRetriever()
    store.insert_fact(
        doc_id="old_fact",
        content="A2A protocol is currently in draft v0.3",
        dense_vec=[0.5, 0.5, 0.5],
        keywords=["a2a", "draft"],
        entities=["A2A"],
        community_theme="protocols",
    )
    store.insert_fact(
        doc_id="new_fact",
        content="A2A protocol reached stable v1.0.0 under Linux Foundation",
        dense_vec=[0.5, 0.5, 0.5],
        keywords=["a2a", "v1.0.0", "stable"],
        entities=["A2A", "Linux Foundation"],
        community_theme="protocols",
    )

    # Invalidate old fact
    invalidated = store.invalidate_contradictory_fact("old_fact", "new_fact")
    assert invalidated is True

    # Query without include_invalidated
    active_res = store.query_penta_store(
        query_vec=[0.5, 0.5, 0.5],
        query_terms=["a2a"],
        query_entities=["A2A"],
        include_invalidated=False,
    )
    doc_ids = [r["doc_id"] for r in active_res]
    assert "new_fact" in doc_ids
    assert "old_fact" not in doc_ids

    # Query with include_invalidated
    all_res = store.query_penta_store(
        query_vec=[0.5, 0.5, 0.5],
        query_terms=["a2a"],
        query_entities=["A2A"],
        include_invalidated=True,
    )
    all_doc_ids = [r["doc_id"] for r in all_res]
    assert "new_fact" in all_doc_ids
    assert "old_fact" in all_doc_ids


def test_radix_cache_boundary_and_ast_skeletonizer():
    # Cache alignment
    text = "Short system prompt"
    aligned = RadixCachePromptOptimizer.align_to_cache_boundary(text, block_size_tokens=64)
    # block size in chars is 64 * 4 = 256
    assert len(aligned) % 256 == 0
    assert aligned.startswith(text)

    # Skeletonizer
    code = (
        "def compute_fibonacci(n: int) -> int:\n"
        "    '''Computes n-th fibonacci number iteratively.'''\n"
        "    a, b = 0, 1\n"
        "    for _ in range(n):\n"
        "        a, b = b, a + b\n"
        "    return a\n"
    )
    skeleton = RadixCachePromptOptimizer.skeletonize_code(code)
    assert "..." in skeleton
    assert "Computes n-th fibonacci number iteratively." in skeleton
    assert "a, b = 0, 1" not in skeleton

    # Delta tokens
    delta = RadixCachePromptOptimizer.compute_delta_tokens(1000, 1450)
    assert delta == 450
    assert RadixCachePromptOptimizer.compute_delta_tokens(1450, 1400) == 0


def test_faz111_master_swarm_self_audit():
    swarm = Faz111MasterAutonomousSwarmEngine()
    audit_report = swarm.run_self_audit()
    assert audit_report["status"] == "HEALTHY"
    assert audit_report["phase"] == "Faz 111 Master Frontier"
    assert audit_report["codeact_sandbox"] == "OPERATIONAL"
    assert audit_report["penta_store"] == "OPERATIONAL"
    assert audit_report["token_physics"] == "OPERATIONAL"
    assert audit_report["otp_supervisor"] == "OPERATIONAL"
    assert audit_report["task_audit_status"] == "COMPLETED"
