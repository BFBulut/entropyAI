"""Core configuration and settings for Entropy AI."""

from pathlib import Path
from pydantic import BaseModel, Field

class EntropyConfig(BaseModel):
    app_name: str = "Entropy AI"
    obsidian_vault_path: Path = Path(r"C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault")
    default_project_path: Path = Path(r"c:\EntropiAI")
    default_mode: str = "floating"  # "floating", "zen", "chat"
    autostart_enabled: bool = True
    context_window_size: int = 20
    model_fallback_name: str = "[Model: Unknown]"

config = EntropyConfig()
