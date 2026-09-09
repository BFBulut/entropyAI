"""Core configuration and settings for Entropy AI with persistence."""

import json
import os
import sys
import tempfile
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


def is_bundle_dir(path) -> bool:
    """
    Yol .exe'nin paket klasörü mü (`dist/EntropyAI` ya da onun `_internal`ı)?

    Paketlenmiş sürümde APP_ROOT .exe'nin klasörüdür. Oraya proje kökü demek,
    ajanın gerçek projeyi değil PyInstaller çıktısını incelemesi demekti:
    kullanıcı "hafızanı kontrol et" dediğinde model paketin içindeki eski ajan
    listesini ve `_internal/skills/` klasörünü gerçek kadro sanıyordu.
    """
    if not path:
        return False
    try:
        p = Path(path).resolve()
    except Exception:
        return False
    if not getattr(sys, "frozen", False):
        # Kaynaktan koşarken APP_ROOT deponun kendisidir; geçerli bir proje kökü.
        return False
    bundle = Path(sys.executable).resolve().parent
    return p == bundle or bundle in p.parents or p.name == "_internal"


def default_workspace_root() -> Path:
    """
    Proje kökü seçilmemişken kullanılacak NÖTR kök.

    Paketlenmiş sürümde ASLA .exe klasörü olmaz: `%USERPROFILE%\\.entropy\\
    workspace`. Kullanıcı gerçek projeyi üst çubuktaki "Proje" düğmesiyle seçer.
    """
    if getattr(sys, "frozen", False):
        base = Path.home() / ".entropy" / "workspace"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return base
    return APP_ROOT


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

# Sağlayıcı başına akıl yürütme eforu (`--effort`). Seviye kümesi CLI'a göre
# değişir (agy: low|medium|high; claude: low|medium|high|xhigh|max), bu yüzden
# tek bir "selected_effort" yerine sağlayıcı başına tutulur: claude'da "max"
# seçip agy'ye dönmek geçersiz bir bayrak üretirdi.
DEFAULT_PROVIDER_EFFORT = {
    "agy": "high",
    "claude": "high",
}


# ---------------------------------------------------------------------------
# Model adı doğrulama (Faz 9.1 — üç kapı)
#
# Doğrulama köprülerde DEĞİL burada: `load_settings()` açılışta zehirli
# `provider_models` değerlerini onarabilmeli, ama köprüleri içe aktaramaz
# (döngüsel içe aktarım). Köprüler bu yardımcıları çağırır; canlı model listesi
# (ör. `agy models`) varsa `extra` parametresiyle genişletilir.
# ---------------------------------------------------------------------------

# `claude --model` tam adları.
CLAUDE_MODEL_NAMES = ("claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5")

# `claude --model` takma adları (belge: code.claude.com/docs/en/model-config).
CLAUDE_MODEL_ALIAS_NAMES = (
    "opus", "sonnet", "haiku", "fable", "best", "default", "opusplan",
)

# agy'nin sunduğu, adı "claude-" ile başlayan modeller. Bu adlar HEM agy hem
# Claude süzgecinden geçebilir; ayrım `agy models` canlı listesiyle yapılır,
# liste yoksa bu sabit devreye girer (yoksa agy ayarı yanlışlıkla onarılırdı).
AGY_CLAUDE_MODEL_NAMES = (
    "claude-sonnet-4-6",
    "claude-opus-4-6-thinking",
)

# agy model adlarının bilinen ön ekleri (canlı liste alınamadığında).
AGY_MODEL_PREFIXES = ("gemini-", "gpt-")


def _strip_context_suffix(name: str) -> str:
    """`opus[1m]` gibi bağlam penceresi ekini ayırır."""
    low = (name or "").strip().lower()
    if low.endswith("[1m]"):
        low = low[:-4]
    return low


def is_claude_model_name(name: str) -> bool:
    """Ad `claude --model`e verilebilir mi (tam ad, takma ad ya da `[1m]` eki)."""
    low = _strip_context_suffix(name)
    if not low:
        return False
    if low in CLAUDE_MODEL_ALIAS_NAMES:
        return True
    # Tam adlar: "claude-" ile başlayan her ad kabul edilir; CLI yeni sürüm
    # adlarını da tanır ve burada beyaz liste tutmak her model çıkışında
    # Entropy'yi kilitlerdi.
    return low.startswith("claude-")


def is_agy_model_name(name: str, extra: Optional[List[str]] = None) -> bool:
    """Ad `agy --model`e verilebilir mi (canlı liste + bilinen ön ekler)."""
    low = (name or "").strip().lower()
    if not low:
        return False
    for m in extra or []:
        if low == str(m).strip().lower():
            return True
    if low.startswith(AGY_MODEL_PREFIXES):
        return True
    return low in AGY_CLAUDE_MODEL_NAMES


def is_valid_model_for(provider: str, name: str, extra: Optional[List[str]] = None) -> bool:
    """Sağlayıcıya göre model adı süzgeci (bilinmeyen sağlayıcı: her ad geçer)."""
    p = (provider or "").strip().lower()
    if p == "claude":
        return is_claude_model_name(name)
    if p == "agy":
        return is_agy_model_name(name, extra=extra)
    return bool(name)


def default_provider() -> str:
    """
    Yeni kart/ajan/ofis için varsayılan sağlayıcı — tek gerçek kaynak.

    Sabit `"agy"` yerine bunu çağırın: agy kurulu değilken doğan her kayıt
    `provider: agy` ile doğup ilk koşuda ölüyordu (Faz 9 araştırması §1.9).
    """
    p = (getattr(config, "provider", "") or "").strip().lower()
    return p if p in ("agy", "claude") else "agy"


def claude_workspace_path() -> Path:
    """
    Claude Code'un koşacağı NÖTR çalışma dizini (Faz 9.2).

    Claude Code proje kimliğini (bellek dizini, `.claude/agents`, git durumu)
    literal cwd'den değil GIT KÖKÜNDEN çözüyor; depo içindeki bir alt klasör
    kaçış sağlamıyor. Bu yüzden dizin bir git deposunun DIŞINDA olmalı: üst
    dizinlerde `.git` görülürse geçici dizine düşülür.
    """
    raw = (getattr(config, "claude_workspace_dir", "") or "").strip()
    base = Path(raw) if raw else (Path.home() / ".entropy" / "workspace")
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path(tempfile.gettempdir()) / "entropy_workspace"
        base.mkdir(parents=True, exist_ok=True)
    if path_is_inside_git_repo(base):
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "Claude çalışma dizini bir git deposunun içinde (%s); "
            "geçici dizine düşülüyor. Claude Code proje kimliğini git kökünden "
            "çözdüğü için depo içi dizin izolasyonu bozar.",
            base,
        )
        base = Path(tempfile.gettempdir()) / "entropy_workspace"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return base


def path_is_inside_git_repo(path: Path) -> bool:
    """Yolun kendisinde ya da üst dizinlerinden birinde `.git` var mı."""
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    for candidate in [p, *p.parents]:
        if (candidate / ".git").exists():
            return True
    return False


class EntropyConfig(BaseModel):
    app_name: str = "Entropy AI"
    # Aktif CLI sağlayıcısı: "agy" (Antigravity) veya "claude" (Claude Code).
    provider: str = "agy"
    provider_models: dict = Field(default_factory=lambda: dict(DEFAULT_PROVIDER_MODELS))
    provider_effort: dict = Field(default_factory=lambda: dict(DEFAULT_PROVIDER_EFFORT))
    # Doğrudan Anthropic API köprüsü (ClaudeApiBridge) için yer tutucu izin
    # bayrağı. Uygulama YOK; açık olsa bile bugün hiçbir kod yolu API çağırmaz.
    allow_claude_api: bool = False
    # Claude Code için isteğe bağlı "Entropy profili": doluysa CLI çağrılarına
    # CLAUDE_CONFIG_DIR ortam değişkeni olarak verilir ve oturum/ayarlar
    # kullanıcının kendi profilinden yalıtılır. BOŞ (varsayılan) bırakılırsa
    # kullanıcının profili kullanılır — çünkü izole profile geçmek yeniden giriş
    # demektir ve bu kullanıcının açık kararı olmalı.
    claude_config_dir: str = ""
    # "Entropy Saf Kip" (Faz 9.2): Claude Code kullanıcının kendi kurulumundan
    # yalıtılır — varsayılan sistem istemi DEĞİŞTİRİLİR (eklenmez), kullanıcının
    # MCP sunucuları/ayar dosyaları/yetenek kataloğu yüklenmez ve süreç git
    # deposunun dışında koşar. Kapatıldığında Faz 8 davranışına
    # (`--append-system-prompt-file` + proje dizininde cwd) dönülür; geri dönüş
    # yolu bilinçli olarak tek ayar.
    claude_isolated: bool = True
    # Saf kipte Claude'un cwd'si. Boş = %USERPROFILE%\.entropy\workspace.
    # Bir git deposunun içinde OLMAMALI (bkz. claude_workspace_path).
    claude_workspace_dir: str = ""
    obsidian_vault_path: Path = Field(default_factory=_default_obsidian_vault)
    default_project_path: Path = Field(default_factory=lambda: default_workspace_root())
    default_mode: str = "floating"  # "floating", "zen", "chat"
    autostart_enabled: bool = True
    # Açılışta yarım kalmış ofis zincirlerini kaldığı yerden sürdür. Varsayılan
    # açık; kapatma imkânı var çünkü sürdürme model çağrısı demektir ve kotasını
    # kontrol etmek isteyen kullanıcı uygulamayı sessiz açabilmeli.
    desk_auto_resume: bool = True
    # Etkileşimli kart kipi (Faz 10-C): kartın CLI süreci ilk sonuçtan sonra da
    # canlı kalır ve sahnedeki bölmeden yazılan mesaj aynı sürece düşer (gerçek
    # terminal girdisi). Kapatıldığında Faz 10-B davranışına dönülür: süreç ilk
    # `result` ile biter, takip mesajı gönderilemez.
    desk_interactive_cards: bool = True
    # Boşta bekleyen etkileşimli sürecin ömrü (saniye). Süre dolunca stdin
    # kapatılır ve süreç sonlandırılır; kullanıcı bölmeyi açık unutsa bile CLI
    # süreci ve oturum belleği sonsuza dek yaşamaz.
    desk_interactive_idle_timeout_s: int = 600
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

    def repair_provider_models(self) -> dict:
        """
        Zehirli `provider_models` girdilerini onarır (Faz 9.1 — göç kapısı).

        Kullanıcının üst çubuktaki serbest metinli model kutusu, agy modelini
        `provider_models["claude"]` alanına yazabiliyordu. Köprünün yedek değeri
        de buradan okunduğu için yabancı-model koruması boşa çıkıyor ve her
        Claude koşusu `unrecognized_model` ile ölüyordu. Onarım dönüş değeri
        {sağlayıcı: (eski, yeni)}; boşsa hiçbir şey değişmedi.
        """
        repaired: dict = {}
        models = self.provider_models if isinstance(self.provider_models, dict) else {}
        for provider, default in DEFAULT_PROVIDER_MODELS.items():
            current = str(models.get(provider) or "").strip()
            if not current:
                continue
            if is_valid_model_for(provider, current):
                continue
            repaired[provider] = (current, default)
            models[provider] = default
        if repaired:
            self.provider_models = models
            import logging as _logging

            for provider, (old, new) in repaired.items():
                _logging.getLogger(__name__).warning(
                    "Ayarlardaki model onarıldı: provider_models[%r] = %r "
                    "(%r bu sağlayıcıya ait değil).", provider, new, old
                )
            try:
                self.save_settings()
            except Exception:
                pass
        return repaired

    def repair_provider_effort(self) -> dict:
        """
        `provider_effort["agy"]` değerini agy'nin gerçekten sunduğu kümeye çeker.

        agy'de efor model adının son ekidir; Claude'da seçilen "xhigh"/"max" agy
        ayarına sızdığında `gemini-3.8-flash-xhigh` gibi var olmayan bir ad
        besteleniyordu. Onarım hem eforu hem — gerekiyorsa — modeli tutarlı hâle
        getirir. Dönüş {"agy": (eski, yeni)}; boşsa değişiklik yok.
        """
        from entropy.core.provider import (
            compose_agy_model, effort_levels_for, split_agy_model,
        )

        repaired: dict = {}
        effort_map = self.provider_effort if isinstance(self.provider_effort, dict) else {}
        model = str((self.provider_models or {}).get("agy") or "").strip()
        levels = effort_levels_for("agy", model)
        if not levels:
            return repaired
        current = str(effort_map.get("agy") or "").strip().lower()
        model_effort = split_agy_model(model)[1]
        # Tek gerçek kaynak model adıdır: ayardaki efor ondan farklıysa ve
        # modelde karşılığı yoksa modele göre düzeltilir.
        target = current if current in levels else (model_effort or levels[-1])
        if target != current:
            repaired["agy"] = (current, target)
            effort_map["agy"] = target
            self.provider_effort = effort_map
        composed = compose_agy_model(model, target)
        if composed and composed != model:
            self.provider_models["agy"] = composed
            if self.selected_model == model:
                self.selected_model = composed
            repaired.setdefault("agy", (current, target))
        if repaired:
            import logging as _logging

            _logging.getLogger(__name__).warning(
                "agy eforu onarıldı: %r -> %r (model %r); agy'de efor model "
                "adının son ekidir.", repaired["agy"][0], repaired["agy"][1],
                self.provider_models.get("agy"),
            )
            try:
                self.save_settings()
            except Exception:
                pass
        return repaired

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
                "provider_effort": self.provider_effort,
                "allow_claude_api": self.allow_claude_api,
                "desk_geometry": self.desk_geometry,
                "desk_auto_resume": self.desk_auto_resume,
                "desk_interactive_cards": self.desk_interactive_cards,
                "desk_interactive_idle_timeout_s": self.desk_interactive_idle_timeout_s,
                "claude_config_dir": self.claude_config_dir,
                "claude_isolated": self.claude_isolated,
                "claude_workspace_dir": self.claude_workspace_dir,
                # Kullanıcının "Proje" düğmesiyle seçtiği kök kalıcı olmalıydı:
                # kaydedilmediği için her açılışta APP_ROOT'a (paketlenmiş
                # sürümde .exe klasörüne) düşüyordu.
                "default_project_path": str(self.default_project_path),
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
                if isinstance(data.get("provider_effort"), dict):
                    merged_effort = dict(DEFAULT_PROVIDER_EFFORT)
                    merged_effort.update(
                        {k: v for k, v in data["provider_effort"].items() if v}
                    )
                    self.provider_effort = merged_effort
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
                if isinstance(data.get("desk_interactive_cards"), bool):
                    self.desk_interactive_cards = data["desk_interactive_cards"]
                idle_s = data.get("desk_interactive_idle_timeout_s")
                if isinstance(idle_s, int) and not isinstance(idle_s, bool) and idle_s > 0:
                    self.desk_interactive_idle_timeout_s = idle_s
                if isinstance(data.get("claude_config_dir"), str):
                    self.claude_config_dir = data["claude_config_dir"]
                if isinstance(data.get("claude_isolated"), bool):
                    self.claude_isolated = data["claude_isolated"]
                if isinstance(data.get("claude_workspace_dir"), str):
                    self.claude_workspace_dir = data["claude_workspace_dir"]
                if isinstance(data.get("default_project_path"), str) and data["default_project_path"]:
                    self.default_project_path = Path(data["default_project_path"])
                self.repair_provider_models()
                self.repair_provider_effort()
                # Paketlenmiş sürümde .exe klasörü proje kökü OLAMAZ: eski ayar
                # dosyaları `C:\\EntropiAI\\dist\\EntropyAI` taşıyordu ve ajan
                # orada `_internal/AGENTS.md` okuyordu.
                if is_bundle_dir(self.default_project_path):
                    self.default_project_path = default_workspace_root()
                # Var olmayan proje kökü de reddedilir. Ölçüm: test koşumları
                # canlı ayar dosyasına `...\pytest-of-batu_\pytest-2301\...`
                # yazmıştı; uygulama açılışta o silinmiş tmp klasörünü proje
                # kökü olarak bağlıyor, ajan derlemesi oraya bakıyordu.
                try:
                    if not Path(self.default_project_path).is_dir():
                        self.default_project_path = default_workspace_root()
                except OSError:
                    self.default_project_path = default_workspace_root()
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
