"""
Canlı koşuda bulunan kusur: ofis raporu Entropy grafına hiç akmıyordu.

`OfficeHarness._write_local_report` raporu yazdıktan sonra
`ingest_office_into_entropy(office, str(path))` çağırıyordu; fonksiyonun ikinci
KONUMSAL parametresi ise `store`. Çağrı her seferinde
`AttributeError: 'str' object has no attribute 'upsert_node'` ile patlıyor,
hata `except` içinde yutuluyor ve geriye yalnızca bir uyarı satırı kalıyordu.
"""

import types

import pytest


def test_local_report_ingest_is_called_with_store_not_path(tmp_path, monkeypatch):
    from dataclasses import replace

    from entropy.agents.desk_registry import DeskOffice, DeskRegistry
    from entropy.agents.harness import OfficeHarness
    from entropy.agents.tasks import TaskBoard, TaskCard

    desk = DeskRegistry(vault_path=tmp_path)
    desk.create(DeskOffice(name="ofis1", purpose="test", budget_tokens=1000))
    board = TaskBoard(vault_path=tmp_path)
    harness = OfficeHarness("ofis1", board=board, offices=desk)

    calls = []

    def fake_ingest(office, store=None, vault_path=None, max_reports=20):
        # Gerçek imzanın aynısı: yanlış konumsal argüman burada yakalanır.
        if store is not None and not hasattr(store, "upsert_node"):
            raise AttributeError("'str' object has no attribute 'upsert_node'")
        calls.append({"office": office, "store": store, "vault_path": vault_path})
        return {"ok": True}

    import entropy.brain.office_graph as og
    monkeypatch.setattr(og, "ingest_office_into_entropy", fake_ingest, raising=False)

    card = TaskCard(id="k1", title="Kart", office="ofis1", goal="hedef")
    path = harness._write_local_report(card, "# Kart\n\ngovde")

    assert path is not None and path.exists()
    assert calls, "ingest_office_into_entropy hiç başarıyla çağrılmadı"
    assert calls[0]["store"] is None
    assert calls[0]["vault_path"] == board.vault_path


def test_ingest_signature_second_positional_is_store():
    """İmza sözleşmesi: ikinci parametre `store`, rapor yolu değil."""
    import inspect

    from entropy.brain.office_graph import ingest_office_into_entropy

    params = list(inspect.signature(ingest_office_into_entropy).parameters)
    assert params[:3] == ["office", "store", "vault_path"], params
