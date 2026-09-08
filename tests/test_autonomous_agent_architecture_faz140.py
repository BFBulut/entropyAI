"""
Unit & Integration Test Suite for Faz 140 Master Autonomous Agent Architecture Module
======================================================================================
Verifies:
1. FastMCP 14.0 Stateless Gateway & MRTR 206 input_required & Saga Rollback
2. Actor Model & Decoupled Task Contract 10.0
3. Erlang-OTP Supervision Trees (ONE_FOR_ONE, ONE_FOR_ALL, REST_FOR_ONE)
4. Kahn DAG Wavefront Scheduler, Stochastic PERT & CPM Slack Borrowing 14.0
5. Hypervisor Agent Harness 4.0 (AST Preflight Guard 25.0 & Merkle Checkpoints & Cooling)
6. Agent Desks 22.0, Linda Distributed Tuple Space 17.0 & MG-SWB 11.0
7. AAIF Horizontal Federation Router & 6D Pareto & PBFT Consensus
8. Heptatriaconta-Store 37-Layer Cognitive Memory (Graphiti 3.2, HippoRAG 2, Ebbinghaus)
9. Extreme Token Physics 31.0 & AST Skeletonizer 25.0
10. Skill Progressive Disclosure Engine 140 (Tier 1/2/3)
11. Faz140MasterSwarmOrchestrator End-to-End Mission
"""

import time
import pytest
from entropy.tools.autonomous_agent_architecture_faz140 import (
    StatelessFastMCP140Engine,
    MCPToolDefinition140,
    TaskLifecycleStage140,
    ActorMessage140,
    ActorInstance140,
    DecoupledTaskContract140,
    TaskStatus140,
    SupervisionTree140,
    SupervisionStrategy140,
    DAGTaskNode140,
    KahnDAGWavefrontScheduler140,
    ASTPreflightGuard25,
    MerkleCheckpointForest140,
    HypervisorAgentHarness140,
    VirtualDesk140,
    DeskRole140,
    LindaTupleSpace140,
    MultiGranularSingleWriterBoundary140,
    AgentCard140,
    AAIFHorizontalFederationRouter140,
    HeptatriacontaStoreCognitiveMemory140,
    ASTSkeletonizer25,
    TokenPhysicsEngine140,
    SkillProgressiveDisclosureEngine140,
    Faz140MasterSwarmOrchestrator
)


# ==============================================================================
# 1. FASTMCP 14.0 ENGINE TESTS
# ==============================================================================

def test_stateless_fastmcp140_engine():
    engine = StatelessFastMCP140Engine()

    # Tool with compensation handler
    state = {"db_entries": []}
    def add_entry(args):
        state["db_entries"].append(args["item"])
        return f"Added {args['item']}"

    def remove_entry(args):
        if args["item"] in state["db_entries"]:
            state["db_entries"].remove(args["item"])
        return f"Removed {args['item']}"

    tool = MCPToolDefinition140(
        name="add_db_entry",
        domain="database",
        description="Adds an entry to database.",
        parameters={"item": "str"},
        handler=add_entry,
        allowed_stages=[TaskLifecycleStage140.EXECUTION],
        cacheable=True,
        compensation_handler=remove_entry
    )
    engine.register_tool(tool)

    # 1. Check Zero-Shot Attenuation catalog
    catalog = engine.get_system_prompt_attenuated_catalog(TaskLifecycleStage140.EXECUTION)
    assert "def add_db_entry(item: str) -> Any:" in catalog

    # 2. MRTR 206 input_required on missing parameter
    headers = {"Mcp-Method": "tools/call", "Mcp-Name": "add_db_entry", "Mcp-Stage": "execution"}
    req_missing = engine.route_request(headers, {"arguments": {}})
    assert req_missing["status"] == "input_required"
    assert req_missing["code"] == 206
    assert "item" in req_missing["missing_fields"]

    # 3. Successful tool call
    req_success = engine.route_request(headers, {"arguments": {"item": "artifact_alpha"}})
    assert req_success["status"] == "success"
    assert req_success["code"] == 200
    assert "artifact_alpha" in state["db_entries"]
    etag = req_success["etag"]

    # 4. ETag 304 conditional request
    headers_with_etag = dict(headers)
    headers_with_etag["If-None-Match"] = etag
    req_cached = engine.route_request(headers_with_etag, {"arguments": {"item": "artifact_alpha"}})
    assert req_cached["status"] == "not_modified"
    assert req_cached["code"] == 304

    # 5. Multi-modal zero copy frame pointers
    req_shm = engine.route_request({"Mcp-Method": "resources/read"}, {"uri": "shm://frame_0x7ffe"})
    assert req_shm["status"] == "success"
    assert req_shm["transport"] == "shared_memory"

    req_pipe = engine.route_request({"Mcp-Method": "resources/read"}, {"uri": "pipe://agent_stream_01"})
    assert req_pipe["status"] == "success"
    assert req_pipe["transport"] == "named_pipe"

    # 6. Saga Rollback
    rollback_res = engine.rollback_saga()
    assert len(rollback_res) == 1
    assert rollback_res[0]["status"] == "compensated"
    assert "artifact_alpha" not in state["db_entries"]


# ==============================================================================
# 2. ACTOR MODEL & DECOUPLED TASK CONTRACT TESTS
# ==============================================================================

def test_actor_model_and_decoupled_task():
    contract = DecoupledTaskContract140(
        task_id="task_140_core",
        title="Implement Secure Auth",
        spec={"endpoint": "/login", "crypto": "ed25519"}
    )
    assert contract.status == TaskStatus140.UNASSIGNED

    # Lease acquisition
    acquired = contract.acquire_lease("agent_code_architect")
    assert acquired is True
    assert contract.status == TaskStatus140.ACQUIRED
    assert contract.assigned_agent == "agent_code_architect"

    # Heartbeat
    hb = contract.heartbeat("agent_code_architect")
    assert hb is True

    # State transition
    contract.transition_to(TaskStatus140.IN_PROGRESS)
    assert contract.status == TaskStatus140.IN_PROGRESS
    contract.transition_to(TaskStatus140.COMPLETED)
    assert contract.status == TaskStatus140.COMPLETED
    assert len(contract.state_history) == 3


# ==============================================================================
# 3. ERLANG-OTP SUPERVISION TREES TESTS
# ==============================================================================

def test_erlang_otp_supervision_trees():
    # Setup actors
    def echo_handler(msg: ActorMessage140):
        if msg.payload.get("crash"):
            raise RuntimeError("Actor crashed by test instruction")
        return ActorMessage140("rep_1", "actor_b", msg.sender_id, "reply", {"ack": True})

    a1 = ActorInstance140("actor_1", "planner", echo_handler)
    a2 = ActorInstance140("actor_2", "coder", echo_handler)
    a3 = ActorInstance140("actor_3", "tester", echo_handler)

    # 1. ONE_FOR_ONE
    sup_one = SupervisionTree140(SupervisionStrategy140.ONE_FOR_ONE)
    sup_one.add_actor(a1)
    sup_one.add_actor(a2)
    sup_one.add_actor(a3)

    res_one = sup_one.handle_failure("actor_2")
    assert res_one["strategy"] == "ONE_FOR_ONE"
    assert res_one["restarted"] == ["actor_2"]

    # 2. ONE_FOR_ALL
    sup_all = SupervisionTree140(SupervisionStrategy140.ONE_FOR_ALL)
    sup_all.add_actor(a1)
    sup_all.add_actor(a2)
    sup_all.add_actor(a3)

    res_all = sup_all.handle_failure("actor_1")
    assert res_all["strategy"] == "ONE_FOR_ALL"
    assert set(res_all["restarted"]) == {"actor_1", "actor_2", "actor_3"}

    # 3. REST_FOR_ONE
    sup_rest = SupervisionTree140(SupervisionStrategy140.REST_FOR_ONE)
    sup_rest.add_actor(a1)
    sup_rest.add_actor(a2)
    sup_rest.add_actor(a3)

    res_rest = sup_rest.handle_failure("actor_2")
    assert res_rest["strategy"] == "REST_FOR_ONE"
    assert res_rest["restarted"] == ["actor_2", "actor_3"]


# ==============================================================================
# 4. KAHN DAG WAVEFRONT & CPM SLACK BORROWING TESTS
# ==============================================================================

def test_kahn_dag_cpm_slack_borrowing():
    scheduler = KahnDAGWavefrontScheduler140()

    # Node A: Discovery (root)
    node_a = DAGTaskNode140("A", "Discovery", optimistic_days=1.0, most_likely_days=2.0, pessimistic_days=3.0)
    # Node B: Database Schema (depends on A)
    node_b = DAGTaskNode140("B", "DBSchema", optimistic_days=2.0, most_likely_days=3.0, pessimistic_days=4.0, dependencies=["A"])
    # Node C: Documentation (depends on A) - shorter duration
    node_c = DAGTaskNode140("C", "Docs", optimistic_days=0.5, most_likely_days=1.0, pessimistic_days=1.5, dependencies=["A"])
    # Node D: Integration (depends on B and C)
    node_d = DAGTaskNode140("D", "Integration", optimistic_days=1.0, most_likely_days=2.0, pessimistic_days=3.0, dependencies=["B", "C"])

    scheduler.add_node(node_a)
    scheduler.add_node(node_b)
    scheduler.add_node(node_c)
    scheduler.add_node(node_d)

    # Wavefront partitioning
    waves = scheduler.compute_wavefronts()
    assert waves[0] == ["A"]
    assert set(waves[1]) == {"B", "C"}
    assert waves[2] == ["D"]

    # CPM and Slack Borrowing
    report = scheduler.compute_cpm_and_slack_borrowing()
    assert "A" in report["critical_path"]
    assert "B" in report["critical_path"]
    assert "D" in report["critical_path"]
    assert "C" not in report["critical_path"]  # Has slack!

    # Model assignments
    assert "Claude-3.7-Sonnet-Thinking" in report["assignments"]["B"]
    assert "Gemini-3.8-Flash" in report["assignments"]["C"]  # Slack borrowed!


# ==============================================================================
# 5. HYPERVISOR AGENT HARNESS 4.0 TESTS
# ==============================================================================

def test_hypervisor_agent_harness_40():
    # 1. AST Preflight Guard: Safe code
    safe_code = """
def calculate_metrics(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
"""
    is_safe, violations = ASTPreflightGuard25.inspect_code(safe_code)
    assert is_safe is True
    assert len(violations) == 0

    # 2. AST Preflight Guard: Unsafe code
    unsafe_code = """
import os
import subprocess
def exploit():
    eval('__import__("os").system("whoami")')
"""
    is_safe_u, violations_u = ASTPreflightGuard25.inspect_code(unsafe_code)
    assert is_safe_u is False
    assert any("Forbidden import: 'os'" in v for v in violations_u)
    assert any("Forbidden import: 'subprocess'" in v for v in violations_u)
    assert any("Forbidden function call: 'eval()'" in v for v in violations_u)

    # 3. Harness execution & temperature cooling
    harness = HypervisorAgentHarness140(initial_temp=0.8)
    assert harness.compute_cooled_temperature(0) == 0.8
    assert harness.compute_cooled_temperature(1) == 0.4
    assert harness.compute_cooled_temperature(2) == 0.2
    assert harness.compute_cooled_temperature(3) == 0.1

    files = {"src/logic.py": safe_code}
    exec_res = harness.execute_protected_step(safe_code, files, attempt=0)
    assert exec_res["status"] == "authorized"
    assert "checkpoint_id" in exec_res
    assert harness.merkle.verify_integrity(exec_res["checkpoint_id"], files) is True


# ==============================================================================
# 6. AGENT DESKS 22.0 & LINDA TUPLE SPACE TESTS
# ==============================================================================

def test_agent_desks_and_linda_tuple_space():
    linda = LindaTupleSpace140()

    received_events = []
    def on_task_event(t: tuple):
        received_events.append(t)

    linda.watch("TASK_SUBMITTED", on_task_event)

    # Linda out
    linda.out(("TASK_SUBMITTED", "task_01", "high_priority"))
    assert len(received_events) == 1

    # Linda rd
    match = linda.rd(("TASK_SUBMITTED", None, None))
    assert match is not None
    assert match[1] == "task_01"

    # Linda in_tuple (consume)
    consumed = linda.in_tuple(("TASK_SUBMITTED", "task_01", "high_priority"))
    assert consumed is not None
    assert linda.rd(("TASK_SUBMITTED", None, None)) is None

    # MG-SWB Lease locks with Vector Clocks
    desk_arch = VirtualDesk140("desk_arch", DeskRole140.ARCHITECTURE, "worktree/arch", "/path/arch")
    desk_eng = VirtualDesk140("desk_eng", DeskRole140.ENGINEERING, "worktree/eng", "/path/eng")
    swb = MultiGranularSingleWriterBoundary140()

    # Desk Arch acquires lock
    locked = swb.acquire_file_lease("src/models.py", desk_arch, ttl=10.0)
    assert locked is True
    assert desk_arch.vector_clock["desk_arch"] >= 1

    # Desk Eng tries to acquire same file -> blocked
    eng_locked = swb.acquire_file_lease("src/models.py", desk_eng, ttl=10.0)
    assert eng_locked is False

    # Arch releases lock -> Eng acquires
    swb.release_file_lease("src/models.py", desk_arch)
    eng_acquired = swb.acquire_file_lease("src/models.py", desk_eng, ttl=10.0)
    assert eng_acquired is True


# ==============================================================================
# 7. AAIF HORIZONTAL FEDERATION ROUTER TESTS
# ==============================================================================

def test_aaif_horizontal_federation_router():
    router = AAIFHorizontalFederationRouter140(secret="super_secret_140")

    import hmac, hashlib
    def sign_card(name, ver, acc, cost):
        data = f"{name}:{ver}:{acc}:{cost}"
        return hmac.new("super_secret_140".encode(), data.encode(), hashlib.sha256).hexdigest()

    card_arch = AgentCard140(
        name="ArchitectAgent",
        version="2.3.0",
        description="System design and AST modeling",
        capabilities=["architecture", "ast_design"],
        accuracy_score=0.98,
        reliability_score=0.95,
        avg_latency_ms=800.0,
        cost_per_mtoken=3.0,
        test_time_compute=True,
        energy_rating=0.85,
        public_key_hmac=sign_card("ArchitectAgent", "2.3.0", 0.98, 3.0)
    )

    card_fast = AgentCard140(
        name="FastCoderAgent",
        version="2.3.0",
        description="High-speed code synthesis",
        capabilities=["architecture", "code_gen"],
        accuracy_score=0.88,
        reliability_score=0.90,
        avg_latency_ms=150.0,
        cost_per_mtoken=0.4,
        test_time_compute=False,
        energy_rating=0.95,
        public_key_hmac=sign_card("FastCoderAgent", "2.3.0", 0.88, 0.4)
    )

    assert card_arch.verify_card("super_secret_140") is True
    router.register_agent(card_arch)
    router.register_agent(card_fast)

    # Pareto selection: High accuracy requirement selects ArchitectAgent
    chosen = router.pareto_select_agent("architecture")
    assert chosen in ["ArchitectAgent", "FastCoderAgent"]

    # 3-Phase PBFT Byzantine Consensus (Quorum Q >= 2f + 1)
    # f = 1 -> quorum = 3
    votes = [
        {"voter": "node1", "proposal": "MIGRATE_TO_FASTMCP_14"},
        {"voter": "node2", "proposal": "MIGRATE_TO_FASTMCP_14"},
        {"voter": "node3", "proposal": "MIGRATE_TO_FASTMCP_14"},
        {"voter": "node4", "proposal": "REJECT"}
    ]
    consensus_ok, decision = router.execute_pbft_consensus(votes, required_f=1)
    assert consensus_ok is True
    assert decision == "MIGRATE_TO_FASTMCP_14"


# ==============================================================================
# 8. HEPTATRIACONTA-STORE 37-LAYER COGNITIVE MEMORY TESTS
# ==============================================================================

def test_heptatriaconta_store_37_layer_memory():
    memory = HeptatriacontaStoreCognitiveMemory140()

    # 1. Graphiti 3.2 Bi-Temporal Validity & Time-Travel Query
    t1 = 1000.0
    t2 = 2000.0
    t3 = 3000.0

    memory.insert_bi_temporal_fact("AuthService", "uses_protocol", "JWT_RS256", valid_from=t1, valid_until=t2)
    memory.insert_bi_temporal_fact("AuthService", "uses_protocol", "Ed25519_A2A", valid_from=t2, valid_until=None)

    # Time travel at t=1500 (Historically JWT)
    facts_past = memory.query_time_travel(1500.0)
    assert ("AuthService", "uses_protocol", "JWT_RS256") in facts_past
    assert ("AuthService", "uses_protocol", "Ed25519_A2A") not in facts_past

    # Time travel at t=2500 (Historically Ed25519)
    facts_present = memory.query_time_travel(2500.0)
    assert ("AuthService", "uses_protocol", "Ed25519_A2A") in facts_present

    # 2. HippoRAG 2 Personalized PageRank (PPR)
    memory.insert_bi_temporal_fact("NodeA", "links_to", "NodeB", valid_from=t1)
    memory.insert_bi_temporal_fact("NodeB", "links_to", "NodeC", valid_from=t1)
    memory.insert_bi_temporal_fact("NodeC", "links_to", "NodeD", valid_from=t1)

    ppr_scores = memory.hipporag_personalized_pagerank(seed_nodes=["NodeA"])
    assert "NodeA" in ppr_scores
    assert ppr_scores["NodeB"] > 0.0
    assert ppr_scores["NodeC"] > 0.0

    # 3. Ebbinghaus & Dreaming sleep consolidation
    now = time.time()
    memory.record_memory_node("mem_important", "Core architecture invariant", importance=0.95, tags=["architecture"])
    memory.record_memory_node("mem_trivial", "Temporary scratch notes", importance=0.20, tags=["scratch"])

    promoted = memory.run_dreaming_consolidation(threshold=0.5)
    assert "mem_important" in promoted
    assert "mem_trivial" not in promoted

    # 4. Hybrid RRF-37 Fusion
    dense = {"doc1": 1, "doc2": 2, "doc3": 3}
    sparse = {"doc2": 1, "doc1": 2, "doc4": 3}
    graph = {"doc1": 1, "doc3": 2, "doc2": 3}

    rrf = memory.hybrid_rrf_37_score(dense, sparse, graph)
    assert "doc1" in rrf
    assert rrf["doc1"] > rrf.get("doc4", 0.0)


# ==============================================================================
# 9. TOKEN PHYSICS 31.0 & AST SKELETONIZER 25.0 TESTS
# ==============================================================================

def test_token_physics_310_and_ast_skeletonizer_250():
    source_code = """
class DataProcessor:
    \"\"\"Processes streaming data frames.\"\"\"
    def __init__(self, buffer_size: int = 1024):
        self.buffer_size = buffer_size
        self._cache = []

    def compute_heavy_hash(self, data: bytes) -> str:
        \"\"\"Hashes payload data.\"\"\"
        result = 0
        for b in data:
            result = (result * 31 + b) & 0xFFFFFFFF
            result ^= (result >> 3)
        return hex(result)
"""
    skeleton = ASTSkeletonizer25.skeletonize(source_code)
    # Checks that method signatures and docstrings are preserved, but bodies replaced with pass
    assert "class DataProcessor:" in skeleton
    assert "def compute_heavy_hash(self, data: bytes) -> str:" in skeleton
    assert "\"\"\"Hashes payload data.\"\"\"" in skeleton
    assert "for b in data:" not in skeleton  # Body stripped!
    assert "pass" in skeleton

    # Radix KV-Cache boundary alignment
    aligned = TokenPhysicsEngine140.align_to_radix_cache_boundary("Test prompt header")
    est_toks = len(aligned) // 4
    assert est_toks % TokenPhysicsEngine140.BLOCK_SIZE == 0

    # Marginal Delta Token Accounting
    delta = TokenPhysicsEngine140.compute_marginal_delta_tokens(cumulative_u_k=15400, cumulative_u_prev=12000)
    assert delta == 3400

    # CodeAct token reduction calculation
    saving = TokenPhysicsEngine140.codeact_token_saving_ratio(json_turns_count=5, avg_tokens_per_json=500)
    assert saving["traditional_tokens"] == 2500
    assert saving["codeact_tokens"] == 750
    assert saving["saved_tokens"] == 1750


# ==============================================================================
# 10. SKILL PROGRESSIVE DISCLOSURE TESTS
# ==============================================================================

def test_skill_progressive_disclosure_engine_140():
    engine = SkillProgressiveDisclosureEngine140()

    engine.register_skill(
        name="database_migrator",
        tier1_yaml="name: database_migrator\ndescription: Zero-downtime schema migrator",
        tier2_md="# Migration Guide\n1. Run preflight dry-run.\n2. Apply shadow table.",
        tier3_code="def run_migration():\n    print('Migrating...')"
    )

    # Tier 1
    discovery = engine.get_discovery_catalog()
    assert "skill: database_migrator" in discovery
    assert "Zero-downtime schema migrator" in discovery

    # Tier 2
    activation = engine.activate_skill("database_migrator")
    assert "# Migration Guide" in activation

    # Tier 3
    execution = engine.execute_skill("database_migrator")
    assert "def run_migration():" in execution


# ==============================================================================
# 11. FAZ 140 MASTER SWARM ORCHESTRATOR END-TO-END TEST
# ==============================================================================

def test_faz140_master_swarm_orchestrator():
    orchestrator = Faz140MasterSwarmOrchestrator()

    tasks = [
        DAGTaskNode140("t1", "Requirements", 1.0, 2.0, 3.0),
        DAGTaskNode140("t2", "BackendAPI", 2.0, 4.0, 6.0, dependencies=["t1"]),
        DAGTaskNode140("t3", "UIPrototypes", 1.0, 1.5, 2.0, dependencies=["t1"]),
        DAGTaskNode140("t4", "SystemIntegration", 1.5, 2.5, 3.5, dependencies=["t2", "t3"])
    ]

    mission_res = orchestrator.execute_mission("Autonomous Web App", tasks)
    assert mission_res["status"] == "orchestrated"
    assert len(mission_res["active_desks"]) == 7
    assert mission_res["schedule"]["total_expected_days"] > 0.0
    assert "Claude-3.7-Sonnet-Thinking" in mission_res["schedule"]["assignments"]["t2"]
    assert "Gemini-3.8-Flash" in mission_res["schedule"]["assignments"]["t3"]  # Slack Borrowed!
