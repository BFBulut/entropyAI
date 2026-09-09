"""
Faz 3c — ofis belleği, ofis raporu, bilgi grafiği ofis/ajan düğümleri.

Kapsanan davranış:
- `append_office_memory` / `consolidate_office_memory` / `load_office_memory`:
  Offices/<ofis>/MEMORY.md, 10 kayıtta LLM'siz konsolidasyon, ≤ 6000 karakter.
- Bağlam kurucu: meta["office"] varsa 300 token'lık ofis belleği bölümü.
- Ofis raporu: wiki sorgu sayfası + Offices/<ofis>/reports/ altında wikilink'li
  kısa özet (kopya değil) + ofis log.md.
- Damıtma: Offices/ kaynak sayılmaz; ofis raporu geri çağırma havuzuna girer.
- Bilgi grafiği: office/agent/query düğümleri ve kenarları, renk/ikon eşlemesi.
- Aktarım: ofis raporu handoff olarak okunmaz.

Tüm testler tmp kasada çalışır; gerçek Obsidian kasasına yazılmaz.
"""

from pathlib import Path

import pytest

from entropy.memory import agent_memory as am
from entropy.memory import wiki


class FakeMemory:
    """Bellek sistemi yerine geçen kayıt toplayıcı (gömme maliyeti ödenmesin)."""

    def __init__(self):
        self.nodes = []

    def store_node(self, category, content, importance=0.5, metadata=None):
        self.nodes.append({"category": category, "content": content, "metadata": metadata or {}})
        return None, True


def _entry(title, vault, **extra):
    base = {
        "title": title,
        "result": "kabul",
        "grade": 0.82,
        "children_count": 3,
        "output_paths": [str(vault / "Entropy" / "Reports" / "Cikti.md")],
        "vault_path": vault,
    }
    base.update(extra)
    return base


# --------------------------------------------------------------------------
# Ofis belleği
# --------------------------------------------------------------------------


def test_append_office_memory_writes_expected_path_and_fields(tmp_path):
    path = am.append_office_memory("Medya Ofisi", _entry("kampanya kartı", tmp_path, learning="Kabul ölçütü kartta yazılmalı."))

    assert path == tmp_path / "Entropy" / "Desk" / "Offices" / "Medya Ofisi" / "MEMORY.md"
    text = path.read_text(encoding="utf-8")
    assert "office: Medya Ofisi" in text
    assert "Ofis Belleği" in text
    assert "kampanya kartı" in text
    assert "not: 0.82" in text
    assert "3 alt kart" in text
    assert "[[Cikti]]" in text
    assert "- Kabul ölçütü kartta yazılmalı." in text
    # Ajan belleği ayrı ağaçta kalır: iki sahip birbirinin dosyasına yazmaz.
    assert not (tmp_path / "Entropy" / "Agents" / "Medya Ofisi").exists()


def test_office_memory_consolidates_after_ten_entries_and_stays_under_cap(tmp_path):
    for i in range(24):
        am.append_office_memory(
            "ofis",
            _entry(f"kart {i}", tmp_path, learning=f"öğrenim {i} " + "x" * 150),
        )
    path = am.office_memory_path("ofis", tmp_path)
    text = path.read_text(encoding="utf-8")

    assert len(text) <= am.MEMORY_MAX_CHARS
    assert am.ARCHIVE_TITLE in text
    assert am.AUTO_MARKER in text
    journal = [l for l in text.splitlines() if l.startswith("- [") and "kart " in l]
    assert len(journal) <= am.JOURNAL_KEEP + am.ARCHIVE_KEEP
    # Son kayıt her zaman günlükte kalır.
    assert "kart 23" in text


def test_load_office_memory_respects_budget(tmp_path):
    for i in range(12):
        am.append_office_memory("ofis", _entry(f"kart {i}", tmp_path, learning=f"öğrenim {i} " + "y" * 120))
    out = am.load_office_memory("ofis", budget_tokens=300, vault_path=tmp_path)

    assert out
    assert len(out) <= 300 * 4
    assert am.LEARNED_TITLE in out
    assert am.ARCHIVE_TITLE not in out
    assert am.load_office_memory("yok-boyle-ofis", vault_path=tmp_path) == ""


def test_consolidate_office_memory_is_llm_free_and_idempotent(tmp_path):
    for i in range(5):
        am.append_office_memory("ofis", _entry("aynı kart", tmp_path))
    p1 = am.consolidate_office_memory("ofis", vault_path=tmp_path)
    text1 = p1.read_text(encoding="utf-8")
    am.consolidate_office_memory("ofis", vault_path=tmp_path)
    text2 = p1.read_text(encoding="utf-8")

    assert "Tekrar eden görevler: aynı kart ×5" in text1
    # Yalnızca `updated` damgası değişir; içerik sabit kalır.
    strip = lambda t: "\n".join(l for l in t.splitlines() if not l.startswith("updated:"))
    assert strip(text1) == strip(text2)


# --------------------------------------------------------------------------
# Bağlam kurucu
# --------------------------------------------------------------------------


def _builder(tmp_path):
    from entropy.memory.context_builder import CognitiveContextBuilder
    from entropy.memory.playbook import PlaybookStore, SkillReportIndex

    store = PlaybookStore(vault_path=tmp_path, index=SkillReportIndex(index_path=tmp_path / "idx.json"))

    class NoMemory:
        def hybrid_recall(self, *a, **k):
            return []

    class NoVault:
        def read_global_memory(self):
            return ""

    return CognitiveContextBuilder(memory_system=NoMemory(), vault_manager=NoVault(), playbook_store=store)


def test_context_includes_office_memory_when_meta_has_office(tmp_path):
    from entropy.memory.context_builder import BUDGET_OFFICE_MEMORY

    am.append_office_memory("ofis", _entry("kota kartı", tmp_path, learning="Ofis kartı 3 alt karta bölünür."))
    b = _builder(tmp_path)

    ctx = b.build("kart nasıl bölünür", skill_name=None, meta={"office": "ofis"}, include_handoff=False)
    kinds = {s.kind for s in ctx.sections}
    assert "office_memory" in kinds
    section = next(s for s in ctx.sections if s.kind == "office_memory")
    assert section.tokens <= BUDGET_OFFICE_MEMORY
    assert "Ofis kartı 3 alt karta bölünür." in section.body

    ctx2 = b.build("kart nasıl bölünür", skill_name=None, include_handoff=False)
    assert "office_memory" not in {s.kind for s in ctx2.sections}


def test_office_memory_comes_after_agent_memory(tmp_path):
    am.append_agent_memory("researcher", {"title": "g", "learning": "ajan satırı", "vault_path": tmp_path})
    am.append_office_memory("ofis", _entry("k", tmp_path, learning="ofis satırı"))
    b = _builder(tmp_path)

    ctx = b.build("soru", skill_name=None, meta={"agent": "researcher", "office": "ofis"}, include_handoff=False)
    kinds = [s.kind for s in ctx.sections]
    assert kinds.index("agent_memory") < kinds.index("office_memory")


# --------------------------------------------------------------------------
# Ofis raporu
# --------------------------------------------------------------------------


def _write_office_report(tmp_path, body="Ofis kartı 3 alt karta bölündü; not 0.82, 1400 token harcandı."):
    mem = FakeMemory()
    page = wiki.write_query_page(
        "medya",
        "Kampanya kartı sonucu",
        body,
        {
            "vault_path": tmp_path,
            "memory": mem,
            "office": "Medya Ofisi",
            "category": wiki.OFFICE_REPORT_CATEGORY,
            "agent": "orkestrator",
            "grade": 0.82,
            "children_count": 3,
            "task_id": "t-7",
        },
    )
    return page, mem


def test_office_report_written_to_wiki_and_office_folder_with_log(tmp_path):
    page, mem = _write_office_report(tmp_path)

    # 1) Yetenek wiki'si
    assert page.parent == tmp_path / "Entropy" / "Skills" / "medya" / "wiki" / "queries"
    assert page.is_file()

    # 2) Ofis klasöründe wikilink'li KISA özet (kopya değil)
    reports = sorted((tmp_path / "Entropy" / "Desk" / "Offices" / "Medya Ofisi" / "reports").glob("*.md"))
    assert len(reports) == 1
    summary = reports[0].read_text(encoding="utf-8")
    assert "type: office_report" in summary
    assert "office: Medya Ofisi" in summary
    assert "grade: 0.82" in summary
    assert "children_count: 3" in summary
    assert f"[[{page.stem}]]" in summary
    assert len(summary) < len(page.read_text(encoding="utf-8")) + 400

    # 3) Ofis günlüğü
    log = tmp_path / "Entropy" / "Desk" / "Offices" / "Medya Ofisi" / "log.md"
    assert "report: Kampanya kartı sonucu (orkestrator)" in log.read_text(encoding="utf-8")

    # 4) Geri çağırma düğümü yalnızca bir kez yazılır (özet ayrı düğüm değil)
    assert [n["category"] for n in mem.nodes] == ["query"]


def test_office_report_summary_is_capped(tmp_path):
    page, _ = _write_office_report(tmp_path, body="ü" * 3000)
    reports = sorted((tmp_path / "Entropy" / "Desk" / "Offices" / "Medya Ofisi" / "reports").glob("*.md"))
    body = reports[0].read_text(encoding="utf-8").split("## Özet", 1)[1]
    assert len(body.strip()) <= wiki.OFFICE_SUMMARY_MAX_CHARS + 2


def test_plain_query_page_does_not_create_office_folder(tmp_path):
    wiki.write_query_page("medya", "sıradan soru", "cevap", {"vault_path": tmp_path, "memory": FakeMemory()})
    assert not (tmp_path / "Entropy" / "Desk" / "Offices").exists()


def test_office_report_is_not_a_distillation_source_but_enters_recall_pool(tmp_path):
    from entropy.memory.playbook import discover_reports

    page, _ = _write_office_report(tmp_path, body="ölçüm " * 200)
    gercek = tmp_path / "Entropy" / "Reports" / "Gercek Rapor.md"
    gercek.parent.mkdir(parents=True, exist_ok=True)
    gercek.write_text("gövde " * 200, encoding="utf-8")

    found = {p.name for p in discover_reports(tmp_path)}
    assert "Gercek Rapor.md" in found
    assert page.name not in found  # wiki/queries dışlaması
    office_report = next((tmp_path / "Entropy" / "Desk" / "Offices" / "Medya Ofisi" / "reports").glob("*.md"))
    assert office_report.name not in found  # Offices/ dışlaması

    # Geri çağırma havuzu: rapor bölümü sorgu sayfasını görür.
    section = _builder(tmp_path)._reports_section("ölçüm", "medya", 900)
    assert section is not None
    assert "ölçüm" in section.body.lower()


# --------------------------------------------------------------------------
# Aktarım (handoff)
# --------------------------------------------------------------------------


def test_load_latest_handoff_skips_office_reports(tmp_path):
    from entropy.memory.handoff import load_latest_handoff, sessions_dir

    d = sessions_dir(tmp_path)
    d.mkdir(parents=True, exist_ok=True)
    (d / "2026-09-08-oturum.md").write_text(
        '---\ntype: handoff\ntitle: "Gerçek aktarım"\n---\n\n## Yapılanlar\n\n- bir şey\n',
        encoding="utf-8",
    )
    # Yanlışlıkla Sessions/ altına düşmüş bir ofis raporu aktarım sayılmamalı.
    (d / "2026-09-09-ofis.md").write_text(
        '---\ntype: office_report\noffice: Medya Ofisi\ntitle: "Kart sonucu"\n---\n\ngövde\n',
        encoding="utf-8",
    )

    latest = load_latest_handoff(tmp_path)
    assert latest is not None
    assert latest["title"] == "Gerçek aktarım"


# --------------------------------------------------------------------------
# Bilgi grafiği — veri
# --------------------------------------------------------------------------


def _office_vault(tmp_path):
    ent = tmp_path / "Entropy"
    office = ent / "Offices" / "Medya Ofisi"
    (office).mkdir(parents=True, exist_ok=True)
    (office / "OFFICE.md").write_text(
        "---\n"
        "name: Medya Ofisi\n"
        "purpose: kampanya üretimi\n"
        "orchestrator: orkestrator\n"
        "evaluator: degerlendirici\n"
        "members: [researcher, tasarimci]\n"
        "---\n\n# Medya Ofisi tüzüğü\n",
        encoding="utf-8",
    )
    agent_dir = ent / "Agents" / "researcher"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "AGENT.md").write_text("---\nname: researcher\nrole: worker\n---\n\nAraştırmacı\n", encoding="utf-8")
    (agent_dir / "MEMORY.md").write_text("# researcher — Ajan Belleği\n", encoding="utf-8")
    return ent


def test_graph_data_has_office_agent_and_query_nodes(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTROPY_GRAPH_CACHE", "0")
    from entropy.memory.obsidian import vault_manager as vm

    vm.clear_graph_cache()
    _office_vault(tmp_path)
    _write_office_report(tmp_path)

    graph = vm.ObsidianVaultManager(vault_path=tmp_path).build_knowledge_graph()
    by_id = {n["id"]: n for n in graph["nodes"]}
    groups = {n["group"] for n in graph["nodes"]}
    assert {"office", "agent", "query"} <= groups

    office_id = "office/Medya Ofisi"
    assert by_id[office_id]["name"] == "Medya Ofisi"

    # Kayıtlı ajan MEVCUT düğüme bağlanır, kayıtsız üyeler sentetik üretilir.
    assert by_id["agent/researcher"]["path"]
    assert by_id["agent/tasarimci"]["group"] == "agent"
    member_links = {
        (l["source"], l["target"], l.get("alias"))
        for l in graph["links"]
        if l["source"] == office_id
    }
    assert (office_id, "agent/orkestrator", "orkestrator") in member_links
    assert (office_id, "agent/degerlendirici", "degerlendirici") in member_links
    assert (office_id, "agent/researcher", "uye") in member_links
    assert (office_id, "agent/tasarimci", "uye") in member_links

    # Ofis raporu özeti query grubunda ve ofise bağlı.
    office_reports = [
        n for n in graph["nodes"]
        if n["group"] == "query" and "Offices" in str(n.get("path", ""))
    ]
    assert len(office_reports) == 1
    assert any(
        l["source"] == office_reports[0]["id"] and l["target"] == office_id and l.get("alias") == "office"
        for l in graph["links"]
    )

    # Ofis MEMORY.md / log.md defterdir: grafiğe düğüm olarak girmez.
    assert not any(str(n.get("path", "")).endswith("Offices\\Medya Ofisi\\MEMORY.md") for n in graph["nodes"])
    vm.clear_graph_cache()


def test_unified_graph_places_office_nodes_under_offices_hub(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("ENTROPY_GRAPH_CACHE", "0")
    from entropy.memory.obsidian import vault_manager as vm
    from entropy.ui.widgets.knowledge_graph import KnowledgeGraphWidget

    vm.clear_graph_cache()
    _office_vault(tmp_path)
    _write_office_report(tmp_path)

    manager = vm.ObsidianVaultManager(vault_path=tmp_path)
    widget = KnowledgeGraphWidget(vault_manager=manager)
    try:
        graph = widget.build_unified_graph()
    finally:
        widget.close()
    by_id = {n["id"]: n for n in graph["nodes"]}

    assert "hub-offices" in by_id and by_id["hub-offices"]["group"] == "hub"
    office = by_id["office/Medya Ofisi"]
    assert office["group"] == "office"
    assert office["parent_hub"] == "hub-offices"
    assert office["cluster_group"] == "offices"

    agent = by_id["agent/researcher"]
    assert agent["group"] == "agent"
    assert agent["parent_hub"] in ("office/Medya Ofisi", "hub-offices")

    # Ofis raporu yaprağı ofis düğümüne asılı ve query grubunda kalır
    # (Reports grubuna kaymaz: damıtma kaynağı değildir).
    leaf = next(n for n in graph["nodes"] if n["group"] == "query" and n["parent_hub"] == "office/Medya Ofisi")
    assert leaf["cluster_group"] == "offices"

    vm.clear_graph_cache()


def test_graph_template_has_office_colors_icons_legend_and_scope():
    from entropy.ui.widgets.knowledge_graph import GRAPH_HTML_TEMPLATE as T

    assert "'office': '#FFB000'" in T
    assert "'agent': '#2DD4BF'" in T
    assert "'query': '#C792EA'" in T
    assert "🏢" in T and "🤖" in T and "🔎" in T
    assert "toggleCategory('office'" in T
    assert "toggleCategory('agent'" in T
    assert "toggleCategory('query'" in T
    assert "currentScope === 'all_offices'" in T
    assert "function getNodeIcon(group)" in T
