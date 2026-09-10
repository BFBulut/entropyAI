"""
Kural onay paneli: ajanın keşfettiği kural adaylarını kullanıcı onaylar.

Kullanıcı tarifi: "ajan kural keşfedince uygulama bana sorsun; 'Kalıcı yap'
dersem kural sistem istemine girsin." Kararı MODEL değil KULLANICI verir; bu
yüzden aday kurallar hiçbir zaman kendiliğinden isteme girmez —
`promoted_rules.rules_section()` yalnızca `promoted` kayıtları döndürür.

Aynı panel iki yerde kullanılır (bu yüzden Desk'te değil, ortak arayüz
klasöründedir):
- Desk "Bellek" sekmesi: seçili ofisin kuralları.
- Zen "Ajanlar" sekmesi: `office="entropy"` — Entropy'nin kendi kuralları.

Bellek katmanı (`entropy.memory.promoted_rules`) paralel ajanda; modül yoksa
panel boş ve pasif kalır (guard), Desk penceresi çökmez.
"""

from __future__ import annotations

import html
from typing import Any, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from entropy.core.event_bus import bus
from entropy.ui.themes.cyber_theme import READING_TOKENS as RT

STATUS_CANDIDATE = "candidate"
STATUS_PROMOTED = "promoted"


def rules_api() -> Optional[Any]:
    """`entropy.memory.promoted_rules` modülü; yoksa None."""
    try:
        from entropy.memory import promoted_rules  # type: ignore

        return promoted_rules
    except Exception:
        return None


def rule_field(rule: Any, name: str, default: str = "") -> Any:
    """Rule dataclass / sözlük fark etmeksizin alan okur."""
    if rule is None:
        return default
    if isinstance(rule, dict):
        value = rule.get(name, default)
    else:
        value = getattr(rule, name, default)
    return default if value is None else value


class RuleCandidatesPanel(QFrame):
    """Kural adayları + onaylı kurallar; onay/ret düğmeleriyle."""

    rule_decided = Signal(str, bool)   # rule_id, kalıcı yapıldı mı

    def __init__(self, parent=None, office: str = "", vault_path: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.office = office or ""
        self.vault_path = vault_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self.title_label = QLabel("")
        self.title_label.setProperty("role", "label")
        layout.addWidget(self.title_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(4)
        self.body_layout.addStretch()
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll, 1)

        self.approved_label = QLabel("")
        self.approved_label.setWordWrap(True)
        self.approved_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.approved_label.setProperty("role", "label")
        layout.addWidget(self.approved_label)

        signal = getattr(bus, "rules_updated", None)
        if signal is not None:
            try:
                signal.connect(self._on_rules_updated)
            except Exception:
                pass

        self.refresh()

    # ------------------------------------------------------------ veri

    def set_office(self, office: str) -> None:
        self.office = office or ""
        self.refresh()

    def _list(self, status: Optional[str]) -> List[Any]:
        api = rules_api()
        if api is None or not self.office:
            return []
        try:
            if self.vault_path is not None:
                return list(api.list_rules(self.office, status, self.vault_path) or [])
            return list(api.list_rules(self.office, status) or [])
        except Exception:
            return []

    def candidates(self) -> List[Any]:
        return self._list(STATUS_CANDIDATE)

    def approved(self) -> List[Any]:
        return self._list(STATUS_PROMOTED)

    # ------------------------------------------------------------ çizim

    @Slot(str, int)
    def _on_rules_updated(self, office: str = "", count: int = 0) -> None:
        if not office or not self.office or office == self.office:
            self.refresh()

    def refresh(self) -> None:
        """Aday satırlarını yeniden kurar ve onaylı listeyi basar."""
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        candidates = self.candidates()
        label = "Entropy" if self.office == "entropy" else (self.office or "—")
        self.title_label.setText(
            f"<b style='color:{RT['accent']}; font-size:13px;'>KURAL ADAYLARI</b>"
            f" <span style='color:{RT['text_dim']}; font-size:11px;'>· {html.escape(label)}"
            f" · {len(candidates)} aday</span>"
        )
        if not candidates:
            empty = QLabel(
                "Bekleyen kural adayı yok. Ajan bir kural keşfedince burada sorulur."
            )
            empty.setWordWrap(True)
            empty.setProperty("role", "label")
            self.body_layout.addWidget(empty)
        for rule in candidates:
            self.body_layout.addWidget(self._make_row(rule))
        self.body_layout.addStretch()

        approved = self.approved()
        if approved:
            items = "".join(
                f"<li>{html.escape(str(rule_field(r, 'text', '')))}</li>"
                for r in approved
            )
            self.approved_label.setText(
                f"<b style='color:{RT['text']}; font-size:11px;'>Onaylı kurallar "
                f"({len(approved)})</b><ul style='margin:2px 0 0 14px;'>{items}</ul>"
            )
        else:
            self.approved_label.setText(
                f"<span style='color:{RT['text_dim']}; font-size:11px;'>"
                f"Onaylı kural yok; sistem istemine kural eklenmiyor.</span>"
            )

    def _make_row(self, rule: Any) -> QWidget:
        rule_id = str(rule_field(rule, "id", ""))
        row = QFrame()
        row.setObjectName("ruleRow")
        row.setProperty("role", "panel")
        box = QVBoxLayout(row)
        box.setContentsMargins(8, 6, 8, 6)
        box.setSpacing(3)

        text = QLabel(
            f"<span style='color:{RT['text']}; font-size:13px;'>"
            f"{html.escape(str(rule_field(rule, 'text', '')))}</span>"
        )
        text.setWordWrap(True)
        box.addWidget(text)

        meta_bits = [str(rule_field(rule, "agent", "")) or "—"]
        source = str(rule_field(rule, "source", ""))
        if source:
            meta_bits.append(f"kaynak: {source}")
        scope = str(rule_field(rule, "scope", ""))
        if scope and scope != "office":
            meta_bits.append(scope)
        meta = QLabel(
            f"<span style='color:{RT['text_dim']}; font-size:11px;'>"
            f"{html.escape(' · '.join(meta_bits))}</span>"
        )
        meta.setWordWrap(True)
        box.addWidget(meta)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        promote_btn = QPushButton("Kalıcı yap")
        promote_btn.setAccessibleName("Kalıcı yap")
        promote_btn.setToolTip("Kural onaylanır ve ajanların sistem istemine girer.")
        promote_btn.setProperty("rule_id", rule_id)
        promote_btn.clicked.connect(self._on_promote_clicked)
        actions.addWidget(promote_btn)
        reject_btn = QPushButton("Reddet")
        reject_btn.setAccessibleName("Reddet")
        reject_btn.setToolTip("Kural isteme girmez; aynı aday tekrar sorulmaz.")
        reject_btn.setProperty("rule_id", rule_id)
        reject_btn.clicked.connect(self._on_reject_clicked)
        actions.addWidget(reject_btn)
        actions.addStretch()
        box.addLayout(actions)
        return row

    # ------------------------------------------------------------ eylemler

    @Slot()
    def _on_promote_clicked(self) -> None:
        sender = self.sender()
        self.promote_rule(str(sender.property("rule_id") or ""))

    @Slot()
    def _on_reject_clicked(self) -> None:
        sender = self.sender()
        self.reject_rule(str(sender.property("rule_id") or ""))

    def _decide(self, rule_id: str, promote: bool) -> bool:
        api = rules_api()
        if api is None or not rule_id or not self.office:
            return False
        fn = getattr(api, "promote" if promote else "reject", None)
        if fn is None:
            return False
        try:
            if self.vault_path is not None:
                result = fn(self.office, rule_id, self.vault_path)
            else:
                result = fn(self.office, rule_id)
        except Exception:
            return False
        if result is None:
            return False
        self.refresh()
        self.rule_decided.emit(rule_id, promote)
        signal = getattr(bus, "rules_updated", None)
        if signal is not None:
            try:
                signal.emit(self.office)
            except Exception:
                pass
        return True

    def promote_rule(self, rule_id: str) -> bool:
        """"Kalıcı yap": kural onaylanır, sistem istemi bloğuna girer."""
        return self._decide(rule_id, True)

    def reject_rule(self, rule_id: str) -> bool:
        return self._decide(rule_id, False)
