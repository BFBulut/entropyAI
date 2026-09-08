"""
Unit tests for Faz 83 Autonomous Agent Architecture.
Validates:
1. TreeSitterASTSkeletonizer (structural AST code skeletonization & token compression).
2. RadixAttentionKVCacheSimulator (compressed prefix trie, TTFT acceleration, KV cache hits).
3. CodeActExecutorEngine (local Python code action evaluation vs multi-turn JSON tool-calling).
4. TieredToolPruningRegistry (Tier 1 manifest vs Tier 2 dynamic schema resolution).
5. Faz83MasterAutonomousSystem end-to-end autonomous cycle with pBFT consensus and Ephemeral Desks.
"""

import pytest
from entropy.tools.autonomous_agent_architecture import (
    TreeSitterASTSkeletonizer,
    RadixAttentionKVCacheSimulator,
    CodeActExecutorEngine,
    TieredToolPruningRegistry,
    Faz83MasterAutonomousSystem
)


def test_tree_sitter_ast_skeletonizer():
    sample_code = '''
class DataProcessor:
    """Processes large streams of data."""
    def __init__(self, buffer_size: int = 1024):
        self.buffer_size = buffer_size
        self.buffer = []

    def compute_heavy_hash(self, payload: bytes) -> str:
        """Computes a SHA-256 hash across the payload."""
        import hashlib
        h = hashlib.sha256()
        h.update(payload)
        for i in range(100):
            h.update(str(i).encode('utf-8'))
        return h.hexdigest()

    async def flush_buffer(self) -> bool:
        """Flushes in-memory buffer to disk."""
        if not self.buffer:
            return False
        self.buffer.clear()
        return True
'''
    res = TreeSitterASTSkeletonizer.skeletonize_code(sample_code)
    assert res["success"] is True
    assert res["raw_tokens"] > res["skeleton_tokens"]
    assert res["compression_ratio_pct"] > 30.0
    assert "class DataProcessor:" in res["skeleton"]
    assert "def compute_heavy_hash(self, payload: bytes) -> str:" in res["skeleton"]
    assert "Computes a SHA-256 hash across the payload." in res["skeleton"]
    # Function body logic should be replaced by Ellipsis (...)
    assert "h = hashlib.sha256()" not in res["skeleton"]

    # Test syntax error handling
    invalid_code = "def broken_func(:\n   print('syntax error')"
    err_res = TreeSitterASTSkeletonizer.skeletonize_code(invalid_code)
    assert err_res["success"] is False
    assert "SyntaxError" in err_res["error"]


def test_radix_attention_kv_cache_simulator():
    sim = RadixAttentionKVCacheSimulator(base_ttft_ms=400.0)

    # Initial query with no prefix in cache
    tokens = ["System", "You", "are", "Entropy", "AI", "pair", "programmer"]
    res1 = sim.lookup_prefix(tokens)
    assert res1["matched_tokens"] == 0
    assert res1["hit_ratio_pct"] == 0.0
    assert res1["estimated_ttft_ms"] > 350.0

    # Insert prefix into Radix Trie
    new_nodes = sim.insert_token_stream("session_1", tokens)
    assert new_nodes == len(tokens)

    # Second query sharing the exact prefix + additional user tokens
    new_tokens = ["System", "You", "are", "Entropy", "AI", "pair", "programmer", "Solve", "Bug", "#42"]
    res2 = sim.lookup_prefix(new_tokens)
    assert res2["matched_tokens"] == 7
    assert res2["hit_ratio_pct"] == 70.0
    # TTFT should be significantly accelerated
    assert res2["estimated_ttft_ms"] < 200.0
    assert res2["acceleration_factor"] > 2.0


def test_codeact_executor_engine():
    stats = CodeActExecutorEngine.evaluate_codeact_vs_toolcall(
        raw_dataset_records=10000,
        filtered_records_target=10,
        record_avg_bytes=100,
        network_roundtrip_ms=800.0
    )

    assert stats["raw_dataset_records"] == 10000
    assert stats["filtered_records"] == 10
    # JSON tool-calling consumes hundreds of thousands of bytes
    assert stats["json_toolcall"]["tokens_consumed"] == 250000
    assert stats["json_toolcall"]["roundtrips"] == 3
    assert stats["json_toolcall"]["latency_ms"] == 2400.0

    # CodeAct executes in 1 roundtrip with minimal tokens
    assert stats["codeact"]["tokens_consumed"] < 1000
    assert stats["codeact"]["roundtrips"] == 1
    assert stats["codeact"]["latency_ms"] < 850.0

    assert stats["token_compression_pct"] > 99.0
    assert stats["latency_reduction_pct"] > 60.0


def test_tiered_tool_pruning_registry():
    registry = TieredToolPruningRegistry()

    # Register tools
    registry.register_tool(
        name="grep_search",
        summary="Searches files for regex patterns.",
        full_json_schema={"type": "object", "properties": {"pattern": {"type": "string"}}},
        category="search"
    )
    registry.register_tool(
        name="git_commit",
        summary="Commits staged files to git repository.",
        full_json_schema={"type": "object", "properties": {"message": {"type": "string"}}},
        category="vcs"
    )
    registry.register_tool(
        name="db_query",
        summary="Runs SQL query against local SQLite cache.",
        full_json_schema={"type": "object", "properties": {"sql": {"type": "string"}}},
        category="database"
    )

    # 1. Tier 1 manifest
    manifest = registry.generate_tier1_manifest()
    assert "| `grep_search` |" in manifest
    assert "| `git_commit` |" in manifest
    assert "| `db_query` |" in manifest

    # 2. Tier 2 resolution
    resolved = registry.resolve_tier2_schemas(["grep_search"])
    assert "grep_search" in resolved
    assert "git_commit" not in resolved
    assert resolved["grep_search"]["properties"]["pattern"]["type"] == "string"

    # 3. Pruning savings calculation
    savings = registry.calculate_pruning_savings(["grep_search"])
    assert savings["total_registered_tools"] == 3
    assert savings["selected_tools_count"] == 1
    assert savings["full_monolithic_tokens"] == 1200  # 3 * 400
    assert savings["actual_tiered_tokens"] == 475     # 3*25 + 1*400
    assert savings["savings_pct"] > 50.0


def test_faz83_master_autonomous_system_e2e():
    system = Faz83MasterAutonomousSystem(embedding_dim=1536)

    candidate_code = '''
def optimize_execution_pipeline(tasks: list) -> dict:
    """Optimizes execution pipeline with RadixAttention and AST pruning."""
    res = {}
    for t in tasks:
        res[t] = "PROCESSED"
    return res
'''
    prefix = ["System:", "Entropy", "Autonomous", "Agent", "2026", "Faz83"]
    concepts = {"Pattern:HarnessEngineering", "Role:ExecutionShell"}
    query_vec = [0.1] * 1536
    memory_vecs = [
        ("mem_1", [0.12] * 1536, {"topic": "AST Pre-flight"}),
        ("mem_2", [-0.08] * 1536, {"topic": "Irrelevant"})
    ]

    # First cycle
    res_cycle1 = system.execute_faz83_autonomous_cycle(
        cycle_id="cycle_faz83_001",
        goal="Synthesize and verify AST skeletonizer and RadixAttention pipeline",
        source_code=candidate_code,
        system_prefix_tokens=prefix,
        query_concepts=concepts,
        query_vector=query_vec,
        memory_vectors=memory_vecs,
        dataset_records_to_filter=8000,
        selected_tools=["view_file", "replace_file_content"]
    )

    assert res_cycle1["status"] == "FAZ83_OPTIMIZATION_AND_CONSENSUS_COMPLETE"
    assert res_cycle1["ast_skeletonizer"]["success"] is True
    assert res_cycle1["codeact_efficiency"]["token_compression_pct"] > 99.0
    assert res_cycle1["tool_pruning"]["savings_pct"] > 40.0
    assert res_cycle1["faz82_consensus_result"]["consensus_verdict"] == "ACCEPTED"
    assert res_cycle1["total_tokens_saved"] > 1000

    # Second cycle re-using prefix in Radix Trie
    res_cycle2 = system.execute_faz83_autonomous_cycle(
        cycle_id="cycle_faz83_002",
        goal="Second turn utilizing warmed KV prefix cache",
        source_code=candidate_code,
        system_prefix_tokens=prefix,
        query_concepts=concepts,
        query_vector=query_vec,
        memory_vectors=memory_vecs,
        dataset_records_to_filter=3000,
        selected_tools=["view_file"]
    )

    # In second cycle, prefix is 100% matched!
    assert res_cycle2["radix_attention"]["matched_tokens"] == len(prefix)
    assert res_cycle2["radix_attention"]["hit_ratio_pct"] == 100.0
    assert res_cycle2["radix_attention"]["acceleration_factor"] > 2.0
