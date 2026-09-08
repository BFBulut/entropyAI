"""
Automated Pytest Suite for Faz 109 Master Autonomous Agent Architecture
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import pytest
import time
from src.entropy.tools.autonomous_agent_architecture_faz109 import (
    Faz109HarnessObservabilityEngine,
    ExecutionTrace,
    FaultCategory,
    Faz109EventDrivenActorSystem,
    ActorMessage,
    MessageType,
    SupervisionPolicy,
    Faz109AgentDesksGovernor,
    DeskDomain,
    Faz109HippoRAG2Engine,
    Faz109LightRAGDualLevelEngine,
    Faz109GraphitiBiTemporalGraph,
    Faz109SupabasePgvector08Engine,
    Faz109ExtremeTokenPhysicsEconomizer,
    Faz109SEP1865InteractiveMCPAppServer,
    Faz109MasterAutonomousEngine,
)


def test_harness_compass_and_ast_preflight():
    engine = Faz109HarnessObservabilityEngine(agent_id="test_agent_109", max_consecutive_failures=3)

    # 1. Traces & HarnessCompass
    engine.record_trace("task_1", 1, "TOOL", "read_file", {"path": "a.py"}, {"data": "ok"}, error=None)
    engine.record_trace("task_1", 2, "TOOL", "read_file", {"path": "b.py"}, {}, error="file_not_found", fault_category=FaultCategory.SCHEMA_MISMATCH)
    engine.record_trace("task_1", 3, "MODEL", None, {"prompt": "code"}, {}, error="hallucinated_variable", fault_category=FaultCategory.HALLUCINATION)

    compass = engine.compute_harness_compass()
    assert compass["status"] == "COMPUTED"
    assert compass["total_traces"] == 3
    assert compass["error_count"] == 2
    assert compass["harness_faults"] == 1
    assert compass["model_faults"] == 1
    assert 0.0 < compass["fit_ratio"] < 1.0
    assert len(compass["recommendations"]) > 0

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
    sys = Faz109EventDrivenActorSystem(policy=SupervisionPolicy.ONE_FOR_ONE)

    # Register actors with A2A card
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
    sys.register_actor("actor_worker", "worker", handler=worker_handler, skills=["data_analysis"])

    card = sys.get_agent_card("actor_worker")
    assert card is not None
    assert card.agent_id == "actor_worker"
    assert "data_analysis" in card.skills

    # Send message
    msg = ActorMessage(
        msg_id="msg_1",
        sender_id="actor_master",
        recipient_id="actor_worker",
        msg_type=MessageType.TASK_DISPATCH,
        payload={"data": "compute_matrix"},
    )
    sent = sys.send_message(msg)
    assert sent is True

    # Process mailbox
    responses = sys.process_mailbox("actor_worker")
    assert len(responses) == 1
    assert "compute_matrix" in replies
    assert sys.actor_health["actor_worker"] == "HEALTHY"

    # Crash & supervision check
    def crashing_handler(msg: ActorMessage):
        raise RuntimeError("Actor unhandled error")

    sys.register_actor("actor_crasher", "worker", handler=crashing_handler)
    crash_msg = ActorMessage(
        msg_id="crash_1",
        sender_id="actor_master",
        recipient_id="actor_crasher",
        msg_type=MessageType.TASK_DISPATCH,
        payload={},
    )
    sys.send_message(crash_msg)
    sys.process_mailbox("actor_crasher")
    assert sys.actor_health["actor_crasher"] == "RESTARTED"


def test_saga_transaction_coordinator():
    sys = Faz109EventDrivenActorSystem()
    state = {"balance": 100, "item_reserved": False}

    def step1_fwd(p):
        state["item_reserved"] = True
        return True

    def step1_comp(p):
        state["item_reserved"] = False

    def step2_fwd_fail(p):
        return False  # Simulate payment failure

    def step2_comp(p):
        pass

    saga = sys.coordinate_saga_transaction([
        ("reserve_item", {}, step1_fwd, step1_comp),
        ("charge_payment", {}, step2_fwd_fail, step2_comp),
    ])

    assert saga["saga_status"] == "FAILED_ROLLED_BACK"
    assert saga["failed_step"] == "charge_payment"
    assert "reserve_item" in saga["compensated_steps"]
    assert state["item_reserved"] is False  # Verified rollback!


def test_agent_desks_single_writer_boundary_and_merge_gatekeeper():
    gov = Faz109AgentDesksGovernor()

    # Provision desks
    desk_dev = gov.provision_desk("desk_dev", "agent_dev", DeskDomain.DEVELOPER)
    desk_test = gov.provision_desk("desk_test", "agent_test", DeskDomain.TESTER)
    desk_arch = gov.provision_desk("desk_arch", "agent_arch", DeskDomain.ARCHITECT)

    assert desk_dev.active_branch == "feature/desk_dev"
    assert desk_test.domain == DeskDomain.TESTER

    # Single-Writer Boundary (SWB) Checks
    res_ok = gov.check_single_writer_boundary("desk_dev", ["src/core.py", "src/models/user.py"])
    assert res_ok["allowed"] is True

    res_violation = gov.check_single_writer_boundary("desk_dev", ["src/core.py", "tests/test_core.py"])
    assert res_violation["allowed"] is False
    assert res_violation["reason"] == "SWB_VIOLATION"
    assert "tests/test_core.py" in res_violation["violating_files"]

    # Test-Gated Merge Gatekeeper
    # 1. 100% pass + 0 regressions + SWB ok -> Approved
    res_merge = gov.evaluate_test_gated_merge(
        desk_id="desk_dev",
        test_pass_rate=1.0,
        regressions_count=0,
        target_files=["src/core.py"],
        ast_preflight_passed=True,
    )
    assert res_merge["merge_approved"] is True
    assert res_merge["status"] == "READY_FOR_FAST_FORWARD_MERGE"

    # 2. Failing tests (< 100%) -> Rejected
    res_fail_tests = gov.evaluate_test_gated_merge(
        desk_id="desk_dev",
        test_pass_rate=0.95,
        regressions_count=0,
        target_files=["src/core.py"],
    )
    assert res_fail_tests["merge_approved"] is False

    # 3. Regressions > 0 -> Rejected
    res_regress = gov.evaluate_test_gated_merge(
        desk_id="desk_dev",
        test_pass_rate=1.0,
        regressions_count=1,
        target_files=["src/core.py"],
    )
    assert res_regress["merge_approved"] is False


def test_hipporag2_bipartite_ppr():
    engine = Faz109HippoRAG2Engine(damping=0.85, max_iter=20)

    engine.add_passage("doc_harness", "Harness engineering wraps LLM into deterministic OS.", ["Harness", "LLM", "OS"])
    engine.add_passage("doc_memory", "HippoRAG combines graph and personalized pagerank.", ["HippoRAG", "Graph", "PageRank"])
    engine.add_passage("doc_bridge", "Harness connects HippoRAG memory to LLM.", ["Harness", "HippoRAG", "LLM"])

    # Query with seed entity
    scores = engine.personalized_pagerank(["Harness"])
    assert len(scores) == 3
    # doc_harness and doc_bridge both link to "Harness"
    assert scores["doc_harness"] > 0
    assert scores["doc_bridge"] > 0
    assert list(scores.keys())[0] in ("doc_harness", "doc_bridge")


def test_lightrag_dual_level_retrieval():
    engine = Faz109LightRAGDualLevelEngine()

    engine.insert_incremental_facts(
        entity="RadixAttention",
        facts=["Tree-structured KV cache sharing", "Avoids redundant GPU prefill"],
        theme="Inference Acceleration and Token Minimization",
    )
    engine.add_relation("RadixAttention", "implements", "PrefixCaching")

    res = engine.dual_level_query("RadixAttention")
    assert res["entity"] == "RadixAttention"
    assert len(res["low_level_facts"]) == 2
    assert "Inference Acceleration" in res["high_level_theme"]
    assert len(res["graph_relations"]) == 1


def test_graphiti_bitemporal_graph_and_invalidation():
    kg = Faz109GraphitiBiTemporalGraph()

    # Fact 1: valid from t=100
    f1 = kg.record_fact("ModelA", "state", "EXPERIMENTAL", valid_from=100.0)
    assert f1.valid_until == pytest.approx(float("inf"))

    # Fact 2: supersedes at t=200
    f2 = kg.record_fact("ModelA", "state", "PRODUCTION", valid_from=200.0)
    assert f1.valid_until == 200.0  # Automated invalidation verified
    assert f2.valid_until == pytest.approx(float("inf"))

    # Query as of t=150 (Time-travel)
    res_150 = kg.query_as_of("ModelA", 150.0)
    assert len(res_150) == 1
    assert res_150[0].object_ == "EXPERIMENTAL"

    # Query as of t=250 (Current state)
    res_250 = kg.query_as_of("ModelA", 250.0)
    assert len(res_250) == 1
    assert res_250[0].object_ == "PRODUCTION"


def test_supabase_pgvector08_iterative_scan_and_popcnt_bq():
    engine = Faz109SupabasePgvector08Engine(dim=384)

    vec_a = [0.5] * 384
    vec_b = [-0.5] * 384
    vec_c = [0.4] * 384

    engine.insert_vector("doc_a", vec_a, {"namespace": "finance", "status": "approved"})
    engine.insert_vector("doc_b", vec_b, {"namespace": "finance", "status": "pending"})
    engine.insert_vector("doc_c", vec_c, {"namespace": "general", "status": "approved"})

    # Iterative scan query with metadata filter (status == 'approved')
    hits = engine.iterative_scan_query(
        query_vec=vec_a,
        filter_predicate=lambda m: m.get("status") == "approved",
        limit=2,
    )
    assert len(hits) == 2
    doc_ids = [h[0] for h in hits]
    assert "doc_a" in doc_ids
    assert "doc_c" in doc_ids
    assert "doc_b" not in doc_ids  # Filtered out


def test_extreme_token_physics_and_aci_viewports():
    economizer = Faz109ExtremeTokenPhysicsEconomizer()

    # 1. CodeAct REPL execution
    code = "data = [x * 2 for x in range(5)]\ntotal = sum(data)\n"
    repl_res = economizer.execute_codeact_repl(code, {})
    assert repl_res["success"] is True
    assert repl_res["result"]["total"] == 20

    # 2. ACI Paged Viewports
    sample_lines = [f"line {i}\n" for i in range(250)]
    chunks = economizer.chunk_file_aci_viewports(sample_lines, window_size=100)
    assert len(chunks) == 3
    assert chunks[0][0] == 1 and chunks[0][1] == 100
    assert chunks[1][0] == 101 and chunks[1][1] == 200
    assert chunks[2][0] == 201 and chunks[2][1] == 250

    # 3. RadixAttention Prefix Caching
    r1 = economizer.compute_radix_prefix_cache_hit("STATIC_SYSTEM_PROMPT_PREFIX")
    assert r1["cache_hit"] is False
    r2 = economizer.compute_radix_prefix_cache_hit("STATIC_SYSTEM_PROMPT_PREFIX")
    assert r2["cache_hit"] is True
    assert r2["estimated_ttft_reduction_pct"] == 85.0

    # 4. Late Chunking Mean Pooling
    doc_tokens = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]
    pooled = economizer.late_chunking_mean_pooling(doc_tokens, [(0, 2), (2, 4)])
    assert len(pooled) == 2
    assert pooled[0] == [2.0, 3.0]  # mean of [1,2] and [3,4]
    assert pooled[1] == [6.0, 7.0]  # mean of [5,6] and [7,8]

    # 5. Delta Token Accounting
    d1 = economizer.compute_delta_token_accounting({"input": 1000, "output": 200})
    assert d1["delta_input_tokens"] == 1000
    assert d1["delta_output_tokens"] == 200

    d2 = economizer.compute_delta_token_accounting({"input": 1250, "output": 280})
    assert d2["delta_input_tokens"] == 250
    assert d2["delta_output_tokens"] == 80


def test_sep1865_interactive_mcp_app_server():
    server = Faz109SEP1865InteractiveMCPAppServer()

    # Register ui:// resource
    server.register_ui_resource(
        uri="ui://agent/dashboard",
        title="Agent Live Dashboard",
        html="<div id='agent-root'>Dashboard Content</div>",
    )

    # Dispatch RPC over postMessage
    res = server.dispatch_post_message_rpc(
        origin_uri="ui://agent/dashboard",
        method="fetch_telemetry",
        params={"range": "1h"},
    )
    assert res["jsonrpc"] == "2.0"
    assert res["result"]["status"] == "SUCCESS"
    assert len(server.post_message_audit_log) == 1

    # Unknown URI
    err_res = server.dispatch_post_message_rpc(
        origin_uri="ui://unknown",
        method="test",
        params={},
    )
    assert "error" in err_res


def test_master_autonomous_engine_end_to_end():
    engine = Faz109MasterAutonomousEngine(agent_id="EntropyAI-Test-Faz109")
    audit = engine.run_comprehensive_self_audit()

    assert audit["audit_status"] == "SUCCESS_100_PERCENT"
    assert audit["preflight_passed"] is True
    assert audit["agent_card_available"] is True
    assert audit["swb_enforced"] is True
    assert audit["hipporag_ppr_active"] is True
    assert audit["bitemporal_recorded"] is True
    assert audit["pgvector_scan_hits"] == 1
    assert audit["codeact_repl_success"] is True
    assert audit["radix_cache_evaluated"] is True
    assert audit["mcp_app_rpc_status"] is True
    assert audit["saga_committed"] is True
