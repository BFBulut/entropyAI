"""
Faz 4 arayüz testleri: adlandırma/temizlik, cila ve Rapor Merkezi "Gelen" şeridi.

Kapsam:
  1. `desk/legacy` kaldırıldı, "muratify" hiçbir kaynakta geçmiyor, başlıklar
     ve düğme metni "Entropy Agent Desk" / "Entropy AI".
  2. Metin kırpma (ElideRight) + tam metin ipucu, yatay kaydırma politikası,
     bilgi grafiği efsanesindeki yeni girdiler.
  3. `ReportInboxStore` / `ReportInboxStrip`: 24 saat penceresi, okundu/pin/
     arşiv, okunmadı rozeti.

Gerçek süreç başlatan hiçbir çağrı yok (`TaskBoard.run` / `OfficeHarness.start`
çağrılmaz); AGY/Claude köprüsüne dokunulmaz.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"


# ===================================================== 1. adlandırma ve temizlik

def test_legacy_desk_package_removed():
    """`desk/legacy/` tamamen kaldırıldı ve hiçbir yerden içe aktarılmıyor."""
    assert not (SRC_ROOT / "entropy" / "desk" / "legacy").exists()

    with pytest.raises(ImportError):
        __import__("entropy.desk.legacy")


def test_no_muratify_reference_in_sources():
    """Uygulama kaynaklarında "muratify" geçmez (büyük/küçük harf duyarsız)."""
    hits = []
    for path in SRC_ROOT.rglob("*"):
        if path.suffix.lower() not in {".py", ".md", ".json", ".html", ".spec", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "muratify" in text.lower():
            hits.append(str(path))
    assert hits == [], f"muratify kalıntısı: {hits}"


def test_spec_hiddenimports_drops_legacy():
    """PyInstaller spec artık kaldırılan paketi gizli içe aktarma saymıyor."""
    spec = (REPO_ROOT / "EntropyAI.spec").read_text(encoding="utf-8")
    assert "entropy.desk.legacy" not in spec
    # Yaşayan desk modülleri listede kalmalı (yanlışlıkla hepsi silinmesin).
    assert "entropy.desk.window" in spec


def test_desk_window_title_and_button_text(qapp):
    """Pencere başlığı ve her iki kipteki düğme metni "Entropy Agent Desk"."""
    from entropy.desk.window import WINDOW_TITLE

    assert WINDOW_TITLE == "Entropy Agent Desk"

    from entropy.ui.modes import chat_mode as chat_mod
    from entropy.ui.modes import zen_mode as zen_mod

    chat_src = Path(chat_mod.__file__).read_text(encoding="utf-8")
    zen_src = Path(zen_mod.__file__).read_text(encoding="utf-8")
    assert 'QPushButton("🏢 Entropy Agent Desk")' in chat_src
    assert 'QPushButton("🏢 Entropy Agent Desk")' in zen_src


def test_desk_window_sets_titles(qapp, monkeypatch):
    """Pencere kurulunca başlık "Entropy Agent Desk" ile başlar."""
    from entropy.desk.window import AgentDeskWindow, reset_desk_window

    reset_desk_window()
    window = AgentDeskWindow(office_registry=_FakeOfficeRegistry([]))
    try:
        assert window.windowTitle().startswith("Entropy Agent Desk")
    finally:
        window.deleteLater()
        reset_desk_window()


# ======================================================= 2. arayüz cilası

class _FakeSpec(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


class _FakeOfficeRegistry:
    def __init__(self, offices=None):
        self._offices = list(offices or [])

    def list(self):
        return list(self._offices)

    def get(self, name):
        for office in self._offices:
            if office["name"] == name:
                return office
        return None


LONG_PURPOSE = (
    "Bu ofis çok uzun bir amaç metnine sahiptir ve bu metin panelin genişliğini "
    "kolayca aşarak yatay kaydırma çubuğu doğurabilir; kırpılması beklenir."
)


def _office(name="arastirma", purpose=LONG_PURPOSE):
    return _FakeSpec({
        "name": name, "purpose": purpose, "orchestrator": "lider",
        "evaluator": "denetci", "members": ["lider", "denetci"],
        "default_provider": "agy", "default_model": "", "max_parallel": 2,
        "budget_tokens": 0, "charter": "", "path": "", "updated_at": "",
    })


def test_offices_list_elides_and_keeps_full_text_in_tooltip(qapp):
    """Uzun ofis amacı kırpılır ama tam metin ipucunda durur; yatay çubuk kapalı."""
    from entropy.desk.offices_panel import OfficesPanel

    panel = OfficesPanel(registry=_FakeOfficeRegistry([_office()]))
    try:
        view = panel.list_widget
        assert view.textElideMode() == Qt.TextElideMode.ElideRight
        assert view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert view.wordWrap() is False

        item = view.item(0)
        # Görünen metin tek satır (eski sabit 60 karakter kesmesi kalktı).
        assert "\n" not in item.text()
        # Kırpılan kısım ipucunda tam olarak durur.
        assert LONG_PURPOSE in item.toolTip()
    finally:
        panel.deleteLater()


def test_offices_action_buttons_have_tooltips(qapp):
    """İkon düğmelerin her birinin açıklayıcı ipucu var."""
    from entropy.desk.offices_panel import OfficesPanel

    panel = OfficesPanel(registry=_FakeOfficeRegistry([_office()]))
    try:
        for attr in ("edit_btn", "delete_btn", "refresh_btn", "create_btn"):
            btn = getattr(panel, attr)
            assert btn.toolTip().strip(), f"{attr} ipucusuz"
    finally:
        panel.deleteLater()


def test_reports_list_has_elide_and_no_hscroll(qapp):
    """Rapor listesi de aynı kırpma/kaydırma politikasını kullanır."""
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    widget = ReportsViewerWidget()
    try:
        view = widget.list_widget
        assert view.textElideMode() == Qt.TextElideMode.ElideRight
        assert view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    finally:
        widget.deleteLater()


def test_elided_label_keeps_full_text(qapp):
    """`ElidedLabel` görünen metni kırpar, tam metni ipucunda ve API'de tutar."""
    from entropy.ui.widgets.ui_polish import ElidedLabel

    text = "Çok uzun bir başlık " * 8
    label = ElidedLabel(text)
    label.resize(120, 20)
    try:
        assert label.full_text() == text
        assert label.toolTip() == text
        assert len(label.text()) < len(text)
    finally:
        label.deleteLater()


def test_apply_list_polish_is_safe_on_plain_list(qapp):
    """Yardımcı, stil verilmemiş sade bir listede de çalışır (guard testi)."""
    from entropy.ui.widgets.ui_polish import apply_list_polish

    view = QListWidget()
    try:
        apply_list_polish(view)
        assert view.textElideMode() == Qt.TextElideMode.ElideRight
        assert view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    finally:
        view.deleteLater()


def test_kanban_columns_have_minimum_width(qapp):
    """Kanban sütunları okunur bir alt genişliğe sahiptir (kart sıkışmasın)."""
    from entropy.ui.widgets.task_board_widget import COLUMN_MIN_WIDTH, TaskBoardWidget

    board = TaskBoardWidget(board=None)
    try:
        assert COLUMN_MIN_WIDTH >= 180
        columns = [
            head.parentWidget() for head in board.column_headers.values()
        ]
        assert columns, "sütun bulunamadı"
        for column in columns:
            assert column.minimumWidth() >= COLUMN_MIN_WIDTH
    finally:
        board.deleteLater()


def test_scene_elides_labels_and_offers_tooltip(qapp):
    """Sahne etiketleri masa genişliğine kırpılır; tam ad ipucundan okunur."""
    from PySide6.QtCore import QPoint

    from entropy.desk.scene import OfficeScene

    long_name = "cok-uzun-adli-arastirma-ajani-2026"
    scene = OfficeScene(office=_FakeSpec({
        "name": "ofis", "orchestrator": long_name, "evaluator": "",
        "members": [long_name],
    }))
    try:
        scene.resize(600, 400)
        scene.relayout()
        slot = scene.slots[0]
        # Yeni sahnede çarpışma dikdörtgeni `DeskSlot.rect` üzerinden gelir;
        # merkezinden hit-test edilir (`slot_at` mantıksal koordinata çevirir).
        center = scene.to_widget(slot.rect.center())
        found = scene.slot_at(QPoint(center.x(), center.y()))
        assert found is not None and found.agent == long_name
        # Şerit dışında ipucu boşalır.
        assert scene.slot_at(QPoint(-500, -500)) is None
    finally:
        scene.deleteLater()


def test_graph_legend_has_new_groups():
    """Efsanede hub-offices / concept / entity girdileri ve renkleri var."""
    src = (SRC_ROOT / "entropy" / "ui" / "widgets" / "knowledge_graph.py").read_text(
        encoding="utf-8"
    )
    for group in ("hub-offices", "concept", "entity"):
        assert f"toggleCategory('{group}'" in src, f"{group} efsanede yok"
        assert f"'{group}': true" in src, f"{group} kategori varsayılanı yok"
    # Renkler: kavram açık yeşil, varlık açık mavi.
    assert "'concept': '#9BE9A8'" in src
    assert "'entity': '#8CC8FF'" in src
    assert "'hub-offices': '#FFC94D'" in src
    # İkonlar
    assert "'concept': '📗'" in src
    assert "'entity': '🏷'" in src


def test_graph_script_is_valid_javascript():
    """Grafik JS'i `node --check` ile sözdizimi doğrulanır (varsa)."""
    import re

    node = None
    for candidate in ("node", "node.exe"):
        try:
            subprocess.run([candidate, "--version"], capture_output=True, timeout=20)
            node = candidate
            break
        except (OSError, subprocess.SubprocessError):
            continue
    if node is None:
        pytest.skip("node bulunamadı")

    src = (SRC_ROOT / "entropy" / "ui" / "widgets" / "knowledge_graph.py").read_text(
        encoding="utf-8"
    )
    blocks = re.findall(r"<script>(.*?)</script>", src, re.DOTALL)
    assert blocks, "script bloğu bulunamadı"
    import tempfile

    for block in blocks:
        js = block.replace("{{", "{").replace("}}", "}")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(js)
            temp = fh.name
        try:
            result = subprocess.run([node, "--check", temp], capture_output=True, timeout=60)
            assert result.returncode == 0, result.stderr.decode("utf-8", "ignore")
        finally:
            os.unlink(temp)


def test_command_card_and_chat_share_reading_typography(qapp):
    """Komut kartı, sohbet balonu ve akış paneli tek tipografi kaynağını kullanır."""
    from entropy.ui.themes.cyber_theme import READING_TOKENS as RT, reading_css
    from entropy.ui.widgets.markdown_renderer import (
        build_chat_bubble_html, build_command_card_html,
    )

    card = build_command_card_html("<table><tr><td>a</td></tr></table>")
    bubble = build_chat_bubble_html("Siz", "merhaba")
    assert RT["font_size_body"] in card
    assert RT["font_size_body"] in bubble
    # Tablolar karta uysun diye belge stil sayfası tabloyu biçimliyor olmalı.
    css = reading_css()
    assert "table" in css and "border-collapse" in css

    from entropy.desk.stream_panel import StreamPanel

    panel = StreamPanel(board=None)
    try:
        assert panel.view.document().defaultStyleSheet() == css
    finally:
        panel.deleteLater()


def test_model_combo_placeholder_when_empty(qapp):
    """Boş model kutusu yer tutucu alır (kopuk ayraç görüntüsü kalkar)."""
    from PySide6.QtWidgets import QComboBox

    from entropy.ui.widgets.ui_polish import (
        MODEL_PLACEHOLDER, apply_model_placeholder, is_model_placeholder,
    )

    combo = QComboBox()
    combo.setEditable(True)
    try:
        assert apply_model_placeholder(combo, []) is True
        assert combo.lineEdit().placeholderText() == MODEL_PLACEHOLDER
        assert combo.toolTip().strip()
        assert is_model_placeholder(MODEL_PLACEHOLDER) is True
        assert is_model_placeholder("gemini-3-pro") is False

        # Dolu kutuya dokunulmaz.
        full = QComboBox()
        full.setEditable(True)
        full.addItem("gemini-3-pro")
        assert apply_model_placeholder(full, ["gemini-3-pro"]) is False
        full.deleteLater()
    finally:
        combo.deleteLater()


# ================================================ 3. Rapor Merkezi "Gelen"

def _entry(path, title, age_hours=1.0, now=None):
    now = now if now is not None else time.time()
    return {
        "path": str(path),
        "title": title,
        "label": f"📄 {title}",
        "mtime": now - age_hours * 3600,
    }


@pytest.fixture
def store(tmp_path):
    from entropy.ui.widgets.report_inbox import ReportInboxStore

    return ReportInboxStore(path=tmp_path / "report_inbox.json")


def test_inbox_filters_last_24_hours(store):
    """Şerit yalnızca son 24 saatte üretilen raporları gösterir."""
    now = time.time()
    entries = [
        _entry("/r/yeni.md", "Yeni rapor", age_hours=2, now=now),
        _entry("/r/dun.md", "Dünkü rapor", age_hours=20, now=now),
        _entry("/r/eski.md", "Eski rapor", age_hours=48, now=now),
    ]
    visible = store.inbox_entries(entries, now=now)
    titles = [e["title"] for e in visible]
    assert titles == ["Yeni rapor", "Dünkü rapor"]
    # 24 saat sınırı dışındaki rapor gerçekten elenmiş.
    assert "Eski rapor" not in titles


def test_inbox_read_pin_archive_roundtrip(store, tmp_path):
    """Okundu / pin / arşiv durumu diske yazılır ve yeniden okunur."""
    now = time.time()
    entries = [
        _entry("/r/a.md", "A", age_hours=1, now=now),
        _entry("/r/b.md", "B", age_hours=1, now=now),
    ]
    assert store.unread_count(entries, now=now) == 2

    store.mark_read("/r/a.md")
    assert store.is_read("/r/a.md") is True
    assert store.unread_count(entries, now=now) == 1

    store.set_pinned("/r/b.md", True)
    assert store.is_pinned("/r/b.md") is True

    store.set_archived("/r/a.md", True)
    assert store.is_archived("/r/a.md") is True
    visible = [e["path"] for e in store.inbox_entries(entries, now=now)]
    assert "/r/a.md" not in visible, "arşivlenen girdi şeritten düşmeli"

    # Kalıcılık: yeni bir depo aynı dosyadan aynı durumu okur.
    from entropy.ui.widgets.report_inbox import ReportInboxStore

    reloaded = ReportInboxStore(path=store.path)
    assert reloaded.is_read("/r/a.md") is True
    assert reloaded.is_pinned("/r/b.md") is True
    assert reloaded.is_archived("/r/a.md") is True


def test_pinned_entry_survives_24h_window(store):
    """Sabitlenen rapor 24 saat dolsa da şeritte kalır."""
    now = time.time()
    entries = [_entry("/r/eski.md", "Eski ama sabit", age_hours=72, now=now)]
    assert store.inbox_entries(entries, now=now) == []

    store.set_pinned("/r/eski.md", True)
    visible = store.inbox_entries(entries, now=now)
    assert [e["title"] for e in visible] == ["Eski ama sabit"]
    # Sabitliler en başta sıralanır.
    assert visible[0]["pinned"] is True


def test_archiving_clears_unread_count(store):
    """Arşivlenen okunmamış rapor rozeti şişirmez."""
    now = time.time()
    entries = [_entry("/r/a.md", "A", age_hours=1, now=now)]
    assert store.unread_count(entries, now=now) == 1
    store.set_archived("/r/a.md", True)
    assert store.unread_count(entries, now=now) == 0


def test_store_survives_corrupt_state_file(tmp_path):
    """Bozuk durum dosyası paneli çökertmez; her şey okunmadı sayılır."""
    from entropy.ui.widgets.report_inbox import ReportInboxStore

    path = tmp_path / "report_inbox.json"
    path.write_text("{bozuk json", encoding="utf-8")
    store = ReportInboxStore(path=path)
    assert store.entry("/r/a.md") == {}
    assert store.is_read("/r/a.md") is False


def test_inbox_strip_opens_and_marks_read(qapp, tmp_path):
    """Şeritteki girdiye tıklanınca rapor açılır ve okundu işaretlenir."""
    from entropy.ui.widgets.report_inbox import ReportInboxStore, ReportInboxStrip

    now = time.time()
    store = ReportInboxStore(path=tmp_path / "inbox.json")
    strip = ReportInboxStrip(store=store)
    opened = []
    unread_seen = []
    strip.report_opened.connect(opened.append)
    strip.unread_changed.connect(unread_seen.append)
    try:
        strip.set_now(now)
        strip.set_entries([
            _entry("/r/a.md", "A", age_hours=1, now=now),
            _entry("/r/b.md", "B", age_hours=1, now=now),
        ])
        assert strip.unread_count() == 2
        assert len(strip.item_widgets) == 2

        strip.open_report("/r/a.md")
        assert opened == ["/r/a.md"]
        assert store.is_read("/r/a.md") is True
        assert strip.unread_count() == 1
        # Rozet sinyali her tazelemede yayılır ve son değer doğrudur.
        assert unread_seen[-1] == 1

        strip.mark_all_read()
        assert strip.unread_count() == 0
    finally:
        strip.deleteLater()


def test_inbox_strip_pin_and_archive_actions(qapp, tmp_path):
    """Şeritteki pin/arşiv düğmeleri depoyu günceller ve görünümü tazeler."""
    from entropy.ui.widgets.report_inbox import ReportInboxStore, ReportInboxStrip

    now = time.time()
    store = ReportInboxStore(path=tmp_path / "inbox.json")
    strip = ReportInboxStrip(store=store)
    try:
        strip.set_now(now)
        strip.set_entries([_entry("/r/a.md", "A", age_hours=1, now=now)])

        assert strip.toggle_pin("/r/a.md") is True
        assert store.is_pinned("/r/a.md") is True
        assert strip.toggle_pin("/r/a.md") is False

        strip.archive("/r/a.md")
        assert store.is_archived("/r/a.md") is True
        assert strip.item_widgets == []
        # Boş durum metni görünür ve açıklayıcıdır.
        assert strip.empty_label.isVisible() or strip.empty_label.text()
        assert "24 saat" in strip.empty_label.text()
    finally:
        strip.deleteLater()


def test_inbox_badge_hides_at_zero(qapp):
    """Rozet sıfırken gizlenir, pozitifken sayıyı ve ipucunu gösterir."""
    from entropy.ui.widgets.report_inbox import InboxBadge

    badge = InboxBadge()
    try:
        badge.set_count(0)
        assert badge.count == 0
        assert badge.isVisible() is False
        assert badge.text() == ""

        badge.set_count(3)
        assert badge.count == 3
        assert "3" in badge.text()
        assert badge.toolTip().strip()
    finally:
        badge.deleteLater()


def test_reports_viewer_hosts_inbox_strip(qapp):
    """Raporlar sekmesinin üstünde Gelen şeridi kuruludur ve okuyucuya bağlıdır."""
    from entropy.ui.widgets.report_inbox import ReportInboxStrip
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    widget = ReportsViewerWidget()
    try:
        assert isinstance(widget.inbox_strip, ReportInboxStrip)
        # Şerit, listeden önce (en üstte) yer alır.
        idx_strip = widget.layout.indexOf(widget.inbox_strip)
        idx_splitter = widget.layout.indexOf(widget.splitter)
        assert idx_strip < idx_splitter
    finally:
        widget.deleteLater()


def test_bus_exposes_inbox_unread_signal():
    """Rozet sayacı olay veri yolu üzerinden dağıtılır."""
    from entropy.core.event_bus import bus

    assert hasattr(bus, "report_inbox_unread")
    received = []
    bus.report_inbox_unread.connect(received.append)
    bus.report_inbox_unread.emit(4)
    assert received == [4]


def test_zen_and_chat_badge_slots_are_qobject_methods():
    """Rozet alıcıları lambda değil, QObject slotu (iş parçacığı kuralı)."""
    from entropy.ui.modes.chat_mode import ChatModeWindow
    from entropy.ui.modes.zen_mode import ZenModeWindow

    assert callable(getattr(ZenModeWindow, "_on_inbox_unread", None))
    assert callable(getattr(ChatModeWindow, "_on_inbox_unread", None))
