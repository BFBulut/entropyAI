"""
Ofis belleği için ince cephe (facade) modülü.

Agent Desk penceresi (`entropy.desk.window`) ofis belleğini **tam metin**
olarak göstermek ister; bağlam kurucu ise bütçeye sığan bir **özet** ister.
Depolama tarafı tek yerde, `entropy.memory.agent_memory` içindedir; burada
yalnızca iki çağrı biçimini uzlaştıran bir sarmalayıcı vardır.

`budget_tokens=None` (varsayılan) -> MEMORY.md'nin tam metni.
`budget_tokens=<int>`            -> agent_memory.load_office_memory özeti.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from entropy.memory.agent_memory import (  # noqa: F401  (yeniden dışa aktarım)
    append_office_memory,
    consolidate_office_memory,
    office_memory_path,
)
from entropy.memory import agent_memory as _agent_memory

__all__ = [
    "load_office_memory",
    "append_office_memory",
    "consolidate_office_memory",
    "office_memory_path",
]


def load_office_memory(
    office: str,
    budget_tokens: Optional[int] = None,
    vault_path: Optional[Path] = None,
) -> str:
    """
    Ofis belleğini döndürür.

    budget_tokens None ise MEMORY.md dosyasının tamamı okunur (pencere tam
    metin gösterir). Dosya yoksa boş dize döner - çağıran taraf kendi
    yer tutucu metnini basar.
    """
    if not office:
        return ""
    if budget_tokens is not None:
        return _agent_memory.load_office_memory(
            office, budget_tokens=budget_tokens, vault_path=vault_path
        )
    try:
        path = office_memory_path(office, vault_path)
    except Exception:
        return ""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return ""
