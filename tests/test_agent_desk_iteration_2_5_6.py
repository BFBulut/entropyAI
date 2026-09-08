"""
Entropy Agent Desk: Comprehensive Test Suite for Iterations 2, 5, and 6 UI Components.
Tests:
1. MediaPayloadHandler (Image/PDF validation, clipboard capture, payload persistence).
2. AgentTerminalPane (Drag-and-Drop, Clipboard paste, Prompt Input Bar & signals).
3. ChatFlowWidget (Multi-channel selection, live feed, handoff format, message_sent signal).
4. CrewRosterWidget & AgentRosterCard (Gamified RPG sheet, badges, focus, coffee break toggle).
"""

import os
import sys
import tempfile
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor, QKeyEvent, QDropEvent
from PySide6.QtCore import Qt, QUrl, QMimeData, QPointF

from src.entropy.agent_desk.core.models import (
    AgentPersona,
    AgentActivityState,
    DeskRole,
)
from src.entropy.agent_desk.core.media_payload import (
    MediaPayloadHandler,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_DOC_EXTENSIONS,
)
from src.entropy.agent_desk.ui.agent_terminal_pane import AgentTerminalPane
from src.entropy.agent_desk.ui.chatflow_widget import ChatFlowWidget
from src.entropy.agent_desk.ui.crew_roster_widget import CrewRosterWidget, AgentRosterCard


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ==============================================================================
# 1. MediaPayloadHandler Tests
# ==============================================================================

def test_media_payload_handler_extensions():
    assert MediaPayloadHandler.is_supported("test.png") is True
    assert MediaPayloadHandler.is_supported("document.pdf") is True
    assert MediaPayloadHandler.is_supported("photo.JPEG") is True
    assert MediaPayloadHandler.is_supported("archive.zip") is False
    assert MediaPayloadHandler.is_supported("script.exe") is False

    assert MediaPayloadHandler.is_image("image.png") is True
    assert MediaPayloadHandler.is_image("doc.pdf") is False
    assert MediaPayloadHandler.is_pdf("doc.pdf") is True
    assert MediaPayloadHandler.is_pdf("doc.png") is False


def test_media_payload_handler_save_clipboard_image(qapp):
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 100x100 RGB image
        img = QImage(100, 100, QImage.Format_RGB32)
        img.fill(QColor("red"))

        saved_path = MediaPayloadHandler.save_clipboard_image(img, target_dir=tmp_dir)
        assert saved_path is not None
        assert os.path.exists(saved_path)
        assert saved_path.endswith(".png")

        info = MediaPayloadHandler.get_payload_info(saved_path)
        assert info["exists"] is True
        assert info["is_image"] is True
        assert info["size_bytes"] > 0

        b64 = MediaPayloadHandler.get_base64_encoded(saved_path)
        assert len(b64) > 0


def test_media_payload_handler_process_file_urls():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
        sample_img = os.path.join(src_dir, "sample.png")
        sample_pdf = os.path.join(src_dir, "report.pdf")
        sample_txt = os.path.join(src_dir, "notes.txt")

        with open(sample_img, "wb") as f:
            f.write(b"PNG_DATA")
        with open(sample_pdf, "wb") as f:
            f.write(b"PDF_DATA")
        with open(sample_txt, "wb") as f:
            f.write(b"TXT_DATA")

        url_list = [QUrl.fromLocalFile(sample_img), QUrl.fromLocalFile(sample_pdf), QUrl.fromLocalFile(sample_txt)]
        processed = MediaPayloadHandler.process_file_urls(url_list, target_dir=dst_dir)

        assert len(processed) == 2  # Only image and pdf accepted
        assert any(p.endswith("sample.png") for p in processed)
        assert any(p.endswith("report.pdf") for p in processed)


# ==============================================================================
# 2. AgentTerminalPane Tests (Drag-and-Drop, Paste & Prompt Input Bar)
# ==============================================================================

def test_agent_terminal_pane_prompt_input_and_signals(qapp):
    persona = AgentPersona(
        agent_id="agent_quant_1",
        name="Quant Developer",
        office_id="off_test",
        role=DeskRole.DEVELOPER,
        model="claude-sonnet-4-6",
    )
    pane = AgentTerminalPane(persona=persona)

    submitted_events = []
    pane.prompt_submitted.connect(lambda aid, text, atts: submitted_events.append((aid, text, atts)))

    # Simulate user typing in the prompt input bar
    pane.input_prompt.setText("Bates SVJ modelinin Carr-Madan Fourier integralini çalıştır.")
    pane.attachments = ["/fake/path/spec.pdf"]

    pane._submit_prompt()

    assert len(submitted_events) == 1
    aid, text, atts = submitted_events[0]
    assert aid == "agent_quant_1"
    assert "Bates SVJ" in text
    assert atts == ["/fake/path/spec.pdf"]

    # Input and attachments should be reset
    assert pane.input_prompt.text() == ""
    assert len(pane.attachments) == 0

    # Verify log output in terminal
    output_text = pane.terminal_output.toPlainText()
    assert "[Kullanıcı İstemi -> Quant Developer]: Bates SVJ" in output_text


def test_agent_terminal_pane_media_attachment_handling(qapp):
    persona = AgentPersona(
        agent_id="agent_architect",
        name="CodeArchitect",
        office_id="off_test",
        role=DeskRole.CODE_ARCHITECT,
        model="gemini-3.8-flash-high",
    )
    pane = AgentTerminalPane(persona=persona)

    attached_signals = []
    pane.payload_attached.connect(lambda aid, paths: attached_signals.append((aid, paths)))

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_img = os.path.join(tmp_dir, "architecture.png")
        with open(test_img, "wb") as f:
            f.write(b"IMG_CONTENT")

        pane._handle_raw_file_paths([test_img])

        assert len(pane.attachments) == 1
        assert len(attached_signals) == 1
        assert attached_signals[0][0] == "agent_architect"
        assert "[📎 Dosya Eklendi]" in pane.terminal_output.toPlainText()


# ==============================================================================
# 3. ChatFlowWidget Tests (Multi-channel & Handoff)
# ==============================================================================

def test_chatflow_widget_channels_and_switching(qapp):
    chat = ChatFlowWidget()

    assert "#genel-ofis" in chat.channel_messages
    assert "#kodlama" in chat.channel_messages
    assert "#qa-denetim" in chat.channel_messages
    assert "#lider-istekleri" in chat.channel_messages

    assert chat.active_channel == "#genel-ofis"

    # Switch channel
    chat.switch_channel("#kodlama")
    assert chat.active_channel == "#kodlama"
    assert chat.channel_buttons["#kodlama"].isChecked() is True


def test_chatflow_widget_send_leader_message(qapp):
    chat = ChatFlowWidget()
    chat.switch_channel("#lider-istekleri")

    sent_messages = []
    chat.message_sent.connect(lambda ch, sender, txt: sent_messages.append((ch, sender, txt)))

    chat.input_text.setText("Hedef: Bates (1996) SVJ modülünü doğrula.")
    chat._send_leader_message()

    assert len(sent_messages) == 1
    ch, sender, txt = sent_messages[0]
    assert ch == "#lider-istekleri"
    assert sender == "Lider"
    assert "Bates (1996)" in txt
    assert chat.input_text.text() == ""


def test_chatflow_widget_agent_handoff(qapp):
    chat = ChatFlowWidget()
    chat.switch_channel("#kodlama")

    handoffs = []
    chat.handoff_dispatched.connect(lambda ch, src, dst, note: handoffs.append((ch, src, dst, note)))

    # Dispatch Handoff: CodeArchitect -> Tester
    chat.add_handoff_message(
        channel="#kodlama",
        from_agent="CodeArchitect",
        to_agent="Tester",
        task_summary="SABR modeli tamamlandı, test süitini koşturabilirsin.",
    )

    assert len(handoffs) == 1
    ch, src, dst, note = handoffs[0]
    assert ch == "#kodlama"
    assert src == "CodeArchitect"
    assert dst == "Tester"
    assert "SABR modeli tamamlandı" in note

    # Check that message list in #kodlama recorded it
    channel_msgs = chat.channel_messages["#kodlama"]
    last_msg = channel_msgs[-1]
    assert last_msg["is_handoff"] is True
    assert last_msg["from_agent"] == "CodeArchitect"
    assert last_msg["to_agent"] == "Tester"


# ==============================================================================
# 4. CrewRosterWidget & AgentRosterCard Tests (RPG Character Sheet & Coffee Break)
# ==============================================================================

def test_crew_roster_card_coffee_break_toggle(qapp):
    persona = AgentPersona(
        agent_id="tester_1",
        name="Tester Lead",
        office_id="off_test",
        role=DeskRole.TESTER,
        model="claude-sonnet-4-6",
        activity_state=AgentActivityState.IDLE,
    )

    card = AgentRosterCard(persona=persona, xp=400, max_xp=500, level=4, focus_pct=90)

    break_events = []
    card.break_toggled.connect(lambda aid, on_break: break_events.append((aid, on_break)))

    # Click coffee break
    card.btn_coffee_break.click()
    assert len(break_events) == 1
    assert break_events[0] == ("tester_1", True)
    assert card.is_on_break is True
    assert card.persona.activity_state == AgentActivityState.COFFEE_BREAK
    assert "Çalışmaya Çağır" in card.btn_coffee_break.text()

    # Click resume work
    card.btn_coffee_break.click()
    assert len(break_events) == 2
    assert break_events[1] == ("tester_1", False)
    assert card.is_on_break is False
    assert card.persona.activity_state == AgentActivityState.IDLE
    assert "Kahve Molası Ver" in card.btn_coffee_break.text()


def test_crew_roster_widget_bulk_operations(qapp):
    p1 = AgentPersona(
        agent_id="dev_1",
        name="Lead Dev",
        office_id="off_test",
        role=DeskRole.DEVELOPER,
        model="claude-sonnet-4-6",
    )
    p2 = AgentPersona(
        agent_id="test_1",
        name="QA Engineer",
        office_id="off_test",
        role=DeskRole.TESTER,
        model="gemini-3.8-flash-high",
    )

    roster = CrewRosterWidget()
    roster.set_personas([p1, p2])

    assert len(roster.cards) == 2

    # Break all
    roster._break_all()
    assert roster.cards["dev_1"].is_on_break is True
    assert roster.cards["test_1"].is_on_break is True
    assert "2 Molada" in roster.lbl_stats.text()

    # Resume all
    roster._resume_all()
    assert roster.cards["dev_1"].is_on_break is False
    assert roster.cards["test_1"].is_on_break is False
    assert "0 Molada" in roster.lbl_stats.text()
