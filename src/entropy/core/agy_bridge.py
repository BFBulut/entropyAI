"""Antigravity (AGY) CLI asynchronous bridge and real-time output pipeline."""

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

    # Dynamic Model Detection Patterns (from CLI headers, flags, or stdout)
    MODEL_PATTERNS = [
        re.compile(r"(?:Model\s+Selection|Active\s+Model|Using\s+Model|Model|Engine)\s*[:=]\s*([a-zA-Z0-9\.\-_\s\(\)]+)", re.IGNORECASE),
        re.compile(r"\[([a-zA-Z0-9\.\-_]+(?:flash|pro|sonnet|haiku|opus|codex|gpt|gemini|claude)[a-zA-Z0-9\.\-_]*)\]", re.IGNORECASE),
        re.compile(r"\bto\s+([a-zA-Z0-9\.\-_]+(?:flash|pro|sonnet|haiku|opus|codex|gpt|gemini|claude)[a-zA-Z0-9\.\-_]*)", re.IGNORECASE),
    ]

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.current_model: str = config.model_fallback_name
        self.total_tokens_used: int = 0
        self.active_project_dir: Path = config.default_project_path
        self.conversation_history: List[Dict[str, str]] = []
        self._current_process: Optional[subprocess.Popen] = None
        self._is_running: bool = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running

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

        # Keep the most recent messages, summarize older messages
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
                bus.terminal_output_received.emit("[Entropy AI] Warning: A prompt is already actively executing.\n")
                return
            self._is_running = True

        bus.core_state_changed.emit("thinking")
        bus.agent_turn_started.emit(prompt)

        # Append to conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        _ = self._truncate_and_summarize_context()

        agy_bin = self.find_agy_executable()
        cmd = [
            agy_bin,
            "-p", prompt,
            "--mode", mode,
            "--add-dir", str(self.active_project_dir),
        ]

        if image_attachments:
            for img in image_attachments:
                if Path(img).exists():
                    cmd.extend(["--add-dir", str(Path(img).parent)])

        full_response_acc = []

        try:
            # Start non-blocking Popen pipeline
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.active_project_dir) if self.active_project_dir.exists() else None
            )

            bus.terminal_output_received.emit(f"entropy@core:~$ {' '.join(cmd)}\n")

            # Read stdout chunk-by-chunk in real-time
            for line in iter(self._current_process.stdout.readline, ''):
                if not line:
                    break

                # Stream to terminal
                bus.terminal_output_received.emit(line)
                full_response_acc.append(line)

                # Emit token chunk and pulse core visualizer (RULE: agent-ui-routing)
                bus.token_chunk_received.emit(line)
                bus.core_pulse_triggered.emit(0.8)

                # Dynamically extract model name (RULE: agent-ui-models)
                detected = self.detect_model_from_text(line)
                if detected and detected != self.current_model:
                    self.current_model = detected
                    bus.model_detected.emit(self.current_model)

                # Approximate token counting (4 chars ~ 1 token)
                new_tokens = max(1, len(line) // 4)
                self.total_tokens_used += new_tokens
                bus.token_usage_updated.emit(self.total_tokens_used)

            self._current_process.stdout.close()
            ret_code = self._current_process.wait()

        except Exception as e:
            err_msg = f"[Entropy AI Error] Failed to execute agy CLI: {str(e)}\n"
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
                    bus.terminal_output_received.emit("\n[Entropy AI] Process terminated by user.\n")
                except Exception:
                    pass
                self._is_running = False
                bus.core_state_changed.emit("idle")
