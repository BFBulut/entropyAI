"""Antigravity (AGY) CLI asynchronous bridge, persistent conversation resumption, and cognitive memory awareness."""

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
from entropy.core.config import config, CHAT_HISTORY_FILE

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
        self.current_conversation_id: Optional[str] = config.last_conversation_id
        self.total_tokens_used: int = 0
        self.latest_input_tokens: int = 0
        self.latest_output_tokens: int = 0
        self.latest_thinking_tokens: int = 0
        self.latest_cache_read_tokens: int = 0
        self.session_total_tokens: int = 0
        self.session_cache_tokens: int = 0
        self.last_cumulative_usage: Dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cache_read_tokens": 0,
            "total_tokens": 0,
        }
        self.session_turn_count: int = 0
        self.active_project_dir: Path = config.default_project_path
        self.conversation_history: List[Dict[str, str]] = []
        self._current_process: Optional[subprocess.Popen] = None
        self._is_running: bool = False
        self._prompt_queue: List[Tuple[str, Optional[List[str]], str]] = []
        self._lock = threading.Lock()

        # Load persisted conversation history if available
        if CHAT_HISTORY_FILE.exists():
            try:
                self.conversation_history = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.conversation_history = []

    @property
    def is_running(self) -> bool:
        return self._is_running

    def reset_conversation(self):
        """Start a fresh conversation topic in Antigravity and clear local chat history."""
        self.current_conversation_id = None
        config.last_conversation_id = None
        config.save_settings()

        self.conversation_history = []
        if CHAT_HISTORY_FILE.exists():
            try:
                CHAT_HISTORY_FILE.unlink(missing_ok=True)
            except Exception:
                pass

        self.total_tokens_used = 0
        self.latest_input_tokens = 0
        self.latest_output_tokens = 0
        self.latest_thinking_tokens = 0
        self.latest_cache_read_tokens = 0
        self.session_total_tokens = 0
        self.session_cache_tokens = 0
        self.last_cumulative_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cache_read_tokens": 0,
            "total_tokens": 0,
        }
        self.session_turn_count = 0
        self._prompt_queue.clear()
        bus.token_usage_updated.emit(0)
        bus.terminal_output_received.emit("\n[Entropy Core] Yeni diyalog oturumu başlatıldı. (Kalıcı bilişsel hafıza ve bilgi grafiği korunuyor)\n")

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

    def get_cognitive_context(self, prompt: str) -> str:
        """Retrieve relevant Obsidian MEMORY.md and cognitive memory nodes to inject into agent consciousness."""
        # Casual greetings do not require heavy technical context injection
        is_greeting = prompt.strip().lower() in [
            "selam", "selamlar", "merhaba", "merhabalar", "hey", "nasılsın",
            "günaydın", "iyi akşamlar", "iyi geceler", "naber"
        ]
        if is_greeting:
            return ""

        context_parts = []

        # 1. Read Global MEMORY.md
        mem_file = config.obsidian_vault_path / "Entropy" / "MEMORY.md"
        if mem_file.exists():
            try:
                mem_text = mem_file.read_text(encoding="utf-8", errors="ignore").strip()
                if mem_text:
                    context_parts.append(f"[Kalıcı Bilişsel Hafıza (Obsidian MEMORY.md)]:\n{mem_text[:750]}")
            except Exception:
                pass

        # 2. Query SQLite / pgvector cognitive memory
        try:
            from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
            cog = CognitiveMemorySystem()
            recalled = cog.recall(prompt, limit=4)
            if recalled:
                items = [f"• {r.get('content', '')}" for r in recalled if r.get('content')]
                if items:
                    context_parts.append("[Hatırlanan İlgili Bilgiler / Anılar]:\n" + "\n".join(items))
        except Exception:
            pass

        # 3. Query Project RAG Indexer for codebase context (only for technical/code queries)
        is_code_or_tech = any(w in prompt.lower() for w in [
            "kod", "dosya", "hata", "fonksiyon", "class", "test", "build", "mcp", "hafıza", "rag", "terminal", "mode"
        ])
        if is_code_or_tech:
            try:
                from entropy.memory.rag.project_indexer import ProjectIndexer
                indexer = ProjectIndexer(self.active_project_dir)
                indexer.scan_and_index(max_files=120)
                matches = indexer.search_codebase(prompt, top_k=3)
                if matches:
                    snippets = [f"• [{m['path']}] {m['snippet']}" for m in matches]
                    context_parts.append("[İlgili Proje Kodları / Belgeler]:\n" + "\n".join(snippets))
            except Exception:
                pass

        # 4. Inject Active Skills & Tools Ecosystem (Progressive Disclosure)
        try:
            from entropy.skills.manager import SkillManager
            sm = SkillManager()
            manifest = sm.get_skills_manifest()
            if manifest:
                context_parts.append(manifest)
        except Exception:
            pass

        return "\n\n".join(context_parts)

    def get_mini_cognitive_context(self, prompt: str) -> str:
        """Lightweight memory retrieval for follow-up turns."""
        try:
            from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
            cog = CognitiveMemorySystem()
            recalled = cog.recall(prompt, limit=2)
            if recalled:
                items = [f"• {r.get('content', '')}" for r in recalled if r.get('content')]
                if items:
                    return "[Bağlamsal Hafıza]:\n" + "\n".join(items)
        except Exception:
            pass
        return ""

    def find_agy_executable(self) -> str:
        """Locate agy CLI binary in system PATH or default Windows installation folders."""
        path = shutil.which("agy") or shutil.which("agy.exe")
        if path:
            return path
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

    def _save_chat_turn(self, user_prompt: str, assistant_resp: str):
        """Save conversation turns persistently to disk for app restart continuity."""
        try:
            CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.conversation_history.append({"role": "user", "content": user_prompt})
            self.conversation_history.append({"role": "assistant", "content": assistant_resp})
            CHAT_HISTORY_FILE.write_text(
                json.dumps(self.conversation_history, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    def send_prompt_async(
        self,
        prompt: str,
        image_attachments: Optional[List[str]] = None,
        pdf_attachments: Optional[List[str]] = None,
        active_skill: Optional[str] = None,
        mode: str = "accept-edits"
    ):
        """Execute a user prompt against agy CLI, queueing if currently busy."""
        with self._lock:
            if self._is_running:
                self._prompt_queue.append((prompt, image_attachments, pdf_attachments, active_skill, mode))
                bus.terminal_output_received.emit(
                    f"\n[Entropy Core] Başka bir işlem yürütülüyor. Mesajınız sıraya alındı ({len(self._prompt_queue)}. sırada)...\n"
                )
                return
            self._is_running = True

        thread = threading.Thread(
            target=self._execute_prompt_worker,
            args=(prompt, image_attachments, pdf_attachments, active_skill, mode),
            daemon=True
        )
        thread.start()

    def _execute_prompt_worker(
        self,
        prompt: str,
        image_attachments: Optional[List[str]] = None,
        pdf_attachments: Optional[List[str]] = None,
        active_skill: Optional[str] = None,
        mode: str = "accept-edits"
    ):
        # 1. Process PDF Attachments if any
        if pdf_attachments:
            try:
                from entropy.skills.pdf_engine import PDFIngestionEngine
                pdf_eng = PDFIngestionEngine()
                pdf_blocks = []
                for pdf_file in pdf_attachments:
                    res = pdf_eng.ingest_and_store_memory(pdf_file)
                    meta = res["metadata"]
                    content_body = res["full_content"][:4000]
                    pdf_blocks.append(
                        f"\n[EKLENEN PDF BELGESİ: {meta['filename']} - {meta['pages']} Sayfa, {meta['word_count']} Kelime]:\n"
                        f"{content_body}\n"
                        f"(Tam özet arşivi: {res['digest_path']})\n"
                    )
                if pdf_blocks:
                    prompt = "\n".join(pdf_blocks) + "\n\n" + prompt
            except Exception as e:
                bus.terminal_output_received.emit(f"[PDF İşleme Hatası]: {e}\n")

        # 2. Inject Explicit Active Skill if selected
        if active_skill and active_skill.lower() not in ["auto", "otomatik", "otomatik algıla"]:
            try:
                from entropy.skills.manager import SkillManager
                sm = SkillManager()
                skills = {s.name: s for s in sm.list_skills()}
                if active_skill in skills:
                    target_skill = skills[active_skill]
                    skill_banner = (
                        f"\n[KULLANICI TARAFINDAN SEÇİLEN UZMANLIK YETENEĞİ: {target_skill.name.upper()}]\n"
                        f"{target_skill.instructions}\n"
                    )
                    prompt = skill_banner + "\n\n" + prompt
            except Exception:
                pass

        bus.core_state_changed.emit("thinking")
        bus.agent_turn_started.emit(prompt)

        agy_bin = self.find_agy_executable()

        # Check if continuing an existing conversation or starting turn 1
        if self.session_turn_count >= 15 and self.current_conversation_id:
            bus.terminal_output_received.emit(
                "\n[Entropy Core] Oturum bağlamı 15 tura ulaştı. Bağlam özetlenerek yeni temiz bir AGY oturumuna aktarılıyor...\n"
            )
            self.current_conversation_id = None
            config.last_conversation_id = None
            config.save_settings()
            self.last_cumulative_usage = {
                "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0, "total_tokens": 0
            }
            self.session_turn_count = 0

        if self.current_conversation_id:
            mini_context = self.get_mini_cognitive_context(prompt)
            turn_prompt = f"{mini_context}\n{prompt}" if mini_context else prompt
            cmd = [
                agy_bin,
                "-p", turn_prompt,
                "--conversation", self.current_conversation_id,
                "--output-format", "stream-json",
                "--mode", mode,
                "--dangerously-skip-permissions",
                "--add-dir", str(self.active_project_dir),
            ]
        else:
            cognitive_context = self.get_cognitive_context(prompt)
            system_directive = (
                "Sen Entropy AI adında otonom bir masaüstü yapay zeka işletim sistemisin. "
                "Kullanıcıya daima Türkçe ve samimi, net, profesyonel bir üslupla yanıt ver.\n"
                "Kendi hafıza sisteminden, Obsidian notlarından ve geçmiş kararlarından tamamen haberdarsın.\n"
            )
            if cognitive_context:
                system_directive += f"\n{cognitive_context[:2500]}\n"

            # Inject recent chat history summary if starting a fresh session
            if self.conversation_history:
                recent = self.conversation_history[-6:]
                system_directive += "\nÖnceki Sohbet Özeti:\n" + "\n".join(
                    [f"- {'Kullanıcı' if m.get('role')=='user' else 'Entropy'}: {m.get('content', '')[:100]}" for m in recent]
                ) + "\n"

            full_prompt_payload = f"{system_directive}\nKullanıcı Mesajı: {prompt}"
            if len(full_prompt_payload) > 3500:
                full_prompt_payload = full_prompt_payload[:3500]

            cmd = [
                agy_bin,
                "-p", full_prompt_payload,
                "--output-format", "stream-json",
                "--mode", mode,
                "--dangerously-skip-permissions",
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
            status_tag = f"Sohbet: {self.current_conversation_id[:8]}..." if self.current_conversation_id else "Yeni Sohbet"
            bus.terminal_output_received.emit(f"\n[Entropy Core | {self.selected_model} | {status_tag}] > {short_prompt}\n")

            for raw_line in iter(self._current_process.stdout.readline, ''):
                if not raw_line:
                    break

                line_str = raw_line.strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                    
                    # Capture and persist conversation ID
                    c_id = data.get("conversation_id")
                    if c_id:
                        self.current_conversation_id = c_id
                        config.last_conversation_id = c_id
                        config.save_settings()

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
                            self.total_tokens_used = self.latest_output_tokens
                            bus.token_usage_updated.emit(self.latest_output_tokens)

                    elif event == "result":
                        result = data.get("result", {})
                        resp = result.get("response", "")
                        if not full_response_acc and resp:
                            bus.terminal_output_received.emit(resp)
                            full_response_acc.append(resp)
                            bus.token_chunk_received.emit(resp)

                        usage = result.get("usage")
                        if usage:
                            # 1. Total lifetime cumulative tokens for this AGY session
                            cum_in = usage.get("input_tokens", 0)
                            cum_out = usage.get("output_tokens", 0)
                            cum_think = usage.get("thinking_tokens", 0)
                            cum_cache = usage.get("cache_read_tokens", 0)
                            cum_total = usage.get("total_tokens", cum_in + cum_out)

                            # 2. Compute exact delta tokens for THIS active turn
                            turn_output = max(0, cum_out - self.last_cumulative_usage.get("output_tokens", 0))
                            turn_input = max(0, cum_in - self.last_cumulative_usage.get("input_tokens", 0))
                            turn_thinking = max(0, cum_think - self.last_cumulative_usage.get("thinking_tokens", 0))
                            turn_cache = max(0, cum_cache - self.last_cumulative_usage.get("cache_read_tokens", 0))

                            # If turn_output is 0 but step had output, fallback to step output
                            if turn_output == 0 and self.latest_output_tokens > 0:
                                turn_output = self.latest_output_tokens

                            turn_total = turn_output + turn_input

                            self.latest_output_tokens = turn_output
                            self.latest_input_tokens = turn_input
                            self.latest_thinking_tokens = turn_thinking
                            self.latest_cache_read_tokens = turn_cache
                            self.session_total_tokens = cum_total
                            self.session_cache_tokens = cum_cache
                            self.total_tokens_used = turn_total

                            # Store baseline for next turn's delta
                            self.last_cumulative_usage = {
                                "input_tokens": cum_in,
                                "output_tokens": cum_out,
                                "thinking_tokens": cum_think,
                                "cache_read_tokens": cum_cache,
                                "total_tokens": cum_total,
                            }
                            self.session_turn_count += 1
                            bus.token_usage_updated.emit(turn_total)

                except json.JSONDecodeError:
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
            next_task = None
            with self._lock:
                self._is_running = False
                self._current_process = None
                if self._prompt_queue:
                    next_task = self._prompt_queue.pop(0)
                    self._is_running = True

            full_text = "".join(full_response_acc)
            self._save_chat_turn(prompt, full_text)
            bus.core_state_changed.emit("idle")
            bus.agent_turn_completed.emit(full_text)

            # Auto-recovery if AGY produced no output or error
            stripped_text = full_text.strip()
            is_empty_or_denied = (
                not stripped_text or
                "jetski: no output produced" in stripped_text or
                "auto-denied" in stripped_text or
                "Traceback" in stripped_text or
                ret_code != 0
            )
            if is_empty_or_denied and self.current_conversation_id:
                bus.terminal_output_received.emit(
                    "\n[Entropy Core] Oturum kilitlendi veya yanıtsız kaldı. Gelecek mesaj için temiz oturuma geçiliyor...\n"
                )
                self.current_conversation_id = None
                config.last_conversation_id = None
                config.save_settings()
                self.last_cumulative_usage = {
                    "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0, "total_tokens": 0
                }
                self.session_turn_count = 0

            # Auto-save research reports and technical dossiers (including autonomous scheduled tasks)
            is_err = "jetski: no output produced" in full_text or "auto-denied" in full_text or "Traceback" in full_text
            is_task_prompt = "[otonom planlı görev:" in prompt.lower()
            is_explicit_research = any(w in prompt.lower() for w in [
                "araştır", "araştırma yap", "rapor hazırla", "raporla", "analiz et", "derinlemesine incele", "dossier", "dokümantasyon oluştur"
            ])
            has_markdown_structure = ("# " in full_text or "## " in full_text) and len(full_text) > 250

            if not is_err and (is_task_prompt or (is_explicit_research and has_markdown_structure)):
                try:
                    from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                    from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
                    vm = ObsidianVaultManager()

                    if is_task_prompt:
                        match = re.search(r"\[OTONOM PLANLI GÖREV:\s*([^\]]+)\]", prompt, re.IGNORECASE)
                        task_name = match.group(1).strip() if match else "Otonom Görev"
                        time_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                        clean_title = f"Gorev_{task_name.replace(' ', '_')}_{time_tag}"
                    else:
                        first_line = prompt.strip().split("\n")[0][:36]
                        clean_title = re.sub(r'[\\/*?:"<>|]', "", first_line).strip() or "Araştırma Raporu"

                    rep_path = vm.save_research_report(clean_title, full_text)

                    # Extract distilled summary (Layer 6 consolidation) rather than storing massive full text
                    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip() and not p.startswith("#")]
                    distilled_summary = paragraphs[0][:250] if paragraphs else full_text[:200]

                    # Also store distilled summary in cognitive memory graph
                    try:
                        cog = CognitiveMemorySystem()
                        cog.store_node(
                            category="semantic",
                            content=f"Araştırma/Görev Özeti [{clean_title}]: {distilled_summary}",
                            importance=0.88,
                            metadata={"source": "task_or_research", "path": str(rep_path)}
                        )
                    except Exception:
                        pass

                    bus.report_created.emit(str(rep_path))
                    bus.cognitive_memory_updated.emit()
                    bus.knowledge_graph_updated.emit()

                    if is_task_prompt:
                        bus.task_notification.emit(task_name, task_name, str(rep_path))

                    bus.terminal_output_received.emit(
                        f"\n[📚 Araştırma Raporu & Hafıza Kaydedildi]: '{clean_title}.md' bilişsel hafızaya işlendi ve Obsidian kasanıza kaydedildi.\n"
                    )
                except Exception:
                    pass

            # Automatically log interaction to Obsidian Daily Note
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                vm = ObsidianVaultManager()
                short_p = prompt.replace("\n", " ")[:60]
                short_r = full_text.replace("\n", " ")[:100]
                vm.append_daily_log(f"- **Etkileşim**: {short_p} -> {short_r}...")
            except Exception:
                pass

            if next_task:
                next_prompt, next_imgs, next_pdfs, next_skill, next_mode = next_task
                next_thread = threading.Thread(
                    target=self._execute_prompt_worker,
                    args=(next_prompt, next_imgs, next_pdfs, next_skill, next_mode),
                    daemon=True
                )
                next_thread.start()

    def terminate_current_process(self):
        """Cancel the currently active agy execution and its child language_server process tree."""
        with self._lock:
            if self._current_process and self._is_running:
                try:
                    pid = self._current_process.pid
                    if sys.platform == "win32":
                        subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        self._current_process.terminate()
                    bus.terminal_output_received.emit("\n[Entropy AI] İşlem kullanıcı tarafından durduruldu.\n")
                except Exception:
                    pass
                self._is_running = False
                bus.core_state_changed.emit("idle")
