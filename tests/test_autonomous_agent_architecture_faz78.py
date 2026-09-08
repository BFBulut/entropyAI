"""
Automated Pytest Suite for Faz 78 Autonomous Multi-Agent Architecture Modules.
Tests:
1. MagenticDualLedgerGovernor (Outer Task Ledger & Inner Progress Ledger, Stall Detection, Auto-Replan).
2. ContextCompactorEngine (Claude Code pattern, Context Fullness Ratio, Root Invariant Re-injection).
3. A2AProtocolCardRegistry (Linux Foundation AAIF A2A v1.0 standard, Hash Signature Verification, JSON-RPC 2.0 Delegation).
4. Faz78MasterAutonomousArchitecture (E2E Master Cycle: Compactor -> Dual-Ledger -> A2A -> Desk -> Checkpoint -> Commit).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    MagenticDualLedgerGovernor,
    ContextCompactorEngine,
    A2AProtocolCardRegistry,
    Faz78MasterAutonomousArchitecture,
)


def test_magentic_dual_ledger_governor_normal_flow():
    governor = MagenticDualLedgerGovernor(stall_threshold=3)

    plan = governor.initialize_plan(
        objective="Refactor Auth Subsystem for Distributed Agents",
        facts=["PostgreSQL database operational", "JWT tokens configured"],
        initial_steps=[
            "Design auth token verification schema",
            "Synthesize AST-validated middleware",
            "Deploy to isolated test desk"
        ]
    )

    assert plan["objective"] == "Refactor Auth Subsystem for Distributed Agents"
    assert len(plan["strategic_plan"]) == 3
    assert plan["status"] == "INITIALIZED"

    # Step 1 success
    res1 = governor.record_step(
        subtask="Design auth token verification schema",
        agent_name="agent_architect",
        success=True,
        output_data={"schema": "AuthTokenSchema"},
        notes="Schema created cleanly."
    )
    assert res1["action"] == "PROCEED"
    assert res1["consecutive_stalls"] == 0
    assert res1["replan_triggered"] is False

    # Verify task ledger reflected completion
    snapshot = governor.get_ledger_snapshot()
    assert snapshot["task_ledger"]["strategic_plan"][0]["status"] == "COMPLETED"
    assert snapshot["progress_ledger_count"] == 1


def test_magentic_dual_ledger_governor_stall_and_auto_replan():
    governor = MagenticDualLedgerGovernor(stall_threshold=3)

    governor.initialize_plan(
        objective="Compile Native Binary Artifact",
        initial_steps=["Run PyInstaller compiler", "Sign binary", "Package installer"]
    )

    # Simulate 2 consecutive failures -> should still allow retry
    governor.record_step("Run PyInstaller compiler", "agent_compiler", False, notes="Linker error")
    res2 = governor.record_step("Run PyInstaller compiler", "agent_compiler", False, notes="Missing symbol")
    assert res2["action"] == "RETRY_OR_SUBDIVIDE"
    assert res2["consecutive_stalls"] == 2
    assert res2["replan_triggered"] is False

    # 3rd consecutive failure -> trips stall threshold
    res3 = governor.record_step("Run PyInstaller compiler", "agent_compiler", False, notes="Memory overflow")
    assert res3["action"] == "DYNAMIC_REPLAN_TRIGGERED"
    assert res3["replan_triggered"] is True
    assert "replan_details" in res3

    # Verify Task Ledger reformulations
    snapshot = governor.get_ledger_snapshot()
    assert snapshot["task_ledger"]["version"] == 2
    assert snapshot["task_ledger"]["status"] == "REPLANNED"
    assert any("diagnose root failure" in s["description"].lower() for s in snapshot["task_ledger"]["strategic_plan"])
    assert snapshot["consecutive_stalls"] == 0


def test_context_compactor_engine_fullness_and_reinjection():
    compactor = ContextCompactorEngine(context_window_limit=200000, compaction_threshold=0.85)

    compactor.register_root_rule("GEMINI.md", "Direct AGY CLI piping invariant.")
    compactor.register_root_rule("MEMORY.md", "GraphRAG cognitive decision record.")

    mock_history = [
        {"role": "user", "content": "Analyze project architecture and generate migration plan."},
        {"role": "assistant", "content": "Executing static code analysis on repository."},
        {"role": "user", "content": "Now generate database schemas for pgvector."},
        {"role": "assistant", "content": "Synthesized halfvec and binary quantization schemas."},
    ]

    # Case A: Below threshold (e.g. 50,000 / 200,000 = 0.25 < 0.85)
    res_low = compactor.evaluate_and_compact(current_tokens=50000, raw_history=mock_history, force=False)
    assert res_low["status"] == "NO_COMPACTION_NEEDED"
    assert res_low["fullness_ratio"] == 0.25

    # Case B: Exceeding threshold (e.g. 180,000 / 200,000 = 0.90 >= 0.85)
    res_high = compactor.evaluate_and_compact(current_tokens=180000, raw_history=mock_history, force=False)
    assert res_high["status"] == "COMPACTED"
    assert res_high["token_savings_percent"] > 90.0
    assert "GEMINI.md" in res_high["re_injected_rules"]
    assert "MEMORY.md" in res_high["re_injected_rules"]

    # Invariants are physically re-injected as system messages
    compacted_msgs = res_high["compacted_messages"]
    system_contents = [m["content"] for m in compacted_msgs if m["role"] == "system"]
    assert any("Direct AGY CLI piping invariant." in c for c in system_contents)
    assert any("GraphRAG cognitive decision record." in c for c in system_contents)
    assert any("COMPACTED SESSION STATE" in c for c in system_contents)


def test_a2a_protocol_card_registry_and_delegation():
    registry = A2AProtocolCardRegistry()

    # 1. Register Specialist Agent Card
    card = registry.register_agent_card(
        agent_id="agent_db_specialist",
        name="Supabase pgvector Specialist",
        version="1.5.0",
        endpoint="https://agents.entropy.internal/a2a/v1/db",
        capabilities=["pgvector_migration", "hnsw_indexing", "binary_quantization"],
        supported_formats=["application/json", "application/sql"]
    )

    assert card["spec_version"] == "a2a-v1.0.0"
    assert "signature_hash" in card

    # 2. Verify signature integrity
    is_valid, err = registry.verify_agent_card("agent_db_specialist")
    assert is_valid is True
    assert err is None

    # 3. Create Delegation Envelope
    contract = {"task_id": "task_db_01", "action": "optimize_hnsw_indexes"}
    envelope = registry.create_delegation_envelope(
        sender_id="orchestrator_prime",
        receiver_id="agent_db_specialist",
        task_contract=contract,
        required_capability="hnsw_indexing"
    )

    assert envelope["jsonrpc"] == "2.0"
    assert envelope["method"] == "a2a.delegateTask"
    assert envelope["params"]["target_agent"] == "agent_db_specialist"

    # Capability mismatch failure test
    with pytest.raises(ValueError, match="lacks required capability"):
        registry.create_delegation_envelope(
            sender_id="orchestrator_prime",
            receiver_id="agent_db_specialist",
            task_contract=contract,
            required_capability="kubernetes_helm_deploy"
        )

    # 4. Process Task Handoff & Issue Receipt
    receipt = registry.process_task_handoff(envelope)
    assert receipt["status"] == "ACCEPTED"
    assert receipt["contract_accepted"] is True
    assert receipt["receiver"] == "agent_db_specialist"


def test_faz78_master_autonomous_architecture_e2e():
    master = Faz78MasterAutonomousArchitecture(context_limit=100000)

    # Execute complete project cycle with subtasks
    subtasks = [
        "Index repository AST structures",
        "Generate unified diff patch",
        "Execute automated test suite"
    ]

    res = master.run_autonomous_project_cycle(
        project_objective="Build Self-Healing Autonomous Micro-Agent Architecture",
        task_id="task_faz78_project",
        subtasks=subtasks,
        current_tokens=90000,  # 90k / 100k = 90% -> triggers auto-compaction
        raw_history=[
            {"role": "user", "content": "Build Self-Healing Autonomous Micro-Agent Architecture"},
            {"role": "assistant", "content": "Scanning architecture specifications and designing components."}
        ]
    )

    assert res["project_status"] == "COMPLETED"
    assert res["compaction_status"] == "COMPACTED"
    assert res["tokens_after_compaction"] < 2000
    assert res["a2a_receipt_id"].startswith("rec_")
    assert res["desk_id"].startswith("desk_task_faz78_project_")
    assert res["checkpoint_id"].startswith("chk_task_faz78_project_")
    assert res["steps_executed"] == 3
    assert res["commit_status"] == "COMMITTED"

    snapshot = res["task_ledger_snapshot"]
    assert snapshot["task_ledger"]["status"] == "INITIALIZED"
    assert snapshot["progress_ledger_count"] == 3
    assert snapshot["consecutive_stalls"] == 0
