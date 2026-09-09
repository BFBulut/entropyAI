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
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject

import sys as _sys

import entropy.core.config  # noqa: F401  (alt modülün yüklenmesi için)
from entropy.core.config import config

# entropy.core paketi 'config' adını config NESNESİNE bağlar; sohbet geçmişi
# yardımcıları için gerçek modül gerekiyor (agy_bridge ile aynı tuzak).
config_module = _sys.modules["entropy.core.config"]
from entropy.core.event_bus import bus
from entropy.core.masking import mask_tool_output
from entropy.core.project_lock import project_lock_manager
from entropy.core.provider import (
    ProviderCommonMixin,
    agent_definitions_dir,
    list_agent_definitions,
)
from entropy.core.task_ledger import TaskStatus, task_ledger

# Windows CreateProcess sınırı AGY köprüsündekiyle aynı gerekçeyle burada da
# geçerli; eşik bilinçli olarak ortak tutuldu (bkz. agy_bridge.ARGV_PROMPT_SAFE_LIMIT).
ARGV_PROMPT_SAFE_LIMIT = 26_500

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
    return len(prompt or "") > ARGV_PROMPT_SAFE_LIMIT


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
        default_model = (
            getattr(config, "provider_models", {}).get("claude") or CLAUDE_MODELS[0]
        )
        current = getattr(config, "selected_model", "") or ""
        # Ayarlardaki model başka bir sağlayıcıya aitse (ör. gemini-*) buraya
        # taşınmaz: geçersiz --model değeri süreci başlatmadan hataya düşürür.
        self.selected_model: str = current if self._is_claude_model(current) else default_model
        self.current_model: str = self.selected_model
        self.current_session_id: Optional[str] = None
        self.last_total_cost_usd: float = 0.0

        self.total_tokens_used: int = 0
        self.background_total_tokens: int = 0
        self.last_background_usage: Dict[str, int] = {}
        self.latest_input_tokens: int = 0
        self.latest_output_tokens: int = 0
        self.latest_thinking_tokens: int = 0
        self.latest_cache_read_tokens: int = 0
        self.session_total_tokens: int = 0
        self.session_cache_tokens: int = 0
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
        self._is_running: bool = False
        self._shutting_down: bool = False
        self._side_threads: List[threading.Thread] = []
        self._prompt_queue: List[Tuple] = []
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._context_pressure_announced = False

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------

    @staticmethod
    def _is_claude_model(name: str) -> bool:
        if not name:
            return False
        low = name.lower()
        return low.startswith("claude-") or low in CLAUDE_MODEL_ALIASES

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
                creationflags=self._creationflags(),
                timeout=20,
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

    def set_model(self, model_name: str) -> None:
        self.selected_model = model_name
        self.current_model = model_name
        config.selected_model = model_name
        try:
            config.provider_models["claude"] = model_name
        except Exception:
            pass
        config.save_settings()
        bus.model_detected.emit(model_name)

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
        self.session_turn_count = 0
        self._context_pressure_announced = False
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
        skip_permissions: bool = False,
        extra_dirs: Optional[List[str]] = None,
        append_system_prompt: Optional[str] = None,
        mcp_config: Optional[str] = None,
    ) -> List[str]:
        """
        Başsız bir Claude Code çağrısının argv'sini kurar.

        `--verbose` bilinçli: `--print` ile `--output-format stream-json`
        birleştiğinde CLI ara olayları yalnızca ayrıntılı kipte yayınlar; onsuz
        akıştan tek bir `result` satırı gelir ve araç/düşünce telemetrisi hiç
        görünmez.
        """
        cmd = [
            self.find_claude_executable(),
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--permission-mode", normalize_permission_mode(mode),
        ]
        if self.selected_model:
            cmd.extend(["--model", self.selected_model])
        if project_dir is not None:
            cmd.extend(["--add-dir", str(project_dir)])
        for d in extra_dirs or []:
            cmd.extend(["--add-dir", str(d)])
        if agent:
            cmd.extend(["--agent", agent])
        if append_system_prompt:
            cmd.extend(["--append-system-prompt", append_system_prompt])
        if mcp_config:
            cmd.extend(["--mcp-config", mcp_config])
        if skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        if resume and self.current_session_id:
            cmd.extend(["--resume", self.current_session_id])

        effort_m = re.search(r"(?:^|\s)/effort\s+(low|medium|high|xhigh|max)\b", prompt, re.IGNORECASE)
        if effort_m:
            cmd.extend(["--effort", effort_m.group(1).lower()])
        return cmd

    def _apply_stdin_prompt(self, cmd: List[str]) -> Optional[str]:
        """Uzun prompt'u argv'den stdin NDJSON yoluna taşır (AGY ile aynı desen)."""
        try:
            idx = cmd.index("-p")
        except ValueError:
            return None
        if idx + 1 >= len(cmd) or not prompt_via_stdin(cmd[idx + 1]):
            return None
        payload = build_stdin_prompt_payload(cmd[idx + 1])
        cmd[idx + 1] = ""
        if "--input-format" not in cmd:
            cmd.extend(["--input-format", "stream-json"])
        return payload

    @staticmethod
    def _feed_stdin(proc, payload: Optional[str]):
        """
        Yükü ayrı iş parçacığından yazar: büyük prompt'ta boru kilitlenmesini önler.

        (Aynı gerekçe AGY köprüsünde ayrıntılı yazılı: biz stdin'e yazarken CLI
        stdout tamponunu doldurursa iki taraf birbirini bekler.)
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

    def consume_stream(self, stream, sink: Optional[Callable[[str], None]] = None) -> Dict[str, object]:
        """
        Claude stream-json satırlarını bus sinyallerine çevirir.

        Dönüş: {"text", "usage", "session_id", "cost_usd", "is_error"}.
        Ayrı metot olması kasıtlı: sohbet ve arka plan yolları aynı çeviriyi
        paylaşır ve test bu metodu sahte bir satır listesiyle doğrudan
        sürebilir (süreç kurmadan).
        """
        text_parts: List[str] = []
        usage: Dict[str, int] = {}
        session_id: Optional[str] = None
        cost = 0.0
        is_error = False

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
                            if sink:
                                sink(chunk)
                            bus.core_pulse_triggered.emit(0.5)
                    elif btype == "thinking":
                        thought = (block.get("thinking") or "").strip()
                        if thought:
                            bus.terminal_output_received.emit(f"[🧠 Düşünce]: {thought}\n")
                            bus.core_pulse_triggered.emit(0.5)
                    elif btype == "tool_use":
                        name = block.get("name", "Araç")
                        params = json.dumps(block.get("input") or {}, ensure_ascii=False)[:300]
                        bus.terminal_output_received.emit(
                            f"\n[⚡ ARAÇ YÜRÜTÜLÜYOR: {name}]\n   Parametreler: {params}...\n"
                        )
                        bus.core_pulse_triggered.emit(0.7)
                turn_usage = parse_usage(message.get("usage"))
                if turn_usage:
                    usage = turn_usage
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
                    if sink:
                        sink(final)
                result_usage = parse_usage(data.get("usage"))
                if result_usage:
                    usage = result_usage
                continue

        return {
            "text": "".join(text_parts),
            "usage": usage,
            "session_id": session_id,
            "cost_usd": cost,
            "is_error": is_error,
        }

    # ------------------------------------------------------------------
    # Token muhasebesi
    # ------------------------------------------------------------------

    def _apply_chat_usage(self, usage: Dict[str, int], cost: float) -> None:
        if not usage:
            return
        with self._state_lock:
            self.latest_input_tokens = usage.get("input_tokens", 0)
            self.latest_output_tokens = usage.get("output_tokens", 0)
            self.latest_thinking_tokens = usage.get("thinking_tokens", 0)
            self.latest_cache_read_tokens = usage.get("cache_read_tokens", 0)
            turn_total = usage.get("total_tokens", 0)
            self.session_total_tokens += turn_total
            self.session_cache_tokens += usage.get("cache_read_tokens", 0)
            self.total_tokens_used = self.session_total_tokens
            self.session_turn_count += 1
            self.last_cumulative_usage = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "thinking_tokens": usage.get("thinking_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_tokens", 0),
                "total_tokens": turn_total,
            }
            self.last_total_cost_usd = cost
        config.last_cumulative_usage = dict(self.last_cumulative_usage)
        try:
            config.save_settings()
        except Exception:
            pass
        bus.token_usage_updated.emit(self.session_total_tokens)

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
    ) -> None:
        """Kullanıcı istemini başsız Claude Code oturumunda çalıştırır; meşgulse sıraya alır."""
        if is_background:
            self.send_background_task_async(
                task_id=task_id or "task-bg",
                task_name=task_name or "Otonom Görev",
                prompt=prompt,
                mode=mode,
                project_path=project_path,
            )
            return

        with self._lock:
            if self._shutting_down:
                return
            if self._is_running:
                self._prompt_queue.append((prompt, active_skill, mode, project_path))
                bus.terminal_output_received.emit(
                    f"\n[Entropy Core] Başka bir işlem yürütülüyor. Mesajınız sıraya alındı "
                    f"({len(self._prompt_queue)}. sırada)...\n"
                )
                return
            self._is_running = True

        threading.Thread(
            target=self._execute_prompt_worker,
            args=(prompt, active_skill, mode, project_path),
            daemon=True,
        ).start()

    def _execute_prompt_worker(
        self,
        prompt: str,
        active_skill: Optional[str] = None,
        mode: str = "accept-edits",
        project_path: Optional[str] = None,
    ) -> None:
        project_dir = Path(project_path).resolve() if project_path else Path(self.active_project_dir).resolve()
        bus.agent_turn_started.emit(prompt)
        bus.core_state_changed.emit("thinking")

        cmd = self.build_command(prompt, mode=mode, project_dir=project_dir, resume=True)
        result: Dict[str, object] = {}
        ret_code = -1
        proc = None
        try:
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
                creationflags=self._creationflags(),
                cwd=str(project_dir) if project_dir.exists() else None,
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
            bus.terminal_output_received.emit(f"\n[Claude Köprü Hatası]: {e}\n")
            bus.core_state_changed.emit("error")
        finally:
            with self._lock:
                self._current_process = None

        full_text = str(result.get("text", "") or "")
        session_id = result.get("session_id")
        if session_id:
            self.current_session_id = str(session_id)
        self._apply_chat_usage(result.get("usage") or {}, float(result.get("cost_usd") or 0.0))

        if full_text:
            self._save_chat_turn(prompt, full_text)
            try:
                bus.agent_turn_completed.emit(full_text)
            except Exception:
                pass
        bus.core_state_changed.emit("idle" if ret_code == 0 else "error")

        # Bağlam doluluğu her turdan SONRA ölçülür: girdi token'ı ancak `result`
        # olayıyla belli olur, öncesinde ölçüm bir önceki turu yansıtırdı.
        try:
            self.check_context_pressure()
        except Exception:
            pass

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
    ) -> None:
        """AGY köprüsüyle birebir aynı sözleşme; farklar yalnızca CLI bayraklarında."""
        with self._lock:
            if self._shutting_down:
                return
        threading.Thread(
            target=self._execute_background_task_worker,
            args=(task_id, task_name, prompt, mode, project_path, on_result, save_report, agent),
            daemon=True,
        ).start()

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
    ) -> None:
        project_dir = Path(project_path).resolve() if project_path else Path(self.active_project_dir).resolve()
        if not project_dir.exists():
            try:
                project_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        task_ledger.record_task_start(
            task_id=task_id,
            task_name=task_name,
            project_path=str(project_dir),
            provider=self.provider_name,
        )

        write_acquired = False
        try:
            write_acquired = project_lock_manager.acquire_write(project_dir, timeout=60.0)
            if not write_acquired:
                err = f"Arka plan görevi '{task_name}' proje yazma kilidini alamadı."
                task_ledger.record_task_failure(task_id=task_id, error=err)
                bus.terminal_output_received.emit(f"\n[Proje Kilidi Hatası]: {err}\n")
                bus.task_completed.emit(task_id, False)
                return

            bus.terminal_output_received.emit(
                f"\n[⏰ Otonom Arka Plan Görevi: {task_name}] Başlatıldı (Claude Code)...\n"
            )
            bus.core_pulse_triggered.emit(0.7)

            cmd = self.build_command(
                prompt,
                mode=mode,
                project_dir=project_dir,
                agent=agent,
                skip_permissions=True,
            )

            result: Dict[str, object] = {}
            ret_code = -1
            execution_error = None
            proc = None
            try:
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
                    creationflags=self._creationflags(),
                    cwd=str(project_dir) if project_dir.exists() else None,
                )
                writer = self._feed_stdin(proc, stdin_payload)
                with self._lock:
                    late = self._shutting_down
                    if not late:
                        self._background_processes[task_id] = proc
                if late:
                    self._kill_tree(proc, wait_budget=1.0)
                    raise RuntimeError("Uygulama kapanıyor; görev başlatılmadı.")

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
                execution_error = str(e)
                bus.terminal_output_received.emit(
                    f"[Otonom Görev Hata] {task_name} yürütülemedi: {execution_error}\n"
                )
            finally:
                with self._lock:
                    self._background_processes.pop(task_id, None)
                try:
                    if proc and proc.poll() is None:
                        self._kill_tree(proc, wait_budget=2.0)
                except Exception:
                    pass

            full_text = str(result.get("text", "") or "").strip()
            success = (
                ret_code == 0
                and bool(full_text)
                and execution_error is None
                and not result.get("is_error")
            )
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
                task_ledger.record_task_failure(
                    task_id=task_id,
                    error=execution_error or f"Çıkış kodu: {ret_code}, yanıt uzunluğu: {len(full_text)}",
                )

            if on_result is not None:
                try:
                    on_result(full_text, success)
                except Exception as cb_err:
                    bus.terminal_output_received.emit(f"[Görev Geri Çağrı Hatası]: {cb_err}\n")

            if not save_report:
                bus.task_completed.emit(task_id, success)
                bus.terminal_output_received.emit(f"\n[✔ Arka Plan Görevi: {task_name} Tamamlandı]\n")
                return

            clean_name = re.sub(r'[\\/*?:"<>|]', "_", task_name).strip() or task_id
            time_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager

                vm = ObsidianVaultManager()
                report = (
                    f"# Otonom Görev Raporu: {task_name}\n\n"
                    f"- **Görev Kimliği**: `{task_id}`\n"
                    f"- **Sağlayıcı**: claude\n"
                    f"- **Durum**: {'Başarılı' if success else 'Hata / Uyarı'}\n\n"
                    f"## Görev Çıktısı ve Bulgular\n\n{full_text}\n"
                )
                rep_path = vm.save_research_report(
                    f"Gorev_{clean_name}_{time_tag}",
                    report,
                    tags=["otonom_gorev", task_id],
                    project_name=self.active_project_dir.name if self.active_project_dir else None,
                )
                bus.task_notification.emit(task_id, task_name, str(rep_path))
                bus.knowledge_graph_updated.emit()
            except Exception as e:
                bus.terminal_output_received.emit(f"[Otonom Rapor Hatası]: {e}\n")
                bus.task_notification.emit(task_id, task_name, masked[:200])

            bus.task_completed.emit(task_id, success)
            bus.terminal_output_received.emit(
                f"\n[✔ Otonom Arka Plan Görevi: {task_name} Tamamlandı]\n"
            )
        except Exception as outer_err:
            try:
                rec = task_ledger.get_task(task_id)
                if (not self._shutting_down) and rec and rec.get("status") == TaskStatus.RUNNING.value:
                    task_ledger.record_task_failure(task_id=task_id, error=str(outer_err))
            except Exception:
                pass
            bus.task_completed.emit(task_id, False)
            bus.terminal_output_received.emit(f"\n[Otonom Görev Kritik Hata]: {outer_err}\n")
        finally:
            if write_acquired:
                try:
                    project_lock_manager.release_write(project_dir)
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
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
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
