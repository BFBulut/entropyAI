"""Faz 13-B: `entropy.memory` → `entropy.brain` paket taşıması sözleşmesi.

Ölçülen dört şey:
1. Kaynak ağacında, testlerde, betiklerde ve spec'te eski ad **hiç geçmez**
   (tek istisna: uyumluluk şiminin kendi dosyası).
2. Şim eski adı yeni modülün **aynı nesnesine** bağlar (derin yollar dâhil).
3. Şim içe aktarıldığında `DeprecationWarning` verir; `entropy.brain` vermez.
4. Şim modülü `EntropyAI.spec` hiddenimports listesinde yer alır (exe'de
   sessizce kaybolmasın).
"""

from __future__ import annotations

import ast
import importlib
import re
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIM_PATH = REPO_ROOT / "src" / "entropy" / "memory" / "__init__.py"
SPEC_PATH = REPO_ROOT / "EntropyAI.spec"

_OLD_PATTERN = re.compile(r"entropy\.memory|entropy/memory")


def _scan_roots():
    yield from (REPO_ROOT / "src").rglob("*.py")
    yield from (REPO_ROOT / "tests").rglob("*.py")
    yield from (REPO_ROOT / "scripts").rglob("*.py")
    yield SPEC_PATH


def test_no_stale_old_package_references():
    """Eski ada atıf sayacı: şim dosyası ve bu test dışında **0**."""
    allowed = {SHIM_PATH.resolve(), Path(__file__).resolve()}
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
            # Spec, şimi bilinçli olarak paketliyor (`'entropy.memory'` girdisi
            # + açıklaması); bu iki satır sapma değildir.
            if resolved == SPEC_PATH.resolve() and (
                "'entropy.memory'" in line or line.lstrip().startswith("#")
            ):
                continue
            if _OLD_PATTERN.search(line):
                offenders.append(f"{resolved.relative_to(REPO_ROOT)}:{lineno}")
    assert offenders == [], f"eski `entropy.memory` atıfları: {offenders}"


@pytest.mark.parametrize(
    "old_name",
    [
        "entropy.memory.gate",
        "entropy.memory.playbook",
        "entropy.memory.context_builder",
        "entropy.memory.obsidian.vault_manager",
        "entropy.memory.supabase.cognitive_memory",
    ],
)
def test_shim_aliases_are_identical_objects(old_name):
    """Eski ad ile yeni ad **aynı modül nesnesini** verir (derin yollar dâhil)."""
    new_name = "entropy.brain" + old_name[len("entropy.memory"):]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        old_mod = importlib.import_module(old_name)
    new_mod = importlib.import_module(new_name)
    assert old_mod is new_mod
    assert sys.modules[old_name] is sys.modules[new_name]


def test_shim_emits_deprecation_warning():
    """Eski adın içe aktarımı uyarı yükseltir; `entropy.brain` sessizdir."""
    src = REPO_ROOT / "src"
    env_prefix = [sys.executable, "-c"]

    old = subprocess.run(
        env_prefix
        + [
            "import sys, warnings; sys.path.insert(0, r'%s');"
            " warnings.simplefilter('error');"
            " import entropy.memory.gate" % src
        ],
        capture_output=True,
        text=True,
    )
    assert old.returncode != 0, "eski ad uyarı yükseltmedi"
    assert "DeprecationWarning" in old.stderr

    new = subprocess.run(
        env_prefix
        + [
            "import sys, warnings; sys.path.insert(0, r'%s');"
            " warnings.simplefilter('error');"
            " import entropy.brain.gate" % src
        ],
        capture_output=True,
        text=True,
    )
    assert new.returncode == 0, f"entropy.brain uyarı verdi: {new.stderr}"


def test_shim_documents_its_lifetime():
    """Şim ömrü dosyanın başında yazılı olmalı (v0.12.0'da silinir)."""
    head = SHIM_PATH.read_text(encoding="utf-8")[:1500]
    assert "v0.12.0" in head
    assert "entropy.brain" in head


def test_spec_lists_the_shim():
    """Şim `EntropyAI.spec` hiddenimports'ta olmalı."""
    tree = ast.parse(SPEC_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "hiddenimports":
            for item in ast.walk(node.value):
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    names.add(item.value)
    assert "entropy.memory" in names
    assert "entropy.brain" in names
