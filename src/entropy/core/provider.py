"""
Sağlayıcı soyutlaması: Entropy'nin konuştuğu CLI'ları tek arayüzde toplar.

Uygulama şimdiye dek doğrudan `AgyProcessBridge`e bağlıydı: main.py onu kuruyor,
arayüz modları `bridge.selected_model` okuyor, zamanlayıcı `send_background_task_async`
çağırıyordu. İkinci bir sağlayıcı (Claude Code CLI) eklenince bu bağların hepsinin
tek bir sözleşmeye dayanması gerekti — `ProviderBridge`.

Sözleşme kasıtlı olarak Protocol: mevcut köprü QObject'ten türüyor ve davranışı
değişmemeli; soyut taban sınıfa taşımak metaclass çakışması (QObject + ABCMeta)
ve mevcut testlerin kırılması demekti. Protocol yalnızca "bu nesne şu metotları
sağlıyor mu" sorusunu yanıtlar, kalıtım zorlamaz.

Paylaşılan davranış (bağlam doluluğu, aktarım, sağlayıcı adı) `ProviderCommonMixin`
ile gelir; iki köprü de onu miras alır, böylece bağlam baskısı mantığı tek yerde.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Protocol, runtime_checkable

# Desteklenen sağlayıcılar. "claude_api" kasıtlı olarak burada yok: API anahtarı
# tespit edilse bile ücretli olduğu için kullanıcı açıkça açmadan seçilemez
# (bkz. config.claude_api_available / EntropyConfig.provider).
PROVIDERS = ("agy", "claude")

# Sağlayıcı başına bağlam penceresi (token). AGY tarafı için 1M varsayımı
# ayarlanabilir bir tahmindir: agy pencere boyutunu bildirmiyor, bu yüzden
# doluluk oranı bir üst sınır tahmini olarak hesaplanır.
DEFAULT_CONTEXT_WINDOWS: Dict[str, int] = {
    "agy": 1_000_000,
    "claude": 200_000,
}

# Claude tarafında model başına pencere; bilinmeyen model varsayılana düşer.
CLAUDE_MODEL_CONTEXT_WINDOWS: Dict[str, int] = {
    "claude-opus-5": 200_000,
    "claude-sonnet-5": 1_000_000,
    "claude-haiku-4-5": 200_000,
}

# Bağlam bu orana ulaşınca baskı sinyali yayılır ve (varsa) aktarım sayfası yazılır.
CONTEXT_PRESSURE_THRESHOLD = 0.60

# Aktarımdan sonra yeni konuşmada tutulan tur sayısı (tur = kullanıcı + asistan).
HANDOFF_KEEP_TURNS = 4


def estimate_tokens(text: Optional[str]) -> int:
    """
    Kaba token tahmini: 4 karakter ≈ 1 token.

    Gerçek tokenizer çağırmıyoruz çünkü bu değer yalnızca doluluk oranı için
    kullanılıyor ve her turda hesaplanıyor; tokenizer yüklemek (tiktoken benzeri)
    açılışa yüzlerce ms eklerdi. Türkçe metinde bu oran biraz iyimser, bu yüzden
    eşik (%60) zaten güvenli tarafta seçildi.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def context_window_for(provider: str, model: Optional[str] = None) -> int:
    """Sağlayıcı (ve varsa model) için bağlam penceresi boyutu."""
    if provider == "claude" and model:
        for name, size in CLAUDE_MODEL_CONTEXT_WINDOWS.items():
            if model.startswith(name):
                return size
    return DEFAULT_CONTEXT_WINDOWS.get(provider, 200_000)


@runtime_checkable
class ProviderBridge(Protocol):
    """
    Entropy'nin bir CLI sağlayıcısından beklediği en küçük yüzey.

    Arayüz, zamanlayıcı ve yetenek katmanı yalnızca bu metotlara dayanır; yeni
    bir sağlayıcı eklemek için başka hiçbir dosyaya dokunmak gerekmemeli.
    """

    #: "agy" | "claude"
    provider_name: str
    selected_model: str
    active_project_dir: Path

    # --- Yürütme ---
    def send_prompt_async(self, prompt: str, **kwargs) -> None: ...

    def send_background_task_async(
        self,
        task_id: str,
        task_name: str,
        prompt: str,
        **kwargs,
    ) -> None: ...

    # --- İptal / kapanış ---
    def terminate_current_process(self) -> None: ...

    def terminate_background_task(self, task_id: str) -> None: ...

    def shutdown(self, timeout: float = 3.0) -> Dict[str, int]: ...

    # --- Durum ---
    def fetch_available_models(self) -> List[str]: ...

    def auth_status(self) -> Dict[str, object]: ...

    def set_model(self, model_name: str) -> None: ...

    def set_project_directory(self, project_path) -> None: ...

    # --- Bağlam ---
    def context_fill_ratio(self) -> float: ...

    # --- Ajan tanımları ---
    def agent_definitions_dir(self) -> Path: ...

    def list_agent_definitions(self) -> List[str]: ...


class ProviderCommonMixin:
    """
    İki köprünün ortak davranışı: bağlam doluluğu, baskı sinyali, aktarım.

    QObject'ten türeyen köprülerin ÖNÜNE konur (MRO'da mixin önce gelir); kendisi
    QObject değildir, bu yüzden Qt metaclass'ıyla çakışmaz.
    """

    provider_name: str = "agy"

    def context_window_size(self) -> int:
        """Aktif sağlayıcı/model için bağlam penceresi."""
        return context_window_for(
            getattr(self, "provider_name", "agy"),
            getattr(self, "selected_model", None),
        )

    def context_used_tokens(self) -> int:
        """
        Şu an bağlamda duran tahmini token sayısı.

        İki kalemin toplamı: (1) diskteki konuşma geçmişinin metin tahmini,
        (2) son turda sağlayıcının bildirdiği girdi token'ı — sistem istemi,
        bilişsel bağlam ve araç çıktıları buraya girer ve geçmiş metninde
        görünmez, bu yüzden yalnızca geçmişe bakmak doluluğu ciddi biçimde
        eksik ölçüyordu.
        """
        history = getattr(self, "conversation_history", None) or []
        hist_tokens = 0
        for turn in history:
            try:
                hist_tokens += estimate_tokens(str(turn.get("content", "")))
            except Exception:
                continue
        last_ctx = 0
        try:
            last_ctx = int(getattr(self, "latest_input_tokens", 0) or 0)
            last_ctx += int(getattr(self, "latest_cache_read_tokens", 0) or 0)
        except Exception:
            last_ctx = 0
        return max(hist_tokens, last_ctx) + min(hist_tokens, last_ctx) // 2

    def context_fill_ratio(self) -> float:
        """Bağlam doluluk oranı (0.0–1.0+); pencere bilinmiyorsa 0.0."""
        window = self.context_window_size()
        if window <= 0:
            return 0.0
        return self.context_used_tokens() / float(window)

    def check_context_pressure(self) -> float:
        """
        Doluluğu ölçer; eşiği aştıysa sinyal yayar ve aktarımı dener.

        Sinyal her turda değil, yalnızca eşiğin ÜSTÜNE ilk çıkışta yayılır:
        aksi hâlde uzun bir oturumda arayüz her turda uyarı gösterirdi. Aktarım
        başarılıysa oran düştüğü için bayrak kendiliğinden sıfırlanır.
        """
        ratio = self.context_fill_ratio()
        if ratio < CONTEXT_PRESSURE_THRESHOLD:
            self._context_pressure_announced = False
            return ratio
        if getattr(self, "_context_pressure_announced", False):
            return ratio
        self._context_pressure_announced = True
        try:
            from entropy.core.event_bus import bus

            bus.context_pressure.emit(float(ratio))
        except Exception:
            pass
        self.compact_context_via_handoff()
        return ratio

    def compact_context_via_handoff(self) -> Optional[str]:
        """
        Geçmişi aktarım sayfasına yazıp yerel geçmişi kısaltır.

        `entropy.memory.handoff.write_handoff` memory-rag tarafından sağlanır;
        henüz yoksa (import guard) hiçbir şey yapılmaz — köprü tek başına da
        çalışmak zorunda. Yeni konuşma = aktarım sayfası + son HANDOFF_KEEP_TURNS
        tur; böylece model devam eden işi kaybetmez ama pencere boşalır.
        """
        history = list(getattr(self, "conversation_history", None) or [])
        if not history:
            return None
        try:
            from entropy.memory.handoff import write_handoff  # type: ignore
        except Exception:
            return None

        meta = {
            "provider": getattr(self, "provider_name", "agy"),
            "model": getattr(self, "selected_model", ""),
            "project": str(getattr(self, "active_project_dir", "")),
            "ratio": self.context_fill_ratio(),
        }
        try:
            page = write_handoff(history, meta)
        except Exception:
            return None
        if not page:
            return None

        keep = history[-(HANDOFF_KEEP_TURNS * 2):]
        summary = {
            "role": "system",
            "content": (
                "[Bağlam Aktarımı] Önceki konuşma sıkıştırıldı; devam sayfası: "
                f"{page}"
            ),
        }
        new_history = [summary] + keep
        lock = getattr(self, "_state_lock", None)
        if lock is not None:
            with lock:
                self.conversation_history = new_history
        else:
            self.conversation_history = new_history
        try:
            import entropy.core.config as config_module

            config_module.save_chat_history(new_history)
        except Exception:
            pass
        return str(page)


# ---------------------------------------------------------------------------
# Ajan tanımları
# ---------------------------------------------------------------------------
#
# Biçim sağlayıcıya göre değişiyor:
#   agy    -> .agents/agents/<ad>/agent.md   (YAML ön bilgi + H1 gövde)
#   claude -> .claude/agents/<ad>.md         (YAML ön bilgi: name/description/
#                                             model/effort/tools + gövde)
# İkisi de sürecin çalışma dizinine göre keşfedilir.

AGENT_DEFINITION_LAYOUT = {
    "agy": (".agents/agents", "agent.md"),
    "claude": (".claude/agents", None),
}


def agent_definitions_dir(provider: str, root: Path | str) -> Path:
    """Sağlayıcının ajan tanımlarını aradığı dizin."""
    rel, _ = AGENT_DEFINITION_LAYOUT.get(provider, AGENT_DEFINITION_LAYOUT["agy"])
    return Path(root) / rel


def list_agent_definitions(provider: str, root: Path | str) -> List[str]:
    """Diskteki ajan adlarını verir (yoksa boş liste)."""
    base = agent_definitions_dir(provider, root)
    names: List[str] = []
    try:
        if not base.is_dir():
            return names
        _, filename = AGENT_DEFINITION_LAYOUT.get(provider, AGENT_DEFINITION_LAYOUT["agy"])
        if filename:
            for child in sorted(base.iterdir()):
                if child.is_dir() and (child / filename).is_file():
                    names.append(child.name)
        else:
            for child in sorted(base.glob("*.md")):
                names.append(child.stem)
    except Exception:
        return names
    return names


# ---------------------------------------------------------------------------
# Fabrika ve çalışırken sağlayıcı değiştirme
# ---------------------------------------------------------------------------


def create_bridge(cfg=None, provider: Optional[str] = None):
    """
    Ayarlardaki (ya da açıkça verilen) sağlayıcı için köprü örneği üretir.

    main.py ve arayüz yöneticisi köprüyü artık doğrudan `AgyProcessBridge()` ile
    değil buradan kurar; sağlayıcı adı ayarlardan geldiği için ikinci bir CLI
    eklemek tek satırlık bir kayıt işi olur.
    """
    if cfg is None:
        from entropy.core.config import config as cfg  # noqa: PLW0127

    name = (provider or getattr(cfg, "provider", "agy") or "agy").strip().lower()
    if name not in PROVIDERS:
        name = "agy"

    if name == "claude":
        from entropy.core.claude_bridge import ClaudeCodeBridge

        return ClaudeCodeBridge()

    from entropy.core.agy_bridge import AgyProcessBridge

    return AgyProcessBridge()


def switch_provider(current_bridge, provider: str, cfg=None):
    """
    Çalışırken sağlayıcı değiştirir: eskisini söndürür, yenisini kurar.

    Söndürme şart: eski köprünün arka plan agy/claude süreçleri ve ledger
    satırları aksi hâlde öksüz kalır (kapanış yolundaki aynı sorun).
    Döndürülen yeni köprüyü çağıran tarafın arayüze bağlaması gerekir.
    """
    if cfg is None:
        from entropy.core.config import config as cfg  # noqa: PLW0127

    name = (provider or "").strip().lower()
    if name not in PROVIDERS:
        raise ValueError(f"Bilinmeyen sağlayıcı: {provider!r} (geçerli: {', '.join(PROVIDERS)})")

    if current_bridge is not None:
        try:
            current_bridge.shutdown(timeout=3.0)
        except Exception:
            pass

    cfg.provider = name
    default_model = getattr(cfg, "provider_models", {}).get(name)
    if default_model:
        cfg.selected_model = default_model
    try:
        cfg.save_settings()
    except Exception:
        pass

    return create_bridge(cfg, provider=name)


_PROVIDER_CMD_RE = re.compile(r"^\s*/provider\b\s*(?P<arg>[A-Za-z_\-]*)\s*$", re.IGNORECASE)


def provider_command(text: str) -> Optional[Dict[str, str]]:
    """
    `/provider [agy|claude]` yerel komutunu ayrıştırır.

    Dönüş: komut değilse None; argümansızsa {"action": "show"}; geçerli adla
    {"action": "set", "provider": <ad>}; geçersiz adla {"action": "error", ...}.
    Komutun kendisi burada YÜRÜTÜLMEZ — yürütme (köprü değiştirme + arayüzü
    yeniden bağlama) çağıranın işi; ayrıştırma köprü tarafında olduğu için
    slash_commands.py ve arayüz aynı kuralı iki kez yazmak zorunda kalmaz.
    """
    if not text:
        return None
    m = _PROVIDER_CMD_RE.match(text)
    if not m:
        return None
    arg = (m.group("arg") or "").strip().lower()
    if not arg:
        return {"action": "show"}
    if arg not in PROVIDERS:
        return {
            "action": "error",
            "message": f"Bilinmeyen sağlayıcı '{arg}'. Geçerli: {', '.join(PROVIDERS)}.",
        }
    return {"action": "set", "provider": arg}
