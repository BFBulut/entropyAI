"""
`bus.task_report_ready` → sohbet kartı köprüsü (Faz 11-C, iş 3).

Chat ve Zen kipleri aynı davranışı paylaşır; mantık tek yerde dursun diye
karışım (mixin) olarak yazıldı. Sunum ve metin üretimi Qt'siz
`report_chat_card` modülünde; burada yalnızca sinyal bağlama ve widget
dokunuşu var.

Kullanım (kipin `__init__` sonunda, `chat_browser` kurulduktan sonra):

    self.install_report_cards()

Sinyal alıcısı QObject metodudur (lambda değil): yük işçi iş parçacığından
gelse bile Qt bağlantıyı kuyruklar.
"""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Slot
from PySide6.QtGui import QTextCursor

from entropy.core.event_bus import bus
from entropy.ui.widgets.report_chat_card import (
    CONTEXT_SCHEME, ReportContextQueue, normalize_report_payload,
    notification_title, report_card_html, resolve_report_path,
)


class ReportCardMixin:
    """Rapor kartı + "Sohbete al" bağlam kuyruğu davranışı."""

    def install_report_cards(self) -> None:
        self.report_context = ReportContextQueue()
        self.report_payloads: Dict[str, Dict[str, Any]] = {}
        signal = getattr(bus, "task_report_ready", None)
        if signal is not None:
            signal.connect(self._on_task_report_ready)

    # ------------------------------------------------------------ sinyal

    def should_notify_once(self, identity: str) -> bool:
        """Aynı OLAY için ikinci kartı engeller (Faz 14-E madde 6).

        Faz 14 planı §2: bir kart koşusu `report_created` + `task_report_ready`
        + `task_notification` üreticilerinden ≥ 3 bildirim kartı basıyordu.
        Eski çözüm 10 saniyelik zaman penceresiydi ve ikinci koşum yeni dosya
        yazınca işe yaramıyordu; artık ölçüt **kimlik**: kart kimliği ya da
        normalize edilmiş rapor yolu. Kimlik boşsa kart basılır (bilgi
        kaybetmek gürültüden kötüdür).
        """
        ident = " ".join(str(identity or "").split()).lower()
        if not ident:
            return True
        seen = getattr(self, "_notified_identities", None)
        if seen is None:
            seen = set()
            self._notified_identities = seen
        if ident in seen:
            return False
        seen.add(ident)
        return True

    @Slot(dict)
    def _on_task_report_ready(self, payload: dict) -> None:
        """Rapor kartını sohbete basar ve bildirim merkezine girdi ekler."""
        data = normalize_report_payload(payload)
        key = data["card_id"] or data["title"]
        self.report_payloads[key] = data
        identity = str(data.get("card_id") or "") or str(
            resolve_report_path(data) or data.get("title") or ""
        )
        if not self.should_notify_once(identity):
            return
        browser = getattr(self, "chat_browser", None)
        if browser is not None:
            browser.append(report_card_html(data))
            browser.moveCursor(QTextCursor.MoveOperation.End)
        center = getattr(self, "notification_center", None)
        if center is not None:
            try:
                center.add("report", notification_title(data), resolve_report_path(data))
            except Exception:
                pass

    # ------------------------------------------------------------ eylemler

    def handle_context_anchor(self, url_str: str) -> bool:
        """
        `entropy-context://<anahtar>` bağlantısını çözer ("Sohbete al").

        Bilinen bir rapor değilse False döner ki çağıran taraf bağlantıyı
        başka bir işleyiciye devretsin.
        """
        if CONTEXT_SCHEME not in url_str:
            return False
        key = url_str.split(CONTEXT_SCHEME, 1)[-1].rstrip("/")
        from urllib.parse import unquote

        key = unquote(key)
        data = getattr(self, "report_payloads", {}).get(key)
        if data is None:
            return False
        self.report_context.add(data)
        appender = getattr(self, "_append_message", None) or getattr(
            self, "_append_chat_message", None
        )
        if callable(appender):
            appender(
                "Entropy AI",
                f"Rapor bağlama alındı: <b>{data['title']}</b> — bir sonraki "
                "mesajınızla birlikte gönderilecek.",
                is_system=True,
            )
        return True

    def apply_report_context(self, prompt: str) -> str:
        """Bekleyen rapor bloklarını istemin başına ekler ve kuyruğu boşaltır."""
        queue = getattr(self, "report_context", None)
        if queue is None:
            return prompt
        return queue.apply(prompt)
