"""
Faz 8 — graf verisi (M1-M6) testleri.

Kapsam: wikilink temizliği, test kalıntısı projelerin dışlanması, GraphStore
köprüsü, `level`/`degree`/`child_count`/`short_label`, topluluk kalitesi ve
aşırı büyük dalların bölünmesi. Tüm testler geçici kasada çalışır; gerçek kasaya
ve gerçek belleğe dokunmaz.
"""

import json
import time
from pathlib import Path

import pytest

from entropy.brain import graph_enrich as ge
from entropy.brain.graph_store import GraphStore
from entropy.brain.obsidian.vault_manager import (
    ObsidianVaultManager,
    clear_graph_cache,
    is_test_artifact_name,
    is_test_artifact_path,
    strip_code_spans,
)
from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem
from entropy.ui.widgets.knowledge_graph import (
    KnowledgeGraphWidget,
    _cognitive_node_name,
)


# --- M1: wikilink temizliği --------------------------------------------------

def test_wikilinks_ignore_code_blocks_and_inline_code(tmp_path):
    vm = ObsidianVaultManager(vault_path=tmp_path)
    content = (
        "Gerçek bağ: [[Hedef Sayfa]]\n\n"
        "```markdown\n"
        "Örnek sözdizimi: [[wikilink]] ve [[Wikilinks]]\n"
        "```\n\n"
        "Satır içi `[[Wikilink]]` örneği de bağ değildir.\n"
        "    [[Girintili Kod Ornegi]]\n"
    )
    targets = [l["target"] for l in vm.extract_wikilinks(content)]
    assert targets == ["Hedef Sayfa"]
    assert "[[wikilink]]" not in strip_code_spans(content)


def test_clean_links_drops_dangling_selfloops_duplicates_and_catalog():
    nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    links = [
        {"source": "a", "target": "b", "is_tree_link": True},
        {"source": "a", "target": "b"},                       # yinelenen (wikilink)
        {"source": "b", "target": "a"},                       # ters yön yinelemesi
        {"source": "a", "target": "a"},                       # öz-döngü
        {"source": "a", "target": "wikilinks"},               # sarkan
        {"source": "b", "target": "c", "is_catalog_link": True},
        {"source": "b", "target": "c", "is_similarity_link": True, "weight": 0.8},
    ]
    out = ge.clean_links(nodes, links)
    pairs = sorted((l["source"], l["target"]) for l in out)
    assert pairs == [("a", "b"), ("b", "c")]
    tree = next(l for l in out if l["kind"] == ge.KIND_TREE)
    sim = next(l for l in out if l["kind"] == ge.KIND_SIMILARITY)
    assert tree["source"] == "a" and tree["target"] == "b"
    assert 0.0 <= tree["weight"] <= 1.0 and sim["weight"] == pytest.approx(0.8)
    assert all("is_catalog_link" not in l for l in out)


# --- M2: test kalıntısı projeler, düğüm adları -------------------------------

def test_test_artifact_projects_excluded_from_vault_graph(tmp_path):
    vm = ObsidianVaultManager(vault_path=tmp_path)
    vm.save_research_report("Gercek Rapor", "# Gercek", project_name="EntropiAI")
    junk = tmp_path / "Entropy" / "Projects" / "test_bridge_background_task_fa0" / "Reports"
    junk.mkdir(parents=True, exist_ok=True)
    (junk / "Artik.md").write_text("# Pytest artigi", encoding="utf-8")

    assert is_test_artifact_name("test_bridge_background_task_fa0")
    assert is_test_artifact_path(junk / "Artik.md")

    clear_graph_cache()
    data = vm.build_knowledge_graph()
    paths = [str(n.get("path", "")) for n in data["nodes"]]
    assert any("Gercek Rapor" in p for p in paths)
    assert not any("test_bridge_background_task_fa0" in p for p in paths)


def test_cognitive_node_name_is_single_line_short_and_unique():
    counts = {}
    a = _cognitive_node_name("# Pazar araştırması\n\nOfis: CanivoPets\n", counts)
    b = _cognitive_node_name("# Pazar araştırması\n\nOfis: Baska\n", counts)
    assert a == "Pazar araştırması"
    assert b != a and b.startswith("Pazar")
    long = _cognitive_node_name("x" * 120, counts)
    assert "\n" not in long and len(long) <= 40


# --- M3: GraphStore köprüsü --------------------------------------------------

def _store(tmp_path) -> GraphStore:
    mem = CognitiveMemorySystem(db_path=tmp_path / "mem.db")
    return GraphStore(memory=mem)


def test_graph_store_bridge_writes_time_importance_type_and_communities(tmp_path):
    store = _store(tmp_path)
    now = time.time()
    store.upsert_node("n-rapor", "report", "ALM Risk Raporu", "gövde",
                      importance=0.83, provenance=str(tmp_path / "ALM.md"))
    store.upsert_node("com-1", "community", "ALM Kümesi", "özet")
    store.add_edge("n-rapor", "com-1", "member_of", weight=1.0)
    with store._connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO communities (id, label, summary, member_count)"
            " VALUES (?, ?, ?, ?)", ("com-1", "ALM Kümesi", "özet", 1))

    nodes = [
        {"id": "Reports/ALM", "name": "ALM Risk Raporu", "group": "Reports",
         "info": f"Obsidian Dosyası: {tmp_path / 'ALM.md'}"},
        {"id": "hub-skills", "name": "Yetenekler", "group": "hub"},
    ]
    links = []
    stats = ge.bridge_graph_store(nodes, links, store)
    ge.apply_default_fields(nodes)

    rep = next(n for n in nodes if n["id"] == "Reports/ALM")
    assert stats["matched"] >= 1
    assert rep["importance"] == pytest.approx(0.83, abs=1e-3)
    assert rep["type"] == "report"
    assert rep["t_valid_from"] > 0 and rep["t_valid_from"] <= now + 5
    assert rep["community_id"] == "com-1"
    comm = next(n for n in nodes if n["group"] == "community")
    assert comm["id"] == "com-1"
    assert any(l["kind"] == ge.KIND_MEMBER_OF for l in links)
    # Eşleşmeyen düğüm de alanlarını alır (kontrol şeridi tek eksik alanda kapanıyordu)
    hub = next(n for n in nodes if n["id"] == "hub-skills")
    assert hub["importance"] is not None and hub["type"] and hub["t_valid_from"] is not None


# --- M4: seviye, derece, etiket ---------------------------------------------

def _tree(source, target):
    return {"source": source, "target": target, "kind": ge.KIND_TREE, "is_tree_link": True}


def test_levels_degree_child_count_and_short_labels():
    nodes = [
        {"id": "ego-entropy-core", "name": "Çekirdek", "group": "ego"},
        {"id": "hub-skills", "name": "Yetenekler", "group": "hub"},
        {"id": "subhub-skill-fin", "name": "financial-auditor", "group": "skill"},
        {"id": "subbranch-fin-risk-alm", "name": "ALM & Risk", "group": "subbranch"},
    ]
    links = [
        _tree("ego-entropy-core", "hub-skills"),
        _tree("hub-skills", "subhub-skill-fin"),
        _tree("subhub-skill-fin", "subbranch-fin-risk-alm"),
    ]
    for i in range(6):
        nid = f"Reports/Gorev_autonomous-agent_2026-09-0{i}_Harness Mimarisi Faz{90 + i}"
        nodes.append({"id": nid, "name": nid.split("/", 1)[1], "group": "Reports"})
        links.append(_tree("subbranch-fin-risk-alm", nid))

    ge.assign_levels(nodes, links)
    ge.assign_labels(nodes)

    by_id = {n["id"]: n for n in nodes}
    assert by_id["ego-entropy-core"]["level"] == 0
    assert by_id["hub-skills"]["level"] == 1
    assert by_id["subhub-skill-fin"]["level"] == 2
    assert by_id["subbranch-fin-risk-alm"]["level"] == 3
    assert by_id["subbranch-fin-risk-alm"]["child_count"] == 6
    assert by_id["hub-skills"]["degree"] == 2
    leaves = [n for n in nodes if n["group"] == "Reports"]
    assert all(n["level"] == 4 for n in leaves)
    shorts = [n["short_label"] for n in nodes]
    assert len(set(shorts)) == len(shorts)              # tekil
    assert all(len(s) <= ge.MAX_SHORT_LABEL for s in shorts)
    # Faz numarası ayırt edici işaretçi olarak etikette kalır.
    assert any("F90" in n["short_label"] for n in leaves)


def test_short_label_prefers_topic_over_repeated_prefix():
    taken = set()
    a = ge.make_short_label("Gorev_autonomous-agent_2026-09-01_Otonom Ajan Mimarisi Faz 111", taken)
    b = ge.make_short_label("Gorev_autonomous-agent_2026-09-02_Otonom Ajan Mimarisi Faz 112", taken)
    assert a != b
    assert len(a) <= 28 and len(b) <= 28
    assert "Gorev" not in a


# --- M5 / M6: topluluk ve dal bölme -----------------------------------------

def test_split_large_parents_caps_children_at_80():
    nodes = [{"id": "p", "name": "ALM & Risk", "group": "subbranch"}]
    links = []
    for i in range(200):
        topic = ["Volatilite", "Kredi", "Likidite", "Basel"][i % 4]
        nid = f"r{i}"
        nodes.append({"id": nid, "name": f"{topic} Raporu Numara {i}", "group": "Reports"})
        links.append(_tree("p", nid))

    created = ge.split_large_parents(nodes, links, max_children=80)
    assert created >= 3
    counts = {}
    for l in links:
        if l.get("kind") == ge.KIND_TREE:
            counts[l["source"]] = counts.get(l["source"], 0) + 1
    assert max(counts.values()) <= 80
    assert all(n["id"].startswith("topic-p-") for n in nodes if n.get("group") == "topic")
    # Yapraklar kaybolmaz, yalnızca ebeveyni değişir.
    assert sum(1 for n in nodes if n["group"] == "Reports") == 200


def test_communities_are_labelled_and_not_tiny():
    nodes = []
    links = []
    for c in range(4):
        hub = f"hub{c}"
        nodes.append({"id": hub, "name": f"Küme {c}", "group": "subbranch"})
        for i in range(10):
            nid = f"n{c}-{i}"
            nodes.append({"id": nid, "name": f"Konu{c} Rapor {i}", "group": "Reports"})
            links.append(_tree(hub, nid))
            if i:
                links.append({"source": f"n{c}-{i-1}", "target": nid,
                              "kind": ge.KIND_SIMILARITY, "weight": 0.9})
    comms = ge.detect_communities(nodes, links)
    if not comms:                                   # networkx yoksa atla
        pytest.skip("networkx yok")
    sizes = {}
    for cid in comms.values():
        sizes[cid] = sizes.get(cid, 0) + 1
    assert min(sizes.values()) >= ge.MIN_COMMUNITY_SIZE
    labels = ge.label_communities(nodes, comms)
    assert all(labels[c] for c in sizes)
    for n in nodes:
        n["community"] = comms.get(n["id"])
    assert ge.modularity(nodes, links) > 0.3


# --- uçtan uca ---------------------------------------------------------------

def test_unified_graph_is_clean_and_enriched(qapp, tmp_path):
    vm = ObsidianVaultManager(vault_path=tmp_path)
    for i in range(12):
        vm.save_research_report(
            f"Gorev_autonomous-agent_2026-09-0{i % 9}_Harness Mimarisi Faz{80 + i}",
            "# Rapor\n\nÖrnek: ```\n[[wikilinks]]\n```\n[[Gercek Hedef]]\n",
            skill_name="autonomous-agent",
        )
    clear_graph_cache()
    widget = KnowledgeGraphWidget(vault_manager=vm)
    try:
        data = widget.build_unified_graph()
    finally:
        widget.close()

    nodes, links = data["nodes"], data["links"]
    ids = {n["id"] for n in nodes}
    assert all(l["source"] in ids and l["target"] in ids for l in links)     # sarkan yok
    assert all(l["source"] != l["target"] for l in links)                    # öz-döngü yok
    seen = set()
    for l in links:
        key = (l["source"], l["target"], l.get("kind"))
        assert key not in seen
        seen.add(key)
    assert all("is_catalog_link" not in l for l in links)
    assert all(l.get("kind") and l.get("weight") is not None for l in links)

    for n in nodes:
        assert "\n" not in str(n.get("name", ""))
        assert n.get("level") is not None
        assert n.get("degree") is not None
        assert n.get("short_label") and len(n["short_label"]) <= ge.MAX_SHORT_LABEL
        assert n.get("importance") is not None
        assert n.get("type")
        assert n.get("t_valid_from") is not None
    shorts = [n["short_label"] for n in nodes]
    assert len(set(shorts)) == len(shorts)
    # JSON serileşebilir olmalı (UI şablonuna gömülüyor).
    json.dumps(data, ensure_ascii=False)


def test_enrich_is_idempotent_and_backward_compatible():
    nodes = [
        {"id": "ego-entropy-core", "name": "Çekirdek", "group": "ego", "cluster_group": "ego"},
        {"id": "hub-skills", "name": "Yetenekler", "group": "hub", "cluster_group": "skills"},
        {"id": "Reports/A", "name": "ALM Risk Raporu", "group": "Reports",
         "cluster": "skill:fin", "parent_hub": "hub-skills"},
    ]
    links = [
        _tree("ego-entropy-core", "hub-skills"),
        _tree("hub-skills", "Reports/A"),
    ]
    data = ge.enrich_graph({"nodes": nodes, "links": links})
    first = json.dumps(data, ensure_ascii=False, sort_keys=True)
    again = json.dumps(ge.enrich_graph(data), ensure_ascii=False, sort_keys=True)
    assert first == again
    # Eski alanlar korunur.
    rep = next(n for n in data["nodes"] if n["id"] == "Reports/A")
    assert rep["cluster"] == "skill:fin" and rep["parent_hub"] == "hub-skills"
    assert data["links"][0].get("is_tree_link") is True
