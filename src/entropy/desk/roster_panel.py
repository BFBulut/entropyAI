"""
Kadro paneli: ofisin ajanları (`AgentsWidget(office=...)`).

Faz 2 ajan paneli ofis parametresiyle yeniden kullanılır; ofis kipinde kartlarda
"orkestratör yap" / "değerlendirici yap" düğmeleri de çıkar (bkz. agents_widget).
"""

from __future__ import annotations

from typing import Any, List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout

from entropy.ui.widgets.agents_widget import AgentsWidget, spec_field


class RosterPanel(QFrame):
    """Sağ sütun: seçili ofisin ajan kadrosu ve rol atamaları."""

    roster_changed = Signal(str)  # ofis adı

    def __init__(
        self,
        parent=None,
        registry: Any = None,
        board: Any = None,
        office_registry: Any = None,
        bridge=None,
        office: str = "",
    ):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.agents_widget = AgentsWidget(
            parent=self,
            registry=registry,
            board=board,
            bridge=bridge,
            office=office,
            office_registry=office_registry,
        )
        layout.addWidget(self.agents_widget)

    @property
    def office(self) -> str:
        return self.agents_widget.office

    def set_office(self, office: str) -> None:
        self.agents_widget.set_office(office)

    def refresh(self) -> None:
        self.agents_widget.refresh_agents()

    def agent_names(self) -> List[str]:
        return [str(spec_field(s, "name", "")) for s in self.agents_widget.list_agents()]

    def assign_role(self, agent_name: str, role: str) -> bool:
        ok = self.agents_widget.assign_office_role(agent_name, role)
        if ok:
            self.roster_changed.emit(self.office)
        return ok
