"""
Faz 10-C arayüz testleri: değişiklik/diff bölmesi, makbuz görünümü, proje =
depo formu, ekip şablonu kutusu ve benzerlik eşiği kalibrasyonu.

Model çağrısı, uzak depoya yazma ve gerçek kasaya yazma YOKTUR:
  * diff için `tmp_path` altında GERÇEK bir git deposu kurulur,
  * `push_branch` / `create_draft_pr` sahte modüllerle gözlenir,
  * makbuz dosyası tmp kasaya yazılır, yorum `instruct_office` yamalanır.

Ekran görüntüleri `scratch/ui/phase10/` altına düşer.
"""

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from entropy.desk import changes_panel as cp
from entropy.desk.changes_panel import ChangesPanel, DiffHighlighter, truncate_diff
from entropy.desk.offices_panel import OfficeEditDialog, TEMPLATE_NONE
from entropy.desk.projects_panel import (
    ProjectEditDialog, default_worktree_root, git_branches, validate_project_form,
)
from entropy.desk.receipt import (
    RECEIPT_SECTIONS, is_receipt, parse_receipt, receipt_html, receipt_summary,
)
from entropy.desk.receipt_panel import ReceiptPanel
from entropy.ui.widgets import knowledge_graph as kg

SHOT_DIR = Path(__file__).resolve().parent.parent / "scratch" / "ui" / "phase10"


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    return app


def shoot(widget, name: str) -> Path:
    widget.resize(max(widget.width(), 760), max(widget.height(), 440))
    widget.show()
    QApplication.processEvents()
    path = SHOT_DIR / f"{name}.png"
    widget.grab().save(str(path))
    return path


class FakeCard:
    """Kart sözleşmesinin test yüzeyi (worktree / branch / pr_url alanları)."""

    def __init__(self, **fields):
        for key, value in fields.items():
            setattr(self, key, value)


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    """Gerçek (fakat izole) git deposu: bir dosya değiştirilmiş halde bırakılır."""
    if not __import__("shutil").which("git"):
        pytest.skip("git kurulu değil")
    path = tmp_path_factory.mktemp("wt_repo")
    git("init", "-b", "main", cwd=path)
    git("config", "user.email", "test@example.com", cwd=path)
    git("config", "user.name", "Test", cwd=path)
    (path / "alpha.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (path / "notes.md").write_text("# not\n", encoding="utf-8")
    git("add", ".", cwd=path)
    git("commit", "-m", "ilk", cwd=path)
    git("checkout", "-b", "is/faz10", cwd=path)
    (path / "alpha.py").write_text("def a():\n    return 2\n\ndef b():\n    return 3\n",
                                   encoding="utf-8")
    (path / "yeni.txt").write_text("yeni satır\n", encoding="utf-8")
    git("add", ".", cwd=path)
    return path


# --------------------------------------------------------------- diff bölmesi


def real_diff_stat(path):
    """Testlik `worktrees.diff_stat`: `git diff --numstat --cached`."""
    proc = git("diff", "--numstat", "--cached", cwd=path)
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, name = parts
        rows.append({
            "file": name,
            "added": int(added) if added.isdigit() else 0,
            "deleted": int(deleted) if deleted.isdigit() else 0,
            "status": "M" if deleted != "0" or added != "0" else "?",
        })
    return rows


def real_file_diff(path, file_name):
    return git("diff", "--cached", "--", file_name, cwd=path).stdout


@pytest.fixture
def worktrees_module(monkeypatch):
    mod = types.ModuleType("entropy.agents.worktrees")
    mod.diff_stat = real_diff_stat
    mod.file_diff = real_file_diff
    mod.worktree_status = lambda path: {"clean": False}
    monkeypatch.setitem(sys.modules, "entropy.agents.worktrees", mod)
    return mod


def test_changes_panel_lists_files_and_highlights_diff(repo, worktrees_module):
    """Değişen dosyalar +/− ile listelenir; diff tembel yüklenir ve renklenir."""
    card = FakeCard(id="k-1", title="Diff kartı", worktree=str(repo), branch="is/faz10")
    panel = ChangesPanel(card=card)

    names = panel.file_names()
    assert "alpha.py" in names and "yeni.txt" in names
    assert "+" in panel.status_label.text() and str(len(names)) in panel.status_label.text()
    # Tembel: liste kurulurken gövde okunmaz.
    assert panel.diff_text() == ""

    text = panel.show_file("alpha.py")
    assert "def b" in text and text.lstrip().startswith("diff")

    hl = panel.highlighter
    assert hl.kind_for("+    return 2") == "add"
    assert hl.kind_for("-    return 1") == "del"
    assert hl.kind_for("@@ -1,2 +1,5 @@") == "hunk"
    assert hl.kind_for("--- a/alpha.py") == "meta"

    shoot(panel, "diff_panel")
    panel.close()


def test_diff_truncated_above_limit():
    """200 KB üstü fark kesilir ve kesildiği açıkça yazılır."""
    big = "\n".join(f"+satir {i}" for i in range(60_000))
    out = truncate_diff(big)
    assert len(out.encode("utf-8")) < len(big.encode("utf-8"))
    assert "kesildi" in out


def test_panel_without_worktree_explains(worktrees_module):
    """Worktree'siz kartta liste boş ve açıklayıcı satır görünür."""
    panel = ChangesPanel(card=FakeCard(id="k-2", title="Worktree yok"))
    assert "worktree kullanmıyor" in panel.status_label.text()
    assert panel.file_names() == []
    panel.close()


def test_push_requires_confirmation(monkeypatch, repo, worktrees_module):
    """Onay verilmeden `push_branch` sözleşmesi HİÇ çağrılmaz."""
    calls = []
    mod = types.ModuleType("entropy.agents.pr_flow")
    mod.gh_available = lambda: True
    mod.push_branch = lambda card, confirm=True: (calls.append(confirm), {"ok": True})[1]
    mod.create_draft_pr = lambda card: {"url": "https://example.invalid/pr/1"}
    mod.prepare_review = lambda card: {}
    monkeypatch.setitem(sys.modules, "entropy.agents.pr_flow", mod)

    card = FakeCard(id="k-3", title="Push", worktree=str(repo), branch="is/faz10")
    panel = ChangesPanel(card=card, confirm=False)

    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    result = panel.push_branch(confirm=True)      # kullanıcı vazgeçti
    assert calls == [] and result["ok"] is False

    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    result = panel.push_branch(confirm=True)      # kullanıcı onayladı
    assert calls == [True] and result["ok"] is True

    pr = panel.create_draft_pr()
    assert pr["url"].endswith("/pr/1")
    assert panel.pr_btn.isEnabled()
    panel.close()


# --------------------------------------------------------------- makbuz

RECEIPT_TEXT = """# Kart k-9

## Plan
| Adım | Sahip |
| --- | --- |
| Diff bölmesi | kodcu |

## İlerleme
- diff listesi bitti

## Değerlendirme
Not: iyi

## Kanıt
`pytest tests/test_ui_phase10_diff_receipt_templates.py` — 9 geçti

## Değişiklikler
- alpha.py +4 −1
- yeni.txt +1 −0

## PR
https://example.invalid/pr/7

## Maliyet
12.400 token

## Yorumlar
- kullanıcı: ekran görüntüsü ekle
"""


def test_receipt_parsing_and_summary():
    sections = parse_receipt(RECEIPT_TEXT)
    assert all(name in sections for name in RECEIPT_SECTIONS)
    assert is_receipt(RECEIPT_TEXT) and not is_receipt("# Sıradan rapor\n\nmetin")
    summary = receipt_summary(sections)
    assert summary["has_proof"] and summary["change_count"] == 2
    assert summary["pr_url"] == "https://example.invalid/pr/7"
    html = receipt_html(sections)
    assert "Maliyet" in html and "example.invalid/pr/7" in html


def test_receipt_panel_sections_and_comment(monkeypatch, tmp_path):
    """Makbuz bölümleri çizilir; yorum `instruct_office(task_id=kart)` çağırır."""
    office = "ofis-a"
    reports = tmp_path / "Desk" / "Offices" / office / "reports"
    reports.mkdir(parents=True)
    (reports / "k-9.md").write_text(RECEIPT_TEXT, encoding="utf-8")

    calls = []
    mailbox = types.ModuleType("entropy.agents.mailbox")
    mailbox.instruct_office = lambda office, text, task_id="": calls.append(
        (office, text, task_id))
    monkeypatch.setitem(sys.modules, "entropy.agents.mailbox", mailbox)

    card = FakeCard(id="k-9", title="Makbuz kartı")
    panel = ReceiptPanel(office=office, card=card, vault_path=tmp_path)

    titles = panel.section_titles()
    for name in RECEIPT_SECTIONS:
        assert name in titles
    assert "Diff bölmesi" in panel.section_text("Plan")
    assert "kanıt var" in panel.header_label.text()

    panel.comment_input.setText("kanıt bölümüne komut çıktısını ekle")
    assert panel.send_comment() is True
    assert calls == [(office, "kanıt bölümüne komut çıktısını ekle", "k-9")]
    assert panel.comment_input.text() == ""

    shoot(panel, "receipt_view")
    panel.close()


def test_receipt_panel_without_report(tmp_path):
    panel = ReceiptPanel(office="bos-ofis", card=FakeCard(id="yok", title="X"),
                         vault_path=tmp_path)
    assert panel.section_titles() == []
    assert "bulunamadı" in panel.header_label.text()
    panel.close()


def test_reports_viewer_adds_read_only_receipt_view():
    """Zen okuyucu: makbuz raporunda bölümlü özet başa eklenir, yorum yok."""
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    html = ReportsViewerWidget._with_receipt_view(None, RECEIPT_TEXT)
    assert "Kanıt" in html and "Maliyet" in html
    assert "Yorum ekle" not in html
    assert ReportsViewerWidget._with_receipt_view(None, "# duz rapor") == ""


# --------------------------------------------------------------- proje formu


def test_project_form_validation_and_branches(repo):
    """Depo yolu/dal doğrulaması: geçersizde kırmızı ipucu + kaydet pasif."""
    dialog = ProjectEditDialog(office="ofis-a")
    assert dialog.save_btn.isEnabled() is False        # ad boş

    dialog.name_input.setText("faz10")
    assert dialog.save_btn.isEnabled() is True
    assert dialog.hint_label.isVisible() is False

    dialog.repo_input.setText(str(repo / "yok-boyle-klasor"))
    assert dialog.save_btn.isEnabled() is False
    assert "bulunamadı" in dialog.hint_label.text()

    dialog.repo_input.setText(str(repo))
    QApplication.processEvents()
    branches = git_branches(str(repo))
    assert "main" in branches and "is/faz10" in branches
    assert dialog.branch_combo.currentText() in branches
    assert dialog.save_btn.isEnabled() is True

    dialog.branch_combo.setCurrentText("olmayan-dal")
    assert dialog.save_btn.isEnabled() is False
    assert "olmayan-dal" in dialog.hint_label.text()

    dialog.branch_combo.setCurrentText("main")
    data = dialog.get_data()
    assert data["repo_path"] == str(repo) and data["base_branch"] == "main"
    assert data["worktree_root"] == default_worktree_root(str(repo))
    assert data["worktree_root"].endswith(".entropy-worktrees")

    shoot(dialog, "project_form")
    dialog.close()


def test_validate_project_form_rules(tmp_path):
    assert validate_project_form({"name": ""}) != ""
    assert validate_project_form({"name": "p"}) == ""
    plain = tmp_path / "duz"
    plain.mkdir()
    assert "git deposu değil" in validate_project_form(
        {"name": "p", "repo_path": str(plain)})
    assert validate_project_form({"name": "p", "base_branch": "main"}) != ""


# --------------------------------------------------------------- şablon


def test_office_dialog_template_combo(monkeypatch):
    """Şablon kutusu listelenir, kadro önizlenir, "Boş" varsayılandır."""
    mod = types.ModuleType("entropy.agents.templates")
    mod.list_templates = lambda: [
        {"name": "arastirma-ekibi", "description": "Araştırma + yazım",
         "agents": ["orkestrator", "arastirmaci", "yazar"]},
    ]
    created = []
    mod.create_office_from_template = lambda template, office_name, provider=None: (
        created.append((template, office_name, provider)))
    monkeypatch.setitem(sys.modules, "entropy.agents.templates", mod)

    dialog = OfficeEditDialog()
    assert dialog.template_combo.currentText() == TEMPLATE_NONE
    assert dialog.selected_template() == ""
    assert dialog.template_combo.findText("arastirma-ekibi") > 0

    dialog.template_combo.setCurrentText("arastirma-ekibi")
    assert "arastirmaci" in dialog.template_preview.text()
    dialog.name_edit.setText("yeni-ofis")
    assert dialog.get_data()["template"] == "arastirma-ekibi"

    shoot(dialog, "office_template")
    dialog.close()


def test_offices_panel_uses_template(monkeypatch):
    """Şablon seçiliyse `create_office_from_template` yolu kullanılır."""
    from entropy.desk.offices_panel import OfficesPanel

    created = []
    mod = types.ModuleType("entropy.agents.templates")
    mod.list_templates = lambda: []
    mod.create_office_from_template = lambda template, office_name, provider=None: (
        created.append((template, office_name, provider)))
    monkeypatch.setitem(sys.modules, "entropy.agents.templates", mod)

    panel = OfficesPanel(registry=None)
    ok = panel.create_from_template(
        {"name": "yeni-ofis", "template": "arastirma-ekibi", "default_provider": "agy"})
    assert ok is True and created == [("arastirma-ekibi", "yeni-ofis", "agy")]
    # Sözleşme yoksa False → çağıran normal yola düşer.
    monkeypatch.delitem(sys.modules, "entropy.agents.templates")
    broken = types.ModuleType("entropy.agents.templates")
    monkeypatch.setitem(sys.modules, "entropy.agents.templates", broken)
    assert panel.create_from_template({"name": "x", "template": "y"}) is False
    panel.close()


# --------------------------------------------------------------- benzerlik


SHORT_TOPICS = ["SABR volatilite", "CLO kredi", "Otonom ajan", "Obsidian bellek"]


def _short_corpus(count: int = 60):
    return [{"id": f"Reports/R{i}", "name": f"{SHORT_TOPICS[i % 4]} Faz{i}"}
            for i in range(count)]


def test_similarity_survives_small_corpus_with_short_titles():
    """QA açık maddesi: 60 raporluk izole korpusta ≥ 20 kenar üretilmeli."""
    leaf = _short_corpus(60)
    links = kg.build_similarity_links(leaf)
    assert len(links) >= 20, f"küçük korpusta kenar üretilmedi: {len(links)}"
    names = {n["id"]: n["name"] for n in leaf}
    same = sum(
        1 for l in links
        if names[l["source"]].rsplit(" ", 1)[0] == names[l["target"]].rsplit(" ", 1)[0]
    )
    assert same / len(links) > 0.9, f"kenarların çoğu aynı konuda olmalı: {same}/{len(links)}"


def test_phase_and_date_tokens_dropped():
    """`fazN` / yıl / sürüm belirteçleri TF-IDF'e girmez."""
    toks = kg._similarity_tokens("SABR volatilite Faz72 2026 v071")
    assert "faz72" not in toks and "v071" not in toks and "2026" not in toks
    assert "volatilite" in toks


def test_similarity_floor_and_best_k():
    """Mutlak taban 0.18'in altındaki çiftler bağlanmaz; k=3 üst sınır."""
    assert kg.SIMILARITY_MIN == pytest.approx(0.18)
    leaf = _short_corpus(24)
    links = kg.build_similarity_links(leaf)
    assert all(l["weight"] >= kg.SIMILARITY_MIN - 1e-9 for l in links)
    degree = {}
    for l in links:
        degree[l["source"]] = degree.get(l["source"], 0) + 1
        degree[l["target"]] = degree.get(l["target"], 0) + 1
    # k-NN karşılıklı olduğu için derece k'yı aşabilir ama 2k'yı aşmamalı.
    assert max(degree.values()) <= 2 * kg.SIMILARITY_K
