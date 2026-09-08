"""
Unit & Integration Test Suite for Faz 141 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 15.0 Stateless Gateway & MRTR 206 input_required & Saga Rollback
2. Actor Model & Decoupled Task Contract 11.0
3. Erlang-OTP Supervision Trees (ONE_FOR_ONE, ONE_FOR_ALL, REST_FOR_ONE)
4. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 15.0
5. Hypervisor Agent Harness 5.0 (AST Preflight Guard 26.0 & Speculative Branches & Merkle Checkpoints)
6. Agent Desks 23.0, Linda Distributed Tuple Space 18.0 & MG-SWB 12.0
7. AAIF Horizontal Federation Router & 7D Pareto & PBFT Consensus
8. Octatriaconta-Store 38-Layer Cognitive Memory (Graphiti 3.5, HippoRAG 2, Ebbinghaus)
9. Extreme Token Physics 32.0 & AST Skeletonizer 26.0
10. Skill Progressive Disclosure Engine 141 (Tier 1/2/3)
11. Faz141MasterSwarmOrchestrator End-to-End Mission
"""

import time
import pytest
from entropy.tools.autonomous_agent_architecture_faz141 import (
    StatelessFastMCP150Engine,
    MCPToolDefinition141,
    TaskLifecycleStage141,
    ActorMessage141,
    ActorInstance141,
    DecoupledTaskContract141,
    TaskStatus141,
    SupervisionTree141,
    SupervisionStrategy141,
    DAGTaskNode141,
    KahnDAGWavefrontScheduler141,
    ASTPreflightGuard26,
    MerkleCheckpointForest141,
    HypervisorAgentHarness141,
    VirtualDesk141,
    DeskRole141,
    LindaTupleSpace141,
    MultiGranularSingleWriterBoundary141,
    AgentCard141,
    AAIFHorizontalFederationRouter141,
    OctatriacontaStoreCognitiveMemory141,
    ASTSkeletonizer26,
    TokenPhysicsEngine141,
    SkillProgressiveDisclosureEngine141,
    Faz141MasterSwarmOrchestrator
)


# ==============================================================================
# 1. FASTMCP 15.0 ENGINE TESTS
# ==============================================================================

def test_stateless_fastmcp150_engine():
    engine = StatelessFastMCP150Engine()

    state = {"db_entries": []}
    def add_entry(args):
        state["db_entries"].append(args["item"])
        return f"Added {args['item']}"

    def remove_entry(args):
        if args["item"] in state["db_entries"]:
            state["db_entries"].remove(args["item"])
        return f"Removed {args['item']}"

    tool = MCPToolDefinition141(
        name="add_db_entry",
        domain="database",
        description="Adds an entry to database.",
        parameters={"item": "str"},
        handler=add_entry,
        allowed_stages=[TaskLifecycleStage141.EXECUTION],
        cacheable=True,
        compensation_handler=remove_entry
    )
    engine.register_tool(tool)

    # 1. Check Zero-Shot Attenuation catalog (<6 tokens)
    catalog = engine.get_system_prompt_attenuated_catalog(TaskLifecycleStage141.EXECUTION)
    assert "def add_db_entry(item: str) -> Any:" in catalog

    # 2. MRTR 206 input_required on missing parameter
    headers = {"Mcp-Method": "tools/call", "Mcp-Name": "add_db_entry", "Mcp-Stage": "execution"}
    req_missing = engine.route_request(headers, {"arguments": {}})
    assert req_missing["status"] == "input_required"
    assert req_missing["code"] == 206
    assert "item" in req_missing["missing_fields"]

    # 3. Successful tool call
    req_success = engine.route_request(headers, {"arguments": {"item": "artifact_beta"}})
    assert req_success["status"] == "success"
    assert req_success["code"] == 200
    assert "artifact_beta" in state["db_entries"]
    etag = req_success["etag"]

    # 4. ETag 304 conditional request
    headers_with_etag = dict(headers)
    headers_with_etag["If-None-Match"] = etag
    req_cached = engine.route_request(headers_with_etag, {"arguments": {"item": "artifact_beta"}})
    assert req_cached["status"] == "not_modified"
    assert req_cached["code"] == 304

    # 5. Multi-modal zero copy frame pointers (grpc, shm, mmap, pipe, blob)
    req_grpc = engine.route_request({"Mcp-Method": "resources/read"}, {"uri": "grpc://cluster_node_01/stream"})
    assert req_grpc["status"] == "success"
    assert req_grpc["transport"] == "grpc_stream"

    req_mmap = engine.route_request({"Mcp-Method": "resources/read"}, {"uri": "mmap://tensor_weights_0x44"})
    assert req_mmap["status"] == "success"
    assert req_mmap["transport"] == "memory_mapped"

    # 6. Reactive resource subscription
    sub_res = engine.route_request({"Mcp-Method": "resources/subscribe"}, {"uri": "stream://sensor_telemetry", "subscriber_id": "agent_monitor"})
    assert sub_res["status"] == "subscribed"
    assert sub_res["subscriber"] == "agent_monitor"

    # 7. Saga Rollback
    rollback_res = engine.rollback_saga()
    assert len(rollback_res) == 1
    assert rollback_res[0]["status"] == "compensated"
    assert "artifact_beta" not in state["db_entries"]


# ==============================================================================
# 2. ACTOR MODEL & DECOUPLED TASK CONTRACT TESTS
# ==============================================================================

def test_actor_model_and_decoupled_task():
    contract = DecoupledTaskContract141(
        task_id="task_141_core",
        title="Implement Bitemporal Memory",
        spec={"module": "memory", "valid_time": True}
    )
    assert contract.status == TaskStatus141.UNASSIGNED

    # Lease acquisition
    acquired = contract.acquire_lease("agent_code_architect")
    assert acquired is True
    assert contract.status == TaskStatus141.ACQUIRED
    assert contract.assigned_agent == "agent_code_architect"

    # Heartbeat
    hb = contract.heartbeat("agent_code_architect")
    assert hb is True

    # State transitions
    contract.transition_to(TaskStatus141.IN_PROGRESS)
    assert contract.status == TaskStatus141.IN_PROGRESS
    contract.transition_to(TaskStatus141.SPECULATING)
    assert contract.status == TaskStatus141.SPECULATING
    contract.transition_to(TaskStatus141.COMPLETED)
    assert contract.status == TaskStatus141.COMPLETED
    assert len(contract.state_history) == 4


# ==============================================================================
# 3. ERLANG-OTP SUPERVISION TREE TESTS
# ==============================================================================

def test_erlang_otp_supervision():
    sup = SupervisionTree141(SupervisionStrategy141.REST_FOR_ONE, max_restarts=3)

    actor1 = ActorInstance141("worker_1", "worker", lambda m: f"w1:{m.action}")
    actor2 = ActorInstance141("worker_2", "worker", lambda m: f"w2:{m.action}")
    actor3 = ActorInstance141("worker_3", "worker", lambda m: f"w3:{m.action}")

    sup.register_child(actor1)
    sup.register_child(actor2)
    sup.register_child(actor3)

    # Post message and process
    actor1.post(ActorMessage141("m1", "tester", "worker_1", "ping", {}))
    res = actor1.process_next()
    assert res == "w1:ping"
    assert actor1.processed_count == 1

    # Simulate failure on worker_2 under REST_FOR_ONE -> worker_2 and worker_3 restarted
    rec = sup.handle_child_failure("worker_2")
    assert rec["status"] == "recovered"
    assert rec["strategy"] == "REST_FOR_ONE"
    assert rec["restarted_actors"] == ["worker_2", "worker_3"]
    assert actor2.restart_count == 1
    assert actor3.restart_count == 1
    assert actor1.restart_count == 0


# ==============================================================================
# 4. KAHN DAG WAVEFRONT & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_cpm_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler141()

    # t1 -> t2 -> t4
    # t1 -> t3 (short) -> t4
    t1 = DAGTaskNode141("t1_research", 1.0, 2.0, 3.0)  # Te = 2.0
    t2 = DAGTaskNode141("t2_heavy_code", 4.0, 6.0, 8.0, dependencies=["t1_research"])  # Te = 6.0
    t3 = DAGTaskNode141("t3_light_docs", 0.5, 1.0, 1.5, dependencies=["t1_research"])  # Te = 1.0
    t4 = DAGTaskNode141("t4_deploy", 1.0, 2.0, 3.0, dependencies=["t2_heavy_code", "t3_light_docs"])  # Te = 2.0

    scheduler.add_node(t1)
    scheduler.add_node(t2)
    scheduler.add_node(t3)
    scheduler.add_node(t4)

    plan = scheduler.compute_schedule_and_wavefronts()
    assert len(plan["wavefronts"]) == 3
    assert plan["wavefronts"][0] == ["t1_research"]
    assert set(plan["wavefronts"][1]) == {"t2_heavy_code", "t3_light_docs"}
    assert plan["wavefronts"][2] == ["t4_deploy"]

    # Critical path: t1 -> t2 -> t4 (duration: 2 + 6 + 2 = 10)
    assert plan["critical_path"] == ["t1_research", "t2_heavy_code", "t4_deploy"]
    assert pytest.approx(plan["total_duration"], 0.01) == 10.0

    tasks = plan["tasks"]
    assert tasks["t2_heavy_code"]["slack"] == 0.0
    assert "Frontier Reasoning" in tasks["t2_heavy_code"]["model"]

    # t3 has slack = 5.0
    assert tasks["t3_light_docs"]["slack"] > 0.0
    assert "Cost & Speed Optimized" in tasks["t3_light_docs"]["model"]


# ==============================================================================
# 5. HYPERVISOR AGENT HARNESS & GUARDRAIL TESTS
# ==============================================================================

def test_hypervisor_harness_guardrails_and_speculation():
    # 1. AST Preflight Guard checks
    malicious_code_1 = "import subprocess\nsubprocess.run(['rm', '-rf', '/'])"
    res1 = ASTPreflightGuard26.inspect_code(malicious_code_1)
    assert res1["safe"] is False
    assert any("Forbidden module import" in v for v in res1["violations"])

    malicious_code_2 = "import os\nos.system('calc.exe')"
    res2 = ASTPreflightGuard26.inspect_code(malicious_code_2)
    assert res2["safe"] is False
    assert any("Dangerous OS execution" in v for v in res2["violations"])

    malicious_code_3 = "x = eval('2 + 2')"
    res3 = ASTPreflightGuard26.inspect_code(malicious_code_3)
    assert res3["safe"] is False
    assert any("Forbidden built-in call: 'eval()'" in v for v in res3["violations"])

    safe_code = "def add(a: int, b: int) -> int:\n    return a + b"
    res_safe = ASTPreflightGuard26.inspect_code(safe_code)
    assert res_safe["safe"] is True

    # 2. Speculative Branch Evaluation
    harness = HypervisorAgentHarness141(initial_temp=0.7, cooling_rate=0.45)
    candidates = [
        {"id": "cand_unsafe", "code": "import subprocess\nsubprocess.call(['ls'])"},
        {"id": "cand_safe", "code": "def process_data(data: list) -> list:\n    return sorted(data)"}
    ]
    branch_res = harness.evaluate_speculative_branches(candidates)
    assert branch_res["selected_branch"] == "cand_safe"
    assert branch_res["score"] > 0.0

    # 3. Dynamic Temperature Cooling
    t0 = harness.compute_dynamic_temperature(0)
    t1 = harness.compute_dynamic_temperature(1)
    t2 = harness.compute_dynamic_temperature(2)
    assert t0 == 0.7
    assert pytest.approx(t1, 0.01) == 0.315
    assert pytest.approx(t2, 0.01) == 0.1417

    # 4. Merkle Checkpoints
    forest = harness.checkpoint_forest
    files = {"src/main.py": "print('hello')", "src/utils.py": "def foo(): pass"}
    root_hash = forest.create_checkpoint("cp_1", files)
    assert len(root_hash) == 64

    ver_ok = forest.verify_consistency("cp_1", files)
    assert ver_ok["consistent"] is True

    ver_tamper = forest.verify_consistency("cp_1", {"src/main.py": "tampered", "src/utils.py": "def foo(): pass"})
    assert ver_tamper["consistent"] is False
    assert any("Modified file: src/main.py" in d for d in ver_tamper["diffs"])


# ==============================================================================
# 6. AGENT DESKS, LINDA TUPLE SPACE & MG-SWB TESTS
# ==============================================================================

def test_agent_desks_and_linda_tuple_space():
    # 1. Multi-Granular Single-Writer Boundary (MG-SWB)
    boundary = MultiGranularSingleWriterBoundary141()
    acq1 = boundary.acquire_file_lease("src/core.py", "desk_architecture", duration_sec=5.0)
    assert acq1 is True

    # Concurrent attempt by engineering desk should fail
    acq2 = boundary.acquire_file_lease("src/core.py", "desk_engineering", duration_sec=5.0)
    assert acq2 is False

    # Check vector clock
    clock = boundary.get_clock("src/core.py")
    assert clock["desk_architecture"] == 1

    # Release and acquire
    boundary.release_file_lease("src/core.py", "desk_architecture")
    acq3 = boundary.acquire_file_lease("src/core.py", "desk_engineering", duration_sec=5.0)
    assert acq3 is True

    # 2. Linda Distributed Tuple Space
    linda = LindaTupleSpace141()
    observed = []
    linda.watch(("code_review", None, "ready"), lambda t: observed.append(t))

    linda.out(("code_review", "PR_101", "ready"))
    assert len(observed) == 1
    assert observed[0] == ("code_review", "PR_101", "ready")

    # Read non-destructively
    rd_res = linda.rd(("code_review", None, "ready"))
    assert rd_res == ("code_review", "PR_101", "ready")

    # In destructively
    in_res = linda.in_tuple(("code_review", "PR_101", None))
    assert in_res == ("code_review", "PR_101", "ready")
    assert linda.rd(("code_review", None, "ready")) is None


# ==============================================================================
# 7. AAIF A2A FEDERATION ROUTER & PBFT CONSENSUS TESTS
# ==============================================================================

def test_aaif_federation_router_and_pbft():
    router = AAIFHorizontalFederationRouter141("secret_key_141")

    c1 = AgentCard141("agent_fast_coder", "Fast Coder", "1.0", ["coding", "refactoring"], "http://localhost:8001", 0.92, 120.0, 0.40, 0.99, domain_authority=0.95)
    c2 = AgentCard141("agent_deep_reasoner", "Deep Reasoner", "2.0", ["coding", "architecture"], "http://localhost:8002", 0.98, 450.0, 2.50, 0.98, domain_authority=0.98)

    router.register_agent(c1)
    router.register_agent(c2)

    # 7D Pareto Optimal Agent selection
    best_coder = router.select_pareto_optimal_agent("coding")
    assert best_coder is not None
    assert best_coder.agent_id in ["agent_fast_coder", "agent_deep_reasoner"]

    # 3-Phase PBFT Byzantine Consensus
    agents = ["agent_fast_coder", "agent_deep_reasoner", "agent_extra_1", "agent_extra_2"]
    router.register_agent(AgentCard141("agent_extra_1", "E1", "1", ["test"], "url", 0.9, 100, 1, 0.9))
    router.register_agent(AgentCard141("agent_extra_2", "E2", "1", ["test"], "url", 0.9, 100, 1, 0.9))

    proposal = {"action": "commit_architecture_v141", "hash": "abc012"}
    pbft_res = router.execute_pbft_consensus(proposal, agents)
    assert pbft_res["consensus"] is True
    assert pbft_res["phase"] == "committed"
    assert pbft_res["votes"] >= pbft_res["quorum"]


# ==============================================================================
# 8. OCTATRIACONTA-STORE 38-LAYER COGNITIVE MEMORY & GRAPHRAG TESTS
# ==============================================================================

def test_octatriaconta_store_memory_and_hipporag():
    mem = OctatriacontaStoreCognitiveMemory141()

    # 1. Bi-temporal relations
    t_start = 100.0
    t_end = 200.0
    mem.insert_bitemporal_relation("AgentA", "ToolX", "deprecates", valid_from=t_start, valid_until=t_end)
    mem.insert_bitemporal_relation("AgentA", "ToolY", "adopts", valid_from=150.0)

    # Time-travel queries
    q1 = mem.query_relations_at_time(120.0)
    assert len(q1) == 1
    assert q1[0].target_entity == "ToolX"

    q2 = mem.query_relations_at_time(180.0)
    assert len(q2) == 2  # Both valid at t=180

    q3 = mem.query_relations_at_time(250.0)
    assert len(q3) == 1
    assert q3[0].target_entity == "ToolY"

    # 2. HippoRAG 2 Personalized PageRank (PPR)
    mem.insert_bitemporal_relation("Core", "ModuleA", "includes", 0)
    mem.insert_bitemporal_relation("ModuleA", "SubModuleB", "links", 0)
    mem.insert_bitemporal_relation("SubModuleB", "DeepNodeC", "calls", 0)

    ranks = mem.hipporag_personalized_pagerank("Core")
    assert "Core" in ranks
    assert "ModuleA" in ranks
    assert ranks["ModuleA"] > ranks["DeepNodeC"]  # 1-hop stronger than 3-hop

    # 3. Ebbinghaus forgetting retention
    retention_fresh = mem.compute_ebbinghaus_retention(1.0, elapsed_seconds=10, repetitions=1)
    retention_old = mem.compute_ebbinghaus_retention(1.0, elapsed_seconds=50000, repetitions=1)
    assert retention_fresh > retention_old

    # With repetitions retention increases
    retention_repeated = mem.compute_ebbinghaus_retention(1.0, elapsed_seconds=50000, repetitions=10)
    assert retention_repeated > retention_old

    # 4. Hybrid RRF-38 score
    rrf = mem.hybrid_rrf_38_score(dense_rank=1, sparse_rank=2, graph_rank=1)
    assert rrf > 0.0


# ==============================================================================
# 9. EXTREME TOKEN PHYSICS & AST SKELETONIZER TESTS
# ==============================================================================

def test_extreme_token_physics_and_skeletonizer():
    # 1. Delta Token Accounting
    d_in, d_out = TokenPhysicsEngine141.compute_turn_delta(
        cumulative_input=1500,
        cumulative_output=600,
        prev_input=1000,
        prev_output=400
    )
    assert d_in == 500
    assert d_out == 200

    # 2. Radix KV Cache block alignment
    aligned_64 = TokenPhysicsEngine141.align_radix_kv_cache(70, block_size=64)
    assert aligned_64 == 128
    aligned_exact = TokenPhysicsEngine141.align_radix_kv_cache(128, block_size=64)
    assert aligned_exact == 128

    # 3. AST Skeletonizer 26.0
    sample_func = (
        "def compute_hash(data: str) -> str:\n"
        "    \"\"\"Docstring to retain.\"\"\"\n"
        "    x = data.strip()\n"
        "    y = x.encode('utf-8')\n"
        "    return hashlib.sha256(y).hexdigest()\n"
    )
    skeleton = ASTSkeletonizer26.skeletonize(sample_func)
    assert "def compute_hash(data: str) -> str:" in skeleton
    assert '"""Docstring to retain."""' in skeleton
    assert "pass" in skeleton
    assert "hashlib.sha256" not in skeleton  # Body pruned!


# ==============================================================================
# 10. SKILL PROGRESSIVE DISCLOSURE TESTS
# ==============================================================================

def test_skill_progressive_disclosure():
    engine = SkillProgressiveDisclosureEngine141(
        skill_name="k8s_deploy",
        discovery_yaml="name: k8s_deploy\ndescription: Deploys pods to cluster\n",
        activation_md="# Instructions for k8s_deploy\nUse kubectl apply -f ...\n",
        execution_script="kubectl apply -f manifest.yaml"
    )

    t1 = engine.get_tier(1)
    assert "name: k8s_deploy" in t1
    assert len(t1) < 100

    t2 = engine.get_tier(2)
    assert "# Instructions for k8s_deploy" in t2

    t3 = engine.get_tier(3)
    assert "kubectl apply -f manifest.yaml" in t3


# ==============================================================================
# 11. FAZ 141 MASTER SWARM ORCHESTRATOR END-TO-END TEST
# ==============================================================================

def test_faz141_master_swarm_orchestrator_end_to_end():
    orchestrator = Faz141MasterSwarmOrchestrator()
    mission_spec = {"mission": "deploy_autonomous_ai_os_faz141"}
    res = orchestrator.execute_full_mission(mission_spec)

    assert res["mission_status"] == "SUCCESS"
    assert "critical_path" in res
    assert len(res["critical_path"]) > 0
    assert res["code_safe"] is True
    assert res["linda_tuples"] >= 1
    assert "AgentArchitect" in res["ppr_associative_memory"]
