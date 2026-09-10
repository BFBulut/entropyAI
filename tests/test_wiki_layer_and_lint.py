"""
Wiki katmanı v1 (kavram/varlık sayfaları), `/lint` denetimleri, bağlam kurucu
sayfa seçimi ve grafik grupları.

Kapsanan davranış:
- `ingest_playbook_to_wiki`: playbook başlıklarından kavram sayfası, sezgisel
  varlık çıkarımı, çapraz bağlar, index.md kategorileri, log.md satırı,
  `dry_run` hiçbir şey yazmaz, yeniden üretim `created` alanını korur.
- `lint_skill`: yedi denetimin her biri için pozitif ve negatif durum.
- Bağlam kurucu: wiki sayfaları bölümü, en fazla iki sayfa, 400 token tavanı,
  toplam 4000 bütçe korunur.
- Bilgi grafiği: concept/entity grupları ve yetenek düğümüne bağlanma.
- Damıtma bitince wiki'nin otomatik üretilmesi (model çağrılmadan).

Tüm testler tmp kasada çalışır; gerçek Obsidian kasasına yazılmaz.
"""

from pathlib import Path

import pytest

from entropy.memory import lint as lintmod
from entropy.memory import wiki
from entropy.memory.playbook import PlaybookStore, SkillPlaybook, SkillReportIndex

PROCEDURE = """## Çalışma Adımları
1. `agy` CLI ile Kredi Kayıt Bürosu kayıtlarını çek.
2. Kredi Kayıt Bürosu verisini KDV Beyannamesi ile karşılaştır.
3. Sonucu PySide6 arayüzünde göster.

## Karar Ölçütleri
- Sapma %5 üzerindeyse KDV Beyannamesi yeniden okunur.

## Bilinen Tuzaklar
- OneDrive mtime'ına güvenme.

## Çıktı Biçimi
- Markdown tablo, `PLAYBOOK.md` ile aynı dilde.
"""


def _store(root: Path, skill: str = "denetci", n_reports: int = 2) -> PlaybookStore:
    rep = root / "Entropy" / "Skills" / skill / "Reports"
    rep.mkdir(parents=True, exist_ok=True)
    for i in range(n_reports):
        (rep / f"Aylik Denetim Raporu {i}.md").write_text(
            f"---\ntitle: R{i}\n---\n\nKredi Kayıt Bürosu ölçümü {i}.\n" + "y" * 400,
            encoding="utf-8",
        )
    return PlaybookStore(vault_path=root, index=SkillReportIndex(index_path=root / "idx.json"))


def _seed(root: Path, skill: str = "denetci", procedure: str = PROCEDURE, version: int = 3,
          n_reports: int = 2) -> PlaybookStore:
    store = _store(root, skill, n_reports)
    store.save(SkillPlaybook(skill=skill, procedure=procedure, version=version,
                             source_count=n_reports, processed_count=n_reports))
    return store


def _read(p) -> str:
    return Path(p).read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Görev 1 — ingest
# --------------------------------------------------------------------------


def test_ingest_creates_concept_pages_for_each_heading(tmp_path):
    store = _seed(tmp_path)
    res = wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)

    assert res["concepts"] == ["Çalışma Adımları", "Karar Ölçütleri",
                               "Bilinen Tuzaklar", "Çıktı Biçimi"]
    c_dir = wiki.concepts_dir("denetci", tmp_path)
    assert len(list(c_dir.glob("*.md"))) == 4

    page = next(p for p in c_dir.glob("*.md") if "calisma" in p.name)
    text = _read(page)
    assert "type: concept" in text
    assert "skill: denetci" in text
    assert 'title: "Çalışma Adımları"' in text
    assert "source_version: 3" in text
    assert "created:" in text and "updated:" in text
    # Kaynak: playbook wikilink'i
    assert "[[PLAYBOOK]]" in text


def test_ingest_extracts_entities_and_cross_links(tmp_path):
    store = _seed(tmp_path)
    res = wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)

    # Çok kelimeli ad iki kez geçiyor -> varlık; tek geçen backtick/CamelCase de girer.
    assert "Kredi Kayıt Bürosu" in res["entities"]
    assert "PySide6" in res["entities"]
    # Başlıklar varlık sayılmamalı: kavram sayfası olarak zaten varlar.
    assert "Çalışma Adımları" not in res["entities"]

    e_dir = wiki.entities_dir("denetci", tmp_path)
    ent = next(p for p in e_dir.glob("*.md") if "kredi-kayit-burosu" in p.name)
    ent_text = _read(ent)
    assert "type: entity" in ent_text
    # Varlık -> kavram bağı
    assert "## İlgili" in ent_text
    assert "[[denetci-calisma-adimlari]]" in ent_text
    # Kavram -> varlık bağı
    concept = next(wiki.concepts_dir("denetci", tmp_path).glob("*calisma*.md"))
    assert "[[denetci-kredi-kayit-burosu]]" in _read(concept)


def test_ingest_updates_index_categories_and_log(tmp_path):
    store = _seed(tmp_path)
    wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)

    index = _read(wiki.wiki_dir("denetci", tmp_path) / "index.md")
    assert "## Yordam" in index
    assert "## Kavramlar" in index
    assert "## Varlıklar" in index
    # Sıra: Yordam < Kavramlar < Varlıklar
    assert index.index("## Yordam") < index.index("## Kavramlar") < index.index("## Varlıklar")

    log = _read(wiki.wiki_dir("denetci", tmp_path) / "log.md")
    assert "ingest:" in log
    assert "4 kavram" in log

    # log.md append-only: ikinci üretim satır ekler, silmez.
    wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)
    assert _read(wiki.wiki_dir("denetci", tmp_path) / "log.md").count("ingest:") == 2


def test_ingest_dry_run_writes_nothing(tmp_path):
    store = _seed(tmp_path)
    res = wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store, dry_run=True)
    assert res["written"] == len(res["concepts"]) + len(res["entities"]) > 0
    assert not wiki.concepts_dir("denetci", tmp_path).exists()
    assert not (wiki.wiki_dir("denetci", tmp_path) / "log.md").exists()


def test_ingest_without_playbook_is_noop(tmp_path):
    store = _store(tmp_path)
    res = wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)
    assert res["written"] == 0
    assert res["reason"] == "playbook yok"


def test_reingest_preserves_created(tmp_path):
    store = _seed(tmp_path)
    wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)
    page = next(wiki.concepts_dir("denetci", tmp_path).glob("*calisma*.md"))
    created = [l for l in _read(page).splitlines() if l.startswith("created:")][0]

    store.save(SkillPlaybook(skill="denetci", procedure=PROCEDURE, version=4))
    wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)
    text = _read(page)
    assert created in text
    assert "source_version: 4" in text


def test_split_playbook_sections_ignores_preamble():
    secs = wiki.split_playbook_sections("giris metni\n\n## A\nbir\n\n### B\niki\n")
    assert [t for t, _ in secs] == ["A", "B"]
    assert secs[0][1] == "bir"


def test_extract_entities_filters_sentence_starts():
    # "Bu Rapor" cümle başıdır (stopword) ve tek geçer; varlık olmamalı.
    names = wiki.extract_entities(["Bu Rapor iyi.", "Merkez Bankası verisi.",
                                   "Merkez Bankası tekrar."])
    assert "Merkez Bankası" in names
    assert "Bu Rapor" not in names


# --------------------------------------------------------------------------
# Görev 2 — lint
# --------------------------------------------------------------------------


def _linted(tmp_path, **kw):
    store = _seed(tmp_path, **kw)
    wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)
    return store


def _checks(res) -> dict:
    return res.counts()


def test_lint_clean_wiki_has_no_structural_findings(tmp_path):
    store = _linted(tmp_path)
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    counts = _checks(res)
    assert counts.get("broken_link", 0) == 0
    assert counts.get("stale", 0) == 0
    assert counts.get("missing_concept", 0) == 0
    assert counts.get("orphan", 0) == 0
    assert res.stats["concepts"] == 4


def test_lint_detects_broken_link(tmp_path):
    store = _linted(tmp_path)
    page = next(wiki.concepts_dir("denetci", tmp_path).glob("*calisma*.md"))
    page.write_text(_read(page) + "\n- [[olmayan-sayfa]]\n", encoding="utf-8")

    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    broken = [f for f in res.findings if f.check == "broken_link"]
    assert broken and "olmayan-sayfa" in broken[0].message


def test_lint_detects_orphan_page(tmp_path):
    store = _linted(tmp_path)
    orphan = wiki.concepts_dir("denetci", tmp_path) / "denetci-yalniz.md"
    orphan.write_text(
        "---\ntype: concept\nskill: denetci\ntitle: \"Yalniz\"\n"
        "category: Kavramlar\nsource_version: 3\n---\n\n# Yalniz\n\nmetin\n",
        encoding="utf-8",
    )
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    orphans = [f.page for f in res.findings if f.check == "orphan"]
    assert "denetci-yalniz" in orphans
    # Bağ alan sayfalar öksüz sayılmamalı.
    assert "denetci-calisma-adimlari" not in orphans


def test_lint_detects_stale_page(tmp_path):
    store = _linted(tmp_path)
    res_before = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    assert _checks(res_before).get("stale", 0) == 0

    store.save(SkillPlaybook(skill="denetci", procedure=PROCEDURE, version=9))
    res_after = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    stale = [f for f in res_after.findings if f.check == "stale"]
    assert stale and "v9" in stale[0].message


def test_lint_detects_missing_concept(tmp_path):
    store = _linted(tmp_path)
    store.save(SkillPlaybook(skill="denetci",
                             procedure=PROCEDURE + "\n## Yeni Bolum\nicerik\n", version=3))
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    missing = [f.page for f in res.findings if f.check == "missing_concept"]
    assert missing == ["Yeni Bolum"]


def test_lint_detects_contradiction_candidate(tmp_path):
    store = _linted(tmp_path)
    q = wiki.queries_dir("denetci", tmp_path)
    q.mkdir(parents=True, exist_ok=True)
    (q / "2026-01-01-a.md").write_text(
        "---\ntype: query\ncategory: Sorgular\ntitle: \"A\"\n---\n\n"
        "Kredi Kayıt Bürosu limiti 120 TL olarak alindi.\n", encoding="utf-8")
    (q / "2026-01-02-b.md").write_text(
        "---\ntype: query\ncategory: Sorgular\ntitle: \"B\"\n---\n\n"
        "Kredi Kayıt Bürosu limiti 340 TL olarak alindi.\n", encoding="utf-8")

    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    contra = [f for f in res.findings if f.check == "contradiction"]
    assert contra and contra[0].page == "Kredi Kayıt Bürosu"
    assert "120TL" in contra[0].message and "340TL" in contra[0].message


def test_lint_no_contradiction_when_values_agree(tmp_path):
    store = _linted(tmp_path)
    q = wiki.queries_dir("denetci", tmp_path)
    q.mkdir(parents=True, exist_ok=True)
    for name in ("2026-01-01-a.md", "2026-01-02-b.md"):
        (q / name).write_text(
            "---\ntype: query\ncategory: Sorgular\ntitle: \"A\"\n---\n\n"
            "Kredi Kayıt Bürosu limiti 120 TL olarak alindi.\n", encoding="utf-8")
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    assert _checks(res).get("contradiction", 0) == 0


def test_lint_detects_unread_reports(tmp_path):
    store = _seed(tmp_path, n_reports=2)
    store.save(SkillPlaybook(skill="denetci", procedure=PROCEDURE, version=3,
                             source_count=2, processed_count=1))
    wiki.ingest_playbook_to_wiki("denetci", vault_path=tmp_path, store=store)
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    unread = [f for f in res.findings if f.check == "unread_report"]
    assert unread and "1/2" in unread[0].message

    # Hepsi işlenmişse bulgu yok.
    store.save(SkillPlaybook(skill="denetci", procedure=PROCEDURE, version=3,
                             source_count=2, processed_count=2))
    res2 = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    assert _checks(res2).get("unread_report", 0) == 0


def test_lint_detects_open_handoff_items(tmp_path):
    store = _linted(tmp_path)
    sess = tmp_path / "Entropy" / "Sessions"
    sess.mkdir(parents=True, exist_ok=True)
    (sess / "2026-01-01-oturum.md").write_text(
        "---\nkind: handoff\n---\n\n# Aktarim\n\n"
        "## Açık İşler\n- lint tablosu arayuze baglanacak\n- [x] wiki ingest yazildi\n\n"
        "## Sonraki Adım\n- devam\n", encoding="utf-8")
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    open_tasks = [f.message for f in res.findings if f.check == "open_task"]
    assert open_tasks == ["lint tablosu arayuze baglanacak"]


def test_lint_no_open_items_when_section_empty(tmp_path):
    store = _linted(tmp_path)
    sess = tmp_path / "Entropy" / "Sessions"
    sess.mkdir(parents=True, exist_ok=True)
    (sess / "2026-01-01-oturum.md").write_text(
        "---\nkind: handoff\n---\n\n# Aktarim\n\n## Açık İşler\n—\n\n", encoding="utf-8")
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    assert _checks(res).get("open_task", 0) == 0


def test_lint_report_and_html_render(tmp_path):
    store = _linted(tmp_path)
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    path = lintmod.write_lint_report(res, vault_path=tmp_path)
    assert path.name == "lint.md"
    body = _read(path)
    assert "type: lint" in body and "denetci" in body

    html = lintmod.render_lint_html([res])
    assert "<table" in html and "denetci" in html
    assert "Kırık bağ" in html


def test_lint_vault_covers_all_skills(tmp_path):
    _linted(tmp_path)
    store2 = _seed(tmp_path, skill="ikinci")
    wiki.ingest_playbook_to_wiki("ikinci", vault_path=tmp_path, store=store2)
    results = lintmod.lint_vault(vault_path=tmp_path)
    assert {r.skill for r in results} == {"denetci", "ikinci"}


# --------------------------------------------------------------------------
# Görev 3 — bağlam kurucu
# --------------------------------------------------------------------------


def test_context_builder_selects_at_most_two_wiki_pages(tmp_path):
    from entropy.memory.context_builder import (
        BUDGET_WIKI_PAGES,
        DEFAULT_TOKEN_BUDGET,
        MAX_WIKI_PAGES,
        CognitiveContextBuilder,
    )

    store = _linted(tmp_path)
    builder = CognitiveContextBuilder(playbook_store=store)
    section = builder._wiki_pages_section("Kredi Kayıt Bürosu KDV karşılaştırması",
                                          "denetci", BUDGET_WIKI_PAGES)
    assert section is not None
    assert section.kind == "wiki_pages"
    assert section.body.count("— [") <= MAX_WIKI_PAGES
    assert section.tokens <= BUDGET_WIKI_PAGES
    # Bağ listeleri bağlama girmez.
    assert "## Kaynaklar" not in section.body

    ctx = builder.build("Kredi Kayıt Bürosu KDV karşılaştırması", skill_name="denetci",
                        token_budget=DEFAULT_TOKEN_BUDGET, include_handoff=False)
    kinds = [s.kind for s in ctx.sections]
    assert "wiki_pages" in kinds
    # Sıra: playbook'tan hemen sonra
    assert kinds.index("wiki_pages") == kinds.index("playbook") + 1
    assert ctx.tokens <= DEFAULT_TOKEN_BUDGET


def test_context_builder_skips_pages_already_in_playbook_section(tmp_path):
    """Kavram sayfası playbook bölümünün kopyasıdır; ikisi birden alınmamalı."""
    from entropy.memory.context_builder import BUDGET_WIKI_PAGES, CognitiveContextBuilder

    store = _linted(tmp_path)
    builder = CognitiveContextBuilder(playbook_store=store)
    pb = store.load("denetci")
    section = builder._wiki_pages_section(
        "Kredi Kayıt Bürosu KDV karşılaştırması", "denetci", BUDGET_WIKI_PAGES,
        exclude_text=pb.procedure,
    )
    # Kavram sayfaları elenir; geriye yalnızca sorguda adı geçen varlık kalır.
    assert section is not None
    picked = [l for l in section.body.splitlines() if l.startswith("— [")]
    assert not any("calisma-adimlari" in l for l in picked)
    assert any("kredi-kayit-burosu" in l or "kdv-beyannamesi" in l for l in picked)


def test_context_builder_without_wiki_pages_returns_none(tmp_path):
    from entropy.memory.context_builder import BUDGET_WIKI_PAGES, CognitiveContextBuilder

    store = _seed(tmp_path)
    builder = CognitiveContextBuilder(playbook_store=store)
    assert builder._wiki_pages_section("herhangi", "denetci", BUDGET_WIKI_PAGES) is None


# --------------------------------------------------------------------------
# Görev 4 — grafik
# --------------------------------------------------------------------------


def test_graph_marks_concept_and_entity_groups(tmp_path):
    from entropy.memory.obsidian.vault_manager import ObsidianVaultManager

    store = _linted(tmp_path)
    vm = ObsidianVaultManager(vault_path=str(tmp_path))
    data = vm.build_knowledge_graph()
    groups = {n["group"] for n in data["nodes"]}
    assert "concept" in groups and "entity" in groups

    concept_ids = [n["id"] for n in data["nodes"] if n["group"] == "concept"]
    assert any(i.startswith("concept/") for i in concept_ids)
    # Yetenek düğümüne bağlanma (aidiyet dosya yolundan gelir)
    skill_links = [l for l in data["links"]
                   if l["target"] == "skill/denetci" and l["source"] in concept_ids]
    assert skill_links
    # Wiki defter dosyaları (index/log) düğüm olmamalı.
    assert not [n for n in data["nodes"] if n["name"] in ("index", "log", "lint")]
    assert store is not None


# --------------------------------------------------------------------------
# Slash komutları (gerçek kasaya dokunmadan)
# --------------------------------------------------------------------------


def test_wiki_and_lint_are_local_commands(monkeypatch, tmp_path):
    from entropy.core import slash_commands as sc

    calls = {}

    def _fake_ingest(skill, **kw):
        calls["wiki"] = skill
        return {"written": 2, "concepts": ["A"], "entities": ["B"], "index": "i", "reason": ""}

    monkeypatch.setattr("entropy.memory.wiki.ingest_playbook_to_wiki", _fake_ingest)
    out = sc.try_handle_local_command("/wiki denetci", bridge=None)
    assert out is not None and "denetci" in out and calls["wiki"] == "denetci"

    store = _linted(tmp_path)
    res = lintmod.lint_skill("denetci", vault_path=tmp_path, store=store)
    monkeypatch.setattr("entropy.memory.lint.lint_vault", lambda **kw: [res])
    monkeypatch.setattr("entropy.memory.lint.write_lint_report",
                        lambda r, **kw: calls.setdefault("lint", r.skill))
    out2 = sc.try_handle_local_command("/lint all", bridge=None)
    assert out2 is not None and "Wiki Denetimi" in out2 and calls["lint"] == "denetci"

    # Faz 12-B: slash yuzeyi 34 -> 31. `/wiki` komut paletinden kaldirildi
    # (yerine `/distill wiki ...`), ama alias olarak yasamaya devam ediyor —
    # yukaridaki `/wiki denetci` cagrisi bunun kaniti.
    names = {c.name for c in sc.LOCAL_COMMANDS}
    assert "/lint" in names
    assert "/wiki" not in names, "/wiki paletten kaldirilmisti (12-B)"
    assert "/distill" in names


# --------------------------------------------------------------------------
# Damıtma ile bütünleşme
# --------------------------------------------------------------------------


def test_distiller_complete_triggers_wiki_ingest(tmp_path):
    from entropy.memory.distiller import PlaybookDistiller

    store = _store(tmp_path, n_reports=2)
    d = PlaybookDistiller(store=store)
    pb = d.run_with_bridge("denetci", send_prompt=lambda p: PROCEDURE)
    assert pb is not None
    pages = list(wiki.concepts_dir("denetci", tmp_path).glob("*.md"))
    assert len(pages) == 4
