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
