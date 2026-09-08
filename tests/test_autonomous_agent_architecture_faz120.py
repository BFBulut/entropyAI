"""
Automated Test Suite for Faz 120 Master Autonomous Agent Architecture
====================================================================
Verifies all Faz 120 invariants:
1. Stateless FastMCP 5.1 Engine (SEP-3600 Dynamic Micro-Embedding Routing, Attenuated Signatures,
   SEP-3550 Reactive Context Push, Stateless ETag Caching, Adaptive Volatility TTL,
   SEP-3102 Batch Pipelines, SEP-3410 Binary Streaming, Background Tasks & Cancellation)
2. AAIF & Linux Foundation A2A v2.1 & AP2 2.6 (Signed Agent Cards, Latency-Aware Gossip Routing,
   Topological DAG Kahn, 2/3 Byzantine Quorum, Multi-Criteria SLA Clawbacks, Proof-of-Execution)
3. Self-Refining Harness 5.5 (Fit Ratio 4.0 Diagnostics, AST Preflight Guard 6.0,
   Merkle Checkpoint Stack, Micro-Harness Adapter Synthesis, Automated Circuit Breakers & Rollback)
4. Agent Desks 5.5 (Worktree SWB Lock Leases, Shared Desk Blackboard, 3-Way AST Semantic Conflict Resolution)
5. Tetradeca-Store 14-Layer Cognitive Memory & RRF-14 Fusion with Ebbinghaus Decay & Graphiti Invalidation
6. Ultra Token Physics 12.0 (Radix Cache Alignment, AST Skeletonization 6.0,
   CodeAct 5.5 Virtual REPL Sandbox & Security, Jina Late Chunking, MRL Truncation, Delta Token Accounting)
7. Erlang-OTP 5.5 Supervision Trees (One-for-One, One-for-All, Rest-for-One, Sliding-Window Budget Limits)
8. Faz 120 Master Autonomous Swarm Orchestrator Full Mission Lifecycle
"""

import math
import time
from pathlib import Path
import pytest

from src.entropy.tools.autonomous_agent_architecture_faz120 import (
    StatelessFastMCP51Engine,
    ElicitationMode120,
    A2APhase120ProtocolEngine,
    AgentCard120,
    SelfRefiningHarness55,
    HarnessFailureType120,
    AgentDeskWorktreeManager55,
    TetradecaStoreCognitiveRetriever,
    CodeActSandboxEngine120,
    CodeActSecurityException120,
    UltraTokenPhysicsOptimizer12,
    OTPSupervisorStrategy120,
    OTPSupervisorTree120,
    Faz120MasterAutonomousSwarmEngine,
)


# ==============================================================================
# 1. FASTMCP 5.1 ROUTING, ATTENUATION, REACTIVE PUSH & BATCH PIPELINE
# ==============================================================================

def test_fastmcp51_stateless_microrouting_attenuation_and_reactive_push():
    engine = StatelessFastMCP51Engine()
    call_count = 0

    def calc_multiplier(args: dict):
        nonlocal call_count
        call_count += 1
        return {"val": args["x"] * 10, "calls": call_count}

    def adder(args: dict):
        return {"val": args.get("val", 0) + 50}

    def config_tool(args: dict):
        return {"service": args["name"], "tier": args.get("tier", "enterprise")}

    engine.register_domain("math", "High performance mathematics and calculations")
    engine.register_domain("service", "Cloud services and configuration")

    engine.register_tool(
        name="multiplier",
        domain="math",
        description="Multiplies input by 10",
        parameters={"x": "int"},
        handler=calc_multiplier,
        cacheable=True,
        cache_ttl_seconds=50,
        volatility_score=0.1,
        supports_binary_streaming=True,
        keywords=["multiply", "math", "times", "product"],
    )

    engine.register_tool(
        name="adder",
        domain="math",
        description="Adds 50 to value",
        parameters={"val": "int"},
        handler=adder,
        cacheable=False,
        keywords=["add", "sum", "plus"],
    )

    engine.register_tool(
        name="config_service",
        domain="service",
        description="Configures service tier with elicitation",
        parameters={"name": "str"},
        handler=config_tool,
        requires_elicitation=True,
        elicitation_schema={"tier": "string"},
        keywords=["service", "config", "tier"],
    )

    # 1. SEP-3600 Dynamic Micro-Embedding Routing
    active_tools = engine.negotiate_active_tools("Perform mathematical multiplication on data", max_tools=2)
    assert len(active_tools) >= 1
    assert active_tools[0]["name"] == "multiplier"
    assert "def multiplier(x: int) -> Any:" in active_tools[0]["signature"]

    # 2. Dynamic Tool Capability Attenuation Check
    tool_def = engine.tools["multiplier"]
    att_sig = tool_def.get_attenuated_signature()
    assert "def multiplier(x: int) -> Any:" in att_sig
    assert '"""Multiplies input by 10"""' in att_sig

    # 3. SEP-3550 Reactive Context Push & Diff Sync
    engine.push_context_diff("agent_alpha", "file_updated", {"path": "src/core.py", "lines": 120})
    diffs = engine.consume_context_diffs("agent_alpha")
    assert len(diffs) == 1
    assert diffs[0]["type"] == "file_updated"
    assert diffs[0]["payload"]["path"] == "src/core.py"
    assert len(engine.consume_context_diffs("agent_alpha")) == 0

    # 4. Tool Execution & Adaptive ETag Caching
    res1 = engine.call_tool("multiplier", {"x": 7})
    assert res1["status"] == "SUCCESS"
    assert res1["result"]["val"] == 70
    assert not res1["cached"]
    etag1 = res1["etag"]

    # 304 Not Modified
    res2 = engine.call_tool("multiplier", {"x": 7}, client_if_none_match=etag1)
    assert res2["status"] == "NOT_MODIFIED"
    assert res2["code"] == 304

    # 5. Batch Pipeline Chaining (SEP-3102)
    steps = [
        {"tool": "multiplier", "arguments": {"x": 4}},
        {"tool": "adder", "pipe_from_previous": True},
    ]
    batch_res = engine.execute_batch_pipeline(steps)
    assert len(batch_res) == 2
    assert batch_res[0]["output"]["result"]["val"] == 40
    assert batch_res[1]["output"]["result"]["val"] == 90

    # 6. Elicitation Protocol
    el_res = engine.call_tool("config_service", {"name": "auth-gateway"})
    assert el_res["status"] == "ELICITATION_REQUIRED"
    assert "tier" in el_res["schema"]

    # 7. Background Tasks & Cancellation
    t_id = engine.submit_background_task("multiplier", {"x": 3})
    task_step1 = engine.execute_task_step(t_id)
    assert task_step1.status == "running"
    task_step2 = engine.execute_task_step(t_id)
    assert task_step2.status == "completed"
    assert task_step2.result["val"] == 30


# ==============================================================================
# 2. AAIF A2A v2.1 PROTOCOL & AP2 2.6 ESCROW
# ==============================================================================

def test_a2a_v21_protocol_agent_cards_gossip_routing_dag_and_ap2_escrow():
    a2a = A2APhase120ProtocolEngine(cluster_secret="master_secret_120")

    card_architect = AgentCard120(
        agent_id="agent_arch",
        name="ArchitectAgent",
        role="System Architect",
        capabilities=["spec_design", "ast_analysis", "memory_curation"],
        endpoint="https://cluster.entropy/arch",
        reputation_score=0.98,
        load_factor=0.1,
        latency_ms=10.0,
    )
    card_dev = AgentCard120(
        agent_id="agent_dev",
        name="DeveloperAgent",
        role="Backend Developer",
        capabilities=["code_synthesis", "refactor", "bugfix"],
        endpoint="https://cluster.entropy/dev",
        reputation_score=0.95,
        load_factor=0.2,
        latency_ms=15.0,
    )

    a2a.register_agent(card_architect)
    a2a.register_agent(card_dev)

    # 1. Cryptographic Signatures
    assert card_architect.verify_card("master_secret_120")
    assert not card_architect.verify_card("wrong_secret")

    # 2. Latency-Aware Gossip Mesh Routing
    best_agent = a2a.route_task_to_optimal_agent(["code_synthesis"])
    assert best_agent is not None
    assert best_agent.agent_id == "agent_dev"

    # 3. Kahn's Algorithm DAG Decomposition
    nodes = ["spec", "models", "api", "ui", "tests", "deploy"]
    edges = [
        ("spec", "models"),
        ("spec", "api"),
        ("models", "tests"),
        ("api", "tests"),
        ("api", "ui"),
        ("tests", "deploy"),
        ("ui", "deploy"),
    ]
    waves = a2a.decompose_dag_kahn(nodes, edges)
    assert waves[0] == ["spec"]
    assert "models" in waves[1] and "api" in waves[1]
    assert waves[-1] == ["deploy"]

    # 4. Byzantine Quorum (2/3 PBFT)
    votes = {"node1": True, "node2": True, "node3": False, "node4": True}
    is_consensus, ratio = a2a.execute_byzantine_quorum(votes, threshold_ratio=0.667)
    assert is_consensus
    assert ratio == 0.75

    # 5. AP2 2.6 Multi-Criteria SLA Escrow with 4-Tier Clawbacks
    escrow_id = a2a.lock_ap2_escrow(
        initiator="agent_arch", worker="agent_dev", tokens=1000, sla_seconds=5.0
    )

    # Scenario A: Perfect completion
    net_paid, refunded = a2a.settle_ap2_escrow(
        escrow_id=escrow_id,
        actual_duration=3.2,
        quality_score=0.92,
        safety_breach=False,
        token_usage=1200,
        poe_content="def hello(): return 'world'",
    )
    assert net_paid == 1000
    assert refunded == 0

    # Scenario B: Latency breach + low quality + token budget overrun
    escrow_id2 = a2a.lock_ap2_escrow(
        initiator="agent_arch", worker="agent_dev", tokens=1000, sla_seconds=4.0
    )
    net_paid2, refunded2 = a2a.settle_ap2_escrow(
        escrow_id=escrow_id2,
        actual_duration=6.5,    # Latency penalty: 20%
        quality_score=0.65,      # Quality penalty: 30%
        safety_breach=False,
        token_usage=3500,        # Token overrun: 25% (total clawback = 75%)
        poe_content="sloppy code output",
    )
    assert refunded2 == 750
    assert net_paid2 == 250


# ==============================================================================
# 3. SELF-REFINING HARNESS 5.5 & AST GUARD 6.0
# ==============================================================================

def test_self_refining_harness55_fit_ratio_ast_guard_adapter_and_circuit_breaker():
    harness = SelfRefiningHarness55(failure_threshold=3)

    # 1. Fit Ratio 4.0 Calculation
    harness.record_failure(HarnessFailureType120.SCAFFOLDING_FAULT)
    harness.record_failure(HarnessFailureType120.AST_SECURITY_FAULT)
    harness.record_failure(HarnessFailureType120.MODEL_REASONING_FAULT)
    harness.record_failure(HarnessFailureType120.MODEL_REASONING_FAULT)

    # 2 harness faults out of 4 total failures = Fit Ratio 0.50
    assert harness.calculate_fit_ratio() == 0.50
    assert harness.circuit_open

    # 2. Reset circuit on success & Merkle Checkpoint
    harness.record_success("state_v1_commit_green")
    assert not harness.circuit_open
    assert len(harness.merkle_checkpoints) == 1
    assert harness.rollback_to_last_checkpoint() is not None

    # 3. AST Preflight Guard 6.0 Zero-Trust Checks
    bad_code_1 = "import os\nos.system('rm -rf /')"
    is_safe1, violations1 = harness.validate_code_ast(bad_code_1)
    assert not is_safe1
    assert any("Forbidden subsystem execution" in v for v in violations1)

    bad_code_2 = "result = eval('2 + 2')"
    is_safe2, violations2 = harness.validate_code_ast(bad_code_2)
    assert not is_safe2
    assert any("Forbidden dynamic execution call" in v for v in violations2)

    good_code = "def calculate_vat(price: float, rate: float = 0.20) -> float:\n    return price * (1.0 + rate)"
    is_safe3, violations3 = harness.validate_code_ast(good_code)
    assert is_safe3
    assert len(violations3) == 0

    # 4. Dynamic Micro-Adapter Synthesis
    def strict_add(args: dict) -> int:
        return args["a"] + args["b"]

    adapter = harness.synthesize_adapter(strict_add, expected_keys=["a", "b"])
    # Tool received case-mismatched or slightly drifted arguments
    adapted_res = adapter({"A": 15, "B": 25})
    assert adapted_res == 40


# ==============================================================================
# 4. AGENT DESKS 5.5, SWB LOCKS & 3-WAY AST SEMANTIC MERGE
# ==============================================================================

def test_agent_desks55_swb_locks_blackboard_and_3way_ast_semantic_merge():
    desks = AgentDeskWorktreeManager55()

    # 1. Single-Writer Boundary (SWB) Leases
    acquired1 = desks.acquire_swb_lease("desk_dev", "src/math.py", lease_seconds=10.0)
    assert acquired1

    # Desk QA cannot acquire same file before expiration
    acquired2 = desks.acquire_swb_lease("desk_qa", "src/math.py", lease_seconds=10.0)
    assert not acquired2

    # Release and reacquire
    desks.release_swb_lease("desk_dev", "src/math.py")
    acquired3 = desks.acquire_swb_lease("desk_qa", "src/math.py", lease_seconds=10.0)
    assert acquired3

    # 2. Shared In-Memory Blackboard
    desks.post_to_blackboard("build_status", {"status": "SUCCESS", "exit_code": 0, "duration": 1.4})
    bb_val = desks.read_from_blackboard("build_status")
    assert bb_val["status"] == "SUCCESS"
    assert bb_val["exit_code"] == 0

    # 3. 3-Way AST Semantic Conflict Resolution
    base_code = """
def calc_tax(income):
    return income * 0.15

def calc_discount(total):
    return total * 0.05
"""

    desk_a_code = """
def calc_tax(income):
    return income * 0.20

def calc_discount(total):
    return total * 0.05
"""

    desk_b_code = """
def calc_tax(income):
    return income * 0.15

def calc_discount(total):
    return total * 0.10
"""

    success, merged_code = desks.merge_3way_ast(base_code, desk_a_code, desk_b_code)
    assert success
    assert "income * 0.2" in merged_code or "income * 0.20" in merged_code
    assert "total * 0.1" in merged_code or "total * 0.10" in merged_code

    # Conflicting edits in same function
    desk_b_conflict = """
def calc_tax(income):
    return income * 0.30

def calc_discount(total):
    return total * 0.10
"""
    success_conflict, msg = desks.merge_3way_ast(base_code, desk_a_code, desk_b_conflict)
    assert not success_conflict
    assert "Semantic conflict on function 'calc_tax'" in msg


# ==============================================================================
# 5. TETRADECA-STORE 14-LAYER COGNITIVE MEMORY & RRF-14
# ==============================================================================

def test_tetradeca_store_memory_ebbinghaus_graphiti_and_rrf14():
    memory = TetradecaStoreCognitiveRetriever()

    # Store memory across different layers
    id1 = memory.store_memory("obsidian_exocortex", "Architecture decision: use FastMCP 5.1 with SEP-3600", tags=["arch", "mcp"])
    id2 = memory.store_memory("pgvector_streaming_diskann", "pgvectorscale SSD index enables 10M vector scale", tags=["pgvector", "database"])
    id3 = memory.store_memory("hipporag2_ppr", "Personalized PageRank PPR enables multi-hop reasoning", tags=["graph", "retrieval"])
    id4 = memory.store_memory("graphiti_bi_temporal", "Active auth endpoint is /v1/auth", tags=["auth", "endpoint"])
    id5 = memory.store_memory("procedural_execution_skills", "Script to deploy container with docker compose", tags=["deploy", "docker"])

    # 1. Graphiti Bi-temporal edge invalidation
    memory.invalidate_graphiti_edge(id4)
    item_auth = next(itm for itm in memory.stores["graphiti_bi_temporal"] if itm.item_id == id4)
    assert item_auth.is_invalidated
    assert item_auth.valid_to is not None

    # 2. Ebbinghaus Forgetting Curve Retention Check
    test_item = memory.stores["obsidian_exocortex"][0]
    retention_now = test_item.calculate_ebbinghaus_retention(time.time())
    assert 0.99 <= retention_now <= 1.0

    retention_future = test_item.calculate_ebbinghaus_retention(time.time() + 3600 * 24 * 7) # 1 week later
    assert retention_future < retention_now

    # 3. 14-Way Reciprocal Rank Fusion (RRF-14)
    results = memory.retrieve_rrf14("FastMCP SEP-3600 architecture", top_k=3)
    assert len(results) >= 1
    top_score, top_item = results[0]
    assert top_score > 0.0
    assert "FastMCP 5.1" in top_item.content


# ==============================================================================
# 6. ULTRA TOKEN PHYSICS 12.0 & CODEACT 5.5
# ==============================================================================

def test_token_physics12_radix_alignment_skeletonization_codeact_and_delta_tokens():
    # 1. RadixAttention Cache Alignment
    prefix = "System Directive: You are Entropy AI pair programmer assistant."
    aligned_128 = UltraTokenPhysicsOptimizer12.align_radix_cache(prefix, boundary=64)
    tokens_count = len(aligned_128.split())
    assert tokens_count % 64 == 0

    # 2. AST Skeletonization 6.0
    full_module = """
def heavy_processing(data: list) -> dict:
    '''Performs complex array transformations and heavy arithmetic.'''
    res = {}
    for idx, item in enumerate(data):
        res[idx] = item ** 2 + 15 * item
    return res

def another_tool(x: int):
    val = x * 2
    return val
"""
    skeleton = UltraTokenPhysicsOptimizer12.skeletonize_python_code(full_module)
    assert "Performs complex array transformations" in skeleton
    assert "item ** 2" not in skeleton
    assert "pass" in skeleton.lower()

    # 3. CodeAct 5.5 Virtual REPL Sandbox
    sandbox = CodeActSandboxEngine120()
    safe_script = """
items = [1, 2, 3, 4, 5]
squared = [x * x for x in items]
total_sum = sum(squared)
"""
    env_out = sandbox.execute_script(safe_script)
    assert env_out["total_sum"] == 55

    # CodeAct Security Breach
    with pytest.raises(CodeActSecurityException120):
        sandbox.execute_script("import os\nos.system('dir')")

    with pytest.raises(CodeActSecurityException120):
        sandbox.execute_script("eval('10 + 20')")

    # 4. Jina Late Chunking Mean Pooling
    token_embs = [
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
        [7.0, 8.0],
    ]
    spans = [(0, 2), (2, 4)]
    pooled = UltraTokenPhysicsOptimizer12.late_chunking_mean_pooling(token_embs, spans)
    assert len(pooled) == 2
    assert pooled[0] == [2.0, 3.0]
    assert pooled[1] == [6.0, 7.0]

    # 5. MRL Truncation & Normalization
    raw_vec = [1.0, 2.0, 3.0, 4.0, 5.0]
    mrl_vec = UltraTokenPhysicsOptimizer12.truncate_mrl(raw_vec, target_dim=3)
    assert len(mrl_vec) == 3
    l2_norm = math.sqrt(sum(x * x for x in mrl_vec))
    assert math.isclose(l2_norm, 1.0, rel_tol=1e-5)

    # 6. Delta Token Accounting Formula
    d_in, d_out = UltraTokenPhysicsOptimizer12.calculate_delta_tokens(
        cum_input_now=15000, cum_output_now=8000, prev_input=12000, prev_output=6500
    )
    assert d_in == 3000
    assert d_out == 1500


# ==============================================================================
# 7. ERLANG-OTP 5.5 SUPERVISION TREES
# ==============================================================================

def test_erlang_otp55_supervision_strategies_and_circuit_collapse():
    restarts_a = 0
    restarts_b = 0
    restarts_c = 0

    def restart_a():
        nonlocal restarts_a
        restarts_a += 1

    def restart_b():
        nonlocal restarts_b
        restarts_b += 1

    def restart_c():
        nonlocal restarts_c
        restarts_c += 1

    # 1. One-for-One Strategy
    sup_one = OTPSupervisorTree120(strategy=OTPSupervisorStrategy120.ONE_FOR_ONE, max_restarts=5)
    sup_one.add_worker("worker_a", restart_a)
    sup_one.add_worker("worker_b", restart_b)

    restarted = sup_one.handle_worker_failure("worker_a")
    assert restarted == ["worker_a"]
    assert restarts_a == 1
    assert restarts_b == 0

    # 2. One-for-All Strategy
    sup_all = OTPSupervisorTree120(strategy=OTPSupervisorStrategy120.ONE_FOR_ALL, max_restarts=5)
    sup_all.add_worker("worker_a", restart_a)
    sup_all.add_worker("worker_b", restart_b)

    restarted_all = sup_all.handle_worker_failure("worker_a")
    assert set(restarted_all) == {"worker_a", "worker_b"}

    # 3. Rest-for-One Strategy
    sup_rest = OTPSupervisorTree120(strategy=OTPSupervisorStrategy120.REST_FOR_ONE, max_restarts=5)
    sup_rest.add_worker("worker_a", restart_a)
    sup_rest.add_worker("worker_b", restart_b)
    sup_rest.add_worker("worker_c", restart_c)

    restarted_rest = sup_rest.handle_worker_failure("worker_b")
    assert restarted_rest == ["worker_b", "worker_c"]

    # 4. Circuit Collapse on Exceeded Sliding Budget
    sup_fragile = OTPSupervisorTree120(max_restarts=2, window_seconds=60.0)
    sup_fragile.add_worker("w1", lambda: None)
    sup_fragile.handle_worker_failure("w1")
    sup_fragile.handle_worker_failure("w1")
    collapsed_list = sup_fragile.handle_worker_failure("w1")
    assert sup_fragile.circuit_collapsed
    assert collapsed_list == []
    assert sup_fragile.workers["w1"]["status"] == "COLLAPSED"


# ==============================================================================
# 8. MASTER AUTONOMOUS SWARM ORCHESTRATOR MISSION LIFECYCLE
# ==============================================================================

def test_faz120_master_autonomous_swarm_engine_mission_lifecycle():
    engine = Faz120MasterAutonomousSwarmEngine()

    safe_code = """
def autonomous_calc_service(metric: float) -> float:
    '''Production hardened metric calculator.'''
    return metric * 1.618033
"""
    result = engine.run_master_mission(
        mission_name="EntropyAutonomousCoreUpgrade", code_snippet=safe_code
    )

    assert result["status"] == "COMPLETED"
    assert result["fit_ratio"] == 1.0
    assert result["checkpoint"] is not None
    assert "EntropyAutonomousCoreUpgrade" in result["mission"]
    assert result["memory_id"] is not None

    # Test blocked unsafe mission
    unsafe_code = "exec('print(123)')"
    unsafe_result = engine.run_master_mission(
        mission_name="MaliciousPayloadAttempt", code_snippet=unsafe_code
    )
    assert unsafe_result["status"] == "BLOCKED"
    assert any("Forbidden dynamic execution call" in r for r in unsafe_result["reason"])
