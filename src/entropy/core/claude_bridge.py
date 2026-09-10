"""
Claude Code CLI köprüsü (başsız / `-p` modu).

AGY köprüsüyle aynı sözleşmeyi (`entropy.core.provider.ProviderBridge`) uygular:
arayüz, zamanlayıcı ve yetenek katmanı hangi sağlayıcının açık olduğunu bilmez.
Farklar CLI'ın kendisinde ve tamamen bu dosyada kapsanır:

  bayrak                     agy                     claude
  -----------------------    --------------------    ---------------------------
  başsız çalışma             -p                      -p / --print
  akış biçimi                --output-format         --output-format stream-json
                             stream-json             (+ --verbose şart)
  stdin akışı                --input-format          --input-format stream-json
                             stream-json
  izin kipi                  --mode accept-edits     --permission-mode acceptEdits
  izin atlama                --dangerously-skip-     --dangerously-skip-permissions
                             permissions
  ek dizin                   --add-dir               --add-dir
  model                      --model                 --model
  alt ajan                   --agent                 --agent
  oturum devamı              (konuşma kimliği)       --resume <session-id>
  oturum durumu              (yok)                   claude auth status --json

Akış olaylarının şeması da farklı: agy `{"event": "step_update"|"result"}`
gönderirken Claude Code `{"type": "system"|"assistant"|"user"|"result"}` gönderir
ve metin `message.content[]` içindeki `text` bloklarındadır. Bu dosya iki şemayı
da AYNI `bus` sinyallerine çevirir; arayüzde tek satır sağlayıcıya özel kod yok.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from entropy.platform.proc import popen_kwargs
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject

import sys as _sys

import entropy.core.config  # noqa: F401  (alt modülün yüklenmesi için)
from entropy.core.config import config

# entropy.core paketi 'config' adını config NESNESİNE bağlar; sohbet geçmişi
# yardımcıları için gerçek modül gerekiyor (agy_bridge ile aynı tuzak).
config_module = _sys.modules["entropy.core.config"]
from entropy.core.event_bus import bus
#: `[OTONOM PLANLI GÖREV: <ad>]` etiketi. `.lower()` kullanılmaz: Türkçe
#: "I" harfi "i"ye düşüp kalıbı kaçırıyor (Faz 13-A).
TASK_PROMPT_RE = re.compile(r"\[OTONOM\s+PLANLI\s+GÖREV:\s*([^\]]+)\]", re.IGNORECASE)

from entropy.core.report_title import (
    derive_report_title,
    safe_filename_title,
    save_session_note,
)
from entropy.core.masking import mask_tool_output
from entropy.core.project_lock import LOCK_TIMEOUT_MARKER, project_lock_manager

# Arka plan görevinin proje kilidini bekleyeceği süre (sn); bkz. agy_bridge.
BACKGROUND_LOCK_TIMEOUT = 60.0
from entropy.core.provider import (
    INTERACTIVE_IDLE_TIMEOUT_S,
    InteractiveSession,
    InteractiveSessionRegistry,
    ProviderCommonMixin,
    agent_definitions_dir,
    followup_rejection,
    list_agent_definitions,
)
from entropy.core.task_ledger import TaskStatus, task_ledger

# Windows CreateProcess sınırı AGY köprüsündekiyle aynı gerekçeyle burada da
# geçerli; eşik bilinçli olarak ortak tutuldu (bkz. agy_bridge.ARGV_PROMPT_SAFE_LIMIT).
ARGV_PROMPT_SAFE_LIMIT = 26_500

# Arka plan görevi başına araç adımı tavanı (Faz 8 / 1). AGY köprüsündeki
# `MAX_STEPS_MARKER` ile AYNI dizge: kart katmanı iki sağlayıcıyı ayırt etmeden
# "adım sınırına takıldı" hâlini tanıyabilsin diye.
MAX_STEPS_MARKER = "[ADIM SINIRI]"

# Claude Code CLI'ında adım/tur tavanı bayrağı YOK. `claude --help` (2026-09,
# bu makinedeki sürüm) çıktısında `--max-turns` geçmiyor; bütçe tarafında
# yalnızca şu satır var:
#   "--max-budget-usd <amount>   Maximum dollar amount to spend on API"
# `--help` her bilinmeyen bayrağı sessizce yutup kullanım metni bastığı için
# (kontrol probu `--zzz-bogus` de exit 0 verdi) bayrağın varlığı yardımla
# doğrulanamıyor; var olmayan bir bayrağı argv'ye koymak süreci daha ilk
# saniyede düşürürdü. Bu yüzden yaptırım AKIŞ TARAFINDA sayılır ve argv bayrağı
# bu anahtar açıkça True yapılmadıkça eklenmez.
CLAUDE_SUPPORTS_MAX_TURNS = False

# `--append-system-prompt` argv'de taşındığı için bilişsel bağlam sınırsız
# olamaz: prompt + sistem istemi birlikte Windows komut satırı sınırına yazılır.
# 6000 karakter (~1500 token) AGY köprüsündeki bütçeyle aynı; orada da bağlam
# bu değerle kırpılıyor.
SYSTEM_PROMPT_CONTEXT_LIMIT = 6000

# Windows CreateProcess komut satırını 32.767 karakterle sınırlar; aşıldığında
# süreç hiç başlamaz ve Python `OSError: [WinError 206] The filename or
# extension is too long` fırlatır. Kullanıcının gördüğü "The command line is too
# long" hatası buydu: bilişsel bağlam + ajan manifesti `--append-system-prompt`
# ile argv'ye giriyordu. Eşik bilinçli olarak sınırın epey altında: argv'ye
# ayrıca --add-dir yolları, model ve oturum kimliği de ekleniyor.
ARGV_TOTAL_SAFE_LIMIT = 28_000

# Bu uzunluğu aşan sistem istemi argv'ye HİÇ yazılmaz, doğrudan dosyaya taşınır.
# Tek başına sınırı aşmasa bile prompt'la toplandığında aşabilir; ayrıca dosya
# yolu argv'yi sabit ~120 karakterde tutar.
SYSTEM_PROMPT_ARGV_LIMIT = 4_000

# `claude --help` çıktısı yalnızca `--append-system-prompt <prompt>` ve
# `--system-prompt <prompt>` belgeliyor; ancak CLI ikilisi (bin/claude.exe)
# `--append-system-prompt-file` / `--system-prompt-file` seçeneklerini de
# tanıyor ("Cannot use both --append-system-prompt and
# --append-system-prompt-file", "Append system prompt file not found" hata
# metinleri ikilinin içinde). Dosya yolu tercih edilir; bayrağı tanımayan bir
# sürümde bu sabit False yapılırsa köprü sistem istemini stdin'deki ilk
# kullanıcı mesajının başına [SİSTEM BAĞLAMI] bloğu olarak koyar (aşağıdaki
# yedek yol) ve argv yine kısa kalır.
CLAUDE_SUPPORTS_SYSTEM_PROMPT_FILE = True

# Sistem istemi dosyasının bayrağı ve stdin yedeğinin blok başlığı.
SYSTEM_PROMPT_FILE_FLAG = "--append-system-prompt-file"
SYSTEM_CONTEXT_BLOCK_HEADER = "[SİSTEM BAĞLAMI]"

# "Entropy Saf Kip" bayrağı: varsayılan sistem istemini EKLEMEZ, DEĞİŞTİRİR.
# `--help` çıktısında belgesiz ama ikilide gerçek; kontrol probuyla ayrıldı:
#   claude -p x --system-prompt-file /yok.txt
#     -> "Error: System prompt file not found: ..."   (bayrak TANINIYOR)
#   claude --zzz-bogus-flag
#     -> "error: unknown option '--zzz-bogus-flag'"   (tanınmayan bayrak)
# Prob model çağırmadan hata verdiği için kota harcamaz.
REPLACE_SYSTEM_PROMPT_FILE_FLAG = "--system-prompt-file"

# Saf kipte argv'ye giren izolasyon bayrakları (hepsi `claude --help` ile
# doğrulandı; alıntılar Faz 9 araştırma raporu §2.2'de):
#   --strict-mcp-config   "Only use MCP servers from --mcp-config, ignoring all
#                          other MCP configurations"
#   --setting-sources     "Comma-separated list of setting sources to load
#                          (user, project, local)."  -> "" = hiçbiri
#   --disable-slash-commands  "Disable all skills"  (32 yetenek kataloğu ~3.8k tok)
#   --tools               "Specify the list of available tools from the built-in
#                          set. Use \"\" to disable all tools, \"default\" ..."
#   --disallowedTools     "Comma or space-separated list of tool names to deny";
#                          "mcp__*" her MCP aracını kaldırır
#   --agents <json>       "JSON object defining custom agents"
#   --fallback-model      "Enable automatic fallback to specified model(s) when
#                          the default model is overloaded or not available"
# `--bare` BİLEREK KULLANILMAZ: abonelik oturumunu (OAuth/keychain) hiç okumaz,
# ANTHROPIC_API_KEY ister. Kullanıcının kimliği claude.ai aboneliği olduğu için
# saf kip `--bare` ile kurulamaz.
ISOLATION_FORBIDDEN_FLAGS = ("--bare",)

# Sohbet turunun araç seti. Salt okuma varsayılan; yazma niyeti tespit edilen
# turda düzenleme araçları eklenir. Varsayılan sistem istemi düştüğü için araç
# kümesini daraltmak modelin yanlış araç seçmesini de engelliyor.
CHAT_TOOLS_READONLY = ["Read", "Glob", "Grep", "WebFetch", "WebSearch"]
CHAT_TOOLS_WRITE = ["Edit", "Write", "Bash"]

# Kart izin kipine göre araç seti (`tools_policy` eşlemesiyle aynı anlam).
# Anahtarlar `normalize_permission_mode` ÇIKTISIDIR (CLI'ın kabul ettiği adlar).
CARD_TOOLS_BY_MODE = {
    "plan": CHAT_TOOLS_READONLY,
    "acceptEdits": CHAT_TOOLS_READONLY + CHAT_TOOLS_WRITE,
    "auto": CHAT_TOOLS_READONLY + CHAT_TOOLS_WRITE,
    "manual": CHAT_TOOLS_READONLY + CHAT_TOOLS_WRITE,
    "dontAsk": CHAT_TOOLS_READONLY + CHAT_TOOLS_WRITE,
    "bypassPermissions": CHAT_TOOLS_READONLY + CHAT_TOOLS_WRITE,
}

# Ana model kullanılamadığında otomatik düşülecek model.
CLAUDE_FALLBACK_MODEL = "claude-sonnet-5"

# `cache_read` token'ının maliyet ağırlığı. Anthropic önbellek okumasını taban
# girdi fiyatının onda birine yakın fiyatlıyor; tek toplamda tam fiyat sayılınca
# rozet 40k'lık bir önbellek okumasını 40k'lık taze girdi gibi gösteriyordu.
CACHE_READ_COST_WEIGHT = 0.1

# `claude --effort <level>`: --help çıktısında "Effort level for the current
# session (low, medium, high, xhigh, max)" olarak belgeli.
CLAUDE_EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]
DEFAULT_CLAUDE_EFFORT = "high"

# Entropy'nin iç kip adları -> Claude Code'un --permission-mode değerleri.
# Claude yalnızca listedeki değerleri kabul eder; eşleşmeyen ad verilirse süreç
# hiç başlamaz, bu yüzden bilinmeyen kip güvenli varsayılana düşürülür.
PERMISSION_MODE_MAP = {
    "accept-edits": "acceptEdits",
    "acceptedits": "acceptEdits",
    "acceptEdits": "acceptEdits",
    "plan": "plan",
    "read": "plan",
    "read-only": "plan",
    "auto": "auto",
    "manual": "manual",
    "dontAsk": "dontAsk",
    "bypass": "bypassPermissions",
    "bypassPermissions": "bypassPermissions",
}

# Sağlayıcının sunduğu modeller. `claude --model` hem tam ad hem takma ad kabul
# eder; kullanıcıya tam adlar gösterilir, takma adlar da geçerli girdi sayılır.
CLAUDE_MODELS = [
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-4-5",
]
CLAUDE_MODEL_ALIASES = {
    "opus": "claude-opus-5",
    "sonnet": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5",
    # Belgeli ek takma adlar (code.claude.com/docs/en/model-config). `--model`
    # bunları doğrudan kabul ediyor; Entropy tam ada çevirmez, geçerli sayar.
    "fable": "claude-fable-5-1",
    "best": "claude-opus-5",
    "default": "claude-opus-5",
    "opusplan": "claude-opus-5",
}


def build_stdin_prompt_payload(prompt: str) -> str:
    """
    `claude --input-format stream-json` için tek satırlık kullanıcı mesajı.

    AGY'nin `{"event": "user", ...}` şemasından farkı anahtarın `type` olması;
    Anthropic akış biçimi mesaj tiplerini `type` alanıyla ayırır.
    """
    return json.dumps(
        {"type": "user", "message": {"role": "user", "content": prompt}},
        ensure_ascii=False,
    ) + "\n"


def prompt_via_stdin(prompt: str) -> bool:
    """
    Prompt argv yerine stdin'den mi geçmeli?

    İki koşuldan biri yeterli:
    1. Uzunluk eşiği (argv sınırı),
    2. Prompt'ta SATIR SONU olması.

    (2) canlı koşuda bulundu: Windows'ta `claude` çalıştırılabiliri bir toplu iş
    sarmalayıcısıdır (`claude.CMD`) ve `subprocess` bu sarmalayıcıyı
    `cmd.exe` üzerinden başlatır. cmd.exe çok satırlı bir argümanı İLK SATIR
    SONUNDA keser: `-p "# ajan\n\n[GÖREV SÖZLEŞMESİ]..."` argümanından modele
    yalnızca `# ajan` ulaşıyor, görev metninin tamamı sessizce kayboluyordu
    (ölçüm: `.cmd` sarmalayıcı `['-p', 'satir1']`, `.exe` ise
    `['-p', 'satir1\\nsatir2\\nsatir3']` alıyor). Eşiğin altındaki her ofis alt
    kartı bu yüzden "bana görev metni verilmedi" diyerek başarısız oluyordu.
    Satır sonu içeren prompt stdin'deki NDJSON yolundan geçince argümanda metin
    kalmıyor ve kesilme olanaksızlaşıyor.
    """
    text = prompt or ""
    return len(text) > ARGV_PROMPT_SAFE_LIMIT or "\n" in text


def argv_length(cmd: List[str]) -> int:
    """
    Komut satırının CreateProcess'e yazılacak toplam uzunluğu (yaklaşık).

    Her argüman arasına bir boşluk, tırnaklanabilir argümanlar için de iki tırnak
    eklenir; ölçüm bilinçli olarak KÖTÜMSER, çünkü eşiği azıcık aşan bir argv
    süreç hiç başlamadan WinError 206 üretiyor.
    """
    total = 0
    for part in cmd:
        text = str(part)
        total += len(text) + 3  # boşluk + iki olası tırnak
    return total


def argv_too_long(cmd: List[str]) -> bool:
    return argv_length(cmd) > ARGV_TOTAL_SAFE_LIMIT


def build_system_context_block(system_prompt: str, prompt: str) -> str:
    """
    Sistem istemini kullanıcı mesajının BAŞINA gömer (dosya bayrağı yoksa yedek).

    Bayrak desteklenmediğinde tek güvenli yol budur: argv'de yalnızca kısa
    bayraklar kalır, uzun metin stdin'den NDJSON olarak akar.
    """
    if not system_prompt:
        return prompt
    return f"{SYSTEM_CONTEXT_BLOCK_HEADER}\n{system_prompt}\n[/SİSTEM BAĞLAMI]\n\n{prompt}"


def normalize_permission_mode(mode: Optional[str]) -> str:
    """Entropy kip adını Claude Code'un beklediği değere çevirir."""
    if not mode:
        return "acceptEdits"
    return PERMISSION_MODE_MAP.get(mode, PERMISSION_MODE_MAP.get(mode.lower(), "acceptEdits"))


def parse_usage(usage: Optional[dict]) -> Dict[str, int]:
    """
    Claude `usage` bloğunu Entropy'nin token muhasebesi sözlüğüne çevirir.

    Anthropic alan adları AGY'ninkilerle birebir aynı değil: önbellek iki kaleme
    ayrılır (`cache_creation_input_tokens` yazım, `cache_read_input_tokens`
    okuma) ve toplam alanı hiç gönderilmez. Toplam burada hesaplanır, yoksa
    rozet her turda 0 gösterirdi.
    """
    if not isinstance(usage, dict):
        return {}
    inp = int(usage.get("input_tokens", 0) or 0)
    out = int(usage.get("output_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", usage.get("cache_read_tokens", 0)) or 0)
    cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
    total = int(usage.get("total_tokens", 0) or 0) or (inp + out + cache_read + cache_write)
    return {
        "input_tokens": inp,
        "output_tokens": out,
        # Claude "thinking" token'ını ayrı raporlamaz; çıktıya dahildir.
        "thinking_tokens": int(usage.get("thinking_tokens", 0) or 0),
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_write,
        "total_tokens": total,
    }


class ClaudeCodeBridge(ProviderCommonMixin, QObject):
    """Entropy'yi yerel, oturumu açık Claude Code CLI'ına bağlar."""

    provider_name = "claude"

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        # OKUMA KAPISI (Faz 9.1). Yedek değerin KENDİSİ de doğrulanır: ayar
        # dosyası zehirlendiğinde (`provider_models["claude"] = "gemini-…"`)
        # yabancı-model koruması yedeğe düşüyor, yedek de zehirli olduğu için
        # `--model gemini-3.1-pro-high` argv'ye giriyor ve her koşu
        # `unrecognized_model` ile ölüyordu.
        default_model = getattr(config, "provider_models", {}).get("claude") or ""
        if not self._is_claude_model(default_model):
            default_model = CLAUDE_MODELS[0]
        current = getattr(config, "selected_model", "") or ""
        # Ayarlardaki model başka bir sağlayıcıya aitse (ör. gemini-*) buraya
        # taşınmaz: geçersiz --model değeri süreci başlatmadan hataya düşürür.
        self.selected_model: str = current if self._is_claude_model(current) else default_model
        self.current_model: str = self.selected_model
        # Akıl yürütme eforu ayardan gelir; geçersiz/eksik değer güvenli
        # varsayılana düşer, çünkü `--effort saçma` süreci hiç başlatmaz.
        effort = (getattr(config, "provider_effort", {}) or {}).get("claude", "")
        self.selected_effort: str = (
            effort if effort in CLAUDE_EFFORT_LEVELS else DEFAULT_CLAUDE_EFFORT
        )
        self.current_session_id: Optional[str] = None
        self.last_total_cost_usd: float = 0.0

        self.total_tokens_used: int = 0
        self.background_total_tokens: int = 0
        self.last_background_usage: Dict[str, int] = {}
        self.latest_input_tokens: int = 0
        self.latest_output_tokens: int = 0
        self.latest_thinking_tokens: int = 0
        self.latest_cache_read_tokens: int = 0
        self.latest_cache_creation_tokens: int = 0
        self.session_total_tokens: int = 0
        self.session_cache_tokens: int = 0
        # Maliyet ağırlıklı oturum toplamı: `cache_read` indirimli (0,1×) sayılır.
        self.session_cost_tokens: int = 0
        self.session_turn_count: int = 0
        self.last_cumulative_usage: Dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cache_read_tokens": 0,
            "total_tokens": 0,
        }

        self.active_project_dir: Path = Path(config.default_project_path)
        self.conversation_history: List[Dict[str, str]] = config_module.load_chat_history()
        self.last_active_skill: Optional[str] = None
        self.last_skill_confidence: float = 0.0

        self._current_process: Optional[subprocess.Popen] = None
        self._background_processes: Dict[str, subprocess.Popen] = {}
        # Etkileşimli kartlar (Faz 10-C): ilk sonuçtan sonra da canlı kalan
        # kart süreçleri; sahnedeki bölme bunlara yazar.
        self._interactive_sessions = InteractiveSessionRegistry()
        self._interactive_stream_meta: Dict[str, dict] = {}
        # Arka plan görevi başına sağlayıcı oturum kimliği (Faz 8 / 3). Ofis
        # harness'ı planlama çağrısı bitince buradan okuyup `state.json`'a
        # yazıyor; `on_result(text, ok)` sözleşmesi kimliği taşıyamıyor ve
        # sözleşmeyi genişletmek tüm sahte köprüleri kırardı.
        self._background_conversations: Dict[str, str] = {}
        self._is_running: bool = False
        self._shutting_down: bool = False
        self._side_threads: List[threading.Thread] = []
        self._prompt_queue: List[Tuple] = []
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._context_pressure_announced = False
        # Son turda kullanılan sistem isteminin parmak izi (Faz 9.9). Değişirse
        # `--resume` yapılmaz: snapshot açık olduğu için süren oturum eski
        # istemi aynen taşır ve saf kip canlıda etkisiz görünürdü.
        self._system_prompt_signature: Optional[str] = None

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------

    @staticmethod
    def _is_claude_model(name: str) -> bool:
        """
        Ad `claude --model`e verilebilir mi (Faz 9.1 — üç kapının süzgeci).

        Gerçek karar `config.is_claude_model_name`'de: aynı süzgeci açılışta
        `load_settings()` de kullanıyor ve köprüyü oradan içe aktaramaz.
        Takma adlar (`opus`, `fable`, `best`, `opusplan`) ve `opus[1m]` gibi
        bağlam ekleri de geçerli sayılır.
        """
        return config_module.is_claude_model_name(name)

    def find_claude_executable(self) -> str:
        """Claude Code CLI ikilisini PATH'te ya da npm global kurulumunda bulur."""
        path = shutil.which("claude") or shutil.which("claude.cmd") or shutil.which("claude.exe")
        if path:
            return path
        fallbacks = [
            Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd",
            Path(os.environ.get("APPDATA", "")) / "npm" / "claude",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "claude" / "claude.exe",
            Path.home() / ".local" / "bin" / "claude",
        ]
        for fb in fallbacks:
            try:
                if fb.exists():
                    return str(fb)
            except Exception:
                continue
        return "claude"

    @staticmethod
    def _creationflags() -> int:
        if os.name == "nt":
            return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return 0

    @staticmethod
    def process_env() -> Optional[Dict[str, str]]:
        """
        Claude CLI çağrılarının ortamı; `claude_config_dir` doluysa izole profil.

        `CLAUDE_CONFIG_DIR` Claude Code'un oturum ve ayar dizinini komple
        taşıyor. Ayar BOŞSA None döner ve süreç ortamı hiç kopyalanmaz —
        varsayılan davranış kullanıcının kendi profili olmalı, yoksa güncelleme
        herkesi habersizce çıkışa düşürürdü.
        """
        try:
            from entropy.core.config import config

            target = (getattr(config, "claude_config_dir", "") or "").strip()
        except Exception:
            return None
        if not target:
            return None
        env = dict(os.environ)
        env["CLAUDE_CONFIG_DIR"] = str(Path(target).expanduser())
        try:
            Path(target).expanduser().mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return env

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ------------------------------------------------------------------
    # Sözleşme: durum
    # ------------------------------------------------------------------

    def fetch_available_models(self) -> List[str]:
        """
        Sağlayıcının model listesi.

        Claude Code model listesini sorgulanabilir bir komutla sunmuyor (`claude
        --help` yalnızca `--model` bayrağını belgeliyor); liste bu yüzden sabit
        ve takma adlarla birlikte verilir. Arayüzdeki combo düzenlenebilir
        olduğu için kullanıcı yeni bir tam ad da yazabilir.
        """
        return list(CLAUDE_MODELS) + sorted(CLAUDE_MODEL_ALIASES.keys())

    def auth_status(self) -> Dict[str, object]:
        """
        `claude auth status --json` çıktısını okur.

        Kota harcamaz: bu komut yerel kimlik bilgisine bakar, model çağırmaz.
        Dönüş her zaman en az {"provider", "logged_in"} taşır; CLI yoksa ya da
        çıktı bozuksa hata metni "error" alanında verilir.
        """
        claude_bin = self.find_claude_executable()
        try:
            res = subprocess.run(
                [claude_bin, "auth", "status", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **popen_kwargs(creationflags=self._creationflags(),
                               env=self.process_env(), timeout=20),
            )
        except Exception as e:
            return {"provider": "claude", "logged_in": False, "error": str(e)}

        raw = (res.stdout or "").strip()
        try:
            data = json.loads(raw)
        except Exception:
            return {
                "provider": "claude",
                "logged_in": False,
                "error": (res.stderr or raw or "auth status çıktısı okunamadı")[:300],
            }
        return {
            "provider": "claude",
            "logged_in": bool(data.get("loggedIn")),
            "auth_method": data.get("authMethod"),
            "account": data.get("email"),
            "subscription": data.get("subscriptionType"),
            "org": data.get("orgName"),
            "raw": data,
        }

    def set_model(self, model_name: str) -> bool:
        """
        YAZMA KAPISI (Faz 9.1): sağlayıcıya ait olmayan adı reddeder.

        Üst çubuğun model kutusu düzenlenebilir; oraya elle yazılan bir agy
        modeli eskiden doğrudan `provider_models["claude"]`e yazılıyordu ve
        ayar dosyasını kalıcı olarak zehirliyordu. Reddedilen ad ayara YAZILMAZ,
        köprünün modeli değişmez; kullanıcı yalnızca bir uyarı görür.
        """
        name = (model_name or "").strip()
        if not self._is_claude_model(name):
            bus.terminal_output_received.emit(
                f"\n[Model Reddedildi]: '{model_name}' bir Claude modeli değil; "
                f"seçim '{self.selected_model}' olarak kaldı.\n"
            )
            return False
        self.selected_model = name
        self.current_model = name
        config.selected_model = name
        try:
            config.provider_models["claude"] = name
        except Exception:
            pass
        config.save_settings()
        bus.model_detected.emit(name)
        return True

    def model_for_run(self, model_name: Optional[str]) -> str:
        """
        Bu koşuda kullanılacak `--model` değeri (kart modeli > oturum modeli).

        Kartın `model` alanı yürütmeye hiç geçmiyordu (araştırma §1.4); köprü
        üst çubuğun modelini kullanıyordu. Yabancı ad buraya kadar gelirse
        sessizce oturum modeline düşülür — argv'ye asla geçersiz ad girmez.
        """
        name = (model_name or "").strip()
        if name and self._is_claude_model(name):
            return name
        return self.selected_model

    @staticmethod
    def describe_launch_error(exc: BaseException) -> str:
        """
        Süreç başlatma hatasını kullanıcının okuyabileceği Türkçe metne çevirir.

        WinError 206 özel olarak açıklanır: kullanıcı "The command line is too
        long" satırından sorunun bağlam boyutu olduğunu anlayamıyordu.
        """
        winerror = getattr(exc, "winerror", None)
        if winerror == 206 or "too long" in str(exc).lower():
            return (
                "Komut satırı Windows sınırını aştı, bu tur başlatılamadı. "
                "Sistem bağlamı dosyaya/stdin'e taşınacak şekilde ayarlandı; "
                "mesajı tekrar gönderebilirsiniz."
            )
        return f"Claude köprüsü bu turu çalıştıramadı: {exc}"

    def effort_levels(self) -> List[str]:
        """`claude --effort` seviyeleri (--help ile doğrulandı)."""
        return list(CLAUDE_EFFORT_LEVELS)

    def set_effort(self, level: str) -> bool:
        """
        Kalıcı efor seviyesini ayarlar; geçersiz seviye reddedilir.

        Dönüş True (sözleşme: `set_effort(level) -> bool`, agy köprüsüyle ortak).
        Claude'da efor ayrı bir bayraktır (`--effort`), model adına dokunulmaz.
        """
        low = (level or "").strip().lower()
        if low not in CLAUDE_EFFORT_LEVELS:
            raise ValueError(
                f"Geçersiz efor '{level}'. Geçerli: {', '.join(CLAUDE_EFFORT_LEVELS)}."
            )
        self.selected_effort = low
        try:
            config.provider_effort["claude"] = low
            config.save_settings()
        except Exception:
            pass
        return True

    def set_project_directory(self, project_path: Path | str) -> None:
        self.active_project_dir = Path(project_path).resolve()
        config.default_project_path = self.active_project_dir
        config.save_settings()
        bus.project_changed.emit(str(self.active_project_dir))
        bus.terminal_output_received.emit(
            f"\n[Proje Değiştirildi]: Çalışma alanı '{self.active_project_dir.name}' "
            f"({self.active_project_dir}) olarak ayarlandı.\n"
        )

    def agent_definitions_dir(self) -> Path:
        return agent_definitions_dir("claude", self.active_project_dir)

    def list_agent_definitions(self) -> List[str]:
        return list_agent_definitions("claude", self.active_project_dir)

    def reset_conversation(self) -> None:
        """Yeni konuşma: oturum kimliği düşer, geçmiş arşive taşınır."""
        self.current_session_id = None
        self.last_archived_chat = config_module.archive_chat_history()
        self.conversation_history = []
        self.total_tokens_used = 0
        self.latest_input_tokens = 0
        self.latest_output_tokens = 0
        self.latest_cache_read_tokens = 0
        self.session_total_tokens = 0
        self.session_cache_tokens = 0
        self.session_cost_tokens = 0
        self.session_turn_count = 0
        self._context_pressure_announced = False
        self._system_prompt_signature = None
        self._prompt_queue.clear()
        bus.token_usage_updated.emit(0)
        bus.chat_history_cleared.emit()

    # ------------------------------------------------------------------
    # Komut kurulumu
    # ------------------------------------------------------------------

    def build_command(
        self,
        prompt: str,
        mode: str = "accept-edits",
        project_dir: Optional[Path] = None,
        agent: Optional[str] = None,
        resume: bool = False,
        resume_id: Optional[str] = None,
        skip_permissions: bool = False,
        extra_dirs: Optional[List[str]] = None,
        append_system_prompt: Optional[str] = None,
        mcp_config: Optional[str] = None,
        max_steps: Optional[int] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[str]] = None,
        agents_json: Optional[str] = None,
        effort: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[str]:
        """
        Başsız bir Claude Code çağrısının argv'sini kurar.

        `--verbose` bilinçli: `--print` ile `--output-format stream-json`
        birleştiğinde CLI ara olayları yalnızca ayrıntılı kipte yayınlar; onsuz
        akıştan tek bir `result` satırı gelir ve araç/düşünce telemetrisi hiç
        görünmez.

        `system_prompt` (Faz 9.2) varsayılan sistem istemini DEĞİŞTİRİR
        (`--system-prompt-file`); `append_system_prompt` ise ona EKLER. İkisi
        birlikte verilirse — CLI da bunu reddeder — değiştirme kazanır ve ek
        metin onun sonuna eklenir. Değiştirme yalnızca `config.claude_isolated`
        açıkken uygulanır; kapalıyken Faz 8 davranışı (ekleme) aynen sürer, geri
        dönüş yolu bilinçli olarak tek ayar.
        """
        isolated = bool(getattr(config, "claude_isolated", False))
        if system_prompt and not isolated:
            # İzolasyon kapalı: değiştirme yerine eski ekleme yoluna dön.
            append_system_prompt = system_prompt if not append_system_prompt else (
                f"{system_prompt}\n\n{append_system_prompt}"
            )
            system_prompt = None
        elif system_prompt and append_system_prompt:
            system_prompt = f"{system_prompt}\n\n{append_system_prompt}"
            append_system_prompt = None

        cmd = [
            self.find_claude_executable(),
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--permission-mode", normalize_permission_mode(mode),
        ]
        run_model = self.model_for_run(model)
        if run_model:
            cmd.extend(["--model", run_model])
            if isolated:
                # Ana model aşırı yüklendiğinde tur ölmesin; belge: "Enable
                # automatic fallback ... when the default model is overloaded
                # or not available".
                cmd.extend(["--fallback-model", CLAUDE_FALLBACK_MODEL])
        # Erişilebilir dizinler. Saf kipte süreç NÖTR bir çalışma dizininde koşar
        # (bkz. run_cwd), bu yüzden proje kökü ve kasa AÇIKÇA verilmelidir; aksi
        # hâlde model "C:\\EntropiAI için okuma izni verilmedi" / "Obsidian kasası
        # izinli dizinlerimde değil" diyerek kendi exe klasörüne düşüyordu.
        seen_dirs = []

        def _add_dir(value) -> None:
            if not value:
                return
            text = str(value)
            if text in seen_dirs:
                return
            seen_dirs.append(text)
            cmd.extend(["--add-dir", text])

        if project_dir is not None:
            _add_dir(project_dir)
        if isolated:
            for d in self.isolation_read_dirs():
                _add_dir(d)
        for d in extra_dirs or []:
            _add_dir(d)
        if agent:
            cmd.extend(["--agent", agent])
        if system_prompt:
            # DEĞİŞTİRME yolu: Claude Code'un kendi 12.4k karakterlik istemi
            # (ve içindeki `# auto memory` bloğu) hiç gelmez. Metin her zaman
            # dosyaya yazılır — argv'de taşınırsa `claude.CMD` sarmalayıcısı çok
            # satırlı argümanı ilk satır sonunda keser.
            path = (
                self.write_system_prompt_file(system_prompt)
                if CLAUDE_SUPPORTS_SYSTEM_PROMPT_FILE
                else None
            )
            if path:
                cmd.extend([REPLACE_SYSTEM_PROMPT_FILE_FLAG, str(path)])
            elif len(system_prompt) <= SYSTEM_PROMPT_ARGV_LIMIT and "\n" not in system_prompt:
                cmd.extend(["--system-prompt", system_prompt])
            else:
                # Yedek yol: dosya yazılamadı ve metin argv'ye sığmıyor. Kimliği
                # kaybetmektense kullanıcı mesajının başına blok olarak göm.
                p_idx = cmd.index("-p")
                cmd[p_idx + 1] = build_system_context_block(system_prompt, cmd[p_idx + 1])
        if append_system_prompt:
            # Uzun sistem istemi argv'ye HİÇ girmez: bilişsel bağlam + ajan
            # manifesti buradan geçtiği için "command line is too long" hatası
            # tam olarak bu satırda doğuyordu.
            # Satır sonu koşulu uzunluk koşuluyla aynı nedenle var: `claude.CMD`
            # toplu iş sarmalayıcısı çok satırlı argümanı ilk satır sonunda
            # kesiyor (bkz. `prompt_via_stdin`). Kısa ama çok satırlı bir sistem
            # istemi argv'de kalırsa modele yalnızca ilk satırı ulaşırdı.
            if CLAUDE_SUPPORTS_SYSTEM_PROMPT_FILE and (
                len(append_system_prompt) > SYSTEM_PROMPT_ARGV_LIMIT
                or "\n" in append_system_prompt
            ):
                path = self.write_system_prompt_file(append_system_prompt)
                if path:
                    cmd.extend([SYSTEM_PROMPT_FILE_FLAG, str(path)])
                else:
                    cmd.extend(["--append-system-prompt", append_system_prompt])
            else:
                cmd.extend(["--append-system-prompt", append_system_prompt])
        if isolated:
            # Kullanıcının genel MCP sunucuları gelmez; yalnızca Entropy'nin
            # kendi yapılandırması verilirse yüklenir. Entropy MCP'si yoksa
            # araç ad alanı ayrıca `--disallowedTools "mcp__*"` ile kapatılır:
            # ölçümde 119 araç adı ~2.4k token tutuyordu.
            cmd.append("--strict-mcp-config")
            if mcp_config:
                cmd.extend(["--mcp-config", mcp_config])
            else:
                cmd.extend(["--disallowedTools", "mcp__*"])
            # Kullanıcının user/project/local ayar dosyaları yüklenmez.
            cmd.extend(["--setting-sources", ""])
            # 32 yeteneklik katalog (~3.8k token) gelmez; Entropy yeteneklerini
            # kendisi yönlendiriyor, CLI'ın slash ad alanına ihtiyacı yok.
            cmd.append("--disable-slash-commands")
            tool_list = list(tools) if tools else list(CHAT_TOOLS_READONLY)
            cmd.extend(["--tools", ",".join(tool_list)])
            if agents_json:
                cmd.extend(["--agents", agents_json])
        elif mcp_config:
            cmd.extend(["--mcp-config", mcp_config])
        if skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        # Adım tavanı: CLI bayrağı bu sürümde YOK (bkz. CLAUDE_SUPPORTS_MAX_TURNS).
        # Bayrak geldiği gün tek satır açılır; yaptırım her hâlükârda
        # `consume_stream` sayacındadır.
        if max_steps and CLAUDE_SUPPORTS_MAX_TURNS:
            cmd.extend(["--max-turns", str(int(max_steps))])
        # `resume_id` açıkça verilen oturum kimliğidir (konuşma eşlemesi);
        # `resume=True` ise köprünün kendi son oturumunu sürdürür. Açık kimlik
        # önceliklidir: arka plan görevi etkileşimli sohbetin oturumuna
        # sızmamalı.
        if resume_id:
            cmd.extend(["--resume", str(resume_id)])
        elif resume and self.current_session_id:
            cmd.extend(["--resume", self.current_session_id])
        elif session_id:
            # Faz 11-C.3: ajanın KALICI oturumu için kimliği önceden atıyoruz
            # (`--session-id <uuid>`); sonraki koşu aynı kimliği `--resume` ile
            # sürdürür. `--resume` ile birlikte VERİLMEZ: CLI ikisini bir arada
            # kabul etmiyor ve zaten anlamsız (kimlik ya yeni ya sürdürülüyor).
            cmd.extend(["--session-id", str(session_id)])

        # Efor önceliği (Faz 11-C.4): prompt'taki tek seferlik `/effort <seviye>`
        # > bu koşuya AÇIKÇA verilen efor (ajanın/kartın eforu) > oturum eforu
        # (üst çubuk). Ortadaki basamak Faz 11-C'de girdi: AGENT.md'deki efor
        # buraya hiç ulaşmıyordu, her kart üst çubuğun eforuyla koşuyordu.
        effort_m = re.search(
            r"(?:^|\s)/effort\s+(low|medium|high|xhigh|max)\b", prompt, re.IGNORECASE
        )
        if effort_m:
            run_effort = effort_m.group(1).lower()
        else:
            run_effort = str(effort or "").strip().lower() or self.selected_effort
        if run_effort in CLAUDE_EFFORT_LEVELS:
            cmd.extend(["--effort", run_effort])
        # Son süzgeç: `--bare` argv'ye ASLA girmez. Kullanıcının kimliği
        # claude.ai aboneliği; bare kip OAuth/keychain okumaz ve
        # ANTHROPIC_API_KEY ister, yani her tur ücretli API'ye kayardı.
        for flag in ISOLATION_FORBIDDEN_FLAGS:
            while flag in cmd:
                cmd.remove(flag)
        return cmd

    # ------------------------------------------------------------------
    # Argv sınırı: sistem istemi dosyası ve stdin'e düşme
    # ------------------------------------------------------------------

    def system_prompt_dir(self) -> Path:
        """Sistem istemi dosyalarının yazıldığı geçici dizin."""
        base = Path(tempfile.gettempdir()) / "entropy_claude_prompts"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def entropy_agents_json(self, effort: Optional[str] = None) -> Optional[str]:
        """
        `--agents` yükü: Entropy'nin kendi kadrosu (Desk ajanları hariç).

        İzole kipte `--setting-sources ""` verildiği için CLI kullanıcının ve
        projenin `.claude/agents` dosyalarını okumaz; derlenmiş kadro yalnızca
        bu bayrakla o tura girer. Kadro boşsa None döner ve bayrak eklenmez:
        boş bir JSON nesnesi bile argv'de gereksiz yer tutuyordu.
        """
        try:
            from entropy.agents.compile import claude_agents_json

            return claude_agents_json(default_effort=str(effort or "")) or None
        except Exception:
            # Kadro okunamadıysa tur yine de koşar: `--agents` sadece bir ek.
            return None

    def write_system_prompt_file(self, text: str) -> Optional[Path]:
        """
        Sistem istemini dosyaya yazar; başarısızsa None (çağıran argv'ye düşer).

        Dosya adı iş parçacığına ve zamana bağlı: aynı anda koşan sohbet ve arka
        plan turu birbirinin istemini ezmesin.
        """
        try:
            name = f"sysprompt_{os.getpid()}_{threading.get_ident()}_{int(time.time() * 1000)}.txt"
            path = self.system_prompt_dir() / name
            path.write_text(text, encoding="utf-8")
            return path
        except Exception:
            return None

    @staticmethod
    def system_prompt_file_in(cmd: List[str]) -> Optional[str]:
        """argv'de sistem istemi dosyası varsa yolunu verir (temizlik için)."""
        for flag in (SYSTEM_PROMPT_FILE_FLAG, REPLACE_SYSTEM_PROMPT_FILE_FLAG):
            try:
                return cmd[cmd.index(flag) + 1]
            except (ValueError, IndexError):
                continue
        return None

    @classmethod
    def system_prompt_text_in(cls, cmd: List[str]) -> str:
        """
        argv'nin taşıdığı sistem istemi metni (satır içi ya da dosyadan).

        Sistem istemi artık üç yoldan biriyle gidebiliyor; onu argv'de sabit bir
        konumda arayan her çağıran (testler, tanılama) tek bir yerden okusun
        diye burada çözülür.
        """
        for flag in ("--append-system-prompt", "--system-prompt"):
            try:
                return cmd[cmd.index(flag) + 1]
            except (ValueError, IndexError):
                continue
        path = cls.system_prompt_file_in(cmd)
        if path:
            try:
                return Path(path).read_text(encoding="utf-8")
            except Exception:
                return ""
        # Yedek yol: metin kullanıcı mesajının başındaki bloğa gömülmüş olabilir.
        try:
            prompt = cmd[cmd.index("-p") + 1]
        except (ValueError, IndexError):
            return ""
        if prompt.startswith(SYSTEM_CONTEXT_BLOCK_HEADER):
            return prompt
        return ""

    @staticmethod
    def cleanup_system_prompt_file(path: Optional[str]) -> None:
        try:
            if path:
                Path(path).unlink(missing_ok=True)
        except Exception:
            pass

    def enforce_argv_limit(self, cmd: List[str]) -> None:
        """
        Argv toplamı sınırı aşıyorsa uzun parçaları argv'den çıkarır.

        Sıra: önce sistem istemi (dosyaya ya da — dosya bayrağı yoksa — prompt'un
        başına), sonra prompt'un kendisi (stdin NDJSON'a; bunu
        `_apply_stdin_prompt` yapar). Bu metot cmd'yi YERİNDE değiştirir.
        """
        if not argv_too_long(cmd):
            return
        try:
            sp_idx = cmd.index("--append-system-prompt")
        except ValueError:
            self._drop_agents_json_if_too_long(cmd)
            return
        system_prompt = cmd[sp_idx + 1]
        if CLAUDE_SUPPORTS_SYSTEM_PROMPT_FILE:
            path = self.write_system_prompt_file(system_prompt)
            if path:
                cmd[sp_idx] = SYSTEM_PROMPT_FILE_FLAG
                cmd[sp_idx + 1] = str(path)
                self._drop_agents_json_if_too_long(cmd)
                return
        # Yedek yol: bayrak yok (ya da dosya yazılamadı) -> sistem istemi
        # kullanıcı mesajının başına gömülür, argv'de hiç metin kalmaz.
        del cmd[sp_idx : sp_idx + 2]
        try:
            p_idx = cmd.index("-p")
        except ValueError:
            self._drop_agents_json_if_too_long(cmd)
            return
        cmd[p_idx + 1] = build_system_context_block(system_prompt, cmd[p_idx + 1])
        self._drop_agents_json_if_too_long(cmd)

    @staticmethod
    def _drop_agents_json_if_too_long(cmd: List[str]) -> bool:
        """
        Sinir hala asiliyorsa `--agents <json>` argv'den dusurulur (Ek-2, Faz 9).

        `--agents` yuku `claude_agents_json()` ile uretilir ve kadro buyudukce
        binlerce karaktere cikar; `argv_length` onu sayiyor ama
        `enforce_argv_limit` yalnizca sistem istemini bosaltiyordu. Kadro tek
        basina siniri asinca islem "command line is too long" ile oluyordu.
        Alt ajan cagrisi bir EK'tir: dusurulunce tur yine kosar, yalnizca
        `--agents` kadrosu gelmez. Dusurme gunluge yazilir.
        """
        if not argv_too_long(cmd):
            return False
        try:
            idx = cmd.index("--agents")
        except ValueError:
            return False
        dropped = cmd[idx + 1] if idx + 1 < len(cmd) else ""
        del cmd[idx : idx + 2]
        try:
            import logging

            logging.getLogger("entropy.claude_bridge").warning(
                "argv siniri asildi: --agents yuku dusuruldu (%d karakter, "
                "kalan argv %d/%d)",
                len(dropped), argv_length(cmd), ARGV_TOTAL_SAFE_LIMIT,
            )
        except Exception:
            pass
        return True

    def _apply_stdin_prompt(self, cmd: List[str], force: bool = False) -> Optional[str]:
        """
        Uzun prompt'u argv'den stdin NDJSON yoluna taşır (AGY ile aynı desen).

        Önce `enforce_argv_limit` çağrılır: sistem istemi argv'de kaldıysa oradan
        çıkarılır. Sonra prompt ya kendi başına uzun olduğu için ya da argv
        toplamı hâlâ sınırın üstünde kaldığı için stdin'e taşınır.

        force=True (etkileşimli kart): uzunluğa bakılmaz. Takip mesajlarının
        aynı borudan akabilmesi için süreç `--input-format stream-json` ile
        başlamalıdır.
        """
        self.enforce_argv_limit(cmd)
        try:
            idx = cmd.index("-p")
        except ValueError:
            return None
        if idx + 1 >= len(cmd):
            return None
        if not force and not prompt_via_stdin(cmd[idx + 1]) and not argv_too_long(cmd):
            return None
        payload = build_stdin_prompt_payload(cmd[idx + 1])
        cmd[idx + 1] = ""
        if "--input-format" not in cmd:
            cmd.extend(["--input-format", "stream-json"])
        return payload

    @staticmethod
    def _feed_stdin(proc, payload: Optional[str], keep_open: bool = False):
        """
        Yükü ayrı iş parçacığından yazar: büyük prompt'ta boru kilitlenmesini önler.

        (Aynı gerekçe AGY köprüsünde ayrıntılı yazılı: biz stdin'e yazarken CLI
        stdout tamponunu doldurursa iki taraf birbirini bekler.)

        keep_open=True (etkileşimli kart): stdin yazımdan sonra AÇIK kalır.
        """
        if not payload or getattr(proc, "stdin", None) is None:
            return None

        def _writer():
            try:
                proc.stdin.write(payload)
                proc.stdin.flush()
            except Exception:
                pass
            finally:
                if keep_open:
                    return
                try:
                    proc.stdin.close()
                except Exception:
                    pass

        t = threading.Thread(target=_writer, name="claude-stdin-writer", daemon=True)
        t.start()
        return t

    # ------------------------------------------------------------------
    # Akış adaptörü
    # ------------------------------------------------------------------

    def consume_stream(
        self,
        stream,
        sink: Optional[Callable[[str], None]] = None,
        max_steps: Optional[int] = None,
        on_step_limit: Optional[Callable[[int], None]] = None,
        stream_meta: Optional[dict] = None,
        task_id: str = "",
        model: Optional[str] = None,
        stop_on_result: bool = False,
    ) -> Dict[str, object]:
        """
        Claude stream-json satırlarını bus sinyallerine çevirir.

        stop_on_result=True (etkileşimli kart): ilk `result` olayında okuma
        DURUR ve dönüşte "stopped_on_result": True gelir. Yineleyici tüketilmiş
        olmadığı için çağıran, kullanıcının takip mesajından sonra aynı akışla
        bu metodu yeniden çağırıp bir sonraki turu okuyabilir.

        stream_meta / task_id / model: `bus.agent_stream` yükünün etiketi
        (ajan, ofis, kart). Sohbet yolu bunları geçmez; o zaman olaylar
        agent="entropy", office="" ile yayılır. Etiket olsun olmasın akış
        HER ZAMAN yayılır — sahne etiketsiz olayları Entropy'nin kendi
        avatarına düşürür.

        Dönüş: {"text", "usage", "session_id", "cost_usd", "is_error",
        "tool_steps", "step_limit_hit"}.

        max_steps: `assistant` mesajlarındaki `tool_use` bloklarının tavanı.
        Aşılınca `on_step_limit(sayaç)` çağrılır (çağıran süreci öldürür) ve
        akış okuma DURDURULUR. None ise sayaç kapalıdır — etkileşimli sohbetin
        uzun araç zincirini kesmek istemiyoruz; AGY köprüsündeki sözleşmenin
        birebir aynısı.
        Ayrı metot olması kasıtlı: sohbet ve arka plan yolları aynı çeviriyi
        paylaşır ve test bu metodu sahte bir satır listesiyle doğrudan
        sürebilir (süreç kurmadan).
        """
        emit_stream = self._agent_stream_emitter(task_id, stream_meta, model)
        text_parts: List[str] = []
        usage: Dict[str, int] = {}
        session_id: Optional[str] = None
        cost = 0.0
        is_error = False
        tool_steps = 0
        step_limit_hit = False
        stopped_on_result = False

        for raw_line in stream:
            if not raw_line:
                break
            line = raw_line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # stream-json olmayan satır (uyarı, yardım metni) kullanıcıya
                # ham geçirilir; yutulursa hata ayıklama imkânsızlaşıyordu.
                bus.terminal_output_received.emit(raw_line)
                emit_stream("text", raw_line)
                continue

            ev_type = data.get("type")

            if ev_type == "system":
                if data.get("subtype") == "init":
                    session_id = data.get("session_id") or session_id
                    model = data.get("model")
                    if model:
                        self.current_model = model
                        bus.model_detected.emit(model)
                    tools = data.get("tools") or []
                    bus.terminal_output_received.emit(
                        f"\n[Claude Code] Oturum başladı (model: {model or 'bilinmiyor'}, "
                        f"{len(tools)} araç).\n"
                    )
                    emit_stream("status", f"Oturum başladı ({model or 'model bilinmiyor'})")
                    bus.core_state_changed.emit("thinking")
                continue

            if ev_type == "assistant":
                message = data.get("message") or {}
                for block in message.get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        chunk = block.get("text") or ""
                        if chunk:
                            text_parts.append(chunk)
                            bus.token_chunk_received.emit(chunk)
                            bus.terminal_output_received.emit(chunk)
                            emit_stream("text", chunk)
                            if sink:
                                sink(chunk)
                            bus.core_pulse_triggered.emit(0.5)
                    elif btype == "thinking":
                        thought = (block.get("thinking") or "").strip()
                        if thought:
                            bus.terminal_output_received.emit(f"[🧠 Düşünce]: {thought}\n")
                            emit_stream("thinking", thought)
                            bus.core_pulse_triggered.emit(0.5)
                    elif btype == "tool_use":
                        # Adım sayacı: Claude'un araç çağrısı olayı tek biçimde
                        # gelir (assistant mesajında `tool_use` bloğu).
                        tool_steps += 1
                        name = block.get("name", "Araç")
                        params = json.dumps(block.get("input") or {}, ensure_ascii=False)[:300]
                        bus.terminal_output_received.emit(
                            f"\n[⚡ ARAÇ YÜRÜTÜLÜYOR: {name}]\n   Parametreler: {params}...\n"
                        )
                        tool_payload = self._tool_payload(name, block.get("input") or {})
                        emit_stream(
                            "tool_call",
                            f"{name}: {tool_payload['input_summary']}",
                            tool=tool_payload,
                        )
                        bus.core_pulse_triggered.emit(0.7)
                turn_usage = parse_usage(message.get("usage"))
                if turn_usage:
                    usage = turn_usage
                if max_steps and not step_limit_hit and tool_steps > int(max_steps):
                    step_limit_hit = True
                    is_error = True
                    emit_stream(
                        "error",
                        f"Araç adımı sınırı aşıldı ({tool_steps} > {int(max_steps)}).",
                    )
                    if on_step_limit is not None:
                        try:
                            on_step_limit(tool_steps)
                        except Exception:
                            pass
                    break
                continue

            if ev_type == "user":
                # Araç sonuçları kullanıcı rolüyle geri döner; ekrana yalnızca
                # kısaltılmış hâli basılır, tam gövde bağlamı şişirir.
                message = data.get("message") or {}
                for block in message.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content")
                        body = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                        bus.terminal_output_received.emit(
                            f"[✔ ARAÇ TAMAMLANDI: {block.get('name', 'Araç')}]\n"
                            f"   Sonuç: {str(body)[:300]}...\n"
                        )
                        emit_stream(
                            "tool_result",
                            str(body),
                            tool=self._tool_payload(block.get("name"), None),
                        )
                        bus.core_pulse_triggered.emit(0.4)
                continue

            if ev_type == "result":
                session_id = data.get("session_id") or session_id
                cost = float(data.get("total_cost_usd", 0.0) or 0.0)
                is_error = bool(data.get("is_error"))
                final = data.get("result")
                if isinstance(final, str) and final and not text_parts:
                    text_parts.append(final)
                    bus.terminal_output_received.emit(final)
                    bus.token_chunk_received.emit(final)
                    emit_stream("text", final)
                    if sink:
                        sink(final)
                result_usage = parse_usage(data.get("usage"))
                if result_usage:
                    usage = result_usage
                # Turun kapanışı: hata "error" (sahnede kırmızı), yoksa "idle"
                # (volta). Sahne bunu kartın bittiği an olarak okur.
                if is_error:
                    emit_stream("error", str(final or "").strip() or "Görev hatayla bitti.")
                else:
                    emit_stream("result", "".join(text_parts))
                if stop_on_result:
                    stopped_on_result = True
                    break
                continue

        return {
            "text": "".join(text_parts),
            "usage": usage,
            "session_id": session_id,
            "cost_usd": cost,
            "is_error": is_error,
            "tool_steps": tool_steps,
            "step_limit_hit": step_limit_hit,
            "stopped_on_result": stopped_on_result,
        }

    # ------------------------------------------------------------------
    # Token muhasebesi
    # ------------------------------------------------------------------

    @staticmethod
    def weighted_turn_tokens(usage: Dict[str, int]) -> int:
        """
        Turun MALİYET ağırlıklı token toplamı (`cache_read` 0,1×).

        Ham toplam kullanıcıyı yanıltıyordu: ölçülen bir turda 42k'lık toplamın
        34,9k'sı önbellek okumasıydı ve önbellek okuması taban girdi fiyatının
        onda birine yakın. Rozet ham toplamı göstermeye devam eder; bu değer
        "gerçek maliyet" satırı içindir.
        """
        cache_read = int(usage.get("cache_read_tokens", 0) or 0)
        total = int(usage.get("total_tokens", 0) or 0)
        return int(round(max(0, total - cache_read) + cache_read * CACHE_READ_COST_WEIGHT))

    def usage_badge_fields(self) -> Dict[str, int]:
        """
        Rozetin okuyacağı token alanları (tek yerde, tek anlam).

        `session` oturum toplamı, `turn` YALNIZCA son tur, `cache_read` önbellek
        okumasının oturum toplamı, `cost_weighted` indirimli toplam.
        """
        with self._state_lock:
            return {
                "session": int(self.session_total_tokens),
                "turn": int(self.total_tokens_used),
                "cache_read": int(self.session_cache_tokens),
                "cost_weighted": int(self.session_cost_tokens),
            }

    def _apply_chat_usage(self, usage: Dict[str, int], cost: float) -> None:
        if not usage:
            return
        with self._state_lock:
            self.latest_input_tokens = usage.get("input_tokens", 0)
            self.latest_output_tokens = usage.get("output_tokens", 0)
            self.latest_thinking_tokens = usage.get("thinking_tokens", 0)
            self.latest_cache_read_tokens = usage.get("cache_read_tokens", 0)
            # Önbelleğe YAZMA ayrı kalem: okuma neredeyse bedava, yazma normal
            # girdiden pahalı. Tek "cache" kaleminde toplandığında rozet pahalı
            # bir turu ucuz gösteriyordu (bkz. usage_breakdown).
            self.latest_cache_creation_tokens = usage.get("cache_creation_tokens", 0)
            turn_total = usage.get("total_tokens", 0)
            self.session_total_tokens += turn_total
            self.session_cache_tokens += usage.get("cache_read_tokens", 0)
            # `total_tokens_used` SON TURUN toplamıdır (Ek-1). Eskiden oturum
            # toplamına eşitleniyordu; rozetteki "(+son tur)" kalemi tanım gereği
            # oturum toplamının kopyasıydı ve "77k (+77k)" gibi anlamsız bir
            # satır çıkıyordu.
            self.total_tokens_used = turn_total
            # Maliyet ağırlıklı toplam: önbellek OKUMASI taban girdi fiyatının
            # onda birine yakın. Tam fiyat sayıldığında 40k'lık bir önbellek
            # okuması 40k'lık taze girdi gibi görünüyordu.
            self.session_cost_tokens += self.weighted_turn_tokens(usage)
            self.session_turn_count += 1
            self.last_cumulative_usage = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "thinking_tokens": usage.get("thinking_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_tokens", 0),
                "cache_creation_tokens": usage.get("cache_creation_tokens", 0),
                "total_tokens": turn_total,
            }
            self.last_total_cost_usd = cost
        config.last_cumulative_usage = dict(self.last_cumulative_usage)
        # Faz 12 kapanışı: SOHBET turu da deftere yazılır. Defter yalnızca arka
        # plan görevlerini tutarken sohbet tüketimi hiçbir yerde birikmiyordu ve
        # tavan aşımının nedeni ölçülemiyordu.
        try:
            task_ledger.record_chat_turn(usage, provider="claude",
                                         model=getattr(self, "model", "") or "")
        except Exception:
            pass
        try:
            config.save_settings()
        except Exception:
            pass
        bus.token_usage_updated.emit(self.session_total_tokens)
        try:
            bus.token_usage_detail.emit(self.usage_badge_fields())
        except Exception:
            pass

    def _save_chat_turn(self, user_prompt: str, assistant_resp: str) -> None:
        try:
            with self._state_lock:
                self.conversation_history.append({"role": "user", "content": user_prompt})
                self.conversation_history.append({"role": "assistant", "content": assistant_resp})
                snapshot = list(self.conversation_history)
            config_module.save_chat_history(snapshot)
            try:
                bus.chat_history_updated.emit()
            except Exception:
                pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Sözleşme: yürütme
    # ------------------------------------------------------------------

    def send_prompt_async(
        self,
        prompt: str,
        image_attachments: Optional[List[str]] = None,
        pdf_attachments: Optional[List[str]] = None,
        active_skill: Optional[str] = None,
        mode: str = "accept-edits",
        is_background: bool = False,
        task_id: Optional[str] = None,
        task_name: Optional[str] = None,
        project_path: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> None:
        """Kullanıcı istemini başsız Claude Code oturumunda çalıştırır; meşgulse sıraya alır."""
        if is_background:
            self.send_background_task_async(
                task_id=task_id or "task-bg",
                task_name=task_name or "Otonom Görev",
                prompt=prompt,
                mode=mode,
                project_path=project_path,
                agent=agent,
            )
            return

        args = (prompt, image_attachments, pdf_attachments, active_skill, mode, project_path, agent)
        with self._lock:
            if self._shutting_down:
                return
            if self._is_running:
                self._prompt_queue.append(args)
                bus.terminal_output_received.emit(
                    f"\n[Entropy Core] Başka bir işlem yürütülüyor. Mesajınız sıraya alındı "
                    f"({len(self._prompt_queue)}. sırada)...\n"
                )
                return
            self._is_running = True

        threading.Thread(target=self._execute_prompt_worker, args=args, daemon=True).start()

    def build_attachment_directive(
        self,
        image_attachments: Optional[List[str]] = None,
        pdf_attachments: Optional[List[str]] = None,
    ) -> Tuple[str, List[str]]:
        """
        Ek dosyaları prompt yönergesine + `--add-dir` listesine çevirir.

        NEDEN base64 değil: `claude --help` çıktısında görsel/PDF için hiçbir
        bayrak yok (`--file` yalnızca sunucudan indirilen `file_id:yol` çiftleri
        içindir) ve `--input-format stream-json` yalnızca "--print ve
        --output-format stream-json ile birlikte" koşullarını doğruluyor;
        gövdesindeki kullanıcı mesajı şemasının içerik BLOKLARINI (image/base64)
        kabul edip etmediği kota harcamadan doğrulanamıyor. Buna karşılık paketin
        `sdk-tools.d.ts` şeması Read aracının hem görseli (`type: "image"`,
        base64 + mediaType) hem PDF'i (`type: "pdf"`, sayfa aralığı, sayfa
        görselleri) yerel dosya yolundan okuduğunu açıkça gösteriyor.
        Dolayısıyla güvenilir yol: dosyanın MUTLAK YOLUNU prompt'ta vermek ve
        klasörünü `--add-dir` ile erişilebilir kılmak; okumayı modelin kendi
        Read aracı yapar (PDF'te sayfa aralığı seçebilme avantajıyla).
        """
        lines: List[str] = []
        dirs: List[str] = []
        for label, files in (("GÖRSEL", image_attachments or []), ("PDF", pdf_attachments or [])):
            for f in files:
                try:
                    p = Path(f).resolve()
                except Exception:
                    continue
                lines.append(f"- [{label}] {p}")
                parent = str(p.parent)
                if parent not in dirs:
                    dirs.append(parent)
        if not lines:
            return "", []
        directive = (
            "[EKLİ DOSYALAR] Aşağıdaki dosyalar bu mesajın ekidir; içeriklerini "
            "Read aracıyla oku (PDF'te gerekiyorsa sayfa aralığı vererek) ve "
            "yanıtını onlara dayandır:\n" + "\n".join(lines)
        )
        return directive, dirs

    # ------------------------------------------------------------------
    # Entropy Saf Kip: tek sistem istemi kurucusu (sohbet + kart)
    # ------------------------------------------------------------------

    def entropy_system_prompt(
        self,
        kind: str,
        *,
        project_path: Optional[str] = None,
        agent_spec: Optional[dict] = None,
        query: str = "",
        history_summary: str = "",
        fallback: str = "",
    ) -> str:
        """
        Varsayılan istemin YERİNE geçecek Entropy kimliğini kurar (Faz 9.2/9.4).

        Gerçek metin `entropy.brain.system_prompt.build_system_prompt`'tan
        gelir; o modül henüz yoksa ya da patlarsa buradaki yedek devreye girer.
        Guard bilinçli: kimliksiz koşmak (bugünkü kart davranışı) saf kipte çok
        daha kötü olurdu — varsayılan istem de düştüğü için model tamamen
        yönergesiz kalırdı.
        """
        try:
            from entropy.brain.system_prompt import build_system_prompt

            text = build_system_prompt(
                kind,
                provider=self.provider_name,
                project_path=project_path,
                agent_spec=agent_spec,
                query=query,
                history_summary=history_summary,
            )
            if text and str(text).strip():
                return str(text)
        except Exception:
            pass
        return fallback or self._fallback_system_prompt(kind, agent_spec=agent_spec)

    @staticmethod
    def _fallback_system_prompt(kind: str, agent_spec: Optional[dict] = None) -> str:
        """
        Kimlik + araç sözleşmesi yedeği.

        Araç sözleşmesi AÇIKÇA yazılı: saf kipte Claude Code'un kendi araç
        kuralları da düştüğü için "önce oku, sonra düzenle" gibi davranışlar
        modele burada söylenmezse hiç söylenmiş olmaz.
        """
        parts = [
            "Sen Entropy AI adında otonom bir masaüstü yapay zeka işletim "
            "sistemisin. Kullanıcıya daima Türkçe, net ve profesyonel bir "
            "üslupla yanıt ver. Kendi hafıza sisteminden, Obsidian notlarından "
            "ve geçmiş kararlarından haberdarsın.",
            "ARAÇ SÖZLEŞMESİ:\n"
            "- Bir dosyayı düzenlemeden önce mutlaka Read ile oku.\n"
            "- Dosya ararken Glob/Grep kullan; tüm depoyu okumaya çalışma.\n"
            "- Bash'i yalnızca gerçekten gerektiğinde ve tek seferlik komutlar "
            "için kullan; etkileşimli komut çalıştırma.\n"
            "- Emin olmadığın bir yolu uydurma; önce varlığını doğrula.",
        ]
        if kind == "card":
            parts.append(
                "GÖREV KİPİ: Arka planda bir görev kartını yürütüyorsun. "
                "Kullanıcıya soru soramazsın; eksik bilgi varsa makul bir "
                "varsayım yapıp varsayımını çıktında açıkça yaz. Sonunda ne "
                "yaptığını ve bulgularını özetle."
            )
        if isinstance(agent_spec, dict):
            name = str(agent_spec.get("name") or "").strip()
            role = str(agent_spec.get("role") or "").strip()
            body = str(agent_spec.get("prompt") or agent_spec.get("description") or "").strip()
            if name:
                header = f"AJAN: {name}" + (f" ({role})" if role else "")
                parts.append(f"{header}\n{body}".strip())
        return "\n\n".join(p for p in parts if p)

    def _forget_stale_session(self, system_prompt: str) -> bool:
        """
        Sistem istemi değiştiyse süren sohbet oturumunu düşürür (Faz 9.9).

        `--system-prompt-snapshot` varsayılan olarak `on`: bir konuşmanın ilk
        isteğinde kaydedilen istem sonraki her `--resume`'de aynen gönderilir,
        sonraki koşuş farklı metin verse bile. Bu yüzden istem değiştiğinde tek
        doğru davranış oturumu bırakmak.
        """
        try:
            from entropy.core.identity import ConversationMap, conversation_map
        except Exception:
            return False
        signature = ConversationMap.prompt_signature(system_prompt)
        previous = self._system_prompt_signature
        self._system_prompt_signature = signature
        if not previous or previous == signature:
            return False
        self.current_session_id = None
        conversation_id = getattr(config, "last_conversation_id", None)
        if conversation_id:
            try:
                conversation_map.forget(str(conversation_id))
            except Exception:
                pass
        bus.terminal_output_received.emit(
            "\n[Entropy] Sistem istemi değişti; temiz bir Claude oturumu açılıyor.\n"
        )
        return True

    def isolation_read_dirs(self) -> List[str]:
        """
        Saf kipte her koşuya eklenen kalıcı okuma dizinleri.

        Obsidian kasası: Entropy'nin belleği/raporları orada; kasa verilmeyince
        model "izinli dizinlerimde değil" diyordu. Çalışma dizini (`~/.entropy/
        workspace`) kendi cwd'sidir ama Claude Code cwd'yi kendiliğinden izinli
        saymıyor. Var olmayan yol eklenmez: CLI onu hata sayıyor.
        """
        dirs: List[str] = []
        for candidate in (
            getattr(config, "obsidian_vault_path", None),
            config_module.claude_workspace_path(),
        ):
            try:
                if candidate and Path(candidate).is_dir():
                    dirs.append(str(Path(candidate).resolve()))
            except Exception:
                continue
        return dirs

    @staticmethod
    def _is_card_worktree(project_dir: Optional[Path]) -> bool:
        """
        Verilen dizin bir kart worktree'si mi (Faz 10-C).

        Ölçüt tek satırlık ve git'in kendi sözleşmesi: BAĞLI (linked) bir
        worktree'nin kökünde `.git` bir DOSYADIR (ana depoda klasördür). Kart
        alanı köprüye taşınmadan aynı bilgiye ulaşılıyor.
        """
        try:
            return project_dir is not None and (Path(project_dir) / ".git").is_file()
        except OSError:
            return False

    def run_cwd(self, project_dir: Optional[Path], in_worktree: bool = False) -> Optional[str]:
        """
        Sürecin çalışma dizini.

        Saf kipte NÖTR ve git deposunun DIŞINDA bir dizin
        (`%USERPROFILE%\\.entropy\\workspace`): Claude Code proje kimliğini —
        bellek dizini, `.claude/agents`, git durumu — literal cwd'den değil GİT
        KÖKÜNDEN çözüyor, bu yüzden depo içindeki bir alt klasör izolasyon
        sağlamıyor. Projeye dosya erişimi `--add-dir` ile verilir.

        **İzolasyonun tek istisnası (Faz 10-C):** kartın `worktree` alanı
        doluysa cwd o worktree'dir. Gerekçe ölçüldü: izole kipte cwd git
        deposunun dışında kalıyor ve kartın `Bash` aracı `git status`
        çalıştırdığında "not a git repository" alıyordu. Worktree kartın KENDİ
        ağacıdır (`--add-dir` zaten oraya işaret ediyor), yani izolasyonun asıl
        amacı — Claude'un kullanıcının deposunu proje sanması — bozulmaz.
        """
        if in_worktree or self._is_card_worktree(project_dir):
            if project_dir is not None and Path(project_dir).exists():
                return str(project_dir)
        if bool(getattr(config, "claude_isolated", False)):
            try:
                return str(config_module.claude_workspace_path())
            except Exception:
                pass
        if project_dir is not None and Path(project_dir).exists():
            return str(project_dir)
        return None

    @staticmethod
    def tools_for(mode: str, needs_write: bool = False) -> List[str]:
        """Bu koşuda `--tools` ile verilecek araç listesi (izin kipine göre)."""
        tools = CARD_TOOLS_BY_MODE.get(normalize_permission_mode(mode))
        if tools is None:
            tools = list(CHAT_TOOLS_READONLY)
            if needs_write:
                tools = tools + CHAT_TOOLS_WRITE
            return tools
        result = list(tools)
        if needs_write:
            for extra in CHAT_TOOLS_WRITE:
                if extra not in result:
                    result.append(extra)
        return result

    def build_chat_system_prompt(
        self,
        prompt: str,
        target_skill=None,
        skill_banner: str = "",
        attachment_directive: str = "",
        resuming: bool = False,
    ) -> str:
        """
        `--append-system-prompt` ile enjekte edilecek metni kurar.

        Neden argv'deki prompt'a değil sistem istemine: Claude Code varsayılan
        sistem istemini korur ve buna EKLER; bağlam oraya konduğunda kullanıcının
        mesajı temiz kalır, `--resume` ile süren oturumda da her turda yeniden
        gönderilmek yerine yalnızca o turun bağlamı eklenir. Sürerken (resume)
        tam bilişsel bağlam yerine mini bağlam kullanılır: ağır bağlam zaten ilk
        turda enjekte edildi, her turda tekrarı pencereyi boş yere doldururdu.
        """
        parts = [
            "Sen Entropy AI adında otonom bir masaüstü yapay zeka işletim sistemisin. "
            "Kullanıcıya daima Türkçe, net ve profesyonel bir üslupla yanıt ver. "
            "Kendi hafıza sisteminden, Obsidian notlarından ve geçmiş kararlarından haberdarsın."
        ]
        if skill_banner:
            parts.append(skill_banner)
        if attachment_directive:
            parts.append(attachment_directive)
        if resuming:
            mini = self.get_mini_cognitive_context(prompt, target_skill=target_skill)
            if mini:
                parts.append(mini)
        else:
            ctx = self.get_cognitive_context(prompt, target_skill=target_skill)
            if ctx:
                if len(ctx) > SYSTEM_PROMPT_CONTEXT_LIMIT:
                    # Kırpma sonu keser; ajan kataloğu bağlamın SONUNDA duruyor ve
                    # sessizce düşüyordu. Kırpılmış bağlamdan sonra geri eklenir:
                    # ajan farkındalığı olmadan devretme önerisi hiç doğmaz.
                    agents_section = self.agents_manifest_section()
                    ctx = ctx[:SYSTEM_PROMPT_CONTEXT_LIMIT]
                    if agents_section and agents_section not in ctx:
                        ctx = f"{ctx}\n\n{agents_section}"
                parts.append(ctx)
            if self.conversation_history:
                recent = self.conversation_history[-6:]
                parts.append(
                    "Önceki Sohbet Özeti:\n"
                    + "\n".join(
                        f"- {'Kullanıcı' if m.get('role') == 'user' else 'Entropy'}: "
                        f"{str(m.get('content', ''))[:100]}"
                        for m in recent
                    )
                )
        return "\n\n".join(p for p in parts if p)

    def _execute_prompt_worker(
        self,
        prompt: str,
        image_attachments: Optional[List[str]] = None,
        pdf_attachments: Optional[List[str]] = None,
        active_skill: Optional[str] = None,
        mode: str = "accept-edits",
        project_path: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> None:
        project_dir = Path(project_path).resolve() if project_path else Path(self.active_project_dir).resolve()
        if not project_dir.exists():
            try:
                project_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # Proje kilidi: arka plan görevi projede yazarken sohbet turu aynı
        # dosyalara dokunursa iki CLI birbirinin düzenlemesini eziyor. Yazma
        # niyeti taşıyan tur yazma kilidi, okuma turu paylaşımlı okuma kilidi alır.
        is_write = self.is_code_modifying_intent(prompt, mode=mode)
        if project_lock_manager.is_write_locked(project_dir):
            bus.terminal_output_received.emit(
                "\n[Proje Kilidi: Arka plan görevi çalışıyor, işlem bekleniyor...]\n"
            )
        if is_write:
            lock_acquired = project_lock_manager.acquire_write(project_dir, timeout=30.0)
        else:
            lock_acquired = project_lock_manager.acquire_read(project_dir, timeout=30.0)
        if not lock_acquired:
            bus.terminal_output_received.emit(
                "\n[Proje Kilidi: Zaman aşımı! Arka plan görevi projeyi kullanıyor.]\n"
            )
            bus.core_state_changed.emit("idle")
            self._drain_queue()
            return

        bus.agent_turn_started.emit(prompt)
        bus.core_state_changed.emit("thinking")

        result: Dict[str, object] = {}
        ret_code = -1
        proc = None
        error_text = ""
        cmd: List[str] = []
        try:
            # Yetenek çözümü ve bilişsel bağlam ortak mixin'den gelir; AGY
            # köprüsüyle aynı kararı verir, böylece sağlayıcı değiştirmek
            # yönlendirmeyi değiştirmez. HAZIRLIK DA try içinde: burada doğan bir
            # hata (ör. bağlam üretimi) eskiden sohbeti kilitli bırakıyordu.
            target_skill, skill_banner = self.resolve_target_skill(prompt, active_skill=active_skill)
            if target_skill is not None:
                self.last_active_skill = target_skill.name
                bus.terminal_output_received.emit(
                    f"[🎯 Yetenek Devrede]: '{target_skill.name}' yeteneği aktif olarak kullanılıyor.\n"
                )

            attachment_directive, extra_dirs = self.build_attachment_directive(
                image_attachments, pdf_attachments
            )
            isolated = bool(getattr(config, "claude_isolated", False))
            resuming = bool(self.current_session_id)
            context_prompt = self.build_chat_system_prompt(
                prompt,
                target_skill=target_skill,
                skill_banner=skill_banner,
                attachment_directive=attachment_directive,
                resuming=resuming,
            )

            system_prompt = None
            if isolated:
                # Saf kip: Claude Code'un varsayılan istemi DEĞİŞTİRİLİR.
                # Kimlik + araç sözleşmesi tek kurucudan gelir, o turun bilişsel
                # bağlamı sonuna eklenir.
                identity_prompt = self.entropy_system_prompt(
                    "chat",
                    project_path=str(project_dir),
                    query=prompt,
                )
                system_prompt = "\n\n".join(
                    p for p in (identity_prompt, context_prompt) if p
                )
                append_system_prompt = None
                # `--system-prompt-snapshot` açık olduğu için süren oturum eski
                # istemi taşır; imza değiştiyse oturum düşürülüp yenisi açılır.
                if resuming and self._forget_stale_session(system_prompt):
                    resuming = False
            else:
                append_system_prompt = context_prompt

            cmd = self.build_command(
                prompt,
                mode=mode,
                project_dir=project_dir,
                agent=agent,
                resume=resuming,
                extra_dirs=extra_dirs,
                append_system_prompt=append_system_prompt,
                system_prompt=system_prompt,
                tools=self.tools_for(mode, needs_write=is_write),
                agents_json=self.entropy_agents_json() if isolated else None,
            )
            stdin_payload = self._apply_stdin_prompt(cmd)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if stdin_payload else subprocess.DEVNULL,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                **popen_kwargs(creationflags=self._creationflags(),
                               env=self.process_env(),
                               cwd=self.run_cwd(project_dir)),
            )
            writer = self._feed_stdin(proc, stdin_payload)
            with self._lock:
                self._current_process = proc
            readline_fn = getattr(proc.stdout, "readline", None)
            stream = iter(readline_fn, "") if callable(readline_fn) else iter(proc.stdout)
            result = self.consume_stream(stream)
            if writer is not None:
                writer.join(timeout=5.0)
            try:
                proc.stdout.close()
            except Exception:
                pass
            ret_code = proc.wait()
        except Exception as e:
            # Hata metni sohbete DÖNDÜRÜLÜR. Eskiden yalnızca terminale basılıp
            # "error" durumuna geçiliyordu; agent_turn_completed hiç yayılmadığı
            # için giriş kutusu açılmıyor ve çekirdek kırmızıda kilitli kalıyordu
            # (WinError 206 = "The command line is too long" tam olarak bu yola
            # düşüyordu).
            error_text = self.describe_launch_error(e)
            bus.terminal_output_received.emit(f"\n[Claude Köprü Hatası]: {e}\n")
        finally:
            with self._lock:
                self._current_process = None
            self.cleanup_system_prompt_file(self.system_prompt_file_in(cmd))
            # Kilit her yolda bırakılır: bırakılmayan bir yazma kilidi projeyi
            # oturum sonuna kadar tüm arka plan görevlerine kapatırdı.
            try:
                if is_write:
                    project_lock_manager.release_write(project_dir)
                else:
                    project_lock_manager.release_read(project_dir)
            except Exception:
                pass

        # Faz 12-B: sohbet yanıtı tek kancadan geçer — `[PANO board_create]`
        # bloğu karta dönüşür, araç/etiket blokları metinden çıkarılır.
        # Kaydetmeden ÖNCE: ham JSON diskteki geçmişe ve bağlam kurucuya
        # girmemeli.
        full_text = self.finalize_chat_text(str(result.get("text", "") or ""))
        session_id = result.get("session_id")
        if session_id:
            self.current_session_id = str(session_id)
        self._apply_chat_usage(result.get("usage") or {}, float(result.get("cost_usd") or 0.0))

        if full_text:
            self._save_chat_turn(prompt, full_text)
            # Faz 13-A (§1.5): serbest sohbet turu RAPOR DEĞİLDİR; kullanıcı
            # verisi kaybolmasın diye `Entropy/Sessions/` altına `type: session`
            # künyesiyle yazılır. Rapor üreten tek yollar: pano kartı çıktısı,
            # `[OTONOM PLANLI GÖREV]` ve açık `/learn`.
            try:
                if not re.search(r'(?:^|\s)/learn\b', prompt or "", re.IGNORECASE) \
                        and not TASK_PROMPT_RE.search(prompt or ""):
                    from entropy.brain.obsidian.vault_manager import ObsidianVaultManager
                    save_session_note(
                        ObsidianVaultManager().entropy_dir,
                        full_text,
                        provider="claude",
                        model=getattr(self, "current_model", "") or "",
                        skill=str(active_skill or ""),
                    )
            except Exception:
                pass
            try:
                bus.agent_turn_completed.emit(full_text)
            except Exception:
                pass
        elif error_text:
            # Yanıt yok ama hata var: turu hata metniyle KAPAT ki arayüz kilidi
            # açılsın ve kullanıcı ikinci mesajı gönderebilsin.
            try:
                bus.agent_turn_completed.emit(error_text)
            except Exception:
                pass
        # Hatadan sonra bile "idle": kırmızı/kilitli durumda kalan çekirdek yeni
        # istem kabul etmiyordu. Hata kullanıcıya metin olarak bildirildi.
        bus.core_state_changed.emit("idle" if (ret_code == 0 or error_text) else "error")

        # Bağlam doluluğu her turdan SONRA ölçülür: girdi token'ı ancak `result`
        # olayıyla belli olur, öncesinde ölçüm bir önceki turu yansıtırdı.
        try:
            self.check_context_pressure()
        except Exception:
            pass

        self._drain_queue()

    def _drain_queue(self) -> None:
        """Sıradaki mesajı başlatır; yoksa köprüyü boşa alır (tek yerde, tek kural)."""
        with self._lock:
            self._is_running = False
            next_task = self._prompt_queue.pop(0) if self._prompt_queue else None
            if next_task:
                self._is_running = True
        if next_task:
            threading.Thread(
                target=self._execute_prompt_worker, args=next_task, daemon=True
            ).start()

    def send_background_task_async(
        self,
        task_id: str,
        task_name: str,
        prompt: str,
        mode: str = "accept-edits",
        project_path: Optional[str] = None,
        on_result: Optional[Callable[[str, bool], None]] = None,
        save_report: bool = True,
        agent: Optional[str] = None,
        needs_write: Optional[bool] = None,
        conversation_id: Optional[str] = None,
        max_steps: Optional[int] = None,
        model: Optional[str] = None,
        agent_spec: Optional[dict] = None,
        stream_meta: Optional[dict] = None,
        interactive: bool = False,
        on_followup_start: Optional[Callable[[str], object]] = None,
        on_followup_end: Optional[Callable[[str], object]] = None,
        tools: Optional[List[str]] = None,
        effort: Optional[str] = None,
        session_id: Optional[str] = None,
        skill: Optional[str] = None,
    ) -> None:
        """
        AGY köprüsüyle birebir aynı sözleşme; farklar yalnızca CLI bayraklarında.

        tools: bu koşuda CLI'a `--tools` ile verilecek AÇIK araç listesi. None
        ise liste izin kipinden türetilir (`tools_for`). Çağıran (ör. ofis
        harness'i) ajanın `tools_policy` künyesini biliyorsa listeyi kendisi
        geçer: salt-okunur bir orkestratör `accept-edits` kipinde koşsa bile
        `Edit/Write/Bash` argv'ye HİÇ girmez, yani yasak istem metnine değil
        CLI'a yazılmış olur.

        interactive / on_followup_start / on_followup_end: etkileşimli kart kipi
        (Faz 10-C), AGY köprüsündeki sözleşmenin aynısı. Süreç ilk `result`
        olayından sonra canlı kalır; `send_followup` yeni tur başlatır. Aynı
        süreç sürdüğü için `--resume` GEREKMEZ ve adım sayacı tur başına
        sıfırlanır.

        stream_meta: `bus.agent_stream` yükünü etiketleyen bağlam
        ({"agent", "office", "card_id"}); harness/görev pompası geçmezse boş.

        conversation_id burada `--resume <session-id>` olur (agy'de
        `--conversation`); iki bayrağın adı farklı, anlamı aynı olduğu için
        sözleşme tek parametrede birleşti.

        max_steps: akıştaki `tool_use` bloklarının tavanı. Aşılırsa süreç
        `terminate_background_task` ile öldürülür ve görev `[ADIM SINIRI]`
        hatasıyla `failed` biter. None ise sayaç kapalı. CLI'da karşılık gelen
        bir bayrak olmadığı için (bkz. CLAUDE_SUPPORTS_MAX_TURNS) yaptırımın
        tamamı akış tarafındadır.
        """
        with self._lock:
            if self._shutting_down:
                # Sessiz dönüş çağıranı asılı bırakıyordu; ret de bir sonuçtur.
                self._notify_result(
                    on_result,
                    f"Arka plan görevi '{task_name}' başlatılmadı: köprü kapanıyor.",
                    False,
                )
                return
        threading.Thread(
            target=self._execute_background_task_worker,
            args=(task_id, task_name, prompt, mode, project_path, on_result,
                  save_report, agent, needs_write, conversation_id, max_steps,
                  model, agent_spec, stream_meta, interactive,
                  on_followup_start, on_followup_end, tools, effort, session_id,
                  skill),
            daemon=True,
        ).start()

    def send_followup(self, task_id: str, text: str) -> bool:
        """
        Koşan bir kart sürecine stdin üzerinden ek kullanıcı mesajı gönderir.

        Sprite'a tıklayıp o ajanın terminaline yazmanın (10.2) altyapısı. Claude
        CLI'ın stream-json kullanıcı olayı, uzun prompt yolunda zaten kullanılan
        `build_stdin_prompt_payload` ile aynıdır ({"type":"user",...}); ikinci
        bir şema icat edilmez. Süreç yoksa ya da stdin borusu kapalıysa False.

        Etkileşimli kipte (Faz 10-C) mesaj oturuma verilir: işçi uyanır, akış
        yeniden `working` olur, tur bitince `bus.task_followup_completed` yayılır.
        """
        emit_stream = self._agent_stream_emitter(task_id, self._stream_meta_for(task_id))
        reason = followup_rejection(text)
        if reason:
            emit_stream("error", reason)
            return False

        session = self._interactive_sessions.get(task_id)
        if session is not None:
            if session.closed or not session.alive():
                self._interactive_sessions.pop(task_id)
                emit_stream("error", "Terminal kapalı: kartın süreci artık çalışmıyor.")
                return False
            if not session.send(str(text)):
                emit_stream("error", "Takip mesajı gönderilemedi (terminal kapalı ya da kilit alınamadı).")
                return False
            emit_stream("status", "Takip mesajı gönderildi…", state="thinking")
            return True

        with self._lock:
            proc = self._background_processes.get(task_id)
        stdin = getattr(proc, "stdin", None) if proc is not None else None
        if stdin is None or getattr(stdin, "closed", False):
            emit_stream("error", "Terminal kapalı: kartın süreci artık çalışmıyor.")
            return False
        try:
            stdin.write(build_stdin_prompt_payload(str(text)))
            stdin.flush()
        except Exception:
            emit_stream("error", "Terminal kapalı: kartın süreci artık çalışmıyor.")
            return False
        return True

    def _stream_meta_for(self, task_id: str) -> Optional[dict]:
        """Kart akış etiketini (ajan/ofis/kart) görev başına hatırlar."""
        with self._state_lock:
            return dict(self._interactive_stream_meta.get(task_id) or {}) or None

    def close_interactive(self, task_id: str, reason: str = "kullanıcı kapattı") -> bool:
        """Etkileşimli kart terminalini kapatır (stdin kapanır, süreç sonlanır)."""
        session = self._interactive_sessions.get(task_id)
        if session is None:
            return False
        session.close(reason)
        self.terminate_background_task(task_id)
        self._interactive_sessions.pop(task_id)
        return True

    def interactive_task_ids(self) -> List[str]:
        """Şu an canlı olan etkileşimli kart terminalleri."""
        return self._interactive_sessions.active_ids()

    def _remember_agent_session(self, agent, session_id: str) -> None:
        """
        Yakalanan oturum kimliğini ajanın kalıcı deposuna yazar (Faz 11-C.3).

        Sessizce başarısız olur: oturum kalıcılığı bir KONFOR, kartın kapanması
        ise sözleşme. Depo yazılamadığında bir sonraki koşu yeni oturum açar.
        """
        name = str(agent or "").strip()
        if not name or not session_id:
            return
        try:
            from entropy.core.identity import agent_session_store

            agent_session_store().record_captured(
                name, self.provider_name, str(session_id), cwd=os.getcwd()
            )
        except Exception:
            pass

    def background_conversation_id(self, task_id: str) -> Optional[str]:
        """Biten arka plan görevinin Claude oturum kimliği (`--resume` girdisi)."""
        with self._lock:
            return self._background_conversations.get(task_id)

    @staticmethod
    def _notify_result(on_result, text: str, success: bool,
                       report_path: str = "") -> None:
        """Geri çağrıyı korumalı çağırır; geri çağrının hatası köprüyü düşürmez."""
        from entropy.core.provider import call_on_result

        call_on_result(on_result, text, success, report_path)

    def _execute_background_task_worker(
        self,
        task_id: str,
        task_name: str,
        prompt: str,
        mode: str = "accept-edits",
        project_path: Optional[str] = None,
        on_result: Optional[Callable[[str, bool], None]] = None,
        save_report: bool = True,
        agent: Optional[str] = None,
        needs_write: Optional[bool] = None,
        conversation_id: Optional[str] = None,
        max_steps: Optional[int] = None,
        model: Optional[str] = None,
        agent_spec: Optional[dict] = None,
        stream_meta: Optional[dict] = None,
        interactive: bool = False,
        on_followup_start: Optional[Callable[[str], object]] = None,
        on_followup_end: Optional[Callable[[str], object]] = None,
        tools: Optional[List[str]] = None,
        effort: Optional[str] = None,
        session_id: Optional[str] = None,
        skill: Optional[str] = None,
    ) -> None:
        emit_stream = self._agent_stream_emitter(task_id, stream_meta, model)
        # Kip bayrağı ayardan; kapalıysa hiçbir çağıran değişmeden Faz 10-B
        # davranışına dönülür.
        interactive = bool(interactive) and bool(
            getattr(config, "desk_interactive_cards", True)
        )
        if interactive:
            with self._state_lock:
                self._interactive_stream_meta[task_id] = dict(stream_meta or {})
        project_dir = Path(project_path).resolve() if project_path else Path(self.active_project_dir).resolve()
        if not project_dir.exists():
            try:
                project_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # Defterde MODEL de yazılı: kartın modeli yürütmeye geçmediğinde hata
        # (üst çubuğun modeliyle koşma) hiçbir kayıtta görünmüyordu.
        task_ledger.record_task_start(
            task_id=task_id,
            task_name=task_name,
            project_path=str(project_dir),
            provider=self.provider_name,
            model=self.model_for_run(model),
        )

        # Kilit türü: çağıran açıkça söylediyse o, yoksa prompt/moddan çıkarım.
        if needs_write is None:
            try:
                needs_write = self.is_code_modifying_intent(prompt, mode=mode)
            except Exception:
                needs_write = True

        write_acquired = False
        read_acquired = False
        notified = {"done": False}
        card_success = False
        interactive_session: Optional[InteractiveSession] = None
        interactive_finalized = False
        try:
            if needs_write:
                write_acquired = project_lock_manager.acquire_write(project_dir, timeout=BACKGROUND_LOCK_TIMEOUT)
                acquired, kind = write_acquired, "yazma kilidini"
            else:
                read_acquired = project_lock_manager.acquire_read(project_dir, timeout=BACKGROUND_LOCK_TIMEOUT)
                acquired, kind = read_acquired, "okuma kilidini"
            if not acquired:
                err = f"{LOCK_TIMEOUT_MARKER} Arka plan görevi '{task_name}' proje {kind} alamadı."
                task_ledger.record_task_failure(task_id=task_id, error=err)
                bus.terminal_output_received.emit(f"\n[Proje Kilidi Hatası]: {err}\n")
                # Geri çağrı olmadan dönmek çağıranın kartını asılı bırakıyordu.
                notified["done"] = True
                self._notify_result(on_result, err, False)
                bus.task_completed.emit(task_id, False)
                return

            bus.terminal_output_received.emit(
                f"\n[⏰ Otonom Arka Plan Görevi: {task_name}] Başlatıldı (Claude Code)...\n"
            )
            bus.core_pulse_triggered.emit(0.7)

            # KİMLİK (Faz 9.4). Arka plan kartları eskiden sistem istemi HİÇ
            # almıyordu (ölçüm: kart oturumlarında Entropy payı 0 karakter);
            # sohbet alıyordu. İki yol artık tek kurucudan besleniyor.
            card_system_prompt = self.entropy_system_prompt(
                "card",
                project_path=str(project_dir),
                agent_spec=agent_spec,
                query=prompt,
            )
            resume_id = conversation_id
            if resume_id:
                # Snapshot açık: süren oturum eski (kimliksiz) istemi taşır.
                try:
                    from entropy.core.identity import conversation_map

                    if conversation_map.sync_prompt(
                        str(conversation_id), self.provider_name, card_system_prompt
                    ):
                        resume_id = None
                except Exception:
                    pass

            cmd = self.build_command(
                prompt,
                mode=mode,
                project_dir=project_dir,
                agent=agent,
                skip_permissions=True,
                resume_id=resume_id,
                max_steps=max_steps,
                system_prompt=card_system_prompt,
                model=model,
                # Açık liste geldiyse izin kipinden türetme YAPILMAZ: çağıranın
                # araç sözleşmesi (ajan künyesi) kipin varsayılanını ezer.
                tools=(
                    [str(t).strip() for t in tools if str(t).strip()]
                    if tools else self.tools_for(mode, needs_write=bool(needs_write))
                ),
                agents_json=(
                    self.entropy_agents_json(effort=effort)
                    if getattr(config, "claude_isolated", False) else None
                ),
                # Faz 11-C.4/C.3: ajanın eforu ve kalıcı oturum kimliği.
                effort=effort,
                session_id=session_id if not resume_id else None,
            )

            result: Dict[str, object] = {}
            ret_code = -1
            execution_error = None
            proc = None
            step_limit = {"error": None}

            def _release_locks() -> None:
                """Proje kilidini bırakır (bir kez; bayraklar sıfırlanır)."""
                nonlocal write_acquired, read_acquired
                if write_acquired:
                    try:
                        project_lock_manager.release_write(project_dir)
                    except Exception:
                        pass
                    write_acquired = False
                if read_acquired:
                    try:
                        project_lock_manager.release_read(project_dir)
                    except Exception:
                        pass
                    read_acquired = False

            def _finalize_followup(turn_result: Dict[str, object], turn: int) -> None:
                """
                Takip turunu sonuçlandırır (kart zaten kapandığı için ayrı yol).

                Ledger'da yeni sütun açılmaz: aynı satırın token toplamları
                artırılır. Claude'un usage'ı tur başına gelir (AGY'deki gibi
                kümülatif değil), bu yüzden taban çıkarma gerekmez.
                """
                text = str(turn_result.get("text", "") or "").strip()
                ok = bool(text) and not turn_result.get("is_error")
                turn_usage = dict(turn_result.get("usage") or {})
                if turn_usage:
                    with self._state_lock:
                        self.last_background_usage = dict(turn_usage)
                        self.background_total_tokens += turn_usage.get("total_tokens", 0)
                    bus.token_usage_updated.emit(turn_usage.get("total_tokens", 0))
                    try:
                        prev = task_ledger.get_task(task_id) or {}
                        merged = {
                            k: int(prev.get(k) or 0) + int(turn_usage.get(k) or 0)
                            for k in ("input_tokens", "output_tokens", "total_tokens")
                        }
                        task_ledger.record_task_success(
                            task_id=task_id,
                            summary=mask_tool_output(text)[:300],
                            usage=merged,
                        )
                    except Exception:
                        pass
                if not ok:
                    emit_stream("error", text or "Takip turu yanıtsız bitti.")
                try:
                    bus.task_followup_completed.emit({
                        "task_id": task_id,
                        "card_id": str((stream_meta or {}).get("card_id") or ""),
                        "text": text,
                        "usage": turn_usage,
                        "turn": int(turn),
                        "success": ok,
                    })
                except Exception:
                    pass

            def _on_step_limit(count: int, _task_id=task_id) -> None:
                step_limit["error"] = (
                    f"{MAX_STEPS_MARKER} Araç adımı sınırı aşıldı "
                    f"({count} > {int(max_steps or 0)}); görev durduruldu."
                )
                bus.terminal_output_received.emit(f"\n[{step_limit['error']}]\n")
                self.terminate_background_task(_task_id)

            def _finalize_card(result: Dict[str, object],
                               ret_code_override: Optional[int] = None) -> None:
                """
                Kartın BİRİNCİ turunu sonlandırır: adım sınırı, oturum kimliği,
                token muhasebesi, ledger, `on_result`, rapor ve `task_completed`.

                Gövde Faz 10-B ile aynı; yalnızca ayrı bir ada taşındı, çünkü
                etkileşimli kipte kart süreç canlıyken (turun `result` olayında)
                finalize edilir — kullanıcı sonucu beklemek zorunda kalmasın.

                ret_code_override: etkileşimli kipte `proc.wait()` çağrılmaz;
                turun `result` olayı başarının kendisidir.
                """
                nonlocal execution_error, ret_code, card_success
                if ret_code_override is not None:
                    ret_code = ret_code_override
                # Adım sınırı, süreç öldürülürken doğan boru hatalarının ÖNÜNDE
                # gelir: kullanıcı "görev neden bitti" sorusunun gerçek yanıtını
                # görmeli, öldürmenin yan etkisini değil.
                if step_limit["error"]:
                    execution_error = step_limit["error"]

                # Oturum kimliği: ofis konuşmasının sürdürülebilmesi için saklanır.
                session_id = result.get("session_id")
                if session_id:
                    with self._lock:
                        self._background_conversations[task_id] = str(session_id)
                    # Faz 11-C.3: ajanın kalıcı oturumu diske yazılır; bellek
                    # sözlüğü uygulama kapanınca gidiyordu.
                    self._remember_agent_session(agent, str(session_id))

                full_text = str(result.get("text", "") or "").strip()
                success = (
                    ret_code == 0
                    and bool(full_text)
                    and execution_error is None
                    and not result.get("is_error")
                )
                card_success = success
                task_usage = dict(result.get("usage") or {})

                if task_usage:
                    with self._state_lock:
                        self.last_background_usage = dict(task_usage)
                        self.background_total_tokens += task_usage.get("total_tokens", 0)
                        running_total = self.background_total_tokens
                    bus.terminal_output_received.emit(
                        f"[Token] {task_name}: {task_usage.get('total_tokens', 0):,} "
                        f"(girdi {task_usage.get('input_tokens', 0):,} / "
                        f"çıktı {task_usage.get('output_tokens', 0):,}) — "
                        f"arka plan toplamı {running_total:,}\n"
                    )
                    bus.token_usage_updated.emit(task_usage.get("total_tokens", 0))

                # Ledger özeti ve tamamlanma özeti maskelenir: araç çıktısı blokları
                # özet için bilgi taşımaz ama satırı (ve sonraki bağlamı) şişirir.
                masked = mask_tool_output(full_text)
                if success:
                    task_ledger.record_task_success(
                        task_id=task_id, summary=masked[:300], usage=task_usage or None
                    )
                elif not self._shutting_down:
                    # usage ile: başarısız görev de token yaktı. Sütun NULL kalırsa
                    # `OfficeHarness.ledger_tokens` None döner ve ofis bütçesi
                    # gerçek maliyeti değil karakter/4 tahminini sayar — canlı
                    # koşuda başarısız bir Claude alt kartının maliyeti muhasebeye
                    # hiç girmedi. AGY köprüsündeki A7a davranışıyla eşitlendi.
                    task_ledger.record_task_failure(
                        task_id=task_id,
                        error=execution_error or f"Çıkış kodu: {ret_code}, yanıt uzunluğu: {len(full_text)}",
                        usage=task_usage or None,
                    )

                # SIRA (Faz 11 kapanışı): rapor kasaya yazıldıktan SONRA geri
                # çağrı koşar, böylece kartın `_finish`i rapor yolunu alabilir.
                notified["done"] = True
                saved_report_path = ""

                if not save_report:
                    self._notify_result(on_result, full_text, success)
                    bus.task_completed.emit(task_id, success)
                    bus.terminal_output_received.emit(f"\n[✔ Arka Plan Görevi: {task_name} Tamamlandı]\n")
                    return

                clean_name = re.sub(r'[\\/*?:"<>|]', "_", task_name).strip() or task_id
                time_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                try:
                    from entropy.brain.obsidian.vault_manager import ObsidianVaultManager

                    vm = ObsidianVaultManager()
                    report = (
                        f"# Otonom Görev Raporu: {task_name}\n\n"
                        f"- **Görev Kimliği**: `{task_id}`\n"
                        f"- **Sağlayıcı**: claude\n"
                        f"- **Durum**: {'Başarılı' if success else 'Hata / Uyarı'}\n\n"
                        f"## Görev Çıktısı ve Bulgular\n\n{full_text}\n"
                    )
                    # Rapor, görevin hangi yeteneğin işi olduğuna atfedilir: atıfsız
                    # rapor hiçbir yetenek için damıtma kaynağı sayılmıyor (AGY
                    # köprüsündeki davranışla aynı).
                    # Faz 13-A: kartın yetenek alanı sezgiyi ezer (AGY köprüsüyle
                    # aynı kural); yeteneksiz kartın raporu yabancı bir yeteneğin
                    # klasörüne düşmez.
                    if skill is not None:
                        task_skill = str(skill).strip() or None
                    else:
                        try:
                            detected = self.detect_skill_for_prompt(prompt)
                            task_skill = detected.name if detected else None
                        except Exception:
                            task_skill = None
                    # Faz 13-A: başlık gövdeden türetilir (AGY köprüsüyle aynı
                    # kural); `Gorev_` öneki + zaman damgası korunur.
                    derived_name = safe_filename_title(
                        derive_report_title(full_text, fallback=clean_name), max_len=60
                    )
                    rep_path = vm.save_research_report(
                        f"Gorev_{derived_name}_{time_tag}",
                        report,
                        tags=["otonom_gorev", task_id],
                        project_name=self.active_project_dir.name if self.active_project_dir else None,
                        skill_name=task_skill,
                    )
                    saved_report_path = str(rep_path)
                    bus.task_notification.emit(task_id, task_name, str(rep_path))
                    bus.knowledge_graph_updated.emit()
                except Exception as e:
                    bus.terminal_output_received.emit(f"[Otonom Rapor Hatası]: {e}\n")
                    bus.task_notification.emit(task_id, task_name, masked[:200])

                self._notify_result(on_result, full_text, success, saved_report_path)
                bus.task_completed.emit(task_id, success)
                bus.terminal_output_received.emit(
                    f"\n[✔ Otonom Arka Plan Görevi: {task_name} Tamamlandı]\n"
                )

            try:
                # Etkileşimli kipte istem her zaman stdin'den gider (takip
                # mesajları aynı borudan akacak).
                stdin_payload = self._apply_stdin_prompt(cmd, force=interactive)
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE if stdin_payload else subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    **popen_kwargs(creationflags=self._creationflags(),
                                   env=self.process_env(),
                                   cwd=self.run_cwd(project_dir)),
                )
                writer = self._feed_stdin(proc, stdin_payload, keep_open=interactive)
                with self._lock:
                    late = self._shutting_down
                    if not late:
                        self._background_processes[task_id] = proc
                if late:
                    self._kill_tree(proc, wait_budget=1.0)
                    raise RuntimeError("Uygulama kapanıyor; görev başlatılmadı.")

                readline_fn = getattr(proc.stdout, "readline", None)
                stream = iter(readline_fn, "") if callable(readline_fn) else iter(proc.stdout)

                if interactive:
                    interactive_session = InteractiveSession(
                        task_id,
                        proc,
                        build_stdin_prompt_payload,
                        idle_timeout=float(
                            getattr(config, "desk_interactive_idle_timeout_s", None)
                            or INTERACTIVE_IDLE_TIMEOUT_S
                        ),
                        on_followup_start=on_followup_start,
                        on_followup_end=on_followup_end,
                    )
                    self._interactive_sessions.register(interactive_session)

                # Tur döngüsü. Kip kapalıyken tek kez döner ve akış EOF'a kadar
                # okunur (eski davranış). Açıkken her `result` olayında okuma
                # durur, tur sonuçlanır ve kullanıcının takip mesajı beklenir;
                # aynı süreç sürdüğü için `--resume` gerekmez, adım sayacı da
                # her `consume_stream` çağrısında sıfırdan başlar (tur başına).
                interactive_turn = 0
                while True:
                    result = self.consume_stream(
                        stream,
                        max_steps=max_steps,
                        on_step_limit=_on_step_limit,
                        stream_meta=stream_meta,
                        task_id=task_id,
                        model=model,
                        stop_on_result=interactive,
                    )
                    if not (
                        interactive
                        and result.get("stopped_on_result")
                        and interactive_session is not None
                    ):
                        break

                    if interactive_turn == 0:
                        _finalize_card(result, ret_code_override=0)
                        interactive_finalized = True
                        # Bekleyen terminal koşan kart değildir: proje kilidi ve
                        # ofis paralellik sayacı burada serbest kalır.
                        _release_locks()
                    else:
                        _finalize_followup(result, interactive_turn)
                        interactive_session.finish_turn()

                    emit_stream("status", "Takip mesajı bekliyor…", state="idle")
                    if not interactive_session.wait_for_followup():
                        emit_stream(
                            "status",
                            f"Terminal kapandı ({interactive_session.close_reason or 'kapatıldı'}).",
                            state="idle",
                        )
                        break
                    interactive_turn += 1
                    emit_stream("status", "Takip mesajı alındı; sürdürülüyor…", state="working")

                if writer is not None:
                    writer.join(timeout=5.0)
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                if interactive_finalized:
                    try:
                        ret_code = proc.wait(timeout=5.0)
                    except Exception:
                        ret_code = -1
                else:
                    ret_code = proc.wait()
            except Exception as e:
                execution_error = str(e)
                bus.terminal_output_received.emit(
                    f"[Otonom Görev Hata] {task_name} yürütülemedi: {execution_error}\n"
                )
                emit_stream("error", f"{task_name} yürütülemedi: {execution_error}")
            finally:
                with self._lock:
                    self._background_processes.pop(task_id, None)
                if interactive_session is not None:
                    interactive_session.close("tur döngüsü bitti")
                    self._interactive_sessions.pop(task_id)
                    with self._state_lock:
                        self._interactive_stream_meta.pop(task_id, None)
                self.cleanup_system_prompt_file(self.system_prompt_file_in(cmd))
                try:
                    if proc and proc.poll() is None:
                        self._kill_tree(proc, wait_budget=2.0)
                except Exception:
                    pass

            # Etkileşimli kartta finalize DÖNGÜ İÇİNDE yapıldı; ikinci kez
            # çalıştırmak ledger'ı, raporu ve `on_result`u tekrarlardı.
            if not interactive_finalized:
                _finalize_card(result)

        except Exception as outer_err:
            try:
                rec = task_ledger.get_task(task_id)
                if (not self._shutting_down) and rec and rec.get("status") == TaskStatus.RUNNING.value:
                    task_ledger.record_task_failure(task_id=task_id, error=str(outer_err))
            except Exception:
                pass
            if not notified["done"]:
                notified["done"] = True
                self._notify_result(on_result, f"Otonom görev kritik hata: {outer_err}", False)
            bus.task_completed.emit(task_id, False)
            bus.terminal_output_received.emit(f"\n[Otonom Görev Kritik Hata]: {outer_err}\n")
        finally:
            if write_acquired:
                try:
                    project_lock_manager.release_write(project_dir)
                except Exception:
                    pass
            if read_acquired:
                try:
                    project_lock_manager.release_read(project_dir)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # İptal ve kapanış
    # ------------------------------------------------------------------

    @staticmethod
    def _kill_tree(proc, wait_budget: float) -> None:
        """Süreci ve çocuklarını indirir; Windows'ta taskkill /T şart.

        Claude Code kendi altında Node işçileri ve MCP sunucuları açar; yalnız
        ebeveyni öldürmek onları öksüz bırakır.
        """
        try:
            if proc.poll() is not None:
                return
        except Exception:
            return
        try:
            if sys.platform == "win32" or os.name == "nt":
                subprocess.run(
                    f"taskkill /F /T /PID {proc.pid}",
                    shell=True,
                    **popen_kwargs(stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL),
                )
            else:
                proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=max(0.0, wait_budget))
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def terminate_current_process(self) -> None:
        with self._lock:
            proc = self._current_process if self._is_running else None
            if proc is None:
                return
            self._is_running = False
        self._kill_tree(proc, wait_budget=2.0)
        bus.terminal_output_received.emit("\n[Entropy AI] İşlem kullanıcı tarafından durduruldu.\n")
        bus.core_state_changed.emit("idle")

    def terminate_background_task(self, task_id: str) -> None:
        with self._lock:
            proc = self._background_processes.get(task_id)
        if proc is not None:
            self._kill_tree(proc, wait_budget=2.0)

    def shutdown(self, timeout: float = 3.0) -> Dict[str, int]:
        """Köprüyü söndürür: yeni iş kabul etme, süreç ağaçlarını indir, ledger'ı kapat."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._lock:
            if self._shutting_down:
                return {"processes": 0, "tasks": 0, "threads": 0}
            self._shutting_down = True
        # Etkileşimli terminaller önce salıverilir: bekleyen işçi iş parçacığı
        # uyanmazsa kapanış boru hatasını beklerken uzar.
        self._interactive_sessions.close_all("uygulama kapanıyor")
        with self._lock:
            procs = list(self._background_processes.values())
            self._background_processes.clear()
            current = self._current_process
            self._current_process = None
            self._is_running = False
            self._prompt_queue.clear()
            side_threads = list(self._side_threads)
            self._side_threads.clear()

        killed = 0
        for proc in procs + ([current] if current is not None else []):
            try:
                alive = proc.poll() is None
            except Exception:
                alive = False
            self._kill_tree(proc, wait_budget=max(0.0, deadline - time.monotonic()))
            killed += int(alive)

        cancelled = 0
        try:
            cancelled = task_ledger.cancel_active("Uygulama kapandı; görev yarıda kesildi.")
        except Exception:
            pass

        joined = 0
        for t in side_threads:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                if t.is_alive():
                    t.join(timeout=remaining)
                joined += 1
            except Exception:
                pass

        return {"processes": killed, "tasks": cancelled, "threads": joined}
