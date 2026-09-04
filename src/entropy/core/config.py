"""Core configuration and settings for Entropy AI with persistence."""

import json
from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel, Field

SETTINGS_FILE = Path(r"C:\EntropiAI\.entropy\settings.json")
CHAT_HISTORY_FILE = Path(r"C:\EntropiAI\.entropy\chat_history.json")

class EntropyConfig(BaseModel):
    app_name: str = "Entropy AI"
    obsidian_vault_path: Path = Path(r"C:\Users\batu_\OneDrive\Belgeler\Obsidian Vault")
    default_project_path: Path = Path(r"c:\EntropiAI")
    default_mode: str = "floating"  # "floating", "zen", "chat"
    autostart_enabled: bool = True
    context_window_size: int = 20
    model_fallback_name: str = "[Model: Unknown]"
    selected_model: str = "gemini-3.1-pro-high"
    last_conversation_id: Optional[str] = None
    last_cumulative_usage: dict = Field(
        default_factory=lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cache_read_tokens": 0,
            "total_tokens": 0,
        }
    )
    available_models: List[str] = [
        "gemini-3.1-pro-high",
        "gemini-3.1-pro-low",
        "gemini-3.8-flash-high",
        "gemini-3.8-flash-medium",
        "gemini-3.8-flash-low",
        "gemini-3.7-flash-high",
        "gemini-3.7-flash-medium",
        "gemini-3.7-flash-low",
        "gemini-3.6-flash-high",
        "claude-sonnet-4-6",
        "claude-opus-4-6-thinking",
        "gpt-oss-120b-medium",
    ]

    def save_settings(self):
        """Persist user preferences to disk."""
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "selected_model": self.selected_model,
                "default_mode": self.default_mode,
                "autostart_enabled": self.autostart_enabled,
                "last_conversation_id": self.last_conversation_id,
                "last_cumulative_usage": self.last_cumulative_usage,
            }
            SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_settings(self):
        """Load persistent preferences from disk."""
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if "selected_model" in data and data["selected_model"]:
                    self.selected_model = data["selected_model"]
                if "default_mode" in data and data["default_mode"]:
                    self.default_mode = data["default_mode"]
                if "autostart_enabled" in data:
                    self.autostart_enabled = data["autostart_enabled"]
                if "last_conversation_id" in data:
                    self.last_conversation_id = data["last_conversation_id"]
                if "last_cumulative_usage" in data and isinstance(data["last_cumulative_usage"], dict):
                    self.last_cumulative_usage = data["last_cumulative_usage"]
        except Exception:
            pass

config = EntropyConfig()
config.load_settings()
