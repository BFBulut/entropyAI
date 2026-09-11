"""Faz 13-B taşıması + Faz 14-F **şim kaldırma** sözleşmesi.

`entropy.memory` → `entropy.brain` taşıması Faz 13-B'de yapıldı; uyumluluk şimi
ADR-0008'in sözü gereği **v0.12.0'da kaldırıldı**. Ölçülen üç şey:

1. Kaynak ağacında, testlerde, betiklerde ve spec'te eski ad **hiç geçmez**.
2. `import entropy.memory` artık **`ModuleNotFoundError`** verir (şim yok);
   `src/entropy/memory/` dizini diskte yoktur.
3. `EntropyAI.spec` hiddenimports listesinde `entropy.memory` **yoktur**,
   `entropy.brain` **vardır**.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIM_PATH = REPO_ROOT / "src" / "entropy" / "memory"
SPEC_PATH = REPO_ROOT / "EntropyAI.spec"

_OLD_PATTERN = re.compile(r"entropy\.memory|entropy/memory")


def _scan_roots():
    yield from (REPO_ROOT / "src").rglob("*.py")
    yield from (REPO_ROOT / "tests").rglob("*.py")
    yield from (REPO_ROOT / "scripts").rglob("*.py")
    yield SPEC_PATH


def test_no_stale_old_package_references():
    """Eski ada atıf sayacı: bu test dosyası dışında **0**."""
    allowed = {Path(__file__).resolve()}
    offenders: list[str] = []
    for path in _scan_roots():
        resolved = path.resolve()
        if resolved in allowed or "__pycache__" in resolved.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _OLD_PATTERN.search(line):
                offenders.append(f"{resolved.relative_to(REPO_ROOT)}:{lineno}")
    assert offenders == [], f"eski `entropy.memory` atıfları: {offenders}"


def test_shim_package_is_deleted():
    """`src/entropy/memory/` dizini diskte yok."""
    assert not SHIM_PATH.exists(), f"şim hâlâ duruyor: {SHIM_PATH}"


def test_old_package_import_fails():
    """`import entropy.memory` → `ModuleNotFoundError` (temiz süreçte ölçülür)."""
    src = REPO_ROOT / "src"
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, r'%s');\n"
            "import entropy.brain.gate\n"
            "try:\n"
            "    import entropy.memory\n"
            "except ModuleNotFoundError:\n"
            "    print('GONE')\n"
            "else:\n"
            "    raise SystemExit('şim hâlâ içe aktarılabiliyor')\n" % src,
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "GONE" in proc.stdout


def test_spec_does_not_list_the_shim():
    """Spec hiddenimports: `entropy.memory` yok, `entropy.brain` var."""
    tree = ast.parse(SPEC_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "hiddenimports":
            for item in ast.walk(node.value):
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    names.add(item.value)
    assert "entropy.memory" not in names
    assert "entropy.brain" in names
