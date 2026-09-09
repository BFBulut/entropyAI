"""Core configuration and settings for Entropy AI with persistence."""

import json
import os
import sys
from typing import List, Optional
from pathlib import Path

# Pydantic, ilk BaseModel sınıfı tanımlandığında "pydantic" giriş noktası grubuna
# kayıtlı tüm eklentileri içe aktarır. Bu makinede o grupta logfire var; logfire
# de requests, asyncio, opentelemetry ve rich zincirini çekiyor. Ölçüm
# (python -X importtime -c "import entropy.main"): entropy.core.config tek başına
# 916 ms, bunun ~860 ms'i bu eklenti zinciri. Uygulama pydantic doğrulama
# eklentisi kullanmadığı için yükleme kapatılıyor — açık ortam değişkeni varsa
# ona dokunulmaz.
os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")

from pydantic import BaseModel, Field  # noqa: E402


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

def claude_api_available() -> bool:
    """
    ANTHROPIC_API_KEY tanımlı mı?

    Yalnızca TESPİT: doğrudan API (ClaudeApiBridge) ücretlidir ve abonelik
    kotasından değil kredi kartından harcar. Anahtar bulunsa bile sağlayıcı
    kendiliğinden API'ye geçmez; kullanıcı `allow_claude_api` ayarını açıkça
    açmadıkça bu bilgi yalnızca ayar ekranında "kullanılabilir" olarak görünür.
    """
    return bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())


# Sağlayıcı başına varsayılan model. Bir sağlayıcıya geçildiğinde selected_model
# bu tablodan doldurulur: gemini-* bir model adını `claude --model`e vermek
# süreci hiç başlatmadan hataya düşürüyordu.
DEFAULT_PROVIDER_MODELS = {
    "agy": "gemini-3.1-pro-high",
    "claude": "claude-opus-5",
}


class EntropyConfig(BaseModel):
    app_name: str = "Entropy AI"
    # Aktif CLI sağlayıcısı: "agy" (Antigravity) veya "claude" (Claude Code).
    provider: str = "agy"
    provider_models: dict = Field(default_factory=lambda: dict(DEFAULT_PROVIDER_MODELS))
    # Doğrudan Anthropic API köprüsü (ClaudeApiBridge) için yer tutucu izin
    # bayrağı. Uygulama YOK; açık olsa bile bugün hiçbir kod yolu API çağırmaz.
    allow_claude_api: bool = False
    obsidian_vault_path: Path = Field(default_factory=_default_obsidian_vault)
    default_project_path: Path = Field(default_factory=lambda: APP_ROOT)
    default_mode: str = "floating"  # "floating", "zen", "chat"
    autostart_enabled: bool = True
    # Açılışta yarım kalmış ofis zincirlerini kaldığı yerden sürdür. Varsayılan
    # açık; kapatma imkânı var çünkü sürdürme model çağrısı demektir ve kotasını
    # kontrol etmek isteyen kullanıcı uygulamayı sessiz açabilmeli.
    desk_auto_resume: bool = True
    context_window_size: int = 20
    model_fallback_name: str = "[Model: Unknown]"
    selected_model: str = "gemini-3.1-pro-high"
    last_conversation_id: Optional[str] = None
    # Agent Desk penceresinin son konumu/boyutu ve bulunduğu ekran.
    # Anahtarlar: x, y, width, height, screen (ekran adı), maximized (bool).
    # Bağımsız bir üst pencere olduğu için ana pencereden ayrı hatırlanır;
    # kullanıcı onu ikinci monitörde bırakmışsa orada açılsın diye ekran adı da
    # saklanır (ekran bağlı değilse birincil ekrana düşülür, bkz. desk/window.py).
    desk_geometry: dict = Field(default_factory=dict)
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
                "provider": self.provider,
                "provider_models": self.provider_models,
                "allow_claude_api": self.allow_claude_api,
                "desk_geometry": self.desk_geometry,
                "desk_auto_resume": self.desk_auto_resume,
            }
            # Atomik yazım: save_settings() işçi iş parçacıklarından da çağrılıyor
            # (her token güncellemesinde). Doğrudan write_text dosyayı önce kesiyor;
            # o anda okuyan (ya da yazan) ikinci bir taraf yarım JSON görebiliyordu.
            tmp_file = SETTINGS_FILE.with_suffix(SETTINGS_FILE.suffix + f".tmp{os.getpid()}")
            tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp_file, SETTINGS_FILE)
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
                # Sağlayıcı alanları eski ayar dosyalarında yok; varsayılan
                # ("agy") korunur, böylece güncelleme kimsenin kurulumunu
                # habersizce Claude'a çevirmez.
                if data.get("provider") in ("agy", "claude"):
                    self.provider = data["provider"]
                if isinstance(data.get("provider_models"), dict):
                    merged = dict(DEFAULT_PROVIDER_MODELS)
                    merged.update({k: v for k, v in data["provider_models"].items() if v})
                    self.provider_models = merged
                if isinstance(data.get("allow_claude_api"), bool):
                    self.allow_claude_api = data["allow_claude_api"]
                if isinstance(data.get("desk_geometry"), dict):
                    self.desk_geometry = data["desk_geometry"]
                if isinstance(data.get("desk_auto_resume"), bool):
                    self.desk_auto_resume = data["desk_auto_resume"]
        except Exception as e:
            print(f"[Entropy Config] Ayarlar okunamadı ({SETTINGS_FILE}): {e}", file=sys.stderr)

config = EntropyConfig()
config.load_settings()


# ---------------------------------------------------------------------------
# Sohbet geçmişi: tek kaynak
#
# Geçmişi hem köprü hem de iki arayüz modu okuyordu; her biri kendi dosya
# okuma/yazma mantığını taşıyordu ve "+ Yeni Sohbet" dosyayı geri dönüşsüz
# siliyordu. Okuma/yazma/arşivleme burada tek yerde toplandı. Fonksiyonlar
# CHAT_HISTORY_FILE'ı çağrı anında modül genelinden okur; testler bu değişkeni
# monkeypatch ile geçici bir dosyaya yönlendirdiğinde arşiv de onunla taşınır.
# ---------------------------------------------------------------------------

# Karşılama amaçlı, kullanıcıya ait olmayan tohum mesajlar; geçmişte gösterilmez.
CHAT_HISTORY_SEED_PROMPTS = ("Merhaba, bu proje nedir?", "Hello")


def chat_archive_dir() -> Path:
    """Arşivlenen sohbetlerin klasörü (geçmiş dosyasının yanında)."""
    return CHAT_HISTORY_FILE.parent / "chat_archive"


def load_chat_history() -> List[dict]:
    """Diskteki sohbet geçmişini okur; tohum mesajları ayıklar."""
    try:
        if not CHAT_HISTORY_FILE.exists():
            return []
        raw = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [
            m for m in raw
            if isinstance(m, dict)
            and str(m.get("content", "")).strip() not in CHAT_HISTORY_SEED_PROMPTS
        ]
    except Exception:
        return []


def save_chat_history(history: List[dict]) -> None:
    """Sohbet geçmişini diske yazar."""
    try:
        CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHAT_HISTORY_FILE.write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def chat_history_signature() -> tuple:
    """Geçmiş dosyasının (değişiklik zamanı, boyut) imzası; ucuz bayatlık kontrolü."""
    try:
        st = CHAT_HISTORY_FILE.stat()
        return (st.st_mtime_ns, st.st_size)
    except Exception:
        return (0, 0)


def archive_chat_history() -> Optional[Path]:
    """
    Mevcut sohbeti arşive taşır ve arşiv dosyasının yolunu döndürür.

    "+ Yeni Sohbet" eskiden chat_history.json'u siliyordu; kullanıcı geçmişini
    geri getirmenin yolu yoktu. Artık silme yerine taşıma yapılır.
    """
    from datetime import datetime

    history = load_chat_history()
    if not history:
        try:
            CHAT_HISTORY_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    try:
        target_dir = chat_archive_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = target_dir / f"{stamp}.json"
        target.write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        CHAT_HISTORY_FILE.unlink(missing_ok=True)
        return target
    except Exception:
        return None
