"""Entry point for PyInstaller executable build."""

import os
import sys
from pathlib import Path

# Add src directory to python path
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from entropy.main import main

if __name__ == "__main__":
    sys.exit(main())
