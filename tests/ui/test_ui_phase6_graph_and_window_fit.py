"""Faz 6: bilgi grafiği görünümü, pencere sığdırma ve efor seçici testleri.

Grafik JS'i burada çalıştırılmaz (Node harness'i `scratch/ui/phase6/` altında);
buradaki testler JS şablonunun sözleşmesini (fonksiyon/eşik varlığı) ve Python
tarafındaki davranışı doğrular.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from entropy.ui.widgets import knowledge_graph as kg
from entropy.ui.window_sizing import fitted_geometry


# --------------------------------------------------------------------------
# 1. Grafik şablonu: kademeli detay, izolasyon, sığdırma kancaları
# --------------------------------------------------------------------------

def test_graph_template_has_progressive_detail_machinery():
    tpl = kg.GRAPH_HTML_TEMPLATE
    for token in (
        "STRUCTURAL_GROUPS",
        "DETAIL_ZOOM",
        "function isDetailShown",
        "function toggleBranchExpansion",
        "function syncDetailState",
    ):
        assert token in tpl, f"şablonda eksik: {token}"


def test_graph_template_isolation_is_selection_based():
    tpl = kg.GRAPH_HTML_TEMPLATE
    assert "function setSelectedNode" in tpl
    assert "function computeBranchSet" in tpl
    assert "function recomputeIsolation" in tpl
    # isNodeVisible izolasyon kümesine bakmalı: 👁️ artık kapsamdan bağımsız çalışır.
    body = tpl.split("function isNodeVisible", 1)[1][:400]
    assert "isolatedIds" in body


def test_graph_template_zoom_goes_through_single_gate():
    tpl = kg.GRAPH_HTML_TEMPLATE
    assert "function applyZoom" in tpl
    assert "applyZoom(zoom * 1.25" in tpl   # + düğmesi
    assert "applyZoom(zoom / 1.25" in tpl   # - düğmesi
    assert "applyZoom(zoom * zoomFactor" in tpl  # tekerlek
    # ⟲ önce ölçüyü tazeler, sonra sığdırır.
    reset = tpl.split("function resetView", 1)[1][:220]
    assert "updateDimensions()" in reset and "fitToView()" in reset


def test_graph_widget_refits_on_show_and_resize(qtbot=None):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    widget = kg.KnowledgeGraphWidget()
    calls = []
    widget._run_js = lambda script: calls.append(script) or True

    from PySide6.QtGui import QResizeEvent, QShowEvent
    from PySide6.QtCore import QSize
    widget.showEvent(QShowEvent())
    widget.resizeEvent(QResizeEvent(QSize(800, 600), QSize(400, 300)))
    widget._apply_view_fit()

    assert any("updateDimensions" in c and "fitToView" in c for c in calls)

    calls.clear()
    widget.select_node("hub-skills")
    assert any("setSelectedNode" in c and "hub-skills" in c for c in calls)

    calls.clear()
    widget._on_isolate_toggled(True)
    assert calls == ["setIsolationMode(true);"]


# --------------------------------------------------------------------------
# 2. Pencere sığdırma matematiği (1920x1080 ve 1366x768)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("area_w,area_h", [(1920, 1040), (1366, 728)])
def test_fitted_geometry_stays_inside_available_area(area_w, area_h):
    area = QRect(0, 0, area_w, area_h)
    geom = fitted_geometry(area, ratio=0.92, min_size=(1100, 680))
    assert geom.width() <= int(area_w * 0.92)
    assert geom.height() <= int(area_h * 0.92)
    assert area.contains(geom), f"{geom} alan dışına taştı"


def test_fitted_geometry_clamps_minimum_on_small_screens():
    # Ekran asgari boyuttan küçükse pencere yine de ekranı aşmaz.
    area = QRect(0, 0, 900, 600)
    geom = fitted_geometry(area, ratio=0.92, min_size=(1100, 680))
    assert geom.width() <= 900 and geom.height() <= 600


def test_fitted_geometry_is_centered_on_secondary_screen_origin():
    area = QRect(1920, 0, 1366, 728)
    geom = fitted_geometry(area, ratio=0.88, min_size=(900, 560))
    assert geom.x() >= 1920
    assert area.contains(geom)


def test_desk_window_uses_screen_ratio_constant():
    from entropy.desk import window as desk_window
    # Faz 7: tek monitörde Desk ekranın sağ YARISINI kaplar (%50 genişlik);
    # ikinci monitör varsa orada %88.
    assert desk_window.DESK_SCREEN_RATIO == pytest.approx(0.5)
    assert desk_window.DESK_SECONDARY_RATIO == pytest.approx(0.88)
    assert desk_window.DESK_MIN_SIZE[0] <= 1366
    assert desk_window.DESK_MIN_SIZE[1] <= 728


def test_zen_and_chat_minimums_fit_1366x768():
    from entropy.ui.modes.zen_mode import ZEN_MIN_SIZE
    from entropy.ui.modes.chat_mode import CHAT_MIN_SIZE
    assert ZEN_MIN_SIZE[0] <= 1366 and ZEN_MIN_SIZE[1] <= 728
    assert CHAT_MIN_SIZE[0] <= 1366 and CHAT_MIN_SIZE[1] <= 728


# --------------------------------------------------------------------------
# 3. Efor seçici
# --------------------------------------------------------------------------

class _BridgeWithEffort:
    provider_name = "agy"
    selected_effort = "medium"

    def __init__(self):
        self.applied = []

    def effort_levels(self):
        return ["low", "medium", "high"]

    def set_effort(self, level):
        self.applied.append(level)
        self.selected_effort = level


class _BridgeWithoutEffort:
    provider_name = "other"


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_effort_selector_reflects_and_persists_selection():
    from PySide6.QtWidgets import QHBoxLayout
    from entropy.ui.widgets.effort_selector import install_effort_selector

    _app()
    host = QWidget()
    layout = QHBoxLayout(host)
    bridge = _BridgeWithEffort()
    combo = install_effort_selector(layout, bridge, host)

    assert combo is not None
    assert [combo.itemText(i) for i in range(combo.count())] == ["low", "medium", "high"]
    assert combo.currentText() == "medium"

    combo.setCurrentText("high")
    assert bridge.applied == ["high"]
    assert bridge.selected_effort == "high"


def test_effort_selector_hidden_when_bridge_lacks_contract():
    from PySide6.QtWidgets import QHBoxLayout
    from entropy.ui.widgets.effort_selector import install_effort_selector

    _app()
    host = QWidget()
    layout = QHBoxLayout(host)
    assert install_effort_selector(layout, _BridgeWithoutEffort(), host) is None
    assert layout.count() == 0
