"""
Bellek katmanındaki performans önbelleklerinin davranış eşitliği.

Bu dosyanın tek işi hız değişikliklerinin **sonucu değiştirmediğini** kanıtlamak:
hibrit geri çağırmanın vektörleştirilmiş yolu eski satır satır taramayla aynı
sıralamayı üretmeli, playbook parmak izi ve kasa grafiği önbellekten okunduğunda
diskten okunanla birebir aynı olmalı. Hız ölçümü burada değil, perf_bench'te.
"""

import json
import time

import pytest

from entropy.memory.obsidian import vault_manager as vault_module
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.memory.playbook import PlaybookStore, SkillReportIndex, clear_file_facts_cache
from entropy.memory.supabase.cognitive_memory import (
    CognitiveMemorySystem,
    LocalEmbeddingEngine,
    embedding_warmup_enabled,
    warm_embedding_engine,
)

# Farklı konulara dayanan sorgular: her biri en fazla 5 sonuç döner (5x5 = 25 çift).
RECALL_QUERIES = [
    "finansal denetim raporunda borçluluk oranı",
    "bilgi grafiği düğüm yerleşimi ve fizik döngüsü",
    "otonom görev zamanlayıcı hata ayıklama",
    "obsidian kasası bellek senkronizasyonu",
    "token bütçesi ve bağlam kurucu",
]

SEED_MEMORIES = [
    ("semantic", "Finansal denetimde borçluluk oranı ve nakit akışı riski birlikte okunur", 0.9),
    ("semantic", "Bilgi grafiği düğümleri dallara göre yelpaze biçiminde yerleştirilir", 0.8),
    ("episodic", "Otonom görev zamanlayıcı arka planda çalışırken arayüz donuyordu", 0.7),
    ("procedural", "Obsidian kasası ile bellek senkronizasyonu rapor yazımından sonra yapılır", 0.6),
    ("semantic", "Bağlam kurucu token bütçesini bölümlere göre paylaştırır", 0.85),
    ("episodic", "Bilgi grafiği fizik döngüsü kare başına on binlerce çift hesaplıyordu", 0.5),
    ("semantic", "Nakit akışı tablosu işletme faaliyetlerinden başlar", 0.4),
    ("procedural", "Rapor damıtma yalnızca işlenmemiş kaynakları okur", 0.65),
    ("episodic", "Kasa taraması OneDrive üzerinde yavaş çalışıyor", 0.55),
    ("semantic", "Gömme modeli çok dilli olmalı; Türkçe sorgular ayırt edilemiyordu", 0.75),
]


@pytest.fixture
def seeded_memory(tmp_path):
    mem = CognitiveMemorySystem(db_path=tmp_path / "recall.db")
    for category, content, importance in SEED_MEMORIES:
        mem.record_memory(category, content, importance=importance)
    return mem


# --------------------------------------------------------------------------
# 1) Hibrit geri çağırma: indeksli yol == eski satır satır tarama
# --------------------------------------------------------------------------

def test_indexed_recall_matches_scalar_scan(seeded_memory):
    """25 sorgu-sonuç çifti: kimlik sırası birebir, skor farkı sayısal gürültü içinde."""
    pairs = 0
    # 0.0: gürültü eşiği hiçbir sonucu elemez, 5x5 = 25 çift karşılaştırılır.
    # 0.15: üretimdeki eşik; eleme dalı da aynı davranmalı.
    for threshold in (0.0, 0.15):
        for query in RECALL_QUERIES:
            scalar = seeded_memory._hybrid_recall_scalar(query, 5, threshold)
            indexed = seeded_memory._hybrid_recall_indexed(query, 5, threshold)

            assert [n.id for n, _ in scalar] == [n.id for n, _ in indexed], (query, threshold)
            for (_, s_old), (_, s_new) in zip(scalar, indexed):
                assert s_old == pytest.approx(s_new, abs=1e-6)
            if threshold == 0.0:
                pairs += len(indexed)

    assert pairs == 25, f"25 sorgu-sonuç çifti bekleniyordu, {pairs} bulundu"


def test_recall_returns_copies_not_cached_objects(seeded_memory):
    """Dönen düğüm önbellekteki nesne olmamalı; çağıran onu değiştirirse indeks bozulmaz."""
    first = seeded_memory.hybrid_recall(RECALL_QUERIES[0], top_k=1)
    assert first
    first[0][0].content = "BOZULDU"
    again = seeded_memory.hybrid_recall(RECALL_QUERIES[0], top_k=1)
    assert again[0][0].content != "BOZULDU"


def test_recall_index_sees_new_node(seeded_memory):
    """Yeni anı yazıldığında önbellek düşer; bir sonraki geri çağırma onu görür."""
    seeded_memory.hybrid_recall(RECALL_QUERIES[0], top_k=5)
    content = "Kaldıraç oranı ve faiz karşılama gücü denetimde birlikte incelenir"
    node, created = seeded_memory.record_memory("semantic", content, importance=0.95)
    assert created

    hits = seeded_memory.hybrid_recall("kaldıraç oranı faiz karşılama denetimi", top_k=10)
    assert node.id in [n.id for n, _ in hits]


def test_recall_index_sees_deleted_node(tmp_path):
    """Süreç dışından silinen düğüm de önbellekten düşer (imza satır sayısını görür)."""
    import sqlite3

    mem = CognitiveMemorySystem(db_path=tmp_path / "del.db")
    node, _ = mem.record_memory("semantic", "Silinecek örnek anı içeriği burada", 0.9)
    assert node.id in [n.id for n, _ in mem.hybrid_recall("silinecek örnek anı", top_k=10)]

    with sqlite3.connect(mem.db_path) as conn:
        conn.execute("DELETE FROM cognitive_nodes WHERE id = ?", (node.id,))
        conn.commit()

    assert node.id not in [n.id for n, _ in mem.hybrid_recall("silinecek örnek anı", top_k=10)]


def test_empty_database_recall_is_empty(tmp_path):
    """Ego tohumu dışında hiçbir şey yokken bile indeksli yol patlamaz."""
    import sqlite3

    mem = CognitiveMemorySystem(db_path=tmp_path / "empty.db")
    with sqlite3.connect(mem.db_path) as conn:
        conn.execute("DELETE FROM cognitive_nodes")
        conn.commit()
    mem._invalidate_recall_index()
    assert mem.hybrid_recall("herhangi bir sorgu", top_k=5) == []


# --------------------------------------------------------------------------
# 2) Gömme önbelleği ve ısıtma bayrağı
# --------------------------------------------------------------------------

def test_embedding_cache_returns_equal_and_isolated_vectors():
    engine = LocalEmbeddingEngine.get_instance()
    text = "gömme önbelleği için tekrarlanan metin"

    first = engine.embed_text(text)
    second = engine.embed_text(text)
    assert first == second
    assert first is not second, "önbellek kendi listesini döndürmemeli"

    first[0] = 12345.0
    third = engine.embed_text(text)
    assert third[0] != 12345.0, "çağıranın değişikliği önbelleği bozmamalı"
    assert engine.cache_stats()["entries"] >= 1


def test_embedding_cache_is_faster_on_second_call():
    """Önbellek gerçekten devrede: ikinci çağrı ilkinden belirgin biçimde ucuz."""
    engine = LocalEmbeddingEngine.get_instance()
    text = f"onbellek hiz olcumu icin benzersiz metin {time.time_ns()}"

    t0 = time.perf_counter()
    engine.embed_text(text)
    cold = time.perf_counter() - t0

    t0 = time.perf_counter()
    engine.embed_text(text)
    warm = time.perf_counter() - t0

    assert warm <= cold


def test_embedding_warmup_flag(monkeypatch):
    monkeypatch.setenv("ENTROPY_EMBEDDING_WARMUP", "0")
    assert embedding_warmup_enabled() is False
    assert warm_embedding_engine() is None

    monkeypatch.setenv("ENTROPY_EMBEDDING_WARMUP", "1")
    assert embedding_warmup_enabled() is True


def test_embedding_warmup_thread_is_background_daemon(monkeypatch):
    """Isıtma ana iş parçacığını bloklamamalı; motor kuruluysa hiç iş parçacığı açılmaz."""
    monkeypatch.setenv("ENTROPY_EMBEDDING_WARMUP", "1")
    LocalEmbeddingEngine.get_instance()  # zaten kuruluysa ısıtma gereksizdir
    assert warm_embedding_engine() is None


# --------------------------------------------------------------------------
# 3) Playbook dosya önbelleği: aynı sonuç, değişikliği kaçırmaz
# --------------------------------------------------------------------------

@pytest.fixture
def isolated_store(tmp_path):
    vault = tmp_path / "Vault"
    reports = vault / "Entropy" / "Skills" / "demo-skill" / "Reports"
    reports.mkdir(parents=True)
    for i in range(3):
        (reports / f"rapor_{i}.md").write_text(f"# Rapor {i}\n\nGövde {i}\n", encoding="utf-8")
    store = PlaybookStore(
        vault_path=vault,
        index=SkillReportIndex(index_path=vault / "skill_report_index.json"),
    )
    clear_file_facts_cache()
    return store, reports


def test_playbook_digest_is_stable_and_cached(isolated_store):
    store, _ = isolated_store
    sources = store.source_reports("demo-skill")
    assert len(sources) == 3

    first = store.digest_of(sources)
    second = store.digest_of(sources)          # önbellekten
    clear_file_facts_cache()
    third = store.digest_of(sources)           # yeniden diskten
    assert first == second == third


def test_playbook_digest_changes_when_content_changes(isolated_store):
    store, reports = isolated_store
    sources = store.source_reports("demo-skill")
    before = store.digest_of(sources)

    target = reports / "rapor_1.md"
    target.write_text("# Rapor 1\n\nGovde tamamen degisti ve uzadi\n", encoding="utf-8")

    after = store.digest_of(store.source_reports("demo-skill"))
    assert after != before, "içerik değişince parmak izi de değişmeli (önbellek kaçırmamalı)"


def test_playbook_content_sha_tracks_edits(isolated_store):
    store, reports = isolated_store
    target = reports / "rapor_2.md"
    before = store.content_sha(target)
    target.write_text("# Rapor 2\n\nYeni govde\n", encoding="utf-8")
    assert store.content_sha(target) != before


def test_playbook_status_repeatable(isolated_store):
    store, _ = isolated_store
    first = store.status("demo-skill")
    second = store.status("demo-skill")
    assert first == second
    assert first["source_count"] == 3


# --------------------------------------------------------------------------
# 4) Kasa grafiği önbelleği: bellek, disk ve taze tarama aynı sonucu vermeli
# --------------------------------------------------------------------------

@pytest.fixture
def graph_vault(tmp_path, monkeypatch):
    # Disk önbelleği gerçek .entropy'ye değil, teste ait dizine yazılsın.
    monkeypatch.setattr(vault_module, "_GRAPH_CACHE_FILE", tmp_path / "cache" / "graph_data.json")
    vault_module.clear_graph_cache()

    mgr = ObsidianVaultManager(vault_path=tmp_path / "GraphVault")
    notes = mgr.entropy_dir / "Notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "Alpha.md").write_text("Alpha notu [[Beta]] ve [[Gamma|Gama]] bağlar.\n", encoding="utf-8")
    (notes / "Beta.md").write_text("Beta notu [[Alpha]] geri bağlar.\n", encoding="utf-8")
    (notes / "Gamma.md").write_text("Gamma notu bağsız.\n", encoding="utf-8")
    vault_module.clear_graph_cache()
    return mgr, notes


def test_vault_graph_cache_matches_fresh_scan(graph_vault, monkeypatch):
    mgr, _ = graph_vault

    monkeypatch.setenv("ENTROPY_GRAPH_CACHE", "0")
    vault_module.clear_graph_cache()
    reference = mgr.build_knowledge_graph()

    monkeypatch.delenv("ENTROPY_GRAPH_CACHE", raising=False)
    vault_module.clear_graph_cache()
    first = mgr.build_knowledge_graph()        # tarar, diske yazar
    warm = mgr.build_knowledge_graph()         # bellek önbelleği

    vault_module.clear_graph_cache()
    from_disk = mgr.build_knowledge_graph()    # disk önbelleği (yeni süreç taklidi)

    assert first == reference
    assert warm == reference
    assert from_disk == reference
    assert len(reference["nodes"]) == 4        # 3 not + MEMORY.md
    assert reference["links"], "wikilink kenarları üretilmiş olmalı"


def test_vault_graph_cache_invalidated_by_new_note(graph_vault):
    mgr, notes = graph_vault
    before = mgr.build_knowledge_graph()

    (notes / "Delta.md").write_text("Delta notu [[Alpha]] bağlar.\n", encoding="utf-8")
    after = mgr.build_knowledge_graph()

    assert len(after["nodes"]) == len(before["nodes"]) + 1
    assert "Notes/Delta" in [n["id"] for n in after["nodes"]]


def test_vault_graph_cache_invalidated_by_edit(graph_vault):
    mgr, notes = graph_vault
    before = mgr.build_knowledge_graph()

    (notes / "Gamma.md").write_text("Gamma notu artik [[Beta]] bağlar.\n", encoding="utf-8")
    after = mgr.build_knowledge_graph()

    assert len(after["links"]) == len(before["links"]) + 1


def test_vault_graph_disk_cache_file_shape(graph_vault, monkeypatch):
    """Disk önbelleği tek dosyada, kasa yoluna göre anahtarlanır ve sınırlı sayıda kasa tutar."""
    mgr, _ = graph_vault
    monkeypatch.delenv("ENTROPY_GRAPH_CACHE", raising=False)
    mgr.build_knowledge_graph()

    payload = json.loads(vault_module._GRAPH_CACHE_FILE.read_text(encoding="utf-8"))
    assert str(mgr.vault_path) in payload
    entry = payload[str(mgr.vault_path)]
    assert entry["signature"]
    assert isinstance(entry["nodes"], list) and isinstance(entry["links"], list)
