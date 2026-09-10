"""
Faz 9 (arayüz 2. tur) testleri.

Kapsanan davranışlar:
  1. Kart kökü ayrımı — ofissiz pano yalnızca Entropy kartlarını, ofisli pano
     yalnızca kendi ofisinin kartlarını gösterir; toplam korunur.
  2. Model listeleri sağlayıcıya göre değişir; agy listesindeki her ad canlı
     `agy models` çıktısında bulunur.
  3. Desk "Ofise talimat" kutusu — boş metin reddi, gönderim, rozet.
  4. Sprite tıklaması → Akış paneli o ajana odaklanır.
  5. Entropy ajan formu Desk ajanlarını göstermez.
  6. Ofis "silme" düğmesi arşivler (klasör kasada kalır, arşive taşınır).

Hiçbir test model çağırmaz ve gerçek kasaya yazmaz (tmp_path kasaları).
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from entropy.agents.tasks import ALL_CARDS, TaskBoard, TaskCard
from entropy.desk.offices_panel import OfficesPanel
from entropy.desk.stream_panel import StreamPanel
from entropy.desk.window import AgentDeskWindow, reset_desk_window
from entropy.ui.widgets.agents_widget import (
    FALLBACK_MODELS, AgentEditDialog, AgentsWidget, AssignTaskDialog,
    list_cards_for, model_belongs_to, models_for_provider,
)
from entropy.ui.widgets.task_board_widget import TaskBoardWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------ 1) kart kökleri

@pytest.fixture
def mixed_vault(tmp_path):
    """İki Entropy kartı + iki ofiste ikişer ofis kartı olan tmp kasa."""
    board = TaskBoard(vault_path=tmp_path)
    for i in range(2):
        board.create(TaskCard(id=f"ent-{i}", title=f"Entropy {i}", agent="entropy-agent"))
    for office in ("alfa", "beta"):
        for i in range(2):
            board.create(TaskCard(
                id=f"{office}-{i}", title=f"{office} {i}",
                agent=f"{office}-orkestrator", office=office,
            ))
    return board


def test_board_roots_are_disjoint(mixed_vault):
    board = mixed_vault
    assert len(board.list()) == 2
    assert len(board.list(office="alfa")) == 2
    assert len(board.list(office="beta")) == 2
    assert len(board.list(office=ALL_CARDS)) == 6


def test_zen_board_shows_only_entropy_cards(app, mixed_vault):
    """Zen 'Görevler' sekmesi = ofissiz pano; ofis kartı görünmemeli."""
    widget = TaskBoardWidget(board=mixed_vault)
    titles = {str(c.title) for c in widget.list_cards()}
    assert titles == {"Entropy 0", "Entropy 1"}
    assert not any(c.office for c in widget.list_cards())


def test_office_board_shows_only_its_own_office(app, mixed_vault):
    alfa = TaskBoardWidget(board=mixed_vault, office="alfa")
    beta = TaskBoardWidget(board=mixed_vault, office="beta")
    zen = TaskBoardWidget(board=mixed_vault)
    assert {str(c.title) for c in alfa.list_cards()} == {"alfa 0", "alfa 1"}
    assert {str(c.title) for c in beta.list_cards()} == {"beta 0", "beta 1"}
    # Sayılar toplamı = toplam kart sayısı (kayıp/çift sayım yok).
    total = len(zen.list_cards()) + len(alfa.list_cards()) + len(beta.list_cards())
    assert total == len(mixed_vault.list(office=ALL_CARDS)) == 6


def test_list_cards_for_falls_back_for_legacy_boards(mixed_vault):
    """`office` argümanı almayan sahte/eski panolarda çağrı çökmez."""

    class LegacyBoard:
        def list(self):
            return ["a", "b"]

    assert list_cards_for(LegacyBoard(), "alfa") == ["a", "b"]
    assert list_cards_for(None, "") == []


def test_projects_and_stream_panels_see_office_cards(app, mixed_vault):
    from entropy.desk.projects_panel import ProjectsPanel

    stream = StreamPanel(board=mixed_vault, office="alfa")
    stream.focus_agent("alfa-orkestrator")
    assert len(stream.cards_for_agent()) == 2

    panel = ProjectsPanel(office="alfa", desk=None, board=mixed_vault)
    # Kart sayacı kartlara ULAŞABİLİYOR (proje alanı boş olduğu için sözlük
    # boş kalır; ulaşamama durumunda çağrı hiç kart görmezdi).
    assert list_cards_for(panel.board, panel.office)


def test_tasks_watcher_watches_both_roots(app, mixed_vault, tmp_path):
    from entropy.agents.watchers import TasksWatcher

    watcher = TasksWatcher(vault_path=tmp_path, poll_interval_ms=60_000)
    files = {p.name for p in watcher._md_files()}
    assert {"ent-0.md", "alfa-0.md", "beta-1.md"} <= files
    watcher.start()
    watched = {os.path.normcase(d) for d in watcher.watched_dirs()}
    assert any("offices" in d and "cards" in d for d in watched)
    watcher.stop()


# ------------------------------------------------------------- 2) model listeleri

def test_agy_fallback_models_come_from_live_agy_models():
    """agy listesindeki her ad `agy models` çıktısında bulunmalı (uydurma yok)."""
    import shutil
    import subprocess

    exe = shutil.which("agy") or shutil.which("agy.cmd")
    if exe is None:
        pytest.skip("agy CLI bulunamadı")
    out = subprocess.run([exe, "models"], capture_output=True, text=True, timeout=120)
    live = set()
    for line in (out.stdout or "").splitlines():
        name = line.split("\t", 1)[0].strip()
        if name and not name.endswith("...") and " " not in name:
            live.add(name)
    assert live, "agy models çıktısı okunamadı"
    missing = [m for m in FALLBACK_MODELS["agy"] if m not in live]
    assert not missing, f"canlı listede olmayan adlar: {missing}"


def test_claude_fallback_models_include_full_names_and_aliases():
    from entropy.core.claude_bridge import CLAUDE_MODELS

    models = FALLBACK_MODELS["claude"]
    for name in CLAUDE_MODELS:
        assert name in models
    for alias in ("opus", "sonnet", "haiku"):
        assert alias in models


def test_model_belongs_to_separates_providers():
    assert model_belongs_to("claude", "claude-opus-5")
    assert model_belongs_to("claude", "opus")
    assert model_belongs_to("claude", "opus[1m]")
    assert model_belongs_to("claude", "sonnet[1m]")
    assert not model_belongs_to("claude", "gemini-3.8-flash-high")
    assert model_belongs_to("agy", "gemini-3.8-flash-high")
    assert not model_belongs_to("agy", "claude-opus-5")
    # Boş = "oturumun modelini miras al", her sağlayıcıda geçerli.
    assert model_belongs_to("agy", "")


def test_models_for_provider_ignores_bridge_of_other_provider():
    class ForeignBridge:
        provider_name = "claude"

        def fetch_available_models(self):
            return ["claude-opus-5"]

    models = models_for_provider("agy", ForeignBridge())
    assert models == FALLBACK_MODELS["agy"]
    assert "claude-opus-5" not in models


def test_entropy_agent_form_model_box_follows_provider(app):
    dialog = AgentEditDialog(skills=[])
    dialog.provider_combo.setCurrentText("claude")
    assert all(model_belongs_to("claude", m) for m in dialog.model_choices())
    dialog.provider_combo.setCurrentText("agy")
    assert all(model_belongs_to("agy", m) for m in dialog.model_choices())


def test_assign_task_dialog_model_box_follows_provider(app):
    dialog = AssignTaskDialog(agent_name="x", skills=[])
    dialog.provider_combo.setCurrentText("claude")
    assert dialog.model_choices() and all(
        model_belongs_to("claude", m) for m in dialog.model_choices())
    dialog.model_combo.setCurrentText("claude-opus-5")
    # Sağlayıcı değişince yabancı ad "miras al"a (boş) düşer.
    dialog.provider_combo.setCurrentText("agy")
    assert dialog.model_combo.currentText() == ""
    assert all(model_belongs_to("agy", m) for m in dialog.model_choices())
    # Boş ilk girdi = oturumun modelini miras al.
    assert dialog.model_combo.itemText(0) == ""


def test_card_detail_model_box_follows_provider(app, mixed_vault):
    widget = TaskBoardWidget(board=mixed_vault)
    detail = widget.detail_panel
    detail.provider_combo.setCurrentText("claude")
    assert all(model_belongs_to("claude", m) for m in detail.model_choices())
    detail.provider_combo.setCurrentText("agy")
    assert all(model_belongs_to("agy", m) for m in detail.model_choices())
    assert detail.model_combo.itemText(0) == ""


def test_top_bar_model_selection_reverts_on_foreign_name(app):
    from entropy.ui.widgets.ui_polish import accept_model_selection
    from PySide6.QtWidgets import QComboBox

    class FakeClaudeBridge:
        provider_name = "claude"
        selected_model = "claude-opus-5"

        def set_model(self, name):
            self.selected_model = name
            return True

    bridge = FakeClaudeBridge()
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItems(["claude-opus-5", "claude-sonnet-5"])
    combo.setCurrentText("claude-opus-5")

    assert accept_model_selection(bridge, combo, "claude-sonnet-5") is True
    assert bridge.selected_model == "claude-sonnet-5"

    assert accept_model_selection(bridge, combo, "gemini-3.8-flash-high") is False
    assert bridge.selected_model == "claude-sonnet-5"
    assert combo.currentText() == "claude-sonnet-5"


# ------------------------------------------------------- 3) ofise talimat kutusu

class _FakeOfficeRegistry:
    def __init__(self, names):
        self._names = list(names)

    def list(self):
        return [{"name": n, "goal": "", "members": []} for n in self._names]

    def get(self, name):
        for spec in self.list():
            if spec["name"] == name:
                return spec
        return None

    def delete(self, name):
        self._names = [n for n in self._names if n != name]
        return True

    def archive(self, name, dry_run=False):
        """
        Faz 10-C: panel artık `vault_hygiene.archive_office`'i doğrudan değil,
        kayıt defterinin `archive()` sözleşmesi üzerinden çağırıyor (önce kart
        worktree'leri bırakılır, canlı etkileşimli koşular kapatılır, sonra
        klasör taşınır). Sahte defter bu sözleşmeyi gerçek `DeskRegistry`'ye
        devrederek sıranın gerçekten işlediğini doğrular.
        """
        from entropy.agents.desk_registry import DeskRegistry

        return DeskRegistry(vault_path=self.vault_path).archive(
            name, dry_run=dry_run
        )


@pytest.fixture
def desk_window(app, tmp_path, monkeypatch, mixed_vault):
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", str(tmp_path), raising=False)
    reset_desk_window()
    window = AgentDeskWindow(
        office_registry=_FakeOfficeRegistry(["alfa", "beta"]),
        agent_registry=None,
        board=mixed_vault,
    )
    yield window
    window.close()
    reset_desk_window()


def test_desk_instruct_box_rejects_empty(desk_window):
    desk_window.set_office("alfa")
    desk_window.instruct_input.setText("   ")
    assert desk_window.send_instruction() is False
    assert "boş" in desk_window.instruct_status.text().lower()


def test_desk_instruct_box_sends_and_shows_badge(desk_window, tmp_path):
    from entropy.agents.mailbox import office_mailbox

    desk_window.set_office("alfa")
    before = office_mailbox("alfa", vault_path=tmp_path).unread_count()
    desk_window.instruct_input.setText("Önce mimari raporu tazele.")
    assert desk_window.send_instruction() is True
    # Kutu temizlendi ve bilgilendirme yazıldı.
    assert desk_window.instruct_input.text() == ""
    assert "sonraki planına" in desk_window.instruct_status.text()
    after = office_mailbox("alfa", vault_path=tmp_path).unread_count()
    assert after == before + 1
    assert desk_window.unread_count() == after
    assert "okunmamış" in desk_window.instruct_badge.text()


def test_desk_instruct_box_needs_an_office(desk_window):
    desk_window.set_office("")
    assert desk_window.instruct_input.isEnabled() is False
    desk_window.instruct_input.setText("bir şey")
    assert desk_window.send_instruction() is False


# -------------------------------------------------- 4) sprite → akış paneli

def test_sprite_click_focuses_stream_tab(desk_window):
    from entropy.desk.window import TAB_STREAM

    desk_window.set_office("alfa")
    desk_window.scene.agent_clicked.emit("alfa-orkestrator")
    assert desk_window.tabs.currentIndex() == TAB_STREAM
    assert desk_window.stream_panel.agent == "alfa-orkestrator"
    # Başlıkta ajan adı, gövdede son kartın özeti.
    assert "alfa-orkestrator" in desk_window.stream_panel.title_label.text()
    assert "alfa 1" in desk_window.stream_panel.view.toPlainText()


# ------------------------------------- 5) Entropy formu Desk ajanlarını gizler

def test_entropy_agents_panel_hides_desk_agents(app, mixed_vault):
    class MixedRegistry:
        def list(self):
            return [
                {"name": "entropy-worker", "role": "worker", "office": ""},
                {"name": "alfa-orkestrator", "role": "orchestrator", "office": "alfa"},
            ]

    widget = AgentsWidget(registry=MixedRegistry(), board=mixed_vault)
    names = [str(a["name"]) for a in widget.list_agents()]
    assert names == ["entropy-worker"]


# ---------------------------------------- 7) pencere tek ekrana sığıyor mu

def test_desk_window_logical_minimum_fits_small_screen(desk_window):
    """
    Mantıksal asgari boyut ≤ 960x540 (Faz 9 hedefi).

    `minimumSizeHint` mantıksal piksel döndürür; ölçüm %200 ölçekte
    (`QT_SCALE_FACTOR=2`) de aynı çıkar — bu yüzden burada tek koşuda
    doğrulanabiliyor.
    """
    hint = desk_window.minimumSizeHint()
    assert hint.width() <= 960, hint.width()
    assert hint.height() <= 540, hint.height()


# ------------------------------------------------------- 6) ofis arşivleme

def test_office_delete_button_archives_instead_of_deleting(app, tmp_path, monkeypatch):
    from entropy.core.config import config
    from entropy.brain import vault_hygiene

    monkeypatch.setattr(config, "obsidian_vault_path", str(tmp_path), raising=False)
    office_dir = tmp_path / "Desk" / "Offices" / "alfa"
    (office_dir / "cards").mkdir(parents=True)
    (office_dir / "MEMORY.md").write_text("ofis belleği", encoding="utf-8")

    registry = _FakeOfficeRegistry(["alfa", "beta"])
    registry.vault_path = tmp_path
    panel = OfficesPanel(registry=registry, agent_registry=None)

    calls = {}
    real = vault_hygiene.archive_office

    def spy(office, vault_path=None, dry_run=True, date=None):
        calls["args"] = (office, vault_path, dry_run)
        return real(office, vault_path=vault_path, dry_run=dry_run, date=date)

    monkeypatch.setattr(vault_hygiene, "archive_office", spy)

    assert panel.archive_office("alfa", confirm=False) is True
    assert calls["args"][0] == "alfa"
    assert calls["args"][2] is False          # dry_run kapalı: gerçekten taşınır
    # Ofis klasörü SİLİNMEDİ, arşive taşındı.
    assert not office_dir.exists()
    archive_root = tmp_path / "Entropy" / "_archive"
    assert archive_root.is_dir()
    survivors = list(archive_root.rglob("MEMORY.md"))
    assert survivors, "ofis klasörü arşivde bulunamadı"

    # Düğmenin etiketi ve ipucu 'arşiv' der (silme değil).
    assert "Arşivle" in panel.delete_btn.text()
    assert "arşiv" in panel.delete_btn.toolTip().lower()


# ---------------------------------------------------------------------------
# Faz 9: model/efor/saglayici kutulari dar pencerede metni kirpmamali
# ---------------------------------------------------------------------------

def _clips(combo) -> bool:
    """Kutu, gorunen metnini kirpiyor mu? (metin geniligi + kenar payi > kutu)"""
    text = combo.currentText()
    return combo.fontMetrics().horizontalAdvance(text) + 44 > combo.width()


def test_chat_top_bar_model_combo_does_not_clip_at_620px(app):
    from entropy.ui.modes.chat_mode import ChatModeWindow
    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    win = ChatModeWindow(bridge=bridge)
    win.resize(620, 700)
    win.show()
    app.processEvents()

    combo = win.model_combo
    # En uzun model adi bile sigmali (acilir liste kapali kutuyu belirler).
    longest = max(
        [combo.itemText(i) for i in range(combo.count())] or [""], key=len
    )
    assert combo.width() >= combo.fontMetrics().horizontalAdvance(longest) + 44
    assert not _clips(combo)
    assert not _clips(win.provider_combo)
    if getattr(win, "effort_combo", None) is not None:
        assert not _clips(win.effort_combo)
    win.close()


def test_zen_top_bar_model_combo_does_not_clip_at_620px(app):
    from entropy.ui.modes.zen_mode import ZenModeWindow
    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    win = ZenModeWindow(bridge=bridge)
    win.resize(620, 700)
    win.show()
    app.processEvents()

    assert not _clips(win.model_combo)
    assert not _clips(win.provider_combo)
    win.close()
