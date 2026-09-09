"""
Faz 7 — rapor akışının türe bağlanması, ofis alım tetikleyicisi, kasa hijyeni.

Kapsanan davranış:
- `ObsidianVaultManager.list_reports`: normal rapor + ofis raporu + wiki sorgu
  sayfası üçü de listeye girer, `kind` alanı doğrudur, `kinds=` süzer.
- `orchestrator_context`: görev + son raporlar + komşular, <= 1200 token,
  "Entropy" dizgesi sızmaz.
- `to_view_data`: graf boşken bile ajan ve rapor düğümleri döner.
- `ingest_office_into_entropy`: `status: done` projesi için `produced` kenarı.
- `schedule_office_ingest`: aralık kısıtı (debounce) çalışır, kota harcamaz.
- `vault_hygiene`: artık AgentDesk klasörleri, hayalet ofisler, kuru koşum
  arşivleme (silme yok).

Tüm testler tmp kasada çalışır; gerçek Obsidian kasasına yazılmaz.
"""

from pathlib import Path

import pytest

from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.memory.office_graph import (
    OfficeGraph,
    desk_office_dir,
    ingest_office_into_entropy,
    orchestrator_context,
    schedule_office_ingest,
)
from entropy.memory.vault_hygiene import (
    archive_stale,
    find_ghost_offices,
    find_stale_agentdesk_dirs,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def vault(tmp_path):
    """Üç rapor türünü de içeren tmp kasa."""
    root = tmp_path / "Entropy"
    _write(root / "Reports" / "arastirma.md", "---\ntitle: Araştırma\n---\n\nGövde.\n")
    _write(
        root / "Desk" / "Offices" / "medya" / "reports" / "2026-09-01-kampanya.md",
        "---\ntype: office_report\noffice: medya\ntitle: Kampanya\n---\n\nÖzet.\n",
    )
    _write(
        root / "Skills" / "research" / "wiki" / "queries" / "2026-09-01-api.md",
        "---\ntype: query\nskill: research\ntitle: API sorgusu\n---\n\nCevap.\n",
    )
    return tmp_path


# --------------------------------------------------------------- rapor akışı


def test_list_reports_collects_all_kinds(vault):
    entries = ObsidianVaultManager(vault).list_reports()
    by_kind = {}
    for entry in entries:
        by_kind.setdefault(entry["kind"], []).append(entry)

    assert set(by_kind) >= {"report", "office_report", "query"}, by_kind
    assert by_kind["office_report"][0]["office"] == "medya"
    assert by_kind["query"][0]["skill"] == "research"
    # Her künye Rapor Merkezi'nin beklediği alanları taşır.
    for entry in entries:
        assert {"path", "title", "modified", "kind", "office", "skill", "importance"} <= set(entry)
        assert 0.0 <= entry["importance"] <= 1.0


def test_list_reports_kinds_filter_is_backward_compatible(vault):
    manager = ObsidianVaultManager(vault)
    all_entries = manager.list_reports()
    only_office = manager.list_reports(kinds=["office_report"])

    assert len(all_entries) >= 3
    assert len(only_office) == 1
    assert only_office[0]["kind"] == "office_report"


def test_frontmatter_type_beats_directory_rule(vault):
    # Reports/ altında ama `type: query`: tür ön bilgiden gelir.
    _write(
        vault / "Entropy" / "Reports" / "gizli-sorgu.md",
        "---\ntype: query\ntitle: Sorgu\n---\n\nMetin.\n",
    )
    kinds = {
        Path(e["path"]).name: e["kind"] for e in ObsidianVaultManager(vault).list_reports()
    }
    assert kinds["gizli-sorgu.md"] == "query"
    assert kinds["arastirma.md"] == "report"


def test_archive_subtree_is_not_listed(vault):
    _write(vault / "Entropy" / "_archive" / "2026-01-01" / "Reports" / "eski.md", "eski")
    names = {Path(e["path"]).name for e in ObsidianVaultManager(vault).list_reports()}
    assert "eski.md" not in names


# ------------------------------------------------------- orkestratör bağlamı


def test_orchestrator_context_uses_reports_and_stays_in_budget(tmp_path):
    root = desk_office_dir("medya", tmp_path)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    for i in range(5):
        _write(
            root / "reports" / f"2026-09-0{i + 1}-rapor.md",
            f"---\ntype: office_report\n---\n\nEntropy raporu {i}: " + ("kampanya ölçümü " * 200),
        )
    graph = OfficeGraph("medya", tmp_path)
    graph.add_note("karar", "Bütçe kararı", "Kampanya bütçesi iki katına çıkarıldı.")
    graph.add_note("bulgu", "Ölçüm", "Dönüşüm oranı yüzde üç.")

    text = orchestrator_context("medya", task="kampanya bütçesi", vault_path=tmp_path)

    assert "## Son raporlar" in text
    assert "Görev: kampanya bütçesi" in text
    assert "Entrop" not in text  # ters yön yasağı
    assert len(text) // 4 <= 1200


def test_orchestrator_context_empty_office_returns_empty(tmp_path):
    desk_office_dir("bos", tmp_path).mkdir(parents=True, exist_ok=True)
    assert orchestrator_context("bos", task="herhangi", vault_path=tmp_path) == ""


# ---------------------------------------------------------- görünüm verisi


def test_view_data_never_empty_for_small_office(tmp_path):
    root = desk_office_dir("kucuk", tmp_path)
    (root / "agents" / "yazar").mkdir(parents=True, exist_ok=True)
    _write(root / "reports" / "2026-09-01-ilk.md", "ilk rapor")

    data = OfficeGraph("kucuk", tmp_path).to_view_data()
    kinds = {n["kind"] for n in data["nodes"]}

    assert "ajan" in kinds and "rapor" in kinds
    assert data["links"], "sanal düğümler ofis merkezine bağlanmalı"
    # Sanal düğümler diske yazılmaz.
    assert not (root / "memory" / "graph.json").exists()


# ------------------------------------------------------------- proje alımı


def test_done_project_produces_report_edges(tmp_path):
    from entropy.memory.graph_store import GraphStore
    from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

    root = desk_office_dir("medya", tmp_path)
    proj = root / "projects" / "kampanya"
    _write(proj / "PROJECT.md", "---\ntitle: Kampanya\nstatus: done\n---\n\nBitti.\n")
    _write(proj / "reports" / "sonuc.md", "Kampanya sonuç raporu.")
    _write(root / "projects" / "devam" / "PROJECT.md", "---\nstatus: active\n---\n")

    store = GraphStore(memory=CognitiveMemorySystem(db_path=tmp_path / "desk.db"))
    stats = ingest_office_into_entropy("medya", store=store, vault_path=tmp_path)

    assert stats["done_projects"] == 1
    task_id = "desk-medya-proje-kampanya"
    produced = store.get_edges(src=task_id, edge_type="produced")
    assert len(produced) == 1
    assert "sonuc" in produced[0].dst


# --------------------------------------------------------- alım tetikleyici


def test_schedule_office_ingest_debounces(tmp_path, monkeypatch):
    from entropy.memory import office_graph

    state = tmp_path / "office_ingest.state.json"
    monkeypatch.setattr(office_graph, "_office_ingest_state_path", lambda: state)

    calls = []
    monkeypatch.setattr(
        office_graph, "ingest_all_offices",
        lambda store=None, vault_path=None: calls.append(1) or [],
    )

    class _FakeStore:
        def ingest_desk_memory(self, vault_path=None):
            return {"offices": 0}

    first = office_graph.schedule_office_ingest(store=_FakeStore(), vault_path=tmp_path)
    second = office_graph.schedule_office_ingest(store=_FakeStore(), vault_path=tmp_path)

    assert first["ran"] is True
    assert second["ran"] is False and second["skipped"] == "debounce"
    assert len(calls) == 1

    forced = office_graph.schedule_office_ingest(
        store=_FakeStore(), vault_path=tmp_path, force=True
    )
    assert forced["ran"] is True and len(calls) == 2


# ------------------------------------------------------------- kasa hijyeni


def test_hygiene_finds_stale_and_ghost_dirs(tmp_path):
    root = tmp_path / "Entropy"
    _write(root / "AgentDesk" / "office_abc" / "layout.json", "{}")
    _write(root / "AgentDesk" / "office_def" / "layout.json", "{}")
    _write(root / "AgentDesk" / "global_template" / "layout.json", "{}")
    _write(root / "Desk" / "Offices" / "hayalet" / "layout.json", "{}")
    _write(root / "Desk" / "Offices" / "gercek" / "OFFICE.md", "---\nname: gercek\n---\n")

    stale = find_stale_agentdesk_dirs(tmp_path)
    ghosts = find_ghost_offices(tmp_path)

    assert {s["name"] for s in stale} == {"office_abc", "office_def"}
    assert all(s["files"] >= 1 for s in stale)
    assert [g["name"] for g in ghosts] == ["hayalet"]


def test_archive_stale_dry_run_moves_nothing(tmp_path):
    root = tmp_path / "Entropy"
    _write(root / "AgentDesk" / "office_abc" / "layout.json", "{}")
    stale = find_stale_agentdesk_dirs(tmp_path)

    plan = archive_stale(stale, vault_path=tmp_path, dry_run=True, date="2026-09-09")
    assert plan["dry_run"] is True and len(plan["planned"]) == 1
    assert (root / "AgentDesk" / "office_abc").is_dir()
    assert not (root / "_archive").exists()

    done = archive_stale(stale, vault_path=tmp_path, dry_run=False, date="2026-09-09")
    assert len(done["moved"]) == 1
    assert not (root / "AgentDesk" / "office_abc").exists()
    assert (root / "_archive" / "2026-09-09" / "office_abc" / "layout.json").exists()


def test_archive_stale_rejects_paths_outside_vault(tmp_path):
    outside = tmp_path / "disarida"
    outside.mkdir()
    result = archive_stale([str(outside)], vault_path=tmp_path, dry_run=False)
    assert result["moved"] == []
    assert result["skipped"][0]["reason"] == "kasa_disi"
    assert outside.is_dir()
