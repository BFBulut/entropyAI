"""İkon katmanı — QtAwesome (MIT) üzerinden Codicons ailesi.

Neden: denetimde arayüzde **376 emoji kullanımı / 76 farklı emoji** ve **0 `QIcon`**
ölçüldü. Emoji renklidir (tek vurgulu paleti bozar), platforma göre farklı çizilir
(kullanıcının makinesinde "tofu" kutusu çıktığı için `apply_emoji_font_fallback`
yaması gerekmişti), ölçeklenmez ve durum alamaz.

Aile: Microsoft Codicons (`msc` öneki, CC BY 4.0) — masaüstü/geliştirici araç
diline en yakın olan. Yedek aile Phosphor (`ph`, MIT).

Kullanım:

    from entropy.ui.design import icon, TOKENS
    btn.setIcon(icon("book", color=TOKENS["color"]["text.muted"]))
    btn.setAccessibleName("Raporlar")   # ikon düğmelerinde ZORUNLU (WCAG)

QtAwesome kurulu değilse `icon()` **boş bir `QIcon`** döndürür; arayüz çökmez,
yalnızca ikon görünmez. Kurulum: `pip install qtawesome` (pyproject `extras`).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "icon",
    "icon_for_emoji",
    "qtawesome_available",
    "EMOJI_ICON_MAP",
    "ICON_FAMILY",
    "font_data_dirs",
]

ICON_FAMILY = "msc"  # Codicons
FALLBACK_FAMILY = "ph"  # Phosphor

# --------------------------------------------------------------------------- #
# Emoji → ikon eşlemesi
#
# Denetimde sayılan 76 farklı emojinin en sık kullanılan 44'ü (kullanım
# sayısına göre sıralı; toplam kullanımın ~%90'ı). Kalan kuyruk sonraki
# adımlarda eklenecek. Anahtar emojinin kendisi değil, **kod noktasıdır**:
# marka/kodlama kazalarını önler ve kaynak dosyada emoji bırakmaz.
# --------------------------------------------------------------------------- #
EMOJI_ICON_MAP: Dict[str, str] = {
    "\U0001F3AF": "target",           # hedef / yetenekler
    "\U0001F3E2": "organization",     # ofis
    "✓": "check",                # onay
    "\U0001F4C1": "folder",
    "\U0001F4C4": "file",
    "✕": "close",
    "\U0001F916": "robot",            # ajan
    "\U0001F4D1": "files",            # sekmeli belge
    "\U0001F4CC": "pin",
    "\U0001F9E0": "circuit-board",    # bilişsel hafıza
    "\U0001F4C5": "calendar",
    "\U0001F4D6": "book",
    "\U0001F50C": "plug",             # MCP
    "\U0001F5C2": "folder-opened",
    "\U0001F5D1": "trash",
    "\U0001F4DA": "library",          # raporlar
    "\U0001F4AC": "comment",          # sohbet
    "\U0001F4D8": "book",
    "\U0001F4E5": "inbox",
    "\U0001F310": "globe",
    "\U0001F33F": "beaker",           # damıtma / deneysel
    "\U0001F7E2": "circle-filled",    # durum: iyi (renk belirteçten gelir)
    "\U0001F4CE": "link",             # ek dosya
    "\U0001F50D": "search",
    "\U0001F9D8": "layout",           # zen kipi
    "❌": "error",
    "\U0001F534": "circle-filled",    # durum: hata
    "⚡": "zap",
    "⚙": "gear",
    "\U0001F517": "link",
    "\U0001F4C2": "folder-opened",
    "♻": "refresh",
    "\U0001F5D3": "calendar",
    "\U0001F514": "bell",
    "⚖": "law",                  # değerlendirme
    "\U0001F3F7": "tag",
    "\U0001F52E": "telescope",        # öngörü
    "✏": "edit",
    "⚠": "warning",
    "\U0001F9E9": "extensions",
    "\U0001F7E1": "circle-filled",    # durum: uyarı
    "\U0001F4CA": "graph",
    "\U0001F4BB": "device-desktop",   # terminal
    "⏰": "clock",                # görevler
}


def qtawesome_available() -> bool:
    """QtAwesome içe aktarılabiliyor mu (paketlenmiş .exe'de de geçerli kontrol)."""
    try:
        import qtawesome  # noqa: F401
    except Exception:
        return False
    return True


def _qta():
    try:
        import qtawesome as qta
    except Exception:
        return None
    return qta


def icon(name: str, color: Optional[str] = None, **options: Any):
    """Codicons ailesinden bir `QIcon` döndürür.

    `name` önek içermeyen ikon adıdır (`"book"`, `"target"`). `color` bir
    belirteç değeri olmalıdır (`TOKENS["color"]["text.muted"]`); düz onaltılık
    yazmak yasaktır. QtAwesome yoksa veya ad bulunamazsa boş `QIcon` döner.
    """
    from PySide6.QtGui import QIcon

    qta = _qta()
    if qta is None:
        return QIcon()
    if color is not None:
        options.setdefault("color", color)
    for family in (ICON_FAMILY, FALLBACK_FAMILY):
        try:
            return qta.icon(f"{family}.{name}", **options)
        except Exception:
            continue
    return QIcon()


def icon_for_emoji(emoji: str, color: Optional[str] = None, **options: Any):
    """Bir emojinin ikon karşılığını döndürür (göç sırasında kullanılır).

    Eşleme tablosunda yoksa boş `QIcon` döner — bu, göçün eksik kaldığı yeri
    `scripts/ui_audit.py` üzerinden görünür kılar.
    """
    from PySide6.QtGui import QIcon

    name = EMOJI_ICON_MAP.get(emoji)
    if not name:
        return QIcon()
    return icon(name, color=color, **options)


def font_data_dirs() -> list[str]:
    """QtAwesome font/charmap dizinleri — `EntropyAI.spec` `datas` girdisi için.

    Bilinen paketleme sorunu (spyder-ide/qtawesome#78): PyInstaller ile font
    dosyaları paketlenmezse ikonlar boş çıkar. Spec bu listeyi kullanır.
    """
    qta = _qta()
    if qta is None:
        return []
    import os

    base = os.path.dirname(qta.__file__)
    return [os.path.join(base, "fonts")]
