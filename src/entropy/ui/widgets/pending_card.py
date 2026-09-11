"""Bekleyen işler kartı — sohbet panelinin üstündeki tek onay yüzeyi (Faz 14-E).

Faz 14 planı §1.3: "İzin/onay yüzeyi hiç kurulmadı… 'Onaylıyorum' dediğinde
onaylanacak bir şey uygulamaya hiç ulaşmamıştı." Bu kart o yüzeyin arayüz
yarısıdır. **Veri yarısı köprü ajanının işidir (14-B)**; burada yalnızca imza
varsayılır ve modül yoksa kart sessizce boş kalır (`ImportError`/`getattr`).

Varsayılan sözleşme (`entropy.core.pending`):

    PendingQueue().list(kind=None) -> [dict(
        id, kind, title, detail, risk, created_at, source, payload, status)]
    PendingQueue().resolve(id, decision: "approve"|"reject", note="") -> dict

Ek kaynak (bugün var olan): `entropy.agents.desk_admin.list_pending()` —
Desk yapı istekleri aynı kartta `kind="desk_change"` olarak görünür; kararları
`apply_pending` / `reject_pending` ile verilir. İki kuyruk tek yüzeyde toplanır
(`ui-design` §2: "aynı bilgi ekranda bir kez").

Sohbet kuralı: kullanıcı sohbete "onaylıyorum" yazdığında **tek** bekleyen öğe
varsa o çözülür (`resolve_from_chat`); birden fazlaysa hiçbir şey yapılmaz ve
kullanıcı karttan seçer. Köprü de aynı kuralı uygular.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from entropy.core.event_bus import bus
from entropy.ui.design import TOKENS
from entropy.ui.widgets.lifecycle import discard_widget

__all__ = [
    "PendingWorkCard", "pending_queue", "desk_pending_entries",
    "APPROVAL_PHRASES", "RISK_LABELS", "DESK_KIND",
]

#: Desk yapı isteklerinin birleşik kuyruktaki türü.
DESK_KIND = "desk_change"

#: Sohbette onay sayılan ifadeler (küçük harfe indirilmiş, tam eşleşme değil).
APPROVAL_PHRASES = ("onaylıyorum", "onayliyorum", "onaylandı", "onayla")

#: Risk rozetinin insan okur karşılığı ve tonu.
RISK_LABELS: Dict[str, tuple] = {
    "low": ("düşük risk", "ok"),
    "medium": ("orta risk", "warn"),
    "high": ("yüksek risk", "danger"),
}


def pending_queue() -> Optional[Any]:
    """`entropy.core.pending.PendingQueue()` örneği; yoksa None (yumuşak düşüş)."""
    try:
        from entropy.core import pending as _pending  # type: ignore
    except Exception:
        return None
    factory = getattr(_pending, "PendingQueue", None)
    if factory is None:
        return None
    try:
        return factory()
    except Exception:
        return None


def desk_pending_entries() -> List[Dict[str, Any]]:
    """Desk yapı isteklerini birleşik kuyruk şemasına çevirir."""
    try:
        from entropy.agents import desk_admin  # type: ignore
    except Exception:
        return []
    lister = getattr(desk_admin, "list_pending", None)
    if lister is None:
        return []
    try:
        rows = list(lister() or [])
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for row in rows:
        data = dict(row) if isinstance(row, dict) else {}
        payload = data.get("payload") or {}
        title = str(data.get("summary") or data.get("kind") or "Desk değişikliği")
        out.append({
            "id": str(data.get("id") or ""),
            "kind": DESK_KIND,
            "title": title,
            "detail": str(payload.get("name") or payload.get("title") or ""),
            "risk": "medium",
            "created_at": data.get("created_at") or "",
            "source": "desk",
            "payload": payload,
            "status": "pending",
        })
    return out


class PendingWorkCard(QFrame):
    """Bekleyen işler: başlık, ayrıntı, risk rozeti, Onayla / Reddet."""

    #: (istek kimliği, onaylandı mı)
    decided = Signal(str, bool)

    def __init__(self, parent: Optional[QWidget] = None, queue: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self._queue = queue if queue is not None else pending_queue()
        self._rows: List[QWidget] = []
        self._entries: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            TOKENS["space"]["3"], TOKENS["space"]["2"],
            TOKENS["space"]["3"], TOKENS["space"]["2"],
        )
        layout.setSpacing(TOKENS["space"]["1"])

        self.title_label = QLabel("Bekleyen işler")
        self.title_label.setProperty("role", "heading")
        layout.addWidget(self.title_label)
        self.body = QVBoxLayout()
        self.body.setSpacing(TOKENS["space"]["1"])
        layout.addLayout(self.body)
        self._layout = layout

        signal = getattr(bus, "pending_changed", None)
        if signal is not None:
            signal.connect(self.on_pending_changed)
        # Desk kuyruğu kendi sinyalini kullanır (13-C sözleşmesi).
        desk_signal = getattr(bus, "desk_request_queued", None)
        if desk_signal is not None:
            desk_signal.connect(self.on_pending_changed)

        self.refresh()

    # ------------------------------------------------------------- veri

    def entries(self) -> List[Dict[str, Any]]:
        """Birleşik bekleyen öğe listesi (Entropy kuyruğu + Desk istekleri)."""
        rows: List[Dict[str, Any]] = []
        lister = getattr(self._queue, "list", None) if self._queue else None
        if lister is not None:
            try:
                for row in (lister() or []):
                    if isinstance(row, dict):
                        rows.append(dict(row))
            except Exception:
                pass
        rows.extend(desk_pending_entries())
        return [r for r in rows if str(r.get("status") or "pending") == "pending"]

    # ------------------------------------------------------------ görünüm

    @Slot()
    @Slot(dict)
    @Slot(str)
    def on_pending_changed(self, *_args) -> None:
        self.refresh()

    def refresh(self) -> None:
        for widget in self._rows:
            self.body.removeWidget(widget)
            discard_widget(widget)
        self._rows = []
        self._entries = self.entries()
        self.title_label.setText(
            f"Bekleyen işler ●{len(self._entries)}" if self._entries
            else "Bekleyen işler"
        )
        self.setVisible(bool(self._entries))
        for entry in self._entries:
            row = self._build_row(entry)
            self.body.addWidget(row)
            self._rows.append(row)

    def _build_row(self, entry: Dict[str, Any]) -> QWidget:
        """İki satırlık kart: başlık + risk, altında ayrıntı ve kararlar.

        Tek satır denendi ve 420 px'lik sağ panelde düğme metinleri kırpıldı
        ("Onayla" → "nayl"); karar düğmesi kırpılmış bir kartta okunmaz.
        """
        row = QFrame(self)
        row.setProperty("role", "panel")
        box = QVBoxLayout(row)
        box.setContentsMargins(
            TOKENS["space"]["2"], TOKENS["space"]["1"],
            TOKENS["space"]["2"], TOKENS["space"]["1"],
        )
        box.setSpacing(TOKENS["space"]["1"])

        head = QHBoxLayout()
        head.setSpacing(TOKENS["space"]["2"])
        title = QLabel(str(entry.get("title") or "İsimsiz istek"))
        title.setProperty("role", "body")
        title.setWordWrap(True)
        detail_text = str(entry.get("detail") or "")
        title.setToolTip(detail_text or title.text())
        head.addWidget(title, 1)

        label, tone = RISK_LABELS.get(str(entry.get("risk") or "medium"),
                                      RISK_LABELS["medium"])
        risk = QLabel(label)
        risk.setProperty("role", "badge")
        risk.setProperty("tone", tone)
        risk.setAccessibleName("Risk düzeyi")
        head.addWidget(risk, 0)
        box.addLayout(head)

        if detail_text:
            detail = QLabel(detail_text)
            detail.setProperty("role", "label")
            detail.setWordWrap(True)
            detail.setAccessibleName("İstek ayrıntısı")
            box.addWidget(detail)

        actions = QHBoxLayout()
        actions.setSpacing(TOKENS["space"]["2"])
        actions.addStretch()
        request_id = str(entry.get("id") or "")
        approve = QPushButton("Onayla")
        approve.setProperty("variant", "primary")
        approve.setAccessibleName(f"Onayla: {title.text()}")
        approve.setProperty("request_id", request_id)
        approve.clicked.connect(self._on_approve_clicked)
        actions.addWidget(approve)

        reject = QPushButton("Reddet")
        reject.setProperty("variant", "ghost")
        reject.setAccessibleName(f"Reddet: {title.text()}")
        reject.setProperty("request_id", request_id)
        reject.clicked.connect(self._on_reject_clicked)
        actions.addWidget(reject)
        box.addLayout(actions)
        return row

    @Slot()
    def _on_approve_clicked(self) -> None:
        sender = self.sender()
        if sender is not None:
            self.approve(str(sender.property("request_id") or ""))

    @Slot()
    def _on_reject_clicked(self) -> None:
        sender = self.sender()
        if sender is not None:
            self.reject(str(sender.property("request_id") or ""))

    # ------------------------------------------------------------- karar

    def approve(self, request_id: str, note: str = "") -> Optional[Dict[str, Any]]:
        return self._resolve(request_id, "approve", note)

    def reject(self, request_id: str, note: str = "") -> Optional[Dict[str, Any]]:
        return self._resolve(request_id, "reject", note)

    def _entry(self, request_id: str) -> Optional[Dict[str, Any]]:
        for entry in self._entries:
            if str(entry.get("id")) == str(request_id):
                return entry
        return None

    def _resolve(self, request_id: str, decision: str,
                 note: str = "") -> Optional[Dict[str, Any]]:
        entry = self._entry(request_id) or {"id": request_id, "kind": ""}
        result: Optional[Dict[str, Any]] = None
        if str(entry.get("kind")) == DESK_KIND:
            result = self._resolve_desk(request_id, decision, note)
        else:
            resolver = getattr(self._queue, "resolve", None) if self._queue else None
            if resolver is not None:
                try:
                    out = resolver(request_id, decision, note)
                    result = dict(out) if isinstance(out, dict) else {"ok": bool(out)}
                except Exception as exc:
                    result = {"ok": False, "message": f"{type(exc).__name__}: {exc}"}
        self.decided.emit(str(request_id), decision == "approve")
        self.refresh()
        return result

    @staticmethod
    def _resolve_desk(request_id: str, decision: str,
                      note: str) -> Optional[Dict[str, Any]]:
        try:
            from entropy.agents import desk_admin  # type: ignore
        except Exception:
            return None
        fn = getattr(
            desk_admin, "apply_pending" if decision == "approve" else "reject_pending",
            None,
        )
        if fn is None:
            return None
        try:
            out = fn(request_id) if decision == "approve" else fn(request_id, note)
        except Exception as exc:
            return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}
        return dict(out) if isinstance(out, dict) else {"ok": bool(out)}

    # --------------------------------------------------------- sohbet yolu

    def resolve_from_chat(self, text: str) -> Optional[Dict[str, Any]]:
        """Sohbetteki "onaylıyorum" ifadesini TEK bekleyen öğeye uygular.

        Birden fazla öğe bekliyorsa hiçbir şey yapılmaz: hangi işin
        onaylandığı belirsizken komut çalıştırmak kullanıcının kastı değildir.
        """
        needle = " ".join(str(text or "").lower().split())
        if not any(phrase in needle for phrase in APPROVAL_PHRASES):
            return None
        self._entries = self.entries()
        if len(self._entries) != 1:
            return None
        return self.approve(str(self._entries[0].get("id") or ""), note=str(text or ""))
