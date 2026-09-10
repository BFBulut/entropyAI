"""Geriye uyumlu köprü — gerçek kaynak `entropy.ui.design.tokens`.

Faz 11-E adım 1: tasarım sistemi `entropy/ui/design/` altına taşındı.
Bu dosya artık **kendi paletini tanımlamaz**; `CYBER_THEME` ve `READING_TOKENS`
aynı anahtarlarla ama yeni belirteç değerleriyle burada türetilir.

Neden köprü: denetimde 223 yerel `setStyleSheet` ve bu iki sözlüğe yapılan
onlarca içe aktarma ölçüldü (`src/entropy/ui/**`, `src/entropy/desk/**`).
Anahtar adlarını korumak, o çağrı yerlerinin bu adımda hiç değişmeden yeni
renkleri almasını sağlar. Anahtar kümesi teste bağlıdır
(`tests/ui/test_design_system.py::test_legacy_alias_keys_stable`).

Denetimin D-01 bulgusu ("iki çelişen palet aynı dosyada") böylece kapanır:
`CYBER_THEME["accent_cyan"]` ile `READING_TOKENS["accent"]` artık aynı renktir.

Yeni kod bu dosyayı kullanmaz:

    from entropy.ui.design import TOKENS, apply_design_system, icon
"""

from entropy.ui.design.tokens import TOKENS

_C = TOKENS["color"]
_T = TOKENS["type"]
_F = TOKENS["font"]
_R = TOKENS["radius"]

# ---------------------------------------------------------------------------
# Takma ad 1: CYBER_THEME (eski anahtarlar korunur, değerler yeni belirteçten)
#
# `accent_amber` → warn, `accent_emerald` → ok, `accent_purple` → accent:
# mor tamamen kaldırıldı (dört farklı mor vardı, hiçbiri anlam taşımıyordu),
# tek vurgu kuralı gereği vurgu rolüne düşürüldü.
# ---------------------------------------------------------------------------
CYBER_THEME = {
    "bg_root": _C["bg"],
    "bg_surface": _C["surface"],
    "bg_card": _C["surface.raised"],
    "bg_terminal": _C["terminal"],
    "border": _C["line"],
    "border_focus": _C["accent"],
    "accent_cyan": _C["accent"],
    "accent_amber": _C["warn"],
    "accent_purple": _C["accent"],
    "accent_emerald": _C["ok"],
    "text_primary": _C["text"],
    "text_secondary": _C["text.muted"],
    "text_muted": _C["text.muted"],
}

# ---------------------------------------------------------------------------
# Takma ad 2: READING_TOKENS (okuma yüzeyi: sohbet balonu + rapor okuyucu)
#
# Eskiden CYBER_THEME'den bir tık farklı gri/vurgu kullanıyordu; bu fark
# kullanıcı tarafından "bulanık, kirli" olarak algılanan geçişin nedeniydi.
# Artık aynı belirteçlerden türer.
# ---------------------------------------------------------------------------
READING_TOKENS = {
    # Yüzeyler: kök → kart → yükseltilmiş. Hiçbiri saf siyah değil.
    "surface_base": _C["bg"],
    "surface_raised": _C["surface"],
    "surface_soft": _C["surface.raised"],
    # Ayırıcı çizgiler
    "divider": _C["line.strong"],
    "divider_soft": _C["line"],
    # Yazı
    "text": _C["text"],
    "text_body": _C["text"],
    "text_dim": _C["text.muted"],
    # Vurgular (tek vurgu + iki durum)
    "accent": _C["accent"],
    "accent_soft": _C["accent.soft"],
    "accent_alt": _C["ok"],
    "accent_warn": _C["warn"],
    # Tipografi (CSS dizeleri — Qt zengin metin motoru için)
    "font_body": _F["sans"],
    "font_mono": _F["mono"],
    "font_size_body": f"{_T['body']['size']}px",
    "font_size_small": f"{_T['label']['size']}px",
    "font_size_mono": f"{_T['mono']['size']}px",
    "line_height": "1.55",
    # Aralıklar
    "radius": f"{_R['md']}px",
    "radius_small": f"{_R['sm']}px",
    "block_margin": f"{TOKENS['space']['4']}px",
}


def reading_css() -> str:
    """
    Sohbet ve rapor yüzeylerinin ortak CSS'i (tek kaynak).

    Qt zengin metin motoru CSS'in dar bir alt kümesini destekler; rgba() ve
    değişkenler çalışmadığı için belirteçler burada düz onaltılık renklere
    açılır. Aynı metin hem tam HTML belgesinde hem de gömülü parçalarda
    kullanılan satır içi stillerle eşleşir.
    """
    t = READING_TOKENS
    return f"""
    body {{
        background-color: {t['surface_base']};
        color: {t['text_body']};
        font-family: {t['font_body']};
        font-size: {t['font_size_body']};
        line-height: {t['line_height']};
        padding: 16px 20px;
    }}
    p {{ margin: 10px 0; line-height: {t['line_height']}; color: {t['text_body']}; }}
    h1 {{ color: {t['text']}; font-size:18px; margin: 20px 0 10px 0; }}
    h2 {{ color: {t['text']}; font-size:18px; margin: 18px 0 8px 0; }}
    h3 {{ color: {t['text']}; font-size:14px; margin: 14px 0 6px 0; }}
    h4 {{ color: {t['text_dim']}; font-size:13px; margin: 12px 0 4px 0; }}
    a {{ color: {t['accent']}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    ul, ol {{ margin: 8px 0 8px 0; padding-left: 22px; }}
    li {{ margin: 4px 0; color: {t['text_body']}; }}
    table {{ border-collapse: collapse; width: 100%; margin: {t['block_margin']} 0; }}
    th, td {{
        border: none;
        border-bottom: 1px solid {t['divider_soft']};
        padding: 8px 12px;
        text-align: left;
        font-size: {t['font_size_small']};
    }}
    th {{
        color: {t['accent']};
        border-bottom: 2px solid {t['divider']};
        font-weight: 600;
    }}
    td {{ color: {t['text_body']}; }}
    """


# ---------------------------------------------------------------------------
# STYLESHEET — pencere düzeyinde uygulanan eski stil sayfası.
#
# Bilinçli olarak `design.qss.build_qss()` DEĞİL: build_qss denetim boyutlarını
# (min/max-height 28 px) dayatır ve bu adımda dokunmadığımız 223 yerel stille
# çakışabilir. Burada eski kural yapısı korunur, yalnızca değerler belirteçten
# gelir. Tam sisteme geçiş `apply_design_system(app)` ile adım 2+ işidir.
# ---------------------------------------------------------------------------
STYLESHEET = f"""
QWidget {{
    background-color: {_C['bg']};
    color: {_C['text']};
    font-family: {_F['sans']};
    font-size: {_T['body']['size']}px;
}}

QFrame#cardFrame {{
    background-color: {_C['surface']};
    border: 1px solid {_C['line']};
    border-radius: {_R['md']}px;
}}

QLabel {{
    background-color: transparent;
    color: {_C['text']};
}}

QPushButton {{
    background-color: {_C['surface.raised']};
    color: {_C['text']};
    border: 1px solid {_C['line.strong']};
    border-radius: {_R['sm']}px;
    padding: 6px 14px;
}}

QPushButton:hover {{
    border-color: {_C['accent']};
    background-color: {_C['surface.raised']};
}}

QPushButton:pressed {{
    background-color: {_C['surface.raised']};
    padding-top: 7px;
}}

QPushButton:focus {{
    border-color: {_C['accent']};
    outline: {TOKENS['control']['focus_ring']}px solid {_C['accent']};
}}

QPushButton:disabled {{
    color: {_C['text.muted']};
    border-color: {_C['line']};
}}

QLineEdit, QTextEdit {{
    background-color: {_C['terminal']};
    color: {_C['text']};
    border: 1px solid {_C['line.strong']};
    border-radius: {_R['sm']}px;
    padding: 8px;
}}

QLineEdit:focus, QTextEdit:focus {{
    border-color: {_C['accent']};
    outline: {TOKENS['control']['focus_ring']}px solid {_C['accent']};
}}

QComboBox {{
    background-color: {_C['bg']};
    color: {_C['text']};
    border: 1px solid {_C['line.strong']};
    border-radius: {_R['sm']}px;
    padding: 4px 8px;
    font-size: {_T['label']['size']}px;
}}

QComboBox:hover, QComboBox:focus {{
    border-color: {_C['accent']};
}}

QComboBox QAbstractItemView {{
    background-color: {_C['surface']};
    color: {_C['text']};
    border: 1px solid {_C['line.strong']};
    selection-background-color: {_C['surface.raised']};
    selection-color: {_C['text']};
}}

QTabWidget::pane {{
    border: 1px solid {_C['line']};
    background: {_C['surface']};
    border-radius: {_R['sm']}px;
}}

QTabBar::tab {{
    background: transparent;
    color: {_C['text.muted']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 6px 12px;
    font-size: {_T['body']['size']}px;
}}

QTabBar::tab:selected {{
    background: {_C['surface']};
    color: {_C['text']};
    border-bottom-color: {_C['accent']};
}}

QSplitter::handle {{
    background-color: {_C['line.strong']};
}}
"""
