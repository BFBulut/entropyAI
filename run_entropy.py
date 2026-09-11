"""Entry point for PyInstaller executable build."""

import os
import sys
from pathlib import Path

# Add src directory to python path
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


def _run_permission_mcp() -> int:
    """
    Paketlenmiş ikilinin ikinci kimliği (Faz 14-B): izin MCP sunucusu.

    `sys.executable` donmuş sürümde `EntropyAI.exe`'dir, yani izin sunucusunu
    "python -m …" ile başlatmak mümkün değil; CLI aynı ikiliyi bu bayrakla
    çağırır. Qt HİÇ kurulmaz: `entropy.main` içe aktarılmadan sapılır.
    """
    from entropy.core.permission_mcp_main import main as mcp_main

    return mcp_main()


if __name__ == "__main__":
    if "--entropy-mcp-permission" in sys.argv[1:]:
        sys.exit(_run_permission_mcp())
    from entropy.main import main

    sys.exit(main())
