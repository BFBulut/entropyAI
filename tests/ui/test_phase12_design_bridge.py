"""Faz 12-D.2 — gömülü belge tema köprüsü, yoğunluk, kalıcılık, birleşik pano.

Kaynak: `docs/reports/2026-09-10_Faz12_Arastirma_D_Arayuz_Tasarim_Denetimi.md`
(D12-01…D12-09) ve `skills/ui-design/SKILL.md` 1.1.0 §0.8-0.10, §6.

Her test bir sözleşmeyi kilitler. Ölçüm mantığının tek kaynağı
`scripts/ui_audit.py`'dir (iddia değil ölçüm). Model çağrısı yok; hepsi
`QT_QPA_PLATFORM=offscreen` altında koşar.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QTextBrowser  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import ui_audit  # noqa: E402

from entropy.ui.design import prefs  # noqa: E402
from entropy.ui.design.embedded import (  # noqa: E402
    EMBEDDED_CONTRAST_REQUIREMENTS,
    css_variables,
    js_palette_json,
    palette,
)
from entropy.ui.design.tokens import chroma, contrast_ratio  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from entropy.ui.design import apply_design_system

    application = QApplication.instance() or QApplication([])
    apply_design_system(application)
    yield application


@pytest.fixture
def isolated_settings(tmp_path):
    """Her test kendi INI dosyasını kullanır — gerçek kullanıcı ayarı okunmaz."""
    ini = tmp_path / "entropy_ui.ini"

    def factory():
        return QSettings(str(ini), QSettings.Format.IniFormat)

    prefs.set_settings_factory(factory)
    yield ini
    prefs.set_settings_factory(None)


@pytest.fixture(scope="module")
def metrics():
    data = ui_audit.static_metrics(ui_audit.DEFAULT_PATHS)
    desk = ui_audit.static_metrics(["src/entropy/desk"])
    data["embedded_hex"] = sorted(set(data["embedded_hex"]) | set(desk["embedded_hex"]))
    data["pure_spectrum_colors"] = sorted(
        set(data["pure_spectrum_colors"]) | set(desk["pure_spectrum_colors"])
    )
    data["arrow_glyphs"] += desk["arrow_glyphs"]
    data.update(ui_audit.token_metrics())
    data.update(ui_audit.persistence_metrics())
    return data


# --------------------------------------------------------- 1. tema köprüsü


def test_no_plain_hex_in_embedded_bodies(metrics):
    """Gömülü HTML/SVG/JS gövdelerinde düz onaltılık renk kalmadı (D12-04/05)."""
    assert metrics["embedded_hex"] == [], metrics["embedded_hex"][:20]


def test_no_pure_spectrum_colors(metrics):
    """Kroma 255 ("neon" imzası) hiçbir katmanda yok."""
    assert metrics["pure_spectrum_colors"] == [], metrics["pure_spectrum_colors"]


def test_embedded_palette_meets_contrast_in_both_themes(metrics):
    """Gömülü palet WCAG 1.4.3 (4,5) ve 1.4.11 (3,0) eşiklerini karşılar."""
    assert metrics["embedded_contrast_failures"] == [], (
        metrics["embedded_contrast_failures"]
    )
    for theme in ("dark", "light"):
        p = palette(theme)
        for fg, bg, threshold in EMBEDDED_CONTRAST_REQUIREMENTS:
            ratio = contrast_ratio(p[fg], p[bg])
            assert ratio >= threshold, f"{theme}:{fg}/{bg}={ratio:.2f}"


def test_embedded_palette_is_low_chroma():
    """`viz.*` serisi düşük kromalı kalır (tasarım sistemi §0.4)."""
    for theme in ("dark", "light"):
        for color in palette(theme)["series"]:
            assert chroma(color) < 255, color


def test_markdown_svg_uses_tokens_and_is_fluid():
    """Mermaid SVG'si belirteç rengi kullanır ve okuma genişliğine sığar."""
    from entropy.ui.widgets.markdown_renderer import (
        MermaidSvgGenerator, set_reader_width,
    )

    p = palette()
    set_reader_width(460)
    svg = MermaidSvgGenerator.render_to_svg("graph TD\nA[Bir]-->B[İki]")
    assert p["surface"] in svg and p["accent"] in svg
    m = re.search(r'width="(\d+)" height="(\d+)" viewBox="0 0 (\d+) (\d+)"', svg)
    assert m, svg[:200]
    render_w, logical_w = int(m.group(1)), int(m.group(3))
    assert render_w <= 460, render_w
    assert logical_w >= render_w  # viewBox mantıksal koordinatı korur


def test_reading_css_wraps_code_blocks():
    """`<pre>` sarar, görsel/SVG kutuya sığar (D12-09)."""
    from entropy.ui.themes.cyber_theme import reading_css

    css = reading_css()
    assert "pre-wrap" in css
    assert "max-width: 100%" in css


def test_graph_canvas_injects_viz_palette():
    """Graf tuvali `:root` değişkenlerini ve JS paletini enjekte eder (D12-05)."""
    from entropy.ui.widgets.knowledge_graph import (
        GRAPH_HTML_TEMPLATE, GRAPH_TEMPLATE_SOURCE, graph_html_template,
    )

    # Ham şablonda tek bir düz renk yok; renk yalnızca enjeksiyonla gelir.
    assert "__VIZ_CSS__" in GRAPH_TEMPLATE_SOURCE
    assert "const VIZ = __VIZ_JSON__;" in GRAPH_TEMPLATE_SOURCE
    assert not re.search(r"#[0-9a-fA-F]{6}\b", GRAPH_TEMPLATE_SOURCE)

    assert "--viz-accent:" in GRAPH_HTML_TEMPLATE
    assert css_variables() in GRAPH_HTML_TEMPLATE
    assert js_palette_json() in GRAPH_HTML_TEMPLATE
    p = palette()
    assert p["accent"] in GRAPH_HTML_TEMPLATE
    assert p["series"][0] in GRAPH_HTML_TEMPLATE

    # Tema değişince tuval paleti yeniden üretilir (yeniden yükleme gerekmez).
    assert palette("light")["accent"] in graph_html_template("light")


def test_embedded_reader_has_no_horizontal_scroll(app):
    """1366 ve 460 px'te gömülü belge yatay kaydırma üretmez (D12-09)."""
    from entropy.ui.widgets.markdown_renderer import render_markdown_to_html

    sample = (
        "# Başlık\n\n```python\n" + "x = " + "1234567890" * 24 + "\n```\n\n"
        "```mermaid\ngraph TD\nA[Uzun bir düğüm adı]-->B[İkinci düğüm]\n```\n"
    )
    for width in (1366, 460):
        browser = QTextBrowser()
        browser.resize(width, 600)
        browser.setHtml(render_markdown_to_html(sample, reader_width=width))
        app.processEvents()
        assert browser.document().idealWidth() <= browser.viewport().width() + 1, width
        browser.deleteLater()


# ------------------------------------------------------------- 2. yoğunluk


@pytest.fixture(scope="module")
def zen(app):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.zen_mode import ZenModeWindow

    win = ZenModeWindow(bridge=AgyProcessBridge())
    win.resize(1366, 768)
    win.show()
    app.processEvents()
    yield win
    win.close()


def test_telemetry_strip_is_gone(zen):
    """Merkez telemetri rozetleri ekranda YOK; nesneler yönlendirildi (D12-02)."""
    for name in ("badge_memory", "badge_skills", "badge_mcp", "badge_model",
                 "zen_telemetry_status"):
        widget = getattr(zen, name, None)
        assert widget is not None, f"{name} kaldırılmamalı (yönlendirme)"
        assert not widget.isVisible(), f"{name} hâlâ ekranda"


def test_header_leaf_widget_count(zen, app):
    """Üst çubuk kapısı beyana değil canlı yaprak sayımına bakar (D12-06)."""
    from PySide6.QtWidgets import QWidget

    header = zen.header_frame
    controls = zen.window_controls
    # Faz 14-E: bölüm şeridi (`navStrip`) üst çubuğun "öğesi" değil, pencere
    # denetimleriyle aynı statüde AYRI bir gruptur ve kendi kapısıyla ölçülür
    # (`nav_strip_violations`, `tests/ui/test_phase14e_layout.py`). Kapı
    # gevşetilmedi: çubuğun kendi yaprak sayımı hâlâ ≤ 6.
    strip = zen.nav_strip
    leaves = [
        w for w in header.findChildren(QWidget)
        if w.isVisibleTo(header) and not w.findChildren(QWidget)
        and not (w is controls or controls.isAncestorOf(w))
        and not (w is strip or strip.isAncestorOf(w))
    ]
    assert len(leaves) <= 6, [type(w).__name__ for w in leaves]


def test_visible_control_density_under_gate(zen, app):
    """1366×768'de aynı anda görünen denetim sayısı ≤ 90 (D12-01)."""
    from PySide6.QtWidgets import (
        QAbstractButton, QComboBox, QLabel, QLineEdit, QSlider, QWidget,
    )

    count = 0
    for child in zen.findChildren(QWidget):
        if not child.isVisible() or child.visibleRegion().isEmpty():
            continue
        if isinstance(child, (QAbstractButton, QComboBox, QLineEdit, QSlider)):
            count += 1
        elif isinstance(child, QLabel) and child.text().strip():
            count += 1
    assert count <= 90, count


def test_report_counter_has_single_source(app):
    """Rapor sayacı tek kaynak: okuyucu Rapor Merkezi'nin sayısını okur (D12-03)."""
    from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

    viewer = ReportsViewerWidget()
    assert viewer.total_report_count() == viewer.report_center.total_count()
    label = viewer.list_count_lbl.text()
    assert str(viewer.report_center.total_count()) in label
    viewer.deleteLater()


def test_audit_script_exposes_new_gates():
    """Yeni kapı alanları betikte tanımlı (kapı beyanı değil, ölçüm)."""
    for key in ("embedded_hex", "embedded_contrast_failures", "pure_spectrum_colors",
                "arrow_glyphs", "splitters_unpersisted",
                "interactive_count_zen_1366", "header_leaf_widgets",
                "embedded_h_overflow"):
        assert key in ui_audit.FINAL_GATES_12D2, key
    assert ui_audit.FINAL_MIN_GATES["themes_reachable"] == 4


# ------------------------------------------------- 3. tema/yoğunluk + kalıcılık


def test_settings_dialog_fields_and_persistence(app, isolated_settings):
    """Ayarlar diyaloğu tema/yoğunluk + karar eşiklerini kalıcılaştırır."""
    from entropy.ui.widgets.settings_dialog import SettingsDialog

    class FakeConfig:
        brain_confidence_threshold = 0.40
        amplification_lock = True
        board_auto_dispatch = True
        agent_session_max_cards = 3
        agent_session_max_tokens = 60000
        saved = False

        def save_settings(self):
            type(self).saved = True

    cfg = FakeConfig()
    dialog = SettingsDialog(config=cfg)
    assert dialog.theme_combo.count() == 2
    assert dialog.density_combo.count() == 2
    assert dialog.confidence_slider is not None
    assert dialog.confidence_slider.minimum() == 20
    assert dialog.confidence_slider.maximum() == 60
    assert dialog.lock_check is not None
    assert dialog.auto_dispatch_check is not None
    assert dialog.max_cards_spin is not None and dialog.max_tokens_spin is not None

    dialog.theme_combo.setCurrentIndex(1)          # light
    dialog.density_combo.setCurrentIndex(1)        # comfortable
    dialog.confidence_slider.setValue(55)
    dialog.lock_check.setChecked(False)
    dialog.auto_dispatch_check.setChecked(False)
    dialog.max_cards_spin.setValue(7)
    data = dialog.apply()

    assert data["ui_theme"] == "light" and data["ui_density"] == "comfortable"
    assert prefs.ui_theme() == "light"
    assert prefs.ui_density() == "comfortable"
    assert abs(cfg.brain_confidence_threshold - 0.55) < 1e-9
    assert cfg.amplification_lock is False
    assert cfg.board_auto_dispatch is False
    assert cfg.agent_session_max_cards == 7
    assert FakeConfig.saved is True
    dialog.deleteLater()
    # Tema geri alınır ki sonraki testler koyu temayla ölçsün.
    prefs.set_ui_theme("dark")
    prefs.set_ui_density("compact")


def test_settings_dialog_survives_missing_config_fields(app, isolated_settings):
    """12-B alanları henüz yoksa diyalog yine açılır (guard)."""
    from entropy.ui.widgets.settings_dialog import SettingsDialog

    class Bare:
        pass

    dialog = SettingsDialog(config=Bare())
    assert dialog.confidence_slider is None
    assert dialog.lock_check is None
    assert dialog.values()["ui_theme"] in ("dark", "light")
    dialog.deleteLater()


def test_splitter_positions_persist(app, isolated_settings):
    """Bölücü konumu QSettings'e yazılır ve geri yüklenir (D12-07)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSplitter, QWidget

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(QWidget())
    splitter.addWidget(QWidget())
    splitter.resize(400, 100)
    splitter.setSizes([120, 280])
    prefs.save_splitter("test.split", splitter)

    other = QSplitter(Qt.Orientation.Horizontal)
    other.addWidget(QWidget())
    other.addWidget(QWidget())
    other.resize(400, 100)
    assert prefs.restore_splitter("test.split", other) is True
    # Qt boyutları tutamaç genişliğine göre yeniden ölçekler; oran korunur.
    sizes = other.sizes()
    assert len(sizes) == 2
    assert abs(sizes[0] / sum(sizes) - 120 / 400) < 0.02, sizes

    prefs.reset_layout(["test.split"])
    fresh = QSplitter(Qt.Orientation.Horizontal)
    fresh.addWidget(QWidget())
    fresh.addWidget(QWidget())
    assert prefs.restore_splitter("test.split", fresh) is False


def test_every_splitter_is_persisted(metrics):
    """Her `QSplitter` kalıcılık yardımcısına bağlı (skill §0.9)."""
    assert metrics["splitters_unpersisted"] == 0, metrics
    assert metrics["themes_reachable"] == 4


# --------------------------------------------------------- 4. birleşik pano


def test_office_cards_panel_is_read_only_and_filters_entropy(app):
    """Ofis kartları bölmesi salt okunur; Entropy kartları görünmez."""
    from entropy.ui.widgets.office_cards_panel import OfficeCardsPanel

    class Card:
        def __init__(self, cid, office, title, status="running", agent="ali"):
            self.id, self.office, self.title = cid, office, title
            self.status, self.agent = status, agent

    class FakeBoard:
        def __init__(self):
            self.calls = []

        def list(self, office=None, **kwargs):
            self.calls.append(office)
            return [
                Card("c1", "entropy", "Entropy kartı"),
                Card("c2", "atolye", "Ofis kartı"),
                Card("c3", "", "Ofissiz"),
            ]

    board = FakeBoard()
    panel = OfficeCardsPanel(board=board)
    assert panel.is_read_only()
    assert board.calls and board.calls[0] == "*"     # ALL_CARDS
    titles = [panel.list_widget.item(i).text() for i in range(panel.list_widget.count())]
    assert any("Ofis kartı" in t for t in titles)
    assert not any("Entropy kartı" in t for t in titles)
    assert not any("Ofissiz" in t for t in titles)

    # `board_state_changed` yükü panelin tazelenmesini tetikler.
    before = len(board.calls)
    panel.on_board_state_changed({"card_id": "c2", "status": "review"})
    assert len(board.calls) > before
    panel.deleteLater()


def test_zen_tasks_tab_hosts_office_cards(zen):
    """Zen "Görevler" sekmesinde ofis kartları bölmesi var ve Entropy panosu ayrı."""
    panel = getattr(zen, "office_cards_panel", None)
    assert panel is not None
    assert panel.parent() is not None
    assert zen.task_board_widget is not panel


# ------------------------------------------------------- 5. beceri adayları


def test_skill_candidates_panel_calls_contract(app):
    """Onayla/Reddet 12-C sözleşmesini çağırır; onaysız etkinleşme yok."""
    from entropy.ui.widgets.skill_candidates_panel import SkillCandidatesPanel

    class FakeApi:
        def __init__(self):
            self.promoted, self.rejected = [], []
            self.items = [{"id": "s1", "name": "pdf-ozetleyici", "summary": "PDF özetler"}]

        def list_candidates(self):
            return list(self.items)

        def promote_skill(self, cid):
            self.promoted.append(cid)
            self.items = [i for i in self.items if i["id"] != cid]

        def reject_skill(self, cid):
            self.rejected.append(cid)
            self.items = [i for i in self.items if i["id"] != cid]

    api = FakeApi()
    panel = SkillCandidatesPanel(api=api)
    assert "pdf-ozetleyici" in panel.body.findChildren(type(panel.title_label))[0].text() \
        or any("pdf-ozetleyici" in w.text() for w in panel.body.findChildren(type(panel.title_label)))
    assert "onay bekliyor" in " ".join(
        w.text() for w in panel.body.findChildren(type(panel.title_label))
    )
    assert panel.decide("s1", True) is True
    assert api.promoted == ["s1"]
    assert panel.candidates() == []

    api.items = [{"id": "s2", "name": "log-temizleyici", "summary": ""}]
    panel.refresh()
    assert panel.decide("s2", False) is True
    assert api.rejected == ["s2"]
    panel.deleteLater()


def test_skill_candidates_panel_without_module(app):
    """`memory.skill_synthesis` yoksa panel boş kalır, ürün kırılmaz."""
    from entropy.ui.widgets.skill_candidates_panel import SkillCandidatesPanel

    class NoApi:
        pass

    panel = SkillCandidatesPanel(api=NoApi())
    assert panel.candidates() == []
    assert panel.decide("x", True) is False
    panel.deleteLater()


def test_autonomous_task_card_appears_in_chat(zen):
    """`task.assigned` + `actor=entropy` sohbete otonom görev kartı yazar."""
    before = zen.chat_browser.toPlainText()
    zen.on_board_state_changed(
        {"event": "task.assigned", "actor": "entropy",
         "title": "Rapor derle", "agent": "arastirmaci", "card_id": "k1"}
    )
    after = zen.chat_browser.toPlainText()
    assert "Entropy görev verdi" in after
    assert "Rapor derle" in after and "arastirmaci" in after

    # Başka aktör / başka olay kart yazmaz.
    mid = zen.chat_browser.toPlainText()
    zen.on_board_state_changed(
        {"event": "task.assigned", "actor": "human", "title": "Elle", "agent": "x"}
    )
    zen.on_board_state_changed(
        {"event": "run.finished", "actor": "entropy", "title": "Bitti", "agent": "x"}
    )
    assert zen.chat_browser.toPlainText() == mid
    assert before != after
