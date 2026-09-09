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
import threading
import time
from typing import Callable, Optional

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, Signal, Slot
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

ACTIVATE_MESSAGE = b"activate\n"
PING_MESSAGE = b"ping\n"
ACK_MESSAGE = b"ok\n"

# Yük altında tek bir waitForReadyRead yetmiyordu; son tarihli okuma döngüsü
# için taban süre (ms).
READ_TIMEOUT_MS = 3000
# ACK'siz kalan öne çıkarma isteği için yeniden deneme sayısı.
NOTIFY_ATTEMPTS = 3
# Sunucu tarafı okuma süresi kısa tutulur: mesajsız (ölü) bir bağlantı,
# arkasındaki gerçek isteği bekletmemeli.
CONSUME_TIMEOUT_MS = 800


def default_lock_name(app_name: str = "EntropyAI") -> str:
    """Kullanıcıya özel soket adı; farklı Windows hesapları birbirini engellemesin."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    safe = "".join(c if c.isalnum() else "_" for c in f"{app_name}-{user}")
    return f"{safe}-single-instance"


class _ServerWorker(QObject):
    """
    Soket sunucusunu KENDİ iş parçacığında çalıştırır.

    Sunucu ana iş parçacığındayken, ana döngü meşgulse (uzun bir UI işi ya da
    testte yığılmış olay kuyruğu) gelen bağlantı saniyelerce kabul edilmiyor,
    ikinci kopya ACK alamadan pes ediyordu. Kendi olay döngüsünde bekleyen bir
    sunucu bundan etkilenmez; `activated` sinyali Qt tarafından kuyruklu
    bağlantıyla ana iş parçacığına taşınır.
    """

    activated = Signal()
    listen_finished = Signal(bool)

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self._server: Optional[QLocalServer] = None

    @Slot()
    def start_listening(self):
        QLocalServer.removeServer(self.name)
        server = QLocalServer()
        if not server.listen(self.name):
            logger.warning("Tek kopya soketi açılamadı (%s): %s", self.name, server.errorString())
            self.listen_finished.emit(False)
            return
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        self.listen_finished.emit(True)

    @Slot()
    def stop(self):
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self.name)
            self._server = None

    @Slot()
    def _on_new_connection(self):
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            if sock is None:
                continue
            # İstemci mesajını yazıp sunucunun "ok" yanıtını bekler; bu yüzden
            # bağlantı biz okuyana kadar açık kalır ve baytlar kaybolmaz.
            self._consume(sock)

    def _consume(self, sock: QLocalSocket, timeout_ms: int = CONSUME_TIMEOUT_MS):
        """
        İstemci mesajını son tarihli döngüyle okur. Yük altında ilk
        waitForReadyRead boş dönebiliyordu; o durumda eskiden yine de ACK
        yazılıyor ve istemci mesajı hiç ulaşmadan başarı sanıyordu.
        Veri okunamazsa ACK yazmıyoruz: istemci başarısızlığı görsün.
        """
        deadline = time.monotonic() + timeout_ms / 1000.0
        data = b""
        while True:
            try:
                data += bytes(sock.readAll())
            except Exception:
                pass
            if data.strip():
                break
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                break
            if sock.state() != QLocalSocket.LocalSocketState.ConnectedState and not sock.bytesAvailable():
                break
            sock.waitForReadyRead(min(remaining_ms, 100))

        if not data.strip():
            logger.warning("Tek kopya sunucusu boş bağlantı aldı; ACK yazılmadı.")
            try:
                sock.disconnectFromServer()
            except Exception:
                pass
            return

        if ACTIVATE_MESSAGE.strip() in data:
            self.activated.emit()
        try:
            sock.write(ACK_MESSAGE)
            sock.flush()
            sock.waitForBytesWritten(timeout_ms)
            sock.disconnectFromServer()
        except Exception:
            pass


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
        self._worker: Optional[_ServerWorker] = None
        self._thread: Optional[QThread] = None

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
        #
        # Ama kilidi çalma kararı ACK'e bağlanmamalı: yük altında ilk kopyanın
        # olay döngüsü ACK'i geciktirebiliyor ve ikinci kopya soketi silip
        # kendini birincil ilan ediyordu (testte "ACQ True"). Bağlantının
        # kurulabilmesi canlı bir dinleyicinin kesin kanıtıdır; ölü kalıntıda
        # Windows adlandırılmış borusuna bağlanılamaz.
        if self._probe_existing(connect_timeout_ms):
            return False

        return self._start_server_thread()

    def _start_server_thread(self, timeout_ms: int = READ_TIMEOUT_MS) -> bool:
        """Sunucuyu ayrı iş parçacığında açar; dinleyemesek de True döneriz."""
        worker = _ServerWorker(self.name)
        thread = QThread()
        worker.moveToThread(thread)
        worker.activated.connect(self.activated)  # kuyruklu: sahibin iş parçacığına taşınır

        listening: list[bool] = []
        ready = threading.Event()

        def _on_listen(ok: bool):
            listening.append(ok)
            ready.set()

        worker.listen_finished.connect(_on_listen, Qt.ConnectionType.DirectConnection)
        thread.started.connect(worker.start_listening)
        thread.start()
        ready.wait(timeout_ms / 1000.0)

        self._worker = worker
        self._thread = thread
        if not listening or not listening[0]:
            # Dinleyemiyorsak kilidi zorlamayız; uygulama yine de açılsın.
            return True
        return True

    # -- ikincil kopya --------------------------------------------------

    def _probe_existing(self, timeout_ms: int) -> bool:
        """
        Dinleyen bir kopya var mı? ACK gelirse kesin evet; ACK gelmese bile
        bağlantı kurulabildiyse evet sayarız (kilidi çalmaktansa ikinci kopya
        çıksın).
        """
        if self._handshake(PING_MESSAGE, timeout_ms) is not None:
            return True
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        connected = sock.waitForConnected(timeout_ms)
        if connected:
            # Yalnızca bağlanıp kopmak sunucu kuyruğunda "ölü" bağlantı
            # bırakıyor ve peşinden gelen activate mesajının baytları
            # kayboluyordu; bu yüzden burada da mesaj yazıp akıtıyoruz.
            sock.write(PING_MESSAGE)
            sock.flush()
            sock.waitForBytesWritten(timeout_ms)
            sock.waitForReadyRead(timeout_ms)
            sock.disconnectFromServer()
        return connected

    def _handshake(self, message: bytes, timeout_ms: int) -> Optional[bytes]:
        """
        Sunucuya mesaj gönderip ACK'ini bekler. Sunucu yoksa ya da ACK
        gelmezse None döner (başarısızlık). Eskiden boş yanıt da (b"")
        başarı sayılıyordu; bu yüzden mesajı hiç okumayan bir sunucu
        `notify_existing`'e True döndürüyordu.

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

        # Son tarihli okuma döngüsü: tek bir waitForReadyRead yük altında
        # ACK'ten önce zaman aşımına uğrayabiliyor.
        wait_ms = max(timeout_ms, READ_TIMEOUT_MS)
        deadline = time.monotonic() + wait_ms / 1000.0
        reply = b""
        while True:
            try:
                reply += bytes(sock.readAll())
            except Exception:
                pass
            if ACK_MESSAGE.strip() in reply:
                break
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                break
            if sock.state() != QLocalSocket.LocalSocketState.ConnectedState and not sock.bytesAvailable():
                break
            sock.waitForReadyRead(min(remaining_ms, 100))

        sock.disconnectFromServer()
        if ACK_MESSAGE.strip() not in reply:
            return None
        return reply

    def notify_existing(self, timeout_ms: int = 500) -> bool:
        """
        Çalışan kopyaya öne çıkma isteği gönderir; ACK gelirse True.

        Yük altında ilk deneme ACK'siz kalabildiği için birkaç kez denenir;
        ACK yoksa mesajın işlendiğine dair kanıt da yoktur.
        """
        for _ in range(NOTIFY_ATTEMPTS):
            if self._handshake(ACTIVATE_MESSAGE, timeout_ms) is not None:
                return True
        return False

    def release(self):
        if self._worker is not None:
            # Kapatma işi sunucunun kendi iş parçacığında yapılmalı.
            QMetaObject.invokeMethod(self._worker, "stop", Qt.ConnectionType.BlockingQueuedConnection)
            self._worker = None
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None
