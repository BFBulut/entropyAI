"""
Faz 10-A: bilişsel bellek çift depo tutarlılığı ve hata görünürlüğü.

Teşhis notu docs/reports/2026-09-11_Faz10_Teshis_ve_Mimari_Bosluk_Notu.md §A:
- A.2 (P0): yazma yolu yalnızca `cognitive_nodes`'a yazıyordu, graf `nodes`
  tablosu yalnızca elle göçle doluyordu; gerçek veritabanında 35 düğüm sapmıştı.
- A.4 (P0): 8 sessiz `except` bloğu; gömme hatası sessizce hash yedeğine
  düşüyor ve düğüm anlamsal geri çağırmadan kalıcı olarak düşüyordu.
"""

import sqlite3

import pytest

from entropy.brain.graph_store import GraphStore
from entropy.brain.supabase.cognitive_memory import (
    CognitiveMemorySystem,
    LocalEmbeddingEngine,
)


@pytest.fixture()
def memory(tmp_path):
    return CognitiveMemorySystem(db_path=tmp_path / "cm.db")


def _drift(db_path) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM cognitive_nodes c LEFT JOIN nodes n ON c.id = n.id"
            " WHERE n.id IS NULL"
        ).fetchone()[0]


# --- A.2: yazma yolu iki depoya da yazar ---------------------------------

def test_record_memory_writes_to_both_stores(memory):
    node, created = memory.record_memory("semantic", "Entropy bellek katmani tek yazma yolu kullanir")
    assert created

    with sqlite3.connect(memory.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM cognitive_nodes WHERE id = ?", (node.id,)
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE id = ?", (node.id,)
        ).fetchone()[0] == 1
    assert memory.store_drift() == 0


def test_five_production_writes_leave_zero_drift(memory):
    """Teşhis notundaki kabul ölçütü: 5 yeni anı sonrası sapma = 0."""
    for i in range(5):
        memory.record_memory("query", f"Faz 10 uretim yolu yazma denemesi {i}")
    assert _drift(memory.db_path) == 0


def test_reconcile_closes_drift_and_is_idempotent(memory, monkeypatch):
    """Sapma senaryosu: eski yol gibi doğrudan cognitive_nodes'a yazılan satırlar."""
    # Faz 11.2: bu test SAPMAYI ölçer, yeniliği değil. 22 satır yalnızca sonda
    # farklı ("... eski kayit 7") olduğu için yazma kapısı bir kısmını kopya
    # sayıp NOOP'a düşürüyordu (ölçüm: 22 yerine 14 satır). Kapı burada
    # bilerek kapatılır; kapının kendi davranışı test_phase11_memory_gate'te.
    monkeypatch.setenv("ENTROPY_MEMORY_GATE", "0")
    memory._graph_sync_enabled = False  # eski (bozuk) yazma yolunu taklit et
    for i in range(22):
        memory.record_memory("query", f"Graf disinda kalmis eski kayit {i}")
    memory._graph_sync_enabled = True
    memory._graph_store = None

    assert memory.store_drift() == 22

    first = memory.reconcile_stores(similarity_edges=False)
    assert first["drift_before"] == 22
    assert first["drift_after"] == 0
    assert first["synced"] == 22

    # Idempotent: ikinci koşu hiçbir şey yazmaz.
    second = memory.reconcile_stores(similarity_edges=False)
    assert second["synced"] == 0
    assert second["drift_after"] == 0


def test_startup_maintenance_closes_drift(memory):
    memory._graph_sync_enabled = False
    memory.record_memory("semantic", "Acilis bakimi bu satiri grafa tasimali")
    memory._graph_sync_enabled = True
    memory._graph_store = None
    assert memory.store_drift() == 1

    out = memory.startup_maintenance(background=False)
    assert out is not None
    assert memory.store_drift() == 0


def test_delete_memory_removes_from_both_stores(memory):
    node, _ = memory.record_memory("semantic", "Silinecek anı iki depodan da gitmeli")
    store = GraphStore(memory=memory)
    store.add_edge(node.id, node.id, "similar_to", weight=0.9)

    removed = memory.delete_memory(node.id)
    assert removed["cognitive_nodes"] == 1
    assert removed["nodes"] == 1
    assert removed["edges"] >= 1

    with sqlite3.connect(memory.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cognitive_nodes WHERE id = ?", (node.id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM nodes WHERE id = ?", (node.id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM edges WHERE src = ? OR dst = ?", (node.id, node.id)).fetchone()[0] == 0


def test_graph_sync_failure_does_not_lose_memory(memory, caplog):
    """Graf senkronu patlasa bile anı `cognitive_nodes`'ta kalır ve hata görünür."""
    class _Broken:
        def sync_from_cognitive(self, **kwargs):
            raise RuntimeError("graf tablosu kilitli")

    memory._graph_store = _Broken()
    node, _ = memory.record_memory("semantic", "Graf patlasa da bu ani kaybolmamali")

    assert memory.get_node(node.id) is not None
    assert any(e["stage"] == "sync_node_to_graph" for e in memory.last_errors)


# --- A.4: gömme hatası sessiz kalmaz -------------------------------------

class _FailingModel:
    def embed(self, texts):
        raise RuntimeError("fastembed cikarimi patladi")


@pytest.fixture()
def failing_engine():
    """Sinirsel model yüklü görünen ama çıkarımı patlayan bir motor."""
    LocalEmbeddingEngine.reset_instance()
    engine = LocalEmbeddingEngine.get_instance()
    old_model, old_neural, old_name = engine._model, engine._is_neural, engine._model_name
    engine._model = _FailingModel()
    engine._is_neural = True
    engine._model_name = "test-neural"
    engine._cache.clear()
    yield engine
    engine._model, engine._is_neural, engine._model_name = old_model, old_neural, old_name
    LocalEmbeddingEngine.reset_instance()


def test_embedding_failure_keeps_node_and_marks_pending(tmp_path, failing_engine):
    memory = CognitiveMemorySystem(db_path=tmp_path / "cm.db")
    node, created = memory.record_memory("semantic", "Gomme patlasa bile kaybolmayan ani")
    assert created

    # Düğüm kaybolmadı...
    assert memory.get_node(node.id) is not None
    # ...ve 'pending' işaretlendi.
    with sqlite3.connect(memory.db_path) as conn:
        status, model = conn.execute(
            "SELECT embedding_status, embedding_model FROM cognitive_nodes WHERE id = ?", (node.id,)
        ).fetchone()
    assert status == "pending"
    assert model == "hash-fallback"
    assert memory.pending_embedding_count() >= 1
    # Sessiz değil: hata sayacında görünür.
    assert any(e["stage"] == "record_memory" for e in memory.last_errors)


def test_reembed_stale_fills_pending_after_engine_recovers(tmp_path, failing_engine):
    memory = CognitiveMemorySystem(db_path=tmp_path / "cm.db")
    node, _ = memory.record_memory("semantic", "Motor duzelince yeniden gomulmeli")
    # Ego tohum düğümü de aynı bozuk motorla yazılır; ikisi de 'pending' olur.
    assert memory.pending_embedding_count() >= 1

    # Motor düzelir: hash tabanlı yedek (deterministik) devreye girer.
    failing_engine._model = None
    failing_engine._is_neural = False
    failing_engine._model_name = ""

    out = memory.reembed_stale()
    assert out["reembedded"] >= 1
    assert out["failed"] == 0
    assert memory.pending_embedding_count() == 0


def test_embed_text_status_reports_fallback(failing_engine):
    vector, status = failing_engine.embed_text_status("herhangi bir metin")
    assert status == "fallback"
    assert len(vector) == 384
    # Başarısız çıkarımın sonucu önbelleğe girmez: sonraki deneme yine sinirsel yolu dener.
    assert "herhangi bir metin" not in failing_engine._cache


# --- A.4: rüya döngüsü kısmi başarısızlığı bildirir ----------------------

def test_dream_reports_step_errors(memory, monkeypatch):
    memory.record_memory("episodic", "Ilk bolumsel etkilesim, yeterince uzun bir icerik")
    memory.record_memory("episodic", "Ikinci bolumsel etkilesim, yeterince uzun bir icerik")

    def _boom(*args, **kwargs):
        raise RuntimeError("budama patladi")

    monkeypatch.setattr(memory, "prune_decayed_memories", _boom)
    result = memory.dream_and_consolidate()

    assert isinstance(result, list)  # eski çağıranlar kırılmaz
    assert result.errors, "rüya döngüsü hatası sessizce yutulmamalı"
    assert any(e["stage"] == "dream:prune" for e in result.errors)
    assert result.ok is False


# --- A.1: build_knowledge_graph None koruması ----------------------------

def test_build_knowledge_graph_survives_none_member(tmp_path, monkeypatch):
    """`None` ofis üyesi tüm grafik yenilemesini çökertmemeli (Faz 7 regresyonu)."""
    from entropy.brain.obsidian import vault_manager as vm

    # Yönetici kasa kökünün altında `Entropy/` alt klasörünü tarar.
    root = tmp_path / "Entropy"
    (root / "Offices" / "office_test").mkdir(parents=True)
    (root / "Offices" / "office_test" / "OFFICE.md").write_text(
        "---\norchestrator: orkestra\nmembers: [a, b]\n---\n\nTest ofisi\n",
        encoding="utf-8",
    )
    (root / "Reports").mkdir()
    (root / "Reports" / "rapor.md").write_text("# Rapor\n[[OFFICE]]\n", encoding="utf-8")
    vault = tmp_path

    real = vm._frontmatter_list

    def _with_none(text, key):
        # Bozuk/eksik ön bilgi: liste içinde None döner.
        return [None] + list(real(text, key))

    monkeypatch.setattr(vm, "_frontmatter_list", _with_none)

    manager = vm.ObsidianVaultManager(vault_path=vault)
    graph = manager.build_knowledge_graph()

    assert graph["nodes"], "grafik boş dönmemeli"
    assert all(node.get("name") is not None for node in graph["nodes"])


def test_dream_success_has_no_errors(memory):
    memory.record_memory("episodic", "Ilk bolumsel etkilesim, yeterince uzun bir icerik")
    memory.record_memory("episodic", "Ikinci bolumsel etkilesim, yeterince uzun bir icerik")
    result = memory.dream_and_consolidate()
    assert result.errors == []
    assert result.ok is True
    assert memory.store_drift() == 0
