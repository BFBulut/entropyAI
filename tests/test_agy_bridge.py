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

