"""Faz 8 — pencere davranışı, üst çubuk sığması ve rapor sayacı.

Kullanıcının v0.5.1 exe'sinde bildirdiği üç sorunu sabitler:

1. Zen çerçevesizdi ama taşınamıyor/boyutlandırılamıyordu ve açılışta
   kullanılabilir alanın yalnızca %92'sini kaplıyordu (ölçülen 1766x949).
2. Chat üst çubuğu tek satırlık ~2440 px'lik bir şeritti; yatay kaydırma
   alanı içinde olduğu için Zen düğmesi ve rozetler görünmüyordu.
3. Rapor Merkezi `reload_from_vault()` sonrası 895 raporu 61'e düşürüyordu ve
   toplam sayaç "Toplam" ibaresi taşımıyordu.

Ek: Chat kapanış yolundaki tekrarlı `disconnect` çağrıları RuntimeWarning
üretiyordu (ölçülen 526).
"""

import warnings

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------- 1) pencere

def test_maximize_window_to_screen_uses_full_available_area(app):
    from entropy.ui.window_sizing import available_geometry, maximize_window_to_screen

    win = QWidget()
    win.setGeometry(10, 10, 400, 300)
    geom = maximize_window_to_screen(win, min_size=(300, 200))
    assert geom == available_geometry()


def test_clamp_window_into_screen_pulls_offscreen_window_back(app):
    from entropy.ui.window_sizing import available_geometry, clamp_window_into_screen

    area = available_geometry()
    win = QWidget()
    win.setMinimumSize(1, 1)
    win.setGeometry(area.x() + area.width() + 800, area.y() + area.height() + 800, 400, 300)
    target = clamp_window_into_screen(win)
    assert area.contains(QRect(target)), (target, area)


def test_frameless_helper_toggles_maximize(app):
    from entropy.ui.widgets.frameless import FramelessWindowHelper

    win = QWidget()
    handle = QWidget(win)
    helper = FramelessWindowHelper(win, handle=handle)
    win.show()
    helper.toggle_maximize()
    assert win.isMaximized()
    helper.toggle_maximize()
    assert not win.isMaximized()
    win.close()


def test_zen_window_is_movable_and_has_window_controls(app):
    from entropy.core.config import config
    from entropy.core.provider import create_bridge
    from entropy.ui.modes.zen_mode import ZenModeWindow

    zen = ZenModeWindow(bridge=create_bridge(config))
    # Taşıma/boyutlandırma yardımcısı ve üst çubuk tutamacı var mı?
    assert zen.frameless.handle is zen.header_frame
    # Küçült / maksimize / kapat üçlüsü.
    assert zen.btn_minimize.isEnabled() and zen.btn_maximize.isEnabled()
    assert callable(zen.toggle_maximize)
    zen.close()


def test_zen_opens_maximized_to_available_area(app):
    from entropy.core.config import config
    from entropy.core.provider import create_bridge
    from entropy.ui.modes.zen_mode import ZenModeWindow
    from entropy.ui.window_sizing import available_geometry

    zen = ZenModeWindow(bridge=create_bridge(config))
    area = available_geometry()
    # Faz 6'da %92 (ör. 1766x949) idi; artık alanın tamamı.
    assert zen.width() >= area.width() - 2
    assert zen.height() >= area.height() - 2
    zen.close()


# ------------------------------------------------------- 2) üst çubuk sığması

def test_flow_layout_minimum_is_widest_item_not_the_sum(app):
    from PySide6.QtWidgets import QPushButton

    from entropy.ui.widgets.flow_layout import FlowHeaderFrame

    frame = FlowHeaderFrame(margins=(0, 0, 0, 0))
    flow = frame.flow()
    for i in range(10):
        flow.addWidget(QPushButton("düğme %d" % i, frame))
    # Toplam ~800 px olsa da minimum tek öğe kadar kalır.
    assert flow.minimumSize().width() < 200


def test_chat_minimum_size_hint_fits_1000px(app):
    from entropy.core.config import config
    from entropy.core.provider import create_bridge
    from entropy.ui.modes.chat_mode import ChatModeWindow

    win = ChatModeWindow(bridge=create_bridge(config))
    assert win.minimumSizeHint().width() <= 1000
    win.close()


@pytest.mark.parametrize("width", [1000, 1280, 1366])
def test_chat_header_items_stay_inside_window(app, width):
    from entropy.core.config import config
    from entropy.core.provider import create_bridge
    from entropy.ui.modes.chat_mode import ChatModeWindow

    win = ChatModeWindow(bridge=create_bridge(config))
    win.setGeometry(0, 0, width, 720)
    win.show()
    app.processEvents()
    app.processEvents()

    header = win.header_frame
    flow = header.flow()
    overflowing = []
    for i in range(flow.count()):
        item = flow.itemAt(i)
        widget = item.widget()
        if widget is None or widget.isHidden():
            continue
        geom = widget.geometry()
        if geom.right() > header.width() or geom.bottom() > header.height():
            overflowing.append((type(widget).__name__, geom))
    assert not overflowing, overflowing
    win.close()


def test_chat_zen_button_exists_and_is_laid_out(app):
    """Kullanıcı "Zen düğmesi görünmüyor" dedi: düğme çubuğun içinde olmalı."""
    from PySide6.QtWidgets import QPushButton

    from entropy.core.config import config
    from entropy.core.provider import create_bridge
    from entropy.ui.modes.chat_mode import ChatModeWindow

    win = ChatModeWindow(bridge=create_bridge(config))
    win.setGeometry(0, 0, 1000, 720)
    win.show()
    app.processEvents()
    zen_buttons = [
        b for b in win.header_frame.findChildren(QPushButton) if "Zen" in b.text()
    ]
    assert zen_buttons, "Chat üst çubuğunda Zen düğmesi yok"
    btn = zen_buttons[0]
    assert btn.geometry().right() <= win.header_frame.width()
    win.close()


def test_zen_header_wraps_instead_of_scrolling(app):
    from entropy.core.config import config
    from entropy.core.provider import create_bridge
    from entropy.ui.modes.zen_mode import ZenModeWindow

    zen = ZenModeWindow(bridge=create_bridge(config))
    zen.setGeometry(0, 0, 1366, 768)
    zen.show()
    app.processEvents()
    # Faz 6'nin yatay kaydırma alanı kaldırıldı.
    assert not hasattr(zen, "header_scroll")
    assert zen.header_frame.height() >= zen.header_frame.heightForWidth(zen.width() - 24) - 4
    zen.close()


# ------------------------------------------------------------ 3) rapor sayacı

def test_report_center_reload_keeps_full_vault(app):
    """`reload_from_vault()` künye sayısını 60'a düşürmemeli."""
    from entropy.ui.widgets.report_center import ReportCenterWidget

    center = ReportCenterWidget()
    assert center.VAULT_RELOAD_LIMIT >= 1000

    entries = [
        {"path": f"/tmp/rapor_{i}.md", "title": f"Rapor {i}", "kind": "report"}
        for i in range(300)
    ]
    center.set_entries(entries)
    # Gercek posta kutusu kunyeleri de eklenebilir; onemli olan 60'a
    # dusurulmemesi.
    assert center._result["total"] >= 300


def test_report_center_header_shows_total_counter(app):
    from entropy.ui.widgets.report_center import ReportCenterWidget

    center = ReportCenterWidget()
    center.set_entries([
        {"path": f"/tmp/r{i}.md", "title": f"R{i}", "kind": "report"} for i in range(12)
    ])
    text = center.header_label.text()
    total = center._result["total"]
    assert f"Toplam {total} rapor" in text and total >= 12
    assert "öne çıkan" in text and "sessiz" in text


def test_report_center_show_all_button_reaches_full_list(app):
    from entropy.ui.widgets.report_center import ReportCenterWidget

    center = ReportCenterWidget()
    center.set_entries([
        {"path": f"/tmp/r{i}.md", "title": f"R{i}", "kind": "report"} for i in range(40)
    ])
    assert center.show_all_btn.isVisibleTo(center)
    assert f"({center._result['total']} rapor)" in center.show_all_btn.text()

    seen = []
    center.show_all_requested.connect(lambda: seen.append(True))
    center._quiet_expanded = False
    center._on_show_all_clicked()
    assert center._quiet_expanded is True
    assert seen == [True]


def test_reports_viewer_show_all_resets_filters(app):
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    viewer = ReportsViewerWidget()
    viewer.search_input.setText("bulunmayan-bir-arama-metni")
    app.processEvents()
    viewer.show_all_reports()
    assert viewer.search_input.text() == ""
    assert viewer.filter_combo.currentIndex() == 0
    assert viewer.list_widget.count() >= 1


# ------------------------------------------------- 4) kapanış uyarıları (0 olmalı)

def test_chat_close_emits_no_disconnect_warnings(app):
    from entropy.core.config import config
    from entropy.core.provider import create_bridge
    from entropy.ui.modes.chat_mode import ChatModeWindow

    win = ChatModeWindow(bridge=create_bridge(config))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(5):
            win.close()
    failed = [w for w in caught if "disconnect" in str(w.message).lower()]
    assert not failed, [str(w.message) for w in failed]
