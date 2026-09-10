"""Gömülü belge köprüsü — HTML / SVG / JS gövdeleri için tek renk kaynağı.

Faz 12-D.2 (denetim D12-04, D12-05, T12-1, T12-2). Tasarım sistemi Faz 11-E'de
widget sınırında durmuştu: `QTextBrowser`'a gönderilen rapor/sohbet HTML'i,
mermaid SVG çizicileri ve `QWebEngineView` graf tuvali kendi "neon" paletlerini
taşıyordu (kroma 255 saf tayf renkler; en kötü çift 2,80:1). Bu modül o iki motorun renk ihtiyacını **`TOKENS` ve `TOKENS["viz"]`
üzerinden** karşılar; gövde kodunda düz onaltılık renk kalmaz.

İki motor, iki taşıma biçimi:

* **QTextBrowser / QTextDocument** — Qt zengin metin motoru CSS değişkenlerini,
  `rgba()`'yı ve `var()`'ı desteklemez. Bu yüzden belirteçler burada **Python
  tarafında düz onaltılığa açılır** (`palette()`), çağıran f-string'e gömer.
* **QWebEngineView (Chromium)** — tam CSS var. `css_variables()` bir `:root`
  bloğu, `js_palette_json()` ise aynı paletin JSON'u olarak enjekte edilir;
  JS mantığı sabit yerine bu tablodan okur.

Kullanım:

    from entropy.ui.design.embedded import palette, css_variables, js_palette_json

    p = palette()                 # {"bg": "#0B0F14", "accent": "#4CC2FF", ...}
    p["series"][0]                # kategorik seri rengi (viz.kind1)
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Dict, List

from entropy.ui.design.tokens import TOKENS, get_tokens

__all__ = [
    "palette",
    "series_colors",
    "css_variables",
    "js_palette_json",
    "EMBEDDED_CONTRAST_REQUIREMENTS",
    "READER_LAYOUT_CSS",
]


#: `viz.*` içinden kategorik seri sırası (pasta dilimi, akış düğümü, grup rengi).
#: Sıra bilerek sabittir: aynı veri her açılışta aynı rengi alır.
_SERIES_KEYS = ("kind2", "kind3", "kind4", "kind1", "kind7", "kind6", "kind5", "neutral")


def _theme(theme: str | None) -> str:
    """`None` ise kullanıcının seçtiği tema (QSettings) kullanılır."""
    if theme:
        return theme
    try:
        from entropy.ui.design.prefs import ui_theme

        return ui_theme()
    except Exception:
        return "dark"


def series_colors(theme: str | None = None) -> List[str]:
    """Kategorik seri paleti (8 ton, hepsi düşük kromalı, kontrastı ölçülmüş)."""
    viz = get_tokens(_theme(theme))["viz"]
    return [viz[k] for k in _SERIES_KEYS]


def palette(theme: str | None = None, density: str = "compact") -> Dict[str, Any]:
    """Gömülü gövdelerin kullanacağı **düz** renk/ölçü tablosu.

    Anahtar adları motor bağımsızdır; `css_variables()` bunları `--viz-<ad>`
    değişkenine, `js_palette_json()` aynı adla JS nesnesine çevirir.
    """
    theme = _theme(theme)
    t = get_tokens(theme, density)
    c = t["color"]
    v = t["viz"]
    return {
        # Yüzeyler — gömülü belge uygulamanın yüzeyiyle AYNI zemini kullanır
        # (denetim D12-04: üç farklı siyah vardı).
        "bg": c["bg"],
        "surface": c["surface"],
        "raised": c["surface.raised"],
        "terminal": c["terminal"],
        # Çizgi / metin
        "line": c["line"],
        "line_strong": c["line.strong"],
        "text": c["text"],
        "text_muted": c["text.muted"],
        # Vurgu ve durumlar (tek vurgu kuralı)
        "accent": c["accent"],
        "accent_ink": c["accent.ink"],
        "accent_soft": c["accent.soft"],
        "ok": c["ok"],
        "warn": c["warn"],
        "danger": c["danger"],
        # Görselleştirme ailesi
        "add": v["add"],
        "del": v["del"],
        "hunk": v["hunk"],
        "meta": v["meta"],
        "neutral": v["neutral"],
        "series": [v[k] for k in _SERIES_KEYS],
        # Tipografi (CSS dizeleri)
        "font_sans": t["font"]["sans"],
        "font_mono": t["font"]["mono"],
        "size_body": t["type"]["body"]["size"],
        "size_label": t["type"]["label"]["size"],
        "size_heading": t["type"]["heading"]["size"],
        "radius": t["radius"]["md"],
        "radius_sm": t["radius"]["sm"],
        "space": t["space"],
        "theme": theme,
    }


class LivePalette(Mapping):
    """Tema degisince KENDILIGINDEN donen palet gorunumu.

    Faz 12-F QA bulgusu: 10 arayuz modulu `_P = palette()` diyerek paleti
    ICE AKTARMA aninda donduruyordu; kullanici calisirken acik temaya
    gecince gomulu HTML govdeleri (rapor okuyucu, sohbet balonlari, graf)
    KOYU kalyordu. Bu sinif `_P["bg"]` kullanimini bozmadan her okumada
    guncel temayi cozer.
    """

    __slots__ = ("_density",)

    def __init__(self, density: str = "compact") -> None:
        self._density = density

    def _snapshot(self) -> Dict[str, Any]:
        return palette(None, self._density)

    def __getitem__(self, key: str) -> Any:
        return self._snapshot()[key]

    def __iter__(self):
        return iter(self._snapshot())

    def __len__(self) -> int:
        return len(self._snapshot())

    def __repr__(self) -> str:  # pragma: no cover - hata ayiklama kolayligi
        return f"LivePalette(theme={self._snapshot()['theme']!r})"


def live_palette(density: str = "compact") -> "LivePalette":
    """Modul duzeyinde guvenle saklanabilen, temaya CANLI baglanan palet."""
    return LivePalette(density)


def _flat_pairs(p: Dict[str, Any]):
    for key, value in p.items():
        if isinstance(value, str) and value.startswith("#"):
            yield key.replace("_", "-"), value
    for i, color in enumerate(p["series"], 1):
        yield f"series-{i}", color


def css_variables(theme: str | None = None, selector: str = ":root") -> str:
    """Chromium tarafı için `:root { --viz-*: … }` bloğu.

    Tema değişince tuvalin yeniden yüklenmesine gerek yoktur: tek bir
    `runJavaScript` ile bu blok değiştirilebilir (bkz. `knowledge_graph`).
    """
    lines = [f"        {selector} {{"]
    for name, color in _flat_pairs(palette(theme)):
        lines.append(f"            --viz-{name}: {color};")
    lines.append("        }")
    return "\n".join(lines)


def js_palette_json(theme: str | None = None) -> str:
    """Aynı paletin JS tarafı (kanvas 2D bağlamı CSS değişkeni okuyamaz)."""
    p = palette(theme)
    payload = {k: v for k, v in p.items() if isinstance(v, str) and v.startswith("#")}
    payload["series"] = list(p["series"])
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


#: Gömülü kontrast kapısı (`scripts/ui_audit.py --> embedded_contrast_failures`).
#: (ön plan anahtarı, zemin anahtarı, eşik) — WCAG 1.4.3 metin 4,5; 1.4.11 sınır 3,0.
EMBEDDED_CONTRAST_REQUIREMENTS = [
    ("text", "bg", 4.5),
    ("text", "surface", 4.5),
    ("text_muted", "surface", 4.5),
    ("accent", "surface", 4.5),
    ("ok", "surface", 4.5),
    ("warn", "surface", 4.5),
    ("danger", "surface", 4.5),
    ("line_strong", "surface", 3.0),
    ("add", "surface", 4.5),
    ("del", "surface", 4.5),
    ("hunk", "surface", 4.5),
    ("meta", "surface", 4.5),
    ("neutral", "surface", 4.5),
]


def READER_LAYOUT_CSS() -> str:  # noqa: N802 — CSS parçası, sınıf değil
    """Okuma yüzeyinin **taşma** kuralları (denetim D12-09).

    Qt zengin metin motoru `overflow-x` bilmez; yatay kaydırma ancak içerik
    kutudan geniş olduğunda çıkar. Bu yüzden çözüm sarmadır: `pre`/`code`
    sarılır, gömülü SVG ve görseller genişliğe uyar.
    """
    return """
    pre, pre code {
        white-space: pre-wrap;
        word-wrap: break-word;
        word-break: break-word;
    }
    code { white-space: pre-wrap; word-wrap: break-word; }
    img, svg { max-width: 100%; }
    table { table-layout: fixed; }
    td, th { word-wrap: break-word; }
    """


_ = TOKENS  # modül belirteç kaynağına bağlıdır (içe aktarma kasten korunur)
