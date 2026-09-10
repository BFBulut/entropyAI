"""
Canlı rapor→yetenek atfı, artımlı damıtma ve oturum aktarımı (handoff) testleri.

Neden bu dosya var
------------------
Kullanıcı şikâyeti ölçülebilir bir kök nedene indi (gerçek kasa, 2026-09-09):
köprü, etkin bir proje varken raporu `Projects/<proje>/Reports/` altına yazıyor
ve yeteneği yalnızca `skill:` etiketi olarak bırakıyordu. `PlaybookStore` ise
etiketi SADECE düz `Entropy/Reports/` altında arıyordu. Gerçek kasada düz
klasörde etiketli 0, proje klasörlerinde 77 rapor vardı; bu yüzden google-flow
"kaynak yok" görünüyor, financial-auditor/autonomous-agent "güncel" kalıyordu.

Buradaki testler o davranışı ve onun etrafındaki artımlı akışı sabitler:
  - proje kapsamlı, etiketli rapor kaynak sayılır
  - yeni yetenek (klasörü olmayan) yalnızca etiketle kaynak bulur
  - rapor yazımı yeteneğe atfedilir ve indeks ANINDA artar (tam tarama yok)
  - "Damıt" artımlıdır; tazeleme ayrı ve açık bir eylemdir
  - aktarım sayfaları damıtma kaynağı DEĞİLDİR ama bağlama girer
"""

import json
from pathlib import Path

import pytest

from entropy.brain.distiller import PlaybookDistiller
from entropy.brain.handoff import (
    SECTION_ORDER,
    SECTION_TITLES,
    extract_sections,
    load_latest_handoff,
    pending_handoff,
    render_handoff,
    write_handoff,
)
from entropy.brain.playbook import (
    PlaybookStore,
    SkillReportIndex,
    classify_report,
    clear_file_facts_cache,
    discover_reports,
    index_new_reports,
    skill_tag_of,
)

REPORT_BODY = "\n".join(
    [
        "## Yöntem",
        "1. Kaynakları topla ve doğrula.",
        "2. Ölçütleri uygula, eşiği aşanları raporla.",
        "3. Bilinen tuzak: tek kaynağa güvenme.",
    ]
    + ["Ek gövde satırı, dosya 400 baytlık eşiği aşsın diye." for _ in range(12)]
)


def _write_report(path: Path, skill: str = "", title: str = "Rapor") -> Path:
    """Kasa biçiminde bir rapor yazar; `skill` verilirse frontmatter'a etiketlenir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = "entropy-ai, research-report" + (f", skill:{skill}" if skill else "")
    path.write_text(
        f"---\ntitle: \"{title}\"\ndate: 2026-09-09\ntags: [{tags}]\n---\n\n# {title}\n\n{REPORT_BODY}\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def vault(tmp_path):
    """İzole kasa; gerçek kasaya hiçbir koşulda yazılmaz."""
    root = tmp_path / "vault"
    (root / "Entropy" / "Reports").mkdir(parents=True)
    (root / "Entropy" / "Skills").mkdir(parents=True)
    (root / "Entropy" / "Projects").mkdir(parents=True)
    clear_file_facts_cache()
    yield root
    clear_file_facts_cache()


@pytest.fixture
def store(vault, tmp_path):
    return PlaybookStore(vault_path=vault, index=SkillReportIndex(tmp_path / "index.json"))


# --------------------------------------------------------------------------
# Kök neden: proje kapsamlı etiketli raporlar
# --------------------------------------------------------------------------


def test_project_scoped_tagged_report_counts_as_source(store, vault):
    """
    Kök neden testi: `Projects/<proje>/Reports/` altındaki etiketli rapor,
    yeteneğin kaynağı sayılmalı.

    Bu test düzeltmeden önce başarısızdır: source_reports yalnızca düz Reports/
    klasörünü tarıyordu ve gerçek kasadaki 77 etiketli raporun tamamı görünmezdi.
    """
    _write_report(vault / "Entropy" / "Projects" / "EntropiAI" / "Reports" / "P1.md", skill="financial-auditor")
    _write_report(vault / "Entropy" / "Projects" / "EntropiAI" / "Reports" / "P2.md", skill="financial-auditor")
    # Başka yeteneğin raporu karışmamalı.
    _write_report(vault / "Entropy" / "Projects" / "EntropiAI" / "Reports" / "P3.md", skill="autonomous-agent")

    names = [p.name for p in store.source_reports("financial-auditor")]
    assert sorted(names) == ["P1.md", "P2.md"]
    assert [p.name for p in store.source_reports("autonomous-agent")] == ["P3.md"]


def test_new_skill_without_folder_becomes_distillable(store, vault):
    """
    google-flow senaryosu: yetenek klasörü ve indeks girdisi yok, yalnızca
    etiketli raporlar var. Düğmenin açılabilmesi için durum "kaynak-yok"
    olmamalıdır.
    """
    for i in range(3):
        _write_report(
            vault / "Entropy" / "Projects" / "EntropiAI" / "Reports" / f"GF{i}.md",
            skill="google-flow",
            title=f"Google Flow {i}",
        )

    status = store.status("google-flow")
    assert status["source_count"] == 3
    assert status["state"] == "yok"
    assert status["needs_build"] is True


def test_flat_and_skill_scoped_reports_still_found(store, vault):
    """Düzeltme eski iki kaynağı (yetenek klasörü, düz etiketli) bozmamalı."""
    _write_report(vault / "Entropy" / "Skills" / "media" / "Reports" / "S1.md")
    _write_report(vault / "Entropy" / "Reports" / "F1.md", skill="media")
    assert sorted(p.name for p in store.source_reports("media")) == ["F1.md", "S1.md"]


def test_playbook_file_is_never_a_source(store, vault):
    """Damıtılmış yordamın kendisi kaynak sayılmamalı (kendi kendini damıtma)."""
    _write_report(vault / "Entropy" / "Projects" / "P" / "Reports" / "PLAYBOOK.md", skill="media")
    _write_report(vault / "Entropy" / "Projects" / "P" / "Reports" / "R1.md", skill="media")
    assert [p.name for p in store.source_reports("media")] == ["R1.md"]


# --------------------------------------------------------------------------
# Artımlı indeksleme
# --------------------------------------------------------------------------


def test_skill_tag_parsing():
    assert skill_tag_of("tags: [entropy-ai, skill:google-flow]") == "google-flow"
    assert skill_tag_of("tags: [entropy-ai, research-report]") is None


def test_index_add_is_incremental(tmp_path):
    """`add` tam yeniden tarama yapmadan tek yol ekler ve yinelemez."""
    index = SkillReportIndex(tmp_path / "i.json")
    p = tmp_path / "r.md"
    p.write_text("x", encoding="utf-8")
    assert index.add("skill-a", p) is True
    assert index.add("skill-a", p) is False  # aynı yol ikinci kez girmez
    assert json.loads((tmp_path / "i.json").read_text(encoding="utf-8")) == {"skill-a": [str(p)]}


def test_index_new_reports_only_reads_unknown_files(store, vault, monkeypatch):
    """
    Artımlı geçiş yalnızca indekste OLMAYAN dosyaları sınıflandırır.

    Ölçüt: sınıflandırıcı çağrı sayısı. İkinci geçişte hiç çağrılmamalı —
    aksi hâlde her yoklamada tüm kasa yeniden okunurdu.
    """
    for i in range(3):
        _write_report(vault / "Entropy" / "Reports" / f"U{i}.md", title=f"Untagged {i}")

    calls = []

    def classify(title, head):
        calls.append(title)
        return "skill-a"

    added = index_new_reports(store, {"skill-a"}, classify)
    assert added == {"skill-a": 3}
    assert len(calls) == 3

    calls.clear()
    assert index_new_reports(store, {"skill-a"}, classify) == {}
    assert calls == []


def test_tagged_report_skips_semantic_classifier(store, vault):
    """Etiket varsa anlamsal sınıflandırıcı hiç çağrılmamalı (tek dosya bile pahalı)."""
    p = _write_report(vault / "Entropy" / "Reports" / "T.md", skill="skill-a")

    def classify(title, head):  # pragma: no cover - çağrılmamalı
        raise AssertionError("etiketli rapor için sınıflandırıcı çağrıldı")

    assert classify_report(p, {"skill-a"}, classify) == "skill-a"


def test_save_research_report_prefers_skill_folder_and_indexes(vault, tmp_path, monkeypatch):
    """
    Rapor yazımı: yetenek biliniyorsa dosya Skills/<yetenek>/Reports/ altına
    düşer (proje verilmiş olsa bile) ve proje bağlamı etiket olarak korunur.
    """
    from entropy.brain.obsidian.vault_manager import ObsidianVaultManager

    vm = ObsidianVaultManager(vault_path=vault)
    path = vm.save_research_report(
        "Yeni Arastirma", REPORT_BODY, project_name="EntropiAI", skill_name="google-flow"
    )

    assert path.parent == vault / "Entropy" / "Skills" / "google-flow" / "Reports"
    text = path.read_text(encoding="utf-8")
    assert "skill:google-flow" in text
    assert "project:EntropiAI" in text  # proje bağlamı kaybolmadı

    clear_file_facts_cache()
    store = PlaybookStore(vault_path=vault, index=SkillReportIndex(tmp_path / "idx.json"))
    assert [p.name for p in store.source_reports("google-flow")] == ["Yeni Arastirma.md"]


# --------------------------------------------------------------------------
# Artımlı "Damıt" ve ayrı "Tazele"
# --------------------------------------------------------------------------


def _distiller(store):
    return PlaybookDistiller(store=store)


def test_distill_processes_only_unread_reports(store, vault):
    """Okunmamış rapor varsa tur yalnızca onları alır."""
    for i in range(3):
        _write_report(vault / "Entropy" / "Skills" / "media" / "Reports" / f"R{i}.md")

    d = _distiller(store)
    prepared = d.prepare("media")
    d.complete(prepared, "## Çalışma Adımları\n1. Adım\n2. Adım\n\n## Karar Ölçütleri\n- Ölçüt\n")
    assert d.unread_count("media") == 0

    _write_report(vault / "Entropy" / "Skills" / "media" / "Reports" / "R9.md", title="Yeni")
    clear_file_facts_cache()
    assert d.unread_count("media") == 1

    prepared2 = d.prepare("media", allow_refresh=False)
    assert prepared2 is not None
    assert [p.name for p in prepared2["sources"]] == ["R9.md"]
    assert prepared2["refresh"] is False


def test_distill_without_refresh_returns_none_when_all_read(store, vault):
    """
    Hepsi okunmuşsa "Damıt" hiçbir şey başlatmaz.

    Bu, "Damıt sıfırdan tazeleme yapıyor" şikâyetinin doğrudan karşılığı:
    kullanıcı onay vermeden tüm arşiv yeniden okunmamalı.
    """
    _write_report(vault / "Entropy" / "Skills" / "media" / "Reports" / "R0.md")
    d = _distiller(store)
    d.complete(d.prepare("media"), "## Çalışma Adımları\n1. Adım\n\n## Karar Ölçütleri\n- Ölçüt\n")

    assert d.prepare("media", allow_refresh=False) is None
    # Tazeleme açıkça istendiğinde çalışır ve tüm arşivi alır.
    refreshed = d.prepare("media", allow_refresh=True)
    assert refreshed is not None and refreshed["refresh"] is True


def test_plan_reports_unread_count(store, vault):
    _write_report(vault / "Entropy" / "Skills" / "media" / "Reports" / "R0.md")
    _write_report(vault / "Entropy" / "Skills" / "media" / "Reports" / "R1.md")
    plan = _distiller(store).plan("media")
    assert plan["unread"] == 2
    assert plan["sources_total"] == 2


# --------------------------------------------------------------------------
# ReportWatcher: canlı indeks
# --------------------------------------------------------------------------


def test_report_watcher_indexes_new_report_and_emits(qapp, store, vault):
    """
    Kasaya dışarıdan düşen rapor, uygulama yeniden başlatılmadan kaynak olmalı.

    İzleyicinin yoklama yolu doğrudan sürülür (QFileSystemWatcher olayını
    beklemek testi zamana bağımlı kılardı); ölçülen davranış: imza değişince
    indeks artımlı büyür ve `bus.reports_updated` yayılır.
    """
    from entropy.core.event_bus import bus
    from entropy.brain.report_watcher import ReportWatcher

    watcher = ReportWatcher(store=store, poll_interval_ms=5000)
    watcher.set_known_skills({"google-flow"})

    seen = []
    bus.reports_updated.connect(seen.append)
    try:
        _write_report(vault / "Entropy" / "Reports" / "Yeni.md", skill="google-flow")
        clear_file_facts_cache()
        watcher._check_now()

        assert seen == ["google-flow"]
        assert [p.name for p in store.source_reports("google-flow")] == ["Yeni.md"]

        # Değişiklik yoksa ikinci yoklama sessizdir: her 5 sn'de bir arayüz
        # yenilemek kartları titretir ve kasayı boşuna okur.
        seen.clear()
        watcher._check_now()
        assert seen == []
    finally:
        bus.reports_updated.disconnect(seen.append)
        watcher.stop()


def test_report_watcher_watches_all_report_dirs(qapp, store, vault):
    """Düz, proje ve yetenek kapsamlı rapor klasörlerinin üçü de izlenmeli."""
    from entropy.brain.report_watcher import ReportWatcher

    (vault / "Entropy" / "Projects" / "P" / "Reports").mkdir(parents=True)
    (vault / "Entropy" / "Skills" / "media" / "Reports").mkdir(parents=True)

    watcher = ReportWatcher(store=store, poll_interval_ms=5000).start()
    try:
        watched = {Path(d) for d in watcher.watched_dirs()}
        assert vault / "Entropy" / "Reports" in watched
        assert vault / "Entropy" / "Projects" / "P" / "Reports" in watched
        assert vault / "Entropy" / "Skills" / "media" / "Reports" in watched
    finally:
        watcher.stop()


# --------------------------------------------------------------------------
# Görev 3: aktarım sayfaları damıtma kaynağı değildir
# --------------------------------------------------------------------------


def test_handoff_pages_are_not_distillation_sources(store, vault):
    """
    Aktarım sayfası yordam değil OLAY taşır: damıtmaya girerse playbook,
    tekrar edilebilir bir yöntem yerine geçmişin günlüğüne dönüşür.
    """
    write_handoff(
        [{"role": "user", "content": "financial-auditor yeteneğini düzelt"},
         {"role": "assistant", "content": "Karar: indeks artımlı güncellenecek."}],
        {"topic": "financial auditor"},
        vault_path=vault,
        memory=_NullMemory(),
    )
    sessions = list((vault / "Entropy" / "Sessions").glob("*.md"))
    assert sessions, "aktarım sayfası yazılmadı"

    clear_file_facts_cache()
    discovered = {p.name for p in discover_reports(vault)}
    assert not (discovered & {p.name for p in sessions})
    assert store.source_reports("financial-auditor") == []


class _NullMemory:
    """Bilişsel bellek yerine geçen sahte: testler gerçek SQLite'a yazmasın."""

    def __init__(self):
        self.nodes = []

    def store_node(self, category, content, importance=0.5, metadata=None):
        self.nodes.append({"category": category, "content": content, "metadata": metadata or {}})
        return (None, True)


# --------------------------------------------------------------------------
# Görev 2: aktarım sayfası
# --------------------------------------------------------------------------


HISTORY = [
    {"role": "user", "content": "/distill index\nfinancial-auditor için yeni raporlar damıtılmıyor, kök nedeni bul."},
    {
        "role": "assistant",
        "content": (
            "Kök neden: raporlar src/entropy/brain/playbook.py tarafından yalnızca düz klasörde aranıyor.\n"
            "Karar: source_reports proje klasörlerini de taramalı.\n"
            "Hata: index_new_reports OSError verdi; çözüldü, try/except eklendi.\n"
            "Ölçüm: 77 rapor, ~1200 token, 0.12 s.\n"
            "Açık iş: ReportWatcher testi henüz yazılmadı.\n"
            "Sonraki adım: skills_widget.py içinde düğmeyi ikiye ayır."
        ),
    },
]


def test_write_handoff_creates_nine_sections(vault):
    """Sayfa dokuz bölümü de içermeli; boş bölüm '—' ile görünür."""
    path = write_handoff(HISTORY, {"topic": "rapor atfı"}, vault_path=vault, memory=_NullMemory())
    text = path.read_text(encoding="utf-8")
    for key in SECTION_ORDER:
        assert f"## {SECTION_TITLES[key]}" in text
    assert path.parent == vault / "Entropy" / "Sessions"
    assert "kind: handoff" in text


def test_handoff_extraction_is_evidence_based(vault):
    """Bölümler geçmişten çıkarımsal doldurulur; model çağrısı yoktur."""
    sections = extract_sections(HISTORY, {"skills": ["financial-auditor"]})
    assert any("kök neden" in s.lower() for s in sections["hedef"] + sections["kararlar"])
    assert any("source_reports" in s or "Karar" in s for s in sections["kararlar"])
    assert any("ReportWatcher" in s for s in sections["acik_isler"])
    assert any("skills_widget" in s for s in sections["sonraki_adim"])
    assert any("playbook.py" in s for s in sections["dosyalar"])
    assert any("çözüldü" in s.lower() or "hata" in s.lower() for s in sections["hatalar"])
    assert "financial-auditor" in sections["yetenekler"]
    assert "/distill" in sections["yetenekler"]
    assert any("token" in s for s in sections["olcumler"])


def test_handoff_masks_long_tool_output(vault):
    """Son turlar bölümünde uzun araç çıktısı maskelenmeli, ham gövde sızmamalı."""
    noise = "X" * 5000
    history = [
        {"role": "user", "content": "dosyayı oku"},
        {"role": "assistant", "content": f"[✔ ARAÇ TAMAMLANDI: Read (0.10s)]\nSonuç: {noise}"},
    ]
    path = write_handoff(history, {"topic": "maske"}, vault_path=vault, memory=_NullMemory())
    text = path.read_text(encoding="utf-8")
    assert noise not in text
    assert len(text) < 6000


def test_handoff_appends_log_and_stores_session_node(vault):
    mem = _NullMemory()
    write_handoff(HISTORY, {"topic": "birinci"}, vault_path=vault, memory=mem)
    write_handoff(HISTORY, {"topic": "ikinci"}, vault_path=vault, memory=mem)

    log = (vault / "Entropy" / "Sessions" / "log.md").read_text(encoding="utf-8")
    assert log.count("- [") == 2
    assert "birinci" in log and "ikinci" in log
    assert [n["category"] for n in mem.nodes] == ["session", "session"]
    assert mem.nodes[0]["metadata"]["kind"] == "handoff"


def test_same_day_same_topic_does_not_overwrite(vault):
    p1 = write_handoff(HISTORY, {"topic": "aynı konu"}, vault_path=vault, memory=_NullMemory())
    p2 = write_handoff(HISTORY, {"topic": "aynı konu"}, vault_path=vault, memory=_NullMemory())
    assert p1 != p2 and p1.exists() and p2.exists()


def test_load_latest_handoff_parses_sections(vault):
    write_handoff(HISTORY, {"topic": "yükleme"}, vault_path=vault, memory=_NullMemory())
    page = load_latest_handoff(vault)
    assert page is not None
    assert page["sections"]["hedef"]
    assert "Oturum Aktarımı" in page["title"]


def test_render_handoff_marks_empty_sections(vault):
    text = render_handoff({k: [] for k in SECTION_ORDER}, "", {}, "Boş")
    assert text.count("—") == len(SECTION_ORDER)


# --------------------------------------------------------------------------
# Bağlam kurucu: "Önceki oturum" bölümü
# --------------------------------------------------------------------------


def test_context_includes_previous_session_once(vault, tmp_path, monkeypatch):
    """
    Aktarım BİR SONRAKİ oturuma girer, her tura değil: 300 token her turda
    yeniden ödenirse aktarımın kazandırdığı bağlam maliyetiyle eşitlenir.
    """
    import entropy.brain.handoff as handoff_mod
    from entropy.brain.context_builder import BUDGET_HANDOFF, CognitiveContextBuilder

    monkeypatch.setattr(handoff_mod, "_CONSUMED_FILE", tmp_path / "consumed.json")
    write_handoff(HISTORY, {"topic": "önceki oturum"}, vault_path=vault, memory=_NullMemory())

    store = PlaybookStore(vault_path=vault, index=SkillReportIndex(tmp_path / "i.json"))
    builder = CognitiveContextBuilder(memory_system=_NullRecall(), vault_manager=_NullVault(), playbook_store=store)

    ctx = builder.build("rapor atfı nasıl düzeltildi", token_budget=4000)
    handoffs = [s for s in ctx.sections if s.kind == "handoff"]
    assert len(handoffs) == 1
    assert handoffs[0].tokens <= BUDGET_HANDOFF
    assert "Hedef:" in handoffs[0].body

    # İkinci turda aynı sayfa tekrar girmez.
    ctx2 = builder.build("devam", token_budget=4000)
    assert [s for s in ctx2.sections if s.kind == "handoff"] == []


def test_pending_handoff_respects_consumed_marker(vault, tmp_path, monkeypatch):
    import entropy.brain.handoff as handoff_mod

    monkeypatch.setattr(handoff_mod, "_CONSUMED_FILE", tmp_path / "c.json")
    path = write_handoff(HISTORY, {"topic": "işaret"}, vault_path=vault, memory=_NullMemory())
    assert pending_handoff(vault)["path"] == str(path)
    handoff_mod.mark_handoff_consumed(str(path))
    assert pending_handoff(vault) is None


# --------------------------------------------------------------------------
# Yerel komutlar: /handoff ve /distill refresh
# --------------------------------------------------------------------------


class _FakeBridge:
    """AGY köprüsü yerine geçen sahte: hiçbir model çağrısı yapılmaz."""

    def __init__(self, project_dir=None, history=None, compress=None):
        self.active_project_dir = project_dir
        self.conversation_history = list(history or [])
        self.started = []
        self._compress = compress

    def send_background_task_async(self, **kwargs):
        self.started.append(kwargs)

    if False:  # pragma: no cover
        pass


def test_handoff_command_writes_page_and_compresses(vault, tmp_path, monkeypatch):
    """`/handoff` sayfayı yazar ve köprünün sıkıştırma yöntemi VARSA çağırır."""
    import entropy.brain.handoff as handoff_mod
    from entropy.core.slash_commands import try_handle_local_command

    monkeypatch.setattr(handoff_mod.config, "obsidian_vault_path", vault, raising=False)
    monkeypatch.setattr(handoff_mod, "_CONSUMED_FILE", tmp_path / "c.json")
    monkeypatch.setattr(handoff_mod, "_store_session_node", lambda *a, **k: True)

    calls = []
    bridge = _FakeBridge(history=HISTORY)
    bridge.compress_history_with_handoff = lambda page: (calls.append(page) or True)

    out = try_handle_local_command("/handoff faz 1 bitti", bridge)
    assert out is not None and "Oturum Aktarımı Yazıldı" in out
    assert len(calls) == 1
    assert list((vault / "Entropy" / "Sessions").glob("*.md"))
    assert "Bağlam sıkıştırıldı" in out


def test_handoff_command_survives_bridge_without_compression(vault, tmp_path, monkeypatch):
    """
    Köprüde `compress_history_with_handoff` yoksa (paralel ajan henüz yazmadıysa)
    komut düşmemeli: sayfanın değeri sıkıştırmaya bağlı değildir.
    """
    import entropy.brain.handoff as handoff_mod
    from entropy.core.slash_commands import try_handle_local_command

    monkeypatch.setattr(handoff_mod.config, "obsidian_vault_path", vault, raising=False)
    monkeypatch.setattr(handoff_mod, "_CONSUMED_FILE", tmp_path / "c.json")
    monkeypatch.setattr(handoff_mod, "_store_session_node", lambda *a, **k: True)

    out = try_handle_local_command("/handoff", _FakeBridge(history=HISTORY))
    assert "Oturum Aktarımı Yazıldı" in out
    assert "bir sonraki oturuma" in out


def test_handoff_command_with_empty_history(vault, monkeypatch):
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/handoff", _FakeBridge(history=[]))
    assert "devredilecek bir şey bulunamadı" in out


def test_handoff_is_offered_in_command_palette():
    """`/handoff` komut paletinde görünmeli; yoksa kullanıcı varlığını bilemez."""
    from entropy.core.slash_commands import LOCAL_COMMANDS

    assert "/handoff" in {c.name for c in LOCAL_COMMANDS}


def test_distill_command_is_incremental_and_refresh_is_explicit(store, vault, monkeypatch):
    """
    `/distill <yetenek>` okunmamış yoksa hiçbir tur başlatmaz ve kullanıcıyı
    `refresh` alt komutuna yönlendirir; `/distill refresh` tazelemeyi başlatır.
    """
    from entropy.core import slash_commands as sc

    _write_report(vault / "Entropy" / "Skills" / "media" / "Reports" / "R0.md")
    d = _distiller(store)
    d.complete(d.prepare("media"), "## Çalışma Adımları\n1. Adım\n\n## Karar Ölçütleri\n- Ölçüt\n")

    class _Skill:
        name = "media"
        description = "test"
        enabled = True

    class _SM:
        def __init__(self, *a, **k):
            pass

        def list_skills(self):
            return [_Skill()]

    monkeypatch.setattr("entropy.skills.manager.SkillManager", _SM)
    bridge = _FakeBridge()

    out = sc.try_handle_local_command("/distill media", bridge, distiller=d)
    assert "okunmamış rapor yok" in out
    assert "/distill refresh media" in out
    assert bridge.started == []

    out2 = sc.try_handle_local_command("/distill refresh media", bridge, distiller=d)
    assert "Damıtma Başlatıldı" in out2
    assert len(bridge.started) == 1


def test_unknown_command_is_not_local():
    """`/handoffs` gibi başka bir komut yerel sanılıp AGY'ye gitmesi engellenmemeli."""
    from entropy.core.slash_commands import try_handle_local_command

    assert try_handle_local_command("/handoffs bir şey", _FakeBridge()) is None


class _NullRecall:
    def recall(self, *_a, **_k):
        return []

    def hybrid_recall(self, *_a, **_k):
        return []


class _NullVault:
    def get_research_reports(self):
        return []

    def read_global_memory(self):
        return ""
