"""Ajanın CANLI koşu durumu (Faz 13-A2, madde 4).

Kullanıcı gerçek ekranda şunu gördü: Ajanlar sekmesinde araştırmacının kartı
"kalıcı oturum · claude · 2 sa önce" diyordu, oysa görev kartı "Çalışıyor"du.
Rozet **oturum dosyasının yaşını** gösteriyordu; bu, ajanın şu anda çalışıp
çalışmadığıyla ilgisi olmayan bir sayıdır.

Bu modül tek bir soruya cevap verir: **bu ajan şu anda koşuyor mu, ne kadardır?**

Veri sözleşmesi (köprü ajanı paralel yazıyor, imza varsayılıyor):

    entropy.agents.identity.AgentSessionStore.status(name) -> {
        "state": "idle" | "running",
        "since": float | None,        # koşu başlangıcı (epoch)
        "card_id": str,
        "card_title": str,
        "last_run_at": float | None,
        "provider": str,
    }

Sözleşme henüz yoksa `getattr` ile **yumuşak düşülür**: durum panodaki
kartlardan türetilir (`taken`/`running` bir kart varsa ajan koşuyordur).
Böylece iki ajanın işi birbirini beklemez.

Qt gerektirmez; testten doğrudan çağrılabilir.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, Optional

__all__ = [
    "RUNNING_CARD_STATUSES",
    "agent_status",
    "status_from_cards",
    "format_duration",
    "run_badge_text",
    "running_agent_count",
]

#: Bir kart bu durumlardaysa sahibi ajan koşuyor sayılır.
RUNNING_CARD_STATUSES = ("taken", "running", "in_progress")

IDLE = "idle"
RUNNING = "running"


def _empty(provider: str = "") -> Dict[str, Any]:
    return {
        "state": IDLE,
        "since": None,
        "card_id": "",
        "card_title": "",
        "last_run_at": None,
        "provider": provider,
    }


def _epoch(value: Any) -> Optional[float]:
    """Damga → epoch saniye; ISO metni de kabul eder, çözemezse None."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        import datetime as dt

        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _field(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def status_from_cards(agent: str, cards: Iterable[Any]) -> Dict[str, Any]:
    """Sözleşme yokken pano kartlarından türetilen durum (yumuşak düşüş)."""
    info = _empty()
    newest_done: Optional[float] = None
    for card in cards or ():
        if str(_field(card, "agent", "")) != agent:
            continue
        status = str(_field(card, "status", ""))
        if status in RUNNING_CARD_STATUSES:
            started = _epoch(_field(card, "started_at", None)) or _epoch(
                _field(card, "updated_at", None)
            )
            info.update(
                state=RUNNING,
                since=started,
                card_id=str(_field(card, "id", "")),
                card_title=str(_field(card, "title", "")),
                provider=str(_field(card, "provider", "")),
            )
        else:
            ts = _epoch(_field(card, "finished_at", None)) or _epoch(
                _field(card, "updated_at", None)
            )
            if ts is not None and (newest_done is None or ts > newest_done):
                newest_done = ts
    if info["state"] != RUNNING:
        info["last_run_at"] = newest_done
    return info


def agent_status(agent: str, cards: Iterable[Any] = ()) -> Dict[str, Any]:
    """Ajanın canlı durumu: önce sözleşme, yoksa kartlardan türetme.

    Sözleşme `state` alanını vermiyorsa (ya da hiç yoksa) kart yolu kullanılır;
    sözleşme koşmuyor derken kart koşuyor diyorsa **kart kazanır**: kart panodaki
    tek gerçek, oturum dosyası yalnızca bir ipucudur.
    """
    contract: Dict[str, Any] = {}
    try:
        from entropy.agents import identity as _identity  # noqa: WPS433

        store_cls = getattr(_identity, "AgentSessionStore", None)
        status_fn = getattr(store_cls, "status", None) if store_cls else None
        if status_fn is not None:
            raw = store_cls().status(agent)
            if isinstance(raw, dict):
                contract = dict(raw)
    except Exception:
        contract = {}

    derived = status_from_cards(agent, cards)
    if not contract:
        return derived
    info = _empty(str(contract.get("provider") or derived.get("provider") or ""))
    info.update({k: contract[k] for k in info if k in contract})
    info["since"] = _epoch(info.get("since"))
    info["last_run_at"] = _epoch(info.get("last_run_at"))
    if derived["state"] == RUNNING and info["state"] != RUNNING:
        return derived
    if info["state"] == RUNNING and info["since"] is None:
        info["since"] = derived.get("since")
    if info["state"] != RUNNING and info["last_run_at"] is None:
        info["last_run_at"] = derived.get("last_run_at")
    return info


def format_duration(seconds: float) -> str:
    """Koşu süresi: "12 sn" / "1 dk 12 sn" / "2 sa 05 dk"."""
    total = max(0, int(seconds))
    if total < 60:
        return f"{total} sn"
    if total < 3600:
        return f"{total // 60} dk {total % 60:02d} sn"
    return f"{total // 3600} sa {(total % 3600) // 60:02d} dk"


def run_badge_text(info: Optional[Dict[str, Any]], now: Optional[float] = None) -> str:
    """Rozet metni: koşarken "çalışıyor · 1 dk 12 sn", boştayken "son koşu: …"."""
    from entropy.ui.widgets.agent_session_badge import humanize_age

    data = info or _empty()
    if data.get("state") == RUNNING:
        since = data.get("since")
        if since:
            moment = now if now is not None else time.time()
            return f"çalışıyor · {format_duration(moment - float(since))}"
        return "çalışıyor"
    last = data.get("last_run_at")
    if last:
        age = humanize_age(float(last), now)
        return f"son koşu: {age}" if age else "son koşu: az önce"
    return "koşu yok"


def running_agent_count(agents: Iterable[str], cards: Iterable[Any] = ()) -> int:
    """Gezinmedeki "Ajanlar" noktası için: kaç ajan şu anda koşuyor."""
    card_list = list(cards or ())
    return sum(1 for a in agents if agent_status(a, card_list).get("state") == RUNNING)
