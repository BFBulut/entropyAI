"""Core configuration and settings for Entropy AI."""

from typing import List
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
    selected_model: str = "gemini-2.5-pro"
    available_models: List[str] = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-3.1-pro",
        "claude-3-7-sonnet",
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
    ]

config = EntropyConfig()
