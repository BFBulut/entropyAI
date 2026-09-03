"""Antigravity (AGY) CLI asynchronous bridge and real-time output pipeline with genuine token metering."""

import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from entropy.core.event_bus import bus
from entropy.core.config import config

class AgyProcessBridge(QObject):
    """Bridges Entropy AI to the authenticated local Antigravity (agy) CLI."""

    MODEL_PATTERNS = [
        re.compile(r"(?:Model\s+Selection|Active\s+Model|Using\s+Model|Model|Engine)\s*[:=]\s*([a-zA-Z0-9\.\-_\s\(\)]+)", re.IGNORECASE),
        re.compile(r"\[([a-zA-Z0-9\.\-_]+(?:flash|pro|sonnet|haiku|opus|codex|gpt|gemini|claude)[a-zA-Z0-9\.\-_]*)\]", re.IGNORECASE),
        re.compile(r"\bto\s+([a-zA-Z0-9\.\-_]+(?:flash|pro|sonnet|haiku|opus|codex|gpt|gemini|claude)[a-zA-Z0-9\.\-_]*)", re.IGNORECASE),
    ]

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.selected_model: str = config.selected_model
        self.current_model: str = self.selected_model or config.model_fallback_name
        self.total_tokens_used: int = 0
        self.latest_input_tokens: int = 0
        self.latest_output_tokens: int = 0
        self.latest_thinking_tokens: int = 0
        self.latest_cache_read_tokens: int = 0
        self.active_project_dir: Path = config.default_project_path
        self.conversation_history: List[Dict[str, str]] = []
        self._current_process: Optional[subprocess.Popen] = None
        self._is_running: bool = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_model(self, model_name: str):
        """Update active model dynamically and persist to configuration."""
        self.selected_model = model_name
        self.current_model = model_name
        config.selected_model = model_name
        config.save_settings()
        bus.model_detected.emit(model_name)

    def fetch_available_models(self) -> List[str]:
        """Dynamically fetch supported models from 'agy models' CLI."""
        agy_bin = self.find_agy_executable()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        try:
            res = subprocess.run(
                [agy_bin, "models"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                timeout=10
            )
            if res.returncode == 0:
                models = []
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if not line or "Fetching" in line:
                        continue
                    parts = line.split("\t")
                    model_id = parts[0].strip()
                    if model_id and model_id not in models:
                        models.append(model_id)
                if models:
                    config.available_models = models
                    return models
        except Exception:
            pass
        return config.available_models

    def find_agy_executable(self) -> str:
        """Locate agy CLI binary in system PATH or default Windows installation folders."""
        path = shutil.which("agy") or shutil.which("agy.exe")
        if path:
            return path
        # Common fallback paths on Windows
        fallbacks = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity" / "bin" / "agy.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Google" / "Antigravity" / "agy.exe",
            Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "antigravity" / "bin" / "agy.exe",
        ]
        for fb in fallbacks:
            if fb.exists():
                return str(fb)
        return "agy"

    def set_project_directory(self, project_path: Path | str):
        """Bind Entropy AI to a specific project folder."""
        self.active_project_dir = Path(project_path).resolve()
        bus.project_changed.emit(str(self.active_project_dir))

    def detect_model_from_text(self, text: str) -> Optional[str]:
        """Extract model name dynamically from text without hardcoding."""
        for pattern in self.MODEL_PATTERNS:
            match = pattern.search(text)
            if match:
                extracted = match.group(1).strip()
                if extracted and extracted != "Unknown":
                    return extracted
        return None

    def _truncate_and_summarize_context(self) -> List[Dict[str, str]]:
        """Apply sliding window context truncation (RULE: agent-ui-routing)."""
        limit = config.context_window_size
        if len(self.conversation_history) <= limit:
            return self.conversation_history

        preserved = self.conversation_history[-limit:]
        older_count = len(self.conversation_history) - limit
        summary_turn = {
            "role": "system",
            "content": f"[Context Truncated: {older_count} older conversation turns were compressed to maintain optimal response latency.]"
        }
        return [summary_turn] + preserved

    def send_prompt_async(
        self,
        prompt: str,
        image_attachments: Optional[List[str]] = None,
        mode: str = "accept-edits"
    ):
        """Execute a user prompt against agy CLI in a non-blocking background worker."""
        thread = threading.Thread(
            target=self._execute_prompt_worker,
            args=(prompt, image_attachments, mode),
            daemon=True
        )
        thread.start()

    def _execute_prompt_worker(
        self,
        prompt: str,
        image_attachments: Optional[List[str]] = None,
        mode: str = "accept-edits"
    ):
        with self._lock:
            if self._is_running:
                bus.terminal_output_received.emit("[Entropy AI] Uyarı: Zaten aktif bir komut çalıştırılıyor.\n")
                return
            self._is_running = True

        bus.core_state_changed.emit("thinking")
        bus.agent_turn_started.emit(prompt)

        # Append to conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        _ = self._truncate_and_summarize_context()

        agy_bin = self.find_agy_executable()

        system_directive = (
            "Sen Entropy AI adında otonom bir masaüstü yapay zeka işletim sistemisin. "
            "Kullanıcıya daima Türkçe ve samimi, net, profesyonel bir üslupla yanıt ver.\n"
        )
        full_prompt_payload = f"{system_directive}\nKullanıcı Mesajı: {prompt}"

        cmd = [
            agy_bin,
            "-p", full_prompt_payload,
            "--output-format", "stream-json",
            "--mode", mode,
            "--add-dir", str(self.active_project_dir),
        ]

        if self.selected_model and self.selected_model != config.model_fallback_name:
            cmd.extend(["--model", self.selected_model])

        if image_attachments:
            for img in image_attachments:
                if Path(img).exists():
                    cmd.extend(["--add-dir", str(Path(img).parent)])

        full_response_acc = []

        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                cwd=str(self.active_project_dir) if self.active_project_dir.exists() else None
            )

            short_prompt = prompt.replace("\n", " ")[:65]
            if len(prompt) > 65:
                short_prompt += "..."
            bus.terminal_output_received.emit(f"\n[Entropy Core | Model: {self.selected_model}] > {short_prompt}\n")

            for raw_line in iter(self._current_process.stdout.readline, ''):
                if not raw_line:
                    break

                line_str = raw_line.strip()
                if not line_str:
                    continue

                # Process NDJSON events from Antigravity engine
                try:
                    data = json.loads(line_str)
                    event = data.get("event")

                    if event == "init":
                        init_data = data.get("init", {})
                        model = init_data.get("model")
                        if model:
                            self.current_model = model
                            bus.model_detected.emit(model)

                    elif event == "step_update":
                        step = data.get("step_update", {})
                        text_delta = step.get("text_delta")
                        if text_delta:
                            bus.terminal_output_received.emit(text_delta)
                            full_response_acc.append(text_delta)
                            bus.token_chunk_received.emit(text_delta)
                            bus.core_pulse_triggered.emit(0.8)

                        usage = step.get("usage")
                        if usage:
                            self.latest_input_tokens = usage.get("input_tokens", 0)
                            self.latest_output_tokens = usage.get("output_tokens", 0)
                            self.latest_thinking_tokens = usage.get("thinking_tokens", 0)
                            self.latest_cache_read_tokens = usage.get("cache_read_tokens", 0)
                            self.total_tokens_used = usage.get("total_tokens", 0)
                            bus.token_usage_updated.emit(self.total_tokens_used)

                    elif event == "result":
                        result = data.get("result", {})
                        resp = result.get("response", "")
                        if not full_response_acc and resp:
                            bus.terminal_output_received.emit(resp)
                            full_response_acc.append(resp)
                            bus.token_chunk_received.emit(resp)

                        usage = result.get("usage")
                        if usage:
                            self.latest_input_tokens = usage.get("input_tokens", 0)
                            self.latest_output_tokens = usage.get("output_tokens", 0)
                            self.latest_thinking_tokens = usage.get("thinking_tokens", 0)
                            self.latest_cache_read_tokens = usage.get("cache_read_tokens", 0)
                            self.total_tokens_used = usage.get("total_tokens", 0)
                            bus.token_usage_updated.emit(self.total_tokens_used)

                except json.JSONDecodeError:
                    # Non-JSON output fallback
                    bus.terminal_output_received.emit(raw_line)
                    full_response_acc.append(raw_line)
                    bus.token_chunk_received.emit(raw_line)
                    bus.core_pulse_triggered.emit(0.6)

            self._current_process.stdout.close()
            ret_code = self._current_process.wait()

        except Exception as e:
            err_msg = f"[Entropy AI Hata] agy CLI yürütülemedi: {str(e)}\n"
            bus.terminal_output_received.emit(err_msg)
            full_response_acc.append(err_msg)
            ret_code = -1

        finally:
            with self._lock:
                self._is_running = False
                self._current_process = None

            full_text = "".join(full_response_acc)
            self.conversation_history.append({"role": "assistant", "content": full_text})
            bus.core_state_changed.emit("idle")
            bus.agent_turn_completed.emit(full_text)

    def terminate_current_process(self):
        """Cancel the currently active agy execution."""
        with self._lock:
            if self._current_process and self._is_running:
                try:
                    self._current_process.terminate()
                    bus.terminal_output_received.emit("\n[Entropy AI] İşlem kullanıcı tarafından durduruldu.\n")
                except Exception:
                    pass
                self._is_running = False
                bus.core_state_changed.emit("idle")
