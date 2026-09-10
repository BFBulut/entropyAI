"""Faz 7 — Zen sol rapor panelinin dar genişlikte kırpılmaması (kozmetik denetim).

Sorun: Rapor Merkezi / Gelen şeridi / okuyucu araç çubuğu içindeki zengin metin
etiketleri ve düğmeler, örtük `minimumSizeHint` üzerinden `ReportsViewerWidget`
minimumunu ~1420 px'e çıkarıyordu. Zen sol sekmesi için `setMinimumWidth(220)`
verilmiş olmasına rağmen QSplitter çocuğu bu örtük minimumun altına indiremediği
için panel araç çubukları kırpılıyor, düzen 1920 px'lik ekranda taşıyordu.

Bu testler minimumun küçük ve öngörülebilir kalmasını sabitler.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_reports_viewer_minimum_width_fits_narrow_zen_panel(app):
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    viewer = ReportsViewerWidget()
    viewer.show()
    # 1420 -> ~400. Zen sol sütunu 460 px ile açılıyor; sınır bunun altında olmalı.
    assert viewer.minimumSizeHint().width() <= 460


def test_report_center_and_inbox_declare_small_explicit_minimums(app):
    from entropy.ui.widgets.report_center import ReportCenterWidget
    from entropy.ui.widgets.report_inbox import ReportInboxStrip

    center = ReportCenterWidget()
    strip = ReportInboxStrip()
    # Açık minimum, uzun etiketlerin ürettiği örtük minimumu ezer.
    assert center.minimumWidth() <= 260
    assert strip.minimumWidth() <= 260


def test_reader_toolbar_can_shrink(app):
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    viewer = ReportsViewerWidget()
    viewer.show()
    assert viewer.rag_status_bar.minimumWidth() <= 220


def test_narrow_resize_keeps_toolbar_widgets_inside_panel(app):
    """Panel 300 px'e daraltıldığında araç çubuğu düğmeleri panel dışına taşmaz."""
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    viewer = ReportsViewerWidget()
    viewer.resize(300, 700)
    viewer.show()
    app.processEvents()
    # Düzeltme öncesi taban ~1420 px'di; şimdi ~389 px (üst başlık satırı +
    # okuyucu bölünmesinin gerçek minimumu). Zen sol sütunu 460 px açıldığı için
    # bu sınır kırpılmayı önlüyor.
    assert viewer.width() <= 400, "panel istenen genişliğe inemedi"
    for btn in (viewer.btn_read_report, viewer.btn_open_standalone):
        assert btn.geometry().right() <= viewer.width() + 2, f"{btn.text()} panel dışına taştı"
