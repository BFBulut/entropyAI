"""
Faz 11.5 — göç betiği (`scripts/memory_migrate_v2.py`).

Sentetik bir "kirli" kaynak veritabanı kurulur (fikstür + uydurma mimari +
yakın kopya + gerçek bilgi), kademeli süzme ölçülür ve hedef veritabanının
şema v2 disiplinine uyduğu doğrulanır. Gerçek profil veritabanına dokunulmaz.
"""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

from entropy.memory.categories import CANONICAL_CATEGORIES
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memory_migrate_v2.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("memory_migrate_v2", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # `dataclass` alan çözümlemesi modülü `sys.modules`ta arar; kayıt edilmezse
    # `MigrationPlan` kurulurken AttributeError verir.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migrate():
    return _load_module()


REAL_NODES = [
    ("semantic", "James A. Ohlson (1980) O-Score modeli dokuz muhasebe oranıyla temerrüt olasılığını kestirir"),
    ("architecture", "Bellek katmanı SQLite üzerinde çalışır ve graf tabloları aynı dosyada durur"),
    ("procedural", "Finansal denetimde bilanço, gelir tablosu ve nakit akış birlikte okunur"),
    ("query", "Kullanıcı wiki sayfası istedi ve rapor gövdesinden derlenmiş bir özet bekliyor"),
]

DIRTY_NODES = [
    # fikstür kalıpları
    ("query", "arastirma-ofisi: Pazar araştırması / Ofis: bir şey · arastirmaci · review"),
    ("semantic", "Ayrıştırıcı Modül bitti. [KANIT] Komut: python -m pytest tests/test_modul.py"),
    # uydurma "N-Layer" mimari serisi
    ("architecture", "Pentacosa-Store 25-Layer Cognitive Memory Architecture katmanları tanımlar"),
    ("architecture", "Heptacosa-Store 27-Layer Cognitive Memory Architecture katmanları tanımlar"),
    # çok kısa
    ("semantic", "kısa not"),
]


@pytest.fixture
def dirty_db(tmp_path):
    """Kirli kaynak: kapı KAPALI yazılır, çünkü eski veritabanı da öyle oluştu."""
    import os

    previous = os.environ.get("ENTROPY_MEMORY_GATE")
    os.environ["ENTROPY_MEMORY_GATE"] = "0"
    try:
        mem = CognitiveMemorySystem(db_path=tmp_path / "legacy.db")
        for category, content in REAL_NODES + DIRTY_NODES:
            mem.record_memory(category, content, importance=0.7, metadata={"path": "/kasa/x.md"})
        # yakın kopyalar: aynı bilgi başka sözcüklerle / numaralandırılmış
        for i in range(6):
            mem.record_memory(
                "semantic",
                f"James A. Ohlson (1980) O-Score modeli dokuz muhasebe oranıyla temerrüt olasılığını kestirir ({i})",
                importance=0.5, metadata={"path": "/kasa/x.md"},
            )
    finally:
        if previous is None:
            os.environ.pop("ENTROPY_MEMORY_GATE", None)
        else:
            os.environ["ENTROPY_MEMORY_GATE"] = previous
    return tmp_path / "legacy.db"


def test_dry_run_does_not_touch_the_source(migrate, dirty_db):
    before = dirty_db.stat().st_size
    with sqlite3.connect(dirty_db) as conn:
        rows_before = conn.execute("SELECT COUNT(*) FROM cognitive_nodes").fetchone()[0]

    copy = migrate._copy_to_temp(dirty_db)
    plan = migrate.plan_migration(copy)

    with sqlite3.connect(dirty_db) as conn:
        rows_after = conn.execute("SELECT COUNT(*) FROM cognitive_nodes").fetchone()[0]
    assert rows_after == rows_before
    assert dirty_db.stat().st_size == before
    assert plan.source_nodes == rows_before


def test_graded_filter_drops_fixtures_fake_architecture_and_duplicates(migrate, dirty_db):
    plan = migrate.plan_migration(migrate._copy_to_temp(dirty_db))
    reasons = plan.counts()["dropped_by_reason"]

    assert reasons.get(migrate.DROP_FIXTURE, 0) >= 2
    assert reasons.get(migrate.DROP_FAKE_ARCH, 0) == 2
    assert reasons.get(migrate.DROP_SHORT, 0) >= 1
    assert reasons.get(migrate.DROP_MERGED, 0) >= 5, "6 yakın kopya birleşmeliydi"

    kept_contents = " ".join(item["content"] for item in plan.kept)
    assert "Ohlson" in kept_contents, "gerçek bilgi korunmalı"
    assert "pytest" not in kept_contents
    assert "Pentacosa-Store" not in kept_contents


def test_migration_maps_categories_to_the_closed_set(migrate, dirty_db, tmp_path):
    plan = migrate.plan_migration(migrate._copy_to_temp(dirty_db))
    assert set(plan.category_after) <= set(CANONICAL_CATEGORIES)
    # "architecture" -> semantic, "query" -> episodic
    assert plan.category_after.get("episodic", 0) >= 1


def test_write_target_builds_clean_v2_database(migrate, dirty_db, tmp_path):
    plan = migrate.plan_migration(migrate._copy_to_temp(dirty_db))
    target = tmp_path / "brain_v2.db"
    stats = migrate.write_target(plan, target)

    assert stats["written"] == len(plan.kept)
    with sqlite3.connect(target) as conn:
        categories = {r[0] for r in conn.execute("SELECT DISTINCT category FROM cognitive_nodes")}
        cols = [r[1] for r in conn.execute("PRAGMA table_info(cognitive_nodes)")]
        rows = conn.execute("SELECT COUNT(*) FROM cognitive_nodes").fetchone()[0]
        graph_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    assert categories <= set(CANONICAL_CATEGORIES), categories
    assert "provenance" in cols and "is_identity" in cols
    # ego tohumu hedefte yeniden kurulur; bu yüzden >= kullanılıyor.
    assert rows >= len(plan.kept)
    assert graph_nodes >= 1, "graf tabloları yeniden kurulmalı"


def test_migration_is_idempotent(migrate, dirty_db, tmp_path):
    first = migrate.plan_migration(migrate._copy_to_temp(dirty_db)).counts()
    second = migrate.plan_migration(migrate._copy_to_temp(dirty_db)).counts()
    assert first["kept"] == second["kept"]
    assert first["dropped_by_reason"] == second["dropped_by_reason"]

    a = tmp_path / "a.db"
    b = tmp_path / "b.db"
    plan = migrate.plan_migration(migrate._copy_to_temp(dirty_db))
    migrate.write_target(plan, a)
    migrate.write_target(migrate.plan_migration(migrate._copy_to_temp(dirty_db)), b)
    with sqlite3.connect(a) as conn:
        ids_a = {r[0] for r in conn.execute("SELECT id FROM cognitive_nodes")}
    with sqlite3.connect(b) as conn:
        ids_b = {r[0] for r in conn.execute("SELECT id FROM cognitive_nodes")}
    assert ids_a == ids_b


def test_backup_is_written_next_to_profile(migrate, dirty_db, monkeypatch, tmp_path):
    """`--apply` yedeksiz koşmamalı: yedek yolu ~/.entropy/backups altındadır."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    dest = migrate.backup(dirty_db)
    assert dest.exists()
    assert dest.parent == tmp_path / ".entropy" / "backups"
    assert dest.name.startswith("cognitive_memory.pre-v2.")


# --------------------------------------------------------------------------
# Faz 11 kapanışı — `--tag-legacy`: v2 öncesi kaynaksız L2 düğümleri
# --------------------------------------------------------------------------

@pytest.fixture
def legacy_db(tmp_path):
    """Kaynaksız L2 + kaynaklı L2 + kimlik düğümü olan v2 şemalı veritabanı."""
    import os
    import time

    previous = os.environ.get("ENTROPY_MEMORY_GATE")
    os.environ["ENTROPY_MEMORY_GATE"] = "0"
    try:
        db = tmp_path / "legacy.db"
        mem = CognitiveMemorySystem(db_path=db)
        old = time.time() - 400 * 86400.0
        for i in range(3):
            mem.record_memory(
                "semantic",
                f"Kaynagi hic kaydedilmemis eski bilgi {i}: bu metin v2 oncesinden geliyor.",
            )
        mem.record_memory(
            "semantic",
            "Kaynagi olan bilgi: rapor gövdesinden derlendi ve dosya yolu var.",
            metadata={"path": "docs/reports/x.md"},
        )
        with sqlite3.connect(db) as conn:
            # Kapı kapalıyken record_memory provenance yazmaz (v1 davranışı);
            # kaynaklı düğümü elle işaretle, kalan üçü kaynaksız kalsın.
            conn.execute(
                "UPDATE cognitive_nodes SET created_at = ?, valid_from = ?",
                (old, time.time()),
            )
            conn.execute(
                "UPDATE cognitive_nodes SET provenance = 'path=docs/reports/x.md'"
                " WHERE content LIKE 'Kaynagi olan bilgi%'"
            )
            conn.commit()
        return db
    finally:
        if previous is None:
            os.environ.pop("ENTROPY_MEMORY_GATE", None)
        else:
            os.environ["ENTROPY_MEMORY_GATE"] = previous


def test_tag_legacy_dry_run_writes_nothing(migrate, legacy_db):
    before = sqlite3.connect(legacy_db).execute(
        "SELECT COUNT(*) FROM cognitive_nodes WHERE TRIM(COALESCE(provenance,'')) = ''"
    ).fetchone()[0]
    report = migrate.plan_legacy_tagging(legacy_db)
    assert report["candidates"] == before == 3
    assert report["already_tagged"] == 0
    after = sqlite3.connect(legacy_db).execute(
        "SELECT COUNT(*) FROM cognitive_nodes WHERE TRIM(COALESCE(provenance,'')) = ''"
    ).fetchone()[0]
    assert after == before, "kuru koşum veritabanına dokunmamalı"


def test_tag_legacy_apply_is_idempotent_and_sets_fields(migrate, legacy_db):
    from entropy.memory.gate import LEGACY_CONFIDENCE, LEGACY_PROVENANCE

    tagged = migrate.apply_legacy_tagging(legacy_db)
    assert tagged == 3
    with sqlite3.connect(legacy_db) as conn:
        rows = conn.execute(
            "SELECT provenance, confidence, valid_from, created_at FROM cognitive_nodes"
            " WHERE provenance = ?", (LEGACY_PROVENANCE,)
        ).fetchall()
    assert len(rows) == 3
    for prov, conf, valid_from, created_at in rows:
        assert prov == LEGACY_PROVENANCE
        assert abs(conf - LEGACY_CONFIDENCE) < 1e-9
        # valid_from eski created_at olmalı (göç anı değil)
        assert abs(valid_from - created_at) < 1e-6

    # ikinci koşum: etiketlenecek düğüm kalmaz
    assert migrate.apply_legacy_tagging(legacy_db) == 0
    report = migrate.plan_legacy_tagging(legacy_db)
    assert report["candidates"] == 0
    assert report["already_tagged"] == 3


def test_legacy_label_is_not_strong_provenance():
    """Etiket kaynak yerine geçmez: yeni L2 yazımı bununla kapıyı geçemez."""
    from entropy.memory.gate import LEGACY_PROVENANCE, derive_provenance

    prov, strong = derive_provenance({}, LEGACY_PROVENANCE)
    assert prov == LEGACY_PROVENANCE
    assert strong is False


def test_brain_metrics_k12_excludes_legacy_tagged(migrate, legacy_db):
    """K12 legacy etiketlileri saymaz; ayrı sayaçta görünür."""
    import importlib.util

    migrate.apply_legacy_tagging(legacy_db)
    path = Path(__file__).resolve().parents[1] / "scripts" / "brain_metrics.py"
    spec = importlib.util.spec_from_file_location("brain_metrics_legacy", path)
    bm = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bm
    spec.loader.exec_module(bm)
    rows = bm.read_rows(legacy_db)
    report = bm.unsourced_l2(rows)
    assert report["count"] == 0, "etiketli düğümler kaynaksız L2 sayılmamalı"
    assert report["legacy_untagged"] == 3
