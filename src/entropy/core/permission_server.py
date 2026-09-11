"""
Entropy'nin kendi izin sunucusu — saf Python stdio MCP (Faz 14-B, §6.6).

Ne işe yarar
------------
Saf kip (ADR-0002) CLI'ın varsayılan izin diyaloğunu düşürdü ve yerine hiçbir
şey konmadı; model reddedilen aracı "onay penceresinde bekliyor" diye
uyduruyordu. Artık CLI'ya `--permission-prompt-tool mcp__entropy__approve`
verilir: CLI izin gerektiren her araç için BU sunucuyu çağırır, sunucu isteği
`core/pending.py` kuyruğuna kart olarak koyar, kullanıcının kararını bekler ve
kararı CLI'ya döner.

Ölçülen sözleşme (canlı spike, `scratch/phase14/permission_spike/README.md`;
`claude` 2.1.268 ile 5 gerçek koşum)
-----------------------------------------------------------------------------
* Taşıma satır satır JSON-RPC 2.0'dır (NDJSON), `Content-Length` başlığı YOK.
* El sıkışma: `initialize` → `notifications/initialized` → `tools/list`.
  İstemci `protocolVersion: "2025-11-25"` bildirdi, sunucu `"2025-06-18"`
  döndürdüğü hâlde bağlantı kabul edildi.
* Çağrı: `tools/call` → `params.arguments` TAM OLARAK üç alan taşır:
  `tool_name` (str), `input` (aracın ham argümanları), `tool_use_id` (str).
  Oturum kimliği, cwd, izin kipi, öneri listesi GELMEZ.
* Yanıt: karar `content[0].text` içinde **JSON metni** olarak döner ve kabul
  edilir; sonuç TEK bir text parçası taşımalıdır — `structuredContent` gibi ek
  alan konursa CLI "invalid result" verip kararı hiç okumaz (canlı S2 ölçümü).
  `isError: false` şart.
      izin: {"behavior": "allow", "updatedInput": <gelen input>}
      ret:  {"behavior": "deny",  "message": "<kısa Türkçe sebep>"}
  Ret mesajı modelin göreceği ARAÇ HATASI metnidir.
* Yanıt süresine üst sınır ÖLÇÜLMEDİ: 45 sn bekleyen bir çağrı sorunsuz koştu
  (`result.subtype = "success"`). Belgedeki 30 sn BAĞLANTI zaman aşımıdır.
  Tavanı Entropy koyar (`DEFAULT_TIMEOUT_S`, 15 dk), aksi hâlde kullanıcı
  paneli görmezse koşum süresiz asılır.
* "Güvenli komut" sınıfı (ör. `echo`) izin kancasından ÖNCE koşar; her araç
  kullanımının sorulacağı garanti EDİLEMEZ (spike §1).

Süreç modeli
------------
Sunucu ayrı bir süreçtir ama onu Entropy BAŞLATMAZ: `--mcp-config` içindeki
`command` ile **CLI'ın kendisi** doğurur (stdio). Hazır olma denetimi de
CLI'dadır (bağlantı zaman aşımı). Entropy'nin sorumluluğu giriş noktasının
çalıştırılabilir olduğunu doğrulamak (`entry_point()`) ve kararın okunacağı
veri kökünü `env` ile devretmektir — spike bu kanalın çalıştığını ölçtü.
Çocuk sürecin penceresi `platform/proc.popen_kwargs` ile gizlenir (§4.3).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, IO, List, Optional

logger = logging.getLogger(__name__)

SERVER_NAME = "entropy"
TOOL_NAME = "approve"
#: CLI'ya verilen tam ad: `mcp__<sunucu>__<araç>`.
PERMISSION_TOOL = f"mcp__{SERVER_NAME}__{TOOL_NAME}"
PROTOCOL_VERSION = "2025-06-18"
SERVER_VERSION = "1.0.0"

#: Kullanıcı kararı için tavan (sn). CLI sınır koymuyor; bu bizim tavanımız.
DEFAULT_TIMEOUT_S = 15 * 60
TIMEOUT_ENV = "ENTROPY_PERMISSION_TIMEOUT_S"

#: Risk bandı — onay kartındaki renk/uyarı bunu okur.
HIGH_RISK_TOOLS = ("Bash", "BashOutput", "KillShell", "NotebookEdit")
MEDIUM_RISK_TOOLS = ("Write", "Edit", "MultiEdit")
LOW_RISK_TOOLS = ("Read", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite")

DENY_TIMEOUT_MESSAGE = "Onay zaman aşımına uğradı; komut çalıştırılmadı."
DENY_DEFAULT_MESSAGE = "Kullanıcı bu aracı reddetti."

__all__ = [
    "SERVER_NAME",
    "TOOL_NAME",
    "PERMISSION_TOOL",
    "PROTOCOL_VERSION",
    "DEFAULT_TIMEOUT_S",
    "TIMEOUT_ENV",
    "risk_for_tool",
    "summarize_input",
    "tool_definition",
    "decide",
    "handle_message",
    "serve",
    "entry_point",
    "mcp_config_payload",
    "write_mcp_config",
]


# --- sınıflandırma -----------------------------------------------------------


def risk_for_tool(tool_name: str) -> str:
    """`Bash` → high, `Write/Edit` → medium, okuma araçları → low."""
    name = str(tool_name or "").strip()
    if name in HIGH_RISK_TOOLS:
        return "high"
    if name in MEDIUM_RISK_TOOLS:
        return "medium"
    if name in LOW_RISK_TOOLS:
        return "low"
    # Bilinmeyen araç (MCP ad alanı dâhil): orta bant. "low" varsayılsaydı
    # yeni bir yazma aracı sessizce düşük riskli görünürdü.
    return "medium"


def summarize_input(tool_name: str, tool_input: Any, limit: int = 400) -> str:
    """Onay kartında görünen tek satır (komut varsa komutun kendisi)."""
    if isinstance(tool_input, dict):
        for key in ("command", "file_path", "path", "url", "pattern", "query"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
        else:
            text = json.dumps(tool_input, ensure_ascii=False)
    else:
        text = str(tool_input or "")
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text or str(tool_name or "")


def tool_definition() -> Dict[str, Any]:
    """`tools/list` girdisi. Şema kasten GEVŞEK: CLI onu doğrulamıyor."""
    return {
        "name": TOOL_NAME,
        "description": (
            "Entropy onay yüzeyi: aracın çalışmasına izin verilip verilmediğini "
            "kullanıcıya sorar."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "input": {"type": "object"},
                "tool_use_id": {"type": "string"},
            },
            "required": ["tool_name", "input"],
            "additionalProperties": True,
        },
    }


# --- karar -------------------------------------------------------------------


def decide(
    arguments: Dict[str, Any],
    queue=None,
    timeout_s: Optional[float] = None,
    cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Bir izin isteğini kuyruğa koyar, kararı bekler ve CLI'ın anladığı nesneyi
    döndürür (`{"behavior": ...}`).

    `cache`: aynı `tool_use_id` ikinci kez sorulursa kullanıcıya TEKRAR
    sorulmaz (spike §7 madde 5).
    """
    tool_name = str(arguments.get("tool_name") or "Araç")
    tool_input = arguments.get("input")
    tool_use_id = str(arguments.get("tool_use_id") or "")
    if cache is not None and tool_use_id and tool_use_id in cache:
        return cache[tool_use_id]

    if queue is None:
        from entropy.core.pending import PendingQueue

        queue = PendingQueue()
    if timeout_s is None:
        timeout_s = _timeout_from_env()

    summary = summarize_input(tool_name, tool_input)
    item_id = queue.add(
        kind="tool_permission",
        title=f"{tool_name}: {summary}",
        detail=json.dumps(tool_input if tool_input is not None else {},
                          ensure_ascii=False, indent=2),
        risk=risk_for_tool(tool_name),
        source="claude-cli",
        payload={
            "tool_name": tool_name,
            "input": tool_input if isinstance(tool_input, dict) else {},
            "tool_use_id": tool_use_id,
        },
    )
    record = queue.wait(item_id, timeout_s)
    if record is None:
        decision = {"behavior": "deny", "message": DENY_TIMEOUT_MESSAGE}
    elif record.get("status") == "approved":
        decision = {
            "behavior": "allow",
            "updatedInput": tool_input if tool_input is not None else {},
        }
    else:
        note = str(record.get("note") or "").strip()
        decision = {"behavior": "deny", "message": note or DENY_DEFAULT_MESSAGE}
    decision["pending_id"] = item_id
    if cache is not None and tool_use_id:
        cache[tool_use_id] = decision
    return decision


def _timeout_from_env() -> float:
    raw = os.environ.get(TIMEOUT_ENV)
    try:
        value = float(raw) if raw else 0.0
    except ValueError:
        value = 0.0
    return value if value > 0 else float(DEFAULT_TIMEOUT_S)


def _tool_result(decision: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kararın MCP `tools/call` sonucu hâli.

    `content` TEK bir `text` parçası taşır ve başka alan EKLENMEZ.

    Ölçüldü (canlı S2, 2026-09-11): sonuca `structuredContent` eklendiğinde CLI
    kararı hiç okumadan araç hatası veriyor —
    `Permission prompt tool returned an invalid result. Expected a single text
    block param with type="text" and a string text value.` — ve komut ne
    koşuyor ne de `permission_denials`a düşüyor (yani ret bile kaybolur).
    İleri uyum için ikinci biçimi taşımak bu sürümde YASAK.

    `pending_id` yalnızca Entropy'nin teşhisi içindir, karar alanlarına karışmaz.
    """
    payload = {k: v for k, v in decision.items() if k != "pending_id"}
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": False,
    }


# --- JSON-RPC ----------------------------------------------------------------


def handle_message(
    message: Dict[str, Any],
    queue=None,
    timeout_s: Optional[float] = None,
    cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Tek bir JSON-RPC iletisini işler. Bildirimlerde `None` döner."""
    method = str(message.get("method") or "")
    msg_id = message.get("id")

    if msg_id is None:
        # Bildirim (`notifications/initialized` gibi): yanıt YASAK.
        return None

    def ok(result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    if method == "initialize":
        return ok(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        )
    if method == "tools/list":
        return ok({"tools": [tool_definition()]})
    if method == "ping":
        return ok({})
    if method == "tools/call":
        params = message.get("params") or {}
        name = str(params.get("name") or "")
        if name not in (TOOL_NAME, PERMISSION_TOOL):
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": f"Bilinmeyen araç: {name}"},
            }
        arguments = params.get("arguments") or {}
        try:
            decision = decide(arguments, queue=queue, timeout_s=timeout_s, cache=cache)
        except Exception as exc:  # karar alınamadı → güvenli taraf: reddet
            logger.warning("İzin kararı alınamadı", exc_info=True)
            decision = {"behavior": "deny", "message": f"Onay alınamadı: {exc}"}
        return ok(_tool_result(decision))
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Bilinmeyen metot: {method}"},
    }


def serve(
    stdin: Optional[IO[str]] = None,
    stdout: Optional[IO[str]] = None,
    queue=None,
    timeout_s: Optional[float] = None,
) -> int:
    """NDJSON döngüsü. Akış kapanınca 0 ile döner."""
    src = stdin if stdin is not None else sys.stdin
    dst = stdout if stdout is not None else sys.stdout
    cache: Dict[str, Dict[str, Any]] = {}
    for raw in src:
        line = (raw or "").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except Exception:
            logger.debug("Ayrıştırılamayan satır atlandı", exc_info=True)
            continue
        if not isinstance(message, dict):
            continue
        response = handle_message(
            message, queue=queue, timeout_s=timeout_s, cache=cache
        )
        if response is None:
            continue
        dst.write(json.dumps(response, ensure_ascii=False) + "\n")
        try:
            dst.flush()
        except Exception:
            pass
    return 0


# --- CLI'ya tanıtma ----------------------------------------------------------


def entry_point() -> List[str]:
    """
    Sunucuyu başlatan argv.

    Kaynaktan koşarken `python -m entropy.core.permission_mcp_main`; paketlenmiş
    sürümde `sys.executable` zaten `EntropyAI.exe` olduğu için AYNI ikili özel
    bir bayrakla çağrılır (`run_entropy.py` bu bayrağı argv'nin başında görür ve
    Qt'yi hiç kurmadan sunucuya sapar).
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--entropy-mcp-permission"]
    return [sys.executable, "-m", "entropy.core.permission_mcp_main"]


def mcp_config_payload(timeout_s: Optional[float] = None) -> Dict[str, Any]:
    """`--mcp-config` dosyasının içeriği (tek sunucu: `entropy`)."""
    argv = entry_point()
    env = {
        # Karar dosyaları uygulamanın kullandığı kökten okunur; çocuk süreç
        # kökü kendi başına tahmin etmeye çalışmaz.
        "ENTROPY_DATA_ROOT": str(_data_root()),
        # Çocuk süreçte Qt YOK: kuyruk sinyal yaymaya çalışmasın.
        "ENTROPY_PENDING_NO_BUS": "1",
        TIMEOUT_ENV: str(int(timeout_s or _timeout_from_env())),
    }
    if not getattr(sys, "frozen", False):
        # Kaynaktan koşumda `src/` yolu çocuğa da gerekir.
        src = Path(__file__).resolve().parents[2]
        existing = os.environ.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{src}{os.pathsep}{existing}" if existing else str(src)
    return {
        "mcpServers": {
            SERVER_NAME: {
                "type": "stdio",
                "command": argv[0],
                "args": argv[1:],
                "env": env,
            }
        }
    }


def _data_root() -> Path:
    try:
        from entropy.core.paths import data_root

        return data_root()
    except Exception:
        return Path.home() / ".entropy"


def write_mcp_config(path: Optional[Path | str] = None,
                     timeout_s: Optional[float] = None) -> Path:
    """Yapılandırmayı diske yazar ve yolunu döndürür (köprü bunu argv'ye koyar)."""
    target = (
        Path(path)
        if path is not None
        else _data_root() / "mcp" / "permission_mcp.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(mcp_config_payload(timeout_s), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target
