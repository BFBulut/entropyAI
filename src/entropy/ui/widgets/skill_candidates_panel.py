"""Beceri adayları — onaysız hiçbir yetenek etkinleşmez (Faz 12-D.2).

Kural onay panelinin (`rules_panel.RuleCandidatesPanel`) kardeşi. Faz 12-C'nin
`memory.skill_synthesis` sözleşmesini kullanır:

    list_candidates() -> [aday]        # aday: dataclass ya da sözlük
    promote_skill(candidate_id) -> Any # kullanıcı "Onayla" derse
    reject_skill(candidate_id) -> Any  # kullanıcı "Reddet" derse

Modül **henüz yoksa** panel sessizce boş durumda kalır (guard); ürün kırılmaz.
Ekranda görünen sözleşme: aday satırında `durum: onay bekliyor` yazar ve
"Onayla" basılmadan yetenek etkin sayılmaz.
"""

from __future__ import annotations

import html
from typing import Any, List, Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from entropy.core.event_bus import bus
from entropy.ui.design import TOKENS
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT
from entropy.ui.widgets.lifecycle import discard_widget

__all__ = ["SkillCandidatesPanel", "skill_synthesis_api", "candidate_field"]


def skill_synthesis_api() -> Optional[Any]:
    """`entropy.brain.skill_synthesis` modülü; yoksa None (12-C ekliyor)."""
    try:
        from entropy.brain import skill_synthesis  # type: ignore

        return skill_synthesis
    except Exception:
        return None


def candidate_field(candidate: Any, name: str, default: Any = "") -> Any:
    """Aday dataclass / sözlük fark etmeksizin alan okur."""
    if isinstance(candidate, dict):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


class SkillCandidatesPanel(QFrame):
    """Beceri adaylarını listeler; Onayla/Reddet ile sözleşmeyi çağırır."""

    #: (aday kimliği, onaylandı mı)
    candidate_decided = Signal(str, bool)

    def __init__(self, parent: Optional[QWidget] = None, api: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self._api = api

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            TOKENS["space"]["2"], TOKENS["space"]["1"],
            TOKENS["space"]["2"], TOKENS["space"]["1"],
        )
        layout.setSpacing(TOKENS["space"]["1"])

        self.title_label = QLabel("")
        self.title_label.setProperty("role", "label")
        layout.addWidget(self.title_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(TOKENS["space"]["1"])
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll, 1)

        signal = getattr(bus, "skills_updated", None)
        if signal is not None:
            try:
                signal.connect(self.on_skills_updated)
            except Exception:
                pass

        self.refresh()

    # ------------------------------------------------------------ veri
    def api(self) -> Optional[Any]:
        return self._api if self._api is not None else skill_synthesis_api()

    def candidates(self) -> List[Any]:
        api = self.api()
        lister = getattr(api, "list_candidates", None)
        if not callable(lister):
            return []
        try:
            return list(lister() or [])
        except Exception:
            return []

    # ------------------------------------------------------------ görünüm
    @Slot()
    def refresh(self) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                discard_widget(widget)

        items = self.candidates()
        self.title_label.setText(
            f"<b style='color:{RT['accent']}; font-size:13px;'>BECERİ ADAYLARI</b>"
            f" <span style='color:{RT['text_dim']}; font-size:11px;'>"
            f"· {len(items)} aday · onaysız etkinleşmez</span>"
        )
        if not items:
            empty = QLabel(
                "Bekleyen beceri adayı yok. Hafıza bir örüntüyü yetenek adayına"
                " dönüştürünce burada sorulur."
            )
            empty.setWordWrap(True)
            empty.setProperty("role", "label")
            self.body_layout.addWidget(empty)
        for candidate in items:
            self.body_layout.addWidget(self._make_row(candidate))
        self.body_layout.addStretch()

    def _make_row(self, candidate: Any) -> QWidget:
        cid = str(candidate_field(candidate, "id", ""))
        name = str(candidate_field(candidate, "name", "") or cid)
        summary = str(candidate_field(candidate, "summary", "") or "")

        row = QFrame()
        row.setObjectName("skillCandidateRow")
        row.setProperty("role", "panel")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(
            TOKENS["space"]["2"], TOKENS["space"]["1"],
            TOKENS["space"]["2"], TOKENS["space"]["1"],
        )
        row_layout.setSpacing(TOKENS["space"]["1"])

        text = QLabel(
            f"<b style='color:{RT['text']}; font-size:13px;'>{html.escape(name)}</b>"
            f"<br/><span style='color:{RT['text_dim']}; font-size:11px;'>"
            f"{html.escape(summary[:160])}</span>"
            f"<br/><span style='color:{RT['accent_warn']}; font-size:11px;'>"
            f"durum: onay bekliyor</span>"
        )
        text.setWordWrap(True)
        row_layout.addWidget(text)

        buttons = QHBoxLayout()
        buttons.setSpacing(TOKENS["space"]["1"])
        approve = QPushButton("Onayla")
        approve.setProperty("variant", "primary")
        approve.setAccessibleName(f"Beceri adayını onayla: {name}")
        approve.setProperty("candidate_id", cid)
        approve.clicked.connect(self._on_approve_clicked)
        buttons.addWidget(approve)

        reject = QPushButton("Reddet")
        reject.setProperty("variant", "ghost")
        reject.setAccessibleName(f"Beceri adayını reddet: {name}")
        reject.setProperty("candidate_id", cid)
        reject.clicked.connect(self._on_reject_clicked)
        buttons.addWidget(reject)
        buttons.addStretch()
        row_layout.addLayout(buttons)
        return row

    # ------------------------------------------------------------ eylem
    @Slot()
    def _on_approve_clicked(self) -> None:
        sender = self.sender()
        self.decide(str(sender.property("candidate_id") or ""), True)

    @Slot()
    def _on_reject_clicked(self) -> None:
        sender = self.sender()
        self.decide(str(sender.property("candidate_id") or ""), False)

    def decide(self, candidate_id: str, approve: bool) -> bool:
        """Sözleşmeyi çağırır. Modül yoksa `False` döner, ürün kırılmaz."""
        if not candidate_id:
            return False
        api = self.api()
        fn = getattr(api, "promote_skill" if approve else "reject_skill", None)
        if not callable(fn):
            return False
        try:
            fn(candidate_id)
        except Exception:
            return False
        self.candidate_decided.emit(candidate_id, approve)
        self.refresh()
        return True

    @Slot()
    def on_skills_updated(self, *args: Any) -> None:
        """`bus.skills_updated` alıcısı (QObject slotu, lambda değil)."""
        self.refresh()
