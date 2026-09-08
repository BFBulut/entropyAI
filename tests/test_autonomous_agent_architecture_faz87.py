"""
Unit tests for Faz 87 Autonomous Agent Architecture.
Validates:
1. A2AAgentDiscoveryNegotiator (Linux Foundation AAIF A2A v1.0 Agent Cards and Zero-Chat Artifact Channel).
2. MiniSWEScaffoldingEngine (Minimalist SWE Scaffolding and Closed-Loop Test-Driven Self-Correction).
3. LateChunkingBinaryQuantizer (Jina AI Late Chunking and Supabase pgvector 0.8+ 1-Bit Binary Quantization).
4. AgentDeskWorktreeOrchestrator (Multi-tenant Git Worktrees, Non-Colliding Ports and Test-Gated Merge).
5. Faz87MasterAutonomousArchitectureSystem (End-to-end unified autonomous cycle with 100% integrity).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    A2AAgentDiscoveryNegotiator,
    MiniSWEScaffoldingEngine,
    LateChunkingBinaryQuantizer,
    AgentDeskWorktreeOrchestrator,
    Faz87MasterAutonomousArchitectureSystem
)


def test_a2a_agent_discovery_negotiator():
    negotiator = A2AAgentDiscoveryNegotiator()

    # 1. Registration
    card1 = negotiator.register_agent_card(
        agent_id="agent_planner",
        card_data={
            "name": "Planner Agent",
            "protocol_version": "1.0.0",
            "capabilities": ["task_planning", "code_review"],
            "endpoints": ["stdio://planner"]
        }
    )
    assert card1["agent_id"] == "agent_planner"
    assert "fingerprint_sha256" in card1
    assert len(card1["fingerprint_sha256"]) == 64

    card2 = negotiator.register_agent_card(
        agent_id="agent_coder",
        card_data={
            "name": "Coder Agent",
            "protocol_version": "1.0.0",
            "capabilities": ["code_refactor", "code_review"],
            "endpoints": ["stdio://coder"]
        }
    )
    assert card2["agent_id"] == "agent_coder"

    # Invalid registration without mandatory fields
    with pytest.raises(ValueError):
        negotiator.register_agent_card("bad_agent", {"name": "Bad"})

    # 2. Discovery
    reviewers = negotiator.discover_compatible_agents("code_review")
    assert len(reviewers) == 2
    planners = negotiator.discover_compatible_agents("task_planning")
    assert len(planners) == 1
    assert planners[0]["agent_id"] == "agent_planner"

    # 3. Negotiation Handshake
    handshake = negotiator.negotiate_handshake("agent_planner", "agent_coder", "session_alpha")
    assert handshake["session_id"] == "session_alpha"
    assert handshake["protocol"] == "A2A_v1.0.0"
    assert "code_review" in handshake["shared_capabilities"]
    assert handshake["transport"] == "ZERO_CHAT_ARTIFACT_PIPELINE"

    # 4. Zero-Chat Artifact Pipeline
    payload = {"patch": "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-print('hello')\n+print('world')", "status": "READY"}
    artifact = negotiator.create_zero_chat_artifact(
        artifact_type="CODE_PATCH",
        title="Fix Greeting Patch",
        payload=payload,
        sender_id="agent_coder",
        recipient_id="agent_planner"
    )
    assert artifact["artifact_type"] == "CODE_PATCH"
    assert artifact["token_savings_pct"] >= 80.0
    assert negotiator.verify_artifact_integrity(artifact) is True

    # Tampered artifact verification
    tampered = dict(artifact)
    tampered["payload"] = {"malicious": True}
    assert negotiator.verify_artifact_integrity(tampered) is False


def test_mini_swe_scaffolding_engine():
    engine = MiniSWEScaffoldingEngine(max_allowed_loc=120)

    # 1. Atomic Actions
    res_view = engine.execute_action_step("view_slice", {"path": "main.py", "start": 1, "end": 20})
    assert res_view["status"] == "VIEW_OK"

    res_patch = engine.execute_action_step("apply_patch", {"path": "main.py", "patch": "+ def foo(): pass"})
    assert res_patch["status"] == "PATCH_APPLIED"

    res_cmd = engine.execute_action_step("execute_sandbox_cmd", {"cmd": "python -m py_compile main.py"})
    assert res_cmd["status"] == "CMD_COMPLETED"

    res_test = engine.execute_action_step("verify_tests", {"suite": "pytest", "exit_code": 0})
    assert res_test["status"] == "TESTS_PASSED"

    # 2. Closed-Loop Self-Correction
    attempt_counter = [0]
    def faulty_runner(code: str):
        attempt_counter[0] += 1
        if attempt_counter[0] >= 2 or "Fix applied" in code:
            return 0, "pytest: 5 passed"
        return 1, "SyntaxError: missing colon on line 4"

    repair_res = engine.run_closed_loop_repair(
        goal="Fix syntax error on line 4",
        target_file="test_code.py",
        initial_code="def broken()\n    pass",
        test_runner_func=faulty_runner,
        max_turns=4
    )
    assert repair_res["status"] == "REPAIR_SUCCEEDED"
    assert repair_res["turns_taken"] <= 2
    assert "Fix applied" in repair_res["final_code"]
    assert repair_res["scaffolding_overhead_loc"] <= 120


def test_late_chunking_binary_quantizer():
    quantizer = LateChunkingBinaryQuantizer(default_dim=16)

    # 1. Late Chunking
    text = (
        "Entropy AI coordinates autonomous agents with Agent Desks and git worktrees. "
        "Late chunking applies global attention across entire documents before chunk pooling. "
        "1-Bit Binary Quantization packs 1536 float32 dimensions into 192 bytes for 32x RAM reduction."
    )
    chunks = quantizer.simulate_late_chunking(text, chunk_size_words=10, embedding_dim=16)
    assert len(chunks) >= 2
    assert all(chunk["is_late_chunked"] is True for chunk in chunks)
    assert len(chunks[0]["pooled_vector"]) == 16

    # 2. 1-Bit BQ Packing
    vec = [0.5, -0.2, 1.1, -3.0, 0.0, 0.9, -0.1, -0.4, 0.8, -0.8, 0.2, 0.3, -0.5, -0.6, 0.7, 0.1]
    bq_result = quantizer.quantize_1bit_bq(vec)
    assert bq_result["dim"] == 16
    assert bq_result["raw_bytes_len"] == 2  # 16 bits = 2 bytes
    assert len(bq_result["bq_bytes"]) == 2

    # 3. Hamming Distance
    b1 = bytes([0b10101010, 0b11001100])
    b2 = bytes([0b10101010, 0b11001100])  # Identical
    assert quantizer.compute_hamming_distance(b1, b2) == 0

    b3 = bytes([0b01010101, 0b00110011])  # Completely opposite
    assert quantizer.compute_hamming_distance(b1, b3) == 16

    # 4. Two-Stage Hybrid Retrieval
    query = [0.5, 0.5, 0.5, 0.5, -0.5, -0.5, -0.5, -0.5, 0.5, 0.5, 0.5, 0.5, -0.5, -0.5, -0.5, -0.5]
    results = quantizer.two_stage_hybrid_search(
        query_vec=query,
        candidate_docs=chunks,
        top_k_fast=3,
        top_k_rerank=2
    )
    assert len(results) <= 2
    assert "hamming_dist" in results[0]
    assert "cosine_sim" in results[0]
    assert results[0]["retrieval_stage"] == "STAGE2_RERANKED"


def test_agent_desk_worktree_orchestrator():
    orchestrator = AgentDeskWorktreeOrchestrator(start_port=4200, max_ports=10)

    # 1. Desk Allocation
    desk1 = orchestrator.allocate_agent_desk("agent_a", "task_101")
    assert desk1["desk_id"] == "desk_agent_a_task_101"
    assert desk1["allocated_port"] == 4200
    assert "git worktree add -b" in desk1["git_command_add"]
    assert desk1["status"] == "DESK_ACTIVE"

    desk2 = orchestrator.allocate_agent_desk("agent_b", "task_102")
    assert desk2["allocated_port"] == 4201

    assert len(orchestrator.get_active_desks()) == 2

    # 2. Test-Gated Merge - Passing Case
    merge_pass = orchestrator.verify_test_gated_merge(desk1, test_passed=True, test_output="All 10 tests passed")
    assert merge_pass["status"] == "MERGE_APPROVED"
    assert "git worktree remove" in merge_pass["cleanup_cmd"]

    # 3. Test-Gated Merge - Failing Case (Rollback Sentinel)
    merge_fail = orchestrator.verify_test_gated_merge(desk2, test_passed=False, test_output="AssertionError on line 20")
    assert merge_fail["status"] == "ROLLBACK_TRIGGERED"
    assert "git branch -D" in merge_fail["cleanup_cmd"]


def test_faz87_master_autonomous_architecture_system():
    system = Faz87MasterAutonomousArchitectureSystem(embedding_dim=8)

    doc = (
        "Linux Foundation AAIF A2A v1.0 standardizes agent-to-agent collaboration and zero-chat artifacts. "
        "Mini-SWE scaffolding provides lean execution primitives to maximize SWE-bench accuracy. "
        "Supabase pgvector 1-Bit Binary Quantization reduces vector RAM by 32x with POPCNT Hamming pre-filtering. "
        "Agent Desk worktrees provide isolated git workspaces with test-gated merges and rollback sentinels."
    )
    triples = [
        ("Entropy AI", "implements", "A2A Protocol"),
        ("A2A Protocol", "reduces", "Token Overhead"),
        ("Entropy AI", "utilizes", "Mini-SWE Scaffolding"),
        ("pgvector", "supports", "1-Bit Binary Quantization")
    ]

    result = system.execute_faz87_autonomous_cycle(
        cycle_id="faz87_prod_validation",
        goal="Demonstrate full Faz 87 Autonomous Lifecycle with A2A, Mini-SWE, 1-Bit BQ and Agent Desks",
        source_code="def autonomous_worker():\n    return 'pass'\n",
        system_instructions="Operate autonomously under AAIF A2A and Mini-SWE constraints.",
        invariant_rules="Enforce 100% test pass rate and Zero-Chat artifact integrity.",
        conversation_history=[
            {"role": "user", "content": "How do we coordinate agents without massive token overhead?"},
            {"role": "assistant", "content": "Use AAIF A2A Zero-Chat artifacts and Agent Desk worktrees."}
        ],
        knowledge_doc=doc,
        openie_triples=triples,
        seed_concept="Entropy AI",
        query_vector=[0.2] * 8,
        memory_vectors=[("mem_faz87", [0.2] * 8, {"title": "Faz 87 Specs"})],
        simulate_test_pass=True,
        cumulative_tokens_snapshot={"input_tokens": 48000, "output_tokens": 12000}
    )

    assert result["status"] == "FAZ87_AUTONOMOUS_CYCLE_COMPLETE"
    assert result["overall_integrity"] == "VERIFIED_100_PERCENT"
    assert result["a2a_v1_protocol"]["artifact_integrity_verified"] is True
    assert result["a2a_v1_protocol"]["token_savings_pct"] >= 80.0
    assert result["agent_desk_worktree"]["merge_result"]["status"] == "MERGE_APPROVED"
    assert result["mini_swe_scaffolding"]["status"] == "REPAIR_SUCCEEDED"
    assert result["hybrid_rag_bq"]["late_chunks_count"] > 0
    assert result["faz86_core"]["overall_integrity"] == "VERIFIED_100_PERCENT"
