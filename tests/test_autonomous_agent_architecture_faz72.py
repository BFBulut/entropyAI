"""
Automated Pytest Suite for Faz 72 Autonomous Agent Architecture Modules.
Tests:
1. LightRAGDualLevelEngine (Dual-Level Incremental Knowledge Graph & Intent Routing).
2. ProgressiveDisclosureSkillManager (Metadata Indexing & Dynamic Skill Unfolding).
3. DualLedgerOrchestrator (Task & Progress Ledgers, Stall Detection & Replanning).
4. ACPEditorProtocolAdapter (Zed & JetBrains Agent Client Protocol JSON-RPC 2.0).
5. SupabaseBQDiskANNEstimator (Binary Quantization 1-bit & Hamming Pre-filtering).
6. Full Integrated Faz 72 Autonomous Governance Pipeline.
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    LightRAGDualLevelEngine,
    ProgressiveDisclosureSkillManager,
    DualLedgerOrchestrator,
    ACPEditorProtocolAdapter,
    SupabaseBQDiskANNEstimator,
    AgentCard,
    A2ANegotiationEngine,
    TaskContract,
    TaskFSMState,
)


def test_lightrag_dual_level_indexing_and_routing():
    engine = LightRAGDualLevelEngine()

    # Index Low-Level Entities
    engine.index_entity(
        entity_id="ast_preflight",
        entity_type="Guardrail",
        description="Deterministic syntax and AST validation guardrail before code execution.",
        linked_entities=["agent_harness", "python_parser"],
        community_id="safety_core"
    )
    engine.index_entity(
        entity_id="agent_harness",
        entity_type="Architecture",
        description="Runtime execution environment governing LLM actions, tools, and state transitions.",
        linked_entities=["ast_preflight", "oodav_loop"],
        community_id="harness_core"
    )

    # Index High-Level Community
    engine.index_community(
        community_id="safety_core",
        theme="Autonomous Safety & Determinism",
        summary="Comprehensive cluster covering AST pre-flight kalkanı, process isolation, and sandboxing.",
        entity_ids=["ast_preflight"]
    )
    engine.index_community(
        community_id="harness_core",
        theme="Harness Engineering Architecture",
        summary="Holistic framework implementing Model + Harness paradigm for deterministic agents.",
        entity_ids=["agent_harness"]
    )

    # Test Intent Routing
    assert engine.route_query_intent("mimari özet ve genel mimari nedir?") == "HIGH_LEVEL"
    assert engine.route_query_intent("hangi fonksiyon AST doğrulaması yapar?") == "LOW_LEVEL"
    assert engine.route_query_intent("ast_preflight mimari yapısı") == "HYBRID"

    # Test Retrieval
    results = engine.retrieve("ast_preflight validation", top_k=2)
    assert len(results["low_level_results"]) > 0
    assert results["low_level_results"][0]["entity_id"] == "ast_preflight"


def test_progressive_disclosure_skill_manager():
    sm = ProgressiveDisclosureSkillManager()

    sm.register_skill(
        skill_id="ast_scanner",
        name="AST Security Scanner",
        description="Scans python source code for dangerous calls like eval/exec.",
        trigger_keywords=["security", "ast", "scan", "vulnerability"],
        full_instructions="Parse AST tree using ast.parse and traverse nodes checking for ForbiddenCalls.",
        required_permissions=["read"],
        scripts=["scan_ast.py"]
    )

    sm.register_skill(
        skill_id="supabase_vector_search",
        name="Supabase Vector Searcher",
        description="Queries Supabase pgvector using halfvec and BQ pre-filtering.",
        trigger_keywords=["supabase", "vector", "embedding", "pgvector"],
        full_instructions="Connect to pgvector via asyncpg and execute cosine distance query.",
        required_permissions=["network", "read"],
        scripts=["query_pgvector.py"]
    )

    # Check Metadata Index Generation
    meta_prompt = sm.get_metadata_index_prompt()
    assert "## Available Skills" in meta_prompt
    assert "ast_scanner" in meta_prompt
    assert "supabase_vector_search" in meta_prompt

    # Trigger Detection
    matched = sm.match_skills_for_prompt("Please run an AST scan on src/core.py")
    assert "ast_scanner" in matched
    assert "supabase_vector_search" not in matched

    # Skill Unfolding
    disclosed = sm.disclose_skill("ast_scanner")
    assert disclosed["level"] == "DISCLOSED_FULL"
    assert "Parse AST tree" in disclosed["instructions"]
    assert "scan_ast.py" in disclosed["available_scripts"]

    # Calculate Progressive Disclosure Savings
    savings = sm.calculate_progressive_savings(
        total_skills_count=40,
        active_skills_count=2,
        avg_skill_full_tokens=1000,
        metadata_tokens_per_skill=40
    )
    # Monolithic: 40 * 1000 = 40,000 tokens
    # Disclosed: (40 * 40) + (2 * 1000) = 1600 + 2000 = 3,600 tokens
    assert savings["monolithic_tokens"] == 40000
    assert savings["disclosed_tokens"] == 3600
    assert savings["savings_percent"] > 90.0
    assert savings["compression_ratio"] > 10.0


def test_dual_ledger_orchestration_and_stall_detection():
    orchestrator = DualLedgerOrchestrator(stall_threshold=3)

    # Initialize Task Ledger
    orchestrator.initialize_task_ledger(
        goal="Autonomous Refactoring of Database Layer",
        constraints=["Zero-downtime", "100% test pass rate", "Max 5000 tokens per turn"],
        plan_steps=["Step 1: AST Scan", "Step 2: Schema Migration", "Step 3: Test Verification"]
    )

    # Step 1: Success
    orchestrator.record_step_execution(
        step_id="step_1",
        worker_agent="CodeArchitect",
        action="Run AST scanner",
        success=True,
        output_summary="AST scan clean, 0 syntax errors."
    )
    health = orchestrator.evaluate_health_and_replanning()
    assert not health["is_stalled"]
    assert health["action_decision"] == "CONTINUE_EXECUTION"

    # Introduce consecutive failures
    orchestrator.record_step_execution("step_2a", "CodeArchitect", "Apply diff", False, "Merge conflict on index.lock")
    orchestrator.record_step_execution("step_2b", "CodeArchitect", "Apply diff retry", False, "Syntax error in patch")
    orchestrator.record_step_execution("step_2c", "CodeArchitect", "Apply diff retry 2", False, "AST validation rejected")

    health_stalled = orchestrator.evaluate_health_and_replanning()
    assert health_stalled["is_stalled"]
    assert health_stalled["consecutive_failures"] == 3
    assert health_stalled["action_decision"] == "DYNAMIC_REPLAN_TRIGGERED"

    # Successful recovery clears stall
    orchestrator.record_step_execution("step_2_recovery", "MasterOrchestrator", "Re-synthesize spec", True, "Clean patch generated")
    health_recovered = orchestrator.evaluate_health_and_replanning()
    assert not health_recovered["is_stalled"]
    assert health_recovered["consecutive_failures"] == 0


def test_acp_editor_protocol_adapter():
    adapter = ACPEditorProtocolAdapter()

    # Test ACP Initialize
    init_res = adapter.handle_initialize(
        request_id=1,
        client_info={"name": "Zed-Editor", "version": "0.180"}
    )
    assert init_res["jsonrpc"] == "2.0"
    assert init_res["result"]["protocolVersion"] == "ACP/1.0"
    assert init_res["result"]["agentInfo"]["capabilities"]["diffStreaming"] is True
    assert init_res["result"]["clientAcknowledged"] == "Zed-Editor"

    # Test Format File Edit Request
    edit_req = adapter.format_file_edit_request(
        session_id="sess_123",
        file_path="src/main.py",
        diff_patch="@@ -1,3 +1,3 @@\n-old\n+new",
        req_id=42
    )
    assert edit_req["jsonrpc"] == "2.0"
    assert edit_req["method"] == "workspace/applyEdit"
    assert edit_req["params"]["filePath"] == "src/main.py"
    assert edit_req["params"]["requiresUserConfirmation"] is True


def test_supabase_bq_diskann_estimator():
    estimator = SupabaseBQDiskANNEstimator()

    # Test storage estimation for 1,000,000 vectors at 1536 dims
    res_1m = estimator.estimate_vector_storage(vector_count=1_000_000, dimensions=1536)
    assert res_1m["fp32_mb"] > 5500.0  # ~5859 MB
    assert res_1m["halfvec_fp16_mb"] < 3000.0  # ~2929 MB
    assert res_1m["bq_1bit_mb"] < 200.0  # ~183 MB
    assert res_1m["bq_compression_ratio_vs_fp32"] >= 30.0  # 32x compression

    # Test Hamming Distance
    # Mask A: 0b1101 (13), Mask B: 0b1001 (9) -> Differs in 1 bit (2nd bit)
    hamming_dist = estimator.compute_hamming_distance(0b1101, 0b1001)
    assert hamming_dist == 1

    # Differing in all 4 bits: 0b1111 vs 0b0000
    assert estimator.compute_hamming_distance(0b1111, 0b0000) == 4


def test_full_integrated_faz72_pipeline():
    # 1. Progressive Disclosure detects necessary skill
    sm = ProgressiveDisclosureSkillManager()
    sm.register_skill(
        skill_id="lightrag_ops",
        name="LightRAG Graph Operator",
        description="Indexes and queries dual-level knowledge graphs.",
        trigger_keywords=["graph", "lightrag", "knowledge", "entity"],
        full_instructions="Perform dual-level query routing and PPR exploration."
    )
    matched_skills = sm.match_skills_for_prompt("Index the knowledge graph entities")
    assert "lightrag_ops" in matched_skills
    disclosed = sm.disclose_skill(matched_skills[0])
    assert disclosed["level"] == "DISCLOSED_FULL"

    # 2. LightRAG Dual-Level Knowledge Graph indexes the architecture
    kg = LightRAGDualLevelEngine()
    kg.index_entity("dual_ledger", "Governor", "Orchestrates task vs progress state.")
    kg.index_community("orchestration", "Agentic OS", "Core multi-agent coordination.", ["dual_ledger"])
    query_res = kg.retrieve("dual_ledger governor")
    assert len(query_res["low_level_results"]) > 0

    # 3. Dual-Ledger manages task execution
    orchestrator = DualLedgerOrchestrator()
    orchestrator.initialize_task_ledger("Complete Faz 72 Deployment", ["Strict TDD"], ["Step 1"])
    orchestrator.record_step_execution("step_1", "EntropyAI", "Deploy Faz 72", True, "All tests passing")
    health = orchestrator.evaluate_health_and_replanning()
    assert health["action_decision"] == "CONTINUE_EXECUTION"

    # 4. A2A Negotiation confirms protocol contract
    agent_card = AgentCard(
        name="CodeArchitect",
        version="2.0",
        description="Autonomous static analysis agent",
        capabilities=["ast_analysis", "udiff_editing", "test_synthesis"],
        endpoint="https://agent.local/a2a"
    )
    task = TaskContract(task_id="task_faz72", spec_path="docs/specs/faz72.md")
    negotiation = A2ANegotiationEngine.negotiate_delegation(
        target_agent=agent_card,
        required_capabilities=["ast_analysis", "test_synthesis"],
        task=task
    )
    assert negotiation["handshake_accepted"] is True
    assert negotiation["status"] == "ACCEPTED"
