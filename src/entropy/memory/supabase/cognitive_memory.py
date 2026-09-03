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
    embedding: Optional[List[float]] = None

    def calculate_ebbinghaus_strength(self, current_time: Optional[float] = None, decay_rate: float = 0.05) -> float:
        """Layer 5: Ebbinghaus Forgetting Curve strength calculation."""
        now = current_time or time.time()
        days_elapsed = max(0.0, (now - self.last_accessed) / 86400.0)
        # Repetition stabilizes memory (increased access_count flattens decay)
        stability = 1.0 + math.log(self.access_count + 1)
        strength = self.importance * math.exp(- (decay_rate * days_elapsed) / stability)
        return max(0.0, min(1.0, strength))

class LocalEmbeddingEngine:
    """Zero-API, 100% offline neural embedding engine with fast fallback (T2.1)."""
    _instance = None
    _model = None
    _is_neural = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        try:
            from fastembed import TextEmbedding
            # Lightweight 384-dimensional ONNX embedding model (<5ms on CPU)
            self._model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            self._is_neural = True
        except Exception:
            self._model = None
            self._is_neural = False

    def embed_text(self, text: str) -> List[float]:
        """Generate a 384-dimensional dense embedding vector."""
        if not text or not text.strip():
            return [0.0] * 384

        if self._is_neural and self._model is not None:
            try:
                vecs = list(self._model.embed([text]))
                return [float(x) for x in vecs[0]]
            except Exception:
                pass

        return self._hash_dense_embedding(text, dim=384)

    def _hash_dense_embedding(self, text: str, dim: int = 384) -> List[float]:
        """Deterministic dense representation when neural model is unavailable or initializing."""
        vec = [0.0] * dim
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vec
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h % 2 == 0) else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two dense vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    sim = dot / (math.sqrt(norm1) * math.sqrt(norm2))
    return max(0.0, min(1.0, sim))

def compute_bm25_score(query_tokens: List[str], doc_tokens: List[str], avg_doc_len: float = 25.0, k1: float = 1.2, b: float = 0.75) -> float:
    """BM25 term frequency saturation and document length normalization (T2.2)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    score = 0.0
    for q in query_tokens:
        count = doc_tokens.count(q)
        if count > 0:
            tf = (count * (k1 + 1)) / (count + k1 * (1 - b + b * (doc_len / max(1.0, avg_doc_len))))
            score += tf
    return min(1.0, score / max(1.0, len(query_tokens) * 1.5))

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
        """Initialize local SQLite persistence schema with embedding vector support (T2.1)."""
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
                    metadata_json TEXT,
                    embedding_json TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON cognitive_nodes (category);
            """)
            # Migration check: ensure embedding_json column exists
            cursor.execute("PRAGMA table_info(cognitive_nodes)")
            cols = [row[1] for row in cursor.fetchall()]
            if "embedding_json" not in cols:
                cursor.execute("ALTER TABLE cognitive_nodes ADD COLUMN embedding_json TEXT")
            conn.commit()

    def _seed_ego_identity(self):
        """Layer 12: Ensure core Ego / Identity persona node exists."""
        ego_id = "ego-entropy-core"
        if not self.get_node(ego_id):
            self._update_ego_identity()

    def _update_ego_identity(self):
        """Ensure core Ego / Identity persona node reflects current system capabilities."""
        ego_id = "ego-entropy-core"
        ego_content = (
            "I am Entropy AI, an autonomous agentic desktop operating system for Windows. "
            "I operate on-device using the Antigravity CLI without demanding external API keys. "
            "I integrate an Obsidian exocortex with bidirectional GraphRAG, 384-dimensional local neural vector embeddings, "
            "Python AST syntax-aware codebase indexing, and background dreaming consolidation."
        )
        ego_node = CognitiveMemoryNode(
            id=ego_id,
            category="ego",
            content=ego_content,
            importance=1.0,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=100,
            metadata={"type": "core_identity", "immutable": True}
        )
        self._save_node(ego_node)

    def migrate_and_clean_database(self) -> Dict[str, int]:
        """
        Audits existing SQLite database:
        - Removes corrupted nodes with replacement characters or malformed titles.
        - Backfills dense 384-d vector embeddings for all remaining nodes.
        - Synchronizes Ego node with current architectural invariants.
        """
        cleaned_count = 0
        reembedded_count = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, content, importance, metadata_json, embedding_json FROM cognitive_nodes")
            rows = cursor.fetchall()

            for r in rows:
                nid, cat, content, importance, meta_json, emb_json = r
                # Check for corrupted encoding or fragmented garbage
                if "\ufffd" in content or "Aratrma" in content or len(content.strip()) < 5:
                    cursor.execute("DELETE FROM cognitive_nodes WHERE id = ?", (nid,))
                    cleaned_count += 1
                    continue

                # Check if embedding is missing or empty
                emb = json.loads(emb_json) if emb_json else None
                if not emb or len(emb) != 384:
                    new_emb = LocalEmbeddingEngine.get_instance().embed_text(content)
                    cursor.execute("UPDATE cognitive_nodes SET embedding_json = ? WHERE id = ?", (json.dumps(new_emb), nid))
                    reembedded_count += 1

            conn.commit()

        self._update_ego_identity()
        return {"cleaned": cleaned_count, "reembedded": reembedded_count}

    def _generate_node_id(self, category: str, content: str) -> str:
        h = hashlib.sha256(f"{category}:{content.strip().lower()}".encode("utf-8")).hexdigest()[:16]
        return f"{category}-{h}"

    def _save_node(self, node: CognitiveMemoryNode):
        if node.embedding is None or len(node.embedding) == 0:
            node.embedding = LocalEmbeddingEngine.get_instance().embed_text(node.content)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cognitive_nodes (id, category, content, importance, created_at, last_accessed, access_count, metadata_json, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    importance = excluded.importance,
                    last_accessed = excluded.last_accessed,
                    access_count = cognitive_nodes.access_count + 1,
                    metadata_json = excluded.metadata_json,
                    embedding_json = excluded.embedding_json
            """, (
                node.id,
                node.category,
                node.content,
                node.importance,
                node.created_at,
                node.last_accessed,
                node.access_count,
                json.dumps(node.metadata or {}),
                json.dumps(node.embedding or [])
            ))
            conn.commit()

    def get_node(self, node_id: str) -> Optional[CognitiveMemoryNode]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, content, importance, created_at, last_accessed, access_count, metadata_json, embedding_json FROM cognitive_nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            if not row:
                return None
            embedding = json.loads(row[8]) if (len(row) > 8 and row[8]) else None
            return CognitiveMemoryNode(
                id=row[0],
                category=row[1],
                content=row[2],
                importance=row[3],
                created_at=row[4],
                last_accessed=row[5],
                access_count=row[6],
                metadata=json.loads(row[7] or "{}"),
                embedding=embedding
            )

    def get_all_nodes(self) -> List[CognitiveMemoryNode]:
        """Return all cognitive memory nodes from local SQLite persistence."""
        nodes = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, content, importance, created_at, last_accessed, access_count, metadata_json, embedding_json FROM cognitive_nodes")
            for row in cursor.fetchall():
                embedding = json.loads(row[8]) if (len(row) > 8 and row[8]) else None
                nodes.append(CognitiveMemoryNode(
                    id=row[0],
                    category=row[1],
                    content=row[2],
                    importance=row[3],
                    created_at=row[4],
                    last_accessed=row[5],
                    access_count=row[6],
                    metadata=json.loads(row[7] or "{}"),
                    embedding=embedding
                ))
        return nodes

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

        # Novel memory: insert new node with dense embedding
        embedding = LocalEmbeddingEngine.get_instance().embed_text(content)
        new_node = CognitiveMemoryNode(
            id=node_id,
            category=category,
            content=content,
            importance=max(0.0, min(1.0, importance)),
            created_at=now,
            last_accessed=now,
            access_count=1,
            metadata=metadata or {},
            embedding=embedding
        )
        self._save_node(new_node)
        return new_node, True

    def hybrid_recall(
        self,
        query: str,
        top_k: int = 5,
        min_threshold: float = 0.15
    ) -> List[Tuple[CognitiveMemoryNode, float]]:
        """
        T2.2 & T2.3: Recollection Engine with Multi-Criteria Hybrid Scoring & Noise Pruning.
        Score = 0.40 * VectorSim + 0.20 * BM25 + 0.25 * Ebbinghaus + 0.15 * Recency
        Filters out noise where final_score < min_threshold.
        """
        now = time.time()
        query_vector = LocalEmbeddingEngine.get_instance().embed_text(query)
        query_tokens = re_tokenize(query)
        results = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, content, importance, created_at, last_accessed, access_count, metadata_json, embedding_json FROM cognitive_nodes")
            rows = cursor.fetchall()

        nodes_to_update = []

        for row in rows:
            embedding = json.loads(row[8]) if (len(row) > 8 and row[8]) else None
            node = CognitiveMemoryNode(
                id=row[0],
                category=row[1],
                content=row[2],
                importance=row[3],
                created_at=row[4],
                last_accessed=row[5],
                access_count=row[6],
                metadata=json.loads(row[7] or "{}"),
                embedding=embedding
            )

            # 1. Dense Vector Cosine Similarity (Weight: 0.40)
            if not node.embedding:
                node.embedding = LocalEmbeddingEngine.get_instance().embed_text(node.content)
                nodes_to_update.append((json.dumps(node.embedding), node.id))
            raw_sim = cosine_similarity(query_vector, node.embedding)
            # Rescale cosine similarity to [0, 1] removing typical dense embedding anisotropy baseline (~0.50)
            vec_sim = max(0.0, min(1.0, (raw_sim - 0.50) / 0.50))

            # 2. Sparse Lexical BM25 Score (Weight: 0.20)
            node_tokens = re_tokenize(node.content)
            bm25_sim = compute_bm25_score(query_tokens, node_tokens)

            # 3. Ebbinghaus Forgetting Curve Retention (Weight: 0.25)
            ebbinghaus_strength = node.calculate_ebbinghaus_strength(current_time=now)

            # 4. Recency Exponential Decay (Weight: 0.15)
            days_ago = max(0.0, (now - node.last_accessed) / 86400.0)
            recency = math.exp(-0.05 * days_ago)

            # Multi-criteria hybrid score formula (T2.2)
            final_score = (
                (0.40 * vec_sim) +
                (0.20 * bm25_sim) +
                (0.25 * ebbinghaus_strength) +
                (0.15 * recency)
            )

            # T2.3: Noise pruning: If both lexical and semantic relevance are low, suppress recency leakage
            if bm25_sim == 0.0 and vec_sim < 0.35:
                final_score *= (vec_sim / 0.35)

            # T2.3: Noise pruning threshold
            if final_score >= min_threshold:
                results.append((node, final_score))

        # Lazy backfill embeddings into SQLite if any were missing
        if nodes_to_update:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.executemany("UPDATE cognitive_nodes SET embedding_json = ? WHERE id = ?", nodes_to_update)
                    conn.commit()
            except Exception:
                pass

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
        Layer 6: Dreaming / Clustering Consolidation (T3.1 & T3.2).
        Gathers episodic memories from the past 24-48 hours, aggregates themes,
        saves consolidated semantic facts, and appends architectural decisions to Obsidian MEMORY.md.
        """
        now = time.time()
        two_days_ago = now - (2 * 86400.0)
        synthesized_rules = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, metadata_json, importance FROM cognitive_nodes WHERE category = 'episodic' AND created_at >= ?",
                (two_days_ago,)
            )
            rows = cursor.fetchall()

        if len(rows) >= 2:
            date_str = time.strftime('%Y-%m-%d')
            topics = [r[0][:80] for r in rows[:5]]
            summary = f"Konsolide Bilişsel Özet ({date_str}): {len(rows)} bölümsel etkileşimden damıtıldı."

            self.record_memory(
                category="semantic",
                content=summary,
                importance=0.85,
                metadata={"source": "dream_consolidation", "items_clustered": len(rows), "samples": topics}
            )
            synthesized_rules.append(summary)

            # T3.2: Export to Obsidian MEMORY.md if available
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                ovm = ObsidianVaultManager()
                ovm.append_to_global_memory("Otonom Bilişsel Konsolidasyon (Rüya)", f"{summary}\n- İpuçları: {'; '.join(topics)}")
            except Exception:
                pass

        # Also run pruning during dream cycle
        self.prune_decayed_memories()
        return synthesized_rules

    def prune_decayed_memories(self, min_strength: float = 0.10, days_dormant: float = 30.0) -> int:
        """
        Layer 5 & T3.3: Prune decayed low-importance episodic memories.
        Prunes nodes where:
        - category is 'episodic'
        - initial importance < 0.35
        - days since last access >= days_dormant
        - calculated Ebbinghaus retention strength < min_strength
        Never prunes 'ego', 'semantic', or 'procedural' memories.
        """
        now = time.time()
        dormant_cutoff = now - (days_dormant * 86400.0)
        pruned_ids = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, category, content, importance, created_at, last_accessed, access_count FROM cognitive_nodes WHERE category = 'episodic' AND last_accessed <= ? AND importance < 0.35",
                (dormant_cutoff,)
            )
            rows = cursor.fetchall()

            for r in rows:
                node = CognitiveMemoryNode(
                    id=r[0],
                    category=r[1],
                    content=r[2],
                    importance=r[3],
                    created_at=r[4],
                    last_accessed=r[5],
                    access_count=r[6]
                )
                if node.calculate_ebbinghaus_strength(current_time=now) < min_strength:
                    pruned_ids.append(node.id)

            if pruned_ids:
                cursor.executemany("DELETE FROM cognitive_nodes WHERE id = ?", [(pid,) for pid in pruned_ids])
                conn.commit()

        return len(pruned_ids)

def re_tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer."""
    return [w.lower() for w in re.findall(r"\w+", text)]
