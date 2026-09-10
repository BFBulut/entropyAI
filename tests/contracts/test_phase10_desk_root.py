"""
FAZ 10-B — Desk'in veri kökü kasa köküne taşındı (`Desk/Offices`).

Doğrulanan kurallar:
  1. Eski kökte (`Entropy/Desk/Offices`) ofisi olan bir kasa, Desk defteri ilk
     kurulduğunda yeni köke taşınır: kopyala → doğrula → sil.
  2. Taşıma günlüklenir (`Desk/_migrations.log`) ve eski günlük birleştirilir.
  3. İdempotent: ikinci koşu hiçbir şey taşımaz, günlüğe satır eklemez.
  4. Çakışma (hedefte FARKLI içerik) kaynağa dokunmaz, günlüğe düşer.
  5. Entropy'nin ajan defteri yeni Desk kökünü de dışlar.
  6. Rapor Merkezi ofis raporlarını yeni kökte `office_report` sayar.
  7. Doğuş talimatı ve derlenmiş ofis ajanları "Entropy" dizgesini YOL olarak
     da içermez (Faz 10-A istisnası kalktı).

Hiçbir test gerçek agy/claude süreci başlatmaz.
"""

import pytest

from entropy.agents.desk_registry import DeskOffice, DeskRegistry
from entropy.core import paths as _paths
from entropy.memory import office_workspace


OFFICE = "medya"


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture(autouse=True)
def isolated_vault(vault, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", vault, raising=False)
    (vault / "Entropy").mkdir(parents=True, exist_ok=True)
    # Süreç ömrü boyunca "kasa başına bir kez" işaretini tazele: her test kendi
    # tmp kasasını kullanıyor ama işaret kümesi modül düzeyinde.
    _paths._migrated_vaults.clear()
    yield


def _legacy_office(vault, name=OFFICE, marker="ilk"):
    """Eski kökte küçük ama gerçekçi bir ofis iskeleti kurar."""
    root = vault / "Entropy" / "Desk" / "Offices" / name
    (root / "agents" / "orkestrator").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "cards").mkdir(parents=True, exist_ok=True)
    (root / "OFFICE.md").write_text(
        f"---\nname: {name}\norchestrator: orkestrator\n---\n\n# {name}\n{marker}\n",
        encoding="utf-8",
    )
    (root / "agents" / "orkestrator" / "AGENT.md").write_text(
        "---\nname: orkestrator\nrole: orchestrator\n---\n\n# orkestrator\n",
        encoding="utf-8",
    )
    (root / "reports" / "rapor-1.md").write_text(
        "---\ntype: office_report\n---\n\n# Rapor 1\n", encoding="utf-8"
    )
    return root


# ---------------------------------------------------------------------------
# 1-3. Taşıma, günlük, idempotentlik
# ---------------------------------------------------------------------------


def test_desk_registry_moves_legacy_root_on_open(vault):
    """Kural 1: defter kurulunca eski kökteki ofis yeni köke taşınır."""
    legacy = _legacy_office(vault)
    assert legacy.is_dir()

    desk = DeskRegistry(vault)

    new_root = vault / "Desk" / "Offices" / OFFICE
    assert new_root.is_dir()
    assert (new_root / "OFFICE.md").read_text(encoding="utf-8").endswith("ilk\n")
    assert (new_root / "agents" / "orkestrator" / "AGENT.md").is_file()
    assert (new_root / "reports" / "rapor-1.md").is_file()
    # Kaynak silindi ve eski kök tamamen kalktı.
    assert not legacy.exists()
    assert not (vault / "Entropy" / "Desk").exists()
    # Defter yeni kökü okuyor.
    assert desk.offices_dir == vault / "Desk" / "Offices"
    assert [o.name for o in desk.list()] == [OFFICE]


def test_migration_writes_log_lines_and_merges_old_log(vault):
    """Kural 2: taşıma satırı + eski günlüğün içeriği yeni günlükte."""
    _legacy_office(vault)
    old_log = vault / "Entropy" / "Desk" / "_migrations.log"
    old_log.write_text("2026-01-01T00:00:00\teski-satır\tkart\n", encoding="utf-8")

    result = _paths.migrate_desk_root(vault, dry_run=False)
    assert result["applied"] is True
    assert [m["name"] for m in result["moves"]] == [OFFICE]

    log = (vault / "Desk" / "_migrations.log").read_text(encoding="utf-8")
    assert "eski-satır" in log  # birleştirildi
    assert "desk-kökü\ttaşındı" in log
    assert OFFICE in log
    assert not old_log.exists()


def test_migration_is_idempotent(vault):
    """Kural 3: ikinci koşu ne dosya taşır ne günlüğe satır ekler."""
    _legacy_office(vault)
    _paths.migrate_desk_root(vault, dry_run=False)
    before = (vault / "Desk" / "_migrations.log").read_text(encoding="utf-8")

    second = _paths.migrate_desk_root(vault, dry_run=False)
    assert second["moves"] == []
    assert second["merged"] == []
    assert second["conflicts"] == []
    after = (vault / "Desk" / "_migrations.log").read_text(encoding="utf-8")
    assert after == before


def test_dry_run_touches_nothing_but_counts(vault):
    """Kuru koşum diske yazmaz; sayıları döndürür."""
    legacy = _legacy_office(vault)
    plan = _paths.migrate_desk_root(vault, dry_run=True)

    assert plan["dry_run"] is True and plan["applied"] is False
    assert plan["offices"] == 1
    assert plan["files"] == 3  # OFFICE.md + AGENT.md + rapor-1.md
    assert plan["dirs"] >= 4  # agents, agents/orkestrator, reports, cards
    assert legacy.is_dir()
    assert not (vault / "Desk").exists()


# ---------------------------------------------------------------------------
# 4. Çakışma
# ---------------------------------------------------------------------------


def test_identical_target_deletes_source_but_different_target_is_left_alone(vault):
    """Kural 4: özdeş hedefte kaynak silinir; farklı hedefte hiçbir şey olmaz."""
    _legacy_office(vault, "ozdes", marker="ayni")
    _legacy_office(vault, "farkli", marker="eski")
    # Yeni kökte iki hedef: biri birebir aynı, biri farklı.
    import shutil

    dst_base = vault / "Desk" / "Offices"
    dst_base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        vault / "Entropy" / "Desk" / "Offices" / "ozdes", dst_base / "ozdes"
    )
    (dst_base / "farkli").mkdir()
    (dst_base / "farkli" / "OFFICE.md").write_text("# farkli\nyeni\n", encoding="utf-8")

    result = _paths.migrate_desk_root(vault, dry_run=False)

    assert [m["name"] for m in result["merged"]] == ["ozdes"]
    assert [c["name"] for c in result["conflicts"]] == ["farkli"]
    # Özdeş olanın kaynağı gitti; çakışanın kaynağı DURUYOR.
    legacy_base = vault / "Entropy" / "Desk" / "Offices"
    assert not (legacy_base / "ozdes").exists()
    assert (legacy_base / "farkli" / "OFFICE.md").is_file()
    # Çakışma varken eski kök silinmez (içinde dosya kaldı).
    assert legacy_base.is_dir()

    log = (vault / "Desk" / "_migrations.log").read_text(encoding="utf-8")
    assert "çakışma" in log and "farkli" in log
    assert "kaynak-silindi" in log and "ozdes" in log
    # Hedef içeriği korundu.
    assert "yeni" in (dst_base / "farkli" / "OFFICE.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. Entropy kadrosu Desk kökünü dışlar
# ---------------------------------------------------------------------------


def test_agent_registry_excludes_new_desk_root(vault):
    """Kural 5: `Entropy/Agents` altına Desk kökünü gösteren bir yol sızarsa dışlanır."""
    from entropy.agents.registry import AgentRegistry

    desk = DeskRegistry(vault)
    desk.create(DeskOffice(name=OFFICE, purpose="Medya"))

    agents = AgentRegistry(vault)
    office_agent_dir = vault / "Desk" / "Offices" / OFFICE / "agents" / "orkestrator"
    assert office_agent_dir.is_dir()
    assert agents._is_desk_path(office_agent_dir) is True
    assert agents._is_desk_path(vault / "Entropy" / "Agents" / "yazar") is False
    assert "orkestrator" not in [s.name for s in agents.list()]


# ---------------------------------------------------------------------------
# 6. Rapor Merkezi yeni kökü tarar
# ---------------------------------------------------------------------------


def test_list_reports_finds_office_reports_under_new_root(vault):
    """Kural 6: `Desk/Offices/<ofis>/reports/*.md` -> `office_report`."""
    from entropy.memory.obsidian.vault_manager import ObsidianVaultManager, clear_report_cache

    desk = DeskRegistry(vault)
    desk.create(DeskOffice(name=OFFICE, purpose="Medya"))
    reports = vault / "Desk" / "Offices" / OFFICE / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "Ofis_Raporu.md").write_text("# Ofis Raporu\nGövde\n", encoding="utf-8")

    clear_report_cache()
    vm = ObsidianVaultManager(vault)
    entries = vm.list_reports()
    mine = [e for e in entries if e["title"].startswith("Ofis Raporu")]
    assert mine, f"ofis raporu bulunamadı: {[e['path'] for e in entries]}"
    assert mine[0]["kind"] == "office_report"
    assert mine[0]["office"] == OFFICE


# ---------------------------------------------------------------------------
# 7. Ürün adı yollarda da geçmez
# ---------------------------------------------------------------------------


def test_spawn_instruction_paths_are_free_of_product_name(vault):
    """Kural 7: mutlak yollar da "Entropy" taşımaz — istisna kalktı."""
    office_workspace.ensure_workspace(OFFICE, vault_path=vault)
    text = office_workspace.spawn_instruction(OFFICE, vault_path=vault)
    assert str(vault) in text  # yollar hâlâ MUTLAK
    assert "Desk" in text
    assert "Entropy" not in text


def test_office_data_paths_are_free_of_product_name(vault):
    """Ofis verisinin tüm yolları yeni kökte; Entropy'nin verisi yerinde."""
    from entropy.agents.mailbox import office_mailbox
    from entropy.agents.tasks import TaskBoard
    from entropy.memory import agent_memory, checkpoints, promoted_rules

    desk = DeskRegistry(vault)
    desk.create(DeskOffice(name=OFFICE, purpose="Medya"))
    board = TaskBoard(vault)

    for path in (
        desk.office_dir(OFFICE),
        board.office_cards_dir(OFFICE),
        office_mailbox(OFFICE, vault).inbox_dir,
        office_workspace.workspace_dir(OFFICE, vault),
        checkpoints.checkpoints_dir(OFFICE, vault),
        promoted_rules.rules_path(OFFICE, vault),
        agent_memory.office_memory_path(OFFICE, vault),
    ):
        rel = path.relative_to(vault)
        assert rel.parts[0] == "Desk", f"{path} Desk kökünde değil"

    # Entropy'nin kendi verisi taşınmadı.
    assert agent_memory.agent_dir("yazar", vault).relative_to(vault).parts[0] == "Entropy"
    assert promoted_rules.rules_path("entropy", vault).relative_to(vault).parts[0] == "Entropy"
    assert TaskBoard(vault).tasks_dir == vault / "Entropy" / "Tasks"
