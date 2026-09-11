"""Tasarım belirteçleri — tek kaynak.

Kaynak: `docs/reports/2026-09-10_Faz11_Arastirma_D_Arayuz_Tasarim_Denetimi.md` §3.
Denetim şu üç kök nedeni ölçtü: 99 farklı hex renk, 223 yerel `setStyleSheet`,
9 yazı boyutu, 58 dolgu kombinasyonu, 0 odak halkası, 1,39:1 kenarlık kontrastı.
Bu dosya bunların tümünün karşısına **12 renk + 4 tipografi kademesi (+mono) +
6 boşluk + 3 yarıçap + 5 durum** koyar.

Ölçülen kontrast oranları (sRGB göreli parlaklık, WCAG 2.x formülü;
`scripts/ui_audit.py --contrast` ile yeniden üretilir):

| Çift (koyu tema)                    | Oran  | Eşik | Sonuç |
|-------------------------------------|------:|-----:|-------|
| `text` / `bg`                       | 16,45 |  4,5 | ✓     |
| `text` / `surface`                  | 15,10 |  4,5 | ✓     |
| `text.muted` / `surface`            |  7,45 |  4,5 | ✓ (eski `#484F58` 2,06 idi) |
| `line.strong` / `surface`           |  3,02 |  3,0 | ✓ (eski `#1F2B42` 1,39 idi) |
| `line.strong` / `bg`                |  3,29 |  3,0 | ✓     |
| `accent` / `surface`                |  8,79 |  4,5 | ✓     |
| `accent.ink` / `accent`             |  9,35 |  4,5 | ✓     |
| `ok` / `surface`                    |  9,96 |  4,5 | ✓     |
| `warn` / `surface`                  |  9,57 |  4,5 | ✓     |
| `danger` / `surface`                |  6,45 |  4,5 | ✓     |

Kroma (max(RGB)-min(RGB)) notu: eski vurgular saf tayf rengiydi (255).
Yeni `accent` 179, `ok` 130, `warn` 157, `danger` 120 — "neon" imzası kırıldı.

Kurallar (ihlali `scripts/ui_audit.py` ile yakalanır):
* Vurgu rengi ekranın en fazla %10'unda kullanılır (60-30-10).
* `ok/warn/danger` **yalnızca durum** anlatır, dekorasyon değildir.
* Mor tamamen kaldırıldı (dört farklı mor vardı, hiçbiri anlam taşımıyordu).
* Graf tuvalinin kategori paleti ayrı bir `viz.*` ailesidir, bu 12'ye karışmaz.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

__all__ = [
    "TOKENS",
    "DARK_TOKENS",
    "LIGHT_TOKENS",
    "get_tokens",
    "resolve",
    "relative_luminance",
    "contrast_ratio",
    "CONTRAST_REQUIREMENTS",
]


# --------------------------------------------------------------------------- #
# Koyu tema (varsayılan)
# --------------------------------------------------------------------------- #
DARK_TOKENS: Dict[str, Any] = {
    "name": "dark",
    "color": {
        # 8 çekirdek yüzey/metin
        "bg": "#0B0F14",              # uygulama zemini
        "surface": "#121924",         # panel/kart
        "surface.raised": "#1A2431",  # hover, seçili, üst kademe
        "line": "#232E3D",            # dekoratif ayraç
        "line.strong": "#5A6676",     # denetim sınırı (WCAG 1.4.11 ≥ 3:1)
        # Faz 13-A kapanış: `line.strong` yalnızca `surface`/`bg` üstünde 3:1
        # tutuyor; yükseltilmiş yüzeyde (kart hover, digest başlık şeridi
        # `line` zemini) 2,35:1'e düşüyordu. Bu belirteç o yüzeyler için.
        "line.onraised": "#7C8798",   # yükseltilmiş yüzeyde denetim sınırı
        "text": "#E7EEF7",            # gövde
        "text.muted": "#9AAABE",      # ikincil etiket
        "accent": "#4CC2FF",          # TEK vurgu: seçili, bağlantı, odak halkası
        "accent.ink": "#08131B",      # dolu vurgu üstündeki metin
        # 3 anlamsal durum
        "ok": "#57D9A3",
        "warn": "#E8B84B",
        "danger": "#F0787A",
        # Terminal yüzeyi zeminden bir kademe koyu (mono okuma alanı)
        "terminal": "#080C11",
        # Vurgunun soluk zemini (seçili satır, chip dolgusu)
        "accent.soft": "#12293A",
    },
    # Görselleştirme ailesi (`viz.*`): graf tuvali, diff boyaması ve akış
    # olayları. Bu aile arayüzün 12 rengine KARIŞMAZ; yalnızca veri kodlar
    # (denetim §3.1). Kroma bilerek düşük tutulur, "neon" imzası yoktur.
    "viz": {
        "add": "#57D9A3",       # diff: eklenen satır (ok ile aynı)
        "del": "#F0787A",       # diff: silinen satır (danger ile aynı)
        "hunk": "#4CC2FF",      # diff: bölüm başlığı (accent)
        "meta": "#9AAABE",      # diff: üstbilgi (text.muted)
        # Düğüm/olay türleri — ayırt edilebilir ama düşük kromalı yedi ton.
        "kind1": "#8E9BF0",     # ofis
        "kind2": "#4CC2FF",     # ajan
        "kind3": "#57D9A3",     # rapor
        "kind4": "#E8B84B",     # karar
        "kind5": "#D9B26A",     # bulgu
        "kind6": "#D98BC0",     # görev
        "kind7": "#6FB6E8",     # proje
        "neutral": "#9AAABE",   # bilinmeyen tür
    },
    "space": {"1": 4, "2": 8, "3": 12, "4": 16, "5": 24, "6": 32},
    "radius": {"sm": 6, "md": 10, "lg": 14},
    "type": {
        "title": {"size": 18, "line": 24, "weight": 600},
        "heading": {"size": 14, "line": 20, "weight": 600},
        "body": {"size": 13, "line": 20, "weight": 400},
        "label": {"size": 11, "line": 16, "weight": 500},
        "mono": {"size": 13, "line": 18, "weight": 400},
    },
    "font": {
        # Sans yedeğinde mono, mono yedeğinde sans YOKTUR (denetim D-15).
        "sans": '"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif',
        "mono": '"Cascadia Mono",Consolas,monospace',
    },
    "control": {
        "height": 28,        # yoğun (compact)
        "height_icon": 28,   # WCAG 2.5.8 tabanı 24 px'in üstünde
        "focus_ring": 2,
        "border": 1,
        "min_target": 24,
        # Faz 14-E: üst şeritteki bölüm düğmesi (ikon + 11 px etiket).
        # 48 px'lik şeride sığar, WCAG 2.5.8 tabanının iki katıdır.
        "height_nav": 36,
    },
    # `nav`: bölüm şeridi ikonu (Faz 14-E, B notu §4 ölçüsü).
    "icon": {"inline": 16, "toolbar": 20, "nav": 24},
    "elevation": {
        # Qt'de gölge pahalı; panel için sınır tercih edilir.
        "0": None,
        "1": {"kind": "border", "width": 1, "color": "line"},
        "2": {"kind": "shadow", "blur": 24, "dy": 6, "color": "#000000", "alpha": 115},
    },
    "state": {
        # 5 durum belirteci — hepsi zorunlu (denetim D-03).
        "hover": {"bg": "surface.raised"},
        "pressed": {"bg": "surface.raised", "shift_y": 1},
        "focus": {"ring": "accent", "width": 2, "offset": 2},
        "disabled": {"opacity": 0.45, "fg": "text.muted"},
        "selected": {"bg": "surface.raised", "stripe": "accent", "stripe_width": 2},
    },
    "density": {
        # Kullanıcı ayarı (denetim D-18): control.height ve boşluk çarpanı.
        "compact": {"control_delta": 0, "space_scale": 1.0},
        "comfortable": {"control_delta": 4, "space_scale": 1.25},
    },
}


# --------------------------------------------------------------------------- #
# Açık tema iskeleti
#
# Faz 11-E adım 1'de yalnızca *iskelet*: aynı anahtar kümesi, aynı kontrast
# eşikleri. Arayüzde henüz bir seçici yok; `get_tokens("light")` ile alınır ve
# testlerle eşik uyumu korunur. Gerçek ekranda ince ayar sonraki adımda.
# --------------------------------------------------------------------------- #
def _light_overrides() -> Dict[str, str]:
    return {
        "bg": "#F5F7FA",
        "surface": "#FFFFFF",
        "surface.raised": "#E9EEF5",
        "line": "#D6DEE9",
        "line.strong": "#6B7788",
        "line.onraised": "#5E6A7B",
        "text": "#101720",
        "text.muted": "#55637A",
        "accent": "#0A6EB4",
        "accent.ink": "#FFFFFF",
        "ok": "#0E7A55",
        "warn": "#8A5A00",
        "danger": "#B02A24",
        "terminal": "#F0F3F8",
        "accent.soft": "#DDEBF8",
    }


def _light_viz_overrides() -> Dict[str, str]:
    """Açık temanın `viz.*` karşılığı (Faz 12-D.2).

    Koyu temanın parlak tonları beyaz zeminde 1,7–2,7:1 kalıyordu; gömülü
    belge köprüsü açık temada da WCAG 1.4.3'ü karşılamak zorunda olduğu için
    aile ayrı ayrı koyulaştırıldı (hepsi `surface` üzerinde ≥ 4,5:1).
    """
    return {
        "add": "#0E7A55",
        "del": "#B02A24",
        "hunk": "#0A6EB4",
        "meta": "#55637A",
        "kind1": "#4351B8",
        "kind2": "#0A6EB4",
        "kind3": "#0E7A55",
        "kind4": "#7A5A00",
        "kind5": "#7A5A1F",
        "kind6": "#9B3C77",
        "kind7": "#1C5E8C",
        "neutral": "#55637A",
    }


LIGHT_TOKENS: Dict[str, Any] = deepcopy(DARK_TOKENS)
LIGHT_TOKENS["name"] = "light"
LIGHT_TOKENS["color"].update(_light_overrides())
LIGHT_TOKENS["viz"].update(_light_viz_overrides())


TOKENS: Dict[str, Any] = DARK_TOKENS

_THEMES = {"dark": DARK_TOKENS, "light": LIGHT_TOKENS}


def get_tokens(theme: str = "dark", density: str = "compact") -> Dict[str, Any]:
    """Tema + yoğunluk uygulanmış **kopya** döndürür (çağıran güvenle değiştirebilir)."""
    base = _THEMES.get(theme)
    if base is None:
        raise KeyError(f"bilinmeyen tema: {theme!r} (dark|light)")
    t = deepcopy(base)
    dens = t["density"].get(density)
    if dens is None:
        raise KeyError(f"bilinmeyen yoğunluk: {density!r} (compact|comfortable)")
    t["control"]["height"] += dens["control_delta"]
    t["control"]["height_icon"] += dens["control_delta"]
    scale = dens["space_scale"]
    if scale != 1.0:
        t["space"] = {k: int(round(v * scale)) for k, v in t["space"].items()}
    t["density_name"] = density
    return t


def resolve(path: str, tokens: Dict[str, Any] | None = None) -> Any:
    """`"color.accent"` / `"type.body.size"` gibi noktalı yolu çözer.

    Renk anahtarlarının kendisi nokta içerebildiği için (`color.text.muted`)
    önce en uzun eşleşme denenir.
    """
    t = tokens or TOKENS
    parts = path.split(".")
    node: Any = t
    i = 0
    while i < len(parts):
        if not isinstance(node, dict):
            raise KeyError(path)
        # en uzun eşleşmeden kısaya doğru dene ("text.muted" gibi bileşik anahtarlar)
        for j in range(len(parts), i, -1):
            key = ".".join(parts[i:j])
            if key in node:
                node = node[key]
                i = j
                break
        else:
            raise KeyError(path)
    return node


# --------------------------------------------------------------------------- #
# Kontrast (WCAG 2.x)
# --------------------------------------------------------------------------- #
def _srgb_channel(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """sRGB göreli parlaklık (WCAG 2.x)."""
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        raise ValueError(f"geçersiz renk: {hex_color!r}")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb_channel(r) + 0.7152 * _srgb_channel(g) + 0.0722 * _srgb_channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """İki renk arasındaki WCAG kontrast oranı (1,0 – 21,0)."""
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def chroma(hex_color: str) -> int:
    """max(RGB) - min(RGB). 255 = saf tayf rengi ("neon" imzası)."""
    h = hex_color.strip().lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return max(r, g, b) - min(r, g, b)


#: (ön plan, zemin, eşik) — hem test hem denetim betiği bu listeyi kullanır.
CONTRAST_REQUIREMENTS = [
    ("text", "bg", 4.5),
    ("text", "surface", 4.5),
    ("text.muted", "surface", 4.5),
    ("text.muted", "bg", 4.5),
    ("line.strong", "surface", 3.0),
    ("line.strong", "bg", 3.0),
    # Yükseltilmiş yüzeylerde ghost kenarlığı (Faz 13-A kapanış ölçümü).
    ("line.onraised", "surface.raised", 3.0),
    ("line.onraised", "line", 3.0),
    ("accent", "surface", 4.5),
    ("accent", "bg", 4.5),
    ("accent.ink", "accent", 4.5),
    ("ok", "surface", 4.5),
    ("warn", "surface", 4.5),
    ("danger", "surface", 4.5),
]
