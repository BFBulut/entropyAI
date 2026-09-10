"""
Ajan kalıcı oturum rozeti (Faz 11-C, iş 2).

Sözleşme: `Entropy/Board/agents/<ad>/session.json` →
`{provider: {session_id|conversation_id, signature, model, effort, cwd, updated_at}}`
(bkz. `docs/STATE.md` §3, `core/identity.AgentSessionStore`).

Buradaki üç işlev Qt gerektirmez, testten doğrudan çağrılabilir:

* `read_session(agent)`   — dosyayı okur, en taze sağlayıcı kaydını döner
* `session_badge_text()`  — "kalıcı oturum · claude · 5 dk önce" / "oturum yok"
* `clear_session(agent)`  — "Oturumu yenile": dosyayı siler (ajan bir sonraki
  koşuda yeni oturum açar; agy ajanı imza değişince zaten yeniliyor)

Renk/ikon **belirteç sisteminden** gelir; bu modül yerel onaltılık renk yazmaz.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

NO_SESSION_TEXT = "oturum yok"


def session_file(agent: str, vault_path: Optional[Path | str] = None) -> Optional[Path]:
    """Ajanın oturum dosyası yolu; yol sözleşmesi yoksa None."""
    try:
        from entropy.core.paths import agent_session_path
    except Exception:
        return None
    try:
        return Path(agent_session_path(agent, vault_path))
    except Exception:
        return None


def _parse_ts(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def read_session(agent: str, vault_path: Optional[Path | str] = None,
                 path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """
    En taze sağlayıcı oturumu: `{provider, session_id, model, effort, updated_at}`.

    Dosya yoksa, bozuksa ya da hiçbir sağlayıcıda kimlik yoksa None döner —
    "oturum yok" ile "okuyamadım" arayüzde aynı şeydir (ikisinde de kalıcı
    oturum vaadi yoktur), ama uydurma bir rozet basılmaz.
    """
    target = Path(path) if path else session_file(agent, vault_path)
    if target is None or not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    best: Optional[Dict[str, Any]] = None
    for provider, record in data.items():
        if not isinstance(record, dict):
            continue
        ident = str(record.get("session_id") or record.get("conversation_id") or "")
        if not ident:
            continue
        entry = {
            "provider": str(provider),
            "session_id": ident,
            "model": str(record.get("model") or ""),
            "effort": str(record.get("effort") or ""),
            "signature": str(record.get("signature") or ""),
            "updated_at": record.get("updated_at") or "",
            "ts": _parse_ts(record.get("updated_at")),
        }
        if best is None or entry["ts"] > best["ts"]:
            best = entry
    return best


def humanize_age(ts: float, now: Optional[float] = None) -> str:
    """`ts` damgasının yaşı: "az önce" / "5 dk önce" / "3 sa önce" / "2 gün önce"."""
    if not ts:
        return ""
    seconds = max(0, int((now if now is not None else time.time()) - ts))
    if seconds < 60:
        return "az önce"
    if seconds < 3600:
        return f"{seconds // 60} dk önce"
    if seconds < 86400:
        return f"{seconds // 3600} sa önce"
    return f"{seconds // 86400} gün önce"


def session_badge_text(info: Optional[Dict[str, Any]], now: Optional[float] = None) -> str:
    """Rozet metni (ikonsuz; ikon `design.icon("link")` ile ayrı konur)."""
    if not info:
        return NO_SESSION_TEXT
    parts = ["kalıcı oturum", str(info.get("provider") or "?")]
    age = humanize_age(float(info.get("ts") or 0.0), now)
    if age:
        parts.append(age)
    return " · ".join(parts)


def session_tooltip(info: Optional[Dict[str, Any]]) -> str:
    if not info:
        return (
            "Bu ajan için kalıcı oturum kaydı yok; bir sonraki koşuda yeni "
            "oturum açılır."
        )
    lines = [
        f"Sağlayıcı: {info.get('provider')}",
        f"Oturum: {str(info.get('session_id'))[:16]}…",
    ]
    if info.get("model"):
        lines.append(f"Model: {info['model']}")
    if info.get("effort"):
        lines.append(f"Efor: {info['effort']}")
    if info.get("updated_at"):
        lines.append(f"Güncellendi: {info['updated_at']}")
    return "\n".join(lines)


def clear_session(agent: str, vault_path: Optional[Path | str] = None,
                  path: Optional[Path | str] = None) -> bool:
    """Oturum dosyasını siler. Zaten yoksa False (silinecek bir şey yoktu)."""
    target = Path(path) if path else session_file(agent, vault_path)
    if target is None or not target.exists():
        return False
    try:
        target.unlink()
    except Exception:
        return False
    return True
