"""
Entropy Board durum makinesi — geçerli geçişlerin TEK kaynağı (Faz 11-C.1).

Neden bu dosya var
------------------
Faz 11 öncesi kart durumu altı ayrı dosyada `replace(card, status=...)` ile
yazılıyordu (`tasks.py:1088/1192/1222`, `harness.py:1826`, iki arayüz düğmesi).
"Geçerli geçiş" diye bir kavram yoktu: bir durum eklemek altı dosyaya dokunmak,
bir geçişi yasaklamak ise imkânsızdı. Tablo veri olarak burada durur; geçişi
uygulayan tek fonksiyon `transition()`'dır.

Neden kütüphane yok
-------------------
`transitions` / `python-statemachine` karşılığında yalnızca 12 satırlık bir
tablo veriyor, buna karşılık PyInstaller paketinde bir bağımlılık daha demek
(PyYAML zaten "paketlenmiş exe'de bulunmayabilir" diye isteğe bağlı tutuluyor,
`registry.py:26-30`). Kütüphaneden alınan tek şey DİSİPLİN: geçiş tek yerde,
geçersiz geçiş hata, kesişen ilgiler (olay yazımı, sinyal) tek kancada.

`transitions`'ın bilinen tuzağı da burada bilerek kapatıldı: geçiş SONRASI
istisna geri alınmaz. Bu yüzden sıra "önce doğrula → sonra kartı üret → sonra
olayı yaz" biçimindedir; doğrulama başarısızsa hiçbir yan etki oluşmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Tuple

# Sekiz durum. `assigned` (ajana verildi, henüz sahiplenilmedi), `taken`
# (atomik claim alındı, süreç henüz doğmadı) ve `canceled` Faz 11-C'de eklendi.
# "blocked" AYRI BİR DURUM DEĞİL: kart `assigned`da bekler ve engelin nedeni
# kart notuna yazılır — dokuzuncu bir durum, panonun okunabilirliğini geçişten
# daha çok bozuyordu.
STATUSES: Tuple[str, ...] = (
    "backlog", "assigned", "taken", "running",
    "review", "done", "failed", "canceled",
)

# Terminal durumlar: buradan çıkış yok (yeniden koşu YENİ bir attempt'tir).
TERMINAL_STATUSES: Tuple[str, ...] = ("done", "canceled")

# Olay sözlüğü — 12 tip. Tablo ile birebir; günlüğe (`board_events`) yazılan
# `action` alanı tam olarak bu değerlerdir.
EVENTS: Tuple[str, ...] = (
    "task.created",
    "task.assigned",
    "task.claimed",
    "run.started",
    "checkpoint.written",
    "run.finished",
    "claim.expired",
    "lock.timeout",
    "task.accepted",
    "task.rejected",
    "task.canceled",
    "task.reset",
    # Faz 12-B: DURUM DEĞİŞTİRMEYEN gözlem olayı. Kart dosyaları ile olay
    # projeksiyonu ayrıştığında yazılır; `project()` bunu geçiş tablosuna
    # sokmadan atlar (aksi hâlde her ayrışma bir de "rejected" üretirdi).
    "board.drift",
)

#: Geçiş üretmeyen (yalnızca kayda geçen) olaylar.
INFO_EVENTS: Tuple[str, ...] = ("board.drift",)

# Kartı `review`den `done`a yalnızca İNSAN taşıyabilir. Ajan çıktısını kimse
# okumadan "bitti" saymak panonun tamamını anlamsız kılardı (tasks.py:23-26).
HUMAN_ACTOR = "human"

# Yeniden koşu tavanı: `review → assigned` (reddedildi) en çok bu kadar.
MAX_ATTEMPTS = 2


class InvalidTransition(Exception):
    """Tabloda karşılığı olmayan (durum, olay) çifti."""

    def __init__(self, status: str, event: str, reason: str = ""):
        self.status = status
        self.event = event
        self.reason = reason
        detail = f": {reason}" if reason else ""
        super().__init__(f"Geçersiz geçiş: {status!r} --{event}-->{detail}")


@dataclass(frozen=True)
class Transition:
    """Tablo satırı. `sources` boşsa kaynak durum aranmaz (yaratma olayı)."""

    name: str
    sources: Tuple[str, ...]
    event: str
    target: str
    guard: Optional[Callable[[dict, dict], Optional[str]]] = None
    note: str = ""


# --- korumalar (guard) -------------------------------------------------------
# Sözleşme: koruma HATA METNİ döndürür (geçiş reddedilir) ya da None (geçer).
# Metin döndürmek, bool döndürmekten üstün: reddin nedeni olay günlüğüne ve
# ajanın gördüğü hata mesajına aynen yazılabiliyor.


def _guard_created(card: dict, payload: dict) -> Optional[str]:
    if not str(card.get("title") or "").strip():
        return "kart başlığı boş"
    if not str(card.get("goal") or card.get("title") or "").strip():
        return "kart hedefi boş"
    return None


def _guard_assigned(card: dict, payload: dict) -> Optional[str]:
    agent = str(payload.get("agent") or card.get("agent") or "").strip()
    if not agent:
        return "atanacak ajan yok"
    # Kadro doğrulaması çağıranın işidir (defter iki kökten gelebiliyor);
    # burada yalnızca "biri yazılmış mı" sorulur.
    return None


def _guard_claimed(card: dict, payload: dict) -> Optional[str]:
    if not payload.get("claimed"):
        # Sahiplenme kilidi (`claims/<id>.lock`, O_CREAT|O_EXCL) ALINMADAN bu
        # geçiş yapılamaz: iki dispatcher turunun aynı kartı almasını engelleyen
        # tek şey bu koruma.
        return "sahiplenme kilidi alınmadı"
    if not str(payload.get("claimed_by") or "").strip():
        return "sahiplenen ajan boş"
    return None


def _guard_started(card: dict, payload: dict) -> Optional[str]:
    if not str(payload.get("provider") or card.get("provider") or "").strip():
        return "sağlayıcı belirsiz"
    return None


def _guard_finished(card: dict, payload: dict) -> Optional[str]:
    return None


def _guard_accepted(card: dict, payload: dict) -> Optional[str]:
    if str(payload.get("actor") or "").strip().lower() != HUMAN_ACTOR:
        return "'done' yalnızca insan onayıyla verilir"
    proof = card.get("proof") or payload.get("proof") or ""
    if not str(proof).strip():
        return ("kanıt yok: kartı kapatmadan önce testi koş ve `[KANIT]` bloğunu "
                "kartın Sonuç bölümüne yaz")
    return None


def _guard_rejected(card: dict, payload: dict) -> Optional[str]:
    if int(card.get("attempt") or 0) >= MAX_ATTEMPTS:
        return f"yeniden koşu tavanı aşıldı (attempt={card.get('attempt')})"
    return None


def _guard_archived(card: dict, payload: dict) -> Optional[str]:
    """
    `review`/`failed` bir kartın arşivlenmesi (T13) yalnızca GEREKÇEYLE.

    Neden ayrı satır: T12 "koşan işi durdur" demek, bu ise "bitmiş ama artık
    panoda durmasın" demek. İkisini birleştirmek her tamamlanmış kartı
    gerekçesiz iptal edilebilir yapardı; `done` ise terminal kalır (kabul
    edilmiş iş geri alınmaz).
    """
    if not str(payload.get("reason") or "").strip():
        return "arşivleme gerekçesi (reason) boş olamaz"
    return None


def _guard_expired(card: dict, payload: dict) -> Optional[str]:
    if payload.get("pid_alive"):
        return "sahiplenen süreç hâlâ canlı"
    return None


# --- tablo -------------------------------------------------------------------
# Rapor §3.2'deki 12 satır, aynı sırayla.

TRANSITIONS: Tuple[Transition, ...] = (
    Transition("T1", (), "task.created", "backlog", _guard_created,
               "kart dosyası yazılır"),
    Transition("T2", ("backlog",), "task.assigned", "assigned", _guard_assigned,
               "agent yazılır"),
    Transition("T3", ("assigned",), "task.claimed", "taken", _guard_claimed,
               "claimed_by + claim_expiry"),
    Transition("T4", ("taken",), "run.started", "running", _guard_started,
               "started_at + provider"),
    Transition("T5", ("running",), "checkpoint.written", "running", None,
               "checkpoint yolu"),
    Transition("T6", ("running",), "run.finished", "review", _guard_finished,
               "ok=1: summary + proof + report_path"),
    Transition("T7", ("running",), "run.finished", "failed", _guard_finished,
               "ok=0: summary"),
    Transition("T8", ("taken", "running"), "claim.expired", "assigned", _guard_expired,
               "kilit silinir, attempt artmaz"),
    Transition("T9", ("running",), "lock.timeout", "assigned", None,
               "proje kilidi alınamadı, yeniden kuyruk"),
    Transition("T10", ("review",), "task.accepted", "done", _guard_accepted,
               "insan onayı"),
    Transition("T11", ("review",), "task.rejected", "assigned", _guard_rejected,
               "attempt += 1"),
    Transition("T12", ("backlog", "assigned", "taken", "running"), "task.canceled",
               "canceled", None, "süreç öldürülür"),
    Transition("T13", ("review", "failed"), "task.canceled", "canceled",
               _guard_archived, "arşivleme: gerekçe ZORUNLU"),
)

# Tabloda YER ALMAYAN ama gerekli tek kaçış: uzlaştırıcının `failed` bir kartı
# yeniden kuyruğa alması ve arayüzün bir kartı elle geri çekmesi. Ayrı olay
# (`task.reset`) çünkü tabloya karışırsa "her durumdan her duruma" kapısı açılır.
RESET_SOURCES: Tuple[str, ...] = ("failed", "review", "assigned", "taken", "running")


def _row_key(t: Transition) -> str:
    return f"{t.name}:{t.event}"


def transitions_for(status: str, event: str) -> List[Transition]:
    """Bu (durum, olay) çiftine uyan tablo satırları (sırayla)."""
    status = str(status or "").strip().lower()
    event = str(event or "").strip()
    out: List[Transition] = []
    for row in TRANSITIONS:
        if row.event != event:
            continue
        if row.sources and status not in row.sources:
            continue
        out.append(row)
    return out


def can(status: str, event: str) -> bool:
    """Tabloda karşılığı var mı (koruma çalıştırılmadan)."""
    return bool(transitions_for(status, event))


def allowed_events(status: str) -> List[str]:
    """Bu durumdan yayılabilecek olaylar — hata mesajlarını yönlendirici yapar."""
    return sorted({t.event for t in TRANSITIONS if not t.sources
                   or str(status or "").lower() in t.sources})


def _card_dict(card) -> dict:
    if isinstance(card, dict):
        return dict(card)
    keys = ("id", "title", "goal", "status", "agent", "provider", "attempt",
            "proof", "checkpoint", "office", "effort", "priority")
    return {k: getattr(card, k, None) for k in keys}


def resolve_target(card, event: str, payload: Optional[dict] = None) -> Transition:
    """
    Bu (kart, olay) için uygulanacak tablo satırı.

    `run.finished` iki satıra (T6/T7) uyar; ayrımı `payload["ok"]` yapar.
    Kanıt korunumu: `ok=1` ama kanıt AÇIKÇA kırmızıysa (`proof.green is False`)
    kart `review`e değil `failed`a düşer — "yeşil olmayan kanıtla kapanış"
    Faz 10-A'daki close-with-proof kuralının makineleşmiş hâli.
    """
    payload = dict(payload or {})
    data = _card_dict(card)
    status = str(data.get("status") or "backlog").strip().lower()
    event = str(event or "").strip()
    if event not in EVENTS:
        raise InvalidTransition(status, event, "bilinmeyen olay")

    rows = transitions_for(status, event)
    if event == "run.finished":
        ok = bool(payload.get("ok", True))
        proof = payload.get("proof")
        if isinstance(proof, dict) and proof.get("green") is False:
            ok = False
        rows = [r for r in rows if (r.target == "review") == ok]
    if not rows:
        raise InvalidTransition(
            status, event,
            "bu durumdan bu olay yayılamaz; olabilecekler: "
            + ", ".join(allowed_events(status)),
        )
    row = rows[0]
    guard = row.guard
    if guard is not None:
        merged = dict(payload)
        merged.setdefault("actor", payload.get("actor", ""))
        reason = guard(data, merged)
        if reason:
            raise InvalidTransition(status, event, reason)
    return row


def transition(card, event: str, payload: Optional[dict] = None, actor: str = ""):
    """
    Kartın YENİ hâlini döndürür (kaydetmez, olay yazmaz).

    Sözleşme bilinçli olarak saf: yazma ve olay günlüğü `board_events`'in işi,
    Qt sinyali `TaskBoard`'ın. Bu fonksiyon yalnızca "geçiş geçerli mi ve kart
    neye dönüşür" sorusunu yanıtlar; böylece test edilebilir ve yan etkisizdir.

    `card` bir `TaskCard` ise aynı tipte kopya, `dict` ise `dict` döner.
    """
    payload = dict(payload or {})
    if actor:
        payload.setdefault("actor", actor)
    row = resolve_target(card, event, payload)
    changes = _effects(card, row, payload)
    if isinstance(card, dict):
        out = dict(card)
        out.update(changes)
        out["status"] = row.target
        return out
    return replace(card, status=row.target, **{
        k: v for k, v in changes.items() if hasattr(card, k)
    })


def _now() -> str:
    import datetime

    return datetime.datetime.now().isoformat(timespec="seconds")


def _effects(card, row: Transition, payload: dict) -> Dict[str, object]:
    """Geçişin kart alanlarına etkisi (tablonun 'Etki' sütunu)."""
    data = _card_dict(card)
    out: Dict[str, object] = {}
    event = row.event

    if event == "task.assigned":
        agent = str(payload.get("agent") or data.get("agent") or "").strip()
        out["agent"] = agent
        out["claimed_by"] = ""
        out["claim_expiry"] = ""
    elif event == "task.claimed":
        out["claimed_by"] = str(payload.get("claimed_by") or "")
        out["claim_expiry"] = str(payload.get("claim_expiry") or "")
    elif event == "run.started":
        out["started_at"] = str(payload.get("started_at") or _now())
        provider = str(payload.get("provider") or data.get("provider") or "")
        if provider:
            out["provider"] = provider
        if payload.get("model"):
            out["model"] = str(payload["model"])
        if payload.get("effort"):
            out["effort"] = str(payload["effort"])
    elif event == "checkpoint.written":
        if payload.get("checkpoint"):
            out["checkpoint"] = str(payload["checkpoint"])
    elif event == "run.finished":
        out["finished_at"] = str(payload.get("finished_at") or _now())
        if payload.get("summary") is not None:
            out["summary"] = str(payload.get("summary") or "")
        proof = payload.get("proof")
        if isinstance(proof, dict):
            text = " ".join(str(proof.get("command") or "").split())
            result = " ".join(str(proof.get("result") or "").split())
            merged = " — ".join(p for p in (text, result) if p)
            if merged:
                out["proof"] = merged
        elif isinstance(proof, str) and proof.strip():
            out["proof"] = proof.strip()
        if payload.get("report_path"):
            out["report_path"] = str(payload["report_path"])
        out["claimed_by"] = ""
        out["claim_expiry"] = ""
    elif event in ("claim.expired", "lock.timeout"):
        out["claimed_by"] = ""
        out["claim_expiry"] = ""
        out["started_at"] = ""
    elif event == "task.rejected":
        out["attempt"] = int(data.get("attempt") or 0) + 1
        out["claimed_by"] = ""
        out["claim_expiry"] = ""
    elif event == "task.canceled":
        out["finished_at"] = str(payload.get("finished_at") or _now())
        if payload.get("summary"):
            out["summary"] = str(payload["summary"])
        out["claimed_by"] = ""
        out["claim_expiry"] = ""
    if payload.get("event_seq"):
        out["event_seq"] = int(payload["event_seq"])
    return out


def reset(card, reason: str = "", actor: str = "system"):
    """
    `task.reset`: asılı/başarısız kartı `assigned`a çeker (uzlaştırıcı yolu).

    Tabloya karışmaz çünkü kaynak kümesi geniş; ayrı kapı olması "keyfi geçiş"
    ile "kurtarma" arasındaki farkı kodda görünür kılıyor.
    """
    data = _card_dict(card)
    status = str(data.get("status") or "").lower()
    if status not in RESET_SOURCES:
        raise InvalidTransition(status, "task.reset", "bu durum kurtarılamaz")
    target = "assigned" if str(data.get("agent") or "").strip() else "backlog"
    changes = {"claimed_by": "", "claim_expiry": "", "started_at": ""}
    if reason:
        changes["summary"] = reason
    if isinstance(card, dict):
        out = dict(card)
        out.update(changes)
        out["status"] = target
        return out
    return replace(card, status=target, **{
        k: v for k, v in changes.items() if hasattr(card, k)
    })


__all__ = [
    "STATUSES", "TERMINAL_STATUSES", "EVENTS", "INFO_EVENTS", "TRANSITIONS", "Transition",
    "InvalidTransition", "HUMAN_ACTOR", "MAX_ATTEMPTS", "RESET_SOURCES",
    "can", "allowed_events", "transitions_for", "resolve_target",
    "transition", "reset",
]
