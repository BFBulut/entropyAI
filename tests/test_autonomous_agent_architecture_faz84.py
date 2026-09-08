"""
Unit tests for Faz 84 Autonomous Agent Architecture.
Validates:
1. AgentHarnessACIEngine (Agent-Computer Interface bounded commands & cognitive load reduction).
2. PromptCacheBreakpointOptimizer (Static-First prompt compilation, cache breakpoints & poisoning detection).
3. ContextCompactionGovernor (Anchored Iterative Summarization combating context rot).
4. A2AAgentCardRegistry (Linux Foundation AAIF A2A Protocol v1.0 discovery & delegation).
5. Faz84MasterAutonomousSystem end-to-end autonomous cycle.
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    AgentHarnessACIEngine,
    PromptCacheBreakpointOptimizer,
    ContextCompactionGovernor,
    A2AAgentCardRegistry,
    Faz84MasterAutonomousSystem
)


def test_agent_harness_aci_engine():
    # Test cognitive load comparison
    load_metric = AgentHarnessACIEngine.calculate_cognitive_load(
        command_type="view_window",
        raw_bash_equivalent="cat file.py | grep -n 'def' | tail -n 50"
    )
    assert load_metric["is_bounded_aci"] is True
    assert load_metric["token_reduction_pct"] >= 70.0
    assert load_metric["cognitive_complexity"] == "LOW"

    # Test unbounded command
    unbounded = AgentHarnessACIEngine.calculate_cognitive_load(
        command_type="arbitrary_bash",
        raw_bash_equivalent="bash -c 'find . -name *.py | xargs grep foo'"
    )
    assert unbounded["is_bounded_aci"] is False
    assert unbounded["cognitive_complexity"] == "HIGH_UNBOUNDED"

    # Test bounded window view
    sample_content = "\n".join([f"Line {i} content" for i in range(1, 101)])
    window = AgentHarnessACIEngine.execute_aci_window_view(sample_content, 10, 20)
    assert window["success"] is True
    assert window["returned_lines_count"] == 11
    assert "10: Line 10 content" in window["window_content"]
    assert "20: Line 20 content" in window["window_content"]
    assert "Line 5 content" not in window["window_content"]

    # Test invalid range
    invalid_window = AgentHarnessACIEngine.execute_aci_window_view(sample_content, 50, 40)
    assert invalid_window["success"] is False
    assert "start_line" in invalid_window["error"]


def test_prompt_cache_breakpoint_optimizer():
    optimizer = PromptCacheBreakpointOptimizer()

    sys_instr = "You are Entropy AI, an autonomous software engineering companion."
    tools_manifest = "view_window, replace_file_content, run_sandboxed_test"
    rules = "1. Always verify AST before saving. 2. Delta token accounting is mandatory."
    history = [
        {"role": "user", "content": "Let's inspect the repository."},
        {"role": "assistant", "content": "I'll read config.py."},
        {"role": "user", "content": "What did you find?"},
        {"role": "assistant", "content": "Found configuration models."}
    ]
    query = "Refactor the database driver."

    compilation = optimizer.compile_static_first_prompt(
        system_instructions=sys_instr,
        tool_manifest=tools_manifest,
        invariant_rules=rules,
        dynamic_turn_history=history,
        active_user_query=query
    )

    assert compilation["is_cache_clean"] is True
    assert compilation["static_tokens"] > 0
    assert compilation["dynamic_tokens"] > 0
    assert compilation["cache_hit_ratio_pct"] > 0.0
    assert compilation["cost_savings_pct"] > 0.0
    assert "=== CACHE_BREAKPOINT ===" in compilation["assembled_prompt"]
    assert compilation["cache_breakpoint"]["stable_prefix_bytes"] > 0

    # Test cache poisoning detection
    clean_prefix = "System instructions with static guidelines."
    check_clean = optimizer.detect_cache_poisoning(clean_prefix)
    assert check_clean["is_poisoned"] is False

    poisoned_prefix = "System session started at 2026-09-05 with id 12345678-abcd-1234-abcd-123456789abc"
    check_poison = optimizer.detect_cache_poisoning(poisoned_prefix)
    assert check_poison["is_poisoned"] is True
    assert len(check_poison["poison_reasons"]) >= 1


def test_context_compaction_governor():
    governor = ContextCompactionGovernor()

    # When history is small, no compaction
    short_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"}
    ]
    short_res = governor.compact_conversation_history(short_history, max_active_turns=4)
    assert short_res["compacted"] is False
    assert len(short_res["active_messages"]) == 2

    # Long history with decisions, errors, and file references
    long_history = [
        {
            "role": "user",
            "content": "Start task in src/entropy/core/config.py. We need to evaluate whether the application configuration should be persisted using SQLite or Pydantic V2 JSON models. Let's analyze disk access latency and schema migration overhead across multiple runs."
        },
        {
            "role": "assistant",
            "content": "We thoroughly evaluated disk access times and decided that pydantic v2 settings provide the cleanest zero-dependency persistence without requiring complex SQLite WAL management or schema migration files."
        },
        {
            "role": "user",
            "content": "There was a SyntaxError encountered during execution in main.py, please resolve the indentation issue in the startup routine."
        },
        {
            "role": "assistant",
            "content": "Fixed syntax error in main.py and verified the complete test suite in tests/test_main.py. All assertions now pass cleanly."
        },
        {
            "role": "user",
            "content": "Now look at vault_manager.py and check how research reports are structured and sanitized before writing to Obsidian storage."
        },
        {
            "role": "assistant",
            "content": "Checked reports directory structure in vault_manager.py. The ANSI sanitization regex strips terminal codes and ensures valid frontmatter."
        },
        {"role": "user", "content": "What is next in our plan?"},
        {"role": "assistant", "content": "We need to run pytest across all test suites."},
        {"role": "user", "content": "Did tests pass?"},
        {"role": "assistant", "content": "All 10 tests passed."}
    ]

    compact_res = governor.compact_conversation_history(long_history, max_active_turns=4)
    assert compact_res["compacted"] is True
    assert compact_res["archived_turns_count"] == 6
    assert len(compact_res["active_messages"]) == 5  # 1 system summary + 4 recent turns
    assert compact_res["compression_ratio_pct"] > 30.0

    summary_content = compact_res["active_messages"][0]["content"]
    assert "ANCHORED CONVERSATION SUMMARY" in summary_content
    assert "config.py" in summary_content or "main.py" in summary_content


def test_a2a_agent_card_registry():
    registry = A2AAgentCardRegistry()

    # Register an agent
    card = registry.register_agent_card(
        agent_id="test-architect",
        name="Architect Subagent",
        role="Code Analysis",
        capabilities=["ast_parsing", "graph_generation"],
        endpoint_url="a2a://local/test-architect"
    )
    assert card["agent_id"] == "test-architect"
    assert card["status"] == "ACTIVE"
    assert card["$schema"] == "https://a2a-protocol.org/schemas/v1/agent-card.json"

    # Create task delegation envelope
    envelope = registry.create_delegation_envelope(
        sender_agent_id="entropy-orchestrator",
        recipient_agent_id="test-architect",
        task_id="task-99",
        task_goal="Refactor AST Parser",
        spec_artifact="# Spec 99\nEnsure zero syntax errors."
    )
    assert envelope["jsonrpc"] == "2.0"
    assert envelope["method"] == "a2a.delegateTask"
    assert envelope["params"]["recipient"] == "test-architect"

    # Accept delegation
    ack = registry.process_delegation_acceptance(envelope, accept=True, reason="Ready to execute.")
    assert ack["result"]["accepted"] is True
    assert ack["result"]["task_id"] == "task-99"

    # Delegation to non-existent agent should raise KeyError
    with pytest.raises(KeyError):
        registry.create_delegation_envelope(
            sender_agent_id="entropy-orchestrator",
            recipient_agent_id="unknown-ghost-agent",
            task_id="task-100",
            task_goal="Do nothing",
            spec_artifact=""
        )


def test_faz84_master_autonomous_system_cycle():
    dim = 8  # lightweight embedding dim for fast test execution
    system = Faz84MasterAutonomousSystem(embedding_dim=dim)

    sample_code = '''
def calculate_metrics(values: list) -> dict:
    """Calculates summary statistics."""
    total = sum(values)
    count = len(values)
    return {"total": total, "mean": total / count if count else 0}
'''
    history = [
        {"role": "user", "content": "Inspect src/entropy/core/config.py and decisions."},
        {"role": "assistant", "content": "Decided to keep config immutable."},
        {"role": "user", "content": "Encountered minor error in tests."},
        {"role": "assistant", "content": "Resolved error."},
        {"role": "user", "content": "Turn 5"},
        {"role": "assistant", "content": "Turn 6"},
        {"role": "user", "content": "Turn 7"}
    ]

    query_vec = [0.1] * dim
    memory_vecs = [
        ("mem-1", [0.1] * dim, {"category": "architecture"}),
        ("mem-2", [-0.1] * dim, {"category": "debugging"})
    ]

    result = system.execute_faz84_autonomous_cycle(
        cycle_id="cycle-faz84-001",
        goal="Autonomous Optimization & Delegation",
        source_code=sample_code,
        system_instructions="You are Entropy AI Master Orchestrator operating on Windows.",
        invariant_rules="Delta token accounting. Real-time piping. Zero cloud vendor lock-in.",
        conversation_history=history,
        query_concepts={"harness", "cache"},
        query_vector=query_vec,
        memory_vectors=memory_vecs,
        delegate_to_agent="code-architect"
    )

    assert result["status"] == "FAZ84_AUTONOMOUS_CYCLE_COMPLETE"
    assert result["context_compaction"]["compacted"] is True
    assert result["prompt_cache_optimization"]["is_cache_clean"] is True
    assert result["aci_metrics"]["cognitive_complexity"] == "LOW"
    assert result["a2a_delegation"]["envelope"] is not None
    assert result["a2a_delegation"]["acknowledgement"]["result"]["accepted"] is True
    assert result["total_tokens_and_cost_savings"] > 0
