"""
Unit tests for Faz 95 Autonomous Agent Architecture.
Validates:
1. Faz95AutonomousTaskDAGManager (Topological task dependencies, reflection, dynamic re-planning).
2. Faz95GitWorktreeAgentDeskManager (AST memory slicing, sandbox execution, test-gated merge).
3. Faz95A2AMCPHub (A2A v1.0 Agent Cards, Opacity task delegation, SEP-1865 MCP Apps UI).
4. Faz95CognitiveTriStoreMemory (PendingInbox quarantine, 1-Bit BQ POPCNT search, Dreaming consolidation).
5. Faz95TokenPhysicsOptimizer & Faz95MasterAutonomousAgentSystem (APC prompt layout, Code-as-action, Master OS).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    Faz95TaskStatus,
    Faz95TaskNode,
    Faz95AutonomousTaskDAGManager,
    Faz95GitWorktreeAgentDeskManager,
    Faz95A2AMCPHub,
    Faz95CognitiveTriStoreMemory,
    Faz95TokenPhysicsOptimizer,
    Faz95MasterAutonomousAgentSystem
)


def test_faz95_task_dag_lifecycle_and_reflection():
    dag = Faz95AutonomousTaskDAGManager(plan_name="EnterpriseRefactor")

    # 1. Add tasks with dependencies
    # task_plan -> task_code -> task_qa
    dag.add_task("task_plan", "Architectural Plan", assigned_agent="LeadPlanner")
    dag.add_task("task_code", "Code Implementation", assigned_agent="CodeDeveloper", dependencies=["task_plan"])
    dag.add_task("task_qa", "QA Verification", assigned_agent="QASentinel", dependencies=["task_code"], max_retries=2)

    # 2. Initially, only task_plan is ready
    ready = dag.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "task_plan"

    # Start and complete task_plan
    dag.start_task("task_plan")
    dag.complete_task("task_plan", outputs={"spec": "SPEC_V1"})

    # Now task_code is ready
    ready = dag.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "task_code"

    dag.start_task("task_code")
    dag.complete_task("task_code", outputs={"commit": "sha256_abc"})

    # Now task_qa is ready
    ready = dag.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "task_qa"

    # 3. Simulate failure with retry & reflection
    dag.start_task("task_qa")
    fail_res1 = dag.fail_task("task_qa", error_reason="AssertionError: expected 42, got 41")
    assert fail_res1["status"] == "RETRYING"
    assert fail_res1["action"] == "SCHEDULED_RETRY"
    assert "Reflection on failure" in fail_res1["reflection"]

    # Ready again because it's retrying and dependencies are met
    ready = dag.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "task_qa"

    # Complete task_qa
    dag.complete_task("task_qa", outputs={"verdict": "PASSED"})
    assert dag.is_dag_complete() is True
    summary = dag.get_summary()
    assert summary["total_tasks"] == 3
    assert summary["is_complete"] is True


def test_faz95_agent_desks_ast_slicing_and_test_gated_merge():
    desk_mgr = Faz95GitWorktreeAgentDeskManager(repo_path="c:/EntropiAI")
    desk = desk_mgr.create_desk(agent_id="agent_alpha", base_branch="main")

    assert desk["desk_id"] == "desk_agent_alpha"
    assert "desks/desk_agent_alpha" in desk["branch"]

    # 1. AST Working Memory Slicing (Orientation Tax reduction)
    full_module = """
import os
import sys

def helper_a():
    return 1

class OrderRouter:
    def route_order(self, order_id: str) -> bool:
        \"\"\"Routes high frequency order.\"\"\"
        if not order_id:
            return False
        return True

def helper_b():
    return 2
"""
    slice_res = desk_mgr.slice_working_memory(full_code=full_module, target_symbol="OrderRouter")
    assert slice_res["status"] == "SLICED_SUCCESS"
    assert slice_res["target_symbol"] == "OrderRouter"
    assert "class OrderRouter" in slice_res["sliced_code"]
    assert "def helper_a" not in slice_res["sliced_code"]
    assert slice_res["orientation_tax_reduction_pct"] > 30.0

    # 2. Sandboxed execution security check
    sec_violation = desk_mgr.execute_in_sandbox("desk_agent_alpha", "os.system('rm -rf /')")
    assert sec_violation["status"] == "SECURITY_VIOLATION"

    safe_exec = desk_mgr.execute_in_sandbox("desk_agent_alpha", "print('Safe computation')")
    assert safe_exec["status"] == "EXECUTION_SUCCESS"

    # 3. Test-gated merge failure triggers Rollback Sentinel
    desk_mgr.desks["desk_agent_alpha"]["local_files"]["router.py"] = "bad code"
    merge_fail = desk_mgr.test_gated_merge("desk_agent_alpha", test_suite_results={"test_auth": True, "test_perf": False})
    assert merge_fail["status"] == "MERGE_REJECTED"
    assert merge_fail["verdict"] == "ROLLBACK_TRIGGERED"
    assert "test_perf" in merge_fail["failed_tests"]
    assert desk_mgr.desks["desk_agent_alpha"]["status"] == "ROLLED_BACK"

    # 4. Successful test-gated merge
    desk_beta = desk_mgr.create_desk(agent_id="agent_beta")
    desk_mgr.desks["desk_agent_beta"]["local_files"]["core.py"] = "def compute(): return 100"
    merge_pass = desk_mgr.test_gated_merge("desk_agent_beta", test_suite_results={"test_core": True, "test_math": True})
    assert merge_pass["status"] == "MERGE_SUCCESS"
    assert merge_pass["verdict"] == "ATOMIC_MERGE_COMPLETED"
    assert "core.py" in desk_mgr.master_files


def test_faz95_a2a_mcp_hub_opacity_and_apps_ui():
    hub = Faz95A2AMCPHub()

    # 1. Register A2A Agent Card
    card = hub.register_agent_card(
        agent_id="analyst_agent",
        card_data={
            "name": "FinancialAnalystAgent",
            "description": "Performs forensic cash flow analysis",
            "capabilities": ["beneish_m_score", "sloan_accruals"],
            "input_schema": {"ticker": "string"},
            "output_schema": {"m_score": "number", "fraud_risk": "string"}
        }
    )
    assert card["protocol_version"] == "A2A/1.0.0"
    assert "analyst_agent" in hub.agent_registry

    # 2. Delegate task with Opacity guarantee (hiding internal CoT)
    private_thoughts = "I think this company is cooking the books because DSRI > 2.0"
    del_res = hub.delegate_task(
        from_agent="orchestrator",
        to_agent="analyst_agent",
        task_payload={"ticker": "XYZ"},
        private_scratchpad=private_thoughts
    )
    assert del_res["status"] == "ACCEPTED"
    assert del_res["transit_payload"]["opacity_guarantee"] == "PRIVATE_COT_STRIPPED"
    assert del_res["private_scratchpad_leaked"] is False

    # 3. SEP-1865 MCP Apps UI resource
    mcp_app = hub.register_mcp_app_ui(
        resource_uri="ui://financial-dashboard/v1",
        component_html="<div id='root'><canvas id='chart'></canvas></div>"
    )
    assert mcp_app["status"] == "ACTIVE"
    assert "allow-scripts" in mcp_app["sandbox"]

    resolved = hub.resolve_mcp_app_ui("ui://financial-dashboard/v1")
    assert resolved["component_html"] == "<div id='root'><canvas id='chart'></canvas></div>"


def test_faz95_cognitive_tri_store_memory_and_dreaming():
    mem = Faz95CognitiveTriStoreMemory()

    # 1. Working & Episodic memory
    mem.set_scratchpad("current_goal", "Optimize late chunking")
    assert mem.scratchpad["current_goal"] == "Optimize late chunking"

    note = mem.append_daily_note("CodeDeveloper", "Implemented 1-Bit BQ", delta_tokens=340)
    assert note["delta_tokens"] == 340
    assert len(mem.daily_notes) == 1

    # 2. PendingInbox quarantine against Memory Poisoning
    inbox_item = mem.submit_to_pending_inbox(
        insight="Binary Quantization reduces pgvector RAM by 32x",
        source_agent="ResearchAgent",
        confidence=0.98
    )
    assert inbox_item["status"] == "PENDING_AUDIT"
    assert len(mem.pending_inbox) == 1

    # Before approval, not in MEMORY.md
    assert not any("Binary Quantization" in line for line in mem.obsidian_memory_md)

    # Approve and commit
    committed = mem.approve_and_commit_to_memory_md(inbox_item["item_id"])
    assert committed is True
    assert any("Binary Quantization" in line for line in mem.obsidian_memory_md)
    assert any("[[ResearchAgent]]" in line for line in mem.obsidian_memory_md)

    # 3. Supabase pgvector 0.8+ BQ & Iterative Scan simulation
    mem.insert_vector(
        doc_id="doc_1",
        text="FastMCP enables high-performance SSE transports.",
        embedding=[0.9, -0.2, 0.4, -0.8],
        metadata={"category": "protocol", "importance": 0.9}
    )
    mem.insert_vector(
        doc_id="doc_2",
        text="Erlang OTP supervision trees provide actor fault tolerance.",
        embedding=[-0.7, 0.6, -0.5, 0.3],
        metadata={"category": "actor_system", "importance": 0.85}
    )

    query = [0.85, -0.15, 0.35, -0.75]
    results = mem.pgvector_iterative_scan_search(query, category_filter="protocol", top_k=2)
    assert len(results) == 1
    assert results[0]["id"] == "doc_1"
    assert results[0]["cosine_sim"] > 0.95

    # 4. Dreaming cognitive consolidation with Ebbinghaus forgetting curve
    dreaming_res = mem.run_dreaming_consolidation(surprise_threshold=0.1, time_elapsed_days=3.0, memory_strength=10.0)
    assert dreaming_res["ebbinghaus_retention_factor"] > 0.70
    assert dreaming_res["total_daily_notes"] == 1


def test_faz95_token_physics_and_master_os_integration():
    optimizer = Faz95TokenPhysicsOptimizer()

    # 1. APC Prompt Layout
    prompt_data = optimizer.format_apc_prompt(
        system_role="You are Entropy AI, an autonomous multi-agent operating system.",
        skill_cards=[
            {"name": "git_worktree", "description": "Isolates workspaces for subagents"},
            {"name": "a2a_dispatch", "description": "Delegates tasks with opacity"}
        ],
        architecture_spec="Rule: 100% test pass rate required before merge.",
        user_turn="Deploy trading agent to desk 4"
    )
    assert prompt_data["kv_cache_hit_ratio"] > 0.60
    assert prompt_data["ttft_speedup_x"] > 3.0
    assert "[BLOCK 0: SYSTEM IDENTITY" in prompt_data["full_prompt"]
    assert "[BLOCK 3: ACTIVE CONVERSATION TURN]" in prompt_data["full_prompt"]

    # 2. Code-as-Action vs JSON Tool Calling efficiency
    efficiency = optimizer.calculate_code_as_action_efficiency(num_tool_calls=5, avg_json_call_tokens=500)
    assert efficiency["json_tool_tokens"] == 2500
    assert efficiency["code_as_action_tokens"] == 550
    assert efficiency["savings_percentage"] > 75.0

    # 3. Delta Token calculation
    curr = {"input": 12000, "output": 3500, "total": 15500}
    prev = {"input": 10000, "output": 2800, "total": 12800}
    deltas = optimizer.compute_delta_tokens(curr, prev)
    assert deltas["delta_input"] == 2000
    assert deltas["delta_output"] == 700
    assert deltas["delta_total"] == 2700

    # 4. Master Autonomous OS Integration
    system = Faz95MasterAutonomousAgentSystem(project_name="EntropyFleet")
    init_res = system.initialize_system()
    assert init_res["status"] == "INITIALIZED"
    assert "lead_planner" in init_res["registered_agents"]
    assert "code_developer" in init_res["registered_agents"]
    assert "qa_sentinel" in init_res["registered_agents"]
