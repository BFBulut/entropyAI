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
    "src/entropy/ui/themes/cyber_theme.py",
}

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
STYLESHEET_RE = re.compile(r"\.setStyleSheet\s*\(")
FIXED_RE = re.compile(r"setFixed(?:Width|Height|Size)\s*\(")
FONT_SIZE_RE = re.compile(r"font-size:\s*([0-9]+)px")
PADDING_RE = re.compile(r"padding:\s*([0-9px ]+);")
RADIUS_RE = re.compile(r"border-radius:\s*([0-9]+)px")
BOLD_RE = re.compile(r"font-weight:\s*(bold|600|700)")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿⬀-⯿]")
ACCESSIBLE_NAME_RE = re.compile(r"setAccessibleName\s*\(")
SHORTCUT_RE = re.compile(r"QShortcut\s*\(")

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

#: Nihai hedefler (denetim §6.2). Adım 6 sonunda `--gate --final` yeşil olmalı.
FINAL_GATES: Dict[str, int] = {
    "distinct_hex": 14,
    "local_stylesheets": 5,
    "fixed_sizes": 10,
    "distinct_font_sizes": 5,
    "distinct_paddings": 8,
    "emoji_usages": 0,
    "contrast_failures": 0,
    "focusless_selectors": 0,
    "small_targets": 0,
}


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
    emojis: set[str] = set()
    accessible_names = 0
    shortcuts = 0
    small_targets: List[str] = []

    for f in _iter_files(paths):
        rel = _rel(f)
        text = f.read_text(encoding="utf-8", errors="ignore")
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
        "distinct_emojis": len(emojis),
        "accessible_names": accessible_names,
        "shortcuts": shortcuts,
        "small_targets": sorted(set(small_targets)),
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

    qss = build_qss()
    missing = [s for s in FOCUSABLE_SELECTORS if f"{s}:focus" not in qss]
    result["focusless_selectors"] = missing
    result["qss_bytes"] = len(qss)
    return result


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Entropy arayüz tasarım denetimi")
    ap.add_argument("--paths", nargs="*", default=DEFAULT_PATHS)
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--gate", action="store_true", help="eşik aşımında çıkış kodu 1")
    ap.add_argument("--final", action="store_true", help="taban yerine nihai hedefleri uygula")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    data: Dict[str, Any] = {"paths": args.paths}
    data.update(static_metrics(args.paths))
    data.update(token_metrics())
    data["contrast_failure_count"] = len(data["contrast_failures"])
    data["focusless_selector_count"] = len(data["focusless_selectors"])
    data["small_target_count"] = len(data["small_targets"])
    data["baseline"] = BASELINE

    gates = FINAL_GATES if args.final else {
        **{k: v for k, v in BASELINE.items()},
        "contrast_failures": 0,
        "focusless_selectors": 0,
    }
    violations = []
    for key, limit in gates.items():
        actual = data.get(key)
        if isinstance(actual, list):
            actual = len(actual)
        if isinstance(actual, int) and actual > limit:
            violations.append(f"{key}: {actual} > {limit}")
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
            "accessible_names", "shortcuts", "contrast_failure_count",
            "focusless_selector_count", "small_target_count",
        ]
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
