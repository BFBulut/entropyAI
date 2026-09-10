"""Entropy arayüz tasarım sistemi (belirteçler → QSS → ikonlar).

Tek giriş noktası: renk, boşluk, yarıçap, tipografi ve ikon **yalnızca** buradan
gelir. Widget dosyalarında düz onaltılık renk veya yerel `setStyleSheet` yazmak
Faz 11-E'den sonra yasaktır (bkz. `skills/ui-design/SKILL.md`).

Sözleşme (sonraki adımlar bu üç ada bağlanır):

    from entropy.ui.design import TOKENS, apply_design_system, icon

    TOKENS["color"]["accent"]          # belirteç okuma
    apply_design_system(app)           # uygulama düzeyinde tek stil sayfası
    icon("book", color=TOKENS["color"]["text.muted"])  # QIcon
"""

from entropy.ui.design.tokens import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    TOKENS,
    contrast_ratio,
    get_tokens,
    relative_luminance,
    resolve,
)
from entropy.ui.design.qss import apply_design_system, build_qss
from entropy.ui.design.icons import EMOJI_ICON_MAP, icon, icon_for_emoji, qtawesome_available

__all__ = [
    "TOKENS",
    "DARK_TOKENS",
    "LIGHT_TOKENS",
    "get_tokens",
    "resolve",
    "contrast_ratio",
    "relative_luminance",
    "build_qss",
    "apply_design_system",
    "icon",
    "icon_for_emoji",
    "EMOJI_ICON_MAP",
    "qtawesome_available",
]
