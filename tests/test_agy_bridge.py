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
