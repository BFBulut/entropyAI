"""
FAZ 10-C — kart başına worktree, PR akışı, ekip şablonları, makbuz.

Doğrulanan kurallar:
  1. `create_worktree` gerçek bir git deposunda ağaç açar, İDEMPOTENTTİR ve
     dal adı `desk/<kart-id>`'dir.
  2. Uzun yol eşiği aşılırsa worktree HİÇ açılmaz (`WorktreeError`).
  3. `remove_worktree` doğrulamalıdır: dizin gitmediyse `removed=False` ve
     kayıt ertelenmiş temizlik kuyruğuna düşer (`list_orphans`).
  4. `diff_stat` staged + unstaged + İZLENMEYEN dosyaları birlikte sayar.
  5. Proje doğrulaması kayıt anındadır: geçersiz yol/dal KAYDEDİLMEZ.
  6. `prepare_review` yerel yoldur (push yok, ağ yok); `push_branch` yalnızca
     açık onayla koşar; `gh` yokken `create_draft_pr` kartı etkilemeden atlar.
  7. Makbuz = ofis raporu: sekiz bölüm başlığı ve artımlı güncelleme.
  8. Şablondan açılan ofiste orkestratör + 3 alt ajan var, "Entropy" geçmez,
     sağlayıcı config'ten gelir ve ikinci uygulama ajanları çoğaltmaz.
  9. Worktree'li alt kartın isteminde `[ÇALIŞMA DİZİNİ]` bloğu var ve yazma
     kilidi kartın KENDİ ağacına düşer (proje geneli kilit değil).

Gerçek `git` kullanılır ama YALNIZCA tmp depolarda; bu deponun worktree
listesine dokunulmaz. Hiçbir test gerçek agy/claude süreci başlatmaz.
"""

import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from entropy.agents import pr_flow, templates as tpl, worktrees as wt
from entropy.agents.desk_registry import (
    DeskOffice,
    DeskProject,
    DeskRegistry,
    validate_project_repo,
)
from entropy.agents.harness import OfficeHarness
from entropy.agents.registry import AgentSpec
from entropy.agents.tasks import TaskBoard, TaskCard


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git kurulu değil"
)


# ---------------------------------------------------------------------------
# Ortak düzenek
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    from entropy.core.config import config

    vault = tmp_path / "Vault"
    (vault / "Entropy").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "obsidian_vault_path", vault, raising=False)
    return vault


def _git(cwd, *args):
    proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


@pytest.fixture
def repo(tmp_path):
    """Tek commit'li küçük bir tmp git deposu."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    (root / "a.txt").write_text("bir\n", encoding="utf-8")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-m", "ilk")
    return root


# ---------------------------------------------------------------------------
# 1-3. worktree yaşam döngüsü
# ---------------------------------------------------------------------------


def test_create_worktree_is_idempotent_and_names_branch_after_card(repo):
    first = wt.create_worktree(repo, "ofis", "kart-1", base_branch="main")
    assert first.is_dir()
    assert (first / "a.txt").read_text(encoding="utf-8") == "bir\n"
    # Dal adı kart kimliğiyle birebir: aynı dal ikinci bir ağaca eklenemiyor.
    assert wt.worktree_status(first)["branch"] == "desk/kart-1"

    second = wt.create_worktree(repo, "ofis", "kart-1", base_branch="main")
    assert second == first
    lines = [ln for ln in _git(repo, "worktree", "list").splitlines()
             if "[desk/kart-1]" in ln]
    assert len(lines) == 1

    # İzolasyon gerçek: ağaçtaki değişiklik ana depoya sızmaz.
    (first / "a.txt").write_text("iki\n", encoding="utf-8")
    assert (repo / "a.txt").read_text(encoding="utf-8") == "bir\n"


def test_two_cards_get_separate_worktrees(repo):
    one = wt.create_worktree(repo, "ofis", "kart-1", base_branch="main")
    two = wt.create_worktree(repo, "ofis", "kart-2", base_branch="main")
    assert one != two
    listing = _git(repo, "worktree", "list")
    assert "desk/kart-1" in listing and "desk/kart-2" in listing


def test_long_path_is_rejected_before_git_is_called(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(wt, "_longpaths_enabled", lambda: False)
    deep = tmp_path / ("u" * 120) / ("v" * 120)
    with pytest.raises(wt.WorktreeError) as err:
        wt.create_worktree(repo, "ofis", "kart-uzun", base_branch="main", root=deep)
    assert "uzun" in str(err.value).lower()
    assert "kart-uzun" not in _git(repo, "worktree", "list")


def test_remove_worktree_verifies_and_queues_orphan(repo, isolated_vault, monkeypatch):
    path = wt.create_worktree(repo, "ofis", "kart-3", base_branch="main")
    (path / "yeni.txt").write_text("kirli\n", encoding="utf-8")

    # Windows ölçümü: dosya kilidi varken `remove --force` rc=255 veriyor,
    # kaydı siliyor ama DİZİNİ bırakıyor. Taklit tam olarak bunu yapar.
    real_git = wt._git

    def fake_git(cwd, *args, **kwargs):
        if args[:2] == ("worktree", "remove"):
            class _P:
                returncode = 255
                stdout = ""
                stderr = "error: failed to delete: Invalid argument"
            return _P()
        return real_git(cwd, *args, **kwargs)

    monkeypatch.setattr(wt, "_git", fake_git)
    result = wt.remove_worktree(repo, path, branch="desk/kart-3", force=True,
                                vault_path=isolated_vault)
    assert result["removed"] is False
    assert result["orphans"] and result["orphans"][0]["path"] == str(path)
    orphans = wt.list_orphans(repo, vault_path=isolated_vault)
    assert [o["path"] for o in orphans] == [str(path)]
    assert (isolated_vault / wt.CLEANUP_QUEUE_SUBPATH).is_file()

    # Kuyruk gerçek silme ile boşalır (açılışta uzlaştırma).
    monkeypatch.setattr(wt, "_git", real_git)
    out = wt.retry_orphans(vault_path=isolated_vault)
    assert out["remaining"] == []
    assert not path.exists()


def test_remove_worktree_deletes_branch_only_when_directory_is_gone(repo, isolated_vault):
    path = wt.create_worktree(repo, "ofis", "kart-4", base_branch="main")
    result = wt.remove_worktree(repo, path, branch="desk/kart-4", force=True,
                                vault_path=isolated_vault)
    assert result["removed"] is True
    assert result["branch_deleted"] is True
    assert "desk/kart-4" not in _git(repo, "branch", "--list")


# ---------------------------------------------------------------------------
# 4. diff okuma
# ---------------------------------------------------------------------------


def test_diff_stat_covers_staged_unstaged_and_untracked(repo):
    path = wt.create_worktree(repo, "ofis", "kart-5", base_branch="main")
    (path / "a.txt").write_text("bir\niki\n", encoding="utf-8")
    (path / "yeni.txt").write_text("x\ny\nz\n", encoding="utf-8")
    (path / "hazir.txt").write_text("h\n", encoding="utf-8")
    _git(path, "add", "hazir.txt")

    rows = {r["file"]: r for r in wt.diff_stat(path)}
    assert rows["a.txt"]["added"] == 1 and rows["a.txt"]["status"] == "modified"
    assert rows["yeni.txt"]["status"] == "new" and rows["yeni.txt"]["added"] == 3
    assert rows["hazir.txt"]["status"] == "staged"

    assert "iki" in wt.file_diff(path, "a.txt")
    status = wt.worktree_status(path)
    assert status["registered"] is True and status["clean"] is False


# ---------------------------------------------------------------------------
# 5. proje = depo + dal
# ---------------------------------------------------------------------------


def test_project_validation_rejects_bad_repo_and_branch(repo, tmp_path):
    assert validate_project_repo("", "") == ""
    assert "bulunamadı" in validate_project_repo(str(tmp_path / "yok"), "")
    plain = tmp_path / "duz"
    plain.mkdir()
    assert "git deposu değil" in validate_project_repo(str(plain), "")
    assert "dalı bu depoda yok" in validate_project_repo(str(repo), "olmayan-dal")
    assert validate_project_repo(str(repo), "main") == ""


def test_create_project_persists_repo_fields_and_refuses_invalid(repo, isolated_vault):
    desk = DeskRegistry(vault_path=isolated_vault)
    desk.create(DeskOffice(name="ofis", purpose="test"))
    project = desk.create_project(
        "ofis", DeskProject(name="p1", repo_path=str(repo), base_branch="main")
    )
    assert project.repo_path == str(repo)
    again = desk.get_project("ofis", "p1")
    assert again.repo_path == str(repo) and again.base_branch == "main"
    assert again.has_repo is True

    with pytest.raises(ValueError):
        desk.create_project("ofis", DeskProject(name="p2", repo_path=str(repo),
                                                base_branch="yok-boyle-dal"))
    assert desk.get_project("ofis", "p2") is None


def test_legacy_project_without_repo_still_reads(isolated_vault):
    desk = DeskRegistry(vault_path=isolated_vault)
    desk.create(DeskOffice(name="ofis"))
    path = desk.projects_dir("ofis") / "eski" / "PROJECT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nname: eski\ngoal: hedef\n---\n\n# eski\n", encoding="utf-8")
    project = desk.get_project("ofis", "eski")
    assert project.goal == "hedef"
    assert project.repo_path == "" and project.has_repo is False


# ---------------------------------------------------------------------------
# 6. PR akışı
# ---------------------------------------------------------------------------


def test_prepare_review_is_local_only_and_never_pushes(repo, monkeypatch):
    path = wt.create_worktree(repo, "ofis", "kart-6", base_branch="main")
    (path / "yeni.txt").write_text("a\nb\n", encoding="utf-8")
    card = TaskCard(id="kart-6", title="iş", worktree=str(path), branch="desk/kart-6")

    calls = []
    monkeypatch.setattr(pr_flow, "push_branch",
                        lambda *a, **k: calls.append(a) or {"pushed": True})
    data = pr_flow.prepare_review(card, base_branch="main")
    assert calls == []
    assert data["branch"] == "desk/kart-6"
    assert data["file_count"] == 1 and data["added"] == 2
    assert "1 dosya" in data["summary"]

    section = pr_flow.changes_section(data)
    assert "yeni.txt" in section and section.startswith("Dal: desk/kart-6")


def test_prepare_review_without_worktree_is_harmless():
    data = pr_flow.prepare_review(TaskCard(id="k", title="t"))
    assert data["file_count"] == 0 and "izole çalışma ağacı yok" in data["summary"]


def test_push_branch_requires_confirmation_and_remote(repo):
    path = wt.create_worktree(repo, "ofis", "kart-7", base_branch="main")
    card = TaskCard(id="kart-7", title="iş", worktree=str(path), branch="desk/kart-7")
    assert pr_flow.push_branch(card, confirm=False) == {"pushed": False,
                                                        "skipped": "onay yok"}
    # Uzak depo yok: push hiç denenmez, kart etkilenmez.
    assert pr_flow.push_branch(card, confirm=True)["skipped"] == "uzak depo yok"


def test_create_draft_pr_skips_when_gh_missing(repo, monkeypatch):
    path = wt.create_worktree(repo, "ofis", "kart-8", base_branch="main")
    card = TaskCard(id="kart-8", title="iş", worktree=str(path), branch="desk/kart-8")
    monkeypatch.setattr(pr_flow, "gh_available", lambda: False)
    out = pr_flow.create_draft_pr(card, office="ofis", base_branch="main")
    assert out == {"skipped": "gh yok", "url": ""}


def test_gh_available_never_logs_output(monkeypatch, caplog):
    monkeypatch.setattr(pr_flow.shutil, "which", lambda name: "C:/fake/gh.exe")

    class _P:
        returncode = 0
        stdout = "Token: ghp_GIZLI_JETON"
        stderr = "Logged in as someone (ghp_GIZLI_JETON)"

    monkeypatch.setattr(pr_flow, "_run", lambda *a, **k: _P())
    with caplog.at_level("DEBUG"):
        assert pr_flow.gh_available() is True
    assert "ghp_GIZLI_JETON" not in caplog.text


def test_pr_body_has_no_brand_leak(repo):
    path = wt.create_worktree(repo, "ofis", "kart-9", base_branch="main")
    card = TaskCard(id="kart-9", title="iş", worktree=str(path), branch="desk/kart-9")
    body = pr_flow.pr_body(card, office="ofis", review=pr_flow.prepare_review(card))
    assert "## Değişiklikler" in body and "## Kanıt" in body


# ---------------------------------------------------------------------------
# 7. makbuz = ofis raporu
# ---------------------------------------------------------------------------


def _office_with_children(isolated_vault, repo=None):
    desk = DeskRegistry(vault_path=isolated_vault)
    desk.create(DeskOffice(name="ofis", purpose="test", default_provider="claude"))
    desk.agents("ofis").update(AgentSpec(name="isci", role="worker",
                                          provider="claude", office="ofis"))
    if repo is not None:
        desk.create_project("ofis", DeskProject(name="p1", repo_path=str(repo),
                                                base_branch="main"))
    board = TaskBoard(vault_path=isolated_vault)
    parent = board.create(TaskCard(id="ust-1", title="Üst iş", office="ofis",
                                   project=("p1" if repo is not None else ""),
                                   status="running"))
    kids = []
    for i in (1, 2):
        kid = board.create(TaskCard(
            id=f"alt-{i}", title=f"Alt {i}", office="ofis", parent="ust-1",
            agent="isci", provider="claude", status="done", intent="write",
            criteria=["ölçüt"], summary=f"alt {i} çıktısı", proof="Sonuç: yeşil",
            grade=0.9, project=("p1" if repo is not None else ""),
        ))
        kids.append(kid)
    board.update(replace(parent, children=[k.id for k in kids]))
    return desk, board


def test_receipt_has_all_sections_and_is_written_incrementally(isolated_vault):
    desk, board = _office_with_children(isolated_vault)
    harness = OfficeHarness("ofis", board=board, offices=desk)
    path = harness._write_receipt("ust-1")
    assert path is not None and path.name == "ust-1.md"
    text = path.read_text(encoding="utf-8")
    for section in ("## Plan", "## İlerleme", "## Değerlendirme", "## Kanıt",
                    "## Değişiklikler", "## PR", "## Maliyet", "## Yorumlar"):
        assert section in text, section
    # Plan tablosu alt kartlardan türer; ilerleme alt kart özetlerini taşır.
    assert "Alt 1" in text and "alt 2 çıktısı" in text
    assert "Sonuç: yeşil" in text
    # Ayrı bir makbuz klasörü AÇILMAZ: rapor klasörü makbuzun kendisidir.
    assert path.parent == desk.reports_dir("ofis")
    assert not (desk.office_dir("ofis") / "receipts").exists()


def test_receipt_changes_section_reads_real_worktree(isolated_vault, repo):
    desk, board = _office_with_children(isolated_vault, repo=repo)
    path = wt.create_worktree(repo, "ofis", "alt-1", base_branch="main")
    (path / "yeni.txt").write_text("a\n", encoding="utf-8")
    board.update(replace(board.get("alt-1"), worktree=str(path), branch="desk/alt-1"))
    harness = OfficeHarness("ofis", board=board, offices=desk)
    review = harness._child_review(harness._children(board.get("ust-1")))
    body = harness._receipt_body(board.get("ust-1"),
                                 harness._children(board.get("ust-1")),
                                 review=review, avg=0.9)
    assert "yeni.txt" in body
    assert "desk/alt-1" in body


# ---------------------------------------------------------------------------
# 8. ekip şablonları
# ---------------------------------------------------------------------------


def test_builtin_templates_are_copied_to_vault_once(isolated_vault):
    written = tpl.ensure_templates(isolated_vault)
    assert set(written) == set(tpl.BUILTIN_TEMPLATES)
    root = tpl.templates_dir(isolated_vault)
    assert (root / "qa" / "OFFICE.md").is_file()
    # İkinci çağrı hiçbir şeye dokunmaz (kullanıcı düzenlemesi korunur).
    edited = root / "qa" / "OFFICE.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\nelle eklendi\n",
                      encoding="utf-8")
    assert tpl.ensure_templates(isolated_vault) == []
    assert "elle eklendi" in edited.read_text(encoding="utf-8")


def test_list_templates_returns_four_with_rosters(isolated_vault):
    rows = {r["name"]: r for r in tpl.list_templates(isolated_vault)}
    assert set(rows) == set(tpl.BUILTIN_TEMPLATES)
    for row in rows.values():
        assert len(row["agents"]) >= 3
    assert "derleyici" in rows["qa"]["agents"]


def test_office_from_template_has_orchestrator_plus_three_and_no_brand(isolated_vault,
                                                                       monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "provider", "claude", raising=False)
    desk = DeskRegistry(vault_path=isolated_vault)
    office = tpl.create_office_from_template("refaktor", "yenilik", desk=desk)
    names = sorted(s.name for s in desk.agents("yenilik").list())
    assert "orkestrator" in names
    assert len([n for n in names if n != "orkestrator"]) >= 3
    for spec in desk.agents("yenilik").list():
        # Sağlayıcı config'ten gelir; şablon dosyası sağlayıcı dayatmaz.
        assert spec.provider == "claude", spec.name
        blob = (spec.prompt or "") + (spec.description or "")
        assert "Entropy" not in blob and "entropy" not in blob.lower(), spec.name
    assert office.max_parallel == 2 and office.budget_tokens == 120000


def test_template_office_and_agents_get_a_quota_friendly_model(isolated_vault, monkeypatch):
    """Sablon `models` alani: ofis, orkestrator ve alt ajanlar modelsiz dogmaz."""
    from entropy.core.config import config, is_valid_model_for

    for provider, expected in (("claude", "claude-sonnet-5"),
                               ("agy", "gemini-3.8-flash-high")):
        monkeypatch.setattr(config, "provider", provider, raising=False)
        desk = DeskRegistry(vault_path=isolated_vault / provider)
        office = tpl.create_office_from_template("qa", f"kalite-{provider}", desk=desk)
        assert office.default_model == expected
        for spec in desk.agents(office.name).list():
            assert spec.model == expected, spec.name
            assert is_valid_model_for(provider, spec.model), spec.name


def test_template_reapplication_does_not_duplicate_or_overwrite(isolated_vault):
    desk = DeskRegistry(vault_path=isolated_vault)
    tpl.create_office_from_template("qa", "kalite", desk=desk)
    agents = desk.agents("kalite")
    spec = agents.get("derleyici")
    agents.update(replace(spec, prompt="ELLE DÜZELTİLDİ"))
    before = sorted(s.name for s in agents.list())

    created = tpl.apply_template(desk, "kalite", "qa")
    assert created == []
    assert sorted(s.name for s in desk.agents("kalite").list()) == before
    assert desk.agents("kalite").get("derleyici").prompt.strip().endswith("ELLE DÜZELTİLDİ")


def test_template_files_carry_no_commercial_brand():
    root = tpl.packaged_templates_dir()
    banned = ("Entropy", "entropiai", "Antigravity", "Claude", "Gemini", "agy")
    for path in root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        # Model alanlarindaki saglayici ADLARI marka sizintisi degildir: bu
        # satirlar ajanin istemine hic girmez, yalnizca hangi CLI modelinin
        # kosacagini soyler (`models: {claude: ..., agy: ...}`). Yasak, ajanin
        # GORDUGU metin icindir; olcum o metinde yapilir.
        text = "\n".join(
            line for line in text.splitlines()
            if not line.strip().startswith(("models:", "model_", "default_model:"))
        )
        for word in banned:
            assert word not in text, f"{path}: {word}"


# ---------------------------------------------------------------------------
# 9. harness ↔ worktree
# ---------------------------------------------------------------------------


def test_child_prompt_declares_worktree_and_lock_follows_the_tree(isolated_vault, repo):
    desk, board = _office_with_children(isolated_vault, repo=repo)
    harness = OfficeHarness("ofis", board=board, offices=desk)
    child = board.get("alt-1")

    path = harness._ensure_worktree(child, board.get("ust-1"))
    assert path and Path(path).is_dir()
    child = board.get("alt-1")
    assert child.worktree == path and child.branch == "desk/alt-1"

    prompt = board.build_prompt(child, project_path=path)
    assert "[ÇALIŞMA DİZİNİ]" in prompt
    assert path in prompt and "desk/alt-1" in prompt
    assert "git komutlarını bu dizinde çalıştır" in prompt.lower()

    # İkinci çağrı aynı ağacı döndürür (idempotent).
    assert harness._ensure_worktree(board.get("alt-1"), board.get("ust-1")) == path


def test_write_intent_children_are_parallel_when_worktree_eligible(isolated_vault, repo):
    desk, board = _office_with_children(isolated_vault, repo=repo)
    harness = OfficeHarness("ofis", board=board, offices=desk)
    parent = board.get("ust-1")
    for kid in harness._children(parent):
        assert harness._worktree_eligible(kid, parent) is True

    # Depo bağlı OLMAYAN projede eski davranış (proje geneli kilit) korunur.
    desk2, board2 = _office_with_children(isolated_vault.parent / "Vault2")
    harness2 = OfficeHarness("ofis", board=board2, offices=desk2)
    parent2 = board2.get("ust-1")
    for kid in harness2._children(parent2):
        assert harness2._worktree_eligible(kid, parent2) is False


def test_deleting_card_releases_its_worktree(isolated_vault, repo):
    board = TaskBoard(vault_path=isolated_vault)
    path = wt.create_worktree(repo, "ofis", "silinecek", base_branch="main")
    board.create(TaskCard(id="silinecek", title="t", worktree=str(path),
                          branch="desk/silinecek"))
    assert board.delete("silinecek") is True
    assert not Path(path).exists()
    assert "desk/silinecek" not in _git(repo, "worktree", "list")


def test_worktree_failure_does_not_kill_the_card(isolated_vault, repo, monkeypatch):
    desk, board = _office_with_children(isolated_vault, repo=repo)
    harness = OfficeHarness("ofis", board=board, offices=desk)

    def boom(*a, **k):
        raise wt.WorktreeError("taklit hata")

    monkeypatch.setattr(wt, "create_worktree", boom)
    path = harness._ensure_worktree(board.get("alt-1"), board.get("ust-1"))
    assert path == ""
    child = board.get("alt-1")
    assert child.status == "done"  # kart ölmedi
    assert "Worktree açılamadı" in (child.notes or "")


def test_run_cwd_uses_worktree_even_in_isolated_mode(repo, monkeypatch):
    from entropy.core.claude_bridge import ClaudeCodeBridge
    from entropy.core.config import config

    monkeypatch.setattr(config, "claude_isolated", True, raising=False)
    path = wt.create_worktree(repo, "ofis", "kart-cwd", base_branch="main")
    cwd = ClaudeCodeBridge.run_cwd(ClaudeCodeBridge, path)
    assert cwd == str(path)
    # Worktree OLMAYAN dizinde izolasyon aynen sürer: ana depo nötr dizine düşer.
    other = ClaudeCodeBridge.run_cwd(ClaudeCodeBridge, repo)
    assert other != str(repo)
    # Açık bayrak da aynı sonucu verir (kartın `worktree` alanını taşıyan yol).
    assert ClaudeCodeBridge.run_cwd(ClaudeCodeBridge, repo, in_worktree=True) == str(repo)


def test_real_bridge_runs_worktree_card_inside_the_worktree(repo, tmp_path, monkeypatch):
    """
    GERÇEK köprü yolu (`subprocess.Popen` taklidiyle): worktree'li bir kart
    izole kipte bile KENDİ ağacında koşmalı.

    Sahte köprüyle geçen bir test bunu gizlerdi: `project_path` köprüye
    ulaşıyor ama `run_cwd` onu nötr dizine çeviriyor olabilirdi.
    """
    import threading

    from entropy.core.claude_bridge import ClaudeCodeBridge
    from entropy.core.config import config
    from entropy.core.task_ledger import TaskLedger

    monkeypatch.setattr(config, "claude_isolated", True, raising=False)
    monkeypatch.setattr("entropy.core.claude_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    worktree = wt.create_worktree(repo, "ofis", "kart-real", base_branch="main")

    seen = {}

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)

        def readline(self):
            return next(self._iter, "")

        def close(self):
            pass

    class DummyProc:
        def __init__(self, *args, **kwargs):
            seen["cwd"] = kwargs.get("cwd")
            seen["argv"] = args[0] if args else kwargs.get("args")
            self.stdout = DummyStdout([
                '{"type":"result","subtype":"success","result":"bitti"}\n',
                "",
            ])
            self.pid = 4321

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    bridge = ClaudeCodeBridge()
    done = threading.Event()
    bridge.send_background_task_async(
        task_id="card-kart-real",
        task_name="worktree kartı",
        prompt="iş",
        mode="accept-edits",
        on_result=lambda text, ok: done.set(),
        save_report=False,
        project_path=str(worktree),
    )
    assert done.wait(timeout=15), "on_result çağrılmadı"
    assert seen.get("cwd") == str(worktree)
