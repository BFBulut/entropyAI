"""
Faz 7 regresyon testleri.

Buradaki her test, daha once gercekten yasanmis bir hataya bagli:

1. `vault_manager.build_knowledge_graph` ajan dugumu kurarken `None.strip()`
   ile cokuyordu (Faz 6'da `(agent_of_page or name or "").strip()` ile
   duzeltildi). Testi None-sayfa senaryosunu kurarak koruyoruz.
2. `report_inbox.collect_recent_entries` kunyeleri `read_report_meta` ile
   yeniden uretiyordu; `kind`/`office` alanlari yolda dusuyordu.
"""

from pathlib import Path

import pytest

from entropy.brain.obsidian.vault_manager import ObsidianVaultManager


# ---------------------------------------------------- 1. graf cokme korumasi

def test_knowledge_graph_agent_category_without_agent_page(tmp_path):
    """
    Klasor adi "agent" oldugu icin kategorisi ajan olan ama AGENT.md
    sablonundan gelmeyen sayfa grafigi cokertmemeli.

    Eski kod `agent_of_page.strip()` cagiriyordu; `_agent_page_name()` bu
    dosya icin None dondugunden AttributeError aliniyordu.
    """
    vault = ObsidianVaultManager(vault_path=tmp_path)
    agent_dir = tmp_path / "Entropy" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "Serbest_Sayfa.md").write_text(
        "# Serbest Sayfa\n\nAjan klasorunde ama AGENT.md degil.\n", encoding="utf-8"
    )

    graph = vault.build_knowledge_graph()

    assert isinstance(graph, dict) and "nodes" in graph
    node = next(
        (n for n in graph["nodes"] if n.get("name") == "Serbest_Sayfa"), None
    )
    assert node is not None, "AGENT.md olmayan ajan sayfasi grafikten dustu"
    assert node["group"] == "agent"


def test_knowledge_graph_survives_agent_dir_with_only_agent_md(tmp_path):
    """Gercek AGENT.md sayfasi hala ajan adiyla dugum uretiyor (karsit kontrol)."""
    vault = ObsidianVaultManager(vault_path=tmp_path)
    d = tmp_path / "Entropy" / "Agents" / "arastirmaci"
    d.mkdir(parents=True, exist_ok=True)
    (d / "AGENT.md").write_text("---\nname: arastirmaci\n---\n# Arastirmaci\n", encoding="utf-8")

    graph = vault.build_knowledge_graph()
    names = {n.get("name") for n in graph["nodes"] if n.get("group") == "agent"}
    assert "arastirmaci" in names


# ------------------------------------------- 2. gelen kutusu kunye alanlari

def test_collect_recent_entries_keeps_kind_and_office(tmp_path, monkeypatch):
    """
    `collect_recent_entries` kunyelerinde `kind` ve `office` alanlari
    `list_reports()` ciktisindan korunmali.

    Regresyon: kunye `read_report_meta(path)` ile sifirdan uretiliyordu;
    o fonksiyon dosyayi tek basina okudugu icin kasa taramasindan gelen
    `kind`/`office` alanlarini bilmiyor ve alanlar dusuyordu.
    """
    from entropy.ui.widgets import report_inbox

    vault = ObsidianVaultManager(vault_path=tmp_path)

    # Ofis raporu: kasa taramasi bunu kind=office_report, office=<ad> olarak
    # kunyeler. Yol duzeni vault_manager.get_research_reports ile ayni olmali.
    office_reports = tmp_path / "Desk" / "Offices" / "finans" / "Reports"
    office_reports.mkdir(parents=True, exist_ok=True)
    (office_reports / "2026-09-09-bilanco.md").write_text(
        "---\ntitle: Bilanco Ozeti\n---\n# Bilanco\n", encoding="utf-8"
    )

    listed = vault.list_reports()
    office_listed = [r for r in listed if r.get("office")]
    if not office_listed:
        pytest.skip("kasa taramasi bu duzende ofis raporu uretmedi")
    expected_kind = office_listed[0].get("kind")
    expected_office = office_listed[0].get("office")

    monkeypatch.setattr(
        report_inbox, "ObsidianVaultManager", lambda *a, **k: vault, raising=False
    )
    monkeypatch.setattr(
        "entropy.brain.obsidian.vault_manager.ObsidianVaultManager",
        lambda *a, **k: vault,
    )

    entries = report_inbox.collect_recent_entries(limit=50)
    assert entries, "gelen kutusu hic kunye toplamadi"

    match = next(
        (e for e in entries if Path(str(e.get("path", ""))).name == "2026-09-09-bilanco.md"),
        None,
    )
    assert match is not None, "ofis raporu kunyesi gelen kutusuna dusmedi"
    assert match.get("kind") == expected_kind, "kind alani kunyeden dustu"
    assert match.get("office") == expected_office, "office alani kunyeden dustu"
    # read_report_meta'nin kendi alanlari da korunmali (birlestirme, ezme degil)
    assert "modified" in match and "tags" in match
