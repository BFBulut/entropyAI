"""Desk düzenleme onayları — yapı değişikliği kullanıcı onayı olmadan uygulanmaz.

Faz 13-C madde 1. Entropy sohbette bir Desk düzenlemesi istediğinde
(`[DESK office …]`, `[DESK agent …]`, `[DESK task …]`) hiçbir şey oluşmaz:
istek kuyruğa yazılır ve sohbete "Desk düzenleme onayı bekliyor …" satırı
düşer. O satır bugüne kadar yalnızca bir slash komutuna
(`/desk approve <id>`) işaret ediyordu; kullanıcı kimliği elle yazmak
zorundaydı. Bu panel aynı kuyruğu, kural/beceri adaylarıyla AYNI yüzeyde
(Ajanlar sekmesi) düğmeye bağlar.

Sözleşme (`entropy.agents.desk_admin`, köprü ajanı):

    list_pending() -> [dict(id, kind, payload, created_at, source, summary)]
    apply_pending(id) -> dict(ok, message, created_paths)
    reject_pending(id, reason="") -> bool

Modül ya da işlevlerden biri yoksa panel boş ve pasif kalır (guard); ürün
kırılmaz, hiçbir şey uygulanmaz.
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

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

__all__ = ["DeskApprovalsPanel", "desk_admin_api", "request_field", "KIND_LABELS"]

#: Kuyruktaki isteğin insan okur karşılığı (ekranda "kind" ham yazılmaz).
KIND_LABELS: Dict[str, str] = {
    "office": "Yeni ofis",
    "agent": "Yeni ajan",
    "task": "Yeni görev kartı",
    "msg": "Ofise talimat",
}


def desk_admin_api() -> Optional[Any]:
    """`entropy.agents.desk_admin` modülü; yoksa None."""
    try:
        from entropy.agents import desk_admin  # type: ignore

        return desk_admin
    except Exception:
        return None


def request_field(record: Any, name: str, default: Any = "") -> Any:
    """İstek sözlük ya da dataclass fark etmeksizin alan okur."""
    if isinstance(record, dict):
        value = record.get(name, default)
    else:
        value = getattr(record, name, default)
    return default if value is None else value


class DeskApprovalsPanel(QFrame):
    """Bekleyen Desk düzenlemeleri; Onayla/Reddet ile sözleşmeyi çağırır."""

    #: (istek kimliği, onaylandı mı)
    request_decided = Signal(str, bool)

    def __init__(self, parent: Optional[QWidget] = None, api: Any = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self._api = api
        self._last_message = ""

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

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("role", "label")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Kuyruk dosya tabanlı: ofis/kadro değişince (uygulama sonrası) yenilenir.
        signal = getattr(bus, "offices_updated", None)
        if signal is not None:
            try:
                signal.connect(self.on_offices_updated)
            except Exception:
                pass

        self.refresh()

    # ------------------------------------------------------------ veri

    def api(self) -> Optional[Any]:
        return self._api if self._api is not None else desk_admin_api()

    def pending(self) -> List[Any]:
        lister = getattr(self.api(), "list_pending", None)
        if not callable(lister):
            return []
        try:
            return list(lister() or [])
        except Exception:
            return []

    def pending_count(self) -> int:
        return len(self.pending())

    # ------------------------------------------------------------ görünüm

    @Slot()
    def refresh(self) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                discard_widget(widget)

        items = self.pending()
        self.title_label.setText(
            f"<b style='color:{RT['accent']}; font-size:13px;'>DESK ONAYLARI</b>"
            f" <span style='color:{RT['text_dim']}; font-size:11px;'>"
            f"· {len(items)} bekleyen · onaysız hiçbir yapı oluşmaz</span>"
        )
        if not items:
            empty = QLabel(
                "Bekleyen Desk düzenlemesi yok. Entropy ofis, ajan ya da kart"
                " oluşturmak isterse burada sorulur."
            )
            empty.setWordWrap(True)
            empty.setProperty("role", "label")
            self.body_layout.addWidget(empty)
        for record in items:
            self.body_layout.addWidget(self._make_row(record))
        self.body_layout.addStretch()

    def _make_row(self, record: Any) -> QWidget:
        request_id = str(request_field(record, "id", ""))
        kind = str(request_field(record, "kind", ""))
        summary = str(request_field(record, "summary", "") or request_id)
        created = str(request_field(record, "created_at", ""))
        source = str(request_field(record, "source", ""))
        kind_label = KIND_LABELS.get(kind, kind or "Desk düzenlemesi")

        row = QFrame()
        row.setObjectName("deskApprovalRow")
        row.setProperty("role", "panel")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(
            TOKENS["space"]["2"], TOKENS["space"]["1"],
            TOKENS["space"]["2"], TOKENS["space"]["1"],
        )
        row_layout.setSpacing(TOKENS["space"]["1"])

        meta_bits = [bit for bit in (created[:16].replace("T", " "), source) if bit]
        text = QLabel(
            f"<b style='color:{RT['text']}; font-size:13px;'>"
            f"{html.escape(kind_label)}</b>"
            f"<br/><span style='color:{RT['text_dim']}; font-size:11px;'>"
            f"{html.escape(summary[:180])}</span>"
            + (f"<br/><span style='color:{RT['text_dim']}; font-size:11px;'>"
               f"{html.escape(' · '.join(meta_bits))}</span>" if meta_bits else "")
            + f"<br/><span style='color:{RT['accent_warn']}; font-size:11px;'>"
              f"durum: onay bekliyor</span>"
        )
        text.setWordWrap(True)
        row_layout.addWidget(text)

        buttons = QHBoxLayout()
        buttons.setSpacing(TOKENS["space"]["1"])
        approve = QPushButton("Onayla")
        approve.setProperty("variant", "primary")
        approve.setAccessibleName(f"Desk düzenlemesini onayla: {kind_label}")
        approve.setToolTip("Düzenleme uygulanır; ofis/ajan/kart gerçekten oluşur.")
        approve.setProperty("request_id", request_id)
        approve.clicked.connect(self._on_approve_clicked)
        buttons.addWidget(approve)

        reject = QPushButton("Reddet")
        reject.setProperty("variant", "ghost")
        reject.setAccessibleName(f"Desk düzenlemesini reddet: {kind_label}")
        reject.setToolTip("İstek silinir; hiçbir yapı oluşmaz.")
        reject.setProperty("request_id", request_id)
        reject.clicked.connect(self._on_reject_clicked)
        buttons.addWidget(reject)
        buttons.addStretch()
        row_layout.addLayout(buttons)
        return row

    def _set_status(self, message: str, ok: bool = True) -> None:
        self._last_message = str(message or "")
        if not self._last_message:
            self.status_label.setVisible(False)
            return
        color = RT["accent"] if ok else RT["accent_warn"]
        self.status_label.setText(
            f"<span style='color:{color}; font-size:11px;'>"
            f"{html.escape(self._last_message)}</span>"
        )
        self.status_label.setVisible(True)

    def last_message(self) -> str:
        return self._last_message

    # ------------------------------------------------------------ eylem

    @Slot()
    def _on_approve_clicked(self) -> None:
        sender = self.sender()
        self.approve(str(sender.property("request_id") or ""))

    @Slot()
    def _on_reject_clicked(self) -> None:
        sender = self.sender()
        self.reject(str(sender.property("request_id") or ""))

    def approve(self, request_id: str) -> bool:
        """İsteği uygular. Uygulama BAŞARISIZSA kayıt kuyrukta kalır."""
        if not request_id:
            return False
        fn = getattr(self.api(), "apply_pending", None)
        if not callable(fn):
            return False
        try:
            result = fn(request_id)
        except Exception as exc:
            self._set_status(f"Uygulanamadı: {exc}", ok=False)
            return False
        data = result if isinstance(result, dict) else {"ok": bool(result)}
        ok = bool(data.get("ok"))
        self._set_status(
            str(data.get("message") or ("Uygulandı." if ok else "Uygulanamadı.")),
            ok=ok,
        )
        self.refresh()
        if ok:
            self.request_decided.emit(request_id, True)
            # Kadro/ofis listesi taze olsun: ofis ya da ajan yeni doğmuş olabilir.
            signal = getattr(bus, "offices_updated", None)
            if signal is not None:
                try:
                    signal.emit("")
                except Exception:
                    pass
        return ok

    def reject(self, request_id: str, reason: str = "kullanıcı reddetti") -> bool:
        if not request_id:
            return False
        fn = getattr(self.api(), "reject_pending", None)
        if not callable(fn):
            return False
        try:
            ok = bool(fn(request_id, reason))
        except Exception as exc:
            self._set_status(f"Reddedilemedi: {exc}", ok=False)
            return False
        self._set_status("İstek reddedildi; hiçbir yapı oluşmadı." if ok
                         else "İstek bulunamadı.", ok=ok)
        self.refresh()
        if ok:
            self.request_decided.emit(request_id, False)
        return ok

    @Slot(str)
    def on_offices_updated(self, *_args: Any) -> None:
        """`bus.offices_updated` alıcısı (QObject slotu, lambda değil)."""
        self.refresh()
