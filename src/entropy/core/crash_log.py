"""
Çökme ve istisna günlüğü.

Pencereli (konsolsuz) derlemede stderr yoktur: yakalanmayan bir Python istisnası,
Qt'nin qFatal mesajı ya da yerel bir hata iz bırakmadan uygulamayı kapatır.
"Damıtma başlattım, uygulama kapandı" türü şikayetlerde Windows olay günlüğü
yalnızca yerel çökmeleri gösterir; Python düzeyindeki kapanışlar için tek kayıt
bu dosyadır: <durum dizini>/logs/entropy.log
"""

from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional

_INSTALLED: Optional[Path] = None
_FAULT_FILE = None  # faulthandler'ın yazacağı dosya açık kalmalı


def log_path() -> Optional[Path]:
    return _INSTALLED


def install_crash_logging(log_dir: Path) -> Optional[Path]:
    """
    Günlük dosyasını kurar; yakalanmayan istisnalar uygulamayı kapatmaz, yazılır.

    - sys.excepthook / threading.excepthook: tam iz + hangi iş parçacığı.
    - faulthandler: yerel çökmede (erişim ihlali, abort) Python yığınlarını dosyaya döker.
    - Qt mesajları (uyarı/kritik/fatal) aynı dosyaya düşer; "different thread" gibi
      iş parçacığı uyarıları burada görünür.
    Dönen değer günlük dosyasının yolu; kurulamazsa None (uygulama yine açılır).
    """
    global _INSTALLED, _FAULT_FILE
    if _INSTALLED is not None:
        return _INSTALLED
    try:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "entropy.log"

        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(threadName)s]: %(message)s"))
        handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(handler)
        if root.level > logging.INFO or root.level == logging.NOTSET:
            root.setLevel(logging.INFO)

        _FAULT_FILE = open(log_dir / "entropy_fault.log", "a", encoding="utf-8")
        faulthandler.enable(file=_FAULT_FILE, all_threads=True)

        crash_logger = logging.getLogger("entropy.crash")

        def _excepthook(exc_type, exc, tb):
            crash_logger.critical(
                "Yakalanmayan istisna (ana iş parçacığı):\n%s",
                "".join(traceback.format_exception(exc_type, exc, tb)),
            )

        def _thread_hook(args):
            crash_logger.critical(
                "Yakalanmayan istisna (iş parçacığı %s):\n%s",
                getattr(args.thread, "name", "?"),
                "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
            )

        sys.excepthook = _excepthook
        threading.excepthook = _thread_hook

        try:
            from PySide6.QtCore import QtMsgType, qInstallMessageHandler

            _levels = {
                QtMsgType.QtDebugMsg: logging.DEBUG,
                QtMsgType.QtInfoMsg: logging.INFO,
                QtMsgType.QtWarningMsg: logging.WARNING,
                QtMsgType.QtCriticalMsg: logging.ERROR,
                QtMsgType.QtFatalMsg: logging.CRITICAL,
            }
            qt_logger = logging.getLogger("qt")

            def _qt_handler(msg_type, context, message):
                qt_logger.log(_levels.get(msg_type, logging.WARNING), "%s", message)
                if msg_type == QtMsgType.QtFatalMsg:
                    for h in root.handlers:
                        try:
                            h.flush()
                        except Exception:
                            pass

            qInstallMessageHandler(_qt_handler)
        except Exception as exc:  # PySide yoksa (testler) yalnızca Python tarafı kurulur
            crash_logger.info("Qt mesaj yakalayıcı kurulamadı: %s", exc)

        crash_logger.info("Çökme günlüğü kuruldu: %s", path)
        _INSTALLED = path
        return path
    except Exception as exc:
        logging.getLogger(__name__).warning("Çökme günlüğü kurulamadı: %s", exc)
        return None
