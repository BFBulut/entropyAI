"""
Faz 14-D — hafıza yazarı alt ajan + kapının hata/günlük reddi bandı.

Ölçülen arıza (A notu §1 satır 3c): başarısız turun hata metni `success`
bayrağına bakılmadan hafızaya yazılıyordu; kapı "bu bir hata günlüğü mü" diye
bakmıyordu. Buradaki testler o üç yolu da kapatır:
  1. kapı bandı (hata/yığın izi/günlük/pytest izi/başarısız tur),
  2. alt ajanın `[HAFIZA]` blok sözleşmesi (ayrıştırma, doğrulama, yazım),
  3. arşiv betiğinin kuru koşumu (geçici DB, silme yok).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from entropy.brain import agent_memory_writer as amw
from entropy.brain.artifact_archive import find_candidates, run as archive_run
from entropy.brain.gate import (
    ACTION_REJECT,
    REJECT_ERRORLOG,
    MemoryGate,
    artifact_provenance_match,
    error_log_match,
)
from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem
from entropy.core.report_title import strip_machine_blocks

GOOD = (
    "canivopets.com pazar araştırması: evcil hayvan aboneliği pazarında "
    "üç rakip abonelik kutusu modeli kullanıyor ve ortalama sepet 420 TL."
)


@pytest.fixture()
def memory(tmp_path: Path) -> CognitiveMemorySystem:
    return CognitiveMemorySystem(db_path=tmp_path / "cog.db")


@pytest.fixture()
def gate(memory: CognitiveMemorySystem) -> MemoryGate:
    return MemoryGate(memory, strict=True, queue_path=Path(memory.db_path).parent / "gray.jsonl")


# ---------------------------------------------------------------- kapı bandı

@pytest.mark.parametrize(
    "content",
    [
        "Traceback (most recent call last):\n  File 'x.py', line 3, in <module>\n    boom()",
        "Error: görev tamamlanamadı, çünkü süreç beklenmedik biçimde sonlandı ve çıktı yok.",
        "Exception yakalandı: AgyProcessBridge beklenen akışı üretemedi ve tur düştü burada.",
        "Otonom Görev Özeti [Test]: 'list_iterator' object has no attribute 'close' hatası.",
        "Otonom Görev Özeti [X]: [Otonom Görev Hata] X yürütülemedi çünkü süreç yanıt vermedi.",
        "[ADIM SINIRI] Araç adımı sınırı aşıldı (21 > 20); görev durduruldu ve kart düştü.",
        "Timeout: arka plan turu 900 saniyede yanıt vermedi, süreç ağacı sonlandırıldı burada.",
        "[12:00:01] WARNING bu yalnızca bir günlük satırıdır ve hafızaya girmemelidir asla.",
    ],
)
def test_gate_rejects_error_and_log_content(gate: MemoryGate, content: str) -> None:
    decision = gate.admit("semantic", content, provenance="report=Entropy/Reports/a.md")
    assert decision.action == ACTION_REJECT
    assert decision.reject_code == REJECT_ERRORLOG
    assert decision.reason
    assert gate.stats[REJECT_ERRORLOG] >= 1


def test_gate_rejects_pytest_provenance(gate: MemoryGate) -> None:
    decision = gate.admit(
        "semantic", GOOD,
        provenance=r"path=C:\Users\x\AppData\Local\Temp\pytest-of-x\pytest-2259\t0\rapor.md",
    )
    assert decision.action == ACTION_REJECT
    assert decision.reject_code == REJECT_ERRORLOG
    assert "izi" in decision.reason


def test_gate_rejects_failed_run_metadata(gate: MemoryGate) -> None:
    decision = gate.admit("semantic", GOOD, metadata={"success": False, "path": "x.md"})
    assert decision.action == ACTION_REJECT
    assert decision.reject_code == REJECT_ERRORLOG


def test_gate_accepts_clean_sourced_content(gate: MemoryGate) -> None:
    decision = gate.admit("semantic", GOOD, provenance="report=Entropy/Reports/canivopets.md")
    assert decision.action != ACTION_REJECT
    assert decision.writes


def test_band_helpers() -> None:
    assert error_log_match("Traceback (most recent call last):")
    assert error_log_match("INFO tek satır") == "log_line"
    assert error_log_match(GOOD) is None
    assert artifact_provenance_match("path=/tmp/rapor.md")
    assert artifact_provenance_match("", {"path": "C:/x/pytest-of-y/z"})
    assert artifact_provenance_match("report=Entropy/Reports/a.md") is None


# ------------------------------------------------------------ [HAFIZA] bloğu

def _block(items: list) -> str:
    return "# Rapor\n\nGövde.\n\n[HAFIZA]\n" + json.dumps({"items": items}, ensure_ascii=False) + "\n[/HAFIZA]\n"


def test_parse_and_validate_block() -> None:
    text = _block([
        {"category": "semantic", "content": GOOD, "importance": 0.7,
         "provenance": {"report": "Entropy/Reports/a.md", "source_urls": ["https://canivopets.com"]},
         "tags": ["pazar"]},
    ])
    raw, errors = amw.parse_block(text)
    assert not errors and len(raw) == 1
    items, verrors = amw.validate_items(raw)
    assert not verrors
    assert items[0].category == "semantic"
    assert "report=" in items[0].provenance and "url=" in items[0].provenance


def test_validate_rejects_bad_category_missing_provenance_and_limits() -> None:
    raw = [
        {"category": "hatira", "content": GOOD, "provenance": {"report": "a.md"}},
        {"category": "semantic", "content": GOOD},                       # provenance yok
        {"category": "semantic", "content": "kısa", "provenance": {"report": "a.md"}},
        {"category": "semantic", "content": "x" * 700, "provenance": {"report": "a.md"}},
    ]
    items, errors = amw.validate_items(raw)
    assert items == []
    assert len(errors) == 4

    many = [{"category": "semantic", "content": f"{GOOD} varyant {i}",
             "provenance": {"report": "a.md"}} for i in range(10)]
    items, errors = amw.validate_items(many)
    assert len(items) == amw.MAX_ITEMS
    assert any("sınırı aşıldı" in e for e in errors)


def test_bad_json_block_is_ignored() -> None:
    raw, errors = amw.parse_block("[HAFIZA]\n{items: bozuk}\n[/HAFIZA]")
    assert raw == [] and errors


def test_ingest_writes_through_gate(memory: CognitiveMemorySystem) -> None:
    text = _block([
        {"category": "semantic", "content": GOOD, "importance": 0.7,
         "provenance": {"report": "Entropy/Reports/a.md"}},
        {"category": "semantic",
         "content": "Otonom Görev Özeti: [Otonom Görev Hata] tur yürütülemedi, süreç düştü.",
         "provenance": {"report": "Entropy/Reports/a.md"}},
    ])
    memory._gate = MemoryGate(memory, strict=True)
    result = amw.ingest_agent_report(memory, text, report_path="Entropy/Reports/a.md")
    assert len(result.written) == 1
    assert len(result.rejected) == 1
    node = memory.get_node(result.written[0])
    assert node is not None and node.provenance
    assert node.metadata.get("writer") == "agent"


def test_ingest_skips_failed_or_unproven_run(memory: CognitiveMemorySystem) -> None:
    text = _block([{"category": "semantic", "content": GOOD, "provenance": {"report": "a.md"}}])
    for kwargs in ({"success": False}, {"has_proof": False}):
        result = amw.ingest_agent_report(memory, text, report_path="a.md", **kwargs)
        assert result.written == []
        assert result.skipped_reason.startswith(REJECT_ERRORLOG)


def test_memory_block_hidden_from_display() -> None:
    text = _block([{"category": "semantic", "content": GOOD, "provenance": {"report": "a.md"}}])
    assert "[HAFIZA]" not in strip_machine_blocks(text)
    assert "[HAFIZA]" not in amw.strip_memory_blocks(text)
    assert "Gövde." in strip_machine_blocks(text)


# --------------------------------------------------------------- arşiv betiği

def _seed_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE cognitive_nodes (id TEXT PRIMARY KEY, category TEXT, content TEXT, "
        "provenance TEXT, metadata_json TEXT, archived INTEGER DEFAULT 0)"
    )
    rows = [
        ("n1", "semantic", "Otonom Görev Özeti: 'list_iterator' object has no attribute", "", "{}", 0),
        ("n2", "semantic", "Temiz içerik, korunacak düğüm.", "report=a.md", "{}", 0),
        ("n3", "episodic", "Fikstür çıktısı", r"path=C:\Temp\pytest-of-x\pytest-1\a.md", "{}", 0),
    ]
    conn.executemany("INSERT INTO cognitive_nodes VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def test_archive_dry_run_changes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "cog.db"
    _seed_db(db)
    result = archive_run(db_path=db, write_vault_log=False)
    assert result["dry_run"] is True
    assert sorted(result["ids"]) == ["n1", "n3"]
    assert result["archived"] == 0
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT COUNT(*) FROM cognitive_nodes WHERE archived=1").fetchone()[0] == 0
    conn.close()


def test_archive_apply_marks_without_deleting(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "cog.db"
    _seed_db(db)
    monkeypatch.setattr("entropy.brain.artifact_archive.backups_root", lambda: tmp_path / "backups")
    result = archive_run(db_path=db, apply=True, write_vault_log=False)
    assert result["archived"] == 2
    assert Path(result["backup"]).exists()
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT COUNT(*) FROM cognitive_nodes").fetchone()[0] == 3  # silme yok
    archived = dict(conn.execute("SELECT id, metadata_json FROM cognitive_nodes WHERE archived=1"))
    conn.close()
    assert set(archived) == {"n1", "n3"}
    assert json.loads(archived["n1"])["archived_reason"] == "phase14d_artifact"
    # ikinci koşum idempotent: aday kalmaz
    assert find_candidates(db) == []
