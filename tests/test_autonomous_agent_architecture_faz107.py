"""
Automated Pytest Suite for Faz 107 Master Autonomous Agent Architecture
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import pytest
import time
from src.entropy.tools.autonomous_agent_architecture_faz107 import (
    Faz107HarnessObservabilityEngine,
    ExecutionTrace,
    Faz107EventDrivenActorSystem,
    ActorMessage,
    MessageType,
    SupervisionPolicy,
    Faz107AgentDesksGovernor,
    DeskDomain,
    Faz107HippoRAG2Engine,
    Faz107LightRAGDualLevelEngine,
    Faz107GraphitiBiTemporalGraph,
    Faz107SupabasePgvector08Engine,
    Faz107ExtremeTokenPhysicsEconomizer,
    Faz107SEP1865InteractiveMCPAppServer,
    Faz107MasterAutonomousEngine,
)


def test_harness_compass_and_ast_preflight():
    engine = Faz107HarnessObservabilityEngine(agent_id="test_agent_107", max_consecutive_failures=3)

    # 1. Traces & HarnessCompass
    engine.record_trace("task_1", 1, "TOOL", "read_file", {"path": "a.py"}, {"data": "ok"}, error=None)
    engine.record_trace("task_1", 2, "TOOL", "read_file", {"path": "b.py"}, {}, error="file_not_found")
    engine.record_trace("task_1", 3, "MODEL", None, {"prompt": "code"}, {}, error="hallucinated_variable")

    compass = engine.compute_harness_compass()
    assert compass["status"] == "COMPUTED"
    assert compass["total_traces"] == 3
    assert compass["error_count"] == 2
    assert compass["harness_faults"] == 1
    assert compass["model_faults"] == 1
    assert 0.0 < compass["fit_ratio"] < 1.0

    # 2. AST Pre-flight
    valid_code = {"src/valid.py": "def add(a: int, b: int) -> int:\n    return a + b\n"}
    res_valid = engine.validate_ast_preflight(valid_code)
    assert res_valid["preflight_passed"] is True
    assert res_valid["file_results"]["src/valid.py"]["status"] == "AST_VALID"

    syntax_err = {"src/broken.py": "def bad_func(:\n    pass\n"}
    res_err = engine.validate_ast_preflight(syntax_err)
    assert res_err["preflight_passed"] is False
    assert res_err["file_results"]["src/broken.py"]["status"] == "SYNTAX_ERROR"

    unsafe_code = {"src/unsafe.py": "def dangerous(x):\n    eval(x)\n"}
    res_unsafe = engine.validate_ast_preflight(unsafe_code)
    assert res_unsafe["preflight_passed"] is False
    assert res_unsafe["file_results"]["src/unsafe.py"]["status"] == "UNSAFE_CALL_DETECTED"

    # 3. Merkle Candidate Freezing
    m_root1 = engine.freeze_candidate_merkle("cand_1", valid_code)
    assert isinstance(m_root1, str)
    assert len(m_root1) == 64

    # 4. Rollback Sentinel (3-Strikes Rule)
    s1 = engine.evaluate_rollback_sentinel("desk_developer", test_passed=False)
    assert s1["action"] == "RETRY"
    assert s1["consecutive_failures"] == 1
    assert s1["remaining_strikes"] == 2

    s2 = engine.evaluate_rollback_sentinel("desk_developer", test_passed=False)
    assert s2["action"] == "RETRY"
    assert s2["consecutive_failures"] == 2

    s3 = engine.evaluate_rollback_sentinel("desk_developer", test_passed=False)
    assert s3["action"] == "ROLLBACK_TRIGGERED"
    assert s3["reset_target"] == "HEAD~1"

    # Reset on pass
    s_pass = engine.evaluate_rollback_sentinel("desk_developer", test_passed=True)
    assert s_pass["action"] == "CONTINUE"
    assert s_pass["consecutive_failures"] == 0


def test_event_driven_actor_system_and_erlang_supervision():
    sys = Faz107EventDrivenActorSystem(policy=SupervisionPolicy.ONE_FOR_ONE)

    # Register actors
    replies = []
    def worker_handler(msg: ActorMessage):
        replies.append(msg.payload.get("data"))
        return ActorMessage(
            msg_id="reply_1",
            sender_id="actor_worker",
            recipient_id="actor_master",
            msg_type=MessageType.RESPONSE,
            payload={"status": "DONE"},
        )

    sys.register_actor("actor_master", "master")
    sys.register_actor("actor_worker", "worker", handler=worker_handler)

    # Send message
    msg = ActorMessage(
        msg_id="m1",
        sender_id="actor_master",
        recipient_id="actor_worker",
        msg_type=MessageType.DELEGATE,
        payload={"data": "compute_task_107"},
    )
    ok = sys.send_message(msg)
    assert ok is True

    # Process worker mailbox
    out = sys.process_mailbox("actor_worker")
    assert len(out) == 1
    assert replies == ["compute_task_107"]
    assert len(sys.mailboxes["actor_master"]) == 1

    # Dead letter queue test
    ghost_msg = ActorMessage(
        msg_id="m2",
        sender_id="actor_master",
        recipient_id="non_existent_actor",
        msg_type=MessageType.QUERY,
        payload={},
    )
    sent_ghost = sys.send_message(ghost_msg)
    assert sent_ghost is False
    assert len(sys.dead_letter_queue) == 1

    # Erlang One-For-One Supervision on crash
    def crashing_handler(m: ActorMessage):
        raise RuntimeError("Fatal Actor Panic")

    sys.register_actor("actor_flaky", "flaky", handler=crashing_handler)
    crash_msg = ActorMessage(
        msg_id="m3",
        sender_id="actor_master",
        recipient_id="actor_flaky",
        msg_type=MessageType.DELEGATE,
        payload={},
    )
    sys.send_message(crash_msg)
    sys.process_mailbox("actor_flaky")
    # Flaky crashed and was auto-restarted
    assert sys.restart_counts["actor_flaky"] == 1
    assert sys.actors["actor_flaky"]["status"] == "ALIVE"


def test_agent_desks_governor_swb_and_merge_gate():
    gov = Faz107AgentDesksGovernor(project_root="c:/EntropiAI")

    # 1. Single-Writer Boundary (SWB)
    # Developer writing to src/ -> ALLOWED
    dev_src, _ = gov.check_write_permission("desk_developer", "src/entropy/core.py")
    assert dev_src is True

    # Architect writing to src/ -> DENIED
    arch_src, reason_arch = gov.check_write_permission("desk_architect", "src/entropy/core.py")
    assert arch_src is False
    assert "SWB VIOLATION" in reason_arch

    # Tester writing to tests/ -> ALLOWED
    test_ok, _ = gov.check_write_permission("desk_tester", "tests/test_core.py")
    assert test_ok is True

    # Tester writing to src/ -> DENIED
    test_src, _ = gov.check_write_permission("desk_tester", "src/entropy/core.py")
    assert test_src is False

    # Security writing audit.json -> ALLOWED
    sec_ok, _ = gov.check_write_permission("desk_security", "reports/audit.json")
    assert sec_ok is True

    # 2. Test-Gated Merge Gatekeeper
    approved = gov.evaluate_test_gated_merge(pass_rate=1.0, regressions=0, coverage=0.92)
    assert approved["merge_allowed"] is True
    assert approved["verdict"] == "MERGE_APPROVED"

    blocked = gov.evaluate_test_gated_merge(pass_rate=0.95, regressions=1, coverage=0.92)
    assert blocked["merge_allowed"] is False
    assert blocked["verdict"] == "MERGE_BLOCKED_QUALITY_GATE"


def test_hipporag2_and_lightrag():
    # HippoRAG 2
    hippo = Faz107HippoRAG2Engine(damping=0.85, max_iter=20)
    hippo.add_entity_relation("gemini", "developed_by", "google", "1", "Gemini is an AI model built by Google.")
    hippo.add_entity_relation("google", "created", "antigravity", "2", "Google created the Antigravity assistant.")
    hippo.add_entity_relation("antigravity", "uses", "harness", "3", "Antigravity relies on harness engineering.")

    top_chunks = hippo.personalized_pagerank(seed_entities=["gemini"], top_k=2)
    assert len(top_chunks) > 0
    # Top chunk should be linked to gemini/google
    top_chunk_id, score, text = top_chunks[0]
    assert score > 0.0
    assert "Gemini" in text or "Google" in text

    # LightRAG
    light = Faz107LightRAGDualLevelEngine()
    light.add_document_incremental("doc_101", "Vector search in PostgreSQL using pgvector 0.8+", ["pgvector", "database"])
    light.add_document_incremental("doc_102", "Agent Desks with Git Worktrees for multi-agent safety", ["agent_desks", "git"])

    res = light.dual_level_query(query="vector search pgvector", active_concept="database")
    assert "doc_101" in res["low_level_chunk_ids"]
    assert "doc_101" in res["high_level_cluster_chunk_ids"]
    assert res["integrated_context_count"] >= 1


def test_graphiti_bitemporal_graph():
    graphiti = Faz107GraphitiBiTemporalGraph()

    # Fact 1 at t=100
    f1 = graphiti.record_fact("database", "is", "postgresql", valid_from=100.0)
    assert f1.startswith("fact_")

    # Check active at t=150
    active_150 = graphiti.query_active_facts("database", at_time=150.0)
    assert len(active_150) == 1
    assert active_150[0]["object"] == "postgresql"

    # Invalidation at t=200: switched to sqlite
    invalidated = graphiti.invalidate_conflicting_facts("database", "is", "sqlite", effective_time=200.0)
    assert invalidated == 1
    graphiti.record_fact("database", "is", "sqlite", valid_from=200.0)

    # Check active at t=250 -> should be sqlite
    active_250 = graphiti.query_active_facts("database", at_time=250.0)
    assert len(active_250) == 1
    assert active_250[0]["object"] == "sqlite"

    # Historical query at t=150 -> should still return postgresql
    active_hist = graphiti.query_active_facts("database", at_time=150.0)
    assert len(active_hist) == 1
    assert active_hist[0]["object"] == "postgresql"


def test_supabase_pgvector08_iterative_scan_and_bq():
    engine = Faz107SupabasePgvector08Engine(dimension=64)

    # Insert sample vectors
    v1 = [1.0] * 32 + [-1.0] * 32
    v2 = [1.0] * 64
    v3 = [-1.0] * 64

    engine.insert_vector("vec_target", v1, {"env": "prod", "priority": "high"})
    engine.insert_vector("vec_other", v2, {"env": "dev", "priority": "low"})
    engine.insert_vector("vec_opp", v3, {"env": "prod", "priority": "low"})

    # Test 1-Bit BQ packing
    packed1 = engine.binary_quantize(v1)
    packed2 = engine.binary_quantize(v2)
    dist = engine.popcnt_hamming_distance(packed1, packed2)
    assert dist == 32  # 32 bit differences

    # Test Iterative Filtered Search (env == 'prod')
    results = engine.iterative_filtered_search(
        query_vector=v1,
        filter_fn=lambda m: m.get("env") == "prod",
        limit=2,
        scan_mode="strict_order",
    )
    assert len(results) == 2
    # vec_target should be top 1 with highest cosine similarity (~1.0)
    assert results[0]["doc_id"] == "vec_target"
    assert results[0]["cosine_similarity"] >= 0.99


def test_extreme_token_physics():
    economizer = Faz107ExtremeTokenPhysicsEconomizer()

    # 1. Delta Token Accounting
    t1 = economizer.compute_delta_token_accounting({"input": 1500, "output": 300})
    assert t1["delta_input"] == 1500
    assert t1["delta_output"] == 300
    assert t1["delta_total"] == 1800

    # Subsequent cumulative reading
    t2 = economizer.compute_delta_token_accounting({"input": 1900, "output": 450})
    assert t2["delta_input"] == 400
    assert t2["delta_output"] == 150
    assert t2["delta_total"] == 550

    # 2. CodeAct savings
    savings = economizer.simulate_codeact_savings(raw_file_lines=2000, matched_lines=5)
    assert savings["token_savings"] > 0
    assert savings["savings_percentage"] > 70.0

    # 3. ACI Paged Viewport
    content = "\n".join(f"line_{i}" for i in range(1, 250))
    vp = economizer.render_aci_paged_viewport(content, start_line=50, page_size=50)
    assert vp["start_line"] == 50
    assert vp["end_line"] == 99
    assert "  50 | line_50" in vp["rendered_text"]

    # 4. RadixAttention KV Cache
    hit_rate = economizer.estimate_radix_cache_hit_rate(system_prefix_length=4000, dynamic_user_length=500)
    assert hit_rate >= 0.85


def test_fastmcp_sep1865_interactive_apps():
    server = Faz107SEP1865InteractiveMCPAppServer(server_name="TestMCP")

    # UI Resource
    html = server.get_ui_resource("ui://components/prefab_data_table.html")
    assert html is not None
    assert "mcp-prefab-table" in html

    # Tool registration & Opacity
    def sample_calc(x: int, y: int) -> int:
        return x * y

    server.register_tool("sample_calc", sample_calc)
    resp = server.call_tool("sample_calc", {"x": 6, "y": 7})
    assert resp["status"] == "SUCCESS"
    assert resp["result"] == 42
    assert resp["is_opaque"] is True


def test_faz107_master_autonomous_engine():
    master = Faz107MasterAutonomousEngine(project_root="c:/EntropiAI")

    # Successful governed development mission
    code = {"src/feature.py": "def run():\n    return 'success'\n"}
    res_success = master.execute_governed_task(
        task_id="task_faz107_001",
        desk_id="desk_developer",
        modified_files=code,
        test_pass_rate=1.0,
        regressions=0,
    )
    assert res_success["success"] is True
    assert res_success["merkle_root"] is not None
    assert res_success["merge_evaluation"]["merge_allowed"] is True
    assert res_success["rollback_decision"]["action"] == "CONTINUE"

    # Blocked due to Single-Writer Boundary violation
    res_swb_blocked = master.execute_governed_task(
        task_id="task_faz107_002",
        desk_id="desk_architect",  # Architect attempting to modify src/
        modified_files=code,
        test_pass_rate=1.0,
        regressions=0,
    )
    assert res_swb_blocked["success"] is False
    assert res_swb_blocked["stage"] == "SWB_CHECK"
    assert "SWB VIOLATION" in res_swb_blocked["error"]
