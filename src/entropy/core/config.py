"""Core configuration and settings for Entropy AI with persistence."""

import json
import os
import sys
from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel, Field


def _resolve_app_root() -> Path:
    """
    Uygulama kökünü verir.

    Kaynaktan çalışırken src/entropy/core/config.py -> <repo>; PyInstaller ile
    paketlendiğinde kaynak ağacı bulunmadığından .exe'nin bulunduğu dizin.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


APP_ROOT = _resolve_app_root()


def _resolve_state_dir() -> Path:
    """
    Ayarların ve sohbet geçmişinin yazılacağı dizini belirler.

    Öncelik sırası:
      1. ENTROPY_HOME ortam değişkeni (açık geçersiz kılma)
      2. Uygulama kökündeki mevcut .entropy/ (kurulu sürümlerin verisi burada;
         taşımadan çalışmaya devam etsin diye korunur)
      3. %LOCALAPPDATA%\\EntropyAI (Windows) veya ~/.entropy (diğer platformlar)

    Sabit bir C:\\EntropiAI yoluna bağlanmak, paketlenmiş .exe'yi başka bir
    makinede ya da proje taşındığında kullanılamaz hale getiriyordu.
    """
    env_home = os.environ.get("ENTROPY_HOME")
    if env_home:
        return Path(env_home).expanduser()

    legacy_dir = APP_ROOT / ".entropy"
    if legacy_dir.is_dir():
        return legacy_dir

    # Paketlenmiş exe genellikle deponun içinden çalışır (<repo>/dist/<ad>/ veya
    # <repo>/dist_check/<ad>/). Orada .entropy olmadığı için LOCALAPPDATA'ya
    # düşmek, dev ağacıyla exe'nin ayarlarını, sohbet geçmişini ve rapor
    # indeksini ikiye bölüyordu (exe'de "/distill" hiç kaynak bulamıyordu).
    # Birkaç üst dizinde mevcut bir .entropy varsa o kullanılır.
    if getattr(sys, "frozen", False):
        for parent in list(APP_ROOT.parents)[:3]:
            candidate = parent / ".entropy"
            if candidate.is_dir():
                return candidate

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "EntropyAI"
    return Path.home() / ".entropy"


def _default_obsidian_vault() -> Path:
    """
    Varsayılan Obsidian kasası yolunu kullanıcının ev dizininden türetir.

    ENTROPY_VAULT_PATH ile geçersiz kılınabilir. Bilinen OneDrive/Belgeler
    yerleşimleri sırayla denenir; hiçbiri yoksa ~/Obsidian Vault döner.
    """
    env_vault = os.environ.get("ENTROPY_VAULT_PATH")
    if env_vault:
        return Path(env_vault).expanduser()

    home = Path.home()
    candidates = [
        home / "OneDrive" / "Belgeler" / "Obsidian Vault",
        home / "OneDrive" / "Documents" / "Obsidian Vault",
        home / "Belgeler" / "Obsidian Vault",
        home / "Documents" / "Obsidian Vault",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return home / "Obsidian Vault"


STATE_DIR = _resolve_state_dir()
SETTINGS_FILE = STATE_DIR / "settings.json"
CHAT_HISTORY_FILE = STATE_DIR / "chat_history.json"

class EntropyConfig(BaseModel):
    app_name: str = "Entropy AI"
    obsidian_vault_path: Path = Field(default_factory=_default_obsidian_vault)
    default_project_path: Path = Field(default_factory=lambda: APP_ROOT)
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
        except Exception as e:
            # Sessizce yutulursa kullanıcı ayarlarının hiç kaydedilmediğini fark edemez.
            print(f"[Entropy Config] Ayarlar kaydedilemedi ({SETTINGS_FILE}): {e}", file=sys.stderr)

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
        except Exception as e:
            print(f"[Entropy Config] Ayarlar okunamadı ({SETTINGS_FILE}): {e}", file=sys.stderr)

config = EntropyConfig()
config.load_settings()
