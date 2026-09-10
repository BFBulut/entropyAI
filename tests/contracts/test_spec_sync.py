"""
Faz 12-A: `EntropyAI.spec` ile kaynak ağacı arasındaki eşleme sözleşmesi.

Faz 10-C'de bir modül ailesi spec'e girmediği için `.exe` içinde worktree/PR/
şablon/makbuz yolları **sessizce** kapanmıştı; Faz 12 araştırma B §2.3 aynı
sınıfta 15 yeni sapma ölçtü. Bu test sapmayı kalıcı olarak sıfırda tutar:
`src/entropy/**` altındaki her modül ya spec'in `hiddenimports` listesinde
adıyla geçer ya da bilinçli dışlama kümesindedir.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "EntropyAI.spec"
SRC_ROOT = REPO_ROOT / "src" / "entropy"

#: Pakete girmesi beklenmeyen alt ağaçlar (geliştirici araçları / tek seferlikler).
EXCLUDED_PREFIXES = (
    "entropy.tools._oneshot",
    "entropy._oneshot",
)


def _source_modules() -> set[str]:
    mods: set[str] = set()
    for path in SRC_ROOT.rglob("*.py"):
        rel = path.relative_to(SRC_ROOT.parent).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        name = ".".join(parts)
        if not name or name.startswith(EXCLUDED_PREFIXES):
            continue
        mods.add(name)
    return mods


def _spec_hidden_imports() -> set[str]:
    """`Analysis(hiddenimports=[...])` listesindeki `entropy.*` girdileri.

    AST ile okunur: `datas` içindeki `'entropy.ico'` gibi dosya adları düzenli
    ifade taramasına karışıyordu.
    """
    tree = ast.parse(SPEC_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or node.arg != "hiddenimports":
            continue
        for item in ast.walk(node.value):
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                if item.value == "entropy" or item.value.startswith("entropy."):
                    names.add(item.value)
    assert names, "spec içinde hiddenimports listesi bulunamadı"
    return names


def test_spec_lists_phase12c_skill_synthesis():
    """Faz 12-C: beceri sentezi exe'de sessizce kapanmasın (12-B kablolaması)."""
    assert "entropy.memory.skill_synthesis" in _spec_hidden_imports()


def test_spec_lists_every_entropy_module():
    """Eksik listesi BOŞ olmalı (Faz 12-A öncesi: 15 modül)."""
    missing = sorted(_source_modules() - _spec_hidden_imports())
    assert missing == [], (
        "EntropyAI.spec hiddenimports'ta eksik modüller (exe'de sessiz kırılma "
        f"riski): {missing}"
    )


def test_spec_hidden_imports_all_exist_in_source():
    """Ters yön: spec var olmayan bir modülü listelemesin (ölü girdi)."""
    source = _source_modules()
    stale = sorted(name for name in _spec_hidden_imports() if name not in source)
    assert stale == [], f"EntropyAI.spec'te kaynakta karşılığı olmayan girdiler: {stale}"


def test_spec_datas_paths_exist():
    """`datas` girdilerinin kaynak yolları diskte gerçekten var."""
    tree = ast.parse(SPEC_PATH.read_text(encoding="utf-8"))
    literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            first, second = node.elts
            if isinstance(first, ast.Constant) and isinstance(second, ast.Constant):
                if isinstance(first.value, str) and isinstance(second.value, str):
                    literals.append(first.value)
    assert literals, "spec içinde datas girdisi bulunamadı"
    eksik = [p for p in literals if not (REPO_ROOT / p).exists()]
    assert eksik == [], f"spec datas yolları diskte yok: {eksik}"


@pytest.mark.parametrize("dead", ["pillow", "PIL"])
def test_no_dead_pillow_dependency(dead):
    """`pillow` hiçbir yerde içe aktarılmıyor; bağımlılık listesinde de olmamalı."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert dead not in pyproject, f"pyproject.toml'da ölü bağımlılık: {dead}"


def test_no_source_file_imports_pil():
    """Kanıt: `pillow` kaldırıldı çünkü hiçbir modül PIL'i içe aktarmıyor."""
    import warnings

    hits: list[str] = []
    warnings.simplefilter("ignore", SyntaxWarning)  # eski betiklerin kaçış dizileri
    for root in ("src", "skills", "scripts"):
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:  # pragma: no cover
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(a.name.split(".")[0] == "PIL" for a in node.names):
                        hits.append(str(path))
                elif isinstance(node, ast.ImportFrom):
                    if (node.module or "").split(".")[0] == "PIL":
                        hits.append(str(path))
    assert hits == [], f"PIL içe aktaran dosyalar var, pillow geri eklenmeli: {hits}"


def test_version_single_source():
    """`entropy.__version__` pyproject'ten türer (üç ayrı sürüm gerçeği bitti)."""
    import tomllib

    import entropy

    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = data["project"]["version"]
    assert entropy.__version__ == declared
    assert entropy._FALLBACK_VERSION == declared, (
        "yedek sürüm pyproject ile ayrıştı — birlikte güncellenmeli"
    )


def test_cli_reports_version():
    """`--version` çıktısı uygulama adı + sürüm."""
    import subprocess
    import sys

    import entropy

    out = subprocess.run(
        [sys.executable, str(REPO_ROOT / "run_entropy.py"), "--version"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert out.returncode == 0, out.stderr
    assert entropy.__version__ in (out.stdout + out.stderr)
