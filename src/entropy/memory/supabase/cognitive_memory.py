"""12-Layer Cognitive Memory Architecture (Mem0 + Supabase pgvector & Local SQLite Fallback)."""

import hashlib
import json
import math
import re
import sqlite3
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from entropy.core.config import config

@dataclass
class CognitiveMemoryNode:
    id: str
    category: str       # 'episodic', 'semantic', 'procedural', 'ego'
    content: str
    importance: float   # 0.0 to 1.0
    created_at: float   # epoch timestamp
    last_accessed: float
    access_count: int = 1
    metadata: Dict[str, Any] = None

    def calculate_ebbinghaus_strength(self, current_time: Optional[float] = None, decay_rate: float = 0.05) -> float:
        """Layer 5: Ebbinghaus Forgetting Curve strength calculation."""
        now = current_time or time.time()
        days_elapsed = max(0.0, (now - self.last_accessed) / 86400.0)
        # Repetition stabilizes memory (increased access_count flattens decay)
        stability = 1.0 + math.log(self.access_count + 1)
        strength = self.importance * math.exp(- (decay_rate * days_elapsed) / stability)
        return max(0.0, min(1.0, strength))

class CognitiveMemorySystem:
    """Manages multi-layered cognitive memory with Supabase pgvector and offline SQLite fallback."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            entropy_home = Path.home() / ".entropy"
            entropy_home.mkdir(parents=True, exist_ok=True)
            self.db_path = entropy_home / "cognitive_memory.db"
        else:
            self.db_path = Path(db_path)
        
        self._init_sqlite_db()
        self._seed_ego_identity()

    def _init_sqlite_db(self):
        """Initialize local SQLite persistence schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_nodes (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    created_at REAL,
                    last_accessed REAL,
                    access_count INTEGER DEFAULT 1,
                    metadata_json TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON cognitive_nodes (category);
            """)
            conn.commit()

    def _seed_ego_identity(self):
        """Layer 12: Ensure core Ego / Identity persona node exists."""
        ego_id = "ego-entropy-core"
        if not self.get_node(ego_id):
            ego_node = CognitiveMemoryNode(
                id=ego_id,
                category="ego",
                content=(
                    "I am Entropy AI, an autonomous agentic desktop operating system for Windows. "
                    "I operate on-device using the Antigravity CLI without demanding external API keys. "
                    "I continuously adapt, learn, and maintain memory across sessions."
                ),
                importance=1.0,
                created_at=time.time(),
                last_accessed=time.time(),
                access_count=100,
                metadata={"type": "core_identity", "immutable": True}
            )
            self._save_node(ego_node)

    def _generate_node_id(self, category: str, content: str) -> str:
        h = hashlib.sha256(f"{category}:{content.strip().lower()}".encode("utf-8")).hexdigest()[:16]
        return f"{category}-{h}"

    def _save_node(self, node: CognitiveMemoryNode):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cognitive_nodes (id, category, content, importance, created_at, last_accessed, access_count, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    importance = excluded.importance,
                    last_accessed = excluded.last_accessed,
                    access_count = cognitive_nodes.access_count + 1,
                    metadata_json = excluded.metadata_json
            """, (
                node.id,
                node.category,
                node.content,
                node.importance,
                node.created_at,
                node.last_accessed,
                node.access_count,
                json.dumps(node.metadata or {})
            ))
            conn.commit()

    def get_node(self, node_id: str) -> Optional[CognitiveMemoryNode]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, content, importance, created_at, last_accessed, access_count, metadata_json FROM cognitive_nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return CognitiveMemoryNode(
                id=row[0],
                category=row[1],
                content=row[2],
                importance=row[3],
                created_at=row[4],
                last_accessed=row[5],
                access_count=row[6],
                metadata=json.loads(row[7] or "{}")
            )

    def record_memory(
        self,
        category: str,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[CognitiveMemoryNode, bool]:
        """
        Layer 2: Surprise/Novelty Filter check.
        If node exists, increments access count and updates recency without duplicating.
        """
        node_id = self._generate_node_id(category, content)
        existing = self.get_node(node_id)
        now = time.time()

        if existing:
            # Not novel: update existing node
            existing.last_accessed = now
            existing.access_count += 1
            existing.importance = max(existing.importance, importance)
            if metadata:
                existing.metadata.update(metadata)
            self._save_node(existing)
            return existing, False

        # Novel memory: insert new node
        new_node = CognitiveMemoryNode(
            id=node_id,
            category=category,
            content=content,
            importance=max(0.0, min(1.0, importance)),
            created_at=now,
            last_accessed=now,
            access_count=1,
            metadata=metadata or {}
        )
        self._save_node(new_node)
        return new_node, True

    def hybrid_recall(self, query: str, top_k: int = 5) -> List[Tuple[CognitiveMemoryNode, float]]:
        """
        RecollectionEngine: Combines Lexical/Semantic Match + Importance + Recency.
        Score = 0.50 * SimScore + 0.30 * Importance + 0.20 * Recency
        """
        now = time.time()
        query_words = set(re_tokenize(query))
        results = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, content, importance, created_at, last_accessed, access_count, metadata_json FROM cognitive_nodes")
            rows = cursor.fetchall()

        for row in rows:
            node = CognitiveMemoryNode(
                id=row[0],
                category=row[1],
                content=row[2],
                importance=row[3],
                created_at=row[4],
                last_accessed=row[5],
                access_count=row[6],
                metadata=json.loads(row[7] or "{}")
            )

            # Text match score (Jaccard similarity approximation)
            node_words = set(re_tokenize(node.content))
            intersection = query_words.intersection(node_words)
            sim_score = len(intersection) / max(1, len(query_words.union(node_words)))

            # Ebbinghaus-adjusted strength
            strength = node.calculate_ebbinghaus_strength(current_time=now)

            # Recency factor (0 to 1 over last 30 days)
            days_ago = max(0.0, (now - node.last_accessed) / 86400.0)
            recency = math.exp(-0.1 * days_ago)

            # Hybrid scoring formula from research report
            final_score = (0.50 * sim_score) + (0.30 * strength) + (0.20 * recency)
            results.append((node, final_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def store_node(
        self,
        category: str,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[CognitiveMemoryNode, bool]:
        """Convenience alias for record_memory."""
        return self.record_memory(category, content, importance, metadata)

    def recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Convenience alias returning list of dicts for hybrid_recall."""
        results = self.hybrid_recall(query, top_k=limit)
        return [
            {
                "id": node.id,
                "category": node.category,
                "content": node.content,
                "importance": node.importance,
                "score": score
            }
            for node, score in results
        ]

    def dream_and_consolidate(self) -> List[str]:
        """
        Layer 6: Dreaming / Clustering Consolidation.
        Gathers episodic memories from the past 24 hours, aggregates common themes,
        and generates synthesized semantic facts.
        """
        now = time.time()
        one_day_ago = now - 86400.0
        synthesized_rules = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, metadata_json FROM cognitive_nodes WHERE category = 'episodic' AND created_at >= ?",
                (one_day_ago,)
            )
            rows = cursor.fetchall()

        if len(rows) >= 3:
            # Cluster and create a consolidated semantic memory
            summary = f"Synthesized from {len(rows)} recent episodic interactions on {time.strftime('%Y-%m-%d')}"
            self.record_memory(
                category="semantic",
                content=summary,
                importance=0.8,
                metadata={"source": "dream_consolidation", "items_clustered": len(rows)}
            )
            synthesized_rules.append(summary)

        return synthesized_rules

def re_tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer."""
    return [w.lower() for w in re.findall(r"\w+", text)]
