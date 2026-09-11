"""Sohbette görünür canlı akış satırı (Faz 14-E madde 3).

Sorun: `bus.agent_stream` Faz 10-B'den beri yayılıyor ama Zen sohbetinde hiçbir
karşılığı yoktu; kullanıcı ajan koşarken ekranda "bir şey oluyor" işareti
görmüyordu (Faz 14 planı §5 "Canlı akış: sinyal var, sohbette yok").

Sözleşme: tek satır, kırpılmış, gürültü sınırlı.

* aynı metin ardışık tekrarlanmaz;
* en fazla **1 satır/sn** yazılır (araya giren olaylar son metni günceller);
* koşu bitince (`kind` ∈ {result, error} ya da `state == "idle"`) satır katlanır
  (gizlenir), böylece boşta ekranda ölü bir şerit kalmaz.

Metin biçimi: "Ajan: web araması yapıyor…" — ajan adı + eylem. Ham araç adı
değil, `tool.input_summary` varsa o gösterilir.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from entropy.core.event_bus import bus
from entropy.ui.design import TOKENS

__all__ = ["AgentStreamLine", "MIN_INTERVAL_S", "LINE_MAX_CHARS", "format_stream_line"]

#: Gürültü sınırı: iki yazım arasında en az bu kadar saniye geçer.
MIN_INTERVAL_S = 1.0
#: Satır uzunluğu tavanı (tek satır, kırpma "…" ile biter).
LINE_MAX_CHARS = 96

#: Akış türünün insan okur karşılığı (ham `kind` ekranda yazılmaz).
_KIND_VERBS = {
    "thinking": "düşünüyor",
    "tool_call": "araç çalıştırıyor",
    "tool_result": "sonucu okuyor",
    "status": "çalışıyor",
    "text": "yazıyor",
}


def format_stream_line(payload: Dict[str, Any]) -> str:
    """Akış yükünü tek satırlık, kırpılmış metne çevirir (saf işlev)."""
    data = dict(payload or {})
    agent = str(data.get("agent") or "Ajan").strip() or "Ajan"
    tool = data.get("tool") or {}
    detail = ""
    if isinstance(tool, dict):
        detail = str(tool.get("input_summary") or tool.get("name") or "").strip()
    if not detail:
        detail = str(data.get("text") or "").strip()
    if not detail:
        detail = _KIND_VERBS.get(str(data.get("kind") or ""), "çalışıyor")
    detail = " ".join(detail.split())
    line = f"{agent}: {detail}"
    if len(line) > LINE_MAX_CHARS:
        line = line[: LINE_MAX_CHARS - 1].rstrip() + "…"
    return line


class AgentStreamLine(QFrame):
    """Tek satırlık canlı akış göstergesi; boştayken kendini gizler."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("agentStreamLine")
        self.setProperty("role", "panel")
        row = QHBoxLayout(self)
        row.setContentsMargins(
            TOKENS["space"]["2"], TOKENS["space"]["1"],
            TOKENS["space"]["2"], TOKENS["space"]["1"],
        )
        row.setSpacing(TOKENS["space"]["2"])

        self.dot = QLabel("●")
        self.dot.setProperty("role", "statusDot")
        self.dot.setProperty("tone", "warn")
        self.dot.setAccessibleName("Ajan akışı göstergesi")
        row.addWidget(self.dot)

        self.label = QLabel("")
        self.label.setProperty("role", "label")
        self.label.setAccessibleName("Ajan canlı akışı")
        row.addWidget(self.label, 1)

        self._last_text = ""
        self._last_at = 0.0
        self.setVisible(False)

        signal = getattr(bus, "agent_stream", None)
        if signal is not None:
            signal.connect(self.on_agent_stream)

    @Slot(dict)
    def on_agent_stream(self, payload: dict) -> None:
        """Akış olayını satıra yansıtır (gürültü sınırlı)."""
        try:
            data = dict(payload or {})
        except Exception:
            return
        kind = str(data.get("kind") or "")
        state = str(data.get("state") or "")
        if kind in ("result", "error") or state == "idle":
            self.collapse()
            return
        text = format_stream_line(data)
        now = time.monotonic()
        if text == self._last_text:
            return
        if now - self._last_at < MIN_INTERVAL_S and self.isVisible():
            # Sınır aşıldı: metni sakla, ekrandaki satırı olduğu gibi bırak.
            return
        self._last_text = text
        self._last_at = now
        self.label.setText(text)
        self.label.setToolTip(str(data.get("full_text") or text))
        self.setVisible(True)

    def collapse(self) -> None:
        """Koşu bitti: satır katlanır, son metin ipucunda kalır."""
        self.setVisible(False)
        self._last_text = ""

    def current_text(self) -> str:
        return self.label.text()
