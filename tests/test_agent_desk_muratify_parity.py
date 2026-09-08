"""
Tests for Muratify AgentSpace Feature Parity across Entropy Agent Desk.
Verifies end-to-end integration:
- Media handling (PDFs & Images) in tasks and prompts.
- EvidenceInspectorDialog and KanbanCardWidget attachment indicators.
- Interactive terminal prompt submission & automated task dispatch.
- ChatFlow multi-channel messaging and agent handoff cards.
- Crew Roster RPG gamification (XP, Leveling, Energy drain & Coffee recharge).
- Pixel Canvas visual state updates.
- 1-Click clean project exporter (.zip) and Git checkpointing.
"""

import os
import sys
import tempfile
import zipfile
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.entropy.agent_desk.core.models import (
    OfficeConfig,
    DeskRole,
    AgentPersona,
    AgentActivityState,
    TaskItem,
    TaskStatus,
)
from src.entropy.agent_desk.core.worker_agent import WorkerAgent
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.core.media_payload_handler import MediaPayloadHandler, MediaPayloadInfo
from src.entropy.agent_desk.core.project_exporter import ProjectExporter
from src.entropy.agent_desk.core.agy_task_executor import AgyTaskExecutor
from src.entropy.agent_desk.ui.kanban_board_widget import KanbanCardWidget, EvidenceInspectorDialog
from src.entropy.agent_desk.ui.chatflow_widget import ChatFlowWidget
from src.entropy.agent_desk.ui.crew_roster_widget import CrewRosterWidget
from src.entropy.agent_desk.ui.agent_terminal_pane import AgentTerminalPane
from src.entropy.agent_desk.ui.pixel_canvas import PixelCanvas


TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

DUMMY_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
    b"2 0 obj <</Type /Pages /Kids [3 0 R 4 0 R] /Count 2>> endobj\n"
    b"3 0 obj <</Type /Page /Parent 2 0 R /Contents 5 0 R>> endobj\n"
    b"4 0 obj <</Type /Page /Parent 2 0 R /Contents 6 0 R>> endobj\n"
    b"5 0 obj <</Length 20>> stream\n(First Page Text) Tj\nendstream endobj\n"
    b"6 0 obj <</Length 21>> stream\n(Second Page Text) Tj\nendstream endobj\n"
    b"xref\n0 7\ntrailer <</Root 1 0 R>>\nstartxref\n300\n%%EOF"
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])
    return app


@pytest.fixture
def sample_media_files(tmp_path):
    """Creates temporary PDF and PNG files for testing."""
    img_path = tmp_path / "diagram.png"
    img_path.write_bytes(TINY_PNG)

    pdf_path = tmp_path / "spec.pdf"
    pdf_path.write_bytes(DUMMY_PDF)

    return str(img_path), str(pdf_path)


def test_media_payload_formatting_and_prompt_injection(sample_media_files):
    img_path, pdf_path = sample_media_files
    info_img = MediaPayloadHandler.inspect_file(img_path)
    info_pdf = MediaPayloadHandler.inspect_file(pdf_path)

    assert info_img.is_image is True
    assert info_pdf.is_pdf is True
    assert info_pdf.pdf_page_count == 2

    # Supports passing file paths directly
    formatted_md = MediaPayloadHandler.format_markdown_attachments([img_path, pdf_path])
    assert "İliştirilmiş Medya" in formatted_md
    assert "diagram.png" in formatted_md
    assert "spec.pdf" in formatted_md

    # Test Prompt construction with executor
    executor = AgyTaskExecutor(allow_live_agy=False)
    task = TaskItem(
        task_id="t_prompt_01",
        office_id="office_test",
        title="UI Tasarımı Kodlama",
        description="Figma görseline ve PDF spekine göre tasarımı kodla.",
        media_attachments=[img_path, pdf_path],
    )
    worker = WorkerAgent(AgentPersona(
        agent_id="dev_1",
        name="Developer Specialist",
        office_id="office_test",
        role=DeskRole.DEVELOPER,
    ))

    prompt = executor._build_task_prompt(task, worker, "Test context")
    assert "İliştirilmiş Medya" in prompt
    assert "diagram.png" in prompt
    assert "spec.pdf" in prompt


def test_kanban_evidence_dialog_and_card_with_media(qapp, sample_media_files):
    img_path, pdf_path = sample_media_files
    task = TaskItem(
        task_id="t_kanban_01",
        office_id="office_test",
        title="Kanban Medya Görevi",
        description="Görsel ve PDF içeren görev.",
        media_attachments=[img_path, pdf_path],
        evidence_verified=True,
        evidence_log="Test output verified 100% PASS",
    )

    card = KanbanCardWidget(task)
    assert card is not None
    # Card contains the attachments indicator
    labels = card.findChildren(object)
    has_media_chip = any("2 ek" in getattr(l, "text", lambda: "")() for l in labels if hasattr(l, "text"))
    assert has_media_chip is True

    # Inspector dialog
    dialog = EvidenceInspectorDialog(task)
    assert dialog is not None
    dlg_labels = [getattr(l, "text", lambda: "")() for l in dialog.findChildren(object) if hasattr(l, "text")]
    assert any("İliştirilmiş Medya Ekleri (2 Dosya)" in t for t in dlg_labels)
    assert any("spec.pdf" in t for t in dlg_labels)
    assert any("diagram.png" in t for t in dlg_labels)


def test_crew_roster_gamification_and_coffee_break(qapp):
    config = OfficeConfig(
        office_id="gamified_office",
        name="Gamified HQ",
        project_root=".",
        orchestrator_agent_id="orch_01",
    )
    orchestrator = OfficeOrchestrator(config=config)
    orchestrator.ensure_default_crew()

    # Find one of the sub-agents
    sub_keys = list(orchestrator.sub_agents.keys())
    assert len(sub_keys) > 0
    dev_key = sub_keys[0]
    dev = orchestrator.sub_agents[dev_key]

    initial_xp = dev.persona.xp
    initial_energy = dev.persona.focus_energy_pct

    # Add XP
    new_level = dev.persona.add_xp(150)
    assert dev.persona.xp == initial_xp + 150
    assert dev.persona.level >= 2
    assert new_level >= 2

    # Consume energy during work
    dev.persona.consume_energy(40.0)
    assert dev.persona.focus_energy_pct == initial_energy - 40.0

    # Rest and recharge
    dev.persona.rest_and_recharge(25.0)
    assert dev.persona.focus_energy_pct == initial_energy - 15.0

    # Crew roster widget
    roster = CrewRosterWidget()
    roster.populate_crew(orchestrator)
    assert len(roster.cards) > 0
    assert roster.grid_layout.count() > 0

    # Toggle coffee break via signal
    break_signals = []
    roster.break_toggled.connect(lambda aid, state: break_signals.append((aid, state)))

    card = roster.cards.get(dev.persona.agent_id)
    assert card is not None
    card.btn_break.click()
    assert len(break_signals) == 1
    assert break_signals[0] == (dev.persona.agent_id, True)


def test_chatflow_and_handoff_cards(qapp):
    chat = ChatFlowWidget()
    initial_count = len(chat.channel_messages.get("#genel-ofis", []))

    chat.add_message(
        channel="#genel-ofis",
        sender="Developer",
        text="Mimari şasi tamamlandı, teste hazır.",
        role="Developer",
        avatar="💻",
    )
    assert len(chat.channel_messages["#genel-ofis"]) == initial_count + 1
    assert chat.channel_messages["#genel-ofis"][-1]["text"] == "Mimari şasi tamamlandı, teste hazır."

    # Agent handoff card
    chat.add_handoff_message(
        channel="#genel-ofis",
        from_agent="Developer",
        to_agent="Tester",
        task_summary="Birim testlerini çalıştır ve doğrula",
    )
    assert len(chat.channel_messages["#genel-ofis"]) == initial_count + 2
    handoff_msg = chat.channel_messages["#genel-ofis"][-1]
    assert handoff_msg["is_handoff"] is True
    assert handoff_msg["from_agent"] == "Developer"
    assert handoff_msg["to_agent"] == "Tester"

    # Leader message submission signal
    sent_msgs = []
    chat.message_sent.connect(lambda ch, s, t: sent_msgs.append((ch, s, t)))
    chat.input_text.setText("Lütfen testleri başlatın.")
    chat._send_leader_message()

    assert len(sent_msgs) == 1
    assert sent_msgs[0][0] == "#genel-ofis"
    assert sent_msgs[0][1] == "Lider"
    assert sent_msgs[0][2] == "Lütfen testleri başlatın."


def test_pixel_canvas_coffee_break_and_speech(qapp):
    config = OfficeConfig(
        office_id="pixel_office",
        name="Pixel Studio",
        project_root=".",
        orchestrator_agent_id="orch_px",
    )
    orchestrator = OfficeOrchestrator(config=config)
    orchestrator.ensure_default_crew()

    canvas = PixelCanvas()
    canvas.resize(700, 350)

    # Set orchestrator to coffee break and talking
    orchestrator.persona.activity_state = AgentActivityState.COFFEE_BREAK
    orchestrator.persona.active_speech_text = "Mola zamanı!"
    orchestrator.persona.level = 3
    orchestrator.persona.focus_energy_pct = 75.0

    sub_personas = [w.persona for w in orchestrator.sub_agents.values()]
    canvas.set_personas(orchestrator.persona, sub_personas)
    canvas.repaint()
    assert canvas.desks[0].persona.activity_state == AgentActivityState.COFFEE_BREAK
    assert canvas.desks[0].persona.active_speech_text == "Mola zamanı!"


def test_agent_terminal_pane_input_and_attachments(qapp, sample_media_files):
    img_path, pdf_path = sample_media_files
    persona = AgentPersona(
        agent_id="term_ag_01",
        name="Terminal Specialist",
        office_id="office_test",
        role=DeskRole.DEVELOPER,
    )
    pane = AgentTerminalPane(persona=persona)

    submitted_prompts = []
    pane.prompt_submitted.connect(lambda aid, txt, att: submitted_prompts.append((aid, txt, att)))

    pane.input_prompt.setText("PDF analizini başlat")
    pane._handle_raw_file_paths([pdf_path, img_path])

    assert len(pane.attachments) == 2
    pane._submit_prompt()

    assert len(submitted_prompts) == 1
    assert submitted_prompts[0][0] == "term_ag_01"
    assert submitted_prompts[0][1] == "PDF analizini başlat"
    assert len(submitted_prompts[0][2]) == 2
    assert any(p.endswith("spec.pdf") for p in submitted_prompts[0][2])
    assert any(p.endswith("diagram.png") for p in submitted_prompts[0][2])
    # Input and attachments cleared after sending
    assert pane.input_prompt.text() == ""
    assert len(pane.attachments) == 0


def test_project_exporter_zip_and_git(tmp_path):
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
    (workspace / "data.json").write_text('{"key": "value"}', encoding="utf-8")

    # Directories that should be ignored
    (workspace / ".git").mkdir()
    (workspace / ".git" / "config").write_text("git config", encoding="utf-8")
    (workspace / "__pycache__").mkdir()
    (workspace / "__pycache__" / "temp.pyc").write_bytes(b"123")

    dest_zip = tmp_path / "exports" / "backup.zip"
    zip_res = ProjectExporter.export_office_to_zip(
        office_id="off_test",
        project_root=str(workspace),
        target_zip_path=str(dest_zip),
    )

    assert os.path.exists(zip_res)
    assert os.path.getsize(zip_res) > 0

    with zipfile.ZipFile(zip_res, "r") as z:
        names = z.namelist()
        assert "main.py" in names
        assert "data.json" in names
        assert not any(".git" in n for n in names)
        assert not any("__pycache__" in n for n in names)

    # Git checkpoint test (safe fallback when git is not initialized)
    commit_res = ProjectExporter.create_git_checkpoint(str(workspace), "Checkpoint Test")
    assert isinstance(commit_res, dict)
    assert "commit_hash" in commit_res
