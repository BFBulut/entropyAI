"""
Faz 11.4 — hafıza yazma yollarının test yalıtımı (K10 = 0'ın koruması).

Denetim: kullanıcının gerçek `~/.entropy/cognitive_memory.db` dosyasındaki
1.544 düğümün 531'i test fikstürüydü. Sızıntının iki nedeni vardı:
  1. yol geçmeyen `CognitiveMemorySystem()` çağrıları ev dizinine düşüyordu,
  2. üretim kapısı (fikstür süzgeci) pytest altında zaten kapalı.

Bu dosya ikisini de kilitler:
  * yazan her yolun `ENTROPY_COGNITIVE_DB` yönlendirmesine uyduğunu (geç
    içe aktarma ve arka plan iş parçacığı dâhil),
  * katı kipin fikstür kalıplarını reddettiğini.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

import pytest

from entropy.brain.gate import MemoryGate, default_strict
from entropy.brain.supabase.cognitive_memory import (
    CognitiveMemorySystem,
    default_cognitive_db_path,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_DB = Path.home() / ".entropy" / "cognitive_memory.db"


# --------------------------------------------------------------------------
# yönlendirme
# --------------------------------------------------------------------------

def test_env_override_is_active_during_tests():
    override = os.environ.get("ENTROPY_COGNITIVE_DB", "")
    assert override, "conftest ENTROPY_COGNITIVE_DB kurmamış"
    assert Path(override) != REAL_DB
    assert default_cognitive_db_path() != REAL_DB


def test_default_constructor_never_hits_real_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTROPY_COGNITIVE_DB", str(tmp_path / "x" / "cog.db"))
    mem = CognitiveMemorySystem()
    assert Path(mem.db_path) == tmp_path / "x" / "cog.db"
    assert Path(mem.db_path) != REAL_DB


def test_write_paths_resolve_to_tmp(tmp_path, monkeypatch):
    """`record_memory` / `store_node` / `_save_node` üçü de tmp DB'ye yazar."""
    db = tmp_path / "cog.db"
    monkeypatch.setenv("ENTROPY_COGNITIVE_DB", str(db))
    mem = CognitiveMemorySystem()
    mem.record_memory(
        "semantic",
        "Yalıtım kanıtı için yazılan yeterince uzun bir metin: bu satır tmp veritabanında olmalı.",
        provenance="tests/contracts/test_phase11_memory_isolation.py",
    )
    mem.store_node(
        "procedural",
        "Yalıtım kanıtı ikinci yol: store_node aynı kapıdan geçer ve aynı dosyaya yazar.",
        provenance="tests/contracts/test_phase11_memory_isolation.py",
    )
    assert db.exists()
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cognitive_nodes").fetchone()[0] >= 1


def test_background_thread_write_stays_in_tmp(tmp_path, monkeypatch):
    """
    Arka plan iş parçacığı (rapor yazıcı, damıtıcı) fixture teardown'undan sonra
    da yazabiliyor; ortam değişkeni süreç genelinde olduğu için hedef yine tmp.
    """
    db = tmp_path / "thread" / "cog.db"
    monkeypatch.setenv("ENTROPY_COGNITIVE_DB", str(db))
    seen: list[Path] = []

    def worker() -> None:
        # kasıtlı olarak GEÇ içe aktarma: modül iş parçacığı içinde çözülür
        from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem as CMS

        inner = CMS()
        inner.record_memory(
            "semantic",
            "Arka plan iş parçacığından yazılan yeterince uzun bir yalıtım kanıtı satırı.",
            provenance="tests/contracts/test_phase11_memory_isolation.py",
        )
        seen.append(Path(inner.db_path))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=60)
    assert seen and seen[0] == db, f"iş parçacığı başka dosyaya yazdı: {seen}"


def test_no_module_builds_its_own_cognitive_db_path():
    """
    Yol tek kaynaktan (`default_cognitive_db_path`) gelmeli. Üç ayrı yerde elle
    kurulmuş yol yüzünden yalıtım daha önce delinmişti.
    """
    offenders = []
    for path in (REPO_ROOT / "src" / "entropy").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "cognitive_memory.db" not in text:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "cognitive_memory.db" not in line:
                continue
            if line.lstrip().startswith("#") or '"""' in line:
                continue
            if "Path.home()" in line and "default_cognitive_db_path" not in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    assert not offenders, f"kendi yolunu kuran modüller: {offenders}"


# --------------------------------------------------------------------------
# üretim kapısı: fikstür kalıpları
# --------------------------------------------------------------------------

FIXTURE_SAMPLES = [
    "Görev pytest-of-kullanici/pytest-2301/test_x altında koştu, sonuç yeşil.",
    "DummyProc üç satır yazdı ve sıfır kodla çıktı; gerçek süreç başlatılmadı.",
    "test_office_harness_creates_board fonksiyonu panonun kurulduğunu doğrular.",
    "Ofis: arastirma-ofisi · arastirmaci · review — kanıtsız kart, sonuç boş.",
]


@pytest.mark.parametrize("content", FIXTURE_SAMPLES)
def test_strict_gate_rejects_fixture_patterns(tmp_path, monkeypatch, content):
    monkeypatch.setenv("ENTROPY_COGNITIVE_DB", str(tmp_path / "cog.db"))
    monkeypatch.setenv("ENTROPY_MEMORY_GATE_STRICT", "1")
    mem = CognitiveMemorySystem()
    gate = MemoryGate(mem, strict=True)
    decision = gate.admit("semantic", content, provenance="docs/gercek_kaynak.md")
    assert decision.action == "reject", f"kapı fikstürü kabul etti: {decision.as_log()}"
    assert not decision.writes


def test_strict_mode_is_on_in_production_off_under_pytest(monkeypatch):
    monkeypatch.delenv("ENTROPY_MEMORY_GATE_STRICT", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "dummy")
    assert default_strict() is False
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert default_strict() is True, "üretimde katı kip kapalı kalırsa fikstür süzgeci çalışmaz"


def test_real_user_db_untouched_by_this_module():
    """Bu modül gerçek veritabanına dokunmadı (dosya varsa boyut/mtime sabit)."""
    if not REAL_DB.exists():
        pytest.skip("gerçek veritabanı yok")
    stat = REAL_DB.stat()
    mem = CognitiveMemorySystem()  # yönlendirilmiş varsayılan
    assert Path(mem.db_path) != REAL_DB
    assert REAL_DB.stat().st_mtime_ns == stat.st_mtime_ns
