"""
Unit tests for Faz 88 Autonomous Agent Architecture.
Validates:
1. AutonomousAgentFleetSupervisor (Role Specialization, FSM Task Contracts, Zero-Chat Artifact Handoffs).
2. DeltaTokenPhysicsGovernor (Delta Token Accounting, RadixAttention Cache Hit Estimation, Sliding Window Compaction).
3. CognitiveMemoryTriStore (Obsidian Markdown Wikilinks, 1-Bit BQ POPCNT Hamming Search, Ebbinghaus Decay).
4. AgentDeskSandboxSentinel (Git Worktree Desk Allocation, Non-Colliding Ports, Test-Gated Merge & Rollback Sentinel).
5. Faz88MasterAutonomousArchitectureSystem (End-to-End Autonomous Lifecycle Verification).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    AgentRole,
    AutonomousAgentFleetSupervisor,
    DeltaTokenPhysicsGovernor,
    CognitiveMemoryTriStore,
    AgentDeskSandboxSentinel,
    Faz88MasterAutonomousArchitectureSystem,
    TaskFSMState
)


def test_autonomous_agent_fleet_supervisor():
    supervisor = AutonomousAgentFleetSupervisor()

    # 1. Swarm Registration
    node1 = supervisor.register_swarm_agent("coder_alpha", AgentRole.CODER, ["python_codegen", "refactor"])
    assert node1.agent_id == "coder_alpha"
    assert node1.role == AgentRole.CODER
    assert node1.status == "IDLE"

    node2 = supervisor.register_swarm_agent("tester_beta", AgentRole.TESTER, ["pytest_exec", "security_audit"])
    assert node2.agent_id == "tester_beta"
    assert node2.role == AgentRole.TESTER

    # 2. Capability Matching
    matched_coder = supervisor.find_best_agent_for_task("python_codegen")
    assert matched_coder is not None
    assert matched_coder.agent_id == "coder_alpha"

    matched_tester = supervisor.find_best_agent_for_task("security_audit")
    assert matched_tester is not None
    assert matched_tester.agent_id == "tester_beta"

    assert supervisor.find_best_agent_for_task("non_existent_capability") is None

    # 3. Task Dispatch
    dispatch = supervisor.create_and_dispatch_task(
        task_id="task_build_service",
        spec_path="specs/task_build_service.md",
        required_capability="python_codegen",
        assigned_desk="desk_1"
    )
    assert dispatch["status"] == "DISPATCHED"
    assert dispatch["worker_id"] == "coder_alpha"
    assert dispatch["contract"].state == TaskFSMState.IN_PROGRESS
    assert matched_coder.status == "BUSY"

    # Cannot dispatch again to busy worker
    with pytest.raises(RuntimeError):
        supervisor.create_and_dispatch_task(
            task_id="task_2",
            spec_path="specs/task_2.md",
            required_capability="python_codegen",
            assigned_desk="desk_2"
        )

    # 4. Zero-Chat Artifact Handoff
    handoff = supervisor.transmit_zero_chat_handoff(
        sender_id="coder_alpha",
        recipient_id="tester_beta",
        task_id="task_build_service",
        payload={"diff": "+ def run(): pass", "status": "READY_FOR_TEST"}
    )
    assert "sha256_hash" in handoff
    assert len(handoff["sha256_hash"]) == 64
    assert handoff["token_savings_pct"] >= 75.0

    # 5. Task Completion & Freeing Worker
    supervisor.complete_task("task_build_service", success=True, reason="All tests passed")
    contract = supervisor.task_registry["task_build_service"]
    assert contract.state == TaskFSMState.COMPLETED
    assert matched_coder.status == "IDLE"
    assert matched_coder.current_task_id is None


def test_delta_token_physics_governor():
    governor = DeltaTokenPhysicsGovernor(max_turns_before_rotation=3, token_ceiling=50000)

    # 1. Delta Accounting Turn 1
    snap1 = {"input_tokens": 1000, "output_tokens": 200}
    turn1 = governor.compute_turn_delta(snap1)
    assert turn1["turn_index"] == 1
    assert turn1["delta_input_tokens"] == 1000
    assert turn1["delta_output_tokens"] == 200
    assert turn1["turn_total_tokens"] == 1200
    assert turn1["needs_session_rotation"] is False

    # Turn 2: Cumulative increases
    snap2 = {"input_tokens": 2500, "output_tokens": 600}
    turn2 = governor.compute_turn_delta(snap2)
    assert turn2["turn_index"] == 2
    assert turn2["delta_input_tokens"] == 1500
    assert turn2["delta_output_tokens"] == 400
    assert turn2["turn_total_tokens"] == 1900
    assert turn2["needs_session_rotation"] is False

    # Turn 3: Hits max_turns_before_rotation = 3
    snap3 = {"input_tokens": 3200, "output_tokens": 800}
    turn3 = governor.compute_turn_delta(snap3)
    assert turn3["turn_index"] == 3
    assert turn3["needs_session_rotation"] is True
    assert turn3["rotation_reason"] == "MAX_TURNS_REACHED"

    # 2. RadixAttention Cache Hit Estimation
    rules = "Mandatory System Prompt Rules: Always use TDD, never use lambdas for slots." * 10
    tools = "tool1(param: str), tool2(code: str), tool3(path: str)" * 5
    prompt = "Write a fast prime factorization algorithm"
    cache_est = governor.estimate_prefix_cache_hit_rate(rules, tools, prompt)
    assert cache_est["cache_hit_rate_pct"] >= 70.0
    assert cache_est["is_cache_optimized"] is True

    # 3. Context Compaction
    history = [
        {"role": "user", "content": "How do we initialize the project?"},
        {"role": "assistant", "content": "Run pip install and initialize git repository."},
        {"role": "user", "content": "What about the database schema?"},
        {"role": "assistant", "content": "Use SQLite for desks and Supabase for cognitive memory."},
        {"role": "user", "content": "Now implement the token governor."},
        {"role": "assistant", "content": "Implementing DeltaTokenPhysicsGovernor now."}
    ]
    compacted = governor.generate_compacted_context_summary(history, keep_recent_count=2)
    assert compacted["compacted"] is True
    assert compacted["evicted_count"] == 4
    assert len(compacted["active_messages"]) == 2
    assert "CONVERSATION_SUMMARY" in compacted["summary"]

    # 4. Windows Process Tree Termination Command
    kill_cmd = governor.get_windows_process_tree_kill_command(1234)
    assert kill_cmd == "taskkill /F /T /PID 1234"


def test_cognitive_memory_tri_store():
    tri_store = CognitiveMemoryTriStore(embedding_dim=16, default_decay_half_life_hours=48.0)

    # 1. Obsidian Markdown Note Formatting
    note = tri_store.format_obsidian_markdown_note(
        title="Autonomous_Harness_Specs",
        tags=["specs", "harness", "agentic_os"],
        content="Autonomous harnesses wrap LLM probabilistic engines in deterministic state machines.",
        wikilinks=["MEMORY", "BELLEK_HARITASI", "Agent_Desks"]
    )
    assert "[[MEMORY]]" in note["content"]
    assert "[[Agent_Desks]]" in note["content"]
    assert "title: Autonomous_Harness_Specs" in note["content"]

    # 2. 1-Bit Binary Quantization & POPCNT Hamming
    vec_a = [1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
    vec_b = [1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
    vec_c = [-1.0, -1.0, -1.0, -1.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0]

    bq_a = tri_store.quantize_1bit_bq(vec_a)
    bq_b = tri_store.quantize_1bit_bq(vec_b)
    bq_c = tri_store.quantize_1bit_bq(vec_c)

    assert len(bq_a) == 2
    assert tri_store.popcnt_hamming_distance(bq_a, bq_b) == 0
    assert tri_store.popcnt_hamming_distance(bq_a, bq_c) == 16

    # 3. Memory Indexing & Ebbinghaus Decay
    tri_store.index_memory("mem_recent", "Recent critical design pattern", vec_a, surprise_score=0.8, elapsed_hours=2.0)
    tri_store.index_memory("mem_old", "Old deprecated protocol note", vec_a, surprise_score=0.1, elapsed_hours=200.0)
    tri_store.index_memory("mem_different", "Completely different topic", vec_c, surprise_score=0.5, elapsed_hours=10.0)

    recent_retention = tri_store.compute_ebbinghaus_retention(elapsed_hours=2.0, surprise_score=0.8)
    old_retention = tri_store.compute_ebbinghaus_retention(elapsed_hours=200.0, surprise_score=0.1)
    assert recent_retention > old_retention

    # 4. Hybrid Two-Stage Recall
    recalled = tri_store.hybrid_recall(query_vector=vec_a, top_k_stage1=3, top_k_final=2)
    assert len(recalled) == 2
    assert recalled[0]["memory_id"] == "mem_recent"
    assert recalled[0]["hamming_distance"] == 0
    assert recalled[0]["cognitive_score"] > recalled[1]["cognitive_score"]


def test_agent_desk_sandbox_sentinel():
    sentinel = AgentDeskSandboxSentinel(base_port=4400, workspace_root="c:/EntropiAI")

    # 1. Desk Allocation
    desk1 = sentinel.allocate_isolated_desk(agent_id="worker_x", task_id="task_001")
    assert desk1["desk_id"] == "desk_worker_x_task_001"
    assert desk1["assigned_port"] == 4400
    assert "git worktree add -b desks/desk_worker_x_task_001" in desk1["git_worktree_cmd"]
    assert desk1["status"] == "ALLOCATED"

    desk2 = sentinel.allocate_isolated_desk(agent_id="worker_y", task_id="task_002")
    assert desk2["assigned_port"] == 4401

    # 2. Test-Gated Merge Gatekeeper - Passing Tests
    merge_approval = sentinel.verify_and_merge_or_rollback(
        desk_id="desk_worker_x_task_001",
        test_exit_code=0
    )
    assert merge_approval["status"] == "MERGE_APPROVED"
    assert "git merge desks/desk_worker_x_task_001" in merge_approval["git_merge_cmd"]
    assert "git worktree remove" in merge_approval["cleanup_cmd"]

    # 3. Rollback Sentinel - Failing Tests
    rollback_trigger = sentinel.verify_and_merge_or_rollback(
        desk_id="desk_worker_y_task_002",
        test_exit_code=1,
        test_traceback="AssertionError: Test failed on line 42"
    )
    assert rollback_trigger["status"] == "ROLLBACK_TRIGGERED"
    assert "git branch -D" in rollback_trigger["cleanup_cmd"]
    assert "git worktree remove --force" in rollback_trigger["cleanup_cmd"]


def test_faz88_master_autonomous_architecture_system():
    system = Faz88MasterAutonomousArchitectureSystem(embedding_dim=8)

    doc = (
        "Entropy AI Faz 88 implements Enterprise Swarm Supervision with Role-Based Dispatching. "
        "Delta Token Physics provides exact delta token billing and RadixAttention prefix caching. "
        "Cognitive Memory Tri-Store unifies Obsidian markdown, 1-Bit BQ pgvector, and Ebbinghaus decay. "
        "Agent Desk Sandbox Sentinels ensure git worktree isolation with Test-Gated Merges."
    )
    triples = [
        ("Entropy AI", "supervises", "Agent Swarm"),
        ("Delta Token Physics", "eliminates", "Cumulative Token Inflation"),
        ("Cognitive Tri-Store", "indexes", "Obsidian & pgvector"),
        ("Agent Desks", "isolate", "Git Worktrees")
    ]

    result = system.execute_faz88_autonomous_cycle(
        cycle_id="faz88_full_validation",
        goal="Validate complete Faz 88 Industrial Autonomous Multi-Agent Lifecycle",
        source_code="def execute_swarm_task():\n    return 'pass'\n",
        system_instructions="Strictly enforce zero-chat artifact handoffs and test-gated merges.",
        invariant_rules="All pytest suites must pass with 100% pass rate before branch integration.",
        conversation_history=[
            {"role": "user", "content": "How do we coordinate agents autonomously with minimal token waste?"},
            {"role": "assistant", "content": "Use Zero-Chat SHA-256 artifacts and Delta Token Accounting."},
            {"role": "user", "content": "How do we isolate file changes?"},
            {"role": "assistant", "content": "Use Git Worktree Agent Desks with Test-Gated Merge Gatekeepers."}
        ],
        knowledge_doc=doc,
        openie_triples=triples,
        seed_concept="Entropy AI",
        query_vector=[0.3] * 8,
        memory_vectors=[("mem_faz88_core", [0.3] * 8, {"title": "Faz 88 Core Specifications"})],
        simulate_test_pass=True,
        cumulative_tokens_snapshot={"input_tokens": 58000, "output_tokens": 15000}
    )

    assert result["status"] == "FAZ88_AUTONOMOUS_CYCLE_COMPLETE"
    assert result["overall_integrity"] == "VERIFIED_100_PERCENT"
    assert result["fleet_supervision"]["token_savings_pct"] >= 75.0
    assert result["fleet_supervision"]["dispatch"]["status"] == "DISPATCHED"
    assert result["token_physics"]["delta_accounting"]["delta_input_tokens"] == 58000
    assert result["token_physics"]["cache_profile"]["is_cache_optimized"] is True
    assert len(result["tri_store_memory"]["recalled_memories"]) > 0
    assert result["agent_desk_sandbox"]["merge_result"]["status"] == "MERGE_APPROVED"
    assert result["mini_swe_scaffolding"]["status"] == "REPAIR_SUCCEEDED"
    assert result["faz87_subsystem"]["overall_integrity"] == "VERIFIED_100_PERCENT"
