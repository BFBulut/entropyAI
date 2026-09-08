"""Automated test suite for Entropy AI Cognitive Memory & Obsidian RAG."""

import time
import pytest
from pathlib import Path

from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
from entropy.memory.rag.project_indexer import ProjectIndexer

@pytest.fixture
def temp_vault(tmp_path):
    vault = tmp_path / "TestVault"
    return ObsidianVaultManager(vault_path=vault)

@pytest.fixture
def temp_cognitive_db(tmp_path):
    db_file = tmp_path / "test_cognitive.db"
    return CognitiveMemorySystem(db_path=db_file)

def test_obsidian_vault_initialization(temp_vault):
    assert temp_vault.entropy_dir.exists()
    assert temp_vault.daily_notes_dir.exists()
    assert temp_vault.reports_dir.exists()
    assert temp_vault.memory_file.exists()

    content = temp_vault.read_global_memory()
    assert "Entropy AI" in content
    assert "System Beliefs" in content

def test_obsidian_daily_and_reports(temp_vault):
    log_file = temp_vault.append_daily_log("Executed test suite successfully.")
    assert log_file.exists()
    assert "Executed test suite successfully." in log_file.read_text(encoding="utf-8")

    report_file = temp_vault.save_research_report(
        title="Agentic OS Architecture",
        content="Deep dive into [[Obsidian]] and [[Supabase]] vector memory.",
        tags=["ai", "architecture"]
    )
    assert report_file.exists()
    reports = temp_vault.list_reports()
    assert len(reports) == 1
    assert "Agentic OS Architecture" in reports[0]["title"]

    graph = temp_vault.build_knowledge_graph()
    assert len(graph["nodes"]) > 0
    # Wikilink to Obsidian or Supabase should be captured
    targets = [link["target"] for link in graph["links"]]
    assert any("Obsidian" in t or "Supabase" in t for t in targets)

def test_cognitive_memory_ego_and_surprise_filter(temp_cognitive_db):
    # Check Layer 12 Ego Node
    ego = temp_cognitive_db.get_node("ego-entropy-core")
    assert ego is not None
    assert ego.importance == 1.0
    assert ego.category == "ego"

    # Layer 2 Surprise / Novelty Filter: First insert
    node1, is_new1 = temp_cognitive_db.record_memory("episodic", "Refactored UI terminal pane", importance=0.7)
    assert is_new1 is True
    assert node1.access_count == 1

    # Insert duplicate memory -> should NOT be considered novel
    node2, is_new2 = temp_cognitive_db.record_memory("episodic", "Refactored UI terminal pane", importance=0.8)
    assert is_new2 is False
    assert node2.id == node1.id
    assert node2.access_count == 2
    assert node2.importance == 0.8

def test_cognitive_memory_ebbinghaus_decay(temp_cognitive_db):
    node, _ = temp_cognitive_db.record_memory("semantic", "Important rule: always use pytest", importance=0.9)
    now = time.time()

    # Initial strength
    s0 = node.calculate_ebbinghaus_strength(current_time=now)
    assert pytest.approx(s0, 0.01) == 0.9

    # 10 days later without access
    s_10days = node.calculate_ebbinghaus_strength(current_time=now + (10 * 86400.0))
    assert s_10days < s0

def test_cognitive_hybrid_recall(temp_cognitive_db):
    temp_cognitive_db.record_memory("semantic", "User prefers dark mode and neon cyan accents", importance=0.9)
    temp_cognitive_db.record_memory("episodic", "Compiled C++ bindings yesterday", importance=0.3)

    results = temp_cognitive_db.hybrid_recall("neon cyan accents", top_k=2)
    assert len(results) > 0
    top_node, score = results[0]
    assert "neon cyan" in top_node.content.lower()

def test_project_indexer(tmp_path):
    # Setup dummy project files
    (tmp_path / "main.py").write_text("def run_entropy_core():\n    return 'Active'", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def helper():\n    pass", encoding="utf-8")

    indexer = ProjectIndexer(root_dir=tmp_path)
    count = indexer.scan_and_index()
    assert count >= 2

    results = indexer.search_codebase("run_entropy_core")
    assert len(results) > 0
    assert results[0]["path"] == "main.py"

def test_wikilink_pipe_alias_and_extraction(temp_vault):
    # T1.1: Wikilink pipe [[Target|Alias]] and header parsing
    sample_text = (
        "Check out [[CognitiveArchitecture|Bilişsel Mimari]] and [[MEMORY#Directives|Temel Direktifler]]. "
        "Also see plain [[Research_Report.md]]."
    )
    links = temp_vault.extract_wikilinks(sample_text)
    assert len(links) == 3
    assert links[0]["target"] == "CognitiveArchitecture"
    assert links[0]["alias"] == "Bilişsel Mimari"
    assert links[1]["target"] == "MEMORY"
    assert links[1]["alias"] == "Temel Direktifler"
    assert links[2]["target"] == "Research_Report"
    assert links[2]["alias"] == "Research_Report"

def test_bidirectional_backlinks_and_moc_sync(temp_vault):
    # T1.2 & T1.3: Inbound/Outbound Backlinks and BELLEK_HARITASI.md MOC
    # Note A links to Note B
    temp_vault.save_research_report("Note_A", "Reference to [[Note_B|Hedef B Notu]] and [[MEMORY]].")
    temp_vault.save_research_report("Note_B", "Content in Note B without outbound links.")

    backlinks = temp_vault.get_backlinks_index()
    assert "Note_B" in backlinks["outbound"]["Note_A"]
    assert "Note_A" in backlinks["inbound"]["Note_B"]
    assert "Hedef B Notu" in backlinks["aliases"].get("Note_B", [])

    # Test MOC generation
    moc_path = temp_vault.sync_map_of_content()
    assert moc_path.exists()
    moc_content = moc_path.read_text(encoding="utf-8")
    assert "Master Bellek Haritası" in moc_content
    assert "Note_A" in moc_content
    assert "Note_B" in moc_content

def test_local_embedding_engine_and_cosine_sim():
    # T2.1: Local zero-API embedding vector generation
    from entropy.memory.supabase.cognitive_memory import LocalEmbeddingEngine, cosine_similarity

    engine = LocalEmbeddingEngine.get_instance()
    v1 = engine.embed_text("Entropy AI autonomous operating system")
    v2 = engine.embed_text("Autonomous AI agent on Windows")
    v3 = engine.embed_text("Cooking recipes for Italian pasta")

    assert len(v1) == 384
    assert len(v2) == 384
    assert len(v3) == 384

    sim_1_2 = cosine_similarity(v1, v2)
    sim_1_3 = cosine_similarity(v1, v3)

    # AI system should be semantically closer to autonomous agent than Italian pasta
    assert sim_1_2 > sim_1_3

def test_multi_criteria_hybrid_scoring_and_noise_pruning(temp_cognitive_db):
    # T2.2 & T2.3: Multi-criteria recall and noise pruning threshold
    temp_cognitive_db.record_memory(
        category="semantic",
        content="Antigravity CLI provides headless zero API key execution",
        importance=0.95
    )
    temp_cognitive_db.record_memory(
        category="episodic",
        content="Random unrelated noise log 12345",
        importance=0.01
    )

    # High relevance query
    matches = temp_cognitive_db.hybrid_recall("Antigravity CLI headless execution", top_k=5, min_threshold=0.15)
    assert len(matches) >= 1
    top_node, score = matches[0]
    assert "Antigravity" in top_node.content
    assert score > 0.30

    # Ensure completely unrelated noise with low importance is pruned by threshold
    noise_matches = temp_cognitive_db.hybrid_recall("Completely unrelated query xyz 999", top_k=5, min_threshold=0.35)
    noise_ids = [node.id for node, s in noise_matches]
    assert not any("12345" in node.content for node, s in noise_matches)

def test_dream_consolidation_and_pruning(temp_cognitive_db):
    # T3.1 & T3.2: Dreaming consolidation
    temp_cognitive_db.record_memory("episodic", "Session log 1: Discussed vector embeddings", importance=0.4)
    temp_cognitive_db.record_memory("episodic", "Session log 2: Discussed Obsidian wikilinks", importance=0.4)

    rules = temp_cognitive_db.dream_and_consolidate()
    assert len(rules) >= 1
    # Özet, etiket değil gerçek anı içeriği taşımalı: önceki sürüm yalnızca
    # "N bölümsel etkileşimden damıtıldı" yazıyor ve recall'ı kirletiyordu.
    assert "vector embeddings" in rules[0] and "Obsidian wikilinks" in rules[0]
    assert "etkileşimden damıtıldı" not in rules[0]

    # Verify a new semantic memory was created and is retrievable by its content
    semantic_nodes = temp_cognitive_db.recall("vector embeddings Obsidian wikilinks")
    assert any("Günlük bilişsel özet" in n["content"] for n in semantic_nodes)

    # T3.3: Pruning test - create an old, low-importance decayed memory
    old_time = time.time() - (35 * 86400.0) # 35 days ago
    temp_cognitive_db.record_memory("episodic", "Ancient noise log to be pruned", importance=0.05)
    # Manually backdate created_at and last_accessed
    node_id = temp_cognitive_db._generate_node_id("episodic", "Ancient noise log to be pruned")
    import sqlite3
    with sqlite3.connect(temp_cognitive_db.db_path) as conn:
        conn.execute("UPDATE cognitive_nodes SET last_accessed = ?, created_at = ? WHERE id = ?", (old_time, old_time, node_id))
        conn.commit()

    pruned = temp_cognitive_db.prune_decayed_memories(min_strength=0.10, days_dormant=30.0)
    assert pruned >= 1
    assert temp_cognitive_db.get_node(node_id) is None

def test_syntax_aware_ast_and_incremental_indexing(tmp_path):
    # T4.1 & T4.2: AST chunking and incremental caching
    py_code = (
        "class EntropyCore:\n"
        "    \"\"\"Main OS Core Controller.\"\"\"\n"
        "    def run(self):\n"
        "        return True\n\n"
        "def launch_terminal(mode: str):\n"
        "    \"\"\"Launch terminal in given mode.\"\"\"\n"
        "    print(mode)\n"
    )
    code_file = tmp_path / "engine.py"
    code_file.write_text(py_code, encoding="utf-8")

    indexer = ProjectIndexer(root_dir=tmp_path)
    count1 = indexer.scan_and_index()
    assert count1 >= 1

    # Verify AST extracted discrete symbols
    symbols = [c["symbol"] for c in indexer.chunks]
    assert any("class EntropyCore" in s for s in symbols)
    assert any("def launch_terminal" in s for s in symbols)

    # Verify search returns exact symbol and line numbers
    results = indexer.search_codebase("launch_terminal")
    assert len(results) >= 1
    assert "def launch_terminal" in results[0]["symbol"]
    assert "L" in results[0]["lines"]

    # T4.2: Incremental indexing - second scan should reuse cache
    mtime_before = indexer._file_cache["engine.py"]["mtime"]
    count2 = indexer.scan_and_index()
    assert count2 == count1
    assert indexer._file_cache["engine.py"]["mtime"] == mtime_before

def test_migrate_and_clean_database(temp_cognitive_db):
    # Insert a corrupted node with replacement character
    import sqlite3
    with sqlite3.connect(temp_cognitive_db.db_path) as conn:
        conn.execute(
            "INSERT INTO cognitive_nodes (id, category, content, importance, created_at, last_accessed, access_count, metadata_json, embedding_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("corrupt-1", "semantic", "Aratrma zeti \ufffd\ufffd bozuk", 0.5, time.time(), time.time(), 1, "{}", None)
        )
        conn.commit()

    assert temp_cognitive_db.get_node("corrupt-1") is not None

    stats = temp_cognitive_db.migrate_and_clean_database()
    assert stats["cleaned"] >= 1
    assert temp_cognitive_db.get_node("corrupt-1") is None

    # Check that ego has 384-d embedding
    ego = temp_cognitive_db.get_node("ego-entropy-core")
    assert ego is not None
    assert ego.embedding is not None
    assert len(ego.embedding) == 384



