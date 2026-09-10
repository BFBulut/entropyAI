"""Belirteçlerden üretilen tek stil sayfası.

Neden: denetimde 223 yerel `setStyleSheet` çağrısı ve 856 renk yazımı ölçüldü;
tek bir rengi değiştirmek 856 yerde arama gerektiriyordu. Burada QSS **üretilir**,
bileşenler yalnızca `objectName` ya da `qproperty` ile sınıflandırılır.

Kapsanan 14 bileşen (denetim §3.7):
Button (primary/ghost/danger) · IconButton · Chip · Input/SearchInput · Select ·
Panel · NavList · ListRow · Card · Reader · Terminal · CommandPalette ·
Toast/StatusDot · Splitter.

Not (Qt sınırı): Qt QSS `outline-offset`'i yok sayar. Odak halkası bu yüzden
`border-color: accent` + `outline: 2px solid accent` ikilisiyle çizilir; iki
kademeli gerçek halka gerekirse sarmalayıcı `QFrame` ya da
`QProxyStyle.drawPrimitive(PE_FrameFocusRect)` kullanılmalıdır. Gerçek ekranda
doğrulanmalı.
"""

from __future__ import annotations

from typing import Any, Dict

from entropy.ui.design.tokens import TOKENS, get_tokens

__all__ = ["build_qss", "apply_design_system", "FOCUSABLE_SELECTORS"]


#: `scripts/ui_audit.py` ve testler bu seçicilerin her biri için `:focus`
#: kuralının üretilmiş QSS içinde bulunmasını şart koşar (WCAG 2.4.7).
FOCUSABLE_SELECTORS = (
    "QPushButton",
    "QToolButton",
    "QLineEdit",
    "QComboBox",
    "QPlainTextEdit",
    "QTextEdit",
    "QListWidget",
    "QTreeView",
    "QTabBar::tab",
    "QCheckBox",
)


def build_qss(tokens: Dict[str, Any] | None = None, density: str = "compact") -> str:
    """Belirteç sözlüğünden uygulama düzeyi QSS üretir.

    `tokens` verilmezse koyu tema + istenen yoğunluk kullanılır.
    """
    t = tokens if tokens is not None else get_tokens("dark", density)
    c, s, r, ty, ct = t["color"], t["space"], t["radius"], t["type"], t["control"]
    f = t["font"]
    h = ct["height"]
    ring = ct["focus_ring"]

    return f"""
/* ===== temel ===== */
QWidget {{
    background-color: {c['bg']};
    color: {c['text']};
    font-family: {f['sans']};
    font-size: {ty['body']['size']}px;
}}
QToolTip {{
    background-color: {c['surface.raised']};
    color: {c['text']};
    border: 1px solid {c['line.strong']};
    border-radius: {r['sm']}px;
    padding: {s['1']}px {s['2']}px;
    font-size: {ty['label']['size']}px;
}}

/* ===== yüzeyler: Panel / Card ===== */
QFrame[role="panel"], QFrame[role="card"], QFrame#panel, QFrame#card, QFrame#cardFrame {{
    background-color: {c['surface']};
    border: 1px solid {c['line']};
    border-radius: {r['md']}px;
}}
QFrame[role="card"]:hover, QFrame#card:hover {{ background-color: {c['surface.raised']}; }}

/* ===== etiket varyantları ===== */
QLabel {{ background: transparent; color: {c['text']}; }}
QLabel[role="title"] {{
    font-size: {ty['title']['size']}px; font-weight: {ty['title']['weight']};
}}
QLabel[role="heading"], QLabel#panelTitle {{
    font-size: {ty['heading']['size']}px; font-weight: {ty['heading']['weight']};
    padding: {s['2']}px {s['3']}px;
}}
QLabel[role="label"], QLabel[muted="true"] {{
    color: {c['text.muted']};
    font-size: {ty['label']['size']}px; font-weight: {ty['label']['weight']};
}}
QLabel[role="mono"] {{
    font-family: {f['mono']}; font-size: {ty['mono']['size']}px;
}}

/* ===== Button: tek kaynak, beş durum ===== */
QPushButton {{
    min-height: {h}px; max-height: {h}px;
    padding: 0 {s['3']}px;
    background-color: transparent;
    color: {c['text']};
    border: {ct['border']}px solid {c['line.strong']};
    border-radius: {r['sm']}px;
    font-weight: {ty['body']['weight']};
}}
QPushButton:hover    {{ background-color: {c['surface.raised']}; }}
QPushButton:pressed  {{ background-color: {c['surface.raised']}; padding-top: 1px; }}
QPushButton:focus    {{ border-color: {c['accent']}; outline: {ring}px solid {c['accent']}; }}
QPushButton:disabled {{ color: {c['text.muted']}; border-color: {c['line']}; }}
QPushButton[variant="primary"] {{
    background-color: {c['accent']}; color: {c['accent.ink']};
    border-color: {c['accent']}; font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ background-color: {c['accent']}; }}
/* Faz 13: "ghost" düğme kenarlıksız + sönük metinken düz yazı gibi görünüyordu
   (kullanıcı: "düğmeler görünmüyor"). Artık ince kenarlığı ve tam kontrastlı
   metni var; vurgu hâlâ yalnızca `primary`de. */
/* Faz 13-A9/G13-2: `line` (#1,29:1) bir AYIRICI rengidir, denetim sınırı
   değil. WCAG 1.4.11 denetim sınırında 3:1 ister; ghost kenarlığı bu yüzden
   `line.strong` (3,02:1). Ölçüm kapısı: `ghost_button_contrast`. */
QPushButton[variant="ghost"] {{ border-color: {c['line.strong']}; color: {c['text']}; }}
/* Faz 13-A kapanış (QA ölçümü): `line.strong` yalnızca `surface`/`bg` üstünde
   3:1 tutuyor; digest başlık şeridi gibi YÜKSELTİLMİŞ zeminlerde 2,35:1'e
   düşüyordu ("Tümünü okundu say", "Temizle"). Yükseltilmiş yüzeydeki ghost
   kenarlığı bu yüzden `line.onraised` belirtecini kullanır (sabit onaltılık
   değil). İşaretleme: `surface="raised"` ya da `role="header"`. */
QWidget[surface="raised"] QPushButton[variant="ghost"],
QWidget[role="header"] QPushButton[variant="ghost"],
QPushButton[variant="ghost"][surface="raised"] {{
    border-color: {c['line.onraised']};
}}
QPushButton[variant="ghost"]:hover {{ border-color: {c['accent']}; color: {c['text']}; }}
QPushButton[variant="danger"] {{ color: {c['danger']}; border-color: {c['danger']}; }}

/* ===== IconButton (WCAG 2.5.8: {ct['min_target']}px tabanının üstünde) ===== */
QPushButton[role="icon"], QPushButton#iconButton, QToolButton {{
    min-width: {ct['height_icon']}px; max-width: {ct['height_icon']}px;
    min-height: {ct['height_icon']}px; max-height: {ct['height_icon']}px;
    padding: 0; border-color: transparent; background-color: transparent;
}}
QToolButton:hover {{ background-color: {c['surface.raised']}; border-radius: {r['sm']}px; }}
QToolButton:focus {{ border: {ct['border']}px solid {c['accent']}; outline: {ring}px solid {c['accent']}; }}

/* ===== Üst çubuk grupları (Faz 11-E adım 2: 18 öğe -> 4) ===== */
QFrame[role="toolbarGroup"], QFrame#windowControls, QFrame#brandCluster,
QFrame#modelCapsule, QFrame#statusCluster {{
    background-color: transparent; border: none;
}}
QPushButton#modelCapsuleButton {{
    background-color: {c['surface']};
    border-color: {c['line']};
    padding: 0 {s['3']}px;
    font-family: {f['mono']}; font-size: {ty['label']['size']}px;
}}
QPushButton#modelCapsuleButton:hover {{ border-color: {c['accent']}; }}
QPushButton#paletteButton {{
    color: {c['text.muted']}; border-color: {c['line']};
    font-family: {f['mono']}; font-size: {ty['label']['size']}px;
}}
QPushButton[role="icon"][variant="danger"]:hover {{ background-color: {c['danger']}; color: {c['accent.ink']}; }}

/* ===== Sol gezinme bölgesi ===== */
QWidget#navRegion, QStackedWidget#navStack {{ background-color: transparent; }}

/* ===== Durum tonlu ikon düğmesi (ör. yordam damıtma) ===== */
QPushButton[tone="ok"]     {{ color: {c['ok']};     border-color: {c['ok']}; }}
QPushButton[tone="warn"]   {{ color: {c['warn']};   border-color: {c['warn']}; }}
QPushButton[tone="danger"] {{ color: {c['danger']}; border-color: {c['danger']}; }}
QPushButton[tone="muted"]  {{ color: {c['text.muted']}; border-color: {c['line']}; }}
QPushButton[tone="ok"]:disabled, QPushButton[tone="warn"]:disabled,
QPushButton[tone="muted"]:disabled {{ color: {c['text.muted']}; border-color: {c['line']}; }}
QLabel[role="badge"][tone="muted"] {{ color: {c['text.muted']}; }}

/* ===== Diyalog / ilerleme çubuğu (pencere kendi stilini yazmaz) ===== */
QDialog {{ background-color: {c['surface']}; color: {c['text']}; }}
QProgressBar {{
    background-color: {c['bg']}; border: 1px solid {c['line']};
    border-radius: {r['sm']}px; text-align: center;
    color: {c['text.muted']}; font-size: {ty['label']['size']}px;
    min-height: {s['4']}px; max-height: {s['4']}px;
}}
QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: {r['sm'] - 2}px; }}
QScrollArea {{ background-color: transparent; border: none; }}
QCheckBox:disabled {{ color: {c['text.muted']}; }}

/* ===== Input / SearchInput ===== */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {c['bg']};
    color: {c['text']};
    border: {ct['border']}px solid {c['line.strong']};
    border-radius: {r['sm']}px;
    padding: {s['1']}px {s['2']}px;
    selection-background-color: {c['accent']};
    selection-color: {c['accent.ink']};
}}
QLineEdit {{ min-height: {h}px; max-height: {h}px; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {c['accent']}; outline: {ring}px solid {c['accent']};
}}
QLineEdit:disabled, QPlainTextEdit:disabled {{ color: {c['text.muted']}; }}

/* ===== Select ===== */
QComboBox {{
    min-height: {h}px; max-height: {h}px;
    background-color: {c['bg']}; color: {c['text']};
    border: {ct['border']}px solid {c['line.strong']};
    border-radius: {r['sm']}px;
    padding: 0 {s['2']}px;
}}
QComboBox:hover {{ background-color: {c['surface.raised']}; }}
QComboBox:focus {{ border-color: {c['accent']}; outline: {ring}px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: {s['4']}px; }}
QComboBox QAbstractItemView {{
    background-color: {c['surface']}; color: {c['text']};
    border: 1px solid {c['line.strong']};
    selection-background-color: {c['surface.raised']};
    selection-color: {c['text']};
    outline: none;
}}

/* ===== CheckBox ===== */
QCheckBox {{ color: {c['text']}; spacing: {s['2']}px; }}
QCheckBox:focus {{ outline: {ring}px solid {c['accent']}; }}
QCheckBox::indicator {{
    width: {s['4']}px; height: {s['4']}px;
    border: 1px solid {c['line.strong']}; border-radius: {r['sm'] - 2}px;
}}
QCheckBox::indicator:checked {{ background-color: {c['accent']}; border-color: {c['accent']}; }}

/* ===== TabBar (geçici: adım 3'te NavList'e taşınacak) ===== */
QTabWidget::pane {{
    border: 1px solid {c['line']}; background-color: {c['surface']};
    border-radius: {r['md']}px;
}}
QTabBar::tab {{
    background-color: transparent; color: {c['text.muted']};
    border: none; border-bottom: 2px solid transparent;
    padding: {s['2']}px {s['3']}px;
    font-size: {ty['body']['size']}px;
}}
QTabBar::tab:hover {{ color: {c['text']}; background-color: {c['surface.raised']}; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom-color: {c['accent']}; }}
QTabBar::tab:focus {{ outline: {ring}px solid {c['accent']}; }}

/* ===== NavList (sol dikey gezinme) + ListRow ===== */
QListWidget, QTreeView, QListView {{
    background-color: transparent; border: none;
    color: {c['text']};
    outline: none;
}}
QListWidget:focus, QTreeView:focus {{ border: {ct['border']}px solid {c['accent']}; border-radius: {r['sm']}px; }}
QListWidget::item, QTreeView::item {{
    min-height: {h}px;
    padding: {s['1']}px {s['2']}px;
    border-radius: {r['sm']}px;
    color: {c['text']};
}}
QListWidget::item:hover, QTreeView::item:hover {{ background-color: {c['surface.raised']}; }}
QListWidget::item:selected, QTreeView::item:selected {{
    background-color: {c['accent.soft']}; color: {c['text']};
}}
QListWidget#navList::item {{
    min-height: {h + 6}px; padding-left: {s['3']}px; color: {c['text.muted']};
}}
QListWidget#navList::item:selected {{
    background-color: {c['surface.raised']}; color: {c['text']};
    border-left: 2px solid {c['accent']};
}}
QHeaderView::section {{
    background-color: {c['surface']}; color: {c['text.muted']};
    border: none; border-bottom: 1px solid {c['line']};
    padding: {s['1']}px {s['2']}px;
    font-size: {ty['label']['size']}px;
}}

/* ===== Chip / rozet ===== */
QLabel[role="badge"], QLabel#chip, QFrame[role="badge"] {{
    background-color: {c['surface.raised']}; color: {c['text.muted']};
    border: 1px solid {c['line']}; border-radius: {r['sm']}px;
    padding: 2px {s['2']}px;
    font-size: {ty['label']['size']}px; font-family: {f['mono']};
}}
QLabel[role="badge"][tone="accent"] {{ color: {c['accent']}; }}
QLabel[role="badge"][tone="ok"]     {{ color: {c['ok']}; }}
QLabel[role="badge"][tone="warn"]   {{ color: {c['warn']}; }}
QLabel[role="badge"][tone="danger"] {{ color: {c['danger']}; }}

/* ===== Toast / StatusDot ===== */
QFrame[role="toast"] {{
    background-color: {c['surface.raised']}; color: {c['text']};
    border: 1px solid {c['line.strong']}; border-radius: {r['md']}px;
    padding: {s['2']}px {s['3']}px;
}}
QLabel[role="statusDot"] {{ color: {c['text.muted']}; font-size: {ty['label']['size']}px; }}
QLabel[role="statusDot"][tone="ok"]     {{ color: {c['ok']}; }}
QLabel[role="statusDot"][tone="warn"]   {{ color: {c['warn']}; }}
QLabel[role="statusDot"][tone="danger"] {{ color: {c['danger']}; }}

/* ===== Reader (markdown yüzeyi) ===== */
QTextBrowser[role="reader"], QTextBrowser#reader {{
    background-color: {c['surface']}; color: {c['text']};
    border: 1px solid {c['line']}; border-radius: {r['md']}px;
    padding: {s['3']}px;
}}

/* ===== Terminal ===== */
QPlainTextEdit[role="terminal"], QTextEdit[role="terminal"],
QTextBrowser[role="terminal"], QWidget#terminal {{
    background-color: {c['terminal']}; color: {c['text']};
    font-family: {f['mono']}; font-size: {ty['mono']['size']}px;
    border: 1px solid {c['line']}; border-radius: {r['sm']}px;
}}

/* ===== CommandPalette ===== */
QFrame[role="palette"], QWidget#palette {{
    background-color: {c['surface']};
    border: 1px solid {c['line.strong']};
    border-radius: {r['lg']}px;
}}

/* ===== Splitter: görünür ama sessiz (kontrast ≥ 3:1) ===== */
QSplitter::handle {{ background-color: {c['line.strong']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}
QSplitter::handle:hover      {{ background-color: {c['accent']}; }}

/* ===== ScrollBar ===== */
QScrollBar:vertical {{
    background: transparent; width: {s['3']}px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['line.strong']}; border-radius: {s['1']}px; min-height: {s['5']}px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
QScrollBar:horizontal {{
    background: transparent; height: {s['3']}px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {c['line.strong']}; border-radius: {s['1']}px; min-width: {s['5']}px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c['accent']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ===== Menü ===== */
QMenu {{
    background-color: {c['surface']}; color: {c['text']};
    border: 1px solid {c['line.strong']}; border-radius: {r['sm']}px;
    padding: {s['1']}px;
}}
QMenu::item {{ padding: {s['1']}px {s['3']}px; border-radius: {r['sm'] - 2}px; }}
QMenu::item:selected {{ background-color: {c['surface.raised']}; }}
"""


def apply_design_system(app, theme: str = "dark", density: str = "compact") -> str:
    """Uygulama düzeyinde **tek** `setStyleSheet` girişi.

    `app` bir `QApplication`'dır. Üretilen QSS hem uygulanır hem döndürülür
    (test ve `scripts/ui_audit.py` döndürülen metni ölçer).
    Yalnızca ana iş parçacığından çağrılmalıdır.
    """
    qss = build_qss(get_tokens(theme, density))
    app.setStyleSheet(qss)
    return qss
