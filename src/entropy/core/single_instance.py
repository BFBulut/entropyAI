"""
Tek kopya kilidi.

Uygulama pencere kapatılınca tepsiye çekilir ve süreç yaşamaya devam eder; ikinci
bir başlatma (autostart + elle açma, ya da kısayola iki kez tıklama) aynı SQLite
belleği, ledger'ı ve .entropy dosyalarını paylaşan ikinci bir kopya üretiyordu.
Gözlenen donmaların en olası nedeni buydu ve dist/ klasörü de kilitli kalıyordu.

Mekanizma: QLocalServer ile adlandırılmış yerel bir soket. İlk kopya sunucuyu
açar; sonraki kopya bağlanabilirse "activate" gönderip çıkar, ilk kopya bunu
alınca mevcut pencereyi öne getirir.
"""

from __future__ import annotations

import getpass
import logging
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

ACTIVATE_MESSAGE = b"activate\n"
PING_MESSAGE = b"ping\n"
ACK_MESSAGE = b"ok\n"


def default_lock_name(app_name: str = "EntropyAI") -> str:
    """Kullanıcıya özel soket adı; farklı Windows hesapları birbirini engellemesin."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    safe = "".join(c if c.isalnum() else "_" for c in f"{app_name}-{user}")
    return f"{safe}-single-instance"


class SingleInstanceGuard(QObject):
    """
    Kullanım:
        guard = SingleInstanceGuard()
        if not guard.try_acquire():
            guard.notify_existing()   # önceki kopyayı öne getir
            sys.exit(0)
        guard.activated.connect(ui.bring_to_front)
    """

    activated = Signal()

    def __init__(self, name: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.name = name or default_lock_name()
        self._server: Optional[QLocalServer] = None

    # -- birincil kopya -------------------------------------------------

    def try_acquire(self, connect_timeout_ms: int = 300) -> bool:
        """
        Kilidi almaya çalışır. Başka bir kopya dinliyorsa False döner.

        Önce bağlanmayı dener: gerçekten dinleyen bir kopya varsa bağlantı
        kurulur. Bağlanamazsa (çökmüş bir kopyadan kalan ölü soket olabilir)
        kalıntı temizlenip sunucu açılır.
        """
        # Yoklama da el sıkışmalı: yalnızca bağlanıp kopan bir istemci, Windows
        # adlandırılmış borusunda sunucunun kuyruğuna "ölü" bir bağlantı bırakıyor
        # ve arkasından gelen gerçek mesajın baytları kayboluyordu.
        if self._handshake(PING_MESSAGE, connect_timeout_ms) is not None:
            return False

        QLocalServer.removeServer(self.name)
        server = QLocalServer(self)
        if not server.listen(self.name):
            logger.warning("Tek kopya soketi açılamadı (%s): %s", self.name, server.errorString())
            # Dinleyemiyorsak kilidi zorlamayız; uygulama yine de açılsın.
            return True
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        return True

    def _on_new_connection(self):
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            if sock is None:
                continue
            # İstemci mesajını yazıp sunucunun "ok" yanıtını bekler; bu yüzden
            # bağlantı biz okuyana kadar açık kalır ve baytlar kaybolmaz.
            if not sock.bytesAvailable():
                sock.waitForReadyRead(500)
            self._consume(sock)

    def _consume(self, sock: QLocalSocket):
        try:
            data = bytes(sock.readAll())
        except Exception:
            data = b""
        if ACTIVATE_MESSAGE.strip() in data:
            self.activated.emit()
        try:
            sock.write(ACK_MESSAGE)
            sock.flush()
            sock.waitForBytesWritten(200)
            sock.disconnectFromServer()
        except Exception:
            pass

    # -- ikincil kopya --------------------------------------------------

    def _handshake(self, message: bytes, timeout_ms: int) -> Optional[bytes]:
        """
        Sunucuya mesaj gönderip yanıtını bekler. Sunucu yoksa None döner.

        Yanıt beklemek iki iş görür: kilidin gerçekten canlı bir kopyada olduğunu
        doğrular ve mesaj okunmadan bağlantının kapanmasını engeller.
        """
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        if not sock.waitForConnected(timeout_ms):
            return None
        sock.write(message)
        sock.flush()
        sock.waitForBytesWritten(timeout_ms)
        reply = b""
        if sock.waitForReadyRead(max(timeout_ms, 500)):
            reply = bytes(sock.readAll())
        sock.disconnectFromServer()
        return reply

    def notify_existing(self, timeout_ms: int = 500) -> bool:
        """Çalışan kopyaya öne çıkma isteği gönderir; yanıt gelirse True."""
        reply = self._handshake(ACTIVATE_MESSAGE, timeout_ms)
        return reply is not None

    def release(self):
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self.name)
            self._server = None
