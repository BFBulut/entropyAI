"""
Faz 13-C.1 — harness ofis kartını ALANLARDAN okur, `summary`den değil.

Kullanıcı şikâyeti: Desk panosunda alt kartın özetinde ham
`[PANO board_finish] {json} [/PANO]` metni duruyordu. Blokları temizlemek
eskiden harness'ın tek gerçek kaynağını yok ederdi; bu yüzden ayrıştırma
kapanış anına (`tasks._finish`) alındı ve harness kartın `checkpoint`,
`proof`, `proof_green` alanlarını okuyor. Bu dosya iki yönü de sürer:
temiz özet + dolu alanlar + harness'ın kanıt kararı.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from entropy.agents.desk_registry import DeskOffice, DeskRegistry
from entropy.agents.harness import OfficeHarness
from entropy.agents.tasks import TaskBoard, TaskCard


@pytest.fixture(autouse=True)
def clean_active_registry():
    OfficeHarness._active.clear()
    yield
    OfficeHarness._active.clear()


RAW = """İş bitti.

[KONTROL NOKTASI]
Özet: Modül yazıldı.
Yapılan: parser.py
Sonraki adımlar: entegrasyon
Dosyalar: src/parser.py
Testler: pytest -q
[/KONTROL NOKTASI]

[KANIT]
Komut: pytest -q
Sonuç: 12 passed
[/KANIT]

[KURAL] Bu projede testler pytest -q ile koşulur.

[PANO board_finish]
{"summary": "Modül hazır", "outputs": ["src/parser.py"]}
[/PANO]
"""


def _setup(tmp_path):
    desk = DeskRegistry(vault_path=tmp_path)
    desk.create(DeskOffice(name="medya", purpose="Metin üretimi"))
    board = TaskBoard(vault_path=tmp_path)
    card = board.create(TaskCard(id="20260911-1600-alt", title="Alt kart",
                                 goal="Modülü yaz", office="medya",
                                 agent="yazar", status="backlog"))
    harness = OfficeHarness("medya", board=board, offices=desk)
    return board, harness, card


def test_office_card_closes_with_clean_summary_and_filled_fields(tmp_path):
    board, harness, card = _setup(tmp_path)
    board._finish(card.id, RAW, True)
    done = board.get(card.id)

    assert "[PANO" not in (done.summary or "")
    assert "Modül hazır" in (done.summary or "") or "İş bitti" in (done.summary or "")
    assert done.checkpoint and Path(done.checkpoint).is_file()
    assert done.proof_green is True


def test_harness_reads_proof_from_card_fields(tmp_path):
    board, harness, card = _setup(tmp_path)
    board._finish(card.id, RAW, True)
    done = board.get(card.id)

    # Özet TEMİZ olduğu için metin yolu (`read_proof`) boş dönmeli; harness'ın
    # kanıtı yine de bulması alan yolundan geldiğinin kanıtıdır.
    assert harness.read_proof(done.summary or "", needs_write=True) is None
    proof = OfficeHarness._card_proof(done)
    assert proof is not None and proof["green"] is True


def test_rule_candidates_are_queued_once_at_close(tmp_path):
    board, harness, card = _setup(tmp_path)
    board._finish(card.id, RAW, True)
    done = board.get(card.id)

    # Kapanışta ham çıktıdan toplandı; temizlenmiş özette artık satır yok, yani
    # harness'ın ikinci taraması ÇİFT aday yazamaz.
    assert "[KURAL]" not in (done.summary or "")
    assert harness.collect_rule_candidates(done.agent, done.summary or "") == []


def test_checkpoint_lands_in_office_workspace_not_entropy_root(tmp_path):
    board, harness, card = _setup(tmp_path)
    board._finish(card.id, RAW, True)
    path = Path(board.get(card.id).checkpoint)
    assert "Desk" in str(path) and "medya" in str(path)
    assert "Entropy" not in path.relative_to(tmp_path).parts[:1]
