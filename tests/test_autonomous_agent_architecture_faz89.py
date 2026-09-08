"""
Unit tests for Faz 89 Autonomous Agent Architecture.
Validates:
1. Faz89A2AAgentCardRegistry (A2A Protocol, Agent Cards, Capability Discovery, Task Dispatch & SHA-256 Artifacts).
2. ModelContextProtocolBridge (MCP Tool Registry, Schema Validation, Sandboxed Execution).
3. pgvector08_TwoPhaseBQReranker (1-Bit BQ Hamming Filter, Iterative Scan, Cosine + Ebbinghaus Reranking).
4. RadixContextEngineeringGovernor (Anchored Prefix Caching, Token Budgeting, Diff-Editing Compression).
5. Faz89AutonomousAgentOrchestrator (End-to-End Autonomous Lifecycle Verification).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    Faz89AgentCard,
    A2ACapability,
    Faz89A2AAgentCardRegistry,
    ModelContextProtocolBridge,
    pgvector08_TwoPhaseBQReranker,
    RadixContextEngineeringGovernor,
    Faz89AutonomousAgentOrchestrator
)


def test_a2a_agent_card_registry():
    registry = Faz89A2AAgentCardRegistry()

    card1 = Faz89AgentCard(
        name="code_architect",
        version="2.0.0",
        description="Software Architect Agent",
        endpoint="a2a://entropy/architect",
        capabilities=[
            A2ACapability("design_patterns", "Generates architecture design"),
            A2ACapability("system_audit", "Audits microservices")
        ]
    )

    card2 = Faz89AgentCard(
        name="test_sentinel",
        version="1.5.0",
        description="QA and Verification Sentinel",
        endpoint="a2a://entropy/sentinel",
        capabilities=[
            A2ACapability("pytest_verification", "Runs automated test harnesses")
        ]
    )

    registry.register_agent_card(card1)
    registry.register_agent_card(card2)

    # 1. Serialization to /.well-known/agent.json
    wk_json = card1.to_well_known_json()
    assert '"name": "code_architect"' in wk_json
    assert '"design_patterns"' in wk_json

    # 2. Capability Discovery
    architects = registry.discover_agents_for_capability("design_patterns")
    assert len(architects) == 1
    assert architects[0].name == "code_architect"

    testers = registry.discover_agents_for_capability("pytest_verification")
    assert len(testers) == 1
    assert testers[0].name == "test_sentinel"

    assert len(registry.discover_agents_for_capability("unknown_cap")) == 0

    # 3. Task Dispatch
    task = registry.dispatch_a2a_task(
        sender="code_architect",
        target="test_sentinel",
        capability="pytest_verification",
        args={"suite": "tests/test_harness.py"}
    )
    assert task.status == "RUNNING"
    assert task.sender_agent == "code_architect"
    assert task.target_agent == "test_sentinel"

    # 4. Artifact Fulfillment with SHA-256 seal
    artifact = registry.fulfill_a2a_task(
        task_id=task.task_id,
        artifact_payload={"exit_code": 0, "pass_rate": 1.0}
    )
    assert task.status == "COMPLETED"
    assert "sha256_seal" in artifact
    assert len(artifact["sha256_seal"]) == 64
    assert artifact["payload"]["pass_rate"] == 1.0


def test_model_context_protocol_bridge():
    mcp = ModelContextProtocolBridge()

    mcp.register_mcp_tool(
        name="read_project_file",
        description="Reads file contents with sandboxing",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        },
        handler=lambda path: f"Content of {path}"
    )

    tools = mcp.list_mcp_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "read_project_file"
    assert "inputSchema" in tools[0]

    # Tool Execution
    result = mcp.execute_mcp_tool("read_project_file", {"path": "README.md"})
    assert result["isError"] is False
    assert "Content of README.md" in result["content"][0]["text"]

    # Non-existent tool
    err_result = mcp.execute_mcp_tool("invalid_tool", {})
    assert err_result["isError"] is True


def test_pgvector08_two_phase_bq_reranker():
    reranker = pgvector08_TwoPhaseBQReranker(ebbinghaus_half_life_hours=48.0)

    # Insert test knowledge records
    # Dimension = 8 for simplicity
    v1 = [1.0, 0.8, -0.5, -0.2, 0.9, -0.1, 0.4, 0.3]
    v2 = [-0.9, -0.7, 0.6, 0.8, -0.4, 0.5, -0.3, -0.2]
    v3 = [0.9, 0.7, -0.4, -0.1, 0.8, -0.2, 0.3, 0.2] # Very similar to v1

    reranker.insert_record("doc_arch", "Harness Engineering Architecture", v1, ["architecture", "harness"], surprise=0.8, elapsed_hours=2.0)
    reranker.insert_record("doc_unrelated", "Quantum Chemistry Simulation", v2, ["chemistry"], surprise=0.1, elapsed_hours=24.0)
    reranker.insert_record("doc_desks", "Agent Desks Worktree Isolation", v3, ["architecture", "desks"], surprise=0.9, elapsed_hours=1.0)

    # Search with query vector close to v1/v3
    query = [0.95, 0.85, -0.45, -0.15, 0.88, -0.12, 0.35, 0.25]

    results = reranker.two_phase_search(
        query_vector=query,
        filter_tag="architecture",
        candidate_k=5,
        final_k=2
    )

    assert len(results) == 2
    # doc_unrelated should be filtered out because tag='architecture'
    doc_ids = [r["doc_id"] for r in results]
    assert "doc_arch" in doc_ids
    assert "doc_desks" in doc_ids
    assert "doc_unrelated" not in doc_ids

    # Scores should be high cosine + modulated
    assert results[0]["modulated_score"] > 0.8


def test_radix_context_engineering_governor():
    gov = RadixContextEngineeringGovernor()

    system_rules = "You are Entropy AI. Always follow deterministic harness rules and git worktree isolation. " * 3
    tools = "tool_1: view_slice, tool_2: apply_patch, tool_3: execute_cmd, tool_4: verify, tool_5: audit, tool_6: diff"
    memory = "Recent memory: Previous test passed with 100% pass rate in desk_01."
    user_prompt = "Refactor the module to use A2A agent card registry."

    budget = gov.evaluate_token_budget(system_rules, tools, memory, user_prompt)
    assert budget["total_tokens"] > 0
    assert budget["static_prefix_tokens"] == budget["breakdown"]["system_tokens"] + budget["breakdown"]["tool_tokens"]
    assert budget["cache_hit_rate"] > 0.0
    assert budget["token_cost_savings_pct"] > 50.0

    # Diff editing savings
    original_code = "def foo():\n" + "\n".join([f"    x_{i} = {i}" for i in range(50)]) + "\n    return 0\n"
    edited_code = original_code.replace("return 0", "return 42")

    diff_metrics = gov.compute_diff_editing_savings(original_code, edited_code)
    assert diff_metrics["token_savings_pct"] > 60.0
    assert diff_metrics["diff_tokens"] < diff_metrics["full_rewrite_tokens"]


def test_faz89_autonomous_agent_orchestrator():
    orchestrator = Faz89AutonomousAgentOrchestrator(embedding_dim=8)

    cycle_id = "cycle_faz89_prod_01"
    goal = "Synthesize and verify A2A Protocol & pgvector 0.8+ integration"
    source_code = "def faz89_entry():\n    return 'verified_and_stable'\n"
    system_rules = "System: Strict A2A Protocol and Radix attention context."
    tool_schemas = "view_slice, apply_patch, execute_sandbox_cmd, verify_tests"
    user_prompt = "Implement Faz 89 autonomous lifecycle."
    query_vector = [0.5, 0.4, -0.2, 0.1, 0.6, -0.3, 0.2, 0.1]

    memory_records = [
        ("mem_1", "A2A Agent Cards and Task Artifacts", [0.48, 0.39, -0.18, 0.12, 0.58, -0.28, 0.19, 0.09], ["a2a", "standards"]),
        ("mem_2", "pgvector 0.8+ Binary Quantization", [0.52, 0.41, -0.21, 0.09, 0.61, -0.31, 0.21, 0.11], ["database", "vector"])
    ]

    result = orchestrator.execute_faz89_autonomous_cycle(
        cycle_id=cycle_id,
        goal=goal,
        source_code=source_code,
        system_instructions=system_rules,
        tool_schemas=tool_schemas,
        user_prompt=user_prompt,
        query_vector=query_vector,
        memory_records=memory_records,
        simulate_test_pass=True
    )

    assert result["status"] == "FAZ89_AUTONOMOUS_CYCLE_COMPLETE"
    assert "a2a_protocol" in result
    assert len(result["a2a_protocol"]["sha256_seal"]) == 64
    assert result["mcp_layer"]["tools_available"] >= 1
    assert result["pgvector_08"]["recalled_count"] >= 1
    assert result["context_engineering"]["diff_savings"]["token_savings_pct"] > 0.0
    assert result["faz88_subsystem"]["overall_integrity"] == "VERIFIED_100_PERCENT"
