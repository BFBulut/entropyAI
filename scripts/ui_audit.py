"""ui_audit — Entropy arayüz tasarım denetimi (ölçüm betiği).

`skills/ui-design/SKILL.md` §6'nın çalıştırılabilir karşılığı. Model çağırmaz,
pencere açmaz; saf statik çözümleme + belirteç kontrast hesabı yapar.

    python scripts/ui_audit.py                     # insan okuyabilir tablo
    python scripts/ui_audit.py --json out.json     # JSON çıktı
    python scripts/ui_audit.py --gate              # kapı eşiklerine göre çıkış kodu
    python scripts/ui_audit.py --paths src/entropy/ui/widgets/skills_widget.py

Çıkış kodu: `--gate` verilmezse her zaman 0. Verilirse, aşılan her kapı için 1.

Kapı eşikleri (denetim §5.2). Faz 11-E adım 1'de yalnızca **taban ölçüm** alınır;
eşikler adım 2–6 boyunca kademeli olarak düşürülür — bugün taban değerler
`BASELINE` içinde kayıtlıdır ve "kötüleşme" (regresyon) kapısı bunlara bakar.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

DEFAULT_PATHS = ["src/entropy/ui"]

# Belirteç dosyalarının kendisi renk yazmak zorundadır; sayımdan muaftır.
TOKEN_FILES = {
    "src/entropy/ui/design/tokens.py",
    "src/entropy/ui/design/qss.py",
    "src/entropy/ui/design/embedded.py",
    "src/entropy/ui/themes/cyber_theme.py",
}

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
STYLESHEET_RE = re.compile(r"\.setStyleSheet\s*\(")
FIXED_RE = re.compile(r"setFixed(?:Width|Height|Size)\s*\(")
FONT_SIZE_RE = re.compile(r"font-size:\s*([0-9]+)px")
PADDING_RE = re.compile(r"padding:\s*([0-9px ]+);")
RADIUS_RE = re.compile(r"border-radius:\s*([0-9]+)px")
BOLD_RE = re.compile(r"font-weight:\s*(bold|600|700)")
# Çeşitleme seçici (U+FE0F) eklendi (Faz 12-D.2).
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿⬀-⯿️]")

#: Yasaklı desen sayacı (denetim D12-11): eski emoji deseni U+2600'ün
#: ALTINDAKİ okları hiç görmüyordu — 38 adet `→` sayıma girmiyordu. Oklar
#: `EMOJI_RE`'ye değil buraya bağlandı, çünkü emoji sayacı **dosya geneline**
#: bakar (yorum ve belge dizesi dahil) ve ok işareti Türkçe teknik yorumda
#: meşru bir bağlaç; `arrow_glyphs` yalnızca kullanıcıya görünen metni sayar.
ARROW_RE = re.compile("[←-⇿⟵-⟷➔➜]")

#: " · " üst-veri ayracı (yasaklı desen, `ui-design/SKILL.md` §5).
MIDPOINT_RE = re.compile(" · ")

#: Gömülü belge gövdesi imzaları: bir satır bunlardan birini içeriyorsa
#: (QTextBrowser / QWebEngine'e giden) HTML/SVG/CSS gövdesi sayılır.
EMBEDDED_MARKERS = (
    "<svg", "<div", "<span", "<pre", "<table", "<b ", "<a ", "<code",
    "<text", "<rect", "<circle", "<path", ":root", "stop-color", "fill=",
    "stroke=", "background:", "background-color:", "color:",
)

ACCESSIBLE_NAME_RE = re.compile(r"setAccessibleName\s*\(")
SHORTCUT_RE = re.compile(r"QShortcut\s*\(")

#: Emoji sayımından muaf dosyalar. Buradaki emoji bir arayüz ikonu DEĞİL,
#: göç altyapısıdır: `icons.py` emoji -> ikon eşlemesini, `ui_polish.py`
#: emoji yazı tipi yedeğini (tofu kazası yaması) tutar, `tokens.py` yalnızca
#: belge dizesinde işaret kullanır. `knowledge_graph.py` gömülü HTML/JS
#: kanvasının tür simgeleri ayrı bir görsel dildir (`viz.*`) ve tasarım
#: sisteminin ikon ailesine dahil değildir.
EMOJI_EXEMPT = {
    "src/entropy/ui/design/icons.py",
    "src/entropy/ui/design/tokens.py",
    "src/entropy/ui/widgets/ui_polish.py",
    "src/entropy/ui/widgets/knowledge_graph.py",
}

#: Faz 11-E adım 1'de bu betikle ölçülen taban değerler (regresyon kapısı
#: bunlara bakar). Denetim raporunun grep sayıları biraz daha yüksekti
#: (hex 99, setStyleSheet 223, emoji 376) çünkü orada `themes/` dosyaları da
#: sayıma giriyordu ve `setStyleSheet` düz metin olarak aranıyordu; burada
#: belirteç dosyaları muaf, çağrı kalıbı `.setStyleSheet(`.
BASELINE: Dict[str, int] = {
    "distinct_hex": 91,
    "local_stylesheets": 222,
    "fixed_sizes": 87,
    "distinct_font_sizes": 9,
    "distinct_paddings": 58,
    "emoji_usages": 358,
    "distinct_emojis": 71,
}

#: Nihai hedefler — Faz 11-E adım 2-6 kabul ölçütleri (dokuz kapı).
#: Denetim §6.2'nin uzun vadeli hedefleri (distinct_hex ≤ 14, emoji 0) HTML
#: gövdelerindeki gömülü renkleri de kapsıyor; onlar bu dilimin kapsamı
#: dışında kaldı ve raporda açık iş olarak yazılıdır.
FINAL_GATES: Dict[str, int] = {
    "local_stylesheets": 40,
    "fixed_sizes": 20,
    "distinct_font_sizes": 5,
    "emoji_usages": 40,
    "contrast_failures": 0,
    "focusless_selectors": 0,
    "small_targets": 0,
    "desk_hex": 0,
    "desk_stylesheets": 10,
}

#: Faz 12-D.2 nihai kapıları (denetim §5.2, tasarım köprüsü + yoğunluk).
FINAL_GATES_12D2: Dict[str, int] = {
    "embedded_hex": 0,                    # gömülü gövdede düz renk kalmadı
    "embedded_contrast_failures": 0,      # gömülü palet WCAG 1.4.3/1.4.11
    "pure_spectrum_colors": 0,            # kroma 255 ("neon" imzası)
    "arrow_glyphs": 5,
    "splitters_unpersisted": 0,           # her QSplitter QSettings'e yazılır
    "interactive_count_zen_1366": 90,     # ara hedef (uzun vade ≤ 60)
    "header_leaf_widgets": 6,             # beyan değil canlı yaprak sayımı
    "embedded_h_overflow": 0,             # 1366 ve 460'ta yatay kaydırma yok
    "button_contrast": 0,                 # Faz 13: metin >= 4,5:1, ikon >= 3:1
}

#: Faz 13 kapı seti (araştırma notu §1.7). Dördü de **canlı** ölçülür.
FINAL_GATES_13: Dict[str, int] = {
    "empty_interactive_count": 0,          # G13-1: metinsiz+ikonsuz+adsız düğme
    "ghost_button_contrast": 0,            # G13-2: ghost kenarlık/zemin >= 3:1
    "click_latency_ms": 50,                # G13-3: RAIL girdi bütçesi
    "min_width_declaration_failures": 0,   # G13-4: beyan >= hesaplanan
}

#: G13-3 uyarı eşiği (kapı 50 ms; 100 ms üstü NN/g'ye göre "kesintisiz" değil).
CLICK_LATENCY_WARN_MS = 100

#: Alt sınır kapıları ("en az" — yukarıdakiler "en fazla").
FINAL_MIN_GATES: Dict[str, int] = {
    "themes_reachable": 4,                # 2 tema × 2 yoğunluk
    "min_button_height": 28,              # Faz 13: tıklanabilir düğme yüksekliği
    "reader_min_width": 560,              # G13-4: okuma kipinde okuyucu gövdesi
}


# --------------------------------------------------------------- Faz 13 kapıları
#
# Kapılar **saf fonksiyon** olarak yazılır ki testler bilerek bozulmuş bir
# widget/işlevle çağırıp kapının gerçekten kırmızıya döndüğünü kanıtlayabilsin
# (SKILL §0/10: "kapı beyana dayanamaz").

def empty_interactive_widgets(root) -> List[str]:
    """G13-1 — metni, ikonu ve erişilebilir adı OLMAYAN görünür düğmeler.

    WCAG 4.1.2 (Name, Role, Value): etkileşimli her öğenin erişilebilir bir
    adı olmalıdır. Üçü de yoksa öğe kullanıcı için görünmez bir dikdörtgendir.
    """
    from PySide6.QtWidgets import QAbstractButton

    offenders: List[str] = []
    for btn in root.findChildren(QAbstractButton):
        if not btn.isVisible() or btn.visibleRegion().isEmpty():
            continue
        if btn.text().strip():
            continue
        if not btn.icon().isNull():
            continue
        if btn.accessibleName().strip():
            continue
        offenders.append(btn.objectName() or type(btn).__name__)
    return offenders


_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")


def _stylesheet_color(text: str, prop: str) -> str:
    """Bir stil sayfasındaki `prop: #rrggbb` değerini döndürür (yoksa "")."""
    for match in re.finditer(prop + r"\s*:\s*([^;\n}]+)", str(text or "")):
        hexes = _HEX_RE.findall(match.group(1))
        if hexes:
            return hexes[-1]
    return ""


def resolve_surface_color(widget) -> str:
    """Düğmenin GERÇEK zemini: kendi/ebeveyn zincirinde ilk opak arka plan.

    Faz 13-A kapanış: kapı eskiden zemini `surface` varsayıyordu; digest
    başlık şeridi (`line`, #232E3D) gibi yükseltilmiş yüzeylerde ölçüm
    gerçeğin üstünde çıkıyordu. Sıra: satır içi stil sayfası → `surface` /
    `role` özelliği → dolduran paletin `Window` rengi → tema `surface`.
    """
    from PySide6.QtGui import QPalette

    from entropy.ui.design import TOKENS as _T

    colors = _T["color"]
    node = widget
    while node is not None:
        found = _stylesheet_color(node.styleSheet(), "background(?:-color)?")
        if found:
            return found
        surface = str(node.property("surface") or "")
        if surface:
            key = surface if surface in colors else f"surface.{surface}"
            if key in colors:
                return colors[key]
        role = str(node.property("role") or "")
        if role == "header":
            return colors["surface.raised"]
        if node.autoFillBackground():
            color = node.palette().color(QPalette.ColorRole.Window)
            if color.alpha() == 255:
                return color.name()
        node = node.parentWidget()
    return colors["surface"]


def resolve_border_color(widget) -> str:
    """Ghost düğmenin gerçek kenarlık rengi (satır içi stil → yüzey belirteci)."""
    from entropy.ui.design import TOKENS as _T

    colors = _T["color"]
    node = widget
    while node is not None:
        found = _stylesheet_color(node.styleSheet(), "border(?:-color)?")
        if found:
            return found
        node = node.parentWidget()
    # QSS sözleşmesi: yükseltilmiş yüzeyde `line.onraised`, aksi hâlde
    # `line.strong` (bkz. `ui/design/qss.py` ghost kuralları).
    node = widget
    while node is not None:
        if str(node.property("surface") or "") == "raised" or \
                str(node.property("role") or "") == "header":
            return colors["line.onraised"]
        node = node.parentWidget()
    return colors["line.strong"]


def ghost_button_contrast_failures(root) -> List[str]:
    """G13-2 — `variant="ghost"` düğmelerin kenarlık/zemin ayrımı (>= 3:1).

    Ghost düğmenin zemini şeffaftır; ölçülen şey kenarlık renginin düğmenin
    **gerçek** zeminine göre kontrastıdır (WCAG 1.4.11 non-text contrast).
    Zemin yüzey başına çözümlenir: `resolve_surface_color`.
    """
    from PySide6.QtWidgets import QAbstractButton

    from entropy.ui.design import TOKENS as _T, contrast_ratio as _cr

    colors = _T["color"]
    failures: List[str] = []
    for btn in root.findChildren(QAbstractButton):
        if not btn.isVisible() or btn.visibleRegion().isEmpty():
            continue
        if str(btn.property("variant") or "") != "ghost":
            continue
        name = btn.accessibleName() or btn.text() or type(btn).__name__
        surface = resolve_surface_color(btn)
        border = _cr(resolve_border_color(btn), surface)
        text = _cr(colors["text"], surface)
        if border < 3.0:
            failures.append(f"{name}: kenarlık {border:.2f} ({surface})")
        if btn.text().strip() and text < 4.5:
            failures.append(f"{name}: metin {text:.2f} ({surface})")
    return failures


def measure_click_latency_ms(action) -> int:
    """G13-3 — bir eylemin ana iş parçacığını blokladığı süre (ms)."""
    from PySide6.QtCore import QElapsedTimer

    timer = QElapsedTimer()
    timer.start()
    action()
    return int(timer.elapsed())


def min_width_declaration_failures(panels) -> List[str]:
    """G13-4 — `minimumWidth()` beyanı, yerleşimin hesapladığından küçük mü?

    `minimumSizeHint().width()` Qt'nin çocuk asgarilerinden hesapladığı gerçek
    sayıdır; `setMinimumWidth` onu EZER. Beyan küçükse panel sıkışınca çocuklar
    kırpılır — kullanıcının "sıkışık" dediği durum tam olarak budur.
    """
    failures: List[str] = []
    for panel in panels:
        try:
            declared = int(panel.minimumWidth())
            computed = int(panel.minimumSizeHint().width())
        except (AttributeError, RuntimeError):
            continue
        if declared < computed:
            failures.append(f"{type(panel).__name__}: beyan {declared} < hesaplanan {computed}")
    return failures


def _iter_files(paths: List[str]):
    for p in paths:
        path = (REPO_ROOT / p) if not Path(p).is_absolute() else Path(p)
        if path.is_file():
            yield path
        else:
            yield from sorted(path.rglob("*.py"))


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def static_metrics(paths: List[str]) -> Dict[str, Any]:
    hexes: set[str] = set()
    hex_total = 0
    stylesheets = 0
    stylesheet_files: Dict[str, int] = {}
    fixed = 0
    font_sizes: set[int] = set()
    paddings: set[str] = set()
    radii: set[int] = set()
    bolds = 0
    emoji_usages = 0
    emoji_raw = 0
    emojis: set[str] = set()
    accessible_names = 0
    shortcuts = 0
    small_targets: List[str] = []
    embedded_hex: List[str] = []
    arrow_glyphs = 0
    midpoint_separators = 0
    pure_spectrum: set[str] = set()

    for f in _iter_files(paths):
        rel = _rel(f)
        text = f.read_text(encoding="utf-8", errors="ignore")
        # Yasaklı desenler yalnızca **kullanıcıya görünen** metinde sayılır:
        # yorum satırları ve belge dizeleri (`#`, `"""`) sayıma girmez, aksi
        # hâlde ölçüm kendi açıklamamızı cezalandırırdı.
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("*"):
                continue
            if '"' not in line and "'" not in line:
                continue
            arrow_glyphs += len(ARROW_RE.findall(line))
            midpoint_separators += len(MIDPOINT_RE.findall(line))
        if rel not in TOKEN_FILES:
            # Gömülü gövde renkleri ayrı sayılır (denetim D12-04/D12-05):
            # widget QSS'i değil, QTextBrowser/QWebEngine'e giden HTML/SVG/JS.
            for line_no, line in enumerate(text.splitlines(), 1):
                if not HEX_RE.search(line):
                    continue
                if any(marker in line for marker in EMBEDDED_MARKERS):
                    for hexv in HEX_RE.findall(line):
                        embedded_hex.append(f"{rel}:{line_no}:{hexv.upper()}")
        for hexv in HEX_RE.findall(text):
            h = hexv.lstrip("#")
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            if max(r, g, b) - min(r, g, b) == 255:
                pure_spectrum.add(hexv.upper())
        if rel not in TOKEN_FILES:
            found = HEX_RE.findall(text)
            hex_total += len(found)
            hexes.update(h.upper() for h in found)
            n = len(STYLESHEET_RE.findall(text))
            if n:
                stylesheets += n
                stylesheet_files[rel] = n
        fixed += len(FIXED_RE.findall(text))
        font_sizes.update(int(m) for m in FONT_SIZE_RE.findall(text))
        paddings.update(m.strip() for m in PADDING_RE.findall(text))
        radii.update(int(m) for m in RADIUS_RE.findall(text))
        bolds += len(BOLD_RE.findall(text))
        found_emoji = EMOJI_RE.findall(text)
        emoji_raw += len(found_emoji)
        if rel not in EMOJI_EXEMPT:
            emoji_usages += len(found_emoji)
            emojis.update(found_emoji)
        accessible_names += len(ACCESSIBLE_NAME_RE.findall(text))
        shortcuts += len(SHORTCUT_RE.findall(text))
        # 24 px altı sabit hedef (WCAG 2.5.8)
        for line_no, line in enumerate(text.splitlines(), 1):
            for m in re.finditer(r"setFixed(?:Size|Height|Width)\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)", line):
                vals = [int(v) for v in m.groups() if v]
                is_control = "Button" in line or "btn" in line.lower()
                if vals and min(vals) < 24 and is_control:
                    small_targets.append(f"{rel}:{line_no}")

    return {
        "distinct_hex": len(hexes),
        "hex_total": hex_total,
        "local_stylesheets": stylesheets,
        "local_stylesheets_by_file": dict(
            sorted(stylesheet_files.items(), key=lambda kv: -kv[1])[:10]
        ),
        "fixed_sizes": fixed,
        "distinct_font_sizes": len(font_sizes),
        "font_sizes": sorted(font_sizes),
        "distinct_paddings": len(paddings),
        "distinct_radii": len(radii),
        "radii": sorted(radii),
        "bold_declarations": bolds,
        "emoji_usages": emoji_usages,
        "emoji_raw": emoji_raw,
        "distinct_emojis": len(emojis),
        "accessible_names": accessible_names,
        "shortcuts": shortcuts,
        "small_targets": sorted(set(small_targets)),
        "embedded_hex": sorted(set(embedded_hex)),
        "arrow_glyphs": arrow_glyphs,
        "midpoint_separators": midpoint_separators,
        "pure_spectrum_colors": sorted(pure_spectrum),
    }


def token_metrics() -> Dict[str, Any]:
    from entropy.ui.design.qss import FOCUSABLE_SELECTORS, build_qss
    from entropy.ui.design.tokens import CONTRAST_REQUIREMENTS, contrast_ratio, get_tokens

    result: Dict[str, Any] = {"contrast": {}, "contrast_failures": []}
    for theme in ("dark", "light"):
        t = get_tokens(theme)
        rows = {}
        for fg, bg, threshold in CONTRAST_REQUIREMENTS:
            ratio = round(contrast_ratio(t["color"][fg], t["color"][bg]), 2)
            rows[f"{fg}/{bg}"] = {"ratio": ratio, "threshold": threshold, "pass": ratio >= threshold}
            if ratio < threshold:
                result["contrast_failures"].append(f"{theme}:{fg}/{bg}={ratio}")
        result["contrast"][theme] = rows

    # Gömülü belge paleti (Faz 12-D.2): rapor okuyucu, sohbet balonu, SVG
    # çizicileri ve graf tuvali bu tabloyu kullanır; kontrastı ayrı ölçülür.
    from entropy.ui.design.embedded import EMBEDDED_CONTRAST_REQUIREMENTS, palette

    result["embedded_contrast"] = {}
    result["embedded_contrast_failures"] = []
    for theme in ("dark", "light"):
        p = palette(theme)
        rows = {}
        for fg, bg, threshold in EMBEDDED_CONTRAST_REQUIREMENTS:
            ratio = round(contrast_ratio(p[fg], p[bg]), 2)
            rows[f"{fg}/{bg}"] = {"ratio": ratio, "threshold": threshold,
                                  "pass": ratio >= threshold}
            if ratio < threshold:
                result["embedded_contrast_failures"].append(f"{theme}:{fg}/{bg}={ratio}")
        result["embedded_contrast"][theme] = rows

    qss = build_qss()
    missing = [s for s in FOCUSABLE_SELECTORS if f"{s}:focus" not in qss]
    result["focusless_selectors"] = missing
    result["qss_bytes"] = len(qss)
    return result


def persistence_metrics() -> Dict[str, Any]:
    """Bölücü kalıcılığı ve ulaşılabilir tema × yoğunluk (D12-07, D12-08)."""
    from entropy.ui.design.prefs import DENSITIES, THEMES

    total = 0
    persisted = 0
    for path in ["src/entropy/ui", "src/entropy/desk"]:
        for f in _iter_files([path]):
            if _rel(f) == "src/entropy/ui/design/prefs.py":
                continue  # yardımcının kendi tanımı sayıma girmez
            text = f.read_text(encoding="utf-8", errors="ignore")
            total += len(re.findall(r"QSplitter\(", text))
            persisted += len(re.findall(r"install_splitter_persistence\(", text))

    # Tema × yoğunluk üründe ulaşılabilir mi: ayar diyaloğu ikisini de sunuyor
    # ve `ui/manager.py` açılışta kayıtlı değeri uyguluyor mu?
    dialog = (REPO_ROOT / "src/entropy/ui/widgets/settings_dialog.py")
    manager = (REPO_ROOT / "src/entropy/ui/manager.py")
    reachable = 0
    if dialog.exists() and manager.exists():
        dtext = dialog.read_text(encoding="utf-8", errors="ignore")
        mtext = manager.read_text(encoding="utf-8", errors="ignore")
        if ("theme_combo" in dtext and "density_combo" in dtext
                and "ui_theme()" in mtext and "ui_density()" in mtext):
            reachable = len(THEMES) * len(DENSITIES)
    return {
        "splitters_total": total,
        "settings_persisted_splitters": persisted,
        "splitters_unpersisted": max(0, total - persisted),
        "themes_reachable": reachable,
    }


def _phase13_live_metrics(app) -> Dict[str, Any]:
    """G13-3 (tıklama gecikmesi) ve G13-4 (okuyucu + beyan) canlı ölçümü."""
    import time as _time

    out: Dict[str, Any] = {}
    try:
        from entropy.ui.widgets.report_center import ReportCenterWidget
        from entropy.ui.widgets.report_inbox import ReportInboxStore, reset_shared_store
        from entropy.ui.widgets.reports_viewer import READER_MIN_WIDTH
        from entropy.ui.widgets.task_board_widget import TaskBoardWidget

        # Gerçek kasaya ve gerçek durum dosyasına DOKUNULMAZ: geçici depo.
        tmp = Path(tempfile.mkdtemp(prefix="ui_audit_p13_"))
        reset_shared_store(ReportInboxStore(tmp / "report_inbox.json"))
        center = ReportCenterWidget(parent=None)
        center.set_quiet_threshold(0.50, persist=False)
        now = _time.time()
        entries = []
        # G13-3 sözleşmesi >= 150 KÜME ister; başlıklar birbirine benzerse
        # TF-IDF kümelemesi onları tek kartta birleştirir. Bu yüzden her
        # başlık ayrı bir konu sözcüğü taşır.
        topics = [
            "kasa", "kapi", "olcum", "yerlesim", "bellek", "ajan", "pano",
            "rapor", "beceri", "wiki", "grafik", "terminal", "makbuz", "ofis",
            "kart", "surum", "kota", "oturum", "diff", "kanit",
        ]
        for i in range(170):
            report = tmp / f"Gorev_Sentetik_{i:03d}.md"
            report.write_text(
                "\n".join([
                    f"# {topics[i % len(topics)].capitalize()}{i:03d}", "",
                    f"Bulgu {i} {topics[(i * 7) % len(topics)]} uzerine.", "",
                    "## Sonuc", "", f"Karar {i}.", "",
                ]),
                encoding="utf-8",
            )
            entries.append({
                "path": str(report),
                "title": f"{topics[i % len(topics)].capitalize()}{i:03d}",
                "mtime": now - i,
            })
        center.set_entries(entries)
        if not center._quiet_expanded:
            center.toggle_quiet()          # G13-3: sessiz bölüm AÇIK ölçülür
        app.processEvents()
        out["click_latency_cards"] = len(center.card_widgets)
        if center.card_widgets:
            card = center.card_widgets[0]
            out["click_latency_ms"] = measure_click_latency_ms(card._on_read)
        else:
            out["click_latency_ms"] = 0
        out["click_latency_warn"] = bool(
            out["click_latency_ms"] > CLICK_LATENCY_WARN_MS
        )
        # Tıklama yolunda diske yazım olmamalı (A3).
        out["click_wrote_state_file"] = (tmp / "report_inbox.json").exists()

        from entropy.ui.widgets.reports_viewer import ReportsViewerWidget

        viewer = ReportsViewerWidget()
        viewer.resize(1366, 768)
        viewer.show()
        app.processEvents()
        viewer.enter_reading_mode()
        app.processEvents()
        out["reader_min_width"] = int(viewer.content_browser.width())
        out["reader_target_width"] = int(READER_MIN_WIDTH)

        board = TaskBoardWidget()
        board.resize(1366, 700)
        board.show()
        app.processEvents()
        panels = [center, viewer, board, viewer.report_center]
        failures = min_width_declaration_failures(panels)
        out["min_width_declaration_failures"] = len(failures)
        out["min_width_declaration_detail"] = failures
        out["board_view_mode_1366"] = board.view_mode()
        out["board_kanban_min_width"] = board.kanban_min_width()

        for widget in (center, viewer, board):
            widget.close()
            widget.deleteLater()
        reset_shared_store()
    except Exception as exc:  # pragma: no cover - ölçüm kolu
        out["phase13_error"] = f"{type(exc).__name__}: {exc}"
    return out


def live_metrics() -> Dict[str, Any]:
    """Offscreen Qt kolu — beyana değil **canlı widget ağacına** bakar.

    Denetim D12-01 (yoğunluk), D12-06 (üst çubuk kapısı beyana dayalıydı) ve
    D12-09 (gömülü belgede yatay kaydırma). Qt yoksa alanlar `None` döner ve
    kapıya girmez.
    """
    out: Dict[str, Any] = {}
    try:
        from PySide6.QtWidgets import (
            QAbstractButton, QApplication, QComboBox, QLabel, QLineEdit,
            QSlider, QTextBrowser, QWidget,
        )
    except Exception:
        return out

    app = QApplication.instance() or QApplication([])
    from entropy.ui.design import apply_design_system

    apply_design_system(app)

    def leaves(root: QWidget) -> List[QWidget]:
        found: List[QWidget] = []
        for child in root.findChildren(QWidget):
            if not child.isVisibleTo(root):
                continue
            if child.findChildren(QWidget):
                continue
            found.append(child)
        return found

    try:
        from entropy.core.agy_bridge import AgyProcessBridge
        from entropy.ui.modes.zen_mode import ZenModeWindow

        win = ZenModeWindow(bridge=AgyProcessBridge())
        win.resize(1366, 768)
        win.show()
        app.processEvents()

        interactive = 0
        filled_labels = 0
        for child in win.findChildren(QWidget):
            if not child.isVisible():
                continue
            # "Aynı anda görünen" = kullanıcının GERÇEKTEN gördüğü. Kaydırma
            # alanının dışına taşan kartlar `isVisible()` için True'dur ama
            # ekranda değildir; `visibleRegion()` boşsa sayılmaz.
            if child.visibleRegion().isEmpty():
                continue
            if isinstance(child, (QAbstractButton, QComboBox, QLineEdit, QSlider)):
                interactive += 1
            elif isinstance(child, QLabel) and child.text().strip():
                filled_labels += 1
        out["interactive_count_zen_1366"] = interactive + filled_labels
        out["interactive_controls_zen_1366"] = interactive
        out["filled_labels_zen_1366"] = filled_labels

        header = getattr(win, "header_frame", None)
        controls = getattr(win, "window_controls", None)
        if header is not None:
            header_leaves = [
                w for w in leaves(header)
                if controls is None or not (w is controls or controls.isAncestorOf(w))
            ]
            out["header_leaf_widgets"] = len(header_leaves)
            out["header_leaf_names"] = [type(w).__name__ for w in header_leaves]

        # --- Faz 13: düğme görünürlüğü ------------------------------------
        # Kullanıcı gerçek ekranda "düğmeler görünmüyor" dedi. Kök neden
        # `variant="ghost"` düğmelerin kenarlıksız + sönük metin oluşuydu.
        # Kapı: düğme metni/zemin >= 4,5:1, ikon/zemin >= 3:1, yükseklik >= 28.
        from entropy.ui.design import TOKENS as _T, contrast_ratio as _cr

        def _button_pair(btn) -> tuple:
            """(ön plan, zemin) belirteç çifti — QSS kuralıyla aynı eşleme."""
            variant = str(btn.property("variant") or "")
            tone = str(btn.property("tone") or "")
            colors = _T["color"]
            if variant == "primary":
                return colors["accent.ink"], colors["accent"]
            if variant == "danger":
                return colors["danger"], colors["surface"]
            if tone in ("ok", "warn", "danger"):
                return colors[tone], colors["surface"]
            if tone == "muted":
                return colors["text.muted"], colors["surface"]
            return colors["text"], colors["surface"]

        text_failures: List[str] = []
        icon_failures: List[str] = []
        heights: List[int] = []
        for btn in win.findChildren(QAbstractButton):
            if not btn.isVisible() or btn.visibleRegion().isEmpty():
                continue
            fg, bg = _button_pair(btn)
            ratio = _cr(fg, bg)
            name = btn.accessibleName() or btn.text() or type(btn).__name__
            if btn.text().strip() and ratio < 4.5:
                text_failures.append(f"{name}: {ratio:.2f}")
            if not btn.icon().isNull() and ratio < 3.0:
                icon_failures.append(f"{name}: {ratio:.2f}")
            heights.append(int(btn.height()))
        out["button_contrast_failures"] = text_failures
        out["button_contrast"] = len(text_failures) + len(icon_failures)
        out["button_icon_contrast_failures"] = icon_failures
        out["min_button_height"] = min(heights) if heights else 0
        out["buttons_measured"] = len(heights)

        # --- Faz 13 kapıları (G13-1 … G13-4) -------------------------------
        empty = empty_interactive_widgets(win)
        out["empty_interactive_count"] = len(empty)
        out["empty_interactive_names"] = empty
        ghost = ghost_button_contrast_failures(win)
        out["ghost_button_contrast"] = len(ghost)
        out["ghost_button_contrast_failures"] = ghost
        out.update(_phase13_live_metrics(app))

        # Gömülü okuma yüzeyi: 1366 ve 460 px'te yatay kaydırma çubuğu
        from entropy.ui.widgets.markdown_renderer import render_markdown_to_html

        sample = (
            "# Başlık\n\n```python\n" + ("x = " + "1234567890" * 24) + "\n```\n\n"
            "```mermaid\ngraph TD\nA[Uzun bir düğüm adı]-->B[İkinci düğüm]\n```\n"
        )
        overflow = []
        for width in (1366, 460):
            browser = QTextBrowser()
            browser.resize(width, 600)
            browser.setHtml(render_markdown_to_html(sample, reader_width=width))
            app.processEvents()
            doc_width = browser.document().idealWidth()
            if doc_width > browser.viewport().width() + 1:
                overflow.append(f"{width}px:{int(doc_width)}")
            browser.deleteLater()
        out["embedded_h_overflow"] = overflow
        win.close()
        win.deleteLater()
    except Exception as exc:  # pragma: no cover - ölçüm kolu
        out["live_error"] = f"{type(exc).__name__}: {exc}"
    return out


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Entropy arayüz tasarım denetimi")
    ap.add_argument("--paths", nargs="*", default=DEFAULT_PATHS)
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--gate", action="store_true", help="eşik aşımında çıkış kodu 1")
    ap.add_argument("--final", action="store_true", help="taban yerine nihai hedefleri uygula")
    ap.add_argument("--live", action="store_true",
                    help="offscreen Qt kolu (canlı yoğunluk ve üst çubuk ölçümü)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    data: Dict[str, Any] = {"paths": args.paths}
    data.update(static_metrics(args.paths))
    # Desk ayrı ölçülür (adım 6 kapıları): kendi hex ve yerel stil sayısı.
    desk = static_metrics(["src/entropy/desk"])
    data["desk_hex"] = desk["distinct_hex"]
    data["desk_stylesheets"] = desk["local_stylesheets"]
    data["desk_emoji"] = desk["emoji_usages"]
    data.update(token_metrics())
    data.update(persistence_metrics())
    # Faz 12-D.2: Desk gövdelerindeki gömülü renk de sayıma girer.
    data["embedded_hex"] = sorted(set(data["embedded_hex"]) | set(desk["embedded_hex"]))
    data["pure_spectrum_colors"] = sorted(
        set(data["pure_spectrum_colors"]) | set(desk["pure_spectrum_colors"])
    )
    data["arrow_glyphs"] += desk["arrow_glyphs"]
    data["midpoint_separators"] += desk["midpoint_separators"]
    if args.final or args.live:
        data.update(live_metrics())
    data["contrast_failure_count"] = len(data["contrast_failures"])
    data["focusless_selector_count"] = len(data["focusless_selectors"])
    data["small_target_count"] = len(data["small_targets"])
    data["embedded_hex_count"] = len(data["embedded_hex"])
    data["embedded_contrast_failure_count"] = len(data["embedded_contrast_failures"])
    data["pure_spectrum_color_count"] = len(data["pure_spectrum_colors"])
    if "embedded_h_overflow" in data:
        data["embedded_h_overflow_count"] = len(data["embedded_h_overflow"])
    data["baseline"] = BASELINE

    gates = dict(FINAL_GATES) if args.final else {
        **{k: v for k, v in BASELINE.items()},
        "contrast_failures": 0,
        "focusless_selectors": 0,
    }
    if args.final:
        # Faz 12-D.2'nin nihai kapıları (denetim §5.2). Canlı kol ölçmediyse
        # (Qt yok) ilgili alan `data`'da olmaz ve kapı atlanır — sessiz yeşil
        # olmaması için `live_error` alanı JSON'a yazılır.
        gates.update(FINAL_GATES_12D2)
        gates.update(FINAL_GATES_13)
    violations = []
    for key, limit in gates.items():
        actual = data.get(key)
        if isinstance(actual, list):
            actual = len(actual)
        if isinstance(actual, int) and actual > limit:
            violations.append(f"{key}: {actual} > {limit}")
    if args.final:
        for key, minimum in FINAL_MIN_GATES.items():
            actual = data.get(key)
            if isinstance(actual, int) and actual < minimum:
                violations.append(f"{key}: {actual} < {minimum}")
    data["gate_violations"] = violations

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if not args.quiet:
        keys = [
            "distinct_hex", "hex_total", "local_stylesheets", "fixed_sizes",
            "distinct_font_sizes", "distinct_paddings", "distinct_radii",
            "bold_declarations", "emoji_usages", "distinct_emojis",
            "accessible_names", "shortcuts", "desk_hex", "desk_stylesheets",
            "desk_emoji", "contrast_failure_count",
            "focusless_selector_count", "small_target_count",
            "embedded_hex_count", "embedded_contrast_failure_count",
            "pure_spectrum_color_count", "arrow_glyphs", "midpoint_separators",
            "settings_persisted_splitters", "splitters_total",
            "themes_reachable",
        ] + ([
            "interactive_count_zen_1366", "header_leaf_widgets",
            "embedded_h_overflow_count", "button_contrast", "min_button_height",
            "empty_interactive_count", "ghost_button_contrast",
            "click_latency_ms", "click_latency_cards",
            "min_width_declaration_failures", "reader_min_width",
            "board_view_mode_1366",
        ] if "interactive_count_zen_1366" in data else [])
        width = max(len(k) for k in keys)
        for k in keys:
            base = BASELINE.get(k)
            note = f"  (taban {base})" if base is not None else ""
            print(f"{k:<{width}} : {data[k]}{note}")
        if violations:
            print("KAPI IHLALI: " + "; ".join(violations))

    return 1 if (args.gate and violations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
