"""
Tek Entropy kimliği: iki sağlayıcı, tek DURUM katmanı.

Araştırma notunun (Faz 5 §4) verdiği karar net: agy ve Claude Code oturumları
birbirini tanımaz ve tanıyamaz — agy abonelik kimliğini makine başına tek Google
hesabı olarak tutar, Claude kendi profil dizinini kullanır. "Tek giriş" teknik
olarak mümkün değil; mümkün olan ve işe yarayan şey TEK DURUM KATMANI:

  - giriş var mı, hangi hesap,
  - kota/oturum penceresi hakkında ne biliniyor,
  - son hata ne,
  - giriş yoksa kullanıcı ne yapmalı (yönlendirme metni).

Problar KOTA HARCAMAZ; hiçbiri model çağırmaz:

  claude : `claude auth status --json`  → loggedIn, email, subscriptionType, orgName
  agy    : `agy models` (yalnızca kimlik doğrulanmışsa liste döner) +
           `~/.gemini/google_accounts.json` (aktif hesap) +
           `~/.gemini/oauth_creds.json` (`expiry_date`, ms epoch → oturum penceresi)

agy'de oturum/kota sorgulayan bir alt komut YOK (`agy --help` doğrulandı: yalnızca
agent/agents, changelog, help, install, mcp, mic-serve, models, plugin,
remote-control, update). Bu yüzden kota ipucu "bilinmiyor" olarak raporlanır —
tahmini bir sayı göstermek yanlış güven verirdi.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

PROVIDERS = ("agy", "claude")

# Periyodik yenileme aralığı (sn). 5 dk: prob iki alt süreç açıyor ve daha sık
# koşmak açılış dışında hiçbir şeyi iyileştirmiyor (oturum saatler sürüyor).
REFRESH_INTERVAL_SECONDS = 300

# agy'nin oturum dosyalarının kökü. `agy` Gemini CLI'ın halefi ve aynı dizini
# yeniden kullanıyor (araştırma notu §4, diskte doğrulandı).
GEMINI_HOME = Path.home() / ".gemini"

UNKNOWN = "bilinmiyor"


LOGIN_GUIDANCE: Dict[str, str] = {
    "claude": (
        "Claude Code oturumu kapalı.\n"
        "1) Terminalde `claude login` çalıştır (tarayıcı açılır).\n"
        "2) claude.ai hesabınla (Pro/Max) ya da konsol API anahtarınla giriş yap.\n"
        "3) `claude auth status --json` çıktısında \"loggedIn\": true görünmeli.\n"
        "Entropy'ye ayrı bir profil vermek istersen Ayarlar → `claude_config_dir` "
        "alanına bir klasör yaz; o klasör CLAUDE_CONFIG_DIR olarak kullanılır ve "
        "orada bir kez daha giriş yapman gerekir."
    ),
    "agy": (
        "Antigravity (agy) oturumu kapalı ya da doğrulanamıyor.\n"
        "1) Terminalde `agy` yazıp etkileşimli oturumu başlat; giriş yapılmamışsa "
        "Google hesabı için tarayıcı akışı açılır.\n"
        "2) Giriş bilgisi `~/.gemini` altında tutulur; makine başına TEK hesap "
        "desteklenir (profil seçici yok).\n"
        "3) `agy models` komutu model listesi döndürüyorsa oturum açıktır."
    ),
}


def login_guidance(provider: str) -> str:
    """Giriş yoksa kullanıcıya gösterilecek yönlendirme metni."""
    return LOGIN_GUIDANCE.get((provider or "").strip().lower(), "Bilinmeyen sağlayıcı.")


@dataclass
class ProviderStatus:
    """Tek bir sağlayıcının kimlik/oturum durumu (tek durum katmanının satırı)."""

    provider: str
    logged_in: bool = False
    account_hint: str = ""
    plan: str = ""
    quota_hint: str = UNKNOWN
    session_window: str = ""
    last_error: str = ""
    checked_at: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @property
    def badge(self) -> str:
        """Rozet metni (arayüz aynı satırı iki kez kurmasın diye burada)."""
        if not self.logged_in:
            return f"{self.provider}: giriş yok"
        who = self.account_hint or UNKNOWN
        plan = f" · {self.plan}" if self.plan else ""
        return f"{self.provider}: {who}{plan}"


def _creationflags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return 0


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Problar
# ---------------------------------------------------------------------------


def probe_claude(runner: Optional[Callable] = None) -> ProviderStatus:
    """
    `claude auth status --json`. Model çağırmaz, kota harcamaz.

    `runner` testler için enjekte edilir (imzası subprocess.run ile aynı);
    gerçek CLI'a bağlı bir test hem yavaş hem de makineye bağımlı olurdu.
    """
    status = ProviderStatus(provider="claude", checked_at=_now())
    run = runner or subprocess.run
    try:
        from entropy.core.claude_bridge import ClaudeCodeBridge

        # Bağlanmamış çağrı bilinçli: gövde `self` kullanmıyor ve prob için
        # koca bir QObject köprüsü kurmak 5 dakikada bir boşuna maliyet olurdu.
        binary = ClaudeCodeBridge.find_claude_executable(None)
        env = ClaudeCodeBridge.process_env()
    except Exception:
        binary, env = "claude", None
    try:
        res = run(
            [binary, "auth", "status", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creationflags(),
            env=env,
            timeout=20,
        )
    except Exception as exc:
        status.last_error = str(exc)[:300]
        return status

    raw = (getattr(res, "stdout", "") or "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        status.last_error = ((getattr(res, "stderr", "") or raw or "auth status okunamadı"))[:300]
        return status
    if not isinstance(data, dict):
        status.last_error = "auth status çıktısı sözlük değil"
        return status

    status.logged_in = bool(data.get("loggedIn"))
    status.account_hint = str(data.get("email") or data.get("orgName") or "")
    status.plan = str(data.get("subscriptionType") or data.get("authMethod") or "")
    # Claude CLI kalan kotayı ya da pencere sıfırlanma anını bildirmiyor; abonelik
    # tipi tek ipucu. Uydurma bir yüzde göstermek yanlış güven verirdi.
    status.quota_hint = (
        f"abonelik: {status.plan}" if status.plan else UNKNOWN
    )
    if not status.logged_in:
        status.last_error = "oturum kapalı"
    return status


def _agy_session_window(now_ms: Optional[int] = None) -> tuple:
    """
    `~/.gemini/oauth_creds.json` → (pencere metni, hesap ipucu).

    `expiry_date` ms cinsinden epoch; erişim belirtecinin ne zaman biteceğini
    verir. Bu KOTA penceresi değil OTURUM penceresidir ve öyle etiketlenir —
    ikisini karıştırmak kullanıcıya yanlış kalan-hak bilgisi gösterirdi.
    """
    window = ""
    account = ""
    try:
        data = json.loads((GEMINI_HOME / "google_accounts.json").read_text(encoding="utf-8"))
        account = str(data.get("active") or "")
    except Exception:
        account = ""
    try:
        creds = json.loads((GEMINI_HOME / "oauth_creds.json").read_text(encoding="utf-8"))
        expiry = creds.get("expiry_date")
        if expiry:
            ts = datetime.datetime.fromtimestamp(int(expiry) / 1000.0)
            now = (
                datetime.datetime.fromtimestamp(now_ms / 1000.0)
                if now_ms is not None
                else datetime.datetime.now()
            )
            minutes = int((ts - now).total_seconds() // 60)
            state = f"{minutes} dk kaldı" if minutes > 0 else "süresi doldu (yenilenecek)"
            window = f"belirteç {ts.isoformat(timespec='minutes')} ({state})"
    except Exception:
        window = ""
    return window, account


def probe_agy(runner: Optional[Callable] = None) -> ProviderStatus:
    """
    agy oturum durumu; model çağırmaz.

    `agy models` yalnızca kimlik doğrulanmışsa liste döndürdüğü için varlığı
    dolaylı ama güvenilir bir oturum kanıtıdır — agy'de oturum sorgulayan bir
    alt komut yok (`agy --help` ile doğrulandı).
    """
    status = ProviderStatus(provider="agy", checked_at=_now(), quota_hint=UNKNOWN)
    window, account = _agy_session_window()
    status.session_window = window
    status.account_hint = account

    run = runner or subprocess.run
    try:
        from entropy.core.agy_bridge import AgyProcessBridge

        binary = AgyProcessBridge.find_agy_executable(None)
    except Exception:
        binary = "agy"
    try:
        res = run(
            [binary, "models"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creationflags(),
            timeout=20,
        )
    except Exception as exc:
        status.last_error = str(exc)[:300]
        return status

    out = (getattr(res, "stdout", "") or "").strip()
    ok = getattr(res, "returncode", 1) == 0 and bool(out)
    status.logged_in = ok
    if ok:
        status.plan = "antigravity-cli"
    else:
        status.last_error = (
            (getattr(res, "stderr", "") or out or f"çıkış kodu {getattr(res, 'returncode', '?')}")
        )[:300]
    # Kota: Antigravity kotası uygulama + CLI + SDK arasında ORTAK ve CLI kalanı
    # bildirmiyor (araştırma notu §4). "bilinmiyor" bilinçli bir cevaptır.
    return status


PROBES: Dict[str, Callable[..., ProviderStatus]] = {
    "claude": probe_claude,
    "agy": probe_agy,
}


# ---------------------------------------------------------------------------
# Durum katmanı
# ---------------------------------------------------------------------------


class IdentityLayer:
    """
    Sağlayıcı durumlarının tek sahibi: prob çalıştırır, önbellekler, yayar.

    Prob alt süreç açtığı için ARKA PLAN iş parçacığında koşar; sinyal ana iş
    parçacığına `bus.invoke_on_main` ile taşınır — arayüz doğrudan bu sinyale
    bağlanır ve prob için hiç beklemez.
    """

    def __init__(self, interval_seconds: float = REFRESH_INTERVAL_SECONDS):
        self.interval_seconds = float(interval_seconds)
        self._statuses: Dict[str, ProviderStatus] = {}
        self._lock = threading.RLock()
        self._timer = None
        # Sağlayıcı otomatik seçimi yalnızca ilk yenilemede koşar.
        self._provider_autoselected = False

    # -- okuma ------------------------------------------------------------

    def get(self, provider: str) -> Optional[ProviderStatus]:
        with self._lock:
            return self._statuses.get((provider or "").strip().lower())

    def all(self) -> Dict[str, ProviderStatus]:
        with self._lock:
            return dict(self._statuses)

    # -- yenileme ---------------------------------------------------------

    def refresh(self, provider: str, runner: Optional[Callable] = None) -> ProviderStatus:
        name = (provider or "").strip().lower()
        probe = PROBES.get(name)
        if probe is None:
            raise ValueError(f"Bilinmeyen sağlayıcı: {provider!r}")
        try:
            status = probe(runner=runner)
        except Exception as exc:
            status = ProviderStatus(provider=name, checked_at=_now(), last_error=str(exc)[:300])
        with self._lock:
            self._statuses[name] = status
        self._emit(status)
        return status

    def refresh_all(self, runner: Optional[Callable] = None) -> Dict[str, ProviderStatus]:
        statuses = {name: self.refresh(name, runner=runner) for name in PROVIDERS}
        # AÇILIŞTA BİR KEZ: etkin sağlayıcının oturumu yoksa ve diğerininki
        # varsa varsayılan sağlayıcı düzeltilir (Faz 9 / Ek-2). Yalnızca ilk
        # turda: kullanıcı sonradan bilerek sağlayıcı değiştirmişse periyodik
        # yenileme onu geri almamalı.
        if not self._provider_autoselected:
            self._provider_autoselected = True
            try:
                auto_select_provider(
                    claude_status=statuses.get("claude"),
                    agy_status=statuses.get("agy"),
                )
            except Exception:
                logger.warning("Sağlayıcı otomatik seçimi başarısız", exc_info=True)
        return statuses

    def refresh_async(self) -> None:
        threading.Thread(target=self.refresh_all, daemon=True).start()

    @staticmethod
    def _emit(status: ProviderStatus) -> None:
        try:
            from entropy.core.event_bus import bus

            bus.invoke_on_main(
                lambda: bus.provider_status_updated.emit(status.provider, status.to_dict())
            )
        except Exception:
            pass

    # -- periyodik --------------------------------------------------------

    def start(self) -> bool:
        """Açılışta bir kez, sonra `interval_seconds`da bir yeniler."""
        self.refresh_async()
        try:
            from PySide6.QtCore import QTimer
        except Exception:
            return False
        try:
            self._timer = QTimer()
            self._timer.setInterval(int(self.interval_seconds * 1000))
            self._timer.timeout.connect(self.refresh_async)
            self._timer.start()
        except Exception:
            logger.warning("Kimlik katmanı sayacı kurulamadı", exc_info=True)
            return False
        return True

    def stop(self) -> None:
        try:
            if self._timer is not None:
                self._timer.stop()
        except Exception:
            pass
        self._timer = None


identity = IdentityLayer()


def auto_select_provider(
    claude_status: Optional[ProviderStatus] = None,
    agy_status: Optional[ProviderStatus] = None,
) -> Optional[str]:
    """
    Açılışta sağlayıcıyı canlı duruma göre düzeltir (Faz 9 / Ek-2).

    Kural: yalnızca ETKİN sağlayıcının oturumu yokken ve DİĞERİNİNKİ varken
    geçilir. Tek yönlü değil çünkü agy'siz makinede her yeni kart/ajan/ofis
    `provider: agy` ile doğup ilk koşuda ölüyordu (araştırma §1.9). Sessiz
    düşme yok: geçiş tek satırlık bilgi olarak terminale de yazılır.

    Dönüş: yeni sağlayıcı adı, ya da değişiklik yoksa None.
    """
    from entropy.core.config import config

    current = (getattr(config, "provider", "") or "agy").strip().lower()
    other = "claude" if current == "agy" else "agy"
    statuses = {
        "claude": claude_status if claude_status is not None else probe_claude(),
        "agy": agy_status if agy_status is not None else probe_agy(),
    }
    if statuses[current].logged_in or not statuses[other].logged_in:
        return None
    config.provider = other
    try:
        config.save_settings()
    except Exception:
        pass
    message = (
        f"[Entropy] Varsayılan sağlayıcı '{other}' olarak ayarlandı: "
        f"'{current}' oturumu bulunamadı."
    )
    logger.info(message)
    try:
        from entropy.core.event_bus import bus

        bus.terminal_output_received.emit(f"\n{message}\n")
    except Exception:
        pass
    return other


# ---------------------------------------------------------------------------
# Konuşma eşlemesi
# ---------------------------------------------------------------------------


def _map_path() -> Path:
    from entropy.core.config import STATE_DIR

    return Path(STATE_DIR) / "conversation_map.json"


class ConversationMap:
    """
    Entropy konuşma kimliği ↔ sağlayıcı oturum kimliği eşlemesi.

    Neden ayrı dosya: `settings.json` her token güncellemesinde yazılıyor ve
    eşleme her turda değişebiliyor; ikisi aynı dosyada olsaydı yarış artardı.

    Sağlayıcı DEĞİŞSE de eşleme korunur: aynı Entropy konuşması altında hem agy
    hem Claude oturum kimliği ayrı ayrı saklanır, geri dönüldüğünde eski oturum
    kaldığı yerden sürer.
    """

    # Sağlayıcı başına devam bayrağı. agy `--conversation <id>`, Claude
    # `--resume <id>` diyor; anlam aynı, ad farklı.
    FLAGS = {"agy": "--conversation", "claude": "--resume"}

    def __init__(self, path: Optional[Path | str] = None):
        self.path = Path(path) if path else _map_path()
        self._lock = threading.RLock()

    def _load(self) -> Dict[str, Dict[str, str]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: Dict[str, Dict[str, str]]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + f".tmp{os.getpid()}")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            logger.warning("Konuşma eşlemesi yazılamadı: %s", self.path)

    def set(self, conversation_id: str, provider: str, session_id: str) -> None:
        provider = (provider or "").strip().lower()
        if not conversation_id or not provider or not session_id:
            return
        with self._lock:
            data = self._load()
            entry = dict(data.get(conversation_id) or {})
            entry[provider] = str(session_id)
            entry["updated_at"] = _now()
            data[conversation_id] = entry
            self._save(data)

    def get(self, conversation_id: str, provider: str) -> Optional[str]:
        entry = self._load().get(conversation_id) or {}
        value = entry.get((provider or "").strip().lower())
        return str(value) if value else None

    def providers_for(self, conversation_id: str) -> List[str]:
        entry = self._load().get(conversation_id) or {}
        return sorted(k for k in entry if k in PROVIDERS)

    def resume_flag(self, conversation_id: str, provider: str) -> List[str]:
        """
        Bu tur için argv'ye eklenecek devam bayrağı (yoksa boş liste).

        Boş liste "yeni oturum" demektir ve bilerek sessizdir: eşleme yoksa
        uydurma bir kimlikle `--resume` çağırmak CLI'ı hataya düşürüyordu.
        """
        provider = (provider or "").strip().lower()
        session = self.get(conversation_id, provider)
        flag = self.FLAGS.get(provider)
        if not session or not flag:
            return []
        return [flag, session]

    @staticmethod
    def prompt_signature(text: str, model: str = "", effort: str = "") -> str:
        """
        Oturumun parmak izi: `sha1(istem | model | efor)` (Faz 11-C.12).

        Kapsam Faz 11-C'de genişledi. Eskiden yalnızca istem hash'leniyordu;
        model ya da efor değiştirilip `--resume` ile eski oturuma dönülünce
        `--system-prompt-snapshot on` yüzünden ESKİ istem taşınıyor ve yeni
        model/efor fiilen uygulanmıyordu. Model/efor boş geçilirse eski imza
        (yalnız istem) birebir korunur — var olan eşlemeler düşmesin diye.
        """
        import hashlib

        material = text or ""
        extra = "|".join(p for p in (str(model or "").strip(),
                                     str(effort or "").strip()) if p)
        if extra:
            material = f"{material}|{extra}"
        return hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()[:16]

    def sync_prompt(self, conversation_id: str, provider: str, system_prompt: str) -> bool:
        """
        Sistem istemi ya da sağlayıcı değiştiyse eşlemeyi düşürür (Faz 9.9).

        Neden gerekli: `claude --system-prompt-snapshot` varsayılan olarak açık
        ve belgesi net — *"Record the system prompt once per conversation and
        reuse it verbatim on every request and resume… even when a later launch
        passes different text."* Yani süren bir oturum `--resume` ile
        sürdürülürse ESKİ (kirli, Claude Code varsayılanını içeren) istemi
        taşımaya devam eder; saf kip canlıda etkisiz görünürdü. Eşleme
        düşürülünce köprü `--resume` vermez ve yeni oturum temiz istemle açılır.

        Dönüş: eşleme düşürüldüyse True.
        """
        provider = (provider or "").strip().lower()
        if not conversation_id or not provider:
            return False
        signature = self.prompt_signature(system_prompt)
        with self._lock:
            data = self._load()
            entry = data.get(conversation_id)
            if not isinstance(entry, dict) or not entry.get(provider):
                return False
            previous = str(entry.get("prompt_signature") or "")
            if previous == signature:
                return False
            if previous:
                logger.info(
                    "Sistem istemi değişti; '%s' konuşması yeniden açılacak.",
                    conversation_id,
                )
                data.pop(conversation_id, None)
                self._save(data)
                return True
            # İlk kayıt: imza yoktu, yalnızca yazılır (eski eşlemeler düşmesin).
            entry["prompt_signature"] = signature
            data[conversation_id] = entry
            self._save(data)
            return False

    def set_prompt_signature(self, conversation_id: str, system_prompt: str) -> None:
        """Yeni oturum açıldıktan sonra imzayı kaydeder."""
        if not conversation_id:
            return
        signature = self.prompt_signature(system_prompt)
        with self._lock:
            data = self._load()
            entry = dict(data.get(conversation_id) or {})
            entry["prompt_signature"] = signature
            entry["updated_at"] = _now()
            data[conversation_id] = entry
            self._save(data)

    def forget(self, conversation_id: str) -> bool:
        with self._lock:
            data = self._load()
            if conversation_id not in data:
                return False
            data.pop(conversation_id)
            self._save(data)
            return True


conversation_map = ConversationMap()


class AgentSessionStore:
    """
    Ajan başına KALICI oturum kimliği (`Entropy/Board/agents/<ad>/session.json`).

    Neden ayrı depo, `ConversationMap` değil: eşlemenin anahtarı KONUŞMA
    kimliği, burada ise AJAN adı. İkisini aynı dosyada birleştirmek "aynı
    anahtar uzayında iki farklı kavram" demekti; çakışmayı önlemek için bu depo
    kendi dosyasında durur ve `ConversationMap`e yazarken `agent:<ad>` anahtarı
    kullanılır.

    Neden diskte: Faz 11 öncesi kimlik GÖREV başına ve BELLEKTEYDİ
    (`claude_bridge._background_conversations`); uygulama kapanınca ajanın
    konuşması yok oluyordu. Kullanıcının isteği bunun tersi: "uygulama kapanıp
    açılsa da aynı oturum sürsün".

    Şema:

        {"claude": {"session_id": "<uuid>", "signature": "<sha1[:16]>",
                    "model": "...", "effort": "...", "cwd": "...",
                    "updated_at": "..."},
         "agy":    {"conversation_id": "...", ...}}

    `cwd` ZORUNLU alan: Claude'un oturum deposu çalışma dizinine göre anahtarlı
    (`~/.claude/projects/<slug(cwd)>/<uuid>.jsonl`). Kart bir worktree'de
    koşuyorsa cwd farklıdır ve o koşu ajanın kalıcı kimliğine DOKUNMAZ — aksi
    hâlde her worktree ajanın konuşmasını başka bir klasöre dağıtırdı.
    """

    NAMESPACE = "entropy-agent:"

    def __init__(self, vault_path=None):
        self.vault_path = vault_path

    def path_for(self, agent: str) -> Path:
        from entropy.core import paths as _paths

        return _paths.agent_session_path(agent, self.vault_path)

    @classmethod
    def claude_session_id(cls, agent: str) -> str:
        """
        Ajanın deterministik Claude oturum kimliği.

        `uuid5` seçildi çünkü CLI `--session-id <uuid>` ile kimliği BİZİM
        atamamıza izin veriyor; böylece kimliği akıştan yakalama yarışı hiç
        doğmuyor ve dosya silinse bile kimlik yeniden hesaplanabiliyor.
        """
        import uuid as _uuid

        return str(_uuid.uuid5(_uuid.NAMESPACE_URL,
                               f"{cls.NAMESPACE}{str(agent or '').strip().lower()}"))

    def load(self, agent: str) -> Dict[str, dict]:
        try:
            data = json.loads(self.path_for(agent).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, agent: str, provider: str) -> Dict[str, object]:
        entry = self.load(agent).get(str(provider or "").strip().lower())
        return dict(entry) if isinstance(entry, dict) else {}

    def record(self, agent: str, provider: str, session_id: str = "",
               conversation_id: str = "", signature: str = "", model: str = "",
               effort: str = "", cwd: str = "") -> None:
        """Oturumu kaydeder/yeniler (atomik: geçici dosya + `os.replace`)."""
        provider = str(provider or "").strip().lower()
        if not agent or not provider:
            return
        path = self.path_for(agent)
        data = self.load(agent)
        entry = dict(data.get(provider) or {})
        if session_id:
            entry["session_id"] = str(session_id)
        if conversation_id:
            entry["conversation_id"] = str(conversation_id)
        if signature:
            entry["signature"] = str(signature)
        entry["model"] = str(model or entry.get("model") or "")
        entry["effort"] = str(effort or entry.get("effort") or "")
        entry["cwd"] = str(cwd or entry.get("cwd") or os.getcwd())
        entry["updated_at"] = _now()
        data[provider] = entry
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".json.tmp{os.getpid()}")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            logger.warning("Ajan oturumu yazılamadı: %s", path)

    def forget(self, agent: str, provider: str = "") -> bool:
        """
        Oturumu düşürür — model/efor/istem değişince ve ajan düzenlenince.

        `provider` boşsa ajanın TÜM sağlayıcı oturumları düşer.
        """
        path = self.path_for(agent)
        data = self.load(agent)
        if not data:
            return False
        if provider:
            if str(provider).strip().lower() not in data:
                return False
            data.pop(str(provider).strip().lower(), None)
        else:
            data = {}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            return True
        except OSError:
            return False

    def run_kwargs(self, agent: str, provider: str, model: str = "",
                   effort: str = "", system_prompt: str = "",
                   cwd: str = "") -> Dict[str, object]:
        """
        Bu koşuda köprüye geçilecek oturum kwarg'ları.

        - imza aynı + kimlik var → `conversation_id` (Claude'da `--resume`,
          agy'de `--conversation`)
        - imza farklı ya da kimlik yok → Claude'da `session_id` (yeni oturum,
          kimliği biz atarız), agy'de boş (kimlik akıştan yakalanacak)
        """
        provider = str(provider or "").strip().lower()
        if not agent or provider not in PROVIDERS:
            return {}
        signature = ConversationMap.prompt_signature(system_prompt, model, effort)
        entry = self.get(agent, provider)
        same = str(entry.get("signature") or "") == signature and bool(entry.get("signature"))
        if provider == "claude":
            prior = str(entry.get("session_id") or "")
            if same and prior:
                self.record(agent, provider, session_id=prior,
                            signature=signature, model=model, effort=effort, cwd=cwd)
                return {"conversation_id": prior}
            # Yeni oturum: kimliği ÖNCEDEN atıyoruz, sonraki koşu sürdürecek.
            # QA 11-C/D kanıtı: aynı kimliği ikinci kez `--session-id` ile
            # vermek CLI'ı "Session ID ... is already in use." ile öldürüyordu
            # (ajanın İKİNCİ kartı her zaman `failed`). İmza düştüyse kimlik
            # ZATEN harcanmıştır; taze bir uuid üretilir.
            if prior:
                import uuid as _uuid

                session_id = str(_uuid.uuid4())
            else:
                session_id = self.claude_session_id(agent)
            self.record(agent, provider, session_id=session_id, signature=signature,
                        model=model, effort=effort, cwd=cwd)
            return {"session_id": session_id}
        conversation_id = str(entry.get("conversation_id") or "")
        if same and conversation_id:
            return {"conversation_id": conversation_id}
        # agy: kimlik önceden atanamıyor; imzayı şimdi yaz, kimliği koşu sonunda
        # `record_captured` yakalayacak.
        self.record(agent, provider, signature=signature, model=model,
                    effort=effort, cwd=cwd)
        self.forget_conversation(agent, provider)
        return {}

    def forget_conversation(self, agent: str, provider: str) -> None:
        """Yalnızca yakalanmış kimliği siler; imza/model kaydı kalır."""
        provider = str(provider or "").strip().lower()
        data = self.load(agent)
        entry = dict(data.get(provider) or {})
        if not entry.pop("conversation_id", None):
            return
        data[provider] = entry
        try:
            self.path_for(agent).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def record_captured(self, agent: str, provider: str, session_id: str,
                        cwd: str = "") -> None:
        """Koşu sonunda akıştan yakalanan kimliği kaydeder (agy yolu)."""
        if not session_id:
            return
        self.record(agent, provider, conversation_id=str(session_id),
                    session_id=str(session_id) if provider == "claude" else "",
                    cwd=cwd)


_agent_session_store = AgentSessionStore()


def agent_session_store(vault_path=None) -> AgentSessionStore:
    """
    Varsayılan ajan oturum deposu. `vault_path` verilirse HER ZAMAN yeni örnek:
    testler yalıtılmış kasada koşuyor, önbellek sızarsa fikstürler karışır.
    """
    if vault_path is not None:
        return AgentSessionStore(vault_path)
    return _agent_session_store


# ---------------------------------------------------------------------------
# Agentic sohbet
# ---------------------------------------------------------------------------

ENTROPY_ROLE = "[Entropy AI]"


def office_role(name: str) -> str:
    return f"[🏢 {name}]"


@dataclass
class ChatTurn:
    """Agentic sohbetin tek turu: kim konuştu, ne dedi, hangi sağlayıcıda."""

    role: str
    provider: str
    text: str
    at: str = field(default_factory=_now)


class AgenticChat:
    """
    Entropy AI (aktif sağlayıcı) ile bir ofis/ajan (kendi sağlayıcısı) arasında
    SIRALI tur alışverişi.

    İki taraf farklı CLI'larda koşar ve birbirinin bağlamını göremez; aktarım bu
    yüzden posta kutusudur: Entropy'nin sorusu ofis kutusuna `question` olarak
    düşer, karşı taraf yanıtını Entropy kutusuna `report` olarak bırakır. Her iki
    taraf da AYNI `conversation_id` altında kendi sağlayıcı oturumunu sürdürür
    (`ConversationMap`), böylece "iki sağlayıcı tek konuşma" görüntüsü oluşur.

    Turlar sıralıdır (aynı anda iki çağrı yok): paralel koşsalardı ikisi de
    diğerinin henüz yazmadığı mesajı okuyordu.
    """

    def __init__(
        self,
        conversation_id: str,
        target: str,
        target_kind: str = "office",
        vault_path=None,
        bridge_factory: Optional[Callable] = None,
        cmap: Optional[ConversationMap] = None,
    ):
        self.conversation_id = conversation_id
        self.target = target
        self.target_kind = target_kind
        self.vault_path = vault_path
        self.bridge_factory = bridge_factory
        self.map = cmap or conversation_map
        self.turns: List[ChatTurn] = []

    # -- yardımcılar -------------------------------------------------------

    def _target_provider(self) -> str:
        from entropy.agents.offices import OfficeRegistry
        from entropy.agents.registry import AgentRegistry

        try:
            if self.target_kind == "office":
                spec = (OfficeRegistry(vault_path=self.vault_path) if self.vault_path
                        else OfficeRegistry()).get(self.target)
                return (spec.default_provider if spec else "agy") or "agy"
            spec = (AgentRegistry(vault_path=self.vault_path) if self.vault_path
                    else AgentRegistry()).get(self.target)
            return (spec.provider if spec else "agy") or "agy"
        except Exception:
            return "agy"

    def _responder(self) -> str:
        """Yanıtı üretecek ajan adı: ofisin orkestratörü ya da ajanın kendisi."""
        if self.target_kind != "office":
            return self.target
        from entropy.agents.offices import OfficeRegistry

        try:
            spec = (OfficeRegistry(vault_path=self.vault_path) if self.vault_path
                    else OfficeRegistry()).get(self.target)
            return (spec.orchestrator if spec else "") or self.target
        except Exception:
            return self.target

    def _bridge(self, provider: str):
        from entropy.agents.tasks import TaskBoard

        return TaskBoard.bridge_for(provider, bridge_factory=self.bridge_factory)

    def transcript(self) -> str:
        return "\n\n".join(f"{t.role} ({t.provider}): {t.text}" for t in self.turns)

    # -- tur ----------------------------------------------------------------

    def send(self, text: str, timeout: float = 300.0) -> Optional[ChatTurn]:
        """
        Entropy'den karşı tarafa bir tur; karşı tarafın yanıtını döndürür.

        Bloke eder (köprü geri çağrısını bekler) çünkü sohbet sıralıdır. Çağıran
        arayüz değil, arka plan iş parçacığıdır.
        """
        from entropy.agents.mailbox import (
            Message,
            entropy_mailbox,
            office_mailbox,
            agent_mailbox,
            text_part,
        )

        self.turns.append(ChatTurn(ENTROPY_ROLE, self._entropy_provider(), text))

        box = (office_mailbox(self.target, vault_path=self.vault_path)
               if self.target_kind == "office"
               else agent_mailbox(self.target, vault_path=self.vault_path))
        box.send(Message(
            task_id=self.conversation_id,
            from_="entropy",
            to=self.target,
            role="user",
            kind="question",
            parts=[text_part(text)],
            status="submitted",
        ))

        provider = self._target_provider()
        bridge = self._bridge(provider)
        if bridge is None:
            return None

        prompt = (
            f"[AGENTIC SOHBET — {self.target}]\n"
            "Entropy AI seninle konuşuyor. Kısa ve doğrudan yanıt ver; plan JSON'u "
            "isteme, yalnızca sorulanı yanıtla.\n\n"
            f"[KONUŞMA]\n{self.transcript()}\n\n[YANITIN]"
        )

        done = threading.Event()
        captured: Dict[str, object] = {}

        def _on_result(full_text: str, ok: bool) -> None:
            captured["text"] = full_text or ""
            captured["ok"] = bool(ok)
            done.set()

        kwargs: Dict[str, object] = dict(
            task_id=f"chat-{self.conversation_id}-{len(self.turns)}",
            task_name=f"Agentic sohbet: {self.target}",
            prompt=prompt,
            mode="accept-edits",
            on_result=_on_result,
            save_report=False,
            agent=self._responder() or None,
        )
        # Devam bayrağı: karşı taraf kendi sağlayıcısında AYNI oturumu sürdürsün.
        session = self.map.get(self.conversation_id, provider)
        if session:
            from entropy.agents.tasks import _accepts_kwarg

            if _accepts_kwarg(bridge.send_background_task_async, "conversation_id"):
                kwargs["conversation_id"] = session
        try:
            bridge.send_background_task_async(**kwargs)
        except Exception:
            logger.exception("Agentic sohbet turu başlatılamadı: %s", self.target)
            return None
        if not done.wait(timeout=timeout):
            return None

        answer = str(captured.get("text") or "").strip()
        turn = ChatTurn(office_role(self.target), provider, answer)
        self.turns.append(turn)

        # Karşı tarafın oturum kimliği köprüde oluştuysa eşlemeye yazılır;
        # bir sonraki tur aynı oturumu sürdürür.
        new_session = getattr(bridge, "current_session_id", None) or getattr(
            bridge, "current_conversation_id", None
        )
        if new_session:
            self.map.set(self.conversation_id, provider, str(new_session))

        from entropy.agents.mailbox import Message as _Msg, entropy_mailbox as _inbox

        try:
            _inbox(vault_path=self.vault_path).send(_Msg(
                task_id=self.conversation_id,
                from_=self.target,
                to="entropy",
                role="agent",
                kind="report",
                parts=[text_part(answer)],
                status="completed" if captured.get("ok") else "failed",
            ))
        except Exception:
            logger.warning("Agentic sohbet yanıtı gelen kutusuna yazılamadı.")
        return turn

    def _entropy_provider(self) -> str:
        try:
            from entropy.core.config import config

            return (getattr(config, "provider", "agy") or "agy").lower()
        except Exception:
            return "agy"

    def close(self, status: str = "completed") -> None:
        """Sohbeti terminal olayla kapatır (terminal sözleşmesi burada da geçerli)."""
        from entropy.agents.mailbox import emit_terminal

        emit_terminal(
            self.conversation_id,
            self.target,
            status,
            f"Agentic sohbet kapandı ({len(self.turns)} tur).",
            vault_path=self.vault_path,
        )
