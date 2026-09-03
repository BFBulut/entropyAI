"""Central Qt Typed Event Bus for Entropy AI."""

from PySide6.QtCore import QObject, Signal

class EntropyEventBus(QObject):
    """Global singleton event bus for cross-component signaling."""

    # UI Mode Transitions
    mode_requested = Signal(str)  # "zen", "floating", "chat"
    mode_changed = Signal(str)

    # Core Visual Activity
    core_pulse_triggered = Signal(float)  # intensity (0.0 - 1.0)
    core_state_changed = Signal(str)     # "idle", "thinking", "executing", "error"

    # AGY CLI Streaming & Lifecycle
    model_detected = Signal(str)         # dynamic model string e.g. "gemini-2.5-flash"
    token_chunk_received = Signal(str)   # streaming text chunk
    terminal_output_received = Signal(str) # stdout/stderr line
    token_usage_updated = Signal(int)    # total tokens consumed
    agent_turn_started = Signal(str)     # prompt
    agent_turn_completed = Signal(str)   # final response

    # Project Context
    project_changed = Signal(str)        # absolute project directory path

    # Tool Execution & Permissions
    tool_approval_requested = Signal(str, str, str)  # tool_name, args_summary, tool_id
    tool_approval_responded = Signal(str, bool)     # tool_id, approved

    # Task Scheduler
    task_triggered = Signal(str, str)    # task_id, task_name
    task_completed = Signal(str, bool)   # task_id, success

    # Knowledge & Reports
    report_created = Signal(str)         # report_path

# Global Event Bus Instance
bus = EntropyEventBus()
