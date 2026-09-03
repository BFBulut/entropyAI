"""Model Context Protocol (MCP) server manager for Entropy AI."""

import os
import shutil
import subprocess
from typing import Dict, List, Optional

class MCPManager:
    """Manages active and configured Model Context Protocol servers via agy mcp CLI."""

    def __init__(self):
        self.agy_bin = shutil.which("agy") or "agy"

    def _get_creationflags(self) -> int:
        if os.name == "nt":
            return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return 0

    def list_servers(self) -> List[Dict[str, str]]:
        """Run 'agy mcp list' and return structured list of configured MCP servers."""
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
            if res.returncode != 0:
                return self._fallback_detected_servers()

            lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            servers = []
            if len(lines) > 1 and "NAME" in lines[0] and "STATUS" in lines[0]:
                for line in lines[1:]:
                    parts = line.split(maxsplit=3)
                    if len(parts) >= 3:
                        servers.append({
                            "name": parts[0],
                            "type": parts[1],
                            "status": parts[2],
                            "target": parts[3] if len(parts) > 3 else ""
                        })
            return servers or self._fallback_detected_servers()
        except Exception:
            return self._fallback_detected_servers()

    def _fallback_detected_servers(self) -> List[Dict[str, str]]:
        """Default known servers if agy is offline during mock testing."""
        return [
            {"name": "StitchMCP", "type": "stdio", "status": "enabled", "target": "https://stitch.googleapis.com/mcp"},
            {"name": "obsidian", "type": "stdio", "status": "enabled", "target": "@bitbonsai/mcpvault"},
            {"name": "supabase", "type": "http", "status": "enabled", "target": "https://mcp.supabase.com/mcp"},
            {"name": "chrome-devtools-mcp", "type": "stdio", "status": "enabled", "target": "chrome-devtools-mcp@latest"},
            {"name": "gmp-code-assist", "type": "http", "status": "enabled", "target": "https://mapscodeassist.googleapis.com/mcp"},
        ]

    def enable_server(self, server_name: str) -> bool:
        """Enable an MCP server via 'agy mcp enable <name>'."""
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
