"""
Faz 5.1 / 5.2 — birleşik graf şeması, uzlaştırma, PPR geri çağırma testleri.

Hepsi tmp DB / tmp kasa üzerinde çalışır. Gerçek `cognitive_memory.db` ve
gerçek Obsidian kasası bu dosyada YALNIZCA okunur; göç ölçümü ayrı bir betikte
gerçek DB'nin kopyası üzerinde yapılır (bkz. rapor).
"""

import json
import sqlite3
import time

import pytest

from entropy.brain.graph_store import (
    EDGE_TYPES,
    NODE_TYPES,
    SCOPE_GENERAL,
    GraphStore,
    compute_importance,
)
from entropy.brain.obsidian.vault_manager import ObsidianVaultManager
from entropy.brain.reconcile import (
    ExistingFact,
    extract_entities,
    extract_facts,
    normalize_text,
    reconcile_facts,
)
from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem


@pytest.fixture
def store(tmp_path):
    mem = CognitiveMemorySystem(db_path=tmp_path / "graph.db")
    return GraphStore(memory=mem)


# --- şema ------------------------------------------------------------------

def test_schema_tables_and_columns(store):
    with sqlite3.connect(store.db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        node_cols = {r[1] for r in conn.execute("PRAGMA table_info(nodes)")}
        edge_cols = {r[1] for r in conn.execute("PRAGMA table_info(edges)")}
        comm_cols = {r[1] for r in conn.execute("PRAGMA table_info(communities)")}

    assert {"nodes", "edges", "communities", "cognitive_nodes"} <= tables
    assert {"id", "type", "title", "body", "importance",
            "created_at", "updated_at", "scope"} <= node_cols
    assert {"src", "dst", "type", "t_valid_from", "t_valid_to",
            "ingested_at", "weight", "provenance"} <= edge_cols
    assert {"id", "label", "summary", "member_count"} <= comm_cols
    assert set(NODE_TYPES) == {
        "episode", "fact", "entity", "procedure", "agent",
        "office", "task", "report", "session", "community"}
    assert set(EDGE_TYPES) == {
        "derived_from", "contradicts", "supersedes", "triggered",
        "produced", "member_of", "similar_to"}


def test_importance_source_type_and_repetition():
    assert compute_importance("report") == pytest.approx(0.6)
    assert compute_importance("session") == pytest.approx(0.4)
    assert compute_importance("fact") == pytest.approx(0.5)
    assert compute_importance("fact", pinned=True) == 1.0
    # Tekrar sayısı önemi artırır ama 1.0'ı geçmez.
    assert compute_importance("fact", repeat_count=10) > compute_importance("fact")
    assert compute_importance("report", repeat_count=10_000) <= 1.0


def test_provenance_records_source_path(store):
    out = store.ingest_text("Sürüm: 0.2.1", source_type="report", title="Yayın notu",
                            provenance="C:/kasa/Reports/yayin.md")
    node = store.get_node(out["node_id"])
    assert node is not None and node.provenance.endswith("yayin.md")
    facts = [n for n in store.all_nodes(types=["fact"])]
    assert facts and any(":" in f.provenance for f in facts), "satır numarası provenansta"


# --- göç -------------------------------------------------------------------

def test_migration_is_lossless_and_reversible(tmp_path):
    mem = CognitiveMemorySystem(db_path=tmp_path / "legacy.db")
    mem.record_memory("episodic", "Kullanıcı [[CanivoPets]] için rapor istedi", importance=0.5)
    mem.record_memory("semantic", "Finansal analiz bilanço gerektirir", importance=0.7)
    mem.record_memory("procedural", "Önce araştırma raporu okunur", importance=0.6)
    mem.record_memory("architecture", "Bellek katmanı SQLite üzerinde çalışır", importance=0.6)
    legacy_ids = {n.id for n in mem.get_all_nodes()}

    store = GraphStore(memory=mem)
    stats = store.migrate_from_cognitive_nodes()

    assert stats["source_nodes"] == len(legacy_ids)
    graph_ids = {n.id for n in store.all_nodes()}
    assert legacy_ids <= graph_ids, "hiçbir eski düğüm kaybolmamalı"
    # category -> type eşlemesi
    types = {n.id: n.type for n in store.all_nodes()}
    assert types[mem._generate_node_id("episodic", "Kullanıcı [[CanivoPets]] için rapor istedi")] == "episode"
    assert types[mem._generate_node_id("semantic", "Finansal analiz bilanço gerektirir")] == "fact"
    assert types[mem._generate_node_id("procedural", "Önce araştırma raporu okunur")] == "procedure"
    # bilinmeyen kategori fact'e düşer ama özgün kategori saklanır
    # Faz 11.1: "architecture" kanonik bir kategori değil; yazma anında
    # `semantic`e eşlenir (düğüm kimliği de ona göre kurulur), ham değer
    # metadata'da izlenebilir kalır.
    arch = store.get_node(mem._generate_node_id("semantic", "Bellek katmanı SQLite üzerinde çalışır"))
    assert arch.type == "fact" and arch.metadata["legacy_category"] == "architecture"
    # wikilink -> entity düğümü + kenar
    assert store.get_node("entity-canivopets") is not None
    assert store.get_edges(dst="entity-canivopets", edge_type="member_of")
    # eski tablo ve eski API'ler bozulmamalı
    assert len(mem.get_all_nodes()) == len(legacy_ids)
    assert mem.get_node("ego-entropy-core") is not None

    # yedek + geri dönüş
    backup = stats["backup_path"]
    assert backup
    assert store.restore_database(backup) is True
    with sqlite3.connect(store.db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "cognitive_nodes" in tables


def test_migration_is_idempotent(store):
    store.memory.record_memory("semantic", "Tekrar eden göç [[Entropy]] düğümü", importance=0.6)
    first = store.migrate_from_cognitive_nodes(backup=False)
    second = store.migrate_from_cognitive_nodes(backup=False)
    assert second["migrated_nodes"] == 0
    assert second["wikilink_edges"] == 0
    assert first["graph_nodes"] == second["graph_nodes"]


# --- uzlaştırma ------------------------------------------------------------

def test_fact_extraction_rules():
    text = (
        "# Yayın raporu\n"
        "[[Entropy]] sürüm: 0.2.1\n"
        "Tarih: 2026-09-10\n"
        "Ekip kart başına 3 gün harcadı.\n"
    )
    facts = extract_facts(text, default_entity="Yayın raporu", provenance="rapor.md")
    keys = {(normalize_text(f.entity), normalize_text(f.predicate)) for f in facts}
    assert ("entropy", "entropy sürüm") in keys or ("entropy", "sürüm") in keys
    assert any(f.kind == "date" or "2026-09-10" in f.value for f in facts)
    assert any(f.kind == "numeric" for f in facts)
    assert all(f.provenance.startswith("rapor.md:") for f in facts)
    assert extract_entities("bkz [[Alfa]] ve [[Beta|beta]] ve [[Alfa]]") == ["Alfa", "Beta"]


def test_reconcile_duplicate_and_contradiction():
    facts = extract_facts("[[Proje]] durum: tamamlandı", default_entity="X")
    existing_same = [ExistingFact("fact-1", "Proje", facts[0].predicate, "tamamlandı", "durum tamamlandı")]
    res = reconcile_facts(facts, existing_same)
    assert res.counts["duplicate"] == 1 and res.counts["created"] == 0

    existing_diff = [ExistingFact("fact-1", "Proje", facts[0].predicate, "beklemede", "durum beklemede")]
    res2 = reconcile_facts(facts, existing_diff)
    assert res2.counts["superseded"] == 1
    assert res2.superseded[0].existing_id == "fact-1"


def test_duplicate_ingest_does_not_create_second_node(store):
    store.ingest_text("[[Proje]] durum: tamamlandı", title="R1", provenance="a.md")
    before = len(store.all_nodes(types=["fact"]))
    out = store.ingest_text("[[Proje]] durum: tamamlandı", title="R2", provenance="b.md")
    assert out["duplicate"] >= 1
    assert len(store.all_nodes(types=["fact"])) == before


def test_contradiction_invalidates_old_edge_and_adds_supersedes(store):
    first = store.ingest_text("[[Proje]] durum: beklemede", title="R1", provenance="a.md")
    old_fact = first["fact_nodes"][0]
    old_edges = store.get_edges(src=old_fact, valid_only=True)
    assert old_edges, "yeni olgunun geçerli kenarı olmalı"

    second = store.ingest_text("[[Proje]] durum: tamamlandı", title="R2", provenance="b.md")
    assert second["superseded"] >= 1
    new_fact = [f for f in second["fact_nodes"] if f != old_fact][0]

    # Eski düğüm SİLİNMEZ, kenarı kapatılır.
    assert store.get_node(old_fact) is not None
    assert all(e.t_valid_to is not None
               for e in store.get_edges(src=old_fact, edge_type="derived_from"))
    sup = store.get_edges(src=new_fact, dst=old_fact, edge_type="supersedes")
    assert sup and sup[0].t_valid_to is None
    assert store.get_edges(src=new_fact, dst=old_fact, edge_type="contradicts")
    assert store.is_node_valid(old_fact) is False
    assert store.is_node_valid(new_fact) is True


def test_valid_only_filter_hides_superseded_node(store):
    store.ingest_text("[[Sunucu]] port: 8080", title="Eski yapılandırma", provenance="a.md")
    store.ingest_text("[[Sunucu]] port: 9090", title="Yeni yapılandırma", provenance="b.md")

    valid = store.graph_recall("Sunucu port", top_k=10, valid_only=True, types=["fact"])
    invalid_included = store.graph_recall("Sunucu port", top_k=10, valid_only=False, types=["fact"])
    valid_values = {n.metadata.get("value") for n, _ in valid}
    all_values = {n.metadata.get("value") for n, _ in invalid_included}
    assert "8080" not in valid_values
    assert "8080" in all_values and "9090" in all_values


# --- geri çağırma: eşitlik ve kazanç ---------------------------------------

QUERIES = [
    "bellek grafiği", "rapor triyajı", "obsidian kasası", "finansal analiz",
    "bilanço okuma", "medya ajansı", "canivopets büyüme", "ajan orkestrasyonu",
    "posta kutusu", "terminal olay", "gömme modeli", "türkçe sorgu",
    "vektör benzerliği", "ebbinghaus unutma", "konsolidasyon rüya",
    "yetenek playbook", "damıtma zinciri", "bağlam bütçesi", "PPR yayılımı",
    "çift zamanlı kenar", "kapsam sızıntısı", "topluluk özeti",
    "yansıma düğümü", "sqlite şema göçü", "kullanıcı sabitlemesi",
]


@pytest.fixture
def seeded_store(tmp_path):
    mem = CognitiveMemorySystem(db_path=tmp_path / "seed.db")
    corpus = [
        ("semantic", "Bellek grafiği çift zamanlı kenarlarla çalışır [[Graf]]"),
        ("semantic", "Rapor triyajı güven eşiğiyle yapılır [[Rapor]]"),
        ("semantic", "Obsidian kasası OneDrive üzerindedir [[Kasa]]"),
        ("semantic", "Finansal analiz bilanço ve gelir tablosu ister [[Finans]]"),
        ("episodic", "Kullanıcı canivopets büyüme raporu istedi [[CanivoPets]]"),
        ("procedural", "Ajan orkestrasyonu posta kutusu üzerinden yürür [[Ofis]]"),
        ("semantic", "Gömme modeli çok dilli MiniLM'dir [[Gomme]]"),
        ("semantic", "Ebbinghaus unutma eğrisi geri çağırmada 0.25 ağırlıklıdır"),
        ("semantic", "Konsolidasyon rüya döngüsünde arka planda koşar"),
        ("procedural", "Yetenek playbook damıtma zincirinden üretilir [[Playbook]]"),
        ("semantic", "Bağlam bütçesi 4000 token ile sınırlıdır"),
        ("semantic", "PPR yayılımı tohumlardan iki adım gider [[Graf]]"),
    ]
    for cat, text in corpus:
        mem.record_memory(cat, text, importance=0.6)
    store = GraphStore(memory=mem)
    store.migrate_from_cognitive_nodes(backup=False, sim_threshold=0.75)
    return store


def test_recall_parity_with_hybrid_when_expansion_off(seeded_store):
    mismatches = []
    for query in QUERIES:
        baseline = seeded_store.memory.hybrid_recall(query, top_k=5)
        graph = seeded_store.graph_recall(query, top_k=5, expand=False, valid_only=False)
        base_ids = [n.id for n, _ in baseline]
        graph_ids = [n.id for n, _ in graph]
        # Skorlar zaman bağımlıdır (tazelik/Ebbinghaus iki çağrı arasında
        # mikrosaniye kayar); sıralama ve skor değeri toleransla karşılaştırılır.
        scores_equal = len(baseline) == len(graph) and all(
            abs(a - b) < 1e-6 for (_, a), (_, b) in zip(baseline, graph)
        )
        if base_ids != graph_ids or not scores_equal:
            mismatches.append((query, base_ids, graph_ids))
    assert not mismatches, f"yayılım kapalıyken eski sıralama birebir korunmalı: {mismatches}"


def test_expansion_brings_related_nodes(seeded_store):
    """İlişkisel sorgular: yayılım tohumda olmayan komşuları getirmeli."""
    relational = [
        "bellek grafiği", "PPR yayılımı", "obsidian kasası",
        "ajan orkestrasyonu", "yetenek playbook",
    ]
    gains = {}
    for query in relational:
        base = {n.id for n, _ in seeded_store.graph_recall(query, top_k=5, expand=False, valid_only=False)}
        expanded = {n.id for n, _ in seeded_store.graph_recall(query, top_k=5, expand=True, valid_only=False)}
        gains[query] = len(expanded - base)
    assert sum(gains.values()) > 0, f"hiçbir sorguda yeni komşu gelmedi: {gains}"


def test_budget_trimming(seeded_store):
    full = seeded_store.graph_recall("bellek grafiği", top_k=8, expand=True, valid_only=False)
    trimmed = seeded_store.graph_recall("bellek grafiği", top_k=8, expand=True,
                                        valid_only=False, budget_chars=60)
    assert len(trimmed) <= len(full)
    assert len(trimmed) >= 1, "bütçe küçük olsa da en az bir sonuç dönmeli"


def test_type_and_time_filters(seeded_store):
    only_procedures = seeded_store.graph_recall("playbook", top_k=10, types=["procedure"],
                                                valid_only=False)
    assert all(n.type == "procedure" for n, _ in only_procedures)
    future = seeded_store.graph_recall("playbook", top_k=10, since=time.time() + 3600,
                                       valid_only=False)
    assert future == []


# --- 5.2: kapsam, Desk belleği, konsolidasyon ------------------------------

def _write_desk_vault(tmp_path):
    root = tmp_path / "Vault" / "Entropy"
    (root / "Offices" / "medya").mkdir(parents=True)
    (root / "Offices" / "finans").mkdir(parents=True)
    (root / "Agents" / "arastirmaci").mkdir(parents=True)
    (root / "Offices" / "medya" / "MEMORY.md").write_text(
        "# Medya ofisi\n[[Medya]] gizli anahtar: kırmızı-balon\nMüşteri: CanivoPets\n",
        encoding="utf-8")
    (root / "Offices" / "finans" / "MEMORY.md").write_text(
        "# Finans ofisi\n[[Finans]] gizli anahtar: mavi-kule\nMüşteri: ATATP\n",
        encoding="utf-8")
    (root / "Agents" / "arastirmaci" / "MEMORY.md").write_text(
        "# Araştırmacı\nRol: kaynak taraması\n", encoding="utf-8")
    return root


def test_desk_memory_ingest_creates_scoped_subgraph(store, tmp_path):
    root = _write_desk_vault(tmp_path)
    stats = store.ingest_desk_memory(vault_path=root)
    assert stats["offices"] == 2 and stats["agents"] == 1
    assert stats["facts"] > 0

    office = store.get_node("office-medya")
    assert office is not None and office.type == "office" and office.scope == "office:medya"
    scoped = store.all_nodes(scopes=["office:medya"])
    assert any(n.type == "fact" for n in scoped)
    # Kapsam düğümüne member_of ile bağlı alt-graf
    members = store.get_edges(dst="office-medya", edge_type="member_of")
    assert len(members) >= 2


def test_scope_filter_prevents_cross_office_leak(store, tmp_path):
    root = _write_desk_vault(tmp_path)
    store.ingest_desk_memory(vault_path=root)

    # vault_path zorunlu: verilmezse desk_scopes() KULLANICININ gerçek kasasını
    # okur ve test ortama bağımlı hâle gelir (desk:* sızıntısı).
    scopes = store.default_scopes(active_office="medya", vault_path=root)
    assert scopes == ["general", "office:medya"]
    results = store.graph_recall("gizli anahtar", top_k=10, scopes=scopes, valid_only=False)
    bodies = " ".join(n.body for n, _ in results)
    assert "mavi-kule" not in bodies, "başka ofisin notu sızdı"
    assert all(n.scope in set(scopes) for n, _ in results)

    # Kapsam verilmezse (yönetici görünümü) her ikisi de görünebilir.
    everything = store.graph_recall("gizli anahtar", top_k=10, valid_only=False)
    assert any(n.scope == "office:finans" for n, _ in everything)


def test_consolidation_creates_communities_and_reflections(seeded_store):
    for i in range(12):
        seeded_store.upsert_node(
            f"episode-test-{i:02d}", "episode", f"Olay {i}",
            body=f"Kullanıcı [[CanivoPets]] için rapor {i} istedi", created_at=time.time() + i,
        )
    out = seeded_store.consolidate(min_community_size=2, reflection_window=10)
    assert out["reflections"] >= 1
    reflection = seeded_store.get_node(out["reflection_ids"][0])
    assert reflection is not None and "Yansıma" in reflection.body
    assert "CanivoPets" in reflection.body
    assert len(seeded_store.get_edges(src=reflection.id, edge_type="derived_from")) == 10
    assert out["duration_s"] >= 0.0

    if out["communities"]:
        comm = seeded_store.list_communities()[0]
        assert comm.member_count >= 2 and comm.summary
        node = seeded_store.get_node(comm.id)
        assert node is not None and node.type == "community"


def test_consolidation_is_idempotent(seeded_store):
    first = seeded_store.consolidate(min_community_size=2)
    before_edges = seeded_store.edge_count()
    second = seeded_store.consolidate(min_community_size=2)
    assert second["communities"] == first["communities"]
    assert seeded_store.edge_count() == before_edges, "aynı kenarlar tekrar yazılmamalı"


# --- görselleştirme verisi -------------------------------------------------

def test_graph_view_data_fields(seeded_store):
    seeded_store.consolidate(min_community_size=2)
    data = seeded_store.graph_view_data()
    assert data["nodes"]
    for node in data["nodes"][:20]:
        assert {"id", "name", "group", "type", "importance", "scope",
                "t_valid_from", "t_valid_to"} <= set(node)
        assert node["type"] in NODE_TYPES
    for link in data["links"][:20]:
        assert {"source", "target", "type", "weight",
                "t_valid_from", "t_valid_to"} <= set(link)
        assert link["type"] in EDGE_TYPES


def test_vault_graph_nodes_carry_new_fields(tmp_path):
    vault = ObsidianVaultManager(vault_path=tmp_path / "Vault")
    vault.save_research_report(title="Graf Raporu", content="[[Obsidian]] bağlantısı", tags=["x"])
    graph = vault.build_knowledge_graph()
    assert graph["nodes"]
    for node in graph["nodes"]:
        assert {"type", "importance", "t_valid_from", "t_valid_to"} <= set(node)
        assert node["t_valid_to"] is None
        assert 0.0 <= node["importance"] <= 1.0


def test_vault_graph_with_communities(tmp_path):
    vault = ObsidianVaultManager(vault_path=tmp_path / "Vault2")
    vault.save_research_report(title="Rapor A", content="[[Konu]]", tags=[])
    mem = CognitiveMemorySystem(db_path=tmp_path / "view.db")
    store = GraphStore(memory=mem)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("INSERT INTO communities (id, label, summary, member_count)"
                     " VALUES ('community-x', 'graf / bellek', 'ozet', 4)")
        conn.commit()
    store.upsert_node("community-x", "community", "graf / bellek", "ozet")

    merged = vault.build_graph_with_communities(graph_store=store)
    comm = [n for n in merged["nodes"] if n["id"] == "community-x"]
    assert comm and comm[0]["type"] == "community" and comm[0]["member_count"] == 4
    assert vault.build_graph_with_communities()["nodes"], "graph_store olmadan da çalışır"


# --- rüya döngüsü -> graf konsolidasyonu bağlaması (Faz 5.7 QA) -------------

def test_dream_and_consolidate_triggers_graph_consolidation(tmp_path, monkeypatch):
    """`dream_and_consolidate` graf katmanının `consolidate()`ını çağırmalı."""
    mem = CognitiveMemorySystem(db_path=tmp_path / "dream.db")
    for i in range(3):
        mem.record_memory(
            category="episodic",
            content=f"Kullanici graf katmani hakkinda soru sordu ({i}).",
            importance=0.7,
        )

    calls = []
    real_consolidate = GraphStore.consolidate

    def spy(self, *a, **kw):
        calls.append(str(self.db_path))
        return real_consolidate(self, *a, **kw)

    monkeypatch.setattr(GraphStore, "consolidate", spy)
    mem.dream_and_consolidate()

    assert len(calls) == 1, "graf konsolidasyonu tam bir kez cagrilmali"
    assert calls[0] == str(mem.db_path), "ayni SQLite dosyasi kullanilmali"


def test_dream_and_consolidate_survives_graph_failure(tmp_path, monkeypatch):
    """Graf konsolidasyonu patlarsa rüya döngüsü yine de sonuç döndürmeli."""
    mem = CognitiveMemorySystem(db_path=tmp_path / "dream_fail.db")
    for i in range(3):
        mem.record_memory(
            category="episodic",
            content=f"Bolumsel ani {i}: hata dayanikliligi testi.",
            importance=0.7,
        )

    def boom(self, *a, **kw):
        raise RuntimeError("graf katmani bilerek patlatildi")

    monkeypatch.setattr(GraphStore, "consolidate", boom)
    out = mem.dream_and_consolidate()
    assert isinstance(out, list)
