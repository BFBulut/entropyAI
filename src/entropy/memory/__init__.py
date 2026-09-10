"""Uyumluluk katmanı: `entropy.memory` → `entropy.brain`.

Faz 13-B'de bellek paketi `entropy.memory` adından `entropy.brain` adına taşındı
(bkz. `docs/adr/ADR-0008-brain-paket-tasimasi.md`). Bu modül eski adı bir sürüm
boyunca çalışır tutar.

ÖMÜR: **v0.11.x** boyunca geçerlidir; **v0.12.0'da silinecektir**. Yeni kod
doğrudan `entropy.brain` kullanmalıdır.

Nasıl çalışır: meta yol bulucusu (`sys.meta_path`) `entropy.memory.<alt>` adını
`entropy.brain.<alt>` modülüne **aynı nesne** olarak bağlar; yani
`entropy.memory.gate is entropy.brain.gate` doğrudur. Derin yollar
(`entropy.memory.obsidian.vault_manager`) da desteklenir.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import warnings
from importlib.abc import Loader, MetaPathFinder

_OLD = "entropy.memory"
_NEW = "entropy.brain"

warnings.warn(
    "`entropy.memory` paketi `entropy.brain` adına taşındı; eski ad v0.12.0'da "
    "kaldırılacak. İçe aktarmaları `entropy.brain` olarak güncelleyin.",
    DeprecationWarning,
    stacklevel=2,
)


class _BrainAliasFinder(MetaPathFinder, Loader):
    """`entropy.memory.*` adlarını `entropy.brain.*` modüllerine yönlendirir."""

    def find_spec(self, fullname, path=None, target=None):  # noqa: D401
        if not fullname.startswith(_OLD + "."):
            return None
        return importlib.util.spec_from_loader(fullname, self)

    def create_module(self, spec):
        # Hedef modülü içe aktar ve **aynı nesneyi** eski ad altında yayınla.
        new_name = _NEW + spec.name[len(_OLD):]
        return importlib.import_module(new_name)

    def exec_module(self, module):  # modül zaten çalıştırılmış durumda
        return None


if not any(isinstance(f, _BrainAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _BrainAliasFinder())


def __getattr__(name: str):
    """Paket düzeyi öznitelikleri `entropy.brain` üzerinden karşıla."""
    brain = importlib.import_module(_NEW)
    try:
        return getattr(brain, name)
    except AttributeError:
        pass
    try:
        return importlib.import_module(f"{_OLD}.{name}")
    except ImportError as exc:  # pragma: no cover - beklenmedik ad
        raise AttributeError(f"module {_OLD!r} has no attribute {name!r}") from exc


def __dir__():
    return sorted(set(dir(importlib.import_module(_NEW))) | set(globals()))
