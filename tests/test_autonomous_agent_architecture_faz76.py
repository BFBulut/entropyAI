"""
Automated Pytest Suite for Faz 76 Autonomous Agent Architecture Modules.
Tests:
1. CircuitBreakerEngine (Identical call tripping, cyclic 2-tool oscillation, max turn steps, reset).
2. DAGProjectTaskManager (Task DAG, Kahn's topological sort, cycle detection, dependency resolution).
3. LightRAGDualLevelIndexer (Low-level entities + High-level themes, dual-level retrieval).
4. JITToolRegistry (Just-in-Time dynamic tool discovery, keyword matching, token minimization).
5. Faz76MasterAutonomousPipeline (End-to-end integration: DAG + JIT + Breaker + LightRAG + Desk).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    CircuitBreakerEngine,
    CircuitBreakerStatus,
    DAGProjectTaskManager,
    ProjectTaskNode,
    LightRAGDualLevelIndexer,
    JITToolRegistry,
    Faz76MasterAutonomousPipeline,
    AgentCard,
)


def test_circuit_breaker_engine_identical_calls():
    breaker = CircuitBreakerEngine(max_identical_actions=3, max_steps_per_turn=10)

    # 1st call - NORMAL
    res1 = breaker.record_action("grep_search", {"query": "auth_token"})
    assert res1["is_safe"] is True
    assert res1["status"] == CircuitBreakerStatus.NORMAL.value

    # 2nd identical call - WARNING
    res2 = breaker.record_action("grep_search", {"query": "auth_token"})
    assert res2["is_safe"] is True
    assert res2["status"] == CircuitBreakerStatus.WARNING.value

    # 3rd identical call - TRIPPED
    res3 = breaker.record_action("grep_search", {"query": "auth_token"})
    assert res3["is_safe"] is False
    assert res3["status"] == CircuitBreakerStatus.TRIPPED.value
    assert "Consecutive identical tool call loop" in res3["tripped_reason"]
    assert "EMERGENCY_STOP" in res3["directive"]

    # Reset
    breaker.reset()
    assert breaker.status == CircuitBreakerStatus.NORMAL
    assert len(breaker.action_history) == 0


def test_circuit_breaker_engine_cyclic_oscillation():
    breaker = CircuitBreakerEngine(max_identical_actions=5, max_steps_per_turn=20)

    # Oscillating: A -> B -> A -> B -> A -> B
    for _ in range(3):
        breaker.record_action("read_file", {"path": "main.py"})
        breaker.record_action("read_file", {"path": "config.py"})

    verdict = breaker._build_verdict()
    assert verdict["is_safe"] is False
    assert verdict["status"] == CircuitBreakerStatus.TRIPPED.value
    assert "Cyclic 2-tool alternating oscillation" in verdict["tripped_reason"]


def test_dag_project_task_manager():
    manager = DAGProjectTaskManager()

    # Create tasks:
    # task_spec -> task_code -> task_test -> task_deploy
    #          \-> task_docs -/
    manager.add_task("task_spec", "Write Architecture Spec", "spec content", dependencies=[])
    manager.add_task("task_code", "Synthesize Code", "code content", dependencies=["task_spec"])
    manager.add_task("task_docs", "Generate Docs", "docs content", dependencies=["task_spec"])
    manager.add_task("task_test", "Run Test Suite", "test content", dependencies=["task_code"])
    manager.add_task("task_deploy", "Deploy Artifacts", "deploy content", dependencies=["task_test", "task_docs"])

    # 1. Topological order
    order = manager.get_topological_order()
    assert order[0] == "task_spec"
    assert order[-1] == "task_deploy"
    assert order.index("task_code") < order.index("task_test")
    assert order.index("task_docs") < order.index("task_deploy")

    # 2. Ready tasks initially (only task_spec has 0 deps)
    ready1 = manager.get_ready_tasks()
    assert len(ready1) == 1
    assert ready1[0].task_id == "task_spec"

    # Complete task_spec
    manager.complete_task("task_spec", {"artifact": "spec.md"})
    assert manager.tasks["task_spec"].status == "COMPLETED"

    # Now both task_code and task_docs become ready
    ready2 = manager.get_ready_tasks()
    ready_ids = [t.task_id for t in ready2]
    assert "task_code" in ready_ids
    assert "task_docs" in ready_ids

    # 3. Cycle Detection
    cyclic_mgr = DAGProjectTaskManager()
    cyclic_mgr.add_task("t1", "Task 1", "...", dependencies=["t2"])
    cyclic_mgr.add_task("t2", "Task 2", "...", dependencies=["t1"])
    with pytest.raises(ValueError, match="Cycle detected"):
        cyclic_mgr.get_topological_order()


def test_lightrag_dual_level_indexer():
    indexer = LightRAGDualLevelIndexer()

    indexer.index_document(
        doc_id="doc_auth",
        title="OAuth2 Security Gateway",
        content="Handles token exchange, PKCE flow, and JWT verification for subagents.",
        low_level_entities=["OAuth2", "PKCE", "JWT", "verify_token", "AuthGateway"],
        high_level_themes=["Authentication", "Zero Trust", "Security Architecture"],
        vector=[1.0, 0.0, 0.0]
    )

    indexer.index_document(
        doc_id="doc_cache",
        title="Prefix KV Cache Economics",
        content="RadixAttention and Anthropic byte-identical prefix caching reduces token costs by 90%.",
        low_level_entities=["KV Cache", "RadixAttention", "prefix_hash", "TokenPhysics"],
        high_level_themes=["Context Optimization", "Token Physics", "Cost Engineering"],
        vector=[0.0, 1.0, 0.0]
    )

    res = indexer.dual_retrieve(
        query_text="How to authenticate with JWT and verify token in security gateway",
        query_entities=["JWT", "verify_token"],
        query_themes=["Authentication", "Security Architecture"],
        query_vector=[0.9, 0.1, 0.0],
        top_k=1
    )

    assert len(res["top_results"]) == 1
    top_doc = res["top_results"][0]
    assert top_doc["doc_id"] == "doc_auth"
    assert "jwt" in [e.lower() for e in top_doc["matched_entities"]]
    assert "authentication" in [t.lower() for t in top_doc["matched_themes"]]
    assert "=== HIGH-LEVEL CONTEXT ===" in res["dual_grounding_prompt"]
    assert "=== LOW-LEVEL DETAILS ===" in res["dual_grounding_prompt"]


def test_jit_tool_registry():
    registry = JITToolRegistry()

    # Register 4 tools
    registry.register_tool(
        name="grep_search",
        description="Search codebase using regular expressions",
        tags=["search", "regex", "code", "file"],
        schema={"properties": {"query": {"type": "string"}}}
    )
    registry.register_tool(
        name="edit_file",
        description="Edit code lines in a target file",
        tags=["code", "edit", "modify", "patch"],
        schema={"properties": {"path": {"type": "string"}, "content": {"type": "string"}}}
    )
    registry.register_tool(
        name="run_sql_query",
        description="Execute analytical queries on PostgreSQL Supabase database",
        tags=["database", "sql", "postgres", "supabase"],
        schema={"properties": {"query": {"type": "string"}}}
    )
    registry.register_tool(
        name="deploy_cluster",
        description="Provision Kubernetes cluster pods",
        tags=["kubernetes", "infra", "deploy", "cluster"],
        schema={"properties": {"manifest": {"type": "string"}}}
    )

    # Prompt matching database tool
    res = registry.resolve_tools_for_prompt("Please query postgres database via SQL", max_tools=2)
    assert "run_sql_query" in res["selected_tool_names"]
    assert "deploy_cluster" not in res["selected_tool_names"]
    assert res["token_savings_percent"] > 0.0
    assert res["selected_token_cost"] < res["baseline_token_cost"]


def test_faz76_master_autonomous_pipeline():
    pipeline = Faz76MasterAutonomousPipeline()

    # Register tools into JIT registry
    pipeline.jit_tools.register_tool(
        name="synthesize_module",
        description="Synthesizes Python modules with AST verification",
        tags=["python", "module", "ast", "code"],
        schema={"properties": {"code": {"type": "string"}}}
    )
    pipeline.jit_tools.register_tool(
        name="cloud_billing",
        description="Audit AWS cloud billing metrics",
        tags=["cloud", "billing", "aws"],
        schema={"properties": {"account": {"type": "string"}}}
    )

    # Index memory
    pipeline.light_rag.index_document(
        doc_id="doc_arch",
        title="Microkernel Agent OS",
        content="The microkernel isolates tasks into ephemeral worktrees.",
        low_level_entities=["Microkernel", "EphemeralDesk", "Worktree"],
        high_level_themes=["Architecture", "Isolation"],
        vector=[1.0, 0.0]
    )

    # Add task to DAG
    pipeline.dag_manager.add_task(
        task_id="step_76_01",
        title="Synthesize Core Worker",
        spec_content="Build Python worker module with AST validation"
    )

    agent_card = AgentCard(
        agent_id="code_agent_76",
        name="CodeArchitect 76",
        version="2026.2",
        capabilities=["code_synthesis", "ast_refactor"]
    )

    valid_code = {
        "service.py": "def handle_request(req: dict) -> dict:\n    return {'status': 200}\n"
    }

    turn_res = pipeline.run_autonomous_project_step(
        task_id="step_76_01",
        system_instructions="You are Entropy AI Faz 76 Master Orchestrator.",
        user_prompt="Synthesize python module service.py with AST validation",
        agent_card=agent_card,
        entities=["Microkernel", "EphemeralDesk"],
        themes=["Architecture"],
        files_to_generate=valid_code
    )

    assert turn_res["task_id"] == "step_76_01"
    assert turn_res["task_status"] == "COMPLETED"
    assert turn_res["commit_status"] == "COMMITTED"
    assert "synthesize_module" in turn_res["selected_tools"]
    assert "cloud_billing" not in turn_res["selected_tools"]
    assert turn_res["tool_savings_pct"] > 0.0
    assert turn_res["cache_savings_pct"] > 0.0
    assert turn_res["dual_rag_results_count"] >= 1
    assert turn_res["circuit_breaker_status"] == "NORMAL"
