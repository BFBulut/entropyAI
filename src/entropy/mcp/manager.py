"""Model Context Protocol (MCP) server manager for Entropy AI."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- agy'nin MCP yapılandırması ---------------------------------------------
#
# Yerel kurulumdan ve agy.EXE içindeki belge/sürüm-notu dizgelerinden doğrulandı:
#   "*   **Global Configuration**: `~/.gemini/config/mcp_config.json` (applies to all"
#   "- Fixed custom MCP server disabling via the TUI. Resolved a directory path
#      mismatch where pressing the `[Disable]` button wrote to the legacy
#      `mcp_config.json` path instead of the migrated `config/mcp_config.json`."
# Yani birincil (güncel) hedef ~/.gemini/config/mcp_config.json; eski kurulumlarda
# ~/.gemini/antigravity/mcp_config.json hâlâ okunuyor. İkisi de duruyorsa yazma
# işlemi her ikisine de yansıtılır — hangi agy sürümü okursa okusun aynı listeyi
# görsün diye.
#
# Sunucu kaydının şeması (agy.EXE'deki struct etiketlerinden):
#   command / args / env            -> stdio sunucu
#   serverUrl (ya da url)           -> http sunucu
#   disabled: true                  -> sunucu pasif
#   enabledTools / disabledTools / timeoutSeconds / tools.eager -> korunur
# Doğrulama kuralları da aynı ikiliden:
#   "MCP server %q must have either command or serverUrl"
#   "MCP server %q cannot have both command and serverUrl"
PRIMARY_MCP_CONFIG = Path.home() / ".gemini" / "config" / "mcp_config.json"
LEGACY_MCP_CONFIG = Path.home() / ".gemini" / "antigravity" / "mcp_config.json"

# Sunucu adı dizin/komut adı gibi kullanılıyor; boşluk ve ayraçlara izin verilmez.
SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")


def _strip_json_comments(text: str) -> str:
    """`//` ve `/* */` yorumlarını dizge içeriğine dokunmadan ayıklar."""
    out: List[str] = []
    i, n = 0, len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == chr(92):  # ters bölü: kaçış başlangıcı
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                while i < n and text[i] not in ("\r", "\n"):
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def loads_relaxed(text: str) -> Dict[str, Any]:
    """
    mcp_config.json'u okur; agy gibi yorum ve sondaki fazladan virgülü hoş görür.

    Önce katı ayrıştırma denenir: geçerli bir dosyada gevşetme uygulanmaz, böylece
    dizge içindeki ',}' gibi diziler yanlışlıkla bozulmaz.
    """
    try:
        return json.loads(text)
    except Exception:
        pass
    cleaned = _strip_json_comments(text)
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return json.loads(cleaned)


class MCPManager:
    """Manages active and configured Model Context Protocol servers via agy mcp CLI."""

    _cached_servers: Optional[List[Dict[str, str]]] = None
    _cache_timestamp: float = 0.0
    _cache_ttl: float = 4.0
    _custom_tools: Dict[str, List[Dict[str, str]]] = {}

    DEFAULT_TOOLS: Dict[str, List[Dict[str, str]]] = {
        "obsidian": [
            {"name": "search_notes", "description": "Obsidian notlarında tam metin veya başlık araması yapar"},
            {"name": "read_note", "description": "Belirli bir Obsidian Markdown notunu okur"},
            {"name": "create_note", "description": "Obsidian kasasına yeni not veya zettelkasten ekler"},
        ],
        "supabase": [
            {"name": "execute_sql", "description": "Supabase veritabanında SQL sorgusu çalıştırır"},
            {"name": "vector_search", "description": "pgvector koleksiyonunda bilişsel semantik arama yapar"},
            {"name": "list_tables", "description": "Veritabanı tablolarını ve şemalarını listeler"},
        ],
        "chrome-devtools-mcp": [
            {"name": "navigate", "description": "Belirtilen web URL'sine gider ve DOM yapısını çeker"},
            {"name": "screenshot", "description": "Aktif web sayfasının tam ekran görüntüsünü alır"},
            {"name": "evaluate_script", "description": "Tarayıcı konsolunda JavaScript kodu yürütür"},
        ],
        "gmp-code-assist": [
            {"name": "code_assist", "description": "Google Maps Platform API kodları ve harita mimarisi üretir"},
            {"name": "places_search", "description": "Google Places API ile konum ve mekan sorguları yapar"},
        ],
        "StitchMCP": [
            {"name": "design_screen", "description": "Google Stitch tasarım sistemi ile arayüz bileşenleri üretir"},
            {"name": "export_html", "description": "Stitch tasarımlarını temiz HTML/CSS koduna dönüştürür"},
        ],
    }

    def __init__(self):
        self.agy_bin = shutil.which("agy") or "agy"

    def _get_creationflags(self) -> int:
        if os.name == "nt":
            return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return 0

    # ------------------------------------------------------------------
    # Yapılandırma dosyası konumu, okuma ve (atomik) yazma
    # ------------------------------------------------------------------
    def config_paths(self) -> List[Path]:
        """Okunacak tüm mcp_config.json yolları, öncelik sırasıyla."""
        return [
            PRIMARY_MCP_CONFIG,
            LEGACY_MCP_CONFIG,
            Path.cwd() / "mcp_config.json",
        ]

    def write_config_paths(self) -> List[Path]:
        """
        Yazılacak yollar: birincil dosya her zaman, eski dosya yalnızca zaten varsa.

        Eski dosya körü körüne oluşturulmaz; ama duruyorsa güncel bırakılır,
        yoksa eski bir agy sürümü kaldırılmış bir sunucuyu görmeye devam ederdi.
        """
        paths = [PRIMARY_MCP_CONFIG]
        if LEGACY_MCP_CONFIG.exists():
            paths.append(LEGACY_MCP_CONFIG)
        return paths

    def read_config(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """Bir mcp_config.json'u sözlük olarak döndürür (yoksa boş iskelet)."""
        target = Path(path) if path else self.write_config_paths()[0]
        if not target.exists():
            return {"mcpServers": {}}
        try:
            data = loads_relaxed(target.read_text(encoding="utf-8"))
        except Exception:
            return {"mcpServers": {}}
        if not isinstance(data, dict):
            return {"mcpServers": {}}
        if not isinstance(data.get("mcpServers"), dict):
            data["mcpServers"] = {}
        return data

    def _write_config(self, data: Dict[str, Any], path: Path) -> bool:
        """
        Yapılandırmayı yedekleyip atomik olarak yazar.

        Yarıda kesilen bir yazma dosyayı bozarsa agy hiçbir MCP sunucusu
        göremez; bu yüzden geçici dosyaya yazılıp os.replace ile takas edilir
        ve önceki içerik `<ad>.bak` olarak saklanır.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                try:
                    shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
                except Exception:
                    pass
            fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".mcp_config_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2, ensure_ascii=False)
                    fh.write("\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_name, path)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
            return True
        except Exception:
            return False

    def _mutate_config(self, mutator) -> bool:
        """
        Yazılabilir tüm yapılandırma dosyalarına aynı değişikliği uygular.

        `mutator(servers: dict) -> bool` sözlüğü yerinde değiştirir; False
        dönerse (örn. sunucu yok) dosyaya dokunulmaz.
        """
        ok = False
        for path in self.write_config_paths():
            data = self.read_config(path)
            servers = data.setdefault("mcpServers", {})
            try:
                changed = mutator(servers)
            except ValueError:
                raise
            if not changed:
                continue
            if self._write_config(data, path):
                ok = True
        if ok:
            self.invalidate_cache()
            self._notify_config_changed()
        return ok

    def invalidate_cache(self) -> None:
        MCPManager._cached_servers = None
        MCPManager._cache_timestamp = 0.0

    def _notify_config_changed(self) -> None:
        """
        MCP listesinin değiştiğini uygulamaya duyurur.

        Köprünün ayrıca bir manifest tazelemesi gerekmiyor: her istem yeni bir
        `agy` süreci başlattığı için mcp_config.json bir sonraki turda zaten
        yeniden okunuyor. Sinyal arayüz rozetleri ve panelleri içindir.
        """
        try:
            from entropy.core.event_bus import bus

            bus.mcp_servers_updated.emit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Listeleme
    # ------------------------------------------------------------------
    @staticmethod
    def _describe_entry(name: str, info: Dict[str, Any], source: Path) -> Dict[str, Any]:
        url = info.get("serverUrl") or info.get("url") or ""
        command = info.get("command") or ""
        args = info.get("args") or []
        if not isinstance(args, list):
            args = [str(args)]
        env = info.get("env") if isinstance(info.get("env"), dict) else {}
        s_type = "http" if url else "stdio"
        target = url if url else " ".join([command] + [str(a) for a in args]).strip()
        return {
            "name": name,
            "type": s_type,
            "status": "disabled" if info.get("disabled") else "enabled",
            "target": target,
            "command": command,
            "args": [str(a) for a in args],
            "env": {str(k): str(v) for k, v in env.items()},
            "url": url,
            "config_path": str(source),
        }

    def list_servers(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """Return configured MCP servers with fast local config parsing and TTL caching."""
        now = time.time()
        if not force_refresh and MCPManager._cached_servers is not None and (now - MCPManager._cache_timestamp) < MCPManager._cache_ttl:
            return MCPManager._cached_servers

        servers: List[Dict[str, Any]] = []

        # 1. Fast path: parse local mcp_config.json files (< 0.1ms, zero subprocess overhead)
        for cfg_path in self.config_paths():
            if not cfg_path.exists():
                continue
            data = self.read_config(cfg_path)
            for s_name, s_info in data.get("mcpServers", {}).items():
                if not isinstance(s_info, dict):
                    continue
                if any(x["name"] == s_name for x in servers):
                    continue
                servers.append(self._describe_entry(s_name, s_info, cfg_path))

        # 2. Yapılandırma hiç bulunamadıysa 'agy mcp list' ile son bir deneme.
        #    (force_refresh burada CLI'ı tetiklemez: her yenilemede 10 sn'ye kadar
        #     bloklayan bir alt süreç arayüzü dondururdu; dosya zaten tek kaynak.)
        if not servers:
            try:
                res = subprocess.run(
                    [self.agy_bin, "mcp", "list"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=self._get_creationflags(),
                    timeout=10
                )
                if res.returncode == 0:
                    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                    if len(lines) > 1 and "NAME" in lines[0] and "STATUS" in lines[0]:
                        cli_servers = []
                        for line in lines[1:]:
                            parts = line.split(maxsplit=3)
                            if len(parts) >= 3:
                                cli_servers.append({
                                    "name": parts[0],
                                    "type": parts[1],
                                    "status": parts[2],
                                    "target": parts[3] if len(parts) > 3 else "",
                                    "command": "",
                                    "args": [],
                                    "env": {},
                                    "url": "",
                                    "config_path": "",
                                })
                        if cli_servers:
                            servers = cli_servers
            except Exception:
                pass

        if not servers:
            servers = self._fallback_detected_servers()

        MCPManager._cached_servers = servers
        MCPManager._cache_timestamp = now
        return servers

    def get_server(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Tek bir sunucunun tam kaydını döndürür (düzenleme formu için)."""
        for s in self.list_servers():
            if s.get("name") == server_name:
                return s
        return None

    def _fallback_detected_servers(self) -> List[Dict[str, str]]:
        """Default known servers if agy is offline during mock testing."""
        return [
            {"name": "StitchMCP", "type": "stdio", "status": "enabled", "target": "https://stitch.googleapis.com/mcp"},
            {"name": "obsidian", "type": "stdio", "status": "enabled", "target": "@bitbonsai/mcpvault"},
            {"name": "supabase", "type": "http", "status": "enabled", "target": "https://mcp.supabase.com/mcp"},
            {"name": "chrome-devtools-mcp", "type": "stdio", "status": "enabled", "target": "chrome-devtools-mcp@latest"},
            {"name": "gmp-code-assist", "type": "http", "status": "enabled", "target": "https://mapscodeassist.googleapis.com/mcp"},
        ]

    def list_tools(self, server_name: Optional[str] = None) -> List[Dict[str, str]]:
        """List available tools for a specific MCP server or all servers."""
        all_tools = []
        target_servers = [server_name] if server_name else [s["name"] for s in self.list_servers()]
        for s in target_servers:
            # Check default known tools
            defaults = self.DEFAULT_TOOLS.get(s, [])
            for t in defaults:
                all_tools.append({
                    "server": s,
                    "name": t["name"],
                    "description": t.get("description", ""),
                })
            # Check custom registered tools
            customs = MCPManager._custom_tools.get(s, [])
            for t in customs:
                if not any(x["name"] == t["name"] and x["server"] == s for x in all_tools):
                    all_tools.append({
                        "server": s,
                        "name": t["name"],
                        "description": t.get("description", ""),
                    })
        return all_tools

    def register_tool(self, server_name: str, tool_name: str, description: str):
        """Register a custom or dynamically synthesized tool for an MCP server."""
        if server_name not in MCPManager._custom_tools:
            MCPManager._custom_tools[server_name] = []
        # Update if existing, or append
        existing = [t for t in MCPManager._custom_tools[server_name] if t["name"] == tool_name]
        if existing:
            existing[0]["description"] = description
        else:
            MCPManager._custom_tools[server_name].append({
                "name": tool_name,
                "description": description
            })

    def get_mcp_commands(self) -> List[Dict[str, str]]:
        """Return slash commands for MCP servers and their sub-tools."""
        commands = []
        servers = self.list_servers()
        for s in servers:
            s_name = s.get("name", "")
            s_type = s.get("type", "stdio")
            s_target = s.get("target", "")
            status = s.get("status", "enabled")

            # Server-level command
            server_cmd = f"/{s_name}"
            commands.append({
                "name": server_cmd,
                "description": f"MCP Sunucusu ({s_type}, {status}): {s_target}" if s_target else f"MCP Sunucusu ({s_type})",
                "category": "mcp",
                "badge": "🔌 MCP",
                "server": s_name,
            })

            # Sub-tools commands
            tools = self.list_tools(s_name)
            for t in tools:
                tool_cmd = f"/{s_name}:{t['name']}"
                commands.append({
                    "name": tool_cmd,
                    "description": t["description"] or f"{s_name} alt aracı",
                    "category": "mcp_tool",
                    "badge": "🔌 MCP ARAÇ",
                    "server": s_name,
                    "tool": t["name"],
                })
        return commands

    # ------------------------------------------------------------------
    # Ekle / güncelle / kaldır / etkinleştir
    # ------------------------------------------------------------------
    @staticmethod
    def build_server_entry(
        server_type: str,
        command_or_url: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Kullanıcı girdisinden geçerli bir mcp_config.json kaydı üretir.

        http/https ile başlayan bir hedef otomatik olarak uzak sunucu sayılır
        (agy da öyle yapıyor: "http/https URLs are detected automatically").
        stdio'da tek satırlık komut ("npx -y paket") komut + argümanlara ayrılır.
        """
        target = (command_or_url or "").strip()
        if not target:
            raise ValueError("Komut veya URL boş olamaz.")

        is_url = target.lower().startswith(("http://", "https://"))
        if (server_type or "").lower() in ("http", "sse", "url", "remote") or is_url:
            if not is_url:
                raise ValueError("HTTP sunucusu için geçerli bir http(s) URL'si gerekir.")
            return {"serverUrl": target}

        parts = [p for p in target.split() if p]
        entry: Dict[str, Any] = {"command": parts[0]}
        extra = list(args) if args else []
        tail = parts[1:] + [str(a) for a in extra if str(a).strip()]
        if tail:
            entry["args"] = tail
        if env:
            entry["env"] = {str(k): str(v) for k, v in env.items() if str(k).strip()}
        return entry

    @staticmethod
    def validate_entry(name: str, entry: Dict[str, Any]) -> None:
        """agy'nin uyguladığı kuralları yazmadan önce burada uygular."""
        if not SERVER_NAME_RE.match(name or ""):
            raise ValueError(
                "Sunucu adı harf/rakam ile başlamalı; yalnızca harf, rakam, '_', '-', '.' içerebilir."
            )
        has_cmd = bool(entry.get("command"))
        has_url = bool(entry.get("serverUrl") or entry.get("url"))
        if has_cmd and has_url:
            raise ValueError(f"'{name}' hem command hem serverUrl içeremez.")
        if not has_cmd and not has_url:
            raise ValueError(f"'{name}' için command ya da serverUrl gerekli.")

    def add_server(
        self,
        name: str,
        server_type: str,
        command_or_url: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        overwrite: bool = True,
    ) -> bool:
        """Add or update an MCP server directly in agy's mcp_config.json."""
        name = (name or "").strip()
        entry = self.build_server_entry(server_type, command_or_url, args=args, env=env)
        self.validate_entry(name, entry)

        def _mutate(servers: Dict[str, Any]) -> bool:
            if name in servers and not overwrite:
                raise ValueError(f"'{name}' zaten kayıtlı.")
            servers[name] = entry
            return True

        return self._mutate_config(_mutate)

    def update_server(
        self,
        name: str,
        server_type: Optional[str] = None,
        command_or_url: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        new_name: Optional[str] = None,
    ) -> bool:
        """
        Var olan bir sunucuyu düzenler; tanımadığı alanları korur.

        agy sürüm notu: "/mcp paneli sunucuyu açıp kapatırken `enabledTools`,
        `timeoutSeconds`, `url` ve `tools.eager` alanlarını düşürüyordu; artık
        tanımadığı her alanı koruyor." Aynı sözleşmeye uyuyoruz: yalnızca
        bağlantı alanları (command/args/env/serverUrl) değiştirilir.
        """
        name = (name or "").strip()
        target_name = (new_name or name).strip()

        def _mutate(servers: Dict[str, Any]) -> bool:
            existing = servers.get(name)
            if not isinstance(existing, dict):
                return False
            merged = dict(existing)
            if command_or_url is not None:
                fresh = self.build_server_entry(
                    server_type or ("http" if (existing.get("serverUrl") or existing.get("url")) else "stdio"),
                    command_or_url,
                    args=args,
                    env=env if env is not None else existing.get("env"),
                )
                for key in ("command", "args", "env", "serverUrl", "url"):
                    merged.pop(key, None)
                merged.update(fresh)
            else:
                if args is not None:
                    merged["args"] = [str(a) for a in args]
                if env is not None:
                    merged["env"] = {str(k): str(v) for k, v in env.items()}
            self.validate_entry(target_name, merged)
            if target_name != name:
                servers.pop(name, None)
            servers[target_name] = merged
            return True

        return self._mutate_config(_mutate)

    def remove_server(self, server_name: str) -> bool:
        """Remove an MCP server from agy's mcp_config.json."""
        server_name = (server_name or "").strip()

        def _mutate(servers: Dict[str, Any]) -> bool:
            return servers.pop(server_name, None) is not None

        return self._mutate_config(_mutate)

    def toggle_server(self, server_name: str, enabled: bool) -> bool:
        """
        Sunucuyu `disabled` bayrağıyla etkin/pasif yapar.

        agy'nin sunucu kaydında bu alan `disabled` adıyla tutuluyor
        (agy.EXE: 'Disabled ... json:"disabled,omitempty..."'). Etkinleştirirken
        bayrak silinir; kalan alanlar olduğu gibi bırakılır.
        """
        server_name = (server_name or "").strip()

        def _mutate(servers: Dict[str, Any]) -> bool:
            entry = servers.get(server_name)
            if not isinstance(entry, dict):
                return False
            if enabled:
                if "disabled" not in entry:
                    return False
                entry.pop("disabled", None)
            else:
                if entry.get("disabled") is True:
                    return False
                entry["disabled"] = True
            return True

        # Zaten istenen durumdaysa dosyaya dokunulmaz ama çağrı başarılıdır.
        # Kontrol önbelleğe değil dosyaya bakar: TTL'li liste önbelleği bir
        # önceki okumadan kalmış olabilir ve "sunucu yok" yanıtı üretirdi.
        changed = self._mutate_config(_mutate)
        if changed:
            return True
        for path in self.write_config_paths():
            entry = self.read_config(path).get("mcpServers", {}).get(server_name)
            if isinstance(entry, dict):
                return (not entry.get("disabled")) == bool(enabled)
        return False

    def enable_server(self, server_name: str) -> bool:
        """Enable an MCP server (mcp_config.json içindeki `disabled` bayrağını kaldırır)."""
        return self.toggle_server(server_name, True)

    def disable_server(self, server_name: str) -> bool:
        """Disable an MCP server (mcp_config.json içine `disabled: true` yazar)."""
        return self.toggle_server(server_name, False)


# Global singleton instance for shared discovery
default_mcp_manager = MCPManager()
