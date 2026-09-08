"""
Automated Pytest Suite for Faz 108 Master Autonomous Agent Architecture
Agentic TDD Invariant: 100% Pass Rate Required.
"""

import pytest
import time
from src.entropy.tools.autonomous_agent_architecture_faz108 import (
    Faz108HarnessObservabilityEngine,
    ExecutionTrace,
    Faz108EventDrivenActorSystem,
    ActorMessage,
    MessageType,
    SupervisionPolicy,
    Faz108AgentDesksGovernor,
    DeskDomain,
    Faz108HippoRAG2Engine,
    Faz108LightRAGDualLevelEngine,
    Faz108GraphitiBiTemporalGraph,
    Faz108SupabasePgvector08Engine,
    Faz108ExtremeTokenPhysicsEconomizer,
    Faz108SEP1865InteractiveMCPAppServer,
    Faz108MasterAutonomousEngine,
)


def test_harness_compass_and_ast_preflight():
    engine = Faz108HarnessObservabilityEngine(agent_id="test_agent_108", max_consecutive_failures=3)

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
    sys = Faz108EventDrivenActorSystem(policy=SupervisionPolicy.ONE_FOR_ONE)

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


def test_agent_desks_single_writer_boundary_and_merge_gatekeeper():
    gov = Faz108AgentDesksGovernor()

    # Provision desks
    desk_dev = gov.provision_desk("desk_dev", "agent_dev", DeskDomain.DEVELOPER)
    desk_test = gov.provision_desk("desk_test", "agent_test", DeskDomain.TESTER)
    desk_arch = gov.provision_desk("desk_arch", "agent_arch", DeskDomain.ARCHITECT)

    assert desk_dev.active_branch == "feature/desk_dev"
    assert desk_test.domain == DeskDomain.TESTER

    # Single-Writer Boundary (SWB) checks
    dev_allowed = gov.check_single_writer_boundary("desk_dev", ["src/main.py", "src/core/bus.py"])
    assert dev_allowed["allowed"] is True

    dev_illegal = gov.check_single_writer_boundary("desk_dev", ["tests/test_core.py", "src/main.py"])
    assert dev_illegal["allowed"] is False
    assert "SWB_VIOLATION" in dev_illegal["reason"]
    assert "tests/test_core.py" in dev_illegal["violations"]

    test_allowed = gov.check_single_writer_boundary("desk_test", ["tests/test_unit.py"])
    assert test_allowed["allowed"] is True

    arch_allowed = gov.check_single_writer_boundary("desk_arch", ["docs/architecture.md", "specifications/api.md"])
    assert arch_allowed["allowed"] is True

    # Merge Gatekeeper checks
    # Case 1: SWB violation rejected
    res_swb_fail = gov.execute_test_gated_merge("desk_dev", 1.0, 0, {"tests/hack.py": "# hack"})
    assert res_swb_fail["merged"] is False
    assert res_swb_fail["status"] == "REJECTED_SWB_VIOLATION"

    # Case 2: Test failure rejected
    res_test_fail = gov.execute_test_gated_merge("desk_dev", 0.95, 0, {"src/main.py": "# code"})
    assert res_test_fail["merged"] is False
    assert res_test_fail["status"] == "REJECTED_TEST_FAILURE"

    # Case 3: Regressions rejected
    res_reg_fail = gov.execute_test_gated_merge("desk_dev", 1.0, 2, {"src/main.py": "# code"})
    assert res_reg_fail["merged"] is False
    assert res_reg_fail["status"] == "REJECTED_TEST_FAILURE"

    # Case 4: 100% pass, 0 regressions, SWB respected -> APPROVED
    res_ok = gov.execute_test_gated_merge("desk_dev", 1.0, 0, {"src/main.py": "# clean code"})
    assert res_ok["merged"] is True
    assert res_ok["status"] == "MERGED_TO_MAIN"
    assert len(gov.merged_history) == 1


def test_hipporag2_associative_memory():
    engine = Faz108HippoRAG2Engine()

    engine.add_passage("p1", "Harness Engineering separates Model from deterministic Harness and Task state.", ["Harness", "Model", "Task"])
    engine.add_passage("p2", "Agent Desks use Git Worktrees to isolate filesystem edits and enforce Single-Writer Boundary.", ["Agent Desks", "Git", "SWB"])
    engine.add_passage("p3", "Single-Writer Boundary ensures Developer modifies src and Tester modifies tests.", ["SWB", "Developer", "Tester"])

    ppr = engine.personalized_pagerank(["Harness"])
    assert len(ppr) > 0
    assert ppr["p1"] > 0.0

    retrieved = engine.retrieve_associative(["SWB"], top_k=2)
    assert len(retrieved) >= 2
    top_pids = [r[0] for r in retrieved]
    assert "p2" in top_pids or "p3" in top_pids


def test_lightrag_and_graphiti_bitemporal():
    # LightRAG Dual-Level
    lrag = Faz108LightRAGDualLevelEngine()
    lrag.index_document("doc_1", "FastMCP 2.0 provides stateless architecture and SEP-1865.", [("FastMCP", "supports", "SEP-1865")])
    res = lrag.dual_level_query("FastMCP", seed_entity="FastMCP")
    assert len(res["chunk_level"]) > 0
    assert len(res["graph_level"]) > 0

    # Graphiti Bi-Temporal Graph
    bg = Faz108GraphitiBiTemporalGraph()
    t0 = 1000.0
    f1 = bg.record_fact("Entropy", "model", "Claude-3.5", valid_from=t0, valid_until=2000.0)
    f2 = bg.record_fact("Entropy", "model", "Gemini-3.8", valid_from=2000.0, valid_until=None)

    # Query as of t=1500 (Historical valid)
    hist = bg.query_as_of("Entropy", 1500.0)
    assert len(hist) == 1
    assert hist[0].object_ == "Claude-3.5"

    # Query as of t=2500 (Current valid)
    curr = bg.query_as_of("Entropy", 2500.0)
    assert len(curr) == 1
    assert curr[0].object_ == "Gemini-3.8"


def test_supabase_pgvector08_iterative_scan_and_bq():
    pg = Faz108SupabasePgvector08Engine(dim=384)

    v1 = [1.0 if i % 2 == 0 else -1.0 for i in range(384)]
    v2 = [1.0 if i % 4 == 0 else -1.0 for i in range(384)]
    v3 = [-1.0] * 384

    pg.insert_vector("doc_a", v1, {"category": "architecture", "env": "prod"})
    pg.insert_vector("doc_b", v2, {"category": "architecture", "env": "dev"})
    pg.insert_vector("doc_c", v3, {"category": "finance", "env": "prod"})

    # Test BQ Hamming distance
    b1 = pg.bq_store["doc_a"]
    b2 = pg.bq_store["doc_b"]
    assert pg.hamming_distance(b1, b1) == 0
    assert pg.hamming_distance(b1, b2) > 0

    # Test Iterative Scan with filter
    hits = pg.iterative_scan_query(v1, filter_fn=lambda m: m.get("env") == "prod", limit=2)
    assert len(hits) == 2
    top_id, sim, meta = hits[0]
    assert top_id == "doc_a"
    assert sim == 1.0
    assert meta["env"] == "prod"


def test_token_physics_and_economizer():
    econ = Faz108ExtremeTokenPhysicsEconomizer()

    # 1. CodeAct 2.0 Python REPL
    code = "x = sum([1, 2, 3, 4, 5])\ny = x * 2\n"
    res_repl = econ.execute_codeact_repl(code)
    assert res_repl["success"] is True
    assert res_repl["scope"]["x"] == "15"
    assert res_repl["scope"]["y"] == "30"

    # 2. ACI Paged Viewports
    sample_text = "\n".join([f"Line {i}" for i in range(1, 101)])
    vp = econ.paginate_viewport(sample_text, start_line=10, end_line=20)
    assert vp["start_line"] == 10
    assert vp["end_line"] == 20
    assert vp["total_lines"] == 100
    assert 0.8 <= vp["tokens_saved_ratio"] <= 0.9

    # 3. RadixAttention Prefix Cache Hit
    prefix = "SYSTEM INSTRUCTION STATIC PREFIX 2026"
    c1 = econ.compute_radix_prefix_cache_hit(prefix)
    assert c1["cache_hit"] is False
    c2 = econ.compute_radix_prefix_cache_hit(prefix)
    assert c2["cache_hit"] is True
    assert c2["estimated_speedup_ratio"] > 0.8

    # 4. Late Chunking Mean-Pooling
    mock_tokens = [[float(i)] * 4 for i in range(10)]
    spans = [(0, 5), (5, 10)]
    chunk_vecs = econ.simulate_late_chunking(mock_tokens, spans)
    assert len(chunk_vecs) == 2
    assert chunk_vecs[0][0] == (0 + 1 + 2 + 3 + 4) / 5.0  # 2.0
    assert chunk_vecs[1][0] == (5 + 6 + 7 + 8 + 9) / 5.0  # 7.0

    # 5. Delta Token Accounting
    u1 = {"input": 1000, "output": 200}
    d1 = econ.compute_delta_token_accounting(u1)
    assert d1["delta_input_tokens"] == 1000
    assert d1["delta_output_tokens"] == 200

    u2 = {"input": 1500, "output": 350}
    d2 = econ.compute_delta_token_accounting(u2)
    assert d2["delta_input_tokens"] == 500
    assert d2["delta_output_tokens"] == 150
    assert d2["delta_total_tokens"] == 650


def test_sep1865_mcp_apps_and_opacity():
    server = Faz108SEP1865InteractiveMCPAppServer()
    server.register_ui_resource("ui://table/view", "Data Table", "<table><tr><td>1</td></tr></table>")

    assert "ui://table/view" in server.ui_resources
    res = server.dispatch_post_message_rpc("ui://table/view", "select_row", {"row_id": 42})
    assert res["jsonrpc"] == "2.0"
    assert res["result"]["status"] == "SUCCESS"
    assert len(server.post_message_audit_log) == 1

    # Unknown resource
    err_res = server.dispatch_post_message_rpc("ui://unknown", "ping", {})
    assert "error" in err_res


def test_master_autonomous_engine_end_to_end():
    engine = Faz108MasterAutonomousEngine(agent_id="Master-Test-108")
    audit = engine.run_comprehensive_self_audit()

    assert audit["audit_status"] == "SUCCESS_100_PERCENT"
    assert audit["preflight_passed"] is True
    assert audit["agent_card_available"] is True
    assert audit["swb_enforced"] is True
    assert audit["hipporag_ppr_active"] is True
    assert audit["bitemporal_recorded"] is True
    assert audit["pgvector_scan_hits"] > 0
    assert audit["codeact_repl_success"] is True
    assert audit["radix_cache_evaluated"] is True
    assert audit["mcp_app_rpc_status"] is True
