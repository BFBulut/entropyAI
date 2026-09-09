"""
Wiki sorgu sayfaları, ajan belleği ve bunların bağlam/grafik/damıtma etkileri.

Kapsanan davranış:
- `write_query_page`: ön bilgi alanları, maskeleme, index.md/log.md güncellemesi,
  bilişsel bellek düğümü (category="query").
- `append_agent_memory` / `consolidate_agent_memory` / `load_agent_memory`:
  10 kayıttan sonra arşive katlama ve 6000 karakter tavanı.
- Bağlam kurucu: ajan belleği bölümü ve sorgu sayfalarının rapor havuzuna girmesi.
- Damıtma kaynağı dışlaması: Sessions/, Tasks/, Agents/, wiki/ kaynak sayılmaz.
- Bilgi grafiği: sorgu sayfaları "query" grubunda ve yetenek düğümüne bağlı.

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
        self.nodes.append(
            {"category": category, "content": content, "importance": importance, "metadata": metadata or {}}
        )
        return None, True


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Wiki sorgu sayfaları
# --------------------------------------------------------------------------


def test_write_query_page_frontmatter_index_log_and_memory(tmp_path):
    mem = FakeMemory()
    out_report = tmp_path / "Entropy" / "Reports" / "AGY Kota Olcumu.md"
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("x", encoding="utf-8")

    path = wiki.write_query_page(
        "financial-auditor",
        "AGY kota ölçümü nasıl okunur",
        "Kısa cevap: ledger özetinden okunur.",
        {
            "agent": "researcher",
            "provider": "agy",
            "model": "gemini-3",
            "task_id": "t-42",
            "output_paths": [str(out_report)],
            "vault_path": tmp_path,
            "memory": mem,
        },
    )

    assert path.parent == tmp_path / "Entropy" / "Skills" / "financial-auditor" / "wiki" / "queries"
    text = _read(path)
    for line in ("type: query", "skill: financial-auditor", "agent: researcher",
                 "provider: agy", "model: gemini-3", "task_id: t-42"):
        assert line in text
    assert "created:" in text
    assert "## Kaynaklar" in text and "[[AGY Kota Olcumu]]" in text

    index = path.parent.parent / "index.md"
    log = path.parent.parent / "log.md"
    assert index.is_file() and log.is_file()
    assert f"[[{path.stem}]]" in _read(index)
    assert f"## {wiki.DEFAULT_CATEGORY}" in _read(index)
    log_text = _read(log)
    assert "query: AGY kota ölçümü nasıl okunur (researcher)" in log_text

    assert len(mem.nodes) == 1
    node = mem.nodes[0]
    assert node["category"] == "query"
    assert len(node["content"]) <= wiki.MEMORY_NODE_MAX_CHARS
    assert node["metadata"]["path"] == str(path)
    assert node["metadata"]["skill"] == "financial-auditor"


def test_query_page_masks_tool_output_and_caps_body(tmp_path):
    """Uzun araç çıktısı maskelenir ve gövde 4000 karakteri aşmaz."""
    mem = FakeMemory()
    huge = "A" * 9000
    body = f"Özet satırı.\n[✔ ARAÇ TAMAMLANDI: Read (0.10s)]\nSonuç: {huge}\n"
    path = wiki.write_query_page(
        "test-skill", "maskeleme", body, {"vault_path": tmp_path, "memory": mem}
    )
    text = _read(path)
    assert huge not in text
    assert "araç çıktısı" in text
    # Gövde (ön bilgi hariç) tavanın altında.
    assert len(text.split("---", 2)[-1]) <= wiki.QUERY_BODY_MAX_CHARS + 200
    assert len(mem.nodes[0]["content"]) <= wiki.MEMORY_NODE_MAX_CHARS


def test_query_page_without_skill_goes_to_global_wiki(tmp_path):
    mem = FakeMemory()
    path = wiki.write_query_page("", "genel soru", "cevap", {"vault_path": tmp_path, "memory": mem})
    assert path.parent == tmp_path / "Entropy" / "Wiki" / "queries"


def test_two_pages_same_day_same_title_do_not_overwrite(tmp_path):
    mem = FakeMemory()
    meta = {"vault_path": tmp_path, "memory": mem}
    p1 = wiki.write_query_page("s", "aynı başlık", "a", dict(meta))
    p2 = wiki.write_query_page("s", "aynı başlık", "b", dict(meta))
    assert p1 != p2 and p1.is_file() and p2.is_file()


def test_rebuild_wiki_index_from_existing_pages(tmp_path):
    mem = FakeMemory()
    meta = {"vault_path": tmp_path, "memory": mem}
    wiki.write_query_page("s", "birinci", "a", dict(meta, category="Ölçümler"))
    wiki.write_query_page("s", "ikinci", "b", dict(meta))
    pb = tmp_path / "Entropy" / "Skills" / "s" / "PLAYBOOK.md"
    pb.write_text("# yordam\n", encoding="utf-8")

    index = wiki.rebuild_wiki_index("s", vault_path=tmp_path)
    text = _read(index)
    assert "## Ölçümler" in text
    assert f"## {wiki.DEFAULT_CATEGORY}" in text
    assert "[[PLAYBOOK]]" in text
    assert text.count("- [[") >= 3


# --------------------------------------------------------------------------
# Ajan belleği
# --------------------------------------------------------------------------


def test_append_agent_memory_creates_sections(tmp_path):
    p = am.append_agent_memory(
        "researcher",
        {
            "title": "Kota ölçümü",
            "result": "başarılı",
            "output_path": str(tmp_path / "Rapor.md"),
            "learning": "Ledger özeti maskelenmiş metinden okunur.",
            "vault_path": tmp_path,
        },
    )
    assert p == tmp_path / "Entropy" / "Agents" / "researcher" / "MEMORY.md"
    text = _read(p)
    assert f"## {am.JOURNAL_TITLE}" in text and f"## {am.LEARNED_TITLE}" in text
    assert "Kota ölçümü" in text and "sonuç: başarılı" in text and "[[Rapor]]" in text
    assert "Ledger özeti" in text
    assert "entries: 1" in text


def test_consolidation_after_ten_entries_archives_and_caps(tmp_path):
    for i in range(10):
        am.append_agent_memory(
            "researcher",
            {
                "title": f"Tekrarlayan görev {i % 3}",
                "result": "başarılı" if i % 2 == 0 else "hata",
                "output_path": f"rapor-{i}",
                "learning": f"Ölçüm {i}: 120 token harcandı.",
                "vault_path": tmp_path,
            },
        )
    path = am.memory_path("researcher", tmp_path)
    text = _read(path)

    assert len(text) <= am.MEMORY_MAX_CHARS
    # 10 kayıt tam günlükte kalır: bu aşamada arşive katlanacak fazlalık yok.
    assert f"## {am.ARCHIVE_TITLE}" not in text
    assert am.AUTO_MARKER in text and "Tekrar eden görevler" in text

    # 11. kayıt sonrası 20'ye kadar devam: arşiv oluşmalı.
    for i in range(10, 20):
        am.append_agent_memory(
            "researcher",
            {"title": f"Tekrarlayan görev {i % 3}", "result": "başarılı", "vault_path": tmp_path},
        )
    text = _read(path)
    assert f"## {am.ARCHIVE_TITLE}" in text
    assert len(text) <= am.MEMORY_MAX_CHARS
    journal_block = text.split(f"## {am.JOURNAL_TITLE}")[1].split("## ")[0]
    assert journal_block.count("\n- ") <= am.JOURNAL_KEEP
    assert "entries: 20" in text


def test_consolidation_keeps_manual_learnings(tmp_path):
    am.append_agent_memory("a1", {"title": "iş", "learning": "elle yazılmış gibi", "vault_path": tmp_path})
    for i in range(9):
        am.append_agent_memory("a1", {"title": f"iş {i}", "vault_path": tmp_path})
    text = _read(am.memory_path("a1", tmp_path))
    assert "elle yazılmış gibi" in text
    assert text.index("elle yazılmış gibi") < text.index(am.AUTO_MARKER)


def test_load_agent_memory_respects_budget(tmp_path):
    for i in range(12):
        am.append_agent_memory(
            "a2",
            {"title": f"görev {i}", "result": "ok", "learning": f"öğrenim {i} " + "x" * 120, "vault_path": tmp_path},
        )
    out = am.load_agent_memory("a2", budget_tokens=300, vault_path=tmp_path)
    assert out
    assert len(out) <= 300 * 4
    assert am.LEARNED_TITLE in out
    assert am.ARCHIVE_TITLE not in out
    assert am.load_agent_memory("yok-boyle-ajan", vault_path=tmp_path) == ""


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


def test_context_includes_agent_memory_when_meta_has_agent(tmp_path):
    am.append_agent_memory(
        "researcher",
        {"title": "kota ölçümü", "result": "ok", "learning": "Ledger özetinden okunur.", "vault_path": tmp_path},
    )
    b = _builder(tmp_path)

    ctx = b.build("kota nasıl ölçülür", skill_name=None, meta={"agent": "researcher"}, include_handoff=False)
    kinds = {s.kind for s in ctx.sections}
    assert "agent_memory" in kinds
    section = next(s for s in ctx.sections if s.kind == "agent_memory")
    assert section.tokens <= 300
    assert "Ledger özetinden okunur." in section.body

    ctx2 = b.build("kota nasıl ölçülür", skill_name=None, include_handoff=False)
    assert "agent_memory" not in {s.kind for s in ctx2.sections}


def test_query_pages_enter_report_pool(tmp_path):
    mem = FakeMemory()
    wiki.write_query_page(
        "s",
        "kota ölçümü",
        "Kota, ledger özetindeki usage alanından okunur; 1200 token harcandı.",
        {"vault_path": tmp_path, "memory": mem},
    )
    b = _builder(tmp_path)
    section = b._reports_section("kota ledger usage", "s", 900)
    assert section is not None
    assert "ledger" in section.body.lower()


# --------------------------------------------------------------------------
# Damıtma kaynağı dışlaması
# --------------------------------------------------------------------------


def test_non_report_dirs_are_excluded_from_distillation_sources(tmp_path):
    from entropy.memory.playbook import discover_reports

    ent = tmp_path / "Entropy"
    filler = "gövde " * 200
    files = {
        "report": ent / "Reports" / "Gercek Rapor.md",
        "session": ent / "Sessions" / "2026-09-09-oturum.md",
        "task": ent / "Tasks" / "gorev-1.md",
        "agent": ent / "Agents" / "researcher" / "NOTLAR.md",
        "query": ent / "Skills" / "s" / "wiki" / "queries" / "2026-09-09-soru.md",
        "wiki_index": ent / "Skills" / "s" / "wiki" / "index.md",
    }
    for p in files.values():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(filler, encoding="utf-8")

    found = {p.name for p in discover_reports(tmp_path)}
    assert "Gercek Rapor.md" in found
    for key in ("session", "task", "agent", "query", "wiki_index"):
        assert files[key].name not in found, key


# --------------------------------------------------------------------------
# Bilgi grafiği
# --------------------------------------------------------------------------


def test_knowledge_graph_marks_query_pages_and_links_to_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTROPY_GRAPH_CACHE", "0")
    from entropy.memory.obsidian import vault_manager as vm

    vm.clear_graph_cache()
    mem = FakeMemory()
    wiki.write_query_page("s", "kota sorusu", "cevap", {"vault_path": tmp_path, "memory": mem})
    (tmp_path / "Entropy" / "Reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Entropy" / "Reports" / "Rapor.md").write_text("içerik", encoding="utf-8")

    graph = vm.ObsidianVaultManager(vault_path=tmp_path).build_knowledge_graph()
    groups = {n["group"] for n in graph["nodes"]}
    assert "query" in groups
    query_nodes = [n for n in graph["nodes"] if n["group"] == "query"]
    assert len(query_nodes) == 1
    skill_nodes = [n for n in graph["nodes"] if n["group"] == "skill"]
    assert [n["name"] for n in skill_nodes] == ["s"]
    assert any(
        l["source"] == query_nodes[0]["id"] and l["target"] == skill_nodes[0]["id"]
        for l in graph["links"]
    )
    vm.clear_graph_cache()
