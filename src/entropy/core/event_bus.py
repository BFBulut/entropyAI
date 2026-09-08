"""Central Qt Typed Event Bus for Entropy AI."""

from PySide6.QtCore import QObject, QThread, Signal, Slot


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
    task_notification = Signal(str, str, str) # task_id, task_name, report_path_or_summary

    # Knowledge & Reports
    report_created = Signal(str)         # report_path
    node_selected = Signal(str)          # node_id
    knowledge_graph_updated = Signal()   # reload knowledge graph signal
    cognitive_memory_updated = Signal()  # memory nodes updated
    skills_updated = Signal()            # skills catalog updated
    mcp_servers_updated = Signal()       # mcp_config.json değişti (ekle/düzenle/kaldır/aç-kapa)
    playbook_updated = Signal(str)       # skill_name: damıtılmış yordam kaydedildi/yenilendi
    distill_progress = Signal(str, int, int)  # skill_name, işlenen rapor, toplam rapor

    # İşçi iş parçacıklarından ana iş parçacığına iş taşır. Alıcı bir QObject slotu
    # olduğu için bağlantı kuyruklu olur; lambda alıcı olsaydı doğrudan işçide
    # koşar ve Qt nesnelerine oradan dokunulurdu.
    call_on_main = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.call_on_main.connect(self._run_on_main)

    @Slot(object)
    def _run_on_main(self, fn):
        fn()

    def invoke_on_main(self, fn) -> None:
        """fn'i ana (bus'ın) iş parçacığında çalıştırır; zaten oradaysa hemen."""
        if QThread.currentThread() is self.thread():
            fn()
        else:
            self.call_on_main.emit(fn)

# Global Event Bus Instance
bus = EntropyEventBus()
