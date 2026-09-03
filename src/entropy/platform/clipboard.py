"""Multimodal clipboard image handler for Entropy AI."""

import hashlib
import time
from pathlib import Path
from typing import Optional, Tuple
from PySide6.QtGui import QClipboard, QImage, QGuiApplication

class ClipboardImageHandler:
    """Detects, saves, and stages images pasted from Windows clipboard (Ctrl+V)."""

    def __init__(self, staging_dir: Optional[Path] = None):
        if staging_dir is None:
            entropy_home = Path.home() / ".entropy"
            self.staging_dir = entropy_home / "staging" / "images"
        else:
            self.staging_dir = Path(staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def has_clipboard_image(self) -> bool:
        """Check whether clipboard currently contains an image bitmap."""
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()
        return mime_data.hasImage() if mime_data else False

    def save_clipboard_image(self) -> Optional[Tuple[str, int, int]]:
        """
        Extract image from clipboard, save to staging as PNG, and return
        (file_path, width, height) or None if no image present.
        """
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()
        if not mime_data or not mime_data.hasImage():
            return None

        image = clipboard.image()
        if image.isNull():
            return None

        # Generate unique hash filename
        timestamp = int(time.time() * 1000)
        h = hashlib.md5(f"img_{timestamp}_{image.width()}_{image.height()}".encode("utf-8")).hexdigest()[:12]
        filename = f"clip_{timestamp}_{h}.png"
        target_path = self.staging_dir / filename

        success = image.save(str(target_path), "PNG")
        if success:
            return str(target_path), image.width(), image.height()
        return None
