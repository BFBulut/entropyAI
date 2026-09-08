"""
Automated Test Suite for Faz 113 Master Autonomous Agent Architecture
====================================================================
Verifies all Faz 113 invariants:
- Stateless FastMCP 4.0 Engine (Sessionless Core, Background Tasks, Cache Hints)
- A2A Protocol v1.0.0 & AP2 (Agent Payments Protocol) Handshake, Agent Cards & SLA Penalties
- Erlang-OTP Supervision Trees 2.5 (One-for-One, One-for-All, Rest-for-One, Rollback Sentinel)
- Code-as-Action (CodeAct) Virtual Sandbox 3.0 & AST Pre-Flight Security
- Septa-Store Multi-Tier Hybrid Retrieval (7 Layers) & RRF-7 Fusion
- Agent Desks Single-Writer Boundary (SWB) & AST Semantic Collision Detection
- Radix-Cache 64/128-Token Alignment, AST Skeletonizer 3.0, Matryoshka MRL & Delta Token Accounting
- Faz 113 Master Autonomous Swarm Orchestrator End-to-End Mission Execution
"""

import math
import time
import pytest
from src.entropy.tools.autonomous_agent_architecture_faz113 import (
    StatelessFastMCP4Engine,
    A2APhase113ProtocolEngine,
    A2ATaskDelegationRequest113,
    A2ATaskStatus,
    AgentCard113,
    OTPSupervisorStrategy,
    OTPSupervisorTree113,
    CodeActSandboxEngine113,
    CodeActSecurityException,
    SeptaStoreCognitiveRetriever113,
    SeptaMemoryNode,
    AgentDeskWorktreeManager113,
    ExtremeTokenPhysicsOptimizer5,
    Faz113MasterAutonomousSwarmEngine,
)


# ==============================================================================
# 1. STATELESS FASTMCP 4.0 TESTS
# ==============================================================================

def test_fastmcp4_stateless_execution_and_cache_hints():
    engine = StatelessFastMCP4Engine()
    call_counter = 0

    def sample_tool(args: dict):
        nonlocal call_counter
        call_counter += 1
        return {"multiplied": args["val"] * 2, "calls": call_counter}

    engine.register_tool(
        name="multiplier",
        description="Multiplies input value by 2",
        parameters={"val": "int"},
        handler=sample_tool,
        cacheable=True,
        cache_ttl_seconds=10,
    )

    # 1. First execution -> Cache miss
    res1 = engine.execute_tool("multiplier", {"val": 21}, user_session_id="user_123")
    assert res1["success"] is True
    assert res1["cached"] is False
    assert res1["result"]["multiplied"] == 42
    assert call_counter == 1
    assert engine.cache_misses == 1

    # 2. Second execution with identical args -> Cache hit
    res2 = engine.execute_tool("multiplier", {"val": 21}, user_session_id="user_123")
    assert res2["success"] is True
    assert res2["cached"] is True
    assert res2["result"]["multiplied"] == 42
    assert call_counter == 1  # Handler was not executed again
    assert engine.cache_hits == 1

    # 3. Background task dispatch (io.modelcontextprotocol/tasks)
    task_id = engine.dispatch_background_task("multiplier", {"val": 50})
    status = engine.get_task_status(task_id)
    assert status is not None
    assert status["status"] == "completed"
    assert status["result"]["multiplied"] == 100


# ==============================================================================
# 2. A2A v1.0.0 & AP2 SLA CONTRACT TESTS
# ==============================================================================

def test_a2a_agent_card_and_ap2_sla_contract():
    engine = A2APhase113ProtocolEngine()
    card = AgentCard113(
        agent_id="agent_fast_dev",
        name="Fast Developer Desk",
        version="2026.113.0",
        description="High speed developer",
        capabilities=["python", "fastmcp_4"],
        endpoints={"tasks": "/tasks"},
        token_rate_per_k=0.03,
        max_concurrency=4,
        sla_max_latency_ms=100.0,
    )
    engine.register_agent(card)

    # Agent Card Schema
    card_json = engine.generate_well_known_agent_card_json("agent_fast_dev")
    assert "https://a2a-protocol.org/schemas/v1.0.0/agent-card.json" in card_json
    assert "agent_fast_dev" in card_json

    # AP2 contract creation
    contract = engine.create_ap2_contract("orch", "agent_fast_dev", token_budget=10000)
    assert contract.escrow_amount == pytest.approx(0.30)  # 10 * 0.03

    # Settlement within SLA
    settled_normal = engine.settle_ap2_contract(contract.contract_id, tokens_used=5000, actual_latency_ms=50.0)
    assert settled_normal == pytest.approx(0.15)
    assert contract.penalty_applied is False

    # Settlement breaching SLA (20% penalty clawback)
    contract_breach = engine.create_ap2_contract("orch", "agent_fast_dev", token_budget=10000)
    settled_penalized = engine.settle_ap2_contract(contract_breach.contract_id, tokens_used=5000, actual_latency_ms=500.0)
    assert settled_penalized == pytest.approx(0.12)  # 0.15 - (0.15 * 0.20)
    assert contract_breach.penalty_applied is True


def test_a2a_delegation_lifecycle_and_dlq():
    engine = A2APhase113ProtocolEngine()
    card = AgentCard113(
        agent_id="active_qa",
        name="Active QA",
        version="2026.113.0",
        description="Active QA",
        capabilities=["testing"],
        endpoints={"tasks": "/tasks"},
        token_rate_per_k=0.01,
        max_concurrency=2,
    )
    engine.register_agent(card)

    # Offline target -> DLQ
    req_offline = A2ATaskDelegationRequest113(
        task_id="t_offline",
        sender_id="orch",
        target_id="missing_agent",
        payload={"task": "test"},
        token_budget=1000,
        deadline_epoch_s=time.time() + 100,
    )
    resp_offline = engine.delegate_task(req_offline)
    assert resp_offline.status == A2ATaskStatus.REJECTED
    assert len(engine.dead_letter_queue) == 1

    # Expired deadline -> DLQ
    req_expired = A2ATaskDelegationRequest113(
        task_id="t_expired",
        sender_id="orch",
        target_id="active_qa",
        payload={"task": "test"},
        token_budget=1000,
        deadline_epoch_s=time.time() - 10,
    )
    resp_expired = engine.delegate_task(req_expired)
    assert resp_expired.status == A2ATaskStatus.REJECTED
    assert len(engine.dead_letter_queue) == 2

    # Valid task -> Verified
    contract = engine.create_ap2_contract("orch", "active_qa", 2000)
    req_valid = A2ATaskDelegationRequest113(
        task_id="t_valid",
        sender_id="orch",
        target_id="active_qa",
        payload={"task": "run_tests"},
        token_budget=2000,
        deadline_epoch_s=time.time() + 100,
        payment_contract=contract,
    )
    resp_valid = engine.delegate_task(req_valid)
    assert resp_valid.status == A2ATaskStatus.VERIFIED
    assert resp_valid.tokens_consumed > 0
    assert engine.verify_signature(
        f"t_valid:active_qa:{A2ATaskStatus.VERIFIED.value}:{resp_valid.tokens_consumed}",
        resp_valid.signature,
    ) is True


# ==============================================================================
# 3. ERLANG-OTP SUPERVISION TREE 2.5 TESTS
# ==============================================================================

def test_otp_supervisor_strategies_and_rollback():
    # 1. ONE_FOR_ONE
    tree_one = OTPSupervisorTree113(strategy=OTPSupervisorStrategy.ONE_FOR_ONE)
    tree_one.register_worker("w1", "Worker 1")
    tree_one.register_worker("w2", "Worker 2")
    tree_one.record_checkpoint("w1", "commit_sha_abc123")

    res = tree_one.handle_worker_crash("w1", "Division by zero")
    assert res["tree_action"] == "RESTARTED"
    assert res["restarted_workers"] == ["w1"]
    assert res["rolled_back_commits"]["w1"] == "commit_sha_abc123"
    assert tree_one.workers["w2"].restart_count == 0

    # 2. REST_FOR_ONE (Cascades to subsequent workers)
    tree_rest = OTPSupervisorTree113(strategy=OTPSupervisorStrategy.REST_FOR_ONE)
    tree_rest.register_worker("stage1", "Parser")
    tree_rest.register_worker("stage2", "Compiler")
    tree_rest.register_worker("stage3", "Deployer")

    res_rest = tree_rest.handle_worker_crash("stage2", "Compiler failed")
    assert res_rest["restarted_workers"] == ["stage2", "stage3"]
    assert tree_rest.workers["stage1"].restart_count == 0

    # 3. Crash intensity tripwire (Tree collapse)
    tree_collapse = OTPSupervisorTree113(max_restarts=2, max_seconds=10.0)
    tree_collapse.register_worker("flaky", "Flaky")
    tree_collapse.handle_worker_crash("flaky", "err1")
    tree_collapse.handle_worker_crash("flaky", "err2")
    res_trip = tree_collapse.handle_worker_crash("flaky", "err3")
    assert res_trip["tree_action"] == "TREE_COLLAPSED"
    assert tree_collapse.is_tree_alive is False


# ==============================================================================
# 4. CODEACT SANDBOX 3.0 SECURITY & EXECUTION TESTS
# ==============================================================================

def test_codeact_security_inspection_and_execution():
    sandbox = CodeActSandboxEngine113()

    # Blocked dangerous imports
    with pytest.raises(CodeActSecurityException, match="Prohibited module import"):
        sandbox.execute_codeact("import urllib.request\nurllib.request.urlopen('http://evil.com')")

    # Blocked dangerous call
    with pytest.raises(CodeActSecurityException, match="Prohibited callable execution"):
        sandbox.execute_codeact("eval('2 + 2')")

    # Safe multi-step execution
    safe_code = (
        "data = [10, 20, 30, 40]\n"
        "squared = [x**2 for x in data]\n"
        "result = sum(squared)\n"
    )
    res = sandbox.execute_codeact(safe_code)
    assert res["success"] is True
    assert res["result"] == 3000
    assert res["tokens_saved_estimate"] > 0


# ==============================================================================
# 5. SEPTA-STORE COGNITIVE RETRIEVER & RRF-7 TESTS
# ==============================================================================

def test_septa_store_rrf_7_fusion():
    retriever = SeptaStoreCognitiveRetriever113()

    node1 = SeptaMemoryNode(
        id="mem_01",
        layer="obsidian",
        title="Architecture Decision Record",
        content="We implement [[FastMCP]] and [[A2A Protocol]] for autonomous agents.",
        entities=["FastMCP", "A2A Protocol"],
        importance=0.9,
    )
    node2 = SeptaMemoryNode(
        id="mem_02",
        layer="pgvector",
        title="Database Schema Vector",
        content="Supabase pgvector 0.8 halfvec enables 4000d embeddings and saves 50 percent RAM.",
        entities=["pgvector", "halfvec"],
        importance=0.8,
    )
    node3 = SeptaMemoryNode(
        id="mem_03",
        layer="graphiti",
        title="Bi-Temporal Invalidation",
        content="Legacy sticky sessions were deprecated in July 2026.",
        valid_until=time.time() - 3600,  # Expired / Invalidated
        entities=["sticky sessions"],
        importance=0.5,
    )
    retriever.add_node(node1)
    retriever.add_node(node2)
    retriever.add_node(node3)

    results = retriever.rrf_7_fusion("FastMCP pgvector halfvec", top_k=2)
    assert len(results) == 2
    top_ids = [n.id for n, _ in results]
    assert "mem_01" in top_ids or "mem_02" in top_ids
    # Expired node3 should be lower rank or suppressed
    assert node3.id not in top_ids


# ==============================================================================
# 6. AGENT DESK WORKTREE & AST SEMANTIC COLLISION TESTS
# ==============================================================================

def test_agent_desk_concurrency_and_ast_collision():
    manager = AgentDeskWorktreeManager113()
    manager.provision_desk("desk_backend", "Backend")
    manager.provision_desk("desk_frontend", "Frontend")

    # Mutex file lock
    locked_backend = manager.acquire_file_lock("desk_backend", "api/routes.py", "agent_1")
    assert locked_backend is True

    locked_frontend = manager.acquire_file_lock("desk_frontend", "api/routes.py", "agent_2")
    assert locked_frontend is False  # Conflicting file lock rejected

    manager.release_file_lock("desk_backend", "api/routes.py")
    locked_now = manager.acquire_file_lock("desk_frontend", "api/routes.py", "agent_2")
    assert locked_now is True

    # AST Semantic Collision: Distinct functions -> Safe (No Collision)
    code_mod_a = "def get_users(): pass\n"
    code_mod_b = "def create_order(): pass\n"
    has_collision, conflicts = manager.check_ast_semantic_collision(code_mod_a, code_mod_b)
    assert has_collision is False
    assert len(conflicts) == 0

    # AST Semantic Collision: Same function modified -> Collision Detected
    code_clash_a = "def process_payment(amount): return amount * 1.1\n"
    code_clash_b = "def process_payment(amount): return amount * 0.9\n"
    has_clash, clash_symbols = manager.check_ast_semantic_collision(code_clash_a, code_clash_b)
    assert has_clash is True
    assert "process_payment" in clash_symbols


# ==============================================================================
# 7. EXTREME TOKEN PHYSICS 5.0 TESTS
# ==============================================================================

def test_extreme_token_physics_5():
    optimizer = ExtremeTokenPhysicsOptimizer5()

    # 1. Radix Attention 64-token Boundary Alignment
    static_instruction = "You are Entropy AI, an autonomous system."
    dynamic_suffix = "Task: Process batch 42."
    aligned_prompt = optimizer.align_radix_prompt(static_instruction, dynamic_suffix, boundary_tokens=64)
    assert "[DYNAMIC_CONTEXT]" in aligned_prompt
    assert static_instruction in aligned_prompt

    # 2. AST Skeletonization 3.0
    source = (
        "def compute_heavy(x: int, y: int) -> int:\n"
        "    '''Computes complex tensor calculation.'''\n"
        "    temp = x * y\n"
        "    for _ in range(100):\n"
        "        temp += 1\n"
        "    return temp\n"
    )
    skeleton = optimizer.skeletonize_python_ast(source)
    assert "Computes complex tensor calculation" in skeleton
    assert "temp = x * y" not in skeleton  # Body replaced
    assert "..." in skeleton

    # 3. Matryoshka Representation Learning (MRL) Truncation
    high_dim_vec = [1.0] * 384
    truncated_vec = optimizer.matryoshka_truncate_embedding(high_dim_vec, target_dim=128)
    assert len(truncated_vec) == 128
    norm = math.sqrt(sum(x * x for x in truncated_vec))
    assert norm == pytest.approx(1.0)

    # 4. Delta Token Accounting
    assert optimizer.compute_delta_tokens(current_usage=1500, previous_usage=1200) == 300
    assert optimizer.compute_delta_tokens(current_usage=500, previous_usage=600) == 0


# ==============================================================================
# 8. FAZ 113 MASTER ORCHESTRATOR MISSION TEST
# ==============================================================================

def test_faz113_master_swarm_mission():
    swarm = Faz113MasterAutonomousSwarmEngine()
    mission_spec = {
        "directive": "Autonomous SOTA Architecture Upgrade",
        "scope": ["FastMCP 4.0", "A2A v1.0", "Septa-Store", "Token Physics 5.0"],
    }
    result = swarm.run_autonomous_mission(
        mission_title="2026 Autonomous Agent Architecture Upgrade",
        mission_spec=mission_spec,
    )
    assert result["status"] == "SUCCESS"
    assert result["a2a_status"] == "verified"
    assert result["ap2_settled_amount"] > 0.0
    assert result["codeact_result"] == 285  # sum of 0^2..9^2 = 285
    assert result["delta_tokens"] > 0
    assert result["duration_ms"] > 0
