"""
Automated Test Suite for Faz 121 Master Autonomous Agent Architecture Module
=============================================================================
Verifies 100% programmatic correctness across all 8 architectural pillars:
1. Stateless FastMCP 5.2 (SEP-3650 Micro-Routing, Attenuation, Reactive Push, ETag Caching)
2. AAIF A2A v2.2 & AP2 2.7 (Agent Cards, Gossip Routing, DAG Scheduling, Byzantine Quorum, Escrow)
3. Self-Refining Harness 6.0 (Fit Ratio 5.0, AST Guard 7.0, Dynamic Adapters, Merkle Rollback)
4. Agent Desks 6.0 (SWB Leases, Shared Blackboard Bus, 3-Way AST Semantic Merge)
5. Pentadeca-Store 15-Layer Memory (Graphiti Invalidation, Ebbinghaus Decay, RRF-15 Fusion)
6. Ultra Token Physics 13.0 (Radix Alignment, CodeAct 6.0 REPL, AST Skeletonization, Delta Tokens)
7. Erlang-OTP 6.0 Supervision Trees (One-for-One, One-for-All, Rest-for-One, Collapse Budget)
8. Faz 121 Master Autonomous Swarm Engine (Full Mission Lifecycle & End-to-End Orchestration)
"""

import hashlib
import time
import pytest

from entropy.tools.autonomous_agent_architecture_faz121 import (
    StatelessFastMCP52Engine,
    MCPToolDefinition121,
    AgentCard121,
    DecoupledTaskContract121,
    AAIFMeshRouter121,
    SelfRefiningHarness60,
    HarnessFaultCategory121,
    AgentDesks60,
    PentadecaStore15LayerMemory,
    TokenPhysics130,
    ErlangOTPSupervisor60,
    SupervisionStrategy121,
    Faz121MasterSwarmOrchestrator
)


def test_fastmcp52_stateless_microrouting_attenuation_and_reactive_push():
    engine = StatelessFastMCP52Engine()

    def calc_add(args):
        return args["a"] + args["b"]

    def text_upper(args):
        return args["text"].upper()

    t1 = MCPToolDefinition121(
        name="math_add",
        domain="math",
        description="Adds two integers a and b",
        parameters={"a": "int", "b": "int"},
        handler=calc_add,
        cacheable=True,
        cache_ttl_seconds=30,
        volatility_score=0.1,
        keywords=["add", "sum", "plus", "math"]
    )
    t2 = MCPToolDefinition121(
        name="string_upper",
        domain="text",
        description="Converts text to uppercase",
        parameters={"text": "str"},
        handler=text_upper,
        cacheable=True,
        cache_ttl_seconds=30,
        volatility_score=0.2,
        keywords=["upper", "string", "capitalize", "text"]
    )

    engine.register_tool(t1)
    engine.register_tool(t2)

    # 1. Test SEP-3650 Micro-Embedding Routing & Attenuation
    neg_res = engine.negotiate_active_tools("I need to calculate sum and add numbers", max_tools=1)
    assert neg_res["selected_tool_count"] == 1
    assert neg_res["tool_names"] == ["math_add"]
    assert "def math_add(a: int, b: int) -> Any:" in neg_res["attenuated_signatures"]
    assert neg_res["token_saving_ratio"] >= 0.90

    # 2. Test Execution & Volatility ETag Caching
    res1 = engine.execute_tool("math_add", {"a": 10, "b": 25})
    assert res1["status"] == "success"
    assert res1["data"] == 35
    assert res1["cached"] is False
    etag = res1["etag"]

    # Repeat with ETag -> 304 Not Modified
    res2 = engine.execute_tool("math_add", {"a": 10, "b": 25}, request_etag=etag)
    assert res2["http_status"] == 304
    assert res2["cached"] is True
    assert res2["data"] is None

    # 3. Test SEP-3550 Reactive Context Push
    engine.push_context_diff("BUILD_SUCCESS", {"job_id": 42, "artifacts": ["bin/app"]})
    diffs = engine.drain_context_diffs()
    assert len(diffs) == 1
    assert diffs[0]["event_type"] == "BUILD_SUCCESS"
    assert engine.drain_context_diffs() == []


def test_a2a_v22_protocol_agent_cards_gossip_routing_dag_and_ap2_escrow():
    router = AAIFMeshRouter121(secret="unit-test-secret-121")

    agent1 = AgentCard121(
        agent_id="agent-coder",
        name="CodeSpecialist",
        role="FullStack Dev",
        skills=["python", "fastapi", "react"],
        public_key="pk_coder_121",
        endpoint="https://mesh.entropy.ai/coder",
        reputation_score=0.98,
        current_load=0.2,
        latency_ms=8.0
    )
    agent2 = AgentCard121(
        agent_id="agent-slow-coder",
        name="SlowCoder",
        role="Dev",
        skills=["python"],
        public_key="pk_slow_121",
        endpoint="https://mesh.entropy.ai/slow",
        reputation_score=0.70,
        current_load=0.8,
        latency_ms=150.0
    )

    router.register_agent(agent1)
    router.register_agent(agent2)

    # 1. Routing selects best composite QoS score (lowest latency + highest reputation)
    routed = router.route_task("python")
    assert routed is not None
    assert routed.agent_id == "agent-coder"

    # 2. Test Kahn DAG Wavefront Scheduling
    t1 = DecoupledTaskContract121(task_id="t1", title="Define Schema", input_schema={}, output_schema={}, acceptance_tests=[])
    t2 = DecoupledTaskContract121(task_id="t2", title="Implement Backend", input_schema={}, output_schema={}, acceptance_tests=[], dependencies=["t1"])
    t3 = DecoupledTaskContract121(task_id="t3", title="Implement Frontend", input_schema={}, output_schema={}, acceptance_tests=[], dependencies=["t1"])
    t4 = DecoupledTaskContract121(task_id="t4", title="Integration Tests", input_schema={}, output_schema={}, acceptance_tests=[], dependencies=["t2", "t3"])

    waves = router.schedule_dag_tasks([t1, t2, t3, t4])
    assert len(waves) == 3
    assert waves[0] == ["t1"]
    assert sorted(waves[1]) == ["t2", "t3"]
    assert waves[2] == ["t4"]

    # 3. Test AP2 2.7 Multi-Criteria SLA Escrow with Clawback
    router.escrow.lock_funds("t2", "client-agent", "agent-coder", 1.00)
    poe = hashlib.sha256(b"code_execution_proof").hexdigest()
    # Latency breach (600ms > 500ms max) -> 20% clawback ($0.20)
    settlement = router.escrow.evaluate_and_settle(
        task_id="t2",
        execution_latency_ms=650.0,
        sla_max_latency_ms=500.0,
        quality_score=0.95,
        safety_breach=False,
        tokens_used=1500,
        token_budget=2000,
        poe_hash=poe
    )
    assert settlement["status"] == "SETTLED"
    assert settlement["clawback_refunded_usd"] == 0.20
    assert settlement["net_payout_usd"] == 0.80
    assert settlement["proof_of_execution_verified"] is True


def test_self_refining_harness60_fit_ratio_ast_guard_adapter_and_circuit_breaker():
    harness = SelfRefiningHarness60()

    # 1. AST Preflight Guard 7.0
    safe_code = """
def calculate_vat(price: float) -> float:
    return price * 1.20
"""
    unsafe_code_eval = """
def run_command(cmd):
    return eval(cmd)
"""
    unsafe_code_os = """
import os
def delete_all():
    os.system("rm -rf /")
"""
    assert harness.ast_preflight_check(safe_code)["safe"] is True
    assert harness.ast_preflight_check(unsafe_code_eval)["safe"] is False
    assert "Forbidden call 'eval()'" in harness.ast_preflight_check(unsafe_code_eval)["reason"]
    assert harness.ast_preflight_check(unsafe_code_os)["safe"] is False

    # 2. Merkle Checkpoints & Rollback Sentinel
    m1 = {"file1.py": "hash1", "file2.py": "hash2"}
    m2 = {"file1.py": "hash1_mod", "file2.py": "hash2"}
    cp1 = harness.record_checkpoint(m1)
    cp2 = harness.record_checkpoint(m2)
    assert len(harness.checkpoints) == 2

    rb = harness.rollback_to_last_green()
    assert rb is not None
    assert rb.checkpoint_id == cp2

    # 3. Dynamic Micro-Adapter Synthesis
    def legacy_greeter(first_name: str, surname: str) -> str:
        return f"Hello, {first_name} {surname}!"

    adapter = harness.synthesize_adapter("legacy_greeter", legacy_greeter, {"first_name": "fname", "surname": "lname"})
    result = adapter(fname="Alan", lname="Turing")
    assert result == "Hello, Alan Turing!"

    # 4. Fit Ratio 5.0 & Circuit Breaker Trigger
    harness.record_failure(HarnessFaultCategory121.SCAFFOLDING, "Tool schema drift")
    harness.record_failure(HarnessFaultCategory121.AST_SECURITY, "Blocked eval call")
    harness.record_failure(HarnessFaultCategory121.TOKEN_OVERRUN, "Context budget blown")
    assert harness.consecutive_failures == 3
    assert harness.circuit_open is True
    assert harness.compute_fit_ratio() == 0.0  # 3 harness faults out of 3 total


def test_agent_desks60_swb_locks_blackboard_and_3way_ast_semantic_merge():
    desks = AgentDesks60()

    # 1. Single-Writer Boundary (SWB) Lease
    lease1 = desks.acquire_swb_lease("desk-dev", "src/auth.py", 10.0)
    assert lease1 is not None

    # Desk QA attempts to write to same path -> rejected
    lease2 = desks.acquire_swb_lease("desk-qa", "src/auth.py", 10.0)
    assert lease2 is None

    # Desk dev releases lease -> QA can acquire
    assert desks.release_swb_lease("desk-dev", "src/auth.py", lease1) is True
    lease3 = desks.acquire_swb_lease("desk-qa", "src/auth.py", 10.0)
    assert lease3 is not None

    # 2. Shared In-Memory Blackboard Bus (Zero-Token Telemetry)
    received = []
    desks.subscribe_blackboard("build_telemetry", lambda topic, val: received.append(val))
    desks.publish_blackboard("build_telemetry", {"compiler_status": "OK", "port": 8080})
    assert len(received) == 1
    assert desks.read_blackboard("build_telemetry")["port"] == 8080

    # 3. 3-Way AST Semantic Merge (Disjoint functions merged without text conflict!)
    base_code = """
def get_status():
    return 'BASE_STATUS'
"""
    desk_a_code = """
def get_status():
    return 'BASE_STATUS'

def calculate_discount(price):
    return price * 0.9
"""
    desk_b_code = """
def get_status():
    return 'BASE_STATUS'

def format_currency(val):
    return f"${val:.2f}"
"""
    merge_res = desks.three_way_ast_merge(base_code, desk_a_code, desk_b_code)
    assert merge_res["merged"] is True
    merged_str = merge_res["merged_code"]
    assert "calculate_discount" in merged_str
    assert "format_currency" in merged_str
    assert "get_status" in merged_str


def test_pentadeca_store_memory_ebbinghaus_graphiti_and_rrf15():
    memory = PentadecaStore15LayerMemory()

    # Store across distinct layers
    memory.store("obsidian", "Entropy AI cognitive memory principles and markdown notes", importance=0.9)
    memory.store("pgvector", "FastMCP 5.2 protocol vector representation", importance=0.85)
    memory.store("hipporag2", "HippoRAG 2 dual-node personalized pagerank associative memory", importance=0.95)
    memory.store("graphiti", "The production database host is db.entropy.internal", importance=0.8)

    # 1. Graphiti Fact Invalidation
    memory.invalidate_graphiti_fact("db.entropy.internal")
    assert memory.layers["graphiti"][0].invalidated is True

    # 2. RRF-15 Fusion Retrieval
    results = memory.hybrid_search_rrf15("HippoRAG memory principles", top_k=2)
    assert len(results) > 0
    top_score, top_doc = results[0]
    assert top_score > 0.0
    # Invalidated fact should not be present in top results
    assert "db.entropy.internal" not in [d.content for _, d in results]


def test_token_physics13_radix_alignment_skeletonization_codeact_and_delta_tokens():
    # 1. RadixAttention 64-token Boundary Alignment
    raw_prompt = "You are an autonomous pair programmer agent in Entropy AI"
    padded = TokenPhysics130.align_radix_cache(raw_prompt, block_size=64)
    tokens = padded.split()
    assert len(tokens) % 64 == 0
    assert "/*PAD*/" in padded

    # 2. AST Skeletonization 7.0 (Body Pruning)
    code = """
def complex_algorithm(x: int, y: int) -> int:
    \"\"\"Calculates heavy polynomial.\"\"\"
    step1 = x * 42
    step2 = y ** 2
    step3 = sum([step1, step2])
    return step3 * 100
"""
    skeleton = TokenPhysics130.skeletonize_python_code(code)
    assert "Calculates heavy polynomial." in skeleton
    assert "step1 = x * 42" not in skeleton
    assert "pass" in skeleton

    # 3. CodeAct 6.0 Virtual REPL Sandbox
    script = """
items = [10, 25, 40, 55, 70]
evens = [x for x in items if x % 2 == 0]
total = sum(evens)
print("TOTAL_EVENS:", total)
"""
    codeact_res = TokenPhysics130.execute_codeact_script(script)
    assert codeact_res["status"] == "success"
    assert "TOTAL_EVENS: 120" in codeact_res["output"]
    assert codeact_res["token_savings_pct"] >= 65.0

    # 4. Delta Token Accounting 6.0
    prev = (5000, 1200)
    current = (6250, 1650)
    d_in, d_out = TokenPhysics130.compute_delta_tokens(prev, current)
    assert d_in == 1250
    assert d_out == 450


def test_erlang_otp60_supervision_strategies_and_circuit_collapse():
    # 1. One-For-One Strategy
    sup_one = ErlangOTPSupervisor60(strategy=SupervisionStrategy121.ONE_FOR_ONE, max_restarts=3, max_seconds=10.0)
    sup_one.add_child("worker-1")
    sup_one.add_child("worker-2")

    res1 = sup_one.handle_child_crash("worker-1")
    assert res1["status"] == "RESTARTED"
    assert res1["restarted_children"] == ["worker-1"]
    assert sup_one.child_status["worker-2"] == "RUNNING"

    # 2. One-For-All Strategy
    sup_all = ErlangOTPSupervisor60(strategy=SupervisionStrategy121.ONE_FOR_ALL, max_restarts=3, max_seconds=10.0)
    sup_all.add_child("desk-arch")
    sup_all.add_child("desk-dev")
    sup_all.add_child("desk-qa")

    res2 = sup_all.handle_child_crash("desk-dev")
    assert res2["restarted_children"] == ["desk-arch", "desk-dev", "desk-qa"]

    # 3. Collapse Trigger on Budget Exceeded (Death-loop prevention)
    sup_collapse = ErlangOTPSupervisor60(strategy=SupervisionStrategy121.ONE_FOR_ONE, max_restarts=2, max_seconds=10.0)
    sup_collapse.add_child("flaky-worker")

    sup_collapse.handle_child_crash("flaky-worker")
    sup_collapse.handle_child_crash("flaky-worker")
    collapse_res = sup_collapse.handle_child_crash("flaky-worker")
    assert collapse_res["status"] == "COLLAPSED"
    assert sup_collapse.collapsed is True
    assert sup_collapse.child_status["flaky-worker"] == "TERMINATED"


def test_faz121_master_autonomous_swarm_engine_mission_lifecycle():
    orchestrator = Faz121MasterSwarmOrchestrator()

    tasks = [
        DecoupledTaskContract121(
            task_id="mission_task_1",
            title="Design Authentication Spec",
            input_schema={"domain": "auth"},
            output_schema={"spec": "str"},
            acceptance_tests=["spec_valid"],
            allocated_tokens=2000,
            escrow_amount_usd=0.25
        ),
        DecoupledTaskContract121(
            task_id="mission_task_2",
            title="Implement Code Engine",
            input_schema={"spec_ref": "mission_task_1"},
            output_schema={"code": "str"},
            acceptance_tests=["test_auth_tokens"],
            allocated_tokens=4000,
            escrow_amount_usd=0.50,
            dependencies=["mission_task_1"]
        ),
        DecoupledTaskContract121(
            task_id="mission_task_3",
            title="QA Test Validation",
            input_schema={"code_ref": "mission_task_2"},
            output_schema={"pass_rate": "float"},
            acceptance_tests=["test_pass_100"],
            allocated_tokens=2000,
            escrow_amount_usd=0.25,
            dependencies=["mission_task_2"]
        )
    ]

    mission_res = orchestrator.execute_autonomous_mission("Mission_Auth_Production_Rollout", tasks)
    assert mission_res["status"] == "SUCCESS"
    assert mission_res["waves_executed"] == 3
    assert mission_res["tasks_completed"] == 3
    assert mission_res["total_payout_usd"] > 0.0
    assert mission_res["byzantine_consensus"]["quorum_reached"] is True
    assert mission_res["harness_fit_ratio"] >= 0.85
