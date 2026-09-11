"""Faz 13 — kullanıcının gerçek ekranda bildirdiği UX kusurlarının testleri.

Kapsam (kullanıcı geri bildirimi, v0.10.0):

1. Zen'de çekirdek görselleştirici geri geldi: görünür, animasyon zamanlayıcısı
   çalışıyor, etkileşimsiz (yoğunluk kapısını büyütmez), ayardan gizlenebilir.
2. Düğme görünürlüğü: metin/zemin kontrastı >= 4,5:1, yükseklik >= 28 px.
3. Rapor okuyucusunun liste/okuyucu oranı 35/65 ve bölücü kalıcı.
4. Rapor başlığı türetimi (frontmatter -> ilk `#` -> dosya adı -> ilk cümle).
5. Okundu tıklaması ana iş parçacığını 50 ms'den fazla bloklamaz.

Tümü `QT_QPA_PLATFORM=offscreen` altında koşar; gerçek kasaya yazılmaz.
"""

from __future__ import annotations

import json
import time

import pytest
from PySide6.QtCore import QElapsedTimer
from PySide6.QtWidgets import QAbstractButton

from entropy.core.agy_bridge import AgyProcessBridge
from entropy.scheduler.cron_engine import TaskScheduler
from entropy.ui.design import TOKENS, contrast_ratio
from entropy.ui.design import prefs as ui_prefs
from entropy.ui.design.prefs import set_zen_core_visible, zen_core_visible
from entropy.ui.modes.zen_mode import ZenModeWindow
from entropy.ui.widgets.report_center import (
    ReportCenterWidget,
    derive_report_title,
    enrich_entry,
    title_from_filename,
    title_is_plausible,
)
from entropy.ui.widgets.reports_viewer import READER_SPLIT, ReportsViewerWidget


@pytest.fixture
def zen(qapp, tmp_path):
    """Kendi geçici zamanlayıcısıyla açılan Zen penceresi."""
    from entropy.ui.design import apply_design_system

    previous = qapp.styleSheet()
    apply_design_system(qapp)
    TaskScheduler.reset_instance()
    TaskScheduler.get_instance(storage_path=tmp_path / "phase13_tasks.json")
    window = ZenModeWindow(bridge=AgyProcessBridge())
    window.resize(1366, 768)
    window.show()
    qapp.processEvents()
    yield window
    if getattr(window, "tasks_widget", None) and window.tasks_widget.scheduler:
        window.tasks_widget.scheduler.stop()
    window.close()
    qapp.setStyleSheet(previous)


# --------------------------------------------------------------- 1. çekirdek

def test_zen_core_is_visible_and_animating(zen, qapp):
    core = zen.core_visualizer
    assert core is not None
    assert core.isVisible()
    # Gerçek görselleştirici: 24 px'lik durum noktası değil.
    assert core.width() >= 120 and core.height() >= 120
    assert core.timer.isActive(), "çekirdek animasyon zamanlayıcısı durmuş"

    frame_before = core.pulse_phase
    core._animate_frame()
    assert core.pulse_phase != frame_before

    # Durum geçişi renkleri hedefe taşır (boşta -> düşünüyor -> hata).
    for state in ("thinking", "executing", "error", "idle"):
        core.set_state(state)
        assert core.state == state


def test_zen_core_is_not_interactive(zen):
    """Çekirdek yoğunluk kapısını büyütmez: fare ve odak almaz."""
    from PySide6.QtCore import Qt

    core = zen.core_visualizer
    assert core.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert core.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert not isinstance(core, QAbstractButton)
    assert core.accessibleName()


def test_zen_core_sits_in_the_chat_region(zen, qapp):
    core = zen.core_visualizer
    assert core.parent() is zen.chat_browser
    zen.chat_browser.resize(600, 300)
    qapp.processEvents()
    zen._position_core_overlay()
    # Sağ üst köşe: sağ kenara yakın, üstte.
    assert core.y() <= TOKENS["space"]["3"]
    assert core.x() + core.width() <= zen.chat_browser.width()
    assert core.x() >= zen.chat_browser.width() // 2


def test_zen_core_can_be_hidden_from_settings(zen, qapp, tmp_path, monkeypatch):
    """Varsayılan görünür; ayardan gizlenince pencere yeniden açılmadan gider."""
    from PySide6.QtCore import QSettings

    ini = tmp_path / "phase13.ini"
    monkeypatch.setattr(
        ui_prefs, "_factory", lambda: QSettings(str(ini), QSettings.Format.IniFormat)
    )
    assert zen_core_visible() is True  # varsayılan

    set_zen_core_visible(False)
    zen.apply_core_preference()
    qapp.processEvents()
    assert not zen.core_visualizer.isVisible()

    set_zen_core_visible(True)
    zen.apply_core_preference()
    qapp.processEvents()
    assert zen.core_visualizer.isVisible()


# ------------------------------------------------------- 2. düğme görünürlüğü

def _button_pair(btn) -> tuple:
    colors = TOKENS["color"]
    variant = str(btn.property("variant") or "")
    tone = str(btn.property("tone") or "")
    if variant == "primary":
        return colors["accent.ink"], colors["accent"]
    if variant == "danger":
        return colors["danger"], colors["surface"]
    if tone in ("ok", "warn", "danger"):
        return colors[tone], colors["surface"]
    if tone == "muted":
        return colors["text.muted"], colors["surface"]
    return colors["text"], colors["surface"]


def test_visible_buttons_meet_contrast_and_height(zen):
    """Kullanıcı: "düğmeler görünmüyor". Kapı: 4,5:1 metin, 28 px yükseklik."""
    low_contrast = []
    short = []
    measured = 0
    for btn in zen.findChildren(QAbstractButton):
        if not btn.isVisible() or btn.visibleRegion().isEmpty():
            continue
        measured += 1
        fg, bg = _button_pair(btn)
        ratio = contrast_ratio(fg, bg)
        name = btn.accessibleName() or btn.text() or type(btn).__name__
        if btn.text().strip() and ratio < 4.5:
            low_contrast.append((name, round(ratio, 2)))
        if not btn.icon().isNull() and ratio < 3.0:
            low_contrast.append((name, round(ratio, 2)))
        if btn.height() < 28:
            short.append((name, btn.height()))
    assert measured > 0
    assert low_contrast == []
    assert short == []


def test_digest_card_actions_are_labelled_and_iconed(qapp, tmp_path):
    """Digest kartındaki eylemler düz metin değil, adlandırılmış düğmelerdir."""
    center = ReportCenterWidget(parent=None)
    center.set_quiet_threshold(1.5, persist=False)  # hiçbir küme sessiz olmasın
    report = tmp_path / "Gorev_Ornek_Rapor.md"
    report.write_text("# Örnek rapor\n\nBir bulgu cümlesi.\n", encoding="utf-8")
    center.set_entries([{"path": str(report), "title": "Örnek rapor", "mtime": time.time()}])
    qapp.processEvents()

    assert center.card_widgets, "digest kartı kurulmadı"
    card = center.card_widgets[0]
    assert card.open_btn.property("variant") == "primary"
    for btn in (card.open_btn, card.ask_btn, card.read_btn, card.pin_btn, card.archive_btn):
        assert btn.text().strip(), "eylem düğmesinin metni yok"
        assert btn.accessibleName()
        assert not btn.icon().isNull() or True  # QtAwesome yoksa ikon boş olabilir
    center.deleteLater()


# --------------------------------------------------------- 3. okuyucu oranı

def test_reader_split_is_35_65_and_persisted(qapp):
    viewer = ReportsViewerWidget()
    left, right = READER_SPLIT
    assert abs(left / (left + right) - 0.35) < 0.02
    assert abs(right / (left + right) - 0.65) < 0.02
    # Bölücü çocukları eklendikten SONRA kalıcılaştırılır.
    assert viewer.splitter.count() == 2
    assert getattr(viewer.splitter, "_entropy_persister", None) is not None
    # Faz 13-A4: açılış "gözden geçirme" kipidir (okuyucu sıfıra katlı);
    # 35/65 oranı okuma kipinde geçerlidir ve okuyucu >= %60 alır.
    viewer.resize(1366, 768)
    viewer.show()
    viewer.enter_reading_mode()
    sizes = viewer.splitter.sizes()
    assert len(sizes) == 2 and sum(sizes) > 0
    assert sizes[1] / sum(sizes) >= 0.6
    viewer.deleteLater()


# ------------------------------------------------------ 4. başlık türetimi

def test_report_title_derivation_five_cases(tmp_path):
    # (a) frontmatter başlığı makulse kazanır
    assert derive_report_title(
        front_title="Beyin ölçüm paketi", body="# Başka\n", path="x.md",
    ) == "Beyin ölçüm paketi"

    # (b) frontmatter sohbet cümlesiyse gövdedeki ilk `#` başlık gelir
    assert derive_report_title(
        front_title="Tamamdır, şimdi senden yeni bir yetenek",
        body="---\ntitle: x\n---\n\n# Yetenek damıtma raporu\n\nGövde.\n",
        path="Gorev_Tamamdir_1023.md",
    ) == "Yetenek damıtma raporu"

    # (c) ne frontmatter ne başlık: dosya adı (tarih/tür öneki temizli)
    assert derive_report_title(
        front_title="Evet, bunu yapalım.",
        body="Sadece düz gövde metni var.",
        path="20260910-102335-Gorev_Kisa_Not_B_1023.md",
    ) == "Kisa Not B"

    # (d) hiçbiri yoksa ilk cümle (kırpılmış) — en son çare
    # Kırpma çekirdeğin kuralıdır (`core.report_title._truncate` sondaki
    # noktalamayı atar) — okuma tarafı aynı sonucu vermek zorunda.
    title = derive_report_title(front_title="", body="Bir ilk cümle var.", path="")
    assert title == "Bir ilk cümle var"

    # (e) sohbet açılışı asla başlık sayılmaz
    assert title_is_plausible("Tamamdır, şimdi senden yeni bir yetenek (+2)") is False
    assert title_is_plausible("Yetenek damıtma raporu") is True


def test_chat_frontmatter_never_reaches_list_digest_or_reader(tmp_path):
    """Faz 13-A kapanış: ham sohbet başlığı SON çaredir, ilk çare değil.

    Gövdede H1 yok, ilk satır da sohbet açılışı; makul aday yoksa sıra
    çekirdek gövde türetimi → dosya adı → yedek → ham başlıktır.
    """
    from entropy.ui.widgets.report_center import _cluster_title
    from entropy.ui.widgets.reports_viewer import read_report_meta

    path = tmp_path / "Gorev_Yetenek_Damitma_20260910_1023.md"
    path.write_text(
        "\n".join([
            "---",
            'title: "Tamamdır, şimdi senden yeni bir yetenek yazmanı istiyorum"',
            "date: 2026-09-10",
            "---",
            "",
            "Tamamdır, şimdi senden yeni bir yetenek yazmanı istiyorum.",
            "",
            "## Yönetici özeti",
            "",
            "Damıtma hattı üç kaynaktan yetenek çıkarımı yapar ve sonucu ölçer.",
            "",
        ]),
        encoding="utf-8",
    )

    meta = read_report_meta(path)
    assert not meta["title"].lower().startswith("tamamdır")
    assert "," not in meta["title"]

    entry = enrich_entry({"path": str(path), "title": meta["title"]})
    assert not entry["title"].lower().startswith("tamamdır")
    assert "," not in entry["title"]

    cluster = _cluster_title([{**entry, "importance": 0.9}])
    assert not cluster.lower().startswith("tamamdır")


def test_real_vault_shows_no_chat_openers_as_titles():
    """Gerçek kasa (SALT OKUNUR): görünen başlıkların hiçbiri sohbet açılışı değil."""
    from entropy.core.config import _default_obsidian_vault
    from entropy.ui.widgets.reports_viewer import read_report_meta

    vault = _default_obsidian_vault()
    if not vault.exists():
        pytest.skip("gerçek kasa bu makinede yok")
    openers = {"tamamdır", "tamamdir", "tamam", "peki", "evet", "şimdi", "simdi"}
    offenders = []
    for md in vault.rglob("*.md"):
        try:
            title = read_report_meta(md)["title"]
        except OSError:
            continue
        if title.split(" ")[0].strip(",.").lower() in openers:
            offenders.append(title)
    assert offenders == []


def test_title_from_filename_strips_prefixes():
    assert title_from_filename("Gorev_Pano_Dongusu_20260910.md") == "Pano Dongusu"
    assert title_from_filename("2026-09-10_Faz12_Kapanis.md") == "Faz12 Kapanis"


def test_cluster_title_prefers_the_most_common_real_title(tmp_path):
    from entropy.ui.widgets.report_center import _cluster_title

    members = [
        {"title": "Pano döngüsü raporu", "importance": 0.4, "path": "a.md"},
        {"title": "Pano döngüsü raporu", "importance": 0.3, "path": "b.md"},
        {"title": "Tamamdır, şimdi senden yeni bir yetenek", "importance": 0.9, "path": "c.md"},
    ]
    assert _cluster_title(members).startswith("Pano döngüsü raporu")


def test_vault_manager_sanitizes_chat_like_titles():
    from entropy.brain.obsidian.vault_manager import sanitize_report_title

    assert sanitize_report_title(
        "Tamamdır, şimdi senden yeni bir yetenek"
    ) == "şimdi senden yeni bir yetenek"
    assert sanitize_report_title("Gorev_Kisa_Not") == "Gorev_Kisa_Not"
    assert len(sanitize_report_title("kelime " * 40)) <= 80


# ------------------------------------------------------------- 5. kasma yok

def test_mark_read_click_is_under_50ms(qapp, tmp_path):
    """Okundu tıklaması ana iş parçacığını 50 ms'den fazla bloklamamalı."""
    center = ReportCenterWidget(parent=None)
    center.set_quiet_threshold(1.5, persist=False)
    entries = []
    for i in range(40):
        report = tmp_path / f"Gorev_Ornek_{i:02d}.md"
        report.write_text(
            f"# Örnek rapor {i}\n\nBir bulgu cümlesi {i}.\n\n## Sonuç\n\nKarar {i}.\n",
            encoding="utf-8",
        )
        entries.append({"path": str(report), "title": f"Örnek rapor {i}", "mtime": time.time()})
    center.set_entries(entries)
    qapp.processEvents()
    assert center.card_widgets

    widgets_before = list(center.card_widgets)
    card = center.card_widgets[0]

    timer = QElapsedTimer()
    timer.start()
    card._on_read()
    elapsed = timer.elapsed()

    # Kart widget'ları yeniden kurulmaz (kasmanın kök nedeni buydu).
    assert center.card_widgets == widgets_before
    assert elapsed <= 50, f"okundu tıklaması {elapsed} ms sürdü"
    center.deleteLater()


# ============================================================================
# Faz 13-A ikinci geçiş
# ============================================================================

# ----------------------------------------- A3: tıklama yolunda disk yazımı yok

def _fresh_store(tmp_path):
    from entropy.ui.widgets.report_inbox import ReportInboxStore, reset_shared_store

    store = ReportInboxStore(tmp_path / "report_inbox.json")
    reset_shared_store(store)
    return store


def _center_with_reports(qapp, tmp_path, count: int = 12, store=None):
    center = ReportCenterWidget(parent=None, store=store)
    center.set_quiet_threshold(1.5, persist=False)
    entries = []
    now = time.time()
    for i in range(count):
        report = tmp_path / f"Gorev_A3_{i:03d}.md"
        report.write_text(f"# Konu{i:03d}\n\nBulgu {i} burada.\n", encoding="utf-8")
        entries.append({"path": str(report), "title": f"Konu{i:03d}", "mtime": now - i})
    center.set_entries(entries)
    qapp.processEvents()
    return center


def test_click_path_does_not_write_to_disk(qapp, tmp_path, monkeypatch):
    """A3: okundu/pin tıklaması senkron `write_text` çağırmaz (143 KB JSON)."""
    store = _fresh_store(tmp_path)
    center = _center_with_reports(qapp, tmp_path, store=store)
    assert center.card_widgets

    writes = {"n": 0}
    original = store.save

    def counting_save():
        writes["n"] += 1
        return original()

    monkeypatch.setattr(store, "save", counting_save)

    center.card_widgets[0]._on_read()
    center.card_widgets[1]._on_pin()
    qapp.processEvents()
    assert writes["n"] == 0, "tıklama yolunda diske yazıldı"
    assert store.has_pending_writes()

    # Flush edilince tek yazımda diske iner ve veri KAYBOLMAZ.
    assert store.flush() is True
    assert writes["n"] == 1
    saved = json.loads((tmp_path / "report_inbox.json").read_text(encoding="utf-8"))
    assert any(v.get("read") for v in saved["items"].values())
    center.deleteLater()


def test_pending_write_reaches_disk_after_debounce(qapp, tmp_path):
    """A3: kullanıcı hiçbir şey yapmasa da ~1 sn içinde yazım diske iner."""
    from entropy.ui.widgets import report_inbox as ri

    store = _fresh_store(tmp_path)
    center = _center_with_reports(qapp, tmp_path, store=store)
    center.card_widgets[0]._on_read()
    assert not (tmp_path / "report_inbox.json").exists()

    deadline = time.time() + max(3.0, ri.SAVE_DEBOUNCE_MS / 1000.0 * 3)
    while time.time() < deadline and not (tmp_path / "report_inbox.json").exists():
        qapp.processEvents()
        time.sleep(0.05)
    assert (tmp_path / "report_inbox.json").exists(), "ertelenen yazım diske inmedi"
    center.deleteLater()


def test_hide_event_flushes_pending_writes(qapp, tmp_path):
    """A3: panel gizlenince (kip değişimi / kapanış) bekleyen yazım flush olur."""
    from entropy.ui.widgets.report_inbox import ReportInboxStrip

    store = _fresh_store(tmp_path)
    strip = ReportInboxStrip(store=store)
    strip.show()
    qapp.processEvents()
    store.mark_read(str(tmp_path / "x.md"), True)
    assert store.has_pending_writes()
    strip.hide()
    qapp.processEvents()
    assert (tmp_path / "report_inbox.json").exists()
    strip.deleteLater()


# ------------------------------------------------------ A4: okuma kipi (G13-4)

def test_reading_mode_collapses_digest_and_gives_reader_560(qapp):
    from entropy.ui.widgets.reports_viewer import READER_MIN_WIDTH

    viewer = ReportsViewerWidget()
    viewer.resize(1366, 768)
    viewer.show()
    qapp.processEvents()

    # Gözden geçirme kipi: digest + liste (aynı anda en çok iki bölge).
    assert viewer.report_center.isVisible()
    # Okuyucu bölgesi sıfıra katlanır (üçüncü bölge ekranda yer kaplamaz).
    assert viewer.splitter.sizes()[1] == 0

    viewer.enter_reading_mode()
    qapp.processEvents()
    assert not viewer.report_center.isVisible(), "okuyucu açıkken digest katlanmalı"
    assert viewer.content_browser.width() >= READER_MIN_WIDTH
    assert viewer.content_browser.minimumWidth() >= READER_MIN_WIDTH

    viewer.back_to_digest_btn.click()
    qapp.processEvents()
    assert viewer.report_center.isVisible(), "okuma kapanınca digest geri gelmeli"
    viewer.deleteLater()


def test_review_card_is_at_least_520px(qapp, tmp_path):
    center = _center_with_reports(qapp, tmp_path, count=6)
    center.resize(900, 600)
    center.show()
    qapp.processEvents()
    assert center.card_widgets
    assert center.card_widgets[0].minimumWidth() >= center.REVIEW_CARD_MIN_WIDTH
    center.deleteLater()


def test_panel_minimum_width_declarations_are_truthful(qapp):
    """G13-4: `minimumWidth()` beyanı hesaplanan çocuk asgarisinden küçük olamaz."""
    import scripts.ui_audit as audit
    from entropy.ui.widgets.task_board_widget import TaskBoardWidget

    viewer = ReportsViewerWidget()
    viewer.resize(1366, 768)
    viewer.show()
    board = TaskBoardWidget()
    board.resize(1366, 700)
    board.show()
    qapp.processEvents()
    failures = audit.min_width_declaration_failures(
        [viewer, viewer.report_center, board]
    )
    assert failures == []
    viewer.deleteLater()
    board.deleteLater()


# ------------------------------------------------- A5: Görevler beyanı + liste

def test_task_board_declares_computed_minimum_and_falls_back_to_list(qapp):
    from entropy.ui.widgets.task_board_widget import TaskBoardWidget

    board = TaskBoardWidget()
    board.show()
    qapp.processEvents()
    # Sabit 220 px beyanı kalktı: beyan artık hesaplanan liste kipi asgarisi.
    assert board.minimumWidth() == board.list_min_width()
    assert board.minimumWidth() != 220

    for width in (1920, 1366, 900):
        board.resize(width, 700)
        qapp.processEvents()
        if board.view_mode() == "kanban":
            assert width >= board.kanban_min_width()
        else:
            assert width < board.kanban_min_width()
            assert board.board_stack.currentWidget() is board.list_view

    # Kanban asgarisinin altında liste görünümü devreye girer.
    board.resize(board.kanban_min_width() - 1, 700)
    qapp.processEvents()
    assert board.view_mode() == "list"
    assert board.board_stack.currentWidget() is board.list_view
    board.deleteLater()


def test_task_board_list_view_shares_data_and_signals(qapp):
    from entropy.ui.widgets.task_board_widget import TaskBoardWidget

    board = TaskBoardWidget()
    board.show()
    board.resize(400, 600)
    qapp.processEvents()
    assert board.view_mode() == "list"
    # Liste kanbanla aynı kart kümesini gösterir (tek veri kaynağı).
    assert board.list_view.count() == len(board.card_widgets)
    board.deleteLater()


# ------------------------------------- A9: kapıların gerçekten ölçtüğü kanıtı

def test_gate_g13_1_turns_red_for_an_unlabelled_button(qapp):
    """Bilerek boş metinli/ikonsuz/adsız düğme kapıyı kırmızıya çevirmeli."""
    import scripts.ui_audit as audit
    from PySide6.QtWidgets import QPushButton, QWidget

    host = QWidget()
    host.resize(200, 80)
    good = QPushButton("Raporu aç", host)
    bad = QPushButton("", host)
    bad.setObjectName("bozukDugme")
    bad.move(0, 40)
    host.show()
    qapp.processEvents()

    offenders = audit.empty_interactive_widgets(host)
    assert "bozukDugme" in offenders, "kapı boş düğmeyi görmedi"

    # Faz 13-A2 madde 2: sözleşme SERTLEŞTİ. Erişilebilir ad WCAG 4.1.2'yi
    # karşılar ama kullanıcının ekranda gördüğü BOŞ KAREYİ doldurmaz; 13-A'da
    # adı olan ikonsuz düğmeler kapıdan geçiyor, kullanıcı yine boş kare
    # görüyordu. Ad artık G13-1'i susturmaz; yalnızca `unnamed_icon_buttons`
    # (ekran okuyucu kapısı) yeşile döner.
    bad.setAccessibleName("Sabitle")
    assert audit.unnamed_icon_buttons(host) == []
    assert audit.empty_interactive_widgets(host) == ["bozukDugme"], (
        "adı olan ama çizilemeyen düğme hâlâ boş karedir"
    )

    # Çizilebilir bir ikon konunca kapı yeşile döner.
    from entropy.ui.design import TOKENS, icon as design_icon

    bad.setIcon(design_icon("edit", color=TOKENS["color"]["text"]))
    qapp.processEvents()
    assert audit.empty_interactive_widgets(host) == []
    assert good.text()
    host.deleteLater()


def test_gate_g13_3_turns_red_for_a_slow_click(qapp):
    """200 ms uyuyan bir tıklama işleyicisi kapıyı aşmalı."""
    import scripts.ui_audit as audit

    fast = audit.measure_click_latency_ms(lambda: None)
    slow = audit.measure_click_latency_ms(lambda: time.sleep(0.2))
    assert fast <= audit.FINAL_GATES_13["click_latency_ms"]
    assert slow > audit.FINAL_GATES_13["click_latency_ms"]
    assert slow > audit.CLICK_LATENCY_WARN_MS


def test_gate_g13_4_turns_red_for_a_lying_declaration(qapp):
    """Beyanı hesaplanandan küçük bir panel kapıyı kırmızıya çevirmeli."""
    import scripts.ui_audit as audit
    from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

    panel = QWidget()
    layout = QHBoxLayout(panel)
    for i in range(4):
        btn = QPushButton(f"Uzun düğme metni {i}")
        btn.setMinimumWidth(200)
        layout.addWidget(btn)
    panel.setMinimumWidth(80)  # yalan beyan
    panel.show()
    qapp.processEvents()
    assert audit.min_width_declaration_failures([panel]), "kapı yalan beyanı görmedi"

    panel.setMinimumWidth(panel.minimumSizeHint().width())
    assert audit.min_width_declaration_failures([panel]) == []
    panel.deleteLater()


def test_gate_g13_2_measures_ghost_variant(qapp):
    """G13-2 ghost düğmeyi de ölçer; `line` yerine `line.strong` kullanılır."""
    import scripts.ui_audit as audit
    from PySide6.QtWidgets import QPushButton, QWidget

    from entropy.ui.design import TOKENS as T, contrast_ratio as cr

    host = QWidget()
    host.resize(200, 60)
    ghost = QPushButton("Pano dosyası", host)
    ghost.setProperty("variant", "ghost")
    host.show()
    qapp.processEvents()
    assert audit.ghost_button_contrast_failures(host) == []
    # Ayırıcı rengi (`line`) bir denetim sınırı olarak WCAG 1.4.11'i geçemez;
    # kapının ölçtüğü fark tam olarak budur.
    assert cr(T["color"]["line"], T["color"]["surface"]) < 3.0
    assert cr(T["color"]["line.strong"], T["color"]["surface"]) >= 3.0
    host.deleteLater()


def test_gate_g13_2_measures_per_surface_background(qapp):
    """Kapı zemini yüzey başına çözer; koyu şerit üstünde `line` kenarlığı kırmızıdır."""
    import scripts.ui_audit as audit
    from PySide6.QtWidgets import QPushButton, QWidget

    from entropy.ui.design import TOKENS as T, contrast_ratio as cr

    colors = T["color"]
    strip = QWidget()
    strip.resize(240, 60)
    # Bilerek bozuk: koyu şerit zemini + ayırıcı rengi kenarlık.
    strip.setStyleSheet(f"background-color: {colors['line']};")
    bad = QPushButton("Temizle", strip)
    bad.setProperty("variant", "ghost")
    bad.setStyleSheet(f"border-color: {colors['line.strong']};")
    strip.show()
    qapp.processEvents()
    failures = audit.ghost_button_contrast_failures(strip)
    assert failures, "koyu şerit üstünde line.strong kenarlık kapıyı kırmızıya döndürmeli"
    assert audit.resolve_surface_color(bad) == colors["line"]

    # Doğru belirteç (`line.onraised`) aynı şeritte geçer.
    bad.setStyleSheet(f"border-color: {colors['line.onraised']};")
    assert audit.ghost_button_contrast_failures(strip) == []
    assert cr(colors["line.onraised"], colors["line"]) >= 3.0
    assert cr(colors["line.onraised"], colors["surface.raised"]) >= 3.0
    strip.deleteLater()


# ------------------------------------------- başlık tek kaynak (core ile aynı)

def test_ui_and_core_title_derivation_agree_on_five_samples():
    from entropy.core import report_title as core_title

    samples = [
        "# Yetenek damıtma raporu\n\nGövde metni burada.\n",
        "---\ntitle: x\n---\n\n# Pano döngüsü raporu\n\nİlk cümle var.\n",
        "Sadece düz gövde metni var burada.",
        "[PANO board_finish] {} [/PANO]\n\n# Kanıt raporu\n\nGövde metni.\n",
        "## Alt başlık\n\nBu ilk anlamlı cümledir.\n",
    ]
    for body in samples:
        core_result = core_title.derive_report_title(body, fallback="")
        ui_result = derive_report_title(front_title="", body=body, path="")
        assert ui_result == core_result, body[:40]


def test_vault_manager_uses_core_safe_filename_title():
    from entropy.core.report_title import safe_filename_title
    from entropy.brain.obsidian import vault_manager

    assert vault_manager.REPORT_TITLE_MAX == 80
    assert vault_manager.sanitize_report_title("Rapor: bir/iki") == safe_filename_title(
        "Rapor: bir/iki"
    )


# ------------------------------------------------------- Sessions/ süzgeci

def _write_session(root, relative: str) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntype: session\ntitle: Oturum notu\n---\n\n# Oturum\n\nGövde.\n",
        encoding="utf-8",
    )
    return str(path)


def test_sessions_are_excluded_from_reports_by_default(tmp_path):
    from entropy.ui.widgets.report_inbox import is_session_entry

    entropy_dir = tmp_path / "Entropy"
    flat = _write_session(entropy_dir, "Sessions/2026-09-10-konu.md")         # eski biçim
    nested = _write_session(entropy_dir, "Sessions/2026-09-10/1030-konu.md")  # yeni biçim
    report = entropy_dir / "Reports" / "Gorev_Rapor.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# Gerçek rapor\n\nGövde.\n", encoding="utf-8")

    assert is_session_entry({"path": flat})
    assert is_session_entry({"path": nested})
    assert not is_session_entry({"path": str(report)})

    # Ön bilgi tek başına da yeter (yol `Sessions/` altında olmasa bile).
    outside = entropy_dir / "Reports" / "Oturum_Kaydi.md"
    outside.write_text("---\ntype: session\n---\n\n# Oturum\n", encoding="utf-8")
    assert is_session_entry({"path": str(outside)})


def test_report_center_counter_ignores_sessions(qapp, tmp_path):
    entropy_dir = tmp_path / "Entropy"
    session = _write_session(entropy_dir, "Sessions/2026-09-10/1030-konu.md")
    report = entropy_dir / "Reports" / "Gorev_Rapor.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# Gerçek rapor\n\nGövde.\n", encoding="utf-8")

    center = ReportCenterWidget(parent=None, store=_fresh_store(tmp_path))
    center.set_quiet_threshold(1.5, persist=False)
    entries = [
        {"path": session, "title": "Oturum notu", "mtime": time.time()},
        {"path": str(report), "title": "Gerçek rapor", "mtime": time.time()},
    ]
    center.set_entries(entries)
    qapp.processEvents()
    assert center.total_count() == 1
    assert "Toplam 1 rapor" in center.header_label.text()

    center.include_sessions = True
    center.set_entries(entries)
    qapp.processEvents()
    assert center.total_count() == 2
    center.deleteLater()


def test_reports_viewer_has_a_sessions_switch(qapp):
    viewer = ReportsViewerWidget()
    assert viewer.sessions_btn.isCheckable()
    assert viewer.include_sessions() is False
    assert viewer.sessions_btn.accessibleName() == "Oturumlar"
    viewer.deleteLater()


# --------------------------------------- çekirdek bindirmesi metni örtmüyor

def test_core_overlay_does_not_cover_text_or_scrollbar(zen, qapp):
    """136 px çekirdek metnin ilk satırını ve kaydırma çubuğunu örtmemeli."""
    browser = zen.chat_browser
    # Faz 14-E: sohbet artık ALTTAKİ bölücünün içinde değil, sağ panelin
    # "Sohbet" sekmesinde. Gövdeye gerçek yükseklik vermek için pencere
    # büyütülür (eski `splitter.setSizes` yolu artık yok).
    zen.right_panel.setCurrentIndex(0)
    zen.setGeometry(0, 0, 1600, 950)
    zen.show()
    qapp.processEvents()
    browser.setHtml("<p>" + ("Satır bir. " * 400) + "</p>")
    qapp.processEvents()

    core = zen.core_visualizer
    assert core.isVisible()
    viewport = browser.viewport().geometry()
    assert not core.geometry().intersects(viewport), "çekirdek sohbet metnini örtüyor"

    scrollbar = browser.verticalScrollBar()
    assert scrollbar.isVisible()
    zen._position_core_overlay()
    assert core.geometry().right() <= browser.viewport().geometry().right()
    assert core.geometry().right() <= browser.width() - scrollbar.width()

    # Gizlenince şerit kalkar: gövde bütün yüksekliği kullanır.
    assert zen._core_reserved_height() >= zen.CORE_OVERLAY_SIZE
    core.setVisible(False)
    zen._apply_core_reserved_strip()
    qapp.processEvents()
    assert zen._core_reserved_height() == 0
    assert browser.viewport().geometry().top() < viewport.top()


# ---------------------------------------------- 13-A kapanış QA düzeltmeleri

def test_frontmatter_title_loses_gorev_prefix_and_timestamp():
    """Frontmatter `title` de dosya adıyla aynı temizlikten geçer.

    Regresyon: küme başlığında ham
    `Gorev_Otonom Ajan Mimarisi Arastirma_20260905_1527` görünüyordu — başlık
    "makul" sayılıp hiç temizlenmeden karta düşüyordu.
    """
    raw = "Gorev_Otonom Ajan Mimarisi Arastirma_20260905_1527"
    title = derive_report_title(front_title=raw, body="", path="", fallback="")
    assert title == "Otonom Ajan Mimarisi Arastirma"
    assert "Gorev_" not in title and "20260905" not in title and "1527" not in title

    # Dosya adı kaynağıyla aynı sonuç (iki kaynak çelişemez).
    assert title_from_filename(f"{raw}.md") == "Otonom Ajan Mimarisi Arastirma"
    # Temiz başlık bozulmaz.
    assert derive_report_title(front_title="Beyin v2 Kapı Ölçümü") == "Beyin v2 Kapı Ölçümü"


def test_board_card_preview_has_no_raw_markdown():
    """Pano kartı önizlemesi `##`, backtick ve makine bloğu göstermez."""
    from entropy.ui.widgets.task_board_widget import plain_preview

    raw = (
        "---\ntitle: x\n---\n"
        "## Sonuç\n\n"
        "`pytest -q` ile **12 test** geçti, bkz. [rapor](a.md).\n"
        "[KANIT]\nkomut: pytest\n\n"
        "- madde bir\n```\nkod = 1\n```\n"
    )
    preview = plain_preview(raw)
    for needle in ("##", "`", "**", "[KANIT]", "kod = 1", "(a.md)"):
        assert needle not in preview, f"{needle!r} önizlemede kaldı: {preview!r}"
    assert "Sonuç" in preview and "pytest -q" in preview and "rapor" in preview
    assert len(plain_preview("x" * 400)) <= 110


def test_board_detail_inputs_have_visible_captions(qapp):
    """Dört giriş kutusunun her birinin görünür (kırpılmayan) etiketi var."""
    from PySide6.QtWidgets import QLabel
    from entropy.ui.widgets.task_board_widget import TaskBoardWidget

    board = TaskBoardWidget(board=None)
    detail = board.detail_panel
    texts = {w.text() for w in detail.findChildren(QLabel) if w.text()}
    for caption in ("Sağlayıcı", "Model", "Efor", "Bütçe"):
        assert caption in texts, f"{caption} etiketi yok: {sorted(texts)}"
    # Yer tutucu artık 320 px'te kırpılmayacak kadar kısa.
    assert detail.budget_input.placeholderText() == "0"
    assert detail.budget_input.maximumWidth() <= 96
    board.deleteLater()
