"""
Entropy Agent Desk: Office Detail Widget.
Detailed workstation for an individual office:
- Interactive PixelCanvas on the left/top.
- Multi-agent terminal panes, Todo Ledger, and Chat history on the right.
- Real-time Antigravity connection status bar in header.
- Full CRUD for tasks (Add, Edit, Delete, Reset, Immediate Execution).
- Full CRUD for agents (Spawn, Edit, Dismiss/Delete).
- Deep Cognitive Memory integration (Obsidian sync, partitioned memories).
"""

from typing import Optional, Dict
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QInputDialog,
    QComboBox,
    QMessageBox,
    QFrame,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QObject
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.core.models import (
    DeskRole,
    TaskStatus,
    AgentActivityState,
    TaskItem,
)
from src.entropy.agent_desk.core.agy_model_registry import AGYModelRegistry
from src.entropy.agent_desk.core.agy_task_executor import AgyTaskExecutor
from src.entropy.agent_desk.ui.pixel_canvas import PixelCanvas
from src.entropy.agent_desk.ui.agent_terminal_pane import AgentTerminalPane
from src.entropy.agent_desk.ui.agy_status_widget import AgyStatusWidget
from src.entropy.agent_desk.ui.memory_graph_canvas import MemoryGraphCanvas
from src.entropy.agent_desk.memory.partitioned_memory import OfficeMemoryPartition
from src.entropy.agent_desk.memory.memory_graph_bridge import MemoryGraphBridge
from src.entropy.agent_desk.ui.kanban_board_widget import KanbanBoardWidget, EvidenceInspectorDialog
from src.entropy.agent_desk.ui.goal_dialog import GoalDelegationDialog
from src.entropy.agent_desk.ui.terminal_grid_widget import TerminalGridWidget
from src.entropy.agent_desk.ui.chatflow_widget import ChatFlowWidget
from src.entropy.agent_desk.ui.crew_roster_widget import CrewRosterWidget


class DetailEventBridge(QObject):
    event_dispatched = Signal(str, dict)


class TaskEditDialog(QDialog):
    def __init__(self, task: Optional[TaskItem] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Görev Düzenle / Yeni Görev")
        self.resize(460, 360)
        self.setStyleSheet("background-color: #1e293b; color: #f8fafc;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_title = QLineEdit(task.title if task else "")
        self.txt_title.setStyleSheet("background-color: #0f172a; color: #f8fafc; padding: 6px; border: 1px solid #334155; border-radius: 4px;")
        form.addRow("Görev Başlığı:", self.txt_title)

        self.txt_desc = QTextEdit(task.description if task else "")
        self.txt_desc.setMaximumHeight(90)
        self.txt_desc.setStyleSheet("background-color: #0f172a; color: #f8fafc; padding: 6px; border: 1px solid #334155; border-radius: 4px;")
        form.addRow("Açıklama:", self.txt_desc)

        self.cb_role = QComboBox()
        self.cb_role.setStyleSheet("background-color: #0f172a; color: #f8fafc; padding: 6px; border: 1px solid #334155; border-radius: 4px;")
        roles = [r.value for r in DeskRole if r != DeskRole.ORCHESTRATOR]
        self.cb_role.addItems(roles)
        if task:
            idx = self.cb_role.findText(task.role_target.value)
            if idx >= 0:
                self.cb_role.setCurrentIndex(idx)
        form.addRow("Hedef Rol:", self.cb_role)

        crit_default = ", ".join(task.acceptance_criteria) if task and task.acceptance_criteria else "Kod yazılmalı, Testler %100 geçmeli"
        self.txt_crit = QLineEdit(crit_default)
        self.txt_crit.setStyleSheet("background-color: #0f172a; color: #f8fafc; padding: 6px; border: 1px solid #334155; border-radius: 4px;")
        form.addRow("Kabul Kriterleri (virgülle ayırın):", self.txt_crit)

        dod_default = ", ".join(task.definition_of_done) if task and task.definition_of_done else "Birim testler yeşil, tip denetimi başarılı, kanıt loglandı"
        self.txt_dod = QLineEdit(dod_default)
        self.txt_dod.setStyleSheet("background-color: #0f172a; color: #f8fafc; padding: 6px; border: 1px solid #334155; border-radius: 4px;")
        form.addRow("Definition of Done (DoD):", self.txt_dod)

        self.txt_verif = QLineEdit(task.verification_command if task and task.verification_command else "")
        self.txt_verif.setPlaceholderText("örn: pytest tests/test_agent_desk_core.py")
        self.txt_verif.setStyleSheet("background-color: #0f172a; color: #f8fafc; padding: 6px; border: 1px solid #334155; border-radius: 4px;")
        form.addRow("Doğrulama Komutu (QA Sentinel):", self.txt_verif)

        self.chk_execute = QCheckBox("Görevi Hemen Başlat (Otomatik Yürüt)")
        self.chk_execute.setChecked(True)
        self.chk_execute.setStyleSheet("color: #38bdf8; font-weight: bold; margin-top: 6px;")
        form.addRow("", self.chk_execute)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("İptal")
        btn_cancel.setStyleSheet("background-color: #475569; color: #ffffff; padding: 6px 14px; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Kaydet")
        btn_save.setStyleSheet("background-color: #2563eb; color: #ffffff; padding: 6px 16px; border-radius: 4px; font-weight: bold;")
        btn_save.clicked.connect(self.accept)

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def get_data(self):
        criteria = [c.strip() for c in self.txt_crit.text().split(",") if c.strip()]
        dod = [d.strip() for d in self.txt_dod.text().split(",") if d.strip()]
        return {
            "title": self.txt_title.text().strip(),
            "description": self.txt_desc.toPlainText().strip(),
            "role": DeskRole(self.cb_role.currentText()),
            "criteria": criteria,
            "definition_of_done": dod,
            "verification_command": self.txt_verif.text().strip() or None,
            "auto_execute": self.chk_execute.isChecked(),
        }


class OfficeDetailWidget(QWidget):
    back_requested = Signal()

    def __init__(
        self,
        orchestrator: OfficeOrchestrator,
        memory_partition: Optional[OfficeMemoryPartition] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.memory_partition = memory_partition or OfficeMemoryPartition()
        self.task_executor = AgyTaskExecutor(memory_partition=self.memory_partition)
        self.terminal_panes: Dict[str, AgentTerminalPane] = {}
        self._is_closing: bool = False

        self._setup_ui()
        self._sync_with_orchestrator()

        # Thread-safe Qt Signal Bridge (QueuedConnection guarantees slot runs on main GUI thread)
        self.event_bridge = DetailEventBridge(self)
        self.event_bridge.event_dispatched.connect(self._on_orchestrator_event, Qt.QueuedConnection)
        self.orchestrator.on_event = self._dispatch_event_threadsafe

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 1. Üst Kontrol Barı (Top Control Bar)
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #1a202c; border-radius: 8px; padding: 6px;")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(8, 6, 8, 6)
        tb_layout.setSpacing(8)

        btn_back = QPushButton("⬅ Ofisler Genel Bakış")
        btn_back.setStyleSheet("background-color: #334155; color: #f1f5f9; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        btn_back.clicked.connect(self.back_requested.emit)

        self.lbl_office_name = QLabel(f"🏢 {self.orchestrator.config.name}")
        self.lbl_office_name.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: bold;")

        btn_edit_office = QPushButton("✏️ Ofisi Düzenle")
        btn_edit_office.setStyleSheet("background-color: #475569; color: #f1f5f9; padding: 6px 10px; border-radius: 4px;")
        btn_edit_office.clicked.connect(self._prompt_edit_office)

        # Live Antigravity Status Badge in detail view
        self.agy_status_widget = AgyStatusWidget()

        btn_goal = QPushButton("🎯 Hedef Dağıt (Goal Delegation)")
        btn_goal.setStyleSheet("background-color: #7c3aed; color: #ffffff; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        btn_goal.clicked.connect(self._prompt_delegate_goal)

        btn_add_task = QPushButton("➕ Yeni Görev Ekle")
        btn_add_task.setStyleSheet("background-color: #2563eb; color: #ffffff; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        btn_add_task.clicked.connect(self._prompt_add_task)

        btn_add_agent = QPushButton("🤖 Yeni Ajan Ata")
        btn_add_agent.setStyleSheet("background-color: #0d9488; color: #ffffff; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        btn_add_agent.clicked.connect(self._prompt_add_agent)

        btn_run_task = QPushButton("▶️ Sıradaki Görevi İşlet")
        btn_run_task.setStyleSheet("background-color: #16a34a; color: #ffffff; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        btn_run_task.clicked.connect(self._run_next_task)

        btn_sprint = QPushButton("⚡ Otonom Sprint Başlat")
        btn_sprint.setStyleSheet("background-color: #ea580c; color: #ffffff; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        btn_sprint.setToolTip("Bekleyen tüm görevleri sırayla A2A devirleriyle otonom olarak tamamlar.")
        btn_sprint.clicked.connect(self._run_autonomous_sprint)

        tb_layout.addWidget(btn_back)
        tb_layout.addWidget(self.lbl_office_name)
        tb_layout.addWidget(btn_edit_office)
        tb_layout.addStretch()
        tb_layout.addWidget(self.agy_status_widget)
        tb_layout.addWidget(btn_goal)
        tb_layout.addWidget(btn_add_task)
        tb_layout.addWidget(btn_add_agent)
        tb_layout.addWidget(btn_run_task)
        tb_layout.addWidget(btn_sprint)

        root_layout.addWidget(top_bar)

        # 2. Ana Çalışma Alanı (Splitter: Sol PixelCanvas / Sağ Paneller)
        splitter = QSplitter(Qt.Horizontal)

        # Sol: PixelCanvas
        canvas_container = QFrame()
        canvas_container.setStyleSheet("background-color: #0f121a; border-radius: 8px; border: 1px solid #1e293b;")
        cc_layout = QVBoxLayout(canvas_container)
        cc_layout.setContentsMargins(6, 6, 6, 6)

        self.pixel_canvas = PixelCanvas()
        self.pixel_canvas.agent_selected.connect(self._on_canvas_agent_selected)
        cc_layout.addWidget(self.pixel_canvas)
        splitter.addWidget(canvas_container)

        # Sağ: Tablar (Kanban, Terminaller, Todo & Sohbet, Hafıza)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            """
            QTabWidget::pane { border: 1px solid #1e293b; background-color: #0f121a; border-radius: 8px; }
            QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 8px 14px; margin-right: 4px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #334155; color: #38bdf8; font-weight: bold; }
            """
        )

        # Tab 0: Kanban Görev Panosu
        self.kanban_board = KanbanBoardWidget()
        self.kanban_board.run_task_requested.connect(self._run_task_by_id)
        self.kanban_board.edit_task_requested.connect(self._edit_task_by_id)
        self.kanban_board.delete_task_requested.connect(self._delete_task_by_id)
        self.kanban_board.reset_task_requested.connect(self._reset_task_by_id)
        self.kanban_board.inspect_evidence_requested.connect(self._inspect_task_evidence)
        self.tabs.addTab(self.kanban_board, "📋 Kanban Panosu")

        # Tab 1: Terminaller (Tabs & Split Grid View)
        self.terminal_grid = TerminalGridWidget()
        self.terminal_grid.grid_mode_changed.connect(self._on_grid_mode_changed)
        self.tabs.addTab(self.terminal_grid, "📟 Terminaller")

        # Tab 2: Todo & Sohbet
        todo_chat_widget = QWidget()
        tc_layout = QVBoxLayout(todo_chat_widget)
        tc_layout.setContentsMargins(8, 8, 8, 8)
        tc_layout.setSpacing(6)

        lbl_todo = QLabel("📋 Ofis Todo Listesi (FSM Task Ledger)")
        lbl_todo.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")
        
        self.list_todo = QListWidget()
        self.list_todo.setStyleSheet("background-color: #0b0f19; color: #e2e8f0; border: 1px solid #1e293b; border-radius: 6px;")

        # Todo List Action Bar
        task_action_bar = QHBoxLayout()
        btn_run_selected = QPushButton("▶️ Seçili Görevi Çalıştır")
        btn_run_selected.setStyleSheet("background-color: #16a34a; color: #ffffff; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        btn_run_selected.clicked.connect(self._run_selected_task)

        btn_edit_selected = QPushButton("✏️ Düzenle")
        btn_edit_selected.setStyleSheet("background-color: #334155; color: #ffffff; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        btn_edit_selected.clicked.connect(self._edit_selected_task)

        btn_delete_selected = QPushButton("🗑️ Sil")
        btn_delete_selected.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        btn_delete_selected.clicked.connect(self._delete_selected_task)

        btn_reset_selected = QPushButton("🔄 Sıfırla (Pending)")
        btn_reset_selected.setStyleSheet("background-color: #334155; color: #cbd5e1; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        btn_reset_selected.clicked.connect(self._reset_selected_task)

        btn_stop_selected = QPushButton("⏹️ Durdur (Kill Tree)")
        btn_stop_selected.setStyleSheet("background-color: #991b1b; color: #fecaca; border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: bold;")
        btn_stop_selected.clicked.connect(self._stop_selected_task)

        task_action_bar.addWidget(btn_run_selected)
        task_action_bar.addWidget(btn_edit_selected)
        task_action_bar.addWidget(btn_delete_selected)
        task_action_bar.addWidget(btn_reset_selected)
        task_action_bar.addWidget(btn_stop_selected)
        task_action_bar.addStretch()

        lbl_chat = QLabel("💬 Ofis İçi Sohbet & Orkestrasyon Günlüğü")
        lbl_chat.setStyleSheet("color: #a855f7; font-weight: bold; font-size: 13px; margin-top: 6px;")
        self.list_chat = QListWidget()
        self.list_chat.setStyleSheet("background-color: #0b0f19; color: #e2e8f0; border: 1px solid #1e293b; border-radius: 6px;")

        tc_layout.addWidget(lbl_todo)
        tc_layout.addWidget(self.list_todo, 2)
        tc_layout.addLayout(task_action_bar)
        tc_layout.addWidget(lbl_chat)
        tc_layout.addWidget(self.list_chat, 2)
        self.tabs.addTab(todo_chat_widget, "📋 Todo & Sohbet")

        # Tab 3: Bölümlendirilmiş Hafıza & 2D Bilgi Grafiği (Memory Knowledge Graph)
        memory_widget = QWidget()
        mem_layout = QVBoxLayout(memory_widget)
        mem_layout.setContentsMargins(8, 8, 8, 8)
        mem_layout.setSpacing(6)

        mem_header_bar = QHBoxLayout()
        lbl_mem = QLabel("🧠 Bilişsel Hafıza & Düğüm Grafiği (Multi-Tenant GraphRAG)")
        lbl_mem.setStyleSheet("color: #14b8a6; font-weight: bold; font-size: 13px;")

        btn_refresh_graph = QPushButton("🔄 Grafiği Tazele")
        btn_refresh_graph.setStyleSheet("background-color: #334155; color: #ffffff; padding: 4px 8px; border-radius: 4px; font-size: 11px;")
        btn_refresh_graph.clicked.connect(self._refresh_memory_list)

        btn_add_note = QPushButton("➕ Yeni Not Ekle")
        btn_add_note.setStyleSheet("background-color: #0d9488; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
        btn_add_note.clicked.connect(self._prompt_add_memory_note)

        btn_sync_obsidian = QPushButton("📖 Obsidian'a Aktar")
        btn_sync_obsidian.setStyleSheet("background-color: #475569; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
        btn_sync_obsidian.clicked.connect(self._sync_all_notes_to_obsidian)

        mem_header_bar.addWidget(lbl_mem)
        mem_header_bar.addStretch()
        mem_header_bar.addWidget(btn_refresh_graph)
        mem_header_bar.addWidget(btn_add_note)
        mem_header_bar.addWidget(btn_sync_obsidian)
        mem_layout.addLayout(mem_header_bar)

        # 2D Interactive Knowledge Graph
        graph_box = QFrame()
        graph_box.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 6px;")
        gb_layout = QVBoxLayout(graph_box)
        gb_layout.setContentsMargins(4, 4, 4, 4)

        self.memory_graph_canvas = MemoryGraphCanvas()
        self.memory_graph_canvas.node_selected.connect(self._on_graph_node_selected)
        gb_layout.addWidget(self.memory_graph_canvas)

        # Node Inspector & Notes List Splitter
        mem_splitter = QSplitter(Qt.Vertical)
        mem_splitter.addWidget(graph_box)

        # Bottom Inspector & Notes List
        bottom_box = QWidget()
        bb_layout = QVBoxLayout(bottom_box)
        bb_layout.setContentsMargins(0, 4, 0, 0)
        bb_layout.setSpacing(4)

        self.lbl_node_inspector = QLabel("💡 Düğüm Detayı: İncelemek için grafikten bir düğüme tıklayın.")
        self.lbl_node_inspector.setStyleSheet("background-color: #1e293b; color: #38bdf8; padding: 4px 8px; border-radius: 4px; font-size: 11px;")

        self.list_memory = QListWidget()
        self.list_memory.setMaximumHeight(120)
        self.list_memory.setStyleSheet("background-color: #0b0f19; color: #e2e8f0; border: 1px solid #1e293b; border-radius: 6px;")

        bb_layout.addWidget(self.lbl_node_inspector)
        bb_layout.addWidget(self.list_memory)
        mem_splitter.addWidget(bottom_box)
        mem_splitter.setSizes([320, 140])

        mem_layout.addWidget(mem_splitter, 1)
        self.tabs.addTab(memory_widget, "🧠 Bilişsel Hafıza Grafiği")

        # Tab 4: ChatFlow (Muratify Takım Sohbeti & Görev Devirleri)
        self.chatflow_widget = ChatFlowWidget()
        self.chatflow_widget.message_sent.connect(self._on_chatflow_message_sent)
        self.chatflow_widget.handoff_dispatched.connect(self._on_chatflow_handoff_dispatched)
        self.tabs.addTab(self.chatflow_widget, "💬 ChatFlow")

        # Tab 5: Ekip Kadrosu (RPG Crew Roster)
        self.crew_roster_widget = CrewRosterWidget()
        self.crew_roster_widget.break_toggled.connect(self._on_crew_break_toggled)
        self.tabs.addTab(self.crew_roster_widget, "👥 Ekip (Crew)")

        splitter.addWidget(self.tabs)
        splitter.setSizes([460, 540])
        root_layout.addWidget(splitter, 1)

    def _sync_with_orchestrator(self):
        # 1. Canvas'a personelleri ver
        sub_personas = [ag.persona for ag in self.orchestrator.sub_agents.values()]
        self.pixel_canvas.set_personas(self.orchestrator.persona, sub_personas)

        # 2. Terminalleri senkronize et
        self._ensure_terminal(self.orchestrator.persona)
        for ag in self.orchestrator.sub_agents.values():
            self._ensure_terminal(ag.persona)

        # Kullanılmayan sekmeleri temizle
        active_ids = {self.orchestrator.persona.agent_id} | set(self.orchestrator.sub_agents.keys())
        for aid in list(self.terminal_panes.keys()):
            if aid not in active_ids:
                pane = self.terminal_panes.pop(aid)
                self.terminal_grid.remove_pane(aid)

        # 3. Crew Roster ve ChatFlow senkronizasyonu
        all_personas = [self.orchestrator.persona] + [ag.persona for ag in self.orchestrator.sub_agents.values()]
        self.crew_roster_widget.set_personas(all_personas)

        # 4. Todo, sohbet ve hafızayı tazele
        self._refresh_todo_list()
        self._refresh_chat_history()
        self._refresh_memory_list()

        # 5. Ofis ızgara düzen modunu senkronize et
        grid_mode = getattr(self.orchestrator.config, "grid_mode", "tabbed")
        self.terminal_grid.set_grid_mode(grid_mode)
        self.pixel_canvas.apply_grid_mode(grid_mode)

    def _ensure_terminal(self, persona):
        if persona.agent_id not in self.terminal_panes:
            pane = AgentTerminalPane(persona=persona)
            pane.agent_edit_requested.connect(self._edit_agent)
            pane.agent_delete_requested.connect(self._delete_agent)
            pane.prompt_submitted.connect(self._on_terminal_prompt_submitted)
            pane.payload_attached.connect(self._on_terminal_payload_attached)
            self.terminal_panes[persona.agent_id] = pane
            tab_title = f"{persona.name[:16]}"
            self.terminal_grid.add_or_update_pane(persona.agent_id, pane, tab_title)
        else:
            self.terminal_panes[persona.agent_id].refresh_persona(persona)
            self.terminal_grid.add_or_update_pane(persona.agent_id, self.terminal_panes[persona.agent_id], persona.name[:16])

    def _on_terminal_prompt_submitted(self, agent_id: str, prompt_text: str, attachments: list):
        agent_name = agent_id
        target_role = DeskRole.DEVELOPER
        if self.orchestrator.persona.agent_id == agent_id:
            agent_name = self.orchestrator.persona.name
            target_role = self.orchestrator.persona.role
        elif agent_id in self.orchestrator.sub_agents:
            worker = self.orchestrator.sub_agents[agent_id]
            agent_name = worker.persona.name
            target_role = worker.persona.role

        msg_body = f"[Doğrudan İstem -> {agent_name}]: {prompt_text}"
        if attachments:
            msg_body += f" (📎 {len(attachments)} dosya)"
        self.chatflow_widget.add_message(
            channel="#lider-istekleri",
            sender="Lider",
            text=msg_body,
            role="Lider",
            avatar="👑",
            is_leader=True,
        )

        if prompt_text.strip():
            task = self.orchestrator.add_task(
                title=prompt_text[:50] + ("..." if len(prompt_text) > 50 else ""),
                description=prompt_text,
                role_target=target_role,
                media_attachments=list(attachments),
            )
            self._refresh_todo_list()
            self.orchestrator.execute_specific_task(
                task_id=task.task_id,
                task_executor=self.task_executor,
                async_run=True,
            )

    def _on_terminal_payload_attached(self, agent_id: str, paths: list):
        agent_name = agent_id
        if self.orchestrator.persona.agent_id == agent_id:
            agent_name = self.orchestrator.persona.name
        elif agent_id in self.orchestrator.sub_agents:
            agent_name = self.orchestrator.sub_agents[agent_id].persona.name

        file_names = ", ".join(os.path.basename(p) for p in paths)
        self.chatflow_widget.add_message(
            channel="#lider-istekleri",
            sender="Lider",
            text=f"📎 Medya eklendi -> {agent_name}: {file_names}",
            role="Lider",
            avatar="📎",
            is_leader=True,
        )

    def _on_chatflow_message_sent(self, channel: str, sender: str, text: str):
        self.orchestrator.chat_history.append({
            "sender": sender,
            "text": f"[{channel}] {text}",
            "time": time.time(),
        })

    def _on_chatflow_handoff_dispatched(self, channel: str, from_agent: str, to_agent: str, summary: str):
        handoff_log = f"\n[🔄 GÖREV DEVRİ]: {from_agent} ➔ {to_agent}: '{summary}'\n"
        for pane in self.terminal_panes.values():
            pane.append_chunk(handoff_log)

    def _on_crew_break_toggled(self, agent_id: str, is_on_break: bool):
        new_state = AgentActivityState.COFFEE_BREAK if is_on_break else AgentActivityState.IDLE
        persona = None
        if self.orchestrator.persona.agent_id == agent_id:
            persona = self.orchestrator.persona
        elif agent_id in self.orchestrator.sub_agents:
            persona = self.orchestrator.sub_agents[agent_id].persona

        if persona:
            persona.activity_state = new_state
            if is_on_break:
                persona.active_speech_text = "☕ Kahve molasındayım..."
            else:
                persona.rest_and_recharge(30.0)
                persona.active_speech_text = ""
            if agent_id in self.terminal_panes:
                self.terminal_panes[agent_id].update_activity_state(new_state)

        self.pixel_canvas.update_office(self.orchestrator)
        self.crew_roster_widget.populate_crew(self.orchestrator)

    def _on_canvas_agent_selected(self, agent_id: str):
        if agent_id in self.terminal_panes:
            self.tabs.setCurrentWidget(self.terminal_grid)
            self.terminal_grid.focus_agent(agent_id)

    def _refresh_todo_list(self):
        # 1. Kanban Panosunu güncelle
        self.kanban_board.populate_tasks(self.orchestrator.todo_list)

        # 2. Yedek Todo Listesini güncelle
        self.list_todo.clear()
        for task in self.orchestrator.todo_list:
            status_emojis = {
                TaskStatus.PENDING: "⏳ PENDING",
                TaskStatus.IN_PROGRESS: "⚙️ IN_PROGRESS",
                TaskStatus.VERIFYING: "🔍 VERIFYING",
                TaskStatus.COMPLETED: "✅ COMPLETED",
                TaskStatus.FAILED: "⚠️ FAILED",
                TaskStatus.ESCALATED: "🚨 ESCALATED",
                TaskStatus.CANCELLED: "⏹️ CANCELLED",
            }
            item_text = f"[{status_emojis.get(task.status, task.status.value)}] {task.title} (Rol: {task.role_target.value}, Deneme: {task.retry_count}/{task.max_retries})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, task.task_id)
            self.list_todo.addItem(item)

    def _refresh_chat_history(self):
        self.list_chat.clear()
        for msg in self.orchestrator.chat_history[-50:]:
            item = QListWidgetItem(f"[{msg['sender_name']}]: {msg['message']}")
            self.list_chat.addItem(item)
        self.list_chat.scrollToBottom()

    def _refresh_memory_list(self):
        self.list_memory.clear()
        records = self.memory_partition.list_office_notes(self.orchestrator.config.office_id)
        for rec in records:
            item = QListWidgetItem(f"📄 {rec.title} [Tags: {', '.join(rec.tags)}]")
            item.setToolTip(f"{rec.content[:300]}...")
            self.list_memory.addItem(item)

        # 2D Knowledge Graph Verisini Güncelle
        try:
            graph_data = MemoryGraphBridge.generate_office_graph(self.orchestrator, self.memory_partition)
            self.memory_graph_canvas.set_graph_data(graph_data)
        except Exception:
            pass

    def _on_graph_node_selected(self, node_data: dict):
        label = node_data.get("label", "Düğüm")
        ntype = node_data.get("type", "node")
        model = node_data.get("model")
        status = node_data.get("status")
        info_parts = [f"📌 {label}", f"Tür: {ntype}"]
        if model:
            info_parts.append(f"Model: {AGYModelRegistry.get_display_name(model)}")
        if status:
            info_parts.append(f"Durum: {status.upper()}")
        self.lbl_node_inspector.setText("  |  ".join(info_parts))

    def _dispatch_event_threadsafe(self, event_type: str, data: dict):
        if not getattr(self, "_is_closing", False) and hasattr(self, "event_bridge"):
            try:
                self.event_bridge.event_dispatched.emit(event_type, data)
            except (RuntimeError, Exception):
                pass

    def cleanup(self):
        """Cleanly unbinds listeners and stops events from reaching a destroyed C++ QWidget."""
        self._is_closing = True
        try:
            if getattr(self.orchestrator, "on_event", None) == self._dispatch_event_threadsafe:
                self.orchestrator.on_event = None
        except Exception:
            pass

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def _on_orchestrator_event(self, event_type: str, data: dict):
        if getattr(self, "_is_closing", False):
            return

        try:
            if event_type == "agent_activity":
                aid = data.get("agent_id")
                state_str = data.get("state", "idle")
                try:
                    st = AgentActivityState(state_str)
                    self.pixel_canvas.update_agent_activity(aid, st)
                    if aid in self.terminal_panes:
                        self.terminal_panes[aid].update_activity_state(st)
                except Exception:
                    pass
            elif event_type == "token_chunk":
                aid = data.get("agent_id")
                chunk = data.get("chunk", "")
                if aid in self.terminal_panes:
                    self.terminal_panes[aid].append_chunk(chunk)
            elif event_type in ["task_added", "task_updated", "task_deleted", "task_completed", "task_retrying", "task_escalated"]:
                self._refresh_todo_list()
            elif event_type == "handoff_dispatched":
                ch = data.get("channel", "#kodlama")
                src = data.get("from_agent", "Orkestratör")
                dst = data.get("to_agent", "Developer")
                summary = data.get("summary", "")
                self.chatflow_widget.add_handoff_message(ch, src, dst, summary)
            elif event_type in ["sprint_started", "sprint_completed"]:
                self._refresh_todo_list()
            elif event_type == "chat_message":
                self._refresh_chat_history()
            elif event_type in ["agent_created", "agent_updated", "agent_deleted"]:
                self._sync_with_orchestrator()
            elif event_type == "grid_mode_changed":
                mode_str = data.get("grid_mode", "tabbed")
                self.terminal_grid.set_grid_mode(mode_str)
                self.pixel_canvas.apply_grid_mode(mode_str)
        except Exception as e:
            pass

    def _on_grid_mode_changed(self, mode_str: str):
        try:
            if self.orchestrator.get_grid_mode().value != mode_str:
                self.orchestrator.set_grid_mode(mode_str)
            self.pixel_canvas.apply_grid_mode(mode_str)
        except Exception:
            pass

    def _prompt_delegate_goal(self):
        dialog = GoalDelegationDialog(office_name=self.orchestrator.config.name, parent=self)
        if dialog.exec() == QDialog.Accepted:
            goal_text = dialog.get_goal_text()
            if not goal_text:
                return
            auto_exec = dialog.should_auto_execute()
            subtasks = self.orchestrator.delegate_goal(
                goal=goal_text,
                task_executor=self.task_executor if auto_exec else None,
                auto_execute=auto_exec,
            )
            self._refresh_todo_list()
            QMessageBox.information(
                self,
                "Hedef Dağıtıldı",
                f"Lider orkestratör hedefi {len(subtasks)} alt göreve ayrıştırdı ve Kanban panosuna yerleştirdi."
            )

    def _inspect_task_evidence(self, task_id: str):
        task = next((t for t in self.orchestrator.todo_list if t.task_id == task_id), None)
        if not task:
            return
        dialog = EvidenceInspectorDialog(task=task, parent=self)
        dialog.exec()

    def _run_task_by_id(self, task_id: str):
        res = self.orchestrator.execute_specific_task(
            task_id=task_id,
            task_executor=self.task_executor,
            async_run=True,
        )
        if res:
            self._refresh_todo_list()

    def _edit_task_by_id(self, task_id: str):
        task = next((t for t in self.orchestrator.todo_list if t.task_id == task_id), None)
        if not task:
            return
        dialog = TaskEditDialog(task=task, parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self.orchestrator.update_task(
                task_id=task.task_id,
                title=data["title"],
                description=data["description"],
                role_target=data["role"],
                acceptance_criteria=data["criteria"],
                verification_command=data["verification_command"],
            )
            task.definition_of_done = data.get("definition_of_done", [])
            self.orchestrator.save_to_disk()
            self._refresh_todo_list()

    def _delete_task_by_id(self, task_id: str):
        reply = QMessageBox.question(
            self,
            "Görevi Sil",
            "Bu görevi silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.orchestrator.delete_task(task_id)
            self._refresh_todo_list()

    def _reset_task_by_id(self, task_id: str):
        self.orchestrator.reset_task(task_id)
        self._refresh_todo_list()

    def _prompt_add_task(self):
        dialog = TaskEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                return

            task = self.orchestrator.add_task(
                title=data["title"],
                description=data["description"],
                role_target=data["role"],
                acceptance_criteria=data["criteria"],
                definition_of_done=data.get("definition_of_done"),
                verification_command=data["verification_command"],
            )
            self._refresh_todo_list()

            if data["auto_execute"]:
                self.orchestrator.execute_specific_task(
                    task_id=task.task_id,
                    task_executor=self.task_executor,
                    async_run=True,
                )

    def _get_selected_task_id(self) -> Optional[str]:
        cur = self.list_todo.currentItem()
        if not cur:
            QMessageBox.information(self, "Seçim Yok", "Lütfen listeden bir görev seçin.")
            return None
        return cur.data(Qt.UserRole)

    def _run_selected_task(self):
        task_id = self._get_selected_task_id()
        if task_id:
            self._run_task_by_id(task_id)

    def _edit_selected_task(self):
        task_id = self._get_selected_task_id()
        if task_id:
            self._edit_task_by_id(task_id)

    def _delete_selected_task(self):
        task_id = self._get_selected_task_id()
        if task_id:
            self._delete_task_by_id(task_id)

    def _reset_selected_task(self):
        task_id = self._get_selected_task_id()
        if task_id:
            self._reset_task_by_id(task_id)

    def _stop_selected_task(self):
        task_id = self._get_selected_task_id()
        if not task_id:
            return
        self.orchestrator.cancel_task(task_id, task_executor=self.task_executor)
        self._refresh_todo_list()

    def _run_next_task(self):
        res = self.orchestrator.execute_next_task(task_executor=self.task_executor, async_run=True)
        if not res:
            QMessageBox.information(self, "Bilgi", "İşletilecek bekleyen (pending) veya başarısız görev bulunamadı.")
        else:
            self._refresh_todo_list()

    def _run_autonomous_sprint(self):
        started = self.orchestrator.run_autonomous_sprint(task_executor=self.task_executor, async_run=True)
        if not started:
            QMessageBox.information(self, "Bilgi", "İşletilecek bekleyen (pending) görev bulunamadı.")
        else:
            self._refresh_todo_list()

    def _prompt_add_agent(self):
        name, ok1 = QInputDialog.getText(self, "Yeni Ajan", "Ajan Adı:")
        if not ok1 or not name.strip():
            return

        roles = [r.value for r in DeskRole if r != DeskRole.ORCHESTRATOR]
        role_str, ok2 = QInputDialog.getItem(self, "Ajan Rolü", "Rol Seçin:", roles, 0, False)
        if not ok2:
            return

        models = AGYModelRegistry.list_model_ids()
        model_str, ok3 = QInputDialog.getItem(self, "AGY Modeli", "Model Seçin:", models, 0, False)
        if not ok3:
            return

        prompt, ok4 = QInputDialog.getText(self, "Sistem Talimatı", "Uzmanlık Yönergesi (System Prompt):")
        if not ok4:
            prompt = ""

        try:
            self.orchestrator.create_sub_agent(
                name=name.strip(),
                role=DeskRole(role_str),
                model=model_str,
                system_prompt=prompt.strip(),
            )
        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))

    def _edit_agent(self, agent_id: str):
        worker = self.orchestrator.sub_agents.get(agent_id)
        if not worker:
            return

        p = worker.persona
        name, ok1 = QInputDialog.getText(self, "Ajanı Düzenle", "Ajan Adı:", text=p.name)
        if not ok1 or not name.strip():
            return

        roles = [r.value for r in DeskRole if r != DeskRole.ORCHESTRATOR]
        cur_role_idx = roles.index(p.role.value) if p.role.value in roles else 0
        role_str, ok2 = QInputDialog.getItem(self, "Ajan Rolü", "Rol Seçin:", roles, cur_role_idx, False)
        if not ok2:
            return

        models = AGYModelRegistry.list_model_ids()
        cur_m_idx = models.index(p.model) if p.model in models else 0
        model_str, ok3 = QInputDialog.getItem(self, "AGY Modeli", "Model Seçin:", models, cur_m_idx, False)
        if not ok3:
            return

        prompt, ok4 = QInputDialog.getText(self, "Sistem Talimatı", "Yönerge:", text=p.system_prompt)
        if not ok4:
            prompt = p.system_prompt

        self.orchestrator.update_sub_agent(
            agent_id=agent_id,
            name=name.strip(),
            role=DeskRole(role_str),
            model=model_str,
            system_prompt=prompt.strip(),
        )

    def _delete_agent(self, agent_id: str):
        worker = self.orchestrator.sub_agents.get(agent_id)
        name = worker.persona.name if worker else agent_id
        reply = QMessageBox.question(
            self,
            "Ajanı Kaldır",
            f"'{name}' personelini ofisten çıkarmak ve masasını boşaltmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.orchestrator.delete_sub_agent(agent_id)

    def _prompt_edit_office(self):
        c = self.orchestrator.config
        new_name, ok1 = QInputDialog.getText(self, "Ofisi Düzenle", "Ofis Adı:", text=c.name)
        if not ok1 or not new_name.strip():
            return

        new_path, ok2 = QInputDialog.getText(self, "Ofisi Düzenle", "Proje Kök Dizini:", text=c.project_root)
        if not ok2 or not new_path.strip():
            return

        new_desc, ok3 = QInputDialog.getText(self, "Ofisi Düzenle", "Açıklama:", text=c.description)
        if not ok3:
            new_desc = c.description

        models = AGYModelRegistry.list_model_ids()
        cur_m = self.orchestrator.persona.model
        cur_idx = models.index(cur_m) if cur_m in models else 0
        model_str, ok4 = QInputDialog.getItem(self, "Ofisi Düzenle", "Lider Orkestratör Modeli:", models, cur_idx, False)
        if not ok4:
            model_str = cur_m

        c.name = new_name.strip()
        c.project_root = new_path.strip()
        c.description = new_desc.strip()
        self.orchestrator.persona.name = f"{c.name} Orkestratörü"
        self.orchestrator.persona.model = model_str
        self.lbl_office_name.setText(f"🏢 {c.name}")
        self.orchestrator._notify_state_changed()
        self._sync_with_orchestrator()

    def _prompt_add_memory_note(self):
        title, ok1 = QInputDialog.getText(self, "Bilişsel Not Ekle", "Not Başlığı:")
        if not ok1 or not title.strip():
            return
        content, ok2 = QInputDialog.getText(self, "Bilişsel Not Ekle", "Not İçeriği:")
        if not ok2 or not content.strip():
            return

        self.memory_partition.store_memory(
            office_id=self.orchestrator.config.office_id,
            title=title.strip(),
            content=content.strip(),
            tags=["manual_note", self.orchestrator.config.office_id],
        )
        self._refresh_memory_list()

    def _sync_all_notes_to_obsidian(self):
        records = self.memory_partition.list_office_notes(self.orchestrator.config.office_id)
        for r in records:
            self.memory_partition.sync_to_obsidian(r)
        QMessageBox.information(
            self,
            "Obsidian Senkronizasyonu",
            f"{len(records)} adet bilişsel hafıza notu Obsidian Kasası'na başarıyla aktarıldı."
        )
