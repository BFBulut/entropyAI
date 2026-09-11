"""
Bekleyen işler — TEK kuyruk (Faz 14-B, sözleşme `docs/ARCHITECTURE.md` §6.7).

Neden
-----
Faz 14 analizinde ölçülen arıza: kullanıcı "onaylıyorum" dediğinde onaylanacak
bir şey uygulamaya hiç ulaşmıyordu. Araç izni için CLI'ın kendi diyaloğu saf
kiple birlikte düşmüştü (`--dangerously-skip-permissions`), Desk değişiklikleri
ayrı bir kuyrukta (`agents/desk_admin.py`) duruyordu, kural/beceri adaylarının
kuyruğu yoktu. Dört akış artık TEK modelde buluşur:

    tool_permission   CLI izin aracı (`core/permission_server.py`)
    desk_change       `[DESK …]` blokları (desk_admin kuyruğu SARMALANIR)
    rule_candidate    ajanın keşfettiği kural
    skill_candidate   beceri sentezleyici

Tasarım kısıtları
-----------------
* **Qt yok.** Bu modülü izin MCP sunucusu AYRI BİR SÜREÇTE (CLI'ın çocuğu)
  içe aktarır; oraya PySide6 taşımak hem ağır hem gereksizdir. Olay veriyolu
  yalnızca varsa ve `ENTROPY_PENDING_NO_BUS` boşsa tembel içe aktarılır.
* **Kanal dosyadır.** İki süreç (uygulama ve MCP sunucusu) aynı klasörü
  paylaşır; karar `<veri kökü>/pending/<id>.json` üzerinden yoklanır. Spike
  ölçtü: CLI yanıt süresine üst sınır koymuyor (45 sn bekleme sorunsuz koştu),
  bu yüzden 200 ms'lik yoklama fazlasıyla yeterli ve soket/named pipe'ın
  taşınabilirlik bedeline gerek yok.
* **Kayıt bırakmayan silme yoktur.** Çözülen kayıt silinmez; `status` alanı
  `approved|rejected|expired` olur ve karar/not/zaman damgası saklanır.
* **Tek yön korunur.** Desk bu kuyruğa kart İTEMEZ; yalnızca kendi değişiklik
  istekleri onay için buraya düşer (ADR-0001).

Sözleşme (arayüz `ui/widgets/pending_card.py` bunu varsayar):

    PendingQueue(root: Path)
    add(kind, title, detail, risk="low", source="", payload=None) -> str
    list(kind=None, status="pending") -> list[dict]
    resolve(id, decision, note="") -> dict
    wait(id, timeout_s) -> dict | None      # bloklayan; MCP sunucusu kullanır

Öğe şeması: `id, kind, title, detail, risk, created_at, source, payload,
status` (+ çözülmüşse `decision, decided_at, note`).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# --- sözleşme sabitleri ------------------------------------------------------

KIND_TOOL_PERMISSION = "tool_permission"
KIND_DESK_CHANGE = "desk_change"
KIND_RULE_CANDIDATE = "rule_candidate"
KIND_SKILL_CANDIDATE = "skill_candidate"
KINDS = (
    KIND_TOOL_PERMISSION,
    KIND_DESK_CHANGE,
    KIND_RULE_CANDIDATE,
    KIND_SKILL_CANDIDATE,
)

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_EXPIRED = "expired"

DECISION_APPROVE = "approve"
DECISION_REJECT = "reject"

RISKS = ("low", "medium", "high")

#: Kuyruğun olay veriyoluna dokunmasını kapatan ortam değişkeni (çocuk süreç).
NO_BUS_ENV = "ENTROPY_PENDING_NO_BUS"

#: `wait()` yoklama aralığı (sn).
POLL_INTERVAL_S = 0.2

__all__ = [
    "KIND_TOOL_PERMISSION",
    "KIND_DESK_CHANGE",
    "KIND_RULE_CANDIDATE",
    "KIND_SKILL_CANDIDATE",
    "KINDS",
    "STATUS_PENDING",
    "STATUS_APPROVED",
    "STATUS_REJECTED",
    "STATUS_EXPIRED",
    "DECISION_APPROVE",
    "DECISION_REJECT",
    "RISKS",
    "NO_BUS_ENV",
    "POLL_INTERVAL_S",
    "PendingQueue",
    "PendingWatcher",
    "queue",
    "start_watcher",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()) or "istek"


def _emit_changed(payload: Dict[str, Any]) -> None:
    """`bus.pending_changed` — Qt yoksa ya da kapalıysa sessizce atlanır."""
    if os.environ.get(NO_BUS_ENV):
        return
    try:
        from entropy.core.event_bus import bus

        bus.pending_changed.emit(dict(payload))
    except Exception:
        logger.debug("pending_changed yayılamadı", exc_info=True)


class PendingQueue:
    """Dosya tabanlı bekleyen işler kuyruğu (süreçler arası, Qt'siz)."""

    def __init__(self, root: Optional[Path | str] = None):
        from entropy.core.paths import pending_root

        self.root: Path = pending_root(root)

    # --- yollar ------------------------------------------------------------

    def path_for(self, item_id: str) -> Path:
        return self.root / f"{_safe_id(item_id)}.json"

    # --- yazma -------------------------------------------------------------

    def add(
        self,
        kind: str,
        title: str,
        detail: str = "",
        risk: str = "low",
        source: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Yeni bir bekleyen iş yazar ve KİMLİĞİNİ döndürür."""
        kind = str(kind or "").strip() or KIND_TOOL_PERMISSION
        risk = str(risk or "low").strip().lower()
        if risk not in RISKS:
            risk = "low"
        item_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{_safe_id(kind)}-{uuid.uuid4().hex[:6]}"
        record = {
            "id": item_id,
            "kind": kind,
            "title": str(title or "").strip(),
            "detail": str(detail or "").strip(),
            "risk": risk,
            "created_at": _now(),
            "source": str(source or ""),
            "payload": dict(payload or {}),
            "status": STATUS_PENDING,
        }
        self._write(record)
        _emit_changed({"action": "added", "item": dict(record)})
        return item_id

    def resolve(self, item_id: str, decision: str, note: str = "") -> Dict[str, Any]:
        """
        Kararı kaydeder ve GÜNCEL künyeyi döndürür.

        `desk_change` öğeleri (sarmalanan `desk_admin` kuyruğu) kendi
        uygulayıcısına yönlendirilir: dosya BU kökte değildir, taşınmaz.
        """
        decision = str(decision or "").strip().lower()
        if decision not in (DECISION_APPROVE, DECISION_REJECT):
            raise ValueError(f"Geçersiz karar: {decision!r}")
        path = self.path_for(item_id)
        if not path.is_file():
            resolved = self._resolve_desk(item_id, decision, note)
            if resolved is not None:
                _emit_changed({"action": "resolved", "item": dict(resolved)})
                return resolved
            raise KeyError(f"Bekleyen iş yok: {item_id}")
        record = self._read(path) or {}
        record["status"] = (
            STATUS_APPROVED if decision == DECISION_APPROVE else STATUS_REJECTED
        )
        record["decision"] = decision
        record["decided_at"] = _now()
        record["note"] = str(note or "")
        self._write(record)
        _emit_changed({"action": "resolved", "item": dict(record)})
        return record

    def expire(self, item_id: str, note: str = "") -> Optional[Dict[str, Any]]:
        """Süresi dolan isteği işaretler (silmez)."""
        path = self.path_for(item_id)
        record = self._read(path)
        if record is None:
            return None
        if record.get("status") != STATUS_PENDING:
            return record
        record["status"] = STATUS_EXPIRED
        record["decision"] = DECISION_REJECT
        record["decided_at"] = _now()
        record["note"] = str(note or "Onay zaman aşımına uğradı")
        self._write(record)
        _emit_changed({"action": "expired", "item": dict(record)})
        return record

    # --- okuma -------------------------------------------------------------

    def get(self, item_id: str) -> Optional[Dict[str, Any]]:
        record = self._read(self.path_for(item_id))
        if record is not None:
            return record
        for item in self._desk_items():
            if item.get("id") == item_id:
                return item
        return None

    def list(
        self, kind: Optional[str] = None, status: Optional[str] = STATUS_PENDING
    ) -> List[Dict[str, Any]]:
        """
        Künyeler (eskiden yeniye).

        Varsayılan `status="pending"`: arayüzün ve "onaylıyorum" çözümünün
        istediği şey BEKLEYEN işlerdir. Geçmişi (kararlar dâhil) görmek için
        `status=None` verilir.
        """
        items: List[Dict[str, Any]] = []
        if self.root.is_dir():
            for path in sorted(self.root.glob("*.json")):
                record = self._read(path)
                if record is not None:
                    items.append(record)
        items.extend(self._desk_items())
        if kind:
            items = [i for i in items if i.get("kind") == kind]
        if status:
            items = [i for i in items if i.get("status") == status]
        items.sort(key=lambda d: str(d.get("created_at") or ""))
        return items

    def wait(self, item_id: str, timeout_s: float) -> Optional[Dict[str, Any]]:
        """
        Karar verilene kadar BLOKLAR (dosya yoklaması).

        Döner: kararlı künye, ya da süre dolduysa `None` (kayıt `expired`
        olarak işaretlenir — çağıran `deny` döndürür).
        """
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while True:
            record = self._read(self.path_for(item_id))
            if record is not None and record.get("status") != STATUS_PENDING:
                return record
            if time.monotonic() >= deadline:
                self.expire(item_id)
                return None
            time.sleep(POLL_INTERVAL_S)

    # --- desk köprüsü ------------------------------------------------------

    def _desk_items(self) -> List[Dict[str, Any]]:
        """
        `desk_admin` kuyruğunu `kind="desk_change"` olarak SARMALAR.

        Dosya taşınmaz: Desk onayları kasadaki kendi klasöründe kalır
        (`Entropy/Desk/_pending`), burada yalnızca aynı şemaya çevrilir.
        """
        try:
            from entropy.agents import desk_admin

            records = desk_admin.list_pending() or []
        except Exception:
            logger.debug("Desk bekleyen istekleri okunamadı", exc_info=True)
            return []
        out: List[Dict[str, Any]] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            payload = dict(rec.get("payload") or {})
            out.append(
                {
                    "id": str(rec.get("id") or ""),
                    "kind": KIND_DESK_CHANGE,
                    "title": str(rec.get("summary") or "").strip(),
                    "detail": json.dumps(payload, ensure_ascii=False, indent=2),
                    "risk": "medium",
                    "created_at": str(rec.get("created_at") or ""),
                    "source": str(rec.get("source") or "desk"),
                    "payload": {"desk_kind": str(rec.get("kind") or ""), **payload},
                    "status": STATUS_PENDING,
                }
            )
        return out

    def _resolve_desk(
        self, item_id: str, decision: str, note: str
    ) -> Optional[Dict[str, Any]]:
        try:
            from entropy.agents import desk_admin

            record = desk_admin.get_pending(item_id)
            if not record:
                return None
            if decision == DECISION_APPROVE:
                desk_admin.apply_pending(item_id)
            else:
                desk_admin.reject_pending(item_id, note or "")
        except Exception:
            logger.warning("Desk onayı uygulanamadı: %s", item_id, exc_info=True)
            return None
        return {
            "id": item_id,
            "kind": KIND_DESK_CHANGE,
            "title": str(record.get("summary") or ""),
            "detail": "",
            "risk": "medium",
            "created_at": str(record.get("created_at") or ""),
            "source": str(record.get("source") or "desk"),
            "payload": dict(record.get("payload") or {}),
            "status": (
                STATUS_APPROVED if decision == DECISION_APPROVE else STATUS_REJECTED
            ),
            "decision": decision,
            "decided_at": _now(),
            "note": str(note or ""),
        }

    # --- disk --------------------------------------------------------------

    def _read(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            if not path.is_file():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # Yarım yazılmış dosya: yoklama döngüsü bir sonraki turda görür.
            return None
        if not isinstance(data, dict):
            return None
        data.setdefault("id", path.stem)
        data.setdefault("status", STATUS_PENDING)
        data.setdefault("payload", {})
        data.setdefault("risk", "low")
        return data

    def _write(self, record: Dict[str, Any]) -> None:
        """Atomik yazım: okuyan taraf yarım JSON görmemeli."""
        path = self.path_for(str(record.get("id") or ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".json.tmp{os.getpid()}")
        tmp.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, path)


def queue(root: Optional[Path | str] = None) -> PendingQueue:
    """Kısayol: varsayılan veri kökündeki kuyruk."""
    return PendingQueue(root)


# --- dış süreç yazımlarını duyurma -------------------------------------------


class PendingWatcher:
    """
    Kuyruk klasörünü yoklayıp `pending_changed` yayan küçük iş parçacığı.

    Neden gerekli: izin isteğini yazan taraf AYRI BİR SÜREÇTİR (MCP sunucusu,
    CLI'ın çocuğu). Onun `add()` çağrısı uygulamanın olay veriyoluna erişemez;
    dosya diske düşer ama uygulama içinde hiçbir sinyal doğmaz ve onay kartı
    ekranda belirmezdi. İzin isteği stream-json'da da görünmediği için (spike
    §4) tek haberci bu yoklamadır. Aralık 0,5 sn: CLI yanıt süresine üst sınır
    koymuyor, gecikme maliyeti yok.
    """

    def __init__(self, queue_obj: Optional[PendingQueue] = None, interval: float = 0.5):
        import threading

        self.queue = queue_obj or PendingQueue()
        self.interval = float(interval)
        self._seen: Dict[str, str] = {}
        self._stop = threading.Event()
        self._thread: Optional[Any] = None

    def scan_once(self) -> List[Dict[str, Any]]:
        """Değişenleri yayar ve yayılan olayları döndürür (test bunu sürer)."""
        events: List[Dict[str, Any]] = []
        for item in self.queue.list(status=None):
            item_id = str(item.get("id") or "")
            if not item_id or item.get("kind") != KIND_TOOL_PERMISSION:
                continue
            status = str(item.get("status") or STATUS_PENDING)
            if self._seen.get(item_id) == status:
                continue
            first = item_id not in self._seen
            self._seen[item_id] = status
            action = "added" if (first and status == STATUS_PENDING) else (
                "expired" if status == STATUS_EXPIRED else "resolved"
            )
            payload = {"action": action, "item": item}
            _emit_changed(payload)
            events.append(payload)
        return events

    def start(self) -> None:
        import threading

        if self._thread is not None:
            return
        # İlk tarama yalnızca durumu ÖĞRENİR: uygulama açılışında diskte duran
        # eski istekler yeniden "istendi" diye bağırmamalı.
        try:
            for item in self.queue.list(status=None):
                self._seen[str(item.get("id") or "")] = str(item.get("status") or "")
        except Exception:
            logger.debug("Kuyruk ilk taraması başarısız", exc_info=True)
        self._thread = threading.Thread(
            target=self._loop, name="pending-watcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_once()
            except Exception:
                logger.debug("Kuyruk yoklaması başarısız", exc_info=True)
            self._stop.wait(self.interval)


_watcher: Optional[PendingWatcher] = None


def start_watcher() -> PendingWatcher:
    """Süreç başına tek yoklayıcı (köprü onay yüzeyini kurarken çağırır)."""
    global _watcher
    if _watcher is None:
        _watcher = PendingWatcher()
        _watcher.start()
    return _watcher
