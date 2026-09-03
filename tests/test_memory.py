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
