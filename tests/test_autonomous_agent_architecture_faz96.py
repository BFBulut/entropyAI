"""
Unit tests for Faz 96 Autonomous Agent Architecture.
Validates:
1. Faz96RadixAttentionCacheManager (Hierarchical Trie KV-Cache, prefix matching, TTFT speedup, swarm sharing).
2. Faz96LateChunkingMRLProcessor (Document-wide attention pooling, Matryoshka dimension truncation, 1-Bit BQ POPCNT, Iterative Scans).
3. Faz96SwarmPBFTConsensus (Practical Byzantine Fault Tolerance, 3-phase consensus, attestation hash, Shadow Desks).
4. Faz96ContextCompressorLLMLingua (Extractive prompt compression, filler elimination, Token Budget Gatekeeper).
5. Faz96MasterAutonomousAgentSystem (Unified orchestration of Faz 96 components).
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    Faz96RadixTreeNode,
    Faz96RadixAttentionCacheManager,
    Faz96LateChunkingMRLProcessor,
    Faz96SwarmPBFTConsensus,
    Faz96ContextCompressorLLMLingua,
    Faz96MasterAutonomousAgentSystem
)


def test_faz96_radix_attention_prefix_caching():
    mgr = Faz96RadixAttentionCacheManager(max_cached_tokens=100000)

    # 1. Warm cache with a system prompt sequence
    sys_prefix = ["You", "are", "Entropy", "AI", "autonomous", "agent", "desktop", "OS"]
    insert_res = mgr.insert_sequence(sys_prefix, cache_id="system_core_v1")

    assert insert_res["cache_id"] == "system_core_v1"
    assert insert_res["sequence_length"] == 8
    assert insert_res["new_nodes_inserted"] == 8

    # 2. Query with an incoming prompt that starts with the same prefix
    incoming_tokens = ["You", "are", "Entropy", "AI", "autonomous", "agent", "desktop", "OS", "please", "refactor", "tests"]
    match_res = mgr.match_longest_prefix(incoming_tokens)

    assert match_res["is_cache_hit"] is True
    assert match_res["matched_tokens"] == 8
    assert match_res["total_tokens"] == 11
    assert match_res["cache_hit_ratio"] > 0.70
    assert match_res["last_matched_cache_id"] == "system_core_v1"
    assert match_res["ttft_speedup_x"] > 3.0

    # 3. Multi-agent swarm prefix sharing evaluation
    shared_prefix = ["GEMINI.md", "RuleDynamicModelBadges", "AGENTS.md", "RuleAgenticTDD"]
    agent_queries = [
        ["develop", "backend", "fastmcp"],
        ["develop", "frontend", "pyside6"],
        ["audit", "security", "sandboxing"],
        ["consolidate", "cognitive", "memory"]
    ]
    sharing_stats = mgr.calculate_swarm_prefix_sharing(shared_prefix, agent_queries)
    assert sharing_stats["num_agent_desks"] == 4
    assert sharing_stats["shared_prefix_tokens"] == 4
    assert sharing_stats["tokens_saved"] == 12  # 3 redundant transmissions saved
    assert sharing_stats["savings_percentage"] > 40.0


def test_faz96_late_chunking_and_matryoshka_mrl():
    processor = Faz96LateChunkingMRLProcessor()

    # 1. Simulate Late Chunking
    doc_tokens = [f"tok_{i}" for i in range(100)]
    boundaries = [(0, 30), (30, 70), (70, 100)]
    chunks = processor.simulate_late_chunking(doc_tokens, boundaries, dim=1536)

    assert len(chunks) == 3
    assert chunks[0]["dimension"] == 1536
    assert len(chunks[0]["embedding"]) == 1536
    assert chunks[1]["token_count"] == 40

    # 2. Matryoshka Representation Learning (MRL) Truncation
    full_vec = chunks[0]["embedding"]
    vec_256 = processor.matryoshka_truncate(full_vec, target_dim=256)
    vec_64 = processor.matryoshka_truncate(full_vec, target_dim=64)

    assert len(vec_256) == 256
    assert len(vec_64) == 64

    # Verify L2 norm is 1.0 (approx)
    norm_256 = sum(x * x for x in vec_256)
    assert pytest.approx(norm_256, rel=1e-3) == 1.0

    # 3. 1-Bit Binary Quantization & POPCNT Hamming
    bq_str1 = processor.binary_quantize(vec_256)
    bq_str2 = processor.binary_quantize(vec_256)  # Identical
    assert len(bq_str1) == 256
    sim_identical = processor.popcnt_hamming_similarity(bq_str1, bq_str2)
    assert sim_identical == 1.0

    # 4. Iterative Index Scan preventing Recall Cliff under metadata filtering
    records = [
        {"id": "doc_1", "embedding": chunks[0]["embedding"], "metadata": {"repo": "EntropyAI", "lang": "python"}},
        {"id": "doc_2", "embedding": chunks[1]["embedding"], "metadata": {"repo": "OtherRepo", "lang": "javascript"}},
        {"id": "doc_3", "embedding": chunks[2]["embedding"], "metadata": {"repo": "EntropyAI", "lang": "python"}}
    ]
    query_vec = chunks[0]["embedding"]
    # Filter only EntropyAI Python records
    filtered_res = processor.iterative_index_scan(
        query_vector=query_vec,
        records=records,
        filter_fn=lambda r: r.get("metadata", {}).get("repo") == "EntropyAI",
        top_k=2,
        target_dim=256
    )

    assert len(filtered_res) == 2
    assert filtered_res[0]["record_id"] == "doc_1"
    assert filtered_res[0]["score"] > 0.99
    assert filtered_res[1]["record_id"] == "doc_3"


def test_faz96_swarm_pbft_consensus_and_shadow_desks():
    nodes = ["supervisor", "dev_alpha", "dev_beta", "qa_sentinel"]
    consensus = Faz96SwarmPBFTConsensus(node_agents=nodes, fault_tolerance_f=1)

    # 1. Pre-Prepare Phase
    proposal_payload = {"change": "refactor_auth_module", "target_branch": "main"}
    prop_res = consensus.propose("supervisor", "prop_001", proposal_payload)
    assert prop_res["phase"] == "PRE_PREPARED"

    # 2. Prepare Phase (Needs 2f + 1 = 3 votes)
    v1 = consensus.prepare("dev_alpha", "prop_001", vote_valid=True)
    assert v1["quorum_reached"] is False  # 2 votes (supervisor + dev_alpha)

    v2 = consensus.prepare("qa_sentinel", "prop_001", vote_valid=True)
    assert v2["quorum_reached"] is True  # 3 votes -> PREPARED
    assert v2["phase"] == "PREPARED"

    # 3. Commit Phase
    c1 = consensus.commit("supervisor", "prop_001")
    c2 = consensus.commit("dev_alpha", "prop_001")
    c3 = consensus.commit("qa_sentinel", "prop_001")

    assert c3["is_finalized"] is True
    assert c3["status"] == "CONSENSUS_REACHED"
    prop_data = consensus.proposals["prop_001"]
    assert "attestation_hash" in prop_data
    assert len(prop_data["attestation_hash"]) == 64

    # 4. Shadow Desk Dispatch
    shadow_desk = consensus.dispatch_shadow_desk(
        primary_desk_id="desk_dev_alpha",
        shadow_desk_id="shadow_qa_alpha",
        feature_spec="OrderRouter_HighFrequency_V2"
    )
    assert shadow_desk["status"] == "ACTIVE_SHADOWING"
    assert len(shadow_desk["generated_tests"]) == 3
    assert "shadow_qa_alpha" in consensus.shadow_desks


def test_faz96_context_compressor_and_budget_gatekeeper():
    compressor = Faz96ContextCompressorLLMLingua()

    # 1. Prompt Compression
    raw_prompt = (
        "As an AI language model, please note that in order to execute the high frequency trading task, "
        "it is worth noting that we essentially need OrderRouter_V2 and FAST_EXEC_TIMEOUT=500ms. "
        "Furthermore, basically just check /api/v1/orders endpoint."
    )
    comp_res = compressor.compress_prompt(
        raw_prompt=raw_prompt,
        preserve_symbols=["OrderRouter_V2", "FAST_EXEC_TIMEOUT", "/api/v1/orders"]
    )

    assert comp_res["tokens_saved"] > 0
    assert comp_res["savings_percentage"] > 25.0
    assert "OrderRouter_V2" in comp_res["compressed_text"]
    assert "FAST_EXEC_TIMEOUT" in comp_res["compressed_text"]
    assert "as an ai language model" not in comp_res["compressed_text"].lower()

    # 2. Token Budget Gatekeeper
    # Safe condition
    gate_safe = compressor.token_budget_gatekeeper(current_tokens=50000, max_context_window=128000)
    assert gate_safe["is_safe"] is True
    assert gate_safe["recommended_action"] == "NORMAL_EXECUTION"

    # Backpressure condition (>85%)
    gate_warn = compressor.token_budget_gatekeeper(current_tokens=110000, max_context_window=128000)
    assert gate_warn["is_safe"] is False
    assert gate_warn["recommended_action"] == "APPLY_BACKPRESSURE_AND_COMPRESS"

    # Circuit breaker condition (>95%)
    gate_crit = compressor.token_budget_gatekeeper(current_tokens=125000, max_context_window=128000)
    assert gate_crit["is_safe"] is False
    assert gate_crit["recommended_action"] == "EMERGENCY_ROTATION_CIRCUIT_BREAKER"


def test_faz96_master_autonomous_agent_system_integration():
    master_sys = Faz96MasterAutonomousAgentSystem(project_name="EntropyAI_Swarm_Test")
    init_res = master_sys.initialize_faz96_environment()

    assert init_res["status"] == "INITIALIZED_FAZ96"
    assert "radix_cache_warmed" in init_res
    assert len(init_res["swarm_nodes"]) == 4
    assert len(init_res["active_shadow_desks"]) == 1

    # End-to-end flow: Radix lookup
    query_tokens = ["EntropyAI", "2026", "AutonomousAgentOS", "WindowsNative", "run_tests"]
    match = master_sys.radix_cache.match_longest_prefix(query_tokens)
    assert match["matched_tokens"] == 4
    assert match["is_cache_hit"] is True

    # Check Task DAG integration compatibility
    master_sys.dag_manager.add_task("task_0", "Init Spec", assigned_agent="supervisor_agent")
    ready = master_sys.dag_manager.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "task_0"
