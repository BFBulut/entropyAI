"""Unit tests for AGY CLI process bridge."""

import pytest
from pathlib import Path
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.config import config

@pytest.fixture
def bridge():
    b = AgyProcessBridge()
    b.conversation_history = []
    b.total_tokens_used = 0
    b.last_cumulative_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "thinking_tokens": 0,
        "cache_read_tokens": 0,
        "total_tokens": 0,
    }
    return b

def test_initial_state(bridge):
    assert bridge.current_model == config.selected_model
    assert bridge.total_tokens_used == 0
    assert not bridge.is_running

def test_dynamic_model_detection(bridge):
    # Tests rule compliance: agent-ui-models (Never hardcode models, fetch dynamically)
    samples = [
        ("Initialized engine using model: gemini-2.5-pro", "gemini-2.5-pro"),
        ("Switching active model to claude-3-7-sonnet...", "claude-3-7-sonnet"),
        ("Model Selection: Gemini 3.8 Flash (High)", "Gemini 3.8 Flash"),
        ("[gemini-2.5-flash] Thinking about prompt...", "gemini-2.5-flash"),
    ]
    for text, expected in samples:
        detected = bridge.detect_model_from_text(text)
        assert detected is not None
        assert expected.lower() in detected.lower()

def test_dynamic_model_detection_unknown(bridge):
    sample = "Regular output line without any model specification."
    assert bridge.detect_model_from_text(sample) is None

def test_context_window_truncation(bridge):
    # Tests rule compliance: agent-ui-routing (Context sliding windows)
    limit = config.context_window_size # 20
    # Add 25 messages
    for i in range(25):
        bridge.conversation_history.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"})

    assert len(bridge.conversation_history) == 25
    truncated = bridge._truncate_and_summarize_context()
    # Should contain 1 summary turn + 20 preserved turns = 21
    assert len(truncated) == limit + 1
    assert "[Context Truncated: 5 older conversation turns" in truncated[0]["content"]
    assert truncated[-1]["content"] == "msg 24"

def test_project_directory_binding(bridge, tmp_path):
    bridge.set_project_directory(tmp_path)
    assert bridge.active_project_dir == tmp_path.resolve()

def test_greeting_cognitive_context_filtering(bridge):
    # Casual greetings must not inject technical RAG codebase snippets
    assert bridge.get_cognitive_context("selam") == ""
    assert bridge.get_cognitive_context("merhaba") == ""
    assert bridge.get_cognitive_context("günaydın") == ""

def test_delta_token_accounting(bridge):
    # Turn 1: cumulative usage {"input_tokens": 15000, "output_tokens": 500, "total_tokens": 15500}
    cum_1 = {"input_tokens": 15000, "output_tokens": 500, "thinking_tokens": 200, "cache_read_tokens": 5000, "total_tokens": 15500}
    t1_out = max(0, cum_1["output_tokens"] - bridge.last_cumulative_usage["output_tokens"])
    t1_in = max(0, cum_1["input_tokens"] - bridge.last_cumulative_usage["input_tokens"])
    assert t1_out == 500
    assert t1_in == 15000
    bridge.last_cumulative_usage = cum_1

    # Turn 2: cumulative usage {"input_tokens": 32000, "output_tokens": 1200, "total_tokens": 33200}
    cum_2 = {"input_tokens": 32000, "output_tokens": 1200, "thinking_tokens": 400, "cache_read_tokens": 12000, "total_tokens": 33200}
    t2_out = max(0, cum_2["output_tokens"] - bridge.last_cumulative_usage["output_tokens"])
    t2_in = max(0, cum_2["input_tokens"] - bridge.last_cumulative_usage["input_tokens"])
    assert t2_out == 700  # 1200 - 500 = 700
    assert t2_in == 17000 # 32000 - 15000 = 17000
    assert t2_out + t2_in == 17700  # Turn 2 delta total
    bridge.last_cumulative_usage = cum_2

    # Reset conversation: baseline returns to 0
    bridge.reset_conversation()
    assert bridge.last_cumulative_usage["total_tokens"] == 0
    assert bridge.session_turn_count == 0

def test_background_task_dispatch_signature(bridge, monkeypatch):
    called = []
    monkeypatch.setattr(
        bridge,
        "send_background_task_async",
        lambda task_id, task_name, prompt, mode="accept-edits": called.append((task_id, task_name, prompt))
    )
    bridge.send_prompt_async(
        prompt="Test background autonomous prompt",
        is_background=True,
        task_id="bg-123",
        task_name="Bg Task"
    )
    assert len(called) == 1
    assert called[0][0] == "bg-123"
    assert called[0][1] == "Bg Task"
    assert not bridge.is_running  # Chat queue not locked!


def test_tool_telemetry_and_thinking_separation(bridge, monkeypatch):
    from entropy.core.event_bus import bus
    import json

    terminal_msgs = []
    chat_chunks = []
    bus.terminal_output_received.connect(lambda msg: terminal_msgs.append(msg))
    bus.token_chunk_received.connect(lambda chunk: chat_chunks.append(chunk))

    lines = [
        # Tool call active
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "write_to_file",
                "parameters": {"TargetFile": "test.py"},
                "state": "ACTIVE"
            }
        }) + "\n",
        # Tool call done
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "write_to_file",
                "state": "DONE",
                "duration_seconds": 1.25
            }
        }) + "\n",
        # Thinking step (no text_delta)
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_type": "agent_response",
                "step_index": 2
            }
        }) + "\n",
        # Chat text delta
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_type": "agent_response",
                "text_delta": "Merhaba, kodları yazdım."
            }
        }) + "\n",
        # Result
        json.dumps({
            "event": "result",
            "result": {"response": "Merhaba, kodları yazdım."}
        }) + "\n",
        ""
    ]

    class DummyStdout:
        def __init__(self, l):
            self._iter = iter(l)
        def readline(self):
            return next(self._iter, "")
        def close(self):
            pass

    class DummyProc:
        def __init__(self, *args, **kwargs):
            self.stdout = DummyStdout(lines)
            self.pid = 1234
        def wait(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)
    bridge._execute_prompt_worker("Test prompt")

    term_out = "".join(terminal_msgs)
    chat_out = "".join(chat_chunks)

    # 1. Tool execution should be visible in terminal
    assert "[⚡ ARAÇ YÜRÜTÜLÜYOR: write_to_file]" in term_out
    assert "[✔ ARAÇ TAMAMLANDI: write_to_file (1.25s)]" in term_out

    # 2. Thinking telemetry should be visible in terminal
    assert "[🧠 Düşünülüyor / Akıl Yürütülüyor (Adım #2)...]" in term_out

    # 3. Chat text delta should NOT be dumped into the terminal pane
    assert "Merhaba, kodları yazdım." not in term_out

    # 4. Chat text delta MUST be delivered to chat browser
    assert "Merhaba, kodları yazdım." in chat_out


def test_safe_session_reset_behavior(bridge, monkeypatch):
    """Ensure rich output (>200 chars) never causes false session reset even on non-zero exit."""
    from entropy.core.event_bus import bus
    import json

    terminal_msgs = []
    bus.terminal_output_received.connect(lambda msg: terminal_msgs.append(msg))
    bridge.current_conversation_id = "test-session-12345"

    rich_text = "A" * 250
    lines = [
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_type": "agent_response",
                "text_delta": rich_text
            }
        }) + "\n",
        ""
    ]

    class DummyStdout:
        def __init__(self, l):
            self._iter = iter(l)
        def readline(self):
            return next(self._iter, "")
        def close(self):
            pass

    class DummyProc:
        def __init__(self, *args, **kwargs):
            self.stdout = DummyStdout(lines)
            self.pid = 1234
        def wait(self):
            return 1  # Non-zero return code!

    monkeypatch.setattr("subprocess.Popen", DummyProc)
    bridge._execute_prompt_worker("Test prompt")

    # The session ID MUST NOT be wiped out because output was rich (>200 chars)
    assert bridge.current_conversation_id == "test-session-12345"
    term_out = "".join(terminal_msgs)
    assert "Oturum kilitlendi veya yanıtsız kaldı" not in term_out


def test_cli_cmd_timeout_and_path_discovery(bridge, monkeypatch, tmp_path):
    """Verify --print-timeout 30m is always passed and explicit paths in prompt are added via --add-dir."""
    captured_cmd = []

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            captured_cmd.extend(cmd)
            self.stdout = type("DummyStdout", (), {"readline": lambda self: "", "close": lambda self: None})()
            self.pid = 1234
        def wait(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)
    target_dir = tmp_path / "Entropy Agent Desk"
    target_dir.mkdir()

    prompt = f"Lütfen şu projeyi geliştir: {target_dir}"
    bridge._execute_prompt_worker(prompt)

    assert "--print-timeout" in captured_cmd
    idx = captured_cmd.index("--print-timeout")
    assert captured_cmd[idx + 1] == "30m"

    assert "--add-dir" in captured_cmd
    add_dirs = [captured_cmd[i+1] for i in range(len(captured_cmd)-1) if captured_cmd[i] == "--add-dir"]
    assert str(target_dir.resolve()) in add_dirs


def test_chat_mode_terminal_button_no_attribute_error(qapp):
    """Verify clicking terminal button in ChatModeWindow does not raise AttributeError."""
    from entropy.ui.modes.chat_mode import ChatModeWindow
    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)
    chat.show()
    
    assert chat.terminal_drawer.isHidden()
    # Click terminal button
    chat.toggle_term_btn.click()
    assert not chat.terminal_drawer.isHidden()
    assert chat.toggle_term_btn.text() == "▼ Terminali Kapat"

    # Click again to close
    chat.toggle_term_btn.click()
    assert chat.terminal_drawer.isHidden()
    assert chat.toggle_term_btn.text() == ">_ Terminal"
    chat.close()


def test_scheduled_task_coding_type_support(tmp_path):
    """Verify ScheduledTask with task_type='kodlama' dispatches concrete code generation prompt."""
    from entropy.scheduler.cron_engine import TaskScheduler, ScheduledTask
    from entropy.ui.widgets.tasks_widget import TasksWidget

    storage = tmp_path / "coding_task.json"
    scheduler = TaskScheduler(storage_path=storage)
    dispatched_prompts = []

    class MockBridge:
        def send_prompt_async(self, prompt, is_background=False, task_id=None, task_name=None, project_path=None):
            dispatched_prompts.append((prompt, project_path))

    bridge = MockBridge()
    task = scheduler.schedule_task(
        task_id="coding-proj-1",
        name="Entropy Agent Desk Geliştirme",
        prompt="Çoklu ofis sistemini kodla",
        interval_type="daily",
        interval_value=12,
        task_type="kodlama",
        project_path="C:\\Entropy Agent Desk"
    )

    tasks_widget = TasksWidget(scheduler=scheduler, bridge=bridge)
    tasks_widget._execute_task_logic(task)

    assert len(dispatched_prompts) == 1
    prompt_text, proj_path = dispatched_prompts[0]
    assert "OTONOM KODLAMA VE PROJE GELİŞTİRME GÖREVİ" in prompt_text
    assert "Bu bir proje/kodlama görevidir!" in prompt_text
    assert "projenin kodlarını yaz, dosyaları diske oluştur" in prompt_text
    assert proj_path == "C:\\Entropy Agent Desk"

    tasks_widget.close()
    scheduler.stop()


def test_extract_windows_paths_handling():
    """Verify extract_windows_paths correctly parses quoted, unquoted, and spaced paths without sentence fragment corruption."""
    from entropy.core.agy_bridge import extract_windows_paths

    text_quoted = 'Lütfen "C:\\Entropy Agent Desk" dizinindeki kodları düzenle.'
    paths_quoted = extract_windows_paths(text_quoted)
    assert any(str(p).endswith("Entropy Agent Desk") for p in paths_quoted)

    text_sentence = 'C:\\Entropy Agent Desk çalışma alanında projeyi geliştir'
    paths_sentence = extract_windows_paths(text_sentence)
    assert len(paths_sentence) > 0
    # Must not contain trailing sentence word "çalışma"
    assert not any("çalışma" in str(p).lower() for p in paths_sentence)

    text_unquoted = 'Dosyayı C:\\MyProject\\src\\main.py konumuna kaydet.'
    paths_unquoted = extract_windows_paths(text_unquoted)
    assert any(str(p).endswith("main.py") for p in paths_unquoted)


def test_rich_tool_telemetry_and_thought_display(bridge, monkeypatch):
    """Verify tool output snippet and thought text are printed in terminal."""
    from entropy.core.event_bus import bus
    import json

    terminal_msgs = []
    bus.terminal_output_received.connect(lambda msg: terminal_msgs.append(msg))

    lines = [
        # Tool call active with params
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "write_to_file",
                "parameters": {"TargetFile": "src/app.py", "CodeContent": "print('hello')"},
                "state": "ACTIVE"
            }
        }) + "\n",
        # Tool call done with output
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "tool_name": "write_to_file",
                "output": "File written successfully. Total lines: 1",
                "state": "DONE",
                "duration_seconds": 0.45
            }
        }) + "\n",
        # Thought step with actual thought text
        json.dumps({
            "event": "step_update",
            "step_update": {
                "step_type": "agent_thought",
                "thought": "Alt ajanları oluşturup mimariyi planlayacağım.",
                "step_index": 3
            }
        }) + "\n",
        ""
    ]

    class DummyStdout:
        def __init__(self, l):
            self._iter = iter(l)
        def readline(self):
            return next(self._iter, "")
        def close(self):
            pass

    class DummyProc:
        def __init__(self, *args, **kwargs):
            self.stdout = DummyStdout(lines)
            self.pid = 1234
        def wait(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)
    bridge._execute_prompt_worker("Test prompt with rich telemetry")

    term_out = "".join(terminal_msgs)
    assert "[⚡ ARAÇ YÜRÜTÜLÜYOR: write_to_file]" in term_out
    assert "src/app.py" in term_out
    assert "[✔ ARAÇ TAMAMLANDI: write_to_file (0.45s)]" in term_out
    assert "File written successfully" in term_out
    assert "[🧠 Düşünce (Adım #3)]: Alt ajanları oluşturup mimariyi planlayacağım." in term_out


def test_autonomous_rules_injected_in_existing_conversation(bridge, monkeypatch):
    """Verify autonomous execution rules and /boost directive are passed even in turn 2+."""
    captured_cmd = []

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            captured_cmd.extend(cmd)
            self.stdout = type("DummyStdout", (), {"readline": lambda self: "", "close": lambda self: None})()
            self.pid = 1234
        def wait(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)
    bridge.current_conversation_id = "existing-conv-id-999"

    prompt = "/boost Şimdi yeni bir proje oluşturacağız."
    bridge._execute_prompt_worker(prompt)

    prompt_flag_idx = captured_cmd.index("-p")
    payload = captured_cmd[prompt_flag_idx + 1]

    assert "TEMEL YÜRÜTME VE KODLAMA KURALLARI" in payload
    assert "FİİLİ OLARAK dosya oluşturma ve düzenleme araçlarını" in payload
    assert "[MOD: BOOST]" in payload
    assert "--effort" in captured_cmd
    assert captured_cmd[captured_cmd.index("--effort") + 1] == "high"


def test_chat_mode_turn_started_auto_expands_terminal(qapp):
    """Verify ChatModeWindow expands terminal drawer when turn starts."""
    from entropy.ui.modes.chat_mode import ChatModeWindow
    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)
    chat.show()

    assert chat.terminal_drawer.isHidden()
    chat._on_turn_started("Prompt")
    assert not chat.terminal_drawer.isHidden()
    assert chat.toggle_term_btn.text() == "▼ Terminali Kapat"
    chat.close()


def test_tasks_widget_auto_detects_coding_intent(tmp_path):
    """Verify tasks widget automatically detects coding intent when prompt contains 'geliştir'."""
    from entropy.scheduler.cron_engine import TaskScheduler
    from entropy.ui.widgets.tasks_widget import TasksWidget

    storage = tmp_path / "coding_task_detect.json"
    scheduler = TaskScheduler(storage_path=storage)
    dispatched_prompts = []

    class MockBridge:
        def send_prompt_async(self, prompt, is_background=False, task_id=None, task_name=None, project_path=None):
            dispatched_prompts.append((prompt, project_path))

    bridge = MockBridge()
    # task_type defaults to "analiz" but prompt says "projeyi geliştir"
    task = scheduler.schedule_task(
        task_id="auto-coding-1",
        name="Agent Desk",
        prompt="Entropy Agent Desk projesini geliştir ve mimariyi kur",
        interval_type="daily",
        interval_value=1,
        task_type="analiz"
    )

    tasks_widget = TasksWidget(scheduler=scheduler, bridge=bridge)
    tasks_widget._execute_task_logic(task)

    assert len(dispatched_prompts) == 1
    prompt_text, _ = dispatched_prompts[0]
    assert "OTONOM KODLAMA VE PROJE GELİŞTİRME GÖREVİ" in prompt_text

    tasks_widget.close()
    scheduler.stop()


def test_natural_language_boost_and_teamwork_directives(bridge, monkeypatch):
    """Verify natural language requests for boost/teamwork trigger directives and high effort."""
    import subprocess
    captured_cmd = []

    class MockPopen:
        def __init__(self, cmd, **kwargs):
            captured_cmd.extend(cmd)
            self.stdout = iter([])
            self.pid = 12345
        def poll(self):
            return 0
        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(subprocess, "Popen", MockPopen)
    monkeypatch.setattr(bridge, "find_agy_executable", lambda: "agy.exe")

    prompt = "Entropy yapay zekamızı teamwork preview yöntemiyle sub-agent'lar oluşturarak projeyi geliştir"
    bridge._execute_prompt_worker(prompt)

    prompt_flag_idx = captured_cmd.index("-p")
    payload = captured_cmd[prompt_flag_idx + 1]

    assert "[MOD: TEAMWORK-PREVIEW]" in payload
    assert "--effort" in captured_cmd
    assert captured_cmd[captured_cmd.index("--effort") + 1] == "high"


def test_background_task_effort_high_for_coding_tasks(bridge, monkeypatch):
    """Verify background tasks with coding prompt receive --effort high."""
    import subprocess
    captured_cmd = []

    class MockPopen:
        def __init__(self, cmd, **kwargs):
            captured_cmd.extend(cmd)
            self.stdout = iter([])
            self.pid = 12345
        def poll(self):
            return 0
        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(subprocess, "Popen", MockPopen)
    monkeypatch.setattr(bridge, "find_agy_executable", lambda: "agy.exe")

    prompt = "⏰ [OTONOM KODLAMA VE PROJE GELİŞTİRME GÖREVİ: Test Görev]\nTalimat: Projeyi geliştir"
    bridge._execute_background_task_worker("task-bg-1", "Test Görev", prompt)

    assert "--effort" in captured_cmd
    assert captured_cmd[captured_cmd.index("--effort") + 1] == "high"


def test_decoupled_thought_and_text_delta_streaming(bridge, monkeypatch):
    """Verify both thought and text_delta are processed when present in the same step."""
    import subprocess
    import json
    from entropy.core.event_bus import bus

    event_payload = json.dumps({
        "event": "step_update",
        "step_update": {
            "step_index": 3,
            "step_type": "agent_thought",
            "thought": "Alt ajanları koordine etmem gerekiyor",
            "text_delta": "Proje dosyaları oluşturuluyor..."
        }
    })

    class MockPopen:
        def __init__(self, cmd, **kwargs):
            self.stdout = iter([event_payload + "\n"])
            self.pid = 12345
        def poll(self):
            return 0
        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(subprocess, "Popen", MockPopen)
    monkeypatch.setattr(bridge, "find_agy_executable", lambda: "agy.exe")

    emitted_terminal = []
    emitted_chat = []

    bus.terminal_output_received.connect(lambda t: emitted_terminal.append(t))
    bus.token_chunk_received.connect(lambda c: emitted_chat.append(c))

    bridge._execute_prompt_worker("Test prompt")

    assert any("[🧠 Düşünce (Adım #3)]: Alt ajanları koordine etmem gerekiyor" in t for t in emitted_terminal)
    assert any("Proje dosyaları oluşturuluyor..." in c for c in emitted_chat)


def test_tasks_widget_extracts_project_path_from_prompt(tmp_path):
    """Verify tasks widget automatically extracts project_path from task prompt."""
    from entropy.scheduler.cron_engine import TaskScheduler
    from entropy.ui.widgets.tasks_widget import TasksWidget

    storage = tmp_path / "path_task_detect.json"
    scheduler = TaskScheduler(storage_path=storage)
    dispatched = []

    class MockBridge:
        def send_prompt_async(self, prompt, is_background=False, task_id=None, task_name=None, project_path=None):
            dispatched.append((prompt, project_path))

    bridge = MockBridge()
    target_dir = tmp_path / "MySpecialProject"

    task = scheduler.schedule_task(
        task_id="extract-path-1",
        name="Build Project",
        prompt=f"Lütfen {str(target_dir)} projesini geliştir",
        interval_type="daily",
        interval_value=1
    )

    tasks_widget = TasksWidget(scheduler=scheduler, bridge=bridge)
    tasks_widget._execute_task_logic(task)

    assert len(dispatched) == 1
    _, proj_p = dispatched[0]
    assert proj_p == str(target_dir)
    assert target_dir.exists()

    tasks_widget.close()
    scheduler.stop()




