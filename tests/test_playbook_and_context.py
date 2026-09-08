"""
Yetenek yordamı (playbook) damıtma döngüsü ve bütçeli bilişsel bağlam testleri.

Kapsanan davranış:
- SKILL.md `tags` alanının her iki YAML biçiminde de okunması (liste biçimi
  önceden yeteneği sessizce kataloğdan düşürüyordu).
- Yetenek kataloğunun tek kaynaktan üretilmesi (panel ile `/` ayrışmasın).
- Rapor keşfinin günlük/dizin dosyalarını elemesi.
- Damıtma döngüsü: kaynak yok -> damıtıldı -> güncel -> yeni rapor -> bayat.
- Bağlamın token bütçesini aşmaması ve önceliği koruması.
"""

import json
from pathlib import Path

import pytest

from entropy.memory.context_builder import (
    DEFAULT_TOKEN_BUDGET,
    CognitiveContextBuilder,
    _best_excerpt,
)
from entropy.memory.distiller import PlaybookDistiller
from entropy.memory.playbook import (
    PLAYBOOK_MAX_CHARS,
    PlaybookStore,
    SkillPlaybook,
    SkillReportIndex,
    discover_reports,
    estimate_tokens,
)
from entropy.skills.manager import SkillManager, _normalize_tags


# --------------------------------------------------------------------------
# SKILL.md ayrıştırma
# --------------------------------------------------------------------------


def test_tags_accepts_both_yaml_forms():
    """YAML `tags` hem virgüllü dize hem de liste olabilir; ikisi de okunmalı."""
    assert _normalize_tags("a, b, c") == ["a", "b", "c"]
    assert _normalize_tags(["a", "b", "c"]) == ["a", "b", "c"]
    assert _normalize_tags(None) == []
    assert _normalize_tags("") == []


def _write_skill(root: Path, name: str, tags_line: str) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: \"{name} testi\"\n{tags_line}\n---\n\n# {name}\n\nTalimatlar.\n",
        encoding="utf-8",
    )
    return d


def test_skill_with_yaml_list_tags_is_not_dropped(tmp_path):
    """
    Liste biçimli tags taşıyan yetenek kataloğa girmeli.

    Regresyon: .split(',') bir listede AttributeError fırlatıyor, geniş except
    None döndürüyor ve yetenek hiç yokmuş gibi davranılıyordu.
    """
    _write_skill(tmp_path, "list-tags-skill", "tags: [alpha, beta, gamma]")
    _write_skill(tmp_path, "string-tags-skill", "tags: alpha, beta")

    sm = SkillManager(root_skills_dir=tmp_path)
    names = {s.name for s in sm.list_skills()}
    assert names == {"list-tags-skill", "string-tags-skill"}

    listed = next(s for s in sm.list_skills() if s.name == "list-tags-skill")
    assert listed.tags == ["alpha", "beta", "gamma"]


def test_isolated_root_does_not_leak_global_skills(tmp_path):
    """Açık kök verildiğinde yalnızca o dizin taranmalı (izole testler için)."""
    _write_skill(tmp_path, "only-skill", "tags: x")
    sm = SkillManager(root_skills_dir=tmp_path)
    assert [s.name for s in sm.list_skills()] == ["only-skill"]


def test_manifest_stays_compact_and_expands_active_skill(tmp_path):
    """
    Katalog her turda enjekte edildiği için kısa kalmalı; yalnızca seçili
    yetenek araçlarıyla genişlemeli.
    """
    d = _write_skill(tmp_path, "tooled-skill", "tags: x")
    scripts = d / "scripts"
    scripts.mkdir()
    for i in range(20):
        (scripts / f"tool_{i}.py").write_text("pass\n", encoding="utf-8")

    sm = SkillManager(root_skills_dir=tmp_path)
    plain = sm.get_skills_manifest()
    expanded = sm.get_skills_manifest(active_skill="tooled-skill")

    assert "tool_0.py" not in plain, "katalog araç yollarını listelememeli"
    assert "tool_0.py" in expanded, "seçili yetenek araçlarıyla açılmalı"
    assert len(expanded) > len(plain)
    # Araç listesi tavanla sınırlanmalı
    assert expanded.count("tool_") <= SkillManager.MANIFEST_MAX_SCRIPTS


# --------------------------------------------------------------------------
# Rapor keşfi ve indeks
# --------------------------------------------------------------------------


def _vault_with_reports(root: Path) -> Path:
    ent = root / "Entropy"
    (ent / "Reports").mkdir(parents=True)
    (ent / "DailyNotes").mkdir(parents=True)

    body = "x" * 800
    (ent / "Reports" / "gercek_rapor.md").write_text(f"---\ntitle: R\n---\n\n{body}\n", encoding="utf-8")
    (ent / "MEMORY.md").write_text(f"# Bellek\n\n{body}\n", encoding="utf-8")
    (ent / "BELLEK_HARITASI.md").write_text(f"# Harita\n\n{body}\n", encoding="utf-8")
    (ent / "DailyNotes" / "2026-09-07.md").write_text(f"# Gunluk\n\n{body}\n", encoding="utf-8")
    (ent / "Reports" / "bos.md").write_text("kisa\n", encoding="utf-8")
    return root


def test_discover_reports_excludes_journals_and_indexes(tmp_path):
    """MEMORY.md, günlük notlar ve içerik haritaları yordam kaynağı değildir."""
    _vault_with_reports(tmp_path)
    found = {p.stem for p in discover_reports(tmp_path)}
    assert found == {"gercek_rapor"}


def test_report_index_roundtrip_and_lookup(tmp_path):
    _vault_with_reports(tmp_path)
    idx = SkillReportIndex(index_path=tmp_path / "idx.json")
    reports = discover_reports(tmp_path)

    dist = idx.rebuild(reports, classify=lambda title, head: "demo")
    assert dist == {"demo": 1}
    assert (tmp_path / "idx.json").is_file()

    reloaded = SkillReportIndex(index_path=tmp_path / "idx.json")
    assert [p.stem for p in reloaded.paths_for("demo")] == ["gercek_rapor"]
    assert reloaded.paths_for("yok-boyle-yetenek") == []


# --------------------------------------------------------------------------
# Damıtma döngüsü
# --------------------------------------------------------------------------


DISTILLED = """## Ne Zaman Kullanilir
Site denetimi gerektiginde.

## Calisma Adimlari
1. Teknik tarama.
2. Icerik bosluklari.
"""


def _skill_vault(root: Path, skill: str, n_reports: int) -> PlaybookStore:
    rep = root / "Entropy" / "Skills" / skill / "Reports"
    rep.mkdir(parents=True, exist_ok=True)
    for i in range(n_reports):
        (rep / f"r{i}.md").write_text(
            f"---\ntitle: R{i}\n---\n\nTeknik SEO taramasi ve icerik bosluklari analizi {i}.\n" + "y" * 500,
            encoding="utf-8",
        )
    return PlaybookStore(vault_path=root, index=SkillReportIndex(index_path=root / "idx.json"))


def test_distillation_lifecycle(tmp_path):
    """kaynak yok -> damıtılmalı -> damıtıldı -> güncel -> yeni rapor -> değişim."""
    store = _skill_vault(tmp_path, "demo", 3)
    d = PlaybookDistiller(store=store)

    assert store.load("demo") is None
    plan = d.plan("demo")
    assert plan["sources_total"] == 3
    assert plan["should_run"] is True

    pb = d.run_with_bridge("demo", send_prompt=lambda prompt: DISTILLED)
    assert pb is not None
    assert pb.source_count == 3
    assert pb.version == 1
    assert "Calisma Adimlari" in pb.procedure
    assert store.playbook_path("demo").is_file()

    assert d.plan("demo")["should_run"] is False

    # Yeni rapor eklenince parmak izi değişmeli
    (tmp_path / "Entropy" / "Skills" / "demo" / "Reports" / "yeni.md").write_text(
        "---\ntitle: Yeni\n---\n\nEk bulgu.\n" + "z" * 500, encoding="utf-8"
    )
    assert store.status("demo")["state"] != "guncel"


def test_multi_pass_distillation_continues_and_refines(tmp_path, monkeypatch):
    """
    Kaynak sayısı tur kapasitesini aşınca: ilk tur 'kısmi' bırakır, ikinci tur
    kaldığı yerden devam eder ve mevcut yordamı prompt'a verir, son tur 'güncel' yapar.
    """
    import entropy.memory.distiller as dmod

    monkeypatch.setattr(dmod, "MAX_SOURCES_PER_PASS", 3)
    store = _skill_vault(tmp_path, "demo", 7)
    d = PlaybookDistiller(store=store)

    p1 = d.prepare("demo")
    assert p1["batch_start"] == 0 and len(p1["sources"]) == 3
    assert "MEVCUT YORDAM" not in p1["prompt"]
    d.complete(p1, "## Adimlar\n1. Ilk tur.")
    st = store.status("demo")
    assert st["state"] == "kismi" and st["needs_refresh"] and st["distilled_from"] == 3

    p2 = d.prepare("demo")
    assert p2["batch_start"] == 3 and len(p2["sources"]) == 3
    assert "MEVCUT YORDAM" in p2["prompt"] and "Ilk tur" in p2["prompt"]
    d.complete(p2, "## Adimlar\n1. Ilk tur.\n2. Ikinci tur.")
    assert store.status("demo")["distilled_from"] == 6

    p3 = d.prepare("demo")
    assert p3["batch_start"] == 6 and len(p3["sources"]) == 1
    pb = d.complete(p3, "## Adimlar\n1-3 birlesik.")
    assert pb.version == 3 and pb.processed_count == 7
    assert store.status("demo")["state"] == "guncel"
    # Her şey işlenmişken açık istek tek turluk bir tazelemedir: en yeni grup,
    # mevcut yordamla birlikte; sayaç toplamda kalır (0'a dönmez, zincirlenmez).
    p4 = d.prepare("demo")
    assert p4["refresh"] is True and "MEVCUT YORDAM" in p4["prompt"]
    assert p4["batch_start"] == 4 and len(p4["sources"]) == 3 and p4["processed_after"] == 7
    pb4 = d.complete(p4, "## Adimlar\n1-3 birlesik.\n4. Tazelendi.")
    assert pb4.processed_count == 7 and store.status("demo")["state"] == "guncel"
    assert d.plan("demo")["should_run"] is False, "otomatik listede görünmemeli"


def test_playbook_without_processed_field_counts_as_fully_read():
    text = SkillPlaybook(skill="x", procedure="## A\nb", source_count=5, processed_count=5).to_markdown()
    assert "processed_count: 5\n" in text
    text = text.replace("processed_count: 5\n", "")
    assert SkillPlaybook.from_markdown(text).processed_count == 5


def test_context_keeps_short_playbook_sections_and_trims_steps(tmp_path):
    """Bütçe daralınca 'Çalışma Adımları' kırpılmalı, ölçüt ve tuzaklar tam kalmalı."""
    store = _skill_vault(tmp_path, "demo", 1)
    steps = "## Çalışma Adımları\n" + "\n".join(f"{i}. adim metni uzun uzun" for i in range(400))
    proc = (
        "## Ne Zaman Kullanılır\nSite denetiminde.\n\n"
        f"{steps}\n\n"
        "## Karar Ölçütleri\nMarj > %60 ise BOGO.\n\n"
        "## Bilinen Tuzaklar\nNegatif kelimesiz kampanya.\n"
    )
    store.save(SkillPlaybook(skill="demo", procedure=proc))
    builder = CognitiveContextBuilder(
        memory_system=_StubMemory([]), vault_manager=_StubVault(""), playbook_store=store
    )
    sec = builder._playbook_section("demo", 300)
    assert sec.tokens <= 300
    assert "Marj > %60 ise BOGO" in sec.body
    assert "Negatif kelimesiz" in sec.body
    assert "Site denetiminde" in sec.body
    assert "399. adim" not in sec.body, "adımlar kırpılmalı"


def test_degenerate_output_is_rejected_and_existing_kept(tmp_path):
    """
    Zenginleştirme turunda kısa/bölümsüz çıktı mevcut yordamı ezmemeli.

    Regresyon: agy 'plan' modunda yordam yerine 1 KB'lık bir plan notu döndürdü ve
    9 KB'lık v4 sessizce silindi.
    """
    from entropy.memory.playbook import DegenerateDistillation

    store = _skill_vault(tmp_path, "demo", 2)
    d = PlaybookDistiller(store=store)
    rich = "\n\n".join(
        f"## {h}\n" + ("madde " * 120).strip()
        for h in ("Ne Zaman Kullanılır", "Çalışma Adımları", "Karar Ölçütleri", "Bilinen Tuzaklar", "Çıktı Biçimi")
    )
    good = d.run_with_bridge("demo", send_prompt=lambda p: rich)
    assert good.version == 1 and len(good.procedure) > 3000

    stub = "Plan hazırlandı; onayladığınızda dosyaya yazabilirim."
    with pytest.raises(DegenerateDistillation):
        d.complete(d.prepare("demo"), stub)

    kept = store.load("demo")
    assert kept.version == 1 and kept.procedure == good.procedure

    # Yeterince uzun ve bölümlü bir çıktı yine kabul edilmeli
    better = rich + "\n\n## Ek\nyeni bulgu"
    pb2 = d.complete(d.prepare("demo"), better)
    assert pb2.version == 2


def test_distiller_returns_none_without_sources(tmp_path):
    store = PlaybookStore(vault_path=tmp_path, index=SkillReportIndex(index_path=tmp_path / "idx.json"))
    d = PlaybookDistiller(store=store)
    assert d.prepare("bos-yetenek") is None
    assert d.run_with_bridge("bos-yetenek", send_prompt=lambda p: DISTILLED) is None


def test_distilled_output_is_cleaned_and_capped(tmp_path):
    """Model frontmatter/kod çiti ekleyebilir; ikisi de temizlenmeli."""
    store = _skill_vault(tmp_path, "demo", 1)
    d = PlaybookDistiller(store=store)

    pb = d.run_with_bridge("demo", send_prompt=lambda p: "```markdown\n## Adimlar\n1. Bir\n```")
    assert pb.procedure.startswith("## Adimlar")
    assert "```" not in pb.procedure

    huge = "## Adimlar\n" + ("uzun metin " * 5000)
    pb2 = d.run_with_bridge("demo", send_prompt=lambda p: huge)
    assert len(pb2.procedure) <= PLAYBOOK_MAX_CHARS + 200  # tavan + kesme notu
    assert pb2.version == 2, "yeniden damıtma sürümü artırmalı"


def test_distilled_output_truncates_at_paragraph_boundary(tmp_path):
    """Tavan aşıldığında kesim cümle ortasında değil paragraf sınırında olmalı."""
    store = _skill_vault(tmp_path, "demo", 1)
    d = PlaybookDistiller(store=store)
    paragraphs = [f"## Bolum {i}\n" + ("madde metni " * 40).strip() for i in range(40)]
    huge = "\n\n".join(paragraphs)
    pb = d.run_with_bridge("demo", send_prompt=lambda p: huge)
    body = pb.procedure.replace("\n\n_(uzunluk sınırında kesildi)_", "")
    assert len(body) <= PLAYBOOK_MAX_CHARS
    assert body.endswith("madde metni"), "kesim bir paragrafın sonunda olmalı, kelime ortasında değil"
    assert pb.procedure.endswith("_(uzunluk sınırında kesildi)_")


def test_playbook_markdown_roundtrip():
    pb = SkillPlaybook(skill="demo", procedure="## Adimlar\n1. Bir", source_count=7, source_digest="abc123")
    parsed = SkillPlaybook.from_markdown(pb.to_markdown())
    assert parsed.skill == "demo"
    assert parsed.source_count == 7
    assert parsed.source_digest == "abc123"
    assert parsed.procedure.startswith("## Adimlar")


# --------------------------------------------------------------------------
# Bütçeli bağlam
# --------------------------------------------------------------------------


class _StubMemory:
    def __init__(self, nodes):
        self._nodes = nodes

    def hybrid_recall(self, query, top_k=5):
        return self._nodes[:top_k]


class _StubNode:
    def __init__(self, content):
        self.content = content
        self.category = "semantic"


class _StubVault:
    def __init__(self, text=""):
        self._text = text

    def read_global_memory(self):
        return self._text


def test_context_respects_token_budget(tmp_path):
    """Bütçe aşılmamalı; kaynak ne kadar büyük olursa olsun."""
    store = _skill_vault(tmp_path, "demo", 5)
    store.save(SkillPlaybook(skill="demo", procedure="## Yordam\n" + ("adim " * 4000)))

    memory = _StubMemory([(_StubNode("ani " * 500), 0.9) for _ in range(20)])
    vault = _StubVault("kalici hafiza " * 2000)

    builder = CognitiveContextBuilder(memory_system=memory, vault_manager=vault, playbook_store=store)
    ctx = builder.build("teknik seo taramasi", skill_name="demo", token_budget=1200)

    assert ctx.tokens <= 1200, f"bütçe aşıldı: {ctx.tokens}"
    assert estimate_tokens(ctx.render()) <= 1400


def test_playbook_takes_priority_over_other_sections(tmp_path):
    """Playbook varsa bağlamın ilk bölümü olmalı."""
    store = _skill_vault(tmp_path, "demo", 2)
    store.save(SkillPlaybook(skill="demo", procedure="## Yordam\nBir adim."))

    builder = CognitiveContextBuilder(
        memory_system=_StubMemory([(_StubNode("bir ani"), 0.8)]),
        vault_manager=_StubVault("global"),
        playbook_store=store,
    )
    ctx = builder.build("teknik seo", skill_name="demo")
    assert ctx.sections[0].kind == "playbook"


def test_context_without_skill_has_no_playbook_or_reports(tmp_path):
    store = PlaybookStore(vault_path=tmp_path, index=SkillReportIndex(index_path=tmp_path / "idx.json"))
    builder = CognitiveContextBuilder(
        memory_system=_StubMemory([(_StubNode("bir ani"), 0.8)]),
        vault_manager=_StubVault(""),
        playbook_store=store,
    )
    ctx = builder.build("herhangi bir soru")
    kinds = {s.kind for s in ctx.sections}
    assert "playbook" not in kinds
    assert "reports" not in kinds


def test_best_excerpt_picks_relevant_paragraph():
    """Belgenin başı değil, sorguya en yakın paragraf seçilmeli."""
    body = (
        "Giris paragrafi, alakasiz baslik tekrari.\n\n"
        "Ikinci paragraf da alakasiz.\n\n"
        "Backlink profili ve organik trafik karsilastirmasi burada anlatiliyor.\n\n"
        "Son paragraf.\n"
    )
    out = _best_excerpt(body, "backlink organik trafik", 200)
    assert "Backlink profili" in out
    assert not out.startswith("Giris paragrafi")


def test_context_survives_failing_section(tmp_path):
    """Bir bölüm patlarsa bağlamın tamamı kaybolmamalı."""

    class _Boom:
        def hybrid_recall(self, *a, **k):
            raise RuntimeError("bellek yok")

    store = _skill_vault(tmp_path, "demo", 1)
    store.save(SkillPlaybook(skill="demo", procedure="## Yordam\nBir adim."))

    builder = CognitiveContextBuilder(
        memory_system=_Boom(), vault_manager=_StubVault("global"), playbook_store=store
    )
    ctx = builder.build("soru", skill_name="demo")
    kinds = {s.kind for s in ctx.sections}
    assert "playbook" in kinds, "diğer bölümler yine de kurulmalı"
