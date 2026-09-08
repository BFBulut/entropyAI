"""
Automated Pytest Suite for Faz 74 Autonomous Agent Architecture Modules.
Tests:
1. ActorSupervisionEngine (Actor Spawning, Message Passing, Mailbox, Failure Isolation, Restarts, Terminations, Dead-letters).
2. SleepTimeConsolidationEngine (Ebbinghaus Decay, NREM Noise Pruning, REM Dreaming & Semantic Distillation).
3. ProgressiveToolDisclosureEngine (Tier-1 Metadata Index, Tier-2 On-Demand Hydration, Context Token Savings).
4. HarnessOfHarnessesPipeline (End-to-End Orchestration Turn with AST & Tests).
"""

from pathlib import Path
import pytest
from entropy.tools.autonomous_agent_architecture import (
    ActorSupervisionEngine,
    ActorState,
    SupervisionStrategy,
    ActorMessage,
    SleepTimeConsolidationEngine,
    EpisodicMemoryRecord,
    ProgressiveToolDisclosureEngine,
    HarnessOfHarnessesPipeline,
)


def test_actor_supervision_lifecycle_and_messaging():
    engine = ActorSupervisionEngine(strategy=SupervisionStrategy.ONE_FOR_ONE, max_restarts=2)

    # 1. Spawn actors
    actor_arch = engine.spawn_actor("actor_arch", role="Architect")
    actor_test = engine.spawn_actor("actor_test", role="Tester")
    assert actor_arch.state == ActorState.IDLE
    assert actor_test.state == ActorState.IDLE

    # 2. Send message
    msg = ActorMessage(
        msg_id="m1",
        sender_id="actor_arch",
        recipient_id="actor_test",
        payload={"action": "run_test_suite", "target": "src/core"}
    )
    assert engine.send_message(msg) is True
    assert len(actor_test.mailbox) == 1

    # 3. Dead letter routing
    dead_msg = ActorMessage(
        msg_id="m_dead",
        sender_id="actor_arch",
        recipient_id="nonexistent_agent",
        payload={"action": "ping"}
    )
    assert engine.send_message(dead_msg) is False
    assert len(engine.dead_letters) == 1

    # 4. Successful execution
    res = engine.process_next_message(
        "actor_test",
        handler_func=lambda p: f"Executed {p['action']}"
    )
    assert res["status"] == "SUCCESS"
    assert res["result"] == "Executed run_test_suite"
    assert actor_test.processed_count == 1
    assert actor_test.state == ActorState.IDLE

    # 5. Empty mailbox test
    res_empty = engine.process_next_message("actor_test", handler_func=lambda p: None)
    assert res_empty["status"] == "NO_MESSAGES"


def test_actor_supervision_failure_and_healing():
    engine = ActorSupervisionEngine(strategy=SupervisionStrategy.ONE_FOR_ONE, max_restarts=2)
    actor = engine.spawn_actor("flaky_worker", role="Refactorer")

    def failing_handler(payload):
        raise RuntimeError("Simulated crash during code generation")

    # Queue 3 failing messages
    for i in range(3):
        engine.send_message(ActorMessage(
            msg_id=f"fail_{i}",
            sender_id="Supervisor",
            recipient_id="flaky_worker",
            payload={"step": i}
        ))

    # Turn 1: Fails, restarts (failure 1 <= 2)
    r1 = engine.process_next_message("flaky_worker", handler_func=failing_handler)
    assert r1["status"] == "FAILED"
    assert actor.state == ActorState.IDLE
    assert actor.failure_count == 1

    # Turn 2: Fails, restarts (failure 2 <= 2)
    r2 = engine.process_next_message("flaky_worker", handler_func=failing_handler)
    assert r2["status"] == "FAILED"
    assert actor.state == ActorState.IDLE
    assert actor.failure_count == 2

    # Turn 3: Fails, exceeds max restarts -> TERMINATED
    r3 = engine.process_next_message("flaky_worker", handler_func=failing_handler)
    assert r3["status"] == "FAILED"
    assert actor.state == ActorState.TERMINATED
    assert actor.failure_count == 3

    # Sending to terminated actor goes to dead letters
    post_term_msg = ActorMessage(
        msg_id="post_term",
        sender_id="Supervisor",
        recipient_id="flaky_worker",
        payload={}
    )
    assert engine.send_message(post_term_msg) is False
    assert len(engine.dead_letters) == 1


def test_sleep_time_consolidation_nrem_and_rem():
    engine = SleepTimeConsolidationEngine(decay_rate=0.08, retention_threshold=0.30)

    # Prepare episodic logs with varying age, access, and salience
    records = [
        EpisodicMemoryRecord(
            record_id="rec_fresh_critical",
            content="Discovered critical security race condition in file lock",
            hours_ago=2.0,
            access_count=5,
            initial_salience=0.9,
            tags=["security", "race-condition", "locks"]
        ),
        EpisodicMemoryRecord(
            record_id="rec_stale_noise",
            content="User said hello and asked what time it is",
            hours_ago=120.0,
            access_count=1,
            initial_salience=0.1,
            tags=["chitchat"]
        ),
        EpisodicMemoryRecord(
            record_id="rec_medium_salience",
            content="Updated git worktree path to avoid index conflicts",
            hours_ago=10.0,
            access_count=3,
            initial_salience=0.7,
            tags=["git", "worktree", "agent-desks"]
        ),
    ]

    # 1. NREM Phase: Stale noise should be pruned
    nrem_result = engine.run_nrem_phase(records)
    assert nrem_result["pruned_count"] == 1
    assert len(nrem_result["retained_records"]) == 2
    retained_ids = [r.record_id for r in nrem_result["retained_records"]]
    assert "rec_fresh_critical" in retained_ids
    assert "rec_medium_salience" in retained_ids
    assert "rec_stale_noise" not in retained_ids

    # 2. REM Phase: Dream associative wikilinks and distill semantic note
    rem_note = engine.run_rem_dreaming_phase(nrem_result["retained_records"], topic="Autonomous Concurrency")
    assert rem_note.title == "Semantic Doctrine: Autonomous Concurrency"
    assert "[[security]]" in rem_note.wikilinks
    assert "[[git]]" in rem_note.wikilinks
    assert "[[worktree]]" in rem_note.wikilinks
    assert rem_note.derived_from_count == 2
    assert rem_note.retention_score > 0.30
    assert len(engine.consolidated_notes) == 1


def test_progressive_tool_disclosure_token_efficiency():
    engine = ProgressiveToolDisclosureEngine()

    # Register 10 tools with 400 schema tokens each (4000 tokens monolithic)
    engine.register_tool(
        tool_id="git_worktree_manager",
        summary="Creates and manages git worktrees for agent isolation",
        tags=["git", "worktree", "desk", "vcs"],
        schema={"type": "object", "properties": {"branch": {"type": "string"}}},
        tokens=400
    )
    engine.register_tool(
        tool_id="ast_preflight_verifier",
        summary="Validates Python syntax tree before disk commit",
        tags=["ast", "syntax", "linter", "python"],
        schema={"type": "object", "properties": {"code": {"type": "string"}}},
        tokens=400
    )
    engine.register_tool(
        tool_id="supabase_vector_search",
        summary="Performs 1-bit binary quantized vector retrieval",
        tags=["vector", "embedding", "supabase", "database"],
        schema={"type": "object", "properties": {"query": {"type": "string"}}},
        tokens=400
    )
    for i in range(4, 11):
        engine.register_tool(
            tool_id=f"auxiliary_tool_{i}",
            summary=f"Auxiliary management utility {i}",
            tags=[f"aux_{i}", "general"],
            schema={"type": "object", "properties": {"arg": {"type": "string"}}},
            tokens=400
        )

    # 1. Tier 1 Index check
    t1_index = engine.generate_tier1_index()
    assert "git_worktree_manager" in t1_index
    assert "ast_preflight_verifier" in t1_index
    assert "supabase_vector_search" in t1_index

    # 2. Tier 2 Hydration for a specific intent
    hydrated = engine.hydrate_tier2_tools("We need to check python syntax and verify ast before commit")
    assert "ast_preflight_verifier" in hydrated["matched_tools"]
    assert len(hydrated["matched_tools"]) == 1
    assert hydrated["total_monolithic_tokens"] == 4000  # 10 tools * 400
    # Tier 1 index tokens: 10 * 25 = 250, hydrated: 400 -> total 650 tokens
    assert hydrated["total_optimized_tokens"] < 1000
    assert hydrated["savings_percent"] > 75.0


def test_harness_of_harnesses_pipeline_e2e(tmp_path):
    pipeline = HarnessOfHarnessesPipeline(root_repo_path=tmp_path)

    # Register tools
    pipeline.tool_engine.register_tool(
        tool_id="code_writer",
        summary="Writes tested Python code modules",
        tags=["code", "python", "writer"],
        schema={"type": "object"},
        tokens=350
    )

    modified_code = {
        "src/auth.py": "def verify_token(token: str) -> bool:\n    return len(token) > 8\n"
    }

    episodic_logs = [
        EpisodicMemoryRecord(
            record_id="ep_auth_impl",
            content="Auth token verifier implemented with length checking",
            hours_ago=1.0,
            access_count=4,
            initial_salience=0.8,
            tags=["auth", "security", "token"]
        ),
        EpisodicMemoryRecord(
            record_id="ep_idle_chat",
            content="Idle ping from healthcheck",
            hours_ago=50.0,
            access_count=1,
            initial_salience=0.1,
            tags=["telemetry"]
        )
    ]

    result = pipeline.run_e2e_project_turn(
        task_id="task_auth_sprint_74",
        task_prompt="Implement and verify python auth token validation",
        modified_code=modified_code,
        episodic_logs=episodic_logs
    )

    assert result["task_id"] == "task_auth_sprint_74"
    assert result["actor_status"] == "SUCCESS"
    assert result["desk_status"] == "SUCCESS"
    assert result["ast_verified"] is True
    assert result["tests_passed"] is True
    assert result["retained_memories"] == 1  # Idle chat pruned
    assert "Semantic Doctrine" in result["dreamed_semantic_note"]
