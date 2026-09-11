"""
İzin MCP sunucusunun giriş noktası — `python -m entropy.core.permission_mcp_main`.

Ayrı bir modül: süreç CLI tarafından doğrulur ve stdout'u JSON-RPC kanalıdır.
Buraya Qt, arayüz ya da beyin İTHAL EDİLMEZ (kanal kirlenirse el sıkışma ölür,
üstelik çocuk süreç başına PySide6 yüklemek saniyeler yerdi).
"""

from __future__ import annotations

import sys


def main(argv=None) -> int:
    # Yazdırma kanalı sözleşmedir: satır tamponlu ve UTF-8 olmalı.
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from entropy.core.permission_server import serve

    return serve()


if __name__ == "__main__":
    sys.exit(main())
