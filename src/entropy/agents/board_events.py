"""
Entropy Board olay günlüğü ve projeksiyonu (Faz 11-C.1).

Neden append-only günlük
------------------------
Bugüne kadar "ne oldu" değil yalnızca "sonuç ne" saklanıyordu: kart dosyasının
son hâli, SQLite defteri ve posta kutusu. Uygulama kapandığında olay dizisi
kayboluyordu; eşleşmeyen bir koşu başlangıcı ("çökmüş koşu") tespit edilemiyor,
asılı kalan kart sonsuza dek `running` görünüyordu.

Sözleşme üç maddede:

1. **Yalnızca ekleme.** Hiçbir satır düzenlenmez/silinmez. Düzenlemeye izin
   verilen an günlük "fazladan adımlarla bir durum alanına" dönüşür.
2. **`TASKBOARD.md` türetilmiştir.** Elle yazılmaz; her olaydan sonra yeniden
   üretilir. Kart dosyaları da bir görünümdür — tek denetim kaynağı günlüktür.
3. **Projeksiyon deterministiktir.** Aynı günlükten iki kez üretilen görünümün
   `projection_hash`i (kanonik JSON + SHA-256) aynı olmak zorundadır; sapma
   varsa bir yerde günlük dışı bir yazma olmuş demektir.

Satır şeması (ESAA v0.3.0 alanlarıyla hizalı):

    {"schema_version":"1.0","seq":1284,"ts":"...","correlation_id":"...",
     "task_id":"...","attempt_id":1,"actor":"arastirmaci","action":"run.started",
     "idempotency_key":"card-<id>-a1-run.started","payload":{...}}
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from entropy.core import paths as _paths
from entropy.agents import board_fsm

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"

# Günlük dosyası aylık döndürülür. GÜNLÜK döndürme bilinçli olarak seçilmedi:
# projeksiyonun 30 dosya açması gerekirdi.
ROTATE_BYTES = 4 * 1024 * 1024

# Projeksiyonda kart başına taşınan alanlar. Karma bu kümeye göre hesaplandığı
# için liste SÖZLEŞMEDİR: alan eklemek eski karmaları geçersiz kılar.
PROJECTED_FIELDS = (
    "status", "agent", "title", "provider", "model", "effort", "priority",
    "attempt", "claimed_by", "checkpoint", "proof", "report_path", "office",
)

_TASKBOARD_HEADER = "<!-- TÜRETİLMİŞ DOSYA — elle düzenlemeyin; kaynak: events.jsonl -->"


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


class BoardEventLog:
    """
    `Entropy/Board/events.jsonl` yazıcısı + projeksiyon üreticisi.

    Süreç içi tek `threading.Lock` altında yazar (`TaskBoard._bridge_lock`
    deseninin aynısı) ve her satırı ayrı `open(..., "a")` ile ekler: uzun süre
    açık tutulan bir tanıtıcı, uygulama çökerse yarım satır bırakıyordu.
    """

    def __init__(self, vault_path: Optional[Path | str] = None):
        self.vault_path = Path(vault_path) if vault_path is not None else None
        self._lock = threading.RLock()
        self._seq: Optional[int] = None
        self._keys: Optional[set] = None

    # -- yollar --------------------------------------------------------

    @property
    def path(self) -> Path:
        return _paths.board_events_path(self.vault_path)

    @property
    def archive_dir(self) -> Path:
        return _paths.board_events_archive_dir(self.vault_path)

    @property
    def projection_path(self) -> Path:
        return _paths.board_projection_path(self.vault_path)

    @property
    def taskboard_path(self) -> Path:
        return _paths.board_taskboard_path(self.vault_path)

    # -- okuma ---------------------------------------------------------

    def read(self, include_archive: bool = True) -> List[dict]:
        """Günlükteki olaylar, `seq` sırasıyla."""
        files: List[Path] = []
        if include_archive and self.archive_dir.is_dir():
            files.extend(sorted(p for p in self.archive_dir.glob("*.jsonl")))
        files.append(self.path)
        events: List[dict] = []
        for f in files:
            try:
                raw = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    # Yarım satır atlanır ama SİLİNMEZ: günlük değiştirilemez.
                    logger.warning("Pano günlüğünde bozuk satır atlandı: %s", f)
                    continue
                if isinstance(obj, dict):
                    events.append(obj)
        events.sort(key=lambda e: int(e.get("seq") or 0))
        return events

    def _load_state(self) -> None:
        if self._seq is not None and self._keys is not None:
            return
        events = self.read()
        self._seq = max((int(e.get("seq") or 0) for e in events), default=0)
        self._keys = {str(e.get("idempotency_key") or "") for e in events}
        self._keys.discard("")

    def last_seq(self) -> int:
        with self._lock:
            self._load_state()
            return int(self._seq or 0)

    # -- yazma ---------------------------------------------------------

    def append(
        self,
        action: str,
        task_id: str,
        actor: str = "",
        payload: Optional[dict] = None,
        attempt_id: int = 1,
        correlation_id: str = "",
        idempotency_key: str = "",
    ) -> Optional[dict]:
        """
        Olayı günlüğe ekler; aynı `idempotency_key` ikinci kez yazılmaz.

        Dönüş: yazılan olay (yeniden giriş yüzünden atlandıysa None).
        Yeniden giriş gerçek bir sorun: köprünün sonuç geri çağrısı bazen
        SENKRON geliyor ve `run.finished` iki kez yazılabiliyordu (bugün
        `harness._starting` seti bunu yalnızca bellekte çözüyor).
        """
        action = str(action or "").strip()
        if action not in board_fsm.EVENTS:
            raise ValueError(f"Bilinmeyen pano olayı: {action!r}")
        task_id = str(task_id or "").strip()
        key = idempotency_key or f"{task_id}-a{int(attempt_id or 1)}-{action}"
        with self._lock:
            self._load_state()
            if key in (self._keys if self._keys is not None else set()):
                return None
            self._rotate_if_needed()
            seq = int(self._seq or 0) + 1
            event = {
                "schema_version": SCHEMA_VERSION,
                "seq": seq,
                "ts": _now(),
                "correlation_id": correlation_id or task_id,
                "task_id": task_id,
                "attempt_id": int(attempt_id or 1),
                "actor": str(actor or ""),
                "action": action,
                "idempotency_key": key,
                "payload": _jsonable(payload or {}),
            }
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event, ensure_ascii=False) + "\n")
            except OSError:
                logger.warning("Pano olayı yazılamadı: %s", self.path)
                return None
            self._seq = seq
            # DİKKAT: `(self._keys or set())` YAZILMAZ — boş küme YANLIŞ değerdir
            # ve anahtar geçici bir kümeye düşerdi (yeniden giriş koruması
            # sessizce çalışmazdı).
            if self._keys is None:
                self._keys = set()
            self._keys.add(key)
        return event

    def _rotate_if_needed(self) -> None:
        try:
            if not self.path.is_file() or self.path.stat().st_size < ROTATE_BYTES:
                return
            stamp = datetime.datetime.now().strftime("%Y-%m")
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            target = self.archive_dir / f"{stamp}.jsonl"
            if target.exists():
                # Aynı ay içinde ikinci döndürme: arşive EKLENİR, üzerine yazılmaz.
                with open(target, "a", encoding="utf-8") as dst, \
                        open(self.path, "r", encoding="utf-8") as src:
                    dst.write(src.read())
                self.path.write_text("", encoding="utf-8")
            else:
                os.replace(self.path, target)
        except OSError:
            logger.warning("Pano günlüğü döndürülemedi: %s", self.path)

    # -- projeksiyon ---------------------------------------------------

    def project(self, events: Optional[Iterable[dict]] = None) -> dict:
        """
        Günlüğü baştan oynatıp kart görünümünü üretir.

        Durum, olayların kendisinden değil FSM'den türetilir: `resolve_target`
        aynı tabloyu kullandığı için projeksiyon ile kart dosyası ayrışamaz.
        Geçersiz bir olay dizisi (elle bozulmuş günlük) kartı OLDUĞU YERDE
        bırakır ve `rejected` sayacına düşer — oynatma çökmez.
        """
        evs = list(events) if events is not None else self.read()
        cards: Dict[str, dict] = {}
        rejected = 0
        last_seq = 0
        for ev in evs:
            last_seq = max(last_seq, int(ev.get("seq") or 0))
            task_id = str(ev.get("task_id") or "")
            if not task_id:
                continue
            action = str(ev.get("action") or "")
            payload = dict(ev.get("payload") or {})
            payload.setdefault("actor", ev.get("actor") or "")
            card = cards.get(task_id)
            if card is None:
                card = {"id": task_id, "status": "backlog", "agent": "",
                        "title": "", "attempt": 0}
                if action != "task.created":
                    # Günlük ortasından başlayan kart (arşiv budandı): kartı
                    # yoktan var etmek yerine mevcut durumdan devam edilir.
                    card["status"] = str(payload.get("status") or "backlog")
                cards[task_id] = card
            for field in PROJECTED_FIELDS:
                if field in payload and field not in ("status",):
                    card[field] = payload[field]
            if "title" in payload:
                card["title"] = payload["title"]
            if action == "task.created":
                card["status"] = "backlog"
                card["event_seq"] = int(ev.get("seq") or 0)
                continue
            if action == "task.reset":
                card["status"] = "assigned" if card.get("agent") else "backlog"
                card["event_seq"] = int(ev.get("seq") or 0)
                continue
            try:
                card.update(board_fsm.transition(card, action, payload))
            except board_fsm.InvalidTransition:
                rejected += 1
                continue
            card["event_seq"] = int(ev.get("seq") or 0)

        view = {
            "schema_version": SCHEMA_VERSION,
            "last_seq": last_seq,
            "rejected": rejected,
            "cards": {
                cid: {k: c.get(k) for k in ("id", *PROJECTED_FIELDS) if k in c or k == "id"}
                for cid, c in sorted(cards.items())
            },
        }
        view["projection_hash"] = projection_hash(view)
        return view

    def write_projection(self, view: Optional[dict] = None) -> dict:
        """Projeksiyonu `projection.json`a ve `TASKBOARD.md`ye yazar."""
        view = view if view is not None else self.project()
        try:
            self.projection_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.projection_path.with_suffix(f".json.tmp{os.getpid()}")
            tmp.write_text(json.dumps(view, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.projection_path)
        except OSError:
            logger.warning("Pano projeksiyonu yazılamadı: %s", self.projection_path)
        self.render_taskboard(view)
        return view

    def render_taskboard(self, view: Optional[dict] = None,
                         cards: Optional[List[dict]] = None) -> str:
        """
        `TASKBOARD.md`yi yeniden üretir ve döndürür.

        `office_workspace.render_board` ile aynı desen (durum başlıkları +
        madde satırları) ama AYRI üretici: ofis panosu Desk'e, bu pano
        Entropy'ye bakar ve iki tarafın sütunları birbirini sürüklemesin.
        """
        view = view if view is not None else self.project()
        rows = cards if cards is not None else list((view.get("cards") or {}).values())
        text = render_taskboard_text(rows, last_seq=int(view.get("last_seq") or 0),
                                     projection_hash=str(view.get("projection_hash") or ""))
        try:
            self.taskboard_path.parent.mkdir(parents=True, exist_ok=True)
            self.taskboard_path.write_text(text, encoding="utf-8")
        except OSError:
            logger.warning("TASKBOARD.md yazılamadı: %s", self.taskboard_path)
        return text


def render_taskboard_text(cards: Iterable[dict], last_seq: int = 0,
                          projection_hash: str = "") -> str:
    """Kart görünümünden insan panosunu üretir (saf fonksiyon; test edilebilir)."""
    by_status: Dict[str, List[dict]] = {s: [] for s in board_fsm.STATUSES}
    for card in cards:
        status = str((card or {}).get("status") or "backlog")
        by_status.setdefault(status, []).append(dict(card or {}))
    lines: List[str] = [
        _TASKBOARD_HEADER,
        "",
        "# Entropy Görev Panosu",
        "",
        f"Son olay: `{last_seq}` · Projeksiyon karması: `{projection_hash[:16]}`",
        "",
    ]
    for status in board_fsm.STATUSES:
        rows = by_status.get(status) or []
        lines.append(f"## {status} ({len(rows)})")
        if not rows:
            lines.append("")
            continue
        for card in sorted(rows, key=lambda c: str(c.get("id") or "")):
            title = str(card.get("title") or card.get("id") or "").strip()
            agent = str(card.get("agent") or "").strip()
            effort = str(card.get("effort") or "").strip()
            priority = str(card.get("priority") or "").strip()
            bits = [b for b in (agent, priority, effort) if b]
            suffix = f" — {' · '.join(bits)}" if bits else ""
            # Rapor bağlantısı (Faz 11 kapanışı): kartın `report_path`i doluysa
            # panodan doğrudan rapora gidilir. Obsidian bağlantısı değil düz
            # Markdown bağlantısı: pano kasa dışından da okunuyor.
            report = str(card.get("report_path") or "").strip()
            link = f" · [rapor]({report.replace(chr(92), '/')})" if report else ""
            lines.append(f"- `{card.get('id')}` {title}{suffix}{link}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def canonical_json(data) -> str:
    """Karma için kanonik biçim: sıralı anahtar, ayraçsız boşluk, UTF-8."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def projection_hash(view: dict) -> str:
    """Projeksiyonun SHA-256'sı; `projection_hash` alanının kendisi hariç."""
    payload = {k: v for k, v in (view or {}).items() if k != "projection_hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _jsonable(value):
    """Yükü JSON'a çevrilebilir hâle getirir (Path, set, dataclass alanları)."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def unmatched_runs(events: Optional[Iterable[dict]] = None,
                   vault_path: Optional[Path | str] = None) -> List[str]:
    """
    Eşleşmeyen `run.started` olan kart kimlikleri = ÇÖKMÜŞ KOŞULAR.

    Uzlaştırıcının aradığı imza budur: koşu başladı, `run.finished` /
    `task.canceled` hiç gelmedi. Uygulama kapanırken kart dosyası `running`
    kalıyordu ve bunu düzelten hiçbir şey yoktu (rapor G6).
    """
    evs = list(events) if events is not None else BoardEventLog(vault_path).read()
    open_runs: Dict[str, int] = {}
    for ev in evs:
        task_id = str(ev.get("task_id") or "")
        action = str(ev.get("action") or "")
        if action == "run.started":
            open_runs[task_id] = int(ev.get("seq") or 0)
        elif action in ("run.finished", "task.canceled", "claim.expired",
                        "lock.timeout", "task.reset"):
            open_runs.pop(task_id, None)
    return sorted(open_runs)


_default_log: Optional[BoardEventLog] = None
_default_lock = threading.Lock()


def board_event_log(vault_path: Optional[Path | str] = None) -> BoardEventLog:
    """
    Varsayılan günlük. `vault_path` verilirse HER ZAMAN yeni örnek döner:
    testler yalıtılmış kasada koşuyor ve önbellek sızdırırsa fikstürler
    birbirine karışır (`tests/conftest.py::isolate_obsidian_vault`).
    """
    global _default_log
    if vault_path is not None:
        return BoardEventLog(vault_path)
    with _default_lock:
        if _default_log is None:
            _default_log = BoardEventLog()
        return _default_log


def reset_default_log() -> None:
    """Test yalıtımı: süreç içi varsayılan günlüğü düşürür."""
    global _default_log
    with _default_lock:
        _default_log = None


__all__ = [
    "SCHEMA_VERSION", "PROJECTED_FIELDS", "BoardEventLog", "board_event_log",
    "reset_default_log", "render_taskboard_text", "canonical_json",
    "projection_hash", "unmatched_runs",
]
