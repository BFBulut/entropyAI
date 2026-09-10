"""
Faz 10-A — ofis çalışma belleği, kontrol noktaları, onaylı kalıcı kurallar.

Tüm testler tmp_path'te sahte bir kasa kullanır; gerçek kasa salt okunurdur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pytest

from entropy.memory import checkpoints, office_workspace, promoted_rules

OFFICE = "TestOfis"


@dataclass
class FakeCard:
    """TaskCard'ın pano için gereken alanları (kart katmanına bağlanmadan)."""

    id: str
    title: str = ""
    status: str = "backlog"
    agent: str = ""
    goal: str = ""
    summary: str = ""
    notes: str = ""
    criteria: List[str] = field(default_factory=list)


@pytest.fixture()
def vault(tmp_path):
    return tmp_path / "Vault"


# --------------------------------------------------------------- çalışma alanı


def test_ensure_workspace_creates_files(vault):
    paths = office_workspace.ensure_workspace(OFFICE, project_path="C:/proje", vault_path=vault)
    assert paths["workspace"].is_dir()
    assert paths["checkpoints"].is_dir()
    for key in ("board", "architecture", "rules"):
        assert paths[key].is_file(), key
    arch = paths["architecture"].read_text(encoding="utf-8")
    for section in office_workspace.ARCHITECTURE_SECTIONS:
        assert f"## {section}" in arch
    assert "C:/proje" in arch


def test_board_render_is_idempotent_and_reflects_cards(vault):
    cards = [
        FakeCard(id="k1", title="Şema", status="running", agent="kodcu", goal="tabloyu kur",
                 summary="ilk sürüm yazıldı"),
        FakeCard(id="k2", title="Test", status="backlog", agent="testçi", goal="kapsamı ölç"),
    ]
    office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    path = office_workspace.render_board(OFFICE, cards=cards, vault_path=vault)
    first = path.read_text(encoding="utf-8")
    mtime = path.stat().st_mtime_ns

    # Aynı kartlarla ikinci üretim: içerik aynı ve dosyaya dokunulmuyor.
    office_workspace.render_board(OFFICE, cards=cards, vault_path=vault)
    assert path.read_text(encoding="utf-8") == first
    assert path.stat().st_mtime_ns == mtime

    for column in office_workspace.BOARD_COLUMNS:
        assert column in first
    assert "Şema" in first and "kodcu" in first and "ilk sürüm yazıldı" in first
    # running kartı backlog'un üstünde olmalı.
    rows = [ln for ln in first.splitlines() if ln.startswith("| ") and "---" not in ln][1:]
    assert rows[0].startswith("| running") and rows[1].startswith("| backlog")


def test_board_handles_empty_office(vault):
    text = office_workspace.board_markdown(OFFICE, cards=[], vault_path=vault)
    assert "(kart yok)" in text


def test_update_architecture_appends_and_logs(vault):
    office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    office_workspace.update_architecture(OFFICE, "SQLite seçildi", author="orkestratör", vault_path=vault)
    office_workspace.update_architecture(
        OFFICE, "Kuyruk tek işçi", author="orkestratör", section="Bileşenler", vault_path=vault
    )
    text = office_workspace.ensure_workspace(OFFICE, vault_path=vault)["architecture"].read_text(
        encoding="utf-8"
    )
    assert "- SQLite seçildi" in text
    assert "- Kuyruk tek işçi" in text
    assert "## Değişiklik günlüğü" in text
    assert text.count("orkestratör") >= 2
    # Değiştirme kipi eski gövdeyi bırakmaz.
    office_workspace.update_architecture(
        OFFICE, "Postgres'e geçildi", author="o", section="Kararlar", replace=True, vault_path=vault
    )
    text2 = office_workspace.workspace_paths(OFFICE, vault)["architecture"].read_text(encoding="utf-8")
    assert "Postgres" in text2 and "SQLite seçildi" not in text2.split("## Değişiklik günlüğü")[0]


def test_ensure_workspace_keeps_architecture(vault):
    paths = office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    office_workspace.update_architecture(OFFICE, "Elle yazılmış karar", vault_path=vault)
    office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    assert "Elle yazılmış karar" in paths["architecture"].read_text(encoding="utf-8")


# --------------------------------------------------------------- doğuş talimatı


def _strip_paths(text: str) -> str:
    """
    Faz 10-B: artık hiçbir şey düşürmez.

    Desk'in veri kökü kasa köküne taşındığı için mutlak yollar da ürün adını
    taşımıyor; "yol satırlarını ölçme" istisnası kaldırıldı. Yardımcı, çağrı
    yerlerini bozmamak için kimliğe indirgendi.
    """
    return text


def test_spawn_instruction_size_and_no_product_name(vault):
    office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    rule = promoted_rules.propose_rule(OFFICE, "kodcu", "Testleri koşmadan kartı kapatma", "kart:k1", vault)
    promoted_rules.promote(OFFICE, rule.id, vault)
    checkpoints.write_checkpoint(
        OFFICE, "k1", summary="şema kuruldu", next_steps="pano bağlanacak",
        files_touched=["a.py"], author="kodcu", vault_path=vault,
    )
    text = office_workspace.spawn_instruction(OFFICE, card_id="k1", agent="kodcu", vault_path=vault)

    assert len(text) <= office_workspace.SPAWN_INSTRUCTION_MAX_CHARS
    assert text.startswith("İşe başlamadan önce şu dosyaları oku:")
    assert "BOARD.md" in text and "ARCHITECTURE.md" in text
    assert str(vault) in text  # yollar MUTLAK
    assert "şema kuruldu" in text  # kontrol noktası özeti
    assert "Testleri koşmadan kartı kapatma" in text  # onaylı kural
    # Ürün adı hiçbir yerde geçmez — yollar dâhil (Faz 10-B).
    assert "Entropy" not in _strip_paths(text)


def test_spawn_instruction_without_card_has_no_resume(vault):
    office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    text = office_workspace.spawn_instruction(OFFICE, vault_path=vault)
    assert "[KALDIĞIN YER]" not in text
    assert len(text) <= office_workspace.SPAWN_INSTRUCTION_MAX_CHARS


def test_spawn_instruction_trims_to_limit(vault):
    office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    for i in range(12):
        rule = promoted_rules.propose_rule(OFFICE, "kodcu", f"Kural numarası {i} her koşuda geçerlidir", "", vault)
        promoted_rules.promote(OFFICE, rule.id, vault)
    text = office_workspace.spawn_instruction(OFFICE, agent="kodcu", vault_path=vault, max_chars=300)
    assert len(text) <= 300
    assert "BOARD.md" in text  # dosya listesi en son düşer


# --------------------------------------------------------------- kontrol noktası


def test_write_read_checkpoint_roundtrip(vault):
    checkpoints.write_checkpoint(
        OFFICE, "kart-7", summary="ayrıştırıcı bitti", done="regex yazıldı",
        next_steps="harness'a bağla", files_touched=["src/a.py", "src/b.py"],
        tests="4 geçti", author="kodcu", vault_path=vault,
    )
    data = checkpoints.read_checkpoint(OFFICE, "kart-7", vault)
    assert data["summary"] == "ayrıştırıcı bitti"
    assert data["done"] == "regex yazıldı"
    assert data["next_steps"] == "harness'a bağla"
    assert data["files_touched"] == ["src/a.py", "src/b.py"]
    assert data["tests"] == "4 geçti"
    assert data["author"] == "kodcu"
    assert data["history"] == []


def test_checkpoint_overwrite_keeps_history(vault):
    checkpoints.write_checkpoint(OFFICE, "kart-8", summary="birinci tur", author="a", vault_path=vault)
    checkpoints.write_checkpoint(OFFICE, "kart-8", summary="ikinci tur", author="a", vault_path=vault)
    data = checkpoints.read_checkpoint(OFFICE, "kart-8", vault)
    assert data["summary"] == "ikinci tur"
    assert any("birinci tur" in h for h in data["history"])


def test_entropy_office_checkpoints_live_outside_desk_root(vault):
    """Entropy'nin kendi kartları Desk kökünde sahte bir ofis açmaz."""
    from entropy.core.paths import desk_root

    path = checkpoints.write_checkpoint(
        "entropy", "kart-e1", summary="entropy kartı", author="a", vault_path=vault
    )
    rel = path.relative_to(vault).as_posix()
    assert rel.startswith("Entropy/Board/checkpoints/"), rel
    assert not (desk_root(vault) / "Offices" / "entropy").exists()

    data = checkpoints.read_checkpoint("entropy", "kart-e1", vault)
    assert data and data["summary"] == "entropy kartı"
    assert checkpoints.resume_section("entropy", "kart-e1", vault).startswith("[KALDIĞIN YER]")


def test_resume_section_budget_and_absence(vault):
    assert checkpoints.resume_section(OFFICE, "yok-boyle-kart", vault) == ""
    checkpoints.write_checkpoint(
        OFFICE, "kart-9", summary="x " * 400, next_steps="devam", author="a", vault_path=vault
    )
    text = checkpoints.resume_section(OFFICE, "kart-9", vault)
    assert text.startswith("[KALDIĞIN YER]")
    assert len(text) <= checkpoints.RESUME_MAX_CHARS


def test_parse_checkpoint_block(vault):
    out = checkpoints.parse_checkpoint_block(
        "Bitirdim.\n\n[KONTROL NOKTASI]\n"
        "yapılan: kart deposu ayrıldı\n"
        "sonraki: pano üretimini bağla\n"
        "dosyalar: src/a.py, src/b.py\n"
        "testler: 4 geçti\n"
    )
    assert out["done"] == "kart deposu ayrıldı"
    assert out["next_steps"] == "pano üretimini bağla"
    assert out["files_touched"] == ["src/a.py", "src/b.py"]
    assert out["tests"] == "4 geçti"
    assert out["summary"] == "kart deposu ayrıldı"
    assert checkpoints.parse_checkpoint_block("blok yok") is None
    assert checkpoints.parse_checkpoint_block("[KONTROL NOKTASI]\nrastgele metin") is None


def test_parse_checkpoint_block_feeds_write(vault):
    parsed = checkpoints.parse_checkpoint_block(
        "[KONTROL NOKTASI]\nyapılan: bitti\nsonraki: yok\ndosyalar: a.py\n"
    )
    checkpoints.write_checkpoint(OFFICE, "kart-10", author="alt", vault_path=vault, **parsed)
    assert checkpoints.read_checkpoint(OFFICE, "kart-10", vault)["done"] == "bitti"


@pytest.mark.parametrize(
    "result_line, expected, ok",
    [("sonuç: yeşil", "green", True), ("sonuç: kırmızı", "red", False),
     ("sonuç: 4 passed", "green", True), ("sonuç: belirsiz", "unknown", None)],
)
def test_parse_proof_block_results(result_line, expected, ok):
    out = checkpoints.parse_proof_block(
        f"[KANIT]\nkomut: python -m pytest tests/x.py -q\n{result_line}\nözet: 4 passed\n"
    )
    assert out["result"] == expected
    assert out["ok"] is ok
    assert out["command"].startswith("python -m pytest")


def test_parse_proof_block_missing():
    assert checkpoints.parse_proof_block("hiç kanıt yok") is None
    assert checkpoints.parse_proof_block("[KANIT]\nlorem ipsum") is None


# --------------------------------------------------------------- kurallar


@pytest.mark.parametrize(
    "text",
    [
        "Traceback (most recent call last): dosya okunamadı",
        "ValueError: beklenmeyen değer",
        "ERROR modül yüklenemedi çünkü bağımlılık eksik",
        'File "src/a.py", line 42',
        "C:\\EntropiAI\\src\\entropy dizinini kullan",
        "src/entropy/memory/playbook.py dosyasını güncelle",
        "kısa",
    ],
)
def test_propose_rule_rejects_non_rules(vault, text):
    assert promoted_rules.propose_rule(OFFICE, "kodcu", text, "kart:1", vault) is None
    assert promoted_rules.list_rules(OFFICE, vault_path=vault) == []


def test_propose_rule_dedupes_and_caps(vault):
    first = promoted_rules.propose_rule(OFFICE, "kodcu", "Kartı kapatmadan önce kanıt iste", "k1", vault)
    again = promoted_rules.propose_rule(OFFICE, "başka", "kartı  KAPATMADAN önce kanıt iste.", "k2", vault)
    assert first is not None and again.id == first.id
    assert len(promoted_rules.list_rules(OFFICE, vault_path=vault)) == 1

    long_rule = promoted_rules.propose_rule(OFFICE, "kodcu", "Uzun kural " * 40, "k3", vault)
    assert len(long_rule.text) <= promoted_rules.RULE_MAX_CHARS


def test_promote_and_reject_flow(vault):
    a = promoted_rules.propose_rule(OFFICE, "kodcu", "Her modül sonunda kontrol noktası yaz", "", vault)
    b = promoted_rules.propose_rule(OFFICE, "kodcu", "Kullanıcıya sormadan bağımlılık ekleme", "", vault)
    assert promoted_rules.rules_section(OFFICE, vault_path=vault) == ""  # aday enjekte edilmez

    promoted_rules.promote(OFFICE, a.id, vault)
    promoted_rules.reject(OFFICE, b.id, vault)
    assert [r.id for r in promoted_rules.list_rules(OFFICE, "promoted", vault)] == [a.id]
    assert [r.id for r in promoted_rules.list_rules(OFFICE, "rejected", vault)] == [b.id]

    section = promoted_rules.rules_section(OFFICE, vault_path=vault)
    assert "[ONAYLI KURALLAR]" in section
    assert "Her modül sonunda kontrol noktası yaz" in section
    assert "bağımlılık ekleme" not in section
    assert promoted_rules.promote(OFFICE, "yok", vault) is None


def test_rules_section_scope_and_budget(vault):
    ofis = promoted_rules.propose_rule(OFFICE, "-", "Ofis geneli kural geçerlidir", "", vault)
    ozel = promoted_rules.propose_rule(
        OFFICE, "testçi", "Yalnızca test ajanına ait kural", "", vault, scope="agent:testçi"
    )
    promoted_rules.promote(OFFICE, ofis.id, vault)
    promoted_rules.promote(OFFICE, ozel.id, vault)

    testci = promoted_rules.rules_section(OFFICE, "testçi", vault_path=vault)
    kodcu = promoted_rules.rules_section(OFFICE, "kodcu", vault_path=vault)
    assert "Yalnızca test ajanına ait kural" in testci
    assert "Yalnızca test ajanına ait kural" not in kodcu
    assert "Ofis geneli kural geçerlidir" in kodcu
    assert len(testci) <= promoted_rules.RULES_SECTION_MAX_CHARS

    for i in range(30):
        r = promoted_rules.propose_rule(OFFICE, "-", f"Doldurma kuralı {i} her koşuda uygulanır", "", vault)
        promoted_rules.promote(OFFICE, r.id, vault)
    assert len(promoted_rules.rules_section(OFFICE, vault_path=vault)) <= promoted_rules.RULES_SECTION_MAX_CHARS


def test_rules_md_is_derived_from_json(vault):
    office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    rule = promoted_rules.propose_rule(OFFICE, "kodcu", "Panoyu okumadan işe başlama", "", vault)
    md = office_workspace.workspace_paths(OFFICE, vault)["rules"].read_text(encoding="utf-8")
    assert "Panoyu okumadan işe başlama" in md
    assert "(henüz onaylı kural yok)" in md
    promoted_rules.promote(OFFICE, rule.id, vault)
    md2 = office_workspace.workspace_paths(OFFICE, vault)["rules"].read_text(encoding="utf-8")
    assert "## Onaylı kurallar" in md2
    assert md2.split("## Bekleyen adaylar")[0].count("Panoyu okumadan işe başlama") == 1


def test_parse_rule_candidates_filters():
    lines = promoted_rules.parse_rule_candidates(
        "Rapor.\n"
        "[KURAL] Kartı kapatmadan önce testleri koş\n"
        "- [KURAL] kartı KAPATMADAN önce testleri koş\n"
        "[KURAL] Traceback (most recent call last): patladı\n"
        "[KURAL] src/a.py dosyasını güncelle\n"
        "[KURAL] Kullanıcıya sormadan kalıcı kural yazma\n"
    )
    assert lines == [
        "Kartı kapatmadan önce testleri koş",
        "Kullanıcıya sormadan kalıcı kural yazma",
    ]


def test_rules_path_split_for_entropy_and_office(vault):
    own = promoted_rules.rules_path("entropy", vault)
    office = promoted_rules.rules_path(OFFICE, vault)
    assert own == vault / "Entropy" / "Memory" / "rules.json"
    assert office.parts[-4:] == ("Offices", OFFICE, "memory", "rules.json")


# --------------------------------------------------------------- sistem istemi


def test_system_prompt_injects_promoted_rules(vault, monkeypatch):
    from entropy.memory import system_prompt

    rule = promoted_rules.propose_rule(
        "entropy", "-", "Faz sonunda kullanıcı onayı beklenir", "sohbet", vault
    )
    promoted_rules.promote("entropy", rule.id, vault)

    monkeypatch.setattr(
        system_prompt,
        "promoted_rules_section",
        lambda max_chars=system_prompt.BUDGET_RULES: system_prompt._trim(
            promoted_rules.rules_section("entropy", vault_path=vault, max_chars=max_chars),
            max_chars,
        ),
    )
    monkeypatch.setattr(system_prompt, "cognitive_section", lambda *a, **k: "")
    monkeypatch.setattr(system_prompt, "_desk_rows", lambda: [])

    text = system_prompt.build_system_prompt("chat", provider="claude", query="merhaba")
    assert "[ONAYLI KURALLAR]" in text
    assert "Faz sonunda kullanıcı onayı beklenir" in text
    assert text.index("[ONAYLI KURALLAR]") > text.index("[KİMLİK]")
    assert text.index("[ONAYLI KURALLAR]") < text.index("[ARAÇ SÖZLEŞMESİ]")
    assert len(text) <= system_prompt.DEFAULT_MAX_CHARS


def test_system_prompt_without_rules_has_no_section(vault, monkeypatch):
    from entropy.memory import system_prompt

    monkeypatch.setattr(system_prompt, "promoted_rules_section", lambda max_chars=0: "")
    monkeypatch.setattr(system_prompt, "cognitive_section", lambda *a, **k: "")
    monkeypatch.setattr(system_prompt, "_desk_rows", lambda: [])
    text = system_prompt.build_system_prompt("chat", provider="claude", query="merhaba")
    assert "[ONAYLI KURALLAR]" not in text
