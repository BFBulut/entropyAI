"""
Geriye dönük uyumluluk kabuğu — gerçek kaynak `entropy.agents.desk_registry`.

Faz 6'da ofisler Entropy'nin kadrosundan ayrıldı: veri kökü `Entropy/Offices`
değil `Desk/Offices`, defter `OfficeRegistry` değil `DeskRegistry`,
tohum ofis/ajan yok. Modül tamamen silinmedi çünkü ofis kavramına dışarıdan
(desk panelleri, kimlik katmanı, komut paleti) onlarca yerden `OfficeSpec` ve
`OfficeRegistry` adıyla erişiliyordu; adları burada takma ad olarak bırakmak,
o çağrı noktalarını tek tek kırmadan tek bir veri kaynağına indirmenin en ucuz
yoluydu. Yeni kod doğrudan `desk_registry`den içe aktarmalı.
"""

from __future__ import annotations

from entropy.agents.desk_registry import (  # noqa: F401
    DEFAULT_BUDGET_TOKENS,
    DEFAULT_MAX_PARALLEL,
    DESK_SUBDIR,
    OFFICE_FILENAME,
    ORCHESTRATOR_AGENT,
    DeskOffice,
    DeskProject,
    DeskRegistry,
    desk_manifest,
    desk_roster,
)

# Eski adlar (yalnızca takma ad; ayrı bir uygulama YOK).
OfficeSpec = DeskOffice
OfficeRegistry = DeskRegistry
offices_manifest = desk_manifest
OFFICES_SUBDIR = DESK_SUBDIR
OFFICE_MANIFEST_CHAR_BUDGET = 520

# Tohum ofis kalmadı: ofisi kullanıcı açar (kural 2). Liste, eski çağrı
# noktaları (`DEFAULT_OFFICES` beklentisi) kırılmasın diye boş bırakıldı.
DEFAULT_OFFICES: list = []

__all__ = [
    "DeskOffice",
    "DeskProject",
    "DeskRegistry",
    "OfficeSpec",
    "OfficeRegistry",
    "offices_manifest",
    "desk_manifest",
    "desk_roster",
    "OFFICES_SUBDIR",
    "DESK_SUBDIR",
    "OFFICE_FILENAME",
    "ORCHESTRATOR_AGENT",
    "DEFAULT_OFFICES",
    "DEFAULT_MAX_PARALLEL",
    "DEFAULT_BUDGET_TOKENS",
]
