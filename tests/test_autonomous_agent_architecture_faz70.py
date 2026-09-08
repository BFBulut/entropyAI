"""
Tests for Entropy AI - Autonomous Agent Architecture Core Engine (Faz 70)
Validates:
1. MultiAgentBlackboardBus (Actor Mailbox + Blackboard State + Topic Broadcast + Priority Queues).
2. AnchoredIterativeCompactionEngine (Prefix cache preservation, intermediate log compaction, token reduction).
3. HierarchicalGraphCommunityDetector (Knowledge graph entity clustering, modularity, community summaries).
4. DiskANNStreamingSimulator (Supabase pgvectorscale vector quantization footprints: FP32, FP16 halfvec, SQ8, BQ).
5. Integration with SpecDrivenDAGScheduler and HippoRAG2.
"""

from pathlib import Path
import pytest

from entropy.tools.autonomous_agent_architecture import (
    MultiAgentBlackboardBus,
    BlackboardMessage,
    AnchoredIterativeCompactionEngine,
    HierarchicalGraphCommunityDetector,
    DiskANNStreamingSimulator,
    SpecDrivenDAGScheduler,
    HippoRAG2NeurobiologicalEngine,
    TokenPhysicsCalculator,
)


def test_blackboard_bus_direct_message():
    bus = MultiAgentBlackboardBus()
    bus.register_agent("agent-orchestrator")
    bus.register_agent("agent-coder")

    msg = BlackboardMessage(
        msg_id="msg-001",
        sender_id="agent-orchestrator",
        recipient_id="agent-coder",
        topic="code/tasks",
        artifact_type="task_spec",
        payload={"task_id": "auth-jwt", "file": "src/auth.py"},
        priority=3
    )

    delivered_count = bus.send_message(msg)
    assert delivered_count == 1

    # Orchestrator mailbox should be empty
    assert len(bus.fetch_mailbox("agent-orchestrator")) == 0

    # Coder mailbox should contain the message
    coder_inbox = bus.fetch_mailbox("agent-coder")
    assert len(coder_inbox) == 1
    assert coder_inbox[0].msg_id == "msg-001"
    assert coder_inbox[0].payload["task_id"] == "auth-jwt"

    # Subsequent fetch should be empty (drained)
    assert len(bus.fetch_mailbox("agent-coder")) == 0


def test_blackboard_bus_topic_broadcast_and_priority():
    bus = MultiAgentBlackboardBus()
    bus.register_agent("lead-architect", topics=["spec/updates"])
    bus.register_agent("backend-agent", topics=["spec/updates", "backend/alerts"])
    bus.register_agent("qa-agent", topics=["spec/updates"])

    # Lead architect broadcasts to topic 'spec/updates'
    msg_low = BlackboardMessage(
        msg_id="msg-low",
        sender_id="lead-architect",
        recipient_id="ALL",
        topic="spec/updates",
        artifact_type="notice",
        payload={"text": "FYI spec format updated"},
        priority=1
    )
    msg_high = BlackboardMessage(
        msg_id="msg-high",
        sender_id="lead-architect",
        recipient_id="ALL",
        topic="spec/updates",
        artifact_type="breaking_change",
        payload={"text": "CRITICAL: Spec revision 2.0"},
        priority=5
    )

    bus.send_message(msg_low)
    bus.send_message(msg_high)

    # Lead architect should not receive own message
    assert len(bus.fetch_mailbox("lead-architect")) == 0

    # Backend agent should have received both, with high priority first
    backend_msgs = bus.fetch_mailbox("backend-agent")
    assert len(backend_msgs) == 2
    assert backend_msgs[0].msg_id == "msg-high"
    assert backend_msgs[0].priority == 5
    assert backend_msgs[1].msg_id == "msg-low"

    # QA agent also received both
    qa_msgs = bus.fetch_mailbox("qa-agent")
    assert len(qa_msgs) == 2


def test_blackboard_state_publish():
    bus = MultiAgentBlackboardBus()
    bus.publish_to_blackboard("system_state", {"phase": "testing", "coverage": 100}, updated_by="qa-agent")

    assert "system_state" in bus.blackboard_state
    assert bus.blackboard_state["system_state"]["value"]["coverage"] == 100
    assert bus.blackboard_state["system_state"]["updated_by"] == "qa-agent"
    assert len(bus.audit_log) >= 1


def test_anchored_iterative_compaction_short_history():
    sys_prompt = "You are an autonomous engineering agent."
    tools = "tool1: read_file\ntool2: write_file"
    history = [
        {"role": "user", "content": "Hello agent"},
        {"role": "assistant", "content": "Hello! How can I assist?"}
    ]

    res = AnchoredIterativeCompactionEngine.compact_context(
        system_prompt=sys_prompt,
        tool_definitions=tools,
        turn_history=history,
        keep_recent_turns=3
    )

    assert res["compaction_performed"] is False
    assert res["prefix_cache_intact"] is True
    assert res["saved_tokens"] == 0
    assert len(res["compacted_history"]) == 2


def test_anchored_iterative_compaction_long_history():
    sys_prompt = "You are an autonomous agent with high reasoning capabilities."
    tools = "tools: git_worktree, ast_verifier, bash_exec, prm_eval"

    # Generate 10 turns with extensive intermediate chat
    history = []
    for i in range(10):
        history.append({"role": "user", "content": f"Turn {i}: Run comprehensive database migration step {i} with extensive sql queries." * 5})
        history.append({"role": "assistant", "content": f"Turn {i}: Executed step {i} successfully. Verified table schema and constraints." * 5})

    res = AnchoredIterativeCompactionEngine.compact_context(
        system_prompt=sys_prompt,
        tool_definitions=tools,
        turn_history=history,
        keep_recent_turns=4,
        pruning_ratio=0.70
    )

    assert res["compaction_performed"] is True
    assert res["prefix_cache_intact"] is True
    assert res["saved_tokens"] > 0
    assert res["savings_percent"] > 20.0
    assert res["total_tokens_after"] < res["total_tokens_before"]

    # Recent turns must be fully preserved
    assert len(res["compacted_history"]) == len(history)
    for recent_turn in res["compacted_history"][-4:]:
        assert "[COMPACTED]" not in recent_turn["content"]

    # Intermediate turns should be marked as compacted
    assert "[COMPACTED]" in res["compacted_history"][0]["content"]


def test_hierarchical_graph_community_detector():
    detector = HierarchicalGraphCommunityDetector()

    # Community 0: Core Agent Loop
    detector.add_edge("AgentHarness", "ExecutionLoop")
    detector.add_edge("ExecutionLoop", "ToolRegistry")
    detector.add_edge("ToolRegistry", "ContextManager")

    # Community 1: Memory & RAG
    detector.add_edge("HippoRAG2", "PersonalizedPageRank")
    detector.add_edge("PersonalizedPageRank", "SupabasePgvector")
    detector.add_edge("SupabasePgvector", "DiskANN")

    comm_map = detector.detect_communities()
    assert "agentharness" in comm_map
    assert "hipporag2" in comm_map

    # Components should be partitioned into distinct clusters
    assert comm_map["agentharness"] == comm_map["executionloop"]
    assert comm_map["hipporag2"] == comm_map["personalizedpagerank"]
    assert comm_map["agentharness"] != comm_map["hipporag2"]

    summaries = detector.summarize_communities(comm_map)
    assert len(summaries) == 2
    assert len(summaries[comm_map["agentharness"]]) == 4
    assert len(summaries[comm_map["hipporag2"]]) == 4


def test_diskann_streaming_quantization_simulator():
    # 1 million vectors, 1536 dims (e.g. OpenAI / Gemini text-embedding-004)
    stats = DiskANNStreamingSimulator.calculate_storage_footprint(vector_count=1_000_000, dimension=1536)

    assert stats["vector_count"] == 1_000_000
    assert stats["dimension"] == 1536
    # FP32: 1M * 1536 * 4 bytes = 6,144,000,000 bytes ≈ 5859.38 MB
    assert stats["fp32_mb"] > 5800.0
    # FP16: half of FP32 ≈ 2929.69 MB
    assert abs(stats["fp16_halfvec_mb"] - stats["fp32_mb"] / 2.0) < 0.1
    # SQ8: quarter of FP32 ≈ 1464.84 MB
    assert abs(stats["sq8_quantized_mb"] - stats["fp32_mb"] / 4.0) < 0.1
    # BQ: 1/32 of FP32 ≈ 183.11 MB
    assert stats["bq_binary_mb"] < 200.0
    assert stats["bq_reduction_pct"] == 96.88


def test_integrated_dag_and_hipporag_workflow():
    # Verify harmonious interaction between DAG scheduler and HippoRAG 2
    dag = SpecDrivenDAGScheduler()
    dag.add_task("task-1", "Design Spec", dependencies=[])
    dag.add_task("task-2", "Implement Core", dependencies=["task-1"])
    dag.add_task("task-3", "Automated Tests", dependencies=["task-2"])

    topological = dag.get_topological_order()
    assert topological == ["task-1", "task-2", "task-3"]

    hippo = HippoRAG2NeurobiologicalEngine()
    hippo.add_triples([
        ("Task1", "generates", "SpecDocument"),
        ("SpecDocument", "guides", "CoreModule"),
        ("CoreModule", "validated_by", "AutomatedTests")
    ])

    query_res = hippo.multi_hop_query(["Task1"], top_k=3)
    assert len(query_res["top_associations"]) >= 1
    top_entity = query_res["top_associations"][0]["node"]
    assert top_entity in ["task1", "specdocument", "coremodule", "automatedtests"]
