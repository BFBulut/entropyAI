"""
Entropy → Desk düzenleme kuyruğu (Faz 13-C.3).

Neden onay kuyruğu
------------------
Kullanıcının kuralı iki yönlü: **Entropy Desk'i geliştirebilir**, ama ofis ve
ajan yaratmak KALICI bir yapı değişikliğidir. Sohbetteki bir cümlenin diske
yeni bir ofis açması, kullanıcının hiç görmediği bir kadro doğurur. Bu yüzden
`[DESK office_create|agent_edit|task]` blokları doğrudan uygulanmaz: yükleriyle
birlikte `Entropy/Desk/_pending/<id>.json` altına düşer, sohbette tek
satırlık "onay bekliyor" makbuzu görünür ve uygulama YALNIZCA kullanıcının
açık eylemiyle (`/desk approve <id>` ya da Desk panelindeki düğme) olur.

`[DESK msg]` kuyruğa girmez: talimat bırakmak yapı değiştirmez ve Entropy
zaten `/ask` + `/desk msg` ile orkestratöre yazabiliyor.

Yön kuralı
----------
Bu modül TEK YÖNLÜDÜR: Entropy'den Desk'e. Ters yön (Desk'in Entropy panosuna
kart açması) burada da, `board_tool_exec` içinde de reddedilir.

Uygulama yolu
-------------
Yeni bir yaratma mantığı YAZILMAZ: `core.slash_commands._handle_desk_admin` ve
`_handle_desk` yolları çağrılır. İkinci bir kadro yazıcısı, "ofis açılınca
orkestratör doğar" kuralının ikinci (ve er geç ayrışan) kopyası olurdu.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Bekleyen isteklerin kasadaki kökü. Entropy'nin KENDİ verisi (`Entropy/`
#: altında), Desk kökünün (`Desk/Offices`) DIŞINDA: Desk bu kuyruğu ne okur ne
#: yazar — tek yön kuralı.
PENDING_SUBDIR = "Entropy/Desk/_pending"

#: Kaynak etiketi: isteği kimin ürettiği (sohbet turu / arayüz).
SOURCE_CHAT = "entropy-chat"

#: Onay isteyen (yapısal) türler.
APPROVAL_KINDS = ("office_create", "agent_edit", "task")
#: Onaysız uygulanan türler.
DIRECT_KINDS = ("msg",)


def pending_dir(vault_path: Optional[Path] = None) -> Path:
    from entropy.core.paths import vault_root

    return vault_root(vault_path) / PENDING_SUBDIR


def _pending_path(request_id: str, vault_path: Optional[Path] = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(request_id or "").strip()) or "istek"
    return pending_dir(vault_path) / f"{safe}.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(kind: str) -> str:
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{kind}"


def summarize(kind: str, payload: Dict[str, Any]) -> str:
    """İnsanın onay ekranında gördüğü tek satır."""
    office = str(payload.get("office") or payload.get("name") or "").strip()
    if kind == "office_create":
        return f"Ofis aç: {office} — {str(payload.get('purpose') or '').strip()}"
    if kind == "agent_edit":
        return (f"Ofis ajanı: {office} / {str(payload.get('name') or '').strip()} — "
                f"{str(payload.get('description') or '').strip()}")
    if kind == "task":
        return f"Ofise görev: {office} — {str(payload.get('title') or '').strip()}"
    if kind == "msg":
        return f"Ofise talimat: {office} — {str(payload.get('text') or '').strip()}"
    return f"{kind}: {office}"


# --- kuyruk ------------------------------------------------------------------


def queue_request(kind: str, payload: Dict[str, Any], *, source: str = SOURCE_CHAT,
                  vault_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Bekleyen isteği diske yazar ve künyesini döndürür.

    Hiçbir yapı DEĞİŞMEZ: bu çağrının tek yan etkisi bir JSON dosyasıdır.
    """
    kind = str(kind or "").strip()
    record = {
        "id": _new_id(kind or "istek"),
        "kind": kind,
        "payload": dict(payload or {}),
        "created_at": _now(),
        "source": str(source or SOURCE_CHAT),
        "summary": summarize(kind, dict(payload or {})),
    }
    path = _pending_path(record["id"], vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def list_pending(vault_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Bekleyen isteklerin künyeleri (eskiden yeniye)."""
    out: List[Dict[str, Any]] = []
    root = pending_dir(vault_path)
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("Bekleyen istek okunamadı: %s", path, exc_info=True)
            continue
        if not isinstance(data, dict):
            continue
        data.setdefault("id", path.stem)
        data.setdefault("payload", {})
        data.setdefault("summary", summarize(str(data.get("kind") or ""),
                                             dict(data.get("payload") or {})))
        out.append(data)
    out.sort(key=lambda d: str(d.get("created_at") or ""))
    return out


def get_pending(request_id: str, vault_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = _pending_path(request_id, vault_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def reject_pending(request_id: str, reason: str = "",
                   vault_path: Optional[Path] = None) -> bool:
    """
    İsteği siler; hiçbir yapı değişmez.

    Gerekçe günlüğe düşer (kart/ofis üretilmediği için yazılacak bir yer yok);
    dönüş, kayıt gerçekten var mıydı sorusunun yanıtıdır.
    """
    path = _pending_path(request_id, vault_path)
    if not path.is_file():
        return False
    try:
        path.unlink()
    except OSError:
        return False
    logger.info("Desk isteği reddedildi (%s): %s", request_id, reason or "-")
    return True


# --- uygulama ----------------------------------------------------------------


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", str(text or ""))
    return " ".join(cleaned.split())


def apply_pending(request_id: str, vault_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Onaylanan isteği uygular ve `{ok, message, created_paths}` döndürür.

    Uygulama başarılıysa bekleyen dosya silinir; başarısızsa KALIR (kullanıcı
    yeniden deneyebilsin).
    """
    record = get_pending(request_id, vault_path)
    if record is None:
        return {"ok": False, "message": f"'{request_id}' kimlikli bekleyen istek yok.",
                "created_paths": []}
    result = apply_request(str(record.get("kind") or ""),
                           dict(record.get("payload") or {}), vault_path=vault_path)
    if result.get("ok"):
        try:
            _pending_path(request_id, vault_path).unlink()
        except OSError:
            pass
    return result


def apply_request(kind: str, payload: Dict[str, Any],
                  vault_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Tek bir Desk düzenlemesini UYGULAR (onay denetimi çağıranın işidir).

    `_handle_desk_admin` / `_handle_desk` yollarını kullanır: ofis açılınca
    orkestratör de doğar, ajan tanımı ofisin çalışma dizinine derlenir.
    """
    kind = str(kind or "").strip()
    payload = dict(payload or {})
    try:
        from entropy.agents.offices import OfficeRegistry
        from entropy.core import slash_commands as _sc
    except Exception as exc:  # pragma: no cover - savunma
        return {"ok": False, "message": f"Desk katmanı yüklenemedi: {exc}",
                "created_paths": []}

    offices = OfficeRegistry(vault_path=vault_path) if vault_path is not None \
        else OfficeRegistry()
    created: List[str] = []

    if kind == "office_create":
        name = str(payload.get("name") or "").strip()
        purpose = str(payload.get("purpose") or "").strip()
        if not name:
            return {"ok": False, "message": "Ofis adı boş.", "created_paths": []}
        message = _sc._handle_desk_admin("office", f"add {name} :: {purpose}", offices)
        spec = offices.get(name)
        if spec is None:
            return {"ok": False, "message": _strip_html(message), "created_paths": []}
        created.append(str(offices.office_dir(name)))
        try:
            agents = offices.agents(name)
            if spec.orchestrator:
                created.append(str(agents.agent_file(spec.orchestrator)))
        except Exception:
            pass
        return {"ok": True, "message": _strip_html(message), "created_paths": created}

    if kind == "agent_edit":
        office = str(payload.get("office") or "").strip()
        name = str(payload.get("name") or "").strip()
        description = str(payload.get("description") or "").strip()
        if not office or not name:
            return {"ok": False, "message": "Ofis ya da ajan adı boş.",
                    "created_paths": []}
        if offices.get(office) is None:
            return {"ok": False, "message": f"'{office}' adında ofis yok.",
                    "created_paths": []}
        agents = offices.agents(office)
        action = "edit" if agents.get(name) is not None else "add"
        message = _sc._handle_desk_admin(
            "agent", f"{action} {office} {name} :: {description}", offices)
        spec = agents.get(name)
        if spec is None:
            return {"ok": False, "message": _strip_html(message), "created_paths": []}
        # Model/efor isteğe bağlı: yalnızca yazıldıysa uygulanır (boş alan
        # ofisin varsayılanını EZMEZ).
        model = str(payload.get("model") or "").strip()
        effort = str(payload.get("effort") or "").strip().lower()
        if model or effort:
            from dataclasses import replace as _replace

            try:
                agents.update(_replace(spec,
                                       model=model or spec.model,
                                       effort=effort or getattr(spec, "effort", "")))
            except Exception:
                logger.debug("Ajan model/efor güncellenemedi", exc_info=True)
        created.append(str(agents.agent_file(name)))
        return {"ok": True, "message": _strip_html(message), "created_paths": created}

    if kind == "task":
        office = str(payload.get("office") or "").strip()
        title = str(payload.get("title") or "").strip()
        goal = str(payload.get("goal") or "").strip()
        project = str(payload.get("project") or "").strip()
        if not office or not title:
            return {"ok": False, "message": "Ofis ya da başlık boş.",
                    "created_paths": []}
        proj = f"@{project} " if project else ""
        message = _sc._handle_desk(f"task {office} {proj}{title} :: {goal or title}")
        ok = "Devredildi" in message or "Kart:" in message
        return {"ok": ok, "message": _strip_html(message), "created_paths": created}

    if kind == "msg":
        office = str(payload.get("office") or "").strip()
        text = str(payload.get("text") or "").strip()
        if not office or not text:
            return {"ok": False, "message": "Ofis ya da talimat boş.",
                    "created_paths": []}
        message = _sc._handle_desk(f"msg {office} :: {text}")
        ok = "Bırakıldı" in message
        return {"ok": ok, "message": _strip_html(message), "created_paths": created}

    return {"ok": False, "message": f"Bilinmeyen Desk düzenlemesi: {kind}",
            "created_paths": []}


# --- sohbet yolu -------------------------------------------------------------


def consume_desk_calls(text: str, vault_path: Optional[Path] = None) -> List[str]:
    """
    Sohbet yanıtındaki `[DESK …]` bloklarını tüketir; makbuz satırlarını döndürür.

    Yapısal bloklar KUYRUĞA girer (hiçbir yapı değişmez), `msg` doğrudan
    uygulanır. Hiçbir hata yükseltilmez: bozuk bir blok sohbet turunu düşürmez.
    """
    try:
        from entropy.agents import board_tools
    except Exception:
        return []
    try:
        calls = board_tools.parse_desk_calls(text or "")
    except Exception:
        logger.warning("Desk blokları ayrıştırılamadı", exc_info=True)
        return []
    receipts: List[str] = []
    for call in calls:
        kind = call.name
        payload = dict(call.args or {})
        if kind in DIRECT_KINDS:
            result = apply_request(kind, payload, vault_path=vault_path)
            receipts.append(
                ("Ofise talimat bırakıldı: " if result.get("ok")
                 else "Ofise talimat bırakılamadı: ") + summarize(kind, payload)
            )
            continue
        if kind not in APPROVAL_KINDS:
            continue
        try:
            record = queue_request(kind, payload, vault_path=vault_path)
        except Exception as exc:
            logger.warning("Desk isteği kuyruğa yazılamadı: %s", exc, exc_info=True)
            receipts.append(f"Desk düzenlemesi kuyruğa alınamadı: {exc}")
            continue
        receipts.append(
            f"Desk düzenleme onayı bekliyor: {record['summary']} "
            f"(/desk approve {record['id']})"
        )
    return receipts


__all__ = [
    "APPROVAL_KINDS", "DIRECT_KINDS", "PENDING_SUBDIR", "SOURCE_CHAT",
    "apply_pending", "apply_request", "consume_desk_calls", "get_pending",
    "list_pending", "pending_dir", "queue_request", "reject_pending",
    "summarize",
]
