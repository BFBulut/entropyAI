"""
Faz 6 — Desk ofis belleği grafı, Entropy'ye tek yönlü akış, roster, geçiş.

Kapsanan davranış:
- `OfficeGraph`: not ekleme, bağ, komşu, sorgu, görünüm verisi, markdown dışa
  aktarım, ajan MEMORY.md girdilerinin düğümleşmesi.
- A-MEM: yeni not komşusunun "## İlgili" bölümünü günceller.
- `ingest_office_into_entropy`: kapsam `desk:<ofis>`, `member_of` kenarları.
- Ters yön yasağı: ofis grafında ve orkestratör bağlamında "Entropy" yok.
- `desk_roster`, damıtma dışlaması (`Desk` kaynak değil), geçiş kuru koşumu.

Tüm testler tmp kasada çalışır; gerçek Obsidian kasasına yazılmaz.
"""

from pathlib import Path

import pytest

from entropy.memory.office_graph import (
    OfficeGraph,
    desk_office_dir,
    desk_roster,
    desk_scopes,
    ingest_office_into_entropy,
    migrate_legacy_offices,
    office_scope,
    orchestrator_context,
)


@pytest.fixture()
def office(tmp_path):
    """tmp kasada `Desk/Offices/medya` iskeleti kurar."""
    root = desk_office_dir("medya", tmp_path)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "projects" / "kampanya").mkdir(parents=True, exist_ok=True)
    (root / "agents" / "yaratici").mkdir(parents=True, exist_ok=True)
    (root / "OFFICE.md").write_text(
        "---\nname: medya\npurpose: Kampanya üretir.\norchestrator: sef\n---\n\n# medya\n",
        encoding="utf-8",
    )
    (root / "reports" / "2026-09-01_kampanya.md").write_text(
        "# Kampanya raporu\nSonuç kabul edildi.\n", encoding="utf-8"
    )
    (root / "reports" / "2026-09-05_olcum.md").write_text(
        "# Ölçüm raporu\nCTR yüzde 2.4.\n", encoding="utf-8"
    )
    return tmp_path


# --------------------------------------------------------------------- graf


def test_add_note_writes_graph_json_and_markdown(office):
    g = OfficeGraph("medya", office)
    node = g.add_note("proje", "Kampanya kartı", "Yeni ürün için lansman kampanyası.")

    assert node["kind"] == "proje"
    graph_path = desk_office_dir("medya", office) / "memory" / "graph.json"
    note_path = desk_office_dir("medya", office) / "memory" / node["note"]
    assert graph_path.exists() and note_path.exists()
    assert "Kampanya kartı" in note_path.read_text(encoding="utf-8")
    # yeniden yükleme kalıcılığı
    assert node["id"] in OfficeGraph("medya", office).nodes


def test_link_neighbors_and_query(office):
    g = OfficeGraph("medya", office)
    proje = g.add_note("proje", "Lansman kampanyası", "Ürün lansmanı planı.", auto_link=False)
    karar = g.add_note("karar", "Bütçe kararı", "Bütçe 40 bin lira olarak onaylandı.", auto_link=False)
    bulgu = g.add_note("bulgu", "Ölçüm bulgusu", "Tıklama oranı yüzde 2.4 ölçüldü.", auto_link=False)

    g.link(karar["id"], proje["id"], "decided")
    g.link(proje["id"], bulgu["id"], "produced")
    g.save()

    n1 = {n["id"] for n in g.neighbors(proje["id"], depth=1)}
    assert n1 == {karar["id"], bulgu["id"]}
    assert karar["id"] in {n["id"] for n in g.neighbors(bulgu["id"], depth=2)}

    hits = [nid for nid, _ in g.query("bütçe onayı", k=2)]
    assert hits and hits[0] == karar["id"]


def test_amem_updates_neighbor_related_section(office):
    g = OfficeGraph("medya", office)
    first = g.add_note("bulgu", "Tıklama oranı ölçümü", "Tıklama oranı yüzde 2.4 ölçüldü.")
    second = g.add_note("karar", "Tıklama oranı hedefi", "Tıklama oranı hedefi yüzde 3 yapıldı.")

    first_note = desk_office_dir("medya", office) / "memory" / first["note"]
    text = first_note.read_text(encoding="utf-8")
    assert "## İlgili" in text
    assert f"[[{second['title']}]]" in text  # komşu notu geriye doğru güncellendi
    assert any(
        e["type"] == "related" and {e["src"], e["dst"]} == {first["id"], second["id"]}
        for e in g.edges
    )


def test_agent_memory_entries_become_nodes_linked_to_agent(office):
    agent_memory = desk_office_dir("medya", office) / "agents" / "yaratici" / "MEMORY.md"
    agent_memory.write_text(
        "# Ajan Belleği\n\n## Öğrenilenler\n"
        "- Kısa videolar uzun videolardan daha çok izleniyor.\n"
        "- Başlıkta rakam kullanmak tıklamayı artırıyor.\n",
        encoding="utf-8",
    )
    g = OfficeGraph("medya", office)
    added = g.ingest_agent_memories()

    assert added == 2
    agent_id = "ajan-yaratici"
    assert agent_id in g.nodes
    member_edges = [e for e in g.edges if e["type"] == "member_of" and e["dst"] == agent_id]
    assert len(member_edges) == 2


def test_view_data_and_export_markdown(office):
    g = OfficeGraph("medya", office)
    a = g.add_note("proje", "Lansman", "Lansman planı.", auto_link=False)
    b = g.add_note("bulgu", "Sonuç", "Kampanya sonucu iyi.", auto_link=False)
    g.link(a["id"], b["id"], "produced")

    view = g.to_view_data()
    ids = {n["id"] for n in view["nodes"]}
    # Faz 7: gerçek düğümlerin yanına ajan/rapor/ofis sanal düğümleri de eklenir
    # (küçük ofiste sekme boş görünmesin diye); gerçek düğümler yine listede.
    assert {a["id"], b["id"]} <= ids
    real = {n["id"] for n in view["nodes"] if not n.get("virtual")}
    assert real == {a["id"], b["id"]}
    produced = [l for l in view["links"] if l["type"] == "produced"]
    assert produced and produced[0]["source"] == a["id"]
    assert all("group" in n and "kind" in n for n in view["nodes"])

    md = g.export_markdown()
    assert "Lansman" in md and "Bağ sayısı: 1" in md


# ------------------------------------------------------- Entropy'ye akış


def _store(tmp_path):
    from entropy.memory.graph_store import GraphStore
    from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

    return GraphStore(memory=CognitiveMemorySystem(db_path=tmp_path / "desk.db"))


def test_ingest_office_uses_desk_scope_and_member_of(office):
    g = OfficeGraph("medya", office)
    g.add_note("proje", "Lansman kampanyası", "Ürün lansmanı planı.", auto_link=False)
    g.add_note("karar", "Bütçe kararı", "Bütçe onaylandı.", auto_link=False)

    store = _store(office)
    stats = ingest_office_into_entropy("medya", store=store, vault_path=office)

    assert stats["scope"] == "desk:medya" == office_scope("medya")
    assert stats["reports"] == 2  # reports/ altındaki iki md
    scoped = store.all_nodes(scopes=["desk:medya"])
    titles = {n.title for n in scoped}
    assert {"Lansman kampanyası", "Bütçe kararı", "kampanya"} <= titles
    office_node = store.get_node(stats["office_id"])
    assert office_node is not None and office_node.type == "office"
    for node in scoped:
        if node.id == stats["office_id"]:
            continue
        assert store.get_edges(src=node.id, dst=stats["office_id"], edge_type="member_of")


def test_desk_scopes_visible_in_default_scopes(office):
    from entropy.memory.graph_store import GraphStore

    assert desk_scopes(office) == ["desk:medya"]
    scopes = GraphStore.default_scopes(active_office=None, vault_path=office)
    assert "general" in scopes and "desk:medya" in scopes


def test_no_reverse_flow_office_graph_has_no_entropy_trace(office):
    g = OfficeGraph("medya", office)
    g.add_note("proje", "Lansman kampanyası", "Ürün lansmanı planı.")
    store = _store(office)
    store.upsert_node("gizli-1", "fact", "Entropy AI çekirdek notu", body="Entropy sırrı")
    ingest_office_into_entropy("medya", store=store, vault_path=office)

    reloaded = OfficeGraph("medya", office)
    graph_text = (desk_office_dir("medya", office) / "memory" / "graph.json").read_text(
        encoding="utf-8"
    )
    assert "Entropy" not in graph_text and "entropy" not in graph_text
    assert "gizli-1" not in graph_text
    assert len(reloaded.nodes) == len(g.nodes)  # Entropy tarafından düğüm eklenmedi

    ctx = orchestrator_context("medya", task="lansman", vault_path=office)
    assert "Lansman kampanyası" in ctx
    assert "Entropy" not in ctx and "entropy" not in ctx


# ---------------------------------------------------------------- roster


def test_desk_roster_lists_orchestrator_purpose_and_last_report(office):
    roster = desk_roster(office)

    assert len(roster) == 1
    row = roster[0]
    assert row["office"] == "medya"
    assert row["orchestrator"] == "sef"
    assert row["purpose"] == "Kampanya üretir."
    assert row["last_report"] == "2026-09-05_olcum.md"
    assert row["agents"] == ["yaratici"]


def test_desk_dir_is_not_a_distillation_source(office):
    from entropy.memory.playbook import _NON_REPORT_DIRS, discover_reports

    assert "desk" in _NON_REPORT_DIRS
    # Damıtma eşiğini (400 bayt) aşan iki dosya: biri Desk'te, biri kasada.
    big = "# Başlık\n" + ("Bu bir gerçek rapor gövdesidir. " * 40)
    (desk_office_dir("medya", office) / "reports" / "buyuk.md").write_text(big, encoding="utf-8")
    normal = office / "Entropy" / "Reports"
    normal.mkdir(parents=True, exist_ok=True)
    (normal / "kasa_raporu.md").write_text(big, encoding="utf-8")

    reports = discover_reports(vault_path=office)
    assert any(p.name == "kasa_raporu.md" for p in reports)
    assert not any("Desk" in str(p) for p in reports)


# ---------------------------------------------------------------- geçiş


def test_migrate_legacy_offices_dry_run_then_apply(tmp_path):
    legacy = tmp_path / "Entropy" / "Offices"
    (legacy / "arastirma-ofisi").mkdir(parents=True)
    (legacy / "arastirma-ofisi" / "OFFICE.md").write_text("tohum", encoding="utf-8")
    (legacy / "medya" / "reports").mkdir(parents=True)
    (legacy / "medya" / "OFFICE.md").write_text("kullanici", encoding="utf-8")
    (legacy / ".seeded.json").write_text("{}", encoding="utf-8")
    agents = tmp_path / "Entropy" / "Agents"
    for name in ("orkestrator", "degerlendirici", "analist", "yazar"):
        (agents / name).mkdir(parents=True)

    plan = migrate_legacy_offices(vault_path=tmp_path, dry_run=True)
    assert plan["dry_run"] and not plan["applied"]
    assert [Path(m["from"]).name for m in plan["moves"]] == ["medya"]
    deleted = {Path(p).name for p in plan["deletes"]}
    assert {"arastirma-ofisi", ".seeded.json", "orkestrator", "degerlendirici"} == deleted
    assert {Path(p).name for p in plan["kept"]} == {"analist", "yazar"}
    assert (legacy / "medya").exists()  # kuru koşum dokunmadı

    applied = migrate_legacy_offices(vault_path=tmp_path, dry_run=False)
    assert applied["applied"]
    assert desk_office_dir("medya", tmp_path).is_dir()
    assert not (legacy / "arastirma-ofisi").exists()
    assert not (agents / "orkestrator").exists()
    assert (agents / "analist").is_dir()
