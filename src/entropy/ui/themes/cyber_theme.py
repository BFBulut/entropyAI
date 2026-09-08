"""Dark Cybernetic theme and design tokens for Entropy AI."""

CYBER_THEME = {
    "bg_root": "#080B10",
    "bg_surface": "#0E1420",
    "bg_card": "#141C2C",
    "bg_terminal": "#05070A",
    "border": "#1F2B42",
    "border_focus": "#00F0FF",
    "accent_cyan": "#00F0FF",
    "accent_amber": "#FFB300",
    "accent_purple": "#9D00FF",
    "accent_emerald": "#00FF9D",
    "text_primary": "#F0F6FC",
    "text_secondary": "#8B949E",
    "text_muted": "#484F58",
}

# ---------------------------------------------------------------------------
# Okuma yüzeyi tasarım belirteçleri (sohbet balonları + rapor okuyucu ortak)
#
# Neden ayrı bir sözlük: sohbet, Zen paneli, rapor okuyucu ve bağımsız rapor
# penceresi aynı görünüme sahip olmalı. Renk/aralık değerleri kod içine
# serpiştirilince tablolar ve kod blokları tam siyah dolgularla ayrışıyordu.
# Yüzeyler artık arka planla uyumlu, birbirinden yalnızca bir kademe farklı.
# ---------------------------------------------------------------------------
READING_TOKENS = {
    # Yüzeyler: kök → kart → yükseltilmiş. Hiçbiri saf siyah değil.
    "surface_base": "#0F1622",
    "surface_raised": "#151E2C",
    "surface_soft": "#1A2434",
    # Ayırıcı çizgiler: dolgu yerine ince çizgi kullanılır.
    "divider": "#22314A",
    "divider_soft": "#1A2436",
    # Yazı
    "text": "#E8EFF7",
    "text_body": "#C7D3E1",
    "text_dim": "#93A3B8",
    # Vurgular
    "accent": "#38D9FF",
    "accent_soft": "#0F2A38",
    "accent_alt": "#3DE8A8",
    "accent_warn": "#FFC24D",
    # Tipografi
    "font_body": "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif",
    "font_mono": "'Cascadia Mono', 'Consolas', 'Courier New', monospace",
    "font_size_body": "14px",
    "font_size_small": "12px",
    "font_size_mono": "13px",
    "line_height": "1.55",
    # Aralıklar
    "radius": "8px",
    "radius_small": "5px",
    "block_margin": "14px",
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
    h1 {{ color: {t['text']}; font-size: 22px; margin: 20px 0 10px 0; }}
    h2 {{ color: {t['text']}; font-size: 18px; margin: 18px 0 8px 0; }}
    h3 {{ color: {t['text']}; font-size: 15px; margin: 14px 0 6px 0; }}
    h4 {{ color: {t['text_dim']}; font-size: 13px; margin: 12px 0 4px 0; }}
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

STYLESHEET = f"""
QWidget {{
    background-color: {CYBER_THEME['bg_root']};
    color: {CYBER_THEME['text_primary']};
    font-family: 'Segoe UI', 'Consolas', sans-serif;
    font-size: 13px;
}}

QFrame#cardFrame {{
    background-color: {CYBER_THEME['bg_surface']};
    border: 1px solid {CYBER_THEME['border']};
    border-radius: 8px;
}}

QLabel {{
    background-color: transparent;
    color: {CYBER_THEME['text_primary']};
}}

QPushButton {{
    background-color: {CYBER_THEME['bg_card']};
    color: {CYBER_THEME['accent_cyan']};
    border: 1px solid {CYBER_THEME['border']};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}}

QPushButton:hover {{
    border-color: {CYBER_THEME['accent_cyan']};
    background-color: #1A263C;
}}

QLineEdit, QTextEdit {{
    background-color: {CYBER_THEME['bg_terminal']};
    color: {CYBER_THEME['text_primary']};
    border: 1px solid {CYBER_THEME['border']};
    border-radius: 6px;
    padding: 8px;
    font-family: 'Consolas', monospace;
}}

QLineEdit:focus, QTextEdit:focus {{
    border-color: {CYBER_THEME['accent_cyan']};
}}

QComboBox {{
    background-color: #05070A;
    color: #00F0FF;
    border: 1px solid #1F2B42;
    border-radius: 4px;
    padding: 4px 8px;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    font-weight: bold;
}}

QComboBox:hover, QComboBox:focus {{
    border-color: #00F0FF;
}}

QComboBox QAbstractItemView {{
    background-color: #0E1420;
    color: #F0F6FC;
    border: 1px solid #1F2B42;
    selection-background-color: #1A263C;
    selection-color: #00F0FF;
}}

QTabWidget::pane {{
    border: 1px solid #1F2B42;
    background: #0E1420;
    border-radius: 6px;
}}

QTabBar::tab {{
    background: #080B10;
    color: #8B949E;
    border: 1px solid #1F2B42;
    padding: 6px 12px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: bold;
    font-size: 11px;
}}

QTabBar::tab:selected {{
    background: #0E1420;
    color: #00F0FF;
    border-bottom-color: #0E1420;
}}
"""
