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
