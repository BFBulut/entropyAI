"""
Posta kutusu: Entropy AI, ofisler ve ajanlar arasında dosya tabanlı mesajlaşma.

Neden dosya: koordinasyon konuşmanın içinde tutulunca uygulama kapanınca
kayboluyordu (harness'ın kart dosyalarıyla çözdüğü sorunun aynısı). Posta kutusu
kasada durur; Entropy, Obsidian ve harici CLI'lar aynı kutuyu görebilir.

Şema A2A'ya (Agent2Agent, v1.0 Ocak 2026) BİLEREK benzetildi: ileride yerel bir
A2A sunucusuna geçilirse taşıyıcı değişir, mesaj gövdesi aynı kalır.

    {
      "id": "...", "task_id": "...", "from": "entropy", "to": "arastirma-ofisi",
      "role": "user|agent", "kind": "instruction|report|question|status",
      "parts": [{"type": "text|file|json", "content": ...}],
      "status": "submitted|working|input_required|completed|failed|canceled",
      "created_at": "...", "terminal": false, "read": false, "acked": false
    }

Dosya düzeni:
    <kasa>/Entropy/Offices/<ofis>/inbox/<ts>-<id>.json
    <kasa>/Entropy/Agents/<ad>/inbox/<ts>-<id>.json
    <kasa>/Entropy/Inbox/<ts>-<id>.json          (Entropy'nin kendi kutusu)

Yazım atomiktir (tmp + os.replace): kutuyu aynı anda bir izleyici okurken bir
harness yazıyor; doğrudan write_text yarım JSON gösteriyordu.

TERMİNAL SÖZLEŞMESİ: her görev/kart yaşam döngüsü SONUNDA `kind="status"` ve
`terminal=True` bir mesaj yayılır (completed/failed/canceled). A2A'nın "her görev
terminal olay yayımlamalı" kuralı; onsuz asılı kalmış bir kartla bitmiş bir kart
dışarıdan ayırt edilemiyordu.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

INBOX_DIRNAME = "inbox"
ENTROPY_INBOX_SUBDIR = "Entropy/Inbox"
OFFICES_SUBDIR = "Entropy/Offices"
AGENTS_SUBDIR = "Entropy/Agents"

OWNER_KINDS = ("office", "agent", "entropy")

MESSAGE_KINDS = ("instruction", "report", "question", "status")

# A2A görev durumları. "auth_required"/"rejected" bilerek dışarıda: Entropy'de
# karşılığı olan bir yol yok ve şemaya yazılınca doğrulama gevşerdi.
MESSAGE_STATUSES = (
    "submitted",
    "working",
    "input_required",
    "completed",
    "failed",
    "canceled",
)

# Terminal sayılan durumlar; `terminal=True` yalnızca bunlarla anlamlıdır.
TERMINAL_STATUSES = ("completed", "failed", "canceled")

# Entropy'nin kendi posta kutusunun sahip adı (tek kutu olduğu için sabit).
ENTROPY_OWNER = "entropy"

# Planlama prompt'una enjekte edilen talimat bölümünün üst sınırı (karakter).
# Posta kutusu sınırsız büyüyebilir; plan çağrısının bütçesi büyüyemez.
INSTRUCTION_CHAR_BUDGET = 2000


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def new_message_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Message:
    """Tek bir posta kutusu mesajı (A2A benzeri gövde)."""

    id: str = field(default_factory=new_message_id)
    task_id: str = ""
    from_: str = ""
    to: str = ""
    role: str = "user"
    kind: str = "instruction"
    parts: List[Dict[str, object]] = field(default_factory=list)
    status: str = "submitted"
    created_at: str = field(default_factory=_now)
    terminal: bool = False
    read: bool = False
    acked: bool = False
    path: Optional[Path] = None

    # -- metin yardımcıları ---------------------------------------------

    @property
    def text(self) -> str:
        """Tüm `text` parçalarının birleşimi (okuma yollarının %90'ı bu)."""
        out = []
        for part in self.parts or []:
            if isinstance(part, dict) and part.get("type") == "text":
                out.append(str(part.get("content") or ""))
        return "\n".join(o for o in out if o).strip()

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data.pop("path", None)
        # Disk şemasında alan adı `from`; Python'da `from` ayrılmış sözcük
        # olduğu için bellek içi ad `from_`. Dönüşüm tek yerde.
        data["from"] = data.pop("from_", "")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, object], path: Optional[Path] = None) -> "Message":
        parts = data.get("parts") or []
        if isinstance(parts, str):
            parts = [{"type": "text", "content": parts}]
        if not isinstance(parts, list):
            parts = []
        kind = str(data.get("kind") or "instruction")
        status = str(data.get("status") or "submitted")
        return cls(
            id=str(data.get("id") or new_message_id()),
            task_id=str(data.get("task_id") or ""),
            from_=str(data.get("from") or data.get("from_") or ""),
            to=str(data.get("to") or ""),
            role=str(data.get("role") or "user"),
            kind=kind if kind in MESSAGE_KINDS else "instruction",
            parts=[p for p in parts if isinstance(p, dict)],
            status=status if status in MESSAGE_STATUSES else "submitted",
            created_at=str(data.get("created_at") or _now()),
            terminal=bool(data.get("terminal")),
            read=bool(data.get("read")),
            acked=bool(data.get("acked")),
            path=path,
        )


def text_part(content: str) -> Dict[str, object]:
    return {"type": "text", "content": str(content or "")}


def json_part(content) -> Dict[str, object]:
    return {"type": "json", "content": content}


def file_part(path) -> Dict[str, object]:
    return {"type": "file", "content": str(path)}


class MailboxScopeError(PermissionError):
    """Ajanlar arası mesaj ofis sınırını aştı."""


class Mailbox:
    """
    Tek bir sahibin (ofis / ajan / Entropy) posta kutusu.

    Durum tutmaz: her okuma diski görür. Kutuyu Entropy, harness ve kullanıcı
    birlikte yazdığı için bellek içi önbellek hızla bayatlardı — kayıt
    defterleriyle (AgentRegistry, OfficeRegistry) aynı ilke.
    """

    def __init__(
        self,
        owner_kind: str,
        owner_name: str = "",
        vault_path: Optional[Path | str] = None,
    ):
        kind = (owner_kind or "").strip().lower()
        if kind not in OWNER_KINDS:
            raise ValueError(f"Bilinmeyen posta kutusu sahibi türü: {owner_kind!r}")
        if kind != "entropy" and not (owner_name or "").strip():
            raise ValueError("Ofis/ajan posta kutusu için sahip adı zorunlu.")
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        self.owner_kind = kind
        self.owner_name = (owner_name or ENTROPY_OWNER).strip() if kind != "entropy" else ENTROPY_OWNER
        self.vault_path = Path(vault_path)

    # -- yollar ----------------------------------------------------------

    @property
    def inbox_dir(self) -> Path:
        if self.owner_kind == "entropy":
            return self.vault_path / ENTROPY_INBOX_SUBDIR
        if self.owner_kind == "office":
            return self.vault_path / OFFICES_SUBDIR / self.owner_name / INBOX_DIRNAME
        return self.vault_path / AGENTS_SUBDIR / self.owner_name / INBOX_DIRNAME

    # -- yazma -----------------------------------------------------------

    def send(
        self,
        message: Optional[Message] = None,
        *,
        sender_office: Optional[str] = None,
        **fields,
    ) -> Message:
        """
        Bu kutuya mesaj bırakır ve `bus.mailbox_updated` yayar.

        `sender_office`: gönderen bir AJAN ise onun ofisi. Kapsam kuralı burada
        uygulanır — eş-eş (ajan → ajan) mesaj yalnızca AYNI ofis içinde geçerli.
        Ofis dışına yazma denemesi sessizce yutulmaz, `MailboxScopeError` olur;
        sessiz yutma "mesajım gitti" sanılan bir sızıntı riski demekti.
        """
        if message is None:
            message = Message(**fields)
        self._check_scope(message, sender_office)
        self._validate(message)

        target = self.inbox_dir
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(f"Posta kutusu dizini açılamadı: {target}") from exc

        stamp = (message.created_at or _now()).replace(":", "").replace("-", "").replace("T", "-")
        path = target / f"{stamp}-{message.id}.json"
        _atomic_write_json(path, message.to_dict())
        message.path = path
        _notify(self.owner_kind, self.owner_name)
        return message

    def _check_scope(self, message: Message, sender_office: Optional[str]) -> None:
        """Ajanlar arası doğrudan mesaj yalnızca aynı ofis içinde."""
        if self.owner_kind != "agent":
            return
        sender = (message.from_ or "").strip()
        if not sender or sender in (ENTROPY_OWNER, ""):
            return
        # Gönderen bir ofis ya da Entropy ise serbest; ajan ise ofis eşleşmeli.
        try:
            from entropy.agents.offices import OfficeRegistry

            offices = OfficeRegistry(vault_path=self.vault_path)
            if offices.get(sender) is not None:
                return
            own_office = None
            for spec in offices.list():
                if self.owner_name in spec.roster():
                    own_office = spec.name
                    break
            sender_home = (sender_office or "").strip() or None
            if sender_home is None:
                for spec in offices.list():
                    if sender in spec.roster():
                        sender_home = spec.name
                        break
        except Exception:
            return
        if own_office is None or sender_home is None or own_office != sender_home:
            raise MailboxScopeError(
                f"'{sender}' ajanı '{self.owner_name}' ajanına yazamaz: "
                f"eş-eş mesaj yalnızca aynı ofis içinde geçerli "
                f"(gönderen ofisi: {sender_home or '-'}, alıcı ofisi: {own_office or '-'})."
            )

    @staticmethod
    def _validate(message: Message) -> None:
        if message.kind not in MESSAGE_KINDS:
            raise ValueError(f"Geçersiz mesaj türü: {message.kind!r}")
        if message.status not in MESSAGE_STATUSES:
            raise ValueError(f"Geçersiz mesaj durumu: {message.status!r}")
        if message.terminal and message.status not in TERMINAL_STATUSES:
            raise ValueError(
                f"terminal=True yalnızca {TERMINAL_STATUSES} durumlarıyla olur; "
                f"gelen: {message.status!r}"
            )

    # -- okuma -----------------------------------------------------------

    def list(self, unread: bool = False, kind: Optional[str] = None,
             task_id: Optional[str] = None) -> List[Message]:
        """Kutudaki mesajlar (dosya adına göre eskiden yeniye)."""
        out: List[Message] = []
        try:
            if not self.inbox_dir.is_dir():
                return out
            children = sorted(self.inbox_dir.glob("*.json"))
        except OSError:
            return out
        for path in children:
            msg = self._read(path)
            if msg is None:
                continue
            if unread and msg.read:
                continue
            if kind and msg.kind != kind:
                continue
            if task_id and msg.task_id != task_id:
                continue
            out.append(msg)
        return out

    def get(self, message_id: str) -> Optional[Message]:
        for msg in self.list():
            if msg.id == message_id:
                return msg
        return None

    @staticmethod
    def _read(path: Path) -> Optional[Message]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Yarım yazılmış ya da bozuk dosya kutuyu tamamen okunamaz
            # yapmamalı; tek mesaj atlanır.
            return None
        if not isinstance(data, dict):
            return None
        return Message.from_dict(data, path=path)

    def unread_count(self) -> int:
        return len(self.list(unread=True))

    # -- işaretleme -------------------------------------------------------

    def mark_read(self, message_id: str) -> bool:
        """Okundu işaretler (mesaj kutuda kalır; silme yok)."""
        return self._patch(message_id, {"read": True})

    def ack(self, message_id: str, status: Optional[str] = None) -> bool:
        """
        Alındı + işlendi onayı. `status` verilirse mesajın durumu da güncellenir.

        Silme yerine `acked` bayrağı: gönderen tarafın "işlendi mi" sorusunu
        yanıtlayabilmesi için mesajın kendisi arşivde kalmalı.
        """
        fields: Dict[str, object] = {"acked": True, "read": True}
        if status:
            if status not in MESSAGE_STATUSES:
                raise ValueError(f"Geçersiz mesaj durumu: {status!r}")
            fields["status"] = status
        return self._patch(message_id, fields)

    def _patch(self, message_id: str, fields: Dict[str, object]) -> bool:
        msg = self.get(message_id)
        if msg is None or msg.path is None:
            return False
        data = msg.to_dict()
        data.update(fields)
        _atomic_write_json(msg.path, data)
        _notify(self.owner_kind, self.owner_name)
        return True


def _atomic_write_json(path: Path, data: Dict[str, object]) -> None:
    """tmp + os.replace: yarım JSON okuyan izleyici olmasın."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}-{threading.get_ident()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _notify(owner_kind: str, owner_name: str) -> None:
    try:
        from entropy.core.event_bus import bus

        bus.mailbox_updated.emit(owner_kind, owner_name)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Kısa yollar
# ---------------------------------------------------------------------------


def office_mailbox(name: str, vault_path=None) -> Mailbox:
    return Mailbox("office", name, vault_path=vault_path)


def agent_mailbox(name: str, vault_path=None) -> Mailbox:
    return Mailbox("agent", name, vault_path=vault_path)


def entropy_mailbox(vault_path=None) -> Mailbox:
    return Mailbox("entropy", vault_path=vault_path)


def ask_office(office: str, question: str, task_id: str = "", vault_path=None) -> Message:
    """`/ask <ofis> <soru>`: ofis kutusuna `question` bırakır."""
    return office_mailbox(office, vault_path=vault_path).send(
        Message(
            task_id=task_id,
            from_=ENTROPY_OWNER,
            to=office,
            role="user",
            kind="question",
            parts=[text_part(question)],
            status="submitted",
        )
    )


def instruct_office(office: str, instruction: str, task_id: str = "", vault_path=None) -> Message:
    """Entropy'nin ofise talimatı; harness planlamadan önce okur."""
    return office_mailbox(office, vault_path=vault_path).send(
        Message(
            task_id=task_id,
            from_=ENTROPY_OWNER,
            to=office,
            role="user",
            kind="instruction",
            parts=[text_part(instruction)],
            status="submitted",
        )
    )


def report_to_entropy(
    sender: str,
    title: str,
    body: str,
    task_id: str = "",
    output_paths: Optional[Iterable[str]] = None,
    vault_path=None,
) -> Message:
    """
    Kart/kart zinciri bitince Entropy'nin gelen kutusuna rapor düşürür.

    `bus.report_inbox_unread` de burada yayılır: Rapor Merkezi rozetinin
    kaynağı tek olsun diye (arayüz yalnızca dinler, saymaz).
    """
    parts: List[Dict[str, object]] = [text_part(body)]
    for p in output_paths or []:
        parts.append(file_part(p))
    box = entropy_mailbox(vault_path=vault_path)
    msg = box.send(
        Message(
            task_id=task_id,
            from_=sender,
            to=ENTROPY_OWNER,
            role="agent",
            kind="report",
            parts=parts,
            status="completed",
        )
    )
    try:
        from entropy.core.event_bus import bus

        bus.report_inbox_unread.emit(box.unread_count())
    except Exception:
        pass
    return msg


def emit_terminal(
    task_id: str,
    sender: str,
    status: str,
    summary: str = "",
    to: str = ENTROPY_OWNER,
    vault_path=None,
) -> Optional[Message]:
    """
    TERMİNAL SÖZLEŞMESİ: bir görevin son olayı.

    Hiçbir yol terminal olay yaymadan bitmemeli — bu yüzden çağrı korumalı ve
    hata yutulur (posta kutusu yazılamıyorsa kartın kapanması engellenmemeli),
    ama çağrının kendisi harness/TaskBoard'ın her çıkış yolunda vardır.
    """
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"Terminal durum {TERMINAL_STATUSES} olmalı; gelen: {status!r}")
    try:
        return entropy_mailbox(vault_path=vault_path).send(
            Message(
                task_id=task_id,
                from_=sender,
                to=to,
                role="agent",
                kind="status",
                parts=[text_part(summary or f"Görev {status}.")],
                status=status,
                terminal=True,
            )
        )
    except Exception:
        logger.warning("Terminal olay yazılamadı: %s / %s", task_id, status)
        return None


def has_terminal_event(task_id: str, vault_path=None) -> bool:
    """Bu görev için terminal olay yayıldı mı (test ve pano için)."""
    return any(
        m.terminal for m in entropy_mailbox(vault_path=vault_path).list(task_id=task_id, kind="status")
    )


def pending_instructions(office: str, vault_path=None, mark: bool = True) -> List[Message]:
    """
    Ofisin okunmamış talimat/soru mesajları; okundu işaretlenir.

    Harness planlamadan ÖNCE çağırır: kullanıcının `/ask` ile bıraktığı yön
    plan çağrısına girmezse posta kutusu yalnızca bir arşiv olurdu.
    """
    box = office_mailbox(office, vault_path=vault_path)
    msgs = [m for m in box.list(unread=True) if m.kind in ("instruction", "question")]
    if mark:
        for m in msgs:
            box.mark_read(m.id)
    return msgs


def instructions_section(messages: Iterable[Message]) -> str:
    """Planlama prompt'una eklenen "[POSTA KUTUSU]" bölümü (bütçeli)."""
    rows: List[str] = []
    total = 0
    for msg in messages:
        text = " ".join((msg.text or "").split())
        if not text:
            continue
        label = "SORU" if msg.kind == "question" else "TALİMAT"
        row = f"- [{label}] {msg.from_ or '?'}: {text}"
        if total + len(row) > INSTRUCTION_CHAR_BUDGET:
            rows.append("- … (kalan mesajlar posta kutusunda)")
            break
        rows.append(row)
        total += len(row)
    if not rows:
        return ""
    return "[POSTA KUTUSU — kullanıcıdan gelen yön]\n" + "\n".join(rows)


# ---------------------------------------------------------------------------
# Ofis durum panosu
# ---------------------------------------------------------------------------


def office_status(office: str, vault_path=None) -> Dict[str, object]:
    """
    Salt-okunur ofis panosu: çalışan görevler, harcama, son terminal olaylar.

    `/desk` ve Agent Desk AYNI veriyi okusun diye tek üretici burasıdır; iki
    yerde ayrı hesaplanınca panolar birbirini tutmuyordu.
    """
    from entropy.agents.harness import OfficeHarness
    from entropy.agents.offices import OfficeRegistry
    from entropy.agents.tasks import TaskBoard

    offices = OfficeRegistry(vault_path=vault_path) if vault_path else OfficeRegistry()
    spec = offices.get(office)
    board = TaskBoard(vault_path=offices.vault_path)
    harness = OfficeHarness(office, board=board, offices=offices)

    running: List[Dict[str, object]] = []
    spent_total = 0
    try:
        cards = board.list()
    except Exception:
        cards = []
    for card in cards:
        if card.office != office or card.parent:
            continue
        state = harness._card_state(card.id)
        spent = int(state.get("tokens", 0) or 0)
        spent_total += spent
        if card.status in ("running", "review"):
            running.append({
                "id": card.id,
                "title": card.title,
                "status": card.status,
                "phase": str(state.get("phase") or ""),
                "tokens": spent,
                "budget": int(card.budget_tokens or (spec.budget_tokens if spec else 0) or 0),
                "children": len(card.children or []),
            })

    inbox = office_mailbox(office, vault_path=offices.vault_path)
    terminals = [
        {
            "task_id": m.task_id,
            "status": m.status,
            "from": m.from_,
            "at": m.created_at,
            "text": m.text[:300],
        }
        for m in entropy_mailbox(vault_path=offices.vault_path).list(kind="status")
        if m.terminal and (not m.task_id or any(c.id == m.task_id for c in cards))
    ][-10:]

    return {
        "office": office,
        "exists": spec is not None,
        "purpose": spec.purpose if spec else "",
        "orchestrator": spec.orchestrator if spec else "",
        "evaluator": spec.evaluator if spec else "",
        "members": list(spec.members) if spec else [],
        "max_parallel": int(spec.max_parallel) if spec else 0,
        "budget_tokens": int(spec.budget_tokens) if spec else 0,
        "running": running,
        "spent_tokens": spent_total,
        "inbox_unread": inbox.unread_count(),
        "recent_terminal": terminals,
    }


# ---------------------------------------------------------------------------
# İzleyici
# ---------------------------------------------------------------------------


class MailboxWatcher:
    """
    Posta kutularını izler ve değişimde `bus.mailbox_updated` yayar.

    İki katman: QFileSystemWatcher (varsa, anında) VE yoklama (varsayılan 5 sn).
    Yoklama şart — QFileSystemWatcher ağ/senkron klasörlerde (Obsidian kasası
    sıklıkla OneDrive/Drive altında) olayları kaçırıyor ve kutu sessizce
    bayatlıyordu.
    """

    def __init__(self, vault_path: Optional[Path | str] = None, poll_seconds: float = 5.0):
        if vault_path is None:
            from entropy.core.config import config

            vault_path = config.obsidian_vault_path
        self.vault_path = Path(vault_path)
        self.poll_seconds = float(poll_seconds)
        self._seen: Dict[str, float] = {}
        self._timer = None
        self._watcher = None
        self._stopped = False

    def inbox_dirs(self) -> List[Path]:
        dirs = [self.vault_path / ENTROPY_INBOX_SUBDIR]
        for base, _ in ((self.vault_path / OFFICES_SUBDIR, "office"),
                        (self.vault_path / AGENTS_SUBDIR, "agent")):
            try:
                if base.is_dir():
                    for child in sorted(base.iterdir()):
                        if child.is_dir():
                            dirs.append(child / INBOX_DIRNAME)
            except OSError:
                continue
        return dirs

    def _owner_of(self, inbox: Path) -> tuple:
        try:
            rel = inbox.relative_to(self.vault_path).as_posix()
        except ValueError:
            return ("entropy", ENTROPY_OWNER)
        if rel == ENTROPY_INBOX_SUBDIR:
            return ("entropy", ENTROPY_OWNER)
        parts = rel.split("/")
        if len(parts) >= 3 and parts[1] == "Offices":
            return ("office", parts[2])
        if len(parts) >= 3 and parts[1] == "Agents":
            return ("agent", parts[2])
        return ("entropy", ENTROPY_OWNER)

    def scan(self) -> List[tuple]:
        """Değişen kutuları bulur, sinyal yayar ve (tür, ad) listesini döndürür."""
        changed: List[tuple] = []
        for inbox in self.inbox_dirs():
            try:
                if not inbox.is_dir():
                    continue
                stamp = max(
                    [inbox.stat().st_mtime]
                    + [p.stat().st_mtime for p in inbox.glob("*.json")]
                )
            except (OSError, ValueError):
                continue
            key = str(inbox)
            if self._seen.get(key) == stamp:
                continue
            first = key not in self._seen
            self._seen[key] = stamp
            if first:
                # İlk tarama mevcut durumu kaydeder; her açılışta "yeni mesaj"
                # yaymak bildirim merkezini geçmişle doldururdu.
                continue
            owner = self._owner_of(inbox)
            changed.append(owner)
            _notify(*owner)
        return changed

    def start(self) -> bool:
        """Qt izleyicisini ve yoklama sayacını kurar; olay döngüsü yoksa False."""
        self.scan()
        try:
            from PySide6.QtCore import QFileSystemWatcher, QTimer
        except Exception:
            return False
        try:
            dirs = [str(d) for d in self.inbox_dirs() if d.is_dir()]
            self._watcher = QFileSystemWatcher(dirs)
            self._watcher.directoryChanged.connect(lambda _p: self.scan())
            self._timer = QTimer()
            self._timer.setInterval(int(self.poll_seconds * 1000))
            self._timer.timeout.connect(self._tick)
            self._timer.start()
        except Exception:
            logger.warning("Posta kutusu izleyicisi kurulamadı", exc_info=True)
            return False
        return True

    def _tick(self) -> None:
        if self._stopped:
            return
        # Yeni açılan ofis/ajan kutuları da izlenmeli; dizin listesi her turda
        # yenilenir (ofis yaratıldığında yeniden başlatma gerekmesin diye).
        try:
            if self._watcher is not None:
                current = set(self._watcher.directories())
                for d in self.inbox_dirs():
                    if d.is_dir() and str(d) not in current:
                        self._watcher.addPath(str(d))
        except Exception:
            pass
        self.scan()

    def stop(self) -> None:
        self._stopped = True
        try:
            if self._timer is not None:
                self._timer.stop()
        except Exception:
            pass
        self._timer = None
        self._watcher = None
