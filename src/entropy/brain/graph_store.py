"""
Birleşik bellek grafı (Faz 5.1 / 5.2).

Tek depo ilkesi: ayrı bir graf veritabanı yoktur; mevcut bilişsel bellek
SQLite dosyası `nodes` / `edges` / `communities` tablolarıyla genişletilir.
Eski `cognitive_nodes` tablosu **olduğu gibi kalır**, böylece `store_node`,
`hybrid_recall`, `dream_and_consolidate` gibi API'ler değişmeden çalışır;
graf katmanı onun üstüne aynalanır.

Model kararları (bkz. docs/reports/2026-09-10_Faz5_Tasarim_Raporu.md §3.1):
- Çift zamanlı kenarlar: `t_valid_from` / `t_valid_to` (NULL = hâlâ geçerli) +
  `ingested_at`. Çelişkide silme yok; eski kenar kapatılır, yenisi `supersedes`
  ile eskisine bağlanır (Zep/Graphiti).
- Düğüm türleri CoALA'nın bellek türlerini kapsar, kapsam (`scope`) alanı Desk
  belleğini aynı grafın alt-grafı yapar.
- Geri çağırma: hibrit tohumlama -> 2 adım yayılım (Personalized PageRank,
  HippoRAG 2 tarzı) -> geçerlilik/tür/kapsam filtresi -> bütçe kırpma.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from entropy.brain.reconcile import (
    ExistingFact,
    Fact,
    ReconcileResult,
    extract_entities,
    extract_facts,
    normalize_text,
    reconcile_facts,
    tr_lower,
)
from entropy.brain.supabase.cognitive_memory import (
    EMBEDDING_DIM,
    CognitiveMemorySystem,
)

try:
    import numpy as _np
except Exception:  # pragma: no cover - numpy'siz ortam
    _np = None


# --- sözleşme: tür kümeleri -------------------------------------------------

NODE_TYPES = (
    "episode", "fact", "entity", "procedure", "agent",
    "office", "task", "report", "session", "community",
)

EDGE_TYPES = (
    "derived_from", "contradicts", "supersedes", "triggered",
    "produced", "member_of", "similar_to",
)

# Eski `cognitive_nodes.category` -> yeni düğüm türü. Listede olmayan
# kategoriler (architecture, protocol, math ...) anlamsal olgudur.
CATEGORY_TO_TYPE: Dict[str, str] = {
    "episodic": "episode",
    "semantic": "fact",
    "procedural": "procedure",
    "ego": "entity",
    "session": "session",
    "query": "report",
    "report": "report",
    "task": "task",
    "agent": "agent",
    "office": "office",
    "entity": "entity",
}
DEFAULT_NODE_TYPE = "fact"

# Ters eşleme: grafa yazılan düğüm eski tabloya aynalanırken hangi kategoriye
# düşer. Aynalama olmadan yeni bilgi `hybrid_recall`ın tohumlamasına giremezdi
# ve "tek bilinç" iki ayrı belleğe bölünürdü.
TYPE_TO_CATEGORY: Dict[str, str] = {
    "episode": "episodic",
    "fact": "semantic",
    "procedure": "procedural",
    "session": "session",
    "report": "semantic",
    "task": "episodic",
    "community": "semantic",
}

# Kaynak türüne göre taban önem (tasarım §3.1).
SOURCE_IMPORTANCE: Dict[str, float] = {
    "report": 0.6,
    "session": 0.4,
    "fact": 0.5,
    "episode": 0.4,
    "procedure": 0.55,
    "entity": 0.35,
    "task": 0.5,
    "agent": 0.5,
    "office": 0.5,
    "community": 0.5,
}
USER_PIN_IMPORTANCE = 1.0

SCOPE_GENERAL = "general"


def compute_importance(
    source_type: str,
    repeat_count: int = 1,
    pinned: bool = False,
) -> float:
    """
    Önem puanı = kaynak türü tabanı + tekrar bonusu; kullanıcı sabitlemesi 1.0.

    Tekrar bonusu logaritmiktir: 10 kez görülen bir olgu +0.22 alır, 100 kez
    görülen +0.46. Doğrusal olsaydı tek bir gürültülü döngü her şeyi 1.0 yapardı.
    """
    if pinned:
        return USER_PIN_IMPORTANCE
    base = SOURCE_IMPORTANCE.get(source_type, 0.5)
    bonus = 0.10 * math.log1p(max(0, int(repeat_count) - 1))
    return max(0.0, min(1.0, base + bonus))


@dataclass
class GraphNode:
    id: str
    type: str
    title: str
    body: str
    importance: float = 0.5
    created_at: float = 0.0
    updated_at: float = 0.0
    scope: str = SCOPE_GENERAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: str = ""
    access_count: int = 1

    def ebbinghaus(self, now: Optional[float] = None, decay_rate: float = 0.05) -> float:
        now = now or time.time()
        days = max(0.0, (now - (self.updated_at or self.created_at or now)) / 86400.0)
        stability = 1.0 + math.log(max(1, self.access_count) + 1)
        return max(0.0, min(1.0, self.importance * math.exp(-(decay_rate * days) / stability)))


@dataclass
class GraphEdge:
    id: int
    src: str
    dst: str
    type: str
    t_valid_from: float
    t_valid_to: Optional[float]
    ingested_at: float
    weight: float = 1.0
    provenance: str = ""

    @property
    def is_valid(self) -> bool:
        return self.t_valid_to is None


@dataclass
class Community:
    id: str
    label: str
    summary: str
    member_count: int


def _slug(text: str, limit: int = 60) -> str:
    s = re.sub(r"[^\w]+", "-", tr_lower(text or "")).strip("-")
    return (s or "x")[:limit]


def _first_line(text: str, limit: int = 120) -> str:
    for line in (text or "").splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:limit]
    return (text or "").strip()[:limit]


class GraphStore:
    """
    `nodes` / `edges` / `communities` üzerinde çalışan birleşik graf katmanı.

    Aynı SQLite dosyasını `CognitiveMemorySystem` ile paylaşır. Yazma yolu
    uzlaştırmadan geçer (`ingest_text`), okuma yolu hibrit tohumlama + PPR
    yayılımıdır (`graph_recall`).
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        memory: Optional[CognitiveMemorySystem] = None,
    ):
        if memory is not None:
            self.memory = memory
            self.db_path = Path(memory.db_path)
        else:
            self.memory = CognitiveMemorySystem(db_path=db_path)
            self.db_path = Path(self.memory.db_path)
        self._init_schema()

    # -- şema ------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    title TEXT,
                    body TEXT,
                    importance REAL DEFAULT 0.5,
                    created_at REAL,
                    updated_at REAL,
                    scope TEXT DEFAULT 'general',
                    metadata_json TEXT,
                    provenance TEXT,
                    access_count INTEGER DEFAULT 1
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    src TEXT NOT NULL,
                    dst TEXT NOT NULL,
                    type TEXT NOT NULL,
                    t_valid_from REAL,
                    t_valid_to REAL,
                    ingested_at REAL,
                    weight REAL DEFAULT 1.0,
                    provenance TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS communities (
                    id TEXT PRIMARY KEY,
                    label TEXT,
                    summary TEXT,
                    member_count INTEGER DEFAULT 0
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes (type)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_scope ON nodes (scope)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON edges (src)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges (dst)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges (type)")
            conn.commit()

    # -- düğüm / kenar temel işlemleri ------------------------------------

    def upsert_node(
        self,
        node_id: str,
        node_type: str,
        title: str,
        body: str = "",
        importance: Optional[float] = None,
        scope: str = SCOPE_GENERAL,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: str = "",
        created_at: Optional[float] = None,
        mirror: bool = True,
    ) -> GraphNode:
        now = time.time()
        existing = self.get_node(node_id)
        if existing is not None:
            access = existing.access_count + 1
            imp = importance if importance is not None else compute_importance(
                existing.type, repeat_count=access,
                pinned=bool((existing.metadata or {}).get("pinned")),
            )
            imp = max(existing.importance, imp)
            meta = dict(existing.metadata or {})
            meta.update(metadata or {})
            with self._connect() as conn:
                conn.execute(
                    "UPDATE nodes SET title=?, body=?, importance=?, updated_at=?, "
                    "metadata_json=?, provenance=?, access_count=? WHERE id=?",
                    (title or existing.title, body or existing.body, imp, now,
                     json.dumps(meta, ensure_ascii=False), provenance or existing.provenance,
                     access, node_id),
                )
                conn.commit()
            node = self.get_node(node_id)  # type: ignore[assignment]
            if mirror and node is not None:
                self._mirror_to_cognitive(node)
            return node  # type: ignore[return-value]

        if importance is None:
            importance = compute_importance(
                node_type, repeat_count=1, pinned=bool((metadata or {}).get("pinned"))
            )
        created = created_at if created_at is not None else now
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO nodes (id, type, title, body, importance, created_at, updated_at,"
                " scope, metadata_json, provenance, access_count) VALUES (?,?,?,?,?,?,?,?,?,?,1)",
                (node_id, node_type, title, body, float(importance), created, now,
                 scope or SCOPE_GENERAL, json.dumps(metadata or {}, ensure_ascii=False),
                 provenance),
            )
            conn.commit()
        node = self.get_node(node_id)  # type: ignore[assignment]
        if mirror and node is not None:
            self._mirror_to_cognitive(node)
        return node  # type: ignore[return-value]

    def _existing_node_ids(self, candidates: Optional[Sequence[str]] = None) -> set:
        """Graf `nodes` tablosunda hâlihazırda bulunan kimlikler."""
        with self._connect() as conn:
            if candidates is None:
                return {r[0] for r in conn.execute("SELECT id FROM nodes")}
            out: set = set()
            ids = list(dict.fromkeys(candidates))
            # SQLite değişken sınırı (999) aşılmasın diye parçalanır.
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                ph = ",".join("?" for _ in chunk)
                out |= {r[0] for r in conn.execute(f"SELECT id FROM nodes WHERE id IN ({ph})", chunk)}
            return out

    def _known_edge_keys(self, srcs: Optional[Sequence[str]] = None) -> set:
        """(src, dst, type) üçlüleri; kenar çoğaltmasını önlemek için."""
        with self._connect() as conn:
            if srcs is None:
                return {(r[0], r[1], r[2]) for r in conn.execute("SELECT src, dst, type FROM edges")}
            out: set = set()
            ids = list(dict.fromkeys(srcs))
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                ph = ",".join("?" for _ in chunk)
                out |= {
                    (r[0], r[1], r[2])
                    for r in conn.execute(
                        f"SELECT src, dst, type FROM edges WHERE src IN ({ph}) OR dst IN ({ph})",
                        chunk + chunk,
                    )
                }
            return out

    def _mirror_to_cognitive(self, node: GraphNode) -> None:
        """
        Graf düğümünü eski `cognitive_nodes` tablosuna aynalar (aynı kimlikle).

        Neden: geri çağırmanın tohumlaması `hybrid_recall` üzerinden gider ve
        eski API'ler (`recall`, bağlam kurucu, bellek denetçisi) hâlâ o tabloyu
        okur. Aynalama olmasa grafa yazılan bilgi hiçbir sorguda görünmezdi.
        Gömme burada üretilmez; geri çağırma indeksi eksik gömmeyi zaten ilk
        sorguda hesaplayıp geri yazıyor (düğüm başına ~90 ms tasarruf).
        """
        category = TYPE_TO_CATEGORY.get(node.type, node.type)
        legacy = (node.metadata or {}).get("legacy_category")
        if legacy:
            category = legacy
        # Faz 11.1: aynalama sekizinci yazma noktasıydı ve `record_memory`yi
        # atladığı için kategori disiplininin dışında kalıyordu ("session",
        # "query", "report" değerleri buradan da giriyordu). Kanonik dörtlüye
        # indirgenir; ham değer metadata'da izlenebilir kalır.
        from entropy.brain.categories import normalize_category

        resolution = normalize_category(category)
        if resolution.mapped:
            (node.metadata or {}).setdefault("legacy_category", category)
        category = resolution.category
        content = node.body or node.title or ""
        if not content.strip():
            return
        meta = dict(node.metadata or {})
        meta.setdefault("graph_type", node.type)
        meta.setdefault("scope", node.scope)
        if node.provenance:
            meta.setdefault("path", node.provenance)
        try:
            with self._connect() as conn:
                conn.execute(
                    # Faz 11-B QA (K12): `provenance` sütunu buraya YAZILMIYORDU.
                    # Ölçüldü: göç sonrası konsolidasyonun ürettiği 42 küme/yansıma
                    # düğümü `cognitive_nodes` tarafında kaynaksız görünüyordu
                    # (graf tarafında `consolidate:label_propagation` yazılı olduğu
                    # hâlde). Kaynak artık aynada da taşınır.
                    "INSERT INTO cognitive_nodes (id, category, content, importance,"
                    " created_at, last_accessed, access_count, metadata_json, provenance)"
                    " VALUES (?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(id) DO UPDATE SET content=excluded.content,"
                    " importance=excluded.importance, last_accessed=excluded.last_accessed,"
                    " access_count=excluded.access_count, metadata_json=excluded.metadata_json,"
                    " provenance=CASE WHEN TRIM(COALESCE(cognitive_nodes.provenance,'')) = ''"
                    " THEN excluded.provenance ELSE cognitive_nodes.provenance END",
                    (node.id, category, content, float(node.importance),
                     node.created_at or time.time(), node.updated_at or time.time(),
                     int(node.access_count or 1), json.dumps(meta, ensure_ascii=False),
                     str(node.provenance or "")),
                )
                conn.commit()
        except sqlite3.Error:
            return
        self.memory._invalidate_recall_index()

    def _row_to_node(self, row: Sequence[Any]) -> GraphNode:
        return GraphNode(
            id=row[0], type=row[1], title=row[2] or "", body=row[3] or "",
            importance=row[4] if row[4] is not None else 0.5,
            created_at=row[5] or 0.0, updated_at=row[6] or 0.0,
            scope=row[7] or SCOPE_GENERAL,
            metadata=json.loads(row[8] or "{}"),
            provenance=row[9] or "", access_count=row[10] or 1,
        )

    _NODE_COLS = ("id, type, title, body, importance, created_at, updated_at, scope,"
                  " metadata_json, provenance, access_count")

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {self._NODE_COLS} FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
        return self._row_to_node(row) if row else None

    def all_nodes(
        self,
        types: Optional[Iterable[str]] = None,
        scopes: Optional[Iterable[str]] = None,
    ) -> List[GraphNode]:
        sql = f"SELECT {self._NODE_COLS} FROM nodes"
        clauses, params = [], []
        if types:
            types = list(types)
            clauses.append(f"type IN ({','.join('?' * len(types))})")
            params += types
        if scopes:
            scopes = list(scopes)
            clauses.append(f"scope IN ({','.join('?' * len(scopes))})")
            params += scopes
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_node(r) for r in rows]

    def node_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])

    def edge_count(self, valid_only: bool = False) -> int:
        sql = "SELECT COUNT(*) FROM edges"
        if valid_only:
            sql += " WHERE t_valid_to IS NULL"
        with self._connect() as conn:
            return int(conn.execute(sql).fetchone()[0])

    def add_edge(
        self,
        src: str,
        dst: str,
        edge_type: str,
        weight: float = 1.0,
        provenance: str = "",
        t_valid_from: Optional[float] = None,
        t_valid_to: Optional[float] = None,
    ) -> int:
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO edges (src, dst, type, t_valid_from, t_valid_to, ingested_at,"
                " weight, provenance) VALUES (?,?,?,?,?,?,?,?)",
                (src, dst, edge_type,
                 t_valid_from if t_valid_from is not None else now,
                 t_valid_to, now, float(weight), provenance),
            )
            conn.commit()
            return int(cur.lastrowid)

    def add_edges_bulk(self, rows: Sequence[Tuple[str, str, str, float, str]]) -> int:
        """(src, dst, type, weight, provenance) demetlerini tek işlemde yazar."""
        if not rows:
            return 0
        now = time.time()
        payload = [(r[0], r[1], r[2], now, None, now, float(r[3]), r[4]) for r in rows]
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO edges (src, dst, type, t_valid_from, t_valid_to, ingested_at,"
                " weight, provenance) VALUES (?,?,?,?,?,?,?,?)", payload,
            )
            conn.commit()
        return len(payload)

    def invalidate_edge(self, edge_id: int, when: Optional[float] = None) -> None:
        """Kenarı geçersizleştirir (silmez): `t_valid_to` doldurulur."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE edges SET t_valid_to = ? WHERE id = ? AND t_valid_to IS NULL",
                (when if when is not None else time.time(), edge_id),
            )
            conn.commit()

    def _row_to_edge(self, row: Sequence[Any]) -> GraphEdge:
        return GraphEdge(
            id=row[0], src=row[1], dst=row[2], type=row[3],
            t_valid_from=row[4] or 0.0, t_valid_to=row[5],
            ingested_at=row[6] or 0.0, weight=row[7] if row[7] is not None else 1.0,
            provenance=row[8] or "",
        )

    _EDGE_COLS = "id, src, dst, type, t_valid_from, t_valid_to, ingested_at, weight, provenance"

    def get_edges(
        self,
        src: Optional[str] = None,
        dst: Optional[str] = None,
        edge_type: Optional[str] = None,
        valid_only: bool = False,
    ) -> List[GraphEdge]:
        sql = f"SELECT {self._EDGE_COLS} FROM edges"
        clauses, params = [], []
        if src:
            clauses.append("src = ?")
            params.append(src)
        if dst:
            clauses.append("dst = ?")
            params.append(dst)
        if edge_type:
            clauses.append("type = ?")
            params.append(edge_type)
        if valid_only:
            clauses.append("t_valid_to IS NULL")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_edge(r) for r in rows]

    # -- göç ---------------------------------------------------------------

    def backup_database(self, suffix: str = ".pre_graph.bak") -> Optional[Path]:
        """Göç öncesi tam dosya yedeği; geri dönüş `restore_database()` ile."""
        target = self.db_path.with_suffix(self.db_path.suffix + suffix)
        try:
            shutil.copy2(self.db_path, target)
            return target
        except OSError:
            return None

    def restore_database(self, backup_path: Path) -> bool:
        """Yedeği geri yükler (göçten dönüş)."""
        backup_path = Path(backup_path)
        if not backup_path.is_file():
            return False
        try:
            shutil.copy2(backup_path, self.db_path)
        except OSError:
            return False
        self.memory._invalidate_recall_index()
        return True

    def migrate_from_cognitive_nodes(
        self,
        backup: bool = True,
        similarity_edges: bool = True,
        sim_top_k: int = 3,
        sim_threshold: float = 0.80,
    ) -> Dict[str, Any]:
        """
        Tam göç: `cognitive_nodes` içeriğini kayıpsız olarak grafa aktarır.

        Faz 10-A'dan sonra bu işlev `sync_from_cognitive()`'in yedek alan tam
        kapsamlı sarıcısıdır; iki kod yolu yoktur (mantık kopyalanmamıştır).
        """
        return self.sync_from_cognitive(
            node_ids=None,
            backup=backup,
            similarity_edges=similarity_edges,
            sim_top_k=sim_top_k,
            sim_threshold=sim_threshold,
        )

    def sync_from_cognitive(
        self,
        node_ids: Optional[Sequence[str]] = None,
        backup: bool = False,
        similarity_edges: bool = True,
        sim_top_k: int = 3,
        sim_threshold: float = 0.80,
    ) -> Dict[str, Any]:
        """
        `cognitive_nodes` satırlarını graf tablolarına yansıtır (idempotent).

        - `node_ids=None`: tüm tablo (tam göç / uzlaştırma).
        - `node_ids=[...]`: yalnızca verilen düğümler — yazma yolundan
          (`CognitiveMemorySystem._save_node`) her yeni anı için çağrılır; böylece
          graf katmanı canlı kalır. Önceden yalnızca elle göç vardı ve gerçek
          veritabanında 35 düğüm grafın dışında kalmıştı.

        Kurallar değişmedi: category -> type eşlemesi (özgün kategori
        `metadata.legacy_category`'de saklanır), `[[wikilink]]` -> `entity`
        düğümü + `member_of` kenarı, gömme kosinüsü -> `similar_to`. Eski tablo
        silinmez. Benzerlik kenarları yalnızca verilen küme içinde hesaplanır;
        tek düğümlü yazmada anlamsız ve pahalı olduğu için yazma yolu bunu
        kapalı çağırır, tam uzlaştırma açık çağırır.
        """
        started = time.time()
        backup_path = self.backup_database() if backup else None

        base_sql = (
            "SELECT id, category, content, importance, created_at, last_accessed,"
            " access_count, metadata_json, embedding_json FROM cognitive_nodes"
        )
        with self._connect() as conn:
            if node_ids is None:
                rows = conn.execute(base_sql).fetchall()
            else:
                wanted = list(dict.fromkeys(node_ids))
                if not wanted:
                    return {
                        "source_nodes": 0, "migrated_nodes": 0, "synced_nodes": 0,
                        "entity_nodes": 0, "graph_nodes": self.node_count(),
                        "wikilink_edges": 0, "similarity_edges": 0, "edges": 0,
                        "edges_total": self.edge_count(), "duration_s": 0.0, "backup_path": "",
                    }
                placeholders = ",".join("?" for _ in wanted)
                rows = conn.execute(
                    f"{base_sql} WHERE id IN ({placeholders})", wanted
                ).fetchall()

        source_total = len(rows)
        node_payload: List[tuple] = []
        entity_nodes: Dict[str, Tuple[str, str]] = {}
        mention_edges: List[Tuple[str, str, str, float, str]] = []
        ids: List[str] = []
        embeddings: List[Optional[List[float]]] = []

        # Yazma yolu her anıda çağrıldığı için tüm düğümleri nesneye çevirmek
        # (1400+ satır) kabul edilemez; yalnızca ilgili kimlikler sorgulanır.
        existing_ids = self._existing_node_ids(None if node_ids is None else [r[0] for r in rows])

        for row in rows:
            nid, category, content, importance, created_at, last_accessed, access_count, meta_json, emb_json = row
            meta = {}
            try:
                meta = json.loads(meta_json or "{}") or {}
            except ValueError:
                meta = {}
            node_type = CATEGORY_TO_TYPE.get((category or "").lower(), DEFAULT_NODE_TYPE)
            # Faz 11.1: yazma kapısı kategoriyi kanonik dörtlüye indirgediğinde
            # ham değeri zaten `legacy_category`ye yazar. Burada üzerine yazmak
            # o izi silerdi ("architecture" -> "semantic" görünürdü).
            meta.setdefault("legacy_category", category)
            scope = meta.get("scope") or SCOPE_GENERAL
            pinned = bool(meta.get("pinned"))
            # Önem: eski değer korunur, ama kaynak türü + tekrar sayısından
            # hesaplanan taban daha yüksekse o kullanılır (bilgi kaybı olmaz).
            derived = compute_importance(node_type, repeat_count=access_count or 1, pinned=pinned)
            imp = max(float(importance or 0.0), derived)
            provenance = str(meta.get("path") or f"cognitive_nodes:{nid}")

            ids.append(nid)
            try:
                embeddings.append(json.loads(emb_json) if emb_json else None)
            except ValueError:
                embeddings.append(None)

            if nid not in existing_ids:
                node_payload.append((
                    nid, node_type, _first_line(content), content or "", imp,
                    created_at or started, last_accessed or created_at or started,
                    scope, json.dumps(meta, ensure_ascii=False), provenance,
                    int(access_count or 1),
                ))

            for ent in extract_entities(content or ""):
                ent_id = f"entity-{_slug(ent)}"
                entity_nodes.setdefault(ent_id, (ent, provenance))
                # `member_of`: düğüm, varlığın kümesine üyedir (varlık = küme
                # başlığı). Ayrı bir "mentions" türü açmamak için sözleşmedeki
                # yedi kenar türü korunur.
                mention_edges.append((nid, ent_id, "member_of", 0.6, provenance))

        if node_payload:
            with self._connect() as conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO nodes (id, type, title, body, importance, created_at,"
                    " updated_at, scope, metadata_json, provenance, access_count)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)", node_payload,
                )
                conn.commit()

        if node_ids is not None and entity_nodes:
            existing_ids |= self._existing_node_ids(list(entity_nodes.keys()))
        for ent_id, (name, prov) in entity_nodes.items():
            if ent_id not in existing_ids:
                # Varlık saplaması eski tabloya aynalanmaz: tek sözcüklük
                # başlıklar geri çağırmada gürültü olurdu (mirror=False).
                self.upsert_node(ent_id, "entity", name, body=name,
                                 provenance=prov, metadata={"source": "wikilink"},
                                 mirror=False)

        # Aynı kenarın göç iki kez koşarsa çoğalmaması için mevcut çiftler elenir.
        known = self._known_edge_keys(None if node_ids is None else [r[0] for r in rows])
        fresh = [m for m in mention_edges if (m[0], m[1], m[2]) not in known]
        # Aynı göç içinde tekrar eden mention'lar da tekilleştirilir.
        seen_pairs = set()
        deduped = []
        for m in fresh:
            key = (m[0], m[1], m[2])
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            deduped.append(m)
        wiki_edges = self.add_edges_bulk(deduped)

        sim_edges = 0
        if similarity_edges:
            sim_edges = self._build_similarity_edges(
                ids, embeddings, top_k=sim_top_k, threshold=sim_threshold, known=known
            )

        duration = time.time() - started
        return {
            "source_nodes": source_total,
            "migrated_nodes": len(node_payload),
            # `synced_nodes` = bu çağrıda grafa YENİ giren düğüm sayısı
            # (`migrated_nodes` ile aynı değer, uzlaştırma diliyle adlandırılmış).
            "synced_nodes": len(node_payload),
            "entity_nodes": len(entity_nodes),
            "graph_nodes": self.node_count(),
            "wikilink_edges": wiki_edges,
            "similarity_edges": sim_edges,
            "edges": wiki_edges + sim_edges,
            "edges_total": self.edge_count(),
            "duration_s": round(duration, 3),
            "backup_path": str(backup_path) if backup_path else "",
        }

    def _build_similarity_edges(
        self,
        ids: Sequence[str],
        embeddings: Sequence[Optional[List[float]]],
        top_k: int = 3,
        threshold: float = 0.80,
        known: Optional[set] = None,
    ) -> int:
        """Gömme kosinüsünden `similar_to` kenarları (numpy yoksa atlanır)."""
        if _np is None or not ids:
            return 0
        usable = [(i, e) for i, e in enumerate(embeddings) if e and len(e) == EMBEDDING_DIM]
        if len(usable) < 2:
            return 0
        idx_map = [i for i, _ in usable]
        mat = _np.asarray([e for _, e in usable], dtype=_np.float64)
        norms = _np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        mat = mat / norms
        sims = mat @ mat.T
        _np.fill_diagonal(sims, -1.0)

        known = known or set()
        rows: List[Tuple[str, str, str, float, str]] = []
        pairs: set = set()
        k = min(top_k, sims.shape[0] - 1)
        if k <= 0:
            return 0
        top = _np.argpartition(-sims, kth=k - 1, axis=1)[:, :k]
        for r in range(sims.shape[0]):
            for c in top[r]:
                score = float(sims[r, int(c)])
                if score < threshold:
                    continue
                a, b = ids[idx_map[r]], ids[idx_map[int(c)]]
                if a == b:
                    continue
                pair = tuple(sorted((a, b)))
                if pair in pairs or (pair[0], pair[1], "similar_to") in known:
                    continue
                pairs.add(pair)
                rows.append((pair[0], pair[1], "similar_to", score, "embedding_cosine"))
        return self.add_edges_bulk(rows)

    # -- yazma yolu: uzlaştırmalı ingest -----------------------------------

    def ingest_text(
        self,
        text: str,
        source_type: str = "report",
        title: str = "",
        scope: str = SCOPE_GENERAL,
        provenance: str = "",
        node_id: Optional[str] = None,
        pinned: bool = False,
        extract: bool = True,
    ) -> Dict[str, Any]:
        """
        Bir metni grafa yazar: kaynak düğüm + kural tabanlı olgular + uzlaştırma.

        Dönen sözlük: kaynak düğüm kimliği ve `created/duplicate/superseded`
        sayıları. Çelişkide eski olgu düğümü **silinmez**; ona bağlı geçerli
        kenar kapatılır ve yeni düğümden `supersedes` kenarı çekilir.
        """
        text = text or ""
        title = title or _first_line(text)
        source_id = node_id or f"{source_type}-{_slug(title or text[:60])}"
        source_node = self.upsert_node(
            source_id,
            source_type if source_type in NODE_TYPES else DEFAULT_NODE_TYPE,
            title, text, scope=scope, provenance=provenance,
            metadata={"pinned": True} if pinned else None,
            importance=USER_PIN_IMPORTANCE if pinned else None,
        )

        result = ReconcileResult()
        created_ids: List[str] = []
        if extract:
            facts = extract_facts(text, default_entity=title, provenance=provenance)
            result = self._apply_facts(facts, source_node, scope=scope, provenance=provenance,
                                       created_ids=created_ids)

        for ent in extract_entities(text):
            ent_id = f"entity-{_slug(ent)}"
            self.upsert_node(ent_id, "entity", ent, body=ent, scope=scope,
                             provenance=provenance, metadata={"source": "wikilink"},
                             mirror=False)
            if not self.get_edges(src=source_id, dst=ent_id, edge_type="member_of"):
                self.add_edge(source_id, ent_id, "member_of", weight=0.6, provenance=provenance)

        out = {"node_id": source_id, "fact_nodes": created_ids}
        out.update(result.counts)
        return out

    def _apply_facts(
        self,
        facts: Sequence[Fact],
        source_node: GraphNode,
        scope: str,
        provenance: str,
        created_ids: List[str],
    ) -> ReconcileResult:
        existing = self._existing_facts(scope=scope)
        result = reconcile_facts(facts, existing)
        now = time.time()

        def _store(fact: Fact) -> str:
            fid = f"fact-{_slug(fact.entity)}-{_slug(fact.predicate)}-{_slug(fact.value, 24)}"
            self.upsert_node(
                fid, "fact", fact.as_text(), fact.raw or fact.as_text(),
                scope=scope, provenance=fact.provenance or provenance,
                metadata={
                    "entity": fact.entity, "predicate": fact.predicate,
                    "value": fact.value, "kind": fact.kind,
                },
            )
            if not self.get_edges(src=fid, dst=source_node.id, edge_type="derived_from"):
                self.add_edge(fid, source_node.id, "derived_from", weight=1.0,
                              provenance=fact.provenance or provenance)
            created_ids.append(fid)
            return fid

        for decision in result.created:
            _store(decision.fact)

        for decision in result.duplicates:
            # Kopya: yeni düğüm açılmaz, mevcut düğümün tekrarı artar (önem yükselir).
            if decision.existing_id:
                node = self.get_node(decision.existing_id)
                if node is not None:
                    self.upsert_node(node.id, node.type, node.title, node.body,
                                     scope=node.scope, provenance=node.provenance)

        for decision in result.superseded:
            new_id = _store(decision.fact)
            old_id = decision.existing_id or ""
            if not old_id or old_id == new_id:
                continue
            # Eski olgunun geçerli kenarları kapatılır: artık "geçerli" filtresine
            # takılmaz ama kayıt ve geçmişi durur.
            for edge in self.get_edges(src=old_id, valid_only=True):
                if edge.type in ("derived_from", "member_of"):
                    self.invalidate_edge(edge.id, when=now)
            self.add_edge(new_id, old_id, "supersedes", weight=1.0, provenance=provenance)
            self.add_edge(new_id, old_id, "contradicts", weight=1.0, provenance=decision.reason)
            with self._connect() as conn:
                conn.execute(
                    "UPDATE nodes SET metadata_json = json_set(COALESCE(metadata_json,'{}'),"
                    " '$.superseded_by', ?) WHERE id = ?", (new_id, old_id),
                )
                conn.commit()
        return result

    def _existing_facts(self, scope: Optional[str] = None) -> List[ExistingFact]:
        sql = ("SELECT id, metadata_json, title, body FROM nodes WHERE type = 'fact'")
        params: List[Any] = []
        if scope:
            sql += " AND scope = ?"
            params.append(scope)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: List[ExistingFact] = []
        for nid, meta_json, title, body in rows:
            try:
                meta = json.loads(meta_json or "{}")
            except ValueError:
                meta = {}
            if not meta.get("entity"):
                continue
            out.append(ExistingFact(
                id=nid, entity=meta.get("entity", ""), predicate=meta.get("predicate", ""),
                value=meta.get("value", ""), text=body or title or "",
            ))
        return out

    def is_node_valid(self, node_id: str) -> bool:
        """Düğüm 'geçerli' mi: üstüne yazan (`supersedes`) bir düğüm yoksa evet."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM edges WHERE dst = ? AND type = 'supersedes' "
                "AND t_valid_to IS NULL LIMIT 1", (node_id,)
            ).fetchone()
        return row is None

    # -- okuma yolu: tohumlama + PPR yayılımı ------------------------------

    def graph_recall(
        self,
        query: str,
        top_k: int = 5,
        expand: bool = True,
        hops: int = 2,
        damping: float = 0.5,
        scopes: Optional[Sequence[str]] = None,
        types: Optional[Sequence[str]] = None,
        valid_only: bool = True,
        since: Optional[float] = None,
        until: Optional[float] = None,
        min_threshold: float = 0.15,
        seed_k: Optional[int] = None,
        budget_chars: Optional[int] = None,
    ) -> List[Tuple[GraphNode, float]]:
        """
        Hibrit tohumlama -> 2 adım yayılım -> filtre -> bütçe kırpma.

        `expand=False` iken sonuç **birebir** `hybrid_recall` sıralamasıdır
        (eşitlik testi bunu doğrular); yayılım yalnızca `expand=True` iken
        devreye girer ve ilişkisel sorgularda tohumda olmayan komşuları getirir.
        """
        seed_limit = seed_k or max(top_k * 4, 20)
        seeds = self.memory.hybrid_recall(query, top_k=seed_limit, min_threshold=min_threshold)
        seed_scores: Dict[str, float] = {}
        seed_order: List[str] = []
        for node, score in seeds:
            if node.id not in seed_scores:
                seed_order.append(node.id)
            seed_scores[node.id] = max(seed_scores.get(node.id, 0.0), float(score))

        if not expand:
            out: List[Tuple[GraphNode, float]] = []
            for nid in seed_order:
                node = self.get_node(nid)
                if node is None:
                    # Grafa henüz aktarılmamış eski düğüm: sözleşmeyi bozmamak
                    # için eski kaydından geçici bir graf düğümü üretilir.
                    legacy = self.memory.get_node(nid)
                    if legacy is None:
                        continue
                    node = GraphNode(
                        id=legacy.id,
                        type=CATEGORY_TO_TYPE.get(legacy.category, DEFAULT_NODE_TYPE),
                        title=_first_line(legacy.content), body=legacy.content,
                        importance=legacy.importance, created_at=legacy.created_at,
                        updated_at=legacy.last_accessed, scope=SCOPE_GENERAL,
                        metadata=legacy.metadata or {}, access_count=legacy.access_count,
                    )
                if not self._passes_filters(node, scopes, types, valid_only, since, until):
                    continue
                out.append((node, seed_scores[nid]))
                if len(out) >= top_k:
                    break
            return self._trim_to_budget(out, budget_chars)

        scores = self._personalized_pagerank(seed_scores, hops=hops, damping=damping)
        now = time.time()
        ranked: List[Tuple[GraphNode, float]] = []
        for nid, relevance in scores.items():
            node = self.get_node(nid)
            if node is None:
                continue
            if not self._passes_filters(node, scopes, types, valid_only, since, until):
                continue
            # skor = ilgi (yayılmış tohum) + önem + yenilik (Ebbinghaus)
            score = 0.55 * relevance + 0.25 * node.importance + 0.20 * node.ebbinghaus(now)
            ranked.append((node, score))
        ranked.sort(key=lambda p: (-p[1], p[0].id))
        return self._trim_to_budget(ranked[:top_k], budget_chars)

    def _passes_filters(
        self,
        node: GraphNode,
        scopes: Optional[Sequence[str]],
        types: Optional[Sequence[str]],
        valid_only: bool,
        since: Optional[float],
        until: Optional[float],
    ) -> bool:
        if scopes is not None and node.scope not in set(scopes):
            return False
        if types is not None and node.type not in set(types):
            return False
        if since is not None and (node.created_at or 0.0) < since:
            return False
        if until is not None and (node.created_at or 0.0) > until:
            return False
        if valid_only and not self.is_node_valid(node.id):
            return False
        return True

    def _adjacency(self, valid_only: bool = True) -> Dict[str, List[Tuple[str, float]]]:
        adj: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        for edge in self.get_edges(valid_only=valid_only):
            if edge.type in ("contradicts",):
                continue  # çelişki kenarı bilgi taşımaz, yayılım yolu değildir
            w = max(0.0, float(edge.weight or 1.0))
            adj[edge.src].append((edge.dst, w))
            adj[edge.dst].append((edge.src, w * 0.8))  # geri yön biraz zayıf
        return adj

    def _personalized_pagerank(
        self,
        seeds: Dict[str, float],
        hops: int = 2,
        damping: float = 0.5,
    ) -> Dict[str, float]:
        """
        Tohumlu PageRank (HippoRAG 2 tarzı), `hops` kadar güç yinelemesi.

        numpy varsa yoğun vektörle, yoksa aynı sonucu veren sözlük döngüsüyle
        hesaplanır; graf boyutu (birkaç bin düğüm) her iki yol için de küçüktür.
        """
        if not seeds:
            return {}
        total = sum(seeds.values()) or 1.0
        personal = {k: v / total for k, v in seeds.items()}
        scores = dict(personal)
        adj = self._adjacency(valid_only=True)
        for _ in range(max(0, hops)):
            nxt: Dict[str, float] = defaultdict(float)
            for nid, val in scores.items():
                if val <= 0.0:
                    continue
                neighbours = adj.get(nid) or []
                wsum = sum(w for _, w in neighbours)
                if wsum <= 0.0:
                    nxt[nid] += val
                    continue
                for dst, w in neighbours:
                    nxt[dst] += damping * val * (w / wsum)
                nxt[nid] += (1.0 - damping) * val
            for nid, val in personal.items():
                nxt[nid] += 0.15 * val
            scores = dict(nxt)
        mx = max(scores.values()) if scores else 0.0
        if mx > 0:
            scores = {k: v / mx for k, v in scores.items()}
        return scores

    @staticmethod
    def _trim_to_budget(
        items: List[Tuple[GraphNode, float]],
        budget_chars: Optional[int],
    ) -> List[Tuple[GraphNode, float]]:
        if not budget_chars or budget_chars <= 0:
            return items
        out, used = [], 0
        for node, score in items:
            cost = len(node.body or node.title or "")
            if out and used + cost > budget_chars:
                break
            out.append((node, score))
            used += cost
        return out

    # -- 5.2: Desk belleğinin katılması ------------------------------------

    def ingest_desk_memory(
        self,
        vault_path: Optional[Path] = None,
        max_chars: int = 8000,
    ) -> Dict[str, Any]:
        """
        `Offices/*/MEMORY.md` ve `Agents/*/MEMORY.md` dosyalarını aynı grafa
        kapsam alt-grafı olarak alır. Ayrı depo yoktur.

        Her ofis/ajan için bir kapsam düğümü (`office` / `agent`) açılır; o
        dosyadan çıkan bütün olgular `scope="office:<ad>"` ile yazılır ve
        `member_of` kenarıyla kapsam düğümüne bağlanır. Sorguda kapsam filtresi
        kullanıldığında başka ofisin notu sızmaz.
        """
        root = self._vault_entropy_dir(vault_path)
        stats = {"offices": 0, "agents": 0, "nodes": 0, "facts": 0, "skipped": 0}
        if root is None or not root.exists():
            return stats

        for kind, folder, node_type in (
            ("office", "Offices", "office"),
            ("agent", "Agents", "agent"),
        ):
            base = root / folder
            if not base.is_dir():
                continue
            for memory_file in sorted(base.glob("*/MEMORY.md")):
                name = memory_file.parent.name
                try:
                    text = memory_file.read_text(encoding="utf-8", errors="ignore")[:max_chars]
                except OSError:
                    stats["skipped"] += 1
                    continue
                scope = f"{kind}:{name}"
                scope_id = f"{node_type}-{_slug(name)}"
                self.upsert_node(scope_id, node_type, name, body=f"{kind}: {name}",
                                 scope=scope, provenance=str(memory_file))
                res = self.ingest_text(
                    text, source_type="report", title=f"{name} belleği",
                    scope=scope, provenance=str(memory_file),
                    node_id=f"report-{kind}-{_slug(name)}-memory",
                )
                if not self.get_edges(src=res["node_id"], dst=scope_id, edge_type="member_of"):
                    self.add_edge(res["node_id"], scope_id, "member_of", provenance=str(memory_file))
                for fid in res.get("fact_nodes", []):
                    if not self.get_edges(src=fid, dst=scope_id, edge_type="member_of"):
                        self.add_edge(fid, scope_id, "member_of", provenance=str(memory_file))
                stats[kind + "s"] += 1
                stats["nodes"] += 1
                stats["facts"] += len(res.get("fact_nodes", []))
        return stats

    @staticmethod
    def _vault_entropy_dir(vault_path: Optional[Path]) -> Optional[Path]:
        if vault_path is not None:
            p = Path(vault_path)
            return p if p.name == "Entropy" else p / "Entropy"
        try:
            from entropy.brain.obsidian.vault_manager import ObsidianVaultManager

            return Path(ObsidianVaultManager().entropy_dir)
        except Exception:
            return None

    @staticmethod
    def default_scopes(
        active_office: Optional[str] = None,
        vault_path: Optional[Path] = None,
        include_desk: bool = True,
    ) -> List[str]:
        """
        Sorgu için varsayılan kapsamlar: genel + aktif ofis + tüm Desk ofisleri.

        Desk kapsamları (`desk:<ofis>`) Entropy'nin geri çağırmasında **salt
        okunur** görünür: ofis projeleri Entropy'nin belleğine akar, ters yön
        yoktur (bkz. entropy.brain.office_graph).
        """
        scopes = [SCOPE_GENERAL]
        if active_office:
            scopes.append(f"office:{active_office}")
        if include_desk:
            try:
                from entropy.brain.office_graph import desk_scopes

                scopes.extend(s for s in desk_scopes(vault_path) if s not in scopes)
            except Exception:  # pragma: no cover - kasa yoksa sessiz geç
                pass
        return scopes

    # -- 5.2: konsolidasyon (topluluk + yansıma) ---------------------------

    def consolidate(
        self,
        min_community_size: int = 3,
        reflection_window: int = 10,
        max_reflections: int = 20,
    ) -> Dict[str, Any]:
        """
        Arka plan konsolidasyonu (LLM'siz, kota harcamaz).

        1) `similar_to` kenarları üzerinde etiket yayılımı -> `community`
           düğümleri + üyelerden `member_of` kenarları.
        2) Her `reflection_window` olaydan bir yansıma düğümü: en sık geçen
           varlık/terimlerin özeti, olaylara `derived_from` ile bağlı.
        """
        started = time.time()
        communities = self._label_propagation(min_size=min_community_size)
        reflections = self._build_reflections(window=reflection_window, limit=max_reflections)
        return {
            "communities": len(communities),
            "reflections": len(reflections),
            "community_ids": [c.id for c in communities],
            "reflection_ids": reflections,
            "duration_s": round(time.time() - started, 3),
        }

    def _label_propagation(self, min_size: int = 3, iterations: int = 5) -> List[Community]:
        edges = [e for e in self.get_edges(edge_type="similar_to", valid_only=True)]
        if not edges:
            return []
        adj: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        for e in edges:
            adj[e.src].append((e.dst, float(e.weight or 1.0)))
            adj[e.dst].append((e.src, float(e.weight or 1.0)))
        labels = {nid: nid for nid in adj}
        for _ in range(iterations):
            changed = False
            for nid in sorted(adj):
                weights: Dict[str, float] = defaultdict(float)
                for dst, w in adj[nid]:
                    weights[labels.get(dst, dst)] += w
                if not weights:
                    continue
                best = max(sorted(weights), key=lambda k: weights[k])
                if best != labels[nid]:
                    labels[nid] = best
                    changed = True
            if not changed:
                break

        groups: Dict[str, List[str]] = defaultdict(list)
        for nid, label in labels.items():
            groups[label].append(nid)

        out: List[Community] = []
        for label, members in groups.items():
            if len(members) < min_size:
                continue
            cid = f"community-{_slug(label, 40)}"
            texts = []
            for m in members[:20]:
                node = self.get_node(m)
                if node is not None:
                    texts.append(node.title or node.body[:100])
            terms = Counter()
            for t in texts:
                for tok in normalize_text(t).split():
                    if len(tok) > 3:
                        terms[tok] += 1
            top_terms = [w for w, _ in terms.most_common(5)]
            comm_label = " / ".join(top_terms[:3]) or label
            summary = (
                f"{len(members)} düğümlük küme. Öne çıkan terimler: "
                f"{', '.join(top_terms) or '-'}."
            )
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO communities (id, label, summary, member_count) VALUES (?,?,?,?)"
                    " ON CONFLICT(id) DO UPDATE SET label=excluded.label,"
                    " summary=excluded.summary, member_count=excluded.member_count",
                    (cid, comm_label, summary, len(members)),
                )
                conn.commit()
            self.upsert_node(cid, "community", comm_label, summary,
                             provenance="consolidate:label_propagation",
                             metadata={"members": len(members)})
            existing_members = {e.src for e in self.get_edges(dst=cid, edge_type="member_of")}
            rows = [(m, cid, "member_of", 1.0, "consolidate") for m in members
                    if m not in existing_members]
            self.add_edges_bulk(rows)
            out.append(Community(cid, comm_label, summary, len(members)))
        return out

    def _build_reflections(self, window: int = 10, limit: int = 20) -> List[str]:
        episodes = sorted(
            self.all_nodes(types=["episode"]), key=lambda n: n.created_at or 0.0
        )
        made: List[str] = []
        for start in range(0, len(episodes) - window + 1, window):
            if len(made) >= limit:
                break
            chunk = episodes[start:start + window]
            terms = Counter()
            entities = Counter()
            for node in chunk:
                for ent in extract_entities(node.body or ""):
                    entities[ent] += 1
                for tok in normalize_text(node.title or node.body or "").split():
                    if len(tok) > 4:
                        terms[tok] += 1
            top_entities = [e for e, _ in entities.most_common(3)]
            top_terms = [t for t, _ in terms.most_common(5)]
            signature = "-".join(top_entities or top_terms)[:60] or f"win{start}"
            rid = f"fact-reflection-{_slug(signature)}-{start // window}"
            summary = (
                f"Yansıma ({len(chunk)} olay): en sık varlıklar "
                f"{', '.join(top_entities) or '-'}; öne çıkan terimler "
                f"{', '.join(top_terms) or '-'}."
            )
            self.upsert_node(rid, "fact", summary[:120], summary,
                             importance=compute_importance("fact", repeat_count=len(chunk)),
                             provenance="consolidate:reflection",
                             metadata={"source": "reflection", "episodes": len(chunk)})
            existing = {e.dst for e in self.get_edges(src=rid, edge_type="derived_from")}
            rows = [(rid, node.id, "derived_from", 1.0, "consolidate:reflection")
                    for node in chunk if node.id not in existing]
            self.add_edges_bulk(rows)
            made.append(rid)
        return made

    def list_communities(self) -> List[Community]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, label, summary, member_count FROM communities"
            ).fetchall()
        return [Community(r[0], r[1] or "", r[2] or "", int(r[3] or 0)) for r in rows]

    # -- görselleştirme verisi ---------------------------------------------

    def graph_view_data(
        self,
        scopes: Optional[Sequence[str]] = None,
        valid_only: bool = False,
        max_nodes: int = 2000,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        UI için düğüm/kenar verisi.

        Düğüm alanları: `id, name, group, type, importance, scope,
        t_valid_from, t_valid_to, member_count`. Kenar alanları:
        `source, target, type, weight, t_valid_from, t_valid_to`.
        Zaman kaydırıcısı `t_valid_from/to`, filtreler `type`/`importance`
        alanlarını kullanır.
        """
        nodes_out: List[Dict[str, Any]] = []
        comms = {c.id: c for c in self.list_communities()}
        for node in self.all_nodes(scopes=scopes)[:max_nodes]:
            valid = self.is_node_valid(node.id)
            if valid_only and not valid:
                continue
            nodes_out.append({
                "id": node.id,
                "name": node.title or node.id,
                "group": node.type,
                "type": node.type,
                "importance": round(float(node.importance), 4),
                "scope": node.scope,
                "t_valid_from": node.created_at,
                "t_valid_to": None if valid else node.updated_at,
                "member_count": comms[node.id].member_count if node.id in comms else 0,
                "path": node.provenance,
            })
        ids = {n["id"] for n in nodes_out}
        links_out = []
        for edge in self.get_edges(valid_only=valid_only):
            if edge.src not in ids or edge.dst not in ids:
                continue
            links_out.append({
                "source": edge.src,
                "target": edge.dst,
                "type": edge.type,
                "alias": edge.type,
                "weight": edge.weight,
                "t_valid_from": edge.t_valid_from,
                "t_valid_to": edge.t_valid_to,
                "is_catalog_link": False,
            })
        return {"nodes": nodes_out, "links": links_out}


__all__ = [
    "GraphStore", "GraphNode", "GraphEdge", "Community",
    "NODE_TYPES", "EDGE_TYPES", "CATEGORY_TO_TYPE", "SOURCE_IMPORTANCE",
    "SCOPE_GENERAL", "compute_importance",
]
