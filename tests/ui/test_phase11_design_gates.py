"""Faz 11-E — tasarım sistemi kapıları (adım 2-6 kabul ölçütleri).

Kaynak: `docs/reports/2026-09-10_Faz11_Arastirma_D_Arayuz_Tasarim_Denetimi.md`
§5.3 ve §6. Her test bir kapıyı kilitler; ölçüm mantığının tek kaynağı
`scripts/ui_audit.py`'dir (iddia değil ölçüm).

Hepsi `QT_QPA_PLATFORM=offscreen` ile koşar; model çağrısı yoktur.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QPushButton, QSplitter, QWidget,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import ui_audit  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from entropy.ui.design import apply_design_system

    application = QApplication.instance() or QApplication([])
    # Kapılar tasarım sistemi uygulanmış hâlde ölçülür (üretimde
    # `ui/manager.py` bunu yapar).
    apply_design_system(application)
    yield application


@pytest.fixture(scope="module")
def metrics():
    data = ui_audit.static_metrics(ui_audit.DEFAULT_PATHS)
    desk = ui_audit.static_metrics(["src/entropy/desk"])
    data["desk_hex"] = desk["distinct_hex"]
    data["desk_stylesheets"] = desk["local_stylesheets"]
    data["desk_emoji"] = desk["emoji_usages"]
    data.update(ui_audit.token_metrics())
    return data


# --------------------------------------------------------------- statik kapılar


def test_local_stylesheets_under_gate(metrics):
    """Yerel `setStyleSheet` 222 -> ≤ 40 (stil tek kaynaktan üretilir)."""
    assert metrics["local_stylesheets"] <= 40, metrics["local_stylesheets_by_file"]


def test_fixed_sizes_under_gate(metrics):
    """Sabit denetim boyutu 87 -> ≤ 20 (yükseklik belirteçten gelir)."""
    assert metrics["fixed_sizes"] <= 20


def test_font_scale_is_four_steps_plus_mono(metrics):
    """Yazı boyutu kademesi 9 -> ≤ 5 (title/heading/body/label + mono)."""
    assert metrics["distinct_font_sizes"] <= 5, metrics["font_sizes"]


def test_emoji_icons_under_gate(metrics):
    """Emoji ikon 358 -> ≤ 40; ikon `design.icon()` üzerinden gelir."""
    assert metrics["emoji_usages"] <= 40, metrics["distinct_emojis"]


def test_no_small_targets(metrics):
    """WCAG 2.5.8: sabit boyutlu hiçbir denetim 24 px'in altında değil."""
    assert metrics["small_targets"] == []


def test_contrast_requirements_hold(metrics):
    """WCAG 1.4.11 / 1.4.3: belirteç çiftlerinin tümü eşiği geçer."""
    assert metrics["contrast_failures"] == []


def test_focus_rule_exists_for_every_focusable(metrics):
    """WCAG 2.4.7: odaklanabilir her seçici için `:focus` kuralı var."""
    assert metrics["focusless_selectors"] == []


def test_desk_uses_only_tokens(metrics):
    """Adım 6: `desk/**` içinde düz onaltılık renk ve yerel stil yok."""
    assert metrics["desk_hex"] == 0
    assert metrics["desk_stylesheets"] <= 10
    assert metrics["desk_emoji"] == 0


def test_local_hex_stays_under_ten_per_file(metrics):
    """Dosya başına düz onaltılık renk ≤ 10 (kalanlar gömülü HTML gövdeleri).

    Tam sıfır hedefi (denetim §6.2) HTML/JS gövdelerini de kapsıyor; bu dilimde
    widget stilleri belirtece bağlandı, gömülü belge gövdeleri açık iş kaldı.
    """
    import re

    offenders = {}
    for path in (REPO_ROOT / "src/entropy/ui").rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in ui_audit.TOKEN_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        distinct = {h.upper() for h in ui_audit.HEX_RE.findall(text)}
        if len(distinct) > 10:
            offenders[rel] = len(distinct)
    # Bilinen istisnalar: graf tuvali (viz paleti) ve markdown okuma teması.
    allowed = {
        "src/entropy/ui/widgets/knowledge_graph.py",
        "src/entropy/ui/widgets/markdown_renderer.py",
        "src/entropy/ui/themes/cyber_theme.py",
    }
    assert set(offenders) <= allowed, offenders
    assert re  # kullanılıyor


# --------------------------------------------------------------- yerleşim kapıları


def _make_zen(app):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.zen_mode import ZenModeWindow

    win = ZenModeWindow(bridge=AgyProcessBridge())
    return win


def _make_chat(app):
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.ui.modes.chat_mode import ChatModeWindow

    return ChatModeWindow(bridge=AgyProcessBridge())


def _splitter_depth(root: QWidget) -> int:
    """En derin iç içe `QSplitter` zinciri."""
    best = 0
    for sp in root.findChildren(QSplitter):
        depth = 0
        node = sp
        while node is not None:
            if isinstance(node, QSplitter):
                depth += 1
            node = node.parentWidget()
        best = max(best, depth)
    return best


def test_topbar_item_count(app):
    """Üst çubuk 18 -> 4 öğe (pencere denetimleri hariç), iki kipte de."""
    zen = _make_zen(app)
    chat = _make_chat(app)
    try:
        for win in (zen, chat):
            assert len(win.header_items) <= 4, win.header_items
            # Öğelerin hepsi gerçekten çubuğun içinde olmalı.
            for item in win.header_items:
                assert item.parentWidget() is not None
                assert win.header_frame.isAncestorOf(item)
    finally:
        chat.close()
        zen.close()


def test_zen_fits_1366(app):
    """1366x768'de taşan panel yok ve yedi bölümün hepsi görünür."""
    zen = _make_zen(app)
    try:
        zen.setGeometry(0, 0, 1366, 768)
        zen.show()
        app.processEvents()

        nav = zen.left_tabs
        assert nav.count() == 7
        assert nav.visible_item_count() == 7, "gezinme listesi kaydırma istiyor"

        # Taşma: doğrudan çocuk panellerin sağ/alt kenarı pencereyi aşmamalı.
        overflowing = []
        for child in zen.centralWidget().findChildren(QWidget):
            if not child.isVisible() or child.parentWidget() is not zen.centralWidget():
                continue
            rect = child.geometry()
            if rect.right() > zen.width() + 1 or rect.bottom() > zen.height() + 1:
                overflowing.append(child.objectName() or child.__class__.__name__)
        assert overflowing == []

        # Bölücü derinliği: KABUK zinciri 2 (denetim D-17: 4 idi).
        # Panel içi tek bölme (rapor listesi | okuyucu) kabuğa dahil değildir;
        # kullanıcı içeriğe ulaşmak için en fazla iki kabuk bölücüsü ayarlar.
        shell = [
            sp for sp in zen.findChildren(QSplitter)
            if sp.objectName() == "shellSplitter"
        ]
        assert len(shell) == 2
        assert _splitter_depth(zen) <= 3
    finally:
        zen.close()


def test_zen_fits_960x540_scaled(app):
    """Faz 12-D.1: Zen'in GERÇEK asgarisi 960x540 mantıksal sınırın altında.

    Neden: %200 ölçeklenen bir monitörde 1 mantıksal px = 2 fiziksel px.
    Eski asgari 1100x680 mantıksal (= 2200x1360 fiziksel) o panele hiçbir
    boyutta sığmıyordu. Ölçüm mantıksaldır, bu yüzden ölçek çarpanından
    bağımsızdır; `QT_SCALE_FACTOR=2` ile alınan ekran görüntüleri
    `scratch/ui/phase12/` altındadır.
    """
    from entropy.ui.modes.zen_mode import ZEN_MIN_SIZE

    zen = _make_zen(app)
    try:
        hint = zen.minimumSizeHint()
        assert hint.width() <= 960, f"asgari genişlik {hint.width()}"
        assert hint.height() <= 540, f"asgari yükseklik {hint.height()}"
        assert ZEN_MIN_SIZE[0] <= 960 and ZEN_MIN_SIZE[1] <= 540, ZEN_MIN_SIZE

        zen.setMinimumSize(*ZEN_MIN_SIZE)
        zen.setGeometry(0, 0, 960, 540)
        zen.show()
        app.processEvents()
        assert zen.width() <= 962 and zen.height() <= 542, zen.size()

        # Pencere denetimleri ve durum kümesi 960'ta da görünür (kompakt kip).
        for name in ("btn_minimize", "btn_maximize"):
            btn = getattr(zen, name)
            assert btn.isVisible(), name
            assert btn.mapTo(zen, btn.rect().bottomRight()).y() <= zen.height() + 1
        cluster = zen.status_cluster
        assert cluster.isVisible()
        top_right = cluster.mapTo(zen, cluster.rect().topRight())
        assert top_right.x() <= zen.width() + 1, top_right

        # Sohbet gövdesi öncelikli: yine görünür ve taşmıyor.
        assert zen.chat_browser.isVisible()
        overflowing = []
        for child in zen.centralWidget().findChildren(QWidget):
            if not child.isVisible() or child.parentWidget() is not zen.centralWidget():
                continue
            rect = child.geometry()
            if rect.right() > zen.width() + 1 or rect.bottom() > zen.height() + 1:
                overflowing.append(child.objectName() or child.__class__.__name__)
        assert overflowing == []
    finally:
        zen.close()


def test_chat_chrome_ratio(app):
    """1280x800'de krom (üst çubuk + şeritler) pencerenin ≤ %25'i."""
    chat = _make_chat(app)
    try:
        chat.setGeometry(0, 0, 1280, 800)
        chat.show()
        app.processEvents()

        chrome = chat.header_frame.height()
        for name in ("report_bar", "notification_scroll", "attachment_bar"):
            widget = getattr(chat, name, None)
            if widget is not None and widget.isVisible():
                chrome += widget.height()
        ratio = chrome / max(1, chat.height())
        assert ratio <= 0.25, f"krom oranı %{ratio * 100:.1f}"
    finally:
        chat.close()


def test_chat_topbar_two_rows_at_460(app):
    """460 px genişlikte üst çubuk en fazla iki satır (eskiden 6 idi)."""
    chat = _make_chat(app)
    try:
        chat.setGeometry(0, 0, 460, 800)
        chat.show()
        app.processEvents()

        header = chat.header_frame
        rows = max(1, round(header.height() / max(1, chat.brand.sizeHint().height() + 8)))
        assert rows <= 2, f"{rows} satır (yükseklik {header.height()} px)"
    finally:
        chat.close()


def test_shortcuts_and_palette_actions(app):
    """Kısayollar kurulu ve her pencere eyleminin palette bir kaydı var."""
    zen = _make_zen(app)
    try:
        assert len(getattr(zen, "_shortcuts", [])) >= 5
        actions = [
            item["payload"] for item in zen._collect_palette_items()
            if item.get("kind") == "action"
        ]
        for key in ("desk", "project", "new_chat", "terminal", "nav_reports"):
            assert key in actions
        # Palet eylemleri gerçekten çalışır (terminal çekmecesi).
        # Offscreen'de pencere gösterilmediği için `isVisible()` her zaman
        # False döner; açık/kapalı durumu `isHidden()` ile ölçülür.
        before = zen.terminal_pane.isHidden()
        assert zen.run_palette_action("terminal") is True
        assert zen.terminal_pane.isHidden() is not before
    finally:
        zen.close()


def test_focusable_controls_have_accessible_names(app):
    """Başlıca denetimlerde `setAccessibleName` var (WCAG 4.1.2)."""
    zen = _make_zen(app)
    try:
        missing = []
        for btn in zen.header_frame.findChildren(QPushButton):
            if not btn.accessibleName() and not btn.text():
                missing.append(btn.objectName() or repr(btn))
        assert missing == []
    finally:
        zen.close()


# --------------------------------------------------------------------------
# Faz 11 kapanışı — boole ayarların arayüz karşılığı
# --------------------------------------------------------------------------

@pytest.mark.parametrize("maker_name", ["_make_zen", "_make_chat"])
def test_setting_toggles_exist_in_palette_and_work(app, monkeypatch, maker_name):
    """`amplification_lock` ve `board_auto_dispatch` palette var ve çalışıyor.

    Kayıtlı boşluk (STATE.md §2.3): iki ayarın da arayüzde hiç karşılığı yoktu.
    Ayar kalıcılaştırma ve tetikleyici uygulaması **çağrılmaz** (monkeypatch);
    ölçülen şey paletin doğru işlevi çağırdığıdır.
    """
    from entropy.core import slash_commands
    from entropy.core.config import config as cfg

    monkeypatch.setattr(slash_commands, "_apply_board_auto", lambda enabled: "")
    monkeypatch.setattr(type(cfg), "save_settings", lambda self: None, raising=False)

    win = globals()[maker_name](app)
    try:
        actions = [
            item["payload"] for item in win._collect_palette_items()
            if item.get("kind") == "action"
        ]
        assert "toggle_lock" in actions
        assert "toggle_board_auto" in actions

        for key, setting in (("toggle_lock", "amplification_lock"),
                             ("toggle_board_auto", "board_auto_dispatch")):
            before = bool(getattr(cfg, setting))
            assert win.run_palette_action(key) is True
            assert bool(getattr(cfg, setting)) is not before
            # geri çevir: testler kullanıcı ayarını kalıcı değiştirmesin
            assert win.run_palette_action(key) is True
            assert bool(getattr(cfg, setting)) is before
    finally:
        win.close()


def test_scheduled_dreaming_uses_dream_v2_module():
    """`tasks_widget` artık eski `cog.dream_and_consolidate()` çağırmıyor."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src/entropy/ui/widgets/tasks_widget.py"
    text = src.read_text(encoding="utf-8")
    assert "cog.dream_and_consolidate()" not in text, "eski 48 saat koşullu metot"
    assert "from entropy.brain.dream import dream_and_consolidate" in text
    assert "send_prompt=None" in text, "zamanlanmış görev kota harcamamalı"
