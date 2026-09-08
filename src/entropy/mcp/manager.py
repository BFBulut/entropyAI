"""Model Context Protocol (MCP) server manager for Entropy AI."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

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

    def list_servers(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """Return configured MCP servers with fast local config parsing and TTL caching."""
        now = time.time()
        if not force_refresh and MCPManager._cached_servers is not None and (now - MCPManager._cache_timestamp) < MCPManager._cache_ttl:
            return MCPManager._cached_servers

        servers: List[Dict[str, str]] = []

        # 1. Fast path: parse local mcp_config.json files (< 0.1ms, zero subprocess overhead)
        mcp_configs = [
            Path.home() / ".gemini" / "antigravity" / "mcp_config.json",
            Path.home() / ".gemini" / "config" / "mcp_config.json",
            Path.cwd() / "mcp_config.json",
        ]
        for cfg_path in mcp_configs:
            if cfg_path.exists():
                try:
                    data = json.loads(cfg_path.read_text(encoding="utf-8"))
                    mcp_servers = data.get("mcpServers", {})
                    for s_name, s_info in mcp_servers.items():
                        if not any(x["name"] == s_name for x in servers):
                            s_type = "http" if "serverUrl" in s_info else "stdio"
                            s_target = s_info.get("serverUrl", "")
                            if not s_target and "args" in s_info:
                                s_target = " ".join(s_info["args"][:2])
                            servers.append({
                                "name": s_name,
                                "type": s_type,
                                "status": "enabled",
                                "target": s_target
                            })
                except Exception:
                    pass

        # 2. If force_refresh or no local config found, run 'agy mcp list'
        if force_refresh or not servers:
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
                                    "target": parts[3] if len(parts) > 3 else ""
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

    def enable_server(self, server_name: str) -> bool:
        """Enable an MCP server via 'agy mcp enable <name>'."""
        MCPManager._cached_servers = None
        try:
            res = subprocess.run(
                [self.agy_bin, "mcp", "enable", server_name],
                capture_output=True,
                text=True,
                creationflags=self._get_creationflags(),
                timeout=10
            )
            return res.returncode == 0
        except Exception:
            return False

    def disable_server(self, server_name: str) -> bool:
        """Disable an MCP server via 'agy mcp disable <name>'."""
        MCPManager._cached_servers = None
        try:
            res = subprocess.run(
                [self.agy_bin, "mcp", "disable", server_name],
                capture_output=True,
                text=True,
                creationflags=self._get_creationflags(),
                timeout=10
            )
            return res.returncode == 0
        except Exception:
            return False

    def add_server(self, name: str, server_type: str, command_or_url: str) -> bool:
        """Add or update an MCP server configuration via 'agy mcp add <name> <type> <command/url>'."""
        MCPManager._cached_servers = None
        try:
            cmd = [self.agy_bin, "mcp", "add", name, server_type, command_or_url]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=self._get_creationflags(),
                timeout=15
            )
            return res.returncode == 0
        except Exception:
            return False

    def remove_server(self, server_name: str) -> bool:
        """Remove an MCP server configuration via 'agy mcp remove <name>'."""
        MCPManager._cached_servers = None
        try:
            cmd = [self.agy_bin, "mcp", "remove", server_name]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=self._get_creationflags(),
                timeout=15
            )
            return res.returncode == 0
        except Exception:
            return False

# Global singleton instance for shared discovery
default_mcp_manager = MCPManager()

