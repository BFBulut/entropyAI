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
    # Her şey işlenmişken açık istek bir tazelemedir: arşiv baştan taranır,
    # mevcut yordamla birlikte; sayaç toplamda kalır (0'a dönmez).
    # Tur boyutu 3 olduğu için tazeleme üç turluk bir zincirdir.
    p4 = d.prepare("demo")
    assert p4["refresh"] is True and "MEVCUT YORDAM" in p4["prompt"]
    assert p4["batch_start"] == 0 and len(p4["sources"]) == 3 and p4["processed_after"] == 7
    assert p4["refresh_end"] == 3 and p4["refresh_total"] == 7
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


# --------------------------------------------------------------------------
# Maliyet düşürme: yordam taşıyan alıntı + yakın-kopya eleme
# --------------------------------------------------------------------------


def test_procedural_excerpt_prefers_steps_over_narrative():
    """Ham ön ek yerine yordam taşıyan bloklar seçilmeli."""
    from entropy.memory.playbook import procedural_excerpt

    body = (
        "Bu rapor 2026 yilinda hazirlanmistir ve genel bir girise sahiptir. " * 12
        + "\n\nAnlatisal ikinci paragraf, hicbir yordam tasimaz. " * 12
        + "\n\n## Yontem\n1. Once teknik tarama yapilir, adim adim.\n"
        "2. Sonra kontrol listesi uygulanir.\n3. Tuzak: negatif kelime unutulmaz.\n"
    )
    out = procedural_excerpt(body, 400)
    assert "## Yontem" in out, "yordam blogu secilmeli"
    assert len(out) <= 400
    assert "Anlatisal ikinci paragraf" not in out


def test_procedural_excerpt_falls_back_to_prefix_when_nothing_scores():
    from entropy.memory.playbook import procedural_excerpt

    body = "duz metin " * 500
    out = procedural_excerpt(body, 200)
    assert out and len(out) <= 200


def test_known_content_loses_priority_to_new_content():
    """Mevcut yordamda zaten geçen blok, yeni bilgi taşıyan bloğa yer bırakmalı."""
    from entropy.memory.playbook import _shingles, procedural_excerpt

    bilinen = "## Adim\n1. Teknik tarama yapilir ve sonuclar karsilastirilir sirayla.\n"
    yeni = "## Adim\n1. Rakip backlink profili cikarilir ve bosluk analizi yapilir.\n"
    body = bilinen + "\n" + yeni
    out = procedural_excerpt(body, len(yeni) + 5, known_shingles=_shingles(bilinen))
    assert "backlink" in out


def test_near_duplicate_reports_collapse_to_one_representative(tmp_path):
    from entropy.memory.playbook import select_representatives

    d = tmp_path / "r"
    d.mkdir()
    ortak = " ".join(f"teknik seo tarama adimi numara {i} kontrol" for i in range(60))
    paths = []
    for i in range(3):
        p = d / f"kopya{i}.md"
        p.write_text(ortak + f"\nkucuk fark {i}\n", encoding="utf-8")
        paths.append(p)
    farkli = d / "farkli.md"
    farkli.write_text(
        " ".join(f"birim ekonomisi marj hesabi kalem {i} butce" for i in range(60)),
        encoding="utf-8",
    )
    paths.append(farkli)

    reps, followers = select_representatives(paths)
    assert [p.name for p in reps] == ["kopya0.md", "farkli.md"]
    assert set(followers["kopya0.md"]) == {"kopya1.md", "kopya2.md"}


def test_short_reports_are_never_eliminated_as_duplicates(tmp_path):
    """Parmak izi çıkarılamayan rapor elenmemeli; eleme ancak ölçülebilirse yapılır."""
    from entropy.memory.playbook import select_representatives

    d = tmp_path / "r"
    d.mkdir()
    paths = []
    for i in range(4):
        p = d / f"k{i}.md"
        p.write_text("ab cd\n", encoding="utf-8")
        paths.append(p)
    reps, followers = select_representatives(paths)
    assert len(reps) == 4 and followers == {}


def _big_vault(root: Path, skill: str, n: int) -> PlaybookStore:
    """Birbirinden farklı n rapor: yakın-kopya elemesi devreye girmesin."""
    rep = root / "Entropy" / "Skills" / skill / "Reports"
    rep.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        gövde = " ".join(f"konu{i}_terim{j} ozgun icerik satiri" for j in range(120))
        (rep / f"r{i:03d}.md").write_text(
            f"---\ntitle: R{i}\n---\n\n## Yontem {i}\n1. Adim {i} uygulanir.\n\n{gövde}\n",
            encoding="utf-8",
        )
    return PlaybookStore(vault_path=root, index=SkillReportIndex(index_path=root / "idx.json"))


def test_large_archive_switches_to_compact_passes_and_costs_less(tmp_path):
    """
    Büyük arşiv: tur başına daha çok rapor, rapor başına daha kısa yordam alıntısı.
    Toplam tahmini maliyet klasik şeklin belirgin altında kalmalı.
    """
    from entropy.memory.distiller import (
        COMPACT_EXCERPT_CHARS,
        COMPACT_MIN_SOURCES,
        COMPACT_SOURCES_PER_PASS,
        estimate_chain_cost,
    )
    from entropy.memory.playbook import DISTILL_EXCERPT_CHARS

    n = COMPACT_MIN_SOURCES + 8
    store = _big_vault(tmp_path, "demo", n)
    d = PlaybookDistiller(store=store)

    plan = d.plan("demo")
    assert plan["compact"] is True
    assert plan["sources_per_pass"] == COMPACT_SOURCES_PER_PASS
    assert plan["excerpt_chars"] == COMPACT_EXCERPT_CHARS
    assert plan["estimated_total_passes"] >= 1
    assert plan["estimated_total_tokens"] > 0

    klasik = estimate_chain_cost(n, 24, DISTILL_EXCERPT_CHARS, 1000)
    assert plan["estimated_total_passes"] < klasik["passes"]
    assert plan["estimated_total_tokens"] < 0.4 * klasik["tokens"], (
        f"hedef %40; ölçülen {plan['estimated_total_tokens'] / klasik['tokens']:.0%}"
    )

    prep = d.prepare("demo")
    assert prep["compact"] is True
    assert len(prep["sources"]) == COMPACT_SOURCES_PER_PASS
    # Alıntılar kısaldı: prompt, klasik şeklin tur boyutunu aşmamalı.
    assert prep["prompt_tokens"] <= (24 * DISTILL_EXCERPT_CHARS) // 4 + 1000


def test_small_archive_behaviour_is_unchanged(tmp_path):
    """Küçük arşivde şekil ve maliyet aynen korunmalı (regresyon kilidi)."""
    from entropy.memory.distiller import MAX_SOURCES_PER_PASS
    from entropy.memory.playbook import DISTILL_EXCERPT_CHARS

    store = _big_vault(tmp_path, "demo", 16)
    d = PlaybookDistiller(store=store)
    plan = d.plan("demo")
    assert plan["compact"] is False
    assert plan["sources_per_pass"] == MAX_SOURCES_PER_PASS
    assert plan["excerpt_chars"] == DISTILL_EXCERPT_CHARS
    assert plan["duplicates_skipped"] == 0
    assert plan["estimated_total_passes"] == 1
    assert d.prepare("demo")["compact"] is False


def test_duplicates_are_marked_processed_so_chain_terminates(tmp_path):
    """Okunmayan kopyalar işlenmiş sayılmazsa zincir hiç bitmez."""
    from entropy.memory.distiller import COMPACT_MIN_SOURCES

    skill = "demo"
    rep = tmp_path / "Entropy" / "Skills" / skill / "Reports"
    rep.mkdir(parents=True)
    n = COMPACT_MIN_SOURCES + 4
    ortak = " ".join(f"ayni yordam adimi {j} kontrol listesi" for j in range(80))
    for i in range(n):
        (rep / f"r{i:03d}.md").write_text(f"## Yontem\n{ortak}\nfark {i}\n", encoding="utf-8")
    store = PlaybookStore(vault_path=tmp_path, index=SkillReportIndex(index_path=tmp_path / "idx.json"))
    d = PlaybookDistiller(store=store)

    plan = d.plan(skill)
    assert plan["duplicates_skipped"] > 0, "neredeyse aynı raporlar elenmeli"
    assert plan["effective_sources"] < n

    prep = d.prepare(skill)
    pb = d.complete(prep, "## Çalışma Adımları\n1. Tara.\n\n## Karar Ölçütleri\n- Eşik.")
    assert pb.processed_count == n, "elenen kopyalar da işlenmiş sayılmalı"
    assert store.status(skill)["state"] == "guncel"


# --------------------------------------------------------------------------
# Playbook kalite ölçütü
# --------------------------------------------------------------------------


def _rich_playbook() -> str:
    return (
        "## Ne Zaman Kullanılır\nDenetim gerektiğinde.\n\n"
        "## Çalışma Adımları\n1. Tara.\n2. Karşılaştır.\n3. Doğrula.\n\n"
        "## Karar Ölçütleri\n- Marj %60 üstündeyse ilerle.\n- Aksi hâlde durdur.\n\n"
        "## Bilinen Tuzaklar\n- Negatif kelime unutulur.\n- Örneklem küçük seçilir.\n\n"
        "## Çıktı Biçimi\n- Başlık, bulgular, öneriler.\n"
    )


def test_playbook_quality_measures_coverage_steps_and_repetition():
    from entropy.memory.playbook import playbook_quality

    good = playbook_quality(_rich_playbook())
    assert good["coverage"] == 1.0
    assert good["missing"] == []
    assert good["step_count"] >= 8
    assert good["repetition"] < 0.2
    assert good["score"] > 0.6

    tekrar = playbook_quality("## Çalışma Adımları\n" + ("ayni cumle tekrar eder durmadan " * 200))
    assert tekrar["coverage"] == 0.25
    assert tekrar["repetition"] > 0.8
    assert set(tekrar["missing"]) == {"criteria", "pitfalls", "output"}
    assert tekrar["score"] < good["score"]


def test_quality_regression_rejects_long_but_sectionless_output(tmp_path):
    """
    Uzunluk ve başlık sayısı kaba ölçüler: uzun ama bölümlerini kaybetmiş bir
    çıktı ikisini de geçebiliyor. Kalite ölçütü onu reddetmeli.
    """
    from entropy.memory.playbook import DegenerateDistillation, playbook_quality

    store = _skill_vault(tmp_path, "demo", 2)
    d = PlaybookDistiller(store=store)
    pb = d.run_with_bridge("demo", send_prompt=lambda p: _rich_playbook())
    assert playbook_quality(pb.procedure)["coverage"] == 1.0

    # Beş başlık, mevcuttan uzun — ama zorunlu bölümlerin hiçbiri yok.
    kotu = "\n\n".join(f"## Notlar {i}\n" + ("genel gozlem metni " * 40) for i in range(5))
    assert len(kotu) > len(pb.procedure)
    with pytest.raises(DegenerateDistillation):
        d.complete(d.prepare("demo"), kotu)
    assert store.load("demo").procedure == pb.procedure

    # Bölümleri koruyan, zenginleşmiş çıktı kabul edilmeli.
    iyi = _rich_playbook() + "\n## Ek Not\n- Yeni bulgu.\n"
    assert d.complete(d.prepare("demo"), iyi).version == 2


def test_immature_playbook_is_not_guarded_by_quality(tmp_path):
    """Kapsamı düşük bir taslak, kalite kapısını kilitlememeli (zincir ilerlesin)."""
    store = _skill_vault(tmp_path, "demo", 2)
    d = PlaybookDistiller(store=store)
    d.run_with_bridge("demo", send_prompt=lambda p: "## Adimlar\n1. Bir.")
    pb2 = d.complete(d.prepare("demo"), "## Adimlar\n" + ("uzun metin " * 300))
    assert pb2 is not None and pb2.version == 2


# --------------------------------------------------------------------------
# Sorguya göre playbook bölüm seçimi
# --------------------------------------------------------------------------


def _wide_playbook() -> str:
    """Üç bölüm: ikisi uzun, ortadaki 'adımlar'. Sabit öncelik adımları düşürür."""
    ne_zaman = "## Ne Zaman Kullanılır\n" + "\n".join(f"- denetim notu {i} aciklama" for i in range(60))
    adimlar = "## Çalışma Adımları\n" + "\n".join(f"{i}. adim metni burada uzun uzun" for i in range(40))
    cikti = "## Çıktı Biçimi\n" + "\n".join(f"- ciktida yer alacak alan {i}" for i in range(60))
    return f"{ne_zaman}\n\n{adimlar}\n\n{cikti}\n"


def test_query_keeps_relevant_section_whole_and_digests_others(tmp_path):
    """
    Sorgu adımlarla ilgiliyse adımlar tam girmeli; ilgisiz bölümler başlık +
    ilk madde olarak kalmalı (tamamen düşmemeli).

    Sabit öncelik 'Çalışma Adımları'nı en sona bırakıp kırptığı için, tam da
    adımlar sorulduğunda en kötü bağlamı üretiyordu.
    """
    store = _skill_vault(tmp_path, "demo", 1)
    proc = _wide_playbook()
    store.save(SkillPlaybook(skill="demo", procedure=proc))
    b = CognitiveContextBuilder(
        memory_system=_StubMemory([]), vault_manager=_StubVault(""), playbook_store=store
    )

    sorgusuz = b._fit_playbook(proc, 600, "")
    sorgulu = b._fit_playbook(proc, 600, "adim adim ne yapmaliyim")

    assert estimate_tokens(sorgulu) <= 600
    assert "39. adim metni" in sorgulu, "ilgili bölüm tam girmeli"
    assert "39. adim metni" not in sorgusuz, "sabit öncelik adımları kırpıyordu"
    assert "## Çıktı Biçimi" in sorgulu, "ilgisiz bölümün başlığı kalmalı"


def test_query_matching_tolerates_turkish_suffixes_and_diacritics(tmp_path):
    """'adim' yazan kullanıcı 'Çalışma Adımları' bölümünü bulabilmeli."""
    store = _skill_vault(tmp_path, "demo", 1)
    proc = _wide_playbook()
    b = CognitiveContextBuilder(
        memory_system=_StubMemory([]), vault_manager=_StubVault(""), playbook_store=store
    )
    # Sorgu aksansız ve ekli; başlık aksanlı ve farklı ekli.
    assert "39. adim metni" in b._fit_playbook(proc, 600, "calisma adimlarini anlat")
    # Alakasız sorgu aynı bölümü seçmemeli.
    assert "39. adim metni" not in b._fit_playbook(proc, 600, "ciktida hangi alanlar olacak")


def test_query_selection_uses_the_whole_budget(tmp_path):
    """İlgili bölüm kısaysa artan bütçe diğer bölümlere geri verilmeli."""
    store = _skill_vault(tmp_path, "demo", 1)
    proc = (
        "## Karar Ölçütleri\n- Eşik %60.\n\n"
        "## Çalışma Adımları\n" + "\n".join(f"{i}. uzun adim metni" for i in range(200))
    )
    b = CognitiveContextBuilder(
        memory_system=_StubMemory([]), vault_manager=_StubVault(""), playbook_store=store
    )
    out = b._fit_playbook(proc, 400, "karar ölçütü eşik nedir")
    assert "Eşik %60" in out
    assert estimate_tokens(out) > 300, "artan bütçe boşa gitmemeli"
    assert estimate_tokens(out) <= 400


def test_query_without_match_falls_back_to_fixed_priority(tmp_path):
    """Hiçbir bölüm sorguyla eşleşmiyorsa eski davranış korunmalı."""
    store = _skill_vault(tmp_path, "demo", 1)
    proc = (
        "## Çalışma Adımları\n" + "\n".join(f"{i}. adim" for i in range(200)) + "\n\n"
        "## Karar Ölçütleri\n- Marj %60.\n"
    )
    b = CognitiveContextBuilder(
        memory_system=_StubMemory([]), vault_manager=_StubVault(""), playbook_store=store
    )
    out = b._fit_playbook(proc, 200, "zzzz qqqq wwww")
    assert "Marj %60" in out, "kısa ve kritik bölüm yine korunmalı"
