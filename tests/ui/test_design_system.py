"""Faz 11-E adım 1 — tasarım sistemi temeli.

Denetimin ölçülebilir iddialarını mekanikleştirir: kontrast eşikleri, odak
kuralları, geriye uyumlu takma adlar, ikon yüklenmesi ve ölçüm betiği.
Model çağrısı yok; Qt kısmı offscreen çalışır.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from entropy.ui.design import (
    DARK_TOKENS,
    EMOJI_ICON_MAP,
    LIGHT_TOKENS,
    TOKENS,
    apply_design_system,
    build_qss,
    contrast_ratio,
    get_tokens,
    icon,
    resolve,
)
from entropy.ui.design.qss import FOCUSABLE_SELECTORS
from entropy.ui.design.tokens import CONTRAST_REQUIREMENTS

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Belirteçler
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("fg,bg,threshold", CONTRAST_REQUIREMENTS)
def test_token_contrast(theme, fg, bg, threshold):
    colors = get_tokens(theme)["color"]
    ratio = contrast_ratio(colors[fg], colors[bg])
    assert ratio >= threshold, f"{theme}: {fg}/{bg} = {ratio:.2f} < {threshold}"


def test_line_strong_and_muted_text_meet_wcag():
    """Denetimdeki iki somut ihlal (1,39:1 kenarlık, 2,06:1 soluk metin) kapandı."""
    c = TOKENS["color"]
    assert contrast_ratio(c["line.strong"], c["surface"]) >= 3.0
    assert contrast_ratio(c["text.muted"], c["surface"]) >= 4.5


def test_no_pure_spectrum_accents():
    """Kroma 255 = saf tayf rengi; 'neon' imzası yasak."""
    from entropy.ui.design.tokens import chroma

    for key in ("accent", "ok", "warn", "danger"):
        assert chroma(TOKENS["color"][key]) < 200, key


def test_token_scales_are_limited():
    assert len(TOKENS["radius"]) == 3
    assert sorted(TOKENS["space"].values()) == [4, 8, 12, 16, 24, 32]
    assert set(TOKENS["type"]) == {"title", "heading", "body", "label", "mono"}
    assert set(TOKENS["state"]) == {"hover", "pressed", "focus", "disabled", "selected"}


def test_font_stacks_do_not_mix_sans_and_mono():
    sans = TOKENS["font"]["sans"].lower()
    mono = TOKENS["font"]["mono"].lower()
    assert "mono" not in sans and "consolas" not in sans
    assert "sans" not in mono


def test_light_theme_has_same_keys():
    assert set(LIGHT_TOKENS["color"]) == set(DARK_TOKENS["color"])
    assert LIGHT_TOKENS["color"]["bg"] != DARK_TOKENS["color"]["bg"]


def test_density_changes_control_height_only_upwards():
    compact = get_tokens("dark", "compact")
    comfortable = get_tokens("dark", "comfortable")
    assert comfortable["control"]["height"] > compact["control"]["height"]
    assert compact["control"]["height_icon"] >= compact["control"]["min_target"]


def test_resolve_handles_dotted_color_keys():
    assert resolve("color.text.muted") == TOKENS["color"]["text.muted"]
    assert resolve("type.body.size") == 13


# --------------------------------------------------------------------------- #
# QSS
# --------------------------------------------------------------------------- #
def test_qss_has_focus_rule_for_every_focusable_selector():
    qss = build_qss()
    missing = [s for s in FOCUSABLE_SELECTORS if f"{s}:focus" not in qss]
    assert not missing, f"odak kuralı eksik: {missing}"


def test_qss_covers_component_library():
    qss = build_qss()
    for needle in (
        'QPushButton[variant="primary"]',
        'QPushButton[role="icon"]',
        'QLabel[role="badge"]',
        'QFrame[role="card"]',
        'QFrame[role="panel"]',
        'QFrame[role="palette"]',
        'QFrame[role="toast"]',
        'QTextBrowser[role="reader"]',
        'QPlainTextEdit[role="terminal"]',
        "QListWidget#navList",
        "QSplitter::handle",
        "QScrollBar:vertical",
        "QToolTip",
        "QComboBox",
    ):
        assert needle in qss, needle


def test_qss_uses_only_token_colors():
    import re

    qss = build_qss()
    used = {h.upper() for h in re.findall(r"#[0-9a-fA-F]{6}", qss)}
    allowed = {v.upper() for v in TOKENS["color"].values()}
    allowed.add("#000000")
    assert used <= allowed, used - allowed


def test_splitter_handle_is_visible_enough():
    """Bölücü tutamağı kontrastı ≥ 3:1 (görünür gruplama)."""
    c = TOKENS["color"]
    assert contrast_ratio(c["line.strong"], c["bg"]) >= 3.0
    assert f"QSplitter::handle {{ background-color: {c['line.strong']}; }}" in build_qss()


def test_apply_design_system_offscreen(qapp_or_skip):
    qss = apply_design_system(qapp_or_skip)
    assert qss.startswith("\n")
    assert qapp_or_skip.styleSheet() == qss
    # temizlik: diğer testlerin görünümünü etkilemesin
    qapp_or_skip.setStyleSheet("")


# --------------------------------------------------------------------------- #
# İkonlar
# --------------------------------------------------------------------------- #
def test_icon_loads_offscreen(qapp_or_skip):
    from entropy.ui.design.icons import qtawesome_available

    if not qtawesome_available():
        pytest.skip("qtawesome kurulu değil")
    ic = icon("book", color=TOKENS["color"]["text.muted"])
    assert not ic.isNull()


def test_every_mapped_icon_name_resolves(qapp_or_skip):
    from entropy.ui.design.icons import qtawesome_available

    if not qtawesome_available():
        pytest.skip("qtawesome kurulu değil")
    missing = [name for name in set(EMOJI_ICON_MAP.values()) if icon(name).isNull()]
    assert not missing, f"ikon ailesinde yok: {missing}"


def test_emoji_map_covers_top_emojis():
    assert len(EMOJI_ICON_MAP) >= 40


def test_icon_never_raises_without_qtawesome(monkeypatch, qapp_or_skip):
    from entropy.ui.design import icons as icons_mod

    monkeypatch.setattr(icons_mod, "_qta", lambda: None)
    assert icons_mod.icon("book").isNull()
    assert icons_mod.icon_for_emoji("\U0001F3AF").isNull()


# --------------------------------------------------------------------------- #
# Geriye uyumlu köprü
# --------------------------------------------------------------------------- #
LEGACY_CYBER_KEYS = {
    "bg_root", "bg_surface", "bg_card", "bg_terminal", "border", "border_focus",
    "accent_cyan", "accent_amber", "accent_purple", "accent_emerald",
    "text_primary", "text_secondary", "text_muted",
}
LEGACY_READING_KEYS = {
    "surface_base", "surface_raised", "surface_soft", "divider", "divider_soft",
    "text", "text_body", "text_dim", "accent", "accent_soft", "accent_alt",
    "accent_warn", "font_body", "font_mono", "font_size_body", "font_size_small",
    "font_size_mono", "line_height", "radius", "radius_small", "block_margin",
}


def test_legacy_alias_keys_stable():
    from entropy.ui.themes.cyber_theme import CYBER_THEME, READING_TOKENS

    assert set(CYBER_THEME) == LEGACY_CYBER_KEYS
    assert set(READING_TOKENS) == LEGACY_READING_KEYS


def test_legacy_aliases_carry_new_token_values():
    from entropy.ui.themes.cyber_theme import CYBER_THEME, READING_TOKENS

    c = TOKENS["color"]
    assert CYBER_THEME["accent_cyan"] == c["accent"]
    assert READING_TOKENS["accent"] == c["accent"]
    # D-01 kapandı: iki palet artık aynı vurgu ve aynı metin rengini veriyor.
    assert CYBER_THEME["accent_cyan"] == READING_TOKENS["accent"]
    assert CYBER_THEME["text_primary"] == READING_TOKENS["text"]
    assert "#00F0FF" not in CYBER_THEME.values()


def test_legacy_stylesheet_has_focus_rules():
    from entropy.ui.themes.cyber_theme import STYLESHEET

    assert "QPushButton:focus" in STYLESHEET
    assert "QLineEdit:focus" in STYLESHEET


def test_reading_css_still_renders():
    from entropy.ui.themes.cyber_theme import reading_css

    css = reading_css()
    assert "body {" in css and TOKENS["color"]["accent"] in css


# --------------------------------------------------------------------------- #
# Ölçüm betiği
# --------------------------------------------------------------------------- #
def test_ui_audit_script_runs_and_records_baseline(tmp_path):
    out = tmp_path / "audit.json"
    proc = subprocess.run(
        [sys.executable, "scripts/ui_audit.py", "--json", str(out), "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    # Taban ölçüm kaydı — düşürme adım 2-6'da yapılır.
    assert data["contrast_failures"] == []
    assert data["focusless_selectors"] == []
    assert data["distinct_hex"] > 0
    assert data["local_stylesheets"] > 0
    assert data["baseline"]["local_stylesheets"] == 222
    assert data["baseline"]["distinct_hex"] == 91


@pytest.fixture
def qapp_or_skip():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app
