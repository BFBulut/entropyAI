"""Skills & Self-Tooling package for Entropy AI."""

# PDF motoru (pypdf) ve medya ajansı motoru yalnızca kullanıldıklarında yükleniyor.
# Ölçüm (python -X importtime -c "import entropy.main"): eskiden paketi içe
# aktarmak pdf_engine + pypdf için ~247 ms, media_agency_soldier için ~74 ms
# ekliyordu; ikisi de açılışta değil, PDF eklendiğinde/yetenek çalıştığında gerekli.
# PEP 562 modül __getattr__'ı sayesinde "from entropy.skills import PDFIngestionEngine"
# yazan mevcut kod aynen çalışmaya devam eder.

from typing import Any

from entropy.skills.manager import SkillManager, SkillDefinition

__all__ = ["SkillManager", "SkillDefinition", "PDFIngestionEngine", "MediaAgencySoldierEngine"]

_LAZY = {
    "PDFIngestionEngine": "entropy.skills.pdf_engine",
    "MediaAgencySoldierEngine": "entropy.skills.media_agency_soldier",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # ikinci erişimde __getattr__'a hiç uğramaz
    return value


def __dir__():
    return sorted(list(globals()) + list(_LAZY))
